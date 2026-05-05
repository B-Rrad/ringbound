Project Change Log (canonical record)

Purpose
------
This file is the canonical, human-editable change log for the repository. Use it to record
any structural, modularization, or notable functional changes so they can be easily
referenced by developers, reviewers, or automated tools.

How to use
----------
- Add a dated entry for each change with a short title, the author, and a brief description.
- Include a short list of files modified and the reason for the change.
- Keep entries concise — link to PRs or commits for deeper context.

Current entries
---------------
- 2026-05-04 — Extract AI and resource responsibilities (GitHub Copilot)
  - Files added: `ai_manager.py`, `resource_manager.py`
  - Files modified: `main.py`
  - Summary: Centralized AI creation and environment config into `ai_manager.py`. Centralized
    music discovery and card DB loading into `resource_manager.py`. Updated `main.py` to
    consume these modules so that future changes to AI or data sources won't conflict with
    UI or core game logic.

Future intent
-------------
This file will be used going forward to record similar refactors, modularization efforts,
and any cross-cutting changes that could impact AI, data sources, or the UI. When making
future changes, append a new dated entry following the template above.

Developer checklist (recommended)
-------------------------------
- Run the game and validate audio and data loading:

```bash
python main.py
```
- Add unit tests for `ai_manager.make_ai()` and `resource_manager.load_cards()`.
- If packaging with pyinstaller, double-check `_MEIPASS` resource_root behavior.

Summary
- Extracted AI factory and environment configuration into `ai_manager.py`.
- Extracted resource functions (music discovery and card DB loading) into `resource_manager.py`.
- Updated `main.py` to use the new modules, reducing responsibilities of the game core.

Why
- Centralizing AI creation reduces duplication and isolates AI selection logic so future AI changes (including AI-driven modifications) won't conflict with game or UI code.
- Centralizing resource and data loading makes it easier to swap data sources (e.g., different JSON, DB, or AI-generated content) without touching game logic.

Files added
- `ai_manager.py` — provides `make_ai(name)` and `configure_ai_from_env()`.
- `resource_manager.py` — provides `discover_music_tracks(resource_root)` and `load_cards(base_path)`.
- `MODULARIZATION.md` — this document listing changes.

Files modified
- `main.py`
  - Replaced inline AI factory and environment setup with calls to `ai_manager.configure_ai_from_env()` and `ai_manager.make_ai()`.
  - Replaced music discovery and database loading with `resource_manager.discover_music_tracks()` and `resource_manager.load_cards()`.
  - Removed now-duplicated helper methods: `_discover_music_tracks`, `load_database`, and `_configure_ai_from_env`.

Notes for future AI integration
- To add or change AI implementations, edit or add classes in `balance_analysis.py` and use `ai_manager.make_ai()` to obtain instances.
- To provide AI-generated card data or alternative data sources, implement a new loader in `resource_manager.py` (for example, `load_cards_from_ai()`), and call it from `main.py` where `load_cards()` is used.
- UI or other systems that need to query AIs should call `game.get_ai(player)` to obtain the currently assigned AI instance.

Developer checklist (recommended next steps)
- Run the game and verify audio still starts and cards load normally.
- Consider adding unit tests around `ai_manager.make_ai()` and `resource_manager.load_cards()`.
- If packaging the app (pyinstaller), confirm that `resource_root` and `_MEIPASS` logic are unchanged and still function.
