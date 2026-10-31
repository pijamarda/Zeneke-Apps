# Design

## Context

See proposal.md for the motivation. Today's relevant setup:

- `Card` belongs to a `game` and a `player`, with two constraints: `bingo_unique_card_per_game` (game + `numbers_key`) and `bingo_one_card_per_player` (game + player). `deal_card(game, player)` returns the existing card or creates a new distinct one, retrying on `IntegrityError`.
- `Claim` has `game`, `player`, `prize` and `row`, and is unique per (game, player, prize). `Claim.winning_numbers(card)` builds the displayed numbers from the one card.
- `views.mark` reads `player.cards.first()`. `game.claim` reads `Card.objects.get(game=game, player=player)`. `state_payload` builds `cards = {player_id: card}` and returns `me.card` / `me.marks`.
- `bingo.js` keeps `pendingMarks` keyed by number, builds a single `#card` table, and rebuilds it when `game_id` changes.
- Game writes take SQLite's write lock first (`Game.objects.filter(room=room).update(version=F('version'))` inside `update_game`), so concurrent actions are serialised.
- Rooms expire after 12 hours of inactivity, so live data is short-lived.

## Goals / Non-Goals

**Goals:**
- One model shape for 1 and 2 cards (a card position), with no separate code path for one-card players.
- Keep the existing rules functions (`valid_linea_row`, `is_bingo`) unchanged. They already work on one grid at a time.

**Non-Goals:**
- Supporting more than 2 cards. The limit is a constant, but the UI and labels assume 1 or 2.
- Keeping the old state JSON fields (`me.card`, `me.marks`). Only our own script reads them, and it ships with the server.

## Decisions

### 1. Data model: card position and a count on the player
- `Player.card_count`: `PositiveSmallIntegerField(default=1)`, either 1 or 2 (`MAX_CARDS = 2` in `models.py`).
- `Card.position`: `PositiveSmallIntegerField(default=0)`, 0 or 1. Replace `bingo_one_card_per_player` with `bingo_one_card_per_position` on (game, player, position). Keep `bingo_unique_card_per_game` as it is. It already makes both of a player's cards differ (spec: "Cards in a game are different").
- `Claim.position`: `PositiveSmallIntegerField(default=0)`, the card that won. The claim stays unique per (game, player, prize), so a player wins a prize once.
- One migration. Defaults of 1 and 0 make every existing player, card and claim valid as they are.

- *Alternative: a `Claim.card` foreign key*. Rejected: a position is enough to find the card, it survives a new deal for the same position, and it needs no nullable FK for old rows.

### 2. Dealing: `deal_cards(game, player)`
Replace `deal_card` with `deal_cards(game, player)`. It creates the missing positions `0..card_count-1`, using the same retry loop per position, and deletes cards at positions `>= card_count`. It is idempotent, so joining, the new game and the count change all call it.

### 3. Changing the count: `POST r/<code>/cards/` with `count=1|2`
`game.set_card_count(room, player, count)` runs in a transaction that first takes the game write lock, like `update_game` does. It reads the settled state and raises `Refused('started')` ("La partida ya ha empezado. Podrás cambiar los cartones en la próxima partida.") if any ball has been drawn. Otherwise it saves `player.card_count` and calls `deal_cards`. Because `draw` takes the same lock, a count change and the first draw can't overlap. Responds like `claim`: `{ok, state}` or `409` with the message. Any value other than 1 or 2 gets a `400`.

The join form posts `cards`. `2` means 2 cards, and anything else means 1. `card_count` is set before `deal_cards` in the same transaction as creating the player.

### 4. Marking by card
`mark` takes a `card` parameter (position, default `0`). It looks up `player.cards.get(position=...)` for the current game, and replies "Ese número no está en tu cartón." if there is no such card or the number isn't on it. The rest (lock, finished check, saving marks) stays the same.

### 5. Claims check each card
`game.claim` loads the player's cards ordered by position and checks each one with the existing rule functions. The first card that wins is recorded as `Claim.position`, along with `row` for línea. If none wins, the claim is refused with the existing messages. A row is checked against the marks of its own card only, so numbers can't be combined across cards.

### 6. State JSON
- `me.cards`: `[{"position": 0, "grid": [...], "marks": [...]}, ...]` ordered by position. `me.card_count`: the player's choice. `me.card` and `me.marks` are removed.
- `_winners` looks up the card by `(player_id, claim.position)`.
- Host `players` items gain `cards` (the count) for the "×2" label.

### 7. Player page
- `player.html` renders a `.bingo-cards` container with one `<table class="bingo-card" data-card="N">` per card, each preceded by a "Cartón N" label when there are two.
- A "1 cartón / 2 cartones" segmented control (`#card-count`) is shown only while `stage === 'waiting'`. Tapping it posts to the cards endpoint and renders the returned state.
- `bingo.js`: `pendingMarks` is keyed by `position + ':' + number`. Cell clicks read the position from the closest `table[data-card]`. The cards are rebuilt when `game_id` changes or the number of cards changes. The "¡Nueva partida!" message becomes "Tienes cartones nuevos." when there are two.
- With two cards, `.bingo-cards.two .cell` uses a smaller height (about 2.6rem instead of 3.2rem) so both cards and the claim buttons fit on a typical phone screen with little or no scrolling.

### 8. Join form and host list
- `join.html` adds a two-option `btn-check` radio group ("1 cartón" checked, "2 cartones") above the submit button. Its value is kept when the form is shown again with an error.
- The host list shows `nickname ×2` from `players[].cards`. The server-rendered list in `host.html` matches it.

## Risks / Trade-offs

- [Two cards make the phone page taller] → Compact cells for two cards (decision 7). The claim buttons stay right after the cards.
- [Marks are per card, so a number on both cards needs two taps] → This is the chosen behaviour, the same as with paper cards, and is spelled out in the spec. Auto-marking stays out.
- [Rolling back the migration fails while any player has a second card, because of the old one-card-per-player constraint] → Before rolling back, delete cards with `position = 1` from the Django shell, or wait for rooms to expire. Spelled out in the Migration Plan.
- [More cards per game make a duplicate deal more likely] → There are millions of possible cards, and the cap is 2 × the player cap. The existing 50-try retry stays.

## Migration Plan

Deploy with `./deploy.sh`. The container entrypoint runs the migration. The new fields have defaults, so existing rooms keep working with one card each. To roll back: first run `uv run python manage.py shell -c "from bingo.models import Card; Card.objects.filter(position=1).delete()"` from `src/app` (or the equivalent in the container), then migrate `bingo` back to `0001` and redeploy the previous commit.
