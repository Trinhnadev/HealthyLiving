# Generated by Django 4.2.7 on 2024-09-19 13:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0010_temporaryuser'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TemporaryUser',
        ),
    ]