"""Animations-Team: der Designer entwirft das Konzept (KI), der Animator rendert das Video (Engine)."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

from content_crew.animation import normalize_concept, random_concept
from content_crew.animation.catalog import TYPES, catalog_for_prompt
from content_crew.config import Config
from content_crew.llm import LLM

log = logging.getLogger(__name__)

DESIGNER_SYSTEM = (
    "Du bist Animations-Designer für virale TikTok-Videos. Du entwirfst animierte Clips: Physik-Simulationen, "
    "'oddly satisfying'-Animationen und hypnotische Muster. Im Video gibt es KEINE Sätze und KEINE Fotos – nur "
    "Animation, Musik und höchstens eine Zahl. Was viral geht: Spannung ab der ersten Sekunde, eine Frage im "
    "Kopf des Zuschauers ('schafft er es?', 'wer gewinnt?'), ein klarer Höhepunkt am Ende, eine bekannte "
    "Melodie, knallige Farben. Caption: kurz, Deutsch, mit Emoji und einer Frage, die zu Kommentaren einlädt. "
    "Keine falschen Versprechen."
)

def example_format(kind: str | None) -> str:
    """JSON-Beispiel für genau diese Animationsart (ein fremdes Beispiel schreibt das kleine Modell sonst ab)."""
    kind = kind if kind in TYPES else "ring_escape"
    spec = TYPES[kind]
    first, rule = next(iter(spec["params"].items()))
    value = rule[0] if isinstance(rule, list) else rule[2]
    return json.dumps({
        "type": kind, "params": {first: value}, "palette": "neon", "music": "...", "sound": "...", "duration": 35,
        "title": "NEUER kurzer Titel (3-6 Wörter)", "caption": "NEUE Frage an die Zuschauer passend zu dieser Animation",
        "hashtags": spec["tags"][:2]}, ensure_ascii=False)


class AnimationDesigner:
    """Entwirft mit dem Sprachmodell ein Konzept aus dem Katalog des Animators."""

    def __init__(self, llm: LLM, ki_text: bool = False):
        self.llm = llm
        self.ki_text = ki_text  # False = Titel/Caption aus geprüften Vorlagen statt vom kleinen Modell

    def design(self, idea: str, insights: dict, learnings: list[str], kind: str | None = None,
               previous: dict | None = None, feedback: str = "", recent: list[str] | None = None) -> dict:
        prompt = [
            f"Auftrag vom Chef: {idea}",
            "Das kann unser Animator (wähle daraus):\n" + json.dumps(catalog_for_prompt(kind), ensure_ascii=False),
            "Trend-Erkenntnisse: " + json.dumps(
                {k: insights.get(k) for k in ("patterns", "hooks", "formats", "avoid")}, ensure_ascii=False),
        ]
        if kind:
            prompt.append(f"Animationsart ist vorgegeben: {kind} ({TYPES[kind]['label']}).")
        if recent:
            prompt.append("Unsere letzten Videos (nicht wiederholen, Farben/Musik variieren): " + "; ".join(recent))
        if learnings:
            prompt.append("Was bei unseren eigenen Videos funktioniert hat:\n- " + "\n- ".join(learnings))
        if previous and feedback:
            prompt.append("Dein vorheriges Konzept:\n" + json.dumps(previous, ensure_ascii=False))
            prompt.append(f"Kritik vom Chef, unbedingt umsetzen:\n{feedback}")
        prompt.append("Antworte nur mit JSON in genau dieser Form. Titel und Caption schreibst du NEU, passend zu "
                      f"dieser Animation – nichts aus Beispielen übernehmen: {example_format(kind)}")
        try:
            raw = self.llm.chat_json(DESIGNER_SYSTEM, "\n\n".join(prompt), temperature=0.9)
        except Exception as exc:  # noqa: BLE001 – ohne KI trotzdem ein gutes Video
            log.warning("Designer ohne KI-Antwort (%s) – nehme ein zufälliges Konzept", exc)
            raw = {}
        if isinstance(raw, list):
            raw = raw[0] if raw and isinstance(raw[0], dict) else {}
        return normalize_concept(raw, force_type=kind, ki_text=self.ki_text)


class Animator:
    """Rendert Konzepte zu MP4 und prüft das Ergebnis technisch."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        a = cfg.get("animation", {})
        v = cfg["video"]
        self.settings = {
            "width": int(v.get("width", 1080)), "height": int(v.get("height", 1920)),
            "fps": int(a.get("fps", 60)), "bloom": float(a.get("bloom", 0.6)),
            "crf": int(a.get("crf", 18)), "preset": str(a.get("preset", "medium")),
        }

    @property
    def out_dir(self) -> Path:
        d = self.cfg.data_dir / "videos"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def check(info: dict, concept: dict) -> list[str]:
        """Technische Qualitätskontrolle: Länge, Bewegung, Helligkeit, Ton."""
        problems = []
        if info["duration"] < 10:
            problems.append(f"zu kurz ({info['duration']:.0f} s)")
        if info["duration"] > float(concept["duration"]) * 1.6 + 5:
            problems.append(f"viel zu lang ({info['duration']:.0f} s)")
        if info["motion"] < 0.4:
            problems.append("kaum Bewegung")
        if info["brightness"] < 4:
            problems.append("zu dunkel")
        if info["notes"] < 8:
            problems.append("fast kein Ton")
        return problems

    def produce(self, concept: dict, video_id: int) -> tuple[Path, dict]:
        from content_crew.animation import render

        target = self.out_dir / f"video_{video_id}.mp4"
        info = render(concept, target, **self.settings)
        problems = self.check(info, concept)
        if problems:  # ein zweiter Versuch mit anderem Zufall
            log.warning("Video %d: %s – rendere neu", video_id, ", ".join(problems))
            concept["seed"] = random.randrange(1, 1 << 30)
            info = render(concept, target, **self.settings)
            info["retry_because"] = problems
        info["problems"] = self.check(info, concept)
        log.info("Animation erstellt: %s (%.1f s, %d Noten)", target, info["duration"], info["notes"])
        return target, info

    def demo(self, kind: str | None = None, **overrides) -> tuple[Path, dict, dict]:
        """Ohne KI: ein zufälliges Konzept rendern (zum Ausprobieren)."""
        from content_crew.animation import render

        concept = random_concept(kind, **overrides)
        target = self.out_dir / f"demo_{concept['type']}_{concept['seed']}.mp4"
        return target, render(concept, target, **self.settings), concept
