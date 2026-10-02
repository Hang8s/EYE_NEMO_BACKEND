import structlog
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.message_archive import ArchiveService
log = structlog.get_logger()
async def connection(event: BusinessConnection, archive: ArchiveService) -> None:
    await archive.connection(event); log.info("telegram.business_connection.updated", business_connection_id=event.id)


async def archive_message(event: Message, archive: ArchiveService, bot: Bot, *, edited: bool = False) -> bool:
    """Archive a message, restoring its Business Connection after a DB reset."""
    row = await archive.archive(event, edited=edited, bot=bot)
    if row is not None or not event.business_connection_id:
        return row is not None
    connection_event = await bot.get_business_connection(event.business_connection_id)
    await archive.connection(connection_event)
    return await archive.archive(event, edited=edited, bot=bot) is not None


async def message(event: Message, archive: ArchiveService, bot: Bot) -> None:
    stored = await archive_message(event, archive, bot)
    log.info("telegram.business_message.archived", business_connection_id=event.business_connection_id, telegram_chat_id=event.chat.id, telegram_message_id=event.message_id, stored=stored)


async def edited(event: Message, archive: ArchiveService, bot: Bot) -> None:
    stored = await archive_message(event, archive, bot, edited=True)
    log.info("telegram.business_message.edited", business_connection_id=event.business_connection_id, telegram_chat_id=event.chat.id, telegram_message_id=event.message_id, stored=stored)
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
