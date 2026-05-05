import os
from typing import Tuple, Optional

from balance_analysis import RandomAI, GreedyAI, StrategicAI


def make_ai(ai_name: Optional[str]):
    if not ai_name:
        return None
    name = ai_name.strip()
    if name == "Random":
        return RandomAI("Random")
    if name == "Greedy":
        return GreedyAI("Greedy")
    if name == "Strategic":
        return StrategicAI("Strategic")
    return None


def configure_ai_from_env() -> Tuple[Optional[object], Optional[object]]:
    p1 = make_ai(os.environ.get("RINGBOUND_P1_AI", ""))
    p2 = make_ai(os.environ.get("RINGBOUND_P2_AI", ""))
    return p1, p2
