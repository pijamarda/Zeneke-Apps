"""Review transitions for chore claims and prize requests.

Each transition starts with a conditional update from pending, so a double
submission or a racing cancel can never move coins twice.
"""
from django.db import transaction
from django.utils import timezone

from .models import ChoreClaim, FercoinTransaction, PrizeRequest


def _leave_pending(model, pk, status, **fields):
    return model.objects.filter(pk=pk, status=model.PENDING).update(status=status, **fields) == 1


def _review(model, pk, status, parent, reason=''):
    return _leave_pending(
        model, pk, status, reviewed_by=parent, reviewed_at=timezone.now(), reason=reason[:200],
    )


@transaction.atomic
def approve_claim(claim, parent):
    if not _review(ChoreClaim, claim.pk, ChoreClaim.APPROVED, parent):
        return False
    tx = FercoinTransaction.objects.create(
        recipient=claim.kid,
        amount=claim.amount,
        chore=claim.chore,
        note=claim.chore.name,
        given_by=parent,
    )
    ChoreClaim.objects.filter(pk=claim.pk).update(transaction=tx)
    return True


@transaction.atomic
def reject_claim(claim, parent, reason=''):
    return _review(ChoreClaim, claim.pk, ChoreClaim.REJECTED, parent, reason)


@transaction.atomic
def approve_request(request_, parent):
    if not _review(PrizeRequest, request_.pk, PrizeRequest.APPROVED, parent):
        return False
    tx = FercoinTransaction.objects.create(
        recipient=request_.kid,
        amount=-request_.amount,
        note=f'Premio: {request_.prize.name}',
        given_by=parent,
    )
    PrizeRequest.objects.filter(pk=request_.pk).update(transaction=tx)
    return True


@transaction.atomic
def reject_request(request_, parent, reason=''):
    return _review(PrizeRequest, request_.pk, PrizeRequest.REJECTED, parent, reason)


@transaction.atomic
def cancel_request(request_, kid):
    if request_.kid_id != kid.pk:
        return False
    return _leave_pending(PrizeRequest, request_.pk, PrizeRequest.CANCELLED)
