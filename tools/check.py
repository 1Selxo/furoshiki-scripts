#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the scripts folder before a pull request is merged (CI runs it on every pull request).

    python tools/check.py            # every script
    python tools/check.py --lua luac # also compile each script with that Lua 5.4 compiler

What it holds a script to (README.md, "Rules for a script"):
- it is scripts/<console>/<ID>.lua, the console one of CONSOLES, the ID the game's own as
  Furoshiki shows it (capitals, digits and hyphens);
- it begins with its `-- reader: title`, `reads` and `version` lines;
- it is UTF-8 and smaller than 256 KB;
- nothing else is in the folder but index.json, the names dictionaries (names-*.zip) and data
  files a script asks for with reader.data(), each under 256 KB; never a character table
  (*.charset), which is made from the game and is not published.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSOLES = {"ps1", "ps2", "psp", "dreamcast", "3ds", "nds", "vita"}
NAME = re.compile(r"^((?=[A-Z-]*[0-9])[A-Z0-9][A-Z0-9-]{3,15}|[A-Z]{4})\.lua$")
HEADER = re.compile(r"^--\s*reader:\s*(\S+)\s+(.*?)\s*$")
DATA = re.compile(r"""reader\.data\(\s*["']([A-Za-z0-9_.-]+)["']\s*\)""")
LIMIT = 256 * 1024


def header(source):
    said = {}
    for raw in source.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("--"):
            break
        match = HEADER.match(line)
        if match:
            said.setdefault(match.group(1), match.group(2))
    return said


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lua", help="a Lua 5.4 compiler (luac) to check each script's syntax")
    args = parser.parse_args()
    luac = shutil.which(args.lua) if args.lua else None
    if args.lua and not luac:
        print(f"no {args.lua}", file=sys.stderr)
        return 2
    problems = []
    scripts = 0
    for folder in sorted((ROOT / "scripts").iterdir()):
        if not folder.is_dir():
            problems.append(f"{folder.name}: only console folders belong in scripts/")
            continue
        if folder.name not in CONSOLES:
            problems.append(f"scripts/{folder.name}: not a console ({', '.join(sorted(CONSOLES))})")
            continue
        wanted = set()
        sources = {}
        for path in sorted(folder.glob("*.lua")):
            where = f"scripts/{folder.name}/{path.name}"
            if not NAME.match(path.name):
                problems.append(f"{where}: name it after the game's ID, e.g. ULJM05887.lua")
                continue
            data = path.read_bytes()
            if len(data) > LIMIT:
                problems.append(f"{where}: larger than 256 KB")
            try:
                source = data.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{where}: not UTF-8")
                continue
            sources[path] = source
            said = header(source)
            for key in ("title", "reads", "version"):
                if not said.get(key):
                    problems.append(f"{where}: no `-- reader: {key} ...` line among its first comments")
            game = path.name[:-4]
            wanted.update(f"{game}.{name}" for name in DATA.findall(source))
            scripts += 1
            if luac:
                run = subprocess.run([luac, "-p", str(path)], capture_output=True, text=True)
                if run.returncode != 0:
                    problems.append(f"{where}: {run.stderr.strip()}")
        for path in sorted(folder.iterdir()):
            name = path.name
            where = f"scripts/{folder.name}/{name}"
            if path.is_dir():
                problems.append(f"{where}: no folders inside a console's folder")
            elif name.endswith(".lua") or name == "index.json" or re.match(r"^names-[a-z0-9-]+\.zip$", name):
                continue
            elif name.endswith(".charset"):
                problems.append(f"{where}: a character table is made from the game and is never published")
            elif name not in wanted:
                problems.append(f"{where}: no script here asks for it (reader.data)")
            elif path.stat().st_size > LIMIT:
                problems.append(f"{where}: larger than 256 KB")
    for problem in problems:
        print(problem)
    print(f"{scripts} scripts, {len(problems)} problem(s)", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
