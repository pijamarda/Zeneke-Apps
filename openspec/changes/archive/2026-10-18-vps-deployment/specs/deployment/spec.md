# Spec Delta

## Purpose

Defines how Zeneke runs and is operated in production on a server behind a reverse proxy: how its health is checked, how it runs and keeps its data, who can reach it, and how deploys and backups behave.

## ADDED Requirements

### Requirement: Health check endpoint
The application SHALL answer `GET /healthz` with status 200 and the body `ok`. It SHALL do so in any mode, over plain HTTP, and whatever the `Host` header, without redirecting and without querying the database.

#### Scenario: Plain HTTP probe in production
- **WHEN** a request for `/healthz` reaches the application in production mode without `X-Forwarded-Proto: https`
- **THEN** the response is 200 with body `ok`, not a redirect

#### Scenario: Unknown host
- **WHEN** `/healthz` is requested with `Host: 127.0.0.1:8000`, which is not in `ALLOWED_HOSTS`
- **THEN** the response is 200 with body `ok`

#### Scenario: Database unavailable
- **WHEN** `/healthz` is requested while the database cannot be opened
- **THEN** the response is still 200 with body `ok`

#### Scenario: Other paths unaffected
- **WHEN** `/healthz/extra` or `/` is requested over plain HTTP in production mode
- **THEN** the normal HTTPS redirect applies

### Requirement: Application runs as a non-root user
The production container SHALL run the application process as the unprivileged user `zeneke` with uid 1000, never as root.

#### Scenario: Process identity
- **WHEN** the production container is running
- **THEN** the gunicorn processes run as uid 1000

### Requirement: Data persists across redeploys
In production the database SHALL live on a persistent volume mounted at the data directory. Rebuilding or recreating the container SHALL NOT lose data.

#### Scenario: Redeploy keeps data
- **WHEN** a kid account exists and the application is redeployed with a rebuilt image
- **THEN** the kid account still exists after the deploy

### Requirement: Production is reachable only through the proxy
The production container SHALL publish its port only on the server's loopback interface, at `127.0.0.1` on a configurable port defaulting to `8010`. It SHALL NOT be reachable directly from other machines.

#### Scenario: Loopback only
- **WHEN** the production container is running
- **THEN** its port is bound to `127.0.0.1:8010` (or the configured port) and not to `0.0.0.0`

### Requirement: Automatic restart
The production container SHALL restart automatically after it crashes and after the server reboots, unless an operator stopped it on purpose.

#### Scenario: Server reboot
- **WHEN** the server reboots with Docker enabled
- **THEN** the application is running again without manual action

### Requirement: One-command deploy
Running `./deploy.sh` on the server SHALL update the code to the latest `origin/main`, back up the database, rebuild and start the application, and wait until it reports healthy. It SHALL then print the deployed commit and exit with status 0. It SHALL need no interactive input.

#### Scenario: New commit on main
- **WHEN** a new commit was pushed to `main` and an operator runs `./deploy.sh`
- **THEN** the server runs that commit, the application is healthy, and the script prints the commit and exits 0

#### Scenario: Nothing new
- **WHEN** `./deploy.sh` runs and `main` has no new commits
- **THEN** the script still ensures the application is up and healthy and exits 0

### Requirement: Failed deploys are reported
If the application does not become healthy within the timeout (120 seconds by default), `./deploy.sh` SHALL exit with a non-zero status and show the application's recent log output. A backup taken before the failed deploy SHALL remain available.

#### Scenario: Application cannot start
- **WHEN** a deploy is run with a configuration that keeps the application from starting (for example an invalid `SECRET_KEY`)
- **THEN** `./deploy.sh` exits non-zero and prints the application's recent logs

#### Scenario: Recovery after a failed deploy
- **WHEN** a deploy has failed and the application is restarting in a loop, and the configuration is then fixed and `./deploy.sh` is run again
- **THEN** the backup step succeeds, the application becomes healthy, and the script exits 0

### Requirement: Deploy refuses unsafe states
`./deploy.sh` SHALL stop with a non-zero status and a clear message, before changing anything, when: `.env.prod` is missing or readable by other users; the checkout is not on branch `main` or has uncommitted changes; `main` cannot be fast-forwarded to `origin/main`; Docker Compose lacks `up --wait`; or another deploy is already running.

#### Scenario: Missing secrets file
- **WHEN** `./deploy.sh` runs without `.env.prod`
- **THEN** it exits non-zero, explains that `.env.prod` must be created from `.env.prod.example`, and changes nothing

#### Scenario: Secrets file too open
- **WHEN** `.env.prod` is readable by group or others
- **THEN** it exits non-zero and suggests `chmod 600 .env.prod`

#### Scenario: Local edits on the server
- **WHEN** the server checkout has uncommitted changes
- **THEN** it exits non-zero without pulling or rebuilding

#### Scenario: Concurrent deploy
- **WHEN** `./deploy.sh` is started while another run is still in progress
- **THEN** the second run exits non-zero immediately, saying a deploy is already running

### Requirement: Database backups
Running `./backup.sh` SHALL write a consistent copy of the live database, taken with SQLite's online backup while the application keeps running, to `backups/db-<YYYYmmdd-HHMMSS>.sqlite3`. It SHALL keep only the most recent 14 backups by default, configurable through `BACKUP_KEEP`. `./deploy.sh` SHALL run it before rebuilding. A backup SHALL never overwrite an existing one. When the application has never been started (first deploy), it SHALL skip with a message instead of failing.

#### Scenario: Backup while running
- **WHEN** `./backup.sh` runs while the application is serving requests
- **THEN** a new `backups/db-<timestamp>.sqlite3` exists and opens as a valid SQLite database containing the current data

#### Scenario: Retention
- **WHEN** 14 backups exist and `./backup.sh` runs with the default retention
- **THEN** the new backup is kept, the oldest one is deleted, and 14 backups remain

#### Scenario: Backup while the app is down
- **WHEN** the application holds data but is stopped or restarting in a loop, and `./backup.sh` runs
- **THEN** a new backup is written that contains that data

#### Scenario: Two backups in the same second
- **WHEN** `./backup.sh` runs twice within the same second
- **THEN** two distinct backup files exist and neither overwrote the other

#### Scenario: First deploy
- **WHEN** `./deploy.sh` runs and the application has never been started
- **THEN** the backup step reports that there is nothing to back up and the deploy continues
