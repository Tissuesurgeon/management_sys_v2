# Generated manually — CalendarEvent → MaintenanceTask

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workforce', '0006_alter_calendarevent_description'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='CalendarEvent',
            new_name='MaintenanceTask',
        ),
        migrations.AlterField(
            model_name='maintenancetask',
            name='assigned_worker',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='maintenance_tasks',
                to='workforce.worker',
            ),
        ),
        migrations.AlterModelOptions(
            name='maintenancetask',
            options={
                'ordering': ['start'],
                'verbose_name': 'Maintenance task',
                'verbose_name_plural': 'Maintenance tasks',
            },
        ),
    ]
