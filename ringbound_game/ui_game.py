import os
import random
import sys

import pygame

from ai_manager import make_ai, configure_ai_from_env
from resource_manager import discover_music_tracks, load_cards

from settings import *
from ui import UIController

class RingboundGame:
    MAX_REALM_CARDS = 6
    MAX_HERO_CARDS = 4
    MUSIC_END_EVENT = pygame.USEREVENT + 1
    MUSIC_EXTENSIONS = (".mp3",)

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Ringbound: Battle for the One Ring")
        self.clock = pygame.time.Clock()

        self.resource_root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        self.music_tracks = discover_music_tracks(self.resource_root)
        self.music_enabled = False
        self.music_index = 0

        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        self.db = load_cards(base_path)
        self.all_suits = sorted({card["suit"] for card in self.db["realm_cards"]})

        # AI players: set via environment variables `RINGBOUND_P1_AI` / `RINGBOUND_P2_AI`
        self.p1_ai, self.p2_ai = configure_ai_from_env()
        self._last_ai_action = 0
        self._ai_action_delay_ms = 220
        self._last_draft_action = 0
        self._draft_action_delay_ms = 160

        self.ui = UIController((WINDOW_WIDTH, WINDOW_HEIGHT), self.resource_root)
        self._start_music()
        self.reset_game_state()



    def _start_music(self):
        if not self.music_tracks:
            return

        try:
            pygame.mixer.init()
            pygame.mixer.music.set_endevent(self.MUSIC_END_EVENT)
        except pygame.error:
            self.music_enabled = False
            return

        self.music_enabled = True
        self.music_index = 0
        self._play_music_track(self.music_index)

    def _play_music_track(self, track_index):
        if not self.music_enabled or not self.music_tracks:
            return

        track_count = len(self.music_tracks)
        for offset in range(track_count):
            candidate_index = (track_index + offset) % track_count
            track_path = self.music_tracks[candidate_index]
            try:
                pygame.mixer.music.load(track_path)
                pygame.mixer.music.play()
                self.music_index = candidate_index
                return
            except pygame.error:
                continue

        self.music_enabled = False

    def _advance_music(self):
        if not self.music_enabled or not self.music_tracks:
            return

        self._play_music_track(self.music_index + 1)



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
        self.current_player = None

        self.discard_pile = []
        self.hero_discard = []
        self.round_effects = self.new_round_effects()
        self.pending_action = None
        self.revealed_hand = None
        self.status_message = "Click to start the draft."



    def get_ai(self, player):
        return self.p1_ai if player == "P1" else self.p2_ai

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
            if "rank" in card:
                ranks.append(card["rank"])
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

        for index in range(10):
            self.realm_draft_visuals.append(self.realm_deck.pop())

        for index in range(8):
            self.hero_draft_visuals.append(self.hero_deck.pop())

        self.status_message = f"{self.current_drafter} drafts first."

    def step_drafting(self):
        # Auto-resolve draft picks for AI players
        if self.state != STATE_DRAFTING:
            return

        drafter = self.current_drafter
        ai = self.get_ai(drafter)
        if ai is None:
            return

        now = pygame.time.get_ticks()
        if now - self._last_draft_action < self._draft_action_delay_ms:
            return

        # Prefer realm picks until full, otherwise pick hero
        pick_type = None
        if self.can_draft_card_type(drafter, "realm") and self.realm_draft_visuals:
            pick_type = "realm"
            # choose highest-rank realm
            best_idx = 0
            best_rank = -999
            for idx, card in enumerate(self.realm_draft_visuals):
                rank = card.get("rank", 0)
                if rank > best_rank:
                    best_rank = rank
                    best_idx = idx
            pick_index = best_idx
        elif self.can_draft_card_type(drafter, "hero") and self.hero_draft_visuals:
            pick_type = "hero"
            # choose random hero
            pick_index = random.randrange(len(self.hero_draft_visuals))
        else:
            return

        self.attempt_draft(pick_index, pick_type)
        self._last_draft_action = now

    def can_draft_card_type(self, player, card_type):
        if player is None:
            return False
        if card_type == "realm":
            return len(self.get_player_realm_hand(player)) < self.MAX_REALM_CARDS
        if card_type == "hero":
            return len(self.get_player_hero_hand(player)) < self.MAX_HERO_CARDS
        return False

    def update_draft_visuals(self):
        return

    def attempt_draft(self, card_index, card_type):
        if not self.can_draft_card_type(self.current_drafter, card_type):
            return

        current_realm_hand = self.get_player_realm_hand(self.current_drafter)
        current_hero_hand = self.get_player_hero_hand(self.current_drafter)

        if card_type == "realm" and 0 <= card_index < len(self.realm_draft_visuals):
            current_realm_hand.append(self.realm_draft_visuals.pop(card_index))
            self.switch_drafter()
        elif card_type == "hero" and 0 <= card_index < len(self.hero_draft_visuals):
            current_hero_hand.append(self.hero_draft_visuals.pop(card_index))
            self.switch_drafter()
        else:
            return

        self.check_draft_complete()

    def switch_drafter(self):
        self.current_drafter = "P2" if self.current_drafter == "P1" else "P1"
        self.status_message = f"{self.current_drafter} is drafting."
        self.update_draft_visuals()

    def check_draft_complete(self):
        if len(self.realm_draft_visuals) == 0 and len(self.hero_draft_visuals) == 0:
            self.attacker = self.first_attacker
            self.defender = self.get_opponent(self.attacker)
            self.current_player = self.attacker

            self.update_hand_visuals()
            self.state = STATE_PLAYING
            self.status_message = f"{self.attacker} opens the first attack."

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
            return self.current_player == self.defender and self.play_phase == "DEFEND" and attack_card is not None and not self.is_trump_card(attack_card)
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
        if self.current_player is None:
            return
        current_realm_hand = self.get_player_realm_hand(self.current_player)
        current_hero_hand = self.get_player_hero_hand(self.current_player)
        self.active_hand_visuals = current_realm_hand + current_hero_hand

    # AI compatibility helpers (used by balance_analysis AIs)
    def get_known_opponent_cards(self, player):
        if self.revealed_hand is not None and self.revealed_hand.get("viewer") == player:
            return list(self.get_player_realm_hand(self.get_opponent(player)))
        return None

    def legal_attack_cards(self, player):
        return [card for card in self.get_player_realm_hand(player) if self.can_attack_with_card(card)]

    def legal_defense_cards(self, player):
        attack_card = None
        if len(self.table_attacks) > len(self.table_defenses):
            attack_card = self.table_attacks[-1]
        if attack_card is None:
            return []
        return [card for card in self.get_player_realm_hand(player) if self.can_defend_with_card(card, attack_card)]

    def usable_heroes(self, player):
        heroes = list(self.get_player_hero_hand(player))
        usable = []
        for hero in heroes:
            prev = self.current_player
            self.current_player = player
            try:
                if self.can_use_hero(hero):
                    usable.append(hero)
            finally:
                self.current_player = prev
        return usable

    def step_ai(self):
        now = pygame.time.get_ticks()
        if now - getattr(self, "_last_ai_action", 0) < getattr(self, "_ai_action_delay_ms", 200):
            return
        if self.state != STATE_PLAYING:
            return
        player = self.current_player
        ai = self.get_ai(player)
        if ai is None:
            return
        if self.pending_action is not None:
            if self.pending_action.get("type") == "choose_suit":
                hero = self.pending_action["hero"]
                suit = ai.choose_suit(self, player, hero)
                if suit in self.all_suits:
                    self.resolve_suit_choice(suit)
                    self._last_ai_action = now
            return

        # Attacker turn
        if player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE"):
            legal_realm = self.legal_attack_cards(player)
            usable = self.usable_heroes(player)
            if self.play_phase == "ATTACK":
                action, payload = ai.choose_attack_action(self, player, legal_realm, usable)
            else:
                action, payload = ai.choose_reinforce_action(self, player, legal_realm, usable)

            if action == "hero" and payload is not None:
                hero_card = payload if isinstance(payload, dict) else next((h for h in self.get_player_hero_hand(player) if h["id"] == payload), None)
                if hero_card is None:
                    self._last_ai_action = now
                    return
                if hero_card["id"] == "aragorn":
                    target = ai.choose_aragorn_target(self, player)
                    if target in self.table_attacks:
                        idx = self.table_attacks.index(target)
                        self.resolve_aragorn(idx)
                elif hero_card["id"] == "saruman":
                    target = self.get_saruman_target_card()
                    if target is not None:
                        choice = ai.choose_saruman_exchange_card(self, player)
                        if choice in self.get_player_realm_hand(player):
                            self.resolve_saruman_exchange(choice)
                elif hero_card["id"] in ("gollum", "wormtongue"):
                    suit = ai.choose_suit(self, player, hero_card)
                    if suit in self.all_suits:
                        self.set_pending_action("choose_suit", hero_card, "AI choosing suit", mode=("gollum_trump" if hero_card["id"] == "gollum" else "wormtongue_block"))
                        self.resolve_suit_choice(suit)
                else:
                    self.attempt_hero_play(hero_card)
            elif action == "realm" and payload is not None:
                self.attempt_play_card(payload)
            else:
                # pass/end attack
                if self.play_phase == "REINFORCE":
                    self.end_round(False, False)
                else:
                    self.end_round(False, False)

            self._last_ai_action = now
            return

        # Defender turn
        legal_realm = self.legal_defense_cards(player)
        usable = [h for h in self.usable_heroes(player) if h["id"] in {"gandalf", "galadriel", "boromir"}]
        action, payload = ai.choose_defense_action(self, player, legal_realm, usable)
        if action == "hero" and payload is not None:
            hero_card = payload if isinstance(payload, dict) else next((h for h in self.get_player_hero_hand(player) if h["id"] == payload), None)
            if hero_card is not None:
                self.attempt_hero_play(hero_card)
        elif action == "realm" and payload is not None:
            self.attempt_play_card(payload)
        else:
            self.concede_defense()

        self._last_ai_action = now

    def is_card_playable_in_hand(self, card_data):
        if self.pending_action is not None:
            return self.pending_action["type"] == "saruman_exchange" and self.is_realm_card(card_data)
        if self.is_hero_card(card_data):
            return self.can_use_hero(card_data)
        if self.play_phase == "DEFEND":
            attack_card = self.get_current_attack_card()
            return self.can_defend_with_card(card_data, attack_card if attack_card else None)
        if self.play_phase in ("ATTACK", "REINFORCE"):
            return self.can_attack_with_card(card_data)
        return False

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

    def resolve_gandalf(self):
        attack_card = self.get_current_attack_card()
        if attack_card is None:
            return

        played_ranks = self.get_reinforce_ranks()
        removed_attack = self.table_attacks.pop()
        self.discard_card(removed_attack)
        self.round_effects["gandalf_ranks"] = played_ranks

        if self.player_has_no_cards(self.defender) and len(self.table_attacks) == len(self.table_defenses):
            self.end_round(defender_took_wound=False, pickup_defenses=False)
            return

        self.sync_turn_after_table_change()
        self.status_message = "Gandalf cancels the latest non-trump attack. The attacker must continue with a played rank or end the attack."

    def resolve_boromir(self):
        if self.get_current_attack_card() is None:
            return

        boromir_guard = {"id": "boromir_guard", "name": "Boromir", "faction": "Fellowship", "power": "Auto-defense"}
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

    def resolve_aragorn(self, attack_index):
        owner = self.pending_action["owner"]
        hero_card = self.pending_action["hero"]
        if not (0 <= attack_index < len(self.table_attacks)):
            return

        returned_attack = self.table_attacks.pop(attack_index)
        self.get_player_realm_hand(owner).append(returned_attack)

        if attack_index < len(self.table_defenses):
            removed_defense = self.table_defenses.pop(attack_index)
            self.discard_card(removed_defense)

        self.consume_hero_card(owner, hero_card)
        self.pending_action = None

        if self.player_has_no_cards(self.defender) and len(self.table_attacks) == len(self.table_defenses):
            self.status_message = "Aragorn recovers an attack and the defense holds."
            self.end_round(defender_took_wound=False, pickup_defenses=False)
            return

        self.sync_turn_after_table_change()
        self.status_message = "Aragorn returns an attack card to your hand."
        self.update_hand_visuals()

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

    def handle_hand_card_click(self, card_data):
        if self.pending_action is not None and self.pending_action["type"] == "saruman_exchange":
            if self.is_realm_card(card_data):
                self.resolve_saruman_exchange(card_data)
            return

        if self.is_hero_card(card_data):
            self.attempt_hero_play(card_data)
            return

        self.attempt_play_card(card_data)

    def attempt_play_card(self, card_data):
        current_hand = self.get_player_realm_hand(self.current_player)
        if card_data not in current_hand:
            return

        current_hand.remove(card_data)

        if self.play_phase in ["ATTACK", "REINFORCE"]:
            self.table_attacks.append(card_data)
            if self.round_effects["gandalf_ranks"]:
                self.round_effects["gandalf_ranks"] = []
            if self.round_effects["legolas_bonus"] > 0:
                self.round_effects["legolas_bonus"] -= 1

            self.play_phase = "DEFEND"
            self.current_player = self.defender
            self.status_message = f"{self.defender} must defend {card_data['name']}."
            self.update_hand_visuals()
            self.check_game_over()

        elif self.play_phase == "DEFEND":
            self.table_defenses.append(card_data)

            if self.player_has_no_cards(self.defender):
                self.end_round(defender_took_wound=False, pickup_defenses=False)
            else:
                self.play_phase = "REINFORCE"
                self.current_player = self.attacker
                self.status_message = f"{self.attacker} may reinforce or end the attack."
                self.update_hand_visuals()
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
                if self.is_realm_card(defense_card):
                    defender_hand.append(defense_card)

        for attack_card in self.table_attacks:
            self.discard_card(attack_card)

        for defense_card in self.table_defenses:
            if pickup_defenses and self.is_realm_card(defense_card):
                continue
            self.discard_card(defense_card)

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
            if self.player_has_no_cards("P1"):
                self.winner = "P1"
                self.state = STATE_GAMEOVER
            elif self.player_has_no_cards("P2"):
                self.winner = "P2"
                self.state = STATE_GAMEOVER

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == self.MUSIC_END_EVENT:
                self._advance_music()
                continue

            if event.type == pygame.VIDEORESIZE:
                resized_w = max(1024, event.w)
                resized_h = max(600, event.h)
                self.screen = pygame.display.set_mode((resized_w, resized_h), pygame.RESIZABLE)
                self.ui.on_resize(resized_w, resized_h)

            intent = self.ui.handle_event(event)
            if intent is not None:
                self.handle_intent(intent)

    def handle_intent(self, intent):
        action = intent.action
        payload = intent.payload

        if action == "start_game" and self.state == STATE_SPLASH:
            # payload may specify play mode and AI choices
            mode = payload.get("mode")
            # allow explicit AI selection for either player
            p1_choice = payload.get("p1_ai")
            p2_choice = payload.get("p2_ai")

            if mode == "2p":
                self.p1_ai = None
                self.p2_ai = None
            else:
                if p1_choice is not None:
                    self.p1_ai = make_ai(p1_choice)
                if p2_choice is not None:
                    self.p2_ai = make_ai(p2_choice)

            self.setup_game()
            self.state = STATE_DRAFTING
            return

        if action == "restart_game" and self.state == STATE_GAMEOVER:
            self.reset_game_state()
            return

        if action == "pick_draft_card" and self.state == STATE_DRAFTING:
            card_index = payload.get("card_index")
            card_type = payload.get("card_type")
            if isinstance(card_index, int) and card_type in ("realm", "hero"):
                self.attempt_draft(card_index, card_type)
            return

        if action == "select_aragorn_target" and self.state == STATE_PLAYING and self.pending_action is not None:
            if self.pending_action.get("type") == "aragorn_return":
                attack_index = payload.get("attack_index")
                if isinstance(attack_index, int):
                    self.resolve_aragorn(attack_index)
            return

        if action == "choose_suit" and self.state == STATE_PLAYING and self.pending_action is not None:
            if self.pending_action.get("type") == "choose_suit":
                suit = payload.get("suit")
                if suit in self.all_suits:
                    self.resolve_suit_choice(suit)
            return

        if action == "select_hand_card" and self.state == STATE_PLAYING:
            if self.pending_action is not None and self.pending_action.get("type") in ("aragorn_return", "choose_suit"):
                return
            card_index = payload.get("card_index")
            if isinstance(card_index, int) and 0 <= card_index < len(self.active_hand_visuals):
                self.handle_hand_card_click(self.active_hand_visuals[card_index])
            return

        if action == "concede_defense" and self.state == STATE_PLAYING:
            if self.play_phase == "DEFEND" and self.pending_action is None:
                self.concede_defense()
            return

        if action == "end_attack" and self.state == STATE_PLAYING:
            if self.play_phase == "REINFORCE" and self.pending_action is None:
                self.end_round(defender_took_wound=False, pickup_defenses=False)
            return

        if action == "confirm_selection":
            resolved = self.ui.resolve_space_intent()
            if resolved is not None:
                self.handle_intent(resolved)
            return

        if action == "request_redraw":
            return

        if action == "pause_confirm_yes":
            self.ui.input_handler.pause_confirm = False
            self.reset_game_state()
            return

        if action == "pause_confirm_no":
            self.ui.input_handler.pause_confirm = False
            return

    def run(self):
        while True:
            self.handle_events()
            # Allow AI players to draft and act each frame
            try:
                self.step_drafting()
            except Exception:
                pass

            try:
                self.step_ai()
            except Exception:
                pass
            self.ui.draw(self.screen, self)
            pygame.display.flip()
            self.clock.tick(FPS)

