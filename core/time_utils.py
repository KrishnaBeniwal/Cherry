import datetime
import re
import zoneinfo
import calendar
from typing import Optional

def parse_duration(time_str: str) -> int:
    """Parses a duration string like '1h30m', '2d5h' into total seconds."""
    time_str = time_str.strip().lower()
    if not time_str:
        raise ValueError("Empty duration string.")
        
    pattern = r'^(?:(\d+)\s*w(?:eeks?)?)?\s*(?:(\d+)\s*d(?:ays?)?)?\s*(?:(\d+)\s*h(?:ou)?r?s?)?\s*(?:(\d+)\s*m(?:in(?:ute)?s?)?)?\s*(?:(\d+)\s*s(?:ec(?:ond)?s?)?)?$'
    match = re.match(pattern, time_str)
    
    if not match or not any(match.groups()):
        # Handle months separately due to variable days.
        m_month = re.match(r'^(\d+)\s*months?$', time_str)
        if m_month:
            return int(m_month.group(1)) * 30 * 86400
        raise ValueError("Invalid duration format. Use things like '1h30m' or '2d'.")
        
    weeks = int(match.group(1) or 0)
    days = int(match.group(2) or 0)
    hours = int(match.group(3) or 0)
    minutes = int(match.group(4) or 0)
    seconds = int(match.group(5) or 0)
    
    total_seconds = (weeks * 7 * 86400) + (days * 86400) + (hours * 3600) + (minutes * 60) + seconds
    if total_seconds <= 0:
        raise ValueError("Duration must be greater than 0.")
        
    return total_seconds

def parse_time(time_str: str) -> datetime.time:
    """Parses a time string like '6am', '18:00', '11:59 PM' into a datetime.time object."""
    time_str = time_str.strip().lower()
    
    m = re.match(r'^(\d{1,2}):(\d{2}):(\d{2})$', time_str)
    if m:
        return datetime.time(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        
    m = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if m:
        return datetime.time(int(m.group(1)), int(m.group(2)))
        
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(am|pm)$', time_str)
    if m:
        h = int(m.group(1))
        minute = int(m.group(2) or 0)
        sec = int(m.group(3) or 0)
        ampm = m.group(4)
        
        if h < 1 or h > 12:
            raise ValueError("12-hour format hour must be between 1 and 12.")
            
        if ampm == 'pm' and h != 12:
            h += 12
        if ampm == 'am' and h == 12:
            h = 0
            
        return datetime.time(h, minute, sec)
        
    raise ValueError("Invalid time format. Use '6am', '18:00', etc.")

def parse_date(date_str: str, tz: datetime.tzinfo) -> datetime.date:
    """Parses a date string like 'today', 'tomorrow', '25 June' into a datetime.date object."""
    date_str = date_str.strip().lower()
    now_local = datetime.datetime.now(tz).date()
    
    if date_str == 'today':
        return now_local
    if date_str == 'tomorrow':
        return now_local + datetime.timedelta(days=1)
        
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        
    formats = [
        "%d %B", "%d %b", "%B %d", "%b %d",
        "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
        "%d/%m/%Y", "%m/%d/%Y", "%d/%m", "%m/%d",
        "%d-%m-%Y", "%m-%d-%Y", "%d-%m", "%m-%d"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            if dt.year == 1900:
                # Guess current or next year if not provided.
                dt = dt.replace(year=now_local.year)
                if dt.date() < now_local:
                    dt = dt.replace(year=now_local.year + 1)
            return dt.date()
        except ValueError:
            continue
            
    raise ValueError("Invalid date format. Use 'today', 'tomorrow', '25 June', '2026-06-25', etc.")

def get_timezone(tz_str: Optional[str]) -> datetime.tzinfo:
    """Resolves an IANA timezone string. Returns UTC if None."""
    if not tz_str:
        return datetime.timezone.utc
    try:
        return zoneinfo.ZoneInfo(tz_str)
    except Exception:
        raise ValueError(f"Invalid timezone: {tz_str}")

def calculate_next_occurrence(base_timestamp: int, repeat_type: str, interval: int = 0) -> int:
    """
    Calculates the next occurrence timestamp based on the base timestamp and repeat logic.
    Always maintains the base interval to prevent drift.
    """
    dt = datetime.datetime.fromtimestamp(base_timestamp, tz=datetime.timezone.utc)
    
    if repeat_type == "every":
        if interval <= 0:
            raise ValueError("Interval must be > 0 for 'every'.")
        return base_timestamp + interval
        
    if repeat_type == "daily":
        dt += datetime.timedelta(days=1)
        return int(dt.timestamp())
        
    if repeat_type == "weekly":
        dt += datetime.timedelta(days=7)
        return int(dt.timestamp())
        
    if repeat_type == "monthly":
        # Add month, handling variable days.
        month = dt.month + 1
        year = dt.year
        if month > 12:
            month = 1
            year += 1
            
        # Clip day to max days.
        max_days = calendar.monthrange(year, month)[1]
        day = min(dt.day, max_days)
        
        dt = dt.replace(year=year, month=month, day=day)
        return int(dt.timestamp())
        
    return 0
