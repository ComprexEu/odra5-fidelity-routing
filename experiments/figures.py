"""Fig. 2 and Fig. 3 of the paper from ``results/figure_data`` (run ``experiments.analysis`` first).

    python -m experiments.figures
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from experiments.common import ROOT  # noqa: E402

DATA = ROOT / "results" / "figure_data"
OUT = ROOT / "results" / "figures"

WIDTH = 12.2 / 2.54  # LNCS text width [in]
plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e4e3df", "grid.linewidth": 0.6, "axes.edgecolor": "#8a8984",
    "axes.axisbelow": True, "lines.linewidth": 1.4, "pdf.fonttype": 42, "ps.fonttype": 42,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
MUTED = "#52514e"
# Our methods in colour (random start dotted or hollow), Qiskit in greys and purple.
STYLE = {
    "dp": ("Exact DP", "#0b0b0b", "D"),
    "tabu_sabre": ("Tabu search, SABRE start", "#2a78d6", "o"),
    "ga_sabre": ("Genetic algorithm, SABRE start", "#eb6834", "s"),
    "rs_sabre": ("Random search, SABRE start", "#1baf7a", "^"),
    "tabu_random": ("Tabu search, random start", "#2a78d6", "o"),
    "ga_random": ("Genetic algorithm, random start", "#eb6834", "s"),
    "rs_random": ("Random search, random start", "#1baf7a", "^"),
    "sabre": ("Qiskit SABRE", "#b9b8b3", "v"),
    "qiskit_l3": ("Qiskit L3, topology-only", "#8a8984", "P"),
    "qiskit_l3_noise": ("Qiskit L3, noise-aware", "#9b3fb5", "X"),
    "preset": ("Qiskit L3, topology-only", "#8a8984", "P"),
}


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None})  # byte-identical reruns
    fig.savefig(OUT / f"{name}.png", dpi=300)
    plt.close(fig)
    print("wrote", OUT / f"{name}.pdf")


def fig_routing() -> None:
    """Fig. 2: (a) share of instances within a gap of the DP, (b) mean gap vs. median runtime."""
    g = pd.read_csv(DATA / "routing_gap.csv")
    t = pd.read_csv(DATA / "routing_quality_time.csv").set_index("m")
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH, 2.25), gridspec_kw={"width_ratios": [1.15, 1]})
    # SABRE is left out of (a): it coincides with the topology-only preset.
    for m in ("qiskit_l3", "qiskit_l3_noise", "rs_random", "ga_random", "tabu_random",
              "rs_sabre", "ga_sabre", "tabu_sabre"):
        label, colour, _ = STYLE[m]
        v = np.sort(g[m].dropna().clip(lower=0).to_numpy())
        y = np.arange(1, len(v) + 1) / len(v) * 100
        random_start = m.endswith("_random")
        a.step(np.r_[0, v], np.r_[0, y], where="post", color=colour, lw=1.3 if random_start else 1.5,
               ls=(0, (1.2, 1.2)) if random_start else "-", label=label)
    a.set_xscale("symlog", linthresh=1, linscale=0.6)
    a.set_xlim(0, 100)
    a.set_xticks([0, 0.5, 1, 2, 5, 10, 20, 50, 100], ["0", "0.5", "1", "2", "5", "10", "20", "50", "100"])
    a.set_xlabel("gap to exact DP [%]")
    a.set_ylabel("instances with at most this gap [%]")
    a.set_ylim(0, 101)
    a.set_title(f"(a) distribution over {len(g)} instances", loc="left")
    for m in ("dp", "tabu_sabre", "ga_sabre", "rs_sabre", "tabu_random", "ga_random", "rs_random",
              "sabre", "qiskit_l3", "qiskit_l3_noise"):
        label, colour, marker = STYLE[m]
        hollow = m.endswith("_random")
        b.scatter(t.loc[m, "time"], t.loc[m, "gap"], marker=marker, s=30, color="white" if hollow else colour,
                  edgecolors=colour, linewidths=1.0, zorder=3, label=label)
    b.set_xscale("log")
    b.set_xticks([0.01, 0.03, 0.1, 0.3, 1])
    b.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    b.minorticks_off()
    b.set_xlim(0.008, 1.5)
    b.set_xlabel("median runtime per instance [s], log scale")
    b.set_ylabel("mean gap to exact DP [%]")
    b.set_title("(b) quality vs. runtime", loc="left")
    handles, labels = b.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.13),
               fontsize=6.5, columnspacing=1.0, handletextpad=0.3)
    fig.tight_layout(rect=(0, 0.17, 1, 1), w_pad=1.2)
    save(fig, "fig_routing")


def fig_e2e() -> None:
    """Fig. 3: per-circuit difference to the noise-aware preset, (a) native cost, (b) simulated fidelity."""
    rel = pd.read_csv(DATA / "e2e_rel.csv")
    aer = pd.read_csv(DATA / "aer.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH, 2.3))

    def sorted_curve(ax, values, m):
        label, colour, _ = STYLE[m]
        v = np.sort(values.dropna().to_numpy())
        q = (np.arange(len(v)) + 0.5) / len(v) * 100
        ax.plot(q, v, color=colour, label=label, lw=1.5 if m == "dp" else 1.2, ls="--" if m == "preset" else "-")

    methods = ("preset", "ga_sabre", "tabu_sabre", "dp")
    for m in methods:
        sorted_curve(a, rel[m], m)
    a.axhline(0, color=MUTED, lw=0.8)
    a.set_ylim(-40, 30)
    a.set_xlim(0, 100)
    a.set_xlabel("circuits, sorted [%]")
    a.set_ylabel("difference to noise-aware L3 [%]")
    a.set_title(r"(a) native cost $C_{\mathrm{nat}}$ (lower is better)", loc="left")
    w = aer.pivot_table(index=["suite", "inst"], columns="method", values="F_adonis_idle")
    for m in methods:
        sorted_curve(b, (w[m] - w["preset_noise"]) / w["preset_noise"] * 100, m)
    b.axhline(0, color=MUTED, lw=0.8)
    b.set_xlim(0, 100)
    b.set_ylim(-15, 30)
    b.set_xlabel("circuits, sorted [%]")
    b.set_title("(b) simulated fidelity (higher is better)", loc="left")
    handles, labels = a.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.03),
               fontsize=6.5, columnspacing=1.2, handlelength=1.8)
    fig.tight_layout(rect=(0, 0.08, 1, 1), w_pad=1.2)
    save(fig, "fig_e2e")


if __name__ == "__main__":
    fig_routing()
    fig_e2e()
