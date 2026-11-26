from aiogram import Router, types
from aiogram.filters import Command
from database import queries
from services.duty_manager import build_duty_message, get_current_duty_info
from handlers.common import get_webapp_keyboard
from handlers.duty_actions import get_duty_keyboard
from handlers.utils import esc_html

router = Router()


@router.message(Command("navbatchi"))
async def cmd_navbatchi(message: types.Message):
    """Bugungi navbatchi va vazifalarni ko'rsatish."""
    raw_title = message.chat.title or message.from_user.first_name or "Smart Kvartira"
    if not await queries.get_group(message.chat.id):
        await queries.register_or_update_group(message.chat.id, raw_title)

    duty_msg = await build_duty_message(message.chat.id, is_automatic=False)
    if not duty_msg:
        await message.answer(
            "⚠️ <b>Navbatchilar ro'yxati hali kiritilmagan!</b>\n\n"
            "/navbatchilar buyrug'i orqali ismlar ro'yxatini yuboring (username bo'lmasa faqat ismning o'zi ham yetarli).",
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
    raw_title = message.chat.title or message.from_user.first_name or "Smart Kvartira"
    if not await queries.get_group(message.chat.id):
        await queries.register_or_update_group(message.chat.id, raw_title)

    cur_member, members, current_index = await get_current_duty_info(message.chat.id)
    group = await queries.get_group(message.chat.id)

    if not members:
        await message.answer(
            "⚠️ <b>Navbatchilar ro'yxati hali kiritilmagan!</b>\n\n"
            "/navbatchilar buyrug'i orqali a'zolarni kiritishingiz mumkin.",
            reply_markup=get_webapp_keyboard(message.chat.id),
            parse_mode="HTML"
        )
        return

    active_id = cur_member["id"] if cur_member else None
    is_temp = bool(cur_member and cur_member.get("is_temporary"))

    safe_title = esc_html(raw_title)
    lines = [
        f"📅 <b>'{safe_title}' NAVBATCHILIK JADVALI:</b>",
        ""
    ]

    for idx, mem in enumerate(members):
        order = idx + 1
        raw_uname = str(mem.get("username") or "").replace("@", "").strip()
        username_str = f" (@{esc_html(raw_uname)})" if raw_uname else ""
        name_str = esc_html(mem.get("name") or "Noma'lum")

        if mem["id"] == active_id:
            badge = "BUGUNGI NAVBAT (1 martalik)" if is_temp else "BUGUNGI NAVBAT"
            lines.append(f"👉 <b>{order}. {name_str}{username_str}</b>  ⬅️ <i>[{badge}]</i>")
        elif is_temp and idx == current_index:
            lines.append(f"    {order}. {name_str}{username_str} <i>(asl navbat)</i>")
        else:
            lines.append(f"    {order}. {name_str}{username_str}")

    lines.append("")
    notify_time = group.get("notify_time", "08:00") if group else "08:00"
    lines.append(f"⏰ <i>Eslatma vaqti: har kuni soat {esc_html(notify_time)}</i>")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_webapp_keyboard(message.chat.id),
        parse_mode="HTML"
    )


@router.message(Command("vazifalar"))
async def cmd_vazifalar(message: types.Message):
    """Guruhdagi kunlik vazifalar ro'yxatini ko'rsatish."""
    raw_title = message.chat.title or message.from_user.first_name or "Smart Kvartira"
    if not await queries.get_group(message.chat.id):
        await queries.register_or_update_group(message.chat.id, raw_title)

    tasks = await queries.get_tasks(message.chat.id)
    if not tasks:
        await message.answer(
            "📋 <b>Hali kunlik vazifalar belgilanmagan!</b>\n\n"
            "/vazifalar_sozlash buyrug'i orqali vazifalar ro'yxatini kiritishingiz mumkin.",
            reply_markup=get_webapp_keyboard(message.chat.id),
            parse_mode="HTML"
        )
        return

    safe_title = esc_html(raw_title)
    lines = [
        f"📋 <b>'{safe_title}' KUNLIK VAZIFALARI:</b>",
        ""
    ]
    for idx, t in enumerate(tasks, start=1):
        safe_task = esc_html(t.get("task_text"))
        lines.append(f"<b>{idx}.</b> {safe_task}")

    lines.append("")
    lines.append("<i>Vazifalarni yangilash uchun: /vazifalar_sozlash</i>")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_webapp_keyboard(message.chat.id),
        parse_mode="HTML"
    )
