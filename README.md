# OCR App

A small desktop app for Windows and macOS that turns scanned PDFs in **Gujarati, Hindi and English** into searchable PDFs. Built on [OCRmyPDF](https://ocrmypdf.readthedocs.io/) and Tesseract, bundled so the person using it installs nothing and needs no account or internet connection.

- Pick one or more PDFs, press Start, get `name-ocr.pdf` (and optionally `name-ocr.txt`) next to each original.
- Straightens and auto-rotates pages, keeps the original scan pixels untouched, adds an invisible text layer.
- Updates itself: newer language models can be installed from the Help menu, and the app tells you when a new release exists.

Downloads are on the [Releases](../../releases) page: one zip per platform (Windows, Mac Apple Silicon, Mac Intel). Each zip contains `User-Guide.pdf` with first-launch instructions.

For building and releasing, see [docs/DEVELOPING.md](docs/DEVELOPING.md).
