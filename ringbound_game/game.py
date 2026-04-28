from .ai_mixin import AIMixin
from .base import RingboundGameBase
from .events import EventMixin
from .gameplay import GameplayMixin
from .rendering import RenderingMixin


class RingboundGame(AIMixin, GameplayMixin, EventMixin, RenderingMixin, RingboundGameBase):
    pass

