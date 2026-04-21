from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pygame


@dataclass
class Intent:
    action: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class HitTarget:
    target_id: str
    rect: pygame.Rect
    action: str
    payload: dict[str, Any]
    enabled: bool = True


class InputHandler:
    def __init__(self):
        self.targets: list[HitTarget] = []
        self.hovered: str | None = None
        self.pressed: str | None = None
        self.mouse_pos: tuple[int, int] = (0, 0)
        self.pause_confirm: bool = False

    def update_targets(self, targets: list[HitTarget]) -> None:
        self.targets = targets
        self.rehit_test(self.mouse_pos)

    def rehit_test(self, mouse_pos: tuple[int, int]) -> None:
        self.mouse_pos = mouse_pos
        self.hovered = None
        for target in reversed(self.targets):
            if target.enabled and target.rect.collidepoint(mouse_pos):
                self.hovered = target.target_id
                return

    def is_hovering_interactive(self) -> bool:
        return self.hovered is not None

    def is_pressed(self, target_id: str) -> bool:
        return self.pressed == target_id

    def handle_event(self, event: pygame.event.Event) -> Intent | None:
        if event.type == pygame.MOUSEMOTION:
            self.rehit_test(event.pos)
            return None

        if event.type == pygame.VIDEORESIZE:
            self.rehit_test(self.mouse_pos)
            return Intent("rehit_test", {"mouse_pos": self.mouse_pos})

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.pause_confirm = True
                return None
            if event.key == pygame.K_r:
                return Intent("request_redraw", {})
            if event.key == pygame.K_SPACE:
                return Intent("confirm_selection", {})

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.rehit_test(event.pos)
            self.pressed = self.hovered
            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.rehit_test(event.pos)
            if self.pressed is None:
                return None

            clicked = self.pressed
            self.pressed = None
            if clicked != self.hovered:
                return None

            for target in reversed(self.targets):
                if target.target_id == clicked and target.enabled:
                    return Intent(target.action, dict(target.payload))

        return None
