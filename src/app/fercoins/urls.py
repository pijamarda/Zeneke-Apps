from django.urls import path
from . import views

app_name = 'fercoins'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('manage/', views.manage, name='manage'),
    path('give/', views.give, name='give'),
    path('give/<int:user_id>/', views.give, name='give_to'),
    path('chores/', views.chores, name='chores'),
    path('chores/new/', views.chore_create, name='chore_create'),
    path('chores/<int:pk>/edit/', views.chore_edit, name='chore_edit'),
    path('chores/<int:pk>/toggle/', views.chore_toggle, name='chore_toggle'),
]
