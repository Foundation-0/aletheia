#!/usr/bin/env python3
"""R5 adversarial + positive verification suite for Track S113 evidence bundle.

100% pure Python standard library, zero bare asserts, deterministic across all three
isolated Python modes (-I -B, -I -O -B, -I -B -W error). Also dynamically executes
dsp_harnesses/{test_s113_r5.py, test_s113_blind_anomaly_hunter.py} whenever numpy
and scipy are installed in the active interpreter.
"""
from __future__ import annotations

import ast
import contextlib
from fractions import Fraction
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import s113_multisensor_audit as audit  # noqa: E402


def _ensure(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _resign_cert(cert: dict) -> dict:
    out = json.loads(audit.canonical_json(cert))
    payload_sha = audit.sha256_text(audit.canonical_json(out["payload"]))
    out["payload_sha256"] = payload_sha
    unsigned = {
        "schema": out["schema"],
        "prereg_id": out["prereg_id"],
        "payload": out["payload"],
        "payload_sha256": payload_sha,
    }
    out["certificate_sha256"] = audit.sha256_text(audit.canonical_json(unsigned))
    return out


def _resign_blind(receipt: dict) -> dict:
    out = json.loads(audit.canonical_json(receipt))
    unsigned = {k: v for k, v in out.items() if k != "receipt_payload_sha256"}
    out["receipt_payload_sha256"] = audit.sha256_text(audit.canonical_json(unsigned))
    return out


def _expect_audit_error(fn, expected_code: str) -> None:
    raised_code = None
    try:
        fn()
    except audit.S113AuditError as exc:
        raised_code = exc.code
    _ensure(
        raised_code == expected_code,
        f"Expected S113AuditError({expected_code!r}), got {raised_code!r}",
    )


class TestS113MultisensorAuditR5(unittest.TestCase):
    def test_01_live_certificate_prereg_pin_and_cli_check(self) -> None:
        cert_path = _HERE / "s113_multisensor_certificate.json"
        blind_path = _HERE / "s113_blind_anomalies_receipt.json"
        prereg_path = _HERE / "PREREG_S113_MULTISENSOR_SILICON_PHYSICS.md"

        cert = audit.load_strict_json_file(cert_path)
        res = audit.verify_certificate_dict(cert)
        _ensure(res["ok"] is True, "Live certificate failed verification")
        _ensure(
            res["payload_sha256"] == "e8e3da5f45cb3331e0b29ac51d08496d6c3ef1b17e9bf27c9e5ad213908ac574",
            f"Unexpected payload_sha256: {res['payload_sha256']}",
        )
        _ensure(
            res["certificate_sha256"] == "107bcb46dfe218926b2a260895773e53b7d806bd55f5a7e760e085287ead410b",
            f"Unexpected certificate_sha256: {res['certificate_sha256']}",
        )

        blind = audit.load_strict_json_file(blind_path)
        bres = audit.verify_blind_receipt_dict(
            blind,
            prereg_path if prereg_path.is_file() else None,
            expected_cert_payload_sha256=res["payload_sha256"],
            expected_manifest_digests=cert["payload"].get("manifest_digests"),
        )
        _ensure(
            bres["ok"] is True
            and bres["total_surviving_anomalies"] == 0
            and bres["holm_rejected"] == 421
            and bres["receipt_payload_sha256"] == "ff21fd7bfe4662018e071af49d7a68b63093f0dd72b4daae2de5acd2fbf2bb31",
            f"Unexpected blind result: {bres}",
        )

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = audit.main(["--check", str(cert_path), "--json"])
        _ensure(rc == 0, f"CLI --check exited {rc}")
        parsed = json.loads(buf.getvalue())
        _ensure(
            parsed["ok"] is True
            and parsed["blind_surviving_anomalies"] == 0
            and parsed["blind_holm_rejected"] == 421,
            f"CLI output mismatch: {parsed}",
        )

    def test_02_pure_q_schur_krein_haynsworth_dark_mode_and_k4_hodge1(self) -> None:
        # 1) Indefinite 3x3 matrix with zero diagonal requiring 2x2 off-diagonal Bunch-Kaufman pivot -> (1, 1, 1)
        indef: audit.QMat = (
            (Fraction(0), Fraction(2), Fraction(0)),
            (Fraction(2), Fraction(0), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(0)),
        )
        _ensure(audit.q_krein_inertia(indef) == (1, 1, 1), "2x2 Bunch-Kaufman pivot inertia failed")

        # 2) Exact integer covariance + singular constant column (Dark-Mode dim_dark=1) + Haynsworth additivity
        samples = [
            [2, 5, 7, 11],
            [4, 3, 7, 9],
            [6, 8, 7, 18],
            [8, 4, 7, 14],
            [10, 9, 7, 23],
            [12, 1, 7, 13],
        ]
        sigma = audit.build_exact_q_gram_covariance(samples)
        _ensure(audit.q_is_symmetric(sigma), "Exact Q covariance must be symmetric")
        dm = audit.q_dark_mode_shadow(sigma, (0, 1, 2))
        _ensure(dm["dim_dark"] == 1 and dm["r_cross"] == 0, f"Expected dim_dark=1, r_cross=0, got {dm}")
        schur = audit.q_schur_pushforward(sigma, (0, 1, 2))
        in_full = audit.q_krein_inertia(sigma)
        in_oo = audit.q_krein_inertia(audit.q_submat(sigma, (0, 1, 2), (0, 1, 2)))
        in_sc = audit.q_krein_inertia(schur)
        _ensure(
            in_full == (in_oo[0] + in_sc[0], in_oo[1] + in_sc[1], in_oo[2] + in_sc[2]),
            f"Haynsworth additivity failed: {in_full} != {in_oo} + {in_sc}",
        )

        # 3) K_4 Hodge-1 exact coboundary (0/1) vs pure curl (> 1/2)
        h_zero = audit.q_k4_hodge1_obstruction({
            "ch0_ch1": 12.0, "ch0_ch2": 35.0, "ch0_ch3": 80.0,
            "ch1_ch2": 23.0, "ch1_ch3": 68.0, "ch2_ch3": 45.0,
        })
        _ensure(h_zero["kappa_h1_exact_q"] == "0/1", f"Expected 0/1 coboundary, got {h_zero}")
        h_curl = audit.q_k4_hodge1_obstruction({
            "ch0_ch1": 50.0, "ch1_ch2": 50.0, "ch0_ch2": -50.0,
            "ch0_ch3": 0.0, "ch1_ch3": 0.0, "ch2_ch3": 0.0,
        })
        _ensure(audit.str_to_frac(h_curl["kappa_h1_exact_q"]) > Fraction(1, 2), f"Expected >1/2 curl, got {h_curl}")

        # 4) Exact-Q guard failures (matrix shape, symmetry, singularity, bit overflow, missing edge)
        _ensure(audit._literal_denotes_exact_zero("0.0") is True, "0.0 must be exact zero")
        _ensure(audit._literal_denotes_exact_zero("not-a-number") is False, "bad literal must not be exact zero")
        _ensure(audit.q_is_symmetric(()) is False, "empty matrix must not be symmetric")
        _ensure(audit.q_is_symmetric(((Fraction(1),), (Fraction(1), Fraction(2)))) is False, "ragged matrix must not be symmetric")
        _expect_audit_error(lambda: audit.frac_to_str(1), "BAD_FRACTION")  # type: ignore[arg-type]
        _expect_audit_error(lambda: audit.frac_to_str(Fraction(1 << (audit.MAX_SERIALIZED_INT_BITS + 5), 1)), "FRACTION_BIT_OVERFLOW")
        _expect_audit_error(lambda: audit.str_to_frac(123), "BAD_FRAC_STR")  # type: ignore[arg-type]
        _expect_audit_error(lambda: audit.str_to_frac("123"), "BAD_FRAC_STR")
        _expect_audit_error(lambda: audit.str_to_frac("1/2/3"), "BAD_FRAC_STR")
        _expect_audit_error(lambda: audit.str_to_frac("a/b"), "BAD_FRAC_STR")
        _expect_audit_error(lambda: audit.str_to_frac(f"{1 << (audit.MAX_SERIALIZED_INT_BITS + 5)}/1"), "FRACTION_BIT_OVERFLOW")
        _expect_audit_error(lambda: audit.q_mul(audit.q_eye(2), audit.q_eye(3)), "QMUL_SHAPE")
        _expect_audit_error(lambda: audit.q_solve(audit.q_eye(2), audit.q_eye(3)), "QSOLVE_SHAPE")
        _expect_audit_error(lambda: audit.q_solve(audit.q_zeros(2, 2), audit.q_eye(2)), "QSINGULAR")
        non_sym: audit.QMat = ((Fraction(1), Fraction(2)), (Fraction(0), Fraction(1)))
        _expect_audit_error(lambda: audit.q_pinv_sym(non_sym), "QNOT_SYM")
        _expect_audit_error(lambda: audit.q_krein_inertia(non_sym), "QNOT_SYM")
        _expect_audit_error(lambda: audit.q_schur_pushforward(non_sym, (0,)), "QNOT_SYM")
        _expect_audit_error(lambda: audit.q_schur_pushforward(audit.q_eye(2), (0, 1)), "QSCHUR_IDX")
        _expect_audit_error(lambda: audit.build_exact_q_gram_covariance([[1, 2], [3, 4]]), "H5_TOO_FEW_WINDOWS")
        _expect_audit_error(lambda: audit.build_exact_q_gram_covariance([[1], [2], [3], [4]]), "H5_BAD_DIM")
        _expect_audit_error(lambda: audit.build_exact_q_gram_covariance([[1, True], [2, 3], [4, 5], [6, 7]]), "H5_NON_INT")  # type: ignore[list-item]
        _expect_audit_error(lambda: audit.q_k4_hodge1_obstruction({"ch0_ch1": 1.0}), "K4_MISSING_EDGE")

    def test_03_refuse_tampered_hashes_and_strict_json_violations(self) -> None:
        base = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")

        bad_payload = json.loads(audit.canonical_json(base))
        bad_payload["payload"]["seed"] = 999999
        _expect_audit_error(lambda: audit.verify_certificate_dict(bad_payload), "PAYLOAD_HASH_MISMATCH")

        bad_cert = _resign_cert(bad_payload)
        bad_cert["certificate_sha256"] = "0" * 64
        _expect_audit_error(lambda: audit.verify_certificate_dict(bad_cert), "CERT_HASH_MISMATCH")

        bad_schema = json.loads(audit.canonical_json(base))
        bad_schema["schema"] = "bad.schema"
        _expect_audit_error(lambda: audit.verify_certificate_dict(bad_schema), "BAD_SCHEMA")

        bad_prereg = json.loads(audit.canonical_json(base))
        bad_prereg["prereg_id"] = "PREREG-OTHER"
        _expect_audit_error(lambda: audit.verify_certificate_dict(bad_prereg), "BAD_PREREG")

        bad_pl_type = json.loads(audit.canonical_json(base))
        bad_pl_type["payload"] = []
        _expect_audit_error(lambda: audit.verify_certificate_dict(bad_pl_type), "MISSING_PAYLOAD")

        bad_av = json.loads(audit.canonical_json(base))
        bad_av["payload"]["raw_av_staged_count"] = 1
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(bad_av)), "RAW_AV_NONZERO")

        empty_mods = json.loads(audit.canonical_json(base))
        empty_mods["payload"]["modules"] = {}
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(empty_mods)), "EMPTY_MODULES")

        _expect_audit_error(lambda: audit.parse_strict_json_text("   "), "EMPTY_JSON")
        _expect_audit_error(lambda: audit.parse_strict_json_text("{bad"), "JSON_SYNTAX_ERROR")
        _expect_audit_error(lambda: audit.parse_strict_json_text("[1, 2]"), "JSON_NOT_OBJECT")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": 1.5}', allow_float=False), "JSON_FLOAT_FORBIDDEN")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": 1e400}'), "JSON_FLOAT_NOT_FINITE")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": 1, "a": 2}'), "JSON_DUPLICATE_KEY")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": NaN}'), "JSON_CONSTANT_FORBIDDEN")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": Infinity}'), "JSON_CONSTANT_FORBIDDEN")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": 1e-400}'), "JSON_FLOAT_UNDERFLOW")
        _expect_audit_error(lambda: audit.load_strict_json_file(_HERE / "nonexistent_file.json"), "FILE_NOT_FOUND")
        with tempfile.TemporaryDirectory() as td:
            crlf_p = Path(td) / "crlf.json"
            crlf_p.write_bytes(b'{"a": 1}\r\n')
            _expect_audit_error(lambda: audit.load_strict_json_file(crlf_p), "CRLF_FORBIDDEN")

    def test_04_refuse_tampered_exact_q_algebra_and_haynsworth_spoof(self) -> None:
        base = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")

        # Non-reduced fraction string
        t_nonred = json.loads(audit.canonical_json(base))
        t_nonred["payload"]["modules"]["H5"]["rapl_dark_r2_given_sensors_exact_q"] = "2/4"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_nonred)), "NONCANONICAL_FRAC_STR")

        # Non-symmetric H5 Schur matrix
        t_nonsym = json.loads(audit.canonical_json(base))
        t_nonsym["payload"]["modules"]["H5"]["sigma_pp_exact_q"][0][1] = "1/1"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_nonsym)), "H5_CERT_NONSYM")

        # Tampered Schur inertia list
        t_in = json.loads(audit.canonical_json(base))
        t_in["payload"]["modules"]["H5"]["krein_inertia_schur_pos_zero_neg"] = [2, 1, 0]
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_in)), "H5_INERTIA_MISMATCH")

        # Negative Krein inertia in Schur matrix
        t_neg = json.loads(audit.canonical_json(base))
        t_neg["payload"]["modules"]["H5"]["schur_complement_pp_exact_q"] = [
            ["-1/1", "0/1", "0/1"],
            ["0/1", "1/1", "0/1"],
            ["0/1", "0/1", "1/1"],
        ]
        t_neg["payload"]["modules"]["H5"]["krein_inertia_schur_pos_zero_neg"] = [2, 0, 1]
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_neg)), "H5_SCHUR_NEGATIVE")

        # Tampered Haynsworth flag
        t_hflag = json.loads(audit.canonical_json(base))
        t_hflag["payload"]["modules"]["H5"]["haynsworth_inertia_additivity_exact"] = False
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_hflag)), "H5_HAYNSWORTH_FLAG")

        # Tampered R^2_Q
        t_r2 = json.loads(audit.canonical_json(base))
        t_r2["payload"]["modules"]["H5"]["rapl_dark_r2_given_sensors_exact_q"] = "1/2"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_r2)), "H5_R2_Q_MISMATCH")

        # Tampered incremental R^2_Q
        t_inc = json.loads(audit.canonical_json(base))
        t_inc["payload"]["modules"]["H5"]["incremental_multisensor_dark_r2_exact_q"] = "1/100"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_inc)), "H5_INCREMENTAL_Q_MISMATCH")

        # Broken Haynsworth inertia additivity
        t_hay = json.loads(audit.canonical_json(base))
        t_hay["payload"]["modules"]["H5"]["krein_inertia_full_pos_zero_neg"] = [12, 1, 0]
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_hay)), "H5_HAYNSWORTH_CERT_FAIL")

        # Tampered K_4 Hodge-1 rational obstruction (E1a and E2a)
        t_k4 = json.loads(audit.canonical_json(base))
        t_k4["payload"]["confirmatory_phases"]["E1"]["e1a_cocycle_and_dispersion"]["core_pinning_3001hz"]["CORE0_3001HZ"]["broadband_hodge1_obstruction"]["kappa_h1_exact_q"] = "1/3"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_k4)), "K4_HODGE1_MISMATCH")

        t_k4_e2 = json.loads(audit.canonical_json(base))
        e2a = t_k4_e2["payload"]["confirmatory_phases"]["E2"]["e2a_cpu_vs_gpu_triangulation_and_imd"]
        first_e2a = next(k for k, v in e2a.items() if isinstance(v, dict) and "broadband_hodge1_obstruction" in v)
        e2a[first_e2a]["broadband_hodge1_obstruction"]["kappa_h1_exact_q"] = "1/3"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(t_k4_e2)), "K4_HODGE1_MISMATCH")

    def test_05_refuse_prereg_verdict_goalpost_shifting_and_h1_holm_spoofs(self) -> None:
        base = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")

        # 1) Payload-level prereg N, verdict_summary type, and deviation note guards
        bad_vsum_type = json.loads(audit.canonical_json(base))
        bad_vsum_type["payload"]["verdict_summary"] = []
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(bad_vsum_type)), "MISSING_VERDICT_SUMMARY")

        bad_pn = json.loads(audit.canonical_json(base))
        bad_pn["payload"]["h1_prereg_n_surrogates"] = 2000
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(bad_pn)), "PREREG_N_MISMATCH")

        bad_dev = json.loads(audit.canonical_json(base))
        bad_dev["payload"]["prereg_deviation_note"] = ""
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(bad_dev)), "PREREG_DEVIATION_MISSING")

        # 2) H1 strict enumeration, N=500 (no OR-bypass), carrier Holm recompute, min_holm_p, passes_null_gate, lag & tau
        h1_vsum = json.loads(audit.canonical_json(base))
        h1_vsum["payload"]["verdict_summary"]["H1"] = "CONFIRMED_H1_EMI"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_vsum)), "VERDICT_SUMMARY_MISMATCH")

        h1_bad_enum = json.loads(audit.canonical_json(base))
        h1_bad_enum["payload"]["modules"]["H1"]["verdict"] = "CONFIRMED_MIXED_FAST_COUPLING"
        h1_bad_enum["payload"]["verdict_summary"]["H1"] = "CONFIRMED_MIXED_FAST_COUPLING"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_bad_enum)), "H1_VERDICT_NOT_ENUMERATED")

        # H1_N_NOT_PREREG must reject n_surrogates=2000 EVEN WHEN posthoc_n2000_exploratory is present
        h1_bad_n = json.loads(audit.canonical_json(base))
        h1_bad_n["payload"]["modules"]["H1"]["n_surrogates"] = 2000
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_bad_n)), "H1_N_NOT_PREREG")

        # Missing prime_carriers / zero present carriers / missing p_holm_n500
        h1_empty_c = json.loads(audit.canonical_json(base))
        h1_empty_c["payload"]["modules"]["H1"]["prime_carriers"] = {}
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_empty_c)), "H1_MISSING_CARRIERS")

        h1_nopres = json.loads(audit.canonical_json(base))
        for c in h1_nopres["payload"]["modules"]["H1"]["prime_carriers"].values():
            c["present"] = False
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_nopres)), "H1_NO_PRESENT_CARRIERS")

        h1_miss_p = json.loads(audit.canonical_json(base))
        del h1_miss_p["payload"]["modules"]["H1"]["prime_carriers"]["3001Hz"]["p_holm_n500"]
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_miss_p)), "H1_MISSING_N500_P")

        # Boundary: single present carrier (len == 1) and exact 1e-6 tolerance on carrier/min Holm + EMI tau edges (0.0 & 2.0)
        for edge_tau in (0.0, 2.0):
            h1_edge = json.loads(audit.canonical_json(base))
            h1_edge["payload"]["modules"]["H1"]["prime_carriers"] = {
                "3001Hz": {"present": True, "p_raw_n500": 0.0, "p_holm_n500": 1e-6}
            }
            h1_edge["payload"]["modules"]["H1"]["min_holm_p"] = 1e-6
            h1_edge["payload"]["modules"]["H1"]["prbs7_p"] = 0.002
            h1_edge["payload"]["modules"]["H1"]["passes_null_gate"] = True
            h1_edge["payload"]["modules"]["H1"]["hf_6_22khz_max_abs_tau_us"] = edge_tau
            h1_edge["payload"]["modules"]["H1"]["verdict"] = "CONFIRMED_H1_EMI"
            h1_edge["payload"]["verdict_summary"]["H1"] = "CONFIRMED_H1_EMI"
            ok_edge = audit.verify_certificate_dict(_resign_cert(h1_edge))
            _ensure(ok_edge["ok"] is True, f"EMI edge tau={edge_tau} must pass")

        # Exact boundary prbs7_p == 0.005 must NOT satisfy prbs_p < 0.005
        h1_prbs_eq = json.loads(audit.canonical_json(base))
        h1_prbs_eq["payload"]["modules"]["H1"]["prime_carriers"] = {
            "3001Hz": {"present": True, "p_raw_n500": 0.002, "p_holm_n500": 0.002}
        }
        h1_prbs_eq["payload"]["modules"]["H1"]["min_holm_p"] = 0.002
        h1_prbs_eq["payload"]["modules"]["H1"]["prbs7_p"] = 0.005
        h1_prbs_eq["payload"]["modules"]["H1"]["passes_null_gate"] = True
        h1_prbs_eq["payload"]["modules"]["H1"]["hf_6_22khz_max_abs_tau_us"] = 1.0
        h1_prbs_eq["payload"]["modules"]["H1"]["verdict"] = "CONFIRMED_H1_EMI"
        h1_prbs_eq["payload"]["verdict_summary"]["H1"] = "CONFIRMED_H1_EMI"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_prbs_eq)), "H1_LAG_NOT_MEASURED")

        # Carrier p_holm_n500 tampered (recomputation catches it)
        h1_bad_ch = json.loads(audit.canonical_json(base))
        h1_bad_ch["payload"]["modules"]["H1"]["prime_carriers"]["3001Hz"]["p_holm_n500"] = 0.0029985
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_bad_ch)), "H1_CARRIER_HOLM_MISMATCH")

        # min_holm_p tampered (recomputation catches it)
        h1_bad_min = json.loads(audit.canonical_json(base))
        h1_bad_min["payload"]["modules"]["H1"]["min_holm_p"] = 0.0029985
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_bad_min)), "H1_MIN_HOLM_MISMATCH")

        # Hand-edited passes_null_gate=True under FALSIFIED must fail closed
        h1_hand_gate = json.loads(audit.canonical_json(base))
        h1_hand_gate["payload"]["modules"]["H1"]["passes_null_gate"] = True
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_hand_gate)), "H1_PASSES_NULL_GATE_MISMATCH")

        # CONFIRMED_H1_EMI despite failing N=500 gate
        h1_spoof = json.loads(audit.canonical_json(base))
        h1_spoof["payload"]["modules"]["H1"]["verdict"] = "CONFIRMED_H1_EMI"
        h1_spoof["payload"]["verdict_summary"]["H1"] = "CONFIRMED_H1_EMI"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_spoof)), "H1_GATE_SPOOF")

        # CONFIRMED_H1_EMI with passing carrier Holm but unmeasured PRBS lag
        h1_nolag = json.loads(audit.canonical_json(base))
        for k, c in h1_nolag["payload"]["modules"]["H1"]["prime_carriers"].items():
            c["p_raw_n500"] = 0.0005
            c["p_holm_n500"] = 0.003
        h1_nolag["payload"]["modules"]["H1"]["min_holm_p"] = 0.003
        h1_nolag["payload"]["modules"]["H1"]["passes_null_gate"] = True
        h1_nolag["payload"]["modules"]["H1"]["verdict"] = "CONFIRMED_H1_EMI"
        h1_nolag["payload"]["verdict_summary"]["H1"] = "CONFIRMED_H1_EMI"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_nolag)), "H1_LAG_NOT_MEASURED")

        # CONFIRMED_H1_EMI with measured PRBS lag but airborne tau=250 us -> H1_TAU_BAND_MISMATCH
        h1_bad_tau = json.loads(audit.canonical_json(h1_nolag))
        h1_bad_tau["payload"]["modules"]["H1"]["prbs7_p"] = 0.001996
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_bad_tau)), "H1_TAU_BAND_MISMATCH")

        # FALSIFIED despite passing PRBS gate -> H1_FALSE_NEGATIVE
        h1_fn = json.loads(audit.canonical_json(base))
        h1_fn["payload"]["modules"]["H1"]["prbs7_p"] = 0.001996
        h1_fn["payload"]["modules"]["H1"]["passes_null_gate"] = True
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(h1_fn)), "H1_FALSE_NEGATIVE")

        # 3) H2..H5 + E1b + E1c + E2b verdict spoof + verdict_summary mismatch checks
        for mod_key, err_code in (
            ("H2", "H2_GATE_SPOOF"),
            ("H3", "H3_GATE_SPOOF"),
            ("H4", "H4_GATE_SPOOF"),
            ("H5", "H5_GATE_SPOOF"),
        ):
            vmm = json.loads(audit.canonical_json(base))
            vmm["payload"]["verdict_summary"][mod_key] = "CONFIRMED"
            _expect_audit_error(lambda s=vmm: audit.verify_certificate_dict(_resign_cert(s)), "VERDICT_SUMMARY_MISMATCH")

            spoof = json.loads(audit.canonical_json(base))
            spoof["payload"]["modules"][mod_key]["verdict"] = "CONFIRMED"
            spoof["payload"]["verdict_summary"][mod_key] = "CONFIRMED"
            _expect_audit_error(lambda s=spoof: audit.verify_certificate_dict(_resign_cert(s)), err_code)

        vmm_e1b = json.loads(audit.canonical_json(base))
        vmm_e1b["payload"]["verdict_summary"]["H3_E1b_IR_1009HZ_OOS"] = "CONFIRMED_REPLICATED"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(vmm_e1b)), "E1B_SUMMARY_MISMATCH")

        spoof_e1b = json.loads(audit.canonical_json(base))
        spoof_e1b["payload"]["confirmatory_phases"]["E1"]["e1b_ir_1009hz_replication"]["verdict"] = "CONFIRMED_REPLICATED"
        spoof_e1b["payload"]["verdict_summary"]["H3_E1b_IR_1009HZ_OOS"] = "CONFIRMED_REPLICATED"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(spoof_e1b)), "E1B_GATE_SPOOF")

        vmm_e1c = json.loads(audit.canonical_json(base))
        vmm_e1c["payload"]["verdict_summary"]["H4_E1c_LINEAR_GAMMA100"] = "CONFIRMED"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(vmm_e1c)), "E1C_SUMMARY_MISMATCH")

        spoof_e1c = json.loads(audit.canonical_json(base))
        spoof_e1c["payload"]["confirmatory_phases"]["E1"]["e1c_linear_gamma100_ptc_and_e1d_thermal"]["verdict"] = "CONFIRMED"
        spoof_e1c["payload"]["verdict_summary"]["H4_E1c_LINEAR_GAMMA100"] = "CONFIRMED"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(spoof_e1c)), "E1C_GATE_SPOOF")

        spoof_e2b = json.loads(audit.canonical_json(base))
        spoof_e2b["payload"]["confirmatory_phases"]["E2"]["e2b_high_wattage_rolling_shutter"]["verdict"] = "CONFIRMED"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(spoof_e2b)), "E2B_GATE_SPOOF")

    def test_06_refuse_blind_receipt_holm_recompute_c2_c6_and_binding_tamper(self) -> None:
        adj = audit.holm_bonferroni_list([0.01, 0.001, 0.02, 0.001])
        _ensure(adj == [0.02, 0.004, 0.02, 0.004], f"Holm step-down mismatch: {adj}")

        base_c = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")
        base_b = audit.load_strict_json_file(_HERE / "s113_blind_anomalies_receipt.json")

        # 1) Tampered self-hash (unsigned edit)
        b_hash = json.loads(audit.canonical_json(base_b))
        b_hash["total_surviving_anomalies"] = 99
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(b_hash), "BLIND_PAYLOAD_HASH_MISMATCH")

        # 2) Certificate / manifest binding mismatch
        _expect_audit_error(
            lambda: audit.verify_blind_receipt_dict(base_b, expected_cert_payload_sha256="0" * 64),
            "BLIND_CERT_BINDING_MISMATCH",
        )
        _expect_audit_error(
            lambda: audit.verify_blind_receipt_dict(base_b, expected_manifest_digests={"phase_a_manifest_sha256": "0" * 64}),
            "BLIND_MANIFEST_BINDING_MISMATCH",
        )

        # 3) Control C2: overwrite ONE row's half2_p_holm with its raw p (0.00125) and re-seal -> MUST FAIL
        b_c2 = json.loads(audit.canonical_json(base_b))
        a3_first = next(r for r in b_c2["holm_rejected"] if r["lens"] == "A3_TIME_REVERSAL_ASYMMETRY")
        a3_first["half2_p_holm"] = 0.00125
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_c2)), "BLIND_HOLM_RECOMPUTE_MISMATCH")

        # 4) Control C6: set ALL rows of multi-member families (A3 m=13 and A1 m=51) to raw p and re-seal -> MUST FAIL
        b_c6 = json.loads(audit.canonical_json(base_b))
        for i, r in enumerate([x for x in b_c6["holm_rejected"] if x["lens"] == "A3_TIME_REVERSAL_ASYMMETRY"]):
            r["half2_p_holm"] = 0.0025 if i == 0 else float(r["half2_p_iaaft"])
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_c6)), "BLIND_HOLM_RECOMPUTE_MISMATCH")

        b_c6_rej = json.loads(audit.canonical_json(base_b))
        a1_rows = [r for r in b_c6_rej["holm_rejected"] if r["lens"] == "A1_BICOHERENCE"]
        for i, r in enumerate(a1_rows):
            r["half2_p_holm"] = 0.0025 if i == 0 else float(r["half2_p_iaaft"])
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_c6_rej)), "BLIND_HOLM_RECOMPUTE_MISMATCH")

        # 5) Promote a holm_rejected row into surviving anomalies_by_phase -> BLIND_HOLM_GATE_MISMATCH
        b_prom = json.loads(audit.canonical_json(base_b))
        moved = b_prom["holm_rejected"].pop(0)
        moved["replicated_anomaly"] = True
        b_prom["anomalies_by_phase"]["IDLE"].append(moved)
        b_prom["total_surviving_anomalies"] += 1
        b_prom["total_holm_rejected"] -= 1
        b_prom["counts_by_lens"][moved["lens"]] = b_prom["counts_by_lens"].get(moved["lens"], 0) + 1
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_prom)), "BLIND_HOLM_GATE_MISMATCH")

        # 6) Wrong holm_family_size -> BLIND_HOLM_FAMILY_MISMATCH
        b_fsize = json.loads(audit.canonical_json(base_b))
        b_fsize["holm_rejected"][0]["holm_family_size"] = 1
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_fsize)), "BLIND_HOLM_FAMILY_MISMATCH")

        # 7) Bad holm_family_scope -> BLIND_BAD_HOLM_SCOPE
        b_scope = json.loads(audit.canonical_json(base_b))
        b_scope["holm_family_scope"] = "within_candidate_set"
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_scope)), "BLIND_BAD_HOLM_SCOPE")

        # 8) Low surrogates, non-integer empirical rank on raw p, missing raw p, total/lens mismatches
        b_low_n = json.loads(audit.canonical_json(base_b))
        b_low_n["holm_rejected"][0]["n_surrogates_confirm"] = 199
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_low_n)), "BLIND_LOW_SURROGATES")

        b_nonint = json.loads(audit.canonical_json(base_b))
        a3_nonint = next(r for r in b_nonint["holm_rejected"] if "half2_p_iaaft" in r)
        a3_nonint["half2_p_iaaft"] = 0.0019
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_nonint)), "BLIND_NONINTEGER_EMPIRICAL_RANK")

        b_noraw = json.loads(audit.canonical_json(base_b))
        a3_noraw = next(r for r in b_noraw["holm_rejected"] if "half2_p_iaaft" in r)
        del a3_noraw["half2_p_iaaft"]
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_noraw)), "BLIND_MISSING_RAW_P")

        b_cnt = json.loads(audit.canonical_json(base_b))
        b_cnt["total_surviving_anomalies"] = 2
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_cnt)), "BLIND_TOTAL_MISMATCH")

        b_rcnt = json.loads(audit.canonical_json(base_b))
        b_rcnt["total_holm_rejected"] = 19
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_rcnt)), "BLIND_REJECTED_TOTAL_MISMATCH")

        b_ccnt = json.loads(audit.canonical_json(base_b))
        b_ccnt["total_candidates_evaluated"] = 174
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_ccnt)), "BLIND_CANDIDATE_TOTAL_MISMATCH")

        b_lcnt = json.loads(audit.canonical_json(base_b))
        b_lcnt["counts_by_lens"]["A3_TIME_REVERSAL_ASYMMETRY"] = 2
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_lcnt)), "BLIND_LENS_COUNTS_MISMATCH")

        # 8b) Family-shrink + reseal, drop-row + reseal, phase-JSON digest edit + reseal, and stale summary checks
        b_shrink = json.loads(audit.canonical_json(base_b))
        a2_kept = [r for r in b_shrink["holm_rejected"] if r["lens"] == "A2_CHIRAL_4X4_CSD"][:2]
        b_shrink["holm_rejected"] = [r for r in b_shrink["holm_rejected"] if r["lens"] != "A2_CHIRAL_4X4_CSD"]
        for r in a2_kept:
            r["holm_family_size"] = 2
            r["half2_p_holm"] = 0.0025
            r["replicated_anomaly"] = True
            b_shrink["anomalies_by_phase"][r["phase"]].append(r)
        b_shrink["counts_by_lens"]["A2_CHIRAL_4X4_CSD"] = 2
        b_shrink["total_surviving_anomalies"] = 2
        b_shrink["total_holm_rejected"] = len(b_shrink["holm_rejected"])
        b_shrink["total_candidates_evaluated"] = 2 + len(b_shrink["holm_rejected"])
        b_shrink["pooled_lens_family_summary"]["A2_CHIRAL_4X4_CSD"] = {
            "family_size": 2,
            "min_raw_p": 0.00125,
            "min_p_holm": 0.0025,
            "surviving_count": 2,
            "rejected_count": 0,
        }
        _expect_audit_error(
            lambda: audit.verify_blind_receipt_dict(
                _resign_blind(b_shrink),
                expected_cert_payload_sha256=base_c["payload_sha256"],
                expected_manifest_digests=base_c["payload"]["manifest_digests"],
            ),
            "BLIND_FAMILY_SIZE_PIN_MISMATCH",
        )

        # Drop 1 row from A3_POST_LOAD_AFTERGLOW (m: 2 -> 1) + fix summary/totals + reseal -> BLIND_FAMILY_SIZE_PIN_MISMATCH
        b_drop = json.loads(audit.canonical_json(base_b))
        ag_rows = [r for r in b_drop["holm_rejected"] if r["lens"] == "A3_POST_LOAD_AFTERGLOW"]
        b_drop["holm_rejected"] = [r for r in b_drop["holm_rejected"] if r["lens"] != "A3_POST_LOAD_AFTERGLOW"]
        kept_ag = ag_rows[0]
        kept_ag["holm_family_size"] = 1
        kept_ag["half2_p_holm"] = float(kept_ag["rep2_p_iaaft"])
        kept_ag["rep2_p_holm"] = float(kept_ag["rep2_p_iaaft"])
        b_drop["holm_rejected"].append(kept_ag)
        b_drop["total_holm_rejected"] = len(b_drop["holm_rejected"])
        b_drop["total_candidates_evaluated"] = len(b_drop["holm_rejected"])
        b_drop["pooled_lens_family_summary"]["A3_POST_LOAD_AFTERGLOW"] = {
            "family_size": 1,
            "min_raw_p": float(kept_ag["rep2_p_iaaft"]),
            "min_p_holm": float(kept_ag["rep2_p_iaaft"]),
            "surviving_count": 0,
            "rejected_count": 1,
        }
        _expect_audit_error(
            lambda: audit.verify_blind_receipt_dict(
                _resign_blind(b_drop),
                expected_cert_payload_sha256=base_c["payload_sha256"],
                expected_manifest_digests=base_c["payload"]["manifest_digests"],
            ),
            "BLIND_FAMILY_SIZE_PIN_MISMATCH",
        )

        # Phase-JSON digest edit + reseal -> BLIND_PHASE_JSON_PIN_MISMATCH
        b_pjson = json.loads(audit.canonical_json(base_b))
        b_pjson["source_phase_json_sha256s"]["phase_a_json_sha256"] = "0" * 64
        _expect_audit_error(
            lambda: audit.verify_blind_receipt_dict(
                _resign_blind(b_pjson),
                expected_cert_payload_sha256=base_c["payload_sha256"],
                expected_manifest_digests=base_c["payload"]["manifest_digests"],
            ),
            "BLIND_PHASE_JSON_PIN_MISMATCH",
        )

        # Stale / malformed pooled_lens_family_summary checks -> BLIND_SUMMARY_MISMATCH
        for mut_fn in (
            lambda d: d.update({"pooled_lens_family_summary": []}),
            lambda d: d["pooled_lens_family_summary"].pop("A1_BICOHERENCE"),
            lambda d: d["pooled_lens_family_summary"].update({"A1_BICOHERENCE": "bad"}),
            lambda d: d["pooled_lens_family_summary"]["A1_BICOHERENCE"].update({"family_size": 999}),
            lambda d: d["pooled_lens_family_summary"]["A1_BICOHERENCE"].update({"surviving_count": 1}),
            lambda d: d["pooled_lens_family_summary"]["A1_BICOHERENCE"].update({"rejected_count": 0}),
            lambda d: d["pooled_lens_family_summary"]["A1_BICOHERENCE"].pop("min_raw_p"),
            lambda d: d["pooled_lens_family_summary"]["A1_BICOHERENCE"].update({"min_raw_p": 0.5}),
            lambda d: d["pooled_lens_family_summary"]["A1_BICOHERENCE"].pop("min_p_holm"),
            lambda d: d["pooled_lens_family_summary"]["A1_BICOHERENCE"].update({"min_p_holm": 0.5}),
        ):
            b_sum = json.loads(audit.canonical_json(base_b))
            mut_fn(b_sum)
            _expect_audit_error(lambda s=b_sum: audit.verify_blind_receipt_dict(_resign_blind(s)), "BLIND_SUMMARY_MISMATCH")

        # 9) Structural / header / boundary guards
        with tempfile.TemporaryDirectory() as td:
            bad_prereg_p = Path(td) / "PREREG_TAMPERED.md"
            bad_prereg_p.write_text("tampered\n", encoding="utf-8")
            _expect_audit_error(lambda: audit.verify_blind_receipt_dict(base_b, bad_prereg_p), "PREREG_FILE_TAMPERED")

        b_short_h = json.loads(audit.canonical_json(base_b))
        b_short_h["receipt_payload_sha256"] = "short"
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(b_short_h), "BLIND_MISSING_HASH")

        b_pr = json.loads(audit.canonical_json(base_b))
        b_pr["prereg_amendment"] = "WRONG"
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_pr)), "BLIND_BAD_PREREG")

        b_psha = json.loads(audit.canonical_json(base_b))
        b_psha["parent_prereg_sha256"] = "0" * 64
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_psha)), "BLIND_PARENT_SHA_MISMATCH")

        b_eph = json.loads(audit.canonical_json(base_b))
        b_eph["phases_analyzed"] = []
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_eph)), "BLIND_EMPTY_PHASES")

        b_bstruct = json.loads(audit.canonical_json(base_b))
        b_bstruct["counts_by_lens"] = []
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_bstruct)), "BLIND_BAD_STRUCT")

        b_mph = json.loads(audit.canonical_json(base_b))
        del b_mph["anomalies_by_phase"]["D"]
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_mph)), "BLIND_MISSING_PHASE")

        b_badrow = json.loads(audit.canonical_json(base_b))
        b_badrow["anomalies_by_phase"]["A"].append("not-a-dict")
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_badrow)), "BLIND_BAD_ROW")

        b_elens = json.loads(audit.canonical_json(base_b))
        b_elens["anomalies_by_phase"]["A"].append({"lens": ""})
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_elens)), "BLIND_EMPTY_LENS")

        b_badrej = json.loads(audit.canonical_json(base_b))
        b_badrej["holm_rejected"].append("not-a-dict")
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_badrej)), "BLIND_BAD_ROW")

        b_erej = json.loads(audit.canonical_json(base_b))
        b_erej["holm_rejected"][0]["lens"] = ""
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(b_erej)), "BLIND_EMPTY_LENS")

        # Boundary: 1-character lens name (len == 1) + exact 1e-6 tolerance on blind Holm recompute & summary
        b_min_ok = _resign_blind({
            "prereg_amendment": audit.AMENDMENT_ID,
            "parent_prereg_sha256": audit.EXPECTED_PARENT_PREREG_SHA256,
            "holm_family_scope": "pooled_across_all_phases",
            "phases_analyzed": ["A"],
            "total_candidates_evaluated": 2,
            "total_surviving_anomalies": 1,
            "total_holm_rejected": 1,
            "counts_by_lens": {"X": 1},
            "pooled_lens_family_summary": {
                "X": {
                    "family_size": 1,
                    "min_raw_p": 2e-6,
                    "min_p_holm": 2e-6,
                    "surviving_count": 1,
                    "rejected_count": 0,
                },
                "Y": {
                    "family_size": 1,
                    "min_raw_p": 0.01,
                    "min_p_holm": 0.01,
                    "surviving_count": 0,
                    "rejected_count": 1,
                },
            },
            "anomalies_by_phase": {
                "A": [{
                    "lens": "X",
                    "holm_family": "X",
                    "holm_family_size": 1,
                    "n_surrogates_confirm": 999999,
                    "half2_p_iaaft": 1e-6,
                    "half2_p_holm": 2e-6,
                    "replicated_anomaly": True,
                }]
            },
            "holm_rejected": [{
                "lens": "Y",
                "holm_family": "Y",
                "holm_family_size": 1,
                "n_surrogates_confirm": 799,
                "half2_p_iaaft": 0.01,
                "half2_p_holm": 0.01,
                "replicated_anomaly": False,
            }],
        })
        _ensure(audit.verify_blind_receipt_dict(b_min_ok)["ok"] is True, "1-char lens & 1e-6 tolerance boundary must pass")

        # Confirm valid binding passes cleanly
        ok_b = audit.verify_blind_receipt_dict(
            base_b,
            expected_cert_payload_sha256=base_c["payload_sha256"],
            expected_manifest_digests=base_c["payload"]["manifest_digests"],
        )
        _ensure(ok_b["ok"] is True, "Valid bound blind receipt must pass")

    def test_07_privacy_leak_refusal_and_bundle_hygiene(self) -> None:
        base = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")
        leaked = json.loads(audit.canonical_json(base))
        leaked["payload"]["note"] = chr(47) + "ho" + "me" + chr(47) + "alice"
        _expect_audit_error(lambda: audit.verify_certificate_dict(_resign_cert(leaked)), "CERT_PRIVACY_LEAK")

        base_b = audit.load_strict_json_file(_HERE / "s113_blind_anomalies_receipt.json")
        leaked_b = json.loads(audit.canonical_json(base_b))
        leaked_b["note"] = chr(47) + "ho" + "me" + chr(47) + "alice"
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(_resign_blind(leaked_b)), "BLIND_PRIVACY_LEAK")

        forbid_exts = {".s32le", ".yuyv", ".grey", ".wav", ".npz", ".npy", ".pt", ".pth", ".bin", ".safetensors", ".pyc", ".so", ".o"}
        forbid_strs = (
            chr(47) + "ho" + "me" + chr(47),
            chr(47) + "Us" + "ers" + chr(47),
            "~" + chr(47),
            "4-" + "mode",
            "AUD" + "IT-",
        )
        py_checked = 0
        for p in sorted(_HERE.rglob("*")):
            if not p.is_file():
                continue
            _ensure("__pycache__" not in p.parts, f"__pycache__ found: {p}")
            _ensure(p.suffix.lower() not in forbid_exts, f"Forbidden binary/raw file staged: {p.name}")
            raw = p.read_bytes()
            _ensure(not raw.startswith(b"\x7fELF"), f"ELF binary staged: {p.name}")
            _ensure(b"\r" not in raw, f"CR byte found in {p.relative_to(_HERE)}")
            txt = raw.decode("utf-8")
            for bad in forbid_strs:
                _ensure(bad not in txt, f"Forbidden token {bad!r} in {p.relative_to(_HERE)}")
            if p.suffix == ".py":
                tree = ast.parse(txt, filename=str(p.name))
                asserts = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
                _ensure(len(asserts) == 0, f"Bare assert in {p.relative_to(_HERE)}")
                py_checked += 1
        _ensure(py_checked >= 6, f"Expected >=6 Python files checked, got {py_checked}")

    def test_08_optional_full_dsp_suites_when_numpy_scipy_available(self) -> None:
        dsp_dir = _HERE / "dsp_harnesses"
        if not dsp_dir.is_dir():
            return
        has_dsp = (importlib.util.find_spec("numpy") is not None) and (importlib.util.find_spec("scipy") is not None)
        if not has_dsp:
            # Stdlib-only CI environment: verify both DSP test files exist and AST-parse cleanly,
            # but report a SKIP (not a pass) since the DSP suites themselves did not run.
            for name in ("test_s113_r5.py", "test_s113_blind_anomaly_hunter.py"):
                p = dsp_dir / name
                _ensure(p.is_file(), f"Missing {name}")
                ast.parse(p.read_text(encoding="utf-8"), filename=name)
            self.skipTest("numpy/scipy unavailable: DSP suites not executed (files AST-parsed only)")

        if str(dsp_dir) not in sys.path:
            sys.path.insert(0, str(dsp_dir))
        loader = unittest.TestLoader()
        for mod_name, file_name in (
            ("s113_dsp_r5_mod", "test_s113_r5.py"),
            ("s113_blind_r5_mod", "test_s113_blind_anomaly_hunter.py"),
        ):
            spec = importlib.util.spec_from_file_location(mod_name, str(dsp_dir / file_name))
            _ensure(spec is not None and spec.loader is not None, f"Cannot load {file_name}")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            suite = loader.loadTestsFromModule(mod)
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
            _ensure(result.wasSuccessful(), f"{file_name} failed:\n{stream.getvalue()}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
