"""Section comparison for SDS Sections 2, 3, 8, 14 and 15.

Comparison is text-based. A detected text change is not a judgment about
hazard severity, regulatory applicability or compliance. Missing or failed
extraction is never reported as "no change".
"""

from __future__ import annotations

import difflib

from .extraction import TEXT_OK

COMPARED_SECTIONS = {
    2: "Hazard identification",
    3: "Composition/information on ingredients",
    8: "Exposure controls/personal protection",
    14: "Transport information",
    15: "Regulatory information",
}
OUT_OF_SCOPE = [n for n in range(1, 17) if n not in COMPARED_SECTIONS]

CHANGED = "compared_changes_detected"
UNCHANGED = "compared_no_text_changes_detected"
NOT_FOUND = "section_not_found"
EXTRACTION_FAILED = "extraction_failed"
UNAVAILABLE = "comparison_unavailable"

STATUS_LABELS = {
    CHANGED: "Compared: changes detected",
    UNCHANGED: "Compared: no text changes detected",
    NOT_FOUND: "Section not found",
    EXTRACTION_FAILED: "Extraction failed",
    UNAVAILABLE: "Comparison unavailable",
}


def _tokens(text: str) -> list[str]:
    # Conservative normalization: whitespace and line breaks only. Case,
    # punctuation, numbers, units, negations and identifiers are preserved.
    return text.split()


def _section(doc, n):
    return (doc.get("sections") or {}).get(str(n)) or (doc.get("sections") or {}).get(n)


def compare_documents(baseline: dict, incoming: dict, unavailable_reason: str | None = None):
    """Compare supported sections of two extracted documents.

    `baseline` and `incoming` are dicts with keys text_status and sections
    (as stored). Returns a JSON-serializable comparison record.
    """
    results = {}
    for n, title in COMPARED_SECTIONS.items():
        results[str(n)] = _compare_section(n, title, baseline, incoming, unavailable_reason)
    changed = [n for n, r in results.items() if r["status"] == CHANGED]
    unchanged = [n for n, r in results.items() if r["status"] == UNCHANGED]
    not_compared = [n for n, r in results.items() if r["status"] not in (CHANGED, UNCHANGED)]
    return {
        "sections": results,
        "changed": changed,
        "unchanged": unchanged,
        "not_compared": not_compared,
        "out_of_scope": OUT_OF_SCOPE,
        "summary": summarize(changed, unchanged, not_compared, results, unavailable_reason),
    }


def _compare_section(n, title, baseline, incoming, unavailable_reason):
    rec = {"title": title, "status": None, "note": "", "old_text": None, "new_text": None,
           "old_pages": None, "new_pages": None, "changes": []}
    if unavailable_reason:
        rec.update(status=UNAVAILABLE, note=unavailable_reason)
        return rec
    problems = []
    for label, doc in (("baseline", baseline), ("incoming", incoming)):
        if doc.get("text_status") != TEXT_OK:
            problems.append((EXTRACTION_FAILED, f"no usable text extracted from {label} document"))
    if problems:
        rec.update(status=EXTRACTION_FAILED, note="; ".join(p[1] for p in problems))
        return rec
    old, new = _section(baseline, n), _section(incoming, n)
    if old:
        rec["old_text"], rec["old_pages"] = old.get("text"), [old["start_page"], old["end_page"]]
    if new:
        rec["new_text"], rec["new_pages"] = new.get("text"), [new["start_page"], new["end_page"]]
    missing = [label for label, s in (("baseline", old), ("incoming", new)) if not s]
    if missing:
        rec.update(status=NOT_FOUND,
                   note=f"Section {n} heading not located in {' and '.join(missing)} document")
        return rec
    empty = [label for label, s in (("baseline", old), ("incoming", new))
             if not (s.get("text") or "").strip()]
    if empty:
        rec.update(status=EXTRACTION_FAILED,
                   note=f"Section {n} heading found but no text extracted in "
                        f"{' and '.join(empty)} document")
        return rec
    a, b = _tokens(old["text"]), _tokens(new["text"])
    if a == b:
        rec.update(status=UNCHANGED,
                   note="No text changes detected after whitespace normalization")
        return rec
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        rec["changes"].append({
            "op": op,
            "removed": " ".join(a[i1:i2]),
            "added": " ".join(b[j1:j2]),
            "context_before": " ".join(a[max(0, i1 - 6):i1]),
            "context_after": " ".join(a[i2:i2 + 6]),
        })
    rec.update(status=CHANGED, note=f"{len(rec['changes'])} changed passage(s)")
    return rec


def _join(nums):
    nums = [str(x) for x in nums]
    if len(nums) <= 1:
        return "".join(nums)
    return ", ".join(nums[:-1]) + " and " + nums[-1]


def summarize(changed, unchanged, not_compared, results, unavailable_reason):
    parts = []
    if unavailable_reason:
        return (f"Comparison unavailable: {unavailable_reason}. Human review required.")
    if changed:
        parts.append(f"Text changes detected in Section{'s' if len(changed) > 1 else ''} "
                     f"{_join(changed)}.")
    if unchanged:
        parts.append(f"No text changes detected in Section{'s' if len(unchanged) > 1 else ''} "
                     f"{_join(unchanged)}.")
    if not_compared:
        details = "; ".join(f"Section {n}: {STATUS_LABELS[results[n]['status']].lower()}"
                            for n in not_compared)
        parts.append(f"Not compared - {details}.")
    parts.append("Sections 1, 4-7, 9-13 and 16 are outside the comparison scope.")
    parts.append("Human review required.")
    return " ".join(parts)
