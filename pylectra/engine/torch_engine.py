"""Torch (GPU/CPU) ODE engine for power-system dynamics.

This is the Phase 2c counterpart of :mod:`pylectra.engine.rhs` + :mod:`pylectra.engine.loop`.
It mirrors the math used by the scipy native engine, but every per-leg compute
runs on a torch device (cuda → mps → cpu, see :func:`pylectra.hardware.torch_device`)
through :mod:`torchdiffeq.odeint`.

Restrictions
------------
This engine implements **only** the subset of model types covered by the
scipy native engine, namely:

* generator type 2  (4th-order classical model)
* exciter   type 3  (the case39dyn AVR)
* governor  type 1  (constant mechanical power)
* PSS       type 3  (no PSS)

Other types raise :class:`NotImplementedError`.

Dtype / device routing
----------------------
The default dtype is ``float64`` (with complex128 for the network solve) so
results match scipy bit-for-bit close.  ``float64`` is only supported on
``cuda`` / ``cpu`` — Apple MPS is double-precision-only after a
``torch_dtype: float32`` override (the auto-router transparently downgrades
the device choice in that case).

Snapshot semantics
------------------
``torchdiffeq.odeint`` returns the trajectory at user-supplied ``t_eval``
points only — there is no "save every accepted step" hook.  We therefore
build a dense ``t_eval`` grid per leg (controlled by ``solver_options``
``["dense_n"]``, default 200 points per leg) and use that as the recorded
trajectory.  ``Stepsize`` reports the spacing of those samples, *not* the
adaptive step taken by the underlying integrator.  See README §Phase 2c.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import numpy as np

from pylectra.core.idx import idx_bus, idx_brch, idx_gen
from pylectra.core.case import NetworkCase
from pylectra.powerflow.newton import NewtonPowerFlow
from pylectra.io.dyn_loaders import (
    loaddyn as Loaddyn,
    loadgen as Loadgen,
    loadexc as Loadexc,
    loadpss as Loadpss,
    loadgov as Loadgov,
    loadevents as Loadevents,
)
from pylectra.network.ybus import make_ybus as makeYbus

from pylectra.network import machine_currents as MachineCurrents
from pylectra.core import freq as _pds_freq
from pylectra.core.freq import set_freq as _set_freq
from pylectra.engine.init_states import (
    generator_init as GeneratorInit,
    exciter_init as ExciterInit,
    governor_init as GovernorInit,
    pss_init as PSSInit,
)
from pylectra.engine.derivatives import (
    generator_step as Generator,
    exciter_step as Exciter,
    governor_step as Governor,
)

from .loop import IntegrationResult, _failed_result
from .state import StateLayout


# A torch solver factory is a callable
#     factory(rhs, y0, t_eval, **opts) -> torch.Tensor of shape (len(t_eval), state_dim)
TorchSolverFactory = Callable[..., Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _torch_or_die():
    try:
        import torch  # noqa: F401
        return __import__("torch")
    except Exception as e:  # pragma: no cover — clearer error in CLI path
        raise RuntimeError(
            "Torch backend selected but `torch` could not be imported. "
            "Install with `pip install torch torchdiffeq`."
        ) from e


def _odeint_or_die():
    try:
        from torchdiffeq import odeint  # type: ignore
        return odeint
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Torch solver selected but `torchdiffeq` could not be imported. "
            "Install with `pip install torchdiffeq`."
        ) from e


def _integrate_with_optional_chunking(
    solver_factory, rhs, y0, t_eval, *, chunk_seconds, solver_options,
):
    """Run ``solver_factory(rhs, y0, t_eval, **opts)`` either in one shot
    or sliced into time-windows of ``chunk_seconds`` length.

    Both modes are mathematically equivalent (same ODE, same solver, same
    sub-tolerances); the windowed mode trades a small amount of overhead
    for an O(window/leg) reduction in odeint's internal RK buffer
    footprint and lets us drain CUDA cache between windows.

    Returns a tensor with shape ``(len(t_eval), state_dim)`` matching the
    single-shot call so callers don't branch on the option.
    """
    torch = _torch_or_die()
    if chunk_seconds is None or chunk_seconds <= 0.0:
        with torch.no_grad():
            return solver_factory(rhs, y0, t_eval, **solver_options)

    # Build window boundaries in *index* space so the per-window t_eval
    # always starts exactly at the previous window's end (state hand-off
    # without re-evaluation overhead).
    t_np = t_eval.detach().cpu().numpy()
    t0 = float(t_np[0])
    t1 = float(t_np[-1])
    if (t1 - t0) <= chunk_seconds:
        with torch.no_grad():
            return solver_factory(rhs, y0, t_eval, **solver_options)

    boundaries = []
    cur = t0
    while cur < t1:
        nxt = min(t1, cur + chunk_seconds)
        boundaries.append((cur, nxt))
        cur = nxt

    out_pieces = []
    y = y0
    last_idx = 0  # how many points of t_eval we've consumed
    is_cuda = (y.device.type == "cuda")
    for w_start, w_end in boundaries:
        # Find the t_eval indices that lie inside [w_start, w_end].
        import numpy as _np
        mask = (t_np >= w_start - 1e-12) & (t_np <= w_end + 1e-12)
        idx = _np.flatnonzero(mask)
        if idx.size == 0:
            continue
        # Always include the previous window's end as the new start so
        # the solver sees a state-consistent grid.
        if idx[0] > last_idx:
            idx = _np.concatenate(([last_idx], idx))
        sub_t = t_eval[idx[0]:idx[-1] + 1]
        with torch.no_grad():
            sub_traj = solver_factory(rhs, y, sub_t, **solver_options)
        # Detach + (optionally) free cache; keep on the same device for
        # cheap concatenation at the end.
        sub_traj = sub_traj.detach()
        if out_pieces:
            # Drop the duplicated first row that matches the previous
            # window's last row.
            out_pieces.append(sub_traj[1:])
        else:
            out_pieces.append(sub_traj)
        y = sub_traj[-1]
        last_idx = idx[-1]
        if is_cuda:  # pragma: no cover - only meaningful on cuda
            torch.cuda.empty_cache()

    return torch.cat(out_pieces, dim=0)


def _build_dense_Y_numpy(baseMVA, bus, branch, xd_tr, gbus, P, Q, U0):
    """Numpy version of the augmented Y-bus, returned as a *dense* matrix.

    Mirrors :func:`Auxiliary.AugYbus.AugYbus` exactly (same load + generator
    augmentation, same shunt term inside ``makeYbus``) but skips the LU
    factorisation — torch will handle the linear solve on the dense tensor.
    """
    Ybus, _, _ = makeYbus(baseMVA, bus, branch)
    yload = (P - 1j * Q) / (np.abs(U0) ** 2)
    nb = Ybus.shape[0]
    ygen = np.zeros(nb, dtype=complex)
    ygen[gbus] = 1.0 / (1j * xd_tr)
    Y = Ybus.toarray() + np.diag(ygen + yload)
    return Y.astype(np.complex128)


# ---------------------------------------------------------------------------
# Network solver (dense torch)
# ---------------------------------------------------------------------------

class _TorchNetworkSolver:
    """Torch counterpart to :class:`pylectra.engine.rhs.NetworkSolver`.

    Holds the dense complex Y-bus tensor on the chosen device and provides
    :meth:`solve_for_U` that scatters generator currents and solves
    ``Y * U = I``.
    """

    def __init__(self, baseMVA, bus, branch, gbus, xd_tr, U_init,
                 *, device, real_dtype, complex_dtype):
        torch = _torch_or_die()
        self.torch = torch
        self.baseMVA = float(baseMVA)
        self.bus = bus
        self.branch = branch
        self.gbus_np = np.asarray(gbus, dtype=int)
        self.xd_tr_np = np.asarray(xd_tr, dtype=float)
        self.U_init = np.asarray(U_init, dtype=complex)
        self.device = device
        self.real_dtype = real_dtype
        self.complex_dtype = complex_dtype
        self.gbus = torch.tensor(self.gbus_np, dtype=torch.long, device=device)
        self.nb = int(bus.shape[0])
        self._Y: Optional[Any] = None
        self._lu: Optional[Any] = None
        self._lu_pivots: Optional[Any] = None
        self.rebuild()

    def rebuild(self) -> None:
        torch = self.torch
        ib = idx_bus()
        PD, QD = ib[6], ib[7]
        Pl = self.bus[:, PD] / self.baseMVA
        Ql = self.bus[:, QD] / self.baseMVA
        Y_np = _build_dense_Y_numpy(self.baseMVA, self.bus, self.branch,
                                    self.xd_tr_np, self.gbus_np, Pl, Ql,
                                    self.U_init)
        Y = torch.tensor(Y_np, dtype=self.complex_dtype, device=self.device)
        self._Y = Y
        # Pre-factor once per leg; reuse for every RHS evaluation.
        self._lu, self._lu_pivots = torch.linalg.lu_factor(Y)

    def solve_for_U(self, Xgen, Pgen_xd_tr_torch):
        """Solve ``Y * U = scatter(Igen)`` for U.

        Parameters
        ----------
        Xgen:
            Generator state tensor, shape ``(ngen, n_xgen)`` real.
        Pgen_xd_tr_torch:
            ``xd_tr`` (per-generator) as a real tensor on the same device.
        """
        torch = self.torch
        delta = Xgen[:, 0]
        Eq = Xgen[:, 2]
        Ed = Xgen[:, 3]
        # Igen = (Eq + j Ed) * exp(j delta) / (j xd_tr)
        # Build complex pieces explicitly to keep autograd disabled cleanly.
        Eqc = Eq.to(self.complex_dtype)
        Edc = Ed.to(self.complex_dtype)
        deltac = delta.to(self.complex_dtype)
        xdc = Pgen_xd_tr_torch.to(self.complex_dtype)
        i = torch.tensor(1j, dtype=self.complex_dtype, device=self.device)
        Igen = (Eqc + i * Edc) * torch.exp(i * deltac) / (i * xdc)

        Ig = torch.zeros(self.nb, dtype=self.complex_dtype, device=self.device)
        Ig.index_add_(0, self.gbus, Igen)

        # Solve via cached LU factorization.
        U = torch.linalg.lu_solve(self._lu, self._lu_pivots, Ig.unsqueeze(-1))
        return U.squeeze(-1)


# ---------------------------------------------------------------------------
# RHS callable
# ---------------------------------------------------------------------------

class _TorchDynamicsRHS:
    """``f(t, y) -> dy/dt`` running entirely on a torch device.

    Limited to genmodel=2, excmodel=3, govmodel=1, pssmodel=3.
    """

    def __init__(self, layout, network, *, Pgen, Pexc, Pgov,
                 device, real_dtype, complex_dtype):
        torch = _torch_or_die()
        self.torch = torch
        self.layout = layout
        self.network = network
        self.device = device
        self.real_dtype = real_dtype
        self.complex_dtype = complex_dtype

        # Pre-extract per-generator parameter tensors (constant during a leg).
        Pgen = np.asarray(Pgen, dtype=float)
        Pexc = np.asarray(Pexc, dtype=float)
        Pgov = np.asarray(Pgov, dtype=float)

        def _t(arr):
            return torch.tensor(np.asarray(arr, dtype=float),
                                dtype=real_dtype, device=device)

        # Generator type 2 parameters (matches Models/Generators/Generator.py)
        self.H      = _t(Pgen[:, 6])
        self.xd_tr  = _t(Pgen[:, 8])
        self.xq_tr  = _t(Pgen[:, 9])
        self.xd     = _t(Pgen[:, 10])
        self.xq     = _t(Pgen[:, 11])
        self.Td0_tr = _t(Pgen[:, 12])
        self.Tq0_tr = _t(Pgen[:, 13])
        # Damping is hard-coded to 0 in the legacy Generator() for type 2.
        self.D = torch.zeros_like(self.H)

        # Exciter type 3 parameters (Models/Exciters/Exciter.py)
        self.Tv = _t(Pexc[:, 1])
        self.mu = _t(Pexc[:, 2])
        self.k  = _t(Pexc[:, 3])
        self.L  = _t(Pexc[:, 6])

        # Frequency / omegas constant.
        self.freq = float(_pds_freq.freq)
        self.omegas = torch.tensor(2.0 * np.pi * self.freq,
                                   dtype=real_dtype, device=device)
        self.pi = torch.tensor(np.pi, dtype=real_dtype, device=device)

        # Cache for the loop snapshot writer (numpy buffers).
        self._last_U_np: Optional[np.ndarray] = None
        self._last_Pe_np: Optional[np.ndarray] = None
        self._last_t: float = -np.inf

    # ------------------------------------------------------------------

    def __call__(self, t, y):
        """Compute dy/dt at (t, y).  ``t`` and ``y`` are torch tensors."""
        torch = self.torch
        Xgen, Xexc, Xgov = self.layout.unpack_torch(y)

        # Network solve
        U = self.network.solve_for_U(Xgen, self.xd_tr)
        Vexc = U.index_select(0, self.network.gbus)

        # Machine currents (mirrors Auxiliary/MachineCurrents.py type-2 block)
        delta = Xgen[:, 0]
        Eq = Xgen[:, 2]
        Ed = Xgen[:, 3]
        theta = torch.angle(Vexc)
        absU = torch.abs(Vexc)
        vd = -absU * torch.sin(delta - theta)
        vq =  absU * torch.cos(delta - theta)
        Id = (vq - Eq) / self.xd_tr
        Iq = -(vd - Ed) / self.xq_tr
        Pe = (Eq * Iq + Ed * Id
              + (self.xd_tr - self.xq_tr) * Id * Iq)

        # Generator (type 2) derivatives
        omega = Xgen[:, 1]
        Efd = Xexc[:, 0]
        Pm = Xgov[:, 0]
        ddelta = omega - self.omegas
        domega = (self.pi * self.freq / self.H) * (
            -self.D * (omega - self.omegas) / self.omegas + Pm - Pe
        )
        dEq = (1.0 / self.Td0_tr) * (Efd - Eq + (self.xd - self.xd_tr) * Id)
        dEd = (1.0 / self.Tq0_tr) * (-Ed - (self.xq - self.xq_tr) * Iq)

        # Exciter (type 3) derivative
        # V, theta already computed for the gen buses (Vexc).
        dEfd = (-Efd - self.mu * self.k * absU * torch.cos(delta - theta) + self.L) / self.Tv

        # Governor (type 1): all derivatives zero (constant mechanical power).
        dXgov = torch.zeros_like(Xgov)

        # Pack
        dXgen = torch.stack([ddelta, domega, dEq, dEd], dim=1)
        dXexc = dEfd.unsqueeze(1)
        dy = self.layout.pack_torch(dXgen, dXexc, dXgov)

        # Cache snapshot data on host (numpy) for the loop writer.
        try:
            self._last_U_np = U.detach().cpu().numpy().astype(complex)
            self._last_Pe_np = Pe.detach().cpu().numpy().astype(float)
            self._last_t = float(t.detach().cpu().item() if hasattr(t, "detach") else t)
        except Exception:
            pass

        return dy


# ---------------------------------------------------------------------------
# Layout extension: torch pack/unpack on a flat tensor
# ---------------------------------------------------------------------------

def _attach_torch_layout(layout: StateLayout) -> None:
    """Monkey-patch torch helpers onto a StateLayout instance."""
    if hasattr(layout, "unpack_torch"):
        return

    def unpack_torch(self, y):
        Xgen = y[:self._xg_end].view(self.ngen, self.n_xgen)
        Xexc = y[self._xg_end:self._xe_end].view(self.ngen, self.n_xexc)
        Xgov = y[self._xe_end:].view(self.ngen, self.n_xgov)
        return Xgen, Xexc, Xgov

    def pack_torch(self, Xgen, Xexc, Xgov):
        torch = _torch_or_die()
        return torch.cat([Xgen.reshape(-1), Xexc.reshape(-1), Xgov.reshape(-1)])

    layout.unpack_torch = unpack_torch.__get__(layout, StateLayout)
    layout.pack_torch = pack_torch.__get__(layout, StateLayout)


# ---------------------------------------------------------------------------
# Integration loop
# ---------------------------------------------------------------------------

class TorchIntegrationLoop:
    """Torch / torchdiffeq driver mirroring :class:`IntegrationLoop`.

    Returns the same :class:`IntegrationResult` shape so
    :class:`pylectra.runners.single.SingleRunner` can consume it transparently.

    Parameters
    ----------
    casefile_pf, casefile_dyn, casefile_ev:
        Same as :class:`IntegrationLoop`.
    solver_factory:
        Callable ``f(rhs, y0, t_eval, **opts) -> trajectory`` (see
        :mod:`pylectra.solvers.torch_solvers`).
    solver_options:
        Forwarded to ``solver_factory``.  Recognised top-level keys
        (consumed here, not forwarded):

        * ``device``         — ``"auto"`` / ``"cpu"`` / ``"cuda"`` / ``"mps"``.
        * ``torch_dtype``    — ``"float64"`` (default) or ``"float32"``.
        * ``dense_n``        — sample-grid size per leg (default 200).
    output:
        Verbosity ``0/1/2``.
    t0:
        Pre-event start (default ``-0.02`` matching scipy native engine).
    """

    def __init__(self,
                 casefile_pf,
                 casefile_dyn,
                 casefile_ev,
                 solver_factory: TorchSolverFactory,
                 solver_options: Optional[Dict[str, Any]] = None,
                 t0: float = -0.02,
                 output: int = 0):
        self.casefile_pf = casefile_pf
        self.casefile_dyn = casefile_dyn
        self.casefile_ev = casefile_ev
        self.solver_factory = solver_factory
        opts = dict(solver_options or {})
        # Pull our own keys out before forwarding.
        self._device_pref = str(opts.pop("device", "auto"))
        self._dtype_str = str(opts.pop("torch_dtype", "float64")).lower()
        self._dense_n = int(opts.pop("dense_n", 200))
        # Time-window chunking inside one leg: split a long ``t_eval`` into
        # sub-windows so the underlying ``odeint`` never holds the whole
        # leg's RK buffer at once.  ``None`` (default) preserves the
        # historical single-call behaviour.  Typical OOM-relief values:
        # 0.2–1.0 (seconds).  See README "GPU acceleration".
        cs = opts.pop("chunk_seconds", None)
        self._chunk_seconds: Optional[float] = float(cs) if cs is not None else None
        self.solver_options = opts
        self.t0 = float(t0)
        self.output = int(output)

    # ------------------------------------------------------------------

    def _resolve_device_and_dtype(self):
        from pylectra.hardware import torch_device

        torch = _torch_or_die()
        dtype_str = self._dtype_str
        if dtype_str not in {"float32", "float64"}:
            raise ValueError(
                f"unsupported torch_dtype={dtype_str!r}; want float32 or float64"
            )
        device_name = torch_device(self._device_pref, dtype=dtype_str)
        if device_name is None:
            raise RuntimeError("torch is not importable; cannot use torch engine")
        device = torch.device(device_name)
        if dtype_str == "float64":
            real_dtype = torch.float64
            complex_dtype = torch.complex128
        else:
            real_dtype = torch.float32
            complex_dtype = torch.complex64
        return device, real_dtype, complex_dtype

    # ------------------------------------------------------------------

    def run(self) -> IntegrationResult:
        torch = _torch_or_die()
        odeint = _odeint_or_die()

        tic = time.time()

        # ---------------- Load data ----------------
        if self.output:
            print('> [torch] Loading dynamic simulation data...')
        freq, stepsize, stoptime = Loaddyn(self.casefile_dyn)
        _set_freq(freq)

        Pgen0 = Loadgen(self.casefile_dyn, 0)
        if Pgen0.shape[1] < 10:
            Pgen0 = np.hstack([Pgen0, np.zeros((Pgen0.shape[0], 10 - Pgen0.shape[1]))])
        Pgen0[:, 9] = Pgen0[:, 8]

        Pexc0 = Loadexc(self.casefile_dyn)
        Ppss0 = Loadpss(self.casefile_dyn)
        Pgov0 = Loadgov(self.casefile_dyn)

        if self.casefile_ev is not None and self.casefile_ev != '':
            event, buschange, linechange = Loadevents(self.casefile_ev)
        else:
            event = np.empty((0, 2))
            buschange = np.empty((0, 4))
            linechange = np.empty((0, 4))

        genmodel = Pgen0[:, 0].astype(int)
        excmodel = Pgen0[:, 1].astype(int)
        pssmodel = Pgen0[:, 2].astype(int)
        govmodel = Pgen0[:, 3].astype(int)

        # Strict subset check — friendlier error than a downstream tensor crash.
        if not np.all(genmodel == 2):
            raise NotImplementedError(
                "Torch engine supports generator type 2 only; got "
                f"{np.unique(genmodel).tolist()}"
            )
        if not np.all(excmodel == 3):
            raise NotImplementedError(
                "Torch engine supports exciter type 3 only; got "
                f"{np.unique(excmodel).tolist()}"
            )
        if not np.all(govmodel == 1):
            raise NotImplementedError(
                "Torch engine supports governor type 1 only; got "
                f"{np.unique(govmodel).tolist()}"
            )
        if not np.all(pssmodel == 3):
            raise NotImplementedError(
                "Torch engine supports PSS type 3 (no PSS) only; got "
                f"{np.unique(pssmodel).tolist()}"
            )

        # ---------------- Power flow ----------------
        case = (self.casefile_pf if isinstance(self.casefile_pf, NetworkCase)
                else NetworkCase.load(self.casefile_pf))
        NewtonPowerFlow().solve(case, {"verbose": 0})
        success = case.success
        if not success:
            return _failed_result('power flow did not converge',
                                  n_bus=0, n_gen=0,
                                  simulationtime=time.time() - tic)
        if self.output:
            print('> [torch] Power flow converged')

        baseMVA = case.mpc["baseMVA"]
        bus = case.mpc["bus"]
        gen = case.mpc["gen"]
        branch = case.mpc["branch"]

        ib = idx_bus(); ig = idx_gen(); ibr = idx_brch()
        BUS_I = ib[4]; VM = ib[11]; VA = ib[12]
        F_BUS = ibr[0]; T_BUS = ibr[1]
        GEN_BUS = ig[0]; GEN_STATUS = ig[7]
        # NewtonPowerFlow.solve already produces 0-based numbering.

        U0 = bus[:, VM] * (np.cos(bus[:, VA] * np.pi / 180.0)
                           + 1j * np.sin(bus[:, VA] * np.pi / 180.0))
        U00 = U0.copy()

        on = np.flatnonzero(gen[:, GEN_STATUS] > 0)
        gbus = gen[on, GEN_BUS].astype(int)
        ngen = gbus.size
        nbus = U0.size

        if self.output:
            print('> [torch] Constructing augmented admittance matrix...')

        xd_tr = np.zeros(ngen)
        xd_tr[genmodel == 2] = Pgen0[genmodel == 2, 8]

        # Resolve device + dtype.
        device, real_dtype, complex_dtype = self._resolve_device_and_dtype()
        if self.output:
            print(f'> [torch] device={device}, dtype={real_dtype}')

        network = _TorchNetworkSolver(
            baseMVA, bus, branch, gbus, xd_tr, U00,
            device=device, real_dtype=real_dtype, complex_dtype=complex_dtype,
        )

        # ---------------- Initial state (numpy, then upload) ----------------
        if self.output:
            print('> [torch] Calculating initial state...')
        Efd0, Xgen0 = GeneratorInit(Pgen0, U0[gbus], gen, baseMVA, genmodel)
        omega0 = Xgen0[:, 1]
        Id0, Iq0, Pe0 = MachineCurrents(Xgen0, Pgen0, U0[gbus], genmodel)
        Vgen0 = np.column_stack([Id0, Iq0, Pe0])

        Vexc0 = U0[gbus]
        Xexc0, Pexc0 = ExciterInit(Efd0, Xgen0, Pexc0, Vexc0, excmodel)
        Xpss0, Ppss0 = PSSInit(Ppss0, pssmodel)
        Vpss0 = np.zeros((ngen, 2))
        Pm0 = Pe0
        Xgov0, Pgov0 = GovernorInit(Pm0, Pgov0, omega0, govmodel)
        Vgov0 = omega0

        # Steady-state checks (same as the scipy engine).
        Fexc0 = Exciter(Xexc0, Xgen0, Pexc0, Vexc0, Vpss0, excmodel)
        Fgov0 = Governor(Xgov0, Pgov0, Vgov0, govmodel)
        Fgen0 = Generator(Xgen0, Xexc0, Xgov0, Pgen0, Vgen0, genmodel)
        if np.sum(np.abs(Fgen0)) > 1e-6:
            return _failed_result('generator not in steady state',
                                  nbus, ngen, time.time() - tic)
        if np.sum(np.abs(Fexc0)) > 1e-6:
            return _failed_result('exciter not in steady state',
                                  nbus, ngen, time.time() - tic)
        if np.sum(np.abs(Fgov0)) > 1e-6:
            return _failed_result('governor not in steady state',
                                  nbus, ngen, time.time() - tic)
        if self.output:
            print('> [torch] System in steady-state')

        # ---------------- Set up RHS + state ----------------
        layout = StateLayout(ngen=ngen,
                             n_xgen=Xgen0.shape[1],
                             n_xexc=Xexc0.shape[1],
                             n_xgov=Xgov0.shape[1])
        _attach_torch_layout(layout)

        rhs = _TorchDynamicsRHS(
            layout, network,
            Pgen=Pgen0, Pexc=Pexc0, Pgov=Pgov0,
            device=device, real_dtype=real_dtype, complex_dtype=complex_dtype,
        )

        y0_np = layout.pack(Xgen0, Xexc0, Xgov0)
        y0 = torch.tensor(y0_np, dtype=real_dtype, device=device)

        # Build leg boundaries identically to the scipy engine.
        n_events = event.shape[0] if event.size else 0
        event_times = (event[:, 0].astype(float) if n_events else np.empty(0))

        leg_bounds = [self.t0]
        for et_ in event_times:
            if et_ > self.t0 and (not leg_bounds or et_ > leg_bounds[-1] + 1e-15):
                leg_bounds.append(float(et_))
        if leg_bounds[-1] < stoptime:
            leg_bounds.append(float(stoptime))
        else:
            leg_bounds[-1] = float(stoptime)

        # Output buffers (no chunking — we know dense_n per leg ahead of time).
        time_chunks = []
        U_chunks = []
        ang_chunks = []
        spd_chunks = []
        eq_chunks = []
        ed_chunks = []
        efd_chunks = []
        tm_chunks = []
        te_chunks = []
        step_chunks = []

        # Initial snapshot (t = t0)
        rhs(torch.tensor(self.t0, dtype=real_dtype, device=device), y0)
        time_chunks.append(np.array([self.t0]))
        U_chunks.append(rhs._last_U_np[None, :])
        ang_chunks.append((Xgen0[:, 0] * 180.0 / np.pi)[None, :])
        spd_chunks.append((Xgen0[:, 1] / (2.0 * np.pi * freq))[None, :])
        eq_chunks.append(Xgen0[:, 2][None, :])
        ed_chunks.append(Xgen0[:, 3][None, :])
        efd_chunks.append(np.asarray(Efd0).ravel()[None, :])
        tm_chunks.append(np.asarray(Pm0).ravel()[None, :])
        te_chunks.append(np.asarray(Pe0).ravel()[None, :])
        step_chunks.append(np.array([stepsize]))

        # ---------------- Main leg-by-leg integration ----------------
        if self.output:
            print('> [torch] Running dynamic simulation...')

        ev = 0
        y = y0
        for li in range(len(leg_bounds) - 1):
            t_start = leg_bounds[li]
            t_end = leg_bounds[li + 1]
            if t_end <= t_start:
                continue

            n_eval = max(2, int(self._dense_n))
            t_eval_np = np.linspace(t_start, t_end, n_eval)
            t_eval = torch.tensor(t_eval_np, dtype=real_dtype, device=device)

            try:
                traj = _integrate_with_optional_chunking(
                    self.solver_factory, rhs, y, t_eval,
                    chunk_seconds=self._chunk_seconds,
                    solver_options=self.solver_options,
                )
            except Exception as e:  # pragma: no cover — solver failure
                return _failed_result(f'torch integrator failed: {e}',
                                      nbus, ngen, time.time() - tic)

            # traj shape: (n_eval, state_dim).  Drop the first row (== y),
            # we already saved the previous endpoint.
            traj_np = traj.detach().cpu().numpy().astype(float)
            time_arr = t_eval_np[1:]
            keep = traj_np[1:]  # n_eval-1 rows

            # Fill snapshot arrays per row.
            U_rows = np.zeros((keep.shape[0], nbus), dtype=complex)
            ang_rows = np.zeros((keep.shape[0], ngen))
            spd_rows = np.zeros((keep.shape[0], ngen))
            eq_rows = np.zeros((keep.shape[0], ngen))
            ed_rows = np.zeros((keep.shape[0], ngen))
            efd_rows = np.zeros((keep.shape[0], ngen))
            tm_rows = np.zeros((keep.shape[0], ngen))
            te_rows = np.zeros((keep.shape[0], ngen))
            step_rows = np.full(keep.shape[0], (t_end - t_start) / (n_eval - 1))

            for ri in range(keep.shape[0]):
                yi = torch.tensor(keep[ri], dtype=real_dtype, device=device)
                ti = torch.tensor(time_arr[ri], dtype=real_dtype, device=device)
                rhs(ti, yi)
                Xg, Xe, Xv = layout.unpack(keep[ri])
                U_rows[ri, :] = rhs._last_U_np
                ang_rows[ri, :] = Xg[:, 0] * 180.0 / np.pi
                spd_rows[ri, :] = Xg[:, 1] / (2.0 * np.pi * freq)
                eq_rows[ri, :] = Xg[:, 2]
                ed_rows[ri, :] = Xg[:, 3]
                efd_rows[ri, :] = Xe[:, 0]
                tm_rows[ri, :] = Xv[:, 0]
                te_rows[ri, :] = rhs._last_Pe_np

            time_chunks.append(time_arr)
            U_chunks.append(U_rows)
            ang_chunks.append(ang_rows)
            spd_chunks.append(spd_rows)
            eq_chunks.append(eq_rows)
            ed_chunks.append(ed_rows)
            efd_chunks.append(efd_rows)
            tm_chunks.append(tm_rows)
            te_chunks.append(te_rows)
            step_chunks.append(step_rows)

            # Update state for the next leg from the very last torch row.
            y = torch.tensor(keep[-1], dtype=real_dtype, device=device)

            # ---------- apply events scheduled at exactly t_end ----------
            applied_any = False
            while ev < n_events and abs(event_times[ev] - t_end) < 1e-12:
                etype = int(event[ev, 1])
                if etype == 1:
                    bus[int(buschange[ev, 1]) - 1, int(buschange[ev, 2]) - 1] = buschange[ev, 3]
                elif etype == 2:
                    branch[int(linechange[ev, 1]) - 1, int(linechange[ev, 2]) - 1] = linechange[ev, 3]
                ev += 1
                applied_any = True

            if applied_any:
                network.rebuild()
                # Save the t+ snapshot under the new topology (matches scipy
                # engine's "two rows for one t" pattern).
                rhs(torch.tensor(t_end, dtype=real_dtype, device=device), y)
                Xg, Xe, Xv = layout.unpack(keep[-1])
                time_chunks.append(np.array([t_end]))
                U_chunks.append(rhs._last_U_np[None, :])
                ang_chunks.append((Xg[:, 0] * 180.0 / np.pi)[None, :])
                spd_chunks.append((Xg[:, 1] / (2.0 * np.pi * freq))[None, :])
                eq_chunks.append(Xg[:, 2][None, :])
                ed_chunks.append(Xg[:, 3][None, :])
                efd_chunks.append(Xe[:, 0][None, :])
                tm_chunks.append(Xv[:, 0][None, :])
                te_chunks.append(rhs._last_Pe_np[None, :])
                step_chunks.append(np.array([0.0]))

        # Concat
        Time = np.concatenate(time_chunks)
        Voltages = np.concatenate(U_chunks, axis=0)
        Angles = np.concatenate(ang_chunks, axis=0)
        Speeds = np.concatenate(spd_chunks, axis=0)
        Eq_trs = np.concatenate(eq_chunks, axis=0)
        Ed_trs = np.concatenate(ed_chunks, axis=0)
        Efds = np.concatenate(efd_chunks, axis=0)
        TM = np.concatenate(tm_chunks, axis=0)
        Tes = np.concatenate(te_chunks, axis=0)
        Stepsize = np.concatenate(step_chunks)
        n = Time.shape[0]
        Errest = np.zeros(n)
        Vss = np.zeros((n, ngen))

        simulationtime = time.time() - tic
        if self.output:
            print(f'> [torch] Simulation completed in {simulationtime:5.2f} seconds')

        return IntegrationResult(
            Time=Time, Voltages=Voltages, Efds=Efds,
            Angles=Angles, Speeds=Speeds,
            Eq_trs=Eq_trs, Ed_trs=Ed_trs, Tes=Tes,
            TM=TM, Vss=Vss, Stepsize=Stepsize, Errest=Errest,
            simulationtime=simulationtime, success=True,
        )


__all__ = ["TorchIntegrationLoop"]
