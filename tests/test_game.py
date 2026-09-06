"""Tests for the pure game rules."""

from __future__ import annotations

import pytest

from cordle.game import (
    Game,
    InvalidGuess,
    Mode,
    Status,
    Tile,
    score_guess,
)

G, Y, B = Tile.CORRECT, Tile.PRESENT, Tile.ABSENT


def tiles(pattern: str) -> tuple[Tile, ...]:
    """Build an expected result from a ``GYB`` shorthand string."""
    lookup = {"G": G, "Y": Y, "B": B}
    return tuple(lookup[c] for c in pattern)


class TestScoreGuess:
    def test_exact_match_is_all_green(self):
        assert score_guess("crane", "crane") == tiles("GGGGG")

    def test_no_overlap_is_all_black(self):
        assert score_guess("crony", "smelt") == tiles("BBBBB")

    def test_mixed(self):
        # Every letter of CRANE appears in NACRE, and only the E lines up.
        assert score_guess("crane", "nacre") == tiles("YYYYG")

    # The bug the original implementation had: `elif letter in target`
    # painted every copy of a letter yellow regardless of how many the
    # answer actually contained.
    @pytest.mark.parametrize(
        "guess, answer, expected",
        [
            # One E in the answer, two in the guess: only one may be yellow.
            ("speed", "abide", "BBYBY"),
            # Answer has one L, guess has two, and one is already green.
            ("llama", "lemma", "GBBGG"),
            # Guess repeats a letter the answer does not have at all.
            ("geese", "abbot", "BBBBB"),
            # Two A's in the guess, two in the answer: one lands green,
            # the other can still be yellow.
            ("array", "banal", "YBBGB"),
            # Both copies genuinely present.
            ("mamma", "gamma", "BGGGG"),
        ],
    )
    def test_duplicate_letters(self, guess, answer, expected):
        assert score_guess(guess, answer) == tiles(expected)

    def test_greens_claim_letters_before_earlier_duplicates_do(self):
        # ABBEY has two B's. BOBBY spends one on a green at index 2, so of
        # the two remaining B's only the first can be yellow -- the one at
        # index 3 has nothing left to match and must be black.
        assert score_guess("bobby", "abbey") == tiles("YBGBG")

    def test_duplicate_in_guess_when_answer_has_one_copy(self):
        # ECLAT has a single L; only the first of the two L's scores.
        assert score_guess("llama", "eclat") == tiles("YBYBB")

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            score_guess("four", "fives")

    def test_number_of_coloured_tiles_never_exceeds_answer_counts(self):
        # Property check: for every letter, greens plus yellows must be at
        # most the number of times that letter appears in the answer.
        from collections import Counter

        answer = "eerie"
        for guess in ("eeeee", "beefy", "elite", "steer"):
            result = score_guess(guess, answer)
            counted = Counter(
                letter
                for letter, tile in zip(guess, result)
                if tile in (Tile.CORRECT, Tile.PRESENT)
            )
            answer_counts = Counter(answer)
            for letter, n in counted.items():
                assert n <= answer_counts[letter], (guess, letter)


class TestGameFlow:
    def test_win_sets_status_and_stops_further_guesses(self):
        game = Game(answer="crane")
        game.submit("slate")
        game.submit("crane")
        assert game.status is Status.WON
        assert game.attempts_used == 2
        with pytest.raises(InvalidGuess):
            game.submit("crane")

    def test_loss_after_max_attempts(self):
        game = Game(answer="crane", max_attempts=3)
        for word in ("slate", "brick", "pouch"):
            game.submit(word)
        assert game.status is Status.LOST
        assert game.attempts_left == 0

    def test_last_guess_correct_wins_rather_than_loses(self):
        # The original code raised TypeError on this path.
        game = Game(answer="crane", max_attempts=2)
        game.submit("slate")
        game.submit("crane")
        assert game.status is Status.WON

    def test_wrong_length_rejected(self):
        game = Game(answer="crane")
        with pytest.raises(InvalidGuess):
            game.submit("four")

    def test_non_alpha_rejected(self):
        game = Game(answer="crane")
        with pytest.raises(InvalidGuess):
            game.submit("ab-cd")

    def test_guess_is_normalised(self):
        game = Game(answer="crane")
        row = game.submit("  CRANE ")
        assert row.guess == "crane"
        assert game.status is Status.WON

    def test_resign(self):
        game = Game(answer="crane")
        game.resign()
        assert game.status is Status.RESIGNED
        with pytest.raises(InvalidGuess):
            game.resign()

    def test_defaults(self):
        game = Game(answer="crane")
        assert game.mode is Mode.PRACTICE
        assert game.hard is False
        assert game.attempts_left == 6


class TestLetterStates:
    def test_tracks_best_known_state_per_letter(self):
        game = Game(answer="crane")
        game.submit("erase")  # E yellow, R yellow, A green, S black, E green
        states = game.letter_states()
        assert states["a"] is Tile.CORRECT
        assert states["e"] is Tile.CORRECT
        assert states["s"] is Tile.ABSENT

    def test_green_is_not_downgraded_by_a_later_yellow(self):
        game = Game(answer="crane")
        game.submit("crane")
        game.rows.append(game.rows[0])  # not realistic, but exercises ranking
        assert game.letter_states()["c"] is Tile.CORRECT

    def test_unused_letters_are_per_game_not_shared(self):
        # The original code aliased and mutated a module level list, so the
        # alphabet was permanently consumed across every game and player.
        first = Game(answer="crane")
        first.submit("puppy")
        second = Game(answer="crane")
        assert len(second.unused_letters()) == 26
        assert "p" not in first.unused_letters()
        assert "p" in second.unused_letters()


class TestHardMode:
    def test_off_by_default(self):
        game = Game(answer="crane")
        game.submit("slate")
        assert game.hard_mode_violation("brick") is None

    def test_green_must_stay_in_place(self):
        game = Game(answer="crane", hard=True)
        game.submit("crony")  # C R green, N present
        violation = game.hard_mode_violation("blimp")
        assert violation is not None
        assert "letter 1" in violation

    def test_present_letter_must_be_reused(self):
        game = Game(answer="crane", hard=True)
        game.submit("nerdy")  # N present, E present, R present
        violation = game.hard_mode_violation("crumb")
        assert violation is not None
        assert "must contain" in violation

    def test_valid_hard_mode_guess_passes(self):
        game = Game(answer="crane", hard=True)
        game.submit("crony")
        assert game.hard_mode_violation("crane") is None

    def test_repeated_letter_count_is_enforced(self):
        game = Game(answer="mamma", hard=True)
        game.submit("mamba")  # three M positions revealed
        violation = game.hard_mode_violation("major")
        assert violation is not None

    def test_submit_rejects_hard_mode_violation(self):
        game = Game(answer="crane", hard=True)
        game.submit("crony")
        with pytest.raises(InvalidGuess):
            game.submit("blimp")
        assert game.attempts_used == 1  # the bad guess did not cost a turn

    def test_first_guess_is_always_allowed(self):
        game = Game(answer="crane", hard=True)
        assert game.hard_mode_violation("fjord") is None
