import json
import shutil
from pathlib import Path

import pytest

from content_crew.boss import Boss
from content_crew.commands import handle_owner_message
from content_crew.config import load_config
from content_crew.db import DB
from content_crew.llm import extract_json
from content_crew.notify import Notifier
from content_crew.platforms.base import Platform, PlatformError
from content_crew.workers.analyst import is_viral
from content_crew.workers.producer import VideoProducer
from content_crew.workers.writer import normalize_script


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "OWNER_PHONE_NUMBER"):
        monkeypatch.delenv(var, raising=False)
    c = load_config(tmp_path / "missing.yaml")
    c["data_dir"] = str(tmp_path / "data")
    c["video"]["tts"] = "none"
    c["platforms"] = []
    return c


@pytest.fixture
def db(cfg):
    return DB(cfg.data_dir / "crew.db")


class FakeLLM:
    """Antwortet je nach Aufgabe wie Jarvis es tun würde."""

    def __init__(self, scores=(5, 8)):
        self.scores = list(scores)
        self.calls = []

    def chat_json(self, system, user, **kw):
        self.calls.append(user)
        if "Plane genau" in user:
            return {"ideas": [{"idea": "3 Morgenroutinen", "why": "x", "instructions": "kurz"}],
                    "question_for_owner": "Soll ich mehr Humor einbauen?"}
        if "Bewerte" in user:
            return {"score": self.scores.pop(0) if self.scores else 9, "feedback": "Hook stärker machen"}
        if "Analysiere" in user:
            return {"patterns": ["Listen"], "hooks": ["Du machst das falsch"], "topics": [], "formats": [], "avoid": []}
        if "echten Zahlen" in user:
            return {"learnings": ["Fragen als Hook"], "next_focus": "Routinen", "summary_for_owner": "Läuft gut."}
        return {"title": "3 Routinen", "hook": "Stopp!", "scenes": [{"text": "Stopp! Das ändert deinen Morgen."},
                {"text": "Folge für mehr."}], "caption": "Morgen", "hashtags": ["motivation", "#fyp"]}


class FakePlatform(Platform):
    name = "fake"

    def __init__(self, cfg, views=50000):
        super().__init__(cfg)
        self.views = views
        self.uploaded = []

    def trends(self, niche, limit=10):
        return [{"platform": "fake", "title": "Top Video", "views": 1, "likes": 1, "comments": 1, "url": ""}]

    def upload(self, video, title, description, tags, public_url=""):
        assert video.exists()
        self.uploaded.append(title)
        return f"post{len(self.uploaded)}"

    def stats(self, post_id):
        return {"views": self.views, "likes": 10, "comments": 1, "shares": 0}


def test_extract_json_handles_think_and_fences():
    text = '<think>{"nope": 1}</think>Klar!\n```json\n{"a": [1, 2]}\n```'
    assert extract_json(text) == {"a": [1, 2]}
    with pytest.raises(ValueError):
        extract_json("kein json")


def test_normalize_script_fills_gaps():
    s = normalize_script({"scenes": ["Hallo Welt", {"text": " "}], "hashtags": ["fyp", "#ok"]})
    assert s["scenes"] == [{"text": "Hallo Welt"}]
    assert s["hashtags"] == ["#fyp", "#ok"]
    assert s["title"] == "Hallo Welt"


def test_viral_rule():
    assert is_viral(40000, [1000, 2000, 3000], 3.0, 10000)
    assert not is_viral(5000, [1000], 3.0, 10000)
    assert not is_viral(None, [], 3.0, 10000)


def test_owner_commands(db):
    assert "pausiert" in handle_owner_message(db, "stop")
    assert db.paused
    handle_owner_message(db, "START")
    assert not db.paused
    vid = db.add_video("x", {"title": "t", "scenes": []}, 8, status="awaiting_approval")
    assert "freigegeben" in handle_owner_message(db, f"ok {vid}")
    handle_owner_message(db, "Mach mehr Videos über Fitness")
    texts = [m["text"] for m in db.take_inbox()]
    assert texts == [f"APPROVE {vid}", "Mach mehr Videos über Fitness"]


def test_call_twiml_gathers_speech_when_public_url(cfg, db):
    cfg["notify"]["public_base_url"] = "https://beispiel.de"
    xml = Notifier(cfg, db).call_twiml("Video <viral> & toll", ask=True)
    assert '<Gather input="speech"' in xml and "https://beispiel.de/voice/answer" in xml
    assert "&lt;viral&gt; &amp; toll" in xml


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")
def test_full_cycle_with_revision_publish_and_viral_call(cfg, db):
    platform = FakePlatform(cfg)
    llm = FakeLLM(scores=(5, 8))
    boss = Boss(cfg, db, llm, Notifier(cfg, db), platforms={"fake": platform}, producer=VideoProducer(cfg))

    created = boss.run_cycle()
    assert len(created) == 1
    video = db.video(created[0])
    assert video["status"] == "published"
    assert video["platform_ids"] == {"fake": "post1"}
    assert Path(video["path"]).stat().st_size > 1000
    assert any("Kritik vom Chef" in c for c in llm.calls), "Skript wurde nach Kritik überarbeitet"

    outbox = db.conn.execute("SELECT kind, channel FROM outbox").fetchall()
    kinds = {(r["kind"], r["channel"]) for r in outbox}
    assert ("question", "sms") in kinds and ("published", "sms") in kinds

    # Nächster Durchlauf: Statistiken -> viral -> Anruf + SMS, nur einmal
    boss.cfg["boss"]["videos_per_cycle"] = 0
    boss.run_cycle()
    boss.run_cycle()
    viral = db.conn.execute("SELECT channel FROM outbox WHERE kind='viral'").fetchall()
    assert sorted(r["channel"] for r in viral) == ["call", "sms"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")
def test_call_when_cycle_done(cfg, db):
    assert "rufe dich an" in handle_owner_message(db, "Ruf mich an")
    boss = Boss(cfg, db, FakeLLM(scores=(9,)), Notifier(cfg, db), platforms={"fake": FakePlatform(cfg)},
                producer=VideoProducer(cfg))
    boss.run_cycle()
    calls = db.conn.execute("SELECT text FROM outbox WHERE kind='done' AND channel='call'").fetchall()
    assert len(calls) == 1 and "Mein Team ist fertig" in calls[0]["text"] and "3 Routinen" in calls[0]["text"]
    boss.run_cycle()  # nur einmal anrufen
    assert db.conn.execute("SELECT COUNT(*) c FROM outbox WHERE kind='done'").fetchone()["c"] == 1


def test_blocked_error_calls_once_per_day(cfg, db):
    boss = Boss(cfg, db, FakeLLM(), Notifier(cfg, db), platforms={})
    err = PlatformError("YouTube-Login abgelaufen", blocked=True)
    boss.report_errors([err], "Upload")
    boss.report_errors([err], "Upload")
    calls = db.conn.execute("SELECT COUNT(*) c FROM outbox WHERE kind='blocked' AND channel='call'").fetchone()
    assert calls["c"] == 1


def test_paused_boss_does_nothing(cfg, db):
    db.set_state("paused", "1")
    llm = FakeLLM()
    assert Boss(cfg, db, llm, Notifier(cfg, db), platforms={}).run_cycle() == []
    assert llm.calls == []


def test_webhook_rejects_strangers_and_accepts_owner(cfg, db, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from content_crew.webhooks import create_app

    monkeypatch.setenv("OWNER_PHONE_NUMBER", "+4917000000")
    client = TestClient(create_app(cfg, db))
    assert client.post("/sms", data={"From": "+491111", "Body": "STOP"}).status_code == 403
    r = client.post("/sms", data={"From": "+4917000000", "Body": "STATUS"})
    assert r.status_code == 200 and "Jarvis ist aktiv" in r.text
    assert client.get("/media/../crew.db").status_code == 404
    json.dumps(r.text)


def test_dashboard_shows_team_and_is_local_only(cfg, db, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from content_crew.webhooks import create_app

    db.add_video("Idee", {"title": "Mein <Test> Video", "scenes": []}, 8, status="awaiting_approval")
    db.set_activity("writer", "schreibt gerade")
    client = TestClient(create_app(cfg, db))
    page = client.get("/").text
    assert "Skript-Autor" in page and "schreibt gerade" in page
    assert "Mein &lt;Test&gt; Video" in page and "Hochladen" in page
    assert client.get("/", headers={"cf-connecting-ip": "1.2.3.4"}, follow_redirects=False).status_code == 303
    r = client.post("/dashboard/cmd", data={"text": "STOP"}, follow_redirects=False)
    assert r.status_code == 303 and db.paused
    assert client.post("/dashboard/cmd", data={"text": "START"}, headers={"x-forwarded-for": "1.2.3.4"}).status_code == 403


def test_dashboard_from_phone_needs_password(cfg, db, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from content_crew import webhooks

    monkeypatch.setenv("DASHBOARD_PASSWORD", "richtig-geheim")
    client = TestClient(webhooks.create_app(cfg, db))
    phone = {"cf-connecting-ip": "5.6.7.8"}
    r = client.get("/", headers=phone, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert "Anmelden" in client.get("/login", headers=phone).text
    bad = client.post("/login", data={"password": "falsch"}, headers=phone, follow_redirects=False)
    assert "error=falsch" in bad.headers["location"]
    assert client.post("/dashboard/cmd", data={"text": "STOP"}, headers=phone).status_code == 403
    ok = client.post("/login", data={"password": "richtig-geheim"}, headers=phone, follow_redirects=False)
    assert ok.headers["location"] == "/" and "jarvis_session" in ok.headers["set-cookie"]
    assert "Secure" in ok.headers["set-cookie"] and "HttpOnly" in ok.headers["set-cookie"]
    client.cookies.set("jarvis_session", ok.cookies.get("jarvis_session") or ok.headers["set-cookie"].split(";")[0].split("=", 1)[1])
    assert "Skript-Autor" in client.get("/", headers=phone).text
    client.post("/dashboard/cmd", data={"text": "STOP"}, headers=phone)
    assert db.paused


def test_login_locks_after_many_failures(cfg, db, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from content_crew import webhooks

    monkeypatch.setenv("DASHBOARD_PASSWORD", "richtig-geheim")
    client = TestClient(webhooks.create_app(cfg, db))
    phone = {"cf-connecting-ip": "9.9.9.9"}
    for _ in range(webhooks.MAX_FAILURES):
        client.post("/login", data={"password": "x"}, headers=phone, follow_redirects=False)
    r = client.post("/login", data={"password": "richtig-geheim"}, headers=phone, follow_redirects=False)
    assert "error=gesperrt" in r.headers["location"]


def test_webhook_rejects_everyone_without_owner_number(cfg, db, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from content_crew.webhooks import create_app

    monkeypatch.delenv("OWNER_PHONE_NUMBER", raising=False)
    client = TestClient(create_app(cfg, db))
    assert client.post("/sms", data={"From": "+4900", "Body": "STOP"}).status_code == 403
    assert not db.paused
