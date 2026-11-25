"""Instagram Graph API (Business/Creator-Konto): Hashtag-Trends, Reels-Upload, Insights."""

from __future__ import annotations

import re
import time
from pathlib import Path

import requests

from content_crew.platforms.base import Platform, PlatformError

GRAPH = "https://graph.facebook.com/v21.0"


class Instagram(Platform):
    name = "instagram"

    @property
    def user_id(self) -> str:
        return self.cfg.env("INSTAGRAM_USER_ID")

    @property
    def token(self) -> str:
        return self.cfg.env("INSTAGRAM_ACCESS_TOKEN")

    def missing(self) -> list[str]:
        out = [n for n in ("INSTAGRAM_USER_ID", "INSTAGRAM_ACCESS_TOKEN") if not self.cfg.env(n)]
        if not self.cfg["notify"].get("public_base_url"):
            out.append("notify.public_base_url (öffentliche URL für Video-Upload)")
        return out

    def _req(self, method: str, path: str, **params) -> dict:
        params["access_token"] = self.token
        resp = requests.request(method, f"{GRAPH}/{path}", params=params, timeout=60)
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            err = data.get("error", {})
            blocked = err.get("code") in (190, 10, 200) or resp.status_code in (401, 403)
            raise PlatformError(f"Instagram: {err.get('message', resp.text[:200])}", blocked=blocked)
        return data

    def trends(self, niche: str, limit: int = 10) -> list[dict]:
        if not (self.user_id and self.token):
            return []
        tag = re.sub(r"[^\wäöüß]", "", niche.split()[0].lower()) or "motivation"
        found = self._req("GET", "ig_hashtag_search", user_id=self.user_id, q=tag).get("data", [])
        if not found:
            return []
        media = self._req(
            "GET", f"{found[0]['id']}/top_media", user_id=self.user_id,
            fields="caption,like_count,comments_count,permalink,media_type", limit=limit,
        ).get("data", [])
        return [{
            "platform": self.name,
            "title": (m.get("caption") or "")[:150],
            "views": None,
            "likes": m.get("like_count", 0),
            "comments": m.get("comments_count", 0),
            "url": m.get("permalink", ""),
        } for m in media]

    def upload(self, video: Path, title: str, description: str, tags: list[str], public_url: str = "") -> str:
        if not public_url:
            raise PlatformError("Instagram braucht eine öffentliche Video-URL (notify.public_base_url)", blocked=True)
        caption = f"{title}\n\n{description}\n\n{' '.join(tags)}"[:2200]
        container = self._req(
            "POST", f"{self.user_id}/media", media_type="REELS", video_url=public_url, caption=caption,
            share_to_feed="true",
        )["id"]
        for _ in range(60):  # bis zu 10 Minuten auf Verarbeitung warten
            status = self._req("GET", container, fields="status_code,status").get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise PlatformError("Instagram konnte das Video nicht verarbeiten")
            time.sleep(10)
        else:
            raise PlatformError("Instagram-Verarbeitung dauert zu lange")
        return self._req("POST", f"{self.user_id}/media_publish", creation_id=container)["id"]

    def stats(self, post_id: str) -> dict:
        base = self._req("GET", post_id, fields="like_count,comments_count")
        out = {"views": None, "likes": base.get("like_count"), "comments": base.get("comments_count"), "shares": None}
        try:
            insights = self._req("GET", f"{post_id}/insights", metric="views,shares").get("data", [])
            for item in insights:
                value = item.get("values", [{}])[0].get("value")
                if item["name"] in ("views", "shares"):
                    out[item["name"]] = value
        except PlatformError:
            pass
        return out
