"""Wachsender Ball: Bei jedem Aufprall wird der Ball größer, bis er den Kreis ausfüllt."""

from __future__ import annotations

import math

import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center

TAU = 2 * math.pi


class GrowingBall(Scene):
    name = "growing_ball"
    substeps = 8
    outro = 1.8

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        self.cx, self.cy = W * 0.5, H * 0.52
        self.R = W * 0.43
        self.r = W * float(params.get("start_size", 0.03))
        self.growth = W * float(params.get("growth", 0.0035))
        self.g = W * 1.3 * float(params.get("gravity", 1.0))
        self.trail_mode = params.get("trail", "outline")
        rng = self.rng
        self.x = self.cx + rng.uniform(-0.12, 0.12) * W
        self.y = self.cy - self.R * 0.35
        self.vx = W * rng.uniform(-0.6, 0.6)
        self.vy = 0.0
        self.bounces = 0
        self.pulse = 0.0
        self.max_r = self.R * 0.985
        self.layer = None
        if not headless:
            self.layer = skia.Surface.MakeRaster(skia.ImageInfo.Make(
                W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
            self.layer.getCanvas().clear(skia.ColorTRANSPARENT)
            clip = skia.Path()
            clip.addCircle(self.cx, self.cy, self.R)
            self.layer.getCanvas().clipPath(clip, doAntiAlias=True)

    def tone(self) -> tuple[int, int, int]:
        return self.ctx.palette.at((self.t / self.target) % 1.0 if not self.ctx.palette.rainbow
                                   else (self.bounces * 0.021) % 1.0)

    def step(self, h: float) -> None:
        self.vy += self.g * h
        self.x += self.vx * h
        self.y += self.vy * h
        dx, dy = self.x - self.cx, self.y - self.cy
        d = math.hypot(dx, dy) or 1e-9
        if d + self.r < self.R:
            return
        nx, ny = dx / d, dy / d
        vn = self.vx * nx + self.vy * ny
        if vn > 0:
            self.vx -= 2 * vn * nx
            self.vy -= 2 * vn * ny
            a = self.rng.uniform(-0.06, 0.06)
            ca, sa = math.cos(a), math.sin(a)
            self.vx, self.vy = self.vx * ca - self.vy * sa, self.vx * sa + self.vy * ca
            speed = math.hypot(self.vx, self.vy) or 1.0
            k = min(self.W * 2.4, max(self.W * 0.4, speed)) / speed
            self.vx *= k
            self.vy *= k
            self.bounces += 1
            self.r = min(self.max_r, self.r + self.growth)
            self.pulse = 1.0
            self.play(self.music.next(), 0.6, self.x)
        k = (self.R - self.r - 0.01) / d
        self.x, self.y = self.cx + dx * k, self.cy + dy * k
        if self.r >= self.max_r - 1e-6:
            self.finish()

    def after_step(self, h: float) -> None:
        pass  # der Kreis ist voll – Ruhe für das Finale

    def on_finish(self) -> None:
        if self.headless:
            return
        self.flash = 1.0
        self.shake = 0.8
        m = 200
        angs = [TAU * k / m for k in range(m)]
        self.particles.burst([self.cx + self.R * math.cos(a) for a in angs],
                             [self.cy + self.R * math.sin(a) for a in angs], self.tone(), speed=self.W * 0.12,
                             size=self.W * 0.011, life=1.7, center=(self.cx, self.cy), radial=self.W * 0.55)
        self.play(0, 0.9, kind="boom", accent=True)
        for p in self.music.chord():
            self.play(p, 0.5, accent=True)

    def frame(self, dt: float) -> None:
        self.pulse = max(0.0, self.pulse - dt * 5)
        if self.layer is None or self.done_at is not None:
            return
        lc = self.layer.getCanvas()
        rgb = self.tone()
        if self.trail_mode == "fill":
            lc.drawCircle(self.x, self.y, self.r, skia.Paint(AntiAlias=True, Color=color(rgb, 0.10)))
            lc.drawCircle(self.x, self.y, self.r, skia.Paint(
                AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(1.0, self.W * 0.0015),
                Color=color(rgb, 0.5)))
        else:
            lc.drawCircle(self.x, self.y, self.r, skia.Paint(
                AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(1.5, self.W * 0.0026),
                Color=color(rgb, 0.85)))

    def draw(self, c: skia.Canvas) -> None:
        if self.layer is not None:
            c.drawImage(self.layer.makeImageSnapshot(), 0, 0)
        rim = self.ctx.palette.at(0.5) if not self.ctx.palette.rainbow else (235, 235, 255)
        c.drawCircle(self.cx, self.cy, self.R, skia.Paint(
            AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=self.W * 0.009,
            Color=color(mix(rim, WHITE, 0.3))))
        rgb = self.tone()
        grow = 1 + 0.04 * self.pulse
        c.drawCircle(self.x, self.y, self.r * grow, skia.Paint(AntiAlias=True, Color=color(mix(rgb, WHITE, 0.15))))
        c.drawCircle(self.x, self.y, self.r * grow, skia.Paint(
            AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(2.0, self.W * 0.005),
            Color=color(WHITE, 0.9)))
        self.particles.draw(c)
        text_center(c, str(self.bounces), self.W / 2, self.H * 0.15, self.W * 0.14)

    @classmethod
    def calibrate(cls, ctx, params):
        return cls.tune(ctx, params, "growth", [0.002, 0.003, 0.0045, 0.0065, 0.009, 0.013, 0.018])
