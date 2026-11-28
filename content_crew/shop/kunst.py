"""Eigene Kunst als Produkte: Poster (Druck auf Bestellung) und Handy-Wallpaper (Download) aus der Serie „24 Hours In …“.

Die Motive rechnet die Animations-Engine – sie kosten nichts. Poster druckt ein Druckpartner erst nach der
Bestellung, Wallpaper werden sofort nach dem Kauf geladen. So muss nichts vorab eingekauft werden.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import numpy as np

MOTIVE = [  # Welt, Stunde (Bildausschnitt der Geschichte), Titel
    ("iceage", 20.6, "Polarlicht über der Eiszeit"),
    ("medieval", 8.3, "Der Drache vom Burgberg"),
    ("egypt", 16.9, "Karawane bei den Pyramiden"),
    ("jungle", 20.6, "Glühwürmchen im Dschungel"),
    ("savanna", 16.9, "Elefanten im Sonnenuntergang"),
    ("arctic", 16.9, "Rentiere im Abendlicht"),
    ("wildwest", 16.9, "Mustangs im Wilden Westen"),
]
POSTER = (3508, 4961)       # A3 mit 300 dpi
WALLPAPER = (1440, 3120)    # moderne Handys (19,5:9)


def render(world: str, hour: float, size: tuple[int, int], path: Path, variant: int = 1) -> Path:
    """Ein Standbild der Geschichte in beliebiger Größe – ohne Schrift."""
    import skia

    from content_crew.animation.engine import Ctx
    from content_crew.animation.palettes import PALETTES
    from content_crew.animation.scenes.adventure import Adventure

    W, H = size
    fps = 30
    scene = Adventure(Ctx(W, H, fps, 56, 7, PALETTES["neon"], "minor"),
                      {"world": world, "ending": "pet", "variant": variant, "poster": True})
    while scene.hour() < hour:
        scene.update(1 / fps)
    frame = np.zeros((H, W, 4), np.uint8)
    surf = skia.Surface(frame, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    c = surf.getCanvas()
    c.clear(skia.ColorBLACK)
    scene.draw(c)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = skia.Image.fromarray(np.ascontiguousarray(frame), colorType=skia.kRGBA_8888_ColorType)
    fmt = skia.kJPEG if path.suffix.lower() in (".jpg", ".jpeg") else skia.kPNG
    img.save(str(path), fmt) if fmt == skia.kPNG else path.write_bytes(bytes(img.encodeToData(skia.kJPEG, 90)))
    return path


def thumbnail_data(world: str, hour: float, size: tuple[int, int] = (360, 509)) -> str:
    """Kleines JPEG als data-URI für die Shop-Vorschau (Standard: Posterformat)."""
    import tempfile

    tmp = Path(tempfile.gettempdir()) / f"kunst_{world}_{size[0]}x{size[1]}.jpg"
    render(world, hour, size, tmp)
    data = base64.b64encode(tmp.read_bytes()).decode()
    tmp.unlink(missing_ok=True)
    return f"data:image/jpeg;base64,{data}"


def products(out_dir: Path, files: bool = True) -> list[dict]:
    """Produktideen für den Shop (ein Poster je Motiv plus ein Wallpaper-Paket). files=True rendert die Druckdateien."""
    out_dir = Path(out_dir)
    ideas = []
    for world, hour, title in MOTIVE:
        poster = out_dir / f"poster_{world}.png"
        if files and not poster.exists():
            render(world, hour, POSTER, poster)
        ideas.append({
            "name": f"Poster „{title}“", "collection": "Kunst & Poster", "season": "", "kind": "pod",
            "origin": "pod", "world": world, "hour": hour, "file": str(poster),
            "problem": "Kahle Wand, aber keine Lust auf Poster, die schon jeder hat?",
            "solution": f"„{title}“ stammt aus unserer TikTok-Serie „24 Hours In …“ – im Schattenriss-Stil "
                        "gezeichnet und erst gedruckt, wenn du bestellst.",
            "benefits": ["Exklusives Motiv aus der TikTok-Serie", "Format A3 (29,7 × 42 cm), matter Druck",
                         "Auf Bestellung gedruckt und gerollt verschickt"],
            "usage": "Mit Bilderrahmen oder Posterleisten aufhängen. Rahmen nicht im Lieferumfang.",
            "material": "Posterpapier, matt", "contents": "1 Poster A3, ohne Rahmen",
            "target": "Fans der Serie, Jugendzimmer, Gaming- und Büro-Ecken", "ek": [9.0, 11.0],
            "market": [19.9, 34.9], "weight_g": 250, "keywords_en": f"poster {world} silhouette art",
            "hook": "Das Poster an der Wand, daneben läuft dieselbe Szene als Video.",
        })
    pack = []
    for world, hour, _ in MOTIVE:
        wp = out_dir / f"wallpaper_{world}.png"
        if files and not wp.exists():
            render(world, hour, WALLPAPER, wp)
        pack.append(str(wp))
    ideas.append({
        "name": "Handy-Wallpaper „24 Hours“ – 7 Motive", "collection": "Kunst & Poster", "season": "",
        "kind": "digital", "origin": "digital", "world": "iceage", "hour": 20.6, "files": pack,
        "problem": "Immer dasselbe Hintergrundbild auf dem Handy?",
        "solution": "Sieben Motive aus „24 Hours In …“ – vom Polarlicht bis zum Drachen – als Wallpaper fürs Handy.",
        "benefits": ["7 Motive in hoher Auflösung (1440 × 3120 Pixel)", "Sofort nach dem Kauf zum Download",
                     "Passt auf alle gängigen Handys"],
        "usage": "Dateien herunterladen und in den Handy-Einstellungen als Hintergrundbild wählen.",
        "material": "Digitale Bilddateien (PNG)", "contents": "7 Wallpaper als PNG",
        "target": "Fans der Serie", "ek": [0.0, 0.0], "market": [2.99, 9.99], "weight_g": 0,
        "keywords_en": "phone wallpaper pack silhouette", "hook": "Handy entsperren – und das Polarlicht leuchtet.",
    })
    return ideas
