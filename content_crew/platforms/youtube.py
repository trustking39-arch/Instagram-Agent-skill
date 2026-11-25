"""YouTube Data API v3: Trend-Suche, Shorts-Upload, Statistiken."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import requests

from content_crew.platforms.base import Platform, PlatformError

API = "https://www.googleapis.com/youtube/v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


class YouTube(Platform):
    name = "youtube"

    @property
    def api_key(self) -> str:
        return self.cfg.env("YOUTUBE_API_KEY")

    @property
    def secret_file(self) -> Path:
        return Path(self.cfg.env("YOUTUBE_CLIENT_SECRET_FILE", "secrets/youtube_client_secret.json"))

    @property
    def token_file(self) -> Path:
        return self.cfg.data_dir / "youtube_token.json"

    def missing(self) -> list[str]:
        out = []
        if not self.api_key:
            out.append("YOUTUBE_API_KEY")
        if not self.secret_file.exists():
            out.append(f"OAuth-Datei {self.secret_file}")
        elif not self.token_file.exists():
            out.append("YouTube-Login (content-crew auth-youtube)")
        return out

    # --- OAuth ---------------------------------------------------------
    def authorize(self) -> None:
        """Einmalig im Browser anmelden (auf deinem PC ausführen)."""
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(self.secret_file), SCOPES)
        creds = flow.run_local_server(port=0)
        self.token_file.write_text(creds.to_json(), encoding="utf-8")

    def _service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        if not self.token_file.exists():
            raise PlatformError("YouTube ist nicht angemeldet: content-crew auth-youtube ausführen", blocked=True)
        creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.token_file.write_text(creds.to_json(), encoding="utf-8")
            else:
                raise PlatformError("YouTube-Login abgelaufen: content-crew auth-youtube ausführen", blocked=True)
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    # --- API -----------------------------------------------------------
    def _get(self, path: str, **params) -> dict:
        resp = requests.get(f"{API}/{path}", params={"key": self.api_key, **params}, timeout=30)
        if resp.status_code == 403:
            raise PlatformError(f"YouTube API verweigert: {resp.text[:200]}", blocked=True)
        resp.raise_for_status()
        return resp.json()

    def trends(self, niche: str, limit: int = 10) -> list[dict]:
        if not self.api_key:
            return []
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lang = self.cfg.get("language", "de")
        found = self._get(
            "search", part="snippet", q=niche, type="video", order="viewCount", videoDuration="short",
            publishedAfter=since, relevanceLanguage=lang, maxResults=min(limit, 50),
        )
        ids = [item["id"]["videoId"] for item in found.get("items", [])]
        if not ids:
            return []
        details = self._get("videos", part="snippet,statistics", id=",".join(ids))
        out = []
        for v in details.get("items", []):
            s = v.get("statistics", {})
            out.append({
                "platform": self.name,
                "title": v["snippet"]["title"],
                "channel": v["snippet"].get("channelTitle", ""),
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
                "url": f"https://youtube.com/shorts/{v['id']}",
            })
        return sorted(out, key=lambda x: x["views"], reverse=True)

    def upload(self, video: Path, title: str, description: str, tags: list[str], public_url: str = "") -> str:
        from googleapiclient.http import MediaFileUpload

        if "#shorts" not in (title + description).lower():
            description = f"{description}\n#Shorts"
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": [t.lstrip("#") for t in tags][:30],
                "categoryId": "22",
                "defaultLanguage": self.cfg.get("language", "de"),
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        request = self._service().videos().insert(
            part="snippet,status", body=body, media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True)
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        return response["id"]

    def stats(self, post_id: str) -> dict:
        data = self._get("videos", part="statistics", id=post_id)
        items = data.get("items", [])
        if not items:
            return {}
        s = items[0]["statistics"]
        return {
            "views": int(s.get("viewCount", 0)),
            "likes": int(s.get("likeCount", 0)),
            "comments": int(s.get("commentCount", 0)),
            "shares": None,
        }
