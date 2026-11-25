"""Werte sicher in die .env-Datei schreiben (bestehende Zeilen bleiben erhalten)."""

from __future__ import annotations

import os
import re
from pathlib import Path


def set_env_values(values: dict[str, str], path: str | Path = ".env") -> None:
    p = Path(path)
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    remaining = {k: v for k, v in values.items() if v is not None}
    out = []
    for line in lines:
        m = re.match(r"\s*([A-Z0-9_]+)\s*=", line)
        if m and m.group(1) in remaining:
            key = m.group(1)
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    out.extend(f"{k}={v}" for k, v in remaining.items())
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:  # pragma: no cover - z. B. Windows-Dateisysteme
        pass
    for key, value in values.items():
        if value is not None:
            os.environ[key] = str(value)
