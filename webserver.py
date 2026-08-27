import logging

from aiohttp import web
from spotipy.oauth2 import SpotifyOAuth

from config import bot_settings
from db import database
from utils.auth import SCOPE

logger = logging.getLogger(__name__)


async def handle_callback(request: web.Request) -> web.Response:
    code = request.query.get("code")
    state = request.query.get("state")
    error = request.query.get("error")

    if error:
        return web.Response(text=f"Login cancelled: {error}", content_type="text/plain")

    if not code or not state:
        return web.Response(status=400, text="Missing required parameters.")

    user_id = database.pop_oauth_state(state)
    if user_id is None:
        return web.Response(status=400, text="This link is invalid or has expired.")

    oauth = SpotifyOAuth(
        client_id=bot_settings.get_spotify_client_id(),
        client_secret=bot_settings.get_spotify_client_secret(),
        redirect_uri=bot_settings.get_spotify_redirect_uri(),
        scope=SCOPE,
        cache_path=None,
    )

    try:
        token_info = oauth.get_access_token(code, as_dict=True, check_cache=False)
    except Exception as exc:
        logger.exception("Spotify token exchange failed")
        return web.Response(status=500, text=f"Error retrieving token: {exc}")

    database.save_token(user_id, token_info)

    bot_app = request.app.get("telegram_app")
    if bot_app is not None:
        try:
            await bot_app.bot.send_message(
                chat_id=user_id,
                text="You've successfully logged in to Spotify! You can now use /account.",
            )
        except Exception:
            logger.exception("Could not notify user %s after login", user_id)

    return web.Response(
        text="Login successful. You can close this page and return to Telegram.",
        content_type="text/plain",
    )


def build_app(telegram_app) -> web.Application:
    app = web.Application()
    app["telegram_app"] = telegram_app
    app.router.add_get("/callback", handle_callback)
    return app


async def run_webserver_async(telegram_app, host: str = "0.0.0.0", port: int = 8888) -> None:
    # Runs on the bot's main event loop (PTB v20+).
    app = build_app(telegram_app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Webserver listening on %s:%s", host, port)
