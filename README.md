# Instagram-Agent-skill – Jarvis und sein KI-Content-Team

Jarvis (dein lokaler [OpenJarvis](https://github.com/open-jarvis/OpenJarvis)) ist der **Chef**.
Er steuert ein Team aus KI-Arbeitern, die rund um die Uhr Content für YouTube Shorts,
Instagram Reels und TikTok machen – und er meldet sich per **SMS oder Anruf** bei dir.
Dazu kommt eine **Shop-Abteilung** mit 14 weiteren Arbeitern, die einen Online-Shop (Shopify)
aufbauen und betreiben – zusammen **20 KI-Arbeiter** ([siehe unten](#die-shop-abteilung)).

```
                    ┌──────────────── Du ────────────────┐
                    │  SMS / Anruf  ▲          │ SMS / Sprache: STOP, STATUS, OK 12, Anweisungen
                    │               │          ▼
                    │        ┌─────────────────────┐
                    │        │  JARVIS (Chef)       │  plant Videos, bewertet Konzepte (1-10),
                    │        │                      │  schickt schlechte Arbeit zurück, lernt aus Zahlen
                    │        └──┬────┬────┬────┬───┘
                    │   Trend-  │Desig-│Anima-│Uploader│Analyst
                    │   Scout   │ner   │tor   │        │(viral?)
                    └───────────┴──────┴──────┴────────┴─────────
                       YouTube · Instagram · TikTok (offizielle APIs)
```

## Was die Arbeiter tun

| Arbeiter | Aufgabe |
|---|---|
| **Trend-Scout** | Sucht die erfolgreichsten Kurzvideos der letzten 7 Tage in deiner Nische (YouTube) und Top-Posts zum Hashtag (Instagram) und analysiert Hooks, Themen, Formate. |
| **Designer** | Entwirft das Konzept: Animationsart, Einstellungen, Farben, Melodie, Länge, Caption mit Frage, Hashtags. Muss nachbessern, bis Jarvis mindestens die Mindestnote gibt. |
| **Animator** | Rendert ein echtes animiertes Video (1080×1920, 60 fps, mit Musik) – **keine Sätze, keine Fotos**. Physik-Simulationen und „Satisfying“-Clips, siehe unten. Prüft danach Länge, Bewegung, Helligkeit und Ton. |
| **Uploader** | Lädt auf alle eingerichteten Plattformen hoch. |
| **Analyst** | Holt regelmäßig Aufrufe, Likes, Kommentare, Shares. Erkennt virale Videos (z. B. 3× dein Median und mind. 10.000 Aufrufe). |
| **Jarvis (Chef)** | Plant jede Runde neue Videos, bewertet streng, lernt aus den echten Zahlen („Fragen als Hook funktionieren“), richtet sich nach deinen Anweisungen. |

### Die Animationsarten

| Art | Was passiert | Spannung |
|---|---|---|
| **Ring-Flucht** (`ring_escape`) | Ball springt in bis zu 50 rotierenden Ringen mit Lücke, jede Lücke sprengt einen Ring | Zahl zählt die Ringe herunter |
| **Ball-Vermehrung** (`escape_multiply`) | Jeder entkommene Ball wird zu zwei neuen – bis der Ring platzt | Zahl zählt die Bälle hoch |
| **Wachsender Ball** (`growing_ball`) | Ball wird bei jedem Aufprall größer und malt ein Muster | Wann ist der Kreis voll? |
| **Farben-Krieg** (`color_wars`) | 2 oder 4 Teams erobern Felder (Pong-Wars-Prinzip) | Wer hat am Ende die meiste Fläche? |
| **Polyrhythmus** (`polyrhythm`) | Punkte auf Bögen, Welle oder Umlaufbahnen, jeder mit eigenem Ton | Countdown, bis sich alle treffen |
| **Galton-Brett** (`galton`) | Hunderte Kugeln fallen durch Nägel und bilden eine Glockenkurve | In welchem Fach landen die meisten? |
| **Dreh-Arena** (`spin_arena`) | Nummerierte Bälle in einem rotierenden Vieleck mit offener Seite | Welche Nummer bleibt als Letzte drin? |

**Story-Videos (auf Wunsch):** „24 Stunden bei den Dinos“ – ein leuchtendes Skelett reist durchs Zeitportal
(Silhouetten-Stil, Tageszeiten, T-Rex-Jagd, Gewitter, Lagerfeuer). Mit `ending: haustier` hängt am Ende ein
Baby-T-Rex am Knochenarm; mit `lang: en` erzählt das Skelett auf Englisch (offline-Stimme Kokoro, Modell wird beim
ersten Mal von GitHub geladen):

```bash
content-crew animate --type dino_trip --duration 58
```

**Story-Serie „24 Hours In …“ (auf Wunsch):** Das Skelett verbringt 24 Stunden in einer von sieben Welten –
Eiszeit, Arktis, Altes Ägypten, Dschungel, Savanne, Mittelalter, Wilder Westen – und erzählt auf Englisch. Jede Folge
hat denselben Spannungsbogen: sanfter Riese (Mammut, Giraffe, Kamel …), Raubtier-Verfolgung (Säbelzahntiger,
Eisbär, Krokodil, Jaguar, Löwe, Drache, Bison-Herde), Versteck, Unwetter (Schneesturm, Sandsturm, Tropenregen,
Gewitter, Staubsturm), Herde im Sonnenuntergang, Nacht unter Polarlicht, Sternen oder Glühwürmchen, Portal nach
Hause. Am Ende kommt ein Jungtier mit (`ending: pet`) oder leuchtende Augen erscheinen im Portal (`ending: eyes`,
Cliffhanger für Teil 2). `variant` wechselt die Formulierungen und Landschaften. Die Tiere stammen aus einem
Baukasten (`content_crew/animation/creatures.py`), der aus Körperproportionen und Extras Schattenrisse zeichnet.

```bash
content-crew animate --type adventure --duration 56
```

Jeder Aufprall spielt einen Ton – auf Wunsch Note für Note eine **gemeinfreie Melodie** (Für Elise, Ode an die
Freude, Bergkönig, Kanon in D, Jingle Bells, Stille Nacht …), damit TikTok den Ton nicht sperrt. Der Höhepunkt wird
automatisch auf die gewünschte Länge abgestimmt (die Physik wird vorab durchgerechnet). Selbst ausprobieren ohne KI:

```bash
content-crew animate --type ring_escape --music fur_elise --palette neon --duration 35
```

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

## Die Shop-Abteilung

14 weitere Arbeiter bauen mit Jarvis einen Online-Shop auf: Sie finden Produkte, rechnen, prüfen,
schreiben die Seiten, bauen die Website und kümmern sich später um Bestellungen und Zahlen.
**Nichts geht ohne deine Freigabe online, und Jarvis gibt kein Geld aus.**

| Abteilung | Arbeiter | Aufgabe |
|---|---|---|
| Einkauf | **Produkt-Scout** | Sucht Alltagshelfer, die ein Problem lösen und sich im Video gut zeigen lassen (Startsortiment mit 26 Produkten, danach Ideen von Jarvis). Saisonware zuerst. |
| | **Einkäufer** | Legt Herkunft, Einkaufspreis, Versand, Zoll und Lieferzeit fest. Ohne Angebot vom Lieferanten rechnet er vorsichtig mit dem oberen Schätzpreis. |
| | **Kalkulator** | Rechnet pro Bestellung mit Umsatzsteuer, Versand, Zoll, Zahlungsgebühr, Werbung und Rückerstattungen. Setzt den Preis so, dass mindestens `min_profit` übrig bleibt – sonst als 2er- oder 3er-Set, sonst fliegt das Produkt raus. Keine erfundenen „statt“-Preise. |
| | **Produktprüfer** | Sortiert aus, was für einen kleinen Shop rechtlich riskant ist: Elektronik/Akkus, Spielzeug und Kinderartikel, Kosmetik, Lebensmittelkontakt, Schmuck, Medizin, Waffen, Chemikalien, Markenware. Merkt Hinweise an (Textilkennzeichnung, Latex, Magnete …) und welche Angaben zur Produktsicherheit (GPSR) noch fehlen. |
| Website | **Webdesigner** | Baut Startseite, Kategorien, Menü und die Seiten Über uns, Versand, FAQ und Kontakt. |
| | **Produkttexter** | Schreibt jede Produktseite auf Deutsch – ohne Heilversprechen und Übertreibungen. |
| | **SEO-Experte** | Google-Titel, Beschreibung, Adresse (Handle) und Schlagwörter. |
| | **Rechts-Check** | Führt die Liste, was du vor dem Verkauf erledigen musst (Gewerbe, Impressum, Rechtstexte, Lieferant, GPSR, Verpackung). |
| | **Shop-Verwalter** | Überträgt freigegebene Produkte, Seiten und Kategorien nach Shopify. Ohne Zugang schreibt er eine Shopify-Importdatei (`data/shop/shopify-import.csv`). |
| Marketing | **Werbe-Manager** | Plant pro Produkt Video-Idee, Zielgruppe und einen Anzeigen-Test mit Stopp-Grenze (aus der Kalkulation). Bezahlte Werbung nur mit deiner Freigabe. |
| | **E-Mail-Marketing** | Entwürfe für Willkommensmail, Neuheiten-Newsletter und Warenkorb-Erinnerung. |
| Betrieb | **Bestell-Manager** | Holt Bestellungen aus Shopify, meldet neue und verspätete. |
| | **Kundenservice** | Pflegt die FAQ und beantwortet Kundenfragen. |
| | **Buchhalter** | Umsatz, Umsatzsteuer und Ergebnis der letzten 30 Tage, CSV pro Monat für die Steuerberatung. |

Die Shop-Runde läuft in jeder Jarvis-Runde mit. Neue Produkte landen im Dashboard unter **Shop**
(mit Freigeben/Ablehnen) und als SMS. Die **Shop-Vorschau** (`/shop` im Dashboard oder
`data/shop/vorschau.html`) zeigt, wie der Shop aussehen wird – mit Jarvis-Notizen zu Gewinn und Risiko.

| SMS / Dashboard | Befehl am PC | Wirkung |
|---|---|---|
| `SHOP` | `content-crew shop status` | Übersicht |
| `OK P3` / `NEIN P3` | `content-crew shop ok P3` | Produkt 3 freigeben / ablehnen |
| `PREIS P3 2,40` | `content-crew shop preis P3 2,40` | echten Einkaufspreis eintragen, der Kalkulator rechnet neu |
| | `content-crew shop` | eine Shop-Runde jetzt |
| | `content-crew shop export` | Shopify-Importdatei schreiben |
| | `content-crew shop fotos` | Produktfotos neu zusammenstellen (`fotos rendern`: fehlende Studiobilder mit Blender rechnen) |
| | `content-crew shop paket` | Shop-Paket als ZIP: Importdatei, Fotos, Druckdateien, Wallpaper, Seiten, Mails, Anleitung |

### Produktfotos aus dem 3D-Fotostudio

Jeder Alltagshelfer ist in `content_crew/shop/studio3d.py` als 3D-Modell in echten Maßen nachgebaut und
wird wie im Fotostudio ausgeleuchtet und mit Blender (Cycles) gerendert. Die Poster hängen gerahmt in einem
Wohnzimmer, die Wallpaper laufen auf drei Handys. Die fertigen Fotos liegen in `shop-assets/bilder/` – von dort
lädt Shopify sie beim Import der CSV-Datei. Neue Studiobilder brauchen die offizielle Blender-Version als
Python-Modul (mit Rauschfilter):

```bash
uv venv /opt/blender-studio --python 3.13 && VIRTUAL_ENV=/opt/blender-studio uv pip install bpy
content-crew shop fotos rendern      # einige Minuten pro Bild
```

Ohne Blender entstehen einfache Ersatzbilder. Wichtig: Die Studiobilder zeigen die Produkte so, wie sie
beschrieben sind – wähle beim Lieferanten genau so ein Produkt oder ersetze die Bilder durch seine Fotos.
Poster werden ohne Rahmen geliefert; das steht im Produkttext und unter den Bildern.

### So wird daraus ein echter Shop

1. **Gewerbe anmelden** (Österreich: Handelsgewerbe, online über usp.gv.at). Die Gründerberatung der WKO hilft gratis.
2. **Shopify-Konto** anlegen, Zahlungen einrichten, unter *Einstellungen → Richtlinien* AGB, Widerruf und Datenschutz erzeugen und prüfen lassen.
3. **Jarvis verbinden:** Im Shopify **Dev Dashboard** eine App anlegen, Berechtigungen `write_products`, `write_content`, `write_publications`, `read_orders` wählen, die App im Shop installieren und Client-ID und Secret mit `content-crew setup` eintragen. Jarvis holt sich damit selbst ein Zugangs-Token (gilt etwa 24 Stunden und wird erneuert).
4. **Lieferanten verbinden**, z. B. die CJdropshipping-App in Shopify (Lager in der EU wählen). Dort die von Jarvis angelegten Produkte mit dem Lieferantenprodukt verknüpfen – dann gehen Bestellungen automatisch an den Lieferanten.
5. Pro Produkt **Hersteller, EU-Verantwortlichen und Sicherheitshinweise** vom Lieferanten eintragen (GPSR) und Fotos hochladen. Erst dann schaltest du das Produkt aktiv (oder `auto_online: true`).
6. Impressum-Daten in `config.yaml` unter `shop.owner` eintragen und erledigte Punkte unter `shop.erledigt` abhaken.

Ehrlich gesagt: Einkaufs- und Versandpreise sind Schätzwerte, bis der Lieferant echte Zahlen liefert
(`PREIS P3 …`). Die Shopify-Anbindung ist gegen die Schnittstellen-Beschreibung gebaut und getestet,
aber noch nicht mit einem echten Shop ausprobiert – Fehler meldet der Shop-Verwalter im Dashboard und per SMS.
Gewinn garantiert niemand: Der Kalkulator sorgt nur dafür, dass sich jede **einzelne** Bestellung rechnet.

---

## Ehrlich: Was geht und was nicht

- **Nur offizielle APIs.** Kein Scraping, keine Bots, die sich als Mensch ausgeben – sonst werden Konten gesperrt.
- **TikTok:** Bis TikTok deine App geprüft hat („Audit“, dauert einige Tage bis Wochen), sind hochgeladene Videos **nur für dich sichtbar**. TikTok bietet keine Trend-Suche an; Trends kommen von YouTube/Instagram.
- **YouTube:** Neue Google-Cloud-Projekte laden Videos zunächst als **privat** hoch, bis die API-Prüfung („Audit“) bestanden ist. Das API-Kontingent reicht für etwa 6 Uploads pro Tag.
- **Instagram:** Nur mit **Business- oder Creator-Konto**, das mit einer Facebook-Seite verbunden ist. Instagram holt das Video von einer **öffentlichen URL** – den nötigen Tunnel startet Content Crew automatisch.
- **Qualität:** Die Animationen rechnet der Animator selbst – ohne Internet, ohne Grafikkarte, ohne Kosten. Echte KI-Videogeneratoren (fotorealistische Clips aus Text) brauchen eine starke Grafikkarte oder einen kostenpflichtigen Dienst und sind hier nicht eingebaut. Das Sprachmodell plant und bewertet nur – nimm mindestens `qwen3.5:9b`, mit Grafikkarte gern größer.
- **Alte Text-Videos** gibt es weiter mit `video.style: slides` in `config.yaml`.
- **Viral garantiert niemand.** Das System testet, misst und lernt – Erfolg braucht trotzdem Zeit.
- Der PC muss laufen, damit das Team arbeitet.

---

## Installation auf deinem PC

**Windows:** Jarvis läuft unter **WSL2**. Einmalig in PowerShell (als Administrator):
```powershell
wsl --install -d Ubuntu-24.04
```
PC neu starten, „Ubuntu“ aus dem Startmenü öffnen, Benutzername und Passwort festlegen. Alles Weitere im Ubuntu-Fenster.
**macOS/Linux:** direkt im Terminal.

### 1. Alles installieren (ein Befehl)
```bash
git clone -b claude/lucid-mendel-ht9zp8 https://github.com/trustking39-arch/Instagram-Agent-skill.git
cd Instagram-Agent-skill
bash scripts/install_pc.sh
```
Das installiert ffmpeg, cloudflared (Tunnel), uv, Jarvis (OpenJarvis + Ollama), das KI-Modell `qwen3.5:9b`
und dieses Projekt. Kleinerer PC ohne Grafikkarte? `MODEL=qwen3.5:4b bash scripts/install_pc.sh`

### 2. Konten anlegen (einmalig, einige Schritte musst du selbst machen)

| Dienst | Was du brauchst | Kosten |
|---|---|---|
| **Twilio** (twilio.com) | Konto + Telefonnummer mit Voice & SMS. *Account SID*, *Auth Token*. Im Testkonto deine Handynummer unter „Verified Caller IDs“ bestätigen. | ca. 1–2 €/Monat + Cent pro SMS/Minute |
| **Pexels** (pexels.com/api) | Kostenloser API-Key für Hintergrundvideos | kostenlos |
| **YouTube** (console.cloud.google.com) | Projekt → *YouTube Data API v3* aktivieren → **API-Schlüssel**. *OAuth-Zustimmungsbildschirm* (Extern, dich als Testnutzer) → *OAuth-Client-ID* Typ **Desktop-App** → JSON als `secrets/youtube_client_secret.json` speichern | kostenlos |
| **Instagram** (developers.facebook.com) | Instagram als **Business-/Creator-Konto**, verbunden mit einer **Facebook-Seite**. App vom Typ „Business“ anlegen → *App-ID* und *App-Geheimcode* | kostenlos |
| **TikTok** (developers.tiktok.com) | App anlegen, Produkte **Login Kit** und **Content Posting API** (Direct Post), Scopes `user.info.basic`, `video.publish`, `video.list`. Redirect-URI: `http://localhost:8788/callback/`. *Client Key*, *Client Secret*. App zur Prüfung einreichen. | kostenlos |

### 3. Zugänge eintragen (Assistent)
```bash
source .venv/bin/activate
content-crew setup            # fragt Nische, Twilio, Pexels, YouTube, Meta, TikTok ab
content-crew auth-youtube     # Browser-Login bei YouTube
content-crew auth-instagram   # Token aus dem Graph API Explorer einfügen – ID wird automatisch gefunden,
                              # der gespeicherte Token läuft nicht ab
content-crew auth-tiktok      # Browser-Login bei TikTok, Token wird automatisch erneuert
content-crew doctor           # zeigt, was noch fehlt
```
Du musst nichts von Hand in Dateien eintragen. Plattformen, die du (noch) nicht einrichtest, werden einfach übersprungen.

### 4. Testen
```bash
content-crew test-sms                  # SMS an dein Handy
content-crew test-call                 # Jarvis ruft dich an
content-crew --dry-run cycle           # Testlauf: Video wird erstellt, nichts hochgeladen, keine SMS
```
Das Testvideo liegt danach in `data/videos/`.

### 5. Starten
```bash
bash scripts/start.sh                  # startet Ollama, Jarvis und das Team
```
Beim Start passiert automatisch:
- Jarvis-Server wird gestartet, falls er nicht läuft
- ein Cloudflare-Tunnel gibt deinem PC eine öffentliche Adresse (für Instagram-Uploads und deine SMS-Antworten)
- diese Adresse wird automatisch bei deiner Twilio-Nummer als SMS-Webhook eingetragen
- du bekommst eine SMS „Jarvis ist gestartet“
- alle 4 Stunden läuft eine Runde: Zahlen prüfen → lernen → Trends → planen → Konzept → Animation → Upload

Weitere Befehle: `content-crew status` (Übersicht im Terminal), `content-crew publish 12` (Video 12 sofort hochladen).

### 6. Jarvis und das Team ansehen – am PC und auf dem Handy

- **Am PC:** im Browser **http://localhost:8787** öffnen (ohne Passwort).
- **Auf dem Handy:** Beim Start schickt dir Jarvis per SMS den Link (`https://….trycloudflare.com`).
  Öffnen, Passwort eingeben – du bleibst 30 Tage angemeldet. Tipp: im Browser „Zum Startbildschirm hinzufügen“.
- Das Passwort legst du in `content-crew setup` fest. Ohne Passwort erzeugt Jarvis beim Start eines und schickt es dir einmalig mit.
- Der Link ändert sich bei jedem Neustart – Jarvis schickt dir dann den neuen.
- Nach 10 falschen Passwörtern ist die Anmeldung 15 Minuten gesperrt.

Du siehst dort, woran jeder Arbeiter gerade arbeitet, alle Videos mit Player, was Jarvis gelernt hat und alle
Nachrichten an dich. Du kannst Jarvis Anweisungen geben, ihn pausieren und Videos freigeben oder verwerfen.

### 7. Automatisch beim Hochfahren starten

**Linux / macOS / WSL mit systemd:**
```bash
bash scripts/install_autostart.sh
```
**Windows:** Einmalig in WSL `sudo nano /etc/wsl.conf` → eintragen:
```
[boot]
systemd=true
```
In PowerShell `wsl --shutdown`, Ubuntu wieder öffnen, `bash scripts/install_autostart.sh` ausführen.
Damit WSL nach dem Windows-Start hochfährt: *Aufgabenplanung* → *Einfache Aufgabe* → Trigger „Bei Anmeldung“ →
Programm `wsl.exe`, Argumente `-d Ubuntu-24.04 -- true`. Energieoptionen: Ruhezustand ausschalten, sonst schläft das Team mit.

### Wichtige Einstellungen (`config.yaml`)

| Einstellung | Bedeutung |
|---|---|
| `niche` | Dein Themengebiet |
| `boss.videos_per_cycle`, `boss.cycle_minutes` | Wie viele Videos wie oft |
| `boss.min_script_score` | Mindestnote, sonst muss der Designer nachbessern |
| `video.style` | `animation` (Standard) oder `slides` (alte Text-Videos) |
| `boss.animation_revisions` | Wie oft der Designer ein Konzept überarbeiten muss (Standard 1) |
| `animation.fps`, `animation.preset` | 60 Bilder/s; `veryfast` rendert schneller, `medium` gibt kleinere Dateien |
| `boss.auto_publish` | `false` = Jarvis fragt dich vor jedem Upload per SMS |
| `virality.*` | Ab wann ein Video als viral gilt (dann ruft Jarvis an) |
| `video.background_dir`, `video.voice` | nur für `slides`: eigene Hintergründe, Stimme |

## Sicherheit

- `.env`, `config.yaml`, `secrets/` und `data/` werden **nicht** ins Git hochgeladen. Teile deine Tokens mit niemandem.
- Der Webhook-Server antwortet nur auf deine Nummer und prüft Twilio-Signaturen.
- Fang mit `auto_publish: false` an, bis du der Qualität vertraust.

## Entwicklung
```bash
uv pip install -e ".[all,dev]" httpx && pytest
```
