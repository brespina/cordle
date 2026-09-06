"""The Discord client."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from .config import Config
from .store import GameStore
from .words import WordList, load_words

log = logging.getLogger(__name__)

EXTENSIONS = ("cordle.cogs.play",)


class CordleBot(commands.Bot):
    """Bot wired up with the word lists and the game store.

    Only slash commands are used, so no message content intent is needed.
    Requesting fewer intents means the bot does not need privileged gateway
    access to be added to a server.
    """

    def __init__(self, config: Config) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.none(),
            help_command=None,
        )
        self.config = config
        self.words: WordList = load_words()
        self.store = GameStore()

    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            await self.load_extension(extension)
            log.info("loaded extension %s", extension)

        if self.config.dev_guild_id is not None:
            guild = discord.Object(id=self.config.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("synced %d command(s) to dev guild %s", len(synced), guild.id)
        else:
            synced = await self.tree.sync()
            log.info("synced %d command(s) globally", len(synced))

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info(
            "connected as %s (%d guild(s), %d words)",
            self.user,
            len(self.guilds),
            len(self.words),
        )
        await self.change_presence(
            activity=discord.Game(name="/cordle daily"),
        )
