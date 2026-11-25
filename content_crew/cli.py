"""Kommandozeile: content-crew <befehl>."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import shutil
import sys
import threading
from pathlib import Path

import requests

from content_crew.commands import status_text
from content_crew.config import Config, load_config
from content_crew.db import DB
from content_crew.llm import LLM
from content_crew.notify import Notifier
from content_crew.platforms import load_platforms


def _setup(args) -> tuple[Config, DB]:
    cfg = load_config(args.config)
    if args.dry_run:
        cfg["dry_run"] = True
    return cfg, DB(cfg.data_dir / "crew.db")


def _boss(cfg: Config, db: DB):
    from content_crew.boss import Boss

    return Boss(cfg, db, LLM(cfg["llm"], cfg.env("JARVIS_API_KEY", "none")), Notifier(cfg, db))


def cmd_init(args) -> None:
    root = Path(__file__).resolve().parent.parent
    for src, dst in (("config.example.yaml", "config.yaml"), (".env.example", ".env")):
        if Path(dst).exists():
            print(f"{dst} existiert schon – nicht überschrieben.")
        else:
            shutil.copy(root / src, dst)
            print(f"{dst} angelegt – bitte ausfüllen.")
    Path("secrets").mkdir(exist_ok=True)


def cmd_doctor(args) -> None:
    cfg, db = _setup(args)
    ok = lambda b: "OK " if b else "-- "  # noqa: E731
    try:
        r = requests.get(cfg["llm"]["base_url"].rstrip("/") + "/models", timeout=10)
        models = [m["id"] for m in r.json().get("data", [])]
        jarvis = cfg["llm"]["model"] in models
        print(f"{ok(jarvis)}Jarvis erreichbar, Modelle: {', '.join(models)}")
    except Exception as exc:  # noqa: BLE001
        print(f"--  Jarvis nicht erreichbar ({exc}). Starte: jarvis start")
    print(f"{ok(shutil.which('ffmpeg'))}ffmpeg")
    n = Notifier(cfg, db)
    print(f"{ok(n.configured)}Twilio (SMS/Anrufe)" + ("" if n.configured else " – TWILIO_* / OWNER_PHONE_NUMBER fehlen"))
    from content_crew.tunnel import Tunnel

    public = cfg["notify"].get("public_base_url") or (Tunnel.available() and cfg["notify"].get("tunnel") != "off")
    print(f"{ok(public)}Öffentliche Adresse" + (
        "" if cfg["notify"].get("public_base_url") else
        (" – wird bei 'content-crew run' automatisch per cloudflared erstellt" if public
         else " – cloudflared installieren (scripts/install_pc.sh)")))
    print(f"{ok(cfg.env('PEXELS_API_KEY'))}Pexels (Hintergrundvideos)"
          + ("" if cfg.env("PEXELS_API_KEY") else " – ohne Key nur farbige Hintergründe"))
    for name, p in load_platforms(cfg).items():
        missing = p.missing()
        print(f"{ok(not missing)}{name}" + (f" – fehlt: {', '.join(missing)}" if missing else ""))
    print(f"\nTestmodus (dry_run): {'AN' if cfg.dry_run else 'aus'}")


def cmd_cycle(args) -> None:
    cfg, db = _setup(args)
    boss = _boss(cfg, db)
    tunnel = _start_services(cfg, db, boss, 8787)
    try:
        created = boss.run_cycle()
    finally:
        if tunnel:
            tunnel.stop()
    print(f"Fertig. Neue Videos: {created or 'keine'}")
    for vid in created:
        v = db.video(vid)
        print(f"  #{vid} [{v['status']}] {v['script']['title']} -> {v['path']}")


def _start_services(cfg: Config, db: DB, boss, port: int):
    """Webhook-/Medien-Server starten und – falls nötig – den öffentlichen Tunnel."""
    threading.Thread(target=_serve, args=(cfg, db, port), daemon=True).start()
    if cfg.dry_run or cfg["notify"].get("public_base_url") or cfg["notify"].get("tunnel", "auto") == "off":
        return None
    from content_crew.tunnel import Tunnel

    tunnel = Tunnel(port)
    url = tunnel.start()
    if url:
        cfg["notify"]["public_base_url"] = url
        boss.notifier.configure_webhook(url)
    return tunnel


def cmd_run(args) -> None:
    cfg, db = _setup(args)
    boss = _boss(cfg, db)
    tunnel = None if args.no_server else _start_services(cfg, db, boss, args.port)
    boss.notifier.sms("Jarvis ist gestartet und arbeitet. Schreib STATUS für eine Übersicht.", "start")
    try:
        boss.run_forever()
    finally:
        if tunnel:
            tunnel.stop()


def cmd_setup(args) -> None:
    from content_crew.wizard import run_wizard

    run_wizard()


def cmd_auth_instagram(args) -> None:
    load_config(args.config)
    from content_crew.auth import instagram_setup

    print("1. Öffne developers.facebook.com/tools/explorer, wähle deine App,")
    print("2. füge die Berechtigungen instagram_basic, instagram_content_publish, instagram_manage_insights,")
    print("   pages_show_list, pages_read_engagement, business_management hinzu,")
    print("3. klicke 'Generate Access Token' und kopiere den Token.\n")
    token = args.token or getpass.getpass("Token einfügen: ").strip()
    info = instagram_setup(token, Config.env("META_APP_ID"), Config.env("META_APP_SECRET"))
    print(f"Instagram verbunden: @{info['username']} (Seite: {info['page']}). Token gespeichert, läuft nicht ab.")


def cmd_auth_tiktok(args) -> None:
    load_config(args.config)
    from content_crew.auth import tiktok_login

    key, secret = Config.env("TIKTOK_CLIENT_KEY"), Config.env("TIKTOK_CLIENT_SECRET")
    if not (key and secret):
        sys.exit("TIKTOK_CLIENT_KEY und TIKTOK_CLIENT_SECRET fehlen – erst content-crew setup ausführen.")
    redirect = Config.env("TIKTOK_REDIRECT_URI", "http://localhost:8788/callback/")
    print(f"Wichtig: '{redirect}' muss in deiner TikTok-App unter Login Kit → Redirect URI eingetragen sein.\n")
    tiktok_login(key, secret, redirect)
    print("TikTok verbunden. Tokens gespeichert und werden automatisch erneuert.")


def _serve(cfg: Config, db: DB, port: int) -> None:
    import uvicorn

    from content_crew.webhooks import create_app

    uvicorn.run(create_app(cfg, db), host="127.0.0.1", port=port, log_level="warning")


def cmd_serve(args) -> None:
    cfg, db = _setup(args)
    _serve(cfg, db, args.port)


def cmd_status(args) -> None:
    cfg, db = _setup(args)
    print(status_text(db))
    for v in db.videos(limit=args.limit):
        print(f"  #{v['id']} [{v['status']}] {v['script']['title']}  {json.dumps(v['platform_ids'])}")
    learnings = db.notes("learning", 5)
    if learnings:
        print("\nLearnings:\n  - " + "\n  - ".join(learnings))


def cmd_sms(args) -> None:
    cfg, db = _setup(args)
    sent = Notifier(cfg, db).sms(args.text or "Hallo, hier ist Jarvis. Die SMS-Verbindung funktioniert.", "test")
    print("SMS gesendet." if sent else "SMS NICHT gesendet (Twilio nicht eingerichtet oder Testmodus).")


def cmd_call(args) -> None:
    cfg, db = _setup(args)
    sent = Notifier(cfg, db).call(
        args.text or "Hallo, hier ist Jarvis. Die Anruf-Verbindung funktioniert.", "test", ask=args.ask)
    print("Anruf gestartet." if sent else "Anruf NICHT gestartet (Twilio nicht eingerichtet oder Testmodus).")


def cmd_auth_youtube(args) -> None:
    cfg, _ = _setup(args)
    from content_crew.platforms.youtube import YouTube

    YouTube(cfg).authorize()
    print("YouTube-Login gespeichert.")


def cmd_publish(args) -> None:
    cfg, db = _setup(args)
    boss = _boss(cfg, db)
    tunnel = _start_services(cfg, db, boss, 8787)
    try:
        boss.publish(args.video_id)
    finally:
        if tunnel:
            tunnel.stop()
    print(json.dumps(db.video(args.video_id)["platform_ids"]))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="content-crew", description="Jarvis und sein KI-Content-Team")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Testmodus: nichts hochladen, keine SMS/Anrufe")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="config.yaml und .env anlegen").set_defaults(func=cmd_init)
    sub.add_parser("doctor", help="prüfen, was eingerichtet ist").set_defaults(func=cmd_doctor)
    sub.add_parser("cycle", help="einen Durchlauf jetzt ausführen").set_defaults(func=cmd_cycle)
    p = sub.add_parser("run", help="dauerhaft laufen (Automatik)")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--no-server", action="store_true", help="ohne Webhook-Server")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("serve", help="nur Webhook-Server starten")
    p.add_argument("--port", type=int, default=8787)
    p.set_defaults(func=cmd_serve)
    p = sub.add_parser("status", help="Übersicht")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("test-sms", help="Test-SMS an dich")
    p.add_argument("text", nargs="?")
    p.set_defaults(func=cmd_sms)
    p = sub.add_parser("test-call", help="Test-Anruf an dich")
    p.add_argument("text", nargs="?")
    p.add_argument("--ask", action="store_true", help="nach Antwort per Sprache fragen")
    p.set_defaults(func=cmd_call)
    sub.add_parser("setup", help="Einrichtungs-Assistent").set_defaults(func=cmd_setup)
    sub.add_parser("auth-youtube", help="einmalig bei YouTube anmelden").set_defaults(func=cmd_auth_youtube)
    p = sub.add_parser("auth-instagram", help="Instagram verbinden")
    p.add_argument("--token", help="Token aus dem Graph API Explorer")
    p.set_defaults(func=cmd_auth_instagram)
    sub.add_parser("auth-tiktok", help="einmalig bei TikTok anmelden").set_defaults(func=cmd_auth_tiktok)
    p = sub.add_parser("publish", help="ein bestimmtes Video hochladen")
    p.add_argument("video_id", type=int)
    p.set_defaults(func=cmd_publish)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args.func(args)


if __name__ == "__main__":
    main()
