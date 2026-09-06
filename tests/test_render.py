"""Tests for board and share-grid formatting."""

from __future__ import annotations

from cordle.game import Game, Mode
from cordle.render import (
    EMPTY_EMOJI,
    TILE_EMOJI,
    build_embed,
    outcome_text,
    render_board,
    render_keyboard,
    render_share,
    score_label,
)
from cordle.game import Tile

GREEN = TILE_EMOJI[Tile.CORRECT]
YELLOW = TILE_EMOJI[Tile.PRESENT]
BLACK = TILE_EMOJI[Tile.ABSENT]


class TestBoard:
    def test_empty_board_is_all_placeholder_rows(self):
        game = Game(answer="crane")
        assert render_board(game).count(EMPTY_EMOJI) == 6 * 5

    def test_played_rows_show_squares_and_letters(self):
        game = Game(answer="crane")
        game.submit("crane")
        first = render_board(game).splitlines()[0]
        assert first.startswith(GREEN * 5)
        assert "C R A N E" in first

    def test_row_count_always_matches_max_attempts(self):
        game = Game(answer="crane")
        game.submit("slate")
        game.submit("brick")
        assert len(render_board(game).splitlines()) == 6


class TestKeyboard:
    def test_no_guesses_yet(self):
        assert "No guesses yet" in render_keyboard(Game(answer="crane"))

    def test_groups_letters_by_state(self):
        game = Game(answer="crane")
        game.submit("slate")
        out = render_keyboard(game)
        assert GREEN in out or YELLOW in out
        assert BLACK in out

    def test_unused_letters_are_listed_and_not_shared_between_games(self):
        # Guards the aliasing bug in the original implementation.
        first = Game(answer="crane")
        first.submit("slate")
        second = Game(answer="crane")
        assert "S" not in render_keyboard(second)
        assert render_keyboard(second) == "_No guesses yet._"


class TestShare:
    def test_practice_grid_has_no_puzzle_number(self):
        game = Game(answer="crane", mode=Mode.PRACTICE)
        game.submit("crane")
        assert render_share(game).startswith("Cordle (practice) 1/6")

    def test_daily_grid_includes_the_puzzle_number(self):
        game = Game(answer="crane", mode=Mode.DAILY, puzzle_number=1234)
        game.submit("crane")
        assert render_share(game).splitlines()[0] == "Cordle 1,234 1/6"

    def test_hard_mode_is_starred(self):
        game = Game(answer="crane", mode=Mode.DAILY, puzzle_number=7, hard=True)
        game.submit("crane")
        assert render_share(game).splitlines()[0].endswith("1/6*")

    def test_loss_is_scored_x(self):
        game = Game(answer="crane", max_attempts=1)
        game.submit("slate")
        assert score_label(game) == "X/1"

    def test_grid_contains_only_colour_squares(self):
        game = Game(answer="crane")
        game.submit("slate")
        game.submit("crane")
        grid = render_share(game).splitlines()[1:]
        assert len(grid) == 2
        for line in grid:
            assert set(line) <= {GREEN, YELLOW, BLACK}


class TestOutcome:
    def test_none_while_in_progress(self):
        assert outcome_text(Game(answer="crane")) is None

    def test_loss_reveals_the_answer(self):
        game = Game(answer="crane", max_attempts=1)
        game.submit("slate")
        assert "CRANE" in outcome_text(game)

    def test_resign_reveals_the_answer(self):
        game = Game(answer="crane")
        game.resign()
        assert "CRANE" in outcome_text(game)

    def test_win_does_not_leak_the_answer_before_sharing(self):
        game = Game(answer="crane")
        game.submit("crane")
        assert "CRANE" not in outcome_text(game)


class TestEmbed:
    def test_in_progress_embed_shows_the_keyboard_not_the_answer(self):
        game = Game(answer="crane")
        game.submit("slate")
        embed = build_embed(game)
        assert [f.name for f in embed.fields] == ["Letters"]
        assert "CRANE" not in (embed.description or "")

    def test_finished_embed_offers_a_share_grid(self):
        game = Game(answer="crane")
        game.submit("crane")
        embed = build_embed(game)
        assert "Share" in [f.name for f in embed.fields]

    def test_footer_counts_remaining_guesses(self):
        game = Game(answer="crane")
        game.submit("slate")
        assert embed_footer(build_embed(game)) == "5 guesses left"

    def test_footer_is_singular_at_one_guess_left(self):
        game = Game(answer="crane", max_attempts=2)
        game.submit("slate")
        assert embed_footer(build_embed(game)) == "1 guess left"


def embed_footer(embed) -> str:
    return embed.footer.text
