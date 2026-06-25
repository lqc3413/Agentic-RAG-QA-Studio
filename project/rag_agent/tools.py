from __future__ import annotations

from typing import Any, Callable, List

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from db.parent_store_manager import ParentStoreManager
from rag.retriever_pipeline import RetrieverPipeline


class ToolFactory:
    """把 RAG 检索能力封装成 LangGraph 可执行工具。"""

    def __init__(self, collection, trace_callback: Callable[[dict[str, Any]], None] | None = None):
        """初始化检索工具依赖的向量库、parent store 和 trace 回调。"""
        self.collection = collection
        self.parent_store_manager = ParentStoreManager()
        self.retriever_pipeline = RetrieverPipeline(collection)
        self.trace_callback = trace_callback

    def _search_child_chunks(
        self,
        query: str,
        limit: int = 5,
        category: str = None,
        config: RunnableConfig = None,
    ) -> str:
        """Search child chunks from the vector database.

        Args:
            query: The search query string.
            limit: The maximum number of results to return.
            category: The knowledge base category to filter by.
                      Available categories are:
                      - 'hr': for HR policies, employee handbook, benefits, leaves, holidays, etc.
                      - 'tech': for coding guidelines, architecture docs, dev standards, etc.
                      - 'finance': for expense reports, contracts, financial rules, etc.
                      - 'general' (or None): for any other general or miscellaneous queries.
                      Please analyze the query and choose the most relevant category.
            config: LangGraph configuration.
        """
        thread_id = None
        request_id = None
        user_id = None
        if config:
            thread_id = config.get("configurable", {}).get("thread_id")
            request_id = config.get("configurable", {}).get("request_id")
            user_id = config.get("configurable", {}).get("user_id")

        try:
            safe_limit = self._normalize_limit(limit)
            trace = self.retriever_pipeline.run(
                query,
                final_limit=safe_limit,
                user_id=user_id,
                category=category,
            )
            self._record_search_trace(trace, thread_id=thread_id, request_id=request_id)

            selected_results = trace.get("selected_results") or []
            if not selected_results:
                failure_reason = trace.get("failure_reason") or "NO_RELEVANT_CHUNKS"
                return f"NO_RELEVANT_CHUNKS: {failure_reason}"

            return self._format_search_results(selected_results)

        except Exception as exc:
            trace = {
                "tool": "search_child_chunks",
                "query": query,
                "top_k": self._normalize_limit(limit),
                "candidate_top_k": None,
                "final_top_k": self._normalize_limit(limit),
                "threshold": 0.0,
                "rerank_enabled": False,
                "rerank_applied": False,
                "candidate_count": 0,
                "selected_count": 0,
                "rejected_count": 0,
                "failure_reason": "TOOL_ERROR",
                "error": str(exc),
                "candidates": [],
                "selected_results": [],
                "rejected_results": [],
                "context_assembly": {},
            }
            self._record_search_trace(trace, thread_id=thread_id, request_id=request_id)
            return f"RETRIEVAL_ERROR: {str(exc)}"

    def _retrieve_many_parent_chunks(
        self,
        parent_ids: List[str],
        config: RunnableConfig = None,
    ) -> str:
        """根据多个 parent_id 读取完整 parent chunks。"""
        try:
            ids = [parent_ids] if isinstance(parent_ids, str) else list(parent_ids)
            user_id = None
            if config:
                user_id = config.get("configurable", {}).get("user_id")
            raw_parents = self.parent_store_manager.load_content_many(ids, user_id=user_id)
            if not raw_parents:
                return "NO_PARENT_DOCUMENTS"

            return "\n\n".join(
                [
                     f"Parent ID: {doc.get('parent_id', 'n/a')}\n"
                     f"File Name: {doc.get('metadata', {}).get('source', 'unknown')}\n"
                     f"Content: {doc.get('content', '').strip()}"
                     for doc in raw_parents
                ]
            )

        except Exception as exc:
            return f"PARENT_RETRIEVAL_ERROR: {str(exc)}"

    def _retrieve_parent_chunks(
        self,
        parent_id: str,
        config: RunnableConfig = None,
    ) -> str:
        """根据 parent_id 读取完整 parent chunk。"""
        try:
            user_id = None
            if config:
                user_id = config.get("configurable", {}).get("user_id")
            parent = self.parent_store_manager.load_content(parent_id, user_id=user_id)
            if not parent:
                return "NO_PARENT_DOCUMENT"

            return (
                f"Parent ID: {parent.get('parent_id', 'n/a')}\n"
                f"File Name: {parent.get('metadata', {}).get('source', 'unknown')}\n"
                f"Content: {parent.get('content', '').strip()}"
            )

        except Exception as exc:
            return f"PARENT_RETRIEVAL_ERROR: {str(exc)}"

    def create_tools(self) -> List:
        """创建并返回 Agent 可调用的工具列表。"""
        search_tool = tool("search_child_chunks")(self._search_child_chunks)
        retrieve_tool = tool("retrieve_parent_chunks")(self._retrieve_parent_chunks)

        return [search_tool, retrieve_tool]

    def _record_search_trace(self, trace: dict[str, Any], thread_id: str = None, request_id: str = None) -> None:
        """把检索 trace 交给 RAGSystem 暂存。"""
        if self.trace_callback:
            self.trace_callback(trace, thread_id=thread_id, request_id=request_id)

    @staticmethod
    def _normalize_limit(limit: int | None) -> int:
        """规范化 LLM 传入的工具 limit。"""
        try:
            value = int(limit or 5)
        except (TypeError, ValueError):
            value = 5

        if value <= 0:
            value = 5

        return min(value, 10)

    @staticmethod
    def _format_search_results(selected_results: list[dict[str, Any]]) -> str:
        """把入选片段格式化成 ToolMessage 内容。"""
        formatted_results = []
        for item in selected_results:
            rerank_line = ""
            if item.get("rerank_score") is not None:
                rerank_line = f"Rerank Score: {item.get('rerank_score')}\n"

            formatted_results.append(
                f"Source ID: {item.get('citation_id', '')}\n"
                f"Parent ID: {item.get('parent_id', '')}\n"
                f"File Name: {item.get('source', '')}\n"
                f"Score: {item.get('score', '')}\n"
                f"{rerank_line}"
                f"Content: {str(item.get('content', '')).strip()}"
            )

        return "\n\n".join(formatted_results)
