# Spec Delta

## ADDED Requirements

### Requirement: Changing the number of cards before the game starts
While no ball has been drawn in the current game, a player SHALL be able to switch between 1 and 2 cartones from their room page. Switching to 2 SHALL deal them a new second card. Switching to 1 SHALL remove their second card and its marks. Once the first ball is drawn, the choice SHALL NOT be changeable until a new game starts.

#### Scenario: Add a second card before the start
- **WHEN** a player with 1 cartón switches to 2 cartones before any ball is drawn
- **THEN** they keep their first card and its marks, and get a new second card

#### Scenario: Back to one card
- **WHEN** a player with 2 cartones switches to 1 cartón before any ball is drawn
- **THEN** they keep "Cartón 1" and its marks, and "Cartón 2" is gone

#### Scenario: Game already started
- **WHEN** at least one ball has been drawn and a player tries to change their number of cartones
- **THEN** the change is refused with a message in Spanish, and their cards stay the same

#### Scenario: Choice offered again in a new game
- **WHEN** the host starts a new game and no ball has been drawn yet
- **THEN** the player can change their number of cartones again

## MODIFIED Requirements

### Requirement: Joining a room with a nickname
A visitor SHALL join a room by opening its join page (from the QR code or by entering the code on `/bingo/`), choosing a nickname and choosing 1 or 2 cartones, with 1 selected by default. Joining SHALL be possible before the game starts, during a game and after it ends. Once joined, the visitor SHALL see as many cards as they chose.

#### Scenario: Join from the QR code
- **WHEN** a visitor scans the QR code, enters the nickname `Ana` and confirms without changing the number of cartones
- **THEN** they are a player of that room and one card is shown

#### Scenario: Join with two cards
- **WHEN** a visitor enters the nickname `Leo`, chooses 2 cartones and confirms
- **THEN** they are a player of that room and two different cards are shown

#### Scenario: Join after the game has started
- **WHEN** a visitor joins a room in which 20 balls have already been drawn
- **THEN** they get as many cards as they chose and can see the 20 balls already drawn

### Requirement: New game in the same room
The host SHALL be able to start a new game in the same room at any time, and SHALL be asked to confirm when the current game has started and not finished. The room code, QR code and players SHALL stay the same, every player SHALL get as many new cards as they had chosen, each with no marks, and the drawn balls and prizes of the previous game SHALL be cleared.

#### Scenario: Start a new game
- **WHEN** a game has finished and the host starts a new game
- **THEN** the room has the same code and players, no balls are drawn, no prizes are awarded, and each player's cards are new and have no marks

#### Scenario: Number of cards is kept
- **WHEN** a player who plays with 2 cartones is in the room and the host starts a new game
- **THEN** that player gets 2 new cards

#### Scenario: Restart a game in progress
- **WHEN** balls have been drawn, nobody has won bingo, and the host chooses to start a new game
- **THEN** the host is asked to confirm, and the new game starts only after confirming

#### Scenario: Players see the new game
- **WHEN** a new game starts while a player's room page is open
- **THEN** the player's page shows their new cards within a few seconds, without a reload

### Requirement: Host screen shows how to join
The host screen SHALL show the room code, a QR code that opens the room's join page on the same site, and the current list of players' nicknames, with "×2" next to players who play with 2 cartones. The QR code SHALL fill the width of the frame it is shown in, without extra empty space beyond its own quiet border. The player list SHALL update without reloading the page.

#### Scenario: QR code target
- **WHEN** the host screen of a room is shown
- **THEN** it displays the room code and a QR code that encodes the absolute URL of that room's join page

#### Scenario: QR code fills its frame
- **WHEN** the host screen is shown at any window width
- **THEN** the QR code scales to the full width of its white frame, keeping its square shape, with no blank band to its right or below it

#### Scenario: New player appears on the host screen
- **WHEN** a player joins while the host screen is open
- **THEN** their nickname appears on the host screen within a few seconds, without a page reload

#### Scenario: Players with two cards
- **WHEN** `Leo` plays with 2 cartones and `Ana` with 1
- **THEN** the host's player list shows `Leo ×2` and `Ana` with no count
