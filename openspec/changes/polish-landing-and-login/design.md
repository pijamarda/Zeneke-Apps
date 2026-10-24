# Design

## Context

- django-allauth 65.16.1, `SOCIALACCOUNT_ONLY = True`, `SOCIALACCOUNT_LOGIN_ON_GET` left at its default (off).
- `templates/account/login.html` already overrides allauth's login page, but its provider buttons are `<a href="{% provider_login_url ... %}">` links. A GET on that URL renders allauth's `socialaccount/login.html` confirmation page, which is the bare page from the bug report.
- allauth's built-in templates all extend `allauth/layouts/base.html` (through `entrance.html` / `manage.html`). That base has no CSS and prints the "Menu:" list. They render their pieces through `{% element %}` templates in `allauth/elements/` (button, form, h1, p, alert, field, ...).
- Our `templates/base.html` provides the navbar, Bootstrap 5 dark theme and blocks `title`, `content`, `extra_head`, `extra_js`.

## Goals / Non-Goals

**Goals:**
- Remove the confirmation step from the normal button flow without weakening CSRF protection.
- Make every allauth page that can still be reached look like the site, using one override point rather than one template per page.

**Non-Goals:**
- Restyling every allauth element type. Only the elements used by the pages reachable with `SOCIALACCOUNT_ONLY` are covered: button, form, h1, h2, p, alert, field/fields, hr, panel.
- A full translation setup (`LANGUAGE_CODE`, `.po` files). Our own templates get Spanish text written in directly; allauth's strings stay as allauth renders them.

## Decisions

### Provider buttons become POST forms
Each button is a `<form method="post" action="{% provider_login_url 'google' %}">` with `{% csrf_token %}` and a submit button styled like today's link. allauth starts the OAuth redirect on POST, so the confirmation page is skipped. `provider_login_url` already copies `?next=` from the current request into the action URL, so returning to Fercoins after sign-in keeps working without extra code.

- *Alternative: `SOCIALACCOUNT_LOGIN_ON_GET = True`.* One line, but allauth documents it as allowing login CSRF (a third-party site can start a sign-in for the visitor). Rejected.
- *Alternative: only restyle the confirmation page.* Still leaves an extra click on every sign-in. Rejected as the main fix, though the restyle happens anyway through the layout override below.

### One layout override for all allauth pages
Add `templates/allauth/layouts/base.html` that `{% extends "base.html" %}`, and maps allauth's `head_title` block into our `title`. Our project templates directory is searched before app templates, so this replaces allauth's base for every allauth page at once (confirmation, cancelled, error, logout, social signup).

Block names: allauth's page templates fill a block called `content`, the same name as the block in our `base.html`. Because the override extends `base.html`, an allauth page's `content` replaces ours directly, so the card wrapper cannot live inside that block. Instead, our `base.html` gets an optional `{% block main_class %}` on `<main>` that the override sets to a narrow centred column (`col-md-6 col-lg-5 mx-auto` style). The allauth elements render as Bootstrap controls (next decision), and the `panel` element renders as a card. Task 2 verifies this with a rendering test.

### Bootstrap-styled allauth elements
Override the handful of `templates/allauth/elements/*.html` listed in Non-Goals with Bootstrap classes (`btn btn-primary`, `form-control`, `alert`, headings with `fw-bold`). Each keeps the attributes of allauth's original (href/type/name/value/form for buttons, method/action for forms) so behaviour is unchanged.

### Home page cards in the template
The home view stays `render(request, 'core/home.html')`. The template decides the cards from `user.is_authenticated` and `user.is_superuser`, the same checks the navbar uses. No new view context is needed.

## Risks / Trade-offs

- [An allauth upgrade changes the element templates' attributes or the layout block names] → Overrides copy only the attribute handling of the 65.x originals; the tests in task 2 render the confirmation, cancelled and logout pages and check for our navbar, so a breaking upgrade shows up as a failing test.
- [Some allauth text stays in English (e.g. "Continue")] → Acceptable for pages that are rarely seen; a later change can set `LANGUAGE_CODE = 'es'` if wanted, which would also switch the admin to Spanish.
- [Users with JavaScript disabled] → Not affected: the buttons are plain HTML forms.

## Migration Plan

Template-only change. Deploy with the normal push to `main`. Rollback is reverting the commit.
