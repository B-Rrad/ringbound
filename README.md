# Ringbound

`Ringbound` is a local two-player fantasy card game built with `pygame`. Players draft realm cards and hero cards, then battle through attack/defense rounds until one player reaches 6 wounds or wins the realm-deck endgame.

## Submission Contents

This repository includes:

- Full source code for the game
- A prebuilt Windows executable at `release/Ringbound.exe`
- Game data files in `data/`

The gameplay video can be found here: https://youtu.be/C1FrNUbSaL8

## Repository Layout

```text
ringbound/
|-- data/
|   |-- hero_cards.json
|   `-- realm_cards.json
|-- ringbound_game/
|   |-- base.py
|   |-- events.py
|   |-- game.py
|   |-- gameplay.py
|   `-- rendering.py
|-- release/
|   `-- Ringbound.exe
|-- main.py
|-- settings.py
|-- ui_elements.py
|-- balance_analysis.py
|-- requirements.txt
|-- .gitignore
`-- README.md
```

## Requirements

- Windows 10/11 to run the included executable
- Python 3.12+ and `pygame` if running from source

## Run The Prebuilt Executable

1. Download using GitHub's 'Download ZIP' option.
2. Extract the ZIP.
3. Open the `release` folder.
4. Double-click `Ringbound.exe`.

## Run From Source

1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Start the game:

```powershell
python main.py
```

## Controls

- Mouse only
- Click on the splash screen to begin the draft
- Click cards to draft or play them
- Click on-screen buttons such as `Take Wound`, `End Attack`, `Pass Attack`, `P1 Heal`, `P2 Heal`, or suit choices when prompted

## Gameplay Rules

- Each player finishes the draft with a maximum of `6` realm cards and `4` hero cards. The opening realm card counts toward that limit.
- After a defended round, the defender becomes the next attacker. If the defender takes a wound, the attacker keeps the initiative.
- When the realm deck is empty, drawing stops. The endgame is then decided by empty realm hands first, then fewer wounds, then fewer total remaining cards.

## Hero Timing Notes

- `Galadriel` may be used at any time while that player has wounds remaining.
- `Saruman` and `Sauron` are start-of-round attack tools.
- `Gandalf` and `Boromir` are defensive responses.
- `Legolas` and `Balrog` must be played together with a realm attack card.
- `Gollum` lets the defender choose the temporary trump suit for the round.

## Project Notes

- `main.py` is the launch entrypoint for the game.
- `ringbound_game/base.py` owns setup, shared state, card loading, and the main loop shell.
- `ringbound_game/gameplay.py` owns drafting, combat flow, hero powers, and win-condition logic.
- `ringbound_game/events.py` owns mouse input and state-driven click handling.
- `ringbound_game/rendering.py` owns screen drawing and panel/layout helpers.
- `ui_elements.py` contains the card and button drawing helpers.
- `settings.py` contains shared window, color, and state constants.
- `balance_analysis.py` is a separate analysis utility and is not required to play the game.
- The game loads `36` realm cards and `12` hero cards from JSON files in `data/`.
- The game-over screen includes a short reason so special endgame outcomes and tiebreaks are visible to the player.

## Rebuild The Executable

If you need to regenerate the executable on Windows:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Ringbound --add-data "data;data" main.py
```
