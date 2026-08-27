"""config/bot_settings.py

Runtime settings the admin can change from inside Telegram (via /admin),
stored as JSON so they persist across restarts without touching .env.

Secrets that never change at runtime (bot token, Spotify credentials,
Postgres credentials) stay in .env / db/database.py — this file is only
for things the admin edits through the bot itself.
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
        "bot_name": "Little AI",
        "log_group_id": None,
        "logging_enabled": False,
        "sponsor_channels": [],
        "membership_required": False,
        "installed_at": "",
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
