"""Slash commands for playing Cordle.

Boards are always sent ephemerally: the grid shows the letters you guessed,
so a public board would spoil the daily word for everyone else in the
channel. ``/share`` posts the colour-only grid publicly instead.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..game import Game, InvalidGuess, Mode, Status, WORD_LENGTH
from ..render import build_embed, render_share
from ..words import today

log = logging.getLogger(__name__)

MODE_CHOICES = [
    app_commands.Choice(name="Daily", value=Mode.DAILY.value),
    app_commands.Choice(name="Practice", value=Mode.PRACTICE.value),
]

HELP_TEXT = f"""
**Cordle** is Wordle in Discord. Guess the {WORD_LENGTH} letter word in 6 tries.

\N{LARGE GREEN SQUARE} right letter, right spot
\N{LARGE YELLOW SQUARE} right letter, wrong spot
\N{BLACK LARGE SQUARE} not in the word

**Commands**
`/cordle daily` - today's puzzle, the same word for everyone
`/cordle practice` - a random word, play as often as you like
`/guess <word>` - submit a guess
`/cordle board` - show your board again
`/share` - post your result grid to the channel
`/giveup` - reveal the answer and end the game

**Hard mode**
Pass `hard: True` when you start. Every hint you have revealed must be
reused in later guesses.

Your board is only visible to you. Only `/share` is public.
""".strip()


class Play(commands.Cog):
    """Everything a player interacts with."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Started here rather than in __init__ so the loop never outlives a
        # cog that failed to attach.
        self.prune_stale.start()

    async def cog_unload(self) -> None:
        self.prune_stale.cancel()

    @tasks.loop(hours=6)
    async def prune_stale(self) -> None:
        """Drop yesterday's daily boards so memory does not grow forever."""
        number = self.bot.words.puzzle_number(self._today())
        removed = self.bot.store.prune(number)
        if removed:
            log.info("pruned %d stale daily game(s)", removed)

    @prune_stale.before_loop
    async def _before_prune(self) -> None:
        await self.bot.wait_until_ready()

    # ---- helpers -------------------------------------------------------

    def _today(self):
        return today(self.bot.config.utc_offset_hours)

    def _resolve_mode(
        self, user_id: int, choice: Optional[app_commands.Choice[str]]
    ) -> Optional[Game]:
        """Pick which board a command applies to.

        With an explicit choice, use that. Otherwise fall back to whichever
        board the player last touched, preferring one still in progress.
        """
        if choice is not None:
            return self.bot.store.get(user_id, Mode(choice.value))
        return self.bot.store.active(user_id)

    async def _send_board(
        self,
        interaction: discord.Interaction,
        game: Game,
        *,
        content: str | None = None,
    ) -> None:
        await interaction.response.send_message(
            content=content,
            embed=build_embed(game, player=interaction.user),
            ephemeral=True,
        )

    # ---- /cordle -------------------------------------------------------

    group = app_commands.Group(name="cordle", description="Play Cordle")

    @group.command(name="daily", description="Play today's puzzle")
    @app_commands.describe(hard="Reuse every revealed hint in later guesses")
    async def daily(self, interaction: discord.Interaction, hard: bool = False) -> None:
        game, created = self.bot.store.start_daily(
            interaction.user.id, self.bot.words, self._today(), hard=hard
        )

        if not created and game.status.is_over:
            await self._send_board(
                interaction,
                game,
                content=(
                    "You have already finished today's puzzle. "
                    "Try `/cordle practice` for another word."
                ),
            )
            return

        note = None
        if not created:
            note = "Resuming today's puzzle."
        elif hard:
            note = "Hard mode is on."
        await self._send_board(interaction, game, content=note)

    @group.command(name="practice", description="Play a random word")
    @app_commands.describe(hard="Reuse every revealed hint in later guesses")
    async def practice(
        self, interaction: discord.Interaction, hard: bool = False
    ) -> None:
        existing = self.bot.store.get(interaction.user.id, Mode.PRACTICE)
        if existing is not None and not existing.status.is_over:
            await self._send_board(
                interaction,
                existing,
                content=(
                    "You already have a practice game going. Finish it, "
                    "or end it with `/giveup`."
                ),
            )
            return

        game = self.bot.store.start_practice(
            interaction.user.id, self.bot.words, hard=hard
        )
        await self._send_board(
            interaction, game, content="Hard mode is on." if hard else None
        )

    @group.command(name="board", description="Show your current board")
    @app_commands.choices(mode=MODE_CHOICES)
    async def board(
        self,
        interaction: discord.Interaction,
        mode: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        game = self._resolve_mode(interaction.user.id, mode)
        if game is None:
            await interaction.response.send_message(
                "You have no game yet. Start one with `/cordle daily`.",
                ephemeral=True,
            )
            return
        self.bot.store.touch(interaction.user.id, game.mode)
        await self._send_board(interaction, game)

    @group.command(name="help", description="How to play")
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="How to play Cordle",
            description=HELP_TEXT,
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---- /guess --------------------------------------------------------

    @app_commands.command(name="guess", description="Submit a Cordle guess")
    @app_commands.describe(word=f"A {WORD_LENGTH} letter word", mode="Which board")
    @app_commands.choices(mode=MODE_CHOICES)
    async def guess(
        self,
        interaction: discord.Interaction,
        word: str,
        mode: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        game = self._resolve_mode(interaction.user.id, mode)
        if game is None:
            await interaction.response.send_message(
                "Start a game first with `/cordle daily`.", ephemeral=True
            )
            return
        if game.status.is_over:
            await interaction.response.send_message(
                "That game is already finished. Start another with "
                "`/cordle practice`.",
                ephemeral=True,
            )
            return

        word = word.strip().lower()
        if len(word) != WORD_LENGTH:
            await interaction.response.send_message(
                f"**{word.upper()}** is {len(word)} letters. "
                f"Guesses must be {WORD_LENGTH}.",
                ephemeral=True,
            )
            return
        if not self.bot.words.is_valid_guess(word):
            await interaction.response.send_message(
                f"**{word.upper()}** is not in the word list.", ephemeral=True
            )
            return

        try:
            game.submit(word)
        except InvalidGuess as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        self.bot.store.touch(interaction.user.id, game.mode)
        hint = "Use `/share` to post your grid." if game.status.is_over else None
        await self._send_board(interaction, game, content=hint)

    @guess.autocomplete("word")
    async def guess_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest real words as the player types, so guesses are never rejected."""
        current = current.strip().lower()
        if not current:
            return []
        matches = self.bot.words.suggest(current, limit=25)
        return [app_commands.Choice(name=w, value=w) for w in matches]

    # ---- /giveup and /share --------------------------------------------

    @app_commands.command(
        name="giveup", description="Reveal the answer and end the game"
    )
    @app_commands.choices(mode=MODE_CHOICES)
    async def giveup(
        self,
        interaction: discord.Interaction,
        mode: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        game = self._resolve_mode(interaction.user.id, mode)
        if game is None or game.status.is_over:
            await interaction.response.send_message(
                "You have no game in progress to give up on.", ephemeral=True
            )
            return

        game.resign()
        self.bot.store.touch(interaction.user.id, game.mode)
        await self._send_board(interaction, game)

    @app_commands.command(
        name="share", description="Post your result grid to the channel"
    )
    @app_commands.choices(mode=MODE_CHOICES)
    async def share(
        self,
        interaction: discord.Interaction,
        mode: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        game = self._resolve_mode(interaction.user.id, mode)
        if game is None:
            await interaction.response.send_message(
                "You have nothing to share yet.", ephemeral=True
            )
            return
        if not game.status.is_over:
            await interaction.response.send_message(
                "Finish the game first - sharing mid-game would give away "
                "your progress.",
                ephemeral=True,
            )
            return
        if game.status is Status.RESIGNED:
            await interaction.response.send_message(
                "You gave up on that one, so there is no grid to share.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"{interaction.user.mention}\n```\n{render_share(game)}\n```"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Play(bot))
