from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password
from django.db.models import F
from django.utils import timezone

from .models import LOCK_MINUTES, MAX_ATTEMPTS, PIN_RE, KidProfile

User = get_user_model()

PIN = 'pin'
SETUP_CODE = 'setup_code'


def _find_kid(username):
    profiles = list(
        KidProfile.objects.select_related('user').filter(
            user__username__iexact=username, user__is_active=True
        )[:2]
    )
    return profiles[0] if len(profiles) == 1 else None


def _record_failure(profile):
    KidProfile.objects.filter(pk=profile.pk).update(failed_attempts=F('failed_attempts') + 1)
    profile.refresh_from_db(fields=['failed_attempts'])
    if profile.failed_attempts >= MAX_ATTEMPTS:
        profile.failed_attempts = 0
        profile.locked_until = timezone.now() + timedelta(minutes=LOCK_MINUTES)
        profile.save(update_fields=['failed_attempts', 'locked_until'])


def verify_kid_credential(username, code, kind=PIN):
    """Check a kid's PIN or setup code, applying the lockout.

    Returns the KidProfile on success, None on any failure.
    """
    profile = _find_kid(username or '')
    if profile is None:
        # Spend roughly the same time as a real check.
        make_password(code or '')
        return None
    if profile.is_locked():
        return None

    if kind == PIN:
        ok = profile.check_pin(code)
    else:
        ok = profile.check_setup_code(code)

    if not ok:
        _record_failure(profile)
        return None
    if profile.failed_attempts:
        profile.failed_attempts = 0
        profile.save(update_fields=['failed_attempts'])
    return profile


class KidPinBackend(BaseBackend):
    """Authenticates kid accounts with username + 4-digit PIN."""

    def authenticate(self, request, username=None, pin=None, **kwargs):
        if username is None or pin is None or not PIN_RE.match(pin):
            return None
        profile = verify_kid_credential(username, pin, PIN)
        return profile.user if profile else None

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id, is_active=True).first()
