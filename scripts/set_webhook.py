import asyncio
from aiogram import Bot
from app.config import get_settings
async def main() -> None:
    settings = get_settings()
    if not settings.app_base_url or not settings.telegram_webhook_secret: raise RuntimeError("APP_BASE_URL and TELEGRAM_WEBHOOK_SECRET are required")
    bot = Bot(settings.telegram_bot_token.get_secret_value())
    try: await bot.set_webhook(f"{settings.app_base_url.rstrip('/')}/telegram/webhook", secret_token=settings.telegram_webhook_secret.get_secret_value(), allowed_updates=["business_connection", "business_message", "edited_business_message", "deleted_business_messages", "message"])
    finally: await bot.session.close()
if __name__ == "__main__": asyncio.run(main())
