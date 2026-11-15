"""The objects-section QC: a deployment row whose two year amounts do not add up to its total is reported."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vm"))

import h5_qc  # noqa: E402


def _sec(text):
    return {"blocks": [{"type": "paragraph", "text": text}]}


def test_a_row_that_adds_up_is_not_reported():
    assert h5_qc.reconcile(_sec("1. Purchase and installation of plant and machinery 1,244.00 616.00 1860")) == []


def test_a_row_that_does_not_add_up_is_reported():
    found = h5_qc.reconcile(_sec("Total (excluding general corporate purposes) 1,244.00 2586.00 4,230.00"))
    assert len(found) == 1 and "3,830.00" in found[0] and "4,230.00" in found[0]


def test_a_dash_counts_as_zero():
    assert h5_qc.reconcile(_sec("Installation of a plant - - 520")) != []
    assert h5_qc.reconcile(_sec("Installation of a plant 500.00 - 500")) == []
