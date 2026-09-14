import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN
from database.db import init_db
from handlers import common, group, admin
from services.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("NavbatchilikBot")

async def setup_bot_commands(bot: Bot):
    """Telegram menyusiga bot buyruqlarini o'rnatish."""
    commands = [
        BotCommand(command="navbatchi", description="Bugungi navbatchi va vazifalar"),
        BotCommand(command="jadval", description="To'liq navbatchilar jadvali"),
        BotCommand(command="vazifalar", description="Kunlik vazifalar ro'yxati"),
        BotCommand(command="navbatchilar", description="[Admin] Navbatchilar ro'yxatini kiritish"),
        BotCommand(command="vazifalar_sozlash", description="[Admin] Kunlik vazifalarni kiritish"),
        BotCommand(command="keyingi", description="[Admin] Navbatni keyingi a'zoga surish"),
        BotCommand(command="vaqt", description="[Admin] Eslatma vaqtini belgilash"),
        BotCommand(command="kunlar", description="[Admin] Ish kunlarini sozlash"),
        BotCommand(command="holat", description="[Admin] Guruh sozlamalari"),
        BotCommand(command="help", description="Qo'llanma va yordam"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error(
            "\n" + "="*60 + "\n"
            "XATOLIK: BOT_TOKEN aniqlanmadi!\n"
            "Iltimos, '.env' faylini oching va Telegram @BotFather dan\n"
            "olingan tokenni 'BOT_TOKEN=' qatoriga kiriting.\n"
            "="*60 + "\n"
        )
        return

    # 1. Ma'lumotlar bazasini initsializatsiya qilish
    logger.info("Ma'lumotlar bazasi ishga tushirilmoqda...")
    await init_db()

    # 2. Bot va Dispatcher yaratish
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 3. Routerlarni ulash (tartib muhim: admin, group, common)
    dp.include_router(admin.router)
    dp.include_router(group.router)
    dp.include_router(common.router)

    # 4. APScheduler rejalashtiruvchisini ishga tushirish
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler muvaffaqiyatli ishga tushirildi.")

    # 5. Buyruqlar menyusini sozlash
    try:
        await setup_bot_commands(bot)
    except Exception as e:
        logger.warning(f"Buyruqlarni menyuga o'rnatishda xatolik: {e}")

    # 6. Eski yangilanishlarni tashlab yuborish va pollingni boshlash
    logger.info("Bot ishga tushdi va xabarlarni kutmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
