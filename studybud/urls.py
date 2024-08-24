from django.conf.urls import handler404
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static
#create home

handler404 = 'base.views.unauthorized'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('base.urls')),
    path('api/',include('base.api.urls')),

]
#IMAGE

urlpatterns = urlpatterns+static(settings.MEDIA_URL, document_root =settings.MEDIA_ROOT)
