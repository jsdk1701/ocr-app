"""OCRmyPDF plugin that reports progress as JSON lines on stdout.

Loaded by the worker via ``ocrmypdf.ocr(plugins=[this file])``. OCRmyPDF holds
the progress bar in the parent process and calls ``update`` as pages finish.
"""
from __future__ import annotations

import json
import sys

from ocrmypdf import hookimpl


def emit(**payload) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class JsonProgressBar:
    def __init__(self, *, total=None, desc=None, unit=None, disable=False, **kwargs):
        self.total = total
        self.desc = desc or ""
        self.unit = unit or ""
        self.disable = disable
        self.completed = 0.0

    def __enter__(self):
        if not self.disable:
            emit(event="stage", desc=self.desc, total=self.total, unit=self.unit)
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, n=1, *, completed=None, **kwargs):
        if completed is not None:
            self.completed = float(completed)
        else:
            self.completed += float(n or 0)
        if not self.disable:
            emit(event="progress", desc=self.desc, completed=self.completed,
                 total=self.total, unit=self.unit)


@hookimpl
def get_progressbar_class():
    return JsonProgressBar
