"""Audio -> MIDI (Basic Pitch, ONNX backend) and MIDI cleanup.

Two versions per stem:
  1. faithful  : every detected note, mapped onto the song's beat grid, NOT quantized
  2. cleaned   : false notes / overtones / octave errors removed, quantized, legato fixed
The cleaned version never rewrites pitches into the key - out-of-key notes are reported, not "fixed".
"""
from __future__ import annotations

import io
import contextlib
from pathlib import Path

import numpy as np

from .midi_io import Note, seconds_to_beats
from .project import HSPError
from . import theory as T

PRESETS = {
    # role, fmin, fmax, onset_thr, frame_thr, min_len_ms, mono, priority
    "vocals": dict(role="melody", fmin=80, fmax=1400, onset=0.5, frame=0.3, min_ms=70, mono=True, top=True),
    "bass": dict(role="bass", fmin=30, fmax=330, onset=0.45, frame=0.3, min_ms=70, mono=True, top=False),
    "other": dict(role="poly", fmin=55, fmax=4200, onset=0.5, frame=0.3, min_ms=60, mono=False, top=True),
    "piano": dict(role="poly", fmin=27, fmax=4200, onset=0.5, frame=0.3, min_ms=50, mono=False, top=True),
    "guitar": dict(role="poly", fmin=70, fmax=1400, onset=0.5, frame=0.3, min_ms=60, mono=False, top=True),
}


def basic_pitch_notes(audio: Path, preset: dict) -> list[tuple[float, float, int, float]]:
    try:
        from basic_pitch import FilenameSuffix, build_icassp_2022_model_path
        from basic_pitch.inference import predict
    except ImportError as e:
        raise HSPError("basic-pitch mangler. Se SETUP.md (installeres med --no-deps på Python 3.12+).") from e
    model = build_icassp_2022_model_path(FilenameSuffix.onnx)
    with contextlib.redirect_stdout(io.StringIO()):
        _, _, events = predict(str(audio), model, onset_threshold=preset["onset"], frame_threshold=preset["frame"],
                               minimum_note_length=preset["min_ms"], minimum_frequency=preset["fmin"],
                               maximum_frequency=preset["fmax"], multiple_pitch_bends=False, melodia_trick=True)
    return [(float(s), float(e), int(p), float(a)) for s, e, p, a, *_ in events]


def active_bars(audio: Path, bar_times: list[float], rel_db: float = -22.0) -> list[bool]:
    """Bars where the stem actually plays (RMS within rel_db of the loudest bar). Leakage from other
    instruments in Demucs stems is usually 25-40 dB down, so notes in inactive bars are dropped."""
    import librosa
    y, sr = librosa.load(str(audio), sr=22050, mono=True)
    out = []
    rms = []
    for a, b in zip(bar_times[:-1], bar_times[1:]):
        seg = y[int(max(0, a) * sr): int(b * sr)]
        rms.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    ref = max(rms) if rms else 1.0
    for r in rms:
        out.append(20 * np.log10((r + 1e-12) / (ref + 1e-12)) > rel_db)
    return out


def events_to_notes(events, beat_times, bpm) -> list[Note]:
    out = []
    for s, e, p, a in events:
        bs, be = seconds_to_beats([s, e], beat_times, bpm)
        out.append(Note(float(bs), float(max(be - bs, 0.01)), p, int(np.clip(a * 127 * 1.3, 20, 127))))
    return sorted(out, key=lambda n: (n.start, -n.pitch))


# ------------------------------------------------------------------ cleanup steps
def _overlap(a: Note, b: Note) -> float:
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))


def remove_overtones(notes: list[Note], stats: dict) -> list[Note]:
    keep = []
    for n in notes:
        ghost = False
        for m in notes:
            if m is n or m.vel < n.vel:
                continue
            if n.pitch - m.pitch in (12, 19, 24) and _overlap(n, m) >= 0.6 * n.dur:
                ghost = True
                break
        if ghost:
            stats["overtones_removed"] += 1
        else:
            keep.append(n)
    return keep


def merge_fragments(notes: list[Note], gap: float, stats: dict) -> list[Note]:
    notes = sorted(notes, key=lambda n: (n.pitch, n.start))
    out: list[Note] = []
    for n in notes:
        if out and out[-1].pitch == n.pitch and n.start - out[-1].end <= gap:
            prev = out[-1]
            prev.dur = max(prev.end, n.end) - prev.start
            prev.vel = max(prev.vel, n.vel)
            stats["fragments_merged"] += 1
        else:
            out.append(Note(n.start, n.dur, n.pitch, n.vel))
    return sorted(out, key=lambda n: (n.start, -n.pitch))


def drop_weak(notes: list[Note], min_beats: float, stats: dict) -> list[Note]:
    if not notes:
        return notes
    vmax = max(n.vel for n in notes)
    keep = []
    for n in notes:
        if n.dur < min_beats and n.vel < 0.6 * vmax:
            stats["short_weak_removed"] += 1
        elif n.vel < 0.22 * vmax:
            stats["quiet_removed"] += 1
        else:
            keep.append(n)
    return keep


def skyline(notes: list[Note], top: bool, stats: dict) -> tuple[list[Note], list[Note]]:
    """Split into a monophonic line (highest or lowest voice) and the remainder (harmony)."""
    notes = sorted(notes, key=lambda n: (n.start, -n.pitch if top else n.pitch))
    line, rest = [], []
    for n in notes:
        if line and _overlap(line[-1], n) > 0.5 * min(n.dur, line[-1].dur):
            better = n.pitch > line[-1].pitch if top else n.pitch < line[-1].pitch
            if better and n.vel >= 0.5 * line[-1].vel:
                rest.append(line.pop())
                line.append(n)
            else:
                rest.append(n)
        else:
            line.append(n)
    stats["moved_to_harmony"] = len(rest)
    return line, rest


def fix_octaves(line: list[Note], stats: dict, window: int = 4) -> list[Note]:
    p = np.array([n.pitch for n in line], dtype=float)
    for i, n in enumerate(line):
        nb = np.r_[p[max(0, i - window):i], p[i + 1:i + 1 + window]]
        if len(nb) < 2:
            continue
        med = float(np.median(nb))
        for shift in (-12, 12):
            if abs(n.pitch - med) >= 10 and abs(n.pitch + shift - med) <= abs(n.pitch - med) - 7:
                n.pitch += shift
                p[i] = n.pitch
                stats["octave_fixes"] += 1
                break
    return line


def choose_grid(notes: list[Note]) -> tuple[float, str, dict]:
    if not notes:
        return 0.25, "1/16", {}
    starts = np.array([n.start for n in notes])
    errs = {}
    for g, name in ((0.25, "1/16"), (1 / 3, "1/8T"), (0.5, "1/8")):
        errs[name] = float(np.mean(np.abs(starts / g - np.round(starts / g)) * g))
    # prefer 1/16 unless triplets fit clearly better; 1/8 only if as good as 1/16
    best = "1/16"
    if errs["1/8T"] < 0.6 * errs["1/16"]:
        best = "1/8T"
    elif errs["1/8"] <= errs["1/16"] * 1.05:
        best = "1/8"
    g = {"1/16": 0.25, "1/8T": 1 / 3, "1/8": 0.5}[best]
    return g, best, {k: round(v, 4) for k, v in errs.items()}


def quantize(notes: list[Note], grid: float, legato: bool, stats: dict) -> list[Note]:
    out = []
    for n in notes:
        s = round(n.start / grid) * grid
        e = max(s + grid, round(n.end / grid) * grid)
        if abs(s - n.start) > 1e-6:
            stats["quantized"] += 1
        out.append(Note(s, e - s, n.pitch, n.vel))
    out.sort(key=lambda n: (n.start, -n.pitch))
    # dedupe identical notes created by quantization
    ded = []
    for n in out:
        if ded and ded[-1].start == n.start and ded[-1].pitch == n.pitch:
            ded[-1].dur = max(ded[-1].dur, n.dur)
            stats["duplicates_removed"] += 1
        else:
            ded.append(n)
    if legato:
        for a, b in zip(ded, ded[1:]):
            if b.start > a.start:
                if a.end > b.start:
                    a.dur = b.start - a.start          # remove overlaps in a mono line
                elif b.start - a.end < grid + 1e-6:
                    a.dur = b.start - a.start          # close tiny gaps -> smooth phrasing
                    stats["legato_fixed"] += 1
    return ded


def fold_range(notes: list[Note], lo: int, hi: int, stats: dict) -> list[Note]:
    for n in notes:
        while n.pitch < lo:
            n.pitch += 12
            stats["range_folded"] += 1
        while n.pitch > hi:
            n.pitch -= 12
            stats["range_folded"] += 1
    return notes


def out_of_key(notes: list[Note], key: str) -> list[dict]:
    tonic, mode = T.parse_key(key)
    pcs = set(T.scale_pcs(tonic, mode)) | set(T.scale_pcs(tonic, "harmonic_minor" if mode == "minor" else mode))
    return [{"bar": int(n.start // 4) + 1, "beat": round(n.start % 4 + 1, 2), "note": T.midi_to_name(n.pitch)}
            for n in notes if n.pitch % 12 not in pcs]


def clean(notes: list[Note], stem: str, key: str, active: list[bool] | None = None) -> tuple[dict[str, list[Note]], dict]:
    pr = PRESETS.get(stem, PRESETS["other"])
    stats = {k: 0 for k in ("overtones_removed", "fragments_merged", "short_weak_removed", "quiet_removed",
                            "octave_fixes", "quantized", "duplicates_removed", "legato_fixed", "range_folded")}
    stats["input_notes"] = len(notes)
    ns = [Note(n.start, n.dur, n.pitch, n.vel) for n in notes]
    stats["leakage_removed"] = 0
    if active:
        keep = []
        for n in ns:
            b = int(n.start // 4)
            if 0 <= b < len(active) and not active[b]:
                stats["leakage_removed"] += 1
            else:
                keep.append(n)
        ns = keep
    if pr["role"] == "poly":
        ns = remove_overtones(ns, stats)
    ns = merge_fragments(ns, gap=0.08, stats=stats)
    ns = drop_weak(ns, min_beats=0.2, stats=stats)
    out: dict[str, list[Note]] = {}
    if pr["role"] in ("melody", "bass"):
        line, _ = skyline(ns, top=pr["top"], stats=stats)
        line = fix_octaves(line, stats)
        g, gname, gerr = choose_grid(line)
        line = quantize(line, g, legato=True, stats=stats)
        if pr["role"] == "bass":
            line = fold_range(line, 28, 55, stats)   # E1..G3 (FL: E2..G4 is MIDI 40..; see theory naming)
        out["melody" if pr["role"] == "melody" else "bass"] = line
    else:
        line, rest = skyline(ns, top=True, stats=stats)
        line = fix_octaves(line, stats)
        g, gname, gerr = choose_grid(ns)
        out["melody"] = quantize(line, g, legato=True, stats=stats)
        out["harmony"] = quantize(rest, g, legato=False, stats=stats)
    stats["grid"] = gname
    stats["grid_errors_beats"] = gerr
    stats["output_notes"] = {k: len(v) for k, v in out.items()}
    allout = [n for v in out.values() for n in v]
    stats["out_of_key_notes"] = out_of_key(allout, key)[:50]
    stats["out_of_key_ratio"] = round(len(out_of_key(allout, key)) / max(1, len(allout)), 3)
    return out, stats
