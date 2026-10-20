# bingo-rooms Specification

## Purpose

Lets anyone, without a Zeneke account, open a bingo room on a shared screen and lets others join it from their phones by QR code or room code. It also defines who controls a room and the limits that keep public rooms safe to offer.

## Requirements

### Requirement: Bingo pages are public
Every bingo page and action SHALL work without signing in. Signing in SHALL NOT be required or offered on bingo pages, and a signed-in family member SHALL be treated like any other visitor. Pages of the other apps SHALL keep their existing sign-in requirements.

#### Scenario: Anonymous visitor opens bingo
- **WHEN** a visitor who is not signed in requests `/bingo/`
- **THEN** the bingo start page is shown, not a redirect to the login page

#### Scenario: Family apps stay protected
- **WHEN** a visitor who is not signed in requests `/fercoins/`
- **THEN** they are still redirected to the login page

### Requirement: Phone-friendly Spanish layout
Bingo pages SHALL be in Spanish and SHALL use a layout made for phones and shared screens, without the site's family navigation links, user menu or login button.

#### Scenario: Guest page without family navigation
- **WHEN** a visitor opens any bingo page
- **THEN** the page text is in Spanish and the page shows no Fercoins, Familia or Login links

### Requirement: Anyone can create a room
A visitor SHALL be able to create a room from the bingo start page with one action and no other input. The browser that created the room SHALL become that room's host, and the visitor SHALL be taken to the room's host screen.

#### Scenario: Create a room
- **WHEN** a visitor who is not signed in taps the create-room button on `/bingo/`
- **THEN** a new room exists, that browser is its host, and the host screen for the room is shown

### Requirement: Room codes
Each room SHALL have a short code that is unique among existing rooms. Codes SHALL use only uppercase letters and digits, and SHALL leave out characters that are easy to confuse (such as `0`/`O` and `1`/`I`). Entering a code SHALL ignore letter case and surrounding spaces.

#### Scenario: Code format
- **WHEN** a room is created
- **THEN** its code contains only uppercase letters and digits without easily confused characters, and no other existing room has the same code

#### Scenario: Code typed in lower case
- **WHEN** a visitor enters the code of an existing room in lower case with a trailing space
- **THEN** they reach that room's join page

### Requirement: Host screen shows how to join
The host screen SHALL show the room code, a QR code that opens the room's join page on the same site, and the current list of players' nicknames. The player list SHALL update without reloading the page.

#### Scenario: QR code target
- **WHEN** the host screen of a room is shown
- **THEN** it displays the room code and a QR code that encodes the absolute URL of that room's join page

#### Scenario: New player appears on the host screen
- **WHEN** a player joins while the host screen is open
- **THEN** their nickname appears on the host screen within a few seconds, without a page reload

### Requirement: Joining a room with a nickname
A visitor SHALL join a room by opening its join page (from the QR code or by entering the code on `/bingo/`) and choosing a nickname. Joining SHALL be possible before the game starts, during a game and after it ends. Once joined, the visitor SHALL see their card.

#### Scenario: Join from the QR code
- **WHEN** a visitor scans the QR code, enters the nickname `Ana` and confirms
- **THEN** they are a player of that room and their card is shown

#### Scenario: Join after the game has started
- **WHEN** a visitor joins a room in which 20 balls have already been drawn
- **THEN** they get a card and can see the 20 balls already drawn

### Requirement: Nickname rules
A nickname SHALL be 1 to 20 characters long after trimming surrounding spaces, and SHALL be unique within the room, ignoring letter case. A nickname that breaks these rules SHALL be refused with a message in Spanish, and the visitor SHALL be able to try another one. Nicknames SHALL always be displayed as plain text.

#### Scenario: Empty nickname
- **WHEN** a visitor tries to join with a nickname made only of spaces
- **THEN** they are not joined and a message asks for a nickname

#### Scenario: Nickname already taken
- **WHEN** `Ana` is in the room and another visitor tries to join as `ana`
- **THEN** they are not joined and a message says the nickname is taken

#### Scenario: Markup in a nickname
- **WHEN** a visitor joins with the nickname `<b>Leo</b>`
- **THEN** every page shows the nickname as the literal text `<b>Leo</b>`, not as bold text

### Requirement: The browser remembers its player
After joining, the same browser SHALL be recognised as the same player in that room until the room expires: reloading, closing and reopening the page, or the phone going to sleep SHALL bring back the same player and card. A browser SHALL be at most one player per room, and opening the join page again SHALL show its existing card.

#### Scenario: Reload keeps the card
- **WHEN** a player who has marked three numbers reloads the room page
- **THEN** they see the same nickname, the same card and the same three marks

#### Scenario: Join page for an existing player
- **WHEN** a browser that already joined a room opens that room's join page again
- **THEN** it is shown its existing card instead of the nickname form

#### Scenario: Another browser is a different player
- **WHEN** a second browser (or a private window) opens the same join page
- **THEN** it is asked for a nickname and becomes a different player

### Requirement: Only the host controls the room
Drawing balls, turning automatic drawing on or off, continuing after a claim, starting a new game and removing players SHALL be allowed only from the host's browser. The same actions from any other browser SHALL be refused and SHALL change nothing. The host's browser SHALL also be able to join the room as a player.

#### Scenario: Player tries to draw
- **WHEN** a request to draw a ball is sent from a player's browser that is not the host
- **THEN** it is refused and no ball is drawn

#### Scenario: Host also plays
- **WHEN** the host's browser opens the room's join page and enters a nickname
- **THEN** it becomes a player of that room as well, and it keeps its host controls on the host screen

### Requirement: Host can remove a player
The host SHALL be able to remove a player from the room. A removed player SHALL disappear from the player list, their card and claims SHALL stop counting, their browser SHALL be shown that they were removed, and that browser SHALL NOT be able to join the same room again.

#### Scenario: Remove a player
- **WHEN** the host removes the player `Troll`
- **THEN** `Troll` is no longer listed, and their browser shows a message that they were removed from the room

#### Scenario: Removed player tries to rejoin
- **WHEN** the removed browser opens the room's join page again
- **THEN** it is refused with a message and does not become a player

### Requirement: New game in the same room
The host SHALL be able to start a new game in the same room at any time, and SHALL be asked to confirm when the current game has started and not finished. The room code, QR code and players SHALL stay the same, every player SHALL get a new card with no marks, and the drawn balls and prizes of the previous game SHALL be cleared.

#### Scenario: Start a new game
- **WHEN** a game has finished and the host starts a new game
- **THEN** the room has the same code and players, no balls are drawn, no prizes are awarded, and each player's card is new and has no marks

#### Scenario: Restart a game in progress
- **WHEN** balls have been drawn, nobody has won bingo, and the host chooses to start a new game
- **THEN** the host is asked to confirm, and the new game starts only after confirming

#### Scenario: Players see the new game
- **WHEN** a new game starts while a player's room page is open
- **THEN** the player's page shows their new card within a few seconds, without a reload

### Requirement: Inactive rooms expire
A room with no activity (no join, draw, mark, claim or host action) for a configurable period SHALL expire and be deleted together with its players, cards, balls and claims. The period SHALL default to 12 hours.

#### Scenario: Old room is gone
- **WHEN** a room has had no activity for longer than the expiry period and someone opens its join page
- **THEN** a message in Spanish says the room does not exist or has expired, with a link to `/bingo/`

#### Scenario: Active room stays
- **WHEN** a room had activity less than the expiry period ago
- **THEN** it still exists and works

### Requirement: Unknown rooms
A room code or room page that does not match an existing room SHALL show the same Spanish "room not found or expired" message, whether the room never existed or has expired.

#### Scenario: Mistyped code
- **WHEN** a visitor enters a code that matches no room on `/bingo/`
- **THEN** a message says the room was not found or has expired, and the visitor can enter another code

### Requirement: Limits on rooms and players
The number of existing rooms and the number of players per room SHALL each have a configurable cap. When a cap is reached, creating a room or joining a room SHALL be refused with a message in Spanish, and nothing SHALL be created.

#### Scenario: Room cap reached
- **WHEN** the number of existing rooms equals the room cap and a visitor tries to create a room
- **THEN** no room is created and a message says that no more rooms can be created right now

#### Scenario: Expired rooms do not count
- **WHEN** the room cap is reached only because some rooms have passed the expiry period, and a visitor tries to create a room
- **THEN** the expired rooms are deleted and the new room is created

#### Scenario: Player cap reached
- **WHEN** a room has as many players as the player cap and another visitor tries to join
- **THEN** they are not joined and a message says the room is full
