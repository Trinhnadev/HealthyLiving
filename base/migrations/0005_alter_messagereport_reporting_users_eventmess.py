# Generated by Django 4.2.7 on 2024-04-05 08:51

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_rename_reporting_user_messagereport_reporting_users'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagereport',
            name='reporting_users',
            field=models.ManyToManyField(blank=True, related_name='reports_made', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='EventMess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(blank=True, null=True, upload_to='')),
                ('body', models.TextField()),
                ('updated', models.DateTimeField(auto_now=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='base.event')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['updated', '-created'],
            },
        ),
    ]
