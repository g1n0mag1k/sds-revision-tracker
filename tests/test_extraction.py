"""Extraction tests on SYNTHETIC fixtures."""

from sdstracker.extraction import (AMBIGUOUS, CONFLICTING, FOUND, MISSING, NO_TEXT,
                                   FAILED, extract_from_pages, extract_pdf, parse_date)
from sdstracker.synthetic import make_image_only, make_malformed, make_sds


def test_parse_date_does_not_guess_ambiguous():
    assert parse_date("2025-06-15")["value"] == "2025-06-15"
    assert parse_date("15 June 2025")["value"] == "2025-06-15"
    assert parse_date("June 15, 2025")["value"] == "2025-06-15"
    assert parse_date("15-Jun-2025")["value"] == "2025-06-15"
    assert parse_date("15/06/2025")["value"] == "2025-06-15"
    assert parse_date("06/15/2025")["value"] == "2025-06-15"
    assert parse_date("03/04/2025")["status"] == AMBIGUOUS
    assert parse_date("03/04/25")["status"] == AMBIGUOUS
    assert parse_date("31/02/2025")["status"] == AMBIGUOUS  # invalid calendar date


def test_fields_found_with_evidence(tmp_path):
    r = extract_pdf(make_sds(tmp_path / "a.pdf"))
    f = r["fields"]
    assert f["product_name"]["status"] == FOUND
    assert f["supplier"]["value"] == "Example Synthetic Supplier (fictional)"
    assert f["revision_date"]["value"] == "2024-03-01"
    ev = f["revision_date"]["evidence"][0]
    assert ev["page"] >= 1 and "Revision date" in ev["text"]
    assert set(r["sections"]) == set(range(1, 17))


def test_print_date_not_used_as_revision_date():
    pages = ["SECTION 1: Identification\nProduct name: X\nSupplier: Y\n"
             "SECTION 16: Other information\nPrint date: 2026-11-05\n" + "filler " * 10]
    f = extract_from_pages(pages)["fields"]["revision_date"]
    assert f["status"] == MISSING


def test_missing_and_ambiguous_date(tmp_path):
    r = extract_pdf(make_sds(tmp_path / "a.pdf", date_line=None))
    assert r["fields"]["revision_date"]["status"] == MISSING
    r = extract_pdf(make_sds(tmp_path / "b.pdf", date_line="Revision date: 03/04/2025"))
    assert r["fields"]["revision_date"]["status"] == AMBIGUOUS


def test_conflicting_dates(tmp_path):
    r = extract_pdf(make_sds(tmp_path / "a.pdf", footer="Revision date: 2023-01-01"))
    assert r["fields"]["revision_date"]["status"] == CONFLICTING


def test_missing_section_reported(tmp_path):
    r = extract_pdf(make_sds(tmp_path / "a.pdf", omit_sections=(8,)))
    assert 8 not in r["sections"]
    assert any("8" in w for w in r["warnings"] if "not located" in w)


def test_image_only_and_malformed(tmp_path):
    r = extract_pdf(make_image_only(tmp_path / "img.pdf"))
    assert r["text_status"] == NO_TEXT
    assert any("Manual review required" in w for w in r["warnings"])
    r = extract_pdf(make_malformed(tmp_path / "bad.pdf"))
    assert r["text_status"] == FAILED
    assert r["fields"]["revision_date"]["status"] == MISSING
