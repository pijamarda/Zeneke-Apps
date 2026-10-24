# Tasks

## 1. One-click Google and GitHub sign-in

- [ ] 1.1 In `src/app/templates/account/login.html`, replace the two provider `<a>` links with `<form method="post" action="{% provider_login_url ... %}">` forms holding `{% csrf_token %}` and a submit button styled like the current buttons (Google SVG and GitHub icon kept); verify in a browser that "Google" goes straight to Google's account picker
- [ ] 1.2 Add tests in `src/app/core/tests.py`: the login page contains POST forms whose action is each provider's login URL, and with `?next=/fercoins/` the action URLs carry that `next`; verify the tests pass
- [ ] 1.3 Add a test that a GET on the Google login URL still returns the confirmation page (200, no redirect to Google), proving `SOCIALACCOUNT_LOGIN_ON_GET` stays off; verify it passes

## 2. Site layout on allauth pages

- [ ] 2.1 Add an optional `main_class` block to `<main>` in `src/app/templates/base.html` (default keeps today's classes); verify existing pages render unchanged
- [ ] 2.2 Add `src/app/templates/allauth/layouts/base.html` extending `base.html`, mapping `head_title` into `title` and setting a narrow centred column; verify the GET confirmation page from 1.3 now contains the site navbar and no "Menu:" text
- [ ] 2.3 Override `src/app/templates/allauth/elements/` button, form, h1, h2, p, alert, field, fields, hr and panel with Bootstrap classes, keeping all attributes the 65.x originals handle; verify the confirmation page's "Continue" is a `btn` and still signs in when submitted
- [ ] 2.4 Add tests that the sign-in cancelled page (`socialaccount_login_cancelled`) and the logout confirmation page (GET `account_logout` while signed in) render with the site navbar; verify they pass

## 3. Home page cards and greeting

- [ ] 3.1 Rewrite `src/app/templates/core/home.html` with Bingo and Fercoins cards for everyone, a "necesitas iniciar sesión" note on Fercoins for anonymous visitors, and a Familia card only for superusers; verify visually at phone and desktop widths
- [ ] 3.2 Add a greeting with the username for signed-in users and a general welcome otherwise
- [ ] 3.3 Add tests in `src/app/core/tests.py` for each `site-home` scenario (anonymous, kid, parent: which cards, the sign-in note, the greeting); verify they pass

## 4. Spanish text

- [ ] 4.1 Translate the home page, the login page ("Iniciar sesión", "Continuar con Google", "Continuar con GitHub", "Niños", labels) and the navbar Login/Logout buttons to Spanish, and set `<html lang="es">` in `base.html`; update the existing assertion on "Continue with Google" in `core/tests.py` to the Spanish label; verify the full test suite passes (from `src/app`: `uv run --project .. python manage.py test`)

## Workflow follow-up

- Open a PR, let CI pass, merge to deploy, then check on apps.zeneke.com from a phone that Google sign-in goes straight to Google.
- Archive the change with `/opsx:archive`.
