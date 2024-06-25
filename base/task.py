# events/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from .models import Event, Invitation





@shared_task
def notify_event_start():
    now = timezone.now()
    upcoming_events = Event.objects.filter(start_time__lte=now + timezone.timedelta(minutes=1), start_time__gt=now)
    for event in upcoming_events:
        invitations = event.invitations.all()
        for invitation in invitations:
            if invitation.accepted:
                send_mail(
                    'Event Starting Soon',
                    f'The event "{event.title}" is starting in 1 minute.',
                    'from@example.com',
                    [invitation.invitee.email],
                )

@shared_task
def delete_past_events():
    now = timezone.now()
    past_events = Event.objects.filter(end_time__lt=now)
    for event in past_events:
        send_mail(
            'Event Deleted',
            f'The event "{event.title}" has ended and has been deleted.',
            'from@example.com',
            [event.creator.email],
        )
        event.delete()
