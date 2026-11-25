"""Farbpaletten für die Animationen (ohne Skia, damit Jarvis sie auch ohne Grafik-Bibliothek kennt)."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Palette:
    name: str
    bg_top: RGB
    bg_bottom: RGB
    colors: tuple[RGB, ...] = ()
    rainbow: bool = False

    def at(self, x: float) -> RGB:
        """Farbe an Position x (0..1) des Farbverlaufs."""
        if self.rainbow:
            r, g, b = colorsys.hsv_to_rgb(x % 1.0, 0.78, 1.0)
            return int(r * 255), int(g * 255), int(b * 255)
        x = min(1.0, max(0.0, x)) * (len(self.colors) - 1)
        i = min(int(x), len(self.colors) - 2) if len(self.colors) > 1 else 0
        if len(self.colors) == 1:
            return self.colors[0]
        f = x - i
        a, b = self.colors[i], self.colors[i + 1]
        return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))  # type: ignore[return-value]

    def cycle(self, i: int) -> RGB:
        if self.rainbow:
            return self.at((i * 0.618034) % 1.0)
        return self.colors[i % len(self.colors)]


PALETTES: dict[str, Palette] = {
    "neon": Palette("neon", (10, 6, 28), (1, 1, 6),
                    ((0, 245, 255), (110, 90, 255), (255, 0, 229), (255, 80, 110), (255, 236, 0))),
    "sunset": Palette("sunset", (34, 8, 34), (5, 2, 10),
                      ((255, 72, 96), (252, 145, 58), (249, 212, 35), (255, 120, 170), (180, 90, 255))),
    "ocean": Palette("ocean", (2, 22, 42), (0, 3, 12),
                     ((0, 119, 182), (0, 180, 216), (72, 202, 228), (144, 224, 239), (210, 244, 250))),
    "candy": Palette("candy", (26, 16, 40), (7, 5, 14),
                     ((255, 150, 150), (255, 205, 150), (250, 250, 160), (180, 255, 180), (150, 240, 255),
                      (160, 190, 255), (200, 170, 255), (255, 180, 245))),
    "rainbow": Palette("rainbow", (12, 10, 22), (0, 0, 2), rainbow=True),
    "fire": Palette("fire", (30, 5, 0), (4, 0, 0),
                    ((255, 30, 0), (255, 90, 0), (255, 154, 0), (255, 206, 0), (255, 244, 150))),
    "matrix": Palette("matrix", (0, 16, 8), (0, 2, 1),
                      ((0, 143, 17), (0, 200, 90), (0, 255, 65), (170, 255, 170))),
    "gold": Palette("gold", (16, 11, 4), (2, 1, 0),
                    ((212, 160, 40), (255, 190, 30), (255, 215, 0), (255, 241, 184))),
    "ice": Palette("ice", (4, 12, 28), (0, 2, 8),
                   ((80, 140, 255), (120, 200, 255), (190, 240, 255), (230, 230, 255))),
}
