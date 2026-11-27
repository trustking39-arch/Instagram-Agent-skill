"""Shop-Verwalter: Verbindung zu Shopify (Admin-API) und Import-Datei (CSV), solange kein Zugang da ist.

Zugang (in .env, über `content-crew setup`):
- SHOPIFY_STORE=mein-shop.myshopify.com
- entweder SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET einer App aus dem Shopify Dev Dashboard
  (Jarvis holt sich damit selbst ein Zugangs-Token, das nach etwa 24 Stunden erneuert wird)
- oder SHOPIFY_ACCESS_TOKEN einer älteren, im Shop-Admin angelegten App.
Nötige Berechtigungen: write_products, write_content (Seiten), write_publications, read_orders.
"""

from __future__ import annotations

import csv
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

API_VERSION = "2026-07"

PRODUCT_SET = """
mutation ProductSet($input: ProductSetInput!, $synchronous: Boolean!) {
  productSet(synchronous: $synchronous, input: $input) {
    product { id handle status }
    userErrors { field message }
  }
}"""

PUBLICATIONS = "{ publications(first: 20) { nodes { id name } } }"

PUBLISH = """
mutation Publish($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) { userErrors { field message } }
}"""

PAGE_CREATE = """
mutation PageCreate($page: PageCreateInput!) {
  pageCreate(page: $page) { page { id handle } userErrors { field message } }
}"""

PAGE_UPDATE = """
mutation PageUpdate($id: ID!, $page: PageUpdateInput!) {
  pageUpdate(id: $id, page: $page) { page { id handle } userErrors { field message } }
}"""

COLLECTION_CREATE = """
mutation CollectionCreate($input: CollectionInput!) {
  collectionCreate(input: $input) { collection { id handle } userErrors { field message } }
}"""

ORDERS = """
query Orders($query: String) {
  orders(first: 100, sortKey: CREATED_AT, reverse: true, query: $query) {
    nodes {
      id name createdAt displayFinancialStatus displayFulfillmentStatus
      totalPriceSet { shopMoney { amount currencyCode } }
      lineItems(first: 30) { nodes { title quantity sku } }
    }
  }
}"""


class ShopifyError(RuntimeError):
    pass


def normalize_store(store: str) -> str:
    store = store.strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
    return store if "." in store else f"{store}.myshopify.com"


class Shopify:
    def __init__(self, store: str, token: str = "", client_id: str = "", client_secret: str = "",
                 api_version: str = API_VERSION, session: requests.Session | None = None, timeout: int = 30):
        self.store = normalize_store(store)
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_version = api_version or API_VERSION
        self.session = session or requests.Session()
        self.timeout = timeout
        self._token = token
        self._static = bool(token)
        self._expires = float("inf") if token else 0.0
        self._online_store: str | None = None

    @classmethod
    def from_cfg(cls, cfg) -> Shopify | None:
        scfg = cfg.get("shop", {}) or {}
        store = cfg.env("SHOPIFY_STORE") or str(scfg.get("shopify_store", ""))
        token = cfg.env("SHOPIFY_ACCESS_TOKEN")
        client_id, secret = cfg.env("SHOPIFY_CLIENT_ID"), cfg.env("SHOPIFY_CLIENT_SECRET")
        if not store or not (token or (client_id and secret)):
            return None
        return cls(store, token, client_id, secret, str(scfg.get("shopify_api_version", API_VERSION)))

    # --- Zugang ------------------------------------------------------------------
    def token(self) -> str:
        if self._token and time.time() < self._expires - 300:
            return self._token
        if not (self.client_id and self.client_secret):
            raise ShopifyError("Kein Shopify-Zugang: SHOPIFY_CLIENT_ID und SHOPIFY_CLIENT_SECRET fehlen.")
        r = self.session.post(f"https://{self.store}/admin/oauth/access_token", data={
            "grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret,
        }, timeout=self.timeout)
        if r.status_code != 200:
            raise ShopifyError(f"Shopify-Anmeldung fehlgeschlagen ({r.status_code}). Ist die App im Shop "
                               f"installiert und gehört sie zur selben Organisation? {r.text[:200]}")
        data = r.json()
        self._token = data["access_token"]
        self._expires = time.time() + float(data.get("expires_in") or 86399)
        return self._token

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        url = f"https://{self.store}/admin/api/{self.api_version}/graphql.json"
        for attempt in range(2):
            r = self.session.post(url, json={"query": query, "variables": variables or {}}, timeout=self.timeout,
                                  headers={"X-Shopify-Access-Token": self.token(), "Content-Type": "application/json"})
            if r.status_code == 401 and not self._static and attempt == 0:
                self._expires = 0.0  # Token abgelaufen: neu holen und noch einmal
                continue
            break
        if r.status_code >= 400:
            raise ShopifyError(f"Shopify antwortet mit {r.status_code}: {r.text[:300]}")
        body = r.json()
        if body.get("errors"):
            raise ShopifyError("; ".join(str(e.get("message", e)) for e in body["errors"])[:500])
        return body.get("data") or {}

    @staticmethod
    def _check(payload: dict | None, what: str) -> dict:
        payload = payload or {}
        errors = payload.get("userErrors") or []
        if errors:
            raise ShopifyError(f"{what}: " + "; ".join(e.get("message", "") for e in errors))
        return payload

    def shop_name(self) -> str:
        return self.graphql("{ shop { name } }").get("shop", {}).get("name", "")

    # --- Produkte ------------------------------------------------------------------
    def product_input(self, p: dict, vendor: str, active: bool, with_cost: bool = True) -> dict:
        offer = p["calc"]["offer"]
        variant: dict = {"optionValues": [{"optionName": "Title", "name": "Default Title"}],
                         "price": f"{offer['price']:.2f}", "sku": sku(p)}
        if with_cost:
            variant["inventoryItem"] = {"cost": f"{p['unit_cost'] * offer['n']:.2f}", "tracked": False}
        data = {
            "title": p["texts"]["title"], "descriptionHtml": p["texts"]["html"], "handle": p["seo"]["handle"],
            "productType": p["collection"], "vendor": vendor, "tags": p["seo"]["tags"],
            "status": "ACTIVE" if active else "DRAFT",
            "seo": {"title": p["seo"]["seo_title"], "description": p["seo"]["seo_description"]},
            "productOptions": [{"name": "Title", "values": [{"name": "Default Title"}]}],
            "variants": [variant],
        }
        if p.get("shopify_id"):
            data["id"] = p["shopify_id"]
        return data

    def upsert_product(self, p: dict, vendor: str, active: bool) -> dict:
        try:
            data = self.graphql(PRODUCT_SET, {"input": self.product_input(p, vendor, active), "synchronous": True})
        except ShopifyError as exc:
            if "inventoryItem" not in str(exc):
                raise
            log.warning("Shopify kennt den Einkaufspreis-Wert nicht – lege das Produkt ohne ihn an")
            data = self.graphql(PRODUCT_SET, {"input": self.product_input(p, vendor, active, with_cost=False),
                                              "synchronous": True})
        result = self._check(data.get("productSet"), "Produkt")
        product = result.get("product") or {}
        if active and product.get("id"):
            self.publish(product["id"])
        return product

    def online_store(self) -> str:
        if self._online_store is None:
            nodes = self.graphql(PUBLICATIONS).get("publications", {}).get("nodes", [])
            match = [n for n in nodes if "online" in n.get("name", "").lower()]
            if not match:
                raise ShopifyError("Vertriebskanal „Online Store“ nicht gefunden.")
            self._online_store = match[0]["id"]
        return self._online_store

    def publish(self, gid: str) -> None:
        data = self.graphql(PUBLISH, {"id": gid, "input": [{"publicationId": self.online_store()}]})
        self._check(data.get("publishablePublish"), "Veröffentlichen")

    # --- Seiten und Kategorien -------------------------------------------------------------
    def upsert_page(self, page: dict, page_id: str = "") -> str:
        fields = {"title": page["title"], "handle": page["handle"], "body": page["body_html"], "isPublished": True}
        if page_id:
            data = self.graphql(PAGE_UPDATE, {"id": page_id, "page": fields})
            return self._check(data.get("pageUpdate"), "Seite")["page"]["id"]
        data = self.graphql(PAGE_CREATE, {"page": fields})
        return self._check(data.get("pageCreate"), "Seite")["page"]["id"]

    def create_collection(self, c: dict) -> str:
        data = self.graphql(COLLECTION_CREATE, {"input": {
            "title": c["title"], "handle": c["handle"], "descriptionHtml": f"<p>{c['text']}</p>",
            "ruleSet": {"appliedDisjunctively": False,
                        "rules": [{"column": "TAG", "relation": "EQUALS", "condition": c["tag"]}]},
        }})
        gid = self._check(data.get("collectionCreate"), "Kategorie")["collection"]["id"]
        self.publish(gid)
        return gid

    # --- Bestellungen -----------------------------------------------------------------------
    def orders(self, days: int = 30) -> list[dict]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        nodes = self.graphql(ORDERS, {"query": f"created_at:>={since}"}).get("orders", {}).get("nodes", [])
        out = []
        for n in nodes:
            money = (n.get("totalPriceSet") or {}).get("shopMoney") or {}
            out.append({
                "id": n["id"], "name": n.get("name", ""), "created": n.get("createdAt", ""),
                "paid": n.get("displayFinancialStatus", ""), "fulfillment": n.get("displayFulfillmentStatus", ""),
                "total": float(money.get("amount") or 0), "currency": money.get("currencyCode", "EUR"),
                "items": [{"title": li.get("title", ""), "quantity": int(li.get("quantity") or 0),
                           "sku": li.get("sku") or ""} for li in (n.get("lineItems") or {}).get("nodes", [])],
            })
        return out


def sku(p: dict) -> str:
    return f"JS-{int(p['id']):04d}"


# --- Import-Datei -------------------------------------------------------------------------------
CSV_HEADERS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Product Category", "Type", "Tags", "Published",
    "Option1 Name", "Option1 Value", "Option2 Name", "Option2 Value", "Option3 Name", "Option3 Value",
    "Variant SKU", "Variant Grams", "Variant Inventory Tracker", "Variant Inventory Qty", "Variant Inventory Policy",
    "Variant Fulfillment Service", "Variant Price", "Variant Compare At Price", "Variant Requires Shipping",
    "Variant Taxable", "Variant Barcode", "Image Src", "Image Position", "Image Alt Text", "Gift Card",
    "SEO Title", "SEO Description", "Variant Image", "Variant Weight Unit", "Variant Tax Code", "Cost per item",
    "Status",
]


def export_csv(products: list[dict], path: Path, vendor: str) -> Path:
    """Shopify-Importdatei (Produkte → Importieren). Alle Produkte kommen als Entwurf an."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for p in products:
            offer = p["calc"]["offer"]
            writer.writerow({
                "Handle": p["seo"]["handle"], "Title": p["texts"]["title"], "Body (HTML)": p["texts"]["html"],
                "Vendor": vendor, "Type": p["collection"], "Tags": ", ".join(p["seo"]["tags"]),
                "Published": "FALSE", "Option1 Name": "Title", "Option1 Value": "Default Title",
                "Variant SKU": sku(p), "Variant Grams": int(p.get("weight_g", 0)) * offer["n"],
                "Variant Inventory Policy": "deny", "Variant Fulfillment Service": "manual",
                "Variant Price": f"{offer['price']:.2f}", "Variant Requires Shipping": "TRUE",
                "Variant Taxable": "TRUE", "Gift Card": "FALSE", "SEO Title": p["seo"]["seo_title"],
                "SEO Description": p["seo"]["seo_description"], "Variant Weight Unit": "g",
                "Cost per item": f"{p['unit_cost'] * offer['n']:.2f}", "Status": "draft",
            })
    return path
