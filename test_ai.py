"""Headless smoke test for the AI opponent integration.

Runs a full game (draft + combat) for each difficulty level without
opening a pygame window.  Verifies that:
  - The AI drafts all its cards without errors
  - The AI plays combat turns until a winner is determined
  - No exceptions are raised during the entire flow
"""

import os
import sys

# Use a dummy video driver so pygame.init() works without a display
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
# Create a tiny hidden surface so rendering calls don't crash
screen = pygame.display.set_mode((1, 1))

from main import RingboundGame
from ai_players import EasyAI, MediumAI, HardAI, _card_data
from settings import STATE_DRAFTING, STATE_PLAYING, STATE_GAMEOVER, AI_DELAY_MS


def run_full_game(ai_class, label):
    """Simulate a complete game with the given AI class controlling P2."""
    game = RingboundGame()
    game.ai_opponent = ai_class()
    game.setup_game()
    game.state = STATE_DRAFTING

    # --- Draft phase ---
    max_draft_steps = 50
    steps = 0
    while game.state == STATE_DRAFTING and steps < max_draft_steps:
        if game.current_drafter == "P2":
            visual, card_type = game.ai_opponent.choose_draft(
                game, game.realm_draft_visuals, game.hero_draft_visuals,
            )
            game.attempt_draft(visual, card_type)
        else:
            # Simulate human P1 drafting: pick the first available card
            if game.realm_draft_visuals:
                game.attempt_draft(game.realm_draft_visuals[0], "realm")
            elif game.hero_draft_visuals:
                game.attempt_draft(game.hero_draft_visuals[0], "hero")
        steps += 1

    assert game.state == STATE_PLAYING, f"[{label}] Draft did not complete (state={game.state}, steps={steps})"
    print(f"  [{label}] Draft complete in {steps} steps.  P1 hand: {len(game.p1_hand)}R+{len(game.p1_heroes)}H  P2 hand: {len(game.p2_hand)}R+{len(game.p2_heroes)}H")

    # --- Combat phase ---
    max_combat_steps = 2000
    steps = 0
    while game.state == STATE_PLAYING and steps < max_combat_steps:
        if game.current_player == "P2":
            action = game.ai_opponent.choose_action(game, "P2")
            execute_ai_action(game, action)
        else:
            simulate_human_turn(game)
        steps += 1

    assert game.state == STATE_GAMEOVER, f"[{label}] Game did not finish (state={game.state}, steps={steps})"
    print(f"  [{label}] Game over in {steps} combat steps.  Winner: {game.winner}  Wounds: P1={game.wounds['P1']} P2={game.wounds['P2']}")


def execute_ai_action(game, action):
    """Mirror of RingboundGame._execute_ai_action for headless testing."""
    from ui_elements import CardUI

    atype = action["type"]
    if atype == "realm":
        card_data = action["card_data"]
        hand = game.get_player_realm_hand("P2")
        if card_data in hand:
            visual = CardUI(card_data, 0, 0)
            game.attempt_play_card(visual)
    elif atype == "hero":
        game.attempt_hero_play(action["card_data"])
    elif atype == "concede":
        game.concede_defense()
    elif atype == "end_attack":
        game.end_round(defender_took_wound=False, pickup_defenses=False)
    elif atype == "suit":
        game.resolve_suit_choice(action["suit"])
    elif atype == "aragorn":
        target_data = action["card_data"]
        for atk in game.table_attacks:
            if _card_data(atk) is target_data or _card_data(atk) == target_data:
                game.resolve_aragorn(atk)
                break
    elif atype == "saruman":
        game.resolve_saruman_exchange(action["card_data"])
    elif atype == "pass":
        game.end_round(defender_took_wound=False, pickup_defenses=False)


def simulate_human_turn(game):
    """Very simple P1 logic: play the first legal card, concede if stuck."""
    from ui_elements import CardUI

    # Handle pending actions for P1
    if game.pending_action is not None:
        ptype = game.pending_action["type"]
        if ptype == "choose_suit":
            game.resolve_suit_choice(game.all_suits[0])
            return
        if ptype == "aragorn_return" and game.table_attacks:
            game.resolve_aragorn(game.table_attacks[0])
            return
        if ptype == "saruman_exchange":
            realm = game.get_player_realm_hand("P1")
            if realm:
                game.resolve_saruman_exchange(realm[0])
            return
        return

    if game.play_phase in ("ATTACK", "REINFORCE"):
        realm = game.get_player_realm_hand("P1")
        for card in realm:
            if game.can_attack_with_card(card):
                visual = CardUI(card, 0, 0)
                game.attempt_play_card(visual)
                return
        # Try using a hero if no realm cards can attack
        heroes = game.get_player_hero_hand("P1")
        for hero in heroes:
            if game.can_use_hero(hero):
                game.attempt_hero_play(hero)
                return
        # No legal attack and no usable heroes — end round
        game.end_round(defender_took_wound=False, pickup_defenses=False)
        return

    if game.play_phase == "DEFEND":
        attack_visual = game.get_current_attack_card()
        if attack_visual is None:
            game.concede_defense()
            return
        attack_data = _card_data(attack_visual)
        realm = game.get_player_realm_hand("P1")
        for card in realm:
            if game.can_defend_with_card(card, attack_data):
                visual = CardUI(card, 0, 0)
                game.attempt_play_card(visual)
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
