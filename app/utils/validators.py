import re
from datetime import datetime, date, timedelta
from typing import Optional, Tuple


def normalize_phone_number(phone: str) -> str:
    """
    Normalizes phone numbers by stripping whatsapp: prefix and whitespace.
    Ensures leading '+' if international code present.
    Example: 'whatsapp:+919876543210' -> '+919876543210'
    """
    if not phone:
        return ""
    cleaned = phone.strip()
    if cleaned.lower().startswith("whatsapp:"):
        cleaned = cleaned[9:].strip()

    # Remove dashes, spaces, parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", cleaned)
    if not cleaned.startswith("+") and cleaned.isdigit() and len(cleaned) == 10:
        cleaned = "+91" + cleaned  # Default country code fallback
    return cleaned


def normalize_time_slot(time_str: str) -> Optional[str]:
    """
    Normalizes times to HH:MM 24-hour format.
    Accepts: '9:00', '09:00', '9am', '9:30 AM', '3:30 pm', '15:30'.
    """
    if not time_str:
        return None

    cleaned = time_str.strip().lower()

    # Try standard formats
    formats = [
        "%H:%M", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H"
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.strftime("%H:%M")
        except ValueError:
            continue

    # Regex heuristic for strings like "11am", "3.30pm"
    match = re.search(r"(\d{1,2})(?::|\.)?(\d{2})?\s*(am|pm)?", cleaned)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        meridiem = match.group(3)
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    return None


def parse_target_date(date_str: str, base_date: Optional[date] = None) -> Optional[date]:
    """
    Parses date string supporting ISO YYYY-MM-DD or natural words like 'tomorrow'.
    """
    if not date_str:
        return None

    if base_date is None:
        base_date = datetime.utcnow().date()

    cleaned = date_str.strip().lower()

    if cleaned in ("today",):
        return base_date
    if cleaned in ("tomorrow",):
        return base_date + timedelta(days=1)
    if cleaned in ("day after tomorrow",):
        return base_date + timedelta(days=2)

    # Weekday lookups e.g. "monday", "next friday"
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    for day_name, target_weekday in weekdays.items():
        if day_name in cleaned:
            days_ahead = (target_weekday - base_date.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7  # If today is Monday, "Monday" means next Monday
            return base_date + timedelta(days=days_ahead)

    # Standard date formats
    date_formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y",
        "%d %b", "%d %B"
    ]
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            # If year wasn't specified, use base_date year
            if "%Y" not in fmt:
                parsed = parsed.replace(year=base_date.year)
                if parsed.date() < base_date:
                    parsed = parsed.replace(year=base_date.year + 1)
            return parsed.date()
        except ValueError:
            continue

    return None
