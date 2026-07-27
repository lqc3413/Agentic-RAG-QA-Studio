import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR / "project"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.services.chat_service import ChatService


class ChatTraceContentTests(unittest.TestCase):
    def test_selected_trace_results_keep_full_content_for_ragas_evaluation(self):
        service = ChatService.__new__(ChatService)
        retrieval_traces = []
        answer_sources = []
        trace = {
            "tool": "search_child_chunks",
            "query": "What is B+ Tree?",
            "top_k": 5,
            "threshold": 0.2,
            "candidate_count": 1,
            "selected_count": 1,
            "rejected_count": 0,
            "selected_results": [
                {
                    "rank": 1,
                    "citation_id": "S1",
                    "parent_id": "p1",
                    "source": "MySQL",
                    "score": 0.9,
                    "threshold": 0.2,
                    "status": "selected",
                    "content": "FULL_CONTEXT_FOR_RAGAS",
                    "content_preview": "FULL_CONTEXT...",
                }
            ],
            "candidates": [],
            "rejected_results": [],
            "context_assembly": {},
        }

        service._process_retrieval_trace(trace, retrieval_traces, answer_sources)
        serialized = service._serialize_traces(retrieval_traces)

        self.assertEqual(
            serialized[0]["selected_results"][0]["content"],
            "FULL_CONTEXT_FOR_RAGAS",
        )


if __name__ == "__main__":
    unittest.main()
