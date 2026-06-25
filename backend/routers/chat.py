import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from backend.schemas import (
    ChatRequest,
    ChatResetRequest,
    ChatResetResponse,
    ChatSessionDeleteResponse,
    ChatSessionItem,
    ChatSessionListResponse,
    ChatSessionRenameRequest,
    QARecordDetail,
    QARecordListResponse,
)
from backend.dependencies import get_agent_memory_manager, get_chat_service, get_qa_record_manager
from backend.security import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def ask_question(
    request: ChatRequest,
    chat_svc = Depends(get_chat_service),
    current_user = Depends(get_current_user),
):
    """RAG 问答入口，返回前端消费的 SSE 流。"""
    session_id = request.session_id.strip() if request.session_id else str(uuid.uuid4())
    generator = chat_svc.ask_stream(request.message, session_id=session_id, user_id=str(current_user["id"]))
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/reset", response_model=ChatResetResponse)
async def reset_session(
    request: ChatResetRequest,
    chat_svc = Depends(get_chat_service),
    current_user = Depends(get_current_user),
):
    session_id = request.session_id.strip() if request.session_id else "default_session"
    await chat_svc.reset(session_id, user_id=str(current_user["id"]))
    return ChatResetResponse(success=True)


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    qa_record_manager = Depends(get_qa_record_manager),
    current_user = Depends(get_current_user),
):
    return ChatSessionListResponse(sessions=qa_record_manager.get_sessions(limit=limit, user_id=str(current_user["id"])))


@router.patch("/sessions/{session_id}", response_model=ChatSessionItem)
async def rename_session(
    request: ChatSessionRenameRequest,
    session_id: str = Path(..., min_length=1),
    qa_record_manager = Depends(get_qa_record_manager),
    current_user = Depends(get_current_user),
):
    sid = session_id.strip()
    user_id = str(current_user["id"])
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Session title cannot be empty")

    try:
        renamed = qa_record_manager.rename_session(sid, title, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not renamed:
        raise HTTPException(status_code=404, detail="Chat session not found")

    for session in qa_record_manager.get_sessions(limit=100, user_id=user_id):
        if session["session_id"] == sid:
            return ChatSessionItem(**session)

    raise HTTPException(status_code=404, detail="Chat session not found")


@router.delete("/sessions/{session_id}", response_model=ChatSessionDeleteResponse)
async def delete_session(
    session_id: str = Path(..., min_length=1),
    chat_svc = Depends(get_chat_service),
    qa_record_manager = Depends(get_qa_record_manager),
    agent_memory_manager = Depends(get_agent_memory_manager),
    current_user = Depends(get_current_user),
):
    sid = session_id.strip()
    user_id = str(current_user["id"])
    deleted_records = qa_record_manager.count_records_by_session(sid, user_id=user_id)
    await chat_svc.reset(sid, user_id=user_id)
    qa_record_manager.delete_session(sid, user_id=user_id)
    deleted_memories = agent_memory_manager.delete_by_session(sid, user_id=user_id)
    return ChatSessionDeleteResponse(
        success=True,
        session_id=sid,
        deleted_records=deleted_records,
        deleted_memories=deleted_memories,
    )


@router.get("/records", response_model=QARecordListResponse)
async def list_records(
    limit: int = Query(default=20, ge=1, le=100),
    session_id: Optional[str] = Query(default=None),
    qa_record_manager = Depends(get_qa_record_manager),
    current_user = Depends(get_current_user),
):
    sid = session_id.strip() if session_id else None
    return QARecordListResponse(records=qa_record_manager.list_recent(limit=limit, session_id=sid, user_id=str(current_user["id"])))


@router.get("/records/{record_id}", response_model=QARecordDetail)
async def get_record_detail(
    record_id: int = Path(..., ge=1),
    qa_record_manager = Depends(get_qa_record_manager),
    current_user = Depends(get_current_user),
):
    record = qa_record_manager.get_record(record_id=record_id, user_id=str(current_user["id"]))
    if record is None:
        raise HTTPException(status_code=404, detail="QA record not found")

    return QARecordDetail(**record)
