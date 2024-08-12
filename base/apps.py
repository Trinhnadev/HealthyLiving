from django.apps import AppConfig

class BaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'base'

    def ready(self):
        import base.signals  # Đảm bảo rằng signals được kết nối khi ứng dụng khởi động
        from base.signals import check_approved_events
        # Kiểm tra tất cả các sự kiện khi server khởi động
        check_approved_events() # Đảm bảo rằng signal được kết nối khi ứng dụng khởi động
