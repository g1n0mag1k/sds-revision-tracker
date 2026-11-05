# SDS Revision Tracker

**SDS revision intake and review-coordination tool, inspired by the Product Development Coordinator role at Techmer PM.**

Tracks incoming supplier Safety Data Sheets, flags potential revisions against what's on file, highlights section-level changes, and drafts notifications for human regulatory review. Every document and action is preserved and logged.

## Why this exists

Under OSHA's Hazard Communication Standard (29 CFR 1910.1200), suppliers must update an SDS within three months of learning of significant new hazard information — but nothing requires them to notify customers that a revision happened. Someone downstream has to catch every change by hand, usually by comparing a new PDF against whatever's on file. That review step is manual, repetitive, and exactly the kind of workflow this tool targets — not raw-material code approval, ERP entry, or anything that depends on Techmer's internal systems.

This tool doesn't replace that review. It removes the busywork around it: finding what changed, so a person can focus on judging whether it matters.

## What it does

- **Intake** — accepts incoming supplier SDS PDFs and extracts product name, supplier, CAS numbers, and revision date (Section 1, Section 16, headers/footers)
- **Match** — compares each document against a raw-material register to detect: new material, duplicate, newer revision, or a stale resend of an older version
- **Diff** — for true revisions, highlights what changed in the hazard-relevant sections (classification, composition, exposure limits, transport, regulatory info)
- **Notify** — drafts a pre-filled notification for regulatory review, summarizing what changed and why it needs a look
- **Preserve & log** — keeps every source document and records intake, review, and notification activity with timestamps, so there's a full audit trail

## What it deliberately does not do

- No ERP integration — reads from an exported register (CSV/Excel), so it needs no IT approval or system access
- No auto-approval — every flagged revision goes to a human for regulatory judgment; the tool surfaces, it doesn't decide
- No cloud dependency — runs locally against documents you provide

## Status

In development — built as a demonstration project, not yet in production use.

## License

*(add license)*
