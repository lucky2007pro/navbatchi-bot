import logging
from typing import Optional, List, Dict, Tuple
from database.db import get_db_connection

logger = logging.getLogger(__name__)

async def create_rating_session(chat_id: int, member_name: str, duty_date: str) -> int:
    """Yangi navbatchilikni baholash sessiyasini yaratadi."""
    async with get_db_connection() as conn:
        cursor = await conn.execute("""
            INSERT INTO duty_ratings (chat_id, member_name, duty_date, likes_count, dislikes_count, is_closed)
            VALUES (?, ?, ?, 0, 0, 0)
        """, (chat_id, member_name, duty_date))
        await conn.commit()
        return cursor.lastrowid

async def get_rating_session(rating_id: int) -> Optional[dict]:
    """Baholash sessiyasi ma'lumotlarini oladi."""
    async with get_db_connection() as conn:
        async with conn.execute("SELECT * FROM duty_ratings WHERE id = ?", (rating_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_active_rating(chat_id: int) -> Optional[dict]:
    """Guruhdagi ayni damdagi yopilmagan (faol) baholash sessiyasini oladi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT * FROM duty_ratings WHERE chat_id = ? AND is_closed = 0 ORDER BY id DESC LIMIT 1",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def update_rating_message_id(rating_id: int, message_id: int) -> None:
    """Telegramda yuborilgan so'rovnoma xabari ID sini saqlaydi."""
    async with get_db_connection() as conn:
        await conn.execute("UPDATE duty_ratings SET message_id = ? WHERE id = ?", (message_id, rating_id))
        await conn.commit()

async def cast_vote(rating_id: int, user_id: int, vote_type: str) -> Tuple[bool, str, int, int]:
    """
    Anonim ovoz berish (Like yoki Dislike).
    Qaytaradi: (o'zgardi_yoki_yangi: bool, holat_matni: str, likes_soni: int, dislikes_soni: int)
    """
    async with get_db_connection() as conn:
        # Avvalgi ovozini tekshiramiz
        async with conn.execute(
            "SELECT vote_type FROM duty_votes WHERE rating_id = ? AND user_id = ?",
            (rating_id, user_id)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing and existing["vote_type"] == vote_type:
            # Allaqachon xuddi shu tugmani bosgan
            # Joriy hisobni qaytaramiz
            async with conn.execute("SELECT likes_count, dislikes_count FROM duty_ratings WHERE id = ?", (rating_id,)) as c:
                r = await c.fetchone()
                likes = r["likes_count"] if r else 0
                dislikes = r["dislikes_count"] if r else 0
            return False, "already", likes, dislikes

        status = "changed" if existing else "new"

        # Ovozni kiritish yoki yangilash
        await conn.execute("""
            INSERT INTO duty_votes (rating_id, user_id, vote_type)
            VALUES (?, ?, ?)
            ON CONFLICT(rating_id, user_id) DO UPDATE SET vote_type = excluded.vote_type
        """, (rating_id, user_id, vote_type))

        # Like va Dislike sonini qayta hisoblash
        async with conn.execute(
            "SELECT COUNT(*) as cnt FROM duty_votes WHERE rating_id = ? AND vote_type = 'like'",
            (rating_id,)
        ) as c_like:
            row_like = await c_like.fetchone()
            likes_count = row_like["cnt"] if row_like else 0

        async with conn.execute(
            "SELECT COUNT(*) as cnt FROM duty_votes WHERE rating_id = ? AND vote_type = 'dislike'",
            (rating_id,)
        ) as c_dis:
            row_dis = await c_dis.fetchone()
            dislikes_count = row_dis["cnt"] if row_dis else 0

        await conn.execute(
            "UPDATE duty_ratings SET likes_count = ?, dislikes_count = ? WHERE id = ?",
            (likes_count, dislikes_count, rating_id)
        )
        await conn.commit()

        return True, status, likes_count, dislikes_count

async def close_rating_session(rating_id: int) -> Optional[dict]:
    """Baholash sessiyasini yopadi va oxirgi natijani qaytaradi."""
    async with get_db_connection() as conn:
        await conn.execute("UPDATE duty_ratings SET is_closed = 1 WHERE id = ?", (rating_id,))
        await conn.commit()
        async with conn.execute("SELECT * FROM duty_ratings WHERE id = ?", (rating_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_last_closed_rating(chat_id: int) -> Optional[dict]:
    """Oxirgi yopilgan baholash sessiyasini qaytaradi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT * FROM duty_ratings WHERE chat_id = ? AND is_closed = 1 ORDER BY id DESC LIMIT 1",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def is_today_rating_sent(chat_id: int, duty_date: str) -> bool:
    """Bugungi sana uchun baholash so'rovi allaqachon yuborilganligini tekshiradi."""
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT 1 FROM duty_ratings WHERE chat_id = ? AND duty_date = ? LIMIT 1",
            (chat_id, duty_date)
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def get_member_ratings_leaderboard(chat_id: int) -> List[dict]:
    """Guruh a'zolarining umumiy navbatchilik reytingini (Liderlar jadvali) qaytaradi."""
    async with get_db_connection() as conn:
        query = """
            SELECT 
                member_name,
                COALESCE(SUM(likes_count), 0) as total_likes,
                COALESCE(SUM(dislikes_count), 0) as total_dislikes,
                COUNT(id) as total_duties
            FROM duty_ratings
            WHERE chat_id = ?
            GROUP BY member_name
            ORDER BY total_likes DESC, total_dislikes ASC
        """
        async with conn.execute(query, (chat_id,)) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                total_votes = d["total_likes"] + d["total_dislikes"]
                approval_rate = round((d["total_likes"] / total_votes) * 100) if total_votes > 0 else 100
                d["approval_rate"] = approval_rate
                result.append(d)
            return result
