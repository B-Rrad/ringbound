import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from ringbound_game import RingboundGame
from settings import STATE_PLAYING


def realm(name, suit, rank):
    return {"name": name, "suit": suit, "rank": rank}


def hero(hero_id, faction="Test"):
    return {"id": hero_id, "name": hero_id.title(), "faction": faction, "power": "test"}


class HeroRegressionTests(unittest.TestCase):
    def setUp(self):
        self.game = RingboundGame()
        self.game.music_enabled = False
        self._reset_state()

    def _reset_state(self):
        game = self.game
        game.state = STATE_PLAYING
        game.attacker = "P1"
        game.defender = "P2"
        game.current_player = "P1"
        game.play_phase = "ATTACK"
        game.p1_hand = []
        game.p2_hand = []
        game.p1_heroes = []
        game.p2_heroes = []
        game.table_attacks = []
        game.table_defenses = []
        game.discard_pile = []
        game.hero_discard = []
        game.pending_action = None
        game.revealed_hand = None
        game.wounds = {"P1": 0, "P2": 0}
        game.round_effects = game.new_round_effects()
        game.realm_deck = [realm("Deck 1", "Rohan", 2), realm("Deck 2", "Mordor", 3)]
        game.hero_deck = []
        game.trump_suit = "Gondor"
        game.trump_card = realm("Trump", "Gondor", 11)
        game.winner = None

    def test_aragorn_returns_attack_and_removes_paired_defense(self):
        attack = realm("Attack", "Shire", 7)
        defense = realm("Defense", "Shire", 9)
        aragorn = hero("aragorn", "Fellowship")
        self.game.play_phase = "REINFORCE"
        self.game.table_attacks = [attack]
        self.game.table_defenses = [defense]
        self.game.p1_hand = [realm("Spare", "Rohan", 4)]
        self.game.p1_heroes = [aragorn]

        self.game.attempt_hero_play(aragorn)
        self.assertEqual(self.game.pending_action["type"], "aragorn_return")

        self.game.resolve_aragorn(0)

        self.assertIn(attack, self.game.p1_hand)
        self.assertIn(defense, self.game.discard_pile)
        self.assertIn(aragorn, self.game.hero_discard)
        self.assertEqual(self.game.table_attacks, [])
        self.assertEqual(self.game.table_defenses, [])

    def test_legolas_can_attack_with_off_rank_card(self):
        attack = realm("Lead", "Gondor", 7)
        defense = realm("Block", "Gondor", 9)
        off_rank = realm("Off Rank", "Shire", 5)
        legolas = hero("legolas", "Fellowship")
        self.game.play_phase = "REINFORCE"
        self.game.table_attacks = [attack]
        self.game.table_defenses = [defense]
        self.game.p1_hand = [off_rank]
        self.game.p1_heroes = [legolas]

        self.game.attempt_hero_play(legolas)

        self.assertEqual(self.game.pending_action["type"], "hero_attack_card")
        self.assertTrue(self.game.can_select_hero_attack_card(off_rank))

        self.game.resolve_hero_attack_card(off_rank)

        self.assertIn(off_rank, self.game.table_attacks)
        self.assertNotIn(off_rank, self.game.p1_hand)
        self.assertIn(legolas, self.game.hero_discard)
        self.assertEqual(self.game.play_phase, "DEFEND")
        self.assertEqual(self.game.current_player, "P2")

    def test_gandalf_cancels_latest_non_trump_attack(self):
        attack = realm("Attack", "Shire", 8)
        gandalf = hero("gandalf", "Fellowship")
        self.game.current_player = "P2"
        self.game.play_phase = "DEFEND"
        self.game.table_attacks = [attack]
        self.game.p2_hand = [realm("Spare Defense", "Rohan", 4)]
        self.game.p2_heroes = [gandalf]

        self.game.attempt_hero_play(gandalf)

        self.assertEqual(self.game.table_attacks, [])
        self.assertIn(8, self.game.round_effects["gandalf_ranks"])
        self.assertEqual(self.game.play_phase, "REINFORCE")
        self.assertEqual(self.game.current_player, "P1")
        self.assertIn(gandalf, self.game.hero_discard)

    def test_galadriel_heals_two_wounds(self):
        galadriel = hero("galadriel", "Fellowship")
        self.game.p1_heroes = [galadriel]
        self.game.wounds["P1"] = 3

        self.game.attempt_hero_play(galadriel)

        self.assertEqual(self.game.wounds["P1"], 1)
        self.assertNotIn(galadriel, self.game.p1_heroes)
        self.assertIn(galadriel, self.game.hero_discard)

    def test_frodo_disables_trump_and_clears_temporary_override(self):
        frodo = hero("frodo", "Fellowship")
        attack = realm("Attack", "Shire", 7)
        trump_defense = realm("Trump Defense", "Gondor", 2)
        same_suit_defense = realm("Same Suit", "Shire", 9)
        self.game.p1_heroes = [frodo]
        self.game.round_effects["temporary_trump_suit"] = "Mordor"

        self.game.attempt_hero_play(frodo)

        self.assertIsNone(self.game.get_effective_trump_suit())
        self.assertFalse(self.game.can_defend_with_card(trump_defense, attack))
        self.assertTrue(self.game.can_defend_with_card(same_suit_defense, attack))

    def test_boromir_auto_defends_and_discards_attacker_card(self):
        attack = realm("Attack", "Shire", 7)
        attacker_card = realm("Attacker Card", "Rohan", 4)
        boromir = hero("boromir", "Fellowship")
        self.game.current_player = "P2"
        self.game.play_phase = "DEFEND"
        self.game.table_attacks = [attack]
        self.game.p2_hand = [realm("Spare Defender", "Mordor", 6)]
        self.game.p2_heroes = [boromir]
        self.game.p1_hand = [attacker_card]

        self.game.attempt_hero_play(boromir)

        self.assertEqual(len(self.game.table_defenses), 1)
        self.assertEqual(self.game.table_defenses[0]["id"], "boromir_guard")
        self.assertNotIn(attacker_card, self.game.p1_hand)
        self.assertIn(attacker_card, self.game.discard_pile)
        self.assertIn(boromir, self.game.hero_discard)
        self.assertEqual(self.game.play_phase, "REINFORCE")
        self.assertEqual(self.game.current_player, "P1")

    def test_nazgul_forces_trump_only_defense(self):
        nazgul = hero("nazgul", "Shadow")
        attack = realm("Attack", "Shire", 7)
        same_suit_high = realm("Same Suit High", "Shire", 9)
        trump_card = realm("Trump Card", "Gondor", 2)
        self.game.p1_heroes = [nazgul]

        self.game.attempt_hero_play(nazgul)

        self.assertTrue(self.game.round_effects["nazgul_active"])
        self.assertFalse(self.game.can_defend_with_card(same_suit_high, attack))
        self.assertTrue(self.game.can_defend_with_card(trump_card, attack))

    def test_saruman_swaps_with_defenders_best_target(self):
        weak_card = realm("Weak Card", "Shire", 3)
        target_trump = realm("Target Trump", "Gondor", 12)
        saruman = hero("saruman", "Shadow")
        self.game.p1_hand = [weak_card]
        self.game.p2_hand = [target_trump]
        self.game.p1_heroes = [saruman]

        self.game.attempt_hero_play(saruman)

        self.assertEqual(self.game.pending_action["type"], "saruman_exchange")
        self.assertEqual(self.game.pending_action["target_card"], target_trump)

        self.game.resolve_saruman_exchange(weak_card)

        self.assertIn(target_trump, self.game.p1_hand)
        self.assertIn(weak_card, self.game.p2_hand)
        self.assertIn(saruman, self.game.hero_discard)

    def test_sauron_reveals_opponents_hand(self):
        sauron = hero("sauron", "Shadow")
        self.game.p1_heroes = [sauron]

        self.game.attempt_hero_play(sauron)

        self.assertEqual(self.game.revealed_hand, {"viewer": "P1", "target": "P2"})
        self.assertIn(sauron, self.game.hero_discard)

    def test_balrog_requires_attack_card_and_deals_wound_after_full_defense(self):
        attack_card = realm("Balrog Attack", "Shire", 7)
        defense_card = realm("Defense", "Shire", 9)
        balrog = hero("balrog", "Shadow")
        self.game.p1_hand = [attack_card]
        self.game.p1_heroes = [balrog]

        self.game.attempt_hero_play(balrog)

        self.assertEqual(self.game.pending_action["type"], "hero_attack_card")
        self.assertTrue(self.game.can_select_hero_attack_card(attack_card))

        self.game.resolve_hero_attack_card(attack_card)
        self.assertEqual(self.game.round_effects["balrog_active"], "P1")
        self.assertEqual(self.game.play_phase, "DEFEND")
        self.assertEqual(self.game.current_player, "P2")

        self.game.table_defenses = [defense_card]
        self.game.end_round(False, False)

        self.assertEqual(self.game.wounds["P2"], 1)
        self.assertEqual(self.game.attacker, "P1")

    def test_gollum_lets_defender_redefine_trump_and_returns_control(self):
        gollum = hero("gollum", "Shadow")
        self.game.p1_heroes = [gollum]

        self.game.attempt_hero_play(gollum)

        self.assertEqual(self.game.pending_action["type"], "choose_suit")
        self.assertEqual(self.game.pending_action["chooser"], "P2")
        self.assertEqual(self.game.current_player, "P2")

        self.game.resolve_suit_choice("Mordor")

        self.assertEqual(self.game.get_effective_trump_suit(), "Mordor")
        self.assertEqual(self.game.current_player, "P1")
        self.assertIsNone(self.game.pending_action)
        self.assertIn(gollum, self.game.hero_discard)

    def test_wormtongue_blocks_named_suit(self):
        wormtongue = hero("wormtongue", "Shadow")
        attack = realm("Attack", "Shire", 7)
        blocked = realm("Blocked", "Shire", 9)
        trump = realm("Trump", "Gondor", 2)
        self.game.p1_heroes = [wormtongue]

        self.game.attempt_hero_play(wormtongue)
        self.game.resolve_suit_choice("Shire")

        self.assertEqual(self.game.round_effects["wormtongue_suit"], "Shire")
        self.assertFalse(self.game.can_defend_with_card(blocked, attack))
        self.assertTrue(self.game.can_defend_with_card(trump, attack))

    def test_balrog_cannot_be_used_without_legal_attack_card(self):
        balrog = hero("balrog", "Shadow")
        off_rank = realm("Off Rank", "Shire", 5)
        self.game.play_phase = "REINFORCE"
        self.game.table_attacks = [realm("Lead", "Gondor", 7)]
        self.game.table_defenses = [realm("Block", "Gondor", 9)]
        self.game.p1_hand = [off_rank]
        self.game.p1_heroes = [balrog]

        self.assertFalse(self.game.can_use_hero(balrog))

    def test_gandalf_cannot_cancel_trump_attack(self):
        trump_attack = realm("Trump Attack", "Gondor", 12)
        gandalf = hero("gandalf", "Fellowship")
        self.game.current_player = "P2"
        self.game.play_phase = "DEFEND"
        self.game.table_attacks = [trump_attack]
        self.game.p2_heroes = [gandalf]

        self.assertFalse(self.game.can_use_hero(gandalf))


if __name__ == "__main__":
    unittest.main()
