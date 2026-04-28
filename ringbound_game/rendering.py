import pygame

from settings import BLACK, DARK_GREEN, GOLD, LIGHT_GRAY, RED, WHITE, WINDOW_HEIGHT, WINDOW_WIDTH
from ui_elements import CardUI


class RenderingMixin:
    def wrap_text(self, text, font, max_width):
        words = text.split()
        if not words:
            return []

        lines = []
        current_line = words[0]
        for word in words[1:]:
            candidate = f"{current_line} {word}"
            if font.size(candidate)[0] <= max_width:
                current_line = candidate
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        return lines

    def draw_text_block(self, text, font, color, rect, line_gap=4, max_lines=None):
        lines = self.wrap_text(text, font, rect.width)
        if max_lines is not None:
            lines = lines[:max_lines]

        y_pos = rect.y
        for line in lines:
            text_surface = font.render(line, True, color)
            self.screen.blit(text_surface, (rect.x, y_pos))
            y_pos += text_surface.get_height() + line_gap

    def draw_splash_screen(self):
        self.screen.fill(BLACK)
        title = self.font_title.render("RINGBOUND", True, WHITE)
        prompt = self.font_regular.render("Click to Start Draft", True, WHITE)
        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 250))
        self.screen.blit(prompt, (WINDOW_WIDTH // 2 - prompt.get_width() // 2, 500))

    def draw_game_over_screen(self):
        self.screen.fill(BLACK)
        title = self.font_title.render("GAME OVER", True, RED)
        winner_text = self.font_subtitle.render(f"{self.winner} claims the One Ring!", True, GOLD)
        prompt = self.font_regular.render("Click anywhere to return to main menu", True, LIGHT_GRAY)
        reason_rect = pygame.Rect(WINDOW_WIDTH // 2 - 290, 360, 580, 70)

        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 200))
        self.screen.blit(winner_text, (WINDOW_WIDTH // 2 - winner_text.get_width() // 2, 300))
        pygame.draw.rect(self.screen, (30, 30, 30), reason_rect, border_radius=8)
        pygame.draw.rect(self.screen, WHITE, reason_rect, 2, border_radius=8)
        self.draw_text_block(self.win_reason or "Victory condition reached.", self.font_tiny, WHITE, reason_rect.inflate(-14, -12), max_lines=3)
        self.screen.blit(prompt, (WINDOW_WIDTH // 2 - prompt.get_width() // 2, 500))

    def draw_drafting_ui(self):
        self.screen.fill((50, 50, 100))
        turn = self.font_title.render(f"Drafting: {self.current_drafter}", True, GOLD)
        p1_text = self.font_small.render(f"P1 Realm: {len(self.p1_hand)} | Heroes: {len(self.p1_heroes)}", True, WHITE)
        p2_text = self.font_small.render(f"P2 Realm: {len(self.p2_hand)} | Heroes: {len(self.p2_heroes)}", True, WHITE)
        rule_text = self.font_tiny.render("Draft limit: 6 Realm Cards and 4 Hero Cards per player.", True, WHITE)
        self.screen.blit(turn, (WINDOW_WIDTH // 2 - turn.get_width() // 2, 30))
        self.screen.blit(p1_text, (50, 50))
        self.screen.blit(p2_text, (WINDOW_WIDTH - 250, 50))
        self.screen.blit(rule_text, (WINDOW_WIDTH // 2 - rule_text.get_width() // 2, 80))

        draft_trump_visual = CardUI(self.trump_card, 40, 92)
        draft_trump_visual.width = 90
        draft_trump_visual.height = 130
        draft_trump_visual.rect = pygame.Rect(
            draft_trump_visual.x,
            draft_trump_visual.y,
            draft_trump_visual.width,
            draft_trump_visual.height,
        )
        draft_trump_visual.draw(self.screen)

        trump_label = self.font_small.render("Trump Card", True, GOLD)
        trump_detail = self.font_tiny.render("This card sets the trump suit for the game.", True, WHITE)
        self.screen.blit(trump_label, (40, 230))
        self.screen.blit(trump_detail, (40, 256))

        for card in self.realm_draft_visuals:
            card.draw(self.screen)
        for card in self.hero_draft_visuals:
            card.draw(self.screen)

    def draw_revealed_hand_panel(self):
        if self.revealed_hand is None:
            return

        panel = pygame.Rect(20, 240, 245, 230)
        pygame.draw.rect(self.screen, (18, 55, 18), panel, border_radius=8)
        pygame.draw.rect(self.screen, WHITE, panel, 2, border_radius=8)

        title = self.font_small.render(f"{self.revealed_hand['target']} Hand", True, GOLD)
        self.screen.blit(title, (panel.x + 10, panel.y + 10))

        cards = self.get_player_combined_hand(self.revealed_hand["target"])
        y_pos = panel.y + 42
        if not cards:
            empty_text = self.font_tiny.render("No cards remaining.", True, LIGHT_GRAY)
            self.screen.blit(empty_text, (panel.x + 10, y_pos))
            return

        for card in cards[:9]:
            label = self.font_tiny.render(card["name"], True, WHITE)
            self.screen.blit(label, (panel.x + 10, y_pos))
            y_pos += 20

    def draw_effects_panel(self):
        panel = pygame.Rect(20, 405, 245, 125)
        pygame.draw.rect(self.screen, (18, 55, 18), panel, border_radius=8)
        pygame.draw.rect(self.screen, WHITE, panel, 2, border_radius=8)

        title = self.font_small.render("Round Effects", True, GOLD)
        self.screen.blit(title, (panel.x + 10, panel.y + 10))

        effect_lines = []
        effective_trump = self.get_effective_trump_suit()
        if self.round_effects["trump_disabled"]:
            effect_lines.append("Trump disabled")
        elif self.round_effects["temporary_trump_suit"] is not None:
            effect_lines.append(f"Trump is now {effective_trump}")
        if self.round_effects["nazgul_active"]:
            effect_lines.append("Defender must use trump")
        if self.round_effects["wormtongue_suit"] is not None:
            effect_lines.append(f"Defender cannot play {self.round_effects['wormtongue_suit']}")
        if self.round_effects["legolas_bonus"] > 0:
            effect_lines.append("Legolas bonus attack ready")
        if self.round_effects["balrog_active"] is not None:
            effect_lines.append("Balrog wound is armed")
        if not effect_lines:
            effect_lines.append("No active hero effects")

        y_pos = panel.y + 42
        for line in effect_lines[:4]:
            text_surface = self.font_tiny.render(line, True, WHITE)
            self.screen.blit(text_surface, (panel.x + 10, y_pos))
            y_pos += 22

    def draw_playing_ui(self):
        self.screen.fill(DARK_GREEN)

        trump_label = self.font_small.render("RING SUIT (TRUMP)", True, GOLD)
        self.screen.blit(trump_label, (30, 20))
        self.trump_visual.draw(self.screen)

        effective_trump = self.get_effective_trump_suit()
        trump_text = f"Active trump: {effective_trump}" if effective_trump is not None else "Active trump: None"
        trump_status = self.font_tiny.render(trump_text, True, WHITE)
        self.screen.blit(trump_status, (30, 220))

        turn_text = self.font_regular.render(f"Active Player: {self.current_player} ({self.play_phase})", True, WHITE)
        self.screen.blit(turn_text, (WINDOW_WIDTH // 2 - turn_text.get_width() // 2, 20))

        p1_wounds = self.font_regular.render(f"P1 Wounds: {self.wounds['P1']}/6", True, RED)
        p2_wounds = self.font_regular.render(f"P2 Wounds: {self.wounds['P2']}/6", True, RED)
        self.screen.blit(p1_wounds, (WINDOW_WIDTH - 220, 30))
        self.screen.blit(p2_wounds, (WINDOW_WIDTH - 220, 70))

        status_rect = pygame.Rect(310, 62, 650, 46)
        pygame.draw.rect(self.screen, (22, 90, 22), status_rect, border_radius=8)
        pygame.draw.rect(self.screen, WHITE, status_rect, 2, border_radius=8)
        self.draw_text_block(self.status_message, self.font_tiny, WHITE, status_rect.inflate(-16, -10), max_lines=2)

        attack_zone = pygame.Rect(WINDOW_WIDTH // 2 - 350, 130, 700, 180)
        defense_zone = pygame.Rect(WINDOW_WIDTH // 2 - 350, 330, 700, 180)
        pygame.draw.rect(self.screen, (20, 100, 20), attack_zone, border_radius=10)
        pygame.draw.rect(self.screen, (20, 100, 20), defense_zone, border_radius=10)
        pygame.draw.rect(self.screen, WHITE, attack_zone, 2, border_radius=10)
        pygame.draw.rect(self.screen, WHITE, defense_zone, 2, border_radius=10)

        attack_label = self.font_regular.render("ATTACK ZONE", True, LIGHT_GRAY)
        defense_label = self.font_regular.render("DEFENSE ZONE", True, LIGHT_GRAY)
        self.screen.blit(attack_label, (WINDOW_WIDTH // 2 - attack_label.get_width() // 2, 190))
        self.screen.blit(defense_label, (WINDOW_WIDTH // 2 - defense_label.get_width() // 2, 400))

        start_x = WINDOW_WIDTH // 2 - 300
        for index, attack_card in enumerate(self.table_attacks):
            attack_card.x = start_x + (index * 120)
            attack_card.y = 140
            attack_card.rect.topleft = (attack_card.x, attack_card.y)
            attack_card.draw(self.screen)
            if self.pending_action is not None and self.pending_action["type"] == "aragorn_return":
                pygame.draw.rect(self.screen, GOLD, attack_card.rect, 4, border_radius=4)

        for index, defense_card in enumerate(self.table_defenses):
            defense_card.x = start_x + (index * 120)
            defense_card.y = 340
            defense_card.rect.topleft = (defense_card.x, defense_card.y)
            defense_card.draw(self.screen)

        if self.play_phase == "DEFEND" and self.pending_action is None:
            self.wound_btn.draw(self.screen)
        elif self.play_phase == "REINFORCE" and self.pending_action is None:
            self.end_atk_btn.text = "End Attack"
            self.end_atk_btn.draw(self.screen)
        elif self.play_phase == "ATTACK" and self.pending_action is None and not self.current_player_has_attack_action():
            self.end_atk_btn.text = "Pass Attack"
            self.end_atk_btn.draw(self.screen)

        if self.pending_action is not None and self.pending_action["type"] == "choose_suit":
            chooser_label = self.font_tiny.render("Select a suit:", True, WHITE)
            self.screen.blit(chooser_label, (1020, 310))
            for button in self.suit_buttons.values():
                button.draw(self.screen)

        if self.can_activate_galadriel("P1"):
            self.p1_heal_btn.draw(self.screen)
        if self.can_activate_galadriel("P2"):
            self.p2_heal_btn.draw(self.screen)

        hand_label = self.font_regular.render(f"{self.current_player}'s Hand:", True, WHITE)
        self.screen.blit(hand_label, (WINDOW_WIDTH // 2 - hand_label.get_width() // 2, 510))
        for visual_card in self.active_hand_visuals:
            visual_card.draw(self.screen)

        self.draw_revealed_hand_panel()
        self.draw_effects_panel()
