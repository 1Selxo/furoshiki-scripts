#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Write every console's index.json, the list that Furoshiki installs scripts from.

    python tools/build-lists.py          # writes scripts/<console>/index.json
    python tools/build-lists.py --check  # says which lists are out of date, writes nothing

CI runs it after a merge and commits the lists; a pull request need not touch them.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("index", ROOT / "tools" / "index.py")
index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(index)


def main(argv):
    stale = []
    for folder in sorted((ROOT / "scripts").iterdir()):
        if not folder.is_dir():
            continue
        files = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file() and p.name != "index.json"}
        made, left_out = index.make(files, folder.name)
        for game, missing in left_out:
            print(f"left out {game}: {', '.join(missing)} not in {folder.name}/", file=sys.stderr)
        text = index.text(made)
        target = folder / "index.json"
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            stale.append(target.relative_to(ROOT).as_posix())
            if "--check" not in argv:
                target.write_text(text, encoding="utf-8", newline="\n")
    for path in stale:
        print(("out of date: " if "--check" in argv else "written: ") + path)
    return 1 if stale and "--check" in argv else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
