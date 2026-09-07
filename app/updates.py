"""Update checks: new app releases on GitHub, newer Tesseract language models.

Nothing here runs automatically except a once-a-day release check that the GUI
starts in a background thread. All functions raise ``UpdateError`` with a plain
message on failure; callers decide whether to show it.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__
from . import paths
from .versions import bundled_versions, git_blob_sha

GITHUB_API = "https://api.github.com"
MODEL_REPOS = {"guj": "tesseract-ocr/tessdata_best", "hin": "tesseract-ocr/tessdata_best",
               "eng": "tesseract-ocr/tessdata_best", "osd": "tesseract-ocr/tessdata"}
USER_AGENT = f"OCR-App/{__version__}"
ProgressCb = Callable[[int, int | None], None]


class UpdateError(Exception):
    pass


def repo() -> str | None:
    r = os.environ.get("OCRAPP_REPO") or bundled_versions().get("repo")
    return r if r and "/" in r and "OWNER" not in r else None


def _get_json(url: str, timeout: float = 15) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise UpdateError(f"Could not reach GitHub ({exc.__class__.__name__}). Check your internet connection.") from exc


def _download(url: str, dest: Path, progress: ProgressCb | None = None, timeout: float = 60) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
            total = r.headers.get("Content-Length")
            total = int(total) if total else None
            done = 0
            while True:
                chunk = r.read(1 << 18)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except Exception as exc:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise UpdateError(f"Download failed ({exc.__class__.__name__}). Check your internet connection.") from exc


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4]) or (0,)


def platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos-arm64" if platform.machine() == "arm64" else "macos-x86_64"
    return "linux"


@dataclass
class ReleaseInfo:
    version: str
    tag: str
    url: str
    notes: str
    asset_name: str | None
    asset_url: str | None

    @property
    def is_newer(self) -> bool:
        return version_tuple(self.version) > version_tuple(__version__)


def check_release() -> ReleaseInfo | None:
    r = repo()
    if not r:
        raise UpdateError("Update checks are not configured for this build.")
    data = _get_json(f"{GITHUB_API}/repos/{r}/releases/latest")
    tag = data.get("tag_name", "")
    key = platform_key()
    asset = next((a for a in data.get("assets", []) if key in a.get("name", "")), None)
    return ReleaseInfo(version=tag.lstrip("v"), tag=tag, url=data.get("html_url", ""),
                       notes=data.get("body", "") or "",
                       asset_name=asset["name"] if asset else None,
                       asset_url=asset["browser_download_url"] if asset else None)


def download_release(rel: ReleaseInfo, progress: ProgressCb | None = None) -> Path:
    if not rel.asset_url or not rel.asset_name:
        raise UpdateError("No download is available for this computer yet. Open the release page instead.")
    dest = paths.downloads_dir() / rel.asset_name
    tmp = dest.with_suffix(dest.suffix + ".part")
    _download(rel.asset_url, tmp, progress, timeout=120)
    tmp.replace(dest)
    return dest


@dataclass
class ModelUpdate:
    name: str
    new_sha: str
    size: int
    url: str
    current_sha: str | None


def check_models() -> list[ModelUpdate]:
    """Compare installed model checksums with the latest files on GitHub."""
    tessdata = paths.prepare_tessdata()
    listings: dict[str, dict] = {}
    for name, r in MODEL_REPOS.items():
        if r not in listings:
            items = _get_json(f"{GITHUB_API}/repos/{r}/contents/")
            listings[r] = {i["name"]: i for i in items if isinstance(i, dict)}
    updates = []
    for name, r in MODEL_REPOS.items():
        item = listings[r].get(f"{name}.traineddata")
        if not item:
            continue
        local = tessdata / f"{name}.traineddata"
        current = git_blob_sha(local) if local.exists() else None
        if current != item["sha"]:
            updates.append(ModelUpdate(name=name, new_sha=item["sha"], size=int(item["size"]),
                                       url=item["download_url"], current_sha=current))
    return updates


def install_model(u: ModelUpdate, progress: ProgressCb | None = None) -> Path:
    """Download, verify, back up the old model, and record the install."""
    d = paths.user_tessdata_dir()
    target = d / f"{u.name}.traineddata"
    tmp = Path(tempfile.mkstemp(prefix=f"{u.name}-", suffix=".part", dir=d)[1])
    try:
        _download(u.url, tmp, progress, timeout=300)
        size = tmp.stat().st_size
        if size != u.size:
            raise UpdateError(f"Downloaded {u.name} model is incomplete ({size} of {u.size} bytes).")
        if git_blob_sha(tmp) != u.new_sha:
            raise UpdateError(f"Downloaded {u.name} model failed verification. Nothing was changed.")
        if target.exists():
            shutil.copy2(target, target.with_suffix(".traineddata.bak"))
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    manifest = paths.read_user_manifest()
    manifest.setdefault("models", {})[u.name] = {"sha": u.new_sha, "size": u.size,
                                                 "source": "update", "installed": time.time()}
    paths.write_user_manifest(manifest)
    return target


def rollback_model(name: str) -> bool:
    d = paths.user_tessdata_dir()
    bak = d / f"{name}.traineddata.bak"
    if not bak.exists():
        return False
    bak.replace(d / f"{name}.traineddata")
    manifest = paths.read_user_manifest()
    manifest.get("models", {}).pop(name, None)
    paths.write_user_manifest(manifest)
    return True


def restore_bundled_models() -> list[str]:
    """Forget all updater-installed models so bundled ones are used again."""
    manifest = paths.read_user_manifest()
    names = list(manifest.get("models", {}).keys())
    manifest["models"] = {}
    paths.write_user_manifest(manifest)
    for n in names:
        (paths.user_tessdata_dir() / f"{n}.traineddata").unlink(missing_ok=True)
    paths.prepare_tessdata()
    return names
