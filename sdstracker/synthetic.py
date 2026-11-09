"""Generator for CLEARLY SYNTHETIC SDS-like test PDFs (development only).

These are not real Safety Data Sheets and do not imitate any supplier's
layout. Every page is stamped "SYNTHETIC TEST DOCUMENT - NOT A REAL SDS".
Requires the development dependency fpdf2.
"""

from __future__ import annotations

from pathlib import Path

STAMP = "SYNTHETIC TEST DOCUMENT - NOT A REAL SDS"

SECTION_TITLES = {
    1: "Identification", 2: "Hazard(s) identification",
    3: "Composition/information on ingredients", 4: "First-aid measures",
    5: "Fire-fighting measures", 6: "Accidental release measures",
    7: "Handling and storage", 8: "Exposure controls/personal protection",
    9: "Physical and chemical properties", 10: "Stability and reactivity",
    11: "Toxicological information", 12: "Ecological information",
    13: "Disposal considerations", 14: "Transport information",
    15: "Regulatory information", 16: "Other information",
}

DEFAULT_BODY = {
    2: ["Classification: Synthetic example classification A.",
        "Signal word: Warning",
        "Hazard statements: H000 Synthetic example statement for testing."],
    3: ["Example component alpha   CAS 7732-18-5   60-70 %",
        "Example component beta    CAS 64-17-5     30-40 %"],
    8: ["Exposure limit (example): 10 mg/m3 TWA",
        "Eye protection: safety glasses with side shields."],
    14: ["UN number: Not regulated (synthetic example).",
         "Transport hazard class: None (synthetic example)."],
    15: ["Regulatory text: synthetic example; refers to 29 CFR 1910.1200 for illustration.",
         "Inventory status: example only."],
}


def sds_lines(product_name="Synthetic Demo Resin Concentrate A",
              supplier="Example Synthetic Supplier (fictional)",
              product_id="SYN-1000", date_line="Revision date: 2024-03-01",
              version="1.0", body=None, omit_sections=(), extra_section1=()):
    body = {**DEFAULT_BODY, **(body or {})}
    lines = []
    for n in range(1, 17):
        if n in omit_sections:
            continue
        lines.append(("h", f"SECTION {n}: {SECTION_TITLES[n]}"))
        if n == 1:
            lines += [("t", f"Product name: {product_name}")]
            if product_id:
                lines.append(("t", f"Product number: {product_id}"))
            lines += [("t", f"Supplier: {supplier}"), ("t", "Address: 1 Example Street, Nowhere")]
            lines += [("t", x) for x in extra_section1]
        elif n == 16:
            if date_line:
                lines.append(("t", date_line))
            if version:
                lines.append(("t", f"Version: {version}"))
            lines.append(("t", "This synthetic document exists only to test software."))
        else:
            for x in body.get(n, [f"Synthetic placeholder text for section {n}."]):
                lines.append(("t", x))
    return lines


def write_pdf(path, lines, lines_per_page=28, footer=None):
    from fpdf import FPDF
    pdf = FPDF(format="Letter")
    pdf.set_auto_page_break(False)
    chunks = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [[]]
    for idx, chunk in enumerate(chunks, 1):
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, STAMP, new_x="LMARGIN", new_y="NEXT")
        for kind, text in chunk:
            pdf.set_font("Helvetica", "B" if kind == "h" else "", 10)
            pdf.cell(0, 8 if kind == "h" else 6, text, new_x="LMARGIN", new_y="NEXT")
        pdf.set_y(-20)
        pdf.set_font("Helvetica", "", 8)
        if footer:
            pdf.cell(0, 5, footer, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"Page {idx} of {len(chunks)}")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return Path(path)


def make_sds(path, footer=None, **kw):
    return write_pdf(path, sds_lines(**kw), footer=footer)


def make_image_only(path):
    """A PDF with drawn shapes only and no text layer (simulates a scanned page)."""
    from fpdf import FPDF
    pdf = FPDF(format="Letter")
    pdf.add_page()
    for i in range(10):
        pdf.rect(20, 20 + i * 20, 170, 10, style="F")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return Path(path)


def make_malformed(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(b"%PDF-1.4\n% synthetic malformed file - not a valid PDF\n")
    return Path(path)


def demo_set(out_dir):
    """Write the synthetic demo document set. Returns {key: path}."""
    out = Path(out_dir)
    revised_body = {
        2: ["Classification: Synthetic example classification A and B.",
            "Signal word: Warning",
            "Hazard statements: H000 Synthetic example statement for testing.",
            "H001 Additional synthetic example statement."],
        8: ["Exposure limit (example): 5 mg/m3 TWA",
            "Eye protection: safety glasses with side shields."],
    }
    files = {
        "baseline_v1": make_sds(out / "SYNTHETIC_resin-A_v1_2024-03-01.pdf"),
        "revision_v2": make_sds(out / "SYNTHETIC_resin-A_v2_2025-06-15.pdf",
                                date_line="Revision date: 2025-06-15", version="2.0",
                                body=revised_body),
        "older_v0": make_sds(out / "SYNTHETIC_resin-A_v0_2022-01-10.pdf",
                             date_line="Revision date: 2022-01-10", version="0.9"),
        "ambiguous_date": make_sds(out / "SYNTHETIC_resin-A_ambiguous-date.pdf",
                                   date_line="Revision date: 03/04/2025", version="2.1",
                                   body=revised_body),
        "image_only": make_image_only(out / "SYNTHETIC_image-only-scan.pdf"),
    }
    return files
