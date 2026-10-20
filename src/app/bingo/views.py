from functools import wraps
from importlib import import_module

import segno
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import game, rules
from .models import AUTO_INTERVALS, NICKNAME_MAX_LENGTH, Player, Room, deal_card

HOST_KEY = 'bingo_host'
PLAYERS_KEY = 'bingo_players'

NOT_HOST = 'Solo quien creó la sala puede hacer esto.'


# Session identity

def _is_host(request, room):
    return room.pk in request.session.get(HOST_KEY, [])


def _session_player(request, room):
    player_id = request.session.get(PLAYERS_KEY, {}).get(str(room.pk))
    if player_id is None:
        return None
    return Player.objects.filter(pk=player_id, room=room).first()


def _remember_host(request, room):
    request.session[HOST_KEY] = request.session.get(HOST_KEY, []) + [room.pk]


def _remember_player(request, room, player):
    players = request.session.get(PLAYERS_KEY, {})
    players[str(room.pk)] = player.pk
    request.session[PLAYERS_KEY] = players


# Decorators

def _not_found(request):
    return render(request, 'bingo/not_found.html', status=404)


def with_room(view):
    @wraps(view)
    def wrapper(request, code, *args, **kwargs):
        room = Room.objects.active().filter(code=code.strip().upper()).first()
        if room is None:
            return _not_found(request)
        return view(request, room, *args, **kwargs)
    return wrapper


def host_only(view):
    @wraps(view)
    def wrapper(request, room, *args, **kwargs):
        if not _is_host(request, room):
            return HttpResponseForbidden(NOT_HOST)
        if request.method == 'POST':
            room.touch()
        return view(request, room, *args, **kwargs)
    return wrapper


def _refused(exc, status=409):
    return JsonResponse({'ok': False, 'message': exc.message}, status=status)


# Start page

def _start(request, message=None, code='', status=200):
    return render(request, 'bingo/start.html', {'message': message, 'code': code}, status=status)


@require_GET
def start(request):
    return _start(request)


@require_POST
def create_room(request):
    now = timezone.now()
    Room.objects.expired(now).delete()
    import_module(settings.SESSION_ENGINE).SessionStore.clear_expired()
    if Room.objects.count() >= settings.BINGO_MAX_ROOMS:
        return _start(request, 'Ahora mismo no se pueden crear más salas. Inténtalo más tarde.', status=503)
    room = Room.create_with_game()
    _remember_host(request, room)
    return redirect('bingo:host', code=room.code)


@require_POST
def go_to_room(request):
    code = request.POST.get('code', '').strip().upper()
    if code and Room.objects.active().filter(code=code).exists():
        return redirect('bingo:room', code=code)
    return _start(request, 'Sala no encontrada o caducada.', code=code, status=404)


# Joining and playing

def _join_url(request, room):
    return request.build_absolute_uri(reverse('bingo:room', args=[room.code]))


def _player_page(request, room, player):
    if player.removed:
        return render(request, 'bingo/removed.html', {'room': room}, status=403)
    state = game.state_payload(room, player=player)
    marks = set(state['me']['marks'])
    card_rows = [
        [{'number': n, 'marked': n in marks} for n in row] for row in state['me']['card'] or []
    ]
    return render(request, 'bingo/player.html', {
        'room': room, 'player': player, 'state': state, 'card_rows': card_rows,
    })


def _join_form(request, room, nickname='', message=None, status=200):
    return render(request, 'bingo/join.html', {
        'room': room, 'nickname': nickname, 'message': message,
        'max_length': NICKNAME_MAX_LENGTH,
    }, status=status)


@require_GET
@with_room
def room_page(request, room):
    player = _session_player(request, room)
    if player is not None:
        return _player_page(request, room, player)
    return _join_form(request, room)


@require_POST
@with_room
def join(request, room):
    player = _session_player(request, room)
    if player is not None:
        return redirect('bingo:room', code=room.code)

    nickname = request.POST.get('nickname', '').strip()
    if not nickname:
        return _join_form(request, room, nickname, 'Escribe un nombre para jugar.', status=400)
    if len(nickname) > NICKNAME_MAX_LENGTH:
        return _join_form(
            request, room, nickname,
            f'El nombre puede tener como máximo {NICKNAME_MAX_LENGTH} caracteres.', status=400,
        )
    if room.players.filter(removed=False).count() >= settings.BINGO_MAX_PLAYERS:
        return _join_form(request, room, nickname, 'La sala está llena.', status=409)
    try:
        with transaction.atomic():
            player = Player.objects.create(room=room, nickname=nickname, nickname_key=nickname.lower())
            deal_card(room.game, player)
    except IntegrityError:
        return _join_form(request, room, nickname, 'Ese nombre ya está en uso en esta sala.', status=409)
    _remember_player(request, room, player)
    room.touch()
    return redirect('bingo:room', code=room.code)


def _active_player(request, room):
    player = _session_player(request, room)
    if player is None or player.removed:
        return None
    return player


@require_POST
@with_room
def mark(request, room):
    player = _active_player(request, room)
    if player is None:
        return HttpResponseForbidden('No estás jugando en esta sala.')
    try:
        number = int(request.POST.get('number', ''))
    except ValueError:
        return JsonResponse({'ok': False, 'message': 'Número no válido.'}, status=400)
    marked = request.POST.get('marked') == '1'

    with transaction.atomic():
        # Write first to take SQLite's lock, so two quick taps don't overwrite each other.
        player.cards.update(marks=F('marks'))
        card = player.cards.select_related('game').first()
        if card is None or number not in card.numbers():
            return JsonResponse({'ok': False, 'message': 'Ese número no está en tu cartón.'}, status=400)
        state, _ = card.game.settled(timezone.now())
        if state.stage == rules.FINISHED:
            return JsonResponse({'ok': False, 'message': game.REFUSALS['finished']}, status=409)
        marks = set(card.marks)
        marks.add(number) if marked else marks.discard(number)
        card.marks = sorted(marks)
        card.save(update_fields=['marks'])
    room.touch()
    return JsonResponse({'ok': True, 'marks': card.marks})


@require_POST
@with_room
def claim(request, room):
    player = _active_player(request, room)
    if player is None:
        return HttpResponseForbidden('No estás jugando en esta sala.')
    prize = request.POST.get('prize')
    if prize not in rules.PRIZES:
        return JsonResponse({'ok': False, 'message': 'Premio no válido.'}, status=400)
    room.touch()
    try:
        game.claim(room, player, prize)
    except game.Refused as exc:
        return _refused(exc)
    return JsonResponse({'ok': True, 'state': game.state_payload(room, player=player)})


@require_GET
@never_cache
@with_room
def state(request, room):
    host = _is_host(request, room) and request.GET.get('view') == 'host'
    player = None if host else _session_player(request, room)
    if not host and player is None:
        return HttpResponseForbidden('No estás jugando en esta sala.')
    return JsonResponse(game.state_payload(room, player=player, host=host))


# Host

@require_GET
@with_room
@host_only
def host(request, room):
    qr_svg = segno.make(_join_url(request, room), error='m').svg_inline(scale=8, border=2)
    return render(request, 'bingo/host.html', {
        'room': room,
        'join_url': _join_url(request, room),
        'qr_svg': qr_svg,
        'intervals': AUTO_INTERVALS,
        'board': range(1, rules.HIGHEST_BALL + 1),
        'state': game.state_payload(room, host=True),
    })


def _host_ok(request, room):
    return JsonResponse({'ok': True, 'state': game.state_payload(room, host=True)})


@require_POST
@with_room
@host_only
def draw(request, room):
    try:
        seen = int(request.POST.get('seen', ''))
    except ValueError:
        return JsonResponse({'ok': False, 'message': 'Petición no válida.'}, status=400)
    try:
        game.draw(room, seen)
    except game.Refused as exc:
        return _refused(exc)
    return _host_ok(request, room)


@require_POST
@with_room
@host_only
def continue_game(request, room):
    try:
        game.continue_game(room)
    except game.Refused as exc:
        return _refused(exc)
    return _host_ok(request, room)


@require_POST
@with_room
@host_only
def auto(request, room):
    value = request.POST.get('interval', 'off')
    if value == 'off':
        interval = None
    else:
        try:
            interval = int(value)
        except ValueError:
            interval = -1
        if interval not in AUTO_INTERVALS:
            return JsonResponse({'ok': False, 'message': 'Intervalo no válido.'}, status=400)
    now = timezone.now()
    room.auto_interval = interval
    room.auto_since = now if interval else None
    room.last_activity_at = now
    room.save(update_fields=['auto_interval', 'auto_since', 'last_activity_at'])
    return _host_ok(request, room)


@require_POST
@with_room
@host_only
def new_game(request, room):
    game.new_game(room)
    room.refresh_from_db()
    return _host_ok(request, room)


@require_POST
@with_room
@host_only
def remove_player(request, room, player_id):
    player = get_object_or_404(Player, pk=player_id, room=room, removed=False)
    game.remove_player(room, player)
    return _host_ok(request, room)
