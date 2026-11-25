"""Öffentliche Adresse für deinen PC über einen kostenlosen Cloudflare-Tunnel.

Twilio (SMS-/Sprach-Antworten) und Instagram (holt das Video ab) brauchen eine
öffentlich erreichbare Adresse. `cloudflared` erzeugt bei jedem Start eine neue
https://….trycloudflare.com-Adresse; Content Crew trägt sie automatisch ein.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
import time

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def find_url(text: str) -> str | None:
    m = URL_RE.search(text)
    return m.group(0) if m else None


class Tunnel:
    def __init__(self, port: int):
        self.port = port
        self.proc: subprocess.Popen | None = None
        self.url: str | None = None

    @staticmethod
    def available() -> bool:
        return shutil.which("cloudflared") is not None

    def start(self, timeout: float = 60) -> str | None:
        if not self.available():
            log.warning("cloudflared ist nicht installiert – keine öffentliche Adresse.")
            return None
        self.proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        found = threading.Event()

        def reader() -> None:
            assert self.proc and self.proc.stdout
            for line in self.proc.stdout:
                if not self.url:
                    url = find_url(line)
                    if url:
                        self.url = url
                        found.set()

        threading.Thread(target=reader, daemon=True).start()
        found.wait(timeout)
        if self.url:
            time.sleep(3)  # DNS des neuen Tunnels braucht einen Moment
            log.info("Öffentliche Adresse: %s", self.url)
        else:
            log.error("Tunnel konnte nicht gestartet werden.")
        return self.url

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
