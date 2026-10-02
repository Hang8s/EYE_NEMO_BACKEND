from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import AsyncIterator
from aiogram.types import Update
from app.api.router import router as api_router
from app.api.mini import router as mini_router
from app.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import make_session_factory
from app.db.base import Base
from app.services.message_archive import ArchiveService
from app.telegram.bot import make_bot, make_dispatcher

def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings(); configure_logging(config.log_level)
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.sessions = make_session_factory(config.database_url); app.state.settings = config; app.state.bot = make_bot(config.telegram_bot_token.get_secret_value()); app.state.dispatcher = make_dispatcher(); app.state.archive = ArchiveService(app.state.sessions, config)
        if config.database_url.startswith("sqlite"):
            async with app.state.sessions.kw["bind"].begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        yield
        await app.state.bot.session.close(); await app.state.sessions.kw["bind"].dispose()
    application = FastAPI(title="Telegram Business Archive", lifespan=lifespan); application.include_router(api_router); application.include_router(mini_router)
    if config.frontend_origin:
        application.add_middleware(CORSMiddleware, allow_origins=[config.frontend_origin], allow_credentials=False, allow_methods=["GET"], allow_headers=["X-Telegram-Init-Data", "Content-Type"])
    @application.get("/health")
    async def health() -> dict[str, str]: return {"status": "ok"}
    @application.get("/health/ready")
    async def ready(request: Request) -> dict[str, str]:
        from sqlalchemy import text
        async with request.app.state.sessions() as db: await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    @application.post("/telegram/webhook")
    async def webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> dict[str, bool]:
        expected = config.telegram_webhook_secret.get_secret_value() if config.telegram_webhook_secret else None
        if not expected or x_telegram_bot_api_secret_token != expected: raise HTTPException(403, "Invalid webhook secret")
        update = Update.model_validate(await request.json()); await request.app.state.dispatcher.feed_update(request.app.state.bot, update, archive=request.app.state.archive, app_url=config.frontend_origin); return {"ok": True}
    return application
app = create_app()
