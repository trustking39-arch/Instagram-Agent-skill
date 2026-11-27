"""Die 20 KI-Arbeiter: das Content-Team (TikTok) und die Shop-Abteilung."""

from __future__ import annotations

DEPARTMENTS = {
    "Leitung": "plant und prüft",
    "Content": "TikTok-Videos für Reichweite",
    "Einkauf": "Produkte finden, prüfen, kalkulieren",
    "Website": "Shop aufbauen und pflegen",
    "Marketing": "Kunden in den Shop holen",
    "Betrieb": "Bestellungen, Service, Zahlen",
}

# (Schlüssel, Name, Abteilung, Aufgabe)
WORKERS: list[tuple[str, str, str, str]] = [
    ("jarvis", "Jarvis", "Leitung", "plant, verteilt Aufgaben und prüft alles"),
    ("scout", "Trend-Scout", "Content", "findet, was auf TikTok gerade läuft"),
    ("writer", "Designer", "Content", "entwirft Animation, Musik und Caption"),
    ("producer", "Animator", "Content", "rendert die Videos mit Ton (60 fps)"),
    ("publisher", "Uploader", "Content", "lädt Videos nach deiner Freigabe hoch"),
    ("analyst", "Analyst", "Content", "misst Aufrufe und lernt daraus"),
    ("productscout", "Produkt-Scout", "Einkauf", "sucht Produkte mit guter Marge"),
    ("buyer", "Einkäufer", "Einkauf", "prüft Lieferant, Versand, Zoll und Lieferzeit"),
    ("calculator", "Kalkulator", "Einkauf", "rechnet Preis und Gewinn pro Bestellung"),
    ("safety", "Produktprüfer", "Einkauf", "sortiert riskante Produkte aus (CE, GPSR, Marken)"),
    ("webdesigner", "Webdesigner", "Website", "baut Startseite, Kategorien, Menü und Infoseiten"),
    ("copywriter", "Produkttexter", "Website", "schreibt die Produktseiten auf Deutsch"),
    ("seo", "SEO-Experte", "Website", "macht die Seiten für Google auffindbar"),
    ("legal", "Rechts-Check", "Website", "prüft Impressum, Widerruf und Pflichtangaben"),
    ("shopsync", "Shop-Verwalter", "Website", "stellt Freigegebenes in Shopify online"),
    ("ads", "Werbe-Manager", "Marketing", "plant Anzeigen und Produktvideos, gibt ohne Budget nichts aus"),
    ("email", "E-Mail-Marketing", "Marketing", "schreibt Willkommensmail, Newsletter und Erinnerungen"),
    ("orders", "Bestell-Manager", "Betrieb", "überwacht Bestellungen, Versand und Lieferzeiten"),
    ("support", "Kundenservice", "Betrieb", "beantwortet Kundenfragen und pflegt die FAQ"),
    ("accountant", "Buchhalter", "Betrieb", "rechnet Umsatz, Kosten, Gewinn und Umsatzsteuer"),
]

KEYS = [w[0] for w in WORKERS]
SHOP_KEYS = [w[0] for w in WORKERS if w[2] not in ("Leitung", "Content")]
NAMES = {w[0]: w[1] for w in WORKERS}
