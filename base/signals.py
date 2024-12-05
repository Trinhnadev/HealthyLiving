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

# Hàm gửi email nhắc nhở
def send_reminder_email(event):
    participants = event.par.all()  # `par` là trường ManyToMany chứa danh sách người tham gia
    recipient_list = [participant.email for participant in participants if participant.email]  # Lọc chỉ người có email hợp lệ

    if not recipient_list:
        print(f"No participants found for event: {event.title}")
        return

    subject = f"Reminder: '{event.title}' is starting soon!"
    message = f"""
    Dear Participant,

    The event '{event.title}' is about to start at {event.start_time.strftime('%Y-%m-%d %H:%M:%S')}.
    
    Location: {event.location}
    Please be ready!

    Best regards,
    Your Event Organizer
    """

    print(f"Sending reminder email to {len(recipient_list)} participants...")  # Log số lượng email gửi

    for email in recipient_list:
        try:
            send_mail(
                subject,
                message,
                'nguyenanhtrinh05@gmail.com',  # Email người gửi
                [email],
                fail_silently=False,
            )
            print(f"Reminder email sent to {email}")
        except Exception as e:
            print(f"Error sending email to {email}: {e}")

# Hàm gửi email cảnh báo sự kiện sẽ bị xóa
def send_event_delete_warning_email(event):
    host_email = event.host.email  # `host` là trường ForeignKey đến người tạo sự kiện
    subject = f"Warning: '{event.title}' is about to be deleted!"
    message = f"""
    Dear {event.host.username},

    The event '{event.title}' at {event.location} is ending soon. The event will be deleted in 1 minute.

    Best regards,
    Your Event Organizer
    """
    
    try:
        send_mail(
            subject,
            message,
            'nguyenanhtrinh05@gmail.com',  # Email người gửi
            [host_email],
            fail_silently=False,
        )
        print(f"Delete warning email sent to {host_email}")
    except Exception as e:
        print(f"Error sending delete warning email to {host_email}: {e}")

# Hàm countdown tới khi sự kiện kết thúc
def countdown_to_end(event_end_time, event_title, event):
    global stop_threads
    current_time = timezone.now().astimezone(VIETNAM_TZ)
    time_to_delete = event_end_time + timedelta(minutes=1)
    warning_email_sent = False  # Cờ để kiểm tra xem đã gửi cảnh báo chưa

    while current_time < time_to_delete and not stop_threads:
        remaining_time = time_to_delete - current_time
        minutes_left = remaining_time.total_seconds() // 60  # Tính số phút còn lại

        print(f"END [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - End time: {event_end_time.strftime('%Y-%m-%d %H:%M:%S')} - Minutes left before deletion: {int(minutes_left)} minutes")

        if minutes_left == 30 and not warning_email_sent:
            print(f"Sending email to host: Event '{event_title}' will be deleted in 1 minute.")
            send_event_delete_warning_email(event)
            warning_email_sent = True  # Đánh dấu đã gửi cảnh báo

        time.sleep(60)  # Dừng chương trình 1 phút
        current_time = timezone.now().astimezone(VIETNAM_TZ)

    print(f"[{timezone.now().astimezone(VIETNAM_TZ).strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' has been deleted.")
    event.delete()

# Hàm countdown tới khi sự kiện bắt đầu
def countdown_timer(event_start_time, event_title, event):
    global stop_threads
    current_time = timezone.now().astimezone(VIETNAM_TZ)
    time_to_wait = event_start_time - timedelta(minutes=1)
    reminder_email_sent = False  # Cờ để kiểm tra xem đã gửi email nhắc nhở chưa

    while current_time < time_to_wait and not stop_threads:
        remaining_time = time_to_wait - current_time
        minutes_left = remaining_time.total_seconds() // 60  # Tính số phút còn lại

        print(f"START [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Event '{event_title}' - Start time: {event_start_time.strftime('%Y-%m-%d %H:%M:%S')} - Minutes left: {int(minutes_left)} minutes")

        if minutes_left == 30 and not reminder_email_sent:
            print(f"Sending reminder email: Event '{event_title}' is starting soon.")
            send_reminder_email(event)
            reminder_email_sent = True  # Đánh dấu đã gửi nhắc nhở

        time.sleep(60)  # Dừng chương trình 1 phút
        current_time = timezone.now().astimezone(VIETNAM_TZ)

    if not stop_threads:
        countdown_to_end(event.end_time, event_title, event)

# Kiểm tra các sự kiện đã được phê duyệt
def check_approved_events():
    approved_events = Event.objects.filter(status='approved')

    for event in approved_events:
        event_start_time = event.start_time
        event_title = event.title
        countdown_thread = threading.Thread(target=countdown_timer, args=(event_start_time, event_title, event))
        countdown_thread.daemon = True  # Dùng daemon thread để tự động dừng khi chương trình chính dừng
        countdown_thread.start()

@receiver(post_save, sender=Event)
def start_countdown_for_new_event(sender, instance, **kwargs):
    print(f"Signal triggered for event: {instance.title} with status {instance.status}")
    if instance.status == 'approved':
        print(f"Approved event detected: {instance.title}")
        event_start_time = instance.start_time
        event_title = instance.title
        countdown_thread = threading.Thread(target=countdown_timer, args=(event_start_time, event_title, instance))
        countdown_thread.daemon = True  # Dùng daemon thread để tự động dừng khi chương trình chính dừng
        countdown_thread.start()

# Added signal handling to stop threads when the server is shut down
def signal_handler(signal, frame):
    global stop_threads
    stop_threads = True  # Đánh dấu dừng tất cả các thread
    print("Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
