import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

SYSTEM_PROMPT = """Sen Ottimo Cafe (Toshkentdagi zamonaviy italyan-style kafe) uchun HR agentisan.
Faqat O'zbek tilida javob ber.

Ottimo Cafe haqida:
- 25 xodim ishlaydi
- Lavozimlari: barista, ofitsiant, oshpaz, kassir, menejer, tozalovchi
- Ish vaqti: 08:00-22:00 (2 smena: 08:00-15:00 va 15:00-22:00)
- Probatsiya muddati: 1 oy
- Ish haqi: Barista 3-4 mln, Ofitsiant 2.5-3.5 mln, Menejer 6-8 mln UZS
- O'zbekiston Mehnat kodeksiga mos ishlaydi

HR vazifalaring:
1. Xodim qabul - CV ko'rib chiqish, intervyu savollari, lavozim talablari
2. Onboarding - yangi xodimga nima kerakligini tushuntirish
3. Smena jadvali - taqsimlash, dam olish kunlari
4. Ish haqi - hisoblash, bonus, jarima
5. Ichki qoidalar - tartib, kafe standartlari
6. Mojarolar - hal qilish yo'llari
7. Mehnat qonunlari - O'zbekiston qonunchiligi bo'yicha

Har doim do'stona, aniq va amaliy javob ber."""

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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Salom"
    text = f"👋 Salom, {user_name}!\n\nMen *Ottimo Cafe HR Agentiman* 🍽️\n\nQuyidagi masalalarda yordam bera olaman:\n\n📋 Xodim qabul qilish\n📅 Smena jadvali\n💰 Ish haqi va bonuslar\n📝 Mehnat shartnomasi\n⚖️ Mehnat qonunlari\n🤝 Xodimlar bilan muammolar\n\nSavolingizni yozing!\n\n/help — yordam\n/clear — suhbatni tozalash"
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🆘 *Yordam*\n\nMenga istalgan HR savolini yozishingiz mumkin:\n\n• Barista uchun talablar qanday?\n• Yangi xodimni qanday qabul qilamiz?\n• Smena jadvalini qanday tuzish kerak?\n• Probatsiya muddati qancha?\n• Xodim shikoyat qilsa nima qilamiz?\n\n/start — Boshiga qaytish\n/clear — Suhbatni tozalash"
    await update.message.reply_text(text, parse_mode='Markdown')

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_sessions[update.effective_user.id] = []
    await update.message.reply_text("✅ Suhbat tozalandi!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    if user_id not in user_sessions:
        user_sessions[user_id] = []
    try:
        reply = ask_gemini(user_id, user_text)
        user_sessions[user_id].append({"user": user_text, "agent": reply})
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Xato: {e}")
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
