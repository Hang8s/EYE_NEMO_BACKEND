import asyncio

from app.config import get_settings
from app.telegram.bot import configure_menu_button, make_bot


async def main() -> None:
    settings = get_settings()
    app_url = settings.mini_app_url or settings.frontend_origin
    if not app_url:
        raise RuntimeError("MINI_APP_URL is required")
    bot = make_bot(settings.telegram_bot_token.get_secret_value())
    try:
        await configure_menu_button(bot, app_url)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
