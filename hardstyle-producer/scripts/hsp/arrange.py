"""Arrangement engine: plan sections from the source song + request, render one multi-track MIDI
(FL imports this as channels + patterns placed on the Playlist) and a bar-by-bar timeline."""
from __future__ import annotations

import re

from . import compose as C
from . import theory as T
from .midi_io import Note

# role -> (section energy, elements). Lengths are in bars and get adapted to the source song.
TEMPLATE = [
    ("Intro", 16, "intro"),
    ("Verse", 16, "verse"),
    ("Breakdown", 32, "breakdown"),
    ("Build-up", 16, "buildup"),
    ("Euphoric Drop", 32, "drop_euphoric"),
    ("Transition", 16, "midbreak"),
    ("Build-up 2", 16, "buildup2"),
    ("Rawstyle Drop", 32, "drop_raw"),
    ("Outro", 16, "outro"),
]


def parse_request(text: str) -> dict:
    t = text.lower()
    bpm = re.search(r"(\d{2,3})\s*bpm", t)
    return {
        "bpm": float(bpm.group(1)) if bpm else 150.0,
        "euphoric_drop": "euphoric" in t or "melodic" in t or "melodisk" in t,
        "raw_drop": "raw" in t or "aggressive" in t or "aggressiv" in t,
        "text": text,
    }


def _round_phrase(x: float, q: int = 8) -> int:
    return max(q, int(round(x / q)) * q)


def plan(analysis: dict, request: str, *, vocal_bars_target: dict | None = None) -> dict:
    """Return arrangement.json content. Vocal regions of the source are mapped into target sections:
    verse-like vocals -> Verse, the most repeated (hook) section -> Breakdown and drops."""
    req = parse_request(request)
    src_bpm = analysis["tempo"]["bpm"]
    tgt = req["bpm"]
    # choose time base: hardstyle at ~150 usually maps to the source's double-time if it is slow
    ratio_full, ratio_double = tgt / src_bpm, tgt / (src_bpm * 2)
    use_double = abs(1 - ratio_double) < abs(1 - ratio_full)
    eff_src = src_bpm * 2 if use_double else src_bpm
    bar_scale = 2.0 if use_double else 1.0   # one source bar becomes 2 target bars in double-time feel
    stretch = tgt / eff_src

    secs = analysis.get("sections", [])
    vocals = (analysis.get("vocals") or {}).get("regions", [])
    # hook = the section the song is built around: high energy, repeated, ideally with vocals.
    has_vocals = bool(vocals)

    def vocal_cover(sec):
        if not has_vocals:
            return 0.0
        bars = set(range(sec["start_bar"], sec["end_bar"] + 1))
        v = set()
        for r in vocals:
            v |= set(range(r["start_bar"], r["end_bar"] + 1))
        return len(bars & v) / max(1, len(bars))

    from collections import Counter
    cnt = Counter(s["label"] for s in secs)

    def hook_score(sec):
        return sec["energy_value"] * 2 + 0.3 * (cnt[sec["label"]] - 1) + vocal_cover(sec) + 0.02 * sec["length_bars"]

    hook = max(secs, key=hook_score) if secs else None
    verse = None
    if has_vocals:
        cands = [s for s in secs if s is not hook and s["label"] != hook["label"] and vocal_cover(s) > 0.4
                 and s["start_bar"] < hook["start_bar"]]
        verse = cands[0] if cands else None
    def map_src(s):
        if not s:
            return None
        return {"src_start_bar": s["start_bar"], "src_end_bar": s["end_bar"],
                "target_length_bars": _round_phrase(s["length_bars"] * bar_scale)}

    sections, bar = [], 1
    for name, length, role in TEMPLATE:
        if role == "drop_euphoric" and not req["euphoric_drop"] and req["raw_drop"]:
            role = "drop_raw"
        if role == "verse" and verse:
            length = min(32, map_src(verse)["target_length_bars"])
        if role == "breakdown" and hook:
            length = min(32, max(16, map_src(hook)["target_length_bars"]))
        vocal = None
        if has_vocals and role == "verse" and verse:
            vocal = map_src(verse)
        elif has_vocals and role in ("breakdown", "drop_euphoric", "outro") and hook:
            vocal = map_src(hook)
        sections.append({"name": name, "role": role, "start_bar": bar, "length_bars": length,
                         "end_bar": bar + length - 1, "vocal_source": vocal})
        bar += length
    return {
        "request": req, "source_bpm": src_bpm, "target_bpm": tgt,
        "time_base": "double-time" if use_double else "same",
        "stretch_factor": round(stretch, 4),
        "stretch_note": (f"Kilden {src_bpm:.1f} BPM tolkes som {eff_src:.1f} BPM og strekkes {stretch:.3f}x til {tgt:g} BPM."),
        "key": analysis["key"]["key"],
        "progression": (analysis.get("chord_loop") or {}).get("progression")
        or [c["chord"] for c in analysis["chords_per_bar"][:4]],
        "hook_source": {"start_bar": hook["start_bar"], "end_bar": hook["end_bar"]} if hook else None,
        "has_vocals": has_vocals,
        "sections": sections,
        "total_bars": bar - 1,
    }


def _shift(notes: list[Note], beats: float) -> list[Note]:
    return [Note(n.start + beats, n.dur, n.pitch, n.vel) for n in notes]


def _expand_prog(prog: list[str], bar_scale: int = 1) -> list[str]:
    out = []
    for c in prog:
        out += [c] * bar_scale
    return out


def render(arr: dict, seed: int = 2, lead_override: list[Note] | None = None,
           prog_bars_per_chord: int = 2) -> tuple[dict[str, list[Note]], list[tuple[float, str]], list[dict]]:
    """Generate all parts for every section. Returns tracks, markers, timeline rows."""
    prog = _expand_prog(arr["progression"], prog_bars_per_chord)
    h = C.Harmony(arr["key"], prog)
    dark = h.darker()
    anchor = int(arr.get("progression_anchor_bar") or 1)   # source bar where the progression starts

    def rotated(harm, sec):
        """Start the progression where the original was when this section's vocal begins,
        so the remix chords sit under the vocal exactly as in the source."""
        vs = sec.get("vocal_source")
        if not vs:
            return harm
        k = (vs["src_start_bar"] - anchor) * 1 % len(harm.names)
        names = harm.names[k:] + harm.names[:k]
        return C.Harmony(T.key_name(harm.tonic, harm.mode), names)
    tracks: dict[str, list[Note]] = {k: [] for k in (
        "Lead", "Lead Harmony", "Counter", "Chords", "Bass", "Kick", "Screech", "Snare Roll", "Kick Roll")}
    markers, timeline = [], []
    phrase_len = 8 * prog_bars_per_chord // 2 if prog_bars_per_chord > 1 else 8
    base_lead = lead_override or C.lead(h, 16, seed=seed, center=69)
    for s in arr["sections"]:
        off = (s["start_bar"] - 1) * 4
        L = s["length_bars"]
        role = s["role"]
        markers.append((off, s["name"]))
        parts = []
        h_sec = rotated(h, s)

        def put(name, notes):
            tracks[name] += _shift([n for n in notes if n.start < L * 4], off)
            parts.append(name)

        def tile(notes, period_bars):
            out = []
            for k in range(0, L, period_bars):
                out += _shift(notes, k * 4)
            return [n for n in out if n.start < L * 4]

        if role == "intro":
            put("Kick", C.kick_pattern(L, "euphoric"))
            put("Chords", C.chords(h, L, "half", add_root=False))
        elif role == "verse":
            put("Chords", C.chords(h_sec, L, "sustain", add_root=False))
        elif role == "breakdown":
            put("Chords", C.chords(h_sec, L, "sustain"))
            put("Lead", tile(base_lead, 16))
            put("Counter", tile(C.countermelody(h_sec, base_lead, 16), 16))
        elif role in ("buildup", "buildup2"):
            put("Snare Roll", C.snare_roll(L))
            put("Chords", C.chords(h, L, "offbeat" if role == "buildup" else "gated"))
            if role == "buildup2":
                put("Kick Roll", _shift(C.kick_roll(1), (L - 2) * 4))
        elif role == "drop_euphoric":
            put("Kick", C.kick_pattern(L, "euphoric"))
            put("Bass", C.bass(h_sec, L, "offbeat"))
            put("Chords", C.chords(h_sec, L, "sustain"))
            put("Lead", tile(base_lead, 16))
            put("Lead Harmony", tile(C.harmonize(h_sec, base_lead), 16))
        elif role == "midbreak":
            put("Chords", C.chords(dark, L, "sustain", add_root=False))
            put("Lead", tile(C.lead(dark, 8, seed=seed + 1, center=66), 8)[: 8 * 4])  # dark preview, 8 bars
        elif role == "drop_raw":
            put("Kick", C.kick_pattern(L, "rawstyle"))
            put("Screech", tile(C.screech(dark, 8, seed=seed + 2), 8))
            put("Chords", [n for n in C.chords(dark, L, "offbeat", add_root=False) if int(n.start // 4) % 8 >= 4])
        elif role == "outro":
            put("Kick", C.kick_pattern(L, "euphoric"))
            put("Chords", C.chords(h_sec, L, "half", add_root=False))
        for b in range(L):
            gb = s["start_bar"] + b
            row = {"bar": gb, "section": s["name"] if b == 0 else "", "chord": (dark if "raw" in role or role == "midbreak" else h_sec).names[b % len(prog)],
                   "elements": ", ".join(sorted(set(parts))),
                   "vocal": ""}
            if s.get("vocal_source") and b < s["vocal_source"]["target_length_bars"]:
                vs = s["vocal_source"]
                row["vocal"] = f"vokal fra kildetakt {vs['src_start_bar']}-{vs['src_end_bar']}" if b == 0 else "|"
            if role in ("buildup", "buildup2"):
                frac = (b + 1) / L
                row["fx"] = f"riser + HP-filter {int(100 + frac * 900)} Hz" if b % 4 == 0 else ""
                if b == L - 1:
                    row["fx"] = "pre-drop pause på slag 4, impact på neste takt 1"
            elif b == 0 and role.startswith("drop"):
                row["fx"] = "impact + crash"
            timeline.append(row)
    tracks = {k: v for k, v in tracks.items() if v}
    return tracks, markers, timeline


def timeline_markdown(arr: dict, timeline: list[dict]) -> str:
    lines = [f"# Arrangement — {arr['target_bpm']:g} BPM, {arr['key']}", "",
             f"{arr['stretch_note']}", "", "| Seksjon | Takt | Lengde | Elementer | Vokal |", "|---|---|---|---|---|"]
    for s in arr["sections"]:
        v = s.get("vocal_source")
        lines.append(f"| {s['name']} | {s['start_bar']}–{s['end_bar']} | {s['length_bars']} | "
                     f"{next((r['elements'] for r in timeline if r['bar'] == s['start_bar']), '')} | "
                     f"{'kilde ' + str(v['src_start_bar']) + '–' + str(v['src_end_bar']) if v else '–'} |")
    lines += ["", "## Takt for takt", "", "| Takt | Seksjon | Akkord | Elementer | Vokal | FX/automasjon |",
              "|---|---|---|---|---|---|"]
    for r in timeline:
        lines.append(f"| {r['bar']} | {r['section']} | {r['chord']} | {r['elements']} | {r['vocal']} | {r.get('fx', '')} |")
    return "\n".join(lines) + "\n"
