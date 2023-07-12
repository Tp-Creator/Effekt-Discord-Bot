import os
import time
import subprocess
import sys

from multiprocessing import Process, Pipe

import bot

# Start bot
discord_connection, child_connection = Pipe()

discord_bot = Process(target=bot.startBot, args=(child_connection,))
discord_bot.start()


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
executable = f"sudo -u ckserver java -Xms{sizes[0]} -Xmx{sizes[1]} -jar server.jar --nogui".split()


def server_command(cmd):
    command = bytes(cmd + "\n", "utf-8")

    # Needs to get flushed
    if mcP.stdin:
        mcP.stdin.write(command)
        mcP.stdin.flush()
    else:
        print("Couldn't send command to subprocess!")


def console(*msg):
    print(*msg)
    discord_connection.send("send:" + " ".join(msg))


content = ""
previousContent = ""

os.chdir(minecraft_dir)
mcP = subprocess.Popen(executable, stdin=subprocess.PIPE)

print("Starting server...")
time.sleep(2)


while True:
    # Checking for commands from Discord
    if discord_connection.poll(timeout=0.2):
        command = discord_connection.recv().lower()
        # Commands to server
        if command.startswith("mc:"):
            if mcP.poll() == None:
                server_command(command[3:])
                # if command == "mc:stop": fake mc

            # Start server
            elif command == "mc:start":
                mcP = subprocess.Popen(executable, stdin=subprocess.PIPE)
                previousContent = ""
                time.sleep(2)

        elif command.startswith("srv:"):
            match (command[4:]):
                case "restart":
                    console("Restarting server...")

                    if mcP.poll() == None:
                        console("Stopping Minecraft")
                        server_command("stop")
                        while mcP.poll() == None:
                            pass

                    console("Disconnecting from Discord")
                    discord_connection.send("dc:stop")
                    while discord_bot.is_alive():
                        pass

                    # os.system("sudo reboot")
                    subprocess.run("sudo reboot", shell=True)
        # if standbyP.poll()...:

    time.sleep(1)

    with open("./logs/latest.log", "r") as log:
        content = log.read()
        if previousContent in content:
            content = content.replace(previousContent, "")
        else:
            previousContent = ""

        if content != "":
            # Send messages from Minecraft server output to discord child process
            discord_connection.send("send:" + content)
            previousContent += content
