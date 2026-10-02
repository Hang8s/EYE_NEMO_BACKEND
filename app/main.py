from __future__ import annotations
from contextlib import asynccontextmanager
import time
import uuid
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from typing import AsyncIterator
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from aiogram.types import Update
from app.api.router import router as api_router
from app.api.mini import router as mini_router
from app.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import make_session_factory
from app.db.base import Base
from app.services.message_archive import ArchiveService
from app.telegram.bot import make_bot, make_dispatcher


logger = structlog.get_logger(__name__)


def validation_summary(error: RequestValidationError) -> list[dict[str, object]]:
    """Return useful validation context without recording submitted values."""
    return [
        {"location": ".".join(str(part) for part in item["loc"]), "type": item["type"]}
        for item in error.errors()
    ]

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
    application = FastAPI(title="Telegram Business Archive", lifespan=lifespan)

    @application.middleware("http")
    async def log_client_errors(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()
        response = await call_next(request)
        if 400 <= response.status_code < 500:
            logger.warning(
                "http_client_error_response",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                query_parameters=sorted(request.query_params.keys()),
                duration_ms=round((time.perf_counter() - started_at) * 1000, 1),
            )
        response.headers["X-Request-ID"] = request_id
        return response

    @application.exception_handler(RequestValidationError)
    async def log_validation_error(request: Request, error: RequestValidationError):  # type: ignore[no-untyped-def]
        logger.warning(
            "request_validation_error",
            request_id=getattr(request.state, "request_id", None),
            method=request.method,
            path=request.url.path,
            validation_errors=validation_summary(error),
        )
        return await request_validation_exception_handler(request, error)

    @application.exception_handler(StarletteHTTPException)
    async def log_http_exception(request: Request, error: StarletteHTTPException):  # type: ignore[no-untyped-def]
        if 400 <= error.status_code < 500:
            logger.warning(
                "http_exception",
                request_id=getattr(request.state, "request_id", None),
                method=request.method,
                path=request.url.path,
                status_code=error.status_code,
                detail=str(error.detail),
            )
        return await http_exception_handler(request, error)

    application.include_router(api_router); application.include_router(mini_router)
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
        update = Update.model_validate(await request.json()); await request.app.state.dispatcher.feed_update(request.app.state.bot, update, archive=request.app.state.archive, app_url=config.mini_app_url or config.frontend_origin); return {"ok": True}
    return application
app = create_app()
