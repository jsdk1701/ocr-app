#!/bin/bash
# Launcher for "OCR App.app". Everything lives in Contents/Resources so the
# bundle can be moved anywhere. First run strips the quarantine flag from the
# bundled binaries so macOS does not prompt for each one.
set -u
RES="$(cd "$(dirname "$0")/../Resources" && pwd)"
APP="$(cd "$RES/../.." && pwd)"
if xattr -p com.apple.quarantine "$APP" >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
fi
export OCRAPP_ROOT="$RES"
export PYTHONPATH="$RES"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
cd "$RES"
exec "$RES/env/bin/python" -m app "$@"
