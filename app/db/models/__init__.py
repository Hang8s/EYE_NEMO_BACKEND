from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
class BusinessConnection(Timestamped, Base):
    __tablename__ = "business_connections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    telegram_business_connection_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(255)); first_name: Mapped[str] = mapped_column(String(255)); last_name: Mapped[str | None] = mapped_column(String(255))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True); connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
class Chat(Timestamped, Base):
    __tablename__ = "chats"; __table_args__ = (UniqueConstraint("business_connection_id", "telegram_chat_id", name="uq_business_chat"), Index("ix_chats_connection_telegram", "business_connection_id", "telegram_chat_id"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4); business_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_connections.id"), index=True); telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True); chat_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(255)); username: Mapped[str | None] = mapped_column(String(255)); first_name: Mapped[str | None] = mapped_column(String(255)); last_name: Mapped[str | None] = mapped_column(String(255))
class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4); telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True); username: Mapped[str | None] = mapped_column(String(255)); first_name: Mapped[str] = mapped_column(String(255)); last_name: Mapped[str | None] = mapped_column(String(255)); is_bot: Mapped[bool] = mapped_column(Boolean, default=False); language_code: Mapped[str | None] = mapped_column(String(32))
class Message(Timestamped, Base):
    __tablename__ = "messages"; __table_args__ = (UniqueConstraint("business_connection_id", "chat_id", "telegram_message_id", name="uq_business_message"), Index("ix_messages_chat_sent", "chat_id", "sent_at"), Index("ix_messages_sender_sent", "sender_user_id", "sent_at"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4); business_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_connections.id"), index=True); chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.id"), index=True); sender_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True); telegram_message_id: Mapped[int] = mapped_column(Integer, index=True); reply_to_telegram_message_id: Mapped[int | None] = mapped_column(Integer); reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id")); message_type: Mapped[str] = mapped_column(String(32)); text: Mapped[str | None] = mapped_column(Text); caption: Mapped[str | None] = mapped_column(Text); sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True); edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True); is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True); is_outgoing: Mapped[bool] = mapped_column(Boolean, default=False); raw_data: Mapped[dict[str, object] | None] = mapped_column(JSON)
    attachments: Mapped[list[Attachment]] = relationship(back_populates="message", cascade="all, delete-orphan")
class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4); message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id"), index=True); telegram_file_id: Mapped[str] = mapped_column(String(255)); telegram_file_unique_id: Mapped[str] = mapped_column(String(255)); type: Mapped[str] = mapped_column(String(32)); file_name: Mapped[str | None] = mapped_column(String(512)); mime_type: Mapped[str | None] = mapped_column(String(255)); file_size: Mapped[int | None] = mapped_column(BigInteger); local_path: Mapped[str | None] = mapped_column(Text); storage_key: Mapped[str | None] = mapped_column(Text)
    message: Mapped[Message] = relationship(back_populates="attachments")
class MessageVersion(Base):
    __tablename__ = "message_versions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4); message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id"), index=True); text: Mapped[str | None] = mapped_column(Text); caption: Mapped[str | None] = mapped_column(Text); version_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
