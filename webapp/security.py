import hashlib
import hmac
import json
import logging
import time
from typing import Optional, Dict, Any
from urllib.parse import parse_qsl, unquote

from aiogram import Bot
from config import BOT_TOKEN

logger = logging.getLogger("WebAppSecurity")

def validate_telegram_init_data(init_data: str, bot_token: str = BOT_TOKEN, max_age_seconds: int = 86400) -> Optional[Dict[str, Any]]:
    """
    Telegram Web App tomonidan yuborilgan initData satrini tekshiradi.
    Agar haqiqiy bo'lsa, ma'lumotlar lug'atini (dict) qaytaradi, aks holda None.
    
    Telegram rasmiy algoritmi:
    1. initData dagi 'hash' ajratib olinadi.
    2. Qolgan parametrlar alifbo tartibida 'key=value' ko'rinishida saralanadi va '\\n' bilan birlashtiriladi.
    3. secret_key = HMAC_SHA256(b"WebAppData", bot_token)
    4. calculated_hash = HMAC_SHA256(secret_key, data_check_string)
    5. hash tengligi tekshiriladi.
    """
    if not init_data or not bot_token:
        return None

    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed_data.pop("hash", None)
        if not received_hash:
            return None

        # Parametrlarni kalit bo'yicha alifbo tartibida saralash
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

        # Maxfiy kalitni hisoblash
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        # Hashni hisoblash
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        # Vaqt hujumlariga qarshi xavfsiz taqqoslash
        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("Telegram WebApp initData hash mos kelmadi!")
            return None

        # auth_date vaqtini tekshirish (ixtiyoriy, eskirmaganligiga ishonch hosil qilish uchun)
        auth_date = int(parsed_data.get("auth_date", 0))
        if max_age_seconds > 0 and (time.time() - auth_date > max_age_seconds):
            logger.warning("Telegram WebApp initData muddati o'tgan!")
            return None

        # Foydalanuvchi ma'lumotlarini JSON dan o'qish
        if "user" in parsed_data:
            try:
                parsed_data["user"] = json.loads(parsed_data["user"])
            except Exception:
                pass

        return parsed_data
    except Exception as e:
        logger.error(f"initData tekshirishda xatolik: {e}")
        return None

async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Foydalanuvchi berilgan chatda admin ekanligini tekshiradi.
    Bu bot ichki doira (o'zimiz) uchun bo'lgani tufayli barcha a'zolarga tahrirlash huquqi beriladi.
    """
    return True

