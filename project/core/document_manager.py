from pathlib import Path
import shutil
import uuid
import config
from db.document_metadata_manager import DocumentMetadataManager
from document_identity import PUBLIC_USER_ID, normalize_user_id, normalize_visibility
from utils import clear_directory_contents, pdf_to_markdown

MAX_UPLOAD_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_PRIVATE_DOCUMENTS_PER_USER = 10
MAX_PRIVATE_DOCUMENT_BYTES_PER_USER = 30 * 1024 * 1024


class DocumentQuotaExceeded(ValueError):
    pass


class DocumentPermissionError(PermissionError):
    pass


class DocumentManager:
    def __init__(self, rag_system):
        self.rag_system = rag_system
        self.markdown_dir = Path(config.MARKDOWN_DIR)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_manager = DocumentMetadataManager()
        
    def add_documents(
        self,
        document_paths,
        progress_callback=None,
        *,
        user_id: str | None = None,
        visibility: str = "private",
        role: str = "user",
        category: str | None = None,
    ):
        if not document_paths:
            return 0, 0
            
        document_paths = [document_paths] if isinstance(document_paths, str) else document_paths
        document_paths = [p for p in document_paths if p and Path(p).suffix.lower() in [".pdf", ".md"]]
        
        if not document_paths:
            return 0, 0
            
        normalized_user_id = normalize_user_id(user_id)
        normalized_visibility = normalize_visibility(visibility, user_id=normalized_user_id)
        if normalized_visibility == "public":
            if role != "admin" and normalized_user_id != PUBLIC_USER_ID:
                raise DocumentPermissionError("Only admins can upload public documents")
            normalized_user_id = PUBLIC_USER_ID
        else:
            if normalized_user_id == PUBLIC_USER_ID:
                raise DocumentPermissionError("Private documents require an authenticated user")
            self.validate_private_quota(
                normalized_user_id,
                incoming_count=len(document_paths),
                incoming_bytes=sum(self._file_size(path) for path in document_paths),
            )

        added = 0
        skipped = 0
            
        for i, doc_path in enumerate(document_paths):
            if progress_callback:
                progress_callback((i + 1) / len(document_paths), f"Processing {Path(doc_path).name}")
                
            document_id = uuid.uuid4().hex
            source_name = Path(doc_path).name
            md_path = self._markdown_path(
                document_id=document_id,
                user_id=normalized_user_id,
                visibility=normalized_visibility,
            )
            file_type = Path(doc_path).suffix.lower().replace(".", "")
            original_size_bytes = self._file_size(doc_path)
                
            try:            
                if Path(doc_path).suffix.lower() == ".md":
                    md_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(doc_path, md_path)
                else:
                    md_path.parent.mkdir(parents=True, exist_ok=True)
                    pdf_to_markdown(doc_path, md_path.parent)
                    converted_path = md_path.parent / f"{Path(doc_path).stem}.md"
                    if converted_path != md_path and converted_path.exists():
                        converted_path.replace(md_path)

                parent_chunks, child_chunks = self.rag_system.chunker.create_chunks_single(
                    md_path,
                    document_id=document_id,
                    source_name=source_name,
                    user_id=normalized_user_id,
                    visibility=normalized_visibility,
                    category=category,
                )
                
                if not child_chunks:
                    self._save_document_metadata(
                        md_path=md_path,
                        document_id=document_id,
                        original_name=Path(doc_path).name,
                        file_type=file_type,
                        status="failed",
                        parent_chunk_count=len(parent_chunks),
                        child_chunk_count=0,
                        error_message="No child chunks generated",
                        user_id=normalized_user_id,
                        visibility=normalized_visibility,
                        category=category,
                        original_size_bytes=original_size_bytes,
                    )
                    skipped += 1
                    continue
                
                collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
                for start in range(0, len(child_chunks), config.EMBEDDING_BATCH_SIZE):
                    batch = child_chunks[start:start + config.EMBEDDING_BATCH_SIZE]
                    collection.add_documents(batch)
                self.rag_system.parent_store.save_many(parent_chunks)
                self._save_document_metadata(
                    md_path=md_path,
                    document_id=document_id,
                    original_name=Path(doc_path).name,
                    file_type=file_type,
                    status="indexed",
                    parent_chunk_count=len(parent_chunks),
                    child_chunk_count=len(child_chunks),
                    error_message=None,
                    user_id=normalized_user_id,
                    visibility=normalized_visibility,
                    category=category,
                    original_size_bytes=original_size_bytes,
                )
                
                added += 1
                
            except Exception as e:
                print(f"Error processing {doc_path}: {e}")
                self._save_document_metadata(
                    md_path=md_path,
                    document_id=document_id,
                    original_name=Path(doc_path).name,
                    file_type=file_type or "md",
                    status="failed",
                    parent_chunk_count=0,
                    child_chunk_count=0,
                    error_message=str(e),
                    user_id=normalized_user_id,
                    visibility=normalized_visibility,
                    original_size_bytes=original_size_bytes if "original_size_bytes" in locals() else 0,
                )
                skipped += 1
            
        return added, skipped
    
    def get_markdown_files(self):
        if not self.markdown_dir.exists():
            return []
        return sorted([p.name for p in self.markdown_dir.glob("*.md")])

    def get_documents(self, user_id: str | None = None):
        self.metadata_manager.sync_from_markdown_files(
            self.markdown_dir,
            collection_name=self.rag_system.collection_name,
        )
        if user_id is not None:
            return self.metadata_manager.get_documents_for_user(user_id)
        return self.metadata_manager.get_all_documents()
    
    def clear_all(self):
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        clear_directory_contents(self.markdown_dir)
        
        self.rag_system.parent_store.clear_store()
        self.rag_system.vector_db.delete_collection(self.rag_system.collection_name)
        self.rag_system.vector_db.create_collection(self.rag_system.collection_name)
        self.metadata_manager.clear_all()

    def delete_document(self, *, user_id: str, role: str, document_id: str) -> bool:
        doc = self.metadata_manager.get_document_by_id(document_id)
        if doc is None:
            return False

        normalized_user_id = normalize_user_id(user_id)
        visibility = normalize_visibility(doc.get("visibility"), user_id=doc.get("user_id"))
        owner_user_id = normalize_user_id(doc.get("user_id"))
        if visibility == "public":
            if role != "admin":
                raise DocumentPermissionError("Only admins can delete public documents")
            vector_user_id = PUBLIC_USER_ID
        else:
            if owner_user_id != normalized_user_id:
                raise DocumentPermissionError("Cannot delete another user's document")
            vector_user_id = normalized_user_id

        self._delete_markdown_file(doc)
        self.rag_system.parent_store.delete_by_document(
            document_id=document_id,
            user_id=vector_user_id,
        )
        self.rag_system.vector_db.delete_document_vectors(
            self.rag_system.collection_name,
            document_id=document_id,
            user_id=vector_user_id,
        )
        self.metadata_manager.delete_document_by_id(document_id)
        return True

    def clear_user_documents(self, *, user_id: str) -> int:
        normalized_user_id = normalize_user_id(user_id)
        docs = self.metadata_manager.get_private_documents_for_user(normalized_user_id)
        for doc in docs:
            self._delete_markdown_file(doc)

        self.rag_system.parent_store.clear_by_user(normalized_user_id)
        self.rag_system.vector_db.delete_private_vectors_for_user(
            self.rag_system.collection_name,
            user_id=normalized_user_id,
        )
        return self.metadata_manager.delete_private_documents_for_user(normalized_user_id)

    def validate_private_quota(self, user_id: str, *, incoming_count: int, incoming_bytes: int) -> None:
        normalized_user_id = normalize_user_id(user_id)
        usage = self.metadata_manager.get_private_usage(normalized_user_id)
        if usage["doc_count"] + int(incoming_count or 0) > MAX_PRIVATE_DOCUMENTS_PER_USER:
            raise DocumentQuotaExceeded(
                f"Private document quota exceeded: max {MAX_PRIVATE_DOCUMENTS_PER_USER} documents"
            )
        if usage["total_bytes"] + int(incoming_bytes or 0) > MAX_PRIVATE_DOCUMENT_BYTES_PER_USER:
            raise DocumentQuotaExceeded(
                f"Private document quota exceeded: max {MAX_PRIVATE_DOCUMENT_BYTES_PER_USER} bytes"
            )

    def _ensure_existing_metadata(self, md_path: Path):
        if self.metadata_manager.get_document(md_path.name):
            return

        self._save_document_metadata(
            md_path=md_path,
            document_id=md_path.name,
            original_name=md_path.name,
            file_type="md",
            status="legacy",
            parent_chunk_count=0,
            child_chunk_count=0,
            error_message=None,
        )

    def _save_document_metadata(
        self,
        *,
        md_path: Path,
        document_id: str,
        original_name: str,
        file_type: str,
        status: str,
        parent_chunk_count: int,
        child_chunk_count: int,
        error_message: str | None,
        user_id: str | None = None,
        visibility: str | None = None,
        category: str | None = None,
        original_size_bytes: int = 0,
    ):
        normalized_user_id = normalize_user_id(user_id)
        normalized_visibility = normalize_visibility(visibility, user_id=normalized_user_id)
        self.metadata_manager.upsert_document(
            {
                "name": self._metadata_name(md_path),
                "document_id": document_id,
                "user_id": normalized_user_id,
                "visibility": normalized_visibility,
                "category": category,
                "original_name": original_name,
                "file_type": file_type,
                "status": status,
                "original_size_bytes": original_size_bytes,
                "parent_chunk_count": parent_chunk_count,
                "child_chunk_count": child_chunk_count,
                "embedding_provider": config.EMBEDDING_PROVIDER,
                "dense_model": config.DENSE_MODEL,
                "sparse_model": config.SPARSE_MODEL,
                "child_chunk_size": config.CHILD_CHUNK_SIZE,
                "child_chunk_overlap": config.CHILD_CHUNK_OVERLAP,
                "min_parent_size": config.MIN_PARENT_SIZE,
                "max_parent_size": config.MAX_PARENT_SIZE,
                "collection_name": self.rag_system.collection_name,
                "error_message": error_message,
            }
        )

    def _markdown_path(self, *, document_id: str, user_id: str, visibility: str) -> Path:
        if visibility == "public":
            return self.markdown_dir / "public" / f"{document_id}.md"
        return self.markdown_dir / "private" / user_id / f"{document_id}.md"

    def _metadata_name(self, md_path: Path) -> str:
        try:
            return md_path.relative_to(self.markdown_dir).as_posix()
        except ValueError:
            return md_path.name

    def _delete_markdown_file(self, doc: dict) -> None:
        name = doc.get("name") or ""
        candidates = [
            self.markdown_dir / name,
            self.markdown_dir / Path(name).name,
        ]
        for path in candidates:
            if path.exists() and path.is_file():
                path.unlink()
                self._remove_empty_parent_dirs(path.parent)
                return

    def _remove_empty_parent_dirs(self, start: Path) -> None:
        current = start
        while current != self.markdown_dir and self.markdown_dir in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    @staticmethod
    def _file_size(path) -> int:
        path = Path(path)
        return path.stat().st_size if path.exists() else 0
