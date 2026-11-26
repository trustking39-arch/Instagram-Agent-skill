"""Erzählstimme für Story-Videos (offline, Kokoro-Sprachmodell, Englisch).

Die Modelldateien (~350 MB) werden beim ersten Gebrauch von GitHub geladen und unter data/tts gespeichert.
Kokoro kann Englisch (US/UK), aber kein Deutsch.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import requests

log = logging.getLogger(__name__)

SR = 44100
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
_MODEL = None


def _ensure_files(folder: Path) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = folder / name
        if not target.exists() or target.stat().st_size == 0:
            log.info("Lade Sprachmodell %s …", name)
            with requests.get(BASE + name, stream=True, timeout=600) as r:
                r.raise_for_status()
                tmp = target.with_suffix(".part")
                with tmp.open("wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                tmp.rename(target)
    return folder / FILES[0], folder / FILES[1]


def _model(folder: Path):
    global _MODEL
    if _MODEL is None:
        from kokoro_onnx import Kokoro

        onnx, voices = _ensure_files(folder)
        _MODEL = Kokoro(str(onnx), str(voices))
    return _MODEL


def narration_track(lines: list[tuple[float, str]], duration: float, folder: Path, voice: str = "am_michael",
                    lang: str = "en-us", speed: float = 1.05) -> np.ndarray:
    """Sätze zu ihren Zeitpunkten sprechen; überlappt ein Satz den nächsten, rückt der nächste nach hinten."""
    model = _model(folder)
    n = int(duration * SR)
    track = np.zeros(n + SR * 8, np.float32)
    free_at = 0.0
    for start, text in lines:
        samples, sr = model.create(text, voice=voice, speed=speed, lang=lang)
        samples = np.asarray(samples, np.float32)
        if sr != SR:  # auf 44,1 kHz bringen
            src = np.arange(len(samples)) / sr
            dst = np.arange(int(len(samples) * SR / sr)) / SR
            samples = np.interp(dst, src, samples).astype(np.float32)
        begin = max(start, free_at)
        i = int(begin * SR)
        if i >= len(track):
            continue
        seg = samples[: len(track) - i]
        track[i:i + len(seg)] += seg
        free_at = begin + len(samples) / SR + 0.15
        if free_at > duration:
            log.warning("Erzählung endet nach dem Video (%.1f s > %.1f s): %s", free_at, duration, text[:40])
    peak = np.abs(track).max()
    return (track[:n] / peak * 0.9 if peak > 0 else track[:n]).astype(np.float32)
