import threading
from django.utils import timezone
from datetime import timedelta
from pytz import timezone as pytz_timezone
import time
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Event
import signal
import sys

# Múi giờ Việt Nam
VIETNAM_TZ = pytz_timezone('Asia/Ho_Chi_Minh')

# Flag to stop all threads if necessary
stop_threads = False

def send_reminder_email(event):
    participants = event.par.all()  # Suppose `par` is a ManyToMany field containing a list of participants
    subject = f"Reminder: '{event.title}' is starting soon!"
    message = f"""
    Dear Participant,

    The event '{event.title}' is about to start at {event.start_time.strftime('%Y-%m-%d %H:%M:%S')}.

    Location: {event.location}
    Please be ready!

    Best regards,
    Your Event Organizer
    """
    recipient_list = [participant.email for participant in participants]
    
    for email in recipient_list:
        send_mail(
            subject,
            message,
            'from@example.com',  # Sender email address
            [email],
            fail_silently=False,
        )

def send_event_delete_warning_email(event):
    host_email = event.host.email  # Assume `host` is the ForeignKey field to the event creator
    subject = f"Warning: '{event.title}' is about to be deleted!"
    message = f"""
    Dear {event.host.username},

    The event '{event.title}' at {event.location} is ending soon. The event will be deleted in 1 minute.

    Best regards,
    Your Event Organizer
    """
    
    send_mail(
        subject,
        message,
        'from@example.com',  # Sender email address
        [host_email],
        fail_silently=False,
    )

def countdown_to_end(event_end_time, event_title, event):
    global stop_threads
    current_time = timezone.now().astimezone(VIETNAM_TZ)
    time_to_delete = event_end_time + timedelta(minutes=1)
    warning_email_sent = False  # Flag to check for email alerts that have been sent

    while current_time < time_to_delete and not stop_threads:
        remaining_time = time_to_delete - current_time
        minutes_left = remaining_time.total_seconds() // 60  # Calculate the remaining minutes

        print(f"END [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - End time: {event_end_time.strftime('%Y-%m-%d %H:%M:%S')} - Minutes left before deletion: {int(minutes_left)} phút", flush=True)

        if minutes_left == 1 and not warning_email_sent:
            print(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - 1 minute left before the event is deleted. Sending email to host.", flush=True)
            send_event_delete_warning_email(event)
            warning_email_sent = True  # Mark that the email has been sent

        time.sleep(60)  # Stop the program for 1 minute
        current_time = timezone.now().astimezone(VIETNAM_TZ)

    print(f"[{timezone.now().astimezone(VIETNAM_TZ).strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' has been deleted.", flush=True)
    event.delete()

def countdown_timer(event_start_time, event_title, event):
    global stop_threads
    current_time = timezone.now().astimezone(VIETNAM_TZ)
    time_to_wait = event_start_time - timedelta(minutes=1)
    reminder_email_sent = False  # Flag to check reminder email has been sent

    while current_time < time_to_wait and not stop_threads:
        remaining_time = time_to_wait - current_time
        minutes_left = remaining_time.total_seconds() // 60  # Calculate the remaining minutes

        print(f"START [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - Start time: {event_start_time.strftime('%Y-%m-%d %H:%M:%S')} - Minutes left: {int(minutes_left)} phút", flush=True)

        if minutes_left == 1 and not reminder_email_sent:
            print(f"START [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - 1 minute left before the event starts. Sending email reminders.", flush=True)
            send_reminder_email(event)
            reminder_email_sent = True  # Mark that the email has been sent

        time.sleep(60)  # Stop the program for 1 minute
        current_time = timezone.now().astimezone(VIETNAM_TZ)

    if not stop_threads:
        countdown_to_end(event.end_time, event_title, event)

def check_approved_events():
    approved_events = Event.objects.filter(status='approved')

    for event in approved_events:
        event_start_time = event.start_time
        event_title = event.title
        countdown_thread = threading.Thread(target=countdown_timer, args=(event_start_time, event_title, event))
        countdown_thread.daemon = True  # Use daemon thread to automatically close when main program stops
        countdown_thread.start()

@receiver(post_save, sender=Event)
def start_countdown_for_new_event(sender, instance, **kwargs):
    print(f"Signal triggered for event: {instance.title} with status {instance.status}")
    if instance.status == 'approved':
        print(f"Approved event detected: {instance.title}")
        event_start_time = instance.start_time
        event_title = instance.title
        countdown_thread = threading.Thread(target=countdown_timer, args=(event_start_time, event_title, instance))
        countdown_thread.daemon = True  # Use daemon thread to automatically close when main program stops
        countdown_thread.start()

# Added signal handling to stop threads when the server is shut down
def signal_handler(signal, frame):
    global stop_threads
    stop_threads = True  # Mark all threads to stop
    print("Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)  #Handle Ctrl+C


