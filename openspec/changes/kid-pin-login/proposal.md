# Proposal

## Why

Kids can't use Zeneke today. Login is OAuth-only (`SOCIALACCOUNT_ONLY = True`), and young kids don't have, and shouldn't need, Google or GitHub accounts. As a result the Fercoins kid dashboard can't be reached. The site will be exposed to the internet, which adds a second problem: anyone who signs in with any Google account becomes a fercoins "family member". The site needs an explicit notion of who is a kid and a simple, safe way for kids to sign in.

## What Changes

- Add **kid accounts**: user accounts explicitly marked with a kid role. Parents (superusers) create them from a new family management page by choosing a username.
- Add **kid login with username + 4-digit PIN** on the main login page, next to the existing Google/GitHub buttons. Only kid accounts can sign in this way.
- When a parent creates a kid, the parent gets a **one-time 6-digit setup code**, valid for 24 hours. The kid signs in once with the code and **chooses their own PIN**, so a username alone can never claim an account. Kids can **change their PIN** at any time, which requires their current PIN.
- Parents can **reset a kid's PIN**, which issues a new setup code so the kid chooses a new PIN, and **unlock** a locked kid account.
- Add **brute-force protection**: 5 consecutive failed PIN attempts lock the account for 15 minutes. All failures show the same generic message, so the page never reveals which usernames exist.
- Make the custom login template actually render. Today allauth ignores `templates/registration/login.html` and shows its unstyled default page.
- **BREAKING (behavior)**: Fercoins member lists and the give form include only kid accounts, not every non-superuser. Existing non-superuser accounts created through OAuth no longer appear in Fercoins until a parent marks them as kids.
- Parents keep signing in with Google/GitHub exactly as today.

## Capabilities

### New Capabilities
- `kid-authentication`: How kid accounts sign in with username + PIN: choosing a PIN at first login, changing it, generic errors and lockout.
- `family-management`: How parents manage the family's kid accounts: creating kids, resetting PINs, unlocking accounts.
- `fercoins`: Which accounts take part in Fercoins. Only kid accounts can be listed as members and receive fercoins.

### Modified Capabilities
<!-- None: no specs exist yet in openspec/specs/. -->

## Impact

- **Code**: `core` gets a kid-role profile model with a migration, the PIN login, set-PIN and change-PIN views, a custom authentication backend, and the family management views. `fercoins` changes its member queries in `views.py` and `forms.py`. Templates: the login page moves to an allauth override (`templates/account/login.html`), plus new family and PIN templates.
- **Settings**: a new authentication backend in `AUTHENTICATION_BACKENDS`. Allauth stays configured as `SOCIALACCOUNT_ONLY` for parents.
- **Data**: new tables only. Existing users are unaffected except that they are no longer listed in Fercoins unless marked as kids.
- **Dependencies**: none new.
- **Out of scope**: production settings hardening (DEBUG/SECRET_KEY defaults, HTTPS cookies, CSRF trusted origins), restricting open OAuth signup, per-IP rate limiting. Each is a follow-up change.
