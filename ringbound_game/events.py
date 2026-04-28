import sys

import pygame

from settings import STATE_DRAFTING, STATE_GAMEOVER, STATE_PLAYING, STATE_SPLASH


class EventMixin:
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()

                if self.state == STATE_SPLASH:
                    self.setup_game()
                    self.state = STATE_DRAFTING

                elif self.state == STATE_GAMEOVER:
                    self.reset_game_state()

                elif self.state == STATE_DRAFTING:
                    for visual_card in self.realm_draft_visuals[:]:
                        if visual_card.is_clicked(mouse_pos):
                            self.attempt_draft(visual_card, "realm")
                            break
                    for visual_card in self.hero_draft_visuals[:]:
                        if visual_card.is_clicked(mouse_pos):
                            self.attempt_draft(visual_card, "hero")
                            break

                elif self.state == STATE_PLAYING:
                    if self.can_activate_galadriel("P1") and self.p1_heal_btn.is_clicked(mouse_pos):
                        self.activate_galadriel("P1")
                        continue
                    if self.can_activate_galadriel("P2") and self.p2_heal_btn.is_clicked(mouse_pos):
                        self.activate_galadriel("P2")
                        continue
                    if self.handle_pending_click(mouse_pos):
                        continue

                    for visual_card in self.active_hand_visuals[:]:
                        if visual_card.is_clicked(mouse_pos):
                            self.handle_hand_card_click(visual_card)
                            break

                    if self.play_phase == "DEFEND" and self.pending_action is None and self.wound_btn.is_clicked(mouse_pos):
                        self.concede_defense()
                    elif self.play_phase in ("ATTACK", "REINFORCE") and self.pending_action is None and self.end_atk_btn.is_clicked(mouse_pos):
                        self.end_round(defender_took_wound=False, pickup_defenses=False)

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
