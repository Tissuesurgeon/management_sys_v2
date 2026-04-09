from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone as dj_tz

from workforce.models import CalendarEvent, Profile, TaskState, Worker, WorkerInvitation

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

# Tailwind — aligned with Management_sys form controls
_IN = 'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500'
_TA = 'w-full rounded-xl border-0 bg-slate-100 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400'
_SEL = 'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-500'


class SignupForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=Profile.Role.choices,
        initial=Profile.Role.WORKER,
        label='Role',
    )
    worker_name = forms.CharField(
        max_length=200,
        required=False,
        label='Full name (workers)',
        help_text='Required when registering as a worker (unless you use an admin invite code).',
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
                    'Use the same email address your administrator registered for this invite.',
                )
            if not emp_ok:
                self.add_error(
                    'employee_id',
                    'Enter the employee ID your administrator registered for this invite.',
                )
            if email_ok and emp_ok:
                self._invitation = inv
                if not name:
                    data['worker_name'] = inv.name
        elif role == Profile.Role.WORKER and not name:
            self.add_error('worker_name', 'Full name is required for worker accounts.')
        return data


class CalendarEventForm(forms.ModelForm):
    checklist_text = forms.CharField(
        label='Checklist (one per line)',
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
        model = CalendarEvent
        fields = [
            'title',
            'location',
            'start',
            'duration_minutes',
            'assigned_worker',
            'recurrence_type',
            'recurrence_end',
            'color',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': _IN}),
            'location': forms.TextInput(attrs={'class': _IN}),
            'start': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': _IN},
                format='%Y-%m-%dT%H:%M',
            ),
            'duration_minutes': forms.NumberInput(attrs={'class': _IN, 'min': 1}),
            'assigned_worker': forms.Select(attrs={'class': _SEL}),
            'recurrence_type': forms.Select(attrs={'class': _SEL}),
            'recurrence_end': forms.DateInput(attrs={'type': 'date', 'class': _IN}),
            'color': forms.Select(attrs={'class': _SEL}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
        ]
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

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.checklist = self.cleaned_data['checklist_text']
        if commit:
            obj.save()
        return obj


class WorkerInvitationForm(forms.ModelForm):
    class Meta:
        model = WorkerInvitation
        fields = [
            'email',
            'employee_id',
            'name',
            'title',
            'department',
            'facility_location',
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'class': _IN, 'placeholder': 'worker@company.com (optional)'}),
            'employee_id': forms.TextInput(attrs={'class': _IN, 'placeholder': 'e.g. 4812-X (optional)'}),
            'name': forms.TextInput(attrs={'class': _IN}),
            'title': forms.TextInput(attrs={'class': _IN}),
            'department': forms.TextInput(attrs={'class': _IN}),
            'facility_location': forms.TextInput(attrs={'class': _IN}),
        }


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
        fields = ['name', 'title', 'department', 'employee_id', 'facility_location']
        widgets = {
            'name': forms.TextInput(attrs={'class': _IN}),
            'title': forms.TextInput(attrs={'class': _IN}),
            'department': forms.TextInput(attrs={'class': _IN}),
            'employee_id': forms.TextInput(attrs={'class': _IN}),
            'facility_location': forms.TextInput(attrs={'class': _IN}),
        }


class TaskStateUpdateForm(forms.Form):
    status = forms.ChoiceField(
        choices=TaskState.Status.choices,
        widget=forms.Select(attrs={'class': _SEL}),
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': _TA}),
        required=False,
    )
    photo_count = forms.IntegerField(
        min_value=0,
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': _IN, 'min': 0}),
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
