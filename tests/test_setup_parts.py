import hashlib
import os
import urllib.parse

from content_crew import auth
from content_crew.envfile import set_env_values
from content_crew.tunnel import find_url
from content_crew.workers.stock import pick_file
from content_crew.workers.writer import normalize_script


def test_set_env_values_keeps_other_lines(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# Kommentar\nA=1\nB=\n")
    set_env_values({"B": "neu", "C": "3"}, env)
    assert env.read_text() == "# Kommentar\nA=1\nB=neu\nC=3\n"
    assert os.environ["C"] == "3"
    monkeypatch.delenv("B")
    monkeypatch.delenv("C")


def test_find_tunnel_url():
    line = "2026 INF |  https://wild-river-abc-12.trycloudflare.com                 |"
    assert find_url(line) == "https://wild-river-abc-12.trycloudflare.com"
    assert find_url("nichts hier") is None


def test_pick_portrait_file():
    videos = [
        {"id": 1, "video_files": [{"width": 1920, "height": 1080, "link": "quer"}]},
        {"id": 2, "video_files": [{"width": 1080, "height": 1920, "link": "hd"},
                                  {"width": 2160, "height": 3840, "link": "4k"}]},
    ]
    assert pick_file(videos) == (2, "hd")
    assert pick_file([videos[0]]) is None


def test_scene_visual_is_kept():
    s = normalize_script({"scenes": [{"text": "Los", "visual": "man running"}, {"text": "Ende"}]})
    assert s["scenes"] == [{"text": "Los", "visual": "man running"}, {"text": "Ende"}]


def test_tiktok_auth_url_uses_hex_challenge():
    url = auth.tiktok_auth_url("key", "http://localhost:8788/callback/", "st", "verifier")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["code_challenge"] == [hashlib.sha256(b"verifier").hexdigest()]
    assert q["redirect_uri"] == ["http://localhost:8788/callback/"]


def test_instagram_setup_finds_business_account(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []

    class Resp:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    def fake_get(url, params, timeout):
        calls.append(url)
        if url.endswith("/oauth/access_token"):
            return Resp({"access_token": "LANG"})
        assert params["access_token"] == "LANG"
        return Resp({"data": [
            {"name": "Ohne IG", "access_token": "x"},
            {"name": "Meine Seite", "access_token": "SEITE",
             "instagram_business_account": {"id": "1789", "username": "ich"}},
        ]})

    monkeypatch.setattr(auth.requests, "get", fake_get)
    info = auth.instagram_setup("KURZ", "appid", "secret")
    assert info["username"] == "ich"
    env = (tmp_path / ".env").read_text()
    assert "INSTAGRAM_USER_ID=1789" in env and "INSTAGRAM_ACCESS_TOKEN=SEITE" in env
    for key in ("INSTAGRAM_USER_ID", "INSTAGRAM_ACCESS_TOKEN"):
        monkeypatch.delenv(key)
