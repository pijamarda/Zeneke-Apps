# bingo-game Specification

## Purpose

Defines how one game of Spanish 90-ball bingo is played in a room: the cards, how balls are drawn, how players mark numbers and claim línea and bingo, how the server checks claims and pauses the game, and how everyone sees the game progress.

## Requirements

### Requirement: Spanish 90-ball cards
Every card SHALL have 3 rows and 9 columns and hold 15 distinct numbers from 1 to 90: exactly 5 per row and 1 to 3 per column. Column 1 SHALL hold numbers 1-9, columns 2 to 8 SHALL hold the tens 10-19 to 70-79, and column 9 SHALL hold 80-90. Numbers in a column SHALL increase from top to bottom. Cards SHALL be random.

#### Scenario: Card shape
- **WHEN** a player gets a card
- **THEN** it has 3 rows of 9 cells, 15 numbers in total, 5 numbers in each row and between 1 and 3 numbers in each column

#### Scenario: Column ranges and order
- **WHEN** a player gets a card
- **THEN** every number is in its column's range (1-9, 10-19, ..., 70-79, 80-90) and the numbers in each column increase from top to bottom

#### Scenario: Many cards are all valid
- **WHEN** 1000 cards are generated
- **THEN** every one of them satisfies the shape, range and order rules

### Requirement: Cards in a game are different
Within one game, no two cards SHALL have the same set of 15 numbers. This SHALL apply both to the cards of different players and to the two cards of the same player.

#### Scenario: Two players
- **WHEN** two players are in the same game
- **THEN** their cards do not contain exactly the same 15 numbers

#### Scenario: Two cards of one player
- **WHEN** a player has 2 cards in a game
- **THEN** the two cards do not contain exactly the same 15 numbers

### Requirement: One or two cards per player
Each player SHALL play with either 1 or 2 cards in a game, as they chose. The player's page SHALL show their cards one below the other, labelled "Cartón 1" and "Cartón 2" when there are two. No player SHALL have more than 2 cards.

#### Scenario: Player with two cards
- **WHEN** a player who chose 2 cartones opens their room page
- **THEN** they see two complete cards, labelled "Cartón 1" and "Cartón 2"

#### Scenario: Player with one card
- **WHEN** a player who chose 1 cartón opens their room page
- **THEN** they see a single card, with no card label

### Requirement: Game progress
A game SHALL go through these stages in order: waiting (no ball drawn), playing for línea, playing for bingo, and finished. The first ball drawn SHALL start the game, a valid línea SHALL move it to playing for bingo once its pause ends, and a valid bingo SHALL finish it once its pause ends.

#### Scenario: First ball starts the game
- **WHEN** the host draws the first ball of a waiting game
- **THEN** the game is playing for línea

#### Scenario: From línea to bingo
- **WHEN** a línea is awarded and its pause ends
- **THEN** the game is playing for bingo

### Requirement: Drawing balls
The host SHALL draw one ball at a time. Each ball SHALL be chosen at random from the numbers 1 to 90 not drawn yet in the game, so no number is drawn twice. No ball SHALL be drawn while the game is paused, after it has finished, or after all 90 numbers have been drawn.

#### Scenario: Host draws a ball
- **WHEN** the host taps the draw button during a game with 10 balls drawn
- **THEN** an 11th ball is drawn that differs from the previous 10

#### Scenario: No draw during a pause
- **WHEN** the host tries to draw while the game is paused after a claim
- **THEN** no ball is drawn

#### Scenario: All numbers drawn
- **WHEN** all 90 numbers have been drawn and the host tries to draw
- **THEN** no ball is drawn and the host is told that no balls are left

### Requirement: Automatic drawing
The host SHALL be able to turn automatic drawing on and off, choosing an interval from a fixed set of options. While it is on and the host screen is open, a ball SHALL be drawn each interval. It SHALL wait during a pause and continue after it, and it SHALL stop when the game finishes or no balls are left.

#### Scenario: Automatic drawing on
- **WHEN** the host turns on automatic drawing with a 10-second interval and keeps the host screen open
- **THEN** a new ball is drawn about every 10 seconds without the host tapping the draw button

#### Scenario: Automatic drawing waits for a pause
- **WHEN** a valid claim pauses the game while automatic drawing is on
- **THEN** no ball is drawn during the pause, and automatic drawing continues after the pause ends if the game is not finished

#### Scenario: Manual draw still available
- **WHEN** automatic drawing is on and the host taps the draw button
- **THEN** a ball is drawn immediately

### Requirement: Everyone sees the draws
The host screen and every player's page SHALL show the last ball drawn and all balls drawn so far in the current game. They SHALL update within a few seconds of each draw, without reloading the page.

#### Scenario: Player sees a new ball
- **WHEN** the host draws the ball 47 while a player's page is open
- **THEN** within a few seconds the player's page shows 47 as the last ball and includes it among the drawn balls

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

### Requirement: Invalid claims
An invalid or refused claim SHALL only show a message in Spanish to the player who made it. It SHALL NOT pause the game, SHALL NOT be shown to other players or the host, and SHALL NOT stop the player from claiming again.

#### Scenario: Invalid claim
- **WHEN** a player claims línea without a valid row
- **THEN** that player sees a message that the claim is not valid, the game keeps going, and nobody else is told

### Requirement: Pause after a valid claim
A valid claim SHALL pause the game. During the pause the host screen and every player's page SHALL show the prize, each winner's nickname and the winning numbers, plus a countdown bar of about 10 seconds. The pause SHALL end when the countdown runs out or when the host taps Continue, whichever comes first.

#### Scenario: Everyone sees the winner
- **WHEN** Ana makes a valid línea claim
- **THEN** within a few seconds the host screen and every player's page show "Línea" with Ana's nickname, her winning row and a countdown bar

#### Scenario: Countdown runs out
- **WHEN** the host does nothing during a pause
- **THEN** the pause ends by itself after about 10 seconds

#### Scenario: Host continues early
- **WHEN** the host taps Continue three seconds into a pause
- **THEN** the pause ends immediately

### Requirement: Shared prizes
Every valid claim for the current prize made before its pause ends SHALL also win that prize. Because no ball can be drawn during the pause, all winners of a prize SHALL have completed it with the same balls. Once the pause ends, that prize SHALL be closed.

#### Scenario: Two players with línea
- **WHEN** Ana makes a valid línea claim and Leo makes a valid línea claim during the pause that follows
- **THEN** both Ana and Leo are awarded línea and both are shown as winners

#### Scenario: Claim after the pause
- **WHEN** a línea pause has ended and another player claims línea before the next ball
- **THEN** the claim is refused because línea is closed

### Requirement: Finished game
After the bingo pause ends, the game SHALL be finished. The host screen and players' pages SHALL show the línea and bingo winners. No more balls SHALL be drawn, marks SHALL NOT change, and the host SHALL be offered to start a new game.

#### Scenario: End of game
- **WHEN** the bingo pause ends
- **THEN** every page shows the game as finished with its línea and bingo winners, and the host screen offers to start a new game
