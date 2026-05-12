import asyncio
import logging
import os
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from browser import PerchanceBrowser

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_env_file(env_path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs from .env into process environment."""
    if not env_path.exists():
        return

    try:
        raw_content = env_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.error("Failed to decode %s as UTF-8; skipping env loading.", env_path)
        return

    for raw_line in raw_content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

# Load token from env
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Shared browser instance
browser: PerchanceBrowser = None

# Queue to handle one request at a time
queue = asyncio.Queue()
queue_lock = asyncio.Lock()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👾 *Perchance AI Character Generator Bot*\n\n"
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
        "⏳ Generation takes about 10-20 seconds.\n"
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

    # Tell user we received it
    status_msg = await update.message.reply_text(
        f"📋 Your request has been queued...\n\nPrompt: {prompt}"
    )

    # Add to queue
    await queue.put((update, context, prompt, status_msg))


async def process_queue():
    """Background worker that processes one generation at a time."""
    while True:
        update, context, prompt, status_msg = await queue.get()
        try:
            await status_msg.edit_text(
                f"⚙️ Generating your character...\n\nPrompt: {prompt}\n\n⏳ Please wait 10-20 seconds..."
            )

            image_path = await browser.generate(prompt)

            if image_path:
                with open(image_path, "rb") as image_file:
                    await update.message.reply_photo(
                        photo=image_file,
                        caption=f"✅ Done!\n\nPrompt: {prompt}"
                    )
                await status_msg.delete()
                # Clean up temp image
                if os.path.exists(image_path):
                    os.remove(image_path)
            else:
                await status_msg.edit_text(
                    "❌ Generation failed. The site may be busy or the prompt was rejected. Please try again."
                )

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            await status_msg.edit_text(
                "❌ Something went wrong. Please try again later."
            )
        finally:
            queue.task_done()
            # Small delay between requests to avoid hammering the site
            await asyncio.sleep(3)


async def post_init(application: Application):
    """Called after bot starts — initialize browser and queue worker."""
    global browser
    logger.info("Initializing browser...")
    browser = PerchanceBrowser()
    await browser.init()
    logger.info("Browser ready!")

    # Start queue processor as background task
    asyncio.create_task(process_queue())


async def post_shutdown(application: Application):
    """Called on shutdown — close browser."""
    if browser:
        await browser.close()


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable not set!")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
