# Proposal

## Why

In a live game with four people, playing felt too quiet: everyone expected a bingo caller reading the numbers in Spanish, plus a sound when someone wins línea or bingo. The same session also showed that the QR code on the host screen looks too small for the white box around it, which looks unfinished on a TV.

## What Changes

- **Spoken ball calls on the host screen:** each new ball is read out in Spanish. A two-digit number is said in full and then digit by digit ("cuarenta y dos, cuatro, dos"). A one-digit number is said once ("siete"). A new ball interrupts a call that is still being spoken.
- **"Activar sonido" toggle on the host screen:** sound is off until the host turns it on. Turning it on plays a short test sound, so whoever runs the screen can hear where the sound comes out (when casting a Chrome tab, the browser voice plays on the laptop and other page sounds play on the TV).
- **Win sounds on the host screen:** applause when a valid línea pauses the game, and a fanfare plus applause when a valid bingo does. Invalid claims stay silent.
- **Optional ball sound:** a separate host setting, off by default, plays a short sound just before each call. It is off by default because when casting it plays on the TV a moment after the voice starts on the laptop.
- The host screen remembers both sound settings in that browser. After a reload, the browser still needs one tap before it will play sound, and the toggle says so.
- Players' phones play no sound.
- **QR code fills its frame:** the QR code on the host screen scales to the full width of its white frame, with no extra empty space.

Out of scope: pre-recorded voice files (a possible later step so the voice also plays on the TV when casting), traditional number nicknames ("la niña bonita"), sound on phones.

## Capabilities

### New Capabilities
- `bingo-sound`: what the host screen says and plays during a game (ball calls, win sounds, optional ball sound) and how the host turns sound on and off.

### Modified Capabilities
- `bingo-rooms`: "Host screen shows how to join" gains the rule that the QR code fills its frame.

## Impact

- `src/app/static/bingo/bingo.js` and `bingo.css`: sound settings, speaking the calls, generated sound effects, playing them only on the host screen.
- `src/app/templates/bingo/host.html`: the "Activar sonido" toggle and the "Sonido de bola" option.
- `src/app/bingo/views.py`: render the QR SVG so it scales to its container (with a `viewBox` instead of a fixed width and height). `src/app/bingo/tests.py`: update the QR test to match.
- No new server endpoints, data model changes or dependencies. The browser's built-in speech (Web Speech API) and Web Audio do the work, with nothing extra to download.
