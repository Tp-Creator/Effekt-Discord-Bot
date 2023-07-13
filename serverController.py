import os
import time
import subprocess
import concurrent.futures
import sys
import datetime
import re
import json

from multiprocessing import Process, Pipe

import bot

# Start bot
discord_connection, child_connection = Pipe()

discord_bot = Process(target=bot.startBot, args=(child_connection,))
discord_bot.start()


### to not get error msgs in vs code
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


sizes = sys.argv[1:] if validSizes(sys.argv[1:]) else ["1024M", "4G"]

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
    server_command("stop")
    console("Stopping Minecraft...")
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
        fake_mc_process.kill()
        while fake_mc_process.poll() == None:
            pass
    console("Starting Minecraft...")
    mc_process = start_process(minecraft_executable, minecraft_dir)
    return mc_process


# Variabler
online_players = {}
zero_player_timer = -1

# starting processes
fake_mc_process = start_process(fake_executable, fake_dir)
mc_process = DummyProcess()

# creating Logreader objects
fake_log_reader = LogReader(fake_dir + "/logs/latest.log")
mc_log_reader = LogReader(minecraft_dir + "/logs/latest.log")
# Because we dont want to send the last log from minecraft.
mc_log_reader.read()


console("Starting standbyMC...")
time.sleep(2)


def foo(bar):
    print("hello {}".format(bar))
    return "foo"


future_stop = DummyFuture()
future_start = DummyFuture()

waiting_stop = False
waiting_start = False

with concurrent.futures.ThreadPoolExecutor() as executor:
    while True:
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
            ).total_seconds() > 60 * 10:
                console("Turning of Minecraft since nobody was online for 10 minutes.")
                # fake_mc_process = stop()
                future_stop = executor.submit(stop)
                waiting_stop = True

        # Checking for commands from Discord
        if discord_connection.poll(timeout=0.2):
            command = discord_connection.recv().lower()
            # Commands to server
            if not waiting_stop and command.startswith("mc:"):
                if mc_process.poll() == None:
                    server_command(command[3:])
                    if command == "mc:stop":
                        # fake_mc_process = stop()
                        future_stop = executor.submit(stop)
                        waiting_stop = True

                # Start server
                elif command == "mc:start":
                    # mc_process = start()
                    waiting_start = True
                    future_start = executor.submit(start)
                    time.sleep(2)

                elif fake_mc_process.poll() == None:
                    # fake mc commands goes here
                    pass

                # Should never happen that both processes are dead
                else:
                    console(
                        "Both the Minecraft server and the standby server are off!\nStarting standby..."
                    )

            elif command.startswith("srv:"):
                match (command[4:]):
                    case "restart":
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
                if command[5:].startswith("online,"):
                    discord_connection.send(
                        f"chan:{command[12:]}:{json.dumps(online_players)}"
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
        if content != "":
            # Send messages from Minecraft server output to discord child process
            discord_connection.send("log:" + content)

            # If someone tries to connect to the standbyMC we start Minecraft
            if "ries to connect to the server" in content:
                # mc_process = start()
                waiting_start = True
                future_start = executor.submit(start)
