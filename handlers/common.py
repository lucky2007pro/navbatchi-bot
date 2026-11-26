import html
from typing import Optional
from urllib.parse import urlparse

from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart, ChatMemberUpdatedFilter, JOIN_TRANSITION, PROMOTED_TRANSITION
from aiogram.enums import ChatType
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import config
from database import queries
from handlers.utils import esc_html

router = Router()


def is_valid_webapp_url(url: str) -> bool:
    """
    Telegram inline tugmalari uchun URL yaroqli ekanligini tekshiradi.
    Telegram faqat public HTTPS manzillarni qabul qiladi (localhost/127.0.0.1 xato beradi).
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith("https://"):
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host or host in ("localhost", "127.0.0.1", "0.0.0.0") or "." not in host:
            return False
        return True
    except Exception:
        return False


def get_webapp_keyboard(chat_id: int, extra_buttons: Optional[list] = None) -> Optional[InlineKeyboardMarkup]:
    """
    Guruh yoki shaxsiy chat uchun Web App ochish tugmasini va qo'shimcha tugmalarni yaratadi.
    Agar WEBAPP_URL yaroqsiz bo'lsa (masalan http://localhost:8080), Telegram xatolik bermasligi
    uchun faqat extra_buttons ni o'zini qaytaradi (yoki None).
    """
    rows = []
    if extra_buttons:
        rows.extend(extra_buttons)

    raw_url = getattr(config, "WEBAPP_URL", "") or ""
    if is_valid_webapp_url(raw_url):
        sep = "&" if "?" in raw_url else "?"
        webapp_url = f"{raw_url}{sep}chat_id={chat_id}"
        if chat_id < 0:
            # Guruhlarda inline tugmaga 'web_app' ruxsat berilmaydi (BUTTON_TYPE_INVALID), 'url' ishlatiladi
            rows.append([
                InlineKeyboardButton(
                    text="📱 Smart Kvartira Web App",
                    url=webapp_url
                )
            ])
        else:
            rows.append([
                InlineKeyboardButton(
                    text="📱 Smart Kvartira Web App",
                    web_app=WebAppInfo(url=webapp_url)
                )
            ])

    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


START_HELP_PRIVATE = """
👋 <b>Assalomu alaykum! Navbatchilik botiga xush kelibsiz!</b>

Bu bot Telegram guruhlarida <b>navbatchilik jadvalini</b>, <b>kunlik vazifalarni</b> va <b>kvartira moliyasini</b> qulay boshqarish uchun mo'ljallangan.

🚀 <b>Botni ishlatish bo'yicha qisqa qo'llanma:</b>
1. Botni guruhingizga qo'shing.
2. Botga xabarlarni qadash (pin) huquqini bering.
3. Guruhda navbatchilar ro'yxatini kiriting: <code>/navbatchilar</code> (username bo'lmasa faqat ismning o'zini yozish ham mumkin!)
4. Kunlik vazifalarni kiriting: <code>/vazifalar_sozlash</code>
5. Bildirishnoma vaqtini belgilang: <code>/vaqt 08:00</code>

Har kuni belgilangan soatda bot navbatchini belgilab, vazifalar bilan birga guruhga yuboradi va xabarni <b>qadab (pin)</b> qo'yadi!

ℹ️ Barcha buyruqlarni ko'rish uchun: /help
"""

HELP_TEXT = """
📖 <b>BOT BUYRUQLARI RO'YXATI:</b>

🧹 <b>Navbatchilik ma'lumotlari:</b>
• /navbatchi — Bugungi navbatchi va vazifalar ro'yxati
• /jadval — To'liq navbatchilar navbati va ro'yxati
• /vazifalar — Guruhdagi kunlik vazifalar ro'yxati
• /reyting — Xonadoshlar navbatchilik reytingi

🔄 <b>Almashtirish va O'tkazib yuborish (1 martalik):</b>
• /almashtirish — Navbatni boshqa a'zo bilan 1 martaga almashtirish (keyin joyiga qaytadi)
• /otkazish — Navbatni 1 martaga o'tkazib yuborish (keyin joyiga qaytadi)
• /qaytarish — Bir martalik almashish yoki o'tkazishni bekor qilib, asl navbatchiga qaytarish

💰 <b>Kvartira kassasi va xarajatlar:</b>
• /kassa — Kassa qoldig'i va oylik xarajatlar
• /kirim <code>summa izoh</code> — Kassaga pul qo'shish
• /chiqim <code>summa izoh</code> — Kassadan pul yechish
• /xarajat <code>summa nomi</code> — Tezkor xarajat yozish (masalan: <code>/xarajat 50000 Go'sht</code>)
• /ijara — Oylik ijara holati va to'lovlar
• /bozorlik — Bozorlik ro'yxatini ko'rish
• /bozorlik_qosh <code>nomi</code> — Bozorlikka mahsulot qo'shish

⚙️ <b>Sozlash va tahrirlash (hamma uchun ochiq):</b>
• /navbatchilar — Navbatchilar ro'yxatini kiritish (faqat ism yoki @username bilan)
• /qayta_tuzish — Navbatchilik jadvalini qayta tuzish (aralashtirish, boshiga qaytarish)
• /vazifalar_sozlash — Kunlik vazifalar ro'yxatini kiritish
• /keyingi — Navbatni navbatdagi odamga surish
• /vaqt <code>HH:MM</code> — Bildirishnoma vaqtini o'zgartirish (masalan: <code>/vaqt 08:30</code>)
• /kunlar — Qaysi kunlari bildirishnoma yuborilishini sozlash
• /holat — Guruh sozlamalari va statistikasi
• /tozalash — Navbatchilar yoki vazifalar ro'yxatini tozalash
"""


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            START_HELP_PRIVATE,
            reply_markup=get_webapp_keyboard(message.chat.id),
            parse_mode="HTML"
        )
    else:
        raw_title = message.chat.title or "Nomsiz guruh"
        await queries.register_or_update_group(message.chat.id, raw_title)
        safe_title = esc_html(raw_title)
        await message.answer(
            f"👋 Assalomu alaykum! <b>{safe_title}</b> guruhida Navbatchilik boti faollashtirildi.\n\n"
            f"⚙️ Sozlash uchun /navbatchilar yoki /help buyrug'idan foydalaning.",
            reply_markup=get_webapp_keyboard(message.chat.id),
            parse_mode="HTML"
        )


@router.message(Command("webapp"))
async def cmd_webapp(message: types.Message):
    """Web App ni ochish buyrug'i."""
    raw_title = message.chat.title or message.from_user.first_name or "Smart Kvartira"
    await queries.register_or_update_group(message.chat.id, raw_title)
    safe_title = esc_html(raw_title)
    kb = get_webapp_keyboard(message.chat.id)
    if kb:
        await message.answer(
            f"📱 <b>{safe_title}</b> navbatchilik va kvartira boshqaruvini Web App orqali ochish:",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"ℹ️ Web App manzili (HTTPS) hali sozlanmagan. Barcha funksiyalardan bot buyruqlari orqali foydalanishingiz mumkin (/help).",
            parse_mode="HTML"
        )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        HELP_TEXT,
        reply_markup=get_webapp_keyboard(message.chat.id),
        parse_mode="HTML"
    )


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=PROMOTED_TRANSITION))
async def on_bot_added_to_group(event: types.ChatMemberUpdated):
    """Bot guruhga qo'shilganda yoki admin qilinganda ishga tushadi."""
    chat = event.chat
    raw_title = chat.title or "Nomsiz guruh"
    await queries.register_or_update_group(chat.id, raw_title)
    safe_title = esc_html(raw_title)

    text = (
        f"👋 Assalomu alaykum, <b>{safe_title}</b> a'zolari!\n\n"
        f"Men bu guruhda <b>kunlik navbatchilikni</b> nazorat qilaman.\n"
        f"📌 Iltimos, xabarlarni qadab (pin) qo'yishim uchun menga <b>Adminlik huquqini</b> bering.\n\n"
        f"🚀 Boshlash uchun quyidagi buyruqlardan foydalanishingiz mumkin:\n"
        f"👉 /navbatchilar — Navbatchilar ro'yxatini kiritish\n"
        f"👉 /vazifalar_sozlash — Vazifalarni kiritish\n"
        f"👉 /help — To'liq qo'llanma"
    )
    await event.bot.send_message(
        chat_id=chat.id,
        text=text,
        reply_markup=get_webapp_keyboard(chat.id),
        parse_mode="HTML"
    )
