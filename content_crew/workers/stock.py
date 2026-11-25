"""Passende Hintergrundvideos aus der kostenlosen Pexels-Datenbank (lizenzfrei, kommerziell nutzbar)."""

from __future__ import annotations

import logging
import random
from pathlib import Path

import requests

log = logging.getLogger(__name__)

API = "https://api.pexels.com/videos/search"


def pick_file(videos: list[dict], min_height: int = 1280) -> tuple[int, str] | None:
    """Kleinste Hochformat-Datei mit ausreichender Auflösung aus den Suchtreffern wählen."""
    candidates = []
    for video in videos:
        for f in video.get("video_files", []):
            w, h = f.get("width") or 0, f.get("height") or 0
            if h >= min_height and h > w and f.get("link"):
                candidates.append((video["id"], h, f["link"]))
    if not candidates:
        return None
    best_per_video: dict[int, tuple[int, str]] = {}
    for vid, h, link in candidates:
        if vid not in best_per_video or h < best_per_video[vid][0]:
            best_per_video[vid] = (h, link)
    vid = random.choice(list(best_per_video)[:3])
    return vid, best_per_video[vid][1]


class StockFootage:
    def __init__(self, api_key: str, cache_dir: Path):
        self.api_key = api_key
        self.cache = cache_dir
        self.cache.mkdir(parents=True, exist_ok=True)

    def find(self, query: str) -> Path | None:
        if not self.api_key or not query:
            return None
        try:
            r = requests.get(API, headers={"Authorization": self.api_key}, timeout=30, params={
                "query": query, "orientation": "portrait", "size": "medium", "per_page": 8,
            })
            r.raise_for_status()
            chosen = pick_file(r.json().get("videos", []))
            if not chosen:
                return None
            vid, link = chosen
            target = self.cache / f"pexels_{vid}.mp4"
            if not target.exists():
                with requests.get(link, stream=True, timeout=120) as dl:
                    dl.raise_for_status()
                    tmp = target.with_suffix(".part")
                    with tmp.open("wb") as fh:
                        for chunk in dl.iter_content(1 << 20):
                            fh.write(chunk)
                    tmp.rename(target)
            return target
        except Exception as exc:  # noqa: BLE001
            log.warning("Kein Stockvideo für %r: %s", query, exc)
            return None
