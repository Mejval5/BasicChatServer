from typing import *
import asyncio
import time
from classes import *
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
        msg = f"(message {self.name} {timestamp} {client.nick} {message}"
        self.history.append((timestamp, f"{client.nick} {message}"))
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
            await client.send_message(f"message {self.name} {msg[0]} {msg[1]}")
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

    def join(self, ch_name):
        #_ch_name = ch_name + "\""
        _ch_name = ch_name
        if not _ch_name.startswith("#"):
            return False
        if not _ch_name.isalnum():
            return False
        channel = channels.get(_ch_name)
        if channel is None:
            channel = Channel(_ch_name)
        return channel.add_client(self)

    def leave(self, ch_name):
        if ch_name not in channels:
            return False
        return channels[ch_name].leave(self)

    async def message_all(self, rest):
        ch_name, _, message = rest.partition(" ")
        if ch_name not in channels:
            return False
        return await channels[ch_name].message(self, message)

    async def replay_channel(self, unread):
        ch_name, _, timestamp = unread.partition(" ")
        if ch_name not in channels:
            return False
        try:
            if int(timestamp) > time.time():
                return False
        except ValueError:
            return False
        return await channels[ch_name].replay(self, int(timestamp))

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
            return data.decode().rstrip("\n").rstrip("\r")#.rstrip(")").rstrip("\"")
        else:
            return data.decode().rstrip("\n").rstrip(")")#.rstrip("\"")

    async def send_message(self, message):
        if windows:
            self.writer.write(f"{message}\n\r".encode())
        else:
            self.writer.write(f"{message}\n".encode())
        async with self._drain_lock:
            await self.writer.drain()

    def set_nick(self, nick):
        #_nick = nick + "\""
        _nick = nick
        if not _nick[1:].isalnum() or nickname_in_use(_nick):
            return False
        self.nick = _nick
        return True

    async def setup_nick(self):
        message = await self.read_message()
        cmd, _, nick = message.partition(" ")
        if cmd != "nick" or not self.set_nick(nick):
            await self.send_error()
            return False
        await self.send_message(nick)
        await self.send_ok()
        return True

    async def parse_cmd(self):

        message = await self.read_message()
        cmd, _, rest = message.partition(" ")
        res = None
        if cmd == "join":
            res = self.join(rest)
        elif cmd == "nick":
            res = self.set_nick(rest)
        elif cmd == "part":
            res = self.leave(rest)
        elif cmd == "message":
            res = await self.message_all(rest)
        elif cmd == "replay":
            res = await self.replay_channel(rest)
        else:
            res = False
        if res == True:
            await self.send_ok()
        if res == False:
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
