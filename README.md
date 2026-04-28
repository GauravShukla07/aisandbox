# Local PDF Sheet Extractor

This repository contains a small local utility for extracting spreadsheet-like
tables from scanned PDFs or sheet images into Excel without using an LLM or any
external API.

## What it does

The extractor keeps sensitive data on-device and uses a traditional computer
vision + OCR pipeline:

1. Render each PDF page to an image locally
2. Detect horizontal and vertical table lines with OpenCV
3. Crop each detected cell
4. OCR each cell with Tesseract
5. Write the result to `.xlsx`, with optional per-page `.csv` files

This works best when the PDF contains images of sheets with clearly visible row
and column borders.

## Requirements

- Python 3.10+
- Tesseract OCR installed locally

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Usage

Extract a PDF into an Excel workbook:

```bash
python3 pdf_sheet_extractor.py input.pdf -o output.xlsx
```

Extract an image or a directory of images:

```bash
python3 pdf_sheet_extractor.py sheet.png
python3 pdf_sheet_extractor.py ./scanned-pages --csv-dir ./csv-out
```

Write debugging overlays to inspect the detected table grid:

```bash
python3 pdf_sheet_extractor.py input.pdf --debug-dir ./debug
```

Useful OCR tuning options:

```bash
python3 pdf_sheet_extractor.py input.pdf --lang eng --psm 7 --oem 3
```

## Output

- One Excel workbook with one worksheet per page/image
- Optional CSV exports, one file per page/image
- Optional debug overlay images showing detected grid lines

## Important limitations

- The current extractor expects visible table borders. If the sheet image has no
  clear row/column lines, the grid detector will likely fail.
- OCR quality depends heavily on scan quality, skew, blur, font size, and
  contrast.
- Merged cells are flattened into ordinary rectangles and may need manual cleanup
  afterward.

## Files

- `pdf_sheet_extractor.py` - main CLI extractor
- `requirements.txt` - Python dependencies
