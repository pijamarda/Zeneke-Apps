# runtime-configuration Specification

## Purpose

Defines how the application takes its configuration from the environment and what it guarantees in each mode. Development stays convenient, and production is safe by default on any host that terminates HTTPS in front of it.

## Requirements

### Requirement: Production mode is the default
The application SHALL run in production mode unless the `DEBUG` setting is explicitly `true` (case-insensitive). A missing, empty or any other value SHALL mean production mode.

#### Scenario: DEBUG not set
- **WHEN** the application starts with no `DEBUG` variable and no `.env` file
- **THEN** it runs in production mode (no debug error pages)

#### Scenario: DEBUG explicitly enabled
- **WHEN** the application starts with `DEBUG=true` or `DEBUG=True`
- **THEN** it runs in development mode

### Requirement: Local environment file is loaded
On startup the application SHALL load variables from `src/.env` if the file exists. A variable already set in the process environment SHALL take precedence over the same variable in the file. A missing file SHALL NOT be an error.

#### Scenario: Local run without Docker
- **WHEN** a developer runs `manage.py runserver` with a `src/.env` containing `DEBUG=true` and no exported variables
- **THEN** the application runs in development mode

#### Scenario: Environment wins over the file
- **WHEN** `src/.env` contains `DEBUG=true` and the process environment has `DEBUG=false`
- **THEN** the application runs in production mode

### Requirement: Production refuses to start without a secure secret key
In production mode the application SHALL refuse to start, with an error naming `SECRET_KEY`, when the key is missing, shorter than 50 characters, has fewer than 5 unique characters, or starts with `django-insecure-`. Development mode SHALL start without a key.

#### Scenario: Missing key
- **WHEN** the application starts in production mode without `SECRET_KEY`
- **THEN** startup fails with an error message that mentions `SECRET_KEY`

#### Scenario: The development fallback key is rejected
- **WHEN** the application starts in production mode with a key starting with `django-insecure-`
- **THEN** startup fails with an error message that mentions `SECRET_KEY`

#### Scenario: Development needs no key
- **WHEN** the application starts in development mode without `SECRET_KEY`
- **THEN** it starts normally

### Requirement: Production refuses to start without allowed hosts
In production mode the application SHALL refuse to start, with an error naming `ALLOWED_HOSTS`, when `ALLOWED_HOSTS` is missing or empty. `ALLOWED_HOSTS` SHALL be a comma-separated list; blank entries and surrounding spaces SHALL be ignored.

#### Scenario: Missing hosts
- **WHEN** the application starts in production mode with a valid key but no `ALLOWED_HOSTS`
- **THEN** startup fails with an error message that mentions `ALLOWED_HOSTS`

#### Scenario: List parsing
- **WHEN** `ALLOWED_HOSTS` is `zeneke.example.com, www.zeneke.example.com,`
- **THEN** exactly those two hosts are accepted

### Requirement: Static assets are served in production
In production mode the application itself SHALL serve its static assets (such as `/static/css/style.css`) with a 200 response, without relying on a separate web server.

#### Scenario: Stylesheet in production
- **WHEN** a browser requests `/static/css/style.css` from the production container
- **THEN** the response is 200 with the stylesheet content

### Requirement: HTTPS is detected behind a proxy
In production mode the application SHALL treat a request as HTTPS when the proxy sends `X-Forwarded-Proto: https`. Absolute URLs it builds, including OAuth callback URLs, SHALL then use `https://`.

#### Scenario: OAuth callback behind the proxy
- **WHEN** a parent starts Google sign-in through a proxy that sends `X-Forwarded-Proto: https`
- **THEN** the callback URL sent to Google starts with `https://`

### Requirement: Plain HTTP is redirected in production
In production mode the application SHALL redirect any request not detected as HTTPS to the same URL over HTTPS. It SHALL send a `Strict-Transport-Security` header on HTTPS responses, valid for 3600 seconds by default and configurable through `SECURE_HSTS_SECONDS`.

#### Scenario: Plain HTTP request
- **WHEN** a request reaches the application in production mode without `X-Forwarded-Proto: https`
- **THEN** the response is a permanent redirect to the `https://` URL

#### Scenario: Default HSTS
- **WHEN** an HTTPS request is served in production mode with no `SECURE_HSTS_SECONDS` set
- **THEN** the response carries `Strict-Transport-Security` with `max-age=3600`

#### Scenario: Configured HSTS
- **WHEN** `SECURE_HSTS_SECONDS=31536000` is set
- **THEN** HTTPS responses carry `max-age=31536000`

### Requirement: Cookies are HTTPS-only in production
In production mode the session and CSRF cookies SHALL be marked `Secure`. In development mode they SHALL NOT be, so that plain `http://localhost` keeps working.

#### Scenario: Production cookie
- **WHEN** a kid signs in over HTTPS in production mode
- **THEN** the session cookie has the `Secure` attribute

#### Scenario: Development cookie
- **WHEN** a kid signs in on `http://localhost:8000` in development mode
- **THEN** sign-in works and the session cookie is not marked `Secure`

### Requirement: Trusted origins follow allowed hosts
Form submissions over HTTPS from any host in `ALLOWED_HOSTS` SHALL pass CSRF origin checking without extra configuration. A `CSRF_TRUSTED_ORIGINS` variable (comma-separated full origins) SHALL, when set, replace the derived list.

#### Scenario: Form post on the production domain
- **WHEN** a kid submits the PIN form on `https://zeneke.example.com` and `ALLOWED_HOSTS=zeneke.example.com`
- **THEN** the request is not rejected by CSRF origin checking

#### Scenario: Explicit override
- **WHEN** `CSRF_TRUSTED_ORIGINS=https://other.example.com` is set
- **THEN** only `https://other.example.com` is trusted as a cross-origin source

### Requirement: Data location is configurable
The SQLite database SHALL be stored in the directory given by `DATA_DIR`, which SHALL be created if missing. When `DATA_DIR` is not set, the database SHALL stay at its current location, `src/app/db.sqlite3`.

#### Scenario: Volume-backed data directory
- **WHEN** the application starts with `DATA_DIR=/data` and runs its migrations
- **THEN** the database file is `/data/db.sqlite3`

#### Scenario: Default location unchanged
- **WHEN** the application starts without `DATA_DIR`
- **THEN** it uses the existing `src/app/db.sqlite3`
