from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ChoreForm, GiveFercoinsForm
from .models import Chore, FercoinTransaction, get_balance

User = get_user_model()

superuser_required = user_passes_test(lambda u: u.is_superuser, login_url='account_login')


@login_required(login_url='account_login')
def dashboard(request):
    if request.user.is_superuser:
        return redirect('fercoins:manage')

    balance = get_balance(request.user)
    transactions = request.user.fercoins_received.select_related('chore', 'given_by').all()

    return render(request, 'fercoins/dashboard.html', {
        'balance': balance,
        'transactions': transactions,
    })


@login_required(login_url='account_login')
@superuser_required
def manage(request):
    members = (
        User.objects.filter(is_superuser=False)
        .annotate(balance=Coalesce(Sum('fercoins_received__amount'), Value(0)))
        .order_by('username')
    )
    return render(request, 'fercoins/manage.html', {'members': members})


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
