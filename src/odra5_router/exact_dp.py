"""Exact routing by Dijkstra's algorithm (Section 4.4).

States are ``(frontier, positions)``: the set of ready interactions and the
physical qubit of every logical qubit. A move either executes a ready
interaction whose qubits are adjacent, paying its two-qubit gate and the
single-qubit gates attached to it, or applies a SWAP on any coupler, at any
time and any number of times, paying three CZ gates on that coupler. All
initial layouts start at cost zero and every linear extension of the DAG is
reachable, so the result is optimal for Eq. 2 over all routes that keep the
order of interactions sharing a qubit, place single-qubit gates as in
:mod:`odra5_router.problem` and do not exploit commutation or resynthesis.

``primary="swaps"`` minimises the SWAP count first and the cost second (the
lexicographic variant of the ablation). The fidelity-blind variant is this
solver with a uniform fidelity model.
"""

from __future__ import annotations

import heapq
import itertools
import time

from odra5_router.fidelity import FidelityModel, adonis_model
from odra5_router.problem import RoutingProblem, RoutingSolution, build_plan, swap_positions


class ExactDP:
    def __init__(self, *, fidelity: FidelityModel | None = None, primary: str = "fidelity") -> None:
        if primary not in ("fidelity", "swaps"):
            raise ValueError("primary must be 'fidelity' or 'swaps'")
        self.fidelity = fidelity
        self.primary = primary

    def solve(self, problem: RoutingProblem, *, seed: int = 0, budget_s: float = 30.0) -> RoutingSolution:
        """Optimal route; raises ``TimeoutError`` if the search does not finish within ``budget_s``.

        ``seed`` is accepted for a uniform interface with the other routers and ignored.
        """
        model = self.fidelity or adonis_model()
        plan = build_plan(problem)
        cm = problem.coupling_map
        n = problem.num_qubits
        inter = plan.interactions
        m = len(inter)
        if m == 0:
            return RoutingSolution(initial_layout=tuple(range(n)))
        edges = {tuple(sorted(e)) for e in cm.get_edges()}

        # Interaction k precedes j if they share a qubit and k is on a lower DAG level.
        prev_level = [0] * n
        levels: list[int] = []
        for a, b in inter:
            lvl = max(prev_level[a], prev_level[b]) + 1
            levels.append(lvl)
            prev_level[a] = prev_level[b] = lvl
        preds = [[k for k in range(m) if levels[k] < levels[j] and (inter[k][0] in inter[j] or inter[k][1] in inter[j])]
                 for j in range(m)]
        # above[j]: bitmask of j and everything that depends on it.
        above = [0] * m
        for j in range(m - 1, -1, -1):
            mask = 1 << j
            for k in range(j + 1, m):
                if j in preds[k]:
                    mask |= above[k]
            above[j] = mask

        def ready(done: int) -> int:
            mask = 0
            for j in range(m):
                if not done & (1 << j) and all(done & (1 << p) for p in preds[j]):
                    mask |= 1 << j
            return mask

        swaps_first = self.primary == "swaps"

        def key_of(cost: float, nswaps: int) -> tuple:
            return (nswaps, cost) if swaps_first else (cost, nswaps)

        inf = (float("inf"), float("inf"))
        best: dict[tuple, tuple] = {}
        came_from: dict[tuple, tuple] = {}  # state -> (previous state, ("adv", j) | ("swap", (a, b)))
        start = ready(0)
        heap = []
        for layout in itertools.permutations(range(n)):
            state = (start, layout)
            heap.append((*key_of(0.0, 0), state))
            best[state] = key_of(0.0, 0)
        heapq.heapify(heap)
        deadline = time.monotonic() + budget_s
        terminal = None  # (cost, nswaps, state)

        while heap:
            if time.monotonic() > deadline:
                break
            k0, k1, state = heapq.heappop(heap)
            if best.get(state) != (k0, k1):
                continue
            cost, nswaps = (k1, k0) if swaps_first else (k0, k1)
            frontier, pos = state
            if frontier == 0:
                total = cost
                for _, q in plan.leftover:
                    total += model.cost_1q(pos[q])
                if terminal is None or key_of(total, nswaps) < key_of(terminal[0], terminal[1]):
                    terminal = (total, nswaps, state)
                continue

            # The executed set is everything that is not in or above the frontier.
            up = 0
            f = frontier
            while f:
                bit = f & -f
                up |= above[bit.bit_length() - 1]
                f ^= bit
            done = ((1 << m) - 1) ^ up

            f = frontier
            while f:
                bit = f & -f
                j = bit.bit_length() - 1
                f ^= bit
                a, b = inter[j]
                pa, pb = pos[a], pos[b]
                if cm.distance(pa, pb) > 1:
                    continue
                step = model.cost_2q(pa, pb)
                for _, q in plan.attached[j]:
                    step += model.cost_1q(pos[q])
                nxt = (ready(done | bit), pos)
                value = key_of(cost + step, nswaps)
                if value < best.get(nxt, inf):
                    best[nxt] = value
                    came_from[nxt] = (state, ("adv", j))
                    heapq.heappush(heap, (*value, nxt))

            for a, b in edges:
                new_pos = list(pos)
                swap_positions(new_pos, a, b)
                nxt = (frontier, tuple(new_pos))
                value = key_of(cost + model.cost_swap(a, b), nswaps + 1)
                if value < best.get(nxt, inf):
                    best[nxt] = value
                    came_from[nxt] = (state, ("swap", (a, b)))
                    heapq.heappush(heap, (*value, nxt))

        if terminal is None:
            raise TimeoutError(f"exact DP did not finish within {budget_s} s")

        order_rev: list[int] = []
        swaps_rev: list[tuple[int, tuple[int, int]]] = []
        next_adv = None
        state = terminal[2]
        while state in came_from:
            state, move = came_from[state]
            if move[0] == "adv":
                next_adv = move[1]
                order_rev.append(next_adv)
            else:
                swaps_rev.append((next_adv, move[1]))
        order = list(reversed(order_rev))
        by_interaction: dict[int, list[tuple[int, int]]] = {}
        for j, edge in reversed(swaps_rev):
            by_interaction.setdefault(j, []).append(edge)
        swaps = tuple((j, a, b) for j in sorted(by_interaction) for a, b in by_interaction[j])
        return RoutingSolution(initial_layout=state[1], swaps=swaps,
                               gate_order=None if order == list(range(m)) else tuple(order))
