import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Replace these
TELEGRAM_BOT_TOKEN = "8454552481:AAE5ha1HvydBHbPqmNb79scQQfNJmdlT0Hw"
OPENROUTER_API_KEY = "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"

MODEL = "openai/gpt-oss-20b:free"

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I am your AI bot 🤖 Send me a message.")

# AI chat function
def ask_ai(user_text):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": user_text}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        result = response.json()

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Error: {e}"

# Handle user messages
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    await update.message.reply_text("Thinking...")

    reply = ask_ai(user_text)

    if len(reply) > 4000:
        reply = reply[:4000]

    await update.message.reply_text(reply)

# Main
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
