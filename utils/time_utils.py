"""Timezone and game hour utilities."""

from datetime import datetime
import pytz

from config import TIMEZONE, DAY_START_HOUR, DAY_END_HOUR


def get_sg_now() -> datetime:
    """Get current time in Singapore timezone."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)


def is_game_hours() -> bool:
    """Check if current time is within game hours (9 AM - 11 PM SGT)."""
    now = get_sg_now()
    return DAY_START_HOUR <= now.hour < DAY_END_HOUR


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds <= 0:
        return "0m"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def format_countdown(seconds: float) -> str:
    """Format seconds into days/hours/minutes countdown."""
    if seconds <= 0:
        return "0m"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def seconds_until_hour(target_hour: int) -> float:
    """Get seconds until a specific hour today/tomorrow in SGT."""
    now = get_sg_now()
    target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target.replace(day=target.day + 1)
    return (target - now).total_seconds()
