import json
import os
import random
import sys

import pygame

from settings import *
from ui_elements import ButtonUI, CardUI
from ai_players import EasyAI, MediumAI, HardAI, _card_data

class RingboundGame:
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
        self.suit_buttons = {}
        self.build_suit_buttons()

        self.easy_btn = ButtonUI(WINDOW_WIDTH // 2 - 120, 300, 240, 55, "Easy", (60, 160, 60))
        self.medium_btn = ButtonUI(WINDOW_WIDTH // 2 - 120, 380, 240, 55, "Medium", (180, 160, 40))
        self.hard_btn = ButtonUI(WINDOW_WIDTH // 2 - 120, 460, 240, 55, "Hard", (180, 50, 50))

        self.ai_opponent = None
        self.ai_timer = 0

        self.reset_game_state()

    def load_database(self):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(base_path, "data", "realm_cards.json"), "r", encoding="utf-8") as f:
                self.db["realm_cards"] = json.load(f)["realm_cards"]
        except FileNotFoundError:
            pass
        try:
            with open(os.path.join(base_path, "data", "hero_cards.json"), "r", encoding="utf-8") as f:
                self.db["hero_cards"] = json.load(f)["hero_cards"]
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
        self.ai_timer = 0
        self.status_message = "Click to start."

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
        for index in range(10):
            self.realm_draft_visuals.append(CardUI(self.realm_deck.pop(), start_x + (index * 120), 280))

        start_x = 160
        for index in range(8):
            self.hero_draft_visuals.append(CardUI(self.hero_deck.pop(), start_x + (index * 120), 500))

        self.status_message = f"{self.current_drafter} drafts first."

    def attempt_draft(self, visual_card, card_type):
        current_realm_hand = self.get_player_realm_hand(self.current_drafter)
        current_hero_hand = self.get_player_hero_hand(self.current_drafter)

        if card_type == "realm":
            current_realm_hand.append(visual_card.data)
            self.realm_draft_visuals.remove(visual_card)
            self.switch_drafter()
        elif card_type == "hero":
            current_hero_hand.append(visual_card.data)
            self.hero_draft_visuals.remove(visual_card)
            self.switch_drafter()

        self.check_draft_complete()

    def switch_drafter(self):
        self.current_drafter = "P2" if self.current_drafter == "P1" else "P1"
        self.status_message = f"{self.current_drafter} is drafting."

    def check_draft_complete(self):
        if len(self.realm_draft_visuals) == 0 and len(self.hero_draft_visuals) == 0:
            self.attacker = self.first_attacker
            self.defender = self.get_opponent(self.attacker)
            self.current_player = self.attacker

            self.trump_visual = CardUI(self.trump_card, 30, 50)
            self.update_hand_visuals()
            self.state = STATE_PLAYING
            self.status_message = f"{self.attacker} opens the first attack."
            self.schedule_ai()

    def can_defend_with_card(self, defense_card, attack_card):
        if attack_card is None:
            return False

        if self.round_effects["wormtongue_suit"] == defense_card["suit"]:
            return False

        if self.round_effects["nazgul_active"] and not self.is_trump_card(defense_card):
            return False

        if defense_card["suit"] == attack_card["suit"] and defense_card["rank"] > attack_card["rank"]:
            return True
        if self.is_trump_card(defense_card) and not self.is_trump_card(attack_card):
            return True
        if self.is_trump_card(defense_card) and self.is_trump_card(attack_card):
            return defense_card["rank"] > attack_card["rank"]
        return False

    def can_attack_with_card(self, attack_card):
        forced_ranks = self.round_effects["gandalf_ranks"]
        if self.play_phase == "ATTACK":
            if forced_ranks:
                return attack_card["rank"] in forced_ranks
            return True
        if self.play_phase != "REINFORCE":
            return False
        if self.round_effects["legolas_bonus"] > 0:
            return True

        valid_ranks = self.get_allowed_attack_ranks()
        if not valid_ranks:
            return True
        return attack_card["rank"] in valid_ranks

    def get_saruman_target_card(self):
        defender_hand = list(self.get_player_realm_hand(self.defender))
        if not defender_hand:
            return None

        effective_trump = self.get_effective_trump_suit()
        trump_cards = [card for card in defender_hand if effective_trump is not None and card["suit"] == effective_trump]
        if trump_cards:
            return max(trump_cards, key=lambda card: card["rank"])
        return max(defender_hand, key=lambda card: card["rank"])

    def can_use_hero(self, hero_card):
        if self.pending_action is not None:
            return False

        hero_id = hero_card["id"]
        realm_count = len(self.get_player_realm_hand(self.current_player))
        attack_card = self.get_current_attack_card()

        if hero_id == "aragorn":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and bool(self.table_attacks)
        if hero_id == "legolas":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and realm_count > 0 and self.round_effects["legolas_bonus"] == 0
        if hero_id == "gandalf":
            return self.current_player == self.defender and self.play_phase == "DEFEND" and attack_card is not None and not self.is_trump_card(attack_card.data)
        if hero_id == "galadriel":
            return self.wounds[self.current_player] > 0
        if hero_id == "frodo":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and not self.round_effects["trump_disabled"]
        if hero_id == "boromir":
            return self.current_player == self.defender and self.play_phase == "DEFEND" and attack_card is not None
        if hero_id == "nazgul":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and not self.round_effects["nazgul_active"] and self.get_effective_trump_suit() is not None
        if hero_id == "saruman":
            return self.current_player == self.attacker and self.play_phase == "ATTACK" and len(self.table_attacks) == 0 and realm_count > 0 and self.get_saruman_target_card() is not None
        if hero_id == "sauron":
            return self.current_player == self.attacker and self.play_phase == "ATTACK" and len(self.table_attacks) == 0 and self.revealed_hand is None
        if hero_id == "balrog":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and self.round_effects["balrog_active"] is None
        if hero_id == "gollum":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and not self.round_effects["trump_disabled"] and self.round_effects["temporary_trump_suit"] is None
        if hero_id == "wormtongue":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and self.round_effects["wormtongue_suit"] is None
        return False

    def update_hand_visuals(self):
        self.active_hand_visuals = []
        current_realm_hand = self.get_player_realm_hand(self.current_player)
        current_hero_hand = self.get_player_hero_hand(self.current_player)

        full_hand = current_realm_hand + current_hero_hand
        if not full_hand:
            return

        spacing = min(120, max(90, (WINDOW_WIDTH - 120) // max(1, len(full_hand))))
        total_width = ((len(full_hand) - 1) * spacing) + 110
        start_x = max(20, (WINDOW_WIDTH - total_width) // 2)

        for index, card_data in enumerate(full_hand):
            visual_card = CardUI(card_data, start_x + (index * spacing), 540)

            if self.pending_action is not None:
                if self.pending_action["type"] == "saruman_exchange":
                    visual_card.is_disabled = not self.is_realm_card(card_data)
                else:
                    visual_card.is_disabled = True
            elif self.is_hero_card(card_data):
                visual_card.is_disabled = not self.can_use_hero(card_data)
            elif self.play_phase == "DEFEND":
                attack_card = self.get_current_attack_card()
                visual_card.is_disabled = not self.can_defend_with_card(card_data, attack_card.data if attack_card else None)
            elif self.play_phase in ("ATTACK", "REINFORCE"):
                visual_card.is_disabled = not self.can_attack_with_card(card_data)
            else:
                visual_card.is_disabled = True

            self.active_hand_visuals.append(visual_card)

    def sync_turn_after_table_change(self):
        if len(self.table_attacks) > len(self.table_defenses):
            self.play_phase = "DEFEND"
            self.current_player = self.defender
            self.status_message = f"{self.defender} must answer the latest attack."
        elif self.table_attacks:
            self.play_phase = "REINFORCE"
            self.current_player = self.attacker
            self.status_message = f"{self.attacker} may reinforce or end the attack."
        elif self.round_effects["gandalf_ranks"]:
            self.play_phase = "REINFORCE"
            self.current_player = self.attacker
            self.status_message = f"{self.attacker} must continue with a played rank or end the attack."
        else:
            self.play_phase = "ATTACK"
            self.current_player = self.attacker
            self.status_message = f"{self.attacker} may lead a fresh attack."

    def discard_card(self, card_data):
        self.discard_pile.append(card_data)
        if self.is_hero_card(card_data):
            self.hero_discard.append(card_data)

    def consume_hero_card(self, player, hero_card):
        hero_hand = self.get_player_hero_hand(player)
        if hero_card in hero_hand:
            hero_hand.remove(hero_card)
            self.discard_card(hero_card)

    def remove_random_card_from_player(self, player):
        realm_hand = self.get_player_realm_hand(player)
        hero_hand = self.get_player_hero_hand(player)
        combined = realm_hand + hero_hand
        if not combined:
            return None

        discarded = random.choice(combined)
        if discarded in realm_hand:
            realm_hand.remove(discarded)
        else:
            hero_hand.remove(discarded)
        self.discard_card(discarded)
        return discarded

    def set_pending_action(self, action_type, hero_card, prompt, **kwargs):
        self.pending_action = {
            "type": action_type,
            "hero": hero_card,
            "owner": self.current_player,
            "prompt": prompt,
            **kwargs,
        }
        self.status_message = prompt
        self.update_hand_visuals()

    def attempt_hero_play(self, hero_card):
        if not self.can_use_hero(hero_card):
            return

        hero_id = hero_card["id"]

        if hero_id == "aragorn":
            self.set_pending_action(
                "aragorn_return",
                hero_card,
                "Aragorn: click one attack card on the table to return it to your hand.",
            )
            return
        if hero_id == "saruman":
            target_card = self.get_saruman_target_card()
            if target_card is None:
                return
            self.set_pending_action(
                "saruman_exchange",
                hero_card,
                f"Saruman: click one of your realm cards to swap with {target_card['name']}.",
                target_card=target_card,
            )
            return
        if hero_id == "gollum":
            self.set_pending_action(
                "choose_suit",
                hero_card,
                "Gollum: choose the suit that becomes trump for this round.",
                mode="gollum_trump",
            )
            return
        if hero_id == "wormtongue":
            self.set_pending_action(
                "choose_suit",
                hero_card,
                "Wormtongue: choose the suit the defender cannot play this round.",
                mode="wormtongue_block",
            )
            return

        self.consume_hero_card(self.current_player, hero_card)

        if hero_id == "legolas":
            self.round_effects["legolas_bonus"] = 1
            self.status_message = "Legolas is ready: your next attack this round can ignore reinforce rank."
        elif hero_id == "gandalf":
            self.resolve_gandalf()
        elif hero_id == "galadriel":
            previous_wounds = self.wounds[self.current_player]
            self.wounds[self.current_player] = max(0, previous_wounds - 2)
            healed = previous_wounds - self.wounds[self.current_player]
            self.status_message = f"Galadriel heals {healed} wound(s) for {self.current_player}."
        elif hero_id == "frodo":
            self.round_effects["trump_disabled"] = True
            self.round_effects["temporary_trump_suit"] = None
            self.status_message = "Frodo disables trump for the rest of the round."
        elif hero_id == "boromir":
            self.resolve_boromir()
        elif hero_id == "nazgul":
            self.round_effects["nazgul_active"] = True
            self.status_message = "Nazgul forces the defender to rely on trump cards only."
        elif hero_id == "sauron":
            self.revealed_hand = {
                "viewer": self.current_player,
                "target": self.get_opponent(self.current_player),
            }
            self.status_message = f"Sauron reveals {self.revealed_hand['target']}'s hand for this round."
        elif hero_id == "balrog":
            self.round_effects["balrog_active"] = self.current_player
            self.status_message = "Balrog will inflict a wound if this round is fully defended."

        self.pending_action = None
        self.check_game_over()
        if self.state != STATE_GAMEOVER:
            self.update_hand_visuals()
            self.schedule_ai()

    def resolve_gandalf(self):
        attack_card = self.get_current_attack_card()
        if attack_card is None:
            return

        played_ranks = self.get_reinforce_ranks()
        removed_attack = self.table_attacks.pop()
        self.discard_card(removed_attack.data)
        self.round_effects["gandalf_ranks"] = played_ranks

        if self.player_has_no_cards(self.defender) and len(self.table_attacks) == len(self.table_defenses):
            self.end_round(defender_took_wound=False, pickup_defenses=False)
            return

        self.sync_turn_after_table_change()
        self.status_message = "Gandalf cancels the latest non-trump attack. The attacker must continue with a played rank or end the attack."
        self.schedule_ai()

    def resolve_boromir(self):
        if self.get_current_attack_card() is None:
            return

        boromir_guard = CardUI(
            {"id": "boromir_guard", "name": "Boromir", "faction": "Fellowship", "power": "Auto-defense"},
            0,
            0,
        )
        self.table_defenses.append(boromir_guard)

        discarded = self.remove_random_card_from_player(self.attacker)
        if self.player_has_no_cards(self.defender):
            self.status_message = "Boromir defends the attack and the round ends."
            self.end_round(defender_took_wound=False, pickup_defenses=False)
            return

        if discarded is None:
            self.status_message = "Boromir auto-defends the attack."
        else:
            self.status_message = f"Boromir auto-defends. {self.attacker} discards {discarded['name']}."

        self.play_phase = "REINFORCE"
        self.current_player = self.attacker
        self.schedule_ai()

    def resolve_suit_choice(self, suit):
        hero_card = self.pending_action["hero"]
        owner = self.pending_action["owner"]
        mode = self.pending_action["mode"]
        self.consume_hero_card(owner, hero_card)

        if mode == "gollum_trump":
            self.round_effects["temporary_trump_suit"] = suit
            self.status_message = f"Gollum sets the trump suit to {suit} for this round."
        else:
            self.round_effects["wormtongue_suit"] = suit
            self.status_message = f"Wormtongue forbids the defender from playing {suit} this round."

        self.pending_action = None
        self.update_hand_visuals()
        self.schedule_ai()

    def resolve_aragorn(self, attack_visual):
        owner = self.pending_action["owner"]
        hero_card = self.pending_action["hero"]
        if attack_visual not in self.table_attacks:
            return

        attack_index = self.table_attacks.index(attack_visual)
        returned_attack = self.table_attacks.pop(attack_index)
        self.get_player_realm_hand(owner).append(returned_attack.data)

        if attack_index < len(self.table_defenses):
            removed_defense = self.table_defenses.pop(attack_index)
            self.discard_card(removed_defense.data)

        self.consume_hero_card(owner, hero_card)
        self.pending_action = None

        if self.player_has_no_cards(self.defender) and len(self.table_attacks) == len(self.table_defenses):
            self.status_message = "Aragorn recovers an attack and the defense holds."
            self.end_round(defender_took_wound=False, pickup_defenses=False)
            return

        self.sync_turn_after_table_change()
        self.status_message = "Aragorn returns an attack card to your hand."
        self.update_hand_visuals()
        self.schedule_ai()

    def resolve_saruman_exchange(self, chosen_card):
        hero_card = self.pending_action["hero"]
        owner = self.pending_action["owner"]
        target_card = self.pending_action["target_card"]
        owner_realm = self.get_player_realm_hand(owner)
        defender_realm = self.get_player_realm_hand(self.defender)

        if chosen_card not in owner_realm or target_card not in defender_realm:
            return

        owner_realm.remove(chosen_card)
        defender_realm.remove(target_card)
        owner_realm.append(target_card)
        defender_realm.append(chosen_card)

        self.consume_hero_card(owner, hero_card)
        self.pending_action = None
        self.status_message = f"Saruman swaps {chosen_card['name']} for {target_card['name']}."
        self.update_hand_visuals()
        self.schedule_ai()

    def handle_hand_card_click(self, visual_card):
        if self.pending_action is not None and self.pending_action["type"] == "saruman_exchange":
            if self.is_realm_card(visual_card.data):
                self.resolve_saruman_exchange(visual_card.data)
            return

        if self.is_hero_card(visual_card.data):
            self.attempt_hero_play(visual_card.data)
            return

        self.attempt_play_card(visual_card)

    def attempt_play_card(self, visual_card):
        current_hand = self.get_player_realm_hand(self.current_player)
        if visual_card.data not in current_hand:
            return

        current_hand.remove(visual_card.data)
        visual_card.is_disabled = False

        if self.play_phase in ["ATTACK", "REINFORCE"]:
            self.table_attacks.append(visual_card)
            if self.round_effects["gandalf_ranks"]:
                self.round_effects["gandalf_ranks"] = []
            if self.round_effects["legolas_bonus"] > 0:
                self.round_effects["legolas_bonus"] -= 1

            self.play_phase = "DEFEND"
            self.current_player = self.defender
            self.status_message = f"{self.defender} must defend {visual_card.data['name']}."
            self.update_hand_visuals()
            self.check_game_over()
            if self.state != STATE_GAMEOVER:
                self.schedule_ai()

        elif self.play_phase == "DEFEND":
            self.table_defenses.append(visual_card)

            if self.player_has_no_cards(self.defender):
                self.end_round(defender_took_wound=False, pickup_defenses=False)
            else:
                self.play_phase = "REINFORCE"
                self.current_player = self.attacker
                self.status_message = f"{self.attacker} may reinforce or end the attack."
                self.update_hand_visuals()
                self.schedule_ai()
            self.check_game_over()

    def concede_defense(self):
        self.wounds[self.defender] += 1
        self.status_message = f"{self.defender} takes a wound."
        self.end_round(defender_took_wound=True, pickup_defenses=True)

    def clear_round_state(self):
        self.table_attacks = []
        self.table_defenses = []
        self.play_phase = "ATTACK"
        self.current_player = self.attacker
        self.pending_action = None
        self.revealed_hand = None
        self.round_effects = self.new_round_effects()

    def end_round(self, defender_took_wound, pickup_defenses):
        if not defender_took_wound and self.round_effects["balrog_active"] == self.attacker:
            self.wounds[self.defender] += 1
            defender_took_wound = True
            self.status_message = f"Balrog wounds {self.defender} despite the defense."

        if not defender_took_wound:
            self.attacker, self.defender = self.defender, self.attacker
        elif pickup_defenses:
            defender_hand = self.get_player_realm_hand(self.defender)
            for defense_card in self.table_defenses:
                if self.is_realm_card(defense_card.data):
                    defender_hand.append(defense_card.data)

        for attack_card in self.table_attacks:
            self.discard_card(attack_card.data)

        for defense_card in self.table_defenses:
            if pickup_defenses and self.is_realm_card(defense_card.data):
                continue
            self.discard_card(defense_card.data)

        self.draw_back_to_six(self.attacker)
        self.draw_back_to_six(self.defender)
        self.clear_round_state()

        self.check_game_over()
        if self.state != STATE_GAMEOVER:
            if defender_took_wound:
                self.status_message = f"{self.attacker} keeps the attack."
            else:
                self.status_message = f"{self.attacker} leads the next round."
            self.update_hand_visuals()
            self.schedule_ai()

    def draw_back_to_six(self, player):
        hand = self.get_player_realm_hand(player)
        while len(hand) < 6 and len(self.realm_deck) > 0:
            hand.append(self.realm_deck.pop())

    def check_game_over(self):
        if self.wounds["P1"] >= 6:
            self.winner = "P2"
            self.state = STATE_GAMEOVER
            return
        if self.wounds["P2"] >= 6:
            self.winner = "P1"
            self.state = STATE_GAMEOVER
            return

        if len(self.realm_deck) == 0:
            p1_empty = self.player_has_no_cards("P1")
            p2_empty = self.player_has_no_cards("P2")
            if p1_empty:
                self.winner = "P1"
                self.state = STATE_GAMEOVER
            elif p2_empty:
                self.winner = "P2"
                self.state = STATE_GAMEOVER
            elif len(self.p1_hand) == 0 and len(self.p2_hand) == 0:
                # Both players have only hero cards left — stalemate.
                # Fewer wounds wins; tie goes to fewer total cards.
                if self.wounds["P1"] < self.wounds["P2"]:
                    self.winner = "P1"
                elif self.wounds["P2"] < self.wounds["P1"]:
                    self.winner = "P2"
                elif len(self.p1_heroes) <= len(self.p2_heroes):
                    self.winner = "P1"
                else:
                    self.winner = "P2"
                self.state = STATE_GAMEOVER

    def is_ai_turn(self):
        """Return True when P2 (the AI) should act."""
        if self.ai_opponent is None:
            return False
        if self.state == STATE_DRAFTING and self.current_drafter == "P2":
            return True
        if self.state == STATE_PLAYING and self.current_player == "P2":
            return True
        return False

    def schedule_ai(self):
        """Start the AI thinking timer if it isn't already running."""
        if self.ai_timer == 0 and self.is_ai_turn():
            self.ai_timer = pygame.time.get_ticks()

    def try_ai_turn(self):
        """Execute the AI's move once the delay has elapsed."""
        if self.ai_timer == 0 or not self.is_ai_turn():
            self.ai_timer = 0
            return
        if pygame.time.get_ticks() - self.ai_timer < AI_DELAY_MS:
            return

        self.ai_timer = 0

        if self.state == STATE_DRAFTING:
            visual, card_type = self.ai_opponent.choose_draft(
                self, self.realm_draft_visuals, self.hero_draft_visuals,
            )
            self.attempt_draft(visual, card_type)
            self.schedule_ai()
            return

        if self.state == STATE_PLAYING:
            action = self.ai_opponent.choose_action(self, "P2")
            self._execute_ai_action(action)
            if self.state != STATE_GAMEOVER:
                self.schedule_ai()

    def _execute_ai_action(self, action):
        """Translate an AI action dict into game method calls."""
        atype = action["type"]

        if atype == "realm":
            card_data = action["card_data"]
            visual = self._make_play_visual(card_data)
            if visual is not None:
                self.attempt_play_card(visual)

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
            self.resolve_saruman_exchange(action["card_data"])

        elif atype == "pass":
            # AI has nothing to do — end the round to avoid stalling
            self.end_round(defender_took_wound=False, pickup_defenses=False)

    def _make_play_visual(self, card_data):
        """Create a CardUI for the AI's chosen card so it can enter the
        table_attacks / table_defenses lists like a human click would."""
        hand = self.get_player_realm_hand("P2")
        if card_data not in hand:
            return None
        return CardUI(card_data, 0, 0)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()

                if self.state == STATE_SPLASH:
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
                    self.setup_game()
                    self.state = STATE_DRAFTING
                    self.schedule_ai()

                elif self.state == STATE_GAMEOVER:
                    self.reset_game_state()

                elif self.state == STATE_DRAFTING:
                    if self.is_ai_turn():
                        continue
                    for visual_card in self.realm_draft_visuals[:]:
                        if visual_card.is_clicked(mouse_pos):
                            self.attempt_draft(visual_card, "realm")
                            self.schedule_ai()
                            break
                    for visual_card in self.hero_draft_visuals[:]:
                        if visual_card.is_clicked(mouse_pos):
                            self.attempt_draft(visual_card, "hero")
                            self.schedule_ai()
                            break

                elif self.state == STATE_PLAYING:
                    if self.is_ai_turn():
                        continue

                    if self.handle_pending_click(mouse_pos):
                        self.schedule_ai()
                        continue

                    for visual_card in self.active_hand_visuals[:]:
                        if visual_card.is_clicked(mouse_pos):
                            self.handle_hand_card_click(visual_card)
                            self.schedule_ai()
                            break

                    if self.play_phase == "DEFEND" and self.pending_action is None and self.wound_btn.is_clicked(mouse_pos):
                        self.concede_defense()
                        self.schedule_ai()
                    elif self.play_phase == "REINFORCE" and self.pending_action is None and self.end_atk_btn.is_clicked(mouse_pos):
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
        prompt = self.font_regular.render("Click to Begin", True, WHITE)
        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 250))
        self.screen.blit(prompt, (WINDOW_WIDTH // 2 - prompt.get_width() // 2, 500))

    def draw_difficulty_screen(self):
        self.screen.fill(BLACK)
        title = self.font_title.render("RINGBOUND", True, WHITE)
        subtitle = self.font_subtitle.render("Choose Difficulty", True, GOLD)
        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 120))
        self.screen.blit(subtitle, (WINDOW_WIDTH // 2 - subtitle.get_width() // 2, 220))
        self.easy_btn.draw(self.screen)
        self.medium_btn.draw(self.screen)
        self.hard_btn.draw(self.screen)

        easy_desc = self.font_tiny.render("Random moves — good for learning the rules", True, LIGHT_GRAY)
        medium_desc = self.font_tiny.render("Greedy heuristics — a solid challenge", True, LIGHT_GRAY)
        hard_desc = self.font_tiny.render("Strategic play — fights to win", True, LIGHT_GRAY)
        self.screen.blit(easy_desc, (WINDOW_WIDTH // 2 - easy_desc.get_width() // 2, 360))
        self.screen.blit(medium_desc, (WINDOW_WIDTH // 2 - medium_desc.get_width() // 2, 440))
        self.screen.blit(hard_desc, (WINDOW_WIDTH // 2 - hard_desc.get_width() // 2, 520))

    def draw_game_over_screen(self):
        self.screen.fill(BLACK)
        title = self.font_title.render("GAME OVER", True, RED)

        if self.winner == "P1":
            winner_label = "You claim the One Ring!"
        else:
            ai_name = self.ai_opponent.name if self.ai_opponent else "P2"
            winner_label = f"The {ai_name} AI claims the One Ring!"
        winner_text = self.font_subtitle.render(winner_label, True, GOLD)
        prompt = self.font_regular.render("Click anywhere to return to main menu", True, LIGHT_GRAY)

        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 200))
        self.screen.blit(winner_text, (WINDOW_WIDTH // 2 - winner_text.get_width() // 2, 300))
        self.screen.blit(prompt, (WINDOW_WIDTH // 2 - prompt.get_width() // 2, 500))

    def draw_drafting_ui(self):
        self.screen.fill((50, 50, 100))
        if self.current_drafter == "P2" and self.ai_opponent is not None:
            turn_label = f"Drafting: {self.ai_opponent.name} AI"
        else:
            turn_label = f"Drafting: {self.current_drafter}"
        turn = self.font_title.render(turn_label, True, GOLD)
        p1 = self.font_small.render(f"P1 Realm: {len(self.p1_hand)} | Heroes: {len(self.p1_heroes)}", True, WHITE)
        p2 = self.font_small.render(f"P2 Realm: {len(self.p2_hand)} | Heroes: {len(self.p2_heroes)}", True, WHITE)
        self.screen.blit(turn, (WINDOW_WIDTH // 2 - turn.get_width() // 2, 30))
        self.screen.blit(p1, (50, 50))
        self.screen.blit(p2, (WINDOW_WIDTH - 250, 50))

        draft_trump_visual = CardUI(self.trump_card, 40, 92)
        draft_trump_visual.width = 90
        draft_trump_visual.height = 130
        draft_trump_visual.rect = pygame.Rect(draft_trump_visual.x, draft_trump_visual.y, draft_trump_visual.width, draft_trump_visual.height)
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
        ai_label = f"AI ({self.ai_opponent.name})" if self.ai_opponent else "P2"
        p2_wounds = self.font_regular.render(f"{ai_label} Wounds: {self.wounds['P2']}/6", True, RED)
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
            self.end_atk_btn.draw(self.screen)

        if self.pending_action is not None and self.pending_action["type"] == "choose_suit":
            chooser_label = self.font_tiny.render("Select a suit:", True, WHITE)
            self.screen.blit(chooser_label, (1020, 310))
            for button in self.suit_buttons.values():
                button.draw(self.screen)

        hand_label = self.font_regular.render(f"{self.current_player}'s Hand:", True, WHITE)
        self.screen.blit(hand_label, (WINDOW_WIDTH // 2 - hand_label.get_width() // 2, 510))

        if self.current_player == "P2" and self.ai_opponent is not None:
            ai_thinking = self.font_small.render(
                f"{self.ai_opponent.name} AI is thinking...", True, GOLD,
            )
            self.screen.blit(ai_thinking, (WINDOW_WIDTH // 2 - ai_thinking.get_width() // 2, 620))
        else:
            for visual_card in self.active_hand_visuals:
                visual_card.draw(self.screen)

        self.draw_revealed_hand_panel()
        self.draw_effects_panel()

    def run(self):
        while True:
            self.handle_events()
            self.try_ai_turn()
            if self.state == STATE_SPLASH:
                self.draw_splash_screen()
            elif self.state == STATE_DIFFICULTY:
                self.draw_difficulty_screen()
            elif self.state == STATE_DRAFTING:
                self.draw_drafting_ui()
            elif self.state == STATE_PLAYING:
                self.draw_playing_ui()
            elif self.state == STATE_GAMEOVER:
                self.draw_game_over_screen()
            pygame.display.flip()
            self.clock.tick(FPS)

if __name__ == "__main__":
    game = RingboundGame()
    game.run()
