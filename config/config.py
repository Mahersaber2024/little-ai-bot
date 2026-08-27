"""config/config.py"""

import logging

from .bot_settings import (
    get_admin_ids,
    get_bot_name,
    get_log_group_id,
    is_logging_enabled,
    get_sponsor_channels,
    is_membership_required,
    is_first_run,
    reload_settings,
)

logger = logging.getLogger(__name__)

ADMIN_IDS = get_admin_ids()
BOT_NAME = get_bot_name()
LOG_GROUP_ID = get_log_group_id()
LOGGING_ENABLED = is_logging_enabled()
SPONSOR_CHANNELS = get_sponsor_channels()
MEMBERSHIP_REQUIRED = is_membership_required()
IS_FIRST_RUN = is_first_run()


def reload() -> None:
    """Reload all settings from bot_settings.json (call after any admin change)."""
    reload_settings()

    global ADMIN_IDS, BOT_NAME, LOG_GROUP_ID, LOGGING_ENABLED
    global SPONSOR_CHANNELS, MEMBERSHIP_REQUIRED, IS_FIRST_RUN

    ADMIN_IDS = get_admin_ids()
    BOT_NAME = get_bot_name()
    LOG_GROUP_ID = get_log_group_id()
    LOGGING_ENABLED = is_logging_enabled()
    SPONSOR_CHANNELS = get_sponsor_channels()
    MEMBERSHIP_REQUIRED = is_membership_required()
    IS_FIRST_RUN = is_first_run()

    logger.info("✅ Settings reloaded")
