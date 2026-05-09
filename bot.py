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
ADMIN_USERNAME = "Ibr0kh1_M"
ADMIN_CHAT_ID = 6613741078

# ===================== DATABASE =====================
def init_db():
    conn = sqlite3.connect("ottimo.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS xodimlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ism TEXT, lavozim TEXT, telefon TEXT, smena TEXT,
        qoshilgan_sana TEXT, holat TEXT DEFAULT "aktiv"
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS kechikishlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        xodim_id INTEGER, sana TEXT, minut INTEGER, izoh TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS arizalar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ism TEXT, telefon TEXT, lavozim TEXT, smena TEXT,
        sana TEXT, holat TEXT DEFAULT "kutilmoqda"
    )''')
    conn.commit()
    conn.close()

def db_query(sql, params=(), fetchall=False, fetchone=False):
    conn = sqlite3.connect("ottimo.db")
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    if fetchall:
        result = c.fetchall(); conn.close(); return result
    if fetchone:
        result = c.fetchone(); conn.close(); return result
    conn.close()
    return c.lastrowid

# ===================== TO'LIQ ANKETA SAVOLLARI (PDF asosida) =====================
ANKETA_STEPS = [
    ("ism_familiya_sharif",   "👤 *1/32* — Ism, Familiya va Sharifingiz:\n_(Masalan: Ibrohim Karimov Aliyevich)_"),
    ("tug_sana",              "📅 *2/32* — Tug'ilgan sanangiz:\n_(Masalan: 15.03.2000)_"),
    ("millat",                "🌍 *3/32* — Millatingiz:\n_(Masalan: O'zbek)_"),
    ("tug_joy",               "🗺 *4/32* — Tug'ilgan joyingiz (viloyat, tuman):"),
    ("yashash_joy",           "🏠 *5/32* — Doimiy yashash manzilingiz:\n_(Ko'cha, uy raqami)_"),
    ("turar_joy",             "🏘 *6/32* — Turar joy turingiz:\n_(Dom / Hovli)_"),
    ("telefon",               "📱 *7/32* — Telefon raqamingiz:\n_(+998 90 123 45 67)_"),
    ("talim",                 "🎓 *8/32* — Ta'lim darajangiz:\n_(Maktab 11-sinf / Kollej-litsey / Institut-universitet)_"),
    ("oquv_yurti",            "🏫 *9/32* — Qaysi o'quv yurtini qachon tamomlagansiz?\n_(Nomi, fakultet, yillar. Yo'q — Yo'q)_"),
    ("oldingi_ish",           "💼 *10/32* — Oldingi ish joylaringiz:\n_(Korxona, lavozim, yillar, bo'shash sababi. Yo'q — Yo'q)_"),
    ("chet_safari",           "✈️ *11/32* — Chet el safariga chiqqanmisiz?\n_(Ha — qayerga? / Yo'q)_"),
    ("oilaviy_holat",         "💑 *12/32* — Oilaviy holatingiz:\n_(Bo'ydoq / Turmush qurgan / Ajrashgan)_"),
    ("oila_azosi",            "👨‍👩‍👧 *13/32* — Oila a'zolaringiz:\n_(Ism, tug'ilgan sana, ish joyi, telefon. Yo'q — Yo'q)_"),
    ("sudlanganmi",           "⚖️ *14/32* — Sudlanganmisiz?\n_(Yo'q / Ha — sababi)_"),
    ("avtomobil",             "🚗 *15/32* — Shaxsiy avtomobilingiz bormi?\n_(Yo'q / Ha — rusumi)_"),
    ("haydovchilik",          "🪪 *16/32* — Haydovchilik guvohnomangiz bormi?\n_(Yo'q / Ha — turi: A/B/C/D/E)_"),
    ("uzbek_tili",            "🗣 *17/32* — O'zbek tilini bilish darajangiz:\n_(A'lo / Yaxshi / Past)_"),
    ("rus_tili",              "🗣 *18/32* — Rus tilini bilish darajangiz:\n_(A'lo / Yaxshi / Past / Bilmayman)_"),
    ("ingliz_tili",           "🗣 *19/32* — Ingliz tilini bilish darajangiz:\n_(A'lo / Yaxshi / Past / Bilmayman)_"),
    ("boshqa_til",            "🗣 *20/32* — Boshqa til bilasizmi?\n_(Yo'q / Ha — qaysi va darajasi)_"),
    ("qobiliyat",             "⭐ *21/32* — Alohida qobiliyatlaringiz:\n_(Yo'q bo'lsa — Yo'q)_"),
    ("bosh_vaqt",             "🎯 *22/32* — Bo'sh vaqtingizni qanday o'tkazasiz?"),
    ("kompyuter",             "💻 *23/32* — Kompyuterda erkin ishlaysizmi?\n_(Ha / Yo'q / O'rta)_"),
    ("qayerdan_bildingiz",    "📢 *24/32* — Kompaniyamiz haqida qayerdan bildingiz?\n_(Do'stim / Instagram / OLX...)_"),
    ("kafil",                 "🤝 *25/32* — Ishlashingizga kafolat bera oladigan shaxs:\n_(Ismi, aloqasi, ish joyi, telefon. Yo'q — Yo'q)_"),
    ("tavsiya",               "📄 *26/32* — Oxirgi ish joyingizdan tavsiya xati bera oladimi?\n_(Ha — ismi, lavozimi, telefon. Yo'q — Yo'q)_"),
    ("surushtirishga_rozi",   "🔍 *27/32* — Oxirgi ish joyingizdan surishtirishimizga rozimisiz?\n_(Ha / Yo'q)_"),
    ("oldingi_maosh",         "💵 *28/32* — Oxirgi ish joyingizda qancha oylik olgan edingiz?"),
    ("kutilayotgan_maosh",    "💰 *29/32* — Bizdan qancha oylik kutasiz?"),
    ("ishlash_muddati",       "📆 *30/32* — Bizda qancha muddat ishlashni rejalashtirasiz?\n_(Uzoq muddatga / 1 yil / Bilmayman)_"),
    ("qolib_ishlash",         "🕐 *31/32* — Ish tugagandan keyin qolib ishlash kerak bo'lsa rozimisiz?\n_(Ha / Yo'q)_"),
    ("smena",                 "⏰ *32/32* — Qaysi smenada ishlashni xohlaysiz?\n\n💰 Kuniga taxminan *200,000 so'm* daromad!\n\n🌅 Ertalab: 07:30-16:30\n🌆 Kechqurun: 16:00-24:00"),
]

SMENA_MENU = ReplyKeyboardMarkup([
    ["🌅 Ertalab (07:30-16:30)"],
    ["🌆 Kechqurun (16:00-24:00)"],
    ["🔄 Ikkalasi ham bo'ladi"]
], resize_keyboard=True, one_time_keyboard=True)

# ===================== STATIK JAVOBLAR =====================
STATIC_RESPONSES = {
    "⏰ Ish vaqti": "⏰ *ISH VAQTI*\n\n🌅 *1-smena:* 07:30 — 16:30\n🌆 *2-smena:* 16:00 — 24:00\n\n💰 Kuniga taxminan *200,000 so'm*\n\n📅 Jadval har *dushanba* yangilanadi\n• O'zgarish 1 kun oldin xabar beriladi\n\n⚠️ Kechikish jarima: 50,000 so'm\n🍽️ Har smena bepul ovqat",
    "💰 Oylik maosh": "💰 *OYLIK MAOSH*\n\n• Barista: 150,000-200,000 so'm\n• Kassir: 120,000-160,000 so'm\n• Konditer: 150,000-250,000 so'm\n\n💰 *Kuniga ~200,000 so'm!*\n🗓️ Har *10 kunda* to'lanadi\n🍽️ Bepul ovqat\n📈 Karyera o'sishi",
    "📝 Ish shartnomasi": "📝 *ISH SHARTNOMASI*\n\n📋 Kerakli hujjatlar:\n• Pasport nusxasi\n• Mehnat daftarchasi\n• Diplom/attestat\n• 3x4 foto (2 dona)\n\n⏳ Probatsiya: 1 oy\n✅ Rasmiy mehnat shartnomasi\n✅ Ijtimoiy sug'urta\n\n📞 @Ottimo_hr",
    "📊 Ish ma'lumotlari": "📊 *OTTIMO CAFE*\n\n☕ Toshkentdagi zamonaviy premium kafe!\n\n🌟 *Afzalliklar:*\n✅ Rasmiy ish joyi\n✅ Kuniga ~200,000 so'm\n✅ Har 10 kunda maosh\n✅ Bepul ovqat\n✅ Karyera o'sishi\n✅ Do'stona muhit\n✅ 25+ professional xodim\n\n💼 Bo'sh o'rinlar:\n• ☕ Barista\n• 💳 Kassir\n• 🍰 Konditer-sotuvchi\n\n📍 *3 ta Filial:*\n1️⃣ Nukus kino — Shifer, 71\n2️⃣ Parus ostida — Katartal, 60A/1\n3️⃣ Talant school — Buyuk Ipak Yo'li, 31\n\n📞 +998 99 060 33 53 | @Ottimo_hr",
    "🤝 Xodimlar muammolari": "🤝 *XODIMLAR MUAMMOLARI*\n\n1️⃣ Hamkasbingiz bilan gaplashing\n2️⃣ Smena menejeriga\n3️⃣ HR: @Ottimo_hr\n\n⚠️ Ish joyida janjal — MAN!\n✅ Har murojaat ko'rib chiqiladi\n\n📞 +998 99 060 33 53",
    "⚖️ Mehnat qonunlari": "⚖️ *MEHNAT QONUNLARI*\n\n✅ HUQUQLAR:\n• O'z vaqtida maosh\n• Yillik ta'til 15-21 kun\n• Kasallik varag'i\n• Ijtimoiy sug'urta\n\n⚠️ MAJBURIYATLAR:\n• O'z vaqtida kelish\n• Ish tartibiga rioya\n\n🚫 MAN:\n• Chekish • Alkogol • Mijozga qo'pollik\n\n📞 @Ottimo_hr",

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
    ("lavozim", "🎯 Lavozimi: (Barista / Kassir / Konditer)"),
    ("telefon", "📱 Telefon raqami:"),
    ("smena", "⏰ Smenasi: (Ertalab / Kechqurun / Ikkalasi)"),
]

user_sessions = {}
user_anketa = {}
admin_state = {}

# ===================== ADMIN =====================
async def show_xodimlar(update, context):
    xodimlar = db_query("SELECT id, ism, lavozim, smena FROM xodimlar WHERE holat='aktiv'", fetchall=True)
    if not xodimlar:
        await update.message.reply_text("📭 Xodimlar ro'yxati bo'sh.", reply_markup=ADMIN_MENU); return
    text = "👥 *XODIMLAR RO'YXATI*\n\n"
    for x in xodimlar:
        text += f"#{x[0]} *{x[1]}*\n🎯 {x[2]} | ⏰ {x[3]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ADMIN_MENU)

async def show_statistika(update, context):
    jami = db_query("SELECT COUNT(*) FROM xodimlar WHERE holat='aktiv'", fetchone=True)[0]
    arizalar = db_query("SELECT COUNT(*) FROM arizalar WHERE holat='kutilmoqda'", fetchone=True)[0]
    kechikish = db_query("SELECT COUNT(*) FROM kechikishlar", fetchone=True)[0]
    await update.message.reply_text(
        f"📊 *STATISTIKA*\n\n👥 Aktiv xodimlar: *{jami}*\n📋 Arizalar: *{arizalar}*\n⚠️ Kechikishlar: *{kechikish}*",
        parse_mode='Markdown', reply_markup=ADMIN_MENU)

async def show_arizalar(update, context):
    arizalar = db_query("SELECT id, ism, telefon, lavozim, smena, sana FROM arizalar WHERE holat='kutilmoqda'", fetchall=True)
    if not arizalar:
        await update.message.reply_text("📭 Ariza yo'q.", reply_markup=ADMIN_MENU); return
    text = "📋 *ARIZALAR*\n\n"
    for a in arizalar:
        text += f"#{a[0]} *{a[1]}*\n📱 {a[2]} | 🎯 {a[3]} | ⏰ {a[4]}\n📅 {a[5]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ADMIN_MENU)

async def start_add_xodim(update, context):
    user_id = update.effective_user.id
    admin_state[user_id] = {"action": "add_xodim", "step": 0, "data": {}}
    await update.message.reply_text("➕ *YANGI XODIM*\n\n" + ADMIN_ADD_STEPS[0][1],
                                     parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())

async def process_add_xodim(update, context):
    user_id = update.effective_user.id
    state = admin_state[user_id]
    key, _ = ADMIN_ADD_STEPS[state["step"]]
    state["data"][key] = update.message.text
    next_step = state["step"] + 1
    if next_step < len(ADMIN_ADD_STEPS):
        state["step"] = next_step
        await update.message.reply_text(ADMIN_ADD_STEPS[next_step][1], reply_markup=ReplyKeyboardRemove())
    else:
        data = state["data"]
        db_query("INSERT INTO xodimlar (ism, lavozim, telefon, smena, qoshilgan_sana) VALUES (?,?,?,?,?)",
                 (data['ism'], data['lavozim'], data['telefon'], data['smena'], datetime.now().strftime("%d.%m.%Y")))
        admin_state.pop(user_id, None)
        await update.message.reply_text(f"✅ *{data['ism']}* qo'shildi!", parse_mode='Markdown', reply_markup=ADMIN_MENU)

async def start_kechikish(update, context):
    xodimlar = db_query("SELECT id, ism FROM xodimlar WHERE holat='aktiv'", fetchall=True)
    if not xodimlar:
        await update.message.reply_text("📭 Xodimlar yo'q.", reply_markup=ADMIN_MENU); return
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
    await query.edit_message_text(f"⚠️ *{xodim[0]}* kechikishi belgilandi!\n💸 50,000 so'm jarima", parse_mode='Markdown')

# ===================== ANKETA =====================
async def start_anketa(update, context):
    user_id = update.effective_user.id
    user_anketa[user_id] = {"step": 0, "data": {}}
    await update.message.reply_text(
        f"📋 *OTTIMO CAFE — ARIZA ANKETA*\n\nJami {len(ANKETA_STEPS)} ta savol.\nBekor qilish: /bekor\n\n" + ANKETA_STEPS[0][1],
        parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())

async def process_anketa(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "/bekor":
        user_anketa.pop(user_id, None)
        await update.message.reply_text("❌ Bekor qilindi.", reply_markup=MAIN_MENU); return

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
        db_query("INSERT INTO arizalar (ism, telefon, lavozim, smena, sana) VALUES (?,?,?,?,?)",
                 (data.get('ism_familiya_sharif'), data.get('telefon'), "Ko'rsatilmagan",
                  data.get('smena'), datetime.now().strftime("%d.%m.%Y")))

        summary = (
            "✅ *ANKETANGIZ TAYYOR! Tekshirib ko'ring:*\n\n"
            f"👤 *Ism:* {data.get('ism_familiya_sharif')}\n"
            f"📅 *Tug'ilgan sana:* {data.get('tug_sana')}\n"
            f"🌍 *Millat:* {data.get('millat')}\n"
            f"🗺 *Tug'ilgan joy:* {data.get('tug_joy')}\n"
            f"🏠 *Yashash joyi:* {data.get('yashash_joy')} ({data.get('turar_joy')})\n"
            f"📱 *Telefon:* {data.get('telefon')}\n"
            f"🎓 *Ta'lim:* {data.get('talim')}\n"
            f"🏫 *O'quv yurti:* {data.get('oquv_yurti')}\n"
            f"💼 *Ish tajribasi:* {data.get('oldingi_ish')}\n"
            f"✈️ *Chet safari:* {data.get('chet_safari')}\n"
            f"💑 *Oilaviy holat:* {data.get('oilaviy_holat')}\n"
            f"👨‍👩‍👧 *Oila a'zosi:* {data.get('oila_azosi')}\n"
            f"⚖️ *Sudlanganmi:* {data.get('sudlanganmi')}\n"
            f"🚗 *Avtomobil:* {data.get('avtomobil')}\n"
            f"🪪 *Haydovchilik:* {data.get('haydovchilik')}\n"
            f"🗣 *Tillar:* O'zbek: {data.get('uzbek_tili')} | Rus: {data.get('rus_tili')} | Ingliz: {data.get('ingliz_tili')} | Boshqa: {data.get('boshqa_til')}\n"
            f"⭐ *Qobiliyat:* {data.get('qobiliyat')}\n"
            f"🎯 *Bo'sh vaqt:* {data.get('bosh_vaqt')}\n"
            f"💻 *Kompyuter:* {data.get('kompyuter')}\n"
            f"📢 *Qayerdan bildingiz:* {data.get('qayerdan_bildingiz')}\n"
            f"🤝 *Kafil:* {data.get('kafil')}\n"
            f"📄 *Tavsiya:* {data.get('tavsiya')}\n"
            f"🔍 *Surishtirish rozi:* {data.get('surushtirishga_rozi')}\n"
            f"💵 *Oldingi maosh:* {data.get('oldingi_maosh')}\n"
            f"💰 *Kutilayotgan maosh:* {data.get('kutilayotgan_maosh')}\n"
            f"📆 *Ishlash muddati:* {data.get('ishlash_muddati')}\n"
            f"🕐 *Qolib ishlash:* {data.get('qolib_ishlash')}\n"
            f"⏰ *Smena:* {data.get('smena')}\n\n"
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
            "🔔 YANGI ARIZA KELDI!\n\n"
            f"👤 {data.get('ism_familiya_sharif')}\n"
            f"📱 {data.get('telefon')}\n"
            f"📅 {data.get('tug_sana')} | 🌍 {data.get('millat')}\n"
            f"🗺 {data.get('tug_joy')}\n"
            f"🏠 {data.get('yashash_joy')} ({data.get('turar_joy')})\n"
            f"🎓 {data.get('talim')}\n"
            f"🏫 {data.get('oquv_yurti')}\n"
            f"💼 {data.get('oldingi_ish')}\n"
            f"✈️ {data.get('chet_safari')}\n"
            f"💑 {data.get('oilaviy_holat')} | 👨‍👩‍👧 {data.get('oila_azosi')}\n"
            f"⚖️ Sudlanganmi: {data.get('sudlanganmi')}\n"
            f"🚗 {data.get('avtomobil')} | 🪪 {data.get('haydovchilik')}\n"
            f"🗣 O'zbek: {data.get('uzbek_tili')} | Rus: {data.get('rus_tili')} | Ingliz: {data.get('ingliz_tili')}\n"
            f"🗣 Boshqa til: {data.get('boshqa_til')}\n"
            f"⭐ {data.get('qobiliyat')}\n"
            f"🎯 {data.get('bosh_vaqt')}\n"
            f"💻 {data.get('kompyuter')}\n"
            f"📢 {data.get('qayerdan_bildingiz')}\n"
            f"🤝 Kafil: {data.get('kafil')}\n"
            f"📄 Tavsiya: {data.get('tavsiya')}\n"
            f"🔍 Surishtirish: {data.get('surushtirishga_rozi')}\n"
            f"💵 Oldingi maosh: {data.get('oldingi_maosh')}\n"
            f"💰 Kutilayotgan: {data.get('kutilayotgan_maosh')}\n"
            f"📆 Muddati: {data.get('ishlash_muddati')}\n"
            f"🕐 Qolib ishlash: {data.get('qolib_ishlash')}\n"
            f"⏰ Smena: {data.get('smena')}\n\n"
            f"📲 @{username}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)
            logger.info(f"Admin ga xabar yuborildi: {ADMIN_CHAT_ID}")
        except Exception as e:
            logger.error(f"Admin ga xabar yuborishda xato: {e}")
            try:
                await context.bot.send_message(chat_id=f"@{ADMIN_USERNAME}", text=msg)
            except Exception as e2:
                logger.error(f"Backup ham xato: {e2}")
        user_anketa.pop(user_id, None)
        # Eski xabarni o'chirish (tasdiqlash tugmalari bilan xabar)
        try:
            await query.message.delete()
        except Exception:
            pass
        # Yangi rahmat xabari
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "🙏 *Anketani to'ldirganingiz uchun katta rahmat!*\n\n"
                "✅ Ma'lumotlaringiz muvaffaqiyatli saqlandi!\n\n"
                "🕐 Ko'rib chiqish muddati: 1-3 ish kuni\n"
                "📱 @Ottimo_hr tez orada siz bilan bog'lanadi\n\n"
                "Omad tilaymiz! 🌟\n\n"
                "📲 Murojaat uchun: https://t.me/ottimo_uz"
            ),
            parse_mode='Markdown',
            disable_web_page_preview=True,
            reply_markup=MAIN_MENU
        )
    elif query.data == "anketa_cancel":
        user_anketa.pop(user_id, None)
        await query.edit_message_text("❌ Anketa bekor qilindi.")
        await context.bot.send_message(chat_id=user_id, text="Bosh menyuga qaytdingiz.", reply_markup=MAIN_MENU)

# ===================== ASOSIY =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Foydalanuvchi"
    await update.message.reply_text(
        f"👋 Salom, *{user_name}*!\n\n🏢 *OTTIMO CAFE HR AGENTIGA XUSH KELIBSIZ!*\n\nQuyidagi bo'limlardan birini tanlang 👇",
        parse_mode='Markdown', reply_markup=MAIN_MENU)

def ask_gemini(user_id, user_text):
    history = user_sessions.get(user_id, [])
    history_text = ""
    if history:
        history_text = "\n\n" + "\n".join([f"Foydalanuvchi: {h['user']}\nAgent: {h['agent']}" for h in history[-5:]])
    full_prompt = "Sen Ottimo Cafe HR agentisan. Faqat O'zbek tilida javob ber." + history_text + f"\n\nFoydalanuvchi: {user_text}\nAgent:"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    r = requests.post(url, json={"contents": [{"parts": [{"text": full_prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}}, timeout=30)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id in user_anketa:
        await process_anketa(update, context); return
    if user_id in admin_state and admin_state[user_id].get("action") == "add_xodim":
        await process_add_xodim(update, context); return

    admin_handlers = {
        "👥 Xodimlar ro'yxati": show_xodimlar,
        "➕ Xodim qo'shish": start_add_xodim,
        "⚠️ Kechikish belgilash": start_kechikish,
        "📋 Arizalar ro'yxati": show_arizalar,
        "📊 Statistika": show_statistika,
    }
    if user_text in admin_handlers:
        await admin_handlers[user_text](update, context); return
    if user_text == "🔙 Bosh menyu":
        await update.message.reply_text("Bosh menyu:", reply_markup=MAIN_MENU); return
    if user_text == "🗑️ Suhbatni tozalash":
        user_sessions[user_id] = []
        await update.message.reply_text("✅ Tozalandi!", reply_markup=MAIN_MENU); return
    if user_text == "🆘 Yordam":
        await update.message.reply_text("Menyudan tanlang yoki savol yozing!", reply_markup=MAIN_MENU); return
    if user_text == "👨‍💼 Admin":
        await update.message.reply_text(
            "👨‍💼 *ADMIN*\n\n📱 @Ottimo_hr\n📞 +998 99 060 33 53\n\n👉 [Admin ga yozish](https://t.me/Ottimo_hr)",
            parse_mode='Markdown', reply_markup=MAIN_MENU, disable_web_page_preview=True); return
    if user_text == "📍 Filiallar":
        await update.message.reply_text(
            "📍 *OTTIMO CAFE FILIALLARI*\n\n"
            "1️⃣ *Nukus kinoteatri yonida*\n📌 Toshkent, Shifer ko'chasi, 71\n\n"
            "2️⃣ *Parus ostida*\n📌 Toshkent, Katartal ko'chasi, 60A/1\n\n"
            "3️⃣ *Talant International School ro'parasida*\n📌 Toshkent, Mirzo Ulug'bek, Buyuk Ipak Yo'li, 31\n\n"
            "📞 +998 99 060 33 53 | @Ottimo_hr",
            parse_mode='Markdown', reply_markup=MAIN_MENU); return
    if user_text == "📞 Qo'llab-quvvatlash":
        await update.message.reply_text(
            "📞 *Qo'llab-quvvatlash*\n\n📱 +998 99 060 33 53\n💬 @Ottimo_hr",
            parse_mode='Markdown', reply_markup=MAIN_MENU); return
    if user_text == "➕ Qo'shimcha savol":
        await update.message.reply_text("➕ Savolingizni yozing! 👇", reply_markup=MAIN_MENU); return
    if user_text == "👷 Ishchi qabul qilish":
        await start_anketa(update, context); return

    # Savol va Javob — AI javob beradi
    if user_text == "❓ Savol va Javob":
        await update.message.reply_text(
            "❓ *SAVOL VA JAVOB*\n\n"
            "Ottimo Cafe haqida istalgan savolingizni yozing — AI avtomatik javob beradi! 👇\n\n"
            "_Masalan: Ish vaqti qanday? Maosh qancha? Qanday hujjatlar kerak?_",
            parse_mode='Markdown', reply_markup=MAIN_MENU)
        return

    if user_text in STATIC_RESPONSES:
        await update.message.reply_text(STATIC_RESPONSES[user_text], parse_mode='Markdown', reply_markup=MAIN_MENU); return

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
