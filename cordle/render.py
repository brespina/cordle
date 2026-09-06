"""Turning a :class:`~cordle.game.Game` into things Discord can display.

Kept separate from the command layer so board formatting can be tested as
plain strings.
"""

from __future__ import annotations

import discord

from .game import Game, Mode, Status, Tile, WORD_LENGTH

TILE_EMOJI: dict[Tile, str] = {
    Tile.CORRECT: "\N{LARGE GREEN SQUARE}",
    Tile.PRESENT: "\N{LARGE YELLOW SQUARE}",
    Tile.ABSENT: "\N{BLACK LARGE SQUARE}",
}
EMPTY_EMOJI = "\N{WHITE LARGE SQUARE}"

COLOR_IN_PROGRESS = discord.Color.blurple()
COLOR_WON = discord.Color.green()
COLOR_LOST = discord.Color.red()


def render_row(row) -> str:
    """One played row: colour squares, then the letters that earned them."""
    squares = "".join(TILE_EMOJI[tile] for tile in row.tiles)
    letters = " ".join(row.guess.upper())
    return f"{squares}  `{letters}`"


def render_board(game: Game) -> str:
    """The full board, padded out with blank rows for remaining guesses."""
    lines = [render_row(row) for row in game.rows]
    blank = EMPTY_EMOJI * WORD_LENGTH
    placeholder = " ".join("\N{HEAVY MINUS SIGN}" for _ in range(WORD_LENGTH))
    for _ in range(game.attempts_left):
        lines.append(f"{blank}  `{placeholder}`")
    return "\n".join(lines)


def render_keyboard(game: Game) -> str:
    """Letter knowledge, grouped by what we have learned about each letter.

    Replaces the original "letters left" field, which mutated a shared list
    and rendered a raw Python repr.
    """
    states = game.letter_states()
    if not states:
        return "_No guesses yet._"

    buckets: dict[Tile, list[str]] = {Tile.CORRECT: [], Tile.PRESENT: [], Tile.ABSENT: []}
    for letter, tile in sorted(states.items()):
        buckets[tile].append(letter.upper())

    lines = []
    for tile in (Tile.CORRECT, Tile.PRESENT, Tile.ABSENT):
        if buckets[tile]:
            lines.append(f"{TILE_EMOJI[tile]} `{' '.join(buckets[tile])}`")

    unused = game.unused_letters()
    if unused:
        lines.append(f"{EMPTY_EMOJI} `{' '.join(l.upper() for l in unused)}`")
    return "\n".join(lines)


def score_label(game: Game) -> str:
    """The ``4/6`` style score, with ``X`` for a loss and ``*`` for hard mode."""
    used = str(game.attempts_used) if game.status is Status.WON else "X"
    return f"{used}/{game.max_attempts}{'*' if game.hard else ''}"


def render_share(game: Game) -> str:
    """The spoiler free emoji grid players paste elsewhere."""
    if game.mode is Mode.DAILY and game.puzzle_number is not None:
        header = f"Cordle {game.puzzle_number:,} {score_label(game)}"
    else:
        header = f"Cordle (practice) {score_label(game)}"
    grid = "\n".join(
        "".join(TILE_EMOJI[tile] for tile in row.tiles) for row in game.rows
    )
    return f"{header}\n{grid}" if grid else header


def _title(game: Game) -> str:
    if game.mode is Mode.DAILY and game.puzzle_number is not None:
        base = f"Cordle {game.puzzle_number:,}"
    else:
        base = "Cordle \N{EM DASH} Practice"
    return f"{base} (hard mode)" if game.hard else base


def _color(game: Game) -> discord.Color:
    if game.status is Status.WON:
        return COLOR_WON
    if game.status in (Status.LOST, Status.RESIGNED):
        return COLOR_LOST
    return COLOR_IN_PROGRESS


PRAISE = {
    1: "Genius",
    2: "Magnificent",
    3: "Impressive",
    4: "Splendid",
    5: "Great",
    6: "Phew",
}


def outcome_text(game: Game) -> str | None:
    """The line shown under a finished board, or None while still playing."""
    if game.status is Status.WON:
        return f"\N{PARTY POPPER} **{PRAISE.get(game.attempts_used, 'Solved')}!**"
    if game.status is Status.LOST:
        return f"\N{CROSS MARK} Out of guesses. The word was **{game.answer.upper()}**."
    if game.status is Status.RESIGNED:
        return f"\N{WHITE FLAG} You gave up. The word was **{game.answer.upper()}**."
    return None


def build_embed(game: Game, *, player: discord.abc.User | None = None) -> discord.Embed:
    """Assemble the board embed for any game state."""
    embed = discord.Embed(
        title=_title(game),
        description=render_board(game),
        color=_color(game),
    )

    outcome = outcome_text(game)
    if outcome:
        embed.add_field(name="\u200b", value=outcome, inline=False)
        embed.add_field(name="Share", value=f"```\n{render_share(game)}\n```", inline=False)
    else:
        embed.add_field(name="Letters", value=render_keyboard(game), inline=False)

    if player is not None:
        embed.set_author(name=player.display_name, icon_url=player.display_avatar.url)

    if game.status.is_over:
        embed.set_footer(text=f"Final: {score_label(game)}")
    else:
        left = game.attempts_left
        embed.set_footer(text=f"{left} guess{'' if left == 1 else 'es'} left")
    return embed
