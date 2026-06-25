from contextlib import contextmanager
from datetime import datetime, timezone

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import config
from db.pg_pool import get_pool


class UserManager:
    def __init__(self, db_path=config.POSTGRES_DSN):
        self._pool = get_pool()
        self._ensure_table()

    @contextmanager
    def _connect(self):
        with self._pool.connection() as conn:
            yield conn

    def _ensure_table(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    profile_json JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
                )
                """
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")

    def create_user(self, *, username: str, password_hash: str, role: str = "user") -> dict:
        now_str = datetime.now(timezone.utc).isoformat()
        clean_username = self.normalize_username(username)
        clean_role = (role or "user").strip() or "user"

        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, created_at, updated_at, profile_json)
                VALUES (%s, %s, %s, %s, %s, '{}'::jsonb)
                RETURNING id
                """,
                (clean_username, password_hash, clean_role, now_str, now_str),
            ).fetchone()
            new_id = row["id"]
            row = conn.execute(
                "SELECT * FROM users WHERE id = %s",
                (new_id,),
            ).fetchone()

        return self._row_to_dict(row)

    def get_by_username(self, username: str) -> dict | None:
        clean_username = self.normalize_username(username)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = %s",
                (clean_username,),
            ).fetchone()

        return self._row_to_dict(row) if row else None

    def get_by_id(self, user_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()

        return self._row_to_dict(row) if row else None

    # ── 用户画像读写 ──────────────────────────────────────────

    def get_profile(self, user_id: int) -> dict:
        """读取用户画像字典。若画像为空或解析失败，返回空字典。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT profile_json FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()

        if not row:
            return {}

        return row["profile_json"] or {}

    def update_profile(self, user_id: int, profile_updates: dict) -> dict:
        """将 profile_updates 合并进现有画像并保存（In-place merge）。

        返回合并后的完整画像字典。
        """
        current = self.get_profile(user_id)
        current.update(profile_updates)
        now_str = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET profile_json = %s, updated_at = %s WHERE id = %s",
                (Jsonb(current), now_str, user_id),
            )

        return current

    def get_profile_as_prompt(self, user_id: int) -> list[str]:
        """将用户画像转化为适合注入 System Prompt 的文本列表。

        每个键值对变为一条可读的规则描述。空画像返回空列表。
        """
        profile = self.get_profile(user_id)
        if not profile:
            return []

        lines = []
        for key, value in profile.items():
            if isinstance(value, list):
                for item in value:
                    lines.append(str(item))
            else:
                lines.append(f"{key}: {value}")

        return lines

    # ── 内部工具方法 ──────────────────────────────────────────

    @staticmethod
    def normalize_username(username: str) -> str:
        return (username or "").strip().lower()

    @staticmethod
    def _row_to_dict(row: dict) -> dict:
        return {
            "id": row["id"],
            "username": row["username"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
