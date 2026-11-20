"""20 Nov 2026: figures printed with spaces are closed up when a fact backs them; serial numbers and split regulation lists are not figures."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.facts import figures  # noqa: E402
from draft.writer import close_spaced_numbers  # noqa: E402

FACTS = [{"value": "2,85,53,700"}]


def test_a_spaced_figure_is_closed_up_when_a_fact_has_it():
    assert close_spaced_numbers("cost of ₹2, 85, 53, 700/- in all", FACTS) == "cost of ₹2,85,53,700/- in all"


def test_a_list_of_numbers_no_fact_backs_is_left_alone():
    t = "Sections 12, 15, 28 and amounts 1, 23, 456"
    assert close_spaced_numbers(t, FACTS) == t


def test_serial_numbers_in_a_numbered_run_are_not_figures():
    t = "18. Gurmel Singh (Brother)\n\n19 Santosh Nair (Brother)\n\n22 Neena Vilku (Sister)"
    assert figures(t) == set()


def test_a_figure_starting_a_line_after_prose_still_counts():
    assert figures("Some prose here.\n\n25 Equity Shares were allotted.") == {25.0}
    assert figures("Some prose here.\n\n5,00,000 Equity Shares were allotted.") == {500000.0}


def test_a_split_regulation_list_is_not_a_set_of_figures():
    assert figures("including Chapter IX and Regulation s 17, 18, 19, 20, 21 and other provisions") == set()
