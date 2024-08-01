import os
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
import base.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studybud.settings')

application = ProtocolTypeRouter({
  "http": get_asgi_application(),
  "websocket": 
      AuthMiddlewareStack(
        URLRouter(
            base.routing.websocket_urlpatterns
            )
    ),
})



from django.core.management import call_command
call_command('event_scheduler')

