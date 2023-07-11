import discord
import discord.ext.commands
import discord.ext.tasks
import os
import atexit

from typing import *
import public_ip as ip
from dotenv import load_dotenv
from multiprocessing import Process, Pipe


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


class Bot(discord.ext.commands.Bot):
    def __init__(self, *args, **kwargs):
        self.child_conn = None
        super().__init__(*args, **kwargs)

    def set_connection(self, child_conn):
        self.child_conn = child_conn

    def get_connection(self):
        return self.child_conn


bot = Bot(command_prefix=".", intents=intents)


# function to start the bot and save connection to parent process
def startBot(child_conn):
    # Start bot
    if TOKEN != None:
        bot.set_connection(child_conn=child_conn)
        bot.run(TOKEN)
    else:
        print("Could not connect to Discord! TOKEN for Discord bot was None!")


@discord.ext.tasks.loop(seconds=1)
async def loop():
    # check for content from parent process
    if bot.get_connection().poll(timeout=0.2):
        com = bot.get_connection().recv()

        if com.startswith("send:"):
            try:
                await bot.get_channel(int(CHANNEL)).send(com[5:])
            except Exception as e:
                await bot.get_channel(int(CHANNEL)).send(
                    "Something tried to send:\n" + str(e)
                )


def checkIpChange():
    ipNow = ip.get()

    with open("", "r") as lastIp:
        if not lastIp.read == ipNow:
            pass


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    await bot.tree.sync(guild=discord.Object(id=GUILD))
    loop.start()

    # global connection
    print("\n" * 2)
    print(bot.get_connection().recv())
    print("\n" * 2)


@bot.command()
async def ping(ctx):
    await ctx.channel.send("Pong!")


@bot.event
async def on_message(msg):
    # check who sent the message
    if msg.author == bot.user:
        return

    if int(msg.channel.id) == int(CHANNEL):
        bot.get_connection().send("mc:" + msg.content)

    await bot.process_commands(msg)


# @bot.tree.command(
#     name="whitelist", description="whitelist {username}", guild=discord.Object(GUILD)
# )
# @discord.app_commands.choices(
#     action=[
#         discord.app_commands.Choice(name="list", value="list"),
#         discord.app_commands.Choice(name="add", value="add"),
#         discord.app_commands.Choice(name="remove", value="remove"),
#         discord.app_commands.Choice(name="on", value="on"),
#         discord.app_commands.Choice(name="off", value="off"),
#     ]
# )
# async def whitelist(
#     interaction: discord.Interaction,
#     action: discord.app_commands.Choice[str],
#     player: Optional[str] = None,
# ):
#     print(f"whitelist {action.value}{' '+player if player else ''}")
#     smd["commandStack"] = smd["commandStack"] + [
#         f"whitelist {action.value}{' '+player if player else ''}"
#     ]
#     await interaction.response.send_message(
#         f"whitelist {action.value}{' '+player if player else ''}", ephemeral=True
#     )


@bot.tree.command(
    name="ip",
    description="Fetch the current public ip adress for the minecraft server",
    guild=discord.Object(GUILD),
)
async def get_ip(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"The current ip adress should be: **{ip.get()}**", ephemeral=False
    )


if __name__ == "__main__":
    # Start bot
    if TOKEN != None:
        bot.run(TOKEN)
    else:
        print("Could not connect to Discord! TOKEN for Discord bot was None!")
