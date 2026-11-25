"""Webserver für Twilio-Rückantworten (SMS + Sprache) und für Video-Dateien.

Instagram lädt Videos nur von einer öffentlichen URL. Dieser Server stellt die
fertigen Videos unter /media/<datei> bereit. Mach ihn über einen Tunnel
(z. B. `jarvis tunnel` oder `cloudflared tunnel --url http://localhost:8787`)
öffentlich und trage die URL in config.yaml unter notify.public_base_url ein.
"""

import logging
from xml.sax.saxutils import escape

from fastapi import FastAPI, HTTPException, Request

from content_crew.commands import handle_owner_message
from content_crew.config import Config
from content_crew.db import DB

log = logging.getLogger(__name__)


def create_app(cfg: Config, db: DB):
    from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

    from content_crew.dashboard import render as render_dashboard

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

    # --- Übersichtsseite: nur direkt auf deinem PC, nie über den öffentlichen Tunnel ---
    def local_only(request: Request) -> None:
        via_tunnel = any(h in request.headers for h in ("cf-connecting-ip", "cf-ray", "x-forwarded-for"))
        client = request.client.host if request.client else ""
        if via_tunnel or client not in ("127.0.0.1", "::1", "localhost", "testclient"):
            raise HTTPException(status_code=404)

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        local_only(request)
        return HTMLResponse(render_dashboard(cfg, db))

    @app.post("/dashboard/cmd")
    async def dashboard_cmd(request: Request):
        local_only(request)
        form = dict(await request.form())
        text = str(form.get("text", "")).strip()
        if text:
            handle_owner_message(db, text, channel="dashboard")
        return RedirectResponse("/", status_code=303)

    return app
