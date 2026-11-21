"""Rough audio preview of a MIDI arrangement (simple built-in synths) + optional vocal stem.
This is a QC/listening aid, NOT production audio - real sounds come from FL Studio + your samples."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .midi_io import read_midi_beats

SR = 44100


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _env(n, a=0.005, r=0.04):
    t = np.arange(n) / SR
    dur = n / SR
    return np.minimum(1, t / a) * np.clip((dur - t) / r, 0, 1)


def _saw(f, n, voices=(0, -0.11, 0.11, -0.2, 0.2)):
    t = np.arange(n) / SR
    return sum(2 * ((t * f * 2 ** (d / 12) + i * 0.13) % 1) - 1 for i, d in enumerate(voices)) / len(voices)


def _kick(n, pitch_offset=0, root_pc=9):
    t = np.arange(n) / SR
    semis = ((root_pc - 9 + 6) % 12) - 6          # nearest octave of the root around A1 (55 Hz)
    base = 55 * 2 ** ((semis + pitch_offset) / 12)
    f = base + 220 * np.exp(-t * 35)
    s = np.tanh(3 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 6)
    return s


def _snare(n):
    t = np.arange(n) / SR
    return (np.random.default_rng(0).standard_normal(n) * 0.6 + np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 25)


INSTR = {
    "lead": (lambda f, n: _saw(f, n), 0.10),
    "harmony": (lambda f, n: _saw(f, n), 0.06),
    "counter": (lambda f, n: _saw(f, n, (0, 0.08)), 0.05),
    "chords": (lambda f, n: _saw(f, n, (0, -0.15, 0.15)), 0.035),
    "bass": (lambda f, n: np.tanh(2 * _saw(f, n, (0,))), 0.16),
    "screech": (lambda f, n: np.sign(_saw(f, n, (0, 0.3))) * 0.7, 0.10),
}


def render(midi: Path, out: Path, bpm: float, vocals: Path | None = None, max_bars: int | None = None,
           kick_root_pc: int = 9) -> Path:
    """kick_root_pc: tune the preview kick to the key root (a pitched kick otherwise skews the key)."""
    tracks, _ = read_midi_beats(midi)
    spb = 60.0 / bpm
    last = max(n.end for ns in tracks.values() for n in ns)
    if max_bars:
        last = min(last, max_bars * 4)
    mix = np.zeros(int((last * spb + 2) * SR))
    for name, notes in tracks.items():
        low = name.lower()
        for n in notes:
            if n.start >= last:
                continue
            i0 = int(n.start * spb * SR)
            ln = int(max(0.03, n.dur * spb) * SR)
            if "kick" in low:
                sig = _kick(int(0.45 * SR), n.pitch - 60 if "tonal" in low else 0, kick_root_pc) * 0.55
            elif "snare" in low or "clap" in low:
                sig = _snare(int(0.15 * SR)) * 0.12 * (n.vel / 127)
            else:
                key = next((k for k in INSTR if k in low), "lead")
                fn, amp = INSTR[key]
                sig = fn(_hz(n.pitch), ln) * _env(ln) * amp * (n.vel / 127)
            j = min(len(mix), i0 + len(sig))
            mix[i0:j] += sig[: j - i0]
    if vocals and vocals.exists():
        import soundfile as sf
        v, sr = sf.read(str(vocals), dtype="float32", always_2d=True)
        v = v.mean(axis=1)
        if sr != SR:
            import librosa
            v = librosa.resample(v, orig_sr=sr, target_sr=SR)
        j = min(len(mix), len(v))
        mix[:j] += v[:j] * 0.9
    mix = np.tanh(mix * 1.2) * 0.9
    import soundfile as sf
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), mix.astype(np.float32), SR)
    return out
