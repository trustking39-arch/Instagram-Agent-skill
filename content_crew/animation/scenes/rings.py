"""Ring-Flucht: Ein Ball springt in sich drehenden Ringen mit je einer Lücke. Jede Lücke zerstört einen Ring."""

from __future__ import annotations

import math

import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center

TAU = 2 * math.pi


class _Ring:
    __slots__ = ("r", "a0", "w", "rgb", "glow")

    def __init__(self, r: float, a0: float, w: float, rgb):
        self.r, self.a0, self.w, self.rgb, self.glow = r, a0, w, rgb, 0.0


class _Ball:
    __slots__ = ("x", "y", "vx", "vy", "trail")

    def __init__(self, x: float, y: float, vx: float, vy: float):
        self.x, self.y, self.vx, self.vy, self.trail = x, y, vx, vy, []


class RingEscape(Scene):
    name = "ring_escape"
    substeps = 8
    outro = 1.8

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        self.cx, self.cy = W * 0.5, H * 0.52
        n = max(3, int(params.get("rings", 24)))
        self.gap = float(params.get("gap", 0.8))
        spin = float(params.get("spin", 1.0))
        pattern = params.get("pattern", "spiral")
        r_min, r_max = W * 0.085, W * 0.445
        self.br = W * 0.0155 * float(params.get("ball_size", 1.0))
        self.g = W * 1.3 * float(params.get("gravity", 1.0))
        spacing = (r_max - r_min) / max(1, n - 1)
        self.width = max(2.0, min(W * 0.0095, spacing * 0.5))
        rng = self.rng
        self.rings: list[_Ring] = []
        for i in range(n):
            r = r_min + spacing * i
            if pattern == "spiral":
                a0, w = i * 0.36, 0.95 * spin
            elif pattern == "alternating":
                a0, w = rng.uniform(0, TAU), spin * (0.7 + 0.5 * rng.random()) * (1 if i % 2 == 0 else -1)
            else:
                a0, w = rng.uniform(0, TAU), spin * rng.uniform(-1.6, 1.6)
            self.rings.append(_Ring(r, a0, w, self.ctx.palette.at(i / max(1, n - 1))))
        self.inner = 0  # Index des innersten noch heilen Rings
        self.balls = []
        for _ in range(max(1, int(params.get("balls", 1)))):
            ang, sp = rng.uniform(0, TAU), W * rng.uniform(0.25, 0.45)
            self.balls.append(_Ball(self.cx + rng.uniform(-3, 3), self.cy + rng.uniform(-3, 3),
                                    math.cos(ang) * sp, math.sin(ang) * sp))

    def half_gap(self) -> float:
        extra = 0.0 if self.t < self.target else min(2.2, (self.t - self.target) * 0.6)  # Notbremse: Lücken wachsen
        return (self.gap + extra) / 2

    def _kick(self, b: _Ball, r: float) -> None:
        """Etwas Zufall gegen endlose Muster, Mindesttempo gegen Stillstand."""
        a = self.rng.uniform(-0.05, 0.05)
        ca, sa = math.cos(a), math.sin(a)
        b.vx, b.vy = b.vx * ca - b.vy * sa, b.vx * sa + b.vy * ca
        speed = math.hypot(b.vx, b.vy) or 1.0
        lo, hi = max(self.W * 0.35, math.sqrt(self.g * r)), self.W * 2.4
        k = min(hi, max(lo, speed)) / speed
        b.vx *= k
        b.vy *= k

    def step(self, h: float) -> None:
        n = len(self.rings)
        half = self.half_gap()
        cx, cy, br = self.cx, self.cy, self.br
        for b in self.balls:
            b.vy += self.g * h
            b.x += b.vx * h
            b.y += b.vy * h
            dx, dy = b.x - cx, b.y - cy
            d = math.hypot(dx, dy) or 1e-9
            while self.inner < n and d > self.rings[self.inner].r:
                self._break(self.inner)
            if self.inner >= n:
                continue
            ring = self.rings[self.inner]
            if d + br < ring.r:
                continue
            diff = (math.atan2(dy, dx) - (ring.a0 + ring.w * self.t) + math.pi) % TAU - math.pi
            if abs(diff) + br / ring.r < half:
                continue  # passt durch die Lücke
            nx, ny = dx / d, dy / d
            vn = b.vx * nx + b.vy * ny
            if vn > 0:
                b.vx -= 2 * vn * nx
                b.vy -= 2 * vn * ny
                self._kick(b, ring.r)
                ring.glow = 1.0
                self.play(self.music.next(), 0.55, b.x)
            k = (ring.r - br - 0.01) / d
            b.x, b.y = cx + dx * k, cy + dy * k

    def _break(self, i: int) -> None:
        ring = self.rings[i]
        self.inner += 1
        if not self.headless:
            half = self.half_gap()
            m = int(24 + ring.r / self.W * 110)
            start = ring.a0 + ring.w * self.t + half
            angs = [start + (TAU - 2 * half) * k / m for k in range(m)]
            xs = [self.cx + ring.r * math.cos(a) for a in angs]
            ys = [self.cy + ring.r * math.sin(a) for a in angs]
            self.particles.burst(xs, ys, ring.rgb, speed=self.W * 0.12, size=self.width * 1.5, life=1.3,
                                 center=(self.cx, self.cy), radial=self.W * 0.35)
            self.play(self.music.next() + 12, 0.35, self.cx, kind="burst")
            self.shake = min(1.0, self.shake + 0.3)
        if self.inner >= len(self.rings):
            self.finish()

    def on_finish(self) -> None:
        if self.headless:
            return
        self.flash = 1.0
        self.shake = 1.0
        for k, b in enumerate(self.balls):
            self.particles.burst([b.x] * 90, [b.y] * 90, self.ctx.palette.cycle(k), speed=self.W * 0.9,
                                 size=self.W * 0.012, life=1.6)
        self.play(0, 0.9, kind="boom", accent=True)
        for p in self.music.chord():
            self.play(p, 0.45, accent=True)

    def frame(self, dt: float) -> None:
        for ring in self.rings:
            ring.glow = max(0.0, ring.glow - dt * 3.5)
        for b in self.balls:
            b.trail.append((b.x, b.y))
            del b.trail[:-14]

    def draw(self, c: skia.Canvas) -> None:
        cx, cy = self.cx, self.cy
        half = self.half_gap()
        sweep = 360 - math.degrees(2 * half)
        paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap)
        for ring in self.rings[self.inner:]:
            r = ring.r
            paint.setColor(color(mix(ring.rgb, WHITE, ring.glow * 0.7)))
            paint.setStrokeWidth(self.width * (1 + ring.glow * 0.8))
            start = math.degrees(ring.a0 + ring.w * self.t + half)
            c.drawArc(skia.Rect(cx - r, cy - r, cx + r, cy + r), start, sweep, False, paint)
        self.particles.draw(c)

        trail_rgb = self.rings[min(self.inner, len(self.rings) - 1)].rgb
        fill = skia.Paint(AntiAlias=True)
        for b in self.balls:
            count = len(b.trail)
            for k, (x, y) in enumerate(b.trail):
                f = (k + 1) / count
                fill.setColor(color(trail_rgb, 0.35 * f))
                c.drawCircle(x, y, self.br * (0.35 + 0.65 * f), fill)
            fill.setColor(color(trail_rgb))
            c.drawCircle(b.x, b.y, self.br, fill)
            fill.setColor(color(WHITE))
            c.drawCircle(b.x, b.y, self.br * 0.62, fill)

        remaining = len(self.rings) - self.inner
        text_center(c, str(remaining), self.W / 2, self.H * 0.15, self.W * 0.14)

    @classmethod
    def calibrate(cls, ctx, params):
        target = max(3.0, ctx.duration - cls.outro)
        params = {**params, "rings": min(int(params.get("rings", 24)), max(6, int(target * 1.4)))}
        return cls.tune(ctx, params, "gap", [0.5, 0.65, 0.8, 1.0, 1.25, 1.55, 1.9, 2.3])
