"""Quick headless test for two-player mode."""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame; pygame.init(); pygame.display.set_mode((1, 1))

from ringbound_game import RingboundGame
from settings import STATE_DRAFTING, STATE_PLAYING, STATE_GAMEOVER
from ui_elements import CardUI
from ai_players import _card_data

for trial in range(5):
    game = RingboundGame()
    game.ai_opponent = None
    game.setup_game()
    game.state = STATE_DRAFTING

    steps = 0
    while game.state == STATE_DRAFTING and steps < 50:
        if game.realm_draft_visuals and game.can_draft_card_type(game.current_drafter, "realm"):
            game.attempt_draft(game.realm_draft_visuals[0], "realm")
        elif game.hero_draft_visuals and game.can_draft_card_type(game.current_drafter, "hero"):
            game.attempt_draft(game.hero_draft_visuals[0], "hero")
        else:
            break
        steps += 1

    assert game.state == STATE_PLAYING
    assert game.ai_opponent is None

    steps = 0
    while game.state == STATE_PLAYING and steps < 500:
        cp = game.current_player
        if game.pending_action:
            pt = game.pending_action["type"]
            if pt == "choose_suit":
                game.resolve_suit_choice(game.all_suits[0])
            elif pt == "aragorn_return" and game.table_attacks:
                game.resolve_aragorn(game.table_attacks[0])
            elif pt == "saruman_exchange":
                r = game.get_player_realm_hand(game.pending_action["owner"])
                if r:
                    game.resolve_saruman_exchange(r[0])
            elif pt == "hero_attack_card":
                r = game.get_player_realm_hand(game.pending_action["owner"])
                if r:
                    game.resolve_hero_attack_card(r[0])
            steps += 1
            continue

        if game.play_phase in ("ATTACK", "REINFORCE"):
            played = False
            for c in game.get_player_realm_hand(cp):
                if game.can_attack_with_card(c):
                    game.attempt_play_card(CardUI(c, 0, 0))
                    played = True
                    break
            if not played:
                game.end_round(defender_took_wound=False, pickup_defenses=False)
        elif game.play_phase == "DEFEND":
            atk = game.get_current_attack_card()
            if atk:
                ad = _card_data(atk)
                played = False
                for c in game.get_player_realm_hand(cp):
                    if game.can_defend_with_card(c, ad):
                        game.attempt_play_card(CardUI(c, 0, 0))
                        played = True
                        break
                if not played:
                    game.concede_defense()
            else:
                game.concede_defense()
        steps += 1

    assert game.state == STATE_GAMEOVER, f"Game stuck after {steps} steps"
    w = game.wounds
    print(f"  [2P #{trial+1}] Done in {steps} steps. Winner: {game.winner}  Wounds: P1={w['P1']} P2={w['P2']}")

print("\nTwo-player mode OK!")
