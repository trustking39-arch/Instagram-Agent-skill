"""Ball-Vermehrung: Jeder Ball, der aus dem drehenden Ring entkommt, wird zu zwei neuen Bällen."""

from __future__ import annotations

import math

import numpy as np
import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center

TAU = 2 * math.pi


class EscapeMultiply(Scene):
    name = "escape_multiply"
    substeps = 4
    outro = 2.2

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        self.cx, self.cy = W * 0.5, H * 0.52
        self.R = W * 0.42
        self.gap = float(params.get("gap", 0.8))
        self.spin = 1.1 * float(params.get("spin", 1.0))
        self.max_balls = max(5, int(params.get("max_balls", 150)))
        self.br = W * 0.017
        self.g = W * 1.2 * float(params.get("gravity", 1.0))
        self.a0 = self.rng.uniform(0, TAU)
        self.nrng = np.random.default_rng(self.rng.randrange(1 << 30))
        ang = self.rng.uniform(0, TAU)
        self.x = np.array([self.cx])
        self.y = np.array([self.cy])
        self.vx = np.array([math.cos(ang) * W * 0.4])
        self.vy = np.array([math.sin(ang) * W * 0.4])
        self.out = np.zeros(1, bool)        # True = entkommen und fällt
        self.hue = np.zeros(1)
        self.spawned = 1
        self.inside = 1
        self.escapes: list[tuple[float, float]] = []
        self.hits = 0
        self.ring_glow = 0.0

    def gap_center(self) -> float:
        return self.a0 + self.spin * self.t

    def half_gap(self) -> float:
        extra = 0.0 if self.t < self.target else min(2.0, (self.t - self.target) * 0.5)
        return (self.gap + extra) / 2

    def _spawn(self, count: int) -> None:
        ang = self.nrng.uniform(0, TAU, count)
        sp = self.W * self.nrng.uniform(0.3, 0.5, count)
        self.x = np.concatenate([self.x, self.cx + self.nrng.uniform(-4, 4, count)])
        self.y = np.concatenate([self.y, self.cy + self.nrng.uniform(-4, 4, count)])
        self.vx = np.concatenate([self.vx, np.cos(ang) * sp])
        self.vy = np.concatenate([self.vy, np.sin(ang) * sp])
        self.out = np.concatenate([self.out, np.zeros(count, bool)])
        hues = (np.arange(self.spawned, self.spawned + count) * 0.618034) % 1.0
        self.hue = np.concatenate([self.hue, hues])
        self.spawned += count

    def step(self, h: float) -> None:
        self.vy += self.g * h
        self.x += self.vx * h
        self.y += self.vy * h
        if self.done_at is None:
            ins = ~self.out
            dx, dy = self.x - self.cx, self.y - self.cy
            d = np.maximum(np.hypot(dx, dy), 1e-9)
            esc = ins & (d > self.R)
            near = ins & ~esc & (d + self.br >= self.R)
            if near.any():
                diff = (np.arctan2(dy, dx) - self.gap_center() + math.pi) % TAU - math.pi
                hit = near & ~(np.abs(diff) + self.br / self.R < self.half_gap())
                idx = np.nonzero(hit)[0]
                if len(idx):
                    nx, ny = dx[idx] / d[idx], dy[idx] / d[idx]
                    vn = self.vx[idx] * nx + self.vy[idx] * ny
                    refl = np.where(vn > 0, vn, 0.0)
                    vx, vy = self.vx[idx] - 2 * refl * nx, self.vy[idx] - 2 * refl * ny
                    a = self.nrng.uniform(-0.05, 0.05, len(idx))
                    vx, vy = vx * np.cos(a) - vy * np.sin(a), vx * np.sin(a) + vy * np.cos(a)
                    sp = np.maximum(np.hypot(vx, vy), 1e-6)
                    k = np.clip(sp, max(self.W * 0.35, math.sqrt(self.g * self.R)), self.W * 2.2) / sp
                    self.vx[idx], self.vy[idx] = vx * k, vy * k
                    push = (self.R - self.br - 0.01) / d[idx]
                    self.x[idx] = self.cx + dx[idx] * push
                    self.y[idx] = self.cy + dy[idx] * push
                    self.hits += int((vn > 0).sum())
            idx = np.nonzero(esc)[0]
            if len(idx):
                self.out[idx] = True
                if not self.headless:
                    self.escapes.extend(zip(self.x[idx].tolist(), self.y[idx].tolist()))
                self._spawn(2 * len(idx))
                self.inside += len(idx)
                if self.inside >= self.max_balls:
                    self.finish()
        gone = self.out & (self.y > self.H + 4 * self.br)
        if gone.any():
            keep = ~gone
            self.x, self.y, self.vx, self.vy = self.x[keep], self.y[keep], self.vx[keep], self.vy[keep]
            self.out, self.hue = self.out[keep], self.hue[keep]

    def on_finish(self) -> None:
        self.out[:] = True  # der Ring zerplatzt, alle Bälle fallen heraus
        if self.headless:
            return
        self.flash = 1.0
        self.shake = 1.0
        m = 160
        angs = np.linspace(0, TAU, m, endpoint=False)
        self.particles.burst(self.cx + self.R * np.cos(angs), self.cy + self.R * np.sin(angs),
                             self.ctx.palette.at(0.2), speed=self.W * 0.15, size=self.W * 0.01, life=1.8,
                             center=(self.cx, self.cy), radial=self.W * 0.5)
        self.play(0, 0.9, kind="boom", accent=True)
        self.play(0, 0.5, kind="burst", accent=True)
        for p in self.music.chord():
            self.play(p, 0.45, accent=True)

    def frame(self, dt: float) -> None:
        self.ring_glow = max(0.0, self.ring_glow - dt * 3)
        for k, (x, y) in enumerate(self.escapes):
            if k < 3:
                self.play(self.music.next(), 0.42, x)
            self.particles.burst([x] * 14, [y] * 14, self.ctx.palette.at(self.fx.random()), speed=self.W * 0.35,
                                 size=self.W * 0.007, life=0.7)
        if self.escapes:
            self.ring_glow = 1.0
        self.escapes = []
        if self.hits and self.inside <= 40 and int(self.t * self.ctx.fps) % 3 == 0:
            self.play(self.music.degree(self.fx.randrange(10, 15)), 0.08, self.cx, kind="tick")
        self.hits = 0

    def draw(self, c: skia.Canvas) -> None:
        cx, cy, R = self.cx, self.cy, self.R
        ring_rgb = self.ctx.palette.at((self.t * 0.03) % 1.0) if self.ctx.palette.rainbow else self.ctx.palette.at(0.15)
        if self.done_at is None:
            half = self.half_gap()
            paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap,
                               StrokeWidth=self.W * 0.014 * (1 + 0.35 * self.ring_glow),
                               Color=color(mix(ring_rgb, WHITE, 0.1 + 0.35 * self.ring_glow)))
            c.drawArc(skia.Rect(cx - R, cy - R, cx + R, cy + R), math.degrees(self.gap_center() + half),
                      360 - math.degrees(2 * half), False, paint)
        fill = skia.Paint(AntiAlias=True)
        rim = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(1.0, self.br * 0.28),
                         Color=color(WHITE, 0.85))
        pal = self.ctx.palette
        for x, y, hue in zip(self.x.tolist(), self.y.tolist(), self.hue.tolist()):
            fill.setColor(color(pal.at(hue)))
            c.drawCircle(x, y, self.br, fill)
            c.drawCircle(x, y, self.br, rim)
        self.particles.draw(c)
        text_center(c, str(self.inside if self.done_at is None else self.max_balls), self.W / 2, self.H * 0.15,
                    self.W * 0.14)

    @classmethod
    def calibrate(cls, ctx, params):
        return cls.tune(ctx, params, "gap", [0.35, 0.45, 0.6, 0.8, 1.05, 1.35, 1.7])
