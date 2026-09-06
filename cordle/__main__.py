"""Entry point: ``python -m cordle``."""

from __future__ import annotations

import logging
import sys

import discord

from .bot import CordleBot
from .config import Config, ConfigError


def main() -> int:
    try:
        config = Config.from_env()
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    discord.utils.setup_logging(level=getattr(logging, config.log_level, logging.INFO))

    bot = CordleBot(config)
    try:
        bot.run(config.token, log_handler=None)
    except discord.LoginFailure:
        print("login failed: CORDLE_TOKEN was rejected by Discord.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
