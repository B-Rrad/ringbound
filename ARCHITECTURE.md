# UI Architecture

## Data Flow

1. `main.py` owns all game rules and state mutation.
2. `UIController` receives pygame events and returns high-level `Intent` values.
3. `main.py` maps each intent to existing rule methods (`attempt_draft`, `handle_hand_card_click`, `resolve_suit_choice`, etc.).
4. `main.py` calls `ui.draw(screen, self)` every frame.
5. `Renderer` reads the immutable snapshot of game state and draws the scene.

This keeps UI rendering/input separate from rule enforcement.

## Package Layout

- `ui/__init__.py`: `UIController` and public export surface.
- `ui/theme.py`: design tokens and color constants.
- `ui/font_cache.py`: cached `pygame.font.Font` objects by file path and point size.
- `ui/layout.py`: `LayoutManager` computes all responsive rectangles and scaled font sizes.
- `ui/card_cache.py`: vector card rendering and surface cache keyed by card/state/size.
- `ui/animator.py`: tween model and easing for short UI animations.
- `ui/input_handler.py`: event routing and click-hit logic returning `Intent`.
- `ui/renderer.py`: full scene composition for splash, drafting, playing, and game over.

## Resize Behavior

- `main.py` listens for `VIDEORESIZE`.
- Window is recreated with `pygame.RESIZABLE` dimensions clamped to at least `1024x600`.
- `UIController.on_resize()` calls `LayoutManager.reflow(new_w, new_h)` and clears cached card surfaces.
- Input re-hit-testing runs immediately so hover state stays correct.

## Adding a New Card Type

1. Add the card shape/text rules in `ui/card_cache.py`.
2. Extend cache key construction if the new card introduces extra visual state.
3. Ensure game state passes a distinct marker field so renderer can branch card drawing.

## Adding a New Game Phase

1. Keep game logic in `main.py` (phase transitions and legality checks).
2. Add phase presentation in `ui/renderer.py` (labels, actionable buttons, zones).
3. Add any new interactions in `ui/input_handler.py` as intents.
4. Map new intents in `RingboundGame.handle_intent`.

## Performance Notes

- Card surfaces are cached and reused; drawing primitives are not rerun every frame for unchanged size/state.
- Font objects are cached and rebuilt only on resize.
- Animations are time-based and non-blocking (no sleep/wait in main loop).
