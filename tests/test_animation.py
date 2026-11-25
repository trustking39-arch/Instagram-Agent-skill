import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from content_crew.animation import TYPES, normalize_concept, random_concept, type_for
from content_crew.animation.audio import Note, render_audio
from content_crew.boss import Boss
from content_crew.config import load_config
from content_crew.db import DB
from content_crew.notify import Notifier

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")
skia = pytest.importorskip("skia")

SMALL = {"width": 180, "height": 320, "fps": 15, "bloom": 0.5, "crf": 30, "preset": "ultrafast"}


def has_audio(path: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True).stdout.split()
    return "audio" in out and "video" in out


def test_normalize_concept_repairs_ki_output():
    c = normalize_concept({"type": "Ring-Flucht", "params": {"rings": 500, "pattern": "quatsch"},
                           "music": "Für Elise", "palette": "NEON", "duration": 300,
                           "hashtags": ["fyp", "#viral", "ballspiel"]})
    assert c["type"] == "ring_escape" and c["params"]["rings"] == 50 and c["params"]["pattern"] == "spiral"
    assert c["music"] == "fur_elise" and c["palette"] == "neon" and c["duration"] == 60
    assert c["hashtags"] == ["#satisfying", "#simulation", "#bouncingball", "#fürelise", "#ballspiel"]
    assert c["caption"] and c["title"]
    # Polyrhythmus spielt eigene Töne pro Punkt: Melodien werden durch eine Tonleiter ersetzt
    assert normalize_concept({"music": "fur_elise"}, force_type="polyrhythm")["music"] not in ("fur_elise",)
    assert normalize_concept("kaputt")["type"] in TYPES
    assert type_for("[Farben-Krieg] Idee") == "color_wars"


def test_audio_has_right_length(tmp_path):
    wav = tmp_path / "a.wav"
    render_audio([Note(0.1, 60), Note(0.5, 64, kind="tick"), Note(1.0, 0, kind="boom", accent=True)], 2.0, wav,
                 pad_root=48)
    import wave

    with wave.open(str(wav)) as wf:
        assert wf.getnchannels() == 2 and abs(wf.getnframes() / wf.getframerate() - 2.0) < 0.01


@pytest.mark.parametrize("kind", list(TYPES))
def test_every_animation_renders_with_sound_and_climax(kind, tmp_path):
    from content_crew.animation import render

    concept = random_concept(kind, random.Random(3), duration=20)
    info = render(concept, tmp_path / "v.mp4", **SMALL)
    assert (tmp_path / "v.mp4").stat().st_size > 10_000 and has_audio(tmp_path / "v.mp4")
    assert 15 <= info["duration"] <= 40, info
    assert info["notes"] >= 8 and info["motion"] > 0.2 and info["climax_at"] is not None
    if kind in ("ring_escape", "growing_ball", "escape_multiply"):  # Höhepunkt wurde auf die Länge abgestimmt
        assert abs(info["climax_at"] - 18) < 8, info


class DesignerLLM:
    """Spielt Jarvis und den Designer."""

    def __init__(self, scores=(5, 8)):
        self.scores = list(scores)
        self.calls = []

    def chat_json(self, system, user, **kw):
        self.calls.append(user)
        if "Plane genau" in user:
            return {"ideas": [{"type": "growing_ball", "idea": "Ball wächst zu Für Elise", "instructions": "neon"}]}
        if "Bewerte" in user:
            return {"score": self.scores.pop(0) if self.scores else 9, "feedback": "Caption braucht eine Frage"}
        if "Analysiere" in user:
            return {"patterns": ["bekannte Melodie"], "hooks": [], "formats": [], "avoid": []}
        if "Auftrag vom Chef" in user:
            return {"type": "growing_ball", "params": {"gravity": 1.2}, "palette": "neon", "music": "Für Elise",
                    "sound": "bell", "duration": 20, "title": "Ball wächst", "caption": "Erkennst du das Lied? 🎶",
                    "hashtags": ["#satisfying"]}
        return {}


@pytest.fixture
def anim_cfg(tmp_path, monkeypatch):
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "OWNER_PHONE_NUMBER"):
        monkeypatch.delenv(var, raising=False)
    c = load_config(tmp_path / "missing.yaml")
    c["data_dir"] = str(tmp_path / "data")
    c["platforms"] = []
    c["video"].update(style="animation", width=SMALL["width"], height=SMALL["height"])
    c["animation"].update(fps=SMALL["fps"], preset="ultrafast", crf=30)
    c["boss"]["auto_publish"] = False
    return c


def test_jarvis_cycle_makes_animation_after_revision(anim_cfg):
    db = DB(anim_cfg.data_dir / "crew.db")
    llm = DesignerLLM(scores=(5, 8))
    boss = Boss(anim_cfg, db, llm, Notifier(anim_cfg, db), platforms={})
    created = boss.run_cycle()
    assert len(created) == 1
    video = db.video(created[0])
    assert video["status"] == "awaiting_approval" and Path(video["path"]).exists()
    script = video["script"]
    assert script["type"] == "growing_ball" and script["music"] == "fur_elise" and script["palette"] == "neon"
    assert script["render"]["notes"] > 0 and not script["render"]["problems"]
    assert any("Kritik vom Chef" in c for c in llm.calls), "Konzept wurde nach Kritik überarbeitet"
    assert db.activity("producer")["text"].startswith("Video #")


def test_batch_uses_each_animation_type(anim_cfg):
    db = DB(anim_cfg.data_dir / "crew.db")
    boss = Boss(anim_cfg, db, DesignerLLM(scores=(9, 9, 9)), Notifier(anim_cfg, db), platforms={})
    created = boss.run_batch(["Farben-Krieg", "Polyrhythmus"], 2)
    assert [db.video(v)["script"]["type"] for v in created] == ["color_wars", "polyrhythm"]
    assert all(db.video(v)["status"] == "awaiting_approval" for v in created)
    assert boss.next_animation_type() not in ("color_wars", "polyrhythm")
    assert json.loads(json.dumps(db.video(created[0])["script"]))["hook"].startswith("Farben-Krieg")


def test_endless_batch_stops_on_owner_stop(anim_cfg):
    from content_crew.commands import handle_owner_message

    db = DB(anim_cfg.data_dir / "crew.db")
    boss = Boss(anim_cfg, db, DesignerLLM(scores=(9, 9, 9)), Notifier(anim_cfg, db), platforms={})
    original = boss.create_video

    def make_and_maybe_stop(*a, **kw):
        vid = original(*a, **kw)
        if len(db.videos(limit=10)) >= 2:
            handle_owner_message(db, "STOP")
        return vid

    boss.create_video = make_and_maybe_stop
    created = boss.run_batch(["Faden-Netz", "Galton-Brett"], 0)
    assert [db.video(v)["script"]["type"] for v in created] == ["string_art", "galton"]
    assert "pausiert" in db.activity("jarvis")["text"]


def test_copied_or_foreign_caption_is_replaced():
    c = normalize_concept({"title": "Ring-Flucht", "caption": "Schafft er alle 30 Ringe? 😳 Schreib deine Schätzung!"},
                          force_type="polyrhythm")
    assert "Ringe" not in c["caption"] and c["title"] != "Ring-Flucht"
    own = normalize_concept({"title": "Goldene Kugel", "caption": "Ganz einfach – erkennst du das Lied? 🎶"},
                            force_type="growing_ball", ki_text=True)
    assert own["caption"].startswith("Ganz einfach")
    tpl = normalize_concept({"caption": "Schafft es der Ring 150 entkommen?", "params": {"sides": 7}},
                            force_type="spin_arena")  # Standard: geprüfte Vorlagen statt KI-Deutsch
    assert "entkommen" not in tpl["caption"] and "Siebeneck" in tpl["title"]


def test_polyrhythm_differs_between_videos():
    from content_crew.animation.engine import Ctx
    from content_crew.animation.palettes import PALETTES
    from content_crew.animation.scenes import SCENES

    def cycles(seed):
        ctx = Ctx(180, 320, 15, 30, seed, PALETTES["neon"], "pentatonic")
        return SCENES["polyrhythm"](ctx, {"layout": "orbits", "dots": 21, "speed": 0.3}, headless=True).cycles

    assert len({tuple(cycles(s)) for s in range(1, 9)}) > 1


def test_jarvis_varies_repeated_concepts(anim_cfg):
    db = DB(anim_cfg.data_dir / "crew.db")
    boss = Boss(anim_cfg, db, DesignerLLM(), Notifier(anim_cfg, db), platforms={})
    first = normalize_concept({"type": "spin_arena", "palette": "fire", "music": "canon",
                               "params": {"sides": 7, "balls": 10, "spin": 0.9, "gravity": 1.0}})
    db.add_video("x", first, 8)
    again = boss.vary(normalize_concept({**first, "seed": 4242}))
    assert again["palette"] != "fire" and again["music"] != "canon"
    assert again["params"] != first["params"]
    assert "Siebeneck" not in again["title"] or again["params"]["sides"] == 7


class DeadLLM:
    def chat_json(self, *a, **kw):
        raise ConnectionError("Jarvis-Server nicht erreichbar")


def test_batch_keeps_producing_without_language_model(anim_cfg):
    db = DB(anim_cfg.data_dir / "crew.db")
    boss = Boss(anim_cfg, db, DeadLLM(), Notifier(anim_cfg, db), platforms={})
    created = boss.run_batch(["Galton-Brett"], 1)
    assert len(created) == 1 and db.video(created[0])["script"]["type"] == "galton"
