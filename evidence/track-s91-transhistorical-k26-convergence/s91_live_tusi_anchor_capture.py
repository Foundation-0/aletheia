#!/usr/bin/env python3
"""Track S91 Live Real-Weight Al-Tusi Counter-Rotating Dual-Loop Anchor Capture (CPU-only).

Reads the frozen trained 2x256 tanh circular predictive-coding Sudoku network
(`demo/models/best.json` + `demo/puzzles.json`) from a read-only clone of
`rel-int/CircularEP` (commit ba2f9b87cc348c0065db27130da20bd2770b8c91) and writes
a zero-float canonical ASCII JSON receipt (`s91_tusi_circularep_live_anchor.json`,
mode 0o600) encoding all 300-puzzle Al-Tusi symmetrization measurements as exact
integers and decimal/scientific strings so downstream pure-Z/Q verification stays
100% stdlib and zero-float.
"""
from __future__ import annotations

import base64
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np

_THIS_DIR = Path(__file__).resolve().parent
_DEFAULT_REPO = Path("/tmp/circularep_ro_s91")
_OUT_PATH = _THIS_DIR / "s91_tusi_circularep_live_anchor.json"
_EXPECTED_COMMIT = "ba2f9b87cc348c0065db27130da20bd2770b8c91"
_EXPECTED_BEST_SHA = "fe5c2e9ba31605345ae25b0000987a6b4d9b9a57224a4c5d15a4d25d0f5b7eda"
_EXPECTED_PUZZLES_SHA = "eed9fb4be46736c1147fdfc292830bedaf5c0f4e640e0c8b2a06d7f12feeba76"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dec_str(val: float, places: int) -> str:
    q = Decimal(10) ** (-places)
    d = Decimal(repr(float(val))).quantize(q, rounding=ROUND_HALF_UP)
    return format(d, f".{places}f")


def _sci_str(val: float, sig: int = 6) -> str:
    return f"{float(val):.{sig}e}"


def _dec_array(obj: dict[str, Any], dtype: Any = np.float64) -> np.ndarray:
    raw = base64.b64decode(obj["b64"])
    arr = np.frombuffer(raw, dtype="<f4").astype(dtype, copy=True)
    if "shape" in obj:
        arr = arr.reshape(obj["shape"])
    return arr


def _power_iter_60(mat: np.ndarray) -> float:
    rng = np.random.default_rng(1)
    v = rng.standard_normal(mat.shape[0])
    v /= np.linalg.norm(v)
    lam_pi = 0.0
    for _ in range(60):
        jv = mat @ v
        lam_pi = float(np.linalg.norm(jv))
        v = jv / (lam_pi + 1e-20)
    return lam_pi


def main() -> int:
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_REPO
    best_path = repo / "demo" / "models" / "best.json"
    puzzles_path = repo / "demo" / "puzzles.json"
    _require(best_path.is_file() and puzzles_path.is_file(), "CircularEP files missing")

    head_ref = (repo / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    if head_ref.startswith("ref: "):
        commit_sha = (repo / ".git" / head_ref[5:]).read_text(encoding="utf-8").strip()
    else:
        commit_sha = head_ref
    best_sha = _sha256_file(best_path)
    puzzles_sha = _sha256_file(puzzles_path)
    _require(commit_sha == _EXPECTED_COMMIT, f"commit mismatch: {commit_sha}")
    _require(best_sha == _EXPECTED_BEST_SHA, f"best.json sha mismatch: {best_sha}")
    _require(puzzles_sha == _EXPECTED_PUZZLES_SHA, f"puzzles.json sha mismatch: {puzzles_sha}")

    best = json.loads(best_path.read_text(encoding="utf-8"))
    puzzles = json.loads(puzzles_path.read_text(encoding="utf-8"))["puzzles"]
    _require(len(puzzles) == 300, f"expected 300 puzzles, got {len(puzzles)}")

    win = _dec_array(best["theta"]["Win"], np.float64)
    bin_ = _dec_array(best["theta"]["bin"], np.float64)
    w1 = _dec_array(best["theta"]["W1"], np.float64)
    b1 = _dec_array(best["theta"]["b1"], np.float64)
    w2 = _dec_array(best["theta"]["W2"], np.float64)
    b2 = _dec_array(best["theta"]["b2"], np.float64)

    sigma_w1 = float(np.linalg.svd(w1, compute_uv=False)[0])
    sigma_w2 = float(np.linalg.svd(w2, compute_uv=False)[0])

    def encode_puz(puz: list[int]) -> np.ndarray:
        x = np.zeros(80, dtype=np.float64)
        for i, val in enumerate(puz):
            x[i * 5 + val] = 1.0
        return x

    def embed_f32(puz: list[int]) -> np.ndarray:
        return (encode_puz(puz) @ win + bin_).astype(np.float32)

    def jacobi_f64(u: np.ndarray, s: np.ndarray, x_inj: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        u_hat = np.tanh(s.astype(np.float64) @ w1 + b1)
        s_hat = np.tanh(u.astype(np.float64) @ w2 + b2 + x_inj.astype(np.float64))
        return u_hat, s_hat

    def energy_f64(u: np.ndarray, s: np.ndarray, x_inj: np.ndarray) -> float:
        u_hat, s_hat = jacobi_f64(u, s, x_inj)
        eu = u.astype(np.float64) - u_hat
        es = s.astype(np.float64) - s_hat
        return 0.5 * float(np.dot(eu, eu) + np.dot(es, es))

    def grad_e_f64(u: np.ndarray, s: np.ndarray, x_inj: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        u_hat, s_hat = jacobi_f64(u, s, x_inj)
        eu = u.astype(np.float64) - u_hat
        es = s.astype(np.float64) - s_hat
        du = eu * (1.0 - u_hat * u_hat)
        ds = es * (1.0 - s_hat * s_hat)
        return eu - ds @ w2.T, es - du @ w1.T

    def run_free_f32(puz: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x_inj = embed_f32(puz)
        u = np.tanh(b1).astype(np.float32)
        s = np.tanh(u.astype(np.float64) @ w2 + b2 + x_inj.astype(np.float64)).astype(np.float32)
        vu = np.zeros_like(u)
        vs = np.zeros_like(s)
        e_val = energy_f64(u, s, x_inj)
        it = 0
        while it < 150 and e_val >= 1e-6:
            gu, gs = grad_e_f64(u, s, x_inj)
            vu = (0.7 * vu - 0.7 * gu.astype(np.float32)).astype(np.float32)
            vs = (0.7 * vs - 0.7 * gs.astype(np.float32)).astype(np.float32)
            u = (u + vu).astype(np.float32)
            s = (s + vs).astype(np.float32)
            it += 1
            e_val = energy_f64(u, s, x_inj)
        return x_inj, u, s

    pi_raw_cx: list[float] = []
    pi_raw_re: list[float] = []
    pi_tusi_cx: list[float] = []
    pi_tusi_re: list[float] = []
    pi_tusi_all: list[float] = []
    rho_raw: list[float] = []
    rho_tusi: list[float] = []
    norm2_raw: list[float] = []
    norm2_tusi: list[float] = []
    nn_raw: list[float] = []
    skew_frac: list[float] = []
    cx_records: list[dict[str, Any]] = []

    tusi_im_max = 0.0
    tusi_nn_dev_max = 0.0
    pyth_fro_err_max = 0.0
    bendixson_viol_max = 0.0
    bendixson_hold_cnt = 0
    twin_h2_block_err_max = 0.0
    skew_real_part_max = 0.0
    rho_tusi_gt_rho_raw_cnt = 0
    rho_tusi_gt_rho_raw_cx_cnt = 0
    norm2_tusi_lt_norm2_raw_cnt = 0
    tusi_contractive_cnt = 0
    cx_improved_cnt = 0

    for idx, entry in enumerate(puzzles):
        puz = entry["puzzle"]
        x_inj, uf, sf = run_free_f32(puz)
        u_h, s_h = jacobi_f64(uf, sf, x_inj)
        a_mat = (1.0 - u_h * u_h)[:, None] * w1.T
        b_mat = (1.0 - s_h * s_h)[:, None] * w2.T
        m_mat = b_mat @ a_mat
        t_mat = 0.5 * (m_mat + m_mat.T)
        k_mat = 0.5 * (m_mat - m_mat.T)

        eigs_m = np.linalg.eigvals(m_mat)
        lam0 = eigs_m[int(np.argmax(np.abs(eigs_m)))]
        rho_m = float(abs(lam0))
        sig_m = float(np.linalg.svd(m_mat, compute_uv=False)[0])
        is_cx = abs(float(lam0.imag)) > 1e-10

        eigs_t_c = np.linalg.eigvals(t_mat)
        tusi_im_max = max(tusi_im_max, float(np.max(np.abs(eigs_t_c.imag))))
        eigs_t = np.linalg.eigvalsh(t_mat)
        rho_t = float(np.max(np.abs(eigs_t)))
        lmax_t = float(eigs_t[-1])
        sig_t = float(np.linalg.svd(t_mat, compute_uv=False)[0])
        tusi_nn_dev_max = max(tusi_nn_dev_max, abs(sig_t / rho_t - 1.0))

        # Exact Bendixson bound: max Re(lambda(M)) <= lambda_max(T_Tusi(M))
        max_re_m = float(np.max(eigs_m.real))
        viol = max_re_m - lmax_t
        bendixson_viol_max = max(bendixson_viol_max, viol)
        if viol <= 1e-12:
            bendixson_hold_cnt += 1

        # Exact Pythagorean Frobenius decomposition ||M||_F^2 = ||T||_F^2 + ||K||_F^2
        mf2 = float(np.sum(m_mat * m_mat))
        tf2 = float(np.sum(t_mat * t_mat))
        kf2 = float(np.sum(k_mat * k_mat))
        pyth_fro_err_max = max(pyth_fro_err_max, abs(mf2 - (tf2 + kf2)))
        skew_frac.append(float(np.sqrt(kf2 / mf2)))

        rho_raw.append(rho_m)
        rho_tusi.append(rho_t)
        norm2_raw.append(sig_m)
        norm2_tusi.append(sig_t)
        nn_raw.append(sig_m / rho_m)

        if rho_t > rho_m:
            rho_tusi_gt_rho_raw_cnt += 1
            if is_cx:
                rho_tusi_gt_rho_raw_cx_cnt += 1
        if sig_t < sig_m:
            norm2_tusi_lt_norm2_raw_cnt += 1
        if rho_t < 1.0:
            tusi_contractive_cnt += 1

        rel_m = abs(_power_iter_60(m_mat) - rho_m) / rho_m
        rel_t = abs(_power_iter_60(t_mat) - rho_t) / rho_t
        pi_tusi_all.append(rel_t)

        if is_cx:
            pi_raw_cx.append(rel_m)
            pi_tusi_cx.append(rel_t)
            if rel_t < rel_m:
                cx_improved_cnt += 1
            cx_records.append(
                {
                    "puzzle_index": idx,
                    "puzzle_id": str(entry.get("id", f"puzzle-{idx:04d}")),
                    "rho_raw": rho_m,
                    "rho_tusi": rho_t,
                    "norm2_raw": sig_m,
                    "pi_err_raw": rel_m,
                    "pi_err_tusi": rel_t,
                }
            )
            if len(cx_records) <= 5:
                # Verify 512x512 H2-conjugated counter-rotating twin-loop block decomposition
                c_blk = 0.5 * np.block([[m_mat, m_mat.T], [m_mat.T, m_mat]])
                inv_rt2 = np.sqrt(0.5)
                i256 = np.eye(256, dtype=np.float64)
                h2_blk = inv_rt2 * np.block([[i256, i256], [i256, -i256]])
                diag_blk = h2_blk @ c_blk @ h2_blk
                target = np.block([[t_mat, np.zeros((256, 256))], [np.zeros((256, 256)), k_mat]])
                twin_h2_block_err_max = max(twin_h2_block_err_max, float(np.max(np.abs(diag_blk - target))))
                eigs_k = np.linalg.eigvals(k_mat)
                skew_real_part_max = max(skew_real_part_max, float(np.max(np.abs(eigs_k.real))))
        else:
            pi_raw_re.append(rel_m)
            pi_tusi_re.append(rel_t)

    _require(len(pi_raw_cx) == 39 and len(pi_raw_re) == 261, "unexpected complex/real split")
    med_raw_cx = float(np.median(pi_raw_cx))
    med_raw_re = float(np.median(pi_raw_re))
    med_tusi_cx = float(np.median(pi_tusi_cx))
    med_tusi_re = float(np.median(pi_tusi_re))

    cx_records.sort(key=lambda r: (-r["pi_err_raw"], r["puzzle_index"]))
    top5_cx = [
        {
            "puzzle_index": int(r["puzzle_index"]),
            "puzzle_id": str(r["puzzle_id"]),
            "rho_raw_dec6": _dec_str(r["rho_raw"], 6),
            "rho_tusi_dec6": _dec_str(r["rho_tusi"], 6),
            "norm2_raw_dec6": _dec_str(r["norm2_raw"], 6),
            "pi_err_raw_dec6": _dec_str(r["pi_err_raw"], 6),
            "pi_err_tusi_sci": _sci_str(r["pi_err_tusi"], 6),
        }
        for r in cx_records[:5]
    ]

    anchor = {
        "schema_version": "aletheia.track_s91.tusi_circularep_live_anchor.v1",
        "track_id": "TRACK-S91-TRANSHISTORICAL-K26-CONVERGENCE",
        "upstream": {
            "repo": "rel-int/CircularEP",
            "commit_sha": commit_sha,
            "best_json_sha256": best_sha,
            "puzzles_json_sha256": puzzles_sha,
            "sigma_W1_dec9": _dec_str(sigma_w1, 9),
            "sigma_W2_dec9": _dec_str(sigma_w2, 9),
            "n_puzzles": 300,
            "hidden_dim": 256,
        },
        "tusi_dual_loop_300_puzzles": {
            "raw_complex_dominant_count": len(pi_raw_cx),
            "raw_real_dominant_count": len(pi_raw_re),
            "tusi_complex_dominant_count": 0,
            "tusi_max_abs_imag_sci": _sci_str(tusi_im_max, 6),
            "tusi_max_normality_dev_sci": _sci_str(tusi_nn_dev_max, 6),
            "pythagorean_fro_max_err_sci": _sci_str(pyth_fro_err_max, 6),
            "bendixson_bound_verified_count": bendixson_hold_cnt,
            "bendixson_max_violation_sci": _sci_str(max(0.0, bendixson_viol_max), 6),
            "twin_h2_block_diag_max_err_sci": _sci_str(twin_h2_block_err_max, 6),
            "skew_curl_max_abs_real_eig_sci": _sci_str(skew_real_part_max, 6),
            "raw_pi60_cx_median_dec6": _dec_str(med_raw_cx, 6),
            "raw_pi60_cx_p90_dec6": _dec_str(float(np.percentile(pi_raw_cx, 90)), 6),
            "raw_pi60_cx_max_dec6": _dec_str(float(np.max(pi_raw_cx)), 6),
            "raw_pi60_re_median_sci": _sci_str(med_raw_re, 6),
            "tusi_pi60_cx_median_sci": _sci_str(med_tusi_cx, 6),
            "tusi_pi60_cx_p90_sci": _sci_str(float(np.percentile(pi_tusi_cx, 90)), 6),
            "tusi_pi60_cx_max_dec6": _dec_str(float(np.max(pi_tusi_cx)), 6),
            "tusi_pi60_re_median_sci": _sci_str(med_tusi_re, 6),
            "tusi_pi60_all_median_sci": _sci_str(float(np.median(pi_tusi_all)), 6),
            "tusi_cx_improved_count": cx_improved_cnt,
            "cx_median_error_reduction_sci": _sci_str(med_raw_cx / med_tusi_cx, 6),
            "raw_cx_vs_re_disparity_sci": _sci_str(med_raw_cx / med_raw_re, 6),
            "tusi_cx_vs_re_disparity_dec4": _dec_str(med_tusi_cx / med_tusi_re, 4),
            "disparity_collapse_factor_sci": _sci_str((med_raw_cx / med_raw_re) / (med_tusi_cx / med_tusi_re), 6),
            "raw_rho_min_dec6": _dec_str(float(np.min(rho_raw)), 6),
            "raw_rho_median_dec6": _dec_str(float(np.median(rho_raw)), 6),
            "raw_rho_max_dec6": _dec_str(float(np.max(rho_raw)), 6),
            "tusi_rho_min_dec6": _dec_str(float(np.min(rho_tusi)), 6),
            "tusi_rho_median_dec6": _dec_str(float(np.median(rho_tusi)), 6),
            "tusi_rho_max_dec6": _dec_str(float(np.max(rho_tusi)), 6),
            "raw_norm2_min_dec6": _dec_str(float(np.min(norm2_raw)), 6),
            "raw_norm2_median_dec6": _dec_str(float(np.median(norm2_raw)), 6),
            "raw_norm2_max_dec6": _dec_str(float(np.max(norm2_raw)), 6),
            "raw_non_normality_median_dec6": _dec_str(float(np.median(nn_raw)), 6),
            "skew_fro_fraction_min_dec6": _dec_str(float(np.min(skew_frac)), 6),
            "skew_fro_fraction_median_dec6": _dec_str(float(np.median(skew_frac)), 6),
            "skew_fro_fraction_max_dec6": _dec_str(float(np.max(skew_frac)), 6),
            "law5_rho_tusi_gt_rho_raw_count": rho_tusi_gt_rho_raw_cnt,
            "law5_rho_tusi_gt_rho_raw_cx_count": rho_tusi_gt_rho_raw_cx_cnt,
            "law5_norm2_tusi_lt_norm2_raw_count": norm2_tusi_lt_norm2_raw_cnt,
            "law5_tusi_contractive_count": tusi_contractive_cnt,
            "law5_cs21_jvp_cost_multiplier": 2,
            "top5_complex_curl_witnesses": top5_cx,
        },
    }

    raw = (json.dumps(anchor, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    tmp = _OUT_PATH.with_name(f".{_OUT_PATH.name}.{os.getpid()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, _OUT_PATH)
    print(f"WROTE {_OUT_PATH.name} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
