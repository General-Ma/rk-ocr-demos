# OCR Chart Review Demo — System Design

## Goal

Build a local web demo where a user drops a scanned PDF and its ground-truth
CSV into two drop zones. The app OCRs the document, compares its readings with
the CSV, and presents mismatches and uncertain readings for review.

Uploaded files and results exist only in browser memory or temporary server
storage for the current run. Do not add a database or persist uploads or
reports. The files in `data/` are development examples, not production inputs.

## Sample data and domain shape

- `Scanned Document.pdf` is a six-page, image-only scan of handwritten vital
  sign readings, about 6.3 MB. It has no extractable text, so OCR is required.
- `Scanned Document - answer.csv` has 16 reading-time columns from 10:00 AM to
  1:45 PM at 15-minute intervals. Rows represent vital status performed,
  systolic and diastolic blood pressure, heart rate, temperature, weight, and
  clinical significance.
- The PDF appears to contain 16 reading forms. Its handwritten times appear to
  be about five minutes later than the CSV's scheduled times in at least the
  first readings. Confirm this relationship across the document before
  applying any offset. Keep both scheduled and OCR-read times in the report.
- The first implementation may specialize in this chart format. Do not imply
  reliable support for arbitrary medical forms.

## Recommended architecture

- **Frontend:** React with Vite.
- **Backend:** FastAPI.
- **OCR:** Run an open-source OCR pipeline on the FastAPI server without an
  inference API key. PaddleOCR is a candidate; validate its performance on the
  handwritten sample before relying on it. Model weights may download on first
  startup and use the OCR library's local cache.
- **Storage:** No database. Keep selected files and results in React page
  state. Process in memory where practical; if PDF rendering or OCR requires
  files, use a temporary directory and remove it when processing finishes,
  including on errors. Never write uploads or reports into `data/`.
- **Hosting:** Initial scope is local development. If hosted remotely later,
  clearly tell users files are sent to that server for processing.

## User flow

1. Show two labeled drop zones side by side: **Scanned document** (PDF) and
   **Ground truth** (CSV).
2. Accept one file in each zone. Show filename and size with remove/replace
   actions. Validate type and size; enable **Run comparison** only when both
   files are valid.
3. Submit both files in one multipart request. Show honest progress for
   upload, PDF processing, OCR, comparison, and report preparation. If the
   server cannot report real stage progress, use an indeterminate state rather
   than fabricated percentages.
4. Show the report in the same page and let users inspect each reading against
   its ground truth and source location.
5. Clearing the report or refreshing the page clears the run. An optional
   report download may be generated in the browser; the server must not save
   it.

## Processing pipeline

1. Validate that the first file is a readable PDF and the second a readable
   CSV. Apply upload and page-count limits; handle temporary files safely.
2. Render PDF pages to bounded-size images to control memory use.
3. Run OCR and use the chart layout to extract each reading's time, field
   values, confidence, page, and page-relative bounding boxes.
4. Parse CSV as a matrix: header columns contain scheduled times and rows
   contain field values. Support quoted cells, blank cells, and a UTF-8 BOM.
5. Normalize both inputs into a common reading-by-field structure. Use
   canonical field IDs internally while retaining original CSV labels.
   Accommodate source spellings such as `Diasistolic` and
   `Heart Rate (Systolic)` without silently altering the source text.
6. Align readings by sequence if that is the established relationship, while
   recording both scheduled and OCR-read times. Do not require exact timestamp
   equality if the form records actual times and the CSV uses scheduled slots.
   If alignment is ambiguous, mark it unresolved instead of comparing likely
   unrelated readings.
7. Normalize harmless formatting differences (for example, `75.40` and
   `75.4`, or recognized `Y`/`Yes` variants). Preserve the raw OCR and CSV
   text. Do not apply clinical ranges or tolerance rules unless explicitly
   defined later.
8. Return a structured report. Delete temporary user files after processing,
   including on failure.

## Comparison and report

Keep comparison result separate from OCR confidence. Suggested per-field
comparison states:

- `match`
- `mismatch`
- `missing_in_ocr`
- `no_ground_truth` — CSV cell is blank; do not count it as a mismatch
- `unresolved` — reading could not be safely aligned or interpreted

Expose OCR confidence separately, with a configurable low-confidence
threshold. A low-confidence OCR value may also be a mismatch; show both facts.
Never present OCR output as verified data.

The report should summarize compared values, matches, mismatches,
low-confidence readings, and unscored or unresolved values. Each detail should
include PDF page, scheduled time, actual time if recognized, field, OCR value,
CSV value, comparison state, confidence, and source bounding box. Selecting a
row should show its source page with the region highlighted.

## API outline

- `GET /api/health` — simple service-ready check.
- `POST /api/ocr` — multipart PDF and CSV upload; returns a structured report
  or a clear validation/processing error.

A synchronous request is adequate for the initial small demo. Keep progress
indeterminate unless the backend can report genuine incremental progress. If
incremental progress or cancellation becomes necessary, use an in-memory job
mechanism without introducing a database.

## Suggested repository layout

```text
app/
  main.py
  api/
  services/
    pdf_render.py
    ocr.py
    csv_ground_truth.py
    align.py
    compare.py
  schemas.py
frontend/
  src/
    components/
    api/
    App.jsx
```

Follow `AGENTS.md`, inspect the repo before implementation, and document setup
and run commands in `README.md`. Keep the example files in ignored `data/` for
local development; do not hardcode them as user-facing inputs.

## UI direction

Design this as a **document review workbench**, not a marketing page or generic
dashboard. During intake, emphasize the two drop zones. During review, give the
scanned chart and comparison rows enough room to inspect together.

Use a restrained paper-and-ink palette: warm paper background, dark ink,
muted form-rule gray, deliberate review blue, red for confirmed mismatches,
and amber for uncertainty. Use a legible UI face and tabular numerals for times
and measurements. Avoid gradients, oversized hero sections, decorative card
templates, and status conveyed by color alone. Pair status colors with labels
or icons; preserve keyboard focus and readable contrast.

Apply the repository's `avoid-ai-design` skill during UI implementation. Keep
the tool dense and legible; do not substitute another trendy palette or
template.

## Privacy and error handling

Do not log uploaded content, OCR text, or clinical values. Return useful errors
for invalid files, malformed CSVs, unsupported page counts, OCR failures, and
timeouts. Keep user uploads and report results transient. Model weights may use
the OCR library cache; they are not user documents or report data.

## Completion criteria

- A user can drop one PDF and one CSV into the page and run a comparison.
- The image-only PDF is processed and the CSV fields and times are parsed into
  comparable readings.
- The report distinguishes mismatches, missing OCR, blank ground truth, and
  low confidence.
- Selecting a result lets the user inspect its source page and location.
- Uploaded files and reports are not saved after the run; no database is
  introduced.
- Setup and usage instructions are documented.
