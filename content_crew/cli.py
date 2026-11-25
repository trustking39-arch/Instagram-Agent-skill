"""Kommandozeile: content-crew <befehl>."""

from __future__ import annotations

import argparse
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
    print(f"{ok(cfg['notify'].get('public_base_url'))}Öffentliche URL (Rückantworten per SMS/Sprache, Instagram)")
    for name, p in load_platforms(cfg).items():
        missing = p.missing()
        print(f"{ok(not missing)}{name}" + (f" – fehlt: {', '.join(missing)}" if missing else ""))
    print(f"\nTestmodus (dry_run): {'AN' if cfg.dry_run else 'aus'}")


def cmd_cycle(args) -> None:
    cfg, db = _setup(args)
    created = _boss(cfg, db).run_cycle()
    print(f"Fertig. Neue Videos: {created or 'keine'}")
    for vid in created:
        v = db.video(vid)
        print(f"  #{vid} [{v['status']}] {v['script']['title']} -> {v['path']}")


def cmd_run(args) -> None:
    cfg, db = _setup(args)
    if not args.no_server:
        threading.Thread(target=_serve, args=(cfg, db, args.port), daemon=True).start()
    _boss(cfg, db).run_forever()


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
    _boss(cfg, db).publish(args.video_id)
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
    sub.add_parser("auth-youtube", help="einmalig bei YouTube anmelden").set_defaults(func=cmd_auth_youtube)
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
