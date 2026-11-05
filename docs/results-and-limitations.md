# Results and limitations

## 1. Real-document demonstration — NOT YET RUN

No genuine supplier SDS revision pair has been tested yet.

From the build environment, supplier sites and web.archive.org were blocked by
the network policy, so I couldn't retrieve or check any specific real SDS PDF.
The real-document acceptance criterion stays **not yet run** until a genuine old/new
pair of the same product from the same supplier has been processed. Results
will be recorded here, separate from the synthetic results below.

| Item | Status |
|---|---|
| Genuine old/new pair obtained | Not yet |
| Provenance recorded in `samples/real/manifest.json` | Not yet |
| Fields extracted correctly (checked by a person against the PDFs) | Not yet run |
| Section location for 2, 3, 8, 14 and 15 | Not yet run |
| Classification and comparison reviewed | Not yet run |

## 2. Synthetic fixture tests (generated documents, not real SDSs)

All automated tests use PDFs generated at test time by
`sdstracker/synthetic.py`. Every page is stamped "SYNTHETIC TEST DOCUMENT - NOT
A REAL SDS", and they use a generic 16-section layout written for this project.
The results show the workflow logic behaves as specified on those documents.
They say nothing about extraction accuracy on real supplier layouts.

Command: `.venv/bin/pytest -q`. The latest result is in the commit history and
in the final session report.

The tests cover:

- **Classification:** first document; duplicate received twice (two receipt
  records); newer revision; older document; same date with changed content;
  different hash with unchanged extracted text.
- **Uncertain inputs:** missing and ambiguous dates; unconfirmed or ambiguous
  material; CAS overlap alone not producing a candidate; no-register-match not
  creating a material.
- **Unreadable inputs:** image-only and malformed PDFs; a missing section; a
  section heading with no text, reported as extraction failed rather than no
  change.
- **Conflicts:** language/jurisdiction conflict not compared; identity conflict
  not forced into a revision.
- **Records:** draft not recorded as sent; review not recorded as approval;
  original PDF preserved byte for byte; filename not used as a storage path;
  upload size limit.
- **Baseline and history:** required activity events; no automatic baseline
  replacement; historical results unchanged after a baseline change.
- **Interface (Streamlit AppTest):** every page renders with the persistent
  notice, and page reruns do not create records.

### Manual browser walkthrough (synthetic demo data)

The app was run locally against `demo-data` and driven in headless Chromium:

1. Uploaded the synthetic v2 PDF, confirmed it as DEMO-RM-001, and got a newer
   dated revision against the explicit baseline.
2. The comparison showed text changes in Sections 2 and 8 and no text changes in
   Sections 3, 14 and 15.
3. Generated the draft and recorded a completed review acknowledgment.
4. Uploaded the same file twice more, giving two extra receipts classified as
   exact duplicates with the association inherited.
5. Uploaded the image-only PDF, which was flagged as having no usable text and
   left awaiting confirmation.

There were no page errors.

## 3. Known limitations

- **Extraction**
  - Labels and section headings are found with heuristics (for example
    "Revision date:", "SECTION 2" or "2. Hazards identification"). Real
    layouts can defeat them: labels in table cells, values on a separate line
    or column, two-column pages, unusual headings, or a table of contents
    that repeats section titles.
  - These cases surface as missing, ambiguous or conflicting fields, or as
    "section not found", never as silent success. They still need a person.
  - A line that mentions both a revision date and a print or "supersedes" date
    is skipped entirely, so the revision date may be reported missing.
  - Lines repeated on at least half the pages are treated as headers/footers
    and left out of section text. Genuinely repeated section text would be
    left out too.
  - Language and jurisdiction are inferred from a few keyword indicators. They
    are shown as "not verified" and are not a reliable edition check.
  - No OCR. Image-only PDFs always need manual review.
- **Comparison**
  - Comparison is word-token text diffing after whitespace normalization only.
    Re-flowed columns, hyphenation, or reordered table cells can show up as
    changes even when the meaning is the same.
  - A detected change is not an assessment of significance.
  - Only Sections 2, 3, 8, 14 and 15 are compared. Changes elsewhere are not
    detected.
- **Matching**
  - Matching uses normalized-name containment and exact product-identifier
    equality. That's enough for suggestions only; a person always confirms.
- **Versions and dates**
  - Version strings are recorded but never ordered.
  - Two documents with the same date but different versions are classified on
    date and content, not on version.
- **Operation**
  - Single-user local SQLite, with no authentication. Actor and reviewer names
    are free-text labels.
  - The activity history is ordinary database rows. It is not tamper-proof and
    is not certified compliance logging.
  - Manual field correction and CSV/Excel import are not in this release.

No accuracy or time-savings figures are claimed.
