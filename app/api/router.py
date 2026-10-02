from __future__ import annotations
import hmac
import uuid
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.config import Settings
from app.db.models import Attachment, Chat, Message

router = APIRouter(prefix="/api")
def session_factory(request: Request) -> async_sessionmaker[AsyncSession]: return request.app.state.sessions
def settings(request: Request) -> Settings: return request.app.state.settings
async def protected(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    value = authorization.removeprefix("Bearer ") if authorization else ""
    if not hmac.compare_digest(value, settings(request).archive_api_key.get_secret_value()): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})
def message_data(row: Message) -> dict[str, object]:
    return {"id": str(row.id), "telegram_message_id": row.telegram_message_id, "chat_id": str(row.chat_id), "sender_user_id": str(row.sender_user_id) if row.sender_user_id else None, "text": row.text, "caption": row.caption, "message_type": row.message_type, "sent_at": row.sent_at, "edited_at": row.edited_at, "is_deleted": row.is_deleted, "deleted_at": row.deleted_at, "reply_to_telegram_message_id": row.reply_to_telegram_message_id, "reply_to_message_id": str(row.reply_to_message_id) if row.reply_to_message_id else None}
@router.get("/chats", dependencies=[Depends(protected)])
async def chats(request: Request, limit: int = Query(50, ge=1, le=100), cursor: str | None = None) -> dict[str, object]:
    async with session_factory(request)() as db:
        statement = select(Chat).order_by(Chat.updated_at.desc(), Chat.id).limit(limit + 1)
        if cursor: statement = statement.where(Chat.id < uuid.UUID(cursor))
        rows = list((await db.scalars(statement)).all()); next_cursor = str(rows[-1].id) if len(rows) > limit else None
        return {"items": [{"id": str(x.id), "telegram_chat_id": x.telegram_chat_id, "type": x.chat_type, "title": x.title, "username": x.username} for x in rows[:limit]], "next_cursor": next_cursor}
@router.get("/chats/{chat_id}", dependencies=[Depends(protected)])
async def chat(request: Request, chat_id: uuid.UUID) -> dict[str, object]:
    async with session_factory(request)() as db:
        row = await db.get(Chat, chat_id)
        if not row: raise HTTPException(404, "Chat not found")
        return {"id": str(row.id), "telegram_chat_id": row.telegram_chat_id, "type": row.chat_type, "title": row.title, "username": row.username}
@router.get("/chats/{chat_id}/messages", dependencies=[Depends(protected)])
async def chat_messages(request: Request, chat_id: uuid.UUID, limit: int = Query(50, ge=1, le=100), before: datetime | None = None, after: datetime | None = None, sender_id: uuid.UUID | None = None, include_deleted: bool = False) -> dict[str, object]:
    async with session_factory(request)() as db:
        statement = select(Message).where(Message.chat_id == chat_id).order_by(Message.sent_at.desc()).limit(limit)
        if before: statement = statement.where(Message.sent_at < before)
        if after: statement = statement.where(Message.sent_at > after)
        if sender_id: statement = statement.where(Message.sender_user_id == sender_id)
        if not include_deleted: statement = statement.where(Message.is_deleted.is_(False))
        return {"items": [message_data(row) for row in (await db.scalars(statement)).all()]}
@router.get("/messages/{message_id}", dependencies=[Depends(protected)])
async def message(request: Request, message_id: uuid.UUID) -> dict[str, object]:
    async with session_factory(request)() as db:
        row = await db.get(Message, message_id)
        if not row: raise HTTPException(404, "Message not found")
        data = message_data(row); attachments = (await db.scalars(select(Attachment).where(Attachment.message_id == row.id))).all(); data["attachments"] = [{"id": str(x.id), "type": x.type, "file_name": x.file_name, "mime_type": x.mime_type, "file_size": x.file_size, "local_path": x.local_path} for x in attachments]; return data
@router.get("/search", dependencies=[Depends(protected)])
async def search(request: Request, q: str, chat_id: uuid.UUID | None = None, sender_id: uuid.UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None, include_deleted: bool = False, limit: int = Query(50, ge=1, le=100)) -> dict[str, object]:
    async with session_factory(request)() as db:
        pattern = f"%{q}%"; statement = select(Message).where(or_(Message.text.ilike(pattern), Message.caption.ilike(pattern))).order_by(Message.sent_at.desc()).limit(limit)
        if chat_id: statement = statement.where(Message.chat_id == chat_id)
        if sender_id: statement = statement.where(Message.sender_user_id == sender_id)
        if date_from: statement = statement.where(Message.sent_at >= date_from)
        if date_to: statement = statement.where(Message.sent_at <= date_to)
        if not include_deleted: statement = statement.where(Message.is_deleted.is_(False))
        return {"items": [message_data(row) for row in (await db.scalars(statement)).all()]}
@router.get("/stats", dependencies=[Depends(protected)])
async def stats(request: Request) -> dict[str, int]:
    from datetime import UTC, timedelta
    async with session_factory(request)() as db:
        now = datetime.now(UTC)
        async def count(statement: Any) -> int: return int((await db.scalar(statement)) or 0)
        return {"total_chats": await count(select(func.count()).select_from(Chat)), "total_stored_messages": await count(select(func.count()).select_from(Message)), "total_deleted_messages": await count(select(func.count()).select_from(Message).where(Message.is_deleted.is_(True))), "total_edited_messages": await count(select(func.count()).select_from(Message).where(Message.edited_at.is_not(None))), "total_media_attachments": await count(select(func.count()).select_from(Attachment)), "messages_last_24_hours": await count(select(func.count()).select_from(Message).where(Message.sent_at >= now - timedelta(hours=24))), "messages_last_7_days": await count(select(func.count()).select_from(Message).where(Message.sent_at >= now - timedelta(days=7)))}
