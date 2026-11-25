"""Alle Animationsarten, die Jarvis' Animator beherrscht."""

from content_crew.animation.scenes.arena import SpinArena
from content_crew.animation.scenes.colorwar import ColorWars
from content_crew.animation.scenes.galton import Galton
from content_crew.animation.scenes.grow import GrowingBall
from content_crew.animation.scenes.multiply import EscapeMultiply
from content_crew.animation.scenes.rhythm import Polyrhythm
from content_crew.animation.scenes.rings import RingEscape
from content_crew.animation.scenes.strings import StringArt

SCENES = {cls.name: cls for cls in (RingEscape, EscapeMultiply, GrowingBall, ColorWars, Polyrhythm, Galton,
                                     SpinArena, StringArt)}

__all__ = ["SCENES"]
