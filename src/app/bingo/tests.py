import random
from datetime import datetime, timedelta, timezone as dt_timezone

from unittest import mock

import segno
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import rules
from .models import CODE_ALPHABET, Card, Game, Player, Room, deal_cards
from .rules import BINGO, FINISHED, LINEA, WAITING, GameState

T0 = datetime(2026, 10, 20, 20, 0, tzinfo=dt_timezone.utc)


def sample_grid():
    return [
        [3, None, 21, None, 45, None, 62, None, 88],
        [None, 14, None, 33, 47, None, None, 71, 90],
        [7, None, 28, 39, None, 56, None, 79, None],
    ]


class CardGenerationTests(SimpleTestCase):
    def test_thousand_cards_follow_every_rule(self):
        rng = random.Random(1234)
        for _ in range(1000):
            grid = rules.generate_card(rng)
            self.assertEqual(len(grid), 3)
            self.assertTrue(all(len(row) == 9 for row in grid))
            numbers = rules.card_numbers(grid)
            self.assertEqual(len(numbers), 15)
            self.assertEqual(len(set(numbers)), 15)
            for row in grid:
                self.assertEqual(sum(n is not None for n in row), 5)
            for column in range(9):
                cells = [grid[row][column] for row in range(3)]
                values = [n for n in cells if n is not None]
                self.assertTrue(1 <= len(values) <= 3)
                low, high = rules.COLUMN_RANGES[column]
                self.assertTrue(all(low <= n <= high for n in values))
                self.assertEqual(values, sorted(values))

    def test_column_ranges(self):
        self.assertEqual(rules.COLUMN_RANGES[0], (1, 9))
        self.assertEqual(rules.COLUMN_RANGES[1], (10, 19))
        self.assertEqual(rules.COLUMN_RANGES[7], (70, 79))
        self.assertEqual(rules.COLUMN_RANGES[8], (80, 90))

    def test_cards_are_random(self):
        rng = random.Random(7)
        keys = {rules.numbers_key(rules.generate_card(rng)) for _ in range(50)}
        self.assertEqual(len(keys), 50)


class ClaimCheckTests(SimpleTestCase):
    def setUp(self):
        self.grid = sample_grid()
        self.row2 = [14, 33, 47, 71, 90]

    def test_valid_linea(self):
        self.assertEqual(rules.valid_linea_row(self.grid, self.row2, self.row2 + [5, 6]), 1)

    def test_row_drawn_but_not_fully_marked(self):
        self.assertIsNone(rules.valid_linea_row(self.grid, self.row2[:4], self.row2))

    def test_row_marked_but_not_fully_drawn(self):
        self.assertIsNone(rules.valid_linea_row(self.grid, self.row2, self.row2[:4]))

    def test_full_card_is_bingo(self):
        numbers = rules.card_numbers(self.grid)
        self.assertTrue(rules.is_bingo(self.grid, numbers, numbers))

    def test_one_number_marked_not_drawn_is_not_bingo(self):
        numbers = rules.card_numbers(self.grid)
        self.assertFalse(rules.is_bingo(self.grid, numbers, numbers[:-1]))


class GameFlowTests(SimpleTestCase):
    def test_first_ball_starts_the_game(self):
        state, ball = rules.draw_ball(GameState(stage=WAITING), random.Random(1))
        self.assertEqual(state.stage, LINEA)
        self.assertEqual(state.drawn, (ball,))

    def test_draws_never_repeat(self):
        state, rng = GameState(stage=WAITING), random.Random(3)
        for _ in range(90):
            state, _ = rules.draw_ball(state, rng)
        self.assertEqual(sorted(state.drawn), list(range(1, 91)))
        self.assertEqual(rules.draw_refusal(state), 'no_balls')

    def test_no_draw_while_paused_or_finished(self):
        paused = rules.start_pause(GameState(stage=LINEA, drawn=(1,)), LINEA, T0)
        self.assertEqual(rules.draw_refusal(paused), 'paused')
        self.assertEqual(rules.draw_refusal(GameState(stage=FINISHED)), 'finished')

    def test_pause_ends_by_itself_after_ten_seconds(self):
        paused = rules.start_pause(GameState(stage=LINEA), LINEA, T0)
        self.assertEqual(rules.settle(paused, T0 + timedelta(seconds=9)), paused)
        settled = rules.settle(paused, T0 + timedelta(seconds=10))
        self.assertEqual(settled.stage, BINGO)
        self.assertFalse(settled.paused)

    def test_later_claims_do_not_extend_the_pause(self):
        paused = rules.start_pause(GameState(stage=LINEA), LINEA, T0)
        again = rules.start_pause(paused, LINEA, T0 + timedelta(seconds=5))
        self.assertEqual(again.pause_ends_at, paused.pause_ends_at)

    def test_continue_ends_the_pause_at_once(self):
        paused = rules.start_pause(GameState(stage=BINGO), BINGO, T0)
        ended = rules.end_pause_now(paused, T0 + timedelta(seconds=3))
        self.assertEqual(ended.stage, FINISHED)
        self.assertFalse(ended.paused)

    def test_linea_claim_during_linea_pause_is_open(self):
        paused = rules.start_pause(GameState(stage=LINEA), LINEA, T0)
        settled = rules.settle(paused, T0 + timedelta(seconds=4))
        self.assertIsNone(rules.claim_refusal(settled, LINEA))

    def test_linea_claim_after_the_pause_is_refused(self):
        paused = rules.start_pause(GameState(stage=LINEA), LINEA, T0)
        settled = rules.settle(paused, T0 + timedelta(seconds=11))
        self.assertEqual(rules.claim_refusal(settled, LINEA), 'linea_closed')
        self.assertIsNone(rules.claim_refusal(settled, BINGO))

    def test_bingo_refused_while_playing_for_linea(self):
        self.assertEqual(rules.claim_refusal(GameState(stage=LINEA), BINGO), 'linea_first')

    def test_claims_refused_before_start_and_after_end(self):
        self.assertEqual(rules.claim_refusal(GameState(stage=WAITING), LINEA), 'waiting')
        self.assertEqual(rules.claim_refusal(GameState(stage=FINISHED), BINGO), 'finished')


class ModelTests(TestCase):
    def test_code_alphabet_and_uniqueness(self):
        codes = {Room.create_with_game().code for _ in range(30)}
        self.assertEqual(len(codes), 30)
        for code in codes:
            self.assertEqual(len(code), 5)
            self.assertTrue(set(code) <= set(CODE_ALPHABET))
        self.assertFalse(set('0O1IL') & set(CODE_ALPHABET))

    def test_code_collision_is_retried(self):
        taken = Room.create_with_game()
        codes = iter([taken.code, 'ZZZZZ'])
        with mock.patch('bingo.models.generate_code', lambda: next(codes)):
            self.assertEqual(Room.create_with_game().code, 'ZZZZZ')

    @override_settings(BINGO_ROOM_IDLE_HOURS=12)
    def test_expired_rooms_are_not_active(self):
        fresh = Room.create_with_game()
        old = Room.create_with_game()
        Room.objects.filter(pk=old.pk).update(last_activity_at=timezone.now() - timedelta(hours=13))
        self.assertEqual(list(Room.objects.active()), [fresh])
        self.assertEqual(list(Room.objects.expired()), [old])

    def test_cards_in_a_game_are_distinct(self):
        room = Room.create_with_game()
        ana = Player.objects.create(room=room, nickname='Ana', nickname_key='ana')
        leo = Player.objects.create(room=room, nickname='Leo', nickname_key='leo')
        grids = [sample_grid(), sample_grid(), rules.generate_card(random.Random(5))]
        with mock.patch('bingo.models.rules.generate_card', side_effect=lambda _rng: grids.pop(0)):
            [first] = deal_cards(room.game, ana)
            [second] = deal_cards(room.game, leo)
        self.assertNotEqual(first.numbers_key, second.numbers_key)
        self.assertEqual(deal_cards(room.game, ana), [first])


    def test_two_cards_for_one_player_are_distinct(self):
        room = Room.create_with_game()
        ana = Player.objects.create(room=room, nickname='Ana', nickname_key='ana', card_count=2)
        grids = [sample_grid(), sample_grid(), rules.generate_card(random.Random(5))]
        with mock.patch('bingo.models.rules.generate_card', side_effect=lambda _rng: grids.pop(0)):
            first, second = deal_cards(room.game, ana)
        self.assertEqual((first.position, second.position), (0, 1))
        self.assertNotEqual(first.numbers_key, second.numbers_key)

    def test_dealing_again_creates_nothing_and_lowering_the_count_drops_card_two(self):
        room = Room.create_with_game()
        ana = Player.objects.create(room=room, nickname='Ana', nickname_key='ana', card_count=2)
        cards = deal_cards(room.game, ana)
        self.assertEqual(deal_cards(room.game, ana), cards)
        self.assertEqual(Card.objects.count(), 2)
        ana.card_count = 1
        self.assertEqual(deal_cards(room.game, ana), cards[:1])
        self.assertEqual(list(Card.objects.values_list('position', flat=True)), [0])

class BingoClientTestCase(TestCase):
    """Helpers that play as several browsers (one Django test client each)."""

    def create_room(self, client=None):
        client = client or self.client
        response = client.post(reverse('bingo:create'))
        room = Room.objects.latest('pk')
        self.assertRedirects(response, reverse('bingo:host', args=[room.code]))
        return room

    def join(self, room, nickname, client=None, cards=None):
        client = client or Client()
        data = {'nickname': nickname}
        if cards is not None:
            data['cards'] = cards
        response = client.post(reverse('bingo:join', args=[room.code]), data)
        return client, response

    def player(self, room, nickname):
        return Player.objects.get(room=room, nickname=nickname)

    def give_card(self, room, nickname, grid=None, position=0):
        grid = grid or sample_grid()
        Card.objects.filter(player=self.player(room, nickname), position=position).update(
            grid=grid, numbers_key=rules.numbers_key(grid), marks=[]
        )

    def set_game(self, room, **fields):
        Game.objects.filter(room=room).update(**fields)

    def game(self, room):
        return Game.objects.get(room=room)

    def url(self, name, room, *args):
        return reverse(f'bingo:{name}', args=[room.code, *args])

    def state(self, room, client, host=False):
        url = self.url('state', room) + ('?view=host' if host else '')
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def mark(self, room, client, numbers, marked=True, card=0):
        for n in numbers:
            response = client.post(
                self.url('mark', room), {'number': n, 'marked': '1' if marked else '0', 'card': card}
            )
            self.assertEqual(response.status_code, 200, response.content)

    def marks(self, room, client, card=0):
        return self.state(room, client)['me']['cards'][card]['marks']

    def claim(self, room, client, prize):
        return client.post(self.url('claim', room), {'prize': prize})


ROW2 = [14, 33, 47, 71, 90]


class StartPageTests(BingoClientTestCase):
    def test_anonymous_visitor_sees_start_page(self):
        response = self.client.get(reverse('bingo:start'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Crear sala')
        self.assertContains(response, 'lang="es"')
        for link in ('Fercoins', 'Familia', 'Login'):
            self.assertNotContains(response, link)

    def test_family_apps_stay_protected(self):
        response = self.client.get('/fercoins/')
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('account_login'), response.url)


class CreateRoomTests(BingoClientTestCase):
    def test_anonymous_visitor_creates_a_room_and_is_host(self):
        room = self.create_room()
        response = self.client.get(self.url('host', room))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, room.code)
        self.assertEqual(self.game(room).stage, rules.WAITING)

    @override_settings(BINGO_MAX_ROOMS=2)
    def test_room_cap(self):
        self.create_room()
        self.create_room()
        response = self.client.post(reverse('bingo:create'))
        self.assertEqual(Room.objects.count(), 2)
        self.assertContains(response, 'no se pueden crear más salas', status_code=503)

    @override_settings(BINGO_MAX_ROOMS=2, BINGO_ROOM_IDLE_HOURS=12)
    def test_expired_rooms_are_deleted_and_do_not_count(self):
        old = self.create_room()
        self.create_room()
        Room.objects.filter(pk=old.pk).update(last_activity_at=timezone.now() - timedelta(hours=13))
        self.create_room()
        self.assertFalse(Room.objects.filter(pk=old.pk).exists())
        self.assertEqual(Room.objects.count(), 2)

    def test_expired_sessions_are_cleared(self):
        from django.contrib.sessions.models import Session
        Session.objects.create(session_key='old', session_data='', expire_date=timezone.now() - timedelta(days=1))
        self.create_room()
        self.assertFalse(Session.objects.filter(session_key='old').exists())


class RoomCodeTests(BingoClientTestCase):
    def test_code_in_lower_case_with_spaces(self):
        room = self.create_room()
        response = Client().post(reverse('bingo:go'), {'code': f'  {room.code.lower()} '})
        self.assertRedirects(response, self.url('room', room))

    def test_unknown_code(self):
        response = self.client.post(reverse('bingo:go'), {'code': 'ZZZZZ'})
        self.assertContains(response, 'Sala no encontrada o caducada', status_code=404)
        self.assertContains(response, 'name="code"', status_code=404)

    @override_settings(BINGO_ROOM_IDLE_HOURS=12)
    def test_unknown_and_expired_rooms_look_the_same(self):
        room = self.create_room()
        Room.objects.filter(pk=room.pk).update(last_activity_at=timezone.now() - timedelta(hours=13))
        expired = Client().get(self.url('room', room))
        unknown = Client().get(reverse('bingo:room', args=['ZZZZZ']))
        for response in (expired, unknown):
            self.assertContains(response, 'Sala no encontrada o caducada', status_code=404)
            self.assertContains(response, reverse('bingo:start'), status_code=404)


class JoinTests(BingoClientTestCase):
    def setUp(self):
        self.room = self.create_room()

    def test_join_with_a_nickname(self):
        client, response = self.join(self.room, 'Ana')
        self.assertRedirects(response, self.url('room', self.room))
        page = client.get(self.url('room', self.room))
        self.assertContains(page, 'Ana')
        self.assertContains(page, 'class="bingo-card"')
        self.assertEqual(Card.objects.filter(player__nickname='Ana').count(), 1)

    def test_join_after_the_game_has_started(self):
        drawn = list(range(1, 21))
        self.set_game(self.room, stage=rules.LINEA, drawn=drawn)
        client, _ = self.join(self.room, 'Late')
        state = self.state(self.room, client)
        self.assertEqual(state['drawn'], drawn)
        self.assertEqual(len(state['me']['cards']), 1)

    def test_empty_nickname(self):
        _, response = self.join(self.room, '   ')
        self.assertContains(response, 'Escribe un nombre', status_code=400)
        self.assertFalse(Player.objects.exists())

    def test_too_long_nickname(self):
        _, response = self.join(self.room, 'x' * 21)
        self.assertContains(response, 'como máximo 20', status_code=400)

    def test_nickname_taken_ignoring_case(self):
        self.join(self.room, 'Ana')
        _, response = self.join(self.room, 'ana')
        self.assertContains(response, 'ya está en uso', status_code=409)
        self.assertEqual(Player.objects.count(), 1)

    def test_markup_in_nickname_is_plain_text(self):
        client, _ = self.join(self.room, '<b>Leo</b>')
        page = client.get(self.url('room', self.room))
        self.assertContains(page, '&lt;b&gt;Leo&lt;/b&gt;')
        self.assertNotContains(page, '<b>Leo</b>')
        host = self.client.get(self.url('host', self.room))
        self.assertNotContains(host, '<b>Leo</b>')

    @override_settings(BINGO_MAX_PLAYERS=2)
    def test_room_full(self):
        self.join(self.room, 'Ana')
        self.join(self.room, 'Leo')
        _, response = self.join(self.room, 'Eva')
        self.assertContains(response, 'La sala está llena', status_code=409)
        self.assertEqual(Player.objects.count(), 2)

    def test_reload_keeps_card_and_marks(self):
        client, _ = self.join(self.room, 'Ana')
        self.give_card(self.room, 'Ana')
        self.mark(self.room, client, [3, 21, 45])
        page = client.get(self.url('room', self.room))
        self.assertContains(page, 'Ana')
        for n in (3, 21, 45):
            self.assertContains(page, f'class="cell marked" data-number="{n}"')
        self.assertContains(page, 'class="cell" data-number="62"')

    def test_join_page_for_an_existing_player(self):
        client, _ = self.join(self.room, 'Ana')
        page = client.get(self.url('room', self.room))
        self.assertNotContains(page, 'name="nickname"')
        again = client.post(self.url('join', self.room), {'nickname': 'Otro'})
        self.assertRedirects(again, self.url('room', self.room))
        self.assertEqual(Player.objects.count(), 1)

    def test_another_browser_is_a_different_player(self):
        self.join(self.room, 'Ana')
        page = Client().get(self.url('room', self.room))
        self.assertContains(page, 'name="nickname"')


class HostOnlyTests(BingoClientTestCase):
    def setUp(self):
        self.room = self.create_room()
        self.ana, _ = self.join(self.room, 'Ana')

    def test_player_cannot_use_host_actions(self):
        player = self.player(self.room, 'Ana')
        requests = [
            ('get', self.url('host', self.room), {}),
            ('post', self.url('draw', self.room), {'seen': 0}),
            ('post', self.url('continue', self.room), {}),
            ('post', self.url('auto', self.room), {'interval': 5}),
            ('post', self.url('new_game', self.room), {}),
            ('post', self.url('remove', self.room, player.pk), {}),
        ]
        game_before = self.game(self.room)
        for method, url, data in requests:
            response = getattr(self.ana, method)(url, data)
            self.assertEqual(response.status_code, 403, url)
        game_after = self.game(self.room)
        self.assertEqual(game_after.pk, game_before.pk)
        self.assertEqual(game_after.drawn, [])
        self.assertIsNone(Room.objects.get(pk=self.room.pk).auto_interval)
        self.assertFalse(self.player(self.room, 'Ana').removed)

    def test_player_state_has_no_host_view(self):
        state = self.state(self.room, self.ana, host=True)
        self.assertNotIn('players', state)

    def test_qr_encodes_the_absolute_join_url(self):
        response = self.client.get(self.url('host', self.room))
        join_url = 'http://testserver' + self.url('room', self.room)
        self.assertEqual(response.context['join_url'], join_url)
        expected = segno.make(join_url, error='m').svg_inline(scale=8, border=2, omitsize=True)
        self.assertEqual(response.context['qr_svg'], expected)
        self.assertContains(response, expected)

    def test_sound_controls_only_on_the_host_screen(self):
        host_page = self.client.get(self.url('host', self.room))
        self.assertContains(host_page, 'id="sound-toggle"')
        self.assertContains(host_page, 'id="ball-sound"')
        player_page = self.ana.get(self.url('room', self.room))
        self.assertEqual(player_page.status_code, 200)
        self.assertNotContains(player_page, 'id="sound-toggle"')
        self.assertNotContains(player_page, 'id="ball-sound"')

    def test_qr_scales_to_its_frame(self):
        qr_svg = self.client.get(self.url('host', self.room)).context['qr_svg']
        self.assertIn('viewBox=', qr_svg)
        self.assertNotIn('width=', qr_svg)

    def test_host_also_plays(self):
        _, response = self.join(self.room, 'Host', client=self.client)
        self.assertRedirects(response, self.url('room', self.room))
        self.assertEqual(self.client.get(self.url('host', self.room)).status_code, 200)
        self.assertIn('me', self.state(self.room, self.client))
        self.assertIn('players', self.state(self.room, self.client, host=True))

    def test_new_player_shows_up_in_host_state(self):
        self.join(self.room, 'Leo')
        names = [p['nickname'] for p in self.state(self.room, self.client, host=True)['players']]
        self.assertEqual(names, ['Ana', 'Leo'])


class GameTestCase(BingoClientTestCase):
    """A room with host (self.client), Ana and Leo, both holding sample_grid-like cards."""

    def setUp(self):
        self.room = self.create_room()
        self.ana, _ = self.join(self.room, 'Ana')
        self.leo, _ = self.join(self.room, 'Leo')
        self.give_card(self.room, 'Ana')
        leo_grid = [row[:] for row in sample_grid()]
        leo_grid[0][0] = 4  # distinct from Ana's card, same second row
        self.give_card(self.room, 'Leo', leo_grid)

    def draw(self, seen=None, client=None):
        client = client or self.client
        if seen is None:
            seen = len(self.game(self.room).drawn)
        return client.post(self.url('draw', self.room), {'seen': seen})

    def playing(self, stage=rules.LINEA, drawn=(), **fields):
        self.set_game(self.room, stage=stage, drawn=list(drawn), **fields)

    def at(self, moment):
        return mock.patch('django.utils.timezone.now', return_value=moment)


class DrawTests(GameTestCase):
    def test_host_draws_a_new_ball(self):
        self.playing(drawn=range(1, 11))
        response = self.draw()
        self.assertEqual(response.status_code, 200)
        drawn = self.game(self.room).drawn
        self.assertEqual(len(drawn), 11)
        self.assertNotIn(drawn[-1], range(1, 11))
        self.assertEqual(response.json()['state']['last'], drawn[-1])

    def test_first_ball_starts_the_game(self):
        self.draw()
        self.assertEqual(self.game(self.room).stage, rules.LINEA)

    def test_repeated_request_draws_only_one_ball(self):
        self.draw(seen=0)
        self.draw(seen=0)
        self.assertEqual(len(self.game(self.room).drawn), 1)

    def test_no_draw_during_a_pause(self):
        self.playing(drawn=[1], pause_prize=rules.LINEA, pause_ends_at=timezone.now() + timedelta(seconds=5))
        response = self.draw()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.game(self.room).drawn, [1])

    def test_no_draw_after_the_game_finished(self):
        self.playing(stage=rules.FINISHED, drawn=[1, 2])
        self.assertEqual(self.draw().status_code, 409)
        self.assertEqual(self.game(self.room).drawn, [1, 2])

    def test_no_balls_left(self):
        self.playing(stage=rules.BINGO, drawn=range(1, 91))
        response = self.draw()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['message'], 'No quedan bolas.')

    def test_drawn_numbers_are_not_marked_for_players(self):
        self.playing(drawn=ROW2)
        self.draw()
        self.assertEqual(self.marks(self.room, self.ana), [])


class MarkTests(GameTestCase):
    def test_mark_drawn_and_undrawn_numbers(self):
        self.playing(drawn=[47])
        self.mark(self.room, self.ana, [47, 3])
        self.assertEqual(self.marks(self.room, self.ana), [3, 47])

    def test_unmark(self):
        self.mark(self.room, self.ana, [47])
        self.mark(self.room, self.ana, [47], marked=False)
        self.assertEqual(self.marks(self.room, self.ana), [])

    def test_marking_twice_is_idempotent(self):
        self.mark(self.room, self.ana, [47, 47])
        self.assertEqual(self.marks(self.room, self.ana), [47])

    def test_number_not_on_card(self):
        response = self.ana.post(self.url('mark', self.room), {'number': 50, 'marked': '1'})
        self.assertEqual(response.status_code, 400)

    def test_only_own_card_changes(self):
        self.mark(self.room, self.leo, [14])
        self.assertEqual(self.marks(self.room, self.ana), [])
        self.assertEqual(self.marks(self.room, self.leo), [14])

    def test_stranger_cannot_mark(self):
        response = Client().post(self.url('mark', self.room), {'number': 14, 'marked': '1'})
        self.assertEqual(response.status_code, 403)

    def test_no_marks_after_the_game_finished(self):
        self.playing(stage=rules.FINISHED)
        response = self.ana.post(self.url('mark', self.room), {'number': 14, 'marked': '1'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.marks(self.room, self.ana), [])


class ClaimTests(GameTestCase):
    def test_valid_linea(self):
        self.playing(drawn=ROW2 + [5])
        self.mark(self.room, self.ana, ROW2)
        response = self.claim(self.room, self.ana, 'linea')
        self.assertEqual(response.status_code, 200)
        state = response.json()['state']
        self.assertEqual(state['pause']['prize'], 'linea')
        self.assertEqual(state['winners']['linea'], [{'nickname': 'Ana', 'numbers': ROW2}])

    def test_row_drawn_but_not_fully_marked(self):
        self.playing(drawn=ROW2)
        self.mark(self.room, self.ana, ROW2[:4])
        response = self.claim(self.room, self.ana, 'linea')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['message'], 'Esa línea no es válida. Revisa tu cartón.')

    def test_row_marked_but_not_fully_drawn(self):
        self.playing(drawn=ROW2[:4])
        self.mark(self.room, self.ana, ROW2)
        self.assertEqual(self.claim(self.room, self.ana, 'linea').status_code, 409)

    def test_late_claim(self):
        self.playing(drawn=ROW2 + [1, 2, 5, 6, 8, 9])
        self.mark(self.room, self.ana, ROW2)
        self.assertEqual(self.claim(self.room, self.ana, 'linea').status_code, 200)

    def test_valid_bingo(self):
        numbers = rules.card_numbers(sample_grid())
        self.playing(stage=rules.BINGO, drawn=numbers)
        self.mark(self.room, self.ana, numbers)
        response = self.claim(self.room, self.ana, 'bingo')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['state']['winners']['bingo'][0]['nickname'], 'Ana')

    def test_bingo_with_one_number_not_drawn(self):
        numbers = rules.card_numbers(sample_grid())
        self.playing(stage=rules.BINGO, drawn=numbers[:-1])
        self.mark(self.room, self.ana, numbers)
        response = self.claim(self.room, self.ana, 'bingo')
        self.assertEqual(response.json()['message'], 'Ese bingo no es válido. Revisa tu cartón.')

    def test_bingo_while_playing_for_linea(self):
        self.playing(drawn=ROW2)
        response = self.claim(self.room, self.ana, 'bingo')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['message'], 'Ahora se juega la línea.')

    def test_invalid_claim_only_tells_the_claimer(self):
        self.playing(drawn=ROW2)
        self.claim(self.room, self.ana, 'linea')
        self.assertIsNone(self.state(self.room, self.leo)['pause'])
        self.assertIsNone(self.state(self.room, self.client, host=True)['pause'])
        self.assertEqual(self.game(self.room).stage, rules.LINEA)
        self.assertEqual(self.draw().status_code, 200)
        self.mark(self.room, self.ana, ROW2)
        self.assertEqual(self.claim(self.room, self.ana, 'linea').status_code, 200)

    def test_shared_linea(self):
        self.playing(drawn=ROW2)
        self.mark(self.room, self.ana, ROW2)
        self.mark(self.room, self.leo, ROW2)
        self.claim(self.room, self.ana, 'linea')
        ends_at = self.game(self.room).pause_ends_at
        response = self.claim(self.room, self.leo, 'linea')
        self.assertEqual(response.status_code, 200)
        names = [w['nickname'] for w in self.state(self.room, self.client, host=True)['winners']['linea']]
        self.assertEqual(names, ['Ana', 'Leo'])
        self.assertEqual(self.game(self.room).pause_ends_at, ends_at)

    def test_linea_closed_after_the_pause(self):
        self.playing(drawn=ROW2)
        self.mark(self.room, self.ana, ROW2)
        self.mark(self.room, self.leo, ROW2)
        self.claim(self.room, self.ana, 'linea')
        with self.at(timezone.now() + timedelta(seconds=11)):
            response = self.claim(self.room, self.leo, 'linea')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['message'], 'La línea ya se cantó. Ahora se juega el bingo.')


class PauseAndAutoTests(GameTestCase):
    def pause_for(self, prize):
        stage = rules.LINEA if prize == 'linea' else rules.BINGO
        self.playing(stage=stage, drawn=[1], pause_prize=prize, pause_ends_at=timezone.now() + timedelta(seconds=8))

    def test_continue_ends_the_pause_and_moves_on(self):
        self.pause_for('linea')
        response = self.client.post(self.url('continue', self.room))
        self.assertEqual(response.status_code, 200)
        game = self.game(self.room)
        self.assertEqual(game.stage, rules.BINGO)
        self.assertIsNone(game.pause_ends_at)
        self.assertEqual(self.draw().status_code, 200)

    def test_bingo_pause_finishes_the_game(self):
        self.pause_for('bingo')
        self.client.post(self.url('continue', self.room))
        self.assertEqual(self.game(self.room).stage, rules.FINISHED)

    def test_pause_ends_by_itself(self):
        self.pause_for('bingo')
        with self.at(timezone.now() + timedelta(seconds=9)):
            self.assertEqual(self.state(self.room, self.ana)['stage'], rules.FINISHED)
            self.assertIsNone(self.state(self.room, self.ana)['pause'])

    def test_pause_shows_remaining_time(self):
        self.pause_for('linea')
        pause = self.state(self.room, self.ana)['pause']
        self.assertEqual(pause['total_ms'], 10000)
        self.assertTrue(7000 < pause['remaining_ms'] <= 8000)

    def test_invalid_interval(self):
        response = self.client.post(self.url('auto', self.room), {'interval': 7})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(Room.objects.get(pk=self.room.pk).auto_interval)

    def test_auto_setting_survives_a_reload(self):
        self.client.post(self.url('auto', self.room), {'interval': 10})
        page = self.client.get(self.url('host', self.room))
        self.assertContains(page, '<option value="10" selected>')
        self.client.post(self.url('auto', self.room), {'interval': 'off'})
        self.assertIsNone(Room.objects.get(pk=self.room.pk).auto_interval)

    def test_next_auto_draw(self):
        now = timezone.now()
        with self.at(now):
            self.client.post(self.url('auto', self.room), {'interval': 10})
        with self.at(now + timedelta(seconds=4)):
            self.assertEqual(self.state(self.room, self.client, host=True)['next_auto_draw_ms'], 6000)
        with self.at(now + timedelta(seconds=12)):
            self.draw()
        with self.at(now + timedelta(seconds=13)):
            self.assertEqual(self.state(self.room, self.client, host=True)['next_auto_draw_ms'], 9000)

    def test_auto_draw_waits_for_the_pause(self):
        self.client.post(self.url('auto', self.room), {'interval': 5})
        self.pause_for('linea')
        self.assertIsNone(self.state(self.room, self.client, host=True)['next_auto_draw_ms'])
        ends_at = self.game(self.room).pause_ends_at
        with self.at(ends_at + timedelta(seconds=1)):
            self.assertEqual(self.state(self.room, self.client, host=True)['next_auto_draw_ms'], 4000)


class StateTests(GameTestCase):
    def test_state_per_stage(self):
        state = self.state(self.room, self.ana)
        self.assertEqual(state['stage'], rules.WAITING)
        self.assertIsNone(state['last'])
        self.playing(drawn=[5, 9])
        state = self.state(self.room, self.ana)
        self.assertEqual((state['stage'], state['drawn'], state['last'], state['balls_left']), ('linea', [5, 9], 9, 88))
        self.playing(stage=rules.FINISHED, drawn=[5, 9])
        self.assertEqual(self.state(self.room, self.ana)['stage'], rules.FINISHED)

    def test_poll_writes_nothing(self):
        from django.contrib.sessions.models import Session
        Room.objects.filter(pk=self.room.pk).update(last_activity_at=timezone.now() - timedelta(hours=1))
        before = Room.objects.get(pk=self.room.pk).last_activity_at
        sessions = list(Session.objects.values_list('session_key', 'session_data', 'expire_date'))
        version = self.game(self.room).version
        self.state(self.room, self.ana)
        self.state(self.room, self.client, host=True)
        self.assertEqual(Room.objects.get(pk=self.room.pk).last_activity_at, before)
        self.assertEqual(list(Session.objects.values_list('session_key', 'session_data', 'expire_date')), sessions)
        self.assertEqual(self.game(self.room).version, version)

    def test_player_view_has_only_their_card(self):
        state = self.state(self.room, self.ana)
        self.assertEqual(set(state), {'game_id', 'stage', 'drawn', 'last', 'balls_left', 'pause', 'winners', 'me'})
        self.assertEqual(state['me']['cards'], [{'position': 0, 'grid': sample_grid(), 'marks': []}])

    def test_stranger_gets_no_state(self):
        self.assertEqual(Client().get(self.url('state', self.room)).status_code, 403)


class NewGameAndRemoveTests(GameTestCase):
    def test_new_game_in_the_same_room(self):
        self.mark(self.room, self.ana, [3])
        self.playing(stage=rules.FINISHED, drawn=ROW2)
        old_game = self.game(self.room).pk
        response = self.client.post(self.url('new_game', self.room))
        self.assertEqual(response.status_code, 200)
        game = self.game(self.room)
        self.assertNotEqual(game.pk, old_game)
        self.assertEqual((game.stage, game.drawn), (rules.WAITING, []))
        self.assertFalse(game.claims.exists())
        self.assertEqual(Room.objects.get(pk=self.room.pk).code, self.room.code)
        state = self.state(self.room, self.ana)
        self.assertEqual(state['game_id'], game.pk)
        self.assertEqual(len(state['me']['cards']), 1)
        self.assertEqual(state['me']['cards'][0]['marks'], [])
        self.assertEqual(game.cards.count(), 2)

    def test_remove_player(self):
        troll, _ = self.join(self.room, 'Troll')
        player = self.player(self.room, 'Troll')
        response = self.client.post(self.url('remove', self.room, player.pk))
        self.assertEqual(response.status_code, 200)
        names = [p['nickname'] for p in response.json()['state']['players']]
        self.assertNotIn('Troll', names)
        self.assertTrue(self.state(self.room, troll)['me']['removed'])
        page = troll.get(self.url('room', self.room))
        self.assertContains(page, 'Te han sacado de la sala', status_code=403)

    def test_removed_player_cannot_rejoin_or_play(self):
        troll, _ = self.join(self.room, 'Troll')
        self.client.post(self.url('remove', self.room, self.player(self.room, 'Troll').pk))
        troll.post(self.url('join', self.room), {'nickname': 'Troll2'})
        self.assertFalse(Player.objects.filter(nickname='Troll2').exists())
        self.assertEqual(self.claim(self.room, troll, 'linea').status_code, 403)

    def test_removed_winner_stops_counting(self):
        self.playing(drawn=ROW2)
        self.mark(self.room, self.leo, ROW2)
        self.claim(self.room, self.leo, 'linea')
        self.client.post(self.url('remove', self.room, self.player(self.room, 'Leo').pk))
        self.assertEqual(self.state(self.room, self.ana)['winners']['linea'], [])
        self.assertEqual(self.game(self.room).stage, rules.LINEA)


class ActivityTests(GameTestCase):
    @override_settings(BINGO_ROOM_IDLE_HOURS=12)
    def test_actions_keep_the_room_alive_and_polls_do_not(self):
        old = timezone.now() - timedelta(hours=11)
        actions = [
            lambda: self.join(self.room, 'Eva'),
            lambda: self.mark(self.room, self.ana, [3]),
            lambda: self.claim(self.room, self.ana, 'linea'),
            lambda: self.draw(),
            lambda: self.client.post(self.url('auto', self.room), {'interval': 'off'}),
            lambda: self.client.post(self.url('continue', self.room)),
            lambda: self.client.post(self.url('new_game', self.room)),
        ]
        for action in actions:
            Room.objects.filter(pk=self.room.pk).update(last_activity_at=old)
            action()
            self.assertGreater(Room.objects.get(pk=self.room.pk).last_activity_at, old, action)

        Room.objects.filter(pk=self.room.pk).update(last_activity_at=old)
        self.state(self.room, self.ana)
        self.assertEqual(Room.objects.get(pk=self.room.pk).last_activity_at, old)
        with self.at(timezone.now() + timedelta(hours=2)):
            self.assertEqual(self.ana.get(self.url('state', self.room)).status_code, 404)


EVA_CARD0 = [
    [1, None, 20, None, 40, None, 60, None, 80],
    [None, 10, None, 30, 47, None, None, 70, 81],
    [2, None, 22, 31, None, 50, None, 72, None],
]
EVA_ROW0 = [10, 30, 47, 70, 81]


def eva_card1():
    grid = [row[:] for row in sample_grid()]
    grid[0][0] = 5  # distinct from Ana's and Leo's cards, same second row (ROW2)
    return grid


class TwoCardTestCase(GameTestCase):
    """GameTestCase plus Eva, who plays with 2 cards: EVA_CARD0 and eva_card1()."""

    def setUp(self):
        super().setUp()
        self.eva, _ = self.join(self.room, 'Eva', cards='2')
        self.give_card(self.room, 'Eva', EVA_CARD0, position=0)
        self.give_card(self.room, 'Eva', eva_card1(), position=1)

    def set_count(self, client, count):
        return client.post(self.url('cards', self.room), {'count': count})


class TwoCardJoinTests(BingoClientTestCase):
    def setUp(self):
        self.room = self.create_room()

    def test_join_with_two_cards(self):
        client, response = self.join(self.room, 'Leo', cards='2')
        self.assertRedirects(response, self.url('room', self.room))
        cards = self.state(self.room, client)['me']['cards']
        self.assertEqual([c['position'] for c in cards], [0, 1])
        self.assertNotEqual(rules.card_numbers(cards[0]['grid']), rules.card_numbers(cards[1]['grid']))
        self.assertEqual(self.state(self.room, client)['me']['card_count'], 2)

    def test_join_without_a_choice_gives_one_card(self):
        client, _ = self.join(self.room, 'Ana')
        self.assertEqual(len(self.state(self.room, client)['me']['cards']), 1)
        client, _ = self.join(self.room, 'Leo', cards='7')
        self.assertEqual(len(self.state(self.room, client)['me']['cards']), 1)

    def test_join_with_two_cards_after_the_game_has_started(self):
        self.set_game(self.room, stage=rules.LINEA, drawn=list(range(1, 21)))
        client, _ = self.join(self.room, 'Late', cards='2')
        state = self.state(self.room, client)
        self.assertEqual(len(state['me']['cards']), 2)
        self.assertEqual(len(state['drawn']), 20)

    def test_form_keeps_the_choice_after_an_error(self):
        _, response = self.join(self.room, '  ', cards='2')
        self.assertContains(response, 'value="2" checked', status_code=400)
        _, response = self.join(self.room, '  ')
        self.assertContains(response, 'value="1" checked', status_code=400)

    def test_join_form_offers_one_or_two_cards(self):
        page = Client().get(self.url('room', self.room))
        self.assertContains(page, '1 cartón')
        self.assertContains(page, '2 cartones')


class TwoCardStateTests(TwoCardTestCase):
    def test_new_game_keeps_the_number_of_cards(self):
        old = {c.pk for c in Card.objects.filter(player__nickname='Eva')}
        self.client.post(self.url('new_game', self.room))
        new = Card.objects.filter(player__nickname='Eva')
        self.assertEqual(sorted(c.position for c in new), [0, 1])
        self.assertFalse(old & {c.pk for c in new})
        self.assertTrue(all(c.marks == [] for c in new))

    def test_host_sees_the_number_of_cards(self):
        players = self.state(self.room, self.client, host=True)['players']
        self.assertEqual({p['nickname']: p['cards'] for p in players}, {'Ana': 1, 'Leo': 1, 'Eva': 2})
        page = self.client.get(self.url('host', self.room))
        self.assertContains(page, 'Eva <span class="card-tag">×2</span>', html=False)
        self.assertNotContains(page, 'Ana <span class="card-tag">')

    def test_player_page_shows_both_cards_with_labels(self):
        page = self.eva.get(self.url('room', self.room))
        self.assertContains(page, 'data-card="0"')
        self.assertContains(page, 'data-card="1"')
        self.assertContains(page, 'Cartón 1')
        self.assertContains(page, 'Cartón 2')
        one = self.ana.get(self.url('room', self.room))
        self.assertContains(one, 'data-card="0"')
        self.assertNotContains(one, 'data-card="1"')
        self.assertNotContains(one, 'Cartón 1')


class TwoCardMarkTests(TwoCardTestCase):
    def test_marks_belong_to_one_card(self):
        self.mark(self.room, self.eva, [47], card=1)
        self.assertEqual(self.marks(self.room, self.eva, card=0), [])
        self.assertEqual(self.marks(self.room, self.eva, card=1), [47])
        self.mark(self.room, self.eva, [47], card=0)
        self.mark(self.room, self.eva, [47], marked=False, card=1)
        self.assertEqual(self.marks(self.room, self.eva, card=0), [47])
        self.assertEqual(self.marks(self.room, self.eva, card=1), [])

    def test_unknown_card_is_refused(self):
        response = self.eva.post(self.url('mark', self.room), {'number': 47, 'marked': '1', 'card': 5})
        self.assertEqual(response.status_code, 400)
        response = self.ana.post(self.url('mark', self.room), {'number': 47, 'marked': '1', 'card': 1})
        self.assertEqual(response.status_code, 400)

    def test_other_players_cards_do_not_change(self):
        self.mark(self.room, self.ana, [14])
        self.assertEqual(self.marks(self.room, self.eva, card=0), [])
        self.assertEqual(self.marks(self.room, self.eva, card=1), [])


class TwoCardClaimTests(TwoCardTestCase):
    def test_linea_on_the_second_card(self):
        self.playing(drawn=ROW2)
        self.mark(self.room, self.eva, ROW2, card=1)
        response = self.claim(self.room, self.eva, 'linea')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['state']['winners']['linea'], [{'nickname': 'Eva', 'numbers': ROW2}])
        self.assertEqual(self.game(self.room).claims.get().position, 1)

    def test_row_split_across_cards_is_invalid(self):
        self.playing(drawn=ROW2)
        self.mark(self.room, self.eva, [47], card=0)
        self.mark(self.room, self.eva, [14, 33, 71, 90], card=1)
        response = self.claim(self.room, self.eva, 'linea')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['message'], 'Esa línea no es válida. Revisa tu cartón.')

    def test_bingo_on_the_second_card(self):
        numbers = rules.card_numbers(eva_card1())
        self.playing(stage=rules.BINGO, drawn=numbers)
        self.mark(self.room, self.eva, numbers, card=1)
        response = self.claim(self.room, self.eva, 'bingo')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['state']['winners']['bingo'], [{'nickname': 'Eva', 'numbers': numbers}])

    def test_both_cards_win_once(self):
        self.playing(drawn=ROW2 + EVA_ROW0)
        self.mark(self.room, self.eva, EVA_ROW0, card=0)
        self.mark(self.room, self.eva, ROW2, card=1)
        self.assertEqual(self.claim(self.room, self.eva, 'linea').status_code, 200)
        self.assertEqual(self.claim(self.room, self.eva, 'linea').status_code, 200)
        winners = self.state(self.room, self.client, host=True)['winners']['linea']
        self.assertEqual(winners, [{'nickname': 'Eva', 'numbers': EVA_ROW0}])


class CardCountTests(TwoCardTestCase):
    def test_add_a_second_card_before_the_start(self):
        self.mark(self.room, self.ana, [3])
        response = self.set_count(self.ana, 2)
        self.assertEqual(response.status_code, 200)
        cards = response.json()['state']['me']['cards']
        self.assertEqual(len(cards), 2)
        self.assertEqual((cards[0]['grid'], cards[0]['marks']), (sample_grid(), [3]))
        self.assertEqual(self.state(self.room, self.client, host=True)['players'][0]['cards'], 2)

    def test_back_to_one_card(self):
        self.mark(self.room, self.eva, [47], card=0)
        response = self.set_count(self.eva, 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['state']['me']['cards'],
                         [{'position': 0, 'grid': EVA_CARD0, 'marks': [47]}])

    def test_refused_once_the_game_started(self):
        self.draw()
        response = self.set_count(self.ana, 2)
        self.assertEqual(response.status_code, 409)
        self.assertIn('La partida ya ha empezado', response.json()['message'])
        self.assertEqual(Card.objects.filter(player__nickname='Ana').count(), 1)
        self.assertEqual(self.player(self.room, 'Ana').card_count, 1)

    def test_bad_values(self):
        for value in ('0', '3', 'dos', ''):
            self.assertEqual(self.set_count(self.ana, value).status_code, 400, value)
        self.assertEqual(Card.objects.filter(player__nickname='Ana').count(), 1)

    def test_strangers_and_removed_players(self):
        self.assertEqual(self.set_count(Client(), 2).status_code, 403)
        self.client.post(self.url('remove', self.room, self.player(self.room, 'Leo').pk))
        self.assertEqual(self.set_count(self.leo, 2).status_code, 403)

    def test_allowed_again_in_a_new_game(self):
        self.playing(stage=rules.FINISHED, drawn=[1, 2])
        self.assertEqual(self.set_count(self.ana, 2).status_code, 409)
        self.client.post(self.url('new_game', self.room))
        self.assertEqual(self.set_count(self.ana, 2).status_code, 200)
        self.assertEqual(Card.objects.filter(player__nickname='Ana').count(), 2)
