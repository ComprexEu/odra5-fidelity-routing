# odra5-fidelity-routing

Code and benchmarks accompanying our paper on fidelity-aware quantum circuit transpilation for Odra5.

Odra5 is a five-qubit IQM Spark processor at Wrocław University of Science and Technology. Its qubits
form a star: one hub coupled to four leaves. Every SWAP goes through the hub, and the four couplers have
different error rates. Two routes with the same number of SWAPs can therefore differ noticeably in
expected fidelity. This repository routes circuits for Odra5 by minimizing the accumulated negative
log-fidelity `C = Σ −ln f_g` over all gates instead of the SWAP count. It contains:

- **Tabu Search** and a **Genetic Algorithm** that share one solution encoding, one set of moves, one
  evaluation budget and one final local search, plus **random search** over the same components as a
  control. They start either from random solutions or from routes of Qiskit's SABRE.
- An **exact dynamic-programming router** (Dijkstra over hub schedules). It gives the optimum of the
  routing stage and is the reference all gaps in the paper are measured against.
- A Qiskit pass that puts any of these routers into Qiskit's level-3 preset pass manager in place of its
  layout and routing stages. Everything else stays Qiskit's own.
- The scripts that produce every table, figure and number of the paper, and the 103 benchmark circuits
  as OpenQASM.

## Installation

Python 3.11 or newer. Qiskit is pinned to 1.2.4, because routes and compiled circuits depend on
Qiskit's SABRE and presets, and qiskit-iqm to 17.8, which supplies the error data.

```bash
git clone https://github.com/ComprexEu/odra5-fidelity-routing.git
cd odra5-fidelity-routing
python -m venv .venv && . .venv/bin/activate
pip install -e ".[experiments,dev]"
pytest
```

`requirements-lock.txt` lists the exact versions of all packages that reproduce the paper's results
(`pip install -r requirements-lock.txt` before `pip install -e .` to get the same environment).

## Usage

```python
from qiskit import QuantumCircuit
from odra5_router import ExactDP, SearchRouter, adonis_model, compile_circuit, fidelity_cost

qc = QuantumCircuit(5)
qc.h(0)
for a, b in [(0, 1), (1, 3), (3, 4), (0, 4), (1, 4)]:
    qc.cx(a, b)

model = adonis_model()                       # gate fidelities of IQM's fake Adonis
tabu = SearchRouter(algorithm="tabu", start="sabre", fidelity=model)
for name, router in [("Qiskit L3", None), ("Tabu Search", tabu), ("exact DP", ExactDP(fidelity=model))]:
    out = compile_circuit(qc, router, model=model, seed=0)
    print(f"{name:12s} cost {fidelity_cost(out, model):.4f}  CZ {out.count_ops().get('cz', 0)}")
```

```
Qiskit L3    cost 0.1945  CZ 8
Tabu Search  cost 0.1734  CZ 8
exact DP     cost 0.1734  CZ 8
```

`compile_circuit` returns a circuit in Odra5's native gates `{r, cz}`. With `router=None` it is Qiskit's
unmodified level-3 preset. With `model` the Qiskit Target carries the gate errors (noise-aware);
without it, only the topology. To route without the rest of the pipeline, build a problem with
`make_problem(circuit)` and call `router.solve(problem)`. The result is an initial layout, an
execution order and a SWAP schedule; `apply(problem, solution)` turns it into a circuit.

For your own device data, construct a `FidelityModel` with the single-qubit fidelity of every qubit
and the two-qubit fidelity of every coupler. The code works on any star with the hub of highest
degree (`star_coupling_map(n)`); the exact DP becomes impractical beyond about seven qubits.

## Reproducing the paper

```bash
python -m experiments.run all          # all experiments, raw results in results/raw/
python -m experiments.analysis         # tables and every number of the text
python -m experiments.figures          # Fig. 2 and Fig. 3
```

| Step | Paper | Output |
|---|---|---|
| `run tune` | parameters of Section 4.3 | `results/raw/tuned.json` |
| `run routing` | Table 1, Fig. 2, Section 6.2 | `results/tables/table1_routing.tex` |
| `run budget` | larger budget, Section 6.2 | `key_numbers.json` → `budget` |
| `run pipeline`, `run aer` | Table 2, Fig. 3, noisy simulation | `results/tables/table2_e2e.tex` |
| `run robust` | other fidelity models, Section 6.3 | `key_numbers.json` → `robustness` |
| `run scaling` | Table 3, Section 6.4 | `results/tables/table3_scaling.tex` |

Each step can be run alone (`python -m experiments.run routing`) and continues where it stopped
if interrupted. `ODRA5_WORKERS` sets the number of processes (default: all CPUs), and
`ODRA5_RESULTS` sets the directory for raw results. On an AMD Ryzen 7 5700U (8 cores, 16 threads) the whole
run takes about 80 minutes.

`results/` contains the tables, figures and `key_numbers.json` of the paper. A fresh
`experiments.run all` reproduces every number of the paper exactly; only the runtimes depend on
the machine.

`python -m experiments.check_regression` reruns 146 runs sampled from all experiments and checks
that they reproduce the stored values exactly. A few of them also run as part of `pytest`.

## Benchmarks

`benchmarks/` holds every circuit as OpenQASM 2.0, as given to the compiler:

- `odra5/`: 104 circuits in 10 groups (random circuits in five sizes, adversarial circuits, QAOA,
  Hamiltonian simulation, Quantum Volume, and other algorithms such as QFT, Grover, adders, a
  variational ansatz and a QUEKO circuit with a known zero-SWAP layout). One random circuit has no
  two-qubit gate after cancellation, which leaves the 103 circuits of the paper.
- `tuning/`: the 25 circuits on which the parameters were selected, disjoint from the benchmark.
- `stars/`: the circuits of the larger-star test (N = 5…8 qubits).
- `fidelity_models.json`: all fidelity models; `adonis` is the main one.

`benchmarks/README.md` and `manifest.json` give the source, generator and parameters of every
instance. `python -m experiments.export_benchmarks` regenerates the directory from
`src/odra5_router/benchmarks.py`.

The error data are not Odra5 calibration data. They come from `IQMFakeAdonis` in qiskit-iqm 17.8,
IQM's fake backend for the same five-qubit star. `adonis_model()` converts the depolarizing parameters
of its error profile to average gate fidelities; the noisy simulation uses the backend's Aer noise
model and its T1, T2 and gate durations.

## Repository layout

```
src/odra5_router/
  topology.py      Odra5 and N-qubit stars, Qiskit Targets with and without error data
  fidelity.py      FidelityModel, the cost of Eq. 2, the IQMFakeAdonis and synthetic models
  problem.py       routing problem and solution, placement of single-qubit gates, apply, validate
  cancel.py        cancellation of adjacent self-inverse two-qubit gates
  encoding.py      the (layout, order, routing decisions) encoding and its decoder
  search.py        random search, Tabu Search, Genetic Algorithm, polish
  exact_dp.py      exact routing by Dijkstra's algorithm
  pipeline.py      routers inside Qiskit's level-3 pass manager; Qiskit baselines
  benchmarks.py    the paper's circuits and fidelity models
  circuits/        random and adversarial circuits, QUEKO generator
experiments/       running the experiments, analysis, figures, benchmark export
tests/             pytest suite; tests/data/regression.json holds the stored runs
benchmarks/        all instances as OpenQASM 2.0
results/           tables, figures and key numbers of the paper
```

## Notes

The QUEKO generator in `src/odra5_router/circuits/queko.py` is adapted from Olivia Di Matteo's
MIT-licensed implementation (<https://github.com/glassnotes/QUEKO-Generator>) of the method by
Tan and Cong; the original license notice is kept in that file.
