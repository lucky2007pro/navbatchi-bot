from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart, ChatMemberUpdatedFilter, JOIN_TRANSITION, PROMOTED_TRANSITION
from aiogram.enums import ChatType
from database import queries

from config import WEBAPP_URL
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

router = Router()

def get_webapp_keyboard(chat_id: int, extra_buttons: list = None) -> InlineKeyboardMarkup:
    """Smart Kvartira Web App inline tugmasini qaytaradi."""
    rows = []
    if extra_buttons:
        rows.extend(extra_buttons)
    if WEBAPP_URL:
        url = f"{WEBAPP_URL}?chat_id={chat_id}"
        rows.append([
            InlineKeyboardButton(text="📱 Smart Kvartira Web App", web_app=WebAppInfo(url=url))
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

START_HELP_PRIVATE = """
👋 <b>Assalomu alaykum! Navbatchilik botiga xush kelibsiz!</b>

Bu bot Telegram guruhlarida <b>navbatchilik jadvalini</b>, <b>kunlik vazifalarni</b> va <b>kvartira moliyasini</b> qulay boshqarish uchun mo'ljallangan.

🚀 <b>Botni ishlatish bo'yicha qisqa qo'llanma:</b>
1. Botni guruhingizga qo'shing.
2. Botga xabarlarni qadash (pin) huquqini bering.
3. Guruhda navbatchilar ro'yxatini kiriting: <code>/navbatchilar</code>
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

🔄 <b>Almashtirish va O'tkazib yuborish (1 martalik):</b>
• /almashtirish — Navbatni boshqa a'zo bilan 1 martaga almashtirish (keyin joyiga qaytadi)
• /otkazish — Navbatni 1 martaga o'tkazib yuborish (keyin joyiga qaytadi)
• /qaytarish — Bir martalik almashish yoki o'tkazishni bekor qilib, asl navbatchiga qaytarish

💰 <b>Kvartira kassasi va xarajatlar:</b>
• /kassa — Kassa qoldig'i va oylik xarajatlar
• /xarajat <code>summa nomi</code> — Tezkor xarajat yozish (masalan: <code>/xarajat 50000 Go'sht</code>)
• /ijara — Oylik ijara holati va to'lovlar
• /bozorlik — Bozorlik ro'yxatini ko'rish
• /bozorlik_qosh <code>nomi</code> — Bozorlikka mahsulot qo'shish

⚙️ <b>Sozlash va tahrirlash (hamma uchun ochiq):</b>
• /navbatchilar — Navbatchilar ro'yxatini yangitdan kiritish
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
        await message.answer(START_HELP_PRIVATE, parse_mode="HTML")
    else:
        # Guruhda start bosilganda guruhni bazaga yozamiz
        await queries.register_or_update_group(message.chat.id, message.chat.title or "Nomsiz guruh")
        await message.answer(
            f"👋 Assalomu alaykum! <b>{message.chat.title}</b> guruhida Navbatchilik boti faollashtirildi.\n\n"
            f"⚙️ Sozlash uchun /navbatchilar yoki /help buyrug'idan foydalaning.",
            parse_mode="HTML"
        )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=PROMOTED_TRANSITION))
async def on_bot_added_to_group(event: types.ChatMemberUpdated):
    """Bot guruhga qo'shilganda yoki admin qilinganda ishga tushadi."""
    chat = event.chat
    await queries.register_or_update_group(chat.id, chat.title or "Nomsiz guruh")

    text = (
        f"👋 Assalomu alaykum, <b>{chat.title}</b> a'zolari!\n\n"
        f"Men bu guruhda <b>kunlik navbatchilikni</b> nazorat qilaman.\n"
        f"📌 Iltimos, xabarlarni qadab (pin) qo'yishim uchun menga <b>Adminlik huquqini</b> bering.\n\n"
        f"🚀 Boshlash uchun guruh admini quyidagi buyruqdan foydalanishi mumkin:\n"
        f"👉 /navbatchilar — Navbatchilar ro'yxatini kiritish\n"
        f"👉 /vazifalar_sozlash — Vazifalarni kiritish\n"
        f"👉 /help — To'liq qo'llanma"
    )
    await event.bot.send_message(chat_id=chat.id, text=text, parse_mode="HTML")
