import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Local convenience: src/.env (never in the image). Real env vars always win.
load_dotenv(BASE_DIR.parent / '.env', override=False)


def env_str(name, default=''):
    """An empty value counts as unset."""
    return os.environ.get(name) or default


def env_bool(name):
    return env_str(name).lower() == 'true'


def env_list(name):
    return [item.strip() for item in env_str(name).split(',') if item.strip()]


# Production unless DEBUG is explicitly "true".
DEBUG = env_bool('DEBUG')

DEV_SECRET_KEY = 'django-insecure-zv%mwt=0g3n(54_pe5&-^#-uj&_$b#qf%^)hy0wrhu=*xai@m^'
SECRET_KEY_MIN_LENGTH = 50
SECRET_KEY_MIN_UNIQUE_CHARACTERS = 5
SECRET_KEY_INSECURE_PREFIX = 'django-insecure-'

SECRET_KEY = env_str('SECRET_KEY', DEV_SECRET_KEY if DEBUG else '')
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')

if not DEBUG:
    if (
        len(SECRET_KEY) < SECRET_KEY_MIN_LENGTH
        or len(set(SECRET_KEY)) < SECRET_KEY_MIN_UNIQUE_CHARACTERS
        or SECRET_KEY.startswith(SECRET_KEY_INSECURE_PREFIX)
    ):
        raise ImproperlyConfigured(
            'SECRET_KEY is missing or insecure (production mode needs 50+ random characters). '
            'For local development copy src/.env.example to src/.env (it sets DEBUG=true).'
        )
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            'ALLOWED_HOSTS is empty (production mode needs the site domain, e.g. zeneke.example.com). '
            'For local development copy src/.env.example to src/.env (it sets DEBUG=true).'
        )


def derive_csrf_trusted_origins(hosts):
    origins = []
    for host in hosts:
        if host == '*':
            continue
        origins.append(f'https://*{host}' if host.startswith('.') else f'https://{host}')
    return origins


CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS') or (
    [] if DEBUG else derive_csrf_trusted_origins(ALLOWED_HOSTS)
)

if not DEBUG:
    # The host (Caddy, Fly proxy, ...) terminates HTTPS and forwards the scheme.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env_str('SECURE_HSTS_SECONDS', '3600'))
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
    # HSTS starts short; subdomains and preload stay off on purpose for now.
    SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']

DATA_DIR = Path(env_str('DATA_DIR', str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    # apps
    'core',
    'bingo',
    'fercoins',
]

MIDDLEWARE = [
    'core.middleware.HealthCheckMiddleware',  # first: skips HTTPS redirect and host check
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
    }
}

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'core.backends.KidPinBackend',
]

SITE_ID = 1

# allauth
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_ONLY = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'github': {
        'APP': {
            'client_id': os.environ.get('GITHUB_CLIENT_ID', ''),
            'secret': os.environ.get('GITHUB_CLIENT_SECRET', ''),
        },
        'SCOPE': ['user:email'],
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    # Manifest storage needs collectstatic (done at image build); dev and tests skip it.
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'
        if DEBUG
        else 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Bingo: public rooms
BINGO_ROOM_IDLE_HOURS = 12
BINGO_MAX_ROOMS = 50
BINGO_MAX_PLAYERS = 30

LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'core:home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
