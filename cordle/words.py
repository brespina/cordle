"""Word list loading and daily puzzle selection.

Two lists are kept, mirroring how Wordle itself ships:

``answers``
    The curated pool a target is drawn from. Common, unsurprising words.
``allowed``
    Every other word accepted as a guess. Much larger, so players are not
    told that a perfectly ordinary English word "is not a valid guess".
"""

from __future__ import annotations

import datetime as dt
import random
from functools import lru_cache
from pathlib import Path

from .game import WORD_LENGTH

DATA_DIR = Path(__file__).resolve().parent / "data"

# Fixed reference point for daily puzzle numbering. Changing either constant
# reshuffles every future daily word, so treat them as frozen.
DAILY_EPOCH = dt.date(2021, 6, 19)
DAILY_SEED = 0xC0FFEE


def _load(path: Path) -> tuple[str, ...]:
    """Read a newline delimited word list, skipping blanks and comments."""
    words = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            word = raw.strip().lower()
            if not word or word.startswith("#"):
                continue
            if len(word) != WORD_LENGTH or not word.isalpha() or not word.isascii():
                raise ValueError(
                    f"{path.name}:{lineno}: {word!r} is not a "
                    f"{WORD_LENGTH} letter ascii word"
                )
            words.append(word)
    if not words:
        raise ValueError(f"{path.name} contains no usable words")
    return tuple(words)


class WordList:
    """The answer pool plus the full set of accepted guesses."""

    def __init__(self, answers: tuple[str, ...], allowed: tuple[str, ...]) -> None:
        self.answers = answers
        self._answer_set = frozenset(answers)
        # Answers are always legal guesses, whether or not the guess-only
        # list happens to repeat them.
        self.valid_guesses = self._answer_set | frozenset(allowed)
        # Precomputed shuffle so consecutive days do not repeat a word until
        # the whole pool has been used.
        order = list(range(len(answers)))
        random.Random(DAILY_SEED).shuffle(order)
        self._daily_order = tuple(order)

    def __len__(self) -> int:
        return len(self.valid_guesses)

    def is_valid_guess(self, word: str) -> bool:
        return word.strip().lower() in self.valid_guesses

    def random_answer(self, rng: random.Random | None = None) -> str:
        return (rng or random).choice(self.answers)

    def suggest(self, prefix: str, limit: int = 25) -> list[str]:
        """Words starting with ``prefix``, common ones first.

        The answer pool is curated everyday vocabulary, so surfacing it ahead
        of the long tail keeps autocomplete from opening with words like
        "craal" when the player typed "cra".
        """
        prefix = prefix.strip().lower()
        if not prefix:
            return []
        common = sorted(w for w in self._answer_set if w.startswith(prefix))
        if len(common) >= limit:
            return common[:limit]
        rest = sorted(
            w
            for w in self.valid_guesses
            if w.startswith(prefix) and w not in self._answer_set
        )
        return (common + rest)[:limit]

    def puzzle_number(self, day: dt.date) -> int:
        """Sequential puzzle number for ``day``, counting from the epoch."""
        return (day - DAILY_EPOCH).days

    def daily_answer(self, day: dt.date) -> str:
        """The answer for ``day``.

        Derived purely from the date, so a bot restart mid-day resumes the
        same word instead of silently switching puzzles underneath players.
        """
        index = self.puzzle_number(day) % len(self._daily_order)
        return self.answers[self._daily_order[index]]


@lru_cache(maxsize=1)
def load_words() -> WordList:
    """Load and cache the bundled word lists."""
    return WordList(
        answers=_load(DATA_DIR / "answers.txt"),
        allowed=_load(DATA_DIR / "allowed_guesses.txt"),
    )


def today(utc_offset_hours: float = 0.0) -> dt.date:
    """Current puzzle date, shifted by ``utc_offset_hours``.

    Lets a server roll its daily word over at local midnight rather than UTC
    midnight without pulling in a timezone database.
    """
    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=utc_offset_hours)
    return now.date()
