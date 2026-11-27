"""Webdesigner und Rechts-Check: Aufbau des Shops (Startseite, Kategorien, Menü, Infoseiten) und eine Vorschau."""

from __future__ import annotations

import html
import json

from content_crew.shop.ideas import COLLECTIONS
from content_crew.shop.pricing import ORIGINS, Settings, eur
from content_crew.shop.workers import faq, season_now, shipping_sentence, slugify

LIVE = ("wartet", "freigegeben", "online")


def build_site(shop_name: str, s: Settings, products: list[dict], email: str = "") -> dict:
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
            "funktionieren.</p>")},
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


# --- Vorschau ------------------------------------------------------------------------------
ICONS = {  # einfache Symbole je Kategorie (24×24, Strichzeichnung)
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
}
TINTS = {"Auto & Unterwegs": "--t1", "Ordnung & Zuhause": "--t2", "Reisen": "--t3", "Sport & Fitness": "--t4",
         "Haustiere": "--t5", "Schreibtisch & Handy": "--t6"}
STATUS = {"wartet": "wartet auf deine Freigabe", "freigegeben": "freigegeben", "online": "online"}

PREVIEW_CSS = """
/* Layout: ein heller Laden – Hinweisleiste, Kopf mit Menü, Bühne, Vorteile, Kategorien, Produktraster, Infos */
:root {
  --bg: #f6f4ef; --panel: #ffffff; --ink: #172033; --muted: #5b6475; --line: #e3dfd5;
  --accent: #c8901b; --accent-ink: #1b1405; --royal: #24305e; --on-royal: #ffffff; --ok: #2c7a4b; --warn: #9a5b00; --bad: #b3261e;
  --t1: #e6ecf8; --t2: #f4ead9; --t3: #e4f1ee; --t4: #f6e3e1; --t5: #efe6f6; --t6: #e9eef0;
  --font-display: "Bricolage Grotesque", "Segoe UI", system-ui, sans-serif;
  --font-body: "Manrope", system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11141b; --panel: #181c26; --ink: #eef0f6; --muted: #a2a9b8; --line: #2a3040; --accent: #e8b44a;
  --accent-ink: #1b1405; --royal: #aab6ff; --on-royal: #10142a; --ok: #6fd39a; --warn: #f0b860; --bad: #ff8a80;
  --t1: #1f2a40; --t2: #33291b; --t3: #1b322d; --t4: #3a2522; --t5: #2d2338; --t6: #222b30; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #11141b; --panel: #181c26; --ink: #eef0f6; --muted: #a2a9b8; --line: #2a3040; --accent: #e8b44a;
  --accent-ink: #1b1405; --royal: #aab6ff; --on-royal: #10142a; --ok: #6fd39a; --warn: #f0b860; --bad: #ff8a80;
  --t1: #1f2a40; --t2: #33291b; --t3: #1b322d; --t4: #3a2522; --t5: #2d2338; --t6: #222b30; color-scheme: dark; }
body { background: var(--bg); color: var(--ink); font: 15px/1.55 var(--font-body);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 0 48px; }
.wrap { max-width: 1080px; margin: 0 auto; display: grid; gap: 22px; }
.notice { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; justify-content: space-between;
  padding: 10px 14px; border-radius: 12px; background: var(--panel); border: 1px dashed var(--accent); font-size: 14px; }
.notice b { color: var(--accent); }
.toggle { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-weight: 600; }
.toggle input { width: 18px; height: 18px; accent-color: var(--royal); }
header.shop { display: flex; flex-wrap: wrap; gap: 10px 20px; align-items: center; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 10px; font: 700 22px/1 var(--font-display); letter-spacing: -.01em; }
.brand svg { width: 30px; height: 30px; color: var(--accent); }
nav ul { list-style: none; display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 0; padding: 0; font-weight: 600; font-size: 14px; }
nav a { color: var(--muted); text-decoration: none; }
nav a:hover, nav a:focus-visible { color: var(--ink); }
.hero { background: var(--royal); color: var(--on-royal); border-radius: 22px; padding: clamp(22px, 5vw, 44px); display: grid; gap: 12px; }
.hero h1 { margin: 0; font: 700 clamp(30px, 7vw, 52px)/1.02 var(--font-display); letter-spacing: -.02em; text-wrap: balance; max-width: 16ch; }
.hero p { margin: 0; max-width: 46ch; font-size: 17px; opacity: .92; }
.cta { justify-self: start; background: var(--accent); color: var(--accent-ink); border-radius: 999px; padding: 11px 20px; font-weight: 800; text-decoration: none; }
.usps { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin: 0; padding: 0; list-style: none; }
.usps li { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px; font-weight: 600; font-size: 14px; display: flex; gap: 8px; align-items: center; }
.usps li::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--accent); flex: none; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { font: 600 14px var(--font-body); border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 999px; padding: 7px 13px; cursor: pointer; }
.chip[aria-pressed="true"] { background: var(--ink); color: var(--bg); border-color: var(--ink); }
h2 { font: 700 24px/1.15 var(--font-display); margin: 0; letter-spacing: -.01em; }
.grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr)); }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; overflow: hidden; display: grid; grid-template-rows: auto 1fr; min-width: 0; }
.pic { aspect-ratio: 4 / 3; max-width: 100%; display: grid; place-items: center; position: relative; }
.pic svg { width: 34%; height: auto; fill: none; stroke: var(--ink); stroke-width: 1.4; stroke-linecap: round; stroke-linejoin: round; opacity: .8; }
.badge { position: absolute; left: 10px; top: 10px; background: var(--accent); color: var(--accent-ink); font-weight: 800; font-size: 12px; padding: 4px 9px; border-radius: 999px; }
.body { padding: 12px 14px 14px; display: grid; gap: 6px; align-content: start; min-width: 0; }
.body h3 { margin: 0; font: 700 17px/1.25 var(--font-display); }
.short { margin: 0; color: var(--muted); font-size: 14px; }
.price { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; font-variant-numeric: tabular-nums; }
.price b { font: 800 20px var(--font-body); }
.price span { color: var(--muted); font-size: 13px; }
details.more summary { cursor: pointer; font-weight: 700; color: var(--royal); font-size: 14px; }
details.more div { font-size: 14px; color: var(--ink); }
details.more h3 { font: 700 14px var(--font-body); margin: 12px 0 4px; }
details.more ul { padding-left: 18px; margin: 6px 0; }
.notes { display: grid; gap: 4px; border-top: 1px dashed var(--line); padding-top: 8px; margin-top: 4px; font-size: 13px; }
.notes .row { display: flex; justify-content: space-between; gap: 10px; font-variant-numeric: tabular-nums; }
.notes .row b { font-weight: 700; }
.pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; font-weight: 700; background: var(--bg); border: 1px solid var(--line); }
.pill.ok { color: var(--ok); } .pill.warn { color: var(--warn); } .pill.bad { color: var(--bad); }
.hint { color: var(--muted); }
body:not(.show-notes) .notes { display: none; }
.info { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); }
.box { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 16px; min-width: 0; }
.box h2 { font-size: 20px; margin-bottom: 8px; }
.box details { border-top: 1px solid var(--line); padding: 8px 0; }
.box details summary { cursor: pointer; font-weight: 700; }
.box p { margin: 6px 0 0; }
footer { display: flex; flex-wrap: wrap; gap: 8px 18px; color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); padding-top: 14px; }
.todo { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; font-size: 14px; }
.todo li { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; }
.todo li::before { content: ""; width: 14px; height: 14px; margin-top: 3px; border-radius: 4px; border: 2px solid var(--muted); }
.todo li.done::before { background: var(--ok); border-color: var(--ok); }
a:focus-visible, button:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

CROWN = ('<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M3 8.5l4.2 3.3L12 5l4.8 6.8L21 8.5'
         'l-1.8 9.5H4.8z"/><rect x="4.8" y="19" width="14.4" height="2" rx="1"/></svg>')


def _pill(level: str) -> str:
    cls = {"ok": "ok", "warnung": "warn", "blockiert": "bad"}.get(level, "")
    label = {"ok": "keine Auffälligkeiten", "warnung": "Hinweise beachten", "blockiert": "gesperrt"}.get(level, level)
    return f'<span class="pill {cls}">{html.escape(label)}</span>'


def _card(p: dict) -> str:
    esc = html.escape
    offer = p["calc"]["offer"]
    tint = TINTS.get(p["collection"], "--t6")
    badge = f'<span class="badge">{esc(offer["label"])}</span>' if offer["n"] > 1 else ""
    per = f'<span>{eur(offer["per_item"])} pro Stück</span>' if offer["n"] > 1 else ""
    warnings = "".join(f'<div class="hint">· {esc(w)}</div>' for w in p["safety"]["warnings"][:2])
    notes = (
        '<div class="notes">'
        f'<div class="row"><span>Status</span><b>{esc(STATUS.get(p["status"], p["status"]))}</b></div>'
        f'<div class="row"><span>Gewinn pro Bestellung</span><b>{eur(p["calc"]["profit"])}</b></div>'
        f'<div class="row"><span>Marge</span><b>{p["calc"]["margin"]:.0f} %</b></div>'
        f'<div class="row"><span>Einkauf ({esc(p.get("price_status", "Schätzung"))})</span>'
        f'<b>{eur(p["unit_cost"])}</b></div>'
        f'<div class="row"><span>Preislage</span><b>{esc(p["calc"]["position"])}</b></div>'
        f'<div class="row"><span>Werbung darf kosten</span><b>bis {eur(p["calc"]["max_ads"])}</b></div>'
        f'<div class="row"><span>Produktprüfer</span>{_pill(p["safety"]["level"])}</div>{warnings}'
        '</div>')
    return (
        f'<article class="card" data-c="{esc(p["collection"])}">'
        f'<div class="pic" style="background: var({tint})">{badge}'
        f'<svg viewBox="0 0 24 24" role="img" aria-label="{esc(p["collection"])}">{ICONS.get(p["collection"], "")}</svg></div>'
        f'<div class="body"><h3>{esc(p["texts"]["title"])}</h3><p class="short">{esc(p["texts"]["short"])}</p>'
        f'<div class="price"><b>{eur(offer["price"])}</b>{per}<span>Lieferzeit {esc(p["delivery_days"])} Werktage</span></div>'
        f'<details class="more"><summary>Produktseite ansehen</summary><div>{p["texts"]["html"]}</div></details>'
        f'{notes}</div></article>')


def render_preview(site: dict, products: list[dict], todos: list[dict] | None = None, stamp: str = "") -> str:
    """Shop-Vorschau als eigenständige Seite (ohne <html>-Gerüst; wird für Dashboard und Artifact verwendet)."""
    esc = html.escape
    shown = [p for p in products if p["status"] in LIVE and p.get("texts")]
    waiting = sum(1 for p in shown if p["status"] == "wartet")
    chips = '<button class="chip" aria-pressed="true" data-f="">Alle</button>' + "".join(
        f'<button class="chip" aria-pressed="false" data-f="{esc(c["title"])}">{esc(c["title"])}</button>'
        for c in site["collections"])
    nav = "".join(f'<li><a href="#produkte">{esc(m["title"])}</a></li>' for m in site["menu"][:6])
    faq_html = "".join(f"<details><summary>{esc(q['q'])}</summary><p>{esc(q['a'])}</p></details>" for q in site["faq"])
    pages = {p["handle"]: p for p in site["pages"]}
    todo_html = ""
    if todos is not None:
        items = "".join(f'<li class="{"done" if t["done"] else ""}">{esc(t["text"])}</li>' for t in todos)
        todo_html = f'<section class="box notes-box"><h2>Das fehlt noch, bevor der Shop verkaufen darf</h2><ul class="todo">{items}</ul></section>'
    script = """
<script>
(() => {
  const chips = [...document.querySelectorAll('.chip')];
  chips.forEach((c) => c.addEventListener('click', () => {
    chips.forEach((x) => x.setAttribute('aria-pressed', String(x === c)));
    document.querySelectorAll('.card').forEach((card) => { card.hidden = !!c.dataset.f && card.dataset.c !== c.dataset.f; });
  }));
  const box = document.getElementById('showNotes');
  const apply = () => { document.body.classList.toggle('show-notes', box.checked);
    document.querySelectorAll('.notes-box').forEach((n) => { n.hidden = !box.checked; }); };
  box.addEventListener('change', apply); apply();
})();
</script>"""
    return f"""<title>{esc(site["shop_name"])} Vorschau</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=Manrope:wght@400;600;700;800&display=swap">
<style>{PREVIEW_CSS}</style>
<div class="wrap">
  <div class="notice"><span><b>Vorschau</b> · So baut Jarvis deinen Shop. Noch nicht online{" · " + esc(stamp) if stamp else ""}.
  {waiting} Produkte warten auf deine Freigabe.</span>
  <label class="toggle"><input type="checkbox" id="showNotes" checked> Jarvis-Notizen zeigen</label></div>
  <header class="shop"><div class="brand">{CROWN}<span>{esc(site["shop_name"])}</span></div>
  <nav aria-label="Hauptmenü"><ul>{nav}</ul></nav></header>
  <section class="hero"><h1>{esc(site["hero"]["title"])}</h1><p>{esc(site["hero"]["text"])}</p>
  <a class="cta" href="#produkte">{esc(site["hero"]["button"])}</a></section>
  <ul class="usps">{"".join(f"<li>{esc(u)}</li>" for u in site["usps"])}</ul>
  {todo_html}
  <section id="produkte" style="display:grid;gap:14px"><h2>Unsere Produkte</h2>
  <div class="chips" role="group" aria-label="Kategorie wählen">{chips}</div>
  <div class="grid">{"".join(_card(p) for p in shown)}</div></section>
  <section class="info">
    <div class="box"><h2>Häufige Fragen</h2>{faq_html}</div>
    <div class="box"><h2>{esc(pages["ueber-uns"]["title"])}</h2>{pages["ueber-uns"]["body_html"]}
    <h2 style="margin-top:14px">{esc(pages["versand"]["title"])}</h2>{pages["versand"]["body_html"]}</div>
  </section>
  <footer>{"".join(f"<span>{esc(f)}</span>" for f in site["footer"])}<span>© {esc(site["shop_name"])}</span></footer>
</div>{script}"""


def wrap_page(fragment: str) -> str:
    """Für den eigenen Webserver: Vorschau in ein vollständiges HTML-Dokument packen."""
    head, body = fragment.split('<div class="wrap">', 1)
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'{head}</head><body><div class="wrap">{body}</body></html>')


def site_json(site: dict) -> str:
    return json.dumps(site, ensure_ascii=False, indent=1)
