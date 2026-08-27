import sys

from telegram.ext import ApplicationBuilder, CommandHandler

from config import bot_settings
from handlers.account import register_account_handlers
from admin.admin import register_admin_handlers
from handlers.music import register_music_handlers
from handlers.recommend import register_recommend_handlers
from handlers.message_handler import register_message_handler
from language_guard import register_language_guard_handlers
from webserver import run_webserver_async
from db.database import init_db

# There is no .env file anywhere in this project. Every setting the bot
# needs (DB credentials, admin IDs, bot token, Spotify creds, ...) lives
# in config/bot_settings.json, written by install.sh and editable from
# /admin — see config/bot_settings.py for details.


def _resolve_bot_token() -> str:
    token = bot_settings.get_bot_token()
    if token:
        return token

    if sys.stdin.isatty():
        print("No BOT_TOKEN configured yet.")
        token = input("Enter your Telegram bot token (from @BotFather): ").strip()
        if token:
            bot_settings.set_bot_token(token)
            return token

    raise ValueError(
        "No bot token configured. Run this once interactively to set it "
        "(`python little_ai.py`), or set it directly with:\n"
        "  python -c \"from config import bot_settings; "
        "bot_settings.set_bot_token('YOUR_TOKEN')\""
    )


BOT_TOKEN = _resolve_bot_token()


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

    register_admin_handlers(app)
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
