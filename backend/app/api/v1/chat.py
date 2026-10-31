import uuid
from typing import Any

from app.api.deps import get_current_user, get_db
from app.schemas.chat import (
    ChatMessageCreate,
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    ChatSessionUpdate,
)
from app.services.chat_service import chat_service
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Create a new orchestrator chat session scoped to the authenticated user."""
    user_id = str(current_user["id"])
    return await chat_service.create_session(user_id=user_id, payload=payload, db=db)


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_chat_sessions(
    is_pinned: bool | None = None,
    is_archived: bool | None = False,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List chat sessions for the current user with pinning, archiving, and search filters."""
    user_id = str(current_user["id"])
    return await chat_service.list_sessions(
        user_id=user_id,
        db=db,
        is_pinned=is_pinned,
        is_archived=is_archived,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve chat session details and all historical messages."""
    user_id = str(current_user["id"])
    return await chat_service.get_session(session_id=session_id, user_id=user_id, db=db)


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: uuid.UUID,
    payload: ChatSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Update chat session title, pinned status, archive state, or project tag."""
    user_id = str(current_user["id"])
    return await chat_service.update_session(
        session_id=session_id,
        user_id=user_id,
        payload=payload,
        db=db,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Delete a chat session and all attached messages."""
    user_id = str(current_user["id"])
    await chat_service.delete_session(session_id=session_id, user_id=user_id, db=db)
    return None


@router.post("/sessions/{session_id}/messages")
async def send_chat_message(
    session_id: uuid.UUID,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Send user instruction to the orchestrator chat.

    Supports SSE streaming (`stream=true`) or synchronous execution (`stream=false`).
    """
    user_id = str(current_user["id"])
    if payload.stream:
        return StreamingResponse(
            chat_service.stream_chat_response(
                session_id=session_id,
                user_id=user_id,
                payload=payload,
                db=db,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "X-Accel-Buffering": "no",
            },
        )

    return await chat_service.submit_message(
        session_id=session_id,
        user_id=user_id,
        payload=payload,
        db=db,
    )
