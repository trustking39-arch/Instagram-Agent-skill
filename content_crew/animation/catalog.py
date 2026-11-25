"""Was der Animator kann: Animationsarten, Einstellungen, Farben, Musik – und Prüfung von Konzepten."""

from __future__ import annotations

import random

from content_crew.animation.audio import INSTRUMENTS, MELODIES, SCALES
from content_crew.animation.palettes import PALETTES

# Zahlen: (min, max, standard). Listen: erlaubte Werte, der erste ist Standard.
TYPES: dict[str, dict] = {
    "ring_escape": {
        "label": "Ring-Flucht",
        "query": "ball escape rings simulation",
        "idee": "Ein Ball springt in vielen sich drehenden Ringen mit je einer Lücke. Jeder Aufprall spielt die "
                "nächste Note einer Melodie, jede durchflogene Lücke lässt einen Ring zersplittern. Oben zählt "
                "eine Zahl die Ringe herunter – Spannung bis zum letzten Ring.",
        "params": {"rings": (8, 50, 26), "balls": (1, 3, 1), "gravity": (0.6, 1.6, 1.0), "spin": (0.5, 2.0, 1.0),
                   "pattern": ["spiral", "alternating", "random"]},
        "caption": "Schafft er alle {rings} Ringe? 😳 Schreib deine Schätzung in die Kommentare!",
        "tags": ["#satisfying", "#simulation", "#physics", "#animation", "#asmr"],
    },
    "escape_multiply": {
        "label": "Ball-Vermehrung",
        "query": "every escape 2 balls simulation",
        "idee": "Ein Ball springt in einem sich drehenden Ring mit Lücke. Jeder Ball, der entkommt, wird zu zwei "
                "neuen Bällen in der Mitte – exponentielles Chaos bis zum großen Knall. Oben zählt eine Zahl die Bälle.",
        "params": {"max_balls": (40, 300, 150), "gravity": (0.6, 1.6, 1.0), "spin": (0.5, 2.0, 1.0)},
        "caption": "Jeder Ball, der entkommt, wird zu zwei 🤯 Bei welcher Zahl platzt der Ring?",
        "tags": ["#satisfying", "#simulation", "#chaos", "#animation", "#oddlysatisfying"],
    },
    "growing_ball": {
        "label": "Wachsender Ball",
        "query": "ball grows every bounce satisfying",
        "idee": "Ein Ball springt in einem Kreis und wird bei jedem Aufprall größer, bis er den Kreis ganz "
                "ausfüllt. Jeder Aufprall spielt die nächste Note, die Spur malt ein farbiges Muster. Gegen Ende "
                "immer schneller – großes Finale.",
        "params": {"gravity": (0.6, 1.6, 1.0), "trail": ["outline", "fill"], "start_size": (0.02, 0.06, 0.03)},
        "caption": "Jeder Aufprall = größer & die nächste Note 🎶 Erkennst du das Lied?",
        "tags": ["#satisfying", "#bouncingball", "#music", "#animation", "#oddlysatisfying"],
    },
    "color_wars": {
        "label": "Farben-Krieg",
        "query": "pong wars color battle simulation",
        "idee": "Bälle in Teamfarben erobern Felder: Trifft ein Ball ein gegnerisches Feld, färbt er es um und "
                "prallt ab. Zahlen oben zeigen den Stand – wer hat am Ende die meiste Fläche?",
        "params": {"teams": [2, 4], "cols": (18, 40, 26), "speed": (0.7, 1.6, 1.0), "balls_per_team": (1, 3, 1)},
        "caption": "Welche Farbe gewinnt? 👀 Wähl dein Team in den Kommentaren!",
        "tags": ["#satisfying", "#simulation", "#pongwars", "#colors", "#animation"],
    },
    "polyrhythm": {
        "label": "Polyrhythmus",
        "query": "polyrhythm animation satisfying",
        "idee": "Viele leuchtende Punkte bewegen sich in leicht unterschiedlichem Tempo (Bögen, Welle oder "
                "Umlaufbahnen) und spielen jeweils ihren eigenen Ton. Es entstehen hypnotische Muster – am Ende "
                "treffen sich alle gleichzeitig (Countdown oben).",
        "params": {"layout": ["arcs", "wave", "orbits"], "dots": (12, 30, 21), "speed": (0.2, 0.45, 0.3)},
        "caption": "Warte, bis sich alle treffen 🤯 Hast du bis zum Ende geschaut?",
        "tags": ["#satisfying", "#polyrhythm", "#hypnotic", "#animation", "#relaxing"],
    },
}

MELODY_LABELS = {
    "fur_elise": "Für Elise (Beethoven)", "ode_to_joy": "Ode an die Freude (Beethoven)",
    "mountain_king": "In der Halle des Bergkönigs (Grieg)", "canon": "Kanon in D (Pachelbel)",
    "twinkle": "Morgen kommt der Weihnachtsmann / Twinkle Twinkle", "greensleeves": "Greensleeves",
    "jingle_bells": "Jingle Bells", "silent_night": "Stille Nacht",
}
SCALE_LABELS = {"pentatonic": "freie Melodie (pentatonisch)", "major": "freie Melodie (Dur)",
                "minor": "freie Melodie (Moll)", "dreamy": "freie Melodie (verträumt)",
                "japanese": "freie Melodie (japanisch)"}
# Bei diesen Arten spielt jeder Punkt/jedes Team eigene Töne – eine Melodie passt dort nicht.
SCALE_ONLY = {"polyrhythm", "color_wars"}
DEFAULT_SOUND = {"ring_escape": "bell", "escape_multiply": "glass", "growing_ball": "pluck",
                 "color_wars": "marimba", "polyrhythm": "glass"}


def type_for(text: str) -> str | None:
    """Animationsart aus einem Namen oder einer Nischen-Bezeichnung erkennen."""
    low = (text or "").lower()
    for key, spec in TYPES.items():
        if key in low or spec["label"].lower() in low:
            return key
    return None


def _number(value, lo, hi, default):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    v = min(hi, max(lo, v))
    return int(round(v)) if isinstance(default, int) else round(v, 3)


def _choice(value, options, fallback):
    for opt in options:
        if value == opt or str(value).strip().lower() == str(opt).lower():
            return opt
    return fallback


def _music_key(value, options: list[str]) -> str | None:
    """Musik auch erkennen, wenn die KI den deutschen Namen schreibt (z. B. „Für Elise“)."""
    low = str(value or "").strip().lower()
    if not low:
        return None
    for key in options:
        label = (MELODY_LABELS.get(key) or SCALE_LABELS.get(key) or "").lower()
        if key in low.replace(" ", "_") or (label and label.split(" (")[0] in low) or low == label:
            return key
    return None


def normalize_concept(raw: dict | None, force_type: str | None = None, rng: random.Random | None = None,
                      randomize: bool = False) -> dict:
    """Konzept vom KI-Designer prüfen: unbekannte Werte ersetzen, Zahlen begrenzen, Texte auffüllen."""
    rng = rng or random.Random()
    raw = raw if isinstance(raw, dict) else {}
    kind = force_type if force_type in TYPES else (raw.get("type") if raw.get("type") in TYPES else None)
    kind = kind or type_for(str(raw.get("type", ""))) or rng.choice(list(TYPES))
    spec = TYPES[kind]
    given = raw.get("params") if isinstance(raw.get("params"), dict) else {}
    params = {}
    for key, rule in spec["params"].items():
        value = given.get(key, raw.get(key))
        if isinstance(rule, list):
            params[key] = _choice(value, rule, rng.choice(rule) if randomize or value is None else rule[0])
        else:
            lo, hi, default = rule
            if value is None and randomize:
                value = rng.uniform(lo, hi) if not isinstance(default, int) else rng.randint(lo, hi)
            params[key] = _number(value, lo, hi, default)

    music_options = list(SCALES) if kind in SCALE_ONLY else list(MELODIES) + list(SCALES)
    music = _music_key(raw.get("music"), music_options)
    if music is None:
        music = rng.choice(list(SCALES) if kind in SCALE_ONLY else list(MELODIES))
    palette = _choice(raw.get("palette"), list(PALETTES), rng.choice(list(PALETTES)))
    sound = _choice(raw.get("sound"), list(INSTRUMENTS), DEFAULT_SOUND[kind])
    duration = _number(raw.get("duration"), 20, 60, 35 if not randomize else rng.randint(28, 42))
    try:
        seed = int(raw.get("seed"))
    except (TypeError, ValueError):
        seed = rng.randrange(1, 1 << 30)

    caption = str(raw.get("caption") or "").strip() or spec["caption"].format(**params)
    title = str(raw.get("title") or "").strip() or caption.split("?")[0][:80]
    tags = [str(t).strip().replace(" ", "") for t in (raw.get("hashtags") or []) if str(t).strip()]
    tags = [t if t.startswith("#") else f"#{t}" for t in tags]
    for t in spec["tags"]:
        if len(tags) >= 8:
            break
        if t.lower() not in (x.lower() for x in tags):
            tags.append(t)
    music_label = MELODY_LABELS.get(music) or SCALE_LABELS.get(music, music)
    return {
        "type": kind, "label": spec["label"], "params": params, "palette": palette, "music": music,
        "sound": sound, "duration": duration, "seed": seed,
        "title": title[:100], "caption": caption[:2000], "hashtags": tags[:12],
        "hook": f"{spec['label']} · {music_label} · Farben {palette}",
        "scenes": [],
    }


def random_concept(kind: str | None = None, rng: random.Random | None = None, **overrides) -> dict:
    """Zufälliges, gültiges Konzept (ohne KI) – für Tests, Demos und als Rückfallebene."""
    rng = rng or random.Random()
    raw = {k: v for k, v in overrides.items() if v is not None}
    return normalize_concept(raw, force_type=kind, rng=rng, randomize=True)


def catalog_for_prompt(kind: str | None = None) -> dict:
    """Kurzbeschreibung für den KI-Designer."""
    kinds = [kind] if kind in TYPES else list(TYPES)
    types = {}
    for k in kinds:
        spec = TYPES[k]
        types[k] = {
            "name": spec["label"], "idee": spec["idee"],
            "params": {p: (r if isinstance(r, list) else f"{r[0]} bis {r[1]} (Standard {r[2]})")
                       for p, r in spec["params"].items()},
        }
    music = list(SCALES) if kind in SCALE_ONLY else list(MELODIES) + list(SCALES)
    return {
        "typen": types,
        "palette": list(PALETTES),
        "music": {m: MELODY_LABELS.get(m) or SCALE_LABELS.get(m) for m in music},
        "sound": list(INSTRUMENTS),
        "duration": "20 bis 60 Sekunden (am besten 25-40)",
    }
