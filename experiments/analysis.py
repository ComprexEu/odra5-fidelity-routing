"""Tables 1-3 and every number quoted in the text of the paper.

    python -m experiments.analysis

Reads the raw results (``$ODRA5_RESULTS``, default ``results/raw``) and writes
``results/tables/*.tex`` (table bodies), ``results/figure_data/*.csv`` (input
of ``experiments.figures``) and ``results/key_numbers.json``. Gaps are in
percent, ``(C - C_DP) / C_DP``; per-instance values are means over seeds,
statistics are Wilcoxon signed-rank tests over instances with Holm correction.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon

from experiments.common import MAIN_MODEL, ROOT, load, problem
from odra5_router.benchmarks import GROUP_LABELS, ODRA5_SUITES, group

OUT = ROOT / "results"
TABLES = OUT / "tables"
FIGDATA = OUT / "figure_data"
KEY: dict = {}

SEARCH_SABRE = ["tabu_sabre", "ga_sabre", "rs_sabre"]
SEARCH_RANDOM = ["tabu_random", "ga_random", "rs_random"]
TABLE1 = SEARCH_SABRE + SEARCH_RANDOM + ["sabre", "qiskit_l3", "qiskit_l3_noise"]
RANDOM_GROUPS = ("tiny", "small", "medium", "heavy", "dense")
STRUCT_GROUPS = ("qaoa", "hamsim", "qv", "other")


def holm(ps):
    ps = np.asarray(ps, float)
    out = np.empty_like(ps)
    running = 0.0
    for k, i in enumerate(np.argsort(ps)):
        running = max(running, min(1.0, (len(ps) - k) * ps[i]))
        out[i] = running
    return out


def wtl(a, b, tol=1e-9):
    """How often ``a`` is lower than, equal to and higher than ``b``."""
    d = a - b
    return int((d < -tol).sum()), int((abs(d) <= tol).sum()), int((d > tol).sum())


def pvalue(a, b):
    d = (a - b).dropna()
    d = d[abs(d) > 1e-12]
    return 1.0 if len(d) < 1 else float(wilcoxon(d).pvalue)


def has_2q(index) -> list[bool]:
    return [len(problem(s, i).interactions) > 0 for s, i in index]


def per_instance(df, col="cost"):
    return df.groupby(["suite", "inst", "m"])[col].mean().unstack("m")


def gaps(wide, ref="dp"):
    return wide.sub(wide[ref], axis=0).div(wide[ref], axis=0) * 100


def r2(x) -> float:
    return round(float(x), 2)


def routing_frame(name="routing", model=MAIN_MODEL):
    df = load(name)
    df = df[(df.status == "ok") & (df.model == model)].copy()
    objective = df["objective"].fillna("fidelity") if "objective" in df else "fidelity"
    df["m"] = np.where(objective == "swaps", df.method + "@swaps", df.method)
    return df


# --- routing level ------------------------------------------------------------------

def routing():
    df = routing_frame()
    w = per_instance(df)
    w = w[has_2q(w.index)]
    dp = w["dp"]
    g = gaps(w)
    g["group"] = [group(i) for i in g.index.get_level_values("inst")]
    g.to_csv(FIGDATA / "routing_gap.csv")
    KEY["instances"] = len(w)

    runs = df.join(dp.rename("dp_cost"), on=["suite", "inst"]).dropna(subset=["dp_cost"])
    runs["gap"] = (runs.cost - runs.dp_cost) / runs.dp_cost * 100
    at_opt = runs.groupby("m").gap.apply(lambda x: float((x <= 1e-4).mean() * 100))
    time = df.groupby("m").time_s.median()

    lines = []
    for gk, label in GROUP_LABELS.items():
        x = g[g.group == gk]
        cells = " & ".join(f"{x[m].mean():.2f}" for m in TABLE1)
        lines.append(f"{label} ({len(x)}) & {w.loc[x.index, 'dp'].mean():.3f} & {cells} \\\\")
    lines += ["\\midrule",
              "Mean gap [\\%] & -- & " + " & ".join(f"{g[m].mean():.2f}" for m in TABLE1) + " \\\\",
              "Runs at optimum [\\%] & -- & " + " & ".join(f"{at_opt[m]:.0f}" for m in TABLE1) + " \\\\",
              f"Median time [s] & {time['dp']:.3f} & " + " & ".join(f"{time[m]:.3f}" for m in TABLE1) + " \\\\"]
    (TABLES / "table1_routing.tex").write_text("\n".join(lines) + "\n")

    KEY["gap"] = {m: r2(g[m].mean()) for m in w.columns}
    KEY["gap_by_group"] = {gk: {m: r2(g.loc[g.group == gk, m].mean()) for m in TABLE1} for gk in GROUP_LABELS}
    KEY["runs_at_optimum_pct"] = {m: round(at_opt[m]) for m in TABLE1}
    KEY["median_time_s"] = {m: round(float(time[m]), 3) for m in ["dp"] + TABLE1}
    dp_runs = df[df.m == "dp"].set_index(["suite", "inst"]).loc[w.index]
    slowest = dp_runs.time_s.idxmax()
    KEY["dp_time_max_s"] = dict(time=r2(dp_runs.time_s.max()), instance=slowest[1],
                                interactions=len(problem(*slowest).interactions))

    pairs = [("tabu_sabre", "ga_sabre"), ("tabu_sabre", "rs_sabre"), ("ga_sabre", "rs_sabre"),
             ("tabu_random", "ga_random"), ("tabu_random", "rs_random"), ("ga_random", "rs_random"),
             *[(m, "qiskit_l3_noise") for m in SEARCH_SABRE + SEARCH_RANDOM]]
    ps = holm([pvalue(w[a], w[b]) for a, b in pairs])
    KEY["tests"] = {f"{a} vs {b}": dict(better_equal_worse=wtl(w[a], w[b]), p_holm=float(p))
                    for (a, b), p in zip(pairs, ps)}

    # Before the polish (Section 6.2): raw gaps and raw comparisons with random search.
    raw = per_instance(df, "cost_raw").reindex(w.index)
    rg = gaps(raw.assign(dp=dp))
    KEY["gap_before_polish"] = {m: r2(rg[m].mean()) for m in SEARCH_SABRE + SEARCH_RANDOM}
    raw_pairs = [("tabu_sabre", "rs_sabre"), ("ga_sabre", "rs_sabre"), ("tabu_random", "rs_random"),
                 ("ga_random", "rs_random")]
    ps = holm([pvalue(raw[a], raw[b]) for a, b in raw_pairs])
    KEY["before_polish_vs_rs"] = {f"{a} vs {b}": dict(points=r2(rg[b].mean() - rg[a].mean()),
                                                      better_equal_worse=wtl(raw[a], raw[b]), p_holm=float(p))
                                  for (a, b), p in zip(raw_pairs, ps)}

    # Qiskit: where the presets differ from SABRE, and runs below the DP.
    KEY["qiskit_l3_differs_from_sabre"] = int((abs(w["qiskit_l3"] - w["sabre"]) > 1e-9).sum())
    q = runs[runs.m.isin(["sabre", "qiskit_l3", "qiskit_l3_noise"])]
    below = q[q.cost < q.dp_cost - 1e-9]
    KEY["qiskit_runs_below_dp"] = dict(runs=len(below), of=len(q), max_pct=r2(-below.gap.min()) if len(below) else 0)
    ours = runs[runs.m.isin(SEARCH_SABRE + SEARCH_RANDOM)]
    KEY["our_runs_below_dp"] = int((ours.cost < ours.dp_cost - 1e-9).sum())

    # The objective (Section 6.2).
    nsw = per_instance(df, "n_swaps").reindex(w.index)
    KEY["fidelity_optimum_uses_min_swaps"] = int((abs(w["dp"] - w["dp_lex"]) <= 1e-9).sum())
    KEY["mean_swaps"] = {m: r2(nsw[m].mean()) for m in ("dp", "dp_lex", "dp_blind", "sabre")}
    KEY["gap_swap_objective"] = {m: r2(g[f"{m}@swaps"].mean()) for m in ("tabu_random", "ga_random")}
    best20 = runs.groupby(["suite", "inst", "m"]).cost.min().unstack("m")
    bg = gaps(best20.assign(dp=dp))
    KEY["best_of_20_gap"] = {m: r2(bg[m].mean()) for m in ["sabre"] + SEARCH_SABRE}

    tm = df.groupby("m").agg(time=("time_s", "median")).join(g.drop(columns="group").mean().rename("gap"))
    tm.to_csv(FIGDATA / "routing_quality_time.csv")


def budget():
    """Anytime gaps after 1e4 and 5e4 evaluations without the polish (Section 6.2)."""
    df = load("budget")
    df = df[df.status == "ok"]
    dp = per_instance(routing_frame())["dp"]
    rows = []
    for r in df.itertuples():
        d = dp.get((r.suite, r.inst))
        if d is None or not problem(r.suite, r.inst).interactions:
            continue
        curve = sorted(r.anytime)
        for e in (10_000, 50_000):
            best = min(c for k, c in curve if k <= e)
            rows.append(dict(method=r.method, inst=r.inst, evals=e, gap=(best - d) / d * 100))
    a = pd.DataFrame(rows).groupby(["method", "inst", "evals"]).gap.mean().groupby(["method", "evals"]).mean()
    KEY["budget"] = {m: {"1e4": r2(a[m, 10_000]), "5e4": r2(a[m, 50_000])} for m in SEARCH_SABRE + SEARCH_RANDOM}
    KEY["budget_instances"] = int(pd.DataFrame(rows).inst.nunique())


# --- end to end ------------------------------------------------------------------------

E2E = ["preset", "dp"] + SEARCH_SABRE[:2] + SEARCH_RANDOM[:2]
E2E_LABELS = {"preset_noise": "Qiskit L3, noise-aware Target", "preset": "Qiskit L3, topology-only Target",
              "dp": "Exact DP", "tabu_sabre": "Tabu Search, SABRE start", "ga_sabre": "Genetic Algorithm, SABRE start",
              "tabu_random": "Tabu Search, random start", "ga_random": "Genetic Algorithm, random start"}


def end_to_end():
    df = load("pipeline")
    df = df[(df.status == "ok") & (df.model == MAIN_MODEL)].assign(m=lambda d: d.method)
    w = per_instance(df)
    w = w[has_2q(w.index)]
    ref = w["preset_noise"]
    rel = w.sub(ref, axis=0).div(ref, axis=0) * 100
    rel["group"] = [group(i) for i in rel.index.get_level_values("inst")]
    rel.to_csv(FIGDATA / "e2e_rel.csv")
    cz = per_instance(df, "n_cz").reindex(w.index)
    masks = {"random": rel.group.isin(RANDOM_GROUPS), "adversarial": rel.group == "hard",
             "structured": rel.group.isin(STRUCT_GROUPS)}
    methods = E2E + ["rs_sabre", "rs_random"]
    pmap = dict(zip(methods, holm([pvalue(w[m], ref) for m in methods])))

    lines = [f"{E2E_LABELS['preset_noise']} & {ref.mean():.3f} & {cz['preset_noise'].mean():.1f} & -- & -- & -- & -- & -- \\\\",
             "\\midrule"]
    for m in E2E:
        better, tie, worse = wtl(w[m], ref)
        cells = " & ".join(f"${rel.loc[mask, m].mean():+.2f}$" for mask in [slice(None), *masks.values()])
        lines.append(f"{E2E_LABELS[m]} & {w[m].mean():.3f} & {cz[m].mean():.1f} & {cells} & {better}/{tie}/{worse} \\\\")
        if m in ("dp", "ga_sabre"):
            lines.append("\\midrule")
    (TABLES / "table2_e2e.tex").write_text("\n".join(lines) + "\n")

    KEY["e2e"] = {m: dict(rel=r2(rel[m].mean()), **{k: r2(rel.loc[mask, m].mean()) for k, mask in masks.items()},
                          better_equal_worse=wtl(w[m], ref), p_holm=pmap.get(m), cost=round(float(w[m].mean()), 3),
                          cz=round(float(cz[m].mean()), 1))
                  for m in ["preset_noise"] + methods}
    KEY["e2e_noise_aware_vs_topology"] = dict(rel=r2(((ref - w["preset"]) / w["preset"] * 100).mean()),
                                              better_equal_worse=wtl(ref, w["preset"]))
    KEY["e2e_tabu_sabre_vs_dp"] = wtl(w["tabu_sabre"], w["dp"])
    est = np.exp(-w)
    gain = (est.sub(est["preset_noise"], axis=0)).div(est["preset_noise"], axis=0) * 100
    KEY["estimated_fidelity"] = {m: dict(mean=round(float(est[m].mean()), 3), gain_mean_pct=r2(gain[m].mean()),
                                         gain_median_pct=r2(gain[m].median()))
                                 for m in ["preset_noise", "dp", "tabu_sabre", "ga_sabre"]}


def noisy_simulation():
    df = load("aer")
    from experiments.run import AER_METHODS

    df = df[(df.status == "ok") & (df.model == MAIN_MODEL) & df.suite.isin(ODRA5_SUITES) & df.method.isin(AER_METHODS)]
    df = df[has_2q(zip(df.suite, df.inst))]
    df.to_csv(FIGDATA / "aer.csv", index=False)
    out = dict(circuits=int(df.groupby(["suite", "inst"]).ngroups), compilations=len(df),
               all_equivalent=bool(df.equiv.all()))
    for c in ("F_depol", "F_adonis", "F_adonis_idle"):
        w = df.pivot_table(index=["suite", "inst"], columns="method", values=c)
        out[c] = dict(spearman=round(float(spearmanr(df.proxy, df[c])[0]), 3),
                      **{m: dict(rel=r2(((w[m] - w["preset_noise"]) / w["preset_noise"] * 100).mean()),
                                 better_equal_worse=wtl(-w[m], -w["preset_noise"]))
                         for m in ["dp", "tabu_sabre", "tabu_random", "ga_sabre", "ga_random"]})
    KEY["noisy_simulation"] = out


def robustness():
    """The 13 fixed circuits under 27 further fidelity models (Section 6.3)."""
    df = load("robust_routing")
    df = df[(df.status == "ok") & (df.suite == "fixed")].assign(m=lambda d: d.method)
    family = lambda mid: "calib" if mid.startswith("calib") else mid.split("_")[0]  # noqa: E731
    w = df.groupby(["model", "inst", "m"]).cost.mean().unstack("m")
    g = gaps(w)
    g["family"] = [family(x) for x in g.index.get_level_values("model")]
    ours = ["tabu_sabre", "ga_sabre", "tabu_random", "ga_random"]
    out = {}
    for f in ("calib", "spread", "uniform"):
        x = g[g.family == f]
        out[f] = dict(models=int(x.index.get_level_values("model").nunique()),
                      **{m: r2(x[m].mean()) for m in ["dp_blind", "qiskit_l3_noise"] + ours})
    ours_means = [out[f][m] for f in out for m in ours]
    qiskit_means = [out[f]["qiskit_l3_noise"] for f in out]
    KEY["robustness"] = dict(out, ours_range=[min(ours_means), max(ours_means)],
                             qiskit_noise_range=[min(qiskit_means), max(qiskit_means)])


# --- larger stars -------------------------------------------------------------------------

SCALING_ROWS = [("dp", "Exact DP"), ("sabre", "Qiskit SABRE"), ("tabu_sabre", "TS, SABRE start"),
                ("ga_sabre", "GA, SABRE start"), ("tabu_random", "TS, random start"), ("ga_random", "GA, random start")]


def scaling():
    df = load("scaling")
    df = df[df.status == "ok"]
    key = ["n", "circ", "cal"]
    dp = df[df.method == "dp"].set_index(key)
    best = df.groupby(key).cost.min().rename("best")
    df = df.join(best, on=key).join(dp[["cost", "dp_finished"]].rename(
        columns={"cost": "dp_cost", "dp_finished": "dp_done"}), on=key)
    df["ref"] = np.where(df.dp_done == True, df.dp_cost, df.best)  # noqa: E712
    df["gap"] = 100 * (df.cost - df.ref) / df.ref
    per = df.groupby(["n", "circ", "cal", "method"]).agg(gap=("gap", "mean"), time=("time_s", "median")).reset_index()
    s = per.groupby(["n", "method"]).agg(gap=("gap", "mean"), time=("time", "median"))
    sizes = sorted(df.n.unique())
    lines = []
    for m, label in SCALING_ROWS:
        cells = []
        for n in sizes:
            if m == "dp" and not dp.loc[n].dp_finished.all():
                cells += ["--", "$>60$"]
            else:
                cells += [f"{s.loc[(n, m), 'gap']:.2f}", f"{s.loc[(n, m), 'time']:.2f}"]
        lines.append(f"{label} & " + " & ".join(cells) + " \\\\")
        if m in ("sabre", "ga_sabre"):
            lines.append("\\midrule")
    (TABLES / "table3_scaling.tex").write_text("\n".join(lines) + "\n")
    KEY["scaling"] = {f"{m}|N{n}": dict(gap=r2(s.loc[(n, m), "gap"]), time=r2(s.loc[(n, m), "time"]))
                      for m, _ in SCALING_ROWS for n in sizes if (n, m) in s.index}
    KEY["scaling_dp_finished"] = {f"N{n}": bool(dp.loc[n].dp_finished.all()) for n in sizes}
    KEY["scaling_mean_interactions"] = {f"N{n}": r2(df[df.n == n].groupby(["circ"]).n_2q.first().mean()) for n in sizes}


if __name__ == "__main__":
    for d in (TABLES, FIGDATA):
        d.mkdir(parents=True, exist_ok=True)
    steps = (routing, budget, end_to_end, noisy_simulation, robustness, scaling)
    for fn in steps:
        try:
            fn()
        except FileNotFoundError as exc:
            print(f"skipped {fn.__name__}: {exc}")
    (OUT / "key_numbers.json").write_text(json.dumps(KEY, indent=1, default=str) + "\n")
    print(f"wrote {OUT / 'key_numbers.json'} and the tables in {TABLES}")
