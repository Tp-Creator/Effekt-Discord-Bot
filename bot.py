import discord
import discord.ext.commands
import os
import atexit

from typing import *
from shared_memory_dict import SharedMemoryDict
import public_ip as ip
from dotenv import load_dotenv

smd = SharedMemoryDict(name="config", size=1000000)

smd["commandStack"] = []
smd["contentStack"] = []

# fetching and printing public ip adress
print("Public ip:", ip.get())

# Bot loading
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("DISCORD_GUILD_ID")
CHANNEL = os.getenv("DISCORD_CONSOLE_CHANNEL_ID")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.ext.commands.Bot(command_prefix=".", intents=intents)
# client = discord.Client(intents=intents)

####


def checkIpChange():
    ipNow = ip.get()

    with open("", "r") as lastIp:
        if not lastIp.read == ipNow:
            pass


# ETSTSTSTST
async def sendToConsole(msg):
    await bot.get_channel(int(CHANNEL)).send(msg)


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    await bot.tree.sync(guild=discord.Object(id=GUILD))


@bot.command()
async def ping(ctx):
    await ctx.channel.send("Pong!")


@bot.event
async def on_message(msg):
    await bot.process_commands(msg)
    while len(smd["contentStack"]) >= 1:
        stack = smd["contentStack"]
        content = stack.pop(0)
        smd["contentStack"] = stack
        print(smd, content)
        await bot.get_channel(int(CHANNEL)).send(content)


@bot.tree.command(
    name="whitelist", description="whitelist {username}", guild=discord.Object(GUILD)
)
@discord.app_commands.choices(
    action=[
        discord.app_commands.Choice(name="list", value="list"),
        discord.app_commands.Choice(name="add", value="add"),
        discord.app_commands.Choice(name="remove", value="remove"),
        discord.app_commands.Choice(name="on", value="on"),
        discord.app_commands.Choice(name="off", value="off"),
    ]
)
async def whitelist(
    interaction: discord.Interaction,
    action: discord.app_commands.Choice[str],
    player: Optional[str] = None,
):
    print(f"whitelist {action.value}{' '+player if player else ''}")
    smd["commandStack"] = smd["commandStack"] + [
        f"whitelist {action.value}{' '+player if player else ''}"
    ]
    await interaction.response.send_message(
        f"whitelist {action.value}{' '+player if player else ''}", ephemeral=True
    )


@bot.tree.command(
    name="ip",
    description="Fetch the current public ip adress for the minecraft server",
    guild=discord.Object(GUILD),
)
async def get_ip(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"The current ip adress should be: **{ip.get()}**", ephemeral=False
    )


@bot.tree.command(
    name="stop",
    description="Stopping the minecraft server",
    guild=discord.Object(GUILD),
)
async def stop(interaction: discord.Interaction):
    print(f"stop")
    smd["commandStack"] = smd["commandStack"] + [f"stop"]
    await interaction.response.send_message(f"Stopping the server...", ephemeral=False)


def exit_handler():
    global smd
    smd.shm.close()
    smd.shm.unlink()
    del smd


atexit.register(exit_handler)

# Start bot
if TOKEN != None:
    bot.run(TOKEN)
else:
    print("Could not connect to Discord! TOKEN for Discord bot was None!")
