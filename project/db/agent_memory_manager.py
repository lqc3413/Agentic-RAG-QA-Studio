import re
from contextlib import contextmanager
from datetime import datetime, timezone

from psycopg.rows import dict_row

import config
from db.pg_pool import get_pool


class AgentMemoryManager:
    """极简长期事实记忆管理器。

    设计原则（借鉴 Mem0 理念）：
    - 只存储「事实」类长期记忆，不再区分 user_preference / workflow_rule 等类型
      （用户偏好已迁移至 UserManager.profile_json）。
    - 移除 FTS5 虚表、触发器、四态版本链（superseded/pending/discard）。
    - 所有记忆默认为 active，冲突由 MemoryExtractor 在提取时一步完成物理删除。
    """

    def __init__(self, db_path=config.POSTGRES_DSN):
        self._pool = get_pool()
        self._ensure_table()


    @contextmanager
    def _connect(self):
        with self._pool.connection() as conn:
            with conn:
                yield conn

    def _ensure_table(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memories (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    session_id TEXT,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'qa_interaction',
                    importance REAL NOT NULL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT,
                    hit_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_user ON agent_memories(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_session ON agent_memories(session_id)")

    # ── 写入 ────────────────────────────────────────────────

    def create_memory(
        self,
        *,
        content: str,
        user_id: str = None,
        session_id: str = None,
        source: str = "qa_interaction",
        importance: float = 0.5,
    ) -> int:
        """写入一条长期事实记忆。"""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO agent_memories (user_id, session_id, content, source, importance, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, session_id, content, source, importance, now_str, now_str),
            ).fetchone()
            return int(row["id"])

    # ── 读取 ────────────────────────────────────────────────

    def get_memory(self, memory_id: int, user_id: str = None) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_memories WHERE id = %s AND user_id IS NOT DISTINCT FROM %s",
                (memory_id, user_id),
            ).fetchone()
            return dict(row) if row else None

    def list_memories(
        self,
        user_id: str = None,
        session_id: str = None,
        limit: int = 50,
    ) -> list[dict]:
        """列出指定用户/会话下的事实记忆，按更新时间倒序。"""
        with self._connect() as conn:
            sql = "SELECT * FROM agent_memories WHERE user_id IS NOT DISTINCT FROM %s"
            params: list = [user_id]
            if session_id:
                sql += " AND session_id = %s"
                params.append(session_id)
            sql += " ORDER BY updated_at DESC LIMIT %s"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    # ── 检索（轻量级词面匹配 + 时效性排序）──────────────────

    def search_memories(
        self,
        query: str = "",
        user_id: str = None,
        session_id: str = None,
        limit: int = 5,
        require_match: bool = False,
    ) -> list[dict]:
        """轻量级事实记忆检索。

        优先返回与 query 词面匹配度高的记忆；
        若 query 为空，按时效性返回最新的记忆。
        """
        with self._connect() as conn:
            if user_id is None:
                sql = "SELECT * FROM agent_memories WHERE user_id IS NULL"
                params = []
            else:
                sql = "SELECT * FROM agent_memories WHERE (user_id = %s OR user_id = 'public')"
                params = [user_id]

            if session_id:
                # 同时召回会话级和全局级（session_id IS NULL）的记忆
                sql += " AND (session_id = %s OR session_id IS NULL)"
                params.append(session_id)
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            return []

        memories = [dict(row) for row in rows]
        now = datetime.now(timezone.utc)

        scored = []
        for mem in memories:
            # 词面匹配分
            match_score = self._lexical_match_score(query, mem["content"]) if query.strip() else 0.0

            if require_match and query.strip() and match_score <= 0:
                continue

            # 时效性分
            ref_str = mem.get("last_used_at") or mem.get("updated_at") or mem.get("created_at")
            try:
                ref_time = datetime.fromisoformat(ref_str)
                if ref_time.tzinfo is None:
                    ref_time = ref_time.replace(tzinfo=timezone.utc)
                delta_sec = (now - ref_time).total_seconds()
            except Exception:
                delta_sec = 86400.0
            recency = 1.0 / (1.0 + max(0.0, delta_sec) / 86400.0)

            importance = mem.get("importance", 0.5)
            score = match_score * 0.5 + importance * 0.25 + recency * 0.25

            mem["match_score"] = match_score
            mem["recency_score"] = recency
            mem["hybrid_score"] = score
            scored.append(mem)

        scored.sort(key=lambda m: m["hybrid_score"], reverse=True)
        return scored[:limit]

    # ── 更新 ────────────────────────────────────────────────

    def record_hit(self, memory_id: int):
        """更新记忆的命中次数和最近使用时间。"""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE agent_memories SET hit_count = hit_count + 1, last_used_at = %s WHERE id = %s",
                (now_str, memory_id),
            )

    def update_memory(self, memory_id: int, **kwargs) -> bool:
        """更新记忆的任意字段值。"""
        if not kwargs:
            return False
        now_str = datetime.now(timezone.utc).isoformat()
        kwargs["updated_at"] = now_str
        fields = []
        params = []
        for k, v in kwargs.items():
            fields.append(f"{k} = %s")
            params.append(v)
        params.append(memory_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE agent_memories SET {', '.join(fields)} WHERE id = %s",
                params,
            )
            return True

    # ── 删除 ────────────────────────────────────────────────

    def delete_memory(self, memory_id: int, user_id: str = None) -> bool:
        """物理删除一条记忆。"""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM agent_memories WHERE id = %s AND user_id IS NOT DISTINCT FROM %s",
                (memory_id, user_id),
            )
            return True

    def delete_by_session(self, session_id: str, user_id: str = None) -> int:
        """删除指定会话的所有记忆。"""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_memories WHERE session_id = %s AND user_id IS NOT DISTINCT FROM %s",
                (session_id, user_id),
            )
            return cursor.rowcount

    def delete_memories_batch(self, memory_ids: list[int], user_id: str = None) -> int:
        """批量物理删除多条记忆（用于冲突替换）。"""
        if not memory_ids:
            return 0
        placeholders = ", ".join("%s" for _ in memory_ids)
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM agent_memories WHERE id IN ({placeholders}) AND user_id IS NOT DISTINCT FROM %s",
                [*memory_ids, user_id],
            )
            return cursor.rowcount

    # ── 内部工具 ─────────────────────────────────────────────

    @staticmethod
    def _lexical_match_score(query: str, content: str) -> float:
        """轻量级词面匹配分，兼容中英文。"""
        query_norm = (query or "").lower().strip()
        content_norm = (content or "").lower()
        if not query_norm or not content_norm:
            return 0.0

        if query_norm in content_norm:
            return 1.0

        raw_terms = re.findall(r"[a-z0-9_+-]{2,}|[\u4e00-\u9fff]{2,}", query_norm)
        terms = []
        for term in raw_terms:
            terms.append(term)
            if re.fullmatch(r"[\u4e00-\u9fff]{3,}", term):
                terms.extend(term[i : i + 2] for i in range(len(term) - 1))

        terms = [t for t in dict.fromkeys(terms) if len(t) >= 2]
        if not terms:
            return 0.0

        hits = sum(1 for t in terms if t in content_norm)
        return min(1.0, hits / min(len(terms), 5)) if hits > 0 else 0.0
