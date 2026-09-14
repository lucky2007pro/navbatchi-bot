from typing import List, Dict, Optional, Tuple
from database.db import get_db_connection
from config import DEFAULT_NOTIFY_TIME, DEFAULT_WORK_DAYS

# ==================== GURUHLAR BO'YICHA SO'ROVLAR ====================

async def register_or_update_group(chat_id: int, chat_title: str) -> None:
    """Guruhni bazaga qo'shadi yoki nomini yangilaydi."""
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO groups (chat_id, chat_title, notify_time, work_days)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                chat_title = excluded.chat_title
        """, (chat_id, chat_title, DEFAULT_NOTIFY_TIME, DEFAULT_WORK_DAYS))
        await conn.commit()

async def get_group(chat_id: int) -> Optional[dict]:
    """Guruh ma'lumotlarini oladi."""
    async with get_db_connection() as conn:
        async with conn.execute("SELECT * FROM groups WHERE chat_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_all_active_groups() -> List[dict]:
    """Barcha faol guruhlar ro'yxatini qaytaradi."""
    async with get_db_connection() as conn:
        async with conn.execute("SELECT * FROM groups WHERE is_active = 1") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def update_group_settings(
    chat_id: int,
    notify_time: Optional[str] = None,
    work_days: Optional[str] = None,
    is_active: Optional[int] = None
) -> None:
    """Guruh sozlamalarini yangilaydi."""
    async with get_db_connection() as conn:
        updates = []
        params = []
        if notify_time is not None:
            updates.append("notify_time = ?")
            params.append(notify_time)
        if work_days is not None:
            updates.append("work_days = ?")
            params.append(work_days)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)

        if updates:
            params.append(chat_id)
            query = f"UPDATE groups SET {', '.join(updates)} WHERE chat_id = ?"
            await conn.execute(query, tuple(params))
            await conn.commit()

async def update_group_index(chat_id: int, new_index: int, last_date: Optional[str] = None) -> None:
    """Hozirgi navbatchi indeksini va oxirgi bildirishnoma sanasini yangilaydi."""
    async with get_db_connection() as conn:
        if last_date:
            await conn.execute("""
                UPDATE groups SET current_index = ?, last_notified_date = ? WHERE chat_id = ?
            """, (new_index, last_date, chat_id))
        else:
            await conn.execute("""
                UPDATE groups SET current_index = ? WHERE chat_id = ?
            """, (new_index, chat_id))
        await conn.commit()

# ==================== NAVBATCHILAR BO'YICHA SO'ROVLAR ====================

async def set_members(chat_id: int, members: List[Dict[str, str]]) -> None:
    """
    Guruh navbatchilar ro'yxatini yangilaydi.
    members = [{"name": "Ali", "username": "ali"}, ...]
    """
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM duty_members WHERE chat_id = ?", (chat_id,))
        for idx, m in enumerate(members, start=1):
            await conn.execute("""
                INSERT INTO duty_members (chat_id, order_num, name, username)
                VALUES (?, ?, ?, ?)
            """, (chat_id, idx, m.get("name", ""), m.get("username", "")))
        # Yangi ro'yxat kiritilganda navbatni boshidan boshlash
        await conn.execute("UPDATE groups SET current_index = 0 WHERE chat_id = ?", (chat_id,))
        await conn.commit()

async def get_members(chat_id: int) -> List[dict]:
    """Guruh navbatchilar ro'yxatini tartib bilan qaytaradi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT * FROM duty_members WHERE chat_id = ? ORDER BY order_num ASC", (chat_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def clear_members(chat_id: int) -> None:
    """Guruh navbatchilarini o'chiradi."""
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM duty_members WHERE chat_id = ?", (chat_id,))
        await conn.execute("UPDATE groups SET current_index = 0 WHERE chat_id = ?", (chat_id,))
        await conn.commit()

# ==================== VAZIFALAR BO'YICHA SO'ROVLAR ====================

async def set_tasks(chat_id: int, tasks: List[str]) -> None:
    """
    Guruh kunlik vazifalar ro'yxatini yangilaydi.
    tasks = ["1-vazifa", "2-vazifa", ...]
    """
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM duty_tasks WHERE chat_id = ?", (chat_id,))
        for idx, task in enumerate(tasks, start=1):
            await conn.execute("""
                INSERT INTO duty_tasks (chat_id, order_num, task_text)
                VALUES (?, ?, ?)
            """, (chat_id, idx, task))
        await conn.commit()

async def get_tasks(chat_id: int) -> List[dict]:
    """Guruh vazifalar ro'yxatini tartib bilan qaytaradi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT * FROM duty_tasks WHERE chat_id = ? ORDER BY order_num ASC", (chat_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def clear_tasks(chat_id: int) -> None:
    """Guruh vazifalarini o'chiradi."""
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM duty_tasks WHERE chat_id = ?", (chat_id,))
        await conn.commit()
