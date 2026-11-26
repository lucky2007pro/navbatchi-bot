import asyncio
import os
import sys
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

# Testlar haqiqiy bazani o'zgartirmasligi uchun vaqtinchalik baza ishlatamiz
TMP_DB = os.path.join(tempfile.gettempdir(), f"navbatchi_e2e_{os.getpid()}.db")
os.environ["DB_PATH"] = TMP_DB

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from database.db import init_db
from database import queries, finance_queries, rating_queries
from services import duty_manager, scheduler
from handlers import common, group, admin, duty_actions, finance, rating
from webapp.server import create_webapp_app

ALLOWED_TELEGRAM_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "tg-spoiler", "blockquote"}


class TelegramHTMLValidator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack = []

    def handle_starttag(self, tag, attrs):
        assert tag in ALLOWED_TELEGRAM_TAGS, f"Telegram ruxsat bermagan HTML teg topildi: <{tag}>"
        self.stack.append(tag)

    def handle_endtag(self, tag):
        assert tag in ALLOWED_TELEGRAM_TAGS, f"Telegram ruxsat bermagan yopiluvchi teg: </{tag}>"
        assert self.stack and self.stack[-1] == tag, f"HTML teglar ketma-ketligi buzilgan: kutilgan </{self.stack[-1] if self.stack else 'None'}>, topilgan </{tag}>"
        self.stack.pop()


def assert_valid_telegram_html(html_text: str):
    assert isinstance(html_text, str) and len(html_text) > 0
    parser = TelegramHTMLValidator()
    parser.feed(html_text)
    parser.close()
    assert not parser.stack, f"Yopilmagan HTML teglar qoldi: {parser.stack}"


def make_fake_message(text: str, chat_id: int = -100555666, chat_type=ChatType.SUPERGROUP, title: str = "Test <Kvartira & Xona>", user_id: int = 101, first_name: str = "Hojiakbar", username: str = "hojiakbar"):
    msg = MagicMock()
    msg.text = text
    msg.chat = MagicMock()
    msg.chat.id = chat_id
    msg.chat.type = chat_type
    msg.chat.title = title if chat_type != ChatType.PRIVATE else None
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.first_name = first_name
    msg.from_user.full_name = first_name
    msg.from_user.username = username
    msg.bot = MagicMock()

    sent_Log = []

    async def _capture(txt, **kwargs):
        if kwargs.get("parse_mode") == "HTML":
            assert_valid_telegram_html(txt)
        sent_Log.append({"text": txt, "kwargs": kwargs})
        res = MagicMock()
        res.message_id = len(sent_Log) + 100
        return res

    msg.answer = AsyncMock(side_effect=_capture)
    msg.reply = AsyncMock(side_effect=_capture)
    msg._sent = sent_Log
    return msg


def make_fake_callback(data: str, chat_id: int = -100555666, chat_type=ChatType.SUPERGROUP, user_id: int = 102, first_name: str = "Sardor", username: str = ""):
    call = MagicMock()
    call.data = data
    call.from_user = MagicMock()
    call.from_user.id = user_id
    call.from_user.first_name = first_name
    call.from_user.full_name = first_name
    call.from_user.username = username
    call.bot = MagicMock()

    call.message = MagicMock()
    call.message.chat = MagicMock()
    call.message.chat.id = chat_id
    call.message.chat.type = chat_type
    call.message.chat.title = "Test Guruh"

    edits = []

    async def _edit_text(txt, **kwargs):
        if kwargs.get("parse_mode") == "HTML":
            assert_valid_telegram_html(txt)
        edits.append({"text": txt, "kwargs": kwargs})

    call.message.edit_text = AsyncMock(side_effect=_edit_text)
    call.message.edit_reply_markup = AsyncMock()
    call.message.reply = AsyncMock(side_effect=_edit_text)
    call.answer = AsyncMock()
    call._edits = edits
    return call


async def run_all_e2e_tests():
    print("=== TO'LIQ E2E TESTLAR BOSHLANDI ===")
    await init_db()
    storage = MemoryStorage()
    chat_id = -100555666

    # 1. WEBAPP_URL yaroqsiz bo'lganda (http://localhost:8080) va HTTPS bo'lganda get_webapp_keyboard testi
    print("1. get_webapp_keyboard va get_duty_keyboard testi...")
    config.WEBAPP_URL = "http://localhost:8080"
    assert common.get_webapp_keyboard(chat_id) is None
    duty_kb_local = duty_actions.get_duty_keyboard(chat_id, has_temp=False)
    assert duty_kb_local is not None
    assert len(duty_kb_local.inline_keyboard) == 1  # Faqat swap va skip tugmalari, yaroqsiz localhost URL yo'q!

    config.WEBAPP_URL = "https://kvartira.example.com"
    grp_kb = common.get_webapp_keyboard(chat_id)
    assert grp_kb is not None and grp_kb.inline_keyboard[0][0].url == f"https://kvartira.example.com?chat_id={chat_id}"
    priv_kb = common.get_webapp_keyboard(12345)
    assert priv_kb is not None and priv_kb.inline_keyboard[0][0].web_app.url == "https://kvartira.example.com?chat_id=12345"
    duty_kb_https = duty_actions.get_duty_keyboard(chat_id, has_temp=True)
    assert len(duty_kb_https.inline_keyboard) == 3  # swap/skip + reset + webapp
    config.WEBAPP_URL = "http://localhost:8080"
    print("   ✅ get_webapp_keyboard va get_duty_keyboard barcha holatlarda xatosiz ishladi.")

    # 2. FAQAT ISM BILAN (usernamesiz, guruhda yo'q odamlarni) ko'p qatorli /navbatchilar orqali qo'shish
    print("2. Faqat ism bilan navbatchilarni qo'shish (/navbatchilar\\n...) testi...")
    state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=chat_id, user_id=101))
    multiline_cmd = "/navbatchilar\nO'tkirbek\nG'ani Karimov\nMirzo-Ulug'bek\nAli <2-xona>"
    msg = make_fake_message(multiline_cmd, chat_id=chat_id)
    await admin.cmd_navbatchilar(msg, state)
    assert len(msg._sent) == 1
    assert "muvaffaqiyatli saqlandi" in msg._sent[0]["text"]

    members = await queries.get_members(chat_id)
    assert len(members) == 4, f"4 ta a'zo kutilgan, olingan: {members}"
    assert members[0] == {**members[0], "name": "O'tkirbek", "username": ""}
    assert members[1] == {**members[1], "name": "G'ani Karimov", "username": ""}
    assert members[2] == {**members[2], "name": "Mirzo-Ulug'bek", "username": ""}
    assert members[3] == {**members[3], "name": "Ali <2-xona>", "username": ""}
    print("   ✅ Guruhda yo'q (usernamesiz) a'zolar yangi qator orqali to'liq va buzilmasdan saqlandi.")

    # Vergul bilan bir qatorda kiritish testi
    comma_parsed = duty_manager.parse_members_text("Sardor, Jasur, Bekzod")
    assert [m["name"] for m in comma_parsed] == ["Sardor", "Jasur", "Bekzod"]
    assert all(m["username"] == "" for m in comma_parsed)
    print("   ✅ Bir qatorda vergul bilan yozilgan ismlar ham to'g'ri ajratildi.")

    # 3. Vazifalarni yangi qatordan kiritish va barcha ko'rish buyruqlarini (/navbatchi, /jadval, /vazifalar, /holat) tekshirish
    print("3. /vazifalar_sozlash, /navbatchi, /jadval, /vazifalar, /holat testlari...")
    msg_tasks = make_fake_message("/vazifalar_sozlash\nOshxonani & gazni tozalash\nAxlatni olib chiqish", chat_id=chat_id)
    await admin.cmd_vazifalar_sozlash(msg_tasks, state)
    assert "Kunlik vazifalar ro'yxati saqlandi" in msg_tasks._sent[0]["text"]

    msg_nav = make_fake_message("/navbatchi", chat_id=chat_id)
    await group.cmd_navbatchi(msg_nav)
    assert "O'tkirbek" in msg_nav._sent[0]["text"]
    assert "G'ani Karimov" in msg_nav._sent[0]["text"]  # Ertangi navbatchi

    msg_jad = make_fake_message("/jadval", chat_id=chat_id)
    await group.cmd_jadval(msg_jad)
    assert "O'tkirbek" in msg_jad._sent[0]["text"]
    assert "Ali &lt;2-xona&gt;" in msg_jad._sent[0]["text"]

    msg_vaz = make_fake_message("/vazifalar", chat_id=chat_id)
    await group.cmd_vazifalar(msg_vaz)
    assert "Oshxonani &amp; gazni tozalash" in msg_vaz._sent[0]["text"]

    msg_holat = make_fake_message("/holat", chat_id=chat_id)
    await admin.cmd_holat(msg_holat)
    assert "4 nafar" in msg_holat._sent[0]["text"]

    # Shaxsiy chatda ham /navbatchi va /jadval ishlashi testi
    priv_id = 777888
    await queries.set_members(priv_id, [{"name": "Yolg'iz Navbatchi", "username": ""}])
    msg_priv = make_fake_message("/navbatchi", chat_id=priv_id, chat_type=ChatType.PRIVATE)
    await group.cmd_navbatchi(msg_priv)
    assert "Yolg'iz Navbatchi" in msg_priv._sent[0]["text"]
    print("   ✅ /navbatchi, /jadval, /vazifalar, /holat guruhda ham, shaxsiy chatda ham HTML xatosiz ishladi.")

    # 4. SCHEDULER TO'LIQ SIKLI (Baholash + E'lon qilish + Keyingi kunga o'tish — usernamesiz a'zolar bilan!)
    print("4. Scheduler kunlik sikli (baholash + bildirishnoma) testi...")
    await queries.update_group_settings(chat_id, notify_time="08:00", work_days="all", is_active=1)

    mock_bot = MagicMock()
    bot_messages = []

    async def _bot_send(chat_id, text, **kwargs):
        if kwargs.get("parse_mode") == "HTML":
            assert_valid_telegram_html(text)
        bot_messages.append({"chat_id": chat_id, "text": text, "kwargs": kwargs})
        m = MagicMock()
        m.message_id = len(bot_messages) + 500
        return m

    async def _bot_edit(text, chat_id, message_id, **kwargs):
        if kwargs.get("parse_mode") == "HTML":
            assert_valid_telegram_html(text)
        bot_messages.append({"edit": True, "chat_id": chat_id, "text": text})

    mock_bot.send_message = AsyncMock(side_effect=_bot_send)
    mock_bot.edit_message_text = AsyncMock(side_effect=_bot_edit)
    mock_bot.pin_chat_message = AsyncMock()

    tz = ZoneInfo(config.TIMEZONE)

    # 1-kun soat 07:00: hali hech qachon navbatchilik e'lon qilinmagan (last_notified_date == ''), baholash chiqmasligi kerak!
    with patch("services.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 11, 20, 7, 0, tzinfo=tz)
        await scheduler.check_and_send_scheduled_duties(mock_bot)
    assert not any(m["chat_id"] == chat_id for m in bot_messages), "1-kun 07:00 da muddatidan oldin baholash chiqmasligi kerak!"

    # 1-kun soat 08:00: 1-a'zo (O'tkirbek) e'lon qilinishi kerak!
    with patch("services.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 11, 20, 8, 0, tzinfo=tz)
        await scheduler.check_and_send_scheduled_duties(mock_bot)

    day1_msgs = [m for m in bot_messages if m.get("chat_id") == chat_id and not m.get("edit")]
    assert len(day1_msgs) == 1
    assert "BUGUNGI NAVBATCHILIK" in day1_msgs[0]["text"]
    assert "O'tkirbek" in day1_msgs[0]["text"]
    bot_messages.clear()

    # 2-kun soat 07:00: 1-kun navbatchilik qilgan O'tkirbek uchun baholash so'rovi yuborilishi kerak!
    with patch("services.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 11, 21, 7, 0, tzinfo=tz)
        await scheduler.check_and_send_scheduled_duties(mock_bot)

    poll_msgs = [m for m in bot_messages if m.get("chat_id") == chat_id and not m.get("edit")]
    assert len(poll_msgs) == 1
    assert "NAVBATCHILIKNI BAHOLASH VAQTI" in poll_msgs[0]["text"]
    assert "O'tkirbek" in poll_msgs[0]["text"], f"O'tkirbek baholanishi kerak edi, lekin xabar: {poll_msgs[0]['text']}"

    # Anonim ovoz berish testi (O'tkirbekning o'zi bosa olmaydi, boshqalar bosadi)
    active_r = await rating_queries.get_active_rating(chat_id)
    assert active_r is not None
    self_call = make_fake_callback(f"rate:like:{active_r['id']}", chat_id=chat_id, user_id=201, first_name="O'tkirbek", username="")
    await rating.cb_vote(self_call)
    self_call.answer.assert_awaited()
    assert "O'zingizning" in self_call.answer.call_args.args[0]

    voter_call = make_fake_callback(f"rate:like:{active_r['id']}", chat_id=chat_id, user_id=202, first_name="Sardor", username="")
    await rating.cb_vote(voter_call)

    bot_messages.clear()

    # 2-kun soat 08:00: O'tkirbek baholashi yopilib, 2-a'zo (G'ani Karimov) navbatchi deb e'lon qilinishi kerak!
    with patch("services.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 11, 21, 8, 0, tzinfo=tz)
        await scheduler.check_and_send_scheduled_duties(mock_bot)

    day2_edits = [m for m in bot_messages if m.get("chat_id") == chat_id and m.get("edit")]
    day2_sends = [m for m in bot_messages if m.get("chat_id") == chat_id and not m.get("edit")]
    assert len(day2_edits) == 1 and "BAHOLASH YAKUNLANDI" in day2_edits[0]["text"]
    assert len(day2_sends) == 1
    assert "G'ani Karimov" in day2_sends[0]["text"]
    assert "Oldingi navbatchilik bahosi (O'tkirbek)" in day2_sends[0]["text"]
    assert "👍 1 ta" in day2_sends[0]["text"]
    print("   ✅ Scheduler 2 kunlik to'liq sikli (baholash -> ovoz -> yopish -> keyingi navbatchi) 100% aniq ishladi!")

    # /reyting komandasi testi
    msg_reyting = make_fake_message("/reyting", chat_id=chat_id)
    await rating.cmd_reyting(msg_reyting)
    assert "O'tkirbek" in msg_reyting._sent[0]["text"]
    print("   ✅ /reyting komandasi to'g'ri ishladi.")

    # 5. Usernamesiz a'zolar bilan Swap (/almashtirish), Skip (/otkazish), Qaytarish (/qaytarish) va Qayta tuzish (/qayta_tuzish)
    print("5. Usernamesiz a'zolar bilan /almashtirish, /otkazish, /qaytarish, /qayta_tuzish testlari...")
    msg_swap = make_fake_message("/almashtirish", chat_id=chat_id)
    await duty_actions.cmd_almashtirish(msg_swap)
    target_id = members[3]["id"]  # Ali <2-xona>

    pick_call = make_fake_callback(f"swap_to:{target_id}", chat_id=chat_id)
    await duty_actions.callback_swap_pick(pick_call)
    assert "username kiritilmagan" in pick_call._edits[0]["text"]

    # Req ID ni ajratib olib qabul qilish
    kb_swap = pick_call._edits[0]["kwargs"]["reply_markup"]
    acc_data = kb_swap.inline_keyboard[0][0].callback_data
    acc_call = make_fake_callback(acc_data, chat_id=chat_id, user_id=303, first_name="Xonadosh", username="xonadosh")
    await duty_actions.callback_swap_accept(acc_call)
    assert "MUVAFFAQIYATLI ALMASHILDI" in acc_call._edits[0]["text"]

    cur_m, _, _ = await duty_manager.get_current_duty_info(chat_id)
    assert cur_m["name"] == "Ali <2-xona>" and cur_m["is_temporary"] is True

    # /qaytarish
    msg_reset = make_fake_message("/qaytarish", chat_id=chat_id)
    await duty_actions.cmd_qaytarish(msg_reset)
    cur_m, _, _ = await duty_manager.get_current_duty_info(chat_id)
    assert cur_m["name"] == "G'ani Karimov" and cur_m["is_temporary"] is False

    # /qayta_tuzish (reset, reverse, shuffle)
    msg_rebuild = make_fake_message("/qayta_tuzish", chat_id=chat_id)
    await admin.cmd_qayta_tuzish(msg_rebuild)
    for action in ("reverse", "shuffle", "reset"):
        cb_reb = make_fake_callback(f"rebuild_{action}", chat_id=chat_id)
        await admin.callback_rebuild_schedule(cb_reb, state)
        assert len(cb_reb._edits) == 1
    grp_after = await queries.get_group(chat_id)
    assert grp_after["current_index"] == 0 and grp_after["last_notified_date"] == ""
    print("   ✅ Swap, Skip, Qaytarish va Qayta tuzish barcha holatlarda xatosiz ishladi.")

    # 6. Moliya va Bozorlik komandalari (/kassa, /kirim, /chiqim, /xarajat, /ijara, /bozorlik, /bozorlik_qosh)
    print("6. Moliya va Bozorlik komandalari (HTML validatsiya bilan) testi...")
    for cmd_text, handler_fn in [
        ("/kirim 100000 Oylik <fond>", finance.cmd_kirim),
        ("/xarajat 35000 Go'sht & piyoz", finance.cmd_xarajat),
        ("/chiqim 15000 Usta haqi", finance.cmd_chiqim),
        ("/kassa", finance.cmd_kassa),
        ("/bozorlik_qosh Yog' & guruch <5kg>", finance.cmd_bozorlik_qosh),
        ("/bozorlik", finance.cmd_bozorlik),
        ("/ijara", finance.cmd_ijara),
    ]:
        m = make_fake_message(cmd_text, chat_id=chat_id)
        await handler_fn(m)
        assert len(m._sent) == 1
    print("   ✅ /kassa, /kirim, /chiqim, /xarajat, /ijara, /bozorlik, /bozorlik_qosh 100% ishladi.")

    # 7. Web App HTTP API: null username, apostrof ismli ijara toggle, sozlamalarni saqlaganda indeks saqlanishi
    print("7. Web App API chekka holatlar testi...")
    app = create_webapp_app(mock_bot)
    sock_path = os.path.join(tempfile.gettempdir(), f"navbatchi_test_{os.getpid()}.sock")
    if os.path.exists(sock_path):
        os.remove(sock_path)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.UnixSite(runner, sock_path)
    await site.start()

    try:
        conn = aiohttp.UnixConnector(path=sock_path)
        async with aiohttp.ClientSession(connector=conn) as client:
            base = "http://localhost"
            res = await client.post(f"{base}/api/save-group-data", json={
                "chat_id": chat_id,
                "members": [
                    {"name": "O'tkirbek", "username": None},
                    {"name": "G'ani", "username": ""},
                    {"name": "Sardor", "username": "@sardor_uz"}
                ],
                "tasks": ["Pol artish"],
                "settings": {"notify_time": "09:00", "work_days": "all", "is_active": 1}
            })
            assert (await res.json())["success"] is True

            db_mems = await queries.get_members(chat_id)
            assert db_mems[0]["username"] == "", f"None 'None' bo'lib qolmasligi kerak: {db_mems[0]}"
            assert db_mems[2]["username"] == "sardor_uz"

            # Navbatni 1 marta suramiz -> G'ani (index 1)
            await client.post(f"{base}/api/next-duty", json={"chat_id": chat_id})
            cur_m, _, cur_idx = await duty_manager.get_current_duty_info(chat_id)
            assert cur_m["name"] == "G'ani" and cur_idx == 1

            # A'zolar ro'yxatini o'zgartirmasdan faqat vaqtni saqlaymiz -> indeks 0 ga tushib ketmasligi kerak!
            await client.post(f"{base}/api/save-group-data", json={
                "chat_id": chat_id,
                "members": [
                    {"name": "O'tkirbek", "username": ""},
                    {"name": "G'ani", "username": ""},
                    {"name": "Sardor", "username": "sardor_uz"}
                ],
                "tasks": ["Pol artish", "Idish yuvish"],
                "settings": {"notify_time": "09:30", "work_days": "all", "is_active": 1}
            })
            cur_m2, _, cur_idx2 = await duty_manager.get_current_duty_info(chat_id)
            assert cur_m2["name"] == "G'ani" and cur_idx2 == 1, "Faqat sozlama o'zgarganda navbat indeksi saqlanishi kerak!"

            # Apostrof ismli a'zo uchun ijara to'lovini belgilash
            res_rent = await client.post(f"{base}/api/toggle-rent-payment", json={
                "chat_id": chat_id,
                "member_name": "O'tkirbek",
                "amount": 500000
            })
            assert (await res_rent.json())["is_paid"] is True

            # GET /api/group-data va /api/finance-data tekshiruvi
            res_gd = await client.get(f"{base}/api/group-data?chat_id={chat_id}")
            gd_json = await res_gd.json()
            assert gd_json["success"] is True and gd_json["is_admin"] is True
            assert len(gd_json["members"]) == 3

            res_fd = await client.get(f"{base}/api/finance-data?chat_id={chat_id}")
            fd_json = await res_fd.json()
            assert fd_json["success"] is True and fd_json["is_admin"] is True

            # Moliya, Ijara va Bozorlik barcha POST endpointlari testi
            r_inc = await client.post(f"{base}/api/add-fund-income", json={
                "chat_id": chat_id, "member_name": "O'tkirbek", "amount": 200000, "note": None
            })
            assert (await r_inc.json())["success"] is True

            r_wit = await client.post(f"{base}/api/add-fund-withdrawal", json={
                "chat_id": chat_id, "member_name": "G'ani", "amount": 50000, "note": "Naqd"
            })
            assert (await r_wit.json())["success"] is True

            r_exp = await client.post(f"{base}/api/add-expense", json={
                "chat_id": chat_id, "title": "Choy va shakar", "amount": 30000,
                "paid_by": "O'tkirbek", "payment_source": "fund", "category": "Bozorlik"
            })
            assert (await r_exp.json())["success"] is True

            fd_after = await (await client.get(f"{base}/api/finance-data?chat_id={chat_id}")).json()
            exp_id = fd_after["recent_expenses"][0]["id"]
            r_delexp = await client.post(f"{base}/api/delete-expense", json={"chat_id": chat_id, "expense_id": exp_id})
            assert (await r_delexp.json())["success"] is True

            r_reset = await client.post(f"{base}/api/reset-fund", json={"chat_id": chat_id, "clear_all": False, "reset_by": "O'tkirbek"})
            assert (await r_reset.json())["new_balance"] == 0

            r_rset = await client.post(f"{base}/api/update-rent-settings", json={"chat_id": chat_id, "total_amount": 3000000, "due_day": 10})
            assert (await r_rset.json())["success"] is True

            r_shop = await client.post(f"{base}/api/shopping-item", json={"chat_id": chat_id, "action": "add", "title": "Non", "added_by": None})
            shop_id = (await r_shop.json())["item_id"]
            await client.post(f"{base}/api/shopping-item", json={"chat_id": chat_id, "action": "toggle", "item_id": shop_id})
            await client.post(f"{base}/api/shopping-item", json={"chat_id": chat_id, "action": "clear_bought"})

            # Statik fayllar va index.html
            assert (await client.get(f"{base}/")).status == 200
            assert (await client.get(f"{base}/static/app.js")).status == 200
            assert (await client.get(f"{base}/static/style.css")).status == 200
    finally:
        await runner.cleanup()
        if os.path.exists(sock_path):
            os.remove(sock_path)

    print("   ✅ Web App barcha HTTP API endpointlari va statik fayllari xatosiz ishladi.")

    # 8. Qolgan barcha bot buyruqlari (/start, /help, /webapp, /vaqt, /kunlar, /keyingi, /otkazish, /tozalash) va Ijara scheduler testi
    print("8. Qolgan barcha buyruqlar va ijara eslatmasi scheduler testi...")
    for cmd_t, fn in [
        ("/start", common.cmd_start),
        ("/help", common.cmd_help),
        ("/webapp", common.cmd_webapp),
        ("/vaqt 08:30", admin.cmd_vaqt),
        ("/kunlar", admin.cmd_kunlar),
        ("/keyingi", admin.cmd_keyingi),
        ("/otkazish", duty_actions.cmd_otkazish),
        ("/tozalash", admin.cmd_tozalash),
    ]:
        m = make_fake_message(cmd_t, chat_id=chat_id)
        await fn(m)
        assert len(m._sent) >= 1

    # Skip tasdiqlash callback testi (usernamesiz a'zolar bilan)
    db_mems_now = await queries.get_members(chat_id)
    skip_cb = make_fake_callback(f"skip_confirm:{db_mems_now[0]['id']}:{db_mems_now[2]['id']}", chat_id=chat_id)
    await duty_actions.callback_skip_confirm(skip_cb)
    assert "1 MARTAGA O'TKAZIB YUBORILDI" in skip_cb._edits[0]["text"]

    # Ijara eslatmasi (usernamesiz a'zo bilan HTML validatsiyasi)
    bot_messages.clear()
    await finance_queries.update_rent_settings(chat_id, total_amount=3000000, due_day=10, notify_days=3)
    with patch("services.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 11, 9, 10, 0, tzinfo=tz)
        await scheduler.check_and_send_rent_reminders(mock_bot)
    rent_msgs = [m for m in bot_messages if m.get("chat_id") == chat_id]
    assert len(rent_msgs) == 1 and "KVARTIRA IJARASI TO'LOVI ESLATMASI" in rent_msgs[0]["text"]
    print("   ✅ Qolgan barcha komandalar, callbacklar va ijara eslatmasi 100% ishladi.")

    if os.path.exists(TMP_DB):
        os.remove(TMP_DB)

    print("\n🎉 BARCHA E2E TESTLAR 100% XATOSIZ VA MUVAFFAQIYATLI YAKUNLANDI!")


if __name__ == "__main__":
    asyncio.run(run_all_e2e_tests())
