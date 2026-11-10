"""Cancellation of adjacent self-inverse two-qubit gates.

Two CX gates with the same control and target, two CZ gates or two SWAPs on
the same qubits multiply to the identity when nothing touches either qubit
between them. Removing such a pair can make two other gates adjacent, so the
pass repeats until nothing changes.

It is used twice: on the input, so that no router pays for gates that would
never run (:func:`reduce_input`), and on the routed output, which is how the
routing level scores every method alike (Section 3.2).
"""

from __future__ import annotations

from qiskit import QuantumCircuit

SELF_INVERSE_2Q = frozenset({"cx", "cz", "swap"})


def cancel_adjacent(circuit: QuantumCircuit) -> QuantumCircuit:
    """Copy of ``circuit`` without adjacent self-inverse two-qubit pairs."""
    data = [(inst, tuple(circuit.find_bit(q).index for q in inst.qubits)) for inst in circuit.data]
    n = circuit.num_qubits
    while True:
        removed: set[int] = set()
        last_touch: list[int | None] = [None] * n
        for i, (inst, qs) in enumerate(data):
            name = inst.operation.name
            if len(qs) == 2 and name in SELF_INVERSE_2Q:
                a, b = qs
                k = last_touch[a]
                # CX pairs must match in control and target, so compare the ordered qubits.
                if k is not None and k == last_touch[b] and k not in removed \
                        and data[k][0].operation.name == name and data[k][1] == qs:
                    removed.update((k, i))
                    continue
            for q in qs:
                last_touch[q] = i
        if not removed:
            break
        data = [d for i, d in enumerate(data) if i not in removed]
    out = QuantumCircuit(n)
    for creg in circuit.cregs:
        out.add_register(creg)
    for inst, _ in data:
        out.append(inst.operation, inst.qubits, inst.clbits)
    return out


def reduce_input(circuit: QuantumCircuit) -> QuantumCircuit:
    """The input every router receives: :func:`cancel_adjacent` of the source circuit."""
    return cancel_adjacent(circuit)
