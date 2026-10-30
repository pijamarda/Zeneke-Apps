# Design

## Context

See proposal.md for the motivation. Today's relevant setup:

- One script, `src/app/static/bingo/bingo.js`, runs both the host screen (`data-role="host"`) and the player page. The host gets the new state straight from its own draw response. Every page also polls the state every 1.5 s.
- `renderBalls()` already detects a genuinely new ball (`renderedGameId` / `renderedCount`). The first render and a game change only set the baseline, so a reload or a poll with no new ball doesn't count as a draw. Ball calls hook into this same detection.
- `renderPause()` runs on every render while `state.pause` is set (`{prize, remaining_ms, total_ms}`), so it cannot tell on its own when a pause has just started.
- The QR code is rendered by `segno ... .svg_inline(scale=8, border=2)` in `views.host`. The output has `width="264" height="264"` and no `viewBox`, while `.qr svg { width: 100%; height: auto }` stretches the box. The drawing stays 264 px inside a wider white box.
- Tested in the live session on the host laptop with Chrome: the Spanish built-in voice plays on the **laptop** even while the tab is cast, and a Web Audio beep plays on the **TV**. With HDMI, both go to the laptop's selected sound output.
- No JavaScript test setup exists. Earlier front-end changes were checked in the browser with `runserver`, plus `manage.py test` for server code.

## Goals / Non-Goals

**Goals:**
- All sound logic lives in the front end, runs only for `role === 'host'`, and needs no new server state, endpoints or assets.
- Calls, win sounds and the test sound are triggered only by real changes (new ball, pause start, toggle tap), never by polling or reloads.

**Non-Goals:**
- Making the voice play on the TV when casting. That needs page-played audio (recorded files) and is a later option.
- Sharing sound settings between browsers or storing them on the server.

## Decisions

### 1. Voice: browser speech, said as separate parts with timed gaps
Use `speechSynthesis` with one `SpeechSynthesisUtterance` per part: the full number, then each digit. Wait on each part's `onend`, then add a fixed delay before the next. Tuned live: **100 ms** before the digits, **200 ms** between them, `rate = 0.9`. Numbers 1-9 are a single part.

Number names come from small lookup tables: units, 10-19, 20-29 (veintiuno, veintidós, ...), then tens + " y " + unit. Digits use the units table, so 0 is "cero".

- *Alternative: one utterance with commas or "..."*. Rejected: every voice handles punctuation differently, so the pauses can't be controlled.
- *Alternative: pre-recorded files*. Deferred: they would cast to the TV, but they need assets. Browser speech is enough for a first version (proposal, Out of scope).

### 2. Voice selection
Pick the first voice with `lang === 'es-ES'`, otherwise any voice whose `lang` starts with `es`. Chrome fills `getVoices()` asynchronously, so pick again on `voiceschanged` and when each call starts. If there's no Spanish voice, skip speaking, so a number is never read in English. Effects still play.

### 3. Interrupting a call
Keep a call counter. A new call increments it, runs `speechSynthesis.cancel()`, and each step of a running call checks the counter before speaking the next part or waiting. A stale call stops by itself, without a pile-up of timers.

### 4. Effects: generated with Web Audio, no files
One shared `AudioContext`, created or resumed inside a user gesture:
- **Test sound:** a short two-tone beep, then the voice says "Sonido activado". It checks both routes at once (when casting, the beep plays on the TV and the voice on the laptop).
- **Ball sound (optional):** a short pitched "pop" (oscillator with a fast pitch drop and decay), played just before the call. The call starts after it finishes (~150 ms).
- **Línea:** about 2.5 s of applause made from many short filtered noise bursts at random times, fading out.
- **Bingo:** a short rising major arpeggio (fanfare) on oscillators, then longer applause (~4 s).

Everything stays inside the ~10 s pause.

- *Alternative: CC0 audio files*. They would sound more natural, but need licensing checks, assets and caching. Generated sound is enough for a first version and can be swapped later behind the same functions.

### 5. Detecting when a pause starts
On the host, remember the last pause that played a sound as a key `game_id + ':' + prize`. The first render only records the current key, if any, without playing. That covers "opened during a pause". After that, a render whose `state.pause` key differs from the stored key plays the matching win sound and stores the key. A second winner of the same prize leaves the key unchanged, so the sound doesn't repeat. Invalid claims never create a pause, so they stay silent.

### 6. Calling a new ball
In `renderBalls()`, when `newBall` is true and the role is host, call `state.last`. The detection already ignores reloads, polls with no change and new games (spec: "No call without a new ball").

### 7. Settings, unlocking and the toggle
- `localStorage` keys `bingo.sound` (`on`/`off`, default off) and `bingo.ballSound` (`on`/`off`, default off). They are per browser, not per room, because the same TV laptop hosts many rooms.
- Host header controls in `host.html`: a toggle button with three labels: "🔇 Activar sonido" (off), "🔊 Sonido activado" (on and unlocked), and "🔈 Toca para activar sonido" (stored as on but the `AudioContext` is not running yet, i.e. after a reload). Next to it, a "Sonido de bola" checkbox.
- Tapping the toggle while off: store `on`, create or resume the `AudioContext`, play the test sound. While in "tap to activate": resume and play the test sound. While on: store `off`, cancel speech.
- Also try `audioContext.resume()` on the first `pointerdown` anywhere on the host page. Tapping "Sacar bola" then unlocks sound too. If that works, the label switches to "Sonido activado".

### 8. QR fills its frame
Render with `svg_inline(scale=8, border=2, omitsize=True)`. segno then writes a `viewBox` with no fixed size, so `.qr svg { width: 100%; height: auto }` scales the drawing to the frame. The 2-module white border stays as the QR quiet zone. Update `test_qr_encodes_the_absolute_join_url` to build the expected SVG with the same arguments.

## Risks / Trade-offs

- [When casting, the voice plays on the laptop and effects on the TV] → Documented in the proposal. The ball sound is off by default because it would clash. Win sounds don't overlap with a call. HDMI puts everything on the TV with no code change.
- [Voice quality and availability depend on the OS and browser] → Spanish only, silent otherwise (decision 2). The test sound shows the host straight away whether the voice works.
- [Browsers block audio until a gesture, and auto-draw is not a gesture] → Explicit toggle plus the "tap to activate" state after reloads (decision 7).
- [Chrome sometimes leaves `speechSynthesis` stuck after the tab was in the background] → Each call starts with `speechSynthesis.cancel()`, which clears a stuck queue.
- [Generated applause may sound artificial] → Acceptable for a first version. It sits behind its own function so recorded files can replace it later.
- [5 s auto interval vs. call length] → A call takes about 2-2.5 s (3 parts, gaps 100/200 ms, rate 0.9), plus ~150 ms with the ball sound. That fits. A late call is cut off by the next one (decision 3).

## Migration Plan

Deploy with `./deploy.sh`. There are no migrations or settings. Roll back by redeploying the previous commit. Settings stored in browsers are ignored by the old code.

## Open Questions

- Exact timbre and length of the applause and fanfare. To be tuned by ear during implementation, within the limits in decision 4.
