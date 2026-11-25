#!/usr/bin/env bash
# Installiert alles für Content Crew auf deinem PC (Ubuntu/WSL2 oder macOS).
# Aufruf:  bash scripts/install_pc.sh          (NICHT mit sudo – fragt selbst nach dem Passwort)
# Anderes Modell:  MODEL=qwen3.5:4b bash scripts/install_pc.sh
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL="${MODEL:-qwen3.5:9b}"
export PATH="$HOME/.local/bin:$PATH"

if [[ "$(id -u)" -eq 0 ]]; then
    echo "Bitte als normaler Benutzer ausführen, nicht als root." >&2
    exit 1
fi

echo "==> 1/5 System-Pakete (ffmpeg, cloudflared)"
if [[ "$(uname -s)" == "Darwin" ]]; then
    command -v brew >/dev/null || { echo "Bitte zuerst Homebrew installieren: https://brew.sh" >&2; exit 1; }
    brew install ffmpeg cloudflared git
else
    sudo apt-get update -q
    sudo apt-get install -y -q ffmpeg git curl libegl1  # libegl1 braucht die Grafik-Engine (Skia)
    if ! command -v cloudflared >/dev/null; then
        arch="$(dpkg --print-architecture)"
        curl -fsSL -o /tmp/cloudflared.deb \
            "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}.deb"
        sudo dpkg -i /tmp/cloudflared.deb
        rm -f /tmp/cloudflared.deb
    fi
fi

echo "==> 2/5 uv (Python-Paketmanager)"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

echo "==> 3/5 Jarvis (OpenJarvis + Ollama)"
if [[ ! -x "$HOME/.openjarvis/.venv/bin/jarvis" ]]; then
    curl -fsSL https://open-jarvis.github.io/OpenJarvis/install.sh | bash -s -- --no-analytics
fi
(cd "$HOME/.openjarvis/src" && uv pip install --python "$HOME/.openjarvis/.venv/bin/python" -e ".[server]")

echo "==> 4/5 KI-Modell $MODEL (einige GB, dauert etwas)"
if ! ollama list >/dev/null 2>&1; then
    nohup ollama serve >/tmp/ollama.log 2>&1 &
    for _ in $(seq 30); do ollama list >/dev/null 2>&1 && break; sleep 1; done
fi
ollama pull "$MODEL"

echo "==> 5/5 Content Crew"
[[ -d .venv ]] || uv venv .venv
uv pip install --python .venv/bin/python -e ".[all]"
mkdir -p data secrets
[[ -f config.yaml ]] || cp config.example.yaml config.yaml
[[ -f .env ]] || { cp .env.example .env; chmod 600 .env; }
sed -i.bak "s/^\([[:space:]]*model:\).*/\1 $MODEL/" config.yaml && rm -f config.yaml.bak

cat <<EOF

Installation fertig.

Weiter geht's:
  cd $(pwd)
  source .venv/bin/activate
  content-crew setup          # Zugangsdaten eintragen (Assistent)
  content-crew doctor         # prüfen
  bash scripts/start.sh       # Jarvis + Team starten
EOF
