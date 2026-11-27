"""Tiere als Schattenrisse für die Story-Videos: ein Baukasten für Vierbeiner, Vögel und Reiter.

Jedes Tier ist ein Steckbrief (SPECIES) aus Körperproportionen und Extras – Rüssel, Stoßzähne, Mähne,
Höcker, Geweih, Flügel. Alle Maße relativ zur Körperlänge L. `cute=True` zeichnet ein Jungtier mit großem
Kopf und Augen (für das Haustier am Ende).
"""

from __future__ import annotations

import math

import skia

from content_crew.animation.engine import WHITE, color, mix

TAU = 2 * math.pi
BLACK = (0, 0, 0)

SPECIES: dict[str, dict] = {
    "mammoth": dict(body_h=0.62, leg=0.5, leg_w=0.17, neck=0.12, neck_angle=10, neck_w=0.34, head=0.34,
                    head_h=0.34, tail=0.18, hump=0.22, trunk=0.7, tusks=0.55, ears="small", fur=True),
    "elephant": dict(body_h=0.58, leg=0.55, leg_w=0.16, neck=0.1, neck_angle=5, neck_w=0.32, head=0.32,
                     head_h=0.32, tail=0.22, trunk=0.65, tusks=0.28, ears="big"),
    "sabertooth": dict(body_h=0.34, leg=0.42, leg_w=0.1, neck=0.16, neck_angle=25, neck_w=0.18, head=0.26,
                       head_h=0.18, tail=0.2, fangs=0.14, ears="cat"),
    "jaguar": dict(body_h=0.3, leg=0.36, leg_w=0.085, neck=0.15, neck_angle=20, neck_w=0.15, head=0.22,
                   head_h=0.15, tail=0.62, tail_curl=0.5, ears="cat"),
    "lion": dict(body_h=0.34, leg=0.42, leg_w=0.1, neck=0.14, neck_angle=25, neck_w=0.2, head=0.24,
                 head_h=0.18, tail=0.55, tail_tuft=True, mane=0.3, ears="cat"),
    "polarbear": dict(body_h=0.44, leg=0.4, leg_w=0.15, neck=0.24, neck_angle=-5, neck_w=0.24, head=0.26,
                      head_h=0.17, tail=0.06, ears="round"),
    "camel": dict(body_h=0.36, leg=0.75, leg_w=0.07, neck=0.5, neck_angle=55, neck_w=0.11, head=0.24,
                  head_h=0.11, head_angle=-15, tail=0.2, hump=0.3, ears="small"),
    "crocodile": dict(body_h=0.2, leg=0.12, leg_w=0.07, neck=0.06, neck_angle=0, neck_w=0.14, head=0.42,
                      head_h=0.1, tail=0.7, tail_w=0.13, low=True, spikes=True, jaw=True),
    "giraffe": dict(body_h=0.42, leg=0.9, leg_w=0.07, neck=1.05, neck_angle=68, neck_w=0.11, head=0.24,
                    head_h=0.11, head_angle=-25, tail=0.35, ossicones=True, ears="small"),
    "horse": dict(body_h=0.4, leg=0.6, leg_w=0.08, neck=0.38, neck_angle=50, neck_w=0.16, head=0.32,
                  head_h=0.13, head_angle=-40, tail=0.4, tail_flow=True, mane_neck=True, ears="small"),
    "reindeer": dict(body_h=0.4, leg=0.58, leg_w=0.07, neck=0.3, neck_angle=45, neck_w=0.15, head=0.25,
                     head_h=0.12, head_angle=-30, tail=0.08, antlers=True, ears="small"),
    "bison": dict(body_h=0.58, leg=0.38, leg_w=0.12, neck=0.1, neck_angle=-15, neck_w=0.34, head=0.24,
                  head_h=0.24, head_angle=-35, tail=0.25, hump=0.3, hump_pos=0.25, horns=True, beard=True),
    "wolf": dict(body_h=0.3, leg=0.42, leg_w=0.07, neck=0.2, neck_angle=30, neck_w=0.14, head=0.26,
                 head_h=0.12, tail=0.45, tail_down=True, ears="pointy"),
    "dragon": dict(body_h=0.4, leg=0.42, leg_w=0.12, neck=0.5, neck_angle=40, neck_w=0.13, head=0.3,
                   head_h=0.13, head_angle=-10, tail=1.0, tail_w=0.1, wings=1.2, spikes=True, horns_back=True),
    "cat": dict(body_h=0.32, leg=0.38, leg_w=0.08, neck=0.14, neck_angle=35, neck_w=0.14, head=0.22,
                head_h=0.17, tail=0.7, tail_curl=0.9, ears="pointy"),
}


def _paint(rgb, alpha=1.0) -> skia.Paint:
    return skia.Paint(AntiAlias=True, Color=color(rgb, alpha))


def _stroke(rgb, width, alpha=1.0) -> skia.Paint:
    return skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeCap=skia.Paint.kRound_Cap,
                      StrokeJoin=skia.Paint.kRound_Join, StrokeWidth=width, Color=color(rgb, alpha))


def quadruped(c: skia.Canvas, kind: str, x: float, ground: float, L: float, facing: int, phase: float, rgb,
              gallop: bool = False, eye=None, cute: bool = False, alpha: float = 1.0, jaw: float = 0.0,
              wing: float | None = None) -> tuple[float, float]:
    """Zeichnet ein Tier; x = Körpermitte, ground = Boden, L = Körperlänge. Gibt die Kopfposition zurück."""
    s = dict(SPECIES[kind])
    f = 1 if facing >= 0 else -1
    if cute:  # Jungtier: kurzer Körper, kurze Beine, großer Kopf
        s.update(leg=s["leg"] * 0.62, head=s["head"] * 1.55, head_h=s["head_h"] * 1.7, neck=s["neck"] * 0.6,
                 tusks=s.get("tusks", 0) * 0.3, mane=0, fangs=0, trunk=s.get("trunk", 0) * 0.6,
                 wings=s.get("wings", 0) * 0.55, horns=False, antlers=False)
    bh = L * s["body_h"]
    leg = L * s["leg"]
    amp = 0.75 if gallop else 0.42
    bob = -abs(math.sin(phase)) * L * (0.05 if gallop else 0.012)
    belly = ground - leg + bob
    top = belly - bh
    cy = (top + belly) / 2
    body = _paint(rgb, alpha)
    far_rgb = mix(rgb, WHITE, 0.12) if sum(rgb) < 200 else mix(rgb, BLACK, 0.18)

    # Beine: hinten/vorne, jeweils fern und nah
    lw = L * s["leg_w"]
    hip, shoulder = x - f * L * 0.32, x + f * L * 0.3
    offsets = ((0.0, 0.5), (math.pi, math.pi + 0.5)) if gallop else ((0.0, math.pi / 2), (math.pi, math.pi * 1.5))

    def draw_leg(px, py, off, front, paint_rgb):
        a = math.sin(phase + off) * amp
        lift = max(0.0, math.cos(phase + off)) * (0.9 if gallop else 0.5)
        total = ground - py
        if s.get("low"):  # Krokodil: kurze, abgespreizte Beine
            c.drawLine(px, py, px + f * math.sin(a) * total * 1.3, ground, _stroke(paint_rgb, lw, alpha))
            return
        thigh, shin = total * 0.52, total * 0.52
        kx, ky = px + f * math.sin(a) * thigh, py + math.cos(a) * thigh
        b = a + (lift if front else -lift)
        fx, fy = kx + f * math.sin(b) * shin, min(ground, ky + math.cos(b) * shin)
        p = _stroke(paint_rgb, lw, alpha)
        c.drawLine(px, py, kx, ky, p)
        p.setStrokeWidth(lw * 0.8)
        c.drawLine(kx, ky, fx, fy, p)

    hip_y, sh_y = cy + bh * 0.15, cy + bh * 0.1
    draw_leg(hip, hip_y, offsets[0][1], False, far_rgb)
    draw_leg(shoulder, sh_y, offsets[1][1], True, far_rgb)

    # Schwanz
    tl = L * s.get("tail", 0.2)
    if tl > 0:
        tx, ty = x - f * L * 0.5, top + bh * (0.5 if s.get("low") else 0.25)
        wag = math.sin(phase * 0.7) * tl * 0.15
        tail = skia.Path()
        tail.moveTo(tx, ty)
        if s.get("low"):
            ex, ey = tx - f * tl, ground - bh * 0.15 + wag * 0.3
            tail.quadTo(tx - f * tl * 0.5, ty + bh * 0.2, ex, ey)
        elif s.get("tail_curl"):
            ex, ey = tx - f * tl * 0.55, ty - tl * 0.35 * s["tail_curl"] + wag
            tail.quadTo(tx - f * tl * 0.5, ty + tl * 0.45, ex, ey)
        elif s.get("tail_down") or s.get("tail_flow"):
            ex, ey = tx - f * tl * 0.45, ty + tl * 0.85 + wag * 0.3
            tail.quadTo(tx - f * tl * 0.55, ty + tl * 0.2, ex, ey)
        else:
            ex, ey = tx - f * tl * 0.4, ty + tl * 0.9 + wag * 0.2
            tail.quadTo(tx - f * tl * 0.35, ty + tl * 0.3, ex, ey)
        if s.get("low"):  # dicker Ansatz, dünne Spitze
            meas = skia.PathMeasure(tail, False)
            n, total_len = 8, meas.getLength()
            for k in range(n):
                seg = skia.Path()
                meas.getSegment(total_len * k / n, total_len * (k + 1) / n + 1, seg, True)
                c.drawPath(seg, _stroke(rgb, L * s.get("tail_w", 0.05) * (1 - 0.8 * k / n), alpha))
        else:
            c.drawPath(tail, _stroke(rgb, L * s.get("tail_w", 0.05) * (1.6 if s.get("tail_flow") else 1), alpha))
        if s.get("tail_tuft"):
            c.drawCircle(ex, ey, L * 0.045, body)

    # Körper (mit Höcker)
    rr = skia.RRect.MakeRectXY(skia.Rect(x - L * 0.5, top, x + L * 0.5, belly), bh * 0.5, bh * 0.5)
    c.drawRRect(rr, body)
    if s.get("hump"):
        hp = x + f * L * (s.get("hump_pos", 0.0) - 0.05)
        c.drawOval(skia.Rect(hp - L * 0.26, top - bh * s["hump"] * 1.2, hp + L * 0.26, top + bh * 0.5), body)
    if s.get("spikes"):
        sp = skia.Path()
        n = 7
        for k in range(n):
            px = x - f * L * 0.45 + f * L * 0.9 * k / (n - 1)
            sp.moveTo(px - L * 0.04, top + bh * 0.08)
            sp.lineTo(px, top - bh * 0.28)
            sp.lineTo(px + L * 0.04, top + bh * 0.08)
        c.drawPath(sp, body)
    if s.get("fur"):  # zottelige Unterkante
        fur = skia.Path()
        for k in range(9):
            px = x - L * 0.45 + L * 0.9 * k / 8
            fur.moveTo(px - L * 0.04, belly - bh * 0.1)
            fur.lineTo(px, belly + bh * 0.16)
            fur.lineTo(px + L * 0.04, belly - bh * 0.1)
        c.drawPath(fur, body)

    # Flügel (Drache): Fledermausflügel mit Fingerknochen und gewelltem Rand
    if s.get("wings"):
        wf = math.sin(phase * 0.8) if wing is None else wing
        span = L * s["wings"]
        rx, ry = x + f * L * 0.08, top + bh * 0.25
        wrist = (rx + f * span * 0.12, ry - span * (0.62 + 0.3 * wf))
        tips = [(rx - f * span * 0.62, ry - span * (0.32 + 0.22 * wf)), (rx - f * span * 0.42, ry - span * 0.05),
                (rx - f * span * 0.12, ry + bh * 0.05)]
        wpath = skia.Path()
        wpath.moveTo(rx, ry)
        wpath.lineTo(*wrist)
        wpath.lineTo(*tips[0])
        prev = tips[0]
        for tip in tips[1:]:
            mx, my = (prev[0] + tip[0]) / 2, (prev[1] + tip[1]) / 2
            wpath.quadTo(mx + f * span * 0.05, my - span * 0.02, tip[0], tip[1])
            prev = tip
        wpath.close()
        c.drawPath(wpath, _paint(far_rgb, alpha))
        bone = _stroke(rgb, L * 0.03, alpha)
        c.drawLine(rx, ry, wrist[0], wrist[1], bone)
        bone.setStrokeWidth(L * 0.018)
        for tip in tips:
            c.drawLine(wrist[0], wrist[1], tip[0], tip[1], bone)

    # nahe Beine
    draw_leg(hip, hip_y, offsets[0][0], False, rgb)
    draw_leg(shoulder, sh_y, offsets[1][0], True, rgb)

    # Hals und Kopf
    na = math.radians(s.get("neck_angle", 20))
    nl = L * s.get("neck", 0.2)
    nx0, ny0 = x + f * L * 0.38, top + bh * 0.3
    nx1, ny1 = nx0 + f * math.cos(na) * nl, ny0 - math.sin(na) * nl
    c.drawLine(nx0, ny0, nx1, ny1, _stroke(rgb, L * s.get("neck_w", 0.15), alpha))
    if s.get("mane_neck"):
        mane = skia.Path()
        for k in range(6):
            fx = nx0 + (nx1 - nx0) * k / 6
            fy = ny0 + (ny1 - ny0) * k / 6
            mane.moveTo(fx, fy - L * 0.04)
            mane.lineTo(fx - f * L * 0.06, fy - L * 0.09)
        c.drawPath(mane, _stroke(rgb, L * 0.03, alpha))
    hl, hh = L * s.get("head", 0.25), L * s.get("head_h", 0.15)
    ha = math.radians(s.get("head_angle", 0))
    c.save()
    c.translate(nx1, ny1)
    c.rotate(math.degrees(-ha) * f)
    hx0 = -f * hl * 0.2
    if s.get("mane"):
        mane = skia.Path()
        cx0, rad = hx0 + f * hl * 0.2, L * s["mane"] * 0.8
        for k in range(14):
            a = TAU * k / 14
            r = rad * (1.0 if k % 2 == 0 else 0.78)
            (mane.moveTo if k == 0 else mane.lineTo)(cx0 + math.cos(a) * r, math.sin(a) * r * 0.95)
        mane.close()
        c.drawPath(mane, body)
    head_rect = skia.Rect(min(hx0, hx0 + f * hl), -hh * 0.55, max(hx0, hx0 + f * hl), hh * 0.45)
    c.drawRRect(skia.RRect.MakeRectXY(head_rect, hh * 0.5, hh * 0.5), body)
    if s.get("jaw"):  # Maul auf/zu
        opening = jaw * hh * 1.2
        lower = skia.Rect(min(hx0, hx0 + f * hl), hh * 0.2 + opening * 0.3, max(hx0, hx0 + f * hl), hh * 0.45 + opening)
        c.drawRRect(skia.RRect.MakeRectXY(lower, hh * 0.25, hh * 0.25), body)
    ears = s.get("ears")
    ex = hx0 + f * hl * 0.15
    if ears == "big":
        c.drawOval(skia.Rect(ex - f * hl * 0.3 - hl * 0.32, -hh * 1.05, ex - f * hl * 0.3 + hl * 0.32, hh * 0.95),
                   _paint(mix(rgb, WHITE, 0.08) if sum(rgb) < 200 else mix(rgb, BLACK, 0.1), alpha))
    elif ears in ("cat", "pointy"):
        tip_h = hh * (0.55 if ears == "cat" else 0.8)
        for dx in (0.0, f * hl * 0.22):
            ear = skia.Path()
            ear.moveTo(ex + dx - hl * 0.09, -hh * 0.4)
            ear.lineTo(ex + dx, -hh * 0.4 - tip_h)
            ear.lineTo(ex + dx + hl * 0.09, -hh * 0.4)
            ear.close()
            c.drawPath(ear, body)
    elif ears in ("round", "small"):
        c.drawCircle(ex, -hh * 0.45, hh * (0.22 if ears == "round" else 0.16), body)
    if s.get("antlers"):
        ant = _stroke(rgb, L * 0.025, alpha)
        for side in (0.0, f * hl * 0.12):
            bx, by = ex + side, -hh * 0.45
            c.drawLine(bx, by, bx - f * hl * 0.3, by - hh * 2.2, ant)
            for k in range(3):
                py = by - hh * (0.7 + k * 0.55)
                px = bx - f * hl * 0.3 * (0.3 + k * 0.25)
                c.drawLine(px, py, px + f * hl * 0.3, py - hh * 0.5, ant)
    if s.get("ossicones"):
        c.drawLine(ex, -hh * 0.4, ex - f * hl * 0.05, -hh * 1.1, _stroke(rgb, L * 0.022, alpha))
    if s.get("horns"):
        horn = skia.Path()
        horn.moveTo(ex, -hh * 0.35)
        horn.quadTo(ex + f * hl * 0.25, -hh * 0.95, ex + f * hl * 0.38, -hh * 0.55)
        c.drawPath(horn, _stroke(rgb, L * 0.035, alpha))
    if s.get("horns_back"):
        horn = skia.Path()
        horn.moveTo(ex, -hh * 0.3)
        horn.quadTo(ex - f * hl * 0.3, -hh * 1.2, ex - f * hl * 0.6, -hh * 1.1)
        c.drawPath(horn, _stroke(rgb, L * 0.03, alpha))
    if s.get("beard"):
        c.drawOval(skia.Rect(hx0 + f * hl * 0.3 - hl * 0.15, hh * 0.2, hx0 + f * hl * 0.3 + hl * 0.15, hh * 1.1), body)
    if s.get("trunk"):
        tl2 = L * s["trunk"]
        sway = math.sin(phase * 0.6) * tl2 * 0.12
        trunk = skia.Path()
        sx, sy = hx0 + f * hl * 0.85, hh * 0.1
        trunk.moveTo(sx, sy)
        trunk.cubicTo(sx + f * tl2 * 0.25, sy + tl2 * 0.35, sx + f * tl2 * 0.1 + sway, sy + tl2 * 0.75,
                      sx + f * tl2 * 0.22 + sway, sy + tl2 * 0.9)
        c.drawPath(trunk, _stroke(rgb, L * 0.07, alpha))
    if s.get("tusks"):
        tk = L * s["tusks"]
        tusk = skia.Path()
        sx, sy = hx0 + f * hl * 0.7, hh * 0.35
        tusk.moveTo(sx, sy)
        tusk.cubicTo(sx + f * tk * 0.15, sy + tk * 0.5, sx + f * tk * 0.6, sy + tk * 0.55, sx + f * tk * 0.75, sy + tk * 0.15)
        c.drawPath(tusk, _stroke(mix(rgb, (240, 232, 210), 0.85 if sum(rgb) < 200 else 0.4), L * 0.035, alpha))
    if s.get("fangs"):
        fg = L * s["fangs"]
        fang = skia.Path()
        fx0 = hx0 + f * hl * 0.72
        fang.moveTo(fx0 - hl * 0.06, hh * 0.3)
        fang.lineTo(fx0 + f * hl * 0.02, hh * 0.3 + fg)
        fang.lineTo(fx0 + hl * 0.06, hh * 0.3)
        fang.close()
        c.drawPath(fang, _paint(mix(rgb, (245, 240, 225), 0.9), alpha))
    # Auge
    eye_x, eye_y = hx0 + f * hl * (0.42 if not cute else 0.5), -hh * (0.12 if not cute else 0.05)
    if cute:
        r = hh * 0.26
        c.drawCircle(eye_x, eye_y, r, _paint(WHITE, alpha))
        c.drawCircle(eye_x + f * r * 0.25, eye_y + r * 0.05, r * 0.6, _paint((20, 18, 26), alpha))
        c.drawCircle(eye_x + f * r * 0.42, eye_y - r * 0.25, r * 0.22, _paint(WHITE, alpha))
        c.drawCircle(eye_x - f * r * 0.2, eye_y + r * 1.3, r * 0.5, _paint((255, 140, 150), 0.6 * alpha))
    elif eye is not None:
        rgb_eye, glow = eye
        c.drawCircle(eye_x, eye_y, max(2.0, hh * 0.1), _paint(rgb_eye, glow * alpha))
    c.restore()
    head_x = nx1 + f * hl * 0.8 * math.cos(ha)
    head_y = ny1 - f * hl * 0.8 * math.sin(-ha) * f
    return head_x, head_y


def bird(c: skia.Canvas, x: float, y: float, size: float, phase: float, rgb, alpha: float = 1.0) -> None:
    """Vogel im Flug (Schattenriss): zwei schlagende Flügel."""
    flap = math.sin(phase)
    p = skia.Path()
    p.moveTo(x - size, y - flap * size * 0.55)
    p.quadTo(x - size * 0.45, y - size * 0.05 - flap * size * 0.2, x, y + size * 0.12)
    p.quadTo(x + size * 0.45, y - size * 0.05 - flap * size * 0.2, x + size, y - flap * size * 0.55)
    c.drawPath(p, _stroke(rgb, size * 0.14, alpha))
    c.drawCircle(x, y + size * 0.1, size * 0.12, _paint(rgb, alpha))


def rider(c: skia.Canvas, x: float, y: float, size: float, facing: int, rgb, kind: str = "knight",
          phase: float = 0.0, alpha: float = 1.0) -> None:
    """Reiter (Ritter mit Lanze und Fahne oder Wüstenreiter mit Tuch). y = Rückenhöhe des Tiers, size ≈ Rumpf."""
    f = 1 if facing >= 0 else -1
    body = _paint(rgb, alpha)
    bob = math.sin(phase * 2) * size * 0.03
    hip = (x, y + bob)
    neck = (x + f * size * 0.08, y - size * 0.62 + bob)
    c.drawLine(hip[0], hip[1] + size * 0.05, hip[0] + f * size * 0.12, hip[1] + size * 0.48, _stroke(rgb, size * 0.16, alpha))
    c.drawLine(hip[0], hip[1], neck[0], neck[1], _stroke(rgb, size * 0.38, alpha))
    c.drawCircle(neck[0] + f * size * 0.02, neck[1] - size * 0.16, size * 0.17, body)
    if kind == "knight":
        helm = skia.Path()  # Helmbusch
        hx, hy = neck[0] - f * size * 0.02, neck[1] - size * 0.26
        helm.moveTo(hx, hy)
        helm.quadTo(hx - f * size * 0.2, hy - size * 0.12, hx - f * size * 0.32, hy + size * 0.05)
        c.drawPath(helm, _stroke(rgb, size * 0.07, alpha))
        hand = (neck[0] + f * size * 0.22, neck[1] + size * 0.25)
        c.drawLine(neck[0], neck[1] + size * 0.12, hand[0], hand[1], _stroke(rgb, size * 0.1, alpha))
        top = (hand[0] - f * size * 0.1, hand[1] - size * 1.1)
        c.drawLine(hand[0] + f * size * 0.03, hand[1] + size * 0.25, top[0], top[1], _stroke(rgb, size * 0.05, alpha))
        flag = skia.Path()
        wave = math.sin(phase * 1.7) * size * 0.05
        flag.moveTo(*top)
        flag.quadTo(top[0] - f * size * 0.2, top[1] + size * 0.02 + wave, top[0] - f * size * 0.42, top[1] + size * 0.1 + wave)
        flag.lineTo(top[0] - f * size * 0.36, top[1] + size * 0.17 + wave)
        flag.lineTo(top[0], top[1] + size * 0.24)
        flag.close()
        c.drawPath(flag, body)
    else:  # Tuch, das im Wind weht
        cloth = skia.Path()
        cx0, cy0 = neck[0] - f * size * 0.06, neck[1] - size * 0.2
        wave = math.sin(phase * 1.5) * size * 0.06
        cloth.moveTo(cx0, cy0)
        cloth.quadTo(cx0 - f * size * 0.3, cy0 + size * 0.05 + wave, cx0 - f * size * 0.5, cy0 + size * 0.2 + wave)
        c.drawPath(cloth, _stroke(rgb, size * 0.1, alpha))
