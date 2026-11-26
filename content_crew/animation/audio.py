"""Ton für die Animationen: jede Kollision spielt eine Note, dazu Hall und ein leiser Klangteppich.

Alles wird mit numpy berechnet, ohne Samples und ohne Internet. Die Melodien sind gemeinfreie
Klassiker und Volkslieder (Urheberrecht abgelaufen), damit TikTok den Ton nicht sperrt.
"""

from __future__ import annotations

import random
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SR = 44100

# Gemeinfreie Melodien als MIDI-Noten (C4 = 60). Jeder Aufprall spielt die nächste Note.
MELODIES: dict[str, list[int]] = {
    "fur_elise": [76, 75, 76, 75, 76, 71, 74, 72, 69, 60, 64, 69, 71, 64, 68, 71, 72, 64,
                  76, 75, 76, 75, 76, 71, 74, 72, 69, 60, 64, 69, 71, 64, 72, 71, 69],
    "ode_to_joy": [64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 64, 62, 62,
                   64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 62, 60, 60,
                   62, 62, 64, 60, 62, 64, 65, 64, 60, 62, 64, 65, 64, 62, 60, 62, 55,
                   64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 62, 60, 60],
    "mountain_king": [59, 61, 62, 64, 66, 62, 66, 65, 61, 65, 64, 60, 64,
                      59, 61, 62, 64, 66, 62, 66, 71, 69, 66, 62, 66, 69],
    "canon": [78, 76, 74, 73, 71, 69, 71, 73, 74, 73, 71, 69, 67, 66, 67, 64],
    "twinkle": [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60, 67, 67, 65, 65, 64, 64, 62,
                67, 67, 65, 65, 64, 64, 62, 60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60],
    "greensleeves": [69, 72, 74, 76, 77, 76, 74, 71, 67, 69, 71, 72, 69, 69, 68, 69, 71, 68, 64,
                     69, 72, 74, 76, 77, 76, 74, 71, 67, 69, 71, 72, 71, 69, 68, 66, 68, 69, 69],
    "jingle_bells": [64, 64, 64, 64, 64, 64, 64, 67, 60, 62, 64, 65, 65, 65, 65, 65, 64, 64, 64, 64,
                     62, 62, 64, 62, 67, 64, 64, 64, 64, 64, 64, 64, 67, 60, 62, 64, 65, 65, 65, 65,
                     65, 64, 64, 64, 67, 67, 65, 62, 60],
    "silent_night": [67, 69, 67, 64, 67, 69, 67, 64, 74, 74, 71, 72, 72, 67, 69, 69, 72, 71, 69,
                     67, 69, 67, 64, 69, 69, 72, 71, 69, 67, 69, 67, 64, 74, 74, 77, 74, 71, 72,
                     76, 72, 67, 64, 67, 65, 62, 60],
}

SCALES: dict[str, list[int]] = {
    "pentatonic": [0, 2, 4, 7, 9],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dreamy": [0, 2, 4, 6, 7, 9, 11],      # lydisch
    "japanese": [0, 2, 3, 7, 8],           # Hirajoshi
}

# Instrumente: Teiltöne als (Frequenz-Verhältnis, Lautstärke, Abklingzeit in s)
INSTRUMENTS: dict[str, list[tuple[float, float, float]]] = {
    "bell": [(1.0, 1.0, 1.5), (2.0, 0.35, 0.9), (3.0, 0.2, 0.55), (4.2, 0.12, 0.35), (5.4, 0.08, 0.22)],
    "marimba": [(1.0, 1.0, 0.55), (4.0, 0.28, 0.12), (10.0, 0.06, 0.04)],
    "pluck": [(float(n), 1.0 / n ** 1.15, 1.1 / n ** 0.7) for n in range(1, 10)],
    "glass": [(1.0, 1.0, 2.2), (2.76, 0.45, 1.3), (5.4, 0.22, 0.7), (8.93, 0.1, 0.35)],
    "kalimba": [(1.0, 1.0, 0.9), (5.9, 0.22, 0.12), (12.1, 0.06, 0.05)],
}


def midi_hz(pitch: float) -> float:
    return 440.0 * 2 ** ((pitch - 69) / 12)


@dataclass
class Note:
    t: float                # Zeitpunkt in Sekunden
    pitch: float            # MIDI-Note
    gain: float = 0.5
    pan: float = 0.0        # -1 links … +1 rechts
    kind: str = "tone"      # tone | tick | burst | boom | roar | thunder | whoosh | squeak | chomp
    accent: bool = False    # wird bei dichten Passagen nicht leiser gemacht (Finale)


class Music:
    """Liefert Tonhöhen: entweder Note für Note eine Melodie oder eine Melodie aus einer Tonleiter."""

    def __init__(self, choice: str, rng: random.Random):
        self.rng = rng
        self.melody = MELODIES.get(choice)
        self.scale = SCALES.get(choice) or (SCALES["major"] if self.melody else SCALES["pentatonic"])
        self.transpose = rng.choice([-3, -2, 0, 0, 2, 3]) if self.melody else 0
        self.root = 60 + rng.choice([-3, -1, 0, 2, 3, 5])
        self.pos = 0
        self.walk = len(self.scale)  # Startstufe für die Zufallsmelodie

    def next(self) -> float:
        """Nächste Note: Melodie weiterspielen oder schrittweise durch die Tonleiter wandern."""
        if self.melody:
            pitch = self.melody[self.pos % len(self.melody)] + self.transpose
            self.pos += 1
            return pitch
        step = self.rng.choice([-2, -1, -1, 1, 1, 2, 3, -3])
        self.walk = max(0, min(len(self.scale) * 3 - 1, self.walk + step))
        return self.degree(self.walk)

    def degree(self, i: int, octave_shift: int = 0) -> float:
        s = self.scale
        return self.root + 12 * (i // len(s) + octave_shift) + s[i % len(s)]

    def chord(self) -> list[float]:
        return [self.degree(0, -1), self.degree(2), self.degree(4), self.degree(len(self.scale), 0)]


def _tone(freq: float, instrument: str) -> np.ndarray:
    parts = INSTRUMENTS.get(instrument, INSTRUMENTS["bell"])
    scale = min(1.8, max(0.35, (261.63 / freq) ** 0.35))  # hohe Töne klingen kürzer
    longest = max(tau for _, _, tau in parts) * scale
    t = np.arange(int(min(3.0, 5 * longest) * SR)) / SR
    sig = np.zeros_like(t)
    for ratio, amp, tau in parts:
        f = freq * ratio
        if f < SR * 0.45:
            sig += amp * np.exp(-t / (tau * scale)) * np.sin(2 * np.pi * f * t)
    sig *= np.minimum(1.0, t / 0.003)
    peak = np.abs(sig).max()
    return (sig / peak if peak > 0 else sig).astype(np.float32)


def _burst(rng: np.random.Generator) -> np.ndarray:
    """Zersplittern: kurzes, helles Rauschen mit Glitzer."""
    t = np.arange(int(0.9 * SR)) / SR
    noise = rng.standard_normal(len(t))
    noise = np.diff(noise, prepend=0.0) * np.exp(-t / 0.09)
    sparkle = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / d)
                  for f, d in ((2637.0, 0.25), (3520.0, 0.18), (4186.0, 0.12)))
    sig = 0.6 * noise / (np.abs(noise).max() or 1) + 0.25 * sparkle
    return (sig / np.abs(sig).max()).astype(np.float32)


def _boom() -> np.ndarray:
    """Tiefer Schlag fürs Finale."""
    t = np.arange(int(1.2 * SR)) / SR
    freq = 45 + 75 * np.exp(-t / 0.08)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    sig = np.sin(phase) * np.exp(-t / 0.35) * np.minimum(1.0, t / 0.002)
    return sig.astype(np.float32)


def _roar(rng: np.random.Generator) -> np.ndarray:
    """Dino-Brüllen: knurrender Sägezahn mit Rauschen, leicht verzerrt."""
    t = np.arange(int(1.9 * SR)) / SR
    f = 92 * (1 + 0.3 * np.exp(-t / 0.35)) * (1 + 0.05 * np.sin(2 * np.pi * 7.5 * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    saw = sum(np.sin(k * phase) / k for k in range(1, 16))
    noise = np.convolve(rng.standard_normal(len(t)), np.ones(6) / 6, mode="same")
    env = np.minimum(1.0, t / 0.12) * np.exp(-np.maximum(0.0, t - 0.95) / 0.35)
    sig = np.tanh(2.4 * (0.75 * saw / np.abs(saw).max() + 0.55 * noise / np.abs(noise).max())) * env
    return (sig / np.abs(sig).max()).astype(np.float32)


def _thunder(rng: np.random.Generator) -> np.ndarray:
    """Donner: kurzer Knall, dann tiefes Grollen."""
    t = np.arange(int(3.2 * SR)) / SR
    n = rng.standard_normal(len(t))
    rumble = np.convolve(n, np.ones(160) / 160, mode="same")
    crack = np.diff(n, prepend=0.0) * np.exp(-t / 0.07)
    env = np.exp(-t / 1.2) * (0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 1.4 * t + rng.random() * 6)))
    sig = rumble / np.abs(rumble).max() * env + 0.3 * crack / np.abs(crack).max()
    return (sig / np.abs(sig).max()).astype(np.float32)


def _whoosh(rng: np.random.Generator) -> np.ndarray:
    """Zeitportal: aufsteigendes Rauschen mit Ton-Sweep."""
    dur = 1.4
    t = np.arange(int(dur * SR)) / SR
    f = 160 + 1100 * (t / dur) ** 2
    sweep = np.sin(2 * np.pi * np.cumsum(f) / SR)
    noise = np.diff(rng.standard_normal(len(t)), prepend=0.0)
    env = np.sin(np.pi * t / dur) ** 2
    sig = (0.6 * sweep + 0.4 * noise / np.abs(noise).max()) * env
    return (sig / np.abs(sig).max()).astype(np.float32)


def _squeak(rng: np.random.Generator) -> np.ndarray:
    """Mini-Brüller eines Baby-Dinos: kurzer, hoher Quietsch-Sweep mit Zittern."""
    dur = 0.45
    t = np.arange(int(dur * SR)) / SR
    f = (980 - 520 * t / dur) * (1 + 0.06 * np.sin(2 * np.pi * 28 * t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    sig = (np.sin(phase) + 0.35 * np.sin(2 * phase) + 0.15 * np.sin(3 * phase)) * np.sin(np.pi * t / dur) ** 0.6
    return (sig / np.abs(sig).max()).astype(np.float32)


def _chomp(rng: np.random.Generator) -> np.ndarray:
    """Zuschnappen: zwei harte Klicks und ein dumpfer Schlag."""
    t = np.arange(int(0.35 * SR)) / SR
    click = np.diff(rng.standard_normal(len(t)), prepend=0.0)
    sig = click * (np.exp(-t / 0.006) + 0.8 * np.exp(-np.maximum(0.0, t - 0.05) / 0.006) * (t > 0.05))
    sig += 0.8 * np.sin(2 * np.pi * (140 - 200 * t) * t) * np.exp(-t / 0.06)
    return (sig / np.abs(sig).max()).astype(np.float32)


def _pad(duration: float, root: float, rng: np.random.Generator) -> np.ndarray:
    """Leiser Klangteppich (Grundton, Quinte, Oktave) mit langsamem Atmen."""
    n = int(duration * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for interval, amp in ((-12, 0.5), (-5, 0.35), (0, 0.3), (7, 0.15)):
        f = midi_hz(root + interval)
        for detune in (-0.0025, 0.0025):
            lfo = 0.6 + 0.4 * np.sin(2 * np.pi * (0.07 + rng.random() * 0.06) * t + rng.random() * 6.28)
            out += amp * lfo * (np.sin(2 * np.pi * f * (1 + detune) * t) + 0.2 * np.sin(4 * np.pi * f * t))
    env = np.minimum(1.0, t / 2.5) * np.minimum(1.0, (duration - t) / 2.0).clip(0)
    out *= env
    peak = np.abs(out).max()
    return (out / peak if peak > 0 else out).astype(np.float32)


def _reverb(x: np.ndarray, rng: np.random.Generator, rt60: float = 1.9) -> np.ndarray:
    m = int(2.6 * SR)
    t = np.arange(m) / SR
    ir = rng.standard_normal(m) * np.exp(-6.9 * t / rt60)
    ir[: int(0.022 * SR)] = 0.0
    ir = np.convolve(ir, np.ones(5) / 5, mode="same")  # etwas dunkler
    ir /= np.sqrt(np.sum(ir ** 2))
    nfft = 1 << int(np.ceil(np.log2(len(x) + m)))
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]
    return y.astype(np.float32)


def render_audio(notes: list[Note], duration: float, path: Path, instrument: str = "bell",
                 pad_root: float | None = None, seed: int = 0, reverb: float = 0.3,
                 voice: np.ndarray | None = None) -> None:
    """Noten zu einer Stereo-WAV-Datei mischen."""
    rng = np.random.default_rng(seed)
    n = max(1, int(duration * SR))
    total = n + int(3.2 * SR)
    left = np.zeros(total, np.float32)
    right = np.zeros(total, np.float32)

    damp = np.ones(len(notes))
    if notes:  # viele Noten gleichzeitig -> jede etwas leiser, sonst wird es Matsch
        times = np.array([nt.t for nt in notes])
        order = np.argsort(times, kind="stable")
        ts = times[order]
        dens = np.empty(len(ts))
        dens[order] = np.searchsorted(ts, ts + 0.06, "right") - np.searchsorted(ts, ts - 0.06)
        damp = 1.0 / np.sqrt(np.maximum(1.0, dens / 2.5))

    cache: dict[tuple, np.ndarray] = {}
    for k, note in enumerate(notes):
        start = int(note.t * SR)
        if start >= n or start < 0:
            continue
        if note.kind == "burst":
            key = ("burst",)
            if key not in cache:
                cache[key] = _burst(rng)
        elif note.kind == "boom":
            key = ("boom",)
            if key not in cache:
                cache[key] = _boom()
        elif note.kind in ("roar", "thunder", "whoosh", "squeak", "chomp"):
            key = (note.kind,)
            if key not in cache:
                cache[key] = {"roar": _roar, "thunder": _thunder, "whoosh": _whoosh, "squeak": _squeak,
                              "chomp": _chomp}[note.kind](rng)
        else:
            inst = "marimba" if note.kind == "tick" else instrument
            key = (inst, round(note.pitch, 2))
            if key not in cache:
                cache[key] = _tone(midi_hz(note.pitch), inst)
        wav = cache[key]
        seg = wav[: total - start]
        gain = note.gain * (1.0 if note.accent else damp[k])
        pan = max(-1.0, min(1.0, note.pan)) * 0.6
        left[start:start + len(seg)] += seg * gain * np.cos((pan + 1) * np.pi / 4)
        right[start:start + len(seg)] += seg * gain * np.sin((pan + 1) * np.pi / 4)

    if pad_root is not None:
        pad = _pad(n / SR, pad_root, rng) * 0.07
        left[:n] += pad
        right[:n] += pad

    if reverb > 0:
        left = left + reverb * _reverb(left, rng)
        right = right + reverb * _reverb(right, rng)

    mix = np.stack([left[:n], right[:n]], axis=1)
    if voice is not None:  # Erzählstimme: Musik wird leiser, solange gesprochen wird
        v = np.zeros(n, np.float32)
        v[: min(n, len(voice))] = voice[:n]
        win = int(0.3 * SR)
        env = np.convolve(np.abs(v), np.ones(win) / win, mode="same")
        env = np.clip(env / (env.max() or 1.0) * 6, 0.0, 1.0)
        music = float(np.percentile(np.abs(mix), 99.5)) or 1.0
        mix = mix / music * 0.5 * (1 - 0.62 * env)[:, None] + v[:, None]
    level = float(np.percentile(np.abs(mix), 99.9)) or 1.0
    mix = np.tanh(mix * (0.9 / level))  # sanfter Limiter
    fade = min(n, int(0.4 * SR))
    mix[n - fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    pcm = (mix * 32000).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
