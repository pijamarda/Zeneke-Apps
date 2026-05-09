from django.contrib.auth import get_user_model
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
