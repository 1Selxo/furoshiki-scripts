# Furoshiki scripts: instructions for coding agents

This repository holds the game scripts that [Furoshiki](https://github.com/sommepo/furoshiki)
reads Japanese games with: one Lua file a game, `scripts/<console>/<game ID>.lua`. A script
finds the text the game shows in the emulator's memory and reports it, so that the player can
look words up in the game's own picture. Furoshiki installs them from here.

When you are asked to add support for a game, follow the steps below from start to end. They
need nothing but Furoshiki, Python 3.9 or newer, and the user's own dump of the game. They work
on Windows, Linux and macOS. Nothing here downloads games, BIOS files, keys or firmware.

## Rules

- **Never commit anything taken from a game**: dumps, extracted files, text, screenshots,
  memory snaps, fonts, character tables. Your working files go in `.agent/`, which Git
  ignores. A script holds addresses and decoding logic only.
- **Say what was seen and how.** "Read the first ten lines of the prologue in Furoshiki, as
  the game showed them" is a report; "should work" is not. Never report a step as done that
  you did not see.
- **Don't push, open a pull request or post anything without the user's word.** Make the
  branch and the commit, then show them the report.
- Bind every script to the build it was written for (step 5): a script that reads the wrong
  addresses on another release is worse than none.

## 1. What you need from the user

- The path to their dump of the game (a disc image or a cartridge or package file).
- Where Furoshiki is (its folder). It must be **version 0.3.2 or newer**: older versions lack
  the commands below.
- That the console's BIOS or firmware is already set up in Furoshiki, where the console needs
  one (PlayStation, PS2, PS Vita). If a game does not start, ask them to start it once from
  Furoshiki itself and fix what it says.

Ask for what you were not given. Then:

```sh
python tools/agent.py setup "<Furoshiki's folder>"
python tools/agent.py start "<the dump>"
```

`start` prints the game's ID, its console and whether a script is loaded already. If
`scripts/<console>/<ID>.lua` exists, the game is supported: say so, and ask whether to improve
that script instead. (On Linux and macOS use `python3`. `--home DIR` gives Furoshiki a
folder of its own for the test, but then the BIOS must be put there too.)

## 2. Reach the game's text

```sh
python tools/agent.py shot .agent/shots/1.png      # look at it
python tools/agent.py press east                  # PlayStation circle, Nintendo A
python tools/agent.py buttons                     # this console's button names
```

Press through the logos and the title screen into the game until a line of dialogue or
narration is on screen. Look at every picture you take: what is on screen decides your next
press. `east` and `south` are the usual confirm and cancel; Start often skips logos. Wait a
second or two after each press: `--times N --gap MS` presses several times.

## 3. Find the text in memory

Take three to six characters of the line on screen (kanji and kana, no punctuation):

```sh
python tools/agent.py find "未来を"
```

It searches the whole memory in Shift-JIS, EUC-JP, UTF-8 and UTF-16 and prints each address
with what is around it. Several hits are usual: the game's whole script, a copy being
drawn, an old line. To tell them apart, go on a line and look again:

```sh
python tools/agent.py snap a        # memory now
python tools/agent.py press east    # the next line
python tools/agent.py snap b
python tools/agent.py snap c        # again, with nothing pressed
python tools/agent.py changed a b --same c
python tools/agent.py read 0x08A96F7B 64 --enc sjis
python tools/agent.py lua "mem.u32(0x0894A000)"
```

`changed` lists the 4-byte words that changed with the line and then stood still: the
pointer to the current message, the count of characters shown, the window's state. `read` and
`lua` (any expression of the script API, run in the game) check what each is.

When `find` finds nothing for a line that is plainly on screen, the game numbers its
characters in a font of its own (a character table). A script for it needs that table, made
from the game, which is never published: tell the user the game cannot be added here, and why.

## 4. Write the script

Read [docs/script-api.md](docs/script-api.md) and [docs/consoles.md](docs/consoles.md), and
one or two scripts of the same console in `scripts/<console>/` (a game of the same maker or
engine is the best start). Then write `scripts/<console>/<ID>.lua`:

- the header lines (`-- reader: title`, `reads`, `version`, and `no hooks` when it uses none);
- a comment on how the game keeps its text and what is not covered;
- the build check: `python tools/agent.py lua reader.build_id`, and `error(...)` on any other;
- the reading itself: on the PS2 and the Dreamcast from `reader.on_frame` only; elsewhere a
  frame callback or a hook. Emit a line once, when the game shows it, never earlier; the
  speaker in `speaker`; choices with `channel = "choice"`;
- where the text is, `reader.layout`, when the box and the characters' cells can be found.

## 5. Try it in the game

```sh
python tools/agent.py try scripts/<console>/<ID>.lua   # copied into Furoshiki, reloaded
python tools/agent.py watch 30                         # each line as it is read
```

`try` prints the script's error if it fails to load. In a second terminal, or between
`watch` runs, press through the game and compare what `watch` prints with your pictures:

- every line shown is read once, whole, when it appears (not before the player gets to it);
- names, numbers and the player's name come out as shown;
- a choice is reported as choices, and the game goes on after one;
- nothing is read on menus, save screens or the title, unless that is meant;
- after `send "state save 1"`, more lines, and `send "state load 1"`, it still reads.

With `reader.layout`, `python tools/agent.py status --all` lists the text on screen with
each character's cell; a picture beside it shows whether the cells sit on the characters.

Fix and `try` again until it holds. Read as far into the game as is reasonable (at least
the first scenes), and note what you could not reach.

## 6. Check and offer it

```sh
python tools/check.py
python tools/agent.py stop
```

`check.py` must say 0 problems. Make a branch named after the game, commit only the script
(and a data file it asks for, if it is not taken from the game), and write the report for the
user: the game and its ID, the build, what is read, what was seen and how far, what is not
covered. With their word, push the branch to their fork and open a pull request here with that
report. Don't commit `scripts/*/index.json`: it is written when the pull request is merged.

## Where things are

| | |
| --- | --- |
| `scripts/<console>/<ID>.lua` | The scripts; each folder's `index.json` is the list Furoshiki installs from |
| `docs/script-api.md` | Everything a script can call |
| `docs/consoles.md` | Each console's processor, screen space and usual encodings |
| `tools/agent.py` | Drives Furoshiki while a script is written (`--help`) |
| `tools/check.py` | What CI checks on every pull request |
| `tools/build-lists.py` | Writes the lists (CI, after a merge) |
