"""Optional demo data for local development."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from workforce.models import CalendarEvent, Worker


class Command(BaseCommand):
    help = 'Create minimal demo workers and calendar events'

    def handle(self, *args, **options):
        w1, _ = Worker.objects.get_or_create(
            name='Alex Chen',
            defaults={
                'title': 'Technician',
                'department': 'Maintenance',
                'employee_id': 'E100',
            },
        )
        w2, _ = Worker.objects.get_or_create(
            name='Jamie Rivera',
            defaults={
                'title': 'Lead',
                'department': 'Maintenance',
                'employee_id': 'E101',
            },
        )
        start = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        CalendarEvent.objects.get_or_create(
            title='HVAC inspection — Building A',
            start=start,
            assigned_worker=w1,
            defaults={
                'location': 'Building A',
                'duration_minutes': 90,
                'recurrence_type': CalendarEvent.Recurrence.WEEKLY,
                'checklist': ['Inspect filters', 'Log readings'],
                'color': CalendarEvent.Color.BLUE,
            },
        )
        CalendarEvent.objects.get_or_create(
            title='Generator test',
            start=start + timedelta(days=1, hours=2),
            assigned_worker=w2,
            defaults={
                'location': 'Plant room',
                'duration_minutes': 45,
                'recurrence_type': CalendarEvent.Recurrence.MONTHLY,
                'checklist': ['Run test cycle', 'Verify logs'],
                'color': CalendarEvent.Color.GREEN,
            },
        )
        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
