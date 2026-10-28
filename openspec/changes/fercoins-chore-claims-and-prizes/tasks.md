# Tasks

Run all commands from `src/app` with `uv run python manage.py ...`.

## 1. Models and migration

- [x] 1.1 Add `Prize` (`name`, `description` blank, `cost` positive integer with a validator for minimum 1, `is_active`, `created_at`; ordered by `cost`, `name`), the abstract `ReviewableRequest`, `ChoreClaim` (with the partial `UniqueConstraint` `one_pending_claim_per_chore`) and `PrizeRequest` to `fercoins/models.py` as described in design.md decisions 1 and 4, plus `get_available_balance(user)` (decision 5). Run `makemigrations fercoins` to create `0002`, then verify `makemigrations --check` is clean and `migrate` succeeds.
- [x] 1.2 Register `Prize`, `ChoreClaim` and `PrizeRequest` in `fercoins/admin.py` (list kid, item, amount, status, created_at; filter by status). Verify they appear at `/admin/`.
- [x] 1.3 Add model tests to `fercoins/tests.py`: a second pending claim for the same kid and chore raises `IntegrityError`, but is allowed once the first is approved, and is allowed for a different kid; `get_available_balance` subtracts only pending request amounts (not approved, rejected or cancelled ones). Verify `manage.py test fercoins` passes.

## 2. Transition helpers

- [x] 2.1 Implement the transition functions in a new `fercoins/services.py` following design.md decisions 3 and 6: `approve_claim`, `reject_claim`, `approve_request`, `reject_request` and `cancel_request`. Each one runs atomically, does a conditional update from pending, creates and links the ledger row only on approval, and returns whether the transition happened. Verify `manage.py check` passes.
- [x] 2.2 Add service tests: approving a claim credits the recorded amount (not the chore's current value) with `chore` and `given_by` set; approving a request deducts the recorded cost with note `Premio: <name>`; a second approval of the same item creates no second transaction; reject after approve and cancel after approve leave the item approved; rejecting stores the reason and moves no coins; approval works for a deactivated chore or prize; approval may make the balance negative. Verify `manage.py test fercoins` passes.

## 3. Prize catalog (parent)

- [x] 3.1 Add `PrizeForm` and the parent views and templates `prizes`, `prize_create`, `prize_edit` and a POST-only `prize_toggle`, mirroring the chore pages (Spanish copy: "Premios", "Nuevo premio", "Coste"). Add a "Premios" button on `manage.html`. Verify the pages load for a superuser in `runserver`.
- [x] 3.2 Add tests: a parent creates and edits a prize; a cost of 0 or -5 is rejected; toggle by GET is refused (405); a kid gets 403 or a redirect on every prize management URL. Verify `manage.py test fercoins` passes.

## 4. Kid dashboard and actions

- [x] 4.1 Add a `kid_required` check (403 for non-kids) and the kid POST views `chore_claim`, `prize_request` and `request_cancel` (design.md decisions 7 and 8). Claim and request validate active status, positive value and available balance, show a Spanish message on success or refusal, and redirect to the dashboard. Cancel only touches the kid's own requests. Verify `manage.py check` passes.
- [x] 4.2 Extend the `dashboard` view and `dashboard.html` for kids: balance plus "Disponible", earning chores with "¡Lo hice!" or a "Pendiente" badge, active prizes with "Lo quiero" or "Te faltan N", the last 10 claims and last 10 requests with status, reason and "Cancelar" on pending requests, then the existing history. Non-kid, non-superuser accounts see none of the new sections. Verify the page renders correctly as a kid in `runserver`.
- [x] 4.3 Add tests: only active, positive chores are listed; a forged claim on a penalty, inactive or missing chore creates nothing; a duplicate pending claim is refused with a message; a request over the available amount is refused (30 available: first 20 OK, second 20 refused); a forged request for an inactive prize creates nothing; a kid cannot cancel another kid's request; a cancel releases the reserved coins; the dashboard shows only the kid's own claims and requests; a non-kid non-superuser gets 403 on the kid actions, and an anonymous user is redirected to login with nothing created. Verify `manage.py test fercoins` passes.

## 5. Parent review page

- [x] 5.1 Add the parent `review` view and `review.html`: pending claims and requests merged and sorted oldest first, each showing the kid, the item, the amount, when it was submitted and the kid's current balance for prize requests, plus approve and reject forms (reject with an optional reason input). Add the POST approve and reject views that call the services and show "Aprobado", "Rechazado" or "Ya estaba revisada". Add the "Pendientes (N)" button on `manage.html`, shown only when N > 0. Verify in `runserver` that approving a claim updates the kid's balance.
- [x] 5.2 Add tests: the review page lists pending items oldest first and says there is nothing to review when empty; a kid is denied; approve and reject by GET are refused (405); approve and reject through the views produce the expected ledger effects; the manage page shows "3" pending for two claims and one request and shows no count when nothing is pending. Verify `manage.py test fercoins` passes.

## 6. Integration check

- [x] 6.1 Run the full suite (`manage.py test`) and `makemigrations --check`, then do a manual smoke test with `runserver`. As a parent: create chores (+5 and -5) and prizes (20 and 80). As a kid in a private window: confirm the penalty chore is hidden, claim the +5 chore twice (the second is refused), and request the 20 prize (available drops by 20) and then cancel it. Request it again. As the parent: approve the claim and the request from "Pendientes" and confirm the kid's balance and history. Confirm every step behaves as specified.

## Workflow follow-up

- Archive the change after review.
- Possible follow-up changes: kids suggesting prizes, per-chore frequency limits, a "delivered" state for prizes.
