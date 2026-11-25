"""Video-Produzent: macht aus dem Skript ein Hochformat-Video (Sprachausgabe + Untertitel)."""

from __future__ import annotations

import logging
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from content_crew.config import Config

log = logging.getLogger(__name__)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/mnt/c/Windows/Fonts/arialbd.ttf",
]
COLORS = ["0x1d3557", "0x2a9d8f", "0x6a4c93", "0xe76f51", "0x264653", "0x8338ec", "0x3a86ff"]
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}


def _ff_path(path: Path | str) -> str:
    """Pfad für ffmpeg-Filter maskieren (Windows-Laufwerksbuchstaben usw.)."""
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Befehl fehlgeschlagen: {' '.join(cmd[:3])} …\n{proc.stderr[-1500:]}")


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


class VideoProducer:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.v = cfg["video"]
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg ist nicht installiert")

    @property
    def out_dir(self) -> Path:
        d = self.cfg.data_dir / "videos"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _font(self) -> str | None:
        if self.v.get("font"):
            return self.v["font"]
        return next((f for f in FONT_CANDIDATES if Path(f).exists()), None)

    def _backgrounds(self) -> list[Path]:
        d = self.v.get("background_dir")
        if not d or not Path(d).expanduser().is_dir():
            return []
        return [p for p in Path(d).expanduser().iterdir() if p.suffix.lower() in IMAGE_EXT | VIDEO_EXT]

    # --- Sprachausgabe -------------------------------------------------
    def tts(self, text: str, out: Path) -> Path | None:
        engine = self.v.get("tts", "edge")
        try:
            if engine == "edge":
                target = out.with_suffix(".mp3")
                _run([sys.executable, "-m", "edge_tts", "--voice", self.v.get("voice", "de-DE-KatjaNeural"),
                      "--text", text, "--write-media", str(target)])
                return target
            if engine == "espeak":
                exe = shutil.which("espeak-ng") or shutil.which("espeak")
                if exe:
                    target = out.with_suffix(".wav")
                    _run([exe, "-v", self.cfg.get("language", "de"), "-w", str(target), text])
                    return target
        except Exception as exc:  # noqa: BLE001
            reason = (str(exc).strip().splitlines() or ["?"])[-1][:200]
            log.warning("Sprachausgabe fehlgeschlagen (%s), Szene ohne Ton: %s", engine, reason)
        return None

    # --- Szenen --------------------------------------------------------
    def _scene(self, idx: int, text: str, work: Path, backgrounds: list[Path]) -> Path:
        w, h, fps = int(self.v["width"]), int(self.v["height"]), int(self.v["fps"])
        audio = self.tts(text, work / f"a{idx}")
        dur = _duration(audio) + 0.35 if audio else max(2.0, len(text.split()) / 2.6)
        (work / f"t{idx}.txt").write_text(textwrap.fill(text, width=20), encoding="utf-8")

        cmd = ["ffmpeg", "-y", "-loglevel", "error"]
        bg = random.choice(backgrounds) if backgrounds else None
        if bg and bg.suffix.lower() in VIDEO_EXT:
            cmd += ["-stream_loop", "-1", "-i", str(bg)]
        elif bg:
            cmd += ["-loop", "1", "-i", str(bg)]
        else:
            cmd += ["-f", "lavfi", "-i", f"color=c={COLORS[idx % len(COLORS)]}:s={w}x{h}:r={fps}"]
        if audio:
            cmd += ["-i", str(audio)]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

        font = self._font()
        draw = (
            f"drawtext=textfile=t{idx}.txt:expansion=none:fontcolor=white:fontsize={int(w * 0.064)}"
            f":line_spacing=14:box=1:boxcolor=black@0.55:boxborderw=28"
            f":x=(w-text_w)/2:y=(h-text_h)/2"
        )
        if font:
            draw += f":fontfile='{_ff_path(font)}'"
        vf = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},{draw}[v]"
        out = work / f"s{idx}.mp4"
        cmd += [
            "-filter_complex", vf, "-map", "[v]", "-map", "1:a", "-t", f"{dur:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-ar", "44100", "-ac", "2", out.name,
        ]
        _run(cmd, cwd=work)
        return out

    def produce(self, script: dict, video_id: int) -> Path:
        backgrounds = self._backgrounds()
        target = self.out_dir / f"video_{video_id}.mp4"
        with tempfile.TemporaryDirectory(prefix="crew_") as tmp:
            work = Path(tmp)
            parts = [self._scene(i, s["text"], work, backgrounds) for i, s in enumerate(script["scenes"])]
            (work / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
            _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
                  "-c", "copy", "-movflags", "+faststart", str(target.resolve())], cwd=work)
        log.info("Video erstellt: %s (%.1f s)", target, _duration(target))
        return target
