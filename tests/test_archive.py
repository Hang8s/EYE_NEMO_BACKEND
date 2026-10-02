from datetime import UTC, datetime
import pytest
from aiogram.types import BusinessConnection, Message, User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base
from app.db.models import Chat, Message as StoredMessage, MessageVersion
from app.services.message_archive import ArchiveService

def connection() -> BusinessConnection:
    return BusinessConnection(id="connection-1", user=User(id=7, is_bot=False, first_name="Owner"), user_chat_id=7, date=datetime.now(UTC), is_enabled=True)
def message(message_id: int = 10, text: str = "hello", reply_to: int | None = None) -> Message:
    data = {"message_id": message_id, "date": int(datetime.now(UTC).timestamp()), "chat": {"id": 99, "type": "private", "first_name": "Chat"}, "from": {"id": 8, "is_bot": False, "first_name": "Sender"}, "business_connection_id": "connection-1", "text": text}
    if reply_to: data["reply_to_message"] = {"message_id": reply_to, "date": int(datetime.now(UTC).timestamp()), "chat": data["chat"], "from": data["from"], "text": "original"}
    return Message.model_validate(data)
@pytest.fixture
async def archive() -> ArchiveService:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False); service = ArchiveService(factory)
    await service.connection(connection())
    yield service
    await engine.dispose()
@pytest.mark.parametrize("text", ["one", "two"])
async def test_new_message_saved(archive: ArchiveService, text: str) -> None:
    await archive.archive(message(text=text))
    async with archive.sessions() as db: assert await db.scalar(select(func.count()).select_from(StoredMessage)) == 1
async def test_duplicate_is_idempotent(archive: ArchiveService) -> None:
    await archive.archive(message()); await archive.archive(message())
    async with archive.sessions() as db: assert await db.scalar(select(func.count()).select_from(StoredMessage)) == 1
async def test_edit_creates_version(archive: ArchiveService) -> None:
    await archive.archive(message(text="before")); await archive.archive(message(text="after"), edited=True)
    async with archive.sessions() as db:
        assert (await db.scalar(select(StoredMessage.text))) == "after"; assert await db.scalar(select(func.count()).select_from(MessageVersion)) == 1
@pytest.mark.parametrize("reply", [1, 2])
async def test_reply_identity_is_preserved(archive: ArchiveService, reply: int) -> None:
    await archive.archive(message(reply_to=reply))
    async with archive.sessions() as db: assert await db.scalar(select(StoredMessage.reply_to_telegram_message_id)) == reply
async def test_chat_upsert(archive: ArchiveService) -> None:
    await archive.archive(message(1)); await archive.archive(message(2))
    async with archive.sessions() as db: assert await db.scalar(select(func.count()).select_from(Chat)) == 1
@pytest.mark.parametrize("deleted", [False, True])
async def test_message_flags(archive: ArchiveService, deleted: bool) -> None:
    await archive.archive(message());
    async with archive.sessions() as db: assert (await db.scalar(select(StoredMessage.is_deleted))) is False
