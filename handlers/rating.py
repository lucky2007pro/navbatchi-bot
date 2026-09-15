import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

from database import rating_queries, queries
from handlers.common import get_webapp_keyboard

logger = logging.getLogger(__name__)

router = Router()

def get_rating_keyboard(rating_id: int, likes: int = 0, dislikes: int = 0, is_closed: bool = False) -> InlineKeyboardMarkup:
    """Baholash uchun anonim Like va Dislike tugmalarini yaratadi."""
    builder = InlineKeyboardBuilder()
    if is_closed:
        builder.button(text=f"👍 {likes}", callback_data="rate:closed")
        builder.button(text=f"👎 {dislikes}", callback_data="rate:closed")
    else:
        builder.button(text=f"👍 {likes}", callback_data=f"rate:like:{rating_id}")
        builder.button(text=f"👎 {dislikes}", callback_data=f"rate:dislike:{rating_id}")
    builder.adjust(2)
    return builder.as_markup()

def build_rating_poll_text(member_name: str, duty_date: str) -> str:
    """Baholash xabari matni."""
    return (
        f"🧹 <b>NAVBATCHILIKNI BAHOLASH VAQTI!</b> 🗳\n\n"
        f"👤 Navbatchi: <b>{member_name}</b>\n"
        f"📅 Sana: <b>{duty_date}</b>\n\n"
        f"Xonadoshlar, navbatchilik qanday bajarildi? Oshxona, xonalar tozaligi va tartib ma'qul bo'ldimi?\n\n"
        f"<i>🔒 Ovoz berish 100% anonim — kim qanday baholagani hech kimga ko'rsatilmaydi!</i>"
    )

@router.callback_query(F.data == "rate:closed")
async def cb_rate_closed(callback: types.CallbackQuery):
    """Yopilgan ovoz berish xabarnomasi."""
    await callback.answer("🔒 Bu navbatchilik uchun ovoz berish yakunlangan.", show_alert=True)

@router.callback_query(F.data.startswith("rate:like:") | F.data.startswith("rate:dislike:"))
async def cb_vote(callback: types.CallbackQuery):
    """Like yoki Dislike bosilganda anonim hisobga olish."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    vote_type = parts[1]  # 'like' or 'dislike'
    try:
        rating_id = int(parts[2])
    except ValueError:
        await callback.answer("Noto'g'ri ID.", show_alert=True)
        return

    rating = await rating_queries.get_rating_session(rating_id)
    if not rating:
        await callback.answer("⚠️ Baholash sessiyasi topilmadi.", show_alert=True)
        return

    if rating.get("is_closed"):
        await callback.answer("🔒 Bu navbatchilik uchun ovoz berish vaqti tugagan.", show_alert=True)
        return

    from_user = callback.from_user
    member_name = (rating.get("member_name") or "").strip()

    # Navbatchining o'zi o'ziga ovoz berishini oldini olish
    user_username = (from_user.username or "").lower().replace("@", "")
    user_first_name = (from_user.first_name or "").lower()
    user_full_name = (from_user.full_name or "").lower()
    target_clean = member_name.lower().replace("@", "").strip()

    is_self = False
    if user_username and user_username == target_clean:
        is_self = True
    elif target_clean and (target_clean == user_first_name or target_clean == user_full_name):
        is_self = True

    # Shuningdek guruh a'zolar ro'yxatidan ham tekshiramiz
    if not is_self and rating.get("chat_id"):
        members = await queries.get_members(rating["chat_id"])
        for m in members:
            m_name = m.get("name", "").strip().lower()
            m_user = m.get("username", "").strip().lower().replace("@", "")
            if (m_name == target_clean or (m_user and m_user == target_clean)):
                if user_username and m_user and user_username == m_user:
                    is_self = True
                    break
                if user_full_name and m_name and (user_full_name == m_name or user_first_name == m_name):
                    is_self = True
                    break

    if is_self:
        await callback.answer("❌ O'zingizning navbatchiligingizga ovoz bera olmaysiz! 😊", show_alert=True)
        return

    # Anonim ovoz berish
    changed, status, likes, dislikes = await rating_queries.cast_vote(rating_id, from_user.id, vote_type)

    if status == "already":
        await callback.answer(f"Ovozingiz allaqachon hisobga olingan! ({'👍' if vote_type == 'like' else '👎'})", show_alert=False)
        return

    if status == "changed":
        await callback.answer(f"✅ Ovozingiz {'👍 Like' if vote_type == 'like' else '👎 Dislike'}ga o'zgartirildi!", show_alert=False)
    else:
        await callback.answer(f"✅ Anonim bahoyingiz qabul qilindi ({'👍' if vote_type == 'like' else '👎'})!", show_alert=False)

    # Xabardagi tugma sonlarini yangilash
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_rating_keyboard(rating_id, likes, dislikes)
        )
    except TelegramBadRequest:
        pass

@router.message(Command("reyting"))
async def cmd_reyting(message: types.Message):
    """Xonadoshlar navbatchilik reytingi (Liderlar jadvali)."""
    if message.chat.type == ChatType.PRIVATE:
        await message.answer("ℹ️ Bu buyruq faqat guruhlarda ishlaydi. Botni kvartira guruhiga qo'shing.")
        return

    leaderboard = await rating_queries.get_member_ratings_leaderboard(message.chat.id)
    if not leaderboard:
        await message.answer(
            "📊 <b>Guruhda hali navbatchiliklar baholanmagan!</b>\n\n"
            "Har kuni navbatchilik almashishidan 1 soat oldin guruhga avtomatik baholash so'rovi yuboriladi.",
            reply_markup=get_webapp_keyboard(message.chat.id),
            parse_mode="HTML"
        )
        return

    lines = [
        f"🏆 <b>'{message.chat.title}' GURUHI NAVBATCHILIK REYTINGI:</b>",
        ""
    ]

    medals = ["🥇", "🥈", "🥉"]
    for idx, item in enumerate(leaderboard):
        badge = medals[idx] if idx < 3 else f"<b>{idx + 1}.</b>"
        name = item["member_name"]
        likes = item["total_likes"]
        dislikes = item["total_dislikes"]
        duties = item["total_duties"]
        rate = item["approval_rate"]

        lines.append(
            f"{badge} <b>{name}</b> ({duties} ta navbatchilik)\n"
            f"   👍 {likes} ta  |  👎 {dislikes} ta  —  <i>{rate}% ijobiy</i>"
        )

    lines.append("")
    lines.append("<i>🔒 Barcha baholar 100% anonim hisoblanadi.</i>")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_webapp_keyboard(message.chat.id),
        parse_mode="HTML"
    )
