"""Shared pieces of the experiments: instances, fidelity models and the parallel runner.

Every experiment appends one JSON line per run to ``$ODRA5_RESULTS/<name>.jsonl``
(default ``results/raw``). Runs are identified by a key, so an interrupted
experiment continues where it stopped when started again.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(os.environ.get("ODRA5_RESULTS", ROOT / "results" / "raw"))
WORKERS = int(os.environ.get("ODRA5_WORKERS", os.cpu_count() or 1))

# One thread per worker process; Qiskit's own thread pool would oversubscribe the CPUs.
os.environ.setdefault("QISKIT_PARALLEL", "FALSE")
os.environ.setdefault("RAYON_NUM_THREADS", "1")

MAIN_MODEL = "adonis"


@lru_cache(maxsize=None)
def suite(name: str) -> dict:
    """``{instance name: circuit}`` of a benchmark suite."""
    from odra5_router.benchmarks import SUITES

    return dict(SUITES[name]())


@lru_cache(maxsize=None)
def problem(suite_name: str, inst: str):
    """The routing problem of an instance: its circuit after input reduction."""
    from odra5_router.cancel import reduce_input
    from odra5_router.problem import make_problem

    return make_problem(reduce_input(suite(suite_name)[inst]))


@lru_cache(maxsize=None)
def models() -> dict:
    from odra5_router.benchmarks import fidelity_models

    return fidelity_models()


def instances(suites):
    for s in suites:
        for i in suite(s):
            yield s, i


def _done_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as f:
        return {json.loads(line)["key"] for line in f if line.strip()}


def run_tasks(tasks: list[dict], fn, name: str, *, workers: int = WORKERS) -> Path:
    """Run ``fn(task) -> list[dict]`` for every task not yet in ``<name>.jsonl``."""
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"{name}.jsonl"
    done = _done_keys(out)
    todo = [t for t in tasks if t["key"] not in done]
    print(f"[{name}] {len(tasks)} runs, {len(tasks) - len(todo)} already done", flush=True)
    if not todo:
        return out
    t0 = time.time()
    # spawn, not fork: forking after Qiskit has started its thread pool can deadlock.
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(workers, mp_context=ctx) as ex, out.open("a") as f:
        futures = {ex.submit(fn, t): t for t in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            t = futures[fut]
            try:
                rows = fut.result()
            except Exception as exc:  # record the failure and keep going
                rows = [{**t, "status": "failed", "error": repr(exc)}]
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.flush()
            if i % max(1, len(todo) // 20) == 0 or i == len(todo):
                el = time.time() - t0
                print(f"[{name}] {i}/{len(todo)}  {el:.0f} s, about {el / i * (len(todo) - i):.0f} s left", flush=True)
    return out


def load(name: str):
    import pandas as pd

    return pd.read_json(RAW / f"{name}.jsonl", lines=True)
