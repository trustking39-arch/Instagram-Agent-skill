# Instagram-Agent-skill – Jarvis und sein KI-Content-Team

Jarvis (dein lokaler [OpenJarvis](https://github.com/open-jarvis/OpenJarvis)) ist der **Chef**.
Er steuert ein Team aus KI-Arbeitern, die rund um die Uhr Content für YouTube Shorts,
Instagram Reels und TikTok machen – und er meldet sich per **SMS oder Anruf** bei dir.

```
                    ┌──────────────── Du ────────────────┐
                    │  SMS / Anruf  ▲          │ SMS / Sprache: STOP, STATUS, OK 12, Anweisungen
                    │               │          ▼
                    │        ┌─────────────────────┐
                    │        │  JARVIS (Chef)       │  plant Themen, bewertet Skripte (1-10),
                    │        │                      │  schickt schlechte Arbeit zurück, lernt aus Zahlen
                    │        └──┬────┬────┬────┬───┘
                    │   Trend-  │Skript│Video-│Uploader│Analyst
                    │   Scout   │Autor │Produz│        │(viral?)
                    └───────────┴──────┴──────┴────────┴─────────
                       YouTube · Instagram · TikTok (offizielle APIs)
```

## Was die Arbeiter tun

| Arbeiter | Aufgabe |
|---|---|
| **Trend-Scout** | Sucht die erfolgreichsten Kurzvideos der letzten 7 Tage in deiner Nische (YouTube) und Top-Posts zum Hashtag (Instagram) und analysiert Hooks, Themen, Formate. |
| **Skript-Autor** | Schreibt das Skript (Hook, Szenen, Caption, Hashtags). Muss nachbessern, bis Jarvis mindestens die Mindestnote gibt. |
| **Video-Produzent** | Baut ein 1080×1920-Video: Sprachausgabe (Microsoft-Edge-Stimme), große Untertitel, Hintergründe (Farben oder deine eigenen Clips/Bilder). |
| **Uploader** | Lädt auf alle eingerichteten Plattformen hoch. |
| **Analyst** | Holt regelmäßig Aufrufe, Likes, Kommentare, Shares. Erkennt virale Videos (z. B. 3× dein Median und mind. 10.000 Aufrufe). |
| **Jarvis (Chef)** | Plant jede Runde neue Videos, bewertet streng, lernt aus den echten Zahlen („Fragen als Hook funktionieren“), richtet sich nach deinen Anweisungen. |

### Wann Jarvis dich kontaktiert

| Ereignis | Standard |
|---|---|
| Video geht viral | **Anruf** + SMS |
| Jarvis kommt nicht weiter (Login abgelaufen, Zugriff verweigert) | **Anruf** + SMS (max. 1× pro Tag je Problem) |
| Jarvis hat eine Frage an dich | SMS (beim Anruf kannst du per Sprache antworten) |
| Video hochgeladen, Fehler, Tagesbericht | SMS |
| Freigabe nötig (wenn `auto_publish: false`) | SMS „Antworte OK 12“ |

Einstellbar in `config.yaml` unter `notify`.

### Was du per SMS (oder am Telefon) sagen kannst

- `STATUS` – Übersicht
- `STOP` / `START` – Automatik pausieren / fortsetzen
- `OK 12` / `NEIN 12` – Video 12 freigeben / verwerfen
- alles andere, z. B. *„Mach mehr Videos über Ernährung, weniger Sport“* – Jarvis übernimmt das als Anweisung

Nur deine eigene Nummer (`OWNER_PHONE_NUMBER`) wird akzeptiert, Twilio-Anfragen werden per Signatur geprüft.

---

## Ehrlich: Was geht und was nicht

- **Nur offizielle APIs.** Kein Scraping, keine Bots, die sich als Mensch ausgeben – sonst werden Konten gesperrt.
- **TikTok:** Bis TikTok deine App geprüft hat („Audit“, dauert einige Tage bis Wochen), sind hochgeladene Videos **nur für dich sichtbar**. TikTok bietet keine Trend-Suche an; Trends kommen von YouTube/Instagram.
- **YouTube:** Neue Google-Cloud-Projekte laden Videos zunächst als **privat** hoch, bis die API-Prüfung („Audit“) bestanden ist. Das API-Kontingent reicht für etwa 6 Uploads pro Tag.
- **Instagram:** Nur mit **Business- oder Creator-Konto**, das mit einer Facebook-Seite verbunden ist. Instagram holt das Video von einer **öffentlichen URL** – dafür braucht dein PC einen Tunnel (siehe unten).
- **Qualität:** Die Videos sind Text-und-Stimme-Shorts. Mit eigenen Clips/Bildern in `video.background_dir` werden sie deutlich besser. Ein lokales Modell ist schwächer als große Cloud-Modelle – nimm mindestens `qwen3.5:9b`, mit Grafikkarte gern größer.
- **Viral garantiert niemand.** Das System testet, misst und lernt – Erfolg braucht trotzdem Zeit.
- Der PC muss laufen, damit das Team arbeitet.

---

## Installation auf deinem PC

**Windows:** OpenJarvis läuft nur unter **WSL2**. Einmalig in PowerShell (als Administrator):
```powershell
wsl --install -d Ubuntu-24.04
```
Danach alles Weitere im Ubuntu-Fenster. **macOS/Linux:** direkt im Terminal.

### 1. Jarvis installieren und starten
```bash
curl -fsSL https://open-jarvis.github.io/OpenJarvis/install.sh | bash
source ~/.bashrc
cd ~/.openjarvis/src && uv pip install --python ~/.openjarvis/.venv/bin/python -e ".[server]" && cd ~
ollama pull qwen3.5:9b
jarvis start
```

### 2. Dieses Projekt installieren
```bash
sudo apt install -y ffmpeg git          # macOS: brew install ffmpeg
git clone https://github.com/trustking39-arch/Instagram-Agent-skill.git
cd Instagram-Agent-skill
uv venv && uv pip install -e ".[all]"
source .venv/bin/activate
content-crew init                       # legt config.yaml und .env an
```
Trag in `config.yaml` deine **Nische** ein (z. B. „Fitness für Anfänger“).

### 3. Zugänge einrichten (in `.env` eintragen)

**Twilio – SMS und Anrufe** (ca. 1–2 €/Monat pro Nummer plus Cent-Beträge pro SMS/Minute)
1. Konto auf twilio.com anlegen, Telefonnummer mit **Voice + SMS** kaufen.
2. In der Twilio-Konsole: *Account SID* und *Auth Token* kopieren → `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.
3. Deine Handynummer → `OWNER_PHONE_NUMBER` (Format `+49170…`). Im Testkonto muss sie als „Verified Caller ID“ bestätigt sein.
4. Test: `content-crew test-sms` und `content-crew test-call`

**YouTube**
1. console.cloud.google.com → Projekt anlegen → *YouTube Data API v3* aktivieren.
2. *Anmeldedaten* → **API-Schlüssel** → `YOUTUBE_API_KEY`.
3. *OAuth-Zustimmungsbildschirm* einrichten (Typ „Extern“, dich als Testnutzer eintragen), dann *OAuth-Client-ID* vom Typ **Desktop-App** → JSON herunterladen → `secrets/youtube_client_secret.json`.
4. `content-crew auth-youtube` (öffnet den Browser zum Anmelden).

**Instagram** (Business/Creator-Konto, verbunden mit einer Facebook-Seite)
1. developers.facebook.com → App anlegen → Produkt *Instagram Graph API*.
2. Im *Graph API Explorer* einen Token mit `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement` erzeugen und in einen **langlebigen Token** (60 Tage) umwandeln → `INSTAGRAM_ACCESS_TOKEN`.
3. Deine Instagram-Business-ID (`GET /me/accounts` → Seite → `instagram_business_account`) → `INSTAGRAM_USER_ID`.
4. Wenn der Token abläuft, ruft Jarvis dich an.

**TikTok**
1. developers.tiktok.com → App anlegen → Produkte *Login Kit* und *Content Posting API* (Direct Post) hinzufügen, Scopes `video.publish`, `video.list`, `user.info.basic`.
2. *Client Key* / *Client Secret* → `.env`.
3. Per Login-Kit-OAuth einen Access- und Refresh-Token für dein Konto holen → `TIKTOK_ACCESS_TOKEN`, `TIKTOK_REFRESH_TOKEN`.
4. App zur Prüfung einreichen, damit Videos öffentlich werden.

**Öffentliche URL (für Antworten per SMS/Sprache und für Instagram)**
```bash
cloudflared tunnel --url http://localhost:8787     # oder: jarvis tunnel
```
Die angezeigte `https://…trycloudflare.com`-Adresse in `config.yaml` → `notify.public_base_url` eintragen.
In Twilio bei deiner Nummer eintragen: *A message comes in* → Webhook `https://DEINE-URL/sms` (POST).

### 4. Prüfen und starten
```bash
content-crew doctor              # zeigt, was noch fehlt
content-crew --dry-run cycle     # Testlauf: Video wird erstellt, nichts hochgeladen, keine SMS
content-crew cycle               # ein echter Durchlauf
content-crew run                 # Dauerbetrieb (alle 4 Stunden ein Durchlauf + Webhook-Server)
content-crew status              # Übersicht über Videos und Learnings
```

Fertige Videos liegen in `data/videos/`, alles andere in `data/crew.db`.

### Wichtige Einstellungen (`config.yaml`)

| Einstellung | Bedeutung |
|---|---|
| `niche` | Dein Themengebiet |
| `boss.videos_per_cycle`, `boss.cycle_minutes` | Wie viele Videos wie oft |
| `boss.min_script_score` | Mindestnote, sonst muss der Autor nachbessern |
| `boss.auto_publish` | `false` = Jarvis fragt dich vor jedem Upload per SMS |
| `virality.*` | Ab wann ein Video als viral gilt (dann ruft Jarvis an) |
| `video.background_dir` | Ordner mit eigenen Clips/Bildern als Hintergrund |
| `video.voice` | Stimme, z. B. `de-DE-ConradNeural` (männlich) |

## Sicherheit

- `.env`, `config.yaml`, `secrets/` und `data/` werden **nicht** ins Git hochgeladen. Teile deine Tokens mit niemandem.
- Der Webhook-Server antwortet nur auf deine Nummer und prüft Twilio-Signaturen.
- Fang mit `auto_publish: false` an, bis du der Qualität vertraust.

## Entwicklung
```bash
uv pip install -e ".[all,dev]" httpx && pytest
```
