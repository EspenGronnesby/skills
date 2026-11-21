"""Beat-based note representation and MIDI writing/validation.

Internally every note is in BEATS relative to song bar 1 (beat 0 = first downbeat).
That makes tempo changes (e.g. 72/144 -> 150 BPM) trivial: write the same beats at a new tempo.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

from .project import HSPError
from . import theory as T

PPQ = 960  # FL Studio-friendly resolution


@dataclass
class Note:
    start: float      # beats
    dur: float        # beats
    pitch: int
    vel: int = 100

    @property
    def end(self) -> float:
        return self.start + self.dur


def seconds_to_beats(t: np.ndarray | float, beat_times: list[float], bpm: float):
    """Map seconds to beats. beat_times[0] MUST be the first downbeat (beat 0 = song bar 1)."""
    bt = np.asarray(beat_times, dtype=float)
    first = bt[0]
    spb = 60.0 / bpm
    return (np.asarray(t, dtype=float) - first) / spb


def write_midi(path: Path, tracks: dict[str, list[Note]], bpm: float, *, offset_beats: float = 0.0,
               markers: list[tuple[float, str]] | None = None, programs: dict[str, int] | None = None,
               time_sig=(4, 4)) -> Path:
    """Type-1 MIDI with tempo, time signature, named tracks and optional section markers."""
    import mido
    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("track_name", name="Tempo", time=0))
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=time_sig[0], denominator=time_sig[1], time=0))
    evs = sorted(((int(round((b + offset_beats) * PPQ)), name) for b, name in (markers or [])))
    last = 0
    for tick, name in evs:
        meta.append(mido.MetaMessage("marker", text=name, time=max(0, tick - last)))
        last = max(last, tick)
    mid.tracks.append(meta)
    for ch_i, (name, notes) in enumerate(tracks.items()):
        tr = mido.MidiTrack()
        tr.append(mido.MetaMessage("track_name", name=name, time=0))
        ch = 9 if name.lower().startswith(("kick", "snare", "drum", "clap")) else (ch_i % 15 if ch_i % 15 != 9 else 15)
        if programs and name in programs:
            tr.append(mido.Message("program_change", channel=ch, program=programs[name], time=0))
        ev = []
        for n in notes:
            s = int(round((n.start + offset_beats) * PPQ))
            e = int(round((n.end + offset_beats) * PPQ))
            if s < 0 or e <= s:
                continue
            p = int(min(127, max(0, n.pitch)))
            v = int(min(127, max(1, n.vel)))
            ev.append((s, 1, mido.Message("note_on", channel=ch, note=p, velocity=v)))
            ev.append((e, 0, mido.Message("note_off", channel=ch, note=p, velocity=0)))
        ev.sort(key=lambda x: (x[0], x[1]))  # offs before ons at same tick
        last = 0
        for t, _, msg in ev:
            tr.append(msg.copy(time=t - last))
            last = t
        mid.tracks.append(tr)
    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(path))
    return path


def read_midi_beats(path: Path) -> tuple[dict[str, list[Note]], float]:
    """Read a MIDI file back into beat-based notes (per track)."""
    import mido
    mid = mido.MidiFile(str(path))
    bpm = 120.0
    tracks: dict[str, list[Note]] = {}
    for i, tr in enumerate(mid.tracks):
        name, t, on = f"track{i}", 0, {}
        notes = []
        for msg in tr:
            t += msg.time
            if msg.type == "track_name":
                name = msg.name
            elif msg.type == "set_tempo":
                bpm = mido.tempo2bpm(msg.tempo)
            elif msg.type == "note_on" and msg.velocity > 0:
                on.setdefault(msg.note, []).append((t, msg.velocity))
            elif msg.type in ("note_off", "note_on") and on.get(msg.note):
                s, v = on[msg.note].pop(0)
                notes.append(Note(s / mid.ticks_per_beat, (t - s) / mid.ticks_per_beat, msg.note, v))
        if notes:
            tracks[name] = sorted(notes, key=lambda n: (n.start, n.pitch))
    return tracks, bpm


def validate_midi(path: Path, expect_bpm: float | None = None, key: str | None = None,
                  pitch_range: tuple[int, int] = (0, 127), expect_beats: float | None = None) -> dict:
    """QC: file parses, has notes, tempo matches, pitches in range, % in key, length plausible."""
    import mido
    try:
        mido.MidiFile(str(path))
    except Exception as e:  # noqa: BLE001
        return {"file": path.name, "ok": False, "errors": [f"Kan ikke leses som MIDI: {e}"]}
    tracks, bpm = read_midi_beats(path)
    allnotes = [n for ns in tracks.values() for n in ns]
    pitched = [n for name, ns in tracks.items() if not name.lower().startswith(("kick", "snare", "clap", "drum", "hat"))
               for n in ns]
    errs, warns = [], []
    if not allnotes:
        errs.append("Ingen noter i filen.")
    if expect_bpm and abs(bpm - expect_bpm) > 0.05:
        errs.append(f"Tempo {bpm:.2f} != forventet {expect_bpm:.2f}")
    lo, hi = pitch_range
    out_range = [n for n in allnotes if not lo <= n.pitch <= hi]
    if out_range:
        warns.append(f"{len(out_range)} noter utenfor {T.midi_to_name(lo)}–{T.midi_to_name(hi)}")
    in_key = None
    if key and pitched:
        tonic, mode = T.parse_key(key)
        pcs = set(T.scale_pcs(tonic, mode))
        in_key = round(sum(1 for n in pitched if n.pitch % 12 in pcs) / len(pitched), 3)
        if in_key < 0.85:
            warns.append(f"Bare {in_key:.0%} av notene er i {key} — sjekk toneart eller kromatikk.")
    last = max((n.end for n in allnotes), default=0)
    if expect_beats and last > expect_beats + 4:
        warns.append(f"Siste note slutter etter forventet lengde ({last:.1f} > {expect_beats:.1f} beats).")
    return {
        "file": path.name, "ok": not errs, "errors": errs, "warnings": warns,
        "tracks": {k: len(v) for k, v in tracks.items()}, "notes": len(allnotes), "bpm": round(bpm, 3),
        "pitch_min": T.midi_to_name(min(n.pitch for n in allnotes)) if allnotes else None,
        "pitch_max": T.midi_to_name(max(n.pitch for n in allnotes)) if allnotes else None,
        "length_bars": round(last / 4, 2), "in_key_ratio": in_key,
    }


def notes_to_json(notes: list[Note]) -> list[dict]:
    return [asdict(n) | {"name": T.midi_to_name(n.pitch), "bar": int(n.start // 4) + 1,
                         "beat_in_bar": round(n.start % 4 + 1, 3)} for n in notes]
