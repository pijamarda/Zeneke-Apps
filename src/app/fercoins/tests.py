from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from core.models import KidProfile

from . import services

from .models import (
    Chore, ChoreClaim, FercoinTransaction, Prize, PrizeRequest, get_available_balance, get_balance,
)

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


def make_kid(username='leo'):
    user = User.objects.create_user(username)
    KidProfile.objects.create(user=user)
    return user


class ReviewableModelTests(TestCase):
    def setUp(self):
        self.leo = make_kid('leo')
        self.ana = make_kid('ana')
        self.bed = Chore.objects.create(name='Hacer la cama', fercoins=5)
        self.ice = Prize.objects.create(name='Helado', cost=20)

    def test_one_pending_claim_per_kid_and_chore(self):
        ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)

    def test_claim_allowed_again_after_review_and_for_other_kid(self):
        first = ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        ChoreClaim.objects.create(kid=self.ana, chore=self.bed, amount=5)
        first.status = ChoreClaim.APPROVED
        first.save()
        ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        self.assertEqual(ChoreClaim.objects.filter(status=ChoreClaim.PENDING).count(), 2)

    def test_available_balance_subtracts_only_pending_requests(self):
        FercoinTransaction.objects.create(recipient=self.leo, amount=100)
        PrizeRequest.objects.create(kid=self.leo, prize=self.ice, amount=20)
        for status in (PrizeRequest.APPROVED, PrizeRequest.REJECTED, PrizeRequest.CANCELLED):
            PrizeRequest.objects.create(kid=self.leo, prize=self.ice, amount=7, status=status)
        PrizeRequest.objects.create(kid=self.ana, prize=self.ice, amount=20)
        self.assertEqual(get_balance(self.leo), 100)
        self.assertEqual(get_available_balance(self.leo), 80)


class ReviewServiceTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_superuser('mama', password='strong-pass-123')
        self.leo = make_kid('leo')
        self.bed = Chore.objects.create(name='Hacer la cama', fercoins=5)
        self.ice = Prize.objects.create(name='Helado', cost=20)

    def claim(self):
        return ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)

    def prize_request(self):
        return PrizeRequest.objects.create(kid=self.leo, prize=self.ice, amount=20)

    def test_approve_claim_credits_recorded_amount(self):
        claim = self.claim()
        self.bed.fercoins = 8
        self.bed.save()
        self.assertTrue(services.approve_claim(claim, self.parent))
        tx = FercoinTransaction.objects.get()
        self.assertEqual((tx.amount, tx.chore, tx.given_by), (5, self.bed, self.parent))
        claim.refresh_from_db()
        self.assertEqual((claim.status, claim.transaction), (ChoreClaim.APPROVED, tx))

    def test_approve_request_deducts_recorded_cost(self):
        FercoinTransaction.objects.create(recipient=self.leo, amount=42)
        request_ = self.prize_request()
        self.ice.cost = 25
        self.ice.save()
        self.assertTrue(services.approve_request(request_, self.parent))
        self.assertEqual(get_balance(self.leo), 22)
        tx = self.leo.fercoins_received.get(amount=-20)
        self.assertEqual((tx.note, tx.given_by), ('Premio: Helado', self.parent))

    def test_double_approval_moves_coins_once(self):
        claim, request_ = self.claim(), self.prize_request()
        services.approve_claim(claim, self.parent)
        services.approve_request(request_, self.parent)
        self.assertFalse(services.approve_claim(claim, self.parent))
        self.assertFalse(services.approve_request(request_, self.parent))
        self.assertEqual(FercoinTransaction.objects.count(), 2)

    def test_reject_or_cancel_after_approval_keeps_approval(self):
        claim, request_ = self.claim(), self.prize_request()
        services.approve_claim(claim, self.parent)
        services.approve_request(request_, self.parent)
        self.assertFalse(services.reject_claim(claim, self.parent))
        self.assertFalse(services.reject_request(request_, self.parent))
        self.assertFalse(services.cancel_request(request_, self.leo))
        claim.refresh_from_db()
        request_.refresh_from_db()
        self.assertEqual(claim.status, ChoreClaim.APPROVED)
        self.assertEqual(request_.status, PrizeRequest.APPROVED)
        self.assertEqual(get_balance(self.leo), -15)

    def test_reject_stores_reason_and_moves_no_coins(self):
        claim, request_ = self.claim(), self.prize_request()
        self.assertTrue(services.reject_claim(claim, self.parent, 'La cama sigue deshecha'))
        self.assertTrue(services.reject_request(request_, self.parent, 'Hoy no, mañana'))
        claim.refresh_from_db()
        self.assertEqual((claim.status, claim.reason), (ChoreClaim.REJECTED, 'La cama sigue deshecha'))
        self.assertFalse(FercoinTransaction.objects.exists())
        self.assertEqual(get_available_balance(self.leo), 0)

    def test_approval_works_for_deactivated_items_and_may_go_negative(self):
        claim, request_ = self.claim(), self.prize_request()
        Chore.objects.update(is_active=False)
        Prize.objects.update(is_active=False)
        self.assertTrue(services.approve_request(request_, self.parent))
        self.assertEqual(get_balance(self.leo), -20)
        self.assertTrue(services.approve_claim(claim, self.parent))
        self.assertEqual(get_balance(self.leo), -15)

    def test_kid_cannot_cancel_someone_elses_request(self):
        request_ = self.prize_request()
        self.assertFalse(services.cancel_request(request_, make_kid('ana')))
        self.assertTrue(services.cancel_request(request_, self.leo))
        request_.refresh_from_db()
        self.assertEqual(request_.status, PrizeRequest.CANCELLED)


class PrizeCatalogTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_superuser('mama', password='strong-pass-123')
        self.client.force_login(self.parent)

    def test_parent_creates_and_edits_prize(self):
        response = self.client.post(reverse('fercoins:prize_create'), {
            'name': 'Helado', 'cost': 20, 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('fercoins:prizes'))
        prize = Prize.objects.get()
        self.assertTrue(prize.is_active)
        self.client.post(reverse('fercoins:prize_edit', args=[prize.pk]), {
            'name': 'Helado grande', 'cost': 25, 'is_active': 'on',
        })
        prize.refresh_from_db()
        self.assertEqual((prize.name, prize.cost), ('Helado grande', 25))
        self.assertContains(self.client.get(reverse('fercoins:prizes')), 'Helado grande')

    def test_cost_must_be_at_least_one(self):
        for cost in (0, -5):
            response = self.client.post(reverse('fercoins:prize_create'), {
                'name': 'Gratis', 'cost': cost, 'is_active': 'on',
            })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertFalse(Prize.objects.exists())

    def test_toggle_is_post_only(self):
        prize = Prize.objects.create(name='Helado', cost=20)
        url = reverse('fercoins:prize_toggle', args=[prize.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        prize.refresh_from_db()
        self.assertFalse(prize.is_active)

    def test_kid_cannot_manage_prizes(self):
        prize = Prize.objects.create(name='Helado', cost=20)
        self.client.force_login(make_kid())
        for url in (
            reverse('fercoins:prizes'),
            reverse('fercoins:prize_create'),
            reverse('fercoins:prize_edit', args=[prize.pk]),
        ):
            self.assertNotEqual(self.client.get(url).status_code, 200)
        self.client.post(reverse('fercoins:prize_toggle', args=[prize.pk]))
        prize.refresh_from_db()
        self.assertTrue(prize.is_active)


class KidActionTests(TestCase):
    def setUp(self):
        self.leo = make_kid('leo')
        self.client.force_login(self.leo)
        self.bed = Chore.objects.create(name='Hacer la cama', fercoins=5)
        self.fight = Chore.objects.create(name='Pelear', fercoins=-5)
        self.water = Chore.objects.create(name='Regar', fercoins=2, is_active=False)
        self.ice = Prize.objects.create(name='Helado', cost=20)

    def give(self, kid, amount):
        FercoinTransaction.objects.create(recipient=kid, amount=amount)

    def claim(self, chore_pk):
        return self.client.post(reverse('fercoins:chore_claim', args=[chore_pk]))

    def request_prize(self, prize_pk):
        return self.client.post(reverse('fercoins:prize_request', args=[prize_pk]))

    def test_only_active_earning_chores_listed(self):
        response = self.client.get(reverse('fercoins:dashboard'))
        self.assertEqual([c.name for c in response.context['chores']], ['Hacer la cama'])
        self.assertNotContains(response, 'Pelear')
        self.assertNotContains(response, 'Regar')

    def test_claim_creates_pending_claim_without_moving_coins(self):
        self.give(self.leo, 10)
        self.assertRedirects(self.claim(self.bed.pk), reverse('fercoins:dashboard'))
        claim = ChoreClaim.objects.get()
        self.assertEqual((claim.kid, claim.amount, claim.status), (self.leo, 5, ChoreClaim.PENDING))
        self.assertEqual(get_balance(self.leo), 10)
        self.assertContains(self.client.get(reverse('fercoins:dashboard')), 'Pendiente')

    def test_forged_claims_create_nothing(self):
        for pk in (self.fight.pk, self.water.pk, 9999):
            self.claim(pk)
        self.assertFalse(ChoreClaim.objects.exists())

    def test_duplicate_pending_claim_refused(self):
        self.claim(self.bed.pk)
        response = self.claim(self.bed.pk)
        self.assertEqual(ChoreClaim.objects.count(), 1)
        self.assertContains(self.client.get(response.url), 'ya está pendiente')

    def test_request_reserves_coins_and_cannot_exceed_available(self):
        self.give(self.leo, 30)
        self.request_prize(self.ice.pk)
        self.assertEqual(get_balance(self.leo), 30)
        self.assertEqual(get_available_balance(self.leo), 10)
        self.request_prize(self.ice.pk)
        self.assertEqual(PrizeRequest.objects.count(), 1)
        response = self.client.get(reverse('fercoins:dashboard'))
        self.assertEqual(response.context['available'], 10)
        self.assertContains(response, 'Te faltan 10')

    def test_forged_request_for_inactive_prize_creates_nothing(self):
        self.give(self.leo, 100)
        self.ice.is_active = False
        self.ice.save()
        self.request_prize(self.ice.pk)
        self.assertFalse(PrizeRequest.objects.exists())

    def test_cancel_releases_coins_and_only_for_own_requests(self):
        self.give(self.leo, 42)
        self.request_prize(self.ice.pk)
        ana = make_kid('ana')
        anas = PrizeRequest.objects.create(kid=ana, prize=self.ice, amount=20)

        response = self.client.post(reverse('fercoins:request_cancel', args=[anas.pk]))
        self.assertEqual(response.status_code, 404)
        anas.refresh_from_db()
        self.assertEqual(anas.status, PrizeRequest.PENDING)

        own = PrizeRequest.objects.get(kid=self.leo)
        self.client.post(reverse('fercoins:request_cancel', args=[own.pk]))
        own.refresh_from_db()
        self.assertEqual(own.status, PrizeRequest.CANCELLED)
        self.assertEqual(get_available_balance(self.leo), 42)

    def test_dashboard_shows_only_own_claims_and_requests(self):
        ana = make_kid('ana')
        ChoreClaim.objects.create(kid=ana, chore=self.bed, amount=5)
        PrizeRequest.objects.create(kid=ana, prize=self.ice, amount=20)
        ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5, status=ChoreClaim.REJECTED,
                                  reason='La cama sigue deshecha')
        response = self.client.get(reverse('fercoins:dashboard'))
        self.assertEqual([c.kid for c in response.context['claims']], [self.leo])
        self.assertEqual(list(response.context['prize_requests']), [])
        self.assertContains(response, 'La cama sigue deshecha')

    def test_kid_actions_are_post_only(self):
        response = self.client.get(reverse('fercoins:chore_claim', args=[self.bed.pk]))
        self.assertEqual(response.status_code, 405)

    def test_non_kid_refused_and_anonymous_redirected(self):
        stranger = User.objects.create_user('stranger', email='s@example.com')
        self.client.force_login(stranger)
        self.assertEqual(self.claim(self.bed.pk).status_code, 403)
        self.assertEqual(self.request_prize(self.ice.pk).status_code, 403)
        self.assertNotContains(self.client.get(reverse('fercoins:dashboard')), '¡Lo hice!')

        self.client.logout()
        response = self.claim(self.bed.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('account_login'), response.url)
        self.request_prize(self.ice.pk)
        self.assertFalse(ChoreClaim.objects.exists())
        self.assertFalse(PrizeRequest.objects.exists())


class ReviewPageTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_superuser('mama', password='strong-pass-123')
        self.client.force_login(self.parent)
        self.leo = make_kid('leo')
        self.ana = make_kid('ana')
        self.bed = Chore.objects.create(name='Hacer la cama', fercoins=5)
        self.table = Chore.objects.create(name='Poner la mesa', fercoins=3)
        self.ice = Prize.objects.create(name='Helado', cost=20)

    def action_url(self, kind, item, action):
        return reverse('fercoins:review_action', args=[kind, item.pk, action])

    def test_lists_pending_items_oldest_first(self):
        request_ = PrizeRequest.objects.create(kid=self.ana, prize=self.ice, amount=20)
        claim = ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        ChoreClaim.objects.create(kid=self.leo, chore=self.table, amount=3, status=ChoreClaim.APPROVED)
        response = self.client.get(reverse('fercoins:review'))
        self.assertEqual([item for _, item in response.context['items']], [request_, claim])
        self.assertContains(response, self.action_url('claim', claim, 'approve'))
        self.assertContains(response, self.action_url('request', request_, 'reject'))

    def test_empty_review_page(self):
        self.assertContains(self.client.get(reverse('fercoins:review')), 'No hay nada que revisar')

    def test_kid_denied(self):
        self.client.force_login(self.leo)
        self.assertNotEqual(self.client.get(reverse('fercoins:review')).status_code, 200)
        claim = ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        self.client.post(self.action_url('claim', claim, 'approve'))
        self.assertFalse(FercoinTransaction.objects.exists())

    def test_actions_are_post_only(self):
        claim = ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        for action in ('approve', 'reject'):
            self.assertEqual(self.client.get(self.action_url('claim', claim, action)).status_code, 405)
        claim.refresh_from_db()
        self.assertTrue(claim.is_pending)

    def test_approve_and_reject_through_views(self):
        FercoinTransaction.objects.create(recipient=self.leo, amount=42)
        claim = ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        request_ = PrizeRequest.objects.create(kid=self.leo, prize=self.ice, amount=20)
        rejected = ChoreClaim.objects.create(kid=self.leo, chore=self.table, amount=3)

        self.client.post(self.action_url('claim', claim, 'approve'))
        self.client.post(self.action_url('request', request_, 'approve'))
        response = self.client.post(self.action_url('request', request_, 'approve'), follow=True)
        self.assertContains(response, 'Ya estaba revisada')
        self.client.post(self.action_url('claim', rejected, 'reject'), {'reason': 'Faltan platos'})

        self.assertEqual(get_balance(self.leo), 27)
        rejected.refresh_from_db()
        self.assertEqual((rejected.status, rejected.reason), (ChoreClaim.REJECTED, 'Faltan platos'))

    def test_unknown_kind_or_action_is_404(self):
        claim = ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        self.assertEqual(self.client.post(self.action_url('chore', claim, 'approve')).status_code, 404)
        self.assertEqual(self.client.post(self.action_url('claim', claim, 'delete')).status_code, 404)

    def test_manage_page_pending_count(self):
        manage = reverse('fercoins:manage')
        self.assertNotContains(self.client.get(manage), 'Pendientes (')
        ChoreClaim.objects.create(kid=self.leo, chore=self.bed, amount=5)
        ChoreClaim.objects.create(kid=self.ana, chore=self.bed, amount=5)
        PrizeRequest.objects.create(kid=self.leo, prize=self.ice, amount=20)
        response = self.client.get(manage)
        self.assertContains(response, 'Pendientes (3)')
        self.assertContains(response, reverse('fercoins:review'))
