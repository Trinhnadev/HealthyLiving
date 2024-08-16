# Generated by Django 4.2.7 on 2024-08-15 04:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_share_content_share_likes_sharecomment'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to='videos/'),
        ),
        migrations.AlterField(
            model_name='chat',
            name='content',
            field=models.TextField(blank=True, null=True),
        ),
    ]
