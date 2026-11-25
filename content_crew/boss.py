"""Jarvis, der Chef: plant, verteilt Aufgaben, prüft Qualität, lernt aus Zahlen, meldet sich beim Besitzer."""

from __future__ import annotations

import hashlib
import json
import random
import logging
import re
import time

from content_crew.animation.catalog import TYPES, type_for
from content_crew.config import Config
from content_crew.db import DB
from content_crew.llm import LLM
from content_crew.notify import Notifier
from content_crew.platforms import Platform, PlatformError, load_platforms
from content_crew.workers import Analyst, Publisher, ScriptWriter, TrendScout, VideoProducer
from content_crew.workers.animator import AnimationDesigner, Animator

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
        self.style = cfg["video"].get("style", "animation")
        self.designer = AnimationDesigner(llm, ki_text=bool(cfg.get("animation", {}).get("ki_captions", False)))
        self.animator: Animator | None = None
        self.publisher = Publisher(cfg, self.platforms)
        self.analyst = Analyst(cfg, db, self.platforms)

    # ------------------------------------------------------------------
    def _producer(self) -> VideoProducer:
        if self.producer is None:
            self.producer = VideoProducer(self.cfg)
        return self.producer

    def _animator(self) -> Animator:
        if self.animator is None:
            self.animator = Animator(self.cfg)
        return self.animator

    def vary(self, concept: dict) -> dict:
        """Abwechslung erzwingen: andere Farben, Musik und Einstellungen als die letzten Videos derselben Art."""
        from content_crew.animation.catalog import MELODIES, PALETTES, SCALE_ONLY, SCALES, make_text, pick_hashtags
        from content_crew.animation.catalog import random_concept

        same = [v["script"] for v in self.db.videos(limit=40) if v["script"].get("type") == concept["type"]][:3]
        if not same:
            return concept
        rng = random.Random(concept["seed"])
        used = {s.get("palette") for s in same}
        if concept["palette"] in used:
            concept["palette"] = rng.choice([p for p in PALETTES if p not in used] or list(PALETTES))
        music_pool = list(SCALES) if concept["type"] in SCALE_ONLY else list(MELODIES)
        heard = {s.get("music") for s in same}
        if concept["music"] in heard:
            concept["music"] = rng.choice([m for m in music_pool if m not in heard] or music_pool)
        if any(s.get("params") == concept["params"] for s in same):
            concept["params"] = random_concept(concept["type"], rng)["params"]
        if not self.designer.ki_text:
            concept["title"], concept["caption"] = make_text(concept["type"], concept["params"], concept["music"],
                                                             concept["seed"])
        concept["hashtags"] = pick_hashtags(concept["hashtags"], concept["type"], concept["music"])
        concept["hook"] = f"{concept['label']} · {concept['music']} · Farben {concept['palette']}"
        return concept

    def recent_animations(self, limit: int = 8) -> list[str]:
        return [f"{v['script'].get('hook', '')} – „{v['script']['title']}“" for v in self.db.videos(limit=limit)
                if v["script"].get("type") in TYPES]

    def next_animation_type(self) -> str:
        """Abwechslung: die Animationsart, die am längsten nicht dran war."""
        used = [v["script"].get("type") for v in self.db.videos(limit=20)]
        return min(TYPES, key=lambda k: (k in used, -used.index(k) if k in used else 0))

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
    def plan(self, insights: dict, learnings: list[str], instructions: list[str], n: int,
             niche: str | None = None) -> dict:
        recent = [v["script"]["title"] for v in self.db.videos(limit=15)]
        if self.style == "animation":
            recent = self.recent_animations(15)
        prompt = {
            "nische": niche or self.cfg["niche"],
            "trend_analyse": {k: insights.get(k) for k in ("patterns", "hooks", "topics", "formats", "avoid")},
            "unsere_learnings": learnings,
            "aktueller_fokus": self.db.notes("focus", 1),
            "anweisungen_vom_besitzer": instructions + self.db.notes("instruction", 5),
            "bereits_gemacht_nicht_wiederholen": recent,
        }
        if self.style == "animation":
            kinds = {k: f"{v['label']}: {v['idee']}" for k, v in TYPES.items()}
            task = (f"\n\nPlane genau {n} neue ANIMIERTE Kurzvideo(s) für TikTok – keine Sätze im Bild, keine "
                    "Fotos, nur hochwertige Animation mit Musik. Unser Animator kann: "
                    + json.dumps(kinds, ensure_ascii=False) + "\nJSON: "
                    '{"ideas": [{"type": "ring_escape", "idea": "konkrete Idee: Animation, Melodie, Farben, '
                    'Höhepunkt", "why": "warum das viral gehen kann", "instructions": "konkrete Anweisung an '
                    'den Animations-Designer"}], "question_for_owner": "nur falls dir wirklich etwas Wichtiges '
                    'fehlt, sonst leer"}')
        else:
            task = (f"\n\nPlane genau {n} neue Kurzvideo(s). JSON: "
                    '{"ideas": [{"idea": "konkrete Idee mit Hook", "why": "warum das viral gehen kann", '
                    '"instructions": "konkrete Anweisung an den Skript-Autor"}], '
                    '"question_for_owner": "nur falls dir wirklich etwas Wichtiges fehlt, sonst leer"}')
        result = self.llm.chat_json(BOSS_SYSTEM, json.dumps(prompt, ensure_ascii=False, indent=1) + task)
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
            "solche Videos verstoßen gegen die Plattform-Regeln. Weniger als 5 Szenen ist zu kurz für ein "
            "Kurzvideo: dann höchstens 5.\n"
            f"{json.dumps(script, ensure_ascii=False)}\n"
            'JSON: {"score": 7, "feedback": "konkrete Verbesserungen"}',
            temperature=0.2,
        )
        return self._verdict(result)

    @staticmethod
    def _verdict(result) -> dict:
        try:
            score = float(result.get("score", 0))
        except (TypeError, ValueError, AttributeError):
            score = 0.0
        feedback = result.get("feedback", "") if isinstance(result, dict) else ""
        return {"score": score, "feedback": feedback if isinstance(feedback, str) else json.dumps(feedback)}

    def review_animation(self, concept: dict, recent: list[str]) -> dict:
        shown = {k: concept.get(k) for k in ("type", "label", "params", "palette", "music", "sound", "duration",
                                             "title", "caption", "hashtags")}
        result = self.llm.chat_json(
            BOSS_SYSTEM,
            "Bewerte dieses Konzept für ein animiertes TikTok-Video streng von 1 bis 10: Spannung ab Sekunde 1, "
            "klarer Höhepunkt, passende Melodie und Farben, Abwechslung zu unseren letzten Videos, Caption mit "
            "Frage (lädt zu Kommentaren ein), passende Hashtags. Unwahre oder irreführende Caption: höchstens 3.\n"
            f"Unsere letzten Videos: {'; '.join(recent) or 'noch keine'}\n"
            f"{json.dumps(shown, ensure_ascii=False)}\n"
            'JSON: {"score": 7, "feedback": "konkrete Verbesserungen"}',
            temperature=0.2,
        )
        return self._verdict(result)

    def create_animation(self, idea: dict, insights: dict, learnings: list[str],
                         publish: bool | None = None) -> int | None:
        """Designer entwirft, Jarvis prüft und schickt zurück, der Animator rendert."""
        bcfg = self.cfg["boss"]
        act = self.db.set_activity
        kind = idea.get("type") if idea.get("type") in TYPES else type_for(idea.get("idea", ""))
        brief = idea["idea"] + (f"\nAnweisung vom Chef: {idea['instructions']}" if idea.get("instructions") else "")
        recent = self.recent_animations()
        act("writer", f"entwirft: {idea['idea'][:80]}")
        concept = self.vary(self.designer.design(brief, insights, learnings, kind=kind, recent=recent))
        act("writer", f"Konzept fertig: „{concept['title']}“ ({concept['label']})")
        act("jarvis", f"prüft das Konzept „{concept['title']}“")
        verdict = self.review_animation(concept, recent)
        for attempt in range(int(bcfg.get("animation_revisions", 1))):
            if verdict["score"] >= bcfg["min_script_score"]:
                break
            log.info("Chef: Konzept %.0f/10 – zurück an den Designer (%d)", verdict["score"], attempt + 1)
            act("jarvis", f"Note {verdict['score']:.0f}/10 – schickt das Konzept zurück: {verdict['feedback'][:120]}")
            act("writer", f"bessert nach (Versuch {attempt + 2})")
            concept = self.vary(self.designer.design(brief, insights, learnings, kind=concept["type"],
                                                     previous=concept, feedback=verdict["feedback"], recent=recent))
            act("writer", f"Überarbeitung fertig: „{concept['title']}“")
            verdict = self.review_animation(concept, recent)
        act("jarvis", f"Note {verdict['score']:.0f}/10 für „{concept['title']}“")
        act("writer", "wartet")
        video_id = self.db.add_video(idea["idea"], concept, verdict["score"])
        if verdict["score"] <= 3:  # nur Regelverstöße verwerfen – die Bildqualität liefert die Engine
            self.db.update_video(video_id, status="rejected")
            self.db.add_note("log", f"Video {video_id} verworfen (Score {verdict['score']}): {verdict['feedback']}")
            return None
        try:
            act("producer", f"animiert Video #{video_id}: {concept['label']}, {concept['duration']} s")
            path, info = self._animator().produce(concept, video_id)
            act("producer", f"Video #{video_id} fertig ({info['duration']:.0f} s, {info['fps']} fps, "
                            f"{info['notes']} Töne)")
        except Exception as exc:  # noqa: BLE001
            act("producer", f"Fehler bei Video #{video_id}")
            self.db.update_video(video_id, status="failed")
            self.notifier.notify("error", f"Video {video_id} konnte nicht erstellt werden: {exc}"[:300])
            log.exception("Animation fehlgeschlagen")
            return None
        concept["render"] = info
        self.db.update_video(video_id, script=concept, path=str(path), status="produced")
        if info["problems"]:
            act("jarvis", f"Video #{video_id} fällt durch die Prüfung: {', '.join(info['problems'])}")
            self.db.update_video(video_id, status="rejected")
            return None
        act("jarvis", f"Video #{video_id} geprüft: {info['duration']:.0f} s, Höhepunkt bei {info['climax_at']} s – ok")
        return self._after_production(video_id, concept, verdict, publish)

    def _after_production(self, video_id: int, script: dict, verdict: dict, publish: bool | None) -> int:
        auto = self.cfg["boss"].get("auto_publish", True) if publish is None else publish
        if auto:
            self.publish(video_id)
        elif publish is False:
            self.db.update_video(video_id, status="awaiting_approval")
        else:
            self.db.update_video(video_id, status="awaiting_approval")
            self.notifier.notify(
                "approval",
                f"Neues Video #{video_id}: \"{script['title']}\" (Score {verdict['score']:.0f}/10). "
                f"Antworte OK {video_id} zum Hochladen oder NEIN {video_id}.",
            )
        return video_id

    def create_video(self, idea: dict, insights: dict, learnings: list[str],
                     publish: bool | None = None) -> int | None:
        if self.style == "animation":
            return self.create_animation(idea, insights, learnings, publish)
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
        return self._after_production(video_id, script, verdict, publish)

    def publish(self, video_id: int, only: list[str] | None = None) -> None:
        video = self.db.video(video_id)
        if not video or not video.get("path"):
            return
        from pathlib import Path

        self.db.set_activity("publisher", f"lädt Video #{video_id} hoch")
        ids, errors = self.publisher.publish(Path(video["path"]), video["script"], only=only)
        self.db.set_activity("publisher", f"Video #{video_id}: {', '.join(ids) or 'keine Plattform'}"
                             + (" (Testmodus)" if self.cfg.dry_run else ""))
        self.report_errors(errors, f"Upload von Video {video_id}")
        if ids:
            self.db.update_video(video_id, status="published", platform_ids={**video["platform_ids"], **ids})
            self.notifier.notify("published", f"Hochgeladen: \"{video['script']['title']}\" auf {', '.join(ids)}.")
        elif not errors:
            self.db.add_note("log", f"Video {video_id}: keine Plattform eingerichtet")

    # --- Serienproduktion ----------------------------------------------
    def run_batch(self, niches: list[str], count: int) -> list[int]:
        """count Videos über mehrere Nischen erstellen; sie warten danach auf den Upload.

        count <= 0 heißt: ohne Ende weiterproduzieren, bis der Besitzer STOP schickt.
        """
        endless = count <= 0
        created: list[int] = []
        learnings = self.db.notes("learning", 10)
        instructions = self.db.notes("instruction", 3)
        insights_cache: dict[str, dict] = {}
        attempts = 0
        while endless or (len(created) < count and attempts < count * 2):
            if endless:
                instructions = self.handle_inbox() + self.db.notes("instruction", 3)
                if self.db.paused:
                    self.db.set_activity("jarvis", "pausiert (STOP) – Dauerproduktion angehalten")
                    break
                if attempts and attempts % 50 == 0:
                    insights_cache.clear()  # Trends regelmäßig neu ansehen
                    learnings = self.db.notes("learning", 10)
            niche = niches[attempts % len(niches)]
            attempts += 1
            kind = type_for(niche) if self.style == "animation" else None
            topic = TYPES[kind]["query"] if kind else niche
            act = self.db.set_activity
            act("jarvis", f"Serie: Video {len(created) + 1}{'' if endless else f' von {count}'} – „{niche}“")
            try:
                if topic not in insights_cache:
                    act("scout", f"analysiert, was bei „{niche}“ viral geht")
                    insights_cache[topic] = self.scout.run(topic)
                    act("scout", f"fertig mit „{niche}“")
                if kind:
                    # Die Art steht fest: Jarvis gibt dem Designer direkt den Auftrag (spart einen KI-Aufruf
                    # pro Video). Bewertet und zurückgeschickt wird trotzdem jedes Konzept.
                    orders = "; ".join(instructions[:3])
                    plan = {"ideas": [{"idea": TYPES[kind]["idee"], "type": kind, "instructions": (
                        "Andere Farben und Musik als bei unseren letzten Videos. "
                        + (f"Anweisungen des Besitzers: {orders}" if orders else ""))}]}
                else:
                    plan = self.plan(insights_cache[topic], learnings, instructions, 1, niche=niche)
                for idea in plan["ideas"]:
                    if kind:
                        idea["type"] = kind
                    idea["idea"] = f"[{niche}] {idea['idea']}"
                    vid = self.create_video(idea, insights_cache[topic], learnings, publish=False)
                    if vid:
                        created.append(vid)
            except Exception as exc:  # noqa: BLE001
                log.exception("Serienvideo in %s fehlgeschlagen", niche)
                act("jarvis", f"Fehler in „{niche}“: {exc}"[:200])
        done = "pausiert (STOP)" if endless and self.db.paused else "Serie fertig"
        self.db.set_activity("jarvis", f"{done} – {len(created)} Videos warten auf den Upload")
        return created

    def publish_pending(self, only: list[str] | None = None) -> list[int]:
        pending = [v["id"] for v in self.db.videos(status="awaiting_approval", limit=500)]
        for vid in reversed(pending):
            self.publish(vid, only=only)
        return pending

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

        kind = self.next_animation_type() if self.style == "animation" else None
        topic = TYPES[kind]["query"] if kind else self.cfg["niche"]
        act("scout", f"sucht Trends zu „{TYPES[kind]['label'] if kind else topic}“")
        insights = self.scout.run(topic)
        act("scout", f"fertig – {insights.get('sample_size', 0)} Videos analysiert")
        act("jarvis", "plant die nächsten Videos")
        self.report_errors([PlatformError(e, blocked=True) for e in insights.get("_blocked", [])], "Trend-Analyse")
        learnings = self.db.notes("learning", 10)
        plan = self.plan(insights, learnings, instructions, int(self.cfg["boss"]["videos_per_cycle"]),
                         niche=TYPES[kind]["label"] if kind else None)
        if kind:
            recent_kinds = [v["script"].get("type") for v in self.db.videos(limit=2)]
            for idea in plan["ideas"]:
                if idea.get("type") not in TYPES or idea.get("type") in recent_kinds:
                    idea["type"] = kind  # Abwechslung statt fünfmal dasselbe
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
        if self.db.get_state("call_when_done") == "1":
            self.db.set_state("call_when_done", "0")
            self.notifier.call(self.cycle_summary(created, insights), kind="done", ask=True)
        return created

    def cycle_summary(self, created: list[int], insights: dict) -> str:
        titles = [self.db.video(v)["script"]["title"] for v in created]
        parts = [f"Hallo, hier ist Jarvis. Mein Team ist fertig. Wir haben {len(created)} neue Videos gemacht."]
        if titles:
            parts.append("Titel: " + "; ".join(titles) + ".")
        patterns = insights.get("patterns") or []
        if patterns and isinstance(patterns, list):
            parts.append("Was gerade viral geht: " + "; ".join(str(p) for p in patterns[:3]) + ".")
        if self.cfg.dry_run:
            parts.append("Wir sind noch im Testmodus, es wurde nichts hochgeladen.")
        return " ".join(parts)

    def run_forever(self) -> None:
        minutes = float(self.cfg["boss"]["cycle_minutes"])
        log.info("Jarvis startet. Durchlauf alle %.0f Minuten.", minutes)
        while True:
            try:
                created = self.run_cycle()
                log.info("Durchlauf fertig, %d Video(s) erstellt.", len(created))
            except Exception as exc:  # noqa: BLE001
                log.exception("Durchlauf fehlgeschlagen")
                self.db.set_activity("jarvis", f"Runde abgebrochen: {exc}"[:200])
                self.notifier.notify("error", f"Jarvis-Durchlauf fehlgeschlagen: {exc}"[:300])
            deadline = time.time() + minutes * 60
            while time.time() < deadline:  # zwischendurch Freigaben/Befehle verarbeiten
                time.sleep(30)
                if self.db.conn.execute("SELECT 1 FROM inbox WHERE handled=0 LIMIT 1").fetchone():
                    self.handle_inbox()
