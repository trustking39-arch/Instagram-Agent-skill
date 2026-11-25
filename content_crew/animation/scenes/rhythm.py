"""Polyrhythmus: Punkte in leicht unterschiedlichem Tempo, jeder mit eigenem Ton. Am Ende treffen sich alle."""

from __future__ import annotations

import math

import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center

TAU = 2 * math.pi


def _tri(u: float) -> float:
    """0 → 1 → 0 pro Zyklus (Hin- und Rückweg)."""
    f = u - math.floor(u)
    return 1 - abs(1 - 2 * f)


class Polyrhythm(Scene):
    name = "polyrhythm"
    substeps = 1
    outro = 2.6

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        self.layout = params.get("layout", "arcs")
        self.N = n = max(4, int(params.get("dots", 21)))
        self.T = self.target
        base = max(3, round(self.T * float(params.get("speed", 0.3))))
        self.cycles = [base + i for i in range(n)]
        per = 1 if self.layout == "orbits" else 2  # Treffer pro Umlauf
        self.per = per
        self.hits = [0] * n
        self.glow = [0.0] * n
        scale = self.music.scale
        span = min(n, len(scale) * 4)  # höchstens vier Oktaven
        self.pitches = [self.music.degree(int(i * span / n), -1) for i in range(n)]
        self.cx = W * 0.5
        if self.layout == "arcs":
            self.base_y = H * 0.6
            self.radii = [W * (0.46 - 0.39 * i / (n - 1)) for i in range(n)]
        elif self.layout == "orbits":
            self.cy = H * 0.52
            self.radii = [W * (0.46 - 0.40 * i / (n - 1)) for i in range(n)]
        else:
            self.rows = [H * (0.2 + 0.6 * i / (n - 1)) for i in range(n)]
            self.amp = W * 0.4
        self.colors = [self.ctx.palette.at(i / (n - 1)) for i in range(n)]

    def freq(self, i: int) -> float:
        return self.cycles[i] / self.T

    def pos(self, i: int, t: float) -> tuple[float, float]:
        u = self.freq(i) * t
        if self.layout == "arcs":
            th = math.pi * _tri(u)
            r = self.radii[i]
            return self.cx + r * math.cos(th), self.base_y - r * math.sin(th)
        if self.layout == "orbits":
            a = -math.pi / 2 + TAU * u
            r = self.radii[i]
            return self.cx + r * math.cos(a), self.cy + r * math.sin(a)
        return self.cx + self.amp * math.sin(TAU * u), self.rows[i]

    def step(self, h: float) -> None:
        t1 = self.t + h
        for i in range(self.N):
            k = math.floor(self.freq(i) * t1 * self.per + 1e-9)
            if k > self.hits[i]:
                self.hits[i] = k
                self.glow[i] = 1.0
                if not self.headless:
                    x, _ = self.pos(i, t1)
                    self.play(self.pitches[i], 0.3, x)
        if self.done_at is None and t1 >= self.T - 1e-6:
            self.finish()

    def on_finish(self) -> None:
        if self.headless:
            return
        self.flash = 0.7
        for i in range(self.N):
            x, y = self.pos(i, self.T)
            self.particles.burst([x] * 10, [y] * 10, self.colors[i], speed=self.W * 0.3, size=self.W * 0.008,
                                 life=1.4)
        self.play(0, 0.8, kind="boom", accent=True)

    def frame(self, dt: float) -> None:
        for i in range(self.N):
            self.glow[i] = max(0.0, self.glow[i] - dt * 2.8)

    # --- Zeichnen ---------------------------------------------------------
    def draw(self, c: skia.Canvas) -> None:
        if self.layout == "arcs":
            self._draw_arcs(c)
        elif self.layout == "orbits":
            self._draw_orbits(c)
        else:
            self._draw_wave(c)
        self.particles.draw(c)
        left = max(0.0, self.T - self.t)
        text_center(c, f"{left:0.1f}" if left > 0 else "0.0", self.W / 2, self.H * 0.13, self.W * 0.1,
                    alpha=0.95)

    def _dot(self, c: skia.Canvas, x: float, y: float, i: int, alpha: float = 1.0) -> None:
        r = self.W * 0.015 * (1 + 0.7 * self.glow[i])
        c.drawCircle(x, y, r * 1.5, skia.Paint(AntiAlias=True, Color=color(self.colors[i], 0.35 * alpha)))
        c.drawCircle(x, y, r, skia.Paint(AntiAlias=True, Color=color(mix(self.colors[i], WHITE, 0.55), alpha)))

    def _draw_arcs(self, c: skia.Canvas) -> None:
        cx, by = self.cx, self.base_y
        for mirror in (True, False):  # erst die Spiegelung, dann das Original
            c.save()
            alpha = 1.0
            if mirror:
                c.translate(0, 2 * by)
                c.scale(1, -1)
                alpha = 0.16
            arc = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap)
            for i in range(self.N):
                r = self.radii[i]
                g = self.glow[i]
                arc.setColor(color(mix(self.colors[i], WHITE, 0.5 * g), (0.28 + 0.7 * g) * alpha))
                arc.setStrokeWidth(self.W * (0.0028 + 0.003 * g))
                c.drawArc(skia.Rect(cx - r, by - r, cx + r, by + r), 180, 180, False, arc)
            trail = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap)
            for i in range(self.N):
                u = self.freq(i) * self.t
                th = math.pi * _tri(u)
                rising = (u - math.floor(u)) < 0.5
                span = min(70.0, math.degrees(TAU * self.freq(i) * 0.09))
                span = min(span, math.degrees(th) if rising else 180 - math.degrees(th))  # nicht unter die Linie
                r = self.radii[i]
                trail.setColor(color(self.colors[i], 0.45 * alpha))
                trail.setStrokeWidth(self.W * 0.012)
                start = -math.degrees(th) if rising else -math.degrees(th) - span
                c.drawArc(skia.Rect(cx - r, by - r, cx + r, by + r), start, span, False, trail)
                x, y = self.pos(i, self.t)
                self._dot(c, x, y, i, alpha)
            c.restore()
        line = skia.Paint(AntiAlias=True, StrokeWidth=3, Color=color(WHITE, 0.6))
        reach = self.radii[0] + self.W * 0.02
        c.drawLine(cx - reach, by, cx + reach, by, line)

    def _draw_orbits(self, c: skia.Canvas) -> None:
        cx, cy = self.cx, self.cy
        ring = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style)
        for i in range(self.N):
            ring.setColor(color(self.colors[i], 0.12 + 0.55 * self.glow[i]))
            ring.setStrokeWidth(self.W * (0.002 + 0.003 * self.glow[i]))
            c.drawCircle(cx, cy, self.radii[i], ring)
        c.drawLine(cx, cy, cx, cy - self.radii[0] - self.W * 0.03,
                   skia.Paint(AntiAlias=True, StrokeWidth=3, Color=color(WHITE, 0.35)))
        pts = [self.pos(i, self.t) for i in range(self.N)]
        path = skia.Path()
        path.moveTo(*pts[0])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        c.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=self.W * 0.003,
                                    StrokeJoin=skia.Paint.kRound_Join, Color=color(WHITE, 0.45)))
        for i, (x, y) in enumerate(pts):
            self._dot(c, x, y, i)

    def _draw_wave(self, c: skia.Canvas) -> None:
        cx = self.cx
        c.drawLine(cx, self.rows[0] - self.W * 0.05, cx, self.rows[-1] + self.W * 0.05,
                   skia.Paint(AntiAlias=True, StrokeWidth=3, Color=color(WHITE, 0.3)))
        guide = skia.Paint(AntiAlias=True, StrokeWidth=1.5)
        for i, y in enumerate(self.rows):
            guide.setColor(color(self.colors[i], 0.1 + 0.35 * self.glow[i]))
            c.drawLine(cx - self.amp, y, cx + self.amp, y, guide)
        pts = [self.pos(i, self.t) for i in range(self.N)]
        path = skia.Path()
        path.moveTo(*pts[0])
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            path.quadTo(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2)
        path.lineTo(*pts[-1])
        shader = skia.GradientShader.MakeLinear(
            [skia.Point(0, self.rows[0]), skia.Point(0, self.rows[-1])],
            [color(self.colors[0], 0.7), color(self.colors[-1], 0.7)])
        c.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=self.W * 0.006,
                                    Shader=shader))
        for i, (x, y) in enumerate(pts):
            self._dot(c, x, y, i)
