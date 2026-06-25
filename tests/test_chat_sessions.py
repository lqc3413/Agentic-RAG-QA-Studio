import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR / "project"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.agent_memory_manager import AgentMemoryManager
from db.qa_record_manager import QARecordManager
from backend.dependencies import (
    get_agent_memory_manager,
    get_chat_service,
    get_qa_record_manager,
)
from backend.routers.chat import router as chat_router
from backend.security import get_current_user


def save_record(manager: QARecordManager, session_id: str, question: str) -> int:
    return manager.save_record(
        question=question,
        answer=f"Answer for {question}",
        answerable=True,
        sources_count=1,
        rejected_sources_count=0,
        failure_reason=None,
        trace_json="[]",
        meta_json="{}",
        session_id=session_id,
        thread_id=f"thread-{session_id}",
    )


class DummyChatService:
    def __init__(self):
        self.reset_session_ids = []

    async def reset(self, session_id, user_id=None):
        self.reset_session_ids.append(f"{user_id}:{session_id}" if user_id else session_id)


class ChatSessionTests(unittest.TestCase):
    def setUp(self):
        from db.pg_pool import clear_all_tables
        clear_all_tables()
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def make_qa_manager(self):
        return QARecordManager(db_path=str(self.tmp_path / "qa_records.db"))

    def make_memory_manager(self):
        return AgentMemoryManager(db_path=str(self.tmp_path / "agent_memory.db"))

    def make_client(self, qa_manager, memory_manager, chat_service):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[get_qa_record_manager] = lambda: qa_manager
        app.dependency_overrides[get_agent_memory_manager] = lambda: memory_manager
        app.dependency_overrides[get_chat_service] = lambda: chat_service
        app.dependency_overrides[get_current_user] = lambda: {
            "id": 1,
            "username": "alice",
            "role": "user",
        }
        return TestClient(app)

    def make_unauthenticated_client(self, qa_manager, memory_manager, chat_service):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[get_qa_record_manager] = lambda: qa_manager
        app.dependency_overrides[get_agent_memory_manager] = lambda: memory_manager
        app.dependency_overrides[get_chat_service] = lambda: chat_service
        return TestClient(app)

    def test_save_record_creates_and_updates_session_metadata(self):
        manager = self.make_qa_manager()
        save_record(manager, "session-a", "What is agentic RAG and why use it?")
        first_session = manager.get_sessions()[0]

        self.assertEqual(first_session["session_id"], "session-a")
        self.assertEqual(first_session["title"], "What is agentic RAG and why use it?")
        self.assertEqual(first_session["record_count"], 1)
        self.assertEqual(first_session["last_question"], "What is agentic RAG and why use it?")

        created_at = first_session["created_at"]
        first_updated_at = first_session["updated_at"]
        time.sleep(0.01)

        save_record(manager, "session-a", "Second question should not rename the chat")
        updated_session = manager.get_sessions()[0]

        self.assertEqual(updated_session["title"], "What is agentic RAG and why use it?")
        self.assertEqual(updated_session["created_at"], created_at)
        self.assertGreater(updated_session["updated_at"], first_updated_at)
        self.assertEqual(updated_session["record_count"], 2)
        self.assertEqual(updated_session["last_question"], "Second question should not rename the chat")

    def test_blank_first_question_uses_new_session_title(self):
        manager = self.make_qa_manager()

        save_record(manager, "session-a", "   ")

        self.assertEqual(manager.get_sessions()[0]["title"], "新会话")

    def test_get_sessions_sorts_by_latest_update_and_limits(self):
        manager = self.make_qa_manager()
        save_record(manager, "old-session", "Old question")
        time.sleep(0.01)
        save_record(manager, "new-session", "New question")

        sessions = manager.get_sessions(limit=1)

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "new-session")

    def test_rename_session_rejects_blank_titles(self):
        manager = self.make_qa_manager()
        save_record(manager, "session-a", "Original title")

        self.assertTrue(manager.rename_session("session-a", "Renamed chat"))
        self.assertEqual(manager.get_sessions()[0]["title"], "Renamed chat")

        with self.assertRaises(ValueError):
            manager.rename_session("session-a", "   ")

    def test_delete_session_cascades_records(self):
        manager = self.make_qa_manager()
        first_id = save_record(manager, "session-a", "Question A")
        second_id = save_record(manager, "session-b", "Question B")

        self.assertTrue(manager.delete_session("session-a"))

        self.assertIsNone(manager.get_record(first_id))
        self.assertEqual(manager.get_record(second_id)["session_id"], "session-b")
        self.assertEqual([session["session_id"] for session in manager.get_sessions()], ["session-b"])

    def test_delete_records_by_session_removes_records_without_session_row(self):
        manager = self.make_qa_manager()
        save_record(manager, "session-a", "Question A")

        deleted_count = manager.delete_records_by_session("session-a")

        self.assertEqual(deleted_count, 1)
        self.assertEqual(manager.list_recent(session_id="session-a"), [])
        self.assertEqual(manager.get_sessions()[0]["session_id"], "session-a")
        self.assertEqual(manager.get_sessions()[0]["record_count"], 0)

    def test_agent_memory_delete_by_session(self):
        manager = self.make_memory_manager()
        manager.create_memory(session_id="session-a", content="A", source="test")
        manager.create_memory(session_id="session-a", content="B", source="test")
        manager.create_memory(session_id="session-b", content="C", source="test")

        deleted_count = manager.delete_by_session("session-a")

        self.assertEqual(deleted_count, 2)
        self.assertEqual(manager.list_memories(session_id="session-a"), [])
        self.assertEqual(len(manager.list_memories(session_id="session-b")), 1)

    def test_agent_memories_are_filtered_by_user_id(self):
        manager = self.make_memory_manager()
        manager.create_memory(session_id="shared-session", content="Alice memory", source="test", user_id="alice")
        manager.create_memory(session_id="shared-session", content="Bob memory", source="test", user_id="bob")
        manager.create_memory(session_id=None, content="Public memory", source="test", user_id="public")

        alice_memories = manager.list_memories(session_id="shared-session", user_id="alice")
        bob_memories = manager.search_memories(query="", session_id="shared-session", user_id="bob", limit=10)
        deleted_count = manager.delete_by_session("shared-session", user_id="alice")

        self.assertEqual([memory["content"] for memory in alice_memories], ["Alice memory"])
        self.assertIn("Bob memory", [memory["content"] for memory in bob_memories])
        self.assertIn("Public memory", [memory["content"] for memory in bob_memories])
        self.assertEqual(deleted_count, 1)
        self.assertEqual(manager.list_memories(session_id="shared-session", user_id="alice"), [])
        self.assertEqual(len(manager.list_memories(session_id="shared-session", user_id="bob")), 1)

    def test_chat_session_routes_list_rename_and_delete(self):
        qa_manager = self.make_qa_manager()
        memory_manager = self.make_memory_manager()
        chat_service = DummyChatService()
        qa_manager.save_record(
            question="Question A",
            answer="Answer A",
            answerable=True,
            sources_count=1,
            rejected_sources_count=0,
            failure_reason=None,
            trace_json="[]",
            meta_json="{}",
            session_id="session-a",
            thread_id="thread-session-a",
            user_id="1",
        )
        memory_manager.create_memory(session_id="session-a", content="A", source="test", user_id="1")
        client = self.make_client(qa_manager, memory_manager, chat_service)

        list_response = client.get("/api/chat/sessions")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["sessions"][0]["session_id"], "session-a")

        rename_response = client.patch("/api/chat/sessions/session-a", json={"title": "Renamed"})
        self.assertEqual(rename_response.status_code, 200)
        self.assertEqual(rename_response.json()["title"], "Renamed")

        blank_response = client.patch("/api/chat/sessions/session-a", json={"title": "  "})
        self.assertEqual(blank_response.status_code, 422)

        long_title_response = client.patch("/api/chat/sessions/session-a", json={"title": "x" * 81})
        self.assertEqual(long_title_response.status_code, 422)

        delete_response = client.delete("/api/chat/sessions/session-a")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {
                "success": True,
                "session_id": "session-a",
                "deleted_records": 1,
                "deleted_memories": 1,
            },
        )
        self.assertEqual(chat_service.reset_session_ids, ["1:session-a"])
        self.assertEqual(qa_manager.get_sessions(), [])
        self.assertEqual(memory_manager.list_memories(session_id="session-a"), [])

    def test_chat_session_routes_require_authentication(self):
        qa_manager = self.make_qa_manager()
        memory_manager = self.make_memory_manager()
        chat_service = DummyChatService()
        client = self.make_unauthenticated_client(qa_manager, memory_manager, chat_service)

        response = client.get("/api/chat/sessions")

        self.assertEqual(response.status_code, 401)

    def test_delete_session_route_reports_all_deleted_records(self):
        qa_manager = self.make_qa_manager()
        memory_manager = self.make_memory_manager()
        chat_service = DummyChatService()
        for idx in range(105):
            qa_manager.save_record(
                question=f"Question {idx}",
                answer=f"Answer {idx}",
                answerable=True,
                sources_count=1,
                rejected_sources_count=0,
                failure_reason=None,
                trace_json="[]",
                meta_json="{}",
                session_id="session-a",
                thread_id="thread-session-a",
                user_id="1",
            )
        client = self.make_client(qa_manager, memory_manager, chat_service)

        delete_response = client.delete("/api/chat/sessions/session-a")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["deleted_records"], 105)
        self.assertEqual(qa_manager.list_recent(session_id="session-a"), [])

    def test_qa_records_are_filtered_by_user_id(self):
        manager = self.make_qa_manager()
        manager.save_record(
            question="Alice question",
            answer="Alice answer",
            answerable=True,
            sources_count=0,
            rejected_sources_count=0,
            failure_reason=None,
            trace_json="[]",
            meta_json="{}",
            session_id="shared-session",
            thread_id="shared-session",
            user_id="alice",
        )
        bob_record_id = manager.save_record(
            question="Bob question",
            answer="Bob answer",
            answerable=True,
            sources_count=0,
            rejected_sources_count=0,
            failure_reason=None,
            trace_json="[]",
            meta_json="{}",
            session_id="shared-session",
            thread_id="shared-session",
            user_id="bob",
        )

        alice_sessions = manager.get_sessions(user_id="alice")
        bob_sessions = manager.get_sessions(user_id="bob")

        self.assertEqual(len(alice_sessions), 1)
        self.assertEqual(alice_sessions[0]["last_question"], "Alice question")
        self.assertEqual(alice_sessions[0]["record_count"], 1)
        self.assertEqual(len(bob_sessions), 1)
        self.assertEqual(bob_sessions[0]["last_question"], "Bob question")
        self.assertEqual(bob_sessions[0]["record_count"], 1)
        self.assertEqual(
            [record["question"] for record in manager.list_recent(session_id="shared-session", user_id="alice")],
            ["Alice question"],
        )
        self.assertIsNone(manager.get_record(bob_record_id, user_id="alice"))
        self.assertEqual(manager.get_record(bob_record_id, user_id="bob")["question"], "Bob question")

    def test_delete_session_only_removes_current_users_records(self):
        manager = self.make_qa_manager()
        save_record(manager, "shared-session", "Legacy question")
        manager.save_record(
            question="Alice question",
            answer="Alice answer",
            answerable=True,
            sources_count=0,
            rejected_sources_count=0,
            failure_reason=None,
            trace_json="[]",
            meta_json="{}",
            session_id="shared-session",
            thread_id="shared-session",
            user_id="alice",
        )
        manager.save_record(
            question="Bob question",
            answer="Bob answer",
            answerable=True,
            sources_count=0,
            rejected_sources_count=0,
            failure_reason=None,
            trace_json="[]",
            meta_json="{}",
            session_id="shared-session",
            thread_id="shared-session",
            user_id="bob",
        )

        self.assertTrue(manager.delete_session("shared-session", user_id="alice"))

        self.assertEqual(manager.list_recent(session_id="shared-session", user_id="alice"), [])
        self.assertEqual(len(manager.list_recent(session_id="shared-session", user_id="bob")), 1)
        self.assertEqual(len(manager.list_recent(session_id="shared-session", user_id=None)), 1)

    def test_sessions_table_and_updated_at_index_exist(self):
        db_path = self.tmp_path / "qa_records.db"
        QARecordManager(db_path=str(db_path))

        from db.pg_pool import get_pool
        pool = get_pool()
        with pool.connection() as conn:
            table = conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = 'sessions'"
            ).fetchone()
            index = conn.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_sessions_updated_at'"
            ).fetchone()

        self.assertIsNotNone(table)
        self.assertIsNotNone(index)

    def test_user_profile_routes_get_and_patch(self):
        from db.user_manager import UserManager
        user_manager = UserManager(db_path=str(self.tmp_path / "users.db"))
        user_manager.create_user(username="alice", password_hash="hash123")

        from backend.dependencies import get_user_manager
        app = FastAPI()
        app.include_router(chat_router)
        from backend.routers.memory import router as memory_router
        app.include_router(memory_router)

        app.dependency_overrides[get_user_manager] = lambda: user_manager
        app.dependency_overrides[get_current_user] = lambda: {
            "id": 1,
            "username": "alice",
            "role": "user",
        }
        client = TestClient(app)

        # Test GET profile (empty initially)
        response = client.get("/api/memory/profile")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["custom_rules"], [])

        # Test PATCH profile
        patch_response = client.patch(
            "/api/memory/profile",
            json={
                "preferred_language": "zh",
                "response_style": "detailed",
                "custom_rules": ["Rule 1", " Rule 1 ", "Rule 2"]
            }
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["preferred_language"], "zh")
        self.assertEqual(patch_response.json()["response_style"], "detailed")
        # Assert clean rules (whitespace trimmed and duplicates removed)
        self.assertEqual(patch_response.json()["custom_rules"], ["Rule 1", "Rule 2"])

        # Verify it persisted
        get_again = client.get("/api/memory/profile")
        self.assertEqual(get_again.json()["custom_rules"], ["Rule 1", "Rule 2"])


if __name__ == "__main__":
    unittest.main()
