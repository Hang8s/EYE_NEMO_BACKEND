from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Attachment, BusinessConnection, Chat, Message

router = APIRouter(prefix="/mini-api", tags=["mini-app"])


@dataclass(frozen=True)
class MiniUser:
    telegram_user_id: int


def _init_user(init_data: str, token: str, max_age: int) -> MiniUser:
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", "")
    auth_date = fields.get("auth_date")
    if not received_hash or not auth_date:
        raise HTTPException(401, "Invalid Mini App authentication")
    try:
        if abs(time.time() - int(auth_date)) > max_age:
            raise ValueError
        user = json.loads(fields["user"])
        user_id = int(user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(401, "Invalid Mini App authentication") from error
    data_check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(401, "Invalid Mini App authentication")
    return MiniUser(user_id)


async def current_user(
    request: Request, x_telegram_init_data: str | None = Header(default=None),
) -> MiniUser:
    if not x_telegram_init_data:
        raise HTTPException(401, "Missing Telegram Mini App authentication")
    settings = request.app.state.settings
    return _init_user(
        x_telegram_init_data,
        settings.telegram_bot_token.get_secret_value(),
        settings.mini_app_auth_max_age_seconds,
    )


async def owned_connection_ids(db: AsyncSession, user: MiniUser) -> list[uuid.UUID]:
    return list(
        (await db.scalars(
            select(BusinessConnection.id).where(
                BusinessConnection.telegram_user_id == user.telegram_user_id,
                BusinessConnection.is_enabled.is_(True),
            )
        )).all()
    )


def message_data(row: Message) -> dict[str, object]:
    return {
        "id": str(row.id), "telegram_message_id": row.telegram_message_id,
        "chat_id": str(row.chat_id), "text": row.text, "caption": row.caption,
        "message_type": row.message_type, "sent_at": row.sent_at,
        "edited_at": row.edited_at, "is_deleted": row.is_deleted,
        "deleted_at": row.deleted_at,
        "reply_to_telegram_message_id": row.reply_to_telegram_message_id,
    }


@router.get("/chats")
async def chats(request: Request, user: MiniUser = Depends(current_user)) -> dict[str, object]:
    async with request.app.state.sessions() as db:
        connections = await owned_connection_ids(db, user)
        if not connections:
            return {"items": []}
        rows = (await db.scalars(select(Chat).where(Chat.business_connection_id.in_(connections)).order_by(Chat.updated_at.desc()))).all()
        return {"items": [{"id": str(row.id), "title": row.title or row.first_name or row.username or str(row.telegram_chat_id), "chat_type": row.chat_type, "updated_at": row.updated_at} for row in rows]}


@router.get("/chats/{chat_id}/messages")
async def chat_messages(request: Request, chat_id: uuid.UUID, before: str | None = None, limit: int = Query(50, ge=1, le=100), user: MiniUser = Depends(current_user)) -> dict[str, object]:
    async with request.app.state.sessions() as db:
        connections = await owned_connection_ids(db, user)
        chat = await db.scalar(select(Chat).where(Chat.id == chat_id, Chat.business_connection_id.in_(connections)))
        if not chat:
            raise HTTPException(404, "Chat not found")
        statement = select(Message).where(Message.chat_id == chat.id).order_by(Message.sent_at.desc()).limit(limit + 1)
        if before:
            from datetime import datetime
            statement = statement.where(Message.sent_at < datetime.fromisoformat(before))
        rows = list((await db.scalars(statement)).all())
        next_cursor = rows[-1].sent_at.isoformat() if len(rows) > limit else None
        output = rows[:limit]
        attachments = (await db.scalars(select(Attachment).where(Attachment.message_id.in_([row.id for row in output])))).all() if output else []
        by_message: dict[uuid.UUID, list[dict[str, object]]] = {}
        for item in attachments:
            by_message.setdefault(item.message_id, []).append({"id": str(item.id), "type": item.type, "file_name": item.file_name, "mime_type": item.mime_type, "file_size": item.file_size, "available": bool(item.local_path)})
        return {"items": [{**message_data(row), "attachments": by_message.get(row.id, [])} for row in output], "next_cursor": next_cursor}


@router.get("/search")
async def search(request: Request, q: str, limit: int = Query(50, ge=1, le=100), user: MiniUser = Depends(current_user)) -> dict[str, object]:
    async with request.app.state.sessions() as db:
        connections = await owned_connection_ids(db, user)
        if not connections:
            return {"items": []}
        pattern = f"%{q}%"
        rows = (await db.scalars(select(Message).join(Chat).where(Chat.business_connection_id.in_(connections), or_(Message.text.ilike(pattern), Message.caption.ilike(pattern))).order_by(Message.sent_at.desc()).limit(limit))).all()
        return {"items": [message_data(row) for row in rows]}


@router.get("/media/{attachment_id}")
async def media(request: Request, attachment_id: uuid.UUID, user: MiniUser = Depends(current_user)) -> FileResponse:
    async with request.app.state.sessions() as db:
        connections = await owned_connection_ids(db, user)
        attachment = await db.scalar(select(Attachment).join(Message).join(Chat).where(Attachment.id == attachment_id, Chat.business_connection_id.in_(connections)))
        if not attachment or not attachment.local_path:
            raise HTTPException(404, "Media not found")
        root = Path(request.app.state.settings.media_path).resolve()
        path = Path(attachment.local_path).resolve()
        if root not in path.parents or not path.is_file():
            raise HTTPException(404, "Media not found")
        return FileResponse(path, media_type=attachment.mime_type, filename=attachment.file_name)
