from __future__ import annotations

from typing import Any

import pygame

from .layout import LayoutManager
from .theme import Theme


class CardCache:
    def __init__(self):
        self._cache: dict[tuple[str, str, int, int], pygame.Surface] = {}

    def clear(self) -> None:
        self._cache.clear()

    def get(self, key: tuple[str, str, int, int]) -> pygame.Surface | None:
        return self._cache.get(key)

    def put(self, key: tuple[str, str, int, int], surface: pygame.Surface) -> None:
        self._cache[key] = surface


class CardRenderer:
    def __init__(self, theme: Theme, layout: LayoutManager):
        self.theme = theme
        self.layout = layout
        self.cache = CardCache()

    def clear_cache(self) -> None:
        self.cache.clear()

    def _id_for_card(self, card: dict[str, Any]) -> str:
        base = card.get("id", card.get("name", "card"))
        suit = card.get("suit", "")
        rank = card.get("rank", "")
        return f"{base}|{suit}|{rank}"

    def card_surface(self, card: dict[str, Any], state: str, size: tuple[int, int]) -> pygame.Surface:
        w, h = size
        key = (self._id_for_card(card), state, w, h)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if "faction" in card:
            surface = self._draw_hero_card(card, state, size)
        else:
            surface = self._draw_realm_card(card, state, size)

        self.cache.put(key, surface)
        return surface

    def _draw_realm_card(self, card: dict[str, Any], state: str, size: tuple[int, int]) -> pygame.Surface:
        w, h = size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        suit = card.get("suit", "")
        suit_color = self.theme.suit_colors.get(suit, self.theme.accent_gold)

        radius = max(1, int(w * 0.09))
        border = max(1, int(w * 0.03))
        card_rect = pygame.Rect(0, 0, w, h)

        if state == "hovered":
            glow = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*suit_color, self.theme.hover_glow_alpha), glow.get_rect(), border_radius=radius)
            surf.blit(glow, (0, 0))

        pygame.draw.rect(surf, self.theme.surface, card_rect, border_radius=radius)
        pygame.draw.rect(surf, suit_color, card_rect, width=border, border_radius=radius)

        title = self.layout.fonts["small"].render(suit.upper(), True, self.theme.text_muted)
        rank = self.layout.fonts["phase"].render(str(card.get("rank", "")), True, suit_color)
        surf.blit(title, (int(w * 0.08), int(h * 0.06)))
        surf.blit(rank, rank.get_rect(center=(int(w * 0.50), int(h * 0.52))))

        self._draw_suit_icon(surf, suit, suit_color, w, h)

        if state == "selected":
            pygame.draw.rect(surf, self.theme.selected_outline, card_rect, width=max(2, int(w * 0.045)), border_radius=radius)

        if state == "disabled":
            self._apply_disabled_overlay(surf)

        return surf

    def _draw_hero_card(self, card: dict[str, Any], state: str, size: tuple[int, int]) -> pygame.Surface:
        w, h = size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        radius = max(1, int(w * 0.09))
        border = max(1, int(w * 0.03))
        card_rect = pygame.Rect(0, 0, w, h)

        if state == "hovered":
            glow = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*self.theme.accent_gold, self.theme.hover_glow_alpha), glow.get_rect(), border_radius=radius)
            surf.blit(glow, (0, 0))

        pygame.draw.rect(surf, self.theme.surface, card_rect, border_radius=radius)
        pygame.draw.rect(surf, self.theme.accent_gold, card_rect, width=border, border_radius=radius)

        faction = card.get("faction", "")
        faction_color = self.theme.fellowship if faction == "Fellowship" else self.theme.shadow

        name_surface = self.layout.fonts["label"].render(card.get("name", "HERO"), True, self.theme.text_primary)
        faction_surface = self.layout.fonts["small"].render(faction, True, faction_color)

        surf.blit(name_surface, (int(w * 0.08), int(h * 0.08)))
        surf.blit(faction_surface, (int(w * 0.08), int(h * 0.23)))
        self._draw_faction_crest(surf, faction, faction_color, w, h)

        text_rect = pygame.Rect(int(w * 0.08), int(h * 0.38), int(w * 0.84), int(h * 0.56))
        lines = self._wrap(card.get("power", "Hero power"), self.layout.fonts["tiny"], text_rect.width)
        y = text_rect.y
        for line in lines[:6]:
            line_surface = self.layout.fonts["tiny"].render(line, True, self.theme.text_primary)
            surf.blit(line_surface, (text_rect.x, y))
            y += max(1, int(h * 0.07))

        if state == "selected":
            pygame.draw.rect(surf, self.theme.selected_outline, card_rect, width=max(2, int(w * 0.045)), border_radius=radius)

        if state == "disabled":
            self._apply_disabled_overlay(surf)

        return surf

    def _draw_suit_icon(self, surface: pygame.Surface, suit: str, color: tuple[int, int, int], w: int, h: int) -> None:
        cx = int(w * 0.83)
        cy = int(h * 0.16)
        icon_w = int(w * 0.14)
        icon_h = int(h * 0.12)

        if suit == "Gondor":
            points = [
                (cx, cy - icon_h // 2),
                (cx - icon_w // 3, cy + icon_h // 3),
                (cx - icon_w // 5, cy + icon_h // 2),
                (cx + icon_w // 5, cy + icon_h // 2),
                (cx + icon_w // 3, cy + icon_h // 3),
            ]
            pygame.draw.polygon(surface, self.theme.text_primary, points)
            pygame.draw.rect(surface, self.theme.text_primary, pygame.Rect(cx - max(1, icon_w // 10), cy + icon_h // 4, max(1, icon_w // 5), max(1, icon_h // 2)))
        elif suit == "Shire":
            pygame.draw.ellipse(surface, color, pygame.Rect(cx - icon_w // 2, cy - icon_h // 2, icon_w, icon_h))
            pygame.draw.line(surface, self.theme.text_primary, (cx - icon_w // 4, cy + icon_h // 3), (cx + icon_w // 4, cy - icon_h // 3), max(1, icon_w // 10))
        elif suit == "Mordor":
            pygame.draw.ellipse(surface, color, pygame.Rect(cx - icon_w // 2, cy - icon_h // 3, icon_w, int(icon_h * 0.7)))
            pygame.draw.ellipse(surface, self.theme.bg, pygame.Rect(cx - icon_w // 4, cy - icon_h // 6, icon_w // 2, icon_h // 3))
            pygame.draw.circle(surface, self.theme.text_primary, (cx, cy), max(1, icon_w // 10))
        elif suit == "Rohan":
            horse = [
                (cx - icon_w // 2, cy),
                (cx - icon_w // 6, cy - icon_h // 3),
                (cx + icon_w // 4, cy - icon_h // 4),
                (cx + icon_w // 2, cy),
                (cx + icon_w // 6, cy + icon_h // 3),
                (cx - icon_w // 4, cy + icon_h // 3),
            ]
            pygame.draw.polygon(surface, color, horse)

    def _draw_faction_crest(self, surface: pygame.Surface, faction: str, color: tuple[int, int, int], w: int, h: int) -> None:
        cx = int(w * 0.84)
        cy = int(h * 0.22)
        size = int(min(w, h) * 0.10)
        if faction == "Fellowship":
            pygame.draw.polygon(surface, color, [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], width=0)
            pygame.draw.circle(surface, self.theme.surface, (cx, cy), max(1, size // 3))
        else:
            pygame.draw.circle(surface, color, (cx, cy), size)
            pygame.draw.circle(surface, self.theme.surface, (cx, cy), max(1, size // 2), width=max(1, size // 4))

    def _apply_disabled_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill(self.theme.disabled_overlay)

        step = max(4, int(surface.get_width() * 0.08))
        for x in range(-surface.get_height(), surface.get_width(), step):
            pygame.draw.line(
                overlay,
                self.theme.disabled_pattern,
                (x, 0),
                (x + surface.get_height(), surface.get_height()),
                max(1, int(surface.get_width() * 0.015)),
            )

        surface.blit(overlay, (0, 0))

    def _wrap(self, text: str, font: pygame.font.Font, max_w: int) -> list[str]:
        words = text.split()
        if not words:
            return []

        lines = [words[0]]
        for word in words[1:]:
            candidate = f"{lines[-1]} {word}"
            if font.size(candidate)[0] <= max_w:
                lines[-1] = candidate
            else:
                lines.append(word)
        return lines
