# # myproject/celery.py
# from __future__ import absolute_import, unicode_literals
# import os
# from celery import Celery 
# from celery.schedules import crontab

# # set the default Django settings module for the 'celery' program.
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studybud.settings')

# app = Celery('studybud')

# # Using a string here means the worker doesn't have to serialize
# # the configuration object to child processes.
# # - namespace='CELERY' means all celery-related configuration keys
# #   should have a `CELERY_` prefix.
# app.config_from_object('django.conf:settings', namespace='CELERY')

# # Load task modules from all registered Django app configs.
# app.autodiscover_tasks()

# app.conf.beat_schedule = {
#     'notify-event-start-every-minute': {
#         'task': 'base.tasks.notify_event_start',
#         'schedule': crontab(minute='*'),
#     },
#     'delete-past-events-every-minute': {
#         'task': 'base.tasks.delete_past_events',
#         'schedule': crontab(minute='*'),
#     },
# }

# @app.task(bind=True)
# def debug_task(self):
#     print(f'Request: {self.request!r}')
