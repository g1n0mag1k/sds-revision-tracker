# Results and limitations

## 1. Real-document results

### 1a. Revision-pair validation — NOT YET RUN

No genuine old/new SDS pair has been tested. On 2026-11-05 a single
web.archive.org lookup for the exact Fisher SDS URL failed with an access
problem: the connection was reset before any response, on 4 attempts. One
further attempt after the allowed-domain settings were saved again failed the
same way. The archive check is recorded as unresolved, and no retries are
scheduled. No
capture list was obtained, so it is unknown whether an earlier revision is
archived. This acceptance criterion stays
**not yet run** until two genuine revisions of the same product from the same
supplier, in the same edition, have gone through the workflow.

### 1b. Single real document — parser validation (run 2026-11-05)

**One real supplier SDS tested; checked metadata and supported-section
boundaries verified on that document after targeted fixes.** This is not a
measure of general extraction accuracy. It is a parser test on one genuine
public SDS, **not** a masterbatch or raw-material demonstration, and not a
revision comparison. Shareable provenance:
[real-sds-provenance.json](real-sds-provenance.json).

**Document:**

| Item | Value |
|---|---|
| Document | Fisher Scientific SDS, Acetone (catalog list includes A18-4), US OSHA HCS 2024 edition, English, 10 pages |
| Printed revision date / number | 18-Dec-2025 / 9 |
| Source | `https://www.fishersci.com/store/msds?partNumber=A184&...` (supplier's own SDS link, found through its SDS search for "A18-4"). HTTP 200, `application/pdf`, no redirect. |
| Retrieved | 2026-11-05 |
| SHA-256 | `08b3b20730e03106b7867f2376c5bfbee388bcecccb19d61468b70289f1e59bb` |
| Storage | PDF in `samples/real/` (git-ignored); provenance committed in `docs/real-sds-provenance.json` |
| Validation | The file opens in pdfplumber, and the text identifies the product, supplier and edition. The `%PDF-` signature check was not relied on alone. |

**Fields:** extractor output compared by hand with the PDF text. The
"Before fixes" column is the first run; "After fixes" is the current code.

| Field | PDF says (page 1 unless noted) | Before fixes | After fixes |
|---|---|---|---|
| Product name | "Product Name Acetone" | Missing (label has no colon) | Correct: Acetone |
| Supplier | "Company" / next line "Fisher Scientific Company" | Missing (bare label) | Correct: Fisher Scientific Company |
| Product identifier | "Cat No. : A18-1; A18-4; …" (list across 9 lines) | Missing ("Cat No." not recognized) | Correct: full catalog list, which includes A18-4 |
| Revision date | "Revision Date 18-Dec-2025" (pp. 1–10 header, p. 10) | Correct: 2025-12-18 | Correct: 2025-12-18 |
| Creation / print dates | "Creation Date 28-Apr-2009", "Print Date 18-Dec-2025" | Correctly not used | Correctly not used |
| Version | "Revision Number 9" | Missing | Correct: 9 |
| Jurisdiction (indicator) | "created pursuant to … US OSHA Hazard Communication Standard 2024" | Conflicting (Section 15 mentions EU REACH 1907/2006) | US (OSHA HCS), from the stated basis, marked not verified |
| Language (indicator) | English | en (not verified) | en (not verified) |
| CAS (informational) | 67-64-1 | Correct | Correct |

**Summary:**

- First run: 3 correct (revision date, CAS, language), 4 missing, 1 conflicting,
  0 incorrect.
- After fixes: all fields above correct.
- One intermediate fix briefly produced an incorrect supplier value ("Company",
  the label itself). It was caught by checking against the PDF and fixed before
  commit.

**Sections:** boundaries checked by hand against the page text.

| Section | Pages | Result |
|---|---|---|
| 2 Hazard(s) identification | 1–2 | Correct start/end; running header and footer excluded |
| 3 Composition | 2–3 | Correct; both content lines kept across the page break, header/footer excluded |
| 8 Exposure controls | 4 | Correct start/end |
| 14 Transport | 7–8 | Correct; DOT, TDG, IATA and IMDG/IMO blocks included, ends before Section 15 |
| 15 Regulatory | 8–10 | Correct; ends before Section 16 |

All 16 section headings were located. No extraction warnings remained after the
fixes.

**Workflow on this document** (scratch data directory, fictional code
`REAL-DEMO-001`):

1. The only candidate suggested was REAL-DEMO-001 (identifier, supplier and
   name matched; CAS shown as informational only).
2. After human confirmation it was classified as **first document on file**.
3. The baseline was designated explicitly.
4. Receiving the same file again was recorded as an **exact duplicate**,
   inheriting the confirmed association.

Every step was recorded in the activity history.

**Regression tests:** `tests/test_real_layout_regressions.py` reproduces the
failing layout patterns using short label-line excerpts. The PDF is not in the
repository.

**What one document does not show:**

- extraction accuracy on other suppliers' layouts
- correct comparison results on real revisions
- edition checks between two real documents

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
  - A running header is recognized only if it repeats on at least half the
    pages (minimum two). A header that appears once, such as in a two-page
    SDS with no header on page 1, stays in the section text. A test pins this
    current behavior: `test_known_limitation_single_occurrence_header_stays_in_section_text`.
  - A product identifier can be a whole catalog-number list (as in the Fisher
    SDS). Matching checks whether any listed number equals the register's
    identifier.
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
