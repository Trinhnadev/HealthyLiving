# Generated by Django 4.2.7 on 2024-05-03 14:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0011_product_status_store_status'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='message',
            options={'ordering': ['-updated', 'created']},
        ),
        migrations.AddField(
            model_name='store',
            name='address',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='store',
            name='phone',
            field=models.CharField(max_length=200, null=True),
        ),
    ]
