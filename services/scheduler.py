import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import TIMEZONE
from database import queries, rating_queries
from services.duty_manager import build_duty_message, advance_to_next_duty
from handlers.common import get_webapp_keyboard
from handlers.rating import build_rating_poll_text, get_rating_keyboard

logger = logging.getLogger(__name__)

tz = ZoneInfo(TIMEZONE)

def get_one_hour_before(time_str: str) -> str:
    """Berilgan 'HH:MM' vaqtidan 1 soat oldingi vaqtni qaytaradi."""
    try:
        hour, minute = map(int, time_str.split(":"))
        rating_hour = (hour - 1) % 24
        return f"{rating_hour:02d}:{minute:02d}"
    except Exception:
        return "07:00"

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
    Har daqiqada barcha faol guruhlarni tekshiradi:
    1. Eslatmadan 1 soat oldin: Oldingi navbatchilikni anonim baholash so'rovini yuboradi.
    2. Eslatma vaqtida: Baholashni yakunlab, natijasi bilan yangi navbatchilikni e'lon qiladi.
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

            # ---------------- 1. NAVBATCHILIKNI BAHOLASH (1 SOAT OLDIN) ----------------
            rating_time = get_one_hour_before(notify_time)
            if rating_time == current_time_str and is_work_day(work_days, current_weekday):
                # Bugun baholash so'rovi allaqachon yuborilganmi?
                if not await rating_queries.is_today_rating_sent(chat_id, current_date_str):
                    members = await queries.get_members(chat_id)
                    if members:
                        current_index = group.get("current_index", 0)
                        prev_index = (current_index - 1) % len(members)
                        prev_member = members[prev_index]
                        member_display = f"@{prev_member['username']}" if prev_member.get("username") else prev_member["name"]

                        try:
                            # Yangi anonim baholash sessiyasini ochish
                            rating_id = await rating_queries.create_rating_session(
                                chat_id=chat_id,
                                member_name=member_display,
                                duty_date=current_date_str
                            )

                            poll_text = build_rating_poll_text(member_display, current_date_str)
                            keyboard = get_rating_keyboard(rating_id, likes=0, dislikes=0)

                            sent_poll = await bot.send_message(
                                chat_id=chat_id,
                                text=poll_text,
                                reply_markup=keyboard,
                                parse_mode="HTML"
                            )
                            await rating_queries.update_rating_message_id(rating_id, sent_poll.message_id)
                            logger.info(f"Guruh {chat_id} uchun {member_display} navbatchiligini baholash so'rovi yuborildi.")
                        except Exception as poll_err:
                            logger.error(f"Guruh {chat_id} ga baholash so'rovi yuborishda xatolik: {poll_err}")

            # ---------------- 2. NAVBATCHILIK E'LON QILISH (NOTIFY_TIME DA) ----------------
            # Vaqti to'g'ri keladimi?
            if notify_time != current_time_str:
                continue

            # Bugun allaqachon yuborilganmi?
            if last_date == current_date_str:
                continue

            # Bugun ish kunimi?
            if not is_work_day(work_days, current_weekday):
                continue

            # Agar avval bildirishnoma yuborilgan bo'lsa, yangi kun uchun navbatni siljitamiz
            if last_date:
                await advance_to_next_duty(chat_id, notify_date=current_date_str)
            else:
                # Birinchi marta bo'lsa, hozirgi sanani qayd etamiz
                cur_idx = group.get("current_index", 0)
                await queries.update_group_index(chat_id, cur_idx, last_date=current_date_str)

            # Faol baholash sessiyasini yopish va natijasini olish
            active_rating = await rating_queries.get_active_rating(chat_id)
            rating_summary = None
            if active_rating:
                rating_summary = await rating_queries.close_rating_session(active_rating["id"])
                # Guruhdagi so'rovnoma xabarini yakunlangan deb tahrirlash
                if active_rating.get("message_id"):
                    try:
                        closed_text = (
                            f"🧹 <b>NAVBATCHILIKNI BAHOLASH YAKUNLANDI!</b> 🔒\n\n"
                            f"👤 Navbatchi: <b>{active_rating['member_name']}</b>\n"
                            f"📊 Natija: 👍 {rating_summary['likes_count']} ta | 👎 {rating_summary['dislikes_count']} ta\n\n"
                            f"<i>Ovoz bergan barcha xonadoshlarga rahmat!</i>"
                        )
                        await bot.edit_message_text(
                            text=closed_text,
                            chat_id=chat_id,
                            message_id=active_rating["message_id"],
                            reply_markup=get_rating_keyboard(
                                active_rating["id"],
                                likes=rating_summary["likes_count"],
                                dislikes=rating_summary["dislikes_count"],
                                is_closed=True
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as edit_err:
                        logger.warning(f"Baholash xabarini yopishda xatolik: {edit_err}")

            # Xabarni shakllantirish (oldingi baholash natijasi bilan birga)
            message_text = await build_duty_message(chat_id, is_automatic=True, rating_summary=rating_summary)
            if not message_text:
                logger.info(f"Guruh {chat_id} uchun navbatchilar ro'yxati bo'sh, xabar yuborilmadi.")
                continue

            try:
                # Xabar ostidagi boshqaruv tugmalari (almashtirish, o'tkazib yuborish, Web App)
                from handlers.duty_actions import get_duty_keyboard
                updated_group = await queries.get_group(chat_id)
                has_temp = bool(updated_group and updated_group.get("temp_duty_member_id"))
                markup = get_duty_keyboard(chat_id, has_temp=has_temp)

                # Guruhga yuborish
                sent_msg = await bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    reply_markup=markup,
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

                logger.info(f"Guruh {chat_id} ga navbatchilik xabari muvaffaqiyatli yuborildi va pin qilindi.")

            except TelegramForbiddenError:
                logger.warning(f"Bot guruhdan {chat_id} chiqarilgan yoki bloklangan.")
            except Exception as send_err:
                logger.error(f"Guruh {chat_id} ga xabar yuborishda xatolik: {send_err}")

    except Exception as e:
        logger.error(f"check_and_send_scheduled_duties da xatolik: {e}", exc_info=True)

async def check_and_send_rent_reminders(bot: Bot) -> None:
    """
    Ijara to'lov muddati yaqinlashganda guruhlarga avtomatik eslatma yuboradi.
    Har kuni soat 10:00 da ishga tushadi.
    """
    try:
        from database import finance_queries
        from handlers.common import get_webapp_keyboard

        now = datetime.now(tz)
        current_day = now.day
        month_str = now.strftime("%Y-%m")

        active_groups = await queries.get_all_active_groups()
        for group in active_groups:
            chat_id = group["chat_id"]
            settings = await finance_queries.get_rent_settings(chat_id)
            total_amount = settings.get("total_amount", 0)
            if total_amount <= 0:
                continue

            due_day = settings.get("due_day", 5)
            notify_days = settings.get("notify_days", 3)

            start_notify_day = max(1, due_day - notify_days)
            if not (start_notify_day <= current_day <= due_day):
                continue

            status_list = await finance_queries.get_rent_status_for_month(chat_id, month_str)
            unpaid_members = [m for m in status_list if not m["is_paid"]]

            if not unpaid_members:
                continue

            days_left = due_day - current_day
            if days_left == 0:
                time_badge = "🔴 <b>BUGUN OXIRGI TO'LOV KUNI!</b>"
            elif days_left == 1:
                time_badge = "🟠 <b>ERTALIKKA TO'LOV KUNI!</b>"
            else:
                time_badge = f"🟡 <i>To'lovga {days_left} kun qoldi!</i>"

            lines = [
                "🏠 <b>KVARTIRA IJARASI TO'LOVI ESLATMASI:</b>",
                "",
                time_badge,
                f"💵 <b>Oylik ijara:</b> {total_amount:,} so'm",
                f"📅 <b>Belgilangan sana:</b> Har oyning {due_day}-kuni",
                "",
                "⏳ <b>Hali to'lamagan xonadoshlar:</b>"
            ]

            for m in unpaid_members:
                username = f" (@{m['username']})" if m.get("username") else ""
                lines.append(f"  • <b>{m['member_name']}</b>{username}: {m['amount']:,} so'm")

            lines.append("")
            lines.append("💳 <i>Iltimos, o'z vaqtida to'lovni amalga oshiring va Web App'da belgilang.</i>")

            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="\n".join(lines),
                    reply_markup=get_webapp_keyboard(chat_id),
                    parse_mode="HTML"
                )
                logger.info(f"Guruh {chat_id} ga ijara to'lovi eslatmasi yuborildi.")
            except Exception as e:
                logger.warning(f"Guruh {chat_id} ga ijara eslatmasi yuborishda xatolik: {e}")

    except Exception as e:
        logger.error(f"check_and_send_rent_reminders da xatolik: {e}", exc_info=True)

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
    scheduler.add_job(
        check_and_send_rent_reminders,
        "cron",
        hour=10,
        minute=0,  # Har kuni soat 10:00 da ijara eslatmasi
        args=[bot],
        id="rent_checker",
        replace_existing=True
    )
    return scheduler
