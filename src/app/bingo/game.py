"""Game actions with a version check, and the JSON state sent to pages."""
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import rules
from .models import Card, Claim, Game, Room, deal_card, rng

REFUSALS = {
    'waiting': 'La partida aún no ha empezado.',
    'finished': 'La partida ha terminado.',
    'linea_first': 'Ahora se juega la línea.',
    'linea_closed': 'La línea ya se cantó. Ahora se juega el bingo.',
    'paused': 'Espera a que termine la pausa.',
    'no_balls': 'No quedan bolas.',
    'invalid_linea': 'Esa línea no es válida. Revisa tu cartón.',
    'invalid_bingo': 'Ese bingo no es válido. Revisa tu cartón.',
    'retry': 'Inténtalo de nuevo.',
}


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code
        self.message = REFUSALS[code]


class _Conflict(Exception):
    pass


def update_game(room, change, now=None):
    """Run `change(game, settled_state)` and save the state it returns.

    `change` returns the new GameState, or a (GameState, extra_fields) pair, and
    may raise Refused. The save only succeeds if nobody else changed the game in
    between; otherwise the whole change is retried once on fresh data.
    """
    now = now or timezone.now()
    for _ in range(2):
        try:
            with transaction.atomic():
                # Take SQLite's write lock before reading, so concurrent actions
                # wait for each other instead of failing with "database is locked".
                Game.objects.filter(room=room).update(version=F('version'))
                game = Game.objects.get(room=room)
                state, resumed_at = game.settled(now)
                result = change(game, state)
                new_state, extra = result if isinstance(result, tuple) else (result, {})
                fields = {
                    'stage': new_state.stage,
                    'drawn': list(new_state.drawn),
                    'pause_prize': new_state.pause_prize,
                    'pause_ends_at': new_state.pause_ends_at,
                    'resumed_at': resumed_at,
                    **extra,
                }
                updated = Game.objects.filter(pk=game.pk, version=game.version).update(
                    version=game.version + 1, **fields
                )
                if not updated:
                    raise _Conflict
                room.touch(now)
                return new_state
        except _Conflict:
            continue
    raise Refused('retry')


def draw(room, seen, now=None):
    now = now or timezone.now()

    def change(game, state):
        if len(state.drawn) != seen:
            return state  # someone else already drew the ball this client asked for
        refusal = rules.draw_refusal(state)
        if refusal:
            raise Refused(refusal)
        new_state, _ = rules.draw_ball(state, rng)
        return new_state, {'last_draw_at': now}

    return update_game(room, change, now)


def claim(room, player, prize, now=None):
    now = now or timezone.now()

    def change(game, state):
        refusal = rules.claim_refusal(state, prize)
        if refusal:
            raise Refused(refusal)
        if Claim.objects.filter(game=game, player=player, prize=prize).exists():
            return state
        card = Card.objects.get(game=game, player=player)
        row = None
        if prize == rules.LINEA:
            row = rules.valid_linea_row(card.grid, card.marks, state.drawn)
            if row is None:
                raise Refused('invalid_linea')
        elif not rules.is_bingo(card.grid, card.marks, state.drawn):
            raise Refused('invalid_bingo')
        Claim.objects.create(game=game, player=player, prize=prize, row=row, created_at=now)
        return rules.start_pause(state, prize, now)

    return update_game(room, change, now)


def continue_game(room, now=None):
    now = now or timezone.now()

    def change(game, state):
        if not state.paused:
            return state
        return rules.end_pause_now(state, now), {'resumed_at': now}

    return update_game(room, change, now)


def new_game(room, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        Game.objects.filter(room=room).delete()
        game = Game.objects.create(room=room, created_at=now)
        for player in room.players.filter(removed=False):
            deal_card(game, player)
        Room.objects.filter(pk=room.pk).update(auto_since=now if room.auto_interval else None)
    room.touch(now)
    return game


def remove_player(room, player, now=None):
    with transaction.atomic():
        player.removed = True
        player.save(update_fields=['removed'])
        player.cards.all().delete()
        player.claims.all().delete()
    room.touch(now)


def _winners(game, prize, cards):
    result = []
    for claim_ in game.claims.filter(prize=prize).select_related('player'):
        card = cards.get(claim_.player_id)
        if card is None:
            continue
        result.append({'nickname': claim_.player.nickname, 'numbers': claim_.winning_numbers(card)})
    return result


def _ms(delta):
    return max(0, int(delta.total_seconds() * 1000))


def state_payload(room, player=None, host=False, now=None):
    """What a page needs to redraw itself. Reads only; never saves anything."""
    now = now or timezone.now()
    game = Game.objects.get(room=room)
    state, resumed_at = game.settled(now)
    cards = {card.player_id: card for card in game.cards.all()}

    payload = {
        'game_id': game.pk,
        'stage': state.stage,
        'drawn': list(state.drawn),
        'last': state.drawn[-1] if state.drawn else None,
        'balls_left': rules.HIGHEST_BALL - len(state.drawn),
        'pause': None,
        'winners': {prize: _winners(game, prize, cards) for prize in rules.PRIZES},
    }
    if state.paused:
        payload['pause'] = {
            'prize': state.pause_prize,
            'remaining_ms': _ms(state.pause_ends_at - now),
            'total_ms': rules.PAUSE_SECONDS * 1000,
        }

    if player is not None:
        card = cards.get(player.pk)
        payload['me'] = {
            'nickname': player.nickname,
            'removed': player.removed,
            'card': card.grid if card else None,
            'marks': card.marks if card else [],
        }

    if host:
        payload['players'] = [
            {'id': p.pk, 'nickname': p.nickname} for p in room.players.filter(removed=False)
        ]
        payload['auto_interval'] = room.auto_interval
        payload['can_draw'] = rules.draw_refusal(state) is None
        payload['next_auto_draw_ms'] = None
        if room.auto_interval and payload['can_draw']:
            bases = [t for t in (game.last_draw_at, resumed_at, room.auto_since) if t]
            base = max(bases) if bases else now
            payload['next_auto_draw_ms'] = _ms(base + timedelta(seconds=room.auto_interval) - now)
    return payload
