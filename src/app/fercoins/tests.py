from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import KidProfile

from .models import FercoinTransaction

User = get_user_model()


class FercoinsMembersTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_superuser('mama', password='strong-pass-123')
        self.client.force_login(self.parent)
        self.stranger = User.objects.create_user('stranger', email='s@example.com')

    def make_kid(self, username='leo'):
        user = User.objects.create_user(username)
        KidProfile.objects.create(user=user)
        return user

    def test_non_kid_not_listed_or_offered(self):
        kid = self.make_kid()
        manage = self.client.get(reverse('fercoins:manage'))
        self.assertContains(manage, kid.username)
        self.assertNotContains(manage, 'stranger')

        give = self.client.get(reverse('fercoins:give'))
        self.assertContains(give, kid.username)
        self.assertNotContains(give, 'stranger')

    def test_forged_recipient_rejected(self):
        response = self.client.post(reverse('fercoins:give'), {
            'recipient': self.stranger.pk, 'amount': 10, 'note': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FercoinTransaction.objects.exists())

    def test_kid_can_receive_and_starts_at_zero(self):
        kid = self.make_kid()
        manage = self.client.get(reverse('fercoins:manage'))
        self.assertEqual(manage.context['members'].get(pk=kid.pk).balance, 0)

        response = self.client.post(reverse('fercoins:give'), {
            'recipient': kid.pk, 'amount': 10, 'note': 'platos',
        })
        self.assertRedirects(response, reverse('fercoins:manage'))
        self.assertEqual(FercoinTransaction.objects.get().recipient, kid)

    def test_empty_state_links_to_family(self):
        response = self.client.get(reverse('fercoins:manage'))
        self.assertContains(response, reverse('core:family'))
