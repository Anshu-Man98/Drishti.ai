"""
backend/tools/date_utils.py

Robust medical billing date parsing and validation utilities.
Supports:
- ISO 8601: '2031-03-14', '2031-03-14T10:30:00', '2031-03-14 10:30:00'
- dd-Mon-yyyy: '14-Mar-2031', '14-March-2031', '15-Oct-2026', '17-October-2026'
- dd/mm/yyyy: '14/03/2031', '14/3/2031', '15/10/2026'
- d-m-yy: '14-3-31', '14-03-31', '14/3/31', '14/03/31' (2-digit years converted: yy < 50 -> 20yy, else 19yy)
- Month names: 'March 14, 2031', '14 March 2031', 'Mar 14, 2031', '14 Mar 2031'
- Indian formats: '14.03.2031', '14-03-2031', '14/03/2031'
- Day ordinals: '14th March 2031', '1st Oct 2026', '2nd November 2026', '3rd Dec 2026'
- Injectable reference date ('now') for deterministic testing.
"""

import re
from datetime import datetime, timezone
from typing import Optional, Union, Tuple

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    from datetime import timedelta
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def parse_flexible_date(date_val: Union[str, datetime, None]) -> Optional[datetime]:
    """
    Parses a wide variety of date strings into a timezone-aware UTC datetime.
    Returns None if date cannot be parsed.
    """
    if date_val is None:
        return None

    if isinstance(date_val, datetime):
        if date_val.tzinfo is None:
            return date_val.replace(tzinfo=timezone.utc)
        return date_val.astimezone(timezone.utc)

    if not isinstance(date_val, str):
        return None

    s = date_val.strip()
    if not s:
        return None

    # Remove ordinals (1st, 2nd, 3rd, 14th)
    s_clean = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)

    # 1. ISO format with/without time and timezone
    if re.match(r"^\d{4}-\d{2}-\d{2}", s_clean):
        try:
            iso_str = s_clean.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass

    # Standard formats
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%b-%Y %I:%M %p",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y",
        "%d-%B-%Y %I:%M %p",
        "%d-%B-%Y %H:%M",
        "%d-%B-%Y",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %I:%M %p",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
        "%d %b, %Y",
        "%d %B, %Y",
        "%m/%d/%Y",
    )

    for fmt in formats:
        try:
            dt = datetime.strptime(s_clean, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # 2-digit years: d-m-yy, dd/mm/yy, dd-mm-yy
    m_2digit = re.match(r"^(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{2})$", s_clean)
    if m_2digit:
        day = int(m_2digit.group(1))
        month = int(m_2digit.group(2))
        yy = int(m_2digit.group(3))
        year = 2000 + yy if yy < 50 else 1900 + yy
        try:
            dt = datetime(year, month, day, tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    # Regex search for embedded dates in longer strings
    # Match ISO: 2031-03-14
    m_iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", s_clean)
    if m_iso:
        try:
            return datetime.strptime(m_iso.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Match dd-Mon-yyyy
    m_dmy = re.search(r"\b(\d{1,2}-[A-Za-z]{3,9}-\d{4})\b", s_clean)
    if m_dmy:
        for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
            try:
                return datetime.strptime(m_dmy.group(1), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    # Match dd/mm/yyyy
    m_slash = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", s_clean)
    if m_slash:
        try:
            return datetime.strptime(m_slash.group(1), "%d/%m/%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Match dd.mm.yyyy
    m_dot = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", s_clean)
    if m_dot:
        try:
            return datetime.strptime(m_dot.group(1), "%d.%m.%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def is_date_after_reference(
    date_val: Union[str, datetime, None],
    now: Optional[Union[datetime, str]] = None,
    tolerance_days: int = 1
) -> Tuple[bool, Optional[datetime], datetime]:
    """
    Checks if a given date string or datetime is in the future relative to `now`
    by comparing calendar dates in Asia/Kolkata (IST) with a configurable tolerance (default +1 day).
    If `now` is None, uses current server time in IST.
    Returns: (is_future, parsed_datetime, reference_now)
    """
    if now is not None:
        if isinstance(now, str):
            ref_parsed = parse_flexible_date(now)
            ref_now = ref_parsed if ref_parsed is not None else datetime.now(IST)
        elif isinstance(now, datetime):
            ref_now = now
        else:
            ref_now = datetime.now(IST)
    else:
        ref_now = datetime.now(IST)

    if ref_now.tzinfo is None:
        ref_now = ref_now.replace(tzinfo=IST)
    ref_now_ist = ref_now.astimezone(IST)
    ref_cal = ref_now_ist.date()

    parsed = parse_flexible_date(date_val)
    if not parsed:
        return False, None, ref_now_ist

    parsed_ist = parsed.astimezone(IST)
    cand_cal = parsed_ist.date()

    diff_days = (cand_cal - ref_cal).days
    is_future = diff_days > tolerance_days

    return is_future, parsed, ref_now_ist
