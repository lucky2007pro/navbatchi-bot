import asyncio
import os
import sys
import aiohttp
from aiohttp import web
from unittest.mock import AsyncMock, MagicMock

# Loyiha ildizini sys.path ga qo'shamiz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db, get_db_connection
from database import queries
from webapp.server import create_webapp_app
from webapp.security import validate_telegram_init_data

async def run_webapp_tests():
    print("=== Web App integratsiyasi testlari boshlandi ===")

    # 1. Baza initsializatsiyasi
    await init_db()
    print("✅ 1. Baza initsializatsiyasi muvaffaqiyatli.")

    # 2. Mock Bot yaratish
    mock_bot = MagicMock()
    mock_bot.get_chat_member = AsyncMock()
    member_status = MagicMock()
    member_status.status = "administrator"
    mock_bot.get_chat_member.return_value = member_status

    # 3. Test guruhini bazaga kiritish
    test_chat_id = -1009999999
    test_chat_title = "Test WebApp Guruhi"
    await queries.register_or_update_group(test_chat_id, test_chat_title)
    print(f"✅ 2. Test guruhi ({test_chat_title}) bazaga qo'shildi.")

    # 4. aiohttp serverini test portida (8899) ishga tushirish
    test_port = 8899
    app = create_webapp_app(mock_bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=test_port)
    await site.start()
    print(f"✅ 3. Web App serveri 127.0.0.1:{test_port} da ishga tushirildi.")

    base_url = f"http://127.0.0.1:{test_port}"

    async with aiohttp.ClientSession() as session:
        # 5. Bosh sahifa (HTML) testi
        async with session.get(f"{base_url}/") as resp:
            assert resp.status == 200, f"Status kodi 200 kutilgan, olingan: {resp.status}"
            text = await resp.text()
            assert "Smart Kvartira" in text, "HTML sarlavhasi topilmadi"
            print("✅ 4. Bosh sahifa (index.html) muvaffaqiyatli yuklandi.")

        # 6. Statik CSS fayl testi
        async with session.get(f"{base_url}/static/style.css") as resp:
            assert resp.status == 200, f"CSS status: {resp.status}"
            css_text = await resp.text()
            assert "--accent-color" in css_text
            print("✅ 5. Statik fayl (style.css) muvaffaqiyatli uzatildi.")

        # 7. Statik JS fayl testi
        async with session.get(f"{base_url}/static/app.js") as resp:
            assert resp.status == 200, f"JS status: {resp.status}"
            js_text = await resp.text()
            assert "loadAllData" in js_text
            print("✅ 6. Statik fayl (app.js) muvaffaqiyatli uzatildi.")

        # 8. GET /api/group-data testi
        async with session.get(f"{base_url}/api/group-data?chat_id={test_chat_id}") as resp:
            assert resp.status == 200, f"API status: {resp.status}"
            data = await resp.json()
            assert data["success"] is True
            assert data["group"]["chat_title"] == test_chat_title
            print(f"✅ 7. GET /api/group-data ishladi: {data['group']['chat_title']}")

        # 9. POST /api/save-group-data testi (Navbatchilar va vazifalarni saqlash)
        payload = {
            "chat_id": test_chat_id,
            "members": [
                {"name": "Hojiakbar", "username": "hojiakbar_dev"},
                {"name": "Nodirbek", "username": "nodir"},
                {"name": "Jasur", "username": ""}
            ],
            "tasks": [
                "Xonani shamollatish",
                "Doskani tozalash"
            ],
            "settings": {
                "notify_time": "09:15",
                "work_days": "workdays",
                "is_active": 1
            }
        }
        async with session.post(f"{base_url}/api/save-group-data", json=payload) as resp:
            assert resp.status == 200, f"Save status: {resp.status}"
            save_res = await resp.json()
            assert save_res["success"] is True
            print("✅ 8. POST /api/save-group-data muvaffaqiyatli saqlandi.")

        # 10. Saqlangan ma'lumotlarni qayta o'qib tekshirish
        async with session.get(f"{base_url}/api/group-data?chat_id={test_chat_id}") as resp:
            updated_data = await resp.json()
            assert len(updated_data["members"]) == 3
            assert updated_data["members"][0]["name"] == "Hojiakbar"
            assert len(updated_data["tasks"]) == 2
            assert updated_data["group"]["notify_time"] == "09:15"
            assert updated_data["group"]["work_days"] == "workdays"
            assert updated_data["current_duty"]["name"] == "Hojiakbar"
            print("✅ 9. O'zgartirilgan ma'lumotlar to'g'ri o'qildi va tekshirildi.")

        # 11. POST /api/next-duty testi (Navbatni surish)
        async with session.post(f"{base_url}/api/next-duty", json={"chat_id": test_chat_id}) as resp:
            assert resp.status == 200, f"Next duty status: {resp.status}"
            next_res = await resp.json()
            assert next_res["success"] is True
            assert next_res["next_member"]["name"] == "Nodirbek"
            print(f"✅ 10. POST /api/next-duty muvaffaqiyatli surildi: {next_res['next_member']['name']}")

    # Tozalash
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM duty_members WHERE chat_id = ?", (test_chat_id,))
        await conn.execute("DELETE FROM duty_tasks WHERE chat_id = ?", (test_chat_id,))
        await conn.execute("DELETE FROM groups WHERE chat_id = ?", (test_chat_id,))
        await conn.commit()

    await runner.cleanup()
    print("\n🎉 BARCHA TESTLAR 100% MUVAFFAQIYATLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(run_webapp_tests())
