"""SDS Revision Tracker - Streamlit interface.

Run: .venv/bin/streamlit run app.py

Records are created only inside deliberate submitted actions (form submits
and buttons). Page reruns/refreshes only read data.
"""

import json
from pathlib import Path

import streamlit as st

from sdstracker import NOTICE, config, db
from sdstracker import workflow as wf
from sdstracker.compare import STATUS_LABELS, CHANGED, UNCHANGED

st.set_page_config(page_title="SDS Revision Tracker", layout="wide")

PAGES = ["Materials & documents", "Intake & material confirmation",
         "Comparison, draft & review", "Activity history"]

FIELD_LABELS = [("product_name", "Product name"), ("supplier", "Supplier"),
                ("product_identifier", "Product identifier"),
                ("revision_date", "Revision/preparation date"), ("version", "Version"),
                ("language", "Language (indicator)"), ("jurisdiction", "Jurisdiction (indicator)"),
                ("cas_numbers", "CAS numbers (informational)")]


# ---------------------------------------------------------------- helpers

def get_conn():
    try:
        # One connection per script run; Streamlit may call widget callbacks
        # (format_func) from another thread.
        return db.connect(check_same_thread=False)
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()


def flash(msg, kind="success"):
    st.session_state["flash"] = (kind, msg)


def show_flash():
    if "flash" in st.session_state:
        kind, msg = st.session_state.pop("flash")
        getattr(st, kind)(msg)


def actor():
    return st.session_state.get("actor", "").strip()


def require_actor():
    if not actor():
        st.warning("Enter your name/label in the sidebar first (it is recorded in the "
                   "activity history; it is not an authenticated identity).")
        return False
    return True


def doc_label(conn, doc_id):
    if not doc_id:
        return "none"
    d = wf.get_document(conn, doc_id)
    f = json.loads(d["fields"])
    date = f.get("revision_date", {})
    dt = date.get("value") or date.get("status", "?")
    return f"Doc #{d['id']} - {d['first_filename']} (date: {dt})"


def receipt_label(conn, r):
    cls = wf.CLASSIFICATION_LABELS.get(r["classification"], "awaiting material confirmation")
    return f"Receipt #{r['id']} - {r['original_filename']} - {cls}"


def material_label(m):
    return f"{m['code']} - {m['product_name']} ({m['supplier']})"


def pdf_download(conn, doc_id, key, role="original"):
    d = wf.get_document(conn, doc_id)
    path = config.DATA_DIR / d["stored_path"]
    if path.exists():
        st.download_button(f"Download {role} PDF (doc #{doc_id})", path.read_bytes(),
                           file_name=d["first_filename"], mime="application/pdf", key=key)
    else:
        st.error(f"Stored file missing: {d['stored_path']}")


def next_step(conn, r):
    if r["classification"] == wf.DUPLICATE:
        if r["match_status"] == wf.UNCONFIRMED:
            return ("Identical to a stored document that has no confirmed material. "
                    "Confirm the association on the original receipt.")
        return "No action needed beyond noting the duplicate receipt."
    if r["match_status"] == wf.UNCONFIRMED:
        return "Confirm which register material this document belongs to (Intake page)."
    rv = conn.execute("SELECT * FROM reviews WHERE receipt_id=?", (r["id"],)).fetchone()
    draft = conn.execute("SELECT 1 FROM notification_drafts WHERE receipt_id=?",
                         (r["id"],)).fetchone()
    steps = []
    if r["classification"] == wf.FIRST:
        steps.append("If appropriate, designate this document as the material's baseline "
                     "(Materials page).")
    if r["classification"] == wf.UNDETERMINED:
        steps.append("Manual review: resolve the uncertainty in the classification reason "
                     "by checking the original PDFs.")
    if not draft:
        steps.append("Generate the notification draft for regulatory review.")
    if rv and rv["status"] != "completed":
        steps.append("Record the review acknowledgment when the human review is done.")
    if r["classification"] == wf.NEWER and rv and rv["status"] == "completed":
        steps.append("If reviewers agree, explicitly change the baseline (Materials page). "
                     "It is never replaced automatically.")
    return " ".join(steps) or "Workflow steps recorded. No further action shown."


# ---------------------------------------------------------------- sidebar

st.sidebar.title("SDS Revision Tracker")
st.sidebar.caption(NOTICE)
page = st.sidebar.radio("Page", PAGES)
st.sidebar.text_input("Your name/label (not authenticated)", key="actor",
                      placeholder="e.g. Demo Coordinator")
st.sidebar.caption(f"Upload limit: {config.MAX_UPLOAD_MB} MB per PDF. No OCR. "
                   "No network calls. Nothing is sent.")

st.info(NOTICE)
conn = get_conn()
show_flash()


# ---------------------------------------------------------------- page 1

def page_materials():
    st.header("Materials & documents")
    st.caption("Register entries use fictional internal codes. Baselines change only "
               "through the explicit action below.")
    mats = conn.execute("SELECT * FROM materials ORDER BY code").fetchall()
    if not mats:
        st.write("No materials. Run `.venv/bin/python -m sdstracker demo-data` or "
                 "`add-material`.")
    for m in mats:
        with st.expander(material_label(m), expanded=True):
            st.write(f"**Product identifier:** {m['product_identifier'] or '-'}  \n"
                     f"**CAS numbers (informational, not identity):** "
                     f"{', '.join(json.loads(m['cas_numbers'])) or '-'}  \n"
                     f"**Selected baseline:** {doc_label(conn, m['baseline_document_id'])}")
            docs = conn.execute("SELECT * FROM documents WHERE material_id=? ORDER BY id",
                                (m["id"],)).fetchall()
            if not docs:
                st.write("No confirmed documents.")
                continue
            rows = []
            for d in docs:
                f = json.loads(d["fields"])
                n_rec = conn.execute("SELECT COUNT(*) FROM receipts WHERE document_id=?",
                                     (d["id"],)).fetchone()[0]
                rows.append({"doc": d["id"], "file": d["first_filename"],
                             "date": f.get("revision_date", {}).get("value")
                             or f.get("revision_date", {}).get("status"),
                             "version": f.get("version", {}).get("value") or "-",
                             "text": d["text_status"], "receipts": n_rec,
                             "baseline": "YES" if d["id"] == m["baseline_document_id"] else "",
                             "sha256": d["sha256"][:12] + "..."})
            st.dataframe(rows, hide_index=True, use_container_width=True)
            with st.form(f"baseline_{m['id']}"):
                st.write("**Designate baseline (explicit, logged)**")
                choice = st.selectbox("Document", [d["id"] for d in docs],
                                      format_func=lambda i: doc_label(conn, i))
                reason = st.text_input("Reason (required)")
                if st.form_submit_button("Set as baseline"):
                    if require_actor():
                        if not reason.strip():
                            st.error("A reason is required.")
                        else:
                            try:
                                wf.set_baseline(conn, m["id"], choice, actor(), reason)
                                flash(f"Baseline for {m['code']} set to document #{choice}.")
                                st.rerun()
                            except wf.WorkflowError as exc:
                                st.error(str(exc))
            for d in docs:
                pdf_download(conn, d["id"], key=f"dl_{m['id']}_{d['id']}")
    un = conn.execute("SELECT * FROM documents WHERE material_id IS NULL").fetchall()
    if un:
        st.subheader("Documents without a confirmed material")
        st.dataframe([{"doc": d["id"], "file": d["first_filename"], "text": d["text_status"]}
                      for d in un], hide_index=True)


# ---------------------------------------------------------------- page 2

def show_fields(d):
    fields = json.loads(d["fields"])
    rows = []
    for key, label in FIELD_LABELS:
        f = fields.get(key, {})
        ev = f.get("evidence") or []
        value = f.get("value")
        if isinstance(value, list):
            value = ", ".join(value) or None
        rows.append({"field": label, "status": f.get("status", "missing"),
                     "extracted value": value or "-",
                     "page": ", ".join(str(e.get("page")) for e in ev if e.get("page")) or "-",
                     "evidence text": " | ".join(e.get("text", "") for e in ev)[:300] or "-",
                     "note": f.get("note", "")})
    st.dataframe(rows, hide_index=True, use_container_width=True)


def page_intake():
    st.header("Intake & material confirmation")
    with st.form("upload", clear_on_submit=True):
        st.write("**Record receipt of an SDS PDF**")
        up = st.file_uploader("PDF file", type=["pdf"])
        c1, c2 = st.columns(2)
        src = c1.text_input("Source URL (optional)")
        ret = c2.text_input("Retrieval date (optional, as known)")
        if st.form_submit_button("Record receipt"):
            if require_actor():
                if up is None:
                    st.error("Choose a file first.")
                else:
                    try:
                        rid = wf.receive_document(conn, up.getvalue(), up.name, actor(),
                                                  source_url=src or None,
                                                  retrieved_on=ret or None)
                        st.session_state["selected_receipt"] = rid
                        flash(f"Receipt #{rid} recorded.")
                        st.rerun()
                    except wf.WorkflowError as exc:
                        st.error(str(exc))

    receipts = conn.execute("SELECT * FROM receipts ORDER BY id DESC").fetchall()
    if not receipts:
        st.write("No receipts yet.")
        return
    ids = [r["id"] for r in receipts]
    default = st.session_state.get("selected_receipt")
    idx = ids.index(default) if default in ids else 0
    rid = st.selectbox("Receipt", ids, index=idx,
                       format_func=lambda i: receipt_label(conn, wf.get_receipt(conn, i)))
    r = wf.get_receipt(conn, rid)
    d = wf.get_document(conn, r["document_id"])
    st.subheader("What arrived")
    st.write(f"**File:** {r['original_filename']}  \n**Received:** {r['received_at']} "
             f"by {r['actor']}  \n**Stored document:** #{d['id']} "
             f"(SHA-256 `{d['sha256']}`, {d['byte_size']} bytes, {d['page_count'] or '?'} pages)  \n"
             f"**Match status:** {r['match_status']}  \n"
             f"**Classification:** {wf.CLASSIFICATION_LABELS.get(r['classification'], 'pending')}")
    if r["classification_reason"]:
        st.write(f"**Reason:** {r['classification_reason']}")
    st.warning(f"Next step: {next_step(conn, r)}")
    if d["text_status"] != "text":
        st.error("No usable text could be extracted from this PDF (no OCR in this release). "
                 "Manual review of the original is required.")
    st.subheader("Extracted identifying fields (attempted; verify against the PDF)")
    show_fields(d)
    warns = json.loads(d["warnings"])
    if warns:
        st.write("**Extraction warnings**")
        for w in warns:
            st.write(f"- {w}")
    pdf_download(conn, d["id"], key=f"dl_intake_{d['id']}_{rid}")

    if r["match_status"] == wf.UNCONFIRMED and r["classification"] != wf.DUPLICATE:
        st.subheader("Confirm material association (required)")
        cands = wf.suggest_candidates(conn, d)
        if cands:
            if cands[0].get("ambiguous"):
                st.warning("Multiple candidates scored equally - the match is ambiguous.")
            st.dataframe([{"code": c["code"], "product": c["product_name"],
                           "supplier": c["supplier"], "score": c["score"],
                           "reasons": "; ".join(c["reasons"])} for c in cands],
                         hide_index=True)
        else:
            st.write("No register candidates suggested from product identifier, supplier "
                     "or name. (CAS numbers are not used to establish identity.)")
        mats = conn.execute("SELECT * FROM materials ORDER BY code").fetchall()
        with st.form(f"confirm_{rid}"):
            choice = st.selectbox("Register material", [None] + [m["id"] for m in mats],
                                  format_func=lambda i: "-- select --" if i is None
                                  else material_label(wf.get_material(conn, i)))
            reason = st.text_input("Confirmation note (optional)")
            if st.form_submit_button("Confirm association and classify"):
                if require_actor():
                    if choice is None:
                        st.error("Select a material.")
                    else:
                        try:
                            wf.confirm_material(conn, rid, choice, actor(), reason or None)
                            flash("Association confirmed and receipt classified.")
                            st.rerun()
                        except wf.WorkflowError as exc:
                            st.error(str(exc))
        with st.form(f"nomatch_{rid}"):
            reason = st.text_input("Reason no register material matches")
            if st.form_submit_button("Mark: no register material matches (manual review)"):
                if require_actor():
                    if not reason.strip():
                        st.error("A reason is required.")
                    else:
                        wf.mark_no_register_match(conn, rid, actor(), reason)
                        flash("Marked for manual review. No material was created.")
                        st.rerun()


# ---------------------------------------------------------------- page 3

def _md(text):
    """Escape Markdown control characters in extracted SDS text."""
    import re
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|~<>:$])", r"\\\1", text or "")


def _pages(p):
    if not p:
        return "not located"
    return f"p. {p[0]}" if p[0] == p[1] else f"pp. {p[0]}-{p[1]}"


def show_section(rid, n, s):
    label = STATUS_LABELS[s["status"]]
    with st.expander(f"Section {n} {s['title']}: {label}",
                     expanded=s["status"] == CHANGED):
        st.write(f"**Status:** {label}. {s['note']}")
        pages = f"Baseline: {_pages(s['old_pages'])}; incoming: {_pages(s['new_pages'])}"
        st.caption(pages)
        for c in s["changes"]:
            st.markdown(f"- ...{_md(c['context_before'])} "
                        + (f":red[~~{_md(c['removed'])}~~] " if c["removed"] else "")
                        + (f":green[**{_md(c['added'])}**] " if c["added"] else "")
                        + f"{_md(c['context_after'])}...")
        st.caption("Red strikethrough = removed from baseline text; green bold = added "
                   "in incoming text.")
        if s["old_text"] is not None or s["new_text"] is not None:
            c1, c2 = st.columns(2)
            c1.text_area("Baseline source text", s["old_text"] or "(not available)",
                         height=180, disabled=True, key=f"old_{rid}_{n}")
            c2.text_area("Incoming source text", s["new_text"] or "(not available)",
                         height=180, disabled=True, key=f"new_{rid}_{n}")


def page_compare():
    st.header("Comparison, draft & review")
    receipts = conn.execute("SELECT * FROM receipts WHERE classification IS NOT NULL"
                            " ORDER BY id DESC").fetchall()
    if not receipts:
        st.write("No classified receipts yet. Confirm a material association on the Intake page.")
        return
    ids = [r["id"] for r in receipts]
    default = st.session_state.get("selected_receipt")
    rid = st.selectbox("Receipt", ids, index=ids.index(default) if default in ids else 0,
                       format_func=lambda i: receipt_label(conn, wf.get_receipt(conn, i)))
    r = wf.get_receipt(conn, rid)
    m = wf.get_material(conn, r["material_id"]) if r["material_id"] else None
    st.write(f"**Material:** {material_label(m) if m else 'not confirmed'}  \n"
             f"**Incoming:** {doc_label(conn, r['document_id'])}  \n"
             f"**Baseline used for this receipt:** {doc_label(conn, r['baseline_document_id'])}"
             + ("  \n*(recorded at classification time; later baseline changes do not "
                "rewrite this result)*" if r["baseline_document_id"] else ""))
    st.write(f"**Classification:** {wf.CLASSIFICATION_LABELS[r['classification']]}  \n"
             f"**Reason:** {r['classification_reason']}")
    st.warning(f"Next step: {next_step(conn, r)}")
    c1, c2 = st.columns(2)
    with c1:
        pdf_download(conn, r["document_id"], key=f"dl_inc_{rid}", role="incoming")
    if r["baseline_document_id"]:
        with c2:
            pdf_download(conn, r["baseline_document_id"], key=f"dl_base_{rid}", role="baseline")

    comp = json.loads(r["comparison"]) if r["comparison"] else None
    st.subheader("Section comparison (Sections 2, 3, 8, 14, 15 only)")
    if comp:
        st.write(f"**Summary:** {comp['summary']}")
        st.caption("Text comparison only. Other sections are outside the comparison scope. "
                   "A text change is not a judgment of hazard severity, regulatory "
                   "applicability, compliance or transport requirements.")
        for n, s in comp["sections"].items():
            show_section(rid, n, s)
    else:
        st.write("No comparison was performed for this receipt (no baseline used).")

    if r["classification"] == wf.DUPLICATE:
        return
    st.subheader("Notification draft (not sent)")
    draft = conn.execute("SELECT * FROM notification_drafts WHERE receipt_id=?",
                         (rid,)).fetchone()
    if draft:
        st.caption(f"Draft generated {draft['generated_at']}. This application cannot send it.")
        st.text_input("To", draft["recipient_label"], disabled=True, key=f"to_{rid}")
        st.text_input("Subject", draft["subject"], disabled=True, key=f"subj_{rid}")
        st.text_area("Body", draft["body"], height=420, disabled=True, key=f"body_{rid}")
    elif st.button("Generate notification draft", key=f"gen_{rid}"):
        if require_actor():
            wf.generate_draft(conn, rid, actor())
            flash("Draft generated (not sent).")
            st.rerun()

    st.subheader("Review acknowledgment (simulated; not approval)")
    rv = conn.execute("SELECT * FROM reviews WHERE receipt_id=?", (rid,)).fetchone()
    if rv is None:
        st.write("No review record for this receipt.")
        return
    st.write(f"**Status:** {rv['status']}  \n**Reviewer label:** {rv['reviewer_label'] or '-'}"
             f"  \n**Comments:** {rv['comments'] or '-'}  \n**Updated:** {rv['updated_at']}"
             + (f"  \n**Completed:** {rv['completed_at']}" if rv["completed_at"] else ""))
    if rv["status"] != "completed":
        with st.form(f"review_{rid}"):
            status = st.selectbox("Status", ["in_progress", "completed"])
            label = st.text_input("Reviewer label (free text, not authenticated)",
                                  value=rv["reviewer_label"] or "")
            comments = st.text_area("Comments", value=rv["comments"] or "")
            if st.form_submit_button("Record review acknowledgment"):
                if require_actor():
                    try:
                        wf.update_review(conn, rid, status, label, comments, actor())
                        flash(f"Review status recorded: {status}. This is an "
                              "acknowledgment, not an approval.")
                        st.rerun()
                    except wf.WorkflowError as exc:
                        st.error(str(exc))


# ---------------------------------------------------------------- page 4

def page_history():
    st.header("Activity history")
    st.caption("Application activity history / version tracking, recorded as the workflow "
               "runs. It is not tamper-proof or certified compliance logging. Past events "
               "cannot be edited from this interface.")
    rows = conn.execute("SELECT * FROM activity_events ORDER BY id DESC").fetchall()
    st.dataframe([{"time (UTC)": e["ts"], "actor": e["actor"], "action": e["action"],
                   "record": f"{e['entity_type']} #{e['entity_id']}" if e["entity_id"]
                   else e["entity_type"],
                   "previous": e["previous_value"] or "", "new": e["new_value"] or "",
                   "reason": e["reason"] or ""} for e in rows],
                 hide_index=True, use_container_width=True)


{PAGES[0]: page_materials, PAGES[1]: page_intake, PAGES[2]: page_compare,
 PAGES[3]: page_history}[page]()
