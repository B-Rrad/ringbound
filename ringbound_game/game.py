from .base import RingboundGameBase
from .events import EventMixin
from .gameplay import GameplayMixin
from .rendering import RenderingMixin


class RingboundGame(GameplayMixin, EventMixin, RenderingMixin, RingboundGameBase):
    pass

