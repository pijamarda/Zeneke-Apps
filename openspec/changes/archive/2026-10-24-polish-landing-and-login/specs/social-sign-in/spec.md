# Spec Delta

## Purpose

Lets parents sign in with their Google or GitHub account in one click from the login page, and keeps every auxiliary sign-in page consistent with the rest of the site.

## ADDED Requirements

### Requirement: One-click provider sign-in
Choosing Google or GitHub on the login page SHALL send the visitor directly to that provider's sign-in, without an intermediate confirmation page on this site. Starting a provider sign-in SHALL require a request protected against cross-site request forgery; a plain link or GET request SHALL NOT start it on its own.

#### Scenario: Google button goes straight to Google
- **WHEN** an anonymous visitor on the login page chooses "Google"
- **THEN** the browser is redirected to Google's sign-in
- **AND** no "Sign In Via Google" page from this site is shown

#### Scenario: GitHub button goes straight to GitHub
- **WHEN** an anonymous visitor on the login page chooses "GitHub"
- **THEN** the browser is redirected to GitHub's sign-in

#### Scenario: A GET request does not start sign-in by itself
- **WHEN** someone opens the provider sign-in URL with a plain GET request
- **THEN** the site does not redirect to the provider
- **AND** it shows a confirmation page that needs an explicit click

### Requirement: Return to the original page after provider sign-in
When a visitor reaches the login page from a protected page on this site, a successful Google or GitHub sign-in SHALL bring them back to that page. Without such a page, they SHALL land on the home page.

#### Scenario: Coming from Fercoins
- **WHEN** an anonymous visitor opens the Fercoins dashboard, is sent to the login page, and signs in with Google
- **THEN** they land on the Fercoins dashboard

#### Scenario: Opening the login page directly
- **WHEN** a visitor opens the login page directly and signs in with GitHub
- **THEN** they land on the home page

### Requirement: Auxiliary sign-in pages use the site layout
Every sign-in related page shown by the site (provider confirmation, sign-in cancelled, sign-in error, logout confirmation, social sign-up form) SHALL use the same layout as the rest of the site: navigation bar, site styles and styled buttons. None of them SHALL show an unstyled page.

#### Scenario: Cancelled sign-in
- **WHEN** a visitor cancels on Google's screen and is sent back to the site
- **THEN** the "cancelled" page shows the site navigation bar and a styled link back to the login page

#### Scenario: Confirmation page opened by a direct link
- **WHEN** someone opens the Google sign-in URL directly in the browser
- **THEN** the confirmation page shows the site navigation bar and a styled "Continue" button
