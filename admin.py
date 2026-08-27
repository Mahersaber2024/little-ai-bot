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
# the bot. Registered on group=-1 in main.py so it runs before every other
# handler.
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
