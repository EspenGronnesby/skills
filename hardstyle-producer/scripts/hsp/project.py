"""Standard song-project folder, manifest and cache handling."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
from pathlib import Path

SUBDIRS = [
    "source", "stems", "analysis", "midi/original", "midi/cleaned", "midi/generated",
    "samples", "arrangement", "fl-studio", "exports", "backups",
]


def _jsonable(o):
    """numpy scalars/arrays -> plain Python for JSON."""
    if hasattr(o, "tolist"):
        return o.tolist()
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(type(o))


class HSPError(RuntimeError):
    """Error with a user-facing message (printed without traceback)."""


def file_hash(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()[:16]


class Project:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.manifest_path = self.root / "project.json"

    # ---------- creation ----------
    @classmethod
    def create(cls, root: Path, audio: Path, request: str = "") -> "Project":
        audio = Path(audio)
        if not audio.exists():
            raise HSPError(f"Fant ikke lydfilen: {audio}")
        if audio.suffix.lower() not in (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aiff", ".aif"):
            raise HSPError(f"Ukjent lydformat: {audio.suffix}. Bruk WAV eller MP3.")
        p = cls(root)
        for d in SUBDIRS:
            (p.root / d).mkdir(parents=True, exist_ok=True)
        dest = p.root / "source" / audio.name
        if not dest.exists():
            shutil.copy2(audio, dest)  # never move/modify the user's original
        m = p.load() if p.manifest_path.exists() else {}
        m.update({
            "name": p.root.name,
            "source": f"source/{audio.name}",
            "source_hash": file_hash(dest),
            "request": request or m.get("request", ""),
            "created": m.get("created", _dt.datetime.now().isoformat(timespec="seconds")),
            "steps": m.get("steps", {}),
            "log": m.get("log", []),
        })
        p.save(m)
        p.log("init", f"Prosjekt opprettet fra {audio.name}")
        return p

    @classmethod
    def open(cls, root: Path) -> "Project":
        p = cls(root)
        if not p.manifest_path.exists():
            raise HSPError(f"{root} er ikke et hardstyle-producer-prosjekt (mangler project.json). Kjør 'init' først.")
        return p

    # ---------- manifest ----------
    def load(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def save(self, m: dict) -> None:
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.manifest_path)

    def log(self, step: str, msg: str, ok: bool = True) -> None:
        m = self.load()
        m.setdefault("log", []).append({
            "time": _dt.datetime.now().isoformat(timespec="seconds"), "step": step, "ok": ok, "msg": msg,
        })
        self.save(m)

    def mark_done(self, step: str, inputs_key: str, outputs: list[str]) -> None:
        m = self.load()
        m.setdefault("steps", {})[step] = {"key": inputs_key, "outputs": outputs,
                                           "time": _dt.datetime.now().isoformat(timespec="seconds")}
        self.save(m)

    def is_done(self, step: str, inputs_key: str) -> bool:
        s = self.load().get("steps", {}).get(step)
        if not s or s.get("key") != inputs_key:
            return False
        return all((self.root / o).exists() for o in s.get("outputs", []))

    # ---------- paths ----------
    @property
    def source(self) -> Path:
        return self.root / self.load()["source"]

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def read_json(self, rel: str) -> dict:
        p = self.root / rel
        if not p.exists():
            raise HSPError(f"Mangler {rel}. Kjør forrige steg først.")
        return json.loads(p.read_text(encoding="utf-8"))

    def write_json(self, rel: str, data) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            self.backup(p)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=_jsonable), encoding="utf-8")
        return p

    def backup(self, p: Path) -> Path | None:
        """Copy an existing output to backups/ before it is regenerated."""
        if not p.exists():
            return None
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        rel = p.relative_to(self.root)
        dest = self.root / "backups" / stamp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        return dest
