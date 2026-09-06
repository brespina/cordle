"""Tests for the in-memory game store."""

from __future__ import annotations

import datetime as dt

from cordle.game import Mode, Status
from cordle.store import GameStore
from cordle.words import load_words

USER = 1234
OTHER = 5678
DAY = dt.date(2026, 9, 5)


def store_and_words():
    return GameStore(), load_words()


class TestDaily:
    def test_first_call_creates_a_game(self):
        store, words = store_and_words()
        game, created = store.start_daily(USER, words, DAY, hard=False)
        assert created is True
        assert game.mode is Mode.DAILY
        assert game.puzzle_number == words.puzzle_number(DAY)

    def test_second_call_same_day_resumes_rather_than_resetting(self):
        store, words = store_and_words()
        first, _ = store.start_daily(USER, words, DAY, hard=False)
        first.submit("crane")
        second, created = store.start_daily(USER, words, DAY, hard=False)
        assert created is False
        assert second is first
        assert second.attempts_used == 1

    def test_a_new_day_starts_a_new_game(self):
        store, words = store_and_words()
        first, _ = store.start_daily(USER, words, DAY, hard=False)
        second, created = store.start_daily(
            USER, words, DAY + dt.timedelta(days=1), hard=False
        )
        assert created is True
        assert second is not first

    def test_players_get_the_same_word_but_separate_boards(self):
        store, words = store_and_words()
        mine, _ = store.start_daily(USER, words, DAY, hard=False)
        theirs, _ = store.start_daily(OTHER, words, DAY, hard=False)
        assert mine.answer == theirs.answer
        assert mine is not theirs
        mine.submit("crane")
        assert theirs.attempts_used == 0


class TestPractice:
    def test_each_start_is_a_fresh_game(self):
        store, words = store_and_words()
        first = store.start_practice(USER, words, hard=False)
        first.resign()
        second = store.start_practice(USER, words, hard=False)
        assert second is not first
        assert second.status is Status.IN_PROGRESS

    def test_hard_flag_is_carried_through(self):
        store, words = store_and_words()
        assert store.start_practice(USER, words, hard=True).hard is True


class TestActive:
    def test_returns_none_when_nothing_played(self):
        store, _ = store_and_words()
        assert store.active(USER) is None

    def test_prefers_the_most_recently_touched_board(self):
        store, words = store_and_words()
        store.start_daily(USER, words, DAY, hard=False)
        practice = store.start_practice(USER, words, hard=False)
        assert store.active(USER) is practice
        store.touch(USER, Mode.DAILY)
        assert store.active(USER).mode is Mode.DAILY

    def test_prefers_an_unfinished_board_over_a_finished_one(self):
        store, words = store_and_words()
        daily, _ = store.start_daily(USER, words, DAY, hard=False)
        practice = store.start_practice(USER, words, hard=False)
        practice.resign()  # most recent, but over
        assert store.active(USER) is daily

    def test_falls_back_to_a_finished_board_when_all_are_over(self):
        store, words = store_and_words()
        practice = store.start_practice(USER, words, hard=False)
        practice.resign()
        assert store.active(USER) is practice

    def test_finished_games_are_kept_so_share_still_works(self):
        store, words = store_and_words()
        game, _ = store.start_daily(USER, words, DAY, hard=False)
        game.resign()
        assert store.get(USER, Mode.DAILY) is game


class TestPrune:
    def test_removes_only_stale_dailies(self):
        store, words = store_and_words()
        store.start_daily(USER, words, DAY, hard=False)
        store.start_practice(USER, words, hard=False)
        current = words.puzzle_number(DAY + dt.timedelta(days=1))

        assert store.prune(current) == 1
        assert store.get(USER, Mode.DAILY) is None
        assert store.get(USER, Mode.PRACTICE) is not None

    def test_keeps_todays_daily(self):
        store, words = store_and_words()
        store.start_daily(USER, words, DAY, hard=False)
        assert store.prune(words.puzzle_number(DAY)) == 0
        assert store.get(USER, Mode.DAILY) is not None
