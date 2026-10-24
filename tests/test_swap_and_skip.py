import asyncio
import os
import sys

# Loyiha ildizini qo'shamiz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db
from database import queries
from services.duty_manager import (
    advance_to_next_duty,
    get_current_duty_info,
    build_duty_message
)
from handlers.utils import is_admin
from webapp.security import is_chat_admin

async def run_tests():
    print("=== SWAP VA SKIP FUNKSIYALARI TESTI ===")

    # 1. Bazani initsializatsiya qilish
    await init_db()
    print("1. Baza ishga tushdi.")

    test_chat_id = -10099887766
    await queries.register_or_update_group(test_chat_id, "Test Kvartira Guruh")

    members = [
        {"name": "Ali", "username": "ali"},
        {"name": "Vali", "username": "vali"},
        {"name": "G'ani", "username": "gani"},
        {"name": "Jasur", "username": "jasur"}
    ]
    await queries.set_members(test_chat_id, members)
    await queries.set_tasks(test_chat_id, ["Idishlarni yuvish", "Xonani tozalash"])

    db_members = await queries.get_members(test_chat_id)
    assert len(db_members) == 4
    ali_id = db_members[0]["id"]
    vali_id = db_members[1]["id"]
    gani_id = db_members[2]["id"]
    jasur_id = db_members[3]["id"]

    # Boshlang'ich holat: Ali navbatchi (index 0)
    cur_m, _, cur_idx = await get_current_duty_info(test_chat_id)
    assert cur_m["name"] == "Ali"
    assert cur_m["is_temporary"] is False
    assert cur_idx == 0
    print("2. Boshlang'ich navbatchi Ali (indeks 0).")

    # ==================== TEST: ALMASHTIRISH (SWAP) ====================
    print("\n--- Test: Almashtirish (Swap) ---")
    # Ali navbatini Jasur bilan almashtirmoqchi
    req_id = await queries.create_swap_request(test_chat_id, ali_id, jasur_id)
    swap_req = await queries.get_swap_request(req_id)
    assert swap_req is not None
    assert swap_req["status"] == "pending"

    # Jasur qabul qildi
    await queries.update_swap_request_status(req_id, "accepted")
    await queries.set_temp_duty(test_chat_id, jasur_id, "swap", ali_id)

    # Endi bugungi navbatchi Jasur bo'lishi kerak!
    cur_m, _, _ = await get_current_duty_info(test_chat_id)
    assert cur_m["id"] == jasur_id
    assert cur_m["name"] == "Jasur"
    assert cur_m["is_temporary"] is True
    assert cur_m["temp_duty_type"] == "swap"
    assert cur_m["original_member"]["name"] == "Ali"
    print("✅ Bugungi navbatchi muvaffaqiyatli Jasurga vaqtincha almashdi.")

    # Xabar matnida ham ko'rinishi tekshiriladi
    msg = await build_duty_message(test_chat_id)
    assert "@jasur" in msg
    assert "almashildi" in msg
    print("✅ Xabar matnida bir martalik almashinuv ko'rindi.")

    # KEYINGI NAVBATCHILIK KELGANDA: Joyiga qaytishi va Alidan keyingi kishiga (Vali) o'tishi kerak!
    print("Keyingi navbatchilik keldi (advance_to_next_duty)...")
    next_m = await advance_to_next_duty(test_chat_id)
    assert next_m["name"] == "Vali"

    # Vaqtinchalik holat tozalangan bo'lishi kerak
    cur_m, _, cur_idx = await get_current_duty_info(test_chat_id)
    assert cur_m["name"] == "Vali"
    assert cur_m["is_temporary"] is False
    assert cur_idx == 1
    print("✅ Keyingi navbatchilikda bir martalik almashuv o'tib, jadval o'z joyiga (Vali) qaytdi!")

    # ==================== TEST: O'TKAZIB YUBORISH (SKIP) ====================
    print("\n--- Test: O'tkazib yuborish (Skip) ---")
    # Hozir Vali navbatchi (index 1). Vali o'z navbatini 1 martaga o'tkazib yubormoqchi
    # Keyingi odam: G'ani
    await queries.set_temp_duty(test_chat_id, gani_id, "skip", vali_id)

    # Endi bugungi navbatchi G'ani bo'lishi kerak
    cur_m, _, _ = await get_current_duty_info(test_chat_id)
    assert cur_m["id"] == gani_id
    assert cur_m["name"] == "G'ani"
    assert cur_m["is_temporary"] is True
    assert cur_m["temp_duty_type"] == "skip"
    print("✅ Bugungi navbatchilik bir martaga G'aniga o'tkazildi.")

    # Xabar matnida ham o'tkazib yuborilgani ko'rinishi kerak
    msg = await build_duty_message(test_chat_id)
    assert "@gani" in msg
    assert "o'tkazib yubordi" in msg
    print("✅ Xabar matnida o'tkazib yuborilganlik qaydi ko'rindi.")

    # KEYINGI NAVBATCHILIK KELGANDA: O'tkazib yuborilgan odam (Vali) o'z joyiga qaytishi kerak!
    print("Keyingi navbatchilik keldi (advance_to_next_duty)...")
    returned_m = await advance_to_next_duty(test_chat_id)
    assert returned_m["name"] == "Vali"

    cur_m, _, cur_idx = await get_current_duty_info(test_chat_id)
    assert cur_m["name"] == "Vali"
    assert cur_m["is_temporary"] is False
    assert cur_idx == 1
    print("✅ O'tkazib yuborilgan navbatchi (Vali) keyingi navbatda yana o'z joyiga qaytdi!")

    # ==================== TEST: ASLIGA QAYTARISH (RESET) ====================
    print("\n--- Test: Asliga qaytarish (Reset) ---")
    await queries.set_temp_duty(test_chat_id, jasur_id, "swap", vali_id)
    cur_m, _, _ = await get_current_duty_info(test_chat_id)
    assert cur_m["name"] == "Jasur"

    # Reset qilish
    await queries.clear_temp_duty(test_chat_id)
    cur_m, _, _ = await get_current_duty_info(test_chat_id)
    assert cur_m["name"] == "Vali"
    assert cur_m["is_temporary"] is False
    print("✅ Asliga qaytarish funksiyasi to'g'ri ishladi.")

    # ==================== TEST: HAMMA UCHUN HUQUQLAR OCHIQLIGI ====================
    print("\n--- Test: Tahrirlash hamma uchun ochiqligi ---")
    admin_result = await is_admin(None, test_chat_id, 123456, "group")
    assert admin_result is True

    webapp_admin = await is_chat_admin(None, test_chat_id, 123456)
    assert webapp_admin is True
    print("✅ Barcha a'zolar uchun tahrirlash huquqi to'liq ochiq!")

    print("\n🎉 BARCHA YANGI TESTLAR 100% MUVAFFAQIYATLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(run_tests())
