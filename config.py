import os
from pathlib import Path
from dotenv import load_dotenv

# .env faylini yuklash
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "navbatchilik.db"))
DEFAULT_NOTIFY_TIME = os.getenv("DEFAULT_NOTIFY_TIME", "08:00")
DEFAULT_WORK_DAYS = os.getenv("DEFAULT_WORK_DAYS", "workdays_sat")

# Vaqt mintaqasi (O'zbekiston uchun Asia/Tashkent)
TIMEZONE = "Asia/Tashkent"

# Telegram Web App sozlamalari
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8080"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8080")
