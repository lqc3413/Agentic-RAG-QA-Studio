from typing import List
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from backend.dependencies import get_document_manager
from backend.schemas import (
    DocumentClearResponse,
    DocumentItem,
    DocumentListResponse,
    DocumentUploadResponse,
)
from backend.security import get_current_user
from core.document_manager import (
    MAX_UPLOAD_FILE_SIZE_BYTES,
    DocumentPermissionError,
    DocumentQuotaExceeded,
)


router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    doc_manager=Depends(get_document_manager),
    current_user=Depends(get_current_user),
):
    documents = [
        DocumentItem(**doc)
        for doc in doc_manager.get_documents(user_id=str(current_user["id"]))
    ]
    return DocumentListResponse(documents=documents)


@router.post("", response_model=DocumentUploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    visibility: str = Form(default="private"),
    category: str = Form(default="general"),
    doc_manager=Depends(get_document_manager),
    current_user=Depends(get_current_user),
):
    if not files:
        return DocumentUploadResponse(added=0, skipped=0, documents=[])

    normalized_visibility = (visibility or "private").strip().lower()
    if normalized_visibility not in {"private", "public"}:
        raise HTTPException(status_code=400, detail="visibility must be 'private' or 'public'")
    if normalized_visibility == "public" and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can upload public documents")

    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Empty filename uploaded")
        suffix = Path(file.filename).suffix.lower()
        if suffix not in (".pdf", ".md"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: '{suffix}'. Only .pdf and .md files are supported.",
            )

    temp_dir = Path(__file__).resolve().parent.parent / "temp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_paths: list[str] = []
    total_upload_bytes = 0
    try:
        for file in files:
            file_uuid_dir = temp_dir / str(uuid.uuid4())
            file_uuid_dir.mkdir(parents=True, exist_ok=True)
            temp_file_path = file_uuid_dir / file.filename

            with open(temp_file_path, "wb") as buffer:
                total_upload_bytes += _copy_upload_file_with_limit(file, buffer)

            temp_paths.append(str(temp_file_path))

        if normalized_visibility == "private" and current_user.get("role") != "admin":
            doc_manager.validate_private_quota(
                str(current_user["id"]),
                incoming_count=len(temp_paths),
                incoming_bytes=total_upload_bytes,
            )

        added, skipped = doc_manager.add_documents(
            temp_paths,
            user_id=str(current_user["id"]),
            visibility=normalized_visibility,
            role=current_user.get("role", "user"),
            category=category.strip().lower(),
        )

        documents = [
            DocumentItem(**doc)
            for doc in doc_manager.get_documents(user_id=str(current_user["id"]))
        ]

        return DocumentUploadResponse(
            added=added,
            skipped=skipped,
            documents=documents,
        )

    except DocumentQuotaExceeded as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except DocumentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred while processing documents: {str(exc)}",
        ) from exc

    finally:
        for path_str in temp_paths:
            path = Path(path_str)
            try:
                if path.exists():
                    path.unlink()
                if path.parent.exists() and path.parent != temp_dir:
                    path.parent.rmdir()
            except Exception as cleanup_err:
                print(f"Error cleaning up temp upload file {path_str}: {cleanup_err}")

        try:
            if temp_dir.exists() and not any(temp_dir.iterdir()):
                temp_dir.rmdir()
        except Exception:
            pass


@router.delete("", response_model=DocumentClearResponse)
async def clear_documents(
    scope: str = Query(default="mine", pattern="^(mine|all)$"),
    doc_manager=Depends(get_document_manager),
    current_user=Depends(get_current_user),
):
    try:
        if scope == "all":
            if current_user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Only admins can clear the global knowledge base")
            doc_manager.clear_all()
        else:
            doc_manager.clear_user_documents(user_id=str(current_user["id"]))

        documents = [
            DocumentItem(**doc)
            for doc in doc_manager.get_documents(user_id=str(current_user["id"]))
        ]
        return DocumentClearResponse(success=True, documents=documents)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear knowledge base: {str(exc)}",
        ) from exc


@router.delete("/{document_id}", response_model=DocumentClearResponse)
async def delete_document(
    document_id: str,
    doc_manager=Depends(get_document_manager),
    current_user=Depends(get_current_user),
):
    try:
        deleted = doc_manager.delete_document(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "user"),
            document_id=document_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Document not found")

        documents = [
            DocumentItem(**doc)
            for doc in doc_manager.get_documents(user_id=str(current_user["id"]))
        ]
        return DocumentClearResponse(success=True, documents=documents)
    except DocumentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(exc)}") from exc


def _copy_upload_file_with_limit(file: UploadFile, buffer) -> int:
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' exceeds the 5 MB upload limit",
            )
        buffer.write(chunk)
    return total
