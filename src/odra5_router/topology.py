"""Coupling graphs and Qiskit targets for star devices.

Odra5 is an IQM Spark processor: five qubits, with physical qubit 2 (QB3 in
IQM numbering) connected to the other four::

        0
        |
    1 - 2 - 3
        |
        4

Native gates are the phased rotation ``r(theta, phi)`` and ``cz``.
"""

from __future__ import annotations

from qiskit.circuit import Parameter
from qiskit.circuit.library import CZGate, RGate
from qiskit.transpiler import CouplingMap, InstructionProperties, Target

ODRA5_NUM_QUBITS = 5
ODRA5_HUB = 2
ODRA5_EDGES: list[tuple[int, int]] = [(0, 2), (1, 2), (2, 3), (2, 4)]


def odra5_coupling_map() -> CouplingMap:
    return CouplingMap(ODRA5_EDGES)


def star_coupling_map(num_qubits: int) -> CouplingMap:
    """Star with hub 0 and leaves ``1..num_qubits-1`` (the larger-star test)."""
    return CouplingMap([(0, i) for i in range(1, num_qubits)])


def odra5_target() -> Target:
    """Odra5 ``Target`` without error data (what Qiskit sees for IQM's fake Adonis)."""
    target = Target(num_qubits=ODRA5_NUM_QUBITS)
    target.add_instruction(RGate(Parameter("theta"), Parameter("phi")),
                           {(q,): None for q in range(ODRA5_NUM_QUBITS)})
    directed = list(ODRA5_EDGES) + [(b, a) for a, b in ODRA5_EDGES]
    target.add_instruction(CZGate(), {pair: None for pair in directed})
    return target


def noise_aware_target(model) -> Target:
    """Odra5 ``Target`` whose instructions carry ``error = 1 - f`` from a ``FidelityModel``.

    Qiskit's noise-aware passes (VF2Layout, VF2PostLayout) use these errors to
    score layouts. The qarg order differs from :func:`odra5_target`; it is
    kept as it was when the paper's results were computed, because Qiskit's
    layout passes iterate over it.
    """
    target = Target(num_qubits=ODRA5_NUM_QUBITS)
    target.add_instruction(
        RGate(Parameter("theta"), Parameter("phi")),
        {(q,): InstructionProperties(error=1.0 - model.one_qubit[q]) for q in range(ODRA5_NUM_QUBITS)},
    )
    cz = {}
    for a, b in ODRA5_EDGES:
        err = 1.0 - model.two_qubit[(a, b)]
        cz[(a, b)] = InstructionProperties(error=err)
        cz[(b, a)] = InstructionProperties(error=err)
    target.add_instruction(CZGate(), cz)
    return target
