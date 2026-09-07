#!/usr/bin/env python
"""Build a relocatable OCR App bundle for the current platform.

    python packaging/build.py [--prefix PATH] [--version X.Y.Z] [--repo OWNER/REPO] [--out dist]

Steps: download language models → conda-pack the environment → prune → copy app,
models and docs → write versions.json → add the platform launcher → zip.
Run it with the environment's own python (it needs conda-pack and Pillow).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import __version__ as DEFAULT_VERSION, APP_NAME  # noqa: E402

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
MODEL_URLS = {
    "guj": "https://github.com/tesseract-ocr/tessdata_best/raw/main/guj.traineddata",
    "hin": "https://github.com/tesseract-ocr/tessdata_best/raw/main/hin.traineddata",
    "eng": "https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata",
    "osd": "https://github.com/tesseract-ocr/tessdata/raw/main/osd.traineddata",
}
PRUNE_DIRS = ["share/tessdata", "include", "share/doc", "share/man", "share/gir-1.0", "share/locale",
              "share/info", "share/gtk-doc", "conda-meta", "pkgs", "lib/python3.12/test",
              "lib/python3.12/idlelib", "lib/python3.12/site-packages/pip",
              "lib/python3.12/site-packages/setuptools", "lib/python3.12/site-packages/conda_pack",
              "lib/python3.12/site-packages/wheel", "lib/cmake", "lib/pkgconfig", "man", "ssl/misc",
              "Library/share/tessdata", "Library/include", "Library/share/doc", "Library/share/man",
              "Library/share/gir-1.0", "Library/share/locale", "Library/lib/cmake", "Library/lib/pkgconfig",
              "Lib/test", "Lib/idlelib", "Lib/site-packages/pip", "Lib/site-packages/setuptools",
              "Lib/site-packages/conda_pack", "Lib/site-packages/wheel", "Lib/tkinter/test"]


def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    log(" ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def platform_key() -> str:
    if IS_WIN:
        return "windows"
    if IS_MAC:
        return "macos-arm64" if platform.machine() == "arm64" else "macos-x86_64"
    return f"linux-{platform.machine()}"


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def download_models(dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    info = {}
    for name, url in MODEL_URLS.items():
        f = dest / f"{name}.traineddata"
        if not f.exists():
            log(f"downloading {name} model")
            urllib.request.urlretrieve(url, f)
        info[name] = {"sha": git_blob_sha(f), "size": f.stat().st_size, "url": url}
    return info


def env_python(prefix: Path) -> Path:
    return prefix / ("python.exe" if IS_WIN else "bin/python")


def pack_env(prefix: Path, dest_env: Path, work: Path) -> None:
    tar = work / "env.tar"
    if tar.exists():
        tar.unlink()
    run([env_python(prefix), "-c", "import sys; from conda_pack.cli import main; sys.exit(main())",
         "-p", prefix, "-o", tar, "--format", "tar", "--ignore-missing-files", "--n-threads", "-1", "--quiet"])
    if dest_env.exists():
        shutil.rmtree(dest_env)
    dest_env.mkdir(parents=True)
    log("extracting packed environment")
    with tarfile.open(tar) as t:
        t.extractall(dest_env, filter="fully_trusted")
    tar.unlink()


def prune(env: Path) -> None:
    for rel in PRUNE_DIRS:
        p = env / rel
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    for pyc in env.rglob("__pycache__"):
        shutil.rmtree(pyc, ignore_errors=True)
    for a in list(env.glob("lib/*.a")) + list(env.glob("Library/lib/*.lib")):
        a.unlink(missing_ok=True)


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))


def copy_tessdata(prefix: Path, models_dir: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for f in models_dir.glob("*.traineddata"):
        shutil.copy2(f, dest / f.name)
    share = (prefix / "Library" / "share" if IS_WIN else prefix / "share") / "tessdata"
    for extra in ("configs", "tessconfigs"):
        if (share / extra).exists():
            copy_tree(share / extra, dest / extra)
    if (share / "pdf.ttf").exists():
        shutil.copy2(share / "pdf.ttf", dest / "pdf.ttf")


def tool_version(cmd: list[str], pattern: str) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        text = out.stdout + out.stderr
        m = re.search(pattern, text)
        return m.group(1) if m else text.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "unknown"


def write_versions(bundle: Path, prefix: Path, version: str, repo: str, models: dict) -> dict:
    bins = prefix / ("Library/bin" if IS_WIN else "bin")
    tess = bins / ("tesseract.exe" if IS_WIN else "tesseract")
    gs = bins / ("gswin64c.exe" if IS_WIN else "gs")
    data = {
        "app": version,
        "repo": repo,
        "platform": platform_key(),
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "ocrmypdf": tool_version([str(env_python(prefix)), "-c", "import ocrmypdf;print(ocrmypdf.__version__)"], r"([\d.]+)"),
        "tesseract": tool_version([str(tess), "--version"], r"tesseract\s+v?([\d.]+)"),
        "ghostscript": tool_version([str(gs), "--version"], r"([\d.]+)"),
        "python": tool_version([str(env_python(prefix)), "--version"], r"([\d.]+)"),
        "models": {k: {"sha": v["sha"], "size": v["size"]} for k, v in models.items()},
    }
    (bundle / "versions.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def stamp_version(app_dir: Path, version: str) -> None:
    init = app_dir / "__init__.py"
    src = init.read_text(encoding="utf-8")
    init.write_text(re.sub(r'__version__ = "[^"]*"', f'__version__ = "{version}"', src), encoding="utf-8")


def make_ico(png: Path, ico: Path) -> None:
    from PIL import Image
    Image.open(png).save(ico, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def make_icns(png: Path, icns: Path, work: Path) -> None:
    from PIL import Image
    iconset = work / "icon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    im = Image.open(png)
    for size in (16, 32, 128, 256, 512):
        im.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
        im.resize((size * 2, size * 2), Image.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
    run(["iconutil", "-c", "icns", iconset, "-o", icns])


def build_mac(stage: Path, res: Path, version: str, work: Path) -> Path:
    app = stage / f"{APP_NAME}.app"
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    shutil.move(str(res), str(contents / "Resources"))
    res = contents / "Resources"
    launcher = contents / "MacOS" / "launcher"
    shutil.copy2(ROOT / "packaging/launcher/mac/launcher.sh", launcher)
    launcher.chmod(0o755)
    plist = (ROOT / "packaging/launcher/mac/Info.plist").read_text().replace("__VERSION__", version)
    (contents / "Info.plist").write_text(plist)
    make_icns(ROOT / "packaging/icon.png", res / "icon.icns", work)
    for doc in ("User-Guide.pdf", "README.txt"):
        if (res / doc).exists():
            shutil.copy2(res / doc, stage / doc)
    return app


def build_windows(stage: Path, res: Path, version: str, work: Path) -> Path:
    folder = stage
    for child in list(res.iterdir()):
        shutil.move(str(child), str(folder / child.name))
    res.rmdir()
    ico = work / "icon.ico"
    make_ico(ROOT / "packaging/icon.png", ico)
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--noconsole",
         "--name", APP_NAME, "--icon", ico, "--distpath", folder, "--workpath", work / "pyi",
         "--specpath", work, ROOT / "packaging/launcher/windows/launcher.py"])
    return folder


def zip_stage(stage: Path, out: Path) -> None:
    if out.exists():
        out.unlink()
    if IS_MAC:
        run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", stage, out])
    else:
        shutil.make_archive(str(out.with_suffix("")), "zip", root_dir=stage.parent, base_dir=stage.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", type=Path, default=ROOT / ".env")
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "OWNER/ocr-app"))
    ap.add_argument("--out", type=Path, default=ROOT / "dist")
    ap.add_argument("--skip-pack", action="store_true", help="reuse build/bundle/env from a previous run")
    ap.add_argument("--no-zip", action="store_true")
    args = ap.parse_args()

    prefix = args.prefix.resolve()
    work = ROOT / "build"
    bundle = work / "bundle"
    key = platform_key()
    log(f"platform {key}, version {args.version}, prefix {prefix}")

    models = download_models(ROOT / "tessdata")
    if not args.skip_pack or not (bundle / "env").exists():
        pack_env(prefix, bundle / "env", work)
        prune(bundle / "env")
    for rel in ("app", "tessdata", "versions.json", "User-Guide.pdf", "README.txt"):
        p = bundle / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    copy_tree(ROOT / "app", bundle / "app")
    stamp_version(bundle / "app", args.version)
    copy_tessdata(prefix, ROOT / "tessdata", bundle / "tessdata")
    if (ROOT / "docs/User-Guide.pdf").exists():
        shutil.copy2(ROOT / "docs/User-Guide.pdf", bundle / "User-Guide.pdf")
    shutil.copy2(ROOT / "packaging/README.txt", bundle / "README.txt")
    info = write_versions(bundle, prefix, args.version, args.repo, models)
    log(f"components: ocrmypdf {info['ocrmypdf']}, tesseract {info['tesseract']}, ghostscript {info['ghostscript']}")

    stage = work / "stage" / APP_NAME  # the folder name people see after unzipping
    if stage.parent.exists():
        shutil.rmtree(stage.parent)
    stage.mkdir(parents=True)
    staged = bundle.parent / "staged"
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(bundle, staged, symlinks=True)
    if IS_MAC:
        product = build_mac(stage, staged, args.version, work)
    elif IS_WIN:
        product = build_windows(stage, staged, args.version, work)
    else:
        product = stage
        for child in list(staged.iterdir()):
            shutil.move(str(child), str(stage / child.name))
    log(f"built {product}")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "versions.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    if not args.no_zip:
        zip_path = args.out / f"OCR-App-{args.version}-{key}.zip"
        zip_stage(stage, zip_path)
        log(f"wrote {zip_path} ({zip_path.stat().st_size // (1 << 20)} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
