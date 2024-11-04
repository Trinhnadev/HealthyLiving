import calendar
import json
import os
import re
import random
import threading
import time
from django.conf import settings
from django.forms import FloatField
from django.shortcuts import render,redirect
from django.contrib import messages
from django.http import HttpResponse
from .models import Room, Topic, Message ,User , Friendship ,Chat ,Product,Order,OrderDetail, Cart , CartItem , Event,Invitation,Store,ChatRoom,MessageReport,Post,Comment,Share,JoinRequest
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
from django.template.loader import render_to_string
from pytz import timezone as pytz_timezone
from django.utils.html import escape
from django.contrib.auth.hashers import check_password
# Múi giờ Việt Nam
VIETNAM_TZ = pytz_timezone('Asia/Ho_Chi_Minh')

from itertools import chain
from operator import attrgetter

@login_required(login_url='login')

def home(request):
    q = request.GET.get('q') if request.GET.get('q') is not None else ''
    user = request.user

    user_rooms = Room.objects.filter(host=user)

    # Count the total number of pending join requests for the user's rooms
    total_pending_requests = JoinRequest.objects.filter(room__in=user_rooms, status='pending').count()


    cart = user.cart if hasattr(user, 'cart') else None
    total_cart_quantity = cart.items.aggregate(total_quantity=Sum('quantity'))['total_quantity'] if cart else 0 
    # Query for topics, chat rooms, and friendship requests
    topic = Topic.objects.all()[:5]
    chat_rooms = ChatRoom.objects.filter(members=user)
    sent = Friendship.objects.filter(receiver=request.user, status='pending')

    # Query for rooms, posts, and shares based on the search query
    rooms = Room.objects.filter(
        Q(topic__name__icontains=q) |
        Q(name__icontains=q)
    )
    posts = Post.objects.filter(
        Q(title__icontains=q) |
        Q(content__icontains=q)
    )
    shares = Share.objects.filter(
        Q(post__title__icontains=q) |
        Q(post__content__icontains=q)
    ).select_related('post')

    # Combine the rooms, posts, and shares into a single queryset, ordered by creation time
    combined_content = sorted(
        chain(rooms, posts, shares),
        key=attrgetter('created_at'),  # assuming `created_at` is a common field
        reverse=True
    )

    room_message = Message.objects.filter(
        Q(room__topic__name__icontains=q)
    )[:5]

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

    combined_notifications = sorted(
        chain(invitations, sent),
        key=attrgetter('created_at'),
        reverse=True
    )

    # Call the friend suggestion function
    friend_suggestions = suggest_friends(user)

    # Include friend suggestions in the context
    context = {
        'combined_content': combined_content,
        'topic': topic,
        'chat_rooms': chat_rooms,
        'room_message': room_message,
        'random_users': random_users,
        'users': accepted_friends,
        'combined_notifications': combined_notifications,
        'friend_suggestions': friend_suggestions,  # Adding friend suggestions to context
        'total_pending_requests':total_pending_requests,
        'total_cart_quantity': total_cart_quantity 
    }

    return render(request, 'base/home.html', context)


# Suggest Friend
def suggest_friends(user):
    # Step 1: Get the list of all users except the current user and their friends
    all_users = User.objects.exclude(id=user.id)
    
    # Get all accepted friends
    user_friends_sent = user.friendship_sent.filter(status='accepted').values_list('receiver_id', flat=True)
    user_friends_received = user.friendship_received.filter(status='accepted').values_list('sender_id', flat=True)
    user_friends = set(user_friends_sent) | set(user_friends_received)
    
    # Exclude friends from the list of potential friends
    all_users = all_users.exclude(id__in=user_friends)
    
    # Exclude users who have a pending friendship request
    pending_requests = user.friendship_sent.filter(status='pending').values_list('receiver_id', flat=True)
    pending_requests_received = user.friendship_received.filter(status='pending').values_list('sender_id', flat=True)
    all_users = all_users.exclude(id__in=pending_requests).exclude(id__in=pending_requests_received)

    # Step 2: Calculate weights for each user and also count mutual friends
    suggestions = defaultdict(lambda: {'score': 0, 'mutual_friends': 0, 'shared_groups': 0, 'interaction_score': 0})

    for potential_friend in all_users:
        # Count mutual friends
        mutual_connections = User.objects.filter(
            id__in=user_friends
        ).filter(
            id__in=Friendship.objects.filter(receiver=potential_friend, status='accepted').values_list('sender_id', flat=True)
        ).count()

        suggestions[potential_friend]['mutual_friends'] = mutual_connections
        suggestions[potential_friend]['score'] += mutual_connections * 2  # Increased weight for mutual friends

        # Calculate Shared Groups Weight (SGW)
        shared_groups = Room.objects.filter(participants=user).filter(participants=potential_friend).count()
        suggestions[potential_friend]['shared_groups'] = shared_groups
        suggestions[potential_friend]['score'] += shared_groups * 1.5  # Weight for shared groups

        # Calculate Interaction History Weight (IHW)
        interaction_count = Comment.objects.filter(
            Q(post__author=user, user=potential_friend) |
            Q(post__author=potential_friend, user=user)
        ).count()
        suggestions[potential_friend]['interaction_score'] = interaction_count
        suggestions[potential_friend]['score'] += interaction_count * 1.8  # Weight for interactions

    # Step 4: Sort by the highest scoring users
    sorted_suggestions = sorted(suggestions.items(), key=lambda x: x[1]['score'], reverse=True)

    # Step 5: Return the top N suggestions (e.g., top 10)
    top_suggestions = [{'user': user,
                        'mutual_friends': data['mutual_friends'],
                        'shared_groups': data['shared_groups'], 
                        'interaction_score': data['interaction_score']}
                       for user, data in sorted_suggestions[:10]]

    return top_suggestions

@login_required(login_url='login')
def userProfile(request, pk):
    # Fetch the user profile
    user_profile = get_object_or_404(User, id=pk)
    current_user = request.user
    
    # Query for friendships and chat rooms
    friendship = Friendship.objects.filter(
        Q(sender=current_user, receiver=user_profile) | Q(sender=user_profile, receiver=current_user)
    ).first()

    accepted_friends = Friendship.objects.filter(
        Q(sender=current_user, status='accepted') | 
        Q(receiver=current_user, status='accepted')
    )

    chat_room = ChatRoom.objects.filter(members=current_user).filter(members=user_profile).first()
    if not chat_room and friendship and friendship.status == 'accepted':
        chat_room = ChatRoom.objects.create()
        chat_room.members.add(current_user, user_profile)

    # Query for topics
    topic = Topic.objects.all()[:5]

    # Query for rooms, posts, and shares associated with the user profile
    rooms = Room.objects.filter(host=user_profile)
    posts = Post.objects.filter(author=user_profile)
    shares = Share.objects.filter(user=user_profile).select_related('post')

    print(shares)

    # Combine the rooms, posts, and shares into a single queryset, ordered by creation time
    combined_content = sorted(
        chain(rooms, posts, shares),
        key=attrgetter('created_at'),
        reverse=True
    )
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    invitations = Invitation.objects.filter(invitee=request.user, accepted=False)
    accepted_friends = Friendship.objects.filter(
        Q(sender=request.user, status='accepted') | 
        Q(receiver=request.user, status='accepted')
    )
    combined_notifications = sorted(
        chain(invitations, sent),
        key=attrgetter('created_at'),
        reverse=True
    )

    # Query for recent messages and friendship requests
    room_message = Message.objects.filter(room__participants=user_profile)[:5]
    sent_requests = Friendship.objects.filter(receiver=current_user, status='pending')

    # Query for users in the same rooms
    users_in_same_rooms = User.objects.filter(room__participants=user_profile).exclude(id=user_profile.id)
    user_counts = users_in_same_rooms.values('id').annotate(room_count=Count('room')).order_by('-room_count')
    top_users = [entry['id'] for entry in user_counts]
    user_friends = user_profile.friendship_sent.filter(status='accepted').values_list('receiver_id', flat=True)
    random_users = User.objects.filter(id__in=top_users).exclude(id__in=user_friends)[:10]

    context = {
        'user': user_profile,
        'combined_content': combined_content,
        'rooms': rooms,
        'room_message': room_message,
        'topic': topic,
        'random_users': random_users,
        'users': accepted_friends,
        'sent': sent_requests,
        'friendship': friendship,
        'chat_room': chat_room,
        'combined_notifications':combined_notifications,
    }

    return render(request, 'base/profile.html', context)



@csrf_exempt
def comment(request, post_id):
        if request.method == 'POST':
            data = json.loads(request.body)
            comment = data.get('comment_text')
            post = Post.objects.get(id=post_id)
            try:
                newcomment = Comment.objects.create(post=post,user=request.user,content=comment)
                post.save()
                print(newcomment.serialize())
                return JsonResponse([newcomment.serialize()], safe=False, status=201)
            except Exception as e:
                return HttpResponse(e)
    
        post = Post.objects.get(id=post_id)
        print(post_id)
        comments = Comment.objects.filter(post=post)
        comments = comments.order_by('-created_at').all()  
        return JsonResponse([comment.serialize() for comment in comments], safe=False)

@login_required(login_url='login')

def userProfile(request, pk):
    # Fetch the user profile
    user_profile = get_object_or_404(User, id=pk)
    current_user = request.user

    # Query for friendships and chat rooms
    friendship = Friendship.objects.filter(
        Q(sender=current_user, receiver=user_profile) | Q(sender=user_profile, receiver=current_user)
    ).first()

    accepted_friends = Friendship.objects.filter(
        Q(sender=current_user, status='accepted') | 
        Q(receiver=current_user, status='accepted')
    )

    chat_room = ChatRoom.objects.filter(members=current_user).filter(members=user_profile).first()
    if not chat_room and friendship and friendship.status == 'accepted':
        chat_room = ChatRoom.objects.create()
        chat_room.members.add(current_user, user_profile)

    # Query for topics
    topic = Topic.objects.all()[:5]

    # Query for rooms, posts, and shares associated with the user profile
    rooms = Room.objects.filter(participants=user_profile)
    posts = Post.objects.filter(author=user_profile)
    # shares = Share.objects.filter(user=user_profile).select_related('post')

    # Combine the rooms, posts, and shares into a single queryset, ordered by creation time
    combined_content = sorted(
        chain(rooms, posts),
        key=attrgetter('created_at'),
        reverse=True
    )

    # Query for recent messages and friendship requests
    room_message = Message.objects.filter(room__participants=user_profile)[:5]
    sent_requests = Friendship.objects.filter(receiver=current_user, status='pending')

    # Query for users in the same rooms
    users_in_same_rooms = User.objects.filter(room__participants=user_profile).exclude(id=user_profile.id)
    user_counts = users_in_same_rooms.values('id').annotate(room_count=Count('room')).order_by('-room_count')
    top_users = [entry['id'] for entry in user_counts]
    user_friends = user_profile.friendship_sent.filter(status='accepted').values_list('receiver_id', flat=True)
    random_users = User.objects.filter(id__in=top_users).exclude(id__in=user_friends)[:10]

    context = {
        'user': user_profile,
        'combined_content': combined_content,
        'rooms': rooms,
        'room_message': room_message,
        'topic': topic,
        'random_users': random_users,
        'users': accepted_friends,
        'sent': sent_requests,
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

@login_required(login_url='login')

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
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Sử dụng authenticate để kiểm tra thông tin đăng nhập
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Thêm bước kiểm tra để xem người dùng có bị cấm không
            if user.is_banned:
                login_result = 'Your account has been banned. Please contact support.'
            else:
                login(request, user)
                return redirect('home')
        else:
            login_result = 'Incorrect credentials. Please try again.'

    context = {'page': page, 'login_result': login_result}
    return render(request, 'base/login_sign.html', context)





def sign(request):
    page = 'sign'
    form = MyUserCreationForm()
    login_result = ''
    
    if request.method == 'POST':
        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email').lower()
            if User.objects.filter(email=email).exists():
                login_result = 'This email is already registered.'
            else:
                user = form.save(commit=False)
                user.username = user.username.lower()
                user.save()
                login(request, user)
                return redirect('home')
        else:
            login_result = 'Registration failed. Please check the information.'

    context = {'form': form, 'page': page, 'login_result': login_result}
    return render(request, 'base/login_sign.html', context)


def logoutUser(request):
    logout(request)
    return redirect('login')

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
@login_required(login_url='login')

@login_required(login_url='login')
def room(request, pk):
    room = Room.objects.get(id=pk)
    pa = room.participants.all()
    messages = room.message_set.all()
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    join_request = JoinRequest.objects.filter(user=request.user, room=room).first()

    # Kiểm tra nếu người dùng đã tham gia phòng hoặc là chủ phòng
    if request.user == room.host or room.is_private == False or request.user in pa:
        if request.method == 'POST' and 'body' in request.POST:
            message = Message.objects.create(
                user=request.user,
                room=room,
                body=request.POST.get('body'),
                image=request.FILES.get('image'),
            )
            room.participants.add(request.user)  # Thêm người dùng vào phòng
            return redirect('room', pk=room.id)

        context = {
            'rooms': room,
            'message': messages,
            'participants': pa,
            'sent': sent
        }
        return render(request, 'base/room.html', context)

    # Nếu phòng là private và người dùng chưa tham gia
    if room.is_private and request.user not in pa:
        if join_request and join_request.status == 'pending':
            # Nếu đã gửi yêu cầu, hiển thị trạng thái yêu cầu đang chờ phê duyệt
            return redirect('home')
        
        if request.method == 'POST' and 'message' in request.POST:
            # Tạo yêu cầu tham gia mới
            join_request = JoinRequest.objects.create(
                user=request.user,
                room=room,
                message=request.POST.get('message')
            )
            return redirect('home')

        return render(request, 'base/room_question.html', {'room': room, 'sent': sent})

def my_rooms(request):
    # Lấy các phòng mà người dùng hiện tại đã tham gia hoặc là chủ phòng
    rooms = Room.objects.filter(host=request.user).annotate(pending_requests_count=Count('join_requests', filter=Q(join_requests__status='pending')))

    context = {
        'rooms': rooms  # Truyền danh sách phòng và số lượng request vào context để hiển thị trong template
    }
    return render(request, 'base/my_room.html', context)
    
@login_required(login_url='login')
def manage_join_requests(request, room_id):
    rooms = Room.objects.filter(host=request.user).annotate(pending_requests_count=Count('join_requests', filter=Q(join_requests__status='pending')))

    room = Room.objects.get(id=room_id)
    
    # Chỉ chủ phòng mới có thể quản lý yêu cầu tham gia
    if request.user != room.host:
        return redirect('home')

    join_requests = JoinRequest.objects.filter(room=room, status='pending')

    if request.method == 'POST':
        join_request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        join_request = JoinRequest.objects.get(id=join_request_id)

        if action == 'approve':
            join_request.status = 'approved'
            join_request.save()
            room.participants.add(join_request.user)  # Thêm người dùng vào phòng
        elif action == 'reject':
            join_request.status = 'rejected'
            join_request.save()

        return redirect('manage_join_requests', room_id=room.id)

    return render(request, 'base/my_room.html', {'room': room,'rooms':rooms, 'join_requests': join_requests})



#can dang nhap moi dung dc
@login_required(login_url='login')

def createRoom(request):
    form = RoomForm()
    topics = Topic.objects.all()
    sent = Friendship.objects.filter(receiver=request.user, status='pending')

    if request.method == 'POST':
        # Lấy giá trị từ form
        topic_name = request.POST.get('topic')
        room_name = request.POST.get('name')
        room_description = request.POST.get('description')
        is_private = request.POST.get('is_private')

        # Kiểm tra nếu bất kỳ trường nào bị bỏ trống
        if not topic_name or not room_name or not room_description or is_private is None:
            messages.error(request, 'All fields are required. Please fill out the form completely.', extra_tags='room_error')
            return render(request, 'base/room_form.html', {'form': form, 'topics': topics, 'sent': sent})

        # Tạo hoặc lấy Topic
        topic, created = Topic.objects.get_or_create(name=topic_name)
        
        # Tạo phòng mới
        room = Room.objects.create(
            host=request.user,
            topic=topic,
            name=room_name,
            description=room_description,
            is_private=is_private == 'True'
        )
        
        # Thêm chủ phòng vào danh sách participants
        room.participants.add(request.user)
        
        return redirect('home')

    context = {
        'form': form,
        'topics': topics,
        'sent': sent
    }
    return render(request, 'base/room_form.html', context)


    


@login_required(login_url='login')
def updateRoom(request, pk):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    room = Room.objects.get(id=pk)
    form = RoomForm(instance=room)
    topics = Topic.objects.all()
    
    if request.user != room.host:
        return HttpResponse('')

    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        room_name = request.POST.get('name')
        room_description = request.POST.get('description')
        is_private = request.POST.get('is_private')

        # Kiểm tra các trường có bị bỏ trống hay không
        if not topic_name or not room_name or not room_description or is_private is None:
            messages.error(request, 'All fields are required. Please fill out the form completely.')
            return render(request, 'base/room_form.html', {'form': form, 'topics': topics, 'room': room, 'sent': sent})

        # Lấy hoặc tạo mới Topic
        topic, created = Topic.objects.get_or_create(name=topic_name)

        # Cập nhật thông tin phòng
        room.name = room_name
        room.topic = topic
        room.description = room_description
        room.is_private = is_private == 'True'

        # Cập nhật câu hỏi và câu trả lời chỉ khi phòng là private
        if room.is_private:
            room.question = request.POST.get('question')
            room.answer = request.POST.get('answer')
        else:
            room.question = ''
            room.answer = ''

        room.save()

        return redirect('home')

    context = {
        'form': form,
        'topics': topics,
        'room': room,
        'sent': sent
    }
    return render(request, 'base/room_form.html', context)



@login_required(login_url='login')
def delete_room(request, room_id):
    room = get_object_or_404(Room, id=room_id)

    if request.method == 'POST':
        # Kiểm tra quyền của người dùng
        if request.user == room.host:
            room.delete()
            messages.success(request, 'The room was successfully deleted.')
        else:
            messages.error(request, 'You are not authorized to delete this room.')
        
        return redirect('home')  # Redirect về trang chủ sau khi xóa


@login_required(login_url='login')
def deleteMessage(request,pk):
    message = Message.objects.get(id = pk)
    # message = get_object_or_404(Message, id=pk)
    if request.user == message.user or request.user.is_admin:
        if request.method == 'POST':
            message.delete()
            return redirect('room',pk=message.room.id)




def topicsPage(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topics = Topic.objects.filter(name__icontains = q)
    return render(request,'base/topics.html',{'topics':topics})

#FriendShip Function
@login_required(login_url='login')

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


@login_required(login_url='login')

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

@login_required(login_url='login')

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



@login_required(login_url='login')

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


@login_required(login_url='login')

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
        
        
    else:
        messages.warning(request, 'No pending friend request found.')

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@login_required(login_url='login')

def reject(request, pk):
    sender = get_object_or_404(User, pk=pk)

    friendship_request = Friendship.objects.filter(
        (Q(sender=sender, receiver=request.user) | Q(sender=request.user, receiver=sender)),
        status__in=['pending', 'accepted']
    ).first()
    chat_room = ChatRoom.objects.filter(members=sender).filter(members=request.user).distinct().first()

    print(chat_room)
    if friendship_request:
        # If the status is 'accepted', update it to 'rejected'
        if friendship_request.status == 'accepted':
            friendship_request.delete()
            if chat_room:
                chat_room.delete()
                
            else:
                messages.success(request, f'Friendship with {sender.username} has been ended.')
        # If the status is 'pending', delete the friend request
        elif friendship_request.status == 'pending':
            friendship_request.delete()
            
    else:
        messages.warning(request, 'No pending or accepted friend request found with this user.')

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@login_required(login_url='login')

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

@login_required(login_url='login')

def open_chat(request, pk):
    chat_room = get_object_or_404(ChatRoom, id=pk)
    chat_rooms = ChatRoom.objects.filter(members=request.user)
    messages = Chat.objects.filter(roomchat=chat_room).order_by('timestamp')

    friend = chat_room.members.exclude(id=request.user.id).first()

    accepted_friends = Friendship.objects.filter(
        (Q(sender=request.user) | Q(receiver=request.user)),
        status='accepted'
    )

    return render(request, 'base/chat.html', {
        'chat_room': chat_room,
        'chat_rooms': chat_rooms,
        'messages': messages,
        'friend': friend,
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
def shopping(request):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    q = request.GET.get('q', '')

    # Tìm kiếm sản phẩm trong cửa hàng của người dùng hiện tại
    products = Product.objects.filter(
        Q(description__icontains=q) | 
        Q(name__icontains=q),
        status='approved'
    )
    
    # Lấy store của người dùng hiện tại
    user_store = Store.objects.filter(owner=request.user, status='approved')
    
    # Tìm kiếm cửa hàng của người dùng hiện tại
    stores = user_store.filter(
        Q(name__icontains=q),
    )
    
    # Tính tổng số lượng sản phẩm trong giỏ hàng nếu người dùng đã đăng nhập
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        total_quantity = cart.items.aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0
    else:
        total_quantity = 0

    # Truyền tổng số lượng vào context để hiển thị trong template
    context = {
        'products': products,
        'stores': stores,
        'sent': sent,
        'total_quantity': total_quantity,  # Truyền tổng số lượng vào context
    }
    
    return render(request, 'base/store.html', context)

#done
@login_required(login_url='login')

def create_store(request):
    if request.method == 'POST':
        # Thêm request.FILES để xử lý các tệp được tải lên
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user  # Thiết lập người sở hữu cho cửa hàng là người dùng hiện tại
            store.status = "waiting"
            store.save()
            # Đảm bảo form m2m được lưu nếu có
            form.save_m2m()
            messages.success(request, 'Store created successfully!')
            return redirect('shop')  # Thay 'shop' bằng tên URL đích sau khi tạo cửa hàng thành công
        else:
            messages.error(request, 'Please fill in all required fields.')
    else:
        form = StoreForm()

    return render(request, 'base/store_form.html', {'form': form})



@login_required(login_url='login')

def update_store(request, pk):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    store = get_object_or_404(Store, pk=pk, owner=request.user)  # Chỉ chủ sở hữu mới được phép cập nhật

    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            store = form.save(commit=False)
            store.status = "waiting"  # Cập nhật trạng thái
            form.save()  # Lưu thay đổi
            messages.success(request, 'Store updated successfully.')
            return redirect('shop')
        else:
            messages.error(request, 'Please fill in all required fields.')
    else:
        form = StoreForm(instance=store)

    return render(request, 'base/store_form.html', {'form': form, 'store': store, 'sent': sent})



@login_required(login_url='login')

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



@login_required(login_url='login')

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
            messages.success(request, 'Product created successfully.')
            return redirect('store_products', store_id=store.id)
        else:
            messages.error(request, 'Please fill in all required fields.')
    else:
        form = ProductForm()
    
    return render(request, 'base/product_form.html', {'form': form, 'store': store, 'stores': stores, "sent": sent})

@login_required(login_url='login')
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
            messages.success(request, 'Product updated successfully.')
            return redirect('store_products', store_id=store.id)
        else:
            messages.error(request, 'Please fill in all required fields.')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'base/product_form.html', {'form': form, 'store': store, "sent": sent})



@login_required(login_url='login')

@require_POST
def update_product_quantity(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity'))

    product = get_object_or_404(Product, id=product_id)

    if quantity > 0:
        product.quantity += quantity
        product.save()

    return redirect('store_products', store_id=product.store.id)

@login_required(login_url='login')

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





@login_required(login_url='login')

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
    stores = Store.objects.filter(owner=request.user, status='approved')

    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        items = cart.items.all()
        total_price = cart.get_total_price()
        # Tính tổng số lượng sản phẩm trong giỏ hàng
        total_quantity = sum(item.quantity for item in items)
    else:
        items = []
        total_price = 0
        total_quantity = 0  # Không có sản phẩm nào nếu người dùng chưa đăng nhập

    context = {
        'cart_items': items,
        'total_price': total_price,
        'total_quantity': total_quantity,  # Truyền tổng số lượng vào context
        'stores': stores,
        "sent": sent,
    }
    return render(request, 'base/cart_detail.html', context)


@login_required(login_url='login')

def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    # Quay trở lại trang giỏ hàng sau khi xóa sản phẩm
    return redirect('cart_detail')

#cbi cxoas
@login_required(login_url='login')


def checkout(request):
    cart = request.user.cart
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        address = request.POST.get('address')

        # Phone number validation: starts with 0, exactly 10 digits, and no letters
        phone_regex = r'^0\d{9}$'
        
        if not re.match(phone_regex, phone_number):
            return render(request, 'base/cart_detail.html', {
                'error_message': 'Invalid phone number format.',
                'cart_items': cart.items.all(),
                'total_price': cart.get_total_price(),
                'form_data': request.POST,
            })

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
                    return render(request, 'base/cart_detail.html', {  # Update with your actual template name
                        'insufficient_stock': insufficient_stock,
                        'cart_items': cart.items.all(),
                        'total_price': cart.get_total_price(),
                        'form_data': request.POST,
                    })

                # Clear the cart after successful transaction
                cart.items.all().delete()

                # Redirect to an order confirmation page
                return redirect('order_detail', order.id)
        else:
            return render(request, 'base/cart_detail.html', {  # Update with your actual template name
                'error_message': 'Please fill out all fields.',
                'cart_items': cart.items.all(),
                'total_price': cart.get_total_price(),
                'form_data': request.POST,
            })

    return render(request, 'base/cart_detail.html', {  # Update with your actual template name
        'cart_items': cart.items.all(),
        'total_price': cart.get_total_price(),
    })


#dơn hang cua shop
@login_required(login_url='login')

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


@login_required(login_url='login')

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

@login_required(login_url='login')

def revenue(request, store_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user, status='approved')
    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        messages.error(request, "Store not found.")
        return redirect('store_order_history')

    # Get all orders containing at least one product from this store
    orders = Order.objects.filter(orderdetail__product__store=store).distinct().order_by('-order_date').prefetch_related('orderdetail_set__product__store')

    # Organize order data and order details by store
    store_orders = defaultdict(lambda: {'orders': [], 'total': 0, 'details': defaultdict(list)})

    for order in orders:
        # Create total price and details for each store in the order
        for detail in order.orderdetail_set.all():
            product_store = detail.product.store
            if product_store.id == store_id:  # Only handle products belonging to the designated store
                store_orders[product_store]['orders'].append(order)
                store_orders[product_store]['details'][order].append(detail)
                store_orders[product_store]['total'] += float(detail.subtotal)

    # Convert results from defaultdict to dict to avoid errors when passing into the template
    store_orders = dict((store, {'orders': data['orders'], 'total': data['total'], 'details': dict(data['details'])}) for store, data in store_orders.items())
    monthly_revenue = orders.annotate(month=ExtractMonth('order_date'))\
                        .values('month')\
                        .annotate(total_revenue=Sum('orderdetail__subtotal'), total_orders=Count('id'))\
                        .order_by('month')

    # Prepare data for the chart 
    revenue_per_month = [0] * 12
    orders_per_month = [0] * 12
    for revenue in monthly_revenue:
        revenue_per_month[revenue['month'] - 1] = revenue['total_revenue']
        orders_per_month[revenue['month'] - 1] = revenue['total_orders']

    revenue_per_month_float = [float(revenue) for revenue in revenue_per_month]

    # Total number of orders and total revenue
    total_orders = orders.count()
    total_revenue = sum(revenue_per_month_float)


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


@login_required(login_url='login')

def dashboard(request, store_id):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user, status="approved")
    store = get_object_or_404(Store, id=store_id)

    month = request.GET.get('month')
    if month and month != 'all':
        month = datetime.strptime(month, '%Y-%m')
        orders = Order.objects.filter(
            orderdetail__product__store=store,
            order_date__year=month.year,
            order_date__month=month.month
        ).distinct().order_by('-order_date').prefetch_related('orderdetail_set__product__store')
        
        top_products = OrderDetail.objects.filter(
            product__store=store,
            order__order_date__year=month.year,
            order__order_date__month=month.month
        ).values('product__name', 'product__image').annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('subtotal')
        ).order_by('-total_sold')[:5]
    else:
        orders = Order.objects.filter(
            orderdetail__product__store=store
        ).distinct().order_by('-order_date').prefetch_related('orderdetail_set__product__store')
        
        top_products = OrderDetail.objects.filter(
            product__store=store
        ).values('product__name', 'product__image').annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('subtotal')
        ).order_by('-total_sold')[:5]

    store_orders = defaultdict(lambda: {'orders': [], 'total': 0, 'details': defaultdict(list)})

    for order in orders:
        for detail in order.orderdetail_set.all():
            product_store = detail.product.store
            if product_store.id == store_id:
                store_orders[product_store]['orders'].append(order)
                store_orders[product_store]['details'][order].append(detail)
                store_orders[product_store]['total'] += float(detail.subtotal)

    store_orders = dict((store, {
        'orders': data['orders'],
        'total': data['total'],
        'details': dict(data['details'])
    }) for store, data in store_orders.items())

    product_names = [product['product__name'] for product in top_products]
    product_sales = [product['total_sold'] for product in top_products]
    product_revenues = [product['total_revenue'] for product in top_products]
    
    total_orders = orders.count()
    store_revenue = sum(order.orderdetail_set.filter(
        product__store=store
    ).aggregate(total=Sum('subtotal'))['total'] for order in orders)

    current_year = datetime.now().year
    month_list = [('all', 'All Months')] + [
        (f"{current_year}-{str(m).zfill(2)}", datetime(current_year, m, 1).strftime('%B'))
        for m in range(1, 13)
    ]

    # Create a list of product data with full image URLs for template context
    top_products_data = []
    for product in top_products:
        name = product['product__name']
        image = product['product__image']
        image_url = f"{settings.MEDIA_URL}{image}" if image else None
        orders_count = product['total_sold']
        revenue = product['total_revenue']
        orders_percentage = (orders_count / total_orders * 100) if total_orders else 0
        revenue_percentage = (revenue / store_revenue * 100) if store_revenue else 0
        top_products_data.append({
            'name': name,
            'image_url': image_url,
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
@login_required(login_url='login')

def order_history(request):
    sent = Friendship.objects.filter(receiver=request.user, status='pending')
    stores = Store.objects.filter(owner=request.user, status='approved')

    # Lấy tất cả các đơn hàng của người dùng, sắp xếp theo ngày đặt hàng
    orders = Order.objects.filter(user=request.user).order_by('-order_date')

    # Tính tổng số lượng sản phẩm trong giỏ hàng của người dùng nếu đã đăng nhập
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        total_quantity = cart.items.aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0
    else:
        total_quantity = 0

    context = {
        'orders': orders,
        'stores': stores,
        'sent': sent,
        'total_quantity': total_quantity  # Truyền tổng số lượng sản phẩm trong giỏ hàng vào context
    }

    return render(request, 'base/order_history.html', context)

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




@login_required(login_url='login')

def toggle_like(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.user in store.liker.all():
        store.liker.remove(request.user)
    else:
        store.liker.add(request.user)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@login_required(login_url='login')

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

    context = {'event':event}

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

            messages.success(request, 'Event created successfully.')
            return redirect('event')
        else:
            messages.error(request, 'Please fill in all required fields correctly.')
    
    context = {'form': form}
    return render(request, 'base/event_form.html', context)


#Update một event
@login_required(login_url='login')

def update_event(request, pk):
    event = get_object_or_404(Event, id=pk, host=request.user)  # Đảm bảo chỉ host mới có thể cập nhật
    
    if request.method == 'POST':
        form = EventsForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            event.status = "waiting"
            event.save()  # Lưu các thay đổi
            messages.success(request, 'Event updated successfully.')
            return redirect('event_detail', pk=event.id)
        else:
            messages.error(request, 'Please fill in all required fields correctly.')
    else:
        form = EventsForm(instance=event)

    return render(request, 'base/event_form.html', {'form': form, 'event': event})


#Xóa một event
@csrf_exempt  # Đảm bảo rằng bạn sử dụng đúng CSRF token khi gửi yêu cầu từ JavaScript
def delete_event(request, pk):
    event = get_object_or_404(Event, id=pk, host=request.user)  # Đảm bảo chỉ host mới có thể xóa

    if request.method == 'POST':
        event.delete()
        return JsonResponse({'success': True})  # Trả về phản hồi JSON thành công
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
    


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
@login_required(login_url='login')

def view_invitations(request):
    # Fetch invitations for the logged-in user
    invitations = Invitation.objects.filter(invitee=request.user, accepted=False)
    
    return render(request, 'base/Notification_event.html', {
        'invitations': invitations
    })

#đồng ý vào event
@login_required(login_url='login')

def accept_invitation(request, invitation_id):
    invitation = get_object_or_404(Invitation, pk=invitation_id, invitee=request.user)
    invitation.accepted = True
    invitation.save()
    # Add the user to the event participants
    invitation.event.par.add(request.user)
    return redirect('event_detail', pk=invitation.event.id)

@login_required(login_url='login')

def liked_events(request):
    liked_events = Event.objects.filter(like=request.user)
    return render(request, 'base/liked_events.html', {'liked_events': liked_events})

#thích event 
@login_required(login_url='login')

def like_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.user in event.like.all():
        event.like.remove(request.user)
    else:
        event.like.add(request.user)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@login_required(login_url='login')

def dislike_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.user in event.like.all():
        event.like.remove(request.user)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


@login_required(login_url='login')

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
@login_required(login_url='login')

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
            return render(request, 'base/enter_reset_code.html', {'error': 'Verification code has expired.'})
        
        if code == request.session.get('password_reset_code'):
            # Nếu mã chính xác, cho phép đặt lại mật khẩu
            return redirect('reset_password')
        else:
            # Nếu mã không chính xác, hiển thị lỗi nhưng giữ nguyên bộ đếm
            return render(request, 'base/enter_reset_code.html', {'error': 'Code is incorrect.', 'sent_at': sent_at})
    
    return render(request, 'base/enter_reset_code.html', {'sent_at': request.session.get('password_reset_sent_at')})





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
            context = {'error': 'Password and confirmation password do not match.', 'new_password': new_password, 'confirm_password': confirm_password}
            return render(request, 'base/reset_password.html', context)

    return render(request, 'base/reset_password.html')



@login_required(login_url='login')

def change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # Kiểm tra các trường có để trống không
        if not old_password or not new_password or not confirm_password:
            messages.error(request, 'Please fill out all required fields.')
            return redirect('change_password')

        # Kiểm tra mật khẩu cũ có chính xác không trước khi cập nhật
        user = request.user

        # Use Django's `check_password` function to ensure proper hashing check
        if not check_password(old_password, user.password):
            messages.error(request, 'The old password is incorrect.')
            return redirect('change_password')

        # Kiểm tra mật khẩu mới và xác nhận mật khẩu có khớp không
        if new_password != confirm_password:
            messages.error(request, 'New password and confirm password do not match.')
            return redirect('change_password')

        # Kiểm tra định dạng mật khẩu mới
        if len(new_password) < 6:
            messages.error(request, 'The new password must be at least 6 characters long.')
            return redirect('change_password')

        if not re.search(r'[A-Z]', new_password):
            messages.error(request, 'The new password must contain at least one uppercase letter.')
            return redirect('change_password')

        if not re.search(r'[\W_]', new_password):
            messages.error(request, 'The new password must contain at least one special character.')
            return redirect('change_password')

        # Nếu mật khẩu cũ đúng và mật khẩu mới hợp lệ, tiến hành cập nhật mật khẩu
        user = request.user
        user.set_password(new_password)
        user.save()

        # Cập nhật session để giữ người dùng đăng nhập sau khi đổi mật khẩu
        update_session_auth_hash(request, user)

        # Thông báo thành công
        messages.success(request, 'Password has been updated successfully.')
        return redirect('change_password')

    return render(request, 'base/change_password.html')



@login_required(login_url='login')

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





@login_required(login_url='login')

def ban_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.is_banned = True
    user.save()
    Message.objects.filter(user=user).delete()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@login_required(login_url='login')

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







def unauthorized(request,exception=None):
    return render(request, 'base/unauthorized.html')








# POst
@login_required(login_url='login')

def post_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        image = request.FILES.get('image')
        video = request.FILES.get('video')  # Handle video upload

        # Check if title and content are not empty
        if not title or not content:
            messages.error(request, 'Title and content cannot be empty.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        content = escape(content).replace('\n', '<br>')

        # Create the post with or without an image/video
        post = Post.objects.create(
            author=request.user,
            title=title,
            content=content,
            image=image,  # Save the image if uploaded
            video=video  # Save the video if uploaded
        )

        messages.success(request, 'Post created successfully!')
        return JsonResponse({'status': 'success', 'post_id': post.id})

    return redirect('home')



@login_required(login_url='login')

def like_post(request, content_id):
    # Check if the content is a Post or a Share
    content = get_object_or_404(Post, id=content_id) if Post.objects.filter(id=content_id).exists() else get_object_or_404(Share, id=content_id)
    user = request.user

    if user in content.likes.all():
        content.likes.remove(user)
        liked = False
    else:
        content.likes.add(user)
        liked = True

    return JsonResponse({
        'liked': liked,
        'like_count': content.likes.count(),
    })


def get_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    data = {
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'image': post.image.url if post.image else None,
    }
    return JsonResponse(data)

@csrf_exempt

def update_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == 'POST':
        post.title = request.POST.get('title')
        post.content = request.POST.get('content')

        if 'media' in request.FILES:
            media = request.FILES['media']
            if media.content_type.startswith('image'):
                post.image = media
                post.video = None  # Clear video if a new image is uploaded
            elif media.content_type.startswith('video'):
                post.video = media
                post.image = None  # Clear image if a new video is uploaded

        post.save()

        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'fail'}, status=400)



def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == 'POST':
        # Kiểm tra quyền của người dùng
        if request.user == post.author:
            post.delete()
            messages.success(request, 'The post was successfully deleted.')
        else:
            messages.error(request, 'You are not authorized to delete this post.')
        
        return redirect('home') 
    


def load_more_comments(request):
    post_id = request.GET.get('post_id')
    offset = int(request.GET.get('offset', 0))
    comments = Comment.objects.filter(post_id=post_id).order_by('created_at')[offset:offset + 5]

    comments_data = []
    for comment in comments:
        comments_data.append({
            'user': comment.user.username,
            'avatar_url': comment.user.avatar.url,
            'created_at': comment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'content': comment.content,
        })

    return JsonResponse({'comments': comments_data})


@login_required(login_url='login')


def add_comment(request, content_id):
    # Check if the content is a Post or a Share
    content = get_object_or_404(Post, id=content_id) if Post.objects.filter(id=content_id).exists() else get_object_or_404(Share, id=content_id)
    if request.method == 'POST':
        content_text = request.POST.get('content')
        if content_text:
            comment = Comment.objects.create(post=content, user=request.user, content=content_text)
            html = render_to_string('base/comment.html', {'comment': comment}, request=request)
            return JsonResponse({'html': html})
    return JsonResponse({'error': 'Invalid request'}, status=400)



@login_required(login_url='login')

@require_POST
def share_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    content = request.POST.get('content', '')  # Get content from the share modal if available
    Share.objects.create(post=post, user=request.user, content=content)
    return JsonResponse({'status': 'success', 'message': 'Post shared successfully!'})


@login_required(login_url='login')


def delete_share(request, share_id):
    if request.method == 'POST':
        share = get_object_or_404(Share, id=share_id)
        if request.user == share.user:  # Assuming the share has a user field
            share.delete()
            messages.success(request, 'Share deleted successfully.')
        else:
            messages.error(request, 'You are not authorized to delete this share.')
    return redirect('home')







def top_stores_by_revenue(request):
    # Calculate total revenue for each store
    top_stores = Store.objects.annotate(
        total_revenue=Sum('orders__orderdetail__subtotal')
    ).order_by('-total_revenue')[:10]  # Get the top 10 stores by revenue

    # Prepare data for the chart
    store_names = [store.name for store in top_stores]
    revenues = [store.total_revenue or 0 for store in top_stores]

    context = {
        'top_stores': top_stores,
        'store_names': store_names,
        'revenues': revenues,
        'selected_month': 0,  # Default to all months
    }

    return render(request, 'base/top_store_revenue.html', context)


def topic_distribution(request):
    # Aggregate the number of participants in each topic
    topics = Topic.objects.annotate(participant_count=Count('room__participants')).order_by('-participant_count')

    # Calculate total participants across all topics
    total_participants = sum(topic.participant_count for topic in topics)

    # Prepare data for the pie chart, including percentage calculation
    topic_names = [topic.name for topic in topics]
    participant_counts = [topic.participant_count for topic in topics]
    participant_percentages = [(count / total_participants) * 100 for count in participant_counts]

    context = {
        'topic_names': topic_names,
        'participant_counts': participant_counts,
        'participant_percentages': participant_percentages,
    }

    return render(request, 'base/topic_distribution.html', context)