"""Produktbilder für die Shop-Vorschau: gezeichnete Packshots im einheitlichen Studio-Stil (SVG, 400 × 300).

Echte Fotos liefert später der Lieferant. Bis dahin zeigen die Illustrationen, wie das Produkt aussieht.
Unbekannte Produkte bekommen ein Kategoriebild.
"""

from __future__ import annotations

ICONS = {  # Kategorie-Symbole (24×24, Strichzeichnung) – für Menü und Ersatzbilder
    "Auto & Unterwegs": '<path d="M5 16h14M6.5 16l1.6-5.2A2 2 0 0 1 10 9.4h4a2 2 0 0 1 1.9 1.4l1.6 5.2"/>'
                        '<rect x="3.5" y="13" width="17" height="5" rx="2"/><circle cx="7.5" cy="18.5" r="1.6"/>'
                        '<circle cx="16.5" cy="18.5" r="1.6"/>',
    "Ordnung & Zuhause": '<path d="M4 11.5 12 5l8 6.5"/><path d="M6.5 10v9h11v-9"/><rect x="10" y="13.5" width="4" '
                         'height="5.5"/>',
    "Reisen": '<rect x="5" y="8" width="14" height="11" rx="2.5"/><path d="M9.5 8V6.2a1.2 1.2 0 0 1 1.2-1.2h2.6a1.2 '
              '1.2 0 0 1 1.2 1.2V8M9 11.5v4M15 11.5v4"/>',
    "Sport & Fitness": '<path d="M3.5 12h17"/><rect x="5.5" y="8" width="3" height="8" rx="1"/><rect x="15.5" y="8" '
                       'width="3" height="8" rx="1"/><path d="M3.5 10.5v3M20.5 10.5v3"/>',
    "Haustiere": '<circle cx="8" cy="8.5" r="1.7"/><circle cx="16" cy="8.5" r="1.7"/><circle cx="5" cy="12.5" r="1.5"/>'
                 '<circle cx="19" cy="12.5" r="1.5"/><path d="M12 12c-2.6 0-4.5 2.5-4.5 4.2 0 1.6 1.4 2.3 2.7 '
                 '2 1-.2 1.2-.5 1.8-.5s.8.3 1.8.5c1.3.3 2.7-.4 2.7-2 0-1.7-1.9-4.2-4.5-4.2z"/>',
    "Schreibtisch & Handy": '<rect x="8" y="3.5" width="8" height="15" rx="2"/><path d="M11 15.5h2M6 21h12"/>',
    "Kunst & Poster": '<rect x="5" y="4" width="14" height="16" rx="1"/><path d="M7 16l3.5-4 3 3 2-2 1.5 3"/>'
                      '<circle cx="14.5" cy="8.5" r="1.3"/>',
}

BACKDROPS = {  # Studio-Hintergrund je Kategorie (oben, unten)
    "Auto & Unterwegs": ("#eaf2fb", "#cddff2"),
    "Ordnung & Zuhause": ("#f7f1e6", "#eadcc3"),
    "Reisen": ("#e8f4f0", "#cfe6de"),
    "Sport & Fitness": ("#fbefed", "#f1d8d4"),
    "Haustiere": ("#f3edf9", "#e1d5ef"),
    "Schreibtisch & Handy": ("#eef1f6", "#d8dfea"),
    "Kunst & Poster": ("#f1ece4", "#ddd2c2"),
}


def _frame(key: str, collection: str, body: str, defs: str = "") -> str:
    top, bottom = BACKDROPS.get(collection, ("#f1f2f4", "#dde1e7"))
    return (f'<svg class="art" viewBox="0 0 400 300" role="img" aria-hidden="true" preserveAspectRatio="xMidYMid slice">'
            f'<defs><linearGradient id="bg-{key}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
            f'<stop offset="1" stop-color="{bottom}"/></linearGradient>'
            f'<radialGradient id="sh-{key}"><stop offset="0" stop-color="#1b2335" stop-opacity=".30"/>'
            f'<stop offset="1" stop-color="#1b2335" stop-opacity="0"/></radialGradient>{defs}</defs>'
            f'<rect width="400" height="300" fill="url(#bg-{key})"/>{body}</svg>')


def _shadow(key: str, cx: float, cy: float, rx: float, ry: float) -> str:
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#sh-{key})"/>'


def _snow(points: list[tuple[int, int, float]]) -> str:
    return "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#ffffff" opacity=".85"/>' for x, y, r in points)


def _eiskratzer(k: str) -> str:
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="3.2" fill="#d6cdbd"/>' for x, y in
                   ((156, 172), (176, 186), (196, 172), (216, 188), (236, 172), (256, 186), (170, 196), (232, 198)))
    body = (_snow([(52, 48, 3.5), (344, 58, 3), (306, 26, 2.4), (70, 238, 2.6), (352, 226, 3.2), (34, 142, 2.2),
                   (118, 30, 2), (372, 128, 2.4)])
            + _shadow(k, 218, 266, 130, 15)
            + '<g transform="translate(22 8) rotate(-16 205 160)">'
            '<path d="M150 198h112l26 56H124z" fill="#2c86dc"/><path d="M150 198h112l6 13H144z" fill="#6cb4f2"/>'
            '<rect x="122" y="250" width="168" height="7" rx="3.5" fill="#1b67b4"/>'
            '<ellipse cx="152" cy="124" rx="21" ry="33" fill="#2c3240" transform="rotate(-24 152 124)"/>'
            '<rect x="156" y="46" width="108" height="130" rx="54" fill="#2f3543"/>'
            '<rect x="176" y="62" width="22" height="74" rx="11" fill="#ffffff" opacity=".09"/>'
            '<path d="M210 54v110" stroke="#4b5366" stroke-width="2.2" stroke-dasharray="5 6"/>'
            f'<rect x="138" y="160" width="136" height="46" rx="18" fill="#ece6da"/>{dots}</g>')
    return _frame(k, "Auto & Unterwegs", body)


def _zugluft(k: str) -> str:
    wind = "".join(f'<path d="M18 {y}q24-12 48 0t48 0" stroke="#7fb2e0" stroke-width="5" fill="none" '
                   f'stroke-linecap="round" opacity="{o}"/>' for y, o in ((96, .9), (124, .65), (152, .45)))
    roll = ('<rect x="0" y="0" width="320" height="42" rx="21" fill="{c}"/>'
            '<rect x="14" y="7" width="292" height="9" rx="4.5" fill="#ffffff" opacity=".24"/>'
            '<path d="M24 24h272" stroke="#ffffff" stroke-opacity=".28" stroke-width="2" stroke-dasharray="7 7"/>')
    body = (wind + _shadow(k, 222, 238, 160, 15)
            + '<g transform="translate(64 118) rotate(-7 160 40)">'
            + f'<g>{roll.format(c="#8790a1")}</g><rect x="8" y="38" width="304" height="12" fill="#e4dccb"/>'
            + f'<g transform="translate(0 46)">{roll.format(c="#717b8d")}</g></g>')
    return _frame(k, "Ordnung & Zuhause", body)


def _tierhaar(k: str) -> str:
    fur = "".join(f'<path d="M{x} {y}q7-11 15 0" stroke="{c}" stroke-width="3.4" fill="none" stroke-linecap="round"/>'
                  for x, y, c in ((120, 258, "#df9450"), (150, 264, "#8f8f8f"), (262, 262, "#df9450"),
                                  (292, 256, "#8f8f8f"), (210, 270, "#df9450")))
    body = (_shadow(k, 212, 256, 122, 14)
            + '<rect x="197" y="26" width="30" height="134" rx="15" fill="#454b59" transform="rotate(26 212 93)"/>'
            '<g stroke="#5c6375" stroke-width="3" stroke-linecap="round" transform="rotate(26 212 93)">'
            '<path d="M204 44h16M204 56h16M204 68h16"/></g>'
            '<rect x="108" y="148" width="208" height="86" rx="32" fill="#e4e8ef" stroke="#c6ccd8" stroke-width="3"/>'
            '<rect x="124" y="194" width="176" height="44" rx="22" fill="#c43a4f"/>'
            '<path d="M138 205h148M138 216h148M138 227h148" stroke="#a62c40" stroke-width="2.2"/>'
            '<circle cx="296" cy="168" r="11" fill="#c43a4f"/>'
            '<rect x="128" y="158" width="120" height="10" rx="5" fill="#ffffff" opacity=".55"/>' + fur)
    return _frame(k, "Haustiere", body)


def _box(x: float, y: float, w: float, h: float, d: float, front: str, top: str, side: str) -> str:
    dy = d * 0.6
    return (f'<path d="M{x} {y}l{d} {-dy}h{w}l{-d} {dy}z" fill="{top}"/>'
            f'<path d="M{x + w} {y}l{d} {-dy}v{h}l{-d} {dy}z" fill="{side}"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{front}"/>'
            f'<path d="M{x + 8} {y + 9}h{w - 16}" stroke="#ffffff" stroke-opacity=".55" stroke-width="2.4" '
            f'stroke-dasharray="4 4"/><rect x="{x + w - 26}" y="{y + 4}" width="14" height="10" rx="3" fill="#f2c14e"/>')


def _packwuerfel(k: str) -> str:
    mesh = ('<g stroke="#ffffff" stroke-opacity=".35" stroke-width="1.4">'
            + "".join(f'<path d="M{150 + i * 14} 96l26 -15.6"/>' for i in range(8)) + "</g>")
    body = (_shadow(k, 206, 262, 150, 15)
            + _box(96, 172, 196, 78, 44, "#253e69", "#3a5a8f", "#1b2f52")
            + _box(118, 118, 160, 54, 38, "#2a998c", "#4cbcae", "#1f7a70")
            + _box(146, 81, 108, 37, 30, "#d6a960", "#e9c486", "#b98b45") + mesh)
    return _frame(k, "Reisen", body)


def _baender(k: str) -> str:
    def band(cx: int, cy: int, color: str) -> str:
        return (f'<ellipse cx="{cx}" cy="{cy}" rx="92" ry="58" fill="none" stroke="{color}" stroke-width="26"/>'
                f'<ellipse cx="{cx}" cy="{cy}" rx="92" ry="58" fill="none" stroke="#ffffff" stroke-opacity=".16" '
                f'stroke-width="26" stroke-dasharray="2 7"/>')
    body = _shadow(k, 204, 250, 150, 14) + band(156, 166, "#e8735f") + band(250, 172, "#2c9a8c") + band(204, 124, "#2b3f6c")
    return _frame(k, "Sport & Fitness", body)


def _laptop(k: str) -> str:
    defs = (f'<linearGradient id="{k}-alu" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#eef1f5"/>'
            f'<stop offset="1" stop-color="#9aa3b2"/></linearGradient>'
            f'<linearGradient id="{k}-scr" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1f3a5f"/>'
            f'<stop offset="1" stop-color="#2f6f73"/></linearGradient>')
    body = (_shadow(k, 205, 262, 140, 13)
            + f'<path d="M150 176L124 254M262 176L288 254M136 222h140" stroke="url(#{k}-alu)" stroke-width="12" '
            'stroke-linecap="round" fill="none"/>'
            '<rect x="122" y="34" width="168" height="114" rx="9" fill="#2a2f3a"/>'
            f'<rect x="130" y="42" width="152" height="98" rx="4" fill="url(#{k}-scr)"/>'
            '<path d="M150 118q56-62 112 0" stroke="#f2c14e" stroke-width="5" fill="none" stroke-linecap="round"/>'
            f'<path d="M104 150h204l24 22H80z" fill="url(#{k}-alu)"/>'
            '<path d="M120 158h172M112 165h188" stroke="#8a93a3" stroke-width="2"/>')
    return _frame(k, "Schreibtisch & Handy", body, defs)


def _frostschutz(k: str) -> str:
    defs = (f'<linearGradient id="{k}-cov" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f4f6f9"/>'
            f'<stop offset="1" stop-color="#b8c1ce"/></linearGradient>')
    quilt = "".join(f'<path d="M{150 + i * 22} 84l{-6 - i * 2} 56" stroke="#9aa5b5" stroke-width="1.6"/>' for i in range(5))
    body = (_snow([(40, 40, 3.2), (360, 52, 3), (300, 22, 2.2), (60, 120, 2.4), (350, 140, 2.6), (24, 220, 2.2),
                   (380, 240, 2.6), (120, 28, 2)])
            + _shadow(k, 200, 262, 160, 14)
            + '<path d="M150 64h100l16 20H134z" fill="#203a66"/>'
            + '<path d="M58 206q0-50 44-62h196q44 12 44 62v34q0 10-10 10H68q-10 0-10-10z" fill="#264372"/>'
            + f'<path d="M110 144h180l-24-60H134z" fill="url(#{k}-cov)"/>{quilt}'
            '<rect x="96" y="132" width="16" height="22" rx="3" fill="#b8c1ce"/><rect x="288" y="132" width="16" height="22" rx="3" fill="#b8c1ce"/>'
            '<ellipse cx="100" cy="196" rx="20" ry="11" fill="#ffe7a3"/><ellipse cx="300" cy="196" rx="20" ry="11" fill="#ffe7a3"/>'
            '<rect x="150" y="206" width="100" height="22" rx="8" fill="#1a2f55"/>'
            '<rect x="70" y="246" width="40" height="18" rx="6" fill="#1a2233"/><rect x="290" y="246" width="40" height="18" rx="6" fill="#1a2233"/>'
            '<path d="M150 64q50-14 100 0" stroke="#ffffff" stroke-width="7" fill="none" stroke-linecap="round"/>'
            '<path d="M72 170q40-14 70-8" stroke="#ffffff" stroke-width="6" fill="none" stroke-linecap="round" opacity=".9"/>')
    return _frame(k, "Auto & Unterwegs", body, defs)


def _fellhandschuh(k: str) -> str:
    nubs = []
    for row in range(5):
        for col in range(5):
            nubs.append(f'<circle cx="{156 + col * 22}" cy="{128 + row * 20}" r="4.4" fill="#2f7fd1"/>')
    for i, (x, h) in enumerate(((150, 66), (178, 78), (206, 80), (234, 70))):
        nubs.append(f'<circle cx="{x + 12}" cy="{108 - h + 22}" r="4" fill="#2f7fd1"/>')
        nubs.append(f'<circle cx="{x + 12}" cy="{108 - h + 42}" r="4" fill="#2f7fd1"/>')
    fingers = "".join(f'<rect x="{x}" y="{112 - h}" width="24" height="{h + 20}" rx="12" fill="#a2aec0"/>'
                      for x, h in ((150, 66), (178, 78), (206, 80), (234, 70)))
    body = (_shadow(k, 204, 262, 112, 14) + fingers
            + '<ellipse cx="128" cy="164" rx="18" ry="38" fill="#a2aec0" transform="rotate(-38 128 164)"/>'
            '<rect x="140" y="108" width="126" height="118" rx="34" fill="#a2aec0"/>'
            + "".join(nubs)
            + '<rect x="134" y="212" width="138" height="38" rx="11" fill="#2f3543"/>'
            '<rect x="146" y="222" width="64" height="18" rx="6" fill="#4a5266"/>'
            '<path d="M290 236q8-12 16 0M306 220q8-12 16 0" stroke="#df9450" stroke-width="3.4" fill="none" stroke-linecap="round"/>')
    return _frame(k, "Haustiere", body)


def _wandhaken(k: str) -> str:
    grid = "".join(f'<path d="M0 {y}h400" stroke="#e3e8ee" stroke-width="2"/>' for y in range(0, 300, 60))
    grid += "".join(f'<path d="M{x} 0v300" stroke="#e3e8ee" stroke-width="2"/>' for x in range(0, 400, 60))

    def hook(x: int) -> str:
        return (f'<ellipse cx="{x + 4}" cy="146" rx="26" ry="9" fill="#1b2335" opacity=".08"/>'
                f'<rect x="{x - 20}" y="86" width="40" height="54" rx="13" fill="#e7ebf0" stroke="#aab4c2" stroke-width="2.5"/>'
                f'<rect x="{x - 12}" y="94" width="10" height="30" rx="5" fill="#ffffff" opacity=".8"/>'
                f'<path d="M{x} 122v22q0 18 16 18" stroke="#8d98a8" stroke-width="13" fill="none" stroke-linecap="round"/>'
                f'<path d="M{x} 122v22q0 18 16 18" stroke="#f4f6f9" stroke-width="8" fill="none" stroke-linecap="round"/>')
    towel = ('<path d="M188 154q14-8 28 0l24 98q-38 14-76 0z" fill="#d8695d"/>'
             '<path d="M172 232q38 12 72 0" stroke="#f3d3cd" stroke-width="7" fill="none"/>'
             '<path d="M194 160l-10 86" stroke="#c2574c" stroke-width="2"/>')
    body = ('<rect width="400" height="300" fill="#f5f7f9"/>' + grid
            + '<ellipse cx="200" cy="150" rx="190" ry="120" fill="#ffffff" opacity=".35"/>'
            + hook(110) + hook(200) + hook(290) + towel)
    return _frame(k, "Ordnung & Zuhause", body)


def _rollbeutel(k: str) -> str:
    body = (_shadow(k, 206, 252, 150, 14)
            + '<rect x="86" y="74" width="222" height="160" rx="16" fill="#d9ecfb" fill-opacity=".75" stroke="#9cc7ec" stroke-width="3"/>'
            '<rect x="106" y="112" width="182" height="44" rx="10" fill="#c8504a"/>'
            '<path d="M118 126h158M118 140h158" stroke="#a83f3a" stroke-width="2"/>'
            '<rect x="106" y="160" width="182" height="40" rx="10" fill="#e4b54a"/>'
            '<path d="M196 160v40" stroke="#c99a34" stroke-width="2"/>'
            '<path d="M98 92h198" stroke="#7fb2e0" stroke-width="4" stroke-dasharray="7 5"/>'
            '<circle cx="320" cy="154" r="38" fill="#d9ecfb" fill-opacity=".9" stroke="#9cc7ec" stroke-width="3"/>'
            '<path d="M320 132a22 22 0 1 1-20 30M320 142a12 12 0 1 1-10 16" stroke="#9cc7ec" stroke-width="3" fill="none"/>'
            '<path d="M104 86l40 132" stroke="#ffffff" stroke-width="10" stroke-opacity=".45" stroke-linecap="round"/>')
    return _frame(k, "Reisen", body)


def _massageball(k: str) -> str:
    defs = (f'<radialGradient id="{k}-o" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#ffc283"/>'
            f'<stop offset="1" stop-color="#e2692a"/></radialGradient>'
            f'<radialGradient id="{k}-t" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#5cc6b9"/>'
            f'<stop offset="1" stop-color="#1b7a70"/></radialGradient>')
    spikes = []
    import math
    for ring, rad in ((0, 50), (1, 34), (2, 18)):
        count = (16, 11, 6)[ring]
        for i in range(count):
            a = 2 * math.pi * i / count + ring * .3
            spikes.append(f'<circle cx="{262 + rad * math.cos(a):.1f}" cy="{166 + rad * math.sin(a):.1f}" r="6" '
                          'fill="#8de0d5" opacity=".75"/>')
    body = (_shadow(k, 150, 236, 78, 12) + _shadow(k, 264, 236, 70, 11)
            + f'<circle cx="150" cy="164" r="64" fill="url(#{k}-o)"/>'
            '<ellipse cx="128" cy="134" rx="22" ry="12" fill="#ffffff" opacity=".35" transform="rotate(-30 128 134)"/>'
            + f'<circle cx="262" cy="166" r="58" fill="url(#{k}-t)"/>' + "".join(spikes))
    return _frame(k, "Sport & Fitness", body, defs)


def _handystaender(k: str) -> str:
    defs = (f'<linearGradient id="{k}-alu" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f1f3f6"/>'
            f'<stop offset="1" stop-color="#97a0af"/></linearGradient>'
            f'<linearGradient id="{k}-scr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f2c14e"/>'
            f'<stop offset="1" stop-color="#e8735f"/></linearGradient>')
    body = (_shadow(k, 210, 262, 110, 12)
            + f'<rect x="136" y="244" width="152" height="12" rx="6" fill="url(#{k}-alu)"/>'
            f'<path d="M262 246L232 134" stroke="url(#{k}-alu)" stroke-width="14" stroke-linecap="round"/>'
            '<g transform="rotate(-14 210 150)">'
            '<rect x="166" y="52" width="90" height="176" rx="16" fill="#1f2430"/>'
            f'<rect x="173" y="60" width="76" height="160" rx="11" fill="url(#{k}-scr)"/>'
            '<circle cx="211" cy="140" r="20" fill="#ffffff" opacity=".9"/><path d="M205 130l16 10-16 10z" fill="#e8735f"/>'
            '<rect x="160" y="222" width="102" height="12" rx="5" fill="#b9c1cd"/></g>')
    return _frame(k, "Schreibtisch & Handy", body, defs)


ART = {
    "Eiskratzer mit gefüttertem Handschuh": _eiskratzer,
    "Zugluftstopper für Türen": _zugluft,
    "Tierhaar-Entfernerrolle": _tierhaar,
    "Packwürfel-Set": _packwuerfel,
    "Widerstandsbänder aus Stoff": _baender,
    "Faltbarer Laptop-Ständer aus Aluminium": _laptop,
    "Frostschutz-Abdeckung für die Windschutzscheibe": _frostschutz,
    "Fellpflege-Handschuh": _fellhandschuh,
    "Selbstklebende Wandhaken": _wandhaken,
    "Vakuum-Rollbeutel für Reisen": _rollbeutel,
    "Massageball-Set": _massageball,
    "Handyständer aus Aluminium": _handystaender,
}


def collection_art(collection: str, key: str = "c") -> str:
    icon = ICONS.get(collection, ICONS["Ordnung & Zuhause"])
    body = (_shadow(key, 200, 236, 90, 12)
            + '<circle cx="200" cy="146" r="78" fill="#ffffff" opacity=".75"/>'
            + f'<g transform="translate(152 98) scale(4)" fill="none" stroke="#24305e" stroke-width="1.3" '
            f'stroke-linecap="round" stroke-linejoin="round">{icon}</g>')
    return _frame(key, collection, body)


def product_art(p: dict) -> str:
    key = f"p{p.get('id', 0)}"
    if p.get("image"):  # echtes Motiv: Poster an der Wand bzw. Wallpaper auf dem Handy
        kind = "phone" if p.get("kind") == "digital" else "poster"
        alt = p.get("name", "").replace('"', "")
        return f'<div class="art mock {kind}"><img src="{p["image"]}" alt="{alt}" loading="lazy"></div>'
    draw = ART.get(p.get("name", ""))
    return draw(key) if draw else collection_art(p.get("collection", ""), key)
