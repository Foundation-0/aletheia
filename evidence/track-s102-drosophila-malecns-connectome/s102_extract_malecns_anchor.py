#!/usr/bin/env python3
"""Track S102 Deterministic Live Data Extraction & Anchor Generator (CPU-only).

Reads the read-only external FlyEM MaleCNS v1.0 `.feather` connectome tables and
pinned Wave-9 portal metadata outside `expedition/` (zero dataset copies inside
`expedition/`) using `pyarrow.feather` + `numpy` + `scipy.sparse`, and writes the
compact, deterministic, pure-integer/rational canonical anchor JSON:
  `s102_malecns_anchor.json` (0o600, zero floats).

Pure-stdlib verification (`s102_malecns_connectome_oracle.py`,
`verify_s102_malecns_connectome.py`, `test_s102_malecns_connectome_r5.py`) consumes
`s102_malecns_anchor.json` with zero third-party dependencies.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any

import numpy as np
import pyarrow.feather as pf
from scipy import sparse

SCHEMA_VERSION = "s102-malecns-anchor-v1"
TRACK_ID = "S102"

_HOME_DIR = Path(os.environ.get("HOME", "."))
DEFAULT_MALECNS_DIR = _HOME_DIR / "hf-datasets" / "flyem-male-cns-v1"
DEFAULT_WAVE9_DIR = _HOME_DIR / "hf-datasets" / "wave9-fly-connectome-exoplanets-20261125"
OUT_ANCHOR_PATH = Path(__file__).resolve().parent / "s102_malecns_anchor.json"

MALECNS_FILES = (
    ("annotations", "body-annotations-male-cns-v1.0-minconf-0.5.feather"),
    ("neurotransmitters", "body-neurotransmitters-male-cns-v1.0.feather"),
    ("connectome_weights", "connectome-weights-male-cns-v1.0-minconf-0.5-significant-only.feather"),
)

WAVE9_PINNED_RELPATHS = (
    ("fruitfly_calculator_readme", "repos/evnsnclr__fruitfly-calculator_README.md"),
    ("fruitfly_calculator_meta", "repos/evnsnclr__fruitfly-calculator_meta.json"),
    ("nfly_readme", "repos/zhengxuyu__nfly_README.md"),
    ("nfly_meta", "repos/zhengxuyu__nfly_meta.json"),
    ("fly_racer_readme", "repos/supat-roong__fly-racer_README.md"),
    ("fly_racer_meta", "repos/supat-roong__fly-racer_meta.json"),
    ("fly_fpv_readme", "repos/joey-david__fly-fpv_README.md"),
    ("fly_fpv_meta", "repos/joey-david__fly-fpv_meta.json"),
    ("neurocraft_fly_readme", "repos/evnsnclr__neurocraft-fly-public_README.md"),
    ("gcs_flat_connectome", "gcs_flat_connectome.json"),
    ("author_evnsnclr", "authors/evnsnclr_repos.json"),
    ("author_zhengxuyu", "authors/zhengxuyu_repos.json"),
    ("author_joey_david", "authors/joey-david_repos.json"),
    ("author_supat_roong", "authors/supat-roong_repos.json"),
)

MODULE_NAMES = (
    "M0_Sensory",
    "M1_OpticLobe",
    "M2_MushroomBody",
    "M3_CentralComplex",
    "M4_CentralBrainOther",
    "M5_Ascending",
    "M6_Descending",
    "M7_VNC_Motor",
)

CX_CORE_NAMES = ("EPG", "PEN", "Delta7", "PEG", "ER", "PFL")

SENS_SC = frozenset({
    "ol_sensory", "cb_sensory", "vnc_sensory", "sensory_ascending",
    "sensory_descending", "vnc_sensory_tbc", "cb_sensory_tbc",
})
OL_SC = frozenset({
    "ol_intrinsic", "visual_projection", "visual_centrifugal",
    "visual_projection_tbc",
})
ASC_SC = frozenset({"ascending_neuron", "efferent_ascending"})
DESC_SC = frozenset({"descending_neuron", "efferent_descending"})
VNC_SC = frozenset({
    "vnc_intrinsic", "vnc_motor", "cb_motor", "vnc_efferent",
    "vnc_endocrine", "vnc_tbc",
})
CB_SC = frozenset({"cb_intrinsic", "cb_endocrine", "cb_efferent", "ENS"})
MB_CLS = frozenset({"Kenyon_Cell", "MBON", "DAN"})

WEIGHT_THRESHOLDS = (1, 2, 5, 10, 20, 50, 100, 500)
TOP_PERMILLE_SPECS = (
    ("top_0p5pct", 5),
    ("top_1p0pct", 10),
    ("top_5p0pct", 50),
    ("top_10p0pct", 100),
)
NULL_LCG_SEED = 102
NULL_ATTEMPT_MULTIPLIER = 10


def sha256_file(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            h.update(chunk)
    return total, h.hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("ascii")


def write_atomic_0600(path: Path, data: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=".s102_anchor_", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp_name, str(path))
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _triads_csr(
    u: np.ndarray,
    v: np.ndarray,
    n: int,
    sgn_vec: np.ndarray,
) -> dict[str, int]:
    adj = sparse.csr_matrix((np.ones(len(u), dtype=np.int64), (u, v)), shape=(n, n))
    adj.sum_duplicates()
    adj.data[:] = 1
    adj2 = adj @ adj
    recip = int(adj.multiply(adj.T).sum())
    ffl = int(adj2.multiply(adj).sum())
    cyc3 = int(adj2.multiply(adj.T).sum()) // 3

    s_vals = sgn_vec[u].astype(np.int64)
    nz = s_vals != 0
    s_mat = sparse.csr_matrix((s_vals[nz], (u[nz], v[nz])), shape=(n, n))
    s_abs = s_mat.copy()
    s_abs.data[:] = 1
    s2 = s_mat @ s_mat
    sa2 = s_abs @ s_abs

    ffl_signed_total = int(sa2.multiply(s_abs).sum())
    ffl_signed_net = int(s2.multiply(s_mat).sum())
    cyc_signed_total = int(sa2.multiply(s_abs.T).sum()) // 3
    cyc_signed_net = int(s2.multiply(s_mat.T).sum()) // 3

    return {
        "reciprocal_directed_edges": recip,
        "ffl_total": ffl,
        "directed_3cycles_total": cyc3,
        "signed_ffl_total": ffl_signed_total,
        "signed_ffl_coherent_pos": (ffl_signed_total + ffl_signed_net) // 2,
        "signed_ffl_incoherent_neg": (ffl_signed_total - ffl_signed_net) // 2,
        "signed_3cycles_total": cyc_signed_total,
        "signed_3cycles_positive_feedback": (cyc_signed_total + cyc_signed_net) // 2,
        "signed_3cycles_negative_feedback": (cyc_signed_total - cyc_signed_net) // 2,
    }


def extract_anchor(malecns_dir: Path, wave9_dir: Path) -> dict[str, Any]:
    malecns_pins: list[dict[str, Any]] = []
    for key, fname in MALECNS_FILES:
        fpath = malecns_dir / fname
        size_b, digest = sha256_file(fpath)
        malecns_pins.append({
            "id": key,
            "filename": fname,
            "bytes": size_b,
            "sha256": digest,
        })

    wave9_pins: list[dict[str, Any]] = []
    for key, relpath in WAVE9_PINNED_RELPATHS:
        fpath = wave9_dir / relpath
        size_b, digest = sha256_file(fpath)
        wave9_pins.append({
            "id": key,
            "relpath": relpath,
            "bytes": size_b,
            "sha256": digest,
        })

    ann = pf.read_table(
        malecns_dir / "body-annotations-male-cns-v1.0-minconf-0.5.feather",
        columns=["bodyId", "superclass", "class", "type"],
    )
    nt = pf.read_table(
        malecns_dir / "body-neurotransmitters-male-cns-v1.0.feather",
        columns=["body", "consensus_nt"],
    )
    wt = pf.read_table(
        malecns_dir / "connectome-weights-male-cns-v1.0-minconf-0.5-significant-only.feather",
        columns=["body_pre", "body_post", "weight"],
    )

    ann_ids = ann["bodyId"].to_numpy()
    ann_sc = ann["superclass"].to_pylist()
    ann_cls = ann["class"].to_pylist()
    ann_tp = ann["type"].to_pylist()

    pre = wt["body_pre"].to_numpy()
    post = wt["body_post"].to_numpy()
    w = wt["weight"].to_numpy()

    all_bodies = np.union1d(np.union1d(ann_ids, pre), post)
    n_all = len(all_bodies)
    pre_i = np.searchsorted(all_bodies, pre)
    post_i = np.searchsorted(all_bodies, post)
    act_nodes = np.union1d(np.unique(pre_i), np.unique(post_i))

    # Neurotransmitter lookup
    nt_ids = nt["body"].to_numpy()
    nt_str = nt["consensus_nt"].to_pylist()
    idx_nt = np.searchsorted(all_bodies, nt_ids)
    mask_nt = (idx_nt < n_all) & (all_bodies[np.minimum(idx_nt, n_all - 1)] == nt_ids)
    nt_sign = np.zeros(n_all, dtype=np.int8)
    nt_cat = np.zeros(n_all, dtype=np.int8)
    nt_label = ["MISSING"] * n_all

    sign_map = {"acetylcholine": 1, "gaba": -1, "glutamate": -1, "histamine": -1}
    cat_map = {
        "acetylcholine": 1,
        "gaba": 2,
        "glutamate": 2,
        "histamine": 2,
        "dopamine": 3,
        "octopamine": 3,
        "serotonin": 3,
    }
    for pos, raw_s in zip(
        idx_nt[mask_nt].tolist(),
        (nt_str[i] for i in np.nonzero(mask_nt)[0].tolist()),
    ):
        lbl = raw_s if isinstance(raw_s, str) and raw_s else "MISSING"
        nt_label[pos] = lbl
        if lbl in sign_map:
            nt_sign[pos] = sign_map[lbl]
        if lbl in cat_map:
            nt_cat[pos] = cat_map[lbl]

    active_nt_counts = dict(sorted(Counter(nt_label[i] for i in act_nodes.tolist()).items()))

    # Module & CX core lookup
    idx_ann = np.searchsorted(all_bodies, ann_ids)
    mod_arr = np.full(n_all, 8, dtype=np.int8)
    cx_sub = np.full(n_all, -1, dtype=np.int8)
    for pos, sc, cl, tp in zip(idx_ann.tolist(), ann_sc, ann_cls, ann_tp):
        if cl == "CX":
            mod_arr[pos] = 3
        elif cl in MB_CLS:
            mod_arr[pos] = 2
        elif sc in SENS_SC:
            mod_arr[pos] = 0
        elif sc in OL_SC:
            mod_arr[pos] = 1
        elif sc in ASC_SC:
            mod_arr[pos] = 5
        elif sc in DESC_SC:
            mod_arr[pos] = 6
        elif sc in VNC_SC:
            mod_arr[pos] = 7
        elif sc in CB_SC:
            mod_arr[pos] = 4
        if tp:
            if tp == "EPG":
                cx_sub[pos] = 0
            elif tp.startswith("PEN"):
                cx_sub[pos] = 1
            elif tp == "Delta7":
                cx_sub[pos] = 2
            elif tp == "PEG":
                cx_sub[pos] = 3
            elif tp.startswith("ER"):
                cx_sub[pos] = 4
            elif tp.startswith("PFL"):
                cx_sub[pos] = 5

    # Whole-CNS exact integer stats
    edge_count = int(len(w))
    total_synapses = int(w.sum(dtype=np.int64))
    min_weight = int(w.min())
    max_weight = int(w.max())
    self_loops = int((pre == post).sum())
    ann_with_superclass = int(sum(1 for sc in ann_sc if sc is not None))
    distinct_types = int(len({tp for tp in ann_tp if tp is not None}))

    # Heavy-tail thresholds
    threshold_table: list[dict[str, int]] = []
    for thr in WEIGHT_THRESHOLDS:
        m = w >= thr
        threshold_table.append({
            "min_weight": int(thr),
            "edges": int(m.sum()),
            "synapses": int(w[m].sum(dtype=np.int64)),
        })

    # Top-k permille exact synaptic concentration (descending weight order)
    w_sorted_desc = np.sort(w)[::-1]
    top_k_table: list[dict[str, Any]] = []
    for label, permille in TOP_PERMILLE_SPECS:
        k = (edge_count * permille) // 1000
        top_syn = int(w_sorted_desc[:k].sum(dtype=np.int64))
        cutoff_w = int(w_sorted_desc[k - 1])
        top_k_table.append({
            "label": label,
            "permille": int(permille),
            "edge_count": int(k),
            "cutoff_weight": cutoff_w,
            "synapses": top_syn,
        })

    # Dale's-law whole-CNS synapse partition
    pre_cat = nt_cat[pre_i]
    pre_sgn = nt_sign[pre_i].astype(np.int64)
    dale_partition: dict[str, dict[str, int]] = {}
    for code, label in (
        (1, "excitatory_ach"),
        (2, "inhibitory_gaba_glu_his"),
        (3, "modulatory_da_oa_5ht"),
        (0, "unclear_missing"),
    ):
        m = pre_cat == code
        dale_partition[label] = {
            "edges": int(m.sum()),
            "synapses": int(w[m].sum(dtype=np.int64)),
        }

    # 8x8 functional supergraph (modules 0..7)
    m_pre = mod_arr[pre_i]
    m_post = mod_arr[post_i]
    valid8 = (m_pre < 8) & (m_post < 8)
    w8_u = np.zeros((8, 8), dtype=np.int64)
    w8_s = np.zeros((8, 8), dtype=np.int64)
    w8_e = np.zeros((8, 8), dtype=np.int64)
    np.add.at(w8_u, (m_pre[valid8], m_post[valid8]), w[valid8])
    np.add.at(w8_s, (m_pre[valid8], m_post[valid8]), w[valid8] * pre_sgn[valid8])
    np.add.at(w8_e, (m_pre[valid8], m_post[valid8]), 1)

    act_mod_counts = Counter(mod_arr[act_nodes].tolist())
    module_active_neurons = [int(act_mod_counts.get(i, 0)) for i in range(8)]
    unannotated_active_neurons = int(act_mod_counts.get(8, 0))

    # 6x6 Central Complex core (EPG, PEN, Delta7, PEG, ER, PFL)
    c_pre = cx_sub[pre_i]
    c_post = cx_sub[post_i]
    valid6 = (c_pre >= 0) & (c_post >= 0)
    w6_u = np.zeros((6, 6), dtype=np.int64)
    w6_s = np.zeros((6, 6), dtype=np.int64)
    w6_e = np.zeros((6, 6), dtype=np.int64)
    np.add.at(w6_u, (c_pre[valid6], c_post[valid6]), w[valid6])
    np.add.at(w6_s, (c_pre[valid6], c_post[valid6]), w[valid6] * pre_sgn[valid6])
    np.add.at(w6_e, (c_pre[valid6], c_post[valid6]), 1)
    cx_core_neurons = [int((cx_sub[act_nodes] == i).sum()) for i in range(6)]

    # Exact CX internal directed & signed triad motifs (class == 'CX', w >= 10, no self-loops)
    cx_mask_nodes = mod_arr == 3
    cx_e_mask = cx_mask_nodes[pre_i] & cx_mask_nodes[post_i] & (pre_i != post_i) & (w >= 10)
    cx_u = pre_i[cx_e_mask]
    cx_v = post_i[cx_e_mask]
    cx_w = w[cx_e_mask]
    cx_nodes_u = np.union1d(np.unique(cx_u), np.unique(cx_v))
    n_cx = len(cx_nodes_u)
    u_loc = np.searchsorted(cx_nodes_u, cx_u)
    v_loc = np.searchsorted(cx_nodes_u, cx_v)
    sgn_loc = nt_sign[cx_nodes_u]

    cx_obs = _triads_csr(u_loc, v_loc, n_cx, sgn_loc)

    # Deterministic pure-integer LCG Maslov-Sneppen degree-preserving null (seed=102, 10*E attempts)
    edge_u = u_loc.tolist()
    edge_v = v_loc.tolist()
    edge_set = set(zip(edge_u, edge_v))
    m_e = len(edge_u)
    state = NULL_LCG_SEED
    swaps = 0
    mask64 = (1 << 64) - 1
    for _ in range(NULL_ATTEMPT_MULTIPLIER * m_e):
        state = (6364136223846793005 * state + 1442695040888963407) & mask64
        i1 = (state >> 16) % m_e
        state = (6364136223846793005 * state + 1442695040888963407) & mask64
        i2 = (state >> 16) % m_e
        if i1 == i2:
            continue
        a, b = edge_u[i1], edge_v[i1]
        c, d = edge_u[i2], edge_v[i2]
        if a == d or c == b or a == c or b == d:
            continue
        if (a, d) in edge_set or (c, b) in edge_set:
            continue
        edge_set.remove((a, b))
        edge_set.remove((c, d))
        edge_set.add((a, d))
        edge_set.add((c, b))
        edge_v[i1] = d
        edge_v[i2] = b
        swaps += 1

    cx_null = _triads_csr(
        np.array(edge_u, dtype=np.int64),
        np.array(edge_v, dtype=np.int64),
        n_cx,
        sgn_loc,
    )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "dataset_release": "flyem-male-cns-v1.0-minconf-0.5-significant-only",
        "license": "CC-BY-4.0",
        "malecns_external_pins": malecns_pins,
        "wave9_portal_pins": wave9_pins,
        "whole_cns_topology": {
            "annotation_rows": int(len(ann_ids)),
            "annotation_with_superclass": ann_with_superclass,
            "distinct_annotated_cell_types": distinct_types,
            "neurotransmitter_table_rows": int(len(nt_ids)),
            "union_body_count": int(n_all),
            "active_connected_neurons": int(len(act_nodes)),
            "directed_edges": edge_count,
            "total_synapses": total_synapses,
            "min_edge_weight": min_weight,
            "max_edge_weight": max_weight,
            "self_loop_edges": self_loops,
            "active_neuron_neurotransmitters": active_nt_counts,
            "dale_edge_synapse_partition": dale_partition,
            "weight_thresholds": threshold_table,
            "top_k_concentration": top_k_table,
        },
        "functional_supergraph_8x8": {
            "module_names": list(MODULE_NAMES),
            "active_neurons_per_module": module_active_neurons,
            "unannotated_active_neurons": unannotated_active_neurons,
            "covered_edges": int(valid8.sum()),
            "covered_synapses": int(w[valid8].sum(dtype=np.int64)),
            "unsigned_synapses_8x8": [[int(x) for x in row] for row in w8_u.tolist()],
            "dale_signed_synapses_8x8": [[int(x) for x in row] for row in w8_s.tolist()],
            "directed_edges_8x8": [[int(x) for x in row] for row in w8_e.tolist()],
        },
        "central_complex_core_6x6": {
            "population_names": list(CX_CORE_NAMES),
            "active_neurons_per_population": cx_core_neurons,
            "unsigned_synapses_6x6": [[int(x) for x in row] for row in w6_u.tolist()],
            "dale_signed_synapses_6x6": [[int(x) for x in row] for row in w6_s.tolist()],
            "directed_edges_6x6": [[int(x) for x in row] for row in w6_e.tolist()],
        },
        "central_complex_triads_w10": {
            "min_weight": 10,
            "active_nodes": int(n_cx),
            "directed_edges": int(len(u_loc)),
            "total_synapses": int(cx_w.sum(dtype=np.int64)),
            "observed": cx_obs,
            "maslov_sneppen_null": {
                "lcg_seed": NULL_LCG_SEED,
                "attempt_multiplier": NULL_ATTEMPT_MULTIPLIER,
                "accepted_swaps": int(swaps),
                **cx_null,
            },
        },
    }

    payload_digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_digest,
        "payload": payload,
    }
    return envelope


def main() -> int:
    malecns_dir = Path(os.environ.get("S102_MALECNS_DIR", str(DEFAULT_MALECNS_DIR)))
    wave9_dir = Path(os.environ.get("S102_WAVE9_DIR", str(DEFAULT_WAVE9_DIR)))
    if not malecns_dir.is_dir() or not wave9_dir.is_dir():
        sys.stderr.write("Missing external read-only dataset directories.\n")
        return 2
    env = extract_anchor(malecns_dir, wave9_dir)
    raw = canonical_json_bytes(env)
    write_atomic_0600(OUT_ANCHOR_PATH, raw)
    mode = stat.S_IMODE(os.lstat(OUT_ANCHOR_PATH).st_mode)
    file_sha = hashlib.sha256(raw).hexdigest()
    sys.stdout.write(
        json.dumps(
            {
                "status": "OK",
                "anchor_file": OUT_ANCHOR_PATH.name,
                "bytes": len(raw),
                "mode_octal": oct(mode),
                "payload_sha256": env["payload_sha256"],
                "file_sha256": file_sha,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
