"""End-to-end compilation in Qiskit's level-3 pass manager (Section 5).

Every method runs inside the same level-3 ``StagedPassManager``. Our routers
replace only its layout and routing stages; init, translation, optimization
(including resynthesis and block consolidation) and scheduling stay Qiskit's
own. The result is a circuit in the native gates ``{r, cz}``.
"""

from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.dagcircuit import DAGCircuit
from qiskit.transpiler import Layout, PassManager, generate_preset_pass_manager
from qiskit.transpiler.basepasses import TransformationPass

from odra5_router.fidelity import FidelityModel
from odra5_router.problem import apply, make_problem, swap_positions
from odra5_router.topology import noise_aware_target, odra5_target


class RouterPass(TransformationPass):
    """Layout and routing stage backed by one of our routers (anything with ``solve(problem, seed, budget_s)``).

    Sets ``layout`` and ``final_layout`` in Qiskit's conventions, so the rest
    of the pass manager and ``Operator.from_circuit`` treat the output like
    that of Qiskit's own routing.
    """

    def __init__(self, router, *, seed: int = 0, budget_s: float = 120.0) -> None:
        super().__init__()
        self.router = router
        self.seed = seed
        self.budget_s = budget_s

    def run(self, dag: DAGCircuit) -> DAGCircuit:
        circuit = dag_to_circuit(dag)
        problem = make_problem(circuit)
        solution = self.router.solve(problem, seed=self.seed, budget_s=self.budget_s)
        routed = apply(problem, solution)

        qubits = list(circuit.qubits)
        self.property_set["layout"] = Layout({qubits[v]: p for v, p in enumerate(solution.initial_layout)})
        self.property_set["original_qubit_indices"] = {q: i for i, q in enumerate(qubits)}
        # final_layout maps the physical qubit where a state starts to where it ends.
        pos = list(solution.initial_layout)
        start_of = {p: v for v, p in enumerate(pos)}
        order = solution.gate_order if solution.gate_order is not None else range(len(problem.interactions))
        swaps_before: dict[int, list[tuple[int, int]]] = {}
        for j, pa, pb in solution.swaps:
            swaps_before.setdefault(j, []).append((pa, pb))
        for j in order:
            for pa, pb in swaps_before.get(j, ()):
                swap_positions(pos, pa, pb)
        out = circuit_to_dag(routed)
        physical = list(out.qubits)
        self.property_set["final_layout"] = Layout({physical[p]: pos[start_of[p]] for p in range(len(physical))})
        return out


def compile_circuit(circuit: QuantumCircuit, router=None, *, model: FidelityModel | None = None,
                    seed: int = 0, budget_s: float = 120.0) -> QuantumCircuit:
    """Compile ``circuit`` for Odra5.

    ``router=None`` runs Qiskit's unmodified level-3 preset. With ``model`` the
    Target carries its gate errors (noise-aware), otherwise only the topology.
    """
    target = noise_aware_target(model) if model is not None else odra5_target()
    pm = generate_preset_pass_manager(3, target=target, seed_transpiler=seed)
    if router is not None:
        pm.layout = PassManager([RouterPass(router, seed=seed, budget_s=budget_s)])
        pm.routing = PassManager([])
    return pm.run(circuit)


def qiskit_route(circuit: QuantumCircuit, *, model: FidelityModel | None = None, seed: int = 0) -> QuantumCircuit:
    """Only the layout and routing stages of the level-3 preset (VF2Layout, SabreLayout
    with SABRE routing, VF2PostLayout): the Qiskit baselines of the routing level."""
    target = noise_aware_target(model) if model is not None else odra5_target()
    pm = generate_preset_pass_manager(3, target=target, seed_transpiler=seed)
    pm.init = None
    pm.translation = None
    pm.optimization = None
    pm.scheduling = None
    return pm.run(circuit)


def sabre_route(problem, seed: int = 0) -> QuantumCircuit:
    """SABRE with the level-3 settings (20 layout and 20 SWAP trials), set explicitly
    so that the result does not depend on the number of CPUs."""
    from qiskit.transpiler.passes import SabreLayout, SabreSwap

    cm = problem.coupling_map
    return PassManager([
        SabreLayout(cm, seed=seed, max_iterations=4, layout_trials=20, swap_trials=20),
        SabreSwap(cm, heuristic="decay", seed=seed, trials=20),
    ]).run(problem.circuit)
