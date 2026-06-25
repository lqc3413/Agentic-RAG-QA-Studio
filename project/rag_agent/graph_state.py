from typing import List, Annotated, Set
from langgraph.graph import MessagesState
import operator


def accumulate_or_reset(existing: List[dict], new: List[dict]) -> List[dict]:
    """合并子 Agent 答案，遇到 reset 标记时清空旧答案。"""
    if new and any(item.get('__reset__') for item in new):
        return []
    return existing + new


def set_union(a: Set[str], b: Set[str]) -> Set[str]:
    """合并已处理过的检索结果标识，避免重复压缩。"""
    return a | b


def union_reducer(existing: List[str], new: List[str]) -> List[str]:
    """合并去重，并保留原有顺序，防止并行节点返回相同状态时并发报错。"""
    if not existing:
        return new or []
    if not new:
        return existing or []
    res = list(existing)
    for item in new:
        if item not in res:
            res.append(item)
    return res


class State(MessagesState):
    """主智能体决策图的状态"""
    questionIsClear: bool = False
    is_retrieval_needed: bool = True
    conversation_summary: str = ""
    originalQuery: str = "" 
    rewrittenQuestions: List[str] = []
    agent_answers: Annotated[List[dict], accumulate_or_reset] = []
    fact_memories: Annotated[List[str], union_reducer] = []
    behavior_memories: Annotated[List[str], union_reducer] = []


class AgentState(MessagesState):
    """单个智能体子图的状态"""
    question: str = ""
    question_index: int = 0
    context_summary: str = ""
    retrieval_keys: Annotated[Set[str], set_union] = set()
    final_answer: str = ""
    agent_answers: List[dict] = []
    tool_call_count: Annotated[int, operator.add] = 0
    iteration_count: Annotated[int, operator.add] = 0
    fact_memories: Annotated[List[str], union_reducer] = []
    behavior_memories: Annotated[List[str], union_reducer] = []
