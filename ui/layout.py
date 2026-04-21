from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from .font_cache import FontCache


@dataclass
class LayoutManager:
    width: int
    height: int
    font_cache: FontCache
    rects: dict[str, pygame.Rect] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    fonts: dict[str, pygame.font.Font] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.reflow(self.width, self.height)

    def reflow(self, new_w: int, new_h: int) -> None:
        self.width = max(1024, int(new_w))
        self.height = max(600, int(new_h))

        top_h = int(self.height * 0.08)
        hand_h = int(self.height * 0.20)
        mid_h = self.height - top_h - hand_h
        side_w = int(self.width * 0.12)
        center_w = self.width - (side_w * 2)

        self.rects["screen"] = pygame.Rect(0, 0, self.width, self.height)
        self.rects["top_bar"] = pygame.Rect(0, 0, self.width, top_h)
        self.rects["trump_panel"] = pygame.Rect(0, top_h, side_w, mid_h)
        self.rects["effects_panel"] = pygame.Rect(self.width - side_w, top_h, side_w, mid_h)
        self.rects["center"] = pygame.Rect(side_w, top_h, center_w, mid_h)
        self.rects["hand_area"] = pygame.Rect(0, top_h + mid_h, self.width, hand_h)

        combat_h = int(mid_h * 0.84)
        combat_y = self.rects["center"].y + int(mid_h * 0.03)
        self.rects["combat_area"] = pygame.Rect(self.rects["center"].x, combat_y, center_w, combat_h)

        self.rects["attack_zone"] = pygame.Rect(
            self.rects["combat_area"].x + int(center_w * 0.03),
            self.rects["combat_area"].y + int(combat_h * 0.03),
            int(center_w * 0.94),
            int(combat_h * 0.40),
        )
        self.rects["defense_zone"] = pygame.Rect(
            self.rects["combat_area"].x + int(center_w * 0.03),
            self.rects["combat_area"].y + int(combat_h * 0.57),
            int(center_w * 0.94),
            int(combat_h * 0.40),
        )

        card_w_cap_by_panel = self.rects["attack_zone"].w / 6.4
        card_w_cap_by_height = (self.rects["hand_area"].h * 0.74) / 1.5
        card_w_floor = min(self.width, self.height) * 0.045
        card_w = max(card_w_floor, min(card_w_cap_by_panel, card_w_cap_by_height))
        card_h = card_w * 1.5

        self.metrics["card_w"] = card_w
        self.metrics["card_h"] = card_h
        self.metrics["card_radius"] = card_w * 0.08
        self.metrics["stroke"] = max(1.0, card_w * 0.03)
        self.metrics["hover_scale"] = 1.06
        self.metrics["hand_overlap"] = card_w * 0.24

        self._rebuild_fonts()

    def _rebuild_fonts(self) -> None:
        self.font_cache.clear()
        display = self.font_cache.display_path
        body = self.font_cache.body_path

        self.fonts["title"] = self.font_cache.get(display, int(self.height * 0.070))
        self.fonts["phase"] = self.font_cache.get(display, int(self.height * 0.040))
        self.fonts["heading"] = self.font_cache.get(display, int(self.height * 0.030))
        self.fonts["label"] = self.font_cache.get(body, int(self.height * 0.024))
        self.fonts["body"] = self.font_cache.get(body, int(self.height * 0.021))
        self.fonts["small"] = self.font_cache.get(body, int(self.height * 0.018))
        self.fonts["tiny"] = self.font_cache.get(body, int(self.height * 0.016))

    def card_size(self) -> tuple[int, int]:
        return int(self.metrics["card_w"]), int(self.metrics["card_h"])

    def place_row(self, area: pygame.Rect, count: int, y_center: int) -> list[pygame.Rect]:
        if count <= 0:
            return []

        card_w, card_h = self.card_size()
        usable_w = area.w * 0.94
        spacing = min(card_w * 0.96, usable_w / max(1, count - 0.2))
        total_w = (count - 1) * spacing + card_w
        start_x = area.x + (area.w - total_w) / 2

        rects: list[pygame.Rect] = []
        for idx in range(count):
            rects.append(
                pygame.Rect(
                    int(start_x + idx * spacing),
                    int(y_center - card_h / 2),
                    int(card_w),
                    int(card_h),
                )
            )
        return rects
