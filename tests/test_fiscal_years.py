"""Fiscal-year tokens: a consecutive period is a period; a garbled range or an unsupported year is masked."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify.checks import Known, mask_ungrounded, scan  # noqa: E402


def _fy(text, facts=()):
    return [(f["raw"], f["grounded"]) for f in scan(text, Known(list(facts), {}, "")) if f["kind"] == "fiscal_year"]


def test_consecutive_periods_are_not_flagged():
    assert _fy("Revenue in FY 2023-24 and FY2025-26 grew.") == []


def test_a_garbled_range_is_flagged_and_masked():
    text = "The industry grew from FY2100 to FY2105."
    assert _fy(text) == [("FY2100 to FY2105", False)]
    masked, hits = mask_ungrounded(text, [], {}, "Test Co")
    assert "FY2100" not in masked and "[●]" in masked and hits[0]["kind"] == "fiscal_year"


def test_a_single_year_is_grounded_when_the_inputs_contain_it():
    facts = [{"id": "a", "type": "entity", "label": "Incorporated", "value": "incorporated in 2010", "unit": "", "period": ""}]
    assert _fy("Incorporated in FY2010.", facts) == [("FY2010", True)]
    assert _fy("Incorporated in FY2031.", facts) == [("FY2031", False)]


def test_a_projection_in_the_inputs_grounds_the_same_period_in_the_draft():
    facts = [{"id": "a", "type": "short_text", "label": "Market", "value": "FY2020 - FY2031P", "unit": "", "period": ""}]
    assert _fy("market from FY2020 to FY2031 at a CAGR", facts) == [("FY2020 to FY2031", True)]
    assert _fy("market from FY2020 to FY2025 at a CAGR", facts) == [("FY2020 to FY2025", False)]


def test_two_digit_headers_are_left_alone():
    assert _fy("Columns: FY26, FY25 and FY24.") == []
