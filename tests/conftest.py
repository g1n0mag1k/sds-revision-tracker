"""Test fixtures. ALL PDFs used by these tests are SYNTHETIC, generated at
test time by sdstracker.synthetic. They are not real-document results."""

import pytest

from sdstracker import db, workflow
from sdstracker.synthetic import make_sds


@pytest.fixture
def env(tmp_path):
    data_dir = tmp_path / "data"
    db.init_db(data_dir)
    conn = db.connect(data_dir)
    fixtures = tmp_path / "synthetic_fixtures"
    fixtures.mkdir()

    class Env:
        pass

    e = Env()
    e.conn, e.data_dir, e.fixtures = conn, data_dir, fixtures

    def receive(path, actor="tester"):
        return workflow.receive_document(conn, path.read_bytes(), path.name, actor,
                                         data_dir=data_dir)

    def material(code="TEST-RM-001", name="Synthetic Demo Resin Concentrate A",
                 supplier="Example Synthetic Supplier (fictional)", pid="SYN-1000"):
        return workflow.add_material(conn, code, name, supplier, pid, ["7732-18-5"])

    def pdf(name, **kw):
        return make_sds(fixtures / name, **kw)

    def baseline(mid, **kw):
        rid = receive(pdf("baseline.pdf", **kw))
        workflow.confirm_material(conn, rid, mid, "tester")
        doc_id = workflow.get_receipt(conn, rid)["document_id"]
        workflow.set_baseline(conn, mid, doc_id, "tester", "test baseline")
        return rid, doc_id

    e.receive, e.material, e.pdf, e.baseline = receive, material, pdf, baseline
    e.receipt = lambda rid: workflow.get_receipt(conn, rid)
    e.events = lambda action=None: [dict(r) for r in conn.execute(
        "SELECT * FROM activity_events" + (" WHERE action=?" if action else "") + " ORDER BY id",
        (action,) if action else ())]
    yield e
    conn.close()
