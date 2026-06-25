import json
from contextlib import contextmanager
from datetime import datetime, timezone

from psycopg.rows import dict_row

import config
from db.pg_pool import get_pool


class QARecordManager:
    def __init__(self, db_path=config.QA_RECORD_DB_PATH):
        self._pool = get_pool()
        self._ensure_table()

    @contextmanager
    def _connect(self):
        with self._pool.connection() as conn:
            yield conn

    def _ensure_table(self):
        with self._connect() as conn:
            self._ensure_sessions_table(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS qa_records (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    answerable INTEGER NOT NULL,
                    sources_count INTEGER NOT NULL DEFAULT 0,
                    rejected_sources_count INTEGER NOT NULL DEFAULT 0,
                    failure_reason TEXT,
                    trace_json TEXT NOT NULL,
                    meta_json TEXT,
                    created_at TEXT NOT NULL,
                    session_id TEXT,
                    thread_id TEXT,
                    user_id TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_records_session_id ON qa_records(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_records_user_session ON qa_records(user_id, session_id)")

    def _ensure_sessions_table(self, conn):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_user_session ON sessions(user_id, session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_updated ON sessions(user_id, updated_at DESC)")

    def save_record(
        self,
        *,
        question: str,
        answer: str,
        answerable: bool,
        sources_count: int,
        rejected_sources_count: int,
        failure_reason: str | None,
        trace_json: str,
        meta_json: str | None = None,
        session_id: str,
        thread_id: str,
        user_id: str | None = None,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            self._upsert_session(
                conn,
                session_id=session_id,
                question=question,
                updated_at=created_at,
                user_id=user_id,
            )
            row = conn.execute(
                """
                INSERT INTO qa_records (
                    question,
                    answer,
                    answerable,
                    sources_count,
                    rejected_sources_count,
                    failure_reason,
                    trace_json,
                    meta_json,
                    created_at,
                    session_id,
                    thread_id,
                    user_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    question,
                    answer,
                    1 if answerable else 0,
                    sources_count,
                    rejected_sources_count,
                    failure_reason,
                    trace_json,
                    meta_json,
                    created_at,
                    session_id,
                    thread_id,
                    user_id,
                ),
            ).fetchone()
            return int(row["id"])

    def _upsert_session(
        self,
        conn,
        *,
        session_id: str,
        question: str,
        updated_at: str,
        user_id: str | None,
    ):
        row = conn.execute(
            "SELECT session_id FROM sessions WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
            (session_id, user_id),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO sessions (session_id, user_id, title, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_id, user_id, self._derive_session_title(question), updated_at, updated_at),
            )
            return

        conn.execute(
            "UPDATE sessions SET updated_at = %s WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
            (updated_at, session_id, user_id),
        )

    @staticmethod
    def _derive_session_title(question: str) -> str:
        title = " ".join((question or "").split())
        if not title:
            return "新会话"

        width = 0
        chars = []
        for char in title:
            char_width = 1 if char.isascii() else 2
            if width + char_width > 60:
                break
            chars.append(char)
            width += char_width
        return "".join(chars)

    def get_sessions(self, limit: int = 50, user_id: str | None = None) -> list[dict]:
        safe_limit = max(1, min(int(limit or 50), 100))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.session_id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    COUNT(r.id) AS record_count,
                    (
                        SELECT qr.question
                        FROM qa_records qr
                        WHERE qr.session_id = s.session_id
                          AND qr.user_id IS NOT DISTINCT FROM s.user_id
                        ORDER BY qr.id DESC
                        LIMIT 1
                    ) AS last_question
                FROM sessions s
                LEFT JOIN qa_records r
                  ON r.session_id = s.session_id
                 AND r.user_id IS NOT DISTINCT FROM s.user_id
                WHERE s.user_id IS NOT DISTINCT FROM %s
                GROUP BY s.session_id, s.title, s.created_at, s.updated_at, s.user_id
                ORDER BY s.updated_at DESC
                LIMIT %s
                """,
                (user_id, safe_limit),
            ).fetchall()

        return [
            {
                "session_id": row["session_id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "record_count": row["record_count"],
                "last_question": row["last_question"],
            }
            for row in rows
        ]

    def rename_session(self, session_id: str, title: str, user_id: str | None = None) -> bool:
        clean_title = " ".join((title or "").split())
        if not clean_title:
            raise ValueError("Session title cannot be empty")
        if len(clean_title) > 80:
            raise ValueError("Session title cannot exceed 80 characters")

        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET title = %s WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
                (clean_title, session_id, user_id),
            )
            return cursor.rowcount > 0

    def count_records_by_session(self, session_id: str, user_id: str | None = None) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS record_count FROM qa_records WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
                (session_id, user_id),
            ).fetchone()
            return int(row["record_count"] or 0)

    def delete_records_by_session(self, session_id: str, user_id: str | None = None) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM qa_records WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
                (session_id, user_id),
            )
            return cursor.rowcount

    def delete_session(self, session_id: str, user_id: str | None = None) -> bool:
        with self._connect() as conn:
            session_row = conn.execute(
                "SELECT session_id FROM sessions WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
                (session_id, user_id),
            ).fetchone()
            conn.execute(
                "DELETE FROM qa_records WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
                (session_id, user_id),
            )
            cursor = conn.execute(
                "DELETE FROM sessions WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
                (session_id, user_id),
            )
            return session_row is not None or cursor.rowcount > 0

    def list_recent(self, limit: int = 20, session_id: str = None, user_id: str | None = None) -> list[dict]:
        safe_limit = max(1, min(int(limit or 20), 100))
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT
                        id,
                        question,
                        answer,
                        answerable,
                        sources_count,
                        rejected_sources_count,
                        failure_reason,
                        created_at
                    FROM qa_records
                    WHERE session_id = %s
                      AND user_id IS NOT DISTINCT FROM %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (session_id, user_id, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        id,
                        question,
                        answer,
                        answerable,
                        sources_count,
                        rejected_sources_count,
                        failure_reason,
                        created_at
                    FROM qa_records
                    WHERE user_id IS NOT DISTINCT FROM %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (user_id, safe_limit),
                ).fetchall()

        return [self._row_to_public_dict(row) for row in rows]

    def get_record(self, record_id: int, user_id: str | None = None) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    question,
                    answer,
                    answerable,
                    sources_count,
                    rejected_sources_count,
                    failure_reason,
                    trace_json,
                    meta_json,
                    created_at,
                    session_id,
                    thread_id
                FROM qa_records
                WHERE id = %s
                  AND user_id IS NOT DISTINCT FROM %s
                """,
                (record_id, user_id),
            ).fetchone()

        if row is None:
            return None

        data = self._row_to_public_dict(row)
        data["trace_json"] = row["trace_json"]
        data["meta_json"] = row["meta_json"]
        data["session_id"] = row.get("session_id")
        data["thread_id"] = row.get("thread_id")
        return data

    @staticmethod
    def dumps_json(data) -> str:
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _row_to_public_dict(row: dict) -> dict:
        return {
            "id": row["id"],
            "question": row["question"],
            "answer": row["answer"],
            "answerable": bool(row["answerable"]),
            "sources_count": row["sources_count"],
            "rejected_sources_count": row["rejected_sources_count"],
            "failure_reason": row["failure_reason"],
            "created_at": row["created_at"],
        }
