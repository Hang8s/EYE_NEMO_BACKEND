import os
os.environ.update({"DATABASE_URL": "sqlite+aiosqlite://", "TELEGRAM_BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyzABCDE", "ARCHIVE_API_KEY": "secret"})
from types import SimpleNamespace
from unittest.mock import AsyncMock
from sqlalchemy.pool import NullPool
from fastapi.testclient import TestClient
from app.config import Settings
from app.db.session import make_session_factory
from app.main import create_app, is_transient_database_connect_error
from app.services.message_archive import ArchiveService
from app.telegram.handlers.business import archive_message

def settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite://", telegram_bot_token="123456:abcdefghijklmnopqrstuvwxyzABCDE", archive_api_key="secret")
def test_health() -> None:
    with TestClient(create_app(settings())) as client: assert client.get("/health").json() == {"status": "ok"}
def test_api_rejects_missing_key() -> None:
    with TestClient(create_app(settings())) as client: assert client.get("/api/chats").status_code == 401
def test_api_accepts_valid_key() -> None:
    with TestClient(create_app(settings())) as client: assert client.get("/api/chats", headers={"Authorization": "Bearer secret"}).status_code == 200
def test_invalid_webhook_secret_rejected() -> None:
    with TestClient(create_app(settings())) as client: assert client.post("/telegram/webhook", json={"update_id": 1}).status_code == 403
def test_frontend_origin_is_normalized_for_cors() -> None:
    config = Settings(database_url="sqlite+aiosqlite://", telegram_bot_token="123456:abcdefghijklmnopqrstuvwxyzABCDE", archive_api_key="secret", frontend_origin="https://hang8s.github.io/EYE_NEMO_FRONTEND/")
    with TestClient(create_app(config)) as client:
        response = client.options("/mini-api/chats", headers={"Origin": "https://hang8s.github.io", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "X-Telegram-Init-Data"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://hang8s.github.io"

def test_vercel_uses_no_process_local_database_pool(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    sessions = make_session_factory("postgresql+asyncpg://user:password@db.example.com/app")
    assert isinstance(sessions.kw["bind"].pool, NullPool)


def test_transient_database_connect_error_detects_busy_socket() -> None:
    error = RuntimeError("database connection failed")
    error.__cause__ = OSError(16, "Device or resource busy")
    assert is_transient_database_connect_error(error)


def test_transient_database_connect_error_ignores_other_errors() -> None:
    assert not is_transient_database_connect_error(OSError(111, "Connection refused"))


async def test_archiving_restores_a_missing_business_connection() -> None:
    event = SimpleNamespace(business_connection_id="connection-id")
    connection = object()
    archive = SimpleNamespace(archive=AsyncMock(side_effect=[None, object()]), connection=AsyncMock())
    bot = SimpleNamespace(get_business_connection=AsyncMock(return_value=connection))
    assert await archive_message(event, archive, bot)
    bot.get_business_connection.assert_awaited_once_with("connection-id")
    archive.connection.assert_awaited_once_with(connection)
    assert archive.archive.await_count == 2


async def test_attachment_is_saved_to_private_blob(monkeypatch) -> None:
    from vercel.blob import AsyncBlobClient

    attachment = SimpleNamespace(
        id="attachment-id", telegram_file_id="telegram-file", file_name="photo.jpg",
        mime_type="image/jpeg", file_size=3, storage_key=None,
    )
    bot = SimpleNamespace(
        get_file=AsyncMock(return_value=SimpleNamespace(file_path="photos/source.jpg")),
        download_file=AsyncMock(side_effect=lambda _path, destination: destination.write(b"jpg")),
    )

    async def put(_self, *_args, **_kwargs):
        return SimpleNamespace(url="https://store.private.blob.vercel-storage.com/attachments/photo.jpg")

    monkeypatch.setattr(AsyncBlobClient, "put", put)
    config = Settings(
        database_url="sqlite+aiosqlite://", telegram_bot_token="123456:abcdefghijklmnopqrstuvwxyzABCDE",
        archive_api_key="secret", media_storage="blob", blob_read_write_token="blob-token",
    )
    await ArchiveService(None, config)._download_attachment(bot, attachment)
    assert attachment.storage_key == "https://store.private.blob.vercel-storage.com/attachments/photo.jpg"
