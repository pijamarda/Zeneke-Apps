# Tasks

Run all commands from `src/app` with `uv run python manage.py ...`.

## 1. Kid profile model

- [x] 1.1 Add `core.KidProfile` (OneToOne to User, `related_name='kid_profile'`, `pin_hash`, `failed_attempts`, `locked_until`, `setup_code_hash`, `setup_code_expires_at`) with helpers `set_pin`, `check_pin`, `issue_setup_code` (returns the plain 6-digit code, stores only its hash, expiry 24h), `is_locked`, `state` (awaiting setup / active / locked). Verify `makemigrations core` creates `0001_initial` and `makemigrations --check` is then clean.
- [x] 1.2 Register `KidProfile` in `core/admin.py` (list username, state, `locked_until`). Verify it appears at `/admin/` after `migrate`.
- [x] 1.3 Add `core/tests.py` model tests: a PIN is stored hashed (the digits are not in `pin_hash`), PIN format validation rejects `123`, `12345`, `12a4`, a new setup code replaces the old one, and an expired code is rejected. Verify `manage.py test core` passes.

## 2. PIN authentication backend and lockout

- [x] 2.1 Implement `core.backends.KidPinBackend` following design.md decision 3 (kid-only, dummy hash for unknown users, atomic counter, lock after 5 failures for 15 min, reset on success), plus a shared helper for setup-code checks that applies the same lockout. Add it to `AUTHENTICATION_BACKENDS` in `backend/settings.py`. Verify `manage.py check` passes.
- [x] 2.2 Add backend tests: correct PIN authenticates; a parent or non-kid username returns `None`; 5 failures lock the account and the correct PIN then fails; the lock expires after 15 min (freeze or patch `timezone.now`); success resets the count (4 wrong, correct, 4 wrong = not locked); `ModelBackend` / `/admin/login/` cannot authenticate a kid with their PIN. Verify `manage.py test core` passes.

## 3. Kid sign-in, setup and change-PIN views

- [x] 3.1 Move the styled login page to `templates/account/login.html` (delete `templates/registration/login.html`) and add the kid form (username + `inputmode="numeric"` code field) posting to `core:kid_login`. Verify that `GET /accounts/login/` renders the Zeneke-styled page with both the OAuth buttons and the kid form, and lists no usernames.
- [x] 3.2 Implement `kid_login` (4-digit = PIN, `login()` and redirect to a safe `next` or `fercoins:dashboard`; 6-digit = setup code, store the pending entry in the session and redirect to `kid_setup_pin`; anything else = the login page with the one generic error) and `kid_setup_pin` (pending entry must be under 10 min old; PIN twice; save, clear the setup code, `login()`). Verify with tests: correct PIN signs in; unknown user, wrong PIN, parent username and locked account all show the identical message; an off-site `next` is ignored; a setup code leads to choose-PIN and then the dashboard; mismatched confirmation is rejected; an expired or reused setup code fails; while setup is pending, `/fercoins/` still redirects to login.
- [x] 3.3 Implement `kid_change_pin` (kid-only, current PIN + new PIN twice; a wrong current PIN counts toward the lockout) and add a "Cambiar PIN" navbar link shown only to kids in `base.html`. Verify with tests: a successful change keeps the kid signed in and the old PIN stops working; a wrong current PIN does not change it and increments `failed_attempts`; non-kids get 403 or a redirect.
- [x] 3.4 Add a test that a kid session uses a 2-week cookie that is not tied to browser close (`SESSION_COOKIE_AGE == 1209600`, `SESSION_EXPIRE_AT_BROWSER_CLOSE` is False, the session cookie has `max-age`). Verify `manage.py test core` passes.

## 4. Family management (parents)

- [x] 4.1 Implement parent-only `/family/` views in `core` (list with states, create kid, reset PIN, unlock; POST-only for actions) and templates in Spanish. Kids are created with `set_unusable_password()`, no email, not staff. The setup code is shown only in the POST response, never via `messages`. Reset re-runs `set_unusable_password()` to end the kid's sessions. Add a "Familia" navbar link for superusers. Verify the pages load for a superuser created with `createsuperuser`.
- [x] 4.2 Add family tests: a kid or anonymous user is denied or redirected; creating a kid shows a 6-digit code once and the state "awaiting setup"; a duplicate username is rejected; a second code invalidates the first; reset invalidates the old PIN and an existing kid session (the next request with that client is anonymous); unlock clears the lock and the old PIN works. Verify `manage.py test core` passes.
- [x] 4.3 Add a test that resetting a locked kid's PIN clears the lock, so the new setup code works immediately. Verify `manage.py test core` passes.

## 5. Fercoins: kids only

- [x] 5.1 Change `fercoins/views.py` `manage` and `fercoins/forms.py` `GiveFercoinsForm.recipient` to filter `kid_profile__isnull=False`, and update the empty state in `templates/fercoins/manage.html` to link to `/family/`. Verify `manage.py check` passes.
- [x] 5.2 Add `fercoins/tests.py` tests: a non-kid non-superuser is not listed and not offered on give; a forged non-kid recipient POST creates no transaction; a new kid appears with balance 0; the empty state links to `/family/`. Verify `manage.py test fercoins` passes.

## 6. Integration check

- [x] 6.1 Run the full suite (`manage.py test`) and `makemigrations --check`, then do a manual smoke test with `runserver`. As a parent (superuser via `/admin/login/`): create a kid on `/family/` and note the code. In a private window: sign in as the kid with the code, choose a PIN, reach the Fercoins dashboard, change the PIN, and log out. Enter 5 wrong PINs and confirm the account locks. Back as the parent: unlock it and give the kid fercoins. Confirm every step behaves as specified.
- [x] 6.2 Update `src/README.md` with local run steps (migrate, createsuperuser, sign in as a parent via `/admin/login/` when OAuth keys are unset, and how kids are created). Verify the documented commands run as written.

## Workflow follow-up

- Archive the change after review.
- Follow-up changes to propose: `prod-hardening` (DEBUG/SECRET_KEY defaults, HTTPS cookies, `CSRF_TRUSTED_ORIGINS`) and restricting open OAuth signup to known parents.
