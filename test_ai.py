"""Headless smoke test for the AI opponent integration.

Runs a full game (draft + combat) for each difficulty level without
opening a pygame window.
"""

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from ringbound_game import RingboundGame
from ai_players import EasyAI, MediumAI, HardAI, _card_data
from settings import STATE_DRAFTING, STATE_PLAYING, STATE_GAMEOVER
from ui_elements import CardUI


def run_full_game(ai_class, label):
    game = RingboundGame()
    game.ai_opponent = ai_class()
    game.setup_game()
    game.state = STATE_DRAFTING

    # --- Draft phase ---
    steps = 0
    while game.state == STATE_DRAFTING and steps < 50:
        if game.current_drafter == "P2":
            result = game.ai_opponent.choose_draft(
                game, game.realm_draft_visuals, game.hero_draft_visuals,
            )
            if result is not None:
                visual, card_type = result
                game.attempt_draft(visual, card_type)
            else:
                break
        else:
            if game.realm_draft_visuals and game.can_draft_card_type("P1", "realm"):
                game.attempt_draft(game.realm_draft_visuals[0], "realm")
            elif game.hero_draft_visuals and game.can_draft_card_type("P1", "hero"):
                game.attempt_draft(game.hero_draft_visuals[0], "hero")
            else:
                break
        steps += 1

    assert game.state == STATE_PLAYING, f"[{label}] Draft did not complete (state={game.state}, steps={steps})"
    print(f"  [{label}] Draft OK. P1: {len(game.p1_hand)}R+{len(game.p1_heroes)}H  P2: {len(game.p2_hand)}R+{len(game.p2_heroes)}H")

    # --- Combat phase ---
    steps = 0
    while game.state == STATE_PLAYING and steps < 2000:
        if game.current_player == "P2" or (
            game.pending_action is not None and game.pending_action.get("chooser") == "P2"
        ):
            action = game.ai_opponent.choose_action(game, "P2")
            execute_action(game, action)
        else:
            simulate_human(game)
        steps += 1

    assert game.state == STATE_GAMEOVER, f"[{label}] Game stuck (state={game.state}, steps={steps})"
    print(f"  [{label}] Done in {steps} steps. Winner: {game.winner}  Wounds: P1={game.wounds['P1']} P2={game.wounds['P2']}")


def execute_action(game, action):
    atype = action["type"]
    if atype == "realm":
        hand = game.get_player_realm_hand("P2")
        cd = action["card_data"]
        if cd in hand:
            game.attempt_play_card(CardUI(cd, 0, 0))
    elif atype == "hero":
        game.attempt_hero_play(action["card_data"])
    elif atype == "concede":
        game.concede_defense()
    elif atype == "end_attack":
        game.end_round(defender_took_wound=False, pickup_defenses=False)
    elif atype == "suit":
        game.resolve_suit_choice(action["suit"])
    elif atype == "aragorn":
        for atk in game.table_attacks:
            if _card_data(atk) is action["card_data"] or _card_data(atk) == action["card_data"]:
                game.resolve_aragorn(atk)
                break
    elif atype == "saruman":
        if action["card_data"] is not None:
            game.resolve_saruman_exchange(action["card_data"])
    elif atype == "hero_attack":
        if action["card_data"] is not None:
            game.resolve_hero_attack_card(action["card_data"])
    elif atype == "galadriel":
        game.activate_galadriel(action.get("player", "P2"))
    elif atype == "pass":
        game.end_round(defender_took_wound=False, pickup_defenses=False)


def simulate_human(game):
    if game.pending_action is not None:
        pt = game.pending_action["type"]
        if pt == "choose_suit":
            game.resolve_suit_choice(game.all_suits[0])
            return
        if pt == "aragorn_return" and game.table_attacks:
            game.resolve_aragorn(game.table_attacks[0])
            return
        if pt == "saruman_exchange":
            realm = game.get_player_realm_hand("P1")
            if realm:
                game.resolve_saruman_exchange(realm[0])
            return
        if pt == "hero_attack_card":
            realm = game.get_player_realm_hand("P1")
            if realm:
                game.resolve_hero_attack_card(realm[0])
            return
        return

    if game.play_phase in ("ATTACK", "REINFORCE"):
        for card in game.get_player_realm_hand("P1"):
            if game.can_attack_with_card(card):
                game.attempt_play_card(CardUI(card, 0, 0))
                return
        for hero in game.get_player_hero_hand("P1"):
            if game.can_use_hero(hero):
                game.attempt_hero_play(hero)
                return
        game.end_round(defender_took_wound=False, pickup_defenses=False)
        return

    if game.play_phase == "DEFEND":
        atk = game.get_current_attack_card()
        if atk is None:
            game.concede_defense()
            return
        ad = _card_data(atk)
        for card in game.get_player_realm_hand("P1"):
            if game.can_defend_with_card(card, ad):
                game.attempt_play_card(CardUI(card, 0, 0))
                return
        game.concede_defense()


if __name__ == "__main__":
    print("Running AI smoke tests...\n")
    for ai_cls, name in [(EasyAI, "Easy"), (MediumAI, "Medium"), (HardAI, "Hard")]:
        print(f"Testing {name} AI:")
        for trial in range(10):
            run_full_game(ai_cls, f"{name} #{trial+1}")
        print()
    print("All smoke tests passed!")
