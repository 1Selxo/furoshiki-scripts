#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Make scripts/, the folders Furoshiki installs from, out of games/, where scripts are written.

    python tools/build-lists.py          # writes scripts/<console>/: the files and index.json
    python tools/build-lists.py --check  # says what in scripts/ is out of date, writes nothing

games/<console>/<game>/ holds a game's scripts (<ID>.lua), the data files they ask for and its
names dictionary. Furoshiki wants each console's files side by side with the list, named by ID
(scripts/<console>/<ID>.lua, index.json), so scripts/ is a copy of games/ in that form. CI writes
it after every merge; never edit it by hand.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("index", ROOT / "tools" / "index.py")
index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(index)
NOTE = ("This folder is made from games/ by tools/build-lists.py (CI runs it after every merge): "
        "Furoshiki installs from here. Edit the scripts in games/, never here.\n")


def wanted():
    """{scripts/<console>/<name>: bytes} that games/ makes, and the problems found."""
    out, problems = {}, []
    for console in sorted(p for p in (ROOT / "games").iterdir() if p.is_dir()):
        files = {}
        for game in sorted(p for p in console.iterdir() if p.is_dir()):
            for path in sorted(p for p in game.iterdir() if p.is_file()):
                if path.name.endswith(".md"):
                    continue
                if path.name in files and files[path.name] != path.read_bytes():
                    problems.append(f"games/{console.name}/*/{path.name}: in two game folders")
                files[path.name] = path.read_bytes()
        made, left_out = index.make(files, console.name)
        for game, missing in left_out:
            problems.append(f"{console.name} {game}: {', '.join(missing)} not beside it")
        folder = f"scripts/{console.name}/"
        for name, data in files.items():
            out[folder + name] = data
        out[folder + "index.json"] = index.text(made).encode("utf-8")
    out["scripts/README.md"] = NOTE.encode("utf-8")
    out.update(catalogues())
    return out, problems


NAMES = {"ps1": "PlayStation", "ps2": "PlayStation 2", "psp": "PSP", "dreamcast": "Dreamcast",
         "3ds": "Nintendo 3DS", "nds": "Nintendo DS", "vita": "PS Vita"}


def catalogues():
    """games/<console>/README.md: the console's games, which GitHub shows under the folder."""
    out = {}
    for console in sorted(p for p in (ROOT / "games").iterdir() if p.is_dir()):
        rows = []
        for game in sorted(p for p in console.iterdir() if p.is_dir()):
            scripts = sorted(game.glob("*.lua"))
            if not scripts:
                continue
            said = index.header(scripts[0].read_text(encoding="utf-8"))
            title = said.get("title", game.name).replace("|", "\\|")
            ids = ", ".join(f"[{s.stem}]({game.name}/{s.name})" for s in scripts)
            reads = said.get("reads", "").replace("|", "\\|")
            rows.append(f"| [{game.name}]({game.name}/) | {title} | {ids} | {reads} |")
        text = (f"# {NAMES.get(console.name, console.name)}\n\n"
                f"{len(rows)} games. Made by tools/build-lists.py from the scripts' header lines.\n\n"
                "| Folder | Title | ID | What is read |\n| --- | --- | --- | --- |\n" + "\n".join(rows) + "\n")
        out[f"games/{console.name}/README.md"] = text.encode("utf-8")
    return out


def main(argv):
    check = "--check" in argv
    files, problems = wanted()
    for problem in problems:
        print(problem, file=sys.stderr)
    stale = []
    for name, data in files.items():
        path = ROOT / name
        if not path.is_file() or path.read_bytes() != data:
            stale.append(name)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    for path in sorted([*(ROOT / "scripts").rglob("*"), *(ROOT / "games").glob("*/README.md")]):
        name = path.relative_to(ROOT).as_posix()
        if path.is_file() and name not in files:
            stale.append(name + " (not in games/)")
            if not check:
                path.unlink()
    for line in stale:
        print(("out of date: " if check else "written: ") + line)
    return 1 if problems or (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
