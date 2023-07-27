import os
import time
import subprocess
import concurrent.futures
import sys
import datetime
import re
import json
import signal
import traceback

from multiprocessing import Process, Pipe

import bot

# Start bot
discord_connection, child_connection = Pipe()

discord_bot = Process(target=bot.startBot, args=(child_connection,))
discord_bot.start()


# to not get error msgs in vs code
class DummyPipe:
    def write(self, msg: bytes) -> None:
        pass

    def flush(self) -> None:
        pass


class DummyProcess:
    def poll(self) -> int | None:
        return 1

    def kill(self):
        pass

    def __init__(self) -> None:
        self.stdin = DummyPipe()


class DummyFuture:
    def running(self) -> bool:
        return False

    def result(self) -> DummyProcess:
        return DummyProcess()


###


#
class LogReader:
    def __init__(self, path: str):
        self.previousContent = ""
        self.path = path

    def read(self) -> str:
        with open(self.path, "r") as log:
            content = log.read()
            if self.previousContent in content:
                content = content.replace(self.previousContent, "")
            else:
                self.previousContent = ""

            self.previousContent += content

        return content


# Makes it possible to write
# >>> python3 serverController.py 1B 2G   # will do between 1 byte and 2 gigabytes of ram
# to run server with custom memory configuration
def validSizes(args):
    if len(args) < 2:
        return False
    if (
        args[0][-1].lower() in "kmg1234567890"
        and (args[0][:-1] + "0").isnumeric()
        and args[1][-1].lower() in "kmg1234567890"
        and (args[1][:-1] + "0").isnumeric()
    ):
        return True
    return False


sizes = sys.argv[1:] if validSizes(sys.argv[1:]) else ["2048M", "6G"]

minecraft_dir = "/home/ckserver/effekt/mcsrv"
minecraft_executable = (
    f"sudo -u ckserver java -Xms{sizes[0]} -Xmx{sizes[1]} -jar server.jar --nogui"
)

fake_dir = "/home/ckserver/effekt/mcfake"
fake_executable = "sudo -u ckserver /usr/bin/python3 ./start.py"


def server_command(cmd):
    command = bytes(cmd + "\n", "utf-8")

    # Needs to get flushed
    if mc_process.stdin:
        mc_process.stdin.write(command)
        mc_process.stdin.flush()
    else:
        console("Couldn't send command to subprocess!")


def console(*msg):
    print(*msg)
    discord_connection.send("konsol:" + " ".join(msg))


def start_process(executable: str, dir=None):
    if dir:
        os.chdir(dir)
    process = subprocess.Popen(executable.split(), stdin=subprocess.PIPE)
    return process


# Stops Minecraft and starts standbyMC
def stop():
    if mc_process.poll() == None:
        console("Stopping Minecraft...")
        try:
            server_command("stop")
        except (BrokenPipeError, IOError):
            print("we want to kill process now!")
            mc_process.kill()
        while mc_process.poll() == None:
            pass
    time.sleep(1)
    console("Starting standbyMC")
    fake_mc_process = start_process(fake_executable, fake_dir)

    return fake_mc_process


# Stops standbyMC and starts Minecraft
def start():
    global zero_player_timer
    zero_player_timer = datetime.datetime.now()
    if fake_mc_process.poll() == None:
        console("Stopping standbyMC")
        # fake_mc_process.terminate()
        # fake_mc_process.kill()
        command = bytes("stop\n", "utf-8")
        fake_mc_process.stdin.write(command)
        fake_mc_process.stdin.flush()

        while fake_mc_process.poll() == None:
            pass
        time.sleep(2)
    console("Starting Minecraft...")
    mc_process = start_process(minecraft_executable, minecraft_dir)
    return mc_process


# Variabler
online_players = {}
zero_player_timer = -1
started_time = datetime.datetime.now()
mc_standby_timeout = 60 * 10

# starting processes
fake_mc_process = start_process(fake_executable, fake_dir)
mc_process = DummyProcess()

# creating Logreader objects
fake_log_reader = LogReader(fake_dir + "/logs/latest.log")
mc_log_reader = LogReader(minecraft_dir + "/logs/latest.log")
# Because we dont want to send the last log from minecraft.
mc_log_reader.read()


console("Starting standbyMC...")
print("Online since", started_time)
time.sleep(2)


future_stop = DummyFuture()
future_start = DummyFuture()

waiting_stop = False
waiting_start = False

with concurrent.futures.ThreadPoolExecutor() as executor:
    while True:
        try:
            if not future_stop.running() and waiting_stop:
                waiting_stop = False
                fake_mc_process = future_stop.result()
            if not future_start.running() and waiting_start:
                waiting_start = False
                mc_process = future_start.result()

            if not waiting_stop and mc_process.poll() == None:
                if zero_player_timer == -1:
                    for player in online_players:
                        if online_players[player]["count"] > 0:
                            break
                    else:
                        zero_player_timer = datetime.datetime.now()
                elif (
                    datetime.datetime.now() - zero_player_timer
                ).total_seconds() > mc_standby_timeout:
                    console(
                        "Turning of Minecraft since nobody was online for 10 minutes."
                    )
                    # fake_mc_process = stop()
                    future_stop = executor.submit(stop)
                    waiting_stop = True

            # Shouldn't happen unless one of the dies never happen that both processes are dead
            if (
                mc_process.poll() != None
                and fake_mc_process.poll() != None
                and not waiting_start
                and not waiting_stop
            ):
                console(
                    "Both the Minecraft server and the standby server are off!\nStarting standbyMC..."
                )
                future_stop = executor.submit(stop)
                waiting_stop = True

            # Checking for commands from Discord
            if discord_connection.poll(timeout=0.2):
                command = discord_connection.recv()
                # Commands to server
                if not waiting_stop and command.startswith("mc:"):
                    command = command.lower()
                    if mc_process.poll() == None:
                        server_command(command[3:])
                        if command == "mc:stop":
                            # fake_mc_process = stop()
                            future_stop = executor.submit(stop)
                            waiting_stop = True
                            online_players = {}

                    # Start server
                    elif command == "mc:start":
                        # mc_process = start()
                        waiting_start = True
                        future_start = executor.submit(start)
                        time.sleep(2)

                    elif fake_mc_process.poll() == None:
                        # fake mc commands goes here
                        pass

                elif command.startswith("srv:"):
                    command = command.lower()
                    if command[4:].startswith("status"):
                        command = command.split(",")

                        # Header
                        msg = f"Status:\n"

                        # MC status
                        if mc_process.poll() == None:
                            # 1 or more players online
                            if zero_player_timer == -1:
                                amount_online = 0
                                for player in online_players:
                                    if online_players[player]["joined"] != False:
                                        amount_online += 1
                                msg += f"```Minecraft: {mc_process.poll() == None} - {amount_online} player(s) online\n"
                            # No players online
                            else:
                                msg += f"```Minecraft: {mc_process.poll() == None} - {round(mc_standby_timeout - (datetime.datetime.now() - zero_player_timer).total_seconds())}s until standby\n"
                        else:
                            msg += f"```Minecraft: {mc_process.poll() == None}\n"

                        # Fake MC status
                        msg += f"StandbyMC: {fake_mc_process.poll() == None}\n"

                        # When this program started the last time
                        msg += f"\nProgram start: {started_time.strftime('%Y-%m-%d, %H:%M:%S')}```"

                        discord_connection.send(f"chan,{command[1]}:" + msg)

                    elif command[4:] == "restart":
                        console("Restarting server...")

                        if mc_process.poll() == None:
                            console("Stopping Minecraft")
                            server_command("stop")
                            while mc_process.poll() == None:
                                pass

                        if fake_mc_process.poll() == None:
                            console("Stopping standbyMC")
                            fake_mc_process.kill()
                            while fake_mc_process.poll() == None:
                                pass

                        console("Disconnecting from Discord")
                        discord_connection.send("dc:stop")
                        while discord_bot.is_alive():
                            pass

                        # os.system("sudo reboot")
                        subprocess.run("sudo reboot", shell=True)

                elif command.startswith("ctrl:"):
                    if command[5:].startswith("online"):
                        command = command.split(",")

                        msg = ""
                        players = dict(
                            sorted(
                                online_players.items(),
                                key=lambda item: item[1]["joined"],
                            )
                        )
                        for player in players:
                            if players[player]["joined"] != False:
                                if msg == "":
                                    msg = "Current players online:\n"
                                msg += f"`{str(datetime.datetime.now()-datetime.datetime.fromtimestamp(players[player]['joined']))[:-7]} - {player}`\n"

                        if msg == "":
                            msg = "There are currently no players online"

                        discord_connection.send(f"chan,{command[1]}:" + msg)

                elif (
                    command.startswith("IGC:")
                    and not waiting_stop
                    and mc_process.poll() == None
                ):
                    # f"IGC:{len(usr_name)},{len(role.name)},{role_color},{usr_name},{role.name},{msg.content}"
                    nameLen, roleLen, roleCol, data = command[4:].split(",", 3)
                    nameLen, roleLen = int(nameLen), int(roleLen)
                    data = data.replace("\\", "\\\\")
                    data = data.replace('"', '\\"')
                    name, role, msgs = (
                        data[:nameLen],
                        data[nameLen + 1: nameLen + roleLen + 1],
                        data[nameLen + roleLen + 2:],
                    )
                    for msg in msgs.split("\n"):
                        server_command(
                            'tellraw @a [{"text": "<'
                            + name
                            + '>", "color": "'
                            + roleCol
                            + '", "hoverEvent":{"action":"show_text","contents":"'
                            + role
                            + '"}}, {"text": " '
                            + msg
                            + '", "color":"white"}]'
                        )

            time.sleep(1)

            content = mc_log_reader.read()
            if content != "":
                # Send messages from Minecraft server output to discord child process
                discord_connection.send("log:" + content)

                joined = re.findall(
                    "\n\\[\\d\\d:\\d\\d:\\d\\d\\] \\[Server thread/INFO\\]: \\w+ joined the game",
                    "\n" + content,
                )

                left = re.findall(
                    "\n\\[\\d\\d:\\d\\d:\\d\\d\\] \\[Server thread/INFO\\]: \\w+ left the game",
                    "\n" + content,
                )

                lines = content.split("\n")
                chats = []
                for line in lines:
                    chat = re.fullmatch(
                        "\\[\\d\\d:\\d\\d:\\d\\d\\] \\[Server thread/INFO\\]: <\\w+> .+",
                        line,
                    )
                    if chat != None:
                        chats.append(chat.group(0)[33:])

                if len(chats):
                    discord_connection.send("IGC:" + "\n".join(chats))

                for usr in joined:
                    zero_player_timer = -1
                    username = usr[34:-16]
                    if username in online_players.keys():
                        online_players[username]["count"] += 1
                        online_players[username][
                            "joined"
                        ] = datetime.datetime.now().timestamp()
                    else:
                        online_players[username] = {
                            "count": 1,
                            "joined": datetime.datetime.now().timestamp(),
                        }

                for usr in left:
                    username = usr[34:-14]
                    if username in online_players.keys():
                        online_players[username]["count"] -= 1
                        online_players[username]["joined"] = False
                    else:
                        # Should never happen
                        online_players[username] = {
                            "count": -1,
                            "joined": False,
                        }

            content = fake_log_reader.read()
            # Skickar inte pings som fake mc får

            if content:
                print(content)
            content = "\n".join(
                [line for line in content.split(
                    "\n") if not "ping packet" in line]
            )
            if content != "":
                # Send messages from Fake Minecraft server output to discord child process
                discord_connection.send("log:" + content)

                # If someone tries to connect to the standbyMC we start Minecraft
                if "ries to connect to the server" in content:
                    # mc_process = start()
                    waiting_start = True
                    future_start = executor.submit(start)
        except KeyboardInterrupt or SystemExit:
            if mc_process.poll() == None:
                console("Stopping Minecraft")
                server_command("stop")
                while mc_process.poll() == None:
                    pass

            if fake_mc_process.poll() == None:
                console("Stopping standbyMC")
                fake_mc_process.kill()
                while fake_mc_process.poll() == None:
                    pass

            console("Disconnecting from Discord")
            discord_connection.send("dc:stop")
            while discord_bot.is_alive():
                pass
            print("Finished.")
            exit(0)
        except Exception as e:
            if not discord_connection.closed and discord_bot.is_alive():
                discord_connection.send(f"log:{traceback.format_exc()}{e}")
            else:
                exit(os.EX_UNAVAILABLE)
