"""Workflow tests. All documents are SYNTHETIC fixtures generated at test time."""

import hashlib
import json

import pytest

from sdstracker import compare, workflow as wf
from sdstracker.synthetic import make_image_only, make_malformed

REVISED = {2: ["Classification: Synthetic example classification A and B.",
               "Signal word: Danger",
               "Hazard statements: H000 Synthetic example statement for testing."],
           8: ["Exposure limit (example): 5 mg/m3 TWA",
               "Eye protection: safety glasses with side shields."]}


def confirm(env, rid, mid):
    wf.confirm_material(env.conn, rid, mid, "tester")
    return env.receipt(rid)


def test_first_document(env):
    mid = env.material()
    rid = env.receive(env.pdf("a.pdf"))
    r = env.receipt(rid)
    assert r["match_status"] == wf.UNCONFIRMED and r["classification"] is None
    r = confirm(env, rid, mid)
    assert r["classification"] == wf.FIRST
    assert r["baseline_document_id"] is None
    # First document does not become the baseline automatically.
    assert wf.get_material(env.conn, mid)["baseline_document_id"] is None


def test_explicit_first_baseline_logged(env):
    mid = env.material()
    _, doc_id = env.baseline(mid)
    assert wf.get_material(env.conn, mid)["baseline_document_id"] == doc_id
    ev = env.events("baseline_designated")
    assert len(ev) == 1 and json.loads(ev[0]["new_value"])["baseline_document_id"] == doc_id


def test_duplicate_twice_two_receipts(env):
    mid = env.material()
    rid1, doc_id = env.baseline(mid)
    p = env.fixtures / "baseline.pdf"
    rid2 = env.receive(p)
    rid3 = env.receive(p)
    rows = env.conn.execute("SELECT * FROM receipts WHERE document_id=?", (doc_id,)).fetchall()
    assert len(rows) == 3
    assert env.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    for rid in (rid2, rid3):
        r = env.receipt(rid)
        assert r["classification"] == wf.DUPLICATE
        assert r["match_status"] == wf.INHERITED and r["material_id"] == mid
    assert len(env.events("duplicate_recognized")) == 2


def test_duplicate_of_unconfirmed_stays_unconfirmed(env):
    p = env.pdf("a.pdf")
    env.receive(p)
    rid2 = env.receive(p)
    r = env.receipt(rid2)
    assert r["classification"] == wf.DUPLICATE
    assert r["match_status"] == wf.UNCONFIRMED and r["material_id"] is None


def test_newer_revision_and_comparison(env):
    mid = env.material()
    _, base_id = env.baseline(mid)
    rid = env.receive(env.pdf("v2.pdf", date_line="Revision date: 2025-06-15",
                              version="2.0", body=REVISED))
    r = confirm(env, rid, mid)
    assert r["classification"] == wf.NEWER
    assert r["baseline_document_id"] == base_id
    assert "2025-06-15" in r["classification_reason"]
    comp = json.loads(r["comparison"])
    assert comp["changed"] == ["2", "8"]
    assert comp["sections"]["3"]["status"] == compare.UNCHANGED
    assert comp["summary"].startswith("Text changes detected in Sections 2 and 8.")
    assert "Human review required." in comp["summary"]
    s8 = comp["sections"]["8"]
    assert any("10" in c["removed"] and "5" in c["added"] for c in s8["changes"])
    assert s8["old_pages"] and s8["new_pages"]
    # Signal word change preserved verbatim (no case/negation normalization).
    assert any("Danger" in c["added"] for c in comp["sections"]["2"]["changes"])


def test_older_document(env):
    mid = env.material()
    env.baseline(mid)
    rid = env.receive(env.pdf("old.pdf", date_line="Revision date: 2022-01-10"))
    assert confirm(env, rid, mid)["classification"] == wf.OLDER


def test_same_date_changed_content(env):
    mid = env.material()
    env.baseline(mid)
    rid = env.receive(env.pdf("same.pdf", body=REVISED))
    assert confirm(env, rid, mid)["classification"] == wf.SAME_DATE_CHANGED


def test_different_hash_unchanged_text(env):
    mid = env.material()
    _, base_id = env.baseline(mid)
    base = env.fixtures / "baseline.pdf"
    alt = env.fixtures / "resaved.pdf"
    # Same content, different bytes (appended PDF comment after EOF).
    alt.write_bytes(base.read_bytes() + b"\n% re-saved copy\n")
    assert hashlib.sha256(alt.read_bytes()).hexdigest() != \
        hashlib.sha256(base.read_bytes()).hexdigest()
    rid = env.receive(alt)
    r = confirm(env, rid, mid)
    assert r["classification"] == wf.UNDETERMINED
    assert "extracted text is identical" in r["classification_reason"]
    comp = json.loads(r["comparison"])
    assert comp["changed"] == []


def test_missing_and_ambiguous_date_undetermined(env):
    mid = env.material()
    env.baseline(mid)
    rid = env.receive(env.pdf("nodate.pdf", date_line=None, body=REVISED))
    r = confirm(env, rid, mid)
    assert r["classification"] == wf.UNDETERMINED
    assert "incoming date is missing" in r["classification_reason"]
    rid = env.receive(env.pdf("amb.pdf", date_line="Revision date: 03/04/2025", body=REVISED))
    r = confirm(env, rid, mid)
    assert r["classification"] == wf.UNDETERMINED
    assert "ambiguous" in r["classification_reason"]


def test_unconfirmed_and_ambiguous_material(env):
    env.material("TEST-RM-001", pid=None)
    env.material("TEST-RM-002", pid=None)  # same name/supplier: ambiguous
    rid = env.receive(env.pdf("a.pdf"))
    r = env.receipt(rid)
    assert r["match_status"] == wf.UNCONFIRMED and r["material_id"] is None
    assert r["classification"] is None
    doc = wf.get_document(env.conn, r["document_id"])
    assert doc["material_id"] is None
    cands = wf.suggest_candidates(env.conn, doc)
    assert len(cands) == 2 and all(c.get("ambiguous") for c in cands)


def test_cas_overlap_alone_is_not_a_candidate(env):
    env.material("TEST-RM-009", name="Unrelated Product", supplier="Other Co", pid="ZZZ")
    doc = wf.get_document(env.conn, env.receipt(env.receive(env.pdf("a.pdf")))["document_id"])
    assert wf.suggest_candidates(env.conn, doc) == []


def test_no_register_match_is_not_new_material(env):
    rid = env.receive(env.pdf("a.pdf"))
    wf.mark_no_register_match(env.conn, rid, "tester", "not in register")
    r = env.receipt(rid)
    assert r["classification"] == wf.UNDETERMINED and r["material_id"] is None
    assert env.conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0


def test_unreadable_pdf_requires_manual_review(env, tmp_path):
    mid = env.material()
    env.baseline(mid)
    for maker, name in ((make_image_only, "img.pdf"), (make_malformed, "bad.pdf")):
        rid = env.receive(maker(env.fixtures / name))
        r = confirm(env, rid, mid)
        assert r["classification"] == wf.UNDETERMINED
        comp = json.loads(r["comparison"])
        assert comp["changed"] == [] and comp["unchanged"] == []
        assert all(s["status"] == compare.EXTRACTION_FAILED for s in comp["sections"].values())
        assert "No text changes" not in comp["summary"]


def test_missing_section_not_reported_as_no_change(env):
    mid = env.material()
    env.baseline(mid)
    rid = env.receive(env.pdf("no14.pdf", date_line="Revision date: 2025-06-15",
                              omit_sections=(14,)))
    comp = json.loads(confirm(env, rid, mid)["comparison"])
    assert comp["sections"]["14"]["status"] == compare.NOT_FOUND
    assert "14" not in comp["unchanged"]
    assert "Section 14: section not found" in comp["summary"]


def test_heading_without_text_is_extraction_failure(env):
    mid = env.material()
    env.baseline(mid)
    rid = env.receive(env.pdf("empty8.pdf", date_line="Revision date: 2025-06-15",
                              body={8: []}))
    comp = json.loads(confirm(env, rid, mid)["comparison"])
    assert comp["sections"]["8"]["status"] == compare.EXTRACTION_FAILED


def test_language_jurisdiction_conflict_not_compared(env):
    mid = env.material()
    env.baseline(mid)
    eu = dict(REVISED)
    eu[15] = ["Regulation (EC) No 1907/2006 (REACH) - synthetic example."]
    rid = env.receive(env.pdf("eu.pdf", date_line="Revision date: 2025-06-15", body=eu))
    r = confirm(env, rid, mid)
    assert r["classification"] == wf.UNDETERMINED
    comp = json.loads(r["comparison"])
    assert all(s["status"] == compare.UNAVAILABLE for s in comp["sections"].values())


def test_identity_conflict_not_forced(env):
    mid = env.material()
    env.baseline(mid)
    rid = env.receive(env.pdf("other.pdf", supplier="Different Synthetic Vendor",
                              date_line="Revision date: 2025-06-15"))
    r = confirm(env, rid, mid)
    assert r["classification"] == wf.UNDETERMINED
    assert "identity conflict" in r["classification_reason"].lower()


def test_no_automatic_baseline_replacement_and_history_kept(env):
    mid = env.material()
    _, base_id = env.baseline(mid)
    rid = env.receive(env.pdf("v2.pdf", date_line="Revision date: 2025-06-15", body=REVISED))
    r = confirm(env, rid, mid)
    assert wf.get_material(env.conn, mid)["baseline_document_id"] == base_id
    before = (r["classification"], r["baseline_document_id"], r["comparison"])
    # Explicit baseline change does not rewrite earlier receipt results.
    wf.set_baseline(env.conn, mid, r["document_id"], "tester", "newer revision reviewed")
    r2 = env.receipt(rid)
    assert (r2["classification"], r2["baseline_document_id"], r2["comparison"]) == before


def test_draft_not_recorded_as_sent(env):
    mid = env.material()
    env.baseline(mid)
    rid = env.receive(env.pdf("v2.pdf", date_line="Revision date: 2025-06-15", body=REVISED))
    confirm(env, rid, mid)
    d1 = wf.generate_draft(env.conn, rid, "tester")
    d2 = wf.generate_draft(env.conn, rid, "tester")  # repeated call: no duplicate draft
    assert d1 == d2
    draft = env.conn.execute("SELECT * FROM notification_drafts WHERE id=?", (d1,)).fetchone()
    assert draft["recipient_label"] == "Regulatory support — demonstration recipient"
    for needle in ("TEST-RM-001", "Newer dated revision", "Section 2", "Section 8",
                   "baseline.pdf", "v2.pdf", "review"):
        assert needle in draft["body"]
    actions = [e["action"] for e in env.events()]
    assert actions.count("draft_generated") == 1
    assert not any(a in ("sent", "notified", "notification_sent") for a in actions)
    assert not any("sent" in e["action"] or "notified" in e["action"] for e in env.events())


def test_review_not_recorded_as_approval(env):
    mid = env.material()
    env.baseline(mid)
    rid = env.receive(env.pdf("v2.pdf", date_line="Revision date: 2025-06-15", body=REVISED))
    confirm(env, rid, mid)
    wf.update_review(env.conn, rid, "in_progress", "Reviewer A", "looking", "tester")
    with pytest.raises(wf.WorkflowError):
        wf.update_review(env.conn, rid, "completed", "", "", "tester")
    wf.update_review(env.conn, rid, "completed", "Reviewer A", "checked sections 2, 8", "tester")
    rv = env.conn.execute("SELECT * FROM reviews WHERE receipt_id=?", (rid,)).fetchone()
    assert rv["status"] == "completed" and rv["completed_at"]
    assert all("approv" not in e["action"] for e in env.events())
    ev = env.events("review_acknowledgment_completed")[0]
    assert "not regulatory approval" in ev["reason"]
    # Draft status and review status are independent: no draft exists here.
    assert env.conn.execute("SELECT COUNT(*) FROM notification_drafts").fetchone()[0] == 0


def test_original_pdf_preserved(env):
    mid = env.material()
    env.baseline(mid)
    p = env.fixtures / "baseline.pdf"
    original = p.read_bytes()
    env.receive(p)  # duplicate receipt must not rewrite the stored file
    doc = env.conn.execute("SELECT * FROM documents").fetchone()
    stored = env.data_dir / doc["stored_path"]
    assert stored.read_bytes() == original
    assert doc["sha256"] == hashlib.sha256(original).hexdigest()
    assert doc["first_filename"] == "baseline.pdf"


def test_filename_is_not_used_as_path(env):
    p = env.pdf("x.pdf")
    rid = wf.receive_document(env.conn, p.read_bytes(), "../../etc/evil.pdf", "tester",
                              data_dir=env.data_dir)
    r = env.receipt(rid)
    doc = wf.get_document(env.conn, r["document_id"])
    assert r["original_filename"] == "evil.pdf"
    assert doc["stored_path"].startswith("documents/") and ".." not in doc["stored_path"]


def test_upload_size_limit(env, monkeypatch):
    from sdstracker import config
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(wf.WorkflowError):
        wf.receive_document(env.conn, b"%PDF-" + b"x" * 20, "big.pdf", "tester",
                            data_dir=env.data_dir)
    assert env.conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0
    assert len(env.events("upload_rejected")) == 1


def test_required_activity_events(env):
    mid = env.material()
    env.baseline(mid)
    env.receive(env.fixtures / "baseline.pdf")
    rid = env.receive(env.pdf("v2.pdf", date_line="Revision date: 2025-06-15", body=REVISED))
    confirm(env, rid, mid)
    wf.generate_draft(env.conn, rid, "tester")
    wf.update_review(env.conn, rid, "completed", "Reviewer A", "", "tester")
    actions = {e["action"] for e in env.events()}
    for a in ("receipt_recorded", "duplicate_recognized", "extraction_outcome",
              "match_confirmed", "classification_recorded", "comparison_recorded",
              "draft_generated", "review_acknowledgment_completed", "baseline_designated"):
        assert a in actions, a


def test_identifier_list_matches_register_identifier(env):
    """A catalog-number list containing the register identifier is a candidate."""
    mid = env.material(pid="SYN-1000")
    rid = env.receive(env.pdf("list.pdf", product_id="SYN-0999; SYN-1000; SYN-1001"))
    doc = wf.get_document(env.conn, env.receipt(rid)["document_id"])
    cands = wf.suggest_candidates(env.conn, doc)
    assert cands[0]["material_id"] == mid
    assert "product identifier matches" in cands[0]["reasons"]
