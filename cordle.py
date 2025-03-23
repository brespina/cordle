"""
__author__: bwandii
__created__: 2025/03/23
__description__: a for fun coding project where i make the game wordle
                 but in discord
"""

import discord
from discord import Embed, Color
from discord.ext import commands
import random

# you will need your own bot token
from cordle_token import get_token


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

with open("past_answers.txt", "r") as f:
    valid_guesses = [guess.strip().lower() for guess in f.readlines()]

active_quests = {}
alphabet = [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "m",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
]


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)


def create_cordle_embed(user_id, quit=False):
    quest = active_quests[user_id]
    target = quest["target"]
    guesses = quest["guesses"]
    user_valid_letters = alphabet
    board = []

    for guess in guesses:
        row = []
        for i, letter in enumerate(guess):
            if letter == target[i]:
                row.append("🟩")
            elif letter in target:
                row.append("🟨")
            else:
                if letter in user_valid_letters:
                    user_valid_letters.remove(letter)
                row.append("⬛")

        board.append(f"{''.join(row)}  {' '.join(guess.upper())}")

    for _ in range(quest["attempts"] - len(guesses)):
        board.append("⬜⬜⬜⬜⬜  _ _ _ _ _")
    #     embed = Embed(
    #         title="Your Guesses",
    #         description="```\n" + "\n".join(board) + "\n```",
    #         color=Color.blue(),
    #     )
    embed = Embed(
        title="Cordle",
        description="```\n" + "\n".join(board) + "\n```",
        color=Color.green(),
    )
    if quit is True:
        embed.add_field(
            name="Nice Try!",
            value=f"The word was \n🟩 {' '.join(target).upper()} 🟩",
        )
    embed.add_field(name="letters left", value=user_valid_letters)
    embed.set_footer(text=f"Guesses left: {quest['attempts'] - len(guesses)}")
    return embed


@bot.tree.command(name="give_up", description="Quit active Cordle quest")
async def give_up(interaction: discord.Interaction):
    user_id = interaction.user.id
    quit = True
    embed = create_cordle_embed(user_id, quit)
    await interaction.response.send_message(
        f"😢 You Quit! The word was **{active_quests[user_id]['target']}**", embed=embed
    )
    del active_quests[user_id]


@bot.tree.command(name="cordle", description="Start a Cordle quest")
async def cordle(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in active_quests:
        await interaction.response.send_message(
            "You already have active Cordle quests!", ephemeral=True
        )
        return

    target = random.choice(valid_guesses)
    active_quests[user_id] = {
        "target": target,
        "guesses": [],
        "attempts": 6,
    }

    embed = create_cordle_embed(user_id)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="guess", description="Submit a Cordle quest guess")
async def guess(interaction: discord.Interaction, guess: str):
    user_id = interaction.user.id
    if user_id not in active_quests:
        await interaction.response.send_message(
            "Start a Cordle quest first with `/cordle`!", ephemeral=True
        )
        return

    quest = active_quests[user_id]
    guess = guess.lower()

    if len(guess) != 5:
        await interaction.response.send_message(
            "Guess must be 5 letters!", ephemeral=True
        )
        return
    if guess not in valid_guesses:
        await interaction.response.send_message("Not a valid guess", ephemeral=True)
        return

    quest["guesses"].append(guess)
    embed = create_cordle_embed(user_id)

    if guess == quest["target"]:
        await interaction.response.send_message(
            f"🎉 You are victorious! The word was **{quest['target']}**", embed=embed
        )
        del active_quests[user_id]
    elif len(quest["guesses"]) >= quest["attempts"]:
        await interaction.response.send_message(
            f"😢 You lost! The word was **{guess['target']}**", embed=embed
        )
        del active_quests[user_id]
    else:
        await interaction.response.send_message(embed=embed)


bot.run(get_token())
