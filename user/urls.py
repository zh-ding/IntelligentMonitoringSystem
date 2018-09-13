from django.urls import path
from user import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('adduser/', views.add_user, name='add_user'),
    path('delete/', views.delete_user, name='delete_user'),
    path('changepwd/', views.change_password, name='change_password'),
]
