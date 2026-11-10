"""One run of a method on one instance (top-level functions, so they pickle into worker processes).

Method names:

- ``dp``, ``dp_lex`` (fewest SWAPs, then lowest cost), ``dp_blind`` (fewest
  SWAPs without error data: a uniform fidelity model);
- ``<algorithm>_<start>``: ``rs``/``tabu``/``ga`` with start ``random``,
  ``sabre`` or ``lookahead``, e.g. ``tabu_sabre``;
- routing level only: ``sabre`` and the layout and routing stages of the
  level-3 preset, ``qiskit_l3`` (topology-only Target) and ``qiskit_l3_noise``;
- end to end only: the unmodified level-3 preset, ``preset`` and ``preset_noise``.
"""

from __future__ import annotations

import time

from experiments.common import RAW, models, problem, suite


def make_router(method: str, model, task: dict):
    from odra5_router.exact_dp import ExactDP
    from odra5_router.search import SearchRouter

    if method == "dp":
        return ExactDP(fidelity=model)
    if method == "dp_lex":
        return ExactDP(fidelity=model, primary="swaps")
    if method == "dp_blind":
        return ExactDP(fidelity=models()["uniform"])
    algorithm, start = method.split("_")
    return SearchRouter(algorithm=algorithm, start=start, fidelity=model,
                        objective=task.get("objective", "fidelity"),
                        max_evals=task.get("max_evals", 10_000), polish=task.get("polish", True),
                        **task.get("params", {}))


def routing_task(t: dict) -> list[dict]:
    """Routing level: route the reduced circuit, score the routed circuit after cancellation."""
    from qiskit.converters import circuit_to_dag

    from odra5_router.cancel import cancel_adjacent
    from odra5_router.fidelity import fidelity_cost
    from odra5_router.pipeline import qiskit_route, sabre_route
    from odra5_router.problem import routed_cost, solution_cost, validate

    model = models()[t["model"]]
    prob = problem(t["suite"], t["inst"])
    row = dict(t)
    t0 = time.perf_counter()
    if t["method"] in ("sabre", "qiskit_l3", "qiskit_l3_noise"):
        if t["method"] == "sabre":
            qc = sabre_route(prob, t["seed"])
        else:
            qc = qiskit_route(prob.circuit, model=model if t["method"] == "qiskit_l3_noise" else None, seed=t["seed"])
        row["time_s"] = time.perf_counter() - t0
        row["cost"] = fidelity_cost(cancel_adjacent(qc), model)
        row["n_swaps"] = sum(1 for n in circuit_to_dag(qc).op_nodes() if n.op.name == "swap")
        row["status"] = "ok"
        return [row]

    router = make_router(t["method"], model, t)
    sol = router.solve(prob, seed=t["seed"], budget_s=t.get("budget_s", 120.0))
    row["time_s"] = time.perf_counter() - t0
    validate(prob, sol)
    row["cost"] = routed_cost(prob, sol, model)
    row["cost_uncancelled"] = solution_cost(prob, sol, model)
    row["n_swaps"] = len(sol.swaps)
    row["n_2q"] = len(prob.interactions)
    stats = getattr(router, "last_stats", None)
    if stats:
        raw = router.last_raw_solution
        row["cost_raw"] = routed_cost(prob, raw, model)
        row["n_swaps_raw"] = len(raw.swaps)
        for k in ("evals", "evals_polish", "iterations", "restarts", "time_search_s", "deadline_hit"):
            row[k] = stats.get(k)
        if t.get("anytime"):
            row["anytime"] = stats["anytime"]
    row["status"] = "ok"
    return [row]


def pipeline_task(t: dict) -> list[dict]:
    """End to end: compile with the level-3 preset, our router in place of layout and routing."""
    from odra5_router.fidelity import fidelity_cost
    from odra5_router.pipeline import compile_circuit

    model = models()[t["model"]]
    circ = suite(t["suite"])[t["inst"]]
    m = t["method"]
    router = None if m in ("preset", "preset_noise") else make_router(m, model, t)
    t0 = time.perf_counter()
    qc = compile_circuit(circ, router, model=None if m == "preset" else model, seed=t["seed"],
                         budget_s=t.get("budget_s", 120.0))
    row = dict(t)
    row["time_s"] = time.perf_counter() - t0
    ops = qc.count_ops()
    row["cost"] = fidelity_cost(qc, model)
    row["n_cz"] = int(ops.get("cz", 0))
    row["n_1q"] = int(ops.get("r", 0))
    row["depth"] = qc.depth()
    row["status"] = "ok"
    if t.get("save_qpy"):
        from qiskit import qpy

        path = RAW / "compiled" / t["model"] / f"{t['inst']}__{m}__s{t['seed']}.qpy"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            qpy.dump(qc, f)
        row["qpy"] = str(path.relative_to(RAW))
    return [row]


def scaling_task(t: dict) -> list[dict]:
    """Larger-star test: one method on one star circuit under one fidelity model."""
    from qiskit.converters import circuit_to_dag

    from odra5_router.benchmarks import star_model, star_problem
    from odra5_router.cancel import cancel_adjacent
    from odra5_router.fidelity import fidelity_cost
    from odra5_router.pipeline import sabre_route
    from odra5_router.problem import routed_cost, validate

    prob = star_problem(t["n"], t["circ"])
    model = star_model(t["n"], t["cal"])
    row = dict(t, n_2q=len(prob.interactions))
    t0 = time.perf_counter()
    if t["method"] == "sabre":
        qc = sabre_route(prob, t["seed"])
        row["time_s"] = time.perf_counter() - t0
        row["cost"] = fidelity_cost(cancel_adjacent(qc), model)
        row["n_swaps"] = sum(1 for x in circuit_to_dag(qc).op_nodes() if x.op.name == "swap")
        row["status"] = "ok"
        return [row]
    router = make_router(t["method"], model, t)
    try:
        sol = router.solve(prob, seed=t["seed"], budget_s=t.get("budget_s", 300.0))
    except TimeoutError:
        row.update(time_s=time.perf_counter() - t0, dp_finished=False, status="ok")
        return [row]
    row["time_s"] = time.perf_counter() - t0
    if t["method"] == "dp":
        row["dp_finished"] = True
    validate(prob, sol)
    row["cost"] = routed_cost(prob, sol, model)
    row["n_swaps"] = len(sol.swaps)
    row["status"] = "ok"
    return [row]


def aer_task(t: dict) -> list[dict]:
    from experiments.noisy_simulation import simulate

    return [simulate(t)]
