from django.urls import path
from . import views

app_name = 'bingo'

urlpatterns = [
    path('', views.start, name='start'),
    path('new/', views.create_room, name='create'),
    path('go/', views.go_to_room, name='go'),
    path('r/<str:code>/', views.room_page, name='room'),
    path('r/<str:code>/join/', views.join, name='join'),
    path('r/<str:code>/state/', views.state, name='state'),
    path('r/<str:code>/mark/', views.mark, name='mark'),
    path('r/<str:code>/claim/', views.claim, name='claim'),
    path('r/<str:code>/cards/', views.card_count, name='cards'),
    path('r/<str:code>/host/', views.host, name='host'),
    path('r/<str:code>/draw/', views.draw, name='draw'),
    path('r/<str:code>/continue/', views.continue_game, name='continue'),
    path('r/<str:code>/auto/', views.auto, name='auto'),
    path('r/<str:code>/new-game/', views.new_game, name='new_game'),
    path('r/<str:code>/remove/<int:player_id>/', views.remove_player, name='remove'),
]
