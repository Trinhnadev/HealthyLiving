import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    name = models.CharField(max_length = 200, null = True)
    email =models.EmailField(unique = True,null =True)
    bio = models.TextField(null = True)

    avatar = models.ImageField(default='defaut1.png',null=True)

    USERNAME_FIELD ='email'
    REQUIRED_FIELDS = []



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
    question = models.CharField(max_length=200,null=True, blank=True)  # New field for question
    answer = models.CharField(max_length=200,null=True, blank=True)

    class Meta:
        ordering = ['-updated','created']

    def __str__(seft):
        return seft.name
    
class Message(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    body = models.TextField()
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['updated','-created']
    def __str__(seft):
        return seft.body[0:50]
    



#friend
class Friendship(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendship_sent')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendship_received')
    status = models.CharField(max_length=20, default='pending')  # 'pending', 'accepted', 'rejected'

    def __str__(self):
        return f"{self.sender.username} - {self.receiver.username} ({self.status})"
    
class ChatRoom(models.Model):
    members = models.ManyToManyField(User, related_name='chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ChatRoom {self.pk} created at {self.created_at}"


#chat
class Chat(models.Model):
    roomchat = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages',null =True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sender_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receiver_messages')
    content = models.TextField()
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
    par = models.ManyToManyField(User,related_name='par',blank=True)
    location = models.CharField(max_length=200)
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

    def __str__(self):
        return f"{self.invitee.username} invited to {self.event.title}"

# Shop in Community
    

class Store(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    img = models.ImageField(default='storebanner.webp',null=True)
    name = models.CharField(max_length=255)
    liker = models.ManyToManyField(User,related_name='liker',blank=True)
    description = models.TextField()

    def __str__(self):
        return self.name
class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products' ,null=True)
    name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/')

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