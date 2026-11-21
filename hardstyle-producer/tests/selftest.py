"""End-to-end self test on a synthetic song with known answers (Db major, 144 BPM, Db-Gb-Ab-Bbm).
Run after install:  .venv/bin/python tests/selftest.py   (Windows: .venv\\Scripts\\python.exe tests\\selftest.py)"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
env = dict(os.environ, PYTHONPATH=str(ROOT / "scripts"))
fails = []


def check(name, cond, detail=""):
    print(f"  [{'OK' if cond else 'FEIL'}] {name} {detail}")
    if not cond:
        fails.append(name)


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    wav = td / "test_song.wav"
    subprocess.run([sys.executable, str(HERE / "make_test_song.py"), str(wav)], check=True)
    r = subprocess.run([sys.executable, "-m", "hsp", "run", str(wav), "-p", str(td / "proj"), "--request",
                        "150 BPM euphoric hardstyle remix, melodic first drop, rawstyle second drop"],
                       env=env, capture_output=True, text=True)
    print(r.stdout[-2500:])
    check("pipeline exit code", r.returncode == 0, r.stderr[-800:] if r.returncode else "")
    if r.returncode == 0:
        a = json.loads((td / "proj/analysis/song_analysis.json").read_text())
        check("tempo 144", abs(a["tempo"]["bpm"] - 144) < 0.5, str(a["tempo"]["bpm"]))
        check("key Db major", a["key"]["key"] in ("Db major", "C# major"), a["key"]["key"])
        check("downbeat ~0.30s", abs(a["downbeat"]["first_downbeat"] - 0.30) < 0.05, str(a["downbeat"]["first_downbeat"]))
        truth = ["Db", "Gb", "Ab", "Bbm"] * 8
        got = [c["chord"] for c in a["chords_per_bar"]][:32]
        acc = sum(g == t for g, t in zip(got, truth)) / 32
        # Demucs is not fully deterministic: 84-91% seen on identical input
        check("chord accuracy >= 80%", acc >= 0.80, f"{acc:.0%}")
        v = json.loads((td / "proj/analysis/midi_validation_arrangement.json").read_text())
        check("arrangement MIDI valid", v["ok"] and v["notes"] > 500 and abs(v["bpm"] - 150) < 0.01, f"{v['notes']} notes")
        for f in ("fl-studio/fl_studio_import_guide.md", "fl-studio/production_notes.md", "arrangement/arrangement.md",
                  "exports/preview_rough.wav", "midi/cleaned/other_melody.mid"):
            check(f"exists {f}", (td / "proj" / f).exists() and (td / "proj" / f).stat().st_size > 100)
# FL Studio project writer: separate patterns per instrument/section, own Playlist track, exact timing
sys.path.insert(0, str(ROOT / "scripts"))
from hsp import compose as C  # noqa: E402
from hsp.flp import FLP, unpack_notes  # noqa: E402
from hsp.flp_organize import build, verify, tracks_from_flp  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    tpl = ROOT / "templates" / "hardstyle_mal.flp"
    raw = tpl.read_bytes()
    check("FLP template parses + round-trips byte-identical", FLP.read(tpl).to_bytes() == raw)
    h = C.Harmony("Db major", ["Gb", "Ab", "Db", "Bbm"])
    tracks = {"Lead": [type(n)(n.start + 32, n.dur, n.pitch, n.vel) for n in C.lead(h, 8, seed=2)],
              "Chords": C.chords(h, 16), "Bass": C.bass(h, 16), "Kick": C.kick_pattern(16)}
    secs = [{"name": "Intro", "start_bar": 1, "length_bars": 8}, {"name": "Drop", "start_bar": 9, "length_bars": 8}]
    out = Path(td) / "t.flp"
    r = build(tpl, out, tracks, secs, bpm=150)
    v = verify(out)
    check("FLP: one pattern per instrument per section", r["patterns"] == 7 and all(len(x[2]) == 1 for x in v["patterns"].values()),
          f"{r['patterns']} patterns")
    check("FLP: each instrument on its own named track", v["track_names"][:4] == ["Lead", "Chords", "Bass", "Kick"])
    back = tracks_from_flp(out)
    tick = 1 / FLP.read(out).ppq   # FL projects run at 96 PPQ: lengths round to the nearest tick, starts are exact
    same = True
    for k in tracks:
        A = sorted((round(n.start, 6), n.pitch, n.dur) for n in tracks[k])
        B = sorted((round(n.start, 6), n.pitch, n.dur) for n in back[k])
        same &= len(A) == len(B) and all(a[0] == b[0] and a[1] == b[1] and abs(a[2] - b[2]) <= tick for a, b in zip(A, B))
    check("FLP: every note keeps its start exactly (length within 1 tick)", same)
    check("FLP: lead clip starts at bar 9", any(i["bar"] == 9 and i["track"] == 1 for i in v["items"]))
    check("FLP: tempo 150", any(e.id == 156 and e.value == 150000 for e in FLP.read(out).events))

# Regression: long intro (lead-in > 1 beat) must not shift MIDI (bug found on MAGIC! - Rude)
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    wav = td / "late.wav"
    subprocess.run([sys.executable, str(HERE / "make_test_song.py"), str(wav), "1.30"], check=True)
    for cmd in (["init", str(wav)], ["separate-stems"], ["analyze-song"], ["extract-midi", "--stems", "other"], ["clean-midi"]):
        rr = subprocess.run([sys.executable, "-m", "hsp", *cmd, "-p", str(td / "p")], env=env, capture_output=True, text=True)
        if rr.returncode:
            print(rr.stderr[-600:])
    a = json.loads((td / "p/analysis/song_analysis.json").read_text())
    check("late intro: downbeat ~1.30s", abs(a["downbeat"]["first_downbeat"] - 1.30) < 0.05, str(a["downbeat"]["first_downbeat"]))
    cn = json.loads((td / "p/analysis/cleaned_notes.json").read_text())["other_melody"]
    truth = json.loads(wav.with_name("late_truth.json").read_text())["melody_notes"]
    tset = {((t["bar"] - 1) * 4 + t["beat"], t["midi"]) for t in truth}
    hits = len(tset & {(n["start"], n["pitch"]) for n in cn})
    check("late intro: melody on correct beats (recall >= 70%)", hits / len(tset) >= 0.7, f"{hits}/{len(tset)}")

print("\nSELVTEST:", "BESTÅTT" if not fails else f"FEILET ({', '.join(fails)})")
sys.exit(1 if fails else 0)
