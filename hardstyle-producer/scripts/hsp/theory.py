"""Music theory helpers: note names, keys, scales, chords. Pure Python, no deps."""
from __future__ import annotations

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "D minor", "G minor", "C minor", "F minor", "Bb minor", "Eb minor"}

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],          # natural minor
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],       # common in rawstyle
}

CHORD_QUALITIES = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
}


def pc_name(pc: int, flats: bool = False) -> str:
    return (NOTE_NAMES_FLAT if flats else NOTE_NAMES_SHARP)[pc % 12]


def midi_to_name(n: int, flats: bool = False) -> str:
    """FL Studio convention: MIDI 60 = C5."""
    return f"{pc_name(n, flats)}{n // 12}"


def name_to_pc(name: str) -> int:
    name = name.strip()
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[name[0].upper()]
    for ch in name[1:]:
        if ch == "#":
            base += 1
        elif ch == "b":
            base -= 1
    return base % 12


def parse_key(key: str) -> tuple[int, str]:
    """'A minor' / 'Db major' / 'F# minor' -> (tonic_pc, mode)."""
    parts = key.replace("_", " ").split()
    tonic = name_to_pc(parts[0])
    mode = parts[1].lower() if len(parts) > 1 else "major"
    if mode in ("min", "m"):
        mode = "minor"
    if mode in ("maj",):
        mode = "major"
    return tonic, mode


def uses_flats(tonic: int, mode: str) -> bool:
    return f"{pc_name(tonic, True)} {mode}" in FLAT_KEYS or (mode == "major" and pc_name(tonic, True) in FLAT_KEYS)


def key_name(tonic: int, mode: str) -> str:
    return f"{pc_name(tonic, uses_flats(tonic, mode))} {mode}"


def scale_pcs(tonic: int, mode: str) -> list[int]:
    return [(tonic + i) % 12 for i in SCALES[mode]]


def chord_pcs(root: int, quality: str) -> list[int]:
    return [(root + i) % 12 for i in CHORD_QUALITIES[quality]]


def chord_name(root: int, quality: str, flats: bool = False) -> str:
    suffix = {"maj": "", "min": "m", "dim": "dim", "sus2": "sus2", "sus4": "sus4"}[quality]
    return pc_name(root, flats) + suffix


def parse_chord(name: str) -> tuple[int, str]:
    """'Am' -> (9,'min'), 'F' -> (5,'maj'), 'Bbsus4'."""
    root_len = 2 if len(name) > 1 and name[1] in "#b" else 1
    root = name_to_pc(name[:root_len])
    rest = name[root_len:]
    q = {"": "maj", "m": "min", "min": "min", "dim": "dim", "sus2": "sus2", "sus4": "sus4", "maj": "maj"}.get(rest, "maj")
    return root, q


def diatonic_triad(tonic: int, mode: str, degree: int) -> tuple[int, str]:
    """degree 0..6 -> (root_pc, quality) built from the scale."""
    sc = scale_pcs(tonic, mode)
    r, t, f = sc[degree % 7], sc[(degree + 2) % 7], sc[(degree + 4) % 7]
    third, fifth = (t - r) % 12, (f - r) % 12
    if third == 4 and fifth == 7:
        return r, "maj"
    if third == 3 and fifth == 7:
        return r, "min"
    return r, "dim"


def nearest_in_set(pitch: int, pcs: list[int]) -> int:
    """Move pitch to the nearest MIDI note whose pitch class is in pcs (ties go down)."""
    best = None
    for d in range(0, 7):
        for cand in (pitch - d, pitch + d):
            if cand % 12 in pcs:
                return cand
    return pitch if best is None else best


def voice_chord(root: int, quality: str, low: int = 57, high: int = 76, prev: list[int] | None = None) -> list[int]:
    """Close-position voicing within [low, high], chosen for minimal movement from prev."""
    pcs = chord_pcs(root, quality)
    candidates = []
    for base in range(low, high - 6):
        if base % 12 not in pcs:
            continue
        v = [base]
        for pc in pcs:
            if pc == base % 12:
                continue
            n = base + ((pc - base) % 12)
            v.append(n)
        v = sorted(v)
        if v[-1] <= high:
            candidates.append(v)
    if not candidates:
        return [low + ((pc - low) % 12) for pc in pcs]
    if prev:
        return min(candidates, key=lambda c: sum(abs(a - b) for a, b in zip(c, sorted(prev))))
    return candidates[len(candidates) // 2]
