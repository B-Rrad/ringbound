from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    bg: tuple[int, int, int] = (13, 11, 14)
    surface: tuple[int, int, int] = (26, 21, 32)
    accent_gold: tuple[int, int, int] = (201, 168, 76)
    accent_ember: tuple[int, int, int] = (184, 74, 46)
    text_primary: tuple[int, int, int] = (232, 223, 200)
    text_muted: tuple[int, int, int] = (122, 111, 94)
    border_subtle: tuple[int, int, int] = (83, 72, 56)
    gondor: tuple[int, int, int] = (74, 127, 165)
    shire: tuple[int, int, int] = (90, 138, 74)
    mordor: tuple[int, int, int] = (138, 48, 48)
    rohan: tuple[int, int, int] = (160, 120, 48)
    fellowship: tuple[int, int, int] = (201, 168, 76)
    shadow: tuple[int, int, int] = (184, 74, 46)
    disabled_overlay: tuple[int, int, int, int] = (0, 0, 0, 140)
    disabled_pattern: tuple[int, int, int, int] = (150, 145, 135, 75)
    hover_glow_alpha: int = 72
    selected_outline: tuple[int, int, int] = (224, 195, 95)
    press_darkening: float = 0.15

    @property
    def suit_colors(self) -> dict[str, tuple[int, int, int]]:
        return {
            "Gondor": self.gondor,
            "Shire": self.shire,
            "Mordor": self.mordor,
            "Rohan": self.rohan,
        }
