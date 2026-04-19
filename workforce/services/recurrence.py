from datetime import date, datetime
from typing import Any, Dict, Optional, Union

from django.utils import timezone as django_tz

from .date_utils import start_of_day


def _local_date(d: Union[datetime, date]) -> date:
    """Calendar date in the active timezone (matches how calendar UI picks days)."""
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        dt = d
        if django_tz.is_naive(dt):
            dt = django_tz.make_aware(dt, django_tz.get_current_timezone())
        return django_tz.localtime(dt).date()
    raise TypeError(d)


def _parse_end(recurrence: Dict[str, Any]) -> Optional[datetime]:
    end = recurrence.get('endDate') if recurrence else None
    if not end:
        return None
    if isinstance(end, str):
        y, m, d = (int(x) for x in end.split('-')[:3])
        return start_of_day(date(y, m, d))
    return start_of_day(end)


def occurs_on_event_day(
    recurrence: Optional[Dict[str, Any]],
    event_start: Union[datetime, date],
    day: Union[datetime, date],
) -> bool:
    """Mirror of Management_sys recurrence.js occursOnEventDay.

    Compare **local calendar dates** for the active ``TIME_ZONE`` so one-off events
    and recurrence lines match the calendar grid and task list (avoids midnight-UTC
    vs midnight-local mismatches when ``USE_TZ`` is true).
    """
    target_date = _local_date(day)
    anchor_date = _local_date(event_start)

    if target_date < anchor_date:
        return False

    rec = recurrence or {}
    end = _parse_end(rec)
    if end:
        end_date = _local_date(end)
        if target_date > end_date:
            return False

    rtype = rec.get('type') or 'none'

    if rtype == 'none':
        return target_date == anchor_date

    if rtype == 'daily':
        return True

    if rtype == 'weekly':
        # Match JS Date.getDay(): Sunday=0 .. Saturday=6
        def js_get_day(d: date) -> int:
            return (d.weekday() + 1) % 7

        return js_get_day(target_date) == js_get_day(anchor_date)

    if rtype == 'monthly':
        dom = anchor_date.day
        if target_date.day != dom:
            return False
        import calendar

        last = calendar.monthrange(target_date.year, target_date.month)[1]
        if dom > last:
            return False
        return True

    return False


def recurrence_dict_from_task(task) -> Dict[str, Any]:
    """Build recurrence dict from MaintenanceTask."""
    r: Dict[str, Any] = {'type': task.recurrence_type or 'none'}
    if task.recurrence_end:
        r['endDate'] = task.recurrence_end.isoformat()
    return r
