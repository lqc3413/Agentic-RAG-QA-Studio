from typing import Literal

from langgraph.types import Send

from config import MAX_ITERATIONS, MAX_TOOL_CALLS
from .graph_state import AgentState, State


def route_after_rewrite(state: State) -> Literal["request_clarification", "agent", "aggregate_answers"]:
    """根据问题改写结果，决定澄清用户、分流到答案聚合、还是进入 Agent 子图。"""
    if not state.get("questionIsClear", False):
        return "request_clarification"

    if not state.get("is_retrieval_needed", True):
        return "aggregate_answers"

    return [
        Send("agent", {
            "question": query,
            "question_index": idx,
            "messages": [],
            "fact_memories": state.get("fact_memories", []),
            "behavior_memories": state.get("behavior_memories", [])
        })
        for idx, query in enumerate(state["rewrittenQuestions"])
    ]


def route_after_orchestrator_call(state: AgentState) -> Literal["tool", "fallback_response", "collect_answer"]:
    """根据 orchestrator 是否产生 tool_calls，决定执行工具还是收集答案。"""
    iteration = state.get("iteration_count", 0)
    tool_count = state.get("tool_call_count", 0)

    if iteration >= MAX_ITERATIONS or tool_count > MAX_TOOL_CALLS:
        return "fallback_response"

    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None) or []

    if not tool_calls:
        return "collect_answer"

    return "tools"
