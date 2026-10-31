# Spec Delta

## ADDED Requirements

### Requirement: One or two cards per player
Each player SHALL play with either 1 or 2 cards in a game, as they chose. The player's page SHALL show their cards one below the other, labelled "Cartón 1" and "Cartón 2" when there are two. No player SHALL have more than 2 cards.

#### Scenario: Player with two cards
- **WHEN** a player who chose 2 cartones opens their room page
- **THEN** they see two complete cards, labelled "Cartón 1" and "Cartón 2"

#### Scenario: Player with one card
- **WHEN** a player who chose 1 cartón opens their room page
- **THEN** they see a single card, with no card label

## MODIFIED Requirements

### Requirement: Cards in a game are different
Within one game, no two cards SHALL have the same set of 15 numbers. This SHALL apply both to the cards of different players and to the two cards of the same player.

#### Scenario: Two players
- **WHEN** two players are in the same game
- **THEN** their cards do not contain exactly the same 15 numbers

#### Scenario: Two cards of one player
- **WHEN** a player has 2 cards in a game
- **THEN** the two cards do not contain exactly the same 15 numbers

### Requirement: Players mark their own card
A player SHALL be able to mark and unmark any number on any of their own cards, whether it has been drawn or not, until the game finishes. Marks SHALL belong to one card: marking a number on one card SHALL NOT mark it on the player's other card. Numbers SHALL NOT be marked automatically. Marks SHALL be saved by the server, and a player SHALL NOT be able to change marks on another player's card.

#### Scenario: Mark a drawn number
- **WHEN** 47 has been drawn and a player taps 47 on their card
- **THEN** 47 is shown as marked, and it is still marked after a reload

#### Scenario: Mark a number not drawn yet
- **WHEN** a player taps a number on their card that has not been drawn
- **THEN** the number is shown as marked

#### Scenario: Unmark
- **WHEN** a player taps a marked number again
- **THEN** it is no longer marked

#### Scenario: Drawn numbers are not marked for the player
- **WHEN** a number on a player's card is drawn and the player does not tap it
- **THEN** it stays unmarked on their card

#### Scenario: Same number on both cards
- **WHEN** 47 is on both of a player's cards and the player taps 47 on "Cartón 1"
- **THEN** 47 is marked on "Cartón 1" and stays unmarked on "Cartón 2"

### Requirement: Claiming línea
While the game is playing for línea, a player SHALL be able to claim línea. The claim SHALL be valid only if at least one row of one of the player's cards has all 5 numbers both marked on that card and drawn. Each card SHALL be checked on its own. Numbers drawn earlier in the game SHALL count, so a late claim is valid as long as línea is still open.

#### Scenario: Valid línea
- **WHEN** all 5 numbers of a player's second row have been drawn and the player has marked all 5, then claims línea
- **THEN** the claim is valid and the player is awarded línea

#### Scenario: Línea on the second card
- **WHEN** a player has 2 cards, no row of "Cartón 1" is complete, and a row of "Cartón 2" is fully drawn and marked, and the player claims línea
- **THEN** the claim is valid, and the winning numbers shown are that row of "Cartón 2"

#### Scenario: Row split across two cards
- **WHEN** a player's marked and drawn numbers would only complete a row by combining numbers from both of their cards, and the player claims línea
- **THEN** the claim is invalid

#### Scenario: Row drawn but not fully marked
- **WHEN** all 5 numbers of a row have been drawn but the player marked only 4 of them, then claims línea
- **THEN** the claim is invalid

#### Scenario: Row marked but not fully drawn
- **WHEN** a player marked all 5 numbers of a row but one of them has not been drawn, then claims línea
- **THEN** the claim is invalid

#### Scenario: Late claim
- **WHEN** a player's row was completed and marked several balls ago, nobody has been awarded línea yet, and the player claims línea now
- **THEN** the claim is valid

### Requirement: Claiming bingo
While the game is playing for bingo, a player SHALL be able to claim bingo. The claim SHALL be valid only if all 15 numbers of one of the player's cards are both marked on that card and drawn. Bingo SHALL NOT be claimable while the game is playing for línea, and línea SHALL NOT be claimable once línea has closed. A player SHALL win each prize at most once, even when both of their cards would win it.

#### Scenario: Valid bingo
- **WHEN** all 15 numbers of a player's card have been drawn and marked, and the player claims bingo
- **THEN** the claim is valid and the player is awarded bingo

#### Scenario: Bingo on the second card
- **WHEN** a player has 2 cards and all 15 numbers of "Cartón 2" have been drawn and marked, and the player claims bingo
- **THEN** the claim is valid, and the winning numbers shown are those of "Cartón 2"

#### Scenario: One number missing
- **WHEN** 14 numbers of a player's card are drawn and marked and the 15th is marked but not drawn, and the player claims bingo
- **THEN** the claim is invalid

#### Scenario: Wrong prize for the stage
- **WHEN** the game is playing for línea and a player claims bingo
- **THEN** the claim is refused with a message that línea is being played

#### Scenario: Both cards win
- **WHEN** both of a player's cards have a complete row and the player claims línea
- **THEN** the player is listed once among the línea winners
