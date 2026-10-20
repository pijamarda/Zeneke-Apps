# Proposal

## Why

Bingo is listed as "planned" on the home page and in the README, but `/bingo/` is an empty Django app with no URLs. The family wants to play bingo together on game nights, including with guests who have no Zeneke account. Everyone should join from their phone by scanning a QR code on a shared screen, with no sign-in.

## What Changes

- Add a **multiplayer Spanish 90-ball bingo** at `/bingo/`. Each card has 3 rows by 9 columns and 15 numbers. **Línea** is the first prize and **bingo** the second, which ends the game.
- **Anyone can create a room**, with no login. The browser that creates it becomes the **host**. The host screen (a TV or laptop) shows a short room code, a **QR code** to join, the players, the last ball and every ball drawn so far.
- **Anyone can join** by scanning the QR or entering the code, then choosing a nickname. Each player gets **one card**. Players can **join after the game has started** and catch up by marking the balls already drawn.
- The **host draws balls** by tapping a button, or turns on **automatic drawing** at a fixed interval.
- **Players mark numbers themselves**: they can mark any number on their card, and marks are saved on the server. A player **claims** línea or bingo, and the **server checks the claim**: it is valid only if every number in the row (línea) or on the card (bingo) is both marked and drawn. A claim made late is still accepted while that prize is open.
- A **valid claim pauses the game** for a short reveal. A ~10 second countdown bar is shown, and the host can tap **Continue** earlier. Every valid claim for the same prize made before the next ball wins, so prizes can be **shared**. An invalid claim only shows a message to that player.
- The host can start a **new game in the same room**. The code, QR and players stay, and everyone gets a new card.
- **Minimal protection** for public use: rooms expire after a period of inactivity, there are caps on active rooms and on players per room, nicknames are length-limited, and the host can remove a player.
- Bingo pages use a **phone-friendly layout in Spanish**, without the family navigation or the login button.
- The family apps (Fercoins, family management, kid sign-in) are unchanged and stay protected by login.

Out of scope: several cards per player, bots or a solo simulator, taking over hosting from another device, WebSockets, per-IP rate limiting.

## Capabilities

### New Capabilities
- `bingo-rooms`: Public rooms. Creating one without a login, the host role, joining by QR code or room code with a nickname, the player identity kept in the browser session, removing players, new games in the same room, and the limits for public use (expiry, caps, nickname rules).
- `bingo-game`: Playing one game. Generating Spanish 90-ball cards, drawing balls (manually and automatically), marking numbers, checking línea and bingo claims, the pause after a valid claim, shared prizes, and how players and the host see the game update.

### Modified Capabilities
<!-- None. Existing capabilities keep their requirements: bingo pages are new public pages, and the protected family pages are unaffected. -->

## Impact

- **Code**: `src/app/bingo/` gets models (room, player, card, drawn balls, claims) with a migration, views, URLs, card generation and claim checking, and tests. New templates under `templates/bingo/` with a minimal phone layout, plus some JavaScript for polling and the host controls.
- **Dependencies**: one small pure-Python library to render the QR code as SVG on the server (`segno`).
- **Data**: new tables only. Expired rooms are deleted by the application itself. Guest visits add rows to Django's session table; the application clears expired sessions, so no new cron job or deploy change is needed.
- **Load**: phones and the host screen poll a small JSON endpoint every 1-2 seconds. This fits the current gunicorn/SQLite setup at family scale.
- **Security**: these are the first public pages that write to the database. Their reach is limited to bingo tables, and the limits above restrict abuse. The other apps' login checks are unchanged.
- **Docs**: the README moves Bingo from "planned" to "live" and describes the public access.
