"""Style-based full production: section plan + the user's own samples (edited where needed) + generated gap
sounds + MIDI parts + vocal arrangement -> one organised FL Studio project.

Style "cinematic_raw_zaag": Phuture Noize-like cinematic intro and euphoric first drop, Rebelion-like rawstyle
second drop (kick gaps, off-kicks, screech call/response), zaag/uptempo ending (meant to run at 200 BPM).
No melodies or audio from those artists are used: only general genre traits.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path, PureWindowsPath

import numpy as np

from . import compose as C
from . import theory as T
from .midi_io import Note

STYLE_CINEMATIC_RAW_ZAAG = [
    # name, role, bars, vocal source (src_start, src_len) or None
    ("Cinematic Intro", "intro_cinematic", 16, None),
    ("Breakdown", "breakdown", 16, "verse"),
    ("Build-up", "buildup", 16, None),
    ("Euphoric Drop", "drop_euphoric", 32, "hook"),
    ("Transition", "midbreak", 16, "hook"),
    ("Build-up 2", "buildup2", 16, None),
    ("Rawstyle Drop", "drop_raw", 32, None),
    ("Zaag (200 BPM)", "zaag", 16, None),
]


def _shift(ns, beats):
    return [Note(n.start + beats, n.dur, n.pitch, n.vel) for n in ns]


def _hits(bars: int, beats: list[float], pitch: int = 60, vel: int = 115, dur: float = 0.25, every: int = 1):
    out = []
    for b in range(0, bars, every):
        for x in beats:
            out.append(Note(b * 4 + x, dur, pitch, vel))
    return out


def best_rotation(prog: list[str], src_chords: list[str], src_start: int, n: int) -> int:
    """Rotation k so that prog[(i+k)%L] best matches the source chords from src_start (1-based) for n bars."""
    L = len(prog)
    roots = [T.parse_chord(c)[0] for c in prog]
    best, bk = -1, 0
    for k in range(L):
        score = 0
        for i in range(n):
            j = src_start - 1 + i
            if 0 <= j < len(src_chords) and src_chords[j] not in ("N", None):
                score += roots[(i + k) % L] == T.parse_chord(src_chords[j])[0]
        if score > best:
            best, bk = score, k
    return bk


def prepare_samples(staged: dict[str, Path], out_dir: Path, key_pc: int) -> dict[str, dict]:
    """staged: role -> local copy of the user's file. Edits (pitch / length) go to out_dir as new files;
    originals are never modified. Returns role -> {"local": Path, "edited": bool, "note": str}."""
    import soundfile as sf
    from pedalboard import time_stretch
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}
    for role, src in staged.items():
        spec = EDITS.get(role)
        if not spec:
            res[role] = {"local": src, "edited": False, "note": "original"}
            continue
        y, sr = sf.read(str(src), dtype="float32", always_2d=True)
        semis = spec.get("semis", 0)
        factor = 1.0
        if spec.get("to_bars"):
            bars, bpm = spec["to_bars"]
            factor = (len(y) / sr) / (bars * 240.0 / bpm)
        z = time_stretch(y.T, sr, stretch_factor=factor, pitch_shift_in_semitones=semis, high_quality=True).T
        z = z / max(1e-9, float(np.max(np.abs(z)))) * 10 ** (-1 / 20)
        name = f"{src.stem}{spec['suffix']}.wav"
        dest = out_dir / name
        sf.write(str(dest), z.astype(np.float32), sr, subtype="PCM_24")
        res[role] = {"local": dest, "edited": True, "note": spec["why"]}
    return res


# per-role edits for this song (G# minor, 160 -> 200 BPM). Pitch keeps tempo, stretch keeps pitch.
EDITS = {
    "zaag_loop": {"semis": 1, "suffix": "_to_G#", "why": "zaag-loop i G -> G# (+1 halvtone), tempo uendret (8 takter @200)"},
    "tension_riser": {"to_bars": (8, 160), "suffix": "_8bars_160", "why": "155 BPM-riser strukket til nøyaktig 8 takter @160"},
    "screech_loop": {"semis": 2, "suffix": "_to_G#", "why": "screech-loop i F# -> G# (+2 halvtoner), tempo uendret"},
}


def plan_sections(analysis: dict, bpm_target: float = 160) -> list[dict]:
    vocals = (analysis.get("vocals") or {}).get("regions", [])
    regs = sorted(vocals, key=lambda r: r["start_bar"])
    verse = regs[0] if regs else None
    hook = max(regs, key=lambda r: r["length_bars"]) if len(regs) == 1 else (regs[1] if len(regs) > 1 else None)
    out, bar = [], 1
    for name, role, length, vsrc in STYLE_CINEMATIC_RAW_ZAAG:
        src = {"verse": verse, "hook": hook}.get(vsrc) if vsrc else None
        vs = None
        if src:
            vs = {"src_start_bar": src["start_bar"], "src_end_bar": src["end_bar"],
                  "target_length_bars": min(length, src["end_bar"] - src["start_bar"] + 1, 16)}
        out.append({"name": name, "role": role, "start_bar": bar, "length_bars": length,
                    "end_bar": bar + length - 1, "vocal_source": vs})
        bar += length
    return out


def render_parts(sections: list[dict], key: str, prog: list[str], bars_per_chord: int, src_chords: list[str],
                 seed: int = 2) -> tuple[dict[str, list[Note]], list[tuple[float, str]]]:
    expanded = [c for c in prog for _ in range(bars_per_chord)]
    tonic, mode = T.parse_key(key)
    tr: dict[str, list[Note]] = {}
    markers = []

    def put(name, notes, off, L):
        tr.setdefault(name, []).extend(_shift([n for n in notes if n.start < L * 4], off))

    base_h = C.Harmony(key, expanded)
    lead16 = C.lead(base_h, 16, seed=seed, center=69, style="euphoric")
    for s in sections:
        off, L, role = (s["start_bar"] - 1) * 4, s["length_bars"], s["role"]
        markers.append((off, s["name"]))
        vs = s.get("vocal_source")
        k = best_rotation(expanded, src_chords, vs["src_start_bar"], vs["target_length_bars"]) if vs else 0
        h = C.Harmony(key, expanded[k:] + expanded[:k])
        dark = h.darker() if mode == "major" else C.Harmony(key, h.names)  # song already minor: keep chords
        lead = C.lead(h, 16, seed=seed, center=69) if vs else lead16

        def tile(ns, period):
            o = []
            for q in range(0, L, period):
                o += _shift(ns, q * 4)
            return o

        if role == "intro_cinematic":
            put("Cinematic Pad", C.chords(h, L, "sustain", low=55, high=74, add_root=False), off, L)
            put("Atmosphere", [Note(0, 4 * 12, 60, 100)], off, L)
            put("Riser", [Note((L - 6) * 4, 24, 60, 110)], off, L)
        elif role == "breakdown":
            put("Cinematic Pad", C.chords(h, L, "sustain", low=55, high=74, add_root=False), off, L)
            put("Chords", C.chords(h, L, "sustain"), off, L)
            put("Lead", tile(lead, 16), off, L)
            put("Counter", tile(C.countermelody(h, lead, 16), 16), off, L)
        elif role in ("buildup", "buildup2"):
            put("Snare", C.snare_roll(8), off, L)                       # one-shot roll, first half
            put("Snare Build", [Note(8 * 4, 32, 60, 115)], off, L)      # 8-bar loop @160, second half
            put("Tension Riser", [Note(8 * 4, 32, 60, 110)], off, L)
            put("Chords", C.chords(h, L, "offbeat" if role == "buildup" else "gated"), off, L)
            put("Reverse Crash", [Note((L - 3) * 4, 12, 60, 110)], off, L)
            if role == "buildup2":
                put("Kick Roll", [Note((L - 3) * 4, 12, 60, 120)], off, L)   # 3.1 bars @160
                put("Vocal Shout", [Note((L - 2) * 4, 8, 60, 120)], off, L)
                put("Uplifter", [Note((L - 5) * 4, 20, 60, 105)], off, L)
            else:
                put("Kick", _shift(C.kick_roll(1), (L - 1) * 4), off, L)
        elif role == "drop_euphoric":
            put("Impact", [Note(0, 8, 60, 127)], off, L)
            put("Kick", C.kick_pattern(L, "euphoric"), off, L)
            put("Clap", _hits(L, [1, 3], 60, 110), off, L)
            put("Bass", C.bass(h, L, "offbeat"), off, L)
            put("Chords", C.chords(h, L, "sustain"), off, L)
            put("Lead", tile(lead, 16), off, L)
            put("Lead Harmony", tile(C.harmonize(h, lead), 16), off, L)
        elif role == "midbreak":
            put("Cinematic Pad", C.chords(dark, L, "sustain", low=55, high=74, add_root=False), off, L)
            put("Atmosphere", [Note(0, 48, 60, 90)], off, L)
            put("Lead", C.lead(dark, 8, seed=seed + 1, center=66), off, L)
        elif role == "drop_raw":
            put("Impact", [Note(0, 8, 60, 127)], off, L)
            # rawstyle kick pattern (gaps, off-kicks, rolls); the G# kick follows the chord root (+-6 semitones)
            raw = []
            for n in C.kick_pattern(L, "rawstyle"):
                semis = ((dark.chord(int(n.start // 4))[0] - tonic + 6) % 12) - 6
                raw.append(Note(n.start, n.dur, 60 + semis, n.vel))
            put("Raw Kick", raw, off, L)
            put("Screech", C.screech(dark, L, seed=seed + 2, base=48), off, L)
            put("Screech FX", [Note(q * 4, 16, 60, 115) for q in range(4, L, 8)], off, L)   # 4-bar loop, every 8 bars
            put("Clap Loop", [Note(q * 4, 16, 60, 110) for q in range(0, L, 4)], off, L)     # 4-bar loop @160
            put("Uplifter", [Note((L - 5) * 4, 20, 60, 105)], off, L)
        elif role == "zaag":
            put("Zaag Kick", [Note(q * 4, 32, 60, 127) for q in range(0, L, 8)], off, L)     # 8-bar loop @200
            put("Noise FX", [Note(0, 32, 60, 100)], off, L)
            put("Shout Hardcore", [Note(0, 16, 60, 120)], off, L)
            put("Shout Rave", [Note(8 * 4, 24, 60, 120)], off, L)
            put("Impact", [Note((L - 1) * 4, 4, 60, 127)], off, L)
    return {k: v for k, v in tr.items() if v}, markers


# Channel order on the Playlist (top to bottom)
ORDER = ["Lead", "Lead Harmony", "Counter", "Chords", "Bass", "Cinematic Pad", "Atmosphere", "Kick", "Raw Kick",
         "Zaag Kick", "Kick Roll", "Clap", "Clap Loop", "Snare", "Snare Build", "Screech", "Screech FX", "Riser",
         "Tension Riser", "Uplifter", "Reverse Crash", "Impact", "Noise FX", "Vocal Shout", "Shout Hardcore", "Shout Rave"]
FLEX = {"Lead", "Lead Harmony", "Counter", "Chords", "Bass"}
