# consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Message, Chat,ChatRoom

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id  = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        username = data['username']
        room = data['room']


        # Save message to the database
        await self.save_message(username, message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'room': room,

            }
        )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        room = event['room']


        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username,
            'room': room,

        }))

    @database_sync_to_async
    def save_message(self, username, message):
        user = User.objects.get(username=username)
        room_id = self.room_id
        Message.objects.create(user=user, room_id=room_id, body=message)




class ChatFriendConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id  = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self,close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        username = data['username']


        # Save message to the database
        await self.save_message(username, message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
            }
        )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']



        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username,


        }))

    @database_sync_to_async
    def save_message(self, username, message):
        user = User.objects.get(username=username)
        chat_room = ChatRoom.objects.get(id=self.chat_id)
    
    # Giả sử ChatRoom chỉ dành cho hai người và bạn muốn xác định người nhận
        receiver = chat_room.members.exclude(id=user.id).first()
        Chat.objects.create(sender=user, receiver=receiver, content=message, roomchat=chat_room)