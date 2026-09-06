"""Tests for word list loading and daily puzzle selection."""

from __future__ import annotations

import datetime as dt

import pytest

from cordle.game import WORD_LENGTH
from cordle.words import DAILY_EPOCH, WordList, load_words, today


@pytest.fixture(scope="module")
def words() -> WordList:
    return load_words()


class TestBundledLists:
    def test_every_word_is_the_right_shape(self, words):
        for word in words.valid_guesses:
            assert len(word) == WORD_LENGTH
            assert word.isalpha() and word.isascii() and word.islower()

    def test_guess_pool_is_much_larger_than_the_answer_pool(self, words):
        # The original bot only accepted the 2,315 answers, so ordinary
        # English words were rejected as invalid.
        assert len(words.answers) > 2000
        assert len(words.valid_guesses) > 12000

    def test_answers_are_always_legal_guesses(self, words):
        for answer in words.answers:
            assert words.is_valid_guess(answer)

    def test_is_valid_guess_normalises_input(self, words):
        assert words.is_valid_guess("  CRANE  ")
        assert not words.is_valid_guess("zzzzz")

    def test_no_duplicate_answers(self, words):
        assert len(set(words.answers)) == len(words.answers)


class TestDaily:
    def test_same_day_gives_same_word(self, words):
        day = dt.date(2026, 9, 5)
        assert words.daily_answer(day) == words.daily_answer(day)

    def test_word_comes_from_the_answer_pool(self, words):
        day = dt.date(2026, 9, 5)
        assert words.daily_answer(day) in words.answers

    def test_puzzle_number_counts_from_the_epoch(self, words):
        assert words.puzzle_number(DAILY_EPOCH) == 0
        assert words.puzzle_number(DAILY_EPOCH + dt.timedelta(days=42)) == 42

    def test_consecutive_days_differ(self, words):
        day = dt.date(2026, 9, 5)
        picks = [words.daily_answer(day + dt.timedelta(days=i)) for i in range(30)]
        assert len(set(picks)) == 30

    def test_no_repeat_until_the_pool_is_exhausted(self, words):
        # The shuffled ordering should walk the whole answer list before
        # coming back around.
        n = len(words.answers)
        picks = {words.daily_answer(DAILY_EPOCH + dt.timedelta(days=i)) for i in range(n)}
        assert len(picks) == n

    def test_selection_survives_a_restart(self, words):
        # A freshly constructed WordList must agree with the cached one,
        # which is what makes the daily word safe to keep out of storage.
        fresh = WordList(answers=words.answers, allowed=())
        day = dt.date(2026, 9, 5)
        assert fresh.daily_answer(day) == words.daily_answer(day)


class TestToday:
    def test_offset_shifts_the_date(self):
        now = dt.datetime.now(dt.timezone.utc)
        assert today(0.0) == now.date()
        # A large enough offset must land on a different calendar day.
        assert today(+48.0) != today(-48.0)


class TestLoadingRejectsBadData:
    def test_wrong_length_word_is_rejected(self, tmp_path):
        from cordle.words import _load

        path = tmp_path / "bad.txt"
        path.write_text("crane\ntoolong\n", encoding="utf-8")
        with pytest.raises(ValueError, match="toolong"):
            _load(path)

    def test_blanks_and_comments_are_skipped(self, tmp_path):
        from cordle.words import _load

        path = tmp_path / "ok.txt"
        path.write_text("# header\n\ncrane\n  SLATE  \n", encoding="utf-8")
        assert _load(path) == ("crane", "slate")

    def test_empty_file_is_rejected(self, tmp_path):
        from cordle.words import _load

        path = tmp_path / "empty.txt"
        path.write_text("\n# nothing\n", encoding="utf-8")
        with pytest.raises(ValueError, match="no usable words"):
            _load(path)


class TestSuggest:
    def test_common_words_are_offered_first(self, words):
        # Alphabetical order alone would lead with obscure entries like
        # "craal"; the curated answer pool should come first.
        top = words.suggest("cra", limit=8)
        assert "crane" in top
        assert "craal" not in top

    def test_respects_the_limit(self, words):
        assert len(words.suggest("s", limit=25)) == 25

    def test_every_suggestion_is_a_legal_guess(self, words):
        for word in words.suggest("qu", limit=25):
            assert words.is_valid_guess(word)

    def test_falls_through_to_the_long_tail_when_needed(self, words):
        # Few or no answers start with "aa", so the guess-only list fills in.
        assert words.suggest("aa", limit=25)

    def test_empty_prefix_suggests_nothing(self, words):
        assert words.suggest("", limit=25) == []

    def test_unknown_prefix_suggests_nothing(self, words):
        assert words.suggest("zzz", limit=25) == []

    def test_no_duplicates(self, words):
        out = words.suggest("b", limit=25)
        assert len(set(out)) == len(out)
