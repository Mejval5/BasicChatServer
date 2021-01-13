from typing import *
import asyncio
import time
from lisp import *

channels: Dict = dict()
clients: Set = set()
windows = False


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
        # parsed_msg = parse(f"(message \"{self.name}\" {timestamp} \"{client.nick}\" \"{message}\")")
        # msg = f"(message {self.name} {timestamp} {client.nick} {message}"
        msg = f"(message \"{self.name}\" {timestamp} \"{client.nick}\" \"{message.value}\")"
        self.history.append((timestamp, f"\"{client.nick}\" \"{message.value}\""))
        tasks = (c.send_message(msg) for c in clients if c in self.clients and c in clients)
        await asyncio.gather(*tasks)
        return None

    async def replay(self, client, ts):
        if client not in self.clients:
            return False
        await client.send_ok()
        for msg in self.history:
            if msg[0] < ts:
                continue
            await client.send_message(f"(message \"{self.name}\" \"{msg[0]}\" {msg[1]})")
        return None

    def add_client(self, client):
        if client in self.clients:
            return False
        self.clients.add(client)
        return True

    def leave(self, client):
        if client not in self.clients:
            return False
        self.clients.remove(client)
        return True


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

    def join(self, chan):
        if type(chan) is not String:
            return False
        if not chan.value.startswith("#") or not chan.value[1:].isalnum():
            return False
        channel = channels.get(chan.value)
        if channel is None:
            channel = Channel(chan.value)
        return channel.add_client(self)

    def leave(self, chan):
        if chan.value not in channels:
            return False
        return channels[chan.value].leave(self)

    async def message_all(self, rest):
        if len(rest) != 2:
            return False
        chan, message = rest[0], rest[1]
        if chan.value not in channels:
            return False
        return await channels[chan.value].message(self, message)

    async def replay_channel(self, rest):
        chan, timestamp = rest[0], rest[1]
        if chan.value not in channels:
            return False
        try:
            if int(timestamp.value) > time.time():
                return False
        except ValueError:
            return False
        return await channels[chan.value].replay(self, int(timestamp.value))

    async def send_ok(self):
        await self.send_message("(ok)")

    async def send_error(self, error=""):
        if error:
            msg = f"(error {error})"
        else:
            msg = "(error)"
        await self.send_message(msg)

    async def read_message(self) -> str:
        data = await self.reader.readline()
        if windows:
            return data.decode().rstrip("\n").rstrip("\r")
        else:
            return data.decode().rstrip("\n")

    async def send_message(self, message):
        if windows:
            self.writer.write(f"{message}\n\r".encode())
        else:
            self.writer.write(f"{message}\n".encode())
        async with self._drain_lock:
            await self.writer.drain()

    async def send_nothing(self):
        async with self._drain_lock:
            await self.writer.drain()

    def set_nick(self, nick):
        if type(nick) is not String:
            return False
        if not nick.value.isalnum() or nickname_in_use(nick.value):
            return False
        if nick.value.startswith("#"):
            return False
        self.nick = nick.value
        return True

    async def setup_nick(self):
        message = parse(await self.read_message())
        if type(message) is not Compound:
            await self.send_error("not compound") # TODO
            return False
        if len(message._children) != 2:
            await self.send_error("too many commands.")
            return False
        cmd, nick = message._children[0], message._children[1]
        if type(nick) is not String:
            await self.send_error("nick is not string.")
            return False
        if cmd.value != "nick":
            await self.send_error("setup a nick first.")
            return False
        if not self.set_nick(nick):
            await self.send_error("choose an available nick.")
            return False
        await self.send_ok()
        return True

    async def parse_cmd(self):
        message = parse(await self.read_message())
        if type(message) is Compound:
            cmd, rest = message._children[0], message._children[1:]
            if cmd.value == "join":
                res = self.join(rest[0])
            elif cmd.value == "nick":
                res = self.set_nick(rest[0])
            elif cmd.value == "part":
                res = self.leave(rest[0])
            elif cmd.value == "message":
                res = await self.message_all(rest)
            elif cmd.value == "replay":
                res = await self.replay_channel(rest)
            else:
                res = False
            if res is None:
                await self.send_nothing()
            elif res:
                await self.send_ok()
            elif not res:
                await self.send_error()
        else:
            await self.send_error()


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
        unix_server = await asyncio.start_server(server, '127.0.0.2', 9999)
    else:
        unix_server = await asyncio.start_unix_server(server, './chatsock')
    async with unix_server:
        await unix_server.serve_forever()


asyncio.run(main())
