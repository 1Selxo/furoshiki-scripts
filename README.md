# Furoshiki scripts

The game scripts that [Furoshiki](https://github.com/sommepo/furoshiki) reads Japanese games
with. A script is one Lua file for one game. It finds the text the game shows in the
emulator's memory, so that you can look words up in the game's own picture. Furoshiki installs
scripts from here (Settings › Consoles › *Game scripts*) with no app update, and anyone can add
a game with a pull request.

## The scripts

Each console has a folder, and each script is named after its game's ID:

```
scripts/
  ps1/        PlayStation      SLPS-01234.lua
  ps2/        PlayStation 2    SLPM-65051.lua
  psp/        PSP              ULJM05887.lua
  dreamcast/  Dreamcast        T14301M.lua
  3ds/        3DS              0004000000088A00.lua
  nds/        DS               AWIJ.lua
  vita/       PS Vita          PCSG00488.lua
```

Beside the scripts are each console's `index.json` (the list Furoshiki installs from, written
by CI after every merge) and the games' names dictionaries (`names-*.zip`, made by Furoshiki's
maintainer from VNDB's character data).

### Using a script by hand

Copy the `.lua` into Furoshiki's scripts folder, then start the game (or choose *Reload game
script* in the Game menu):

| Furoshiki on | Scripts folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Furoshiki\program\reader\profiles` |
| Linux | `~/.local/share/Furoshiki/program/reader/profiles` |
| Android | `Android/data/io.github.sommepo.furoshiki/files/reader/profiles` |

A script in that folder wins over an installed one, so this is also how a script is shared
before it is merged: send the file.

## Adding a game

Adding a game is a job for a coding agent (Claude Code, Codex, Gemini CLI and the like).
You need Furoshiki 0.3.2 or newer, Python 3.9 or newer, the agent, and your own dump of the
game (the Japanese release). It works on Windows, Linux and macOS.

1. Fork this repository on GitHub, clone your fork, and start your agent in it.
2. Ask it to add the game, and say where the dump and Furoshiki are. For example: *"Add
   support for Steins;Gate on the PSP. The game is at D:\Games\PSP\steins-gate.iso and
   Furoshiki is in C:\Furoshiki."*
3. The agent follows [AGENTS.md](AGENTS.md). It starts the game in Furoshiki, finds the text
   in memory, writes the script and tries it in the running game, then tells you what it saw
   read.
4. Play the game for a while yourself with the script. It is in your scripts folder already.
5. Let the agent open the pull request. When it is merged, everyone can install the script
   from Furoshiki.

The agent drives Furoshiki through `tools/agent.py`, a small Python program with no
dependencies (`python tools/agent.py --help`).

Some games keep their text in a font of their own rather than as Shift-JIS or Unicode. A
script for such a game needs a character table made from the game, which can't be published,
so those games can't be added here. The agent says so when it finds one.

## Rules for a script

- One script per game ID. A game with several releases or discs has one script per ID.
- It starts with the `-- reader: title`, `reads` and `version` lines
  ([docs/script-api.md](docs/script-api.md)), and checks the game's build before reading.
- It holds addresses and decoding logic only: no text, pictures or fonts from the game.
- `python tools/check.py` says 0 problems. CI runs it on every pull request.

## Documents

- [AGENTS.md](AGENTS.md): the steps from a dump to a pull request.
- [docs/script-api.md](docs/script-api.md): everything a script can call.
- [docs/consoles.md](docs/consoles.md): each console's processor, screen space and encodings.

## Licence

The scripts and tools are under the GNU General Public License, version 3 or later
([COPYING](COPYING)), as Furoshiki is. The names dictionaries are under the Open Database
License, as VNDB's data is ([NAMES-LICENSE](NAMES-LICENSE)).
