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
            res["payload_sha256"] == "0ea122458a73ef1a97b3b7471d252a9679e7fb885d14178ae4f2c30754fa0845",
            f"Unexpected payload_sha256: {res['payload_sha256']}",
        )
        _ensure(
            res["certificate_sha256"] == "b18744a69571acf501a25fd2340082804bf0d390d2012495d4a2b571fe39d3d5",
            f"Unexpected certificate_sha256: {res['certificate_sha256']}",
        )

        blind = audit.load_strict_json_file(blind_path)
        bres = audit.verify_blind_receipt_dict(blind, prereg_path if prereg_path.is_file() else None)
        _ensure(bres["ok"] is True and bres["total_surviving_anomalies"] == 193, f"Unexpected blind result: {bres}")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = audit.main(["--check", str(cert_path), "--json"])
        _ensure(rc == 0, f"CLI --check exited {rc}")
        parsed = json.loads(buf.getvalue())
        _ensure(parsed["ok"] is True and parsed["blind_surviving_anomalies"] == 193, f"CLI output mismatch: {parsed}")

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

    def test_03_refuse_tampered_hashes_and_strict_json_violations(self) -> None:
        base = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")

        bad_payload = json.loads(audit.canonical_json(base))
        bad_payload["payload"]["seed"] = 999999
        _expect_audit_error(lambda: audit.verify_certificate_dict(bad_payload), "PAYLOAD_HASH_MISMATCH")

        bad_cert = _resign_cert(bad_payload)
        bad_cert["certificate_sha256"] = "0" * 64
        _expect_audit_error(lambda: audit.verify_certificate_dict(bad_cert), "CERT_HASH_MISMATCH")

        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": 1, "a": 2}'), "JSON_DUPLICATE_KEY")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": NaN}'), "JSON_CONSTANT_FORBIDDEN")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": Infinity}'), "JSON_CONSTANT_FORBIDDEN")
        _expect_audit_error(lambda: audit.parse_strict_json_text('{"a": 1e-400}'), "JSON_FLOAT_UNDERFLOW")

    def test_04_refuse_tampered_exact_q_algebra_and_haynsworth_spoof(self) -> None:
        base = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")

        # Non-reduced fraction string
        t_nonred = json.loads(audit.canonical_json(base))
        t_nonred["payload"]["modules"]["H5"]["rapl_dark_r2_given_sensors_exact_q"] = "2/4"
        t_nonred = _resign_cert(t_nonred)
        _expect_audit_error(lambda: audit.verify_certificate_dict(t_nonred), "NONCANONICAL_FRAC_STR")

        # Tampered R^2_Q
        t_r2 = json.loads(audit.canonical_json(base))
        t_r2["payload"]["modules"]["H5"]["rapl_dark_r2_given_sensors_exact_q"] = "1/2"
        t_r2 = _resign_cert(t_r2)
        _expect_audit_error(lambda: audit.verify_certificate_dict(t_r2), "H5_R2_Q_MISMATCH")

        # Tampered incremental R^2_Q
        t_inc = json.loads(audit.canonical_json(base))
        t_inc["payload"]["modules"]["H5"]["incremental_multisensor_dark_r2_exact_q"] = "1/100"
        t_inc = _resign_cert(t_inc)
        _expect_audit_error(lambda: audit.verify_certificate_dict(t_inc), "H5_INCREMENTAL_Q_MISMATCH")

        # Broken Haynsworth inertia additivity
        t_hay = json.loads(audit.canonical_json(base))
        t_hay["payload"]["modules"]["H5"]["krein_inertia_full_pos_zero_neg"] = [12, 1, 0]
        t_hay = _resign_cert(t_hay)
        _expect_audit_error(lambda: audit.verify_certificate_dict(t_hay), "H5_HAYNSWORTH_CERT_FAIL")

        # Tampered K_4 Hodge-1 rational obstruction
        t_k4 = json.loads(audit.canonical_json(base))
        t_k4["payload"]["confirmatory_phases"]["E1"]["e1a_cocycle_and_dispersion"]["core_pinning_3001hz"]["CORE0_3001HZ"]["broadband_hodge1_obstruction"]["kappa_h1_exact_q"] = "1/3"
        t_k4 = _resign_cert(t_k4)
        _expect_audit_error(lambda: audit.verify_certificate_dict(t_k4), "K4_HODGE1_MISMATCH")

    def test_05_refuse_prereg_verdict_goalpost_shifting(self) -> None:
        base = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")

        for mod_key, err_code in (
            ("H2", "H2_GATE_SPOOF"),
            ("H3", "H3_GATE_SPOOF"),
            ("H4", "H4_GATE_SPOOF"),
            ("H5", "H5_GATE_SPOOF"),
        ):
            spoof = json.loads(audit.canonical_json(base))
            spoof["payload"]["modules"][mod_key]["verdict"] = "CONFIRMED"
            spoof["payload"]["verdict_summary"][mod_key] = "CONFIRMED"
            spoof = _resign_cert(spoof)
            _expect_audit_error(lambda s=spoof: audit.verify_certificate_dict(s), err_code)

        # Spoof E1c linear PTC (0.972693 <= 0.98) to CONFIRMED -> must fail closed
        spoof_e1c = json.loads(audit.canonical_json(base))
        spoof_e1c["payload"]["confirmatory_phases"]["E1"]["e1c_linear_gamma100_ptc_and_e1d_thermal"]["verdict"] = "CONFIRMED"
        spoof_e1c["payload"]["verdict_summary"]["H4_E1c_LINEAR_GAMMA100"] = "CONFIRMED"
        spoof_e1c = _resign_cert(spoof_e1c)
        _expect_audit_error(lambda: audit.verify_certificate_dict(spoof_e1c), "E1C_GATE_SPOOF")

    def test_06_refuse_blind_receipt_cs09_and_holm_violations(self) -> None:
        adj = audit.holm_bonferroni_list([0.01, 0.001, 0.02, 0.001])
        _ensure(adj == [0.02, 0.004, 0.02, 0.004], f"Holm step-down mismatch: {adj}")

        base_b = audit.load_strict_json_file(_HERE / "s113_blind_anomalies_receipt.json")

        b_low_n = json.loads(audit.canonical_json(base_b))
        b_low_n["anomalies_by_phase"]["IDLE"][0]["n_surrogates_confirm"] = 199
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(b_low_n), "BLIND_LOW_SURROGATES")

        b_bad_p = json.loads(audit.canonical_json(base_b))
        b_bad_p["anomalies_by_phase"]["IDLE"][0]["half2_p_holm"] = 0.005
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(b_bad_p), "BLIND_HOLM_THRESHOLD")

        b_nonint = json.loads(audit.canonical_json(base_b))
        b_nonint["anomalies_by_phase"]["IDLE"][0]["half2_p_holm"] = 0.0019
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(b_nonint), "BLIND_NONINTEGER_EMPIRICAL_RANK")

        b_cnt = json.loads(audit.canonical_json(base_b))
        b_cnt["total_surviving_anomalies"] = 192
        _expect_audit_error(lambda: audit.verify_blind_receipt_dict(b_cnt), "BLIND_TOTAL_MISMATCH")

    def test_07_privacy_leak_refusal_and_bundle_hygiene(self) -> None:
        base = audit.load_strict_json_file(_HERE / "s113_multisensor_certificate.json")
        leaked = json.loads(audit.canonical_json(base))
        leaked["payload"]["note"] = chr(47) + "ho" + "me" + chr(47) + "alice"
        leaked = _resign_cert(leaked)
        _expect_audit_error(lambda: audit.verify_certificate_dict(leaked), "CERT_PRIVACY_LEAK")

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
            # Stdlib-only CI environment: verify both DSP test files exist and AST-parse cleanly
            for name in ("test_s113_r5.py", "test_s113_blind_anomaly_hunter.py"):
                p = dsp_dir / name
                _ensure(p.is_file(), f"Missing {name}")
                ast.parse(p.read_text(encoding="utf-8"), filename=name)
            return

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
