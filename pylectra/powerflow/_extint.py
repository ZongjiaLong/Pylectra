"""Native ``ext2int`` / ``int2ext`` — bus-numbering re-mapping for power flow.

Direct port of legacy ``PowerFlow/ext2int.py`` and ``int2ext.py``. Only the
struct-mode (mpc dict) interface is exposed — the four-argument matrix form
is unused by every native consumer.

Behaviourally identical to the legacy versions on ``mpc`` dicts, validated
by ``tests/numerical/test_extint_parity.py``.
"""
from __future__ import annotations

import numpy as np

from pylectra.core.idx import idx_bus, idx_brch, idx_gen


def _empty_status():
    return {"on": np.array([], dtype=int), "off": np.array([], dtype=int)}


def _empty_idx():
    return {"e2i": None, "i2e": None, "status": _empty_status()}


def _new_order():
    return {
        "state": "e",
        "ext": {"bus": None, "branch": None, "gen": None},
        "bus": _empty_idx(),
        "gen": _empty_idx(),
        "branch": {"status": _empty_status()},
    }


def ext2int(mpc: dict) -> dict:
    """Convert ``mpc`` from external to internal bus numbering (in-place)."""
    BUS_I = idx_bus()[4]
    BUS_TYPE = idx_bus()[5]
    PQ, PV, REF, NONE = idx_bus()[:4]
    GEN_BUS = idx_gen()[0]
    GEN_STATUS = idx_gen()[7]
    F_BUS = idx_brch()[0]
    T_BUS = idx_brch()[1]
    BR_STATUS = idx_brch()[10]

    first = "order" not in mpc
    if not first and mpc["order"].get("state") == "i":
        return mpc

    o = _new_order() if first else mpc["order"]

    o["ext"]["bus"] = mpc["bus"].copy()
    o["ext"]["branch"] = mpc["branch"].copy()
    o["ext"]["gen"] = mpc["gen"].copy()
    if "gencost" in mpc:
        if mpc["gencost"] is None or (hasattr(mpc["gencost"], "size")
                                      and mpc["gencost"].size == 0):
            mpc.pop("gencost")
        else:
            o["ext"]["gencost"] = mpc["gencost"].copy()

    bt = mpc["bus"][:, BUS_TYPE]
    valid = (bt == PQ) | (bt == PV) | (bt == REF) | (bt == NONE)
    bad = np.flatnonzero(~valid)
    if bad.size > 0:
        raise ValueError(f"ext2int: bus index {bad[0]} has an invalid BUS_TYPE")

    bus_i = mpc["bus"][:, BUS_I].astype(int)
    nb = mpc["bus"].shape[0]
    max_bn = int(bus_i.max())
    n2i = np.zeros(max_bn + 1, dtype=int)
    n2i[bus_i] = np.arange(nb)
    bs = (bt != NONE)
    o["bus"]["status"]["on"] = np.flatnonzero(bs)
    o["bus"]["status"]["off"] = np.flatnonzero(~bs)

    gen_bus = mpc["gen"][:, GEN_BUS].astype(int)
    gs = (mpc["gen"][:, GEN_STATUS] > 0) & bs[n2i[gen_bus]]
    o["gen"]["status"]["on"] = np.flatnonzero(gs)
    o["gen"]["status"]["off"] = np.flatnonzero(~gs)

    fbus = mpc["branch"][:, F_BUS].astype(int)
    tbus = mpc["branch"][:, T_BUS].astype(int)
    brs = (mpc["branch"][:, BR_STATUS] != 0) & bs[n2i[fbus]] & bs[n2i[tbus]]
    o["branch"]["status"]["on"] = np.flatnonzero(brs)
    o["branch"]["status"]["off"] = np.flatnonzero(~brs)

    if o["bus"]["status"]["off"].size:
        mpc["bus"] = mpc["bus"][o["bus"]["status"]["on"], :]
    if o["branch"]["status"]["off"].size:
        mpc["branch"] = mpc["branch"][o["branch"]["status"]["on"], :]
    if o["gen"]["status"]["off"].size:
        mpc["gen"] = mpc["gen"][o["gen"]["status"]["on"], :]

    nb = mpc["bus"].shape[0]
    o["bus"]["i2e"] = mpc["bus"][:, BUS_I].astype(int).copy()
    e2i = np.full(int(o["bus"]["i2e"].max()) + 1, -1, dtype=int)
    e2i[o["bus"]["i2e"]] = np.arange(nb)
    o["bus"]["e2i"] = e2i

    mpc["bus"][:, BUS_I] = e2i[mpc["bus"][:, BUS_I].astype(int)]
    mpc["gen"][:, GEN_BUS] = e2i[mpc["gen"][:, GEN_BUS].astype(int)]
    mpc["branch"][:, F_BUS] = e2i[mpc["branch"][:, F_BUS].astype(int)]
    mpc["branch"][:, T_BUS] = e2i[mpc["branch"][:, T_BUS].astype(int)]

    e2i_gen = np.argsort(mpc["gen"][:, GEN_BUS], kind="stable")
    o["gen"]["e2i"] = e2i_gen
    o["gen"]["i2e"] = np.argsort(e2i_gen, kind="stable")
    mpc["gen"] = mpc["gen"][e2i_gen, :]

    o.pop("int", None)
    o["state"] = "i"
    mpc["order"] = o
    return mpc


def int2ext(mpc: dict) -> dict:
    """Convert ``mpc`` from internal back to external bus numbering."""
    BUS_I = idx_bus()[4]
    GEN_BUS = idx_gen()[0]
    F_BUS = idx_brch()[0]
    T_BUS = idx_brch()[1]

    if "order" not in mpc:
        raise ValueError("int2ext: mpc has no 'order' field")
    o = mpc["order"]
    if o.get("state") != "i":
        raise ValueError("int2ext: mpc claims it is already external")

    o.setdefault("int", {})
    o["int"]["bus"] = mpc["bus"].copy()
    o["int"]["branch"] = mpc["branch"].copy()
    o["int"]["gen"] = mpc["gen"].copy()
    if "gencost" in mpc and "gencost" in o.get("ext", {}):
        o["int"]["gencost"] = mpc["gencost"].copy()
        mpc["gencost"] = o["ext"]["gencost"].copy()

    mpc["bus"] = o["ext"]["bus"].copy()
    mpc["branch"] = o["ext"]["branch"].copy()
    mpc["gen"] = o["ext"]["gen"].copy()

    on_b = o["bus"]["status"]["on"]
    on_br = o["branch"]["status"]["on"]
    on_g = o["gen"]["status"]["on"]
    mpc["bus"][on_b, :] = o["int"]["bus"]
    mpc["branch"][on_br, :] = o["int"]["branch"]
    mpc["gen"][on_g, :] = o["int"]["gen"][o["gen"]["i2e"], :]

    i2e = o["bus"]["i2e"]
    mpc["bus"][on_b, BUS_I] = i2e[mpc["bus"][on_b, BUS_I].astype(int)]
    mpc["branch"][on_br, F_BUS] = i2e[mpc["branch"][on_br, F_BUS].astype(int)]
    mpc["branch"][on_br, T_BUS] = i2e[mpc["branch"][on_br, T_BUS].astype(int)]
    mpc["gen"][on_g, GEN_BUS] = i2e[mpc["gen"][on_g, GEN_BUS].astype(int)]

    o.pop("ext", None)
    o["state"] = "e"
    mpc["order"] = o
    return mpc


__all__ = ["ext2int", "int2ext"]
