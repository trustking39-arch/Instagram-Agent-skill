"""Webdesigner und Rechts-Check: Aufbau des Shops (Startseite, Kategorien, Menü, Infoseiten) und eine Vorschau."""

from __future__ import annotations

import html
import json

from content_crew.shop.ideas import COLLECTIONS
from content_crew.shop.pricing import ORIGINS, Settings, eur
from content_crew.shop.workers import faq, season_now, shipping_sentence, slugify

LIVE = ("wartet", "freigegeben", "online")


def build_site(shop_name: str, s: Settings, products: list[dict], email: str = "", slogan: str = "") -> dict:
    live = [p for p in products if p["status"] in LIVE]
    seen: list[str] = []
    for p in live:
        if p["collection"] not in seen:
            seen.append(p["collection"])
    collections = [{"title": c, "handle": slugify(c), "text": COLLECTIONS.get(c, ""), "tag": c} for c in seen]
    days = ORIGINS[s.origin]["days"]
    winter = season_now() == "winter"
    questions = faq(s, email)
    esc = html.escape
    pages = [
        {"handle": "ueber-uns", "title": "Über uns", "body_html": (
            f"<p>{esc(shop_name)} ist ein kleiner Online-Shop aus Österreich. Wir suchen Alltagshelfer, die ein "
            "echtes Problem lösen: im Auto, zu Hause, auf Reisen, beim Sport und mit Haustieren.</p>"
            "<p>Viele unserer Produkte zeigen wir in kurzen Videos auf TikTok. So siehst du vor dem Kauf, wie sie "
            "funktionieren.</p>"
            "<p>Unsere Poster und Wallpaper stammen aus unserer TikTok-Serie „24 Hours In …“: Ein Abenteurer reist "
            "durch ein Portal in fremde Welten – von der Eiszeit bis in den Wilden Westen. Was er dort findet, gibt "
            "es bei uns als Kunstdruck.</p>")},
        {"handle": "versand", "title": "Versand & Lieferung", "body_html": (
            f"<p>{esc(shipping_sentence(s))} Die Lieferzeit beträgt {days} Werktage nach Zahlungseingang.</p>"
            "<p>Sobald dein Paket unterwegs ist, bekommst du eine E-Mail mit der Sendungsverfolgung.</p>")},
        {"handle": "faq", "title": "Häufige Fragen", "body_html": "".join(
            f"<h3>{esc(q['q'])}</h3><p>{esc(q['a'])}</p>" for q in questions)},
        {"handle": "kontakt", "title": "Kontakt", "body_html": (
            f"<p>Fragen zu einem Produkt oder deiner Bestellung? Schreib uns an "
            f"{esc(email) if email else '[deine E-Mail-Adresse]'}. Wir antworten werktags innerhalb von 24 "
            "Stunden.</p>")},
    ]
    return {
        "shop_name": shop_name,
        "slogan": slogan,
        "hero": {
            "title": "Gut durch den Winter" if winter else "Clevere Helfer für jeden Tag",
            "text": f"Für Auto, Zuhause, Reise und Haustier. Lieferung in {days} Werktagen.",
            "button": "Jetzt entdecken",
        },
        "usps": [shipping_sentence(s).replace("Versand ", "Versand: ", 1) if s.free_from <= 0 else
                 f"Ab {eur(s.free_from)} versandkostenfrei", f"Lieferung in {days} Werktagen",
                 "14 Tage Widerrufsrecht", "Sichere Bezahlung"],
        "collections": collections,
        "menu": [{"title": "Startseite", "url": "/"}]
                + [{"title": c["title"], "url": f"/collections/{c['handle']}"} for c in collections]
                + [{"title": "Häufige Fragen", "url": "/pages/faq"}, {"title": "Kontakt", "url": "/pages/kontakt"}],
        "pages": pages,
        "faq": questions,
        "footer": ["Impressum", "AGB", "Widerrufsbelehrung", "Datenschutzerklärung", "Versand & Lieferung"],
    }


# --- Rechts-Check --------------------------------------------------------------------
def legal_todos(shop_cfg: dict, connected: bool, gpsr_missing: int, approved: int = 0) -> list[dict]:
    """Was du selbst erledigen musst, bevor der Shop verkaufen darf (Stand Österreich)."""
    owner = shop_cfg.get("owner") or {}
    done = shop_cfg.get("erledigt") or {}
    impressum = all(str(owner.get(k, "")).strip() for k in ("name", "anschrift", "email", "gewerbe", "behoerde"))
    return [
        {"text": "Gewerbe anmelden: Handelsgewerbe (freies Gewerbe), online über usp.gv.at. Die Gründerberatung "
                 "der WKO hilft gratis bei Sozialversicherung, Kleinunternehmerregelung und Steuer.",
         "done": bool(done.get("gewerbe"))},
        {"text": "Shopify-Shop eröffnen und Jarvis verbinden (content-crew setup, Schritt Shopify).",
         "done": connected},
        {"text": "Impressum-Angaben eintragen: Name, Anschrift, E-Mail, Gewerbe und Gewerbebehörde, UID-Nummer "
                 "falls vorhanden.", "done": impressum},
        {"text": "Rechtstexte in Shopify erzeugen (Einstellungen → Richtlinien) und prüfen lassen: AGB, "
                 "Widerrufsbelehrung, Datenschutzerklärung.", "done": bool(done.get("rechtstexte"))},
        {"text": "Lieferanten wählen (z. B. CJdropshipping mit EU-Lager) und seine Shopify-App verbinden. Dann "
                 "gehen Bestellungen automatisch an den Lieferanten.", "done": bool(done.get("lieferant"))},
        {"text": ("Produktsicherheit (GPSR): Für jedes Produkt, das du freigibst, brauchen wir vom Lieferanten "
                  "Hersteller, EU-Verantwortlichen und Sicherheitshinweise." if not approved else
                  f"Produktsicherheit (GPSR): Für {gpsr_missing} freigegebene Produkte fehlen noch Hersteller und "
                  "EU-Verantwortlicher vom Lieferanten." if gpsr_missing else
                  "Produktsicherheit (GPSR): Hersteller und EU-Verantwortlicher sind bei allen freigegebenen "
                  "Produkten eingetragen."), "done": bool(approved) and gpsr_missing == 0},
        {"text": "Verpackungen lizenzieren (Verpackungsverordnung) – beim Lieferanten nachfragen, wer das "
                 "übernimmt.", "done": bool(done.get("verpackung"))},
    ]


# --- Vorschau: der Shop so, wie Kunden ihn sehen (plus Jarvis-Notizen für dich) ---------------------
STATUS = {"wartet": "wartet auf deine Freigabe", "freigegeben": "freigegeben", "online": "online"}

PREVIEW_CSS = """
/* Layout: Shop-Startseite – Hinweisleiste für dich, Ankündigung, fester Kopf mit Warenkorb, Bühne mit Produktbildern,
   Vertrauensleiste, Kategorien, Produktraster, Werte, Fragen, Fuß. Warenkorb als Schublade, Produktseite als Dialog. */
:root {
  --bg: #f7f5f0; --panel: #ffffff; --ink: #141b2d; --muted: #596173; --line: #e5e1d7;
  --navy: #1d2a4f; --on-navy: #ffffff; --navy-soft: #e8ebf3; --gold: #d29b2c; --on-gold: #1d1606;
  --owner: #fff4d6; --on-owner: #4a3500; --ok: #2c7a4b; --warn: #9a5b00; --bad: #b3261e;
  --font-display: "Bricolage Grotesque", "Segoe UI", system-ui, sans-serif;
  --font-body: "Manrope", system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f121a; --panel: #171b26; --ink: #eef0f6; --muted: #a3aabb; --line: #283043;
  --navy: #0b1328; --on-navy: #f2f4f9; --navy-soft: #1c2336; --gold: #e3b04b; --on-gold: #1d1606;
  --owner: #3a2f12; --on-owner: #ffe3a1; --ok: #6fd39a; --warn: #f0b860; --bad: #ff8a80; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0f121a; --panel: #171b26; --ink: #eef0f6; --muted: #a3aabb; --line: #283043;
  --navy: #0b1328; --on-navy: #f2f4f9; --navy-soft: #1c2336; --gold: #e3b04b; --on-gold: #1d1606;
  --owner: #3a2f12; --on-owner: #ffe3a1; --ok: #6fd39a; --warn: #f0b860; --bad: #ff8a80; color-scheme: dark; }
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font: 15px/1.55 var(--font-body); }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 30; background: var(--panel); }
.gut { padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.inner { max-width: 1160px; margin: 0 auto; }
a { color: inherit; }
button { font: inherit; cursor: pointer; }
button:focus-visible, a:focus-visible, summary:focus-visible, select:focus-visible, input:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
.owner { background: var(--owner); color: var(--on-owner); font-size: 13px; }
.owner .inner { display: flex; flex-wrap: wrap; gap: 6px 16px; justify-content: space-between; align-items: center; padding-block: 8px; }
.owner label { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; cursor: pointer; }
.owner input { width: 17px; height: 17px; accent-color: var(--navy); }
.announce { background: var(--navy); color: var(--on-navy); font-size: 13px; font-weight: 600; letter-spacing: .02em; }
.announce .inner { display: flex; flex-wrap: wrap; justify-content: center; gap: 4px 22px; padding-block: 8px; text-align: center; }
header.site { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 20; background: var(--panel); border-bottom: 1px solid var(--line); }
header.site .inner { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 16px; padding-block: 12px; }
.logo { display: flex; align-items: center; gap: 9px; text-decoration: none; }
.logo svg { width: 30px; height: 30px; color: var(--gold); flex: none; }
.logo b { font: 700 22px/1 var(--font-display); letter-spacing: -.02em; }
.logo span { font: 600 13px/1 var(--font-body); color: var(--muted); letter-spacing: .14em; text-transform: uppercase; }
nav.main ul { list-style: none; margin: 0; padding: 0; display: flex; gap: 4px 20px; justify-content: center; flex-wrap: wrap; font-weight: 700; font-size: 14px; }
nav.main a { text-decoration: none; color: var(--muted); }
nav.main a:hover { color: var(--ink); }
.icons { display: flex; gap: 6px; }
.icon-btn { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 12px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); position: relative; }
.icon-btn svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.count { position: absolute; top: -6px; right: -6px; min-width: 20px; height: 20px; border-radius: 10px; padding: 0 5px; background: var(--gold); color: var(--on-gold); font: 800 12px/20px var(--font-body); text-align: center; }
@media (max-width: 760px) {
  header.site .inner { grid-template-columns: 1fr auto; }
  nav.main { grid-column: 1 / -1; order: 3; overflow-x: auto; }
  nav.main ul { justify-content: flex-start; flex-wrap: nowrap; white-space: nowrap; }
}
main { display: grid; grid-template-columns: minmax(0, 1fr); gap: 56px; padding-block: 28px 64px; }
main > section, .hero .inner > *, .collage > div { min-width: 0; }
.hero .inner { display: grid; gap: 28px; align-items: center; grid-template-columns: minmax(0, 1fr); }
@media (min-width: 880px) { .hero .inner { grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); } }
.eyebrow { font: 800 12px/1 var(--font-body); letter-spacing: .16em; text-transform: uppercase; color: var(--gold); }
.hero h1 { font: 700 clamp(36px, 7vw, 64px)/1 var(--font-display); letter-spacing: -.03em; margin: 12px 0 14px; text-wrap: balance; }
.hero p { margin: 0; max-width: 46ch; font-size: 17px; color: var(--muted); }
.ctas { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; border-radius: 12px; padding: 12px 20px; font-weight: 800; text-decoration: none; border: 1px solid transparent; }
.btn.gold { background: var(--gold); color: var(--on-gold); }
.btn.navy { background: var(--navy); color: var(--on-navy); }
.btn.ghost { background: transparent; border-color: var(--line); color: var(--ink); }
.collage { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
.collage > div { position: relative; border-radius: 18px; overflow: hidden; aspect-ratio: 4 / 3; max-width: 100%; }
.collage > div:first-child { grid-column: 1 / -1; aspect-ratio: 8 / 5; }
svg.art { display: block; width: 100%; height: 100%; }
.mock { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: linear-gradient(180deg, #efe9df, #d9cfbf); }
.card .img, .cat .img, .pd .img, .line .thumb { position: relative; overflow: hidden; }
.mock img { display: block; height: 84%; width: auto; max-width: 92%; object-fit: contain; }
.mock.poster img { border: 5px solid #ffffff; box-shadow: 0 10px 22px rgba(20, 20, 30, .28), 0 2px 4px rgba(20, 20, 30, .2); }
.mock.phone img { height: 88%; border-radius: 14px; border: 5px solid #15171d; box-shadow: 0 10px 22px rgba(20, 20, 30, .3); }
.trust ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); }
.trust li { display: grid; grid-template-columns: 40px minmax(0, 1fr); gap: 12px; align-items: center; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; }
.trust svg { width: 40px; height: 40px; padding: 9px; border-radius: 12px; background: var(--navy-soft); fill: none; stroke: var(--ink); stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.trust b { display: block; font-size: 14px; }
.trust span { color: var(--muted); font-size: 13px; }
h2 { font: 700 clamp(24px, 4vw, 32px)/1.1 var(--font-display); letter-spacing: -.02em; margin: 0; text-wrap: balance; }
.head { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: end; justify-content: space-between; margin-bottom: 18px; }
.head p { margin: 4px 0 0; color: var(--muted); }
.cats { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(min(100%, 170px), 1fr)); }
.cat { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; overflow: hidden; text-align: left; padding: 0; color: var(--ink); }
.cat .img { aspect-ratio: 1 / 1; max-width: 100%; }
.cat b { display: block; padding: 10px 12px 2px; font-size: 15px; }
.cat span { display: block; padding: 0 12px 12px; color: var(--muted); font-size: 13px; }
.tools { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.chip { border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 999px; padding: 7px 14px; font-weight: 700; font-size: 14px; }
.chip[aria-pressed="true"] { background: var(--ink); color: var(--bg); border-color: var(--ink); }
select { font: inherit; font-weight: 700; font-size: 14px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 999px; padding: 7px 12px; }
.grid { display: grid; gap: 14px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (min-width: 760px) { .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (min-width: 1040px) { .grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; overflow: hidden; display: grid; grid-template-rows: auto 1fr; min-width: 0; }
.card .img { position: relative; display: block; width: 100%; aspect-ratio: 1 / 1; max-width: 100%; border: 0; padding: 0; background: none; cursor: pointer; }
.art.photo { position: absolute; inset: 0; background-color: #ece9e3; background-size: cover; background-position: center; }
.fill { position: absolute; inset: 0; }
.gallery { position: absolute; left: 12px; bottom: 12px; z-index: 2; display: flex; gap: 8px; flex-wrap: wrap; }
.gallery button { position: relative; width: 54px; height: 54px; padding: 0; border-radius: 10px; overflow: hidden; border: 2px solid #ffffff; background: none; box-shadow: 0 2px 8px rgba(10, 14, 24, .25); }
.gallery button[aria-pressed="true"] { border-color: var(--gold); }
.note { font-size: 12.5px; color: var(--muted); margin: 0; }
.badges { position: absolute; left: 10px; top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
.badge { font: 800 11.5px/1 var(--font-body); padding: 6px 9px; border-radius: 999px; background: var(--gold); color: var(--on-gold); }
.badge.cold { background: var(--navy); color: var(--on-navy); }
.card .body { padding: 12px 14px 14px; display: grid; gap: 6px; align-content: start; min-width: 0; }
.kicker { font: 800 11px/1 var(--font-body); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.card h3 { margin: 0; font: 700 16.5px/1.25 var(--font-display); }
.card h3 button { all: unset; cursor: pointer; }
.card h3 button:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
.short { margin: 0; color: var(--muted); font-size: 13.5px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.price { display: flex; flex-wrap: wrap; gap: 2px 8px; align-items: baseline; font-variant-numeric: tabular-nums; margin-top: 2px; }
.price b { font: 800 20px var(--font-body); }
.price small { color: var(--muted); font-size: 12px; }
.add { margin-top: 6px; width: 100%; border: 0; border-radius: 11px; padding: 11px 12px; background: var(--navy); color: var(--on-navy); font-weight: 800; font-size: 14px; }
.notes { display: none; gap: 4px; border-top: 1px dashed var(--line); margin-top: 6px; padding-top: 8px; font-size: 12.5px; }
.show-notes .notes { display: grid; }
.notes .row { display: flex; justify-content: space-between; gap: 10px; font-variant-numeric: tabular-nums; }
.pill { border-radius: 999px; padding: 2px 8px; font-weight: 800; font-size: 11.5px; border: 1px solid var(--line); }
.pill.ok { color: var(--ok); } .pill.warn { color: var(--warn); } .pill.bad { color: var(--bad); }
.checklist { display: none; background: var(--owner); color: var(--on-owner); border-radius: 18px; padding: 18px 20px; }
.show-notes .checklist { display: block; }
.checklist h2 { font-size: 22px; }
.checklist ul { list-style: none; margin: 12px 0 0; padding: 0; display: grid; gap: 8px; }
.checklist li { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; font-size: 14px; }
.checklist li::before { content: ""; width: 14px; height: 14px; margin-top: 3px; border-radius: 4px; border: 2px solid currentColor; }
.checklist li.done::before { background: var(--ok); border-color: var(--ok); }
.values { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 250px), 1fr)); }
.value { background: var(--navy); color: var(--on-navy); border-radius: 18px; padding: 22px; }
.value b { font: 700 19px/1.2 var(--font-display); display: block; margin-bottom: 6px; }
.value p { margin: 0; opacity: .85; }
.info { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); }
.box { background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 20px; min-width: 0; }
.box h2 { font-size: 24px; margin-bottom: 8px; }
.box details { border-top: 1px solid var(--line); padding: 10px 0; }
.box summary { cursor: pointer; font-weight: 700; }
.box p { margin: 8px 0 0; color: var(--muted); }
footer.site { background: var(--navy); color: var(--on-navy); }
footer.site .inner { display: grid; gap: 24px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr)); padding-block: 40px 24px; }
footer.site h4 { margin: 0 0 10px; font: 800 12px/1 var(--font-body); letter-spacing: .14em; text-transform: uppercase; opacity: .75; }
footer.site ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; font-size: 14px; }
footer.site p { margin: 8px 0 0; font-size: 14px; opacity: .85; max-width: 32ch; }
.legal { grid-column: 1 / -1; border-top: 1px solid rgba(255, 255, 255, .15); padding-top: 16px; font-size: 13px; opacity: .75; display: flex; flex-wrap: wrap; gap: 6px 18px; justify-content: space-between; }
.drawer { position: fixed; inset: 0; z-index: 40; display: grid; justify-items: end; background: rgba(10, 14, 24, .45); }
.drawer[hidden] { display: none !important; }
.drawer .panel { width: min(420px, 100%); height: 100%; background: var(--panel); display: grid; grid-template-rows: auto 1fr auto; padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); padding-right: env(safe-area-inset-right, 0px); }
.drawer header { display: flex; justify-content: space-between; align-items: center; padding: 16px 18px; border-bottom: 1px solid var(--line); }
.drawer h2 { font-size: 22px; }
.lines { overflow: auto; padding: 8px 18px; display: grid; gap: 12px; align-content: start; }
.line { display: grid; grid-template-columns: 64px minmax(0, 1fr) auto; gap: 12px; align-items: center; }
.line .thumb { width: 64px; height: 48px; border-radius: 10px; overflow: hidden; }
.line b { display: block; font-size: 14px; }
.line small { color: var(--muted); }
.qty { display: inline-flex; align-items: center; border: 1px solid var(--line); border-radius: 10px; }
.qty button { width: 30px; height: 30px; border: 0; background: none; color: var(--ink); font-weight: 800; }
.qty span { min-width: 22px; text-align: center; font-variant-numeric: tabular-nums; }
.sum { border-top: 1px solid var(--line); padding: 14px 18px 18px; display: grid; gap: 8px; }
.sum .row { display: flex; justify-content: space-between; font-variant-numeric: tabular-nums; }
.sum .total { font-weight: 800; font-size: 17px; }
.bar { height: 8px; border-radius: 4px; background: var(--navy-soft); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--gold); width: 0; transition: width .3s; }
.hint { font-size: 13px; color: var(--muted); margin: 0; }
.empty { color: var(--muted); padding: 24px 0; text-align: center; }
dialog { border: 0; padding: 0; border-radius: 20px; width: min(920px, calc(100% - 24px)); max-height: calc(100% - 24px); background: var(--panel); color: var(--ink); }
dialog::backdrop { background: rgba(10, 14, 24, .5); }
.pd { display: grid; grid-template-columns: minmax(0, 1fr); }
@media (min-width: 760px) { .pd { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } }
.pd .img { aspect-ratio: 4 / 3; max-width: 100%; }
@media (min-width: 760px) { .pd .img { aspect-ratio: auto; height: 100%; min-height: 320px; } }
.pd .txt { padding: 20px 22px 24px; display: grid; gap: 10px; align-content: start; min-width: 0; }
.pd h2 { font-size: 26px; }
.pd ul { margin: 0; padding-left: 18px; }
.pd details { border-top: 1px solid var(--line); padding: 10px 0; }
.pd summary { cursor: pointer; font-weight: 800; }
.pd details div { font-size: 14px; color: var(--ink); }
.pd details h3 { font: 800 14px var(--font-body); margin: 12px 0 4px; }
.close { position: absolute; right: 12px; top: 12px; z-index: 2; }
.toast { position: fixed; left: 50%; bottom: calc(18px + env(safe-area-inset-bottom, 0px)); transform: translateX(-50%); z-index: 60; background: var(--ink); color: var(--bg); padding: 11px 16px; border-radius: 12px; font-weight: 700; font-size: 14px; max-width: calc(100% - 32px); }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

LOGO = ('<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" '
        'stroke-width="2.4"/><path d="M12 6.4l1.5 4.1 4.1 1.5-4.1 1.5-1.5 4.1-1.5-4.1-4.1-1.5 4.1-1.5z" '
        'fill="currentColor"/></svg>')
ICON = {
    "bag": '<path d="M6 8h12l-1 12H7z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "truck": '<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
    "return": '<path d="M9 7L5 11l4 4"/><path d="M5 11h9a5 5 0 0 1 0 10h-3"/>',
    "lock": '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
}


def _svg(name: str) -> str:
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICON[name]}</svg>'


def _pill(level: str) -> str:
    cls = {"ok": "ok", "warnung": "warn", "blockiert": "bad"}.get(level, "")
    label = {"ok": "ohne Befund", "warnung": "Hinweise beachten", "blockiert": "gesperrt"}.get(level, level)
    return f'<span class="pill {cls}">{html.escape(label)}</span>'


def _card(p: dict, art: str) -> str:
    esc = html.escape
    offer = p["calc"]["offer"]
    badges = ""
    if offer["n"] > 1:
        badges += f'<span class="badge">{esc(offer["label"].replace("Set", "Pack"))}</span>'
    if p.get("season") == "winter":
        badges += '<span class="badge cold">Winter-Tipp</span>'
    per = f'<small>{eur(offer["per_item"])} pro Stück</small>' if offer["n"] > 1 else ""
    warn = "".join(f'<div class="hint">· {esc(w.split(":")[0])}</div>' for w in p["safety"]["warnings"][:2])
    notes = (f'<div class="notes"><div class="row"><b>P{p["id"]}</b><span>{esc(STATUS.get(p["status"], p["status"]))}</span></div>'
             f'<div class="row"><span>Gewinn pro Bestellung</span><b>{eur(p["calc"]["profit"])}</b></div>'
             f'<div class="row"><span>Marge</span><b>{p["calc"]["margin"]:.0f} %</b></div>'
             f'<div class="row"><span>Einkauf ({esc(p.get("price_status", "Schätzung"))})</span><b>{eur(p["unit_cost"])}</b></div>'
             f'<div class="row"><span>Preislage</span><b>{esc(p["calc"]["position"])}</b></div>'
             f'<div class="row"><span>Produktprüfer</span>{_pill(p["safety"]["level"])}</div>{warn}</div>')
    return (f'<article class="card" data-id="{p["id"]}" data-c="{esc(p["collection"])}" data-price="{offer["price"]}">'
            f'<button class="img" data-open="{p["id"]}" aria-label="{esc(p["texts"]["title"])} ansehen">'
            f'{art}<span class="badges">{badges}</span></button>'
            f'<div class="body"><span class="kicker">{esc(p["collection"])}</span>'
            f'<h3><button data-open="{p["id"]}">{esc(p["texts"]["title"])}</button></h3>'
            f'<p class="short">{esc(" · ".join(b.rstrip(".") for b in p.get("benefits", [])[:2]) or p["texts"]["short"])}</p>'
            f'<div class="price"><b>{eur(offer["price"])}</b>{per}<small>inkl. USt.</small></div>'
            f'<button class="add" data-add="{p["id"]}">In den Warenkorb</button>{notes}</div></article>')


def render_preview(site: dict, products: list[dict], todos: list[dict] | None = None, stamp: str = "",
                   s: Settings | None = None) -> str:
    """Shop-Vorschau als eigenständige Seite (ohne <html>-Gerüst; für Dashboard und Artifact)."""
    from content_crew.shop.art import product_art
    from content_crew.shop.fotos import photo_data

    esc = html.escape
    s = s or Settings()
    shown = [p for p in products if p["status"] in LIVE and p.get("texts")]
    winter_first = sorted(shown, key=lambda p: p.get("season") != "winter")
    photos = {p["id"]: photo_data(p) for p in shown}
    # Jedes Foto steht nur einmal in der Seite (als CSS-Klasse) und wird in Karte, Kategorie und Dialog wiederverwendet
    photo_css = "".join(f".ph-{pid}-{k}{{background-image:url({uri})}}"
                        for pid, uris in photos.items() for k, uri in enumerate(uris))

    def art_for(p: dict) -> str:
        if photos.get(p["id"]):
            return f'<div class="art photo ph-{p["id"]}-0" role="img" aria-label="{esc(p["texts"]["title"])}"></div>'
        return product_art(p)

    arts = {p["id"]: art_for(p) for p in shown}
    waiting = sum(1 for p in shown if p["status"] == "wartet")
    days = ORIGINS[s.origin]["days"]
    name = site["shop_name"]
    brand, _, rest = name.partition(" ")
    ship_line = (f"Ab {eur(s.free_from)} versandkostenfrei" if s.free_from > 0 else shipping_sentence(s))
    art_first = sorted([p for p in shown if p.get("image") and p.get("kind") == "pod"],
                       key=lambda p: ["iceage", "arctic", "medieval"].index(p["world"])
                       if p.get("world") in ("iceage", "arctic", "medieval") else 9)
    hero_items = (art_first + winter_first)[:3]
    hero_arts = [arts[p["id"]] for p in hero_items]
    if hero_arts and hero_arts[0].startswith("<svg"):
        hero_arts[0] = hero_arts[0].replace('viewBox="0 0 400 300"', 'viewBox="0 25 400 250"', 1)
    collage = "".join(f"<div>{a}</div>" for a in hero_arts)
    counts: dict[str, int] = {}
    for p in shown:
        counts[p["collection"]] = counts.get(p["collection"], 0) + 1
    first = {}
    for p in shown:
        first.setdefault(p["collection"], p)
    cats = "".join(
        f'<button class="cat" data-f="{esc(c["title"])}"><div class="img">{arts[first[c["title"]]["id"]]}</div>'
        f'<b>{esc(c["title"])}</b><span>{counts.get(c["title"], 0)} Produkte</span></button>'
        for c in site["collections"] if c["title"] in first)
    chips = '<button class="chip" aria-pressed="true" data-f="">Alle</button>' + "".join(
        f'<button class="chip" aria-pressed="false" data-f="{esc(c["title"])}">{esc(c["title"])}</button>'
        for c in site["collections"] if c["title"] in first)
    nav = "".join(f'<li><a href="#produkte" data-f="{esc(c["title"])}">{esc(c["title"])}</a></li>'
                  for c in site["collections"] if c["title"] in first)
    faq_html = "".join(f"<details><summary>{esc(q['q'])}</summary><p>{esc(q['a'])}</p></details>" for q in site["faq"])
    pages = {pg["handle"]: pg for pg in site["pages"]}
    todo_html = ""
    if todos is not None:
        items = "".join(f'<li class="{"done" if t["done"] else ""}">{esc(t["text"])}</li>' for t in todos)
        todo_html = (f'<section class="gut"><div class="inner checklist"><h2>Für dich: Das fehlt noch, bevor der '
                     f'Shop verkaufen darf</h2><ul>{items}</ul></div></section>')
    data = [{"id": p["id"], "title": p["texts"]["title"], "price": p["calc"]["offer"]["price"],
             "label": p["calc"]["offer"]["label"], "n": p["calc"]["offer"]["n"], "collection": p["collection"],
             "short": p["texts"]["short"], "html": p["texts"]["html"], "benefits": p.get("benefits", []),
             "days": p.get("delivery_days", days),
             "gallery": [f"ph-{p['id']}-{k}" for k in range(len(photos.get(p["id"], [])))],
             "note": ("Abbildung mit Rahmen und Deko – geliefert wird das Poster ohne Rahmen."
                      if p.get("kind") == "pod" else "")} for p in shown]
    origin_text = {"eu_lager": "aus Lagern in der EU", "china_direkt": "direkt vom Lieferanten",
                   "eigenlager": "aus unserem Lager in Österreich"}[s.origin]
    script = """
<script>
(() => {
  const D = JSON.parse(document.getElementById('shopData').textContent);
  const byId = Object.fromEntries(D.products.map((p) => [p.id, p]));
  const $ = (q) => document.querySelector(q);
  const eur = (v) => v.toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
  let cart = {};
  try { cart = JSON.parse(localStorage.getItem('shop-cart') || '{}') || {}; } catch (e) { cart = {}; }
  const save = () => { try { localStorage.setItem('shop-cart', JSON.stringify(cart)); } catch (e) {} };
  let toastTimer;
  function toast(text) {
    const t = $('#toast'); t.textContent = text; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
  }
  function art(id) { const el = document.querySelector(`.card[data-id="${id}"] .art`); return el ? el.outerHTML : ''; }
  function render() {
    const ids = Object.keys(cart).filter((id) => cart[id] > 0 && byId[id]);
    const count = ids.reduce((n, id) => n + cart[id], 0);
    $('#count').textContent = count; $('#count').hidden = count === 0;
    const lines = $('#lines'); lines.replaceChildren();
    if (!ids.length) { lines.innerHTML = '<p class="empty">Dein Warenkorb ist leer.</p>'; }
    for (const id of ids) {
      const p = byId[id];
      const row = document.createElement('div'); row.className = 'line';
      row.innerHTML = `<div class="thumb">${art(id)}</div><div><b></b><small></small></div>`
        + `<div class="qty"><button aria-label="weniger">−</button><span>${cart[id]}</span><button aria-label="mehr">+</button></div>`;
      row.querySelector('b').textContent = p.title;
      row.querySelector('small').textContent = eur(p.price * cart[id]);
      const [minus, plus] = row.querySelectorAll('.qty button');
      minus.onclick = () => { cart[id] -= 1; if (cart[id] <= 0) delete cart[id]; save(); render(); };
      plus.onclick = () => { cart[id] += 1; save(); render(); };
      lines.append(row);
    }
    const sub = ids.reduce((sum, id) => sum + byId[id].price * cart[id], 0);
    const physical = ids.some((id) => byId[id].days !== 'sofort');
    const free = D.freeFrom > 0 && sub >= D.freeFrom;
    const ship = !physical || free ? 0 : D.fee;
    $('#sub').textContent = eur(sub);
    $('#ship').textContent = ids.length ? (ship ? eur(ship) : 'gratis') : '–';
    $('#total').textContent = eur(sub + ship);
    const left = Math.max(0, D.freeFrom - sub);
    $('#barFill').style.width = D.freeFrom > 0 ? Math.min(100, sub / D.freeFrom * 100) + '%' : '100%';
    $('#freeHint').textContent = !ids.length ? '' : !physical ? 'Nur Downloads im Warenkorb – kein Versand nötig.'
      : !D.freeFrom ? '' : left > 0 ? `Noch ${eur(left)} bis zum Gratisversand.` : 'Du bekommst Gratisversand.';
  }
  function add(id, n = 1) { cart[id] = (cart[id] || 0) + n; save(); render(); toast(`„${byId[id].title}“ liegt im Warenkorb.`); }
  const drawer = $('#drawer');
  function openCart() { drawer.hidden = false; $('#closeCart').focus(); }
  function closeCart() { drawer.hidden = true; $('#cartBtn').focus(); }
  $('#cartBtn').onclick = openCart; $('#closeCart').onclick = closeCart;
  drawer.addEventListener('click', (e) => { if (e.target === drawer) closeCart(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !drawer.hidden) closeCart(); });
  $('#checkout').onclick = () => toast('Vorschau: Die Kasse kommt, sobald der Shop mit Shopify verbunden ist.');
  $('#searchBtn').onclick = () => { $('#produkte').scrollIntoView({ behavior: 'smooth' }); $('#sort').focus(); };
  const dlg = $('#pd');
  let current = null, qty = 1;
  function openProduct(id) {
    const p = byId[id]; current = id; qty = 1;
    $('#pdImg').innerHTML = art(id);
    const gal = $('#pdGallery'); gal.replaceChildren();
    if (p.gallery.length > 1) {
      p.gallery.forEach((cls, i) => {
        const b = document.createElement('button');
        b.type = 'button'; b.setAttribute('aria-label', `Bild ${i + 1} von ${p.gallery.length}`);
        b.setAttribute('aria-pressed', String(i === 0));
        b.innerHTML = `<div class="art photo ${cls}"></div>`;
        b.onclick = () => {
          const main = $('#pdImg .art'); if (main) main.className = `art photo ${cls}`;
          gal.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        };
        gal.append(b);
      });
    }
    $('#pdNote').textContent = p.note;
    $('#pdKicker').textContent = p.collection;
    $('#pdTitle').textContent = p.title;
    $('#pdPrice').textContent = eur(p.price);
    $('#pdPer').textContent = p.n > 1 ? `${p.label.replace('Set', 'Pack')} · ${eur(p.price / p.n)} pro Stück` : '';
    $('#pdShort').textContent = p.short;
    const ul = $('#pdBenefits'); ul.replaceChildren(...p.benefits.map((b) => { const li = document.createElement('li'); li.textContent = b; return li; }));
    $('#pdDesc').innerHTML = p.html;
    $('#pdShip').textContent = p.days === 'sofort'
      ? 'Sofort nach dem Kauf als Download – kein Versand. Dein Widerrufsrecht erlischt mit dem Download, wenn du dem an der Kasse zustimmst.'
      : `Lieferzeit ${p.days} Werktage. ${D.shipText} Du kannst innerhalb von 14 Tagen ohne Angabe von Gründen widerrufen.`;
    $('#pdQty').textContent = qty;
    dlg.showModal();
  }
  $('#pdMinus').onclick = () => { qty = Math.max(1, qty - 1); $('#pdQty').textContent = qty; };
  $('#pdPlus').onclick = () => { qty += 1; $('#pdQty').textContent = qty; };
  $('#pdAdd').onclick = () => { add(current, qty); dlg.close(); };
  $('#pdClose').onclick = () => dlg.close();
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  document.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => openProduct(b.dataset.open)));
  document.querySelectorAll('[data-add]').forEach((b) => b.addEventListener('click', () => add(b.dataset.add)));
  const chips = [...document.querySelectorAll('.chip')];
  function filter(f) {
    chips.forEach((x) => x.setAttribute('aria-pressed', String((x.dataset.f || '') === f)));
    document.querySelectorAll('.card').forEach((c) => { c.hidden = !!f && c.dataset.c !== f; });
  }
  chips.forEach((c) => c.addEventListener('click', () => filter(c.dataset.f || '')));
  document.querySelectorAll('.cat, nav.main a').forEach((c) => c.addEventListener('click', () => {
    filter(c.dataset.f || ''); $('#produkte').scrollIntoView({ behavior: 'smooth' });
  }));
  const grid = $('#grid');
  const original = [...grid.children];
  $('#sort').addEventListener('change', (e) => {
    const cards = [...original];
    if (e.target.value === 'auf') cards.sort((a, b) => a.dataset.price - b.dataset.price);
    if (e.target.value === 'ab') cards.sort((a, b) => b.dataset.price - a.dataset.price);
    grid.replaceChildren(...cards);
  });
  const notes = $('#showNotes');
  const apply = () => document.body.classList.toggle('show-notes', notes.checked);
  notes.addEventListener('change', apply); apply();
  render();
})();
</script>"""
    shop_data = json.dumps({"products": data, "fee": s.shipping_fee, "freeFrom": s.free_from,
                            "shipText": shipping_sentence(s)},
                           ensure_ascii=False).replace("</", "<\\/")
    year = str(__import__("datetime").date.today().year)
    return f"""<title>{esc(name)} Vorschau</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=Manrope:wght@400;600;700;800&display=swap">
<style>{PREVIEW_CSS}{photo_css}</style>
<div class="wrap">
<div class="owner gut"><div class="inner"><span><b>Vorschau für dich</b> · noch nicht online{" · " + esc(stamp) if stamp else ""} · {waiting} Produkte warten auf deine Freigabe</span>
<label><input type="checkbox" id="showNotes"> Jarvis-Notizen</label></div></div>
<div class="announce gut"><div class="inner"><span>{esc(ship_line)}</span><span>Lieferung in {esc(days)} Werktagen</span><span>14 Tage Widerrufsrecht</span></div></div>
<header class="site gut"><div class="inner">
  <a class="logo" href="#top" aria-label="{esc(name)} Startseite">{LOGO}<b>{esc(brand)}</b><span>{esc(rest)}</span></a>
  <nav class="main" aria-label="Kategorien"><ul>{nav}</ul></nav>
  <div class="icons"><button class="icon-btn" id="searchBtn" aria-label="Produkte durchsuchen">{_svg("search")}</button>
  <button class="icon-btn" id="cartBtn" aria-label="Warenkorb öffnen">{_svg("bag")}<span class="count" id="count" hidden>0</span></button></div>
</div></header>
<main id="top">
  <section class="hero gut"><div class="inner">
    <div><span class="eyebrow">{"Winter-Auswahl" if winter_first and winter_first[0].get("season") == "winter" else "Neu im Shop"}</span>
    <h1>{esc(site["hero"]["title"])}</h1>
    <p>Kleine Helfer, die ein echtes Problem lösen – fürs Auto, für zu Hause, für die Reise und dein Haustier. Dazu Poster und Wallpaper aus unserer TikTok-Serie „24 Hours In …“.</p>
    <div class="ctas"><a class="btn gold" href="#produkte">Jetzt entdecken</a><a class="btn ghost" href="#hilfe">Versand &amp; Rückgabe</a></div></div>
    <div class="collage">{collage}</div>
  </div></section>
  <section class="trust gut"><div class="inner"><ul>
    <li>{_svg("truck")}<div><b>{esc(ship_line)}</b><span>sonst {eur(s.shipping_fee)} Versand</span></div></li>
    <li>{_svg("clock")}<div><b>Lieferung in {esc(days)} Werktagen</b><span>mit Sendungsverfolgung</span></div></li>
    <li>{_svg("return")}<div><b>14 Tage Widerrufsrecht</b><span>ohne Angabe von Gründen</span></div></li>
    <li>{_svg("lock")}<div><b>Sichere Bezahlung</b><span>verschlüsselt an der Kasse</span></div></li>
  </ul></div></section>
  {todo_html}
  <section class="gut"><div class="inner"><div class="head"><div><h2>Kategorien</h2><p>Finde den passenden Helfer.</p></div></div>
  <div class="cats">{cats}</div></div></section>
  <section class="gut" id="produkte"><div class="inner">
    <div class="head"><div><h2>Unsere Produkte</h2><p>Alle Preise inkl. USt., zzgl. Versand.</p></div>
    <div class="tools"><label class="hint" for="sort">Sortieren</label><select id="sort"><option value="">Empfohlen</option>
    <option value="auf">Preis aufsteigend</option><option value="ab">Preis absteigend</option></select></div></div>
    <div class="tools" role="group" aria-label="Kategorie wählen" style="margin-bottom:16px">{chips}</div>
    <div class="grid" id="grid">{"".join(_card(p, arts[p["id"]]) for p in shown)}</div>
  </div></section>
  <section class="gut"><div class="inner values">
    <div class="value"><b>Ausgesucht statt Massenware</b><p>Wir nehmen nur Produkte, die ein Alltagsproblem lösen und die wir dir in kurzen Videos zeigen können.</p></div>
    <div class="value"><b>Ehrliche Preise</b><p>Keine erfundenen Streichpreise. Der Preis, den du siehst, ist der Preis.</p></div>
    <div class="value"><b>Rückgabe ohne Stress</b><p>Passt etwas nicht, hast du 14 Tage Zeit. Schreib uns einfach.</p></div>
  </div></section>
  <section class="gut" id="hilfe"><div class="inner info">
    <div class="box"><h2>Häufige Fragen</h2>{faq_html}</div>
    <div class="box"><h2>{esc(pages["ueber-uns"]["title"])}</h2>{pages["ueber-uns"]["body_html"]}
    <h2 style="margin-top:18px">{esc(pages["versand"]["title"])}</h2>{pages["versand"]["body_html"]}</div>
  </div></section>
</main>
<footer class="site gut"><div class="inner">
  <div><a class="logo" href="#top">{LOGO}<b>{esc(brand)}</b><span>{esc(rest)}</span></a>
  <p>{esc(site.get("slogan") or "Clevere Alltagshelfer aus Österreich")} – Kunst aus unserer TikTok-Serie und kleine Helfer für jeden Tag, geliefert zu dir.</p></div>
  <div><h4>Shop</h4><ul>{"".join(f"<li>{esc(c['title'])}</li>" for c in site["collections"] if c["title"] in first)}</ul></div>
  <div><h4>Hilfe</h4><ul><li>Versand &amp; Lieferung</li><li>Rückgabe &amp; Widerruf</li><li>Häufige Fragen</li><li>Kontakt</li></ul></div>
  <div><h4>Rechtliches</h4><ul>{"".join(f"<li>{esc(f)}</li>" for f in site["footer"] if f != "Versand & Lieferung")}</ul></div>
  <div class="legal"><span>© {esc(year)} {esc(name)}</span><span>Alle Preise inkl. USt., zzgl. Versandkosten</span></div>
</div></footer>
<div class="drawer" id="drawer" hidden><div class="panel" role="dialog" aria-modal="true" aria-labelledby="cartTitle">
  <header><h2 id="cartTitle">Warenkorb</h2><button class="icon-btn" id="closeCart" aria-label="Warenkorb schließen">{_svg("x")}</button></header>
  <div class="lines" id="lines"></div>
  <div class="sum"><div class="bar"><i id="barFill"></i></div><p class="hint" id="freeHint"></p>
    <div class="row"><span>Zwischensumme</span><span id="sub">0,00 €</span></div>
    <div class="row"><span>Versand</span><span id="ship">–</span></div>
    <div class="row total"><span>Gesamt inkl. USt.</span><span id="total">0,00 €</span></div>
    <button class="btn gold" id="checkout">Zur Kasse</button></div>
</div></div>
<dialog id="pd" aria-labelledby="pdTitle"><div style="position:relative"><button class="icon-btn close" id="pdClose" aria-label="Schließen">{_svg("x")}</button>
  <div class="pd"><div class="img"><div class="fill" id="pdImg"></div><div class="gallery" id="pdGallery"></div></div><div class="txt">
    <span class="kicker" id="pdKicker"></span><h2 id="pdTitle"></h2>
    <div class="price"><b id="pdPrice"></b><small>inkl. USt., zzgl. Versand</small></div><small class="hint" id="pdPer"></small>
    <p class="note" id="pdNote"></p><p class="hint" id="pdShort"></p><ul id="pdBenefits"></ul>
    <div class="tools"><div class="qty"><button id="pdMinus" aria-label="weniger">−</button><span id="pdQty">1</span><button id="pdPlus" aria-label="mehr">+</button></div>
    <button class="btn navy" id="pdAdd">In den Warenkorb</button></div>
    <details><summary>Beschreibung</summary><div id="pdDesc"></div></details>
    <details><summary>Versand &amp; Rückgabe</summary><div><p id="pdShip"></p></div></details>
  </div></div></div></dialog>
<div class="toast" id="toast" role="status" hidden></div>
<script type="application/json" id="shopData">{shop_data}</script>
</div>{script}"""


def wrap_page(fragment: str) -> str:
    """Für den eigenen Webserver: Vorschau in ein vollständiges HTML-Dokument packen."""
    head, body = fragment.split('<div class="wrap">', 1)
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'{head}</head><body><div class="wrap">{body}</body></html>')


def site_json(site: dict) -> str:
    return json.dumps(site, ensure_ascii=False, indent=1)
