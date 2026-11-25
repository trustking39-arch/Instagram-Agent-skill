"""Webserver für Twilio-Rückantworten (SMS + Sprache) und für Video-Dateien.

Instagram lädt Videos nur von einer öffentlichen URL. Dieser Server stellt die
fertigen Videos unter /media/<datei> bereit. Mach ihn über einen Tunnel
(z. B. `jarvis tunnel` oder `cloudflared tunnel --url http://localhost:8787`)
öffentlich und trage die URL in config.yaml unter notify.public_base_url ein.
"""

import hashlib
import hmac
import logging
import time
from xml.sax.saxutils import escape

from fastapi import FastAPI, HTTPException, Request

from content_crew.commands import handle_owner_message
from content_crew.config import Config
from content_crew.db import DB

log = logging.getLogger(__name__)

COOKIE = "jarvis_session"
MAX_FAILURES = 10
LOCK_SECONDS = 15 * 60


def create_app(cfg: Config, db: DB):
    from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

    from content_crew.dashboard import render as render_dashboard
    from content_crew.dashboard import render_login

    app = FastAPI(title="Content Crew Webhooks")
    owner = cfg.env("OWNER_PHONE_NUMBER")
    token = cfg.env("TWILIO_AUTH_TOKEN")
    media_dir = (cfg.data_dir / "videos").resolve()

    async def verified_form(request: Request) -> dict:
        form = dict(await request.form())
        if token:
            from twilio.request_validator import RequestValidator

            base = cfg["notify"].get("public_base_url", "").rstrip("/")
            url = f"{base}{request.url.path}" if base else str(request.url)
            signature = request.headers.get("X-Twilio-Signature", "")
            if not RequestValidator(token).validate(url, form, signature):
                raise HTTPException(status_code=403, detail="Ungültige Twilio-Signatur")
        if not owner or form.get("From") != owner:  # ohne eingetragene Besitzer-Nummer nimmt niemand Befehle an
            raise HTTPException(status_code=403, detail="Unbekannter Absender")
        return form

    def twiml(body: str) -> Response:
        return Response(content=f"<Response>{body}</Response>", media_type="application/xml")

    @app.post("/sms")
    async def sms(request: Request):
        form = await verified_form(request)
        reply = handle_owner_message(db, form.get("Body", ""), channel="sms")
        return twiml(f"<Message>{escape(reply)}</Message>")

    @app.post("/voice/answer")
    async def voice_answer(request: Request):
        form = await verified_form(request)
        speech = form.get("SpeechResult", "").strip()
        if not speech:
            return twiml('<Say language="de-DE">Ich habe nichts verstanden. Schreib mir gern eine SMS.</Say>')
        reply = handle_owner_message(db, speech, channel="voice")
        return twiml(f'<Say language="de-DE">{escape(reply)}</Say>')

    @app.get("/media/{name}")
    def media(name: str):
        path = (media_dir / name).resolve()
        if path.parent != media_dir or not path.is_file() or path.suffix != ".mp4":
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="video/mp4")

    @app.get("/health")
    def health():
        return {"ok": True}

    # --- Übersichtsseite: am PC frei, übers Internet (Handy) nur mit Passwort ---
    password = cfg.env("DASHBOARD_PASSWORD")
    session_value = hmac.new(password.encode(), b"jarvis-dashboard-v1", hashlib.sha256).hexdigest() if password else ""
    failures: dict[str, list[float]] = {}

    def is_local(request: Request) -> bool:
        via_tunnel = any(h in request.headers for h in ("cf-connecting-ip", "cf-ray", "x-forwarded-for"))
        client = request.client.host if request.client else ""
        return not via_tunnel and client in ("127.0.0.1", "::1", "localhost", "testclient")

    def allowed(request: Request) -> bool:
        if is_local(request):
            return True
        cookie = request.cookies.get(COOKIE, "")
        return bool(session_value) and hmac.compare_digest(cookie, session_value)

    def remote_ip(request: Request) -> str:
        return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")

    def locked(ip: str) -> bool:
        recent = [t for t in failures.get(ip, []) if time.time() - t < LOCK_SECONDS]
        failures[ip] = recent
        return len(recent) >= MAX_FAILURES

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        if not allowed(request):
            return RedirectResponse("/login", status_code=303)
        return HTMLResponse(render_dashboard(cfg, db))

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, error: str = ""):
        return HTMLResponse(render_login(error, configured=bool(password)))

    @app.post("/login")
    async def login(request: Request):
        ip = remote_ip(request)
        if not password:
            return RedirectResponse("/login", status_code=303)
        if locked(ip):
            return RedirectResponse("/login?error=gesperrt", status_code=303)
        form = dict(await request.form())
        if not hmac.compare_digest(str(form.get("password", "")), password):
            failures.setdefault(ip, []).append(time.time())
            log.warning("Falsches Übersichts-Passwort von %s", ip)
            return RedirectResponse("/login?error=falsch", status_code=303)
        failures.pop(ip, None)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(COOKIE, session_value, max_age=30 * 24 * 3600, httponly=True,
                            secure=not is_local(request), samesite="lax")
        return response

    @app.post("/logout")
    def logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE)
        return response

    @app.post("/dashboard/cmd")
    async def dashboard_cmd(request: Request):
        if not allowed(request):
            raise HTTPException(status_code=403)
        form = dict(await request.form())
        text = str(form.get("text", "")).strip()
        if text:
            handle_owner_message(db, text, channel="dashboard")
        return RedirectResponse("/", status_code=303)

    return app
