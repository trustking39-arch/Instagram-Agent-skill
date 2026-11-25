"""Übersichtsseite: Jarvis und seine Arbeiter live im Browser (http://localhost:8787)."""

from __future__ import annotations

import time
from html import escape
from pathlib import Path

from content_crew.commands import status_text
from content_crew.config import Config
from content_crew.db import DB

WORKERS = [
    ("jarvis", "Jarvis", "Chef", "plant, bewertet, lernt"),
    ("scout", "Trend-Scout", "Arbeiter", "findet, was gerade läuft"),
    ("writer", "Skript-Autor", "Arbeiter", "schreibt Hook und Szenen"),
    ("producer", "Video-Produzent", "Arbeiter", "baut das Video"),
    ("publisher", "Uploader", "Arbeiter", "lädt auf die Plattformen"),
    ("analyst", "Analyst", "Arbeiter", "misst, was viral geht"),
]

STATUS_LABEL = {
    "draft": "Entwurf", "produced": "fertig", "awaiting_approval": "wartet auf Freigabe",
    "published": "veröffentlicht", "rejected": "verworfen", "failed": "Fehler",
}

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#16181d;--muted:#5f6673;--line:#e3e6eb;--accent:#4f46e5;
--ok:#15803d;--warn:#b45309;--bad:#b91c1c;--chip:#eef0f4}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--text:#e8eaf0;--muted:#9aa3b2;
--line:#262b35;--accent:#8b84ff;--ok:#4ade80;--warn:#fbbf24;--bad:#f87171;--chip:#222733}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0}h2{font-size:15px;margin:32px 0 12px;color:var(--muted);font-weight:600;
text-transform:uppercase;letter-spacing:.04em}
.top{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}
.sub{color:var(--muted);margin:4px 0 0}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;background:var(--chip);font-size:13px}
.badge.ok{color:var(--ok)}.badge.warn{color:var(--warn)}.badge.bad{color:var(--bad)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card.boss{grid-column:1/-1;border-color:var(--accent)}
.who b{font-size:16px;display:block}.role{color:var(--muted);font-size:13px;display:block}
.now{margin:8px 0 0}.when{color:var(--muted);font-size:12px;margin-top:4px}
.busy .now::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;
background:var(--ok);margin-right:8px;vertical-align:middle}
.videos{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
video{width:100%;aspect-ratio:9/16;background:#000;border-radius:8px;display:block}
.vt{font-weight:600;margin:8px 0 2px}.meta{color:var(--muted);font-size:13px}
ul{margin:0;padding-left:18px}li{margin:4px 0}
.msg{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:14px}
.msg:last-child{border:0}.msg .k{min-width:92px;color:var(--muted)}
form{display:inline}button{font:inherit;padding:6px 14px;border-radius:8px;border:1px solid var(--line);
background:var(--card);color:var(--text);cursor:pointer}button.primary{background:var(--accent);
color:#fff;border-color:var(--accent)}.actions{display:flex;gap:8px;flex-wrap:wrap}
input[type=text]{font:inherit;padding:6px 10px;border-radius:8px;border:1px solid var(--line);
background:var(--card);color:var(--text);flex:1;min-width:200px}
.say{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
"""

REFRESH_JS = """
setInterval(async()=>{try{const r=await fetch(location.pathname,{cache:'no-store'});
const d=new DOMParser().parseFromString(await r.text(),'text/html');
for(const id of ['live','team','msgs']){const n=d.getElementById(id);if(n)document.getElementById(id).replaceWith(n);}
}catch(e){}},10000);
"""


def _ago(ts: float) -> str:
    if not ts:
        return "noch nie"
    s = int(time.time() - ts)
    if s < 60:
        return "gerade eben"
    if s < 3600:
        return f"vor {s // 60} Min."
    if s < 86400:
        return f"vor {s // 3600} Std."
    return f"vor {s // 86400} Tagen"


def render(cfg: Config, db: DB) -> str:
    e = escape
    paused = db.paused
    last = float(db.get_state("last_cycle", "0") or 0)
    minutes = float(cfg["boss"]["cycle_minutes"])
    next_in = max(0, int((last + minutes * 60 - time.time()) / 60)) if last else None
    mode = "Testmodus – nichts wird hochgeladen, keine SMS" if cfg.dry_run else "Live"
    state = ('<span class="badge warn">pausiert</span>' if paused else '<span class="badge ok">arbeitet</span>')

    team = []
    for key, name, role, job in WORKERS:
        a = db.activity(key)
        busy = time.time() - a["ts"] < 600 and not a["text"].startswith(("wartet", "fertig", "Runde fertig"))
        team.append(
            f'<div class="card{" boss" if key == "jarvis" else ""}{" busy" if busy else ""}">'
            f'<div class="who"><b>{e(name)}</b><span class="role">{e(role)} · {e(job)}</span></div>'
            f'<div class="now">{e(a["text"])}</div><div class="when">{_ago(a["ts"])}</div></div>'
        )

    metrics: dict[int, list[dict]] = {}
    for m in db.latest_metrics():
        metrics.setdefault(m["video_id"], []).append(m)
    vids = []
    for v in db.videos(limit=24):
        name = Path(v["path"]).name if v.get("path") else ""
        player = f'<video src="/media/{e(name)}" controls preload="metadata"></video>' if name else ""
        stats = ", ".join(f"{m['platform']}: {m['views'] or 0} Aufrufe" for m in metrics.get(v["id"], []))
        approve = ""
        if v["status"] == "awaiting_approval":
            vid = v["id"]
            ok_btn = _cmd(f"OK {vid}", "Hochladen", True)
            no_btn = _cmd(f"NEIN {vid}", "Verwerfen")
            approve = f'<div class="actions" style="margin-top:8px">{ok_btn}{no_btn}</div>'
        vids.append(
            f'<div class="card">{player}<div class="vt">#{v["id"]} {e(v["script"]["title"])}</div>'
            f'<div class="meta">{e(STATUS_LABEL.get(v["status"], v["status"]))} · Note {v["score"] or 0:.0f}/10'
            f'{" · " + e(", ".join(v["platform_ids"])) if v["platform_ids"] else ""}</div>'
            f'{f"<div class=meta>{e(stats)}</div>" if stats else ""}{approve}</div>'
        )

    learnings = db.notes("learning", 8)
    focus = db.notes("focus", 1)
    instr = db.notes("instruction", 5)
    msgs = db.conn.execute("SELECT * FROM outbox ORDER BY id DESC LIMIT 12").fetchall()
    kind_label = {"call": "Anruf", "sms": "SMS"}
    msg_html = "".join(
        f'<div class="msg"><span class="k">{kind_label.get(m["channel"], m["channel"])} · {_ago(m["ts"])}</span>'
        f'<span>{e(m["text"])}{"" if m["sent"] else " <span class=meta>(nicht gesendet)</span>"}</span></div>'
        for m in msgs
    ) or '<p class="meta">Noch keine Nachrichten.</p>'

    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis Team</title>
<style>{CSS}</style></head><body><main>
<div class="top" id="live"><div><h1>Jarvis und sein Team {state}</h1>
<p class="sub">{e(cfg["niche"])} · {e(mode)} · Modell {e(cfg["llm"]["model"])} · letzte Runde {_ago(last)}
{f"· nächste in {next_in} Min." if next_in is not None and not paused else ""}</p>
<p class="sub">{e(status_text(db))}</p></div>
<div class="actions">{_cmd("START", "Weiter", True) if paused else _cmd("STOP", "Pausieren")}</div></div>

<h2>Team</h2><div class="grid" id="team">{"".join(team)}</div>

<h2>Anweisung an Jarvis</h2><div class="card">
<form method="post" action="/dashboard/cmd" class="say"><input type="text" name="text" required
placeholder="z. B. Mach mehr Videos über Ernährung, weniger über Sport"><button class="primary">Senden</button></form>
{"<p class=meta>Letzte Anweisungen:</p><ul>" + "".join(f"<li>{e(i)}</li>" for i in instr) + "</ul>" if instr else ""}
</div>

<h2>Videos</h2><div class="videos">{"".join(vids) or '<p class="meta">Noch keine Videos.</p>'}</div>

<h2>Was Jarvis gelernt hat</h2><div class="card">
{f"<p><b>Fokus:</b> {e(focus[0])}</p>" if focus else ""}
{"<ul>" + "".join(f"<li>{e(x)}</li>" for x in learnings) + "</ul>" if learnings else
 '<p class="meta">Noch nichts – Jarvis lernt, sobald echte Aufrufzahlen da sind.</p>'}</div>

<h2>Nachrichten an dich</h2><div class="card" id="msgs">{msg_html}</div>
</main><script>{REFRESH_JS}</script></body></html>"""


def _cmd(command: str, label: str, primary: bool = False) -> str:
    return (f'<form method="post" action="/dashboard/cmd"><input type="hidden" name="text" value="{escape(command)}">'
            f'<button{" class=primary" if primary else ""}>{escape(label)}</button></form>')
