"""Gate fidelities and the negative log-fidelity cost.

The estimated fidelity of a circuit is the product of its gate fidelities,
so the cost minimised everywhere in this package is

    C = sum over gates g of -ln(f_g)                                  (Eq. 2)

A single-qubit gate costs ``-ln f`` of the physical qubit it runs on, a
two-qubit gate ``-ln f`` of its coupler, and a SWAP three times the coupler
cost (it decomposes into three CZ gates). Measurements, resets and barriers
are free.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag

from odra5_router.topology import ODRA5_EDGES, ODRA5_NUM_QUBITS

NOT_CHARGED = frozenset({"measure", "reset", "barrier"})

@dataclass(frozen=True)
class FidelityModel:
    """Fidelity of a single-qubit gate on every qubit and of a two-qubit gate on every coupler.

    ``two_qubit`` is keyed by the coupler ``(a, b)`` with ``a < b``.
    """

    one_qubit: tuple[float, ...]
    two_qubit: dict[tuple[int, int], float]

    def __post_init__(self) -> None:
        n = len(self.one_qubit)
        for q, f in enumerate(self.one_qubit):
            if not 0.0 < f < 1.0:
                raise ValueError(f"fidelity of qubit {q} is not in (0, 1): {f}")
        for (a, b), f in self.two_qubit.items():
            if not (0 <= a < b < n):
                raise ValueError(f"coupler {(a, b)} must be (a, b) with 0 <= a < b < {n}")
            if not 0.0 < f < 1.0:
                raise ValueError(f"fidelity of coupler {(a, b)} is not in (0, 1): {f}")

    def cost_1q(self, q: int) -> float:
        return -math.log(self.one_qubit[q])

    def cost_2q(self, a: int, b: int) -> float:
        return -math.log(self.two_qubit[(a, b) if a < b else (b, a)])

    def cost_swap(self, a: int, b: int) -> float:
        return 3.0 * self.cost_2q(a, b)

    def to_json(self) -> dict:
        return {"one_qubit": list(self.one_qubit),
                "two_qubit": {f"{a}-{b}": f for (a, b), f in self.two_qubit.items()}}

    @classmethod
    def from_json(cls, d: dict) -> "FidelityModel":
        two = {tuple(sorted(map(int, k.split("-")))): v for k, v in d["two_qubit"].items()}
        return cls(one_qubit=tuple(d["one_qubit"]), two_qubit=two)


def adonis_model() -> FidelityModel:
    """Fidelities from the error profile of IQM's ``IQMFakeAdonis`` (qiskit-iqm 17.8).

    The profile gives a depolarizing parameter ``p`` for every gate; it is
    converted to the average gate fidelity ``f = 1 - p (d - 1) / d`` (``d = 2``
    or ``4``). The profile's ``p = 0`` (QB4) is taken as ``f = 0.99999``.
    """
    from iqm.qiskit_iqm import IQMFakeAdonis

    backend = IQMFakeAdonis()
    profile = backend.error_profile
    index = backend.qubit_name_to_index

    def fidelity(p: float, d: int) -> float:
        return 1 - p * (d - 1) / d if p else 0.99999

    one_qubit = [0.0] * ODRA5_NUM_QUBITS
    for name, p in profile.single_qubit_gate_depolarizing_error_parameters["prx"].items():
        one_qubit[index(name)] = fidelity(p, 2)
    two_qubit = {tuple(sorted((index(a), index(b)))): fidelity(p, 4)
                 for (a, b), p in profile.two_qubit_gate_depolarizing_error_parameters["cz"].items()}
    return FidelityModel(one_qubit=tuple(one_qubit), two_qubit=two_qubit)


def synthetic_model(seed: int = 0) -> FidelityModel:
    """Random Odra5 model with calibration-like values.

    Single-qubit fidelities are drawn from [0.991, 0.995], two-qubit ones from
    [0.945, 0.970]. Seed 0 is the model the hyperparameters were tuned on;
    seeds 1..20 are the calibration-like models of the robustness check.
    """
    rng = random.Random(seed)
    one_qubit = tuple(0.995 - 0.004 * rng.random() for _ in range(ODRA5_NUM_QUBITS))
    two_qubit = {tuple(sorted(e)): 0.97 - 0.025 * rng.random() for e in ODRA5_EDGES}
    return FidelityModel(one_qubit=one_qubit, two_qubit=two_qubit)


def fidelity_cost(circuit: QuantumCircuit, model: FidelityModel) -> float:
    """Cost (Eq. 2) of a circuit on physical qubits, whatever produced it."""
    dag = circuit_to_dag(circuit)
    total = 0.0
    for node in dag.op_nodes():
        qs = [dag.find_bit(q).index for q in node.qargs]
        if len(qs) == 1:
            if node.op.name not in NOT_CHARGED:
                total += model.cost_1q(qs[0])
        elif len(qs) == 2:
            total += model.cost_swap(*qs) if node.op.name == "swap" else model.cost_2q(*qs)
    return total
