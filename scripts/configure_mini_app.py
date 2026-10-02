import asyncio

from app.config import get_settings
from app.telegram.bot import configure_menu_button, make_bot


async def main() -> None:
    settings = get_settings()
    if not settings.frontend_origin:
        raise RuntimeError("FRONTEND_ORIGIN is required")
    bot = make_bot(settings.telegram_bot_token.get_secret_value())
    try:
        await configure_menu_button(bot, settings.frontend_origin)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
