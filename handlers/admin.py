import html
import random
import re
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ChatType

from database import queries
from services.duty_manager import parse_members_text, parse_tasks_text, build_duty_message, advance_to_next_duty, get_current_duty_info
from handlers.utils import is_admin, extract_command_args, esc_html
from handlers.common import get_webapp_keyboard

router = Router()

class AdminStates(StatesGroup):
    waiting_for_members = State()
    waiting_for_tasks = State()
    waiting_for_time = State()

# ==================== NAVBATCHILARNI KIRITISH ====================

@router.message(Command("navbatchilar"))
async def cmd_navbatchilar(message: types.Message, state: FSMContext):
    """Navbatchilar ro'yxatini kiritish."""
    if not await is_admin(message.bot, message.chat.id, message.from_user.id, message.chat.type):
        await message.reply("⛔ <b>Kechirasiz, bu buyruq faqat guruh adminlari uchun!</b>", parse_mode="HTML")
        return

    # Guruhni bazaga ro'yxatga olib qo'yamiz
    await queries.register_or_update_group(message.chat.id, message.chat.title or message.from_user.first_name or "Smart Kvartira")

    # Buyruqdan keyin birdan matn yuborilgan bo'lsa (bo'sh joy yoki yangi qator bilan: /navbatchilar\nAli\nVali)
    command_args = extract_command_args(message.text)
    if command_args:
        await process_members_input(message, command_args)
        return

    # Aks holda FSM holatiga o'tkaziladi
    await state.set_state(AdminStates.waiting_for_members)
    await state.update_data(target_chat_id=message.chat.id)

    prompt = (
        "✍️ <b>Navbatchilar ro'yxatini yuboring:</b>\n\n"
        "Har bir a'zoni yangi qatordan tartib bilan yozing.\n"
        "<i>Namuna:</i>\n"
        "<code>1. @hojiakbar (Hojiakbar)</code>\n"
        "<code>2. @nodir (Nodir)</code>\n"
        "<code>3. Jasur</code>\n"
        "<code>4. Sardor</code>\n\n"
        "💡 <i>Guruhda yo'q yoki usernamesi yo'q a'zolarning faqat ismini yozsangiz kifoya!</i>\n\n"
        "Bekor qilish uchun /cancel deb yozing."
    )
    await message.reply(prompt, parse_mode="HTML")

@router.message(AdminStates.waiting_for_members)
async def handle_members_state(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("⚠️ Iltimos, navbatchilar ro'yxatini matn ko'rinishida yuboring (yoki /cancel bosing).")
        return
    if message.text.startswith("/cancel"):
        await state.clear()
        await message.reply("❌ Amal bekor qilindi.")
        return

    data = await state.get_data()
    chat_id = data.get("target_chat_id", message.chat.id)
    await state.clear()
    await process_members_input(message, message.text, target_chat_id=chat_id)

async def process_members_input(message: types.Message, text: str, target_chat_id: int = None):
    chat_id = target_chat_id or message.chat.id
    members = parse_members_text(text)

    if not members:
        await message.reply(
            "⚠️ <b>A'zolar ro'yxati aniqlanmadi!</b>\n"
            "Iltimos, har bir a'zoni yangi qatordan yozib qayta urinib ko'ring.",
            parse_mode="HTML"
        )
        return

    await queries.set_members(chat_id, members)

    result_lines = [
        "✅ <b>Navbatchilar ro'yxati muvaffaqiyatli saqlandi!</b>\n",
        "📋 <b>Yangi navbatchilik jadvali:</b>"
    ]
    for idx, mem in enumerate(members, start=1):
        raw_uname = str(mem.get("username") or "").replace("@", "").strip()
        username_str = f" (@{esc_html(raw_uname)})" if raw_uname else ""
        safe_name = esc_html(mem.get("name"))
        result_lines.append(f"{idx}. {safe_name}{username_str}")

    result_lines.append("")
    result_lines.append("👉 Navbat 1-a'zodan boshlandi (/navbatchi yoki /jadval orqali ko'rish mumkin).")
    result_lines.append("Vazifalarni kiritish uchun: /vazifalar_sozlash")

    await message.reply("\n".join(result_lines), parse_mode="HTML")

# ==================== VAZIFALARNI KIRITISH ====================

@router.message(Command("vazifalar_sozlash"))
async def cmd_vazifalar_sozlash(message: types.Message, state: FSMContext):
    """Kunlik vazifalar ro'yxatini kiritish."""
    if not await is_admin(message.bot, message.chat.id, message.from_user.id, message.chat.type):
        await message.reply("⛔ <b>Kechirasiz, bu buyruq faqat guruh adminlari uchun!</b>", parse_mode="HTML")
        return

    await queries.register_or_update_group(message.chat.id, message.chat.title or message.from_user.first_name or "Smart Kvartira")

    command_args = extract_command_args(message.text)
    if command_args:
        await process_tasks_input(message, command_args)
        return

    await state.set_state(AdminStates.waiting_for_tasks)
    await state.update_data(target_chat_id=message.chat.id)

    prompt = (
        "✍️ <b>Kunlik vazifalar ro'yxatini yuboring:</b>\n\n"
        "Har bir vazifani yangi qatordan yozing.\n"
        "<i>Namuna:</i>\n"
        "<code>1. Xonani shamollatish va tozalash</code>\n"
        "<code>2. Doska va ish stollarini tozalash</code>\n"
        "<code>3. Chiqindilarni chiqarib tashlash</code>\n\n"
        "Bekor qilish uchun /cancel deb yozing."
    )
    await message.reply(prompt, parse_mode="HTML")

@router.message(AdminStates.waiting_for_tasks)
async def handle_tasks_state(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("⚠️ Iltimos, vazifalar ro'yxatini matn ko'rinishida yuboring (yoki /cancel bosing).")
        return
    if message.text.startswith("/cancel"):
        await state.clear()
        await message.reply("❌ Amal bekor qilindi.")
        return

    data = await state.get_data()
    chat_id = data.get("target_chat_id", message.chat.id)
    await state.clear()
    await process_tasks_input(message, message.text, target_chat_id=chat_id)

async def process_tasks_input(message: types.Message, text: str, target_chat_id: int = None):
    chat_id = target_chat_id or message.chat.id
    tasks = parse_tasks_text(text)

    if not tasks:
        await message.reply(
            "⚠️ <b>Vazifalar ro'yxati aniqlanmadi!</b>\n"
            "Iltimos, har bir vazifani yangi qatordan yozib qayta yuboring.",
            parse_mode="HTML"
        )
        return

    await queries.set_tasks(chat_id, tasks)

    result_lines = [
        "✅ <b>Kunlik vazifalar ro'yxati saqlandi!</b>\n",
        "📋 <b>Vazifalar:</b>"
    ]
    for idx, t in enumerate(tasks, start=1):
        result_lines.append(f"{idx}. {esc_html(t)}")

    result_lines.append("")
    result_lines.append("Bugungi navbatchi bilan birga ushbu vazifalar ko'rsatiladi.")

    await message.reply("\n".join(result_lines), parse_mode="HTML")

# ==================== NAVBATNI MAJBURIY O'TKAZISH (/keyingi) ====================

@router.message(Command("keyingi"))
async def cmd_keyingi(message: types.Message):
    """Navbatni qo'lda keyingi a'zoga surish."""
    if not await is_admin(message.bot, message.chat.id, message.from_user.id, message.chat.type):
        await message.reply("⛔ <b>Kechirasiz, bu buyruq faqat guruh adminlari uchun!</b>", parse_mode="HTML")
        return

    members = await queries.get_members(message.chat.id)
    if not members:
        await message.reply("⚠️ Navbatchilar ro'yxati bo'sh! Avval /navbatchilar orqali kiriting.")
        return

    # Keyingisiga surish
    next_member = await advance_to_next_duty(message.chat.id)
    raw_uname = str(next_member.get("username") or "").replace("@", "").strip()
    mention = f"@{esc_html(raw_uname)}" if raw_uname else esc_html(next_member.get("name"))
    await message.reply(
        f"⏭️ <b>Navbat keyingi navbatchiga o'tkazildi!</b>\n\n"
        f"👉 Yangi navbatchi: <b>{mention}</b>\n\n"
        f"Barcha ma'lumotni ko'rish: /navbatchi",
        parse_mode="HTML"
    )

# ==================== BILDIRISHNOMA VAQTINI SOZLASH (/vaqt) ====================

@router.message(Command("vaqt"))
async def cmd_vaqt(message: types.Message):
    """Bildirishnoma vaqtini belgilash (masalan: /vaqt 08:30)."""
    if not await is_admin(message.bot, message.chat.id, message.from_user.id, message.chat.type):
        await message.reply("⛔ <b>Kechirasiz, bu buyruq faqat guruh adminlari uchun!</b>", parse_mode="HTML")
        return

    args = extract_command_args(message.text)
    if not args:
        group = await queries.get_group(message.chat.id)
        cur_time = group.get("notify_time", "08:00") if group else "08:00"
        await message.reply(
            f"⏰ <b>Hozirgi bildirishnoma vaqti:</b> <code>{cur_time}</code>\n\n"
            f"Vaqtni o'zgartirish uchun soat va daqiqani yuboring.\n"
            f"<i>Masalan:</i> <code>/vaqt 08:30</code> yoki <code>/vaqt 07:45</code>",
            parse_mode="HTML"
        )
        return

    if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", args):
        await message.reply("⚠️ Noto'g'ri vaqt formati! Iltimos, <code>HH:MM</code> formatida kiriting (masalan: <code>08:00</code>).", parse_mode="HTML")
        return

    # 8:00 ni 08:00 ga to'g'irlash
    parts = args.split(":")
    formatted_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}"

    await queries.register_or_update_group(message.chat.id, message.chat.title or "Nomsiz")
    await queries.update_group_settings(message.chat.id, notify_time=formatted_time)

    await message.reply(
        f"✅ <b>Bildirishnoma vaqti o'rnatildi:</b> <code>{formatted_time}</code>\n"
        f"Bot har kuni soat {formatted_time} da navbatchilik xabarini guruhga yuboradi va pin qiladi.",
        parse_mode="HTML"
    )

# ==================== ISH KUNLARINI SOZLASH (/kunlar) ====================

@router.message(Command("kunlar"))
async def cmd_kunlar(message: types.Message):
    """Qaysi kunlari bildirishnoma yuborilishini belgilash."""
    if not await is_admin(message.bot, message.chat.id, message.from_user.id, message.chat.type):
        await message.reply("⛔ <b>Kechirasiz, bu buyruq faqat guruh adminlari uchun!</b>", parse_mode="HTML")
        return

    group = await queries.get_group(message.chat.id)
    cur_days = group.get("work_days", "workdays_sat") if group else "workdays_sat"

    status_map = {
        "workdays": "🏢 Dushanba - Juma (5 kun)",
        "workdays_sat": "📅 Dushanba - Shanba (6 kun)",
        "all": "🔄 Har kuni (7 kun)"
    }

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 Dushanba - Juma (5 kun)", callback_data="days_workdays")],
        [InlineKeyboardButton(text="📅 Dushanba - Shanba (6 kun)", callback_data="days_workdays_sat")],
        [InlineKeyboardButton(text="🔄 Har kuni (7 kun)", callback_data="days_all")]
    ])

    await message.reply(
        f"📅 <b>Bildirishnoma yuborish kunlari:</b>\n"
        f"Hozirgi sozlama: <b>{status_map.get(cur_days, cur_days)}</b>\n\n"
        f"O'zgartirish uchun quyidagi variantlardan birini tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("days_"))
async def callback_days(call: CallbackQuery):
    if not await is_admin(call.bot, call.message.chat.id, call.from_user.id, call.message.chat.type):
        await call.answer("⛔ Faqat guruh admini o'zgartirishi mumkin!", show_alert=True)
        return

    mode = call.data.replace("days_", "")
    await queries.update_group_settings(call.message.chat.id, work_days=mode)

    names = {
        "workdays": "🏢 Dushanba - Juma (5 kun)",
        "workdays_sat": "📅 Dushanba - Shanba (6 kun)",
        "all": "🔄 Har kuni (7 kun)"
    }
    await call.answer("Sozlama saqlandi!")
    await call.message.edit_text(
        f"✅ <b>Bildirishnoma yuborish kunlari o'zgartirildi:</b>\n"
        f"👉 <b>{names.get(mode, mode)}</b>",
        parse_mode="HTML"
    )

# ==================== HOLATNI KO'RISH (/holat) ====================

@router.message(Command("holat"))
async def cmd_holat(message: types.Message):
    """Guruh sozlamalari va statistikasi."""
    if not await is_admin(message.bot, message.chat.id, message.from_user.id, message.chat.type):
        await message.reply("⛔ Bu buyruq faqat adminlar uchun!", parse_mode="HTML")
        return

    raw_title = message.chat.title or message.from_user.first_name or "Smart Kvartira"
    group = await queries.get_group(message.chat.id)
    if not group:
        await queries.register_or_update_group(message.chat.id, raw_title)
        group = await queries.get_group(message.chat.id)

    cur_member, members, _ = await get_current_duty_info(message.chat.id)
    tasks = await queries.get_tasks(message.chat.id)

    notify_time = group.get("notify_time", "08:00")
    work_days = group.get("work_days", "workdays_sat")
    is_active = "✅ Yoqilgan" if group.get("is_active", 1) else "❌ O'chirilgan"

    days_map = {
        "workdays": "Dushanba - Juma",
        "workdays_sat": "Dushanba - Shanba",
        "all": "Har kuni"
    }

    cur_member_name = "Belgilanmagan"
    if cur_member:
        cur_member_name = esc_html(cur_member.get("name") or "Noma'lum")
        raw_uname = str(cur_member.get("username") or "").replace("@", "").strip()
        if raw_uname:
            cur_member_name += f" (@{esc_html(raw_uname)})"
        if cur_member.get("is_temporary"):
            cur_member_name += " <i>(1 martalik)</i>"

    safe_title = esc_html(raw_title)
    text = (
        f"⚙️ <b>'{safe_title}' HOLATI:</b>\n\n"
        f"👥 <b>Navbatchilar soni:</b> {len(members)} nafar\n"
        f"👉 <b>Hozirgi navbatchi:</b> {cur_member_name}\n"
        f"📋 <b>Kunlik vazifalar:</b> {len(tasks)} ta\n"
        f"⏰ <b>Bildirishnoma vaqti:</b> {esc_html(notify_time)}\n"
        f"📅 <b>Kunlar:</b> {days_map.get(work_days, esc_html(work_days))}\n"
        f"🔔 <b>Avtomatik eslatma:</b> {is_active}\n\n"
        f"💡 <i>Vaqtni o'zgartirish: /vaqt 08:30</i>\n"
        f"💡 <i>Kunlarni o'zgartirish: /kunlar</i>\n"
        f"💡 <i>Jadvalni qayta tuzish: /qayta_tuzish</i>"
    )
    await message.reply(
        text,
        reply_markup=get_webapp_keyboard(message.chat.id),
        parse_mode="HTML"
    )

# ==================== TOZALASH (/tozalash) ====================

@router.message(Command("tozalash"))
async def cmd_tozalash(message: types.Message):
    """Ma'lumotlarni tozalash."""
    if not await is_admin(message.bot, message.chat.id, message.from_user.id, message.chat.type):
        await message.reply("⛔ Bu buyruq faqat adminlar uchun!", parse_mode="HTML")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Navbatchilarni o'chirish", callback_data="clear_members")],
        [InlineKeyboardButton(text="📋 Vazifalarni o'chirish", callback_data="clear_tasks")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="clear_cancel")]
    ])
    await message.reply("⚠️ <b>Nimani tozalamoqchisiz?</b>", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("clear_"))
async def callback_clear(call: CallbackQuery):
    if not await is_admin(call.bot, call.message.chat.id, call.from_user.id, call.message.chat.type):
        await call.answer("⛔ Faqat admin o'chira oladi!", show_alert=True)
        return

    action = call.data.replace("clear_", "")
    if action == "members":
        await queries.clear_members(call.message.chat.id)
        await call.answer("Navbatchilar ro'yxati tozalandi!")
        await call.message.edit_text("✅ <b>Navbatchilar ro'yxati tozalandi.</b> Yangi ro'yxat kiritish uchun: /navbatchilar", parse_mode="HTML")
    elif action == "tasks":
        await queries.clear_tasks(call.message.chat.id)
        await call.answer("Vazifalar ro'yxati tozalandi!")
        await call.message.edit_text("✅ <b>Kunlik vazifalar ro'yxati tozalandi.</b> Yangi vazifalar kiritish uchun: /vazifalar_sozlash", parse_mode="HTML")
    else:
        await call.answer("Bekor qilindi.")
        await call.message.edit_text("❌ Tozalash bekor qilindi.")


# ==================== JADVALNI QAYTA TUZISH (/qayta_tuzish) ====================

def _format_schedule_list(members: list) -> str:
    lines = []
    for idx, mem in enumerate(members, start=1):
        raw_uname = str(mem.get("username") or "").replace("@", "").strip()
        username_str = f" (@{esc_html(raw_uname)})" if raw_uname else ""
        safe_name = esc_html(mem.get("name"))
        lines.append(f"{idx}. {safe_name}{username_str}")
    return "\n".join(lines)


@router.message(Command("qayta_tuzish"))
async def cmd_qayta_tuzish(message: types.Message):
    """Navbatchilik jadvalini qayta tuzish menyusi."""
    if not await is_admin(message.bot, message.chat.id, message.from_user.id, message.chat.type):
        await message.reply("⛔ <b>Kechirasiz, bu buyruq faqat guruh adminlari uchun!</b>", parse_mode="HTML")
        return

    await queries.register_or_update_group(message.chat.id, message.chat.title or "Nomsiz")
    members = await queries.get_members(message.chat.id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔀 Tasodifiy aralashtirish", callback_data="rebuild_shuffle")],
        [InlineKeyboardButton(text="⏮️ 1-o'rindan boshlash", callback_data="rebuild_reset")],
        [InlineKeyboardButton(text="🔁 Tartibni teskari qilish", callback_data="rebuild_reverse")],
        [InlineKeyboardButton(text="✍️ Yangi ro'yxat kiritish", callback_data="rebuild_new")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="rebuild_cancel")],
    ])

    if members:
        text = (
            "♻️ <b>NAVBATCHILIK JADVALINI QAYTA TUZISH</b>\n\n"
            f"📋 <b>Hozirgi tartib ({len(members)} nafar):</b>\n"
            f"{_format_schedule_list(members)}\n\n"
            "Qanday qayta tuzmoqchisiz?"
        )
    else:
        text = (
            "♻️ <b>NAVBATCHILIK JADVALINI QAYTA TUZISH</b>\n\n"
            "⚠️ Hozircha navbatchilar ro'yxati bo'sh.\n"
            "Yangi ro'yxat kiritish uchun quyidagi tugmani bosing:"
        )

    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("rebuild_"))
async def callback_rebuild_schedule(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.bot, call.message.chat.id, call.from_user.id, call.message.chat.type):
        await call.answer("⛔ Ruxsat berilmadi!", show_alert=True)
        return

    chat_id = call.message.chat.id
    action = call.data.replace("rebuild_", "")

    if action == "cancel":
        await call.answer("Bekor qilindi.")
        await call.message.edit_text("❌ Jadvalni qayta tuzish bekor qilindi.")
        return

    if action == "new":
        await state.set_state(AdminStates.waiting_for_members)
        await state.update_data(target_chat_id=chat_id)
        await call.answer()
        await call.message.edit_text(
            "✍️ <b>Yangi navbatchilar ro'yxatini yuboring:</b>\n\n"
            "Har bir a'zoni yangi qatordan tartib bilan yozing.\n"
            "<i>Namuna:</i>\n"
            "<code>1. @hojiakbar (Hojiakbar)</code>\n"
            "<code>2. @nodir (Nodir)</code>\n"
            "<code>3. Jasur</code>\n\n"
            "Bekor qilish uchun /cancel deb yozing.",
            parse_mode="HTML"
        )
        return

    members = await queries.get_members(chat_id)
    if not members:
        await call.answer("⚠️ Navbatchilar ro'yxati bo'sh!", show_alert=True)
        return

    if action == "shuffle":
        reordered = [{"name": m["name"], "username": m.get("username", "")} for m in members]
        random.shuffle(reordered)
        await queries.set_members(chat_id, reordered)
        await queries.clear_temp_duty(chat_id)
        title = "🔀 <b>Jadval tasodifiy aralashtirildi!</b>"
        updated = reordered
    elif action == "reverse":
        reordered = [{"name": m["name"], "username": m.get("username", "")} for m in reversed(members)]
        await queries.set_members(chat_id, reordered)
        await queries.clear_temp_duty(chat_id)
        title = "🔁 <b>Jadval tartibi teskari qilindi!</b>"
        updated = reordered
    elif action == "reset":
        await queries.reset_schedule_progress(chat_id)
        title = "⏮️ <b>Navbat 1-o'rindan boshlandi!</b>"
        updated = members
    else:
        await call.answer("Noma'lum amal.")
        return

    await call.answer("Jadval yangilandi!")
    await call.message.edit_text(
        f"{title}\n\n"
        f"📋 <b>Yangi navbatchilik jadvali:</b>\n"
        f"{_format_schedule_list(updated)}\n\n"
        f"👉 Navbat 1-a'zodan boshlanadi. Ko'rish: /navbatchi",
        parse_mode="HTML"
    )
