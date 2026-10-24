# Proposal

## Why

Signing in with Google or GitHub stops on a bare, unstyled allauth page ("Sign In Via Google ... Continue") with no site CSS, which looks broken, especially on phones. The home page also lists only Bingo, so Fercoins, the app the family uses most, can only be found from the navbar.

## What Changes

- **One-click social sign-in:** clicking "Google" or "GitHub" on the login page goes straight to the provider. The intermediate "Sign In Via ..." confirmation page no longer appears in the normal flow. The page you came from (for example Fercoins) is still where you land after signing in.
- **Site styling on every allauth page:** any allauth page that can still be reached (the confirmation page opened by a direct link, sign-in cancelled, sign-in error, the logout confirmation, the social sign-up form) uses the site layout: navbar, dark theme, Bootstrap buttons and cards. No more raw "Menu:" list.
- **Home page shows the apps a visitor can use:**
  - A Fercoins card next to Bingo. Signed-out visitors see that it needs a sign-in.
  - A Familia card for parents (superusers), matching the navbar.
  - A greeting with the user's name when signed in.
- **Spanish everywhere:** the home page, the login page and the navbar's Login/Logout buttons are translated to Spanish, so they match Fercoins, Familia and Bingo, and the page language becomes `es`.

Out of scope: Google's own account picker and consent screen (styled by Google; the app name and logo there are set in the Google Cloud console), new sign-in providers, highlighting the current page in the navbar, changes to the kid PIN sign-in behaviour.

## Capabilities

### New Capabilities
- `social-sign-in`: how parents start a Google or GitHub sign-in from the login page and what they see on the auxiliary sign-in pages.
- `site-home`: what the home page shows to signed-out visitors, kids and parents.

### Modified Capabilities
<!-- None. kid-authentication only requires that the login page shows the Google and
     GitHub buttons next to the kid form; that stays true, only the button labels'
     language changes. -->

## Impact

- **Templates:** `src/app/templates/core/home.html`, `src/app/templates/account/login.html`, `src/app/templates/base.html`; new overrides under `src/app/templates/allauth/` (layout and a few form elements).
- **Possibly** `src/app/static/css/style.css` for small styling of the new cards.
- **Tests:** `core/tests.py` asserts the English button text "Continue with Google"; it moves to the Spanish text. New tests for the home page cards and the POST sign-in buttons.
- **No changes** to models, settings, URLs, dependencies or data. No allauth security setting is relaxed (`SOCIALACCOUNT_LOGIN_ON_GET` stays off).
- **Deploy:** normal push to `main`.
