import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from src import config

log = logging.getLogger("polybot")

def is_in_cooldown() -> bool:
    """
    Check if the current time is within the configured cooldown window.
    Times are compared in the configured timezone (default US/Eastern).
    """
    try:
        tz = ZoneInfo(config.COOLDOWN_TIMEZONE)
        now = datetime.now(tz)
        current_time_str = now.strftime("%H:%M")
        
        # Simple string comparison works for HH:MM format
        is_cooldown = config.COOLDOWN_START_TIME <= current_time_str <= config.COOLDOWN_END_TIME
        
        return is_cooldown
    except Exception as e:
        log.error("Error checking cooldown status: %s", e)
        return False


def get_dynamic_gap_trigger() -> float:
    """
    Return the appropriate GAP_TRIGGER_USD based on the current time.
    During active hours (default 07:00-15:00 Asia/Bangkok), return the ACTIVE value.
    Outside that window, return the DEFAULT (sniper) value.
    """
    try:
        tz = ZoneInfo(config.GAP_ACTIVE_TIMEZONE)
        now = datetime.now(tz)
        current_time_str = now.strftime("%H:%M")

        if config.GAP_ACTIVE_START <= current_time_str <= config.GAP_ACTIVE_END:
            return config.GAP_TRIGGER_USD_ACTIVE
        return config.GAP_TRIGGER_USD_DEFAULT
    except Exception as e:
        log.error("Error in dynamic gap trigger: %s — using default", e)
        return config.GAP_TRIGGER_USD_DEFAULT
