import random

from settings import STATE_GAMEOVER, STATE_PLAYING, WINDOW_WIDTH
from ui_elements import CardUI


class GameplayMixin:
    def can_draft_card_type(self, player, card_type):
        if card_type == "realm":
            return len(self.get_player_realm_hand(player)) < self.MAX_REALM_CARDS
        if card_type == "hero":
            return len(self.get_player_hero_hand(player)) < self.MAX_HERO_CARDS
        return False

    def player_completed_draft(self, player):
        return (
            len(self.get_player_realm_hand(player)) >= self.MAX_REALM_CARDS
            and len(self.get_player_hero_hand(player)) >= self.MAX_HERO_CARDS
        )

    def drafting_has_available_pick(self, player):
        return (
            self.can_draft_card_type(player, "realm") and bool(self.realm_draft_visuals)
        ) or (
            self.can_draft_card_type(player, "hero") and bool(self.hero_draft_visuals)
        )

    def drafting_is_complete(self):
        both_players_full = self.player_completed_draft("P1") and self.player_completed_draft("P2")
        no_picks_left = not self.drafting_has_available_pick("P1") and not self.drafting_has_available_pick("P2")
        return both_players_full or no_picks_left

    def update_draft_visuals(self):
        can_take_realm = self.can_draft_card_type(self.current_drafter, "realm")
        can_take_hero = self.can_draft_card_type(self.current_drafter, "hero")
        for visual_card in self.realm_draft_visuals:
            visual_card.is_disabled = not can_take_realm
        for visual_card in self.hero_draft_visuals:
            visual_card.is_disabled = not can_take_hero

    def attempt_draft(self, visual_card, card_type):
        current_realm_hand = self.get_player_realm_hand(self.current_drafter)
        current_hero_hand = self.get_player_hero_hand(self.current_drafter)

        if not self.can_draft_card_type(self.current_drafter, card_type):
            return

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
        next_drafter = self.get_opponent(self.current_drafter)
        if not self.drafting_has_available_pick(next_drafter) and self.drafting_has_available_pick(self.current_drafter):
            next_drafter = self.current_drafter
        self.current_drafter = next_drafter
        self.status_message = f"{self.current_drafter} is drafting."
        self.update_draft_visuals()

    def check_draft_complete(self):
        if self.drafting_is_complete():
            self.attacker = self.first_attacker
            self.defender = self.get_opponent(self.attacker)
            self.current_player = self.attacker

            self.trump_visual = CardUI(self.trump_card, 30, 50)
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

    def current_player_has_attack_action(self):
        if self.current_player != self.attacker or self.play_phase not in ("ATTACK", "REINFORCE"):
            return False
        if any(self.can_attack_with_card(card) for card in self.get_player_realm_hand(self.current_player)):
            return True
        return any(
            hero_card["id"] != "galadriel" and self.can_use_hero(hero_card)
            for hero_card in self.get_player_hero_hand(self.current_player)
        )

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
        legal_attack_exists = any(self.can_attack_with_card(card) for card in self.get_player_realm_hand(self.current_player))

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
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and self.round_effects["balrog_active"] is None and legal_attack_exists
        if hero_id == "gollum":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and not self.round_effects["trump_disabled"] and self.round_effects["temporary_trump_suit"] is None
        if hero_id == "wormtongue":
            return self.current_player == self.attacker and self.play_phase in ("ATTACK", "REINFORCE") and self.round_effects["wormtongue_suit"] is None
        return False

    def find_player_hero(self, player, hero_id):
        for hero_card in self.get_player_hero_hand(player):
            if hero_card["id"] == hero_id:
                return hero_card
        return None

    def can_activate_galadriel(self, player):
        return self.state == STATE_PLAYING and self.wounds[player] > 0 and self.find_player_hero(player, "galadriel") is not None

    def activate_galadriel(self, player):
        hero_card = self.find_player_hero(player, "galadriel")
        if hero_card is None or self.wounds[player] <= 0 or self.state != STATE_PLAYING:
            return

        previous_wounds = self.wounds[player]
        self.wounds[player] = max(0, previous_wounds - 2)
        healed = previous_wounds - self.wounds[player]
        self.consume_hero_card(player, hero_card)
        self.status_message = f"Galadriel heals {healed} wound(s) for {player}."
        self.check_game_over()
        if self.state != STATE_GAMEOVER:
            self.update_hand_visuals()

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
                elif self.pending_action["type"] == "hero_attack_card":
                    visual_card.is_disabled = not self.can_select_hero_attack_card(card_data)
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

    def can_select_hero_attack_card(self, card_data):
        if self.pending_action is None or self.pending_action["type"] != "hero_attack_card":
            return False
        if not self.is_realm_card(card_data):
            return False
        if card_data not in self.get_player_realm_hand(self.pending_action["owner"]):
            return False

        mode = self.pending_action["mode"]
        if mode == "legolas_bonus":
            return True
        return self.can_attack_with_card(card_data)

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

    def set_pending_action(self, action_type, hero_card, prompt, chooser=None, current_player_override=None, **kwargs):
        self.pending_action = {
            "type": action_type,
            "hero": hero_card,
            "owner": self.current_player,
            "chooser": chooser if chooser is not None else self.current_player,
            "prompt": prompt,
            **kwargs,
        }
        if current_player_override is not None:
            self.current_player = current_player_override
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
                "Gollum: defender chooses the suit that becomes trump for this round.",
                mode="gollum_trump",
                chooser=self.defender,
                current_player_override=self.defender,
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
        if hero_id == "galadriel":
            self.activate_galadriel(self.current_player)
            return
        if hero_id == "legolas":
            self.set_pending_action(
                "hero_attack_card",
                hero_card,
                "Legolas: choose one realm card to attack with now, ignoring rank restrictions.",
                mode="legolas_bonus",
            )
            return
        if hero_id == "balrog":
            self.set_pending_action(
                "hero_attack_card",
                hero_card,
                "Balrog: choose one realm card to attack with now.",
                mode="balrog_attack",
            )
            return

        self.consume_hero_card(self.current_player, hero_card)

        if hero_id == "gandalf":
            self.resolve_gandalf()
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
        self.discard_card(removed_attack.data)
        self.round_effects["gandalf_ranks"] = played_ranks

        if self.player_has_no_cards(self.defender) and len(self.table_attacks) == len(self.table_defenses):
            self.end_round(defender_took_wound=False, pickup_defenses=False)
            return

        self.sync_turn_after_table_change()
        self.status_message = "Gandalf cancels the latest non-trump attack. The attacker must continue with a played rank or end the attack."

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

    def resolve_suit_choice(self, suit):
        hero_card = self.pending_action["hero"]
        owner = self.pending_action["owner"]
        chooser = self.pending_action["chooser"]
        mode = self.pending_action["mode"]
        self.consume_hero_card(owner, hero_card)

        if mode == "gollum_trump":
            self.round_effects["temporary_trump_suit"] = suit
            self.status_message = f"{chooser} sets the trump suit to {suit} for this round."
        else:
            self.round_effects["wormtongue_suit"] = suit
            self.status_message = f"Wormtongue forbids the defender from playing {suit} this round."

        self.pending_action = None
        self.current_player = owner
        self.update_hand_visuals()

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

    def resolve_hero_attack_card(self, chosen_card):
        hero_card = self.pending_action["hero"]
        owner = self.pending_action["owner"]
        mode = self.pending_action["mode"]
        if chosen_card not in self.get_player_realm_hand(owner):
            return
        if not self.can_select_hero_attack_card(chosen_card):
            return

        self.pending_action = None
        self.current_player = owner
        self.consume_hero_card(owner, hero_card)
        if mode == "legolas_bonus":
            self.round_effects["legolas_bonus"] = 1
        elif mode == "balrog_attack":
            self.round_effects["balrog_active"] = owner

        self.attempt_play_card(CardUI(chosen_card, 0, 0))
        if self.state != STATE_GAMEOVER:
            if mode == "legolas_bonus":
                self.status_message = f"Legolas joins the attack with {chosen_card['name']}."
            else:
                self.status_message = f"Balrog charges with {chosen_card['name']}."
            self.update_hand_visuals()

    def handle_hand_card_click(self, visual_card):
        if self.pending_action is not None and self.pending_action["type"] == "saruman_exchange":
            if self.is_realm_card(visual_card.data):
                self.resolve_saruman_exchange(visual_card.data)
            return
        if self.pending_action is not None and self.pending_action["type"] == "hero_attack_card":
            if self.is_realm_card(visual_card.data):
                self.resolve_hero_attack_card(visual_card.data)
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

        elif self.play_phase == "DEFEND":
            self.table_defenses.append(visual_card)

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

    def check_game_over(self):
        if self.wounds["P1"] >= 6:
            self.winner = "P2"
            self.win_reason = "P1 reached 6 wounds."
            self.state = STATE_GAMEOVER
            return
        if self.wounds["P2"] >= 6:
            self.winner = "P1"
            self.win_reason = "P2 reached 6 wounds."
            self.state = STATE_GAMEOVER
            return

        if len(self.realm_deck) == 0:
            p1_realm_empty = self.player_has_no_realm_cards("P1")
            p2_realm_empty = self.player_has_no_realm_cards("P2")
            if p1_realm_empty and not p2_realm_empty:
                self.winner = "P1"
                self.win_reason = "P1 emptied all realm cards after the deck ran out."
                self.state = STATE_GAMEOVER
            elif p2_realm_empty and not p1_realm_empty:
                self.winner = "P2"
                self.win_reason = "P2 emptied all realm cards after the deck ran out."
                self.state = STATE_GAMEOVER
            elif p1_realm_empty and p2_realm_empty:
                if self.wounds["P1"] < self.wounds["P2"]:
                    self.winner = "P1"
                    self.win_reason = "Both players ran out of realm cards; P1 had fewer wounds."
                    self.state = STATE_GAMEOVER
                elif self.wounds["P2"] < self.wounds["P1"]:
                    self.winner = "P2"
                    self.win_reason = "Both players ran out of realm cards; P2 had fewer wounds."
                    self.state = STATE_GAMEOVER
                else:
                    p1_total = self.get_player_total_cards("P1")
                    p2_total = self.get_player_total_cards("P2")
                    if p1_total < p2_total:
                        self.winner = "P1"
                        self.win_reason = "Realm cards were exhausted and tied on wounds; P1 had fewer total cards left."
                        self.state = STATE_GAMEOVER
                    elif p2_total < p1_total:
                        self.winner = "P2"
                        self.win_reason = "Realm cards were exhausted and tied on wounds; P2 had fewer total cards left."
                        self.state = STATE_GAMEOVER
                    else:
                        self.winner = random.choice(["P1", "P2"])
                        self.win_reason = "All endgame tiebreakers were equal, so the winner was chosen at random."
                        self.state = STATE_GAMEOVER
