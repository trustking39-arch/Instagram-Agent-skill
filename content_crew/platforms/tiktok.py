"""TikTok Content Posting API + Display API: Upload und Statistiken.

Hinweis: TikTok bietet normalen Entwicklern keine Trend-Suche an. Trends kommen
deshalb von YouTube/Instagram, TikTok liefert die Zahlen deiner eigenen Videos.
Solange deine TikTok-App nicht von TikTok geprüft ("audited") ist, sind
hochgeladene Videos nur für dich sichtbar (SELF_ONLY).
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from content_crew.platforms.base import Platform, PlatformError

API = "https://open.tiktokapis.com/v2"
CHUNK = 10 * 1024 * 1024


class TikTok(Platform):
    name = "tiktok"

    def missing(self) -> list[str]:
        return [n for n in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN") if not self.cfg.env(n)]

    @property
    def _token_cache(self) -> Path:
        return self.cfg.data_dir / "tiktok_token.txt"

    def _token(self) -> str:
        return self.cfg.env("TIKTOK_ACCESS_TOKEN") or (
            self._token_cache.read_text().strip() if self._token_cache.exists() else "")

    def refresh(self) -> None:
        refresh = self.cfg.env("TIKTOK_REFRESH_TOKEN")
        if not refresh:
            raise PlatformError("TikTok-Token abgelaufen und kein Refresh-Token vorhanden", blocked=True)
        resp = requests.post(f"{API}/oauth/token/", data={
            "client_key": self.cfg.env("TIKTOK_CLIENT_KEY"),
            "client_secret": self.cfg.env("TIKTOK_CLIENT_SECRET"),
            "grant_type": "refresh_token",
            "refresh_token": refresh,
        }, timeout=30)
        data = resp.json()
        if "access_token" not in data:
            raise PlatformError(f"TikTok-Token konnte nicht erneuert werden: {data}", blocked=True)
        self._token_cache.write_text(data["access_token"])
        from content_crew.envfile import set_env_values

        set_env_values({"TIKTOK_ACCESS_TOKEN": data["access_token"],
                        "TIKTOK_REFRESH_TOKEN": data.get("refresh_token", refresh)})

    def _post(self, path: str, body: dict, params: dict | None = None, retry: bool = True) -> dict:
        resp = requests.post(
            f"{API}/{path}", params=params, json=body, timeout=60,
            headers={"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json; charset=UTF-8"},
        )
        data = resp.json() if resp.content else {}
        code = data.get("error", {}).get("code", "ok")
        if code == "access_token_invalid" and retry:
            self.refresh()
            return self._post(path, body, params, retry=False)
        if resp.status_code >= 400 or code != "ok":
            blocked = code in ("access_token_invalid", "scope_not_authorized", "unaudited_client_can_only_post_to_private_accounts")
            raise PlatformError(f"TikTok: {data.get('error', {}).get('message', resp.text[:200])}", blocked=blocked)
        return data.get("data", {})

    def _privacy(self) -> str:
        info = self._post("post/publish/creator_info/query/", {})
        options = info.get("privacy_level_options", ["SELF_ONLY"])
        return "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in options else options[0]

    def upload(self, video: Path, title: str, description: str, tags: list[str], public_url: str = "") -> str:
        size = video.stat().st_size
        chunk = size if size <= CHUNK else CHUNK
        count = max(1, size // chunk)
        init = self._post("post/publish/video/init/", {
            "post_info": {
                "title": f"{title} {' '.join(tags)}"[:2200],
                "privacy_level": self._privacy(),
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
            },
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count},
        })
        upload_url, publish_id = init["upload_url"], init["publish_id"]
        with video.open("rb") as fh:
            for i in range(count):
                start = i * chunk
                end = size - 1 if i == count - 1 else start + chunk - 1
                fh.seek(start)
                part = fh.read(end - start + 1)
                r = requests.put(upload_url, data=part, timeout=300, headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes {start}-{end}/{size}",
                    "Content-Length": str(len(part)),
                })
                if r.status_code not in (200, 201, 206):
                    raise PlatformError(f"TikTok-Upload fehlgeschlagen: HTTP {r.status_code}")
        for _ in range(60):
            st = self._post("post/publish/status/fetch/", {"publish_id": publish_id})
            if st.get("status") == "PUBLISH_COMPLETE":
                ids = st.get("publicaly_available_post_id") or []
                return str(ids[0]) if ids else f"publish:{publish_id}"
            if st.get("status") == "FAILED":
                raise PlatformError(f"TikTok hat den Post abgelehnt: {st.get('fail_reason')}")
            time.sleep(10)
        return f"publish:{publish_id}"

    def stats(self, post_id: str) -> dict:
        if post_id.startswith("publish:"):
            st = self._post("post/publish/status/fetch/", {"publish_id": post_id.split(":", 1)[1]})
            ids = st.get("publicaly_available_post_id") or []
            if not ids:
                return {}
            post_id = str(ids[0])
        data = self._post(
            "video/query/", {"filters": {"video_ids": [post_id]}},
            params={"fields": "id,title,view_count,like_count,comment_count,share_count"},
        )
        videos = data.get("videos", [])
        if not videos:
            return {}
        v = videos[0]
        return {"views": v.get("view_count"), "likes": v.get("like_count"),
                "comments": v.get("comment_count"), "shares": v.get("share_count")}
