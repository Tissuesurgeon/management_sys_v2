"""Delete all maintenance tasks and persisted task state; reset worker task aggregates."""

from django.core.management.base import BaseCommand
from django.db import transaction

from workforce.models import MaintenanceTask, TaskState, Worker


class Command(BaseCommand):
    help = (
        'Remove all MaintenanceTask and TaskState rows, and reset Worker '
        'tasks_completed / avg_resolution_min / reliability.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not ask for confirmation.',
        )

    def handle(self, *args, **options):
        if not options['no_input']:
            self.stdout.write(
                self.style.WARNING(
                    'This will delete ALL maintenance tasks and task state, '
                    'and reset worker task counters.',
                ),
            )
            confirm = input('Type YES to continue: ')
            if confirm.strip() != 'YES':
                self.stdout.write(self.style.ERROR('Aborted.'))
                return

        with transaction.atomic():
            n_state = TaskState.objects.count()
            n_tasks = MaintenanceTask.objects.count()
            TaskState.objects.all().delete()
            MaintenanceTask.objects.all().delete()
            Worker.objects.update(
                tasks_completed=0,
                avg_resolution_min=0,
                reliability=100,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Deleted {n_state} task state row(s), {n_tasks} maintenance task(s). '
                'Worker task counters reset.',
            ),
        )
