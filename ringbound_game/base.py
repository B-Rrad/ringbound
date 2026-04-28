import json
import os
import random
import sys

import pygame

from settings import (
    BLUE,
    FPS,
    RED,
    STATE_DRAFTING,
    STATE_GAMEOVER,
    STATE_PLAYING,
    STATE_SPLASH,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from ui_elements import ButtonUI, CardUI


class RingboundGameBase:
    MAX_REALM_CARDS = 6
    MAX_HERO_CARDS = 4
    DRAFT_REALM_DISPLAY_COUNT = 10
    DRAFT_HERO_DISPLAY_COUNT = 8

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Ringbound: Battle for the One Ring")
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont("Arial", 64, bold=True)
        self.font_subtitle = pygame.font.SysFont("Arial", 36, italic=True)
        self.font_regular = pygame.font.SysFont("Arial", 28)
        self.font_small = pygame.font.SysFont("Arial", 20)
        self.font_tiny = pygame.font.SysFont("Arial", 16)

        self.db = {"realm_cards": [], "hero_cards": []}
        self.all_suits = []
        self.load_database()

        self.wound_btn = ButtonUI(1020, 260, 160, 50, "Take Wound", RED)
        self.end_atk_btn = ButtonUI(1020, 260, 160, 50, "End Attack", BLUE)
        self.p1_heal_btn = ButtonUI(1010, 520, 170, 42, "P1 Heal", BLUE)
        self.p2_heal_btn = ButtonUI(1010, 570, 170, 42, "P2 Heal", BLUE)
        self.suit_buttons = {}
        self.build_suit_buttons()

        self.reset_game_state()

    def load_database(self):
        if hasattr(sys, "_MEIPASS"):
            project_root = sys._MEIPASS
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        try:
            with open(os.path.join(project_root, "data", "realm_cards.json"), "r", encoding="utf-8") as file_obj:
                self.db["realm_cards"] = json.load(file_obj)["realm_cards"]
        except FileNotFoundError:
            pass

        try:
            with open(os.path.join(project_root, "data", "hero_cards.json"), "r", encoding="utf-8") as file_obj:
                self.db["hero_cards"] = json.load(file_obj)["hero_cards"]
        except FileNotFoundError:
            pass

        self.all_suits = sorted({card["suit"] for card in self.db["realm_cards"]})

    def build_suit_buttons(self):
        start_x = 980
        start_y = 340
        for index, suit in enumerate(self.all_suits):
            self.suit_buttons[suit] = ButtonUI(
                start_x,
                start_y + (index * 46),
                190,
                38,
                suit,
                BLUE,
            )

    def new_round_effects(self):
        return {
            "trump_disabled": False,
            "temporary_trump_suit": None,
            "nazgul_active": False,
            "wormtongue_suit": None,
            "legolas_bonus": 0,
            "balrog_active": None,
            "gandalf_ranks": [],
        }

    def reset_game_state(self):
        self.state = STATE_SPLASH
        self.p1_hand = []
        self.p2_hand = []
        self.p1_heroes = []
        self.p2_heroes = []
        self.wounds = {"P1": 0, "P2": 0}
        self.winner = None
        self.win_reason = ""

        self.realm_deck = []
        self.hero_deck = []
        self.trump_card = None
        self.trump_suit = None
        self.current_drafter = None
        self.first_attacker = None

        self.attacker = None
        self.defender = None
        self.play_phase = "ATTACK"
        self.table_attacks = []
        self.table_defenses = []

        self.realm_draft_visuals = []
        self.hero_draft_visuals = []
        self.active_hand_visuals = []
        self.trump_visual = None
        self.current_player = None

        self.discard_pile = []
        self.hero_discard = []
        self.round_effects = self.new_round_effects()
        self.pending_action = None
        self.revealed_hand = None
        self.status_message = "Click to start the draft."

    def get_player_realm_hand(self, player):
        return self.p1_hand if player == "P1" else self.p2_hand

    def get_player_hero_hand(self, player):
        return self.p1_heroes if player == "P1" else self.p2_heroes

    def get_player_total_cards(self, player):
        return len(self.get_player_realm_hand(player)) + len(self.get_player_hero_hand(player))

    def get_player_combined_hand(self, player):
        return self.get_player_realm_hand(player) + self.get_player_hero_hand(player)

    def get_opponent(self, player):
        return "P2" if player == "P1" else "P1"

    def player_has_no_cards(self, player):
        return self.get_player_total_cards(player) == 0

    def player_has_no_realm_cards(self, player):
        return len(self.get_player_realm_hand(player)) == 0

    def is_hero_card(self, card_data):
        return "faction" in card_data

    def is_realm_card(self, card_data):
        return "suit" in card_data

    def get_effective_trump_suit(self):
        if self.round_effects["trump_disabled"]:
            return None
        if self.round_effects["temporary_trump_suit"] is not None:
            return self.round_effects["temporary_trump_suit"]
        return self.trump_suit

    def is_trump_card(self, card_data):
        effective_trump = self.get_effective_trump_suit()
        return effective_trump is not None and card_data.get("suit") == effective_trump

    def get_current_attack_card(self):
        if len(self.table_attacks) > len(self.table_defenses):
            return self.table_attacks[-1]
        return None

    def get_reinforce_ranks(self):
        ranks = []
        for card in self.table_attacks + self.table_defenses:
            if "rank" in card.data:
                ranks.append(card.data["rank"])
        return ranks

    def get_allowed_attack_ranks(self):
        ranks = list(self.get_reinforce_ranks())
        for rank in self.round_effects["gandalf_ranks"]:
            if rank not in ranks:
                ranks.append(rank)
        return ranks

    def setup_game(self):
        self.realm_deck = list(self.db["realm_cards"])
        self.hero_deck = list(self.db["hero_cards"])
        random.shuffle(self.realm_deck)
        random.shuffle(self.hero_deck)

        if len(self.realm_deck) < 3:
            self.winner = "Setup Error"
            self.win_reason = "At least 3 realm cards are required to start a game."
            self.state = STATE_GAMEOVER
            return False

        p1_init = self.realm_deck.pop()
        p2_init = self.realm_deck.pop()
        self.p1_hand.append(p1_init)
        self.p2_hand.append(p2_init)

        if p1_init["rank"] > p2_init["rank"]:
            self.current_drafter = "P1"
            self.first_attacker = "P2"
        elif p2_init["rank"] > p1_init["rank"]:
            self.current_drafter = "P2"
            self.first_attacker = "P1"
        else:
            self.current_drafter = random.choice(["P1", "P2"])
            self.first_attacker = "P2" if self.current_drafter == "P1" else "P1"

        self.trump_card = self.realm_deck.pop()
        self.trump_suit = self.trump_card["suit"]

        start_x = 40
        realm_display_count = min(self.DRAFT_REALM_DISPLAY_COUNT, len(self.realm_deck))
        for index in range(realm_display_count):
            self.realm_draft_visuals.append(CardUI(self.realm_deck.pop(), start_x + (index * 120), 280))

        start_x = 160
        hero_display_count = min(self.DRAFT_HERO_DISPLAY_COUNT, len(self.hero_deck))
        for index in range(hero_display_count):
            self.hero_draft_visuals.append(CardUI(self.hero_deck.pop(), start_x + (index * 120), 500))

        self.status_message = f"{self.current_drafter} drafts first."
        self.update_draft_visuals()
        self.check_draft_complete()
        return True

    def draw_back_to_six(self, player):
        hand = self.get_player_realm_hand(player)
        while len(hand) < 6 and len(self.realm_deck) > 0:
            hand.append(self.realm_deck.pop())

    def run(self):
        while True:
            self.handle_events()
            if self.state == STATE_SPLASH:
                self.draw_splash_screen()
            elif self.state == STATE_DRAFTING:
                self.draw_drafting_ui()
            elif self.state == STATE_PLAYING:
                self.draw_playing_ui()
            elif self.state == STATE_GAMEOVER:
                self.draw_game_over_screen()
            pygame.display.flip()
            self.clock.tick(FPS)
