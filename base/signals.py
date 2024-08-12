import threading
from django.utils import timezone
from datetime import timedelta
from pytz import timezone as pytz_timezone
import time
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Event

# Múi giờ Việt Nam
VIETNAM_TZ = pytz_timezone('Asia/Ho_Chi_Minh')

def send_reminder_email(event):
    participants = event.par.all()  # Giả sử `par` là trường ManyToMany chứa danh sách người tham gia
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
            'from@example.com',  # Địa chỉ email người gửi
            [email],
            fail_silently=False,
        )

def send_event_delete_warning_email(event):
    host_email = event.host.email  # Giả sử `host` là trường ForeignKey đến người tạo sự kiện
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
        'from@example.com',  # Địa chỉ email người gửi
        [host_email],
        fail_silently=False,
    )

def countdown_to_end(event_end_time, event_title, event):
    current_time = timezone.now().astimezone(VIETNAM_TZ)
    time_to_delete = event_end_time + timedelta(minutes=1)
    warning_email_sent = False  # Cờ để kiểm tra email cảnh báo đã được gửi

    while current_time < time_to_delete:
        remaining_time = time_to_delete - current_time
        minutes_left = remaining_time.total_seconds() // 60  # Tính số phút còn lại

        # Hiển thị thông tin trên một dòng duy nhất
        print(f"END [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - End time: {event_end_time.strftime('%Y-%m-%d %H:%M:%S')} - Minutes left before deletion: {int(minutes_left)} phút", flush=True)

        if minutes_left == 1 and not warning_email_sent:
            print(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - Còn 1 phút trước khi sự kiện bị xóa. Sending email to host.", flush=True)
            send_event_delete_warning_email(event)
            warning_email_sent = True  # Đánh dấu rằng email đã được gửi

        time.sleep(60)  # Dừng chương trình trong 1 phút
        current_time = timezone.now().astimezone(VIETNAM_TZ)

    # Xóa sự kiện sau khi đã hết thời gian
    print(f"[{timezone.now().astimezone(VIETNAM_TZ).strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' đã bị xóa.", flush=True)
    event.delete()

def countdown_timer(event_start_time, event_title, event):
    current_time = timezone.now().astimezone(VIETNAM_TZ)
    time_to_wait = event_start_time - timedelta(minutes=1)
    reminder_email_sent = False  # Cờ để kiểm tra email nhắc nhở đã được gửi

    while current_time < time_to_wait:
        remaining_time = time_to_wait - current_time
        minutes_left = remaining_time.total_seconds() // 60  # Tính số phút còn lại

        # Hiển thị thông tin trên một dòng duy nhất
        print(f"START [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - Start time: {event_start_time.strftime('%Y-%m-%d %H:%M:%S')} - Minutes left: {int(minutes_left)} phút", flush=True)

        if minutes_left == 1 and not reminder_email_sent:
            print(f"START [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - Còn 1 phút trước khi sự kiện bắt đầu. Sending email reminders.", flush=True)
            send_reminder_email(event)
            reminder_email_sent = True  # Đánh dấu rằng email đã được gửi

        time.sleep(60)  # Dừng chương trình trong 1 phút
        current_time = timezone.now().astimezone(VIETNAM_TZ)

    # Bắt đầu đếm ngược đến khi xóa sự kiện sau khi sự kiện kết thúc
    countdown_to_end(event.end_time, event_title, event)

def check_approved_events():
    approved_events = Event.objects.filter(status='approved')

    for event in approved_events:
        event_start_time = event.start_time
        event_title = event.title
        countdown_thread = threading.Thread(target=countdown_timer, args=(event_start_time, event_title, event))
        countdown_thread.start()

@receiver(post_save, sender=Event)
def start_countdown_for_new_event(sender, instance, **kwargs):
    print(f"Signal triggered for event: {instance.title} with status {instance.status}")
    if instance.status == 'approved':
        print(f"Approved event detected: {instance.title}")
        event_start_time = instance.start_time
        event_title = instance.title
        countdown_thread = threading.Thread(target=countdown_timer, args=(event_start_time, event_title, instance))
        countdown_thread.start()  # Bắt đầu luồng
