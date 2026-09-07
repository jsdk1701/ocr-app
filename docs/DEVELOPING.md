# Developing OCR App

## Layout

```
app/                 the application (tkinter GUI + OCRmyPDF worker + update logic)
packaging/build.py   builds a relocatable bundle for the current platform
packaging/smoke_test.py   runs the bundle on samples/smoke/*.pdf and checks the text
packaging/launcher/  Mac .app skeleton and the Windows launcher
docs/User-Guide.md   end-user guide; rendered to User-Guide.pdf (committed) and shipped in every zip
environment.yml      the runtime environment, all from conda-forge
.github/workflows/   release.yml (build + smoke test + GitHub Release), auto-update.yml (monthly check)
```

## Run from source

Install [micromamba](https://mamba.org/) (or download the standalone binary into `.tools/bin`), then:

```bash
micromamba create -p ./.env -f environment.yml
./.env/bin/python packaging/build.py --no-zip --skip-pack   # once: downloads models into tessdata/
./.env/bin/python -m app
```

Windows: `.env\python.exe -m app`. The app finds `.env` next to `app/` automatically. Models land in the user data folder (`~/Library/Application Support/OCR App` or `%APPDATA%\OCR App`) on first run.

Run the worker directly for debugging:

```bash
./.env/bin/python -m app.worker in.pdf out.pdf --language guj+hin+eng --deskew --rotate-pages --sidecar out.txt
```

## Build a bundle locally

```bash
./.env/bin/python packaging/build.py --repo YOURNAME/ocr-app
./.env/bin/python packaging/smoke_test.py "build/stage/OCR App/OCR App.app/Contents/Resources"
```

The zip lands in `dist/`. `--skip-pack` reuses the packed environment from a previous run when iterating on `app/`. Windows builds need `pip install pyinstaller` (for the 20-line launcher only).

The bundle is a conda-pack of `environment.yml` with the big unused parts removed (`PRUNE_DIRS` in `build.py`), plus `app/`, `tessdata/` (four `tessdata_best` models and Tesseract's config files), `versions.json`, the guide, and a launcher that sets `OCRAPP_ROOT`, `PYTHONPATH`, `TESSDATA_PREFIX` and `GS_LIB`.

## Cut a release

1. Bump `__version__` in `app/__init__.py` and commit.
2. `git tag v0.2.0 && git push --tags`.
3. Actions builds Windows, Mac arm64 and Mac x86_64, smoke-tests each, and publishes a GitHub Release with the three zips and `versions.json`.

Or use *Actions → Build and release → Run workflow* with a version number; that path creates the tag for you.

## Automatic updates

`auto-update.yml` runs monthly. It asks conda-forge for the newest OCRmyPDF, Tesseract and Ghostscript, asks GitHub for the current model checksums, and compares them with `versions.json` of the latest release. If anything changed it triggers `release.yml` with the next patch version. A failing smoke test opens an issue and publishes nothing.

The app reads `versions.json` from its bundle and `repo` from it to know where to look. `build.py --repo` (or `GITHUB_REPOSITORY` in CI) fills that in; a bundle built without it has update checks disabled.

To pin a component (for example if a Tesseract release misbehaves), pin it in `environment.yml` (`tesseract=5.5.*`). The auto-update job then stops seeing it as "newer".

## Regenerate the user guide

`docs/User-Guide.pdf` is committed. After editing `docs/User-Guide.md`, on a Mac with Chrome:

```bash
./.env/bin/python packaging/make_guide.py
```

## Samples

`samples/smoke/*.pdf` are synthetic scans rendered from HTML (`packaging/make_samples.py`, macOS + Chrome). They are used by the smoke test; expected words live in `packaging/smoke_test.py`.
