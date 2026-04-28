from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import pygame

from .animator import Animator
from .card_cache import CardRenderer
from .font_cache import FontCache
from .input_handler import InputHandler, Intent
from .layout import LayoutManager
from .renderer import Renderer
from .theme import Theme


@dataclass
class UIController:
    initial_size: tuple[int, int]
    root_dir: str = field(default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def __post_init__(self) -> None:
        self.theme = Theme()
        self.font_cache = FontCache(self.root_dir)
        self.layout_manager = LayoutManager(self.initial_size[0], self.initial_size[1], self.font_cache)
        self.animator = Animator()
        self.card_renderer = CardRenderer(self.theme, self.layout_manager)
        self.input_handler = InputHandler()
        self.renderer = Renderer(self.theme, self.layout_manager, self.card_renderer, self.animator, self.root_dir)
        self._last_targets = []

    def handle_event(self, event: pygame.event.Event) -> Intent | None:
        return self.input_handler.handle_event(event)

    def draw(self, screen: pygame.Surface, game_state: Any) -> None:
        targets = self.renderer.draw(screen, game_state, self.input_handler)
        self.input_handler.update_targets(targets)
        self._last_targets = targets

    def on_resize(self, new_w: int, new_h: int) -> None:
        self.layout_manager.reflow(new_w, new_h)
        self.card_renderer.clear_cache()
        self.input_handler.rehit_test(self.input_handler.mouse_pos)

    def resolve_space_intent(self) -> Intent | None:
        enabled = [target for target in self._last_targets if target.enabled]
        if len(enabled) == 1:
            only = enabled[0]
            return Intent(only.action, dict(only.payload))
        return None


__all__ = ["Intent", "UIController"]
