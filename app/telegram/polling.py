import asyncio
from app.config import get_settings
from app.db.session import make_session_factory
from app.services.message_archive import ArchiveService
from app.telegram.bot import make_bot, make_dispatcher
async def main() -> None:
    settings = get_settings()
    if settings.telegram_mode != "polling" or settings.app_env == "production": raise RuntimeError("polling is development-only")
    bot = make_bot(settings.telegram_bot_token.get_secret_value())
    try: await make_dispatcher().start_polling(bot, archive=ArchiveService(make_session_factory(settings.database_url), settings), app_url=settings.frontend_origin, allowed_updates=["business_connection", "business_message", "edited_business_message", "deleted_business_messages", "message"])
    finally: await bot.session.close()
if __name__ == "__main__": asyncio.run(main())
