import json
import logging
from pathlib import Path
from typing import Tuple

from aiohttp import web
from aiogram import Bot

from config import BOT_TOKEN, WEBAPP_HOST, WEBAPP_PORT, BASE_DIR
from database import queries, finance_queries
from services.duty_manager import get_current_duty_info, advance_to_next_duty
from webapp.security import validate_telegram_init_data, is_chat_admin

logger = logging.getLogger("WebAppServer")

STATIC_DIR = BASE_DIR / "webapp" / "static"

@web.middleware
async def cors_middleware(request: web.Request, handler):
    """CORS so'rovlariga ruxsat beruvchi middleware."""
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

async def handle_index(request: web.Request) -> web.Response:
    """Bosh sahifa (Web App HTML) ni qaytarish."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return web.Response(text="Web App index.html fayli topilmadi.", status=404)
    return web.FileResponse(index_file)

async def handle_get_group_data(request: web.Request) -> web.Response:
    """Guruh navbatchilari, vazifalari va sozlamalarini olish API."""
    bot: Bot = request.app["bot"]
    chat_id_str = request.query.get("chat_id")
    if not chat_id_str:
        return web.json_response({"success": False, "error": "chat_id ko'rsatilmadi"}, status=400)

    try:
        chat_id = int(chat_id_str)
    except ValueError:
        return web.json_response({"success": False, "error": "Noto'g'ri chat_id formati"}, status=400)

    group = await queries.get_group(chat_id)
    if not group:
        return web.json_response({
            "success": False,
            "error": "Guruh topilmadi. Avval guruhda botga biror buyruq yuboring (/start yoki /help)."
        }, status=404)

    # Foydalanuvchining Telegram initData tekshiruvi
    init_data_raw = request.headers.get("X-Telegram-Init-Data") or request.query.get("init_data", "")
    validated_data = validate_telegram_init_data(init_data_raw, BOT_TOKEN) if init_data_raw else None

    is_admin = False
    user_info = None

    if validated_data and "user" in validated_data:
        user_info = validated_data["user"]
        user_id = user_info.get("id")
        if user_id:
            is_admin = await is_chat_admin(bot, chat_id, user_id)
    elif chat_id > 0:
        # Shaxsiy chat bo'lsa
        is_admin = True
    else:
        # initData berilmagan bo'lsa (masalan tashqi brauzerdan ko'rilganda)
        # Ma'lumotlarni ko'rishga ruxsat, lekin tahrirlashga yo'q
        is_admin = False

    members = await queries.get_members(chat_id)
    tasks = await queries.get_tasks(chat_id)
    current_duty, _, current_index = await get_current_duty_info(chat_id)

    return web.json_response({
        "success": True,
        "group": group,
        "members": members,
        "tasks": tasks,
        "current_duty": current_duty,
        "current_index": current_index,
        "is_admin": is_admin,
        "user": user_info
    })

async def handle_save_group_data(request: web.Request) -> web.Response:
    """Guruh navbatchilari, vazifalari va sozlamalarini saqlash API."""
    bot: Bot = request.app["bot"]

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Noto'g'ri JSON format"}, status=400)

    chat_id = data.get("chat_id")
    if not chat_id:
        return web.json_response({"success": False, "error": "chat_id ko'rsatilmadi"}, status=400)

    try:
        chat_id = int(chat_id)
    except ValueError:
        return web.json_response({"success": False, "error": "Noto'g'ri chat_id formati"}, status=400)

    # Adminlikni tekshirish
    init_data_raw = request.headers.get("X-Telegram-Init-Data") or ""
    validated_data = validate_telegram_init_data(init_data_raw, BOT_TOKEN) if init_data_raw else None

    is_admin = False
    if validated_data and "user" in validated_data:
        user_id = validated_data["user"].get("id")
        if user_id:
            is_admin = await is_chat_admin(bot, chat_id, user_id)
    elif chat_id > 0:
        is_admin = True
    elif not init_data_raw and WEBAPP_HOST in ("0.0.0.0", "127.0.0.1", "localhost"):
        # Lokal ishlab chiqish / test rejimida admin deb hisoblash
        is_admin = True

    if not is_admin:
        return web.json_response({
            "success": False,
            "error": "Kechirasiz, faqat guruh adminlari o'zgarishlarni saqlashi mumkin!"
        }, status=403)

    # 1. Navbatchilar ro'yxatini yangilash
    if "members" in data and isinstance(data["members"], list):
        formatted_members = []
        for m in data["members"]:
            name = str(m.get("name", "")).strip()
            username = str(m.get("username", "")).replace("@", "").strip()
            if name:
                formatted_members.append({"name": name, "username": username})
        if formatted_members:
            await queries.set_members(chat_id, formatted_members)

    # 2. Vazifalar ro'yxatini yangilash
    if "tasks" in data and isinstance(data["tasks"], list):
        formatted_tasks = [str(t).strip() for t in data["tasks"] if str(t).strip()]
        await queries.set_tasks(chat_id, formatted_tasks)

    # 3. Sozlamalarni yangilash
    settings = data.get("settings", {})
    if settings:
        notify_time = settings.get("notify_time")
        work_days = settings.get("work_days")
        is_active = settings.get("is_active")
        await queries.update_group_settings(
            chat_id=chat_id,
            notify_time=notify_time,
            work_days=work_days,
            is_active=is_active
        )

    return web.json_response({
        "success": True,
        "message": "Ma'lumotlar muvaffaqiyatli saqlandi!"
    })

async def handle_next_duty(request: web.Request) -> web.Response:
    """Navbatni keyingi a'zoga siljitish API."""
    bot: Bot = request.app["bot"]

    try:
        data = await request.json()
        chat_id = int(data.get("chat_id"))
    except Exception:
        return web.json_response({"success": False, "error": "Noto'g'ri so'rov"}, status=400)

    # Adminlik tekshiruvi
    init_data_raw = request.headers.get("X-Telegram-Init-Data") or ""
    validated_data = validate_telegram_init_data(init_data_raw, BOT_TOKEN) if init_data_raw else None

    is_admin = False
    if validated_data and "user" in validated_data:
        user_id = validated_data["user"].get("id")
        if user_id:
            is_admin = await is_chat_admin(bot, chat_id, user_id)
    elif chat_id > 0:
        is_admin = True
    elif not init_data_raw and WEBAPP_HOST in ("0.0.0.0", "127.0.0.1", "localhost"):
        is_admin = True

    if not is_admin:
        return web.json_response({
            "success": False,
            "error": "Faqat guruh adminlari navbatni surishi mumkin!"
        }, status=403)

    next_member = await advance_to_next_duty(chat_id)
    if not next_member:
        return web.json_response({"success": False, "error": "Navbatchilar ro'yxati bo'sh"}, status=400)

    return web.json_response({
        "success": True,
        "next_member": next_member,
        "message": f"Navbat muvaffaqiyatli o'tkazildi: {next_member['name']}"
    })

async def check_admin_helper(request: web.Request, chat_id: int) -> bool:
    """Foydalanuvchi admin yoki oddiy a'zoligini tekshirish yordamchisi."""
    bot: Bot = request.app["bot"]
    init_data_raw = request.headers.get("X-Telegram-Init-Data") or request.query.get("init_data", "")
    validated_data = validate_telegram_init_data(init_data_raw, BOT_TOKEN) if init_data_raw else None

    if validated_data and "user" in validated_data:
        user_id = validated_data["user"].get("id")
        if user_id:
            return await is_chat_admin(bot, chat_id, user_id)
    elif chat_id > 0:
        return True
    elif not init_data_raw and WEBAPP_HOST in ("0.0.0.0", "127.0.0.1", "localhost"):
        return True
    return False

# ==================== MOLIYA VA BOZORLIK API ====================

async def handle_get_finance_data(request: web.Request) -> web.Response:
    """Kassa balansi, xarajatlar, ijara va bozorlik ro'yxatini olish."""
    chat_id_str = request.query.get("chat_id")
    if not chat_id_str:
        return web.json_response({"success": False, "error": "chat_id kerak"}, status=400)

    try:
        chat_id = int(chat_id_str)
    except ValueError:
        return web.json_response({"success": False, "error": "Noto'g'ri chat_id"}, status=400)

    fund_balance = await finance_queries.get_fund_balance(chat_id)
    month_expense = await finance_queries.get_month_expense_total(chat_id)
    recent_expenses = await finance_queries.get_recent_expenses(chat_id, 25)
    recent_fund = await finance_queries.get_recent_fund_transactions(chat_id, 15)
    rent_settings = await finance_queries.get_rent_settings(chat_id)
    rent_status = await finance_queries.get_rent_status_for_month(chat_id)
    shopping_items = await finance_queries.get_shopping_items(chat_id)
    members = await queries.get_members(chat_id)
    is_admin = await check_admin_helper(request, chat_id)

    return web.json_response({
        "success": True,
        "fund_balance": fund_balance,
        "month_expense": month_expense,
        "recent_expenses": recent_expenses,
        "recent_fund": recent_fund,
        "rent_settings": rent_settings,
        "rent_status": rent_status,
        "shopping_items": shopping_items,
        "members": members,
        "is_admin": is_admin
    })

async def handle_add_fund_income(request: web.Request) -> web.Response:
    """Kassaga pul kiritish (Kirim)."""
    try:
        data = await request.json()
        chat_id = int(data.get("chat_id"))
        member_name = str(data.get("member_name", "")).strip()
        amount = int(data.get("amount", 0))
        note = str(data.get("note", "")).strip()
    except Exception:
        return web.json_response({"success": False, "error": "Noto'g'ri ma'lumotlar"}, status=400)

    if not member_name or amount <= 0:
        return web.json_response({"success": False, "error": "A'zo ismi va to'g'ri summa kiritilishi shart"}, status=400)

    await finance_queries.add_fund_income(chat_id, member_name, amount, note)
    new_balance = await finance_queries.get_fund_balance(chat_id)
    return web.json_response({
        "success": True,
        "message": f"✅ Kassaga {amount:,} so'm qo'shildi!",
        "new_balance": new_balance
    })

async def handle_add_expense(request: web.Request) -> web.Response:
    """Yangi xarajat kiritish."""
    try:
        data = await request.json()
        chat_id = int(data.get("chat_id"))
        title = str(data.get("title", "")).strip()
        amount = int(data.get("amount", 0))
        paid_by = str(data.get("paid_by", "")).strip()
        payment_source = str(data.get("payment_source", "fund")).strip()
        category = str(data.get("category", "Bozorlik")).strip()
    except Exception:
        return web.json_response({"success": False, "error": "Noto'g'ri ma'lumotlar"}, status=400)

    if not title or amount <= 0 or not paid_by:
        return web.json_response({"success": False, "error": "Xarajat nomi, summa va to'lovchi kiritilishi shart"}, status=400)

    await finance_queries.add_expense(chat_id, title, amount, paid_by, payment_source, category)
    new_balance = await finance_queries.get_fund_balance(chat_id)
    return web.json_response({
        "success": True,
        "message": f"✅ {amount:,} so'mlik xarajat saqlandi!",
        "new_balance": new_balance
    })

async def handle_update_rent_settings(request: web.Request) -> web.Response:
    """Ijara sozlamalarini yangilash."""
    try:
        data = await request.json()
        chat_id = int(data.get("chat_id"))
        total_amount = int(data.get("total_amount", 0))
        due_day = int(data.get("due_day", 5))
    except Exception:
        return web.json_response({"success": False, "error": "Noto'g'ri ma'lumotlar"}, status=400)

    if not await check_admin_helper(request, chat_id):
        return web.json_response({"success": False, "error": "Faqat adminlar ijara sozlamalarini o'zgartira oladi"}, status=403)

    await finance_queries.update_rent_settings(chat_id, total_amount, due_day)
    return web.json_response({"success": True, "message": "Ijara sozlamalari yangilandi!"})

async def handle_toggle_rent_payment(request: web.Request) -> web.Response:
    """Xonadoshning ijara to'lovini belgilash."""
    try:
        data = await request.json()
        chat_id = int(data.get("chat_id"))
        member_name = str(data.get("member_name", "")).strip()
        month_year = str(data.get("month_year", "")).strip()
        amount = int(data.get("amount", 0))
    except Exception:
        return web.json_response({"success": False, "error": "Noto'g'ri ma'lumotlar"}, status=400)

    if not await check_admin_helper(request, chat_id):
        return web.json_response({"success": False, "error": "Faqat admin to'lov holatini o'zgartira oladi"}, status=403)

    new_status = await finance_queries.toggle_rent_payment(chat_id, month_year, member_name, amount)
    return web.json_response({
        "success": True,
        "is_paid": new_status,
        "message": "To'langan" if new_status else "To'lanmagan"
    })

async def handle_shopping_item(request: web.Request) -> web.Response:
    """Bozorlik ro'yxati amallari (qo'shish, belgilash, o'chirish)."""
    try:
        data = await request.json()
        chat_id = int(data.get("chat_id"))
        action = str(data.get("action", "")).strip()
    except Exception:
        return web.json_response({"success": False, "error": "Noto'g'ri ma'lumotlar"}, status=400)

    if action == "add":
        title = str(data.get("title", "")).strip()
        added_by = str(data.get("added_by", "")).strip()
        if not title:
            return web.json_response({"success": False, "error": "Mahsulot nomi bo'sh bo'lmasligi kerak"}, status=400)
        item_id = await finance_queries.add_shopping_item(chat_id, title, added_by)
        return web.json_response({"success": True, "item_id": item_id})

    elif action == "toggle":
        item_id = int(data.get("item_id", 0))
        new_status = await finance_queries.toggle_shopping_item(item_id, chat_id)
        return web.json_response({"success": True, "is_bought": new_status})

    elif action == "delete":
        item_id = int(data.get("item_id", 0))
        await finance_queries.delete_shopping_item(item_id, chat_id)
        return web.json_response({"success": True})

    elif action == "clear_bought":
        await finance_queries.clear_bought_shopping_items(chat_id)
        return web.json_response({"success": True})

    return web.json_response({"success": False, "error": "Noma'lum amal"}, status=400)

def create_webapp_app(bot: Bot) -> web.Application:
    """aiohttp web application yaratish va marshrutlarni ulash."""
    app = web.Application(middlewares=[cors_middleware])
    app["bot"] = bot

    # API marshrutlari (Navbatchilik)
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/group-data", handle_get_group_data)
    app.router.add_post("/api/save-group-data", handle_save_group_data)
    app.router.add_post("/api/next-duty", handle_next_duty)

    # API marshrutlari (Moliya, Ijara, Bozorlik)
    app.router.add_get("/api/finance-data", handle_get_finance_data)
    app.router.add_post("/api/add-fund-income", handle_add_fund_income)
    app.router.add_post("/api/add-expense", handle_add_expense)
    app.router.add_post("/api/update-rent-settings", handle_update_rent_settings)
    app.router.add_post("/api/toggle-rent-payment", handle_toggle_rent_payment)
    app.router.add_post("/api/shopping-item", handle_shopping_item)

    # Statik fayllar (CSS, JS, ikonlar)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/static/", path=STATIC_DIR, name="static")

    return app

async def start_webapp_server(bot: Bot) -> Tuple[web.AppRunner, web.TCPSite]:
    """Web App serverini asinxron fonda ishga tushirish."""
    app = create_webapp_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=WEBAPP_HOST, port=WEBAPP_PORT)
    await site.start()
    logger.info(f"🚀 Web App serveri ishga tushdi: http://{WEBAPP_HOST}:{WEBAPP_PORT}")
    return runner, site
