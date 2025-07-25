import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
from openai import AsyncOpenAI
from telegram.error import BadRequest
from model_utils import set_model, get_model, get_model_or_default, has_model

load_dotenv()
BOT_TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = AsyncOpenAI(api_key=OPENROUTER_API_KEY,
                     base_url="https://openrouter.ai/api/v1")

models = {
    "DeepSeek": "tngtech/deepseek-r1t2-chimera:free",
    "Moonshot": "moonshotai/kimi-k2:free",
    "Qwen": "qwen/qwen3-235b-a22b-07-25:free"
}


async def ask_openrouter(prompt: str, model_id: str) -> str:
    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "تو یک دستیار فارسی‌زبان هستی."},
                {"role": "user", "content": prompt}
            ])
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ خطا در API:", e)
        return "متاسفم، نشد پاسخ بدم."


async def setmodel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton(name, callback_data=name)] for name in models]
    markup = InlineKeyboardMarkup(buttons)
    msg = await update.message.reply_text("🧠 یکی از مدل‌های زیر رو انتخاب کن:", reply_markup=markup)

    if context.job_queue:
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id), 60)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chosen = query.data

    if chosen not in models:
        await query.answer("مدل معتبر نیست.")
        return

    set_model(user_id, models[chosen])
    msg = await query.edit_message_text(f"✅ مدل شما تنظیم شد به: {chosen}")
    await query.answer()

    if context.job_queue:
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id), 30)


async def show_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reply_msg = (
        f"🔍 مدل فعلی شما:\n`{get_model(user_id)}`"
        if has_model(user_id)
        else "❗ هنوز هیچ مدلی انتخاب نکردی.\nاستفاده از `/setmodel` توصیه میشه."
    )
    reply = await update.message.reply_text(reply_msg, parse_mode="Markdown")

    if context.job_queue:
        context.job_queue.run_once(
            lambda ctx: [ctx.bot.delete_message(chat_id=update.effective_chat.id, message_id=id)
                         for id in [update.message.message_id, reply.message_id]],
            30
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        print("⚠️ پیام نامعتبر بود یا متن نداشت.")
        return

    text = message.text
    bot_username = (await context.bot.get_me()).username

    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] and f"@{bot_username}" not in text:
        return

    if f"@{bot_username}" in text:
        text = text.replace(f"@{bot_username}", "").strip()

    user_id = message.from_user.id

    if not has_model(user_id):
        reply = await message.reply_text("⛔ هنوز هیچ مدلی انتخاب نکردی!\nاز دستور `/setmodel` استفاده کن.")
        if context.job_queue:
            context.job_queue.run_once(
                lambda ctx: [ctx.bot.delete_message(chat_id=message.chat_id, message_id=id)
                             for id in [message.message_id, reply.message_id]], 30
            )
        return

    model_id = get_model_or_default(user_id)
    thinking = await message.reply_text("🤖 در حال فکر کردن...")

    if context.job_queue:
        context.job_queue.run_once(
            lambda ctx: ctx.bot.delete_message(chat_id=thinking.chat_id, message_id=thinking.message_id), 10
        )

    response = await ask_openrouter(text, model_id)
    await message.reply_text(response)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("setmodel", setmodel))
    app.add_handler(CommandHandler("model", show_model))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_webhook(
        listen="0.0.0.0",
        port=8080,
        webhook_url="https://telegram-ai-bot-xyal.onrender.com/"
    )


if __name__ == "__main__":
    main()
