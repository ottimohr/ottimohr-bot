import os
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

SYSTEM_PROMPT = """Sen Ottimo Cafe uchun HR agentisan. Faqat O'zbek tilida javob ber.

Ottimo Cafe ma'lumotlari:
- Bo'sh o'rinlar: Barista, Kassir, Konditer-sotuvchi
- Yosh: 20-35, Rus tili shart
- Oylik: 120,000-250,000 so'm, har 10 kunda
- 1-smena: 07:30-16:30, 2-smena: 16:00-24:00
- Manzil: Chilonzor va Olmazor tumanlari
- Tel: +998 99 060 33 53, Telegram: @Ottimo_hr
- Chekmaydigan va spirtli ichimlik iste'mol qilmaydigan bo'lishi shart
- Probatsiya: 1 oy"""

# Tayyor javoblar — Gemini API ga bog'liq emas
STATIC_RESPONSES = {
    "👷 Ishchi qabul qilish": """👷 *ISHCHI QABUL QILISH*

📌 *Bo'sh ish o'rinlari:*
• Barista (alkogolsiz ichimliklar)
• Kassir
• Konditer-sotuvchi

✅ *Talablar:*
• Yosh: 20-35
• Rus tilini bilish (shart!)
• Soha bo'yicha tajriba (afzal)
• Chaqqon, halol, mas'uliyatli
• Chekmaydigan ✖️
• Spirtli ichimlik iste'mol qilmaydigan ✖️

📋 *Anketa qanday to'ldiriladi?*

*1. Shaxsiy ma'lumotlar:*
— Ism, Familiya, Sharif
— Tug'ilgan sana va joy
— Yashash manzili
— Telefon raqami

*2. Ta'lim:*
— Maktab / Kollej / Universitet
— O'quv yurti nomi, fakultet

*3. Ish tajribasi (5 tagacha):*
— Korxona nomi
— Lavozim
— Ishlagan yillari
— Ishdan bo'shash sababi

*4. Oilaviy holat:*
— Bo'ydoq / Turmush qurgan / Ajrashgan
— Oila a'zolari ma'lumotlari

*5. Til bilimi:*
— O'zbek tili
— Rus tili ⭐ (shart!)
— Ingliz tili

*6. Qo'shimcha:*
— Kompyuter bilimlari
— Haydovchilik guvohnomasi
— Kafil shaxs ma'lumotlari
— Kutilayotgan maosh
— Zararli odatlar (chekish, alkogol — YO'Q bo'lishi shart!)

📞 *Bog'lanish:*
Tel: +998 99 060 33 53
Telegram: @Ottimo_hr""",

    "⏰ Ish vaqti": """⏰ *ISH VAQTI*

🕐 *1-smena:* 07:30 — 16:30
🕔 *2-smena:* 16:00 — 24:00

📌 *Muhim qoidalar:*
• Smenaga 10 daqiqa oldin kelish shart
• Kechikish uchun jarima: 50,000 so'm
• Smena almashtirish faqat menejer ruxsati bilan
• Ish kiyimi smenaga kelganda kiyiladi

🍽️ *Ovqatlanish:*
• Xodimlar uchun bepul ovqat
• Smena davomida belgilangan tanaffus

📅 *Dam olish:*
• Har oyda belgilangan dam olish kunlari
• Jadval oldindan e'lon qilinadi""",

    "🔄 Smena vaqti": """🔄 *SMENA JADVALI*

┌─────────────────────────────┐
│ 1-SMENA: 07:30 — 16:30     │
│ 2-SMENA: 16:00 — 24:00     │
└─────────────────────────────┘

📋 *Smena taqsimlash qoidalari:*
• Jadval har hafta tuziladi
• Smena o'zgarishi 1 kun oldin xabar beriladi
• Almashtirish faqat menejer orqali
• Ikkala smena xodimlarga navbat bilan beriladi

⚠️ *Muhim:*
• Smenaga kech qolish — 50,000 so'm jarima
• Sababsiz kelmagan kun — ish haqidan ushlanadi
• 3 marta kechikish — ogohlantirish

📞 Smena haqida: @Ottimo_hr""",

    "💰 Oylik maosh": """💰 *OYLIK MAOSH VA IMTIYOZLAR*

💵 *Maosh (tajribaga qarab):*
• Barista: 150,000 — 200,000 so'm
• Kassir: 120,000 — 160,000 so'm  
• Konditer-sotuvchi: 150,000 — 250,000 so'm

🗓️ *To'lov tartibi:*
• Har 10 kunda bir marta to'lanadi
• Probatsiya davrida asosiy maosh

🎁 *Imtiyozlar:*
• Bepul ovqat (har smena)
• O'sish va rivojlanish imkoniyati
• Barqaror ish joyi
• Jamoaviy tadbirlar

⚠️ *Jarimalar:*
• Kechikish: 50,000 so'm
• Sababsiz kelmaslik: maoshdan ushlanadi""",

    "📝 Ish shartnomasi": """📝 *ISH (MEHNAT) SHARTNOMASI*

📌 *Shartnoma shartlari:*
• Rasmiy mehnat shartnomasi tuziladi
• O'zbekiston Mehnat kodeksi asosida
• Probatsiya muddati: 1 oy

📋 *Kerakli hujjatlar:*
• Pasport (nusxa)
• Mehnat daftarchasi (agar bo'lsa)
• Diplom yoki attestat
• 3x4 fotosurat

✅ *Xodim huquqlari:*
• Belgilangan maosh o'z vaqtida to'lanadi
• Mehnat ta'tili (yillik)
• Ijtimoiy sug'urta
• Xavfsiz ish sharoiti

⚠️ *Xodim majburiyatlari:*
• Ish tartibiga rioya qilish
• Kafe standartlarini saqlash
• Mijozlarga sifatli xizmat ko'rsatish
• Sir saqlash

📞 Shartnoma haqida: @Ottimo_hr""",

    "📊 Ish ma'lumotlari": """📊 *OTTIMO CAFE HAQIDA*

🏢 *Biz haqimizda:*
Ottimo — Toshkentdagi zamonaviy kafe. Bizning vazifamiz mijozlarga nafaqat desert, balki kayfiyat va zavq ulashish!

📍 *Manzillar:*
• Chilonzor tumani
• Olmazor tumani

👥 *Jamoamiz:*
• 25+ xodim
• Do'stona muhit
• Professional jamoa

💼 *Bo'sh o'rinlar:*
• Barista ⭐
• Kassir ⭐
• Konditer-sotuvchi ⭐

🌟 *Nima taklif qilamiz:*
• Oylik: 120,000 — 250,000 so'm
• Har 10 kunda to'lov
• Bepul ovqat
• Kasb o'rganish imkoniyati
• Barqaror ish

📞 *Bog'lanish:*
Tel: +998 99 060 33 53
Telegram: @Ottimo_hr""",

    "🤝 Xodimlar muammolari": """🤝 *XODIMLAR BILAN MUAMMOLAR*

📋 *Muammo hal qilish tartibi:*

*1-qadam:* Muammoni bevosita hamkasbingiz bilan hal qiling

*2-qadam:* Hal bo'lmasa — smena menejeriga murojaat qiling

*3-qadam:* Menejer ham hal qila olmasa — HR ga yozing:
📱 @Ottimo_hr

⚠️ *Qoidalar:*
• Ish joyida janjal — MUTLAQO MAN!
• Muammolarni mijozlar oldida muhokama qilmang
• Har qanday shikoyat yozma shaklda qabul qilinadi

✅ *HR kafolat beradi:*
• Har bir murojaat ko'rib chiqiladi
• Adolatli qaror qabul qilinadi
• Sir saqlash kafolatlanadi

📞 HR bilan bog'lanish:
Tel: +998 99 060 33 53
Telegram: @Ottimo_hr""",

    "⚖️ Mehnat qonunlari": """⚖️ *MEHNAT QONUNLARI*

📌 *O'zbekiston Mehnat Kodeksi asosida:*

✅ *Xodim HUQUQLARI:*
• Belgilangan maosh o'z vaqtida olish
• Yillik mehnat ta'tili (15-21 ish kuni)
• Kasallik varag'i (to'liq to'lanadi)
• Xavfsiz ish sharoiti
• Rasmiy mehnat shartnomasi
• Ijtimoiy sug'urta

⚠️ *Xodim MAJBURIYATLARI:*
• Ish tartibiga rioya qilish
• Ish joyiga o'z vaqtida kelish
• Kafe mulkiga ehtiyotkorlik bilan munosabat
• Maxfiy ma'lumotlarni oshkor etmaslik

🚫 *MAN ETILGAN:*
• Ish vaqtida telefonda uzoq gaplashish
• Ish joyida chekish
• Spirtli ichimlik iste'mol qilish
• Mijozlarga qo'pollik

📞 Savollar uchun: @Ottimo_hr""",

    "❓ Savol va Javob": """❓ *KO'P BERILADIGAN SAVOLLAR*

*❓ Qanday ish o'rinlari bor?*
✅ Barista, Kassir, Konditer-sotuvchi

*❓ Yosh chegarasi qanday?*
✅ 20 dan 35 yoshgacha

*❓ Tajriba shart ekanmi?*
✅ Afzal, lekin o'rgatamiz

*❓ Rus tili nima uchun shart?*
✅ Mijozlarning ko'pi rus tilida muloqot qiladi

*❓ Oylik qancha?*
✅ 120,000 — 250,000 so'm (tajribaga qarab)

*❓ Maosh qachon beriladi?*
✅ Har 10 kunda bir marta

*❓ Ish vaqti qanday?*
✅ 1-smena: 07:30-16:30 / 2-smena: 16:00-24:00

*❓ Probatsiya qancha davom etadi?*
✅ 1 oy

*❓ Ovqat beriladi?*
✅ Ha, bepul!

*❓ Qayerda joylashgan?*
✅ Chilonzor va Olmazor tumanlarida

*❓ Qanday murojaat qilish kerak?*
✅ @Ottimo_hr yoki +998 99 060 33 53"""
}

MAIN_MENU = ReplyKeyboardMarkup([
    ["👷 Ishchi qabul qilish", "❓ Savol va Javob", "⏰ Ish vaqti"],
    ["💰 Oylik maosh", "📝 Ish shartnomasi", "📊 Ish ma'lumotlari"],
    ["🤝 Xodimlar muammolari", "🔄 Smena vaqti", "⚖️ Mehnat qonunlari"],
    ["👨‍💼 Admin", "📞 Qo'llab-quvvatlash", "➕ Qo'shimcha savol"],
    ["🆘 Yordam", "🗑️ Suhbatni tozalash"]
], resize_keyboard=True)

user_sessions = {}

def ask_gemini(user_id, user_text):
    history = user_sessions.get(user_id, [])
    history_text = ""
    if history:
        history_text = "\n\nOldingi suhbat:\n" + "\n".join([
            f"Foydalanuvchi: {h['user']}\nAgent: {h['agent']}"
            for h in history[-5:]
        ])
    full_prompt = SYSTEM_PROMPT + history_text + f"\n\nFoydalanuvchi: {user_text}\nAgent:"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Foydalanuvchi"
    text = (
        f"👋 Salom, *{user_name}*!\n\n"
        f"🏢 *OTTIMO CAFE HR AGENTIGA XUSH KELIBSIZ!*\n\n"
        f"Quyidagi bo'limlardan birini tanlang yoki savol yozing 👇"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🆘 *Yordam*\n\n"
        "Menyudan mavzu tanlang yoki o'zingiz savol yozing!\n\n"
        "👷 Ishchi qabul qilish\n"
        "❓ Savol va Javob\n"
        "⏰ Ish vaqti\n"
        "💰 Oylik maosh\n"
        "📝 Ish shartnomasi\n"
        "📊 Ish ma'lumotlari\n"
        "🤝 Xodimlar muammolari\n"
        "🔄 Smena vaqti\n"
        "⚖️ Mehnat qonunlari"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    # Suhbatni tozalash
    if user_text == "🗑️ Suhbatni tozalash":
        user_sessions[user_id] = []
        await update.message.reply_text("✅ Suhbat tozalandi!", reply_markup=MAIN_MENU)
        return

    # Yordam
    if user_text == "🆘 Yordam":
        await help_command(update, context)
        return

    # Admin
    if user_text == "👨‍💼 Admin":
        await update.message.reply_text(
            "👨‍💼 *Admin*\n\n📱 Telegram: @Ottimo_hr\n📞 Tel: +998 99 060 33 53\n\nIsh vaqti: 09:00-18:00",
            parse_mode='Markdown', reply_markup=MAIN_MENU
        )
        return

    # Qo'llab-quvvatlash
    if user_text == "📞 Qo'llab-quvvatlash":
        await update.message.reply_text(
            "📞 *Qo'llab-quvvatlash*\n\n📱 Tel: +998 99 060 33 53\n💬 Telegram: @Ottimo_hr\n\n📍 Chilonzor va Olmazor tumanlari",
            parse_mode='Markdown', reply_markup=MAIN_MENU
        )
        return

    # Qo'shimcha savol
    if user_text == "➕ Qo'shimcha savol":
        await update.message.reply_text(
            "➕ Savolingizni yozing, javob beraman! 👇",
            reply_markup=MAIN_MENU
        )
        return

    # Tayyor javoblar — tugma bosilganda
    if user_text in STATIC_RESPONSES:
        await update.message.reply_text(
            STATIC_RESPONSES[user_text],
            parse_mode='Markdown',
            reply_markup=MAIN_MENU
        )
        return

    # Erkin savol — Gemini ga yuborish
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    if user_id not in user_sessions:
        user_sessions[user_id] = []
    try:
        reply = ask_gemini(user_id, user_text)
        user_sessions[user_id].append({"user": user_text, "agent": reply})
        await update.message.reply_text(reply, reply_markup=MAIN_MENU)
    except Exception as e:
        logger.error(f"Xato: {e}")
        await update.message.reply_text(
            "⚠️ Xatolik yuz berdi. Iltimos @Ottimo_hr ga murojaat qiling.",
            reply_markup=MAIN_MENU
        )

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
