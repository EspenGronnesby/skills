"""Environment check: Python, libraries, models, ffmpeg, FL Studio install + user data folders."""
from __future__ import annotations

import importlib
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


def _ver(mod: str):
    try:
        m = importlib.import_module(mod)
        return getattr(m, "__version__", "ok")
    except Exception as e:  # noqa: BLE001
        return f"MANGLER ({type(e).__name__})"


def find_fl_studio() -> list[dict]:
    found = []
    sysname = platform.system()
    if sysname == "Darwin":
        for base in (Path("/Applications"), Path.home() / "Applications"):
            for app in base.glob("FL Studio*.app"):
                info = {"path": str(app)}
                pl = app / "Contents" / "Info.plist"
                if pl.exists():
                    try:
                        d = plistlib.loads(pl.read_bytes())
                        info["version"] = d.get("CFBundleShortVersionString") or d.get("CFBundleVersion")
                    except Exception:  # noqa: BLE001
                        pass
                found.append(info)
    elif sysname == "Windows":
        for base in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Image-Line",
                     Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Image-Line"):
            for d in base.glob("FL Studio*"):
                exe = next((p for p in (d / "FL64.exe", d / "FL.exe") if p.exists()), None)
                info = {"path": str(d), "exe": str(exe) if exe else None}
                if exe:
                    try:
                        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                              f"(Get-Item '{exe}').VersionInfo.ProductVersion"],
                                             capture_output=True, text=True, timeout=15)
                        info["version"] = out.stdout.strip() or None
                    except Exception:  # noqa: BLE001
                        pass
                found.append(info)
    return found


def fl_user_data() -> dict:
    """FL Studio user data folder (where controller scripts and user templates live)."""
    cands = [Path.home() / "Documents" / "Image-Line" / "FL Studio"]
    res = {}
    for c in cands:
        if c.exists():
            res["user_data"] = str(c)
            hw = c / "Settings" / "Hardware"
            res["hardware_scripts_dir"] = str(hw) if hw.exists() else f"{hw} (finnes ikke ennå)"
            res["scripts_installed"] = sorted(p.name for p in hw.iterdir() if p.is_dir()) if hw.exists() else []
            pk = c.parent.parent / "Image-Line" / "Data" / "FL Studio" / "Packs"
    return res


def run() -> dict:
    r = {
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": sys.version.split()[0],
        "python_ok": sys.version_info >= (3, 10),
        "ffmpeg": shutil.which("ffmpeg"),
        "libraries": {m: _ver(m) for m in ("numpy", "librosa", "soundfile", "mido", "pretty_midi",
                                            "basic_pitch", "onnxruntime", "torch", "demucs", "pedalboard")},
        "fl_studio": find_fl_studio(),
        "fl_user": fl_user_data(),
    }
    try:
        from basic_pitch import FilenameSuffix, build_icassp_2022_model_path
        p = build_icassp_2022_model_path(FilenameSuffix.onnx)
        r["basic_pitch_onnx_model"] = str(p) if Path(p).exists() else "MANGLER"
    except Exception as e:  # noqa: BLE001
        r["basic_pitch_onnx_model"] = f"MANGLER ({e})"
    hub = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
    r["demucs_models_cached"] = sorted(p.name for p in hub.glob("*.th")) if hub.exists() else []
    problems = []
    if not r["python_ok"]:
        problems.append("Python 3.10+ kreves.")
    if not r["ffmpeg"]:
        problems.append("ffmpeg mangler (trengs for MP3). Mac: brew install ffmpeg | Win: winget install Gyan.FFmpeg")
    for m, v in r["libraries"].items():
        if str(v).startswith("MANGLER"):
            problems.append(f"{m} mangler — kjør setup-skriptet.")
    if not r["fl_studio"]:
        problems.append("Fant ikke FL Studio i standard installasjonsmappe.")
    r["problems"] = problems
    r["ok"] = not problems
    return r
