# bingo-sound Specification

## Purpose

Defines what the bingo host screen says and plays during a game, so the room hears each ball called in Spanish and hears when someone wins línea or bingo, and how the host turns that sound on and off.

## Requirements

### Requirement: Sound only on the host screen
Ball calls and game sounds SHALL play only on a room's host screen. Players' pages SHALL NOT play any sound.

#### Scenario: Player page stays silent
- **WHEN** a ball is drawn while sound is on at the host screen
- **THEN** the host screen calls the ball and no player's page plays any sound

### Requirement: Host turns sound on and off
The host screen SHALL have a sound toggle that starts off. Turning it on SHALL play a short test sound right away. While it is off, the host screen SHALL play no sound. The game SHALL work the same with sound on or off.

#### Scenario: Sound starts off
- **WHEN** the host opens a room's host screen for the first time in a browser
- **THEN** the sound toggle is off and drawing a ball plays no sound

#### Scenario: Turning sound on plays a test sound
- **WHEN** the host turns the sound toggle on
- **THEN** the host screen immediately plays a short test sound that includes the voice

#### Scenario: Turning sound off
- **WHEN** the host turns the sound toggle off and then draws a ball
- **THEN** no sound is played

### Requirement: Sound settings are remembered
The host screen SHALL remember the sound toggle and the ball sound option in that browser across reloads. When sound was on but the browser needs a tap before it plays sound, the toggle SHALL say so (for example "Toca para activar sonido") and SHALL NOT appear to be already playing.

#### Scenario: Reload with sound on
- **WHEN** the host reloads the host screen after turning sound on
- **THEN** the toggle asks for a tap to activate sound, and after that tap balls are called again without changing any setting

### Requirement: Ball calls in Spanish
While sound is on, each new ball drawn SHALL be read out once in Spanish. A number from 1 to 9 SHALL be said once by its name. A number from 10 to 90 SHALL be said by its name and then digit by digit, with a short pause before the digits and a short pause between them.

#### Scenario: Two-digit number
- **WHEN** ball 42 is drawn with sound on
- **THEN** the host screen says "cuarenta y dos", then "cuatro", then "dos"

#### Scenario: One-digit number
- **WHEN** ball 7 is drawn with sound on
- **THEN** the host screen says only "siete"

#### Scenario: Round number
- **WHEN** ball 90 is drawn with sound on
- **THEN** the host screen says "noventa", then "nueve", then "cero"

#### Scenario: No call without a new ball
- **WHEN** the host screen is opened or reloaded, refreshes its state with no new ball, or a new game starts
- **THEN** no ball is called

### Requirement: A new call replaces the previous one
When a new ball is drawn while the previous call is still being spoken, the previous call SHALL stop and the new ball SHALL be called.

#### Scenario: Quick draws
- **WHEN** the host draws two balls in quick succession with sound on
- **THEN** the first call stops and the second ball is called in full

### Requirement: Spanish voice only
Ball calls SHALL use a Spanish voice, preferring Spain Spanish. When the browser has no Spanish voice, the host screen SHALL NOT read numbers in another language; other sounds SHALL still play.

#### Scenario: No Spanish voice available
- **WHEN** sound is on and the browser offers no Spanish voice
- **THEN** balls are not read out and win sounds still play

### Requirement: Win sounds
While sound is on, the host screen SHALL play applause when a valid línea pauses the game, and a fanfare with applause when a valid bingo pauses it. Each SHALL play once per prize, even when several players share it. Invalid claims SHALL play no sound.

#### Scenario: Línea won
- **WHEN** a valid línea claim pauses the game with sound on
- **THEN** the host screen plays applause once

#### Scenario: Bingo won
- **WHEN** a valid bingo claim pauses the game with sound on
- **THEN** the host screen plays a fanfare with applause once

#### Scenario: Shared prize
- **WHEN** a second player makes a valid línea claim during the same línea pause
- **THEN** the applause is not played again

#### Scenario: Invalid claim
- **WHEN** a player makes an invalid claim
- **THEN** the host screen plays no sound

#### Scenario: Opening during a pause
- **WHEN** the host screen is opened or reloaded while a pause is already showing
- **THEN** no win sound is played

### Requirement: Optional ball sound
The host screen SHALL offer a ball sound option that is off by default. While it and sound are both on, a short sound SHALL play just before each ball call.

#### Scenario: Ball sound off by default
- **WHEN** sound is on and the ball sound option has never been changed
- **THEN** a drawn ball is called with no sound before the call

#### Scenario: Ball sound on
- **WHEN** sound and the ball sound option are both on and a ball is drawn
- **THEN** a short sound plays and then the ball is called
