"""Dreh-Arena: Nummerierte Bälle in einem sich drehenden Vieleck mit offener Seite. Wer bleibt als Letzter drin?"""

from __future__ import annotations

import math

import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center

TAU = 2 * math.pi


class _Ball:
    __slots__ = ("x", "y", "vx", "vy", "num", "rgb", "out", "trail", "last_hit")

    def __init__(self, x, y, vx, vy, num, rgb):
        self.x, self.y, self.vx, self.vy, self.num, self.rgb = x, y, vx, vy, num, rgb
        self.out = False
        self.trail: list[tuple[float, float]] = []
        self.last_hit = -1.0


class SpinArena(Scene):
    name = "spin_arena"
    substeps = 8
    outro = 2.4

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        rng = self.rng
        self.cx, self.cy = W * 0.5, H * 0.53
        self.sides = max(3, min(8, int(params.get("sides", 6))))
        self.R = W * 0.43
        self.gap = float(params.get("gap", 0.3))
        self.omega = 0.9 * float(params.get("spin", 1.0)) * rng.choice([-1, 1])
        self.g = W * 1.3 * float(params.get("gravity", 1.0))
        count = max(3, int(params.get("balls", 10)))
        self.br = W * (0.036 if count <= 8 else 0.03 if count <= 12 else 0.025)
        self.a0 = rng.uniform(0, TAU)
        pal = self.ctx.palette
        self.balls: list[_Ball] = []
        for i in range(count):
            ang, rad = i * 2.39996, self.br * 2.3 * math.sqrt(i + 0.5)  # Sonnenblumen-Muster: keine Überlappung
            sp = W * rng.uniform(0.2, 0.45)
            va = rng.uniform(0, TAU)
            rgb = pal.cycle(i) if pal.rainbow else pal.at(i / max(1, count - 1))
            self.balls.append(_Ball(self.cx + rad * math.cos(ang), self.cy + rad * math.sin(ang),
                                    math.cos(va) * sp, math.sin(va) * sp, i + 1, rgb))
        self.inside = count
        self.winner: _Ball | None = None
        self.last_note = -1.0
        self.last_tick = -1.0
        self.glow = 0.0
        self.exits: list[_Ball] = []

    # --- Geometrie --------------------------------------------------------
    def open_fraction(self) -> float:
        extra = 0.0 if self.t < self.target else (self.t - self.target) * 0.08  # Notbremse
        return min(0.9, self.gap + extra)

    def walls(self) -> list[tuple[float, float, float, float]]:
        n, th = self.sides, self.a0 + self.omega * self.t
        pts = [(self.cx + self.R * math.cos(th + TAU * k / n), self.cy + self.R * math.sin(th + TAU * k / n))
               for k in range(n)]
        segs = []
        for k in range(n):
            (ax, ay), (bx, by) = pts[k], pts[(k + 1) % n]
            if k == 0 and self.done_at is None:  # die offene Seite: Lücke in der Mitte
                keep = (1 - self.open_fraction()) / 2
                segs.append((ax, ay, ax + (bx - ax) * keep, ay + (by - ay) * keep))
                segs.append((bx - (bx - ax) * keep, by - (by - ay) * keep, bx, by))
            elif self.done_at is None:
                segs.append((ax, ay, bx, by))
        return segs

    # --- Physik -------------------------------------------------------------
    def step(self, h: float) -> None:
        br, cx, cy, w = self.br, self.cx, self.cy, self.omega
        vmax = self.W * 2.5
        for b in self.balls:
            b.vy += self.g * h
            b.x += b.vx * h
            b.y += b.vy * h
        if self.done_at is not None:
            return
        walls = self.walls()
        live = [b for b in self.balls if not b.out]
        for b in live:
            for ax, ay, bx, by in walls:
                ex, ey = bx - ax, by - ay
                u = max(0.0, min(1.0, ((b.x - ax) * ex + (b.y - ay) * ey) / (ex * ex + ey * ey)))
                qx, qy = ax + u * ex, ay + u * ey
                dx, dy = b.x - qx, b.y - qy
                d2 = dx * dx + dy * dy
                if d2 >= br * br:
                    continue
                d = math.sqrt(d2) or 1e-9
                nx, ny = dx / d, dy / d
                if 0.0 < u < 1.0:  # an einer Seite immer nach innen drücken, nie hindurch
                    ix, iy = -ey, ex
                    if ix * (cx - qx) + iy * (cy - qy) < 0:
                        ix, iy = -ix, -iy
                    il = math.hypot(ix, iy)
                    ix, iy = ix / il, iy / il
                    if nx * ix + ny * iy < 0:
                        nx, ny = ix, iy
                wx, wy = -w * (qy - cy), w * (qx - cx)  # Geschwindigkeit der Wand an der Stelle
                rvx, rvy = b.vx - wx, b.vy - wy
                vn = rvx * nx + rvy * ny
                if vn < 0:
                    tx, ty = -ny, nx
                    vt = rvx * tx + rvy * ty
                    vn2, vt2 = -vn * 0.92, vt * 0.94
                    b.vx, b.vy = vn2 * nx + vt2 * tx + wx, vn2 * ny + vt2 * ty + wy
                    if -vn > self.W * 0.15 and self.t - self.last_note > 0.07:
                        self.last_note = self.t
                        self.glow = 1.0
                        self.play(self.music.next(), 0.45, b.x)
                b.x, b.y = qx + nx * br, qy + ny * br
            if math.hypot(b.x - cx, b.y - cy) > self.R + br:
                b.out = True
                self.inside -= 1
                if not self.headless:
                    self.exits.append(b)
        live = [b for b in live if not b.out]
        for i, b1 in enumerate(live):
            for b2 in live[i + 1:]:
                dx, dy = b2.x - b1.x, b2.y - b1.y
                if abs(dx) > 2 * br or abs(dy) > 2 * br:
                    continue
                d2 = dx * dx + dy * dy
                if d2 >= 4 * br * br or d2 == 0:
                    continue
                d = math.sqrt(d2)
                nx, ny = dx / d, dy / d
                push = (2 * br - d) / 2
                b1.x, b1.y, b2.x, b2.y = b1.x - nx * push, b1.y - ny * push, b2.x + nx * push, b2.y + ny * push
                vn = (b1.vx - b2.vx) * nx + (b1.vy - b2.vy) * ny
                if vn > 0:
                    j = vn * 0.97
                    b1.vx, b1.vy, b2.vx, b2.vy = b1.vx - j * nx, b1.vy - j * ny, b2.vx + j * nx, b2.vy + j * ny
                    if vn > self.W * 0.2 and self.t - self.last_tick > 0.05:
                        self.last_tick = self.t
                        self.play(self.music.degree(12 + b1.num % 5), 0.07, b1.x, kind="tick")
        for b in live:
            sp = math.hypot(b.vx, b.vy)
            if sp > vmax:
                b.vx, b.vy = b.vx * vmax / sp, b.vy * vmax / sp
        if self.inside <= 1:
            remaining = [b for b in self.balls if not b.out]
            self.winner = remaining[0] if remaining else max(self.balls, key=lambda b: b.y)
            self.finish()

    def on_finish(self) -> None:
        if self.headless:
            return
        self.flash = 0.6
        self.shake = 0.8
        segs = self.walls_at_finish()
        xs, ys = [], []
        for ax, ay, bx, by in segs:
            for k in range(30):
                xs.append(ax + (bx - ax) * k / 29)
                ys.append(ay + (by - ay) * k / 29)
        self.particles.burst(xs, ys, self.ctx.palette.at(0.3), speed=self.W * 0.15, size=self.W * 0.01, life=1.8,
                             center=(self.cx, self.cy), radial=self.W * 0.45)
        w = self.winner
        self.particles.burst([w.x] * 60, [w.y] * 60, w.rgb, speed=self.W * 0.7, size=self.W * 0.011, life=1.6)
        self.play(0, 0.85, kind="boom", accent=True)
        for p in self.music.chord():
            self.play(p, 0.45, accent=True)

    def walls_at_finish(self):
        n, th = self.sides, self.a0 + self.omega * self.t
        pts = [(self.cx + self.R * math.cos(th + TAU * k / n), self.cy + self.R * math.sin(th + TAU * k / n))
               for k in range(n)]
        return [(*pts[k], *pts[(k + 1) % n]) for k in range(n)]

    def after_step(self, h: float) -> None:
        for b in self.balls:  # nach dem Finale: der Sieger schwebt, der Rest fällt
            if b is self.winner:
                b.vx *= 0.9
                b.vy *= 0.9
                b.x += (self.cx - b.x) * min(1.0, 3 * h)
                b.y += (self.cy - b.y) * min(1.0, 3 * h)
            else:
                b.vy += self.g * h
                b.x += b.vx * h
                b.y += b.vy * h

    def frame(self, dt: float) -> None:
        self.glow = max(0.0, self.glow - dt * 4)
        for b in self.exits:
            self.particles.burst([b.x] * 26, [b.y] * 26, b.rgb, speed=self.W * 0.45, size=self.W * 0.008, life=0.9)
            self.play(self.music.next() + 12, 0.35, b.x)
            self.play(0, 0.2, b.x, kind="burst")
        self.exits = []
        for b in self.balls:
            b.trail.append((b.x, b.y))
            del b.trail[:-7]
        self.balls = [b for b in self.balls if b.y < self.H + 200 or b is self.winner]

    # --- Zeichnen -----------------------------------------------------------
    def draw(self, c: skia.Canvas) -> None:
        W = self.W
        if self.done_at is None:
            wall = skia.Paint(AntiAlias=True, StrokeWidth=W * 0.013 * (1 + 0.25 * self.glow),
                              StrokeCap=skia.Paint.kRound_Cap,
                              Color=color(mix(self.ctx.palette.at(0.3), WHITE, 0.15 + 0.35 * self.glow)))
            for ax, ay, bx, by in self.walls():
                c.drawLine(ax, ay, bx, by, wall)
        fill = skia.Paint(AntiAlias=True)
        rim = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(2.0, self.br * 0.14))
        for b in self.balls:
            alpha = 0.55 if b.out else 1.0
            n = len(b.trail)
            for k, (x, y) in enumerate(b.trail[:-1]):
                fill.setColor(color(b.rgb, 0.22 * alpha * (k + 1) / n))
                c.drawCircle(x, y, self.br * 0.85, fill)
        for b in self.balls:
            big = 1.0
            if b is self.winner and self.done_at is not None:
                big = 1.0 + min(0.8, (self.t - self.done_at) * 1.2)
            alpha = 0.55 if b.out else 1.0
            r = self.br * big
            fill.setColor(color(b.rgb, alpha))
            c.drawCircle(b.x, b.y, r, fill)
            rim.setColor(color(WHITE, 0.9 * alpha))
            c.drawCircle(b.x, b.y, r, rim)
            light = sum(b.rgb) / 3 > 165
            text_center(c, str(b.num), b.x, b.y, r * 1.05, (20, 20, 30) if light else WHITE, alpha)
        self.particles.draw(c)
        if self.done_at is not None and self.winner is not None:
            text_center(c, f"#{self.winner.num}", W / 2, self.H * 0.15, W * 0.16, mix(self.winner.rgb, WHITE, 0.2))
        else:
            text_center(c, str(self.inside), W / 2, self.H * 0.15, W * 0.14)

    @classmethod
    def calibrate(cls, ctx, params):
        return cls.tune(ctx, params, "gap", [0.15, 0.19, 0.24, 0.3, 0.38, 0.48, 0.6])
