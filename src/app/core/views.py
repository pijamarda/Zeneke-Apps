import time

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.cache import add_never_cache_headers
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .backends import PIN, SETUP_CODE, verify_kid_credential
from .forms import ChangePinForm, CreateKidForm, SetPinForm
from .models import PIN_RE, SETUP_CODE_RE, KidProfile

User = get_user_model()

superuser_required = user_passes_test(lambda u: u.is_superuser, login_url='account_login')

KID_BACKEND = 'core.backends.KidPinBackend'
LOGIN_FAILED = 'Usuario o PIN incorrectos.'
SETUP_SESSION_KEY = 'kid_setup'
SETUP_SESSION_SECONDS = 10 * 60


def home(request):
    return render(request, 'core/home.html')


# Kid sign-in

def _safe_next(request, next_url):
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


def _login_failed(request, username, next_url):
    return render(request, 'account/login.html', {
        'kid_error': LOGIN_FAILED,
        'kid_username': username,
        'kid_next': next_url,
    })


def kid_login(request):
    if request.method != 'POST':
        return redirect('account_login')

    username = request.POST.get('username', '').strip()
    code = request.POST.get('code', '').strip()
    next_url = request.POST.get('next', '')

    if PIN_RE.match(code):
        profile = verify_kid_credential(username, code, PIN)
        if profile:
            login(request, profile.user, backend=KID_BACKEND)
            return redirect(_safe_next(request, next_url) or 'fercoins:dashboard')
    elif SETUP_CODE_RE.match(code):
        profile = verify_kid_credential(username, code, SETUP_CODE)
        if profile:
            request.session[SETUP_SESSION_KEY] = {'user_id': profile.user_id, 'at': time.time()}
            return redirect('core:kid_setup_pin')

    return _login_failed(request, username, next_url)


def _pending_setup_profile(request):
    pending = request.session.get(SETUP_SESSION_KEY)
    if not pending or time.time() - pending.get('at', 0) > SETUP_SESSION_SECONDS:
        return None
    profile = KidProfile.objects.select_related('user').filter(
        user_id=pending.get('user_id'), user__is_active=True
    ).first()
    if profile is None or not profile.has_valid_setup_code() or profile.is_locked():
        return None
    return profile


def kid_setup_pin(request):
    profile = _pending_setup_profile(request)
    if profile is None:
        request.session.pop(SETUP_SESSION_KEY, None)
        return redirect('account_login')

    form = SetPinForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        profile.set_pin(form.cleaned_data['pin'])
        profile.unlock()
        profile.save()
        request.session.pop(SETUP_SESSION_KEY, None)
        login(request, profile.user, backend=KID_BACKEND)
        messages.success(request, '¡PIN guardado!')
        return redirect('fercoins:dashboard')

    return render(request, 'core/kid_setup_pin.html', {'form': form, 'kid': profile.user})


@login_required(login_url='account_login')
def kid_change_pin(request):
    if not hasattr(request.user, 'kid_profile'):
        return HttpResponseForbidden()

    form = ChangePinForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        profile = verify_kid_credential(
            request.user.username, form.cleaned_data['current_pin'], PIN
        )
        if profile is None:
            form.add_error('current_pin', 'PIN actual incorrecto.')
        else:
            profile.set_pin(form.cleaned_data['pin'])
            profile.save()
            messages.success(request, 'PIN cambiado.')
            return redirect('fercoins:dashboard')

    return render(request, 'core/kid_change_pin.html', {'form': form})


# Family management (parents)

def _show_setup_code(request, kid, code, created):
    response = render(request, 'core/family_code.html', {
        'kid': kid,
        'code': code,
        'created': created,
    })
    add_never_cache_headers(response)
    return response


@login_required(login_url='account_login')
@superuser_required
def family(request):
    kids = KidProfile.objects.select_related('user').all()
    return render(request, 'core/family.html', {'kids': kids})


@login_required(login_url='account_login')
@superuser_required
def family_create(request):
    form = CreateKidForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = User.objects.create_user(username=form.cleaned_data['username'])
            profile = KidProfile(user=user)
            code = profile.issue_setup_code()
            profile.save()
        return _show_setup_code(request, user, code, created=True)
    return render(request, 'core/family_form.html', {'form': form})


@require_POST
@login_required(login_url='account_login')
@superuser_required
def family_reset_pin(request, pk):
    profile = get_object_or_404(KidProfile.objects.select_related('user'), pk=pk)
    with transaction.atomic():
        profile.clear_pin()
        profile.unlock()
        code = profile.issue_setup_code()
        profile.save()
        # A new unusable password changes the session auth hash, ending every session.
        profile.user.set_unusable_password()
        profile.user.save(update_fields=['password'])
    return _show_setup_code(request, profile.user, code, created=False)


@require_POST
@login_required(login_url='account_login')
@superuser_required
def family_unlock(request, pk):
    profile = get_object_or_404(KidProfile.objects.select_related('user'), pk=pk)
    profile.unlock()
    profile.save(update_fields=['failed_attempts', 'locked_until'])
    messages.success(request, f'{profile.user.username} desbloqueado.')
    return redirect('core:family')
