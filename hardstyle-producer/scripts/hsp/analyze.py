"""Song analysis: tempo + beat grid, downbeats, key, chords per bar, structure, vocal activity.

Every estimate carries a confidence and alternatives, so uncertainty is reported, not hidden.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import theory as T

SR = 22050
HOP = 512

# Krumhansl-Kessler key profiles
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def load_mono(path: Path, sr: int = SR) -> np.ndarray:
    import librosa
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    if y.size == 0 or float(np.max(np.abs(y))) < 1e-4:
        from .project import HSPError
        raise HSPError(f"Lydfilen ser tom eller stille ut: {path}")
    return y


# ---------------------------------------------------------------- tempo
def estimate_tempo(y: np.ndarray, sr: int = SR) -> dict:
    import librosa
    _, y_perc = librosa.effects.hpss(y)
    onset = librosa.onset.onset_strength(y=y_perc, sr=sr, hop_length=HOP)
    # global autocorrelation tempogram -> candidate peaks
    tg = librosa.autocorrelate(onset, max_size=int(4.0 * sr / HOP))
    tg[: int(0.25 * sr / HOP)] = 0  # ignore > 240 BPM
    lags = np.arange(len(tg))
    bpms = 60.0 * sr / (HOP * np.maximum(lags, 1))
    valid = (bpms >= 60) & (bpms <= 200)
    cand = []
    for i in np.argsort(tg * valid)[::-1]:
        if not valid[i]:
            continue
        # refine with parabolic interpolation
        if 0 < i < len(tg) - 1:
            a, b, c = tg[i - 1], tg[i], tg[i + 1]
            off = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0
        else:
            off = 0
        bpm = 60.0 * sr / (HOP * (i + off))
        if all(abs(bpm - x["bpm"]) / x["bpm"] > 0.04 for x in cand):
            cand.append({"bpm": round(float(bpm), 2), "strength": float(tg[i])})
        if len(cand) >= 4:
            break
    top = cand[0]["strength"] if cand else 1.0
    for c in cand:
        c["strength"] = round(c["strength"] / top, 3)

    tempo_bt, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=HOP,
                                              start_bpm=cand[0]["bpm"] if cand else 120, tightness=200)
    beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=HOP)
    ibi = np.diff(beat_times)
    bpm_grid = float(60.0 / np.median(ibi)) if len(ibi) else float(np.atleast_1d(tempo_bt)[0])
    stability = float(np.std(60.0 / ibi)) if len(ibi) > 2 else None
    # confidence: how dominant the chosen tempo is vs. the runner-up that is NOT a 2x/0.5x relative
    conf = 1.0
    for c in cand[1:]:
        ratio = c["bpm"] / bpm_grid
        if not any(abs(ratio - r) < 0.05 for r in (0.5, 2.0, 1.5, 2 / 3)):
            conf = round(1.0 - c["strength"], 3)
            break
    return {
        "bpm": round(bpm_grid, 2),
        "bpm_rounded": int(round(bpm_grid)),
        "half_time": round(bpm_grid / 2, 2),
        "double_time": round(bpm_grid * 2, 2),
        "candidates": cand,
        "confidence": conf,
        "tempo_std_bpm": round(stability, 3) if stability is not None else None,
        "beat_times": [round(float(t), 4) for t in beat_times],
        "_onset": onset,
    }


def _interp(env: np.ndarray, pos: np.ndarray) -> np.ndarray:
    pos = pos[(pos >= 0) & (pos < len(env) - 1)]
    return np.interp(pos, np.arange(len(env)), env)


def fit_grid(y: np.ndarray, bpm0: float, sr: int = SR) -> dict:
    """Fit a constant-tempo grid: fine BPM + beat phase via onset comb, bar phase via harmonic novelty.
    Produced pop/EDM is almost always on a fixed grid; drift is reported separately."""
    import librosa
    y_harm, y_perc = librosa.effects.hpss(y)
    on = librosa.onset.onset_strength(y=y_perc, sr=sr, hop_length=HOP)
    on = on / (on.max() + 1e-9)
    fps = sr / HOP
    best = (-1, bpm0, 0.0)
    for bpm in np.linspace(bpm0 * 0.99, bpm0 * 1.01, 161):
        period = fps * 60.0 / bpm
        for ph in np.arange(0, period, 0.25):
            s = _interp(on, ph + period * np.arange(int(len(on) / period) + 1)).mean()
            if s > best[0]:
                best = (s, bpm, ph)
    _, bpm, ph = best
    period = fps * 60.0 / bpm
    # harmonic novelty: chroma difference between the beat before and the beat after each frame
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=HOP)
    w = max(2, int(period))
    cs = np.cumsum(np.pad(chroma, ((0, 0), (1, 0))), axis=1)
    n = chroma.shape[1]
    nov = np.zeros(n)
    for i in range(w, n - w):
        a = (cs[:, i] - cs[:, i - w]) / w
        b = (cs[:, i + w] - cs[:, i]) / w
        nov[i] = 1 - float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    nov = nov / (nov.max() + 1e-9)
    # low-band onsets (kick on 1 is common)
    S = np.abs(librosa.stft(y_perc, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    low = S[freqs < 120].sum(axis=0)
    low_on = np.maximum(0, np.diff(low, prepend=low[0]))
    low_on = low_on / (low_on.max() + 1e-9)
    # 8 hypotheses: comb may have locked to offbeats (offbeat bass/hats), so test +half-beat too
    scores, hyps = [], []
    for half in (0.0, 0.5):
        for k in range(4):
            start = ph + (k + half) * period
            pos = start + 4 * period * np.arange(int(n / (4 * period)) + 1)
            beat_pos = start + period * np.arange(int(n / period) + 1)
            s = (_interp(nov, pos).mean() * 2.0 + _interp(low_on, pos).mean() * 0.5
                 + _interp(low_on, beat_pos).mean() * 0.5)
            scores.append(float(s))
            hyps.append(start)
    order = np.argsort(scores)[::-1]
    first = max(0.0, (hyps[int(order[0])] % (4 * period)) / fps - HOP / sr)  # onset-flux lag ~1 frame
    beat_sec = 60.0 / bpm
    while first - 4 * beat_sec >= 0:
        first -= 4 * beat_sec
    conf = (scores[order[0]] - scores[order[1]]) / (scores[order[0]] + 1e-9)
    return {"bpm": float(bpm), "first_downbeat": float(first), "beat_phase_sec": float(ph / fps),
            "bar_phase_scores": [round(s, 4) for s in scores], "confidence": round(float(conf), 3),
            "comb_score": round(float(best[0]), 4)}


def _unused_estimate_downbeat(y: np.ndarray, beat_times: np.ndarray, sr: int = SR) -> dict:
    """Pick which beat phase (0-3) is beat 1 using low-band onsets + harmonic change."""
    import librosa
    if len(beat_times) < 8:
        return {"phase": 0, "confidence": 0.0, "first_downbeat": float(beat_times[0]) if len(beat_times) else 0.0}
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    low = S[freqs < 150].sum(axis=0)
    low_on = np.maximum(0, np.diff(low, prepend=low[0]))
    chroma = librosa.feature.chroma_stft(S=S ** 2, sr=sr)
    frames = librosa.time_to_frames(beat_times, sr=sr, hop_length=HOP)
    frames = np.clip(frames, 0, S.shape[1] - 1)
    bc = librosa.util.sync(chroma, frames, aggregate=np.mean)
    bc = bc / (np.linalg.norm(bc, axis=0, keepdims=True) + 1e-9)
    change = np.r_[0, 1 - np.sum(bc[:, 1:] * bc[:, :-1], axis=0)]
    lo = low_on[frames]
    lo = lo / (lo.max() + 1e-9)
    n = min(len(change), len(lo))
    score = []
    for ph in range(4):
        idx = np.arange(ph, n, 4)
        score.append(float(np.mean(lo[idx]) + 1.5 * np.mean(change[idx])))
    order = np.argsort(score)[::-1]
    best = int(order[0])
    conf = (score[order[0]] - score[order[1]]) / (score[order[0]] + 1e-9)
    return {"phase": best, "confidence": round(float(conf), 3),
            "first_downbeat": round(float(beat_times[best]), 4), "phase_scores": [round(s, 4) for s in score]}


# ---------------------------------------------------------------- key
def estimate_key(chroma_mean: np.ndarray) -> dict:
    scores = []
    for tonic in range(12):
        for mode, prof in (("major", KK_MAJOR), ("minor", KK_MINOR)):
            r = float(np.corrcoef(np.roll(prof, tonic), chroma_mean)[0, 1])
            scores.append((r, tonic, mode))
    scores.sort(reverse=True)
    r0, t0, m0 = scores[0]
    alts = [{"key": T.key_name(t, m), "score": round(r, 3)} for r, t, m in scores[1:4]]
    rel = (t0 + 3) % 12 if m0 == "minor" else (t0 - 3) % 12
    rel_mode = "major" if m0 == "minor" else "minor"
    return {
        "key": T.key_name(t0, m0), "tonic_pc": t0, "mode": m0, "score": round(r0, 3),
        "confidence": round(r0 - scores[1][0], 3), "alternatives": alts,
        "relative": T.key_name(rel, rel_mode),
        "note": "Lav confidence betyr ofte at dur og parallell moll (relative) er vanskelige å skille — sjekk med øret.",
    }


# ---------------------------------------------------------------- chords
def _chord_templates():
    labels, mats = [], []
    for root in range(12):
        for q in ("maj", "min"):
            v = np.zeros(12)
            for i, pc in enumerate(T.chord_pcs(root, q)):
                v[pc] = [1.0, 0.8, 0.9][i]
            labels.append((root, q))
            mats.append(v / np.linalg.norm(v))
    return labels, np.array(mats)


def estimate_chords(chroma_bars: np.ndarray, bass_bars: np.ndarray, key: dict) -> list[dict]:
    labels, M = _chord_templates()
    scale = set(T.scale_pcs(key["tonic_pc"], key["mode"]))
    flats = T.uses_flats(key["tonic_pc"], key["mode"])
    out = []
    for b in range(chroma_bars.shape[1]):
        c = chroma_bars[:, b]
        if c.sum() < 1e-6:
            out.append({"bar": b + 1, "chord": "N", "confidence": 0.0})
            continue
        c = c / (np.linalg.norm(c) + 1e-9)
        s = M @ c
        bass = bass_bars[:, b] / (bass_bars[:, b].max() + 1e-9)
        for i, (root, q) in enumerate(labels):
            s[i] += 0.45 * bass[root]                       # bass supports the root
            if all(pc in scale for pc in T.chord_pcs(root, q)):
                s[i] += 0.06                                 # mild diatonic prior
        order = np.argsort(s)[::-1]
        r, q = labels[order[0]]
        r2, q2 = labels[order[1]]
        out.append({"bar": b + 1, "chord": T.chord_name(r, q, flats), "root_pc": r, "quality": q,
                    "confidence": round(float(s[order[0]] - s[order[1]]), 3),
                    "alternative": T.chord_name(r2, q2, flats)})
    return out


def find_loop(chords: list[dict], lengths=(4, 8, 2)) -> dict | None:
    """Most frequent repeating progression of 2/4/8 bars (on bar-aligned windows)."""
    names = [c["chord"] for c in chords]
    best = None
    for L in lengths:
        counts: dict[tuple, list[int]] = {}
        for i in range(0, len(names) - L + 1):
            w = tuple(names[i:i + L])
            if "N" in w or len(set(w)) < 2:
                continue
            counts.setdefault(w, []).append(i + 1)
        for w, starts in counts.items():
            # non-overlapping occurrences
            occ, last = 0, -10 ** 9
            for s in starts:
                if s - last >= L:
                    occ += 1
                    last = s
            cover = occ * L
            if occ >= 2 and (best is None or cover > best["bars_covered"]):
                best = {"progression": list(w), "length_bars": L, "occurrences": occ,
                        "start_bars": starts, "bars_covered": cover}
    return best


# ---------------------------------------------------------------- structure
def segment_structure(feat_bars: np.ndarray, rms_bars: np.ndarray, phrase: int = 4) -> list[dict]:
    """Novelty-based boundaries snapped to `phrase`-bar grid, labelled by repetition + energy."""
    n = feat_bars.shape[1]
    if n < 8:
        return [{"start_bar": 1, "end_bar": n, "label": "A", "energy": "mid"}]
    F = feat_bars / (np.linalg.norm(feat_bars, axis=0, keepdims=True) + 1e-9)
    SSM = F.T @ F
    k = 4
    kern = np.kron(np.array([[1, -1], [-1, 1]]), np.ones((k, k)))
    nov = np.zeros(n)
    for i in range(k, n - k):
        nov[i] = np.sum(SSM[i - k:i + k, i - k:i + k] * kern)
    e = rms_bars / (rms_bars.max() + 1e-9)
    de = np.abs(np.diff(e, prepend=e[0]))
    nov = nov / (nov.max() + 1e-9) + de / (de.max() + 1e-9)
    bounds = [0]
    for b in range(phrase, n, phrase):
        win = nov[max(0, b - 1): b + 2]
        if win.max() > 0.35 and b - bounds[-1] >= phrase * 2 - phrase // 2:
            bounds.append(b)
    bounds.append(n)
    segs = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        segs.append({"start_bar": a + 1, "end_bar": b, "length_bars": b - a,
                     "mean": F[:, a:b].mean(axis=1), "energy_val": float(e[a:b].mean())})
    # label by similarity clustering
    labels, protos = [], []
    for s in segs:
        v = s["mean"] / (np.linalg.norm(s["mean"]) + 1e-9)
        for j, p in enumerate(protos):
            if float(v @ p) > 0.93:
                labels.append(chr(65 + j))
                break
        else:
            protos.append(v)
            labels.append(chr(65 + len(protos) - 1))
    qs = np.quantile([s["energy_val"] for s in segs], [0.33, 0.66])
    out = []
    for s, lab in zip(segs, labels):
        ev = s["energy_val"]
        out.append({"start_bar": s["start_bar"], "end_bar": s["end_bar"], "length_bars": s["length_bars"],
                    "label": lab, "energy": "low" if ev < qs[0] else ("high" if ev > qs[1] else "mid"),
                    "energy_value": round(ev, 3)})
    return out


def vocal_activity(vocal_path: Path, bar_times: np.ndarray, sr: int = SR) -> dict:
    import librosa
    y = load_mono(vocal_path, sr)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP)
    thr = max(0.02, 0.25 * float(np.percentile(rms, 95)))
    per_bar = []
    for i in range(len(bar_times) - 1):
        m = (t >= bar_times[i]) & (t < bar_times[i + 1])
        per_bar.append(float(np.mean(rms[m] > thr)) if m.any() else 0.0)
    active = [p > 0.2 for p in per_bar]
    regions, start = [], None
    for i, a in enumerate(active + [False]):
        if a and start is None:
            start = i
        if not a and start is not None:
            if i - start >= 1:
                regions.append({"start_bar": start + 1, "end_bar": i, "length_bars": i - start})
            start = None
    # merge gaps of one bar (breaths between lines)
    merged = []
    for r in regions:
        if merged and r["start_bar"] - merged[-1]["end_bar"] <= 2:
            merged[-1]["end_bar"] = r["end_bar"]
            merged[-1]["length_bars"] = merged[-1]["end_bar"] - merged[-1]["start_bar"] + 1
        else:
            merged.append(dict(r))
    return {"per_bar_activity": [round(p, 2) for p in per_bar], "regions": merged, "threshold_rms": round(thr, 4)}


# ---------------------------------------------------------------- main entry
def analyze(audio: Path, stems_dir: Path | None = None) -> dict:
    import librosa
    y = load_mono(audio)
    duration = len(y) / SR
    tempo = estimate_tempo(y)
    tracked = np.array(tempo["beat_times"])
    g = fit_grid(y, tempo["candidates"][0]["bpm"] if tempo["candidates"] else tempo["bpm"])
    tempo["bpm"] = round(g["bpm"], 2)
    tempo["bpm_rounded"] = int(round(g["bpm"]))
    tempo["half_time"] = round(g["bpm"] / 2, 2)
    tempo["double_time"] = round(g["bpm"] * 2, 2)
    spb = 60.0 / g["bpm"]
    bar_len = 4 * spb
    first = g["first_downbeat"]
    grid_beats = first - bar_len + spb * np.arange(int((duration - first) / spb) + 6)
    # drift check: how far the free-running beat tracker strays from the fixed grid
    if len(tracked):
        dev = np.array([np.min(np.abs(((t - first) / spb) - np.round((t - first) / spb))) * spb for t in tracked])
        tempo["grid_deviation_ms_median"] = round(float(np.median(dev)) * 1000, 1)
        tempo["grid_deviation_ms_p90"] = round(float(np.percentile(dev, 90)) * 1000, 1)
        tempo["constant_tempo_likely"] = bool(np.percentile(dev, 90) < 0.05)
    tempo["beat_times"] = [round(float(t), 4) for t in grid_beats if 0 <= t <= duration]
    down = {"first_downbeat": round(first, 4), "confidence": g["confidence"],
            "bar_phase_scores": g["bar_phase_scores"],
            "note": "confidence < 0.1 = usikker taktstart. Sjekk at takt 1 høres riktig ut i FL."}
    # song bar 1 starts at the first downbeat; anything before it is a pickup
    bar_times = first + bar_len * np.arange(0, int(np.ceil((duration - first) / bar_len)) + 1)
    align_pad = float((bar_len - first) % bar_len)  # silence to prepend so downbeats land on FL bar lines
    if align_pad > bar_len - 0.01:
        align_pad = 0.0
    fl_bar_offset = 0 if align_pad == 0.0 else 1   # FL bar = song bar + offset (pickup fills FL bar 1)

    # Harmony source: prefer drum-free stems (pitched kicks ruin chord/bass reading on the full mix)
    have_stems = bool(stems_dir and all((stems_dir / f"{s}.wav").exists() for s in ("bass", "other")))
    if have_stems:
        def _ld(name):
            z = load_mono(stems_dir / f"{name}.wav") if (stems_dir / f"{name}.wav").exists() else np.zeros_like(y)
            return np.pad(z, (0, max(0, len(y) - len(z))))[: len(y)]
        y_bass = _ld("bass")
        y_harm = _ld("other") + 0.8 * y_bass
        if (stems_dir / "vocals.wav").exists():
            y_harm = y_harm + 0.5 * _ld("vocals")
        harmony_source = "stems (other + bass + 0.5*vocals)"
    else:
        y_harm, _ = librosa.effects.hpss(y)
        y_bass = y_harm
        harmony_source = "full mix (HPSS) — mindre pålitelig; kjør separate-stems for bedre akkorder"
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=SR, hop_length=HOP)
    key = estimate_key(chroma.mean(axis=1))

    # bass chroma (C1-B3)
    C = np.abs(librosa.cqt(y_bass, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C1"), n_bins=36))
    bass_chroma = np.zeros((12, C.shape[1]))
    for i in range(36):
        bass_chroma[i % 12] += C[i]
    bt = np.clip(bar_times, 0, duration)
    frames = librosa.time_to_frames(bt, sr=SR, hop_length=HOP)
    frames = np.unique(np.clip(frames, 0, chroma.shape[1]))
    chroma_bars = librosa.util.sync(chroma, frames, aggregate=np.median, pad=False)
    bass_bars = librosa.util.sync(bass_chroma, frames, aggregate=np.mean, pad=False)
    chords = estimate_chords(chroma_bars, bass_bars, key)
    loop = find_loop(chords)

    mfcc = librosa.feature.mfcc(y=y, sr=SR, hop_length=HOP, n_mfcc=13)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0][None, :]
    feat = np.vstack([chroma, mfcc / 50.0])
    feat_bars = librosa.util.sync(feat, frames, aggregate=np.mean, pad=False)
    rms_bars = librosa.util.sync(rms, frames, aggregate=np.mean, pad=False)[0]
    sections = segment_structure(feat_bars, rms_bars)

    # transition / build-up / drop candidates from bar energy
    e = rms_bars / (rms_bars.max() + 1e-9)
    transitions = []
    for i in range(1, len(e)):
        jump = e[i] - e[i - 1]
        if abs(jump) > 0.18 and (i % 4 == 0):
            transitions.append({"bar": i + 1, "type": "energy_up" if jump > 0 else "energy_down",
                                "delta": round(float(jump), 3)})
    vocals = None
    if stems_dir and (stems_dir / "vocals.wav").exists():
        vocals = vocal_activity(stems_dir / "vocals.wav", bar_times)

    n_bars = len(chords)
    return {
        "file": audio.name,
        "duration_sec": round(duration, 3),
        "tempo": {k: v for k, v in tempo.items() if not k.startswith("_") and k != "beat_times"},
        "time_signature": {"value": "4/4", "measured": False,
                           "note": "Antatt 4/4 (standard i pop/hardstyle). Ikke målt robust."},
        "downbeat": down,
        "grid": {"bar_length_sec": round(bar_len, 4), "first_downbeat_sec": round(float(first), 4),
                 "pickup_sec": round(float(first), 4), "align_pad_sec": round(align_pad, 4),
                 "fl_bar_offset": fl_bar_offset, "n_bars": n_bars,
                 "bar_times_sec": [round(float(t), 4) for t in bar_times[: n_bars + 1]],
                 "note": "Takt 1 = første downbeat. align_pad_sec stillhet legges foran lyd/MIDI slik at "
                         "taktene havner på FL sitt grid; FL-takt = sangtakt + fl_bar_offset."},
        "beat_times_sec": tempo["beat_times"],
        "key": key,
        "harmony_source": harmony_source,
        "chords_per_bar": chords,
        "chord_loop": loop,
        "sections": sections,
        "transitions": transitions,
        "vocals": vocals,
        "energy_per_bar": [round(float(x), 3) for x in e],
    }
