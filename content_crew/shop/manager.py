"""Jarvis' Shop-Abteilung: eine Shop-Runde mit allen Arbeitern, Freigaben, Bestellungen und Buchhaltung.

Grundregeln: Kein Produkt geht ohne Freigabe des Besitzers online, Jarvis gibt kein Geld aus, und ein
Produkt wird in Shopify erst aktiv geschaltet, wenn die Angaben zur Produktsicherheit (GPSR) vollständig sind.
"""

from __future__ import annotations

import csv
import logging
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from content_crew.shop.pricing import ORIGINS, Settings, eur, plan_offer, shipping_cost
from content_crew.shop.safety import check
from content_crew.shop.shopify import Shopify, ShopifyError, export_csv, sku
from content_crew.shop.website import build_site, legal_todos, render_preview, wrap_page
from content_crew.shop.workers import (Buyer, Copywriter, ProductScout, ad_plan, email_drafts, season_now, seo)

log = logging.getLogger(__name__)

ACTIVE = ("wartet", "freigegeben", "online")
GPSR_NEEDED = ("hersteller", "eu_person", "kennung", "hinweise")


class ShopManager:
    def __init__(self, cfg, db, llm=None, notifier=None, shopify: Shopify | None | bool = None):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        self.notifier = notifier
        self.scfg = cfg.get("shop", {}) or {}
        self.s = Settings.from_cfg(self.scfg)
        self.shopify = Shopify.from_cfg(cfg) if shopify is None else (shopify or None)
        self.scout = ProductScout(llm, use_llm=bool(self.scfg.get("ki_ideen", True)))
        self.buyer = Buyer(self.s)
        self.copywriter = Copywriter(llm, use_llm=bool(self.scfg.get("ki_texte", False)))
        self.dir = Path(cfg.data_dir) / "shop"
        self.dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return str(self.scfg.get("name") or "Mein Shop")

    @property
    def email(self) -> str:
        return str((self.scfg.get("owner") or {}).get("email", ""))

    def act(self, worker: str, text: str) -> None:
        self.db.set_activity(worker, text)

    def _notify(self, kind: str, text: str) -> None:
        if self.notifier is not None:
            self.notifier.notify(kind, text)

    # --- ein Produkt durch die Abteilung schicken ------------------------------------------
    def evaluate(self, idea: dict, settings: Settings | None = None) -> dict:
        name = idea["name"]
        s = settings or self.s
        self.act("buyer", f"prüft Einkauf und Versand: {name}")
        p = self.buyer.prepare(idea)
        spec = ORIGINS[p["origin"]]
        self.act("buyer", f"{name}: {spec['label']}, {eur(p['unit_cost'])} Einkauf ({p['price_status']}), "
                          f"Lieferzeit {spec['days']} Tage")
        self.act("safety", f"prüft {name} auf CE, Spielzeug, Kosmetik, Marken")
        p["safety"] = check(p)
        if p["safety"]["level"] == "blockiert":
            self.act("safety", f"sortiert aus: {name} – {p['safety']['blocked'][0]}")
            p["reason"] = p["safety"]["blocked"][0]
            p["id"] = self.db.add_product(name, p, status="zu_riskant")
            return {**p, "status": "zu_riskant"}
        self.act("safety", f"{name}: " + ("keine Auffälligkeiten" if p["safety"]["level"] == "ok"
                                          else f"{len(p['safety']['warnings'])} Hinweis(e) für den Text"))
        self.act("calculator", f"rechnet Preis und Gewinn für {name}")
        p["calc"] = plan_offer(p, s)
        if not p["calc"]["ok"]:
            self.act("calculator", f"{name} rechnet sich nicht")
            p["reason"] = p["calc"]["reason"]
            p["id"] = self.db.add_product(name, p, status="rechnet_sich_nicht")
            return {**p, "status": "rechnet_sich_nicht"}
        offer = p["calc"]["offer"]
        self.act("calculator", f"{name}: {offer['label']} für {eur(offer['price'])}, "
                               f"{eur(p['calc']['profit'])} Gewinn pro Bestellung")
        self.act("copywriter", f"schreibt die Produktseite: {name}")
        p["texts"] = self.copywriter.write(p, p["calc"], s)
        self.act("seo", f"optimiert „{p['texts']['title']}“ für Google")
        p["seo"] = seo(p, p["texts"], self.name)
        self.act("ads", f"plant Videos und Anzeigen-Test für {name}")
        p["ads"] = ad_plan(p, p["calc"])
        p["id"] = self.db.add_product(name, p, status="wartet")
        return {**p, "status": "wartet"}

    def add_art(self) -> list[dict]:
        """Eigene Kunst als Produkte: Poster (Druck auf Bestellung) und ein Wallpaper-Paket (Download).

        Die Motive rechnet die Animations-Engine – Einkauf entfällt. Verkauft wird vor allem über die
        eigenen TikTok-Videos, daher weniger Werbekosten pro Bestellung als bei den Alltagshelfern.
        """
        from content_crew.shop import kunst

        known = self.known_names()
        added = []
        for idea in kunst.products(self.dir / "kunst"):
            if idea["name"] in known:
                continue
            digital = idea["kind"] == "digital"
            self.act("webdesigner", f"gestaltet „{idea['name']}“")
            size = (270, 585) if digital else (360, 509)
            idea["image"] = kunst.thumbnail_data(idea["world"], idea["hour"], size)
            settings = replace(self.s, ads=1.0, min_profit=3.0) if digital else replace(self.s, ads=2.0)
            added.append(self.evaluate(idea, settings))
        if added:
            self.build_site()
            self.write_preview()
        return added

    def known_names(self) -> set[str]:
        return {p["name"] for p in self.db.products(limit=2000)}

    # --- Freigaben ----------------------------------------------------------------------------
    def approve(self, product_id: int) -> str:
        return approve_product(self.db, product_id)

    def reject(self, product_id: int) -> str:
        return reject_product(self.db, product_id)

    def set_cost(self, product_id: int, cost: float) -> str:
        """Echten Einkaufspreis vom Lieferanten eintragen – der Kalkulator rechnet neu."""
        p = self.db.product(product_id)
        if not p:
            return f"Produkt P{product_id} gibt es nicht."
        idea = {k: v for k, v in p.items() if k not in ("id", "status", "created_at", "updated_at")}
        idea["cost_confirmed"] = round(float(cost), 2)
        prepared = self.buyer.prepare(idea)
        calc = plan_offer(prepared, self.s)
        prepared["calc"] = calc
        if not calc["ok"]:
            prepared["reason"] = calc["reason"]
            self.db.update_product(product_id, status="rechnet_sich_nicht", data=_clean(prepared))
            return f"P{product_id}: Mit {eur(cost)} Einkauf rechnet es sich nicht. {calc['reason']}"
        prepared["texts"] = self.copywriter.write(prepared, calc, self.s)
        prepared["seo"] = seo(prepared, prepared["texts"], self.name)
        prepared["ads"] = ad_plan(prepared, calc)
        status = p["status"] if p["status"] in ACTIVE else "wartet"
        self.db.update_product(product_id, status=status, data=_clean(prepared))
        offer = calc["offer"]
        return (f"P{product_id}: Einkauf {eur(cost)} eingetragen. Neuer Preis {offer['label']} "
                f"{eur(offer['price'])}, Gewinn {eur(calc['profit'])} pro Bestellung.")

    # --- die Runde ------------------------------------------------------------------------------
    def run_cycle(self) -> dict:
        report: dict = {"neu": [], "aussortiert": [], "online": [], "bestellungen": 0, "fehler": []}
        self.act("jarvis", "plant die Shop-Runde")
        waiting = self.db.products(["wartet", "freigegeben"])
        want = max(0, min(int(self.scfg.get("ideas_per_cycle", 6)), int(self.scfg.get("queue_size", 12)) - len(waiting)))
        if want:
            self.act("productscout", f"sucht {want} neue Produkte (Saison: {season_now() or 'ganzjährig'})")
            ideas = self.scout.ideas(want, self.known_names(), season_now())
            self.act("productscout", f"{len(ideas)} Produktideen an den Einkäufer übergeben" if ideas else
                     "keine neuen Ideen – Startsortiment ist durch, Jarvis ist gerade nicht erreichbar")
            for idea in ideas:
                try:
                    p = self.evaluate(idea)
                except Exception as exc:  # noqa: BLE001 – ein kaputtes Produkt hält die Runde nicht auf
                    log.exception("Produkt %s fehlgeschlagen", idea.get("name"))
                    report["fehler"].append(f"{idea.get('name')}: {exc}")
                    continue
                (report["neu"] if p["status"] == "wartet" else report["aussortiert"]).append(p)
        else:
            self.act("productscout", f"pausiert – {len(waiting)} Produkte liegen schon bei dir zur Freigabe")
        self.build_site()
        report["online"] = self.sync(report)
        report["bestellungen"] = self.check_orders(report)
        self.accounting()
        preview = self.write_preview()
        summary = self.summary(report)
        self.db.set_doc("letzte_runde", {"ts": time.time(), "text": summary, "vorschau": str(preview)})
        self.act("jarvis", summary)
        if report["neu"]:
            ids = ", ".join(f"P{p['id']}" for p in report["neu"][:6])
            self._notify("approval", f"Jarvis: {len(report['neu'])} neue Produkte für deinen Shop warten auf deine "
                                     f"Freigabe ({ids}). Antworte z. B. OK {ids.split(',')[0]} oder NEIN … – "
                                     "Details in der Übersicht unter Shop.")
        return report

    def summary(self, report: dict) -> str:
        counts = self.counts()
        parts = [f"Shop-Runde fertig: {len(report['neu'])} neue Produkte zur Freigabe"]
        if report["aussortiert"]:
            parts.append(f"{len(report['aussortiert'])} aussortiert")
        parts.append(f"insgesamt {counts.get('wartet', 0)} warten, {counts.get('freigegeben', 0)} freigegeben, "
                     f"{counts.get('online', 0)} in Shopify")
        if report["bestellungen"]:
            parts.append(f"{report['bestellungen']} neue Bestellungen")
        return ", ".join(parts) + "."

    def counts(self) -> dict:
        rows = self.db.conn.execute("SELECT status, COUNT(*) n FROM products GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}

    # --- Website, Texte, Recht ------------------------------------------------------------------
    def build_site(self) -> dict:
        products = self.db.products(list(ACTIVE))
        self.act("webdesigner", "baut Startseite, Kategorien, Menü und Infoseiten")
        site = build_site(self.name, self.s, products, self.email)
        self.db.set_doc("website", site)
        self.act("webdesigner", f"Shop-Aufbau fertig: {len(site['collections'])} Kategorien, "
                                f"{len(site['pages'])} Infoseiten")
        self.act("support", f"FAQ aktualisiert: {len(site['faq'])} Antworten für Kunden")
        self.act("email", "schreibt Willkommensmail, Neuheiten-Newsletter und Warenkorb-Erinnerung")
        self.db.set_doc("emails", email_drafts(self.name, products, self.s))
        self.act("email", "3 E-Mail-Entwürfe liegen bereit")
        todos = self.todos()
        open_todos = [t for t in todos if not t["done"]]
        self.act("legal", f"{len(open_todos)} Punkte offen, bevor der Shop verkaufen darf" if open_todos
                 else "alle Pflichtangaben vollständig")
        return site

    def todos(self) -> list[dict]:
        approved = self.db.products(["freigegeben", "online"])
        missing = sum(1 for p in approved if not gpsr_complete(p))
        return legal_todos(self.scfg, self.shopify is not None, missing, len(approved))

    def write_preview(self) -> Path:
        site = self.db.doc("website") or self.build_site()
        products = self.db.products(list(ACTIVE))
        stamp = datetime.now().strftime("Stand %d.%m.%Y %H:%M")
        fragment = render_preview(site, list(reversed(products)), self.todos(), stamp, self.s)
        (self.dir / "vorschau-fragment.html").write_text(fragment, encoding="utf-8")
        path = self.dir / "vorschau.html"
        path.write_text(wrap_page(fragment), encoding="utf-8")
        return path

    # --- Shopify -----------------------------------------------------------------------------------
    def sync(self, report: dict | None = None) -> list[int]:
        approved = self.db.products(["freigegeben", "online"])
        if self.shopify is None:
            path = export_csv(list(reversed(approved)), self.dir / "shopify-import.csv", self.name)
            self.act("shopsync", f"wartet auf deinen Shopify-Zugang – Import-Datei mit {len(approved)} "
                                 f"freigegebenen Produkten liegt bereit ({path.name})")
            return []
        done: list[int] = []
        try:
            self.act("shopsync", f"verbindet sich mit {self.shopify.store}")
            self.sync_site()
            for p in approved:
                active = gpsr_complete(p) and bool(self.scfg.get("auto_online", False))
                self.act("shopsync", f"überträgt „{p['texts']['title']}“ ({'aktiv' if active else 'Entwurf'})")
                result = self.shopify.upsert_product(p, self.name, active)
                data = _clean(p) | {"shopify_id": result.get("id", p.get("shopify_id", ""))}
                self.db.update_product(p["id"], status="online", data=data)
                done.append(p["id"])
            self.act("shopsync", f"{len(done)} Produkte in Shopify aktuell")
        except (ShopifyError, OSError) as exc:
            log.warning("Shopify-Abgleich fehlgeschlagen: %s", exc)
            self.act("shopsync", f"Fehler beim Abgleich: {exc}"[:200])
            if report is not None:
                report["fehler"].append(str(exc))
            self._notify("error", f"Shop-Verwalter: Shopify-Abgleich fehlgeschlagen – {exc}"[:300])
        return done

    def sync_site(self) -> None:
        site = self.db.doc("website") or self.build_site()
        ids = self.db.doc("shopify_ids", {"pages": {}, "collections": {}})
        for page in site["pages"]:
            ids["pages"][page["handle"]] = self.shopify.upsert_page(page, ids["pages"].get(page["handle"], ""))
        for c in site["collections"]:
            if c["handle"] not in ids["collections"]:
                ids["collections"][c["handle"]] = self.shopify.create_collection(c)
        self.db.set_doc("shopify_ids", ids)
        self.act("webdesigner", f"Seiten und Kategorien in Shopify angelegt ({len(ids['pages'])} Seiten, "
                                f"{len(ids['collections'])} Kategorien)")

    # --- Bestellungen und Buchhaltung -----------------------------------------------------------------
    def check_orders(self, report: dict | None = None) -> int:
        if self.shopify is None:
            self.act("orders", "wartet – sobald der Shop verbunden ist, behalte ich jede Bestellung im Blick")
            self.act("support", "wartet auf die ersten Kundenfragen")
            return 0
        try:
            self.act("orders", "holt neue Bestellungen aus Shopify")
            orders = self.shopify.orders(days=30)
        except (ShopifyError, OSError) as exc:
            self.act("orders", f"Bestellungen nicht abrufbar: {exc}"[:200])
            return 0
        new = 0
        late = []
        max_days = int(ORIGINS[self.s.origin]["days"].split("–")[-1]) + 3
        for o in orders:
            created = _ts(o["created"])
            if self.db.upsert_order(o["id"], created, o):
                new += 1
                self._notify("report", f"Neue Bestellung {o['name']}: {sum(i['quantity'] for i in o['items'])} "
                                       f"Artikel, {eur(o['total'])}.")
            if o["fulfillment"].upper() not in ("FULFILLED",) and time.time() - created > max_days * 86400:
                late.append(o["name"])
        if late:
            self._notify("report", f"Bestell-Manager: Diese Bestellungen sind seit über {max_days} Tagen nicht "
                                   f"versendet: {', '.join(late[:8])}. Bitte beim Lieferanten nachfragen.")
        self.act("orders", f"{len(orders)} Bestellungen in 30 Tagen, {new} neu, {len(late)} verspätet")
        return new

    def accounting(self) -> dict:
        since = time.time() - 30 * 86400
        orders = self.db.orders(since=since)
        if not orders:
            result = {"bestellungen": 0, "text": "noch kein Umsatz"}
            self.db.set_doc("buchhaltung", result)
            self.act("accountant", "noch kein Umsatz – die Buchhaltung startet mit der ersten Bestellung")
            return result
        by_sku = {sku(p): p for p in self.db.products(limit=2000) if p.get("calc", {}).get("ok")}
        gross = goods = shipping = fees = 0.0
        for o in orders:
            gross += o["total"]
            for item in o["items"]:
                p = by_sku.get(item["sku"])
                if p:
                    goods += p["unit_cost"] * p["calc"]["offer"]["n"] * item["quantity"]
            p0 = next((by_sku.get(i["sku"]) for i in o["items"] if by_sku.get(i["sku"])), None)
            n_items = sum(i["quantity"] for i in o["items"])
            shipping += shipping_cost(p0.get("weight_g", 300) if p0 else 300, max(1, n_items), self.s.origin)
            fees += o["total"] * self.s.pay_pct / 100 + self.s.pay_fix
        tax = gross * self.s.vat / (100 + self.s.vat)
        net = gross - tax
        result = {"bestellungen": len(orders), "umsatz_brutto": round(gross, 2), "umsatzsteuer": round(tax, 2),
                  "umsatz_netto": round(net, 2), "wareneinsatz": round(goods, 2), "versand": round(shipping, 2),
                  "gebuehren": round(fees, 2), "ergebnis_vor_werbung": round(net - goods - shipping - fees, 2),
                  "zeitraum": "letzte 30 Tage", "hinweis": "Wareneinsatz und Versand sind Schätzwerte aus der "
                  "Kalkulation; Werbekosten sind nicht abgezogen."}
        self.db.set_doc("buchhaltung", result)
        month = datetime.now().strftime("%Y-%m")
        path = self.dir / f"buchhaltung-{month}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(["Bestellung", "Datum", "Bezahlt", "Versand", "Betrag brutto", "Artikel"])
            for o in orders:
                writer.writerow([o["name"], o["created"][:10], o["paid"], o["fulfillment"],
                                 f"{o['total']:.2f}".replace(".", ","),
                                 " | ".join(f"{i['quantity']}× {i['title']}" for i in o["items"])])
        self.act("accountant", f"30 Tage: {eur(gross)} Umsatz, davon {eur(tax)} USt, Ergebnis vor Werbung "
                               f"ca. {eur(result['ergebnis_vor_werbung'])}")
        return result

    def status_text(self) -> str:
        return shop_status_text(self.db, self.shopify is not None)


# --- Hilfen, die auch ohne Manager funktionieren (SMS-Befehle, Übersicht) ----------------------------
def approve_product(db, product_id: int) -> str:
    p = db.product(product_id)
    if not p:
        return f"Produkt P{product_id} gibt es nicht."
    if p["status"] in ("freigegeben", "online"):
        return f"P{product_id} „{p['name']}“ ist schon freigegeben."
    if p["status"] != "wartet":
        return f"P{product_id} „{p['name']}“ kann nicht freigegeben werden ({p['status'].replace('_', ' ')})."
    db.update_product(product_id, status="freigegeben")
    return (f"P{product_id} „{p['name']}“ freigegeben. Der Shop-Verwalter stellt es in der nächsten Runde in "
            "deinen Shop (als Entwurf, bis die Produktsicherheits-Angaben da sind).")


def reject_product(db, product_id: int) -> str:
    p = db.product(product_id)
    if not p:
        return f"Produkt P{product_id} gibt es nicht."
    db.update_product(product_id, status="abgelehnt")
    return f"P{product_id} „{p['name']}“ abgelehnt. Der Produkt-Scout sucht Ersatz."


def shop_status_text(db, connected: bool | None = None) -> str:
    rows = db.conn.execute("SELECT status, COUNT(*) n FROM products GROUP BY status").fetchall()
    c = {r["status"]: r["n"] for r in rows}
    out = (f"Shop: {c.get('wartet', 0)} Produkte warten auf Freigabe, {c.get('freigegeben', 0)} freigegeben, "
           f"{c.get('online', 0)} in Shopify, "
           f"{c.get('zu_riskant', 0) + c.get('rechnet_sich_nicht', 0) + c.get('abgelehnt', 0)} aussortiert.")
    if connected is not None:
        out += " Shopify: " + ("verbunden." if connected else "noch nicht verbunden.")
    return out


def gpsr_complete(p: dict) -> bool:
    gpsr = p.get("gpsr") or {}
    return all(str(gpsr.get(k, "")).strip() for k in GPSR_NEEDED)


def _clean(p: dict) -> dict:
    return {k: v for k, v in p.items() if k not in ("id", "status", "created_at", "updated_at")}


def _ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return time.time()


__all__ = ["ShopManager", "approve_product", "reject_product", "shop_status_text"]
