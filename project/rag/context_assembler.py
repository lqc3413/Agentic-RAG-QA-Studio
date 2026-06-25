from __future__ import annotations

from collections import Counter
from typing import Iterable

import config

from .retrieval_models import ContextAssemblyResult, RetrievalItem


class ContextAssembler:
    """从候选片段中筛选最终进入 LLM 上下文的内容。"""

    def __init__(
        self,
        *,
        max_chunks: int | None = None,
        max_tokens: int | None = None,
        dedup_by_parent: bool | None = None,
        dedup_by_content: bool | None = None,
    ):
        """初始化上下文数量、token 预算和去重规则。"""
        self.max_chunks = max(1, int(max_chunks or config.CONTEXT_MAX_CHUNKS))
        self.max_tokens = max(1, int(max_tokens or config.CONTEXT_MAX_TOKENS))
        self.dedup_by_parent = (
            config.CONTEXT_DEDUP_BY_PARENT
            if dedup_by_parent is None
            else bool(dedup_by_parent)
        )
        self.dedup_by_content = (
            config.CONTEXT_DEDUP_BY_CONTENT
            if dedup_by_content is None
            else bool(dedup_by_content)
        )

    def assemble(
        self,
        candidates: Iterable[RetrievalItem],
        *,
        final_limit: int,
        score_threshold: float,
        rerank_enabled: bool,
        rerank_score_threshold: float,
    ) -> ContextAssemblyResult:
        """执行阈值过滤、rerank 过滤、去重和上下文预算控制。"""
        selected: list[RetrievalItem] = []
        rejected: list[RetrievalItem] = []
        annotated_candidates: list[RetrievalItem] = []
        seen_parent_ids: set[str] = set()
        seen_content_hashes: set[str] = set()
        estimated_tokens = 0

        max_selected = max(1, min(int(final_limit), self.max_chunks))

        for candidate in candidates:
            item = candidate.clone()
            rejection_reason = self._get_rejection_reason(
                item,
                selected_count=len(selected),
                max_selected=max_selected,
                estimated_tokens=estimated_tokens,
                score_threshold=score_threshold,
                rerank_enabled=rerank_enabled,
                rerank_score_threshold=rerank_score_threshold,
                seen_parent_ids=seen_parent_ids,
                seen_content_hashes=seen_content_hashes,
            )

            if rejection_reason:
                item.status = self._status_from_reason(rejection_reason)
                item.rejection_reason = rejection_reason
                rejected.append(item)
                annotated_candidates.append(item)
                continue

            item.status = "selected"
            item.rejection_reason = None
            item.citation_id = f"S{len(selected) + 1}"
            selected.append(item)
            annotated_candidates.append(item)
            estimated_tokens += item.estimated_tokens

            if item.parent_id:
                seen_parent_ids.add(item.parent_id)
            if item.content_hash:
                seen_content_hashes.add(item.content_hash)

        rejection_counts = Counter(
            item.rejection_reason or "UNKNOWN"
            for item in rejected
        )

        return ContextAssemblyResult(
            selected=selected,
            rejected=rejected,
            annotated_candidates=annotated_candidates,
            estimated_tokens=estimated_tokens,
            dropped_count=len(rejected),
            rejection_counts=dict(rejection_counts),
        )

    def config_summary(self) -> dict:
        """返回当前上下文组装配置。"""
        return {
            "max_chunks": self.max_chunks,
            "max_tokens": self.max_tokens,
            "dedup_by_parent": self.dedup_by_parent,
            "dedup_by_content": self.dedup_by_content,
        }

    def _get_rejection_reason(
        self,
        item: RetrievalItem,
        *,
        selected_count: int,
        max_selected: int,
        estimated_tokens: int,
        score_threshold: float,
        rerank_enabled: bool,
        rerank_score_threshold: float,
        seen_parent_ids: set[str],
        seen_content_hashes: set[str],
    ) -> str | None:
        """判断候选片段是否应该被拒绝，并返回拒绝原因。"""
        if item.score < score_threshold:
            return "BELOW_SCORE_THRESHOLD"

        if (
            rerank_enabled
            and rerank_score_threshold > 0
            and (item.rerank_score is None or item.rerank_score < rerank_score_threshold)
        ):
            return "BELOW_RERANK_THRESHOLD"

        if self.dedup_by_parent and item.parent_id and item.parent_id in seen_parent_ids:
            return "DUPLICATE_PARENT"

        if self.dedup_by_content and item.content_hash and item.content_hash in seen_content_hashes:
            return "DUPLICATE_CONTENT"

        if selected_count >= max_selected:
            return "CONTEXT_BUDGET_EXCEEDED"

        if estimated_tokens + item.estimated_tokens > self.max_tokens:
            return "CONTEXT_BUDGET_EXCEEDED"

        return None

    @staticmethod
    def _status_from_reason(reason: str) -> str:
        """把拒绝原因转换成前端展示用状态。"""
        return {
            "BELOW_SCORE_THRESHOLD": "rejected_low_score",
            "BELOW_RERANK_THRESHOLD": "rejected_low_rerank",
            "DUPLICATE_PARENT": "rejected_duplicate_parent",
            "DUPLICATE_CONTENT": "rejected_duplicate_content",
            "CONTEXT_BUDGET_EXCEEDED": "rejected_context_budget",
        }.get(reason, "rejected")
