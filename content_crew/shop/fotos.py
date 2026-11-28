"""Produktfotos für den Shop-Import: Illustrationen der Alltagshelfer, Poster an der Wand, Wallpaper auf Handys.

Alle Bilder entstehen lokal (Skia) – als JPEG, damit Shopify sie beim CSV-Import von einer öffentlichen
Adresse laden kann.
"""

from __future__ import annotations

from pathlib import Path

import skia

from content_crew.shop.art import product_art

SIZE = 1200


def _save(surface: skia.Surface, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(surface.makeImageSnapshot().encodeToData(skia.kJPEG, 90)))
    return path.name


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
    c.drawImageRect(img, inner, skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear))
    c.restore()


def poster_photos(p: dict, out: Path) -> list[str]:
    """Poster im Rahmen an der Wand und das Motiv allein."""
    art = skia.Image.open(p["file"])
    s = skia.Surface(SIZE, SIZE)
    c = s.getCanvas()
    _wall(c, SIZE, SIZE)
    _framed(c, art, SIZE / 2, SIZE * 0.45, SIZE * 0.72, SIZE * 0.018)
    names = [_save(s, out / f"P{p['id']:02d}-1.jpg")]
    flat = skia.Surface(SIZE, int(SIZE * art.height() / art.width()))
    flat.getCanvas().drawImageRect(art, skia.Rect(0, 0, flat.width(), flat.height()),
                                   skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear))
    names.append(_save(flat, out / f"P{p['id']:02d}-2.jpg"))
    return names


def phone_photos(p: dict, out: Path) -> list[str]:
    """Drei Handys mit Wallpapern aus dem Paket."""
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
    svg = product_art({**p, "image": None}).replace(
        '<svg class="art" viewBox', f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE * 3 // 4}" viewBox', 1)
    dom = skia.SVGDOM.MakeFromStream(skia.MemoryStream(svg.encode(), True))
    s = skia.Surface(SIZE, SIZE * 3 // 4)
    c = s.getCanvas()
    c.clear(skia.ColorWHITE)
    dom.setContainerSize(skia.Size(SIZE, SIZE * 3 // 4))
    dom.render(c)
    return [_save(s, out / f"P{p['id']:02d}-1.jpg")]


def product_photos(p: dict, out: Path) -> list[str]:
    if p.get("kind") == "pod" and p.get("file"):
        return poster_photos(p, out)
    if p.get("kind") == "digital":
        return phone_photos(p, out)
    return illustration_photo(p, out)
