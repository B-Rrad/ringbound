from __future__ import annotations

from typing import Any

import pygame

from .animator import Animator, Tween, ease_out_quad
from .card_cache import CardRenderer
from .input_handler import HitTarget, InputHandler
from .layout import LayoutManager
from .theme import Theme


class Renderer:
    def __init__(self, theme: Theme, layout: LayoutManager, card_renderer: CardRenderer, animator: Animator):
        self.theme = theme
        self.layout = layout
        self.card_renderer = card_renderer
        self.animator = animator
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

    def _draw_background(self, screen: pygame.Surface) -> None:
        rect = self.layout.rects["screen"]
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

    def _draw_splash(self, screen: pygame.Surface, targets: list[HitTarget]) -> None:
        center = self.layout.rects["screen"].center
        title = self.layout.fonts["title"].render("RINGBOUND", True, self.theme.accent_gold)
        prompt = self.layout.fonts["heading"].render("Click to start draft", True, self.theme.text_primary)

        screen.blit(title, title.get_rect(center=(center[0], int(center[1] * 0.78))))
        prompt_rect = prompt.get_rect(center=(center[0], int(center[1] * 1.15)))
        screen.blit(prompt, prompt_rect)

        targets.append(HitTarget("splash_start", self.layout.rects["screen"], "start_game", {}))

    def _draw_game_over(self, screen: pygame.Surface, game: Any, targets: list[HitTarget]) -> None:
        center = self.layout.rects["screen"].center
        title = self.layout.fonts["title"].render("GAME OVER", True, self.theme.accent_ember)
        winner = getattr(game, "winner", "P1")
        winner_text = self.layout.fonts["phase"].render(f"{winner} claims the One Ring", True, self.theme.accent_gold)
        prompt = self.layout.fonts["label"].render("Click to return to splash", True, self.theme.text_primary)

        screen.blit(title, title.get_rect(center=(center[0], int(center[1] * 0.72))))
        screen.blit(winner_text, winner_text.get_rect(center=(center[0], int(center[1] * 1.02))))
        screen.blit(prompt, prompt.get_rect(center=(center[0], int(center[1] * 1.28))))

        targets.append(HitTarget("gameover_restart", self.layout.rects["screen"], "restart_game", {}))

    def _draw_drafting(self, screen: pygame.Surface, game: Any, targets: list[HitTarget], input_handler: InputHandler, now: int) -> None:
        heading = self.layout.fonts["phase"].render(f"Drafting: {game.current_drafter}", True, self.theme.accent_gold)
        screen.blit(heading, heading.get_rect(center=(self.layout.rects["screen"].centerx, int(self.layout.height * 0.06))))

        p1 = self.layout.fonts["small"].render(f"P1 Draft: {len(game.p1_hand)} realm, {len(game.p1_heroes)} hero", True, self.theme.text_primary)
        p2 = self.layout.fonts["small"].render(f"P2 Draft: {len(game.p2_hand)} realm, {len(game.p2_heroes)} hero", True, self.theme.text_primary)
        draft_rule = self.layout.fonts["tiny"].render("Draft limit: 6 realm cards and 4 hero cards per player", True, self.theme.text_primary)
        screen.blit(p1, (int(self.layout.width * 0.02), int(self.layout.height * 0.02)))
        screen.blit(p2, (int(self.layout.width * 0.78), int(self.layout.height * 0.02)))
        screen.blit(draft_rule, draft_rule.get_rect(center=(self.layout.rects["screen"].centerx, int(self.layout.height * 0.10))))

        trump_label = self.layout.fonts["small"].render("Trump Card", True, self.theme.accent_gold)
        trump_rect = pygame.Rect(
            int(self.layout.width * 0.02),
            int(self.layout.height * 0.10),
            int(self.layout.metrics["card_w"]),
            int(self.layout.metrics["card_h"]),
        )
        screen.blit(trump_label, (trump_rect.x, int(self.layout.height * 0.07)))
        if game.trump_card is not None:
            trump_surface = self.card_renderer.card_surface(game.trump_card, "normal", trump_rect.size)
            screen.blit(trump_surface, trump_rect)

        realm_area = pygame.Rect(int(self.layout.width * 0.16), int(self.layout.height * 0.26), int(self.layout.width * 0.80), int(self.layout.height * 0.27))
        hero_area = pygame.Rect(int(self.layout.width * 0.16), int(self.layout.height * 0.56), int(self.layout.width * 0.80), int(self.layout.height * 0.27))

        realm_rects = self.layout.place_row(realm_area, len(game.realm_draft_visuals), realm_area.centery)
        hero_rects = self.layout.place_row(hero_area, len(game.hero_draft_visuals), hero_area.centery)

        realm_enabled = game.can_draft_card_type(game.current_drafter, "realm")
        hero_enabled = game.can_draft_card_type(game.current_drafter, "hero")

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
        pygame.draw.rect(screen, (18, 14, 22), top)
        pygame.draw.line(screen, self.theme.border_subtle, (0, top.bottom - 1), (self.layout.width, top.bottom - 1), max(1, int(self.layout.height * 0.002)))

        self._draw_player_header(screen, "P1", game.wounds.get("P1", 0), pygame.Rect(0, 0, int(self.layout.width * 0.32), top.height), now)
        self._draw_player_header(screen, "P2", game.wounds.get("P2", 0), pygame.Rect(int(self.layout.width * 0.68), 0, int(self.layout.width * 0.32), top.height), now)

        phase_text = f"{game.current_player} - {game.play_phase}"
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

    def _draw_player_header(self, screen: pygame.Surface, player: str, wounds: int, rect: pygame.Rect, now: int) -> None:
        label = self.layout.fonts["small"].render(player, True, self.theme.text_primary)
        screen.blit(label, (rect.x + int(rect.w * 0.05), rect.y + int(rect.h * 0.20)))

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
        pygame.draw.rect(screen, (22, 18, 28), panel)
        pygame.draw.line(screen, self.theme.border_subtle, (panel.right - 1, panel.y), (panel.right - 1, panel.bottom), max(1, int(self.layout.width * 0.001)))

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
        pygame.draw.rect(screen, (22, 18, 28), panel)
        pygame.draw.line(screen, self.theme.border_subtle, (panel.x, panel.y), (panel.x, panel.bottom), max(1, int(self.layout.width * 0.001)))

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
            pygame.draw.rect(screen, (26, 22, 31), zone, border_radius=max(1, int(zone.h * 0.06)))
            pygame.draw.rect(screen, self.theme.border_subtle, zone, width=max(1, int(zone.h * 0.02)), border_radius=max(1, int(zone.h * 0.06)))
            text = self.layout.fonts["small"].render(label, True, self.theme.text_muted)
            screen.blit(text, (zone.centerx - text.get_width() // 2, zone.y + int(zone.h * 0.06)))

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
        pygame.draw.rect(screen, (18, 14, 22), hand_area)
        pygame.draw.line(screen, self.theme.border_subtle, (0, hand_area.y), (self.layout.width, hand_area.y), max(1, int(self.layout.height * 0.002)))

        caption = self.layout.fonts["label"].render(f"{game.current_player} Hand", True, self.theme.text_primary)
        screen.blit(caption, (hand_area.centerx - caption.get_width() // 2, hand_area.y + int(hand_area.h * 0.05)))

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
        if game.pending_action is not None and game.pending_action["type"] == "choose_suit":
            area = self.layout.rects["effects_panel"]
            prompt = self.layout.fonts["tiny"].render("Choose a suit", True, self.theme.text_primary)
            screen.blit(prompt, (area.x + int(area.w * 0.08), area.y + int(area.h * 0.62)))

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
        if game.play_phase == "DEFEND" and game.pending_action is None:
            button_id = "btn_wound"
            self._draw_button(screen, btn, "Take Wound", self.theme.accent_ember, input_handler.is_pressed(button_id))
            targets.append(HitTarget(button_id, btn, "concede_defense", {}))
        elif game.play_phase == "REINFORCE" and game.pending_action is None:
            button_id = "btn_end"
            self._draw_button(screen, btn, "End Attack", self.theme.gondor, input_handler.is_pressed(button_id))
            targets.append(HitTarget(button_id, btn, "end_attack", {}))

    def _draw_button(self, screen: pygame.Surface, rect: pygame.Rect, text: str, color: tuple[int, int, int], pressed: bool) -> None:
        if pressed:
            color = tuple(max(0, int(c * (1.0 - self.theme.press_darkening))) for c in color)
        pygame.draw.rect(screen, color, rect, border_radius=max(1, int(rect.h * 0.24)))
        pygame.draw.rect(screen, self.theme.text_primary, rect, width=max(1, int(rect.h * 0.08)), border_radius=max(1, int(rect.h * 0.24)))
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
        screen.blit(prompt, prompt.get_rect(center=(box.centerx, int(box.y + box.h * 0.34))))

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
