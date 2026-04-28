import sys

import pygame

from ai_players import EasyAI, MediumAI, HardAI
from settings import (
    STATE_DIFFICULTY,
    STATE_DRAFTING,
    STATE_GAMEOVER,
    STATE_MODE_SELECT,
    STATE_PLAYING,
    STATE_SPLASH,
)


class EventMixin:
    def handle_draft_clicks(self, mouse_pos):
        for visual_card in self.realm_draft_visuals[:]:
            if visual_card.is_clicked(mouse_pos):
                self.attempt_draft(visual_card, "realm")
                return True

        for visual_card in self.hero_draft_visuals[:]:
            if visual_card.is_clicked(mouse_pos):
                self.attempt_draft(visual_card, "hero")
                return True

        return False

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()

                if self.state == STATE_SPLASH:
                    self.state = STATE_MODE_SELECT

                elif self.state == STATE_MODE_SELECT:
                    if self.two_player_btn.is_clicked(mouse_pos):
                        self.ai_opponent = None
                        if self.setup_game():
                            self.state = STATE_DRAFTING
                    elif self.vs_ai_btn.is_clicked(mouse_pos):
                        self.state = STATE_DIFFICULTY

                elif self.state == STATE_DIFFICULTY:
                    if self.easy_btn.is_clicked(mouse_pos):
                        self.ai_opponent = EasyAI()
                    elif self.medium_btn.is_clicked(mouse_pos):
                        self.ai_opponent = MediumAI()
                    elif self.hard_btn.is_clicked(mouse_pos):
                        self.ai_opponent = HardAI()
                    else:
                        continue
                    if self.setup_game():
                        self.state = STATE_DRAFTING
                        self.schedule_ai()

                elif self.state == STATE_GAMEOVER:
                    self.reset_game_state()

                elif self.state == STATE_DRAFTING:
                    if self.is_ai_turn():
                        continue
                    if self.handle_draft_clicks(mouse_pos):
                        self.schedule_ai()
                        continue

                elif self.state == STATE_PLAYING:
                    if self.is_ai_turn():
                        continue

                    if self.can_activate_galadriel("P1") and self.p1_heal_btn.is_clicked(mouse_pos):
                        self.activate_galadriel("P1")
                        self.schedule_ai()
                        continue
                    if self.ai_opponent is None and self.can_activate_galadriel("P2") and self.p2_heal_btn.is_clicked(mouse_pos):
                        self.activate_galadriel("P2")
                        continue
                    if self.handle_pending_click(mouse_pos):
                        self.schedule_ai()
                        continue

                    for visual_card in self.active_hand_visuals[:]:
                        if visual_card.is_clicked(mouse_pos):
                            self.handle_hand_card_click(visual_card)
                            self.schedule_ai()
                            break

                    if self.can_concede_defense() and self.wound_btn.is_clicked(mouse_pos):
                        self.concede_defense()
                        self.schedule_ai()
                    elif self.can_end_attack() and self.end_atk_btn.is_clicked(mouse_pos):
                        self.end_round(defender_took_wound=False, pickup_defenses=False)
                        self.schedule_ai()

    def handle_pending_click(self, mouse_pos):
        if self.pending_action is None:
            return False

        action_type = self.pending_action["type"]
        if action_type == "choose_suit":
            for suit, button in self.suit_buttons.items():
                if button.is_clicked(mouse_pos):
                    self.resolve_suit_choice(suit)
                    return True
            return True

        if action_type == "aragorn_return":
            for attack_card in self.table_attacks:
                if attack_card.is_clicked(mouse_pos):
                    self.resolve_aragorn(attack_card)
                    return True
            return True

        return False
