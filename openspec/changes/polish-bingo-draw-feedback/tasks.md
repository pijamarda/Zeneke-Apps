# Tasks

Front-end only: `src/app/static/bingo/bingo.js` and `src/app/static/bingo/bingo.css`. Check in a browser with `runserver` (from `src/app`: `uv run python manage.py runserver`), using a desktop window for the host and a phone-sized window or device emulation for players.

## 1. Swipe hint on the phone strip

- [x] 1.1 Add the `has-more` toggle to `bingo.js` (design.md decision 4: checked after each render, on the strip's `scroll` event and on resize) and the `.drawn-strip.has-more` mask fade (`mask-image` and `-webkit-mask-image`) to `bingo.css`. Verify in a phone-sized viewport: no fade with 5 balls drawn; a fade on the right edge with 20 balls; the fade disappears after scrolling to the end of the strip and comes back when scrolling back.

## 2. New-ball animation

- [x] 2.1 Add new-ball detection to `bingo.js` following design.md decision 1 (`renderedGameId`/`renderedCount`; the first render and a game change only set the baseline), and make the phone strip incremental following decision 2 (prepend only new balls; rebuild otherwise). Verify in the browser: drawing 3 balls adds them in order with the newest on the left; reloading the page shows the same strip; a new game empties it.
- [x] 2.2 Add the keyframes and `is-new` classes from design.md decision 3 (`pop` on the phone's last ball, `pop-roll` on the host's last ball, `slide-in` on the newest strip ball, `flash` on the new board cell), with the replay helper (remove class, reflow, add class, remove on `animationend`). Verify on both screens: each draw animates once, on the host screen and on an open player page; a poll right after a draw (or the host's own draw response followed by its next poll) does not replay it; opening or reloading a page and starting a new game do not animate.
- [x] 2.3 Add the `prefers-reduced-motion: reduce` rule (design.md decision 5). Verify with the browser's reduced-motion emulation (for example Chrome DevTools > Rendering > "Emulate CSS prefers-reduced-motion"): a draw updates the numbers with no animation, and the strip fade is still shown.

## 3. Integration check

- [x] 3.1 Run `uv run python manage.py test` (it should still pass, since no server code changed). Then play a short game in the browser with a host window and two phone-sized player windows: manual draws, automatic drawing at 5 s, a línea claim with its pause, and a new game. Confirm the animations and fade behave as in tasks 1-2, with no errors in the browser console.
- [ ] 3.2 After deploying with `./deploy.sh`, open a room on the TV or laptop and join with a real phone. Confirm the fade shows once the strip overflows, swiping reveals older balls, and new balls animate on both screens.

## Workflow follow-up

- Archive the change after deployment. There are no specs to sync (`skip_specs`).
