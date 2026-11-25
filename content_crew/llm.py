"""Verbindung zu Jarvis (OpenJarvis, OpenAI-kompatible API)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

log = logging.getLogger(__name__)

ANSWER_TOOL = {
    "type": "function",
    "function": {
        "name": "antwort",
        "description": "Gib hier deine vollständige Antwort zurück.",
        "parameters": {
            "type": "object",
            "properties": {"antwort": {
                "type": "string",
                "description": "deine vollständige Antwort (bei JSON-Aufgaben das JSON als Text)",
            }},
            "required": ["antwort"],
        },
    },
}


def extract_json(text: str) -> Any:
    """Erstes gültiges JSON-Objekt/-Array aus einer Modellantwort holen."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                value, _ = decoder.raw_decode(text[i:])
                return value
            except json.JSONDecodeError:
                continue
    raise ValueError("Keine gültige JSON-Antwort gefunden")


class LLM:
    def __init__(self, cfg: dict, api_key: str = "none"):
        self.base_url = cfg["base_url"].rstrip("/")
        self.model = cfg["model"]
        self.timeout = int(cfg.get("timeout_seconds", 600))
        self.api_key = api_key or "none"
        self.direct = bool(cfg.get("direct", True))

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.direct:
            # Mit eigener Werkzeugliste antwortet der OpenJarvis-Server direkt mit dem Modell,
            # statt erst seinen Agenten (inkl. Websuche) laufen zu lassen. Das ist für klar
            # umrissene Team-Aufgaben schneller und verlässlicher.
            body["tools"] = [ANSWER_TOOL]
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        message = resp.json()["choices"][0]["message"]
        content = message.get("content") or ""
        for call in message.get("tool_calls") or []:
            fn = call.get("function", {})
            if fn.get("name") == "antwort":
                args = fn.get("arguments") or "{}"
                try:
                    parsed = json.loads(args) if isinstance(args, str) else args
                except json.JSONDecodeError:
                    parsed = {"antwort": args}
                value = parsed.get("antwort", parsed) if isinstance(parsed, dict) else parsed
                content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                break
        return re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()

    def chat_json(self, system: str, user: str, retries: int = 2, temperature: float = 0.5) -> Any:
        system = system + "\nAntworte AUSSCHLIESSLICH mit gültigem JSON, ohne Erklärtext."
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            text = self.chat(system, user, temperature=temperature)
            try:
                return extract_json(text)
            except ValueError as exc:
                last_error = exc
                log.warning("Ungültiges JSON von Jarvis (Versuch %d): %s", attempt + 1, text[:200])
                user += "\n\nWICHTIG: Deine letzte Antwort war kein gültiges JSON. Gib nur JSON zurück."
        raise RuntimeError(f"Jarvis lieferte kein JSON: {last_error}")
