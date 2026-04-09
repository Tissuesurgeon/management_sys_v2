import secrets

from django.conf import settings
from django.db import models


def generate_worker_invite_code(length: int = 10) -> str:
    """Human-friendly code (no ambiguous 0/O, 1/I)."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class Profile(models.Model):
    class Role(models.TextChoices):
        ORG_ADMIN = 'org_admin', 'Organization admin'
        WORKER = 'worker', 'Worker'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.WORKER)
    photo = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True,
        help_text='Profile photo (shown in the app header).',
    )

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'


class Worker(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='worker',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    employee_id = models.CharField(max_length=64, blank=True)
    facility_location = models.CharField(max_length=200, blank=True)
    tasks_completed = models.PositiveIntegerField(default=0)
    avg_resolution_min = models.PositiveIntegerField(default=0)
    reliability = models.DecimalField(max_digits=5, decimal_places=2, default=100)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class WorkerInvitation(models.Model):
    """Pre-registration for workers: admin sets name and optional email / employee ID; worker redeems with code at signup."""

    invite_code = models.CharField(max_length=32, unique=True, db_index=True)
    email = models.EmailField(
        blank=True,
        help_text='If set, the worker must use this email when signing up.',
    )
    employee_id = models.CharField(
        max_length=64,
        blank=True,
        help_text='If set, the worker must enter this employee ID at signup.',
    )
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    facility_location = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='worker_invitations_created',
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='worker_invitations_claimed',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.invite_code})'

    def save(self, *args, **kwargs):
        if not self.invite_code:
            for _ in range(20):
                code = generate_worker_invite_code()
                if not WorkerInvitation.objects.filter(invite_code=code).exists():
                    self.invite_code = code
                    break
            else:  # pragma: no cover
                self.invite_code = generate_worker_invite_code(16)
        super().save(*args, **kwargs)


class CalendarEvent(models.Model):
    class Recurrence(models.TextChoices):
        NONE = 'none', 'None'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    class Color(models.TextChoices):
        BLUE = 'blue', 'Blue'
        GREEN = 'green', 'Green'
        ORANGE = 'orange', 'Orange'
        RED = 'red', 'Red'

    title = models.CharField(max_length=500)
    location = models.CharField(max_length=500, blank=True)
    start = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    assigned_worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name='events',
    )
    recurrence_type = models.CharField(
        max_length=20,
        choices=Recurrence.choices,
        default=Recurrence.NONE,
    )
    recurrence_end = models.DateField(null=True, blank=True)
    checklist = models.JSONField(default=list)
    color = models.CharField(
        max_length=20,
        choices=Color.choices,
        default=Color.BLUE,
    )

    class Meta:
        ordering = ['start']

    def __str__(self):
        return self.title


class TaskState(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'

    derived_task_id = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    notes = models.TextField(blank=True)
    checklist_done = models.JSONField(default=dict)
    photo_count = models.PositiveIntegerField(default=0)
    last_saved_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Task state'
        verbose_name_plural = 'Task states'

    def __str__(self):
        return self.derived_task_id
