"""What "today" is for the business (the stores' time zone, not the server's UTC clock)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings

EARLIEST = date(2000, 1, 1)  # dates before this are refused (same as the 2000-2099 months elsewhere)


def business_today() -> date:
    return datetime.now(ZoneInfo(get_settings().business_timezone)).date()
