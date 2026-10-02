import os
os.environ.update({"DATABASE_URL": "sqlite+aiosqlite://", "TELEGRAM_BOT_TOKEN": "123456:abcdefghijklmnopqrstuvwxyzABCDE", "ARCHIVE_API_KEY": "secret"})
from fastapi.testclient import TestClient
from app.config import Settings
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
