from __future__ import annotations

from pathlib import Path

from content_crew.config import Config


class PlatformError(RuntimeError):
    """Fehler einer Plattform. blocked=True heißt: Jarvis braucht den Besitzer (z. B. Token abgelaufen)."""

    def __init__(self, message: str, blocked: bool = False):
        super().__init__(message)
        self.blocked = blocked


class Platform:
    name = "base"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def missing(self) -> list[str]:
        """Fehlende Zugangsdaten (leer = einsatzbereit)."""
        return []

    @property
    def configured(self) -> bool:
        return not self.missing()

    def trends(self, niche: str, limit: int = 10) -> list[dict]:
        """Erfolgreiche aktuelle Inhalte zum Thema: [{title, views, likes, comments, url}]."""
        return []

    def upload(self, video: Path, title: str, description: str, tags: list[str], public_url: str = "") -> str:
        raise NotImplementedError

    def stats(self, post_id: str) -> dict:
        """{views, likes, comments, shares} eines eigenen Posts."""
        raise NotImplementedError
