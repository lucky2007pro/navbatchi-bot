from aiogram import Bot
from aiogram.enums import ChatType

async def is_admin(bot: Bot, chat_id: int, user_id: int, chat_type: str) -> bool:
    """Foydalanuvchi guruh admini yoki egasi ekanligini tekshiradi."""
    if chat_type == ChatType.PRIVATE:
        return True
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False
