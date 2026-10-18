# Design

## Context

- Django 6.0.1 + django-allauth 65.16.1, SQLite, gunicorn with 2 workers in Docker.
- Allauth runs with `SOCIALACCOUNT_ONLY = True`, so there is no password login form. `/admin/login/` is the only password path and it requires `is_staff`.
- "Parent" today means `is_superuser`. `fercoins` treats every non-superuser as a family member (`views.manage`, `GiveFercoinsForm.recipient`).
- `/accounts/login/` currently renders allauth's default `account/login.html`. The styled `templates/registration/login.html` is never used, because allauth looks for templates under `account/`.
- There are no tests in the repo yet.

Requirements live in `specs/`; see `proposal.md` for the motivation.

## Goals / Non-Goals

**Goals:**
- Put the kid identity (role, PIN, lockout, setup code) in `core`, so future apps such as Bingo can reuse "who is a kid".
- Make PIN sign-in the only way to authenticate as a kid.

**Non-Goals:**
- A general role or permission system. Parents stay `is_superuser`.
- Per-IP rate limiting, CAPTCHA, production settings hardening, closing open OAuth signup. These are follow-up changes.
- A numeric keypad widget. A plain `inputmode="numeric"` field is enough for now.

## Decisions

### 1. `KidProfile` in `core` marks a kid; having one is the role
A `core.KidProfile` with a `OneToOneField(User, related_name='kid_profile')` holds `pin_hash`, `failed_attempts`, `locked_until`, `setup_code_hash`, `setup_code_expires_at`. A user is a kid if and only if this profile exists, and queries filter with `kid_profile__isnull=False`.
- *Alternative:* a `role` field on a general `FamilyProfile`. Rejected for now: parents don't need a profile yet, and it can be generalised when Bingo needs it.
- *Alternative:* a Django `Group("kids")`. Rejected: the lockout and setup state need their own fields anyway.

### 2. The PIN is hashed in `KidProfile.pin_hash`, not in `User.password`
Store it with `make_password` and check it with `check_password` (Django's configured hasher). The kid's `User.password` is always unusable (`set_unusable_password()`). As a result, `ModelBackend`, `/admin/login/` and any future password login can never authenticate a kid, so the lockout cannot be bypassed.
- *Alternative:* `user.set_password(pin)`, as discussed during exploration. Rejected: every password path (including the admin form, which has no lockout) would accept the PIN.
- **Ending sessions on reset:** Django ties sessions to a hash of `User.password`. A parent reset calls `set_unusable_password()` again, which writes a new random unusable value, so every existing kid session becomes invalid. A kid changing their own PIN does not touch `User.password`, so they stay signed in, as the spec requires.

### 3. A custom auth backend does the check and the lockout
`core.backends.KidPinBackend.authenticate(request, username=None, pin=None)` is added to `AUTHENTICATION_BACKENDS`. It only acts when `pin` is passed, so the other backends ignore it and it ignores their calls. Steps:
1. Look up the user with `kid_profile`, matching the username case-insensitively. If more than one kid matches, treat it as no match (the create form prevents such duplicates). If none exists, run a dummy `check_password` (similar timing) and return `None`.
2. If `locked_until > now`, return `None` (no counting while locked).
3. If the PIN matches, reset `failed_attempts` to 0 and return the user. Otherwise increment the counter atomically (`F('failed_attempts') + 1`) and, on reaching 5, set `locked_until = now + 15 min` and reset the counter. Return `None`.

The setup-code check reuses the same lock and counter logic through a shared helper, but it does not log the kid in (see 4). Constants: `MAX_ATTEMPTS = 5`, `LOCK_MINUTES = 15`, `SETUP_CODE_HOURS = 24`.
- The counter lives in the DB because the default `LocMemCache` is per-process and gunicorn runs 2 workers. SQLite serialises writes, which is enough at this scale.

### 4. Setup-code sign-in uses a pending session step, not a login
The kid form posts `username` + `code` to `core:kid_login`:
- **4-digit code:** treated as a PIN. Call `authenticate(...)` then `login(...)`, and redirect to a safe `next` or to `fercoins:dashboard`.
- **6-digit code:** treated as a setup code. If it is valid and not expired, store `kid_setup_user_id` and a timestamp in the session (no `login()`), and redirect to `core:kid_setup_pin`. That view accepts only a pending entry less than 10 minutes old. Once the PIN is saved, it clears the setup hash, logs in, and redirects to the dashboard.
- Anything else, or any failure: re-render the login page with the one generic message.

Because the kid is never logged in before choosing a PIN, "cannot skip choosing a PIN" holds automatically: every other page treats them as anonymous.

### 5. One login page, overriding allauth's template
Move the styled page to `templates/account/login.html`, which allauth's `LoginView` renders, and delete `templates/registration/login.html`. The page keeps the Google and GitHub buttons and adds the kid form, which posts to `core:kid_login`. On failure `kid_login` renders the same template with the error. Allauth settings stay as they are.

### 6. Family management lives in `core` at `/family/`
Parent-only views using the same `superuser_required` pattern as `fercoins/views.py`: the list, create kid, reset PIN, and unlock (POST only). The setup code is generated with `secrets.randbelow(10**6)` and zero-padded to 6 digits. Only its hash is stored. The plain code is rendered **directly in the POST response** and is never put in `messages`, because the default message storage can keep it in a cookie. Reloading the page shows nothing, and the code page is sent with `Cache-Control: no-store`. A reset also clears the lock and failure count. Kid users are created with `set_unusable_password()`, no email, and `is_staff = is_superuser = False`. With no email, allauth can't auto-connect a social account to them.
- `KidProfile` is also registered in the admin, so a parent can turn an existing OAuth-created account into a kid. This is the migration path for current members.

### 7. Fercoins filters to kids
`manage` and `GiveFercoinsForm.recipient` change `is_superuser=False` to `kid_profile__isnull=False`. Because the form's queryset limits the choices, a forged recipient id fails validation. The empty-state text links to `/family/`.

### 8. Sessions and UI copy
Django's defaults (`SESSION_COOKIE_AGE` = 2 weeks, `SESSION_EXPIRE_AT_BROWSER_CLOSE = False`) already give the 2-week kid session, so no settings change is needed. A test pins this behaviour. New family and PIN pages are in Spanish, like the rest of Fercoins. The navbar gets a "Cambiar PIN" link for kids and a "Familia" link for parents.

## Risks / Trade-offs

- [A 4-digit PIN can still be guessed slowly: about 480 tries per day per kid] → acceptable for a points app. Per-IP throttling is a follow-up. A parent can see lock states on `/family/`.
- [Repeated failures can lock out a kid on purpose (denial of service)] → the lock lasts only 15 min and a parent can unlock immediately.
- [A setup code read off the parent's screen is a credential for 24h] → it is single use, expires, and is replaced by any new code. Lockout applies to it too.
- [A brief username timing difference despite the dummy hash] → low impact. It only reveals that a kid username exists, not the PIN.
- [BREAKING: existing non-superuser members vanish from Fercoins] → their transactions remain. A parent attaches a `KidProfile` in the admin to bring one back.
- [SQLite under concurrent writes] → the scale is a single family. It can be revisited if the app moves to Postgres.

## Migration Plan

1. Deploy. The entrypoint runs `migrate`, which creates the `core_kidprofile` table only.
2. A parent creates kids on `/family/`, or converts existing accounts through the admin.
3. Rollback: revert the code. The new table can stay or be removed by migrating `core` to `zero`. No existing data is changed.
