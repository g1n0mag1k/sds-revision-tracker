"""Streamlit AppTest smoke tests (SYNTHETIC data). Checks pages render, the
persistent notice is shown, and reruns do not create duplicate records."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from sdstracker import NOTICE, config, db, workflow as wf

APP = str(Path(__file__).resolve().parent.parent / "app.py")
REVISED = {8: ["Exposure limit (example): 5 mg/m3 TWA"]}


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    from sdstracker.synthetic import make_sds
    db.init_db()
    conn = db.connect()
    mid = wf.add_material(conn, "TEST-RM-001", "Synthetic Demo Resin Concentrate A",
                          "Example Synthetic Supplier (fictional)", "SYN-1000")
    b = make_sds(tmp_path / "base.pdf")
    rid = wf.receive_document(conn, b.read_bytes(), b.name, "tester")
    wf.confirm_material(conn, rid, mid, "tester")
    wf.set_baseline(conn, mid, wf.get_receipt(conn, rid)["document_id"], "tester", "t")
    n = make_sds(tmp_path / "new.pdf", date_line="Revision date: 2025-06-15", body=REVISED)
    rid2 = wf.receive_document(conn, n.read_bytes(), n.name, "tester")
    wf.confirm_material(conn, rid2, mid, "tester")
    yield conn, rid2
    conn.close()


def counts(conn):
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("receipts", "notification_drafts", "reviews", "activity_events")}


def test_pages_render_with_notice(seeded):
    conn, _ = seeded
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    for page in at.sidebar.radio[0].options:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
        assert any(NOTICE in i.value for i in at.info)


def test_reruns_do_not_create_records(seeded):
    conn, rid = seeded
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.text_input[0].set_value("Demo Coordinator").run()
    at.sidebar.radio[0].set_value("Comparison, draft & review").run()
    before = counts(conn)
    at.run(); at.run()
    assert counts(conn) == before
    gen = [b for b in at.button if b.label == "Generate notification draft"]
    gen[0].click().run()
    assert not at.exception
    after = counts(conn)
    assert after["notification_drafts"] == before["notification_drafts"] + 1
    at.run(); at.run()
    assert counts(conn) == after
