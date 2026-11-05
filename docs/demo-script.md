# Three-minute demo script (hiring manager)

**Before the demo:**

```bash
.venv/bin/python -m sdstracker init-db
```

```bash
.venv/bin/python -m sdstracker demo-data
```

```bash
.venv/bin/streamlit run app.py
```

Enter "Demo Coordinator" in the sidebar.

> Say up front: "This is an independent work sample. The documents in this run
> are synthetic test documents, clearly stamped as not real SDSs, and the
> material codes are fictional."

**0:00–0:20 — Framing.** Point to the persistent notice.
"Suppliers revise SDSs without necessarily telling customers. This tool
supports the person who has to catch those revisions. It finds and lays out
what changed; it doesn't decide whether a change matters."

**0:20–0:45 — Materials & documents.** Open DEMO-RM-001.
"Here's the register entry and its **explicitly selected baseline** SDS. The
baseline only changes when someone deliberately changes it, and that is logged."

**0:45–1:20 — Intake.** Upload `data/synthetic_demo/SYNTHETIC_resin-A_v2_2025-06-15.pdf`.
"Every upload becomes a receipt. These are the extracted identifying fields,
each with a status and the evidence line and page, so I can check them against
the PDF. The tool suggests a material, but I have to confirm it." Confirm
DEMO-RM-001.

**1:20–2:00 — Comparison.** Open "Comparison, draft & review".
- "It's classified as a *newer dated revision*. Here's the reason, and here's
  the baseline it was compared against."
- "Text changes were detected in Sections 2 and 8. Here are the removed and
  added text and the source text side by side. The other sections are stated
  as outside the comparison scope."

**2:00–2:30 — Handoff.** Generate the draft.
"This is a **draft** for regulatory support. Nothing is sent." Record the review
as completed with a reviewer label: "That's an acknowledgment, not an approval."

**2:30–2:50 — Edge cases.**
- Upload the same v2 file again: "Exact duplicate. The receipt is still
  recorded."
- Upload `SYNTHETIC_image-only-scan.pdf`: "No text layer, so it's flagged for
  manual review rather than reported as unchanged."

**2:50–3:00 — Activity history.**
"Every step is in the activity history, with actor, reason and before/after
values. It's version tracking, not certified compliance logging."
