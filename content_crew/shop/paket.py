"""Shop-Paket: alles, was der Shop zum Start braucht – als Ordner und als ZIP-Datei.

Inhalt: Shopify-Importdatei, Produktfotos, Druckdateien der Poster, Wallpaper zum Download, Infoseiten,
E-Mail-Vorlagen und eine Schritt-für-Schritt-Anleitung (LIES-MICH.txt) mit dem aktuellen Shopnamen.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from content_crew.shop.fotos import PHOTO_DIR
from content_crew.shop.pricing import eur
from content_crew.shop.shopify import export_csv


def _partner(p: dict) -> str:
    if p.get("kind") == "pod":
        return "Druckpartner (Printful oder Gelato)"
    if p.get("kind") == "digital":
        return "Shopify-App Digital Downloads"
    words = p.get("keywords_en") or []
    hint = f" – Suchbegriff beim Lieferanten: „{words[0]}“" if words else ""
    return f"CJdropshipping, EU-Lager{hint}"


def readme(name: str, products: list[dict], domain_hint: str = "") -> str:
    collections = sorted({p["collection"] for p in products})
    title = f"{name} – Shop-Paket"
    lines = [
        title, "=" * len(title), "",
        (f"In diesem Ordner liegt alles, was dein Shop braucht: {len(products)} Produkte mit Texten, Preisen und "
         "Fotos, die Druckdateien für die Poster, die Wallpaper zum Download, die Infoseiten und E-Mail-Vorlagen."),
        ("Kein Produkt musst du vorher kaufen: Poster druckt der Druckpartner erst nach einer Bestellung, die "
         "Wallpaper sind digital, und die Alltagshelfer schickt der Lieferant, nachdem der Kunde bezahlt hat."), "",
        "Ordner", "------",
        f"1_shopify-import.csv      Alle {len(products)} Produkte für den Import in Shopify (Fotos lädt Shopify selbst)",
        "2_produktfotos            Die Produktfotos (falls du sie woanders brauchst)",
        "3_poster-druckdateien     Die Poster in A3 mit 300 dpi für den Druckpartner",
        "4_wallpaper-download      Die Handy-Wallpaper (1440 × 3120) – das verkaufst du als Download",
        "5_seiten                  Über uns, Versand & Lieferung, Häufige Fragen, Kontakt",
        "6_emails                  Willkommensmail, Neuheiten-Newsletter, Warenkorb-Erinnerung", "",
        "Zu den Fotos", "------------",
        "Die Fotos der Alltagshelfer sind Studiobilder aus dem 3D-Fotostudio: Jedes Produkt ist in echten Maßen",
        "nachgebaut und so gezeigt, wie es beschrieben ist. Wähle beim Lieferanten genau so ein Produkt – oder",
        "ersetze die Bilder durch seine Fotos. Die Poster hängen zur Ansicht gerahmt im Wohnzimmer; geliefert",
        "wird das Poster ohne Rahmen (steht so auch im Produkttext).", "",
        "So startest du den Verkauf (Schritt für Schritt)",
        "--------------------------------------------------",
        "1. Gewerbe anmelden – Pflicht, bevor du verkaufst. Handel ist ein freies Gewerbe, online über",
        "   usp.gv.at. Die Gründerberatung der WKO hilft gratis (Sozialversicherung, Kleinunternehmer, Steuer).", "",
        f"2. Shopify-Konto anlegen (shopify.com), Land Österreich, Shopname „{name}“.",
        "   Prüfe vorher im Markenregister (Österreichisches Patentamt, EUIPO), ob der Name frei ist."
        + (f"\n   {domain_hint}" if domain_hint else ""), "",
        "3. Produkte importieren: Produkte → Importieren → Datei 1_shopify-import.csv wählen.",
        f"   Alle {len(products)} Produkte kommen als Entwurf an, die Fotos lädt Shopify automatisch mit.", "",
        "4. Kategorien anlegen: Produkte → Kollektionen → Kollektion erstellen → „Automatisiert“,",
        "   Bedingung „Produkttyp ist gleich …“. Eine Kollektion je Typ:",
        "   " + ", ".join(collections), "",
        "5. Infoseiten: Onlineshop → Seiten → Seite hinzufügen. Für jede Datei in 5_seiten eine Seite,",
        "   Inhalt hineinkopieren. Dann Onlineshop → Navigation: Kategorien und Seiten ins Menü.", "",
        "6. Rechtstexte: Einstellungen → Richtlinien: AGB, Widerrufsbelehrung, Datenschutzerklärung und",
        "   Impressum erzeugen und mit deinen Daten (Name, Anschrift, E-Mail, Gewerbe, Gewerbebehörde)",
        "   ergänzen. Lass sie prüfen (z. B. Muster der WKO).", "",
        "7. Bezahlung: Einstellungen → Zahlungen → Shopify Payments aktivieren (braucht deine Gewerbe- und",
        "   Bankdaten), optional PayPal.", "",
        "8. Partner verbinden – dann läuft der Versand automatisch:",
        "   - Poster: App „Printful“ oder „Gelato“ installieren, je Motiv ein Poster A3 anlegen, die Datei aus",
        "     3_poster-druckdateien hochladen und mit dem importierten Produkt verknüpfen. Die Angaben zu",
        "     Hersteller und EU-Verantwortlichem (Produktsicherheit/GPSR) gibt dir der Druckpartner.",
        "   - Wallpaper: App „Digital Downloads“ (von Shopify, gratis) installieren und beim Wallpaper-Produkt",
        "     die Dateien aus 4_wallpaper-download anhängen. An der Kasse den Hinweis aktivieren, dass das",
        "     Widerrufsrecht mit dem Download erlischt.",
        "   - Alltagshelfer: App „CJdropshipping“ installieren, Lager in der EU wählen, das passende Produkt",
        "     suchen (Suchbegriffe unten) und mit dem importierten Produkt verbinden („Connect“). Echten",
        "     Einkaufspreis prüfen – liegt er höher als geschätzt, Preis anpassen. Hersteller und",
        "     EU-Verantwortlichen beim Lieferanten erfragen und in die Produktbeschreibung schreiben.", "",
        "9. Produkte aktiv schalten: Produkte → die Produkte mit verbundenem Partner markieren →",
        "   „Als aktiv festlegen“. Nur aktivieren, was auch wirklich geliefert werden kann.", "",
        "10. Verkauf starten: Einstellungen → Tarif wählen. Dann Onlineshop → Einstellungen →",
        "    Passwortschutz ausschalten. Ab jetzt kann jeder kaufen. Shop-Link in deine TikTok-Bio.", "",
        "11. Automatik mit Jarvis (optional): Im Shopify Dev Dashboard eine App anlegen (Rechte",
        "    write_products, write_content, write_publications, read_orders), im Shop installieren und",
        "    Client-ID und Secret mit `content-crew setup` eintragen. Dann pflegt Jarvis Produkte und Seiten,",
        "    meldet neue Bestellungen und führt die Buchhaltung.", "",
        f"Die {len(products)} Produkte", "-" * (len(str(len(products))) + 13),
    ]
    for p in products:
        lines.append(f"P{p['id']:<3} {p['texts']['title']}")
        lines.append(f"     Preis {eur(p['calc']['offer']['price'])} · Gewinn pro Bestellung {eur(p['calc']['profit'])}"
                     f" · Partner: {_partner(p)}")
    lines += ["", "Gewinn pro Bestellung = nach Umsatzsteuer, Versand, Zahlungsgebühr, Rückerstattungen und einem",
              "Werbeanteil. Bei den Alltagshelfern sind die Einkaufspreise geschätzt, bis der Lieferant echte",
              "Preise liefert. Garantieren kann den Umsatz niemand – Verkäufe hängen davon ab, wie viele Leute den",
              "Shop sehen. Deine TikTok-Videos sind dafür die beste Werbung.", ""]
    return "\n".join(lines)


def build_package(manager, domain_hint: str = "") -> Path:
    """Paket-Ordner und ZIP unter data/shop/paket/<Name>-Shop-Paket(.zip) erzeugen."""
    name = manager.name
    slug = re.sub(r"[^0-9A-Za-zÄÖÜäöüß]+", "-", name).strip("-") or "Shop"
    base = manager.dir / "paket"
    root = base / f"{slug}-Shop-Paket"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    products = list(reversed(manager.db.products(["freigegeben", "online"])))
    export_csv(products, root / "1_shopify-import.csv", name, str(manager.scfg.get("image_base_url", "")))
    for p in products:
        for photo in p.get("photos") or []:
            src = PHOTO_DIR / photo
            if src.exists():
                (root / "2_produktfotos").mkdir(exist_ok=True)
                shutil.copy2(src, root / "2_produktfotos" / photo)
        if p.get("kind") == "pod" and p.get("file") and Path(p["file"]).exists():
            (root / "3_poster-druckdateien").mkdir(exist_ok=True)
            shutil.copy2(p["file"], root / "3_poster-druckdateien" / Path(p["file"]).name)
        if p.get("kind") == "digital":
            for f in p.get("files") or []:
                if Path(f).exists():
                    (root / "4_wallpaper-download").mkdir(exist_ok=True)
                    shutil.copy2(f, root / "4_wallpaper-download" / Path(f).name)
    site = manager.site()
    (root / "5_seiten").mkdir()
    for page in site["pages"]:
        (root / "5_seiten" / f"{page['handle']}.html").write_text(
            f"<h1>{page['title']}</h1>\n{page['body_html']}\n", encoding="utf-8")
    (root / "6_emails").mkdir()
    for key, mail in (manager.db.doc("emails") or {}).items():
        if isinstance(mail, dict):
            (root / "6_emails" / f"{key}.txt").write_text(f"Betreff: {mail['betreff']}\n\n{mail['text']}\n",
                                                          encoding="utf-8")
        else:
            (root / "6_emails" / "hinweis.txt").write_text(f"{mail}\n", encoding="utf-8")
    (root / "LIES-MICH.txt").write_text(readme(name, products, domain_hint), encoding="utf-8")
    for old in base.glob("*.zip"):
        old.unlink()
    for old in base.iterdir():
        if old.is_dir() and old != root:
            shutil.rmtree(old)
    zpath = base / f"{slug}-Shop-Paket.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob("*")):
            if f.is_file():
                z.write(f, f"{root.name}/{f.relative_to(root)}")
    return zpath
