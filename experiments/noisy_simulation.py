"""Noisy simulation of compiled circuits (Section 6.3, "Noisy simulation").

For a circuit compiled from |00000>, the simulated fidelity is <psi|rho|psi>,
where psi is its noiseless output state and rho its output under one of three
noise models (exact density matrices, no shot noise):

- ``F_depol``: depolarizing noise matched to the fidelity model
  (p = 2(1 - f) for ``r``, p = 4(1 - f)/3 for ``cz``), the noise the proxy describes;
- ``F_adonis``: the Aer noise model of IQM's ``IQMFakeAdonis`` from qiskit-iqm 17.8
  (depolarizing errors and relaxation during gates);
- ``F_adonis_idle``: the same plus thermal relaxation on idle qubits after an
  ALAP schedule, with the T1, T2 and gate durations of the same backend, which
  the proxy does not model.

``equiv`` records whether the compiled circuit implements the input unitary.
"""

from __future__ import annotations

from functools import cache

from experiments.common import RAW, models, suite


@cache
def adonis_backend():
    from iqm.qiskit_iqm import IQMFakeAdonis

    return IQMFakeAdonis()


def depolarizing_noise(model):
    from qiskit_aer.noise import NoiseModel, depolarizing_error

    nm = NoiseModel(basis_gates=["r", "cz"])
    for q, f in enumerate(model.one_qubit):
        nm.add_quantum_error(depolarizing_error(2 * (1 - f), 1), "r", [q])
    for (a, b), f in model.two_qubit.items():
        e = depolarizing_error(4 * (1 - f) / 3, 2)
        nm.add_quantum_error(e, "cz", [a, b])
        nm.add_quantum_error(e, "cz", [b, a])
    return nm


def adonis_noise():
    return adonis_backend().noise_model


def with_idle_relaxation(qc):
    """ALAP-schedule ``qc`` and add thermal relaxation on every idle period (dt = 1 ns)."""
    from qiskit import QuantumCircuit
    from qiskit.transpiler import InstructionDurations, PassManager
    from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDelay
    from qiskit_aer.noise import thermal_relaxation_error

    backend = adonis_backend()
    profile = backend.error_profile
    t1 = {backend.qubit_name_to_index(q): t for q, t in profile.t1s.items()}  # ns
    t2 = {backend.qubit_name_to_index(q): t for q, t in profile.t2s.items()}
    r_ns = int(profile.single_qubit_gate_durations["prx"])
    cz_ns = int(profile.two_qubit_gate_durations["cz"])
    durations = InstructionDurations([("r", None, r_ns), ("cz", None, cz_ns)], dt=1e-9)
    scheduled = PassManager([ALAPScheduleAnalysis(durations), PadDelay()]).run(qc)
    out = QuantumCircuit(qc.num_qubits)
    for inst in scheduled.data:
        qs = [scheduled.find_bit(q).index for q in inst.qubits]
        if inst.operation.name == "delay":
            for q in qs:
                out.append(thermal_relaxation_error(t1[q], t2[q], inst.operation.duration), [q])
        else:
            out.append(inst.operation, qs)
    return out


def simulate(t: dict) -> dict:
    import numpy as np
    from qiskit import qpy
    from qiskit.quantum_info import DensityMatrix, Operator, Statevector, state_fidelity
    from qiskit_aer import AerSimulator

    from odra5_router.fidelity import fidelity_cost

    model = models()[t["model"]]
    with (RAW / t["qpy"]).open("rb") as f:
        qc = qpy.load(f)[0].remove_final_measurements(inplace=False)
    original = suite(t["suite"])[t["inst"]].remove_final_measurements(inplace=False)
    psi = Statevector(qc)
    sim = AerSimulator(method="density_matrix")

    def fidelity(circ, noise):
        c = circ.copy()
        c.save_density_matrix()
        rho = DensityMatrix(sim.run(c, noise_model=noise).result().data(0)["density_matrix"])
        return float(state_fidelity(rho, psi))

    adonis = adonis_noise()
    cost = fidelity_cost(qc, model)
    try:
        equiv = bool(Operator.from_circuit(qc).equiv(Operator(original)))
    except Exception:
        equiv = None
    return dict(t, cost=cost, proxy=float(np.exp(-cost)),
                F_depol=fidelity(qc, depolarizing_noise(model)),
                F_adonis=fidelity(qc, adonis),
                F_adonis_idle=fidelity(with_idle_relaxation(qc), adonis),
                equiv=equiv, n_cz=int(qc.count_ops().get("cz", 0)), depth=qc.depth(), status="ok")
