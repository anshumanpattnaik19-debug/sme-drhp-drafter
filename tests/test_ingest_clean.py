"""Running headers and footers are not body text, and table cells are checked like prose."""
import fitz

from ingest import readers
from verify.checks import mask_ungrounded


def _report_pdf(path):
    doc = fitz.open()
    for n in range(1, 5):
        page = doc.new_page()
        page.insert_text((72, 60), "Kestrel Flexipak Limited - Restated Financial Information", fontsize=9)
        page.insert_text((72, 110), f"Body paragraph {n}: the Company has no outstanding statutory dues for year {n}.",
                         fontsize=10)
        page.insert_text((72, 780), f"Page {n}", fontsize=8)
    doc.save(str(path))
    doc.close()
    return path


def test_running_header_and_page_numbers_are_removed(tmp_path):
    res = readers.read_file(str(_report_pdf(tmp_path / "report.pdf")), ocr=False)
    text = "\n".join(b["text"] for b in res["blocks"])
    assert "Restated Financial Information" not in text
    assert "Page 2" not in text and "Page 4" not in text
    assert "Body paragraph 2" in text and "Body paragraph 4" in text


def test_strip_keeps_a_line_that_is_not_repeated():
    blocks = [{"kind": "text", "text": "Header line\nUnique line on page one"},
              {"kind": "text", "text": "Header line\nUnique line on page two"},
              {"kind": "text", "text": "Header line\nUnique line on page three"}]
    readers.strip_running_lines(blocks)
    assert all("Header line" not in b["text"] for b in blocks)
    assert "Unique line on page one" in blocks[0]["text"]


def test_a_value_in_a_table_cell_is_masked_when_the_inputs_do_not_have_it():
    facts = [{"value": "Kestrel Flexipak Limited", "type": "entity"}]
    cell, masked = mask_ungrounded("Year ended March 31, 2023", facts, None, "Kestrel")
    assert "2023" not in cell
    assert masked and masked[0]["kind"] == "date"
