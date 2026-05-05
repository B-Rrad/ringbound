"""Regression tests for Gollum suit selection ownership."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from ai_players import EasyAI
from ringbound_game import RingboundGame
from settings import STATE_PLAYING


def hero_by_id(game, hero_id):
    for hero in game.db["hero_cards"]:
        if hero["id"] == hero_id:
            return dict(hero)
    raise AssertionError(f"Missing hero: {hero_id}")


def realm_by_suit(game, suit):
    for card in game.db["realm_cards"]:
        if card["suit"] == suit:
            return dict(card)
    raise AssertionError(f"Missing realm suit: {suit}")


def build_attack_state(game, attacker):
    defender = game.get_opponent(attacker)
    game.state = STATE_PLAYING
    game.attacker = attacker
    game.defender = defender
    game.current_player = attacker
    game.play_phase = "ATTACK"
    game.trump_suit = game.all_suits[0]
    game.round_effects = game.new_round_effects()
    game.pending_action = None
    game.p1_hand = [realm_by_suit(game, game.all_suits[1])]
    game.p2_hand = [realm_by_suit(game, game.all_suits[2])]
    game.p1_heroes = []
    game.p2_heroes = []


def test_human_gollum_chooser_stays_with_owner():
    game = RingboundGame()
    game.ai_opponent = None
    build_attack_state(game, "P1")

    gollum = hero_by_id(game, "gollum")
    game.p1_heroes = [gollum]

    assert game.can_use_hero(gollum)
    game.attempt_hero_play(gollum)

    assert game.pending_action is not None
    assert game.pending_action["type"] == "choose_suit"
    assert game.pending_action["owner"] == "P1"
    assert game.pending_action["chooser"] == "P1"
    assert game.current_player == "P1"

    chosen_suit = game.all_suits[-1]
    game.resolve_suit_choice(chosen_suit)

    assert game.round_effects["temporary_trump_suit"] == chosen_suit
    assert gollum not in game.p1_heroes


def test_ai_gollum_choice_stays_with_ai_owner():
    game = RingboundGame()
    game.ai_opponent = EasyAI()
    build_attack_state(game, "P2")

    gollum = hero_by_id(game, "gollum")
    game.p2_heroes = [gollum]

    assert game.can_use_hero(gollum)
    game.attempt_hero_play(gollum)

    assert game.pending_action is not None
    assert game.pending_action["chooser"] == "P2"
    assert game.current_player == "P2"
    assert game.is_ai_turn()

    action = game.ai_opponent.choose_action(game, "P2")
    assert action["type"] == "suit"
    assert action["suit"] in game.all_suits


if __name__ == "__main__":
    test_human_gollum_chooser_stays_with_owner()
    test_ai_gollum_choice_stays_with_ai_owner()
    print("Gollum chooser tests passed!")
