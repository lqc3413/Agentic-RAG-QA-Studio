import sys
import tempfile
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

from backend.dependencies import get_document_manager
from backend.routers.documents import router as documents_router
from backend.security import get_current_user
from core.document_manager import DocumentManager, DocumentQuotaExceeded
from db.document_metadata_manager import DocumentMetadataManager


class FakeChunker:
    def create_chunks_single(self, md_path, *, document_id=None, source_name=None, user_id=None, visibility=None, category=None):
        from langchain_core.documents import Document

        parent = Document(
            page_content=Path(md_path).read_text(encoding="utf-8"),
            metadata={
                "document_id": document_id,
                "source": source_name,
                "source_name": source_name,
                "parent_id": f"{document_id}_parent_0",
                "user_id": user_id,
                "visibility": visibility,
            },
        )
        child = Document(
            page_content=parent.page_content,
            metadata=dict(parent.metadata),
        )
        return [(f"{document_id}_parent_0", parent)], [child]


class FakeCollection:
    def __init__(self):
        self.documents = []

    def add_documents(self, docs):
        self.documents.extend(docs)


class FakeVectorDb:
    def __init__(self):
        self.collection = FakeCollection()
        self.deleted = []

    def get_collection(self, collection_name):
        return self.collection

    def delete_document_vectors(self, collection_name, *, document_id, user_id):
        self.deleted.append(("document", collection_name, document_id, user_id))

    def delete_private_vectors_for_user(self, collection_name, *, user_id):
        self.deleted.append(("user", collection_name, user_id))


class FakeParentStore:
    def __init__(self):
        self.parents = []
        self.deleted = []

    def save_many(self, parents):
        self.parents.extend(parents)

    def delete_by_document(self, *, document_id, user_id=None):
        self.deleted.append(("document", document_id, user_id))
        return 1

    def clear_by_user(self, user_id):
        self.deleted.append(("user", user_id))
        return 1


class FakeRagSystem:
    def __init__(self):
        self.collection_name = "test_collection"
        self.chunker = FakeChunker()
        self.vector_db = FakeVectorDb()
        self.parent_store = FakeParentStore()


class FakeDocumentManager:
    def __init__(self):
        self.documents = [
            {
                "name": "private/alice/doc-alice.md",
                "document_id": "doc-alice",
                "user_id": "alice",
                "visibility": "private",
                "original_name": "alice-notes.md",
                "type": "md",
                "status": "indexed",
            },
            {
                "name": "public/doc-public.md",
                "document_id": "doc-public",
                "user_id": "public",
                "visibility": "public",
                "original_name": "public-guide.md",
                "type": "md",
                "status": "indexed",
            },
        ]
        self.calls = []

    def get_documents(self, user_id=None):
        self.calls.append(("get_documents", user_id))
        return self.documents

    def add_documents(self, paths, *, user_id=None, visibility="private", role="user", category=None, progress_callback=None):
        self.calls.append(("add_documents", list(paths), user_id, visibility, role))
        return 1, 0

    def validate_private_quota(self, user_id, *, incoming_count, incoming_bytes):
        self.calls.append(("validate_private_quota", user_id, incoming_count, incoming_bytes))

    def delete_document(self, *, user_id, role, document_id):
        self.calls.append(("delete_document", user_id, role, document_id))
        return True

    def clear_user_documents(self, *, user_id):
        self.calls.append(("clear_user_documents", user_id))
        return 2

    def clear_all(self):
        self.calls.append(("clear_all",))


class QuotaFailingDocumentManager(FakeDocumentManager):
    def validate_private_quota(self, user_id, *, incoming_count, incoming_bytes):
        raise DocumentQuotaExceeded("Quota exceeded")


class TenantDocumentRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.manager = FakeDocumentManager()

        app = FastAPI()
        app.include_router(documents_router)
        app.dependency_overrides[get_document_manager] = lambda: self.manager
        app.dependency_overrides[get_current_user] = lambda: {
            "id": 1,
            "username": "alice",
            "role": "user",
        }
        self.client = TestClient(app)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_list_documents_uses_current_user_scope(self):
        response = self.client.get("/api/documents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["documents"][0]["document_id"], "doc-alice")
        self.assertEqual(response.json()["documents"][0]["original_name"], "alice-notes.md")
        self.assertIn(("get_documents", "1"), self.manager.calls)

    def test_upload_private_documents_uses_current_user_and_quota(self):
        response = self.client.post(
            "/api/documents",
            files={"files": ("notes.md", b"# Title\n\nhello", "text/markdown")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(call[0] == "validate_private_quota" and call[1] == "1" for call in self.manager.calls))
        self.assertTrue(any(call[0] == "add_documents" and call[2] == "1" and call[3] == "private" for call in self.manager.calls))

    def test_upload_rejects_files_larger_than_five_megabytes(self):
        oversized = b"x" * (5 * 1024 * 1024 + 1)

        response = self.client.post(
            "/api/documents",
            files={"files": ("large.md", oversized, "text/markdown")},
        )

        self.assertEqual(response.status_code, 413)
        self.assertFalse(any(call[0] == "add_documents" for call in self.manager.calls))

    def test_upload_rejects_private_quota_overage(self):
        self.manager = QuotaFailingDocumentManager()

        response = self.client.post(
            "/api/documents",
            files={"files": ("notes.md", b"# Title\n\nhello", "text/markdown")},
        )

        self.assertEqual(response.status_code, 413)
        self.assertFalse(any(call[0] == "add_documents" for call in self.manager.calls))

    def test_delete_document_uses_current_user_scope(self):
        response = self.client.delete("/api/documents/doc-alice")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("delete_document", "1", "user", "doc-alice"), self.manager.calls)

    def test_clear_documents_clears_only_current_users_private_documents(self):
        response = self.client.delete("/api/documents")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("clear_user_documents", "1"), self.manager.calls)
        self.assertNotIn(("clear_all",), self.manager.calls)

    def test_admin_clear_uses_global_clear(self):
        app = FastAPI()
        app.include_router(documents_router)
        app.dependency_overrides[get_document_manager] = lambda: self.manager
        app.dependency_overrides[get_current_user] = lambda: {
            "id": 99,
            "username": "admin",
            "role": "admin",
        }
        admin_client = TestClient(app)

        response = admin_client.delete("/api/documents?scope=all")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("clear_all",), self.manager.calls)

    def test_admin_upload_public_document_skips_private_quota(self):
        app = FastAPI()
        app.include_router(documents_router)
        app.dependency_overrides[get_document_manager] = lambda: self.manager
        app.dependency_overrides[get_current_user] = lambda: {
            "id": 99,
            "username": "admin",
            "role": "admin",
        }
        admin_client = TestClient(app)

        response = admin_client.post(
            "/api/documents",
            data={"visibility": "public"},
            files={"files": ("guide.md", b"# Guide\n\nshared", "text/markdown")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(call[0] == "validate_private_quota" for call in self.manager.calls))
        self.assertTrue(any(call[0] == "add_documents" and call[3] == "public" for call in self.manager.calls))


class TenantDocumentManagerTests(unittest.TestCase):
    def setUp(self):
        from db.pg_pool import clear_all_tables
        clear_all_tables()
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp_path = Path(self.tmpdir.name)
        self.rag_system = FakeRagSystem()
        self.manager = DocumentManager(self.rag_system)
        self.manager.markdown_dir = self.tmp_path / "markdown_docs"
        self.manager.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.manager.metadata_manager = DocumentMetadataManager(
            db_path=str(self.tmp_path / "document_metadata.db")
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_same_filename_uploads_across_users_get_distinct_private_documents(self):
        alice_file = self.tmp_path / "alice" / "notes.md"
        bob_file = self.tmp_path / "bob" / "notes.md"
        alice_file.parent.mkdir()
        bob_file.parent.mkdir()
        alice_file.write_text("# Notes\n\nAlice private content", encoding="utf-8")
        bob_file.write_text("# Notes\n\nBob private content", encoding="utf-8")

        self.manager.add_documents([str(alice_file)], user_id="alice", visibility="private")
        self.manager.add_documents([str(bob_file)], user_id="bob", visibility="private")

        alice_docs = self.manager.get_documents(user_id="alice")
        bob_docs = self.manager.get_documents(user_id="bob")

        alice_private = [doc for doc in alice_docs if doc["visibility"] == "private"]
        bob_private = [doc for doc in bob_docs if doc["visibility"] == "private"]
        self.assertEqual(len(alice_private), 1)
        self.assertEqual(len(bob_private), 1)
        self.assertNotEqual(alice_private[0]["document_id"], bob_private[0]["document_id"])
        self.assertEqual(alice_private[0]["original_name"], "notes.md")
        self.assertEqual(bob_private[0]["original_name"], "notes.md")
        self.assertTrue((self.manager.markdown_dir / alice_private[0]["name"]).exists())
        self.assertTrue((self.manager.markdown_dir / bob_private[0]["name"]).exists())
        self.assertEqual({doc["document_id"] for doc in alice_docs}, {alice_private[0]["document_id"]})
        self.assertEqual({doc["document_id"] for doc in bob_docs}, {bob_private[0]["document_id"]})


if __name__ == "__main__":
    unittest.main()
