# Design

## Context

- `src/app/bingo/` is an installed Django app mounted at `/bingo/`. Its `models.py`, `views.py` and `urls.py` are empty, and it has no templates or tests.
- Django 6.0 on SQLite, served by gunicorn with **2 sync workers** (WSGI) behind Caddy. There is no Channels, no Redis and no background worker, and the default cache is per-process `LocMemCache`.
- Login is enforced per view (`@login_required`), not by middleware, so views without the decorator are public. Sessions use Django's default database backend, and an anonymous session row is written only when the session is modified.
- `templates/base.html` holds the family navbar (Bingo, Fercoins, Familia, Login/Logout) and loads Bootstrap 5 and Bootstrap Icons from a CDN. The only static file is `static/css/style.css`.
- In production, `SECURE_PROXY_SSL_HEADER` is set, so `request.build_absolute_uri()` returns `https://` URLs behind Caddy.

Motivation: see `proposal.md`. Required behaviour: `specs/bingo-rooms/spec.md` and `specs/bingo-game/spec.md`.

## Goals / Non-Goals

**Goals:**
- No new infrastructure: everything runs in the existing gunicorn/SQLite container, and nothing needs a background process or cron job.
- Correct with 2 workers and several browsers acting at once: no ball drawn twice, no double draws from a double tap, consistent claims and pauses.
- Game rules (card generation, claim checks, stage changes) are plain functions that can be tested without HTTP.

**Non-Goals:**
- Push updates (WebSockets, server-sent events).
- Generic multi-game abstractions or reuse by other apps.
- Translations: the bingo UI is written directly in Spanish.

## Decisions

### 1. Polling instead of push
Each page polls `GET /bingo/r/<code>/state/` every ~1.5 s and redraws from the JSON it gets back. The response is small (at most 90 balls, one card, a player list), it reads only from the database, and it is marked `never_cache`.
- *Alternative:* WebSockets with Channels and an ASGI server. Rejected: a new server process and probably Redis for a game where a ball comes out every few seconds.
- *Alternative:* server-sent events. Rejected: each open page would hold one of the 2 sync workers for its whole lifetime, so two phones would block the entire site.
- Load estimate: 30 players at about 0.7 requests per second each is about 20 short read requests per second, well within 2 workers on SQLite.

### 2. Anonymous identity in the Django session
The session holds `bingo_host` (ids of rooms this browser hosts) and `bingo_players` (room id to player id). It is written only when a visitor creates or joins a room, so polling never writes sessions.
- A removed player's row stays with `removed=True`. The browser still maps to it, so it gets the "you were removed" page and cannot rejoin (spec: *Host can remove a player*).
- *Alternative:* a separate signed cookie holding tokens. Rejected: the session already does this, and it is protected by `SESSION_COOKIE_SECURE`.
- Side effect: signing in or out on the main site flushes the session and loses the bingo identity. This is accepted (see Risks).

### 3. Data model
```
Room    code (unique), created_at, last_activity_at, auto_interval (seconds, null = off), auto_since
Game    room (FK), stage, drawn (JSON list, in draw order), pause_prize, pause_ends_at,
        version (int), created_at                    -- one current game per room
Player  room (FK), nickname, nickname_key (lowercased; unique per room), removed, joined_at
Card    game (FK), player (FK), grid (JSON 3x9, null for blanks), marks (JSON list),
        numbers_key (sorted numbers as text; unique per game)
Claim   game (FK), player (FK), prize ('linea' | 'bingo'), row (null for bingo), created_at
        -- valid claims only; unique (game, player, prize)
```
- `stage` is `waiting`, `linea`, `bingo` or `finished` (spec: *Game progress*). `pause_prize` and `pause_ends_at` are set during a pause.
- A **new game** deletes the previous `Game` (its cards and claims cascade), creates a new one in `waiting` and deals a card to every non-removed player. Players and the room stay.
- The `numbers_key` unique constraint guarantees distinct cards within a game (spec: *Cards in a game are different*). A collision triggers regeneration.
- Drawn balls are stored as a JSON list on `Game` instead of one row per ball. Every draw already rewrites the game row under the version check (decision 5), and the list keeps the state endpoint to one row read.

### 4. Game rules are pure functions in `bingo/rules.py`
`generate_card(rng)`, `valid_linea_row(grid, marks, drawn)`, `is_bingo(grid, marks, drawn)` and `settle(game, now)` take and return plain values, with no requests or database access.
- **Card generation:** start every column at 1 number and add the 6 remaining numbers to random columns, never more than 3 per column. Then place each column's numbers in rows: 3-number columns fill every row, and 1- and 2-number columns pick rows at random, retrying until every row has exactly 5. Finally sample each column's numbers from its range (1-9, 10-19, ..., 70-79, 80-90) and sort them top to bottom. This converges after a few retries, and tests check 1000 seeded cards against every rule.
- Randomness comes from `secrets.SystemRandom()` in production and a seeded `random.Random` in tests.

### 5. Concurrency: version check on `Game`
Every write that changes game state (draw, claim, continue, new game, auto setting) runs inside `transaction.atomic()`. It reads the game, calls `settle(now)`, computes the new state, and saves with `Game.objects.filter(pk=..., version=v).update(..., version=v + 1)`. If no row was updated, another request won the race: the view reloads and re-evaluates once, then answers with the current state.
- The transaction starts with a no-op `UPDATE` of the game row. This takes SQLite's write lock before reading, so concurrent actions wait for each other (busy timeout) instead of failing with "database is locked" when a read transaction tries to upgrade to a write. Mark requests do the same on the player's card. A burst test against gunicorn with 2 workers (20 simultaneous draws, 12 simultaneous claims) produced one ball and 12 shared winners, with no errors.
- **Draw** requests carry the number of balls the client has seen (`seen`). The server draws only if `len(drawn) == seen`. A double tap, two open host tabs, or the auto timer firing at the same moment as a manual tap produce one ball, not two.
- Marks live on `Card`, not on `Game`, so taps never conflict with draws. A mark request sets one number to marked or unmarked (it does not toggle), so a retried tap gives the same result.
- *Alternative:* `select_for_update`. Rejected: SQLite ignores row locks. Making every transaction `IMMEDIATE` through database `OPTIONS` would also work, but it changes every app's transactions for a bingo-only need.

### 6. Pauses end lazily, with no background timer
The first valid claim for the current prize sets `pause_prize` and `pause_ends_at = now + 10 s`. Later valid claims for the same prize during the pause add winners without extending it. **Continue** sets `pause_ends_at = now`.

`settle(game, now)` runs at the start of every state read and write. If a pause has ended, it closes the prize and moves the stage on (`linea` to `bingo`, `bingo` to `finished`). Reads return the settled state in their response but do not save it. The next write saves it under the version check from decision 5.
- Clients draw the countdown bar from a server-computed `pause_remaining_ms`, so a phone with a wrong clock still shows the right time.
- A claim for the current prize is accepted only while it is open: the stage matches and either there is no pause, or the pause is for this prize and has not ended. That gives the shared-prize rule (spec: *Shared prizes*), and no ball can be drawn during the pause.

### 7. Automatic drawing is driven by the host page
`Room.auto_interval` (one of 5, 8, 10, 15 or 20 s, or off) is saved on the server, so reloading the host screen keeps the setting. The state response includes `next_auto_draw_ms`, the time left until `max(last draw, end of last pause, moment auto was turned on) + interval` (`Room.auto_since` records the last one). The host page's JavaScript sends a normal draw request with `seen` when that time reaches zero. Closing the host screen stops automatic drawing, which matches the spec ("while the host screen is open").
- *Alternative:* the server draws when a poll arrives late enough. Rejected: any player's poll would then write to the game, which adds contention for no visible benefit.

### 8. Views, URLs and pages
```
GET  /bingo/                        start page: create room, enter a code
POST /bingo/new/                    create room -> host screen
POST /bingo/go/                     code form -> join page (or "not found")
GET  /bingo/r/<code>/host/          host screen (host only)
GET  /bingo/r/<code>/               join page: nickname form, or the player's card
POST /bingo/r/<code>/join/          join with a nickname
GET  /bingo/r/<code>/state/         JSON state (host view or player view)
POST /bingo/r/<code>/mark/          {number, marked}
POST /bingo/r/<code>/claim/         {prize}
POST /bingo/r/<code>/draw/          {seen}                 host only
POST /bingo/r/<code>/continue/                             host only
POST /bingo/r/<code>/auto/          {interval | off}       host only
POST /bingo/r/<code>/new-game/                             host only
POST /bingo/r/<code>/remove/<id>/                          host only
```
- Host-only endpoints return 403 to any other browser. Unknown or expired codes render the shared "Sala no encontrada o caducada" page with status 404.
- `templates/bingo/base.html` is a standalone layout (Bootstrap from the same CDN, `lang="es"`, no family navbar). The host screen uses large type for a TV, and the player page is a full-width card for a phone.
- One static script, `static/bingo/bingo.js`, handles polling, rendering and POSTs with the CSRF token. The pages render fully on the server at first load, then update in place with plain JavaScript and no framework.
- During a pause, the host screen shows a full-screen overlay. Player pages show a top banner instead, so players can still mark numbers and make a shared claim.
- Nicknames are inserted with Django's auto-escaping in templates and with `textContent` in JavaScript, never `innerHTML` (spec: *Nickname rules*).

### 9. The QR code is generated on the server with `segno`
The host view builds the join URL with `request.build_absolute_uri(...)` and renders it as inline SVG with `segno`. It's pure Python with no native dependencies and adds about 100 KB to the image.
- *Alternative:* a JavaScript QR library from a CDN. Rejected: it moves logic to the client, and a test cannot check what the QR encodes.

### 10. Limits and cleanup inside the application
- Settings with defaults, overridable in `settings.py` and in tests: `BINGO_ROOM_IDLE_HOURS = 12`, `BINGO_MAX_ROOMS = 50`, `BINGO_MAX_PLAYERS = 30`. The nickname length (20) and auto intervals are constants.
- `last_activity_at` is updated by joins, marks, claims and host actions, but not by polling. That way an abandoned TV tab doesn't keep a room alive forever.
- Room lookups filter out rooms past the idle cutoff, so an expired room is "not found" even before it is deleted. **Room creation** first deletes expired rooms (cascading to everything else) and calls `SessionStore.clear_expired()`, then checks the room cap. No cron job is needed, and `deploy.sh`/`backup.sh` are unchanged.
- Codes: 5 characters from `ABCDEFGHJKMNPQRSTUVWXYZ23456789` (no `0 O 1 I L`) generated with `secrets`, retried on collision. That gives about 28 million combinations, which is hard to guess for rooms that only live for hours.

### 11. Removing a player
Removal sets `Player.removed = True` and deletes their card and claims. The stage does not roll back: if they were the only winner of a prize that has already closed, the prize stays closed and no winner is shown for it. Their next poll returns `removed: true`, and the page shows the removed message.

## Risks / Trade-offs

- [Rooms are public: anyone with the URL can join a family game] → codes are hard to guess, rooms expire after 12 h idle, the host can remove a player, and a removed browser cannot rejoin from the same session.
- [A determined abuser can create rooms or rejoin from a fresh private window] → the room and player caps bound the damage. Per-IP rate limiting is a deliberate follow-up if this ever happens.
- [Guest sessions add rows to `django_session`] → expired rows are cleared whenever a room is created. Sessions last 2 weeks (Django's default), so the table stays small at this scale.
- [Signing in or out on the main site loses the bingo identity in that browser] → rare during a game. The player rejoins with another nickname, or the host continues with a new room.
- [Polling uses more requests than push] → about 20 req/s at 30 players is fine for 2 workers. The interval can be raised if needed.
- [The host screen going to sleep stops automatic drawing] → this is visible (balls stop) and tapping Draw always works. The host page can keep the screen awake with the Wake Lock API where the browser supports it.
- [SQLite "database is locked" under bursts of writes] → writes are tiny and short. Django's SQLite timeout absorbs short contention, and version conflicts are retried once.
- [The first public pages that write data] → they only touch bingo tables, CSRF stays on for every POST, and the protected apps are unchanged (a test checks `/fercoins/` still redirects anonymous visitors).

## Migration Plan

1. Merge and run `./deploy.sh`. The entrypoint's `migrate` creates the bingo tables. Existing tables are untouched, and `uv sync` in the image build installs `segno`.
2. Smoke test in production: create a room on the TV or laptop, join from two phones by QR, play to línea and bingo, and start a new game.
3. Rollback: redeploy the previous commit. The bingo tables can stay, or be dropped with `migrate bingo zero` before rolling back.

## Open Questions

- Exact limits (idle hours, room cap, player cap) and the set of auto-draw intervals. The defaults above are starting points and are easy to change in settings.
- Whether the host screen should also play a sound or read the number aloud (Web Speech API) on each draw. This is a pure front-end addition that doesn't change the specs.
