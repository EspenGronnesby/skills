"""Synthesize a short test song with KNOWN ground truth, to validate the pipeline.
Db major, 144 BPM, 4/4, progression Db-Gb-Ab-Bbm (I-IV-V-vi), 32 bars, 0.30 s lead-in silence.
Sections: 1-8 pads only | 9-24 drums+bass+pads+melody | 25-32 pads+melody (no drums)
"""
import json
import sys
import numpy as np
import soundfile as sf

SR = 44100
BPM = 144
BEAT = 60 / BPM
BAR = 4 * BEAT
LEAD = float(sys.argv[2]) if len(sys.argv) > 2 else 0.30
NB = 32
prog = [(1, "maj"), (6, "maj"), (8, "maj"), (10, "min")]  # Db Gb Ab Bbm (pc)
names = ["Db", "Gb", "Ab", "Bbm"]
total = LEAD + NB * BAR + 1.0
out = np.zeros(int(total * SR))


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(sig, t0):
    i = int(t0 * SR)
    j = min(len(out), i + len(sig))
    out[i:j] += sig[: j - i]


def saw(f, dur, amp, detune=(0, -0.12, 0.12)):
    t = np.arange(int(dur * SR)) / SR
    s = sum(2 * ((t * f * 2 ** (d / 12)) % 1) - 1 for d in detune) / len(detune)
    env = np.minimum(1, t / 0.02) * np.minimum(1, (dur - t) / 0.05)
    return amp * s * env


def tone(f, dur, amp, vib=0.0):
    t = np.arange(int(dur * SR)) / SR
    ph = 2 * np.pi * np.cumsum(f * (1 + vib * np.sin(2 * np.pi * 5.5 * t))) / SR
    s = np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
    env = np.minimum(1, t / 0.03) * np.minimum(1, (dur - t) / 0.06)
    return amp * s * env


def kick():
    t = np.arange(int(0.35 * SR)) / SR
    f = 50 + 120 * np.exp(-t * 30)
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def hat():
    t = np.arange(int(0.05 * SR)) / SR
    return 0.15 * np.random.default_rng(1).standard_normal(len(t)) * np.exp(-t * 80)


# melody (2-bar motif per chord pair), scale degrees in Db major as MIDI
mel_pat = [  # (beat offset within 2 bars, midi, beats)
    (0, 77, 1), (1, 75, 0.5), (1.5, 73, 0.5), (2, 75, 1.5), (4, 80, 1), (5, 78, 1), (6, 77, 2),
]
mel_pat2 = [(0, 80, 1), (1, 78, 0.5), (1.5, 77, 0.5), (2, 75, 1.5), (4, 73, 1), (5, 72, 1), (6, 73, 2)]
truth_notes = []
for b in range(NB):
    t0 = LEAD + b * BAR
    root, q = prog[b % 4]
    third = 4 if q == "maj" else 3
    for iv in (0, third, 7):
        add(saw(hz(60 + root + iv if root + iv < 12 else 48 + root + iv), BAR, 0.08), t0)
    if 8 <= b < 24:
        for k in range(4):
            add(kick(), t0 + k * BEAT)
            add(hat(), t0 + k * BEAT + BEAT / 2)
            add(saw(hz(36 + root), BEAT / 2 * 0.9, 0.18, detune=(0,)), t0 + k * BEAT + BEAT / 2)
    if b >= 8 and b % 2 == 0:
        pat = mel_pat if (b // 2) % 2 == 0 else mel_pat2
        for off, m, d in pat:
            add(tone(hz(m), d * BEAT * 0.95, 0.22, vib=0.004), t0 + off * BEAT)
            truth_notes.append({"bar": b + 1, "beat": off, "midi": m, "beats": d})

out /= np.max(np.abs(out)) * 1.1
path = sys.argv[1]
sf.write(path, out, SR)
json.dump({"bpm": BPM, "key": "Db major", "lead_in_sec": LEAD, "bars": NB,
           "chords": [names[b % 4] for b in range(NB)],
           "sections": [[1, 8, "pads"], [9, 24, "full"], [25, 32, "pads+melody"]],
           "melody_notes": truth_notes}, open(path.replace(".wav", "_truth.json"), "w"), indent=1)
print("wrote", path, round(len(out) / SR, 2), "s")
