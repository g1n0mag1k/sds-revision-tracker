# SDS Revision Tracker

**SDS revision intake and review-coordination tool — an independent portfolio
work sample inspired by the SDS revision coordination responsibility in Techmer
PM's Product Development Coordinator posting.**

> Independent portfolio demonstration. Supports document review; does not make
> safety or regulatory determinations. This is not a Techmer PM internal system
> or an endorsed product.

It records incoming supplier Safety Data Sheets and helps a person do several things:

- check identifying details against a small material register
- confirm which material each document belongs to
- see what text changed in hazard-relevant sections compared with an explicitly
  selected baseline SDS
- hand a draft notification to a human reviewer

Every received document and workflow action is preserved in an application
activity history.

## Why this exists

Under OSHA's Hazard Communication Standard (29 CFR 1910.1200), suppliers must
update an SDS within three months of learning of significant new hazard
information — but nothing requires them to notify customers that a revision
happened. Someone downstream has to catch every change by hand, usually by
comparing a new PDF against whatever's on file. That review step is manual,
repetitive, and exactly the kind of workflow this tool targets — not
raw-material code approval, ERP entry, or anything that depends on internal
company systems.

This tool doesn't replace that review. It removes the busywork around it:
finding what changed, so a person can focus on judging whether it matters.

## What it does

- **Intake**: records every upload as a receipt, duplicates included. Identical
  file bytes are stored once, under an application-controlled path, and never
  overwritten.
- **Extract (attempted)**: uses pdfplumber to look for product name, supplier,
  product identifier, revision/preparation date and version in Section 1,
  Section 16 and page headers/footers.
  - Each field is reported as found, missing, ambiguous or conflicting, with
    its evidence text and page.
  - Print and retrieval dates are ignored. Ambiguous dates such as `03/04/2025`
    are not guessed.
  - Image-only or unreadable PDFs are flagged for manual review. There is no OCR.
- **Match**: suggests register materials by product identifier, supplier and
  name.
  - CAS numbers are shown for information but never used to establish product
    identity.
  - A person must confirm the association. An unmatched document is **not**
    treated as a new material automatically.
- **Classify**, against the material's explicitly selected baseline, with a
  stated reason. Outcomes:
  - first document on file
  - exact duplicate
  - newer dated revision
  - older dated document
  - same date with changed content
  - undetermined / manual review
- **Compare**: Sections 2, 3, 8, 14 and 15 only, as text.
  - Each section is reported as changes detected, no text changes detected,
    section not found, extraction failed, or comparison unavailable.
  - Missing or failed extraction is never reported as "no change".
- **Draft**: generates a notification draft for "Regulatory support —
  demonstration recipient". There is no sending capability.
- **Review acknowledgment**: pending → in progress → completed, with a free-text
  reviewer label. This is a simulated acknowledgment, not approval.
- **Activity history**: a readable timeline of receipts, duplicates, extraction
  outcomes, confirmations, classifications, comparisons, drafts, reviews and
  baseline designations.

The baseline is never replaced automatically. It changes only through an
explicit, logged action. Each receipt keeps the baseline and comparison used
at the time it was classified.

## What it deliberately does not do

- No ERP integration. The register is seeded by an explicit command; CSV/Excel
  import is not in the first release.
- No auto-approval or regulatory decisions. Every result goes to a person; the
  tool surfaces text changes and does not judge hazard severity, compliance,
  transport requirements or permission to use a material.
- No cloud dependency. It runs locally, makes no LLM/API calls, has no runtime
  downloads, and has Streamlit usage statistics disabled.
- No OCR, email sending/ingestion, supplier monitoring or authentication.
- The activity history is application version tracking, **not** tamper-proof or
  certified compliance logging.

## Setup

Requires Python 3.10+ (developed on 3.13).

```bash
./scripts/bootstrap.sh
```

The bootstrap script creates `.venv/` and installs the pinned requirements. It
does not create or reset data, download documents, or start a server.

```bash
.venv/bin/python -m sdstracker init-db
```

`init-db` creates `data/tracker.db` if it is missing and never resets an
existing database.

```bash
.venv/bin/python -m sdstracker demo-data
```

`demo-data` is optional. It seeds a **synthetic** register (fictional codes
`DEMO-RM-001` and `DEMO-RM-002`) and stores a synthetic baseline SDS. It also
writes further synthetic PDFs to upload to `data/synthetic_demo/`. It does
nothing if materials already exist, and it needs the development dependency
`fpdf2`.

## Run

```bash
.venv/bin/streamlit run app.py
```

Then open http://localhost:8501. Enter a name/label in the sidebar; it is
recorded in the activity history and is not an authenticated identity.

Other explicit commands:

```bash
.venv/bin/python -m sdstracker add-material --code DEMO-RM-101 --name "Product" --supplier "Supplier" --product-id "123"
```

```bash
.venv/bin/python -m sdstracker receive path/to/file.pdf --actor "Your name" --source-url URL --retrieved-on 2026-11-05
```

The upload limit is 20 MB per PDF (`.streamlit/config.toml` and
`sdstracker/config.py`).

## Test

```bash
.venv/bin/pytest -q
```

All automated tests use **synthetic** PDFs generated at test time. They are
not real-document results. See [docs/results-and-limitations.md](docs/results-and-limitations.md).

## Documentation

- [docs/project-spec.md](docs/project-spec.md): approved specification
- [docs/results-and-limitations.md](docs/results-and-limitations.md): test
  results, real-document status, limitations
- [docs/demo-script.md](docs/demo-script.md): three-minute demo script
- [docs/job-duty-mapping.md](docs/job-duty-mapping.md): feature-to-job-duty
  mapping
- [samples/real/README.md](samples/real/README.md): how real SDS PDFs are
  sourced and recorded (kept out of Git)

## Status

In development. Built as a demonstration project and not in production use.
One genuine supplier SDS (Fisher Scientific, Acetone) has been used as a
parser test. Revision-pair validation on a genuine old/new pair is **not yet
run**. See the results report.

## License

*(license not yet decided)*
