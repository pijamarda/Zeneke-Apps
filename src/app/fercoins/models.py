from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum

User = get_user_model()


class Chore(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    fercoins = models.IntegerField(help_text='Positive to reward, negative to penalise')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        sign = '+' if self.fercoins >= 0 else ''
        return f'{self.name} ({sign}{self.fercoins})'


class FercoinTransaction(models.Model):
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='fercoins_received'
    )
    amount = models.IntegerField(help_text='Positive to add, negative to deduct')
    chore = models.ForeignKey(
        Chore, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    note = models.CharField(max_length=255, blank=True)
    given_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='fercoins_given'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f'{self.recipient.username} {sign}{self.amount} by {self.given_by}'


def get_balance(user):
    result = user.fercoins_received.aggregate(total=Sum('amount'))
    return result['total'] or 0


class Prize(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    cost = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['cost', 'name']

    def __str__(self):
        return f'{self.name} ({self.cost})'


class ReviewableRequest(models.Model):
    """A kid's request that waits for a parent's review before any coins move."""

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (PENDING, 'Pendiente'),
        (APPROVED, 'Aprobada'),
        (REJECTED, 'Rechazada'),
        (CANCELLED, 'Cancelada'),
    ]

    amount = models.PositiveIntegerField(help_text='Recorded when the kid submits it')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    transaction = models.OneToOneField(
        FercoinTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

    @property
    def is_pending(self):
        return self.status == self.PENDING


class ChoreClaim(ReviewableRequest):
    kid = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chore_claims')
    chore = models.ForeignKey(Chore, on_delete=models.CASCADE, related_name='claims')

    class Meta(ReviewableRequest.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['kid', 'chore'],
                condition=models.Q(status='pending'),
                name='one_pending_claim_per_chore',
            ),
        ]

    def __str__(self):
        return f'{self.kid.username}: {self.chore.name} +{self.amount} ({self.status})'


class PrizeRequest(ReviewableRequest):
    kid = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prize_requests')
    prize = models.ForeignKey(Prize, on_delete=models.CASCADE, related_name='requests')

    def __str__(self):
        return f'{self.kid.username}: {self.prize.name} -{self.amount} ({self.status})'


def get_available_balance(user):
    pending = user.prize_requests.filter(status=PrizeRequest.PENDING).aggregate(
        total=Sum('amount')
    )
    return get_balance(user) - (pending['total'] or 0)
