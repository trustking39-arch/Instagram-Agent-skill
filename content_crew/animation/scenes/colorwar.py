"""Farben-Krieg: Bälle in Teamfarben erobern Felder. Wer hat am Ende die meiste Fläche?"""

from __future__ import annotations

import math

import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center

TAU = 2 * math.pi
# Teamfarben müssen sich klar unterscheiden – unabhängig von der Hintergrund-Palette
TEAM_SETS_2 = [
    [(242, 236, 220), (34, 48, 110)],        # Tag gegen Nacht
    [(255, 70, 90), (40, 170, 255)],          # Rot gegen Blau
    [(255, 0, 200), (0, 235, 255)],           # Pink gegen Türkis
    [(255, 205, 0), (130, 70, 255)],          # Gelb gegen Lila
    [(60, 240, 120), (255, 100, 40)],         # Grün gegen Orange
]
TEAM_SETS_4 = [
    [(255, 70, 90), (40, 170, 255), (255, 210, 0), (60, 220, 120)],
    [(0, 235, 255), (255, 0, 200), (255, 236, 0), (140, 90, 255)],
    [(255, 120, 40), (130, 70, 255), (240, 240, 240), (0, 200, 170)],
]
DIRS = [(math.cos(k * math.pi / 4), math.sin(k * math.pi / 4)) for k in range(8)]


class _Ball:
    __slots__ = ("x", "y", "vx", "vy", "team", "trail")

    def __init__(self, x, y, vx, vy, team):
        self.x, self.y, self.vx, self.vy, self.team, self.trail = x, y, vx, vy, team, []


class ColorWars(Scene):
    name = "color_wars"
    substeps = 4
    outro = 2.2

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        self.teams = 4 if int(params.get("teams", 2)) >= 3 else 2
        self.cols = max(8, int(params.get("cols", 26)))
        self.x0, aw = W * 0.05, W * 0.9
        self.s = aw / self.cols
        self.rows = max(8, int(H * 0.6 / self.s) // 2 * 2)
        self.y0 = H * 0.53 - self.rows * self.s / 2
        self.x1, self.y1 = self.x0 + self.cols * self.s, self.y0 + self.rows * self.s
        self.colors = self.fx.choice(TEAM_SETS_2 if self.teams == 2 else TEAM_SETS_4)
        self.grid = [[self._home(r, c) for c in range(self.cols)] for r in range(self.rows)]
        self.counts = [0] * self.teams
        for row in self.grid:
            for team in row:
                self.counts[team] += 1
        self.br = self.s * 0.5
        speed = self.s * 26 * float(params.get("speed", 1.0))
        self.speed = speed
        rng = self.rng
        # Jedes Team hat Phasen der Stärke und Schwäche: die Front schwappt hin und her (Drama!)
        self.waves = [(rng.uniform(5.0, 9.0), rng.uniform(0, TAU)) for _ in range(self.teams)]
        self.balls: list[_Ball] = []
        for team in range(self.teams):
            for _ in range(max(1, int(params.get("balls_per_team", 1)))):
                r, c = self._random_cell(team)
                ang = rng.choice([1, 3, 5, 7]) * math.pi / 4 + rng.uniform(-0.3, 0.3)
                self.balls.append(_Ball(self.x0 + (c + 0.5) * self.s, self.y0 + (r + 0.5) * self.s,
                                        math.cos(ang) * speed, math.sin(ang) * speed, team))
        self.last_note = [-1.0] * self.teams
        self.dirty: list[tuple[int, int]] = []
        self.board = None
        if not headless:
            self.board = skia.Surface.MakeRaster(skia.ImageInfo.Make(
                W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
            self.board.getCanvas().clear(skia.ColorTRANSPARENT)
            for r in range(self.rows):
                for c in range(self.cols):
                    self._paint_cell(r, c)

    def _home(self, r: int, c: int) -> int:
        top = r < self.rows // 2
        if self.teams == 2:
            return 0 if top else 1
        left = c < self.cols // 2
        return (0 if left else 1) if top else (2 if left else 3)

    def _random_cell(self, team: int) -> tuple[int, int]:
        cells = [(r, c) for r in range(1, self.rows - 1) for c in range(1, self.cols - 1)
                 if self.grid[r][c] == team and all(self.grid[r + i][c + j] == team
                                                    for i in (-1, 0, 1) for j in (-1, 0, 1))]
        return self.rng.choice(cells)

    def _paint_cell(self, r: int, c: int) -> None:
        canvas = self.board.getCanvas()
        x, y, s = self.x0 + c * self.s, self.y0 + r * self.s, self.s
        canvas.drawRect(skia.Rect(x, y, x + s, y + s), skia.Paint(Color=color((0, 0, 0)), BlendMode=skia.BlendMode.kClear))
        rgb = mix(self.colors[self.grid[r][c]], (0, 0, 0), 0.28)
        inset = s * 0.07
        canvas.drawRoundRect(skia.Rect(x + inset, y + inset, x + s - inset, y + s - inset), s * 0.2, s * 0.2,
                             skia.Paint(AntiAlias=True, Color=color(rgb)))

    def step(self, h: float) -> None:
        if self.done_at is None and self.t >= self.target:
            self.finish()
        s, br = self.s, self.br
        for b in self.balls:
            period, phase = self.waves[b.team]
            power = math.sin(TAU * self.t / period + phase)
            splash = 3 if power > 0.8 else 2 if power > 0.5 else 1 if power > 0.2 else 0  # Stärkephase: große Bissen
            want = self.speed * (1 + 0.35 * power)
            have = math.hypot(b.vx, b.vy) or 1.0
            b.vx, b.vy = b.vx * want / have, b.vy * want / have
            b.x += b.vx * h
            b.y += b.vy * h
            if b.x - br < self.x0:
                b.x, b.vx = self.x0 + br, abs(b.vx)
            elif b.x + br > self.x1:
                b.x, b.vx = self.x1 - br, -abs(b.vx)
            if b.y - br < self.y0:
                b.y, b.vy = self.y0 + br, abs(b.vy)
            elif b.y + br > self.y1:
                b.y, b.vy = self.y1 - br, -abs(b.vy)
            flipped = False
            for ca, sa in DIRS:
                c = int((b.x + ca * br - self.x0) // s)
                r = int((b.y + sa * br - self.y0) // s)
                if not (0 <= c < self.cols and 0 <= r < self.rows):
                    continue
                old = self.grid[r][c]
                if old == b.team:
                    continue
                self.grid[r][c] = b.team
                self.counts[old] -= 1
                self.counts[b.team] += 1
                flipped = True
                if not self.headless:
                    self.dirty.append((r, c))
                if splash:
                    self._splash(r, c, b.team, splash)
                if abs(ca) > abs(sa):
                    if b.vx * ca > 0:
                        b.vx = -b.vx
                elif b.vy * sa > 0:
                    b.vy = -b.vy
            if flipped:
                a = self.rng.uniform(-0.04, 0.04)
                b.vx, b.vy = b.vx * math.cos(a) - b.vy * math.sin(a), b.vx * math.sin(a) + b.vy * math.cos(a)
                if self.t - self.last_note[b.team] > 0.035 * self.teams:
                    self.last_note[b.team] = self.t
                    self.play(self.music.degree(self._degree(b)), 0.32, b.x)

    def _splash(self, r0: int, c0: int, team: int, k: int) -> None:
        """Mehrere Felder auf einmal erobern (nur gegnerische, ohne Abprallen)."""
        gained = 0
        for r in range(max(0, r0 - k), min(self.rows, r0 + k + 1)):
            for c in range(max(0, c0 - k), min(self.cols, c0 + k + 1)):
                if (r - r0) ** 2 + (c - c0) ** 2 > k * k + 0.5 or self.grid[r][c] == team:
                    continue
                self.counts[self.grid[r][c]] -= 1
                self.counts[team] += 1
                self.grid[r][c] = team
                gained += 1
                if not self.headless:
                    self.dirty.append((r, c))
        if gained >= 3 and not self.headless:
            x, y = self.x0 + (c0 + 0.5) * self.s, self.y0 + (r0 + 0.5) * self.s
            self.particles.burst([x] * 10, [y] * 10, self.colors[team], speed=self.W * 0.25, size=self.s * 0.3,
                                 life=0.6)

    def _degree(self, b: _Ball) -> int:
        span = len(self.music.scale) * 2
        frac = (b.y - self.y0) / max(1.0, self.y1 - self.y0)
        return int((1 - frac) * span) + b.team % 2 * 2

    def leader(self) -> int:
        return max(range(self.teams), key=lambda k: self.counts[k])

    def on_finish(self) -> None:
        if self.headless:
            return
        win = self.leader()
        self.flash = 0.45
        for b in self.balls:
            if b.team == win:
                self.particles.burst([b.x] * 70, [b.y] * 70, self.colors[win], speed=self.W * 0.8,
                                     size=self.W * 0.011, life=1.6)
        self.play(0, 0.8, kind="boom", accent=True)
        for p in self.music.chord():
            self.play(p, 0.45, accent=True)

    def frame(self, dt: float) -> None:
        if self.board is not None:
            for r, c in self.dirty:
                self._paint_cell(r, c)
        self.dirty = []
        for b in self.balls:
            b.trail.append((b.x, b.y))
            del b.trail[:-8]

    def draw(self, c: skia.Canvas) -> None:
        W, H = self.W, self.H
        if self.board is not None:
            c.drawImage(self.board.makeImageSnapshot(), 0, 0)
        frame = skia.Rect(self.x0 - 6, self.y0 - 6, self.x1 + 6, self.y1 + 6)
        c.drawRoundRect(frame, 14, 14, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                                  StrokeWidth=3, Color=color(WHITE, 0.3)))
        fill = skia.Paint(AntiAlias=True)
        for b in self.balls:
            rgb = mix(self.colors[b.team], WHITE, 0.45)
            n = len(b.trail)
            for k, (x, y) in enumerate(b.trail):
                fill.setColor(color(rgb, 0.3 * (k + 1) / n))
                c.drawCircle(x, y, self.br * 0.8, fill)
            fill.setColor(color(WHITE))
            c.drawCircle(b.x, b.y, self.br * 0.95, fill)
            c.drawCircle(b.x, b.y, self.br * 0.95, skia.Paint(
                AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(2.0, self.br * 0.3),
                Color=color(self.colors[b.team])))
        self.particles.draw(c)

        # Punktestand: nur Zahlen in Teamfarbe und ein Balken
        total = sum(self.counts)
        win = self.leader() if self.done_at is not None else -1
        size = W * (0.11 if self.teams == 2 else 0.075)
        for k in range(self.teams):
            x = W * ((0.27 + 0.46 * k) if self.teams == 2 else (0.14 + 0.24 * k))
            boost = 1.25 if k == win else 1.0
            text_center(c, str(self.counts[k]), x, H * 0.115, size * boost, mix(self.colors[k], WHITE, 0.2))
        bar_y, bar_h = H * 0.165, W * 0.018
        x = self.x0
        for k in range(self.teams):
            w = (self.x1 - self.x0) * self.counts[k] / total
            c.drawRect(skia.Rect(x, bar_y, x + w, bar_y + bar_h), skia.Paint(Color=color(self.colors[k])))
            x += w
