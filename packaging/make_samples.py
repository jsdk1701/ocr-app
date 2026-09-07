"""Generate image-only sample PDFs (Gujarati, Hindi, English, mixed, rotated).

Renders HTML with headless Chrome so Indic scripts are shaped correctly, then
rasterises to 300 DPI with Ghostscript and rebuilds image-only PDFs so they
behave like real scans. Run from the repo root with the conda env python.
"""
from __future__ import annotations
import shutil, subprocess, sys, tempfile
from pathlib import Path
import img2pdf
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples" / "smoke"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
GS = str(ROOT / ".env" / "bin" / "gs")

GUJ = [
 "ભારત મારો દેશ છે. ગુજરાત રાજ્યની રાજધાની ગાંધીનગર છે.",
 "અમદાવાદ સાબરમતી નદીના કિનારે વસેલું શહેર છે. અહીં ઘણા ઐતિહાસિક સ્થળો આવેલાં છે.",
 "શિક્ષણ એ સમાજના વિકાસનો પાયો છે. પુસ્તકો જ્ઞાનનો ભંડાર છે અને વાંચન મનને સમૃદ્ધ બનાવે છે.",
 "સ્વામિનારાયણ સંપ્રદાયના મંદિરો ગુજરાતમાં અનેક સ્થળોએ આવેલાં છે.",
]
HIN = [
 "भारत मेरा देश है। हिन्दी भारत की राजभाषा है।",
 "गंगा नदी हिमालय से निकलती है और बंगाल की खाड़ी में मिलती है।",
 "शिक्षा समाज के विकास की नींव है। पुस्तकें ज्ञान का भंडार हैं।",
 "दिल्ली भारत की राजधानी है और यहाँ अनेक ऐतिहासिक स्मारक हैं।",
]
ENG = [
 "The quick brown fox jumps over the lazy dog.",
 "Optical character recognition converts scanned pages into searchable text.",
 "Education is the foundation of society. Books are a treasury of knowledge.",
 "This sample page checks that English text is recognised correctly.",
]

def html(title, paras, font):
    body = "".join(f"<p>{p}</p>" for p in paras * 3)
    return f"""<!doctype html><meta charset=utf-8><style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: {font}; font-size: 14pt; line-height: 1.7; }}
    h1 {{ font-size: 22pt; margin-bottom: 8mm; }}
    p {{ margin: 0 0 6mm 0; text-align: justify; }}
    </style><h1>{title}</h1>{body}"""

PAGES = {
 "guj":   html("ગુજરાતી નમૂનો", GUJ, "'Gujarati MT', 'Kohinoor Gujarati'"),
 "hin":   html("हिन्दी नमूना", HIN, "'Devanagari MT', 'Kohinoor Devanagari'"),
 "eng":   html("English sample", ENG, "Georgia, 'Times New Roman'"),
 "mixed": html("Mixed sample / મિશ્ર નમૂનો / मिश्रित नमूना",
               [GUJ[0], HIN[0], ENG[0], GUJ[2], HIN[2], ENG[2]],
               "'Gujarati MT', 'Devanagari MT', Georgia"),
}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for name, doc in PAGES.items():
            (td / f"{name}.html").write_text(doc, encoding="utf-8")
            pdf = td / f"{name}.pdf"
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={pdf}", f"file://{td}/{name}.html"],
                           check=True, capture_output=True)
            png = td / f"{name}-%d.png"
            subprocess.run([GS, "-q", "-sDEVICE=pnggray", "-r300", "-o", str(png), str(pdf)], check=True)
            pngs = sorted(td.glob(f"{name}-*.png"))
            (OUT / f"{name}.pdf").write_bytes(img2pdf.convert([str(p) for p in pngs], dpi=300))
            if name == "eng":
                rot = td / "eng-rot.png"
                Image.open(pngs[0]).rotate(90, expand=True).save(rot)
                (OUT / "eng-rotated.pdf").write_bytes(img2pdf.convert([str(rot)], dpi=300))
            print("wrote", name, len(pngs), "page(s)")

if __name__ == "__main__":
    sys.exit(main())
