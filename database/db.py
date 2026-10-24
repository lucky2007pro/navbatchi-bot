from contextlib import asynccontextmanager
import aiosqlite
import logging
from config import DB_PATH, DEFAULT_NOTIFY_TIME, DEFAULT_WORK_DAYS

logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_db_connection():
    """Ma'lumotlar bazasiga asinxron ulanish konteksti."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn

async def init_db():
    """Barcha kerakli jadvallarni yaratadi."""
    async with get_db_connection() as conn:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                notify_time TEXT DEFAULT '{DEFAULT_NOTIFY_TIME}',
                work_days TEXT DEFAULT '{DEFAULT_WORK_DAYS}',
                current_index INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                last_notified_date TEXT DEFAULT '',
                temp_duty_member_id INTEGER DEFAULT NULL,
                temp_duty_type TEXT DEFAULT NULL,
                temp_duty_original_id INTEGER DEFAULT NULL
            )
        """)

        # groups jadvaliga yangi ustunlarni xavfsiz qo'shish (migratsiya)
        for col_name, col_type in [
            ("temp_duty_member_id", "INTEGER DEFAULT NULL"),
            ("temp_duty_type", "TEXT DEFAULT NULL"),
            ("temp_duty_original_id", "INTEGER DEFAULT NULL")
        ]:
            try:
                await conn.execute(f"ALTER TABLE groups ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        # Navbatchilikni almashtirish takliflari jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS duty_swap_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                from_member_id INTEGER NOT NULL,
                to_member_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES groups (chat_id) ON DELETE CASCADE
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS duty_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                order_num INTEGER NOT NULL,
                name TEXT NOT NULL,
                username TEXT DEFAULT '',
                FOREIGN KEY (chat_id) REFERENCES groups (chat_id) ON DELETE CASCADE
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS duty_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                order_num INTEGER NOT NULL,
                task_text TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES groups (chat_id) ON DELETE CASCADE
            )
        """)

        # 1. Kassa harakatlari (Kirim / Chiqim)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                member_name TEXT NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES groups (chat_id) ON DELETE CASCADE
            )
        """)

        # 2. Xarajatlar (Chiqimlar tarixi)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                amount INTEGER NOT NULL,
                paid_by TEXT NOT NULL,
                payment_source TEXT DEFAULT 'fund',
                category TEXT DEFAULT 'Bozorlik',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES groups (chat_id) ON DELETE CASCADE
            )
        """)

        # 3. Ijara sozlamalari
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rent_settings (
                chat_id INTEGER PRIMARY KEY,
                total_amount INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'UZS',
                due_day INTEGER DEFAULT 5,
                notify_days INTEGER DEFAULT 3,
                FOREIGN KEY (chat_id) REFERENCES groups (chat_id) ON DELETE CASCADE
            )
        """)

        # 4. Oylik ijara to'lovlari (Kim to'ladi / to'lamadi)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rent_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                month_year TEXT NOT NULL,
                member_name TEXT NOT NULL,
                amount INTEGER DEFAULT 0,
                is_paid INTEGER DEFAULT 0,
                paid_at TEXT DEFAULT '',
                FOREIGN KEY (chat_id) REFERENCES groups (chat_id) ON DELETE CASCADE
            )
        """)

        # 5. Bozorlik ro'yxati (Shopping list)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shopping_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                is_bought INTEGER DEFAULT 0,
                added_by TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES groups (chat_id) ON DELETE CASCADE
            )
        """)

        await conn.commit()
    logger.info("Ma'lumotlar bazasi jadvallari muvaffaqiyatli ishga tushirildi.")
