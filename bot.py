import os
import logging
import requests
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Loglarni sozlash
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# O'zgaruvchilarni o'rnatish (Environment Variables)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_USERNAME = "mr_jalilov7"

# ===================== DATABASE =====================
def init_db():
    conn = sqlite3.connect("ottimo.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS xodimlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ism TEXT NOT NULL,
        lavozim TEXT NOT NULL,
        telefon TEXT,
        smena TEXT,
        qoshilgan_sana TEXT,
        holat TEXT DEFAULT "aktiv"
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS arizalar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ism TEXT,
        telefon TEXT,
        lavozim TEXT,
        smena TEXT,
        sana TEXT,
        holat TEXT DEFAULT "kutilmoqda"
    )''')
    conn.commit()
    conn.close()

# ===================== ANKETA SAVOLLARI =====================
ANKETA_STEPS = [
    ("ism_familiya_sharif", "👤 *1/13* — Ism, Familiya va Sharifingizni kiriting:"),
    ("tug_sana", "📅 *2/13* — Tug'ilgan sanangiz:"),
    ("millat", "🌍 *3/13* — Millatingiz:"),
    ("yashash", "🏠 *4/13* — Doimiy yashash manzilingiz:"),
    ("telefon", "📱 *5/13* — Telefon raqamingiz:"),
    ("talim", "🎓 *6/13* — Ta'lim darajangiz:"),
    ("tajriba", "💼 *7/13* — Oldingi ish tajribangiz:"),
    ("rus_tili", "🗣️ *8/13* — Rus tilini bilish darajangiz:"),
    ("ingliz_tili", "🗣️ *9/13* — Ingliz tilini bilish darajangiz:"),
    ("kompyuter", "💻 *10/13* — Kompyuterda ishlash darajangiz:"),
    ("lavozim", "🎯 *11/13* — Qaysi lavozimga murojaat qilmoqchisiz?"),
    ("smena", "⏰ *12/13* — Qaysi smenada ishlashni xohlaysiz?"),
    ("qoshimcha", "📝 *13/13* — Qo'shimcha ma'lumot yoki savol:"),
]

# ===================== MENYULAR =====================
MAIN_MENU = ReplyKeyboardMarkup([
    ["👷 Ishchi qabul qilish", "📍 Filiallarimiz", "⏰ Ish vaqti"],
    ["💰 Oylik maosh", "📝 Ish shartnomasi", "📊 Ish ma'lumotlari"],
    ["🤝 Xodimlar muammolari", "🔄 Smena vaqti", "⚖️ Mehnat qonunlari"],
    ["👨‍💼 Admin panel", "📞 Qo'llab-quvvatlash", "➕ Qo'shimcha savol"],
    ["🆘 Yordam", "🗑️ Suhbatni tozalash"]
], resize_keyboard=True)

SMENA_MENU = ReplyKeyboardMarkup([
    ["🌅 Ertalab (07:30-16:30)", "🌆 Kechqurun (16:00-24:00)"],
    ["🔄 Ikkalasi ham bo'ladi"]
], resize_keyboard=True)

ADMIN_MENU = ReplyKeyboardMarkup([
    ["👥 Xodimlar ro'yxati", "📋 Arizalar ro'yxati"],
    ["📊 Statistika", "🔙 Bosh menyu"]
], resize_keyboard=True)

# ===================== JAVOBLAR LUG'ATI =====================
STATIC_RESPONSES = {
    "📍 Filiallarimiz": (
        "📍 *OTTIMO FILIALLARI:*\n\n"
        "1️⃣ *Ottimo Nukus filiali* — Nukus kino yonida, Shifer ko‘chasi 71\n"
        "2️⃣ *Ottimo Parus filiali* — Parus savdo markazi yonida, Katartal 60A/1\n"
        "3️⃣ *Ottimo Buyuk Ipak Yo‘li filiali* — Talant School ro‘parasida, Buyuk Ipak Yo‘li 31"
    ),
    "📊 Ish ma'lumotlari": (
        "📊 *OTTIMO CAFE HAQIDA MA'LUMOT*\n\n"
        "✨ **Ottimo** — bu shunchaki kafe emas, bu premium sifat va o'ziga xos ta'm uyg'unligidir. Biz Toshkentda gelato (muzqaymoq) va sifatli kofe madaniyatini yangi darajaga olib chiqmoqdamiz.\n\n"
        "🌟 **Bizning afzalliklarimiz:**\n"
        "✅ **Rasmiy ish joyi:** Mehnat qonunchiligi asosida ish yuritiladi.\n"
        "✅ **Barqaror daromad:** Kuniga o'rtacha ~200,000 so'm.\n"
        "✅ **Bepul ovqatlanish:** Ish vaqtida xodimlar uchun issiq ovqat.\n"
        "✅ **Karyera o'sishi:** Oddiy xodimdan boshqaruvchigacha o'sish imkoniyati.\n"
        "✅ **Do'stona jamoa:** 25 nafardan ortiq yosh va g'ayratli professional jamoa.\n\n"
        "☕ **Siz nimalar bilan ishlaysiz?**\n"
        "Italiya texnologiyasi asosida tayyorlanadigan muzqaymoqlar, yangi qovurilgan kofe donalari va eksklyuziv shirinliklar.\n\n"
        "📍 Hozirda Toshkentda 3 ta filialimiz mavjud va kengayishda davom etamiz!"
    ),
    "⏰ Ish vaqti": "⏰ *ISH VAQTI*\n\n🌅 1-smena: 07:30 — 16:30\n🌆 2-smena: 16:00 — 24:00\n\n⚠️ Kechikish jarimasi: 50,000 so'm",
    "💰 Oylik maosh": "💰 *MAOSH TIZIMI*\n\nHar 10 kunda to'lanadi. Kunlik daromad ish natijasiga ko'ra ~200,000 so'mni tashkil qiladi.",
    "📝 Ish shartnomasi": "📝 Shartnoma tuzish uchun: Pasport nusxasi, 2 dona 3x4 rasm va ma'lumotnoma talab etiladi.",
    "🔄 Smena vaqti": "🔄 Smenalar haftalik jadval asosida taqsimlanadi. Har bir xodim haftasiga 1 kun dam oladi.",
    "🤝 Xodimlar muammolari": "🤝 Har qanday murojaat va muammolar HR tomonidan maxfiy va adolatli ko'rib chiqiladi: @Ottimo_hr",
    "⚖️ Mehnat qonunlari": "⚖️ Biz O'zbekiston Respublikasi Mehnat Kodeksiga to'liq amal qilamiz.",
}

# ===================== FUNKSIYALAR =====================
user_anketa = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Salom, *{update.effective_user.first_name}*!\n\n"
        "🏢 **OTTIMO CAFE HR AGENTIGA XUSH KELIBSIZ!**\n\n"
        "Sizga qanday yordam bera olaman?",
        parse_mode='Markdown', reply_markup=MAIN_MENU
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id in user_anketa:
        await process_anketa(update, context)
        return

    if user_text in STATIC_RESPONSES:
        await update.message.reply_text(STATIC_RESPONSES[user_text], parse_mode='Markdown', reply_markup=MAIN_MENU)
        return

    if user_text == "👷 Ishchi qabul qilish":
        await start_anketa(update, context)
        return
    
    if user_text == "👨‍💼 Admin panel":
        await update.message.reply_text("👨‍💼 Admin boshqaruvi:", reply_markup=ADMIN_MENU)
        return

    # Gemini AI qismi (savollar uchun)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        reply = ask_gemini(user_text)
        await update.message.reply_text(reply, reply_markup=MAIN_MENU)
    except:
        await update.message.reply_text("Hozirda tizim band, iltimos keyinroq savol bering.")

async def start_anketa(update, context):
    user_id = update.effective_user.id
    user_anketa[user_id] = {"step": 0, "data": {}}
    await update.message.reply_text(ANKETA_STEPS[0][1], parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())

async def process_anketa(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    step_data = user_anketa[user_id]
    current_step = step_data["step"]
    
    key = ANKETA_STEPS[current_step][0]
    step_data["data"][key] = text
    next_step = current_step + 1

    if next_step < len(ANKETA_STEPS):
        step_data["step"] = next_step
        next_key, next_question = ANKETA_STEPS[next_step]
        markup = SMENA_MENU if next_key == "smena" else ReplyKeyboardRemove()
        await update.message.reply_text(next_question, parse_mode='Markdown', reply_markup=markup)
    else:
        user_anketa.pop(user_id)
        await update.message.reply_text("✅ Anketangiz qabul qilindi! Menejerlarimiz siz bilan bog'lanishadi.", reply_markup=MAIN_MENU)

def ask_gemini(user_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": f"Sen Ottimo kafesi HR agentisan. Quyidagi savolga O'zbek tilida, do'stona va professional javob ber: {user_text}"}]}]}
    response = requests.post(url, json=payload, timeout=30)
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]

def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Ottimo HR bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
