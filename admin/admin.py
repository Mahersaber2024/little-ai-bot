from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from config import bot_settings
from db import database
from utils.logger import log_admin_action
from utils.permissions import add_admin, get_admin_ids, is_admin, is_owner_admin, remove_admin

# --------------------------------------------------------------------------
# Guard: block banned users everywhere, and passively record who talks to
# the bot. Registered on group=-1 (see register_admin_handlers below) so it
# runs before every other handler.
# --------------------------------------------------------------------------

async def guard_and_track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    database.record_user_seen(user.id, user.username, user.first_name, user.last_name)

    if database.is_banned(user.id):
        if update.callback_query:
            await update.callback_query.answer("You are banned from using this bot.", show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text("You are banned from using this bot.")
        raise ApplicationHandlerStop


# --------------------------------------------------------------------------
# Admin panel menu
# --------------------------------------------------------------------------

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("This command is for admins only.")
        return

    keyboard = [
        [InlineKeyboardButton("🚫 Ban User", callback_data='admin_ban')],
        [InlineKeyboardButton("✅ Unban User", callback_data='admin_unban')],
        [InlineKeyboardButton("📃 Banned List", callback_data='admin_banned_list')],
        [InlineKeyboardButton("📢 Sponsor Channels", callback_data='admin_sponsor_menu')],
        [InlineKeyboardButton("👤 Manage Admins", callback_data='admin_admins_menu')],
        [InlineKeyboardButton("🧾 Logging Settings", callback_data='admin_logging_menu')],
        [InlineKeyboardButton("🎵 Spotify Settings", callback_data='admin_spotify_menu')],
    ]
    text = "Admin panel:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


def _back_button(target: str = 'admin_menu') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data=target)]])


# --------------------------------------------------------------------------
# Ban / Unban / Banned list
# --------------------------------------------------------------------------

async def prompt_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_ban_target'] = True
    await query.edit_message_text(
        "Send the numeric Telegram user ID to ban, optionally followed by a reason.\n"
        "Example: <code>123456789 spamming</code>",
        parse_mode="HTML",
        reply_markup=_back_button(),
    )


async def prompt_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_unban_target'] = True
    await query.edit_message_text(
        "Send the numeric Telegram user ID to unban.",
        reply_markup=_back_button(),
    )


async def show_banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    banned = database.list_banned(limit=30)
    if not banned:
        text = "No banned users."
    else:
        lines = ["<b>Banned users:</b>"]
        for row in banned:
            reason = row.get('reason') or '-'
            lines.append(f"• <code>{row['telegram_user_id']}</code> — {reason}")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=_back_button())


async def handle_ban_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    context.user_data['awaiting_ban_target'] = False
    parts = text.split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        await update.message.reply_text("Invalid format. Send a numeric user ID, e.g.: 123456789 spamming")
        return

    target_id = int(parts[0])
    reason = parts[1] if len(parts) > 1 else None
    admin = update.effective_user

    if target_id == admin.id:
        await update.message.reply_text("You can't ban yourself.")
        return
    if is_admin(target_id):
        await update.message.reply_text("That user is an admin and can't be banned.")
        return

    database.ban_user(target_id, banned_by=admin.id, reason=reason)
    await update.message.reply_text(f"User {target_id} has been banned.")
    await log_admin_action(
        context.bot, admin, "Ban User",
        details=f"Target: {target_id}" + (f"\nReason: {reason}" if reason else ""),
    )


async def handle_unban_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    context.user_data['awaiting_unban_target'] = False
    text = text.strip()
    if not text.isdigit():
        await update.message.reply_text("Invalid format. Send a numeric user ID.")
        return

    target_id = int(text)
    admin = update.effective_user
    removed = database.unban_user(target_id)
    if removed:
        await update.message.reply_text(f"User {target_id} has been unbanned.")
        await log_admin_action(context.bot, admin, "Unban User", details=f"Target: {target_id}")
    else:
        await update.message.reply_text(f"User {target_id} was not banned.")


# --------------------------------------------------------------------------
# Sponsor channels
# --------------------------------------------------------------------------

async def sponsor_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    channels = bot_settings.get_sponsor_channels()
    required = bot_settings.is_membership_required()

    lines = ["<b>Sponsor Channels</b>", f"Force membership: {'ON' if required else 'OFF'}", ""]
    keyboard = []
    if channels:
        for i, ch in enumerate(channels):
            lines.append(f"{i + 1}. {ch.get('title') or ch['id']} (<code>{ch['id']}</code>)")
            keyboard.append([InlineKeyboardButton(f"❌ Remove #{i + 1}", callback_data=f'admin_sponsor_rm:{i}')])
    else:
        lines.append("No sponsor channels configured.")

    keyboard.append([InlineKeyboardButton("➕ Add Channel", callback_data='admin_sponsor_add')])
    keyboard.append([InlineKeyboardButton(
        f"{'🔕 Disable' if required else '🔔 Enable'} Force Membership",
        callback_data='admin_sponsor_toggle',
    )])
    keyboard.append([InlineKeyboardButton("⬅ Back", callback_data='admin_menu')])

    await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def prompt_sponsor_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_sponsor_add'] = True
    await query.edit_message_text(
        "Send the channel ID or @username to add as a sponsor channel, "
        "optionally followed by a display title.\n"
        "Example: <code>@mychannel My Channel</code>",
        parse_mode="HTML",
        reply_markup=_back_button('admin_sponsor_menu'),
    )


async def handle_sponsor_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    context.user_data['awaiting_sponsor_add'] = False
    parts = text.strip().split(maxsplit=1)
    if not parts:
        await update.message.reply_text("Invalid format.")
        return

    channel_id = parts[0]
    title = parts[1] if len(parts) > 1 else ""
    channel = bot_settings.add_sponsor_channel(channel_id, title=title)
    await update.message.reply_text(f"Sponsor channel added: {channel['title']} ({channel['id']})")
    await log_admin_action(context.bot, update.effective_user, "Add Sponsor Channel", details=str(channel))


async def sponsor_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    index = int(query.data.split(':')[1])
    channels = bot_settings.get_sponsor_channels()
    removed_channel = channels[index] if 0 <= index < len(channels) else None

    if bot_settings.remove_sponsor_channel(index):
        await query.answer("Removed.")
        await log_admin_action(
            context.bot, update.effective_user, "Remove Sponsor Channel", details=str(removed_channel),
        )
    else:
        await query.answer("Not found.")
    await sponsor_menu(update, context)


async def sponsor_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    new_value = not bot_settings.is_membership_required()
    bot_settings.set_membership_required(new_value)
    await query.answer("Updated.")
    await log_admin_action(
        context.bot, update.effective_user, "Toggle Force Membership", details=f"Now: {new_value}",
    )
    await sponsor_menu(update, context)


# --------------------------------------------------------------------------
# Manage admins
# --------------------------------------------------------------------------

async def admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    ids = get_admin_ids()
    lines = ["<b>Admins</b>", ""]
    for admin_id in ids:
        tag = " (owner, from .env)" if is_owner_admin(admin_id) else ""
        lines.append(f"• <code>{admin_id}</code>{tag}")

    keyboard = [
        [InlineKeyboardButton("➕ Add Admin", callback_data='admin_admins_add')],
        [InlineKeyboardButton("➖ Remove Admin", callback_data='admin_admins_remove')],
        [InlineKeyboardButton("⬅ Back", callback_data='admin_menu')],
    ]
    await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def prompt_admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_admin_add'] = True
    await query.edit_message_text(
        "Send the numeric Telegram user ID to make an admin.",
        reply_markup=_back_button('admin_admins_menu'),
    )


async def prompt_admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_admin_remove'] = True
    await query.edit_message_text(
        "Send the numeric Telegram user ID to remove from admins.\n"
        "(Owner admins seeded from .env can't be removed this way.)",
        reply_markup=_back_button('admin_admins_menu'),
    )


async def handle_admin_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    context.user_data['awaiting_admin_add'] = False
    text = text.strip()
    if not text.isdigit():
        await update.message.reply_text("Invalid format. Send a numeric user ID.")
        return
    target_id = int(text)
    if add_admin(target_id):
        await update.message.reply_text(f"User {target_id} is now an admin.")
        await log_admin_action(context.bot, update.effective_user, "Add Admin", details=f"Target: {target_id}")
    else:
        await update.message.reply_text(f"User {target_id} is already an admin.")


async def handle_admin_remove_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    context.user_data['awaiting_admin_remove'] = False
    text = text.strip()
    if not text.isdigit():
        await update.message.reply_text("Invalid format. Send a numeric user ID.")
        return
    target_id = int(text)
    if is_owner_admin(target_id):
        await update.message.reply_text("That admin is seeded from .env and can't be removed here.")
        return
    if remove_admin(target_id):
        await update.message.reply_text(f"User {target_id} is no longer an admin.")
        await log_admin_action(context.bot, update.effective_user, "Remove Admin", details=f"Target: {target_id}")
    else:
        await update.message.reply_text(f"User {target_id} was not an admin.")


# --------------------------------------------------------------------------
# Logging settings
# --------------------------------------------------------------------------

async def logging_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    enabled = bot_settings.is_logging_enabled()
    group_id = bot_settings.get_log_group_id()

    lines = [
        "<b>Logging Settings</b>",
        f"Enabled: {'ON' if enabled else 'OFF'}",
        f"Log group: <code>{group_id}</code>" if group_id else "Log group: not set",
    ]
    keyboard = [
        [InlineKeyboardButton(f"{'🔕 Disable' if enabled else '🔔 Enable'} Logging", callback_data='admin_logging_toggle')],
        [InlineKeyboardButton("🗂 Set Log Group ID", callback_data='admin_logging_set_group')],
        [InlineKeyboardButton("⬅ Back", callback_data='admin_menu')],
    ]
    await query.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def logging_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    new_value = not bot_settings.is_logging_enabled()
    bot_settings.set_logging_enabled(new_value)
    await query.answer("Updated.")
    await logging_menu(update, context)


async def prompt_logging_set_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_log_group_id'] = True
    await query.edit_message_text(
        "Send the numeric chat ID of the group to use for admin-action logs.\n"
        "(Add the bot to that group first, then forward any message from it to "
        "@userinfobot or similar to find its ID.)",
        reply_markup=_back_button('admin_logging_menu'),
    )


async def handle_log_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    context.user_data['awaiting_log_group_id'] = False
    text = text.strip()
    try:
        group_id = int(text)
    except ValueError:
        await update.message.reply_text("Invalid format. Send a numeric chat ID (usually negative).")
        return
    bot_settings.set_log_group_id(group_id)
    await update.message.reply_text(f"Log group set to {group_id}.")
    await log_admin_action(context.bot, update.effective_user, "Set Log Group", details=str(group_id))


# --------------------------------------------------------------------------
# Spotify app settings (client ID / secret / redirect URI)
# --------------------------------------------------------------------------

def _mask(value: str) -> str:
    if not value:
        return "not set"
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-4:]}"


async def spotify_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    client_id = bot_settings.get_spotify_client_id()
    client_secret = bot_settings.get_spotify_client_secret()
    redirect_uri = bot_settings.get_spotify_redirect_uri()

    lines = [
        "<b>Spotify Settings</b>",
        "These are the app credentials from your Spotify Developer Dashboard "
        "(https://developer.spotify.com/dashboard). They're shared by every "
        "admin who logs in via /account.",
        "",
        f"Client ID: <code>{_mask(client_id)}</code>",
        f"Client Secret: <code>{_mask(client_secret)}</code>",
        f"Redirect URI: <code>{redirect_uri}</code>",
        "",
        "Make sure this exact Redirect URI is added under your Spotify app's "
        "settings, or logins will fail.",
    ]
    keyboard = [
        [InlineKeyboardButton("Set Client ID", callback_data='admin_spotify_set_id')],
        [InlineKeyboardButton("Set Client Secret", callback_data='admin_spotify_set_secret')],
        [InlineKeyboardButton("Set Redirect URI", callback_data='admin_spotify_set_uri')],
        [InlineKeyboardButton("⬅ Back", callback_data='admin_menu')],
    ]
    await query.edit_message_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True,
    )


async def prompt_spotify_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    field = query.data.split('admin_spotify_set_')[-1]  # 'id' | 'secret' | 'uri'
    flag_map = {
        'id': ('awaiting_spotify_client_id', "Send the Spotify Client ID."),
        'secret': ('awaiting_spotify_client_secret', "Send the Spotify Client Secret."),
        'uri': ('awaiting_spotify_redirect_uri', "Send the Redirect URI (must match the Spotify dashboard exactly)."),
    }
    flag, prompt_text = flag_map[field]
    context.user_data[flag] = True
    await query.edit_message_text(prompt_text, reply_markup=_back_button('admin_spotify_menu'))


async def handle_spotify_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, flag: str) -> None:
    context.user_data[flag] = False
    text = text.strip()
    if not text:
        await update.message.reply_text("Empty value ignored.")
        return

    if flag == 'awaiting_spotify_client_id':
        bot_settings.set_spotify_credentials(client_id=text)
        await update.message.reply_text("Spotify Client ID updated.")
        await log_admin_action(context.bot, update.effective_user, "Set Spotify Client ID")
    elif flag == 'awaiting_spotify_client_secret':
        bot_settings.set_spotify_credentials(client_secret=text)
        await update.message.reply_text("Spotify Client Secret updated.")
        await log_admin_action(context.bot, update.effective_user, "Set Spotify Client Secret")
    elif flag == 'awaiting_spotify_redirect_uri':
        bot_settings.set_spotify_credentials(redirect_uri=text)
        await update.message.reply_text("Spotify Redirect URI updated.")
        await log_admin_action(context.bot, update.effective_user, "Set Spotify Redirect URI", details=text)


# --------------------------------------------------------------------------
# Text-flow dispatcher — called from handlers/message_handler.py for any
# plain-text reply an admin sends while one of the awaiting_* flags above
# is set. Returns True if it handled the message.
# --------------------------------------------------------------------------

_TEXT_FLOWS = {
    'awaiting_ban_target': handle_ban_text,
    'awaiting_unban_target': handle_unban_text,
    'awaiting_sponsor_add': handle_sponsor_add_text,
    'awaiting_admin_add': handle_admin_add_text,
    'awaiting_admin_remove': handle_admin_remove_text,
    'awaiting_log_group_id': handle_log_group_text,
}
_SPOTIFY_TEXT_FLAGS = (
    'awaiting_spotify_client_id',
    'awaiting_spotify_client_secret',
    'awaiting_spotify_redirect_uri',
)


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    text = update.message.text.strip()

    for flag, handler in _TEXT_FLOWS.items():
        if context.user_data.get(flag):
            await handler(update, context, text)
            return True

    for flag in _SPOTIFY_TEXT_FLAGS:
        if context.user_data.get(flag):
            await handle_spotify_text(update, context, text, flag)
            return True

    return False


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

def register_admin_handlers(app: Application) -> None:
    app.add_handler(TypeHandler(Update, guard_and_track), group=-1)

    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(CallbackQueryHandler(admin_panel, pattern=r"^admin_menu$"))
    app.add_handler(CallbackQueryHandler(prompt_ban, pattern=r"^admin_ban$"))
    app.add_handler(CallbackQueryHandler(prompt_unban, pattern=r"^admin_unban$"))
    app.add_handler(CallbackQueryHandler(show_banned_list, pattern=r"^admin_banned_list$"))

    app.add_handler(CallbackQueryHandler(sponsor_menu, pattern=r"^admin_sponsor_menu$"))
    app.add_handler(CallbackQueryHandler(prompt_sponsor_add, pattern=r"^admin_sponsor_add$"))
    app.add_handler(CallbackQueryHandler(sponsor_remove, pattern=r"^admin_sponsor_rm:"))
    app.add_handler(CallbackQueryHandler(sponsor_toggle, pattern=r"^admin_sponsor_toggle$"))

    app.add_handler(CallbackQueryHandler(admins_menu, pattern=r"^admin_admins_menu$"))
    app.add_handler(CallbackQueryHandler(prompt_admin_add, pattern=r"^admin_admins_add$"))
    app.add_handler(CallbackQueryHandler(prompt_admin_remove, pattern=r"^admin_admins_remove$"))

    app.add_handler(CallbackQueryHandler(logging_menu, pattern=r"^admin_logging_menu$"))
    app.add_handler(CallbackQueryHandler(logging_toggle, pattern=r"^admin_logging_toggle$"))
    app.add_handler(CallbackQueryHandler(prompt_logging_set_group, pattern=r"^admin_logging_set_group$"))

    app.add_handler(CallbackQueryHandler(spotify_menu, pattern=r"^admin_spotify_menu$"))
    app.add_handler(CallbackQueryHandler(prompt_spotify_set, pattern=r"^admin_spotify_set_"))
