"""Original one-shots synthesised for the gaps in the user's library (screech, clap, impact, cinematic pad).

Pitched sounds are rendered at C5 (MIDI 60, FL Studio's default sampler root), so a sampler channel plays
them in any key straight from the MIDI notes. All output: 44.1 kHz, 24-bit stereo WAV, peak -1 dBFS.
These are generated here, so they are free to use.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

SR = 44100
C5 = 261.6256


def _norm(x: np.ndarray, peak_db: float = -1.0) -> np.ndarray:
    m = float(np.max(np.abs(x))) or 1.0
    return x / m * 10 ** (peak_db / 20)


def _stereo(x: np.ndarray, width: float = 0.0, seed: int = 0) -> np.ndarray:
    if width <= 0:
        return np.stack([x, x], 1)
    d = int(0.011 * SR)
    r = np.r_[np.zeros(d), x[:-d]] * width + x * (1 - width)
    return np.stack([x, r], 1)


def _lp(x: np.ndarray, cutoff: float) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(4, cutoff, "low", fs=SR, output="sos"), x)


def _bp(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def _hp(x: np.ndarray, cutoff: float) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, cutoff, "high", fs=SR, output="sos"), x)


def _reverb(x: np.ndarray, decay: float = 1.5, mix: float = 0.3, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(decay * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 6.9 / decay)
    wet = np.convolve(x, ir)[: len(x) + n] / np.sqrt(n) * 4
    dry = np.r_[x, np.zeros(n)]
    m = min(len(dry), len(wet))
    out = dry[:m] * (1 - mix) + wet[:m] * mix
    return out


def screech(variant: int = 0, dur: float = 1.2) -> np.ndarray:
    """Rawstyle screech: FM + hard clipping + moving formant filter, at C5. 8 variants."""
    rng = np.random.default_rng(variant)
    t = np.arange(int(dur * SR)) / SR
    f = C5 * (1 + 0.004 * np.sin(2 * np.pi * 6 * t))
    if variant % 2:                     # pitch dive at the start, classic screech gesture
        f = f * (1 + 0.5 * np.exp(-t * 18))
    ratio = [1.0, 2.0, 1.5, 3.0, 0.5, 2.5, 1.333, 4.0][variant % 8]
    idx = 3 + 5 * (0.5 + 0.5 * np.sin(2 * np.pi * (0.8 + variant * 0.3) * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    mod = np.sin(ph * ratio) * idx
    x = np.sin(ph + mod)
    x = np.tanh(x * (6 + variant)) + 0.3 * np.sign(np.sin(ph * 0.5))
    # sweeping formant (the "talking" part)
    lo = 600 + 400 * variant % 3
    seg = int(0.05 * SR)
    out = np.zeros_like(x)
    for k in range(0, len(x), seg):
        c = lo + 1800 * (0.5 + 0.5 * np.sin(2 * np.pi * (1.5 + 0.2 * variant) * k / SR + rng.uniform(0, 3)))
        out[k:k + seg] = _bp(x[max(0, k - 2048):k + seg], c * 0.6, min(c * 1.6, 15000))[-len(x[k:k + seg]):]
    out = np.tanh(out * 3)
    env = np.minimum(1, t / 0.004) * np.minimum(1, (dur - t) / 0.03)
    return _norm(_hp(out * env, 80))


def clap(variant: int = 0) -> np.ndarray:
    rng = np.random.default_rng(10 + variant)
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    offs = [0, 0.009, 0.017, 0.026][: 3 + variant % 2]
    for o in offs:                       # several hand hits = the "clap" smear
        i = int(o * SR)
        burst = rng.standard_normal(n - i) * np.exp(-np.arange(n - i) / SR * (60 if o < offs[-1] else 14))
        x[i:] += burst
    x = _bp(x, 900 + 150 * variant, 6000)
    x = _reverb(x, 0.6 + 0.2 * variant, 0.25, seed=variant)[: int(0.9 * SR)]
    return _norm(np.tanh(x * 1.5))


def impact(variant: int = 0) -> np.ndarray:
    """Sub drop + noise boom for drop starts."""
    dur = 3.0 + variant
    t = np.arange(int(dur * SR)) / SR
    f = 30 + 90 * np.exp(-t * 3.5)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (1.3 - 0.2 * variant))
    rng = np.random.default_rng(20 + variant)
    boom = _lp(rng.standard_normal(len(t)), 900) * np.exp(-t * 4)
    x = np.tanh(1.6 * sub) + 0.35 * boom
    x = _reverb(x, 2.5, 0.25, seed=variant)[: len(t) + SR]
    return _norm(x)


def cinematic_pad(dur: float = 6.0) -> np.ndarray:
    """Wide string/choir-like pad at C5 for the cinematic intro (play chords with MIDI)."""
    t = np.arange(int(dur * SR)) / SR
    x = np.zeros_like(t)
    for d in (-0.14, -0.07, 0, 0.07, 0.14):
        ph = 2 * np.pi * C5 * 2 ** (d / 12) * t + np.random.default_rng(int(d * 100) + 50).uniform(0, 6)
        x += (2 * ((ph / (2 * np.pi)) % 1) - 1)
    x = _lp(x, 2400)
    # "aah" formants for a choir colour
    x = 0.6 * x + 0.5 * _bp(x, 650, 1100) + 0.3 * _bp(x, 2400, 2900)
    env = np.minimum(1, t / 1.2) * np.minimum(1, (dur - t) / 1.0)
    x = _reverb(x * env, 3.5, 0.4, seed=7)
    return _norm(x, -2.0)


def riser(dur: float = 8.0) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    rng = np.random.default_rng(30)
    n = rng.standard_normal(len(t))
    out = np.zeros_like(n)
    seg = int(0.05 * SR)
    for k in range(0, len(n), seg):
        c = 300 * (40 ** (k / len(n)))
        out[k:k + seg] = _bp(n[max(0, k - 2048):k + seg], c * 0.7, min(c * 1.4, 18000))[-len(n[k:k + seg]):]
    return _norm(out * (t / dur) ** 1.5)


def render_all(out_dir: Path) -> list[dict]:
    """Render the generated kit. Returns [{file, role, note}] for the project's sample map."""
    import soundfile as sf
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []

    def save(name, x, role, width=0.0):
        p = out_dir / name
        sf.write(str(p), _stereo(x, width).astype(np.float32), SR, subtype="PCM_24")
        made.append({"file": str(p), "name": name, "role": role, "root": "C5", "generated": True,
                     "duration_sec": round(len(x) / SR, 2)})

    for v in range(6):
        save(f"HSP_Screech_{v + 1:02d}_C.wav", screech(v), "screech", 0.3)
    for v in range(3):
        save(f"HSP_Clap_{v + 1:02d}.wav", clap(v), "clap", 0.2)
    for v in range(2):
        save(f"HSP_Impact_{v + 1:02d}.wav", impact(v), "impact", 0.4)
    save("HSP_Cinematic_Pad_C.wav", cinematic_pad(), "atmosphere", 0.6)
    save("HSP_Noise_Riser_8s.wav", riser(), "riser", 0.5)
    return made
