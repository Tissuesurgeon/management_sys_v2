from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from django.utils import timezone

from workforce.models import MaintenanceTask, TaskState, Worker


def checklist_is_complete(
    checklist: List[str],
    checklist_done: Optional[Dict[str, Any]],
) -> bool:
    """True when every checklist line index is marked done in ``checklist_done``."""
    if not checklist:
        return True
    done = checklist_done or {}
    for i in range(len(checklist)):
        if not (done.get(str(i)) or done.get(i)):
            return False
    return True


def effective_worker_display_status(
    persisted_status: str,
    checklist: List[str],
    checklist_done: Optional[Dict[str, Any]],
) -> str:
    """UI / active-list status: completed only when the checklist is fully checked."""
    if persisted_status == TaskState.Status.COMPLETED and not checklist_is_complete(
        checklist,
        checklist_done,
    ):
        return TaskState.Status.IN_PROGRESS
    return persisted_status
from workforce.services.date_utils import date_key, format_time, start_of_day, to_aware
from workforce.services.recurrence import occurs_on_event_day, recurrence_dict_from_task


@dataclass
class DerivedTask:
    id: str
    title: str
    description: str
    location: str
    due_time: str
    due_date: datetime
    worker_pk: Optional[int]
    status: str
    checklist: List[str]
    source_task_id: int
    date_key_str: str
    color: str
    assigned_trade: str


def generate_tasks_from_calendar(
    events,
    day: Union[datetime, date],
    *,
    worker_trade: Optional[str] = None,
    viewer_worker_pk: Optional[int] = None,
) -> List[DerivedTask]:
    """Expand calendar maintenance tasks for ``day``.

    If ``worker_trade`` is set (field technician), only include tasks assigned to that trade.
    If unset (e.g. facility manager views all), include every task.

    ``viewer_worker_pk`` is stored on each derived task for compatibility (logged-in worker).
    """
    day_start = start_of_day(day)
    if timezone.is_naive(day_start):
        day_start = to_aware(day_start)
    key = date_key(day_start)
    out: List[DerivedTask] = []

    for ev in events:
        if worker_trade is not None and ev.assigned_trade != worker_trade:
            continue
        rec = recurrence_dict_from_task(ev)
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
        out.append(
            DerivedTask(
                id=f'{ev.pk}::{key}',
                title=ev.title,
                location=ev.location or '',
                description=getattr(ev, 'description', '') or '',
                due_time=format_time(due),
                due_date=due,
                worker_pk=viewer_worker_pk,
                status='scheduled',
                checklist=list(ev.checklist or []),
                source_task_id=ev.pk,
                date_key_str=key,
                color=ev.color or 'blue',
                assigned_trade=ev.assigned_trade,
            )
        )

    out.sort(key=lambda t: t.due_date)
    return out


def merge_task_state(
    tasks: List[DerivedTask],
    state_map: Dict[str, TaskState],
) -> List[Dict[str, Any]]:
    """Attach persisted status/notes from TaskState.

    ``status`` is the worker-facing effective status: ``completed`` only when the
    persisted status is completed *and* every checklist item is checked.
    """
    merged = []
    for t in tasks:
        st = state_map.get(t.id)
        persisted = st.status if st else t.status
        checklist_done = st.checklist_done if st else {}
        row = {
            'task': t,
            'persist': st,
            'persisted_status': persisted,
            'status': effective_worker_display_status(persisted, t.checklist, checklist_done),
            'notes': st.notes if st else '',
            'checklist_done': checklist_done,
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
    """``derived_task_id`` is ``{maintenance_task_pk}::{YYYY-MM-DD}``."""
    parts = derived_id.split('::', 1)
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), parts[1]
    except ValueError:
        return None, None


def trade_label(value: str) -> str:
    """Human label for a Worker.Trade value."""
    try:
        return Worker.Trade(value).label
    except ValueError:
        return value
