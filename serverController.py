import os
import time
import subprocess
import datetime
import sys
import atexit

from shared_memory_dict import SharedMemoryDict

smd = SharedMemoryDict(name="config", size=1000000)


def validSizes(args):
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
    if process.stdin:
        process.stdin.write(command)
        process.stdin.flush()
    else:
        print("Couldn't send command to subprocess!")


content = ""
previousContent = ""

os.chdir(minecraft_dir)
process = subprocess.Popen(executable, stdin=subprocess.PIPE)
print("Starting server...")


def exit_handler():
    global smd
    smd.shm.close()
    smd.shm.unlink()
    del smd


atexit.register(exit_handler)

while process.poll() == None:
    # command = input(":")
    command = ""
    if "commandStack" in smd.keys() and len(smd["commandStack"]) >= 1:
        stack = smd["commandStack"]
        command = stack.pop(0)
        smd["commandStack"] = stack

    if process.poll() == None and command != "":
        server_command(command)

    time.sleep(0.1)

    with open("./logs/latest.log", "r") as log:
        content = log.read()
        if previousContent in content:
            content = content.replace(previousContent, "")
        if content != "":
            smd["contentStack"] = smd["contentStack"] + [content]
            previousContent += content
