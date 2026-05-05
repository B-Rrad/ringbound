"""AI integration mixin for RingboundGame.

Provides schedule_ai / try_ai_turn timer logic and action execution.
Slots into the mixin chain alongside EventMixin, GameplayMixin, etc.
"""

import pygame

from ai_players import EasyAI, MediumAI, HardAI, _card_data
from settings import (
    AI_DELAY_MS,
    STATE_DIFFICULTY,
    STATE_DRAFTING,
    STATE_GAMEOVER,
    STATE_PLAYING,
    STATE_SPLASH,
    BLUE,
    GOLD,
    LIGHT_GRAY,
    RED,
    WHITE,
    WINDOW_WIDTH,
)
from ui_elements import ButtonUI, CardUI


class AIMixin:
    """Adds single-player AI opponent support to RingboundGame."""

    def ai_init(self):
        """Call from __init__ after super().__init__()."""
        self.ai_opponent = None
        self.ai_timer = 0
        self.easy_btn = ButtonUI(WINDOW_WIDTH // 2 - 120, 300, 240, 55, "Easy", (60, 160, 60))
        self.medium_btn = ButtonUI(WINDOW_WIDTH // 2 - 120, 380, 240, 55, "Medium", (180, 160, 40))
        self.hard_btn = ButtonUI(WINDOW_WIDTH // 2 - 120, 460, 240, 55, "Hard", (180, 50, 50))

    def ai_reset(self):
        """Call from reset_game_state."""
        self.ai_timer = 0

    # ------------------------------------------------------------------
    # Turn detection & scheduling
    # ------------------------------------------------------------------

    def is_ai_turn(self):
        if self.ai_opponent is None:
            return False
        if self.state == STATE_DRAFTING and self.current_drafter == "P2":
            return True
        if self.state == STATE_PLAYING and self.current_player == "P2":
            return True
        # Gollum: defender (could be P2) chooses suit
        if (self.state == STATE_PLAYING
                and self.pending_action is not None
                and self.pending_action.get("chooser") == "P2"):
            return True
        return False

    def schedule_ai(self):
        if self.ai_timer == 0 and self.is_ai_turn():
            self.ai_timer = pygame.time.get_ticks()

    def try_ai_turn(self):
        if self.ai_timer == 0 or not self.is_ai_turn():
            self.ai_timer = 0
            return
        if pygame.time.get_ticks() - self.ai_timer < AI_DELAY_MS:
            return

        self.ai_timer = 0

        if self.state == STATE_DRAFTING:
            result = self.ai_opponent.choose_draft(
                self, self.realm_draft_visuals, self.hero_draft_visuals,
            )
            if result is not None:
                visual, card_type = result
                self.attempt_draft(visual, card_type)
            self.schedule_ai()
            return

        if self.state == STATE_PLAYING:
            action = self.ai_opponent.choose_action(self, "P2")
            self._execute_ai_action(action)
            if self.state != STATE_GAMEOVER:
                self.schedule_ai()

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_ai_action(self, action):
        atype = action["type"]

        if atype == "realm":
            card_data = action["card_data"]
            hand = self.get_player_realm_hand("P2")
            if card_data in hand:
                self.attempt_play_card(CardUI(card_data, 0, 0))

        elif atype == "hero":
            self.attempt_hero_play(action["card_data"])

        elif atype == "concede":
            self.concede_defense()

        elif atype == "end_attack":
            self.end_round(defender_took_wound=False, pickup_defenses=False)

        elif atype == "suit":
            self.resolve_suit_choice(action["suit"])

        elif atype == "aragorn":
            target_data = action["card_data"]
            for atk in self.table_attacks:
                if _card_data(atk) is target_data or _card_data(atk) == target_data:
                    self.resolve_aragorn(atk)
                    break

        elif atype == "saruman":
            card_data = action["card_data"]
            if card_data is not None:
                self.resolve_saruman_exchange(card_data)

        elif atype == "hero_attack":
            card_data = action["card_data"]
            if card_data is not None:
                self.resolve_hero_attack_card(card_data)

        elif atype == "galadriel":
            player = action.get("player", "P2")
            self.activate_galadriel(player)

        elif atype == "pass":
            self.end_round(defender_took_wound=False, pickup_defenses=False)
