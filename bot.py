import os
import logging
import requests
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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

# ===================== ANKETA =====================
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

SMENA_MENU = ReplyKeyboardMarkup([
    ["🌅 Ertalab (07:30-16:30)"],
    ["🌆 Kechqurun (16:00-24:00)"],
    ["🔄 Ikkalasi ham bo'ladi"]
], resize_keyboard=True, one_time_keyboard=True)

# ===================== STATIK JAVOBLAR =====================
STATIC_RESPONSES = {
    "⏰ Ish vaqti": "⏰ *ISH VAQTI*\n\n🌅 *1-smena:* 07:30 — 16:30\n🌆 *2-smena:* 16:00 — 24:00\n\n💰 Kuniga taxminan *200,000 so'm*\n\n📅 *Smena almashinuvi:*\n• Jadval har *dushanba* yangilanadi\n• O'zgarish 1 kun oldin xabar beriladi\n• Almashtirish faqat menejer ruxsati bilan\n\n⚠️ Kechikish jarima: 50,000 so'm",
    "💰 Oylik maosh": "💰 *OYLIK MAOSH*\n\n• Barista: 150,000-200,000 so'm\n• Kassir: 120,000-160,000 so'm\n• Konditer: 150,000-250,000 so'm\n\n💰 *Kuniga ~200,000 so'm!*\n\n🗓️ Har *10 kunda* to'lanadi\n🍽️ Bepul ovqat\n📈 Karyera o'sishi",
    "📝 Ish shartnomasi": "📝 *ISH SHARTNOMASI*\n\n📋 Kerakli hujjatlar:\n• Pasport nusxasi\n• Mehnat daftarchasi\n• Diplom/attestat\n• 3x4 foto (2 dona)\n\n⏳ Probatsiya: 1 oy\n\n✅ Huquqlar:\n• O'z vaqtida maosh\n• Yillik ta'til\n• Ijtimoiy sug'urta\n\n📞 @Ottimo_hr",
    "📊 Ish ma'lumotlari": "📊 *OTTIMO CAFE*\n\n☕ Toshkentdagi zamonaviy premium kafe!\n\n🌟 *Afzalliklar:*\n✅ Rasmiy ish joyi\n✅ Kuniga ~200,000 so'm\n✅ Har 10 kunda maosh\n✅ Bepul ovqat\n✅ Karyera o'sishi\n✅ Do'stona muhit\n✅ 25+ professional xodim\n\n💼 Bo'sh o'rinlar:\n• ☕ Barista\n• 💳 Kassir\n• 🍰 Konditer-sotuvchi\n\n📍 *3 ta Filial:*\n1️⃣ Nukus kino yonida — Shifer, 71\n2️⃣ Parus ostida — Katartal, 60A/1\n3️⃣ Talant school ro'parasida — Buyuk Ipak Yo'li, 31\n\n📞 +998 99 060 33 53 | @Ottimo_hr",
    "🤝 Xodimlar muammolari": "🤝 *XODIMLAR MUAMMOLARI*\n\n1-qadam: Hamkasbingiz bilan gaplashing\n2-qadam: Smena menejeriga\n3-qadam: HR ga: @Ottimo_hr\n\n⚠️ Ish joyida janjal — MAN!\n✅ Har murojaat ko'rib chiqiladi\n\n📞 +998 99 060 33 53",
    "⚖️ Mehnat qonunlari": "⚖️ *MEHNAT QONUNLARI*\n\n✅ HUQUQLAR:\n• O'z vaqtida maosh\n• Yillik ta'til (15-21 kun)\n• Kasallik varag'i\n• Ijtimoiy sug'urta\n\n⚠️ MAJBURIYATLAR:\n• O'z vaqtida kelish\n• Ish tartibiga rioya\n\n🚫 MAN:\n• Chekish\n• Alkogol\n• Mijozga qo'pollik\n\n📞 @Ottimo_hr",
    "❓ Savol va Javob": "❓ *FAQ*\n\n❓ Ish o'rinlari?\n✅ Barista, Kassir, Konditer\n\n❓ Yosh?\n✅ 20-35\n\n❓ Kunlik daromad?\n✅ ~200,000 so'm\n\n❓ Maosh qachon?\n✅ Har 10 kunda\n\n❓ Ish vaqti?\n✅ 07:30-16:30 / 16:00-24:00\n\n❓ Probatsiya?\n✅ 1 oy\n\n❓ Ovqat?\n✅ Bepul!\n\n❓ Murojaat?\n✅ @Ottimo_hr | +998 99 060 33 53",
}

# ===================== MENYULAR =====================
MAIN_MENU = ReplyKeyboardMarkup([
    ["👷 Ishchi qabul qilish", "❓ Savol va Javob", "⏰ Ish vaqti"],
    ["💰 Oylik maosh", "📝 Ish shartnomasi", "📊 Ish ma'lumotlari"],
    ["🤝 Xodimlar muammolari", "📍 Filiallar", "⚖️ Mehnat qonunlari"],
    ["👨‍💼 Admin", "📞 Qo'llab-quvvatlash", "➕ Qo'shimcha savol"],
    ["🆘 Yordam", "🗑️ Suhbatni tozalash"]
], resize_keyboard=True)

ADMIN_MENU = ReplyKeyboardMarkup([
    ["👥 Xodimlar ro'yxati", "➕ Xodim qo'shish"],
    ["⚠️ Kechikish belgilash", "📋 Arizalar ro'yxati"],
    ["📊 Statistika", "🔙 Bosh menyu"]
], resize_keyboard=True)

ADMIN_ADD_STEPS = [
    ("ism", "👤 Xodim ismi:"),
    ("lavozim", "🎯 Lavozimi:\n(Barista / Kassir / Konditer-sotuvchi)"),
    ("telefon", "📱 Telefon raqami:"),
    ("smena", "⏰ Smenasi:\n(Ertalab / Kechqurun / Ikkalasi)"),
]

user_sessions = {}
user_anketa = {}
admin_state = {}

# ===================== ADMIN FUNKSIYALAR =====================
async def show_admin_panel(update, context):
    await update.message.reply_text(
        "👨‍💼 *ADMIN PANEL*\n\nNimani qilmoqchisiz?",
        parse_mode='Markdown',
        reply_markup=ADMIN_MENU
    )

async def show_xodimlar(update, context):
    xodimlar = db_query("SELECT id, ism, lavozim, smena FROM xodimlar WHERE holat='aktiv'", fetchall=True)
    if not xodimlar:
        await update.message.reply_text("📭 Xodimlar ro'yxati bo'sh.", reply_markup=ADMIN_MENU)
        return
    text = "👥 *XODIMLAR RO'YXATI*\n\n"
    for x in xodimlar:
        text += f"#{x[0]} *{x[1]}*\n🎯 {x[2]} | ⏰ {x[3]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ADMIN_MENU)

async def show_statistika(update, context):
    jami = db_query("SELECT COUNT(*) FROM xodimlar WHERE holat='aktiv'", fetchone=True)[0]
    arizalar = db_query("SELECT COUNT(*) FROM arizalar WHERE holat='kutilmoqda'", fetchone=True)[0]
    kechikish = db_query("SELECT COUNT(*) FROM kechikishlar", fetchone=True)[0]
    await update.message.reply_text(
        f"📊 *STATISTIKA*\n\n👥 Aktiv xodimlar: *{jami}*\n📋 Kutilayotgan arizalar: *{arizalar}*\n⚠️ Jami kechikishlar: *{kechikish}*",
        parse_mode='Markdown', reply_markup=ADMIN_MENU
    )

async def show_arizalar(update, context):
    arizalar = db_query("SELECT id, ism, telefon, lavozim, smena, sana FROM arizalar WHERE holat='kutilmoqda'", fetchall=True)
    if not arizalar:
        await update.message.reply_text("📭 Kutilayotgan ariza yo'q.", reply_markup=ADMIN_MENU)
        return
    text = "📋 *ARIZALAR*\n\n"
    for a in arizalar:
        text += f"#{a[0]} *{a[1]}*\n📱 {a[2]} | 🎯 {a[3]} | ⏰ {a[4]}\n📅 {a[5]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ADMIN_MENU)

# ===================== ANKETA =====================
async def start_anketa(update, context):
    user_id = update.effective_user.id
    user_anketa[user_id] = {"step": 0, "data": {}}
    _, question = ANKETA_STEPS[0]
    await update.message.reply_text(
        "📋 *OTTIMO CAFE — ARIZA ANKETA*\n\nSavollarni birma-bir javob bering.\nBekor qilish: /bekor\n\n" + question,
        parse_mode='Markdown', reply_markup=ReplyKeyboardRemove()
    )

async def process_anketa(update, context):
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
        next_key, next_question = ANKETA_STEPS[next_step]
        if next_key == "smena":
            await update.message.reply_text(next_question, parse_mode='Markdown', reply_markup=SMENA_MENU)
        else:
            await update.message.reply_text(next_question, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
    else:
        data = step_data["data"]
        db_query(
            "INSERT INTO arizalar (ism, telefon, lavozim, smena, sana) VALUES (?,?,?,?,?)",
            (data.get('ism_familiya_sharif'), data.get('telefon'), data.get('lavozim'),
             data.get('smena'), datetime.now().strftime("%d.%m.%Y"))
        )
        summary = (
            "✅ *ANKETANGIZ TAYYOR! Tekshirib ko'ring:*\n\n"
            f"👤 *Ism:* {data.get('ism_familiya_sharif')}\n"
            f"📅 *Tug'ilgan sana:* {data.get('tug_sana')}\n"
            f"🌍 *Millat:* {data.get('millat')}\n"
            f"🏠 *Manzil:* {data.get('yashash')}\n"
            f"📱 *Telefon:* {data.get('telefon')}\n"
            f"🎓 *Ta'lim:* {data.get('talim')}\n"
            f"💼 *Tajriba:* {data.get('tajriba')}\n"
            f"🗣️ *Rus tili:* {data.get('rus_tili')}\n"
            f"🗣️ *Ingliz tili:* {data.get('ingliz_tili')}\n"
            f"💻 *Kompyuter:* {data.get('kompyuter')}\n"
            f"🎯 *Lavozim:* {data.get('lavozim')}\n"
            f"⏰ *Smena:* {data.get('smena')}\n"
            f"📝 *Qo'shimcha:* {data.get('qoshimcha')}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Tasdiqlaysizmi?"
        )
        confirm_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="anketa_confirm"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data="anketa_cancel")
        ]])
        await update.message.reply_text(summary, parse_mode='Markdown', reply_markup=confirm_keyboard)

async def anketa_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "anketa_confirm":
        data = user_anketa.get(user_id, {}).get("data", {})
        username = query.from_user.username or "username_yoq"
        msg = (
            "🔔 *YANGI ARIZA KELDI!*\n\n"
            f"👤 *{data.get('ism_familiya_sharif')}*\n"
            f"📱 {data.get('telefon')}\n"
            f"🎯 Lavozim: *{data.get('lavozim')}*\n"
            f"⏰ Smena: *{data.get('smena')}*\n"
            f"📅 Tug'ilgan: {data.get('tug_sana')}\n"
            f"🏠 Manzil: {data.get('yashash')}\n"
            f"🎓 Ta'lim: {data.get('talim')}\n"
            f"💼 Tajriba: {data.get('tajriba')}\n"
            f"🗣️ Rus: {data.get('rus_tili')} | Ingliz: {data.get('ingliz_tili')}\n"
            f"💻 Kompyuter: {data.get('kompyuter')}\n"
            f"📝 Qo'shimcha: {data.get('qoshimcha')}\n\n"
            f"📲 Telegram: @{username}"
        )
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
            "✅ *Anketangiz yuborildi!*\n\n"
            "🕐 Ko'rib chiqish: 1-3 ish kuni\n"
            "📱 @Ottimo_hr siz bilan bog'lanadi\n\nRahmat! 🙏",
            parse_mode='Markdown'
        )
        await context.bot.send_message(chat_id=user_id, text="Bosh menyu:", reply_markup=MAIN_MENU)
    elif query.data == "anketa_cancel":
        user_anketa.pop(user_id, None)
        await query.edit_message_text("❌ Anketa bekor qilindi.")
        await context.bot.send_message(chat_id=user_id, text="Bosh menyuga qaytdingiz.", reply_markup=MAIN_MENU)

# ===================== ADMIN XODIM QO'SHISH =====================
async def start_add_xodim(update, context):
    user_id = update.effective_user.id
    admin_state[user_id] = {"action": "add_xodim", "step": 0, "data": {}}
    await update.message.reply_text(
        "➕ *YANGI XODIM QO'SHISH*\n\n" + ADMIN_ADD_STEPS[0][1],
        parse_mode='Markdown', reply_markup=ReplyKeyboardRemove()
    )

async def process_add_xodim(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    state = admin_state[user_id]
    current_step = state["step"]
    key, _ = ADMIN_ADD_STEPS[current_step]
    state["data"][key] = text
    next_step = current_step + 1
    if next_step < len(ADMIN_ADD_STEPS):
        state["step"] = next_step
        await update.message.reply_text(ADMIN_ADD_STEPS[next_step][1], reply_markup=ReplyKeyboardRemove())
    else:
        data = state["data"]
        db_query(
            "INSERT INTO xodimlar (ism, lavozim, telefon, smena, qoshilgan_sana) VALUES (?,?,?,?,?)",
            (data['ism'], data['lavozim'], data['telefon'], data['smena'], datetime.now().strftime("%d.%m.%Y"))
        )
        admin_state.pop(user_id, None)
        await update.message.reply_text(
            f"✅ *{data['ism']}* xodimlar ro'yxatiga qo'shildi!",
            parse_mode='Markdown', reply_markup=ADMIN_MENU
        )

# ===================== KECHIKISH =====================
async def start_kechikish(update, context):
    xodimlar = db_query("SELECT id, ism FROM xodimlar WHERE holat='aktiv'", fetchall=True)
    if not xodimlar:
        await update.message.reply_text("📭 Xodimlar yo'q.", reply_markup=ADMIN_MENU)
        return
    keyboard = [[InlineKeyboardButton(x[1], callback_data=f"kechik_{x[0]}")] for x in xodimlar]
    await update.message.reply_text("⚠️ *Qaysi xodim kechikdi?*", parse_mode='Markdown',
                                     reply_markup=InlineKeyboardMarkup(keyboard))

async def kechikish_callback(update, context):
    query = update.callback_query
    await query.answer()
    xodim_id = int(query.data.split("_")[1])
    xodim = db_query("SELECT ism FROM xodimlar WHERE id=?", (xodim_id,), fetchone=True)
    db_query("INSERT INTO kechikishlar (xodim_id, sana, minut) VALUES (?,?,?)",
             (xodim_id, datetime.now().strftime("%d.%m.%Y"), 15))
    await query.edit_message_text(
        f"⚠️ *{xodim[0]}* kechikishi belgilandi!\n💸 Jarima: 50,000 so'm",
        parse_mode='Markdown'
    )

# ===================== ASOSIY =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Foydalanuvchi"
    await update.message.reply_text(
        f"👋 Salom, *{user_name}*!\n\n🏢 *OTTIMO CAFE HR AGENTIGA XUSH KELIBSIZ!*\n\nQuyidagi bo'limlardan birini tanlang 👇",
        parse_mode='Markdown', reply_markup=MAIN_MENU
    )

def ask_gemini(user_id, user_text):
    history = user_sessions.get(user_id, [])
    history_text = ""
    if history:
        history_text = "\n\nOldingi suhbat:\n" + "\n".join([
            f"Foydalanuvchi: {h['user']}\nAgent: {h['agent']}"
            for h in history[-5:]
        ])
    system = "Sen Ottimo Cafe HR agentisan. Faqat O'zbek tilida javob ber."
    full_prompt = system + history_text + f"\n\nFoydalanuvchi: {user_text}\nAgent:"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}}
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id in user_anketa:
        await process_anketa(update, context)
        return

    if user_id in admin_state:
        if admin_state[user_id].get("action") == "add_xodim":
            await process_add_xodim(update, context)
            return

    # Admin panel tugmalari
    if user_text == "👥 Xodimlar ro'yxati":
        await show_xodimlar(update, context)
        return
    if user_text == "➕ Xodim qo'shish":
        await start_add_xodim(update, context)
        return
    if user_text == "⚠️ Kechikish belgilash":
        await start_kechikish(update, context)
        return
    if user_text == "📋 Arizalar ro'yxati":
        await show_arizalar(update, context)
        return
    if user_text == "📊 Statistika":
        await show_statistika(update, context)
        return
    if user_text == "🔙 Bosh menyu":
        await update.message.reply_text("Bosh menyu:", reply_markup=MAIN_MENU)
        return

    # Asosiy menyu tugmalari
    if user_text == "🗑️ Suhbatni tozalash":
        user_sessions[user_id] = []
        await update.message.reply_text("✅ Suhbat tozalandi!", reply_markup=MAIN_MENU)
        return
    if user_text == "🆘 Yordam":
        await update.message.reply_text("Menyudan tanlang yoki savol yozing!", reply_markup=MAIN_MENU)
        return

    # 👨‍💼 Admin — faqat @Ottimo_hr linki
    if user_text == "👨‍💼 Admin":
        await update.message.reply_text(
            "👨‍💼 *ADMIN*\n\n"
            "Ottimo HR boshqaruvi:\n\n"
            "📱 Telegram: @Ottimo_hr\n"
            "📞 Tel: +998 99 060 33 53\n\n"
            "👉 [Admin ga yozish](https://t.me/Ottimo_hr)",
            parse_mode='Markdown',
            reply_markup=MAIN_MENU,
            disable_web_page_preview=True
        )
        return

    # 📍 Filiallar
    if user_text == "📍 Filiallar":
        await update.message.reply_text(
            "📍 *OTTIMO CAFE FILIALLARI*\n\n"
            "1️⃣ *Nukus kinoteatri yonida*\n"
            "📌 Toshkent, Shifer ko'chasi, 71\n\n"
            "2️⃣ *Parus ostida*\n"
            "📌 Toshkent, Katartal ko'chasi, 60A/1\n\n"
            "3️⃣ *Talant International School ro'parasida*\n"
            "📌 Toshkent, Mirzo Ulug'bek tumani, Buyuk Ipak Yo'li, 31\n\n"
            "📞 +998 99 060 33 53\n"
            "💬 @Ottimo_hr",
            parse_mode='Markdown',
            reply_markup=MAIN_MENU
        )
        return

    if user_text == "📞 Qo'llab-quvvatlash":
        await update.message.reply_text(
            "📞 *Qo'llab-quvvatlash*\n\n📱 +998 99 060 33 53\n💬 @Ottimo_hr",
            parse_mode='Markdown', reply_markup=MAIN_MENU
        )
        return
    if user_text == "➕ Qo'shimcha savol":
        await update.message.reply_text("➕ Savolingizni yozing! 👇", reply_markup=MAIN_MENU)
        return
    if user_text == "👷 Ishchi qabul qilish":
        await start_anketa(update, context)
        return
    if user_text in STATIC_RESPONSES:
        await update.message.reply_text(STATIC_RESPONSES[user_text], parse_mode='Markdown', reply_markup=MAIN_MENU)
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
        await update.message.reply_text("⚠️ Xatolik. @Ottimo_hr ga murojaat qiling.", reply_markup=MAIN_MENU)

def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(anketa_callback, pattern="^anketa_"))
    app.add_handler(CallbackQueryHandler(kechikish_callback, pattern="^kechik_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
