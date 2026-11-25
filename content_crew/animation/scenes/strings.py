"""Faden-Netz: Ein Ball springt im Kreis – jeder Aufprall spannt einen neuen leuchtenden Faden zum Ball."""

from __future__ import annotations

import math

import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center

TAU = 2 * math.pi


class StringArt(Scene):
    name = "string_art"
    substeps = 8
    outro = 2.2

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        rng = self.rng
        self.cx, self.cy = W * 0.5, H * 0.52
        self.R = W * 0.43
        self.br = W * 0.022
        self.speed = float(params.get("speed", 1.0))
        self.max_points = max(8, int(params.get("points", 60)))
        self.g = W * 1.2 * float(params.get("gravity", 1.0))
        self.web = params.get("web", "ball")  # ball = Fäden zum Ball, chain = Fäden zwischen den Treffern
        self.x = self.cx + rng.uniform(-0.1, 0.1) * W
        self.y = self.cy - self.R * 0.3
        ang = rng.uniform(0, TAU)
        self.vx, self.vy = math.cos(ang) * W * 0.5 * self.speed, math.sin(ang) * W * 0.5 * self.speed
        self.points: list[tuple[float, float, float]] = []  # x, y, Zeitpunkt
        self.pulse = 0.0

    def step(self, h: float) -> None:
        self.vy += self.g * h
        self.x += self.vx * h
        self.y += self.vy * h
        dx, dy = self.x - self.cx, self.y - self.cy
        d = math.hypot(dx, dy) or 1e-9
        lim = self.R - self.br
        if d < lim:
            return
        nx, ny = dx / d, dy / d
        vn = self.vx * nx + self.vy * ny
        if vn > 0:
            self.vx -= 2 * vn * nx
            self.vy -= 2 * vn * ny
            a = self.rng.uniform(-0.07, 0.07)
            ca, sa = math.cos(a), math.sin(a)
            self.vx, self.vy = self.vx * ca - self.vy * sa, self.vx * sa + self.vy * ca
            sp = math.hypot(self.vx, self.vy) or 1.0
            k = min(self.W * 3.2, max(self.W * 0.45 * self.speed, sp)) / sp
            self.vx *= k
            self.vy *= k
            self.points.append((self.cx + nx * self.R, self.cy + ny * self.R, self.t))
            self.pulse = 1.0
            self.play(self.music.next(), 0.55, self.x)
            if len(self.points) >= self.max_points:
                self.finish()
        self.x, self.y = self.cx + nx * lim, self.cy + ny * lim

    def after_step(self, h: float) -> None:
        self.vx *= 0.96
        self.vy *= 0.96
        self.x += (self.cx - self.x) * min(1.0, 2.5 * h)
        self.y += (self.cy - self.y) * min(1.0, 2.5 * h)

    def on_finish(self) -> None:
        if self.headless:
            return
        self.flash = 0.6
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        self.particles.burst(xs * 3, ys * 3, self.ctx.palette.at(0.6), speed=self.W * 0.25, size=self.W * 0.009,
                             life=1.6, center=(self.cx, self.cy), radial=self.W * 0.3)
        self.play(0, 0.8, kind="boom", accent=True)
        for p in self.music.chord():
            self.play(p, 0.45, accent=True)

    def frame(self, dt: float) -> None:
        self.pulse = max(0.0, self.pulse - dt * 4)

    def draw(self, c: skia.Canvas) -> None:
        W = self.W
        n = len(self.points)
        pal = self.ctx.palette
        c.drawCircle(self.cx, self.cy, self.R, skia.Paint(
            AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=W * 0.006,
            Color=color(mix(pal.at(0.5), WHITE, 0.4), 0.8)))
        line = skia.Paint(AntiAlias=True, StrokeWidth=max(1.2, W * 0.0022), StrokeCap=skia.Paint.kRound_Cap)
        dot = skia.Paint(AntiAlias=True)
        hx, hy = (self.x, self.y) if self.web == "ball" or self.done_at is not None else (None, None)
        for i, (px, py, born) in enumerate(self.points):
            rgb = pal.at(i / max(1, self.max_points - 1))
            fresh = max(0.0, 1.0 - (self.t - born) * 2.5)
            line.setColor(color(mix(rgb, WHITE, 0.5 * fresh), 0.55 + 0.4 * fresh))
            if hx is not None:
                c.drawLine(px, py, hx, hy, line)
            elif i > 0:
                c.drawLine(self.points[i - 1][0], self.points[i - 1][1], px, py, line)
            dot.setColor(color(mix(rgb, WHITE, 0.4)))
            c.drawCircle(px, py, W * 0.006 * (1 + fresh), dot)
        if self.web != "ball" and n and self.done_at is None:  # loser Faden vom letzten Treffer zum Ball
            line.setColor(color(WHITE, 0.6))
            c.drawLine(self.points[-1][0], self.points[-1][1], self.x, self.y, line)
        r = self.br * (1 + 0.25 * self.pulse)
        c.drawCircle(self.x, self.y, r * 1.6, skia.Paint(AntiAlias=True, Color=color(pal.at(0.5), 0.25)))
        c.drawCircle(self.x, self.y, r, skia.Paint(AntiAlias=True, Color=color(WHITE)))
        self.particles.draw(c)
        text_center(c, str(n), W / 2, self.H * 0.15, W * 0.14)

    @classmethod
    def calibrate(cls, ctx, params):
        target = max(3.0, ctx.duration - cls.outro)
        params = {**params, "points": min(int(params.get("points", 60)), max(12, int(target * 2.4)))}
        return cls.tune(ctx, params, "speed", [0.6, 0.9, 1.3, 1.8, 2.4, 3.1, 4.0])
