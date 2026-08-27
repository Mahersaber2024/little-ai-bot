"""
language_guard.py
------------------
"""

import random
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from handlers.music import music_menu

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

PERSIAN_TEASE_LINES = [
    "This bot does not play Persian tracks. Please send something else.",
    "Persian music is not supported here. Try a different track.",
    "That track appears to be in Persian, so it will not be played.",
    "Sorry, Persian songs are off-limits on this bot.",
]

# Any character in the Arabic/Persian Unicode block.
PERSIAN_SCRIPT_PATTERN = re.compile(r"[\u0600-\u06FF]")


def looks_persian(*text_fields: str) -> bool:
    """Heuristic: does any given metadata field contain Persian/Arabic script?"""
    combined = " ".join(field for field in text_fields if field)
    return bool(PERSIAN_SCRIPT_PATTERN.search(combined))


def build_play_button(track_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Play", callback_data=f"confirm_play:{track_key}")]]
    )


# --------------------------------------------------------------------------
# "play" text trigger
# --------------------------------------------------------------------------

async def play_text_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fires when a user simply types 'play' (case-insensitive)."""
    await music_menu(update, context)


# --------------------------------------------------------------------------
# Incoming audio (sent or forwarded)
# --------------------------------------------------------------------------

async def handle_incoming_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs whenever a user sends or forwards an audio file to the bot/chat."""
    message = update.effective_message
    is_audio_doc = (
        message.document
        and message.document.mime_type
        and "audio" in message.document.mime_type
    )
    audio = message.audio or (message.document if is_audio_doc else None)

    if audio is None:
        return

    title = getattr(audio, "title", "") or ""
    performer = getattr(audio, "performer", "") or ""
    file_name = getattr(audio, "file_name", "") or ""

    if looks_persian(title, performer, file_name):
        await message.reply_text(random.choice(PERSIAN_TEASE_LINES))
        return

    display_name = title or file_name or "Track"
    await message.reply_text(
        f"<b>Now Playing:</b> {display_name}",
        parse_mode=ParseMode.HTML,
        reply_markup=build_play_button("incoming"),
    )


async def handle_play_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles taps on the Play button shown under a track."""
    query = update.callback_query
    await query.answer(text="Playing")
    try:
        await query.edit_message_text(
            text=f"{query.message.text}\n\nNow playing.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        # Safe to ignore if the text is unchanged or message has no text body.
        pass


# --------------------------------------------------------------------------
# Auto-greeting when the bot is added to a new chat/group
# --------------------------------------------------------------------------

async def on_bot_added_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = update.my_chat_member
    if result is None:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    joined_statuses = {"member", "administrator"}
    left_statuses = {"left", "kicked"}

    if old_status in left_statuses and new_status in joined_statuses:
        chat_id = result.chat.id
        text = (
            "<b>Little AI has joined this chat.</b>\n\n"
            "Send or forward a music file here and it will be played.\n"
            "Type <b>play</b> to open the track menu."
        )
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

def register_language_guard_handlers(app: Application) -> None:
    """Call this once from main.py, after building the Application, to wire
    up all the handlers defined in this module."""

    # "play" typed as plain text opens the music menu
    app.add_handler(
        MessageHandler(filters.Regex(re.compile(r"^play$", re.IGNORECASE)), play_text_trigger)
    )

    # Forwarded or directly sent audio files
    app.add_handler(
        MessageHandler((filters.AUDIO | filters.Document.ALL) & ~filters.COMMAND, handle_incoming_audio)
    )

    app.add_handler(CallbackQueryHandler(handle_play_confirmation, pattern=r"^confirm_play:"))

    # Detect the bot being added to a group/chat
    app.add_handler(ChatMemberHandler(on_bot_added_to_chat, ChatMemberHandler.MY_CHAT_MEMBER))
