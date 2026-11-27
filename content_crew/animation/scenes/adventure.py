"""Story-Serie „24 Stunden in …“: das leuchtende Skelett reist in sieben Welten (Silhouetten-Stil).

Gleicher Spannungsbogen wie bei den Dinos – Ankunft, sanfter Riese, Gefahr, Flucht, Versteck, Unwetter,
Herde im Sonnenuntergang, Nacht, Portal –, aber jede Welt hat eigene Landschaft, Tiere, Wetter und
Nachthimmel. Am Ende kommt etwas mit nach Hause: ein Jungtier (Haustier) oder leuchtende Augen im Portal.
Das Skelett erzählt auf Englisch (Kokoro-Stimme).
"""

from __future__ import annotations

import math
import random

import numpy as np
import skia

from content_crew.animation.creatures import SPECIES, bird, quadruped, rider
from content_crew.animation.engine import WHITE, color, mix, text_center
from content_crew.animation.scenes.dino import BLACK, TAU, DinoTrip, _phase, _smooth, sky_at
from content_crew.animation.worlds import pick

TINTS = {"cold": ((150, 190, 255), 0.35), "desert": ((255, 190, 110), 0.3), "jungle": ((70, 190, 150), 0.28),
         "savanna": ((255, 165, 70), 0.32), "medieval": ((120, 130, 170), 0.3), "west": ((240, 120, 70), 0.32)}

WORLDS: dict[str, dict] = {
    "iceage": dict(sky="cold", far="glacier", mid="pines", near="snow", fore="snow", cover="ice", early="mammoth",
                   danger="sabertooth", herd="mammoth", weather="snow", night="aurora", pet="mammoth",
                   pet_rgb=(176, 128, 96), title=("24 HOURS", "IN THE ICE AGE"),
                   beats=["ARRIVAL", "MAMMOTH", "FREEZING", "SABERTOOTH!", "HIDING", "SNOWSTORM", "MAMMOTHS",
                          "NIGHT", "GOING HOME"]),
    "arctic": dict(sky="cold", far="glacier", mid="ice", near="snow", fore="snow", cover="ice", early="reindeer",
                   danger="polarbear", herd="reindeer", weather="snow", night="aurora", pet="polarbear",
                   pet_rgb=(236, 234, 228), title=("24 HOURS", "IN THE ARCTIC"),
                   beats=["ARRIVAL", "REINDEER", "ICE COLD", "POLAR BEAR!", "HIDING", "BLIZZARD", "REINDEER HERD",
                          "NORTHERN LIGHTS", "GOING HOME"]),
    "egypt": dict(sky="desert", far="pyramids", mid="palms", near="sand", fore="rocks", cover="rock", early="camel",
                  danger="crocodile", herd="camel", riders="desert", weather="sand", night="stars", pet="cat",
                  pet_rgb=(214, 170, 110), title=("24 HOURS", "IN ANCIENT EGYPT"),
                  beats=["ARRIVAL", "PYRAMIDS", "HEAT", "CROCODILE!", "HIDING", "SANDSTORM", "CARAVAN", "NIGHT",
                         "GOING HOME"]),
    "jungle": dict(sky="jungle", far="jungle", mid="jungle", near="grass", fore="leaves", cover="bush",
                   early="elephant", danger="jaguar", herd="elephant", weather="rain", night="fireflies",
                   pet="jaguar", pet_rgb=(222, 170, 80), title=("24 HOURS", "IN THE JUNGLE"),
                   beats=["ARRIVAL", "ELEPHANT", "HUMIDITY", "JAGUAR!", "HIDING", "TROPICAL RAIN", "ELEPHANTS",
                          "FIREFLIES", "GOING HOME"]),
    "savanna": dict(sky="savanna", far="savanna", mid="acacia", near="grass", fore="leaves", cover="rock",
                    early="giraffe", danger="lion", herd="elephant", weather="rain", night="stars", pet="lion",
                    pet_rgb=(226, 178, 104), title=("24 HOURS", "IN THE SAVANNA"),
                    beats=["ARRIVAL", "GIRAFFE", "HEAT", "LION!", "HIDING", "THUNDERSTORM", "ELEPHANTS", "NIGHT",
                           "GOING HOME"]),
    "medieval": dict(sky="medieval", far="castle", mid="oaks", near="grass", fore="leaves", cover="bush",
                     early="horse", riders="knight", danger="dragon", herd="horse", weather="rain", night="stars",
                     pet="dragon", pet_rgb=(110, 190, 120), title=("24 HOURS", "IN THE MIDDLE AGES"),
                     beats=["ARRIVAL", "KNIGHT", "CASTLE", "DRAGON!", "HIDING", "THUNDERSTORM", "KNIGHTS", "NIGHT",
                            "GOING HOME"]),
    "wildwest": dict(sky="west", far="mesas", mid="cactus", near="sand", fore="rocks", cover="wagon", early="horse",
                     danger="bison", danger_count=3, herd="horse", wild=True, weather="dust", night="stars",
                     pet="wolf", pet_rgb=(176, 166, 156), title=("24 HOURS", "IN THE WILD WEST"),
                     beats=["ARRIVAL", "MUSTANG", "NO WATER", "STAMPEDE!", "HIDING", "DUST STORM", "WILD HORSES",
                            "NIGHT", "GOING HOME"]),
}
BEAT_HOURS = (0.0, 1.0, 4.0, 6.5, 10.0, 12.5, 15.5, 18.5, 22.5)
DANGER_L = {"sabertooth": 0.36, "jaguar": 0.34, "lion": 0.36, "polarbear": 0.38, "crocodile": 0.5, "bison": 0.3,
            "dragon": 0.36}
EARLY_L = {"mammoth": 0.3, "reindeer": 0.2, "camel": 0.22, "elephant": 0.3, "giraffe": 0.2, "horse": 0.22}
HERD_L = {"mammoth": 0.22, "reindeer": 0.16, "camel": 0.18, "elephant": 0.22, "horse": 0.17}


class Adventure(DinoTrip):
    name = "adventure"
    substeps = 1
    outro = 2.0

    def __init__(self, ctx, params, headless=False):
        self.world_key = params.get("world") if params.get("world") in WORLDS else "iceage"
        self.world = WORLDS[self.world_key]
        self.variant = int(params.get("variant") or 0)
        super().__init__(ctx, params, headless)
        W, H, g = self.W, self.H, self.ground
        self.ending = params.get("ending") if params.get("ending") in ("pet", "eyes") else "pet"
        self.lang = "en"
        self.epi_len = 10.5 if self.ending == "pet" else 8.5
        self.story_T = max(3.0, self.target - self.epi_len)
        self.epi_start = self.story_T * 24.6 / 24
        self.danger_phase = 0.0
        self.danger_head = (W, g)
        rng = random.Random(self.variant * 101 + 7)
        self.herd_n = 3 + self.variant % 2
        self.danger_n = self.world.get("danger_count", 1)
        self.fireflies = [(rng.uniform(0, W), rng.uniform(g - H * 0.32, g - H * 0.03), rng.uniform(0, TAU),
                           rng.uniform(0.5, 1.2)) for _ in range(46)]
        self.flakes = np.array([[rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.5, 1.0)] for _ in range(320)])
        self.cover_x = W * 0.3

    # --- Zeit und Himmel -------------------------------------------------------------
    def epi(self) -> float:
        return self.t - self.epi_start

    def sky(self, hour: float):
        top, bottom = sky_at(hour)
        tint, amount = TINTS.get(self.world["sky"], ((255, 255, 255), 0.0))
        top, bottom = mix(top, tint, amount * 0.6), mix(bottom, tint, amount)
        storm = _phase(hour, 12.6, 13.0) * (1 - _phase(hour, 15.2, 15.6))
        weather = self.world["weather"]
        if storm and weather == "snow":
            top, bottom = mix(top, (170, 180, 200), 0.5 * storm), mix(bottom, (214, 222, 234), 0.6 * storm)
        elif storm and weather in ("sand", "dust"):
            top, bottom = mix(top, (150, 108, 70), 0.5 * storm), mix(bottom, (214, 160, 100), 0.6 * storm)
        return top, bottom

    # --- Landschaft (einmal vorgezeichnet) ----------------------------------------------
    def _make_layers(self) -> dict:
        W, H, g = self.W, self.H, self.ground
        rng = random.Random(self.variant * 977 + sum(map(ord, self.world_key)))
        fill = skia.Paint(AntiAlias=True, Color=color(WHITE))
        stroke = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap,
                            Color=color(WHITE))
        layers = {}
        far, top = self._layer(H * 0.2, g + 4)
        self._far(far.getCanvas(), rng, fill, stroke)
        layers["far"] = (far.makeImageSnapshot(), top)
        mid, top = self._layer(H * 0.2, g + 4)
        self._mid(mid.getCanvas(), rng, fill, stroke)
        layers["mid"] = (mid.makeImageSnapshot(), top)
        near, top = self._layer(g - H * 0.04, H)
        self._near(near.getCanvas(), rng, fill, stroke)
        layers["near"] = (near.makeImageSnapshot(), top)
        city, top = self._layer(H * 0.35, g + 4)
        win, _ = self._layer(H * 0.35, g + 4)
        c, wc = city.getCanvas(), win.getCanvas()
        lit = skia.Paint(AntiAlias=True)
        x = -0.02 * W
        while x < W * 1.05:
            bw, bh = rng.uniform(0.09, 0.18) * W, rng.uniform(0.1, 0.33) * H
            c.drawRect(skia.Rect(x, g - bh, x + bw - W * 0.008, g + 4), fill)
            for row in range(int(bh / (H * 0.028)) - 1):
                for col in range(int(bw / (W * 0.035))):
                    if rng.random() < 0.42:
                        lit.setColor(color((255, rng.randint(190, 225), 120), rng.uniform(0.55, 0.95)))
                        wx, wy = x + W * 0.012 + col * W * 0.035, g - bh + H * 0.018 + row * H * 0.028
                        wc.drawRect(skia.Rect(wx, wy, wx + W * 0.016, wy + H * 0.012), lit)
            x += bw
        layers["city"] = (city.makeImageSnapshot(), top)
        layers["windows"] = (win.makeImageSnapshot(), top)
        return layers

    def _far(self, c, rng, fill, stroke) -> None:
        W, H, g = self.W, self.H, self.ground
        kind = self.world["far"]
        path = skia.Path()
        path.moveTo(0, g)
        if kind == "glacier":  # Eisschelfe mit Abbruchkanten, dahinter Gipfel
            peaks = skia.Path()
            peaks.moveTo(0, g)
            x = 0.0
            while x < 2 * W:
                peaks.lineTo(x, g - rng.uniform(0.14, 0.24) * H)
                x += rng.uniform(0.1, 0.2) * W
            peaks.lineTo(2 * W, g)
            peaks.close()
            c.drawPath(peaks, skia.Paint(AntiAlias=True, Color=color(WHITE, 0.55)))
            x, h = 0.0, rng.uniform(0.07, 0.12) * H
            while x < 2 * W:
                w = rng.uniform(0.14, 0.32) * W
                path.lineTo(x, g - h)
                path.lineTo(x + w * 0.9, g - h - rng.uniform(-0.008, 0.008) * H)
                h = rng.uniform(0.05, 0.13) * H
                path.lineTo(x + w, g - h)
                x += w
        elif kind == "pyramids":
            x = 0.0
            while x <= 2 * W:
                path.lineTo(x, g - (0.03 + 0.02 * math.sin(x / W * 5.3)) * H)
                x += W * 0.04
            for px, size in ((0.3, 0.24), (0.58, 0.17), (0.76, 0.1), (1.35, 0.21), (1.62, 0.13)):
                pyr = skia.Path()
                cx, hh = (px + rng.uniform(-0.04, 0.04)) * W, size * H
                pyr.moveTo(cx - hh * 0.95, g)
                pyr.lineTo(cx, g - hh)
                pyr.lineTo(cx + hh * 0.95, g)
                pyr.close()
                c.drawPath(pyr, fill)
        elif kind == "jungle":
            x = 0.0
            while x < 2 * W:
                w, h = rng.uniform(0.15, 0.3) * W, rng.uniform(0.1, 0.22) * H
                path.quadTo(x + w * 0.5, g - h * 1.6, x + w, g - rng.uniform(0.04, 0.08) * H)
                x += w
        elif kind == "savanna":
            x = 0.0
            while x <= 2 * W:
                path.lineTo(x, g - (0.025 + 0.015 * math.sin(x / W * 4.1 + 1)) * H)
                x += W * 0.04
            mx = W * rng.uniform(1.1, 1.4)  # Tafelberg in der Ferne
            mt = skia.Path()
            mt.moveTo(mx - W * 0.4, g)
            mt.lineTo(mx - W * 0.12, g - H * 0.12)
            mt.lineTo(mx + W * 0.1, g - H * 0.125)
            mt.lineTo(mx + W * 0.38, g)
            mt.close()
            c.drawPath(mt, fill)
        elif kind == "mesas":
            x = 0.0
            while x < 2 * W:
                w, h = rng.uniform(0.2, 0.42) * W, rng.uniform(0.07, 0.2) * H
                path.lineTo(x, g - H * 0.02)
                path.lineTo(x + w * 0.15, g - h)
                path.lineTo(x + w * 0.8, g - h)
                path.lineTo(x + w * 0.95, g - H * 0.02)
                x += w + rng.uniform(0.02, 0.12) * W
        elif kind == "castle":
            x = 0.0
            while x <= 2 * W:
                path.lineTo(x, g - (0.04 + 0.025 * math.sin(x / W * 3.0)) * H)
                x += W * 0.04
            for base in (0.55, 1.55):
                self._castle(c, base * W + rng.uniform(-0.05, 0.05) * W, g - 0.055 * H, fill, stroke)
        else:
            x = 0.0
            while x < 2 * W:
                path.lineTo(x, g - rng.uniform(0.06, 0.15) * H)
                x += rng.uniform(0.08, 0.16) * W
        path.lineTo(2 * W, g - H * 0.04)
        path.lineTo(2 * W, g)
        path.close()
        c.drawPath(path, fill)

    def _castle(self, c, x, base, fill, stroke) -> None:
        W, H = self.W, self.H
        c.drawRect(skia.Rect(x - W * 0.14, base - H * 0.1, x + W * 0.14, base + 4), fill)
        for k in range(9):  # Zinnen
            cx = x - W * 0.14 + k * W * 0.035
            c.drawRect(skia.Rect(cx, base - H * 0.112, cx + W * 0.018, base - H * 0.1), fill)
        for tx, th in ((-0.15, 0.2), (0.15, 0.2), (0.0, 0.27)):
            left = x + tx * W - W * 0.03
            c.drawRect(skia.Rect(left, base - H * th, left + W * 0.06, base + 4), fill)
            roof = skia.Path()
            roof.moveTo(left - W * 0.008, base - H * th)
            roof.lineTo(left + W * 0.03, base - H * (th + 0.06))
            roof.lineTo(left + W * 0.068, base - H * th)
            roof.close()
            c.drawPath(roof, fill)
            stroke.setStrokeWidth(W * 0.004)
            fx, fy = left + W * 0.03, base - H * (th + 0.06)
            c.drawLine(fx, fy, fx, fy - H * 0.03, stroke)
            flag = skia.Path()
            flag.moveTo(fx, fy - H * 0.03)
            flag.lineTo(fx + W * 0.03, fy - H * 0.024)
            flag.lineTo(fx, fy - H * 0.018)
            c.drawPath(flag, fill)

    def _mid(self, c, rng, fill, stroke) -> None:
        W, H, g = self.W, self.H, self.ground
        kind = self.world["mid"]
        x = rng.uniform(0, 0.1) * W
        while x < 2 * W - 0.05 * W:
            if kind == "pines":
                h, w = rng.uniform(0.12, 0.24) * H, rng.uniform(0.05, 0.08) * W
                c.drawRect(skia.Rect(x - W * 0.005, g - h * 0.25, x + W * 0.005, g), fill)
                for k in range(3):
                    tri = skia.Path()
                    y0 = g - h * (0.2 + k * 0.26)
                    ww = w * (1 - k * 0.25)
                    tri.moveTo(x - ww, y0)
                    tri.lineTo(x, y0 - h * 0.42)
                    tri.lineTo(x + ww, y0)
                    tri.close()
                    c.drawPath(tri, fill)
                x += rng.uniform(0.06, 0.16) * W
            elif kind == "ice":
                pts = []
                w, h = rng.uniform(0.06, 0.14) * W, rng.uniform(0.04, 0.13) * H
                pts = [(x - w, g), (x - w * rng.uniform(0.5, 0.9), g - h * rng.uniform(0.5, 0.8)),
                       (x - w * 0.1, g - h), (x + w * rng.uniform(0.3, 0.6), g - h * rng.uniform(0.6, 0.9)), (x + w, g)]
                p = skia.Path()
                p.moveTo(*pts[0])
                for pt in pts[1:]:
                    p.lineTo(*pt)
                p.close()
                c.drawPath(p, fill)
                x += rng.uniform(0.14, 0.32) * W
            elif kind == "palms":
                hgt = rng.uniform(0.16, 0.28) * H
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
                    frond = skia.Path()
                    frond.moveTo(tx, ty)
                    frond.quadTo(tx + math.cos(a) * ln, ty + math.sin(a) * ln * 0.9,
                                 tx + math.cos(a) * ln * 1.3, ty + math.sin(a) * ln * 0.6 + ln * 0.55)
                    c.drawPath(frond, stroke)
                x += rng.uniform(0.18, 0.4) * W
            elif kind in ("jungle", "oaks"):
                tall = kind == "jungle"
                h = rng.uniform(0.22, 0.36) * H if tall else rng.uniform(0.11, 0.19) * H
                stroke.setStrokeWidth(W * (0.016 if tall else 0.02))
                c.drawLine(x, g, x + rng.uniform(-0.02, 0.02) * W, g - h, stroke)
                for k in range(7 if tall else 6):
                    c.drawCircle(x + rng.uniform(-0.08, 0.08) * W, g - h + rng.uniform(-0.05, 0.03) * H,
                                 rng.uniform(0.045, 0.08) * W, fill)
                if tall:
                    stroke.setStrokeWidth(W * 0.004)
                    for k in range(3):
                        vx = x + rng.uniform(-0.07, 0.07) * W
                        c.drawLine(vx, g - h + H * 0.02, vx + rng.uniform(-0.01, 0.01) * W,
                                   g - h + rng.uniform(0.08, 0.18) * H, stroke)
                x += rng.uniform(0.12, 0.24) * W
            elif kind == "acacia":
                h = rng.uniform(0.13, 0.2) * H
                stroke.setStrokeWidth(W * 0.012)
                tx = x + rng.uniform(-0.03, 0.03) * W
                c.drawLine(x, g, tx, g - h * 0.7, stroke)
                for side in (-1, 1):
                    c.drawLine(tx, g - h * 0.7, tx + side * W * 0.06, g - h, stroke)
                c.drawOval(skia.Rect(tx - W * 0.16, g - h - H * 0.025, tx + W * 0.16, g - h + H * 0.012), fill)
                x += rng.uniform(0.35, 0.7) * W
            elif kind == "cactus":
                h = rng.uniform(0.08, 0.16) * H
                stroke.setStrokeWidth(W * 0.03)
                c.drawLine(x, g, x, g - h, stroke)
                stroke.setStrokeWidth(W * 0.022)
                for side, ah in ((-1, 0.45), (1, 0.6)):
                    if rng.random() < 0.8:
                        ax, ay = x + side * W * 0.035, g - h * ah
                        c.drawLine(x, ay + h * 0.08, ax, ay + h * 0.08, stroke)
                        c.drawLine(ax, ay + h * 0.08, ax, ay - h * 0.25, stroke)
                x += rng.uniform(0.2, 0.45) * W
            else:
                c.drawCircle(x, g, rng.uniform(0.03, 0.06) * W, fill)
                x += rng.uniform(0.1, 0.2) * W

    def _near(self, c, rng, fill, stroke) -> None:
        W, H, g = self.W, self.H, self.ground
        kind = self.world["near"]
        edge = skia.Path()
        edge.moveTo(0, H)
        edge.lineTo(0, g)
        x = 0.0
        wobble = 0.004 if kind == "grass" else 0.002
        while x <= 2 * W:
            edge.lineTo(x, g + rng.uniform(-wobble, wobble) * H)
            x += 0.02 * W
        edge.lineTo(2 * W, H)
        edge.close()
        c.drawPath(edge, fill)
        if kind == "grass":
            stroke.setStrokeWidth(W * 0.004)
            for _ in range(160):
                gx = rng.uniform(0, 2 * W)
                for k in range(3):
                    c.drawLine(gx, g + 2, gx + (k - 1) * W * 0.008, g - rng.uniform(0.01, 0.025) * H, stroke)
        elif kind == "snow":
            for _ in range(18):
                gx = rng.uniform(0, 2 * W)
                c.drawOval(skia.Rect(gx - W * 0.08, g - H * 0.012, gx + W * 0.08, g + H * 0.01), fill)
        else:  # Sand mit Steinen
            for _ in range(26):
                gx = rng.uniform(0, 2 * W)
                r = rng.uniform(0.006, 0.016) * W
                c.drawOval(skia.Rect(gx - r * 1.6, g - r, gx + r * 1.6, g + r), fill)

    def _draw_foreground(self, c: skia.Canvas, rgb) -> None:
        kind = self.world["fore"]
        if kind == "leaves":
            super()._draw_foreground(c, rgb)
            return
        W, H = self.W, self.H
        paint = skia.Paint(AntiAlias=True, Color=color(rgb))
        if kind == "snow":
            for cx, w in ((W * 0.02, W * 0.3), (W * 0.98, W * 0.34)):
                c.drawOval(skia.Rect(cx - w, H * 0.955, cx + w, H * 1.06), paint)
        else:
            for cx, w, h in ((W * 0.04, W * 0.2, H * 0.06), (W * 0.95, W * 0.24, H * 0.075)):
                rock = skia.Path()
                rock.moveTo(cx - w, H)
                rock.lineTo(cx - w * 0.6, H - h)
                rock.lineTo(cx + w * 0.2, H - h * 1.15)
                rock.lineTo(cx + w * 0.8, H - h * 0.5)
                rock.lineTo(cx + w, H)
                rock.close()
                c.drawPath(rock, paint)

    # --- Erzählung ------------------------------------------------------------------------
    def voiceover(self) -> list[tuple[float, str]]:
        sec = lambda h: h * self.story_T / 24  # noqa: E731
        w, v = self.world_key, self.variant
        lines = [(0.25, pick(w, "intro", v)), (sec(2.6), pick(w, "early", v)), (sec(4.3), pick(w, "challenge", v)),
                 (sec(6.5), pick(w, "seven", v)), (sec(7.45), pick(w, "run", v)), (sec(8.2), pick(w, "danger", v)),
                 (sec(10.1), pick(w, "hide", v)), (sec(12.6), pick(w, "weather", v)), (sec(15.6), pick(w, "herd", v)),
                 (sec(18.7), pick(w, "night", v)), (sec(22.6), pick(w, "portal", v))]
        e0 = self.epi_start
        if self.ending == "pet":
            lines += [(e0 + 0.3, pick(w, "pet_home", v)), (e0 + 3.0, pick(w, "pet_found", v)),
                      (e0 + 6.2, pick(w, "pet_end", v))]
        else:
            lines += [(e0 + 0.3, pick(w, "eyes_home", v)), (e0 + 3.2, pick(w, "eyes_found", v)),
                      (e0 + 5.6, pick(w, "eyes_end", v))]
        return lines

    # --- Ablauf --------------------------------------------------------------------------------
    def step(self, h: float) -> None:
        hour = self.hour()
        v = self.speed(hour)
        self.scroll += v * h
        moving = abs(v) > 1
        self.walk_phase += h * (9.5 if abs(v) > self.W * 0.3 else 5.2 if moving else 0.0)
        if 6.5 <= hour < 12.6:
            self.danger_phase += h * (7.5 if (7.4 <= hour < 10.0 or hour >= 11.5) else 3.0)
        if self.done_at is None and self.epi() >= self.epi_len:
            self.finish()
        self._sounds(hour)

    def _sounds(self, hour: float) -> None:
        if self.headless:
            return
        W = self.W
        danger = self.world["danger"]
        weather = self.world["weather"]
        if self.at_hour(0.02):
            self.play(0, 0.7, W * 0.35, kind="whoosh", accent=True)
        if self.at_hour(7.0):
            self.play(0, 1.0, W * 0.75, kind="roar", accent=True)
            self.shake = 1.0
            if danger == "dragon":
                self.play(0, 0.6, W * 0.7, kind="burst", accent=True)
            if danger == "bison":
                for k in range(3):
                    self.play(0, 0.5, W * 0.8, kind="boom", accent=True)
        if self.at_hour(11.0):
            self.play(0, 0.5, W * 0.8, kind="roar", accent=True)
        for k, hh in enumerate((13.0, 14.3, 15.1)):
            if self.at_hour(hh):
                if weather == "rain":
                    self.play(0, 0.9, W * 0.5, kind="thunder", accent=True)
                    self.flash = 1.0
                else:
                    self.play(0, 0.75, W * (0.2 + 0.3 * k), kind="whoosh", accent=True)
                    self.play(0, 0.25, kind="boom")
        if self.at_hour(22.6) or self.at_hour(23.9):
            self.play(0, 0.75, W * 0.7, kind="whoosh", accent=True)
        if self.epi() >= 0:
            self._home_sounds()
            return
        if self.t >= self.beat:  # Musik: Puls, Hi-Hat, Melodie – je nach Szene
            n = int(round(self.beat / self.beat_len))
            chase = 7.4 <= hour < 10.0
            self.beat += self.beat_len * (0.5 if chase else 1.0)
            night = 18.5 <= hour < 22.5
            if not night and hour >= 1.0:
                self.play(0, 0.22 if not chase else 0.32, kind="boom")
                self.play(self.music.degree(14 + n % 3), 0.05, kind="tick")
            if night:
                if n % 4 == 0:
                    self.play(self.music.degree(self.fx.randrange(4, 9)), 0.14)
                if self.fx.random() < 0.5:
                    self.play(self.music.degree(16), 0.03, self.fx.uniform(0, W), kind="tick")
            elif n % 2 == 0 or chase:
                self.play(self.music.next() + (12 if chase else 0), 0.2)
        heavy = danger in ("bison", "polarbear", "dragon", "crocodile")
        if 6.5 <= hour < 12.6 and int(self.danger_phase / math.pi) != int((self.danger_phase - 0.12) / math.pi):
            self.play(0, 0.2 if heavy else 0.08, self.danger_x(hour), kind="boom")

    def _home_sounds(self) -> None:
        W = self.W
        if self.at_epi(0.0):
            self.play(0, 0.8, W * 0.3, kind="whoosh", accent=True)
            self.flash = 1.0
        if self.at_epi(1.2):
            self.play(0, 0.35, W * 0.55, kind="boom")
        if self.ending == "pet":
            for e in (1.9, 2.9, 3.6):
                if self.at_epi(e):
                    self.play(0, 0.45, W * 0.35, kind="squeak", accent=True)
            for k, e in enumerate((5.4, 6.0, 6.6)):
                if self.at_epi(e):
                    self.hearts.append(self.t)
                    self.play(self.music.degree(10 + 2 * k), 0.3, W * 0.5, accent=True)
            if self.at_epi(7.0):
                self.play(0, 0.5, kind="boom", accent=True)
                for p in self.music.chord():
                    self.play(p + 12, 0.25, accent=True)
        else:
            if self.at_epi(3.0):
                self.play(0, 0.55, W * 0.3, kind="roar", accent=True)
                self.shake = 0.6
            if self.at_epi(4.4):
                self.play(0, 0.6, kind="boom", accent=True)
                for p in self.music.chord():
                    self.play(p - 12, 0.3, accent=True)

    def frame(self, dt: float) -> None:
        if self.epi() >= 0:
            return
        hour = self.hour()
        W, H, g = self.W, self.H, self.ground
        if 19.0 <= hour < 22.6 and self.fx.random() < 0.5:  # Funken vom Lagerfeuer
            fx, fy = self._fire_pos()
            self.particles.burst([fx], [fy - H * 0.02], (255, 170, 60), speed=W * 0.05, size=W * 0.005,
                                 life=1.2, vy0=-W * 0.22)
        storm = 12.6 <= hour < 15.6
        weather = self.world["weather"]
        if storm and weather == "rain":
            self.drops[:, 0] -= W * 0.25 * dt
            self.drops[:, 1] += H * 1.4 * dt
            wrap = self.drops[:, 1] > g
            self.drops[wrap, 1] -= g + H * 0.2
            self.drops[self.drops[:, 0] < -20, 0] += W * 1.3
        elif storm or (weather == "snow" and 2.0 <= hour < 6.5):
            fast = weather in ("sand", "dust")
            speed = 1.0 if storm else 0.25
            self.flakes[:, 0] -= W * (1.5 if fast else 0.35) * speed * dt * self.flakes[:, 2]
            self.flakes[:, 1] += H * (0.05 if fast else 0.22) * dt * self.flakes[:, 2] * (1 + speed)
            self.flakes[self.flakes[:, 0] < -10, 0] += W + 20
            self.flakes[self.flakes[:, 1] > g, 1] -= g
        if self.world["danger"] == "dragon":
            breathe = 7.0 <= hour < 7.5 or (7.6 <= hour < 9.8 and self.fx.random() < 0.12)
            if breathe:
                hx, hy = self.danger_head
                self.particles.burst([hx] * 6, [hy] * 6, (255, 140, 40), speed=W * 0.12, size=W * 0.012, life=0.7,
                                     vx0=-W * 0.9, vy0=W * 0.05)

    # --- Positionen ----------------------------------------------------------------------------
    def danger_x(self, hour: float) -> float:
        return self.trex_x(hour)

    # --- Zeichnen ---------------------------------------------------------------------------------
    def draw(self, c: skia.Canvas) -> None:
        if self.epi() >= 0:
            self._draw_home(c, self.epi())
            return
        W, H, g = self.W, self.H, self.ground
        hour = self.hour()
        top, bottom = self.sky(hour)
        c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(0, g)], [color(top), color(bottom)])))
        night = _phase(hour, 18.6, 19.6) * (1 - _phase(hour, 22.8, 23.6))
        if self.world["night"] == "aurora":
            self._draw_aurora(c, night)
        self._draw_sky_objects(c, hour, night)
        far, midc, nearc = mix(bottom, BLACK, 0.42), mix(bottom, BLACK, 0.7), mix(bottom, BLACK, 0.9)
        if self.world["far"] == "glacier":  # Eis bleibt heller als Fels
            far, midc = mix(bottom, BLACK, 0.3), mix(bottom, BLACK, 0.6)
        self._blit(c, "far", self.scroll * 0.15, far)
        self._draw_early(c, hour, mix(bottom, BLACK, 0.55))
        self._blit(c, "mid", self.scroll * 0.45, midc)
        self._draw_herd(c, hour, mix(bottom, BLACK, 0.84))
        if self.world["night"] == "fireflies":
            self._draw_fireflies(c, night)
        self._draw_eyes(c, hour, night)
        self._draw_portal(c, hour)
        self._draw_fire(c, hour)
        self._draw_skeleton_scene(c, hour)
        self._draw_danger(c, hour, nearc)
        self._blit(c, "near", self.scroll, nearc)
        self._draw_cover(c, hour, nearc)
        self._draw_weather(c, hour)
        self.particles.draw(c)
        self._draw_foreground(c, mix(bottom, BLACK, 0.95))
        self._draw_text(c, hour)

    def _saddle(self, kind: str, x: float, ground: float, L: float, facing: int) -> tuple[float, float]:
        s = SPECIES[kind]
        y = ground - L * s["leg"] - L * s["body_h"]
        if kind == "camel":
            return x - facing * L * 0.05, y - L * s["body_h"] * s.get("hump", 0) * 0.9
        return x - facing * L * 0.08, y + L * 0.02

    def _draw_early(self, c, hour: float, rgb) -> None:
        W, H, g = self.W, self.H, self.ground
        if 0.8 <= hour < 6.5:
            kind = self.world["early"]
            x = W * (1.12 - 0.66 * _phase(hour, 0.8, 6.3))
            L = W * EARLY_L[kind]
            gallop = self.world.get("wild") and kind == "horse"
            if gallop:
                x = W * (1.3 - 1.8 * _phase(hour, 1.2, 4.4))
            quadruped(c, kind, x, g - H * 0.01, L, -1, self.t * (8 if gallop else 2.4), rgb, gallop=bool(gallop))
            if self.world.get("riders") and kind in ("horse", "camel"):
                sx, sy = self._saddle(kind, x, g - H * 0.01, L, -1)
                rider(c, sx, sy, L * 0.5, -1, rgb, self.world["riders"], self.t * 2.4)
        if 1.5 <= hour < 4.2:
            for k, (dx, dy) in enumerate(((0.0, 0.0), (0.12, 0.04), (0.22, -0.02), (0.3, 0.05))):
                f = (hour - 1.5) / 2.7
                bx = W * (1.15 - 1.4 * f + dx)
                by = H * (0.24 + dy) + math.sin(self.t * 1.5 + k) * H * 0.01
                bird(c, bx, by, W * 0.03, self.t * 9 + k, mix(rgb, BLACK, 0.2))

    def _draw_herd(self, c, hour: float, rgb) -> None:
        if not 15.4 <= hour < 18.8:
            return
        W, g = self.W, self.ground
        kind = self.world["herd"]
        gallop = bool(self.world.get("wild"))
        f = (hour - 15.4) / 3.4
        for k in range(self.herd_n):
            baby = kind in ("mammoth", "elephant") and k == self.herd_n - 1
            L = W * HERD_L[kind] * (0.55 if baby else 1 - 0.1 * (k % 2))
            x = W * (1.3 - 1.9 * f) + k * W * 0.3
            phase = self.t * (8 if gallop else 4.5) + k
            quadruped(c, kind, x, g + 2, L, -1, phase, rgb, gallop=gallop)
            if self.world.get("riders") and kind in ("horse", "camel"):
                sx, sy = self._saddle(kind, x, g + 2, L, -1)
                rider(c, sx, sy, L * 0.5, -1, rgb, self.world["riders"], phase)

    def _draw_danger(self, c, hour: float, rgb) -> None:
        if not 6.5 <= hour < 12.6:
            return
        W, H, g = self.W, self.H, self.ground
        kind = self.world["danger"]
        L = W * DANGER_L[kind]
        x = self.danger_x(hour)
        leaving = hour >= 11.5
        facing = 1 if leaving else -1
        gallop = 7.4 <= hour < 10.0 or leaving
        jaw = _phase(hour, 6.9, 7.05) * (1 - _phase(hour, 7.35, 7.5))
        lift = 0.0
        if kind == "dragon":
            lift = H * 0.11 * _phase(hour, 7.4, 7.8) * (1 - _phase(hour, 9.6, 10.0)) + H * 0.14 * _phase(hour, 11.5, 12.2)
        for k in range(self.danger_n):
            dx = k * L * 0.8 * (-facing)
            dy = (k % 2) * H * 0.012
            head = quadruped(c, kind, x + dx, g - lift + dy, L * (1 - 0.08 * k), facing, self.danger_phase + k * 1.3,
                             rgb, gallop=gallop, eye=((255, 200, 60), 0.95), jaw=jaw,
                             wing=math.sin(self.danger_phase * (1.8 if lift else 0.6)) if kind == "dragon" else None)
            if k == 0:
                self.danger_head = head

    def _draw_cover(self, c, hour: float, rgb) -> None:
        if not 10.0 <= hour < 12.6:
            return
        W, H, g = self.W, self.H, self.ground
        alpha = _phase(hour, 10.0, 10.3) * (1 - _phase(hour, 12.3, 12.6))
        paint = skia.Paint(AntiAlias=True, Color=color(rgb, alpha))
        rx = self.cover_x
        kind = self.world["cover"]
        p = skia.Path()
        if kind == "ice":
            for i, (dx, dy) in enumerate(((-0.2, 0.0), (-0.17, -0.11), (-0.05, -0.155), (0.08, -0.125), (0.19, -0.05),
                                          (0.2, 0.0))):
                (p.moveTo if i == 0 else p.lineTo)(rx + dx * W, g + 6 + dy * H)
            p.close()
            c.drawPath(p, paint)
        elif kind == "bush":
            for k in range(7):
                bx = rx + (k - 3) * W * 0.055
                c.drawCircle(bx, g - H * (0.05 + 0.03 * math.sin(k * 1.7)), W * (0.07 + 0.015 * (k % 3)), paint)
            c.drawRect(skia.Rect(rx - W * 0.2, g - H * 0.04, rx + W * 0.2, g + 6), paint)
        elif kind == "wagon":
            c.drawRect(skia.Rect(rx - W * 0.2, g - H * 0.1, rx + W * 0.17, g - H * 0.035), paint)
            c.drawOval(skia.Rect(rx - W * 0.2, g - H * 0.19, rx + W * 0.17, g - H * 0.01), paint)
            ring = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=W * 0.012,
                              Color=color(rgb, alpha))
            for wx in (rx - W * 0.12, rx + W * 0.09):
                c.drawCircle(wx, g - H * 0.035, W * 0.045, ring)
                for k in range(4):
                    a = k * math.pi / 4 + self.t * 0
                    c.drawLine(wx - math.cos(a) * W * 0.045, g - H * 0.035 - math.sin(a) * W * 0.045,
                               wx + math.cos(a) * W * 0.045, g - H * 0.035 + math.sin(a) * W * 0.045, ring)
        else:  # Felsblock
            p.moveTo(rx - W * 0.2, g + 6)
            p.cubicTo(rx - W * 0.2, g - H * 0.1, rx - W * 0.05, g - H * 0.14, rx + W * 0.06, g - H * 0.12)
            p.cubicTo(rx + W * 0.16, g - H * 0.1, rx + W * 0.2, g - H * 0.04, rx + W * 0.2, g + 6)
            p.close()
            c.drawPath(p, paint)

    def _draw_weather(self, c, hour: float) -> None:
        W, H, g = self.W, self.H, self.ground
        weather = self.world["weather"]
        storm = _phase(hour, 12.6, 13.0) * (1 - _phase(hour, 15.2, 15.6))
        if weather == "rain":
            if storm > 0:
                self._draw_rain(c, hour)
            return
        light = weather == "snow" and 2.0 <= hour < 6.5
        amount = max(storm, 0.35 * _phase(hour, 2.0, 2.5) * (1 - _phase(hour, 6.0, 6.5)) if light else 0.0)
        if amount <= 0:
            return
        if weather == "snow":
            dot = skia.Paint(AntiAlias=True, Color=color(WHITE, 0.85 * amount))
            n = int(len(self.flakes) * (0.4 + 0.6 * amount))
            for x, y, s in self.flakes[:n]:
                c.drawCircle(float(x), float(y), W * 0.004 * s + 1, dot)
            c.drawRect(skia.Rect(0, 0, W, g), skia.Paint(Color=color((236, 240, 248), 0.22 * storm)))
        else:
            sand = (226, 180, 120)
            line = skia.Paint(AntiAlias=True, StrokeWidth=max(1.5, W * 0.0025), Color=color(sand, 0.55 * amount))
            for x, y, s in self.flakes:
                c.drawLine(float(x), float(y), float(x) + W * 0.04 * s, float(y) - H * 0.002, line)
            c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Color=color((206, 150, 90), 0.3 * storm)))
            if weather == "dust" and storm > 0.2:  # Steppenläufer
                weed = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=W * 0.004,
                                  Color=color((70, 50, 36), storm))
                for k in range(2):
                    p = (self.t * 0.4 + k * 0.55) % 1.6
                    r = W * (0.045 + 0.015 * k)
                    wx = W * (1.2 - p)
                    wy = g - r - abs(math.sin(self.t * 4 + k)) * H * 0.03
                    c.drawCircle(wx, wy, r, weed)
                    for j in range(5):
                        a = self.t * -6 + j * 1.3
                        c.drawLine(wx + math.cos(a) * r, wy + math.sin(a) * r, wx - math.cos(a + 2) * r * 0.6,
                                   wy - math.sin(a + 2) * r * 0.6, weed)

    def _draw_aurora(self, c, night: float) -> None:
        if night <= 0:
            return
        W, H = self.W, self.H
        for k, (rgb, base, amp, speed) in enumerate((((80, 255, 170), 0.16, 0.04, 0.6), ((160, 110, 255), 0.23, 0.05, -0.45),
                                                    ((70, 220, 255), 0.11, 0.03, 0.8))):
            path = skia.Path()
            for i in range(41):
                x = W * i / 40
                y = H * base + math.sin(i * 0.35 + self.t * speed + k) * H * amp + math.sin(i * 0.9 + self.t * speed * 1.7) * H * amp * 0.4
                (path.moveTo if i == 0 else path.lineTo)(x, y)
            c.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=H * 0.05,
                                        Color=color(rgb, 0.28 * night),
                                        MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, W * 0.02)))

    def _draw_fireflies(self, c, night: float) -> None:
        if night <= 0:
            return
        W, H = self.W, self.H
        for x, y, ph, sp in self.fireflies:
            xx = x + math.sin(self.t * sp + ph) * W * 0.03
            yy = y + math.cos(self.t * sp * 1.3 + ph) * H * 0.015
            glow = night * (0.5 + 0.5 * math.sin(self.t * 3 * sp + ph))
            c.drawCircle(xx, yy, W * 0.012, skia.Paint(AntiAlias=True, Color=color((220, 255, 120), 0.18 * glow)))
            c.drawCircle(xx, yy, W * 0.004, skia.Paint(AntiAlias=True, Color=color((240, 255, 170), glow)))

    def _draw_text(self, c, hour: float) -> None:
        W, H = self.W, self.H
        if self.t < 2.4:
            a = 1 - _phase(self.t, 1.8, 2.4)
            t1, t2 = self.world["title"]
            text_center(c, t1, W / 2, H * 0.12, W * 0.12, alpha=a, shadow=True)
            text_center(c, t2, W / 2, H * 0.19, W * (0.085 if len(t2) < 16 else 0.072), (255, 220, 150), a, shadow=True)
            return
        shown = min(24, int(hour))
        label = [t for h0, t in zip(BEAT_HOURS, self.world["beats"]) if hour >= h0][-1]
        a = _phase(self.t, 2.4, 2.8)
        text_center(c, f"HOUR {shown}", W / 2, H * 0.11, W * 0.11, alpha=a, shadow=True)
        text_center(c, label, W / 2, H * 0.17, W * 0.065, (255, 220, 150), a, shadow=True)
        bar = skia.Rect(W * 0.2, H * 0.205, W * 0.2 + W * 0.6 * min(1.0, hour / 24), H * 0.205 + W * 0.012)
        c.drawRoundRect(skia.Rect(W * 0.2, H * 0.205, W * 0.8, H * 0.205 + W * 0.012), 8, 8,
                        skia.Paint(AntiAlias=True, Color=color(WHITE, 0.25 * a)))
        c.drawRoundRect(bar, 8, 8, skia.Paint(AntiAlias=True, Color=color((255, 200, 90), a)))

    def _draw_skeleton_scene(self, c, hour: float) -> None:
        W, H, g = self.W, self.H, self.ground
        x, facing, pose, scale, rot = W * 0.42, 1, "stand", 1.0, 0.0
        jaw, shake = 0.0, 0.0
        if hour < 1.2:
            x = W * (0.3 + 0.12 * _phase(hour, 0.3, 1.2))
            scale = _phase(hour, 0.15, 0.6)
            pose = "walk" if hour > 0.6 else "stand"
        elif hour < 6.5:
            pose = "walk"
        elif hour < 7.4:
            jaw = _phase(hour, 6.6, 6.9) * 0.6
            shake = 1.0 if hour > 6.9 else 0.0
        elif hour < 10.0:
            pose, facing, x, jaw = "run", -1, W * 0.4, 0.5
        elif hour < 12.4:
            pose, x = "crouch", W * 0.27
        elif hour < 15.6:
            shake = 0.4
        elif hour < 18.8:
            pose = "stand"
        elif hour < 22.7:
            pose, rot = "sleep", -math.pi / 2
        else:
            p = _phase(hour, 23.0, 23.6)
            x = W * (0.42 + 0.3 * p)
            pose = "walk" if 23.0 <= hour < 23.6 else "stand"
            scale = 1 - _phase(hour, 23.6, 23.9)
        if scale <= 0.01:
            return
        if shake:
            x += self.fx.uniform(-1, 1) * W * 0.004 * shake
        self.skeleton(c, x, g, self.S * scale, facing, pose, jaw, rot)
        if pose == "sleep":
            for k in range(3):
                ph = (self.t * 0.5 + k / 3) % 1
                text_center(c, "Z", x + W * 0.05 + ph * W * 0.08, g - H * 0.08 - ph * H * 0.08, W * (0.04 + 0.03 * ph),
                            alpha=1 - ph)

    # --- Nachspiel zu Hause ---------------------------------------------------------------------
    def _draw_home(self, c, e: float) -> None:
        W, H, g = self.W, self.H, self.ground
        c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(0, g)], [color((10, 12, 40)), color((70, 40, 96))])))
        dot = skia.Paint(AntiAlias=True)
        for x, y, r, ph in self.stars[:60]:
            dot.setColor(color(WHITE, 0.5 + 0.4 * math.sin(self.t * 2 + ph)))
            c.drawCircle(x, y, r, dot)
        c.drawCircle(W * 0.8, H * 0.28, W * 0.045, skia.Paint(AntiAlias=True, Color=color((240, 236, 220))))
        if self.layers:
            img, top = self.layers["city"]
            c.drawImage(img, 0, top, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(
                ColorFilter=skia.ColorFilters.Blend(color((20, 20, 46)), skia.BlendMode.kSrcIn)))
            img, top = self.layers["windows"]
            c.drawImage(img, 0, top)
        c.drawRect(skia.Rect(0, g, W, H), skia.Paint(Color=color((12, 12, 22))))
        c.drawRect(skia.Rect(0, g, W, g + H * 0.006), skia.Paint(Color=color((90, 84, 110))))
        px, py = W * 0.3, g - H * 0.11
        if self.ending == "pet":
            size = _smooth(e / 0.5) * (1 - _smooth((e - 3.4) / 0.4))
        else:
            size = _smooth(e / 0.5) * (1 + 0.25 * _smooth((e - 2.6) / 0.6))
        if size > 0.01:
            r = H * 0.1 * size
            for k, (rgb, w, speed) in enumerate((((0, 230, 255), 0.012, 1.5), ((180, 80, 255), 0.008, -2.2),
                                                ((255, 255, 255), 0.004, 3.0))):
                rr = r * (1 - k * 0.14)
                c.drawOval(skia.Rect(px - rr * 0.62, py - rr, px + rr * 0.62, py + rr), skia.Paint(
                    AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=W * w, Color=color(rgb, 0.95),
                    PathEffect=skia.DashPathEffect.Make([rr * 0.5, rr * 0.18], self.t * 300 * speed)))
            c.drawOval(skia.Rect(px - r * 0.5, py - r * 0.85, px + r * 0.5, py + r * 0.85),
                       skia.Paint(AntiAlias=True, Color=color((20, 10, 40), 0.85 if self.ending == "eyes" else 0.3)))
        sx, hop, facing = W * 0.58, 0.0, 1
        if e < 1.2:
            f = _smooth((e - 0.5) / 0.7)
            sx = px + (W * 0.58 - px) * f
            hop = -math.sin(math.pi * f) * H * 0.09
        if e >= (2.3 if self.ending == "pet" else 2.7):
            facing = -1
        scale = _smooth((e - 0.45) / 0.15)
        shaking = 1.0 if self.ending == "eyes" and e >= 3.1 else 0.0
        jaw = 0.55 * _smooth((e - 3.1) / 0.3) if self.ending == "eyes" else 0.0
        arm = _smooth((e - 4.6) / 0.5) * 0.8 if self.ending == "pet" else 0.0
        sx += self.fx.uniform(-1, 1) * W * 0.003 * shaking
        if scale > 0.01:
            self.skeleton(c, sx, g + hop, self.S * scale, facing, "stand", jaw, 0.0, arm, 0.0)
        if self.ending == "pet":
            self._draw_pet(c, e, px, sx)
        elif e >= 3.0:
            blink = 0.15 if math.sin(self.t * 1.7) > 0.96 else 1.0
            glow = _smooth((e - 3.0) / 0.4)
            for dx in (-1, 1):
                ex, ey = px + dx * W * 0.035, py - H * 0.01
                c.drawCircle(ex, ey, W * 0.03, skia.Paint(AntiAlias=True, Color=color((255, 200, 60), 0.3 * glow)))
                c.drawOval(skia.Rect(ex - W * 0.018, ey - W * 0.012 * blink, ex + W * 0.018, ey + W * 0.012 * blink),
                           skia.Paint(AntiAlias=True, Color=color((255, 214, 90), glow)))
                c.drawOval(skia.Rect(ex - W * 0.004, ey - W * 0.011 * blink, ex + W * 0.004, ey + W * 0.011 * blink),
                           skia.Paint(AntiAlias=True, Color=color((30, 12, 8), glow)))
        label = "BACK HOME"
        if self.ending == "pet" and e >= 5.2:
            label = "NEW PET"
        elif self.ending == "eyes" and e >= 4.4:
            label = "PART 2?"
        text_center(c, "2026", W / 2, H * 0.11, W * 0.12, alpha=_smooth(e / 0.5), shadow=True)
        text_center(c, label, W / 2, H * 0.17, W * 0.07, (255, 220, 150), 1.0, shadow=True)

    def _draw_pet(self, c, e: float, px: float, sx: float) -> None:
        if e < 1.8:
            return
        W, H, g = self.W, self.H, self.ground
        kind, rgb = self.world["pet"], self.world["pet_rgb"]
        L = W * 0.15
        target = sx - W * 0.16
        if e < 2.3:  # springt aus dem Portal
            f = _smooth((e - 1.8) / 0.5)
            x, y, facing = px + W * 0.04 * f, g - math.sin(math.pi * f) * H * 0.07, 1
        elif e < 2.8:
            x, y, facing = px + W * 0.04, g - abs(math.sin(self.t * 9)) * H * 0.006, 1
        elif e < 3.8:  # rennt zum Skelett
            f = _smooth((e - 2.8) / 1.0)
            x, y, facing = px + W * 0.04 + (target - px - W * 0.04) * f, g - abs(math.sin(self.t * 12)) * H * 0.01, 1
        else:  # hüpft vor Freude
            x, y, facing = target, g - abs(math.sin(self.t * 5)) * H * 0.02, 1
        quadruped(c, kind, x, y, L, facing, self.t * 12, rgb, gallop=2.8 <= e < 3.8, cute=True,
                  wing=math.sin(self.t * 10) if kind == "dragon" else None)
        if e >= 5.3:
            self._draw_hearts(c, x, y - H * 0.08)
