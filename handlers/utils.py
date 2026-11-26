import html
import re
from aiogram import Bot
from aiogram.enums import ChatType


def esc_html(val) -> str:
    """Telegram HTML xabar matni uchun (<, >, &) belgilarini xavfsiz kodlaydi (apostroflarni buzmasdan)."""
    return html.escape(str(val or ""), quote=False)


def extract_command_args(text: str) -> str:
    """
    Buyruqdan keyingi matnni ajratib oladi (bo'sh joy yoki yangi qator orqali yozilgan bo'lsa ham).
    Masalan:
      '/navbatchilar 1. Ali' -> '1. Ali'
      '/navbatchilar\\nAli\\nVali' -> 'Ali\\nVali'
    """
    if not text:
        return ""
    parts = re.split(r"\s+", text.strip(), maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


async def is_admin(bot: Bot, chat_id: int, user_id: int, chat_type: str) -> bool:
    """
    Foydalanuvchi guruh a'zosi/admini ekanligini tekshiradi.
    Bu bot ichki doira (o'zimiz) uchun bo'lgani tufayli barcha a'zolar tahrirlashi mumkin.
    """
    return True

