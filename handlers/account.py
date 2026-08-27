from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import spotipy
from utils.auth import ensure_token


async def account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    token_info = await ensure_token(update, context, user_id)
    if not token_info:
        return

    keyboard = [
        [InlineKeyboardButton("My Profile", callback_data='account_profile')],
        [InlineKeyboardButton("My Playlists", callback_data='account_playlists')],
        [InlineKeyboardButton("Create Playlist", callback_data='account_create_playlist')],
        [InlineKeyboardButton("Add Track", callback_data='account_add_track')],
        [InlineKeyboardButton("Like Track", callback_data='account_like_track')],
        [InlineKeyboardButton("My Top Tracks", callback_data='account_top_tracks')],
        [InlineKeyboardButton("Playback Control", callback_data='account_playback_control')],
        [InlineKeyboardButton("Now Playing", callback_data='account_currently_playing')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Account menu:", reply_markup=reply_markup)


async def account_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    token_info = await ensure_token(update, context, user_id, via_query=True)
    if not token_info:
        return

    sp = spotipy.Spotify(auth=token_info['access_token'])
    data = query.data

    if data == 'account_profile':
        profile = sp.current_user()
        msg = f"Name: {profile['display_name']}\nEmail: {profile.get('email', '-')}\nID: {profile['id']}"
        await query.edit_message_text(msg)

    elif data == 'account_playlists':
        pls = sp.current_user_playlists(limit=10)
        msg = "Your playlists:\n"
        for pl in pls['items']:
            msg += f"- {pl['name']} ({pl['tracks']['total']} tracks) — id: {pl['id']}\n"
        await query.edit_message_text(msg or "No playlists found.")

    elif data == 'account_create_playlist':
        await query.edit_message_text("Please send the name of the new playlist.")
        context.user_data['awaiting_new_playlist_name'] = True

    elif data == 'account_like_track':
        await query.edit_message_text("Please send the link of the track to like.")
        context.user_data['awaiting_like_track_url'] = True

    elif data == 'account_add_track':
        await query.edit_message_text("Please send the track link and playlist ID (e.g.: <url> <playlist_id>)")
        context.user_data['awaiting_add_track'] = True

    elif data == 'account_top_tracks':
        top_tracks = sp.current_user_top_tracks(limit=5)
        msg = "Your top tracks:\n"
        for t in top_tracks['items']:
            msg += f"- {t['name']} by {t['artists'][0]['name']}\n"
        await query.edit_message_text(msg or "Nothing found.")

    elif data == 'account_playback_control':
        keyboard = [
            [InlineKeyboardButton("Play/Pause", callback_data='playback_toggle')],
            [InlineKeyboardButton("Next", callback_data='playback_next')],
            [InlineKeyboardButton("Previous", callback_data='playback_previous')],
            [InlineKeyboardButton("Volume Down", callback_data='volume_down')],
            [InlineKeyboardButton("Volume Up", callback_data='volume_up')],
        ]
        await query.edit_message_text("Playback control:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'account_currently_playing':
        current = sp.current_user_playing_track()
        if current and current['item']:
            track = current['item']
            msg = f"Now playing:\n{track['name']} by {track['artists'][0]['name']}"
        else:
            msg = "Nothing is currently playing."
        await query.edit_message_text(msg)

    elif data == 'playback_toggle':
        try:
            playback = sp.current_playback()
            if playback and playback['is_playing']:
                sp.pause_playback()
                await query.edit_message_text("Playback paused.")
            else:
                sp.start_playback()
                await query.edit_message_text("Playback started.")
        except spotipy.exceptions.SpotifyException as e:
            await query.edit_message_text(f"Error: {e}")

    elif data == 'playback_next':
        try:
            sp.next_track()
            await query.edit_message_text("Skipping to next track.")
        except spotipy.exceptions.SpotifyException as e:
            await query.edit_message_text(f"Error: {e}")

    elif data == 'playback_previous':
        try:
            sp.previous_track()
            await query.edit_message_text("Playing previous track.")
        except spotipy.exceptions.SpotifyException as e:
            await query.edit_message_text(f"Error: {e}")

    elif data == 'volume_down':
        playback = sp.current_playback()
        if playback:
            vol = playback.get('device', {}).get('volume_percent', 50)
            new_vol = max(0, vol - 10)
            sp.volume(new_vol)
            await query.edit_message_text(f"Volume decreased to {new_vol}%.")
        else:
            await query.edit_message_text("No active device.")

    elif data == 'volume_up':
        playback = sp.current_playback()
        if playback:
            vol = playback.get('device', {}).get('volume_percent', 50)
            new_vol = min(100, vol + 10)
            sp.volume(new_vol)
            await query.edit_message_text(f"Volume increased to {new_vol}%.")
        else:
            await query.edit_message_text("No active device.")

    else:
        await query.edit_message_text("Invalid option.")


def register_account_handlers(app):
    app.add_handler(CommandHandler("account", account))
    app.add_handler(CallbackQueryHandler(account_button_handler, pattern=r"^(account_|playback_|volume_)"))
