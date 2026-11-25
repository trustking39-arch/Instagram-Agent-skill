"""Animations-Studio: hochwertige animierte Kurzvideos (Physik-Simulationen, „Satisfying“-Clips) mit Ton.

Keine Sätze im Bild, keine Fotos: Jarvis' Animator rechnet jede Szene selbst (Skia), mischt die Musik
(numpy) und kodiert ein TikTok-taugliches MP4 (1080x1920, 60 fps, ffmpeg).
"""

from content_crew.animation.catalog import TYPES, normalize_concept, random_concept, type_for


def render(concept: dict, out, **settings) -> dict:
    """Konzept zu MP4 rendern (lädt die Grafik-Bibliothek erst bei Bedarf)."""
    from content_crew.animation.engine import render as _render

    return _render(concept, out, **settings)


__all__ = ["TYPES", "normalize_concept", "random_concept", "render", "type_for"]
