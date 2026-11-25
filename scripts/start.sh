#!/usr/bin/env bash
# Startet Ollama, den Jarvis-Server und das Content-Team (Dauerbetrieb).
# Zusätzliche Argumente gehen an `content-crew run`, z. B.: bash scripts/start.sh --dry-run
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
mkdir -p data

if ! ollama list >/dev/null 2>&1; then
    echo "Starte Ollama…"
    nohup ollama serve >data/ollama.log 2>&1 &
    for _ in $(seq 60); do ollama list >/dev/null 2>&1 && break; sleep 1; done
fi

if ! curl -fsS -m 3 http://127.0.0.1:8000/v1/models >/dev/null 2>&1; then
    echo "Starte Jarvis…"
    jarvis start
    for _ in $(seq 60); do curl -fsS -m 3 http://127.0.0.1:8000/v1/models >/dev/null 2>&1 && break; sleep 2; done
fi
curl -fsS -m 3 http://127.0.0.1:8000/v1/models >/dev/null || { echo "Jarvis antwortet nicht – siehe ~/.openjarvis/server.log" >&2; exit 1; }

echo "Jarvis läuft. Starte das Team…"
exec .venv/bin/content-crew run "$@"
