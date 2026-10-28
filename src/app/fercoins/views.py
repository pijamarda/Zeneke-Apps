from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, transaction
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import ChoreForm, GiveFercoinsForm, PrizeForm
from .models import (
    Chore, ChoreClaim, FercoinTransaction, Prize, PrizeRequest, get_available_balance, get_balance,
)

User = get_user_model()

superuser_required = user_passes_test(lambda u: u.is_superuser, login_url='account_login')


def kid_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'kid_profile'):
            return HttpResponseForbidden()
        return view(request, *args, **kwargs)
    return wrapper


@login_required(login_url='account_login')
def dashboard(request):
    if request.user.is_superuser:
        return redirect('fercoins:manage')

    balance = get_balance(request.user)
    transactions = request.user.fercoins_received.select_related('chore', 'given_by').all()
    context = {'balance': balance, 'transactions': transactions}

    if hasattr(request.user, 'kid_profile'):
        available = get_available_balance(request.user)
        pending_chore_ids = set(
            request.user.chore_claims.filter(status=ChoreClaim.PENDING).values_list('chore_id', flat=True)
        )
        chores = list(Chore.objects.filter(is_active=True, fercoins__gt=0))
        for chore in chores:
            chore.is_pending = chore.pk in pending_chore_ids
        prizes = list(Prize.objects.filter(is_active=True))
        for prize in prizes:
            prize.missing = max(prize.cost - available, 0)
        context.update({
            'is_kid': True,
            'available': available,
            'chores': chores,
            'prizes': prizes,
            'claims': request.user.chore_claims.select_related('chore')[:10],
            'prize_requests': request.user.prize_requests.select_related('prize')[:10],
        })

    return render(request, 'fercoins/dashboard.html', context)


@login_required(login_url='account_login')
@superuser_required
def manage(request):
    members = (
        User.objects.filter(kid_profile__isnull=False)
        .annotate(balance=Coalesce(Sum('fercoins_received__amount'), Value(0)))
        .order_by('username')
    )
    pending_count = (
        ChoreClaim.objects.filter(status=ChoreClaim.PENDING).count()
        + PrizeRequest.objects.filter(status=PrizeRequest.PENDING).count()
    )
    return render(request, 'fercoins/manage.html', {'members': members, 'pending_count': pending_count})


@login_required(login_url='account_login')
@superuser_required
def give(request, user_id=None):
    form = GiveFercoinsForm(request.POST or None, recipient_id=user_id)

    if request.method == 'POST' and form.is_valid():
        chore = form.cleaned_data['chore']
        FercoinTransaction.objects.create(
            recipient=form.cleaned_data['recipient'],
            amount=form.cleaned_data['amount'],
            chore=chore,
            note=form.cleaned_data['note'] or (chore.name if chore else ''),
            given_by=request.user,
        )
        messages.success(request, 'Fercoins actualizados.')
        return redirect('fercoins:manage')

    chores = Chore.objects.filter(is_active=True)
    return render(request, 'fercoins/give.html', {'form': form, 'chores': chores})


@login_required(login_url='account_login')
@superuser_required
def chores(request):
    active = Chore.objects.filter(is_active=True)
    inactive = Chore.objects.filter(is_active=False)
    return render(request, 'fercoins/chores.html', {'active': active, 'inactive': inactive})


@login_required(login_url='account_login')
@superuser_required
def chore_create(request):
    form = ChoreForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tarea creada.')
        return redirect('fercoins:chores')
    return render(request, 'fercoins/chore_form.html', {'form': form, 'title': 'Nueva tarea'})


@login_required(login_url='account_login')
@superuser_required
def chore_edit(request, pk):
    chore = get_object_or_404(Chore, pk=pk)
    form = ChoreForm(request.POST or None, instance=chore)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tarea actualizada.')
        return redirect('fercoins:chores')
    return render(request, 'fercoins/chore_form.html', {'form': form, 'title': 'Editar tarea'})


@login_required(login_url='account_login')
@superuser_required
def chore_toggle(request, pk):
    chore = get_object_or_404(Chore, pk=pk)
    chore.is_active = not chore.is_active
    chore.save()
    return redirect('fercoins:chores')


@login_required(login_url='account_login')
@superuser_required
def prizes(request):
    active = Prize.objects.filter(is_active=True)
    inactive = Prize.objects.filter(is_active=False)
    return render(request, 'fercoins/prizes.html', {'active': active, 'inactive': inactive})


@login_required(login_url='account_login')
@superuser_required
def prize_create(request):
    form = PrizeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Premio creado.')
        return redirect('fercoins:prizes')
    return render(request, 'fercoins/prize_form.html', {'form': form, 'title': 'Nuevo premio'})


@login_required(login_url='account_login')
@superuser_required
def prize_edit(request, pk):
    prize = get_object_or_404(Prize, pk=pk)
    form = PrizeForm(request.POST or None, instance=prize)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Premio actualizado.')
        return redirect('fercoins:prizes')
    return render(request, 'fercoins/prize_form.html', {'form': form, 'title': 'Editar premio'})


@require_POST
@login_required(login_url='account_login')
@superuser_required
def prize_toggle(request, pk):
    prize = get_object_or_404(Prize, pk=pk)
    prize.is_active = not prize.is_active
    prize.save()
    return redirect('fercoins:prizes')


@require_POST
@login_required(login_url='account_login')
@kid_required
def chore_claim(request, pk):
    chore = Chore.objects.filter(pk=pk, is_active=True, fercoins__gt=0).first()
    if chore is None:
        messages.error(request, 'Esa tarea no se puede reclamar.')
        return redirect('fercoins:dashboard')

    pending = ChoreClaim.objects.filter(kid=request.user, chore=chore, status=ChoreClaim.PENDING)
    if pending.exists():
        messages.info(request, f'«{chore.name}» ya está pendiente de revisión.')
        return redirect('fercoins:dashboard')

    try:
        with transaction.atomic():
            ChoreClaim.objects.create(kid=request.user, chore=chore, amount=chore.fercoins)
    except IntegrityError:
        messages.info(request, f'«{chore.name}» ya está pendiente de revisión.')
    else:
        messages.success(request, f'¡Bien! «{chore.name}» queda pendiente de que lo revise un adulto.')
    return redirect('fercoins:dashboard')


@require_POST
@login_required(login_url='account_login')
@kid_required
def prize_request(request, pk):
    prize = Prize.objects.filter(pk=pk, is_active=True).first()
    if prize is None:
        messages.error(request, 'Ese premio no está disponible.')
        return redirect('fercoins:dashboard')

    with transaction.atomic():
        if prize.cost > get_available_balance(request.user):
            messages.error(request, f'No tienes suficientes fercoins disponibles para «{prize.name}».')
            return redirect('fercoins:dashboard')
        PrizeRequest.objects.create(kid=request.user, prize=prize, amount=prize.cost)

    messages.success(request, f'Has pedido «{prize.name}». Un adulto lo revisará pronto.')
    return redirect('fercoins:dashboard')


@require_POST
@login_required(login_url='account_login')
@kid_required
def request_cancel(request, pk):
    request_ = get_object_or_404(PrizeRequest, pk=pk, kid=request.user)
    if services.cancel_request(request_, request.user):
        messages.success(request, f'Petición de «{request_.prize.name}» cancelada.')
    else:
        messages.info(request, 'Esa petición ya estaba revisada.')
    return redirect('fercoins:dashboard')


@login_required(login_url='account_login')
@superuser_required
def review(request):
    claims = ChoreClaim.objects.filter(status=ChoreClaim.PENDING).select_related('kid', 'chore')
    prize_requests = PrizeRequest.objects.filter(status=PrizeRequest.PENDING).select_related('kid', 'prize')
    balances = {}
    for request_ in prize_requests:
        if request_.kid_id not in balances:
            balances[request_.kid_id] = get_balance(request_.kid)
        request_.kid_balance = balances[request_.kid_id]

    items = [('claim', claim) for claim in claims] + [('request', r) for r in prize_requests]
    items.sort(key=lambda item: item[1].created_at)
    return render(request, 'fercoins/review.html', {'items': items})


REVIEW_ACTIONS = {
    'claim': (ChoreClaim, services.approve_claim, services.reject_claim),
    'request': (PrizeRequest, services.approve_request, services.reject_request),
}


@require_POST
@login_required(login_url='account_login')
@superuser_required
def review_action(request, kind, pk, action):
    if kind not in REVIEW_ACTIONS or action not in ('approve', 'reject'):
        raise Http404
    model, approve, reject = REVIEW_ACTIONS[kind]
    item = get_object_or_404(model, pk=pk)

    if action == 'approve':
        done = approve(item, request.user)
        text = 'Aprobado.'
    else:
        done = reject(item, request.user, request.POST.get('reason', '').strip())
        text = 'Rechazado.'

    if done:
        messages.success(request, text)
    else:
        messages.info(request, 'Ya estaba revisada.')
    return redirect('fercoins:review')
