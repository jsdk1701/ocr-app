"""Run OCRmyPDF on one file and report progress as JSON lines on stdout.

Started by the GUI as a subprocess so OCRmyPDF's multiprocessing works and the
window never freezes. Can also be used from a terminal:

    python -m app.worker input.pdf output.pdf --language guj+hin+eng --deskew
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path


def emit(**payload) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


NOISE = ("OMP: Warning", "OMP: Hint", "KMP_")


class JsonLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            msg = record.getMessage().strip()
            if not msg or any(n in msg for n in NOISE):
                return
            emit(event="log", level=record.levelname.lower(), message=msg)
        except Exception:  # pragma: no cover - never let logging kill the job
            pass


def friendly_message(exc: BaseException) -> tuple[str, str]:
    """Map an OCRmyPDF exception to (code, plain-language message)."""
    from ocrmypdf import exceptions as E

    if isinstance(exc, E.EncryptedPdfError):
        return "encrypted", ("This PDF is password-protected. Remove the password first "
                             "(for example open it and use Print → Save as PDF), then try again.")
    if isinstance(exc, E.PriorOcrFoundError):
        return "has_text", ("This PDF already contains text, so it was skipped. Tick "
                            "'Re-OCR pages that already have text' to OCR it anyway.")
    if isinstance(exc, E.OutputFileAccessError):
        return "output", "Could not write the output file. Check that the folder is not read-only or full."
    if isinstance(exc, E.MissingDependencyError):
        return "dependency", ("A required component (Tesseract or Ghostscript) is missing from this "
                              "installation. Re-download the app.")
    if isinstance(exc, E.TesseractConfigError):
        return "config", "The OCR engine configuration is damaged. Re-download the app."
    if isinstance(exc, (E.InputFileError, E.UnsupportedImageFormatError, E.DpiError)):
        return "input", "This file could not be read as a PDF. It may be damaged, or not really a PDF."
    if isinstance(exc, E.SubprocessOutputError):
        return "engine", f"The OCR engine failed on this file. Details: {exc}"
    if isinstance(exc, E.BadArgsError):
        return "args", f"Invalid options: {exc}"
    if isinstance(exc, E.ExitCodeException):
        return "ocrmypdf", str(exc) or exc.__class__.__name__
    if isinstance(exc, MemoryError):
        return "memory", "The computer ran out of memory on this file. Close other programs and try again."
    return "unexpected", f"Unexpected error: {exc.__class__.__name__}: {exc}"


def run(args: argparse.Namespace) -> int:
    from . import paths

    paths.apply_environment()
    logging.basicConfig(level=logging.WARNING, handlers=[JsonLogHandler()])
    logging.getLogger("ocrmypdf").setLevel(logging.WARNING)

    import ocrmypdf

    plugin = Path(__file__).with_name("progress_plugin.py")
    emit(event="start", input=str(args.input), output=str(args.output),
         ocrmypdf=ocrmypdf.__version__, language=args.language)
    try:
        ocrmypdf.ocr(
            args.input,
            args.output,
            language=args.language,
            deskew=args.deskew,
            rotate_pages=args.rotate_pages,
            force_ocr=args.force_ocr,
            skip_text=not args.force_ocr,
            sidecar=args.sidecar,
            jobs=args.jobs or None,
            pdf_renderer="sandwich",
            output_type="pdf",
            optimize=1,
            progress_bar=True,
            plugins=[str(plugin)],
        )
    except KeyboardInterrupt:
        emit(event="error", code="cancelled", message="Cancelled.")
        return 130
    except BaseException as exc:  # noqa: BLE001 - everything becomes a JSON error
        code, message = friendly_message(exc)
        emit(event="error", code=code, message=message)
        return 1
    emit(event="done", output=str(args.output), sidecar=str(args.sidecar) if args.sidecar else None)
    return 0


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="ocr-worker")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--language", default="guj+hin+eng")
    p.add_argument("--deskew", action="store_true")
    p.add_argument("--rotate-pages", action="store_true")
    p.add_argument("--force-ocr", action="store_true")
    p.add_argument("--sidecar", type=Path, default=None)
    p.add_argument("--jobs", type=int, default=0)
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(run(parse()))
