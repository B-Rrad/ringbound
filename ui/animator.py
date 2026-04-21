from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame


def ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_in_out(t: float) -> float:
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass
class Tween:
    key: str
    start_rect: pygame.Rect
    end_rect: pygame.Rect
    start_time_ms: int
    duration_ms: int
    easing: Callable[[float], float] = ease_out_quad
    alpha_from: int = 255
    alpha_to: int = 255

    def sample(self, now_ms: int) -> tuple[pygame.Rect, int, bool]:
        elapsed = max(0, now_ms - self.start_time_ms)
        progress = min(1.0, elapsed / max(1, self.duration_ms))
        eased = self.easing(progress)

        rect = pygame.Rect(
            int(lerp(self.start_rect.x, self.end_rect.x, eased)),
            int(lerp(self.start_rect.y, self.end_rect.y, eased)),
            int(lerp(self.start_rect.w, self.end_rect.w, eased)),
            int(lerp(self.start_rect.h, self.end_rect.h, eased)),
        )
        alpha = int(lerp(self.alpha_from, self.alpha_to, eased))
        return rect, alpha, progress >= 1.0


class Animator:
    def __init__(self):
        self.tweens: list[Tween] = []

    def add(self, tween: Tween) -> None:
        self.tweens = [t for t in self.tweens if t.key != tween.key]
        self.tweens.append(tween)

    def get(self, key: str, now_ms: int) -> tuple[pygame.Rect | None, int | None]:
        for tween in self.tweens:
            if tween.key == key:
                rect, alpha, done = tween.sample(now_ms)
                if done:
                    self.tweens = [t for t in self.tweens if t.key != key]
                return rect, alpha
        return None, None

    def has_active(self) -> bool:
        return bool(self.tweens)
