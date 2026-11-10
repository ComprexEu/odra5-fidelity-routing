"""Random Search, Tabu Search and the Genetic Algorithm of Section 4.

All three use the same encoding (:mod:`odra5_router.encoding`), the same
elementary moves, the same budget of ``max_evals`` decoder calls and the same
final polish; they differ only in how they search. Elementary moves:

- transposition of two entries of the layout,
- exchange of two consecutive interactions on disjoint qubits in the order
  (which keeps it a linear extension of the DAG),
- change of one routing decision.

Starts (``start``):

- ``"random"``: uniform layout and decisions, order from the locality-
  preserving Kahn's algorithm;
- ``"sabre"``: the routes of 20 SABRE runs translated into the encoding are
  used first (Tabu Search starts from the best one and restarts from the
  others, the GA puts them in its initial population, random search
  evaluates them first); they count against the budget;
- ``"lookahead"``: decisions of a demand lookahead for a random layout and
  order. Not part of the paper's comparison; its runs only contribute to the
  best known solutions of the larger-star test (Section 6.4).

The default parameters are the ones selected on the tuning split (Section 4.3).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from odra5_router.encoding import Encoding
from odra5_router.fidelity import FidelityModel, adonis_model
from odra5_router.problem import RoutingProblem, RoutingSolution

ALGORITHMS = ("rs", "tabu", "ga")
STARTS = ("random", "sabre", "lookahead")
OBJECTIVES = ("fidelity", "swaps")
_INF = float("inf")


@dataclass
class Candidate:
    layout: list[int]
    order: list[int]
    decisions: list[int]
    cost: float = _INF   # value of the objective
    fid: float = _INF    # fidelity cost; equals ``cost`` under the fidelity objective
    nswaps: int = 0

    def copy(self) -> "Candidate":
        return Candidate(list(self.layout), list(self.order), list(self.decisions),
                         self.cost, self.fid, self.nswaps)


def order_crossover(p1: list[int], p2: list[int], rng: random.Random) -> list[int]:
    """OX1 on permutations: a slice of ``p1``, the rest in the order of ``p2``."""
    n = len(p1)
    if n < 2:
        return list(p1)
    i, j = sorted(rng.sample(range(n), 2))
    child = [-1] * n
    child[i:j + 1] = p1[i:j + 1]
    taken = set(child[i:j + 1])
    fill = iter(x for x in p2 if x not in taken)
    for k in list(range(j + 1, n)) + list(range(0, i)):
        child[k] = next(fill)
    return child


def precedence_crossover(p1: list[int], p2: list[int], rng: random.Random) -> list[int]:
    """The child repeatedly takes the first unscheduled interaction of a random parent,
    so it is a linear extension of the DAG whenever both parents are."""
    m = len(p1)
    used = [False] * (max(p1) + 1 if p1 else 0)
    i1 = i2 = 0
    out: list[int] = []
    while len(out) < m:
        if rng.random() < 0.5:
            while used[p1[i1]]:
                i1 += 1
            j = p1[i1]
        else:
            while used[p2[i2]]:
                i2 += 1
            j = p2[i2]
        used[j] = True
        out.append(j)
    return out


@dataclass
class SearchRouter:
    algorithm: str = "tabu"
    start: str = "sabre"
    objective: str = "fidelity"
    max_evals: int = 10_000
    polish: bool = True
    fidelity: FidelityModel | None = None
    # Tabu Search: candidate list K, tenure L, restart after S iterations without improvement.
    candidates: int = 8
    tenure: int = 7
    stagnation: int = 400
    # Genetic Algorithm: population N, elitism e, tournament k, crossover p_c, mutation p_m.
    population: int = 80
    elitism: int = 2
    tournament: int = 3
    crossover_rate: float = 0.9
    mutation_rate: float = 0.7
    local_order: bool = True  # locality-preserving initial orders; False = plain random Kahn
    sabre_runs: int = 20
    last_stats: dict = field(default_factory=dict)
    last_raw_solution: RoutingSolution | None = None

    def __post_init__(self) -> None:
        if self.algorithm not in ALGORITHMS:
            raise ValueError(f"algorithm must be one of {ALGORITHMS}")
        if self.start not in STARTS:
            raise ValueError(f"start must be one of {STARTS}")
        if self.objective not in OBJECTIVES:
            raise ValueError(f"objective must be one of {OBJECTIVES}")

    def solve(self, problem: RoutingProblem, *, seed: int = 0, budget_s: float = 30.0) -> RoutingSolution:
        """Best route found within ``max_evals`` evaluations (or ``budget_s`` seconds).

        ``last_raw_solution`` holds the route before the polish, ``last_stats``
        the evaluation counts and the anytime curve ``[(evals, best fidelity cost), ...]``.
        """
        t0 = time.monotonic()
        self._deadline = t0 + budget_s
        enc = Encoding(problem, self.fidelity or adonis_model())
        if enc.m == 0:
            self.last_stats = {"evals": 0, "evals_polish": 0, "anytime": [], "time_s": 0.0}
            self.last_raw_solution = RoutingSolution(initial_layout=tuple(range(enc.n)))
            return self.last_raw_solution
        self._enc = enc
        self._rng = random.Random(seed)
        self._evals = 0
        self._best: Candidate | None = None
        self._anytime: list[tuple[int, float]] = []
        self._restarts = 0
        self._iters = 0
        self._starts = self._sabre_candidates(problem, seed) if self.start == "sabre" else []

        {"rs": self._random_search, "tabu": self._tabu_search, "ga": self._genetic_algorithm}[self.algorithm]()
        raw = self._best.copy()
        evals_search = self._evals
        t_search = time.monotonic() - t0
        best = self._polish(raw) if self.polish else raw
        self.last_raw_solution = self._solution(raw)
        self.last_stats = {
            "evals": evals_search,
            "evals_polish": self._evals - evals_search,
            "iterations": self._iters,
            "restarts": self._restarts,
            "anytime": list(self._anytime),
            "time_search_s": t_search,
            "time_s": time.monotonic() - t0,
            "deadline_hit": time.monotonic() > self._deadline,
        }
        return self._solution(best)

    # -- shared machinery -------------------------------------------------------

    def _out_of_budget(self) -> bool:
        return self._evals >= self.max_evals or time.monotonic() > self._deadline

    def _evaluate(self, c: Candidate) -> Candidate:
        fid, ns, _ = self._enc.decode(c.layout, c.order, c.decisions)
        self._evals += 1
        c.fid = fid
        c.nswaps = ns
        c.cost = fid if self.objective == "fidelity" else float(ns)
        if self._best is None or c.cost < self._best.cost:
            self._best = c.copy()
            self._anytime.append((self._evals, c.fid))
        return c

    def _sabre_candidates(self, problem: RoutingProblem, seed: int) -> list[Candidate]:
        """Candidates from SABRE runs with the level-3 settings, evaluated and sorted best first."""
        from qiskit.transpiler import PassManager
        from qiskit.transpiler.passes import SabreLayout

        enc = self._enc
        found: dict[tuple, Candidate] = {}
        for k in range(self.sabre_runs):
            pm = PassManager([SabreLayout(problem.coupling_map, seed=seed * 1000 + k, max_iterations=4,
                                          layout_trials=20, swap_trials=20)])
            routed = pm.run(problem.circuit)
            layout_q = pm.property_set["layout"]
            layout = [layout_q[q] for q in problem.circuit.qubits]
            try:
                c = Candidate(*enc.from_routed(routed, layout))
            except ValueError:
                continue
            found.setdefault((tuple(c.layout), tuple(c.order), tuple(c.decisions)), c)
        return sorted((self._evaluate(c) for c in found.values()), key=lambda c: c.cost)

    def _new_candidate(self) -> Candidate:
        if self._starts:
            return self._starts.pop(0).copy()
        enc, rng = self._enc, self._rng
        layout = list(range(enc.n))
        rng.shuffle(layout)
        order = enc.random_order(rng, local=self.local_order)
        if self.start == "lookahead":
            decisions = enc.lookahead_decisions(layout, order)
        else:
            decisions = [rng.randrange(3) for _ in range(enc.m)]
        return self._evaluate(Candidate(layout, order, decisions))

    def _move_types(self) -> list[str]:
        return ["layout", "order", "decision"] if self._enc.m >= 2 else ["layout", "decision"]

    def _random_move(self, c: Candidate, exchangeable: list[int]):
        """``(tabu attribute, move)`` of a random elementary move on ``c``."""
        enc, rng = self._enc, self._rng
        types = self._move_types()
        if "order" in types and not exchangeable:
            types.remove("order")
        t = rng.choice(types)
        if t == "layout":
            u, v = rng.sample(range(enc.n), 2)
            return ("L", min(u, v), max(u, v)), ("layout", u, v)
        if t == "order":
            k = rng.choice(exchangeable)
            x, y = c.order[k], c.order[k + 1]
            return ("O", min(x, y), max(x, y)), ("order", k)
        j = rng.randrange(enc.m)
        return ("G", j), ("decision", j, (c.decisions[j] + rng.randrange(1, 3)) % 3)

    @staticmethod
    def _apply(c: Candidate, move) -> Candidate:
        d = c.copy()
        if move[0] == "layout":
            _, u, v = move
            d.layout[u], d.layout[v] = d.layout[v], d.layout[u]
        elif move[0] == "order":
            k = move[1]
            d.order[k], d.order[k + 1] = d.order[k + 1], d.order[k]
        else:
            _, j, value = move
            d.decisions[j] = value
        return d

    def _solution(self, c: Candidate) -> RoutingSolution:
        _, _, swaps = self._enc.decode(c.layout, c.order, c.decisions, record=True)
        order = tuple(c.order)
        return RoutingSolution(initial_layout=tuple(c.layout), swaps=tuple(swaps),
                               gate_order=None if order == tuple(range(self._enc.m)) else order)

    # -- the three algorithms ---------------------------------------------------

    def _random_search(self) -> None:
        while not self._out_of_budget():
            self._new_candidate()
            self._iters += 1

    def _tabu_search(self) -> None:
        cur = self._new_candidate()
        tabu: dict[tuple, int] = {}
        it = 0
        last_improvement = 0
        best_cost = self._best.cost
        while not self._out_of_budget():
            it += 1
            if it - last_improvement > self.stagnation:
                cur = self._new_candidate()
                tabu.clear()
                last_improvement = it
                self._restarts += 1
                continue
            exchangeable = self._enc.exchangeable(cur.order) if self._enc.m >= 2 else []
            chosen = None
            fallback = None
            for _ in range(self.candidates):
                if self._out_of_budget():
                    break
                attr, move = self._random_move(cur, exchangeable)
                cand = self._evaluate(self._apply(cur, move))
                if fallback is None or cand.cost < fallback[1].cost:
                    fallback = (attr, cand)
                # Aspiration: a tabu move is admissible if it beats the best known cost.
                admissible = tabu.get(attr, -1) < it or cand.cost < best_cost
                if admissible and (chosen is None or cand.cost < chosen[1].cost):
                    chosen = (attr, cand)
            chosen = chosen or fallback  # all sampled moves tabu: take the least bad one
            if chosen is None:
                break
            attr, cur = chosen
            tabu[attr] = it + self.tenure
            if self._best.cost < best_cost:
                best_cost = self._best.cost
                last_improvement = it
        self._iters = it

    def _genetic_algorithm(self) -> None:
        rng, enc = self._rng, self._enc
        pop: list[Candidate] = []
        while len(pop) < self.population and not self._out_of_budget():
            pop.append(self._new_candidate())

        def tournament() -> Candidate:
            return min(rng.sample(pop, min(self.tournament, len(pop))), key=lambda c: c.cost)

        gen = 0
        while not self._out_of_budget():
            gen += 1
            pop.sort(key=lambda c: c.cost)
            nxt = [c.copy() for c in pop[:self.elitism]]
            while len(nxt) < self.population and not self._out_of_budget():
                p1, p2 = tournament(), tournament()
                if rng.random() < self.crossover_rate:
                    decisions = [x if rng.random() < 0.5 else y for x, y in zip(p1.decisions, p2.decisions)]
                    child = Candidate(order_crossover(p1.layout, p2.layout, rng),
                                      precedence_crossover(p1.order, p2.order, rng), decisions)
                else:
                    child = p1.copy()
                for t in self._move_types():  # each operator independently with p_m
                    if rng.random() >= self.mutation_rate:
                        continue
                    if t == "layout":
                        child = self._apply(child, ("layout", *rng.sample(range(enc.n), 2)))
                    elif t == "order":
                        exchangeable = enc.exchangeable(child.order)
                        if exchangeable:
                            child = self._apply(child, ("order", rng.choice(exchangeable)))
                    else:
                        j = rng.randrange(enc.m)
                        child = self._apply(child, ("decision", j, (child.decisions[j] + rng.randrange(1, 3)) % 3))
                nxt.append(self._evaluate(child))
            pop = nxt
        self._iters = gen

    # -- shared polish ------------------------------------------------------------

    def _polish(self, c: Candidate) -> Candidate:
        """Best-improvement descent over all single moves until no move lowers the cost.

        Not counted in ``max_evals``; capped at another ``max_evals`` evaluations
        and at the time limit, which it never reaches on the paper's instances.
        """
        enc = self._enc
        cap = self._evals + self.max_evals
        cur = c.copy()
        improved = True
        while improved and self._evals < cap and time.monotonic() <= self._deadline:
            improved = False
            moves = [("layout", u, v) for u in range(enc.n) for v in range(u + 1, enc.n)]
            moves += [("order", k) for k in enc.exchangeable(cur.order)]
            moves += [("decision", j, v) for j in range(enc.m) for v in range(3) if v != cur.decisions[j]]
            best_neighbor = None
            for move in moves:
                if self._evals >= cap:
                    break
                cand = self._evaluate(self._apply(cur, move))
                if cand.cost < cur.cost - 1e-12 and (best_neighbor is None or cand.cost < best_neighbor.cost):
                    best_neighbor = cand
            if best_neighbor is not None:
                cur = best_neighbor
                improved = True
        return cur
