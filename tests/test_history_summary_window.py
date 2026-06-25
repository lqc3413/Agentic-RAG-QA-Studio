import sys
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR / "project"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from rag_agent.nodes import rewrite_query, summarize_history
from rag_agent.schemas import QueryAnalysis


class DummySummaryLLM:
    def __init__(self):
        self.calls = []

    def with_config(self, **kwargs):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content="summary from visible history")


class DummyRewriteLLM:
    def __init__(self):
        self.calls = []

    def with_config(self, **kwargs):
        return self

    def with_structured_output(self, schema, method=None):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return QueryAnalysis(
            is_clear=True,
            questions=["RAG 和普通搜索有什么区别？"],
            clarification_needed="",
        )


class HistorySummaryWindowTests(unittest.TestCase):
    def test_tool_messages_do_not_trigger_history_summary_for_one_visible_turn(self):
        llm = DummySummaryLLM()
        messages = [
            HumanMessage(content="Redis 持久化有哪些方式？", id="m1"),
            AIMessage(content="", tool_calls=[], id="m2"),
            ToolMessage(content="search result 1", tool_call_id="call-1", name="search_child_chunks", id="m3"),
            ToolMessage(content="parent result 1", tool_call_id="call-2", name="retrieve_parent_chunks", id="m4"),
            ToolMessage(content="search result 2", tool_call_id="call-3", name="search_child_chunks", id="m5"),
            ToolMessage(content="parent result 2", tool_call_id="call-4", name="retrieve_parent_chunks", id="m6"),
            AIMessage(content="Redis 持久化主要包括 RDB 和 AOF。", id="m7"),
        ]

        result = summarize_history({"messages": messages}, llm)

        self.assertNotIn("conversation_summary", result)
        self.assertEqual(llm.calls, [])

    def test_history_summary_keeps_latest_three_visible_turns(self):
        llm = DummySummaryLLM()
        messages = [
            HumanMessage(content="Q1", id="m1"),
            AIMessage(content="A1", id="m2"),
            ToolMessage(content="tool noise", tool_call_id="call-1", name="search_child_chunks", id="m3"),
            HumanMessage(content="Q2", id="m4"),
            AIMessage(content="A2", id="m5"),
            HumanMessage(content="Q3", id="m6"),
            AIMessage(content="A3", id="m7"),
            HumanMessage(content="Q4", id="m8"),
            AIMessage(content="A4", id="m9"),
        ]

        result = summarize_history({"messages": messages}, llm)

        self.assertEqual(result["conversation_summary"], "summary from visible history")
        removed_ids = {msg.id for msg in result["messages"]}
        self.assertIn(messages[0].id, removed_ids)
        self.assertIn(messages[1].id, removed_ids)
        self.assertIn(messages[2].id, removed_ids)
        self.assertNotIn(messages[3].id, removed_ids)
        summarized_prompt = llm.calls[0][1].content
        self.assertIn("User: Q1", summarized_prompt)
        self.assertIn("Assistant: A1", summarized_prompt)
        self.assertNotIn("Q2", summarized_prompt)

    def test_rewrite_query_receives_recent_visible_history_before_summary_exists(self):
        llm = DummyRewriteLLM()
        messages = [
            HumanMessage(content="RAG 是什么？", id="m1"),
            AIMessage(content="RAG 是检索增强生成。", id="m2"),
            ToolMessage(content="tool noise", tool_call_id="call-1", name="search_child_chunks", id="m3"),
            HumanMessage(content="它和普通搜索有什么区别？", id="m4"),
        ]

        result = rewrite_query({"messages": messages}, llm)

        self.assertTrue(result["questionIsClear"])
        prompt = llm.calls[0][1].content
        self.assertIn("Recent Conversation:", prompt)
        self.assertIn("User: RAG 是什么？", prompt)
        self.assertIn("Assistant: RAG 是检索增强生成。", prompt)
        self.assertIn("User Query:\n它和普通搜索有什么区别？", prompt)
        self.assertNotIn("tool noise", prompt)

    def test_current_user_question_does_not_split_recent_completed_turn(self):
        llm = DummySummaryLLM()
        messages = [
            HumanMessage(content="Q1", id="m1"),
            AIMessage(content="A1", id="m2"),
            HumanMessage(content="Q2", id="m3"),
            AIMessage(content="A2", id="m4"),
            HumanMessage(content="Q3", id="m5"),
            AIMessage(content="A3", id="m6"),
            HumanMessage(content="Q4", id="m7"),
        ]

        result = summarize_history({"messages": messages}, llm)

        self.assertNotIn("conversation_summary", result)
        self.assertEqual(llm.calls, [])

    def test_history_summary_keeps_latest_three_completed_turns_and_current_question(self):
        llm = DummySummaryLLM()
        messages = [
            HumanMessage(content="Q1", id="m1"),
            AIMessage(content="A1", id="m2"),
            ToolMessage(content="old tool noise", tool_call_id="call-1", name="search_child_chunks", id="m3"),
            HumanMessage(content="Q2", id="m4"),
            AIMessage(content="A2", id="m5"),
            HumanMessage(content="Q3", id="m6"),
            AIMessage(content="A3", id="m7"),
            HumanMessage(content="Q4", id="m8"),
            AIMessage(content="A4", id="m9"),
            HumanMessage(content="Q5", id="m10"),
        ]

        result = summarize_history({"messages": messages}, llm)

        self.assertEqual(result["conversation_summary"], "summary from visible history")
        removed_ids = {msg.id for msg in result["messages"]}
        self.assertIn(messages[0].id, removed_ids)
        self.assertIn(messages[1].id, removed_ids)
        self.assertIn(messages[2].id, removed_ids)
        self.assertNotIn(messages[3].id, removed_ids)
        self.assertNotIn(messages[9].id, removed_ids)
        summarized_prompt = llm.calls[0][1].content
        self.assertIn("User: Q1", summarized_prompt)
        self.assertIn("Assistant: A1", summarized_prompt)
        self.assertNotIn("Q2", summarized_prompt)


if __name__ == "__main__":
    unittest.main()
