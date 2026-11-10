# Benchmark circuits

Written by `python -m experiments.export_benchmarks` from `src/odra5_router/benchmarks.py`.
The circuits are OpenQASM 2.0 as given to the compiler, before adjacent CX pairs are cancelled.
`random_circuit(n, g, p, seed)` draws `g` steps; each step is a CX on a random pair of qubits with
probability `p`, otherwise an H and an RZ with a random angle on random qubits.
`fidelity_models.json` holds every fidelity model; `adonis` is the main one.

## Odra5 benchmark (103 circuits with two-qubit gates)

| Name | Group | 2Q gates after reduction | Depth | Source |
|---|---|---|---|---|
| `tiny_0` | Random tiny | 3 | 3 | random_circuit(n=5, num_gates=4, p_two_qubit=0.5, seed=0) |
| `tiny_1` | Random tiny | 2 | 5 | random_circuit(n=5, num_gates=6, p_two_qubit=0.5, seed=1) |
| `small_0` | Random small | 3 | 6 | random_circuit(n=5, num_gates=10, p_two_qubit=0.4, seed=42) |
| `small_1` | Random small | 4 | 9 | random_circuit(n=5, num_gates=12, p_two_qubit=0.4, seed=99) |
| `medium_0` | Random medium | 5 | 10 | random_circuit(n=5, num_gates=20, p_two_qubit=0.35, seed=123) |
| `medium_1` | Random medium | 9 | 17 | random_circuit(n=5, num_gates=25, p_two_qubit=0.35, seed=456) |
| `heavy_0` | Random heavy | 13 | 23 | random_circuit(n=5, num_gates=40, p_two_qubit=0.3, seed=789) |
| `heavy_1` | Random heavy | 14 | 31 | random_circuit(n=5, num_gates=50, p_two_qubit=0.3, seed=1001) |
| `dense_0` | Random dense | 38 | 44 | random_circuit(n=5, num_gates=60, p_two_qubit=0.7, seed=2024) |
| `dense_1` | Random dense | 51 | 54 | random_circuit(n=5, num_gates=80, p_two_qubit=0.65, seed=2025) |
| `hard_2r` | Adversarial | 12 | 11 | adversarial_circuit(rounds=2): one CX on each of the six leaf pairs per round |
| `hard_4r` | Adversarial | 24 | 19 | adversarial_circuit(rounds=4): one CX on each of the six leaf pairs per round |
| `hard_8r` | Adversarial | 48 | 38 | adversarial_circuit(rounds=8): one CX on each of the six leaf pairs per round |
| `tiny_s100` | Random tiny | 3 | 4 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=100) |
| `tiny_s101` | Random tiny | 0 | 2 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=101) (not used: no two-qubit gate after reduction) |
| `tiny_s102` | Random tiny | 3 | 5 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=102) |
| `tiny_s103` | Random tiny | 2 | 3 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=103) |
| `tiny_s104` | Random tiny | 2 | 7 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=104) |
| `tiny_s105` | Random tiny | 2 | 4 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=105) |
| `tiny_s106` | Random tiny | 1 | 5 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=106) |
| `tiny_s107` | Random tiny | 2 | 2 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=107) |
| `tiny_s108` | Random tiny | 3 | 3 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=108) |
| `tiny_s109` | Random tiny | 1 | 4 | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=109) |
| `small_s100` | Random small | 7 | 8 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=100) |
| `small_s101` | Random small | 5 | 8 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=101) |
| `small_s102` | Random small | 4 | 8 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=102) |
| `small_s103` | Random small | 3 | 7 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=103) |
| `small_s104` | Random small | 6 | 10 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=104) |
| `small_s105` | Random small | 2 | 7 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=105) |
| `small_s106` | Random small | 4 | 7 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=106) |
| `small_s107` | Random small | 5 | 7 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=107) |
| `small_s108` | Random small | 7 | 6 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=108) |
| `small_s109` | Random small | 4 | 7 | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=109) |
| `medium_s100` | Random medium | 10 | 16 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=100) |
| `medium_s101` | Random medium | 8 | 15 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=101) |
| `medium_s102` | Random medium | 8 | 18 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=102) |
| `medium_s103` | Random medium | 6 | 11 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=103) |
| `medium_s104` | Random medium | 9 | 13 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=104) |
| `medium_s105` | Random medium | 6 | 13 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=105) |
| `medium_s106` | Random medium | 5 | 14 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=106) |
| `medium_s107` | Random medium | 5 | 12 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=107) |
| `medium_s108` | Random medium | 8 | 12 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=108) |
| `medium_s109` | Random medium | 7 | 15 | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=109) |
| `heavy_s100` | Random heavy | 16 | 27 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=100) |
| `heavy_s101` | Random heavy | 17 | 31 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=101) |
| `heavy_s102` | Random heavy | 14 | 33 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=102) |
| `heavy_s103` | Random heavy | 9 | 24 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=103) |
| `heavy_s104` | Random heavy | 15 | 28 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=104) |
| `heavy_s105` | Random heavy | 9 | 24 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=105) |
| `heavy_s106` | Random heavy | 13 | 29 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=106) |
| `heavy_s107` | Random heavy | 13 | 24 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=107) |
| `heavy_s108` | Random heavy | 14 | 26 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=108) |
| `heavy_s109` | Random heavy | 14 | 29 | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=109) |
| `dense_s100` | Random dense | 45 | 45 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=100) |
| `dense_s101` | Random dense | 46 | 47 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=101) |
| `dense_s102` | Random dense | 42 | 51 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=102) |
| `dense_s103` | Random dense | 45 | 46 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=103) |
| `dense_s104` | Random dense | 44 | 50 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=104) |
| `dense_s105` | Random dense | 37 | 49 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=105) |
| `dense_s106` | Random dense | 41 | 41 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=106) |
| `dense_s107` | Random dense | 45 | 45 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=107) |
| `dense_s108` | Random dense | 41 | 43 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=108) |
| `dense_s109` | Random dense | 40 | 49 | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=109) |
| `hard_12r` | Adversarial | 72 | 58 | adversarial_circuit(rounds=12): one CX on each of the six leaf pairs per round |
| `hard_16r` | Adversarial | 96 | 77 | adversarial_circuit(rounds=16): one CX on each of the six leaf pairs per round |
| `ghz_5q` | Other structured | 4 | 14 | GHZ state (H and a CX chain) |
| `qft_5q` | Other structured | 20 | 44 | Qiskit QFT(5, do_swaps=False) |
| `aqft_5q` | Other structured | 14 | 44 | Qiskit QFT(5, approximation_degree=2, do_swaps=False) |
| `w_state_5q` | Other structured | 8 | 20 | W state (RY and a controlled-H cascade) |
| `bv_5q` | Other structured | 3 | 11 | Bernstein-Vazirani, secret 1011 |
| `grover_4q` | Other structured | 72 | 201 | Grover search on 4 qubits with an ancilla, 1 iteration |
| `qaoa_g0_p1` | QAOA MaxCut | 14 | 34 | QAOA MaxCut, p=1, random 5-node graph (edge probability 0.5, seed 300), gamma=0.39, beta=0.25 |
| `qaoa_g0_p2` | QAOA MaxCut | 28 | 62 | QAOA MaxCut, p=2, random 5-node graph (edge probability 0.5, seed 300), gamma=0.39, beta=0.25 |
| `qaoa_g1_p1` | QAOA MaxCut | 12 | 28 | QAOA MaxCut, p=1, random 5-node graph (edge probability 0.5, seed 301), gamma=0.39, beta=0.25 |
| `qaoa_g1_p2` | QAOA MaxCut | 24 | 48 | QAOA MaxCut, p=2, random 5-node graph (edge probability 0.5, seed 301), gamma=0.39, beta=0.25 |
| `qaoa_g2_p1` | QAOA MaxCut | 10 | 22 | QAOA MaxCut, p=1, random 5-node graph (edge probability 0.5, seed 302), gamma=0.39, beta=0.25 |
| `qaoa_g2_p2` | QAOA MaxCut | 20 | 40 | QAOA MaxCut, p=2, random 5-node graph (edge probability 0.5, seed 302), gamma=0.39, beta=0.25 |
| `qaoa_g3_p1` | QAOA MaxCut | 10 | 28 | QAOA MaxCut, p=1, random 5-node graph (edge probability 0.5, seed 303), gamma=0.39, beta=0.25 |
| `qaoa_g3_p2` | QAOA MaxCut | 20 | 46 | QAOA MaxCut, p=2, random 5-node graph (edge probability 0.5, seed 303), gamma=0.39, beta=0.25 |
| `qaoa_g4_p1` | QAOA MaxCut | 12 | 28 | QAOA MaxCut, p=1, random 5-node graph (edge probability 0.5, seed 304), gamma=0.39, beta=0.25 |
| `qaoa_g4_p2` | QAOA MaxCut | 24 | 50 | QAOA MaxCut, p=2, random 5-node graph (edge probability 0.5, seed 304), gamma=0.39, beta=0.25 |
| `qv_5q_s0` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=0) |
| `qv_5q_s1` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=1) |
| `qv_5q_s2` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=2) |
| `qv_5q_s3` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=3) |
| `qv_5q_s4` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=4) |
| `qv_5q_s5` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=5) |
| `qv_5q_s6` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=6) |
| `qv_5q_s7` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=7) |
| `qv_5q_s8` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=8) |
| `qv_5q_s9` | Quantum Volume | 30 | 47 | Qiskit QuantumVolume(5, depth=5, seed=9) |
| `adder_1bit_5q` | Other structured | 15 | 40 | 1-bit full adder (CCX, CX) |
| `heisenberg_ring_r2` | Hamiltonian simulation | 60 | 182 | Heisenberg XXX model on a 5-ring, first-order Trotter, 2 steps, dt=0.1 |
| `ising_full_r2` | Hamiltonian simulation | 40 | 66 | transverse-field Ising model with all-to-all ZZ couplings, first-order Trotter, 2 steps |
| `heisenberg_ring_r4` | Hamiltonian simulation | 120 | 362 | Heisenberg XXX model on a 5-ring, first-order Trotter, 4 steps, dt=0.1 |
| `ising_full_r4` | Hamiltonian simulation | 80 | 122 | transverse-field Ising model with all-to-all ZZ couplings, first-order Trotter, 4 steps |
| `qaoa_k5_p3` | QAOA MaxCut | 60 | 94 | QAOA MaxCut on the complete graph K5, p=3 |
| `qaoa_k5_p4` | QAOA MaxCut | 80 | 122 | QAOA MaxCut on the complete graph K5, p=4 |
| `qaoa_ring_p6` | QAOA MaxCut | 60 | 182 | QAOA MaxCut on the 5-cycle, p=6 |
| `vqe_su2_full_r3` | Other structured | 30 | 43 | Qiskit EfficientSU2(5, reps=3, entanglement='full'), fixed random parameters |
| `vqe_su2_full_r6` | Other structured | 60 | 82 | Qiskit EfficientSU2(5, reps=6, entanglement='full'), fixed random parameters |
| `grover_4q_it3` | Other structured | 216 | 597 | Grover search on 4 qubits with an ancilla, 3 iterations |
| `qft_adder_2b` | Other structured | 10 | 32 | Qiskit DraperQFTAdder(2, kind='fixed') on the inputs 01 and 11 |
| `queko_d32` | Other structured | 15 | 25 | QUEKO (Tan and Cong) on the Odra5 graph, depth 32, densities (0.25, 0.3), seed 0; known zero-SWAP layout |

## Tuning split (25 circuits, disjoint from the benchmark)

| Name | Source |
|---|---|
| `tiny_s200` | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=200) |
| `tiny_s201` | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=201) |
| `tiny_s202` | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=202) |
| `tiny_s203` | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=203) |
| `tiny_s204` | random_circuit(n=5, num_gates=5, p_two_qubit=0.5, seed=204) |
| `small_s200` | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=200) |
| `small_s201` | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=201) |
| `small_s202` | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=202) |
| `small_s203` | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=203) |
| `small_s204` | random_circuit(n=5, num_gates=11, p_two_qubit=0.4, seed=204) |
| `medium_s200` | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=200) |
| `medium_s201` | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=201) |
| `medium_s202` | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=202) |
| `medium_s203` | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=203) |
| `medium_s204` | random_circuit(n=5, num_gates=22, p_two_qubit=0.35, seed=204) |
| `heavy_s200` | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=200) |
| `heavy_s201` | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=201) |
| `heavy_s202` | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=202) |
| `heavy_s203` | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=203) |
| `heavy_s204` | random_circuit(n=5, num_gates=45, p_two_qubit=0.3, seed=204) |
| `dense_s200` | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=200) |
| `dense_s201` | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=201) |
| `dense_s202` | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=202) |
| `dense_s203` | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=203) |
| `dense_s204` | random_circuit(n=5, num_gates=70, p_two_qubit=0.68, seed=204) |

## Larger stars (N = 5..8)

10 circuits per size and 5 fidelity models per size (`star_N<n>_model<k>` in
`fidelity_models.json`, f_1Q in [0.991, 0.995], f_2Q in [0.945, 0.970]).

| Name | 2Q gates after reduction | Source |
|---|---|---|
| `N5_c0` | 26 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=0) on a star with hub 0 and leaves 1..4 |
| `N5_c1` | 25 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=1) on a star with hub 0 and leaves 1..4 |
| `N5_c2` | 21 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=2) on a star with hub 0 and leaves 1..4 |
| `N5_c3` | 27 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=3) on a star with hub 0 and leaves 1..4 |
| `N5_c4` | 24 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=4) on a star with hub 0 and leaves 1..4 |
| `N5_c5` | 24 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=5) on a star with hub 0 and leaves 1..4 |
| `N5_c6` | 25 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=6) on a star with hub 0 and leaves 1..4 |
| `N5_c7` | 27 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=7) on a star with hub 0 and leaves 1..4 |
| `N5_c8` | 30 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=8) on a star with hub 0 and leaves 1..4 |
| `N5_c9` | 22 | random_circuit(n=5, num_gates=40, p_two_qubit=0.7, seed=9) on a star with hub 0 and leaves 1..4 |
| `N6_c0` | 23 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=0) on a star with hub 0 and leaves 1..5 |
| `N6_c1` | 27 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=1) on a star with hub 0 and leaves 1..5 |
| `N6_c2` | 18 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=2) on a star with hub 0 and leaves 1..5 |
| `N6_c3` | 29 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=3) on a star with hub 0 and leaves 1..5 |
| `N6_c4` | 28 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=4) on a star with hub 0 and leaves 1..5 |
| `N6_c5` | 20 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=5) on a star with hub 0 and leaves 1..5 |
| `N6_c6` | 25 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=6) on a star with hub 0 and leaves 1..5 |
| `N6_c7` | 28 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=7) on a star with hub 0 and leaves 1..5 |
| `N6_c8` | 31 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=8) on a star with hub 0 and leaves 1..5 |
| `N6_c9` | 27 | random_circuit(n=6, num_gates=40, p_two_qubit=0.7, seed=9) on a star with hub 0 and leaves 1..5 |
| `N7_c0` | 23 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=0) on a star with hub 0 and leaves 1..6 |
| `N7_c1` | 25 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=1) on a star with hub 0 and leaves 1..6 |
| `N7_c2` | 19 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=2) on a star with hub 0 and leaves 1..6 |
| `N7_c3` | 28 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=3) on a star with hub 0 and leaves 1..6 |
| `N7_c4` | 30 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=4) on a star with hub 0 and leaves 1..6 |
| `N7_c5` | 30 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=5) on a star with hub 0 and leaves 1..6 |
| `N7_c6` | 28 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=6) on a star with hub 0 and leaves 1..6 |
| `N7_c7` | 30 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=7) on a star with hub 0 and leaves 1..6 |
| `N7_c8` | 28 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=8) on a star with hub 0 and leaves 1..6 |
| `N7_c9` | 27 | random_circuit(n=7, num_gates=40, p_two_qubit=0.7, seed=9) on a star with hub 0 and leaves 1..6 |
| `N8_c0` | 25 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=0) on a star with hub 0 and leaves 1..7 |
| `N8_c1` | 29 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=1) on a star with hub 0 and leaves 1..7 |
| `N8_c2` | 22 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=2) on a star with hub 0 and leaves 1..7 |
| `N8_c3` | 25 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=3) on a star with hub 0 and leaves 1..7 |
| `N8_c4` | 31 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=4) on a star with hub 0 and leaves 1..7 |
| `N8_c5` | 29 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=5) on a star with hub 0 and leaves 1..7 |
| `N8_c6` | 26 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=6) on a star with hub 0 and leaves 1..7 |
| `N8_c7` | 28 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=7) on a star with hub 0 and leaves 1..7 |
| `N8_c8` | 30 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=8) on a star with hub 0 and leaves 1..7 |
| `N8_c9` | 23 | random_circuit(n=8, num_gates=40, p_two_qubit=0.7, seed=9) on a star with hub 0 and leaves 1..7 |
