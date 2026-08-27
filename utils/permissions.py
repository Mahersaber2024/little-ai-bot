"""utils/permissions.py

ADMIN_USER_IDS = the .env-seeded "owner" admin(s) (ADMIN_USER_IDS in .env,
comma-separated) plus anyone added later via the /admin panel. The .env
seed always stays admin — it's the fallback so the bot never ends up with
no admin at all.
"""
import os

from config import bot_settings

_env_raw = os.getenv("ADMIN_USER_IDS", "")
OWNER_ADMIN_IDS = [int(x) for x in _env_raw.replace(" ", "").split(",") if x]


def get_admin_ids() -> list[int]:
    """Owner admins (from .env) + admins added at runtime, deduplicated."""
    dynamic = bot_settings.get_admin_ids()
    return list(dict.fromkeys(OWNER_ADMIN_IDS + dynamic))


# Kept as a module-level list for callers that just want a snapshot
# (e.g. auth.get_admin_token). Use get_admin_ids() if you need it fresh
# after an admin was just added/removed.
ADMIN_USER_IDS = get_admin_ids()


def is_admin(user_id: int) -> bool:
    return int(user_id) in get_admin_ids()


def is_owner_admin(user_id: int) -> bool:
    """True only for .env-seeded admins — used to stop the last owner from
    being removed via the bot."""
    return int(user_id) in OWNER_ADMIN_IDS


def add_admin(user_id: int) -> bool:
    global ADMIN_USER_IDS
    added = bot_settings.add_admin_id(user_id)
    ADMIN_USER_IDS = get_admin_ids()
    return added


def remove_admin(user_id: int) -> bool:
    global ADMIN_USER_IDS
    if is_owner_admin(user_id):
        return False  # owner admins (from .env) can't be removed via the bot
    removed = bot_settings.remove_admin_id(user_id)
    ADMIN_USER_IDS = get_admin_ids()
    return removed
