"""Jarvis meldet sich beim Besitzer: SMS und Sprachanrufe über Twilio."""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from content_crew.config import Config
from content_crew.db import DB

log = logging.getLogger(__name__)

SMS_LIMIT = 1500


class Notifier:
    def __init__(self, cfg: Config, db: DB):
        self.cfg = cfg
        self.db = db
        self.sid = cfg.env("TWILIO_ACCOUNT_SID")
        self.token = cfg.env("TWILIO_AUTH_TOKEN")
        self.from_number = cfg.env("TWILIO_PHONE_NUMBER")
        self.owner = cfg.env("OWNER_PHONE_NUMBER")
        self._client = None

    @property
    def configured(self) -> bool:
        return all([self.sid, self.token, self.from_number, self.owner])

    def _twilio(self):
        if self._client is None:
            from twilio.rest import Client

            self._client = Client(self.sid, self.token)
        return self._client

    def _live(self) -> bool:
        return self.configured and not self.cfg.dry_run

    # ------------------------------------------------------------------
    def sms(self, text: str, kind: str = "info") -> bool:
        text = text[:SMS_LIMIT]
        sent = False
        if self._live():
            try:
                self._twilio().messages.create(to=self.owner, from_=self.from_number, body=text)
                sent = True
            except Exception:  # noqa: BLE001
                log.exception("SMS konnte nicht gesendet werden")
        log.info("[SMS %s%s] %s", kind, "" if sent else " – nicht gesendet", text)
        self.db.add_outbox(kind, "sms", text, sent)
        return sent

    def call_twiml(self, text: str, ask: bool) -> str:
        lang = "de-DE" if self.cfg.get("language", "de") == "de" else "en-US"
        say = f'<Say language="{lang}">{escape(text)}</Say>'
        base = self.cfg["notify"].get("public_base_url", "").rstrip("/")
        if ask and base:
            prompt = "Bitte sprich jetzt deine Antwort nach dem Signal."
            return (
                f'<Response>{say}<Gather input="speech" language="{lang}" speechTimeout="auto" '
                f'action="{escape(base)}/voice/answer" method="POST"><Say language="{lang}">{prompt}</Say>'
                f'</Gather><Say language="{lang}">Keine Antwort erhalten. Du kannst auch per SMS antworten.</Say>'
                f"</Response>"
            )
        tail = " Du kannst mir per SMS antworten." if ask else ""
        return f'<Response>{say}<Say language="{lang}">{escape(tail)}</Say></Response>'

    def call(self, text: str, kind: str = "info", ask: bool = False) -> bool:
        sent = False
        if self._live():
            try:
                self._twilio().calls.create(to=self.owner, from_=self.from_number, twiml=self.call_twiml(text, ask))
                sent = True
            except Exception:  # noqa: BLE001
                log.exception("Anruf fehlgeschlagen")
        log.info("[ANRUF %s%s] %s", kind, "" if sent else " – nicht ausgeführt", text)
        self.db.add_outbox(kind, "call", text, sent)
        return sent

    def configure_webhook(self, base_url: str) -> bool:
        """SMS-Webhook der Twilio-Nummer automatisch auf <base_url>/sms setzen."""
        if not self.configured or not base_url:
            return False
        try:
            numbers = self._twilio().incoming_phone_numbers.list(phone_number=self.from_number, limit=1)
            if not numbers:
                log.error("Twilio-Nummer %s nicht im Konto gefunden", self.from_number)
                return False
            numbers[0].update(sms_url=f"{base_url.rstrip('/')}/sms", sms_method="POST")
            log.info("Twilio leitet SMS-Antworten jetzt an %s/sms", base_url.rstrip("/"))
            return True
        except Exception:  # noqa: BLE001
            log.exception("Twilio-Webhook konnte nicht gesetzt werden")
            return False

    def notify(self, kind: str, text: str, ask: bool = False) -> None:
        """Je nach Ereignis-Art anrufen und/oder SMS schicken (siehe config notify)."""
        ncfg = self.cfg["notify"]
        if kind in ncfg.get("call_on", []):
            self.call(text, kind=kind, ask=ask)
            self.sms(text, kind=kind)
        elif kind in ncfg.get("sms_on", []):
            self.sms(text, kind=kind)
        else:
            log.info("[%s] %s", kind, text)
