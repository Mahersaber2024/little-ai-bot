"""utils/permissions.py

ADMIN_USER_IDS = the "owner" admin(s) seeded once by install.sh
(bot_settings.json's owner_admin_ids, set at install time and not
editable from /admin) plus anyone added later via the /admin panel. The
owner seed always stays admin — it's the fallback so the bot never ends
up with no admin at all.
"""
from config import bot_settings


def get_admin_ids() -> list[int]:
    """Owner admins (seeded at install) + admins added at runtime, deduplicated."""
    owner = bot_settings.get_owner_admin_ids()
    dynamic = bot_settings.get_admin_ids()
    return list(dict.fromkeys(owner + dynamic))


# Kept as a module-level list for callers that just want a snapshot
# (e.g. auth.get_admin_token). Use get_admin_ids() if you need it fresh
# after an admin was just added/removed.
ADMIN_USER_IDS = get_admin_ids()


def is_admin(user_id: int) -> bool:
    return int(user_id) in get_admin_ids()


def is_owner_admin(user_id: int) -> bool:
    """True only for admins seeded at install time — used to stop the
    last owner from being removed via the bot."""
    return int(user_id) in bot_settings.get_owner_admin_ids()


def add_admin(user_id: int) -> bool:
    global ADMIN_USER_IDS
    added = bot_settings.add_admin_id(user_id)
    ADMIN_USER_IDS = get_admin_ids()
    return added


def remove_admin(user_id: int) -> bool:
    global ADMIN_USER_IDS
    if is_owner_admin(user_id):
        return False  # owner admins (seeded at install) can't be removed via the bot
    removed = bot_settings.remove_admin_id(user_id)
    ADMIN_USER_IDS = get_admin_ids()
    return removed
