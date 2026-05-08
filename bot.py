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

SYSTEM_PROMPT = """Sen Ottimo Cafe (Toshkentdagi zamonaviy kafe) uchun HR agentisan.
Faqat O'zbek tilida javob ber. Har doim do'stona, aniq va amaliy javob ber.

=== OTTIMO CAFE HAQIDA TO'LIQ MA'LUMOT ===

BO'SH ISH O'RINLARI:
- Barista (alkogolsiz ichimliklar)
- Kassir
- Konditer-sotuvchi

XODIMLARDAN NIMA KUTILADI:
- Ichimliklarni standart asosida sifatli tayyorlash
- Desert va gelatolarni chiroyli, sotiladigan qilib taqdim etish
- Har bir mijozga e'tibor va yaxshi kayfiyat berish

TALABLAR:
- Yosh: 20-35
- Rus tilini bilishi shart
- Shu sohada tajriba bo'lishi afzal
- Chaqqon, halol va mas'uliyatli
- Jamoada ishlashni biladigan
- Mijoz bilan ishlashni yoqtiradigan
- Chekmaydigan va spirtli ichimlik iste'mol qilmaydigan

ISH HAQI VA IMTIYOZLAR:
- Oylik: 120,000 – 250,000 so'm (tajribaga qarab)
- Har 10 kunda oylik beriladi
- Mazali ovqat bepul
- Barqaror ish joyi
- O'sish va rivojlanish imkoniyati

ISH VAQTI (SMENALAR):
- 1-smena: 07:30 – 16:30
- 2-smena: 16:00 – 24:00

MANZILLAR:
- Chilonzor tumani
- Olmazor tumani

BOG'LANISH:
- Telefon: +998 99 060 33 53
- Telegram: @Ottimo_hr

=== RASMIY ANKETA MA'LUMOTLARI ===
Ottimo Cafe ga ishga kirish uchun quyidagi anketa to'ldiriladi:

SHAXSIY MA'LUMOTLAR:
- Ism, Familiya, Sharif
- Tug'ilgan sana
- Millat
- Tug'ilgan joy (viloyat, tuman)
- Doimiy yashash joyi
- Shaxsiy telefon raqami
- Turar joy turi (Dom/Hovli)

TA'LIM:
- Maktab (11-sinf) / Kollej-litsey / Institut-universitet
- O'quv yurti nomi va fakultet
- O'qish yillari

OLDINGI ISH TAJRIBASI:
- Korxona nomi
- Lavozim
- Ishlagan yillari
- Ishdan bo'shash sababi (5 ta ish joyi ko'rsatiladi)

QO'SHIMCHA MA'LUMOTLAR:
- Chet el safari bo'lganmi
- Oilaviy holat (bo'ydoq/turmush qurgan/ajrashgan)
- Oila a'zolari (ism, tug'ilgan sana, ish joyi, telefon)
- Sudlanganmi
- Shaxsiy avtomobil bormi
- Haydovchilik guvohnomasi (A/B/C/D/E)

TIL BILIMI (a'lo/yaxshi/past):
- O'zbek tili
- Rus tili (shart!)
- Ingliz tili

QO'SHIMCHA SAVOLLAR:
- Alohida qobiliyatlari
- Bo'sh vaqtni qanday o'tkazadi
- Kompyuterda ishlash darajasi
- Korxona haqida qayerdan eshitgan
- Kafil shaxs (ismi, aloqasi, ish joyi)
- Oxirgi ish joyidan tavsiya xati
- Kutilayotgan maosh
- Qancha muddatga ishlashni rejalashtiradi
- Ishdan keyin qolib ishlashga rozimi
- Yig'ilishlarda qatnashishga rozimi
- Jamoada ishlash haqida tushunchasi
- Ota-onani chaqirishga rozimi
- Chekadimi (YO'Q bo'lishi shart!)
- Spirtli ichimlik ichadimi (YO'Q bo'lishi shart!)
- Zararli odatlari
- Kelajakdagi maqsadlari
- Sog'liq muammolari

=== HR QOIDALAR ===
- Probatsiya muddati: 1 oy
- Kechikish jarima: 50,000 so'm
- O'zbekiston Mehnat kodeksiga mos ishlaydi"""

MENU_QUESTIONS = {
    "👷 Ishchi qabul qilish": """Ottimo Cafe ga ishga kirmoqchi bo'lgan odamga quyidagilarni tushuntir:
1. Bo'sh ish o'rinlari (Barista, Kassir, Konditer-sotuvchi)
2. Asosiy talablar (yosh, til, tajriba, xulq-atvor)
3. Anketa to'ldirish jarayoni - qanday ma'lumotlar kerak:
   - Shaxsiy ma'lumotlar (ism, familiya, sharif, tug'ilgan sana, yashash joyi, telefon)
   - Ta'lim ma'lumotlari
   - Oldingi ish tajribasi (5 tagacha)
   - Oilaviy holat va oila a'zolari
   - Til bilimi (O'zbek, Rus - shart!, Ingliz)
   - Kompyuter bilimlari
   - Kafil shaxs ma'lumotlari
4. Muhim shartlar: chekmaydigan, spirtli ichimlik iste'mol qilmaydigan
5. Bog'lanish: @Ottimo_hr yoki +998 99 060 33 53
Batafsil va qadamma-qadam tushuntir.""",

    "❓ Savol va Javob": "Ottimo Cafe ga ish qidiruvchilar va xodimlar ko'p beriladigan savollar va javoblarni ro'yxat qilib ber. Anketa, talablar, maosh, ish vaqti haqida.",
    "⏰ Ish vaqti": "Ottimo Cafe da ish vaqti va smenalar haqida batafsil ma'lumot ber: 1-smena 07:30-16:30, 2-smena 16:00-24:00.",
    "💰 Oylik maosh": "Ottimo Cafe da barcha lavozimlardagi oylik maosh (120,000-250,000 so'm), har 10 kunda to'lash, bonus va imtiyozlar haqida batafsil ma'lumot ber.",
    "📝 Ish shartnomasi": "Ottimo Cafe da mehnat shartnomasi qanday tuziladi? Probatsiya (1 oy), asosiy shartlar, huquq va majburiyatlar.",
    "📊 Ish ma'lumotlari": "Ottimo Cafe haqida to'liq ma'lumot: bo'sh ish o'rinlari, talablar, manzillar (Chilonzor, Olmazor), bog'lanish (+998 99 060 33 53, @Ottimo_hr).",
    "🤝 Xodimlar muammolari": "Xodimlar o'rtasidagi mojarolar va muammolarni qanday hal qilish kerak? Ottimo Cafe qoidalari asosida tushuntir.",
    "🔄 Smena vaqti": "Ottimo Cafe smena jadvali: 1-smena 07:30-16:30 va 2-smena 16:00-24:00. Taqsimlash qoidalari va muhim nuqtalar.",
    "⚖️ Mehnat qonunlari": "O'zbekiston mehnat qonunlari bo'yicha Ottimo Cafe xodimlarining asosiy huquq va majburiyatlari.",
    "➕ Qo'shimcha savol": "Foydalanuvchi qo'shimcha savol berishni xohlaydi. Ularni savol berishga taklif qil.",
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
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1500}
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
        f"Men sizga quyidagi masalalarda yordam bera olaman:\n\n"
        f"👷 Ishga qabul va anketa to'ldirish\n"
        f"⏰ Ish vaqti va smenalar\n"
        f"💰 Oylik maosh va imtiyozlar\n"
        f"📝 Mehnat shartnomasi\n"
        f"🤝 Xodimlar bilan muammolar\n\n"
        f"Pastdagi menyudan tanlang yoki savol yozing! 👇"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🆘 *Yordam*\n\n"
        "Menyudan mavzu tanlang yoki o'zingiz savol yozing.\n\n"
        "*Bo'limlar:*\n"
        "👷 Ishchi qabul qilish — anketa va talablar\n"
        "❓ Savol va Javob — tez-tez so'raladigan savollar\n"
        "⏰ Ish vaqti — smena jadvali\n"
        "💰 Oylik maosh — maosh va bonuslar\n"
        "📝 Ish shartnomasi — shartnoma shartlari\n"
        "📊 Ish ma'lumotlari — umumiy ma'lumot\n"
        "🤝 Xodimlar muammolari — mojarolarni hal qilish\n"
        "🔄 Smena vaqti — smena taqsimlash\n"
        "⚖️ Mehnat qonunlari — huquq va majburiyatlar\n"
        "➕ Qo'shimcha savol — boshqa savollar\n\n"
        "*Buyruqlar:*\n"
        "/start — Boshiga qaytish\n"
        "/help — Yordam"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_text == "🗑️ Suhbatni tozalash":
        user_sessions[user_id] = []
        await update.message.reply_text("✅ Suhbat tozalandi!", reply_markup=MAIN_MENU)
        return

    if user_text == "🆘 Yordam":
        await help_command(update, context)
        return

    if user_text == "👨‍💼 Admin":
        text = (
            "👨‍💼 *Admin bo'limi*\n\n"
            "Admin bilan bog'lanish:\n"
            "📱 Telegram: @Ottimo_hr\n"
            "📞 Tel: +998 99 060 33 53\n\n"
            "Ish vaqti: 09:00 - 18:00"
        )
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)
        return

    if user_text == "📞 Qo'llab-quvvatlash":
        text = (
            "📞 *Qo'llab-quvvatlash*\n\n"
            "📱 Telefon: +998 99 060 33 53\n"
            "💬 Telegram: @Ottimo_hr\n\n"
            "📍 Manzillar:\n"
            "• Chilonzor tumani\n"
            "• Olmazor tumani\n\n"
            "Ish vaqti: 07:30 - 24:00"
        )
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)
        return

    if user_text == "➕ Qo'shimcha savol":
        await update.message.reply_text(
            "➕ *Qo'shimcha savol*\n\nSavolingizni yozing, javob beraman! 👇",
            parse_mode='Markdown',
            reply_markup=MAIN_MENU
        )
        return

    if user_text in MENU_QUESTIONS:
        actual_question = MENU_QUESTIONS[user_text]
    else:
        actual_question = user_text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    if user_id not in user_sessions:
        user_sessions[user_id] = []

    try:
        reply = ask_gemini(user_id, actual_question)
        user_sessions[user_id].append({"user": actual_question, "agent": reply})
        await update.message.reply_text(reply, reply_markup=MAIN_MENU)
    except Exception as e:
        logger.error(f"Xato: {e}")
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.", reply_markup=MAIN_MENU)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
