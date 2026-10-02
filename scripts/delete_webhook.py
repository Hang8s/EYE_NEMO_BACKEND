import asyncio
from aiogram import Bot
from app.config import get_settings
async def main() -> None:
    bot = Bot(get_settings().telegram_bot_token.get_secret_value())
    try: await bot.delete_webhook(drop_pending_updates=False)
    finally: await bot.session.close()
if __name__ == "__main__": asyncio.run(main())
