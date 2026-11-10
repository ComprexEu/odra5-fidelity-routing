"""Routing problem, routing solution and how a solution becomes a circuit.

A solution never modifies the input circuit. It consists of

- ``initial_layout[v]``: the physical qubit of logical qubit ``v`` (the layout pi),
- ``gate_order``: the execution order sigma of the two-qubit interactions, any
  linear extension of their dependency DAG (``None`` = the DAG's own order),
- ``swaps``: ``(j, pa, pb)`` = SWAP the physical qubits ``pa`` and ``pb``
  right before interaction ``j``.

Single-qubit gates travel with their logical qubit: every single-qubit gate
runs right before the next two-qubit gate on its qubit, after that gate's
SWAPs, and gates with no later two-qubit gate run at the end (Section 3.1).
:func:`apply` and :func:`solution_cost` walk the same :func:`execution_steps`,
so the cost of a solution always equals the cost of the circuit it builds.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag
from qiskit.dagcircuit import DAGCircuit
from qiskit.transpiler import CouplingMap

from odra5_router.cancel import cancel_adjacent
from odra5_router.fidelity import NOT_CHARGED, FidelityModel, fidelity_cost
from odra5_router.topology import odra5_coupling_map


@dataclass(frozen=True)
class RoutingProblem:
    circuit: QuantumCircuit
    coupling_map: CouplingMap

    @property
    def num_qubits(self) -> int:
        return self.circuit.num_qubits

    @property
    def dag(self) -> DAGCircuit:
        return circuit_to_dag(self.circuit)

    @cached_property
    def interactions(self) -> tuple[tuple[int, int], ...]:
        """Logical qubit pairs of the two-qubit gates, in the DAG's topological order."""
        dag = self.dag
        return tuple(
            (dag.find_bit(node.qargs[0]).index, dag.find_bit(node.qargs[1]).index)
            for node in dag.topological_op_nodes()
            if len(node.qargs) == 2
        )


def make_problem(circuit: QuantumCircuit, coupling_map: CouplingMap | None = None) -> RoutingProblem:
    return RoutingProblem(circuit, coupling_map or odra5_coupling_map())


@dataclass(frozen=True)
class RoutingSolution:
    initial_layout: tuple[int, ...]
    swaps: tuple[tuple[int, int, int], ...] = ()
    gate_order: tuple[int, ...] | None = None


def swap_positions(pos: list[int], pa: int, pb: int) -> None:
    """Exchange the logical qubits sitting on physical qubits ``pa`` and ``pb``."""
    va = pos.index(pa)
    vb = pos.index(pb)
    pos[va], pos[vb] = pos[vb], pos[va]


@dataclass(frozen=True)
class Plan:
    """Where every gate of a problem's circuit is executed.

    ``attached[j]`` holds the single-qubit gates that run right before
    interaction ``j``, ``leftover`` those that run at the end, ``other`` the
    remaining operations (measurements, barriers, ...). Single-qubit entries
    are ``(node, logical_qubit)``.
    """

    interactions: tuple[tuple[int, int], ...]
    two_qubit_nodes: tuple
    attached: tuple[tuple, ...]
    leftover: tuple
    other: tuple


def build_plan(problem: RoutingProblem) -> Plan:
    dag = problem.dag
    pending: list[list] = [[] for _ in range(problem.num_qubits)]
    attached: list[tuple] = []
    two_qubit_nodes: list = []
    other: list = []
    for node in dag.topological_op_nodes():
        qs = [dag.find_bit(q).index for q in node.qargs]
        if len(qs) == 2:
            a, b = qs
            attached.append(tuple(pending[a] + pending[b]))
            pending[a].clear()
            pending[b].clear()
            two_qubit_nodes.append(node)
        elif len(qs) == 1 and node.op.name not in NOT_CHARGED:
            pending[qs[0]].append((node, qs[0]))
        elif qs:
            other.append((node, qs))
    leftover = tuple(entry for wire in pending for entry in wire)
    return Plan(
        interactions=problem.interactions,
        two_qubit_nodes=tuple(two_qubit_nodes),
        attached=tuple(attached),
        leftover=leftover,
        other=tuple(other),
    )


def execution_steps(problem: RoutingProblem, solution: RoutingSolution, plan: Plan | None = None):
    """Yield the routed circuit's operations in execution order.

    Steps are ``("swap", pa, pb)``, ``("1q", node, p)``, ``("2q", node, pa, pb)``
    and ``("other", node, physical_qubits)``.
    """
    plan = plan or build_plan(problem)
    m = len(plan.interactions)
    order = solution.gate_order if solution.gate_order is not None else range(m)
    if sorted(order) != list(range(m)):
        raise ValueError(f"gate_order must be a permutation of 0..{m - 1}")
    pos = list(solution.initial_layout)
    swaps_before: dict[int, list[tuple[int, int]]] = {}
    for j, pa, pb in solution.swaps:
        swaps_before.setdefault(j, []).append((pa, pb))
    for j in order:
        for pa, pb in swaps_before.get(j, ()):
            yield ("swap", pa, pb)
            swap_positions(pos, pa, pb)
        for node, q in plan.attached[j]:
            yield ("1q", node, pos[q])
        a, b = plan.interactions[j]
        yield ("2q", plan.two_qubit_nodes[j], pos[a], pos[b])
    for node, q in plan.leftover:
        yield ("1q", node, pos[q])
    for node, qs in plan.other:
        yield ("other", node, [pos[q] for q in qs])


def apply(problem: RoutingProblem, solution: RoutingSolution) -> QuantumCircuit:
    """The routed circuit on physical qubits."""
    if len(solution.initial_layout) != problem.num_qubits:
        raise ValueError("initial_layout has the wrong length")
    out = QuantumCircuit(problem.num_qubits)
    for creg in problem.circuit.cregs:
        out.add_register(creg)
    for step in execution_steps(problem, solution):
        if step[0] == "swap":
            out.swap(step[1], step[2])
        elif step[0] == "1q":
            out.append(step[1].op, [step[2]], step[1].cargs)
        elif step[0] == "2q":
            out.append(step[1].op, [step[2], step[3]], step[1].cargs)
        else:
            out.append(step[1].op, step[2], step[1].cargs)
    return out


def validate(problem: RoutingProblem, solution: RoutingSolution) -> None:
    """Raise ``ValueError`` unless the solution routes every two-qubit gate on a coupler."""
    n = problem.num_qubits
    if sorted(solution.initial_layout) != list(range(n)):
        raise ValueError(f"initial_layout must be a permutation of 0..{n - 1}")
    cm = problem.coupling_map
    m = len(problem.interactions)
    for j, pa, pb in solution.swaps:
        if not 0 <= j < m:
            raise ValueError(f"SWAP before interaction {j}, which does not exist")
        if cm.distance(pa, pb) != 1:
            raise ValueError(f"SWAP ({pa}, {pb}) is not on a coupler")
    for step in execution_steps(problem, solution):
        if step[0] == "2q" and cm.distance(step[2], step[3]) != 1:
            raise ValueError(f"two-qubit gate on ({step[2]}, {step[3]}), which is not a coupler")


def solution_cost(problem: RoutingProblem, solution: RoutingSolution, model: FidelityModel,
                  plan: Plan | None = None) -> float:
    """Cost (Eq. 2) of the routed circuit, computed without building it."""
    total = 0.0
    for step in execution_steps(problem, solution, plan):
        if step[0] == "swap":
            total += model.cost_swap(step[1], step[2])
        elif step[0] == "1q":
            total += model.cost_1q(step[2])
        elif step[0] == "2q":
            total += model.cost_2q(step[2], step[3])
    return total


def routed_cost(problem: RoutingProblem, solution: RoutingSolution, model: FidelityModel) -> float:
    """The routing-level score of Section 3.2: cost after adjacent pairs of the routed circuit cancel."""
    return fidelity_cost(cancel_adjacent(apply(problem, solution)), model)
