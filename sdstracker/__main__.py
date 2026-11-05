"""Command line: explicit setup and demo commands.

  .venv/bin/python -m sdstracker init-db
  .venv/bin/python -m sdstracker demo-data
  .venv/bin/python -m sdstracker add-material --code ... --name ... --supplier ...
  .venv/bin/python -m sdstracker receive FILE.pdf --actor NAME [--source-url URL --retrieved-on DATE]
"""

import argparse
import sys
from pathlib import Path

from . import NOTICE, config, db, workflow


def cmd_init_db(args):
    path, created = db.init_db()
    print(f"{'Created' if created else 'Existing database kept (not reset)'}: {path}")


def cmd_demo_data(args):
    db.init_db()
    conn = db.connect()
    if conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0]:
        print("Materials already exist; demo data was not added (nothing reset).")
        return 1
    try:
        from .synthetic import demo_set
    except ImportError:
        print("demo-data needs the development dependency fpdf2 (requirements-dev.txt).")
        return 1
    actor = "demo-data command"
    files = demo_set(config.synthetic_demo_dir())
    mid = workflow.add_material(
        conn, "DEMO-RM-001", "Synthetic Demo Resin Concentrate A",
        "Example Synthetic Supplier (fictional)", product_identifier="SYN-1000",
        cas_numbers=["7732-18-5", "64-17-5"], actor=actor,
        reason="Synthetic demonstration register entry; fictional internal code")
    workflow.add_material(
        conn, "DEMO-RM-002", "Synthetic Demo Pigment Blend B",
        "Example Synthetic Supplier (fictional)", product_identifier="SYN-2000",
        cas_numbers=["7732-18-5"], actor=actor,
        reason="Synthetic demonstration register entry; fictional internal code")
    rid = workflow.receive_document(conn, files["baseline_v1"].read_bytes(),
                                    files["baseline_v1"].name, actor)
    workflow.confirm_material(conn, rid, mid, actor,
                              reason="Demo setup: baseline document for DEMO-RM-001")
    doc_id = workflow.get_receipt(conn, rid)["document_id"]
    workflow.set_baseline(conn, mid, doc_id, actor,
                          reason="Demo setup: explicit baseline designation")
    print("Synthetic demo data added (SYNTHETIC - not real SDS documents).")
    print("Register: DEMO-RM-001 (baseline stored), DEMO-RM-002.")
    print(f"Synthetic PDFs to upload in the app are in: {config.synthetic_demo_dir()}")
    for k, p in files.items():
        if k != "baseline_v1":
            print(f"  {k}: {p.name}")
    return 0


def cmd_add_material(args):
    conn = db.connect()
    mid = workflow.add_material(conn, args.code, args.name, args.supplier,
                                args.product_id, args.cas or [], actor=args.actor,
                                reason=args.reason)
    print(f"Material #{mid} {args.code} added.")


def cmd_receive(args):
    conn = db.connect()
    p = Path(args.file)
    rid = workflow.receive_document(conn, p.read_bytes(), p.name, args.actor,
                                    source_url=args.source_url,
                                    retrieved_on=args.retrieved_on)
    r = workflow.get_receipt(conn, rid)
    print(f"Receipt #{rid} recorded (document #{r['document_id']}, "
          f"match status {r['match_status']}, classification {r['classification'] or 'pending'}).")
    print("Confirm the material association in the app before classification.")


def main(argv=None):
    print(NOTICE, file=sys.stderr)
    ap = argparse.ArgumentParser(prog="sdstracker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="create tables if missing (never resets)").set_defaults(f=cmd_init_db)
    sub.add_parser("demo-data", help="seed SYNTHETIC demo register and baseline").set_defaults(f=cmd_demo_data)
    a = sub.add_parser("add-material", help="add one register material")
    a.add_argument("--code", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--supplier", required=True)
    a.add_argument("--product-id")
    a.add_argument("--cas", action="append")
    a.add_argument("--actor", default="cli user")
    a.add_argument("--reason")
    a.set_defaults(f=cmd_add_material)
    r = sub.add_parser("receive", help="record receipt of a PDF")
    r.add_argument("file")
    r.add_argument("--actor", required=True)
    r.add_argument("--source-url")
    r.add_argument("--retrieved-on")
    r.set_defaults(f=cmd_receive)
    args = ap.parse_args(argv)
    return args.f(args) or 0


if __name__ == "__main__":
    sys.exit(main())
