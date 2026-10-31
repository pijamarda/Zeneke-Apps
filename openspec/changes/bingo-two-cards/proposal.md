# Proposal

## Why

In a real bingo hall people often buy two cartones to play more numbers at once. Today every bingo player gets exactly one card, and players have asked to play with two.

## What Changes

- **Choose 1 or 2 cartones when joining:** the join form gets a choice between "1 cartón" and "2 cartones", with 1 selected by default.
- **Change it while the game hasn't started:** while no ball has been drawn, a player can switch between 1 and 2 cartones from their room page. Adding a second card deals a new card. Going back to one removes the second card.
- **The choice is kept for new games:** when the host starts a new game, each player gets as many new cards as they had chosen.
- **Two cards on the player page:** the cards are shown one below the other, labelled "Cartón 1" and "Cartón 2". Each number is marked on its own card, so a number that is on both cards has to be marked on each card separately.
- **One claim button for both cards:** "¡Línea!" and "¡Bingo!" check all of the player's cards. A claim is valid if any one card meets the rule. A player still wins each prize at most once, even if both cards would win. The winner display shows the numbers of the card that won.
- **Every card in a game is different:** this now covers both cards of the same player and the cards of all other players.
- **Host screen:** the player list shows "×2" next to players who have two cards.

Out of scope: more than 2 cartones, a host setting that limits the number of cards, and línea or bingo made from numbers spread across two cards (each card is checked on its own).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `bingo-game`: cards are per player and per position (one or two per player), they must all differ within a game, marks are per card, and línea and bingo claims check each of the player's cards.
- `bingo-rooms`: the join form asks for the number of cartones, the room page lets a player change it before the game starts, new games keep it, and the host's player list shows it.

## Impact

- `src/app/bingo/models.py`: `Player` stores the number of cards, and `Card` gets a position (0 or 1) in place of the one-card-per-player constraint. `Claim` records which card won. A new migration covers these changes, and existing cards become position 0.
- `src/app/bingo/game.py` and `views.py`: dealing cards, joining, the new change-card-count action, marking by card, claims against each card, and the state JSON (`me.cards` replaces `me.card` / `me.marks`).
- `src/app/bingo/urls.py`: a new `r/<code>/cards/` endpoint.
- Templates `join.html`, `player.html` and `host.html`, plus `static/bingo/bingo.js` and `bingo.css`: the card choice, rendering two cards, marking by card, and "×2" in the host list.
- `src/app/bingo/tests.py`: update tests that read `me.card` / `me.marks`, and add tests for two cards.
- No new dependencies or settings.
