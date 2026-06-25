from typing import Literal, Set

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.types import Command

from config import BASE_TOKEN_THRESHOLD, TOKEN_GROWTH_FACTOR
from utils import estimate_context_tokens
from .graph_state import AgentState, State
from .prompts import *
from .schemas import QueryAnalysis


VISIBLE_TURN_WINDOW = 3


def _is_visible_history_message(message) -> bool:
    if isinstance(message, HumanMessage):
        return True
    if isinstance(message, AIMessage):
        return bool(message.content) and not getattr(message, "tool_calls", None)
    return False


def _split_history_for_summary(messages, *, keep_turns: int = VISIBLE_TURN_WINDOW):
    completed_turn_starts = []
    pending_human_index = None

    for index, message in enumerate(messages):
        if not _is_visible_history_message(message):
            continue
        if isinstance(message, HumanMessage):
            pending_human_index = index
        elif isinstance(message, AIMessage) and pending_human_index is not None:
            completed_turn_starts.append(pending_human_index)
            pending_human_index = None

    if len(completed_turn_starts) <= keep_turns:
        return [], []

    cutoff_index = completed_turn_starts[-keep_turns]
    old_messages = messages[:cutoff_index]
    relevant_old_msgs = [
        message
        for message in old_messages
        if _is_visible_history_message(message)
    ]
    return old_messages, relevant_old_msgs


def _format_recent_visible_history(messages, *, keep_turns: int = VISIBLE_TURN_WINDOW) -> str:
    visible_messages = [
        message
        for message in messages
        if _is_visible_history_message(message)
    ]
    if visible_messages and isinstance(visible_messages[-1], HumanMessage):
        visible_messages = visible_messages[:-1]

    recent_messages = visible_messages[-keep_turns * 2:]
    if not recent_messages:
        return ""

    lines = []
    for message in recent_messages:
        role = "User" if isinstance(message, HumanMessage) else "Assistant"
        lines.append(f"{role}: {message.content}")
    return "\n".join(lines)


def summarize_history(state: State, llm):
    """将多轮历史对话压缩成当前问题可用的滚动摘要，并物理裁剪已摘要的旧消息。"""
    messages = state.get("messages", [])
    # 窗口大小：保留最近 3 轮对话原文（即最近 6 条消息）
    old_messages, relevant_old_msgs = _split_history_for_summary(messages)
    if not old_messages:
        return {"agent_answers": [{"__reset__": True}]}

    if not relevant_old_msgs:
        # 没有需要摘要的对话消息，但依然返回 RemoveMessage 清理陈旧的工具消息以控制存储
        return {
            "messages": [RemoveMessage(id=msg.id) for msg in old_messages],
            "agent_answers": [{"__reset__": True}]
        }

    existing_summary = state.get("conversation_summary", "")
    conversation = ""
    if existing_summary:
        conversation += f"Previous Conversation Summary:\n{existing_summary}\n\n"

    conversation += "New historical messages to merge into summary:\n"
    for msg in relevant_old_msgs:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        conversation += f"{role}: {msg.content}\n"

    summary_response = llm.with_config(temperature=0.2).invoke(
        [
            SystemMessage(content=get_conversation_summary_prompt()),
            HumanMessage(content=conversation),
        ]
    )

    # 物理删除被摘要的旧消息，优化 SQLite checkpoint 体积
    remove_msgs = [RemoveMessage(id=msg.id) for msg in old_messages]

    return {
        "conversation_summary": summary_response.content,
        "messages": remove_msgs,
        "agent_answers": [{"__reset__": True}],
    }


def rewrite_query(state: State, llm):
    """将用户问题改写成适合文档检索的自包含 query，保留主图历史不被物理抹除。"""
    messages = state["messages"]
    last_message = messages[-1]
    conversation_summary = state.get("conversation_summary", "")
    recent_history = _format_recent_visible_history(messages)

    # 注入事实类长期记忆辅助改写消歧
    fact_memories = state.get("fact_memories", [])
    fact_section = ""
    if fact_memories:
        fact_section = "Relevant Fact Memories:\n" + "\n".join(f"- {fm}" for fm in fact_memories) + "\n\n"

    context_parts = []
    if conversation_summary.strip():
        context_parts.append(f"Conversation Summary:\n{conversation_summary}")
    if recent_history.strip():
        context_parts.append(f"Recent Conversation:\n{recent_history}")
    if fact_section.strip():
        context_parts.append(fact_section.strip())
    context_parts.append(f"User Query:\n{last_message.content}")
    context_section = "\n\n".join(context_parts) + "\n"

    llm_with_structure = llm.with_config(temperature=0.1).with_structured_output(
        QueryAnalysis, method="function_calling"
    )
    response = llm_with_structure.invoke(
        [
            SystemMessage(content=get_rewrite_query_prompt()),
            HumanMessage(content=context_section),
        ]
    )

    if response is None:
        return {
            "questionIsClear": True,
            "is_retrieval_needed": True,
            "originalQuery": last_message.content,
            "rewrittenQuestions": [last_message.content],
        }

    if response.is_clear:
        return {
            "questionIsClear": True,
            "is_retrieval_needed": getattr(response, "is_retrieval_needed", True),
            "originalQuery": last_message.content,
            "rewrittenQuestions": response.questions or [],
        }

    clarification = (
        response.clarification_needed
        if response.clarification_needed
        and len(response.clarification_needed.strip()) > 10
        else "I need more information to understand your question."
    )

    return {
        "questionIsClear": False,
        "messages": [AIMessage(content=clarification)],
    }


def request_clarification(state: State):
    """保留中断点，让前端向用户请求澄清。"""
    return {}


async def orchestrator(state: AgentState, llm_with_tools):
    """让 LLM 决定调用检索工具、回查 parent，或生成最终答案。"""
    context_summary = state.get("context_summary", "").strip()
    
    # 将行为规范类记忆注入决策 Prompt 尾部限制输出行为
    behavior_memories = state.get("behavior_memories", [])
    sys_prompt_content = get_orchestrator_prompt()
    if behavior_memories:
        sys_prompt_content += "\n\n[USER STYLE GUIDELINES & COLLABORATION RULES (YOU MUST STRICTLY FOLLOW)]\n"
        sys_prompt_content += "\n".join(f"- {bm}" for bm in behavior_memories)
        
    sys_msg = SystemMessage(content=sys_prompt_content)
    
    summary_injection = (
        [
            HumanMessage(
                content=(
                     "[COMPRESSED CONTEXT FROM PRIOR RESEARCH]\n\n"
                     f"{context_summary}"
                )
            )
        ]
        if context_summary
        else []
    )

    # 提取已执行过的检索历史防重复注入
    retrieved_ids = state.get("retrieval_keys", set())
    history_injection = []
    if retrieved_ids:
        parent_ids = sorted(rid.replace("parent::", "") for rid in retrieved_ids if rid.startswith("parent::"))
        search_queries = sorted(rid.replace("search::", "") for rid in retrieved_ids if rid.startswith("search::"))
        
        block = "\n[ALREADY EXECUTED - DO NOT RE-SEARCH OR DUPLICATE]\n"
        if search_queries:
            block += "Already executed search queries:\n" + "\n".join(f"- {q}" for q in search_queries) + "\n"
        if parent_ids:
            block += "Already retrieved parent document chunks:\n" + "\n".join(f"- {p}" for p in parent_ids) + "\n"
        history_injection = [SystemMessage(content=block)]

    if state.get("iteration_count", 0) == 0:
        human_msg = HumanMessage(content=state["question"])
        force_search = HumanMessage(
            content=(
                "YOU MUST CALL 'search_child_chunks' AS THE FIRST STEP "
                "TO ANSWER THIS QUESTION."
            )
        )
        response = None
        async for chunk in llm_with_tools.astream(
            [sys_msg] + summary_injection + history_injection + [human_msg, force_search]
        ):
            if response is None:
                response = chunk
            else:
                response += chunk

        return {
            "messages": [human_msg, response],
            "tool_call_count": len(response.tool_calls or []),
            "iteration_count": 1,
        }

    response = None
    async for chunk in llm_with_tools.astream(
        [sys_msg] + summary_injection + history_injection + state["messages"]
    ):
        if response is None:
            response = chunk
        else:
            response += chunk
    tool_calls = response.tool_calls if hasattr(response, "tool_calls") else []

    return {
        "messages": [response],
        "tool_call_count": len(tool_calls) if tool_calls else 0,
        "iteration_count": 1,
    }


async def fallback_response(state: AgentState, llm):
    """在工具调用达到限制时，基于已有检索内容生成兜底回答。"""
    seen = set()
    unique_contents = []

    for message in state["messages"]:
        if isinstance(message, ToolMessage) and message.content not in seen:
            unique_contents.append(message.content)
            seen.add(message.content)

    context_summary = state.get("context_summary", "").strip()

    context_parts = []
    if context_summary:
        context_parts.append(
            "## Compressed Research Context (from prior iterations)\n\n"
            f"{context_summary}"
        )

    if unique_contents:
        context_parts.append(
            "## Retrieved Data (current iteration)\n\n"
            + "\n\n".join(
                f"--- DATA SOURCE {index} ---\n{content}"
                for index, content in enumerate(unique_contents, 1)
            )
        )

    context_text = (
        "\n\n".join(context_parts)
        if context_parts
        else "No data was retrieved from the documents."
    )

    prompt_content = (
        f"USER QUERY: {state.get('question')}\n\n"
        f"{context_text}\n\n"
        "INSTRUCTION:\n"
        "Provide the best possible answer using only the data above."
    )
    response = None
    async for chunk in llm.astream(
        [
            SystemMessage(content=get_fallback_response_prompt()),
            HumanMessage(content=prompt_content),
        ]
    ):
        if response is None:
            response = chunk
        else:
            response += chunk

    return {"messages": [response]}


def should_compress_context(
    state: AgentState,
) -> Command[Literal["compress_context", "orchestrator"]]:
    """工具执行后判断是否压缩上下文，或回到 orchestrator 继续推理。"""
    import re
    messages = state["messages"]
    new_ids: Set[str] = set()
    parent_id_pattern = re.compile(r"Parent ID:\s*([^\n\s]+)")

    # 1. 解析最新一轮工具调用的参数
    for message in reversed(messages):
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            for tool_call in message.tool_calls:
                if tool_call["name"] == "retrieve_parent_chunks":
                    raw = (
                        tool_call["args"].get("parent_id")
                        or tool_call["args"].get("id")
                        or tool_call["args"].get("ids")
                        or []
                    )

                    if isinstance(raw, str):
                        new_ids.add(f"parent::{raw}")
                    else:
                        new_ids.update(f"parent::{parent_id}" for parent_id in raw)

                elif tool_call["name"] == "search_child_chunks":
                    query = tool_call["args"].get("query", "")
                    if query:
                        new_ids.add(f"search::{query}")

            break

    # 2. 从返回的 ToolMessage 文本内容中正则提取所有真正检索命中的 parent_id，解耦 RAGSystem callback 的副作用
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and message.name == "search_child_chunks":
            for pid in parent_id_pattern.findall(message.content or ""):
                if pid and pid != "n/a":
                    new_ids.add(f"parent::{pid}")
            break

    updated_ids = state.get("retrieval_keys", set()) | new_ids

    current_token_messages = estimate_context_tokens(messages)
    current_token_summary = estimate_context_tokens(
        [HumanMessage(content=state.get("context_summary", ""))]
    )
    current_tokens = current_token_messages + current_token_summary

    max_allowed = BASE_TOKEN_THRESHOLD + int(
        current_token_summary * TOKEN_GROWTH_FACTOR
    )

    goto = "compress_context" if current_tokens > max_allowed else "orchestrator"

    return Command(
        update={"retrieval_keys": updated_ids},
        goto=goto,
    )


def compress_context(state: AgentState, llm):
    """把过长的工具结果和对话压缩成可复用研究摘要。"""
    messages = state["messages"]
    existing_summary = state.get("context_summary", "").strip()

    if not messages:
        return {}

    conversation_text = (
        f"USER QUESTION:\n{state.get('question')}\n\n"
        "Conversation to compress:\n\n"
    )
    if existing_summary:
        conversation_text += (
            f"[PRIOR COMPRESSED CONTEXT]\n{existing_summary}\n\n"
        )

    for message in messages[1:]:
        if isinstance(message, AIMessage):
            tool_calls_info = ""

            if getattr(message, "tool_calls", None):
                calls = ", ".join(
                    f"{tool_call['name']}({tool_call['args']})"
                    for tool_call in message.tool_calls
                )
                tool_calls_info = f" | Tool calls: {calls}"

            conversation_text += (
                f"[ASSISTANT{tool_calls_info}]\n"
                f"{message.content or '(tool call only)'}\n\n"
            )

        elif isinstance(message, ToolMessage):
            tool_name = getattr(message, "name", "tool")
            conversation_text += (
                f"[TOOL RESULT - {tool_name}]\n"
                f"{message.content}\n\n"
            )

    summary_response = llm.invoke(
        [
            SystemMessage(content=get_context_compression_prompt()),
            HumanMessage(content=conversation_text),
        ]
    )
    new_summary = summary_response.content

    retrieved_ids: Set[str] = state.get("retrieval_keys", set())
    if retrieved_ids:
        parent_ids = sorted(
            retrieval_id
            for retrieval_id in retrieved_ids
            if retrieval_id.startswith("parent::")
        )
        search_queries = sorted(
            retrieval_id.replace("search::", "")
            for retrieval_id in retrieved_ids
            if retrieval_id.startswith("search::")
        )

        block = "\n\n---\n**Already executed (do NOT repeat):**\n"

        if parent_ids:
            block += (
                "Parent chunks retrieved:\n"
                + "\n".join(
                    f"- {parent_id.replace('parent::', '')}"
                    for parent_id in parent_ids
                )
                + "\n"
            )

        if search_queries:
            block += (
                "Search queries already run:\n"
                + "\n".join(f"- {query}" for query in search_queries)
                + "\n"
            )

        new_summary += block

    return {
        "context_summary": new_summary,
        "messages": [
            RemoveMessage(id=message.id)
            for message in messages[1:]
        ],
    }


def collect_answer(state: AgentState):
    """收集单个 Agent 子图产出的最终答案。"""
    last_message = state["messages"][-1]
    is_valid = (
        isinstance(last_message, AIMessage)
        and last_message.content
        and not last_message.tool_calls
    )
    answer = last_message.content if is_valid else "Unable to generate an answer."

    return {
        "final_answer": answer,
        "agent_answers": [
            {
                "index": state["question_index"],
                "question": state["question"],
                "answer": answer,
            }
        ],
    }


async def aggregate_answers(state: State, llm):
    """把一个或多个子问题答案聚合成最终回答。"""
    # 将行为规范类记忆注入聚合 Prompt 控制最终排版风格
    behavior_memories = state.get("behavior_memories", [])
    sys_prompt_content = get_aggregation_prompt()
    if behavior_memories:
        sys_prompt_content += "\n\n[USER STYLE GUIDELINES & COLLABORATION RULES (YOU MUST STRICTLY FOLLOW)]\n"
        sys_prompt_content += "\n".join(f"- {bm}" for bm in behavior_memories)

    if not state.get("is_retrieval_needed", True):
        conversation_summary = state.get("conversation_summary", "")
        recent_history = _format_recent_visible_history(state["messages"])
        
        prompt = (
            f"You are a helpful assistant. Directly answer the user's question based on the conversation context.\n\n"
            f"Conversation Summary:\n{conversation_summary}\n\n"
            f"Recent Conversation:\n{recent_history}\n\n"
            f"User Question: {state['originalQuery']}"
        )
        
        response = None
        async for chunk in llm.astream(
            [
                SystemMessage(content=sys_prompt_content),
                HumanMessage(content=prompt)
            ]
        ):
            if response is None:
                response = chunk
            else:
                response += chunk
        return {"messages": [response]}

    if not state.get("agent_answers"):
        return {"messages": [AIMessage(content="No answers were generated.")]}

    sorted_answers = sorted(state["agent_answers"], key=lambda item: item["index"])
    formatted_answers = ""
    for index, answer in enumerate(sorted_answers, start=1):
        formatted_answers += f"\nAnswer {index}:\n{answer['answer']}\n"

    user_message = HumanMessage(
        content=(
            f"Original user question: {state['originalQuery']}\n"
            f"Retrieved answers:{formatted_answers}"
        )
    )
    response = None
    async for chunk in llm.astream(
        [
            SystemMessage(content=sys_prompt_content),
            user_message,
        ]
    ):
        if response is None:
            response = chunk
        else:
            response += chunk

    return {"messages": [response]}
