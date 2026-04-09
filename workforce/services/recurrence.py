from datetime import date, datetime
from typing import Any, Dict, Optional, Union

from .date_utils import start_of_day


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
    """Mirror of Management_sys recurrence.js occursOnEventDay."""
    target = start_of_day(day)
    start = start_of_day(event_start)

    if target < start:
        return False

    rec = recurrence or {}
    end = _parse_end(rec)
    if end and target > end:
        return False

    rtype = rec.get('type') or 'none'

    if rtype == 'none':
        return target == start

    if rtype == 'daily':
        return True

    if rtype == 'weekly':
        # Match JS Date.getDay(): Sunday=0 .. Saturday=6
        def js_get_day(d: datetime) -> int:
            return (d.weekday() + 1) % 7

        return js_get_day(target) == js_get_day(start)

    if rtype == 'monthly':
        dom = start.day
        if target.day != dom:
            return False
        import calendar

        last = calendar.monthrange(target.year, target.month)[1]
        if dom > last:
            return False
        return True

    return False


def recurrence_dict_from_event(event) -> Dict[str, Any]:
    """Build recurrence dict from CalendarEvent model."""
    r: Dict[str, Any] = {'type': event.recurrence_type or 'none'}
    if event.recurrence_end:
        r['endDate'] = event.recurrence_end.isoformat()
    return r
