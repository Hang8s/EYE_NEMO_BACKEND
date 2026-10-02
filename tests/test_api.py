import os
os.environ.update({"DATABASE_URL": "sqlite+aiosqlite://", "TELEGRAM_BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyzABCDE", "ARCHIVE_API_KEY": "secret"})
from sqlalchemy.pool import NullPool
from fastapi.testclient import TestClient
from app.config import Settings
from app.db.session import make_session_factory
from app.main import create_app

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
