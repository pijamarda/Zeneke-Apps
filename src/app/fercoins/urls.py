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
    path('chores/<int:pk>/claim/', views.chore_claim, name='chore_claim'),
    path('prizes/<int:pk>/request/', views.prize_request, name='prize_request'),
    path('requests/<int:pk>/cancel/', views.request_cancel, name='request_cancel'),
    path('review/', views.review, name='review'),
    path('review/<str:kind>/<int:pk>/<str:action>/', views.review_action, name='review_action'),
    path('prizes/', views.prizes, name='prizes'),
    path('prizes/new/', views.prize_create, name='prize_create'),
    path('prizes/<int:pk>/edit/', views.prize_edit, name='prize_edit'),
    path('prizes/<int:pk>/toggle/', views.prize_toggle, name='prize_toggle'),
]
