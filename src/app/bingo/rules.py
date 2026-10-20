"""Spanish 90-ball bingo rules as plain functions (no requests, no database)."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

ROWS = 3
COLUMNS = 9
NUMBERS_PER_ROW = 5
NUMBERS_PER_CARD = ROWS * NUMBERS_PER_ROW
MAX_PER_COLUMN = 3
HIGHEST_BALL = 90
COLUMN_RANGES = [(1, 9)] + [(10 * c, 10 * c + 9) for c in range(1, 8)] + [(80, 90)]

WAITING = 'waiting'
LINEA = 'linea'
BINGO = 'bingo'
FINISHED = 'finished'
PRIZES = (LINEA, BINGO)

PAUSE_SECONDS = 10


def generate_card(rng):
    """Return a random 3x9 card: rows of 9 cells, None for blanks."""
    while True:
        counts = [1] * COLUMNS
        while sum(counts) < NUMBERS_PER_CARD:
            column = rng.randrange(COLUMNS)
            if counts[column] < MAX_PER_COLUMN:
                counts[column] += 1
        for _ in range(1000):
            rows_by_column = [sorted(rng.sample(range(ROWS), n)) for n in counts]
            totals = [sum(row in rows for rows in rows_by_column) for row in range(ROWS)]
            if totals == [NUMBERS_PER_ROW] * ROWS:
                break
        else:
            continue
        grid = [[None] * COLUMNS for _ in range(ROWS)]
        for column, rows in enumerate(rows_by_column):
            low, high = COLUMN_RANGES[column]
            numbers = sorted(rng.sample(range(low, high + 1), len(rows)))
            for row, number in zip(rows, numbers):
                grid[row][column] = number
        return grid


def card_numbers(grid):
    return sorted(n for row in grid for n in row if n is not None)


def numbers_key(grid):
    return ','.join(str(n) for n in card_numbers(grid))


def _covered(numbers, marks, drawn):
    marks, drawn = set(marks), set(drawn)
    return all(n in marks and n in drawn for n in numbers)


def valid_linea_row(grid, marks, drawn):
    """Index of the first row whose numbers are all marked and drawn, else None."""
    for index, row in enumerate(grid):
        if _covered([n for n in row if n is not None], marks, drawn):
            return index
    return None


def is_bingo(grid, marks, drawn):
    return _covered(card_numbers(grid), marks, drawn)


@dataclass(frozen=True)
class GameState:
    stage: str
    drawn: tuple = ()
    pause_prize: str | None = None
    pause_ends_at: datetime | None = None

    @property
    def paused(self):
        return self.pause_ends_at is not None


def settle(state, now):
    """Apply an ended pause: close its prize and move the game on."""
    if state.pause_ends_at is None or now < state.pause_ends_at:
        return state
    next_stage = BINGO if state.pause_prize == LINEA else FINISHED
    return replace(state, stage=next_stage, pause_prize=None, pause_ends_at=None)


def claim_refusal(state, prize):
    """Why a claim for `prize` is refused on a settled state, or None if it is open.

    A prize stays open during the pause its first valid claim started, because the
    stage only moves on when that pause ends (see settle).
    """
    if state.stage == FINISHED:
        return 'finished'
    if state.stage == WAITING:
        return 'waiting'
    if state.stage == prize:
        return None
    return 'linea_first' if prize == BINGO else 'linea_closed'


def start_pause(state, prize, now):
    """Start the reveal pause for the first valid claim; later claims keep it."""
    if state.paused:
        return state
    return replace(state, pause_prize=prize, pause_ends_at=now + timedelta(seconds=PAUSE_SECONDS))


def end_pause_now(state, now):
    if not state.paused:
        return state
    return settle(replace(state, pause_ends_at=now), now)


def draw_refusal(state):
    """Why no ball can be drawn on a settled state, or None."""
    if state.stage == FINISHED:
        return 'finished'
    if state.paused:
        return 'paused'
    if len(state.drawn) >= HIGHEST_BALL:
        return 'no_balls'
    return None


def draw_ball(state, rng):
    left = [n for n in range(1, HIGHEST_BALL + 1) if n not in set(state.drawn)]
    ball = rng.choice(left)
    stage = LINEA if state.stage == WAITING else state.stage
    return replace(state, stage=stage, drawn=state.drawn + (ball,)), ball
