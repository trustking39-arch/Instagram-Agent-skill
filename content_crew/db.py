"""SQLite-Speicher: Videos, Statistiken, Learnings, Nachrichten."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    idea TEXT NOT NULL,
    script TEXT NOT NULL,
    score REAL,
    path TEXT,
    status TEXT NOT NULL,              -- draft | produced | awaiting_approval | published | rejected | failed
    platform_ids TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS metrics (
    video_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    ts REAL NOT NULL,
    views INTEGER, likes INTEGER, comments INTEGER, shares INTEGER
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,                -- learning | focus | log
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    channel TEXT NOT NULL,             -- sms | voice
    text TEXT NOT NULL,
    handled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    channel TEXT NOT NULL,
    text TEXT NOT NULL,
    sent INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    video_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (video_id, platform, kind)
);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class DB:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # --- state ---
    def get_state(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO state(key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    @property
    def paused(self) -> bool:
        return self.get_state("paused") == "1"

    # --- videos ---
    def add_video(self, idea: str, script: dict, score: float | None, status: str = "draft") -> int:
        cur = self.conn.execute(
            "INSERT INTO videos(created_at, idea, script, score, status) VALUES (?,?,?,?,?)",
            (time.time(), idea, json.dumps(script, ensure_ascii=False), score, status),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_video(self, video_id: int, **fields: Any) -> None:
        if "platform_ids" in fields:
            fields["platform_ids"] = json.dumps(fields["platform_ids"])
        if "script" in fields:
            fields["script"] = json.dumps(fields["script"], ensure_ascii=False)
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE videos SET {cols} WHERE id=?", (*fields.values(), video_id))
        self.conn.commit()

    def video(self, video_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
        return self._video(row) if row else None

    def videos(self, status: str | None = None, limit: int = 50) -> list[dict]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM videos WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM videos ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._video(r) for r in rows]

    @staticmethod
    def _video(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["script"] = json.loads(d["script"])
        d["platform_ids"] = json.loads(d["platform_ids"] or "{}")
        return d

    # --- metrics ---
    def add_metrics(self, video_id: int, platform: str, m: dict) -> None:
        self.conn.execute(
            "INSERT INTO metrics VALUES (?,?,?,?,?,?,?)",
            (video_id, platform, time.time(), m.get("views"), m.get("likes"), m.get("comments"), m.get("shares")),
        )
        self.conn.commit()

    def latest_metrics(self, platform: str | None = None) -> list[dict]:
        sql = """
        SELECT m.* FROM metrics m
        JOIN (SELECT video_id, platform, MAX(ts) ts FROM metrics GROUP BY video_id, platform) x
          ON m.video_id=x.video_id AND m.platform=x.platform AND m.ts=x.ts
        """
        args: tuple = ()
        if platform:
            sql += " WHERE m.platform=?"
            args = (platform,)
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    # --- alerts ---
    def alert_once(self, video_id: int, platform: str, kind: str) -> bool:
        """True, wenn dieser Alarm neu ist (und merkt ihn sich)."""
        try:
            self.conn.execute("INSERT INTO alerts VALUES (?,?,?)", (video_id, platform, kind))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    # --- notes ---
    def add_note(self, kind: str, text: str) -> None:
        self.conn.execute("INSERT INTO notes(ts, kind, text) VALUES (?,?,?)", (time.time(), kind, text))
        self.conn.commit()

    def notes(self, kind: str, limit: int = 10) -> list[str]:
        rows = self.conn.execute(
            "SELECT text FROM notes WHERE kind=? ORDER BY id DESC LIMIT ?", (kind, limit)
        ).fetchall()
        return [r["text"] for r in rows]

    # --- inbox / outbox ---
    def add_inbox(self, channel: str, text: str) -> None:
        self.conn.execute("INSERT INTO inbox(ts, channel, text) VALUES (?,?,?)", (time.time(), channel, text))
        self.conn.commit()

    def take_inbox(self) -> list[dict]:
        rows = [dict(r) for r in self.conn.execute("SELECT * FROM inbox WHERE handled=0 ORDER BY id").fetchall()]
        if rows:
            self.conn.execute("UPDATE inbox SET handled=1 WHERE id IN (%s)" % ",".join("?" * len(rows)),
                              [r["id"] for r in rows])
            self.conn.commit()
        return rows

    def add_outbox(self, kind: str, channel: str, text: str, sent: bool) -> None:
        self.conn.execute(
            "INSERT INTO outbox(ts, kind, channel, text, sent) VALUES (?,?,?,?,?)",
            (time.time(), kind, channel, text, int(sent)),
        )
        self.conn.commit()
