import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API keys
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini sozlash
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# HR Agent system prompt
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
1. Xodim qabul — CV ko'rib chiqish, intervyu savollari, lavozim talablari
2. Onboarding — yangi xodimga nima kerakligini tushuntirish
3. Smena jadvali — taqsimlash, dam olish kunlari
4. Ish haqi — hisoblash, bonus, jarima
5. Ichki qoidalar — tartib, kafe standartlari
6. Mojarolar — hal qilish yo'llari
7. Mehnat qonunlari — O'zbekiston qonunchiligi bo'yicha

Har doim do'stona, aniq va amaliy javob ber. Kerak bo'lsa ro'yxat yoki jadval ko'rinishida yoz."""

# Har bir foydalanuvchi uchun suhbat tarixi
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot ishga tushganda"""
    user_name = update.effective_user.first_name or "Salom"
    welcome_text = f"""👋 Salom, {user_name}!

Men **Ottimo Cafe HR Agentiman** 🍽️

Quyidagi masalalarda yordam bera olaman:

📋 Xodim qabul qilish
📅 Smena jadvali
💰 Ish haqi va bonuslar
📝 Mehnat shartnomasi
⚖️ Mehnat qonunlari
🤝 Xodimlar bilan muammolar

Savolingizni yozing, javob beraman!

/help — yordam
/clear — suhbatni tozalash"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam"""
    help_text = """🆘 *Yordam*

Menga istalgan HR savolini yozishingiz mumkin:

*Misol savollar:*
• Barista uchun talablar qanday?
• Yangi xodimni qanday qabul qilamiz?
• Smena jadvalini qanday tuzish kerak?
• Probatsiya muddati qancha?
• Xodim shikoyat qilsa nima qilamiz?
• Intervyu savollari tayyorlab ber

*Buyruqlar:*
/start — Boshiga qaytish
/clear — Suhbatni tozalash
/help — Yordam"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suhbat tarixini tozalash"""
    user_id = update.effective_user.id
    user_sessions[user_id] = []
    await update.message.reply_text("✅ Suhbat tozalandi. Yangi savol bering!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarlarni qayta ishlash"""
    user_id = update.effective_user.id
    user_text = update.message.text

    # Typing ko'rsatish
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Suhbat tarixini olish yoki yangi yaratish
    if user_id not in user_sessions:
        user_sessions[user_id] = []

    try:
        # Gemini ga yuborish
        chat_history = user_sessions[user_id]
        
        # To'liq prompt
        full_prompt = f"{SYSTEM_PROMPT}\n\nFoydalanuvchi: {user_text}"
        
        if chat_history:
            # Oldingi suhbatni qo'shish
            history_text = "\n".join([
                f"Foydalanuvchi: {h['user']}\nAgent: {h['agent']}"
                for h in chat_history[-5:]  # Oxirgi 5 ta
            ])
            full_prompt = f"{SYSTEM_PROMPT}\n\nOldingi suhbat:\n{history_text}\n\nFoydalanuvchi: {user_text}"

        response = model.generate_content(full_prompt)
        reply = response.text

        # Tarixga qo'shish
        user_sessions[user_id].append({
            "user": user_text,
            "agent": reply
        })

        # Javob yuborish
        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Xato: {e}")
        await update.message.reply_text(
            "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring yoki /clear buyrug'ini ishlating."
        )

def main():
    """Botni ishga tushirish"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
