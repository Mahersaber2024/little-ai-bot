from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import spotipy
from utils.auth import get_spotify_client, ensure_token


async def music_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Search Track", callback_data='music_search_track')],
        [InlineKeyboardButton("Search Album", callback_data='music_search_album')],
        [InlineKeyboardButton("Search Artist", callback_data='music_search_artist')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text("Music menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Music menu:", reply_markup=reply_markup)


async def music_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    prompts = {
        'music_search_track': ("Send the track name:", 'awaiting_search_track'),
        'music_search_album': ("Send the album name:", 'awaiting_search_album'),
        'music_search_artist': ("Send the artist name:", 'awaiting_search_artist'),
    }

    if data in prompts:
        text, flag = prompts[data]
        await query.edit_message_text(text)
        context.user_data[flag] = True
    else:
        await query.edit_message_text("Invalid option.")


async def handle_track_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str):
    user_id = update.effective_user.id
    token_info = await ensure_token(update, context, user_id)
    if not token_info:
        return
    sp = get_spotify_client(user_id)

    results = sp.search(q=query_text, type='track', limit=5)
    tracks = results['tracks']['items']
    if not tracks:
        await update.message.reply_text("No results found.")
        return

    msg = "Search results:\n"
    for t in tracks:
        msg += f"- {t['name']} by {t['artists'][0]['name']}\n  {t['external_urls']['spotify']}\n"
    await update.message.reply_text(msg)


async def handle_album_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str):
    user_id = update.effective_user.id
    token_info = await ensure_token(update, context, user_id)
    if not token_info:
        return
    sp = get_spotify_client(user_id)

    results = sp.search(q=query_text, type='album', limit=5)
    albums = results['albums']['items']
    if not albums:
        await update.message.reply_text("No results found.")
        return

    msg = "Search results:\n"
    for a in albums:
        msg += f"- {a['name']} by {a['artists'][0]['name']}\n  {a['external_urls']['spotify']}\n"
    await update.message.reply_text(msg)


async def handle_artist_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str):
    user_id = update.effective_user.id
    token_info = await ensure_token(update, context, user_id)
    if not token_info:
        return
    sp = get_spotify_client(user_id)

    results = sp.search(q=query_text, type='artist', limit=5)
    artists = results['artists']['items']
    if not artists:
        await update.message.reply_text("No results found.")
        return

    msg = "Search results:\n"
    for a in artists:
        followers = a.get('followers', {}).get('total', 0)
        msg += f"- {a['name']} ({followers} followers)\n  {a['external_urls']['spotify']}\n"
    await update.message.reply_text(msg)


def register_music_handlers(app):
    app.add_handler(CommandHandler("music", music_menu))
    app.add_handler(CallbackQueryHandler(music_button_handler, pattern=r"^music_search_"))
