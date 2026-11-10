"""All experiments of the paper.

    python -m experiments.run tune|routing|pipeline|budget|robust|aer|scaling|all

Results go to ``$ODRA5_RESULTS`` (default ``results/raw``); every step can be
interrupted and restarted. ``all`` runs them in the order listed, which is
also the order they depend on each other (``aer`` simulates circuits saved by
``pipeline``).
"""

from __future__ import annotations

import itertools
import json
import sys

from experiments.common import MAIN_MODEL, RAW, instances, models, run_tasks
from experiments.tasks import aer_task, pipeline_task, routing_task, scaling_task
from odra5_router.benchmarks import ODRA5_SUITES, STAR_CIRCUITS, STAR_MODELS, STAR_SIZES

SEARCH = [f"{a}_{s}" for a in ("rs", "tabu", "ga") for s in ("random", "sabre")]
QISKIT_ROUTING = ("sabre", "qiskit_l3", "qiskit_l3_noise")
SEEDS = range(20)


def _routing_tasks(model, suites, seeds, methods, swaps_objective=(), singles=("dp", "dp_lex", "dp_blind")):
    tasks = []
    for s, i in instances(suites):
        base = dict(suite=s, inst=i, model=model)
        for m in singles:
            tasks.append(dict(base, key=f"{m}|{s}|{i}|{model}|0", method=m, seed=0))
        for seed in seeds:
            for m in QISKIT_ROUTING:
                tasks.append(dict(base, key=f"{m}|{s}|{i}|{model}|{seed}", method=m, seed=seed))
            for m in methods:
                for obj in ("fidelity", "swaps") if m in swaps_objective else ("fidelity",):
                    tasks.append(dict(base, key=f"{m}|{obj}|{s}|{i}|{model}|{seed}", method=m, objective=obj,
                                      seed=seed))
    return tasks


def routing():
    """Table 1, Fig. 2 and the objective ablation (Sections 6.1, 6.2)."""
    tasks = _routing_tasks(MAIN_MODEL, ODRA5_SUITES, SEEDS, SEARCH, swaps_objective=("tabu_random", "ga_random"))
    run_tasks(tasks, routing_task, "routing")


AER_METHODS = ("preset", "preset_noise", "dp") + tuple(SEARCH)


def _pipeline_tasks(model, suites, seeds, methods, save_qpy=False):
    return [dict(key=f"{m}|{s}|{i}|{model}|{seed}", suite=s, inst=i, model=model, method=m, seed=seed,
                 save_qpy=save_qpy and seed == 0 and m in AER_METHODS)
            for s, i in instances(suites) for seed in seeds for m in methods]


def pipeline():
    """Table 2 and Fig. 3(a) (Section 6.3)."""
    methods = ("preset", "preset_noise", "dp") + tuple(SEARCH)
    run_tasks(_pipeline_tasks(MAIN_MODEL, ODRA5_SUITES, SEEDS, methods, save_qpy=True), pipeline_task, "pipeline")


def budget():
    """Larger budget without the polish (Section 6.2): anytime curves up to 5e4 evaluations."""
    tasks = [dict(key=f"{m}|{s}|{i}|{seed}", suite=s, inst=i, model=MAIN_MODEL, method=m, seed=seed,
                  max_evals=50_000, polish=False, anytime=True)
             for s, i in instances(("fixed", "random")) for seed in range(10) for m in SEARCH]
    run_tasks(tasks, routing_task, "budget")


def robust():
    """Other fidelity models on the 13 fixed circuits (Section 6.3, "Other fidelity models")."""
    methods = ("tabu_sabre", "ga_sabre", "rs_sabre", "tabu_random", "ga_random", "rs_random")
    for mid in models():
        if mid == MAIN_MODEL:
            continue
        run_tasks(_routing_tasks(mid, ("fixed",), range(5), methods), routing_task, "robust_routing")
        run_tasks(_pipeline_tasks(mid, ("fixed",), range(3),
                                  ("preset", "preset_noise", "dp", "tabu_sabre", "ga_sabre", "tabu_random", "ga_random")),
                  pipeline_task, "robust_pipeline")


def aer():
    """Noisy simulation of the seed-0 compilations saved by ``pipeline`` (Fig. 3(b))."""
    rows = [json.loads(line) for line in (RAW / "pipeline.jsonl").open() if line.strip()]
    tasks = [dict(key=r["key"], suite=r["suite"], inst=r["inst"], model=r["model"], method=r["method"],
                  seed=r["seed"], qpy=r["qpy"]) for r in rows if r.get("qpy") and r.get("status") == "ok"]
    run_tasks(tasks, aer_task, "aer")


# Parameters of the lookahead start, tuned like the others (Section 4.3).
LOOKAHEAD_PARAMS = {"tabu": dict(stagnation=100), "ga": dict(population=160, mutation_rate=0.5), "rs": {}}


def scaling():
    """Synthetic stars with N = 5..8 qubits (Table 3, Section 6.4)."""
    tasks = []
    for n, c, cal in itertools.product(STAR_SIZES, STAR_CIRCUITS, STAR_MODELS):
        base = dict(n=n, circ=c, cal=cal)
        tasks.append(dict(base, key=f"dp|{n}|{c}|{cal}", method="dp", seed=0, budget_s=60.0))
        for seed in range(5):
            tasks.append(dict(base, key=f"sabre|{n}|{c}|{cal}|{seed}", method="sabre", seed=seed))
            for alg in ("rs", "tabu", "ga"):
                for start in ("random", "sabre", "lookahead"):
                    params = LOOKAHEAD_PARAMS[alg] if start == "lookahead" else {}
                    m = f"{alg}_{start}"
                    tasks.append(dict(base, key=f"{m}|{n}|{c}|{cal}|{seed}", method=m, seed=seed, params=params))
    tasks.sort(key=lambda t: t["method"] != "dp")  # the long DP runs first
    run_tasks(tasks, scaling_task, "scaling")


TABU_GRID = [dict(candidates=c, tenure=t, stagnation=s) for c, t, s in itertools.product((8, 16, 32), (3, 7), (100, 400))]
TABU_GRID += [dict(candidates=c, tenure=7, stagnation=s) for c, s in itertools.product((2, 4, 6), (100, 400))]
GA_GRID = [dict(population=p, mutation_rate=m, crossover_rate=x)
           for p, m, x in itertools.product((20, 40, 80), (0.1, 0.3), (0.7, 0.9))]
GA_GRID += [dict(population=p, mutation_rate=m, crossover_rate=0.9) for p, m in itertools.product((80, 160), (0.4, 0.5, 0.7))]


def tune():
    """Parameter selection on the tuning split (Section 4.3).

    18 configurations per algorithm, 5 seeds, 10^4 evaluations, random start
    with plain random initial orders, synthetic model ``calib_00``. A
    configuration is scored by its mean gap to the DP before the polish
    (the polish is shared and would hide the differences). Writes
    ``tuned.json`` and ``tune_report.csv`` next to the raw results.
    """
    import pandas as pd

    model = "calib_00"
    insts = [i for _, i in instances(("tuning",))]
    tasks = [dict(key=f"dp|{i}", suite="tuning", inst=i, model=model, method="dp", seed=0) for i in insts]
    for alg, grid in (("tabu", TABU_GRID), ("ga", GA_GRID)):
        for cfg, params in enumerate(grid):
            for i in insts:
                for seed in range(5):
                    tasks.append(dict(key=f"{alg}|{cfg}|{i}|{seed}", suite="tuning", inst=i, model=model,
                                      method=f"{alg}_random", seed=seed, cfg=cfg,
                                      params=dict(params, local_order=False)))
    run_tasks(tasks, routing_task, "tune")

    rows = [json.loads(line) for line in (RAW / "tune.jsonl").open() if line.strip()]
    df = pd.DataFrame(rows)
    ref = df[df.method == "dp"].set_index("inst")["cost"]
    df = df[df.method != "dp"].copy()
    df["gap"] = (df["cost"] - df["inst"].map(ref)) / df["inst"].map(ref)
    df["gap_raw"] = (df["cost_raw"] - df["inst"].map(ref)) / df["inst"].map(ref)
    report = (df.groupby(["method", "cfg"])
              .agg(mean_gap_raw=("gap_raw", "mean"), mean_gap=("gap", "mean"), params=("params", "first"))
              .reset_index().sort_values(["method", "mean_gap_raw", "mean_gap"]))
    report.to_csv(RAW / "tune_report.csv", index=False)
    tuned = {}
    for method, g in report.groupby("method"):
        params = dict(g.iloc[0]["params"])
        params.pop("local_order")
        tuned[method.split("_")[0]] = params
    (RAW / "tuned.json").write_text(json.dumps(tuned, indent=2) + "\n")
    print(json.dumps(tuned, indent=2))


STEPS = {"tune": tune, "routing": routing, "pipeline": pipeline, "budget": budget, "robust": robust,
         "aer": aer, "scaling": scaling}

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what not in STEPS and what != "all":
        sys.exit(f"unknown step {what!r}; choose from {', '.join(STEPS)} or all")
    for name, fn in STEPS.items():
        if what in (name, "all"):
            fn()
