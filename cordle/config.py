"""Runtime configuration, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when the environment is missing something the bot needs."""


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _int_env(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class Config:
    token: str
    #: Hours to shift UTC by when deciding which day's puzzle is current.
    utc_offset_hours: float = 0.0
    #: Sync slash commands to this guild for instant availability while
    #: developing. Global sync can take up to an hour to propagate.
    dev_guild_id: int | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        token = os.getenv("CORDLE_TOKEN", "").strip()
        if not token:
            raise ConfigError(
                "CORDLE_TOKEN is not set. Copy .env.example to .env and add "
                "your bot token."
            )
        return cls(
            token=token,
            utc_offset_hours=_float_env("CORDLE_UTC_OFFSET_HOURS", 0.0),
            dev_guild_id=_int_env("CORDLE_DEV_GUILD_ID"),
            log_level=os.getenv("CORDLE_LOG_LEVEL", "INFO").upper(),
        )
