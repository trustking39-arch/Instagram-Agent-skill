"""Alle Animationsarten, die Jarvis' Animator beherrscht."""

from content_crew.animation.scenes.colorwar import ColorWars
from content_crew.animation.scenes.grow import GrowingBall
from content_crew.animation.scenes.multiply import EscapeMultiply
from content_crew.animation.scenes.rhythm import Polyrhythm
from content_crew.animation.scenes.rings import RingEscape

SCENES = {cls.name: cls for cls in (RingEscape, EscapeMultiply, GrowingBall, ColorWars, Polyrhythm)}

__all__ = ["SCENES"]
