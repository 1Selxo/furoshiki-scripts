#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Drive Furoshiki while a game script is written: start a game, press its buttons, take
pictures, search the game's memory for text, and try a script in the running game.

Works on Windows, Linux and macOS with Python 3.9 or newer and nothing else installed. It
talks to Furoshiki's control channel (a named pipe on Windows, a local socket elsewhere),
which Furoshiki opens when it is started with READER_DESKTOP_CONTROL set: `start` does that.

    python tools/agent.py setup PATH          # where Furoshiki is (its folder or program)
    python tools/agent.py start GAME_FILE     # starts Furoshiki with the game
    python tools/agent.py status              # the game's ID, the script's state, the line read
    python tools/agent.py press circle        # a button by the console's name for it
                                              # (`buttons` lists them) or by its place: south
                                              # east west north start select l1 r1 l2 r2
    python tools/agent.py shot shots/a.png    # a picture of the game
    python tools/agent.py find "こんにちは"     # the text in memory, in every encoding
    python tools/agent.py snap NAME           # keep the memory as it is now
    python tools/agent.py changed A B         # addresses that differ between two snaps
    python tools/agent.py read 0x8A0000 256   # bytes, with the text they decode to
    python tools/agent.py lua "mem.u32(0x8A0000)"
    python tools/agent.py try games/psp/steins-gate/ULJM05887.lua   # into Furoshiki, reloaded
    python tools/agent.py watch 60            # each line the script reads, for 60 seconds
    python tools/agent.py send "COMMAND ..."  # any command of the channel
    python tools/agent.py stop                # quits Furoshiki

What it keeps between runs (where Furoshiki is, its process, the snaps) is in `.agent/` at
the top of this repository, which Git ignores. Nothing here goes on the network.
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".agent"
CONFIG = STATE / "config.json"
WINDOWS = os.name == "nt"
PIPE_NAME = "furoshiki-agent"

# A button by where it is on the pad, as Furoshiki maps a controller: the console's own
# name for it is the first of these that the console has (the PlayStation's Cross, the
# Nintendo consoles' A, ...). The console's own names work too (`buttons` lists them).
POSITIONS = {
    "south": ["Cross", "A"], "east": ["Circle", "B"], "west": ["Square", "X"],
    "north": ["Triangle", "Y"], "l1": ["L1", "L"], "r1": ["R1", "R"], "l2": ["L2", "ZL"],
    "r2": ["R2", "ZR"], "start": ["Start", "Plus"], "select": ["Select", "Minus"],
}

ENCODINGS = {
    "sjis": "cp932", "eucjp": "euc_jp", "utf8": "utf-8",
    "utf16le": "utf-16-le", "utf16be": "utf-16-be",
}


def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(config):
    STATE.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(config, indent=1), encoding="utf-8")


def channel_address():
    if os.environ.get("FUROSHIKI_CHANNEL"):
        return os.environ["FUROSHIKI_CHANNEL"]
    if WINDOWS:
        return PIPE_NAME
    return str(Path(tempfile.gettempdir()) / f"furoshiki-agent-{os.getuid()}.sock")


class Channel:
    """One connection to Furoshiki's control channel: a command a line, an answer a line."""

    def __init__(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        last = None
        while True:
            try:
                if WINDOWS:
                    self.pipe = open("\\\\.\\pipe\\" + channel_address(), "r+b", buffering=0)
                    self.sock = None
                else:
                    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.sock.connect(channel_address())
                    self.pipe = None
                break
            except OSError as error:
                last = error
                if time.monotonic() > deadline:
                    raise SystemExit(f"Furoshiki's channel is not there ({last}). "
                                     "Start it with: python tools/agent.py start GAME_FILE")
                time.sleep(0.25)
        self.buffer = b""

    def ask(self, command):
        data = command.replace("\n", " ").encode("utf-8") + b"\n"
        if self.sock:
            self.sock.sendall(data)
        else:
            self.pipe.write(data)
        while b"\n" not in self.buffer:
            chunk = self.sock.recv(1 << 20) if self.sock else self.pipe.read(1 << 16)
            if not chunk:
                raise SystemExit("Furoshiki closed the channel (did it quit?)")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.decode("utf-8", "replace")


def ask(command, channel=None):
    answer = (channel or Channel()).ask(command)
    if answer.startswith("ERR"):
        raise SystemExit(f"{command.split()[0]}: {answer}")
    return answer[3:] if answer.startswith("OK ") else ""


def status(channel=None):
    return json.loads(ask("status", channel))


def find_program(given):
    path = Path(given).expanduser().resolve()
    if path.is_dir():
        for name in ("Furoshiki.exe", "reader-home.exe", "reader-home", "Furoshiki"):
            if (path / name).is_file():
                return path / name
        raise SystemExit(f"No Furoshiki program in {path}")
    if not path.is_file():
        raise SystemExit(f"{path} is not there")
    return path


# ---- Commands ----

def cmd_setup(args):
    program = find_program(args.path)
    config = load_config()
    config["program"] = str(program)
    save_config(config)
    print(f"Furoshiki: {program}")


def cmd_start(args):
    config = load_config()
    program = os.environ.get("FUROSHIKI") or config.get("program")
    if not program:
        raise SystemExit("Say where Furoshiki is first: python tools/agent.py setup PATH")
    game = Path(args.game).expanduser().resolve()
    if not game.is_file():
        raise SystemExit(f"{game} is not there")
    env = dict(os.environ, READER_DESKTOP_CONTROL=channel_address())
    if args.home:
        env["READER_HOME_DIR"] = str(Path(args.home).expanduser().resolve())
    STATE.mkdir(exist_ok=True)
    log = open(STATE / "furoshiki.log", "ab")
    flags = {}
    if WINDOWS:
        flags["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        flags["start_new_session"] = True
    process = subprocess.Popen([program, "--play", str(game)], env=env, stdout=log, stderr=log,
                               stdin=subprocess.DEVNULL, cwd=str(Path(program).parent), **flags)
    config["pid"] = process.pid
    save_config(config)
    channel = Channel(timeout=60)
    deadline = time.monotonic() + args.wait
    while time.monotonic() < deadline:
        now = status(channel)
        if now.get("title_id") and now.get("frame", 0) > 0:
            break
        time.sleep(0.5)
    print(json.dumps(summary(status(channel), channel), ensure_ascii=False, indent=1))


# A console's key in Furoshiki and its folder here.
FOLDERS = {"ps1": "ps1", "ps2": "ps2", "psp": "psp", "dc": "dreamcast", "3ds": "3ds",
           "nds": "nds", "psvita": "vita"}


def summary(now, channel=None):
    keep = {k: now.get(k) for k in ("title_id", "title", "frame", "profile", "current", "choices")}
    out = {k: v for k, v in keep.items() if v not in (None, "", [])}
    try:
        console = json.loads(ask("console", channel))
    except SystemExit:
        return out
    folder = FOLDERS.get(console.get("key"), console.get("key"))
    out["console"] = console.get("name")
    if now.get("title_id"):
        found = sorted((ROOT / "games" / folder).glob(f"*/{now['title_id']}.lua"))
        out["script_here"] = (found[0].relative_to(ROOT).as_posix() if found else
                              f"none yet: games/{folder}/<the game's name, e.g. steins-gate>/{now['title_id']}.lua")
    return out


def cmd_status(args):
    channel = Channel()
    now = status(channel)
    print(json.dumps(now if args.all else summary(now, channel), ensure_ascii=False, indent=1))


def button_bit(channel, wanted):
    buttons = json.loads(ask("buttons", channel))
    lower = {name.lower(): bit for name, bit in buttons.items()}
    for name in POSITIONS.get(wanted.lower(), [wanted]):
        if name.lower() in lower:
            return lower[name.lower()]
    raise SystemExit(f"No button {wanted}. This console's: {' '.join(buttons)}; "
                     f"or by place: {' '.join(POSITIONS)}")


def cmd_buttons(args):
    print(json.dumps(json.loads(ask("buttons")), indent=1))


def cmd_press(args):
    channel = Channel()
    bit = button_bit(channel, args.button)
    for i in range(args.times):
        ask(f"pad {bit} {args.ms}", channel)
        if args.gap and i + 1 < args.times:
            time.sleep(args.gap / 1000)
    print("OK")


def cmd_shot(args):
    path = Path(args.file).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    ask(f"grab {path}")
    print(path)


def regions(channel):
    return json.loads(ask("mem-regions", channel))


def snapshot(channel, name):
    """The game's memory now, as STATE/snaps/NAME.bin with its regions beside it."""
    folder = STATE / "snaps"
    folder.mkdir(parents=True, exist_ok=True)
    found = regions(channel)
    path = (folder / f"{name}.bin").resolve()
    ask(f"dump {path}", channel)
    (folder / f"{name}.json").write_text(json.dumps(found), encoding="utf-8")
    return path, found


def load_snap(name):
    folder = STATE / "snaps"
    try:
        found = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
        data = (folder / f"{name}.bin").read_bytes()
    except OSError:
        raise SystemExit(f"No snap {name}: python tools/agent.py snap {name}")
    return data, found


def address_of(offset, found):
    at = 0
    for region in found:
        if offset < at + region["size"]:
            return region["base"] + offset - at, region
        at += region["size"]
    return None, None


def patterns(text, encodings):
    out = []
    for key in encodings:
        try:
            out.append((key, text.encode(ENCODINGS[key])))
        except UnicodeEncodeError:
            pass
    return out


def cmd_find(args):
    encodings = args.enc.split(",") if args.enc else list(ENCODINGS)
    if args.snap:
        data, found = load_snap(args.snap)
    else:
        channel = Channel()
        path, found = snapshot(channel, "last")
        data = path.read_bytes()
    hits = 0
    for key, needle in patterns(args.text, encodings):
        start = 0
        while hits < args.limit:
            offset = data.find(needle, start)
            if offset < 0:
                break
            address, region = address_of(offset, found)
            if address is not None and (args.video or region.get("state") != 3):
                context = data[max(0, offset - 16): offset + len(needle) + 32]
                print(f"0x{address:08X}  {key:8}  {decode_view(context, key)}")
                hits += 1
            start = offset + 1
    if hits == 0:
        print("Not found. Is the text on screen now? Try part of it, or another encoding "
              "(a game with its own character table needs one: see docs/consoles.md).")


def decode_view(raw, key):
    text = raw.decode(ENCODINGS[key], "replace")
    return "".join(c if c.isprintable() else "·" for c in text)


def cmd_snap(args):
    path, found = snapshot(Channel(), args.name)
    total = sum(r["size"] for r in found)
    print(f"{path} ({total:,} bytes, {len(found)} regions)")


def cmd_changed(args):
    a, found = load_snap(args.a)
    b, _ = load_snap(args.b)
    same = load_snap(args.same)[0] if args.same else None
    count = 0
    step = args.width
    for offset in range(0, min(len(a), len(b)) - step + 1, step):
        if a[offset:offset + step] == b[offset:offset + step]:
            continue
        if same is not None and same[offset:offset + step] != b[offset:offset + step]:
            continue
        address, region = address_of(offset, found)
        if region is None or region.get("state") == 3:
            continue
        av = int.from_bytes(a[offset:offset + step], "little")
        bv = int.from_bytes(b[offset:offset + step], "little")
        print(f"0x{address:08X}  {av:#x} -> {bv:#x}")
        count += 1
        if count >= args.limit:
            print(f"... (first {args.limit}; --limit for more)")
            break


def cmd_read(args):
    raw = bytes.fromhex(ask(f"mem-read {args.address} {args.length}"))
    base = int(args.address, 0)
    for at in range(0, len(raw), 16):
        row = raw[at:at + 16]
        print(f"0x{base + at:08X}  {row.hex(' '):<47}  " +
              "".join(chr(c) if 32 <= c < 127 else "." for c in row))
    for key in (args.enc.split(",") if args.enc else ["sjis", "utf16le"]):
        print(f"{key}: {decode_view(raw, key)}")


def cmd_lua(args):
    print(ask("lua " + args.code))


def cmd_try(args):
    script = Path(args.script).expanduser().resolve()
    if not script.is_file():
        raise SystemExit(f"{script} is not there")
    channel = Channel()
    now = status(channel)
    game = now.get("title_id")
    if not game:
        raise SystemExit("No game is running: python tools/agent.py start GAME_FILE")
    if script.stem.upper() != game.upper() and not args.force:
        raise SystemExit(f"The running game is {game}; the script is {script.name}. "
                         "A script is named after its game's ID (--force to try it anyway).")
    folder = Path(ask("scripts-folder", channel))
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(script, folder / f"{game}.lua")
    for data in script.parent.glob(f"{script.stem}.*"):
        if data.suffix not in (".lua", ".md"):
            shutil.copyfile(data, folder / f"{game}{data.name[len(script.stem):]}")
    before = now.get("profile", {})
    ask("script-reload", channel)
    time.sleep(1.0)
    after = status(channel).get("profile", {})
    print(json.dumps({"copied_to": str(folder / f"{game}.lua"), "profile": after},
                     ensure_ascii=False, indent=1))
    if after.get("error"):
        sys.exit(1)
    if not after.get("loaded") and not before.get("loaded"):
        print("The script did not load and said nothing: is it named after the running game?")


def cmd_watch(args):
    channel = Channel()
    seen = None
    end = time.monotonic() + args.seconds
    while time.monotonic() < end:
        now = status(channel)
        current = now.get("current") or {}
        key = (current.get("id"), current.get("text"))
        if current and key != seen:
            seen = key
            speaker = f"{current['speaker']}: " if current.get("speaker") else ""
            print(f"[{now.get('frame')}] {speaker}{current.get('text')}", flush=True)
        if now.get("choices"):
            choices = now["choices"]
            if choices != getattr(cmd_watch, "last_choices", None):
                cmd_watch.last_choices = choices
                print(f"[{now.get('frame')}] choices: {choices}", flush=True)
        time.sleep(args.every / 1000)


def cmd_send(args):
    channel = Channel()
    for command in args.commands:
        print(channel.ask(command))


def cmd_stop(args):
    config = load_config()
    quit_asked = False
    try:
        quit_asked = Channel(timeout=2).ask("quit").startswith("OK")
    except SystemExit:
        pass
    pid = config.pop("pid", None)
    if quit_asked:
        time.sleep(3)
    if pid and not quit_asked:
        try:
            if WINDOWS:
                subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True)
            else:
                os.kill(pid, 15)
        except OSError:
            pass
    save_config(config)
    print("stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="say where Furoshiki is")
    p.add_argument("path")
    p.set_defaults(run=cmd_setup)

    p = sub.add_parser("start", help="start Furoshiki with a game")
    p.add_argument("game")
    p.add_argument("--home", help="a Furoshiki folder of its own for this test (READER_HOME_DIR)")
    p.add_argument("--wait", type=float, default=30, help="seconds to wait for the game")
    p.set_defaults(run=cmd_start)

    p = sub.add_parser("status", help="the game, its script, the line read")
    p.add_argument("--all", action="store_true", help="everything the channel says")
    p.set_defaults(run=cmd_status)

    p = sub.add_parser("buttons", help="the console's buttons")
    p.set_defaults(run=cmd_buttons)

    p = sub.add_parser("press", help="press a button of the console")
    p.add_argument("button")
    p.add_argument("ms", nargs="?", type=int, default=100)
    p.add_argument("--times", type=int, default=1)
    p.add_argument("--gap", type=int, default=400, help="ms between presses")
    p.set_defaults(run=cmd_press)

    p = sub.add_parser("shot", help="a picture of the game")
    p.add_argument("file")
    p.set_defaults(run=cmd_shot)

    p = sub.add_parser("find", help="search the game's memory for text")
    p.add_argument("text")
    p.add_argument("--enc", help="encodings to try: " + ",".join(ENCODINGS))
    p.add_argument("--snap", help="search a snap instead of memory now")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--video", action="store_true", help="video memory too")
    p.set_defaults(run=cmd_find)

    p = sub.add_parser("snap", help="keep the game's memory as it is now")
    p.add_argument("name")
    p.set_defaults(run=cmd_snap)

    p = sub.add_parser("changed", help="what differs between two snaps")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--same", help="a third snap B must equal (taken later, nothing changed)")
    p.add_argument("--width", type=int, default=4, choices=(1, 2, 4))
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(run=cmd_changed)

    p = sub.add_parser("read", help="bytes of the game's memory")
    p.add_argument("address")
    p.add_argument("length")
    p.add_argument("--enc")
    p.set_defaults(run=cmd_read)

    p = sub.add_parser("lua", help="Lua in the script's state (mem, text, reader)")
    p.add_argument("code")
    p.set_defaults(run=cmd_lua)

    p = sub.add_parser("try", help="put a script in the scripts folder and reload it")
    p.add_argument("script")
    p.add_argument("--force", action="store_true")
    p.set_defaults(run=cmd_try)

    p = sub.add_parser("watch", help="print each line read")
    p.add_argument("seconds", nargs="?", type=float, default=30)
    p.add_argument("--every", type=int, default=250)
    p.set_defaults(run=cmd_watch)

    p = sub.add_parser("send", help="raw commands of the channel")
    p.add_argument("commands", nargs="+")
    p.set_defaults(run=cmd_send)

    p = sub.add_parser("stop", help="quit Furoshiki")
    p.set_defaults(run=cmd_stop)

    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        args.run(args)
    except BrokenPipeError:  # the output was cut short (`| head`)
        sys.stderr.close()


if __name__ == "__main__":
    main()
