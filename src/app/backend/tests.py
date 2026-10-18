import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from dotenv import load_dotenv

from core.models import KidProfile

User = get_user_model()

APP_DIR = Path(settings.BASE_DIR)
GOOD_KEY = secrets.token_urlsafe(50)
CONFIG_VARS = [
    'DEBUG', 'SECRET_KEY', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS',
    'SECURE_HSTS_SECONDS', 'DATA_DIR',
]

SHOW_SETTINGS = """
import json, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
from django.conf import settings
print(json.dumps({
    'DEBUG': settings.DEBUG,
    'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,
    'CSRF_TRUSTED_ORIGINS': settings.CSRF_TRUSTED_ORIGINS,
    'SECURE_HSTS_SECONDS': settings.SECURE_HSTS_SECONDS,
    'DB_NAME': str(settings.DATABASES['default']['NAME']),
}))
"""


def run_django(code_or_args, **env):
    """Run in a fresh interpreter; every config var is '' (unset) unless given."""
    full_env = {**os.environ, **{name: '' for name in CONFIG_VARS}, **env}
    args = code_or_args if isinstance(code_or_args, list) else ['-c', code_or_args]
    return subprocess.run(
        [sys.executable, *args], cwd=APP_DIR, env=full_env,
        capture_output=True, text=True, timeout=60,
    )


def load_settings(**env):
    result = run_django(SHOW_SETTINGS, **env)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


PROD = {'SECRET_KEY': GOOD_KEY, 'ALLOWED_HOSTS': 'zeneke.example.com'}


class ModeAndValidationTests(SimpleTestCase):
    def test_production_is_default(self):
        self.assertFalse(load_settings(**PROD)['DEBUG'])
        self.assertFalse(load_settings(DEBUG='yes', **PROD)['DEBUG'])

    def test_debug_true_enables_development(self):
        for value in ['true', 'True']:
            with self.subTest(value=value):
                self.assertTrue(load_settings(DEBUG=value)['DEBUG'])

    def test_production_rejects_bad_keys(self):
        for key in ['', 'django-insecure-' + GOOD_KEY, 'short-key', 'a' * 60]:
            with self.subTest(key=key[:20]):
                result = run_django(SHOW_SETTINGS, SECRET_KEY=key, ALLOWED_HOSTS='x.example.com')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('SECRET_KEY', result.stderr)

    def test_development_needs_no_key(self):
        self.assertTrue(load_settings(DEBUG='true')['DEBUG'])

    def test_production_requires_hosts(self):
        result = run_django(SHOW_SETTINGS, SECRET_KEY=GOOD_KEY)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ALLOWED_HOSTS', result.stderr)

    def test_host_list_parsing(self):
        values = load_settings(SECRET_KEY=GOOD_KEY, ALLOWED_HOSTS='a.example.com, b.example.com,')
        self.assertEqual(values['ALLOWED_HOSTS'], ['a.example.com', 'b.example.com'])

    def test_environment_wins_over_env_file(self):
        with tempfile.NamedTemporaryFile('w', suffix='.env', delete=False) as f:
            f.write('DEBUG=true\n')
        self.addCleanup(os.unlink, f.name)
        with mock.patch.dict(os.environ, {'DEBUG': 'false'}):
            load_dotenv(f.name, override=False)
            self.assertEqual(os.environ['DEBUG'], 'false')


class SecurityValueTests(SimpleTestCase):
    def test_trusted_origins_derived_from_hosts(self):
        values = load_settings(SECRET_KEY=GOOD_KEY, ALLOWED_HOSTS='zeneke.example.com,.example.org,*')
        self.assertEqual(
            values['CSRF_TRUSTED_ORIGINS'],
            ['https://zeneke.example.com', 'https://*.example.org'],
        )

    def test_trusted_origins_override(self):
        values = load_settings(CSRF_TRUSTED_ORIGINS='https://other.example.com', **PROD)
        self.assertEqual(values['CSRF_TRUSTED_ORIGINS'], ['https://other.example.com'])

    def test_hsts_default_and_configured(self):
        self.assertEqual(load_settings(**PROD)['SECURE_HSTS_SECONDS'], 3600)
        self.assertEqual(
            load_settings(SECURE_HSTS_SECONDS='31536000', **PROD)['SECURE_HSTS_SECONDS'], 31536000
        )


class DataDirTests(SimpleTestCase):
    def test_default_location_unchanged(self):
        self.assertEqual(load_settings(DEBUG='true')['DB_NAME'], str(APP_DIR / 'db.sqlite3'))

    def test_data_dir_created_and_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / 'nested'
            result = run_django(
                ['manage.py', 'migrate', '--noinput'], DEBUG='true', DATA_DIR=str(data_dir)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((data_dir / 'db.sqlite3').exists())


PROD_SECURITY = dict(
    DEBUG=False,
    ALLOWED_HOSTS=['zeneke.example.com'],
    CSRF_TRUSTED_ORIGINS=['https://zeneke.example.com'],
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    SECURE_SSL_REDIRECT=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SECURE_HSTS_SECONDS=3600,
    ACCOUNT_DEFAULT_HTTP_PROTOCOL='https',
)
HOST = {'HTTP_HOST': 'zeneke.example.com'}
HTTPS = {**HOST, 'HTTP_X_FORWARDED_PROTO': 'https'}


@override_settings(**PROD_SECURITY)
class ProductionRequestTests(TestCase):
    def setUp(self):
        user = User.objects.create_user('leo')
        profile = KidProfile(user=user)
        profile.set_pin('1234')
        profile.save()

    def test_plain_http_redirects_to_https(self):
        response = self.client.get('/fercoins/', **HOST)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://zeneke.example.com/fercoins/')

    def test_hsts_on_https(self):
        response = self.client.get('/', **HTTPS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Strict-Transport-Security'], 'max-age=3600')

    def test_session_cookie_is_secure(self):
        response = self.client.post(
            reverse('core:kid_login'), {'username': 'leo', 'code': '1234'}, **HTTPS
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.cookies[settings.SESSION_COOKIE_NAME]['secure'])

    def test_form_post_from_allowed_host_passes_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('account_login'), **HTTPS)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        response = client.post(
            reverse('core:kid_login'),
            {'username': 'leo', 'code': '1234', 'csrfmiddlewaretoken': token},
            HTTP_ORIGIN='https://zeneke.example.com', **HTTPS,
        )
        self.assertNotEqual(response.status_code, 403)
        self.assertEqual(response.status_code, 302)

    def test_google_callback_uses_https(self):
        response = self.client.post('/accounts/google/login/', **HTTPS)
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            'redirect_uri=https%3A%2F%2Fzeneke.example.com%2Faccounts%2Fgoogle%2Flogin%2Fcallback%2F',
            response['Location'],
        )


class DevelopmentRequestTests(TestCase):
    def test_localhost_sign_in_without_secure_cookie(self):
        user = User.objects.create_user('leo')
        profile = KidProfile(user=user)
        profile.set_pin('1234')
        profile.save()
        response = self.client.post(
            reverse('core:kid_login'), {'username': 'leo', 'code': '1234'},
            HTTP_HOST='localhost:8000',
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(response.cookies[settings.SESSION_COOKIE_NAME]['secure'])
