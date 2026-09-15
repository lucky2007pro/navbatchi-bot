from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.enums import ChatType

from database import finance_queries, queries
from handlers.common import get_webapp_keyboard

router = Router()

@router.message(Command("kassa"))
async def cmd_kassa(message: types.Message):
    """Umumiy kassa qoldig'i va oylik xarajatlar haqida ma'lumot."""
    chat_id = message.chat.id
    balance = await finance_queries.get_fund_balance(chat_id)
    month_total = await finance_queries.get_month_expense_total(chat_id)
    recent_expenses = await finance_queries.get_recent_expenses(chat_id, limit=5)

    lines = [
        "💰 <b>KVARTIRA KASSASI VA XARAJATLAR:</b>",
        "",
        f"💵 <b>Kassa qoldig'i:</b> <code>{balance:,} so'm</code>",
        f"📊 <b>Bu oylik jami chiqim:</b> <code>{month_total:,} so'm</code>",
        ""
    ]

    if recent_expenses:
        lines.append("📝 <b>Oxirgi xarajatlar:</b>")
        for idx, exp in enumerate(recent_expenses, start=1):
            source_icon = "💰" if exp.get("payment_source") == "fund" else "👤"
            lines.append(
                f"  {idx}. <b>{exp['title']}</b> — {exp['amount']:,} so'm "
                f"<i>({source_icon} {exp['paid_by']})</i>"
            )
    else:
        lines.append("<i>Hozircha xarajatlar kiritilmagan.</i>")

    lines.append("")
    lines.append("💡 <i>Tezkor xarajat yozish: /xarajat 45000 Go'sht</i>")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_webapp_keyboard(chat_id),
        parse_mode="HTML"
    )

@router.message(Command("xarajat"))
async def cmd_xarajat(message: types.Message):
    """Tezkor xarajat yozish: /xarajat <summa> <nomi>"""
    chat_id = message.chat.id
    args = message.text.partition(" ")[2].strip()

    if not args:
        await message.reply(
            "✍️ <b>Xarajat kiritish namunasi:</b>\n"
            "<code>/xarajat 50000 Go'sht va sabzi</code>\n"
            "<code>/xarajat 15000 Non va tuxum</code>\n\n"
            "Yoki to'liq Web App orqali boshqaring:",
            reply_markup=get_webapp_keyboard(chat_id),
            parse_mode="HTML"
        )
        return

    parts = args.split(" ", 1)
    try:
        amount = int(parts[0].replace(",", "").replace(".", "").replace(" ", ""))
        title = parts[1].strip() if len(parts) > 1 else "Noma'lum xarid"
    except ValueError:
        await message.reply("⚠️ Summa noto'g'ri kiritildi. Masalan: <code>/xarajat 50000 Go'sht</code>", parse_mode="HTML")
        return

    paid_by = message.from_user.full_name or message.from_user.first_name or "Xonadosh"

    # Xarajatni kassadan to'langan deb bazaga yozamiz
    await finance_queries.add_expense(
        chat_id=chat_id,
        title=title,
        amount=amount,
        paid_by=paid_by,
        payment_source="fund",
        category="Bozorlik"
    )

    new_balance = await finance_queries.get_fund_balance(chat_id)

    text = (
        f"✅ <b>Xarajat muvaffaqiyatli saqlandi!</b>\n\n"
        f"🛒 <b>Nomi:</b> {title}\n"
        f"💸 <b>Summa:</b> {amount:,} so'm\n"
        f"👤 <b>Kiritdi:</b> {paid_by}\n\n"
        f"💰 <b>Kassada qoldi:</b> {new_balance:,} so'm"
    )

    await message.answer(
        text,
        reply_markup=get_webapp_keyboard(chat_id),
        parse_mode="HTML"
    )

@router.message(Command("ijara"))
async def cmd_ijara(message: types.Message):
    """Ijara holati va to'lovlar monitoringi."""
    chat_id = message.chat.id
    settings = await finance_queries.get_rent_settings(chat_id)
    total_amount = settings.get("total_amount", 0)
    due_day = settings.get("due_day", 5)

    month_str = datetime.now().strftime("%Y-%m")
    status_list = await finance_queries.get_rent_status_for_month(chat_id, month_str)

    lines = [
        f"🏠 <b>KVARTIRA IJARASI ({datetime.now().strftime('%B %Y')}):</b>",
        "",
        f"💵 <b>Oylik ijara:</b> {total_amount:,} so'm",
        f"📅 <b>To'lov sanasi:</b> Har oyning {due_day}-kuni",
        ""
    ]

    if status_list:
        lines.append("👥 <b>Xonadoshlar to'lov holati:</b>")
        for m in status_list:
            icon = "✅" if m["is_paid"] else "⏳"
            status_text = "To'langan" if m["is_paid"] else "Kutilmoqda"
            lines.append(f"  {icon} <b>{m['member_name']}</b>: {m['amount']:,} so'm ({status_text})")
    else:
        lines.append("<i>Navbatchilar ro'yxatida xonadoshlar kiritilmagan.</i>")

    lines.append("")
    lines.append("📱 <i>Boshqarish va belgilash uchun Web App'ni oching:</i>")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_webapp_keyboard(chat_id),
        parse_mode="HTML"
    )

@router.message(Command("bozorlik"))
async def cmd_bozorlik(message: types.Message):
    """Bozorlik ro'yxatini ko'rish."""
    chat_id = message.chat.id
    items = await finance_queries.get_shopping_items(chat_id)

    lines = [
        "🛒 <b>BOZORLIK RO'YXATI:</b>",
        ""
    ]

    pending = [i for i in items if not i["is_bought"]]
    bought = [i for i in items if i["is_bought"]]

    if pending:
        lines.append("📌 <b>Olinishi kerak:</b>")
        for idx, i in enumerate(pending, start=1):
            lines.append(f"  ◻️ {idx}. {i['title']}")
    else:
        lines.append("✨ <i>Hamma narsa olingan yoki ro'yxat bo'sh!</i>")

    if bought:
        lines.append("")
        lines.append("✅ <b>Olinganlar:</b>")
        for idx, i in enumerate(bought, start=1):
            lines.append(f"  <s>{i['title']}</s>")

    lines.append("")
    lines.append("➕ <i>Yangi mahsulot qo'shish: /bozorlik_qosh <nomi></i>")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_webapp_keyboard(chat_id),
        parse_mode="HTML"
    )

@router.message(Command("bozorlik_qosh"))
async def cmd_bozorlik_qosh(message: types.Message):
    """Bozorlikka yangi narsa qo'shish: /bozorlik_qosh <nomi>"""
    chat_id = message.chat.id
    title = message.text.partition(" ")[2].strip()

    if not title:
        await message.reply("✍️ Mahsulot nomini yozing. Masalan: <code>/bozorlik_qosh Yog' va kartoshka</code>", parse_mode="HTML")
        return

    sender = message.from_user.first_name or "Xonadosh"
    await finance_queries.add_shopping_item(chat_id, title, added_by=sender)

    await message.answer(
        f"✅ <b>Bozorlik ro'yxatiga qo'shildi:</b> {title}",
        reply_markup=get_webapp_keyboard(chat_id),
        parse_mode="HTML"
    )
