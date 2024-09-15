import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

from datetime import timedelta
from django.utils import timezone
# from .tasks import send_event_reminder, delete_event_and_notify_host

class User(AbstractUser):
    class UserRole(models.TextChoices):
        ADMIN = 'AD', 'Admin'
        USER = 'US', 'User'
        MODER = 'MO', 'Moder'

    name = models.CharField(max_length = 200, null = True)
    email =models.EmailField(unique = True,null =True)
    bio = models.TextField(null = True)

    avatar = models.ImageField(default='default1.png',null=True)
    coveravatar = models.ImageField(default='default1.png',null=True)
    role = models.CharField(
        max_length=2,
        choices=UserRole.choices,
        default=UserRole.USER,
        null =True
    )
    is_banned = models.BooleanField(default=False)
    USERNAME_FIELD ='email'
    REQUIRED_FIELDS = []
    def is_admin(self):
        return self.role == self.UserRole.ADMIN
    
    def serialize(self):
        return {
            'id': self.id,
            "username": self.username,
            "avatar": self.avatar.url,
            "name": self.name,
        }








class Topic(models.Model):
    name = models.CharField(max_length=200)

    def __str__(seft):
        return seft.name
# Create your models here.
class Room(models.Model):
    # id = models.UUIDField(primary_key= True, default =uuid.uuid4)
    host = models.ForeignKey(User,on_delete=models.SET_NULL,null =True)
    topic = models.ForeignKey(Topic,on_delete=models.SET_NULL,null=True)
    name = models.CharField(max_length=200,null =True)
    img = models.ImageField(default='',null=True)
    description = models.TextField(null = True, blank = True)
    participants = models.ManyToManyField(User,related_name='participants',blank=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    is_private = models.BooleanField(default=False)  # New field to indicate privacy
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-updated','created']

    def __str__(seft):
        return seft.name
    

class JoinRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='join_requests')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='join_requests')
    message = models.TextField()  # Lý do tham gia phòng
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Join request from {self.user.username} for room {self.room.name} - Status: {self.status}"

    
class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    video = models.FileField(upload_to='chat_videos/', blank=True, null=True)
    body = models.TextField(blank=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created']

    def __str__(self):
        if self.body:
            return self.body[:50]
        return "Media message"
    

class MessageReport(models.Model):
    class ReportReasons(models.TextChoices):
        SPAM = 'SP', 'Spam or misleading'
        HARASSMENT = 'HR', 'Harassment or bullying'
        INAPPROPRIATE_CONTENT = 'IC', 'Inappropriate content'
        COPYRIGHT = 'CR', 'Copyright violation'
        OTHER = 'OT', 'Other'

    reported_message = models.ForeignKey(Message, related_name='reports_received', on_delete=models.CASCADE)
    reporting_users = models.ManyToManyField(User, related_name='reports_made',blank=True)
    reason = models.TextField()
    detail = models.TextField(null=True, blank=True)  # Optional: for additional details if 'Other' is selected
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f' reports {self.reported_message}'
    
    def __str__(self):
        reporting_users = ', '.join(user.username for user in self.reporting_users.all())
        return f'{reporting_users} reports {self.reported_message}'

    

#friend
class Friendship(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendship_sent')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendship_received')
    status = models.CharField(max_length=20, default='pending')  # 'pending', 'accepted', 'rejected'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username} - {self.receiver.username} ({self.status})"
    
class ChatRoom(models.Model):
    members = models.ManyToManyField(User, related_name='chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ChatRoom {self.pk} created at {self.created_at}"


#chat
class Chat(models.Model):
    roomchat = models.ForeignKey('ChatRoom', on_delete=models.CASCADE, related_name='messages', null=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sender_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receiver_messages')
    image = models.ImageField(blank=True, null=True)
    video = models.FileField(upload_to='videos/', blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sender} to {self.receiver} at {self.timestamp}"
    
# Event
class Event(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_events')
    title = models.CharField(max_length=200)
    description = models.TextField()
    img = models.ImageField(default='eventDefault.jpg',null=True)
    like = models.ManyToManyField(User,related_name='like',blank=True)
    par = models.ManyToManyField(User,related_name='par',blank=True)
    location = models.CharField(max_length=200)
    status = models.CharField(max_length=200, default="waiting", null= True)
    is_private = models.BooleanField(default=False)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    



    

class Invitation(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='invitations')
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invitations')
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invitee.username} invited to {self.event.title}"

# Shop in Community
    

class Store(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    img = models.ImageField(default='storebanner.webp',null=True)
    name = models.CharField(max_length=255)
    liker = models.ManyToManyField(User,related_name='liker',blank=True)
    description = models.TextField()
    status = models.CharField(max_length=200, default="waiting", null= True)
    address = models.TextField(null =True)
    phone = models.CharField(max_length=200,null =True)


    def __str__(self):
        return self.name
class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products' ,null=True)
    name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/')
    status = models.CharField(max_length=200, default="waiting", null= True)




    def __str__(self):
        return self.name

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    

    def get_total_price(self):
        total = sum(item.quantity * item.product.price for item in self.items.all())
        return total

    def __str__(self):
        return f"Cart for {self.user.username}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    
    def get_total(self):
        return self.quantity * self.product.price
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='orders',null=True)
    order_date = models.DateTimeField(auto_now_add=True)
    address = models.TextField( null=True)  # Assuming a simple text field for the address
    full_name = models.CharField(max_length=255,null=True)  # To store the full name of the user placing the order
    phone_number = models.CharField(max_length=20,null=True)

class OrderDetail(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)



class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=255)
    content = models.TextField()
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)
    image = models.ImageField(upload_to='post_images/', blank=True, null=True)
    video = models.FileField(upload_to='post_videos/', blank=True, null=True, help_text="Upload a video file.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def like_count(self):
        return self.likes.count()

    def share_count(self):
        return self.shares.count()

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commenters')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.user.username} on {self.post.title}'
    
    def serialize(self):
        return {
            "id": self.id,
            "user": self.user.serialize(),
            "body": self.content,
            "timestamp": self.created_at.strftime("%b %d %Y, %I:%M %p")
        }
    
    
    

class Share(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_posts')
    content = models.TextField(null=True, blank=True)  # Field to add content to the share
    likes = models.ManyToManyField(User, related_name='liked_shares', blank=True)  # Likes for the share
    created_at = models.DateTimeField(auto_now_add=True)

    def like_count(self):
        return self.likes.count()

    def __str__(self):
        return f'{self.user.username} shared {self.post.title}'
    


