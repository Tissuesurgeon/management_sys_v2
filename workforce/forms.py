from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import formset_factory
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone as dj_tz

from workforce.models import (
    Gender,
    MaintenanceTask,
    Profile,
    TaskState,
    Worker,
    WorkerInvitation,
    WorkerPasswordResetCode,
)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

# Tailwind — aligned with Management_sys form controls
_IN = 'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500'
_TA = 'w-full rounded-xl border-0 bg-slate-100 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400'
_SEL = 'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-500'


def _configure_assigned_trade_field(field):
    """Which trade pool can see and complete this task (all matching technicians)."""
    field.label = 'Assigned trade'
    field.help_text = 'Every technician with this trade sees the task until someone completes it.'


class SignupForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=Profile.Role.choices,
        initial=Profile.Role.WORKER,
        label='Account type',
    )
    trade = forms.ChoiceField(
        choices=[('', 'Select trade')] + list(Worker.Trade.choices),
        required=False,
        label='Trade',
        help_text='Required for workers (plumber, electrician, or general technician).',
    )
    worker_name = forms.CharField(
        max_length=200,
        required=False,
        label='Full name (workers)',
        help_text='Required when registering as a worker (unless you use a registration code from your facility manager).',
    )
    employee_id = forms.CharField(max_length=64, required=False, label='Employee ID')
    registration_code = forms.CharField(
        max_length=64,
        required=False,
        label='Registration code',
        help_text='If your organization gave you a code, enter it here.',
        widget=forms.TextInput(
            attrs={
                'class': _IN,
                'placeholder': 'e.g. A1B2C3D4E5',
                'autocomplete': 'off',
            },
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            [
                'username',
                'email',
                'password1',
                'password2',
                'role',
                'trade',
                'registration_code',
                'worker_name',
                'employee_id',
            ],
        )

    def clean(self):
        data = super().clean()
        role = data.get('role')
        name = (data.get('worker_name') or '').strip()
        code = (data.get('registration_code') or '').strip()

        if role == Profile.Role.WORKER and code:
            inv = WorkerInvitation.objects.filter(
                invite_code__iexact=code,
                claimed_at__isnull=True,
            ).first()
            if not inv:
                self.add_error('registration_code', 'Invalid or already used registration code.')
                return data
            email = (data.get('email') or '').strip()
            emp = (data.get('employee_id') or '').strip()
            email_ok = not inv.email or email.lower() == inv.email.lower()
            emp_ok = not inv.employee_id or emp == inv.employee_id.strip()
            if not email_ok:
                self.add_error(
                    'email',
                    'Use the same email address your facility manager registered for this invite.',
                )
            if not emp_ok:
                self.add_error(
                    'employee_id',
                    'Enter the employee ID your facility manager registered for this invite.',
                )
            if email_ok and emp_ok:
                self._invitation = inv
                if not name:
                    data['worker_name'] = inv.name
        elif role == Profile.Role.WORKER and not name:
            self.add_error('worker_name', 'Full name is required for worker accounts.')

        if role == Profile.Role.WORKER:
            inv = getattr(self, '_invitation', None)
            trade = (data.get('trade') or '').strip()
            if inv and inv.trade:
                if trade and trade != inv.trade:
                    self.add_error(
                        'trade',
                        'This registration code is for a different trade.',
                    )
                else:
                    data['trade'] = inv.trade
            elif not trade:
                self.add_error('trade', 'Select your trade.')
            else:
                data['trade'] = trade

        return data


class PasswordResetWithCodeForm(forms.Form):
    username = forms.CharField(
        label='Username',
        max_length=150,
        widget=forms.TextInput(attrs={'class': _IN, 'autocomplete': 'username'}),
    )
    code = forms.CharField(
        label='Reset code',
        max_length=64,
        widget=forms.TextInput(attrs={'class': _IN, 'autocomplete': 'off'}),
    )
    password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={'class': _IN, 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={'class': _IN, 'autocomplete': 'new-password'}),
    )

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        username = (data.get('username') or '').strip()
        code = (data.get('code') or '').strip()
        p1 = data.get('password1')
        p2 = data.get('password2')
        if not username or not code:
            return data
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.add_error('username', 'No account with that username.')
            return data
        prof = Profile.objects.filter(user=user).first()
        if not prof or prof.role != Profile.Role.WORKER:
            self.add_error(
                'username',
                'Password reset with a code is only available for worker accounts.',
            )
            return data
        now = dj_tz.now()
        row = WorkerPasswordResetCode.objects.filter(
            user=user,
            code__iexact=code,
            used_at__isnull=True,
            expires_at__gt=now,
        ).first()
        if not row:
            self.add_error('code', 'Invalid, expired, or already used code.')
            return data
        self._reset_row = row
        self._user = user
        if p1 != p2:
            self.add_error('password2', 'The two password fields do not match.')
            return data
        if p1:
            try:
                validate_password(p1, user=user)
            except ValidationError as exc:
                for err in exc.messages:
                    self.add_error('password1', err)
        return data


class MaintenanceTaskForm(forms.ModelForm):
    checklist_text = forms.CharField(
        label='Task checklist (one item per line)',
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'placeholder': 'One item per line',
                'class': _TA,
            },
        ),
        required=False,
    )

    class Meta:
        model = MaintenanceTask
        fields = [
            'title',
            'description',
            'location',
            'start',
            'duration_minutes',
            'assigned_trade',
            'color',
        ]
        labels = {
            'start': 'Date',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': _IN}),
            'description': forms.Textarea(
                attrs={
                    'class': _TA,
                    'rows': 4,
                    'placeholder': 'Instructions or context shown on the task detail screen',
                },
            ),
            'location': forms.TextInput(attrs={'class': _IN}),
            'start': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': _IN},
                format='%Y-%m-%dT%H:%M',
            ),
            'duration_minutes': forms.HiddenInput(),
            'assigned_trade': forms.Select(attrs={'class': _SEL}),
            'color': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            [
                'title',
                'description',
                'checklist_text',
                'location',
                'start',
                'duration_minutes',
                'assigned_trade',
                'color',
            ],
        )
        self.fields['start'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
        ]
        _configure_assigned_trade_field(self.fields['assigned_trade'])
        if self.instance.pk:
            if self.instance.checklist:
                self.initial['checklist_text'] = '\n'.join(self.instance.checklist)
            if self.instance.start:
                self.initial['start'] = dj_tz.localtime(self.instance.start).strftime(
                    '%Y-%m-%dT%H:%M',
                )

    def clean_checklist_text(self):
        raw = self.cleaned_data.get('checklist_text') or ''
        lines = [x.strip() for x in raw.splitlines() if x.strip()]
        return lines if lines else ['Verify completion']

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('duration_minutes') is None:
            cleaned['duration_minutes'] = 60
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.checklist = self.cleaned_data['checklist_text']
        if commit:
            obj.save()
        return obj


def make_maintenance_task_bulk_row_form(first_day: date, last_day: date):
    """Single row for bulk month create; ``first_day`` / ``last_day`` bound the allowed ``start`` date."""

    class MaintenanceTaskBulkRowForm(forms.Form):
        title = forms.CharField(
            max_length=500,
            required=False,
            widget=forms.TextInput(attrs={'class': _IN, 'placeholder': 'Task title'}),
        )
        description = forms.CharField(
            required=False,
            widget=forms.Textarea(
                attrs={
                    'class': _TA,
                    'rows': 2,
                    'placeholder': 'Optional description',
                },
            ),
        )
        checklist_text = forms.CharField(
            label='Checklist (one line per item)',
            required=False,
            widget=forms.Textarea(
                attrs={
                    'rows': 2,
                    'placeholder': 'One item per line',
                    'class': _TA,
                },
            ),
        )
        location = forms.CharField(
            max_length=500,
            required=False,
            widget=forms.TextInput(attrs={'class': _IN, 'placeholder': 'Location'}),
        )
        start = forms.DateTimeField(
            required=False,
            widget=forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': _IN},
                format='%Y-%m-%dT%H:%M',
            ),
        )
        duration_minutes = forms.IntegerField(
            min_value=1,
            max_value=24 * 60,
            initial=60,
            required=False,
            widget=forms.HiddenInput(),
        )
        assigned_trade = forms.ChoiceField(
            choices=Worker.Trade.choices,
            required=False,
            widget=forms.Select(attrs={'class': _SEL}),
        )
        recurrence_type = forms.ChoiceField(
            choices=MaintenanceTask.Recurrence.choices,
            initial=MaintenanceTask.Recurrence.NONE,
            required=False,
            widget=forms.HiddenInput(),
        )
        color = forms.ChoiceField(
            choices=MaintenanceTask.Color.choices,
            initial=MaintenanceTask.Color.BLUE,
            required=False,
            widget=forms.HiddenInput(),
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['start'].input_formats = [
                '%Y-%m-%dT%H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
            ]
            _configure_assigned_trade_field(self.fields['assigned_trade'])

        def clean_checklist_text(self):
            raw = self.cleaned_data.get('checklist_text') or ''
            lines = [x.strip() for x in raw.splitlines() if x.strip()]
            return lines if lines else ['Verify completion']

        def clean_start(self):
            title = (self.cleaned_data.get('title') or '').strip()
            st = self.cleaned_data.get('start')
            if not title:
                return st
            if not st:
                return st
            if dj_tz.is_naive(st):
                st = dj_tz.make_aware(st, dj_tz.get_current_timezone())
            d = dj_tz.localtime(st).date()
            if not (first_day <= d <= last_day):
                raise ValidationError(
                    'Start date must fall within the selected month.',
                )
            return st

        def clean(self):
            cleaned = super().clean()
            title = (cleaned.get('title') or '').strip()
            if not title:
                return cleaned
            if not cleaned.get('start'):
                self.add_error('start', 'Start date and time are required when a title is set.')
            if not cleaned.get('assigned_trade'):
                self.add_error('assigned_trade', 'Select a trade when a title is set.')
            dm = cleaned.get('duration_minutes')
            if dm is None:
                cleaned['duration_minutes'] = 60
            return cleaned

    return MaintenanceTaskBulkRowForm


def maintenance_task_bulk_formset_factory(first_day: date, last_day: date, *, extra: int = 1):
    RowForm = make_maintenance_task_bulk_row_form(first_day, last_day)
    return formset_factory(
        RowForm,
        extra=extra,
        min_num=0,
        max_num=50,
        validate_max=True,
        can_delete=False,
    )


class WorkerInvitationForm(forms.ModelForm):
    class Meta:
        model = WorkerInvitation
        fields = [
            'email',
            'employee_id',
            'name',
            'gender',
            'trade',
        ]
        labels = {
            'gender': 'Gender',
        }
        widgets = {
            'email': forms.EmailInput(attrs={'class': _IN, 'placeholder': 'worker@company.com (optional)'}),
            'employee_id': forms.TextInput(attrs={'class': _IN, 'placeholder': 'e.g. 4812-X (optional)'}),
            'name': forms.TextInput(attrs={'class': _IN}),
            'gender': forms.Select(attrs={'class': _SEL}),
            'trade': forms.Select(attrs={'class': _SEL}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['trade'].required = False
        self.fields['trade'].choices = [
            ('', 'Any trade (optional)'),
        ] + list(Worker.Trade.choices)
        self.fields['gender'].required = False
        self.fields['gender'].choices = [
            ('', 'Select gender'),
        ] + list(Gender.choices)

    def clean_trade(self):
        t = self.cleaned_data.get('trade')
        return t if t else None

    def clean_gender(self):
        g = self.cleaned_data.get('gender')
        return g if g else ''


class UserAccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': _IN, 'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'class': _IN, 'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'class': _IN, 'autocomplete': 'email'}),
        }


class ProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['photo']
        widgets = {
            'photo': forms.ClearableFileInput(
                attrs={
                    'class': _IN,
                    'accept': 'image/jpeg,image/png,image/webp',
                },
            ),
        }

    def clean_photo(self):
        f = self.cleaned_data.get('photo')
        if f is False:
            return False
        if not f or getattr(f, 'name', '') == '':
            return f
        if getattr(f, 'size', 0) > 2 * 1024 * 1024:
            raise ValidationError('Image must be under 2 MB.')
        if Image is not None:
            f.seek(0)
            try:
                with Image.open(f) as im:
                    im.verify()
            except Exception as exc:  # noqa: BLE001 — surface bad uploads clearly
                raise ValidationError('Please upload a valid image file.') from exc
            f.seek(0)
        return f


class WorkerProfileForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = ['name', 'gender', 'title', 'department', 'employee_id', 'facility_location', 'trade']
        labels = {
            'title': 'Job title',
            'gender': 'Gender',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': _IN}),
            'gender': forms.Select(attrs={'class': _SEL}),
            'title': forms.TextInput(attrs={'class': _IN}),
            'department': forms.TextInput(attrs={'class': _IN}),
            'employee_id': forms.TextInput(attrs={'class': _IN}),
            'facility_location': forms.TextInput(attrs={'class': _IN}),
            'trade': forms.Select(attrs={'class': _SEL}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gender'].required = False
        self.fields['gender'].choices = [
            ('', 'Select gender'),
        ] + list(Gender.choices)

    def clean_gender(self):
        g = self.cleaned_data.get('gender')
        return g if g else ''


class TaskStateUpdateForm(forms.Form):
    status = forms.ChoiceField(
        choices=TaskState.Status.choices,
        widget=forms.Select(attrs={'class': _SEL}),
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': _TA}),
        required=False,
    )

    def __init__(self, *args, checklist_keys=None, checklist_done=None, **kwargs):
        super().__init__(*args, **kwargs)
        checklist_keys = checklist_keys or []
        done = checklist_done or {}
        for i, key in enumerate(checklist_keys):
            name = f'check_{i}'
            self.fields[name] = forms.BooleanField(
                required=False,
                label=key,
                initial=bool(done.get(str(i)) or done.get(i)),
                widget=forms.CheckboxInput(
                    attrs={'class': 'h-4 w-4 rounded border-slate-300 text-slate-800 focus:ring-slate-500'},
                ),
            )
