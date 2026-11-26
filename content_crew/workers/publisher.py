"""Uploader: lädt fertige Videos auf alle eingerichteten Plattformen hoch."""

from __future__ import annotations

import logging
from pathlib import Path

from content_crew.config import Config
from content_crew.platforms.base import Platform, PlatformError

log = logging.getLogger(__name__)


class Publisher:
    def __init__(self, cfg: Config, platforms: dict[str, Platform]):
        self.cfg = cfg
        self.platforms = platforms

    def public_url(self, video: Path) -> str:
        base = self.cfg["notify"].get("public_base_url", "").rstrip("/")
        return f"{base}/media/{video.name}" if base else ""

    def publish(self, video: Path, script: dict, only: list[str] | None = None) -> tuple[dict[str, str], list[PlatformError]]:
        ids: dict[str, str] = {}
        errors: list[PlatformError] = []
        description = script.get("caption", "")
        tags = script.get("hashtags", [])
        from content_crew.animation.catalog import TYPES, pick_hashtags

        if script.get("type") in TYPES:  # immer die aktuellen Hashtag-Regeln anwenden (3-5 gezielte Tags)
            tags = pick_hashtags(tags, script["type"], script.get("music"), (script.get("params") or {}).get("lang"))
        for name, platform in self.platforms.items():
            if only and name not in only:
                continue
            if self.cfg.dry_run:
                ids[name] = f"dryrun-{video.stem}"
                log.info("[Testmodus] %s würde hochgeladen auf %s", video.name, name)
                continue
            missing = platform.missing()
            if missing:
                errors.append(PlatformError(f"{name} nicht eingerichtet: {', '.join(missing)}"))
                continue
            try:
                ids[name] = platform.upload(video, script["title"], description, tags, self.public_url(video))
                log.info("Hochgeladen auf %s: %s", name, ids[name])
            except PlatformError as exc:
                errors.append(exc)
                log.error("Upload auf %s fehlgeschlagen: %s", name, exc)
            except Exception as exc:  # noqa: BLE001
                errors.append(PlatformError(f"{name}: {exc}"))
                log.exception("Upload auf %s fehlgeschlagen", name)
        return ids, errors
