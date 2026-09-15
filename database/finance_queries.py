from datetime import datetime
from typing import List, Dict, Optional, Any
from database.db import get_db_connection
from database.queries import get_members

# ==================== KASSA VA XARAJATLAR SO'ROVLARI ====================

async def get_fund_balance(chat_id: int) -> int:
    """Guruh umumiy kassasidagi hozirgi qoldiqni hisoblaydi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as balance FROM fund_transactions WHERE chat_id = ?",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return int(row["balance"]) if row else 0

async def add_fund_income(chat_id: int, member_name: str, amount: int, note: str = "") -> None:
    """Kassaga pul kiritish (Kirim)."""
    if amount <= 0:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO fund_transactions (chat_id, member_name, amount, type, note, created_at)
            VALUES (?, ?, ?, 'income', ?, ?)
        """, (chat_id, member_name, amount, note, now))
        await conn.commit()

async def add_expense(
    chat_id: int,
    title: str,
    amount: int,
    paid_by: str,
    payment_source: str = "fund",
    category: str = "Bozorlik"
) -> None:
    """
    Yangi xarajat kiritish.
    Agar payment_source == 'fund' bo'lsa, avtomatik ravishda kassadan chiqim qilinadi.
    """
    if amount <= 0:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    async with get_db_connection() as conn:
        # Xarajatlar jadvaliga yozish
        await conn.execute("""
            INSERT INTO expenses (chat_id, title, amount, paid_by, payment_source, category, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (chat_id, title, amount, paid_by, payment_source, category, now))

        # Agar kassadan to'langan bo'lsa, kassa harakatlariga manfiy summa yozamiz
        if payment_source == "fund":
            await conn.execute("""
                INSERT INTO fund_transactions (chat_id, member_name, amount, type, note, created_at)
                VALUES (?, ?, ?, 'expense', ?, ?)
            """, (chat_id, paid_by, -amount, title, now))

        await conn.commit()

async def get_recent_expenses(chat_id: int, limit: int = 20) -> List[dict]:
    """Oxirgi xarajatlar ro'yxatini qaytaradi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT * FROM expenses WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_recent_fund_transactions(chat_id: int, limit: int = 15) -> List[dict]:
    """Oxirgi kassa amallari ro'yxatini qaytaradi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT * FROM fund_transactions WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_month_expense_total(chat_id: int, month_prefix: str = "") -> int:
    """Oy davomidagi jami chiqim summasi."""
    if not month_prefix:
        month_prefix = datetime.now().strftime("%Y-%m")
    pattern = f"{month_prefix}%"
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE chat_id = ? AND created_at LIKE ?",
            (chat_id, pattern)
        ) as cursor:
            row = await cursor.fetchone()
            return int(row["total"]) if row else 0

# ==================== IJARA VA TO'LOVLAR SO'ROVLARI ====================

async def get_rent_settings(chat_id: int) -> dict:
    """Guruh ijara sozlamalarini oladi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT * FROM rent_settings WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return {
                "chat_id": chat_id,
                "total_amount": 0,
                "currency": "UZS",
                "due_day": 5,
                "notify_days": 3
            }

async def update_rent_settings(chat_id: int, total_amount: int, due_day: int = 5) -> None:
    """Guruh ijara sozlamalarini yangilaydi."""
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO rent_settings (chat_id, total_amount, currency, due_day)
            VALUES (?, ?, 'UZS', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                total_amount = excluded.total_amount,
                due_day = excluded.due_day
        """, (chat_id, total_amount, due_day))
        await conn.commit()

async def get_rent_status_for_month(chat_id: int, month_year: str = "") -> List[dict]:
    """
    Belgilangan oy uchun har bir a'zoning ijara to'lov holatini qaytaradi.
    """
    if not month_year:
        month_year = datetime.now().strftime("%Y-%m")

    members = await get_members(chat_id)
    if not members:
        return []

    settings = await get_rent_settings(chat_id)
    total_rent = settings.get("total_amount", 0)
    per_person = total_rent // len(members) if members else 0

    results = []
    async with get_db_connection() as conn:
        for m in members:
            name = m["name"]
            async with conn.execute("""
                SELECT * FROM rent_payments
                WHERE chat_id = ? AND month_year = ? AND member_name = ?
            """, (chat_id, month_year, name)) as cursor:
                payment = await cursor.fetchone()

            if payment:
                p_dict = dict(payment)
                results.append({
                    "member_name": name,
                    "username": m.get("username", ""),
                    "amount": p_dict.get("amount") or per_person,
                    "is_paid": bool(p_dict.get("is_paid", 0)),
                    "paid_at": p_dict.get("paid_at", "")
                })
            else:
                # Agar hali yozuv bo'lmasa, dastlabki holat
                results.append({
                    "member_name": name,
                    "username": m.get("username", ""),
                    "amount": per_person,
                    "is_paid": False,
                    "paid_at": ""
                })

    return results

async def toggle_rent_payment(chat_id: int, month_year: str, member_name: str, amount: int = 0) -> bool:
    """Xonadoshning joriy oy uchun ijara to'lov holatini teskarisiga o'zgartiradi."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    async with get_db_connection() as conn:
        async with conn.execute("""
            SELECT * FROM rent_payments
            WHERE chat_id = ? AND month_year = ? AND member_name = ?
        """, (chat_id, month_year, member_name)) as cursor:
            row = await cursor.fetchone()

        if row:
            new_status = 0 if row["is_paid"] else 1
            paid_at = now if new_status else ""
            await conn.execute("""
                UPDATE rent_payments
                SET is_paid = ?, paid_at = ?
                WHERE chat_id = ? AND month_year = ? AND member_name = ?
            """, (new_status, paid_at, chat_id, month_year, member_name))
        else:
            new_status = 1
            await conn.execute("""
                INSERT INTO rent_payments (chat_id, month_year, member_name, amount, is_paid, paid_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (chat_id, month_year, member_name, amount, now))

        await conn.commit()
        return bool(new_status)

# ==================== BOZORLIK RO'YXATI SO'ROVLARI ====================

async def get_shopping_items(chat_id: int) -> List[dict]:
    """Bozorlik ro'yxatini qaytaradi (avval olinmaganlar, keyin olinganlar)."""
    async with get_db_connection() as conn:
        async with conn.execute("""
            SELECT * FROM shopping_items
            WHERE chat_id = ?
            ORDER BY is_bought ASC, id DESC
        """, (chat_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def add_shopping_item(chat_id: int, title: str, added_by: str = "") -> int:
    """Bozorlik ro'yxatiga yangi mahsulot qo'shish."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    async with get_db_connection() as conn:
        cursor = await conn.execute("""
            INSERT INTO shopping_items (chat_id, title, is_bought, added_by, created_at)
            VALUES (?, ?, 0, ?, ?)
        """, (chat_id, title, added_by, now))
        await conn.commit()
        return cursor.lastrowid

async def toggle_shopping_item(item_id: int, chat_id: int) -> bool:
    """Mahsulotni olingan/olinmagan deb belgilash."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT is_bought FROM shopping_items WHERE id = ? AND chat_id = ?",
            (item_id, chat_id)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            new_status = 1 if row["is_bought"] == 0 else 0

        await conn.execute(
            "UPDATE shopping_items SET is_bought = ? WHERE id = ? AND chat_id = ?",
            (new_status, item_id, chat_id)
        )
        await conn.commit()
        return bool(new_status)

async def delete_shopping_item(item_id: int, chat_id: int) -> None:
    """Mahsulotni ro'yxatdan o'chirish."""
    async with get_db_connection() as conn:
        await conn.execute(
            "DELETE FROM shopping_items WHERE id = ? AND chat_id = ?",
            (item_id, chat_id)
        )
        await conn.commit()

async def clear_bought_shopping_items(chat_id: int) -> None:
    """Barcha olingan (galochka qo'yilgan) mahsulotlarni tozalash."""
    async with get_db_connection() as conn:
        await conn.execute(
            "DELETE FROM shopping_items WHERE chat_id = ? AND is_bought = 1",
            (chat_id,)
        )
        await conn.commit()
