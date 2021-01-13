from typing import *
import asyncio
import time
from lisp import *

channels: Dict = dict()
clients: Set = set()
windows = True


class Channel:
    def __init__(self, name):
        self.name = name
        self.history = list()
        channels[name] = self
        self.clients = set()

    async def message(self, client, message):
        if client not in self.clients:
            return False
        timestamp = int(time.time())
        msg = f"(message \"{self.name}\" {timestamp} \"{client.nick}\" \"{message.value}\")"
        self.history.append((timestamp, f"\"{client.nick}\" \"{message.value}\""))
        tasks = (c.send_message(msg) for c in clients if c in self.clients)
        await asyncio.gather(*tasks)

    async def replay(self, client, ts):
        if client not in self.clients:
            return False
        await client.send_ok()
        for msg in self.history:
            if msg[0] < ts:
                continue
            #await asyncio.sleep(10)
            await client.send_message(f"(message \"{self.name}\" \"{msg[0]}\" {msg[1]})")

    async def add_client(self, client):
        if client in self.clients:
            await client.send_error("cannot add client")
        else:
            self.clients.add(client)
            await client.send_ok()

    async def leave(self, client):
        if client not in self.clients:
            await client.send_error("client not in self.clients")
        self.clients.remove(client)
        await client.send_ok()


def nickname_in_use(nick):
    for c in clients:
        if nick == c.nick:
            return True
    return False


class Client:
    def __init__(self, reader, writer):
        self.writer = writer
        self.reader = reader
        self.nick = None
        clients.add(self)
        self._drain_lock = asyncio.Lock()

    async def join(self, rest):
        if len(rest) != 1:
            await self.send_error("len(rest) in join is not 1")
            return
        chan = rest[0]
        if not type(chan) is String:
            await self.send_error("chan is not string")
        elif not chan.value.startswith("#") or not chan.value[1:].isalnum():
            await self.send_error("chan does not start with #")
        else:
            channel = channels.get(chan.value)
            if channel is None:
                channel = Channel(chan.value)
            await channel.add_client(self)

    async def leave(self, rest):
        if len(rest) != 1:
            await self.send_error("len(rest) in leave function is not = 1")
            return
        chan = rest[0]
        if not type(chan) is String:
            await self.send_error("chan is not string")
        if chan.value not in channels:
            await self.send_error("chan not in channels")
        else:
            await channels[chan.value].leave(self)

    async def message_all(self, rest):
        if len(rest) != 2:
            await self.send_error("rest is longer than 2")
            return
        chan, message = rest[0], rest[1]
        if not type(chan) is String or not type(message) is  String:
            await self.send_error("chan or msg is not string")
            return
        if chan.value not in channels:
            await self.send_error("chan not in channels")
            return
        if self not in channels[chan.value].clients:
            await self.send_error("you aint in this channel boy")
            return
        await channels[chan.value].message(self, message)

    async def replay_channel(self, rest):
        if len(rest) != 2:
            await self.send_error("len(rest) in replay function is not 2")
            return
        chan, timestamp = rest[0], rest[1]
        if not type(chan) is String or not type(timestamp) is Number:
            await self.send_error("chan or timestamp are incorrect types")
            return
        if chan.value not in channels:
            await self.send_error("chan not in channels")
            return
        if self not in channels[chan.value].clients:
            await self.send_error("you aint in this channel boy")
            return
        try:
            if int(timestamp.value) > time.time():
                await self.send_error("timestamp breaks temporality")
                return
        except ValueError:
            await self.send_error("ValueError")
            return
        await channels[chan.value].replay(self, int(timestamp.value))
        

    async def send_ok(self):
        await self.send_message("(ok)")

    async def send_error(self, error=""):
        if error:
            msg = f"(error \"{error}\")"
        else:
            msg = "(error)"
        await self.send_message(msg)

    async def read_message(self) -> str:
        data = await self.reader.readline()
        if windows:
            return data.decode('windows-1252').rstrip("\n").rstrip("\r")
        else:
            return data.decode('utf-8').rstrip("\n")

    async def send_message(self, message):
        if windows:
            self.writer.write(f"{message}\n\r".encode(encoding='windows-1252'))
        else:
            self.writer.write(f"{message}\n".encode(encoding='utf-8'))
        async with self._drain_lock:
            await self.writer.drain()

    def set_nick(self, rest):
        if len(rest) != 1:
            asyncio.create_task(self.send_error("len(rest is not 1"+str(rest)))
            return False
        nick = rest[0]
        if type(nick) is not String:
            asyncio.create_task(self.send_error("nick is not string"))
            return False
        if not nick.value.isalnum() or nickname_in_use(nick.value):
            asyncio.create_task(self.send_error("bick is not alnum"))
            return False
        if nick.value.startswith("#"):
            asyncio.create_task(self.send_error("nick starts with #"))
            return False
        self.nick = nick.value
        return True

    async def setup_nick(self):
        try:
            message = parse(await self.read_message())
        except UnicodeDecodeError:
            asyncio.create_task(self.send_error("bad bad unicode"))
            return False
        if type(message) is not Compound:
            asyncio.create_task(self.send_error("not compound")) # TODO
            return False
        if len(message._children) != 2:
            asyncio.create_task(self.send_error("too few or many commands."))
            return False
        cmd, rest = message._children[0], message._children[1:]
        if type(cmd) is not Identifier:
            asyncio.create_task(self.send_error("command not identifier."))
            return False
        if cmd.value != "nick":
            asyncio.create_task(self.send_error("setup a nick first."))
            return False
        if not self.set_nick(rest):
            return False
        asyncio.create_task(self.send_ok())
        return True

    async def parse_cmd(self):
        try:
            message = parse(await self.read_message())
        except UnicodeDecodeError:
            asyncio.create_task(self.send_error("bad bad unicode"))
            return
        if type(message) is Compound:
            cmd, rest = message._children[0], message._children[1:]
            if type(cmd) is Identifier:
                if cmd.value == "join":
                    asyncio.create_task(self.join(rest))
                    return
                elif cmd.value == "nick":
                    if self.set_nick(rest):
                        asyncio.create_task(self.send_ok())
                        return
                elif cmd.value == "part":
                    asyncio.create_task(self.leave(rest))
                    return
                elif cmd.value == "message":
                    asyncio.create_task(self.message_all(rest))
                    return
                elif cmd.value == "replay":
                    asyncio.create_task(self.replay_channel(rest))
                    return
        asyncio.create_task(self.send_error("parse cmd failed"))


async def server(reader, writer):
    c = Client(reader, writer)
    try:
        while not await c.setup_nick():
            pass
        while True:
            await c.parse_cmd()
    except ConnectionError:
        clients.remove(c)


async def main():
    if windows:
        unix_server = await asyncio.start_server(server, '192.168.0.104', 8888)
    else:
        unix_server = await asyncio.start_unix_server(server, './chatsock')
    async with unix_server:
        a = asyncio.create_task(unix_server.serve_forever())
        b = asyncio.create_task(run_tests())
        await a
        await b


        
lock = asyncio.Lock()

async def run_tests():
    reader, writer = await asyncio.open_connection(host="192.168.0.104", port="8888")
    
    await tests(reader, writer)
    

async def read(reader):
    return (await reader.readline()).decode('windows-1252').rstrip("\n").rstrip("\r")

async def write(message, writer):
    writer.write(message+"\n\r".encode(encoding='windows-1252'))
    async with lock:
        await writer.drain()


async def tests(reader, writer):
    await write("(nick \"foo\")", writer)
    await _assert ("(ok)", reader)

    await write("(nick \"foo\")", writer)
    await _assert ("(error)", reader)

    await write("(nick \"foo\")", writer)
    await _assert ("(error)", reader)

    await write("(nick \"bar\")", writer)
    await _assert ("(ok)", reader)

    await write("(nick \"bar\" \"awd\")", writer)
    await _assert ("(error)", reader)

    await write("((nick \"bar\"))", writer)
    await _assert ("(error)", reader)

    await write("(())", writer)
    await _assert ("(error)", reader)

    await write("()", writer)
    await _assert ("(error)", reader)


async def _assert(b, reader):
    a = await read(reader)
    print(a)


asyncio.run(main())
