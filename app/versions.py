"""Report what is installed: app version, engine versions, model checksums."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from . import __version__
from . import paths


def git_blob_sha(path: Path) -> str:
    """SHA-1 the way git names blobs, so it matches GitHub's contents API."""
    data = path.read_bytes()
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def bundled_versions() -> dict:
    p = paths.versions_file()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"app": __version__}


def _run(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (out.stdout or out.stderr or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def live_versions() -> dict:
    paths.apply_environment()
    tess = _run([shutil.which("tesseract") or "tesseract", "--version"])
    gs_name = shutil.which("gs") or shutil.which("gswin64c") or "gs"
    gs = _run([gs_name, "--version"])
    ocrmypdf = _run([paths.python_executable(), "-c", "import ocrmypdf; print(ocrmypdf.__version__)"])
    m = re.search(r"tesseract\s+v?([\d.]+)", tess)
    return {
        "app": __version__,
        "ocrmypdf": ocrmypdf or "unknown",
        "tesseract": m.group(1) if m else (tess.splitlines()[0] if tess else "unknown"),
        "ghostscript": gs or "unknown",
        "models": installed_model_shas(),
    }


def installed_model_shas() -> dict:
    d = paths.prepare_tessdata()
    manifest = paths.read_user_manifest().get("models", {})
    out = {}
    for name in paths.MODEL_NAMES:
        f = d / f"{name}.traineddata"
        if f.exists():
            out[name] = {"sha": git_blob_sha(f), "size": f.stat().st_size,
                         "source": manifest.get(name, {}).get("source", "bundled")}
    return out
