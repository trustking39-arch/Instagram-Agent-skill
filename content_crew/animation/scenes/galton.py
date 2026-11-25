"""Galton-Brett: Hunderte Kugeln fallen durch Nägel und bilden von selbst eine Glockenkurve."""

from __future__ import annotations

import math

import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center


class _Ball:
    __slots__ = ("x", "y", "vx", "vy", "i", "phase", "bin", "tx", "ty")

    def __init__(self, x, y, vx, i):
        self.x, self.y, self.vx, self.vy, self.i = x, y, vx, 0.0, i
        self.phase = 0          # 0 = fällt durch die Nägel, 1 = sinkt ins Fach
        self.bin = -1
        self.tx = self.ty = 0.0


class Galton(Scene):
    name = "galton"
    substeps = 6
    outro = 2.4

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        self.K = k = max(4, int(params.get("rows", 12)))
        self.N = max(10, int(params.get("balls", 220)))
        self.interval = float(params.get("interval", 0.12))
        self.cx = W * 0.5
        self.dx = W * 0.9 / (k + 1)
        self.dy = self.dx * 0.86
        self.top = H * 0.21
        self.last_row = self.top + (k - 1) * self.dy
        self.bins_top = self.last_row + self.dy * 0.7
        self.floor = H * 0.865
        self.pr = self.dx * 0.075
        expected = self.N * math.comb(k, k // 2) / 2 ** k
        bin_h = self.floor - self.bins_top
        self.br = min(self.dx * 0.19, math.sqrt(bin_h * self.dx / (4 * 0.87 * 1.35 * expected)))
        self.per_row = max(1, int(self.dx * 0.92 // (2 * self.br)))
        rows_needed = max(1, int(params.get("stack_rows") or 0) or math.ceil(expected * 1.3 / self.per_row))
        self.slot_h = min(2 * self.br * 0.87, (bin_h - 2 * self.br) / max(1, rows_needed - 1))
        self.g = W * 2.0
        self.balls: list[_Ball] = []
        self.released = 0
        self.settled = 0
        self.counts = [0] * (k + 1)
        self.last_tick = -1.0
        self.layer = None
        if not headless:
            self.layer = skia.Surface.MakeRaster(skia.ImageInfo.Make(
                W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
            self.layer.getCanvas().clear(skia.ColorTRANSPARENT)

    # --- Geometrie --------------------------------------------------------
    def peg(self, row: int, j: int) -> tuple[float, float]:
        return self.cx + (j - row / 2) * self.dx, self.top + row * self.dy

    def bin_x(self, b: int) -> float:
        return self.cx + (b - self.K / 2) * self.dx

    def slot(self, b: int, n: int) -> tuple[float, float]:
        row, col = divmod(n, self.per_row)
        shift = 0.5 if row % 2 and self.per_row > 1 else 0.0  # versetzt stapeln wie echte Kugeln
        x = self.bin_x(b) + (col - (self.per_row - 1) / 2 + shift * 0.5) * 2 * self.br * 0.98
        return x, self.floor - self.br - row * self.slot_h

    def color_of(self, i: int):
        return self.ctx.palette.at(i / max(1, self.N - 1))

    # --- Physik -------------------------------------------------------------
    def step(self, h: float) -> None:
        while self.released < self.N and self.t >= self.released * self.interval:
            jitter = self.rng.uniform(-1.5, 1.5)
            self.balls.append(_Ball(self.cx + jitter, self.top - self.dy * 0.9, self.rng.uniform(-12, 12),
                                    self.released))
            self.released += 1
        keep = []
        for b in self.balls:
            b.vy += self.g * h
            if b.phase == 0:
                b.vx *= math.exp(-3.5 * h)
                b.x += b.vx * h
                b.y += b.vy * h
                self._pegs(b)
                half = ((b.y - self.top) / self.dy + 1.6) * self.dx / 2  # Trichter: nicht seitlich hinaus
                if abs(b.x - self.cx) > half and (b.x - self.cx) * b.vx > 0:
                    b.vx = -b.vx * 0.3
                if b.y > self.bins_top:
                    b.bin = max(0, min(self.K, round((b.x - self.cx) / self.dx + self.K / 2)))
                    b.tx, b.ty = self.slot(b.bin, self.counts[b.bin])
                    self.counts[b.bin] += 1
                    b.phase = 1
                keep.append(b)
            else:
                b.x += (b.tx - b.x) * min(1.0, 14 * h)
                b.y += b.vy * h
                if b.y >= b.ty:
                    self._settle(b)
                else:
                    keep.append(b)
        self.balls = keep
        if self.released >= self.N and not self.balls and self.done_at is None:
            self.finish()

    def _pegs(self, b: _Ball) -> None:
        row0 = round((b.y - self.top) / self.dy)
        for row in (row0 - 1, row0, row0 + 1):
            if not 0 <= row < self.K:
                continue
            j = max(0, min(row, round((b.x - self.cx) / self.dx + row / 2)))
            px, py = self.peg(row, j)
            dx, dy = b.x - px, b.y - py
            d = math.hypot(dx, dy)
            reach = self.br + self.pr
            if d >= reach or d == 0:
                continue
            nx, ny = dx / d, dy / d
            b.x, b.y = px + nx * reach, py + ny * reach
            vn = b.vx * nx + b.vy * ny
            if vn < 0:
                b.vx -= 1.3 * vn * nx
                b.vy -= 1.3 * vn * ny
                kick = self.rng.uniform(-1, 1) * self.W * 0.02  # Zufall entscheidet: links oder rechts
                b.vx += -ny * kick
                b.vy += nx * kick
                if self.t - self.last_tick > 0.035:
                    self.last_tick = self.t
                    self.play(self.music.degree(14 + row % 5), 0.05, b.x, kind="tick")

    def _settle(self, b: _Ball) -> None:
        b.x, b.y = b.tx, b.ty
        self.settled += 1
        if self.headless:
            return
        rgb = self.color_of(b.i)
        lc = self.layer.getCanvas()
        lc.drawCircle(b.x, b.y, self.br * 0.96, skia.Paint(AntiAlias=True, Color=color(rgb)))
        lc.drawCircle(b.x - self.br * 0.3, b.y - self.br * 0.3, self.br * 0.3,
                      skia.Paint(AntiAlias=True, Color=color(WHITE, 0.35)))
        center = self.K / 2
        self.play(self.music.degree(int(abs(b.bin - center) * -1 + 10)), 0.2, b.x)

    def on_finish(self) -> None:
        if self.headless:
            return
        self.flash = 0.4
        self.play(0, 0.7, kind="boom", accent=True)
        for p in self.music.chord():
            self.play(p, 0.4, accent=True)

    # --- Zeichnen -----------------------------------------------------------
    def draw(self, c: skia.Canvas) -> None:
        W = self.W
        wall = skia.Paint(AntiAlias=True, StrokeWidth=max(2.0, W * 0.003), StrokeCap=skia.Paint.kRound_Cap,
                          Color=color(WHITE, 0.25))
        for side in (-1, 1):  # Trichterwände
            x0 = self.cx + side * 1.6 * self.dx / 2
            x1 = self.cx + side * ((self.K - 1) + 1.6) * self.dx / 2
            c.drawLine(x0, self.top - self.dy * 0.6, x1, self.last_row + self.dy * 0.5, wall)
        peg_paint = skia.Paint(AntiAlias=True, Color=color(mix(self.ctx.palette.at(0.5), WHITE, 0.6)))
        for row in range(self.K):
            for j in range(row + 1):
                px, py = self.peg(row, j)
                c.drawCircle(px, py, self.pr, peg_paint)
        div = skia.Paint(AntiAlias=True, StrokeWidth=max(2.0, W * 0.0035), Color=color(WHITE, 0.35))
        for b in range(self.K + 2):
            x = self.bin_x(b) - self.dx / 2
            c.drawLine(x, self.bins_top, x, self.floor, div)
        c.drawLine(self.bin_x(0) - self.dx / 2, self.floor, self.bin_x(self.K) + self.dx / 2, self.floor, div)
        if self.layer is not None:
            c.drawImage(self.layer.makeImageSnapshot(), 0, 0)
        fill = skia.Paint(AntiAlias=True)
        for b in self.balls:
            fill.setColor(color(self.color_of(b.i)))
            c.drawCircle(b.x, b.y, self.br, fill)
        if self.done_at is not None:
            self._draw_curve(c, min(1.0, (self.t - self.done_at) / 0.9))
        text_center(c, str(self.settled), W / 2, self.H * 0.115, W * 0.12)

    def _draw_curve(self, c: skia.Canvas, progress: float) -> None:
        total = sum(self.counts) or 1
        mean = sum(b * n for b, n in enumerate(self.counts)) / total
        sd = math.sqrt(max(0.3, sum((b - mean) ** 2 * n for b, n in enumerate(self.counts)) / total))
        path = skia.Path()
        steps = 120
        last = int(steps * progress)
        for s in range(last + 1):
            b = -0.5 + (self.K + 1) * s / steps
            expected = total * math.exp(-((b - mean) ** 2) / (2 * sd * sd)) / (sd * math.sqrt(2 * math.pi))
            height = expected / self.per_row * self.slot_h + self.br
            x, y = self.bin_x(0) + (b * self.dx), self.floor - height
            if s == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        c.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=self.W * 0.008,
                                    StrokeJoin=skia.Paint.kRound_Join, StrokeCap=skia.Paint.kRound_Cap,
                                    Color=color(WHITE, 0.95)))

    # --- Kalibrierung: Takt so wählen, dass die letzte Kugel genau am Ende landet --------
    @classmethod
    def _simulate(cls, ctx, params) -> "Galton":
        sim = cls(ctx, params, headless=True)
        dt = 1.0 / ctx.fps
        while sim.done_at is None and sim.t < ctx.duration * 2 + 10:
            sim.update(dt)
        return sim

    @classmethod
    def calibrate(cls, ctx, params):
        target = max(3.0, ctx.duration - cls.outro)
        n = max(10, int(params.get("balls", 220)))
        params = {**params, "interval": max(0.02, (target - 2.5) / n)}
        sim = cls._simulate(ctx, params)
        for _ in range(3):
            done = sim.done_at or sim.t
            if abs(done - target) < 0.4:
                break
            flight = done - (n - 1) * params["interval"]
            params["interval"] = max(0.02, (target - flight) / max(1, n - 1))
            sim = cls._simulate(ctx, params)
        # Die Verteilung hängt nicht von der Stapelhöhe ab: so passt der höchste Stapel genau ins Fach
        params["stack_rows"] = math.ceil(max(sim.counts) / sim.per_row)
        return params
