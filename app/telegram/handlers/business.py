import structlog
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.message_archive import ArchiveService
log = structlog.get_logger()
async def connection(event: BusinessConnection, archive: ArchiveService) -> None:
    await archive.connection(event); log.info("telegram.business_connection.updated", business_connection_id=event.id)
async def message(event: Message, archive: ArchiveService, bot: Bot) -> None:
    await archive.archive(event, bot=bot); log.info("telegram.business_message.archived", business_connection_id=event.business_connection_id, telegram_chat_id=event.chat.id, telegram_message_id=event.message_id)
async def edited(event: Message, archive: ArchiveService, bot: Bot) -> None:
    await archive.archive(event, edited=True, bot=bot); log.info("telegram.business_message.edited", business_connection_id=event.business_connection_id, telegram_chat_id=event.chat.id, telegram_message_id=event.message_id)
async def deleted(event: BusinessMessagesDeleted, archive: ArchiveService) -> None:
    await archive.deleted(event); log.info("telegram.business_message.deleted", business_connection_id=event.business_connection_id, telegram_chat_id=event.chat.id)
async def archive_command(event: Message, app_url: str | None) -> None:
    if not app_url:
        await event.answer("Mini App URL is not configured.")
        return
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Відкрити архів", web_app=WebAppInfo(url=app_url))
    await event.answer("Ваш особистий архів чатів:", reply_markup=keyboard.as_markup())
def make_router() -> Router:
    router = Router(name="business")
    router.business_connection.register(connection)
    router.business_message.register(message)
    router.edited_business_message.register(edited)
    router.deleted_business_messages.register(deleted)
    router.message.register(archive_command, Command("archive"))
    return router
