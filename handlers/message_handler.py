from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from utils.auth import get_spotify_client
from handlers.music import handle_track_search, handle_album_search, handle_artist_search


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get('awaiting_search_track'):
        context.user_data['awaiting_search_track'] = False
        await handle_track_search(update, context, text)
        return

    if context.user_data.get('awaiting_search_album'):
        context.user_data['awaiting_search_album'] = False
        await handle_album_search(update, context, text)
        return

    if context.user_data.get('awaiting_search_artist'):
        context.user_data['awaiting_search_artist'] = False
        await handle_artist_search(update, context, text)
        return

    if context.user_data.get('awaiting_new_playlist_name'):
        sp = get_spotify_client(user_id)
        if not sp:
            await update.message.reply_text("You need to log in first. Run /account.")
            return
        new_pl = sp.user_playlist_create(user=sp.current_user()['id'], name=text, public=False)
        await update.message.reply_text(f"Playlist '{text}' created. ID: {new_pl['id']}")
        context.user_data['awaiting_new_playlist_name'] = False

    elif context.user_data.get('awaiting_like_track_url'):
        sp = get_spotify_client(user_id)
        if not sp:
            await update.message.reply_text("You need to log in first. Run /account.")
            return
        try:
            track_id = text.split("track/")[-1].split("?")[0]
            sp.current_user_saved_tracks_add([track_id])
            await update.message.reply_text("Track added to your liked songs.")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
        context.user_data['awaiting_like_track_url'] = False

    elif context.user_data.get('awaiting_add_track'):
        sp = get_spotify_client(user_id)
        if not sp:
            await update.message.reply_text("You need to log in first. Run /account.")
            return
        try:
            parts = text.split()
            if len(parts) != 2:
                raise ValueError("Invalid format. Provide two values: track link and playlist ID")
            track_url, playlist_id = parts
            track_id = track_url.split("track/")[-1].split("?")[0]
            sp.playlist_add_items(playlist_id, [track_id])
            await update.message.reply_text("Track added to the playlist.")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
        context.user_data['awaiting_add_track'] = False


def register_message_handler(app):
    # group=1: runs independently from language_guard handlers (group=0)
    # so typing "play" doesn't conflict.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler), group=1)
