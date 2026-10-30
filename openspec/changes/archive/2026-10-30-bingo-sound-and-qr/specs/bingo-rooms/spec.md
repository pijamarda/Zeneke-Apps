# Spec Delta

## MODIFIED Requirements

### Requirement: Host screen shows how to join
The host screen SHALL show the room code, a QR code that opens the room's join page on the same site, and the current list of players' nicknames. The QR code SHALL fill the width of the frame it is shown in, without extra empty space beyond its own quiet border. The player list SHALL update without reloading the page.

#### Scenario: QR code target
- **WHEN** the host screen of a room is shown
- **THEN** it displays the room code and a QR code that encodes the absolute URL of that room's join page

#### Scenario: QR code fills its frame
- **WHEN** the host screen is shown at any window width
- **THEN** the QR code scales to the full width of its white frame, keeping its square shape, with no blank band to its right or below it

#### Scenario: New player appears on the host screen
- **WHEN** a player joins while the host screen is open
- **THEN** their nickname appears on the host screen within a few seconds, without a page reload
