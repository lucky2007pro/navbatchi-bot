import asyncio
import os
import sys

# Loyiha ildizini qo'shamiz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db
from database import finance_queries, queries
from webapp.server import create_webapp_app
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web

async def run_tests():
    print("=== YANGI KASSA KIRIM-CHIQIM VA NOLLASH (RESET) TESTLARI ===")

    await init_db()
    test_chat_id = -10077889900
    await queries.register_or_update_group(test_chat_id, "Moliya Test Guruh")

    # Tozalash
    from database.db import get_db_connection
    async with get_db_connection() as conn:
        await conn.execute('DELETE FROM fund_transactions WHERE chat_id = ?', (test_chat_id,))
        await conn.execute('DELETE FROM expenses WHERE chat_id = ?', (test_chat_id,))
        await conn.execute('DELETE FROM rent_payments WHERE chat_id = ?', (test_chat_id,))
        await conn.execute('DELETE FROM rent_settings WHERE chat_id = ?', (test_chat_id,))
        await conn.execute('DELETE FROM shopping_items WHERE chat_id = ?', (test_chat_id,))
        await conn.commit()

    # 1. Boshlang'ich balans 0
    balance = await finance_queries.get_fund_balance(test_chat_id)
    assert balance == 0
    print("1. Boshlang'ich balans 0 so'm.")

    # 2. Kirim qo'shish (150,000 so'm)
    await finance_queries.add_fund_income(test_chat_id, "Ali", 150000, "Oylik fond")
    balance = await finance_queries.get_fund_balance(test_chat_id)
    assert balance == 150000
    print("2. Kirim qo'shildi: 150,000 so'm.")

    # 3. Yana kirim (50,000 so'm)
    await finance_queries.add_fund_income(test_chat_id, "Vali", 50000, "Bozorlik uchun")
    balance = await finance_queries.get_fund_balance(test_chat_id)
    assert balance == 200000
    print("3. Ikkinchi kirim: jami 200,000 so'm.")

    # 4. Chiqim (Mablag' yechish / Chiqarish - 70,000 so'm)
    await finance_queries.add_fund_withdrawal(test_chat_id, "G'ani", 70000, "Xonaga gilam yuvdirishga berildi")
    balance = await finance_queries.get_fund_balance(test_chat_id)
    assert balance == 130000
    print("4. Mablag' chiqarildi (70,000 so'm), qoldiq: 130,000 so'm.")

    # 5. Mablag'ni 0 qilish (Reset - adjust rejimi)
    old_bal = await finance_queries.reset_fund_balance(test_chat_id, clear_all=False, reset_by="Ali")
    assert old_bal == 130000
    new_bal = await finance_queries.get_fund_balance(test_chat_id)
    assert new_bal == 0
    print(f"5. Mablag' 0 qilindi (Eski: {old_bal:,} so'm -> Yangi: {new_bal} so'm).")

    # Tarixda reset yozuvi borligini tekshirish
    txs = await finance_queries.get_recent_fund_transactions(test_chat_id, limit=5)
    assert any(t["type"] == "reset" for t in txs)
    print("6. Tarixda nollash (reset) qaydi muvaffaqiyatli saqlangan.")

    # 7. Tranzaksiyani o'chirish (Delete)
    tx_to_delete = txs[0]["id"]
    deleted = await finance_queries.delete_fund_transaction(tx_to_delete, test_chat_id)
    assert deleted is True
    print("7. Tranzaksiya muvaffaqiyatli o'chirildi.")

    # 8. Web App API testlari
    print("\n--- Web App API lari testi ---")
    await finance_queries.reset_fund_balance(test_chat_id, clear_all=True)

    app = create_webapp_app(bot=None)
    async with TestClient(TestServer(app)) as client:
        # A) Mablag' kiritish API
        res = await client.post("/api/add-fund-income", json={
            "chat_id": test_chat_id,
            "member_name": "Jasur",
            "amount": 80000,
            "note": "Konditsioner filtri"
        })
        data = await res.json()
        assert data["success"] is True
        assert data["new_balance"] == 80000
        print("✅ API /api/add-fund-income ishladi.")

        # B) Mablag' chiqarish API
        res = await client.post("/api/add-fund-withdrawal", json={
            "chat_id": test_chat_id,
            "member_name": "Jasur",
            "amount": 30000,
            "note": "Chiqim"
        })
        data = await res.json()
        assert data["success"] is True
        assert data["new_balance"] == 50000
        print("✅ API /api/add-fund-withdrawal ishladi.")

        # D) Xarajat kiritish va o'chirish (Kassa balansi qaytarilishi testi)
        await finance_queries.reset_fund_balance(test_chat_id, clear_all=True)
        await finance_queries.add_fund_income(test_chat_id, "Ali", 100000, "Boshlang'ich fond")
        bal = await finance_queries.get_fund_balance(test_chat_id)
        assert bal == 100000

        # Kassadan xarajat kiritish
        exp_id = await finance_queries.add_expense(test_chat_id, "Tuxum va non", 25000, "Ali", payment_source="fund")
        bal_after_exp = await finance_queries.get_fund_balance(test_chat_id)
        assert bal_after_exp == 75000
        print("✅ Xarajat qo'shildi va kassa balansi kamaytirildi (75,000 so'm).")

        # Xarajatni o'chirish API orqali
        res = await client.post("/api/delete-expense", json={
            "chat_id": test_chat_id,
            "expense_id": exp_id
        })
        data = await res.json()
        assert data["success"] is True
        bal_restored = await finance_queries.get_fund_balance(test_chat_id)
        assert bal_restored == 100000, f"Xarajat o'chirilgach kassa balansi 100,000 ga qaytishi kerak, lekin {bal_restored} bo'ldi!"
        print("✅ Xarajat o'chirilganda kassa balansi muvaffaqiyatli qaytarildi (100,000 so'm)!")

        # E) Ijara to'lovi oy ko'rsatilmasdan ham to'g'ri ishlashi testi
        await queries.set_members(test_chat_id, [{"name": "Ali", "username": "ali"}])
        await finance_queries.update_rent_settings(test_chat_id, total_amount=600000, due_day=5, notify_days=3)
        res = await client.post("/api/toggle-rent-payment", json={
            "chat_id": test_chat_id,
            "member_name": "Ali",
            "amount": 0
        })
        data = await res.json()
        assert data["success"] is True
        assert data["is_paid"] is True
        rent_status = await finance_queries.get_rent_status_for_month(test_chat_id)
        assert rent_status[0]["is_paid"] is True
        assert rent_status[0]["amount"] == 600000
        print("✅ Ijara to'lov statusi va summasi avtomatik to'g'ri belgilandi.")

    print("\n🎉 BARCHA MOLIYA VA NOLLASH TESTLARI 100% MUVAFFAQIYATLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(run_tests())
