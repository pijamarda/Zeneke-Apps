# Spec Delta

## MODIFIED Requirements

### Requirement: Plain HTTP is redirected in production
In production mode the application SHALL redirect any request not detected as HTTPS to the same URL over HTTPS, except the health-check endpoint `/healthz` (see the `deployment` capability). It SHALL send a `Strict-Transport-Security` header on HTTPS responses, valid for 3600 seconds by default and configurable through `SECURE_HSTS_SECONDS`.

#### Scenario: Plain HTTP request
- **WHEN** a request reaches the application in production mode without `X-Forwarded-Proto: https`
- **THEN** the response is a permanent redirect to the `https://` URL

#### Scenario: Health check is not redirected
- **WHEN** a request for `/healthz` reaches the application in production mode without `X-Forwarded-Proto: https`
- **THEN** the response is 200, not a redirect

#### Scenario: Default HSTS
- **WHEN** an HTTPS request is served in production mode with no `SECURE_HSTS_SECONDS` set
- **THEN** the response carries `Strict-Transport-Security` with `max-age=3600`

#### Scenario: Configured HSTS
- **WHEN** `SECURE_HSTS_SECONDS=31536000` is set
- **THEN** HTTPS responses carry `max-age=31536000`
