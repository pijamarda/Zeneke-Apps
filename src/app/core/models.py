import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

PIN_RE = re.compile(r'^\d{4}$')
SETUP_CODE_RE = re.compile(r'^\d{6}$')

MAX_ATTEMPTS = 5
LOCK_MINUTES = 15
SETUP_CODE_HOURS = 24


def validate_pin(pin):
    if not isinstance(pin, str) or not PIN_RE.match(pin):
        raise ValidationError('El PIN debe tener exactamente 4 dígitos.')


class KidProfile(models.Model):
    """Marks a user as a kid and holds their PIN credentials."""

    STATE_AWAITING_SETUP = 'awaiting_setup'
    STATE_ACTIVE = 'active'
    STATE_LOCKED = 'locked'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kid_profile'
    )
    pin_hash = models.CharField(max_length=256, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    setup_code_hash = models.CharField(max_length=256, blank=True)
    setup_code_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return self.user.username

    # PIN

    def set_pin(self, pin):
        validate_pin(pin)
        self.pin_hash = make_password(pin)
        self.setup_code_hash = ''
        self.setup_code_expires_at = None

    def check_pin(self, pin):
        return bool(self.pin_hash) and check_password(pin, self.pin_hash)

    def clear_pin(self):
        self.pin_hash = ''

    # Setup code

    def issue_setup_code(self):
        """Return a new plain 6-digit code; only its hash is kept."""
        code = f'{secrets.randbelow(10**6):06d}'
        self.setup_code_hash = make_password(code)
        self.setup_code_expires_at = timezone.now() + timedelta(hours=SETUP_CODE_HOURS)
        return code

    def has_valid_setup_code(self):
        return bool(self.setup_code_hash) and (
            self.setup_code_expires_at is not None
            and self.setup_code_expires_at > timezone.now()
        )

    def check_setup_code(self, code):
        return self.has_valid_setup_code() and check_password(code, self.setup_code_hash)

    # Lockout

    def is_locked(self):
        return self.locked_until is not None and self.locked_until > timezone.now()

    def unlock(self):
        self.failed_attempts = 0
        self.locked_until = None

    @property
    def state(self):
        if self.is_locked():
            return self.STATE_LOCKED
        if not self.pin_hash:
            return self.STATE_AWAITING_SETUP
        return self.STATE_ACTIVE

    def get_state_display(self):
        return {
            self.STATE_AWAITING_SETUP: 'Pendiente de configurar',
            self.STATE_ACTIVE: 'Activo',
            self.STATE_LOCKED: 'Bloqueado',
        }[self.state]
