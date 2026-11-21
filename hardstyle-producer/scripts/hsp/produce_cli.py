"""`hsp produce`: full style production into one organised FL project (samplers + FLEX + vocal clip)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path, PureWindowsPath

import numpy as np

from .midi_io import Note
from .project import HSPError, Project
from . import production as PR
from . import theory as T


def _win_join(base: str, *parts: str) -> str:
    return str(PureWindowsPath(base, *parts))


def render_preview(tracks: dict[str, list[Note]], samples: dict[str, Path], vocal: Path | None, out: Path,
                   bpm: float, tempo_changes: list[tuple[float, float]] | None = None, sr: int = 44100) -> Path:
    """Preview with the REAL samples (sampler-style: pitch by resampling, root C5=60) and simple synths for
    FLEX parts. tempo_changes: [(beat, bpm)] after the start - e.g. the zaag section at 200."""
    import soundfile as sf
    from .preview import INSTR, _env, _hz
    changes = sorted([(0.0, bpm)] + list(tempo_changes or []))

    def t_of(beat):
        t, prev_b, prev_bpm = 0.0, 0.0, changes[0][1]
        for b, nb in changes[1:]:
            if beat <= b:
                break
            t += (b - prev_b) * 60 / prev_bpm
            prev_b, prev_bpm = b, nb
        return t + (beat - prev_b) * 60 / prev_bpm

    last = max(n.end for v in tracks.values() for n in v)
    mix = np.zeros((int((t_of(last) + 8) * sr), 2), np.float32)
    cache = {}
    for name, notes in tracks.items():
        smp = samples.get(name)
        if smp is not None and smp not in cache:
            y, s0 = sf.read(str(smp), dtype="float32", always_2d=True)
            if y.shape[1] == 1:
                y = np.repeat(y, 2, 1)
            if s0 != sr:
                import librosa
                y = librosa.resample(y.T, orig_sr=s0, target_sr=sr).T
            cache[smp] = y
        for n in notes:
            i0 = int(t_of(n.start) * sr)
            if smp is not None:
                y = cache[smp]
                ratio = 2 ** ((n.pitch - 60) / 12)
                if abs(ratio - 1) > 1e-3:
                    idx = np.arange(0, len(y) - 1, ratio)
                    y = np.stack([np.interp(idx, np.arange(len(y)), y[:, c]) for c in (0, 1)], 1)
                dur = int((t_of(n.end) - t_of(n.start)) * sr)
                seg = y[:max(dur, int(0.05 * sr))] * (n.vel / 127) * 0.6
            else:
                key = next((k for k in INSTR if k in name.lower()), "lead")
                fn, amp = INSTR[key]
                ln = int((t_of(n.end) - t_of(n.start)) * sr)
                mono = fn(_hz(n.pitch), max(ln, 64)) * _env(max(ln, 64)) * amp * (n.vel / 127)
                seg = np.stack([mono, mono], 1)
            j = min(len(mix), i0 + len(seg))
            mix[i0:j] += seg[: j - i0]
    if vocal and vocal.exists():
        v, s0 = sf.read(str(vocal), dtype="float32", always_2d=True)
        j = min(len(mix), len(v))
        mix[:j] += v[:j] * 0.9
    mix = np.tanh(mix * 0.9) * 0.95
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), mix, sr)
    return out


def produce(project: Path, picks: dict[str, str], staged_root: Path, fl_base: str, prog: list[str],
            bars_per_chord: int, target_bpm: float = 160, zaag_bpm: float = 200, seed: int = 2) -> dict:
    """picks: channel -> Windows path of one of the user's samples (or 'GEN:<file>' for a generated one)."""
    from .sounddesign import render_all
    from .flp_organize import build, verify
    from .cli import _vocal_arrangement
    p = Project.open(project)
    an = p.read_json("analysis/song_analysis.json")
    key = an["key"]["key"]
    tonic, _ = T.parse_key(key)
    sections = PR.plan_sections(an, target_bpm)
    src_chords = [c["chord"] for c in an["chords_per_bar"]]
    tracks, markers = PR.render_parts(sections, key, prog, bars_per_chord, src_chords, seed=seed)

    # --- samples: generated kit + edits of the user's files (originals untouched)
    sdir = p.path("samples")
    gen = {Path(m["file"]).name: Path(m["file"]) for m in render_all(sdir / "generated")}
    staged, win_of = {}, {}
    for ch, wp in picks.items():
        if wp.startswith("GEN:"):
            name = wp[4:]
            staged[ch] = gen[name]
            win_of[ch] = _win_join(fl_base, "samples", "generated", name)
        else:
            rel = PureWindowsPath(wp).relative_to(PureWindowsPath(r"C:\Users\essi1\Documents\Image-Line\Downloads\FL CLOUD Sounds"))
            local = staged_root.joinpath(*rel.parts)
            if not local.exists():
                raise HSPError(f"Mangler lokal kopi av {wp}")
            staged[ch] = local
            win_of[ch] = wp
    role_of = {"Zaag Kick": "zaag_loop", "Tension Riser": "tension_riser", "Screech FX": "screech_loop"}
    edits = PR.prepare_samples({role_of[c]: staged[c] for c in role_of if c in staged}, sdir / "edited", tonic)
    sample_log = []
    for ch, role in role_of.items():
        if ch in staged and edits[role]["edited"]:
            staged[ch] = edits[role]["local"]
            win_of[ch] = _win_join(fl_base, "samples", "edited", edits[role]["local"].name)
            sample_log.append({"channel": ch, "file": edits[role]["local"].name, "edit": edits[role]["note"]})
    # verify every sample is audible (catches empty FL Cloud placeholders)
    import soundfile as sf
    for ch, f in staged.items():
        y, _ = sf.read(str(f), always_2d=True)
        if float(np.max(np.abs(y))) < 1e-4:
            raise HSPError(f"Sample for {ch} er stille: {f.name}")

    # --- vocal arrangement (source -> target tempo, placed per section)
    src_bpm = an["tempo"]["bpm"]
    arr = {"target_bpm": target_bpm, "stretch_factor": target_bpm / src_bpm, "sections": sections,
           "total_bars": sections[-1]["end_bar"], "time_base": "same", "key": key, "progression": prog,
           "bars_per_chord": bars_per_chord, "has_vocals": True, "style": "cinematic_raw_zaag"}
    voc = _vocal_arrangement(p, an, arr, p.path("arrangement", f"vocals_arranged_{int(target_bpm)}bpm.wav"))
    p.write_json("arrangement/arrangement.json", arr)

    # --- FL project
    order = [c for c in PR.ORDER if c in tracks] + [c for c in tracks if c not in PR.ORDER]
    tracks = {c: tracks[c] for c in order}
    samplers = [{"name": c, "path": win_of[c]} for c in order if c not in PR.FLEX and c in win_of]
    missing = [c for c in order if c not in PR.FLEX and c not in win_of]
    if missing:
        raise HSPError(f"Ingen sample valgt for: {missing}")
    clips = []
    if voc:
        import soundfile as sf
        clips.append({"name": "Vocals", "path": _win_join(fl_base, "arrangement", voc.name), "start_bar": 1,
                      "seconds": sf.info(str(voc)).duration})
    tpl = Path(__file__).resolve().parents[2] / "templates" / "hardstyle_mal.flp"
    out = p.path("fl-studio", f"{p.root.name}.flp")
    if out.exists():
        p.backup(out)
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    r = build(tpl, out, tracks, sections, bpm=target_bpm, samplers=samplers, audio_clips=clips)
    v = verify(out)
    zaag = next(s for s in sections if s["role"] == "zaag")
    prev = render_preview(tracks, staged, voc, p.path("exports", "preview_with_your_samples.wav"), target_bpm,
                          tempo_changes=[((zaag["start_bar"] - 1) * 4, zaag_bpm)])
    info = {"flp": str(out), "patterns": r["patterns"], "clips": len(v["items"]), "tracks": v["track_names"],
            "samplers": {s["name"]: s["path"] for s in samplers}, "edits": sample_log,
            "sections": [(s["name"], s["start_bar"], s["length_bars"]) for s in sections],
            "zaag_start_bar": zaag["start_bar"], "preview": str(prev), "vocal": str(voc) if voc else None,
            "notes_total": sum(len(x) for x in tracks.values())}
    p.write_json("fl-studio/production.json", info)
    return info
