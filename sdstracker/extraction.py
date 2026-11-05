"""Text extraction from SDS PDFs with pdfplumber (no OCR).

Extraction is a best-effort attempt to locate specific fields and section
text. It does not mean the SDS has been understood. Every field keeps the
raw evidence text and page so a person can verify it against the PDF.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

# Field statuses
FOUND, MISSING, AMBIGUOUS, CONFLICTING = "found", "missing", "ambiguous", "conflicting"

# Document text statuses
TEXT_OK, NO_TEXT, FAILED = "text", "no_text", "failed"

MIN_TEXT_CHARS = 40

SECTION_KEYWORDS = {
    1: ("identification",),
    2: ("hazard",),
    3: ("composition", "ingredient"),
    4: ("first aid", "first-aid"),
    5: ("fire",),
    6: ("accidental release",),
    7: ("handling", "storage"),
    8: ("exposure", "personal protection"),
    9: ("physical",),
    10: ("stability", "reactivity"),
    11: ("toxicolog",),
    12: ("ecolog",),
    13: ("disposal",),
    14: ("transport",),
    15: ("regulatory",),
    16: ("other information",),
}

SECTION_RE = re.compile(r"^\s*(?:SECTION|Section)\s+(\d{1,2})\b\s*[:.\-]?\s*(.*)$")
NUMBERED_RE = re.compile(r"^\s*(\d{1,2})\.\s+([A-Za-z].*)$")
PAGE_NUMBER_RE = re.compile(r"^\s*page\s+\d+\s*(of|/)\s*\d+\s*$", re.I)

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# Labels that identify a revision date (preferred) or a preparation/issue date.
REVISION_LABEL_RE = re.compile(
    r"(revision\s+date|date\s+of\s+revision|revised\s+on|last\s+revised|revised|"
    r"date\s+revised)\s*[:\-]?\s*(.+)$", re.I)
PREPARATION_LABEL_RE = re.compile(
    r"(preparation\s+date|date\s+of\s+preparation|date\s+prepared|issue\s+date|"
    r"date\s+of\s+issue|version\s+date)\s*[:\-]?\s*(.+)$", re.I)
# Lines mentioning these are never treated as the document's revision date.
EXCLUDED_DATE_CONTEXT_RE = re.compile(
    r"print|supersed|previous|replaces|retriev|download|received|expir", re.I)

VERSION_RE = re.compile(
    r"\b(?:version|rev\.)\s*(?:no\.?|number|#)?\s*[:\-]?\s*(\d[\w.\-]*)", re.I)

PRODUCT_NAME_RE = re.compile(
    r"^\s*(?:product\s+name|trade\s+name|name\s+of\s+product)\s*[:\-]\s*(.+)$", re.I)
PRODUCT_ID_RE = re.compile(
    r"^\s*(?:product\s+(?:number|code|no\.?)|catalog(?:ue)?\s+(?:number|no\.?)|"
    r"item\s+(?:number|no\.?)|material\s+(?:number|no\.?)|article\s+(?:number|no\.?))"
    r"\s*[:\-]\s*(.+)$", re.I)
SUPPLIER_RE = re.compile(
    r"^\s*(?:supplier|manufacturer(?:\s*/\s*supplier)?|company(?:\s+name)?|"
    r"details\s+of\s+the\s+supplier[^:]*)\s*[:\-]\s*(.*)$", re.I)

CAS_RE = re.compile(r"\b(\d{2,7})-(\d{2})-(\d)\b")

LANGUAGE_MARKERS = {
    "en": ("hazards identification", "hazard identification", "composition/information",
           "first-aid measures", "first aid measures", "transport information",
           "regulatory information"),
    "fr": ("identification des dangers", "rubrique"),
    "de": ("mögliche gefahren", "abschnitt"),
    "es": ("identificación de los peligros", "sección"),
}
JURISDICTION_MARKERS = {
    "US (OSHA HCS)": ("29 cfr 1910.1200", "osha hazard communication", "hazcom 2012"),
    "EU/UK (REACH/CLP)": ("1907/2006", "1272/2008", "regulation (ec)", "uk reach"),
    "Canada (WHMIS/HPR)": ("whmis", "hazardous products regulations"),
}


# ---------------------------------------------------------------- dates

def parse_date(raw: str) -> dict:
    """Parse a date string without guessing ambiguous formats.

    Returns {"status": found|ambiguous|missing, "value": ISO date or None, "note": str}.
    """
    s = raw.strip()
    m = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", s)
    if m:
        return _mk(int(m[1]), int(m[2]), int(m[3]), m[0])
    m = re.search(r"\b(\d{1,2})[\s\-./]+([A-Za-z]{3,9})\.?[\s\-./,]+(\d{4})\b", s)
    if m and m[2][:3].lower() in MONTHS:
        return _mk(int(m[3]), MONTHS[m[2][:3].lower()], int(m[1]), m[0])
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b", s)
    if m and m[1][:3].lower() in MONTHS:
        return _mk(int(m[3]), MONTHS[m[1][:3].lower()], int(m[2]), m[0])
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a > 12 and b <= 12:
            return _mk(y, b, a, m[0], "day-first (day > 12)")
        if b > 12 and a <= 12:
            return _mk(y, a, b, m[0], "month-first (day > 12)")
        if a == b:
            return _mk(y, a, b, m[0])
        return {"status": AMBIGUOUS, "value": None, "matched": m[0],
                "note": f"'{m[0]}' could be day-first or month-first; not guessed"}
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2})\b", s)
    if m:
        return {"status": AMBIGUOUS, "value": None, "matched": m[0],
                "note": f"'{m[0]}' has a two-digit year; not guessed"}
    return {"status": MISSING, "value": None, "matched": None,
            "note": "no recognizable date in labeled text"}


def _mk(y, mo, d, matched, note=""):
    try:
        return {"status": FOUND, "value": date(y, mo, d).isoformat(),
                "matched": matched, "note": note}
    except ValueError:
        return {"status": AMBIGUOUS, "value": None, "matched": matched,
                "note": f"'{matched}' is not a valid calendar date"}


# ---------------------------------------------------------------- helpers

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_name(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    stop = {"inc", "llc", "ltd", "corp", "corporation", "co", "company", "gmbh",
            "sa", "ag", "plc", "limited", "the"}
    return " ".join(t for t in s.split() if t not in stop)


def valid_cas(cas: str) -> bool:
    digits = cas.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    return total % 10 == check


def _section_heading(line: str):
    m = SECTION_RE.match(line)
    if m:
        n = int(m[1])
        if 1 <= n <= 16:
            return n, normalize_space(m[2])
    m = NUMBERED_RE.match(line)
    if m:
        n, title = int(m[1]), m[2].lower()
        if 1 <= n <= 16 and any(k in title for k in SECTION_KEYWORDS[n]) and len(title) < 90:
            return n, normalize_space(m[2])
    return None


# ---------------------------------------------------------------- main API

def extract_pdf(path) -> dict:
    """Extract text, sections and identifying fields from a PDF file."""
    result = {"text_status": FAILED, "page_count": None, "fields": {},
              "sections": {}, "warnings": [], "full_text": ""}
    try:
        with open(path, "rb") as fh:
            if fh.read(5) != b"%PDF-":
                result["warnings"].append("File does not begin with a PDF header (%PDF-).")
        import pdfplumber
        pages = []
        with pdfplumber.open(path) as pdf:
            result["page_count"] = len(pdf.pages)
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
    except Exception as exc:  # malformed / unreadable PDF
        result["warnings"].append(
            f"PDF could not be read ({type(exc).__name__}). Manual review required.")
        result["fields"] = _empty_fields("PDF could not be read")
        return result
    return extract_from_pages(pages, result)


def extract_from_pages(pages: list[str], result: dict | None = None) -> dict:
    result = result or {"text_status": FAILED, "page_count": len(pages), "fields": {},
                        "sections": {}, "warnings": [], "full_text": ""}
    result["page_count"] = result.get("page_count") or len(pages)
    total_chars = sum(len(p.strip()) for p in pages)
    if total_chars < MIN_TEXT_CHARS:
        result["text_status"] = NO_TEXT
        result["warnings"].append(
            "No usable text layer found (possibly image-only or blank). OCR is not "
            "supported. Manual review required.")
        result["fields"] = _empty_fields("no text layer")
        return result
    result["text_status"] = TEXT_OK
    # Fingerprint of ALL extracted text (whitespace-normalized), used to report
    # "file bytes differ but extracted text is identical".
    import hashlib
    result["text_fingerprint"] = hashlib.sha256(
        normalize_space(" ".join(pages)).encode("utf-8")).hexdigest()

    page_lines = [[ln for ln in p.splitlines()] for p in pages]
    # Header/footer candidates: first and last 3 non-empty lines of each page.
    hf_lines = []
    for i, lines in enumerate(page_lines, 1):
        non_empty = [ln for ln in lines if ln.strip()]
        for ln in non_empty[:3] + non_empty[-3:]:
            hf_lines.append((i, ln))
    # Lines that repeat on at least half of the pages (min 2) are treated as
    # running headers/footers and excluded from section text.
    repeated = set()
    if len(pages) >= 2:
        counts = Counter()
        for lines in page_lines:
            for ln in {normalize_space(x) for x in lines if x.strip()}:
                counts[ln] += 1
        threshold = max(2, (len(pages) + 1) // 2)
        repeated = {ln for ln, c in counts.items() if c >= threshold}

    sections, warnings = _split_sections(page_lines, repeated)
    result["warnings"].extend(warnings)
    result["sections"] = sections
    body_lines = [(i, ln) for i, lines in enumerate(page_lines, 1) for ln in lines
                  if ln.strip() and normalize_space(ln) not in repeated
                  and not PAGE_NUMBER_RE.match(ln)]
    result["full_text"] = "\n".join(normalize_space(ln) for _, ln in body_lines)

    scope = []
    for n in (1, 16):
        if n in sections:
            scope.extend((p, ln) for p, ln in sections[n]["lines"])
    if not scope:
        result["warnings"].append(
            "Sections 1 and 16 were not located; identifying fields were searched "
            "on the first and last pages instead.")
        scope = [(1, ln) for ln in page_lines[0]] + \
                [(len(page_lines), ln) for ln in page_lines[-1]]
    seen = set()
    search = []
    for p, ln in scope + hf_lines:
        key = (p, normalize_space(ln))
        if ln.strip() and key not in seen:
            seen.add(key)
            search.append((p, ln))

    f = {}
    f["product_name"] = _labeled_field(search, PRODUCT_NAME_RE, "product name")
    f["product_identifier"] = _labeled_field(search, PRODUCT_ID_RE, "product identifier")
    f["supplier"] = _supplier_field(search)
    f["revision_date"] = _date_field(search)
    f["version"] = _version_field(search)
    f["language"] = _marker_field(result["full_text"], LANGUAGE_MARKERS, "language")
    f["jurisdiction"] = _marker_field(result["full_text"], JURISDICTION_MARKERS,
                                      "jurisdiction")
    f["cas_numbers"] = _cas_field(sections)
    result["fields"] = f
    for name in ("product_name", "supplier", "revision_date"):
        if f[name]["status"] != FOUND:
            result["warnings"].append(f"{name.replace('_', ' ').capitalize()}: "
                                      f"{f[name]['status']}.")
    # Drop internal line lists before storage (keep text + pages).
    for sec in sections.values():
        sec.pop("lines", None)
    return result


def _empty_fields(reason):
    names = ("product_name", "product_identifier", "supplier", "revision_date",
             "version", "language", "jurisdiction", "cas_numbers")
    return {n: {"status": MISSING, "value": None, "evidence": [], "note": reason}
            for n in names}


def _split_sections(page_lines, repeated):
    sections = {}
    warnings = []
    current = None
    last_n = 0
    for p, lines in enumerate(page_lines, 1):
        for ln in lines:
            if not ln.strip():
                continue
            norm = normalize_space(ln)
            if norm in repeated or PAGE_NUMBER_RE.match(ln):
                continue
            head = _section_heading(ln)
            if head:
                n, title = head
                if n in sections:
                    warnings.append(f"Section {n} heading appears more than once; "
                                    "the first occurrence was used.")
                elif n > last_n:
                    current = {"title": title, "heading": norm, "start_page": p,
                               "end_page": p, "lines": []}
                    sections[n] = current
                    last_n = n
                    continue
            if current is not None:
                current["lines"].append((p, ln))
                current["end_page"] = p
    for n, sec in sections.items():
        sec["text"] = "\n".join(normalize_space(ln) for _, ln in sec["lines"])
        sec["status"] = "found" if sec["text"].strip() else "heading_only"
    missing = [n for n in range(1, 17) if n not in sections]
    if missing:
        warnings.append("Section headings not located: " + ", ".join(map(str, missing)) + ".")
    return sections, warnings


def _value_after(search, idx, inline):
    if inline.strip():
        return inline.strip()
    # Value on the next non-empty line on the same page.
    p = search[idx][0]
    for q, ln in search[idx + 1: idx + 3]:
        if q == p and ln.strip():
            return ln.strip()
    return ""


def _labeled_field(search, regex, label):
    hits = []
    for i, (p, ln) in enumerate(search):
        m = regex.match(ln)
        if m:
            val = _value_after(search, i, m.group(1))
            if val:
                hits.append({"page": p, "text": normalize_space(ln), "raw": val})
    return _resolve(hits, label, key=lambda h: normalize_space(h["raw"]).lower())


def _supplier_field(search):
    hits = []
    for i, (p, ln) in enumerate(search):
        m = SUPPLIER_RE.match(ln)
        if m:
            val = _value_after(search, i, m.group(1))
            if val:
                hits.append({"page": p, "text": normalize_space(ln), "raw": val})
    return _resolve(hits, "supplier", key=lambda h: normalize_name(h["raw"]))


def _resolve(hits, label, key):
    if not hits:
        return {"status": MISSING, "value": None, "evidence": [],
                "note": f"no labeled {label} found"}
    values = {}
    for h in hits:
        h["normalized"] = key(h)
        values.setdefault(h["normalized"], h["raw"])
    if len(values) > 1:
        return {"status": CONFLICTING, "value": None, "evidence": hits,
                "note": f"{len(values)} different {label} values found"}
    return {"status": FOUND, "value": normalize_space(hits[0]["raw"]),
            "normalized": hits[0]["normalized"], "evidence": hits, "note": ""}


def _date_field(search):
    revision, preparation = [], []
    for p, ln in search:
        if EXCLUDED_DATE_CONTEXT_RE.search(ln):
            continue
        m = REVISION_LABEL_RE.search(ln)
        bucket = revision
        if not m:
            m = PREPARATION_LABEL_RE.search(ln)
            bucket = preparation
        if not m:
            continue
        parsed = parse_date(m.group(2))
        if parsed["status"] == MISSING:
            continue
        bucket.append({"page": p, "text": normalize_space(ln), "label": m.group(1),
                       "raw": parsed["matched"], "parsed": parsed})
    hits = revision or preparation
    kind = "revision" if revision else "preparation/issue"
    if not hits:
        return {"status": MISSING, "value": None, "evidence": [], "kind": None,
                "note": "no labeled revision or preparation date found "
                        "(print/retrieval dates are ignored)"}
    ambiguous = [h for h in hits if h["parsed"]["status"] == AMBIGUOUS]
    values = {h["parsed"]["value"] for h in hits if h["parsed"]["status"] == FOUND}
    if ambiguous:
        return {"status": AMBIGUOUS, "value": None, "evidence": hits, "kind": kind,
                "note": "; ".join(h["parsed"]["note"] for h in ambiguous)}
    if len(values) > 1:
        return {"status": CONFLICTING, "value": None, "evidence": hits, "kind": kind,
                "note": f"different {kind} dates found: " + ", ".join(sorted(values))}
    return {"status": FOUND, "value": values.pop(), "evidence": hits, "kind": kind,
            "note": f"labeled as {kind} date"}


def _version_field(search):
    hits = []
    for p, ln in search:
        if EXCLUDED_DATE_CONTEXT_RE.search(ln):
            continue
        for m in VERSION_RE.finditer(ln):
            hits.append({"page": p, "text": normalize_space(ln), "raw": m.group(1)})
    res = _resolve(hits, "version", key=lambda h: h["raw"].lower())
    res["note"] = (res["note"] + "; " if res["note"] else "") + \
        "version strings are recorded, not ordered"
    return res


def _marker_field(full_text, markers, label):
    low = full_text.lower()
    found = {}
    for value, terms in markers.items():
        hits = [t for t in terms if t in low]
        if hits:
            found[value] = hits
    if not found:
        return {"status": MISSING, "value": None, "evidence": [],
                "note": f"{label} could not be established from the text"}
    ev = [{"page": None, "text": ", ".join(v), "raw": k} for k, v in found.items()]
    if len(found) > 1:
        return {"status": CONFLICTING, "value": None, "evidence": ev,
                "note": f"indicators for more than one {label}: " + ", ".join(found)}
    value = next(iter(found))
    return {"status": FOUND, "value": value, "evidence": ev,
            "note": f"inferred from text indicators only; not verified"}


def _cas_field(sections):
    sec = sections.get(3)
    if not sec:
        return {"status": MISSING, "value": [], "evidence": [],
                "note": "Section 3 not located"}
    cas = []
    for p, ln in sec["lines"]:
        for m in CAS_RE.finditer(ln):
            c = m.group(0)
            if valid_cas(c) and c not in cas:
                cas.append(c)
    return {"status": FOUND if cas else MISSING, "value": cas, "evidence": [],
            "note": "informational only; CAS numbers are not used as product identity"}
