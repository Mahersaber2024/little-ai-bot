import os
import time
import uuid

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import database
from utils.permissions import get_admin_ids, is_admin

SPOTIFY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")

SCOPE = (
    "user-read-email user-read-private "
    "playlist-read-private playlist-modify-private playlist-modify-public "
    "user-library-read user-library-modify "
    "user-top-read "
    "user-read-playback-state user-modify-playback-state user-read-currently-playing"
)


def _make_oauth() -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=None,
    )


def build_login_keyboard(user_id: int) -> InlineKeyboardMarkup:
    state = str(uuid.uuid4())
    database.save_oauth_state(state, user_id)
    auth_url = _make_oauth().get_authorize_url(state=state)
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Log in with Spotify", url=auth_url)]]
    )


def _refresh_if_needed(token_info: dict, owner_id: int) -> dict | None:
    """Refresh token_info if it's about to expire, saving it back under
    owner_id. Returns None if the refresh fails."""
    if token_info["expires_at"] - int(time.time()) < 60:
        oauth = _make_oauth()
        try:
            token_info = oauth.refresh_access_token(token_info["refresh_token"])
        except Exception:
            return None
        database.save_token(owner_id, token_info)
    return token_info


def get_spotify_client(user_id: int) -> spotipy.Spotify | None:
    """Everyone shares the Spotify account linked by an admin.

    Admins and regular users both resolve to the same underlying account:
    whichever admin has completed the OAuth login. Only admins can trigger
    that login (see ensure_token) — regular users never see a login flow."""
    owner_id, token_info = database.get_admin_token(ADMIN_USER_IDS)
    if not token_info:
        return None

    token_info = _refresh_if_needed(token_info, owner_id)
    if not token_info:
        return None

    return spotipy.Spotify(auth=token_info["access_token"])


async def ensure_token(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    via_query: bool = False,
) -> dict | None:
    """Admins: log in with their own Spotify account if not already linked
    (shows the login button). Regular users: silently reuse whichever
    admin account is linked; if none is linked yet, they're told to wait —
    they are never shown a login button themselves."""

    if is_admin(user_id):
        token_info = database.get_token(user_id)
        if token_info:
            token_info = _refresh_if_needed(token_info, user_id)

        if not token_info:
            keyboard = build_login_keyboard(user_id)
            text = "You need to log in to your Spotify account to use this feature:"
            if via_query:
                await update.callback_query.edit_message_text(text, reply_markup=keyboard)
            else:
                await update.message.reply_text(text, reply_markup=keyboard)
            return None

        return token_info

    # Regular user: piggyback on whichever admin is linked. No login flow
    # is ever offered to them.
    owner_id, token_info = database.get_admin_token(ADMIN_USER_IDS)
    if token_info:
        token_info = _refresh_if_needed(token_info, owner_id)

    if not token_info:
        text = "This bot isn't linked to a Spotify account yet. Ask the admin to log in first."
        if via_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return None

    return token_info
