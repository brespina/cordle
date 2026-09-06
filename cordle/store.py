"""In-memory game storage.

Games live only for the lifetime of the process. The daily *word* is derived
from the date rather than stored, so a restart resumes the same puzzle even
though in-progress boards are lost.
"""

from __future__ import annotations

import datetime as dt

from .game import Game, Mode
from .words import WordList


class GameStore:
    """Holds at most one daily and one practice game per player.

    Finished games are kept so ``/board`` and ``/share`` still work after the
    final guess. Stale dailies are dropped by :meth:`prune`.
    """

    def __init__(self) -> None:
        self._games: dict[tuple[int, Mode], Game] = {}
        self._last_mode: dict[int, Mode] = {}

    def get(self, user_id: int, mode: Mode) -> Game | None:
        return self._games.get((user_id, mode))

    def put(self, user_id: int, game: Game) -> None:
        self._games[(user_id, game.mode)] = game
        self._last_mode[user_id] = game.mode

    def touch(self, user_id: int, mode: Mode) -> None:
        """Remember which board this player interacted with most recently."""
        self._last_mode[user_id] = mode

    def active(self, user_id: int) -> Game | None:
        """The player's most recently used game, preferring unfinished ones."""
        preferred = self._last_mode.get(user_id)
        candidates = [preferred] if preferred else []
        candidates += [m for m in Mode if m != preferred]

        for mode in candidates:
            game = self._games.get((user_id, mode))
            if game is not None and not game.status.is_over:
                return game
        for mode in candidates:
            game = self._games.get((user_id, mode))
            if game is not None:
                return game
        return None

    def start_daily(
        self, user_id: int, words: WordList, day: dt.date, *, hard: bool
    ) -> tuple[Game, bool]:
        """Fetch or create today's daily game.

        Returns ``(game, created)``. An existing board for today is returned
        untouched, so ``/cordle daily`` is safe to run twice.
        """
        number = words.puzzle_number(day)
        existing = self.get(user_id, Mode.DAILY)
        if existing is not None and existing.puzzle_number == number:
            self.touch(user_id, Mode.DAILY)
            return existing, False

        game = Game(
            answer=words.daily_answer(day),
            mode=Mode.DAILY,
            hard=hard,
            puzzle_number=number,
        )
        self.put(user_id, game)
        return game, True

    def start_practice(self, user_id: int, words: WordList, *, hard: bool) -> Game:
        """Start a fresh practice game, replacing any finished one.

        The caller is responsible for refusing when a practice game is still
        in progress; this method always creates.
        """
        game = Game(answer=words.random_answer(), mode=Mode.PRACTICE, hard=hard)
        self.put(user_id, game)
        return game

    def prune(self, current_puzzle_number: int) -> int:
        """Drop daily games from previous days. Returns how many were removed."""
        stale = [
            key
            for key, game in self._games.items()
            if game.mode is Mode.DAILY and game.puzzle_number != current_puzzle_number
        ]
        for key in stale:
            del self._games[key]
        return len(stale)

    def __len__(self) -> int:
        return len(self._games)
