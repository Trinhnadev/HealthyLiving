# Generated by Django 4.2.7 on 2024-04-05 09:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0008_eventmessage_delete_eventmess'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventmessage',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='base.event'),
        ),
    ]
