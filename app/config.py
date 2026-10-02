from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlsplit

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_env: str = "development"; app_host: str = "0.0.0.0"; app_port: int = Field(default=8000, validation_alias="PORT")
    database_url: str; telegram_bot_token: SecretStr; telegram_mode: str = "polling"
    telegram_webhook_secret: SecretStr | None = None; app_base_url: str | None = None; archive_api_key: SecretStr
    media_storage: str = "none"; media_path: Path = Path("/data/media"); log_level: str = "INFO"
    frontend_origin: str | None = None
    mini_app_url: str | None = None
    mini_app_auth_max_age_seconds: int = 3600
    @field_validator("telegram_mode")
    @classmethod
    def valid_mode(cls, value: str) -> str:
        if value not in {"webhook", "polling"}: raise ValueError("TELEGRAM_MODE must be webhook or polling")
        return value
    @field_validator("media_storage")
    @classmethod
    def valid_storage(cls, value: str) -> str:
        if value not in {"none", "local"}: raise ValueError("MEDIA_STORAGE must be none or local")
        return value
    @field_validator("frontend_origin")
    @classmethod
    def normalize_frontend_origin(cls, value: str | None) -> str | None:
        """CORS compares origins exactly, so remove a Pages path or trailing slash."""
        if not value:
            return value
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("FRONTEND_ORIGIN must be an absolute HTTP(S) URL")
        return f"{parsed.scheme}://{parsed.netloc}"
    def validate_production(self) -> None:
        if self.app_env == "production" and (self.telegram_mode != "webhook" or not self.app_base_url or not self.telegram_webhook_secret): raise ValueError("production requires webhook mode, APP_BASE_URL and TELEGRAM_WEBHOOK_SECRET")
@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    settings.validate_production()
    return settings
