# consumers.py
import base64
from tokenize import Comment
from django.core.files.base import ContentFile
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Message, Chat,ChatRoom, Post,Room

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '')
        username = data['username']
        userAvatar = data['userAvatar']
        media = data.get('media', None)

        # Save message to the database
        await self.save_message(username, message, media)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'userAvatar': userAvatar,
                'media': media,  # Include the media in the event
            }
        )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        userAvatar = event['userAvatar']
        media = event['media']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username,
            'userAvatar': userAvatar,
            'media': media,
        }))

    @database_sync_to_async
    def save_message(self, username, message, media):
        user = User.objects.get(username=username)
        room = Room.objects.get(id=self.room_id)
        msg = Message.objects.create(user=user, room=room, body=message)
        room.participants.add(user)

        if media:
            if media['type'].startswith('image/'):
                msg.image.save(media['name'], ContentFile(base64.b64decode(media['data'].split(',')[1])), save=True)
            elif media['type'].startswith('video/'):
                msg.video.save(media['name'], ContentFile(base64.b64decode(media['data'].split(',')[1])), save=True)



class ChatFriendConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_id}'
        
        # Join the room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        media_base64 = data.get('media')
        media_type = data.get('media_type')
        username = data['username']
        
        # Save the message to the database
        saved_message = await self.save_message(username, message, media_base64, media_type)

        # Send the message to the room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': saved_message.content,
                'media': saved_message.image.url if saved_message.image else saved_message.video.url if saved_message.video else None,
                'media_type': media_type,
                'username': saved_message.sender.username,
                'avatar_url': saved_message.sender.avatar.url
            }
        )

    async def chat_message(self, event):
        message = event['message']
        media = event['media']
        media_type = event['media_type']
        username = event['username']
        avatar_url = event['avatar_url']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'media': media,
            'media_type': media_type,
            'username': username,
            'avatar_url': avatar_url,
        }))

    @database_sync_to_async
    def save_message(self, username, message, media_base64=None, media_type=None):
        user = User.objects.get(username=username)
        chat_room = ChatRoom.objects.get(id=self.chat_id)
        receiver = chat_room.members.exclude(id=user.id).first()

        chat_message = Chat.objects.create(
            roomchat=chat_room, sender=user, receiver=receiver, content=message
        )

        if media_base64:
            format, imgstr = media_base64.split(';base64,')
            ext = format.split('/')[-1]

            if media_type == 'image':
                media = ContentFile(base64.b64decode(imgstr), name=f'{username}_image.{ext}')
                chat_message.image.save(f'{username}_image.{ext}', media)
            elif media_type == 'video':
                media = ContentFile(base64.b64decode(imgstr), name=f'{username}_video.{ext}')
                chat_message.video.save(f'{username}_video.{ext}', media)

        return chat_message



class CommentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.post_id = self.scope['url_route']['kwargs']['post_id']
        self.post_group_name = f'post_{self.post_id}'

        await self.channel_layer.group_add(
            self.post_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.post_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        comment_content = data['comment']

        await self.channel_layer.group_send(
            self.post_group_name,
            {
                'type': 'send_comment',
                'comment': comment_content
            }
        )

    async def send_comment(self, event):
        comment = event['comment']

        await self.send(text_data=json.dumps({
            'comment': comment
        }))