import os
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_USERNAME = "mr_jalilov7"

# ===================== ANKETA SAVOLLARI =====================
ANKETA_STEPS = [
    ("ism", "👤 *1/15* — Ismingizni kiriting:\n_(Masalan: Ibrohim)_"),
    ("familiya", "👤 *2/15* — Familiyangizni kiriting:\n_(Masalan: Karimov)_"),
    ("sharif", "👤 *3/15* — Sharifingizni kiriting:\n_(Masalan: Aliyevich)_"),
    ("tug_sana", "📅 *4/15* — Tug'ilgan sanangiz:\n_(Masalan: 15.03.2000)_"),
    ("millat", "🌍 *5/15* — Millatingiz:\n_(Masalan: O'zbek)_"),
    ("yashash", "🏠 *6/15* — Doimiy yashash manzilingiz:\n_(Tuman, ko'cha, uy)_"),
    ("telefon", "📱 *7/15* — Telefon raqamingiz:\n_(Masalan: +998 90 123 45 67)_"),
    ("talim", "🎓 *8/15* — Ta'lim darajangiz:\n_(Maktab / Kollej / Universitet)_"),
    ("tajriba", "💼 *9/15* — Oldingi ish tajribangiz:\n_(Korxona nomi, lavozim, yillar. Yo'q bo'lsa — Yo'q deb yozing)_"),
    ("rus_tili", "🗣️ *10/15* — Rus tilini bilish darajangiz:\n_(A'lo / Yaxshi / Past / Bilmayman)_"),
    ("ingliz_tili", "🗣️ *11/15* — Ingliz tilini bilish darajangiz:\n_(A'lo / Yaxshi / Past / Bilmayman)_"),
    ("kompyuter", "💻 *12/15* — Kompyuterda ishlash darajangiz:\n_(Erkin / O'rta / Bilmayman)_"),
    ("lavozim", "🎯 *13/15* — Qaysi lavozimga murojaat qilmoqchisiz?\n_(Barista / Kassir / Konditer-sotuvchi)_"),
    ("maosh", "💰 *14/15* — Kutilayotgan oylik maoshingiz:\n_(Masalan: 200,000 so'm)_"),
    ("qoshimcha", "📝 *15/15* — Qo'shimcha ma'lumot yoki savol:\n_(Yo'q bo'lsa — Yo'q deb yozing)_"),
]

# ===================== STATIK JAVOBLAR =====================
STATIC_RESPONSES = {
    "⏰ Ish vaqti": """⏰ *ISH VAQTI*

🕐 *1-smena:* 07:30 — 16:30
🕔 *2-smena:* 16:00 — 24:00

📅 *Smena almashinuvi:*
• Smena jadvali har hafta yangilanadi
• Dushanba kuni keyingi hafta jadvali e'lon qilinadi
• Smena o'zgarishi kamida 1 kun oldin xabar beriladi
• Almashtirish faqat menejer ruxsati bilan

⚠️ *Muhim qoidalar:*
• Smenaga 10 daqiqa oldin kelish shart
• Kechikish jarima: 50,000 so'm
• Sababsiz kelmaslik — maoshdan ushlanadi
• 3 marta kechikish — ogohlantirish beriladi

🍽️ *Ovqatlanish:*
• Har smena bepul ovqat beriladi
• Belgilangan tanaffus vaqtida""",

    "🔄 Smena vaqti": """🔄 *SMENA JADVALI*

┌──────────────────────────┐
│ 1-SMENA: 07:30 — 16:30  │
│ 2-SMENA: 16:00 — 24:00  │
└──────────────────────────┘

📅 *Smena qachon almashinadi?*
• Jadval har *dushanba* kuni e'lon qilinadi
• Har xodim haftada kamida 1 ta dam olish kuni oladi
• Ikkala smena navbat bilan taqsimlanadi
• Dam olish kunlari oldindan belgilanadi

⚠️ *Qoidalar:*
• Smena o'zgartirish — menejer orqali
• Kechikish: 50,000 so'm jarima
• Smenani o'z vaqtida topshirish shart

📞 Jadval haqida: @Ottimo_hr""",

    "💰 Oylik maosh": """💰 *OYLIK MAOSH VA IMTIYOZLAR*

💵 *Maosh (tajribaga qarab):*
• Barista: 150,000 — 200,000 so'm
• Kassir: 120,000 — 160,000 so'm
• Konditer-sotuvchi: 150,000 — 250,000 so'm

🗓️ *To'lov tartibi:*
• Har *10 kunda* bir marta to'lanadi
• Probatsiya davrida asosiy maosh

🎁 *Imtiyozlar:*
• Bepul ovqat (har smena) 🍽️
• Kasb o'rganish imkoniyati 📚
• Barqaror ish joyi 🏢
• O'sish va rivojlanish 📈

⚠️ *Jarimalar:*
• Kechikish: 50,000 so'm
• Sababsiz kelmaslik: maoshdan ushlanadi""",

    "📝 Ish shartnomasi": """📝 *ISH (MEHNAT) SHARTNOMASI*

📋 *Kerakli hujjatlar:*
• Pasport (nusxa)
• Mehnat daftarchasi (agar bo'lsa)
• Diplom yoki attestat
• 3x4 fotosurat (2 dona)

⏳ *Probatsiya:* 1 oy

✅ *Xodim huquqlari:*
• Belgilangan maosh o'z vaqtida to'lanadi
• Yillik mehnat ta'tili
• Ijtimoiy sug'urta
• Xavfsiz ish sharoiti

⚠️ *Xodim majburiyatlari:*
• Ish tartibiga rioya qilish
• Kafe standartlarini saqlash
• Mijozlarga sifatli xizmat
• Sir saqlash

📞 Shartnoma haqida: @Ottimo_hr""",

    "📊 Ish ma'lumotlari": """📊 *OTTIMO CAFE HAQIDA*

☕ *Biz kim biz?*
Ottimo — Toshkentdagi zamonaviy premium kafe. Bizning vazifamiz — mijozlarga nafaqat mazali taom, balki kayfiyat va zavq ulashish!

🌟 *Nima uchun Ottimo?*
✅ Rasmiy ish joyi va mehnat shartnomasi
✅ Har 10 kunda maosh
✅ Bepul ovqat har kuni
✅ Professional jamoa (25+ xodim)
✅ Kasb o'rganish va rivojlanish
✅ Barqaror va qulay ish muhiti
✅ Karyera o'sishi imkoniyati
✅ Do'stona va qo'llab-quvvatlovchi muhit
✅ Zamonaviy ish sharoiti
✅ Tajriba orttirishga keng imkon

💼 *Bo'sh o'rinlar:*
• ☕ Barista
• 💳 Kassir
• 🍰 Konditer-sotuvchi

📍 *Filiallar:*

1️⃣ *Nukus kinoteatri yonida*
📌 Toshkent, Shifer ko'chasi, 71

2️⃣ *Parus ostida*
📌 Toshkent, Katartal ko'chasi, 60A/1

3️⃣ *Talant International School ro'parasida*
📌 Toshkent, Mirzo Ulug'bek tumani, Buyuk Ipak Yo'li, 31

📞 *Bog'lanish:*
Tel: +998 99 060 33 53
Telegram: @Ottimo_hr""",

    "🤝 Xodimlar muammolari": """🤝 *XODIMLAR BILAN MUAMMOLAR*

📋 *Muammo hal qilish tartibi:*

*1-qadam:* Hamkasbingiz bilan muloqot qiling
*2-qadam:* Hal bo'lmasa — smena menejeriga
*3-qadam:* HR ga yozing: @Ottimo_hr

⚠️ *Qoidalar:*
• Ish joyida janjal — MAN ETILGAN!
• Muammolarni mijozlar oldida muhokama qilmang
• Har qanday shikoyat yozma shaklda

✅ *HR kafolat beradi:*
• Har bir murojaat ko'rib chiqiladi
• Adolatli qaror qabul qilinadi
• Sir saqlash kafolatlanadi

📞 +998 99 060 33 53 | @Ottimo_hr""",

    "⚖️ Mehnat qonunlari": """⚖️ *MEHNAT QONUNLARI*

✅ *Xodim HUQUQLARI:*
• Belgilangan maosh o'z vaqtida olish
• Yillik mehnat ta'tili (15-21 ish kuni)
• Kasallik varag'i to'liq to'lanadi
• Xavfsiz ish sharoiti
• Rasmiy mehnat shartnomasi
• Ijtimoiy sug'urta

⚠️ *Xodim MAJBURIYATLARI:*
• Ish tartibiga rioya qilish
• O'z vaqtida kelish
• Kafe mulkiga ehtiyotkorlik
• Maxfiylikni saqlash

🚫 *MAN ETILGAN:*
• Ish vaqtida uzoq telefon suhbati
• Chekish
• Spirtli ichimlik
• Mijozlarga qo'pollik

📞 @Ottimo_hr""",

    "❓ Savol va Javob": """❓ *KO'P BERILADIGAN SAVOLLAR*

*❓ Qanday ish o'rinlari bor?*
✅ Barista, Kassir, Konditer-sotuvchi

*❓ Yosh chegarasi?*
✅ 20-35 yosh

*❓ Tajriba shart ekanmi?*
✅ Afzal, lekin o'rgatamiz

*❓ Rus tili shart ekanmi?*
✅ Ha, shart (mijozlar uchun)

*❓ Oylik qancha?*
✅ 120,000 — 250,000 so'm

*❓ Maosh qachon beriladi?*
✅ Har 10 kunda

*❓ Ish vaqti?*
✅ 07:30-16:30 yoki 16:00-24:00

*❓ Probatsiya?*
✅ 1 oy

*❓ Ovqat beriladi?*
✅ Ha, bepul!

*❓ Qayerda joylashgan?*
✅ Nukus kino, Parus, Talant school yonida

*❓ Murojaat?*
✅ @Ottimo_hr | +998 99 060 33 53"""
}

MAIN_MENU = ReplyKeyboardMarkup([
    ["👷 Ishchi qabul qilish", "❓ Savol va Javob", "⏰ Ish vaqti"],
    ["💰 Oylik maosh", "📝 Ish shartnomasi", "📊 Ish ma'lumotlari"],
    ["🤝 Xodimlar muammolari", "🔄 Smena vaqti", "⚖️ Mehnat qonunlari"],
    ["👨‍💼 Admin", "📞 Qo'llab-quvvatlash", "➕ Qo'shimcha savol"],
    ["🆘 Yordam", "🗑️ Suhbatni tozalash"]
], resize_keyboard=True)

# Foydalanuvchi holatlari
user_sessions = {}
user_anketa = {}  # anketa jarayoni

def get_anketa_step(user_id):
    return user_anketa.get(user_id, {}).get("step", None)

async def start_anketa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_anketa[user_id] = {"step": 0, "data": {}}
    key, question = ANKETA_STEPS[0]
    await update.message.reply_text(
        "📋 *OTTIMO CAFE — ARIZA ANKETA*\n\n"
        "Savollarni birma-bir javob bering.\n"
        "Bekor qilish uchun /bekor yozing.\n\n" + question,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )

async def process_anketa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "/bekor":
        user_anketa.pop(user_id, None)
        await update.message.reply_text("❌ Anketa bekor qilindi.", reply_markup=MAIN_MENU)
        return

    step_data = user_anketa[user_id]
    current_step = step_data["step"]
    key, _ = ANKETA_STEPS[current_step]
    step_data["data"][key] = text

    next_step = current_step + 1

    if next_step < len(ANKETA_STEPS):
        step_data["step"] = next_step
        _, next_question = ANKETA_STEPS[next_step]
        await update.message.reply_text(next_question, parse_mode='Markdown')
    else:
        # Barcha savollar tugadi — tasdiqlash
        data = step_data["data"]
        summary = (
            "✅ *ANKETANGIZ TAYYOR!*\n\n"
            f"👤 Ism: {data.get('ism')} {data.get('familiya')} {data.get('sharif')}\n"
            f"📅 Tug'ilgan sana: {data.get('tug_sana')}\n"
            f"🌍 Millat: {data.get('millat')}\n"
            f"🏠 Manzil: {data.get('yashash')}\n"
            f"📱 Telefon: {data.get('telefon')}\n"
            f"🎓 Ta'lim: {data.get('talim')}\n"
            f"💼 Tajriba: {data.get('tajriba')}\n"
            f"🗣️ Rus tili: {data.get('rus_tili')}\n"
            f"🗣️ Ingliz tili: {data.get('ingliz_tili')}\n"
            f"💻 Kompyuter: {data.get('kompyuter')}\n"
            f"🎯 Lavozim: {data.get('lavozim')}\n"
            f"💰 Kutilayotgan maosh: {data.get('maosh')}\n"
            f"📝 Qo'shimcha: {data.get('qoshimcha')}\n\n"
            "Tasdiqlaysizmi?"
        )
        confirm_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data="anketa_confirm"),
                InlineKeyboardButton("❌ Bekor qilish", callback_data="anketa_cancel")
            ]
        ])
        await update.message.reply_text(summary, parse_mode='Markdown', reply_markup=confirm_keyboard)

async def anketa_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "anketa_confirm":
        data = user_anketa.get(user_id, {}).get("data", {})
        user_name = query.from_user.first_name or ""
        username = query.from_user.username or "username_yoq"

        msg = (
            "📋 *YANGI ARIZA KELDI!*\n\n"
            f"👤 {data.get('ism')} {data.get('familiya')} {data.get('sharif')}\n"
            f"📅 {data.get('tug_sana')}\n"
            f"🌍 {data.get('millat')}\n"
            f"🏠 {data.get('yashash')}\n"
            f"📱 {data.get('telefon')}\n"
            f"🎓 {data.get('talim')}\n"
            f"💼 {data.get('tajriba')}\n"
            f"🗣️ Rus: {data.get('rus_tili')} | Ingliz: {data.get('ingliz_tili')}\n"
            f"💻 Kompyuter: {data.get('kompyuter')}\n"
            f"🎯 Lavozim: {data.get('lavozim')}\n"
            f"💰 Maosh kutilmasi: {data.get('maosh')}\n"
            f"📝 Qo'shimcha: {data.get('qoshimcha')}\n\n"
            f"📲 Telegram: @{username}"
        )

        # Adminga yuborish
        try:
            await context.bot.send_message(
                chat_id=f"@{ADMIN_USERNAME}",
                text=msg,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Admin ga yuborishda xato: {e}")

        user_anketa.pop(user_id, None)
        await query.edit_message_text(
            "✅ *Anketangiz muvaffaqiyatli yuborildi!*\n\n"
            "Tez orada @Ottimo_hr siz bilan bog'lanadi.\n"
            "Ko'rib chiqish muddati: 1-3 ish kuni.\n\n"
            "Rahmat! 🙏",
            parse_mode='Markdown'
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="Bosh menyuga qaytish uchun /start bosing.",
            reply_markup=MAIN_MENU
        )

    elif query.data == "anketa_cancel":
        user_anketa.pop(user_id, None)
        await query.edit_message_text("❌ Anketa bekor qilindi.")
        await context.bot.send_message(
            chat_id=user_id,
            text="Bosh menyuga qaytdingiz.",
            reply_markup=MAIN_MENU
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Foydalanuvchi"
    await update.message.reply_text(
        f"👋 Salom, *{user_name}*!\n\n"
        f"🏢 *OTTIMO CAFE HR AGENTIGA XUSH KELIBSIZ!*\n\n"
        f"Quyidagi bo'limlardan birini tanlang yoki savol yozing 👇",
        parse_mode='Markdown',
        reply_markup=MAIN_MENU
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Yordam*\n\n"
        "👷 Ishchi qabul — anketa to'ldirish\n"
        "❓ Savol va Javob — FAQ\n"
        "⏰ Ish vaqti — smena jadvali\n"
        "💰 Oylik maosh — maosh va bonuslar\n"
        "📝 Ish shartnomasi — shartlar\n"
        "📊 Ish ma'lumotlari — filiallar va afzalliklar\n"
        "🤝 Xodimlar muammolari — yordam\n"
        "🔄 Smena vaqti — jadval\n"
        "⚖️ Mehnat qonunlari — huquqlar",
        parse_mode='Markdown',
        reply_markup=MAIN_MENU
    )

def ask_gemini(user_id, user_text):
    history = user_sessions.get(user_id, [])
    history_text = ""
    if history:
        history_text = "\n\nOldingi suhbat:\n" + "\n".join([
            f"Foydalanuvchi: {h['user']}\nAgent: {h['agent']}"
            for h in history[-5:]
        ])
    system = "Sen Ottimo Cafe HR agentisan. Faqat O'zbek tilida javob ber. Do'stona va aniq javob ber."
    full_prompt = system + history_text + f"\n\nFoydalanuvchi: {user_text}\nAgent:"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    # Anketa jarayonida bo'lsa
    if user_id in user_anketa:
        await process_anketa(update, context)
        return

    # Suhbatni tozalash
    if user_text == "🗑️ Suhbatni tozalash":
        user_sessions[user_id] = []
        await update.message.reply_text("✅ Suhbat tozalandi!", reply_markup=MAIN_MENU)
        return

    if user_text == "🆘 Yordam":
        await help_command(update, context)
        return

    if user_text == "👨‍💼 Admin":
        await update.message.reply_text(
            "👨‍💼 *Admin*\n\n📱 Telegram: @Ottimo_hr\n📞 +998 99 060 33 53\n\nIsh vaqti: 09:00-18:00",
            parse_mode='Markdown', reply_markup=MAIN_MENU
        )
        return

    if user_text == "📞 Qo'llab-quvvatlash":
        await update.message.reply_text(
            "📞 *Qo'llab-quvvatlash*\n\n📱 +998 99 060 33 53\n💬 @Ottimo_hr\n\n"
            "📍 *Filiallar:*\n"
            "1️⃣ Nukus kino yonida — Shifer ko'chasi, 71\n"
            "2️⃣ Parus ostida — Katartal ko'chasi, 60A/1\n"
            "3️⃣ Talant school ro'parasida — Buyuk Ipak Yo'li, 31",
            parse_mode='Markdown', reply_markup=MAIN_MENU
        )
        return

    if user_text == "➕ Qo'shimcha savol":
        await update.message.reply_text("➕ Savolingizni yozing! 👇", reply_markup=MAIN_MENU)
        return

    # Ishchi qabul — anketa boshlash
    if user_text == "👷 Ishchi qabul qilish":
        await start_anketa(update, context)
        return

    # Boshqa tugmalar — statik javob
    if user_text in STATIC_RESPONSES:
        await update.message.reply_text(
            STATIC_RESPONSES[user_text],
            parse_mode='Markdown',
            reply_markup=MAIN_MENU
        )
        return

    # Erkin savol — Gemini
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
            "⚠️ Xatolik yuz berdi. @Ottimo_hr ga murojaat qiling.",
            reply_markup=MAIN_MENU
        )

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(anketa_callback, pattern="^anketa_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
