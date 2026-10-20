# Design

## Context

- All bingo pages update from `static/bingo/bingo.js`: every ~1.5 s, and after the host's own actions, `update(state)` calls `render()`.
- `renderBalls()` rebuilds the phone strip (`#drawn-strip`) from scratch on **every** render (`replaceChildren`). On the host, it toggles `drawn`/`last` classes on the 1-90 board cells. The last ball is `#last-ball` (`.ball-last` on the phone, `.ball-huge` on the host).
- The player script already remembers `gameId` to notice a new game.
- The strip is a single row with `overflow-x: auto` (`.drawn-strip` in `bingo.css`), and phones hide its scrollbar.

Motivation: see `proposal.md`. No spec changes (`skip_specs`).

## Goals / Non-Goals

**Goals:**
- Animate exactly once per newly drawn ball, on every open page, whether the ball arrives through a poll or through the host's own draw response.
- Show the swipe hint only when there is something to swipe to.
- CSS does the animations. JavaScript only decides *when*.

**Non-Goals:**
- Changes to the JSON state, views or templates beyond a class or wrapper.
- Animating anything other than a new ball (claims, pauses and joins keep their current look).

## Decisions

### 1. "New ball" means: same game, more balls than last rendered
The script keeps `renderedGameId` and `renderedCount` from the previous render. A render counts as a new ball when `state.game_id === renderedGameId` and `state.drawn.length > renderedCount`. The first render after loading the page only records the baseline, and a change of game id resets it, so opening, reloading and new games never animate.
- If several balls arrive at once (for example after the phone was offline), only the newest ball animates.
- The host page gets the new state twice: once in its draw response and again on the next poll. The second time the count hasn't grown, so nothing replays.
- *Alternative:* compare `state.last` with the previous value. Rejected: a new game can start with the same last number, and the count also tells us how many strip items to add.

### 2. The strip is updated incrementally
Rebuilding the strip on every poll would cut an animation in progress and start the new ball over. Instead:
- same game and the count grew: prepend only the new balls, and give the newest one the `is-new` class
- anything else (first render, new game, count went down): rebuild as today, with no animation

The slide-in animates the new ball from zero width to its normal size, so the other balls move right smoothly. No layout code is needed.

### 3. Replaying CSS animations
Animated elements get an `is-new` class (last ball, newest strip ball, the board cell). To replay it on an element that already has it (`#last-ball` is reused for every ball), the script removes the class, forces a reflow (reading `offsetWidth`), then adds it back. An `animationend` listener removes the class.
- Keyframes, about 0.4-0.6 s each:
  - `pop` on `.ball-last`: scale 0.3 to 1.15 to 1
  - `pop-roll` on `.ball-huge`: the same scaling plus a small rotation
  - `slide-in` on the strip ball
  - `flash` on `.board-cell`: a bright yellow glow fading back to the normal "drawn"/"last" colour
- *Alternative:* the Web Animations API (`element.animate`). It's also fine, but keeping the keyframes in CSS keeps the styling in one place, and the reduced-motion rule (decision 5) then covers everything automatically.

### 4. Swipe hint with a CSS mask, toggled by scroll position
The strip gets a `has-more` class while `scrollLeft + clientWidth < scrollWidth - 1`. The class is checked after each render, on the strip's `scroll` event, and on window resize. `.drawn-strip.has-more` applies `mask-image` (and `-webkit-mask-image` for Safari): a linear gradient that fades the last ~3 rem to transparent. The hint therefore disappears when all balls fit or when the player has scrolled to the end.
- *Alternative:* an overlaid gradient element. Rejected: it needs a wrapper and a background colour matched to the page, while the mask works on any background.

### 5. Reduced motion is handled in CSS
`@media (prefers-reduced-motion: reduce)` turns off the bingo animations (`animation: none`) and smooth scrolling. The fade hint stays, because it doesn't move.

## Risks / Trade-offs

- [A poll lands while an animation is running] → the strip and `#last-ball` are no longer rebuilt when nothing changed (decision 2), so the animation finishes.
- [Older browsers without `mask-image`] → the strip simply shows no fade, which is today's behaviour.
- [Animations on a slow phone] → only `transform`, `opacity` and `width`/`margin` are animated, on a single small element each time.

## Migration Plan

Front-end only. Deploy with `./deploy.sh`. The hashed static file names make browsers load the new CSS and JS. To roll back, redeploy the previous commit.
