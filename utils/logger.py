"""utils/logger.py

Sends admin-action log messages (bans, sponsor-channel changes, etc.) to
the log group configured in bot_settings, if logging is enabled.

This is a plain, single-channel logger (no forum topics) — much simpler
than a full multi-topic setup, since this bot only needs a lightweight
audit trail.
"""
import logging
from datetime import datetime

from telegram.constants import ParseMode

from config import bot_settings

logger = logging.getLogger(__name__)


def _format_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> str:
    name = f"{(first_name or '').strip()} {(last_name or '').strip()}".strip() or "Unknown"
    username_text = f"@{username}" if username else "-"
    return f"Name: {name}\nUsername: {username_text}\nID: {user_id}"


async def log_admin_action(bot, admin_user, action: str, details: str = None) -> None:
    """Post an admin-action entry to the log group, if configured/enabled.

    admin_user is a telegram.User (e.g. update.effective_user).
    Silently does nothing if logging is off or no log group is set, and
    never raises — a broken log group shouldn't break the admin action
    that triggered it.
    """
    if not bot_settings.is_logging_enabled():
        return

    group_id = bot_settings.get_log_group_id()
    if not group_id:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin_info = _format_user(admin_user.id, admin_user.username, admin_user.first_name, admin_user.last_name)

    lines = [
        "<b>Admin Action</b>",
        f"Time: <code>{timestamp}</code>",
        "\u2500" * 17,
        admin_info,
        "\u2500" * 17,
        f"Action: <b>{action}</b>",
    ]
    if details:
        lines.append(f"Details: {details}")

    try:
        await bot.send_message(chat_id=group_id, text="\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception:
        logger.exception("Failed to send admin log message")
