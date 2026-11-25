"""Einmalige Anmeldung bei Instagram und TikTok; Tokens landen automatisch in .env."""

from __future__ import annotations

import hashlib
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from content_crew.envfile import set_env_values

GRAPH = "https://graph.facebook.com/v21.0"
TIKTOK_AUTH = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_SCOPES = "user.info.basic,video.publish,video.list"


# --- Instagram -------------------------------------------------------------
def instagram_setup(user_token: str, app_id: str = "", app_secret: str = "") -> dict:
    """Aus einem Token des Graph API Explorers einen dauerhaften Seiten-Token machen
    und die Instagram-Business-ID automatisch finden."""
    token = user_token
    if app_id and app_secret:
        r = requests.get(f"{GRAPH}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": app_id,
            "client_secret": app_secret, "fb_exchange_token": user_token,
        }, timeout=30)
        r.raise_for_status()
        token = r.json()["access_token"]
    r = requests.get(f"{GRAPH}/me/accounts", params={
        "fields": "name,access_token,instagram_business_account{id,username}", "access_token": token,
    }, timeout=30)
    r.raise_for_status()
    for page in r.json().get("data", []):
        ig = page.get("instagram_business_account")
        if ig:
            values = {"INSTAGRAM_USER_ID": ig["id"], "INSTAGRAM_ACCESS_TOKEN": page["access_token"]}
            set_env_values(values)
            return {**values, "username": ig.get("username", ""), "page": page.get("name", "")}
    raise RuntimeError(
        "Keine Facebook-Seite mit verbundenem Instagram-Business-/Creator-Konto gefunden. "
        "Verbinde dein Instagram-Konto in den Instagram-Einstellungen mit einer Facebook-Seite."
    )


# --- TikTok ----------------------------------------------------------------
def tiktok_auth_url(client_key: str, redirect_uri: str, state: str, verifier: str) -> str:
    challenge = hashlib.sha256(verifier.encode()).hexdigest()  # TikTok erwartet Hex statt Base64
    return TIKTOK_AUTH + "?" + urllib.parse.urlencode({
        "client_key": client_key, "scope": TIKTOK_SCOPES, "response_type": "code",
        "redirect_uri": redirect_uri, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })


def tiktok_exchange(client_key: str, client_secret: str, code: str, redirect_uri: str, verifier: str) -> dict:
    r = requests.post(TIKTOK_TOKEN, data={
        "client_key": client_key, "client_secret": client_secret, "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri, "code_verifier": verifier,
    }, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"TikTok-Anmeldung fehlgeschlagen: {data}")
    values = {"TIKTOK_ACCESS_TOKEN": data["access_token"], "TIKTOK_REFRESH_TOKEN": data.get("refresh_token", "")}
    set_env_values(values)
    return values


def tiktok_login(client_key: str, client_secret: str, redirect_uri: str, timeout: int = 300) -> dict:
    """Browser-Login. Die redirect_uri (Standard http://localhost:8788/callback/) muss in
    deiner TikTok-App unter Login Kit eingetragen sein."""
    parsed = urllib.parse.urlparse(redirect_uri)
    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(48)
    result: dict = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [""])[0] == state and "code" in query:
                result["code"] = query["code"][0]
                body = "TikTok verbunden. Du kannst dieses Fenster schliessen."
            else:
                result["error"] = query.get("error_description", query.get("error", ["unbekannt"]))[0]
                body = f"Fehler: {result['error']}"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())
            done.set()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", parsed.port or 80), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = tiktok_auth_url(client_key, redirect_uri, state, verifier)
    print("Öffne diesen Link im Browser und melde dich bei TikTok an:\n\n" + url + "\n")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    done.wait(timeout)
    server.shutdown()
    if "code" not in result:
        raise RuntimeError(f"TikTok-Anmeldung abgebrochen: {result.get('error', 'Zeit abgelaufen')}")
    return tiktok_exchange(client_key, client_secret, result["code"], redirect_uri, verifier)
