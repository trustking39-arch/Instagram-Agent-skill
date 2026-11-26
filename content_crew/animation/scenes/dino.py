"""Zeitreise: Ein leuchtendes Skelett verbringt 24 Stunden bei den Dinosauriern (Silhouetten-Stil).

Die Welt besteht aus Schattenrissen vor einem Himmel, der durch alle Tageszeiten läuft. Nur das
Skelett leuchtet. Oben stehen die Stunde und ein Stichwort – keine Sätze.
"""

from __future__ import annotations

import math

import numpy as np
import skia

from content_crew.animation.engine import WHITE, Scene, color, mix, text_center

TAU = 2 * math.pi
BLACK = (0, 0, 0)

# Himmel je Stunde: (Stunde, oben, unten)
SKY = [
    (0.0, (44, 30, 86), (250, 150, 120)),
    (2.5, (58, 132, 214), (250, 214, 170)),
    (5.5, (34, 146, 236), (196, 232, 250)),
    (10.5, (52, 120, 200), (244, 204, 150)),
    (12.8, (34, 40, 58), (84, 86, 98)),
    (15.2, (40, 44, 64), (110, 96, 104)),
    (16.2, (72, 48, 112), (252, 120, 60)),
    (18.2, (22, 20, 60), (126, 52, 84)),
    (19.5, (4, 6, 20), (20, 20, 46)),
    (22.6, (12, 10, 34), (42, 30, 64)),
    (23.6, (52, 40, 104), (250, 150, 124)),
    (25.0, (70, 110, 190), (252, 196, 152)),
]

BEATS = [  # (ab Stunde, Stichwort)
    (0.0, "ANKUNFT"), (1.0, "ERSTER DINO"), (4.0, "HITZE"), (6.5, "T-REX!"), (10.0, "VERSTECKT"),
    (12.5, "GEWITTER"), (15.5, "DINO-HERDE"), (18.5, "NACHT"), (22.5, "ZURÜCK"),
]


def _lerp(a, b, f):
    return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))


def sky_at(hour: float):
    for (h0, t0, b0), (h1, t1, b1) in zip(SKY, SKY[1:]):
        if h0 <= hour <= h1:
            f = (hour - h0) / (h1 - h0)
            f = f * f * (3 - 2 * f)
            return _lerp(t0, t1, f), _lerp(b0, b1, f)
    return SKY[-1][1], SKY[-1][2]


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _phase(hour: float, a: float, b: float) -> float:
    return _smooth((hour - a) / (b - a))


class DinoTrip(Scene):
    name = "dino_trip"
    substeps = 1
    outro = 2.0

    def __init__(self, ctx, params, headless=False):
        super().__init__(ctx, params, headless)
        W, H = self.W, self.H
        self.ground = H * 0.76
        self.S = H * 0.23  # Größe des Skeletts
        self.scroll = 0.0
        self.walk_phase = 0.0
        self.trex_phase = 0.0
        self.beat = 0.0
        self.beat_len = 60 / 100
        self.fired: set[str] = set()
        self.herd = max(2, min(4, int(params.get("dinos", 3))))
        rng = self.rng
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H * 0.55), rng.uniform(1, 3) * W / 1080,
                       rng.uniform(0, TAU)) for _ in range(140)]
        self.drops = np.array([[rng.uniform(0, W * 1.3), rng.uniform(-H, H)] for _ in range(260)])
        self.eyes = [(W * 0.16, self.ground - H * 0.05, 0.0), (W * 0.86, self.ground - H * 0.08, 1.7),
                     (W * 0.62, self.ground - H * 0.04, 3.1)]
        self.layers = None if headless else self._make_layers()

    # --- Zeit ------------------------------------------------------------------
    def hour(self, t: float | None = None) -> float:
        t = self.t if t is None else t
        return 24.0 * t / self.target

    def at_hour(self, h: float) -> bool:
        """Einmal-Ereignis: True genau beim ersten Bild nach Stunde h."""
        key = f"{h:.2f}"
        if key not in self.fired and self.hour() >= h:
            self.fired.add(key)
            return True
        return False

    # --- Hintergrund-Ebenen (einmal vorgezeichnet, dann nur verschoben und eingefärbt) ---
    def _layer(self, top: float, bottom: float) -> tuple[skia.Surface, float]:
        surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(
            int(self.W * 2), int(bottom - top), skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
        surf.getCanvas().clear(skia.ColorTRANSPARENT)
        surf.getCanvas().translate(0, -top)
        return surf, top

    def _make_layers(self) -> dict:
        W, H, g = self.W, self.H, self.ground
        rng = self.fx
        fill = skia.Paint(AntiAlias=True, Color=color(WHITE))
        layers = {}

        far, top = self._layer(H * 0.3, g + 4)
        c = far.getCanvas()
        path = skia.Path()
        path.moveTo(0, g)
        x = 0.0
        while x < 2 * W:
            path.lineTo(x, g - rng.uniform(0.06, 0.15) * H)
            x += rng.uniform(0.08, 0.16) * W
        path.lineTo(2 * W, g - 0.1 * H)
        path.lineTo(2 * W, g)
        path.close()
        c.drawPath(path, fill)
        self.volcano_x = W * 0.62
        vol = skia.Path()
        vol.moveTo(self.volcano_x - W * 0.42, g)
        vol.cubicTo(self.volcano_x - W * 0.2, g - H * 0.12, self.volcano_x - W * 0.09, g - H * 0.3,
                    self.volcano_x - W * 0.05, g - H * 0.33)
        vol.lineTo(self.volcano_x + W * 0.05, g - H * 0.33)
        vol.cubicTo(self.volcano_x + W * 0.09, g - H * 0.3, self.volcano_x + W * 0.2, g - H * 0.12,
                    self.volcano_x + W * 0.42, g)
        vol.close()
        c.drawPath(vol, fill)
        self.volcano_top = g - H * 0.33
        layers["far"] = (far.makeImageSnapshot(), top)

        mid, top = self._layer(H * 0.3, g + 4)
        c = mid.getCanvas()
        stroke = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap,
                            Color=color(WHITE))
        x = rng.uniform(0, 0.1) * W
        while x < 2 * W - 0.05 * W:
            kind = rng.random()
            if kind < 0.45:  # Palme
                hgt = rng.uniform(0.2, 0.33) * H
                lean = rng.uniform(-0.08, 0.08) * W
                tx, ty = x + lean, g - hgt
                stroke.setStrokeWidth(W * 0.012)
                trunk = skia.Path()
                trunk.moveTo(x, g)
                trunk.quadTo(x + lean * 0.2, g - hgt * 0.6, tx, ty)
                c.drawPath(trunk, stroke)
                stroke.setStrokeWidth(W * 0.01)
                for k in range(8):
                    a = -math.pi / 2 + (k - 3.5) * 0.42
                    ln = rng.uniform(0.08, 0.12) * W
                    ex, ey = tx + math.cos(a) * ln * 1.3, ty + math.sin(a) * ln * 0.6 + ln * 0.55
                    frond = skia.Path()
                    frond.moveTo(tx, ty)
                    frond.quadTo(tx + math.cos(a) * ln, ty + math.sin(a) * ln * 0.9, ex, ey)
                    c.drawPath(frond, stroke)
            elif kind < 0.75:  # Baumfarn
                hgt = rng.uniform(0.1, 0.18) * H
                stroke.setStrokeWidth(W * 0.009)
                c.drawLine(x, g, x, g - hgt, stroke)
                stroke.setStrokeWidth(W * 0.007)
                for k in range(6):
                    a = -math.pi / 2 + (k - 2.5) * 0.55
                    ln = rng.uniform(0.05, 0.08) * W
                    frond = skia.Path()
                    frond.moveTo(x, g - hgt)
                    frond.quadTo(x + math.cos(a) * ln, g - hgt + math.sin(a) * ln,
                                 x + math.cos(a) * ln * 1.5, g - hgt + ln * 0.35)
                    c.drawPath(frond, stroke)
            else:  # Busch
                for k in range(5):
                    c.drawCircle(x + rng.uniform(-0.05, 0.05) * W, g - rng.uniform(0.0, 0.03) * H,
                                 rng.uniform(0.03, 0.06) * W, fill)
            x += rng.uniform(0.1, 0.22) * W
        layers["mid"] = (mid.makeImageSnapshot(), top)

        near, top = self._layer(g - H * 0.04, H)
        c = near.getCanvas()
        edge = skia.Path()
        edge.moveTo(0, H)
        edge.lineTo(0, g)
        x = 0.0
        while x <= 2 * W:
            edge.lineTo(x, g + rng.uniform(-0.004, 0.004) * H)
            x += 0.02 * W
        edge.lineTo(2 * W, H)
        edge.close()
        c.drawPath(edge, fill)
        stroke.setStrokeWidth(W * 0.004)
        for _ in range(160):  # Grasbüschel
            gx = rng.uniform(0, 2 * W)
            for k in range(3):
                c.drawLine(gx, g + 2, gx + (k - 1) * W * 0.008, g - rng.uniform(0.01, 0.025) * H, stroke)
        layers["near"] = (near.makeImageSnapshot(), top)
        return layers

    def _blit(self, c: skia.Canvas, name: str, offset: float, rgb) -> None:
        img, top = self.layers[name]
        paint = skia.Paint(ColorFilter=skia.ColorFilters.Blend(color(rgb), skia.BlendMode.kSrcIn))
        width = img.width()
        x0 = -(offset % width)
        for x in (x0, x0 + width):
            if x < self.W and x + width > 0:
                c.drawImage(img, x, top, skia.SamplingOptions(skia.FilterMode.kLinear), paint)

    # --- Ablauf ------------------------------------------------------------------
    def speed(self, hour: float) -> float:
        """Wie schnell die Welt vorbeizieht (px/s): Gehen, Rennen, Stehen."""
        W = self.W
        if 1.0 <= hour < 4.0:
            return W * 0.11
        if 4.0 <= hour < 6.3:
            return W * 0.06
        if 7.4 <= hour < 10.0:
            return -W * 0.42  # Flucht nach links
        if 23.0 <= hour < 23.6:
            return 0.0
        return 0.0

    def step(self, h: float) -> None:
        hour = self.hour()
        v = self.speed(hour)
        self.scroll += v * h
        moving = abs(v) > 1
        self.walk_phase += h * (9.5 if abs(v) > self.W * 0.3 else 5.2 if moving else 0.0)
        if 6.5 <= hour < 12.0:
            self.trex_phase += h * (7.0 if 7.4 <= hour < 10.0 else 3.2)
        if self.done_at is None and hour >= 24.6:
            self.finish()
        self._sounds(hour)

    def _sounds(self, hour: float) -> None:
        if self.headless:
            return
        W = self.W
        if self.at_hour(0.02):
            self.play(0, 0.7, W * 0.35, kind="whoosh", accent=True)
        if self.at_hour(7.0):
            self.play(0, 1.0, W * 0.75, kind="roar", accent=True)
            self.shake = 1.0
        if self.at_hour(11.0):
            self.play(0, 0.55, W * 0.8, kind="roar", accent=True)
        for hh in (13.0, 14.3, 15.1):
            if self.at_hour(hh):
                self.play(0, 0.9, W * 0.5, kind="thunder", accent=True)
                self.flash = 1.0
        if self.at_hour(13.7):
            self.play(0, 0.8, W * 0.6, kind="boom", accent=True)
            self.play(0, 0.4, W * 0.6, kind="burst", accent=True)
        if self.at_hour(22.6):
            self.play(0, 0.7, W * 0.7, kind="whoosh", accent=True)
        if self.at_hour(23.9):
            self.play(0, 0.8, W * 0.7, kind="whoosh", accent=True)
        # Musik: Puls, Hi-Hat, Melodie – je nach Szene
        if self.t >= self.beat:
            n = int(round(self.beat / self.beat_len))
            self.beat += self.beat_len * (0.5 if 7.4 <= hour < 10.0 else 1.0)
            night = 18.5 <= hour < 22.5
            if not night and hour >= 1.0:
                self.play(0, 0.22 if hour < 7.4 or hour >= 10 else 0.32, kind="boom")
                self.play(self.music.degree(14 + n % 3), 0.05, kind="tick")
            if night:
                if n % 4 == 0:
                    self.play(self.music.degree(self.fx.randrange(4, 9)), 0.14)
                if self.fx.random() < 0.5:
                    self.play(self.music.degree(16), 0.03, self.fx.uniform(0, W), kind="tick")
            elif n % 2 == 0 or 7.4 <= hour < 10.0:
                self.play(self.music.next() + (12 if 7.4 <= hour < 10.0 else 0), 0.2)
        if 6.5 <= hour < 12.0 and int(self.trex_phase / math.pi) != int((self.trex_phase - 0.12) / math.pi):
            self.play(0, 0.18, self.trex_x(hour), kind="boom")  # Schritte des T-Rex

    def frame(self, dt: float) -> None:
        hour = self.hour()
        W, H = self.W, self.H
        if 13.6 <= hour < 15.5 and self.fx.random() < 0.6:  # Vulkan spuckt Lava
            vx = self._volcano_screen_x()
            if -W * 0.2 < vx < W * 1.2:
                self.particles.burst([vx] * 4, [self.volcano_top] * 4, (255, 120, 30), speed=W * 0.25,
                                     size=W * 0.009, life=1.4, vy0=-W * 0.45)
        if 19.0 <= hour < 22.6 and self.fx.random() < 0.5:  # Funken vom Lagerfeuer
            fx, fy = self._fire_pos()
            self.particles.burst([fx], [fy - H * 0.02], (255, 170, 60), speed=W * 0.05, size=W * 0.005,
                                 life=1.2, vy0=-W * 0.22)
        if 12.6 <= hour < 15.6:  # Regen
            self.drops[:, 0] -= W * 0.25 * dt
            self.drops[:, 1] += H * 1.4 * dt
            wrap = self.drops[:, 1] > self.ground
            self.drops[wrap, 1] -= self.ground + H * 0.2
            self.drops[self.drops[:, 0] < -20, 0] += W * 1.3

    # --- Positionen ----------------------------------------------------------------
    def _volcano_screen_x(self) -> float:
        width = self.W * 2
        x = self.volcano_x - (self.scroll * 0.15) % width
        return x if x > -self.W * 0.5 else x + width

    def _fire_pos(self) -> tuple[float, float]:
        return self.W * 0.6, self.ground

    def trex_x(self, hour: float) -> float:
        W = self.W
        if hour < 6.5:
            return W * 1.6
        if hour < 7.0:
            return W * (1.5 - 0.72 * _phase(hour, 6.5, 7.0))
        if hour < 7.4:
            return W * 0.78
        if hour < 10.0:
            return W * (0.78 - 0.08 * math.sin((hour - 7.4) * 2.2))
        if hour < 11.5:
            return W * 0.8
        return W * (0.8 + 1.0 * _phase(hour, 11.5, 12.5))

    # --- Zeichnen ------------------------------------------------------------------
    def draw(self, c: skia.Canvas) -> None:
        W, H, g = self.W, self.H, self.ground
        hour = self.hour()
        top, bottom = sky_at(hour)
        c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(0, g)], [color(top), color(bottom)])))
        night = _phase(hour, 18.6, 19.6) * (1 - _phase(hour, 22.8, 23.6))
        self._draw_sky_objects(c, hour, night)

        far = mix(bottom, BLACK, 0.42)
        midc = mix(bottom, BLACK, 0.7)
        nearc = mix(bottom, BLACK, 0.9)
        self._blit(c, "far", self.scroll * 0.15, far)
        if 13.6 <= hour < 16.0:  # glühender Krater
            vx = self._volcano_screen_x()
            glow = 1 - _phase(hour, 15.3, 16.0)
            c.drawCircle(vx, self.volcano_top + H * 0.01, W * 0.12, skia.Paint(
                AntiAlias=True, Shader=skia.GradientShader.MakeRadial(
                    skia.Point(vx, self.volcano_top), W * 0.12,
                    [color((255, 110, 30), 0.85 * glow), color((255, 60, 0), 0.0)])))
        self._draw_background_dinos(c, hour, mix(bottom, BLACK, 0.55))
        self._blit(c, "mid", self.scroll * 0.45, midc)
        self._draw_herd(c, hour, mix(bottom, BLACK, 0.86))
        self._draw_eyes(c, hour, night)
        self._draw_portal(c, hour)
        self._draw_fire(c, hour)
        self._draw_skeleton_scene(c, hour)
        self._draw_trex(c, hour, nearc)
        self._blit(c, "near", self.scroll, nearc)
        if 10.0 <= hour < 12.6:  # Felsen als Versteck
            rock = skia.Path()
            rx = W * 0.3
            rock.moveTo(rx - W * 0.2, g + 6)
            rock.cubicTo(rx - W * 0.2, g - H * 0.1, rx - W * 0.05, g - H * 0.14, rx + W * 0.06, g - H * 0.12)
            rock.cubicTo(rx + W * 0.16, g - H * 0.1, rx + W * 0.2, g - H * 0.04, rx + W * 0.2, g + 6)
            rock.close()
            alpha = _phase(hour, 10.0, 10.3) * (1 - _phase(hour, 12.3, 12.6))
            c.drawPath(rock, skia.Paint(AntiAlias=True, Color=color(nearc, alpha)))
        if 12.6 <= hour < 15.6:
            self._draw_rain(c, hour)
        self.particles.draw(c)
        self._draw_foreground(c, mix(bottom, BLACK, 0.95))
        self._draw_text(c, hour)

    def _draw_foreground(self, c: skia.Canvas, rgb) -> None:
        W, H = self.W, self.H
        paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap,
                           StrokeWidth=W * 0.022, Color=color(rgb))
        sway = math.sin(self.t * 0.9) * W * 0.01
        for bx, side in ((W * 0.02, 1), (W * 0.98, -1)):
            for k in range(5):
                a = -math.pi / 2 + side * (0.25 + k * 0.28)
                ln = W * (0.42 - k * 0.05)
                leaf = skia.Path()
                leaf.moveTo(bx, H * 1.02)
                ex = bx + math.cos(a) * ln + sway
                ey = H * 1.02 + math.sin(a) * ln * 0.75 + ln * 0.25
                leaf.quadTo(bx + math.cos(a) * ln * 0.6, H * 1.02 + math.sin(a) * ln * 0.9, ex, ey)
                c.drawPath(leaf, paint)

    def _draw_sky_objects(self, c: skia.Canvas, hour: float, night: float) -> None:
        W, H, g = self.W, self.H, self.ground
        if night > 0:
            dot = skia.Paint(AntiAlias=True)
            for x, y, r, ph in self.stars:
                dot.setColor(color(WHITE, night * (0.5 + 0.5 * math.sin(self.t * 2 + ph))))
                c.drawCircle(x, y, r, dot)
            c.drawCircle(W * 0.78, H * 0.2, W * 0.05, skia.Paint(AntiAlias=True, Color=color((240, 236, 220), night)))
        if 0 <= hour < 18.8 and not (12.6 <= hour < 15.6):  # Sonne auf ihrer Bahn
            f = hour / 18.8
            sx, sy = W * (0.1 + 0.8 * f), g - math.sin(math.pi * f) * H * 0.36 - H * 0.06
            sun = (255, 236, 170) if 3 < hour < 14 else (255, 170, 90)
            c.drawCircle(sx, sy, W * 0.07, skia.Paint(AntiAlias=True, Color=color(sun, 0.95)))
        if 23.2 <= hour:
            f = _phase(hour, 23.2, 25)
            c.drawCircle(W * 0.15, g - f * H * 0.1, W * 0.07, skia.Paint(AntiAlias=True, Color=color((255, 200, 140))))

    def _draw_background_dinos(self, c: skia.Canvas, hour: float, rgb) -> None:
        W, H, g = self.W, self.H, self.ground
        if 0.8 <= hour < 6.5:  # Brachiosaurus zieht langsam durchs Bild
            x = W * (1.35 - 0.85 * _phase(hour, 0.8, 6.3))
            self.brachio(c, x, g - H * 0.01, H * 0.12, -1, mix(rgb, BLACK, 0.15), self.t * 2.2)
        if 1.5 <= hour < 4.2:  # Flugsaurier
            for k, (dx, dy) in enumerate(((0.0, 0.0), (0.12, 0.04), (0.22, -0.02))):
                f = (hour - 1.5) / 2.7
                x = W * (1.15 - 1.4 * f + dx)
                y = H * (0.2 + dy) + math.sin(self.t * 1.5 + k) * H * 0.01
                self.ptero(c, x, y, W * 0.06, rgb, self.t * 7 + k)

    def _draw_herd(self, c: skia.Canvas, hour: float, rgb) -> None:
        if not 15.4 <= hour < 18.8:
            return
        W, g = self.W, self.ground
        f = (hour - 15.4) / 3.4
        for k in range(self.herd):
            x = W * (1.3 - 1.9 * f) + k * W * 0.32
            self.trike(c, x, g + 2, W * 0.16 * (1 - 0.15 * (k % 2)), -1, rgb, self.t * 5 + k)

    def _draw_eyes(self, c: skia.Canvas, hour: float, night: float) -> None:
        if not 19.8 <= hour < 22.8:
            return
        for k, (x, y, ph) in enumerate(self.eyes):
            if hour < 20.0 + k * 0.7:
                continue
            blink = 0.0 if math.sin(self.t * 1.3 + ph) > 0.93 else 1.0
            for dx in (-1, 1):
                c.drawCircle(x + dx * self.W * 0.012, y, self.W * 0.006,
                             skia.Paint(AntiAlias=True, Color=color((255, 220, 60), night * blink)))

    def _draw_portal(self, c: skia.Canvas, hour: float) -> None:
        W, H, g = self.W, self.H, self.ground
        if hour < 1.4:
            px, size = W * 0.3, _phase(hour, 0.0, 0.25) * (1 - _phase(hour, 1.0, 1.4))
        elif hour >= 22.6:
            px, size = W * 0.74, _phase(hour, 22.6, 23.0) * (1 - _phase(hour, 24.15, 24.5))
        else:
            return
        if size <= 0.01:
            return
        py = g - H * 0.11
        r = H * 0.1 * size
        for k, (rgb, w, speed) in enumerate((((0, 230, 255), 0.012, 1.5), ((180, 80, 255), 0.008, -2.2),
                                            ((255, 255, 255), 0.004, 3.0))):
            rr = r * (1 - k * 0.14)
            paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=W * w,
                               Color=color(rgb, 0.95),
                               PathEffect=skia.DashPathEffect.Make([rr * 0.5, rr * 0.18], self.t * 300 * speed))
            c.drawOval(skia.Rect(px - rr * 0.62, py - rr, px + rr * 0.62, py + rr), paint)
        c.drawOval(skia.Rect(px - r * 0.5, py - r * 0.85, px + r * 0.5, py + r * 0.85),
                   skia.Paint(AntiAlias=True, Color=color((150, 230, 255), 0.35 * size)))

    def _draw_fire(self, c: skia.Canvas, hour: float) -> None:
        if not 18.8 <= hour < 22.8:
            return
        W, H = self.W, self.H
        fx, fy = self._fire_pos()
        on = _phase(hour, 18.8, 19.2) * (1 - _phase(hour, 22.4, 22.8))
        c.drawCircle(fx, fy - H * 0.02, W * 0.3, skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeRadial(
            skia.Point(fx, fy - H * 0.02), W * 0.3, [color((255, 130, 40), 0.35 * on), color((255, 80, 0), 0.0)])))
        for k, (rgb, s) in enumerate((((255, 70, 20), 1.0), ((255, 150, 40), 0.7), ((255, 230, 120), 0.4))):
            jitter = self.fx.uniform(0.85, 1.15)
            w, hgt = W * 0.035 * s * on, H * 0.05 * s * jitter * on
            flame = skia.Path()
            flame.moveTo(fx - w, fy)
            flame.cubicTo(fx - w, fy - hgt * 0.5, fx - w * 0.2, fy - hgt * 0.7, fx + self.fx.uniform(-w, w) * 0.3, fy - hgt)
            flame.cubicTo(fx + w * 0.2, fy - hgt * 0.7, fx + w, fy - hgt * 0.5, fx + w, fy)
            flame.close()
            c.drawPath(flame, skia.Paint(AntiAlias=True, Color=color(rgb, 0.95)))

    def _draw_rain(self, c: skia.Canvas, hour: float) -> None:
        a = _phase(hour, 12.6, 13.0) * (1 - _phase(hour, 15.2, 15.6))
        paint = skia.Paint(AntiAlias=True, StrokeWidth=max(1.5, self.W * 0.002), Color=color((200, 210, 230), 0.45 * a))
        dx, dy = -self.W * 0.012, self.H * 0.03
        for x, y in self.drops:
            if 0 < y < self.ground:
                c.drawLine(float(x), float(y), float(x + dx), float(y + dy), paint)
        if self.flash > 0.5:  # Blitz
            bolt = skia.Path()
            x, y = self.W * 0.42, 0.0
            bolt.moveTo(x, y)
            rng = np.random.default_rng(int(hour * 10))
            while y < self.H * 0.55:
                x += rng.uniform(-0.05, 0.05) * self.W
                y += rng.uniform(0.04, 0.07) * self.H
                bolt.lineTo(x, y)
            c.drawPath(bolt, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=self.W * 0.006,
                                        Color=color((235, 240, 255), self.flash)))

    def _draw_text(self, c: skia.Canvas, hour: float) -> None:
        W, H = self.W, self.H
        if self.t < 2.4:
            a = 1 - _phase(self.t, 1.8, 2.4)
            text_center(c, "24 STUNDEN", W / 2, H * 0.12, W * 0.12, alpha=a, shadow=True)
            text_center(c, "BEI DEN DINOS", W / 2, H * 0.19, W * 0.09, (255, 220, 150), a, shadow=True)
            return
        shown = min(24, int(hour))
        label = [t for h0, t in BEATS if hour >= h0][-1]
        a = _phase(self.t, 2.4, 2.8)
        text_center(c, f"STUNDE {shown}", W / 2, H * 0.11, W * 0.11, alpha=a, shadow=True)
        text_center(c, label, W / 2, H * 0.17, W * 0.065, (255, 220, 150), a, shadow=True)
        bar = skia.Rect(W * 0.2, H * 0.205, W * 0.2 + W * 0.6 * min(1.0, hour / 24), H * 0.205 + W * 0.012)
        c.drawRoundRect(skia.Rect(W * 0.2, H * 0.205, W * 0.8, H * 0.205 + W * 0.012), 8, 8,
                        skia.Paint(AntiAlias=True, Color=color(WHITE, 0.25 * a)))
        c.drawRoundRect(bar, 8, 8, skia.Paint(AntiAlias=True, Color=color((255, 200, 90), a)))

    # --- Skelett --------------------------------------------------------------------
    def _draw_skeleton_scene(self, c: skia.Canvas, hour: float) -> None:
        W, H, g = self.W, self.H, self.ground
        x, facing, pose, scale, rot = W * 0.42, 1, "stand", 1.0, 0.0
        jaw, shake = 0.0, 0.0
        if hour < 1.2:  # aus dem Portal
            x = W * (0.3 + 0.12 * _phase(hour, 0.3, 1.2))
            scale = _phase(hour, 0.15, 0.6)
            pose = "walk" if hour > 0.6 else "stand"
        elif hour < 6.5:
            pose = "walk"
        elif hour < 7.4:
            jaw = _phase(hour, 6.6, 6.9) * 0.6
            shake = 1.0 if hour > 6.9 else 0.0
        elif hour < 10.0:
            pose, facing, x = "run", -1, W * 0.4
            jaw = 0.5
        elif hour < 12.4:
            pose, x = "crouch", W * 0.27
        elif hour < 15.6:
            shake = 0.4
        elif hour < 18.8:
            pose = "stand"
        elif hour < 22.7:
            pose, x, rot = "sleep", W * 0.42, -math.pi / 2
        else:
            p = _phase(hour, 23.0, 23.6)
            x = W * (0.42 + 0.3 * p)
            pose = "walk" if 23.0 <= hour < 23.6 else "stand"
            scale = 1 - _phase(hour, 23.6, 23.9)
        if scale <= 0.01:
            self._draw_baby(c, hour)
            return
        if shake:
            x += self.fx.uniform(-1, 1) * W * 0.004 * shake
        self.skeleton(c, x, g, self.S * scale, facing, pose, jaw, rot)
        if pose == "sleep":
            for k in range(3):
                ph = (self.t * 0.5 + k / 3) % 1
                text_center(c, "Z", x + W * 0.05 + ph * W * 0.08, g - H * 0.08 - ph * H * 0.08, W * (0.04 + 0.03 * ph),
                            alpha=1 - ph)
        self._draw_baby(c, hour)

    def _draw_baby(self, c: skia.Canvas, hour: float) -> None:
        """Ende: ein Baby-T-Rex springt hinterher ins Portal."""
        if not 23.7 <= hour < 24.2:
            return
        W, g = self.W, self.ground
        p = _phase(hour, 23.7, 24.15)
        x = W * (0.05 + 0.69 * p)
        size = W * 0.12 * (1 - _phase(hour, 24.0, 24.15))
        hop = -abs(math.sin(p * 10)) * self.H * 0.02
        if size > 1:
            self.trex(c, x, g + hop, size, 1, (20, 16, 22), self.t * 14, 0.3)

    def skeleton(self, c: skia.Canvas, x: float, ground: float, S: float, facing: int, pose: str,
                 jaw: float = 0.0, rot: float = 0.0) -> None:
        ph = self.walk_phase
        leg, knee, arm, elbow, lean, bob, hip_h = 0.0, 0.05, 0.08, 0.25, 0.0, 0.0, 0.48
        swing = math.sin(ph)
        if pose == "walk":
            leg, knee, arm, elbow, bob = 0.42 * swing, 0.35, 0.35 * swing, 0.35, -abs(math.cos(ph)) * 0.015
        elif pose == "run":
            leg, knee, arm, elbow, lean, bob = 0.85 * swing, 0.9, 0.9 * swing, 1.3, 0.28, -abs(math.cos(ph)) * 0.04
        elif pose == "crouch":
            hip_h, lean = 0.28, 0.55
        c.save()
        if rot:  # liegend: um die Hüfte drehen und auf den Boden legen
            c.translate(x, ground - S * 0.05)
            c.rotate(math.degrees(rot))
            c.translate(-x, -(ground - S * (hip_h - bob)))
        bone = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=S * 0.034,
                          StrokeCap=skia.Paint.kRound_Cap, Color=color(WHITE))
        joint = skia.Paint(AntiAlias=True, Color=color(WHITE))
        dark = skia.Paint(AntiAlias=True, Color=color((18, 16, 26)))
        hx, hy = x, ground - S * (hip_h - bob)

        def limb(sx, sy, angle, length):
            return sx + facing * math.sin(angle) * length, sy + math.cos(angle) * length

        # Beine (erst das hintere, dann das vordere)
        for sign in (-1, 1):
            if pose == "crouch":
                a1, a2 = 1.25, -0.95
            else:
                a1 = leg * sign
                a2 = a1 - knee * (0.5 + 0.5 * max(0.0, -swing * sign)) if pose != "stand" else a1 - 0.05
            kx, ky = limb(hx, hy, a1, S * 0.24)
            ax, ay = limb(kx, ky, a2, S * 0.23)
            ax2, ay2 = ax, min(ay, ground - S * 0.02)
            bone.setAlphaf(0.75 if sign < 0 else 1.0)
            c.drawLine(hx, hy, kx, ky, bone)
            c.drawLine(kx, ky, ax2, ay2, bone)
            c.drawLine(ax2, ay2, ax2 + facing * S * 0.08, ay2 + S * 0.015, bone)
            c.drawCircle(kx, ky, S * 0.022, joint)
        bone.setAlphaf(1.0)
        # Wirbelsäule und Rippen
        nx, ny = hx + facing * math.sin(lean) * S * 0.42, hy - math.cos(lean) * S * 0.42
        for k in range(9):
            f = k / 8
            c.drawCircle(hx + (nx - hx) * f, hy + (ny - hy) * f, S * 0.018, joint)
        rib = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=S * 0.022,
                         StrokeCap=skia.Paint.kRound_Cap, Color=color(WHITE))
        for k in range(4):
            f = 0.45 + k * 0.13
            sx, sy = hx + (nx - hx) * f, hy + (ny - hy) * f
            path = skia.Path()
            path.moveTo(sx, sy)
            path.quadTo(sx + facing * S * 0.13, sy - S * 0.01, sx + facing * S * 0.11, sy + S * 0.06)
            c.drawPath(path, rib)
        c.drawOval(skia.Rect(hx - S * 0.07, hy - S * 0.035, hx + S * 0.07, hy + S * 0.035), joint)
        # Arme
        sx, sy = hx + (nx - hx) * 0.9, hy + (ny - hy) * 0.9
        for sign in (-1, 1):
            if pose == "crouch":
                a1, a2 = 1.6, 2.6
            elif pose == "stand":
                a1, a2 = 0.12 * sign, 0.25
            else:
                a1 = -arm * sign
                a2 = a1 + elbow
            ex, ey = limb(sx, sy, a1, S * 0.17)
            wx, wy = limb(ex, ey, a2, S * 0.16)
            bone.setAlphaf(0.75 if sign < 0 else 1.0)
            c.drawLine(sx, sy, ex, ey, bone)
            c.drawLine(ex, ey, wx, wy, bone)
            c.drawCircle(wx, wy, S * 0.02, joint)
        bone.setAlphaf(1.0)
        # Schädel mit Kiefer
        cx, cy = nx + facing * S * 0.02, ny - S * 0.11
        r = S * 0.095
        c.drawCircle(cx, cy, r, joint)
        c.save()
        c.translate(cx - facing * r * 0.2, cy + r * 0.55)
        c.rotate(math.degrees(jaw) * facing)
        c.drawRoundRect(skia.Rect(min(0, facing * r * 1.05), -r * 0.12, max(0, facing * r * 1.05), r * 0.38),
                        r * 0.2, r * 0.2, joint)
        c.restore()
        c.drawCircle(cx + facing * r * 0.38, cy - r * 0.08, r * 0.27, dark)
        c.drawCircle(cx + facing * r * 0.75, cy + r * 0.35, r * 0.09, dark)
        c.restore()

    # --- Dinosaurier (Silhouetten) ---------------------------------------------------
    def trex(self, c: skia.Canvas, x: float, ground: float, size: float, facing: int, rgb, phase: float,
             jaw: float = 0.0, eye: float = 0.0) -> None:
        c.save()
        c.translate(x, ground)
        c.scale(facing * size, size)
        fill = skia.Paint(AntiAlias=True, Color=color(rgb))
        legp = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap,
                          StrokeJoin=skia.Paint.kRound_Join, Color=color(rgb), StrokeWidth=0.11)
        hip = (0.0, -0.62)
        for k, sign in enumerate((-1, 1)):
            a = 0.45 * math.sin(phase + (0 if sign > 0 else math.pi))
            kx, ky = hip[0] + math.sin(a) * 0.3, hip[1] + math.cos(a) * 0.3
            ax, ay = kx - 0.05, min(-0.04, ky + 0.3)
            leg = skia.Path()
            leg.moveTo(*hip)
            leg.lineTo(kx, ky)
            leg.lineTo(ax, ay)
            leg.lineTo(ax + 0.16, -0.01)
            legp.setStrokeWidth(0.13 if k else 0.11)
            c.drawPath(leg, legp)
        body = skia.Path()
        body.moveTo(-1.25, -0.72)
        body.cubicTo(-0.75, -0.92, -0.35, -1.0, 0.0, -0.98)
        body.cubicTo(0.28, -0.97, 0.45, -1.08, 0.58, -1.25)
        body.cubicTo(0.66, -1.36, 0.76, -1.42, 0.92, -1.40)
        body.cubicTo(1.02, -1.38, 1.1, -1.32, 1.1, -1.25)
        body.lineTo(0.78, -1.21)
        body.cubicTo(0.72, -1.12, 0.6, -0.98, 0.5, -0.88)
        body.cubicTo(0.4, -0.72, 0.22, -0.6, 0.0, -0.58)
        body.cubicTo(-0.35, -0.6, -0.75, -0.66, -1.25, -0.72)
        body.close()
        c.drawPath(body, fill)
        c.save()  # Unterkiefer (öffnet sich beim Brüllen)
        c.translate(0.76, -1.22)
        c.rotate(math.degrees(jaw) * 0.8)
        jawp = skia.Path()
        jawp.moveTo(0.0, 0.0)
        jawp.lineTo(0.32, 0.0)
        jawp.cubicTo(0.3, 0.06, 0.15, 0.1, 0.0, 0.08)
        jawp.close()
        c.drawPath(jawp, fill)
        c.restore()
        arm = skia.Path()
        arm.moveTo(0.42, -0.86)
        arm.lineTo(0.56, -0.8)
        arm.lineTo(0.6, -0.72)
        c.drawPath(arm, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=0.05,
                                   StrokeCap=skia.Paint.kRound_Cap, Color=color(rgb)))
        if eye > 0:
            c.drawCircle(0.86, -1.33, 0.025, skia.Paint(AntiAlias=True, Color=color((255, 60, 30), eye)))
        c.restore()

    def _draw_trex(self, c: skia.Canvas, hour: float, rgb) -> None:
        if not 6.5 <= hour < 12.5:
            return
        W, H = self.W, self.H
        jaw = 0.0
        if 6.95 <= hour < 7.6:
            jaw = 0.55 * math.sin(math.pi * _phase(hour, 6.95, 7.6))
        if 10.9 <= hour < 11.3:
            jaw = 0.3 * math.sin(math.pi * _phase(hour, 10.9, 11.3))
        facing = 1 if hour >= 11.5 else -1
        sniff = H * 0.02 * math.sin(self.t * 3) if 10.0 <= hour < 11.5 else 0.0
        self.trex(c, self.trex_x(hour), self.ground + sniff * 0.2, H * 0.22, facing, rgb, self.trex_phase, jaw, 1.0)

    def brachio(self, c: skia.Canvas, x: float, ground: float, size: float, facing: int, rgb, phase: float) -> None:
        c.save()
        c.translate(x, ground)
        c.scale(facing * size, size)
        paint = skia.Paint(AntiAlias=True, Color=color(rgb))
        legs = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=0.14,
                          StrokeCap=skia.Paint.kRound_Cap, Color=color(rgb))
        for k, lx in enumerate((-0.35, -0.25, 0.25, 0.38)):
            a = 0.18 * math.sin(phase + k * 1.7)
            c.drawLine(lx, -0.55, lx + math.sin(a) * 0.5, -0.02, legs)
        c.drawOval(skia.Rect(-0.6, -0.95, 0.65, -0.45), paint)
        neck = skia.Path()
        neck.moveTo(0.35, -0.85)
        neck.cubicTo(0.6, -1.4, 0.75, -1.9, 0.95, -2.1)
        neck.lineTo(1.05, -2.0)
        neck.cubicTo(0.9, -1.8, 0.75, -1.3, 0.62, -0.62)
        neck.close()
        c.drawPath(neck, paint)
        c.drawOval(skia.Rect(0.9, -2.18, 1.18, -2.03), paint)
        tail = skia.Path()
        tail.moveTo(-0.55, -0.85)
        tail.cubicTo(-0.9, -0.8, -1.2, -0.55, -1.45, -0.35)
        tail.cubicTo(-1.15, -0.5, -0.85, -0.58, -0.55, -0.6)
        tail.close()
        c.drawPath(tail, paint)
        c.restore()

    def trike(self, c: skia.Canvas, x: float, ground: float, size: float, facing: int, rgb, phase: float) -> None:
        c.save()
        c.translate(x, ground)
        c.scale(facing * size, size)
        paint = skia.Paint(AntiAlias=True, Color=color(rgb))
        legs = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=0.16,
                          StrokeCap=skia.Paint.kRound_Cap, Color=color(rgb))
        for k, lx in enumerate((-0.45, -0.3, 0.3, 0.45)):
            a = 0.25 * math.sin(phase + k * 1.6)
            c.drawLine(lx, -0.45, lx + math.sin(a) * 0.4, -0.02, legs)
        c.drawOval(skia.Rect(-0.75, -0.95, 0.6, -0.35), paint)
        frill = skia.Path()
        frill.addCircle(0.62, -0.78, 0.3)
        c.drawPath(frill, paint)
        head = skia.Path()
        head.moveTo(0.6, -0.9)
        head.lineTo(1.15, -0.62)
        head.lineTo(0.95, -0.45)
        head.lineTo(0.6, -0.5)
        head.close()
        c.drawPath(head, paint)
        horns = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=0.05,
                           StrokeCap=skia.Paint.kRound_Cap, Color=color(rgb))
        c.drawLine(0.78, -0.82, 1.25, -1.0, horns)
        c.drawLine(1.05, -0.62, 1.3, -0.72, horns)
        tail = skia.Path()
        tail.moveTo(-0.7, -0.75)
        tail.lineTo(-1.15, -0.5)
        tail.lineTo(-0.7, -0.55)
        tail.close()
        c.drawPath(tail, paint)
        c.restore()

    def ptero(self, c: skia.Canvas, x: float, y: float, size: float, rgb, phase: float) -> None:
        c.save()
        c.translate(x, y)
        c.scale(-size, size)
        flap = 0.5 + 0.5 * math.sin(phase)
        paint = skia.Paint(AntiAlias=True, Color=color(rgb))
        wing = skia.Path()
        wing.moveTo(-1.6, -0.6 + flap * 0.9)
        wing.quadTo(-0.7, -0.4, 0.0, 0.0)
        wing.quadTo(0.7, -0.4, 1.6, -0.6 + flap * 0.9)
        wing.quadTo(0.6, 0.1, 0.0, 0.18)
        wing.quadTo(-0.6, 0.1, -1.6, -0.6 + flap * 0.9)
        c.drawPath(wing, paint)
        head = skia.Path()
        head.moveTo(0.0, 0.0)
        head.lineTo(0.55, 0.1)
        head.lineTo(0.0, 0.18)
        head.moveTo(0.05, 0.02)
        head.lineTo(-0.3, -0.18)
        head.lineTo(-0.05, 0.1)
        c.drawPath(head, paint)
        c.restore()
