import os

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler

from handlers.account import register_account_handlers
from handlers.music import register_music_handlers
from handlers.recommend import register_recommend_handlers
from handlers.message_handler import register_message_handler
from language_guard import register_language_guard_handlers
from webserver import run_webserver_async
from db.database import init_db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file.")


async def start_command(update, context):
    await update.message.reply_text(
        "Welcome to Little AI!\n\nUse /account to log in to Spotify or /music to open the music menu."
    )


async def help_command(update, context):
    await update.message.reply_text(
        "Help:\n"
        "/account - Manage your Spotify account\n"
        "/music - Music menu\n"
        "/recommend [genre] - Get track recommendations\n"
        "/category_playlists [id] - Playlists in a category\n\n"
        "You can also forward a track directly or type \"play\"."
    )


async def _on_startup(app):
    # Runs the webserver on the same event loop PTB v20+ manages.
    init_db()
    await run_webserver_async(app)


def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(_on_startup).build()

    register_account_handlers(app)
    register_music_handlers(app)
    register_recommend_handlers(app)
    register_message_handler(app)
    register_language_guard_handlers(app)

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
