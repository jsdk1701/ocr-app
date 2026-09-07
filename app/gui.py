"""The window: pick PDFs, choose options, watch progress, get searchable PDFs."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME, __version__, paths, settings, updates, versions

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class Job:
    input: Path
    output: Path
    sidecar: Path | None
    status: str = "Waiting"
    detail: str = ""
    iid: str = ""
    pages: int | None = None
    started: float = 0.0
    logs: list[str] = field(default_factory=list)


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(2, 1000):
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return q
    return p


def reveal(path: Path) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass


class App(tk.Tk):
    POLL_MS = 100

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.minsize(720, 520)
        self.settings = settings.load_settings()
        self.jobs: list[Job] = []
        self.current: Job | None = None
        self.proc: subprocess.Popen | None = None
        self.lines: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False
        self.cancel_requested = False
        self.readers_open = 0
        self.ui_queue: queue.Queue = queue.Queue()
        self._build()
        self.after(self.POLL_MS, self._poll)
        self.after(1500, self._auto_update_check)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- layout ----------
    def _build(self) -> None:
        self.option_add("*tearOff", False)
        menubar = tk.Menu(self)
        helpm = tk.Menu(menubar)
        helpm.add_command(label="Check for updates…", command=self.check_updates)
        helpm.add_command(label="Update language models…", command=self.update_models)
        helpm.add_command(label="Restore original language models", command=self.restore_models)
        helpm.add_separator()
        helpm.add_command(label="Open user guide", command=self.open_guide)
        helpm.add_command(label="About", command=self.about)
        menubar.add_cascade(label="Help", menu=helpm)
        self.config(menu=menubar)

        pad = {"padx": 10, "pady": 4}
        self.banner = tk.Frame(self, bg="#fff3cd")
        self.banner_label = tk.Label(self.banner, bg="#fff3cd", anchor="w", justify="left")
        self.banner_label.pack(side="left", fill="x", expand=True, padx=10, pady=6)
        self.banner_btn = tk.Button(self.banner, text="Download", command=self._banner_download)
        self.banner_btn.pack(side="right", padx=4)
        tk.Button(self.banner, text="Later", command=lambda: self.banner.pack_forget()).pack(side="right")
        self.banner_release: updates.ReleaseInfo | None = None

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        self.top = top
        ttk.Button(top, text="Add PDF files…", command=self.add_files).pack(side="left")
        ttk.Button(top, text="Remove selected", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Label(top, text="Language:").pack(side="left", padx=(18, 4))
        self.lang_var = tk.StringVar(value=settings.LABEL_BY_LANGUAGE.get(
            self.settings.language, settings.LANGUAGE_LABELS[0]))
        ttk.Combobox(top, textvariable=self.lang_var, values=settings.LANGUAGE_LABELS,
                     state="readonly", width=34).pack(side="left")

        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)
        self.deskew_var = tk.BooleanVar(value=self.settings.deskew)
        self.rotate_var = tk.BooleanVar(value=self.settings.rotate_pages)
        self.force_var = tk.BooleanVar(value=self.settings.force_ocr)
        self.sidecar_var = tk.BooleanVar(value=self.settings.sidecar)
        ttk.Checkbutton(opts, text="Straighten pages", variable=self.deskew_var).pack(side="left")
        ttk.Checkbutton(opts, text="Fix rotated pages", variable=self.rotate_var).pack(side="left", padx=12)
        ttk.Checkbutton(opts, text="Re-OCR pages that already have text",
                        variable=self.force_var).pack(side="left")
        ttk.Checkbutton(opts, text="Also save a .txt file", variable=self.sidecar_var).pack(side="left", padx=12)

        cols = ("file", "status", "detail")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended", height=8)
        self.tree.heading("file", text="PDF")
        self.tree.heading("status", text="Status")
        self.tree.heading("detail", text="Details")
        self.tree.column("file", width=330)
        self.tree.column("status", width=90, anchor="center")
        self.tree.column("detail", width=260)
        self.tree.pack(fill="both", expand=True, padx=10)
        self.tree.bind("<Double-1>", self._open_selected_output)

        prog = ttk.Frame(self)
        prog.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(prog, mode="determinate", maximum=1000)
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar(value="Add one or more scanned PDFs to begin.")
        ttk.Label(prog, textvariable=self.status_var).pack(anchor="w", pady=(4, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        self.start_btn = ttk.Button(btns, text="Start OCR", command=self.start)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=6)
        self.open_btn = ttk.Button(btns, text="Show output folder", command=self.open_output, state="disabled")
        self.open_btn.pack(side="right")
        ttk.Label(btns, text="Output is saved next to each PDF as  name-ocr.pdf",
                  foreground="#555").pack(side="right", padx=10)

        self.log = tk.Text(self, height=5, state="disabled", wrap="word", font=("TkDefaultFont", 10))
        self.log.pack(fill="x", padx=10, pady=(0, 10))

    # ---------- job list ----------
    def add_files(self) -> None:
        initial = self.settings.last_folder or str(Path.home())
        files = filedialog.askopenfilenames(title="Choose scanned PDF files",
                                            initialdir=initial,
                                            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not files:
            return
        self.settings.last_folder = str(Path(files[0]).parent)
        for f in files:
            self.add_job(Path(f))

    def add_job(self, path: Path) -> Job:
        path = path.expanduser().resolve()
        if any(j.input == path and j.status in ("Waiting", "Working") for j in self.jobs):
            return next(j for j in self.jobs if j.input == path)
        out = unique_path(path.with_name(f"{path.stem}-ocr.pdf"))
        side = unique_path(path.with_name(f"{path.stem}-ocr.txt")) if self.sidecar_var.get() else None
        job = Job(input=path, output=out, sidecar=side)
        job.iid = self.tree.insert("", "end", values=(path.name, job.status, ""))
        self.jobs.append(job)
        self._set_status(f"{len([j for j in self.jobs if j.status == 'Waiting'])} file(s) ready. Press Start OCR.")
        return job

    def remove_selected(self) -> None:
        for iid in self.tree.selection():
            job = next((j for j in self.jobs if j.iid == iid), None)
            if job and job is not self.current:
                self.jobs.remove(job)
                self.tree.delete(iid)

    def _update_row(self, job: Job) -> None:
        self.tree.item(job.iid, values=(job.input.name, job.status, job.detail))

    # ---------- running ----------
    def _collect_settings(self) -> settings.OcrSettings:
        s = self.settings
        s.language = settings.LANGUAGE_BY_LABEL.get(self.lang_var.get(), "guj")
        s.deskew = self.deskew_var.get()
        s.rotate_pages = self.rotate_var.get()
        s.force_ocr = self.force_var.get()
        s.sidecar = self.sidecar_var.get()
        settings.save_settings(s)
        return s

    def start(self) -> None:
        if self.running:
            return
        if not any(j.status == "Waiting" for j in self.jobs):
            self.add_files()
            if not any(j.status == "Waiting" for j in self.jobs):
                return
        self._collect_settings()
        self.running = True
        self.cancel_requested = False
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self._next_job()

    def _next_job(self) -> None:
        job = next((j for j in self.jobs if j.status == "Waiting"), None)
        if job is None or self.cancel_requested:
            self._finish_all()
            return
        self.current = job
        job.status, job.detail, job.started = "Working", "Starting…", time.time()
        job.output = unique_path(job.output)
        if job.sidecar is None and self.settings.sidecar:
            job.sidecar = unique_path(job.input.with_name(f"{job.input.stem}-ocr.txt"))
        if not self.settings.sidecar:
            job.sidecar = None
        self._update_row(job)
        self.progress.config(value=0)
        self._set_status(f"Preparing {job.input.name}…")
        s = self.settings
        cmd = [paths.python_executable(), "-m", "app.worker", str(job.input), str(job.output),
               "--language", s.language, "--jobs", str(s.effective_jobs())]
        if s.deskew:
            cmd.append("--deskew")
        if s.rotate_pages:
            cmd.append("--rotate-pages")
        if s.force_ocr:
            cmd.append("--force-ocr")
        if job.sidecar:
            cmd += ["--sidecar", str(job.sidecar)]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(paths.APP_DIR)
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, encoding="utf-8", errors="replace",
                                         cwd=str(paths.APP_DIR), env=env, creationflags=CREATE_NO_WINDOW)
        except OSError as exc:
            self._job_failed(job, f"Could not start the OCR engine: {exc}")
            self._next_job()
            return
        self.readers_open = 2
        for stream, tag in ((self.proc.stdout, "out"), (self.proc.stderr, "err")):
            threading.Thread(target=self._reader, args=(stream, tag), daemon=True).start()

    def _reader(self, stream, tag: str) -> None:
        for line in iter(stream.readline, ""):
            self.lines.put((tag, line.rstrip("\n")))
        self.lines.put((tag, None))

    def _poll(self) -> None:
        try:
            while True:
                fn = self.ui_queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        try:
            while True:
                tag, line = self.lines.get_nowait()
                if line is None:
                    self.readers_open -= 1
                    continue
                if tag == "out":
                    self._handle_line(line)
                elif line.strip():
                    self._append_log(line)
        except queue.Empty:
            pass
        if self.proc is not None and self.proc.poll() is not None and self.readers_open <= 0:
            rc = self.proc.returncode
            job, self.proc, self.current = self.current, None, None
            if job and job.status == "Working":
                if rc == 0 and job.output.exists():
                    self._job_done(job)
                elif self.cancel_requested:
                    self._job_cancelled(job)
                else:
                    self._job_failed(job, job.detail or f"The OCR engine stopped unexpectedly (code {rc}).")
            self._next_job()
        self.after(self.POLL_MS, self._poll)

    def _handle_line(self, line: str) -> None:
        try:
            ev = json.loads(line)
        except ValueError:
            self._append_log(line)
            return
        job = self.current
        kind = ev.get("event")
        if job is None:
            return
        if kind == "stage":
            desc = ev.get("desc") or ""
            if ev.get("unit") == "page" and ev.get("total"):
                job.pages = int(ev["total"])
            self._set_status(f"{job.input.name}: {desc}…")
        elif kind == "progress":
            total = ev.get("total") or 0
            done = ev.get("completed") or 0
            if total:
                frac = min(1.0, done / total)
                self.progress.config(value=int(frac * 1000))
                if ev.get("unit") == "page":
                    elapsed = time.time() - job.started
                    eta = ""
                    if done >= 1 and frac < 1:
                        remaining = elapsed / done * (total - done)
                        eta = f"  ~{self._fmt_time(remaining)} left"
                    job.detail = f"page {int(done)} of {int(total)}"
                    self._update_row(job)
                    self._set_status(f"{job.input.name}: {ev.get('desc')} page {int(done)} of {int(total)}{eta}")
                else:
                    self._set_status(f"{job.input.name}: {ev.get('desc')} {int(frac * 100)}%")
        elif kind == "log":
            msg = ev.get("message", "")
            job.logs.append(msg)
            self._append_log(f"{job.input.name}: {msg}")
        elif kind == "error":
            job.detail = ev.get("message", "Failed")
            job.status = "Failed" if ev.get("code") != "has_text" else "Skipped"
        elif kind == "done":
            pass

    def _job_done(self, job: Job) -> None:
        secs = time.time() - job.started
        job.status = "Done"
        pages = f"{job.pages} pages, " if job.pages else ""
        job.detail = f"{pages}{self._fmt_time(secs)} → {job.output.name}"
        self._update_row(job)
        self._append_log(f"Finished {job.input.name} → {job.output}")
        self.open_btn.config(state="normal")

    def _job_failed(self, job: Job, message: str) -> None:
        if job.status == "Working":
            job.status = "Failed"
        job.detail = message
        self._update_row(job)
        self._append_log(f"{job.status}: {job.input.name}: {message}")
        self._remove_partial(job)

    def _job_cancelled(self, job: Job) -> None:
        job.status, job.detail = "Cancelled", ""
        self._update_row(job)
        self._remove_partial(job)

    def _remove_partial(self, job: Job) -> None:
        if job.status != "Done":
            for p in (job.output, job.sidecar):
                if p and p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

    def _finish_all(self) -> None:
        self.running = False
        self.current = None
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        done = sum(1 for j in self.jobs if j.status == "Done")
        failed = [j for j in self.jobs if j.status in ("Failed", "Skipped")]
        if self.cancel_requested:
            self._set_status("Cancelled.")
        elif failed:
            self._set_status(f"Finished: {done} done, {len(failed)} could not be processed (see Details).")
        else:
            self._set_status(f"All done: {done} file(s) converted.")
        self.progress.config(value=1000 if done and not failed else 0)
        self.bell()

    def cancel(self) -> None:
        if not self.running:
            return
        self.cancel_requested = True
        self._set_status("Cancelling…")
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except OSError:
                pass

    def open_output(self) -> None:
        job = next((j for j in reversed(self.jobs) if j.status == "Done"), None)
        if job:
            reveal(job.output)

    def _open_selected_output(self, _event=None) -> None:
        for iid in self.tree.selection():
            job = next((j for j in self.jobs if j.iid == iid), None)
            if job and job.status == "Done":
                reveal(job.output)

    # ---------- helpers ----------
    @staticmethod
    def _fmt_time(secs: float) -> str:
        secs = int(secs)
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{secs // 60}m {secs % 60:02d}s"
        return f"{secs // 3600}h {(secs % 3600) // 60:02d}m"

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _append_log(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _on_close(self) -> None:
        if self.running and not messagebox.askyesno(APP_NAME, "OCR is still running. Quit anyway?"):
            return
        self.cancel_requested = True
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except OSError:
                pass
        self._collect_settings()
        self.destroy()

    def _bg(self, fn, on_done) -> None:
        """Run fn in a thread; deliver its result (or exception) to on_done on the UI thread."""
        def run():
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                result = exc
            self.ui_queue.put(lambda: on_done(result))
        threading.Thread(target=run, daemon=True).start()

    # ---------- updates ----------
    def _auto_update_check(self) -> None:
        if time.time() - self.settings.last_update_check < 86400 or not updates.repo():
            return
        self.settings.last_update_check = time.time()
        settings.save_settings(self.settings)
        self._bg(updates.check_release, self._show_release_banner)

    def _show_release_banner(self, rel) -> None:
        if not isinstance(rel, updates.ReleaseInfo) or not rel.is_newer:
            return
        if rel.tag == self.settings.skipped_release:
            return
        self.banner_release = rel
        first = (rel.notes.strip().splitlines() or [""])[0][:120]
        self.banner_label.config(text=f"Version {rel.version} is available (you have {__version__}). {first}")
        self.banner.pack(fill="x", before=self.top)

    def _banner_download(self) -> None:
        rel = self.banner_release
        if not rel:
            return
        self.banner.pack_forget()
        self._download_release(rel)

    def _download_release(self, rel: updates.ReleaseInfo) -> None:
        if not rel.asset_url:
            webbrowser.open(rel.url)
            return
        self._set_status(f"Downloading {rel.asset_name}…")

        def progress(done, total):
            pct = f"{done * 100 // total}%" if total else f"{done // (1 << 20)} MB"
            self.ui_queue.put(lambda: self._set_status(f"Downloading {rel.asset_name}… {pct}"))

        def done(result):
            if isinstance(result, Exception):
                messagebox.showerror(APP_NAME, str(result))
                self._set_status("Download failed.")
                return
            self._set_status(f"Downloaded to {result}")
            messagebox.showinfo(APP_NAME, f"The new version was saved to:\n{result}\n\n"
                                "To update: quit this app, unzip the download, and replace the old "
                                f"'{APP_NAME}' folder with the new one. The user guide has pictures of each step.")
            reveal(result)

        self._bg(lambda: updates.download_release(rel, progress), done)

    def check_updates(self) -> None:
        if not updates.repo():
            messagebox.showinfo(APP_NAME, "Update checks are not configured for this build.")
            return
        self._set_status("Checking for updates…")

        def done(result):
            if isinstance(result, Exception):
                messagebox.showerror(APP_NAME, str(result))
                self._set_status("Update check failed.")
                return
            rel = result
            if rel and rel.is_newer:
                self._set_status(f"Version {rel.version} is available.")
                if messagebox.askyesno(APP_NAME, f"Version {rel.version} is available (you have {__version__}).\n\n"
                                       f"{rel.notes[:600]}\n\nDownload it now?"):
                    self._download_release(rel)
            else:
                self._set_status("You have the latest version.")
                messagebox.showinfo(APP_NAME, f"You have the latest version ({__version__}).")

        self._bg(updates.check_release, done)

    def update_models(self) -> None:
        if self.running:
            messagebox.showinfo(APP_NAME, "Please wait for OCR to finish before updating models.")
            return
        self._set_status("Checking language models…")

        def done(result):
            if isinstance(result, Exception):
                messagebox.showerror(APP_NAME, str(result))
                self._set_status("Model check failed.")
                return
            if not result:
                self._set_status("Language models are up to date.")
                messagebox.showinfo(APP_NAME, "Your language models are already the latest available.")
                return
            names = ", ".join(u.name for u in result)
            size = sum(u.size for u in result) / (1 << 20)
            if not messagebox.askyesno(APP_NAME, f"Newer language models are available: {names} "
                                       f"({size:.0f} MB).\n\nDownload and install them now?"):
                self._set_status("Model update skipped.")
                return
            self._install_models(result)

        self._bg(updates.check_models, done)

    def _install_models(self, ups: list) -> None:
        def work():
            installed = []
            for u in ups:
                self.ui_queue.put(lambda u=u: self._set_status(f"Downloading {u.name} model…"))
                updates.install_model(u)
                installed.append(u.name)
            return installed

        def done(result):
            if isinstance(result, Exception):
                messagebox.showerror(APP_NAME, str(result))
                self._set_status("Model update failed. Previous models are still in place.")
                return
            self._set_status(f"Installed updated models: {', '.join(result)}.")
            messagebox.showinfo(APP_NAME, f"Updated language models installed: {', '.join(result)}.\n\n"
                                "If results look worse, use Help → Restore original language models.")

        self._bg(work, done)

    def restore_models(self) -> None:
        if self.running:
            messagebox.showinfo(APP_NAME, "Please wait for OCR to finish first.")
            return
        names = updates.restore_bundled_models()
        msg = ("Restored the original models: " + ", ".join(names)) if names else "No updated models were installed."
        self._set_status(msg)
        messagebox.showinfo(APP_NAME, msg)

    def open_guide(self) -> None:
        for name in ("User-Guide.pdf", "docs/User-Guide.pdf", "docs/User-Guide.md"):
            p = paths.APP_DIR / name
            if p.exists():
                webbrowser.open(p.as_uri())
                return
        messagebox.showinfo(APP_NAME, "The user guide was not found next to the app.")

    def about(self) -> None:
        self._set_status("Collecting version information…")

        def done(result):
            if isinstance(result, Exception):
                messagebox.showerror(APP_NAME, str(result))
                return
            v = result
            models = "\n".join(f"    {n}: {m['sha'][:10]} ({m['source']})" for n, m in v.get("models", {}).items())
            b = versions.bundled_versions()
            messagebox.showinfo(f"About {APP_NAME}",
                                f"{APP_NAME} {v['app']}\n"
                                f"Build: {b.get('built', 'from source')}  {b.get('platform', '')}\n\n"
                                f"OCRmyPDF {v['ocrmypdf']}\nTesseract {v['tesseract']}\nGhostscript {v['ghostscript']}\n\n"
                                f"Language models:\n{models}")
            self._set_status("")

        self._bg(versions.live_versions, done)
