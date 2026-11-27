import csv
import json

import pytest

from content_crew.commands import handle_owner_message
from content_crew.config import load_config
from content_crew.db import DB
from content_crew.shop import ShopManager
from content_crew.shop.ideas import IDEAS
from content_crew.shop.pricing import Settings, breakdown, nice_price, plan_offer, required_gross
from content_crew.shop.safety import check, claims_in
from content_crew.shop.shopify import CSV_HEADERS, Shopify, ShopifyError
from content_crew.shop.team import KEYS, WORKERS
from content_crew.shop.workers import normalize_idea


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    for var in ("SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET", "SHOPIFY_ACCESS_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    c = load_config(tmp_path / "missing.yaml")
    c["data_dir"] = str(tmp_path / "data")
    c["shop"]["name"] = "Test Shop"
    return c


@pytest.fixture
def db(cfg):
    return DB(cfg.data_dir / "crew.db")


def test_twenty_workers_with_unique_keys():
    assert len(WORKERS) == 20 and len(set(KEYS)) == 20
    assert KEYS[:6] == ["jarvis", "scout", "writer", "producer", "publisher", "analyst"]


def test_breakdown_matches_the_five_euro_calculator():
    b = breakdown(5, 1, 0, 0.5, 3, 3, Settings())
    assert b["Umsatzsteuer"] == 0.83 and b["Gewinn"] == -6.97


def test_required_gross_hits_the_target_profit():
    s = Settings()
    g = required_gross(1, 4.5, 4.2, 0, s, 4.0)
    assert abs(breakdown(g, 1, 0, 4.5, 4.2, 0, s)["Gewinn"] - 4.0) < 0.01


def test_nice_price_rounds_up_to_usual_endings():
    assert nice_price(12.31) == 12.90 and nice_price(12.95) == 12.99 and nice_price(13.0) == 13.90


def test_offer_uses_a_set_when_one_piece_would_be_too_expensive():
    s = Settings()
    single = plan_offer({"unit_cost": 4.5, "weight_g": 250, "market": (12.9, 24.9)}, s)
    assert single["ok"] and single["offer"]["n"] == 1 and single["profit"] >= s.min_profit
    clips = plan_offer({"unit_cost": 2.0, "weight_g": 80, "market": (7.9, 12.9)}, s)
    assert clips["ok"] and clips["offer"]["n"] == 2 and clips["offer"]["per_item"] <= 12.9
    assert clips["profit"] >= s.min_profit
    bad = plan_offer({"unit_cost": 3.0, "weight_g": 100, "market": (5.9, 7.9)}, s)
    assert not bad["ok"] and "Rechnet sich nicht" in bad["reason"]


def test_china_direct_adds_duty():
    r = plan_offer({"unit_cost": 2.0, "weight_g": 200, "market": (14.9, 24.9), "origin": "china_direkt"}, Settings())
    assert r["breakdown"]["Zoll"] == 3.0 and any("Zoll" in n for n in r["notes"])


@pytest.mark.parametrize("name,blocked", [
    ("LED-Lichterkette mit USB", True), ("Kinderspielzeug Auto", True), ("Edelstahl-Trinkflasche", True),
    ("Nike Socken", True), ("Bildschirmreiniger Spray", True), ("Silberne Halskette", True),
    ("Katzenspielzeug mit Federn", False), ("Leder-Geldbörse", False), ("Kabel-Clips aus Silikon", False),
])
def test_safety_blocks_risky_products(name, blocked):
    assert (check({"name": name})["level"] == "blockiert") is blocked


def test_safety_warnings_and_claims():
    r = check({"name": "Massageball", "problem": "Rücken verspannt"})
    assert r["level"] == "warnung" and r["gpsr_missing"]
    assert claims_in("Hilft garantiert – nie wieder Fusseln!") == ["garantiert", "nie wieder"]


def test_starter_ideas_are_safe_and_profitable():
    s = Settings()
    names = [i["name"] for i in IDEAS]
    assert len(names) == len(set(names)) >= 20
    for idea in IDEAS:
        assert check(idea)["level"] != "blockiert", idea["name"]
        offer = plan_offer({**idea, "unit_cost": idea["ek"][1]}, s)
        assert offer["ok"], idea["name"]
        text = " ".join([idea["problem"], idea["solution"], idea["hook"], *idea["benefits"]])
        assert not claims_in(text), idea["name"]


def test_normalize_idea_rejects_nonsense():
    good = {k: IDEAS[0][k] for k in IDEAS[0] if k != "season"}
    assert normalize_idea(good)["name"] == IDEAS[0]["name"]
    assert normalize_idea({**good, "ek": [50, 2]}) is None
    assert normalize_idea({**good, "market": "teuer"}) is None
    assert normalize_idea({"name": "x"}) is None


def test_shop_round_without_shopify(cfg, db):
    m = ShopManager(cfg, db, shopify=False)
    report = m.run_cycle()
    assert len(report["neu"]) == 6 and not report["fehler"]
    p = db.product(report["neu"][0]["id"])
    assert p["status"] == "wartet" and p["calc"]["profit"] >= 4 and p["texts"]["html"].startswith("<p>")
    assert p["seo"]["handle"] and len(p["seo"]["seo_title"]) <= 60 and len(p["seo"]["seo_description"]) <= 155
    assert "Freigabe" in p["ads"]["bezahlt"]
    site = db.doc("website")
    assert site["collections"] and {pg["handle"] for pg in site["pages"]} == {"ueber-uns", "versand", "faq", "kontakt"}
    preview = (m.dir / "vorschau.html").read_text(encoding="utf-8")
    assert "Test Shop" in preview and p["texts"]["title"] in preview and "<!doctype html>" in preview
    assert db.activity("shopsync")["text"].startswith("wartet auf deinen Shopify-Zugang")
    # Warteschlange voll genug: in der zweiten Runde nur bis queue_size auffüllen
    second = m.run_cycle()
    assert len(second["neu"]) == 6
    assert m.run_cycle()["neu"] == []


def test_approvals_cost_update_and_csv_export(cfg, db):
    m = ShopManager(cfg, db, shopify=False)
    ids = [p["id"] for p in m.run_cycle()["neu"]]
    assert "freigegeben" in handle_owner_message(db, f"ok p{ids[0]}")
    assert "abgelehnt" in handle_owner_message(db, f"NEIN P{ids[1]}")
    assert "gibt es nicht" in handle_owner_message(db, "OK P999")
    assert "rechnet" in handle_owner_message(db, f"preis p{ids[2]} 1,20")
    assert db.take_inbox()[0]["text"] == f"SHOPCOST {ids[2]} 1.20"
    msg = m.set_cost(ids[2], 1.20)
    assert "1,20 €" in msg and db.product(ids[2])["price_status"] == "bestätigt"
    m.sync()
    rows = list(csv.DictReader((m.dir / "shopify-import.csv").open(encoding="utf-8")))
    assert list(rows[0].keys()) == CSV_HEADERS and len(rows) == 1
    assert rows[0]["Status"] == "draft" and rows[0]["Variant SKU"] == f"JS-{ids[0]:04d}"
    assert float(rows[0]["Variant Price"]) == db.product(ids[0])["calc"]["offer"]["price"]
    assert "1 Produkte warten" not in handle_owner_message(db, "SHOP")


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def chat_json(self, system, user, **kw):
        self.calls += 1
        risky = {**{k: IDEAS[0][k] for k in IDEAS[0] if k != "season"}, "name": "USB-Ventilator mit Akku"}
        new = {**{k: IDEAS[3][k] for k in IDEAS[3] if k != "season"}, "name": "Lenkradbezug aus Kunstleder"}
        return {"ideas": [risky, new, {"name": "kaputt"}]}


def test_llm_ideas_after_starter_list_and_risky_ones_are_sorted_out(cfg, db):
    for idea in IDEAS:  # Startsortiment ist schon verbraucht
        db.add_product(idea["name"], {"name": idea["name"]}, status="abgelehnt")
    llm = FakeLLM()
    report = ShopManager(cfg, db, llm=llm, shopify=False).run_cycle()
    assert llm.calls == 1
    assert [p["name"] for p in report["neu"]] == ["Lenkradbezug aus Kunstleder"]
    assert [p["status"] for p in report["aussortiert"]] == ["zu_riskant"]


class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data, self.text = status, data, json.dumps(data)

    def json(self):
        return self._data


class FakeSession:
    """Spielt die Shopify-Admin-API nach."""

    def __init__(self, reject_cost=False):
        self.posts = []
        self.reject_cost = reject_cost

    def post(self, url, data=None, json=None, headers=None, timeout=None):
        self.posts.append((url, data, json, headers))
        if url.endswith("/admin/oauth/access_token"):
            return FakeResponse(200, {"access_token": "tok-1", "scope": "write_products", "expires_in": 86399})
        q = json["query"]
        if "productSet" in q:
            variant = json["variables"]["input"]["variants"][0]
            if self.reject_cost and "inventoryItem" in variant:
                return FakeResponse(200, {"errors": [{"message": "Field 'inventoryItem' is not defined"}]})
            n = sum(1 for p in self.posts if "productSet" in (p[2] or {}).get("query", ""))
            return FakeResponse(200, {"data": {"productSet": {"product": {
                "id": f"gid://shopify/Product/{n}", "handle": json["variables"]["input"]["handle"],
                "status": json["variables"]["input"]["status"]}, "userErrors": []}}})
        if "publications" in q:
            return FakeResponse(200, {"data": {"publications": {"nodes": [{"id": "gid://p/1", "name": "Online Store"}]}}})
        if "publishablePublish" in q:
            return FakeResponse(200, {"data": {"publishablePublish": {"userErrors": []}}})
        if "pageCreate" in q:
            return FakeResponse(200, {"data": {"pageCreate": {"page": {"id": "gid://page/" + json["variables"]["page"]["handle"]}, "userErrors": []}}})
        if "pageUpdate" in q:
            return FakeResponse(200, {"data": {"pageUpdate": {"page": {"id": json["variables"]["id"]}, "userErrors": []}}})
        if "collectionCreate" in q:
            return FakeResponse(200, {"data": {"collectionCreate": {"collection": {"id": "gid://c/" + json["variables"]["input"]["handle"]}, "userErrors": []}}})
        if "orders(" in q:
            return FakeResponse(200, {"data": {"orders": {"nodes": [{
                "id": "gid://shopify/Order/1", "name": "#1001", "createdAt": "2026-11-26T10:00:00Z",
                "displayFinancialStatus": "PAID", "displayFulfillmentStatus": "UNFULFILLED",
                "totalPriceSet": {"shopMoney": {"amount": "22.80", "currencyCode": "EUR"}},
                "lineItems": {"nodes": [{"title": "Testprodukt", "quantity": 1, "sku": "JS-0001"}]}}]}}})
        return FakeResponse(200, {"data": {}})


def test_shopify_sync_with_client_credentials(cfg, db):
    session = FakeSession(reject_cost=True)
    shop = Shopify("test-laden", client_id="id", client_secret="geheim", session=session)
    assert shop.store == "test-laden.myshopify.com"
    m = ShopManager(cfg, db, shopify=shop)
    first = m.run_cycle()
    assert first["bestellungen"] == 1  # Bestellung #1001 ist neu
    ids = [p["id"] for p in first["neu"]]
    approve = m.approve(ids[0])
    assert "freigegeben" in approve
    report = m.run_cycle()
    token_calls = [p for p in session.posts if p[0].endswith("/admin/oauth/access_token")]
    assert len(token_calls) == 1 and token_calls[0][1]["grant_type"] == "client_credentials"
    graphql = [p for p in session.posts if p[0].endswith("/admin/api/2026-07/graphql.json")]
    assert all(p[3]["X-Shopify-Access-Token"] == "tok-1" for p in graphql)
    sets = [p[2]["variables"]["input"] for p in graphql if "productSet" in p[2]["query"]]
    assert sets[-1]["status"] == "DRAFT" and "inventoryItem" not in sets[-1]["variants"][0]  # ohne GPSR kein Live
    assert db.product(ids[0])["status"] == "online" and db.product(ids[0])["shopify_id"].startswith("gid://")
    assert ids[0] in report["online"]
    assert set(db.doc("shopify_ids")["pages"]) == {"ueber-uns", "versand", "faq", "kontakt"}
    assert report["bestellungen"] == 0 and db.orders()[0]["name"] == "#1001"
    books = db.doc("buchhaltung")
    assert books["bestellungen"] == 1 and books["umsatz_brutto"] == 22.8 and books["umsatzsteuer"] == 3.8


def test_shopify_errors_are_reported_not_raised(cfg, db):
    class Broken(FakeSession):
        def post(self, url, **kw):
            return FakeResponse(401, {"error": "invalid_client"})

    shop = Shopify("x", client_id="id", client_secret="falsch", session=Broken())
    with pytest.raises(ShopifyError):
        shop.token()
    m = ShopManager(cfg, db, shopify=shop)
    ids = [p["id"] for p in m.run_cycle()["neu"]]
    m.approve(ids[0])
    report = m.run_cycle()
    assert report["fehler"] and "Fehler" in db.activity("shopsync")["text"]


def test_dashboard_shop_section_preview_and_state(cfg, db):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from content_crew.webhooks import create_app

    ids = [p["id"] for p in ShopManager(cfg, db, shopify=False).run_cycle()["neu"]]
    client = TestClient(create_app(cfg, db))
    page = client.get("/").text
    assert "20 KI-Arbeiter" in page and "Produkt-Scout" in page and f"OK P{ids[0]}" in page
    assert "Gewerbe anmelden" in page
    client.post("/dashboard/cmd", data={"text": f"OK P{ids[0]}"})
    assert db.product(ids[0])["status"] == "freigegeben"
    preview = client.get("/shop")
    assert preview.status_code == 200 and "Jarvis-Notizen" in preview.text
    state = client.get("/dashboard/state.json").json()
    assert set(state["workers"]) == set(KEYS) and state["shop"]["wartet"] == len(ids) - 1
    team = client.get("/team").text
    assert "__SHOP__" not in team and "Shop-Verwalter" in team
    assert client.get("/shop", headers={"cf-connecting-ip": "1.2.3.4"}, follow_redirects=False).status_code == 303
