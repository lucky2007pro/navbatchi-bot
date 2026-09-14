import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import TIMEZONE
from database import queries
from services.duty_manager import build_duty_message, advance_to_next_duty

logger = logging.getLogger(__name__)

tz = ZoneInfo(TIMEZONE)

def is_work_day(work_days_setting: str, weekday: int) -> bool:
    """
    weekday: 0=Dushanba, 1=Seshanba, ..., 5=Shanba, 6=Yakshanba
    """
    if work_days_setting == "all":
        return True
    elif work_days_setting == "workdays":
        return weekday < 5  # Dush-Juma (0,1,2,3,4)
    elif work_days_setting == "workdays_sat":
        return weekday < 6  # Dush-Shanba (0,1,2,3,4,5)
    return True

async def check_and_send_scheduled_duties(bot: Bot) -> None:
    """
    Har daqiqada barcha faol guruhlarni tekshiradi va vaqti kelganlariga
    navbatchilik xabarini yuborib pin qiladi.
    """
    try:
        now = datetime.now(tz)
        current_time_str = now.strftime("%H:%M")
        current_date_str = now.strftime("%Y-%m-%d")
        current_weekday = now.weekday()

        active_groups = await queries.get_all_active_groups()

        for group in active_groups:
            chat_id = group["chat_id"]
            notify_time = group.get("notify_time", "08:00")
            work_days = group.get("work_days", "workdays_sat")
            last_date = group.get("last_notified_date", "")

            # Vaqti to'g'ri keladimi?
            if notify_time != current_time_str:
                continue

            # Bugun allaqachon yuborilganmi?
            if last_date == current_date_str:
                continue

            # Bugun ish kunimi?
            if not is_work_day(work_days, current_weekday):
                continue

            # Xabarni shakllantirish
            message_text = await build_duty_message(chat_id, is_automatic=True)
            if not message_text:
                logger.info(f"Guruh {chat_id} uchun navbatchilar ro'yxati bo'sh, xabar yuborilmadi.")
                continue

            try:
                # Guruhga yuborish
                sent_msg = await bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    parse_mode="HTML"
                )

                # Xabarni qadash (pin)
                try:
                    await bot.pin_chat_message(
                        chat_id=chat_id,
                        message_id=sent_msg.message_id,
                        disable_notification=False
                    )
                except TelegramBadRequest as pin_err:
                    logger.warning(f"Guruhda {chat_id} xabarni pin qilishga ruxsat yo'q: {pin_err}")

                # Navbatni keyingi a'zoga siljitish va sanani saqlash
                await advance_to_next_duty(chat_id, notify_date=current_date_str)
                logger.info(f"Guruh {chat_id} ga navbatchilik xabari muvaffaqiyatli yuborildi va pin qilindi.")

            except TelegramForbiddenError:
                logger.warning(f"Bot guruhdan {chat_id} chiqarilgan yoki bloklangan.")
            except Exception as send_err:
                logger.error(f"Guruh {chat_id} ga xabar yuborishda xatolik: {send_err}")

    except Exception as e:
        logger.error(f"check_and_send_scheduled_duties da xatolik: {e}", exc_info=True)

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    APScheduler rejalashtiruvchisini ishga tushiradi va har daqiqada tekshiruv qo'shadi.
    """
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        check_and_send_scheduled_duties,
        "cron",
        second=0,  # Har daqiqaning 0-soniyasida
        args=[bot],
        id="duty_checker",
        replace_existing=True
    )
    return scheduler
