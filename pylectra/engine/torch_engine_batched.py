"""Batched (over-samples) torch engine — Phase 2/3 of the GPU-batched plan.

This module is *additive*: it does not touch :mod:`pylectra.engine.torch_engine`
or the scipy native engine.  It implements the two device-side primitives that
let one GPU pass simulate ``B`` independent samples in parallel:

* :class:`BatchedNetworkSolver` — holds a (homogeneous or per-sample) dense
  complex Y-bus on the device, LU-factored once per leg.  ``solve_for_U``
  takes batched generator state and returns ``U`` of shape ``(B, nb)``.
* :class:`BatchedDynamicsRHS` — ``f(t, y) -> dy/dt`` where ``y`` is shape
  ``(B, S)`` flat.  Parameters are stored as ``(1, ngen)`` (or ``(B, ngen)``
  for heterogeneous machine constants) and broadcast over the batch axis.

Restricted to the same model subset as :mod:`pylectra.engine.torch_engine`:
genmodel=2, excmodel=3, govmodel=1, pssmodel=3.

The integration driver itself (batched RK4) and the public ``run()`` entry
land in Phase 3 — this file is the math kernel only.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from pylectra.core import freq as _pds_freq
from pylectra.core.idx import idx_bus
from pylectra.engine.state import StateLayout
from pylectra.engine.torch_engine import _build_dense_Y_numpy, _torch_or_die


# ---------------------------------------------------------------------------
# Network solver
# ---------------------------------------------------------------------------

class BatchedNetworkSolver:
    """Batched dense complex Y-bus + LU.

    Parameters
    ----------
    baseMVA, bus, branch:
        Host-side MATPOWER arrays used to build the augmented Y-bus on numpy.
        For the homogeneous case all samples share one ``(nb, nb)`` matrix
        (we still upload it as ``(1, nb, nb)`` so torch broadcast handles
        the batch dim cleanly).  For the heterogeneous case, pass a list of
        per-sample ``bus``/``branch`` arrays via :meth:`rebuild_per_sample`.
    gbus:
        Generator bus indices (numpy, 0-based).
    xd_tr:
        Per-generator transient reactance (numpy, ``(ngen,)``).
    U_init:
        Pre-fault bus voltages used for the load-augmentation term.
    batch_size:
        ``B`` — the number of samples to simulate in parallel.
    homogeneous:
        If True, store ``Y`` as ``(1, nb, nb)`` and broadcast on solve.
    """

    def __init__(self, baseMVA, bus, branch, gbus, xd_tr, U_init,
                 *, batch_size: int, device, real_dtype, complex_dtype,
                 homogeneous: bool = True,
                 bus_per_sample=None, branch_per_sample=None,
                 U_init_per_sample=None):
        torch = _torch_or_die()
        self.torch = torch
        self.B = int(batch_size)
        self.baseMVA = float(baseMVA)
        self.bus = bus
        self.branch = branch
        self.gbus_np = np.asarray(gbus, dtype=int)
        self.xd_tr_np = np.asarray(xd_tr, dtype=float)
        self.U_init = np.asarray(U_init, dtype=complex)
        self.device = device
        self.real_dtype = real_dtype
        self.complex_dtype = complex_dtype

        # Per-sample heterogeneous mode: ``bus_per_sample`` is a list/array
        # of length B with each entry the same shape as ``bus``; same for
        # ``branch_per_sample``; ``U_init_per_sample`` is ``(B, nb)``.
        self._het = (bus_per_sample is not None
                     and branch_per_sample is not None)
        self.homogeneous = bool(homogeneous) and not self._het
        self.bus_per_sample = bus_per_sample
        self.branch_per_sample = branch_per_sample
        self.U_init_per_sample = (np.asarray(U_init_per_sample, dtype=complex)
                                  if U_init_per_sample is not None else None)

        self.nb = int(bus.shape[0])
        self.gbus = torch.tensor(self.gbus_np, dtype=torch.long, device=device)

        # Filled by :meth:`rebuild`.
        self._Y: Optional[object] = None
        self._lu: Optional[object] = None
        self._lu_pivots: Optional[object] = None

        self.rebuild()

    # ------------------------------------------------------------------
    def rebuild(self) -> None:
        """(Re)build the Y-bus tensor (homogeneous ``(1, nb, nb)`` or
        heterogeneous ``(B, nb, nb)``) and LU-factor on the device."""
        torch = self.torch
        ib = idx_bus()
        PD, QD = ib[6], ib[7]

        if self._het:
            B = self.B
            nb = self.nb
            Y_stack = np.empty((B, nb, nb), dtype=complex)
            for i in range(B):
                bus_i = self.bus_per_sample[i]
                branch_i = self.branch_per_sample[i]
                U_i = (self.U_init_per_sample[i]
                       if self.U_init_per_sample is not None else self.U_init)
                Pl = bus_i[:, PD] / self.baseMVA
                Ql = bus_i[:, QD] / self.baseMVA
                Y_stack[i] = _build_dense_Y_numpy(
                    self.baseMVA, bus_i, branch_i,
                    self.xd_tr_np, self.gbus_np, Pl, Ql, U_i,
                )
            Y = torch.tensor(Y_stack, dtype=self.complex_dtype,
                             device=self.device)
        else:
            Pl = self.bus[:, PD] / self.baseMVA
            Ql = self.bus[:, QD] / self.baseMVA
            Y_np = _build_dense_Y_numpy(self.baseMVA, self.bus, self.branch,
                                        self.xd_tr_np, self.gbus_np, Pl, Ql,
                                        self.U_init)
            Y = torch.tensor(Y_np, dtype=self.complex_dtype,
                             device=self.device).unsqueeze(0)

        self._Y = Y
        self._lu, self._lu_pivots = torch.linalg.lu_factor(Y)

    # ------------------------------------------------------------------
    def solve_for_U(self, Xgen, xd_tr_b):
        """Solve ``Y · U = scatter(I_gen)`` for U.

        Parameters
        ----------
        Xgen:
            ``(B, ngen, n_xgen)`` real tensor.  Columns 0/2/3 are
            ``delta``, ``Eq'``, ``Ed'``.
        xd_tr_b:
            ``(1, ngen)`` (or ``(B, ngen)``) real tensor of transient
            reactances — broadcast against the state slice.

        Returns
        -------
        U:
            ``(B, nb)`` complex bus-voltage tensor.
        """
        torch = self.torch
        delta = Xgen[:, :, 0]                       # (B, ngen)
        Eq = Xgen[:, :, 2]
        Ed = Xgen[:, :, 3]
        c = self.complex_dtype
        i = torch.tensor(1j, dtype=c, device=self.device)
        Eqc = Eq.to(c)
        Edc = Ed.to(c)
        deltac = delta.to(c)
        xdc = xd_tr_b.to(c)
        # Igen has shape (B, ngen) complex.
        Igen = (Eqc + i * Edc) * torch.exp(i * deltac) / (i * xdc)

        # Scatter into bus space: (B, nb) complex.
        Ig = torch.zeros(self.B, self.nb, dtype=c, device=self.device)
        # index_add_ along bus dim 1 with the (ngen,) gbus index, broadcast
        # over the batch axis automatically.
        Ig.index_add_(1, self.gbus, Igen)

        # lu_solve: (1, nb, nb) factors against (B, nb, 1) RHS → (B, nb, 1).
        U = torch.linalg.lu_solve(
            self._lu, self._lu_pivots, Ig.unsqueeze(-1)
        ).squeeze(-1)
        return U


# ---------------------------------------------------------------------------
# RHS callable
# ---------------------------------------------------------------------------

class BatchedDynamicsRHS:
    """Batched ``f(t, y) -> dy/dt`` running entirely on a torch device.

    All parameters broadcast over the batch axis: a homogeneous sweep stores
    them as ``(1, ngen)``, a heterogeneous sweep stores them as ``(B, ngen)``
    — the call site is identical thanks to torch broadcasting.
    """

    def __init__(self, layout: StateLayout, network: BatchedNetworkSolver,
                 *, Pgen, Pexc, Pgov,
                 device, real_dtype, complex_dtype,
                 batch_params: bool = False):
        torch = _torch_or_die()
        self.torch = torch
        self.layout = layout
        self.network = network
        self.device = device
        self.real_dtype = real_dtype
        self.complex_dtype = complex_dtype
        self.B = network.B

        Pgen = np.asarray(Pgen, dtype=float)
        Pexc = np.asarray(Pexc, dtype=float)
        Pgov = np.asarray(Pgov, dtype=float)

        # Build (1, ngen) (or (B, ngen)) parameter tensors.  ``batch_params``
        # is reserved for Phase 5 heterogeneous-machine sweeps; today the
        # homogeneous path uses (1, ngen) and lets broadcasting do the work.
        def _t(arr_1d):
            x = torch.tensor(np.asarray(arr_1d, dtype=float),
                             dtype=real_dtype, device=device)
            return x.unsqueeze(0)  # (1, ngen)

        # Generator type 2 parameters
        self.H      = _t(Pgen[:, 6])
        self.xd_tr  = _t(Pgen[:, 8])
        self.xq_tr  = _t(Pgen[:, 9])
        self.xd     = _t(Pgen[:, 10])
        self.xq     = _t(Pgen[:, 11])
        self.Td0_tr = _t(Pgen[:, 12])
        self.Tq0_tr = _t(Pgen[:, 13])
        self.D = torch.zeros_like(self.H)

        # Exciter type 3 parameters
        self.Tv = _t(Pexc[:, 1])
        self.mu = _t(Pexc[:, 2])
        self.k  = _t(Pexc[:, 3])
        self.L  = _t(Pexc[:, 6])

        self.freq = float(_pds_freq.freq)
        self.omegas = torch.tensor(2.0 * np.pi * self.freq,
                                   dtype=real_dtype, device=device)
        self.pi = torch.tensor(np.pi, dtype=real_dtype, device=device)

    # ------------------------------------------------------------------
    def __call__(self, t, y):
        """Compute dy/dt at (t, y).

        Parameters
        ----------
        t:
            0-d real torch tensor on the device (unused — the system is
            time-invariant within a leg).
        y:
            ``(B, S)`` flat real torch tensor.

        Returns
        -------
        dy:
            ``(B, S)`` flat real torch tensor.
        """
        torch = self.torch
        Xgen, Xexc, Xgov = self.layout.unpack_torch_batched(y)
        # Xgen: (B, ngen, 4); Xexc: (B, ngen, 1); Xgov: (B, ngen, 4)

        # Network solve — U: (B, nb) complex.
        U = self.network.solve_for_U(Xgen, self.xd_tr)
        Vexc = U.index_select(1, self.network.gbus)        # (B, ngen) complex

        delta = Xgen[:, :, 0]
        Eq = Xgen[:, :, 2]
        Ed = Xgen[:, :, 3]
        theta = torch.angle(Vexc)
        absU = torch.abs(Vexc)

        vd = -absU * torch.sin(delta - theta)
        vq =  absU * torch.cos(delta - theta)
        Id = (vq - Eq) / self.xd_tr
        Iq = -(vd - Ed) / self.xq_tr
        Pe = (Eq * Iq + Ed * Id
              + (self.xd_tr - self.xq_tr) * Id * Iq)

        # Generator (type 2) derivatives
        omega = Xgen[:, :, 1]
        Efd = Xexc[:, :, 0]
        Pm = Xgov[:, :, 0]
        ddelta = omega - self.omegas
        domega = (self.pi * self.freq / self.H) * (
            -self.D * (omega - self.omegas) / self.omegas + Pm - Pe
        )
        dEq = (1.0 / self.Td0_tr) * (Efd - Eq + (self.xd - self.xd_tr) * Id)
        dEd = (1.0 / self.Tq0_tr) * (-Ed - (self.xq - self.xq_tr) * Iq)

        # Exciter (type 3)
        dEfd = (-Efd - self.mu * self.k * absU * torch.cos(delta - theta)
                + self.L) / self.Tv

        # Governor (type 1): zero derivatives.
        dXgov = torch.zeros_like(Xgov)

        # Pack — stack along the inner (state-component) axis.
        dXgen = torch.stack([ddelta, domega, dEq, dEd], dim=2)  # (B, ngen, 4)
        dXexc = dEfd.unsqueeze(2)                               # (B, ngen, 1)
        dy = self.layout.pack_torch_batched(dXgen, dXexc, dXgov)
        return dy

    # ------------------------------------------------------------------
    def compute_outputs(self, y):
        """Post-pass helper: given a ``(N, S)`` stack of states (typically
        ``N = T*B`` flattened), return ``(U, Pe)`` of shapes ``(N, nb)``
        complex and ``(N, ngen)`` real, in one batched solve.

        Used by Phase 3's output assembly so we don't re-evaluate the RHS
        per row.
        """
        torch = self.torch
        # Re-route through unpack_torch_batched, treating the leading dim
        # as the batch dim regardless of its actual meaning.
        Xgen, Xexc, Xgov = self.layout.unpack_torch_batched(y)
        # Temporarily reuse the network solver.  Note: this requires the
        # solver to have been built with batch_size == y.shape[0].
        N = y.shape[0]
        if N != self.network.B:
            raise RuntimeError(
                "compute_outputs: y batch dim "
                f"{N} != network.B {self.network.B}; build a sized solver"
            )
        U = self.network.solve_for_U(Xgen, self.xd_tr)
        Vexc = U.index_select(1, self.network.gbus)
        delta = Xgen[:, :, 0]
        Eq = Xgen[:, :, 2]
        Ed = Xgen[:, :, 3]
        theta = torch.angle(Vexc)
        absU = torch.abs(Vexc)
        vd = -absU * torch.sin(delta - theta)
        vq =  absU * torch.cos(delta - theta)
        Id = (vq - Eq) / self.xd_tr
        Iq = -(vd - Ed) / self.xq_tr
        Pe = (Eq * Iq + Ed * Id
              + (self.xd_tr - self.xq_tr) * Id * Iq)
        return U, Pe


# ---------------------------------------------------------------------------
# Phase 3 — leg-by-leg integration loop
# ---------------------------------------------------------------------------

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from pylectra.core.case import NetworkCase
from pylectra.core.freq import set_freq as _set_freq
from pylectra.core.idx import idx_brch, idx_gen
from pylectra.engine.init_states import (
    exciter_init as ExciterInit,
    generator_init as GeneratorInit,
    governor_init as GovernorInit,
    pss_init as PSSInit,
)
from pylectra.engine.derivatives import (
    exciter_step as Exciter,
    generator_step as Generator,
    governor_step as Governor,
)
from pylectra.engine.loop import IntegrationResult, _failed_result
from pylectra.io.dyn_loaders import (
    loaddyn as Loaddyn,
    loadevents as Loadevents,
    loadexc as Loadexc,
    loadgen as Loadgen,
    loadgov as Loadgov,
    loadpss as Loadpss,
)
from pylectra.network import machine_currents as MachineCurrents
from pylectra.powerflow.newton import NewtonPowerFlow


@dataclass
class BatchedRunSpec:
    """Per-batch configuration for :class:`BatchedTorchIntegrationLoop`.

    Parameters
    ----------
    batch_size:
        Number of independent samples to simulate in parallel.
    y0_perturbation:
        Optional ``(B, S)`` host-side numpy array added to the shared
        steady-state ``y0`` to seed each sample.  ``None`` runs ``B``
        identical sims (useful for benchmarking only).
    fixed_step:
        RK4 step size (seconds).  Default 1 ms — stable for case39.
    dense_n:
        Per-leg sample-grid size (number of recorded points).
    device_pref:
        ``"auto"``/``"cuda"``/``"cpu"``/``"mps"``.
    torch_dtype:
        ``"float64"`` (default) or ``"float32"``.
    output_chunk:
        How many ``(T, B)`` rows to evaluate per output post-pass.  ``None``
        means a single shot — fine until memory is tight.
    """
    batch_size: int
    y0_perturbation: Optional[np.ndarray] = None
    fixed_step: float = 1e-3
    dense_n: int = 200
    device_pref: str = "auto"
    torch_dtype: str = "float64"
    output_chunk: Optional[int] = None


class BatchedTorchIntegrationLoop:
    """One ``B``-sample GPU pass producing ``B`` :class:`IntegrationResult`."""

    def __init__(self, casefile_pf, casefile_dyn, casefile_ev,
                 spec: BatchedRunSpec,
                 t0: float = -0.02,
                 output: int = 0):
        self.casefile_pf = casefile_pf
        self.casefile_dyn = casefile_dyn
        self.casefile_ev = casefile_ev
        self.spec = spec
        self.t0 = float(t0)
        self.output = int(output)

    # ------------------------------------------------------------------
    def _resolve_device_and_dtype(self):
        from pylectra.hardware import torch_device
        torch = _torch_or_die()
        dt = self.spec.torch_dtype.lower()
        if dt not in {"float32", "float64"}:
            raise ValueError(f"unsupported torch_dtype={dt!r}")
        device_name = torch_device(self.spec.device_pref, dtype=dt)
        if device_name is None:
            raise RuntimeError("torch is not importable")
        device = torch.device(device_name)
        if dt == "float64":
            return device, torch.float64, torch.complex128
        return device, torch.float32, torch.complex64

    # ------------------------------------------------------------------
    def run(self) -> List[IntegrationResult]:
        torch = _torch_or_die()
        from pylectra.solvers.torch_solvers import batched_rk4

        tic = time.time()
        spec = self.spec
        B = int(spec.batch_size)

        if self.output:
            print(f"> [batched-torch] Loading dynamic data, B={B}")
        freq, stepsize, stoptime = Loaddyn(self.casefile_dyn)
        _set_freq(freq)

        Pgen0 = Loadgen(self.casefile_dyn, 0)
        if Pgen0.shape[1] < 10:
            Pgen0 = np.hstack([Pgen0,
                               np.zeros((Pgen0.shape[0], 10 - Pgen0.shape[1]))])
        Pgen0[:, 9] = Pgen0[:, 8]
        Pexc0 = Loadexc(self.casefile_dyn)
        Ppss0 = Loadpss(self.casefile_dyn)
        Pgov0 = Loadgov(self.casefile_dyn)

        if self.casefile_ev not in (None, ""):
            event, buschange, linechange = Loadevents(self.casefile_ev)
        else:
            event = np.empty((0, 2))
            buschange = np.empty((0, 4))
            linechange = np.empty((0, 4))

        genmodel = Pgen0[:, 0].astype(int)
        excmodel = Pgen0[:, 1].astype(int)
        pssmodel = Pgen0[:, 2].astype(int)
        govmodel = Pgen0[:, 3].astype(int)
        if not (np.all(genmodel == 2) and np.all(excmodel == 3)
                and np.all(govmodel == 1) and np.all(pssmodel == 3)):
            raise NotImplementedError(
                "Batched torch engine requires the same model subset as "
                "the single-sample torch engine "
                "(genmodel=2, excmodel=3, govmodel=1, pssmodel=3)."
            )

        # Power flow init (host).
        case = (self.casefile_pf if isinstance(self.casefile_pf, NetworkCase)
                else NetworkCase.load(self.casefile_pf))
        NewtonPowerFlow().solve(case, {"verbose": 0})
        if not case.success:
            return [_failed_result("power flow did not converge",
                                   n_bus=0, n_gen=0,
                                   simulationtime=time.time() - tic)
                    for _ in range(B)]

        baseMVA = case.mpc["baseMVA"]
        bus = case.mpc["bus"]
        gen = case.mpc["gen"]
        branch = case.mpc["branch"]

        ib = idx_bus(); ig = idx_gen(); ibr = idx_brch()
        VM = ib[11]; VA = ib[12]
        GEN_BUS = ig[0]; GEN_STATUS = ig[7]

        U0 = bus[:, VM] * (np.cos(bus[:, VA] * np.pi / 180.0)
                           + 1j * np.sin(bus[:, VA] * np.pi / 180.0))
        on = np.flatnonzero(gen[:, GEN_STATUS] > 0)
        gbus = gen[on, GEN_BUS].astype(int)
        ngen = gbus.size
        nbus = U0.size

        xd_tr = np.zeros(ngen)
        xd_tr[genmodel == 2] = Pgen0[genmodel == 2, 8]

        # Steady-state init (numpy).
        Efd0, Xgen0 = GeneratorInit(Pgen0, U0[gbus], gen, baseMVA, genmodel)
        Id0, Iq0, Pe0 = MachineCurrents(Xgen0, Pgen0, U0[gbus], genmodel)
        Vexc0 = U0[gbus]
        Xexc0, Pexc0 = ExciterInit(Efd0, Xgen0, Pexc0, Vexc0, excmodel)
        Xpss0, Ppss0 = PSSInit(Ppss0, pssmodel)
        Xgov0, Pgov0 = GovernorInit(Pe0, Pgov0, Xgen0[:, 1], govmodel)

        # Sanity steady-state checks (host, identical to scipy engine).
        Vpss0 = np.zeros((ngen, 2))
        Fexc0 = Exciter(Xexc0, Xgen0, Pexc0, Vexc0, Vpss0, excmodel)
        Fgov0 = Governor(Xgov0, Pgov0, Xgen0[:, 1], govmodel)
        Vgen0 = np.column_stack([Id0, Iq0, Pe0])
        Fgen0 = Generator(Xgen0, Xexc0, Xgov0, Pgen0, Vgen0, genmodel)
        if (np.sum(np.abs(Fgen0)) > 1e-6
                or np.sum(np.abs(Fexc0)) > 1e-6
                or np.sum(np.abs(Fgov0)) > 1e-6):
            return [_failed_result("system not in steady state",
                                   nbus, ngen, time.time() - tic)
                    for _ in range(B)]

        layout = StateLayout(ngen=ngen,
                             n_xgen=Xgen0.shape[1],
                             n_xexc=Xexc0.shape[1],
                             n_xgov=Xgov0.shape[1])

        # Resolve device + dtype, build batched solver + RHS.
        device, real_dtype, complex_dtype = self._resolve_device_and_dtype()
        if self.output:
            print(f"> [batched-torch] device={device} dtype={real_dtype}")

        network = BatchedNetworkSolver(
            baseMVA, bus, branch, gbus, xd_tr, U0,
            batch_size=B, device=device,
            real_dtype=real_dtype, complex_dtype=complex_dtype,
        )
        rhs = BatchedDynamicsRHS(
            layout, network, Pgen=Pgen0, Pexc=Pexc0, Pgov=Pgov0,
            device=device, real_dtype=real_dtype, complex_dtype=complex_dtype,
        )

        # Build batched y0 on device.
        y0_np = layout.pack(Xgen0, Xexc0, Xgov0)              # (S,)
        y0_b = np.broadcast_to(y0_np, (B, layout.size)).copy()  # (B, S)
        if spec.y0_perturbation is not None:
            pert = np.asarray(spec.y0_perturbation, dtype=float)
            if pert.shape != (B, layout.size):
                raise ValueError(
                    f"y0_perturbation shape {pert.shape} != ({B}, {layout.size})"
                )
            y0_b = y0_b + pert

        return self._integrate_core(
            layout=layout, network=network, rhs=rhs, y0_b=y0_b,
            freq=freq, stoptime=stoptime,
            event=event, buschange=buschange, linechange=linechange,
            bus=bus, branch=branch,
            nbus=nbus, ngen=ngen, B=B,
            real_dtype=real_dtype, device=device, tic=tic,
        )

    # ------------------------------------------------------------------
    def run_perturbed(self, perturbed_cases: Sequence[NetworkCase]
                      ) -> List[IntegrationResult]:
        """Run B simulations whose initial conditions come from B distinct
        perturbed cases (one per sample, already mutated by scenarios).

        Each ``perturbed_cases[i]`` must be a :class:`NetworkCase` whose
        ``bus`` / ``branch`` arrays already reflect the per-sample
        perturbation (load shift, line outage, …).  This method runs B
        host-side power flows, builds per-sample steady-state ICs, stacks
        them, and drives the heterogeneous batched integrator.

        Returns
        -------
        List[IntegrationResult]
            One result per sample, in the same order as ``perturbed_cases``.
            Samples whose PF or steady-state init failed produce a
            ``_failed_result`` entry; the rest still run together on the
            successful sub-batch.  (Today: any single failure aborts the
            whole batch with B failed results — Phase 5 partial-run.)
        """
        torch = _torch_or_die()
        tic = time.time()
        spec = self.spec
        B = len(perturbed_cases)
        if B != int(spec.batch_size):
            raise ValueError(
                f"len(perturbed_cases)={B} != spec.batch_size={spec.batch_size}"
            )

        if self.output:
            print(f"> [batched-torch] Loading dynamic data, B={B} (perturbed)")
        freq, stepsize, stoptime = Loaddyn(self.casefile_dyn)
        _set_freq(freq)

        Pgen0 = Loadgen(self.casefile_dyn, 0)
        if Pgen0.shape[1] < 10:
            Pgen0 = np.hstack([Pgen0,
                               np.zeros((Pgen0.shape[0], 10 - Pgen0.shape[1]))])
        Pgen0[:, 9] = Pgen0[:, 8]
        Pexc0 = Loadexc(self.casefile_dyn)
        Ppss0 = Loadpss(self.casefile_dyn)
        Pgov0 = Loadgov(self.casefile_dyn)

        if self.casefile_ev not in (None, ""):
            event, buschange, linechange = Loadevents(self.casefile_ev)
        else:
            event = np.empty((0, 2))
            buschange = np.empty((0, 4))
            linechange = np.empty((0, 4))

        genmodel = Pgen0[:, 0].astype(int)
        excmodel = Pgen0[:, 1].astype(int)
        pssmodel = Pgen0[:, 2].astype(int)
        govmodel = Pgen0[:, 3].astype(int)
        if not (np.all(genmodel == 2) and np.all(excmodel == 3)
                and np.all(govmodel == 1) and np.all(pssmodel == 3)):
            raise NotImplementedError(
                "Batched torch engine requires genmodel=2, excmodel=3, "
                "govmodel=1, pssmodel=3 only."
            )

        # ---- Per-sample host-side PF + steady-state init ----
        ig = idx_gen()
        ib = idx_bus()
        VM = ib[11]; VA = ib[12]
        GEN_BUS = ig[0]; GEN_STATUS = ig[7]

        bus_per: List[np.ndarray] = []
        branch_per: List[np.ndarray] = []
        U0_per = []                         # list of (nb,) complex
        y0_rows = []                        # list of (S,) flat
        baseMVA = None
        gbus_ref = None
        layout = None
        Pexc_eff = Pexc0
        Pgov_eff = Pgov0
        Vpss0 = None

        for i, c in enumerate(perturbed_cases):
            try:
                NewtonPowerFlow().solve(c, {"verbose": 0})
            except Exception:
                c.success = False
            if not c.success:
                return [_failed_result(
                    f"power flow did not converge (sample {i})",
                    n_bus=0, n_gen=0,
                    simulationtime=time.time() - tic) for _ in range(B)]

            if baseMVA is None:
                baseMVA = c.mpc["baseMVA"]
            bus_i = c.mpc["bus"].copy()
            branch_i = c.mpc["branch"].copy()
            gen_i = c.mpc["gen"]
            U0_i = bus_i[:, VM] * (np.cos(bus_i[:, VA] * np.pi / 180.0)
                                   + 1j * np.sin(bus_i[:, VA] * np.pi / 180.0))
            on_i = np.flatnonzero(gen_i[:, GEN_STATUS] > 0)
            gbus_i = gen_i[on_i, GEN_BUS].astype(int)
            if gbus_ref is None:
                gbus_ref = gbus_i
            elif gbus_i.shape != gbus_ref.shape or not np.array_equal(gbus_i, gbus_ref):
                raise NotImplementedError(
                    "Per-sample generator-bus topology must be identical; "
                    f"sample {i} has different gbus."
                )

            ngen_i = gbus_i.size
            Efd0_i, Xgen0_i = GeneratorInit(Pgen0, U0_i[gbus_i], gen_i,
                                            baseMVA, genmodel)
            Id0_i, Iq0_i, Pe0_i = MachineCurrents(Xgen0_i, Pgen0,
                                                  U0_i[gbus_i], genmodel)
            Vexc0_i = U0_i[gbus_i]
            Xexc0_i, Pexc_eff = ExciterInit(Efd0_i, Xgen0_i, Pexc0,
                                            Vexc0_i, excmodel)
            _Xpss_i, _ = PSSInit(Ppss0, pssmodel)
            Xgov0_i, Pgov_eff = GovernorInit(Pe0_i, Pgov0, Xgen0_i[:, 1],
                                             govmodel)

            if layout is None:
                layout = StateLayout(ngen=ngen_i,
                                     n_xgen=Xgen0_i.shape[1],
                                     n_xexc=Xexc0_i.shape[1],
                                     n_xgov=Xgov0_i.shape[1])

            # Steady-state sanity check (cheap).
            Vpss0 = np.zeros((ngen_i, 2))
            Vgen0_i = np.column_stack([Id0_i, Iq0_i, Pe0_i])
            F1 = Generator(Xgen0_i, Xexc0_i, Xgov0_i, Pgen0, Vgen0_i, genmodel)
            F2 = Exciter(Xexc0_i, Xgen0_i, Pexc_eff, Vexc0_i, Vpss0, excmodel)
            F3 = Governor(Xgov0_i, Pgov_eff, Xgen0_i[:, 1], govmodel)
            if (np.sum(np.abs(F1)) > 1e-6
                    or np.sum(np.abs(F2)) > 1e-6
                    or np.sum(np.abs(F3)) > 1e-6):
                return [_failed_result(
                    f"sample {i} not in steady state",
                    bus_i.shape[0], ngen_i,
                    simulationtime=time.time() - tic) for _ in range(B)]

            bus_per.append(bus_i)
            branch_per.append(branch_i)
            U0_per.append(U0_i)
            y0_rows.append(layout.pack(Xgen0_i, Xexc0_i, Xgov0_i))

        nbus = bus_per[0].shape[0]
        ngen = gbus_ref.size
        U0_b = np.stack(U0_per, axis=0)               # (B, nb)
        y0_b = np.stack(y0_rows, axis=0)              # (B, S)

        xd_tr = np.zeros(ngen)
        xd_tr[genmodel == 2] = Pgen0[genmodel == 2, 8]

        device, real_dtype, complex_dtype = self._resolve_device_and_dtype()
        if self.output:
            print(f"> [batched-torch] device={device} dtype={real_dtype}")

        network = BatchedNetworkSolver(
            baseMVA, bus_per[0], branch_per[0], gbus_ref, xd_tr, U0_per[0],
            batch_size=B, device=device,
            real_dtype=real_dtype, complex_dtype=complex_dtype,
            bus_per_sample=bus_per,
            branch_per_sample=branch_per,
            U_init_per_sample=U0_b,
        )
        rhs = BatchedDynamicsRHS(
            layout, network, Pgen=Pgen0, Pexc=Pexc_eff, Pgov=Pgov_eff,
            device=device, real_dtype=real_dtype, complex_dtype=complex_dtype,
        )

        return self._integrate_core(
            layout=layout, network=network, rhs=rhs, y0_b=y0_b,
            freq=freq, stoptime=stoptime,
            event=event, buschange=buschange, linechange=linechange,
            bus=bus_per[0], branch=branch_per[0],
            nbus=nbus, ngen=ngen, B=B,
            real_dtype=real_dtype, device=device, tic=tic,
        )

    # ------------------------------------------------------------------
    def _integrate_core(self, *, layout, network, rhs, y0_b,
                        freq, stoptime, event, buschange, linechange,
                        bus, branch, nbus, ngen, B,
                        real_dtype, device, tic) -> List[IntegrationResult]:
        """Run the leg-by-leg batched RK4 driver, apply events, return B
        :class:`IntegrationResult`.  Shared by :meth:`run` (homogeneous IC)
        and :meth:`run_perturbed` (heterogeneous IC).

        ``bus`` / ``branch`` are the host-side arrays whose mutation by
        events triggers a network rebuild — for heterogeneous mode the
        caller must point ``bus``/``branch`` at the per-sample arrays so
        :meth:`BatchedNetworkSolver.rebuild` picks them up.  Today only
        homogeneous events are supported (same fault for all samples); the
        heterogeneous-event path is a Phase 5 concern.
        """
        torch = _torch_or_die()
        from pylectra.solvers.torch_solvers import batched_rk4

        spec = self.spec
        y = torch.tensor(y0_b, dtype=real_dtype, device=device)

        n_events = event.shape[0] if event.size else 0
        event_times = event[:, 0].astype(float) if n_events else np.empty(0)
        leg_bounds = [self.t0]
        for et_ in event_times:
            if et_ > self.t0 and et_ > leg_bounds[-1] + 1e-15:
                leg_bounds.append(float(et_))
        if leg_bounds[-1] < stoptime:
            leg_bounds.append(float(stoptime))
        else:
            leg_bounds[-1] = float(stoptime)

        traj_chunks: List[Any] = []
        time_chunks: List[np.ndarray] = []
        traj_chunks.append(y.unsqueeze(0))
        time_chunks.append(np.array([self.t0]))

        if self.output:
            print("> [batched-torch] Running dynamic simulation...")

        ev = 0
        for li in range(len(leg_bounds) - 1):
            t_start = leg_bounds[li]
            t_end = leg_bounds[li + 1]
            if t_end <= t_start:
                continue
            n_eval = max(2, int(spec.dense_n))
            t_eval_np = np.linspace(t_start, t_end, n_eval)
            t_eval = torch.tensor(t_eval_np, dtype=real_dtype, device=device)
            try:
                traj = batched_rk4(rhs, y, t_eval, max_step=spec.fixed_step)
            except Exception as e:  # pragma: no cover
                return [_failed_result(f"batched RK4 failed: {e}",
                                       nbus, ngen, time.time() - tic)
                        for _ in range(B)]
            # Drop the duplicated first row (it equals the previous endpoint
            # we already saved); keep (n_eval-1, B, S).
            traj_chunks.append(traj[1:])
            time_chunks.append(t_eval_np[1:])
            y = traj[-1]

            # Apply events at t_end (homogeneous across batch).
            applied = False
            while ev < n_events and abs(event_times[ev] - t_end) < 1e-12:
                etype = int(event[ev, 1])
                if etype == 1:
                    r = int(buschange[ev, 1]) - 1
                    c = int(buschange[ev, 2]) - 1
                    val = buschange[ev, 3]
                    if network._het:
                        for i in range(B):
                            network.bus_per_sample[i][r, c] = val
                    else:
                        bus[r, c] = val
                elif etype == 2:
                    r = int(linechange[ev, 1]) - 1
                    c = int(linechange[ev, 2]) - 1
                    val = linechange[ev, 3]
                    if network._het:
                        for i in range(B):
                            network.branch_per_sample[i][r, c] = val
                    else:
                        branch[r, c] = val
                ev += 1
                applied = True
            if applied:
                network.rebuild()
                # "Two rows for one t" — record post-event snapshot.
                traj_chunks.append(y.unsqueeze(0))
                time_chunks.append(np.array([t_end]))

        # Concatenate trajectory: (T, B, S) on device.
        traj_dev = torch.cat(traj_chunks, dim=0)
        Time = np.concatenate(time_chunks)
        T_total = traj_dev.shape[0]

        # ---- One-shot output post-pass ----
        # We need (T*B, S) so the network solver (built for B) handles each
        # row.  Slice into groups of B rows along the time axis to reuse the
        # existing solver without resizing.
        chunk = spec.output_chunk if spec.output_chunk is not None else T_total
        chunk = max(1, int(chunk))

        Voltages = np.empty((T_total, B, nbus), dtype=complex)
        Tes = np.empty((T_total, B, ngen), dtype=float)

        # Process T-axis in groups so we always feed the solver a (B, S)
        # slice (network was built with batch_size=B).
        for k in range(T_total):
            U_k, Pe_k = rhs.compute_outputs(traj_dev[k])
            Voltages[k] = U_k.detach().cpu().numpy()
            Tes[k] = Pe_k.detach().cpu().numpy()

        traj_np = traj_dev.detach().cpu().numpy()  # (T, B, S)

        # Fan out into B IntegrationResult.
        results: List[IntegrationResult] = []
        Stepsize = np.full(T_total, spec.fixed_step)
        Errest = np.zeros(T_total)
        # Slice (T, B, S) into per-sample (T, S), then unpack via numpy layout.
        for b in range(B):
            yb = traj_np[:, b, :]                     # (T, S)
            Xgen_b = yb[:, :layout._xg_end].reshape(T_total, ngen, layout.n_xgen)
            Xexc_b = yb[:, layout._xg_end:layout._xe_end].reshape(
                T_total, ngen, layout.n_xexc)
            Xgov_b = yb[:, layout._xe_end:].reshape(T_total, ngen, layout.n_xgov)
            results.append(IntegrationResult(
                Time=Time.copy(),
                Voltages=Voltages[:, b, :].copy(),
                Efds=Xexc_b[:, :, 0].copy(),
                Angles=(Xgen_b[:, :, 0] * 180.0 / np.pi).copy(),
                Speeds=(Xgen_b[:, :, 1] / (2.0 * np.pi * freq)).copy(),
                Eq_trs=Xgen_b[:, :, 2].copy(),
                Ed_trs=Xgen_b[:, :, 3].copy(),
                Tes=Tes[:, b, :].copy(),
                TM=Xgov_b[:, :, 0].copy(),
                Vss=np.zeros((T_total, ngen)),
                Stepsize=Stepsize.copy(),
                Errest=Errest.copy(),
                simulationtime=time.time() - tic,
                success=True,
            ))

        if self.output:
            print(f"> [batched-torch] Done in {time.time() - tic:.2f}s, "
                  f"B={B}, T={T_total}")
        return results


__all__ = [
    "BatchedNetworkSolver",
    "BatchedDynamicsRHS",
    "BatchedRunSpec",
    "BatchedTorchIntegrationLoop",
]
