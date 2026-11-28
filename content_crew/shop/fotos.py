"""Produktfotos für Shop-Vorschau und Shopify-Import.

Erste Wahl sind fotorealistische Studiobilder aus Blender (studio3d.py): Jedes Produkt ist dort als 3D-Modell in
echten Maßen nachgebaut und wie im Fotostudio ausgeleuchtet, die Poster hängen gerahmt in einem Wohnzimmer, die
Wallpaper laufen auf drei Handys. Ist Blender nicht installiert, entstehen einfache Ersatzbilder mit Skia.

Wichtig für den Verkauf: Die Studiobilder zeigen die Alltagshelfer so, wie sie beschrieben sind. Sobald ein
Lieferant feststeht, muss seine Ware genau so aussehen – oder seine echten Fotos ersetzen die Renderings.

Alle Bilder sind JPEGs, damit Shopify sie beim CSV-Import von einer öffentlichen Adresse laden kann.
"""

from __future__ import annotations

import base64
import functools
import os
import shutil
import subprocess
from pathlib import Path

import skia

from content_crew.shop.art import product_art

SIZE = 1200
PHOTO_DIR = Path(__file__).resolve().parents[2] / "shop-assets" / "bilder"
STUDIO_SCRIPT = Path(__file__).with_name("studio3d.py")
BLENDER_VENV = Path("/opt/blender-studio/bin/python")

# Produktname → Szene im Fotostudio (studio3d.PRODUCTS)
STUDIO_KEYS = {
    "Eiskratzer mit gefüttertem Handschuh": "eiskratzer",
    "Zugluftstopper für Türen": "zugluftstopper",
    "Tierhaar-Entfernerrolle": "tierhaar",
    "Packwürfel-Set": "packwuerfel",
    "Widerstandsbänder aus Stoff": "baender",
    "Faltbarer Laptop-Ständer aus Aluminium": "laptop",
    "Frostschutz-Abdeckung für die Windschutzscheibe": "frostschutz",
    "Fellpflege-Handschuh": "fellhandschuh",
    "Selbstklebende Wandhaken": "wandhaken",
    "Vakuum-Rollbeutel für Reisen": "rollbeutel",
    "Massageball-Set": "massageball",
    "Handyständer aus Aluminium": "handystaender",
}


# Zusätzliche Szenen je Produkt – das Anwendungsfoto steht vorne und wird zum Hauptbild
EXTRA_SCENES = {"frostschutz": ["frostschutz_auto"]}


def studio_key(p: dict) -> str | None:
    """Welche Studio-Szene zu einem Produkt gehört (None = kein 3D-Modell vorhanden)."""
    if p.get("kind") == "pod" and p.get("world"):
        return f"poster_{p['world']}"
    if p.get("kind") == "digital":
        return "wallpaper"
    return STUDIO_KEYS.get(p.get("name", ""))


def studio_scenes(p: dict) -> list[str]:
    """Alle Studio-Szenen eines Produkts in der Reihenfolge der Shopfotos."""
    key = studio_key(p)
    return [*EXTRA_SCENES.get(key, []), key] if key else []


def blender_command() -> list[str] | None:
    """Blender als Python-Modul (offizielle Version mit Rauschfilter) oder das blender-Programm."""
    for cand in (os.environ.get("BLENDER_PYTHON", ""), str(BLENDER_VENV)):
        if cand and Path(cand).exists():
            return [cand, str(STUDIO_SCRIPT)]
    exe = shutil.which("blender")
    return [exe, "-b", "--factory-startup", "-P", str(STUDIO_SCRIPT), "--"] if exe else None


def render_studio(keys: list[str], out_dir: Path, art_dir: Path, size: int = SIZE, samples: int = 96) -> bool:
    """Studiobilder rechnen (dauert je Bild einige Minuten). False, wenn Blender fehlt."""
    cmd = blender_command()
    if not cmd or not keys:
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd + ["--out", str(out_dir), "--only", ",".join(keys), "--size", str(size),
                          "--samples", str(samples), "--art", str(art_dir)], check=True)
    return True


def _save(surface: skia.Surface, path: Path, quality: int = 88) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(surface.makeImageSnapshot().encodeToData(skia.kJPEG, quality)))
    return path.name


def _sampling() -> skia.SamplingOptions:
    return skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


def _copy_square(src: Path, path: Path) -> str:
    img = skia.Image.open(str(src))
    s = skia.Surface(SIZE, SIZE)
    side = min(img.width(), img.height())
    s.getCanvas().drawImageRect(img, skia.Rect.MakeXYWH((img.width() - side) / 2, (img.height() - side) / 2, side, side),
                                skia.Rect(0, 0, SIZE, SIZE), _sampling())
    return _save(s, path)


def _wall(c: skia.Canvas, w: int, h: int) -> None:
    c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeLinear(
        [skia.Point(0, 0), skia.Point(0, h)], [skia.Color(242, 237, 228), skia.Color(217, 207, 191)])))
    c.drawRect(skia.Rect(0, h * 0.86, w, h), skia.Paint(Color=skia.Color(196, 182, 160)))


def _framed(c: skia.Canvas, img: skia.Image, x: float, y: float, height: float, border: float, radius: float = 0,
            frame=skia.ColorWHITE) -> None:
    width = height * img.width() / img.height()
    rect = skia.Rect(x - width / 2 - border, y - height / 2 - border, x + width / 2 + border, y + height / 2 + border)
    shadow = skia.Paint(AntiAlias=True, Color=skia.Color4f(0.08, 0.08, 0.12, 0.35),
                        MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, height * 0.025))
    c.drawRRect(skia.RRect.MakeRectXY(rect.makeOffset(0, height * 0.02), radius, radius), shadow)
    c.drawRRect(skia.RRect.MakeRectXY(rect, radius, radius), skia.Paint(AntiAlias=True, Color=frame))
    inner = skia.Rect(x - width / 2, y - height / 2, x + width / 2, y + height / 2)
    c.save()
    c.clipRRect(skia.RRect.MakeRectXY(inner, max(0, radius - border), max(0, radius - border)), True)
    c.drawImageRect(img, inner, _sampling())
    c.restore()


def flat_art(p: dict, path: Path) -> str:
    """Das Motiv allein – so sieht der Druck aus (quadratisch mit Rand, damit nichts abgeschnitten wird)."""
    art = skia.Image.open(p["file"])
    s = skia.Surface(SIZE, SIZE)
    c = s.getCanvas()
    c.clear(skia.Color(243, 240, 234))
    _framed(c, art, SIZE / 2, SIZE / 2, SIZE * 0.86, 0, 0, skia.ColorWHITE)
    return _save(s, path)


def wallpaper_strip(p: dict, path: Path) -> str:
    """Alle Motive des Wallpaper-Pakets nebeneinander."""
    files = [f for f in p.get("files") or [] if Path(f).exists()]
    s = skia.Surface(SIZE, SIZE)
    c = s.getCanvas()
    c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeLinear(
        [skia.Point(0, 0), skia.Point(0, SIZE)], [skia.Color(30, 34, 48), skia.Color(14, 16, 24)])))
    n = max(1, len(files))
    rows = 1 if n <= 4 else 2
    per_row = (n + rows - 1) // rows
    gap = SIZE * 0.025
    w = (SIZE - gap * (per_row + 1)) / per_row
    h = w * 3120 / 1440
    if rows * h + gap * (rows + 1) > SIZE:
        h = (SIZE - gap * (rows + 1)) / rows
        w = h * 1440 / 3120
    top = (SIZE - rows * h - (rows - 1) * gap) / 2
    for i, f in enumerate(files):
        r, k = divmod(i, per_row)
        count = per_row if r < rows - 1 else n - per_row * (rows - 1)
        left = (SIZE - count * w - (count - 1) * gap) / 2
        _framed(c, skia.Image.open(f), left + k * (w + gap) + w / 2, top + r * (h + gap) + h / 2, h,
                SIZE * 0.006, SIZE * 0.022, skia.Color(16, 18, 24))
    return _save(s, path)


def poster_photos(p: dict, out: Path) -> list[str]:
    """Ersatz ohne Blender: Poster im Rahmen an der Wand und das Motiv allein."""
    art = skia.Image.open(p["file"])
    s = skia.Surface(SIZE, SIZE)
    c = s.getCanvas()
    _wall(c, SIZE, SIZE)
    _framed(c, art, SIZE / 2, SIZE * 0.45, SIZE * 0.72, SIZE * 0.018)
    return [_save(s, out / f"P{p['id']:02d}-1.jpg"), flat_art(p, out / f"P{p['id']:02d}-2.jpg")]


def phone_photos(p: dict, out: Path) -> list[str]:
    """Ersatz ohne Blender: drei Handys mit Wallpapern aus dem Paket."""
    files = p.get("files") or []
    s = skia.Surface(SIZE, SIZE)
    c = s.getCanvas()
    c.drawPaint(skia.Paint(Shader=skia.GradientShader.MakeLinear(
        [skia.Point(0, 0), skia.Point(0, SIZE)], [skia.Color(32, 38, 66), skia.Color(14, 17, 30)])))
    picks = [f for f in files if any(w in f for w in ("medieval", "iceage", "jungle"))][:3] or files[:3]
    for k, (dx, tilt) in enumerate(((-0.27, -8), (0.0, 0), (0.27, 8))):
        if k >= len(picks):
            break
        img = skia.Image.open(picks[k])
        c.save()
        c.translate(SIZE / 2 + dx * SIZE, SIZE * 0.5)
        c.rotate(tilt)
        _framed(c, img, 0, 0, SIZE * (0.66 if k == 1 else 0.6), SIZE * 0.012, SIZE * 0.045, skia.Color(16, 18, 24))
        c.restore()
    return [_save(s, out / f"P{p['id']:02d}-1.jpg")]


def illustration_photo(p: dict, out: Path) -> list[str]:
    """Ersatz ohne Blender: die Shop-Illustration als Bild."""
    svg = product_art({**p, "image": None}).replace(
        '<svg class="art" viewBox', f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE * 3 // 4}" viewBox', 1)
    dom = skia.SVGDOM.MakeFromStream(skia.MemoryStream(svg.encode(), True))
    s = skia.Surface(SIZE, SIZE * 3 // 4)
    c = s.getCanvas()
    c.clear(skia.ColorWHITE)
    dom.setContainerSize(skia.Size(SIZE, SIZE * 3 // 4))
    dom.render(c)
    return [_save(s, out / f"P{p['id']:02d}-1.jpg")]


def studio_photos(p: dict, out: Path, studio_dir: Path) -> list[str]:
    """Studiobilder als Shopfotos, dazu bei Postern das Motiv allein und beim Wallpaper-Paket alle Motive."""
    sources = [studio_dir / f"{k}.jpg" for k in studio_scenes(p)]
    sources = [s for s in sources if s.exists()]
    if not sources:
        return []
    names = [_copy_square(src, out / f"P{p['id']:02d}-{i}.jpg") for i, src in enumerate(sources, start=1)]
    nxt = out / f"P{p['id']:02d}-{len(names) + 1}.jpg"
    if p.get("kind") == "pod" and p.get("file") and Path(p["file"]).exists():
        names.append(flat_art(p, nxt))
    if p.get("kind") == "digital" and p.get("files"):
        names.append(wallpaper_strip(p, nxt))
    return names


def product_photos(p: dict, out: Path, studio_dir: Path | None = None) -> list[str]:
    if studio_dir is not None:
        names = studio_photos(p, out, studio_dir)
        if names:
            return names
    if p.get("kind") == "pod" and p.get("file"):
        return poster_photos(p, out)
    if p.get("kind") == "digital":
        return phone_photos(p, out)
    return illustration_photo(p, out)


@functools.lru_cache(maxsize=256)
def _data_uri(path: str, mtime: float, width: int, quality: int) -> str:
    img = skia.Image.open(path)
    h = round(img.height() * width / img.width())
    s = skia.Surface(width, h)
    s.getCanvas().drawImageRect(img, skia.Rect(0, 0, width, h), _sampling())
    data = bytes(s.makeImageSnapshot().encodeToData(skia.kJPEG, quality))
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def photo_data(p: dict, width: int = 560, quality: int = 80, photo_dir: Path | None = None) -> list[str]:
    """Die Produktfotos als eingebettete Bilder (für die Vorschau, die ohne Webserver auskommen muss)."""
    folder = photo_dir or PHOTO_DIR
    out = []
    for name in p.get("photos") or []:
        f = folder / name
        if f.exists():
            out.append(_data_uri(str(f), f.stat().st_mtime, width, quality))
    return out
