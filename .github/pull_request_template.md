### The game

- Title (Japanese and English):
- Console and game ID:
- Build (`python tools/agent.py lua reader.build_id`):
- Release or disc version:

### What is read

<!-- The message window, speakers, furigana, choices, other screens. -->

### Where the text is on screen

- [ ] The script gives `reader.layout` for every window it reads, and each character's cell
      was checked against a picture of the game (`python tools/agent.py status --all`).
- [ ] It has no layout. Why the places could not be found:

### What was tried in the game

<!-- How far into the game, savestate save and load, a choice, menus. -->

### Not covered

<!-- Screens, modes or routes the script does not read, and what was not reached. -->

### Checks

- [ ] `python tools/check.py` says 0 problems (and no warning, or the warning is explained above).
- [ ] Only files in `games/<console>/<game>/` are changed.
