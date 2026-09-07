"""Render docs/User-Guide.md to docs/User-Guide.pdf with headless Chrome (macOS)."""
from __future__ import annotations
import subprocess, sys, tempfile
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CSS = """
@page { size: A4; margin: 18mm; }
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #222; }
h1 { font-size: 22pt; border-bottom: 2px solid #1f4e79; padding-bottom: 4px; color: #1f4e79; }
h2 { font-size: 15pt; color: #1f4e79; margin-top: 18pt; }
h3 { font-size: 12pt; margin-top: 12pt; }
code { background: #f2f2f2; padding: 1px 4px; border-radius: 3px; font-size: 10pt; }
pre { background: #f2f2f2; padding: 8px; border-radius: 4px; font-size: 9.5pt; white-space: pre-wrap; }
li { margin: 3px 0; }
"""

def main() -> int:
    md = (ROOT / "docs/User-Guide.md").read_text(encoding="utf-8")
    html = f"<!doctype html><meta charset=utf-8><title>OCR App User Guide</title><style>{CSS}</style>" \
           + markdown.markdown(md, extensions=["fenced_code", "tables"])
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "guide.html"
        src.write_text(html, encoding="utf-8")
        out = ROOT / "docs/User-Guide.pdf"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", src.as_uri()], check=True, capture_output=True)
        print("wrote", out, out.stat().st_size // 1024, "KB")
    return 0

if __name__ == "__main__":
    sys.exit(main())
