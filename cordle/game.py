"""Pure Wordle game logic.

Deliberately free of any Discord imports so the rules can be unit tested
without a bot, an event loop, or a network.
"""

from __future__ import annotations

import enum
from collections import Counter
from dataclasses import dataclass, field

WORD_LENGTH = 5
MAX_ATTEMPTS = 6
ALPHABET = "abcdefghijklmnopqrstuvwxyz"


class Tile(enum.Enum):
    """The result of scoring a single letter of a guess."""

    CORRECT = "correct"
    PRESENT = "present"
    ABSENT = "absent"


class Status(enum.Enum):
    """Where a game currently stands."""

    IN_PROGRESS = "in_progress"
    WON = "won"
    LOST = "lost"
    RESIGNED = "resigned"

    @property
    def is_over(self) -> bool:
        return self is not Status.IN_PROGRESS


class Mode(enum.Enum):
    """Which pool the answer was drawn from."""

    DAILY = "daily"
    PRACTICE = "practice"


class InvalidGuess(Exception):
    """Raised when a guess cannot be accepted. The message is user facing."""


def score_guess(guess: str, answer: str) -> tuple[Tile, ...]:
    """Score ``guess`` against ``answer`` using real Wordle duplicate handling.

    Letters are matched in two passes. Exact position matches are consumed
    first, then remaining letters are matched against what is left over. This
    is what stops ``speed`` against ``abide`` from reporting two yellow E's
    when the answer only contains one.
    """
    if len(guess) != len(answer):
        raise ValueError("guess and answer must be the same length")

    tiles = [Tile.ABSENT] * len(guess)
    remaining = Counter(answer)

    for i, letter in enumerate(guess):
        if letter == answer[i]:
            tiles[i] = Tile.CORRECT
            remaining[letter] -= 1

    for i, letter in enumerate(guess):
        if tiles[i] is Tile.CORRECT:
            continue
        if remaining[letter] > 0:
            tiles[i] = Tile.PRESENT
            remaining[letter] -= 1

    return tuple(tiles)


@dataclass(frozen=True)
class Row:
    """One submitted guess and the tiles it earned."""

    guess: str
    tiles: tuple[Tile, ...]

    @property
    def is_win(self) -> bool:
        return all(tile is Tile.CORRECT for tile in self.tiles)


@dataclass
class Game:
    """A single player's board.

    ``answer`` is the target word. ``rows`` accumulates scored guesses. The
    game is finished once ``status.is_over`` is true; further guesses raise.
    """

    answer: str
    mode: Mode = Mode.PRACTICE
    hard: bool = False
    max_attempts: int = MAX_ATTEMPTS
    puzzle_number: int | None = None
    rows: list[Row] = field(default_factory=list)
    status: Status = Status.IN_PROGRESS

    @property
    def attempts_used(self) -> int:
        return len(self.rows)

    @property
    def attempts_left(self) -> int:
        return self.max_attempts - self.attempts_used

    def letter_states(self) -> dict[str, Tile]:
        """Best known state per letter, for the keyboard hint.

        A letter that has ever been green stays green even if a later guess
        puts it in the wrong slot.
        """
        rank = {Tile.ABSENT: 0, Tile.PRESENT: 1, Tile.CORRECT: 2}
        best: dict[str, Tile] = {}
        for row in self.rows:
            for letter, tile in zip(row.guess, row.tiles):
                if letter not in best or rank[tile] > rank[best[letter]]:
                    best[letter] = tile
        return best

    def unused_letters(self) -> list[str]:
        """Letters not yet tried at all."""
        seen = self.letter_states()
        return [letter for letter in ALPHABET if letter not in seen]

    def hard_mode_violation(self, guess: str) -> str | None:
        """Return a user facing reason ``guess`` breaks hard mode, or None.

        Two constraints are enforced, matching the widely used interpretation:
        every revealed green must stay in its position, and every letter
        revealed as present must reappear at least as many times as it has
        been shown to occur.
        """
        if not self.hard or not self.rows:
            return None

        required_positions: dict[int, str] = {}
        required_counts: Counter[str] = Counter()

        for row in self.rows:
            row_counts: Counter[str] = Counter()
            for i, (letter, tile) in enumerate(zip(row.guess, row.tiles)):
                if tile is Tile.CORRECT:
                    required_positions[i] = letter
                if tile in (Tile.CORRECT, Tile.PRESENT):
                    row_counts[letter] += 1
            for letter, count in row_counts.items():
                if count > required_counts[letter]:
                    required_counts[letter] = count

        for position, letter in sorted(required_positions.items()):
            if guess[position] != letter:
                return (
                    f"Hard mode: letter {position + 1} must be "
                    f"**{letter.upper()}**."
                )

        guess_counts = Counter(guess)
        for letter, count in sorted(required_counts.items()):
            if guess_counts[letter] < count:
                if count == 1:
                    return f"Hard mode: your guess must contain **{letter.upper()}**."
                return (
                    f"Hard mode: your guess must contain at least {count} "
                    f"**{letter.upper()}**'s."
                )

        return None

    def submit(self, guess: str) -> Row:
        """Validate and record ``guess``, advancing the game status.

        Raises :class:`InvalidGuess` with a user facing message if the guess
        cannot be accepted. Callers are expected to have already checked the
        word against the dictionary; length and hard mode are checked here.
        """
        if self.status.is_over:
            raise InvalidGuess("That game is already finished.")

        guess = guess.strip().lower()
        if len(guess) != WORD_LENGTH:
            raise InvalidGuess(f"Guesses must be exactly {WORD_LENGTH} letters.")
        if not guess.isalpha() or not guess.isascii():
            raise InvalidGuess("Guesses must be letters only.")

        violation = self.hard_mode_violation(guess)
        if violation is not None:
            raise InvalidGuess(violation)

        row = Row(guess=guess, tiles=score_guess(guess, self.answer))
        self.rows.append(row)

        if row.is_win:
            self.status = Status.WON
        elif self.attempts_left <= 0:
            self.status = Status.LOST

        return row

    def resign(self) -> None:
        """Give up on an in progress game."""
        if self.status.is_over:
            raise InvalidGuess("That game is already finished.")
        self.status = Status.RESIGNED
