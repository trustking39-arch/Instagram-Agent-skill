"""Konfiguration aus config.yaml und .env laden."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "niche": "Motivation und Selbstverbesserung",
    "language": "de",
    "platforms": ["youtube", "instagram", "tiktok"],
    "llm": {"base_url": "http://127.0.0.1:8000/v1", "model": "qwen3.5:9b", "timeout_seconds": 600},
    "boss": {
        "videos_per_cycle": 1,
        "cycle_minutes": 240,
        "min_script_score": 7,
        "max_revisions": 2,
        "animation_revisions": 1,  # bei Animationen reicht eine Überarbeitung: die Bildqualität liefert die Engine
        "auto_publish": True,
    },
    "virality": {"viral_multiplier": 3.0, "viral_min_views": 10000},
    "notify": {
        "call_on": ["viral", "blocked"],
        "sms_on": ["question", "published", "error", "approval", "report"],
        "public_base_url": "",
        "tunnel": "auto",
    },
    "video": {
        "style": "animation",  # animation = animierte Clips mit Musik; slides = alte Text-Videos
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "tts": "edge",
        "voice": "de-DE-KatjaNeural",
        "font": "",
        "background_dir": "",
    },
    # ki_captions: true = Titel/Caption schreibt das Sprachmodell (erst ab einem großen Modell sinnvoll)
    "animation": {"fps": 60, "bloom": 0.6, "crf": 18, "preset": "medium", "ki_captions": False},
    "data_dir": "./data",
    "dry_run": False,
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


class Config(dict):
    """Dict mit Punkt-Zugriff auf Umgebungsvariablen über .env()."""

    @property
    def data_dir(self) -> Path:
        path = Path(self["data_dir"]).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def dry_run(self) -> bool:
        return bool(self.get("dry_run")) or os.environ.get("CONTENT_CREW_DRY_RUN") == "1"

    @staticmethod
    def env(name: str, default: str = "") -> str:
        return os.environ.get(name, default).strip()


def load_config(path: str | Path = "config.yaml") -> Config:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(".env"))
    except ImportError:  # pragma: no cover
        pass
    data: dict = {}
    p = Path(path)
    if p.exists():
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return Config(_merge(DEFAULTS, data))
