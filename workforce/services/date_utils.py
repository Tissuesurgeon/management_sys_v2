from datetime import date, datetime, time
from typing import Union

import django.utils.timezone as tz


def start_of_day(d: Union[date, datetime]) -> datetime:
    if isinstance(d, datetime):
        if tz.is_aware(d):
            return d.replace(hour=0, minute=0, second=0, microsecond=0)
        return datetime(d.year, d.month, d.day, 0, 0, 0)
    return datetime(d.year, d.month, d.day, 0, 0, 0)


def date_key(d: Union[date, datetime]) -> str:
    x = start_of_day(d)
    return x.strftime('%Y-%m-%d')


def parse_date_key(key: str) -> datetime:
    y, m, day = (int(p) for p in key.split('-'))
    return start_of_day(date(y, m, day))


def format_time(dt: datetime) -> str:
    return dt.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ', 1)


def to_aware(dt: datetime) -> datetime:
    if tz.is_aware(dt):
        return dt
    return tz.make_aware(dt, tz.get_current_timezone())
