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
                last_notified_date TEXT DEFAULT ''
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

        await conn.commit()
    logger.info("Ma'lumotlar bazasi jadvallari muvaffaqiyatli ishga tushirildi.")
