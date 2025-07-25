import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
from openai import AsyncOpenAI
from telegram.error import BadRequest
from model_utils import set_model, get_model, get_model_or_default, has_model

from keep_alive import keep_alive

keep_alive()
# بارگذاری توکن‌ها
load_dotenv()
BOT_TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = AsyncOpenAI(api_key=OPENROUTER_API_KEY,
                     base_url="https://openrouter.ai/api/v1")

# مدل‌های قابل انتخاب
models = {
    "DeepSeek": "tngtech/deepseek-r1t2-chimera:free",
    "Moonshot": "moonshotai/kimi-k2:free",
    "Qwen": "qwen/qwen3-235b-a22b-07-25:free",
}


# دریافت پاسخ از API
async def ask_openrouter(prompt: str, model_id: str) -> str:
    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[{
                "role": "system",
                "content": "تو یک دستیار فارسی‌زبان هستی."
            }, {
                "role": "user",
                "content": prompt
            }])
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ خطا در API:", e)
        return "متاسفم، نشد پاسخ بدم."


# حذف دو پیام (کاربر و ربات) بعد از زمان مشخص
def delete_both(context, chat_id, user_msg_id, bot_msg_id, delay=30):

    async def delete(ctx):
        for msg_id in [user_msg_id, bot_msg_id]:
            try:
                await ctx.bot.delete_message(chat_id=chat_id,
                                             message_id=msg_id)
            except BadRequest:
                pass

    context.job_queue.run_once(delete, when=delay)


# انتخاب مدل با دکمه
async def setmodel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton(name, callback_data=name)]
               for name in models]
    markup = InlineKeyboardMarkup(buttons)
    msg = await update.message.reply_text("🧠 یکی از مدل‌های زیر رو انتخاب کن:",
                                          reply_markup=markup)
    context.job_queue.run_once(
        lambda ctx: ctx.bot.delete_message(chat_id=msg.chat_id,
                                           message_id=msg.message_id), 60)


# دکمه انتخاب مدل زده شد
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chosen = query.data
    if chosen not in models:
        await query.answer("مدل معتبر نیست.")
        return
    set_model(user_id, models[chosen])
    msg = await query.edit_message_text(f"✅ مدل شما تنظیم شد به: {chosen}")
    context.job_queue.run_once(
        lambda ctx: ctx.bot.delete_message(chat_id=msg.chat_id,
                                           message_id=msg.message_id), 30)
    await query.answer()


# نمایش مدل فعلی کاربر
async def show_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reply_msg = ""
    if has_model(user_id):
        reply_msg = f"🔍 مدل فعلی شما:\n`{get_model(user_id)}`"
    else:
        reply_msg = "❗ هنوز هیچ مدلی انتخاب نکردی.\nاستفاده از `/setmodel` توصیه میشه."

    reply = await update.message.reply_text(reply_msg, parse_mode="Markdown")
    delete_both(context, update.effective_chat.id, update.message.message_id,
                reply.message_id)


    # پیام کاربر رسید و باید پاسخ بدیم طبق مدل انتخاب‌شده
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # بررسی اعتبار پیام و وجود متن
    if not message or not message.text:
        print("⚠️ پیام نامعتبر بود یا متن نداشت.")
        return

    text = message.text
    bot_username = (await context.bot.get_me()).username

    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP
                             ] and f"@{bot_username}" not in text:
        return

    if f"@{bot_username}" in text:
        text = text.replace(f"@{bot_username}", "").strip()

    user_id = message.from_user.id

    if not has_model(user_id):
        reply = await message.reply_text(
            "⛔ شما هنوز هیچ مدلی انتخاب نکردی!\nاز دستور `/setmodel` استفاده کن."
        )
        delete_both(context, message.chat_id, message.message_id,
                    reply.message_id)
        return

    model_id = get_model_or_default(user_id)
    thinking = await message.reply_text("🤖 در حال فکر کردن...")

    context.job_queue.run_once(
        lambda ctx: ctx.bot.delete_message(chat_id=thinking.chat_id,
                                           message_id=thinking.message_id), 10)

    response = await ask_openrouter(text, model_id)
    await message.reply_text(response)


# اجرا
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("setmodel", setmodel))
app.add_handler(CommandHandler("model", show_model))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                               handle_message))

print("🚀 ربات آماده و در حال اجراست...")
app.run_polling()
