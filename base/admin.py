from django.contrib import admin

# Register your models here.
from .models import Room ,Topic,Message,User,Friendship,Chat,Product,Order,OrderDetail,Cart, CartItem,Event,Invitation,Store,ChatRoom,MessageReport

admin.site.register(Room)
admin.site.register(Chat)
admin.site.register(Event)
admin.site.register(Invitation)
admin.site.register(Store)
admin.site.register(ChatRoom)
admin.site.register(MessageReport)




admin.site.register(Friendship)

admin.site.register(User)

admin.site.register(Topic)
admin.site.register(Message)
admin.site.register(Product)
admin.site.register(Cart)
admin.site.register(CartItem)

admin.site.register(Order)
admin.site.register(OrderDetail)






