"""Skript-Autor: schreibt Kurzvideo-Skripte und bessert nach Kritik vom Chef nach."""

from __future__ import annotations

import json

from content_crew.llm import LLM

SYSTEM = (
    "Du bist ein erfahrener Skript-Autor für virale Kurzvideos (15-45 Sekunden, Hochformat). "
    "Die ersten 2 Sekunden entscheiden alles: starker Hook. Kurze Sätze, gesprochen klingt natürlich, "
    "jede Szene max. 2 kurze Sätze. Ende mit Call-to-Action. Keine falschen Versprechen, keine "
    "erfundenen Fakten, keine urheberrechtlich geschützten Inhalte."
)

FORMAT = (
    "Regeln: title höchstens 70 Zeichen; 3 bis 8 scenes; text = gesprochener Satz (zugleich Untertitel); "
    "visual = 2-3 englische Suchbegriffe für ein passendes Stockvideo; 5-10 hashtags.\n"
    "Beispiel für die Struktur (Inhalt NICHT übernehmen):\n"
    '{"title": "Warum du morgens müde bist", "hook": "Du machst morgens diesen einen Fehler.", '
    '"scenes": [{"text": "Du machst morgens diesen einen Fehler.", "visual": "tired man alarm clock"}, '
    '{"text": "Folge mir für mehr.", "visual": "sunrise city"}], '
    '"caption": "Kurze Beschreibung mit Frage an die Zuschauer", "hashtags": ["#morgenroutine", "#motivation"]}'
)


def normalize_script(script: dict) -> dict:
    scenes = []
    for s in script.get("scenes") or []:
        text = s.get("text") if isinstance(s, dict) else str(s)
        visual = str(s.get("visual") or "").strip() if isinstance(s, dict) else ""
        if text and text.strip():
            scenes.append({"text": text.strip(), "visual": visual} if visual else {"text": text.strip()})
    if not scenes and script.get("hook"):
        scenes = [{"text": script["hook"]}]
    tags = [t if str(t).startswith("#") else f"#{t}" for t in (script.get("hashtags") or [])][:15]
    return {
        "title": str(script.get("title") or (scenes[0]["text"] if scenes else "Neues Video"))[:100],
        "hook": str(script.get("hook") or (scenes[0]["text"] if scenes else "")),
        "scenes": scenes[:12],
        "caption": str(script.get("caption") or ""),
        "hashtags": [str(t).replace(" ", "") for t in tags],
    }


class ScriptWriter:
    def __init__(self, llm: LLM, language: str = "de"):
        self.llm = llm
        self.language = language

    def write(self, idea: str, insights: dict, learnings: list[str], previous: dict | None = None,
              feedback: str = "") -> dict:
        prompt = [
            f"Sprache: {self.language}",
            f"Video-Idee: {idea}",
            "Trend-Erkenntnisse: " + json.dumps(
                {k: insights.get(k) for k in ("patterns", "hooks", "formats", "avoid")}, ensure_ascii=False),
        ]
        if learnings:
            prompt.append("Was bei unseren eigenen Videos funktioniert hat:\n- " + "\n- ".join(learnings))
        if previous and feedback:
            prompt.append("Dein vorheriges Skript:\n" + json.dumps(previous, ensure_ascii=False))
            prompt.append(f"Kritik vom Chef, unbedingt umsetzen:\n{feedback}")
        prompt.append(f"Schreibe das Skript als JSON: {FORMAT}")
        return normalize_script(self.llm.chat_json(SYSTEM, "\n\n".join(prompt), temperature=0.8))
