import asyncio
import os
import sys
import aiohttp
from aiohttp import web
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db, get_db_connection
from database import queries, finance_queries
from webapp.server import create_webapp_app

async def run_finance_tests():
    print("=== Smart Kvartira (Moliya & Bozorlik) Testlari Boshlandi ===")

    # 1. Baza initsializatsiyasi
    await init_db()
    print("✅ 1. Baza initsializatsiyasi muvaffaqiyatli.")

    test_chat_id = -1007777777
    test_chat_title = "Kvartira 42"

    # Guruh va a'zolarni kiritish
    await queries.register_or_update_group(test_chat_id, test_chat_title)
    members_data = [
        {"name": "Ali", "username": "ali_student"},
        {"name": "Vali", "username": "vali_student"},
        {"name": "G'ani", "username": "gani_student"}
    ]
    await queries.set_members(test_chat_id, members_data)
    print(f"✅ 2. Guruh va 3 ta a'zo ro'yxatga olindi.")

    # 2. Kassa Kirim va Balans testi
    await finance_queries.add_fund_income(test_chat_id, "Ali", 100000, "Sentabr oylik fond")
    await finance_queries.add_fund_income(test_chat_id, "Vali", 100000, "Sentabr oylik fond")
    bal = await finance_queries.get_fund_balance(test_chat_id)
    assert bal == 200000, f"Kassa balansi 200,000 kutilgan, olingan: {bal}"
    print(f"✅ 3. Kassa kirim va balans to'g'ri hisoblandi: {bal:,} so'm")

    # 3. Chiqim (Kassadan to'langan) testi
    await finance_queries.add_expense(
        chat_id=test_chat_id,
        title="Bozorlik (Go'sht, kartoshka)",
        amount=65000,
        paid_by="Ali",
        payment_source="fund",
        category="Bozorlik"
    )
    bal_after = await finance_queries.get_fund_balance(test_chat_id)
    assert bal_after == 135000, f"Kassa qoldig'i 135,000 kutilgan, olingan: {bal_after}"
    print(f"✅ 4. Kassadan chiqim to'g'ri yechildi, yangi balans: {bal_after:,} so'm")

    # 4. Chiqim (Shaxsiy cho'ntagidan to'langan) testi
    await finance_queries.add_expense(
        chat_id=test_chat_id,
        title="Wi-Fi to'lovi",
        amount=120000,
        paid_by="Vali",
        payment_source="personal",
        category="Kommunal"
    )
    # Kassadan yechilmasligi kerak!
    bal_after_personal = await finance_queries.get_fund_balance(test_chat_id)
    assert bal_after_personal == 135000, "Shaxsiy to'lov kassadan yechilmasligi kerak edi!"
    print("✅ 5. Shaxsiy to'lov kassa balansiga daxl qilmadi.")

    # 5. Oylik xarajatlar summasi
    total_exp = await finance_queries.get_month_expense_total(test_chat_id)
    assert total_exp == 185000, f"Oylik jami xarajat 185,000 kutilgan, olingan: {total_exp}"
    print(f"✅ 6. Oylik jami xarajat to'g'ri hisoblandi: {total_exp:,} so'm")

    # 6. Ijara sozlamalari va a'zolar to'lov holati testi
    await finance_queries.update_rent_settings(test_chat_id, total_amount=3000000, due_day=5)
    rent_settings = await finance_queries.get_rent_settings(test_chat_id)
    assert rent_settings["total_amount"] == 3000000
    assert rent_settings["due_day"] == 5

    status_list = await finance_queries.get_rent_status_for_month(test_chat_id)
    assert len(status_list) == 3
    # 3 million 3 kishiga bo'linganda har biriga 1 million
    assert status_list[0]["amount"] == 1000000
    assert status_list[0]["is_paid"] is False
    print(f"✅ 7. Ijara kishi boshiga to'g'ri taqsimlandi: {status_list[0]['amount']:,} so'm")

    # Ali to'ladi deb belgilash (toggle)
    new_st = await finance_queries.toggle_rent_payment(test_chat_id, "2026-09", "Ali", 1000000)
    assert new_st is True
    status_list_after = await finance_queries.get_rent_status_for_month(test_chat_id, "2026-09")
    ali_st = next(s for s in status_list_after if s["member_name"] == "Ali")
    assert ali_st["is_paid"] is True
    print("✅ 8. Ijara to'lov statusi muvaffaqiyatli to'langan deb belgilandi.")

    # 7. Bozorlik ro'yxati testi
    item1_id = await finance_queries.add_shopping_item(test_chat_id, "Kungaboqar yog'i", "Ali")
    item2_id = await finance_queries.add_shopping_item(test_chat_id, "Osh tuzi", "Vali")
    items = await finance_queries.get_shopping_items(test_chat_id)
    assert len(items) == 2

    # Yog'ni olindi deb belgilash
    toggled = await finance_queries.toggle_shopping_item(item1_id, test_chat_id)
    assert toggled is True
    # Olinganlarni tozalash
    await finance_queries.clear_bought_shopping_items(test_chat_id)
    items_after = await finance_queries.get_shopping_items(test_chat_id)
    assert len(items_after) == 1
    assert items_after[0]["title"] == "Osh tuzi"
    print("✅ 9. Bozorlik ro'yxati CRUD amallari to'liq ishladi.")

    # 8. Web App API orqali test qilish
    mock_bot = MagicMock()
    app = create_webapp_app(mock_bot)
    runner = web.AppRunner(app)
    await runner.setup()
    test_port = 8898
    site = web.TCPSite(runner, host="127.0.0.1", port=test_port)
    await site.start()

    base_url = f"http://127.0.0.1:{test_port}"
    async with aiohttp.ClientSession() as session:
        # GET /api/finance-data
        async with session.get(f"{base_url}/api/finance-data?chat_id={test_chat_id}") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["success"] is True
            assert data["fund_balance"] == 135000
            assert len(data["recent_expenses"]) == 2
            assert data["rent_settings"]["total_amount"] == 3000000
            print("✅ 10. Web App GET /api/finance-data API muvaffaqiyatli JSON qaytardi.")

        # POST /api/add-fund-income API
        async with session.post(f"{base_url}/api/add-fund-income", json={
            "chat_id": test_chat_id,
            "member_name": "G'ani",
            "amount": 50000,
            "note": "Bozorlik uchun"
        }) as resp:
            assert resp.status == 200
            res_json = await resp.json()
            assert res_json["new_balance"] == 185000
            print("✅ 11. Web App POST /api/add-fund-income API to'g'ri ishladi.")

        # POST /api/add-expense API
        async with session.post(f"{base_url}/api/add-expense", json={
            "chat_id": test_chat_id,
            "title": "Non va tuxum",
            "amount": 15000,
            "paid_by": "G'ani",
            "payment_source": "fund",
            "category": "Bozorlik"
        }) as resp:
            assert resp.status == 200
            res_json = await resp.json()
            assert res_json["new_balance"] == 170000
            print("✅ 12. Web App POST /api/add-expense API to'g'ri ishladi.")

    # Tozalash
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM fund_transactions WHERE chat_id = ?", (test_chat_id,))
        await conn.execute("DELETE FROM expenses WHERE chat_id = ?", (test_chat_id,))
        await conn.execute("DELETE FROM rent_settings WHERE chat_id = ?", (test_chat_id,))
        await conn.execute("DELETE FROM rent_payments WHERE chat_id = ?", (test_chat_id,))
        await conn.execute("DELETE FROM shopping_items WHERE chat_id = ?", (test_chat_id,))
        await conn.execute("DELETE FROM duty_members WHERE chat_id = ?", (test_chat_id,))
        await conn.execute("DELETE FROM groups WHERE chat_id = ?", (test_chat_id,))
        await conn.commit()

    await runner.cleanup()
    print("\n🎉 SMART KVARTIRA BARCHA TESTLARI 100% MUVAFFAQIYATLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(run_finance_tests())
