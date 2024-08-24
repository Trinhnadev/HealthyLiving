# myapp/routing.py
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/room/<int:room_id>/', consumers.ChatConsumer.as_asgi()),
    path('ws/open_chat/<int:chat_id>/', consumers.ChatFriendConsumer.as_asgi()),
    path('ws/comments/<int:post_id>/', consumers.CommentConsumer.as_asgi()),
    

]