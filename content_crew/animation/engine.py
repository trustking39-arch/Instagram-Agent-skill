"""Render-Engine: Skia zeichnet jedes Bild gestochen scharf, ffmpeg legt Glanz (Bloom) darüber und kodiert MP4."""

from __future__ import annotations

import logging
import math
import random
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import skia

from content_crew.animation.audio import Music, render_audio
from content_crew.animation.palettes import PALETTES, RGB, Palette

log = logging.getLogger(__name__)


# --- Farben -------------------------------------------------------------
def color(rgb: RGB, alpha: float = 1.0) -> int:
    return skia.Color(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(max(0.0, min(1.0, alpha)) * 255))


def mix(a: RGB, b: RGB, f: float) -> RGB:
    f = max(0.0, min(1.0, f))
    return (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f), int(a[2] + (b[2] - a[2]) * f))


WHITE: RGB = (255, 255, 255)


# --- Schrift ------------------------------------------------------------
_FONT_FILES = [
    "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/seguibl.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]
_TYPEFACE: skia.Typeface | None = None


def typeface() -> skia.Typeface:
    global _TYPEFACE
    if _TYPEFACE is None:
        for f in _FONT_FILES:
            if Path(f).exists():
                tf = skia.Typeface.MakeFromFile(f)
                if tf is not None:
                    _TYPEFACE = tf
                    break
        if _TYPEFACE is None:
            _TYPEFACE = skia.Typeface("Arial", skia.FontStyle.Bold()) or skia.Typeface()
    return _TYPEFACE


def text_center(c: skia.Canvas, text: str, x: float, y: float, size: float, rgb: RGB = WHITE,
                alpha: float = 1.0, shadow: bool = False) -> None:
    """Text (nur Zahlen/Zeichen, keine Sätze) mittig zeichnen; y ist die optische Mitte."""
    font = skia.Font(typeface(), size)
    font.setEdging(skia.Font.Edging.kAntiAlias)
    width = font.measureText(text)
    if shadow:  # weicher dunkler Schatten: lesbar auch vor hellem Himmel
        c.drawString(text, x - width / 2, y + size * 0.36 + size * 0.04, font, skia.Paint(
            AntiAlias=True, Color=color((0, 0, 0), 0.45 * alpha),
            MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, size * 0.06)))
    c.drawString(text, x - width / 2, y + size * 0.36, font, skia.Paint(AntiAlias=True, Color=color(rgb, alpha)))


# --- Partikel -----------------------------------------------------------
class Particles:
    """Funken, Splitter, Explosionen. Eigene Zufallsquelle, damit die Physik unberührt bleibt."""

    def __init__(self, rng: random.Random, gravity: float = 0.0):
        self.rng = np.random.default_rng(rng.randrange(1 << 30))
        self.gravity = gravity
        self.groups: list[dict] = []

    def burst(self, xs, ys, rgb: RGB, speed: float, size: float, life: float, vx0=0.0, vy0=0.0,
              center: tuple[float, float] | None = None, radial: float = 0.0) -> None:
        """Partikel erzeugen; mit center fliegen sie zusätzlich mit `radial` px/s nach außen."""
        xs = np.atleast_1d(np.asarray(xs, float))
        ys = np.atleast_1d(np.asarray(ys, float))
        n = len(xs)
        ang = self.rng.uniform(0, 2 * np.pi, n)
        sp = speed * self.rng.uniform(0.25, 1.0, n)
        vx, vy = np.cos(ang) * sp + vx0, np.sin(ang) * sp + vy0
        if center is not None and radial:
            dx, dy = xs - center[0], ys - center[1]
            d = np.maximum(np.hypot(dx, dy), 1e-6)
            k = radial * self.rng.uniform(0.6, 1.2, n)
            vx, vy = vx + dx / d * k, vy + dy / d * k
        self.groups.append({
            "x": xs.copy(), "y": ys.copy(), "vx": vx, "vy": vy,
            "rgb": rgb, "size": size, "age": 0.0, "life": life,
        })

    def update(self, dt: float) -> None:
        alive = []
        for g in self.groups:
            g["age"] += dt
            if g["age"] >= g["life"]:
                continue
            g["vy"] += self.gravity * dt
            g["vx"] *= 0.985
            g["vy"] *= 0.985
            g["x"] += g["vx"] * dt
            g["y"] += g["vy"] * dt
            alive.append(g)
        self.groups = alive

    def draw(self, c: skia.Canvas) -> None:
        paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap)
        for g in self.groups:
            f = 1.0 - g["age"] / g["life"]
            paint.setColor(color(mix(WHITE, g["rgb"], min(1.0, g["age"] * 6)), f ** 0.7))
            paint.setStrokeWidth(max(1.0, g["size"] * (0.4 + 0.6 * f)))
            pts = [skia.Point(float(x), float(y)) for x, y in zip(g["x"], g["y"])]
            c.drawPoints(skia.Canvas.kPoints_PointMode, pts, paint)


# --- Szene-Grundgerüst ----------------------------------------------------
@dataclass
class Ctx:
    W: int
    H: int
    fps: int
    duration: float          # gewünschte Länge (Sekunden)
    seed: int
    palette: Palette
    music_choice: str

    def physics_rng(self) -> random.Random:
        return random.Random(self.seed)

    def fx_rng(self) -> random.Random:
        return random.Random(self.seed * 7919 + 1)

    def music(self) -> Music:
        return Music(self.music_choice, random.Random(self.seed + 17))


class Scene:
    """Basis für alle Animationen. Physik (step) ist strikt getrennt vom Zeichnen (draw)."""

    name = "scene"
    substeps = 8
    outro = 1.6           # so lange läuft das Video nach dem Höhepunkt weiter
    pad = True            # leiser Klangteppich unter den Noten

    def __init__(self, ctx: Ctx, params: dict, headless: bool = False):
        self.ctx = ctx
        self.W, self.H = ctx.W, ctx.H
        self.p = params
        self.headless = headless
        self.rng = ctx.physics_rng()
        self.fx = ctx.fx_rng()
        self.music = ctx.music()
        self.t = 0.0
        self.notes: list = []
        self.done_at: float | None = None
        self.particles = Particles(self.fx, gravity=ctx.W * 0.9)
        self.shake = 0.0
        self.flash = 0.0

    # Zeitpunkte
    @property
    def target(self) -> float:
        """Wann der Höhepunkt kommen soll."""
        return max(3.0, self.ctx.duration - self.outro)

    def hard_limit(self) -> float:
        return self.target * 1.6 + 2

    # Ablauf
    def update(self, dt: float) -> None:
        h = dt / self.substeps
        for _ in range(self.substeps):
            if self.done_at is None:
                self.step(h)
            else:
                self.after_step(h)
            self.t += h
        if self.done_at is None and self.t >= self.hard_limit():
            self.finish()
        if not self.headless:
            self.particles.update(dt)
            self.shake = max(0.0, self.shake - dt * 4)
            self.flash = max(0.0, self.flash - dt * 2.5)
            self.frame(dt)

    def step(self, h: float) -> None:  # Physik, wird von Unterklassen ersetzt
        pass

    def after_step(self, h: float) -> None:  # Bewegung nach dem Höhepunkt (Standard: Physik läuft weiter)
        self.step(h)

    def frame(self, dt: float) -> None:  # einmal pro Bild: Spuren, Effekte
        pass

    def finish(self) -> None:
        if self.done_at is None:
            self.done_at = self.t
            self.on_finish()

    def on_finish(self) -> None:
        pass

    def finished(self) -> bool:
        return self.done_at is not None and self.t >= self.done_at + self.outro

    # Ton
    def play(self, pitch: float, gain: float = 0.5, x: float | None = None, kind: str = "tone",
             accent: bool = False) -> None:
        if self.headless:
            return
        from content_crew.animation.audio import Note

        pan = 0.0 if x is None else (x / self.W) * 2 - 1
        self.notes.append(Note(self.t, pitch, gain, pan, kind, accent))

    # Zeichnen
    def draw(self, c: skia.Canvas) -> None:
        pass

    def draw_flash(self, c: skia.Canvas) -> None:
        if self.flash > 0:
            c.drawPaint(skia.Paint(Color=color(WHITE, self.flash * 0.35)))

    # Kalibrierung: Parameter so einstellen, dass der Höhepunkt genau zur Wunschlänge kommt
    @classmethod
    def calibrate(cls, ctx: Ctx, params: dict) -> dict:
        return params

    @classmethod
    def finish_time(cls, ctx: Ctx, params: dict, limit: float) -> float:
        sim = cls(ctx, params, headless=True)
        dt = 1.0 / ctx.fps
        while sim.done_at is None and sim.t < limit:
            sim.update(dt)
        return sim.done_at if sim.done_at is not None and sim.done_at < sim.hard_limit() - 1e-6 else math.inf

    @classmethod
    def tune(cls, ctx: Ctx, params: dict, key: str, candidates: list[float]) -> dict:
        """Wert für params[key] suchen, bei dem der Höhepunkt am nächsten an der Wunschzeit liegt."""
        probe = cls(ctx, params, headless=True)
        target, limit = probe.target, probe.hard_limit()

        def cost(value: float) -> tuple[float, float]:
            tf = cls.finish_time(ctx, {**params, key: value}, limit)
            if math.isinf(tf):
                return 1e9, tf
            return abs(tf - target) + (tf - target) * 0.5 * (tf > target), tf

        results = sorted(((cost(v), v) for v in candidates), key=lambda r: r[0][0])
        best_cost, best = results[0][0][0], results[0][1]
        if best_cost > target * 0.04 and len(results) > 1:  # zwischen den zwei besten fein suchen
            other = results[1][1]
            for f in (0.25, 0.5, 0.75):
                v = best + (other - best) * f
                c, _ = cost(v)
                if c < best_cost:
                    best_cost, best = c, v
        log.info("Kalibriert %s: %s=%.3f (Abweichung %.1fs)", cls.name, key, best, best_cost)
        return {**params, key: best}


# --- Hintergrund --------------------------------------------------------
def make_background(W: int, H: int, palette: Palette, rng: random.Random) -> skia.Image:
    surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    c = surf.getCanvas()
    c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeLinear(
        [skia.Point(0, 0), skia.Point(0, H)], [color(palette.bg_top), color(palette.bg_bottom)])))
    glow = palette.at(0.5)
    c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeRadial(
        skia.Point(W / 2, H * 0.5), W * 0.9, [color(glow, 0.10), color(glow, 0.0)])))
    dot = skia.Paint(AntiAlias=True)
    for _ in range(int(W * H / 9000)):  # feiner Sternenstaub für Tiefe
        dot.setColor(color(WHITE, rng.uniform(0.04, 0.16)))
        c.drawCircle(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.6, 1.8) * W / 1080, dot)
    c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeRadial(
        skia.Point(W / 2, H / 2), H * 0.72, [skia.Color(0, 0, 0, 0), skia.Color(0, 0, 0, 175)], [0.45, 1.0])))
    return surf.makeImageSnapshot()


# --- Ausgabe ------------------------------------------------------------
class Encoder:
    """Nimmt Rohbilder entgegen; ffmpeg fügt den Glanz hinzu und kodiert H.264."""

    def __init__(self, path: Path, W: int, H: int, fps: int, bloom: float, crf: int, preset: str, log_file: Path):
        if bloom > 0:
            sw, sh = max(2, W // 4 // 2 * 2), max(2, H // 4 // 2 * 2)
            graph = (f"[0:v]format=gbrp,split[a][b];[b]scale={sw}:{sh}:flags=area,gblur=sigma={max(1.0, W / 200):.1f},"
                     f"scale={W}:{H}:flags=bilinear[g];[a][g]blend=all_mode=screen:all_opacity={bloom:.2f},"
                     "format=yuv420p[v]")
        else:
            graph = "[0:v]format=yuv420p[v]"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-", "-filter_complex", graph, "-map", "[v]", "-c:v", "libx264",
               "-preset", preset, "-crf", str(crf), "-profile:v", "high", "-r", str(fps), str(path)]
        self.log = log_file.open("wb")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=self.log)

    def write(self, frame: np.ndarray) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(memoryview(frame))

    def close(self) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        code = self.proc.wait()
        self.log.close()
        if code != 0:
            raise RuntimeError(f"ffmpeg-Fehler beim Kodieren: {Path(self.log.name).read_text(errors='replace')[-800:]}")


def render(concept: dict, out: Path, *, width: int = 1080, height: int = 1920, fps: int = 60,
           bloom: float = 0.6, crf: int = 18, preset: str = "medium") -> dict:
    """Konzept rendern und als MP4 (mit Ton) speichern. Gibt technische Daten zurück."""
    from content_crew.animation.scenes import SCENES

    cls = SCENES[concept["type"]]
    ctx = Ctx(width, height, fps, float(concept["duration"]), int(concept["seed"]),
              PALETTES[concept["palette"]], concept["music"])
    params = cls.calibrate(ctx, dict(concept.get("params") or {}))
    scene = cls(ctx, params)
    bg = make_background(width, height, ctx.palette, ctx.fx_rng())
    frame = np.zeros((height, width, 4), np.uint8)
    surface = skia.Surface(frame, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    canvas = surface.getCanvas()
    dt = 1.0 / fps
    max_frames = int((scene.hard_limit() + scene.outro + 1) * fps)

    motion: list[float] = []
    brightness: list[float] = []
    prev = None
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="anim_") as tmp:
        silent = Path(tmp) / "video.mp4"
        enc = Encoder(silent, width, height, fps, bloom, crf, preset, Path(tmp) / "ffmpeg.log")
        frames = 0
        try:
            while frames < max_frames:
                scene.update(dt)
                canvas.drawImage(bg, 0, 0)
                canvas.save()
                if scene.shake > 0:
                    k = scene.shake * width * 0.012
                    canvas.translate(scene.fx.uniform(-k, k), scene.fx.uniform(-k, k))
                scene.draw(canvas)
                canvas.restore()
                scene.draw_flash(canvas)
                enc.write(frame)
                frames += 1
                if frames % max(1, fps // 2) == 0:  # Qualitätsdaten: Bewegung und Helligkeit
                    small = frame[::24, ::24, :3].astype(np.int16)
                    brightness.append(float(small.mean()))
                    if prev is not None:
                        motion.append(float(np.abs(small - prev).mean()))
                    prev = small
                if scene.finished():
                    break
        finally:
            enc.close()
        duration = frames / fps
        wav = Path(tmp) / "audio.wav"
        render_audio(scene.notes, duration, wav, instrument=concept.get("sound", "bell"),
                     pad_root=(scene.music.root - 12) if scene.pad else None, seed=ctx.seed)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg-Fehler beim Zusammenfügen: {proc.stderr[-600:]}")
    return {
        "duration": round(duration, 2), "frames": frames, "fps": fps, "notes": len(scene.notes),
        "params": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in params.items()},
        "climax_at": round(scene.done_at, 2) if scene.done_at is not None else None,
        "motion": round(float(np.mean(motion)) if motion else 0.0, 2),
        "brightness": round(float(np.mean(brightness)) if brightness else 0.0, 1),
    }
