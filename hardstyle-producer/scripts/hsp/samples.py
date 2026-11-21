"""Searchable inventory of the user's own sample packs. Only reports files that actually exist."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

AUDIO_EXT = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".ogg"}
PRESET_EXT = {".fst", ".nmsv", ".fxp", ".fxb", ".flp", ".mid"}

ROLES = {  # role -> keywords matched against path (folder + filename), checked in order
    "zaag": ["zaag", "uptempo"],
    "kick_roll": ["kick roll", "kick_roll", "kickroll"],
    "kick": ["kick", "bd", "bassdrum"],
    "kick_tail": ["tail"],
    "clap": ["clap"],
    "snare": ["snare", "snr"],
    "hat": ["hat", "hihat", "hh", "ride", "cymbal", "crash"],
    "screech": ["screech", "screeches"],
    "lead": ["lead", "supersaw", "saw"],
    "riser": ["riser", "rise", "uplifter", "sweep up", "upsweep", "build up", "buildup", "build-up"],
    "downlifter": ["downlifter", "downsweep", "fall"],
    "impact": ["impact", "hit", "boom", "sub drop", "subdrop"],
    "reverse": ["reverse", "rev "],
    "atmosphere": ["atmos", "atmosphere", "ambience", "ambient", "pad", "drone", "texture"],
    "vocal": ["vocal", "vox", "chant", "shout", "spoken"],
    "fx": ["fx", "sfx", "noise", "white noise", "zap", "laser"],
    "loop": ["loop"],
    "midi": [".mid"],
}
KEY_RE = re.compile(r"(?<![a-z])([a-g](?:#|b|sharp|flat)?)\s*(m(?:in(?:or)?)?|maj(?:or)?)?(?![a-z])", re.I)
BPM_RE = re.compile(r"(\d{2,3})\s*bpm", re.I)


def classify(path: Path) -> list[str]:
    s = str(path).lower().replace("_", " ").replace("-", " ")
    roles = []
    for role, kws in ROLES.items():
        if any(k in s for k in kws):
            roles.append(role)
    if "kick" in roles and "screech" in roles:
        roles.remove("kick")
    return roles or ["other"]


_KEY_TOKEN = re.compile(r"(?:^|[_\s\-\(\[])([A-G](?:#|b|s(?=[_\s\-m]))?)(m|min|minor|maj|major)?(?=$|[_\s\-\)\]])")


def parse_meta(name: str) -> dict:
    """BPM + key from a sample filename. Handles F#, G#m, Emin, Fm, 'F#_Female', 'Gmin_High' ..."""
    meta = {}
    stem = Path(name).stem
    m = BPM_RE.search(stem)
    cands = [int(m.group(1))] if m else [int(x) for x in re.findall(r"(?:^|_)(\d{2,3})(?=_)", stem)]
    cands = [c for c in cands if 60 <= c <= 260]
    if cands:
        meta["bpm"] = cands[0]
    keys = []
    for km in _KEY_TOKEN.finditer(stem):
        root, q = km.group(1), (km.group(2) or "")
        if root.endswith("s"):
            root = root[:-1] + "#"
        keys.append(root + (" minor" if q.lower() in ("m", "min", "minor") else (" major" if q else "")))
    if keys:
        meta["key"] = keys[-1] if len(keys) > 1 and keys[-1].endswith(("minor", "major")) else keys[0]
    return meta


def build_inventory(roots: list[Path], out_dir: Path, with_audio_info: bool = True) -> dict:
    items = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in AUDIO_EXT | PRESET_EXT:
                continue
            it = {"path": str(p), "file": p.name, "pack": p.relative_to(root).parts[0] if len(p.relative_to(root).parts) > 1 else root.name,
                  "ext": p.suffix.lower(), "roles": classify(p.relative_to(root)), **parse_meta(p.name)}
            if with_audio_info and p.suffix.lower() in AUDIO_EXT:
                try:
                    import soundfile as sf
                    i = sf.info(str(p))
                    it["duration_sec"] = round(i.duration, 3)
                    it["sample_rate"] = i.samplerate
                except Exception:  # noqa: BLE001
                    it["unreadable"] = True
            items.append(it)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "samples_inventory.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(out_dir / "samples_inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pack", "file", "roles", "key", "bpm", "duration_sec", "path"])
        for it in items:
            w.writerow([it["pack"], it["file"], "|".join(it["roles"]), it.get("key", ""), it.get("bpm", ""),
                        it.get("duration_sec", ""), it["path"]])
    by_role: dict[str, int] = {}
    for it in items:
        for r in it["roles"]:
            by_role[r] = by_role.get(r, 0) + 1
    return {"total": len(items), "by_role": dict(sorted(by_role.items(), key=lambda x: -x[1])),
            "roots": [str(r) for r in roots]}


def suggest(inventory_json: Path, role: str, key: str | None = None, bpm: float | None = None,
            query: str | None = None, limit: int = 8) -> list[dict]:
    items = json.loads(Path(inventory_json).read_text(encoding="utf-8"))
    cands = [it for it in items if role in it["roles"] and not it.get("unreadable")]
    if query:
        q = query.lower()
        cands = [it for it in cands if q in it["path"].lower()]

    def score(it):
        s = 0.0
        if key and it.get("key"):
            s += 2 if it["key"].split()[0].lower() == key.split()[0].lower() else 0
        if bpm and it.get("bpm"):
            s += 1.5 if abs(it["bpm"] - bpm) < 1 else (0.5 if abs(it["bpm"] - bpm) < 5 else -0.5)
        if role in ("kick", "clap", "snare", "impact") and it.get("duration_sec"):
            s += 0.3 if it["duration_sec"] < 2.5 else 0
        return s
    return sorted(cands, key=score, reverse=True)[:limit]
