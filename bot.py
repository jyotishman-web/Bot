import asyncio
import logging
import os
import httpx
import urllib.parse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Queue to handle one request at a time
queue = asyncio.Queue()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👾 *AI Character Generator Bot*\n\n"
        "Send me a character description and I'll generate an image for you!\n\n"
        "Example: `warrior elf girl with blue hair`\n\n"
        "⚠️ This bot generates *18+ content*. By using it, you confirm you are 18 or older.",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to use:*\n\n"
        "Just send any character description as a message.\n\n"
        "🔹 Good prompts:\n"
        "• `anime girl with red eyes and silver hair`\n"
        "• `muscular knight in dark armor`\n"
        "• `cute wizard with a magic staff`\n\n"
        "⏳ Generation takes about 5-10 seconds.\n"
        "📋 Requests are queued if multiple users send at once.",
        parse_mode="Markdown"
    )


async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text.strip()
    user = update.message.from_user

    if not prompt:
        await update.message.reply_text("Please send a character description!")
        return

    logger.info(f"User {user.id} ({user.username}) requested: {prompt}")

    status_msg = await update.message.reply_text(
        f"📋 Queued...\n\n*Prompt:* `{prompt}`",
        parse_mode="Markdown"
    )

    await queue.put((update, context, prompt, status_msg))


async def process_queue():
    """Background worker — processes one generation at a time."""
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            update, context, prompt, status_msg = await queue.get()
            try:
                await status_msg.edit_text(
                    f"⚙️ Generating...\n\n*Prompt:* `{prompt}`\n\n⏳ Please wait ~5-10 seconds...",
                    parse_mode="Markdown"
                )

                # Build Pollinations.ai URL
                encoded = urllib.parse.quote(prompt)
                seed = int(asyncio.get_event_loop().time() * 1000) % 999999
                url = (
                    f"https://image.pollinations.ai/prompt/{encoded}"
                    f"?model=flux&width=768&height=768&nologo=true&nsfw=true&seed={seed}"
                )

                logger.info(f"Fetching image from Pollinations: {url}")
                response = await client.get(url, follow_redirects=True)

                content_type = response.headers.get("content-type", "")
                if response.status_code == 200 and content_type.startswith("image"):
                    await update.message.reply_photo(
                        photo=response.content,
                        caption=f"✅ *Done!*\n\n*Prompt:* `{prompt}`",
                        parse_mode="Markdown"
                    )
                    await status_msg.delete()
                else:
                    logger.error(f"Bad response: {response.status_code} | {content_type}")
                    await status_msg.edit_text(
                        "❌ Generation failed. Please try again with a different prompt."
                    )

            except httpx.TimeoutException:
                logger.error("Timeout from Pollinations")
                await status_msg.edit_text(
                    "⏱️ Timed out — the server is busy. Please try again in a moment."
                )
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await status_msg.edit_text(
                    "❌ Something went wrong. Please try again."
                )
            finally:
                queue.task_done()
                await asyncio.sleep(1)


async def post_init(application: Application):
    asyncio.create_task(process_queue())
    logger.info("Queue worker started. Bot ready!")


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable not set!")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
