from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

import config

from .retrieval_models import RetrievalItem, lexical_overlap_score


@dataclass
class RerankResult:
    """reranker 的统一返回结构。"""

    items: list[RetrievalItem]
    applied: bool
    provider: str
    model: str
    error: str | None = None


class Reranker:
    """所有 reranker 的统一接口。"""

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalItem],
        rerank_top_k: int,
    ) -> RerankResult:
        """对候选片段重新排序。"""
        raise NotImplementedError


class LocalLexicalReranker(Reranker):
    """使用关键词重叠实现本地轻量 rerank。"""

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalItem],
        rerank_top_k: int,
    ) -> RerankResult:
        """对候选片段按词项重叠分数重新排序。"""
        head = [
            item.clone(
                rerank_score=lexical_overlap_score(query, item.content),
            )
            for item in candidates[:rerank_top_k]
        ]
        tail = [
            item.clone(rerank_score=0.0)
            for item in candidates[rerank_top_k:]
        ]

        reranked_head = sorted(
            head,
            key=lambda item: (item.rerank_score or 0.0, item.score),
            reverse=True,
        )
        reranked = reranked_head + tail
        return RerankResult(
            items=[
                item.clone(rank_after_rerank=index)
                for index, item in enumerate(reranked, start=1)
            ],
            applied=True,
            provider="local",
            model="local_lexical_v1",
        )


class ZhipuReranker(Reranker):
    """调用智谱 rerank API 对候选片段重新排序。"""

    def __init__(self):
        """读取智谱 rerank 的模型、地址、密钥和超时配置。"""
        self.endpoint = config.RERANK_API_BASE_URL
        self.api_key = config.RERANK_API_KEY
        self.model = config.RERANK_MODEL
        self.timeout = config.RERANK_TIMEOUT_SECONDS
        self.max_document_chars = config.RERANK_MAX_DOCUMENT_CHARS

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalItem],
        rerank_top_k: int,
    ) -> RerankResult:
        """调用外部 rerank 服务，失败时回退到原始召回顺序。"""
        if not self.api_key:
            return self._fallback(candidates, "RERANK_API_KEY_MISSING")

        head = candidates[:rerank_top_k]
        tail = candidates[rerank_top_k:]
        if not head:
            return RerankResult(
                items=[],
                applied=False,
                provider="zhipu",
                model=self.model,
            )

        payload = {
            "model": self.model,
            "query": query,
            "documents": [
                item.content[: self.max_document_chars]
                for item in head
            ],
            "top_n": len(head),
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return self._fallback(
                candidates,
                f"ZHIPU_RERANK_HTTP_{exc.code}: {detail[:300]}",
            )
        except Exception as exc:
            return self._fallback(candidates, f"ZHIPU_RERANK_ERROR: {exc}")

        scores_by_index: dict[int, float] = {}
        for result in data.get("results", []) or []:
            try:
                index = int(result.get("index"))
                score = float(result.get("relevance_score"))
            except (TypeError, ValueError):
                continue
            scores_by_index[index] = round(score, 4)

        reranked_head = [
            item.clone(rerank_score=scores_by_index.get(index, 0.0))
            for index, item in enumerate(head)
        ]
        reranked_head = sorted(
            reranked_head,
            key=lambda item: (item.rerank_score or 0.0, item.score),
            reverse=True,
        )
        reranked = reranked_head + [
            item.clone(rerank_score=None)
            for item in tail
        ]

        return RerankResult(
            items=[
                item.clone(rank_after_rerank=index)
                for index, item in enumerate(reranked, start=1)
            ],
            applied=True,
            provider="zhipu",
            model=self.model,
        )

    def _fallback(self, candidates: list[RetrievalItem], error: str) -> RerankResult:
        """保留候选结果，并在 trace 中记录 rerank 未生效的原因。"""
        return RerankResult(
            items=[
                item.clone(rank_after_rerank=item.rank_before_rerank, rerank_score=None)
                for item in candidates
            ],
            applied=False,
            provider="zhipu",
            model=self.model,
            error=error,
        )


def create_reranker() -> Reranker:
    """根据配置创建具体 reranker。"""
    provider = str(config.RERANK_PROVIDER).lower()
    if provider in {"zhipu", "bigmodel", "glm"}:
        return ZhipuReranker()
    if provider in {"local", "local_lexical", "local_lexical_v1"}:
        return LocalLexicalReranker()
    return LocalLexicalReranker()
