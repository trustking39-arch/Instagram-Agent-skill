"""Analyst: holt die Zahlen der eigenen Videos und erkennt, was viral geht."""

from __future__ import annotations

import logging
import statistics

from content_crew.config import Config
from content_crew.db import DB
from content_crew.platforms.base import Platform, PlatformError

log = logging.getLogger(__name__)


def is_viral(views: int | None, others: list[int], multiplier: float, min_views: int) -> bool:
    if not views:
        return False
    baseline = statistics.median(others) if others else 0
    return views >= max(min_views, multiplier * baseline)


class Analyst:
    def __init__(self, cfg: Config, db: DB, platforms: dict[str, Platform]):
        self.cfg = cfg
        self.db = db
        self.platforms = platforms

    def refresh(self) -> tuple[list[dict], list[PlatformError]]:
        """Statistiken aktualisieren. Gibt neue Viral-Treffer und Fehler zurück."""
        errors: list[PlatformError] = []
        for video in self.db.videos(status="published", limit=30):
            for name, post_id in video["platform_ids"].items():
                platform = self.platforms.get(name)
                if not platform or post_id.startswith("dryrun-"):
                    continue
                try:
                    stats = platform.stats(post_id)
                    if stats:
                        self.db.add_metrics(video["id"], name, stats)
                except PlatformError as exc:
                    errors.append(exc)
                except Exception as exc:  # noqa: BLE001
                    errors.append(PlatformError(f"{name}: {exc}"))
                    log.exception("Statistik von %s fehlgeschlagen", name)
        return self.viral_hits(), errors

    def viral_hits(self) -> list[dict]:
        vcfg = self.cfg["virality"]
        hits = []
        for platform in {m["platform"] for m in self.db.latest_metrics()}:
            rows = self.db.latest_metrics(platform)
            for row in rows:
                others = [r["views"] for r in rows if r["video_id"] != row["video_id"] and r["views"]]
                if is_viral(row["views"], others, vcfg["viral_multiplier"], vcfg["viral_min_views"]):
                    if self.db.alert_once(row["video_id"], platform, "viral"):
                        video = self.db.video(row["video_id"])
                        hits.append({**row, "title": video["script"]["title"] if video else "?"})
        return hits

    def performance_table(self) -> list[dict]:
        table = []
        for row in self.db.latest_metrics():
            video = self.db.video(row["video_id"])
            if not video:
                continue
            table.append({
                "id": row["video_id"], "platform": row["platform"], "title": video["script"]["title"],
                "hook": video["script"].get("hook", ""), "views": row["views"], "likes": row["likes"],
                "comments": row["comments"], "shares": row["shares"],
            })
        return sorted(table, key=lambda r: r["views"] or 0, reverse=True)
