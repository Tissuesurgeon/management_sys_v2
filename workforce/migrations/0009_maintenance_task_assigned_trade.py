# Generated manually — MaintenanceTask.assigned_worker → assigned_trade

from django.db import migrations, models


def copy_trade_from_worker(apps, schema_editor):
    MaintenanceTask = apps.get_model('workforce', 'MaintenanceTask')
    Worker = apps.get_model('workforce', 'Worker')
    for m in MaintenanceTask.objects.all():
        wid = getattr(m, 'assigned_worker_id', None)
        if wid:
            try:
                w = Worker.objects.get(pk=wid)
                m.assigned_trade = w.trade
            except Worker.DoesNotExist:
                m.assigned_trade = 'general_technician'
        else:
            m.assigned_trade = 'general_technician'
        m.save(update_fields=['assigned_trade'])


class Migration(migrations.Migration):

    dependencies = [
        ('workforce', '0008_worker_trade'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancetask',
            name='assigned_trade',
            field=models.CharField(
                choices=[
                    ('plumber', 'Plumber'),
                    ('electrician', 'Electrician'),
                    ('general_technician', 'General technician'),
                ],
                default='general_technician',
                help_text='All technicians with this trade see the task until it is completed.',
                max_length=32,
            ),
        ),
        migrations.RunPython(copy_trade_from_worker, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='maintenancetask',
            name='assigned_worker',
        ),
    ]
