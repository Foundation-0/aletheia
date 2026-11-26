#!/usr/bin/env python3
"""Pure-Stdlib R5 Unit & Mutation-Kill Suite for `s115_silisense_audit.py`.

Strictly Python standard library ONLY (`0` torch/numpy/scipy imports, `0` bare asserts, `0` skips).
Exercises every `require_ok` guard, exact threshold boundary (`CONFIRMED` / `PARTIAL` / `FALSIFIED`
across `H15a`, `H15b`, and `H15c`), inner-hash tamper, `mlos` Zone-B receipt tamper/window/telemetry
refusal, Mode-1 airlock breach refusal, directory hygiene (`WEIGHTS`/`AV`/`ELF`), and CLI modes.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from typing import Any, Callable, Dict

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import s115_silisense_audit as aud  # noqa: E402


def _resign(obj: Dict[str, Any], field: str) -> Dict[str, Any]:
    body = {k: v for k, v in obj.items() if k != field}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    out = dict(body)
    out[field] = hashlib.sha256(raw).hexdigest()
    return out


class TestS115SiliSenseAuditR5(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_results = json.loads((_HERE / aud.RESULTS_FILENAME).read_text(encoding="utf-8"))
        cls.base_zoneb = json.loads((_HERE / aud.ZONE_B_FILENAME).read_text(encoding="utf-8"))
        cls.base_report = (_HERE / aud.REPORT_FILENAME).read_text(encoding="utf-8")
        cls.base_prereg = (_HERE / aud.PREREG_FILENAME).read_bytes()

    def _make_fixture_dir(
        self,
        td: str,
        *,
        mutate_results: Callable[[Dict[str, Any]], None] | None = None,
        resign_results: bool = True,
        mutate_zoneb: Callable[[Dict[str, Any]], None] | None = None,
        resign_zoneb: bool = True,
        report_text: str | None = None,
        include_prereg: bool = True,
    ) -> Path:
        d = Path(td) / "sub_bundle"
        d.mkdir(parents=True, exist_ok=True)
        res = copy.deepcopy(self.base_results)
        if mutate_results is not None:
            mutate_results(res)
        if resign_results:
            res = _resign(res, "result_sha256")
        zb = copy.deepcopy(self.base_zoneb)
        if mutate_zoneb is not None:
            mutate_zoneb(zb)
        if resign_zoneb:
            zb = _resign(zb, "receipt_sha256")
        rep = self.base_report if report_text is None else report_text
        if mutate_zoneb is not None and report_text is None:
            rep = rep + f"\n<!-- updated receipt {zb['receipt_sha256']} -->\n"

        if include_prereg:
            (d / aud.PREREG_FILENAME).write_bytes(self.base_prereg)
        (d / aud.RESULTS_FILENAME).write_text(json.dumps(res, sort_keys=True), encoding="utf-8")
        (d / aud.ZONE_B_FILENAME).write_text(json.dumps(zb, sort_keys=True), encoding="utf-8")
        (d / aud.REPORT_FILENAME).write_text(rep, encoding="utf-8")
        return d

    def _expect_audit_code(self, fn: Callable[[], Any], expected_code: str) -> None:
        with self.assertRaises(aud.S115AuditError) as ctx:
            fn()
        self.assertEqual(ctx.exception.code, expected_code)

    def test_01_live_track_certificate_build_and_cli_roundtrip(self) -> None:
        cert = aud.build_certificate(_HERE)
        self.assertEqual(cert["schema"], aud.SCHEMA_VERSION)
        self.assertEqual(cert["verdicts"], {"H15a": "FALSIFIED", "H15b": "FALSIFIED", "H15c": "FALSIFIED"})
        self.assertEqual(cert["hygiene"], {"weights_count": 0, "av_count": 0, "elf_count": 0})
        self.assertEqual(cert["sensor_airlock"]["sensor_violations"], 0)
        self.assertEqual(len(cert["cert_sha256"]), 64)

        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td)
            buf_out, buf_err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
                rc_w = aud.main(["--track-dir", str(d), "--write"])
                self.assertEqual(rc_w, 0)
                cert_p = d / aud.CERT_FILENAME
                self.assertTrue(cert_p.is_file())
                rc_c = aud.main(["--track-dir", str(d), "--check", str(cert_p)])
                self.assertEqual(rc_c, 0)
                rc_c_rel = aud.main(["--track-dir", str(d), "--check"])
                self.assertEqual(rc_c_rel, 0)
                rc_plain = aud.main(["--track-dir", str(d)])
                self.assertEqual(rc_plain, 0)

                bad_cert = json.loads(cert_p.read_text(encoding="utf-8"))
                bad_cert["n2_claims"] = 1
                cert_p.write_text(json.dumps(bad_cert), encoding="utf-8")
                rc_bad = aud.main(["--track-dir", str(d), "--check"])
                self.assertEqual(rc_bad, 2)

                drifted = _resign(bad_cert, "cert_sha256")
                cert_p.write_text(json.dumps(drifted), encoding="utf-8")
                rc_drift = aud.main(["--track-dir", str(d), "--check"])
                self.assertEqual(rc_drift, 2)

                # Non-finite JSON constants (NaN / Infinity / -Infinity) & overflow floats (1e999) MUST fail closed with typed rc=2 (MALFORMED_JSON)
                for bad_lit in ("NaN", "Infinity", "-Infinity", "1e999"):
                    buf_err.seek(0)
                    buf_err.truncate(0)
                    cert_p.write_text('{"cert_sha256": "' + ("0" * 64) + '", "bad": ' + bad_lit + "}\n", encoding="utf-8")
                    rc_bad_lit = aud.main(["--track-dir", str(d), "--check"])
                    self.assertEqual(rc_bad_lit, 2, f"Expected rc=2 for {bad_lit}")
                    self.assertIn("MALFORMED_JSON", buf_err.getvalue())

                # CLI mutual exclusion (--write + --check, --write + --standalone) MUST fail closed (rc=2)
                self.assertEqual(aud.main(["--track-dir", str(d), "--write", "--check"]), 2)
                self.assertEqual(aud.main(["--track-dir", str(d), "--write", "--standalone"]), 2)
                self.assertEqual(aud.main(["--track-dir", str(d), "--standalone", "--json"]), 0)

    def test_02_pure_grading_functions_all_outcomes_and_exact_boundaries(self) -> None:
        # H15a: CONFIRMED, PARTIAL, FALSIFIED + exact boundary checks (-20.0, -2.0, 0.05)
        self.assertEqual(
            aud.grade_h15a_pure(
                any_sig_0p005=True, a3_rel_pct=-20.0, a3_z=-2.0, a7_rel_pct=-20.0, a7_z=-2.0,
                max_eqw_rel_diff=0.05, eqw_a3_z=-2.0, eqw_a7_z=0.0,
            )["verdict"],
            "CONFIRMED",
        )
        self.assertEqual(
            aud.grade_h15a_pure(
                any_sig_0p005=True, a3_rel_pct=-20.0, a3_z=-2.0, a7_rel_pct=-20.0, a7_z=-2.0,
                max_eqw_rel_diff=0.0501, eqw_a3_z=-2.0, eqw_a7_z=-2.0,
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            aud.grade_h15a_pure(
                any_sig_0p005=True, a3_rel_pct=-19.99, a3_z=-2.5, a7_rel_pct=-25.0, a7_z=-1.99,
                max_eqw_rel_diff=0.03, eqw_a3_z=-3.0, eqw_a7_z=-3.0,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            aud.grade_h15a_pure(
                any_sig_0p005=False, a3_rel_pct=-40.0, a3_z=-5.0, a7_rel_pct=-40.0, a7_z=-5.0,
                max_eqw_rel_diff=0.01, eqw_a3_z=-5.0, eqw_a7_z=-5.0,
            )["verdict"],
            "FALSIFIED",
        )

        # H15b: CONFIRMED (via stall or via cv), PARTIAL, FALSIFIED + exact boundaries
        self.assertEqual(
            aud.grade_h15b_pure(
                med_lead_ms=-20.0, max_p_circ=0.0049,
                stall_no_rel=-25.0, stall_no_z=-2.0, stall_smi_rel=-25.0, stall_smi_z=-2.0, stall_shuf_z=-2.0,
                cv_no_rel=0.0, cv_no_z=0.0, cv_smi_rel=0.0, cv_smi_z=0.0, cv_shuf_z=0.0,
                tps_no_rel=-2.0,
            )["verdict"],
            "CONFIRMED",
        )
        self.assertEqual(
            aud.grade_h15b_pure(
                med_lead_ms=-20.0, max_p_circ=0.005,  # strict < 0.005 boundary!
                stall_no_rel=-25.0, stall_no_z=-2.0, stall_smi_rel=-25.0, stall_smi_z=-2.0, stall_shuf_z=-2.0,
                cv_no_rel=0.0, cv_no_z=0.0, cv_smi_rel=0.0, cv_smi_z=0.0, cv_shuf_z=0.0,
                tps_no_rel=-2.0,
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            aud.grade_h15b_pure(
                med_lead_ms=-25.0, max_p_circ=0.002,
                stall_no_rel=-5.0, stall_no_z=-1.0, stall_smi_rel=0.0, stall_smi_z=0.0, stall_shuf_z=0.0,
                cv_no_rel=-20.0, cv_no_z=-2.0, cv_smi_rel=-20.0, cv_smi_z=-2.0, cv_shuf_z=-2.0,
                tps_no_rel=-2.01,  # misses -2.0% tps gate -> PARTIAL
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            aud.grade_h15b_pure(
                med_lead_ms=-19.9, max_p_circ=0.002,
                stall_no_rel=-24.9, stall_no_z=-3.0, stall_smi_rel=0.0, stall_smi_z=0.0, stall_shuf_z=0.0,
                cv_no_rel=-19.9, cv_no_z=-3.0, cv_smi_rel=0.0, cv_smi_z=0.0, cv_shuf_z=0.0,
                tps_no_rel=-5.1,
            )["verdict"],
            "FALSIFIED",
        )

        # H15c: CONFIRMED (via EDP or via drift), PARTIAL, FALSIFIED + exact boundaries
        self.assertEqual(
            aud.grade_h15c_pure(
                vs_tps_rel=-5.0, vs_tps_z=-2.0, vs_edp0_rel=-2.0, vs_edp0_z=-2.0, drift_vs_edp0_rel=0.0, drift_vs_edp0_z=0.0
            )["verdict"],
            "CONFIRMED",
        )
        self.assertEqual(
            aud.grade_h15c_pure(
                vs_tps_rel=-5.0, vs_tps_z=-2.0, vs_edp0_rel=1.5, vs_edp0_z=0.5, drift_vs_edp0_rel=-15.0, drift_vs_edp0_z=-2.0
            )["verdict"],
            "CONFIRMED",
        )
        self.assertEqual(
            aud.grade_h15c_pure(
                vs_tps_rel=-5.0, vs_tps_z=-2.0, vs_edp0_rel=2.0, vs_edp0_z=1.0, drift_vs_edp0_rel=-14.9, drift_vs_edp0_z=-3.0
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            aud.grade_h15c_pure(
                vs_tps_rel=-5.0, vs_tps_z=-2.0, vs_edp0_rel=2.01, vs_edp0_z=1.0, drift_vs_edp0_rel=0.0, drift_vs_edp0_z=0.0
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            aud.grade_h15c_pure(
                vs_tps_rel=-4.99, vs_tps_z=-3.0, vs_edp0_rel=-10.0, vs_edp0_z=-3.0, drift_vs_edp0_rel=-20.0, drift_vs_edp0_z=-3.0
            )["verdict"],
            "FALSIFIED",
        )

    def test_03_hygiene_prereg_report_and_inner_hash_refusals(self) -> None:
        # Weights, AV, and ELF magic refusals
        for fname, content, code in (
            ("leak.pt", b"weights", "HYGIENE_WEIGHTS"),
            ("mic.wav", b"RIFF", "HYGIENE_AV"),
            ("kern.so", b"not_elf", "HYGIENE_ELF"),
            ("hidden_bin.dat", b"\x7fELF\x02\x01", "HYGIENE_ELF"),
        ):
            with tempfile.TemporaryDirectory() as td:
                d = self._make_fixture_dir(td)
                (d / fname).write_bytes(content)
                self._expect_audit_code(lambda: aud.build_certificate(d), code)

        # Local PREREG tamper, missing PREREG, and missing REPORT_FILENAME (_sha256_file M002)
        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td)
            (d / aud.PREREG_FILENAME).write_text("tampered prereg", encoding="utf-8")
            self._expect_audit_code(lambda: aud.build_certificate(d), "PREREG_SHA_MISMATCH")

        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td, include_prereg=False)
            self._expect_audit_code(lambda: aud.build_certificate(d), "MISSING_PREREG")

        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td)
            (d / aud.REPORT_FILENAME).unlink()
            self._expect_audit_code(lambda: aud.build_certificate(d), "MISSING_FILE")

        # Missing JSON, malformed JSON, non-dict root
        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td)
            (d / aud.RESULTS_FILENAME).unlink()
            self._expect_audit_code(lambda: aud.build_certificate(d), "MISSING_JSON")

        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td)
            (d / aud.RESULTS_FILENAME).write_text("{bad json", encoding="utf-8")
            self._expect_audit_code(lambda: aud.build_certificate(d), "MALFORMED_JSON")

        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td)
            (d / aud.RESULTS_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
            self._expect_audit_code(lambda: aud.build_certificate(d), "SCHEMA_ROOT")

        # Inner hash mismatch & missing inner hash
        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td, mutate_results=lambda r: r.update({"elapsed_seconds": 1.0}), resign_results=False)
            self._expect_audit_code(lambda: aud.build_certificate(d), "INNER_HASH_MISMATCH")

        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td, mutate_results=lambda r: r.pop("result_sha256", None), resign_results=False)
            (d / aud.RESULTS_FILENAME).write_text(json.dumps({k: v for k, v in self.base_results.items() if k != "result_sha256"}), encoding="utf-8")
            self._expect_audit_code(lambda: aud.build_certificate(d), "MISSING_INNER_HASH")

        # Report missing PREREG SHA or Zone-B SHA
        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td, report_text="no hashes here")
            self._expect_audit_code(lambda: aud.build_certificate(d), "REPORT_PREREG_REF")

        with tempfile.TemporaryDirectory() as td:
            d = self._make_fixture_dir(td, report_text=aud.PREREG_SHA256)
            self._expect_audit_code(lambda: aud.build_certificate(d), "REPORT_ZONEB_REF")

    def test_04_zone_b_and_airlock_tamper_refusals(self) -> None:
        zone_b_mutations = [
            (lambda z: z.update({"schema": "wrong"}), "RECEIPT_SCHEMA"),
            (lambda z: z.update({"determinism_zone": "A"}), "RECEIPT_ZONE"),
            (lambda z: z.update({"clean_hardware_run": False}), "RECEIPT_UNCLEAN"),
            (lambda z: z.update({"anomalies": ["THROTTLE"]}), "RECEIPT_ANOMALIES"),
            (lambda z: z.update({"gpu_telemetry_available": False}), "RECEIPT_NO_GPU_TEL"),
            (lambda z: z["execution"].update({"exit_code": 1}), "RECEIPT_EXIT_CODE"),
            (lambda z: z["execution"].update({"started_utc": "2099-01-01T00:00:00Z"}), "RECEIPT_TIME_WINDOW"),
            (lambda z: z["execution"].update({"started_utc": 12345}), "BAD_TIMESTAMP"),
            (lambda z: z["execution"].update({"started_utc": "not-a-date"}), "BAD_TIMESTAMP"),
            (lambda z: z["execution"].update({"started_utc": "2026-11-26T00:08:20"}), "NAIVE_TIMESTAMP"),
            (lambda z: z["start_gpu_telemetry"].update({"compute_vram_mib": 12}), "RECEIPT_COMPUTE_VRAM"),
            (lambda z: z["end_gpu_telemetry"]["clocks_event_reasons"].update({"thermal_throttled": True}), "RECEIPT_THERMAL_THROTTLE"),
            (lambda z: z["end_gpu_telemetry"]["clocks_event_reasons"].update({"slowdown_active": True}), "RECEIPT_SLOWDOWN"),
            (lambda z: z.pop("end_gpu_telemetry"), "RECEIPT_TEL_OBJ"),
            (lambda z: z["start_gpu_telemetry"].pop("clocks_event_reasons"), "RECEIPT_CLOCKS_OBJ"),
        ]
        for mut_fn, expected_code in zone_b_mutations:
            with tempfile.TemporaryDirectory() as td:
                d = self._make_fixture_dir(td, mutate_zoneb=mut_fn)
                self._expect_audit_code(lambda: aud.build_certificate(d), expected_code)

        airlock_mutations = [
            (lambda r: r.update({"preregistration_sha256": "0" * 64}), "RESULT_PREREG_SHA"),
            (lambda r: r.pop("sensor_airlock_audit"), "AIRLOCK_MISSING"),
            (lambda r: r["sensor_airlock_audit"].update({"mode": "dmic-authorized"}), "AIRLOCK_MODE"),
            (lambda r: r["sensor_airlock_audit"].update({"dmic_authorized": True}), "AIRLOCK_DMIC"),
            (lambda r: r["sensor_airlock_audit"].update({"camera_policy": "ALLOW"}), "AIRLOCK_CAMERA_POLICY"),
            (lambda r: r["sensor_airlock_audit"].update({"checked_open_calls": 0}), "AIRLOCK_INACTIVE"),
            (lambda r: r["sensor_airlock_audit"].update({"camera_opens": 1}), "AIRLOCK_BREACH"),
            (lambda r: r["sensor_airlock_audit"].update({"audio_opens": 1}), "AIRLOCK_BREACH"),
            (lambda r: r.pop("hardware_sampler_info"), "SAMPLER_INFO_MISSING"),
            (lambda r: r["hardware_sampler_info"].update({"rapl_domains": ["pkg"]}), "RAPL_DOMAINS_MISMATCH"),
            (lambda r: r["hardware_sampler_info"].update({"nvml_ready": False}), "NVML_NOT_READY"),
            (lambda r: r.pop("verdicts"), "MISSING_VERDICTS"),
        ]
        for mut_fn, expected_code in airlock_mutations:
            with tempfile.TemporaryDirectory() as td:
                d = self._make_fixture_dir(td, mutate_results=mut_fn)
                self._expect_audit_code(lambda: aud.build_certificate(d), expected_code)

    def test_05_h15a_h15b_h15c_recomputation_and_schema_guards(self) -> None:
        exp_mutations = [
            # H15a guards
            (lambda r: r["h15a"]["standard_pairs"].pop(), "H15A_STD_COUNT"),
            (lambda r: r["h15a"]["equal_watt_pairs"].pop(), "H15A_EQW_COUNT"),
            (lambda r: r["h15a"]["standard_pairs"][0].update({"seed": 999}), "H15A_SEEDS"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"].update({"tokens_processed": 100}), "H15A_CS08_TOKENS"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"].update({"A7_max_residual_lin_corr": 1e-3}), "H15A_SCHUR_E"),
            (lambda r: r["h15a"]["standard_pairs"][0]["holosphere_v2_sm86"].update({"A7_max_residual_lin_corr": 1e-3}), "H15A_SCHUR_F"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"].pop("OP1_SEAM1"), "MISSING_EXACT_Q"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"]["OP1_SEAM1"].update({"max_leverage_exact_q": "-1/4"}), "OP1_BOUNDS"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"]["OP1_SEAM1"].update({"max_leverage_exact_q": "1/1"}), "OP1_BOUNDS"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"]["OP2_SEAM3"].update({"phi_asym_exact_q": "3/2"}), "OP2_BOUNDS"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"]["OP3_F3"].update({"kappa_f3_exact_q": "-1/3"}), "OP3_BOUNDS"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"].update({"frame64_merkle_sha256": "short"}), "FRAME64_HASH"),
            (lambda r: r["h15a"]["equal_watt_pairs"][0]["holosphere_v2_sm86"].update({"mean_gpu_power_w": 0.0}), "H15A_EQW_POS"),
            (lambda r: r["h15a"]["graded"].update({"criterion_2_both_a3_and_a7_reduced_20pct": True}), "H15A_GATE_MISMATCH"),
            (lambda r: r["verdicts"].update({"H15a": "CONFIRMED"}), "H15A_VERDICT_MISMATCH"),
            # H15b guards
            (lambda r: r["h15b"]["runs"].pop(), "H15B_RUN_COUNT"),
            (lambda r: r["h15b"]["lead_receipts"].pop(), "H15B_LEAD_COUNT"),
            (lambda r: r["h15b"]["delay_bandwidth_lock"].update({"f_tau_product": 0.25}), "H15B_DELAY_BW"),
            (lambda r: r["h15b"]["runs"][0].update({"min_lyapunov_conductance_g": 0.40}), "H15B_LYAPUNOV_BOUNDS"),
            (lambda r: r["h15b"]["runs"][0].update({"arm": "FakeArm"}), "H15B_ARMS"),
            (lambda r: r["h15b"]["runs"][0].update({"seed": 888}), "H15B_SEEDS"),
            (lambda r: r["h15b"]["runs"][0].update({"tokens_total": 123}), "H15B_CS08_TOKENS"),
            (lambda r: r["h15b"]["runs"][2].update({"damped_steps_count": 999}), "H15B_SHUFFLED_DUTY_MISMATCH"),
            (lambda r: r["h15b"]["graded"].update({"criterion_1_precursor_lead": True}), "H15B_GATE_MISMATCH"),
            (lambda r: r["verdicts"].update({"H15b": "CONFIRMED"}), "H15B_VERDICT_MISMATCH"),
            # H15c guards
            (lambda r: r["h15c"]["calibration_by_seed"].pop("42"), "H15C_CAL_SEEDS"),
            (lambda r: r["h15c"]["calibration_by_seed"].update({"42": "not_a_dict"}), "H15C_SEED_MISSING"),
            (lambda r: r["h15c"]["sustained_runs"].pop(), "H15C_SUS_COUNT"),
            (lambda r: r["h15c"]["calibration_by_seed"]["42"]["candidates"].pop(), "H15C_CAND_COUNT"),
            (lambda r: r["h15c"]["calibration_by_seed"]["42"]["candidates"][0].update({"effective_tokens_per_step": 4096}), "H15C_CS08_CAL"),
            (lambda r: r["h15c"]["calibration_by_seed"]["42"]["candidates"][0].update({"edp": 0.0}), "H15C_EDP_POS"),
            (lambda r: r["h15c"]["calibration_by_seed"]["42"]["selection"].update({"Scalar-TokPerSec-Tuner": "wrong"}), "H15C_SELECTION_MISMATCH"),
            (lambda r: r["h15c"]["sustained_runs"][0].update({"effective_tokens_per_step": 4096}), "H15C_CS08_SUS"),
            (lambda r: r["h15c"]["sustained_runs"][0].update({"selected_config_id": "wrong"}), "H15C_SUS_CONFIG_BIND"),
            (lambda r: r["h15c"]["sustained_runs"][0].update({"tuner_arm": "FakeTuner"}), "H15C_TUNERS"),
            (lambda r: r["h15c"]["sustained_runs"][0].update({"seed": 777}), "H15C_SUS_SEEDS"),
            # Duplicate valid tuner (replaces all Scalar-MeanWatt-EDP-Tuner rows with Scalar-TokPerSec-Tuner) -> H15C_TUNERS
            (
                lambda r: [
                    row.update({"tuner_arm": "Scalar-TokPerSec-Tuner", "selected_config_id": r["h15c"]["calibration_by_seed"][str(row["seed"])]["selection"]["Scalar-TokPerSec-Tuner"]})
                    for row in r["h15c"]["sustained_runs"]
                    if row["tuner_arm"] == "Scalar-MeanWatt-EDP-Tuner"
                ],
                "H15C_TUNERS",
            ),
            # Duplicate valid seed within a tuner (42, 42, 2026) -> H15C_SUS_SEEDS
            (
                lambda r: [
                    row.update({"seed": 42, "selected_config_id": r["h15c"]["calibration_by_seed"]["42"]["selection"][row["tuner_arm"]]})
                    for row in r["h15c"]["sustained_runs"]
                    if row["tuner_arm"] == "Scalar-TokPerSec-Tuner" and row["seed"] == 137
                ],
                "H15C_SUS_SEEDS",
            ),
            (lambda r: r["h15c"]["graded"].update({"criterion_1_edp_vs_scalar_tps": True}), "H15C_GATE_MISMATCH"),
            (lambda r: r["verdicts"].update({"H15c": "CONFIRMED"}), "H15C_VERDICT_MISMATCH"),
            # Primitive type guards
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"].update({"abs_A3": True}), "BAD_NUMBER"),
            (lambda r: r["h15a"]["standard_pairs"][0]["eager_h7b"].update({"tokens_processed": True}), "BAD_INT"),
        ]
        for mut_fn, expected_code in exp_mutations:
            with tempfile.TemporaryDirectory() as td:
                d = self._make_fixture_dir(td, mutate_results=mut_fn)
                self._expect_audit_code(lambda: aud.build_certificate(d), expected_code)

        # Positive exact-equality boundary acceptance tests (kills <= -> < and >= -> > boundary mutants!)
        def _set_valid_exact_boundaries(r: Dict[str, Any]) -> None:
            e0 = r["h15a"]["standard_pairs"][0]["eager_h7b"]
            f0 = r["h15a"]["standard_pairs"][0]["holosphere_v2_sm86"]
            e0["OP1_SEAM1"]["max_leverage_exact_q"] = "0/1"
            e0["OP2_SEAM3"]["phi_asym_exact_q"] = "1/1"
            e0["OP3_F3"]["kappa_f3_exact_q"] = "0/1"
            e0["A7_max_residual_lin_corr"] = aud.A7_SCHUR_CORR_MAX
            f0["A7_max_residual_lin_corr"] = aud.A7_SCHUR_CORR_MAX
            r["h15b"]["runs"][0]["min_lyapunov_conductance_g"] = 0.70
            r["h15b"]["runs"][1]["min_lyapunov_conductance_g"] = 1.00

        def _set_equal_timestamps(z: Dict[str, Any]) -> None:
            ts = str(self.base_results["completed_utc"])
            z["execution"]["started_utc"] = ts
            z["execution"]["ended_utc"] = ts

        with tempfile.TemporaryDirectory() as td:
            d_pos = self._make_fixture_dir(td, mutate_results=_set_valid_exact_boundaries, mutate_zoneb=_set_equal_timestamps)
            cert_pos = aud.build_certificate(d_pos)
            self.assertTrue(cert_pos["prereg_verified"])

        # Student-t df=1, odd/even df coverage & paired_stats length guard
        self._expect_audit_code(lambda: aud.recompute_paired_stats([1.0, 2.0], [1.0, 2.0]), "PAIRED_LEN")
        self._expect_audit_code(lambda: aud._student_t_two_sided_p(2.0, 0), "BAD_DF")
        self.assertGreater(aud._student_t_two_sided_p(1.0, 1), 0.49)
        st_even = aud.recompute_paired_stats([10.0, 10.0, 10.0, 10.0, 10.0], [8.0, 8.0, 8.0, 8.0, 8.0])
        self.assertLess(st_even["z_paired"], -100.0)
        st_odd = aud.recompute_paired_stats([10.0, 10.2, 9.8, 10.1], [8.0, 8.1, 7.9, 8.0])
        self.assertLess(st_odd["p_student_t_2s"], 0.01)


if __name__ == "__main__":
    unittest.main()
