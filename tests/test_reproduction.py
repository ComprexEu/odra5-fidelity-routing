"""The code reproduces stored runs of the paper's experiments exactly.

A few fast runs of each kind; ``python -m experiments.check_regression``
checks all 146 stored runs.
"""

import importlib.metadata
import json

import pytest

from experiments.check_regression import FIXTURE, compare, run_case


def test_pinned_qiskit():
    # Routes and compiled circuits depend on Qiskit's SABRE and presets.
    assert importlib.metadata.version("qiskit") == "1.2.4"


def quick_cases():
    cases = json.loads(FIXTURE.read_text())
    picked = {}
    for c in cases:
        t = c["task"]
        kind = (c["experiment"], t["method"])
        slow = t.get("max_evals", 10_000) > 10_000 or c["experiment"] in ("aer", "scaling") \
            or t.get("suite") == "algorithmic"
        if not slow and kind not in picked:
            picked[kind] = c
    return list(picked.values())


@pytest.mark.parametrize("case", quick_cases(), ids=lambda c: c["name"])
def test_stored_run_is_reproduced(case, tmp_path, monkeypatch):
    monkeypatch.setattr("experiments.common.RAW", tmp_path)
    monkeypatch.setattr("experiments.tasks.RAW", tmp_path)
    assert compare(case, run_case(case)) == []
