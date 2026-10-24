import re
from typing import List, Dict, Optional, Tuple
from database import queries

def parse_members_text(text: str) -> List[Dict[str, str]]:
    """
    Foydalanuvchi kiritgan matndan navbatchilar ro'yxatini ajratib oladi.
    Formatlar misollari:
      1. @hojiakbar (Hojiakbar)
      2. Nodirbek (@nodir)
      3. @jasur
      4. Sardor
    """
    lines = text.strip().split("\n")
    members = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Boshidagi tartib raqamlarini tozalash (masalan "1.", "1)", "1 -", "-")
        cleaned = re.sub(r"^\s*(\d+[\.\)\-]?|\-|\*)\s*", "", line).strip()
        if not cleaned:
            continue

        # Username qidirish (@username)
        username_match = re.search(r"@([a-zA-Z0-9_]{4,32})", cleaned)
        username = username_match.group(1) if username_match else ""

        # Qolgan matndan ismni ajratish
        name_candidate = re.sub(r"@([a-zA-Z0-9_]{4,32})", "", cleaned)
        # Qavslar, chiziqchalar va bo'sh joylarni tozalash
        name = re.sub(r"[\(\)\[\]\-—]", " ", name_candidate).strip()
        name = re.sub(r"\s+", " ", name)

        # Agar ism qolmasa, username ning o'zini ism sifatida ishlatamiz
        if not name and username:
            name = f"@{username}"
        elif not name and not username:
            name = cleaned

        members.append({
            "name": name,
            "username": username
        })

    return members

def parse_tasks_text(text: str) -> List[str]:
    """
    Foydalanuvchi kiritgan matndan vazifalar ro'yxatini ajratib oladi.
    """
    lines = text.strip().split("\n")
    tasks = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Boshidagi tartib raqamlarini tozalash
        cleaned = re.sub(r"^\s*(\d+[\.\)\-]?|\-|\*)\s*", "", line).strip()
        if cleaned:
            tasks.append(cleaned)

    return tasks

async def get_current_duty_info(chat_id: int) -> Tuple[Optional[dict], List[dict], int]:
    """
    Guruhdagi ayni damdagi navbatchi, barcha a'zolar va hozirgi indeksni qaytaradi.
    Agar vaqtinchalik (swap yoki skip) navbatchi tayinlangan bo'lsa, uni ko'rsatadi.
    """
    group = await queries.get_group(chat_id)
    if not group:
        return None, [], 0

    members = await queries.get_members(chat_id)
    if not members:
        return None, [], 0

    current_index = group.get("current_index", 0) % len(members)
    original_member = members[current_index]

    temp_duty_id = group.get("temp_duty_member_id")
    if temp_duty_id:
        temp_member = next((m for m in members if m["id"] == temp_duty_id), None)
        if temp_member:
            current_member = dict(temp_member)
            current_member["is_temporary"] = True
            current_member["temp_duty_type"] = group.get("temp_duty_type", "swap")
            current_member["original_member"] = original_member
            return current_member, members, current_index

    current_member = dict(original_member)
    current_member["is_temporary"] = False
    return current_member, members, current_index

async def build_duty_message(chat_id: int, is_automatic: bool = False) -> Optional[str]:
    """
    Guruh uchun navbatchilik xabari matnini (HTML formatida) tayyorlaydi.
    """
    current_member, members, current_index = await get_current_duty_info(chat_id)
    if not current_member:
        return None

    tasks = await queries.get_tasks(chat_id)

    # Navbatchini belgilash (agar username bo'lsa tag qilamiz)
    if current_member.get("username"):
        duty_mention = f"@{current_member['username']}"
        if current_member.get("name") and current_member['name'] != f"@{current_member['username']}":
            duty_tag = f"<b>{duty_mention}</b> ({current_member['name']})"
        else:
            duty_tag = f"<b>{duty_mention}</b>"
    else:
        duty_tag = f"<b>{current_member['name']}</b>"

    # Vaqtinchalik holat izohi (Swap yoki Skip)
    temp_note = ""
    if current_member.get("is_temporary"):
        orig = current_member.get("original_member", {})
        orig_tag = f"@{orig['username']}" if orig.get("username") else orig.get("name", "Asl navbatchi")
        if current_member.get("temp_duty_type") == "swap":
            temp_note = f"\n🔄 <i>(Navbat <b>{orig_tag}</b> bilan 1 martaga almashildi. Keyingi navbatda joyiga qaytadi)</i>"
        elif current_member.get("temp_duty_type") == "skip":
            temp_note = f"\n⏭️ <i>(<b>{orig_tag}</b> bugungi navbatini 1 martaga o'tkazib yubordi. Keyingi navbatda joyiga qaytadi)</i>"

    # Keyingi navbatchini ham ko'rsatish (qulaylik uchun)
    next_member_text = ""
    if len(members) > 1:
        if current_member.get("is_temporary") and current_member.get("temp_duty_type") == "skip":
            orig = current_member.get("original_member", {})
            next_tag = f"@{orig['username']}" if orig.get("username") else orig.get("name", "")
            next_member_text = f"\n<i>(Keyingi navbat o'z joyiga qaytadi: {next_tag})</i>"
        else:
            next_index = (current_index + 1) % len(members)
            next_mem = members[next_index]
            if next_mem.get("username"):
                next_tag = f"@{next_mem['username']}"
            else:
                next_tag = next_mem['name']
            next_member_text = f"\n<i>(Ertangi navbatchi: {next_tag})</i>"

    # Sarlavha
    if is_automatic:
        header = "🧹 <b>BUGUNGI NAVBATCHILIK</b> 🔔"
    else:
        header = "📌 <b>HOZIRGI NAVBATCHILIK MA'LUMOTI</b>"

    lines = [
        header,
        "",
        f"👤 <b>Bugungi navbatchi:</b> {duty_tag}{temp_note}{next_member_text}",
        ""
    ]

    # Vazifalar
    if tasks:
        lines.append("📋 <b>Bugungi vazifalar:</b>")
        for idx, t in enumerate(tasks, start=1):
            lines.append(f"  <b>{idx}.</b> {t['task_text']}")
    else:
        lines.append("📋 <b>Bugungi vazifalar:</b> Belgilanmagan (/vazifalar_sozlash orqali qo'shishingiz mumkin)")

    lines.append("")
    lines.append("✨ <i>Iltimos, vazifalarni o'z vaqtida va mas'uliyat bilan bajaring!</i>")

    return "\n".join(lines)

async def advance_to_next_duty(chat_id: int, notify_date: Optional[str] = None) -> Optional[dict]:
    """
    Navbatni keyingi a'zoga siljitadi va yangi navbatchini qaytaradi.
    Agar vaqtinchalik bir martalik o'tkazib yuborish (skip) yoki almashtirish (swap)
    bo'lgan bo'lsa, bir martadan keyin o'z joyiga qaytaradi.
    """
    group = await queries.get_group(chat_id)
    if not group:
        return None

    members = await queries.get_members(chat_id)
    if not members:
        return None

    temp_duty_type = group.get("temp_duty_type")
    current_index = group.get("current_index", 0)

    # 1. Skip bo'lgan bo'lsa: bir marta o'tkazib yuborildi, keyingi navbatchilikda joyiga qaytadi
    if temp_duty_type == "skip":
        new_index = current_index % len(members)
        await queries.clear_temp_duty(chat_id)
        await queries.update_group_index(chat_id, new_index, last_date=notify_date)
        return members[new_index]

    # 2. Swap bo'lgan bo'lsa: bir marta almashdi, keyingi navbatchilikda jadval o'z joyiga qaytadi
    if temp_duty_type == "swap":
        new_index = (current_index + 1) % len(members)
        await queries.clear_temp_duty(chat_id)
        await queries.update_group_index(chat_id, new_index, last_date=notify_date)
        return members[new_index]

    # 3. Odatiy navbat
    new_index = (current_index + 1) % len(members)
    await queries.update_group_index(chat_id, new_index, last_date=notify_date)
    return members[new_index]
