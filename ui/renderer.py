from __future__ import annotations

from typing import Any

import pygame

from .animator import Animator, Tween, ease_out_quad
from .card_cache import CardRenderer
from .input_handler import HitTarget, InputHandler
from .layout import LayoutManager
from .theme import Theme


class Renderer:
    BACKGROUND_EXTENSIONS = (".png", ".jpg", ".jpeg")

    def __init__(self, theme: Theme, layout: LayoutManager, card_renderer: CardRenderer, animator: Animator, root_dir: str):
        self.theme = theme
        self.layout = layout
        self.card_renderer = card_renderer
        self.animator = animator
        self.root_dir = root_dir
        self._background_image = self._load_background_image()
        self._last_positions: dict[str, pygame.Rect] = {}
        self._slot_card_ids: dict[str, str] = {}
        self._card_last_rects: dict[str, pygame.Rect] = {}
        self._last_phase: str | None = None
        self._phase_flash_until = 0
        self._last_wounds: dict[str, int] = {"P1": 0, "P2": 0}
        self._wound_flash_until: dict[str, int] = {"P1": 0, "P2": 0}

    def draw(self, screen: pygame.Surface, game: Any, input_handler: InputHandler) -> list[HitTarget]:
        now = pygame.time.get_ticks()
        targets: list[HitTarget] = []

        self._draw_background(screen)

        state = getattr(game, "state", "SPLASH")
        if state == "SPLASH":
            self._draw_splash(screen, targets)
        elif state == "DRAFTING":
            self._draw_drafting(screen, game, targets, input_handler, now)
        elif state == "PLAYING":
            self._draw_playing(screen, game, targets, input_handler, now)
        else:
            self._draw_game_over(screen, game, targets)

        if input_handler.pause_confirm:
            self._draw_pause_confirm(screen, targets, input_handler)

        self._draw_custom_cursor(screen, input_handler)
        return targets

    def _load_background_image(self) -> pygame.Surface | None:
        import os

        for extension in self.BACKGROUND_EXTENSIONS:
            image_path = os.path.join(self.root_dir, f"background{extension}")
            if not os.path.isfile(image_path):
                continue

            try:
                return pygame.image.load(image_path).convert_alpha()
            except pygame.error:
                continue

        return None

    def _draw_background(self, screen: pygame.Surface) -> None:
        rect = self.layout.rects["screen"]
        if self._background_image is not None:
            background = pygame.transform.smoothscale(self._background_image, rect.size)
            screen.blit(background, (0, 0))

            tint = pygame.Surface(rect.size, pygame.SRCALPHA)
            tint.fill((*self.theme.bg, 58))
            screen.blit(tint, (0, 0))
            return

        top = self.theme.bg
        bottom = tuple(min(255, int(c * 1.2)) for c in self.theme.bg)
        for row in range(rect.height):
            t = row / max(1, rect.height)
            color = (
                int(top[0] + (bottom[0] - top[0]) * t),
                int(top[1] + (bottom[1] - top[1]) * t),
                int(top[2] + (bottom[2] - top[2]) * t),
            )
            pygame.draw.line(screen, color, (0, row), (rect.width, row))

    def _bubble_rect(self, rect: pygame.Rect, pad_x: int, pad_y: int) -> pygame.Rect:
        return pygame.Rect(rect.x - pad_x, rect.y - pad_y, rect.w + pad_x * 2, rect.h + pad_y * 2)

    def _draw_bubble(self, screen: pygame.Surface, rect: pygame.Rect, *, fill: tuple[int, int, int, int] | None = None, outline: tuple[int, int, int, int] | None = None, radius: int | None = None, shadow_offset: tuple[int, int] = (0, 3)) -> None:
        radius = radius if radius is not None else max(10, int(min(rect.w, rect.h) * 0.18))
        bubble = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill_color = fill if fill is not None else (18, 14, 22, 200)
        outline_color = outline if outline is not None else (*self.theme.accent_gold, 120)

        shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 100), shadow.get_rect().move(shadow_offset), border_radius=radius)
        screen.blit(shadow, rect.topleft)
        pygame.draw.rect(bubble, fill_color, bubble.get_rect(), border_radius=radius)
        pygame.draw.rect(bubble, outline_color, bubble.get_rect(), width=max(1, int(min(rect.w, rect.h) * 0.045)), border_radius=radius)
        screen.blit(bubble, rect.topleft)

    def _draw_text_bubble(self, screen: pygame.Surface, rect: pygame.Rect, *, fill: tuple[int, int, int, int] | None = None, outline: tuple[int, int, int, int] | None = None, radius: int | None = None, shadow_offset: tuple[int, int] = (0, 3)) -> pygame.Rect:
        bubble_rect = self._bubble_rect(rect, max(10, int(rect.h * 0.28)), max(8, int(rect.h * 0.20)))
        self._draw_bubble(screen, bubble_rect, fill=fill, outline=outline, radius=radius, shadow_offset=shadow_offset)
        return bubble_rect

    def _draw_translucent_rect(self, screen: pygame.Surface, rect: pygame.Rect, fill: tuple[int, int, int, int], outline: tuple[int, int, int, int] | None = None, border_width: int = 0, radius: int | None = None) -> None:
        radius = radius if radius is not None else max(1, int(min(rect.w, rect.h) * 0.08))
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, fill, surface.get_rect(), border_radius=radius)
        if outline is not None and border_width > 0:
            pygame.draw.rect(surface, outline, surface.get_rect(), width=border_width, border_radius=radius)
        screen.blit(surface, rect.topleft)

    def _render_text_box(self, screen: pygame.Surface, text_surface: pygame.Surface, center: tuple[int, int], *, fill: tuple[int, int, int, int] | None = None, outline: tuple[int, int, int, int] | None = None, radius: int | None = None, padding: tuple[int, int] | None = None, shadow_offset: tuple[int, int] = (0, 3)) -> pygame.Rect:
        padding_x, padding_y = padding if padding is not None else (18, 12)
        bubble_rect = text_surface.get_rect(center=center)
        bubble_rect = bubble_rect.inflate(padding_x * 2, padding_y * 2)
        self._draw_bubble(screen, bubble_rect, fill=fill, outline=outline, radius=radius, shadow_offset=shadow_offset)
        screen.blit(text_surface, text_surface.get_rect(center=bubble_rect.center))
        return bubble_rect

    def _draw_splash(self, screen: pygame.Surface, targets: list[HitTarget]) -> None:
        center = self.layout.rects["screen"].center
        title = self.layout.fonts["title"].render("RINGBOUND", True, self.theme.accent_gold)
        prompt = self.layout.fonts["heading"].render("Click to start draft", True, self.theme.text_primary)

        self._render_text_box(screen, title, (center[0], int(center[1] * 0.78)), fill=(24, 18, 30, 204), outline=(*self.theme.accent_gold, 150), radius=24, padding=(26, 18))
        prompt_rect = prompt.get_rect(center=(center[0], int(center[1] * 1.05)))
        self._render_text_box(screen, prompt, prompt_rect.center, fill=(18, 14, 22, 190), outline=(*self.theme.border_subtle, 170), radius=20, padding=(22, 14))

        # Splash controls: choose play mode
        btn_w = int(self.layout.width * 0.28)
        btn_h = int(self.layout.height * 0.065)
        gap = int(self.layout.height * 0.02)
        start_y = int(center[1] * 1.20)

        modes = [
            ("Two Players", {"mode": "2p"}),
            ("Vs Random AI", {"mode": "ai", "p2_ai": "Random"}),
            ("Vs Greedy AI", {"mode": "ai", "p2_ai": "Greedy"}),
            ("Vs Strategic AI", {"mode": "ai", "p2_ai": "Strategic"}),
        ]

        for i, (label, payload) in enumerate(modes):
            rect = pygame.Rect(center[0] - btn_w // 2, start_y + i * (btn_h + gap), btn_w, btn_h)
            pressed = False
            self._draw_button(screen, rect, label, self.theme.accent_gold if i == 0 else self.theme.gondor, pressed)
            targets.append(HitTarget(f"splash_{i}", rect, "start_game", dict(payload)))

    def _draw_game_over(self, screen: pygame.Surface, game: Any, targets: list[HitTarget]) -> None:
        center = self.layout.rects["screen"].center
        title = self.layout.fonts["title"].render("GAME OVER", True, self.theme.accent_ember)
        winner = getattr(game, "winner", "P1")
        try:
            winner_label = ("AI" if getattr(game, "get_ai", lambda p: None)(winner) is not None else "Player")
        except Exception:
            winner_label = winner
        winner_text = self.layout.fonts["phase"].render(f"{winner_label} claims the One Ring", True, self.theme.accent_gold)
        prompt = self.layout.fonts["label"].render("Click to return to splash", True, self.theme.text_primary)

        self._render_text_box(screen, title, (center[0], int(center[1] * 0.72)), fill=(30, 18, 18, 205), outline=(*self.theme.accent_ember, 150), radius=24, padding=(26, 18))
        self._render_text_box(screen, winner_text, (center[0], int(center[1] * 1.02)), fill=(22, 18, 28, 205), outline=(*self.theme.accent_gold, 150), radius=22, padding=(24, 14))
        self._render_text_box(screen, prompt, (center[0], int(center[1] * 1.28)), fill=(18, 14, 22, 190), outline=(*self.theme.border_subtle, 160), radius=18, padding=(20, 12))

        targets.append(HitTarget("gameover_restart", self.layout.rects["screen"], "restart_game", {}))

    def _draw_drafting(self, screen: pygame.Surface, game: Any, targets: list[HitTarget], input_handler: InputHandler, now: int) -> None:
        input_enabled = getattr(game, "is_human_turn", lambda: True)()

        def actor_label(player: str) -> str:
            try:
                ai = getattr(game, "get_ai", lambda p: None)(player)
            except Exception:
                ai = None
            return "AI" if ai is not None else "Player"

        heading = self.layout.fonts["phase"].render(f"Drafting: {actor_label(game.current_drafter)}", True, self.theme.accent_gold)
        self._render_text_box(screen, heading, (self.layout.rects["screen"].centerx, int(self.layout.height * 0.06)), fill=(24, 18, 30, 196), outline=(*self.theme.accent_gold, 140), radius=22, padding=(24, 14))

        p1_label = actor_label("P1")
        p2_label = actor_label("P2")
        p1 = self.layout.fonts["small"].render(f"{p1_label} Draft: {len(game.p1_hand)} realm, {len(game.p1_heroes)} hero", True, self.theme.text_primary)
        p2 = self.layout.fonts["small"].render(f"{p2_label} Draft: {len(game.p2_hand)} realm, {len(game.p2_heroes)} hero", True, self.theme.text_primary)
        draft_rule = self.layout.fonts["tiny"].render("Draft limit: 6 realm cards and 4 hero cards per player", True, self.theme.text_primary)
        self._render_text_box(screen, p1, (int(self.layout.width * 0.16), int(self.layout.height * 0.04)), fill=(18, 14, 22, 188), outline=(*self.theme.border_subtle, 150), radius=18, padding=(18, 10))
        self._render_text_box(screen, p2, (int(self.layout.width * 0.84), int(self.layout.height * 0.04)), fill=(18, 14, 22, 188), outline=(*self.theme.border_subtle, 150), radius=18, padding=(18, 10))
        self._render_text_box(screen, draft_rule, (self.layout.rects["screen"].centerx, int(self.layout.height * 0.10)), fill=(20, 16, 24, 188), outline=(*self.theme.accent_gold, 115), radius=16, padding=(20, 10))

        trump_label = self.layout.fonts["small"].render("Trump Card", True, self.theme.accent_gold)
        trump_rect = pygame.Rect(
            int(self.layout.width * 0.02),
            int(self.layout.height * 0.10),
            int(self.layout.metrics["card_w"]),
            int(self.layout.metrics["card_h"]),
        )
        self._render_text_box(screen, trump_label, (trump_rect.centerx, int(self.layout.height * 0.08)), fill=(24, 18, 30, 196), outline=(*self.theme.accent_gold, 140), radius=16, padding=(18, 10))
        if game.trump_card is not None:
            trump_surface = self.card_renderer.card_surface(game.trump_card, "normal", trump_rect.size)
            screen.blit(trump_surface, trump_rect)

        draft_x = int(self.layout.width * 0.14)
        draft_w = int(self.layout.width * 0.72)
        realm_area = pygame.Rect(draft_x, int(self.layout.height * 0.26), draft_w, int(self.layout.height * 0.27))
        hero_area = pygame.Rect(draft_x, int(self.layout.height * 0.56), draft_w, int(self.layout.height * 0.27))

        realm_rects = self.layout.place_row(realm_area, len(game.realm_draft_visuals), realm_area.centery)
        hero_rects = self.layout.place_row(hero_area, len(game.hero_draft_visuals), hero_area.centery)

        realm_enabled = input_enabled and game.can_draft_card_type(game.current_drafter, "realm")
        hero_enabled = input_enabled and game.can_draft_card_type(game.current_drafter, "hero")

        for idx, card_data in enumerate(game.realm_draft_visuals):
            self._draw_card_instance(
                screen,
                card_data,
                realm_rects[idx],
                input_handler,
                targets,
                now,
                f"draft_realm_{idx}",
                "pick_draft_card",
                {"card_type": "realm", "card_index": idx},
                enabled=realm_enabled,
            )

        for idx, card_data in enumerate(game.hero_draft_visuals):
            self._draw_card_instance(
                screen,
                card_data,
                hero_rects[idx],
                input_handler,
                targets,
                now,
                f"draft_hero_{idx}",
                "pick_draft_card",
                {"card_type": "hero", "card_index": idx},
                enabled=hero_enabled,
            )

    def _draw_playing(self, screen: pygame.Surface, game: Any, targets: list[HitTarget], input_handler: InputHandler, now: int) -> None:
        top = self.layout.rects["top_bar"]
        self._draw_translucent_rect(screen, top, (18, 14, 22, 172), (*self.theme.border_subtle, 180), max(1, int(top.h * 0.05)), radius=max(1, int(top.h * 0.14)))

        self._draw_player_header(screen, "P1", game.wounds.get("P1", 0), pygame.Rect(0, 0, int(self.layout.width * 0.32), top.height), now, game)
        self._draw_player_header(screen, "P2", game.wounds.get("P2", 0), pygame.Rect(int(self.layout.width * 0.68), 0, int(self.layout.width * 0.32), top.height), now, game)

        try:
            current_label = ("AI" if getattr(game, "get_ai", lambda p: None)(game.current_player) is not None else "Player")
        except Exception:
            current_label = game.current_player
        phase_text = f"{current_label} - {game.play_phase}"
        phase_color = self.theme.accent_gold if now < self._phase_flash_until else self.theme.text_primary
        phase_surface = self.layout.fonts["heading"].render(phase_text, True, phase_color)
        screen.blit(phase_surface, phase_surface.get_rect(center=top.center))

        if self._last_phase is not None and self._last_phase != phase_text:
            self._phase_flash_until = now + 180
        self._last_phase = phase_text

        self._draw_trump_panel(screen, game)
        self._draw_effects_panel(screen, game)
        self._draw_combat(screen, game, targets, input_handler, now)
        self._draw_hand(screen, game, targets, input_handler, now)
        self._draw_action_buttons(screen, game, targets, input_handler)

    def _draw_player_header(self, screen: pygame.Surface, player: str, wounds: int, rect: pygame.Rect, now: int, game: Any | None = None) -> None:
        try:
            ai = getattr(game, "get_ai", lambda p: None)(player)
        except Exception:
            ai = None
        display = "AI" if ai is not None else "Player"
        label = self.layout.fonts["small"].render(display, True, self.theme.text_primary)
        screen.blit(label, (rect.x + int(rect.w * 0.05), rect.y + int(rect.h * 0.20)))

        # If this player is controlled by AI, display AI tag
        ai = None
        if game is not None:
            try:
                ai = getattr(game, "get_ai", lambda p: None)(player)
            except Exception:
                ai = None
        if ai is not None:
            ai_label = self.layout.fonts["tiny"].render(f"AI: {ai.name}", True, self.theme.text_muted)
            screen.blit(ai_label, (rect.x + int(rect.w * 0.05), rect.y + int(rect.h * 0.52)))

        pip_r = max(2, int(self.layout.height * 0.008))
        start_x = rect.x + int(rect.w * 0.22)
        y = rect.y + int(rect.h * 0.50)
        spacing = pip_r * 3

        if wounds > self._last_wounds[player]:
            self._wound_flash_until[player] = now + 280
        self._last_wounds[player] = wounds

        for idx in range(6):
            x = start_x + idx * spacing
            fill = self.theme.accent_ember if idx < wounds else (40, 32, 30)
            pygame.draw.circle(screen, fill, (x, y), pip_r)
            pygame.draw.circle(screen, self.theme.border_subtle, (x, y), pip_r, width=max(1, int(pip_r * 0.3)))

        # Pulse only the most recently gained wound pip instead of flashing the whole header.
        if wounds > 0 and now < self._wound_flash_until[player]:
            pulse_idx = wounds - 1
            pulse_x = start_x + pulse_idx * spacing
            progress = (self._wound_flash_until[player] - now) / 280.0
            pulse_alpha = max(35, min(140, int(140 * progress)))
            pulse_radius = pip_r + max(1, int(pip_r * 0.7 * (1.0 - progress)))

            pulse_surface = pygame.Surface((pulse_radius * 4, pulse_radius * 4), pygame.SRCALPHA)
            pygame.draw.circle(
                pulse_surface,
                (*self.theme.accent_ember, pulse_alpha),
                (pulse_radius * 2, pulse_radius * 2),
                pulse_radius,
                width=max(1, int(pip_r * 0.45)),
            )
            screen.blit(pulse_surface, (pulse_x - pulse_radius * 2, y - pulse_radius * 2))

    def _draw_trump_panel(self, screen: pygame.Surface, game: Any) -> None:
        panel = self.layout.rects["trump_panel"]
        self._draw_translucent_rect(screen, panel, (22, 18, 28, 168), (*self.theme.border_subtle, 150), max(1, int(panel.w * 0.03)), radius=max(1, int(panel.w * 0.06)))

        label = self.layout.fonts["small"].render("RING SUIT (TRUMP)", True, self.theme.accent_gold)
        screen.blit(label, (panel.x + int(panel.w * 0.08), panel.y + int(panel.h * 0.03)))

        if game.trump_card is not None:
            card_w = int(panel.w * 0.70)
            card_h = int(card_w * 1.5)
            card_rect = pygame.Rect(panel.centerx - card_w // 2, panel.y + int(panel.h * 0.11), card_w, card_h)
            card_surface = self.card_renderer.card_surface(game.trump_card, "normal", card_rect.size)
            screen.blit(card_surface, card_rect)

        trump_text = game.get_effective_trump_suit()
        trump_line = self.layout.fonts["tiny"].render(f"Active: {trump_text if trump_text else 'None'}", True, self.theme.text_primary)
        screen.blit(trump_line, (panel.x + int(panel.w * 0.08), panel.y + int(panel.h * 0.54)))

    def _draw_effects_panel(self, screen: pygame.Surface, game: Any) -> None:
        panel = self.layout.rects["effects_panel"]
        self._draw_translucent_rect(screen, panel, (22, 18, 28, 168), (*self.theme.border_subtle, 150), max(1, int(panel.w * 0.03)), radius=max(1, int(panel.w * 0.06)))

        title = self.layout.fonts["small"].render("Round Effects", True, self.theme.accent_gold)
        screen.blit(title, (panel.x + int(panel.w * 0.08), panel.y + int(panel.h * 0.03)))

        lines: list[str] = []
        effects = game.round_effects
        trump = game.get_effective_trump_suit()
        if effects["trump_disabled"]:
            lines.append("Trump disabled")
        elif effects["temporary_trump_suit"] is not None:
            lines.append(f"Trump is {trump}")
        if effects["nazgul_active"]:
            lines.append("Defender must use trump")
        if effects["wormtongue_suit"] is not None:
            lines.append(f"Cannot play {effects['wormtongue_suit']}")
        if effects["legolas_bonus"] > 0:
            lines.append("Legolas bonus ready")
        if effects["balrog_active"] is not None:
            lines.append("Balrog wound armed")
        if not lines:
            lines.append("No active hero effects")

        y = panel.y + int(panel.h * 0.12)
        for line in lines[:7]:
            pygame.draw.circle(screen, self.theme.accent_gold, (panel.x + int(panel.w * 0.11), y + int(panel.h * 0.01)), max(1, int(self.layout.width * 0.003)))
            line_surface = self.layout.fonts["tiny"].render(line, True, self.theme.text_primary)
            screen.blit(line_surface, (panel.x + int(panel.w * 0.18), y))
            y += int(panel.h * 0.07)

    def _draw_combat(self, screen: pygame.Surface, game: Any, targets: list[HitTarget], input_handler: InputHandler, now: int) -> None:
        attack_zone = self.layout.rects["attack_zone"]
        defense_zone = self.layout.rects["defense_zone"]

        for zone, label in ((attack_zone, "ATTACK ZONE"), (defense_zone, "DEFENSE ZONE")):
            self._draw_translucent_rect(screen, zone, (26, 22, 31, 150), (*self.theme.border_subtle, 135), max(1, int(zone.h * 0.02)), radius=max(1, int(zone.h * 0.06)))
            text = self.layout.fonts["small"].render(label, True, self.theme.text_muted)
            self._render_text_box(screen, text, (zone.centerx, zone.y + int(zone.h * 0.11)), fill=(18, 14, 22, 172), outline=(*self.theme.border_subtle, 120), radius=14, padding=(16, 8))

        attack_rects = self.layout.place_row(attack_zone, len(game.table_attacks), int(attack_zone.y + attack_zone.h * 0.60))
        defense_rects = self.layout.place_row(defense_zone, len(game.table_defenses), int(defense_zone.y + defense_zone.h * 0.60))

        for idx, card_data in enumerate(game.table_attacks):
            payload = {"attack_index": idx}
            action = "select_aragorn_target"
            is_pickable = game.pending_action is not None and game.pending_action["type"] == "aragorn_return"
            self._draw_card_instance(screen, card_data, attack_rects[idx], input_handler, targets, now, f"atk_{idx}", action, payload, enabled=is_pickable)

        for idx, card_data in enumerate(game.table_defenses):
            self._draw_card_instance(screen, card_data, defense_rects[idx], input_handler, targets, now, f"def_{idx}", "noop", {}, enabled=False)

    def _draw_hand(self, screen: pygame.Surface, game: Any, targets: list[HitTarget], input_handler: InputHandler, now: int) -> None:
        hand_area = self.layout.rects["hand_area"]
        self._draw_translucent_rect(screen, hand_area, (18, 14, 22, 172), (*self.theme.border_subtle, 150), max(1, int(hand_area.h * 0.05)), radius=max(1, int(hand_area.h * 0.08)))

        try:
            ai = getattr(game, "get_ai", lambda p: None)(game.current_player)
        except Exception:
            ai = None
        caption_text = ("AI" if ai is not None else "Player") + " Hand"
        caption = self.layout.fonts["label"].render(caption_text, True, self.theme.text_primary)
        self._render_text_box(screen, caption, (hand_area.centerx, hand_area.y + int(hand_area.h * 0.12)), fill=(22, 18, 28, 196), outline=(*self.theme.accent_gold, 120), radius=16, padding=(18, 10))

        card_w, card_h = self.layout.card_size()
        hand_cards = game.active_hand_visuals
        if not hand_cards:
            return

        usable_w = hand_area.w * 0.92
        spacing = min(card_w * 0.94, usable_w / max(1, len(hand_cards) - 0.18))
        total_w = (len(hand_cards) - 1) * spacing + card_w
        start_x = hand_area.x + (hand_area.w - total_w) / 2
        y = hand_area.y + int(hand_area.h * 0.20)

        for idx, card_data in enumerate(hand_cards):
            rect = pygame.Rect(int(start_x + idx * spacing), y, card_w, card_h)
            self._draw_card_instance(
                screen,
                card_data,
                rect,
                input_handler,
                targets,
                now,
                f"hand_{idx}",
                "select_hand_card",
                {"card_index": idx},
                enabled=bool(game.is_card_playable_in_hand(card_data)),
            )

    def _draw_action_buttons(self, screen: pygame.Surface, game: Any, targets: list[HitTarget], input_handler: InputHandler) -> None:
        input_enabled = getattr(game, "is_human_turn", lambda: True)()

        if input_enabled and game.pending_action is not None and game.pending_action["type"] == "choose_suit":
            area = self.layout.rects["effects_panel"]
            prompt = self.layout.fonts["tiny"].render("Choose a suit", True, self.theme.text_primary)
            self._render_text_box(screen, prompt, (area.centerx, area.y + int(area.h * 0.66)), fill=(18, 14, 22, 196), outline=(*self.theme.accent_gold, 120), radius=14, padding=(16, 8))

            for idx, suit in enumerate(game.all_suits):
                button = pygame.Rect(
                    area.x + int(area.w * 0.08),
                    area.y + int(area.h * (0.68 + idx * 0.075)),
                    int(area.w * 0.84),
                    int(area.h * 0.06),
                )
                button_id = f"suit_{suit}"
                pressed = input_handler.is_pressed(button_id)
                self._draw_button(screen, button, suit, self.theme.suit_colors.get(suit, self.theme.accent_gold), pressed)
                targets.append(HitTarget(button_id, button, "choose_suit", {"suit": suit}))

        center = self.layout.rects["center"]
        btn = pygame.Rect(
            int(center.x + center.w * 0.77),
            int(center.y + center.h * 0.44),
            int(center.w * 0.19),
            int(center.h * 0.08),
        )
        if input_enabled and game.play_phase == "DEFEND" and game.pending_action is None:
            button_id = "btn_wound"
            self._draw_button(screen, btn, "Take Wound", self.theme.accent_ember, input_handler.is_pressed(button_id))
            targets.append(HitTarget(button_id, btn, "concede_defense", {}))
        elif input_enabled and game.play_phase == "REINFORCE" and game.pending_action is None:
            button_id = "btn_end"
            self._draw_button(screen, btn, "End Attack", self.theme.gondor, input_handler.is_pressed(button_id))
            targets.append(HitTarget(button_id, btn, "end_attack", {}))

    def _draw_button(self, screen: pygame.Surface, rect: pygame.Rect, text: str, color: tuple[int, int, int], pressed: bool) -> None:
        if pressed:
            color = tuple(max(0, int(c * (1.0 - self.theme.press_darkening))) for c in color)
        translucent = (*color, 175)
        border = (*self.theme.text_primary, 150)
        self._draw_translucent_rect(screen, rect, translucent, border, max(1, int(rect.h * 0.08)), radius=max(1, int(rect.h * 0.24)))
        label = self.layout.fonts["small"].render(text, True, self.theme.text_primary)
        screen.blit(label, label.get_rect(center=rect.center))

    def _draw_card_instance(
        self,
        screen: pygame.Surface,
        card_data: Any,
        logical_rect: pygame.Rect,
        input_handler: InputHandler,
        targets: list[HitTarget],
        now: int,
        target_id: str,
        action: str,
        payload: dict[str, Any],
        enabled: bool = True,
    ) -> None:
        card_id = self.card_renderer._id_for_card(card_data)

        targets.append(HitTarget(target_id, logical_rect.copy(), action, payload, enabled=enabled))

        state = "disabled" if not enabled else "normal"
        if input_handler.hovered == target_id and enabled:
            state = "hovered"

        scale = self.layout.metrics["hover_scale"] if state == "hovered" else 1.0
        draw_size = (int(logical_rect.w * scale), int(logical_rect.h * scale))
        draw_rect = pygame.Rect(
            logical_rect.centerx - draw_size[0] // 2,
            logical_rect.centery - draw_size[1] // 2,
            draw_size[0],
            draw_size[1],
        )

        motion_key = f"motion_{target_id}"
        previous = self._last_positions.get(motion_key)
        prior_card_id = self._slot_card_ids.get(target_id)

        # Animate any newly entered card for this slot, even if the slot coordinates are unchanged.
        if prior_card_id != card_id:
            start = self._card_last_rects.get(card_id)
            if start is None:
                start = draw_rect.copy()
                start.y = int(self.layout.height * 1.05)
            self.animator.add(Tween(motion_key, start.copy(), draw_rect.copy(), now, 180, easing=ease_out_quad, alpha_from=0, alpha_to=255))
        elif previous.topleft != draw_rect.topleft:
            self.animator.add(Tween(motion_key, previous.copy(), draw_rect.copy(), now, 180, easing=ease_out_quad))

        self._slot_card_ids[target_id] = card_id
        self._last_positions[motion_key] = draw_rect.copy()
        self._card_last_rects[card_id] = draw_rect.copy()

        anim_rect, anim_alpha = self.animator.get(motion_key, now)
        final_rect = anim_rect if anim_rect is not None else draw_rect
        final_alpha = anim_alpha if anim_alpha is not None else 255

        card_surface = self.card_renderer.card_surface(card_data, state, final_rect.size)
        if final_alpha != 255:
            card_surface = card_surface.copy()
            card_surface.set_alpha(final_alpha)

        screen.blit(card_surface, final_rect)

    def _draw_pause_confirm(self, screen: pygame.Surface, targets: list[HitTarget], input_handler: InputHandler) -> None:
        shade = pygame.Surface(self.layout.rects["screen"].size, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))

        box = pygame.Rect(
            int(self.layout.width * 0.33),
            int(self.layout.height * 0.36),
            int(self.layout.width * 0.34),
            int(self.layout.height * 0.24),
        )
        pygame.draw.rect(screen, self.theme.surface, box, border_radius=max(1, int(box.h * 0.08)))
        pygame.draw.rect(screen, self.theme.accent_gold, box, width=max(1, int(box.h * 0.03)), border_radius=max(1, int(box.h * 0.08)))

        prompt = self.layout.fonts["label"].render("Return to splash?", True, self.theme.text_primary)
        self._render_text_box(screen, prompt, (box.centerx, int(box.y + box.h * 0.34)), fill=(24, 18, 30, 205), outline=(*self.theme.accent_gold, 140), radius=18, padding=(18, 10))

        yes = pygame.Rect(int(box.x + box.w * 0.15), int(box.y + box.h * 0.60), int(box.w * 0.30), int(box.h * 0.24))
        no = pygame.Rect(int(box.x + box.w * 0.55), int(box.y + box.h * 0.60), int(box.w * 0.30), int(box.h * 0.24))

        self._draw_button(screen, yes, "Yes", self.theme.accent_ember, input_handler.is_pressed("pause_yes"))
        self._draw_button(screen, no, "No", self.theme.gondor, input_handler.is_pressed("pause_no"))
        targets.append(HitTarget("pause_yes", yes, "pause_confirm_yes", {}))
        targets.append(HitTarget("pause_no", no, "pause_confirm_no", {}))

    def _draw_custom_cursor(self, screen: pygame.Surface, input_handler: InputHandler) -> None:
        if not input_handler.is_hovering_interactive():
            pygame.mouse.set_visible(True)
            return

        pygame.mouse.set_visible(False)
        x, y = input_handler.mouse_pos
        radius = max(4, int(self.layout.height * 0.008))
        pygame.draw.circle(screen, self.theme.accent_gold, (x, y), radius, width=max(1, int(radius * 0.4)))
        pygame.draw.line(screen, self.theme.accent_gold, (x - radius * 2, y), (x + radius * 2, y), max(1, int(radius * 0.3)))
        pygame.draw.line(screen, self.theme.accent_gold, (x, y - radius * 2), (x, y + radius * 2), max(1, int(radius * 0.3)))
