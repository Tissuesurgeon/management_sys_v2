from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workforce', '0004_worker_password_reset_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
    ]
