# aisandbox

Offline PDF-to-Excel extraction for scanned spreadsheet pages.

## What this does

This repository now contains a local-only command line tool that:

1. renders each PDF page to an image locally,
2. detects table grid lines with OpenCV,
3. OCRs each detected cell with a local ONNX OCR model, and
4. writes the result into an `.xlsx` workbook.

It does **not** use an LLM and does **not** send data to any external API.

## When this approach works best

Use this for PDFs that are effectively images of sheets, especially when:

- the table has visible row and column borders,
- text is reasonably sharp,
- the page is not heavily rotated or skewed.

If your PDF already contains selectable text instead of scanned images, classic
PDF table tools such as Camelot or Tabula may work even better, also without
LLMs.

## Installation

```bash
python3 -m pip install -r requirements.txt
```

## Usage

```bash
python3 offline_pdf_excel.py input.pdf output.xlsx --infer-numbers
```

Useful tuning flags:

- `--dpi 220` increases render quality before OCR.
- `--cell-padding 3` trims borders away from each cell before OCR.
- `--line-coverage-ratio 0.2` controls how much of a line must be visible to
  count as a row or column border.
- `--ocr-score-threshold 0.35` filters weak OCR results.

Show all options:

```bash
python3 offline_pdf_excel.py --help
```

## Output behavior

- Each detected table becomes a separate worksheet.
- Worksheet names follow `page-N-table-M`.
- With `--infer-numbers`, plain integers and decimals are written as numeric
  Excel cells.

## Notes and limitations

- Merged cells are not reconstructed explicitly; the tool emits the detected
  cell grid and OCR text per cell.
- Borderless tables are much harder to recover with classical CV alone.
- If no stable grid is found, the workbook is still created with a note instead
  of failing silently.
