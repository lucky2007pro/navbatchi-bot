import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ChatType

from database import queries
from services.duty_manager import get_current_duty_info, build_duty_message
from handlers.common import get_webapp_keyboard

logger = logging.getLogger(__name__)

router = Router()

def get_duty_keyboard(chat_id: int, has_temp: bool = False) -> InlineKeyboardMarkup:
    """Navbatchilik xabari ostidagi qulay boshqaruv tugmalari."""
    buttons = [
        [
            InlineKeyboardButton(text="🔄 Navbatni almashtirish", callback_data="duty_swap_init"),
            InlineKeyboardButton(text="⏭️ O'tkazib yuborish", callback_data="duty_skip_init"),
        ]
    ]
    if has_temp:
        buttons.append([
            InlineKeyboardButton(text="↩️ Asliga qaytarish", callback_data="duty_reset_temp")
        ])
    return get_webapp_keyboard(chat_id, extra_buttons=buttons)

# ==================== NAVBATNI ALMASHTIRISH (SWAP) ====================

@router.message(Command("almashtirish"))
@router.message(Command("swap"))
async def cmd_almashtirish(message: types.Message):
    """Navbatchilikni boshqa a'zo bilan bir martaga almashtirish."""
    if message.chat.type == ChatType.PRIVATE:
        await message.reply("ℹ️ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    chat_id = message.chat.id
    members = await queries.get_members(chat_id)
    if not members or len(members) < 2:
        await message.reply("⚠️ Guruhda navbatchilar ro'yxati kamida 2 kishi bo'lishi kerak! /navbatchilar orqali kiriting.")
        return

    cur_member, all_members, _ = await get_current_duty_info(chat_id)
    cur_id = cur_member["id"] if cur_member else None

    # Boshqa a'zolar ro'yxatidan tanlash uchun tugmalar
    keyboard_buttons = []
    for m in members:
        if m["id"] == cur_id:
            continue
        uname = f" (@{m['username']})" if m.get("username") else ""
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"👤 {m['name']}{uname}",
                callback_data=f"swap_to:{m['id']}"
            )
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="swap_cancel")
    ])

    cur_name = cur_member.get("name", "Hozirgi navbatchi")
    if cur_member.get("username"):
        cur_name += f" (@{cur_member['username']})"

    text = (
        "🔄 <b>NAVBATCHILIKNI ALMASHTIRISH</b>\n\n"
        f"👤 <b>Hozirgi navbatchi:</b> {cur_name}\n\n"
        "<i>Navbatchilikni kim bilan almashtirmoqchisiz? Quyidagi ro'yxatdan tanlang:</i>"
    )

    await message.reply(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "duty_swap_init")
async def callback_swap_init(call: CallbackQuery):
    """Navbatchilik xabaridagi '🔄 Navbatni almashtirish' tugmasi bosilganda."""
    chat_id = call.message.chat.id
    members = await queries.get_members(chat_id)
    if not members or len(members) < 2:
        await call.answer("Guruhda kamida 2 ta navbatchi bo'lishi kerak!", show_alert=True)
        return

    cur_member, all_members, _ = await get_current_duty_info(chat_id)
    cur_id = cur_member["id"] if cur_member else None

    keyboard_buttons = []
    for m in members:
        if m["id"] == cur_id:
            continue
        uname = f" (@{m['username']})" if m.get("username") else ""
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"👤 {m['name']}{uname}",
                callback_data=f"swap_to:{m['id']}"
            )
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="swap_cancel")
    ])

    cur_name = cur_member.get("name", "Hozirgi navbatchi")
    if cur_member.get("username"):
        cur_name += f" (@{cur_member['username']})"

    text = (
        "🔄 <b>NAVBATCHILIKNI ALMASHTIRISH</b>\n\n"
        f"👤 <b>Hozirgi navbatchi:</b> {cur_name}\n\n"
        "<i>Navbatchilikni kim bilan almashtirmoqchisiz? Quyidagi ro'yxatdan tanlang:</i>"
    )

    await call.message.reply(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )
    await call.answer()

@router.callback_query(F.data.startswith("swap_to:"))
async def callback_swap_pick(call: CallbackQuery):
    """Almashtirmoqchi bo'lgan a'zo tanlanganda taklif yuborish."""
    chat_id = call.message.chat.id
    to_member_id = int(call.data.split(":")[1])

    to_member = await queries.get_member_by_id(to_member_id)
    if not to_member:
        await call.answer("A'zo topilmadi!", show_alert=True)
        return

    cur_member, _, _ = await get_current_duty_info(chat_id)
    if not cur_member:
        await call.answer("Hozirgi navbatchi aniqlanmadi!", show_alert=True)
        return

    # Taklifni bazada saqlash
    req_id = await queries.create_swap_request(chat_id, cur_member["id"], to_member["id"])

    initiator = call.from_user.full_name or call.from_user.first_name
    from_tag = f"@{cur_member['username']}" if cur_member.get("username") else cur_member["name"]
    to_tag = f"@{to_member['username']}" if to_member.get("username") else to_member["name"]

    proposal_text = (
        "📩 <b>NAVBATCHILIKNI ALMASHTIRISH TAKLIFI!</b>\n\n"
        f"👤 <b>Taklif yuboruvchi:</b> {initiator}\n"
        f"👤 <b>Asl navbatchi:</b> {from_tag}\n"
        f"👉 <b>Taklif etilayotgan shaxs:</b> {to_tag}\n\n"
        f"❓ <b>{to_member['name']}</b>, siz bugun <b>{cur_member['name']}</b> o'rniga navbatchilik qilishga rozimisiz?\n\n"
        f"ℹ️ <i>(Bu 1 martalik almashinuv: bugun almashadi, keyingi navbatchilikda jadval yana o'z joyiga qaytadi)</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"swap_acc:{req_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"swap_rej:{req_id}")
        ]
    ])

    await call.message.edit_text(proposal_text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer("Taklif yuborildi!")

@router.callback_query(F.data.startswith("swap_acc:"))
async def callback_swap_accept(call: CallbackQuery):
    """Taklif qabul qilinganda navbatchini vaqtincha almashtirish."""
    req_id = int(call.data.split(":")[1])
    req = await queries.get_swap_request(req_id)
    if not req:
        await call.answer("Taklif topilmadi yoki muddati o'tgan!", show_alert=True)
        return

    if req.get("status") != "pending":
        await call.answer("Bu taklif allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    chat_id = req["chat_id"]
    to_member = await queries.get_member_by_id(req["to_member_id"])
    from_member = await queries.get_member_by_id(req["from_member_id"])

    # Foydalanuvchini tekshirish: agar to_member da username bo'lsa, mos keladimi?
    user_username = (call.from_user.username or "").lower()
    target_username = (to_member.get("username") or "").lower()
    
    # Agar target_username bo'lsa va bosgan odam boshqa bo'lsa
    if target_username and user_username and target_username != user_username:
        # Guruh ichidagi xonadoshlar bo'lgani sababli, boshqa odam bossa ogohlantiramiz
        await call.answer(f"⛔ Bu taklif faqat @{target_username} ({to_member['name']}) uchun!", show_alert=True)
        return

    # Taklifni qabul qilish
    await queries.update_swap_request_status(req_id, "accepted")
    await queries.set_temp_duty(chat_id, to_member["id"], "swap", from_member["id"])

    to_tag = f"@{to_member['username']}" if to_member.get("username") else to_member["name"]
    from_tag = f"@{from_member['username']}" if from_member.get("username") else from_member["name"]

    success_text = (
        "✅ <b>NAVBATCHILIK MUVAFFAQIYATLI ALMASHILDI!</b>\n\n"
        f"👤 <b>Bugungi yangi navbatchi:</b> {to_tag}\n"
        f"🔄 <i>({from_tag} bilan bir martaga almashildi)</i>\n\n"
        "✨ <i>Keyingi navbatchilikda jadval yana o'z joyiga qaytadi.</i>\n\n"
        "Barcha ma'lumotni ko'rish: /navbatchi"
    )

    await call.message.edit_text(success_text, reply_markup=None, parse_mode="HTML")
    await call.answer("Taklif qabul qilindi!")

@router.callback_query(F.data.startswith("swap_rej:"))
async def callback_swap_reject(call: CallbackQuery):
    """Taklif rad etilganda."""
    req_id = int(call.data.split(":")[1])
    req = await queries.get_swap_request(req_id)
    if not req:
        await call.answer("Taklif topilmadi!", show_alert=True)
        return

    if req.get("status") != "pending":
        await call.answer("Bu taklif allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    to_member = await queries.get_member_by_id(req["to_member_id"])
    from_member = await queries.get_member_by_id(req["from_member_id"])

    user_username = (call.from_user.username or "").lower()
    target_username = (to_member.get("username") or "").lower()
    if target_username and user_username and target_username != user_username:
        await call.answer(f"⛔ Bu taklif faqat @{target_username} uchun!", show_alert=True)
        return

    await queries.update_swap_request_status(req_id, "rejected")

    reject_text = (
        "❌ <b>TAKLIF RAD ETILDI</b>\n\n"
        f"<b>{to_member['name']}</b> navbatchilikni almashtirish taklifini rad etdi.\n"
        f"Bugungi navbatchi o'zgarishsiz qoldi: <b>{from_member['name']}</b>."
    )

    await call.message.edit_text(reject_text, reply_markup=None, parse_mode="HTML")
    await call.answer("Taklif rad etildi.")

@router.callback_query(F.data == "swap_cancel")
async def callback_swap_cancel(call: CallbackQuery):
    await call.message.edit_text("❌ Navbatchilikni almashtirish bekor qilindi.", reply_markup=None)
    await call.answer("Bekor qilindi.")

# ==================== O'TKAZIB YUBORISH (SKIP) ====================

@router.message(Command("otkazish"))
@router.message(Command("skip"))
async def cmd_otkazish(message: types.Message):
    """Bugungi navbatchilikni bir martaga keyingi a'zoga o'tkazib yuborish."""
    if message.chat.type == ChatType.PRIVATE:
        await message.reply("ℹ️ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    chat_id = message.chat.id
    members = await queries.get_members(chat_id)
    if not members or len(members) < 2:
        await message.reply("⚠️ Guruhda kamida 2 ta navbatchi bo'lishi kerak!")
        return

    group = await queries.get_group(chat_id)
    cur_idx = (group.get("current_index", 0) if group else 0) % len(members)
    cur_member = members[cur_idx]
    next_idx = (cur_idx + 1) % len(members)
    next_member = members[next_idx]

    cur_tag = f"@{cur_member['username']}" if cur_member.get("username") else cur_member["name"]
    next_tag = f"@{next_member['username']}" if next_member.get("username") else next_member["name"]

    text = (
        "⏭️ <b>NAVBATCHILIKNI O'TKAZIB YUBORISH</b>\n\n"
        f"👤 <b>Hozirgi navbatchi:</b> {cur_tag}\n"
        f"👉 <b>O'tkazilayotgan shaxs:</b> {next_tag}\n\n"
        f"❓ Bugungi navbatchilikni 1 martaga <b>{next_member['name']}</b>ga o'tkazmoqchimisiz?\n\n"
        f"ℹ️ <i>(Keyingi navbatchilikda navbat yana o'z joyiga — <b>{cur_member['name']}</b>ga qaytadi)</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Ha, o'tkazilsin",
                callback_data=f"skip_confirm:{next_member['id']}:{cur_member['id']}"
            ),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="skip_cancel")
        ]
    ])

    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "duty_skip_init")
async def callback_skip_init(call: CallbackQuery):
    """Navbatchi xabaridagi '⏭️ O'tkazib yuborish' tugmasi bosilganda."""
    chat_id = call.message.chat.id
    members = await queries.get_members(chat_id)
    if not members or len(members) < 2:
        await call.answer("Guruhda kamida 2 ta navbatchi bo'lishi kerak!", show_alert=True)
        return

    group = await queries.get_group(chat_id)
    cur_idx = (group.get("current_index", 0) if group else 0) % len(members)
    cur_member = members[cur_idx]
    next_idx = (cur_idx + 1) % len(members)
    next_member = members[next_idx]

    cur_tag = f"@{cur_member['username']}" if cur_member.get("username") else cur_member["name"]
    next_tag = f"@{next_member['username']}" if next_member.get("username") else next_member["name"]

    text = (
        "⏭️ <b>NAVBATCHILIKNI O'TKAZIB YUBORISH</b>\n\n"
        f"👤 <b>Hozirgi navbatchi:</b> {cur_tag}\n"
        f"👉 <b>O'tkazilayotgan shaxs:</b> {next_tag}\n\n"
        f"❓ Bugungi navbatchilikni 1 martaga <b>{next_member['name']}</b>ga o'tkazmoqchimisiz?\n\n"
        f"ℹ️ <i>(Keyingi navbatchilikda navbat yana o'z joyiga — <b>{cur_member['name']}</b>ga qaytadi)</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Ha, o'tkazilsin",
                callback_data=f"skip_confirm:{next_member['id']}:{cur_member['id']}"
            ),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="skip_cancel")
        ]
    ])

    await call.message.reply(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("skip_confirm:"))
async def callback_skip_confirm(call: CallbackQuery):
    """O'tkazib yuborishni tasdiqlash."""
    parts = call.data.split(":")
    next_id = int(parts[1])
    orig_id = int(parts[2])

    chat_id = call.message.chat.id
    next_member = await queries.get_member_by_id(next_id)
    orig_member = await queries.get_member_by_id(orig_id)

    if not next_member or not orig_member:
        await call.answer("A'zo ma'lumoti topilmadi!", show_alert=True)
        return

    # Bazaga bir martalik o'tkazib yuborishni yozamiz
    await queries.set_temp_duty(chat_id, next_member["id"], "skip", orig_member["id"])

    next_tag = f"@{next_member['username']}" if next_member.get("username") else next_member["name"]
    orig_tag = f"@{orig_member['username']}" if orig_member.get("username") else orig_member["name"]

    text = (
        "⏭️ <b>NAVBATCHILIK 1 MARTAGA O'TKAZIB YUBORILDI!</b>\n\n"
        f"👤 <b>Bugungi navbatchi:</b> {next_tag}\n"
        f"<i>({orig_tag} bugungi navbatini 1 martaga o'tkazib yubordi)</i>\n\n"
        f"✨ <i>Keyingi navbatchilikda navbat yana o'z joyiga — <b>{orig_member['name']}</b>ga qaytadi.</i>\n\n"
        "Barcha ma'lumotni ko'rish: /navbatchi"
    )

    await call.message.edit_text(text, reply_markup=None, parse_mode="HTML")
    await call.answer("Navbatchilik o'tkazildi!")

@router.callback_query(F.data == "skip_cancel")
async def callback_skip_cancel(call: CallbackQuery):
    await call.message.edit_text("❌ Navbatchilikni o'tkazib yuborish bekor qilindi.", reply_markup=None)
    await call.answer("Bekor qilindi.")

# ==================== ASLIGA QAYTARISH (/qaytarish) ====================

@router.message(Command("qaytarish"))
@router.message(Command("asliga_qaytarish"))
@router.message(Command("reset_swap"))
async def cmd_qaytarish(message: types.Message):
    """Bir martalik almashtirish yoki o'tkazishni bekor qilib, asl navbatchiga qaytarish."""
    chat_id = message.chat.id
    group = await queries.get_group(chat_id)
    if not group or not group.get("temp_duty_member_id"):
        await message.reply("ℹ️ Hozirda hech qanday vaqtinchalik almashtirish yoki o'tkazish mavjud emas.")
        return

    await queries.clear_temp_duty(chat_id)
    cur_member, _, _ = await get_current_duty_info(chat_id)
    tag = f"@{cur_member['username']}" if cur_member.get("username") else cur_member["name"]

    await message.reply(
        f"🔄 <b>Navbatchilik asl holatiga qaytarildi!</b>\n\n"
        f"👤 Bugungi navbatchi yana: <b>{tag}</b>\n\n"
        f"Barcha ma'lumotni ko'rish: /navbatchi",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "duty_reset_temp")
async def callback_duty_reset_temp(call: CallbackQuery):
    """Navbatchi xabaridan bevosita asliga qaytarish tugmasi."""
    chat_id = call.message.chat.id
    await queries.clear_temp_duty(chat_id)
    cur_member, _, _ = await get_current_duty_info(chat_id)
    tag = f"@{cur_member['username']}" if cur_member.get("username") else cur_member["name"]

    await call.answer("Asl holatiga qaytarildi!")
    await call.message.reply(
        f"🔄 <b>Navbatchilik asl holatiga qaytarildi!</b>\n\n"
        f"👤 Bugungi navbatchi: <b>{tag}</b>",
        parse_mode="HTML"
    )
