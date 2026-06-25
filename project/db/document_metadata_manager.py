from datetime import datetime, timezone
from pathlib import Path

from psycopg.rows import dict_row

import config
from db.pg_pool import get_pool
from document_identity import (
    PUBLIC_USER_ID,
    normalize_document_id,
    normalize_user_id,
    normalize_visibility,
)


class DocumentMetadataManager:
    def __init__(self, db_path=config.DOCUMENT_METADATA_DB_PATH):
        self._pool = get_pool()
        self._ensure_table()

    def _connect(self):
        return self._pool.connection()

    def _ensure_table(self):
        with self._pool.connection() as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_metadata (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        document_id TEXT,
                        user_id TEXT,
                        visibility TEXT NOT NULL DEFAULT 'public',
                        category TEXT NOT NULL DEFAULT 'general',
                        original_name TEXT,
                        file_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        original_size_bytes INTEGER NOT NULL DEFAULT 0,
                        parent_chunk_count INTEGER NOT NULL DEFAULT 0,
                        child_chunk_count INTEGER NOT NULL DEFAULT 0,
                        embedding_provider TEXT,
                        dense_model TEXT,
                        sparse_model TEXT,
                        child_chunk_size INTEGER,
                        child_chunk_overlap INTEGER,
                        min_parent_size INTEGER,
                        max_parent_size INTEGER,
                        collection_name TEXT,
                        error_message TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_document_metadata_document_id
                    ON document_metadata(document_id)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_document_metadata_user_visibility
                    ON document_metadata(user_id, visibility)
                    """
                )

    def upsert_document(self, metadata: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        values = self._normalize_metadata(metadata, now)

        with self._pool.connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO document_metadata (
                        name,
                        document_id,
                        user_id,
                        visibility,
                        category,
                        original_name,
                        file_type,
                        status,
                        original_size_bytes,
                        parent_chunk_count,
                        child_chunk_count,
                        embedding_provider,
                        dense_model,
                        sparse_model,
                        child_chunk_size,
                        child_chunk_overlap,
                        min_parent_size,
                        max_parent_size,
                        collection_name,
                        error_message,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(name) DO UPDATE SET
                        document_id = excluded.document_id,
                        user_id = excluded.user_id,
                        visibility = excluded.visibility,
                        category = excluded.category,
                        original_name = excluded.original_name,
                        file_type = excluded.file_type,
                        status = excluded.status,
                        original_size_bytes = excluded.original_size_bytes,
                        parent_chunk_count = excluded.parent_chunk_count,
                        child_chunk_count = excluded.child_chunk_count,
                        embedding_provider = excluded.embedding_provider,
                        dense_model = excluded.dense_model,
                        sparse_model = excluded.sparse_model,
                        child_chunk_size = excluded.child_chunk_size,
                        child_chunk_overlap = excluded.child_chunk_overlap,
                        min_parent_size = excluded.min_parent_size,
                        max_parent_size = excluded.max_parent_size,
                        collection_name = excluded.collection_name,
                        error_message = excluded.error_message,
                        updated_at = excluded.updated_at
                    """,
                    (
                        values["name"],
                        values["document_id"],
                        values["user_id"],
                        values["visibility"],
                        values["category"],
                        values["original_name"],
                        values["file_type"],
                        values["status"],
                        values["original_size_bytes"],
                        values["parent_chunk_count"],
                        values["child_chunk_count"],
                        values["embedding_provider"],
                        values["dense_model"],
                        values["sparse_model"],
                        values["child_chunk_size"],
                        values["child_chunk_overlap"],
                        values["min_parent_size"],
                        values["max_parent_size"],
                        values["collection_name"],
                        values["error_message"],
                        values["created_at"],
                        values["updated_at"],
                    ),
                )

    def get_document(self, name: str) -> dict | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM document_metadata
                WHERE name = %s
                """,
                (name,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_public_dict(row)

    def get_document_by_id(self, document_id: str) -> dict | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM document_metadata
                WHERE document_id = %s
                """,
                (document_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_public_dict(row)

    def get_all_documents(self) -> list[dict]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM document_metadata
                ORDER BY created_at DESC, name ASC
                """
            ).fetchall()

        return [self._row_to_public_dict(row) for row in rows]

    def get_documents_for_user(self, user_id: str) -> list[dict]:
        normalized_user_id = normalize_user_id(user_id)
        with self._pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM document_metadata
                WHERE visibility = 'public'
                   OR (visibility = 'private' AND user_id = %s)
                ORDER BY created_at DESC, name ASC
                """,
                (normalized_user_id,),
            ).fetchall()

        return [self._row_to_public_dict(row) for row in rows]

    def get_private_documents_for_user(self, user_id: str) -> list[dict]:
        normalized_user_id = normalize_user_id(user_id)
        with self._pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM document_metadata
                WHERE user_id = %s
                  AND visibility = 'private'
                ORDER BY created_at DESC, name ASC
                """,
                (normalized_user_id,),
            ).fetchall()

        return [self._row_to_public_dict(row) for row in rows]

    def get_private_usage(self, user_id: str) -> dict:
        normalized_user_id = normalize_user_id(user_id)
        with self._pool.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS doc_count,
                    COALESCE(SUM(original_size_bytes), 0) AS total_bytes
                FROM document_metadata
                WHERE user_id = %s
                  AND visibility = 'private'
                  AND status IN ('indexed', 'legacy')
                """,
                (normalized_user_id,),
            ).fetchone()

        return {
            "doc_count": int(row["doc_count"] or 0),
            "total_bytes": int(row["total_bytes"] or 0),
        }

    def delete_document_by_id(self, document_id: str) -> bool:
        with self._pool.connection() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    DELETE FROM document_metadata
                    WHERE document_id = %s
                    """,
                    (document_id,),
                )
                return cursor.rowcount > 0

    def delete_private_documents_for_user(self, user_id: str) -> int:
        normalized_user_id = normalize_user_id(user_id)
        with self._pool.connection() as conn:
            with conn:
                cursor = conn.execute(
                    """
                    DELETE FROM document_metadata
                    WHERE user_id = %s
                      AND visibility = 'private'
                    """,
                    (normalized_user_id,),
                )
                return int(cursor.rowcount or 0)

    def clear_all(self) -> None:
        with self._pool.connection() as conn:
            with conn:
                conn.execute("DELETE FROM document_metadata")

    def sync_from_markdown_files(
        self,
        markdown_dir: Path,
        *,
        collection_name: str | None = None,
    ) -> None:
        markdown_dir = Path(markdown_dir)
        if not markdown_dir.exists():
            return

        for path in sorted(markdown_dir.glob("*.md")):
            if self.get_document(path.name):
                continue
            self.upsert_document(
                {
                    "name": path.name,
                    "original_name": path.name,
                    "file_type": "md",
                    "status": "legacy",
                    "parent_chunk_count": 0,
                    "child_chunk_count": 0,
                    "collection_name": collection_name,
                }
            )

    @staticmethod
    def _normalize_metadata(metadata: dict, now: str) -> dict:
        return {
            "name": metadata["name"],
            "document_id": normalize_document_id(
                metadata.get("document_id"),
                fallback=metadata["name"],
            ),
            "user_id": normalize_user_id(metadata.get("user_id")),
            "visibility": normalize_visibility(
                metadata.get("visibility"),
                user_id=metadata.get("user_id"),
            ),
            "category": metadata.get("category") or "general",
            "original_name": metadata.get("original_name") or metadata["name"],
            "file_type": (metadata.get("file_type") or metadata.get("type") or "md").lower(),
            "status": metadata.get("status") or "indexed",
            "original_size_bytes": int(metadata.get("original_size_bytes") or 0),
            "parent_chunk_count": int(metadata.get("parent_chunk_count") or 0),
            "child_chunk_count": int(metadata.get("child_chunk_count") or 0),
            "embedding_provider": metadata.get("embedding_provider") or config.EMBEDDING_PROVIDER,
            "dense_model": metadata.get("dense_model") or config.DENSE_MODEL,
            "sparse_model": metadata.get("sparse_model") or config.SPARSE_MODEL,
            "child_chunk_size": metadata.get("child_chunk_size") or config.CHILD_CHUNK_SIZE,
            "child_chunk_overlap": metadata.get("child_chunk_overlap") or config.CHILD_CHUNK_OVERLAP,
            "min_parent_size": metadata.get("min_parent_size") or config.MIN_PARENT_SIZE,
            "max_parent_size": metadata.get("max_parent_size") or config.MAX_PARENT_SIZE,
            "collection_name": metadata.get("collection_name"),
            "error_message": metadata.get("error_message"),
            "created_at": metadata.get("created_at") or now,
            "updated_at": metadata.get("updated_at") or now,
        }

    @staticmethod
    def _row_to_public_dict(row: dict) -> dict:
        return {
            "name": row["name"],
            "document_id": row["document_id"] or row["name"],
            "user_id": row["user_id"] or PUBLIC_USER_ID,
            "visibility": row["visibility"] or "public",
            "category": row["category"] or "general",
            "original_name": row["original_name"],
            "type": row["file_type"],
            "status": row["status"],
            "original_size_bytes": row["original_size_bytes"],
            "parent_chunk_count": row["parent_chunk_count"],
            "child_chunk_count": row["child_chunk_count"],
            "embedding_provider": row["embedding_provider"],
            "dense_model": row["dense_model"],
            "sparse_model": row["sparse_model"],
            "child_chunk_size": row["child_chunk_size"],
            "child_chunk_overlap": row["child_chunk_overlap"],
            "min_parent_size": row["min_parent_size"],
            "max_parent_size": row["max_parent_size"],
            "collection_name": row["collection_name"],
            "error_message": row["error_message"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
