"""Plattform-Anbindungen über die offiziellen APIs."""

from __future__ import annotations

from content_crew.config import Config
from content_crew.platforms.base import Platform, PlatformError
from content_crew.platforms.instagram import Instagram
from content_crew.platforms.tiktok import TikTok
from content_crew.platforms.youtube import YouTube

ALL = {"youtube": YouTube, "instagram": Instagram, "tiktok": TikTok}


def load_platforms(cfg: Config) -> dict[str, Platform]:
    return {name: ALL[name](cfg) for name in cfg["platforms"] if name in ALL}


__all__ = ["Platform", "PlatformError", "load_platforms", "ALL"]
