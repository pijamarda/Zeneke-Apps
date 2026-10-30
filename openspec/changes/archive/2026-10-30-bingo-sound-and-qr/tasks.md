# Tasks

Server tests run from `src/app` with `uv run python manage.py test bingo`. Check the browser parts with `uv run python manage.py runserver` (also from `src/app`): a desktop Chrome window for the host and a phone-sized window or device emulation for players. Chrome needs a Spanish voice installed to hear calls.

## 1. QR fills its frame

- [x] 1.1 In `views.host`, render the QR with `svg_inline(scale=8, border=2, omitsize=True)` (design.md decision 8). Update `test_qr_encodes_the_absolute_join_url` to expect the same arguments and also check that the SVG has a `viewBox` and no `width=` attribute. Verify: `uv run python manage.py test bingo` passes, and on the host screen, at desktop width and at a narrow width under 900 px, the QR fills its white frame with no blank band to the right or below.

## 2. Sound controls on the host screen

- [x] 2.1 Add the sound toggle button and the "Sonido de bola" checkbox to `host.html` (design.md decision 7), styled in `bingo.css` to fit the header. Add a test in `tests.py` that the host page contains both controls and the player page contains neither. Verify: `uv run python manage.py test bingo` passes.
- [x] 2.2 In `bingo.js`, for the host role only, add the `bingo.sound` / `bingo.ballSound` settings in `localStorage`, the shared `AudioContext`, the three toggle labels, and the unlock on toggle tap and on the first `pointerdown` (decision 7). Turning sound on plays the test sound: a beep, then "Sonido activado" (decision 4). Verify in the browser: first visit shows "Activar sonido" and the checkbox is off; tapping plays the test sound and shows "Sonido activado"; reloading shows "Toca para activar sonido", and tapping it (or tapping "Sacar bola") switches back to "Sonido activado"; turning it off silences everything; the player page has no controls and no console errors.

## 3. Ball calls

- [x] 3.1 Add the Spanish number names, voice selection (decision 2), the part-by-part call with 100 / 200 ms gaps at rate 0.9 (decision 1), and interruption through a call counter plus `speechSynthesis.cancel()` (decision 3). Verify in the host page's DevTools console by calling the function directly for 7, 10, 15, 21, 42 and 90: you hear "siete" / "diez, uno, cero" / "quince, uno, cinco" / "veintiuno, dos, uno" / "cuarenta y dos, cuatro, dos" / "noventa, nueve, cero", and calling 42 then 77 right away cuts 42 off and says 77 in full.
- [x] 3.2 Call `state.last` from `renderBalls()` when `newBall` is true on the host with sound on, with the optional ball "pop" first when the setting is on (decisions 4 and 6). Verify in the browser: each manual draw is called once; auto-draw at 5 s calls every ball without overlap; reloading, polls with no new ball and "Nueva partida" call nothing; the pop plays only with "Sonido de bola" checked; with sound off nothing plays; an open player page stays silent.

## 4. Win sounds

- [x] 4.1 Add the línea applause and the bingo fanfare plus applause (decision 4), triggered by the pause-start key `game_id:prize` with the first render only setting the baseline (decision 5). Verify in the browser with a host and two players: a valid línea plays applause once; a second valid línea in the same pause plays nothing more; a valid bingo plays the fanfare and applause; an invalid claim plays nothing; reloading the host during a pause plays nothing; each sound ends within the ~10 s pause.

## 5. Integration check

- [x] 5.1 Run `uv run python manage.py test bingo` and play a full game in the browser with sound on: manual and automatic draws, a shared línea, a bingo and a new game. Confirm the behaviour matches every scenario in `specs/bingo-sound/spec.md`, with no errors in the browser console.
- [x] 5.2 After deploying with `./deploy.sh`, on the TV laptop: cast the host tab and confirm the voice plays on the laptop and the beep and applause play on the TV. Then connect by HDMI and confirm everything plays on the TV. Scan the QR from a phone to confirm it still opens the join page.

## Workflow follow-up

- Archive the change after deployment, syncing the `bingo-sound` and `bingo-rooms` deltas into the main specs.
