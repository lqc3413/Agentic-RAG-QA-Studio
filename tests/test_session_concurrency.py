import asyncio
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR / "project"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env", override=True)

import config
config.QDRANT_DB_PATH = ":memory:"

from utils import sanitize_no_proxy_env
sanitize_no_proxy_env()

from backend.services.chat_service import ChatService
from core.rag_system import RAGSystem
from db.qa_record_manager import QARecordManager


async def test_db_migration():
    """验证旧版 QA 记录表可以平滑补 session/thread 字段。"""
    print("\n[DB Migration Test] Starting...")
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_qa_records_legacy.db"

        conn = sqlite3.connect(test_db_path)
        conn.execute(
            """
            CREATE TABLE qa_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                answerable INTEGER NOT NULL,
                sources_count INTEGER NOT NULL DEFAULT 0,
                rejected_sources_count INTEGER NOT NULL DEFAULT 0,
                failure_reason TEXT,
                trace_json TEXT NOT NULL,
                meta_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO qa_records (question, answer, answerable, trace_json, created_at)
            VALUES ('Legacy question', 'Legacy answer', 1, '{}', '2026-06-06T00:00:00Z')
            """
        )
        conn.commit()
        conn.close()

        manager = QARecordManager(db_path=str(test_db_path))

        conn = sqlite3.connect(test_db_path)
        cursor = conn.execute("PRAGMA table_info(qa_records)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        print(f"Columns in migrated DB: {columns}")
        assert "session_id" in columns, "Migration failed: session_id column missing"
        assert "thread_id" in columns, "Migration failed: thread_id column missing"

        legacy_record = manager.get_record(1)
        print(f"Legacy record read back: {legacy_record}")
        assert legacy_record["question"] == "Legacy question"
        assert legacy_record["session_id"] is None, "Legacy session_id should be None"

        new_id = manager.save_record(
            question="New question",
            answer="New answer",
            answerable=True,
            sources_count=1,
            rejected_sources_count=0,
            failure_reason=None,
            trace_json="[]",
            meta_json="{}",
            session_id="session_test_123",
            thread_id="thread_test_123",
        )
        new_record = manager.get_record(new_id)
        print(f"New record read back: {new_record}")
        assert new_record["session_id"] == "session_test_123"

    print("[DB Migration Test] PASSED.")


async def test_concurrency_isolation():
    """验证并发问答请求下 trace 不会跨 session/request 串线。"""
    print("\n[Concurrency Trace Isolation Test] Starting...")
    rag_system = RAGSystem()
    rag_system.initialize()
    chat_service = ChatService(rag_system)

    session_a = "session_A_concurrency_test"
    session_b = "session_B_concurrency_test"
    msg_a = "请问系统中的蓝鲸指的是什么？"
    msg_b = "为什么天空是蓝色的？"

    print("Sending Session A and Session B questions concurrently...")

    async def consume_stream(session_id, message):
        traces = []
        final_answer = ""
        async for chunk_str in chat_service.ask_stream(message, session_id=session_id):
            if not chunk_str.startswith("data: "):
                continue
            try:
                payload = json.loads(chunk_str[6:])
            except json.JSONDecodeError:
                continue
            if payload["type"] == "traces":
                traces.extend(payload["data"])
            elif payload["type"] == "final_answer":
                final_answer = payload["data"]
        return traces, final_answer

    traces_a, traces_b = await asyncio.gather(
        consume_stream(session_a, msg_a),
        consume_stream(session_b, msg_b),
    )
    traces_a, _ = traces_a
    traces_b, _ = traces_b

    print(f"Session A response summary: traces={len(traces_a)}")
    print(f"Session B response summary: traces={len(traces_b)}")

    for trace in traces_a:
        print(f"Trace in Session A query: '{trace['query']}'")
        assert "蓝鲸" in trace["query"], f"A Session trace polluted with B: {trace['query']}"

    for trace in traces_b:
        print(f"Trace in Session B query: '{trace['query']}'")
        assert "蓝鲸" not in trace["query"], f"B Session trace polluted with A: {trace['query']}"

    print("[Concurrency Trace Isolation Test] PASSED.")


async def main():
    await test_db_migration()
    await test_concurrency_isolation()


if __name__ == "__main__":
    asyncio.run(main())
