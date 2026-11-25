"""Befehle, die der Besitzer per SMS oder Anruf an Jarvis schicken kann."""

from __future__ import annotations

import re

from content_crew.db import DB

HELP = (
    "Befehle: STATUS, STOP (pausieren), START (weiter), ANRUF (nach der Runde anrufen), OK <id> (Video freigeben), "
    "NEIN <id> (verwerfen). Jeder andere Text ist eine Anweisung an Jarvis."
)


def status_text(db: DB) -> str:
    vids = db.videos(limit=200)
    labels = {"draft": "Entwurf", "produced": "fertig", "awaiting_approval": "warten auf Freigabe",
              "published": "veröffentlicht", "rejected": "verworfen", "failed": "Fehler"}
    counts: dict[str, int] = {}
    for v in vids:
        label = labels.get(v["status"], v["status"])
        counts[label] = counts.get(label, 0) + 1
    metrics = db.latest_metrics()
    total_views = sum(m["views"] or 0 for m in metrics)
    state = "PAUSIERT" if db.paused else "aktiv"
    parts = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "noch keine Videos"
    return f"Jarvis ist {state}. Videos – {parts}. Views gesamt: {total_views}."


def handle_owner_message(db: DB, text: str, channel: str = "sms") -> str:
    """Sofort-Befehle ausführen. Gibt die Antwort an den Besitzer zurück.

    Freitext und Freigaben landen in der Inbox und werden im nächsten Durchlauf
    vom Chef (Jarvis) verarbeitet.
    """
    msg = text.strip()
    upper = msg.upper()
    if upper in {"STOP", "PAUSE"}:
        db.set_state("paused", "1")
        return "Jarvis ist pausiert. Mit START geht es weiter."
    if upper in {"START", "WEITER"}:
        db.set_state("paused", "0")
        return "Jarvis arbeitet wieder."
    if upper == "STATUS":
        return status_text(db)
    if upper in {"HILFE", "HELP", "?"}:
        return HELP
    if upper in {"ANRUF", "RUF MICH AN", "ANRUFEN"}:
        db.set_state("call_when_done", "1")
        return "Mach ich: Ich rufe dich an, sobald die nächste Runde fertig ist."
    m = re.fullmatch(r"(OK|JA|NEIN|NO)\s+#?(\d+)", upper)
    if m:
        video = db.video(int(m.group(2)))
        if not video:
            return f"Video {m.group(2)} gibt es nicht."
        if m.group(1) in {"NEIN", "NO"}:
            db.update_video(video["id"], status="rejected")
            return f"Video {video['id']} verworfen."
        db.add_inbox(channel, f"APPROVE {video['id']}")
        return f"Video {video['id']} freigegeben, wird im nächsten Durchlauf hochgeladen."
    db.add_inbox(channel, msg)
    return "Verstanden, ich gebe das an mein Team weiter."
