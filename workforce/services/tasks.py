from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from django.utils import timezone

from workforce.models import CalendarEvent, TaskState
from workforce.services.date_utils import date_key, format_time, start_of_day, to_aware
from workforce.services.recurrence import occurs_on_event_day, recurrence_dict_from_event


@dataclass
class DerivedTask:
    id: str
    title: str
    location: str
    due_time: str
    due_date: datetime
    worker_pk: int
    status: str
    checklist: List[str]
    source_event_id: int
    date_key_str: str
    color: str


def generate_tasks_from_calendar(
    events,
    day: Union[datetime, date],
    *,
    worker_pk: Optional[int] = None,
) -> List[DerivedTask]:
    """Port of generateTasksFromCalendar.js"""
    day_start = start_of_day(day)
    if timezone.is_naive(day_start):
        day_start = to_aware(day_start)
    key = date_key(day_start)
    out: List[DerivedTask] = []

    for ev in events:
        if worker_pk is not None and ev.assigned_worker_id != worker_pk:
            continue
        rec = recurrence_dict_from_event(ev)
        if not occurs_on_event_day(rec, ev.start, day_start):
            continue
        start_dt = ev.start
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
        due = day_start.replace(
            hour=start_dt.hour,
            minute=start_dt.minute,
            second=0,
            microsecond=0,
        )
        wid = ev.assigned_worker_id
        out.append(
            DerivedTask(
                id=f'{ev.pk}::{key}',
                title=ev.title,
                location=ev.location or '',
                due_time=format_time(due),
                due_date=due,
                worker_pk=wid,
                status='scheduled',
                checklist=list(ev.checklist or []),
                source_event_id=ev.pk,
                date_key_str=key,
                color=ev.color or 'blue',
            )
        )

    out.sort(key=lambda t: t.due_date)
    return out


def merge_task_state(
    tasks: List[DerivedTask],
    state_map: Dict[str, TaskState],
) -> List[Dict[str, Any]]:
    """Attach persisted status/notes from TaskState."""
    merged = []
    for t in tasks:
        st = state_map.get(t.id)
        row = {
            'task': t,
            'persist': st,
            'status': st.status if st else t.status,
            'notes': st.notes if st else '',
            'checklist_done': st.checklist_done if st else {},
            'photo_count': st.photo_count if st else 0,
        }
        merged.append(row)
    return merged


def collect_state_map_for_ids(derived_ids: List[str]) -> Dict[str, TaskState]:
    if not derived_ids:
        return {}
    qs = TaskState.objects.filter(derived_task_id__in=derived_ids)
    return {s.derived_task_id: s for s in qs}


def parse_derived_task_id(derived_id: str) -> Tuple[Optional[int], Optional[str]]:
    """``derived_task_id`` is ``{calendar_event_pk}::{YYYY-MM-DD}``."""
    parts = derived_id.split('::', 1)
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), parts[1]
    except ValueError:
        return None, None
