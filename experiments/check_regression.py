"""Rerun the runs stored in ``tests/data/regression.json`` and compare them with the stored values.

    python -m experiments.check_regression            # all 146 runs (a few minutes)
    python -m experiments.check_regression routing    # one experiment only

The stored runs are a random sample of every experiment of the paper (taken
from the raw results the paper's numbers were computed from), so a clean pass
means this code reproduces them exactly.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "data" / "regression.json"
FIELDS = ("cost", "cost_raw", "n_swaps", "n_cz", "F_depol", "F_adonis", "F_adonis_idle", "proxy", "dp_finished")


def run_case(case: dict) -> dict:
    from experiments import tasks

    t = dict(case["task"])
    exp = case["experiment"]
    if exp == "scaling":
        return tasks.scaling_task(t)[0]
    if exp in ("pipeline", "robust_pipeline"):
        return tasks.pipeline_task(t)[0]
    if exp == "aer":
        compiled = tasks.pipeline_task(dict(t, save_qpy=True))[0]
        return tasks.aer_task(dict(t, qpy=compiled["qpy"]))[0]
    return tasks.routing_task(t)[0]


def compare(case: dict, got: dict) -> list[str]:
    bad = []
    for k in FIELDS:
        if k in case["expected"] and case["expected"][k] != got.get(k):
            bad.append(f"{k}: stored {case['expected'][k]!r}, got {got.get(k)!r}")
    exp_any = case["expected"].get("anytime")
    if isinstance(exp_any, list) and [list(x) for x in exp_any] != [list(x) for x in got.get("anytime", [])]:
        bad.append("anytime curve differs")
    return bad


def main() -> int:
    os.environ.setdefault("ODRA5_RESULTS", tempfile.mkdtemp(prefix="odra5-regression-"))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cases = [c for c in json.loads(FIXTURE.read_text()) if only in (None, c["experiment"])]
    failures = 0
    for c in cases:
        bad = compare(c, run_case(c))
        print(("FAIL " if bad else "ok   ") + f"{c['experiment']:16s} {c['name']}")
        for b in bad:
            print("       " + b)
        failures += bool(bad)
    print(f"{len(cases) - failures}/{len(cases)} runs reproduced exactly")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
