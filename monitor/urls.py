from django.urls import path
from monitor import views

urlpatterns = [
    path('', views.monitor, name='monitor'),
    path('videofeed', views.video_feed, name='video_feed'),
]
