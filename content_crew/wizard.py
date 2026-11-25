"""Einrichtungs-Assistent: fragt alle Zugangsdaten ab und schreibt sie in .env / config.yaml."""

from __future__ import annotations

import getpass
import json
import os
import re
import shutil
from pathlib import Path

from content_crew.envfile import set_env_values

ROOT = Path(__file__).resolve().parent.parent

SECTIONS = [
    ("Twilio – damit Jarvis dich anrufen und dir SMS schicken kann (twilio.com → Console)", [
        ("TWILIO_ACCOUNT_SID", "Account SID", False),
        ("TWILIO_AUTH_TOKEN", "Auth Token", True),
        ("TWILIO_PHONE_NUMBER", "Deine Twilio-Nummer (+49…)", False),
        ("OWNER_PHONE_NUMBER", "DEINE Handynummer (+49…)", False),
    ]),
    ("Pexels – kostenlose Hintergrundvideos (pexels.com/api → API-Key)", [
        ("PEXELS_API_KEY", "Pexels API-Key", True),
    ]),
    ("YouTube – Trend-Suche (console.cloud.google.com → YouTube Data API v3 → API-Schlüssel)", [
        ("YOUTUBE_API_KEY", "YouTube API-Schlüssel", True),
    ]),
    ("Meta/Instagram – App-Daten (developers.facebook.com → deine App → Einstellungen → Allgemein)", [
        ("META_APP_ID", "App-ID", False),
        ("META_APP_SECRET", "App-Geheimcode", True),
    ]),
    ("TikTok – App-Daten (developers.tiktok.com → deine App)", [
        ("TIKTOK_CLIENT_KEY", "Client Key", False),
        ("TIKTOK_CLIENT_SECRET", "Client Secret", True),
    ]),
]


def _ask(label: str, current: str, secret: bool) -> str:
    shown = ("gesetzt" if secret else current) if current else "leer"
    prompt = f"  {label} [{shown}, Enter = behalten]: "
    value = getpass.getpass(prompt) if secret else input(prompt)
    return value.strip()


def run_wizard() -> None:
    print("\n=== Content Crew – Einrichtung ===\nLeer lassen = später einrichten.\n")
    for src, dst in (("config.example.yaml", "config.yaml"), (".env.example", ".env")):
        if not Path(dst).exists():
            shutil.copy(ROOT / src, dst)
    Path("secrets").mkdir(exist_ok=True)

    cfg_path = Path("config.yaml")
    text = cfg_path.read_text(encoding="utf-8")
    current_niche = re.search(r'^niche:\s*"?([^"#\n]*)"?', text, re.M)
    niche = input(f"Dein Themengebiet/Nische [{current_niche.group(1).strip() if current_niche else ''}]: ").strip()
    if niche:
        text = re.sub(r"^niche:.*$", f"niche: {json.dumps(niche, ensure_ascii=False)}", text, flags=re.M)
    approve = input("Soll Jarvis dich vor jedem Upload per SMS fragen? (empfohlen am Anfang) [J/n]: ").strip().lower()
    text = re.sub(r"^(\s*auto_publish:)\s*\w+", r"\1 " + ("true" if approve == "n" else "false"), text, flags=re.M)
    cfg_path.write_text(text, encoding="utf-8")

    for title, fields in SECTIONS:
        print(f"\n{title}")
        updates = {}
        for key, label, secret in fields:
            value = _ask(label, os.environ.get(key, ""), secret)
            if value:
                updates[key] = value
        if updates:
            set_env_values(updates)

    secret_file = Path("secrets/youtube_client_secret.json")
    if not secret_file.exists():
        print(f"\nYouTube-Upload: Lade die OAuth-Datei (Desktop-App) herunter und speichere sie als {secret_file}.")
    print("\nFertig. Nächste Schritte:")
    print("  content-crew auth-youtube      # YouTube-Login")
    print("  content-crew auth-instagram    # Instagram verbinden")
    print("  content-crew auth-tiktok       # TikTok-Login")
    print("  content-crew doctor            # prüfen")
