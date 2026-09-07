# OCR App — User Guide

OCR App turns a scanned PDF (a photo of each page) into a PDF you can **search**, **select** and **copy text from**. It reads **Gujarati, Hindi and English**. Nothing is uploaded anywhere: all work happens on your own computer, and no internet connection is needed to convert files.

The converted file is saved **next to the original** with `-ocr` added to the name. Your original PDF is never changed.

## 1. Download and unzip

1. Download the zip file for your computer:
   - **Windows**: `OCR-App-…-windows.zip`
   - **Mac with Apple chip (M1, M2, M3, M4…)**: `OCR-App-…-macos-arm64.zip`
   - **Mac with Intel chip**: `OCR-App-…-macos-x86_64.zip`
   - Not sure which Mac? Click the Apple menu → *About This Mac*. It says either "Apple M…" or "Intel".
2. **Unzip it completely.** On Windows, right-click the zip → *Extract All…* and pick a place like *Documents*. On a Mac, double-click the zip. You get a folder called **OCR App**.
3. Keep the whole folder together. The app needs the `env` folder that sits next to it. You can move the folder anywhere, including a USB stick.

## 2. First time you open the app

The app is not signed with a paid developer certificate, so your computer shows a warning **once**. This is expected. Follow the steps for your system.

### Windows

1. Open the *OCR App* folder and double-click **OCR App.exe**.
2. A blue box says *"Windows protected your PC"*. Click **More info**.
3. Click **Run anyway**.

You only need to do this the first time.

### Mac (macOS 15 Sequoia or newer)

1. Double-click **OCR App**. A message says it *"was not opened"* or *"cannot be opened"*. Click **Done**.
2. Open **System Settings** → **Privacy & Security**.
3. Scroll down to the *Security* section. You will see *"OCR App was blocked to protect your Mac"*. Click **Open Anyway**.
4. Enter your Mac password. Click **Open** on the final confirmation.

### Mac (macOS 14 or older)

1. **Right-click** (or hold Control and click) **OCR App** and choose **Open**.
2. Click **Open** in the dialog.

### If the Mac still refuses

Open **Terminal** (press Command + Space, type *Terminal*, press Enter), then type the following and press Enter. Replace the path with wherever your folder is; dragging the app onto the Terminal window types the path for you.

```
xattr -dr com.apple.quarantine "/Users/yourname/Downloads/OCR App/OCR App.app"
```

Then double-click the app normally.

## 3. Converting a PDF

1. Click **Add PDF files…** and choose one or more scanned PDFs.
2. Pick the **Language**. *Gujarati only* is the default. Choose *Gujarati (+ English)* for books with English passages, *Hindi (+ English)* for Hindi books, or *Mixed* when a document has all three. Picking the exact language gives the best results and is fastest.
3. Leave **Straighten pages** and **Fix rotated pages** ticked. They correct crooked or sideways scans.
4. **Re-OCR pages that already have text** is ticked by default, so every page is read fresh even if the PDF already had some (possibly wrong) text. Untick it to leave such pages alone.
5. Tick **Also save a .txt file** if you also want the plain text in a separate file.
6. Press **Start OCR**. The progress bar shows the page count and time left. You can keep using your computer; leave the app open.
7. When it says *All done*, click **Show output folder**. You will find:
   - `name-ocr.pdf` — the searchable PDF
   - `name-ocr.txt` — the plain text, if *Also save a .txt file* was ticked

To convert several books, add them all first; they are processed one after another.

### How long does it take?

Roughly 1 to 3 seconds per page on a recent laptop. A 400-page book takes about 5 to 15 minutes. Older computers take longer.

### How good is the text?

On clean printed books the text is very accurate. Old, faded, decorative or handwritten pages will have mistakes. The text is hidden behind the scanned image, so the page always *looks* exactly like the original; only search and copy are affected by mistakes.

## 4. If something goes wrong

The *Details* column and the box at the bottom of the window explain what happened. Common messages:

- **This PDF is password-protected** — open the PDF, choose *Print* → *Save as PDF*, and convert that copy.
- **This PDF already contains text** — it was skipped because *Re-OCR pages that already have text* was unticked. Tick it to redo the file.
- **Could not write the output file** — the folder is read-only or the disk is full. Move the PDF to *Documents* and try again.
- **The 'env' folder is missing** (Windows) — the zip was not fully extracted. Extract the whole folder again.

If the app does not open at all, re-download the zip and repeat section 2.

## 5. Keeping it up to date

Better language models and engine versions come out from time to time.

- **Help → Update language models…** downloads newer Gujarati / Hindi / English recognition files. Takes under a minute. If results look worse afterwards, use **Help → Restore original language models**.
- **Help → Check for updates…** looks for a new version of the whole app. The app also checks once a day when it starts and shows a yellow bar at the top if there is one. Click **Download**, then:
  1. Quit OCR App.
  2. Unzip the downloaded file.
  3. Replace your old *OCR App* folder with the new one.
  4. Open it. The first-time warning from section 2 appears again once.

**Help → About** shows exactly which versions you have.

## 6. Removing the app

Delete the *OCR App* folder. To also remove settings and downloaded models, delete:

- Windows: `%APPDATA%\OCR App`
- Mac: `~/Library/Application Support/OCR App`

## 7. Getting help

Send the person who gave you the app: which computer you use (Windows / Mac), the message from the *Details* column, and if possible the PDF that failed.
