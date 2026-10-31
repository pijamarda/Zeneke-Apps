# Tasks

Server tests run from `src/app` with `uv run python manage.py test bingo`. Check the browser parts with `uv run python manage.py runserver` (also from `src/app`): a desktop window for the host and a phone-sized window or device emulation for players.

## 1. Data model and dealing

- [ ] 1.1 Add `Player.card_count`, `Card.position` and `Claim.position`. Replace the `bingo_one_card_per_player` constraint with `bingo_one_card_per_position` on (game, player, position), and add `MAX_CARDS = 2` (design.md decision 1). Create the migration with `uv run python manage.py makemigrations bingo`. Verify: `uv run python manage.py migrate` applies it on a database with existing rooms, and `uv run python manage.py makemigrations --check bingo` reports no changes.
- [ ] 1.2 Replace `deal_card` with `deal_cards(game, player)`: it creates the missing positions and deletes extra ones (decision 2), and is used by `join` and `game.new_game`. Add tests: a player with `card_count=2` gets two cards with different `numbers_key`, calling it twice creates nothing new, lowering the count to 1 deletes position 1, and a new game deals 2 new cards to a 2-card player. Verify: `uv run python manage.py test bingo` passes.

## 2. Server behaviour

- [ ] 2.1 Join form: read `cards` (`2` means 2, anything else 1), set `card_count` before dealing, and add the "1 cartón / 2 cartones" radio group to `join.html`, which keeps its value when the form is shown again with an error (decision 8). Add tests for joining with 2 cards, joining with no `cards` field (1 card), and joining with 2 after 20 balls are drawn. Verify: tests pass.
- [ ] 2.2 State JSON: `me.cards`, `me.card_count`, `players[].cards`, and `_winners` looking up `(player_id, position)` (decision 6). Update existing tests that read `me.card` / `me.marks`. Verify: tests pass.
- [ ] 2.3 Marking by card: the `card` parameter, defaulting to 0, with the "not on your card" reply for an unknown position (decision 4). Add tests: marking 47 on card 1 leaves card 0 unmarked even when 47 is on both cards; position 5 is refused; another player's card can't be changed. Verify: tests pass.
- [ ] 2.4 Claims against each card, recording `Claim.position` (decision 5). Add tests: línea on card 1 only is valid and the winner's numbers are that card's row; a row completed only by combining marks from both cards is invalid; bingo on card 1 is valid; both cards with a línea give one winner entry. Verify: tests pass.
- [ ] 2.5 `POST r/<code>/cards/` and `game.set_card_count` with the lock and the `started` refusal (decision 3). Add tests: 1→2 before the start keeps card 0 and its marks and adds a card; 2→1 removes card 1; the change is refused with status 409 after the first ball and the cards don't change; a bad value gets 400; a stranger or removed player gets 403; after a new game the change is allowed again. Verify: tests pass.

## 3. Pages

- [ ] 3.1 `player.html` and `bingo.js`: render one or two cards with "Cartón N" labels, `pendingMarks` keyed by position, marking posts `card`, rebuild on game or count change, and the `#card-count` control shown only while waiting (decision 7). Add a server test that the player page renders two `data-card` tables and both labels for a 2-card player, and one table with no label for a 1-card player. Verify in the browser: join with 2 cartones, mark the same number on one card only, reload and the marks stay; switch 2→1→2 before the first ball; after the first ball the control is hidden; a línea on "Cartón 2" shows that row in the pause; a new game shows two new cards without a reload; no console errors.
- [ ] 3.2 `bingo.css`: compact cells and labels for two cards (decision 7). Verify in device emulation at 390×844 that both cards and the claim buttons fit with little or no scrolling, and that a 1-card player looks the same as before.
- [ ] 3.3 Host list shows `×2` from `players[].cards`, both server-rendered in `host.html` and in `renderPlayers()` (decision 8). Add a test that the host state has `cards: 2` for a 2-card player. Verify in the browser: the label appears when a 2-card player joins and changes when they switch before the start.

## 4. Integration check

- [ ] 4.1 Run `uv run python manage.py test bingo` and play a full game in the browser with a host, one 1-card player and one 2-card player: switching counts before the start, a línea on the second card, a shared línea, a bingo, then a new game. Confirm the behaviour matches every scenario in `specs/bingo-game/spec.md` and `specs/bingo-rooms/spec.md`, with no errors in the browser console.

## Workflow follow-up

- Deploy with `./deploy.sh`, then archive the change, syncing the `bingo-game` and `bingo-rooms` deltas into the main specs.
