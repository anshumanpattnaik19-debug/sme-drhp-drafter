"""draft.writer.choose_draft: best-of-n must not reward a draft for saying less."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft.writer import choose_draft  # noqa: E402


def test_lowest_key_wins_among_drafts_of_similar_length():
    assert choose_draft([((0, 2, -3), 900), ((0, 1, -3), 1000), ((0, 1, -1), 1000)]) == 1


def test_a_much_shorter_draft_is_not_chosen_for_having_fewer_masked_values():
    assert choose_draft([((0, 0, 0), 120), ((0, 3, -5), 1000), ((0, 2, -4), 1100)]) == 2


def test_one_runaway_draft_does_not_raise_the_floor():
    assert choose_draft([((0, 1, -2), 800), ((0, 4, -2), 900), ((1, 5, 0), 6000)]) == 0


def test_single_candidate_and_empty():
    assert choose_draft([((0, 0, 0), 10)]) == 0
