# Ringbound

this is a test
`Ringbound` is a local two-player fantasy card game built with `pygame`. Players draft realm cards and hero cards, then battle through attack/defense rounds until one player reaches 6 wounds or empties their hand after the deck runs out.

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
- Click on-screen buttons such as `Take Wound`, `End Attack`, or suit choices when prompted

## Project Notes

- `main.py` contains the game loop, drafting flow, combat flow, and win-condition logic.
- `ui_elements.py` contains the card and button drawing helpers.
- `settings.py` contains shared window, color, and state constants.
- `balance_analysis.py` is a separate analysis utility and is not required to play the game.
- The game loads `36` realm cards and `12` hero cards from JSON files in `data/`.

## Rebuild The Executable

If you need to regenerate the executable on Windows:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Ringbound --add-data "data;data" main.py
```
