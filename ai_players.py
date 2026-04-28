"""AI opponents for Ringbound.

Three difficulty levels adapted to the refactored mixin architecture.
Each AI class implements:
  - choose_draft(game, realm_visuals, hero_visuals) -> (visual, card_type)
  - choose_action(game, player) -> action dict
"""

from __future__ import annotations

import random
from collections import Counter


# ---------------------------------------------------------------------------
# Hero sets used to filter which heroes the AI considers per phase
# ---------------------------------------------------------------------------
ATTACK_HEROES = {
    "aragorn", "legolas", "galadriel", "frodo", "nazgul",
    "saruman", "sauron", "balrog", "gollum", "wormtongue",
}
DEFENSE_HEROES = {"gandalf", "galadriel", "boromir"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card_data(card):
    """Return the raw dict whether *card* is a CardUI or a plain dict."""
    return getattr(card, "data", card)


def _realm_cards_in_hand(game, player):
    return list(game.get_player_realm_hand(player))


def _hero_cards_in_hand(game, player):
    return list(game.get_player_hero_hand(player))


def _usable_heroes(game, player, phase_set):
    """Return hero dicts the player can legally activate right now,
    filtered to *phase_set* (ATTACK_HEROES or DEFENSE_HEROES)."""
    saved = game.current_player
    game.current_player = player
    heroes = []
    for hero in _hero_cards_in_hand(game, player):
        if hero["id"] not in phase_set:
            continue
        if game.can_use_hero(hero):
            heroes.append(hero)
    game.current_player = saved
    return heroes


def _legal_attack_cards(game, player):
    return [c for c in _realm_cards_in_hand(game, player)
            if game.can_attack_with_card(c)]


def _legal_defense_cards(game, player):
    attack_visual = game.get_current_attack_card()
    if attack_visual is None:
        return []
    attack_data = _card_data(attack_visual)
    return [c for c in _realm_cards_in_hand(game, player)
            if game.can_defend_with_card(c, attack_data)]


def _known_opponent_cards(game, player):
    """If Sauron revealed the opponent's hand, return those cards."""
    if game.revealed_hand is not None and game.revealed_hand["viewer"] == player:
        opponent = game.get_opponent(player)
        return list(game.get_player_realm_hand(opponent))
    return None


# ===================================================================
# Base class – also serves as the Easy AI (random play)
# ===================================================================

class EasyAI:
    """Picks mostly random legal moves."""

    name = "Easy"

    # -- Draft ----------------------------------------------------------

    hero_draft_scores = {
        "galadriel": 8.8, "boromir": 8.5, "gandalf": 8.2,
        "balrog": 8.0, "sauron": 7.8, "saruman": 7.6,
        "nazgul": 7.2, "wormtongue": 7.0, "frodo": 6.8,
        "aragorn": 6.7, "legolas": 6.5, "gollum": 6.0,
    }

    def draft_score(self, card_data):
        if "rank" in card_data:
            return card_data["rank"] - 5
        return self.hero_draft_scores.get(card_data["id"], 5.0)

    def choose_draft(self, game, realm_visuals, hero_visuals):
        """Return a (visual_card, card_type) tuple respecting draft limits."""
        options = []
        if game.can_draft_card_type(game.current_drafter, "realm"):
            options += [(v, "realm") for v in realm_visuals]
        if game.can_draft_card_type(game.current_drafter, "hero"):
            options += [(v, "hero") for v in hero_visuals]
        if not options:
            return None
        return random.choice(options)

    # -- Combat ---------------------------------------------------------

    def choose_action(self, game, player):
        """Return an action dict the game loop can execute.

        Possible shapes:
            {"type": "realm",       "card_data": <dict>}
            {"type": "hero",        "card_data": <dict>}
            {"type": "concede"}
            {"type": "end_attack"}
            {"type": "pass"}
            {"type": "suit",        "suit": <str>}
            {"type": "aragorn",     "card_data": <dict>}
            {"type": "saruman",     "card_data": <dict>}
            {"type": "hero_attack", "card_data": <dict>}   # for legolas/balrog
            {"type": "galadriel"}
        """
        # Handle pending actions first
        if game.pending_action is not None:
            return self._resolve_pending(game, player)

        # Check if Galadriel heal is worthwhile
        gal = self._maybe_galadriel(game, player)
        if gal is not None:
            return gal

        if player == game.attacker and game.play_phase in ("ATTACK", "REINFORCE"):
            return self._choose_attack(game, player)
        if player == game.defender and game.play_phase == "DEFEND":
            return self._choose_defense(game, player)
        return {"type": "end_attack"}

    # -- Galadriel (standalone heal) ------------------------------------

    def _maybe_galadriel(self, game, player):
        return None

    # -- Pending helpers ------------------------------------------------

    def _resolve_pending(self, game, player):
        action_type = game.pending_action["type"]
        chooser = game.pending_action.get("chooser", game.pending_action.get("owner"))

        if action_type == "choose_suit":
            return {"type": "suit", "suit": self._choose_suit(game, chooser, game.pending_action["hero"])}
        if action_type == "aragorn_return":
            target = self._choose_aragorn_target(game, player)
            return {"type": "aragorn", "card_data": _card_data(target)}
        if action_type == "saruman_exchange":
            card = self._choose_saruman_card(game, game.pending_action["owner"])
            return {"type": "saruman", "card_data": card}
        if action_type == "hero_attack_card":
            card = self._choose_hero_attack_card(game, game.pending_action["owner"])
            if card is not None:
                return {"type": "hero_attack", "card_data": card}
        return {"type": "pass"}

    # -- Attack / Reinforce ---------------------------------------------

    def _choose_attack(self, game, player):
        legal_realm = _legal_attack_cards(game, player)
        usable = _usable_heroes(game, player, ATTACK_HEROES)

        if usable and random.random() < 0.3:
            return {"type": "hero", "card_data": random.choice(usable)}
        if legal_realm:
            return {"type": "realm", "card_data": random.choice(legal_realm)}
        return {"type": "end_attack"}

    # -- Defense --------------------------------------------------------

    def _choose_defense(self, game, player):
        legal_realm = _legal_defense_cards(game, player)
        usable = _usable_heroes(game, player, DEFENSE_HEROES)

        if usable and random.random() < 0.35:
            return {"type": "hero", "card_data": random.choice(usable)}
        if legal_realm:
            return {"type": "realm", "card_data": random.choice(legal_realm)}
        return {"type": "concede"}

    # -- Suit / Aragorn / Saruman / hero_attack helpers -----------------

    def _choose_suit(self, game, player, hero_card):
        return random.choice(game.all_suits)

    def _choose_aragorn_target(self, game, player):
        return random.choice(game.table_attacks)

    def _choose_saruman_card(self, game, player):
        realm = _realm_cards_in_hand(game, player)
        if not realm:
            return None
        return random.choice(realm)

    def _choose_hero_attack_card(self, game, player):
        """Pick a realm card for Legolas or Balrog's hero_attack_card pending."""
        realm = _realm_cards_in_hand(game, player)
        if not realm:
            return None
        return random.choice(realm)


# ===================================================================
# Medium AI – Greedy heuristics
# ===================================================================

class MediumAI(EasyAI):
    name = "Medium"

    def choose_draft(self, game, realm_visuals, hero_visuals):
        options = []
        if game.can_draft_card_type(game.current_drafter, "realm"):
            options += [(v, "realm") for v in realm_visuals]
        if game.can_draft_card_type(game.current_drafter, "hero"):
            options += [(v, "hero") for v in hero_visuals]
        if not options:
            return None
        return max(options, key=lambda pair: self.draft_score(pair[0].data))

    # -- Galadriel heal -------------------------------------------------

    def _maybe_galadriel(self, game, player):
        if game.wounds[player] >= 4 and game.can_activate_galadriel(player):
            return {"type": "galadriel", "player": player}
        return None

    # -- Attack ---------------------------------------------------------

    def _choose_attack_hero(self, game, player, usable):
        hero_map = {h["id"]: h for h in usable}
        opponent = game.get_opponent(player)
        opp_known = _known_opponent_cards(game, player)
        opp_trumps = 0
        if opp_known:
            opp_trumps = sum(1 for c in opp_known if "suit" in c and game.is_trump_card(c))

        if "sauron" in hero_map and game.play_phase == "ATTACK" and not game.table_attacks:
            return hero_map["sauron"]
        if "saruman" in hero_map and game.play_phase == "ATTACK" and not game.table_attacks:
            target = game.get_saruman_target_card()
            if target is not None and (game.is_trump_card(target) or target["rank"] >= 12):
                return hero_map["saruman"]
        if "wormtongue" in hero_map:
            return hero_map["wormtongue"]
        if "nazgul" in hero_map and opp_trumps <= 2:
            return hero_map["nazgul"]
        if "frodo" in hero_map and opp_trumps >= 2:
            return hero_map["frodo"]
        if "balrog" in hero_map and game.wounds[opponent] >= 3:
            return hero_map["balrog"]
        if "legolas" in hero_map and game.play_phase == "REINFORCE":
            return hero_map["legolas"]
        if "aragorn" in hero_map and any(
            i < len(game.table_defenses) for i in range(len(game.table_attacks))
        ):
            return hero_map["aragorn"]
        if "gollum" in hero_map:
            return hero_map["gollum"]
        return None

    def _choose_attack(self, game, player):
        legal_realm = _legal_attack_cards(game, player)
        usable = _usable_heroes(game, player, ATTACK_HEROES)

        hero = self._choose_attack_hero(game, player, usable)
        if hero is not None:
            return {"type": "hero", "card_data": hero}
        if legal_realm:
            best = min(legal_realm, key=lambda c: (game.is_trump_card(c), c["rank"]))
            if game.play_phase == "REINFORCE" and best["rank"] > 9 and not usable:
                return {"type": "end_attack"}
            return {"type": "realm", "card_data": best}
        return {"type": "end_attack"}

    # -- Defense --------------------------------------------------------

    def _choose_defense_hero(self, game, player, legal_realm, usable):
        hero_map = {h["id"]: h for h in usable}
        attack_visual = game.get_current_attack_card()
        if attack_visual is None:
            return None
        attack = _card_data(attack_visual)

        if "gandalf" in hero_map and (not legal_realm or attack["rank"] >= 12):
            return hero_map["gandalf"]
        if "boromir" in hero_map and (not legal_realm or game.is_trump_card(attack)):
            return hero_map["boromir"]
        return None

    def _choose_defense(self, game, player):
        legal_realm = _legal_defense_cards(game, player)
        usable = _usable_heroes(game, player, DEFENSE_HEROES)

        hero = self._choose_defense_hero(game, player, legal_realm, usable)
        if hero is not None:
            return {"type": "hero", "card_data": hero}
        if legal_realm:
            return {"type": "realm", "card_data": min(
                legal_realm, key=lambda c: (game.is_trump_card(c), c["rank"])
            )}
        return {"type": "concede"}

    # -- Suit -----------------------------------------------------------

    def _choose_suit(self, game, player, hero_card):
        opp_known = _known_opponent_cards(game, player)
        if hero_card["id"] == "wormtongue":
            if opp_known:
                counts = Counter(c["suit"] for c in opp_known if "suit" in c)
                if counts:
                    return counts.most_common(1)[0][0]
            attack_visual = game.get_current_attack_card()
            if attack_visual is not None:
                return _card_data(attack_visual)["suit"]
        # For gollum (defender chooses), pick suit we have most of
        own_counts = Counter(c["suit"] for c in _realm_cards_in_hand(game, player))
        if own_counts:
            return own_counts.most_common(1)[0][0]
        return game.all_suits[0]

    # -- Aragorn / Saruman / hero_attack --------------------------------

    def _choose_aragorn_target(self, game, player):
        def score(atk):
            d = _card_data(atk)
            idx = game.table_attacks.index(atk)
            defended = idx < len(game.table_defenses)
            return (game.is_trump_card(d), defended, d["rank"])
        return max(game.table_attacks, key=score)

    def _choose_saruman_card(self, game, player):
        realm = _realm_cards_in_hand(game, player)
        if not realm:
            return None
        return min(realm, key=lambda c: (game.is_trump_card(c), c["rank"]))

    def _choose_hero_attack_card(self, game, player):
        realm = _realm_cards_in_hand(game, player)
        if not realm:
            return None
        return min(realm, key=lambda c: (game.is_trump_card(c), c["rank"]))


# ===================================================================
# Hard AI – Strategic play
# ===================================================================

class HardAI(MediumAI):
    name = "Hard"

    def draft_score(self, card_data):
        base = super().draft_score(card_data)
        if "rank" in card_data:
            return base + (1.5 if card_data["rank"] >= 12 else 0)
        return base + 0.6

    # -- Galadriel heal -------------------------------------------------

    def _maybe_galadriel(self, game, player):
        if game.wounds[player] >= 3 and game.can_activate_galadriel(player):
            return {"type": "galadriel", "player": player}
        return None

    # -- Attack ---------------------------------------------------------

    def _best_attack_card(self, game, player, legal_realm):
        opp_cards = _known_opponent_cards(game, player)
        scored = []
        for card in legal_realm:
            difficulty = 0.0
            if opp_cards:
                defendable = any(
                    game.can_defend_with_card(oc, card)
                    for oc in opp_cards if "suit" in oc
                )
                difficulty = 2.0 if not defendable else 0.0
            trump_penalty = 3.0 if game.is_trump_card(card) else 0.0
            scored.append((difficulty - trump_penalty - card["rank"] / 20.0, card))
        return max(scored, key=lambda x: x[0])[1]

    def _choose_attack(self, game, player):
        legal_realm = _legal_attack_cards(game, player)
        usable = _usable_heroes(game, player, ATTACK_HEROES)

        hero = self._choose_attack_hero(game, player, usable)
        if hero is not None and hero["id"] in {
            "sauron", "saruman", "wormtongue", "nazgul",
            "frodo", "balrog", "legolas",
        }:
            return {"type": "hero", "card_data": hero}
        if legal_realm:
            best = self._best_attack_card(game, player, legal_realm)
            if game.play_phase == "REINFORCE":
                opponent = game.get_opponent(player)
                opp_count = game.get_player_total_cards(opponent)
                own_count = game.get_player_total_cards(player)
                if opp_count > own_count:
                    return {"type": "end_attack"}
            return {"type": "realm", "card_data": best}
        if hero is not None:
            return {"type": "hero", "card_data": hero}
        return {"type": "end_attack"}

    # -- Suit -----------------------------------------------------------

    def _choose_suit(self, game, player, hero_card):
        opp_known = _known_opponent_cards(game, player)
        if hero_card["id"] == "wormtongue":
            attack_visual = game.get_current_attack_card()
            if attack_visual is not None:
                return _card_data(attack_visual)["suit"]
            if opp_known:
                counts = Counter(c["suit"] for c in opp_known if "suit" in c)
                if counts:
                    return counts.most_common(1)[0][0]

        own_counts = Counter(c["suit"] for c in _realm_cards_in_hand(game, player))
        if opp_known and hero_card["id"] == "gollum":
            enemy_counts = Counter(c["suit"] for c in opp_known if "suit" in c)
            best_suit = game.all_suits[0]
            best_score = None
            for suit in game.all_suits:
                score = own_counts.get(suit, 0) - enemy_counts.get(suit, 0)
                if best_score is None or score > best_score:
                    best_score = score
                    best_suit = suit
            return best_suit
        if own_counts:
            return own_counts.most_common(1)[0][0]
        return game.all_suits[0]

    def _choose_hero_attack_card(self, game, player):
        realm = _realm_cards_in_hand(game, player)
        if not realm:
            return None
        return self._best_attack_card(game, player, realm)
