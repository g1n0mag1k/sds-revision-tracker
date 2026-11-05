"""Regression tests for extraction problems found on a REAL supplier SDS.

Source: Fisher Scientific SDS for Acetone (catalog A18-4), US OSHA HCS 2024
edition, revision date 18-Dec-2025 - see samples/real/README.md for provenance.
The PDF itself is NOT in the repository. These tests use only short label-line
excerpts reproducing the layout patterns that failed, not the document.
"""

from sdstracker.extraction import FOUND, MISSING, extract_from_pages

PAGE1 = """SAFETY DATA SHEET
Creation Date 28-Apr-2009 Revision Date 18-Dec-2025 Revision Number 9
This safety data sheet was created pursuant to the requirements of: US OSHA Hazard Communication Standard 2024 (29
CFR 1910.1200)
1. Identification
Product Name Acetone
Cat No. : A18-1; A18-4; A18-20;
A18P-4; A18S-4
CAS No 67-64-1
Details of the supplier of the safety data sheet
Company
Fisher Scientific Company
One Reagent Lane
2. Hazard(s) identification
Classification
Flammable liquids Category 2
3. Composition/information on Ingredients
Component CAS No Weight %
Acetone 67-64-1 >95
______________________________________________
Page 1 / 3"""

PAGE2 = """Acetone Revision Date 18-Dec-2025
______________________________________________
8. Exposure controls / personal protection
Exposure Guidelines
______________________________________________
Page 2 / 3"""

PAGE3 = """Acetone Revision Date 18-Dec-2025
______________________________________________
14. Transport information
DOT
UN-No UN1090
15. Regulatory Information
Component CAS No REACH (1907/2006) - REACH Regulation (EC 1907/2006)
16. Other Information
Revision Date 18-Dec-2025
Print Date 18-Dec-2025
______________________________________________
Page 3 / 3"""


def extract():
    return extract_from_pages([PAGE1, PAGE2, PAGE3])


def test_label_without_colon_product_name():
    f = extract()["fields"]["product_name"]
    assert f["status"] == FOUND and f["value"] == "Acetone"
    assert f["evidence"][0]["page"] == 1


def test_bare_company_label_value_on_next_line():
    f = extract()["fields"]["supplier"]
    assert f["status"] == FOUND
    assert f["value"] == "Fisher Scientific Company"
    assert "Fisher Scientific Company" in f["evidence"][0]["text"]


def test_catalog_number_list_with_continuation():
    f = extract()["fields"]["product_identifier"]
    assert f["status"] == FOUND
    assert "A18-4" in f["value"] and "A18S-4" in f["value"]


def test_revision_number_as_version_and_print_date_ignored():
    f = extract()["fields"]
    assert f["version"]["status"] == FOUND and f["version"]["value"] == "9"
    assert f["revision_date"]["status"] == FOUND
    assert f["revision_date"]["value"] == "2025-12-18"
    assert all("Print" not in e["text"] for e in f["revision_date"]["evidence"])


def test_declared_basis_preferred_over_section15_inventory_mentions():
    f = extract()["fields"]["jurisdiction"]
    assert f["status"] == FOUND and f["value"] == "US (OSHA HCS)"
    assert "not verified" in f["note"]


def test_running_header_and_page_footer_not_in_section_text():
    # As in the real document, the running header repeats on every page after
    # the first (here pages 2-3), so it is treated as a header and excluded.
    s = extract()["sections"]
    assert set(s) >= {1, 2, 3, 8, 14, 15, 16}
    assert "Revision Date" not in s[8]["text"]
    assert "Page" not in s[3]["text"]
    assert s[3]["text"].splitlines()[-1] == "Acetone 67-64-1 >95"


def test_cat_no_without_value_stays_missing():
    f = extract_from_pages(["1. Identification\nProduct Name X\nCompany\n\n"
                            "2. Hazard(s) identification\n" + "text " * 20])["fields"]
    assert f["product_identifier"]["status"] == MISSING
