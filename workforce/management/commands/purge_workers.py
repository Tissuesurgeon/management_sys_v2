"""Delete field technician accounts and related data (destructive)."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from workforce.models import Profile, TaskState

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Delete all users with the field technician role (profile.worker). '
        'This CASCADE-deletes their Worker rows. Maintenance tasks are keyed by trade, not worker, and are not removed. '
        'Facility manager (org_admin) accounts are kept. '
        'Deletes all TaskState rows first to avoid orphaned completion records. '
        'Requires --yes to run.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Confirm you understand this is irreversible.',
        )

    def handle(self, *args, **options):
        if not options['yes']:
            self.stderr.write(
                self.style.ERROR(
                    'Refusing to run without --yes. '
                    'This deletes technician users, their Worker rows, and all TaskState rows (maintenance tasks remain).',
                ),
            )
            return

        ts_n = TaskState.objects.count()
        TaskState.objects.all().delete()
        self.stdout.write(self.style.WARNING(f'Deleted {ts_n} TaskState row(s).'))

        qs = User.objects.filter(profile__role=Profile.Role.WORKER).exclude(is_superuser=True)
        n = qs.count()
        qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f'Deleted {n} user account(s) with field technician role (and CASCADE: Worker rows).',
            ),
        )
