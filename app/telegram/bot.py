from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonWebApp, WebAppInfo
from app.telegram.handlers.business import make_router
def make_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(); dispatcher.include_router(make_router()); return dispatcher
def make_bot(token: str) -> Bot: return Bot(token=token)
async def configure_menu_button(bot: Bot, app_url: str) -> None:
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Архів", web_app=WebAppInfo(url=app_url)))
