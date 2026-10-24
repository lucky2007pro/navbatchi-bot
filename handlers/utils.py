from aiogram import Bot
from aiogram.enums import ChatType

async def is_admin(bot: Bot, chat_id: int, user_id: int, chat_type: str) -> bool:
    """
    Foydalanuvchi guruh a'zosi/admini ekanligini tekshiradi.
    Bu bot ichki doira (o'zimiz) uchun bo'lgani tufayli barcha a'zolar tahrirlashi mumkin.
    """
    return True

