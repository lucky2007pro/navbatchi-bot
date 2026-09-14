from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart, ChatMemberUpdatedFilter, JOIN_TRANSITION, PROMOTED_TRANSITION
from aiogram.enums import ChatType
from database import queries

router = Router()

START_HELP_PRIVATE = """
👋 <b>Assalomu alaykum! Navbatchilik botiga xush kelibsiz!</b>

Bu bot Telegram guruhlarida <b>navbatchilik jadvalini</b> va <b>kunlik vazifalarni</b> avtomatlashtirish uchun mo'ljallangan.

🚀 <b>Botni ishlatish bo'yicha qisqa qo'llanma:</b>
1. Botni guruhingizga qo'shing.
2. Botga guruhda <b>Admin</b> huquqini bering (<i>xabarlarni qadash / pin qilish huquqi bilan</i>).
3. Guruhda navbatchilar ro'yxatini kiriting: <code>/navbatchilar</code>
4. Kunlik vazifalarni kiriting: <code>/vazifalar_sozlash</code>
5. Bildirishnoma vaqtini belgilang: <code>/vaqt 08:00</code>

Har kuni belgilangan soatda bot navbatchini belgilab, vazifalar bilan birga guruhga yuboradi va xabarni <b>qadab (pin)</b> qo'yadi!

ℹ️ Barcha buyruqlarni ko'rish uchun: /help
"""

HELP_TEXT = """
📖 <b>BOT BUYRUQLARI RO'YXATI:</b>

👥 <b>Guruh a'zolari uchun:</b>
• /navbatchi — Bugungi navbatchi va vazifalar ro'yxatini ko'rsatish
• /jadval — To'liq navbatchilar navbati va ro'yxati
• /vazifalar — Guruhdagi kunlik vazifalar ro'yxati

⚙️ <b>Adminlar uchun buyruqlar:</b>
• /navbatchilar — Navbatchilar ro'yxatini yangitdan kiritish
• /vazifalar_sozlash — Kunlik vazifalar ro'yxatini kiritish
• /keyingi — Navbatni majburiy keyingi odamga o'tkazish
• /vaqt <code>HH:MM</code> — Bildirishnoma yuborish vaqtini o'zgartirish (masalan: <code>/vaqt 08:30</code>)
• /kunlar — Qaysi kunlari bildirishnoma yuborilishini sozlash
• /holat — Guruh sozlamalari va hozirgi holat
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
