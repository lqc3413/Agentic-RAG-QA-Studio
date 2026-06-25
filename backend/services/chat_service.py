import re
import traceback
from typing import List, Dict, Any, AsyncGenerator
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk
from backend.schemas import ChatResponse, QueryAnalysis, RetrievalTrace, Candidate, Source, SystemAlert


TRAILING_SOURCES_PATTERN = re.compile(
    r"\n+\s*(?:---\s*)?\n?\s*\*\*Sources:\*\*\s*(?:\n\s*[-*]\s+.*)*\s*$",
    re.IGNORECASE,
)
HISTORY_SUMMARY_TITLE = "会话历史摘要"


def strip_trailing_sources_block(content: str) -> str:
    """清理模型回答结尾可能自带的 Sources 区块。"""
    return TRAILING_SOURCES_PATTERN.sub("", content).rstrip()


class ChatService:
    """驱动 RAG Agent 问答，并把回答、trace、sources 组织成 API 响应。"""

    MAX_FACT_MEMORIES = 5

    def __init__(self, rag_system):
        """保存已经初始化好的 RAGSystem 实例。"""
        self.rag_system = rag_system
        from db.agent_memory_manager import AgentMemoryManager
        from db.user_manager import UserManager
        self.memory_manager = AgentMemoryManager()
        self.user_manager = UserManager()

    async def ask(self, message: str, session_id: str = None, user_id: str = None) -> ChatResponse:
        """执行非流式问答，主要用于兼容普通 JSON 响应。"""
        import uuid
        import asyncio
        if not self.rag_system.agent_graph:
            return ChatResponse(
                answer="⚠️ RAG system agent graph is not initialized!",
                query_analysis=QueryAnalysis(is_clear=True, rewritten_queries=[], clarification_needed=""),
                answerable=False,
                failure_reason="Graph not initialized"
            )

        session_id = session_id or str(uuid.uuid4())
        thread_id = self._build_thread_id(session_id=session_id, user_id=user_id)
        request_id = str(uuid.uuid4())

        self.rag_system.clear_retrieval_traces(thread_id, request_id)

        # 1. 载入并分类该 session 下的长期记忆
        fact_memories, behavior_memories, used_memories = self._load_context_memories(
            message=message.strip(),
            session_id=session_id,
            user_id=user_id,
        )

        config = self.rag_system.get_config(thread_id, request_id, user_id=user_id)
        current_state = await self.rag_system.agent_graph.aget_state(config)

        state_update = {
            "messages": [HumanMessage(content=message.strip())],
            "fact_memories": fact_memories,
            "behavior_memories": behavior_memories
        }

        if current_state.next:
            await self.rag_system.agent_graph.aupdate_state(config, state_update)
            stream_input = None
        else:
            stream_input = state_update

        retrieval_traces: List[RetrievalTrace] = []
        answer_sources: List[Dict[str, Any]] = []
        summarize_history_buffer = ""

        try:
            async for chunk, metadata in self.rag_system.agent_graph.astream(
                stream_input, config=config, stream_mode="messages"
            ):
                node = metadata.get("langgraph_node", "")

                if node == "summarize_history" and isinstance(chunk, AIMessageChunk) and chunk.content:
                    summarize_history_buffer += chunk.content

                if isinstance(chunk, ToolMessage) and getattr(chunk, "name", "") in ("search_child_chunks", "retrieve_parent_chunks"):
                    trace = self.rag_system.pop_retrieval_trace(thread_id, request_id)
                    if trace:
                        self._process_retrieval_trace(trace, retrieval_traces, answer_sources)

            while True:
                trace = self.rag_system.pop_retrieval_trace(thread_id, request_id)
                if not trace:
                    break
                self._process_retrieval_trace(trace, retrieval_traces, answer_sources)

            final_state = await self.rag_system.agent_graph.aget_state(config)
            messages = final_state.values.get("messages", [])

            is_clear = final_state.values.get("questionIsClear", False)
            is_retrieval_needed = final_state.values.get("is_retrieval_needed", True)
            rewritten_queries = final_state.values.get("rewrittenQuestions", [])
            clarification_needed = ""

            is_clarification_interrupt = final_state.next and any(
                "request_clarification" in n for n in final_state.next
            )

            if not is_clear or is_clarification_interrupt:
                aimessages = [m for m in messages if isinstance(m, AIMessage)]
                clarification_text = (
                    aimessages[-1].content
                    if aimessages
                    else "I need more information to understand your question."
                )
                
                return ChatResponse(
                    answer=clarification_text,
                    query_analysis=QueryAnalysis(
                        is_clear=False,
                        rewritten_queries=[],
                        clarification_needed=clarification_text
                    ),
                    retrieval_traces=[],
                    sources=[],
                    answerable=False,
                    failure_reason="Query clarification needed"
                )

            aimessages = [
                m
                for m in messages
                if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)
            ]
            raw_answer = aimessages[-1].content if aimessages else "Unable to generate an answer."
            clean_answer = strip_trailing_sources_block(raw_answer)

            sources: List[Source] = []
            for src in answer_sources:
                sources.append(Source(
                    source_id=src["source_id"],
                    source=src["source"],
                    parent_id=src["parent_id"],
                    score=src["score"],
                    threshold=src["threshold"],
                    content_preview=src["content_preview"],
                    rerank_score=src.get("rerank_score"),
                ))

            failure_reason = self._get_failure_reason(
                retrieval_traces,
                answer_sources,
                is_clear=is_clear,
                is_clarification_interrupt=is_clarification_interrupt,
                clean_answer=clean_answer,
            )
            answerable = failure_reason is None

            meta = self._build_meta()
            meta["fact_memories"] = fact_memories
            meta["behavior_memories"] = behavior_memories
            meta["used_memories"] = used_memories

            system_alerts = []
            if summarize_history_buffer:
                system_alerts.append(SystemAlert(
                    title=HISTORY_SUMMARY_TITLE,
                    content=summarize_history_buffer
                ))

            # 新增：智能判定检索来源卡片
            if is_clear and not is_clarification_interrupt:
                if is_retrieval_needed:
                    if answer_sources:
                        system_alerts.append(SystemAlert(
                            title="知识库检索应答",
                            content=f"已参考知识库中的 {len(answer_sources)} 个关联片段进行解答。"
                        ))
                    else:
                        system_alerts.append(SystemAlert(
                            title="知识库检索未果",
                            content="已发起检索，但未找到关联文档。已通过大模型常识解答。"
                        ))
                else:
                    system_alerts.append(SystemAlert(
                        title="上下文直接对话",
                        content="此提问属于直接对话，已结合会话历史直接回答。"
                    ))

            # 2. 异步触发长期记忆抽取（简化版：单次 LLM 调用完成画像更新 + 事实提取 + 冲突删除）
            from rag_agent.memory_extractor import MemoryExtractor
            extractor = MemoryExtractor(memory_manager=self.memory_manager, user_manager=self.user_manager)
            asyncio.create_task(extractor.extract_and_update(message.strip(), clean_answer, session_id, user_id=user_id))

            return ChatResponse(
                answer=clean_answer,
                query_analysis=QueryAnalysis(
                    is_clear=True,
                    rewritten_queries=rewritten_queries,
                    clarification_needed=""
                ),
                retrieval_traces=retrieval_traces,
                sources=sources,
                system_alerts=system_alerts,
                answerable=answerable,
                failure_reason=failure_reason,
                meta=meta
            )

        except Exception as e:
            return ChatResponse(
                answer=f"❌ Error occurred during query execution: {str(e)}",
                query_analysis=QueryAnalysis(is_clear=True, rewritten_queries=[], clarification_needed=""),
                answerable=False,
                failure_reason=f"Exception: {str(e)}"
            )

    def _process_retrieval_trace(
        self,
        trace: Dict[str, Any],
        retrieval_traces: List[RetrievalTrace],
        answer_sources: List[Dict[str, Any]]
    ):
        """把 pipeline trace 转成前端和问答记录使用的数据结构。"""
        selected_items = trace.get("selected_results") or [
            item
            for item in trace.get("candidates", [])
            if item.get("status") == "selected"
        ]
        
        existing_keys = {src["source_key"] for src in answer_sources}
        for item in selected_items:
            source_key = (
                item.get("source", ""),
                item.get("parent_id", ""),
                item.get("content_preview", ""),
            )
            if source_key not in existing_keys:
                answer_sources.append({
                    "source_id": f"S{len(answer_sources) + 1}",
                    "source": item.get("source", ""),
                    "parent_id": item.get("parent_id", ""),
                    "score": float(item.get("score") or 0.0),
                    "threshold": float(item.get("threshold") or 0.0),
                    "rerank_score": item.get("rerank_score"),
                    "content_preview": item.get("content_preview", ""),
                    "source_key": source_key,
                })
                existing_keys.add(source_key)

        def to_candidate(item: Dict[str, Any]) -> Candidate:
            """把 trace 中的候选片段转成响应 schema。"""
            rerank_score = item.get("rerank_score")
            if rerank_score is not None:
                rerank_score = float(rerank_score)

            return Candidate(
                rank=int(item.get("rank") or 0),
                citation_id=item.get("citation_id") or "",
                parent_id=item.get("parent_id") or "",
                source=item.get("source") or "",
                score=float(item.get("score") or 0.0),
                threshold=float(item.get("threshold") or 0.0),
                status=item.get("status") or "rejected_low_score",
                content_preview=item.get("content_preview") or "",
                rejection_reason=item.get("rejection_reason"),
                rerank_score=rerank_score,
                rank_before_rerank=item.get("rank_before_rerank"),
                rank_after_rerank=item.get("rank_after_rerank"),
                content_hash=item.get("content_hash"),
                estimated_tokens=item.get("estimated_tokens"),
            )

        candidates = [to_candidate(item) for item in trace.get("candidates", [])]
        selected_candidates = [
            to_candidate(item)
            for item in trace.get("selected_results", [])
        ]
        rejected_candidates = [
            to_candidate(item)
            for item in trace.get("rejected_results", [])
        ]

        raw_parent_ids = trace.get("parent_ids") or []
        if isinstance(raw_parent_ids, str):
            parent_ids = [raw_parent_ids]
        else:
            parent_ids = [str(parent_id) for parent_id in raw_parent_ids if parent_id]

        retrieval_traces.append(RetrievalTrace(
            tool=trace.get("tool") or "search_child_chunks",
            query=trace.get("query") or "",
            top_k=int(trace.get("top_k") or 0),
            candidate_top_k=trace.get("candidate_top_k"),
            final_top_k=trace.get("final_top_k"),
            threshold=float(trace.get("threshold") or 0.0),
            rerank_enabled=bool(trace.get("rerank_enabled") or False),
            rerank_applied=bool(trace.get("rerank_applied") or False),
            rerank_provider=trace.get("rerank_provider"),
            rerank_model=trace.get("rerank_model"),
            rerank_top_k=trace.get("rerank_top_k"),
            rerank_score_threshold=trace.get("rerank_score_threshold"),
            rerank_error=trace.get("rerank_error"),
            candidate_count=int(trace.get("candidate_count") or 0),
            selected_count=int(trace.get("selected_count") or 0),
            rejected_count=int(trace.get("rejected_count") or 0),
            failure_reason=trace.get("failure_reason") or trace.get("error"),
            parent_ids=parent_ids,
            error=trace.get("error"),
            candidates=candidates,
            selected_results=selected_candidates,
            rejected_results=rejected_candidates,
            context_assembly=trace.get("context_assembly") or {},
        ))

    def _serialize_traces(self, retrieval_traces: List[RetrievalTrace]) -> List[Dict[str, Any]]:
        """把 RetrievalTrace 序列化成 SSE 和数据库可保存的字典。"""
        return [
            {
                "tool": trace.tool,
                "query": trace.query,
                "top_k": trace.top_k,
                "candidate_top_k": trace.candidate_top_k,
                "final_top_k": trace.final_top_k,
                "threshold": trace.threshold,
                "rerank_enabled": trace.rerank_enabled,
                "rerank_applied": trace.rerank_applied,
                "rerank_provider": trace.rerank_provider,
                "rerank_model": trace.rerank_model,
                "rerank_top_k": trace.rerank_top_k,
                "rerank_score_threshold": trace.rerank_score_threshold,
                "rerank_error": trace.rerank_error,
                "candidate_count": trace.candidate_count,
                "selected_count": trace.selected_count,
                "rejected_count": trace.rejected_count,
                "failure_reason": trace.failure_reason,
                "parent_ids": trace.parent_ids,
                "error": trace.error,
                "candidates": [
                    {
                        "rank": candidate.rank,
                        "citation_id": candidate.citation_id,
                        "parent_id": candidate.parent_id,
                        "source": candidate.source,
                        "score": candidate.score,
                        "threshold": candidate.threshold,
                        "status": candidate.status,
                        "rejection_reason": candidate.rejection_reason,
                        "rerank_score": candidate.rerank_score,
                        "rank_before_rerank": candidate.rank_before_rerank,
                        "rank_after_rerank": candidate.rank_after_rerank,
                        "content_hash": candidate.content_hash,
                        "estimated_tokens": candidate.estimated_tokens,
                        "content_preview": candidate.content_preview,
                    }
                    for candidate in trace.candidates
                ],
                "selected_results": [
                    {
                        "rank": candidate.rank,
                        "citation_id": candidate.citation_id,
                        "parent_id": candidate.parent_id,
                        "source": candidate.source,
                        "score": candidate.score,
                        "threshold": candidate.threshold,
                        "status": candidate.status,
                        "rejection_reason": candidate.rejection_reason,
                        "rerank_score": candidate.rerank_score,
                        "rank_before_rerank": candidate.rank_before_rerank,
                        "rank_after_rerank": candidate.rank_after_rerank,
                        "content_hash": candidate.content_hash,
                        "estimated_tokens": candidate.estimated_tokens,
                        "content_preview": candidate.content_preview,
                    }
                    for candidate in trace.selected_results
                ],
                "rejected_results": [
                    {
                        "rank": candidate.rank,
                        "citation_id": candidate.citation_id,
                        "parent_id": candidate.parent_id,
                        "source": candidate.source,
                        "score": candidate.score,
                        "threshold": candidate.threshold,
                        "status": candidate.status,
                        "rejection_reason": candidate.rejection_reason,
                        "rerank_score": candidate.rerank_score,
                        "rank_before_rerank": candidate.rank_before_rerank,
                        "rank_after_rerank": candidate.rank_after_rerank,
                        "content_hash": candidate.content_hash,
                        "estimated_tokens": candidate.estimated_tokens,
                        "content_preview": candidate.content_preview,
                    }
                    for candidate in trace.rejected_results
                ],
                "context_assembly": trace.context_assembly,
            }
            for trace in retrieval_traces
        ]

    """标准失败原因代码集合，优先用于保存与展示。"""
    STANDARD_FAILURE_REASONS = {
        "NO_RAG_TRACE",
        "NO_CHILD_CHUNK",
        "LOW_SCORE_FILTERED",
        "NO_PARENT_FOUND",
        "TOOL_ERROR",
        "RERANK_FILTERED",
        "DEDUP_FILTERED",
        "CONTEXT_BUDGET_EXCEEDED",
        "NO_CONTEXT_AFTER_ASSEMBLY",
    }

    @classmethod
    def _get_failure_reason(
        cls,
        retrieval_traces: List[RetrievalTrace],
        answer_sources: List[Dict[str, Any]],
        *,
        is_clear: bool = True,
        is_clarification_interrupt: bool = False,
        clean_answer: str = "",
    ) -> str | None:
        """根据澄清状态、检索 trace 和 sources 计算标准失败原因。

        当模型已经生成了有效回答（clean_answer 非空且非错误消息）时，
        即使所有候选片段被低分过滤，也视为已回答，仅附加 warning 级别标注
        而非将整条记录标记为未回答。
        """
        if not is_clear or is_clarification_interrupt:
            return "Query clarification needed"

        if not retrieval_traces:
            return "NO_RAG_TRACE"

        # 检查 trace 中是否有明确的严重错误
        for trace in retrieval_traces:
            if trace.failure_reason in cls.STANDARD_FAILURE_REASONS:
                # 如果模型已成功生成了有意义的回答，仅将 LOW_SCORE_FILTERED 视为 warning
                if trace.failure_reason == "LOW_SCORE_FILTERED" and cls._has_valid_answer(clean_answer):
                    continue
                return trace.failure_reason

        for trace in retrieval_traces:
            if trace.failure_reason:
                if cls._has_valid_answer(clean_answer):
                    continue
                return trace.failure_reason

        if retrieval_traces and not answer_sources:
            # 如果模型最终依然生成了有意义的答案，不标记为未回答
            if cls._has_valid_answer(clean_answer):
                return None
            return "LOW_SCORE_FILTERED"

        return None

    @staticmethod
    def _has_valid_answer(clean_answer: str) -> bool:
        """判断模型是否产生了有效的回答内容（非空且非错误消息）。"""
        if not clean_answer or not clean_answer.strip():
            return False
        stripped = clean_answer.strip()
        if stripped.startswith("❌") or stripped.startswith("⚠️"):
            return False
        if stripped.lower().startswith("unable to generate"):
            return False
        return True

    @staticmethod
    def _build_meta() -> Dict[str, Any]:
        """返回前端展示用的模型、阈值和检索配置元信息。"""
        import config as app_config

        return {
            "llm_provider": getattr(app_config, "LLM_PROVIDER", "openai_compatible"),
            "llm_model": getattr(app_config, "LLM_MODEL", ""),
            "dense_model": getattr(app_config, "DENSE_MODEL", "text-embedding-v3"),
            "sparse_model": getattr(app_config, "SPARSE_MODEL", "Qdrant/bm25"),
            "score_threshold": getattr(app_config, "SEARCH_SCORE_THRESHOLD", 0.45),
            "candidate_top_k": getattr(app_config, "RETRIEVAL_CANDIDATE_TOP_K", 12),
            "final_top_k": getattr(app_config, "RETRIEVAL_FINAL_TOP_K", 5),
            "rerank_enabled": getattr(app_config, "RERANK_ENABLED", False),
            "rerank_provider": getattr(app_config, "RERANK_PROVIDER", ""),
            "rerank_model": getattr(app_config, "RERANK_MODEL", ""),
            "rerank_top_k": getattr(app_config, "RERANK_TOP_K", 0),
            "context_max_chunks": getattr(app_config, "CONTEXT_MAX_CHUNKS", 5),
            "context_max_tokens": getattr(app_config, "CONTEXT_MAX_TOKENS", 3000),
        }

    def _save_qa_record(
        self,
        *,
        question: str,
        answer: str,
        answerable: bool,
        retrieval_traces: List[RetrievalTrace],
        answer_sources: List[Dict[str, Any]],
        failure_reason: str | None,
        meta: Dict[str, Any],
        session_id: str,
        thread_id: str,
        user_id: str = None,
    ) -> int:
        """保存一次问答记录和对应检索诊断数据。"""
        serialized_traces = self._serialize_traces(retrieval_traces)
        rejected_sources_count = sum(trace.rejected_count for trace in retrieval_traces)

        return self.rag_system.qa_record_manager.save_record(
            question=question,
            answer=answer,
            answerable=answerable,
            sources_count=len(answer_sources),
            rejected_sources_count=rejected_sources_count,
            failure_reason=failure_reason,
            trace_json=self.rag_system.qa_record_manager.dumps_json(serialized_traces),
            meta_json=self.rag_system.qa_record_manager.dumps_json(meta),
            session_id=session_id,
            thread_id=thread_id,
            user_id=user_id,
        )

    async def ask_stream(self, message: str, session_id: str = None, user_id: str = None) -> AsyncGenerator[str, None]:
        """执行流式问答，并通过 SSE 分批返回正文、trace、sources 和 meta。"""
        import json
        import asyncio
        import uuid
        if not self.rag_system.agent_graph:
            err_res = {
                "type": "text",
                "data": "⚠️ RAG system agent graph is not initialized!"
            }
            yield f"data: {json.dumps(err_res, ensure_ascii=False)}\n\n"
            return

        session_id = session_id or str(uuid.uuid4())
        thread_id = self._build_thread_id(session_id=session_id, user_id=user_id)
        request_id = str(uuid.uuid4())

        self.rag_system.clear_retrieval_traces(thread_id, request_id)

        # 1. 载入并分类该 session 下的长期记忆
        fact_memories, behavior_memories, used_memories = self._load_context_memories(
            message=message.strip(),
            session_id=session_id,
            user_id=user_id,
        )

        config = self.rag_system.get_config(thread_id, request_id, user_id=user_id)
        current_state = await self.rag_system.agent_graph.aget_state(config)

        state_update = {
            "messages": [HumanMessage(content=message.strip())],
            "fact_memories": fact_memories,
            "behavior_memories": behavior_memories
        }

        if current_state.next:
            await self.rag_system.agent_graph.aupdate_state(config, state_update)
            stream_input = None
        else:
            stream_input = state_update

        retrieval_traces: List[RetrievalTrace] = []
        answer_sources: List[Dict[str, Any]] = []
        summarize_history_buffer = ""

        query_analysis_sent = False
        history_summary_sent = False
        rag_alert_sent = False

        try:
            async for chunk, metadata in self.rag_system.agent_graph.astream(
                stream_input, config=config, stream_mode="messages"
            ):
                node = metadata.get("langgraph_node", "")

                if node == "summarize_history" and isinstance(chunk, AIMessageChunk) and chunk.content:
                    summarize_history_buffer += chunk.content

                if isinstance(chunk, ToolMessage) and getattr(chunk, "name", "") in ("search_child_chunks", "retrieve_parent_chunks"):
                    trace = self.rag_system.pop_retrieval_trace(thread_id, request_id)
                    if trace:
                        self._process_retrieval_trace(trace, retrieval_traces, answer_sources)

                if not history_summary_sent and node != "summarize_history" and summarize_history_buffer.strip():
                    yield f"data: {json.dumps({'type': 'system_alert', 'data': {'title': HISTORY_SUMMARY_TITLE, 'content': summarize_history_buffer}}, ensure_ascii=False)}\n\n"
                    history_summary_sent = True

                if not query_analysis_sent and node not in ("summarize_history", "rewrite_query") and node != "":
                    state_val = await self.rag_system.agent_graph.aget_state(config)
                    is_clear = state_val.values.get("questionIsClear", False)
                    rewritten_queries = state_val.values.get("rewrittenQuestions", [])
                    is_clarification_interrupt = state_val.next and any(
                        "request_clarification" in n for n in state_val.next
                    )
                    
                    if not is_clear or is_clarification_interrupt:
                        messages = state_val.values.get("messages", [])
                        aimessages = [m for m in messages if isinstance(m, AIMessage)]
                        clarification_text = (
                            aimessages[-1].content
                            if aimessages
                            else "I need more information to understand your question."
                        )
                        yield f"data: {json.dumps({'type': 'text', 'data': clarification_text}, ensure_ascii=False)}\n\n"
                        qa_data = {
                            "is_clear": False,
                            "rewritten_queries": [],
                            "clarification_needed": clarification_text
                        }
                        yield f"data: {json.dumps({'type': 'query_analysis', 'data': qa_data}, ensure_ascii=False)}\n\n"
                    else:
                        qa_data = {
                            "is_clear": True,
                            "rewritten_queries": rewritten_queries,
                            "clarification_needed": ""
                        }
                        yield f"data: {json.dumps({'type': 'query_analysis', 'data': qa_data}, ensure_ascii=False)}\n\n"
                        
                        # 如果不需要检索，则立即发射“上下文直接对话”系统警报
                        is_retrieval_needed = state_val.values.get("is_retrieval_needed", True)
                        if not is_retrieval_needed and not rag_alert_sent:
                            rag_alert = {
                                "title": "上下文直接对话",
                                "content": "此提问属于直接对话，已结合会话历史直接回答。"
                            }
                            yield f"data: {json.dumps({'type': 'system_alert', 'data': rag_alert}, ensure_ascii=False)}\n\n"
                            rag_alert_sent = True
                    query_analysis_sent = True

                if node in ("aggregate_answers", "fallback_response", "orchestrator") and isinstance(chunk, AIMessageChunk) and chunk.content:
                    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                        continue
                    if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                        continue
                    
                    # 在准备流式输出回答正文前，发射 RAG 系统警报（如果尚未发射且处于需要检索状态）
                    if not rag_alert_sent:
                        state_val = await self.rag_system.agent_graph.aget_state(config)
                        is_clear = state_val.values.get("questionIsClear", False)
                        is_retrieval_needed = state_val.values.get("is_retrieval_needed", True)
                        is_clarification_interrupt = state_val.next and any(
                            "request_clarification" in n for n in state_val.next
                        )
                        if is_clear and not is_clarification_interrupt:
                            if is_retrieval_needed:
                                if answer_sources:
                                    rag_alert = {
                                        "title": "知识库检索应答",
                                        "content": f"已参考知识库中的 {len(answer_sources)} 个关联片段进行解答。"
                                    }
                                else:
                                    rag_alert = {
                                        "title": "知识库检索未果",
                                        "content": "已发起检索，但未找到关联文档。已通过大模型常识解答。"
                                    }
                            else:
                                rag_alert = {
                                    "title": "上下文直接对话",
                                    "content": "此提问属于直接对话，已结合会话历史直接回答。"
                                }
                            yield f"data: {json.dumps({'type': 'system_alert', 'data': rag_alert}, ensure_ascii=False)}\n\n"
                            rag_alert_sent = True

                    yield f"data: {json.dumps({'type': 'text', 'data': chunk.content}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)

            while True:
                trace = self.rag_system.pop_retrieval_trace(thread_id, request_id)
                if not trace:
                    break
                self._process_retrieval_trace(trace, retrieval_traces, answer_sources)

            final_state = await self.rag_system.agent_graph.aget_state(config)
            messages = final_state.values.get("messages", [])

            if not history_summary_sent and summarize_history_buffer.strip():
                yield f"data: {json.dumps({'type': 'system_alert', 'data': {'title': HISTORY_SUMMARY_TITLE, 'content': summarize_history_buffer}}, ensure_ascii=False)}\n\n"
                history_summary_sent = True

            # 兜底发射 RAG 判定系统警报
            if not rag_alert_sent:
                is_clear = final_state.values.get("questionIsClear", False)
                is_retrieval_needed = final_state.values.get("is_retrieval_needed", True)
                is_clarification_interrupt = final_state.next and any(
                    "request_clarification" in n for n in final_state.next
                )
                if is_clear and not is_clarification_interrupt:
                    if is_retrieval_needed:
                        if answer_sources:
                            rag_alert = {
                                "title": "知识库检索应答",
                                "content": f"已参考知识库中的 {len(answer_sources)} 个关联片段进行解答。"
                            }
                        else:
                            rag_alert = {
                                "title": "知识库检索未果",
                                "content": "已发起检索，但未找到关联文档。已通过大模型常识解答。"
                            }
                    else:
                        rag_alert = {
                            "title": "上下文直接对话",
                            "content": "此提问属于直接对话，已结合会话历史直接回答。"
                        }
                    yield f"data: {json.dumps({'type': 'system_alert', 'data': rag_alert}, ensure_ascii=False)}\n\n"
                    rag_alert_sent = True

            if not query_analysis_sent:
                is_clear = final_state.values.get("questionIsClear", False)
                rewritten_queries = final_state.values.get("rewrittenQuestions", [])
                is_clarification_interrupt = final_state.next and any(
                    "request_clarification" in n for n in final_state.next
                )
                if not is_clear or is_clarification_interrupt:
                    aimessages = [m for m in messages if isinstance(m, AIMessage)]
                    clarification_text = (
                        aimessages[-1].content
                        if aimessages
                        else "I need more information to understand your question."
                    )
                    yield f"data: {json.dumps({'type': 'text', 'data': clarification_text}, ensure_ascii=False)}\n\n"
                    qa_data = {
                        "is_clear": False,
                        "rewritten_queries": [],
                        "clarification_needed": clarification_text
                    }
                    yield f"data: {json.dumps({'type': 'query_analysis', 'data': qa_data}, ensure_ascii=False)}\n\n"
                else:
                    qa_data = {
                        "is_clear": True,
                        "rewritten_queries": rewritten_queries,
                        "clarification_needed": ""
                    }
                    yield f"data: {json.dumps({'type': 'query_analysis', 'data': qa_data}, ensure_ascii=False)}\n\n"
                query_analysis_sent = True

            aimessages = [
                m
                for m in messages
                if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)
            ]
            raw_answer = aimessages[-1].content if aimessages else "Unable to generate an answer."
            clean_answer = strip_trailing_sources_block(raw_answer)
            yield f"data: {json.dumps({'type': 'final_answer', 'data': clean_answer}, ensure_ascii=False)}\n\n"

            serialized_traces = self._serialize_traces(retrieval_traces)
            yield f"data: {json.dumps({'type': 'traces', 'data': serialized_traces}, ensure_ascii=False)}\n\n"

            # 清理内部字段 source_key 后再发送给前端
            clean_sources = [
                {k: v for k, v in src.items() if k != 'source_key'}
                for src in answer_sources
            ]
            yield f"data: {json.dumps({'type': 'sources', 'data': clean_sources}, ensure_ascii=False)}\n\n"

            meta = self._build_meta()
            meta["fact_memories"] = fact_memories
            meta["behavior_memories"] = behavior_memories
            meta["used_memories"] = used_memories
            yield f"data: {json.dumps({'type': 'meta', 'data': meta}, ensure_ascii=False)}\n\n"

            is_clear = final_state.values.get("questionIsClear", False)
            is_clarification_interrupt = final_state.next and any(
                "request_clarification" in n for n in final_state.next
            )
            failure_reason = self._get_failure_reason(
                retrieval_traces,
                answer_sources,
                is_clear=is_clear,
                is_clarification_interrupt=is_clarification_interrupt,
                clean_answer=clean_answer,
            )
            answerable = failure_reason is None
            record_id = self._save_qa_record(
                question=message.strip(),
                answer=clean_answer,
                answerable=answerable,
                retrieval_traces=retrieval_traces,
                answer_sources=answer_sources,
                failure_reason=failure_reason,
                meta=meta,
                session_id=session_id,
                thread_id=thread_id,
                user_id=user_id,
            )
            yield f"data: {json.dumps({'type': 'record_saved', 'data': {'id': record_id}}, ensure_ascii=False)}\n\n"

            # 2. 异步触发长期记忆抽取（简化版：单次 LLM 调用完成画像更新 + 事实提取 + 冲突删除）
            from rag_agent.memory_extractor import MemoryExtractor
            extractor = MemoryExtractor(memory_manager=self.memory_manager, user_manager=self.user_manager)
            asyncio.create_task(extractor.extract_and_update(message.strip(), clean_answer, session_id, user_id=user_id))

        except Exception as e:
            traceback.print_exc()
            err_data = {
                "type": "text",
                "data": f"❌ Error occurred during query execution: {str(e)}"
            }
            yield f"data: {json.dumps(err_data, ensure_ascii=False)}\n\n"

    async def reset(self, session_id: str = "default_session", user_id: str = None):
        """重置指定 RAG 会话线程并刷新观测数据。"""
        await self.rag_system.reset_thread(self._build_thread_id(session_id=session_id, user_id=user_id))
        self.rag_system.observability.flush()

    @staticmethod
    def _build_thread_id(*, session_id: str, user_id: str = None) -> str:
        if not user_id:
            return session_id
        return f"{user_id}:{session_id}"

    def _load_context_memories(self, *, message: str, session_id: str, user_id: str = None) -> tuple[list[str], list[str], list[dict]]:
        """加载用户画像（行为偏好）和长期事实记忆。

        简化后的逻辑：
        - behavior_memories 直接从 UserManager.get_profile_as_prompt() 获取（全量注入，无需检索）。
        - fact_memories 从简化后的 AgentMemoryManager 中按词面匹配检索。
        """
        # 1. 用户画像 → behavior_memories（全量读取，不做检索）
        behavior_memories: list[str] = []
        if user_id:
            try:
                behavior_memories = self.user_manager.get_profile_as_prompt(int(user_id))
            except Exception:
                pass

        # 2. 长期事实 → fact_memories（轻量级词面检索）
        fact_candidates = self.memory_manager.search_memories(
            query=message,
            user_id=user_id,
            session_id=session_id,
            limit=self.MAX_FACT_MEMORIES,
            require_match=True,
        )

        # 记录命中
        for item in fact_candidates:
            try:
                self.memory_manager.record_hit(item["id"])
            except Exception:
                pass

        fact_memories = [item["content"] for item in fact_candidates]

        # 3. 构建前端诊断元信息
        used_items = [
            {
                "id": item.get("id"),
                "type": "fact",
                "content": item.get("content"),
                "importance": item.get("importance"),
                "hybrid_score": item.get("hybrid_score"),
                "match_score": item.get("match_score"),
                "recency_score": item.get("recency_score"),
            }
            for item in fact_candidates
        ]

        return fact_memories, behavior_memories, used_items
