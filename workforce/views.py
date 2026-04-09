from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from workforce.decorators import org_admin_required, worker_required
from workforce.forms import (
    CalendarEventForm,
    ProfilePhotoForm,
    SignupForm,
    TaskStateUpdateForm,
    UserAccountForm,
    WorkerInvitationForm,
    WorkerProfileForm,
)
from workforce.import_parser import create_events_from_import, parse_uploaded_file
from workforce.models import CalendarEvent, Profile, TaskState, Worker, WorkerInvitation
from workforce.utils import ensure_profile
from workforce.services.date_utils import date_key, parse_date_key
from workforce.services.tasks import (
    collect_state_map_for_ids,
    generate_tasks_from_calendar,
    merge_task_state,
    parse_derived_task_id,
)

def _profile(request):
    return ensure_profile(request.user)


def _enrich_task_states_for_report(states: List[TaskState]) -> List[Dict[str, Any]]:
    """Join persisted task rows to calendar events and workers for admin reporting."""
    eids: List[int] = []
    for st in states:
        eid, _ = parse_derived_task_id(st.derived_task_id)
        if eid is not None:
            eids.append(eid)
    events = {
        e.pk: e
        for e in CalendarEvent.objects.select_related('assigned_worker').filter(pk__in=set(eids))
    }
    rows: List[Dict[str, Any]] = []
    for st in states:
        eid, task_date = parse_derived_task_id(st.derived_task_id)
        ev = events.get(eid) if eid is not None else None
        checklist = list(ev.checklist or []) if ev else []
        done = st.checklist_done or {}
        n_done = sum(
            1
            for i in range(len(checklist))
            if done.get(str(i)) or done.get(i)
        )
        rows.append(
            {
                'state': st,
                'event': ev,
                'task_date': task_date,
                'worker_name': ev.assigned_worker.name if ev and ev.assigned_worker else '—',
                'checklist_done_count': n_done,
                'checklist_total': len(checklist),
                'title': ev.title if ev else 'Unknown or deleted event',
                'location': (ev.location or '') if ev else '',
            },
        )
    return rows


def _local_event_start_date_key(ev: CalendarEvent) -> str:
    s = ev.start
    if timezone.is_naive(s):
        s = timezone.make_aware(s, timezone.get_current_timezone())
    return date_key(timezone.localtime(s).date())


def home(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect('workforce:login')
    prof = _profile(request)
    if prof.role == Profile.Role.ORG_ADMIN:
        return redirect('workforce:admin_dashboard')
    return redirect('workforce:worker_my_tasks')


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect('workforce:home')
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('workforce:home')
    return render(request, 'workforce/login.html', {'form': form})


def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect('workforce:home')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        role = form.cleaned_data['role']
        invitation = getattr(form, '_invitation', None)
        with transaction.atomic():
            inv_locked = None
            if role == Profile.Role.WORKER and invitation:
                inv_locked = WorkerInvitation.objects.select_for_update().get(pk=invitation.pk)
                if inv_locked.claimed_at:
                    messages.error(
                        request,
                        'This registration code was already used. Ask your admin for a new one.',
                    )
                    return render(request, 'workforce/signup.html', {'form': form})
            user = form.save(commit=False)
            if form.cleaned_data.get('email'):
                user.email = form.cleaned_data['email']
            user.save()
            Profile.objects.create(user=user, role=role)
            if role == Profile.Role.WORKER and inv_locked:
                Worker.objects.create(
                    user=user,
                    name=inv_locked.name,
                    title=inv_locked.title,
                    department=inv_locked.department,
                    employee_id=inv_locked.employee_id or (form.cleaned_data.get('employee_id') or '').strip(),
                    facility_location=inv_locked.facility_location,
                )
                inv_locked.claimed_at = timezone.now()
                inv_locked.claimed_by = user
                inv_locked.save()
            elif role == Profile.Role.WORKER:
                Worker.objects.create(
                    user=user,
                    name=form.cleaned_data['worker_name'].strip(),
                    employee_id=form.cleaned_data.get('employee_id') or '',
                )
        login(request, user)
        messages.success(request, 'Account created.')
        return redirect('workforce:home')
    return render(request, 'workforce/signup.html', {'form': form})


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('workforce:login')


@org_admin_required
def admin_dashboard(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    worker_count = Worker.objects.count()
    events_qs = CalendarEvent.objects.select_related('assigned_worker').all()
    today_tasks = generate_tasks_from_calendar(list(events_qs), timezone.localtime())
    today_tasks_count = len(today_tasks)
    completed_today = TaskState.objects.filter(
        status=TaskState.Status.COMPLETED,
        last_saved_at__date=today,
    ).count()
    open_items = TaskState.objects.exclude(status=TaskState.Status.COMPLETED).count()
    recent_states = list(TaskState.objects.order_by('-last_saved_at')[:6])
    recent_activity = _enrich_task_states_for_report(recent_states)
    return render(
        request,
        'workforce/admin/dashboard.html',
        {
            'worker_count': worker_count,
            'today_tasks_count': today_tasks_count,
            'completed_today': completed_today,
            'open_items': open_items,
            'today': today,
            'recent_activity': recent_activity,
        },
    )


@org_admin_required
def admin_calendar_list(request: HttpRequest) -> HttpResponse:
    """Calendar page — layout parity with Management_sys AdminCalendar + CalendarMonth."""
    now = timezone.localtime()
    today = now.date()

    try:
        y = int(request.GET.get('year') or now.year)
        m = int(request.GET.get('month') or now.month)
    except ValueError:
        y, m = now.year, now.month
    if m < 1:
        m, y = 12, y - 1
    if m > 12:
        m, y = 1, y + 1

    selected_raw = request.GET.get('selected')
    if selected_raw:
        try:
            parts = [int(x) for x in selected_raw.split('-')[:3]]
            selected_date = date(parts[0], parts[1], parts[2])
        except (ValueError, IndexError):
            selected_date = today
    else:
        selected_date = today

    events_qs = CalendarEvent.objects.select_related('assigned_worker').all()
    events_list = list(events_qs)
    event_count = len(events_list)

    first = date(y, m, 1)
    # JS Date.getDay(): Sun=0 … Sat=6. Python weekday(): Mon=0 … Sun=6
    start_pad = (first.weekday() + 1) % 7
    days_in_month = calendar.monthrange(y, m)[1]
    cells: List[Optional[date]] = [None] * start_pad
    for d in range(1, days_in_month + 1):
        cells.append(date(y, m, d))
    while len(cells) % 7 != 0:
        cells.append(None)

    tasks_by_day: Dict[str, int] = {}
    for d in range(1, days_in_month + 1):
        day = date(y, m, d)
        tasks_by_day[date_key(day)] = len(
            generate_tasks_from_calendar(events_list, day),
        )

    calendar_cells: List[Dict[str, Any]] = []
    for cell in cells:
        if cell is None:
            calendar_cells.append({'pad': True})
        else:
            dk = date_key(cell)
            calendar_cells.append(
                {
                    'pad': False,
                    'date': cell,
                    'key': dk,
                    'count': tasks_by_day.get(dk, 0),
                },
            )

    selected_key = date_key(selected_date)
    today_key = date_key(today)

    day_events: List[CalendarEvent] = []
    for ev in events_list:
        if _local_event_start_date_key(ev) == selected_key:
            day_events.append(ev)

    tasks_for_day = generate_tasks_from_calendar(events_list, selected_date)

    prev_m, prev_y = (m - 1, y) if m > 1 else (12, y - 1)
    next_m, next_y = (m + 1, y) if m < 12 else (1, y + 1)

    header_subtitle = (
        f'{selected_date.strftime("%B %Y")} · Organization schedule'
    )
    import_open = request.GET.get('import') == '1'

    return render(
        request,
        'workforce/admin/calendar_list.html',
        {
            'events': events_list,
            'event_count': event_count,
            'view_year': y,
            'view_month': m,
            'month_title': date(y, m, 1).strftime('%B %Y'),
            'calendar_cells': calendar_cells,
            'selected_date': selected_date,
            'selected_key': selected_key,
            'today_key': today_key,
            'day_events': day_events,
            'tasks_for_day': tasks_for_day,
            'header_subtitle': header_subtitle,
            'tasks_for_day_count': len(tasks_for_day),
            'prev_year': prev_y,
            'prev_month': prev_m,
            'next_year': next_y,
            'next_month': next_m,
            'import_open': import_open,
        },
    )


@org_admin_required
def admin_calendar_create(request: HttpRequest) -> HttpResponse:
    form = CalendarEventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Event created.')
        return redirect('workforce:admin_calendar_list')
    return render(request, 'workforce/admin/calendar_form.html', {'form': form, 'title': 'New event'})


@org_admin_required
def admin_calendar_edit(request: HttpRequest, pk: int) -> HttpResponse:
    ev = get_object_or_404(CalendarEvent, pk=pk)
    form = CalendarEventForm(request.POST or None, instance=ev)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Event updated.')
        return redirect('workforce:admin_calendar_list')
    return render(
        request,
        'workforce/admin/calendar_form.html',
        {'form': form, 'title': 'Edit event', 'event': ev},
    )


@org_admin_required
def admin_calendar_delete(request: HttpRequest, pk: int) -> HttpResponse:
    ev = get_object_or_404(CalendarEvent, pk=pk)
    if request.method == 'POST':
        ev.delete()
        messages.success(request, 'Event deleted.')
        return redirect('workforce:admin_calendar_list')
    return render(request, 'workforce/admin/calendar_confirm_delete.html', {'event': ev})


@org_admin_required
def admin_tasks(request: HttpRequest) -> HttpResponse:
    raw = request.GET.get('date') or ''
    try:
        day = datetime.strptime(raw, '%Y-%m-%d').date() if raw else timezone.localdate()
    except ValueError:
        day = timezone.localdate()
    worker_pk = request.GET.get('worker')
    w_pk: Optional[int] = None
    if worker_pk not in (None, ''):
        try:
            w_pk = int(worker_pk)
        except ValueError:
            w_pk = None

    events = CalendarEvent.objects.select_related('assigned_worker').all()
    tasks = generate_tasks_from_calendar(events, day, worker_pk=w_pk)
    ids = [t.id for t in tasks]
    state_map = collect_state_map_for_ids(ids)
    merged = merge_task_state(tasks, state_map)
    workers = Worker.objects.all()
    wmap = {w.pk: w.name for w in workers}
    for row in merged:
        row['worker_name'] = wmap.get(row['task'].worker_pk, '')
    return render(
        request,
        'workforce/admin/tasks.html',
        {
            'day': day,
            'date_str': day.isoformat(),
            'merged_tasks': merged,
            'workers': workers,
            'filter_worker': w_pk,
        },
    )


@org_admin_required
def admin_task_report(request: HttpRequest) -> HttpResponse:
    """Detailed report of persisted task work (status, notes, photos, checklist)."""
    today = timezone.localdate()
    raw_from = request.GET.get('date_from') or ''
    raw_to = request.GET.get('date_to') or ''
    try:
        date_from = datetime.strptime(raw_from, '%Y-%m-%d').date() if raw_from else today - timedelta(days=30)
    except ValueError:
        date_from = today - timedelta(days=30)
    try:
        date_to = datetime.strptime(raw_to, '%Y-%m-%d').date() if raw_to else today
    except ValueError:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    status_filter = request.GET.get('status') or ''
    valid_statuses = {c for c, _ in TaskState.Status.choices}
    if status_filter not in valid_statuses:
        status_filter = ''

    worker_pk = request.GET.get('worker')
    w_pk: Optional[int] = None
    if worker_pk not in (None, ''):
        try:
            w_pk = int(worker_pk)
        except ValueError:
            w_pk = None

    qs = TaskState.objects.filter(
        last_saved_at__date__gte=date_from,
        last_saved_at__date__lte=date_to,
    ).order_by('-last_saved_at')

    if status_filter:
        qs = qs.filter(status=status_filter)

    if w_pk is not None:
        eids = list(
            CalendarEvent.objects.filter(assigned_worker_id=w_pk).values_list('pk', flat=True),
        )
        if not eids:
            qs = qs.none()
        else:
            q = Q()
            for eid in eids:
                q |= Q(derived_task_id__startswith=f'{eid}::')
            qs = qs.filter(q)

    summary = {
        'total': qs.count(),
        'completed': qs.filter(status=TaskState.Status.COMPLETED).count(),
        'in_progress': qs.filter(status=TaskState.Status.IN_PROGRESS).count(),
        'scheduled': qs.filter(status=TaskState.Status.SCHEDULED).count(),
    }

    paginator = Paginator(qs, 30)
    page = request.GET.get('page') or 1
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    rows = _enrich_task_states_for_report(list(page_obj.object_list))
    workers = Worker.objects.all()
    q = request.GET.copy()
    q.pop('page', None)
    pagination_qs = q.urlencode()
    return render(
        request,
        'workforce/admin/task_report.html',
        {
            'rows': rows,
            'page_obj': page_obj,
            'paginator': paginator,
            'summary': summary,
            'date_from': date_from,
            'date_to': date_to,
            'date_from_str': date_from.isoformat(),
            'date_to_str': date_to.isoformat(),
            'status_filter': status_filter,
            'workers': workers,
            'filter_worker': w_pk,
            'pagination_qs': pagination_qs,
        },
    )


@org_admin_required
def admin_workers(request: HttpRequest) -> HttpResponse:
    workers = Worker.objects.annotate(event_count=Count('events')).order_by('name')
    return render(request, 'workforce/admin/workers.html', {'workers': workers})


@org_admin_required
def admin_worker_invites(request: HttpRequest) -> HttpResponse:
    invites = WorkerInvitation.objects.select_related('created_by', 'claimed_by').order_by('-created_at')
    return render(request, 'workforce/admin/worker_invites.html', {'invites': invites})


@org_admin_required
def admin_worker_invite_create(request: HttpRequest) -> HttpResponse:
    form = WorkerInvitationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        inv = form.save(commit=False)
        inv.created_by = request.user
        inv.save()
        messages.success(
            request,
            f'Registration created. Share code {inv.invite_code} with {inv.name}.',
        )
        return redirect('workforce:admin_worker_invites')
    return render(request, 'workforce/admin/worker_invite_form.html', {'form': form})


@org_admin_required
def admin_worker_detail(request: HttpRequest, pk: int) -> HttpResponse:
    worker = get_object_or_404(Worker, pk=pk)
    return render(request, 'workforce/admin/worker_detail.html', {'worker': worker})


@org_admin_required
def admin_import(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST' and request.FILES.get('file'):
        f = request.FILES['file']
        data = f.read()
        rows, errors = parse_uploaded_file(f.name, data)
        if errors and not rows:
            for e in errors:
                messages.error(request, e)
        elif errors:
            for e in errors:
                messages.warning(request, e)
        if rows:
            created = create_events_from_import(rows)
            messages.success(request, f'Imported {len(created)} activities.')
        cy = request.POST.get('cal_year')
        cm = request.POST.get('cal_month')
        cs = request.POST.get('cal_selected')
        if cy and cm and cs:
            return redirect(
                f'{reverse("workforce:admin_calendar_list")}?year={cy}&month={cm}&selected={cs}',
            )
        return redirect('workforce:admin_import')
    return render(request, 'workforce/admin/import.html')


@worker_required
def worker_my_tasks(request: HttpRequest) -> HttpResponse:
    worker = get_object_or_404(Worker, user=request.user)
    day_raw = request.GET.get('date') or ''
    try:
        day = datetime.strptime(day_raw, '%Y-%m-%d').date() if day_raw else timezone.localdate()
    except ValueError:
        day = timezone.localdate()

    events = CalendarEvent.objects.select_related('assigned_worker').all()
    tasks = generate_tasks_from_calendar(events, day, worker_pk=worker.pk)
    ids = [t.id for t in tasks]
    state_map = collect_state_map_for_ids(ids)
    merged = merge_task_state(tasks, state_map)
    return render(
        request,
        'workforce/worker/my_tasks.html',
        {'merged_tasks': merged, 'day': day, 'date_str': day.isoformat()},
    )


@worker_required
def worker_schedule(request: HttpRequest) -> HttpResponse:
    worker = get_object_or_404(Worker, user=request.user)
    now = timezone.localdate()
    try:
        y = int(request.GET.get('year') or now.year)
        m = int(request.GET.get('month') or now.month)
    except ValueError:
        y, m = now.year, now.month
    if m < 1:
        m, y = 12, y - 1
    if m > 12:
        m, y = 1, y + 1

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(y, m)
    events = CalendarEvent.objects.select_related('assigned_worker').all()

    grid: List[List[Dict[str, Any]]] = []
    for week in weeks:
        row = []
        for d in week:
            if d.month != m:
                row.append({'day': None, 'in_month': False, 'count': 0, 'date_str': ''})
                continue
            tasks = generate_tasks_from_calendar(events, d, worker_pk=worker.pk)
            row.append(
                {
                    'day': d.day,
                    'in_month': True,
                    'count': len(tasks),
                    'date_str': d.isoformat(),
                },
            )
        grid.append(row)

    prev_m, prev_y = (m - 1, y) if m > 1 else (12, y - 1)
    next_m, next_y = (m + 1, y) if m < 12 else (1, y + 1)

    month_task_count = 0
    last_d = calendar.monthrange(y, m)[1]
    for d in range(1, last_d + 1):
        day = date(y, m, d)
        month_task_count += len(generate_tasks_from_calendar(events, day, worker_pk=worker.pk))

    subtitle = f'{calendar.month_name[m]} {y} · {month_task_count} tasks this month (you)'
    return render(
        request,
        'workforce/worker/schedule.html',
        {
            'year': y,
            'month': m,
            'month_name': calendar.month_name[m],
            'weeks': grid,
            'prev_year': prev_y,
            'prev_month': prev_m,
            'next_year': next_y,
            'next_month': next_m,
            'month_task_count': month_task_count,
            'subtitle': subtitle,
        },
    )


@worker_required
def worker_history(request: HttpRequest) -> HttpResponse:
    worker = get_object_or_404(Worker, user=request.user)
    states = TaskState.objects.filter(status=TaskState.Status.COMPLETED).order_by('-last_saved_at')
    rows: List[Dict[str, Any]] = []
    for st in states:
        parts = st.derived_task_id.split('::')
        if len(parts) != 2:
            continue
        try:
            eid = int(parts[0])
        except ValueError:
            continue
        ev = CalendarEvent.objects.filter(pk=eid, assigned_worker=worker).first()
        if not ev:
            continue
        rows.append({'state': st, 'event': ev, 'date_key': parts[1]})
    return render(request, 'workforce/worker/history.html', {'rows': rows})


@org_admin_required
def admin_profile(request: HttpRequest) -> HttpResponse:
    user = request.user
    prof = ensure_profile(user)
    user_form = UserAccountForm(request.POST or None, instance=user)
    photo_form = ProfilePhotoForm(
        request.POST or None,
        request.FILES or None,
        instance=prof,
    )
    if request.method == 'POST':
        u_ok = user_form.is_valid()
        p_ok = photo_form.is_valid()
        if u_ok and p_ok:
            user_form.save()
            photo_form.save()
            messages.success(request, 'Profile updated.')
            return redirect('workforce:admin_profile')
    return render(
        request,
        'workforce/admin/profile.html',
        {
            'user_form': user_form,
            'photo_form': photo_form,
            'profile': prof,
        },
    )


@worker_required
def worker_profile(request: HttpRequest) -> HttpResponse:
    worker = get_object_or_404(Worker, user=request.user)
    user = request.user
    prof = ensure_profile(user)
    user_form = UserAccountForm(request.POST or None, instance=user)
    photo_form = ProfilePhotoForm(
        request.POST or None,
        request.FILES or None,
        instance=prof,
    )
    worker_form = WorkerProfileForm(request.POST or None, instance=worker)
    if request.method == 'POST':
        u_ok = user_form.is_valid()
        p_ok = photo_form.is_valid()
        w_ok = worker_form.is_valid()
        if u_ok and p_ok and w_ok:
            user_form.save()
            photo_form.save()
            worker_form.save()
            messages.success(request, 'Profile updated.')
            return redirect('workforce:worker_profile')
    return render(
        request,
        'workforce/worker/profile.html',
        {
            'user_form': user_form,
            'photo_form': photo_form,
            'worker_form': worker_form,
            'worker': worker,
            'profile': prof,
        },
    )


@worker_required
def worker_task_detail(request: HttpRequest, event_id: int, date_key: str) -> HttpResponse:
    worker = get_object_or_404(Worker, user=request.user)
    ev = get_object_or_404(CalendarEvent, pk=event_id, assigned_worker=worker)
    try:
        day = parse_date_key(date_key)
    except (ValueError, IndexError):
        raise Http404('Invalid date') from None

    tasks = generate_tasks_from_calendar([ev], day, worker_pk=worker.pk)
    if not tasks:
        raise Http404('No task on this date for this event.')
    task = tasks[0]
    derived_id = task.id
    st = TaskState.objects.filter(derived_task_id=derived_id).first()

    checklist_keys = list(task.checklist or [])
    initial: Dict[str, Any] = {}
    if st:
        initial['status'] = st.status
        initial['notes'] = st.notes
        initial['photo_count'] = st.photo_count
    else:
        initial['status'] = TaskState.Status.SCHEDULED
        initial['notes'] = ''
        initial['photo_count'] = 0

    form = TaskStateUpdateForm(
        request.POST or None,
        initial=initial,
        checklist_keys=checklist_keys,
        checklist_done=st.checklist_done if st else {},
    )

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'add_photo':
            prev = TaskState.objects.filter(derived_task_id=derived_id).first()
            new_count = (prev.photo_count if prev else 0) + 1
            TaskState.objects.update_or_create(
                derived_task_id=derived_id,
                defaults={
                    'photo_count': new_count,
                    'status': prev.status if prev else TaskState.Status.SCHEDULED,
                    'notes': prev.notes if prev else '',
                    'checklist_done': prev.checklist_done if prev else {},
                },
            )
            messages.success(request, 'Photo added.')
            return redirect('workforce:worker_task_detail', event_id=event_id, date_key=date_key)

    if request.method == 'POST' and form.is_valid():
        action = request.POST.get('action', 'save')
        done: Dict[str, bool] = {}
        for i, _label in enumerate(checklist_keys):
            field = f'check_{i}'
            if field in form.fields and form.cleaned_data.get(field):
                done[str(i)] = True
        status_val = form.cleaned_data['status']
        if action == 'complete':
            status_val = TaskState.Status.COMPLETED
        elif action == 'draft':
            if status_val != TaskState.Status.COMPLETED:
                status_val = TaskState.Status.IN_PROGRESS
        photo_n = form.cleaned_data.get('photo_count') or 0
        TaskState.objects.update_or_create(
            derived_task_id=derived_id,
            defaults={
                'status': status_val,
                'notes': form.cleaned_data.get('notes') or '',
                'photo_count': photo_n,
                'checklist_done': done,
            },
        )
        messages.success(request, 'Task saved.')
        if action == 'complete':
            return redirect('workforce:worker_history')
        if action == 'draft':
            return redirect('workforce:worker_my_tasks')
        return redirect('workforce:worker_task_detail', event_id=event_id, date_key=date_key)

    pc = st.photo_count if st else 0
    photo_preview_range = list(range(min(pc, 4)))

    return render(
        request,
        'workforce/worker/task_detail.html',
        {
            'event': ev,
            'task': task,
            'derived_id': derived_id,
            'form': form,
            'date_key': date_key,
            'persist': st,
            'photo_preview_range': photo_preview_range,
        },
    )
