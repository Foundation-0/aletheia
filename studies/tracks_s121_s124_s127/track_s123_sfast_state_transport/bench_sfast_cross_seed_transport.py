#!/usr/bin/env python3
"""Track S123 (EXP-Q28a + EXP-Q30c): Deterministic CPU Cross-Seed State Transport Micro-Benchmark.

Tests:
  1. Cross-seed O(1) HoloSphere S_fast Woodbury associative-memory transport (3 seeds -> 6 pairs):
     Native upper bound, Raw unaligned, Bilinear Frobenius Procrustes, Bilinear OLS Procrustes,
     Mid-document Prefix Handoff + Suffix Continuation, SVD Rank Sweep r in {4, 8, 16, 32}
     (clean 64-doc calibration and isotropic orthogonal perturbation sigma=0.35 denoising),
     Random O(d) null, and Shuffled-Doc null.
  2. Non-Abelian A_5 (L=16, 60-class) CayleySU2 holonomy mid-word prefix handoff (3 seeds -> 6 pairs):
     Native upper bound, Kabsch SO(3) (det=+1) conjugation, Improper O(3) (det=-1) reflection
     obstruction, Abelian RoPE-style commutative sum control (W14-OBS-1), Random SO(3) null,
     and Shuffled-Word null.

CPU-only (CUDA_VISIBLE_DEVICES="", OPENBLAS_NUM_THREADS=1), zero bare asserts,
pure-stdlib --selftest-stdlib mode for isolated -I parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_BENCH = "aletheia.s123.cross_seed_state_transport_bench.v1"
SCHEMA_SELFTEST = "aletheia.s123.cross_seed_state_transport_selftest.v1"

SEEDS: Tuple[int, int, int] = (42, 137, 2026)
RANK_SWEEP: Tuple[int, ...] = (4, 8, 16, 32)
D_HEAD = 32
N_KEYS = 12
N_VALS = 12
T_DOC = 8
A5_LEN = 16


class BenchTransportError(ValueError):
    """Fail-closed error for Track S123 CPU benchmark."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise BenchTransportError(code, detail)


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Pure-stdlib deterministic dataset builders & A_5 group generator (zero deps)
# ---------------------------------------------------------------------------


def build_assoc_recall_dataset(
    n_samples: int,
    *,
    seed: int,
    n_keys: int = N_KEYS,
    n_vals: int = N_VALS,
    t_doc: int = T_DOC,
) -> List[Tuple[List[Tuple[int, int]], int, int]]:
    """Generate deterministic associative key-value documents with deliberate overwrite steps."""
    require_ok(n_samples >= 1, "BAD_N_SAMPLES", "n_samples must be >= 1")
    require_ok(n_keys >= 4, "BAD_N_KEYS", "n_keys must be >= 4")
    require_ok(n_vals >= 4, "BAD_N_VALS", "n_vals must be >= 4")
    require_ok(t_doc >= 4, "BAD_T_DOC", "t_doc must be >= 4")
    require_ok(t_doc - 2 <= n_keys, "BAD_KEY_CAP", "t_doc - 2 must be <= n_keys")
    rng = random.Random(seed)
    docs: List[Tuple[List[Tuple[int, int]], int, int]] = []
    for _ in range(n_samples):
        # Choose distinct keys for first t_doc - 2 steps, then overwrite 2 earlier keys so Woodbury erasure matters!
        base_keys = rng.sample(range(n_keys), t_doc - 2)
        seq: List[Tuple[int, int]] = []
        mem: Dict[int, int] = {}
        for k in base_keys:
            v = rng.randrange(n_vals)
            seq.append((k, v))
            mem[k] = v
        # Two overwrite steps updating two distinct keys to NEW distinct values
        for ow_k in rng.sample(base_keys, 2):
            old_v = mem[ow_k]
            new_v = (old_v + 1 + rng.randrange(n_vals - 1)) % n_vals
            seq.append((ow_k, new_v))
            mem[ow_k] = new_v
        q_k = rng.choice(list(mem.keys()))
        docs.append((seq, q_k, mem[q_k]))
    return docs


def _quat_mul_py(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    return (
        a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
        a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
        a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
        a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0],
    )


def _quat_to_so3_key(q: Tuple[float, float, float, float]) -> Tuple[int, ...]:
    """Sign-invariant (+q == -q) quantized SO(3) signature for exact 60-element A_5 group indexing."""
    q0, q1, q2, q3 = q
    mat = (
        1.0 - 2.0 * (q2 * q2 + q3 * q3), 2.0 * (q1 * q2 - q0 * q3), 2.0 * (q1 * q3 + q0 * q2),
        2.0 * (q1 * q2 + q0 * q3), 1.0 - 2.0 * (q1 * q1 + q3 * q3), 2.0 * (q2 * q3 - q0 * q1),
        2.0 * (q1 * q3 - q0 * q2), 2.0 * (q2 * q3 + q0 * q1), 1.0 - 2.0 * (q1 * q1 + q2 * q2),
    )
    return tuple(int(round(x * 10000.0)) for x in mat)


def build_a5_generators_and_table() -> Dict[str, Any]:
    """Build exact 4-generator icosahedral 2I -> A_5 (60 classes) lookup table in pure stdlib."""
    phi = (1.0 + math.sqrt(5.0)) * 0.5
    inv_phi = 1.0 / phi
    # Standard binary icosahedral generators in SU(2):
    # g0: order-5 rotation in 2I/+-I (angle 2*pi/5), g1: order-2/order-3 non-commuting partner
    g0 = (0.5 * phi, 0.5 * inv_phi, 0.5, 0.0)
    g1 = (0.5, 0.5, 0.5, 0.5)
    g0_inv = (g0[0], -g0[1], -g0[2], -g0[3])
    g1_inv = (g1[0], -g1[1], -g1[2], -g1[3])
    gens = (g0, g1, g0_inv, g1_inv)
    # Exact Cayley vectors w = q_vec / (1 + q_0) for each generator (all have q_0 >= 0.5 > 0 -> acute basin!)
    gen_w = tuple((g[1] / (1.0 + g[0]), g[2] / (1.0 + g[0]), g[3] / (1.0 + g[0])) for g in gens)

    # BFS closure in SO(3) to enumerate all 60 distinct elements of A_5
    ident = (1.0, 0.0, 0.0, 0.0)
    seen: Dict[Tuple[int, ...], int] = {_quat_to_so3_key(ident): 0}
    queue: List[Tuple[float, float, float, float]] = [ident]
    idx = 0
    while idx < len(queue):
        cur = queue[idx]
        idx += 1
        for g in gens:
            nxt = _quat_mul_py(cur, g)
            k = _quat_to_so3_key(nxt)
            if k not in seen:
                seen[k] = len(seen)
                queue.append(nxt)
    return {"gens_quat": gens, "gens_cayley_w": gen_w, "so3_key_to_id": seen}


def build_a5_word_dataset(
    n_samples: int,
    *,
    seed: int,
    word_len: int = A5_LEN,
) -> Tuple[List[List[int]], List[int]]:
    """Generate deterministic length-L words over 4 A_5 generators with exact 60-class group targets."""
    require_ok(n_samples >= 1, "BAD_A5_N", "n_samples must be >= 1")
    require_ok(word_len >= 4, "BAD_A5_LEN", "word_len must be >= 4")
    tbl = build_a5_generators_and_table()
    gens = tbl["gens_quat"]
    key_to_id = tbl["so3_key_to_id"]
    rng = random.Random(seed)
    words: List[List[int]] = []
    labels: List[int] = []
    for _ in range(n_samples):
        w = [rng.randrange(4) for _ in range(word_len)]
        q = (1.0, 0.0, 0.0, 0.0)
        for tok in w:
            q = _quat_mul_py(q, gens[tok])
        words.append(w)
        labels.append(key_to_id[_quat_to_so3_key(q)])
    return words, labels


def count_a5_reversal_fixed_prefixes(words: Sequence[Sequence[int]], half: int) -> int:
    """Count prefixes P = w[:half] satisfying rev(P) == P in A_5 (exact T2b det=-1 survival count)."""
    require_ok(half >= 1, "BAD_HALF", "half must be >= 1")
    tbl = build_a5_generators_and_table()
    gens = tbl["gens_quat"]
    fixed = 0
    for w in words:
        require_ok(len(w) >= half, "WORD_TOO_SHORT", "word shorter than prefix half")
        pref = w[:half]
        q_fwd = (1.0, 0.0, 0.0, 0.0)
        q_rev = (1.0, 0.0, 0.0, 0.0)
        for tok in pref:
            q_fwd = _quat_mul_py(q_fwd, gens[tok])
        for tok in reversed(pref):
            q_rev = _quat_mul_py(q_rev, gens[tok])
        if _quat_to_so3_key(q_fwd) == _quat_to_so3_key(q_rev):
            fixed += 1
    return fixed


def run_stdlib_selftest() -> Dict[str, Any]:
    """Pure-stdlib verification of deterministic datasets, |A_5| == 60, and exact rev(P)==P prefix count."""
    docs = build_assoc_recall_dataset(16, seed=2026)
    tbl = build_a5_generators_and_table()
    words_test, _ = build_a5_word_dataset(200, seed=5005, word_len=A5_LEN)
    rev_fixed = count_a5_reversal_fixed_prefixes(words_test, A5_LEN // 2)
    g0, g1 = tbl["gens_quat"][0], tbl["gens_quat"][1]
    non_abelian = _quat_to_so3_key(_quat_mul_py(g0, g1)) != _quat_to_so3_key(_quat_mul_py(g1, g0))

    payload: Dict[str, Any] = {
        "schema": SCHEMA_SELFTEST,
        "seeds": list(SEEDS),
        "rank_sweep": list(RANK_SWEEP),
        "assoc_sample_count": len(docs),
        "a5_group_order": len(tbl["so3_key_to_id"]),
        "a5_non_abelian_verified": non_abelian,
        "a5_seed5005_rev_fixed_prefixes": rev_fixed,
        "passed": len(docs) == 16 and len(tbl["so3_key_to_id"]) == 60 and non_abelian and rev_fixed == 64,
    }
    payload["payload_sha256"] = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return payload


# ---------------------------------------------------------------------------
# CPU PyTorch Micro-Experiments (Strictly Deterministic, CUDA_VISIBLE_DEVICES="")
# ---------------------------------------------------------------------------


def _fit_orthogonal_procrustes_torch(torch: Any, za: Any, zb: Any) -> Any:
    """Closed-form O(d) Procrustes R minimizing ||zb - za @ R^T||_F (za, zb: [N, d])."""
    cross = zb.T @ za
    u, _, vh = torch.linalg.svd(cross, full_matrices=False)
    return u @ vh


def _fit_kabsch_so3_torch(torch: Any, wa: Any, wb: Any) -> Tuple[Any, Any]:
    """Return (R_proper det=+1, R_improper det=-1) on R^3 (wa, wb: [N, 3])."""
    cross = wb.T @ wa
    u, _, vh = torch.linalg.svd(cross, full_matrices=False)
    r_raw = u @ vh
    det_raw = float(torch.linalg.det(r_raw).item())
    flip = torch.diag(torch.tensor([1.0, 1.0, -1.0], dtype=wa.dtype))
    if det_raw >= 0.0:
        r_proper = r_raw
        r_improper = u @ flip @ vh
    else:
        r_proper = u @ flip @ vh
        r_improper = r_raw
    return r_proper, r_improper


def _so3_to_unit_quat_torch(torch: Any, r_mat: Any) -> Any:
    """Convert proper 3x3 SO(3) matrix (det=+1) to unit quaternion (q0, q1, q2, q3) via Shepperd branch."""
    m = r_mat.double()
    tr = float(m[0, 0] + m[1, 1] + m[2, 2])
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        q0 = 0.25 * s
        q1 = float(m[2, 1] - m[1, 2]) / s
        q2 = float(m[0, 2] - m[2, 0]) / s
        q3 = float(m[1, 0] - m[0, 1]) / s
    elif float(m[0, 0]) > float(m[1, 1]) and float(m[0, 0]) > float(m[2, 2]):
        s = math.sqrt(1.0 + float(m[0, 0] - m[1, 1] - m[2, 2])) * 2.0
        q0 = float(m[2, 1] - m[1, 2]) / s
        q1 = 0.25 * s
        q2 = float(m[0, 1] + m[1, 0]) / s
        q3 = float(m[0, 2] + m[2, 0]) / s
    elif float(m[1, 1]) > float(m[2, 2]):
        s = math.sqrt(1.0 + float(m[1, 1] - m[0, 0] - m[2, 2])) * 2.0
        q0 = float(m[0, 2] - m[2, 0]) / s
        q1 = float(m[0, 1] + m[1, 0]) / s
        q2 = 0.25 * s
        q3 = float(m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + float(m[2, 2] - m[0, 0] - m[1, 1])) * 2.0
        q0 = float(m[1, 0] - m[0, 1]) / s
        q1 = float(m[0, 2] + m[2, 0]) / s
        q2 = float(m[1, 2] + m[2, 1]) / s
        q3 = 0.25 * s
    q = torch.tensor([q0, q1, q2, q3], dtype=torch.float32)
    return q / q.norm().clamp_min(1e-8)


def _run_exp1_sfast_assoc_transport(torch: Any) -> Dict[str, Any]:
    """Experiment 1: Cross-seed O(1) S_fast Woodbury transport + SVD rank sweep (3 seeds -> 6 pairs)."""
    import torch.nn as nn  # type: ignore[import-not-found]
    import torch.nn.functional as F  # type: ignore[import-not-found]

    class MicroWoodburyCell(nn.Module):
        def __init__(self, seed: int) -> None:
            super().__init__()
            gen = torch.Generator(device="cpu").manual_seed(seed)
            self.emb_k = nn.Parameter(torch.randn((N_KEYS, D_HEAD), generator=gen) * 0.5)
            self.emb_v = nn.Parameter(torch.randn((N_VALS, D_HEAD), generator=gen) * 0.5)
            self.emb_q = nn.Parameter(torch.randn((N_KEYS, D_HEAD), generator=gen) * 0.5)
            self.beta_logit = nn.Parameter(torch.tensor(0.8))
            self.head = nn.Linear(D_HEAD, N_VALS, bias=False)
            with torch.no_grad():
                self.head.weight.copy_(torch.randn((N_VALS, D_HEAD), generator=gen) * 0.3)
                # Freeze a distinct random orthogonal gauge per seed to ensure independent bases
                g_k = torch.randn((D_HEAD, D_HEAD), generator=gen)
                u_k, _, vh_k = torch.linalg.svd(g_k)
                self.register_buffer("gauge_k", u_k @ vh_k)

        def keys(self, k_ids: Any) -> Any:
            raw = self.emb_k[k_ids] @ self.gauge_k
            return F.normalize(raw, dim=-1)

        def vals(self, v_ids: Any) -> Any:
            return F.normalize(self.emb_v[v_ids], dim=-1)

        def queries(self, q_ids: Any) -> Any:
            raw = self.emb_q[q_ids] @ self.gauge_k
            return F.normalize(raw, dim=-1)

        def accumulate_state(self, k_seq: Any, v_seq: Any, s_init: Optional[Any] = None) -> Any:
            # Right-acting Woodbury: S' = S (I - beta k k^T) + beta v k^T, S shape [B, D, D]
            bsz, t_len = k_seq.shape
            ks = self.keys(k_seq)  # [B, T, D]
            vs = self.vals(v_seq)  # [B, T, D]
            beta = torch.sigmoid(self.beta_logit)
            s = torch.zeros((bsz, D_HEAD, D_HEAD), dtype=torch.float32) if s_init is None else s_init.clone()
            for t in range(t_len):
                kt = ks[:, t, :]  # [B, D]
                vt = vs[:, t, :]  # [B, D]
                sk = torch.bmm(s, kt.unsqueeze(-1)).squeeze(-1)  # [B, D]
                s = s + beta * torch.bmm((vt - sk).unsqueeze(-1), kt.unsqueeze(1))
            return s

        def readout_logits(self, s_mat: Any, q_ids: Any) -> Any:
            q = self.queries(q_ids)  # [B, D]
            y = torch.bmm(s_mat, q.unsqueeze(-1)).squeeze(-1)
            return self.head(y) * 8.0

    def _pack_docs(docs: Sequence[Tuple[List[Tuple[int, int]], int, int]]) -> Tuple[Any, Any, Any, Any]:
        k_seq = torch.tensor([[pair[0] for pair in d[0]] for d in docs], dtype=torch.long)
        v_seq = torch.tensor([[pair[1] for pair in d[0]] for d in docs], dtype=torch.long)
        q_ids = torch.tensor([d[1] for d in docs], dtype=torch.long)
        y_ids = torch.tensor([d[2] for d in docs], dtype=torch.long)
        return k_seq, v_seq, q_ids, y_ids

    train_docs = build_assoc_recall_dataset(1024, seed=1001)
    cal_docs = build_assoc_recall_dataset(64, seed=2002)
    test_docs = build_assoc_recall_dataset(128, seed=3003)

    tr_k, tr_v, tr_q, tr_y = _pack_docs(train_docs)
    ca_k, ca_v, ca_q, ca_y = _pack_docs(cal_docs)
    te_k, te_v, te_q, te_y = _pack_docs(test_docs)

    models: Dict[int, MicroWoodburyCell] = {}
    native_accs: Dict[str, float] = {}
    for sd in SEEDS:
        torch.manual_seed(sd)
        m = MicroWoodburyCell(sd)
        opt = torch.optim.AdamW(m.parameters(), lr=0.04, weight_decay=1e-4)
        rng_idx = torch.Generator(device="cpu").manual_seed(sd + 77)
        for _ in range(260):
            idx = torch.randint(0, len(train_docs), (64,), generator=rng_idx)
            s_m = m.accumulate_state(tr_k[idx], tr_v[idx])
            lg = m.readout_logits(s_m, tr_q[idx])
            loss = F.cross_entropy(lg, tr_y[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
        m.eval()
        with torch.no_grad():
            s_te = m.accumulate_state(te_k, te_v)
            acc = float((m.readout_logits(s_te, te_q).argmax(dim=-1) == te_y).float().mean().item())
        models[sd] = m
        native_accs[f"seed_{sd}"] = round(acc, 4)

    # Cross-seed evaluation across all 6 ordered pairs (A -> B, A != B)
    all_k_ids = torch.arange(N_KEYS, dtype=torch.long)
    all_v_ids = torch.arange(N_VALS, dtype=torch.long)
    pair_out: Dict[str, Any] = {}

    with torch.no_grad():
        for sd_a in SEEDS:
            for sd_b in SEEDS:
                if sd_a == sd_b:
                    continue
                ma, mb = models[sd_a], models[sd_b]
                pkey = f"s{sd_a}_to_s{sd_b}"

                # 1. Fit bilinear orthogonal gauge (Q_k, Q_v) strictly on calibration tokens!
                ka_cal = ma.keys(ca_k.reshape(-1))
                kb_cal = mb.keys(ca_k.reshape(-1))
                va_cal = ma.vals(ca_v.reshape(-1))
                vb_cal = mb.vals(ca_v.reshape(-1))
                q_k = _fit_orthogonal_procrustes_torch(torch, ka_cal, kb_cal)
                q_v = _fit_orthogonal_procrustes_torch(torch, va_cal, vb_cal)

                # Calibration S_fast states for Frob vs OLS scalar scaling
                sa_cal = ma.accumulate_state(ca_k, ca_v)
                sb_cal = mb.accumulate_state(ca_k, ca_v)
                sa_cal_rot = torch.einsum("ij,bjk,lk->bil", q_v, sa_cal, q_k)
                norm_a = float(sa_cal_rot.norm().item())
                norm_b = float(sb_cal.norm().item())
                s_frob = norm_b / max(1e-8, norm_a)
                s_ols = float((sa_cal_rot * sb_cal).sum().item()) / max(1e-8, norm_a * norm_a)

                # Test states
                sa_te = ma.accumulate_state(te_k, te_v)
                sb_te_nat = mb.accumulate_state(te_k, te_v)
                sb_te_rot = torch.einsum("ij,bjk,lk->bil", q_v, sa_te, q_k)

                acc_nat = float((mb.readout_logits(sb_te_nat, te_q).argmax(dim=-1) == te_y).float().mean().item())
                acc_raw = float((mb.readout_logits(sa_te, te_q).argmax(dim=-1) == te_y).float().mean().item())
                acc_frob = float((mb.readout_logits(s_frob * sb_te_rot, te_q).argmax(dim=-1) == te_y).float().mean().item())
                acc_ols = float((mb.readout_logits(s_ols * sb_te_rot, te_q).argmax(dim=-1) == te_y).float().mean().item())

                # Prefix Handoff (Model A reads t=0..3 -> O(1) transport -> Model B continues t=4..7 natively!)
                sa_pref = ma.accumulate_state(te_k[:, :4], te_v[:, :4])
                sb_pref_trans = s_frob * torch.einsum("ij,bjk,lk->bil", q_v, sa_pref, q_k)
                sb_handoff = mb.accumulate_state(te_k[:, 4:], te_v[:, 4:], s_init=sb_pref_trans)
                acc_handoff = float((mb.readout_logits(sb_handoff, te_q).argmax(dim=-1) == te_y).float().mean().item())

                # Adversarial Nulls: Random O(d) & Shuffled Document
                gen_n = torch.Generator(device="cpu").manual_seed(sd_a * 1000 + sd_b)
                u_rk, _, vh_rk = torch.linalg.svd(torch.randn((D_HEAD, D_HEAD), generator=gen_n))
                u_rv, _, vh_rv = torch.linalg.svd(torch.randn((D_HEAD, D_HEAD), generator=gen_n))
                sb_rand = s_frob * torch.einsum("ij,bjk,lk->bil", u_rv @ vh_rv, sa_te, u_rk @ vh_rk)
                acc_rand = float((mb.readout_logits(sb_rand, te_q).argmax(dim=-1) == te_y).float().mean().item())

                perm = torch.roll(torch.arange(len(test_docs)), shifts=1)
                acc_shuf = float((mb.readout_logits(s_frob * sb_te_rot[perm], te_q).argmax(dim=-1) == te_y).float().mean().item())

                # 2. Query-Aware SVD Rank Sweep r in {4, 8, 16, 32} (Clean 64-doc Fit & Isotropic Perturbation sigma=0.35)
                # Query subspace in Model B spanned by calibration queries Q_B
                qb_cal = mb.queries(ca_q)
                _, _, vh_q = torch.linalg.svd(qb_cal, full_matrices=False)
                # Note: N_KEYS = 12 distinct keys -> true key/query subspace rank == 12 < 16 < 32!
                rank_clean: Dict[str, Any] = {}
                rank_noisy: Dict[str, Any] = {}

                # Add isotropic perturbation sigma=0.35 to test Theorem 3 state-MSE denoising on orthogonal complement
                noise_e = torch.randn(sb_te_rot.shape, generator=gen_n) * 0.35
                sb_noisy_full = s_frob * sb_te_rot + noise_e
                for rk in RANK_SWEEP:
                    if rk < D_HEAD:
                        u_r = vh_q[: min(rk, vh_q.shape[0]), :].T  # [D, r']
                        p_r = u_r @ u_r.T
                    else:
                        p_r = torch.eye(D_HEAD, dtype=torch.float32)

                    sb_c_proj = torch.einsum("bij,jk->bik", s_frob * sb_te_rot, p_r)
                    acc_c = float((mb.readout_logits(sb_c_proj, te_q).argmax(dim=-1) == te_y).float().mean().item())
                    mse_c = float(((sb_c_proj - sb_te_nat).pow(2)).mean().item())
                    rank_clean[f"r{rk}"] = {"acc": round(acc_c, 4), "state_mse": round(mse_c, 6)}

                    sb_n_proj = torch.einsum("bij,jk->bik", sb_noisy_full, p_r)
                    acc_n = float((mb.readout_logits(sb_n_proj, te_q).argmax(dim=-1) == te_y).float().mean().item())
                    mse_n = float(((sb_n_proj - sb_te_nat).pow(2)).mean().item())
                    rank_noisy[f"r{rk}"] = {"acc": round(acc_n, 4), "state_mse": round(mse_n, 6)}

                # Verify raw subspace rank of trained keys/queries (should be <= N_KEYS = 12 < 32!)
                eff_key_rank = int((torch.linalg.svdvals(mb.keys(all_k_ids)) > 1e-3).sum().item())
                eff_val_rank = int((torch.linalg.svdvals(mb.vals(all_v_ids)) > 1e-3).sum().item())

                pair_out[pkey] = {
                    "scales": {
                        "s_frob": round(s_frob, 6),
                        "s_ols": round(s_ols, 6),
                        "ols_le_frob": s_ols <= s_frob + 1e-6,
                    },
                    "effective_subspace_ranks": {"keys": eff_key_rank, "vals": eff_val_rank},
                    "test_accuracy": {
                        "Native_UpperBound": round(acc_nat, 4),
                        "Raw_Unaligned_Control": round(acc_raw, 4),
                        "Bilinear_Frob_Procrustes": round(acc_frob, 4),
                        "Bilinear_OLS_Procrustes": round(acc_ols, 4),
                        "Prefix_Handoff_Suffix_Continue": round(acc_handoff, 4),
                        "Adversarial_Null_Random_Od": round(acc_rand, 4),
                        "Adversarial_Null_Shuffled_Doc": round(acc_shuf, 4),
                    },
                    "svd_rank_sweep_clean": rank_clean,
                    "svd_rank_sweep_noisy_nullspace": rank_noisy,
                }

    n_p = float(len(pair_out))
    mean_nat = sum(v["test_accuracy"]["Native_UpperBound"] for v in pair_out.values()) / n_p
    mean_raw = sum(v["test_accuracy"]["Raw_Unaligned_Control"] for v in pair_out.values()) / n_p
    mean_frob = sum(v["test_accuracy"]["Bilinear_Frob_Procrustes"] for v in pair_out.values()) / n_p
    mean_ols = sum(v["test_accuracy"]["Bilinear_OLS_Procrustes"] for v in pair_out.values()) / n_p
    mean_ho = sum(v["test_accuracy"]["Prefix_Handoff_Suffix_Continue"] for v in pair_out.values()) / n_p
    mean_rand = sum(v["test_accuracy"]["Adversarial_Null_Random_Od"] for v in pair_out.values()) / n_p
    mean_shuf = sum(v["test_accuracy"]["Adversarial_Null_Shuffled_Doc"] for v in pair_out.values()) / n_p
    mean_noisy_mse_by_r = {
        f"r{rk}": round(sum(v["svd_rank_sweep_noisy_nullspace"][f"r{rk}"]["state_mse"] for v in pair_out.values()) / n_p, 6)
        for rk in RANK_SWEEP
    }
    mean_noisy_acc_by_r = {
        f"r{rk}": round(sum(v["svd_rank_sweep_noisy_nullspace"][f"r{rk}"]["acc"] for v in pair_out.values()) / n_p, 4)
        for rk in RANK_SWEEP
    }
    all_ols_le_frob = all(v["scales"]["ols_le_frob"] for v in pair_out.values())

    return {
        "native_seed_accuracies": native_accs,
        "pairs": pair_out,
        "summary": {
            "mean_native_acc": round(mean_nat, 4),
            "mean_raw_unaligned_acc": round(mean_raw, 4),
            "mean_frob_procrustes_acc": round(mean_frob, 4),
            "mean_ols_procrustes_acc": round(mean_ols, 4),
            "mean_prefix_handoff_acc": round(mean_ho, 4),
            "mean_random_od_null_acc": round(mean_rand, 4),
            "mean_shuffled_doc_null_acc": round(mean_shuf, 4),
            "mean_noisy_nullspace_mse_by_rank": mean_noisy_mse_by_r,
            "mean_noisy_nullspace_acc_by_rank": mean_noisy_acc_by_r,
            "r16_vs_r32_mse_reduction_ratio": round(mean_noisy_mse_by_r["r32"] / max(1e-12, mean_noisy_mse_by_r["r16"]), 4),
            "r16_minus_r32_acc_pp": round(100.0 * (mean_noisy_acc_by_r["r16"] - mean_noisy_acc_by_r["r32"]), 2),
            "sanity_cauchy_schwarz_ols_le_frob": all_ols_le_frob,
            "gate_S123_G1_pass": (mean_frob >= 0.85) and (mean_frob - max(mean_rand, mean_shuf) >= 0.60),
            "gate_S123_G2_state_mse_denoise_pass": (mean_noisy_mse_by_r["r16"] < mean_noisy_mse_by_r["r32"]) and (mean_noisy_acc_by_r["r16"] >= mean_noisy_acc_by_r["r32"]),
        },
    }


def _run_exp2_a5_su2_nonabelian_transport(torch: Any) -> Dict[str, Any]:
    """Experiment 2: Non-Abelian A_5 (L=16, 60 classes) CayleySU2 mid-word handoff & det=+1 vs -1 obstruction."""
    import torch.nn as nn  # type: ignore[import-not-found]
    import torch.nn.functional as F  # type: ignore[import-not-found]

    tbl = build_a5_generators_and_table()
    base_w = torch.tensor(tbl["gens_cayley_w"], dtype=torch.float32)  # [4, 3]

    def _cayley_t(w: Any) -> Any:
        n2 = (w * w).sum(dim=-1, keepdim=True)
        inv = 1.0 / (1.0 + n2)
        return torch.cat(((1.0 - n2) * inv, 2.0 * w * inv), dim=-1)

    def _qmul_t(a: Any, b: Any) -> Any:
        return torch.stack((
            a[..., 0] * b[..., 0] - a[..., 1] * b[..., 1] - a[..., 2] * b[..., 2] - a[..., 3] * b[..., 3],
            a[..., 0] * b[..., 1] + a[..., 1] * b[..., 0] + a[..., 2] * b[..., 3] - a[..., 3] * b[..., 2],
            a[..., 0] * b[..., 2] - a[..., 1] * b[..., 3] + a[..., 2] * b[..., 0] + a[..., 3] * b[..., 1],
            a[..., 0] * b[..., 3] + a[..., 1] * b[..., 2] - a[..., 2] * b[..., 1] + a[..., 3] * b[..., 0],
        ), dim=-1)

    def _qconj_t(q: Any) -> Any:
        return torch.stack((q[..., 0], -q[..., 1], -q[..., 2], -q[..., 3]), dim=-1)

    def _q_to_so3_flat(q: Any) -> Any:
        q0, q1, q2, q3 = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
        return torch.stack((
            1.0 - 2.0 * (q2 * q2 + q3 * q3), 2.0 * (q1 * q2 - q0 * q3), 2.0 * (q1 * q3 + q0 * q2),
            2.0 * (q1 * q2 + q0 * q3), 1.0 - 2.0 * (q1 * q1 + q3 * q3), 2.0 * (q2 * q3 - q0 * q1),
            2.0 * (q1 * q3 - q0 * q2), 2.0 * (q2 * q3 + q0 * q1), 1.0 - 2.0 * (q1 * q1 + q2 * q2),
        ), dim=-1)

    class MicroA5CayleyCell(nn.Module):
        def __init__(self, seed: int) -> None:
            super().__init__()
            gen = torch.Generator(device="cpu").manual_seed(seed + 500)
            # Distinct proper SO(3) seed gauge R_seed (det=+1) rotating the 4 Cayley generator axes!
            u, _, vh = torch.linalg.svd(torch.randn((3, 3), generator=gen))
            r_sd = u @ vh
            if float(torch.linalg.det(r_sd).item()) < 0.0:
                r_sd = u @ torch.diag(torch.tensor([1.0, 1.0, -1.0])) @ vh
            self.register_buffer("r_gauge", r_sd)
            # Generator parameters initialized in this seed's own rotated SO(3) frame (+ tiny noise)
            w_init = base_w @ r_sd.T + torch.randn((4, 3), generator=gen) * 0.015
            self.gen_w = nn.Parameter(w_init)
            self.cls_head = nn.Linear(9, 60)

        def roll_holonomy(self, tok_seq: Any, q_init: Optional[Any] = None) -> Any:
            bsz, seq_l = tok_seq.shape
            qs = _cayley_t(self.gen_w[tok_seq])  # [B, L, 4]
            if q_init is None:
                cur = torch.zeros((bsz, 4), dtype=torch.float32)
                cur[:, 0] = 1.0
            else:
                cur = q_init.clone()
            for t in range(seq_l):
                cur = _qmul_t(cur, qs[:, t, :])
                cur = cur / cur.norm(dim=-1, keepdim=True).clamp_min(1e-8)
            return cur

        def classify_holonomy(self, q_end: Any) -> Any:
            return self.cls_head(_q_to_so3_flat(q_end))

    tr_w, tr_y = build_a5_word_dataset(1200, seed=4004, word_len=A5_LEN)
    te_w, te_y = build_a5_word_dataset(200, seed=5005, word_len=A5_LEN)
    tr_wt = torch.tensor(tr_w, dtype=torch.long)
    tr_yt = torch.tensor(tr_y, dtype=torch.long)
    te_wt = torch.tensor(te_w, dtype=torch.long)
    te_yt = torch.tensor(te_y, dtype=torch.long)

    models: Dict[int, MicroA5CayleyCell] = {}
    native_accs: Dict[str, float] = {}
    for sd in SEEDS:
        torch.manual_seed(sd)
        m = MicroA5CayleyCell(sd)
        opt = torch.optim.AdamW(
            [
                {"params": [m.gen_w], "lr": 0.003},
                {"params": list(m.cls_head.parameters()), "lr": 0.05},
            ]
        )
        rng_i = torch.Generator(device="cpu").manual_seed(sd + 99)
        for _ in range(280):
            idx = torch.randint(0, len(tr_w), (96,), generator=rng_i)
            q_end = m.roll_holonomy(tr_wt[idx])
            loss = F.cross_entropy(m.classify_holonomy(q_end), tr_yt[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
        m.eval()
        with torch.no_grad():
            acc = float((m.classify_holonomy(m.roll_holonomy(te_wt)).argmax(dim=-1) == te_yt).float().mean().item())
        models[sd] = m
        native_accs[f"seed_{sd}"] = round(acc, 4)

    pair_out: Dict[str, Any] = {}
    half = A5_LEN // 2
    with torch.no_grad():
        for sd_a in SEEDS:
            for sd_b in SEEDS:
                if sd_a == sd_b:
                    continue
                ma, mb = models[sd_a], models[sd_b]
                pkey = f"s{sd_a}_to_s{sd_b}"

                # Fit SO(3) (det=+1) vs improper O(3) (det=-1) generator alignment from 4 generator axes
                r_prop, r_improp = _fit_kabsch_so3_torch(torch, ma.gen_w, mb.gen_w)
                u_prop = _so3_to_unit_quat_torch(torch, r_prop).unsqueeze(0)  # [1, 4]
                u_prop_inv = _qconj_t(u_prop)

                # Native Model B full word
                qb_nat = mb.roll_holonomy(te_wt)
                acc_nat = float((mb.classify_holonomy(qb_nat).argmax(dim=-1) == te_yt).float().mean().item())

                # 1. Kabsch SO(3) (det=+1) Mid-Word Prefix Handoff:
                # Model A reads prefix [0..7] -> U_A -> conjugate U_B = u_R U_A u_R^-1 -> Model B reads suffix [8..15]!
                qa_pref = ma.roll_holonomy(te_wt[:, :half])
                qb_pref_prop = _qmul_t(_qmul_t(u_prop, qa_pref), u_prop_inv)
                qb_handoff_prop = mb.roll_holonomy(te_wt[:, half:], q_init=qb_pref_prop)
                acc_prop = float((mb.classify_holonomy(qb_handoff_prop).argmax(dim=-1) == te_yt).float().mean().item())

                # 2. Improper O(3) (det=-1) Reflection Obstruction:
                # Transport Model A's prefix Cayley vector w_pref = q_vec / (1+q_0) via improper R_improp (det=-1)!
                # Because R_improp(a (+) b) == (R_improp b) (+) (R_improp a), non-Abelian word order REVERSES!
                # Handle q0 < 0 sign canonicalization before inverse Cayley
                sign_a = torch.where(qa_pref[:, :1] >= 0.0, 1.0, -1.0)
                qa_pos = qa_pref * sign_a
                w_pref_a = qa_pos[:, 1:] / (1.0 + qa_pos[:, :1]).clamp_min(1e-6)
                qb_pref_improp = _cayley_t(w_pref_a @ r_improp.T)
                qb_handoff_improp = mb.roll_holonomy(te_wt[:, half:], q_init=qb_pref_improp)
                acc_improp = float((mb.classify_holonomy(qb_handoff_improp).argmax(dim=-1) == te_yt).float().mean().item())

                # 3. Abelian RoPE-Style Commutative Sum Control (W14-OBS-1):
                # Ignores non-Abelian path ordering by summing mapped generator vectors w_sum = sum_{t<half} R w_t
                w_pref_sum_b = (ma.gen_w[te_wt[:, :half]] @ r_prop.T).sum(dim=1)
                qb_pref_abel = _cayley_t(w_pref_sum_b)
                qb_handoff_abel = mb.roll_holonomy(te_wt[:, half:], q_init=qb_pref_abel)
                acc_abel = float((mb.classify_holonomy(qb_handoff_abel).argmax(dim=-1) == te_yt).float().mean().item())

                # 4. Random SO(3) Null & Shuffled-Word Null
                gen_r = torch.Generator(device="cpu").manual_seed(sd_a * 2000 + sd_b)
                ur_m, _, vhr_m = torch.linalg.svd(torch.randn((3, 3), generator=gen_r))
                r_rand = ur_m @ vhr_m
                if float(torch.linalg.det(r_rand).item()) < 0.0:
                    r_rand = ur_m @ torch.diag(torch.tensor([1.0, 1.0, -1.0])) @ vhr_m
                u_rand = _so3_to_unit_quat_torch(torch, r_rand).unsqueeze(0)
                qb_pref_rand = _qmul_t(_qmul_t(u_rand, qa_pref), _qconj_t(u_rand))
                acc_rand = float(
                    (mb.classify_holonomy(mb.roll_holonomy(te_wt[:, half:], q_init=qb_pref_rand)).argmax(dim=-1) == te_yt)
                    .float()
                    .mean()
                    .item()
                )

                perm = torch.roll(torch.arange(len(te_w)), shifts=1)
                qb_handoff_shuf = mb.roll_holonomy(te_wt[:, half:], q_init=qb_pref_prop[perm])
                acc_shuf = float((mb.classify_holonomy(qb_handoff_shuf).argmax(dim=-1) == te_yt).float().mean().item())

                pair_out[pkey] = {
                    "det_proper": round(float(torch.linalg.det(r_prop).item()), 4),
                    "det_improper": round(float(torch.linalg.det(r_improp).item()), 4),
                    "handoff_test_accuracy": {
                        "Native_UpperBound": round(acc_nat, 4),
                        "Kabsch_SO3_DetPlus1": round(acc_prop, 4),
                        "Improper_O3_DetMinus1_Obstruction": round(acc_improp, 4),
                        "Abelian_Commutative_Sum_W14_OBS_1": round(acc_abel, 4),
                        "Random_SO3_Null": round(acc_rand, 4),
                        "Shuffled_Word_Null": round(acc_shuf, 4),
                    },
                }

    n_p = float(len(pair_out))
    m_nat = sum(v["handoff_test_accuracy"]["Native_UpperBound"] for v in pair_out.values()) / n_p
    m_prop = sum(v["handoff_test_accuracy"]["Kabsch_SO3_DetPlus1"] for v in pair_out.values()) / n_p
    m_imp = sum(v["handoff_test_accuracy"]["Improper_O3_DetMinus1_Obstruction"] for v in pair_out.values()) / n_p
    m_abel = sum(v["handoff_test_accuracy"]["Abelian_Commutative_Sum_W14_OBS_1"] for v in pair_out.values()) / n_p
    m_rand = sum(v["handoff_test_accuracy"]["Random_SO3_Null"] for v in pair_out.values()) / n_p
    m_shuf = sum(v["handoff_test_accuracy"]["Shuffled_Word_Null"] for v in pair_out.values()) / n_p
    rev_fixed_cnt = count_a5_reversal_fixed_prefixes(te_w, half)
    rev_fixed_rate = round(rev_fixed_cnt / float(len(te_w)), 4)
    rev_exact_match = all(round(v["handoff_test_accuracy"]["Improper_O3_DetMinus1_Obstruction"] * len(te_w)) == rev_fixed_cnt for v in pair_out.values())

    return {
        "native_seed_accuracies": native_accs,
        "pairs": pair_out,
        "summary": {
            "mean_native_acc": round(m_nat, 4),
            "mean_kabsch_so3_det_plus1_acc": round(m_prop, 4),
            "mean_improper_o3_det_minus1_acc": round(m_imp, 4),
            "a5_prefix_rev_eq_self_count": rev_fixed_cnt,
            "a5_prefix_rev_eq_self_rate": rev_fixed_rate,
            "improper_survival_matches_rev_fixed_exact": rev_exact_match,
            "mean_abelian_sum_w14_obs1_acc": round(m_abel, 4),
            "mean_random_so3_null_acc": round(m_rand, 4),
            "mean_shuffled_word_null_acc": round(m_shuf, 4),
            "det_minus1_drop_pp": round(100.0 * (m_prop - m_imp), 2),
            "gate_S123_G3_pass": (m_prop >= 0.95) and ((m_prop - m_imp) >= 0.50) and (max(m_rand, m_shuf) <= 0.10),
        },
    }


def run_cpu_benchmark(out_json: Optional[Path] = None) -> Dict[str, Any]:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    import torch  # type: ignore[import-not-found]

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    t0 = time.perf_counter()

    exp1 = _run_exp1_sfast_assoc_transport(torch)
    exp2 = _run_exp2_a5_su2_nonabelian_transport(torch)

    g1 = bool(exp1["summary"]["gate_S123_G1_pass"])
    g2 = bool(exp1["summary"]["gate_S123_G2_state_mse_denoise_pass"])
    g3 = bool(exp2["summary"]["gate_S123_G3_pass"])
    cs_sanity = bool(exp1["summary"]["sanity_cauchy_schwarz_ols_le_frob"])
    if g1 and g2 and g3 and cs_sanity:
        overall = "CONFIRMED"
    elif g1 or g3:
        overall = "PARTIAL"
    else:
        overall = "FALSIFIED"

    # Compute deterministic canonical payload_sha256 strictly BEFORE attaching wall_seconds!
    payload: Dict[str, Any] = {
        "schema": SCHEMA_BENCH,
        "device": "cpu",
        "seeds": list(SEEDS),
        "rank_sweep": list(RANK_SWEEP),
        "exp1_sfast_woodbury_assoc_recall": exp1,
        "exp2_a5_cayley_su2_nonabelian": exp2,
        "gates": {
            "S123_G1_sfast_cross_seed": g1,
            "S123_G2_svd_state_mse_denoising": g2,
            "S123_G3_a5_so3_det_obstruction": g3,
            "sanity_S123_cauchy_schwarz_ols_le_frob": cs_sanity,
            "overall_verdict": overall,
        },
    }
    payload["payload_sha256"] = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    payload["wall_seconds"] = round(time.perf_counter() - t0, 2)

    if out_json is not None:
        out_json.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.chmod(out_json, 0o644)
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S123 CPU Cross-Seed State Transport Benchmark")
    parser.add_argument("--selftest-stdlib", action="store_true")
    parser.add_argument("--run-cpu", action="store_true")
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.run_cpu:
            res = run_cpu_benchmark(out_json=args.out_json)
        else:
            res = run_stdlib_selftest()
    except BenchTransportError as exc:
        sys.stderr.write(f"FAIL {exc.code}: {exc.detail}\n")
        return 2

    if args.json or args.selftest_stdlib:
        sys.stdout.write(json.dumps(res, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")
    else:
        verdict = res.get("gates", {}).get("overall_verdict", "SELFTEST_PASS")
        sys.stdout.write(f"PASS {res['schema']} verdict={verdict} payload_sha256={res['payload_sha256']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
