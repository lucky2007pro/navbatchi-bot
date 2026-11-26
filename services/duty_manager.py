import html
import re
from typing import List, Dict, Optional, Tuple
from database import queries


def _esc(val) -> str:
    return html.escape(str(val or ""), quote=False)


def parse_members_text(text: str) -> List[Dict[str, str]]:
    """
    Foydalanuvchi kiritgan matndan navbatchilar ro'yxatini ajratib oladi.
    Formatlar misollari:
      1. @hojiakbar (Hojiakbar)
      2. Nodirbek (@nodir)
      3. @jasur
      4. Sardor
      5. Ali, Vali, G'ani (bir qatorda vergul bilan yozilsa ham)
    """
    if not text or not text.strip():
        return []

    raw_lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    # Agar faqat bitta qator bo'lsa va vergul bilan ajratilgan bo'lsa (masalan: "Ali, Vali, Sardor")
    if len(raw_lines) == 1 and "," in raw_lines[0]:
        lines = [part.strip() for part in raw_lines[0].split(",") if part.strip()]
    else:
        lines = raw_lines

    members = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Boshidagi tartib raqamlari va belgilarni tozalash (masalan "1.", "1)", "1 -", "-", "•")
        cleaned = re.sub(r"^\s*(?:\d+\s*[\.\)\-:]?|\-|\*|•)\s*", "", line).strip()
        if not cleaned:
            continue

        # Username qidirish (@username — kamida 3 ta belgi)
        username_match = re.search(r"@([a-zA-Z0-9_]{3,32})", cleaned)
        username = username_match.group(1) if username_match else ""

        # Qolgan matndan ismni ajratish
        name_candidate = re.sub(r"@([a-zA-Z0-9_]{3,32})", "", cleaned)
        # Qavslar va ajratuvchi tirelarni (" - ", " — ") tozalash (Mirzo-Ulug'bek kabi ismlarni buzmasdan)
        name = re.sub(r"[\(\)\[\]]", " ", name_candidate)
        name = re.sub(r"(?:^\s*[\-—]+\s*|\s+[\-—]+\s+|\s*[\-—]+\s*$)", " ", name)
        name = re.sub(r"\s+", " ", name).strip()

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
    if not text or not text.strip():
        return []

    raw_lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if len(raw_lines) == 1 and "," in raw_lines[0]:
        lines = [part.strip() for part in raw_lines[0].split(",") if part.strip()]
    else:
        lines = raw_lines

    tasks = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Boshidagi tartib raqamlarini tozalash
        cleaned = re.sub(r"^\s*(?:\d+\s*[\.\)\-:]?|\-|\*|•)\s*", "", line).strip()
        if cleaned:
            tasks.append(cleaned)

    return tasks


async def get_current_duty_info(chat_id: int) -> Tuple[Optional[dict], List[dict], int]:
    """
    Guruhdagi ayni damdagi navbatchi, barcha a'zolar va hozirgi indeksni qaytaradi.
    Agar vaqtinchalik (swap yoki skip) navbatchi tayinlangan bo'lsa, uni ko'rsatadi.
    """
    members = await queries.get_members(chat_id)
    if not members:
        return None, [], 0

    group = await queries.get_group(chat_id)
    if not group:
        await queries.register_or_update_group(chat_id, "Smart Kvartira")
        group = await queries.get_group(chat_id) or {"current_index": 0}

    current_index = (group.get("current_index") or 0) % len(members)
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
        else:
            # Eskirgan temp_duty_member_id bo'lsa tozalab yuboramiz
            await queries.clear_temp_duty(chat_id)

    current_member = dict(original_member)
    current_member["is_temporary"] = False
    return current_member, members, current_index


def format_member_html(member: dict, bold: bool = True) -> str:
    """
    A'zoni HTML formatida xavfsiz ko'rsatish (username bo'lsa @mention, bo'lmasa faqat ismi).
    """
    raw_name = str(member.get("name") or "Noma'lum").strip()
    raw_username = str(member.get("username") or "").replace("@", "").strip()
    safe_name = _esc(raw_name)
    safe_username = _esc(raw_username)

    if safe_username:
        mention = f"@{safe_username}"
        if raw_name and raw_name != f"@{raw_username}":
            return f"<b>{mention}</b> ({safe_name})" if bold else f"{mention} ({safe_name})"
        return f"<b>{mention}</b>" if bold else mention
    return f"<b>{safe_name}</b>" if bold else safe_name


async def build_duty_message(chat_id: int, is_automatic: bool = False, rating_summary: Optional[dict] = None) -> Optional[str]:
    """
    Guruh uchun navbatchilik xabari matnini (HTML formatida) tayyorlaydi.
    """
    current_member, members, current_index = await get_current_duty_info(chat_id)
    if not current_member:
        return None

    tasks = await queries.get_tasks(chat_id)

    # Navbatchini belgilash (agar username bo'lsa tag qilamiz, bo'lmasa faqat ismini chiqaramiz)
    duty_tag = format_member_html(current_member, bold=True)

    # Vaqtinchalik holat izohi (Swap yoki Skip)
    temp_note = ""
    if current_member.get("is_temporary"):
        orig = current_member.get("original_member", {})
        orig_raw_user = str(orig.get("username") or "").replace("@", "").strip()
        orig_raw_name = str(orig.get("name") or "Asl navbatchi").strip()
        orig_tag = f"@{_esc(orig_raw_user)}" if orig_raw_user else _esc(orig_raw_name)
        if current_member.get("temp_duty_type") == "swap":
            temp_note = f"\n🔄 <i>(Navbat <b>{orig_tag}</b> bilan 1 martaga almashildi. Keyingi navbatda joyiga qaytadi)</i>"
        elif current_member.get("temp_duty_type") == "skip":
            temp_note = f"\n⏭️ <i>(<b>{orig_tag}</b> bugungi navbatini 1 martaga o'tkazib yubordi. Keyingi navbatda joyiga qaytadi)</i>"

    # Keyingi navbatchini ham ko'rsatish (qulaylik uchun)
    next_member_text = ""
    if len(members) > 1:
        if current_member.get("is_temporary") and current_member.get("temp_duty_type") == "skip":
            orig = current_member.get("original_member", {})
            orig_raw_user = str(orig.get("username") or "").replace("@", "").strip()
            orig_raw_name = str(orig.get("name") or "").strip()
            next_tag = f"@{_esc(orig_raw_user)}" if orig_raw_user else _esc(orig_raw_name)
            next_member_text = f"\n<i>(Keyingi navbat o'z joyiga qaytadi: {next_tag})</i>"
        else:
            next_index = (current_index + 1) % len(members)
            next_mem = members[next_index]
            next_raw_user = str(next_mem.get("username") or "").replace("@", "").strip()
            next_raw_name = str(next_mem.get("name") or "").strip()
            next_tag = f"@{_esc(next_raw_user)}" if next_raw_user else _esc(next_raw_name)
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

    # Oldingi navbatchilik bahosi natijasi (agar mavjud bo'lsa)
    if rating_summary:
        prev_name = _esc(rating_summary.get("member_name"))
        likes = rating_summary.get("likes_count", 0)
        dislikes = rating_summary.get("dislikes_count", 0)
        total = likes + dislikes
        if total > 0:
            if likes > dislikes:
                status_note = "🌟 A'lo darajada!"
            elif likes == dislikes:
                status_note = "✅ Qoniqarli!"
            else:
                status_note = "⚠️ Kamchiliklar bor"
        else:
            status_note = "ℹ️ Baholanmadi"

        lines.append(f"📊 <b>Oldingi navbatchilik bahosi ({prev_name}):</b>")
        lines.append(f"   👍 {likes} ta  |  👎 {dislikes} ta — <i>{status_note}</i>")
        lines.append("")

    # Vazifalar
    if tasks:
        lines.append("📋 <b>Bugungi vazifalar:</b>")
        for idx, t in enumerate(tasks, start=1):
            safe_task = _esc(t.get("task_text"))
            lines.append(f"  <b>{idx}.</b> {safe_task}")
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
    members = await queries.get_members(chat_id)
    if not members:
        return None

    group = await queries.get_group(chat_id)
    if not group:
        await queries.register_or_update_group(chat_id, "Smart Kvartira")
        group = await queries.get_group(chat_id) or {"current_index": 0}

    temp_duty_type = group.get("temp_duty_type")
    current_index = group.get("current_index") or 0

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
