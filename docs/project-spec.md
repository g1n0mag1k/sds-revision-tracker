# SDS Revision Tracker — Approved Project Specification

This is the authoritative specification approved for the first release.
It takes precedence over earlier README text and earlier plans. The
"Approval clarifications" at the end were added when the plan was approved.

## Purpose

Build a small, working, locally runnable portfolio application inspired by
the SDS revision coordination responsibility in Techmer PM's Product
Development Coordinator posting.

This is an independent job-application work sample, not a Techmer PM
internal system or an endorsed product.

It should demonstrate:

- Accurate document records.
- Recognition of missing or conflicting information.
- Revision comparison.
- Clear handoffs to a human reviewer.
- Traceable activity history.
- Honest limits on automation.

Do not build an enterprise compliance platform.

## Corrections to the earlier plan

1. Use Streamlit for the interface, not Flask.
2. Use pdfplumber for extraction, not pypdf, unless a concrete compatibility
   problem is identified and approved.
3. No CSV import in the first release. Seed a small register through a
   documented explicit demo command.
4. An unmatched PDF is NOT automatically a new material.
5. CAS overlap is NOT sufficient to establish product identity.
6. Require human confirmation before linking a non-duplicate document to a
   material.
7. Preserve every receipt, including duplicate receipts. A unique document
   hash must not eliminate receipt history.
8. Keep review acknowledgment separate from notification-draft status.
9. Do not automatically replace the baseline/reference SDS when a newer
   document arrives.
10. Do not make archived-document availability or successful supplier access
    sound guaranteed.
11. Leave the license undecided for now.
12. Do not use paid Firecrawl or another paid service without approval.

## First-release workflow

The main demonstration must show:

1. A stored baseline SDS for a material.
2. Intake of another SDS.
3. Extracted identifying metadata with visible evidence.
4. Human confirmation of material association.
5. Document classification with a reason.
6. Comparison against an explicitly identified baseline.
7. A notification draft for human review.
8. A review acknowledgment.
9. A readable activity history.

Also show an exact duplicate receipt and one manual-review case.
Prioritize completing this workflow over optional features.

## Stack and local operation

Python, Streamlit, SQLite through the standard library, pdfplumber, pytest,
standard-library hashing and difflib. RapidFuzz optional (omitted). A
PDF-generation library may be used as a development-only dependency for
clearly synthetic test fixtures.

Use a virtual environment and requirements files; no other
dependency-management system.

The finished app must run locally; work offline after dependencies and
documents are installed; make no LLM/API calls; require no cloud services;
have no telemetry or runtime downloads. No OCR in the first release.

Use application-controlled file paths, a documented upload-size limit, and
visible handling of malformed/unreadable PDFs.

## Data model

Preserve these distinct concepts with the simplest schema:

- **Material**: internal code; product name; supplier; optional product
  identifier; optional multiple CAS numbers; explicitly selected baseline
  document, if applicable.
- **Stored document**: original filename; managed filepath; SHA-256 hash;
  source URL/retrieval date when known; extracted metadata; original evidence
  strings; extraction warnings; confirmed material association.
- **Intake/receipt**: a record for every upload/receipt; timestamp; actor;
  document reference; match status; classification and reason; comparison
  baseline.
- **Review acknowledgment**: pending/in-progress/completed; reviewer label;
  comments; timestamps.
- **Notification draft**: subject/body; intended recipient label; generation
  timestamp; associated intake/comparison.
- **Activity event**: timestamp; user/system actor; action; affected record;
  relevant previous/new values; reason where applicable.

Review completion is a simulated acknowledgment, not regulatory approval.
Entered reviewer names are not authenticated identities. Retain original
PDFs without overwriting them. Identical file bytes may be stored once, with
multiple receipt records.

## Metadata extraction

Attempt to extract product name, supplier, product identifier,
preparation/revision date, and version number if present. Inspect Section 1,
Section 16, and headers/footers as appropriate.

For important fields: preserve raw extracted text; store normalized values
separately; show page/evidence text where practical; report found, missing,
ambiguous, or conflicting.

Do not confuse printing, receipt, or retrieval dates with revision dates. Do
not guess ambiguous date formats. If manual correction is supported,
preserve the original extraction and record the correction and reason.
Unreadable/image-only PDFs must visibly require manual review. Do not use an
"extraction complete" label that implies the entire SDS has been understood.

## Matching and classification

Use hashes for exact duplicate detection. Suggest material candidates using
product identifier, supplier, and name. Do not use CAS as a unique product
identifier. Require confirmation for a non-duplicate document's material
association. Keep matching, extraction, classification, and review statuses
separate.

Required classification outcomes: first document on file; exact duplicate;
newer dated revision; older dated document; same date with changed content;
undetermined/manual review.

Different hashes alone do not prove a revision. If hashes differ but
extracted text is unchanged, report that clearly. Do not assume version
strings can always be ordered. Conflicting identity, dates, language, or
jurisdiction must not be forced into a confident revision classification.
Show the classification reason and comparison baseline. Newly received
documents do not automatically replace the selected baseline document.

## Section comparison

Compare Section 2 (hazard identification), Section 3
(composition/information on ingredients), Section 8 (exposure
controls/personal protection), Section 14 (transport information), and
Section 15 (regulatory information). State clearly that other sections are
outside the comparison scope.

Show old/new source text, added/removed text, page references where
practical, and section comparison status. Use conservative formatting
normalization; preserve meaningful numbers, units, negations, chemical
identifiers, and hazard statements.

Distinguish: compared: changes detected; compared: no text changes
detected; section not found; extraction failed; comparison unavailable.
Missing or failed extraction must never mean "no change."

Use deterministic summaries, such as "Text changes detected in Sections 2
and 8. Human review required." Do not infer hazard severity, regulatory
applicability, compliance, permission to use a material, or legal transport
conclusions. Keep original PDFs available for verification.

## Notification and review

Generate a draft addressed to "Regulatory support — demonstration
recipient", including: material code; product/supplier; baseline and
incoming documents; old/new dates and any uncertainty; classification and
reason; supported sections with changes; extraction/comparison limitations;
references to original documents; request for human review.

No sending capability. "Draft generated" must not be logged as "sent" or
"notified." "Review completed" must not be logged as "approved."

## Activity history

Record events as the workflow runs: receipt; duplicate recognition;
extraction outcome; match confirmation; manual correction; classification;
comparison; draft generation; review acknowledgment; explicit baseline
change, if implemented. Provide a readable timeline. Describe this as
application activity history/version tracking, not tamper-proof or certified
compliance logging. No normal UI for editing past activity events.

## Real documents

For a real demonstration use genuine old/new SDS revisions of the same
product and supplier, same language/jurisdiction where possible, actual
product/supplier identities, and fictional internal material codes, clearly
labeled. Do not modify a real SDS to manufacture a revision. Do not claim
unrelated products form a valid revision pair. Do not assume web.archive.org
contains a suitable historical copy. Keep real PDFs out of Git initially;
commit provenance instructions and a manifest instead. If a genuine pair is
unavailable, report the blocker, request a decision, and do not misrepresent
synthetic tests as the real-document demonstration. A homepage header
response is not proof that a specific PDF is available.

## Interface

A simple Streamlit interface with: (1) materials/documents; (2) intake and
material confirmation; (3) comparison, draft, and review; (4) activity
history. Make obvious what arrived, which material it belongs to, which
baseline was used, what text changed, what is uncertain, and what a human
should do next.

Persistent notice: "Independent portfolio demonstration. Supports document
review; does not make safety or regulatory determinations."

No decorative charts or age/expiration dashboard.

## Tests

Cover: first document; duplicate received twice with two receipt records;
newer revision; older document; same date with changed content; different
hash with unchanged extracted text; missing/ambiguous date; unconfirmed or
ambiguous material; unreadable PDF; missing section; extraction failure not
reported as no change; draft not recorded as sent; review not recorded as
approval; original PDF preservation; required activity events; no automatic
baseline replacement. Keep synthetic fixtures conspicuously separate from
real-document results. Report actual tests run and failures.

## Setup and documentation

Create `scripts/bootstrap.sh`; an explicit init-db command that does not
reset existing data; an explicit demo-data command; `.gitignore` for
environments, databases, uploads, real PDFs, caches, and secrets; a README
with setup/run/test instructions; this specification; a short
results/limitations report; a three-minute hiring-manager demo script; a
feature-to-job-duty mapping.

Setup must not automatically download SDSs, reset databases, or start a
server. Use explicit `.venv` executable paths. Do not invent extraction
accuracy or time-savings claims. Report real-document results separately
from generated-fixture tests.

## Out of scope

Flask or a separate web API; CSV/Excel import in the first release; ERP
integration; email sending/ingestion; supplier monitoring; OCR; LLM
extraction; formulations; work orders; TDS generation; cloud deployment;
enterprise authentication; automated regulatory decisions.

## Approval clarifications

- Manual field correction is excluded from the first release.
- Streamlit reruns must not create duplicate receipt, draft, review, or
  activity records; records are created only for deliberate submitted
  actions. Two deliberate uploads of an identical PDF still produce two
  receipt records.
- A duplicate may inherit a material association only if the stored document
  already has a confirmed association; otherwise it remains unconfirmed.
- Missing or unreadable text must never produce "no changes detected."
  Whole-document extraction success does not establish that every supported
  section was extracted correctly.
- Each receipt's classification and comparison retain the baseline used at
  that time; a later baseline change does not rewrite historical results.
- Unrelated language/jurisdiction editions are not compared as a revision
  pair. If those attributes cannot be established, the limitation is shown
  rather than implying they were verified.
- A user can designate the first confirmed document as the baseline
  explicitly, with an activity event. No automatic baseline replacement.
- The real-document acceptance criterion stays marked "not yet run" until
  genuine PDFs have been tested.
