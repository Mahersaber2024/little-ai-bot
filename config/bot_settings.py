"""config/bot_settings.py

There is no .env file anywhere in this project. Every setting the bot
needs — database credentials, owner/dynamic admin IDs, the bot token,
Spotify app credentials, and everything else changeable from /admin —
lives in this single JSON file (bot_settings.json, chmod 600), so it
persists across restarts and across re-running install.sh.

install.sh writes the initial values here directly (DB credentials,
owner admin IDs, bot token) by calling into this module. After that:
  - Spotify credentials and DB credentials are fully self-service — set
    or changed any time from /admin, no restart needed.
  - BOT_TOKEN can't be self-service (the bot needs it just to start),
    but living here means it's asked for once, at first run, and is
    never silently overwritten by re-running install.sh later.
  - owner_admin_ids is seeded once at install time and is not editable
    from inside the bot (see utils/permissions.py::is_owner_admin) —
    it's the fallback so the bot never ends up with no admin at all.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_settings.json")

_cache: Optional[dict] = None


def _get_default_settings() -> dict:
    return {
        "admin_ids": [],
        "owner_admin_ids": [],
        "bot_name": "Little AI",
        "log_group_id": None,
        "logging_enabled": False,
        "sponsor_channels": [],
        "membership_required": False,
        "installed_at": "",
        # Secrets below live here (bot_settings.json, chmod 600) so they
        # survive re-running install.sh and can be changed by an admin
        # from inside the bot (DB/Spotify creds) without redeploying.
        # bot_token can't be self-service (the bot needs it just to start),
        # but keeping it here means it's only ever entered once, at
        # install/first-run time, and never overwritten by a later install.
        "bot_token": "",
        "db_host": "localhost",
        "db_port": "5432",
        "db_name": "",
        "db_user": "",
        "db_password": "",
        "spotify_client_id": "",
        "spotify_client_secret": "",
        "spotify_redirect_uri": "http://localhost:8888/callback",
    }


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    data = None
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            data = None

    if data is None:
        data = _get_default_settings()

    defaults = _get_default_settings()
    for key, value in defaults.items():
        if key not in data:
            data[key] = value

    _cache = data
    return data


def _save(data: dict) -> None:
    global _cache
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.chmod(SETTINGS_FILE, 0o600)
        _cache = data
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise


def reload_settings() -> dict:
    global _cache
    _cache = None
    return _load()


# ------------------------------------------------------------------
# Admins
# ------------------------------------------------------------------

def get_admin_ids() -> List[int]:
    return list(_load().get("admin_ids", []))


def set_admin_ids(admin_ids: List[int]) -> None:
    data = _load()
    data["admin_ids"] = [int(x) for x in admin_ids if x]
    _save(data)


def add_admin_id(admin_id: int) -> bool:
    data = _load()
    ids = data.get("admin_ids", [])
    if admin_id not in ids:
        ids.append(int(admin_id))
        data["admin_ids"] = ids
        _save(data)
        return True
    return False


def remove_admin_id(admin_id: int) -> bool:
    data = _load()
    ids = data.get("admin_ids", [])
    if admin_id in ids:
        ids.remove(int(admin_id))
        data["admin_ids"] = ids
        _save(data)
        return True
    return False


# ------------------------------------------------------------------
# Owner admins — seeded once by install.sh, not editable from /admin.
# This is the fallback so the bot can never end up with no admin at all
# (see utils/permissions.py::is_owner_admin / remove_admin).
# ------------------------------------------------------------------

def get_owner_admin_ids() -> List[int]:
    return list(_load().get("owner_admin_ids", []))


def set_owner_admin_ids(admin_ids: List[int]) -> None:
    data = _load()
    data["owner_admin_ids"] = [int(x) for x in admin_ids if x]
    _save(data)


# ------------------------------------------------------------------
# Bot name / logging
# ------------------------------------------------------------------

def get_bot_name() -> str:
    return _load().get("bot_name", "Little AI")


def set_bot_name(name: str) -> None:
    data = _load()
    data["bot_name"] = name.strip() or "Little AI"
    _save(data)


def get_log_group_id() -> Optional[int]:
    return _load().get("log_group_id")


def set_log_group_id(group_id: int) -> None:
    data = _load()
    data["log_group_id"] = int(group_id)
    _save(data)


def is_logging_enabled() -> bool:
    return bool(_load().get("logging_enabled", False))


def set_logging_enabled(enabled: bool) -> None:
    data = _load()
    data["logging_enabled"] = bool(enabled)
    _save(data)


# ------------------------------------------------------------------
# Sponsor channels / forced membership
# ------------------------------------------------------------------

def get_sponsor_channels() -> List[Dict]:
    return list(_load().get("sponsor_channels", []))


def add_sponsor_channel(channel_id, title: str = "", link: str = "") -> Dict:
    raw = str(channel_id).strip()
    try:
        stored_id = int(raw)
    except ValueError:
        stored_id = raw if raw.startswith("@") else f"@{raw.lstrip('@')}"

    channel = {"id": stored_id, "title": (title or raw).strip(), "link": (link or "").strip()}

    data = _load()
    channels = data.get("sponsor_channels", [])
    for existing in channels:
        if existing.get("id") == channel["id"]:
            return existing
    channels.append(channel)
    data["sponsor_channels"] = channels
    _save(data)
    return channel


def remove_sponsor_channel(index: int) -> bool:
    data = _load()
    channels = data.get("sponsor_channels", [])
    if 0 <= index < len(channels):
        channels.pop(index)
        data["sponsor_channels"] = channels
        _save(data)
        return True
    return False


def is_membership_required() -> bool:
    return bool(_load().get("membership_required", False))


def set_membership_required(value: bool) -> None:
    data = _load()
    data["membership_required"] = bool(value)
    _save(data)


# ------------------------------------------------------------------
# Database credentials
# ------------------------------------------------------------------
# Written once by install.sh; readable/writable at any time (e.g. from a
# future /admin option) since db/database.py reads these fresh on every
# connection rather than caching them at import time.

def get_db_config() -> Dict[str, str]:
    data = _load()
    return {
        "host": data.get("db_host") or "localhost",
        "port": str(data.get("db_port") or "5432"),
        "database": data.get("db_name") or "",
        "user": data.get("db_user") or "",
        "password": data.get("db_password") or "",
    }


def set_db_config(
    host: str = None,
    port: str = None,
    database: str = None,
    user: str = None,
    password: str = None,
) -> None:
    data = _load()
    if host is not None:
        data["db_host"] = host.strip()
    if port is not None:
        data["db_port"] = str(port).strip()
    if database is not None:
        data["db_name"] = database.strip()
    if user is not None:
        data["db_user"] = user.strip()
    if password is not None:
        data["db_password"] = password
    _save(data)


# ------------------------------------------------------------------
# Secrets: bot token / Spotify app credentials
# ------------------------------------------------------------------
# Spotify credentials are read fresh on every call (not cached at import
# time) so an admin changing them via /admin takes effect immediately,
# with no restart.

def get_bot_token() -> str:
    return (_load().get("bot_token") or "").strip()


def set_bot_token(token: str) -> None:
    data = _load()
    data["bot_token"] = (token or "").strip()
    _save(data)


def get_spotify_client_id() -> str:
    return (_load().get("spotify_client_id") or "").strip()


def get_spotify_client_secret() -> str:
    return (_load().get("spotify_client_secret") or "").strip()


def get_spotify_redirect_uri() -> str:
    return (_load().get("spotify_redirect_uri") or "").strip() or "http://localhost:8888/callback"


def set_spotify_credentials(client_id: str = None, client_secret: str = None, redirect_uri: str = None) -> None:
    data = _load()
    if client_id is not None:
        data["spotify_client_id"] = client_id.strip()
    if client_secret is not None:
        data["spotify_client_secret"] = client_secret.strip()
    if redirect_uri is not None:
        data["spotify_redirect_uri"] = redirect_uri.strip()
    _save(data)


def is_spotify_configured() -> bool:
    return bool(get_spotify_client_id() and get_spotify_client_secret())


# ------------------------------------------------------------------
# Misc
# ------------------------------------------------------------------

def is_first_run() -> bool:
    return not bool(_load().get("installed_at"))


def mark_installed() -> None:
    data = _load()
    data["installed_at"] = __import__("datetime").datetime.now().isoformat()
    _save(data)


def get_config() -> Dict:
    return _load()


def update_config(key: str, value: Any) -> None:
    data = _load()
    data[key] = value
    _save(data)
