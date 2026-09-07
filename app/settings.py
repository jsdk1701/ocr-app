"""User-facing options and their mapping to OCRmyPDF arguments."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from .paths import user_config_file

LANGUAGES: list[tuple[str, str]] = [
    ("Mixed (Gujarati + Hindi + English)", "guj+hin+eng"),
    ("Gujarati (+ English)", "guj+eng"),
    ("Hindi (+ English)", "hin+eng"),
    ("English only", "eng"),
]
LANGUAGE_LABELS = [label for label, _ in LANGUAGES]
LANGUAGE_BY_LABEL = dict(LANGUAGES)
LABEL_BY_LANGUAGE = {code: label for label, code in LANGUAGES}


@dataclass
class OcrSettings:
    language: str = "guj+hin+eng"
    deskew: bool = True
    rotate_pages: bool = True
    force_ocr: bool = False
    sidecar: bool = True
    jobs: int = 0  # 0 = all cores
    last_update_check: float = 0.0
    last_folder: str = ""
    skipped_release: str = ""

    def effective_jobs(self) -> int:
        return self.jobs or max(1, (os.cpu_count() or 2))


def load_settings() -> OcrSettings:
    p = user_config_file()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            known = {k: v for k, v in data.items() if k in OcrSettings.__dataclass_fields__}
            return OcrSettings(**known)
        except (OSError, ValueError, TypeError):
            pass
    return OcrSettings()


def save_settings(s: OcrSettings) -> None:
    try:
        user_config_file().write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")
    except OSError:
        pass
