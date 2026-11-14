# OCR chart review demo

A local React + FastAPI workbench for comparing scanned vital-sign forms with a
CSV of scheduled readings, using a two-panel wizard.

**Configure source data:** choose Upload file, Database, or API. File upload
supports CSV; Database and API offer configuration previews only. Select a source
file and click **Confirm source**. The server validates its contents before the
wizard advances. Invalid uploads stay on this panel with an error.

**Documents and audit:** add PDFs and click **Process** to inspect uploaded
information, confidence, and highlighted document regions. Then click
**Compare / Audit** to compare it with the confirmed source. Results use separate
**Uploaded** and **Source** columns. Select any result row (or use its radio
control with the keyboard) to open the matching PDF page and center the field's
bounding box, including when zoomed in. Solid boxes mark detected text; dashed
boxes mark expected areas that need manual inspection. Filtering out the selected
row removes its highlight. Auditing never reruns OCR.

During processing, the UI shows live phases: uploading, checking documents,
loading OCR, reading pages, and preparing results. The page bar measures completed
pages; phases without a measurable total use an indeterminate animation. Audit
requests display **Analyzing…** until the response arrives. Loading indicators
respect reduced-motion settings and clear on success or errors. Use **Back to
source** to change the reference data; changing it invalidates the audit report
while retaining the document extraction.

Multiple PDFs are combined into one chart in upload order and audited against the
single CSV schedule. Every result retains its document name and local page
number. Ambiguous alignment remains unresolved.

Changing the main source clears the report and retains extraction.
Adding/removing PDFs clears both extraction and report. Clear run resets everything.

## Run locally

Requires Python **3.11** (tested), Node **20.19+ or 22.12+**, and npm. CPU only;
no inference API key, external OCR service, database, or Tesseract installation.
Install dependencies and build once, from the repository root:

```bash
python3.11 -m venv data/venv
source data/venv/bin/activate
python -m pip install -r requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open **http://127.0.0.1:8000**. Select your own PDF and CSV, or use the two example
files in `data/`. The backend does not load those examples automatically.
RapidOCR uses local ONNX models; its pinned distribution includes the default
models. A different installation/configuration may download models on first use.
Allow extra time for initialization. Rebuild after changing frontend code.

For development, run FastAPI as above and, in another terminal:

```bash
npm run dev --prefix frontend
```

Open the Vite URL (normally http://127.0.0.1:5173). `/api` is proxied to port 8000.
No CORS configuration is needed. Run one backend worker for this small demo.

## What the demo does

- Accepts 1–10 PDFs (20 MB and 1–12 pages in total) and one UTF-8 CSV
  (1 MB maximum). Requests are bounded to 22 MB, including multipart overhead.
- Renders scans to at most 2,000 pixels on the longest side, then runs local
  RapidOCR/ONNX OCR. It detects printed labels and reads their adjacent regions.
- Parses CSV reading times across columns and fields down rows. Quoted cells,
  a UTF-8 BOM, blank values, `Diasistolic`, and `Heart Rate (Systolic)` are supported.
  Times must increase within one day. Unknown/duplicate fields are rejected.
- Aligns the printed form intervals with the CSV's relative schedule, requiring
  supporting handwritten times to establish the baseline. If interval headings
  cannot establish alignment, an exact, consistent actual-time offset of at most
  ten minutes is required across the full sequence. Otherwise results are unresolved.
- Preserves OCR text, parsed values, CSV text, actual times, scheduled times,
  confidence, page numbers, and relative bounding boxes. Decimal formatting and
  Yes/Y or No/N variants normalize without clinical ranges or numeric tolerances.
- Separates `match`, `mismatch`, `missing_in_ocr`, `no_ground_truth`, and
  `unresolved` from the configurable low-confidence threshold. Filtering and
  source selection happen entirely in the browser. An expected region is labeled
  separately from an actual detected text box.

## Scope and sample validation

This specializes in the supplied upright, repeated vital-sign chart layout.
It is **not a general medical-form reader**. Checkboxes are deliberately marked
unresolved for manual inspection: recognizing their printed labels does not
establish whether a box was ticked. Crossed-out or corrected handwriting can
produce incorrect numbers even at high confidence. A mismatch means OCR differs
from the CSV; it is not a verified chart discrepancy.

The six-page development sample contains **16 populated forms** plus a blank,
crossed-out final form. The initial times run about five minutes after the CSV,
but that offset does not hold for the full document. Printed interval headings
establish the sequence instead. Forms with no recognized time or numeric field
are omitted; if that loses a scheduled reading, count/interval validation leaves
alignment unresolved rather than shifting the following readings.

Validated with the pinned engine on the sample: **112 field results**, comprising
58 matches, 14 mismatches, 37 unresolved values (including 32 checkbox values),
and 3 blank-ground-truth values. Eleven actual times were parsed; unreadable times
remain unverified. These counts demonstrate processing, **not OCR accuracy**.
Processing took about 14 seconds on the development machine; hardware varies.
Expected CSV answers never enter the OCR extraction module.

## Privacy and lifecycle

Files go to the FastAPI server. With the loopback commands above, processing stays
on your computer. If you host it remotely, uploaded files leave your computer.

There is no database, report directory, persistent run state, or report logging.
Multipart uploads may briefly spool to system temporary files; the parser closes
and deletes them on completion or errors. OCR runs in a separate process using
in-memory PDF bytes and page images. The worker is terminated after the response,
on client disconnect, or after ten minutes. Only one run is accepted at a time.
Responses use `Cache-Control: no-store`. The browser holds the extraction, report,
and source images until Clear run or refresh. The audit request sends only the CSV
and extracted readings back to the server; it does not resend PDF page images. Model files are software assets in the OCR
package/cache and remain installed. ONNX telemetry is disabled.

Private samples and local development artifacts belong in ignored `data/`.
Only `data/.gitkeep` should be committed. Runtime processing never writes uploads
or reports there. Do not force-add samples, screenshots, or local test reports.

## Checks

```bash
source data/venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
npm run build --prefix frontend
node .agents/skills/avoid-ai-design/scripts/detect.mjs frontend/src
```

Tests cover CSV validation/normalization, comparison states, interval alignment,
ambiguous timestamps, checkbox uncertainty, upload limits, malformed PDFs, separate
extraction/auditing, and combined multi-document audits.
A real-sample Chrome check also exercised the wizard flow with the sample
split into two PDFs, configuration previews, source highlighting across PDFs,
mismatch filtering, mobile layout, and invalidation of stale results. No browser automation dependency
is needed to run the demo.

API: `GET /api/health` reports service readiness (models initialize on demand).
- `POST /api/source`: multipart `source` file. Validates the reference CSV and
  returns reading/field counts, without saving the uploaded data.
- `POST /api/extract`: multipart `pdfs` file fields (repeat for each PDF). Returns
  extracted documents and source page images, without comparison results. With
  `Accept: application/x-ndjson`, streams progress events followed by a final
  `result` event, or an `error` event if processing fails. Blank lines keep the
  connection live. The wizard uses this stream; no jobs or results are persisted.
- `POST /api/compare`: multipart `csv` file and `extraction` JSON string containing
  `documents` (the extraction response's document array in upload order). Returns the audit report; the server saves no extraction state.
- `POST /api/ocr`: retained for older clients; accepts `pdf` and `csv` file fields
  and performs the original single-document combined operation.

Errors return a `detail` message. A busy OCR server returns 409; a processing
timeout returns 504.

See [the original design](docs/system-design.md) for the handoff specification.
