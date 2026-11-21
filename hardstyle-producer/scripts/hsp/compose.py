"""Hardstyle composition engine. Everything is derived from key + chord progression; no random filler.

All generators return list[Note] in beats, starting at beat 0, for `bars` bars.
Progression = list of chord names, one per bar (repeated cyclically if shorter than `bars`).
Deterministic for a given seed, so results are repeatable; change `seed` for a new variation.
"""
from __future__ import annotations

import random

from .midi_io import Note
from . import theory as T

KICK_NOTE = 60      # C5 in FL Studio: default root note for samplers
SNARE_NOTE = 62
CLAP_NOTE = 64


# ------------------------------------------------------------------ helpers
class Harmony:
    def __init__(self, key: str, progression: list[str]):
        self.tonic, self.mode = T.parse_key(key)
        self.scale = T.scale_pcs(self.tonic, self.mode)
        self.prog = [T.parse_chord(c) for c in progression]
        self.names = list(progression)

    def chord(self, bar: int) -> tuple[int, str]:
        return self.prog[bar % len(self.prog)]

    def chord_tones(self, bar: int) -> list[int]:
        return T.chord_pcs(*self.chord(bar))

    def step(self, pitch: int, steps: int) -> int:
        """Move `steps` scale degrees from pitch (pitch snapped into scale first)."""
        notes = [n for n in range(0, 128) if n % 12 in self.scale]
        p = T.nearest_in_set(pitch, self.scale)
        i = notes.index(p) + steps
        return notes[max(0, min(len(notes) - 1, i))]

    def snap_chord(self, pitch: int, bar: int) -> int:
        return T.nearest_in_set(pitch, self.chord_tones(bar))

    def darker(self) -> "Harmony":
        """Parallel-minor version (modal interchange): same degrees, minor scale. Used for rawstyle."""
        if self.mode == "minor":
            h = Harmony(T.key_name(self.tonic, "minor"), self.names)
            h.scale = T.scale_pcs(self.tonic, "phrygian")  # even darker: b2 colour
            return h
        new = []
        for root, q in self.prog:
            deg = self.scale.index(root) if root in self.scale else 0
            r2, q2 = T.diatonic_triad(self.tonic, "minor", deg)
            new.append(T.chord_name(r2, q2, T.uses_flats(self.tonic, "minor")))
        return Harmony(T.key_name(self.tonic, "minor"), new)


def _cycle(bars: int, n: int):
    return [b % n for b in range(bars)]


# ------------------------------------------------------------------ chords / bass / kicks
def chords(h: Harmony, bars: int, style: str = "sustain", low: int = 57, high: int = 76,
           add_root: bool = True) -> list[Note]:
    """Supersaw chord stack with voice leading. style: sustain | offbeat | gated | half"""
    out, prev = [], None
    for b in range(bars):
        root, q = h.chord(b)
        v = T.voice_chord(root, q, low, high, prev)
        prev = v
        pitches = list(v)
        if add_root:
            r = v[0] - ((v[0] - root) % 12)
            pitches.insert(0, r - 12 if r - 12 >= low - 14 else r)
        t0 = b * 4
        if style == "sustain":
            hits = [(0, 4)]
        elif style == "half":
            hits = [(0, 2), (2, 2)]
        elif style == "offbeat":
            hits = [(i + 0.5, 0.45) for i in range(4)]
        elif style == "gated":
            pat = [1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 1]
            hits = [(i * 0.25, 0.22) for i, x in enumerate(pat) if x]
        else:
            raise ValueError(style)
        for s, d in hits:
            for p in pitches:
                out.append(Note(t0 + s, d, p, 100 if s % 1 == 0 else 92))
    return out


def bass(h: Harmony, bars: int, style: str = "offbeat", octave_base: int = 36) -> list[Note]:
    """offbeat: classic hardstyle offbeat bass | rolling: 3x 1/16 after each kick | sustain"""
    out = []
    for b in range(bars):
        root, _ = h.chord(b)
        p = octave_base + ((root - octave_base) % 12)
        for beat in range(4):
            t = b * 4 + beat
            if style == "offbeat":
                out.append(Note(t + 0.5, 0.45, p, 110))
            elif style == "rolling":
                for k in (1, 2, 3):
                    out.append(Note(t + k * 0.25, 0.22, p, 100 if k == 2 else 90))
        if style == "sustain":
            out.append(Note(b * 4, 4, p, 100))
    return out


def kick_pattern(bars: int, style: str = "euphoric", phrase: int = 8) -> list[Note]:
    out = []
    for b in range(bars):
        pos = b % phrase
        hits = [0, 1, 2, 3]
        if style == "euphoric" and pos == phrase - 1:
            hits = [0, 1, 2, 2.5, 3]                    # small pickup into next phrase
        if style == "rawstyle":
            if pos in (1, 5):
                hits = [0, 1, 2]                        # gap on beat 4 = tension
            elif pos == 3:
                hits = [0, 1, 2, 2.75, 3.5]             # off-kick fill
            elif pos == phrase - 1:
                hits = [0, 1, 2, 2.5, 3, 3.25, 3.5, 3.75]  # kick roll into next phrase
        for x in hits:
            out.append(Note(b * 4 + x, 0.25, KICK_NOTE, 127 if x % 1 == 0 else 112))
    return out


def tonal_kick(h: Harmony, bars: int, base: int = 48) -> list[Note]:
    """Kick hits pitched to the chord root: load a pitched kick in FL (e.g. sampler, root C5)
    and the tail follows the harmony. Pitches are kept within +-6 semitones of C to limit artifacts."""
    out = []
    for b in range(bars):
        root, _ = h.chord(b)
        semis = ((root - 0 + 6) % 12) - 6            # -6..+5 around C
        for beat in range(4):
            out.append(Note(b * 4 + beat, 0.9, KICK_NOTE + semis, 127))
    return out


def kick_roll(bars: int = 1) -> list[Note]:
    """Accelerating kick roll for the end of a build-up: 1/4 -> 1/8 -> 1/16."""
    out, t, total = [], 0.0, bars * 4
    for frac, step in ((0.5, 1.0), (0.25, 0.5), (0.25, 0.25)):
        end = t + frac * total
        while t < end - 1e-9:
            out.append(Note(t, min(step, 0.25), KICK_NOTE, int(90 + 37 * t / total)))
            t += step
    return out


def snare_roll(bars: int = 8, pause_last_beat: bool = True) -> list[Note]:
    """Classic build-up roll: quarters -> 8ths -> 16ths -> 32nds with velocity ramp."""
    out = []
    total = bars * 4
    stages = [(1.0, 0.25), (0.5, 0.25), (0.25, 0.25), (0.125, 0.25)]  # (step, fraction of length)
    t = 0.0
    for step, frac in stages:
        end = t + frac * total
        while t < end - 1e-9:
            if pause_last_beat and t >= total - 1:
                break
            out.append(Note(t, step * 0.9, SNARE_NOTE, int(55 + 72 * (t / total))))
            t += step
    return out


# ------------------------------------------------------------------ leads
RHYTHMS = {  # one bar each: (onset beat, duration)
    "dotted": [(0, 1.5), (1.5, 1.5), (3, 1)],
    "flow": [(0, 0.75), (0.75, 0.75), (1.5, 1), (2.5, 0.5), (3, 1)],
    "drive": [(0, 1), (1, 0.5), (1.5, 0.5), (2, 1), (3, 0.5), (3.5, 0.5)],
    "long": [(0, 2), (2, 1), (3, 1)],
    "pickup": [(0, 1.5), (1.5, 0.5), (2, 0.5), (2.5, 0.5), (3, 0.5), (3.5, 0.5)],
    "end": [(0, 3), (3, 1)],
    "hold": [(0, 4)],
}


def _motif(rng: random.Random) -> list[int]:
    """Scale-step contour: mostly steps, a leap is answered by a step the other way."""
    steps, cur = [0], 0
    while len(steps) < 12:
        if rng.random() < 0.22:
            leap = rng.choice([3, 4, -3, 2, -2])
            cur += leap
            steps.append(cur)
            cur += -1 if leap > 0 else 1
        else:
            move = rng.choice([1, -1, -1, 1, 2, -2, 0]) if len(steps) > 3 else rng.choice([1, -1, 2, -2])
            cur += move
        steps.append(cur)
    return steps[:12]


def lead(h: Harmony, bars: int = 8, seed: int = 1, center: int = 72, style: str = "euphoric") -> list[Note]:
    """8-bar phrase logic: A (motif) | A' (sequence) | A (repeat) | climax + resolution.
    Strong beats land on chord tones; weak beats may use passing scale tones."""
    rng = random.Random(seed)
    names = list(RHYTHMS)
    r_a = rng.choice(["dotted", "flow", "drive"])
    r_b = rng.choice(["long", "dotted"])
    contour = _motif(rng)
    plan = []  # per bar: (rhythm, contour offset, lift)
    for b in range(bars):
        pos = b % 8
        if pos in (0, 2, 4):
            plan.append((r_a, 0, 0))
        elif pos in (1, 5):
            plan.append((r_b, 3, 0))
        elif pos == 3:
            plan.append(("pickup" if style == "euphoric" else r_a, 6, 0))
        elif pos == 6:
            plan.append((r_a, 0, 2))      # climax: lifted by a third
        else:
            plan.append(("end", 9, 0))
    out, prev = [], None
    lo, hi = center - 10, center + 10
    for b, (rname, coff, lift) in enumerate(plan):
        rh = RHYTHMS[rname]
        tones = h.chord_tones(b)
        # bar anchor: chord tone nearest the previous note (voice leading) or the center
        ref = prev if prev is not None else center
        anchor = T.nearest_in_set(ref + (3 if lift else 0), tones)
        for i, (s, d) in enumerate(rh):
            steps = contour[(coff + i) % len(contour)] - contour[coff % len(contour)]
            p = h.step(anchor, steps + (2 if lift else 0))
            strong = (s % 2 == 0) or d >= 1.5
            if strong:
                p = h.snap_chord(p, b)
            if rname == "end" and i == 0:
                # resolve: tonic if it is a chord tone, else the chord's third
                cands = [p2 for p2 in range(lo, hi + 1) if p2 % 12 == h.tonic and h.tonic in tones]
                if not cands:
                    third = tones[1]
                    cands = [p2 for p2 in range(lo, hi + 1) if p2 % 12 == third]
                p = min(cands, key=lambda x: abs(x - (prev or center)))
            while p > hi:
                p -= 12
            while p < lo:
                p += 12
            vel = 118 if s == 0 else (108 if s % 1 == 0 else 98)
            out.append(Note(b * 4 + s, d, p, vel))
            prev = p
    # 1) avoid unintended repeats: same pitch twice in a row inside a bar -> move one scale step
    for a, b2 in zip(out, out[1:]):
        if b2.pitch == a.pitch and int(a.start // 4) == int(b2.start // 4) and b2.dur < 3:
            cand = h.step(b2.pitch, 1 if (b2.start % 2) else -1)
            strong = (b2.start % 2 == 0) or b2.dur >= 1.5
            b2.pitch = h.snap_chord(cand, int(b2.start // 4)) if strong else cand
            if b2.pitch == a.pitch:
                b2.pitch = h.step(a.pitch, 2)
    # 2) climax: bar 7 of each 8-bar phrase must hold the highest note - shift that bar up by scale steps
    for start in range(0, bars - 6, 8):
        seg = [n for n in out if start * 4 <= n.start < (start + 8) * 4]
        clim = [n for n in seg if (start + 6) * 4 <= n.start < (start + 7) * 4]
        for _ in range(4):
            others = [n.pitch for n in seg if n not in clim]
            if not clim or max(n.pitch for n in clim) > max(others):
                break
            for n in clim:
                n.pitch = h.step(n.pitch, 2)
                if (n.start % 2 == 0) or n.dur >= 1.5:
                    n.pitch = h.snap_chord(n.pitch, int(n.start // 4))
    # 3) smooth leaps larger than a sixth by octave displacement (keeps pitch class = harmony intact)
    for a, b2 in zip(out, out[1:]):
        while b2.pitch - a.pitch > 9 and b2.pitch - 12 >= lo - 2:
            b2.pitch -= 12
        while a.pitch - b2.pitch > 9 and b2.pitch + 12 <= hi + 4:
            b2.pitch += 12
    return out


def harmonize(h: Harmony, melody: list[Note], interval_steps: int = -2) -> list[Note]:
    """Diatonic harmony line (default a third below). On strong beats it must be a chord tone;
    if the third below is not, use the next chord tone below instead."""
    out = []
    for n in melody:
        bar = int(n.start // 4)
        p = h.step(n.pitch, interval_steps)
        strong = (n.start % 2 == 0) or n.dur >= 1.5
        if strong and p % 12 not in h.chord_tones(bar):
            cand = [x for x in range(n.pitch - 9, n.pitch - 2) if x % 12 in h.chord_tones(bar)]
            if cand:
                p = max(cand)
        out.append(Note(n.start, n.dur, p, max(1, n.vel - 15)))
    return out


def countermelody(h: Harmony, melody: list[Note], bars: int, low: int = 55) -> list[Note]:
    """Fills where the lead holds a long note (>= 1.5 beats): 1/8 arpeggio of the chord below the lead."""
    out = []
    for n in melody:
        if n.dur < 1.5:
            continue
        bar = int(n.start // 4)
        tones = sorted({low + ((pc - low) % 12) for pc in h.chord_tones(bar)})
        seq = tones + [tones[1]]
        t = n.start + 0.5
        i = 0
        while t < n.end - 0.01:
            out.append(Note(t, 0.45, seq[i % len(seq)], 88))
            t += 0.5
            i += 1
    return out


def screech(h: Harmony, bars: int = 8, seed: int = 3, base: int = 48) -> list[Note]:
    """Rawstyle screech: rhythmic call (bars 1-2) and response (3-4), varied in 5-8, fill in bar 8.
    Pitches: chord root, b2/5th colour, octave jumps - kept in the (darker) scale."""
    rng = random.Random(seed)
    pats = [
        "x..x..x.x..x.x..",
        "x.x..x..x.x..x..",
        "xx..x.x..x..x.x.",
        "x..x.x..x..x..xx",
    ]
    call, resp = rng.sample(pats, 2)
    out = []
    for b in range(bars):
        pos = b % 8
        pat = call if pos % 4 < 2 else resp
        root = base + ((h.chord(b)[0] - base) % 12)
        fifth = h.step(root, 4)
        colour = h.step(root, 1)  # b2 in phrygian / 2 in minor
        for i, ch in enumerate(pat):
            if ch != "x":
                continue
            t = b * 4 + i * 0.25
            if pos == 7 and i >= 8:
                continue  # leave room for the fill
            if pat is call:
                p = root if i % 8 != 6 else colour
            else:
                p = fifth if i < 8 else root + 12
            if pos >= 4 and i == 0:
                p += 12 if rng.random() < 0.5 else 0      # variation in second half
            out.append(Note(t, 0.2, p, 120 if i % 4 == 0 else 105))
        if pos == 7:  # descending 1/16 fill
            run = [root + 12, h.step(root + 12, -1), fifth, h.step(fifth, -1), h.step(root, 2), colour, root, root]
            for k, p in enumerate(run):
                out.append(Note(b * 4 + 2 + k * 0.25, 0.2, p, 110 + (k % 2) * 10))
    return out
