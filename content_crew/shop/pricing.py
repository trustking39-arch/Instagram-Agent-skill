"""Kalkulator: was pro Bestellung übrig bleibt – und welcher Preis sich rechnet.

Alle Beträge in Euro. Verkaufspreise sind Bruttopreise (inkl. Umsatzsteuer), so wie Kunden sie sehen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Versand-Schätzwerte je Herkunft der Ware. Echte Preise liefert später der Lieferant.
# steps: (bis Gramm, Preis fürs erste Stück); extra: je weiterem Stück im selben Paket;
# duty: Zoll pro Paket (seit 1. 7. 2026 pauschal 3 € je Warenart bei Sendungen aus Nicht-EU-Ländern bis 150 €).
ORIGINS: dict[str, dict] = {
    "eu_lager": {"label": "Lieferant mit EU-Lager", "steps": [(250, 4.2), (500, 4.9), (1000, 5.9), (2000, 7.9)],
                 "extra": 0.8, "duty": 0.0, "days": "3–6"},
    "china_direkt": {"label": "Direktversand aus China", "steps": [(250, 2.5), (500, 3.5), (1000, 5.5), (2000, 8.9)],
                     "extra": 0.6, "duty": 3.0, "days": "8–15"},
    "eigenlager": {"label": "Eigenes Lager, Versand mit der Post", "steps": [(1000, 5.2), (2000, 6.9)],
                   "extra": 0.3, "duty": 0.0, "days": "1–3", "packing": 0.5},
    "pod": {"label": "Druckpartner (Druck auf Bestellung)", "steps": [(500, 5.5), (2000, 7.5)], "extra": 1.5,
            "duty": 0.0, "days": "4–8"},
    "digital": {"label": "Sofort-Download", "steps": [(10 ** 9, 0.0)], "extra": 0.0, "duty": 0.0, "days": "sofort",
                "digital": True},
}


@dataclass
class Settings:
    vat: float = 20.0           # Umsatzsteuer in % (Österreich)
    pay_pct: float = 2.5        # Zahlungsgebühr in %
    pay_fix: float = 0.30       # Zahlungsgebühr fix pro Bestellung
    ads: float = 4.0            # Werbekosten pro Bestellung
    refund_pct: float = 5.0     # Rückerstattungen in % vom Nettoumsatz
    min_profit: float = 4.0     # Mindestgewinn pro Bestellung nach allen Kosten
    shipping_fee: float = 3.90  # Versandkosten, die der Kunde zahlt
    free_from: float = 30.0     # Gratisversand ab diesem Bestellwert (0 = nie)
    origin: str = "eu_lager"

    @classmethod
    def from_cfg(cls, shop_cfg: dict | None) -> Settings:
        shop_cfg = shop_cfg or {}
        values = {}
        for name in cls.__dataclass_fields__:
            if name in shop_cfg and shop_cfg[name] is not None:
                values[name] = shop_cfg[name] if name == "origin" else float(shop_cfg[name])
        s = cls(**values)
        if s.origin not in ORIGINS:
            s.origin = "eu_lager"
        return s


def shipping_cost(weight_g: float, n: int, origin: str) -> float:
    """Versand für ein Paket mit n Stück (Schätzung)."""
    spec = ORIGINS[origin]
    first = spec["steps"][-1][1]
    for limit, price in spec["steps"]:
        if weight_g <= limit:
            first = price
            break
    return round(first + max(0, n - 1) * spec["extra"] + spec.get("packing", 0.0), 2)


def breakdown(price: float, n: int, fee: float, unit_cost: float, shipping: float, duty: float,
              s: Settings) -> dict:
    """Wohin die Euros einer Bestellung gehen: n Angebote (Stück oder Sets) zu je price, plus Versandgebühr fee.
    unit_cost ist der Einkauf pro Angebot (bei einem 3er-Set also 3 Stück)."""
    gross = n * price + fee
    tax = gross * s.vat / (100 + s.vat)
    net = gross - tax
    goods = n * unit_cost
    payment = gross * s.pay_pct / 100 + s.pay_fix
    refunds = net * s.refund_pct / 100
    profit = net - goods - shipping - duty - payment - s.ads - refunds
    out = {"Kunde zahlt": gross, "Umsatzsteuer": tax, "Einkauf": goods, "Versand": shipping, "Zoll": duty,
           "Zahlungsgebühr": payment, "Werbung": s.ads, "Rückerstattungen": refunds, "Gewinn": profit}
    return {k: round(v, 2) for k, v in out.items()} | {"netto": round(net, 2)}


def required_gross(n: int, unit_cost: float, shipping: float, duty: float, s: Settings, target: float) -> float:
    """Bruttoumsatz einer Bestellung, ab dem `target` Gewinn übrig bleibt."""
    keep = (1 - s.refund_pct / 100) / (1 + s.vat / 100) - s.pay_pct / 100
    return (target + n * unit_cost + shipping + duty + s.pay_fix + s.ads) / keep


def nice_price(x: float) -> float:
    """Auf den nächsten üblichen Preis aufrunden: …,90 oder …,99."""
    x = round(x, 2)
    base = math.floor(x)
    for cand in (base + 0.90, base + 0.99, base + 1.90):
        if cand + 1e-9 >= x:
            return round(cand, 2)
    return round(base + 1.90, 2)  # pragma: no cover


def eur(x: float) -> str:
    """1234.5 -> '1.234,50 €'"""
    text = f"{abs(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 else "") + text + " €"


def position(per_item: float, market: tuple[float, float]) -> str:
    lo, hi = market
    if per_item < lo - 1e-9:
        return "günstiger als üblich"
    if per_item <= (lo + hi) / 2 + 1e-9:
        return "im üblichen Bereich"
    if per_item <= hi + 1e-9:
        return "am oberen Rand"
    return "teurer als üblich"


def plan_offer(product: dict, s: Settings) -> dict:
    """Preis festlegen: erst einzeln, sonst als 2er- oder 3er-Set. Abgelehnt wird, was sich nicht rechnet."""
    origin = product.get("origin") or s.origin
    spec = ORIGINS[origin]
    unit = float(product["unit_cost"])
    weight = float(product.get("weight_g") or 300)
    market = tuple(product["market"])
    lo, hi = float(market[0]), float(market[1])
    duty = spec["duty"]
    tried = []
    sizes = (1,) if spec.get("digital") else (1, 2, 3)
    for n in sizes:  # n Stück pro Angebot (1 = einzeln, sonst Set)
        set_cost = n * unit
        ship = shipping_cost(weight, n, origin)
        floor = lo * n * (0.9 if n > 1 else 1.0)  # nicht billiger als der Markt (Sets mit 10 % Nachlass)
        g = required_gross(1, set_cost, ship, duty, s, s.min_profit)
        fee = 0.0 if spec.get("digital") else s.shipping_fee
        price = nice_price(max(g - fee, floor))
        if s.free_from and price >= s.free_from:
            fee = 0.0
            price = nice_price(max(g, floor))
        per_item = round(price / n, 2)
        b = breakdown(price, 1, fee, set_cost, ship, duty, s)
        tried.append({"n": n, "price": price, "per_item": per_item})
        if per_item <= hi + 1e-9:
            break
    else:
        cheapest = min(tried, key=lambda t: t["per_item"])
        return {
            "ok": False, "origin": origin, "origin_label": spec["label"], "tried": tried,
            "reason": (f"Rechnet sich nicht: Für {eur(s.min_profit)} Gewinn müsste ein Stück mindestens "
                       f"{eur(cheapest['per_item'])} kosten, üblich sind höchstens {eur(hi)}."),
        }
    label = "Einzeln" if n == 1 else f"{n}er-Set"
    notes = []
    if duty:
        notes.append(f"Zoll: {eur(duty)} pro Paket (Direktversand aus einem Nicht-EU-Land).")
    if s.free_from and price < s.free_from and not spec.get("digital"):
        k = math.ceil(s.free_from / price)
        big = breakdown(price, k, 0.0, set_cost, shipping_cost(weight, k * n, origin), duty, s)
        big_profit = big["Gewinn"]
        if big_profit < s.min_profit:
            notes.append(f"Achtung: Bei {k * n} Stück mit Gratisversand bleiben nur {eur(big_profit)}.")
    net = b["netto"]
    return {
        "ok": True,
        "origin": origin, "origin_label": spec["label"], "delivery_days": spec["days"],
        "offer": {"n": n, "label": label, "price": price, "per_item": per_item, "fee": fee},
        "profit": b["Gewinn"],
        "margin": round(b["Gewinn"] / net * 100, 1) if net else 0.0,
        "max_ads": round(b["Gewinn"] + s.ads, 2),  # so viel darf Werbung pro Bestellung kosten (Null-Gewinn)
        "breakdown": b,
        "position": position(per_item, (lo, hi)),
        "tried": tried,
        "notes": notes,
    }
