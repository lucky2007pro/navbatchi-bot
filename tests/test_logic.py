import asyncio
import os
import sys

# Loyiha ildizini qo'shamiz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db, get_db_connection
from database import queries
from services.duty_manager import (
    parse_members_text,
    parse_tasks_text,
    build_duty_message,
    advance_to_next_duty,
    get_current_duty_info
)
from services.scheduler import is_work_day

async def run_tests():
    print("--- 1. Baza initsializatsiyasi testi ---")
    await init_db()
    print("✅ Baza muvaffaqiyatli ishga tushirildi.")

    print("\n--- 2. Parserlar testi ---")
    sample_members_text = """
    1. @hojiakbar (Hojiakbar)
    2. Nodirbek (@nodir)
    3. Jasur Olimov
    4. @sardor
    """
    members = parse_members_text(sample_members_text)
    assert len(members) == 4, f"Kutilgan 4, olingan: {len(members)}"
    assert members[0]["username"] == "hojiakbar"
    assert members[0]["name"] == "Hojiakbar"
    assert members[1]["username"] == "nodir"
    assert members[1]["name"] == "Nodirbek"
    assert members[2]["username"] == ""
    assert members[2]["name"] == "Jasur Olimov"
    assert members[3]["username"] == "sardor"
    print(f"✅ Navbatchilar parseri to'g'ri ishladi: {members}")

    sample_tasks_text = """
    1. Xonani shamollatish va polni tozalash
    2. Doska va ish stollarini tartibga keltirish
    3. Chiqindilarni chiqarib tashlash
    """
    tasks = parse_tasks_text(sample_tasks_text)
    assert len(tasks) == 3, f"Kutilgan 3, olingan: {len(tasks)}"
    print(f"✅ Vazifalar parseri to'g'ri ishladi: {tasks}")

    print("\n--- 3. Guruh, a'zolar va vazifalar saqlash testi ---")
    test_chat_id = -1001234567890
    test_chat_title = "Test Guruh"

    await queries.register_or_update_group(test_chat_id, test_chat_title)
    await queries.set_members(test_chat_id, members)
    await queries.set_tasks(test_chat_id, tasks)

    saved_group = await queries.get_group(test_chat_id)
    assert saved_group is not None
    assert saved_group["chat_title"] == test_chat_title

    saved_members = await queries.get_members(test_chat_id)
    assert len(saved_members) == 4

    saved_tasks = await queries.get_tasks(test_chat_id)
    assert len(saved_tasks) == 3
    print("✅ Ma'lumotlar bazaga to'g'ri saqlandi va o'qildi.")

    print("\n--- 4. Navbatchi xabarini shakllantirish testi ---")
    msg = await build_duty_message(test_chat_id, is_automatic=True)
    assert msg is not None
    assert "@hojiakbar" in msg
    assert "Xonani shamollatish" in msg
    print("✅ Shakllangan xabar ko'rinishi:")
    print("-" * 40)
    print(msg)
    print("-" * 40)

    print("\n--- 5. Aylanma navbat (Round-robin) testi ---")
    # 1-navbatchi hojiakbar edi (index 0)
    # 1 marta suramiz -> nodir (index 1)
    next_m = await advance_to_next_duty(test_chat_id)
    assert next_m["username"] == "nodir"

    # Yana 1 marta -> jasur (index 2)
    next_m = await advance_to_next_duty(test_chat_id)
    assert next_m["name"] == "Jasur Olimov"

    # Yana 1 marta -> sardor (index 3)
    next_m = await advance_to_next_duty(test_chat_id)
    assert next_m["username"] == "sardor"

    # Yana 1 marta -> aylanib yana birinchi navbatchi hojiakbar (index 0) ga qaytishi kerak!
    next_m = await advance_to_next_duty(test_chat_id)
    assert next_m["username"] == "hojiakbar"
    print("✅ Aylanma navbat to'liq 4 a'zodan aylanib yana 1-a'zoga muvaffaqiyatli qaytdi!")

    print("\n--- 6. Ish kunlari mantiqi testi ---")
    # 0=Dushanba, 4=Juma, 5=Shanba, 6=Yakshanba
    assert is_work_day("workdays", 0) is True
    assert is_work_day("workdays", 4) is True
    assert is_work_day("workdays", 5) is False
    assert is_work_day("workdays", 6) is False

    assert is_work_day("workdays_sat", 5) is True
    assert is_work_day("workdays_sat", 6) is False

    assert is_work_day("all", 6) is True
    print("✅ Ish kunlari filtri to'g'ri ishladi.")

    print("\n🎉 BARCHA TESTLAR MUVAFFAQIYATLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(run_tests())
