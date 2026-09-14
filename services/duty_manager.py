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
    """
    group = await queries.get_group(chat_id)
    if not group:
        return None, [], 0

    members = await queries.get_members(chat_id)
    if not members:
        return None, [], 0

    current_index = group.get("current_index", 0) % len(members)
    current_member = members[current_index]

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

    # Keyingi navbatchini ham ko'rsatish (qulaylik uchun)
    next_member_text = ""
    if len(members) > 1:
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
        f"👤 <b>Bugungi navbatchi:</b> {duty_tag}{next_member_text}",
        ""
    ]

    # Vazifalar
    if tasks:
        lines.append("📋 <b>Bugungi vazifalar:</b>")
        for idx, t in enumerate(tasks, start=1):
            lines.append(f"  <b>{idx}.</b> {t['task_text']}")
    else:
        lines.append("📋 <b>Bugungi vazifalar:</b> Belgilanmagan (Admin /vazifalar orqali qo'shishi mumkin)")

    lines.append("")
    lines.append("✨ <i>Iltimos, vazifalarni o'z vaqtida va mas'uliyat bilan bajaring!</i>")

    return "\n".join(lines)

async def advance_to_next_duty(chat_id: int, notify_date: Optional[str] = None) -> Optional[dict]:
    """
    Navbatni keyingi a'zoga siljitadi va yangi navbatchini qaytaradi.
    """
    group = await queries.get_group(chat_id)
    if not group:
        return None

    members = await queries.get_members(chat_id)
    if not members:
        return None

    current_index = group.get("current_index", 0)
    new_index = (current_index + 1) % len(members)

    await queries.update_group_index(chat_id, new_index, last_date=notify_date)
    return members[new_index]
