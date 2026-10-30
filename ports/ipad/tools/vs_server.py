#!/usr/bin/env python3
"""WMMT3DX versus server: the lobby and the race packets' relay for the port's online versus.

Run it on a computer the devices can reach (the same Wi-Fi, or a forwarded UDP port):
    python3 vs_server.py [port]        (default port 27015)
then enter this computer's IP address on each device's VERSUS screen. Up to 4 players.

Protocol (UDP, little-endian), every datagram starts with b"WV", version 1, type:
  1 HELLO  c->s  u32 id, u8 status (0 lobby, 1 racing, 2.. the area vote: menu.h
                 MENU_VS_CHOOSING ..), char name[16], u8 n, profile[n]
                 (sent twice a second; a client silent for 6 s is dropped)
  2 LOBBY  s->c  u8 players, u8 your slot, u8 host slot, u8 ramp, u8 km, u32 race id,
                 then per player: u8 slot, u32 id, u8 status, char name[16], u8 n, profile[n]
  3 START  c->s  u8 ramp, u8 km, u8 song + 2 (the host's: the players in the lobby race,
                 all with its BGM)
  4 GO     s->c  u32 race id, u32 seed, u8 ramp, u8 km, u8 machines, u8 your PCB,
                 then per machine: u8 pcb, u32 id, char name[16], u8 n, profile[n];
                 then u8 song + 2 (0: none sent)
  5 RACE   c->s  u32 race id, u8 pcb, packet (relayed as it is to the race's other machines)
  6 BYE    c->s  u32 id
  7 DISCOVER c->s  (the LAN's search, broadcast to the port; a device hosting in the app,
                 src/vs_host.c, answers it; this server does not)
  8 OFFER  s->c  u8 players, char name[16], u32 the host's own player id
  9 CLOSED s->c  u32 the host's id (an app's host closing its game; this server does not)
The profile is the client's own (its car); the server passes it on unread.
"""
import random
import socket
import struct
import sys
import time

MAGIC = b"WV\x01"
HELLO, LOBBY, START, GO, RACE, BYE = 1, 2, 3, 4, 5, 6
MAX_PLAYERS = 4
TIMEOUT = 6.0
TIMEOUT_RACING = 20.0  # a player loading or racing (status 1): its device may stall a while at the start


class Player:
    def __init__(self, pid, addr):
        self.id = pid
        self.addr = addr
        self.status = 0
        self.name = b""
        self.profile = b""
        self.seen = time.time()
        self.race = 0  # the race id it was sent GO for
        self.pcb = 0


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 27015
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", port))
    s.settimeout(0.5)
    try:  # the address the devices should enter
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))
        ip = probe.getsockname()[0]
        probe.close()
    except OSError:
        ip = "?"
    print("WMMT3DX versus server on %s port %d (enter %s on the devices)" % (ip, port, ip), flush=True)

    players = []  # in join order: slot = index
    ramp, km, race_id = 0, 13, 0
    races = {}    # race id -> list of (pcb, Player)
    relayed = 0
    last_report = time.time()

    def lobby_to(p):
        host = 0
        body = struct.pack("<BBBBBI", len(players), players.index(p), host, ramp, km, race_id)
        for i, q in enumerate(players):
            body += struct.pack("<BIB16sB", i, q.id, q.status, q.name, len(q.profile)) + q.profile
        s.sendto(MAGIC + bytes([LOBBY]) + body, p.addr)

    def lobby_all():
        for p in players:
            lobby_to(p)

    while True:
        try:
            data, addr = s.recvfrom(4096)
        except socket.timeout:
            data, addr = None, None
        now = time.time()
        gone = [p for p in players if now - p.seen > (TIMEOUT_RACING if p.status == 1 else TIMEOUT)]
        for p in gone:
            print("%s left (timed out)" % p.name.rstrip(b"\0").decode("latin-1"), flush=True)
            players.remove(p)
        if gone:
            lobby_all()
        if now - last_report > 10 and relayed:
            print("  relayed %d race packets" % relayed, flush=True)
            relayed = 0
            last_report = now
        if not data or len(data) < 4 or data[:3] != MAGIC:
            continue
        kind, body = data[3], data[4:]
        sender = next((p for p in players if p.addr == addr), None)
        if kind == RACE:
            if len(body) < 5 or not sender:
                continue
            rid, pcb = struct.unpack_from("<IB", body)
            sender.seen = now
            for q_pcb, q in races.get(rid, ()):
                if q is not sender and q in players:
                    s.sendto(data, q.addr)
                    relayed += 1
            continue
        if kind == HELLO:
            if len(body) < 22:
                continue
            pid, status, name, n = struct.unpack_from("<IB16sB", body)
            profile = body[22:22 + n]
            p = next((q for q in players if q.id == pid), None)
            if p is None:
                if len(players) >= MAX_PLAYERS:
                    continue
                p = Player(pid, addr)
                players.append(p)
                print("%s joined from %s:%d (%d players)" % (name.rstrip(b"\0").decode("latin-1"), addr[0], addr[1],
                                                             len(players)), flush=True)
            changed = (p.status, p.name, p.profile, p.addr) != (status, name, profile, addr)
            p.addr, p.status, p.name, p.profile, p.seen = addr, status, name, profile, now
            if changed:
                lobby_all()
            else:
                lobby_to(p)
            continue
        if kind == START:
            if not sender or players.index(sender) != 0 or len(body) < 2 or len(players) < 2:
                continue
            ramp, km = body[0], body[1]
            song = body[2] if len(body) >= 3 else 0
            race_id = (race_id + 1) & 0xffffffff or 1
            seed = random.getrandbits(31)
            machines = list(players)
            races[race_id] = [(i, p) for i, p in enumerate(machines)]
            for old in [r for r in races if r < race_id - 4]:
                del races[old]
            print("race %d: ramp %d, %d km, %d players" % (race_id, ramp, km, len(machines)), flush=True)
            for i, p in enumerate(machines):
                p.race, p.pcb, p.status = race_id, i, 1
                body_go = struct.pack("<IIBBBB", race_id, seed, ramp, km, len(machines), i)
                for j, q in enumerate(machines):
                    body_go += struct.pack("<BI16sB", j, q.id, q.name, len(q.profile)) + q.profile
                body_go += bytes([song])
                for _ in range(3):  # UDP: say it more than once; clients take the first
                    s.sendto(MAGIC + bytes([GO]) + body_go, p.addr)
            continue
        if kind == BYE and sender:
            print("%s left" % sender.name.rstrip(b"\0").decode("latin-1"), flush=True)
            players.remove(sender)
            lobby_all()


if __name__ == "__main__":
    main()
