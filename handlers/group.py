from aiogram import Router, types
from aiogram.filters import Command
from aiogram.enums import ChatType
from database import queries
from services.duty_manager import build_duty_message, get_current_duty_info
from handlers.common import get_webapp_keyboard
from handlers.duty_actions import get_duty_keyboard

router = Router()

@router.message(Command("navbatchi"))
async def cmd_navbatchi(message: types.Message):
    """Bugungi navbatchi va vazifalarni ko'rsatish."""
    if message.chat.type == ChatType.PRIVATE:
        await message.answer("ℹ️ Bu buyruq faqat guruhlarda ishlaydi. Botni guruhingizga qo'shing.")
        return

    duty_msg = await build_duty_message(message.chat.id, is_automatic=False)
    if not duty_msg:
        await message.answer(
            "⚠️ <b>Navbatchilar ro'yxati hali kiritilmagan!</b>\n\n"
            "Guruh a'zolari /navbatchilar buyrug'i yoki Web App orqali ro'yxatni kiritishi mumkin.",
            reply_markup=get_webapp_keyboard(message.chat.id),
            parse_mode="HTML"
        )
        return

    group = await queries.get_group(message.chat.id)
    has_temp = bool(group and group.get("temp_duty_member_id"))
    await message.answer(
        duty_msg,
        reply_markup=get_duty_keyboard(message.chat.id, has_temp=has_temp),
        parse_mode="HTML"
    )

@router.message(Command("jadval"))
async def cmd_jadval(message: types.Message):
    """Guruhdagi to'liq navbatchilik jadvalini ko'rsatish."""
    if message.chat.type == ChatType.PRIVATE:
        await message.answer("ℹ️ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    group = await queries.get_group(message.chat.id)
    members = await queries.get_members(message.chat.id)

    if not members:
        await message.answer(
            "⚠️ <b>Navbatchilar ro'yxati hali kiritilmagan!</b>\n\n"
            "Guruh admini /navbatchilar buyrug'i orqali a'zolarni kiritishi mumkin.",
            parse_mode="HTML"
        )
        return

    current_index = (group.get("current_index", 0) if group else 0) % len(members)

    lines = [
        f"📅 <b>'{message.chat.title}' GURUHI NAVBATCHILIK JADVALI:</b>",
        ""
    ]

    for idx, mem in enumerate(members):
        order = idx + 1
        username_str = f" (@{mem['username']})" if mem.get("username") else ""
        name_str = mem.get("name", "Noma'lum")

        # Agar ayni damdagi navbatchi bo'lsa
        if idx == current_index:
            lines.append(f"👉 <b>{order}. {name_str}{username_str}</b>  ⬅️ <i>[BUGUNGI NAVBAT]</i>")
        else:
            lines.append(f"    {order}. {name_str}{username_str}")

    lines.append("")
    notify_time = group.get("notify_time", "08:00") if group else "08:00"
    lines.append(f"⏰ <i>Eslatma vaqti: har kuni soat {notify_time}</i>")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_webapp_keyboard(message.chat.id),
        parse_mode="HTML"
    )

@router.message(Command("vazifalar"))
async def cmd_vazifalar(message: types.Message):
    """Guruhdagi kunlik vazifalar ro'yxatini ko'rsatish."""
    if message.chat.type == ChatType.PRIVATE:
        await message.answer("ℹ️ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    tasks = await queries.get_tasks(message.chat.id)
    if not tasks:
        await message.answer(
            "📋 <b>Guruhda hali kunlik vazifalar belgilanmagan!</b>\n\n"
            "Guruh admini Web App yoki /vazifalar_sozlash buyrug'i orqali vazifalar ro'yxatini kiritishi mumkin.",
            reply_markup=get_webapp_keyboard(message.chat.id),
            parse_mode="HTML"
        )
        return

    lines = [
        f"📋 <b>'{message.chat.title}' GURUHI KUNLIK VAZIFALARI:</b>",
        ""
    ]
    for idx, t in enumerate(tasks, start=1):
        lines.append(f"<b>{idx}.</b> {t['task_text']}")

    lines.append("")
    lines.append("<i>Admin vazifalarni o'zgartirish uchun Web App'dan foydalanishi mumkin:</i>")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_webapp_keyboard(message.chat.id),
        parse_mode="HTML"
    )
