"""Explicit local date boundaries for Canvas queries."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from .config import BridgeError


def now_utc():
    return datetime.now(timezone.utc)


def parse_date(value: str, zone: str, end_of_day=False):
    try:
        if len(value) == 10:
            day = datetime.strptime(value, "%Y-%m-%d").date()
            result = datetime.combine(day, time.max if end_of_day else time.min)
        else:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            result = result.replace(tzinfo=ZoneInfo(zone))
        return result
    except (ValueError, TypeError, AttributeError):
        raise BridgeError("日期必须使用 YYYY-MM-DD 或 ISO 8601 格式。") from None


def optional_date(value, zone):
    if not value:
        return None
    try:
        return parse_date(value, zone)
    except BridgeError:
        return None
