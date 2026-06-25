from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from backend.schemas import (
    MemoryItem,
    MemoryListResponse,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemorySearchRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from backend.dependencies import get_agent_memory_manager, get_user_manager
from backend.security import get_current_user

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    session_id: Optional[str] = Query(default=None),
    memory_manager=Depends(get_agent_memory_manager),
    current_user=Depends(get_current_user),
):
    """查询记忆列表，支持按会话过滤。"""
    try:
        memories = memory_manager.list_memories(
            user_id=str(current_user["id"]),
            session_id=session_id,
        )
        return MemoryListResponse(memories=[MemoryItem(**_adapt(m)) for m in memories])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query memories: {str(e)}")


@router.post("", response_model=MemoryItem)
async def create_memory(
    request: MemoryCreateRequest,
    memory_manager=Depends(get_agent_memory_manager),
    current_user=Depends(get_current_user),
):
    """手动创建一条新记忆。"""
    try:
        new_id = memory_manager.create_memory(
            content=request.content.strip(),
            source="manual",
            importance=request.importance,
            user_id=str(current_user["id"]),
            session_id=request.session_id,
        )
        memory = memory_manager.get_memory(new_id, user_id=str(current_user["id"]))
        if not memory:
            raise HTTPException(status_code=500, detail="Failed to retrieve created memory")
        return MemoryItem(**_adapt(memory))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create memory: {str(e)}")


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    user_manager=Depends(get_user_manager),
    current_user=Depends(get_current_user),
):
    """获取当前用户的用户画像配置。"""
    try:
        profile = user_manager.get_profile(int(current_user["id"]))
        return UserProfileResponse(
            preferred_language=profile.get("preferred_language"),
            response_style=profile.get("response_style"),
            custom_rules=profile.get("custom_rules") or [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load user profile: {str(e)}")


@router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(
    request: UserProfileUpdateRequest,
    user_manager=Depends(get_user_manager),
    current_user=Depends(get_current_user),
):
    """更新当前用户的用户画像配置。"""
    try:
        user_id = int(current_user["id"])
        updates = {}
        if request.preferred_language is not None:
            updates["preferred_language"] = request.preferred_language.strip()
        if request.response_style is not None:
            updates["response_style"] = request.response_style.strip()
        if request.custom_rules is not None:
            clean_rules = []
            for r in request.custom_rules:
                cleaned = r.strip()
                if cleaned and cleaned not in clean_rules:
                    clean_rules.append(cleaned)
            updates["custom_rules"] = clean_rules

        # 保存更新
        updated = user_manager.update_profile(user_id, updates)
        return UserProfileResponse(
            preferred_language=updated.get("preferred_language"),
            response_style=updated.get("response_style"),
            custom_rules=updated.get("custom_rules") or [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {str(e)}")


@router.get("/{memory_id}", response_model=MemoryItem)
async def get_memory(
    memory_id: int = Path(..., ge=1),
    memory_manager=Depends(get_agent_memory_manager),
    current_user=Depends(get_current_user),
):
    """获取单条记忆的详细信息。"""
    memory = memory_manager.get_memory(memory_id, user_id=str(current_user["id"]))
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryItem(**_adapt(memory))


@router.patch("/{memory_id}", response_model=MemoryItem)
async def update_memory(
    request: MemoryUpdateRequest,
    memory_id: int = Path(..., ge=1),
    memory_manager=Depends(get_agent_memory_manager),
    current_user=Depends(get_current_user),
):
    """更新一条记忆的属性值（支持修改内容和重要性）。"""
    user_id = str(current_user["id"])
    memory = memory_manager.get_memory(memory_id, user_id=user_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    update_data = {}
    if request.content is not None:
        update_data["content"] = request.content.strip()
    if request.importance is not None:
        update_data["importance"] = request.importance

    if not update_data:
        return MemoryItem(**_adapt(memory))

    try:
        memory_manager.update_memory(memory_id, **update_data)
        updated_memory = memory_manager.get_memory(memory_id, user_id=user_id)
        return MemoryItem(**_adapt(updated_memory))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update memory: {str(e)}")


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: int = Path(..., ge=1),
    memory_manager=Depends(get_agent_memory_manager),
    current_user=Depends(get_current_user),
):
    """物理删除一条记忆。"""
    user_id = str(current_user["id"])
    memory = memory_manager.get_memory(memory_id, user_id=user_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    try:
        memory_manager.delete_memory(memory_id, user_id=user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {str(e)}")


@router.post("/search", response_model=MemoryListResponse)
async def search_memories(
    request: MemorySearchRequest,
    memory_manager=Depends(get_agent_memory_manager),
    current_user=Depends(get_current_user),
):
    """基于词面匹配在事实记忆库中检索记忆。"""
    try:
        results = memory_manager.search_memories(
            query=request.query,
            user_id=str(current_user["id"]),
            session_id=request.session_id,
            limit=request.limit,
            require_match=bool(request.query.strip()),
        )
        return MemoryListResponse(memories=[MemoryItem(**_adapt(m)) for m in results])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")


def _adapt(memory: dict) -> dict:
    """将简化后的 AgentMemoryManager 返回字段适配为 MemoryItem schema。"""
    return {
        "id": memory.get("id"),
        "content": memory.get("content", ""),
        "source": memory.get("source", "qa_interaction"),
        "importance": memory.get("importance", 0.5),
        "session_id": memory.get("session_id"),
        "created_at": memory.get("created_at", ""),
        "updated_at": memory.get("updated_at", ""),
        "last_used_at": memory.get("last_used_at"),
        "hit_count": memory.get("hit_count", 0),
    }
