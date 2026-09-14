# 🤖 Telegram Navbatchilik va Vazifalar Boti

Telegram guruhlarida navbatchilik jadvali va kunlik vazifalarni avtomatlashtirish, har kuni belgilangan soatda navbatchini eslatib, xabarni guruhga qadab (pin) qo'yish uchun yaratilgan bot.

---

## 🌟 Asosiy Xususiyatlar

1. **Aylanma navbatchilik (Round-Robin):**
   - Guruh a'zolari navbatma-navbat almashadi.
   - Barcha a'zolar o'tgach, navbat yana 1-a'zodan davom etadi.
2. **Moslashuvchan ro'yxat kiritish:**
   - Admin matn shaklida bittada yoki ketma-ketlikda yuborishi mumkin:
     ```text
     1. @hojiakbar (Hojiakbar)
     2. @nodir (Nodirbek)
     3. Jasur
     ```
3. **Kunlik vazifalar ro'yxati:**
   - Guruhdagi kunlik bajarilishi shart bo'lgan vazifalar ro'yxati navbatchi bilan birga yuboriladi.
4. **Avtomatik Pin (Qadash):**
   - Har kuni belgilangan vaqtda (masalan, 08:00) bot xabarni yuboradi va avtomatik qadab (pin) qo'yadi.
5. **Ish kunlari sozlamasi:**
   - Dushanba - Juma (5 kunlik)
   - Dushanba - Shanba (6 kunlik)
   - Har kuni (7 kunlik)
6. **Favqulodda o'tkazish (`/keyingi`):**
   - Agar bugungi navbatchi dars/ishga kelolmasa, admin bir buyruq bilan navbatni keyingi a'zoga surishi mumkin.

---

## 🚀 Ishga Tushirish Qo'llanmasi

### 1. Bot Tokenini olish
1. Telegramda [@BotFather](https://t.me/BotFather) botiga kiring.
2. `/newbot` buyrug'i orqali yangi bot yarating va berilgan **API Token**ni nusxalab oling.

### 2. `.env` faylini sozlash
Loyiha ichidagi `.env` faylini oching va tokenni yozing:
```env
BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
DB_PATH=navbatchilik.db
DEFAULT_NOTIFY_TIME=08:00
DEFAULT_WORK_DAYS=workdays_sat
```

### 3. Botni ishga tushirish
```bash
./venv/bin/python3 main.py
```
*(yoki tizimda: `python3 main.py`)*

---

## 👥 Botni Guruhda Ishlatish

1. Botni guruhingizga qo'shing.
2. **Muhim:** Botga guruhda **Admin** huquqini bering (ayniqsa *Xabarlarni qadash / Pin messages* huquqi kerak).
3. Guruhda buyruqlar orqali sozlang:
   - `/navbatchilar` — Navbatchilar ro'yxatini yuboring
   - `/vazifalar_sozlash` — Kunlik vazifalarni yuboring
   - `/vaqt 08:00` — Bildirishnoma soatini belgilang
   - `/kunlar` — Ish kunlarini tanlang

---

## 📋 Buyruqlar Ro'yxati

| Buyruq | Kimlar uchun | Tavsif |
|---|---|---|
| `/navbatchi` | Barcha | Bugungi navbatchi va vazifalar ma'lumoti |
| `/jadval` | Barcha | To'liq navbatchilar jadvali va hozirgi navbat |
| `/vazifalar` | Barcha | Guruhdagi kunlik vazifalar ro'yxati |
| `/navbatchilar` | Faqat Admin | Navbatchilar ro'yxatini kiritish/yangilash |
| `/vazifalar_sozlash` | Faqat Admin | Vazifalar ro'yxatini kiritish/yangilash |
| `/keyingi` | Faqat Admin | Navbatni keyingi navbatchiga majburiy surish |
| `/vaqt 08:00` | Faqat Admin | Bildirishnoma yuborish vaqtini o'zgartirish |
| `/kunlar` | Faqat Admin | Bildirishnoma kunlarini sozlash (inline menyu) |
| `/holat` | Faqat Admin | Guruh statistikasi va sozlamalar holati |
| `/tozalash` | Faqat Admin | Navbatchilar yoki vazifalar ro'yxatini tozalash |
| `/help` | Barcha | Qo'llanma |
# navbatchi-bot
# navbatchi-bot
# navbatchi-bot
