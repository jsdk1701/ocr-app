"""Tiny Windows launcher, frozen to "OCR App.exe" with PyInstaller.

It only sets environment variables and starts the bundled pythonw on the app,
so OCRmyPDF itself is never frozen.
"""
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
env = dict(os.environ)
env["OCRAPP_ROOT"] = here
env["PYTHONPATH"] = here
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONNOUSERSITE"] = "1"
pythonw = os.path.join(here, "env", "pythonw.exe")
if not os.path.exists(pythonw):
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, "The 'env' folder is missing. Please unzip the whole "
                                     "OCR App folder, not just the .exe.", "OCR App", 0x10)
    sys.exit(1)
subprocess.Popen([pythonw, "-m", "app"], cwd=here, env=env,
                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
