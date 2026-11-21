"""Stem separation with Demucs (htdemucs), plus verification and grid alignment."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from .project import HSPError

STEMS4 = ["vocals", "drums", "bass", "other"]
MODELS = {"fast": "htdemucs", "high": "htdemucs_ft", "6stem": "htdemucs_6s"}


def separate(audio: Path, out_dir: Path, quality: str = "fast", device: str | None = None) -> list[Path]:
    model = MODELS.get(quality, quality)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, "-m", "demucs", "-n", model, "-o", tmp, "--float32"]
        if device:
            cmd += ["-d", device]
        cmd.append(str(audio))
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout)[-1500:]
            hint = ""
            if "Could not" in tail or "urlopen" in tail or "HTTP" in tail:
                hint = "\nTips: Demucs laster ned modellvekter første gang (~80 MB). Sjekk internett."
            if "ffmpeg" in tail.lower() or "torchaudio" in tail.lower():
                hint += "\nTips: konverter til WAV først, eller installer ffmpeg."
            raise HSPError(f"Demucs feilet ({model}).{hint}\n{tail}")
        found = list(Path(tmp).rglob("*.wav"))
        if not found:
            raise HSPError("Demucs kjørte, men produserte ingen WAV-filer.")
        outs = []
        for f in found:
            dest = out_dir / f"{f.stem}.wav"
            shutil.move(str(f), dest)
            outs.append(dest)
    return sorted(outs)


def verify_stem(path: Path, expected_duration: float | None = None) -> dict:
    import soundfile as sf
    info = sf.info(str(path))
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    rms = float(np.sqrt(np.mean(data ** 2))) if data.size else 0.0
    res = {"file": path.name, "sample_rate": sr, "channels": info.channels,
           "duration_sec": round(info.duration, 3), "peak_dbfs": round(20 * np.log10(peak + 1e-12), 1),
           "rms_dbfs": round(20 * np.log10(rms + 1e-12), 1), "ok": True, "warnings": []}
    if peak < 10 ** (-35 / 20):
        res["warnings"].append("Stemmen er (nesten) stille — instrumentet finnes kanskje ikke i låten.")
    if peak >= 0.999:
        res["warnings"].append("Topper ved 0 dBFS — mulig clipping. Senk volumet i FL før prosessering.")
    if expected_duration and abs(info.duration - expected_duration) > 0.1:
        res["ok"] = False
        res["warnings"].append(f"Lengde {info.duration:.2f}s avviker fra kilden {expected_duration:.2f}s.")
    if not np.all(np.isfinite(data)):
        res["ok"] = False
        res["warnings"].append("Filen inneholder NaN/Inf — korrupt.")
    return res


def align_to_grid(src: Path, dest: Path, pad_sec: float) -> Path:
    """Prepend silence so the song's bar lines land on FL's bar lines (24-bit WAV)."""
    import soundfile as sf
    data, sr = sf.read(str(src), dtype="float32", always_2d=True)
    pad = np.zeros((int(round(pad_sec * sr)), data.shape[1]), dtype=np.float32)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), np.vstack([pad, data]), sr, subtype="PCM_24")
    return dest


def stretch_to_bpm(src: Path, dest: Path, src_bpm: float, dst_bpm: float, semitones: float = 0.0) -> Path:
    """High-quality time-stretch (Rubber Band via Spotify Pedalboard)."""
    try:
        from pedalboard import time_stretch
    except ImportError as e:
        raise HSPError("Pedalboard mangler: pip install pedalboard") from e
    import soundfile as sf
    data, sr = sf.read(str(src), dtype="float32", always_2d=True)
    out = time_stretch(data.T, sr, stretch_factor=dst_bpm / src_bpm, pitch_shift_in_semitones=semitones,
                       high_quality=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), out.T, sr, subtype="PCM_24")
    return dest
