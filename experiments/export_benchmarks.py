"""Write every benchmark instance and fidelity model to ``benchmarks/``.

    python -m experiments.export_benchmarks

- ``odra5/<group>/<name>.qasm``: the 104 circuits of the Odra5 benchmark,
- ``tuning/<name>.qasm``: the 25 tuning circuits,
- ``stars/N<n>/c<k>.qasm``: the circuits of the larger-star test,
- ``fidelity_models.json``: every fidelity model,
- ``manifest.json`` and ``README.md``: where every instance comes from.

The circuits are OpenQASM 2.0 as given to the compiler, before the adjacent
CX pairs are cancelled.
"""

from __future__ import annotations

import json

from qiskit import qasm2

from experiments.common import ROOT, models, problem, suite
from odra5_router.benchmarks import (
    FIXED_RANDOM,
    GROUP_LABELS,
    ODRA5_SUITES,
    SIZE_CLASSES,
    STAR_CIRCUITS,
    STAR_MODELS,
    STAR_SIZES,
    group,
    star_circuit,
    star_model,
    star_problem,
)

OUT = ROOT / "benchmarks"

KNOWN = {
    "ghz_5q": "GHZ state (H and a CX chain)",
    "qft_5q": "Qiskit QFT(5, do_swaps=False)",
    "aqft_5q": "Qiskit QFT(5, approximation_degree=2, do_swaps=False)",
    "w_state_5q": "W state (RY and a controlled-H cascade)",
    "bv_5q": "Bernstein-Vazirani, secret 1011",
    "grover_4q": "Grover search on 4 qubits with an ancilla, 1 iteration",
    "grover_4q_it3": "Grover search on 4 qubits with an ancilla, 3 iterations",
    "adder_1bit_5q": "1-bit full adder (CCX, CX)",
    "qft_adder_2b": "Qiskit DraperQFTAdder(2, kind='fixed') on the inputs 01 and 11",
    "queko_d32": "QUEKO (Tan and Cong) on the Odra5 graph, depth 32, densities (0.25, 0.3), seed 0; "
                 "known zero-SWAP layout",
}


def source(name: str) -> str:
    fixed = {n: (s, g, p) for n, s, g, p in FIXED_RANDOM}
    if name in fixed:
        s, g, p = fixed[name]
        return f"random_circuit(n=5, num_gates={g}, p_two_qubit={p}, seed={s})"
    if name.startswith("hard_"):
        return f"adversarial_circuit(rounds={name[5:-1]}): one CX on each of the six leaf pairs per round"
    cls = name.split("_")[0]
    if cls in SIZE_CLASSES and "_s" in name:
        g, p = SIZE_CLASSES[cls]
        return f"random_circuit(n=5, num_gates={g}, p_two_qubit={p}, seed={name.split('_s')[1]})"
    if name in KNOWN:
        return KNOWN[name]
    if name.startswith("qv_5q_s"):
        return f"Qiskit QuantumVolume(5, depth=5, seed={name.split('_s')[1]})"
    if name.startswith("qaoa_g"):
        g, p = name[6:].split("_p")
        return f"QAOA MaxCut, p={p}, random 5-node graph (edge probability 0.5, seed {300 + int(g)}), gamma=0.39, beta=0.25"
    if name.startswith("qaoa_k5"):
        return f"QAOA MaxCut on the complete graph K5, p={name[-1]}"
    if name.startswith("qaoa_ring"):
        return "QAOA MaxCut on the 5-cycle, p=6"
    if name.startswith("heisenberg_ring"):
        return f"Heisenberg XXX model on a 5-ring, first-order Trotter, {name[-1]} steps, dt=0.1"
    if name.startswith("ising_full"):
        return f"transverse-field Ising model with all-to-all ZZ couplings, first-order Trotter, {name[-1]} steps"
    if name.startswith("vqe_su2_full"):
        return f"Qiskit EfficientSU2(5, reps={name.split('_r')[-1]}, entanglement='full'), fixed random parameters"
    raise KeyError(name)


def write(rel: str, qc) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(qasm2.dumps(qc))


def main() -> None:
    manifest = {"odra5": [], "tuning": [], "stars": []}
    for s in ODRA5_SUITES:
        for name, qc in suite(s).items():
            prob = problem(s, name)
            rel = f"odra5/{group(name)}/{name}.qasm"
            write(rel, qc)
            manifest["odra5"].append(dict(
                name=name, group=GROUP_LABELS[group(name)], file=rel, source=source(name),
                gates=sum(v for k, v in qc.count_ops().items() if k not in ("measure", "barrier")),
                two_qubit_after_reduction=len(prob.interactions), depth_after_reduction=prob.circuit.depth(),
                in_paper=bool(prob.interactions)))
    for name, qc in suite("tuning").items():
        rel = f"tuning/{name}.qasm"
        write(rel, qc)
        manifest["tuning"].append(dict(name=name, file=rel, source=source(name)))
    for n in STAR_SIZES:
        for k in STAR_CIRCUITS:
            rel = f"stars/N{n}/c{k}.qasm"
            write(rel, star_circuit(n, k))
            manifest["stars"].append(dict(N=n, name=f"N{n}_c{k}", file=rel,
                                          source=f"random_circuit(n={n}, num_gates=40, p_two_qubit=0.7, seed={k}) "
                                                 f"on a star with hub 0 and leaves 1..{n - 1}",
                                          two_qubit_after_reduction=len(star_problem(n, k).interactions)))

    fm = {mid: m.to_json() for mid, m in models().items()}
    for n in STAR_SIZES:
        for k in STAR_MODELS:
            fm[f"star_N{n}_model{k}"] = star_model(n, k).to_json()
    (OUT / "fidelity_models.json").write_text(json.dumps(fm, indent=1) + "\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")

    lines = ["# Benchmark circuits", "",
             "Written by `python -m experiments.export_benchmarks` from `src/odra5_router/benchmarks.py`.",
             "The circuits are OpenQASM 2.0 as given to the compiler, before adjacent CX pairs are cancelled.",
             "`random_circuit(n, g, p, seed)` draws `g` steps; each step is a CX on a random pair of qubits with",
             "probability `p`, otherwise an H and an RZ with a random angle on random qubits.",
             "`fidelity_models.json` holds every fidelity model; `adonis` is the main one.", "",
             "## Odra5 benchmark (103 circuits with two-qubit gates)", "",
             "| Name | Group | 2Q gates after reduction | Depth | Source |", "|---|---|---|---|---|"]
    for r in manifest["odra5"]:
        note = "" if r["in_paper"] else " (not used: no two-qubit gate after reduction)"
        lines.append(f"| `{r['name']}` | {r['group']} | {r['two_qubit_after_reduction']} | "
                     f"{r['depth_after_reduction']} | {r['source']}{note} |")
    lines += ["", "## Tuning split (25 circuits, disjoint from the benchmark)", "",
              "| Name | Source |", "|---|---|"]
    lines += [f"| `{r['name']}` | {r['source']} |" for r in manifest["tuning"]]
    lines += ["", "## Larger stars (N = 5..8)", "",
              "10 circuits per size and 5 fidelity models per size (`star_N<n>_model<k>` in",
              "`fidelity_models.json`, f_1Q in [0.991, 0.995], f_2Q in [0.945, 0.970]).", "",
              "| Name | 2Q gates after reduction | Source |", "|---|---|---|"]
    lines += [f"| `{r['name']}` | {r['two_qubit_after_reduction']} | {r['source']} |" for r in manifest["stars"]]
    (OUT / "README.md").write_text("\n".join(lines) + "\n")
    print("wrote", OUT, {k: len(v) for k, v in manifest.items()}, len(fm), "fidelity models")


if __name__ == "__main__":
    main()
