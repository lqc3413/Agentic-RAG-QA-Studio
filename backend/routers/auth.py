import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_user_manager
from backend.schemas import (
    AuthTokenResponse,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    UserResponse,
)
from backend.security import create_access_token, get_current_user, hash_password, verify_password


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, user_manager=Depends(get_user_manager)):
    try:
        user = user_manager.create_user(
            username=request.username,
            password_hash=hash_password(request.password),
            role="user",
        )
    except Exception as exc:
        import psycopg
        if isinstance(exc, (sqlite3.IntegrityError, psycopg.IntegrityError)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from exc
        raise exc

    return AuthTokenResponse(
        access_token=create_access_token(user),
        user=UserResponse(**user),
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(request: LoginRequest, user_manager=Depends(get_user_manager)):
    user = user_manager.get_by_username(request.username)
    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    return AuthTokenResponse(
        access_token=create_access_token(user),
        user=UserResponse(**user),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return UserResponse(**current_user)


@router.post("/logout", response_model=LogoutResponse)
async def logout():
    return LogoutResponse(success=True)
