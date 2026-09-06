# cordle

Wordle, as a Discord bot.

## Play

| command | what it does |
| --- | --- |
| `/cordle daily` | today's puzzle — the same word for everyone, worldwide |
| `/cordle practice` | a random word, as many times as you like |
| `/guess <word>` | submit a guess (with autocomplete over the full word list) |
| `/cordle board` | show your board again |
| `/share` | post your emoji result grid to the channel |
| `/giveup` | reveal the answer and end the game |
| `/cordle help` | how to play |

Both modes accept `hard: True`, which requires every revealed hint to be
reused in later guesses.

Boards are **ephemeral** — only you see them. That matters because the board
shows the letters you guessed, so a public board would spoil the daily word
for the rest of the channel. `/share` posts the colour-only grid publicly.

## Setup

```sh
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate elsewhere
pip install -e ".[dev]"

cp .env.example .env          # then paste your bot token into CORDLE_TOKEN
python -m cordle
```

The bot uses slash commands only, so it needs **no privileged intents**.
Invite it with the `applications.commands` scope.

### Configuration

All optional except the token. See `.env.example`.

| variable | default | purpose |
| --- | --- | --- |
| `CORDLE_TOKEN` | *required* | bot token |
| `CORDLE_UTC_OFFSET_HOURS` | `0` | shift the daily rollover off UTC midnight |
| `CORDLE_DEV_GUILD_ID` | *unset* | sync commands to one guild for instant testing |
| `CORDLE_LOG_LEVEL` | `INFO` | log verbosity |

Global command sync can take up to an hour to propagate. Set
`CORDLE_DEV_GUILD_ID` while developing and commands appear immediately.

## Layout

```
cordle/
  game.py      pure rules: scoring, hard mode, win/loss. no discord imports
  words.py     word lists, daily selection, autocomplete ranking
  render.py    boards, keyboards, share grids, embeds
  store.py     in-memory games
  bot.py       the client
  cogs/play.py slash commands
  data/        answers.txt (2,315) + allowed_guesses.txt (10,657)
tests/         84 tests, no network or event loop needed
```

`game.py` is deliberately free of Discord imports so the rules — especially
duplicate-letter scoring, which is the part everyone gets wrong — can be
tested as plain functions.

```sh
pytest
```

## Notes

**Word lists.** Two lists, mirroring how Wordle itself ships: 2,315 curated
answers, plus 10,657 further words accepted as guesses but never chosen as
the target. Guessing an ordinary English word no longer gets rejected.
Source: [cfreshman's gists](https://gist.github.com/cfreshman).

**Daily words** are derived from the date via a fixed shuffle of the answer
pool, so every player gets the same word, a restart resumes the same puzzle,
and no word repeats until all 2,315 have been used — a little over six years.
`DAILY_EPOCH` and `DAILY_SEED` in `words.py` define that ordering; changing
either reshuffles every future puzzle.

**State is in memory.** Games are lost on restart. The daily *word* is not,
since it is computed from the date rather than stored.
