# Design

## Context

`fercoins` has two models. `Chore` has a signed `fercoins` value: positive values are rewards and negative values are penalties. `FercoinTransaction` is a ledger row. A balance is always derived as `SUM(amount)` (`get_balance`); no balance is stored. Parents are superusers, and every parent view uses `login_required` + `superuser_required`. Kids are users with a `core.KidProfile` (`kid_profile` relation). The kid dashboard (`fercoins:dashboard`) shows the balance and the transaction history. The database is SQLite. See proposal.md for the motivation and the specs for the required behavior.

## Goals / Non-Goals

**Goals:**
- Keep `FercoinTransaction` the single source of truth for balances. Claims and requests never change balances themselves; only approval writes a ledger row.
- Make every review transition (approve, reject, cancel) safe against double submission.
- Reuse the existing view, form and template patterns (Bootstrap dark cards, Spanish copy).

**Non-Goals:**
- No generic workflow or state-machine library.
- No change to the manual "Dar fercoins" flow or to the existing chore pages, apart from linking to the new pages.
- No real-time updates. Pages reflect state on load.

## Decisions

### 1. Two models with a shared abstract base

`ChoreClaim` (FK `chore`) and `PrizeRequest` (FK `prize`) both inherit from an abstract `ReviewableRequest`. The base holds `kid` (FK User, `related_name` per model), `amount` (positive integer, recorded at creation), `status` (`pending` / `approved` / `rejected` / `cancelled`), `reason` (short, blank), `created_at`, `reviewed_at`, `reviewed_by` (FK User, null) and `transaction` (OneToOne to `FercoinTransaction`, null, `SET_NULL`). The `cancelled` status is used only by `PrizeRequest`.

*Alternative:* a single `Request` table with a `kind` field and nullable `chore` / `prize` FKs. One review queue query is simpler that way, but every row carries a meaningless nullable FK, and the per-chore uniqueness constraint becomes awkward. Two querysets merged in Python for the review page is cheap at family scale.

### 2. Recorded amount, positive in both models

`amount` is copied from `chore.fercoins` or `prize.cost` at creation and stored as a positive number in both models. On approval, the ledger row is `+amount` for a claim and `-amount` for a prize request. Later edits to the chore or prize therefore never change what is pending or reserved, as the specs require.

### 3. Atomic, conditional state transitions

Each transition runs in `transaction.atomic()` and starts with a conditional update:

```
updated = ChoreClaim.objects.filter(pk=pk, status=PENDING).update(status=APPROVED, ...)
if updated == 1: create the FercoinTransaction and link it
```

If the row was no longer pending (a double click, or a cancel racing an approve), `updated == 0` and nothing else happens. The view then shows an info message such as "Ya estaba revisada." This guarantees that coins are credited or deducted at most once without relying on `select_for_update`, which SQLite ignores.

### 4. One pending claim per chore: a DB constraint plus a view check

`ChoreClaim.Meta.constraints` gets `UniqueConstraint(fields=['kid', 'chore'], condition=Q(status='pending'), name='one_pending_claim_per_chore')`. SQLite supports partial unique indexes. The claim view checks first so it can show a friendly message, and it also catches `IntegrityError` in case of a race.

### 5. Available balance

Add `get_available_balance(user)`, which is `get_balance(user)` minus the sum of `amount` over the user's pending `PrizeRequest`s. The request view computes it and creates the request inside one `transaction.atomic()`.

### 6. Prize ledger rows

The prize ledger row has `chore=None`, `note="Premio: <name>"`, `amount=-cost` and `given_by=<approving parent>`. The dashboard history already falls back to `note` when there is no chore, so prize rows show up without template changes. Approved chore claims set `chore=<chore>` and `note=<chore name>`, just like the existing give flow.

### 7. Access control

- Add a `kid_required` check: the user must have a `kid_profile`; otherwise raise `PermissionDenied` (403). Kid action views are `login_required` + `kid_required` + `require_POST`.
- Parent views (prize CRUD, review page, approve and reject) use the existing `login_required` + `superuser_required`. Approve and reject are `require_POST`.
- The dashboard keeps its current access. The chores, prizes and "my requests" sections, and their action buttons, render only for kids.
- Prize active toggle is POST-only. The existing chore toggle is GET and is left as it is; that's not this change's concern.

### 8. URLs and pages (all under `/fercoins/`)

| URL | Who | Purpose |
|---|---|---|
| `chores/<pk>/claim/` | kid, POST | create a claim |
| `prizes/<pk>/request/` | kid, POST | create a prize request |
| `requests/<pk>/cancel/` | kid, POST | cancel own pending request |
| `prizes/`, `prizes/new/`, `prizes/<pk>/edit/`, `prizes/<pk>/toggle/` | parent | prize catalog, mirrors chores |
| `review/` | parent | pending claims + requests, oldest first |
| `review/claim/<pk>/<approve\|reject>/`, `review/request/<pk>/<approve\|reject>/` | parent, POST | transitions; reject takes optional `reason` |

The kid dashboard shows the balance and available coins, then chores with "¡Lo hice!" (or "Pendiente" when a claim is pending), prizes with "Lo quiero" (or "Te faltan N"), then the last 10 claims and the last 10 requests (with "Cancelar" on pending requests), and finally the existing history. The manage page gets a "Pendientes (N)" button next to "Tareas" and a "Premios" button.

## Risks / Trade-offs

- [Two simultaneous prize requests from the same kid could both pass the available-balance check, because SQLite deferred transactions read before they take the write lock] → Accepted at family scale: it needs two near-identical submissions within milliseconds, and approval is still a human step, so the parent sees both. Wrapping the check in `atomic()` keeps the window tiny.
- [Approval can push a balance below zero if a penalty arrived after the request] → Allowed by the spec, which keeps the parent in control. The review page shows the kid's current balance next to each prize request so the parent can decide.
- [The kid dashboard gets long] → The sections are ordered by how often they're used, and the recent claims and requests lists are capped at 10 each. A separate kid page can come later if needed.

## Migration Plan

- One new migration in `fercoins` (`0002`) that only creates tables and the partial unique index. Existing data is untouched.
- It deploys through the existing CI pipeline. The entrypoint runs `migrate`.
- Rollback: redeploy the previous image and run `manage.py migrate fercoins 0001`, which drops the new tables. Ledger rows created by approvals stay valid on their own.
