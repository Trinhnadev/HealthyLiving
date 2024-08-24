# from django.contrib import admin
from django.urls import path
from django.conf.urls import handler404
from . import views

urlpatterns = [

    # path('',views.home,name="banner"),


    path('',views.loginPage,name="login"),



    path('home/',views.home,name="home"),
    path('room/<str:pk>/',views.room,name="room"),
    path('create-room/',views.createRoom, name ="create-room"),
    path('update-room/<slug:pk>/',views.updateRoom, name ="update-room"),
    path('delete-room/<int:room_id>/', views.delete_room, name='delete_room'),
    path('logout/',views.logoutUser,name="logout"),
    path('sign/',views.sign,name="sign"),
    path('profile/<str:pk>/',views.userProfile,name="profile"),
    path('delete-message/<str:pk>/',views.deleteMessage, name ="delete-message"),
    path('update-user/',views.updateUser, name ="update-user"),
    path('topics/',views.topicsPage, name ="topics"),
    path('friend/',views.friendPages, name ="friend"),
    path('all-friend/',views.AllFriend, name ="all-friend"),
    


    path('activity/',views.activityPages, name ="activity"),


    path('update_avatar/', views.update_avatar, name='update_avatar'),
    path('update_coveravatar/', views.update_coveravatar, name='update_coveravatar'),

    path('addFriend/<str:pk>/',views.sentRequest,name="addFriend"),
    path('accept/<str:pk>/',views.acceptRequest,name = 'accept'),
    path('reject/<str:pk>/',views.reject, name = 'reject'),

    path('chat/', views.chat, name='chat'),

    path('open_chat/<str:pk>/', views.open_chat, name='open_chat'),
    path('delete_message_chat/<int:message_id>/', views.delete_message_chat, name='delete_message_chat'),
    



    # shop
    path('shop/', views.shopping, name='shop'),
    path('create_store/', views.create_store, name='create_store'),
    path('update_store/<int:pk>/', views.update_store, name='update_store'),
    path('delete_store/<int:pk>/', views.delete_store, name='delete_store'),
    path('store_detail/<str:pk>', views.store_detail, name='store_detail'),
    path('store/<int:store_id>/products/', views.store_products, name='store_products'),


    #CRUD product
    path('store/<int:store_id>/product/add/', views.product_create, name='product_create'),
    path('store/<int:store_id>/product/<int:product_id>/edit/', views.product_update, name='product_update'),
    path('store/<int:store_id>/product/<int:product_id>/delete/', views.product_delete, name='product_delete'),
    path('dashboard/<int:store_id>/', views.dashboard, name='dashboard'),
    path('revenue/<int:store_id>/', views.revenue, name='revenue'),
    path('product/update_quantity/', views.update_product_quantity, name='update_product_quantity'),


    
    





    path('store/<int:store_id>/product/<int:product_id>/', views.product_detail, name='product_detail'),





    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    # Đường dẫn tới trang giỏ hàng, giả sử bạn có view này
    path('cart/', views.cart_detail, name='cart_detail'),




     path('checkout/', views.checkout, name='checkout'),
    path('order-detail/<int:order_id>/', views.order_detail, name='order_detail'),


    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('order-history/', views.order_history, name='order_history'),  # URL xem chi tiết đơn hàng
    # path('order/<int:order_id>/', views.order_detail, name='order_detail'),

    path('store/<int:store_id>/toggle-like/', views.toggle_like, name='toggle_like'),

    # store history

    path('store/<int:store_id>/order-history/', views.store_order_history, name='store_order_history'),
    path('store/<int:store_id>/order/<int:order_id>/', views.store_order_detail, name='store_order_detail'),
    path('liked-stores/', views.liked_stores, name='liked_stores'),
    #join room
    # path('rooms/join/<int:room_id>/', views.join_private_room, name='join_private_room'),


    #event 
    path('event/',views.event, name ="event"),
    path('myevent/',views.myevent, name ="myevent"),
    path('eventJoined/',views.eventJoined, name ="eventJoined"),
    path('events/<int:event_id>/', views.friends_not_in_event, name='events'),
    path('events/<int:event_id>/invite/<int:user_id>/', views.send_invitation, name='send_invitation'),
    path('invitations/', views.view_invitations, name='view_invitations'),
    path('invitation/accept/<int:invitation_id>/', views.accept_invitation, name='accept_invitation'),
    path('invitation/decline/<int:invitation_id>/', views.decline_invitation, name='decline_invitation'),


    path('event_detail/<str:pk>/',views.eventDetail, name ="event_detail"),
    path('careAbout/<str:pk>/',views.careAbout, name ="careAbout"),
    path('discareAbout/<str:pk>/',views.discareAbout, name ="discareAbout"),




    path('create-event/',views.createEvent, name ="create-event"),
    path('event-update/<int:pk>/', views.update_event, name='update_event'),
    path('event-delete/<int:pk>/', views.delete_event, name='delete_event'),
    path('event/<int:event_id>/like/', views.like_event, name='like_event'),
    path('event/<int:event_id>/dislike/', views.dislike_event, name='dislike_event'),
    path('liked-events/', views.liked_events, name='liked_events'),
    path('dislike_selected_events/', views.dislike_selected_events, name='dislike_selected_events'),


    path('password_reset/', views.password_reset_request, name='password_reset_request'),
    path('enter_reset_code/', views.enter_reset_code, name='enter_reset_code'),
    path('reset_password/', views.reset_password, name='reset_password'),
    path('change_password/', views.change_password, name='change_password'),
    path('report/', views.report_mess, name='report_message'),



    # admin
    path('manage/', views.manageUser, name='manage'),
    path('ban-user/<int:user_id>/', views.ban_user, name='ban_user'),
    path('unban-user/<int:user_id>/', views.unban_user, name='unban_user'),
    path('manageUserBan/', views.manageUserBanned, name='manageUserBan'),
    path('manageRoom/', views.manageRoom, name='manageRoom'),

    path('reports/messages/', views.reported_messages, name='reported_messages'),
    path('create_account/', views.create_account, name='create_account'),
    path('manage_event/', views.ManageEvent, name='manage_event'),
    path('manage_stores/', views.manageStore, name='manage_stores'),
    path('manage_products/', views.manageProduct, name='manage_products'),



    path('product/<int:pk>/approve/', views.approve_product, name='approve_product'),
    path('product/<int:pk>/reject/', views.reject_product, name='reject_product'),

    path('event/<int:pk>/approve/', views.approve_event, name='approve_event'),
    path('event/<int:pk>/reject/', views.reject_event, name='reject_event'),

    path('store/<int:pk>/approve/', views.approve_store, name='approve_store'),
    path('store/<int:pk>/reject/', views.reject_store, name='reject_store'),
    path('event/<int:event_id>/message/<int:message_id>/delete/', views.delete_event_message, name='delete_event_message'),



    path('unauthorized/', views.unauthorized, name='unauthorized'),




    path('post/create/', views.post_create, name='post_create'),
    path('like-post/<int:content_id>/', views.like_post, name='like-post'),
    path('get-post/<int:post_id>/', views.get_post, name='get-post'),
    path('update-post/<int:post_id>/', views.update_post, name='update-post'),
    path('delete-post/<int:post_id>/', views.delete_post, name='delete_post'),
    
    path('load-more-comments/', views.load_more_comments, name='load_more_comments'),
    path('add-comment/<int:content_id>/', views.add_comment, name='add-comment'),
    path('share-post/<int:post_id>/', views.share_post, name='share-post'),
    path('delete-share/<int:share_id>/', views.delete_share, name='delete_share'),
    

]