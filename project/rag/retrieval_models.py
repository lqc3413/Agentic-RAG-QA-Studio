from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


_WORD_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def normalize_text(value: str) -> str:
    """压缩文本空白，得到稳定的对比文本。"""
    return " ".join(str(value or "").split())


def content_preview(content: str, max_length: int = 180) -> str:
    """生成用于 trace 展示的短内容预览。"""
    normalized_content = normalize_text(content)
    if len(normalized_content) <= max_length:
        return normalized_content
    return normalized_content[:max_length] + "..."


def content_hash(content: str) -> str:
    """生成内容指纹，用于重复 chunk 去重。"""
    normalized_content = normalize_text(content).lower()
    return hashlib.sha1(normalized_content.encode("utf-8")).hexdigest()[:16]


def lexical_overlap_score(query: str, content: str) -> float:
    """计算 query 和候选内容的词项重叠分数。"""
    query_terms = set(_WORD_PATTERN.findall(str(query or "").lower()))
    if not query_terms:
        return 0.0

    content_terms = set(_WORD_PATTERN.findall(str(content or "").lower()))
    if not content_terms:
        return 0.0

    overlap = query_terms & content_terms
    return round(len(overlap) / len(query_terms), 4)


def estimate_tokens(text: str) -> int:
    """粗略估算文本 token 数，用于上下文预算控制。"""
    normalized = normalize_text(text)
    if not normalized:
        return 0
    return max(1, len(normalized) // 3)


@dataclass
class RetrievalItem:
    """RetrieverPipeline 内部流转的统一候选片段结构。"""

    rank: int
    parent_id: str
    source: str
    score: float
    threshold: float
    content: str
    content_preview: str
    content_hash: str
    citation_id: str = ""
    status: str = "candidate"
    rejection_reason: str | None = None
    rerank_score: float | None = None
    rank_before_rerank: int | None = None
    rank_after_rerank: int | None = None
    estimated_tokens: int = 0

    @classmethod
    def from_document(cls, *, rank: int, doc: Any, score: float, threshold: float) -> "RetrievalItem":
        """把 Qdrant 返回的 Document 和 score 转成 RetrievalItem。"""
        content = str(getattr(doc, "page_content", "") or "").strip()
        metadata = getattr(doc, "metadata", {}) or {}
        normalized_score = round(float(score), 4)

        return cls(
            rank=rank,
            parent_id=str(metadata.get("parent_id", "") or ""),
            source=str(metadata.get("source", "") or ""),
            score=normalized_score,
            threshold=threshold,
            content=content,
            content_preview=content_preview(content),
            content_hash=content_hash(content),
            rank_before_rerank=rank,
            estimated_tokens=estimate_tokens(content),
        )

    def clone(self, **updates: Any) -> "RetrievalItem":
        """复制候选片段，并覆盖指定字段。"""
        data = self.to_dict(include_content=True)
        data.update(updates)
        return RetrievalItem(**data)

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        """转换为可序列化字典，供 trace、API 和问答记录使用。"""
        data = {
            "rank": self.rank,
            "citation_id": self.citation_id,
            "parent_id": self.parent_id,
            "source": self.source,
            "score": self.score,
            "threshold": self.threshold,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "rerank_score": self.rerank_score,
            "rank_before_rerank": self.rank_before_rerank,
            "rank_after_rerank": self.rank_after_rerank,
            "content_preview": self.content_preview,
            "content_hash": self.content_hash,
            "estimated_tokens": self.estimated_tokens,
        }
        if include_content:
            data["content"] = self.content
        return data


@dataclass
class ContextAssemblyResult:
    """ContextAssembler 的筛选结果。"""

    selected: list[RetrievalItem] = field(default_factory=list)
    rejected: list[RetrievalItem] = field(default_factory=list)
    annotated_candidates: list[RetrievalItem] = field(default_factory=list)
    estimated_tokens: int = 0
    dropped_count: int = 0
    rejection_counts: dict[str, int] = field(default_factory=dict)
