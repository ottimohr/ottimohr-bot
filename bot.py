import os
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID", "")

SYSTEM_PROMPT = """Sen Ottimo Cafe (Toshkentdagi zamonaviy italyan-style kafe) uchun HR agentisan.
Faqat O'zbek tilida javob ber.

Ottimo Cafe haqida:
- 25 xodim ishlaydi
- Lavozimlari: barista, ofitsiant, oshpaz, kassir, menejer, tozalovchi
- Ish vaqti: 08:00-22:00 (2 smena: 08:00-15:00 va 15:00-22:00)
- Probatsiya muddati: 1 oy
- Ish haqi: Barista 3-4 mln, Ofitsiant 2.5-3.5 mln, Oshpaz 4-6 mln, Menejer 6-8 mln UZS
- O'zbekiston Mehnat kodeksiga mos ishlaydi
- Har oyda 2 kun dam olish
- Kechikish jarima: 50,000 UZS

HR vazifalaring:
1. Xodim qabul - CV, intervyu, lavozim talablari
2. Onboarding - yangi xodimga yo'riqnoma
3. Smena jadvali - taqsimlash, dam olish
4. Ish haqi - hisoblash, bonus, jarima
5. Ichki qoidalar - tartib, standartlar
6. Mojarolar - hal qilish
7. Mehnat qonunlari - O'zbekiston qonunchiligi

Har doim do'stona, aniq va amaliy javob ber. Kerak bo'lsa ro'yxat yoki jadval ko'rinishida yoz."""

# Menyu savollari
MENU_QUESTIONS = {
    "👷 Ishchi qabul qilish": "Ottimo Cafe da yangi xodim qabul qilish jarayonini batafsil tushuntir. Qanday qadamlar, hujjatlar va talablar bor?",
    "❓ Savol va Javob": "Ottimo Cafe xodimlari ko'p beriladigan savollarni va ularga javoblarni ro'yxat qilib ber.",
    "⏰ Ish vaqti": "Ottimo Cafe da ish vaqti qanday? Smena boshlanish va tugash vaqtlari, tanaffuslar haqida batafsil ayt.",
    "💰 Oylik maosh": "Ottimo Cafe da barcha lavozimlardagi oylik maosh, bonus va jarimalar haqida batafsil ma'lumot ber.",
    "📝 Ish shartnomasi": "Ottimo Cafe da mehnat shartnomasi qanday tuziladi? Asosiy shartlar, huquq va majburiyatlar nima?",
    "📊 Ish ma'lumotlari": "Ottimo Cafe haqida umumiy ma'lumot: qoidalar, standartlar, xodimlar uchun muhim narsalar.",
    "🤝 Xodimlar muammolari": "Xodimlar o'rtasidagi mojarolar va muammolarni qanday hal qilish kerak? Misollar bilan tushuntir.",
    "🔄 Smena vaqti": "Ottimo Cafe smena jadvali qanday? 1-smena va 2-smena vaqtlari, taqsimlash qoidalari nima?",
    "⚖️ Mehnat qonunlari": "O'zbekiston mehnat qonunlari bo'yicha Ottimo Cafe xodimlarining asosiy huquq va majburiyatlari.",
    "➕ Qo'shimcha savol": "Siz qo'shimcha savol berishingiz mumkin. Iltimos, savolingizni yozing.",
}

# Asosiy menyu - 3 qismga bo'lingan
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
        f"Men *Ottimo Cafe HR Agentiman* 🍽️\n\n"
        f"Quyidagi bo'limlardan birini tanlang yoki o'zingiz savol yozing:\n\n"
        f"👷 *Ishga oid* — qabul, shartnoma, maosh\n"
        f"📋 *Ma'lumot* — qoidalar, vaqt, smena\n"
        f"🤝 *Yordam* — muammolar, admin, qo'llab-quvvatlash"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🆘 *Yordam*\n\n"
        "Menyudan mavzu tanlang yoki o'zingiz savol yozing.\n\n"
        "*Bo'limlar:*\n"
        "👷 Ishchi qabul qilish\n"
        "❓ Savol va Javob\n"
        "⏰ Ish vaqti\n"
        "💰 Oylik maosh\n"
        "📝 Ish shartnomasi\n"
        "📊 Ish ma'lumotlari\n"
        "🤝 Xodimlar muammolari\n"
        "🔄 Smena vaqti\n"
        "⚖️ Mehnat qonunlari\n"
        "➕ Qo'shimcha savol\n\n"
        "*Buyruqlar:*\n"
        "/start — Boshiga qaytish\n"
        "/help — Yordam"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Foydalanuvchi"
    user_text = update.message.text

    # Suhbatni tozalash
    if user_text == "🗑️ Suhbatni tozalash":
        user_sessions[user_id] = []
        await update.message.reply_text("✅ Suhbat tozalandi! Yangi savol bering.", reply_markup=MAIN_MENU)
        return

    # Yordam
    if user_text == "🆘 Yordam":
        await help_command(update, context)
        return

    # Admin
    if user_text == "👨‍💼 Admin":
        text = (
            "👨‍💼 *Admin bo'limi*\n\n"
            "Admin bilan bog'lanish uchun:\n"
            "📱 @ottimo_admin\n\n"
            "Ish vaqti: 09:00 - 18:00"
        )
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)
        return

    # Qo'llab-quvvatlash
    if user_text == "📞 Qo'llab-quvvatlash":
        text = (
            "📞 *Qo'llab-quvvatlash*\n\n"
            "Muammo yoki savollar uchun:\n\n"
            "📱 Telefon: +998 90 000 00 00\n"
            "📧 Email: hr@ottimo.uz\n"
            "💬 Telegram: @ottimo_support\n\n"
            "Ish vaqti: 09:00 - 22:00"
        )
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)
        return

    # Qo'shimcha savol
    if user_text == "➕ Qo'shimcha savol":
        await update.message.reply_text(
            "➕ *Qo'shimcha savol*\n\nSavolingizni yozing, javob beraman! 👇",
            parse_mode='Markdown',
            reply_markup=MAIN_MENU
        )
        return

    # Menyu tugmasi bosilganda
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
        await update.message.reply_text(
            "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
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
