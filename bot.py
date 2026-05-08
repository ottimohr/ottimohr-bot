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

# O'zgaruvchilarni o'rnatish
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
    c.execute('''CREATE TABLE IF NOT EXISTS kechikishlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        xodim_id INTEGER,
        sana TEXT,
        minut INTEGER,
        izoh TEXT,
        FOREIGN KEY(xodim_id) REFERENCES xodimlar(id)
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

def db_query(sql, params=(), fetchall=False, fetchone=False):
    conn = sqlite3.connect("ottimo.db")
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    if fetchall:
        result = c.fetchall()
        conn.close()
        return result
    if fetchone:
        result = c.fetchone()
        conn.close()
        return result
    conn.close()
    return c.lastrowid

# ===================== ANKETA SAVOLLARI =====================
ANKETA_STEPS = [
    ("ism_familiya_sharif", "👤 *1/13* — Ism, Familiya va Sharifingizni kiriting:\n_(Masalan: Ibrohim Karimov Aliyevich)_"),
    ("tug_sana", "📅 *2/13* — Tug'ilgan sanangiz:\n_(Masalan: 15.03.2000)_"),
    ("millat", "🌍 *3/13* — Millatingiz:\n_(Masalan: O'zbek)_"),
    ("yashash", "🏠 *4/13* — Doimiy yashash manzilingiz:\n_(Tuman, ko'cha, uy)_"),
    ("telefon", "📱 *5/13* — Telefon raqamingiz:\n_(Masalan: +998 90 123 45 67)_"),
    ("talim", "🎓 *6/13* — Ta'lim darajangiz:\n_(Maktab / Kollej / Universitet)_"),
    ("tajriba", "💼 *7/13* — Oldingi ish tajribangiz:\n_(Korxona, lavozim, yillar. Yo'q bo'lsa — Yo'q)_"),
    ("rus_tili", "🗣️ *8/13* — Rus tilini bilish darajangiz:\n_(A'lo / Yaxshi / Past / Bilmayman)_"),
    ("ingliz_tili", "🗣️ *9/13* — Ingliz tilini bilish darajangiz:\n_(A'lo / Yaxshi / Past / Bilmayman)_"),
    ("kompyuter", "💻 *10/13* — Kompyuterda ishlash darajangiz:\n_(Erkin / O'rta / Bilmayman)_"),
    ("lavozim", "🎯 *11/13* — Qaysi lavozimga murojaat qilmoqchisiz?\n_(Barista / Kassir / Konditer-sotuvchi)_"),
    ("smena", "⏰ *12/13* — Qaysi smenada ishlashni xohlaysiz?\n\n💰 Kuniga taxminan *200,000 so'm* daromad!\n\n🌅 Ertalab: 07:30-16:30\n🌆 Kechqurun: 16:00-24:00"),
    ("qoshimcha", "📝 *13/13* — Qo'shimcha ma'lumot yoki savol:\n_(Yo'q bo'lsa — Yo'q deb yozing)_"),
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
    ["🌅 Ertalab (07:30-16:30)"],
    ["🌆 Kechqurun (16:00-24:00)"],
    ["🔄 Ikkalasi ham bo'ladi"]
], resize_keyboard=True, one_time_keyboard=True)

ADMIN_MENU = ReplyKeyboardMarkup([
    ["👥 Xodimlar ro'yxati", "➕ Xodim qo'shish"],
    ["⚠️ Kechikish belgilash", "📋 Arizalar ro'yxati"],
    ["📊 Statistika", "🔙 Bosh menyu"]
], resize_keyboard=True)

# ===================== JAVOBLAR LUG'ATI =====================
STATIC_RESPONSES = {
    "📍 Filiallarimiz": (
        "📍 *OTTIMO FILIALLARI:*\n\n"
        "1️⃣ *Ottimo Nukus filiali* — Nukus kino yonida, Shifer ko‘chasi 71\n\n"
        "2️⃣ *Ottimo Parus filiali* — Parus savdo markazi yonida, Katartal 60A/1\n\n"
        "3️⃣ *Ottimo Buyuk Ipak Yo‘li filiali* — Talant School ro‘parasida, Buyuk Ipak Yo‘li 31"
    ),
    "⏰ Ish vaqti": "⏰ *ISH VAQTI*\n\n🌅 *1-smena:* 07:30 — 16:30\n🌆 *2-smena:* 16:00 — 24:00\n\n💰 Kuniga taxminan *200,000 so'm*\n\n⚠️ Kechikish jarima: 50,000 so'm",
    "💰 Oylik maosh": "💰 *OYLIK MAOSH*\n\n• Kuniga taxminan *200,000 so'm*\n🗓️ Har *10 kunda* to'lanadi\n🍽️ Bepul ovqat va karyera o'sishi!",
    "📝 Ish shartnomasi": "📝 *ISH SHARTNOMASI*\n\n📋 Pasport nusxasi, mehnat daftarchasi va 3x4 rasm kerak.\n⏳ Probatsiya: 1 oy.",
    "📊 Ish ma'lumotlari": "📊 *OTTIMO CAFE*\n\n☕ Toshkentdagi zamonaviy premium kafe!\n✅ Rasmiy ish joyi, do'stona muhit.",
    "🔄 Smena vaqti": "🔄 *SMENA JADVALI*\n\n🌅 1-SMENA: 07:30 — 16:30\n🌆 2-SMENA: 16:00 — 24:00\n\n📞 @Ottimo_hr",
    "🤝 Xodimlar muammolari": "🤝 Har qanday murojaat menejer yoki HR tomonidan ko'rib chiqiladi: @Ottimo_hr",
    "⚖️ Mehnat qonunlari": "⚖️ *MEHNAT QONUNLARI*\n\n✅ O'z vaqtida maosh va yillik ta'til kafolatlanadi.",
    "❓ Savol va Javob": "❓ Savolingiz bo'lsa, @Ottimo_hr ga murojaat qiling yoki pastdagi tugmani bosing.",
}

# Holatlar uchun xotira
user_sessions = {}
user_anketa = {}
admin_state = {}

# ===================== FUNKSIYALAR =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Salom, *{update.effective_user.first_name}*!\n\n"
        f"🏢 *OTTIMO CAFE HR AGENTIGA XUSH KELIBSIZ!*\n\n"
        f"Quyidagi bo'limlardan birini tanlang 👇",
        parse_mode='Markdown', reply_markup=MAIN_MENU
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    # Anketa jarayoni
    if user_id in user_anketa:
        await process_anketa(update, context)
        return

    # Statik javoblar (Filiallar, Ish vaqti va h.k.)
    if user_text in STATIC_RESPONSES:
        await update.message.reply_text(STATIC_RESPONSES[user_text], parse_mode='Markdown', reply_markup=MAIN_MENU)
        return

    # Admin paneli boshqaruvi
    if user_text == "👨‍💼 Admin panel":
        await update.message.reply_text("👨‍💼 Admin menyusi:", reply_markup=ADMIN_MENU)
        return
    if user_text == "🔙 Bosh menyu":
        await update.message.reply_text("Asosiy menyu:", reply_markup=MAIN_MENU)
        return
    if user_text == "👷 Ishchi qabul qilish":
        await start_anketa(update, context)
        return
    
    # Gemini AI javobi
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        reply = ask_gemini(user_id, user_text)
        await update.message.reply_text(reply, reply_markup=MAIN_MENU)
    except Exception as e:
        await update.message.reply_text("⚠️ Hozir javob berolmayman, birozdan so'ng urinib ko'ring.")

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
        # Yakunlash va saqlash logikasi (Sizning kodingizdagi DB saqlash qismi)
        user_anketa.pop(user_id)
        await update.message.reply_text("✅ Anketangiz yuborildi! @Ottimo_hr siz bilan bog'lanadi.", reply_markup=MAIN_MENU)

def ask_gemini(user_id, user_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": f"Sen Ottimo Cafe HR agentisan. O'zbek tilida javob ber: {user_text}"}]}]}
    response = requests.post(url, json=payload, timeout=30)
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]

def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Ottimo Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
