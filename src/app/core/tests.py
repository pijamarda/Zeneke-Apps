import time
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import OperationalError, connection
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import MAX_ATTEMPTS, KidProfile, validate_pin
from .views import LOGIN_FAILED, SETUP_SESSION_KEY

User = get_user_model()


def make_kid(username='leo', pin='1234'):
    user = User.objects.create_user(username=username)
    profile = KidProfile(user=user)
    if pin:
        profile.set_pin(pin)
    profile.save()
    return profile


class KidProfileModelTests(TestCase):
    def test_pin_is_stored_hashed(self):
        profile = make_kid(pin='0427')
        self.assertTrue(profile.pin_hash)
        self.assertNotIn('0427', profile.pin_hash)
        self.assertTrue(profile.check_pin('0427'))
        self.assertFalse(profile.check_pin('0428'))

    def test_pin_format(self):
        validate_pin('0427')
        for bad in ['123', '12345', '12a4', '', ' 123']:
            with self.subTest(pin=bad), self.assertRaises(ValidationError):
                validate_pin(bad)

    def test_setup_code_is_hashed_and_replaced(self):
        profile = make_kid(pin=None)
        first = profile.issue_setup_code()
        self.assertRegex(first, r'^\d{6}$')
        self.assertNotIn(first, profile.setup_code_hash)
        self.assertTrue(profile.check_setup_code(first))
        second = profile.issue_setup_code()
        self.assertTrue(profile.check_setup_code(second))
        if first != second:
            self.assertFalse(profile.check_setup_code(first))

    def test_expired_setup_code_rejected(self):
        profile = make_kid(pin=None)
        code = profile.issue_setup_code()
        profile.setup_code_expires_at = timezone.now() - timedelta(seconds=1)
        self.assertFalse(profile.check_setup_code(code))

    def test_states(self):
        profile = make_kid(pin=None)
        self.assertEqual(profile.state, KidProfile.STATE_AWAITING_SETUP)
        profile.set_pin('1234')
        self.assertEqual(profile.state, KidProfile.STATE_ACTIVE)
        profile.locked_until = timezone.now() + timedelta(minutes=5)
        self.assertEqual(profile.state, KidProfile.STATE_LOCKED)


class KidPinBackendTests(TestCase):
    def setUp(self):
        self.profile = make_kid('leo', '1234')

    def auth(self, username='leo', pin='1234'):
        return authenticate(None, username=username, pin=pin)

    def test_correct_pin(self):
        self.assertEqual(self.auth(), self.profile.user)

    def test_username_case_insensitive(self):
        self.assertEqual(self.auth(username='Leo'), self.profile.user)

    def test_non_kid_accounts_rejected(self):
        parent = User.objects.create_superuser('mama', password='strong-pass-123')
        other = User.objects.create_user('stranger', password='1234')
        self.assertIsNone(self.auth(username=parent.username))
        self.assertIsNone(self.auth(username=other.username))

    def test_lockout_after_max_failures(self):
        for _ in range(MAX_ATTEMPTS):
            self.assertIsNone(self.auth(pin='0000'))
        self.assertIsNone(self.auth())
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_locked())

    def test_lock_expires(self):
        for _ in range(MAX_ATTEMPTS):
            self.auth(pin='0000')
        KidProfile.objects.filter(pk=self.profile.pk).update(
            locked_until=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.auth(), self.profile.user)

    def test_success_resets_count(self):
        for _ in range(MAX_ATTEMPTS - 1):
            self.auth(pin='0000')
        self.assertEqual(self.auth(), self.profile.user)
        for _ in range(MAX_ATTEMPTS - 1):
            self.auth(pin='0000')
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_locked())
        self.assertEqual(self.auth(), self.profile.user)

    def test_password_paths_cannot_use_pin(self):
        self.assertIsNone(authenticate(None, username='leo', password='1234'))
        response = self.client.post(
            '/admin/login/', {'username': 'leo', 'password': '1234', 'next': '/admin/'}
        )
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.failed_attempts, 0)


class KidLoginViewTests(TestCase):
    def setUp(self):
        self.profile = make_kid('leo', '1234')
        self.url = reverse('core:kid_login')

    def post(self, username='leo', code='1234', **extra):
        return self.client.post(self.url, {'username': username, 'code': code, **extra})

    def assertFailed(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, LOGIN_FAILED)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_page_has_both_options_and_no_usernames(self):
        response = self.client.get(reverse('account_login'))
        self.assertContains(response, 'Continue with Google')
        self.assertContains(response, 'Continue with GitHub')
        self.assertContains(response, self.url)
        self.assertNotContains(response, 'leo')

    def test_correct_pin_signs_in(self):
        response = self.post()
        self.assertRedirects(response, reverse('fercoins:dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.profile.user.pk)

    def test_safe_next_is_honoured(self):
        response = self.post(next='/fercoins/?x=1')
        self.assertRedirects(response, '/fercoins/?x=1', fetch_redirect_response=False)

    def test_offsite_next_is_ignored(self):
        response = self.post(next='https://evil.example/')
        self.assertRedirects(response, reverse('fercoins:dashboard'))

    def test_failures_look_identical(self):
        User.objects.create_superuser('mama', password='strong-pass-123')
        responses = [
            self.post(username='nobody'),
            self.post(code='9999'),
            self.post(username='mama'),
            self.post(code='12'),
        ]
        for _ in range(MAX_ATTEMPTS):
            self.post(code='9999')
        responses.append(self.post())  # locked, correct PIN
        for response in responses:
            self.assertFailed(response)

    def test_get_redirects_to_login(self):
        self.assertRedirects(self.client.get(self.url), reverse('account_login'))

    def test_session_lasts_two_weeks(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 14 * 24 * 60 * 60)
        self.assertFalse(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        response = self.post()
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(int(cookie['max-age']), settings.SESSION_COOKIE_AGE)


class KidSetupPinTests(TestCase):
    def setUp(self):
        self.profile = make_kid('mia', pin=None)
        self.code = self.profile.issue_setup_code()
        self.profile.save()

    def start_setup(self, code=None):
        return self.client.post(
            reverse('core:kid_login'), {'username': 'mia', 'code': code or self.code}
        )

    def test_setup_code_then_choose_pin(self):
        response = self.start_setup()
        self.assertRedirects(response, reverse('core:kid_setup_pin'))
        self.assertNotIn('_auth_user_id', self.client.session)

        response = self.client.post(
            reverse('core:kid_setup_pin'), {'pin': '0427', 'pin_confirm': '0427'}
        )
        self.assertRedirects(response, reverse('fercoins:dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.profile.user.pk)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.check_pin('0427'))
        self.assertFalse(self.profile.setup_code_hash)

    def test_username_alone_is_not_enough(self):
        wrong_code = '000000' if self.code != '000000' else '111111'
        for code in ['', wrong_code, '1234']:
            response = self.client.post(reverse('core:kid_login'), {'username': 'mia', 'code': code})
            self.assertContains(response, LOGIN_FAILED)
        self.assertNotIn(SETUP_SESSION_KEY, self.client.session)

    def test_mismatched_confirmation(self):
        self.start_setup()
        response = self.client.post(
            reverse('core:kid_setup_pin'), {'pin': '0427', 'pin_confirm': '0428'}
        )
        self.assertContains(response, 'no coinciden')
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.pin_hash)

    def test_invalid_pin_rejected(self):
        self.start_setup()
        response = self.client.post(
            reverse('core:kid_setup_pin'), {'pin': '12a4', 'pin_confirm': '12a4'}
        )
        self.assertContains(response, '4 dígitos')

    def test_expired_setup_code(self):
        KidProfile.objects.filter(pk=self.profile.pk).update(
            setup_code_expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertContains(self.start_setup(), LOGIN_FAILED)

    def test_setup_code_single_use(self):
        self.start_setup()
        self.client.post(reverse('core:kid_setup_pin'), {'pin': '0427', 'pin_confirm': '0427'})
        other = Client()
        response = other.post(reverse('core:kid_login'), {'username': 'mia', 'code': self.code})
        self.assertContains(response, LOGIN_FAILED)

    def test_cannot_skip_choosing_pin(self):
        self.start_setup()
        response = self.client.get(reverse('fercoins:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('account_login'), response['Location'])

    def test_pending_setup_expires(self):
        self.start_setup()
        session = self.client.session
        session[SETUP_SESSION_KEY]['at'] = time.time() - 11 * 60
        session.save()
        response = self.client.get(reverse('core:kid_setup_pin'))
        self.assertRedirects(response, reverse('account_login'))

    def test_setup_page_requires_pending_entry(self):
        response = self.client.get(reverse('core:kid_setup_pin'))
        self.assertRedirects(response, reverse('account_login'))


class KidChangePinTests(TestCase):
    def setUp(self):
        self.profile = make_kid('leo', '1234')
        self.client.post(reverse('core:kid_login'), {'username': 'leo', 'code': '1234'})
        self.url = reverse('core:kid_change_pin')

    def change(self, current='1234', new='5678', confirm=None):
        return self.client.post(self.url, {
            'current_pin': current, 'pin': new, 'pin_confirm': confirm or new,
        })

    def test_successful_change(self):
        response = self.change()
        self.assertRedirects(response, reverse('fercoins:dashboard'))
        self.assertIn('_auth_user_id', self.client.session)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.check_pin('5678'))
        self.assertFalse(self.profile.check_pin('1234'))

    def test_wrong_current_pin_counts_as_failure(self):
        response = self.change(current='0000')
        self.assertContains(response, 'PIN actual incorrecto')
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.check_pin('1234'))
        self.assertEqual(self.profile.failed_attempts, 1)

    def test_non_kid_forbidden(self):
        parent = User.objects.create_superuser('mama', password='strong-pass-123')
        client = Client()
        client.force_login(parent)
        self.assertEqual(client.get(self.url).status_code, 403)

    def test_anonymous_redirected(self):
        response = Client().get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_navbar_link_only_for_kids(self):
        self.assertContains(self.client.get('/'), self.url)
        self.assertNotContains(Client().get('/'), self.url)


class FamilyManagementTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_superuser('mama', password='strong-pass-123')
        self.client.force_login(self.parent)

    def create_kid(self, username='leo'):
        response = self.client.post(reverse('core:family_create'), {'username': username})
        code = response.context['code'] if response.context and 'code' in response.context else None
        return response, code

    def test_access_denied_for_kids_and_anonymous(self):
        make_kid('mia', '1234')
        kid_client = Client()
        kid_client.post(reverse('core:kid_login'), {'username': 'mia', 'code': '1234'})
        for url in [reverse('core:family'), reverse('core:family_create')]:
            with self.subTest(url=url):
                response = kid_client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertNotContains(response, 'mia', status_code=302)
                anon = Client().get(url)
                self.assertIn(reverse('account_login'), anon['Location'])

    def test_create_kid_shows_code_once(self):
        response, code = self.create_kid()
        self.assertRegex(code, r'^\d{6}$')
        self.assertContains(response, code)
        self.assertIn('no-store', response['Cache-Control'])
        user = User.objects.get(username='leo')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(user.kid_profile.state, KidProfile.STATE_AWAITING_SETUP)

        listing = self.client.get(reverse('core:family'))
        self.assertContains(listing, 'leo')
        self.assertContains(listing, 'Pendiente de configurar')
        self.assertNotContains(listing, code)

    def test_duplicate_username_rejected(self):
        User.objects.create_user('Leo')
        response, _ = self.create_kid('leo')
        self.assertContains(response, 'ya existe')
        self.assertEqual(KidProfile.objects.count(), 0)

    def test_new_code_invalidates_old(self):
        _, first = self.create_kid()
        profile = KidProfile.objects.get(user__username='leo')
        response = self.client.post(reverse('core:family_reset_pin', args=[profile.pk]))
        second = response.context['code']
        profile.refresh_from_db()
        self.assertTrue(profile.check_setup_code(second))
        if first != second:
            self.assertFalse(profile.check_setup_code(first))

    def test_reset_pin_invalidates_pin_and_sessions(self):
        profile = make_kid('leo', '1234')
        tablet = Client()
        tablet.post(reverse('core:kid_login'), {'username': 'leo', 'code': '1234'})
        self.assertEqual(tablet.get(reverse('fercoins:dashboard')).status_code, 200)

        response = self.client.post(reverse('core:family_reset_pin', args=[profile.pk]))
        self.assertRegex(response.context['code'], r'^\d{6}$')

        dashboard = tablet.get(reverse('fercoins:dashboard'))
        self.assertEqual(dashboard.status_code, 302)
        profile.refresh_from_db()
        self.assertFalse(profile.check_pin('1234'))
        self.assertEqual(profile.state, KidProfile.STATE_AWAITING_SETUP)

        login = Client().post(reverse('core:kid_login'), {'username': 'leo', 'code': response.context['code']})
        self.assertRedirects(login, reverse('core:kid_setup_pin'))

    def test_reset_clears_lock(self):
        profile = make_kid('leo', '1234')
        for _ in range(MAX_ATTEMPTS):
            authenticate(None, username='leo', pin='0000')
        profile.refresh_from_db()
        self.assertTrue(profile.is_locked())

        response = self.client.post(reverse('core:family_reset_pin', args=[profile.pk]))
        profile.refresh_from_db()
        self.assertFalse(profile.is_locked())
        self.assertEqual(profile.failed_attempts, 0)

        login = Client().post(
            reverse('core:kid_login'), {'username': 'leo', 'code': response.context['code']}
        )
        self.assertRedirects(login, reverse('core:kid_setup_pin'))

    def test_unlock(self):
        profile = make_kid('leo', '1234')
        for _ in range(MAX_ATTEMPTS):
            authenticate(None, username='leo', pin='0000')
        listing = self.client.get(reverse('core:family'))
        self.assertContains(listing, 'Bloqueado')

        self.client.post(reverse('core:family_unlock', args=[profile.pk]))
        self.assertEqual(authenticate(None, username='leo', pin='1234'), profile.user)

    def test_actions_are_post_only(self):
        profile = make_kid('leo', '1234')
        for name in ['core:family_reset_pin', 'core:family_unlock']:
            self.assertEqual(self.client.get(reverse(name, args=[profile.pk])).status_code, 405)

    def test_navbar_link_for_parents(self):
        self.assertContains(self.client.get('/'), reverse('core:family'))


PROD_SECURITY = dict(
    DEBUG=False,
    ALLOWED_HOSTS=['zeneke.example.com'],
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    SECURE_SSL_REDIRECT=True,
)


class HealthCheckTests(SimpleTestCase):
    """SimpleTestCase forbids database queries, so these also prove /healthz needs none."""

    def assertHealthy(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
        self.assertEqual(response['Content-Type'], 'text/plain')

    def test_ok_in_development(self):
        self.assertHealthy(self.client.get('/healthz'))

    @override_settings(**PROD_SECURITY)
    def test_plain_http_in_production_not_redirected(self):
        self.assertHealthy(self.client.get('/healthz', HTTP_HOST='zeneke.example.com'))
        for path in ['/', '/healthz/extra']:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST='zeneke.example.com')
                self.assertEqual(response.status_code, 301)

    @override_settings(**PROD_SECURITY)
    def test_unknown_host(self):
        self.assertHealthy(self.client.get('/healthz', HTTP_HOST='127.0.0.1:8000'))

    def test_database_unavailable(self):
        with mock.patch.object(
            connection, 'ensure_connection', side_effect=OperationalError('db down')
        ):
            self.assertHealthy(self.client.get('/healthz'))
