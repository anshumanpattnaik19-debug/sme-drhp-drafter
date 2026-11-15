"""Dates from OCR text, where the spaces between day, month and year are often lost ("21September2023")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.facts import parse_dates  # noqa: E402
from extract import rules  # noqa: E402


def test_compact_ocr_dates_are_read():
    found = sorted(str(d) for d in parse_dates("Date of issue 21September2023 Validupto 20September2026"))
    assert found == ["2023-09-21", "2026-09-20"]
    assert [m.group(1) for m in rules.RE_DATE.finditer("Valid 20September2026")] == ["20September2026"]


def test_ocr_text_gets_spaces_back_in_dates():
    from ingest.readers import _space_dates

    assert _space_dates("Date of issue 21September2023 Validupto 20September2026") == \
        "Date of issue 21 September 2023 Validupto 20 September 2026"
    assert _space_dates("on 1st March2024") == "on 1st March 2024"


def test_spaced_dates_still_read():
    assert sorted(str(d) for d in parse_dates("14 August 2025 and August 8, 2022")) == ["2022-08-08", "2025-08-14"]
