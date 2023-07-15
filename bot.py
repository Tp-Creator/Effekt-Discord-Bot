import discord
import discord.ext.commands
import discord.ext.tasks
import os
import json
import datetime
import public_ip as ip

from typing import *
from dotenv import load_dotenv

# fetching and printing public ip adress
print("Public ip:", ip.get())

# Bot loading
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") or "0"
GUILD = os.getenv("DISCORD_GUILD_ID") or "0"
KONSOL_ID = os.getenv("DISCORD_CONSOLE_CHANNEL_ID") or "0"
IN_GAME_CHAT_ID = os.getenv("DISCORD_IN_GAME_CHAT_CHANNEL_ID") or "0"
SUPER_USERS = json.loads(os.getenv("DISCORD_SUPER_USERS") or "[]")

if "0" in [TOKEN, GUILD, KONSOL_ID, IN_GAME_CHAT_ID]:
    raise EnvironmentError("One or many environment variable(s) missing!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class ConnectionInterface:
    def recv(self, *args, **kwargs) -> str:
        return ""

    def send(self, *args: str, **kwargs) -> None:
        pass

    def poll(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass


class Bot(discord.ext.commands.Bot):
    def __init__(self, *args, **kwargs):
        self.controller_connection = ConnectionInterface()
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
        controller_connection.close()
        exit(0)
    else:
        print("Could not connect to Discord! TOKEN for Discord bot was None!")


@discord.ext.tasks.loop(seconds=1)
async def loop():
    global konsol

    # check for content from parent process
    if bot.get_connection().poll(timeout=0.2):
        com = bot.get_connection().recv()

        if com.startswith("konsol:") or com.startswith("log:"):
            is_log = int(com.startswith("log:"))
            try:
                begining = com.find(":") + 1
                # Split messages into chunks of 1950 max to send them more easily
                if len(com[begining:]) > 1950:
                    msg = com[begining:]
                    while len(msg) > 1950:
                        splitPoint = msg[:1950].rfind("\n")
                        if splitPoint == -1:
                            splitPoint = 1950
                        await konsol.send(
                            "```" * is_log + msg[:splitPoint] + "```" * is_log
                        )
                        msg = msg[splitPoint:]
                    await konsol.send("```" * is_log + msg + "```" * is_log)
                else:
                    await konsol.send("```" * is_log + com[begining:] + "```" * is_log)
            except Exception as e:
                await konsol.send("Something tried to send:\n" + str(e))

        if com.startswith("IGC:"):
            msgs = com[4:].split("\n")
            for msg in msgs:
                await bot.get_channel(int(IN_GAME_CHAT_ID)).send("`" + msg + "`")

        # send in specific channel
        elif com.startswith("chan,"):
            data = com[5:].split(":", 1)  # split at first ":" only
            await bot.get_channel(int(data[0])).send(data[1])

        elif com.startswith("dc:"):
            if com[3:] == "stop":
                await bot.close()


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")

    global konsol
    konsol = [
        channel
        for channel in bot.get_all_channels()
        if channel.name == "konsol"
        and int(channel.id) == int(KONSOL_ID)
        and not isinstance(channel, discord.ForumChannel)
        and not isinstance(channel, discord.CategoryChannel)
    ][0]

    await bot.tree.sync(guild=discord.Object(id=GUILD))
    await konsol.send("Connected to Discord")
    loop.start()


@bot.event
async def on_message(msg):
    # check who sent the message
    if msg.author == bot.user:
        return

    print(msg.content, msg.author.name, msg.channel.id)
    if int(msg.channel.id) == int(IN_GAME_CHAT_ID):
        # print("igc send")
        # print("user roles:", msg.author.roles)
        # print("user roles:", msg.author.roles[1].color)
        # for role in msg.author.roles:
        #     print("permission:", role.name, role.permissions, role.color)

        for role in msg.author.roles[::-1]:
            role_color = role.color
            if role_color != "#000000":
                break
        usr_name = msg.author.display_name
        role = msg.author.roles[-1]

        bot.get_connection().send(
            f"IGC:{len(usr_name)},{len(role.name)},{role_color},{usr_name},{role.name},{msg.content}"
        )

    if int(msg.channel.id) == int(KONSOL_ID) and msg.author.id in SUPER_USERS:
        bot.get_connection().send("mc:" + msg.content)

    await bot.process_commands(msg)  # Onödig För eventuella icke "/kommandon"


# Ping
@bot.tree.command(
    name="ping",
    description='Responds "Pong!"',
    guild=discord.Object(GUILD),
)
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)


# IP
@bot.tree.command(
    name="ip",
    description="Fetch the current public ip adress for the minecraft server",
    guild=discord.Object(GUILD),
)
async def get_ip(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"The current ip adress should be: **{ip.get()}**", ephemeral=False
    )


# Online
@bot.tree.command(
    name="online",
    description="Sends a list of all players that are online",
    guild=discord.Object(GUILD),
)
async def online_list(interaction: discord.Interaction):
    bot.get_connection().send(f"ctrl:online,{interaction.channel_id}")
    await interaction.response.send_message(f"Processing...", ephemeral=False)


# Status
@bot.tree.command(
    name="status",
    description="get status",
    guild=discord.Object(GUILD),
)
async def get_srv_status(interaction: discord.Interaction):
    if interaction.user.id in SUPER_USERS:
        bot.get_connection().send(f"srv:status,{interaction.channel_id}")
        await interaction.response.send_message(f"Processing...", ephemeral=True)
    else:
        await interaction.response.send_message(
            f"You do not have permisson to use this command.", ephemeral=True
        )


# Restart
@bot.tree.command(
    name="restart",
    description="Will restart the actuall server computer!",
    guild=discord.Object(GUILD),
)
async def restart_server(interaction: discord.Interaction):
    if interaction.user.id in SUPER_USERS:
        await interaction.response.send_message(f"Restarting server...", ephemeral=True)
        bot.get_connection().send("srv:restart")
        # pass

    else:
        await interaction.response.send_message(
            f"You do not have permisson to use this command.", ephemeral=True
        )
        # Warnings
        for usr_id in SUPER_USERS:
            if user := bot.get_user(usr_id):
                await user.send(
                    f"Warning: `{interaction.user.name}` tried to restart the server"
                )

    # await interaction.response.send_message(f"Test", ephemeral=True)


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
