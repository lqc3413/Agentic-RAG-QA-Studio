import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR / "project"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.parent_store_manager import ParentStoreManager
from db.document_metadata_manager import DocumentMetadataManager
from document_chunker import DocumentChuncker
from rag.tenant_filters import build_tenant_filter
from rag.retriever_pipeline import RetrieverPipeline


class FakeCollection:
    def __init__(self):
        self.calls = []

    def similarity_search_with_score(self, query, **kwargs):
        self.calls.append({"query": query, **kwargs})
        return []


class TenantDocumentHelperTests(unittest.TestCase):
    def setUp(self):
        from db.pg_pool import clear_all_tables
        clear_all_tables()

    def test_metadata_manager_migrates_legacy_rows_to_public_document_fields(self):
        from db.pg_pool import get_pool
        pool = get_pool()
        with pool.connection() as conn:
            with conn:
                conn.execute("DELETE FROM document_metadata WHERE name = 'legacy.md'")
                conn.execute(
                    """
                    INSERT INTO document_metadata (
                        name, original_name, file_type, status, created_at, updated_at, document_id, user_id
                    )
                    VALUES ('legacy.md', 'legacy.md', 'md', 'legacy', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', NULL, NULL)
                    """
                )

        manager = DocumentMetadataManager()
        legacy = manager.get_document("legacy.md")

        self.assertEqual(legacy["document_id"], "legacy.md")
        self.assertEqual(legacy["user_id"], "public")
        self.assertEqual(legacy["visibility"], "public")
        self.assertEqual(legacy["original_size_bytes"], 0)

    def test_metadata_manager_accepts_new_document_identity_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DocumentMetadataManager(db_path=str(Path(tmpdir) / "metadata.db"))
            manager.upsert_document(
                {
                    "name": "same-name.md",
                    "document_id": "doc_a",
                    "user_id": "user-a",
                    "visibility": "private",
                    "original_size_bytes": 42,
                    "file_type": "md",
                    "status": "indexed",
                }
            )

            doc = manager.get_document("same-name.md")

        self.assertEqual(doc["document_id"], "doc_a")
        self.assertEqual(doc["user_id"], "user-a")
        self.assertEqual(doc["visibility"], "private")
        self.assertEqual(doc["original_size_bytes"], 42)

    def test_metadata_manager_lists_public_and_current_user_private_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DocumentMetadataManager(db_path=str(Path(tmpdir) / "metadata.db"))
            manager.upsert_document(
                {
                    "name": "public/doc-public.md",
                    "document_id": "doc-public",
                    "user_id": "public",
                    "visibility": "public",
                    "file_type": "md",
                    "status": "indexed",
                }
            )
            manager.upsert_document(
                {
                    "name": "private/alice/doc-alice.md",
                    "document_id": "doc-alice",
                    "user_id": "alice",
                    "visibility": "private",
                    "file_type": "md",
                    "status": "indexed",
                }
            )
            manager.upsert_document(
                {
                    "name": "private/bob/doc-bob.md",
                    "document_id": "doc-bob",
                    "user_id": "bob",
                    "visibility": "private",
                    "file_type": "md",
                    "status": "indexed",
                }
            )

            docs = manager.get_documents_for_user("alice")

        self.assertEqual(
            {doc["document_id"] for doc in docs},
            {"doc-public", "doc-alice"},
        )

    def test_metadata_manager_reports_private_quota_usage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DocumentMetadataManager(db_path=str(Path(tmpdir) / "metadata.db"))
            manager.upsert_document(
                {
                    "name": "private/alice/indexed.md",
                    "document_id": "indexed",
                    "user_id": "alice",
                    "visibility": "private",
                    "file_type": "md",
                    "status": "indexed",
                    "original_size_bytes": 10,
                }
            )
            manager.upsert_document(
                {
                    "name": "private/alice/legacy.md",
                    "document_id": "legacy",
                    "user_id": "alice",
                    "visibility": "private",
                    "file_type": "md",
                    "status": "legacy",
                    "original_size_bytes": 20,
                }
            )
            manager.upsert_document(
                {
                    "name": "private/alice/failed.md",
                    "document_id": "failed",
                    "user_id": "alice",
                    "visibility": "private",
                    "file_type": "md",
                    "status": "failed",
                    "original_size_bytes": 999,
                }
            )
            manager.upsert_document(
                {
                    "name": "public/shared.md",
                    "document_id": "shared",
                    "user_id": "public",
                    "visibility": "public",
                    "file_type": "md",
                    "status": "indexed",
                    "original_size_bytes": 500,
                }
            )

            usage = manager.get_private_usage("alice")

        self.assertEqual(usage, {"doc_count": 2, "total_bytes": 30})

    def test_chunker_uses_document_id_for_parent_ids_when_provided(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "same-name.md"
            md_path.write_text("# Title\n\n" + ("tenant scoped text. " * 160), encoding="utf-8")

            parent_chunks, child_chunks = DocumentChuncker().create_chunks_single(
                md_path,
                document_id="doc_a",
                source_name="same-name.md",
                user_id="user-a",
                visibility="private",
            )

        self.assertTrue(parent_chunks)
        self.assertTrue(child_chunks)
        parent_id, parent_doc = parent_chunks[0]
        self.assertEqual(parent_id, "doc_a_parent_0")
        self.assertEqual(parent_doc.metadata["parent_id"], "doc_a_parent_0")
        self.assertEqual(parent_doc.metadata["document_id"], "doc_a")
        self.assertEqual(parent_doc.metadata["source"], "same-name.md")
        self.assertEqual(parent_doc.metadata["source_name"], "same-name.md")
        self.assertEqual(parent_doc.metadata["user_id"], "user-a")
        self.assertEqual(parent_doc.metadata["visibility"], "private")
        self.assertEqual(child_chunks[0].metadata["parent_id"], "doc_a_parent_0")
        self.assertEqual(child_chunks[0].metadata["document_id"], "doc_a")

    def test_chunker_keeps_legacy_parent_ids_without_document_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "same-name.md"
            md_path.write_text("# Title\n\n" + ("legacy scoped text. " * 160), encoding="utf-8")

            parent_chunks, child_chunks = DocumentChuncker().create_chunks_single(md_path)

        self.assertTrue(parent_chunks)
        parent_id, parent_doc = parent_chunks[0]
        self.assertEqual(parent_id, "same-name_parent_0")
        self.assertEqual(parent_doc.metadata["parent_id"], "same-name_parent_0")
        self.assertEqual(parent_doc.metadata["source"], "same-name.pdf")
        self.assertNotIn("document_id", parent_doc.metadata)
        self.assertEqual(child_chunks[0].metadata["parent_id"], "same-name_parent_0")

    def test_parent_store_rejects_private_chunk_for_wrong_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ParentStoreManager(store_path=tmpdir)
            store.save(
                "doc_a_parent_0",
                "private content",
                {
                    "document_id": "doc_a",
                    "user_id": "user-a",
                    "visibility": "private",
                },
            )

            with self.assertRaises(PermissionError):
                store.load_content("doc_a_parent_0", user_id="user-b")

            allowed = store.load_content("doc_a_parent_0", user_id="user-a")

        self.assertEqual(allowed["content"], "private content")
        self.assertEqual(allowed["metadata"]["user_id"], "user-a")

    def test_parent_store_keeps_legacy_unscoped_reads_without_user_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ParentStoreManager(store_path=tmpdir)
            store.save(
                "doc_a_parent_0",
                "private content",
                {
                    "document_id": "doc_a",
                    "user_id": "user-a",
                    "visibility": "private",
                },
            )

            loaded = store.load_content("doc_a_parent_0")

        self.assertEqual(loaded["content"], "private content")

    def test_parent_store_deletes_only_requested_user_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ParentStoreManager(store_path=tmpdir)
            store.save(
                "doc_a_parent_0",
                "alice content",
                {
                    "document_id": "doc_a",
                    "user_id": "alice",
                    "visibility": "private",
                },
            )
            store.save(
                "doc_b_parent_0",
                "bob content",
                {
                    "document_id": "doc_b",
                    "user_id": "bob",
                    "visibility": "private",
                },
            )

            deleted_count = store.delete_by_document(
                document_id="doc_a",
                user_id="alice",
            )

            self.assertEqual(deleted_count, 1)
            with self.assertRaises(FileNotFoundError):
                store.load_content("doc_a_parent_0", user_id="alice")
            self.assertEqual(
                store.load_content("doc_b_parent_0", user_id="bob")["content"],
                "bob content",
            )

    def test_tenant_filter_matches_current_user_public_and_legacy(self):
        tenant_filter = build_tenant_filter("user-a", include_legacy_public=True)
        payload = tenant_filter.model_dump() if hasattr(tenant_filter, "model_dump") else tenant_filter.dict()

        self.assertEqual(
            payload["should"][0]["key"],
            "metadata.user_id",
        )
        self.assertEqual(payload["should"][0]["match"]["value"], "user-a")
        self.assertEqual(
            payload["should"][1]["key"],
            "metadata.visibility",
        )
        self.assertEqual(payload["should"][1]["match"]["value"], "public")
        self.assertEqual(
            payload["should"][2]["must"][0]["is_empty"]["key"],
            "metadata.user_id",
        )
        self.assertEqual(
            payload["should"][2]["must"][1]["is_empty"]["key"],
            "metadata.visibility",
        )

    def test_retriever_pipeline_only_passes_filter_when_user_id_is_supplied(self):
        collection = FakeCollection()
        pipeline = RetrieverPipeline(collection)

        pipeline.run("hello", user_id="user-a")
        pipeline.run("hello")

        self.assertIn("filter", collection.calls[0])
        payload = collection.calls[0]["filter"].model_dump()
        tenant_filter = payload["must"][0]
        self.assertEqual(tenant_filter["should"][0]["match"]["value"], "user-a")
        self.assertNotIn("filter", collection.calls[1])


if __name__ == "__main__":
    unittest.main()
