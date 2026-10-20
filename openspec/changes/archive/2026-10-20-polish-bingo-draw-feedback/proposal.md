# Proposal

## Why

The first games in production showed two small problems with how drawn balls look. On phones, the strip of drawn balls scrolls sideways but nothing shows that it does, so after about ten balls it simply looks cut off. And a new ball appears without any visual cue, so players who glance away can miss that the number changed.

## What Changes

- **Swipe hint on the phone strip:** the right edge of the drawn-balls strip fades out while there are more balls to scroll to, which makes clear that older numbers are there. The strip keeps its current behaviour: every ball drawn, newest on the left, scrolling sideways.
- **New-ball animation on the phone and on the host screen (TV or laptop):**
  - The last ball "pops" in. On the host screen the pop is bigger and the ball rolls slightly.
  - On the phone strip, the new ball slides in from the left.
  - On the host's 1-90 board, the new number's cell briefly flashes yellow.
- The animation plays only when a new ball has been drawn: not on the regular updates every 1.5 s, not when the page is opened or reloaded, and not when a new game starts.
- People whose device asks for reduced motion get no animation.

Out of scope: reading numbers aloud, changing which balls are shown on the phone, sounds.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
<!-- None. The change is purely visual: pages show exactly the same information
     as the `bingo-game` and `bingo-rooms` specs require today. The change sets
     `skip_specs: true` in .openspec.yaml. -->

## Impact

- **Code**: only the front end. `src/app/static/bingo/bingo.css` (fade and keyframe animations, reduced-motion rule) and `src/app/static/bingo/bingo.js` (detect a newly drawn ball and trigger the animations). Templates may get an extra wrapper for the fade.
- **No changes** to views, models, the JSON state, settings, dependencies or data.
- **Deploy**: a normal `./deploy.sh`. The production static storage gives the changed files new hashed names, so browsers pick them up without clearing their cache.
