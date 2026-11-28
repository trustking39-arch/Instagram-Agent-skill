"""Die Arbeiter der Shop-Abteilung. Sie laufen auch ohne Sprachmodell; mit Jarvis findet der Scout mehr Ideen."""

from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re

from content_crew.shop.ideas import COLLECTIONS, IDEAS
from content_crew.shop.pricing import ORIGINS, Settings, eur
from content_crew.shop.safety import claims_in

log = logging.getLogger(__name__)

EMPTY_GPSR = {"hersteller": "", "eu_person": "", "kennung": "", "hinweise": "", "bild": ""}


def season_now(today: dt.date | None = None) -> str:
    month = (today or dt.date.today()).month
    if month in (11, 12, 1, 2):
        return "winter"
    if month in (5, 6, 7, 8):
        return "sommer"
    return ""


def slugify(text: str) -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("×", "x")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:80]


def cut(text: str, limit: int) -> str:
    """Auf limit Zeichen kürzen, ohne ein Wort zu zerschneiden."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:–-") + "…"


# --- Produkt-Scout ------------------------------------------------------------
REQUIRED = ("name", "collection", "problem", "solution", "benefits", "usage", "material", "contents", "target",
            "ek", "market", "weight_g", "keywords_en", "hook")

SCOUT_SYSTEM = (
    "Du bist Produkt-Scout für einen kleinen Online-Shop in Österreich. Du schlägst Alltagsprodukte vor, die ein "
    "echtes Problem lösen, im Video gut zu zeigen sind und günstig im Einkauf sind (Einkauf höchstens ein Viertel "
    "des üblichen Verkaufspreises). Verboten: Elektronik, Akkus, Batterien, Lampen, Spielzeug, Kinder- und "
    "Babyartikel, Kosmetik, alles mit Lebensmittelkontakt, Lebensmittel, Schmuck, Medizinprodukte, Waffen, "
    "Chemikalien, Markenware und Fanartikel. Schreib natürliches, korrektes Deutsch ohne Werbeversprechen."
)


class ProductScout:
    def __init__(self, llm=None, use_llm: bool = True):
        self.llm = llm
        self.use_llm = use_llm

    def ideas(self, n: int, exclude: set[str], season: str) -> list[dict]:
        """Erst das geprüfte Startsortiment (Saisonware zuerst, Kategorien gemischt), danach Ideen von Jarvis."""
        pool = [i for i in IDEAS if i["name"] not in exclude and i.get("season", "") in ("", season)]
        pool.sort(key=lambda i: i.get("season", "") != season)
        by_collection: dict[str, list[dict]] = {}
        for idea in pool:
            by_collection.setdefault(idea["collection"], []).append(idea)
        picked: list[dict] = []
        while len(picked) < n and any(by_collection.values()):
            for items in by_collection.values():
                if items and len(picked) < n:
                    picked.append(dict(items.pop(0), source="Startsortiment"))
        if len(picked) < n and self.llm is not None and self.use_llm:
            picked += self.llm_ideas(n - len(picked), exclude | {p["name"] for p in picked}, season)
        return picked

    def llm_ideas(self, n: int, exclude: set[str], season: str) -> list[dict]:
        example = {k: IDEAS[0][k] for k in REQUIRED}
        prompt = (
            f"Schlage {n} neue Produkte vor. Saison: {season or 'ganzjährig'}. Kategorien: "
            f"{', '.join(COLLECTIONS)}. Nicht wiederholen: {', '.join(sorted(exclude)) or '–'}.\n"
            "ek = geschätzter Einkaufspreis [min, max] in Euro bei einem Lieferanten mit EU-Lager, "
            "market = üblicher Verkaufspreis [min, max] in Österreich, weight_g = Versandgewicht in Gramm.\n"
            'JSON: {"ideas": [' + json.dumps(example, ensure_ascii=False) + "]}"
        )
        try:
            result = self.llm.chat_json(SCOUT_SYSTEM, prompt, temperature=0.8)
        except Exception as exc:  # noqa: BLE001 – ohne Jarvis bleibt es beim Startsortiment
            log.warning("Produkt-Scout: Jarvis nicht erreichbar (%s)", exc)
            return []
        raw = result.get("ideas", []) if isinstance(result, dict) else result if isinstance(result, list) else []
        ideas = []
        for item in raw:
            idea = normalize_idea(item)
            if idea and idea["name"] not in exclude:
                ideas.append(dict(idea, source="Jarvis (KI)"))
        return ideas[:n]


def normalize_idea(item) -> dict | None:
    """KI-Vorschlag prüfen und vereinheitlichen; None bei unbrauchbaren Daten."""
    if not isinstance(item, dict) or any(k not in item for k in REQUIRED):
        return None
    try:
        ek = [float(x) for x in item["ek"]][:2]
        market = [float(x) for x in item["market"]][:2]
        weight = int(float(item["weight_g"]))
    except (TypeError, ValueError):
        return None
    benefits = [str(b).strip() for b in item["benefits"] if str(b).strip()] if isinstance(item["benefits"], list) else []
    if len(ek) != 2 or len(market) != 2 or len(benefits) < 2 or not 0.2 <= ek[0] <= ek[1] <= 60:
        return None
    if not 4 <= market[0] <= market[1] <= 200 or not 20 <= weight <= 5000:
        return None
    collection = item["collection"] if item["collection"] in COLLECTIONS else "Ordnung & Zuhause"
    idea = {k: str(item[k]).strip() for k in REQUIRED if k not in ("ek", "market", "weight_g", "benefits")}
    idea.update(collection=collection, ek=ek, market=market, weight_g=weight, benefits=benefits[:3],
                season=str(item.get("season", "")) if item.get("season") in ("winter", "sommer") else "")
    return idea


# --- Einkäufer ------------------------------------------------------------------
class Buyer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def prepare(self, idea: dict) -> dict:
        p = dict(idea)
        p["origin"] = p.get("origin") if p.get("origin") in ORIGINS else self.settings.origin
        confirmed = p.get("cost_confirmed")
        p["unit_cost"] = float(confirmed) if confirmed else float(p["ek"][1])  # ohne Angebot vorsichtig rechnen
        p["price_status"] = "bestätigt" if confirmed else "Schätzung"
        p["delivery_days"] = ORIGINS[p["origin"]]["days"]
        p["supplier_search"] = p.get("keywords_en", "")
        p["gpsr"] = {**EMPTY_GPSR, **(p.get("gpsr") or {})}
        return p


# --- Produkttexter --------------------------------------------------------------
def shipping_sentence(s: Settings) -> str:
    if s.shipping_fee <= 0:
        return "Versandkostenfrei."
    if s.free_from > 0:
        return f"Versand {eur(s.shipping_fee)}, ab {eur(s.free_from)} Bestellwert versandkostenfrei."
    return f"Versand {eur(s.shipping_fee)}."


def product_texts(p: dict, calc: dict, s: Settings) -> dict:
    esc = html.escape
    n = calc["offer"]["n"]
    title = p["name"] if n == 1 else f"{p['name']} – {n}er-Pack"
    contents = p["contents"] if n == 1 else f"{n} × {p['contents']}"
    body = (f"<p>{esc(p['problem'])} {esc(p['solution'])}</p>"
            f"<ul>{''.join(f'<li>{esc(b)}</li>' for b in p['benefits'])}</ul>"
            f"<h3>So funktioniert’s</h3><p>{esc(p['usage'])}</p>"
            f"<h3>Details</h3><ul><li>Material: {esc(p['material'])}</li><li>Lieferumfang: {esc(contents)}</li></ul>"
            + (f"<h3>Download</h3><p>Sofort nach dem Kauf als Download – kein Versand. Mit dem Download beginnt die "
               "Ausführung des Vertrags; dein Widerrufsrecht erlischt, wenn du dem an der Kasse zustimmst.</p>"
               if p.get("origin") == "digital" else
               f"<h3>Versand</h3><p>Lieferzeit {esc(p['delivery_days'])} Werktage. {esc(shipping_sentence(s))}</p>"))
    gpsr = p.get("gpsr") or {}
    if gpsr.get("hersteller"):
        rows = [("Hersteller", gpsr["hersteller"]), ("Verantwortliche Person in der EU", gpsr.get("eu_person", "")),
                ("Produktkennung", gpsr.get("kennung", "")), ("Sicherheitshinweise", gpsr.get("hinweise", ""))]
        body += "<h3>Produktsicherheit</h3><p>" + "<br>".join(f"{k}: {esc(v)}" for k, v in rows if v) + "</p>"
    return {"title": title, "html": body, "short": p["solution"], "contents": contents}


class Copywriter:
    def __init__(self, llm=None, use_llm: bool = False):
        self.llm = llm
        self.use_llm = use_llm

    def write(self, p: dict, calc: dict, s: Settings) -> dict:
        texts = product_texts(p, calc, s)
        if self.llm is None or not self.use_llm:
            return texts
        try:  # Jarvis darf den Einstieg lebendiger formulieren – Fakten bleiben aus dem Datenblatt
            result = self.llm.chat_json(
                SCOUT_SYSTEM,
                "Schreib einen Einstiegsabsatz (2 Sätze, Du-Form) für diese Produktseite. Keine Versprechen, "
                f"die nicht im Datenblatt stehen.\n{json.dumps({k: p[k] for k in ('name', 'problem', 'solution', 'benefits')}, ensure_ascii=False)}\n"
                'JSON: {"einstieg": "..."}', temperature=0.6)
            intro = str(result.get("einstieg", "")).strip() if isinstance(result, dict) else ""
            if 40 <= len(intro) <= 400 and not claims_in(intro):
                texts["html"] = re.sub(r"^<p>.*?</p>", f"<p>{html.escape(intro)}</p>", texts["html"], count=1)
        except Exception as exc:  # noqa: BLE001
            log.warning("Produkttexter: Jarvis nicht erreichbar (%s) – Vorlage bleibt", exc)
        return texts


# --- SEO-Experte ------------------------------------------------------------------
def seo(p: dict, texts: dict, shop_name: str) -> dict:
    title = f"{texts['title']} kaufen | {shop_name}"
    if len(title) > 60:
        title = f"{texts['title']} | {shop_name}"
    if len(title) > 60:
        title = cut(texts["title"], 60)
    benefits = ". ".join(b.rstrip(".") for b in p["benefits"][:2])
    delivery = "Sofort-Download." if p.get("origin") == "digital" else f"Lieferung in {p['delivery_days']} Werktagen."
    desc = cut(f"{p['name']}: {benefits}. {delivery}", 155)
    tags = [p["collection"]] + (["Winter"] if p.get("season") == "winter" else [])
    return {"seo_title": title, "seo_description": desc, "handle": slugify(texts["title"]), "tags": tags}


# --- Werbe-Manager ---------------------------------------------------------------------
def ad_plan(p: dict, calc: dict) -> dict:
    offer = calc["offer"]
    return {
        "hook": p["hook"],
        "video": [f"Problem zeigen: {p['problem']}", f"Produkt in Aktion: {p['solution']}",
                  f"Ergebnis zeigen, dann Preis nennen: {offer['label']} für {eur(offer['price'])}"],
        "zielgruppe": p.get("target", ""),
        "organisch": "3 kurze Videos in 7 Tagen auf TikTok, Shop-Link in der Bio.",
        "bezahlt": (f"Nur mit deiner Freigabe: Test mit 10 € pro Tag für 3 Tage. Stopp, sobald ein Kauf mehr als "
                    f"{eur(calc['max_ads'])} Werbung kostet."),
        "max_cpa": calc["max_ads"],
    }


# --- E-Mail-Marketing ----------------------------------------------------------------------
def email_drafts(shop_name: str, products: list[dict], s: Settings) -> dict:
    top = [p for p in products if p.get("texts")][:3]
    picks = "\n".join(f"– {p['texts']['title']}: {eur(p['calc']['offer']['price'])}" for p in top) or "– …"
    art = " – und Poster und Wallpaper aus unserer TikTok-Serie" if any(
        p.get("kind") in ("pod", "digital") for p in products) else ""
    return {
        "willkommen": {
            "betreff": f"Willkommen bei {shop_name}!",
            "text": (f"Hallo!\n\nSchön, dass du dabei bist. Bei {shop_name} findest du kleine Helfer, die den Alltag "
                     f"leichter machen{art}. {shipping_sentence(s)}\n\nGerade beliebt:\n{picks}\n\nBis bald!"),
        },
        "neu_im_shop": {
            "betreff": "Neu im Shop: Helfer für den Winter",
            "text": f"Hallo!\n\nFrisch im Sortiment:\n{picks}\n\n{shipping_sentence(s)}",
        },
        "warenkorb": {
            "betreff": "Du hast noch etwas im Warenkorb",
            "text": ("Hallo!\n\nDein Warenkorb wartet noch auf dich. Wenn du Fragen zum Produkt oder zum Versand hast, "
                     "antworte einfach auf diese E-Mail."),
        },
        "hinweis": ("Newsletter nur an Leute schicken, die sich mit Bestätigungs-Mail angemeldet haben "
                    "(Double-Opt-in). Die Warenkorb-Erinnerung stellst du in Shopify unter Marketing → "
                    "Automatisierungen ein."),
    }


# --- Kundenservice ----------------------------------------------------------------------------
def faq(s: Settings, email: str = "") -> list[dict]:
    days = ORIGINS[s.origin]["days"]
    contact = f"Schreib uns an {email}." if email else "Schreib uns über das Kontaktformular."
    where = {"eu_lager": "aus Lagern in der EU", "china_direkt": "direkt von unserem Lieferanten in Asien",
             "eigenlager": "aus unserem eigenen Lager in Österreich"}[s.origin]
    return [
        {"q": "Wie lange dauert die Lieferung?",
         "a": f"{days} Werktage nach Zahlungseingang. Die Sendungsnummer bekommst du per E-Mail."},
        {"q": "Was kostet der Versand?", "a": shipping_sentence(s)},
        {"q": "Woher kommen die Produkte?", "a": f"Wir versenden {where}."},
        {"q": "Kann ich etwas zurückgeben?",
         "a": f"Ja. Du kannst innerhalb von 14 Tagen nach Erhalt ohne Angabe von Gründen widerrufen. {contact}"},
        {"q": "Welche Zahlungsarten gibt es?", "a": "Alle verfügbaren Zahlungsarten siehst du an der Kasse."},
        {"q": "Mein Paket ist noch nicht da – was tun?",
         "a": f"Schau zuerst in die Sendungsverfolgung aus der Versandbestätigung. Hilft das nicht weiter: {contact}"},
    ]
