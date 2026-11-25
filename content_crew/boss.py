"""Jarvis, der Chef: plant, verteilt Aufgaben, prüft Qualität, lernt aus Zahlen, meldet sich beim Besitzer."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time

from content_crew.config import Config
from content_crew.db import DB
from content_crew.llm import LLM
from content_crew.notify import Notifier
from content_crew.platforms import Platform, PlatformError, load_platforms
from content_crew.workers import Analyst, Publisher, ScriptWriter, TrendScout, VideoProducer

log = logging.getLogger(__name__)

BOSS_SYSTEM = (
    "Du bist Jarvis, Chef eines KI-Content-Teams. Dein Ziel: Kurzvideos, die viral gehen und dem Kanal "
    "des Besitzers Reichweite bringen. Du entscheidest Themen, gibst deinen Arbeitern klare, konkrete "
    "Anweisungen, bewertest ihre Arbeit streng und lernst aus den echten Zahlen. Anweisungen des Besitzers "
    "haben immer Vorrang. Wenn dir eine wichtige Information fehlt, stellst du dem Besitzer eine kurze Frage."
)


class Boss:
    def __init__(self, cfg: Config, db: DB, llm: LLM, notifier: Notifier,
                 platforms: dict[str, Platform] | None = None, producer: VideoProducer | None = None):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        self.notifier = notifier
        self.platforms = platforms if platforms is not None else load_platforms(cfg)
        self.scout = TrendScout(llm, self.platforms)
        self.writer = ScriptWriter(llm, cfg.get("language", "de"))
        self.producer = producer
        self.publisher = Publisher(cfg, self.platforms)
        self.analyst = Analyst(cfg, db, self.platforms)

    # ------------------------------------------------------------------
    def _producer(self) -> VideoProducer:
        if self.producer is None:
            self.producer = VideoProducer(self.cfg)
        return self.producer

    def report_errors(self, errors: list[PlatformError], context: str) -> None:
        """Blockierende Fehler (Login abgelaufen usw.) per Anruf melden, aber höchstens 1x pro Tag."""
        for exc in errors:
            text = f"{context}: {exc}"
            if not exc.blocked:
                log.warning(text)
                continue
            key = "alert_" + hashlib.sha1(text.encode()).hexdigest()[:12]
            last = float(self.db.get_state(key, "0"))
            if time.time() - last > 24 * 3600:
                self.db.set_state(key, str(time.time()))
                self.notifier.notify("blocked", f"Jarvis hier. Ich komme nicht weiter. {text}. Bitte kümmere dich darum.")

    def handle_inbox(self) -> list[str]:
        """Nachrichten des Besitzers abarbeiten. Gibt freie Anweisungen zurück."""
        instructions = []
        for msg in self.db.take_inbox():
            m = re.fullmatch(r"APPROVE (\d+)", msg["text"])
            if m:
                self.publish(int(m.group(1)))
            else:
                instructions.append(msg["text"])
                self.db.add_note("instruction", msg["text"])
        return instructions

    # --- Planung & Qualitätskontrolle ----------------------------------
    def plan(self, insights: dict, learnings: list[str], instructions: list[str], n: int) -> dict:
        recent = [v["script"]["title"] for v in self.db.videos(limit=15)]
        prompt = {
            "nische": self.cfg["niche"],
            "trend_analyse": {k: insights.get(k) for k in ("patterns", "hooks", "topics", "formats", "avoid")},
            "unsere_learnings": learnings,
            "aktueller_fokus": self.db.notes("focus", 1),
            "anweisungen_vom_besitzer": instructions + self.db.notes("instruction", 5),
            "bereits_gemacht_nicht_wiederholen": recent,
        }
        result = self.llm.chat_json(
            BOSS_SYSTEM,
            json.dumps(prompt, ensure_ascii=False, indent=1)
            + f"\n\nPlane genau {n} neue Kurzvideo(s). JSON: "
            '{"ideas": [{"idea": "konkrete Idee mit Hook", "why": "warum das viral gehen kann", '
            '"instructions": "konkrete Anweisung an den Skript-Autor"}], '
            '"question_for_owner": "nur falls dir wirklich etwas Wichtiges fehlt, sonst leer"}',
        )
        if not isinstance(result, dict):
            result = {"ideas": result if isinstance(result, list) else []}
        result["ideas"] = [i for i in result.get("ideas", []) if isinstance(i, dict) and i.get("idea")][:n]
        return result

    def review(self, script: dict) -> dict:
        result = self.llm.chat_json(
            BOSS_SYSTEM,
            "Bewerte dieses Kurzvideo-Skript streng von 1 bis 10 (Hook, Tempo, Mehrwert, Viral-Potenzial, "
            "Call-to-Action). Gib konkrete Verbesserungen an. Enthält das Skript Heilversprechen, medizinische "
            "Behauptungen, Finanz-/Erfolgsgarantien oder irreführende Aussagen, ist der Score höchstens 3 – "
            "solche Videos verstoßen gegen die Plattform-Regeln.\n"
            f"{json.dumps(script, ensure_ascii=False)}\n"
            'JSON: {"score": 7, "feedback": "konkrete Verbesserungen"}',
            temperature=0.2,
        )
        try:
            score = float(result.get("score", 0))
        except (TypeError, ValueError, AttributeError):
            score = 0.0
        feedback = result.get("feedback", "") if isinstance(result, dict) else ""
        return {"score": score, "feedback": feedback if isinstance(feedback, str) else json.dumps(feedback)}

    def create_video(self, idea: dict, insights: dict, learnings: list[str]) -> int | None:
        bcfg = self.cfg["boss"]
        act = self.db.set_activity
        brief = idea["idea"] + (f"\nAnweisung vom Chef: {idea['instructions']}" if idea.get("instructions") else "")
        act("writer", f"schreibt: {idea['idea'][:80]}")
        script = self.writer.write(brief, insights, learnings)
        act("writer", f"Entwurf fertig: „{script['title']}“")
        act("jarvis", f"bewertet „{script['title']}“")
        verdict = self.review(script)
        for attempt in range(int(bcfg["max_revisions"])):
            if verdict["score"] >= bcfg["min_script_score"]:
                break
            log.info("Chef: Skript %.0f/10 – zurück an den Autor (%d)", verdict["score"], attempt + 1)
            act("jarvis", f"Note {verdict['score']:.0f}/10 – schickt das Skript zurück: {verdict['feedback'][:120]}")
            act("writer", f"bessert nach (Versuch {attempt + 2})")
            script = self.writer.write(brief, insights, learnings, previous=script, feedback=verdict["feedback"])
            act("writer", f"Überarbeitung fertig: „{script['title']}“")
            verdict = self.review(script)
        act("jarvis", f"Note {verdict['score']:.0f}/10 für „{script['title']}“")
        act("writer", "wartet")
        video_id = self.db.add_video(idea["idea"], script, verdict["score"])
        if verdict["score"] < bcfg["min_script_score"]:
            self.db.update_video(video_id, status="rejected")
            self.db.add_note("log", f"Video {video_id} verworfen (Score {verdict['score']}): {verdict['feedback']}")
            log.info("Chef: Skript %d verworfen (Score %.0f)", video_id, verdict["score"])
            return None
        try:
            act("producer", f"schneidet Video #{video_id} ({len(script['scenes'])} Szenen)")
            path = self._producer().produce(script, video_id)
            act("producer", f"Video #{video_id} fertig")
        except Exception as exc:  # noqa: BLE001
            act("producer", f"Fehler bei Video #{video_id}")
            self.db.update_video(video_id, status="failed")
            self.notifier.notify("error", f"Video {video_id} konnte nicht erstellt werden: {exc}"[:300])
            log.exception("Videoproduktion fehlgeschlagen")
            return None
        self.db.update_video(video_id, path=str(path), status="produced")
        if bcfg.get("auto_publish", True):
            self.publish(video_id)
        else:
            self.db.update_video(video_id, status="awaiting_approval")
            self.notifier.notify(
                "approval",
                f"Neues Video #{video_id}: \"{script['title']}\" (Score {verdict['score']:.0f}/10). "
                f"Antworte OK {video_id} zum Hochladen oder NEIN {video_id}.",
            )
        return video_id

    def publish(self, video_id: int) -> None:
        video = self.db.video(video_id)
        if not video or not video.get("path"):
            return
        from pathlib import Path

        self.db.set_activity("publisher", f"lädt Video #{video_id} hoch")
        ids, errors = self.publisher.publish(Path(video["path"]), video["script"])
        self.db.set_activity("publisher", f"Video #{video_id}: {', '.join(ids) or 'keine Plattform'}"
                             + (" (Testmodus)" if self.cfg.dry_run else ""))
        self.report_errors(errors, f"Upload von Video {video_id}")
        if ids:
            self.db.update_video(video_id, status="published", platform_ids={**video["platform_ids"], **ids})
            self.notifier.notify("published", f"Hochgeladen: \"{video['script']['title']}\" auf {', '.join(ids)}.")
        elif not errors:
            self.db.add_note("log", f"Video {video_id}: keine Plattform eingerichtet")

    # --- Lernen aus Zahlen ---------------------------------------------
    def learn(self) -> None:
        table = self.analyst.performance_table()
        if len(table) < 2:
            return
        result = self.llm.chat_json(
            BOSS_SYSTEM,
            "Das sind die echten Zahlen unserer Videos:\n"
            + json.dumps(table[:25], ensure_ascii=False, indent=1)
            + '\n\nWas funktioniert, was nicht? JSON: {"learnings": ["konkrete Regel fürs Team"], '
              '"next_focus": "worauf wir uns jetzt konzentrieren", "summary_for_owner": "2 Sätze"}',
            temperature=0.3,
        )
        if not isinstance(result, dict):
            return
        for item in result.get("learnings", [])[:5]:
            self.db.add_note("learning", str(item))
        if result.get("next_focus"):
            self.db.add_note("focus", str(result["next_focus"]))
        last = float(self.db.get_state("last_report", "0"))
        if result.get("summary_for_owner") and time.time() - last > 24 * 3600:
            self.db.set_state("last_report", str(time.time()))
            self.notifier.notify("report", f"Tagesbericht von Jarvis: {result['summary_for_owner']}")

    # --- Durchlauf -------------------------------------------------------
    def run_cycle(self) -> list[int]:
        instructions = self.handle_inbox()
        if self.db.paused:
            log.info("Jarvis ist pausiert (Besitzer hat STOP geschickt).")
            return []

        act = self.db.set_activity
        act("jarvis", "leitet eine neue Runde")
        act("analyst", "holt Aufrufe, Likes und Kommentare")
        hits, errors = self.analyst.refresh()
        act("analyst", f"fertig – {len(hits)} neue virale Videos")
        self.report_errors(errors, "Statistiken")
        for hit in hits:
            self.notifier.notify(
                "viral",
                f"Gute Nachrichten! Dein Video \"{hit['title']}\" geht auf {hit['platform']} viral: "
                f"{hit['views']} Aufrufe.",
            )
        act("jarvis", "wertet die Zahlen aus und lernt daraus")
        self.learn()

        act("scout", f"sucht Trends zu „{self.cfg['niche']}“")
        insights = self.scout.run(self.cfg["niche"])
        act("scout", f"fertig – {insights.get('sample_size', 0)} Videos analysiert")
        act("jarvis", "plant die nächsten Videos")
        self.report_errors([PlatformError(e, blocked=True) for e in insights.get("_blocked", [])], "Trend-Analyse")
        learnings = self.db.notes("learning", 10)
        plan = self.plan(insights, learnings, instructions, int(self.cfg["boss"]["videos_per_cycle"]))
        question = plan.get("question_for_owner")
        question = question.strip() if isinstance(question, str) else ""
        if len(question) > 3:
            self.notifier.notify("question", f"Frage von Jarvis: {question}", ask=True)

        created = []
        for idea in plan["ideas"]:
            vid = self.create_video(idea, insights, learnings)
            if vid:
                created.append(vid)
        self.db.set_state("last_cycle", str(time.time()))
        act("jarvis", f"Runde fertig – {len(created)} Video(s). Wartet auf die nächste Runde")
        return created

    def run_forever(self) -> None:
        minutes = float(self.cfg["boss"]["cycle_minutes"])
        log.info("Jarvis startet. Durchlauf alle %.0f Minuten.", minutes)
        while True:
            try:
                created = self.run_cycle()
                log.info("Durchlauf fertig, %d Video(s) erstellt.", len(created))
            except Exception as exc:  # noqa: BLE001
                log.exception("Durchlauf fehlgeschlagen")
                self.notifier.notify("error", f"Jarvis-Durchlauf fehlgeschlagen: {exc}"[:300])
            deadline = time.time() + minutes * 60
            while time.time() < deadline:  # zwischendurch Freigaben/Befehle verarbeiten
                time.sleep(30)
                if self.db.conn.execute("SELECT 1 FROM inbox WHERE handled=0 LIMIT 1").fetchone():
                    self.handle_inbox()
