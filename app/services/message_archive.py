from __future__ import annotations
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePath
from typing import Any
from aiogram import Bot
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message as TgMessage
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.db.models import Attachment, BusinessConnection as Connection, Chat, Message, MessageVersion, User
from app.config import Settings

def message_type(message: TgMessage) -> str:
    for name in ("photo", "video", "voice", "audio", "document", "animation", "sticker", "video_note", "location", "contact", "poll"):
        if getattr(message, name, None) is not None: return name
    return "text" if message.text is not None else "unknown"
def attachment_payload(message: TgMessage, kind: str) -> dict[str, Any] | None:
    item: Any = getattr(message, kind, None)
    if kind == "photo" and item: item = item[-1]
    if item is None or not hasattr(item, "file_id"): return None
    return {"telegram_file_id": item.file_id, "telegram_file_unique_id": item.file_unique_id, "type": kind, "file_name": getattr(item, "file_name", None), "mime_type": getattr(item, "mime_type", None), "file_size": getattr(item, "file_size", None)}

class ArchiveService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], settings: Settings | None = None) -> None:
        self.sessions = sessions
        self.settings = settings
    async def _download_attachment(self, bot: Bot, attachment: Attachment) -> None:
        if not self.settings or self.settings.media_storage == "none": return
        try:
            file = await bot.get_file(attachment.telegram_file_id)
            if not file.file_path: return
            if self.settings.media_storage == "local":
                root = self.settings.media_path.resolve()
                target = root / str(attachment.id)
                target.parent.mkdir(parents=True, exist_ok=True)
                await bot.download_file(file.file_path, destination=target)
                attachment.local_path = str(target)
                attachment.storage_key = str(attachment.id)
                return
            content = BytesIO()
            await bot.download_file(file.file_path, destination=content)
            from vercel.blob import AsyncBlobClient
            token = self.settings.blob_read_write_token
            if not token: return
            suffix = PurePath(attachment.file_name or file.file_path).suffix
            uploaded = await AsyncBlobClient().put(
                f"attachments/{attachment.id}{suffix}", content.getvalue(), access="private",
                content_type=attachment.mime_type, add_random_suffix=True,
                multipart=bool(attachment.file_size and attachment.file_size > 4 * 1024 * 1024),
                token=token.get_secret_value(),
            )
            attachment.storage_key = uploaded.url
        except Exception as error:
            import structlog
            structlog.get_logger().warning("telegram.media.download_failed", attachment_id=str(attachment.id), error=str(error))
    async def connection(self, event: BusinessConnection) -> None:
        async with self.sessions() as db, db.begin():
            row = await db.scalar(select(Connection).where(Connection.telegram_business_connection_id == event.id))
            now = event.date
            values = {"telegram_user_id": event.user.id, "username": event.user.username, "first_name": event.user.first_name, "last_name": event.user.last_name, "is_enabled": event.is_enabled, "connected_at": now if event.is_enabled else None, "disconnected_at": None if event.is_enabled else now}
            if row:
                for key, value in values.items(): setattr(row, key, value)
            else: db.add(Connection(telegram_business_connection_id=event.id, **values))
    async def _chat(self, db: AsyncSession, connection: Connection, message: TgMessage) -> Chat:
        chat = await db.scalar(select(Chat).where(Chat.business_connection_id == connection.id, Chat.telegram_chat_id == message.chat.id))
        values = {"chat_type": message.chat.type, "title": message.chat.title, "username": message.chat.username, "first_name": message.chat.first_name, "last_name": message.chat.last_name}
        if chat:
            for key, value in values.items(): setattr(chat, key, value)
            return chat
        chat = Chat(business_connection_id=connection.id, telegram_chat_id=message.chat.id, **values); db.add(chat); await db.flush(); return chat
    async def _user(self, db: AsyncSession, message: TgMessage) -> User | None:
        if not message.from_user: return None
        source = message.from_user; user = await db.scalar(select(User).where(User.telegram_user_id == source.id))
        values = {"username": source.username, "first_name": source.first_name, "last_name": source.last_name, "is_bot": source.is_bot, "language_code": source.language_code}
        if user:
            for key, value in values.items(): setattr(user, key, value)
            return user
        user = User(telegram_user_id=source.id, **values); db.add(user); await db.flush(); return user
    async def archive(self, event: TgMessage, edited: bool = False, bot: Bot | None = None) -> Message | None:
        external_id = event.business_connection_id
        if not external_id: return None
        async with self.sessions() as db, db.begin():
            connection = await db.scalar(select(Connection).where(Connection.telegram_business_connection_id == external_id))
            if not connection or not connection.is_enabled: return None
            chat, sender = await self._chat(db, connection, event), await self._user(db, event)
            row = await db.scalar(select(Message).where(Message.business_connection_id == connection.id, Message.chat_id == chat.id, Message.telegram_message_id == event.message_id))
            kind = message_type(event); reply_id = event.reply_to_message.message_id if event.reply_to_message else None
            if row:
                if edited:
                    db.add(MessageVersion(message_id=row.id, text=row.text, caption=row.caption)); row.text, row.caption, row.edited_at = event.text, event.caption, datetime.fromtimestamp(event.edit_date, UTC) if event.edit_date else datetime.now(UTC)
                return row
            row = Message(business_connection_id=connection.id, chat_id=chat.id, sender_user_id=sender.id if sender else None, telegram_message_id=event.message_id, reply_to_telegram_message_id=reply_id, message_type=kind, text=event.text, caption=event.caption, sent_at=event.date, edited_at=event.edit_date if edited else None, is_outgoing=bool(event.from_user and event.from_user.id == connection.telegram_user_id), raw_data=event.model_dump(mode="json", exclude_none=True))
            if reply_id:
                row.reply_to_message_id = await db.scalar(select(Message.id).where(Message.chat_id == chat.id, Message.telegram_message_id == reply_id))
            db.add(row); await db.flush()
            media = attachment_payload(event, kind)
            if media:
                attachment = Attachment(message_id=row.id, **media)
                db.add(attachment)
                await db.flush()
                if bot: await self._download_attachment(bot, attachment)
            return row
    async def deleted(self, event: BusinessMessagesDeleted) -> int:
        async with self.sessions() as db, db.begin():
            connection = await db.scalar(select(Connection).where(Connection.telegram_business_connection_id == event.business_connection_id))
            if not connection: return 0
            chat = await db.scalar(select(Chat).where(Chat.business_connection_id == connection.id, Chat.telegram_chat_id == event.chat.id))
            if not chat: return 0
            result = await db.execute(update(Message).where(Message.business_connection_id == connection.id, Message.chat_id == chat.id, Message.telegram_message_id.in_(event.message_ids), Message.is_deleted.is_(False)).values(is_deleted=True, deleted_at=datetime.now(UTC)))
            return int(result.rowcount or 0)  # type: ignore[attr-defined]
