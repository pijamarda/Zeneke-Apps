import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from . import rules

CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 5
NICKNAME_MAX_LENGTH = 20
AUTO_INTERVALS = (5, 8, 10, 15, 20)

rng = secrets.SystemRandom()


def generate_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def idle_cutoff(now=None):
    return (now or timezone.now()) - timedelta(hours=settings.BINGO_ROOM_IDLE_HOURS)


class RoomQuerySet(models.QuerySet):
    def active(self, now=None):
        return self.filter(last_activity_at__gte=idle_cutoff(now))

    def expired(self, now=None):
        return self.filter(last_activity_at__lt=idle_cutoff(now))


class Room(models.Model):
    code = models.CharField(max_length=CODE_LENGTH, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)
    auto_interval = models.PositiveSmallIntegerField(null=True, blank=True)
    auto_since = models.DateTimeField(null=True, blank=True)

    objects = RoomQuerySet.as_manager()

    def __str__(self):
        return self.code

    @classmethod
    def create_with_game(cls):
        for _ in range(20):
            try:
                with transaction.atomic():
                    room = cls.objects.create(code=generate_code())
                    Game.objects.create(room=room)
                    return room
            except IntegrityError:
                continue
        raise RuntimeError('Could not find a free room code')

    def touch(self, now=None):
        now = now or timezone.now()
        Room.objects.filter(pk=self.pk).update(last_activity_at=now)
        self.last_activity_at = now


class Game(models.Model):
    STAGES = [
        (rules.WAITING, 'Esperando'),
        (rules.LINEA, 'Jugando a línea'),
        (rules.BINGO, 'Jugando a bingo'),
        (rules.FINISHED, 'Terminada'),
    ]
    PRIZE_CHOICES = [(rules.LINEA, 'Línea'), (rules.BINGO, 'Bingo')]

    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='game')
    stage = models.CharField(max_length=10, choices=STAGES, default=rules.WAITING)
    drawn = models.JSONField(default=list)
    pause_prize = models.CharField(max_length=10, choices=PRIZE_CHOICES, null=True, blank=True)
    pause_ends_at = models.DateTimeField(null=True, blank=True)
    last_draw_at = models.DateTimeField(null=True, blank=True)
    resumed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.room.code} ({self.stage})'

    def state(self):
        return rules.GameState(
            stage=self.stage,
            drawn=tuple(self.drawn),
            pause_prize=self.pause_prize,
            pause_ends_at=self.pause_ends_at,
        )

    def settled(self, now):
        """The state with any ended pause applied, and when play last resumed."""
        state = self.state()
        new = rules.settle(state, now)
        resumed_at = self.resumed_at
        if state.paused and not new.paused:
            resumed_at = state.pause_ends_at
        return new, resumed_at


class Player(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='players')
    nickname = models.CharField(max_length=NICKNAME_MAX_LENGTH)
    nickname_key = models.CharField(max_length=NICKNAME_MAX_LENGTH)
    removed = models.BooleanField(default=False)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['joined_at', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['room', 'nickname_key'], name='bingo_unique_nickname_per_room'),
        ]

    def __str__(self):
        return self.nickname


class Card(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='cards')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='cards')
    grid = models.JSONField()
    marks = models.JSONField(default=list)
    numbers_key = models.CharField(max_length=60)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['game', 'numbers_key'], name='bingo_unique_card_per_game'),
            models.UniqueConstraint(fields=['game', 'player'], name='bingo_one_card_per_player'),
        ]

    def numbers(self):
        return rules.card_numbers(self.grid)


def deal_card(game, player):
    """Give the player a card for this game, distinct from the others in it."""
    existing = Card.objects.filter(game=game, player=player).first()
    if existing:
        return existing
    for _ in range(50):
        grid = rules.generate_card(rng)
        try:
            with transaction.atomic():
                return Card.objects.create(
                    game=game, player=player, grid=grid, numbers_key=rules.numbers_key(grid)
                )
        except IntegrityError:
            existing = Card.objects.filter(game=game, player=player).first()
            if existing:
                return existing
    raise RuntimeError('Could not deal a distinct card')


class Claim(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='claims')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='claims')
    prize = models.CharField(max_length=10, choices=Game.PRIZE_CHOICES)
    row = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['game', 'player', 'prize'], name='bingo_one_claim_per_prize'),
        ]

    def winning_numbers(self, card):
        if self.prize == rules.LINEA and self.row is not None:
            return [n for n in card.grid[self.row] if n is not None]
        return card.numbers()
