from __future__ import annotations

from pathlib import Path

import pygame


class FontCache:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self._cache: dict[tuple[str, int], pygame.font.Font] = {}

        fonts_dir = self.root_dir / "fonts"
        self.display_path = str(fonts_dir / "DejaVuSerif-Bold.ttf")
        self.body_path = str(fonts_dir / "LiberationSerif-Regular.ttf")
        self.mono_path = str(fonts_dir / "DejaVuSansMono.ttf")

    def clear(self) -> None:
        self._cache.clear()

    def get(self, font_path: str, point_size: int) -> pygame.font.Font:
        safe_size = max(1, int(point_size))
        key = (font_path, safe_size)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            font = pygame.font.Font(font_path, safe_size)
        except Exception:
            font = pygame.font.Font(self.mono_path, safe_size)

        self._cache[key] = font
        return font
