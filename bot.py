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
ADMIN_CHAT_ID = 206004279

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

# ===================== ANKETA SAVOLLARI =====================
ANKETA_STEPS = [
    ("ism_familiya_sharif", "👤 1/31 — Ism, Familiya va Sharifingizni kiriting:\n(Masalan: Ibrohim Karimov Aliyevich)"),
    ("tug_sana",            "📅 2/31 — Tug'ilgan sanangizni kiriting:\n(Masalan: 15.03.2000)"),
    ("millat",              "🌍 3/31 — Millatingizni kiriting:\n(Masalan: O'zbek)"),
    ("tug_joy",             "🗺 4/31 — Tug'ilgan joyingizni kiriting (viloyat, tuman):\n(Masalan: Toshkent shahri, Chilonzor tumani)"),
    ("yashash_joy",         "🏠 5/31 — Doimiy yashash manzilingizni kiriting:\n(Ko'cha, uy raqami)"),
    ("turar_joy",           "🏘 6/31 — Turar joy turingizni belgilang:\n(Dom / Hovli)"),
    ("telefon",             "📱 7/31 — Telefon raqamingizni kiriting:\n(Masalan: +998 90 123 45 67)"),
    ("talim",               "🎓 8/31 — Ta'lim darajangizni belgilang:\n(Maktab 11-sinf / Kollej-litsey / Institut-universitet)"),
    ("oquv_yurti",          "🏫 9/31 — Qaysi o'quv yurtini va qachon tamomlagansiz?\n(O'quv yurti nomi, fakultet, o'qish yillari.\nYo'q bo'lsa — Yo'q deb yozing)"),
    ("oldingi_ish",         "💼 10/31 — Oldingi ish joylaringiz haqida ma'lumot bering:\n(Korxona nomi, lavozim, ishlagan yillar, ishdan bo'shash sababi.\nYo'q bo'lsa — Yo'q deb yozing)"),
    ("chet_safari",         "✈️ 11/31 — Chet el safariga chiqqanmisiz?\n(Ha bo'lsa — qaysi mamlakatga va maqsad nima edi?\nYo'q bo'lsa — Yo'q deb yozing)"),
    ("oilaviy_holat",       "💑 12/31 — Oilaviy holatingizni belgilang:\n(Bo'ydoq / Turmush qurgan / Ajrashgan)"),
    ("oila_azosi",          "👨‍👩‍👧 13/31 — Oila a'zolaringiz haqida ma'lumot bering:\n(Ism-familiya, tug'ilgan sana, ish joyi, telefon raqami.\nYo'q bo'lsa — Yo'q deb yozing)"),
    ("sudlanganmi",         "⚖️ 14/31 — Sudlanganmisiz?\n(Yo'q / Ha bo'lsa — sababini yozing)"),
    ("avtomobil",           "🚗 15/31 — Shaxsiy avtomobilingiz bormi?\n(Yo'q / Ha bo'lsa — rusumini yozing)"),
    ("haydovchilik",        "🪪 16/31 — Haydovchilik guvohnomangiz bormi?\n(Yo'q / Ha bo'lsa — turini yozing: A, B, C, D yoki E)"),
    ("uzbek_tili",          "🗣 17/31 — O'zbek tilini qay darajada bilasiz?\n(A'lo / Yaxshi / Past)"),
    ("rus_tili",            "🗣 18/31 — Rus tilini qay darajada bilasiz?\n(A'lo / Yaxshi / Past / Bilmayman)"),
    ("ingliz_tili",         "🗣 19/31 — Ingliz tilini qay darajada bilasiz?\n(A'lo / Yaxshi / Past / Bilmayman)"),
    ("boshqa_til",          "🗣 20/31 — Boshqa tillarni bilasizmi?\n(Yo'q / Ha bo'lsa — qaysi til va darajasini yozing)"),
    ("qobiliyat",           "⭐ 21/31 — Alohida qobiliyatlaringiz bormi?\n(Masalan: oshpazlik, rasmchilik, musiqa...\nYo'q bo'lsa — Yo'q deb yozing)"),
    ("bosh_vaqt",           "🎯 22/31 — Bo'sh vaqtingizni qanday o'tkazasiz?\n(Masalan: sport, kitob o'qish, sayohat...)"),
    ("kompyuter",           "💻 23/31 — Kompyuterda ishlash darajangizni belgilang:\n(Erkin / O'rta darajada / Bilmayman)"),
    ("qayerdan_bildingiz",  "📢 24/31 — Kompaniyamiz haqida qayerdan bildingiz yoki kim taklif qildi?\n(Masalan: do'stim, Instagram, OLX...)"),
    ("kafil",               "🤝 25/31 — Sizni korxonamizda ishlashingizga kafolat bera oladigan shaxs bormi?\n(Ismi, siz bilan aloqasi, ish joyi va telefon raqami.\nYo'q bo'lsa — Yo'q deb yozing)"),
    ("tavsiya",             "📄 26/31 — Oxirgi ish joyingizdan tavsiya xati bera oladimi?\n(Ha bo'lsa — ismi, lavozimi va telefon raqami.\nYo'q bo'lsa — Yo'q deb yozing)"),
    ("surushtirishga_rozi", "🔍 27/31 — Oxirgi ish joyingizdan surishtirishimizga rozimisiz?\n(Ha / Yo'q)"),
    ("oldingi_maosh",       "💵 28/31 — Oxirgi ish joyingizda qancha oylik maosh olgan edingiz?\n(Masalan: 1 500 000 so'm)"),
    ("kutilayotgan_maosh",  "💰 29/31 — Bizdan qancha oylik maosh kutasiz?\n(Masalan: 2 000 000 so'm)"),
    ("ishlash_muddati",     "📆 30/31 — Bizning korxonamizda qancha muddat ishlashni rejalashtirasiz?\n(Masalan: uzoq muddatga / 1 yil / hali aniq emas)"),
    ("smena",               "⏰ 31/31 — Qaysi vaqtda ishlashni xohlaysiz?\n\n☀️ Kunduzi (07:30 — 16:30)\n🌙 Kechki payt (16:00 — 24:00)\n🔄 Ikkalasi ham bo'ladi"),
]

SMENA_MENU = ReplyKeyboardMarkup([
    ["☀️ Kunduzi (07:30-16:30)"],
    ["🌙 Kechki payt (16:00-24:00)"],
    ["🔄 Ikkalasi ham bo'ladi"]
], resize_keyboard=True, one_time_keyboard=True)

# ===================== STATIK JAVOBLAR =====================
STATIC_RESPONSES = {
    "⏰ Ish vaqti": (
        "⏰ ISH VAQTI\n\n"
        "☀️ 1-smena: 07:30 — 16:30 (kunduzi)\n"
        "🌙 2-smena: 16:00 — 24:00 (kechki payt)\n\n"
        "📅 Smena jadvali har dushanba yangilanadi\n"
        "Smena o'zgarishi kamida 1 kun oldin xabar beriladi\n"
        "Smena almashtirish faqat menejer ruxsati bilan amalga oshiriladi\n\n"
        "⚠️ Smenaga kechikish uchun jarima: 50 000 so'm\n"
        "🍽 Har bir smenada xodimlarga bepul ovqat beriladi"
    ),
    "📊 Ish ma'lumotlari": (
        "📊 OTTIMO CAFE HAQIDA\n\n"
        "Ottimo — Toshkentdagi zamonaviy va qulay kafe. "
        "Bizning maqsadimiz — mijozlarga yoqimli muhit va sifatli xizmat ko'rsatish.\n\n"
        "✅ Rasmiy mehnat shartnomasi\n"
        "✅ Maosh har 10 kunda to'lanadi\n"
        "✅ Har smenada bepul ovqat\n"
        "✅ Karyera o'sishi va rivojlanish imkoniyati\n"
        "✅ Do'stona va professional jamoa (25+ xodim)\n"
        "✅ Barqaror ish joyi\n"
        "✅ Zamonaviy ish sharoiti\n\n"
        "💼 Bo'sh ish o'rinlari:\n"
        "☕ Barista\n"
        "💳 Kassir\n"
        "🍰 Konditer-sotuvchi\n\n"
        "📍 Filiallar:\n"
        "1. Nukus kinoteatri yonida — Shifer ko'chasi, 71\n"
        "2. Parus ostida — Katartal ko'chasi, 60A/1\n"
        "3. Talant International School ro'parasida — Buyuk Ipak Yo'li, 31\n\n"
        "📞 +998 99 060 33 53 | @Ottimo_hr"
    ),
    "🤝 Xodimlar muammolari": (
        "🤝 XODIMLAR MUAMMOLARINI HAL QILISH\n\n"
        "Muammo yuzaga kelganda quyidagi tartibda harakat qiling:\n\n"
        "1-qadam: Muammoni bevosita hamkasbingiz bilan muhokama qiling\n"
        "2-qadam: Hal bo'lmasa, smena menejeriga murojaat qiling\n"
        "3-qadam: Menejer yordam bera olmasa, HR ga yozing: @Ottimo_hr\n\n"
        "⚠️ Ish joyida baland ovozda janjallashish mutlaqo man etiladi\n"
        "⚠️ Muammolarni mijozlar oldida muhokama qilmang\n\n"
        "✅ Har bir murojaat ko'rib chiqiladi\n"
        "✅ Adolatli qaror qabul qilinadi\n"
        "✅ Maxfiylik kafolatlanadi\n\n"
        "📞 +998 99 060 33 53 | @Ottimo_hr"
    ),
    "⚖️ Mehnat qonunlari": (
        "⚖️ MEHNAT QONUNLARI\n\n"
        "O'zbekiston Mehnat kodeksi asosida:\n\n"
        "✅ XODIM HUQUQLARI:\n"
        "• Belgilangan maosh o'z vaqtida to'lanadi\n"
        "• Yillik mehnat ta'tili (15-21 ish kuni)\n"
        "• Kasallik varag'i to'liq hisobga olinadi\n"
        "• Xavfsiz va qulay ish sharoiti\n"
        "• Rasmiy mehnat shartnomasi tuziladi\n"
        "• Ijtimoiy sug'urta qilinadi\n\n"
        "⚠️ XODIM MAJBURIYATLARI:\n"
        "• Ish tartibiga qat'iy rioya qilish\n"
        "• Belgilangan vaqtda ish joyida bo'lish\n"
        "• Kafe mulkiga ehtiyotkorlik bilan munosabatda bo'lish\n"
        "• Maxfiy ma'lumotlarni oshkor etmaslik\n\n"
        "🚫 MUTLAQO MAN ETILADI:\n"
        "• Ish vaqtida chekish\n"
        "• Spirtli ichimlik iste'mol qilish\n"
        "• Mijozlarga qo'pollik qilish\n\n"
        "📞 @Ottimo_hr"
    ),
}

# ===================== MENYULAR =====================
MAIN_MENU = ReplyKeyboardMarkup([
    ["👷 Ishchi qabul qilish", "❓ Savol va Javob", "⏰ Ish vaqti"],
    ["📊 Ish ma'lumotlari", "🤝 Xodimlar muammolari", "⚖️ Mehnat qonunlari"],
    ["📍 Filiallar", "📞 Qo'llab-quvvatlash", "🌐 Til tanlash"],
    ["👨‍💼 Admin", "🆘 Yordam", "🗑️ Suhbatni tozalash"]
], resize_keyboard=True)

ADMIN_MENU = ReplyKeyboardMarkup([
    ["👥 Xodimlar ro'yxati", "➕ Xodim qo'shish"],
    ["⚠️ Kechikish belgilash", "📋 Arizalar ro'yxati"],
    ["📊 Statistika", "🔙 Bosh menyu"]
], resize_keyboard=True)

ADMIN_ADD_STEPS = [
    ("ism",     "👤 Xodimning ismi:"),
    ("lavozim", "🎯 Lavozimi: (Barista / Kassir / Konditer)"),
    ("telefon", "📱 Telefon raqami:"),
    ("smena",   "⏰ Smenasi: (Kunduzi / Kechki payt / Ikkalasi)"),
]

user_sessions = {}
user_anketa = {}
admin_state = {}

# ===================== ADMIN =====================
async def show_xodimlar(update, context):
    xodimlar = db_query("SELECT id, ism, lavozim, smena FROM xodimlar WHERE holat='aktiv'", fetchall=True)
    if not xodimlar:
        await update.message.reply_text("Xodimlar ro'yxati bo'sh.", reply_markup=ADMIN_MENU); return
    text = "XODIMLAR RO'YXATI\n\n"
    for x in xodimlar:
        text += f"#{x[0]} {x[1]}\nLavozim: {x[2]} | Smena: {x[3]}\n\n"
    await update.message.reply_text(text, reply_markup=ADMIN_MENU)

async def show_statistika(update, context):
    jami = db_query("SELECT COUNT(*) FROM xodimlar WHERE holat='aktiv'", fetchone=True)[0]
    arizalar = db_query("SELECT COUNT(*) FROM arizalar WHERE holat='kutilmoqda'", fetchone=True)[0]
    kechikish = db_query("SELECT COUNT(*) FROM kechikishlar", fetchone=True)[0]
    await update.message.reply_text(
        f"STATISTIKA\n\nAktiv xodimlar: {jami}\nKutilayotgan arizalar: {arizalar}\nJami kechikishlar: {kechikish}",
        reply_markup=ADMIN_MENU)

async def show_arizalar(update, context):
    arizalar = db_query("SELECT id, ism, telefon, lavozim, smena, sana FROM arizalar WHERE holat='kutilmoqda'", fetchall=True)
    if not arizalar:
        await update.message.reply_text("Kutilayotgan ariza yo'q.", reply_markup=ADMIN_MENU); return
    text = "ARIZALAR\n\n"
    for a in arizalar:
        text += f"#{a[0]} {a[1]}\nTelefon: {a[2]} | Lavozim: {a[3]} | Smena: {a[4]}\nSana: {a[5]}\n\n"
    await update.message.reply_text(text, reply_markup=ADMIN_MENU)

async def start_add_xodim(update, context):
    user_id = update.effective_user.id
    admin_state[user_id] = {"action": "add_xodim", "step": 0, "data": {}}
    await update.message.reply_text("YANGI XODIM QO'SHISH\n\n" + ADMIN_ADD_STEPS[0][1], reply_markup=ReplyKeyboardRemove())

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
        await update.message.reply_text(f"{data['ism']} xodimlar ro'yxatiga muvaffaqiyatli qo'shildi!", reply_markup=ADMIN_MENU)

async def start_kechikish(update, context):
    xodimlar = db_query("SELECT id, ism FROM xodimlar WHERE holat='aktiv'", fetchall=True)
    if not xodimlar:
        await update.message.reply_text("Xodimlar yo'q.", reply_markup=ADMIN_MENU); return
    keyboard = [[InlineKeyboardButton(x[1], callback_data=f"kechik_{x[0]}")] for x in xodimlar]
    await update.message.reply_text("Qaysi xodim kechikdi?", reply_markup=InlineKeyboardMarkup(keyboard))

async def kechikish_callback(update, context):
    query = update.callback_query
    await query.answer()
    xodim_id = int(query.data.split("_")[1])
    xodim = db_query("SELECT ism FROM xodimlar WHERE id=?", (xodim_id,), fetchone=True)
    db_query("INSERT INTO kechikishlar (xodim_id, sana, minut) VALUES (?,?,?)",
             (xodim_id, datetime.now().strftime("%d.%m.%Y"), 15))
    await query.edit_message_text(f"{xodim[0]} kechikishi belgilandi. Jarima: 50 000 so'm")

# ===================== ANKETA =====================
async def start_anketa(update, context):
    user_id = update.effective_user.id
    user_anketa[user_id] = {"step": 0, "data": {}}
    await update.message.reply_text(
        f"OTTIMO CAFE — ISH UCHUN ARIZA\n\nJami {len(ANKETA_STEPS)} ta savol.\n"
        "Bekor qilish uchun /bekor deb yozing.\n\n" + ANKETA_STEPS[0][1],
        reply_markup=ReplyKeyboardRemove())

async def process_anketa(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "/bekor":
        user_anketa.pop(user_id, None)
        await update.message.reply_text("Ariza bekor qilindi.", reply_markup=MAIN_MENU); return

    step_data = user_anketa[user_id]
    current_step = step_data["step"]
    key, _ = ANKETA_STEPS[current_step]
    step_data["data"][key] = text
    next_step = current_step + 1

    if next_step < len(ANKETA_STEPS):
        step_data["step"] = next_step
        next_key, next_question = ANKETA_STEPS[next_step]
        if next_key == "smena":
            await update.message.reply_text(next_question, reply_markup=SMENA_MENU)
        else:
            await update.message.reply_text(next_question, reply_markup=ReplyKeyboardRemove())
    else:
        data = step_data["data"]
        db_query("INSERT INTO arizalar (ism, telefon, lavozim, smena, sana) VALUES (?,?,?,?,?)",
                 (data.get('ism_familiya_sharif'), data.get('telefon'), "Ko'rsatilmagan",
                  data.get('smena'), datetime.now().strftime("%d.%m.%Y")))

        summary = (
            "ANKETANGIZ TAYYOR! Iltimos, tekshirib ko'ring:\n\n"
            f"Ism, Familiya, Sharif: {data.get('ism_familiya_sharif')}\n"
            f"Tug'ilgan sana: {data.get('tug_sana')}\n"
            f"Millat: {data.get('millat')}\n"
            f"Tug'ilgan joy: {data.get('tug_joy')}\n"
            f"Yashash manzili: {data.get('yashash_joy')} ({data.get('turar_joy')})\n"
            f"Telefon: {data.get('telefon')}\n"
            f"Ta'lim: {data.get('talim')}\n"
            f"O'quv yurti: {data.get('oquv_yurti')}\n"
            f"Ish tajribasi: {data.get('oldingi_ish')}\n"
            f"Chet el safari: {data.get('chet_safari')}\n"
            f"Oilaviy holat: {data.get('oilaviy_holat')}\n"
            f"Oila a'zolari: {data.get('oila_azosi')}\n"
            f"Sudlanganmi: {data.get('sudlanganmi')}\n"
            f"Avtomobil: {data.get('avtomobil')}\n"
            f"Haydovchilik guvohnomasi: {data.get('haydovchilik')}\n"
            f"O'zbek tili: {data.get('uzbek_tili')}\n"
            f"Rus tili: {data.get('rus_tili')}\n"
            f"Ingliz tili: {data.get('ingliz_tili')}\n"
            f"Boshqa tillar: {data.get('boshqa_til')}\n"
            f"Qobiliyatlar: {data.get('qobiliyat')}\n"
            f"Bo'sh vaqt: {data.get('bosh_vaqt')}\n"
            f"Kompyuter: {data.get('kompyuter')}\n"
            f"Qayerdan bildingiz: {data.get('qayerdan_bildingiz')}\n"
            f"Kafil shaxs: {data.get('kafil')}\n"
            f"Tavsiya xati: {data.get('tavsiya')}\n"
            f"Surishtirish roziligi: {data.get('surushtirishga_rozi')}\n"
            f"Oldingi maosh: {data.get('oldingi_maosh')}\n"
            f"Kutilayotgan maosh: {data.get('kutilayotgan_maosh')}\n"
            f"Ishlash muddati: {data.get('ishlash_muddati')}\n"
            f"Ish vaqti: {data.get('smena')}\n\n"
            "Tasdiqlaysizmi?"
        )
        confirm_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="anketa_confirm"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data="anketa_cancel")
        ]])
        await update.message.reply_text(summary, reply_markup=confirm_keyboard)

async def anketa_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "anketa_confirm":
        data = user_anketa.get(user_id, {}).get("data", {})
        username = query.from_user.username or "username_yoq"

        msg = (
            "YANGI ARIZA KELDI!\n\n"
            f"Ism: {data.get('ism_familiya_sharif')}\n"
            f"Telefon: {data.get('telefon')}\n"
            f"Tug'ilgan sana: {data.get('tug_sana')} | Millat: {data.get('millat')}\n"
            f"Tug'ilgan joy: {data.get('tug_joy')}\n"
            f"Yashash manzili: {data.get('yashash_joy')} ({data.get('turar_joy')})\n"
            f"Ta'lim: {data.get('talim')}\n"
            f"O'quv yurti: {data.get('oquv_yurti')}\n"
            f"Ish tajribasi: {data.get('oldingi_ish')}\n"
            f"Chet el safari: {data.get('chet_safari')}\n"
            f"Oilaviy holat: {data.get('oilaviy_holat')}\n"
            f"Oila a'zolari: {data.get('oila_azosi')}\n"
            f"Sudlanganmi: {data.get('sudlanganmi')}\n"
            f"Avtomobil: {data.get('avtomobil')} | Haydovchilik: {data.get('haydovchilik')}\n"
            f"O'zbek tili: {data.get('uzbek_tili')} | Rus tili: {data.get('rus_tili')} | Ingliz tili: {data.get('ingliz_tili')}\n"
            f"Boshqa tillar: {data.get('boshqa_til')}\n"
            f"Qobiliyatlar: {data.get('qobiliyat')}\n"
            f"Bo'sh vaqt: {data.get('bosh_vaqt')}\n"
            f"Kompyuter: {data.get('kompyuter')}\n"
            f"Qayerdan bildingiz: {data.get('qayerdan_bildingiz')}\n"
            f"Kafil shaxs: {data.get('kafil')}\n"
            f"Tavsiya xati: {data.get('tavsiya')}\n"
            f"Surishtirish roziligi: {data.get('surushtirishga_rozi')}\n"
            f"Oldingi maosh: {data.get('oldingi_maosh')}\n"
            f"Kutilayotgan maosh: {data.get('kutilayotgan_maosh')}\n"
            f"Ishlash muddati: {data.get('ishlash_muddati')}\n"
            f"Ish vaqti: {data.get('smena')}\n\n"
            f"Telegram: @{username}"
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
        try:
            await query.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "Anketani to'ldirganingiz uchun katta rahmat!\n\n"
                "Ma'lumotlaringiz muvaffaqiyatli saqlandi.\n\n"
                "Ko'rib chiqish muddati: 1-3 ish kuni\n"
                "@Ottimo_hr tez orada siz bilan bog'lanadi\n\n"
                "Omad tilaymiz!\n\n"
                "Murojaat uchun: https://t.me/ottimo_uz"
            ),
            reply_markup=MAIN_MENU
        )

    elif query.data == "anketa_cancel":
        user_anketa.pop(user_id, None)
        await query.edit_message_text("Ariza bekor qilindi.")
        await context.bot.send_message(chat_id=user_id, text="Bosh menyuga qaytdingiz.", reply_markup=MAIN_MENU)

# ===================== ASOSIY =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Foydalanuvchi"
    await update.message.reply_text(
        f"Salom, {user_name}!\n\nOttimo Cafe HR botiga xush kelibsiz!\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=MAIN_MENU)

def ask_gemini(user_id, user_text):
    history = user_sessions.get(user_id, [])
    # Ottimo mode tekshirish
    ottimo_mode = any(h.get("user") == "__ottimo_mode__" for h in history)

    history_text = ""
    clean_history = [h for h in history if h.get("user") != "__ottimo_mode__"]
    if clean_history:
        history_text = "\n\n" + "\n".join([
            f"Foydalanuvchi: {h['user']}\nAgent: {h['agent']}"
            for h in clean_history[-5:]
        ])

    # Til aniqlash
    lang = "uz"
    for h in history:
        if h.get("user") == "__lang_ru__":
            lang = "ru"; break
        elif h.get("user") == "__lang_en__":
            lang = "en"; break

    if lang == "ru":
        lang_instruction = "Отвечай только на русском языке."
    elif lang == "en":
        lang_instruction = "Reply only in English."
    else:
        lang_instruction = "Faqat o'zbek tilida javob ber."

    ottimo_info = (
        "Ottimo Cafe haqida to'liq ma'lumot:\n"
        "- Zamonaviy kafe, Toshkentda 3 ta filiali bor\n"
        "- Filiallar: 1) Nukus kinoteatri yonida, Shifer ko'chasi 71; "
        "2) Parus ostida, Katartal ko'chasi 60A/1; "
        "3) Talant International School ro'parasida, Buyuk Ipak Yo'li 31\n"
        "- Bo'sh ish o'rinlari: Barista, Kassir, Konditer-sotuvchi\n"
        "- Ish vaqti: kunduzi 07:30-16:30, kechki payt 16:00-24:00\n"
        "- Yosh talabi: 20-35 yosh\n"
        "- Rus tilini bilish shart\n"
        "- Chekmaydigan va spirtli ichimlik iste'mol qilmaydigan bo'lishi shart\n"
        "- Probatsiya muddati: 1 oy\n"
        "- Maosh har 10 kunda to'lanadi\n"
        "- Har smenada bepul ovqat beriladi\n"
        "- Bog'lanish: +998 99 060 33 53, @Ottimo_hr"
    )

    if ottimo_mode:
        system = (
            f"{lang_instruction}\n"
            "Sen Ottimo Cafe uchun maxsus HR yordamchisisisan.\n"
            "MUHIM QOIDA: Faqat Ottimo Cafe haqidagi savollarga javob ber.\n"
            "Agar savol Ottimo Cafe bilan bog'liq bo'lmasa: "
            "Kechirasiz, men faqat Ottimo Cafe haqidagi savollarga javob bera olaman, de.\n\n"
            + ottimo_info + "\n\nDo'stona va ijodiy tarzda javob ber."
        )
    else:
        system = (
            f"{lang_instruction}\n"
            "Sen Ottimo Cafe uchun HR agentisan.\n"
            + ottimo_info + "\nHar doim do'stona va aniq javob ber."
        )

    full_prompt = system + history_text + f"\n\nFoydalanuvchi: {user_text}\nAgent:"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={GEMINI_API_KEY}"
    r = requests.post(url, json={"contents": [{"parts": [{"text": full_prompt}]}],
                                  "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}}, timeout=30)
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
        await update.message.reply_text("Suhbat tozalandi!", reply_markup=MAIN_MENU); return
    if user_text == "🆘 Yordam":
        await update.message.reply_text(
            "Menyudan bo'lim tanlang yoki istalgan savolingizni yozing, javob beramiz!",
            reply_markup=MAIN_MENU); return
    if user_text == "👨‍💼 Admin":
        await update.message.reply_text(
            "Admin bilan bog'lanish:\n\nTelegram: @Ottimo_hr\nTelefon: +998 99 060 33 53\n\nIsh vaqti: 09:00 — 18:00",
            reply_markup=MAIN_MENU); return
    if user_text == "📍 Filiallar":
        await update.message.reply_text(
            "OTTIMO CAFE FILIALLARI\n\n"
            "1. Nukus kinoteatri yonida\n"
            "   Toshkent, Shifer ko'chasi, 71\n\n"
            "2. Parus ostida\n"
            "   Toshkent, Katartal ko'chasi, 60A/1\n\n"
            "3. Talant International School ro'parasida\n"
            "   Toshkent, Mirzo Ulug'bek tumani, Buyuk Ipak Yo'li, 31\n\n"
            "Telefon: +998 99 060 33 53\n"
            "Telegram: @Ottimo_hr",
            reply_markup=MAIN_MENU); return
    if user_text == "📞 Qo'llab-quvvatlash":
        await update.message.reply_text(
            "Qo'llab-quvvatlash xizmati:\n\nTelefon: +998 99 060 33 53\nTelegram: @Ottimo_hr",
            reply_markup=MAIN_MENU); return
    if user_text == "🌐 Til tanlash":
        lang_keyboard = ReplyKeyboardMarkup([
            ["🇺🇿 O'zbek tili"],
            ["🇷🇺 Русский язык"],
            ["🇬🇧 English"],
            ["🔙 Bosh menyu"]
        ], resize_keyboard=True)
        await update.message.reply_text(
            "Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=lang_keyboard)
        return

    if user_text == "🇺🇿 O'zbek tili":
        user_sessions[user_id] = [{"user": "__lang_uz__", "agent": "__lang_uz__"}]
        await update.message.reply_text(
            "O'zbek tili tanlandi! Endi savollaringizni o'zbek tilida berishingiz mumkin.",
            reply_markup=MAIN_MENU)
        return

    if user_text == "🇷🇺 Русский язык":
        user_sessions[user_id] = [{"user": "__lang_ru__", "agent": "__lang_ru__"}]
        await update.message.reply_text(
            "Выбран русский язык! Теперь вы можете задавать вопросы на русском языке.",
            reply_markup=MAIN_MENU)
        return

    if user_text == "🇬🇧 English":
        user_sessions[user_id] = [{"user": "__lang_en__", "agent": "__lang_en__"}]
        await update.message.reply_text(
            "English selected! Now you can ask questions in English.",
            reply_markup=MAIN_MENU)
        return

    if user_text == "➕ Qo'shimcha savol":
        await update.message.reply_text("Savolingizni yozing!", reply_markup=MAIN_MENU); return
    if user_text == "👷 Ishchi qabul qilish":
        await start_anketa(update, context); return
    if user_text == "❓ Savol va Javob":
        user_sessions[user_id] = [{"user": "__ottimo_mode__", "agent": "__ottimo_mode__"}]
        await update.message.reply_text(
            "Ottimo Cafe haqida istalgan savolingizni yozing!\n\n"
            "Masalan:\n"
            "— Filiallar qayerda joylashgan?\n"
            "— Ish vaqti qanday?\n"
            "— Qanday hujjatlar kerak?\n"
            "— Barista bo'lib ishlash uchun nima qilish kerak?",
            reply_markup=MAIN_MENU); return
    if user_text in STATIC_RESPONSES:
        await update.message.reply_text(STATIC_RESPONSES[user_text], reply_markup=MAIN_MENU); return

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
            "Hozirda texnik nosozlik yuz berdi. Iltimos, @Ottimo_hr ga murojaat qiling.",
            reply_markup=MAIN_MENU)

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
