from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from utils.auth import get_spotify_client, ensure_token


async def recommend_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    token_info = await ensure_token(update, context, user_id)
    if not token_info:
        return

    keyboard = [
        [InlineKeyboardButton("Recommend by Genre", callback_data='recommend_genre')],
        [InlineKeyboardButton("Featured Playlists", callback_data='recommend_featured_playlists')],
        [InlineKeyboardButton("New Releases", callback_data='recommend_new_releases')],
        [InlineKeyboardButton("Categories", callback_data='recommend_categories')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Recommendations menu:", reply_markup=reply_markup)


async def recommend_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    sp = get_spotify_client(user_id)
    if not sp:
        await query.edit_message_text("Please log in first with /account.")
        return

    if data == 'recommend_genre':
        genres = sp.recommendation_genre_seeds()
        msg = "Available genres:\n" + ", ".join(genres['genres'])
        msg += "\n\nGet a recommendation with:\n/recommend [genre]"
        await query.edit_message_text(msg)

    elif data == 'recommend_featured_playlists':
        featured = sp.featured_playlists(limit=5)
        msg = "Featured playlists:\n"
        for pl in featured['playlists']['items']:
            msg += f"- {pl['name']}\n  Link: {pl['external_urls']['spotify']}\n"
        await query.edit_message_text(msg)

    elif data == 'recommend_new_releases':
        new_releases = sp.new_releases(country='US', limit=5)
        msg = "New releases:\n"
        for album in new_releases['albums']['items']:
            msg += f"- {album['name']} by {album['artists'][0]['name']}\n  Link: {album['external_urls']['spotify']}\n"
        await query.edit_message_text(msg)

    elif data == 'recommend_categories':
        categories = sp.categories(limit=10)
        msg = "Categories:\n"
        for cat in categories['categories']['items']:
            msg += f"- {cat['name']} (id: {cat['id']})\n"
        msg += "\nSee a category's playlists with:\n/category_playlists [category_id]"
        await query.edit_message_text(msg)

    else:
        await query.edit_message_text("Invalid option.")


async def recommend_genre_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    genre = " ".join(context.args).lower()

    sp = get_spotify_client(user_id)
    if not sp:
        await update.message.reply_text("You need to log in first. Run /account.")
        return

    if not genre:
        await update.message.reply_text("Please provide a genre.")
        return

    genres_available = sp.recommendation_genre_seeds()['genres']
    if genre not in genres_available:
        await update.message.reply_text(f"That genre isn't available. Valid genres:\n{', '.join(genres_available)}")
        return

    recs = sp.recommendations(seed_genres=[genre], limit=5)
    msg = f"Recommendations for {genre}:\n"
    for t in recs['tracks']:
        msg += f"- {t['name']} - {t['artists'][0]['name']}\n"
    await update.message.reply_text(msg)


async def category_playlists_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    category_id = context.args[0] if context.args else None

    sp = get_spotify_client(user_id)
    if not sp:
        await update.message.reply_text("You need to log in first. Run /account.")
        return

    if not category_id:
        await update.message.reply_text("Please provide a category ID, e.g.: /category_playlists pop")
        return

    try:
        playlists = sp.category_playlists(category_id, limit=5)
        msg = f"Playlists in category {category_id}:\n"
        for pl in playlists['playlists']['items']:
            msg += f"- {pl['name']}\n  Link: {pl['external_urls']['spotify']}\n"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Error fetching playlists:\n{e}")


def register_recommend_handlers(app):
    app.add_handler(CommandHandler("recommend", recommend_genre_command))
    app.add_handler(CommandHandler("category_playlists", category_playlists_command))
    app.add_handler(CallbackQueryHandler(recommend_button_handler, pattern=r"^recommend_"))
