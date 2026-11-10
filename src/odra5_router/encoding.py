"""The solution encoding of Section 4.1 and its decoder.

A candidate is ``(layout, order, decisions)``:

- ``layout[v]``: physical qubit of logical qubit ``v`` (the layout pi),
- ``order``: an execution order of the ``m`` interactions, any linear
  extension of their dependency DAG (sigma),
- ``decisions[j]`` in {0, 1, 2}, indexed by interaction (r_j): for ``I_j = (a, b)``
  0 = no SWAP if ``a`` and ``b`` are adjacent (otherwise as 1),
  1 = ``a`` must be on the hub when ``I_j`` runs, 2 = ``b`` must be on the hub.

If the required operand is not on the hub, the decoder inserts one SWAP
between it and the hub. The decisions name an operand, not a coupler, so every
candidate decodes to a feasible route whatever the layout, and decisions keep
their meaning when recombined across parents with different layouts.
"""

from __future__ import annotations

import random

from odra5_router.fidelity import FidelityModel
from odra5_router.problem import RoutingProblem, build_plan

_INF = float("inf")

# Lookahead of the "lookahead" start: the operand with more upcoming
# interactions (weighted 1/d over the next 14) goes to the hub.
_HORIZON = 14
_WEIGHTS = tuple(1.0 / d for d in range(1, _HORIZON + 1))


class Encoding:
    """A routing problem and fidelity model compiled to flat lists for a fast decoder."""

    def __init__(self, problem: RoutingProblem, model: FidelityModel) -> None:
        plan = build_plan(problem)
        n = problem.num_qubits
        edges = {tuple(sorted(e)) for e in problem.coupling_map.get_edges()}
        degree = [0] * n
        for a, b in edges:
            degree[a] += 1
            degree[b] += 1
        hub = max(range(n), key=lambda q: degree[q])
        if any(hub not in e for e in edges):
            raise ValueError("the encoding needs a star coupling map")

        self.n = n
        self.hub = hub
        self.inter = plan.interactions
        self.m = len(self.inter)
        self.attached = tuple(tuple(q for _, q in plan.attached[j]) for j in range(self.m))
        self.leftover = tuple(q for _, q in plan.leftover)
        self.c1 = [model.cost_1q(p) for p in range(n)]
        self.c2 = [[_INF] * n for _ in range(n)]
        for a, b in edges:
            self.c2[a][b] = self.c2[b][a] = model.cost_2q(a, b)
        self.qcount = [0] * n
        for a, b in self.inter:
            self.qcount[a] += 1
            self.qcount[b] += 1

        # Dependency DAG: interaction j depends on the previous interaction on each of its qubits.
        last = [-1] * n
        preds: list[set[int]] = [set() for _ in range(self.m)]
        for j, (a, b) in enumerate(self.inter):
            for q in (a, b):
                if last[q] >= 0:
                    preds[j].add(last[q])
                last[q] = j
        self.preds = tuple(tuple(p) for p in preds)
        succs: list[list[int]] = [[] for _ in range(self.m)]
        for j, ps in enumerate(self.preds):
            for p in ps:
                succs[p].append(j)
        self.succs = tuple(tuple(s) for s in succs)

    def decode(self, layout, order, decisions, record: bool = False):
        """Return ``(cost, n_swaps, swaps)``; ``swaps`` is built only with ``record``.

        ``cost`` equals :func:`odra5_router.problem.solution_cost` of the decoded route.
        """
        hub, c1, c2, inter, attached = self.hub, self.c1, self.c2, self.inter, self.attached
        pos = list(layout)
        occ = [0] * self.n
        for v, p in enumerate(pos):
            occ[p] = v
        cost = 0.0
        ns = 0
        swaps = [] if record else None
        for j in order:
            a, b = inter[j]
            pa, pb = pos[a], pos[b]
            r = decisions[j]
            mover = -1
            if pa == hub or pb == hub:
                if r == 1 and pa != hub:
                    mover = a
                elif r == 2 and pb != hub:
                    mover = b
            else:
                mover = b if r == 2 else a
            if mover >= 0:
                pm = pos[mover]
                other = occ[hub]
                pos[mover] = hub
                pos[other] = pm
                occ[hub] = mover
                occ[pm] = other
                cost += 3.0 * c2[pm][hub]
                ns += 1
                if record:
                    swaps.append((j, pm, hub))
            for q in attached[j]:
                cost += c1[pos[q]]
            cost += c2[pos[a]][pos[b]]
        for q in self.leftover:
            cost += c1[pos[q]]
        return cost, ns, swaps

    def lookahead_decisions(self, layout, order) -> list[int]:
        """Decisions of a demand lookahead: at a leaf-leaf interaction the operand
        with more weighted upcoming interactions is brought to the hub."""
        hub, inter = self.hub, self.inter
        pos = list(layout)
        occ = [0] * self.n
        for v, p in enumerate(pos):
            occ[p] = v
        remaining = list(self.qcount)
        decisions = [0] * self.m
        m = len(order)
        for idx in range(m):
            j = order[idx]
            a, b = inter[j]
            remaining[a] -= 1
            remaining[b] -= 1
            if pos[a] == hub or pos[b] == hub:
                continue
            sa = sb = 0.0
            for w, k in enumerate(range(idx + 1, min(m, idx + 1 + _HORIZON))):
                x, y = inter[order[k]]
                if a in (x, y):
                    sa += _WEIGHTS[w]
                if b in (x, y):
                    sb += _WEIGHTS[w]
            if abs(sa - sb) < 1e-5:
                mover = b if remaining[b] > remaining[a] else a
            else:
                mover = b if sb > sa else a
            pm = pos[mover]
            other = occ[hub]
            pos[mover] = hub
            pos[other] = pm
            occ[hub] = mover
            occ[pm] = other
            decisions[j] = 1 if mover == a else 2
        return decisions

    def from_routed(self, routed, layout) -> tuple[list[int], list[int], list[int]]:
        """Candidate that reproduces the hub schedule of a circuit routed by another router.

        ``routed`` was produced from this problem's circuit (e.g. by SABRE) and
        starts from ``layout``. Each two-qubit gate is matched to the next
        unexecuted interaction of its logical qubits, and its decision names
        the operand that was on the hub. The decoded route puts the same qubit
        on the hub at every interaction with at most one SWAP before it, so it
        never has more SWAPs than ``routed``.
        """
        hub = self.hub
        pos = list(layout)
        occ = [0] * self.n
        for v, p in enumerate(pos):
            occ[p] = v
        queue: list[list[int]] = [[] for _ in range(self.n)]
        for j, (a, b) in enumerate(self.inter):
            queue[a].append(j)
            queue[b].append(j)
        ptr = [0] * self.n
        order: list[int] = []
        decisions = [0] * self.m
        for inst in routed.data:
            qs = [routed.find_bit(q).index for q in inst.qubits]
            if len(qs) != 2:
                continue
            p, q = qs
            if inst.operation.name == "swap":
                u, w = occ[p], occ[q]
                occ[p], occ[q] = w, u
                pos[u], pos[w] = q, p
                continue
            a, b = occ[p], occ[q]
            j = queue[a][ptr[a]]
            if queue[b][ptr[b]] != j:
                raise ValueError("routed circuit does not follow the interaction DAG")
            ptr[a] += 1
            ptr[b] += 1
            order.append(j)
            on_hub = a if pos[a] == hub else b
            decisions[j] = 1 if on_hub == self.inter[j][0] else 2
        if len(order) != self.m:
            raise ValueError("routed circuit misses interactions")
        return list(layout), order, decisions

    def random_order(self, rng: random.Random, local: bool = False) -> list[int]:
        """Random linear extension of the DAG (Kahn's algorithm, random choice among ready interactions).

        With ``local`` the next interaction is drawn among the ready ones that
        share a qubit with the previous one whenever there are any, so that
        blocks of gates on the same qubits are not interleaved at random.
        """
        indeg = [len(p) for p in self.preds]
        ready = [j for j in range(self.m) if indeg[j] == 0]
        out: list[int] = []
        while ready:
            k = rng.randrange(len(ready))
            if local and out:
                a, b = self.inter[out[-1]]
                near = [i for i, r in enumerate(ready) if a in self.inter[r] or b in self.inter[r]]
                if near:
                    k = near[rng.randrange(len(near))]
            j = ready.pop(k)
            out.append(j)
            for s in self.succs[j]:
                indeg[s] -= 1
                if indeg[s] == 0:
                    ready.append(s)
        return out

    def exchangeable(self, order) -> list[int]:
        """Positions ``k`` where ``order[k]`` and ``order[k+1]`` act on disjoint qubits."""
        out = []
        for k in range(len(order) - 1):
            a, b = self.inter[order[k]]
            c, d = self.inter[order[k + 1]]
            if a != c and a != d and b != c and b != d:
                out.append(k)
        return out

    def is_topological(self, order) -> bool:
        seen = [False] * self.m
        for j in order:
            if any(not seen[p] for p in self.preds[j]):
                return False
            seen[j] = True
        return len(order) == self.m and all(seen)
