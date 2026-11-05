"""Intake, material confirmation, classification, drafts and review.

Every state change is a deliberate function call that writes an activity
event. Nothing here sends notifications or approves anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from . import config
from .compare import compare_documents
from .db import SYSTEM_ACTOR, loads, log_event, now
from .extraction import (AMBIGUOUS, CONFLICTING, FOUND, TEXT_OK, extract_pdf,
                         normalize_name)

# Classification outcomes
FIRST = "first_document_on_file"
DUPLICATE = "exact_duplicate"
NEWER = "newer_dated_revision"
OLDER = "older_dated_document"
SAME_DATE_CHANGED = "same_date_changed_content"
UNDETERMINED = "undetermined_manual_review"

CLASSIFICATION_LABELS = {
    FIRST: "First document on file",
    DUPLICATE: "Exact duplicate",
    NEWER: "Newer dated revision",
    OLDER: "Older dated document",
    SAME_DATE_CHANGED: "Same date with changed content",
    UNDETERMINED: "Undetermined - manual review",
}

# Match statuses
UNCONFIRMED = "unconfirmed"
CONFIRMED = "confirmed"
INHERITED = "inherited_from_identical_document"
NO_REGISTER_MATCH = "no_register_match"

REVIEW_STATUSES = ("pending", "in_progress", "completed")
RECIPIENT_LABEL = "Regulatory support — demonstration recipient"


class WorkflowError(Exception):
    """A requested action is not allowed in the current state."""


# ---------------------------------------------------------------- materials

def add_material(conn, code, product_name, supplier, product_identifier=None,
                 cas_numbers=None, actor=SYSTEM_ACTOR, reason=None):
    cur = conn.execute(
        "INSERT INTO materials (code, product_name, supplier, product_identifier,"
        " cas_numbers, created_at) VALUES (?,?,?,?,?,?)",
        (code, product_name, supplier, product_identifier,
         json.dumps(cas_numbers or []), now()))
    mid = cur.lastrowid
    log_event(conn, actor, "material_created", "material", mid,
              new_value={"code": code, "product_name": product_name,
                         "supplier": supplier, "product_identifier": product_identifier},
              reason=reason)
    conn.commit()
    return mid


def get_material(conn, material_id):
    return conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()


def get_document(conn, document_id):
    return conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()


def get_receipt(conn, receipt_id):
    return conn.execute("SELECT * FROM receipts WHERE id=?", (receipt_id,)).fetchone()


def doc_dict(row) -> dict:
    d = dict(row)
    d["fields"] = loads(d["fields"], {})
    d["sections"] = loads(d["sections"], {})
    d["warnings"] = loads(d["warnings"], [])
    return d


# ---------------------------------------------------------------- intake

def _safe_display_name(name: str) -> str:
    base = os.path.basename(name or "unnamed.pdf")
    return re.sub(r"[^\w.\- ()]+", "_", base)[:200] or "unnamed.pdf"


def receive_document(conn, data: bytes, original_filename: str, actor: str,
                     source_url: str | None = None, retrieved_on: str | None = None,
                     data_dir=None) -> int:
    """Record one deliberate receipt of a file. Returns the receipt id.

    Identical bytes are stored once; every call creates a new receipt.
    """
    actor = (actor or "").strip() or "unnamed user"
    filename = _safe_display_name(original_filename)
    if len(data) > config.MAX_UPLOAD_BYTES:
        log_event(conn, actor, "upload_rejected", "receipt", None,
                  new_value={"filename": filename, "bytes": len(data)},
                  reason=f"File exceeds the {config.MAX_UPLOAD_MB} MB upload limit")
        conn.commit()
        raise WorkflowError(f"File exceeds the {config.MAX_UPLOAD_MB} MB upload limit; "
                            "it was not stored.")
    if not data:
        raise WorkflowError("Empty file; nothing was stored.")

    sha = hashlib.sha256(data).hexdigest()
    existing = conn.execute("SELECT * FROM documents WHERE sha256=?", (sha,)).fetchone()
    ts = now()

    if existing:
        doc_id = existing["id"]
        if existing["material_id"] is not None:
            match_status, material_id = INHERITED, existing["material_id"]
            reason = (f"Identical file bytes (SHA-256) to stored document #{doc_id}, "
                      f"which has a confirmed material association.")
        else:
            match_status, material_id = UNCONFIRMED, None
            reason = (f"Identical file bytes (SHA-256) to stored document #{doc_id}. "
                      "That document has no confirmed material association yet, so "
                      "none is inherited.")
        cur = conn.execute(
            "INSERT INTO receipts (document_id, original_filename, received_at, actor,"
            " match_status, material_id, classification, classification_reason)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (doc_id, filename, ts, actor, match_status, material_id, DUPLICATE, reason))
        rid = cur.lastrowid
        log_event(conn, actor, "receipt_recorded", "receipt", rid,
                  new_value={"filename": filename, "sha256": sha, "document_id": doc_id})
        log_event(conn, SYSTEM_ACTOR, "duplicate_recognized", "receipt", rid,
                  new_value={"document_id": doc_id, "match_status": match_status},
                  reason=reason)
        log_event(conn, SYSTEM_ACTOR, "classification_recorded", "receipt", rid,
                  new_value={"classification": DUPLICATE}, reason=reason)
        conn.commit()
        return rid

    # New bytes: store under an application-controlled path, never overwrite.
    docs_dir = config.documents_dir(data_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / f"{sha}.pdf"
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise WorkflowError(f"Stored file {path.name} does not match its hash; "
                                "refusing to overwrite.")
    else:
        with open(path, "xb") as fh:  # exclusive create: never overwrites
            fh.write(data)
    ext = extract_pdf(path)
    fields = dict(ext["fields"])
    if ext.get("text_fingerprint"):
        fields["text_fingerprint"] = {"status": FOUND, "value": ext["text_fingerprint"],
                                      "evidence": [], "note": "SHA-256 of normalized text"}
    cur = conn.execute(
        "INSERT INTO documents (sha256, stored_path, first_filename, byte_size, page_count,"
        " source_url, retrieved_on, text_status, fields, sections, warnings, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (sha, str(path.relative_to(Path(data_dir or config.DATA_DIR))), filename, len(data),
         ext["page_count"], source_url, retrieved_on, ext["text_status"],
         json.dumps(fields), json.dumps({str(k): v for k, v in ext["sections"].items()}),
         json.dumps(ext["warnings"]), ts))
    doc_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO receipts (document_id, original_filename, received_at, actor,"
        " match_status) VALUES (?,?,?,?,?)",
        (doc_id, filename, ts, actor, UNCONFIRMED))
    rid = cur.lastrowid
    log_event(conn, actor, "receipt_recorded", "receipt", rid,
              new_value={"filename": filename, "sha256": sha, "document_id": doc_id,
                         "source_url": source_url, "retrieved_on": retrieved_on})
    log_event(conn, SYSTEM_ACTOR, "document_stored", "document", doc_id,
              new_value={"stored_path": path.name, "bytes": len(data)})
    summary = {k: v.get("status") for k, v in ext["fields"].items()}
    log_event(conn, SYSTEM_ACTOR, "extraction_outcome", "document", doc_id,
              new_value={"text_status": ext["text_status"], "fields": summary,
                         "sections_located": sorted(int(k) for k in ext["sections"]),
                         "warnings": len(ext["warnings"])},
              reason="Attempted field/section extraction; not a full understanding of the SDS")
    conn.commit()
    return rid


# ---------------------------------------------------------------- matching

def _norm_id(s):
    return re.sub(r"[\s\-_./]", "", (s or "").lower())


def _id_set(s):
    """An extracted identifier may be a list (e.g. several catalog numbers)."""
    return {_norm_id(x) for x in re.split(r"[;,]", s or "") if _norm_id(x)}


def _ids_overlap(a, b):
    return bool(_id_set(a) & _id_set(b))


def _names_match(a, b):
    a, b = normalize_name(a), normalize_name(b)
    return bool(a and b) and (a == b or a in b or b in a)


def suggest_candidates(conn, document) -> list[dict]:
    """Suggest register materials. Suggestions are never applied automatically.

    Uses product identifier, supplier and product name. CAS overlap is shown
    for information only and does not contribute to the score.
    """
    doc = doc_dict(document) if not isinstance(document, dict) else document
    f = doc["fields"]
    pid = f.get("product_identifier", {}).get("value")
    sup = f.get("supplier", {}).get("value")
    name = f.get("product_name", {}).get("value")
    doc_cas = set(f.get("cas_numbers", {}).get("value") or [])
    out = []
    for m in conn.execute("SELECT * FROM materials ORDER BY code"):
        score, reasons = 0, []
        if pid and m["product_identifier"] and _ids_overlap(pid, m["product_identifier"]):
            score += 3
            reasons.append("product identifier matches")
        elif pid and m["product_identifier"]:
            reasons.append("product identifier differs")
        if sup and _names_match(sup, m["supplier"]):
            score += 1
            reasons.append("supplier matches")
        if name and _names_match(name, m["product_name"]):
            score += 2
            reasons.append("product name matches")
        shared = doc_cas & set(json.loads(m["cas_numbers"] or "[]"))
        if shared:
            reasons.append(f"shares CAS {', '.join(sorted(shared))} (informational only)")
        if score > 0:
            out.append({"material_id": m["id"], "code": m["code"],
                        "product_name": m["product_name"], "supplier": m["supplier"],
                        "score": score, "reasons": reasons})
    out.sort(key=lambda c: -c["score"])
    if len(out) > 1 and out[0]["score"] == out[1]["score"]:
        for c in out:
            c["ambiguous"] = True
    return out


def confirm_material(conn, receipt_id, material_id, actor, reason=None):
    """Human confirmation of a receipt's material association; then classify."""
    r = get_receipt(conn, receipt_id)
    if r is None:
        raise WorkflowError("Receipt not found.")
    if r["classification"] == DUPLICATE:
        raise WorkflowError("Exact duplicate receipts inherit association from the "
                            "original document; confirm on the original receipt.")
    if r["match_status"] != UNCONFIRMED:
        raise WorkflowError(f"Receipt match status is already '{r['match_status']}'.")
    m = get_material(conn, material_id)
    if m is None:
        raise WorkflowError("Material not found.")
    doc = get_document(conn, r["document_id"])
    if doc["material_id"] not in (None, material_id):
        raise WorkflowError("Document is already associated with a different material.")
    actor = (actor or "").strip() or "unnamed user"
    conn.execute("UPDATE documents SET material_id=? WHERE id=?", (material_id, doc["id"]))
    conn.execute("UPDATE receipts SET match_status=?, material_id=? WHERE id=?",
                 (CONFIRMED, material_id, receipt_id))
    log_event(conn, actor, "match_confirmed", "receipt", receipt_id,
              previous_value={"match_status": UNCONFIRMED, "material_id": None},
              new_value={"match_status": CONFIRMED, "material_id": material_id,
                         "material_code": m["code"], "document_id": doc["id"]},
              reason=reason or "Human confirmed material association")
    _classify(conn, receipt_id)
    _ensure_review(conn, receipt_id, actor)
    conn.commit()


def mark_no_register_match(conn, receipt_id, actor, reason):
    r = get_receipt(conn, receipt_id)
    if r is None or r["match_status"] != UNCONFIRMED or r["classification"] == DUPLICATE:
        raise WorkflowError("Only unconfirmed, non-duplicate receipts can be marked.")
    actor = (actor or "").strip() or "unnamed user"
    why = ("A person indicated that no register material matches this document. It is "
           "not treated as a new material automatically; manual review is required.")
    conn.execute("UPDATE receipts SET match_status=?, classification=?,"
                 " classification_reason=? WHERE id=?",
                 (NO_REGISTER_MATCH, UNDETERMINED, why, receipt_id))
    log_event(conn, actor, "match_marked_no_register_entry", "receipt", receipt_id,
              previous_value={"match_status": UNCONFIRMED},
              new_value={"match_status": NO_REGISTER_MATCH}, reason=reason or why)
    log_event(conn, SYSTEM_ACTOR, "classification_recorded", "receipt", receipt_id,
              new_value={"classification": UNDETERMINED}, reason=why)
    _ensure_review(conn, receipt_id, actor)
    conn.commit()


# ---------------------------------------------------------------- classify

def _field(doc, name):
    return doc["fields"].get(name) or {"status": "missing", "value": None}


def _identity_checks(material, baseline, incoming):
    conflicts, limits = [], []
    sup, name, pid = (_field(incoming, k) for k in ("supplier", "product_name",
                                                     "product_identifier"))
    for label, f in (("supplier", sup), ("product name", name)):
        if f["status"] == CONFLICTING:
            conflicts.append(f"incoming document has conflicting {label} values")
        elif f["status"] != FOUND:
            limits.append(f"incoming {label} not found")
    if sup["status"] == FOUND and not _names_match(sup["value"], material["supplier"]):
        conflicts.append(f"incoming supplier '{sup['value']}' does not match register "
                         f"supplier '{material['supplier']}'")
    if pid["status"] == FOUND and material["product_identifier"] and \
            not _ids_overlap(pid["value"], material["product_identifier"]):
        conflicts.append(f"incoming product identifier '{pid['value']}' differs from "
                         f"register '{material['product_identifier']}'")
    if baseline is not None:
        bpid, bname = _field(baseline, "product_identifier"), _field(baseline, "product_name")
        if pid["status"] == FOUND and bpid["status"] == FOUND and \
                not _ids_overlap(pid["value"], bpid["value"]):
            conflicts.append(f"product identifier differs from baseline "
                             f"('{bpid['value']}' vs '{pid['value']}')")
        if name["status"] == FOUND and bname["status"] == FOUND and \
                not _names_match(name["value"], bname["value"]):
            conflicts.append(f"product name differs from baseline "
                             f"('{bname['value']}' vs '{name['value']}')")
    return conflicts, limits


def _edition_checks(baseline, incoming):
    """Language/jurisdiction. Returns (blocking_conflicts, limitations)."""
    blocking, limits = [], []
    for attr in ("language", "jurisdiction"):
        b, i = _field(baseline, attr), _field(incoming, attr)
        if b["status"] == FOUND and i["status"] == FOUND and b["value"] != i["value"]:
            blocking.append(f"{attr} differs (baseline: {b['value']}; "
                            f"incoming: {i['value']})")
        else:
            for label, f in (("baseline", b), ("incoming", i)):
                if f["status"] == CONFLICTING:
                    limits.append(f"{label} {attr}: {f['note']}")
                elif f["status"] != FOUND:
                    limits.append(f"{label} {attr} could not be established")
            if b["status"] == FOUND and i["status"] == FOUND:
                limits.append(f"{attr} inferred from text indicators as {i['value']} "
                              "for both documents (not verified)")
    return blocking, limits


def _classify(conn, receipt_id):
    r = get_receipt(conn, receipt_id)
    material = get_material(conn, r["material_id"])
    incoming = doc_dict(get_document(conn, r["document_id"]))
    baseline_id = material["baseline_document_id"]
    comparison = None
    limitations = []

    if baseline_id is None:
        others = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE material_id=? AND id<>?",
            (material["id"], incoming["id"])).fetchone()[0]
        if others == 0:
            cls = FIRST
            reason = ("No other document is on file for this material. No baseline is "
                      "selected; a person may designate this document as the baseline.")
        else:
            cls = UNDETERMINED
            reason = ("Other documents are on file for this material but no baseline is "
                      "selected, so there is nothing explicit to compare against.")
        if incoming["text_status"] != TEXT_OK:
            reason += " No usable text was extracted from this document."
        _store_classification(conn, receipt_id, cls, reason, None, None)
        return

    if baseline_id == incoming["id"]:
        _store_classification(conn, receipt_id, UNDETERMINED,
                              "This document is already the selected baseline.",
                              baseline_id, None)
        return

    baseline = doc_dict(get_document(conn, baseline_id))
    reasons = []
    if incoming["text_status"] != TEXT_OK:
        cls = UNDETERMINED
        reasons.append("no usable text was extracted from the incoming document "
                       "(image-only, blank or unreadable PDF); manual review required")
        comparison = compare_documents(baseline, incoming)
    elif baseline["text_status"] != TEXT_OK:
        cls = UNDETERMINED
        reasons.append("no usable text is available for the baseline document")
        comparison = compare_documents(baseline, incoming)
    else:
        blocking, ed_limits = _edition_checks(baseline, incoming)
        limitations += ed_limits
        conflicts, id_limits = _identity_checks(material, baseline, incoming)
        limitations += id_limits
        if blocking:
            cls = UNDETERMINED
            reasons.append("documents appear to be different editions: " + "; ".join(blocking))
            comparison = compare_documents(
                baseline, incoming,
                unavailable_reason="documents appear to be different language/jurisdiction "
                                   "editions and are not compared as a revision pair")
        else:
            comparison = compare_documents(baseline, incoming)
            cls, date_reason = _date_classification(baseline, incoming)
            reasons.append(date_reason)
            if conflicts:
                cls = UNDETERMINED
                reasons.insert(0, "identity conflict: " + "; ".join(conflicts))
            same_text = (_field(baseline, "text_fingerprint").get("value") ==
                         _field(incoming, "text_fingerprint").get("value"))
            if same_text:
                reasons.append("file bytes differ from the baseline but the extracted "
                               "text is identical")
                if cls == SAME_DATE_CHANGED:
                    cls = UNDETERMINED
    bv, iv = _field(baseline, "version"), _field(incoming, "version")
    if bv.get("value") or iv.get("value"):
        reasons.append(f"version strings recorded as baseline '{bv.get('value') or '-'}', "
                       f"incoming '{iv.get('value') or '-'}' (not ordered)")
    reason = "; ".join(reasons)
    reason = reason[0].upper() + reason[1:] + "."
    if limitations:
        reason += " Limitations: " + "; ".join(limitations) + "."
    _store_classification(conn, receipt_id, cls, reason, baseline_id, comparison)


def _date_classification(baseline, incoming):
    b, i = _field(baseline, "revision_date"), _field(incoming, "revision_date")
    if b["status"] != FOUND or i["status"] != FOUND:
        details = []
        for label, f in (("baseline", b), ("incoming", i)):
            if f["status"] != FOUND:
                details.append(f"{label} date is {f['status']}"
                               + (f" ({f.get('note')})" if f.get("note") else ""))
        return UNDETERMINED, "dates cannot be compared: " + "; ".join(details)
    note = ""
    if b.get("kind") != i.get("kind"):
        note = (f" (baseline date labeled {b.get('kind')}, incoming labeled "
                f"{i.get('kind')})")
    if i["value"] > b["value"]:
        return NEWER, (f"incoming date {i['value']} is later than baseline date "
                       f"{b['value']}{note}")
    if i["value"] < b["value"]:
        return OLDER, (f"incoming date {i['value']} is earlier than baseline date "
                       f"{b['value']}{note}")
    return SAME_DATE_CHANGED, (f"incoming and baseline share the date {i['value']} but the "
                               f"file content differs{note}")


def _store_classification(conn, receipt_id, cls, reason, baseline_id, comparison):
    conn.execute("UPDATE receipts SET classification=?, classification_reason=?,"
                 " baseline_document_id=?, comparison=? WHERE id=?",
                 (cls, reason, baseline_id,
                  json.dumps(comparison) if comparison else None, receipt_id))
    log_event(conn, SYSTEM_ACTOR, "classification_recorded", "receipt", receipt_id,
              new_value={"classification": cls, "baseline_document_id": baseline_id},
              reason=reason)
    if comparison:
        log_event(conn, SYSTEM_ACTOR, "comparison_recorded", "receipt", receipt_id,
                  new_value={"baseline_document_id": baseline_id,
                             "sections": {n: s["status"]
                                          for n, s in comparison["sections"].items()}},
                  reason=comparison["summary"])


# ---------------------------------------------------------------- baseline

def set_baseline(conn, material_id, document_id, actor, reason):
    """Explicitly designate a material's baseline document."""
    m = get_material(conn, material_id)
    d = get_document(conn, document_id)
    if m is None or d is None:
        raise WorkflowError("Material or document not found.")
    if d["material_id"] != material_id:
        raise WorkflowError("Only a document with a confirmed association to this "
                            "material can be its baseline.")
    if m["baseline_document_id"] == document_id:
        raise WorkflowError("This document is already the baseline.")
    actor = (actor or "").strip() or "unnamed user"
    conn.execute("UPDATE materials SET baseline_document_id=? WHERE id=?",
                 (document_id, material_id))
    log_event(conn, actor, "baseline_designated", "material", material_id,
              previous_value={"baseline_document_id": m["baseline_document_id"]},
              new_value={"baseline_document_id": document_id},
              reason=reason or "Explicit baseline designation")
    conn.commit()


# ---------------------------------------------------------------- review

def _ensure_review(conn, receipt_id, actor):
    if conn.execute("SELECT 1 FROM reviews WHERE receipt_id=?", (receipt_id,)).fetchone():
        return
    ts = now()
    cur = conn.execute("INSERT INTO reviews (receipt_id, status, created_at, updated_at)"
                       " VALUES (?,?,?,?)", (receipt_id, "pending", ts, ts))
    log_event(conn, SYSTEM_ACTOR, "review_opened", "review", cur.lastrowid,
              new_value={"receipt_id": receipt_id, "status": "pending"},
              reason="Human review acknowledgment required")


def update_review(conn, receipt_id, status, reviewer_label, comments, actor):
    """Record a review acknowledgment step. Completion is NOT approval."""
    if status not in REVIEW_STATUSES:
        raise WorkflowError("Unknown review status.")
    rv = conn.execute("SELECT * FROM reviews WHERE receipt_id=?", (receipt_id,)).fetchone()
    if rv is None:
        raise WorkflowError("No review exists for this receipt yet.")
    if rv["status"] == "completed":
        raise WorkflowError("Review acknowledgment is already completed.")
    if status == "completed" and not (reviewer_label or "").strip():
        raise WorkflowError("A reviewer label is required to complete the acknowledgment.")
    ts = now()
    conn.execute("UPDATE reviews SET status=?, reviewer_label=?, comments=?, updated_at=?,"
                 " completed_at=? WHERE id=?",
                 (status, reviewer_label, comments, ts,
                  ts if status == "completed" else None, rv["id"]))
    action = "review_acknowledgment_completed" if status == "completed" else "review_status_changed"
    log_event(conn, (actor or "").strip() or "unnamed user", action, "review", rv["id"],
              previous_value={"status": rv["status"]},
              new_value={"status": status, "reviewer_label": reviewer_label,
                         "comments": comments},
              reason="Simulated acknowledgment only; not regulatory approval. "
                     "Reviewer label is not an authenticated identity.")
    conn.commit()


# ---------------------------------------------------------------- drafts

def generate_draft(conn, receipt_id, actor) -> int:
    """Create a notification DRAFT. Nothing is sent. One draft per receipt."""
    existing = conn.execute("SELECT id FROM notification_drafts WHERE receipt_id=?",
                            (receipt_id,)).fetchone()
    if existing:
        return existing["id"]
    r = get_receipt(conn, receipt_id)
    if r is None or r["classification"] is None:
        raise WorkflowError("Receipt must be classified before a draft is generated.")
    if r["classification"] == DUPLICATE:
        raise WorkflowError("Exact duplicates do not need a notification draft.")
    subject, body = render_draft(conn, r)
    cur = conn.execute("INSERT INTO notification_drafts (receipt_id, recipient_label, subject,"
                       " body, generated_at) VALUES (?,?,?,?,?)",
                       (receipt_id, RECIPIENT_LABEL, subject, body, now()))
    did = cur.lastrowid
    log_event(conn, (actor or "").strip() or "unnamed user", "draft_generated",
              "notification_draft", did,
              new_value={"receipt_id": receipt_id, "recipient_label": RECIPIENT_LABEL},
              reason="Draft only; this application has no sending capability")
    conn.commit()
    return did


def _date_text(doc):
    f = _field(doc, "revision_date")
    if f["status"] == FOUND:
        return f"{f['value']} ({f.get('note') or 'labeled date'})"
    return f"{f['status'].upper()} - {f.get('note') or ''}".strip(" -")


def render_draft(conn, r):
    m = get_material(conn, r["material_id"]) if r["material_id"] else None
    inc = doc_dict(get_document(conn, r["document_id"]))
    base = doc_dict(get_document(conn, r["baseline_document_id"])) \
        if r["baseline_document_id"] else None
    comp = loads(r["comparison"])
    code = m["code"] if m else "(no confirmed material)"
    subject = (f"[DRAFT - review requested] SDS receipt #{r['id']} for {code}: "
               f"{CLASSIFICATION_LABELS[r['classification']]}")
    lines = [
        f"To: {RECIPIENT_LABEL}",
        "Status: DRAFT generated by the SDS Revision Tracker demonstration. Not sent.",
        "",
        f"Material code: {code}" + (" (fictional demonstration code)" if m else ""),
        f"Product / supplier (register): "
        + (f"{m['product_name']} / {m['supplier']}" if m else "not confirmed"),
        "",
        f"Incoming document: #{inc['id']} '{r['original_filename']}' received "
        f"{r['received_at']} by {r['actor']}",
        f"  Stored file: {inc['stored_path']} (SHA-256 {inc['sha256'][:16]}...)",
        f"  Date: {_date_text(inc)}",
    ]
    if inc.get("source_url"):
        lines.append(f"  Source: {inc['source_url']} (retrieved {inc.get('retrieved_on') or 'unknown'})")
    if base:
        lines += [f"Baseline document: #{base['id']} '{base['first_filename']}'",
                  f"  Stored file: {base['stored_path']} (SHA-256 {base['sha256'][:16]}...)",
                  f"  Date: {_date_text(base)}"]
    else:
        lines.append("Baseline document: none used")
    lines += ["",
              f"Classification: {CLASSIFICATION_LABELS[r['classification']]}",
              f"Reason: {r['classification_reason']}", ""]
    if comp:
        lines.append("Supported-section comparison (Sections 2, 3, 8, 14, 15):")
        for n, s in comp["sections"].items():
            from .compare import STATUS_LABELS
            lines.append(f"  Section {n} {s['title']}: {STATUS_LABELS[s['status']]}"
                         + (f" - {s['note']}" if s["note"] else ""))
        lines += ["", f"Summary: {comp['summary']}"]
    else:
        lines.append("Supported-section comparison: not performed (no baseline used).")
    warnings = inc["warnings"]
    lines += ["", "Extraction/comparison limitations:"]
    lines += [f"  - {w}" for w in warnings] or ["  - none recorded"]
    lines += ["  - Text comparison only. Sections outside 2, 3, 8, 14 and 15 are not compared.",
              "  - No OCR; image-only content is not read.",
              "  - This draft makes no determination about hazard severity, regulatory "
              "applicability, compliance, transport, or permission to use the material.",
              "",
              "Request: please review the original documents and record a review "
              "acknowledgment in the tracker.",
              ]
    return subject, "\n".join(lines)
