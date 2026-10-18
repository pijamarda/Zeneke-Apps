from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('kid/login/', views.kid_login, name='kid_login'),
    path('kid/setup-pin/', views.kid_setup_pin, name='kid_setup_pin'),
    path('kid/change-pin/', views.kid_change_pin, name='kid_change_pin'),
    path('family/', views.family, name='family'),
    path('family/new/', views.family_create, name='family_create'),
    path('family/<int:pk>/reset-pin/', views.family_reset_pin, name='family_reset_pin'),
    path('family/<int:pk>/unlock/', views.family_unlock, name='family_unlock'),
]
