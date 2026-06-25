from __future__ import annotations

from typing import Any

import config
from qdrant_client.http import models as qmodels

from .context_assembler import ContextAssembler
from .rerankers import create_reranker
from .retrieval_models import RetrievalItem
from .tenant_filters import build_tenant_filter


class RetrieverPipeline:
    """执行 child chunk 召回、rerank、过滤和 trace 组装。"""

    def __init__(self, collection, *, context_assembler: ContextAssembler | None = None):
        """初始化检索流水线依赖的向量库、上下文组装器和 reranker。"""
        self.collection = collection
        self.context_assembler = context_assembler or ContextAssembler()
        self.reranker = create_reranker()

    def run(
        self,
        query: str,
        *,
        final_limit: int | None = None,
        user_id: str | None = None,
        tenant: Any | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """执行一次完整检索，并返回可追踪的检索 trace。"""
        final_limit = self._normalize_final_limit(final_limit)
        candidate_top_k = self._candidate_top_k(final_limit)
        score_threshold = float(config.SEARCH_SCORE_THRESHOLD)
        rerank_enabled = bool(config.RERANK_ENABLED)
        rerank_provider = str(config.RERANK_PROVIDER)
        rerank_model = str(config.RERANK_MODEL)
        rerank_top_k = max(1, int(config.RERANK_TOP_K))
        rerank_score_threshold = float(config.RERANK_SCORE_THRESHOLD)

        effective_user_id = self._resolve_user_id(user_id=user_id, tenant=tenant)
        search_kwargs = {"k": candidate_top_k}
        
        filter_conditions = []
        if effective_user_id:
            filter_conditions.append(build_tenant_filter(effective_user_id))
            
        if category and category.strip().lower() != "general":
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="metadata.category",
                    match=qmodels.MatchValue(value=category.strip().lower()),
                )
            )
            
        if filter_conditions:
            search_kwargs["filter"] = qmodels.Filter(must=filter_conditions)

        scored_results = self.collection.similarity_search_with_score(
            query,
            **search_kwargs,
        )

        candidates = [
            RetrievalItem.from_document(
                rank=index,
                doc=doc,
                score=score,
                threshold=score_threshold,
            )
            for index, (doc, score) in enumerate(scored_results, start=1)
        ]

        rerank_result = self._rerank(
            query=query,
            candidates=candidates,
            enabled=rerank_enabled,
            rerank_top_k=rerank_top_k,
        )
        reranked_results = rerank_result["items"]
        rerank_applied = bool(rerank_result["applied"])
        rerank_error = rerank_result["error"]

        assembly = self.context_assembler.assemble(
            reranked_results,
            final_limit=final_limit,
            score_threshold=score_threshold,
            rerank_enabled=rerank_applied,
            rerank_score_threshold=rerank_score_threshold,
        )

        failure_reason = self._failure_reason(
            candidates=candidates,
            selected=assembly.selected,
            rejected=assembly.rejected,
        )

        trace_candidates = assembly.annotated_candidates[: int(config.TRACE_MAX_CANDIDATES)]

        return {
            "tool": "search_child_chunks",
            "query": query,
            "category": category,
            "top_k": candidate_top_k,
            "candidate_top_k": candidate_top_k,
            "final_top_k": final_limit,
            "threshold": score_threshold,
            "rerank_enabled": rerank_enabled,
            "rerank_applied": rerank_applied,
            "rerank_provider": rerank_provider,
            "rerank_model": rerank_model,
            "rerank_top_k": rerank_top_k,
            "rerank_score_threshold": rerank_score_threshold,
            "rerank_error": rerank_error,
            "candidate_count": len(candidates),
            "selected_count": len(assembly.selected),
            "rejected_count": len(assembly.rejected),
            "failure_reason": failure_reason,
            "user_id": effective_user_id,
            "candidates": [
                item.to_dict(include_content=True)
                for item in trace_candidates
            ],
            "candidate_results": [
                item.to_dict(include_content=True)
                for item in candidates[: int(config.TRACE_MAX_CANDIDATES)]
            ],
            "reranked_results": [
                item.to_dict(include_content=True)
                for item in reranked_results[: int(config.TRACE_MAX_CANDIDATES)]
            ],
            "selected_results": [
                item.to_dict(include_content=True)
                for item in assembly.selected
            ],
            "rejected_results": [
                item.to_dict(include_content=True)
                for item in assembly.rejected[: int(config.TRACE_MAX_CANDIDATES)]
            ],
            "context_assembly": {
                **self.context_assembler.config_summary(),
                "used_chunks": len(assembly.selected),
                "dropped_chunks": assembly.dropped_count,
                "estimated_tokens": assembly.estimated_tokens,
                "rejection_counts": assembly.rejection_counts,
            },
        }

    @staticmethod
    def _normalize_final_limit(limit: int | None) -> int:
        """规范化最终进入上下文的 chunk 数。"""
        try:
            normalized = int(limit or config.RETRIEVAL_FINAL_TOP_K)
        except (TypeError, ValueError):
            normalized = int(config.RETRIEVAL_FINAL_TOP_K)

        if normalized <= 0:
            normalized = int(config.RETRIEVAL_FINAL_TOP_K)

        return min(
            normalized,
            int(config.RETRIEVAL_MAX_TOOL_LIMIT),
            int(config.RETRIEVAL_FINAL_TOP_K),
        )

    @staticmethod
    def _candidate_top_k(final_limit: int) -> int:
        """计算第一阶段候选召回数量。"""
        configured_top_k = int(config.RETRIEVAL_CANDIDATE_TOP_K)
        return max(final_limit, configured_top_k)

    @staticmethod
    def _resolve_user_id(*, user_id: str | None = None, tenant: Any | None = None) -> str | None:
        if user_id:
            return str(user_id)

        if tenant is None:
            return None

        if isinstance(tenant, dict):
            value = tenant.get("user_id")
        else:
            value = getattr(tenant, "user_id", None)

        if value:
            return str(value)
        return None

    def _rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalItem],
        enabled: bool,
        rerank_top_k: int,
    ) -> dict[str, Any]:
        """按配置执行 rerank，关闭时保留原始召回顺序。"""
        if not candidates:
            return {
                "items": [],
                "applied": False,
                "error": None,
            }

        if not enabled:
            return {
                "items": [
                    item.clone(
                        rank_after_rerank=item.rank_before_rerank,
                        rerank_score=None,
                    )
                    for item in candidates
                ],
                "applied": False,
                "error": None,
            }

        result = self.reranker.rerank(
            query=query,
            candidates=candidates,
            rerank_top_k=rerank_top_k,
        )
        return {
            "items": result.items,
            "applied": result.applied,
            "error": result.error,
        }

    @staticmethod
    def _failure_reason(
        *,
        candidates: list[RetrievalItem],
        selected: list[RetrievalItem],
        rejected: list[RetrievalItem],
    ) -> str | None:
        """把底层拒绝原因汇总为一次检索的失败原因。"""
        if not candidates:
            return "NO_CHILD_CHUNK"

        if selected:
            return None

        reasons = {item.rejection_reason for item in rejected if item.rejection_reason}
        if reasons == {"BELOW_SCORE_THRESHOLD"}:
            return "LOW_SCORE_FILTERED"
        if reasons == {"BELOW_RERANK_THRESHOLD"}:
            return "RERANK_FILTERED"
        if reasons and reasons <= {"DUPLICATE_PARENT", "DUPLICATE_CONTENT"}:
            return "DEDUP_FILTERED"
        if "CONTEXT_BUDGET_EXCEEDED" in reasons:
            return "CONTEXT_BUDGET_EXCEEDED"

        return "NO_CONTEXT_AFTER_ASSEMBLY"
