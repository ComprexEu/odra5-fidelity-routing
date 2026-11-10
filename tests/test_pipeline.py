from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from odra5_router import ExactDP, SearchRouter, adonis_model, apply, compile_circuit, make_problem, validate
from odra5_router.circuits.random import adversarial_circuit, random_circuit
from odra5_router.problem import swap_positions


def test_compiled_circuits_are_equivalent_and_native():
    model = adonis_model()
    circuits = [random_circuit(5, 30, seed=3, p_two_qubit=0.5), adversarial_circuit(2)]
    routers = [None, ExactDP(fidelity=model), SearchRouter(algorithm="tabu", start="sabre", fidelity=model,
                                                           max_evals=500)]
    for qc in circuits:
        for router in routers:
            out = compile_circuit(qc, router, model=model, seed=0)
            assert set(out.count_ops()) <= {"r", "cz"}
            assert Operator.from_circuit(out).equiv(Operator(qc))


def test_measurements_follow_their_qubit():
    qc = QuantumCircuit(5, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 3)
    qc.measure([0, 3], [0, 1])
    prob = make_problem(qc)
    sol = ExactDP(fidelity=adonis_model()).solve(prob)
    validate(prob, sol)
    routed = apply(prob, sol)
    measured = [routed.find_bit(inst.qubits[0]).index for inst in routed.data if inst.operation.name == "measure"]
    pos = list(sol.initial_layout)
    for _, pa, pb in sol.swaps:
        swap_positions(pos, pa, pb)
    assert measured == [pos[0], pos[3]]
