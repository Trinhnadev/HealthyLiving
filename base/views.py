import calendar
import json
import os
import random
import threading
import time
from django.shortcuts import render,redirect
from django.contrib import messages
from django.http import HttpResponse
from .models import Room, Topic, Message ,User , Friendship ,Chat ,Product,Order,OrderDetail, Cart , CartItem , Event,Invitation,Store,ChatRoom,MessageReport,EventMessage,Notification
from django.db.models import Q
from django.contrib.auth.decorators import login_required ,user_passes_test
from .forms import RoomForm, UserForm ,ProfileForm ,MyUserCreationForm,EventsForm,StoreForm,ProductForm,CheckoutForm,ReportForm
# from django.contrib.auth.forms import UserCreationForm
# from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login ,logout
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.http import HttpResponseRedirect
from django.db import transaction
from datetime import datetime,  timedelta
from django.utils import timezone
from django.core.mail import send_mail
import random
import string
from django.contrib.auth.hashers import make_password
from django.utils.timezone import now
from django.contrib.auth import update_session_auth_hash
from django.db.models import Count ,Prefetch
from collections import defaultdict
from django.db.models import Sum, F 
from django.db.models.functions import ExtractMonth
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from itertools import chain
from operator import attrgetter
from .decorators import role_required
from django.core.management import call_command

from pytz import timezone as pytz_timezone
# Múi giờ Việt Nam
VIETNAM_TZ = pytz_timezone('Asia/Ho_Chi_Minh')

@login_required
def home(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topic = Topic.objects.all()[0:5]
    user = request.user

    chat_rooms = ChatRoom.objects.filter(members=user)
    rooms = Room.objects.filter(
        Q(topic__name__icontains=q) |
        Q(name__icontains=q)
    )
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    room_count = rooms.count()
    room_message = Message.objects.filter(
        Q(room__topic__name__icontains=q)
    )[0:5]

    invitations = Invitation.objects.filter(invitee=request.user, accepted=False)
    accepted_friends = Friendship.objects.filter(
        Q(sender=request.user, status='accepted') | 
        Q(receiver=request.user, status='accepted')
    )

    users_in_same_rooms = User.objects.filter(room__participants=user).exclude(id=user.id)

    user_counts = users_in_same_rooms.values('id').annotate(room_count=Count('room')).order_by('-room_count')
    top_users = [entry['id'] for entry in user_counts]
    user_friends = user.friendship_sent.filter(status='accepted').values_list('receiver_id', flat=True)
    random_users = User.objects.filter(id__in=top_users).exclude(id__in=user_friends)[:10]

    rooms_with_message_count = rooms.annotate(message_count=Count('message'))

    combined_notifications = sorted(
        chain(invitations, sent),
        key=attrgetter('created_at'),
        reverse=True
    )



    context = {
        'rooms': rooms_with_message_count,
        'topic': topic,
        'chat_rooms': chat_rooms,
        'room_count': room_count,
        'room_message': room_message,
        'random_users': random_users,
        'users': accepted_friends,
        'combined_notifications': combined_notifications,
    }

    return render(request, 'base/home.html', context)


@login_required
def userProfile(request,pk):
    user = get_object_or_404(User, id=pk)
    
    friendship = Friendship.objects.filter(
        Q(sender=request.user, receiver=user) | Q(sender=user, receiver=request.user)
    ).first()
    sent = Friendship.objects.filter(receiver=request.user, status='pending')

    accepted_friends = Friendship.objects.filter(
        Q(sender=request.user, status='accepted') | 
        Q(receiver=request.user, status='accepted')
    )

    users_in_same_rooms = User.objects.filter(room__participants=user).exclude(id=user.id)

    # Đếm số lần mỗi người dùng khác xuất hiện trong các phòng mà user tham gia
    user_counts = users_in_same_rooms.values('id').annotate(room_count=Count('room')).order_by('-room_count')

    # Lấy các người dùng xuất hiện nhiều nhất trong các phòng mà user tham gia
    top_users = [entry['id'] for entry in user_counts]

    # Lấy danh sách bạn bè của user
    user_friends = user.friendship_sent.filter(status='accepted').values_list('receiver_id', flat=True)

    # Loại bỏ các người dùng đã là bạn bè của user
    random_users = User.objects.filter(id__in=top_users).exclude(id__in=user_friends)[:10]
    
    # Lấy các phòng và đếm số lượng tin nhắn cho từng phòng
    rooms = user.room_set.annotate(message_count=Count('message'))
    room_message = user.message_set.all()[0:5]
    topic = Topic.objects.all()[0:5]
    
    chat_room = ChatRoom.objects.filter(members=request.user).filter(members=user).first()
    if not chat_room and friendship and friendship.status == 'accepted':
        chat_room = ChatRoom.objects.create()
        chat_room.members.add(request.user, user)

    context = {
        'user': user,
        'rooms': rooms,
        'room_message': room_message,
        'topic': topic,
        'random_users': random_users,
        'users': accepted_friends,
        'sent': sent,
        'friendship': friendship,
        'chat_room': chat_room,
    }
    return render(request, 'base/profile.html', context)


@login_required(login_url='login')
def update_avatar(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Avatar updated successfully'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid form data'})
    else:
        form = ProfileForm(instance=user)
        context = {'form': form}
        return render(request, 'base/upload_profile_image.html', context)

@login_required
@csrf_exempt
def update_coveravatar(request):
    if request.method == 'POST' and request.FILES.get('coveravatar'):
        user = request.user
        user.coveravatar = request.FILES['coveravatar']
        user.save()
        return JsonResponse({'status': 'success', 'message': 'Cover photo updated successfully!'})
    return JsonResponse({'status': 'error', 'message': 'Failed to update cover photo.'})



def loginPage(request):
    page = 'login'
    login_result = ''
    if request.method == 'POST':
        username = request.POST.get('username').lower()
        password = request.POST.get('password')

        # Sử dụng authenticate để kiểm tra thông tin đăng nhập
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Thêm bước kiểm tra để xem người dùng có bị cấm không
            if user.is_banned:
                messages.error(request, 'Your account has been banned. Please contact the administrator for more information.')
                login_result = 'banned'
            else:
                login(request, user)
                login_result = 'success'
                return redirect('home')
        else:
            login_result = 'error'

    context = {'page': page, 'login_result': login_result}
    return render(request, 'base/login_sign.html', context)


def logoutUser(request):
    logout(request)
    return redirect('login')


def sign(request):
    page = 'sign'
    form = MyUserCreationForm()

    if request.method == 'POST':
        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            if User.objects.filter(email=email).exists():
                messages.error(request, "Email này đã được đăng ký.")
            else:
                user = form.save(commit=False)
                user.username = user.username.lower()
                user.save()
                login(request, user)
                return redirect('home')
        else:
            print(form.errors)  # In ra lỗi của form để kiểm tra
            messages.error(request, "Đăng ký không thành công. Vui lòng kiểm tra lại thông tin.")

    context = {'form': form}
    return render(request, 'base/login_sign.html', context)


def updateUser(request):
    user = request.user

    if request.method == 'POST':
        name = request.POST.get('name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        bio = request.POST.get('bio')

        user.name = name
        user.username = username
        user.email = email
        user.bio = bio
        user.save()

        return redirect('profile', pk=user.id)

    context = {'user': user}
    return render(request, 'base/update-user.html', context)

#End profile

#Room Function
@login_required
def room(request,pk):
    room = Room.objects.get(id=pk)
    pa = room.participants.all()
    messages = room.message_set.all()
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    if request.user == room.host or room.is_private==False or request.user in pa:
        if request.method == 'POST' and 'body' in request.POST:
            message = Message.objects.create(
                user=request.user,
                room=room,
                body=request.POST.get('body'),
                image=request.FILES.get('image'),
            )
            room.participants.add(request.user)
            return redirect('room', pk=room.id)
        context = {
            'rooms': room,
            'message': messages,
            'participants': pa,
            'created_at': datetime.now(),  # Dummy value, replace it with the actual creation time
            'message_id': None
        }
        return render(request, 'base/room.html', context)

    if room.is_private and request.user not in pa:
        if request.method == 'POST' and 'answer' in request.POST:
            user_answer = request.POST.get('answer', '').strip().lower()
            correct_answers = room.answer.lower().split(',')
            if any(keyword.strip() in user_answer for keyword in correct_answers):
                room.participants.add(request.user)
                return redirect('room', pk=room.id)
            else:
                return redirect('home')
        return render(request, 'base/room_question.html', {'room': room, 'sent': sent})

    



#can dang nhap moi dung dc
@login_required(login_url='login')
def createRoom(request):
    form = RoomForm()
    topic = Topic.objects.all()
    sent = Friendship.objects.filter(receiver=request.user, status='pending')

    answer_keywords = request.POST.get('answer', '').strip()
    answer_keywords = ','.join([keyword.strip() for keyword in answer_keywords.split(',')])


    #kiem tra phuong thuc
    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created = Topic.objects.get_or_create(name = topic_name)
        Room.objects.create(
            host =request.user,
            topic = topic,
            name = request.POST.get('name'),
            description = request.POST.get('description'),
            is_private = request.POST.get('is_private'),
            question = request.POST.get('question'),
            answer = answer_keywords,
        )
        return redirect('home')
    context = {'form':form,"topic":topic,"sent":sent}
    return render(request,'base/room_form.html',context)
    

@login_required(login_url='login')
def updateRoom(request,pk):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    room = Room.objects.get(id= pk)
    form = RoomForm(instance=room)
    topic = Topic.objects.all()
    if request.user != room.host:
        return HttpResponse('')
    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created = Topic.objects.get_or_create(name = topic_name)
        room.name = request.POST.get('name')
        room.topic = topic
        room.description = request.POST.get('description')
        room.password = request.POST.get('password')
        room.save()

        return redirect('home')

    context = {'form':form,'topic':topic,'room':room,"sent":sent}
    return render(request,'base/room_form.html',context)

@login_required(login_url='login')
def deleteRoom(request,pk):
    room = Room.objects.get(id = pk)
    if request.method == 'POST':
        room.delete()
        return redirect('home')
    return render(request,'base/delete.html',{'obj':room})


@login_required(login_url='login')
def deleteMessage(request,pk):
    message = Message.objects.get(id = pk)
    # message = get_object_or_404(Message, id=pk)
    if request.user == message.user or request.user.is_admin:
        if request.method == 'POST':
            message.delete()
            return redirect('room',pk=message.room.id)
    return render(request,'base/delete.html',{'obj':message})



def topicsPage(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topics = Topic.objects.filter(name__icontains = q)
    return render(request,'base/topics.html',{'topics':topics})

#FriendShip Function
@login_required
def friendPages(request):
    q = request.GET.get('q', '')
    current_user = request.user
    chat_rooms = ChatRoom.objects.filter(members=current_user)
    users = User.objects.exclude(id=current_user.id).filter(username__icontains=q)

    # Fetch all accepted friends
    friendships_accepted = Friendship.objects.filter(
        Q(sender=current_user, status='accepted') | Q(receiver=current_user, status='accepted')
    )
    accepted_friends = [friendship.sender if friendship.receiver == current_user else friendship.receiver for friendship in friendships_accepted]

    return render(request, 'base/Friend.html', {
        'users': users,
        'user': current_user,
        'accepted_friends': accepted_friends,
        'chat_rooms': chat_rooms,
    })


@login_required
def AllFriend(request):
    q = request.GET.get('q', '')
    current_user = request.user
    chat_rooms = ChatRoom.objects.filter(members=current_user)
    users = User.objects.exclude(id=current_user.id).filter(username__icontains=q)

    friendships_sent = Friendship.objects.filter(sender=current_user, status='pending')
    sent_friend_requests = [friendship.receiver for friendship in friendships_sent]

    friendships_received = Friendship.objects.filter(receiver=current_user, status='pending')
    received_friend_requests = [friendship.sender for friendship in friendships_received]

    friendships_accepted = Friendship.objects.filter(Q(sender=current_user, status='accepted') | Q(receiver=current_user, status='accepted'))
    accepted_friends = [friendship.sender if friendship.receiver == current_user else friendship.receiver for friendship in friendships_accepted]


    
    return render(request, 'base/allFriend.html', {
        'users': users,
        'user': current_user,
        'sent_friend_requests': sent_friend_requests,
        'received_friend_requests': received_friend_requests,
        'accepted_friends': accepted_friends,
        'chat_rooms':chat_rooms,
    })

@login_required
def myFriends(request):
    q = request.GET.get('q', '')  # Use an empty string as default if 'q' is not present
    current_user = request.user
    # Filter friends based on search query and friendship status
    user = Friendship.objects.filter(
        (Q(sender=current_user, status='accepted') | Q(receiver=current_user, status='accepted'))
        & (Q(sender__username__icontains=q) | Q(receiver__username__icontains=q))
    )
    return render(request,'base/myfriend.html',{'user':user})



def activityPages(request):
    room_message = Message.objects.all()
    return render(request,'base/activityvp.html',{})



@login_required
#add friend
def sentRequest(request,pk):
    receiver = get_object_or_404(User, pk=pk)
    previous_request = Friendship.objects.filter(sender=request.user, receiver=receiver).first()

    if previous_request:
        previous_request.status = 'pending'
        previous_request.save()
        messages.success(request, 'Friend request resent successfully.')
    else:
        # If there is no previous request, create a new one
        Friendship.objects.create(sender=request.user, receiver=receiver, status='pending')
        messages.success(request, 'Friend request sent successfully.')

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@login_required
def acceptRequest(request,pk):
    sender = User.objects.get(pk=pk)

        # Check if there is a pending friend request
    friendship_request = Friendship.objects.filter(Q(sender=sender, receiver=request.user, status='pending')|Q(sender=request.user, receiver=sender, status='pending')).first()

    if friendship_request:
        friendship_request.status = 'accepted'
        friendship_request.save()

        existing_room = ChatRoom.objects.filter(members__id=sender.id).filter(members__id=request.user.id).distinct()
        if not existing_room.exists():
            # Nếu không, tạo ChatRoom mới
            chat_room = ChatRoom.objects.create()
            chat_room.members.add(sender, request.user)
        messages.success(request, f'You are now friends with {sender.username}.')
        
    else:
        messages.warning(request, 'No pending friend request found.')

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@login_required
def reject(request, pk):
    sender = get_object_or_404(User, pk=pk)

    friendship_request = Friendship.objects.filter(
        (Q(sender=sender, receiver=request.user) | Q(sender=request.user, receiver=sender)),
        status__in=['pending', 'accepted']
    ).first()
    chat_room = ChatRoom.objects.filter(members__in=[sender, request.user]).distinct().first()
    if friendship_request:
        # If the status is 'accepted', update it to 'rejected'
        if friendship_request.status == 'accepted':
            friendship_request.delete()
            if chat_room:
                chat_room.delete()
                messages.success(request, f'Friendship with {sender.username} has been ended and the chat room has been deleted.')
            else:
                messages.success(request, f'Friendship with {sender.username} has been ended.')
        # If the status is 'pending', delete the friend request
        elif friendship_request.status == 'pending':
            friendship_request.delete()
            messages.success(request, f'Friend request from {sender.username} rejected.')
    else:
        messages.warning(request, 'No pending or accepted friend request found with this user.')

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@login_required
#Chat with Friend function
def chat(request):
    user = request.user
    query = request.GET.get('q', '')
    chat_rooms = ChatRoom.objects.filter(members=user)
    if query:
        chat_rooms = chat_rooms.filter(members__username__icontains=query).distinct()

    # Tìm tất cả bạn bè đã chấp nhận của người dùng
    accepted_friends = Friendship.objects.filter(
        (Q(sender=user) | Q(receiver=user)),
        status='accepted'
    )

    context = {
        'chat_rooms': chat_rooms,
        'accepted_friends': accepted_friends,
    }

    return render(request,'base/chat.html',context)

@login_required
def open_chat(request, pk):
    chat_room = get_object_or_404(ChatRoom, id=pk)
    chat_rooms = ChatRoom.objects.filter(members=request.user)
    messages = Chat.objects.filter(roomchat=chat_room).order_by('timestamp')
    
    # Lấy người bạn duy nhất trong phòng chat này
    friend = chat_room.members.exclude(id=request.user.id).first()

    accepted_friends = Friendship.objects.filter(Q(sender=request.user, status='accepted') | Q(receiver=request.user, status='accepted'))

    if request.method == 'POST' and friend:
        content = request.POST.get('body', '').strip()
        image = request.FILES.get('image')
        if content or image:
            # Đảm bảo friend là một instance cụ thể của User
            Chat.objects.create(
                roomchat=chat_room,
                sender=request.user,
                receiver=friend,  # friend giờ là một instance của User
                content=content,
                image=image,
            )
        return redirect('open_chat', pk=pk)

    return render(request, 'base/chat.html', {
        'chat_room': chat_room,
        'chat_rooms':chat_rooms,
        'messages': messages,
        'friend': friend,  # Chuyển friend dưới dạng một instance của User
        'accepted_friends': accepted_friends
    })

def delete_message_chat(request, message_id):
    message = get_object_or_404(Chat, id=message_id)
    chat_rooms = ChatRoom.objects.filter(members=request.user)

    # Check if the user has permission to delete the message
    if request.user == message.sender:
        message.delete()
        messages.success(request, 'Message deleted successfully.')
    else:
        messages.error(request, 'You do not have permission to delete this message.')

    # Redirect back to the chat room or any other appropriate page
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


#End chat function

# shop ban hang
#done
def shopping (request):
    # products = Product.objects.all()
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    q = request.GET.get('q', '')
    # Lấy store của người dùng hiện tại
    
    # Tìm kiếm sản phẩm trong store của người dùng hiện tại
    products = Product.objects.filter(
        Q(description__icontains=q) | 
        Q(name__icontains=q),
        status='approved'
    )
    user_store = Store.objects.filter(owner=request.user,status='approved')
    # Tìm kiếm cửa hàng của người dùng hiện tại
    stores = user_store.filter(
        Q(name__icontains=q),
    )
    context = {'products': products, 'stores': stores,"sent":sent}
    return render(request, 'base/store.html', context)

#done
@login_required
def create_store(request):
    if request.method == 'POST':
        # Thêm request.FILES để xử lý các tệp được tải lên
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user  
            store.status = "waiting"# Thiết lập người sở hữu cho cửa hàng là người dùng hiện tại
            store.save()
            # Đảm bảo form m2m được lưu nếu có
            form.save_m2m()
            return redirect('shop')  # Thay 'shop' bằng tên URL đích sau khi tạo cửa hàng thành công
    else:
        form = StoreForm()
    return render(request, 'base/store_form.html', {'form': form})



@login_required
def update_store(request, pk):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    store = get_object_or_404(Store, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            store = form.save(commit=False)
            store.status = "waiting"
            form.save()
            return redirect('shop')
    else:
        form = StoreForm(instance=store)
    return render(request, 'base/store_form.html', {'form': form, 'store': store,"sent":sent})



@login_required
def delete_store(request, pk):
    store = get_object_or_404(Store, pk=pk, owner=request.user)

    store.delete()
    return redirect('shop')



def store_detail(request,pk):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    store = get_object_or_404(Store, id=pk)
    products = Product.objects.filter(store=store)
    stores = Store.objects.filter(owner=request.user,status ="approved")
    # Tìm kiếm cửa hàng của người dùng hiện tại

    context = {'store':store, 'products':products ,'stores':stores,"sent":sent}
    return render(request,'base/store_profile_detail.html',context)



def store_products(request, store_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    store = get_object_or_404(Store, id=store_id)
    query = request.GET.get('q')
    stores = Store.objects.filter(owner=request.user,status='approved')

    if query:
        # Lọc sản phẩm dựa trên từ khóa tìm kiếm trong tên hoặc mô tả sản phẩm
        products = Product.objects.filter(
            Q(store=store),
            Q(name__icontains=query) | Q(description__icontains=query),status ="approved"
        )
    else:
        products = Product.objects.filter(store=store)

    return render(request, 'base/store_detail.html', {'store': store, 'products': products,'stores':stores,"sent":sent})



@login_required
def product_create(request, store_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    stores = Store.objects.filter(owner=request.user)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store = store
            product.save()
            return redirect('store_products', store_id=store.id)
    else:
        form = ProductForm()
    return render(request, 'base/product_form.html', {'form': form, 'store': store,'stores': stores,"sent":sent})

@login_required
def product_update(request, store_id, product_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    product = get_object_or_404(Product, id=product_id, store=store)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save(commit=False)
            product.status = "waiting"
            form.save()
            return redirect('store_products', store_id=store.id)
    else:
        form = ProductForm(instance=product)
    return render(request, 'base/product_form.html', {'form': form, 'store': store,"sent":sent})



@login_required
@require_POST
def update_product_quantity(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity'))

    product = get_object_or_404(Product, id=product_id)

    if quantity > 0:
        product.quantity += quantity
        product.save()

    return redirect('store_products', store_id=product.store.id)

@login_required
def product_delete(request, store_id, product_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    product = get_object_or_404(Product, id=product_id, store=store)
    
    product.delete()
    return redirect('store_products', store_id=store.id)
    



def product_detail(request, store_id, product_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user)

    product = get_object_or_404(Product, store__id=store_id, id=product_id)
    
    # Tính tổng số lượng của sản phẩm cụ thể
    total_quantity = OrderDetail.objects.filter(product=product).aggregate(total=Sum('quantity'))['total']
    if total_quantity is None:
        total_quantity = 0
    
    return render(request, 'base/product_detail.html', {
        'product': product,
        'stores': stores,
        'sent': sent,
        'total_quantity': total_quantity  # Truyền tổng số lượng sản phẩm vào context
    })





@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    user = request.user
    cart, created = Cart.objects.get_or_create(user=user)

    # Lấy số lượng từ form, sử dụng giá trị mặc định là 1 nếu không tìm thấy
    quantity = int(request.POST.get('quantity', 1))

    cart_item, created = CartItem.objects.get_or_create(
        product=product,
        cart=cart,
    )
    if not created:
        # Cập nhật số lượng dựa trên giá trị nhập vào từ form
        cart_item.quantity += quantity
    else:
        # Nếu là lần đầu tiên sản phẩm được thêm vào giỏ, thiết lập số lượng
        cart_item.quantity = quantity
    cart_item.save()

    # Redirect to the previous page or cart detail page
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))





def cart_detail(request):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user,status='approved')

    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        items = cart.items.all()
        total_price = cart.get_total_price()
    else:
        items = []
        total_price = 0

    context = {
        'cart_items': items,
        'total_price': total_price,
        'stores':stores,
        "sent":sent,
    }
    return render(request, 'base/cart_detail.html', context)

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    # Quay trở lại trang giỏ hàng sau khi xóa sản phẩm
    return redirect('cart_detail')

#cbi cxoas
@login_required

def checkout(request):
    cart = request.user.cart
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        address = request.POST.get('address')
        
        if full_name and phone_number and address:
            with transaction.atomic():  # Use a transaction to ensure data integrity
                order = Order.objects.create(
                    user=request.user,
                    full_name=full_name,
                    phone_number=phone_number,
                    address=address,
                    store=cart.items.first().product.store if cart.items.exists() else None
                )

                # Move cart items to order details and update stock
                insufficient_stock = []
                for item in cart.items.all():
                    if item.product.quantity >= item.quantity:  # Check if enough stock
                        item.product.quantity -= item.quantity  # Deduct stock
                        item.product.save()

                        OrderDetail.objects.create(
                            order=order,
                            product=item.product,
                            quantity=item.quantity,
                            subtotal=item.get_total()
                        )
                    else:
                        insufficient_stock.append(item.product.name)

                if insufficient_stock:  # If any products have insufficient stock
                    return render(request, 'template_name.html', {  # Update with your actual template name
                        'error_message': f'Insufficient stock for: {", ".join(insufficient_stock)}',
                        'cart_items': cart.items.all(),
                        'total_price': cart.get_total_price(),
                        'form_data': request.POST,
                    })

                # Clear the cart after successful transaction
                cart.items.all().delete()

                # Redirect to an order confirmation page
                return redirect('order_detail', order.id)
        else:
            return render(request, 'template_name.html', {  # Update with your actual template name
                'error_message': 'Please fill out all fields.',
                'cart_items': cart.items.all(),
                'total_price': cart.get_total_price(),
                'form_data': request.POST,
            })

    return render(request, 'template_name.html', {  # Update with your actual template name
        'cart_items': cart.items.all(),
        'total_price': cart.get_total_price(),
    })


#dơn hang cua shop
@login_required
def store_order_history(request, store_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner = request.user,status='approved')
    store = get_object_or_404(Store, id=store_id, owner=request.user)

    orders = Order.objects.filter(orderdetail__product__store=store).distinct().order_by('-order_date').prefetch_related('orderdetail_set__product__store')

    # Tính toán tổng số tiền cho mỗi hóa đơn
    order_totals = defaultdict(float)  # Sử dụng float để lưu trữ tổng số tiền
    for order in orders:
        for detail in order.orderdetail_set.all():
            if detail.product.store == store:  # Kiểm tra xem sản phẩm có thuộc cửa hàng này không
                order_totals[order.id] += float(detail.subtotal)

    # Chuyển kết quả từ defaultdict sang dict để tránh lỗi khi truyền vào template
    order_totals = dict(order_totals)

    return render(request, 'base/store_order_history.html', {
        'stores':stores,
        'store': store,
        'orders': orders,
        'order_totals': order_totals,
        'sent':sent,
    })


@login_required
def store_order_detail(request, store_id, order_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    order = get_object_or_404(Order, id=order_id, store=store)

    # Filter order details to include only products from the specified store
    order_details = order.orderdetail_set.filter(product__store=store)

    # Calculate the total for the filtered order details
    order_total = sum(detail.subtotal for detail in order_details)

    return render(request, 'base/store_order_detail.html', {
        'store': store,
        'order': order,
        'order_details': order_details,
        'order_total': order_total,
        'sent':sent
    })

@login_required
def revenue(request, store_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user, status='approved')
    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        messages.error(request, "Store not found.")
        return redirect('store_order_history')

    # Lấy tất cả đơn hàng có chứa ít nhất một sản phẩm từ cửa hàng này
    orders = Order.objects.filter(orderdetail__product__store=store).distinct().order_by('-order_date').prefetch_related('orderdetail_set__product__store')

    # Tổ chức dữ liệu đơn hàng và chi tiết đơn hàng theo cửa hàng
    store_orders = defaultdict(lambda: {'orders': [], 'total': 0, 'details': defaultdict(list)})

    for order in orders:
        # Khởi tạo tổng giá và chi tiết cho từng cửa hàng trong đơn hàng
        for detail in order.orderdetail_set.all():
            product_store = detail.product.store
            if product_store.id == store_id:  # Chỉ xử lý sản phẩm thuộc cửa hàng được chỉ định
                store_orders[product_store]['orders'].append(order)
                store_orders[product_store]['details'][order].append(detail)
                store_orders[product_store]['total'] += float(detail.subtotal)

    # Chuyển kết quả từ defaultdict sang dict để tránh lỗi khi truyền vào template
    store_orders = dict((store, {'orders': data['orders'], 'total': data['total'], 'details': dict(data['details'])}) for store, data in store_orders.items())
    monthly_revenue = orders.annotate(month=ExtractMonth('order_date'))\
                        .values('month')\
                        .annotate(total_revenue=Sum('orderdetail__subtotal'), total_orders=Count('id'))\
                        .order_by('month')

    # Chuẩn bị dữ liệu cho biểu đồ (Giả sử doanh thu cho những tháng không có đơn hàng là 0)
    revenue_per_month = [0] * 12
    orders_per_month = [0] * 12
    for revenue in monthly_revenue:
        revenue_per_month[revenue['month'] - 1] = revenue['total_revenue']
        orders_per_month[revenue['month'] - 1] = revenue['total_orders']

    revenue_per_month_float = [float(revenue) for revenue in revenue_per_month]

    # Tổng số lượng đơn hàng và tổng doanh thu
    total_orders = orders.count()
    total_revenue = sum(revenue_per_month_float)

    # Render kết quả ra template, ví dụ 'store_order_history.html'
    return render(request, 'base/revenue.html', {
        'store': store,
        'orders': orders,
        'stores': stores,
        'store_orders': store_orders,
        'revenue_per_month': revenue_per_month_float,
        'orders_per_month': orders_per_month,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
          'sent':sent,  # Passing months to the template
    })


@login_required
def dashboard(request, store_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user, status="approved")
    store = get_object_or_404(Store, id=store_id)

    month = request.GET.get('month')
    if month and month != 'all':
        month = datetime.strptime(month, '%Y-%m')
        orders = Order.objects.filter(orderdetail__product__store=store, order_date__year=month.year, order_date__month=month.month).distinct().order_by('-order_date').prefetch_related('orderdetail_set__product__store')
        top_products = OrderDetail.objects.filter(product__store=store, order__order_date__year=month.year, order__order_date__month=month.month).values('product__name', 'product__image').annotate(total_sold=Sum('quantity'), total_revenue=Sum('subtotal')).order_by('-total_sold')[:5]
    else:
        orders = Order.objects.filter(orderdetail__product__store=store).distinct().order_by('-order_date').prefetch_related('orderdetail_set__product__store')
        top_products = OrderDetail.objects.filter(product__store=store).values('product__name', 'product__image').annotate(total_sold=Sum('quantity'), total_revenue=Sum('subtotal')).order_by('-total_sold')[:5]

    store_orders = defaultdict(lambda: {'orders': [], 'total': 0, 'details': defaultdict(list)})

    for order in orders:
        for detail in order.orderdetail_set.all():
            product_store = detail.product.store
            if product_store.id == store_id:
                store_orders[product_store]['orders'].append(order)
                store_orders[product_store]['details'][order].append(detail)
                store_orders[product_store]['total'] += float(detail.subtotal)

    store_orders = dict((store, {'orders': data['orders'], 'total': data['total'], 'details': dict(data['details'])}) for store, data in store_orders.items())
    product_names = [product['product__name'] for product in top_products]
    product_sales = [product['total_sold'] for product in top_products]
    product_revenues = [product['total_revenue'] for product in top_products]
    
    total_orders = orders.count()
    store_revenue = sum(order.orderdetail_set.filter(product__store=store).aggregate(total=Sum('subtotal'))['total'] for order in orders)

    current_year = datetime.now().year
    month_list = [('all', 'All Months')] + [(f"{current_year}-{str(m).zfill(2)}", datetime(current_year, m, 1).strftime('%B')) for m in range(1, 13)]

    # Create a list of product data for template context
    top_products_data = []
    for product in top_products:
        name = product['product__name']
        image = product['product__image']
        orders_count = product['total_sold']
        revenue = product['total_revenue']
        orders_percentage = (orders_count / total_orders * 100) if total_orders else 0
        revenue_percentage = (revenue / store_revenue * 100) if store_revenue else 0
        top_products_data.append({
            'name': name,
            'image': image,
            'orders_count': orders_count,
            'orders_percentage': orders_percentage,
            'revenue': revenue,
            'revenue_percentage': revenue_percentage,
        })

    return render(request, 'base/dashboard.html', {
        'store': store,
        'orders': orders,
        'stores': stores,
        'store_orders': store_orders,
        'top_products': top_products_data,
        'total_orders': total_orders,
        'store_revenue': store_revenue,
        'selected_month': month.strftime('%Y-%m') if month and month != 'all' else 'all',
        'month_list': month_list,
        'sent': sent,
    })




def history(request):
    # Lấy tất cả các đơn hàng của người dùng hiện tại
    order = Order.objects.filter(user=request.user).order_by('-order_date')
    return render(request, 'base/history.html', {'order': order})
#cac dơn hang cua khach
@login_required
def order_history(request):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user,status='approved')

    orders = Order.objects.filter(user=request.user).order_by('-order_date')  # Get all orders for the user, ordered by date
    
    return render(request, 'base/order_history.html', {'orders': orders ,'stores':stores,'sent':sent})

#chi tiet don hang
def order_detail(request, order_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user)
    order = get_object_or_404(Order, id=order_id, user=request.user)  # Ensure the order belongs to the logged-in user
    order_items = order.orderdetail_set.all()  # Retrieve all items associated with this order
    
    # Calculate the total amount
    total_amount = sum(item.subtotal for item in order_items)
    
    return render(request, 'base/order_detail.html', {
        'order': order,
        'order_items': order_items,
        'stores': stores,
        'total_amount': total_amount,
        'sent':sent
    })




@login_required
def toggle_like(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.user in store.liker.all():
        store.liker.remove(request.user)
    else:
        store.liker.add(request.user)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@login_required
def liked_stores(request):
    # Lấy tất cả cửa hàng mà người dùng hiện tại thích
    store = Store.objects.filter(liker=request.user).order_by('name')
    stores = Store.objects.filter(owner=request.user,status ="approved").order_by('name')

    
    # Truyền kết quả vào template
    return render(request, 'base/liked_stores.html', {'stores': stores,'store':store})
#Event Funtion Start

def event(request):
    invitations = Invitation.objects.filter(invitee=request.user, accepted=False)

    q = request.GET.get('q') if request.GET.get('q') != None else ''
    event = Event.objects.filter(
        Q(title__icontains =q) |
        Q(location__icontains = q),
        is_private = False,
        status='approved'
    )
    context = {'event':event,'invitations':invitations}

    return render(request,'base/event.html',context)



#hiển thị event chi tiết
def eventDetail(request,pk):
    event = Event.objects.get(id=pk)

    messages = event.messages.all()
    if request.method == 'POST':
        message = EventMessage.objects.create(
            user = request.user,
            event = event,
            body =request.POST.get('body'),
            image =request.FILES.get('image'),
            )
        return redirect('event_detail',pk=event.id)
        # context = {'rooms':room, 'message':messages,
        #            'created_at': datetime.now(),  # Dummy value, replace it with the actual creation time
        #             'message_id': None}
    
    context = {'event':event ,'message':messages,}

    return render(request,'base/event-detail.html',context)



#Hiển thị các event của tôi
def myevent(request):
    invitations = Invitation.objects.filter(invitee=request.user, accepted=False)

    event = Event.objects.filter(host=request.user)
    context = {'event':event,'invitations':invitations}
    return render(request,'base/event.html',context)

#Hiển thị các event tôi sẽ tham gia
def eventJoined(request):
    invitations = Invitation.objects.filter(invitee=request.user, accepted=False)

    event = Event.objects.filter(par=request.user)
    context = {'event':event,'invitations':invitations}
    return render(request,'base/event.html',context)


#Quan tâm đến event
def careAbout(request,pk):
    event = get_object_or_404(Event, id=pk)
    # Giả sử 'par' là một ManyToManyField liên kết với User
    event.par.add(request.user)

    # Redirect người dùng sau khi thêm vào danh sách quan tâm
    # Thay thế 'event-detail' với tên pattern URL của trang chi tiết sự kiện
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))



#Bỏ quan tâm event
def discareAbout(request,pk):
    event = get_object_or_404(Event, id=pk)
    # Giả sử 'par' là một ManyToManyField liên kết với User
    event.par.remove(request.user)

    # Redirect người dùng sau khi thêm vào danh sách quan tâm
    # Thay thế 'event-detail' với tên pattern URL của trang chi tiết sự kiện
    Invitation.objects.filter(event=event, invitee=request.user).delete()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

#event

#Tạo một Event


@login_required(login_url='login')
def createEvent(request):
    form = EventsForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            event = form.save(commit=False)
            event.status = "waiting"
            event.host = request.user
            event.save()
            event.par.add(request.user)  # Add the host to the participants
            event.save()

            return redirect('event')
    else:
        form = EventsForm()
    
    # Lấy tất cả các sự kiện đã được phê duyệt (approved)


    context = {'form': form}
    return render(request, 'base/event_form.html', context)


#Update một event
@login_required
def update_event(request, pk):
    event = get_object_or_404(Event, id=pk, host=request.user)  # Đảm bảo chỉ host mới có thể cập nhật
    if request.method == 'POST':
        form = EventsForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            event.status = "waiting"
            form.save()
            return redirect('event_detail', pk=event.id)
    else:
        form = EventsForm(instance=event)
    return render(request, 'base/event_form.html', {'form': form})


#Xóa một event
def delete_event(request, pk):
    event = get_object_or_404(Event, id=pk, host=request.user)  # Đảm bảo chỉ host mới có thể xóa
    if request.method == 'POST':
        event.delete()
        return redirect('event')
    return render(request, 'base/delete.html', {'event': event})


#Hiển thị các bạn bè chưa tham gia vào event
def friends_not_in_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    # Get all accepted friendships for the user
    user_friendships = Friendship.objects.filter(
        (Q(sender=request.user) | Q(receiver=request.user)),
        status='accepted'
    )

    # Extract all friend user objects
    friends = set()
    for friendship in user_friendships:
        friend = friendship.receiver if friendship.sender == request.user else friendship.sender
        friends.add(friend)

    # Get all users who are already participating in the event
    participants = set(event.par.all())

    # Determine which friends are not participating in the event
    non_participating_friends = friends - participants

    search_query = request.GET.get('search', '')  # Get the search parameter from the URL
    if search_query:
        non_participating_friends = [friend for friend in non_participating_friends if search_query.lower() in friend.username.lower()]
    invited_ids = list(Invitation.objects.filter(event=event).values_list('invitee_id', flat=True))
    return render(request, 'base/invite.html', {
        'event': event,
        'non_participating_friends': non_participating_friends,
        'search_query': search_query,
        'invited_ids':invited_ids
    })


#Gửi lời mời tham gia vào event
def send_invitation(request, event_id, user_id):
    event = get_object_or_404(Event, pk=event_id)
    
    # Check if the user making the request is the host of the event
    
    
    invitee = get_object_or_404(User, pk=user_id)
    
    # Check if an invitation has already been sent to this user for this event
    if Invitation.objects.filter(event=event, invitee=invitee).exists():
        return HttpResponse("An invitation has already been sent to this user.", status=400)

    # Check if the user is already a participant of the event
    if event.par.filter(pk=user_id).exists():
        return HttpResponse("This user is already a participant of the event.", status=400)
    
    # Create and save the new invitation
    invitation = Invitation(event=event, invitee=invitee)
    invitation.save()
    

    # Redirect to the event detail page or where you want to show the success message
    return redirect('events', event_id=event.id)

#Xem thông báo mời vào event
@login_required
def view_invitations(request):
    # Fetch invitations for the logged-in user
    invitations = Invitation.objects.filter(invitee=request.user, accepted=False)
    
    return render(request, 'base/Notification_event.html', {
        'invitations': invitations
    })

#đồng ý vào event
@login_required
def accept_invitation(request, invitation_id):
    invitation = get_object_or_404(Invitation, pk=invitation_id, invitee=request.user)
    invitation.accepted = True
    invitation.save()
    # Add the user to the event participants
    invitation.event.par.add(request.user)
    return redirect('event_detail', pk=invitation.event.id)

@login_required
def liked_events(request):
    liked_events = Event.objects.filter(like=request.user)
    return render(request, 'base/liked_events.html', {'liked_events': liked_events})

#thích event 
@login_required
def like_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.user in event.like.all():
        event.like.remove(request.user)
    else:
        event.like.add(request.user)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@login_required
def dislike_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.user in event.like.all():
        event.like.remove(request.user)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@login_required
@require_POST
@csrf_exempt
def dislike_selected_events(request):
    if request.method == 'POST':
        event_ids = request.POST.getlist('event_ids[]')
        events = Event.objects.filter(id__in=event_ids, like=request.user)

        for event in events:
            event.like.remove(request.user)

        return JsonResponse({'status': 'success', 'message': f'{len(events)} events disliked'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

#từ chối vào event
@login_required
def decline_invitation(request, invitation_id):
    invitation = get_object_or_404(Invitation, pk=invitation_id, invitee=request.user)
    invitation.delete()
    return redirect('view_invitations')







def password_reset_request(request):
    if request.method == "POST":
        email = request.POST['email']
        user = User.objects.filter(email=email).first()
        if user is not None:
            # Tạo mã xác nhận
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            # Lưu mã vào session để kiểm tra sau này
            request.session['password_reset_code'] = code
            request.session['user_email'] = email
            request.session['password_reset_sent_at'] = datetime.now().timestamp()  # Lưu thời gian gửi mã
            
            # Gửi email
            send_mail(
                'Password Reset Confirmation Code',
                f'Your confirmation code is: {code}',
                'from@example.com',
                [email],
                fail_silently=False,
            )
            return redirect('enter_reset_code')  # Chuyển hướng đến trang nhập mã xác nhận
    return render(request, 'base/password_reset_request.html')



def enter_reset_code(request):
    if request.method == "POST":
        code = request.POST['code']
        current_time = now().timestamp()
        sent_at = request.session.get('password_reset_sent_at', 0)
        
        # Kiểm tra nếu mã đã quá 1 phút
        if current_time - sent_at > 60:  # 60 giây
            del request.session['password_reset_code']
            del request.session['user_email']
            return render(request, 'base/enter_reset_code.html', {'error': 'Mã xác nhận đã hết hạn.'})
        if code == request.session.get('password_reset_code'):
            # Nếu mã chính xác, cho phép đặt lại mật khẩu
            return redirect('reset_password')
        else:
            # Nếu mã không chính xác, thông báo lỗi
            return render(request, 'base/enter_reset_code.html', {'error': 'Mã không chính xác.'})
    return render(request, 'base/enter_reset_code.html',{'sent_at': request.session.get('password_reset_sent_at')})




def reset_password(request):
    if request.method == "POST":
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # Kiểm tra xem hai mật khẩu có giống nhau không
        if new_password == confirm_password:
            email = request.session.get('user_email')
            if email:
                user = User.objects.get(email=email)
                user.password = make_password(new_password)
                user.save()
                # Xóa session
                del request.session['password_reset_code']
                del request.session['user_email']
                return redirect('login')  # Hoặc trang thông báo đặt lại thành công
        else:
            # Nếu mật khẩu không khớp, hiển thị thông báo lỗi
            context = {'error': 'Mật khẩu và mật khẩu xác nhận không khớp.', 'new_password': new_password, 'confirm_password': confirm_password}
            return render(request, 'base/reset_password.html', context)

    return render(request, 'base/reset_password.html')



@login_required
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST['old_password']
        new_password = request.POST['new_password']
        confirm_password = request.POST['confirm_password']

        if not request.user.check_password(old_password):
            # Nếu mật khẩu cũ không đúng
            messages.error(request, 'Mật khẩu cũ không chính xác.')
            return redirect('change_password')

        if new_password != confirm_password:
            # Nếu mật khẩu mới và xác nhận mật khẩu không khớp
            messages.error(request, 'New password and confirm password do not match.')
            return redirect('change_password')

        # Cập nhật mật khẩu mới
        user = request.user
        user.set_password(new_password)
        user.save()

        # Cập nhật session để người dùng không bị đăng xuất sau khi đổi mật khẩu
        update_session_auth_hash(request, user)

        messages.success(request, 'Password has been updated successfully.')
        return redirect('change_password')

    return render(request, 'base/change_password.html')




@login_required
def report_mess(request):
    if request.method == 'POST':
        reported_message_id = request.POST.get('reported_message_id')
        reasons = request.POST.get('reasons').split(',')
        detail = request.POST.get('detail', '')

        try:
            reported_message = get_object_or_404(Message, id=reported_message_id)
            for reason in reasons:
                report = MessageReport.objects.create(
                    reported_message=reported_message,
                    reason=reason,
                    detail=detail
                )
                report.reporting_users.add(request.user)
            return JsonResponse({'success': True})
        except Message.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Message not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})



# Admin
@role_required(allowed_roles=['AD'])
def manageUser(request):
    query = request.GET.get('q', '')
    users = User.objects.exclude(id=request.user.id).exclude(is_banned=True)
    
    if query:
        users = users.filter(username__icontains=query).distinct()
    return render(request,'base/manage.html',{'users':users})





@login_required
def ban_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.is_banned = True
    user.save()
    Message.objects.filter(user=user).delete()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@login_required
def unban_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.is_banned = False
    user.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@role_required(allowed_roles=['AD'])
def manageUserBanned(request):
    query = request.GET.get('q', '')
    users = User.objects.exclude(id=request.user.id).exclude(is_banned=False)
    
    if query:
        users = users.filter(username__icontains=query).distinct()
    return render(request,'base/manage-ban.html',{'users':users})


@role_required(allowed_roles=['AD','MO'])
def reported_messages(request):
    query = request.GET.get('q', '')

    reports = MessageReport.objects.prefetch_related(
        Prefetch('reporting_users', queryset=User.objects.all()),
        'reported_message__room',
    ).annotate(report_count=Count('reporting_users', distinct=True))  # Ensure we're counting unique users

    if query:
        reports = reports.filter(
            Q(reason__icontains=query) | 
            Q(detail__icontains=query) | 
            Q(reported_message__body__icontains=query) |
            Q(reporting_users__username__icontains=query)
        ).distinct()

    return render(request, 'base/manage-report.html', {'reports': reports, 'query': query})



@role_required(allowed_roles=['AD','MO'])
def manageRoom(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    rooms = Room.objects.filter(
        Q(topic__name__icontains =q) |
        Q(name__icontains = q)
    )


    return render(request,'base/manage-room.html',{'rooms':rooms})


@role_required(allowed_roles=['AD','MO'])
def manageStore(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    stores = Store.objects.filter(
        Q(owner__name__icontains =q) |
        Q(description__icontains =q) |
        Q(name__icontains = q),status = "waiting"
    )


    return render(request,'base/manage_store.html',{'stores':stores})




@role_required(allowed_roles=['AD'])
def create_account(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        name = request.POST.get('name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'base/create-account.html')
        
        try:
            user = User.objects.create_user(username=email, email=email, password=password1)
            user.name = name 
            role = request.POST.get('role')
            if role in [choice[0] for choice in User.UserRole.choices]:  # Validate role choice
                user.role = role
            else:
                messages.error(request, "Invalid role selected.")
                return render(request, 'base/create-account.html')
            user.save()
            return redirect('manage')  # Adjust 'home' to your home URL name
        except Exception as e:
            messages.error(request, str(e))
            return render(request, 'base/create-account.html')
    
    return render(request, 'base/create-account.html')


@role_required(allowed_roles=['AD','MO'])
def ManageEvent(request):
    invitations = Invitation.objects.filter(invitee=request.user, accepted=False)

    q = request.GET.get('q') if request.GET.get('q') != None else ''
    event = Event.objects.filter(
        Q(title__icontains =q) |
        Q(location__icontains = q),
        is_private = False,
        status='waiting'
    )
    context = {'event':event,'invitations':invitations}

    return render(request,'base/manage-event.html',context)


def approve_event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    event.status = 'approved'
    event.save()
    return redirect('manage_event')

def reject_event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    event.status = 'rejected'
    event.save()
    return redirect('manage_event')

def approve_store(request, pk):
    store = get_object_or_404(Store, pk=pk)
    store.status = 'approved'
    store.save()
    return redirect('manage_stores')

def reject_store(request, pk):
    store = get_object_or_404(Store, pk=pk)
    store.status = 'rejected'
    store.save()
    return redirect('manage_stores')




@role_required(allowed_roles=['AD','MO'])
def manageProduct(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    products = Product.objects.filter(
        Q(store__name__icontains =q) |
        Q(description__icontains =q) |
        Q(name__icontains = q),status = "waiting"
    )


    return render(request,'base/manage_product.html',{'products':products})


def approve_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.status = 'approved'
    product.save()
    return redirect('manage_products')

def reject_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.status = 'rejected'
    product.save()
    return redirect('manage_products')



def user_suggestions(request):
    query = request.GET.get('query', '')
    users = User.objects.filter(username__icontains=query)[:5]
    suggestions = [{'id': user.id, 'username': user.username} for user in users]
    return JsonResponse({'suggestions': suggestions})


def delete_event_message(request, event_id, message_id):
    # Lấy tin nhắn cụ thể
    message = get_object_or_404(EventMessage, id=message_id)
    
    # Kiểm tra quyền truy cập: chỉ người tạo tin nhắn mới có thể xóa nó
    if request.user == message.user:
        # Xóa tin nhắn
        message.delete()
    
    # Chuyển hướng người dùng đến trang chi tiết sự kiện sau khi xóa tin nhắn
    return redirect('event_detail', pk=event_id)




@role_required(allowed_roles=['AD','MO'])
#analys 
def top_stores_by_revenue(request):
    current_month = datetime.now().month
    current_year = datetime.now().year
    selected_month = int(request.GET.get('month', current_month))
    selected_year = int(request.GET.get('year', current_year))

    # Filter orders by the selected month and year
    orders = Order.objects.filter(order_date__year=selected_year, order_date__month=selected_month)
    
    # Annotate and aggregate revenue per store
    store_revenues = orders.values('orderdetail__product__store__name') \
        .annotate(total_revenue=Sum('orderdetail__subtotal')) \
        .order_by('-total_revenue')[:5]

    # Prepare data for the dropdowns
    months = range(1, 13)
    years = Order.objects.dates('order_date', 'year', order='DESC').distinct()

    # Convert Decimal to float for JSON serialization
    labels = [store['orderdetail__product__store__name'] for store in store_revenues]
    data = [float(store['total_revenue']) for store in store_revenues]

    context = {
        'labels': json.dumps(labels),
        'data': json.dumps(data),
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months': months,
        'years': years,
    }

    return render(request, 'base/top_store_revenue.html', context)


@role_required(allowed_roles=['AD','MO'])
def top_products_by_month(request):
    current_month = datetime.now().month
    current_year = datetime.now().year

    # Validate and get month and year from request, default to current month and year if invalid
    try:
        selected_month = int(request.GET.get('month', current_month))
        if not 1 <= selected_month <= 12:
            selected_month = current_month
    except (ValueError, TypeError):
        selected_month = current_month

    try:
        selected_year = int(request.GET.get('year', current_year))
    except (ValueError, TypeError):
        selected_year = current_year

    # Filter orders by the selected month and year
    order_details = OrderDetail.objects.filter(order__order_date__year=selected_year, order__order_date__month=selected_month)
    
    # Annotate and aggregate quantity per product
    product_sales = order_details.values('product__name') \
        .annotate(total_quantity=Sum('quantity')) \
        .order_by('-total_quantity')[:10]

    # Prepare data for the dropdowns
    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    years = OrderDetail.objects.dates('order__order_date', 'year', order='DESC').distinct()

    # Prepare data for the chart
    labels = [item['product__name'] for item in product_sales]
    data = [item['total_quantity'] for item in product_sales]

    context = {
        'labels': json.dumps(labels),
        'data': json.dumps(data),
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months': months,
        'years': years,
    }

    return render(request, 'base/top_products_by_month.html', context)


def unauthorized(request):
    return render(request, 'base/unauthorized.html')








# Notification


