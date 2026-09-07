"""Locate bundled binaries, models and user data folders.

Two layouts are supported:

  source checkout:   <repo>/.env  <repo>/app  <repo>/tessdata
  release bundle:    <Bundle>/env <Bundle>/app <Bundle>/tessdata

The user models folder overrides bundled models so that updated language
models can be installed without reinstalling the app.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from . import APP_NAME

APP_DIR = Path(os.environ.get("OCRAPP_ROOT") or Path(__file__).resolve().parent.parent)
IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

MODEL_NAMES = ("guj", "hin", "eng", "osd")
TESSDATA_EXTRAS = ("configs", "tessconfigs", "pdf.ttf")


def env_dir() -> Path | None:
    for name in ("env", ".env"):
        p = APP_DIR / name
        if (p / ("python.exe" if IS_WINDOWS else "bin/python")).exists():
            return p
    return None


def env_bin_dirs() -> list[Path]:
    env = env_dir()
    if env is None:
        return []
    if IS_WINDOWS:
        return [env, env / "Library" / "bin", env / "Library" / "usr" / "bin", env / "Scripts"]
    return [env / "bin"]


def bundled_tessdata_dir() -> Path:
    return APP_DIR / "tessdata"


def user_data_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def user_tessdata_dir() -> Path:
    d = user_data_dir() / "tessdata"
    d.mkdir(parents=True, exist_ok=True)
    return d


def user_models_manifest() -> Path:
    return user_data_dir() / "models.json"


def read_user_manifest() -> dict:
    p = user_models_manifest()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def write_user_manifest(data: dict) -> None:
    user_models_manifest().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _same_file(a: Path, b: Path) -> bool:
    try:
        sa, sb = a.stat(), b.stat()
    except OSError:
        return False
    return sa.st_size == sb.st_size and int(sa.st_mtime) == int(sb.st_mtime)


def prepare_tessdata() -> Path:
    """Build the effective tessdata folder and return it.

    Bundled models and Tesseract config files are copied into the user folder
    unless the user folder holds a model the updater installed (recorded in
    models.json). That way updated models win, but a new app release with newer
    bundled models still replaces anything the updater did not install.
    """
    src = bundled_tessdata_dir()
    dst = user_tessdata_dir()
    manifest = read_user_manifest().get("models", {})
    if not src.exists():
        return dst
    for entry in src.iterdir():
        target = dst / entry.name
        if entry.is_dir():
            if not target.exists():
                shutil.copytree(entry, target)
            continue
        stem = entry.stem if entry.suffix == ".traineddata" else None
        if stem and manifest.get(stem, {}).get("source") == "update" and target.exists():
            continue
        if not _same_file(entry, target):
            shutil.copy2(entry, target)
    return dst


def apply_environment() -> dict[str, str]:
    """Make bundled binaries and models visible to OCRmyPDF and Tesseract."""
    env = os.environ
    bins = [str(p) for p in env_bin_dirs() if p.exists()]
    if bins:
        env["PATH"] = os.pathsep.join(bins + [env.get("PATH", "")])
    env["TESSDATA_PREFIX"] = str(prepare_tessdata())
    # Ghostscript is compiled with its build-time prefix; point it at the moved resources.
    gs_lib = ghostscript_lib_dirs()
    if gs_lib and "GS_LIB" not in env:
        env["GS_LIB"] = os.pathsep.join(str(d) for d in gs_lib)
    # OCRmyPDF parallelises across pages; keep Tesseract single-threaded per page.
    env.setdefault("OMP_THREAD_LIMIT", "1")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return dict(env)


def ghostscript_lib_dirs() -> list[Path]:
    env = env_dir()
    if env is None:
        return []
    share = (env / "Library" / "share" if IS_WINDOWS else env / "share") / "ghostscript"
    out: list[Path] = []
    if share.exists():
        for ver in sorted(share.iterdir(), reverse=True):
            for sub in ("Resource/Init", "lib", "Resource/Font", "fonts"):
                d = ver / sub
                if d.exists():
                    out.append(d)
            if out:
                break
    return out


def python_executable() -> str:
    env = env_dir()
    if env is None:
        return sys.executable
    if IS_WINDOWS:
        return str(env / "python.exe")
    return str(env / "bin" / "python")


def versions_file() -> Path:
    return APP_DIR / "versions.json"


def user_config_file() -> Path:
    return user_data_dir() / "config.json"


def downloads_dir() -> Path:
    d = Path.home() / "Downloads"
    return d if d.exists() else Path.home()
