import discord
import discord.ext.commands
import discord.ext.tasks
import os
import public_ip as ip

from typing import *
from dotenv import load_dotenv
from abc import ABC, abstractmethod

# fetching and printing public ip adress
print("Public ip:", ip.get())

# Bot loading
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") or "0"
GUILD = os.getenv("DISCORD_GUILD_ID") or "0"
CHANNEL = os.getenv("DISCORD_CONSOLE_CHANNEL_ID") or "0"

if "0" in [TOKEN, GUILD, CHANNEL]:
    raise EnvironmentError("One or many environment variable(s) missing!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class ConnectionInterface(ABC):
    @abstractmethod
    def recv(*args, **kwargs) -> str:
        pass

    @abstractmethod
    def send(*args, **kwargs):
        pass

    @abstractmethod
    def poll(*args, **kwargs):
        pass


class Bot(discord.ext.commands.Bot):
    def __init__(self, *args, **kwargs):
        self.controller_connection = ConnectionInterface
        super().__init__(*args, **kwargs)

    def set_connection(self, controller_connection):
        self.controller_connection = controller_connection

    def get_connection(self):
        return self.controller_connection


bot = Bot(command_prefix=".", intents=intents)


# function to start the bot and save connection to parent process
def startBot(controller_connection):
    if TOKEN != None:
        bot.set_connection(controller_connection=controller_connection)
        bot.run(TOKEN)
    else:
        print("Could not connect to Discord! TOKEN for Discord bot was None!")


@discord.ext.tasks.loop(seconds=1)
async def loop():
    global konsol

    # check for content from parent process
    if bot.get_connection().poll(timeout=0.2):
        com = bot.get_connection().recv()

        if com.startswith("send:"):
            try:
                # Split messages into chunks of 2000 max to send them more easily
                if len(com[5:]) > 2000:
                    msg = com[5:]
                    while len(msg) > 2000:
                        splitPoint = msg[:2000].rfind("\n")
                        if splitPoint == -1:
                            splitPoint = 2000
                        await konsol.send(msg[:splitPoint])
                        msg = msg[splitPoint:]
                    await konsol.send(msg)
                else:
                    await konsol.send(com[5:])
            except Exception as e:
                await konsol.send("Something tried to send:\n" + str(e))


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")

    global konsol
    konsol = [
        channel
        for channel in bot.get_all_channels()
        if channel.name == "konsol"
        and int(channel.id) == int(CHANNEL)
        and not isinstance(channel, discord.ForumChannel)
        and not isinstance(channel, discord.CategoryChannel)
    ][0]

    await bot.tree.sync(guild=discord.Object(id=GUILD))
    await konsol.send("Went Online again!")
    loop.start()


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
    raise RuntimeError(
        'Bot can only be started by parent process. Try "python3 serverController.py"'
    )

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
