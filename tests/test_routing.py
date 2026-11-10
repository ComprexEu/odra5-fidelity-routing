import itertools
import random

import pytest
from qiskit import QuantumCircuit

from odra5_router import ExactDP, SearchRouter, adonis_model, make_problem, synthetic_model, validate
from odra5_router.benchmarks import star_model, star_problem
from odra5_router.cancel import cancel_adjacent, reduce_input
from odra5_router.circuits.random import adversarial_circuit, random_circuit
from odra5_router.encoding import Encoding
from odra5_router.fidelity import fidelity_cost
from odra5_router.pipeline import sabre_route
from odra5_router.problem import RoutingSolution, apply, routed_cost, solution_cost

MODEL = adonis_model()


def small_problems():
    for seed in range(6):
        yield make_problem(reduce_input(random_circuit(5, 9, seed=seed, p_two_qubit=0.6)))
    yield make_problem(adversarial_circuit(1))


def test_decoded_cost_matches_the_built_circuit():
    rng = random.Random(0)
    for prob in small_problems():
        enc = Encoding(prob, MODEL)
        for _ in range(30):
            layout = rng.sample(range(5), 5)
            order = enc.random_order(rng, local=rng.random() < 0.5)
            decisions = [rng.randrange(3) for _ in range(enc.m)]
            cost, n_swaps, swaps = enc.decode(layout, order, decisions, record=True)
            sol = RoutingSolution(tuple(layout), tuple(swaps), tuple(order))
            validate(prob, sol)
            assert n_swaps <= enc.m
            assert cost == pytest.approx(solution_cost(prob, sol, MODEL), abs=1e-12)
            assert cost == pytest.approx(fidelity_cost(apply(prob, sol), MODEL), abs=1e-12)


def all_orders(enc):
    for perm in itertools.permutations(range(enc.m)):
        if enc.is_topological(perm):
            yield list(perm)


@pytest.mark.parametrize("seed", [0, 1, 3, 9])
def test_encoding_contains_the_optimum(seed):
    """Exhaustive search over the encoding reaches the cost of the exact DP (Section 4.1)."""
    prob = make_problem(reduce_input(random_circuit(5, 7, seed=seed, p_two_qubit=0.6)))
    model = synthetic_model(seed)
    enc = Encoding(prob, model)
    assert 1 <= enc.m <= 4
    best = min(enc.decode(list(layout), order, list(dec))[0]
               for layout in itertools.permutations(range(5))
               for order in all_orders(enc)
               for dec in itertools.product(range(3), repeat=enc.m))
    dp = ExactDP(fidelity=model).solve(prob)
    assert best == pytest.approx(solution_cost(prob, dp, model), abs=1e-12)


def test_dp_is_never_beaten_by_the_search():
    for prob in small_problems():
        dp = solution_cost(prob, ExactDP(fidelity=MODEL).solve(prob), MODEL)
        for alg in ("rs", "tabu", "ga"):
            router = SearchRouter(algorithm=alg, start="random", fidelity=MODEL, max_evals=500)
            sol = router.solve(prob, seed=1)
            validate(prob, sol)
            assert solution_cost(prob, sol, MODEL) >= dp - 1e-12


def test_lexicographic_dp_uses_fewest_swaps():
    prob = make_problem(adversarial_circuit(2))
    lex = ExactDP(fidelity=MODEL, primary="swaps").solve(prob)
    fid = ExactDP(fidelity=MODEL).solve(prob)
    assert len(lex.swaps) <= len(fid.swaps)
    assert solution_cost(prob, fid, MODEL) <= solution_cost(prob, lex, MODEL) + 1e-12


def test_sabre_translation_never_adds_swaps():
    for prob in small_problems():
        enc = Encoding(prob, MODEL)
        from qiskit.transpiler import PassManager
        from qiskit.transpiler.passes import SabreLayout

        pm = PassManager([SabreLayout(prob.coupling_map, seed=3, layout_trials=4, swap_trials=4)])
        routed = pm.run(prob.circuit)
        layout = [pm.property_set["layout"][q] for q in prob.circuit.qubits]
        n_sabre = sum(1 for inst in routed.data if inst.operation.name == "swap")
        _, ns, _ = enc.decode(*enc.from_routed(routed, layout))
        assert ns <= n_sabre


def test_larger_stars():
    prob, model = star_problem(7, 0), star_model(7, 1)
    sol = SearchRouter(algorithm="tabu", start="sabre", fidelity=model, max_evals=300).solve(prob, seed=0)
    validate(prob, sol)
    assert routed_cost(prob, sol, model) <= fidelity_cost(cancel_adjacent(sabre_route(prob, 0)), model) * 1.5


def test_cancellation():
    qc = QuantumCircuit(3)
    qc.cx(0, 1)
    qc.x(2)
    qc.cx(0, 1)   # cancels with the first CX: nothing in between on qubits 0 and 1
    qc.cx(1, 2)
    qc.cx(2, 1)   # different control and target: does not cancel
    qc.h(0)
    qc.swap(0, 1)
    qc.swap(1, 0)  # SWAP is symmetric only as a set of qubits; ordered qubits differ, kept
    out = cancel_adjacent(qc)
    assert [inst.operation.name for inst in out.data] == ["x", "cx", "cx", "h", "swap", "swap"]
