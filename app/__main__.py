"""Entry point: ``python -m app`` starts the window."""
from __future__ import annotations

import sys


def main() -> int:
    from . import paths
    paths.apply_environment()
    from .gui import App
    App().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
