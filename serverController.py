import os
import time
import subprocess
import datetime
import sys
import atexit

from multiprocessing import Process, Queue, Pipe
import bot

# Start bot

parent_conn, child_conn = Pipe()

child_conn.poll

effBot = Process(target=bot.startBot, args=(child_conn,))
effBot.start()
# print("\n" * 2)
# print(parent_conn.recv())
# print("\n" * 2)

parent_conn.send("hej")

# from shared_memory_dict import SharedMemoryDict

# smd = SharedMemoryDict(name="config", size=1000000)


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


# Makes it possible to write
# >>> python3 serverController.py 1B 2G   # will do between 1 byte and 2 gigabytes of ram
# to run server with custom memory configuration
sizes = sys.argv[1:] if validSizes(sys.argv[1:]) else ["1024M", "4G"]

minecraft_dir = "/home/ckserver/effekt/mcsrv"
executable = f"java -Xms{sizes[0]} -Xmx{sizes[1]} -jar server.jar --nogui".split()


def server_command(cmd):
    command = bytes(cmd + "\n", "utf-8")

    # Needs to get flushed
    if mcP.stdin:
        mcP.stdin.write(command)
        mcP.stdin.flush()
    else:
        print("Couldn't send command to subprocess!")


content = ""
previousContent = ""

os.chdir(minecraft_dir)
mcP = subprocess.Popen(executable, stdin=subprocess.PIPE)

print("Starting server...")
time.sleep(2)


# def exit_handler():
#     global smd
#     smd.shm.close()
#     smd.shm.unlink()
#     del smd


# atexit.register(exit_handler)

while True:
    # Checking for commands from Discord
    if parent_conn.poll(timeout=0.2):
        command = parent_conn.recv().lower()
        # Commands to server
        if mcP.poll() == None and command.startswith("mc:"):
            server_command(command[3:])
            # if command == "mc:stop":

        # Start server
        elif command == "mc:start":
            mcP = subprocess.Popen(executable, stdin=subprocess.PIPE)
            previousContent = ""
            time.sleep(2)

        # if standbyP.poll()...:

    time.sleep(0.1)

    with open("./logs/latest.log", "r") as log:
        content = log.read()
        if previousContent in content:
            content = content.replace(previousContent, "")

        if content != "":
            # Send messages from Minecraft server output to discord child process
            parent_conn.send("send:" + content)
            previousContent += content
