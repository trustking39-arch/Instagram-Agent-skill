"""Shop-Abteilung: 14 KI-Arbeiter, die mit Jarvis einen Online-Shop aufbauen und betreiben."""

from content_crew.shop.manager import ShopManager, approve_product, reject_product, shop_status_text
from content_crew.shop.team import WORKERS

__all__ = ["ShopManager", "WORKERS", "approve_product", "reject_product", "shop_status_text"]
