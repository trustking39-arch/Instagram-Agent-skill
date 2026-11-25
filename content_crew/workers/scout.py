"""Trend-Scout: sammelt, was in deiner Nische gerade gut läuft, und wertet es aus."""

from __future__ import annotations

import logging

from content_crew.llm import LLM
from content_crew.platforms.base import Platform, PlatformError

log = logging.getLogger(__name__)

SYSTEM = (
    "Du bist ein Social-Media-Trendanalyst für Kurzvideos (YouTube Shorts, Instagram Reels, TikTok). "
    "Du erkennst Muster in erfolgreichen Videos: Hooks, Themen, Formate, Längen, Emotionen."
)


class TrendScout:
    def __init__(self, llm: LLM, platforms: dict[str, Platform]):
        self.llm = llm
        self.platforms = platforms

    def collect(self, niche: str) -> tuple[list[dict], list[PlatformError]]:
        items: list[dict] = []
        errors: list[PlatformError] = []
        for p in self.platforms.values():
            try:
                items.extend(p.trends(niche))
            except PlatformError as exc:
                errors.append(exc)
                log.warning("Trends von %s fehlgeschlagen: %s", p.name, exc)
            except Exception as exc:  # noqa: BLE001
                errors.append(PlatformError(f"{p.name}: {exc}"))
                log.exception("Trends von %s fehlgeschlagen", p.name)
        return items, errors

    def analyze(self, niche: str, items: list[dict]) -> dict:
        if items:
            lines = "\n".join(
                f"- [{i['platform']}] {i['title']!r} | Views {i.get('views')} | Likes {i.get('likes')} "
                f"| Kommentare {i.get('comments')}"
                for i in items[:30]
            )
            source = f"Aktuell erfolgreiche Videos zum Thema:\n{lines}"
        else:
            source = "Es liegen gerade keine Plattformdaten vor. Nutze dein allgemeines Wissen über die Nische."
        return self.llm.chat_json(
            SYSTEM,
            f"Nische: {niche}\n\n{source}\n\n"
            'Analysiere und gib JSON zurück: {"patterns": ["..."], "hooks": ["..."], '
            '"topics": ["..."], "formats": ["..."], "avoid": ["..."]}',
        )

    def run(self, niche: str) -> dict:
        items, errors = self.collect(niche)
        insights = self.analyze(niche, items)
        if not isinstance(insights, dict):
            insights = {"patterns": insights}
        insights["sample_size"] = len(items)
        insights["top_examples"] = items[:5]
        insights["errors"] = [str(e) for e in errors]
        insights["_blocked"] = [str(e) for e in errors if e.blocked]
        return insights
