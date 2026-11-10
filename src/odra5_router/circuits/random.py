"""Seeded random and adversarial circuits."""

from __future__ import annotations

import random

from qiskit import QuantumCircuit

from odra5_router.topology import ODRA5_NUM_QUBITS

# The six pairs of Odra5 leaves; none of them is a coupler.
LEAF_PAIRS: tuple[tuple[int, int], ...] = ((0, 1), (1, 3), (3, 4), (4, 0), (0, 3), (1, 4))


def random_circuit(num_qubits: int = ODRA5_NUM_QUBITS, num_gates: int = 10, *, seed: int = 0,
                   p_two_qubit: float = 0.4) -> QuantumCircuit:
    """``num_gates`` steps; each is a CX on a random pair with probability ``p_two_qubit``,
    otherwise an H and an RZ with a random angle, each on a random qubit."""
    rng = random.Random(seed)
    qc = QuantumCircuit(num_qubits)
    for _ in range(num_gates):
        if rng.random() < p_two_qubit and num_qubits >= 2:
            a, b = rng.sample(range(num_qubits), 2)
            qc.cx(a, b)
        else:
            qc.h(rng.randrange(num_qubits))
            qc.rz(rng.uniform(0, 6.28), rng.randrange(num_qubits))
    return qc


def adversarial_circuit(rounds: int, *, seed: int = 0) -> QuantumCircuit:
    """``rounds`` rounds of one CX on each of the six leaf pairs, in a seeded order per round."""
    rng = random.Random(seed)
    qc = QuantumCircuit(ODRA5_NUM_QUBITS)
    for _ in range(rounds):
        for a, b in rng.sample(LEAF_PAIRS, len(LEAF_PAIRS)):
            qc.cx(a, b)
    return qc
