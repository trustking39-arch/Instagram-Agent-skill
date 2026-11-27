"""Produktprüfer: sortiert Produkte aus, die für einen kleinen Shop rechtlich riskant sind.

Kein Ersatz für eine Rechtsberatung – aber er hält das Team von den typischen Fallen fern
(CE-Pflicht, Spielzeug, Kosmetik, Lebensmittelkontakt, Schmuck, Markenrechte, Gefahrstoffe).
"""

from __future__ import annotations

import re

B = r"(?<![a-zäöüß])"  # Wortanfang
E = r"(?![a-zäöüß])"   # Wortende

# (Kategorie, Muster) – ein Treffer sperrt das Produkt
BLOCK: list[tuple[str, list[str]]] = [
    ("Elektronik, Akku oder Batterie (CE, Elektrogeräte- und Batterierecht)", [
        "usb", "akku", "batterie", B + "led" + E, "ladegerät", "ladekabel", "netzteil", "bluetooth", "elektrisch",
        "elektronisch", B + "elektro", "powerbank", "lautsprecher", "kopfhörer", B + "solar", "smartwatch",
        B + "smart" + E, "wlan", "wifi", "lampe", "leuchte", "lichterkette", "ventilator", "heizdecke", "beheizt",
        "fernbedienung", "kamera", B + "motor", "vibration"]),
    ("Spielzeug oder Kinderartikel (Spielzeugrichtlinie)", [
        "(?<!katzen)(?<!hunde)spielzeug", B + "kinder", "baby", "kleinkind", "säugling", "schnuller", "rassel",
        "kuscheltier", "plüsch"]),
    ("Kosmetik oder Körperpflege (Kosmetikverordnung)", [
        B + "creme", "serum", "kosmetik", "make-up", "makeup", "parfum", "parfüm", "lotion", "shampoo",
        "haarfarbe", "nagellack", "lippenstift", "zahnaufhellung", "bleaching", "duftöl", "körperöl", "badesalz",
        B + "seife"]),
    ("Kontakt mit Lebensmitteln (Lebensmittelkontakt-Verordnung)", [
        "becher", B + "tasse", "teller", "besteck", "flasche", "brotdose", "lunchbox", "backform", "schneidebrett",
        "strohhalm", "trinkhalm", "frischhalte", "vorratsdose", "kochlöffel", "pfanne", "kochtopf", "eiswürfel",
        "thermos", "geschirr"]),
    ("Lebensmittel oder Nahrungsergänzung", [
        "nahrungsergänzung", "vitamin", "protein", B + "tee" + E, "kaffee", "snack", "süßigkeit", "kapseln"]),
    ("Schmuck (Grenzwerte für Nickel, Cadmium und Blei)", [
        "schmuck", "halskette", "armband", "ohrring", "piercing", "fingerring", "fußkettchen", "armreif", "brosche"]),
    ("Medizin oder Gesundheitsversprechen (Medizinprodukterecht)", [
        "medizin", "therapie", B + "heilt", "heilung", "orthopäd", "haltungskorrektur", "bandage", "orthese",
        "kompressionsstrumpf", "blutdruck", "fieber", "schwanger", "inkontinenz", "atemschutz", "ffp2",
        "mundschutz"]),
    ("Waffe oder gefährlicher Gegenstand", [
        "messer", "klinge", "schlagring", "pfefferspray", "laserpointer", "feuerwerk", "softair", "airsoft",
        "armbrust", "schleuder", "elektroschocker", "taser", "dolch", "schwert", "munition", "feuerzeug"]),
    ("Chemikalie (Kennzeichnung nach CLP-Verordnung)", [
        "reiniger", "reinigungsmittel", B + "spray", "kleber", "klebstoff", "lösungsmittel", "ätherisch",
        "wandfarbe", B + "lack" + E, "pestizid", "dünger", "insektizid"]),
    ("Markenware oder Fanartikel (Marken- und Urheberrecht)", [
        B + w + E for w in ("nike", "adidas", "apple", "iphone", "samsung", "disney", "marvel", "pokemon",
                            "pokémon", "lego", "stanley", "dyson", "gucci", "louis vuitton", "chanel", "rolex",
                            "ikea", "playstation", "nintendo", "barbie", "harry potter", "star wars", "minecraft",
                            "fortnite", "hello kitty", "sanrio", "airpods", "tesla", "ferrari", "porsche")]),
]

# (Hinweis, Muster) – ein Treffer ist erlaubt, braucht aber Sorgfalt in Text und Produktangaben
WARN: list[tuple[str, list[str]]] = [
    ("Textil: Die Faserzusammensetzung muss auf dem Etikett und der Produktseite stehen.", [
        "baumwolle", "polyester", "nylon", "elasthan", "textil", "fleece", B + "samt" + E, "oxford-gewebe"]),
    ("Latex: In der Beschreibung auf Latex hinweisen (Allergie).", ["latex"]),
    ("Starke Magnete: Warnhinweis für Herzschrittmacher und Kinder beilegen.", ["magnet", "neodym"]),
    ("Sport: Sicherheits- und Gebrauchshinweise (Belastung, Prüfen vor Gebrauch) auf Deutsch beilegen.", [
        "fitness", "training", "widerstand", "liegestütz", "springseil", "klimmzug"]),
    ("Auto: Hinweis, dass Sicht, Airbags und Bedienung nicht behindert werden dürfen.", [
        B + "auto", B + "kfz", "windschutzscheibe", "lüftungsgitter", "kofferraum"]),
    ("Keine Heil- oder Gesundheitsversprechen in Texten und Videos, nur Komfort beschreiben.", [
        "schmerz", "rücken", "haltung", "entspann", "massage", "gesund", B + "schlaf", "verspann"]),
]

GPSR_FIELDS = {
    "hersteller": "Hersteller mit Name, Postanschrift und E-Mail",
    "eu_person": "Verantwortliche Person in der EU (wenn der Hersteller außerhalb der EU sitzt)",
    "kennung": "Produktkennung (Typ-, Modell- oder Chargennummer)",
    "hinweise": "Warn- und Sicherheitshinweise auf Deutsch",
    "bild": "Produktfoto",
}


def _text(product: dict) -> str:
    parts = [product.get(k, "") for k in ("name", "collection", "material", "contents", "problem", "solution",
                                          "usage")]
    parts += list(product.get("benefits") or [])
    return " ".join(str(p) for p in parts).lower()


def _hits(text: str, patterns: list[str]) -> list[str]:
    found = []
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            found.append(m.group(0))
    return found


def check(product: dict) -> dict:
    """{"level": ok|warnung|blockiert, "blocked": [...], "warnings": [...], "gpsr_missing": [...]}"""
    text = _text(product)
    blocked = []
    for label, patterns in BLOCK:
        hits = _hits(text, patterns)
        if hits:
            blocked.append(f"{label} – gefunden: „{hits[0]}“")
    warnings = [label for label, patterns in WARN if _hits(text, patterns)]
    gpsr = product.get("gpsr") or {}
    missing = [desc for key, desc in GPSR_FIELDS.items() if not str(gpsr.get(key, "")).strip()]
    level = "blockiert" if blocked else ("warnung" if warnings else "ok")
    return {"level": level, "blocked": blocked, "warnings": warnings, "gpsr_missing": missing}


def claims_in(text: str) -> list[str]:
    """Heikle Versprechen in einem fertigen Werbe- oder Produkttext finden."""
    risky = [B + "heilt", "heilung", "garantiert", "100 %", "100%", "wundermittel", "schmerzfrei", "klinisch",
             "dermatologisch", "abnehmen", "fettverbrennung", "für immer", "nie wieder"]
    return _hits(text.lower(), risky)
