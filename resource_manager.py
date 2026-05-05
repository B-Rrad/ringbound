import json
import os
from pathlib import Path
from typing import Dict, Any, Tuple


def discover_music_tracks(resource_root: str, extensions=('.mp3',)):
    music_dir = Path(resource_root) / "music"
    if not music_dir.is_dir():
        return []
    return [str(path) for path in sorted(music_dir.iterdir()) if path.is_file() and path.suffix.lower() in extensions]


def load_cards(base_path: str) -> Dict[str, Any]:
    db = {"realm_cards": [], "hero_cards": []}
    try:
        with open(os.path.join(base_path, "data", "realm_cards.json"), "r", encoding="utf-8") as f:
            db["realm_cards"] = json.load(f).get("realm_cards", [])
    except FileNotFoundError:
        pass
    try:
        with open(os.path.join(base_path, "data", "hero_cards.json"), "r", encoding="utf-8") as f:
            db["hero_cards"] = json.load(f).get("hero_cards", [])
    except FileNotFoundError:
        pass

    return db
