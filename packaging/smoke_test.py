#!/usr/bin/env python
"""Run the built bundle on the sample scans and assert known words come out.

    python packaging/smoke_test.py <bundle-root>

<bundle-root> is the folder containing env/, app/ and tessdata/:
  macOS:   "dist/stage/OCR App.app/Contents/Resources"   Windows: "dist/stage/OCR App"
Uses a temporary home folder so it behaves like a fresh user account.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IS_WIN = sys.platform.startswith("win")
CASES = {
    "guj.pdf": ("guj+eng", ["ગુજરાત", "ગાંધીનગર", "સાબરમતી"]),
    "hin.pdf": ("hin+eng", ["भारत", "हिमालय", "राजधानी"]),
    "eng.pdf": ("eng", ["quick brown fox", "searchable text"]),
    "eng-rotated.pdf": ("eng", ["quick brown fox"]),
    "mixed.pdf": ("guj+hin+eng", ["ગાંધીનગર", "quick brown fox"]),
}


def main(bundle: Path) -> int:
    py = bundle / ("env/python.exe" if IS_WIN else "env/bin/python")
    assert py.exists(), f"missing {py}"
    failures = []
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ, OCRAPP_ROOT=str(bundle), PYTHONPATH=str(bundle), PYTHONIOENCODING="utf-8",
                   PYTHONDONTWRITEBYTECODE="1")
        if IS_WIN:
            env["APPDATA"] = td
        else:
            env["HOME"] = td
            env["PATH"] = "/usr/bin:/bin"  # nothing from the developer machine
        for name, (lang, words) in CASES.items():
            src = ROOT / "samples/smoke" / name
            out = Path(td) / f"{src.stem}-ocr.pdf"
            side = Path(td) / f"{src.stem}.txt"
            t0 = time.time()
            p = subprocess.run([str(py), "-m", "app.worker", str(src), str(out), "--language", lang,
                                "--deskew", "--rotate-pages", "--sidecar", str(side)],
                               cwd=str(bundle), env=env, capture_output=True, text=True, encoding="utf-8")
            events = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
            errors = [e for e in events if e.get("event") == "error"]
            text = side.read_text(encoding="utf-8") if side.exists() else ""
            missing = [w for w in words if w not in text]
            layer_ok = False
            if out.exists():
                q = subprocess.run([str(py), "-c", "import sys;from pdfminer.high_level import extract_text;"
                                    "print(extract_text(sys.argv[1]))", str(out)],
                                   capture_output=True, text=True, encoding="utf-8", env=env)
                layer_ok = all(w in q.stdout for w in words)
            ok = p.returncode == 0 and out.exists() and not errors and not missing and layer_ok
            print(f"{'PASS' if ok else 'FAIL'} {name:16s} {lang:12s} {time.time() - t0:5.1f}s"
                  f"{'' if ok else f'  rc={p.returncode} errors={errors} missing={missing} layer_ok={layer_ok}'}")
            if not ok:
                failures.append(name)
                print(p.stderr[-2000:])
    print("SMOKE TEST", "FAILED" if failures else "PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).resolve()))
