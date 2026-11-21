"""hardstyle-producer command line. Run:  python -m hsp <command> --help"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from .project import HSPError, Project


def _p(msg: str) -> None:
    print(msg, flush=True)


def _np_default(o):
    import numpy as np
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def _clean_json(x):
    return json.loads(json.dumps(x, default=_np_default))


# ------------------------------------------------------------------ steps
def cmd_init(a) -> Project:
    p = Project.create(Path(a.project), Path(a.audio), a.request or "")
    _p(f"Prosjekt klart: {p.root}")
    return p


def cmd_separate(a) -> None:
    from .stems import separate, verify_stem, align_to_grid
    p = Project.open(Path(a.project))
    m = p.load()
    key = f"{m['source_hash']}:{a.quality}"
    if p.is_done("separate", key) and not a.force:
        _p("Stems finnes allerede for denne kilden (bruk --force for å kjøre på nytt).")
        return
    t0 = time.time()
    _p(f"Separerer stems med Demucs ({a.quality}) — kan ta noen minutter på CPU ...")
    outs = separate(p.source, p.path("stems"), a.quality)
    import soundfile as sf
    dur = sf.info(str(p.source)).duration
    report = [verify_stem(o, dur) for o in outs]
    p.write_json("analysis/stems_report.json", _clean_json(report))
    bad = [r for r in report if not r["ok"]]
    if bad:
        raise HSPError("Stem-verifisering feilet: " + "; ".join(f"{r['file']}: {r['warnings']}" for r in bad))
    p.mark_done("separate", key, [f"stems/{o.name}" for o in outs])
    p.log("separate", f"{len(outs)} stems på {time.time() - t0:.0f}s")
    for r in report:
        _p(f"  {r['file']:12} {r['duration_sec']:7.2f}s  {r['sample_rate']} Hz  peak {r['peak_dbfs']} dBFS"
           + (f"  ! {r['warnings']}" if r["warnings"] else ""))


def cmd_analyze(a) -> dict:
    from .analyze import analyze
    p = Project.open(Path(a.project))
    m = p.load()
    have_stems = (p.path("stems") / "other.wav").exists()
    key = f"{m['source_hash']}:{'stems' if have_stems else 'mix'}:v2"
    if p.is_done("analyze", key) and not a.force:
        _p("Analysen er oppdatert (bruk --force for å kjøre på nytt).")
        return p.read_json("analysis/song_analysis.json")
    _p("Analyserer tempo, takt, toneart, akkorder og struktur ...")
    res = _clean_json(analyze(p.source, p.path("stems") if have_stems else None))
    p.write_json("analysis/song_analysis.json", res)
    p.write_json("analysis/chord_progression.json", {
        "key": res["key"]["key"], "loop": res["chord_loop"], "harmony_source": res["harmony_source"],
        "per_bar": res["chords_per_bar"]})
    if res["grid"]["align_pad_sec"] > 0 and have_stems:
        from .stems import align_to_grid
        for st in sorted(p.path("stems").glob("*.wav")):
            align_to_grid(st, p.path("stems", "aligned", st.name), res["grid"]["align_pad_sec"])
    p.mark_done("analyze", key, ["analysis/song_analysis.json", "analysis/chord_progression.json"])
    t, k = res["tempo"], res["key"]
    _p(f"  BPM: {t['bpm']} (konfidens {t['confidence']}, halv {t['half_time']}, dobbel {t['double_time']})")
    _p(f"  Toneart: {k['key']} (konfidens {k['confidence']}; alternativ {k['alternatives'][0]['key']})")
    _p(f"  Takt 1 starter ved {res['downbeat']['first_downbeat']} s (konfidens {res['downbeat']['confidence']})")
    if res["chord_loop"]:
        _p(f"  Akkordløkke: {' – '.join(res['chord_loop']['progression'])} ({res['chord_loop']['occurrences']}x)")
    _p(f"  Seksjoner: " + ", ".join(f"{s['label']}[{s['start_bar']}-{s['end_bar']}]" for s in res["sections"]))
    if res.get("vocals"):
        _p("  Vokal: " + ", ".join(f"takt {r['start_bar']}-{r['end_bar']}" for r in res["vocals"]["regions"]))
    _p(f"  Harmonikilde: {res['harmony_source']}")
    return res


def _stems_for_midi(p: Project, requested: str | None) -> list[Path]:
    names = requested.split(",") if requested else ["vocals", "bass", "other"]
    out = []
    for n in names:
        f = p.path("stems", f"{n}.wav")
        if f.exists():
            out.append(f)
    if not out:
        raise HSPError("Fant ingen stems. Kjør separate-stems først (eller --stems mix for hele miksen).")
    return out


def cmd_extract(a) -> None:
    from .transcribe import basic_pitch_notes, events_to_notes, active_bars, PRESETS
    from .midi_io import write_midi, validate_midi, notes_to_json
    p = Project.open(Path(a.project))
    an = p.read_json("analysis/song_analysis.json")
    bpm = an["tempo"]["bpm"]
    bt = [an["grid"]["first_downbeat_sec"]]  # beat 0 = song bar 1 (NOT the first beat after t=0)
    off = 4 * an["grid"]["fl_bar_offset"]
    raw_all, reports, gates = {}, [], {}
    srep = {r["file"]: r for r in (p.read_json("analysis/stems_report.json")
                                     if p.path("analysis", "stems_report.json").exists() else [])}
    for f in _stems_for_midi(p, a.stems):
        stem = f.stem
        if srep.get(f.name, {}).get("peak_dbfs", 0) < -35:
            _p(f"Hopper over {stem}: stemmen er nesten stille (peak {srep[f.name]['peak_dbfs']} dBFS) — "
               "instrumentet finnes trolig ikke i låten.")
            continue
        _p(f"Transkriberer {stem} (Basic Pitch) ...")
        ev = basic_pitch_notes(f, PRESETS.get(stem, PRESETS["other"]))
        notes = events_to_notes(ev, bt, bpm)
        raw_all[stem] = notes_to_json(notes)
        gates[stem] = active_bars(f, an["grid"]["bar_times_sec"])
        out = p.path("midi", "original", f"{stem}_faithful.mid")
        write_midi(out, {f"{stem} (faithful)": notes}, bpm, offset_beats=off)
        rep = validate_midi(out, bpm, an["key"]["key"])
        reports.append(rep)
        _p(f"  {out.name}: {rep['notes']} noter, {rep['pitch_min']}–{rep['pitch_max']}, i toneart {rep['in_key_ratio']}")
    p.write_json("analysis/transcription_raw.json", raw_all)
    p.write_json("analysis/stem_activity.json", gates)
    p.write_json("analysis/midi_validation_original.json", reports)
    p.log("extract-midi", f"{len(raw_all)} stems transkribert")


def cmd_clean(a) -> None:
    from .transcribe import clean
    from .midi_io import Note, write_midi, validate_midi
    p = Project.open(Path(a.project))
    an = p.read_json("analysis/song_analysis.json")
    raw = p.read_json("analysis/transcription_raw.json")
    gates = p.read_json("analysis/stem_activity.json") if p.path("analysis", "stem_activity.json").exists() else {}
    bpm, key = an["tempo"]["bpm"], an["key"]["key"]
    off = 4 * an["grid"]["fl_bar_offset"]
    report, cleaned = {}, {}
    for stem, notes in raw.items():
        ns = [Note(n["start"], n["dur"], n["pitch"], n["vel"]) for n in notes]
        parts, stats = clean(ns, stem, key, gates.get(stem))
        report[stem] = stats
        for part, pn in parts.items():
            if not pn:
                continue
            out = p.path("midi", "cleaned", f"{stem}_{part}.mid")
            write_midi(out, {f"{stem} {part} (cleaned)": pn}, bpm, offset_beats=off)
            v = validate_midi(out, bpm, key)
            cleaned[f"{stem}_{part}"] = [n.__dict__ for n in pn]
            _p(f"  {out.name}: {v['notes']} noter (fra {stats['input_notes']} rå, {stats['leakage_removed']} lekkasje fjernet), grid {stats['grid']}, "
               f"oktavfiks {stats['octave_fixes']}, utenfor toneart {stats['out_of_key_ratio']:.0%}")
    p.write_json("analysis/midi_cleanup_report.json", report)
    p.write_json("analysis/cleaned_notes.json", cleaned)
    p.log("clean-midi", "renset MIDI skrevet")


def _harmony_from(p: Project, a):
    from .compose import Harmony
    an = p.read_json("analysis/song_analysis.json") if p.path("analysis", "song_analysis.json").exists() else None
    key = a.key or (an["key"]["key"] if an else None)
    prog = a.progression.split(",") if a.progression else (
        (an.get("chord_loop") or {}).get("progression") if an else None)
    if not key or not prog:
        raise HSPError("Trenger toneart og akkorder: kjør analyze-song, eller gi --key og --progression.")
    expanded = []
    for c in prog:
        expanded += [c] * a.bars_per_chord
    return Harmony(key, expanded), key


def cmd_generate(a) -> None:
    from . import compose as C
    from .midi_io import write_midi, validate_midi
    p = Project.open(Path(a.project))
    h, key = _harmony_from(p, a)
    if a.dark:
        h = h.darker()
    bpm = a.bpm or p.load().get("target_bpm") or 150
    bars = a.bars
    part = a.part
    if part == "lead":
        L = C.lead(h, bars, seed=a.seed, center=a.center)
        tracks = {"Lead": L, "Lead Harmony": C.harmonize(h, L), "Counter": C.countermelody(h, L, bars)}
    elif part == "chords":
        tracks = {"Chords": C.chords(h, bars, a.style or "sustain")}
    elif part == "bass":
        tracks = {"Bass": C.bass(h, bars, a.style or "offbeat"), "Kick (tonal)": C.tonal_kick(h, bars)}
    elif part == "screech":
        tracks = {"Screech": C.screech(h.darker() if not a.dark else h, bars, seed=a.seed)}
    elif part == "build-up":
        tracks = {"Snare Roll": C.snare_roll(bars), "Chords": C.chords(h, bars, "offbeat"),
                  "Kick Roll": [type(n)(n.start + (bars - 1) * 4, n.dur, n.pitch, n.vel) for n in C.kick_roll(1)]}
    elif part == "drop":
        style = "rawstyle" if a.dark else "euphoric"
        L = C.lead(h, bars, seed=a.seed, center=a.center)
        tracks = {"Kick": C.kick_pattern(bars, style), "Bass": C.bass(h, bars, "offbeat"),
                  "Chords": C.chords(h, bars, "sustain")}
        if a.dark:
            tracks["Screech"] = C.screech(h, bars, seed=a.seed)
        else:
            tracks.update({"Lead": L, "Lead Harmony": C.harmonize(h, L)})
    else:
        raise HSPError(f"Ukjent del: {part}")
    name = f"{part}{'_dark' if a.dark else ''}_seed{a.seed}.mid"
    out = p.path("midi", "generated", name)
    p.backup(out)
    write_midi(out, tracks, bpm)
    v = validate_midi(out, bpm, T_key(h))
    _p(f"Skrev {out.relative_to(p.root)}: {v['tracks']}  {v['pitch_min']}–{v['pitch_max']}  i toneart {v['in_key_ratio']}")
    for w in v["warnings"]:
        _p(f"  ! {w}")


def T_key(h) -> str:
    from . import theory as T
    return T.key_name(h.tonic, h.mode)


def _vocal_arrangement(p: Project, an: dict, arr: dict, out: Path) -> Path | None:
    import numpy as np
    import soundfile as sf
    voc = p.path("stems", "vocals.wav")
    if not voc.exists():
        return None
    from pedalboard import time_stretch
    data, sr = sf.read(str(voc), dtype="float32", always_2d=True)
    bars = an["grid"]["bar_times_sec"]
    tgt_bar = 4 * 60.0 / arr["target_bpm"]
    total = np.zeros((int((arr["total_bars"] + 1) * tgt_bar * sr), data.shape[1]), dtype=np.float32)
    placed = 0
    for s in arr["sections"]:
        vs = s.get("vocal_source")
        if not vs:
            continue
        a0 = bars[max(0, vs["src_start_bar"] - 1)]
        a1 = bars[min(len(bars) - 1, vs["src_end_bar"])]
        seg = data[int(a0 * sr): int(a1 * sr)]
        if len(seg) < sr // 4:
            continue
        st = time_stretch(seg.T, sr, stretch_factor=arr["stretch_factor"], high_quality=True).T
        maxlen = int(min(s["length_bars"], vs["target_length_bars"]) * tgt_bar * sr)
        st = st[:maxlen]
        fade = min(len(st), int(0.02 * sr))
        st[-fade:] *= np.linspace(1, 0, fade)[:, None]
        i0 = int((s["start_bar"] - 1) * tgt_bar * sr)
        total[i0:i0 + len(st)] += st[: len(total) - i0]
        placed += 1
    if not placed:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), total, sr, subtype="PCM_24")
    return out


def _vocal_extras(p: Project, an: dict, arr: dict) -> None:
    """Full vocal stem stretched to target BPM with song bar 1 on FL bar 2, plus the vocal hook as lead MIDI."""
    import numpy as np
    import soundfile as sf
    from .midi_io import Note, write_midi
    tgt = arr["target_bpm"]
    voc = p.path("stems", "vocals.wav")
    if voc.exists() and arr.get("has_vocals"):
        from pedalboard import time_stretch
        d, sr = sf.read(str(voc), dtype="float32", always_2d=True)
        st = time_stretch(d.T, sr, stretch_factor=arr["stretch_factor"], high_quality=True).T
        bar = 4 * 60.0 / tgt
        first = an["grid"]["first_downbeat_sec"] / arr["stretch_factor"]
        pad = (bar - first) % bar or bar
        out = np.vstack([np.zeros((int(round(pad * sr)), d.shape[1]), np.float32), st])
        sf.write(str(p.path("arrangement", f"vocals_full_{int(tgt)}bpm_bar2.wav")), out, sr, subtype="PCM_24")
    cn = p.read_json("analysis/cleaned_notes.json") if p.path("analysis", "cleaned_notes.json").exists() else {}
    mel, hook = cn.get("vocals_melody"), arr.get("hook_source")
    if mel and hook:
        scale = 2.0 if arr["time_base"] == "double-time" else 1.0
        b0 = (hook["start_bar"] - 1) * 4
        b1 = hook["end_bar"] * 4
        ns = [Note((n["start"] - b0) * scale, n["dur"] * scale, n["pitch"], max(100, n["vel"])) for n in mel
              if b0 <= n["start"] < b1]
        if ns:
            med = sorted(n.pitch for n in ns)[len(ns) // 2]
            sh = 12 * round((69 - med) / 12)
            write_midi(p.path("midi", "generated", "lead_from_vocal_hook.mid"),
                       {"Lead (vocal hook)": [Note(n.start, n.dur, n.pitch + sh, n.vel) for n in ns]}, tgt)


def cmd_package(a) -> None:
    """Copy the deliverables (same relative paths as the guide) to one folder. Skips source audio/stems."""
    p = Project.open(Path(a.project))
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        raise HSPError(f"{out} finnes og er ikke tom — velg en ny mappe (vi overskriver aldri).")
    pats = ["arrangement/*", "fl-studio/*.md", "midi/**/*.mid", "exports/*.mp3",
            "analysis/song_analysis.json", "analysis/chord_progression.json", "analysis/midi_cleanup_report.json"]
    n = 0
    for pat in pats:
        for f in p.root.glob(pat):
            if f.is_file():
                dest = out / f.relative_to(p.root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                n += 1
    _p(f"Pakket {n} filer til {out}")


def cmd_plan(a) -> None:
    from .arrange import plan, render, timeline_markdown
    from .midi_io import Note, write_midi, validate_midi
    from . import compose as C
    p = Project.open(Path(a.project))
    an = p.read_json("analysis/song_analysis.json")
    req = a.request or p.load().get("request") or "150 BPM euphoric hardstyle remix"
    arr = plan(an, req)
    if a.progression:
        arr["progression"] = a.progression.split(",")
        arr["progression_source"] = "manual (--progression)"
    if getattr(a, "anchor_bar", None):
        arr["progression_anchor_bar"] = a.anchor_bar
    elif an.get("chord_loop"):
        arr["progression_anchor_bar"] = an["chord_loop"]["start_bars"][0]
    lead_override = None
    if a.lead_from_vocals:
        cn = p.read_json("analysis/cleaned_notes.json") if p.path("analysis", "cleaned_notes.json").exists() else {}
        mel = cn.get("vocals_melody")
        if not mel:
            raise HSPError("--lead-from-vocals krever renset vokal-MIDI (kjør extract-midi og clean-midi).")
        hook = next((s["vocal_source"] for s in arr["sections"] if s["role"] == "breakdown" and s.get("vocal_source")), None)
        if hook is None and arr.get("hook_source"):
            hook = {"src_start_bar": arr["hook_source"]["start_bar"]}
        scale = 2.0 if arr["time_base"] == "double-time" else 1.0
        b0 = ((hook["src_start_bar"] - 1) * 4) if hook else 0
        notes = [Note((n["start"] - b0) * scale, n["dur"] * scale, n["pitch"], n["vel"]) for n in mel
                 if n["start"] >= b0 and (n["start"] - b0) * scale < 64]
        if notes:
            med = sorted(n.pitch for n in notes)[len(notes) // 2]
            shift = 12 * round((69 - med) / 12)
            lead_override = [Note(n.start, n.dur, n.pitch + shift, max(100, n.vel)) for n in notes]
            _p(f"Bruker vokal-hooken som lead ({len(notes)} noter, transponert {shift:+d} halvtoner).")
    tracks, markers, timeline = render(arr, seed=a.seed, lead_override=lead_override,
                                       prog_bars_per_chord=a.bars_per_chord)
    arr["seed"] = a.seed
    arr["bars_per_chord"] = a.bars_per_chord
    p.write_json("arrangement/arrangement.json", arr)
    md = timeline_markdown(arr, timeline)
    p.backup(p.path("arrangement", "arrangement.md"))
    p.path("arrangement", "arrangement.md").write_text(md, encoding="utf-8")
    out = p.path("arrangement", "arrangement.mid")
    p.backup(out)
    write_midi(out, tracks, arr["target_bpm"], markers=markers)
    v = validate_midi(out, arr["target_bpm"], arr["key"], expect_beats=arr["total_bars"] * 4)
    p.write_json("analysis/midi_validation_arrangement.json", v)
    # separate per-part files for convenience
    for name, notes in tracks.items():
        fn = name.lower().replace(" ", "_") + ".mid"
        write_midi(p.path("midi", "generated", fn), {name: notes}, arr["target_bpm"])
    voc = _vocal_arrangement(p, an, arr, p.path("arrangement", f"vocals_arranged_{int(arr['target_bpm'])}bpm.wav"))
    _vocal_extras(p, an, arr)
    m = p.load()
    m["target_bpm"] = arr["target_bpm"]
    p.save(m)
    _p(f"Arrangement: {arr['total_bars']} takter @ {arr['target_bpm']:g} BPM ({arr['stretch_note']})")
    for s in arr["sections"]:
        _p(f"  {s['start_bar']:>4}–{s['end_bar']:<4} {s['name']:<15}" + (
            f" vokal fra kildetakt {s['vocal_source']['src_start_bar']}-{s['vocal_source']['src_end_bar']}" if s.get("vocal_source") else ""))
    _p(f"  MIDI: {v['notes']} noter i {len(v['tracks'])} spor, {v['length_bars']} takter, i toneart {v['in_key_ratio']}"
       + (" ✓" if v["ok"] else f" FEIL {v['errors']}"))
    if voc:
        _p(f"  Vokal plassert: {voc.relative_to(p.root)}")


def cmd_prepare_fl(a) -> None:
    from .fl import import_guide, production_notes
    p = Project.open(Path(a.project))
    an = p.read_json("analysis/song_analysis.json")
    arr = p.read_json("arrangement/arrangement.json")
    voc = next(p.path("arrangement").glob("vocals_arranged_*.wav"), None)
    flp = next(p.path("fl-studio").glob("*.flp"), None)
    files = {"arrangement_mid": "arrangement/arrangement.mid",
             "flp": str(flp.relative_to(p.root)) if flp else None,
             "vocals_arranged": str(voc.relative_to(p.root)) if voc else None}
    g = import_guide(p.root.name, arr, files, an)
    for rel, txt in (("fl-studio/fl_studio_import_guide.md", g),
                     ("fl-studio/production_notes.md", production_notes(arr, an))):
        f = p.path(rel)
        p.backup(f)
        f.write_text(txt, encoding="utf-8")
        _p(f"Skrev {rel}")


def cmd_chord_check(a) -> None:
    """Per bar: detected chord (stems) + bass notes. Bass decides inversions (e.g. Fm vs Db/F) and the loop.
    Prints a suggested progression + anchor bar for plan-arrangement."""
    from collections import Counter
    from . import theory as T
    p = Project.open(Path(a.project))
    an = p.read_json("analysis/song_analysis.json")
    cn = p.read_json("analysis/cleaned_notes.json") if p.path("analysis", "cleaned_notes.json").exists() else {}
    bass = cn.get("bass_bass", [])
    flats = T.uses_flats(an["key"]["tonic_pc"], an["key"]["mode"])
    lo, hi = (int(x) for x in a.bars.split("-")) if a.bars else (1, len(an["chords_per_bar"]))
    rows = []
    for c in an["chords_per_bar"][lo - 1:hi]:
        b = c["bar"]
        bn = [n for n in bass if (b - 1) * 4 <= n["start"] < b * 4]
        main = max(bn, key=lambda n: n["dur"])["pitch"] % 12 if bn else None
        chord = c["chord"]
        if main is not None and chord != "N":
            r, q = T.parse_chord(chord)
            if main not in T.chord_pcs(r, q):
                # bass not in the chord -> try the diatonic chord that contains it as a third (inversion) or root
                for deg in range(7):
                    r2, q2 = T.diatonic_triad(an["key"]["tonic_pc"], an["key"]["mode"], deg)
                    if main == r2:
                        chord = T.chord_name(r2, q2, flats)
                        break
            elif main != r:
                chord = f"{chord}/{T.pc_name(main, flats)}"
        rows.append((b, c["chord"], c.get("confidence", 0), T.pc_name(main, flats) if main is not None else "-", chord))
        _p(f"  takt {b:>3}: akkord {c['chord']:<5} (konf {c.get('confidence', 0):.2f})  bass {rows[-1][3]:<3} -> {chord}")
    # most common 4-bar loop, trying all 4 phases; uses the analysed chord (bass only annotates)
    names = [r[1] for r in rows]
    best = None
    for ph in range(4):
        cnt = Counter(tuple(names[i:i + 4]) for i in range(ph, len(names) - 3, 4) if "N" not in names[i:i + 4])
        if cnt:
            w, n = cnt.most_common(1)[0]
            if best is None or n > best[1]:
                best = (w, n, lo + ph)
    if best:
        _p(f"\nForslag: --progression {','.join(best[0])} --bars-per-chord 1 --anchor-bar {best[2]}  "
           f"({best[1]}x av {len(names) // 4} firetakters-vinduer). Sjekk takter der 'bass ->' avviker.")


def cmd_verify(a) -> None:
    """QC: for every bar where a source vocal is placed, compare the ORIGINAL chord under that vocal bar
    (from the analysis) with the chord the remix puts there (from the arrangement MIDI bass).
    Low agreement = the vocal will clash -> wrong --progression or --anchor-bar."""
    from .midi_io import read_midi_beats
    p = Project.open(Path(a.project))
    arr = p.read_json("arrangement/arrangement.json")
    an = p.read_json("analysis/song_analysis.json")
    src = {c["bar"]: c.get("root_pc") for c in an["chords_per_bar"]}
    tr, _ = read_midi_beats(p.path("arrangement", "arrangement.mid"))
    bass = {}
    for n in sorted(tr.get("Bass", []) or tr.get("Chords", []), key=lambda n: (n.start, n.pitch)):
        bass.setdefault(int(n.start // 4) + 1, n.pitch % 12)
    from . import theory as T
    pcs_by_bar: dict[int, set] = {}
    for n in tr.get("Chords", []):
        pcs_by_bar.setdefault(int(n.start // 4) + 1, set()).add(n.pitch % 12)
    sec_chords = {}
    for b, pcs in pcs_by_bar.items():        # identify the triad from all chord notes (voicing-independent)
        for r in range(12):
            if any(set(T.chord_pcs(r, q)) <= pcs for q in ("maj", "min", "dim")):
                sec_chords[b] = r
                break
    scale = 2 if arr["time_base"] == "double-time" else 1
    total_hit = total = 0
    checked = False
    for sec in arr["sections"]:
        vs = sec.get("vocal_source")
        if not vs:
            continue
        hit = n = 0
        for b in range(min(sec["length_bars"], vs["target_length_bars"])):
            sbar = vs["src_start_bar"] + b // scale
            tbar = sec["start_bar"] + b
            remix_root = sec_chords.get(tbar, bass.get(tbar))
            if src.get(sbar) is None or remix_root is None:
                continue
            n += 1
            hit += remix_root == src[sbar]
        if n:
            checked = True
            total_hit += hit
            total += n
            _p(f"  {sec['name']:<15} takter med vokal: {n:>3}  samme akkord som originalen: {hit / n:.0%}")
        else:
            _p(f"  {sec['name']:<15} (ingen bass/akkorder å sammenligne i denne seksjonen)")
    if not checked:
        _p("Ingen vokal-seksjoner med akkorder å kontrollere.")
        return
    rate = total_hit / total
    _p(f"Totalt: {rate:.0%} av vokal-taktene har samme akkord som i originalen.")
    if rate < 0.6:
        raise HSPError("Vokal og akkorder kolliderer trolig. Kjør chord-check og juster --progression/--anchor-bar.")
    _p("KONTROLL BESTÅTT")


TEMPLATE_FLP = Path(__file__).resolve().parents[2] / "templates" / "hardstyle_mal.flp"


def cmd_build_flp(a) -> None:
    """Organised FL Studio project: one pattern per instrument per section, one named Playlist track per
    instrument, clips at the right bars, section markers, tempo. Source: arrangement.mid + arrangement.json,
    or --from-flp to reorganise an existing project (keeps the user's edits)."""
    from .flp_organize import build, verify, tracks_from_flp
    from .midi_io import read_midi_beats
    p = Project.open(Path(a.project))
    arr = p.read_json("arrangement/arrangement.json")
    template = Path(a.template) if a.template else TEMPLATE_FLP
    if not template.exists():
        raise HSPError(f"Fant ikke FL-malen: {template}")
    if a.from_flp:
        tracks = tracks_from_flp(Path(a.from_flp))
        src = Path(a.from_flp)
        template = src            # keep the user's own channels/sounds/mixer
    else:
        tracks, _ = read_midi_beats(p.path("arrangement", "arrangement.mid"))
        src = p.path("arrangement", "arrangement.mid")
    order = ["Lead", "Lead Harmony", "Counter", "Chords", "Bass", "Kick", "Screech", "Snare Roll", "Kick Roll"]
    tracks = {k: tracks[k] for k in order if k in tracks} | {k: v for k, v in tracks.items() if k not in order}
    out = Path(a.out) if a.out else p.path("fl-studio", f"{p.root.name}.flp")
    if out.exists():
        raise HSPError(f"{out} finnes allerede — velg et annet navn (overskriver aldri).")
    out.parent.mkdir(parents=True, exist_ok=True)
    total_in = sum(len(v) for v in tracks.values())
    try:
        r = build(template, out, tracks, arr["sections"], bpm=arr["target_bpm"])
    except ValueError as e:
        raise HSPError(str(e)) from e
    v = verify(out)
    total_out = sum(c for _, c, _ in v["patterns"].values())
    _p(f"Bygget {out.name} fra {src.name}: {r['patterns']} mønstre, {r['clips']} klipp, "
       f"{len(r['tracks'])} Playlist-spor, {total_out}/{total_in} noter.")
    for d in r["detail"]:
        _p(f"  spor {d['track']:>2}  takt {d['start_bar']:>3}  {d['bars']:>3} takter  {d['name']}")
    if total_out != total_in:
        raise HSPError("Antall noter stemmer ikke etter bygging — filen må ikke brukes.")


def cmd_preview(a) -> None:
    from .preview import render
    p = Project.open(Path(a.project))
    arr = p.read_json("arrangement/arrangement.json")
    voc = next(p.path("arrangement").glob("vocals_arranged_*.wav"), None)
    out = p.path("exports", "preview_rough.wav")
    from . import theory as T
    render(p.path("arrangement", "arrangement.mid"), out, arr["target_bpm"], voc, a.max_bars,
           kick_root_pc=T.parse_key(arr["key"])[0])
    mp3 = out.with_suffix(".mp3")
    import subprocess
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-b:a", "192k", str(mp3)], check=False)
    _p(f"Grov forhåndslytt (enkle synther, ikke ferdig lyd): {out.relative_to(p.root)}")


def cmd_diagnose(a) -> None:
    from .diagnose import run
    r = run()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    if a.project:
        p = Project.open(Path(a.project))
        p.write_json("analysis/diagnose.json", r)


def cmd_samples(a) -> None:
    from .samples import build_inventory, suggest
    out = Path(a.out)
    if a.roots:
        s = build_inventory([Path(r) for r in a.roots], out)
        _p(f"Inventar: {s['total']} filer. Per rolle: {s['by_role']}")
    if a.role:
        res = suggest(out / "samples_inventory.json", a.role, a.key, a.bpm, a.query)
        if not res:
            _p(f"Ingen verifiserte samples med rolle '{a.role}'.")
        for it in res:
            _p(f"  {it['file']}  [{it['pack']}]  {it.get('key', '')} {it.get('bpm', '')}\n    {it['path']}")


def cmd_run(a) -> None:
    """Full pipeline: init -> stems -> analyze -> extract -> clean -> plan -> prepare-fl."""
    a.force = getattr(a, "force", False)
    cmd_init(a)
    if not a.no_stems:
        cmd_separate(a)
    cmd_analyze(a)
    if not a.no_stems:
        a.stems = None
        cmd_extract(a)
        cmd_clean(a)
    cmd_plan(a)
    a.template = a.out = a.from_flp = None
    cmd_build_flp(a)
    cmd_prepare_fl(a)
    a.max_bars = None
    cmd_preview(a)
    _p(f"\nFerdig. Åpne {Path(a.project) / 'fl-studio' / 'fl_studio_import_guide.md'}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hsp", description="hardstyle-producer pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def proj(sp):
        sp.add_argument("--project", "-p", required=True, help="Prosjektmappe")
        sp.add_argument("--force", action="store_true", help="Kjør på nytt selv om resultat finnes")

    s = sub.add_parser("init", help="Opprett prosjektmappe og kopier inn lydfil")
    s.add_argument("audio"); proj(s); s.add_argument("--request", default="")
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("separate-stems"); proj(s)
    s.add_argument("--quality", default="fast", help="fast (htdemucs) | high (htdemucs_ft) | 6stem")
    s.set_defaults(fn=cmd_separate)
    s = sub.add_parser("analyze-song"); proj(s); s.set_defaults(fn=cmd_analyze)
    s = sub.add_parser("extract-midi"); proj(s); s.add_argument("--stems", default=None, help="f.eks. vocals,bass")
    s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("clean-midi"); proj(s); s.set_defaults(fn=cmd_clean)
    for part in ("lead", "chords", "bass", "screech", "build-up", "drop"):
        s = sub.add_parser(f"generate-{part}"); proj(s)
        s.add_argument("--bars", type=int, default=16 if part != "build-up" else 16)
        s.add_argument("--seed", type=int, default=2)
        s.add_argument("--key"); s.add_argument("--progression", help="f.eks. Db,Gb,Ab,Bbm")
        s.add_argument("--bars-per-chord", type=int, default=2)
        s.add_argument("--bpm", type=float); s.add_argument("--center", type=int, default=69)
        s.add_argument("--style"); s.add_argument("--dark", action="store_true", help="Parallell moll / rawstyle")
        s.set_defaults(fn=cmd_generate, part=part)
    s = sub.add_parser("plan-arrangement"); proj(s)
    s.add_argument("--request"); s.add_argument("--seed", type=int, default=2)
    s.add_argument("--progression"); s.add_argument("--bars-per-chord", type=int, default=2)
    s.add_argument("--lead-from-vocals", action="store_true", help="Bruk vokal-hooken som lead-melodi")
    s.add_argument("--anchor-bar", type=int, help="Kildetakt der akkordprogresjonen starter")
    s.set_defaults(fn=cmd_plan)
    s = sub.add_parser("prepare-fl-studio"); proj(s); s.set_defaults(fn=cmd_prepare_fl)
    s = sub.add_parser("chord-check", help="Akkord + bass per takt, foreslår progresjon"); proj(s)
    s.add_argument("--bars", help="f.eks. 17-40 (et refreng)"); s.set_defaults(fn=cmd_chord_check)
    s = sub.add_parser("verify", help="Sjekk at vokal og akkorder sitter sammen"); proj(s); s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("build-flp", help="Lag ferdig organisert FL Studio-prosjekt (.flp)"); proj(s)
    s.add_argument("--template"); s.add_argument("--out")
    s.add_argument("--from-flp", help="Omorganiser et eksisterende prosjekt (beholder dine endringer)")
    s.set_defaults(fn=cmd_build_flp)
    s = sub.add_parser("package", help="Samle leveransen i én mappe"); proj(s)
    s.add_argument("--out", required=True); s.set_defaults(fn=cmd_package)
    s = sub.add_parser("preview", help="Grov lyd-forhåndsvisning av arrangementet"); proj(s)
    s.add_argument("--max-bars", type=int); s.set_defaults(fn=cmd_preview)
    s = sub.add_parser("diagnose"); s.add_argument("--project", "-p"); s.set_defaults(fn=cmd_diagnose)
    s = sub.add_parser("samples", help="Bygg/søk i sample-inventar")
    s.add_argument("--roots", nargs="*"); s.add_argument("--out", required=True)
    s.add_argument("--role"); s.add_argument("--key"); s.add_argument("--bpm", type=float); s.add_argument("--query")
    s.set_defaults(fn=cmd_samples)
    s = sub.add_parser("run", help="Hele pipelinen fra lydfil til FL-klare filer")
    s.add_argument("audio"); proj(s); s.add_argument("--request", default="150 BPM euphoric hardstyle remix, melodic first drop, rawstyle second drop")
    s.add_argument("--quality", default="fast"); s.add_argument("--seed", type=int, default=2)
    s.add_argument("--progression"); s.add_argument("--bars-per-chord", type=int, default=2)
    s.add_argument("--lead-from-vocals", action="store_true"); s.add_argument("--no-stems", action="store_true")
    s.set_defaults(fn=cmd_run)

    a = ap.parse_args(argv)
    try:
        a.fn(a)
        return 0
    except HSPError as e:
        print(f"FEIL: {e}", file=sys.stderr)
        try:
            if getattr(a, "project", None):
                Project.open(Path(a.project)).log(a.cmd, str(e), ok=False)
        except Exception:  # noqa: BLE001
            pass
        return 2
