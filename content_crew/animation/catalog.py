"""Was der Animator kann: Animationsarten, Einstellungen, Farben, Musik – und Prüfung von Konzepten."""

from __future__ import annotations

import random
import re

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
        "tags": ["#satisfying", "#simulation", "#bouncingball", "#oddlysatisfying", "#physics"],
    },
    "escape_multiply": {
        "label": "Ball-Vermehrung",
        "query": "every escape 2 balls simulation",
        "idee": "Ein Ball springt in einem sich drehenden Ring mit Lücke. Jeder Ball, der entkommt, wird zu zwei "
                "neuen Bällen in der Mitte – exponentielles Chaos bis zum großen Knall. Oben zählt eine Zahl die Bälle.",
        "params": {"max_balls": (40, 300, 150), "gravity": (0.6, 1.6, 1.0), "spin": (0.5, 2.0, 1.0)},
        "caption": "Jeder Ball, der entkommt, wird zu zwei 🤯 Bei welcher Zahl platzt der Ring?",
        "tags": ["#satisfying", "#simulation", "#chaos", "#oddlysatisfying", "#physics"],
    },
    "growing_ball": {
        "label": "Wachsender Ball",
        "query": "ball grows every bounce satisfying",
        "idee": "Ein Ball springt in einem Kreis und wird bei jedem Aufprall größer, bis er den Kreis ganz "
                "ausfüllt. Jeder Aufprall spielt die nächste Note, die Spur malt ein farbiges Muster. Gegen Ende "
                "immer schneller – großes Finale.",
        "params": {"gravity": (0.6, 1.6, 1.0), "trail": ["outline", "fill"], "start_size": (0.02, 0.06, 0.03)},
        "caption": "Jeder Aufprall = größer & die nächste Note 🎶 Erkennst du das Lied?",
        "tags": ["#satisfying", "#bouncingball", "#oddlysatisfying", "#music", "#simulation"],
    },
    "color_wars": {
        "label": "Farben-Krieg",
        "query": "pong wars color battle simulation",
        "idee": "Bälle in Teamfarben erobern Felder: Trifft ein Ball ein gegnerisches Feld, färbt er es um und "
                "prallt ab. Zahlen oben zeigen den Stand – wer hat am Ende die meiste Fläche?",
        "params": {"teams": [2, 4], "cols": (18, 40, 26), "speed": (0.7, 1.6, 1.0), "balls_per_team": (1, 3, 1)},
        "caption": "Welche Farbe gewinnt? 👀 Wähl dein Team in den Kommentaren!",
        "tags": ["#pongwars", "#satisfying", "#simulation", "#oddlysatisfying", "#colors"],
    },
    "polyrhythm": {
        "label": "Polyrhythmus",
        "query": "polyrhythm animation satisfying",
        "idee": "Viele leuchtende Punkte bewegen sich in leicht unterschiedlichem Tempo (Bögen, Welle oder "
                "Umlaufbahnen) und spielen jeweils ihren eigenen Ton. Es entstehen hypnotische Muster – am Ende "
                "treffen sich alle gleichzeitig (Countdown oben).",
        "params": {"layout": ["arcs", "wave", "orbits"], "dots": (12, 30, 21), "speed": (0.2, 0.45, 0.3)},
        "caption": "Warte, bis sich alle treffen 🤯 Hast du bis zum Ende geschaut?",
        "tags": ["#polyrhythm", "#satisfying", "#hypnotic", "#relaxing", "#asmr"],
    },
    "galton": {
        "label": "Galton-Brett",
        "query": "galton board satisfying simulation",
        "idee": "Hunderte bunte Kugeln fallen durch ein Dreieck aus Nägeln in Fächer. Jede landende Kugel spielt "
                "einen Ton, die Fächer füllen sich in Farbschichten – am Ende entsteht von selbst eine perfekte "
                "Glockenkurve, die aufleuchtet.",
        "params": {"rows": (8, 14, 12), "balls": (120, 400, 220)},
        "caption": "In welchem Fach landen die meisten Kugeln? 🎯 Tipp jetzt!",
        "tags": ["#galtonboard", "#satisfying", "#physik", "#mathe", "#oddlysatisfying"],
    },
    "spin_arena": {
        "label": "Dreh-Arena",
        "query": "balls spinning hexagon last one wins",
        "idee": "Nummerierte Bälle springen in einem sich drehenden Vieleck (z. B. Sechseck) mit einer offenen "
                "Seite. Einer nach dem anderen fliegt hinaus – die Zahl oben zählt herunter. Welche Nummer bleibt "
                "als Letzte übrig? Der Sieger wird groß gefeiert.",
        "params": {"sides": (3, 8, 6), "balls": (6, 16, 10), "spin": (0.4, 1.6, 0.9), "gravity": (0.6, 1.5, 1.0)},
        "caption": "Welche Nummer bleibt als Letzte drin? 👀 Schreib deinen Tipp in die Kommentare!",
        "tags": ["#satisfying", "#simulation", "#bouncingball", "#oddlysatisfying", "#physics"],
    },
    "string_art": {
        "label": "Faden-Netz",
        "query": "bouncing ball every bounce adds a line",
        "idee": "Ein leuchtender Ball springt in einem Kreis. Jeder Aufprall setzt einen Punkt und spannt einen neuen "
                "Faden – entweder alle Fäden zum Ball (ein Netz, das ihm folgt) oder von Treffer zu Treffer (ein "
                "Fadenbild). Jeder Aufprall spielt die nächste Note, die Zahl oben zählt die Fäden.",
        "params": {"points": (30, 120, 60), "gravity": (0.6, 1.5, 1.0), "web": ["ball", "chain"]},
        "caption": "Jeder Aufprall spannt einen neuen Faden 🕸️ Wie sieht es am Ende aus?",
        "tags": ["#satisfying", "#stringart", "#bouncingball", "#oddlysatisfying", "#simulation"],
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
# Lied- und Saison-Hashtags (Weihnachtsmelodien bringen im Advent zusätzliche Reichweite)
MELODY_TAGS = {
    "jingle_bells": "#weihnachten", "silent_night": "#weihnachten", "twinkle": "#weihnachten",
    "fur_elise": "#fürelise", "ode_to_joy": "#beethoven", "mountain_king": "#klassik", "canon": "#klassik",
    "greensleeves": "#klassik",
}
# Riesige Sammel-Hashtags helfen TikTok nicht beim Einordnen – das Video geht darin unter.
LOW_VALUE_TAGS = {"#fyp", "#foryou", "#foryoupage", "#fy", "#viral", "#fürdich", "#fürdichseite", "#trending",
                  "#xyzbca", "#explore", "#tiktok"}
MAX_TAGS = 5
# Bei diesen Arten spielt jeder Punkt/jedes Team eigene Töne – eine Melodie passt dort nicht.
SCALE_ONLY = {"polyrhythm", "color_wars", "galton"}
DEFAULT_SOUND = {"ring_escape": "bell", "escape_multiply": "glass", "growing_ball": "pluck",
                 "color_wars": "marimba", "polyrhythm": "glass", "galton": "kalimba", "spin_arena": "bell",
                 "string_art": "glass"}


# --- Texte: saubere, abwechslungsreiche Vorlagen (das kleine Sprachmodell schreibt oft holpriges Deutsch) ---
SONGS = {"fur_elise": "Für Elise", "ode_to_joy": "Ode an die Freude", "mountain_king": "In der Halle des Bergkönigs",
         "canon": "Kanon in D", "twinkle": "Morgen kommt der Weihnachtsmann", "greensleeves": "Greensleeves",
         "jingle_bells": "Jingle Bells", "silent_night": "Stille Nacht"}
XMAS = {"jingle_bells", "silent_night", "twinkle"}
CAPTIONS: dict[str, list[str]] = {
    "ring_escape": [
        "Schafft er alle {rings} Ringe? 😳 Schreib deine Schätzung in die Kommentare!",
        "{rings} Ringe, ein Ball – bei welchem Ring wird es knapp? 👀",
        "Wie lange braucht er für alle {rings} Ringe? ⏱️ Tipp jetzt!",
        "Jede Lücke kostet einen Ring 😮 Schafft er alle {rings}?",
    ],
    "escape_multiply": [
        "Jeder Ball, der entkommt, wird zu zwei 🤯 Bei welcher Zahl platzt der Ring?",
        "Aus 1 werden {max_balls} 😳 Wie lange hält der Ring durch?",
        "Ein Ball reicht für totales Chaos 🤯 Wann platzt der Ring? Tipp jetzt!",
    ],
    "growing_ball": [
        "Jeder Aufprall macht ihn größer und spielt die nächste Note 🎶 Erkennst du das Lied?",
        "Wie viele Aufpralle, bis der Kreis voll ist? 🤔 Schreib deine Zahl!",
        "Er wächst mit jedem Ton 🎶 Bei welcher Note ist Schluss?",
    ],
    "color_wars": [
        "Welche Farbe hat am Ende mehr Fläche? 👀 Wähl dein Team in den Kommentaren!",
        "Wer erobert das Feld? 🏆 Schreib deine Farbe in die Kommentare!",
        "Mal führt die eine Farbe, mal die andere – wer gewinnt am Ende? 👀 Wähl dein Team!",
    ],
    "polyrhythm": [
        "{dots} Punkte, jeder in seinem eigenen Takt – warte, bis sich alle treffen 🤯",
        "Bleib bis zum Ende: Dann treffen sich alle {dots} Punkte gleichzeitig 🎶",
        "Jeder Punkt spielt seinen eigenen Ton 🌀 Hast du bis zum Schluss geschaut?",
    ],
    "galton": [
        "In welchem Fach landen die meisten Kugeln? 🎯 Tipp jetzt, bevor die Kurve erscheint!",
        "{balls} Kugeln, reiner Zufall – und trotzdem entsteht eine perfekte Kurve 🤯",
        "Zufall oder Muster? 🤔 Schau, was {balls} Kugeln am Ende zeichnen",
    ],
    "spin_arena": [
        "Welche Nummer bleibt als Letzte im {shape}? 👀 Schreib deinen Tipp in die Kommentare!",
        "{balls} Bälle, ein drehendes {shape} – wer bleibt übrig? 🏆",
        "Wähl deine Nummer von 1 bis {balls} 👇 Bleibt sie bis zum Schluss drin?",
    ],
    "string_art": [
        "Jeder Aufprall spannt einen neuen Faden 🕸️ Wie sieht es am Ende aus?",
        "{points} Fäden, ein Ball – schau, welches Muster entsteht ✨",
        "Aus Chaos wird Kunst: Jeder Aufprall ein Faden 🎶 Bleib bis zum Ende!",
    ],
}
SONG_QUESTION = {"ring_escape": "Schafft er alle {rings} Ringe?", "escape_multiply": "Wann platzt der Ring?",
                 "growing_ball": "Wie groß wird er?", "spin_arena": "Welche Nummer bleibt übrig?",
                 "string_art": "Wie sieht das Netz am Ende aus?"}
TITLES = {
    "ring_escape": "Ring-Flucht: {rings} Ringe", "escape_multiply": "Ball-Vermehrung bis {max_balls}",
    "growing_ball": "Wachsender Ball", "color_wars": "Farben-Krieg mit {teams} Teams",
    "polyrhythm": "Polyrhythmus mit {dots} Punkten", "galton": "Galton-Brett mit {balls} Kugeln",
    "spin_arena": "Dreh-Arena: {balls} Bälle im {shape}", "string_art": "Faden-Netz mit {points} Fäden",
}


def make_text(kind: str, params: dict, music: str | None, seed: int) -> tuple[str, str]:
    """Titel und Caption aus den Vorlagen – passend zu Art, Einstellungen und Melodie."""
    rng = random.Random(seed * 31 + 7)
    values = {**params, "shape": SHAPES.get(int(params.get("sides", 6) or 6), "Vieleck")}
    song = SONGS.get(music or "")
    if song and kind in SONG_QUESTION and rng.random() < 0.45:
        tree = " 🎄" if music in XMAS else ""
        event = "Jede Flucht spielt" if kind == "escape_multiply" else "Jeder Aufprall spielt"
        caption = f"Hörst du es? 🎶 {event} die nächste Note von „{song}“. {SONG_QUESTION[kind]}{tree}"
    else:
        caption = rng.choice(CAPTIONS[kind])
    title = TITLES[kind] + (f" – {song}" if song and kind in SONG_QUESTION else "")
    return title.format(**values), caption.format(**values)


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


FOREIGN_WORDS = {  # eindeutige Wörter, die nur zu einer Animationsart passen
    "ring_escape": ["ringe", "ring-flucht"], "escape_multiply": ["zu zwei", "verdoppel", "vermehr"],
    "growing_ball": ["wächst", "wachsend", "wird größer"], "color_wars": ["farbe gewinnt", "dein team", "farben-krieg"],
    "polyrhythm": ["polyrhythm", "treffen sich", "alle treffen"], "galton": ["glockenkurve", "galton"],
    "spin_arena": ["welche nummer", "dreh-arena"], "string_art": ["faden", "fäden"],
}


SHAPES = {3: "Dreieck", 4: "Viereck", 5: "Fünfeck", 6: "Sechseck", 7: "Siebeneck", 8: "Achteck"}
SHAPE_WORDS = r"\b(dreieck|viereck|quadrat|fünfeck|sechseck|siebeneck|achteck|hexagon|pentagon|oktagon|vieleck)\b"


def _foreign_text(kind: str, text: str) -> bool:
    """True, wenn der Text klar zu einer anderen Animationsart gehört (und nicht zu dieser)."""
    low = text.lower()
    own = any(w in low for w in FOREIGN_WORDS.get(kind, []))
    other = any(w in low for k, words in FOREIGN_WORDS.items() if k != kind for w in words)
    labels = any(spec["label"].lower() in low for k, spec in TYPES.items() if k != kind)
    return labels or (other and not own)


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


def pick_hashtags(suggested, kind: str, music: str | None) -> list[str]:
    """3-5 Hashtags: Nische zuerst, dann Lied/Saison, dann passende Vorschläge der KI."""
    spec = TYPES[kind]["tags"]
    ki = [str(t).strip().replace(" ", "") for t in (suggested or []) if str(t).strip()]
    ki = [t if t.startswith("#") else f"#{t}" for t in ki]
    song = [MELODY_TAGS[music]] if music in MELODY_TAGS else []
    out: list[str] = []
    for t in spec[:3] + song + ki + spec[3:]:
        low = t.lower()
        if low in LOW_VALUE_TAGS or low in (x.lower() for x in out) or len(t) < 3:
            continue
        out.append(t)
        if len(out) >= MAX_TAGS:
            break
    return out


def normalize_concept(raw: dict | None, force_type: str | None = None, rng: random.Random | None = None,
                      randomize: bool = False, ki_text: bool = False) -> dict:
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

    caption = re.sub(r"\s*#[\w\u00c0-\u017f]+", "", str(raw.get("caption") or "")).strip()  # Hashtags kommen separat
    title = str(raw.get("title") or "").strip()
    if not ki_text or _foreign_text(kind, f"{title} {caption}") or "NEUE" in caption or "NEUER" in title:
        title, caption = make_text(kind, params, music, seed)  # sauberes Deutsch aus den Vorlagen
    caption = caption or spec["caption"].format(**params)
    title = title or caption.split("?")[0][:80]
    if kind == "spin_arena":  # die Form im Text muss zur Animation passen (7 Seiten = Siebeneck)
        shape = SHAPES.get(int(params.get("sides", 6)), "Vieleck")
        caption, title = (re.sub(SHAPE_WORDS, shape, t, flags=re.I) for t in (caption, title))
    tags = pick_hashtags(raw.get("hashtags"), kind, music)
    music_label = MELODY_LABELS.get(music) or SCALE_LABELS.get(music, music)
    return {
        "type": kind, "label": spec["label"], "params": params, "palette": palette, "music": music,
        "sound": sound, "duration": duration, "seed": seed,
        "title": title[:100], "caption": caption[:2000], "hashtags": tags,
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
