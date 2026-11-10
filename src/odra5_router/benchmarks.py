"""The benchmark of the paper: circuits and fidelity models.

The Odra5 benchmark has 104 circuits in five suites; one of them (``tiny_1``)
has no two-qubit gate after reduction, which leaves the 103 circuits of the
paper. The tuning split is disjoint from all of them. ``benchmarks/`` holds
every circuit as OpenQASM 2.0 (see ``experiments/export_benchmarks.py``).
"""

from __future__ import annotations

import math
import random

from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import QFT, DraperQFTAdder, EfficientSU2, QuantumVolume

from odra5_router.cancel import reduce_input
from odra5_router.circuits.queko import odra5_queko
from odra5_router.circuits.random import adversarial_circuit, random_circuit
from odra5_router.fidelity import FidelityModel, adonis_model, synthetic_model
from odra5_router.problem import RoutingProblem
from odra5_router.topology import ODRA5_EDGES, ODRA5_NUM_QUBITS, star_coupling_map

# --- random circuits ----------------------------------------------------------

# The first ten random circuits (name, seed, number of steps, p_2Q).
FIXED_RANDOM = (
    ("tiny_0", 0, 4, 0.5), ("tiny_1", 1, 6, 0.5),
    ("small_0", 42, 10, 0.4), ("small_1", 99, 12, 0.4),
    ("medium_0", 123, 20, 0.35), ("medium_1", 456, 25, 0.35),
    ("heavy_0", 789, 40, 0.3), ("heavy_1", 1001, 50, 0.3),
    ("dense_0", 2024, 60, 0.7), ("dense_1", 2025, 80, 0.65),
)

# Size classes of the seeded random circuits: number of steps, p_2Q.
SIZE_CLASSES = {
    "tiny": (5, 0.50), "small": (11, 0.40), "medium": (22, 0.35), "heavy": (45, 0.30), "dense": (70, 0.68),
}
EVAL_SEEDS = range(100, 110)
TUNING_SEEDS = range(200, 205)


def _size_class_circuits(seeds) -> list[tuple[str, QuantumCircuit]]:
    return [(f"{cls}_s{s}", random_circuit(ODRA5_NUM_QUBITS, g, seed=s, p_two_qubit=p))
            for cls, (g, p) in SIZE_CLASSES.items() for s in seeds]


def fixed_circuits() -> list[tuple[str, QuantumCircuit]]:
    """The ten fixed random circuits and the adversarial circuits with 2, 4 and 8 rounds."""
    out = [(name, random_circuit(ODRA5_NUM_QUBITS, g, seed=s, p_two_qubit=p)) for name, s, g, p in FIXED_RANDOM]
    return out + [(f"hard_{r}r", adversarial_circuit(r)) for r in (2, 4, 8)]


def random_circuits() -> list[tuple[str, QuantumCircuit]]:
    """Ten seeds per size class (seeds 100..109)."""
    return _size_class_circuits(EVAL_SEEDS)


def tuning_circuits() -> list[tuple[str, QuantumCircuit]]:
    """The tuning split: five seeds per size class (seeds 200..204)."""
    return _size_class_circuits(TUNING_SEEDS)


def adversarial_circuits() -> list[tuple[str, QuantumCircuit]]:
    """The adversarial circuits with 12 and 16 rounds."""
    return [(f"hard_{r}r", adversarial_circuit(r)) for r in (12, 16)]


# --- structured circuits --------------------------------------------------------

def _native(qc: QuantumCircuit) -> QuantumCircuit:
    """Unroll to the native gates {r, cz}, without routing."""
    return transpile(qc, basis_gates=["r", "cz"], optimization_level=1)


def _grover(iterations: int) -> QuantumCircuit:
    """Grover search on qubits 0..3 with qubit 4 as the oracle's target."""
    qc = QuantumCircuit(5)
    qc.h(range(4))
    for _ in range(iterations):
        qc.x(1)
        qc.mcx([0, 1, 2, 3], 4)
        qc.x(1)
        qc.h(range(4))
        qc.x(range(4))
        qc.mcx([0, 1, 2, 3], 4)
        qc.x(range(4))
        qc.h(range(4))
    return qc


def structured_circuits() -> list[tuple[str, QuantumCircuit]]:
    """GHZ, QFT, approximate QFT, W state, Bernstein-Vazirani, Grover, QAOA (p = 1, 2),
    Quantum Volume and a one-bit adder."""
    out = []
    ghz = QuantumCircuit(5)
    ghz.h(0)
    for i in range(4):
        ghz.cx(i, i + 1)
    out.append(("ghz_5q", ghz))

    qft = QuantumCircuit(5)
    qft.append(QFT(num_qubits=5, do_swaps=False), range(5))
    out.append(("qft_5q", qft))
    aqft = QuantumCircuit(5)
    aqft.append(QFT(num_qubits=5, approximation_degree=2, do_swaps=False), range(5))
    out.append(("aqft_5q", aqft))

    w = QuantumCircuit(5)
    w.ry(2 * math.asin(1 / math.sqrt(5)), 0)
    for i in range(4):
        w.ch(i, i + 1)
        w.cx(i + 1, i)
    out.append(("w_state_5q", w))

    bv = QuantumCircuit(5)  # secret 1011, qubit 4 is the target
    bv.x(4)
    bv.h(range(5))
    for q in (0, 1, 3):
        bv.cx(q, 4)
    bv.h(range(4))
    out.append(("bv_5q", bv))

    out.append(("grover_4q", _grover(1)))

    for g in range(5):  # MaxCut on random 5-node graphs
        rng = random.Random(300 + g)
        edges = [(u, v) for u in range(5) for v in range(u + 1, 5) if rng.random() < 0.5]
        edges = edges or [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]
        for p in (1, 2):
            qc = QuantumCircuit(5)
            qc.h(range(5))
            for _ in range(p):
                for u, v in edges:
                    qc.cx(u, v)
                    qc.rz(2 * 0.39, v)
                    qc.cx(u, v)
                for q in range(5):
                    qc.rx(2 * 0.25, q)
            out.append((f"qaoa_g{g}_p{p}", qc))

    for s in range(10):
        out.append((f"qv_5q_s{s}", QuantumVolume(num_qubits=5, depth=5, seed=s)))

    adder = QuantumCircuit(5)
    adder.ccx(0, 1, 4)
    adder.cx(0, 1)
    adder.ccx(1, 2, 4)
    adder.cx(1, 2)
    adder.cx(2, 3)
    out.append(("adder_1bit_5q", adder))
    return [(name, _native(qc)) for name, qc in out]


def algorithmic_circuits() -> list[tuple[str, QuantumCircuit]]:
    """Longer algorithmic circuits: Trotterised Hamiltonian simulation, deep QAOA,
    a hardware-efficient ansatz, Grover with three iterations, a QFT adder and QUEKO."""
    out = []
    ring = [(i, (i + 1) % 5) for i in range(5)]
    complete = [(u, v) for u in range(5) for v in range(u + 1, 5)]

    for steps in (2, 4):  # first-order Trotter, dt = 0.1
        qc = QuantumCircuit(5)  # Heisenberg XXX on a ring
        for _ in range(steps):
            for u, v in ring:
                qc.rxx(0.2, u, v)
                qc.ryy(0.2, u, v)
                qc.rzz(0.2, u, v)
        out.append((f"heisenberg_ring_r{steps}", _native(qc)))
        qc = QuantumCircuit(5)  # transverse-field Ising, all-to-all couplings
        qc.h(range(5))
        for _ in range(steps):
            for u, v in complete:
                qc.rzz(0.2, u, v)
            for q in range(5):
                qc.rx(0.3, q)
        out.append((f"ising_full_r{steps}", _native(qc)))

    for name, edges, p in (("qaoa_k5_p3", complete, 3), ("qaoa_k5_p4", complete, 4), ("qaoa_ring_p6", ring, 6)):
        qc = QuantumCircuit(5)
        qc.h(range(5))
        for layer in range(p):
            gamma, beta = 0.4 - 0.05 * layer, 0.3 + 0.05 * layer
            for u, v in edges:
                qc.rzz(2 * gamma, u, v)
            for q in range(5):
                qc.rx(2 * beta, q)
        out.append((name, _native(qc)))

    for reps in (3, 6):  # fixed random parameters
        ansatz = EfficientSU2(5, reps=reps, entanglement="full")
        rng = random.Random(500 + reps)
        qc = ansatz.assign_parameters([rng.uniform(-math.pi, math.pi) for _ in range(ansatz.num_parameters)])
        out.append((f"vqe_su2_full_r{reps}", _native(qc.decompose())))

    out.append(("grover_4q_it3", _native(_grover(3))))

    add = QuantumCircuit(5)  # 01 + 11 on two 2-bit registers
    add.x([0, 2, 3])
    add.append(DraperQFTAdder(2, kind="fixed"), range(4))
    out.append(("qft_adder_2b", _native(add.decompose().decompose())))

    queko, _ = odra5_queko(32, density_vec=(0.25, 0.3), seed=0)  # known zero-SWAP layout
    out.append(("queko_d32", queko))
    return out


SUITES = {
    "fixed": fixed_circuits,
    "random": random_circuits,
    "adversarial": adversarial_circuits,
    "structured": structured_circuits,
    "algorithmic": algorithmic_circuits,
    "tuning": tuning_circuits,
}
ODRA5_SUITES = ("fixed", "random", "adversarial", "structured", "algorithmic")


def group(name: str) -> str:
    """Benchmark group of Table 1."""
    if name.startswith(("heisenberg", "ising")):
        return "hamsim"
    for g in ("tiny", "small", "medium", "heavy", "dense", "hard", "qaoa", "qv"):
        if name.startswith(g):
            return g
    return "other"


GROUP_LABELS = {
    "tiny": "Random tiny", "small": "Random small", "medium": "Random medium", "heavy": "Random heavy",
    "dense": "Random dense", "hard": "Adversarial", "qaoa": "QAOA MaxCut", "hamsim": "Hamiltonian simulation",
    "qv": "Quantum Volume", "other": "Other structured",
}


# --- fidelity models ------------------------------------------------------------

def fidelity_models() -> dict[str, FidelityModel]:
    """``adonis`` (the main model), the tuning model ``calib_00``, 20 further
    calibration-like models, 5 with a large spread and a uniform one."""
    models = {"adonis": adonis_model()}
    for s in range(21):
        models[f"calib_{s:02d}"] = synthetic_model(seed=s)
    for s in range(1, 6):
        rng = random.Random(500 + s)
        one = tuple(0.998 - 0.006 * rng.random() for _ in range(ODRA5_NUM_QUBITS))
        two = {tuple(sorted(e)): 0.90 + 0.095 * rng.random() for e in ODRA5_EDGES}
        models[f"spread_{s}"] = FidelityModel(one_qubit=one, two_qubit=two)
    models["uniform"] = FidelityModel(one_qubit=(0.99,) * ODRA5_NUM_QUBITS,
                                      two_qubit={tuple(sorted(e)): 0.95 for e in ODRA5_EDGES})
    return models


# --- larger stars -----------------------------------------------------------------

STAR_SIZES = (5, 6, 7, 8)
STAR_CIRCUITS = range(10)
STAR_MODELS = range(1, 6)


def star_circuit(n: int, k: int) -> QuantumCircuit:
    return random_circuit(n, 40, seed=k, p_two_qubit=0.7)


def star_problem(n: int, k: int) -> RoutingProblem:
    return RoutingProblem(reduce_input(star_circuit(n, k)), star_coupling_map(n))


def star_model(n: int, k: int) -> FidelityModel:
    rng = random.Random(1000 * n + k)
    one = tuple(0.995 - 0.004 * rng.random() for _ in range(n))
    two = {(0, i): 0.97 - 0.025 * rng.random() for i in range(1, n)}
    return FidelityModel(one_qubit=one, two_qubit=two)
