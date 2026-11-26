#!/usr/bin/env python3
"""Assertion-free pure-stdlib R5 test suite for Track S107 (PREREG-S107 + Amendment 1).

Covers:
  - Live certificate verification (literal_prereg_verdict vs graded_verdict, paired_t df=2)
  - Cryptographic mlos receipt verification (zeroed receipt_sha256, unsigned telemetry edits,
    wrong schema/exit_code/duration/throttling, H7a receipt copied over H7c, duplicate receipts)
  - Dynamic verdict derivation on synthetic datasets (CONFIRMED, PARTIAL, FALSIFIED for H7a/H7c/H7b)
  - Exact CS-08 parameter/FLOP parity guards and boundary checks across H7a/H7c/H7b
  - Corpus digest equality, preflight integrity, manifest schema, and strict JSON depth/key/hex guards
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from typing import Any, Dict

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s107_hypersphere_audit as audit


_TRACK_ARTIFACTS = (
    "h7a_gpu_results.json",
    "h7b_gpu_results.json",
    "h7c_gpu_results.json",
    "mlos_zone_b_h7a.json",
    "mlos_zone_b_h7b.json",
    "mlos_zone_b_h7c.json",
    "s107_cpu_preflight_receipt.json",
    "corpus_manifest.json",
    "PREREG_S107_HYPERSPHERE_TRANSFORMER.md",
    "PREREG_S107_S108_AMENDMENT1.md",
)


def _copy_track_dir(dst: Path) -> None:
    for fname in _TRACK_ARTIFACTS:
        shutil.copy2(_THIS_DIR / fname, dst / fname)


def _resign_mlos(rec: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(rec)
    body = {k: v for k, v in out.items() if k != "receipt_sha256"}
    out["receipt_sha256"] = audit.canonical_sha256(body)
    return out


class TestTrackS107HypersphereAuditR5(unittest.TestCase):
    def test_01_live_certificate_check_passes(self) -> None:
        cert_path = _THIS_DIR / "s107_hypersphere_certificate.json"
        cert = audit.verify_certificate_file(cert_path, _THIS_DIR)
        p = cert["payload"]
        self.assertEqual(p["total_live_gpu_runs"], 111)
        self.assertEqual(p["scorecard"]["literal_prereg_verdict"]["H7a"], "FALSIFIED")
        self.assertEqual(p["scorecard"]["literal_prereg_verdict"]["H7c"], "CONFIRMED")
        self.assertEqual(p["scorecard"]["literal_prereg_verdict"]["H7b"], "FALSIFIED")
        self.assertEqual(p["scorecard"]["graded_verdict"]["H7a"], "FALSIFIED")
        self.assertEqual(p["scorecard"]["graded_verdict"]["H7c"], "PARTIAL")
        self.assertEqual(p["scorecard"]["graded_verdict"]["H7b"], "PARTIAL")
        self.assertEqual(p["scorecard"]["n2_claims"], 0)
        self.assertEqual(p["scorecard"]["weights_saved"], 0)
        self.assertEqual(p["cpu_preflight"]["gates_passed"], 9)
        self.assertEqual(p["h7b"]["su2_over_rope_wall_clock_ratio"], 3.9125)
        self.assertEqual(p["h7b"]["su2_vs_rope_t2048_bpb"]["df"], 2)
        self.assertIn("paired_t", p["h7b"]["su2_vs_rope_t2048_bpb"])
        self.assertNotIn("z_score", p["h7b"]["su2_vs_rope_t2048_bpb"])
        self.assertFalse(p["prereg_provenance"]["pre_run_lock_verifiable_from_git_history"])
        self.assertFalse(p["corpus_manifest"]["reconstructible_from_repo_alone"])

    def test_02_cli_check_and_standalone_deterministic(self) -> None:
        cert_path = _THIS_DIR / "s107_hypersphere_certificate.json"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(audit.main(["--check", str(cert_path)]), 0)
            self.assertEqual(audit.main(["--standalone", "--track-dir", str(_THIS_DIR)]), 0)
            self.assertEqual(audit.main(["--check", str(cert_path), "--json"]), 0)
            self.assertEqual(audit.main(["--standalone", "--track-dir", str(_THIS_DIR), "--json"]), 0)

    def test_03_certificate_envelope_and_replay_guards(self) -> None:
        cert_path = _THIS_DIR / "s107_hypersphere_certificate.json"
        base = json.loads(cert_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            empty_dir = td_path / "empty_track"
            empty_dir.mkdir()

            # Invalid hex format (including non-str int) for certificate_sha256 and payload_sha256.
            bad_fmt1 = copy.deepcopy(base)
            bad_fmt1["certificate_sha256"] = 12345
            p1 = td_path / "bad_fmt1.json"
            p1.write_text(json.dumps(bad_fmt1), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as ctx1:
                audit.verify_certificate_file(p1, _THIS_DIR)
            self.assertIn("Invalid certificate_sha256 field", str(ctx1.exception))

            bad_fmt2 = copy.deepcopy(base)
            bad_fmt2["payload_sha256"] = 67890
            p2 = td_path / "bad_fmt2.json"
            p2.write_text(json.dumps(bad_fmt2), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as ctx2:
                audit.verify_certificate_file(p2, _THIS_DIR)
            self.assertIn("Invalid payload_sha256 field", str(ctx2.exception))

            # Zeroed certificate_sha256 must fail on envelope check before touching track_dir.
            bad_env = copy.deepcopy(base)
            bad_env["certificate_sha256"] = "0" * 64
            p3 = td_path / "bad_env.json"
            p3.write_text(json.dumps(bad_env), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as ctx3:
                audit.verify_certificate_file(p3, empty_dir)
            self.assertIn("tampered envelope", str(ctx3.exception))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(["--check", str(p3), "--track-dir", str(_THIS_DIR)]), 2)

            # Tampered payload with updated certificate_sha256 but stale payload_sha256 fails before disk replay.
            bad_pay_stale = copy.deepcopy(base)
            bad_pay_stale["payload"]["total_live_gpu_runs"] = 999
            body_no_sig = {k: v for k, v in bad_pay_stale.items() if k != "certificate_sha256"}
            bad_pay_stale["certificate_sha256"] = audit.canonical_sha256(body_no_sig)
            p4 = td_path / "bad_pay_stale.json"
            p4.write_text(json.dumps(bad_pay_stale), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as ctx4:
                audit.verify_certificate_file(p4, empty_dir)
            self.assertIn("tampered payload", str(ctx4.exception))

            # Fully re-signed tampered payload fails specifically on replayed payload_sha256 check.
            bad_pay_resigned = copy.deepcopy(base)
            bad_pay_resigned["payload"]["scorecard"]["graded_verdict"]["H7a"] = "CONFIRMED"
            bad_pay_resigned["payload_sha256"] = audit.canonical_sha256(bad_pay_resigned["payload"])
            body_no_sig = {k: v for k, v in bad_pay_resigned.items() if k != "certificate_sha256"}
            bad_pay_resigned["certificate_sha256"] = audit.canonical_sha256(body_no_sig)
            p5 = td_path / "bad_pay_resigned.json"
            p5.write_text(json.dumps(bad_pay_resigned), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as ctx5:
                audit.verify_certificate_file(p5, _THIS_DIR)
            self.assertIn("Replayed payload_sha256", str(ctx5.exception))

            # Valid payload_sha256 + extra top-level envelope key re-signed fails specifically on replayed certificate_sha256.
            bad_extra = copy.deepcopy(base)
            bad_extra["extra_field"] = "unexpected"
            body_no_sig = {k: v for k, v in bad_extra.items() if k != "certificate_sha256"}
            bad_extra["certificate_sha256"] = audit.canonical_sha256(body_no_sig)
            p6 = td_path / "bad_extra.json"
            p6.write_text(json.dumps(bad_extra), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as ctx6:
                audit.verify_certificate_file(p6, _THIS_DIR)
            self.assertIn("Replayed certificate_sha256", str(ctx6.exception))

    def test_04_mlos_zeroed_sha_unsigned_telemetry_and_track_swap_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_dir(td_path)

            # Case A: Zeroed receipt_sha256 must fail closed.
            mlos_a = td_path / "mlos_zone_b_h7a.json"
            orig_a = json.loads(mlos_a.read_text(encoding="utf-8"))
            z = copy.deepcopy(orig_a)
            z["receipt_sha256"] = "0" * 64
            mlos_a.write_text(json.dumps(z), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)

            # Case B: Unsigned telemetry edit (temperature changed without re-signing) must fail closed.
            u = copy.deepcopy(orig_a)
            u["end_gpu_telemetry"]["temperature_gpu_c"] = 99
            mlos_a.write_text(json.dumps(u), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)

            # Restore H7a receipt, then Case C: copy mlos_zone_b_h7a.json over mlos_zone_b_h7c.json.
            shutil.copy2(_THIS_DIR / "mlos_zone_b_h7a.json", mlos_a)
            shutil.copy2(_THIS_DIR / "mlos_zone_b_h7a.json", td_path / "mlos_zone_b_h7c.json")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)
            # Even with verify_live_bindings=False, duplicate receipt_sha256 across tracks must fail closed!
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path, verify_live_bindings=False)

    def test_05_mlos_field_guards_and_duration_boundary(self) -> None:
        orig_a = json.loads((_THIS_DIR / "mlos_zone_b_h7a.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            p = td_path / "mlos_test.json"

            # Exact duration boundary passes (kills >= to > mutant).
            exact_sec = float(orig_a["execution"]["duration_ms"]) / 1000.0
            p.write_text(json.dumps(orig_a), encoding="utf-8")
            ok_rec = audit.verify_mlos_receipt(p, min_duration_sec=exact_sec)
            self.assertEqual(ok_rec["exit_code"], 0)

            # Shorter duration fails.
            with self.assertRaises(audit.S107AuditError):
                audit.verify_mlos_receipt(p, min_duration_sec=exact_sec + 0.01)

            # Invalid receipt_sha256 format (non-str int) fails before compare_digest.
            bad_fmt = copy.deepcopy(orig_a)
            bad_fmt["receipt_sha256"] = 12345
            p.write_text(json.dumps(bad_fmt), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as ctx_fmt:
                audit.verify_mlos_receipt(p)
            self.assertIn("invalid receipt_sha256 format", str(ctx_fmt.exception))

            # Re-signed invalid field cases must each fail closed individually.
            mutators = [
                lambda r: r.__setitem__("schema", "mlos-run-receipt/v9.9"),
                lambda r: r.__setitem__("clean_hardware_run", False),
                lambda r: r.__setitem__("anomalies", ["thermal_event"]),
                lambda r: r.__setitem__("determinism_zone", "C"),
                lambda r: r["execution"].__setitem__("exit_code", 1),
                lambda r: r["execution"].__setitem__("duration_ms", 0.0),
                lambda r: r["execution"].__setitem__("duration_ms", True),
                lambda r: r.__setitem__("gpu_telemetry_available", False),
                lambda r: r["start_gpu_telemetry"]["clocks_event_reasons"].__setitem__("thermal_throttled", True),
                lambda r: r["end_gpu_telemetry"]["clocks_event_reasons"].__setitem__("slowdown_active", True),
            ]
            for fn in mutators:
                cand = copy.deepcopy(orig_a)
                fn(cand)
                p.write_text(json.dumps(_resign_mlos(cand)), encoding="utf-8")
                with self.assertRaises(audit.S107AuditError):
                    audit.verify_mlos_receipt(p)

            # Wrong expected_receipt_sha256 binding fails.
            p.write_text(json.dumps(orig_a), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.verify_mlos_receipt(p, expected_receipt_sha256="a" * 64)

    def test_06_dynamic_verdict_derivation_h7a_h7c_h7b(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_dir(td_path)

            # 1) H7a synthetic CONFIRMED via BPB win AND via KL win (proves verdict is not hardcoded).
            h7a_path = td_path / "h7a_gpu_results.json"
            h7a_orig = json.loads(h7a_path.read_text(encoding="utf-8"))
            h7a_bpb = copy.deepcopy(h7a_orig)
            for run in h7a_bpb["runs"]:
                if run["arm_name"] == "S3-Polar-Std":
                    run["val"]["bpb"] = 2.00 + 0.001 * int(run["seed"]) / 2026.0
            h7a_path.write_text(json.dumps(h7a_bpb), encoding="utf-8")
            out_a_bpb = audit.audit_h7a(td_path, verify_live_bindings=False)
            self.assertEqual(out_a_bpb["literal_prereg_verdict"], "CONFIRMED")
            self.assertEqual(out_a_bpb["graded_verdict"], "CONFIRMED")

            # Live bindings reject modified H7a results_sha256.
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7a(td_path, verify_live_bindings=True)

            h7a_kl = copy.deepcopy(h7a_orig)
            for run in h7a_kl["runs"]:
                if run["arm_name"] == "S3-Polar-nGPT":
                    run["val"]["bpb"] = 2.48
                    run["ptq_3bit_kl_nats"] = 0.005
            h7a_path.write_text(json.dumps(h7a_kl), encoding="utf-8")
            out_a_kl = audit.audit_h7a(td_path, verify_live_bindings=False)
            self.assertEqual(out_a_kl["literal_prereg_verdict"], "CONFIRMED")

            # 2) H7c synthetic FALSIFIED (no criterion fires) AND synthetic CONFIRMED (beats RandRot + R6).
            h7c_path = td_path / "h7c_gpu_results.json"
            h7c_orig = json.loads(h7c_path.read_text(encoding="utf-8"))
            h7c_fail = copy.deepcopy(h7c_orig)
            for run in h7c_fail["runs"]:
                if run["arm_name"] == "CliffordTorus-HopfLoop":
                    run["val"]["bpb"] = 3.20
                    run["r_test_extrapolation_bpb"]["R6"] = 8.0
                    run["m1_h1_4bit"]["delta_r_over_delta_1"] = 4.0
            h7c_path.write_text(json.dumps(h7c_fail), encoding="utf-8")
            out_c_fail = audit.audit_h7c(td_path, verify_live_bindings=False)
            self.assertEqual(out_c_fail["literal_prereg_verdict"], "FALSIFIED")
            self.assertEqual(out_c_fail["graded_verdict"], "FALSIFIED")
            self.assertIsNone(out_c_fail["post_hoc_reason"])

            # Live bindings reject modified H7c results_sha256.
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7c(td_path, verify_live_bindings=True)

            h7c_conf = copy.deepcopy(h7c_orig)
            for run in h7c_conf["runs"]:
                if run["arm_name"] == "CliffordTorus-HopfLoop":
                    run["val"]["bpb"] = 2.30
                    run["r_test_extrapolation_bpb"]["R6"] = 2.50
                    run["m1_h1_4bit"]["delta_r_over_delta_1"] = 1.50
            h7c_path.write_text(json.dumps(h7c_conf), encoding="utf-8")
            out_c_conf = audit.audit_h7c(td_path, verify_live_bindings=False)
            self.assertEqual(out_c_conf["literal_prereg_verdict"], "CONFIRMED")
            self.assertEqual(out_c_conf["graded_verdict"], "CONFIRMED")
            self.assertIsNone(out_c_conf["post_hoc_reason"])

            # 3) H7b synthetic CONFIRMED (T2048 win + no T512 regression) AND synthetic FALSIFIED (no win).
            h7b_path = td_path / "h7b_gpu_results.json"
            h7b_orig = json.loads(h7b_path.read_text(encoding="utf-8"))
            h7b_conf = copy.deepcopy(h7b_orig)
            for run in h7b_conf["runs"]:
                if run["arm_name"] == "SU2-Holonomy-Scan-nGPT":
                    run["val"]["bpb"] = 2.65
            h7b_path.write_text(json.dumps(h7b_conf), encoding="utf-8")
            out_b_conf = audit.audit_h7b(td_path, verify_live_bindings=False)
            self.assertEqual(out_b_conf["literal_prereg_verdict"], "CONFIRMED")
            self.assertEqual(out_b_conf["graded_verdict"], "CONFIRMED")
            self.assertIsNone(out_b_conf["post_hoc_reason"])

            # Live bindings reject modified H7b results_sha256.
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7b(td_path, verify_live_bindings=True)

            h7b_fail = copy.deepcopy(h7b_orig)
            for run in h7b_fail["runs"]:
                if run["arm_name"] == "SU2-Holonomy-Scan-nGPT":
                    run["val"]["bpb"] = 2.95
                    run["length_extrapolation_bpb"]["T2048"] = 3.20
            h7b_path.write_text(json.dumps(h7b_fail), encoding="utf-8")
            out_b_fail = audit.audit_h7b(td_path, verify_live_bindings=False)
            self.assertEqual(out_b_fail["literal_prereg_verdict"], "FALSIFIED")
            self.assertEqual(out_b_fail["graded_verdict"], "FALSIFIED")
            self.assertIsNone(out_b_fail["post_hoc_reason"])

    def test_07_cs08_parity_and_run_count_guards_h7a_h7c_h7b(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_dir(td_path)

            # H7a: run count guard, param > 0.5%, flop > 1.0%, and exact boundaries (0.5%, 1.0%).
            h7a_p = td_path / "h7a_gpu_results.json"
            h7a_orig = json.loads(h7a_p.read_text(encoding="utf-8"))
            ref_p = int(next(r for r in h7a_orig["runs"] if r["arm_name"] == "Cyl-Std")["params"]["non_embedding_params"])
            ref_f = int(next(r for r in h7a_orig["runs"] if r["arm_name"] == "Cyl-Std")["flops"]["total_fwd_flops_per_token"])

            # Exact boundary 0.5% params and 1.0% flops passes (kills <= -> < flips).
            exact_a = copy.deepcopy(h7a_orig)
            for r in exact_a["runs"]:
                if r["arm_name"] == "S3-Polar-Std":
                    r["params"]["non_embedding_params"] = ref_p + (ref_p // 200)  # exact 0.5%
                    r["flops"]["total_fwd_flops_per_token"] = ref_f + (ref_f // 100)  # exact 1.0%
            h7a_p.write_text(json.dumps(exact_a), encoding="utf-8")
            out_ex = audit.audit_h7a(td_path, verify_live_bindings=False)
            self.assertEqual(out_ex["max_non_emb_param_diff_pct"], 0.5)
            self.assertEqual(out_ex["max_flop_diff_pct"], 1.0)

            bad_a_p = copy.deepcopy(h7a_orig)
            for r in bad_a_p["runs"]:
                if r["arm_name"] == "S3-Polar-Std":
                    r["params"]["non_embedding_params"] = int(ref_p * 1.01)
            h7a_p.write_text(json.dumps(bad_a_p), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7a(td_path, verify_live_bindings=False)

            bad_a_f = copy.deepcopy(h7a_orig)
            for r in bad_a_f["runs"]:
                if r["arm_name"] == "S3-Polar-Std":
                    r["flops"]["total_fwd_flops_per_token"] = int(ref_f * 1.02)
            h7a_p.write_text(json.dumps(bad_a_f), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7a(td_path, verify_live_bindings=False)

            bad_a_cnt = copy.deepcopy(h7a_orig)
            bad_a_cnt["runs"] = bad_a_cnt["runs"][:-1]
            h7a_p.write_text(json.dumps(bad_a_cnt), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7a(td_path, verify_live_bindings=False)

            # H7c: exact boundaries (0.5%, 5.0%), param > 0.5%, flop > 5.0%, and run count guard.
            h7c_p = td_path / "h7c_gpu_results.json"
            h7c_orig = json.loads(h7c_p.read_text(encoding="utf-8"))
            ref_p8 = int(next(r for r in h7c_orig["runs"] if r["arm_name"] == "Unlooped-8L")["params"]["non_embedding_params"])
            ref_f16 = int(next(r for r in h7c_orig["runs"] if r["arm_name"] == "Unlooped-16L")["flops"]["total_fwd_flops_per_token"])

            exact_c = copy.deepcopy(h7c_orig)
            for r in exact_c["runs"]:
                if r["arm_name"] == "FlatLoop-Std":
                    r["params"]["non_embedding_params"] = ref_p8 + (ref_p8 // 200)  # exact 0.5%
                    r["flops"]["total_fwd_flops_per_token"] = ref_f16 + (ref_f16 // 20)  # exact 5.0%
            h7c_p.write_text(json.dumps(exact_c), encoding="utf-8")
            out_ex_c = audit.audit_h7c(td_path, verify_live_bindings=False)
            self.assertEqual(out_ex_c["max_looped_vs_8L_param_diff_pct"], 0.5)
            self.assertEqual(out_ex_c["max_looped_vs_16L_flop_diff_pct"], 5.0)

            bad_c_p = copy.deepcopy(h7c_orig)
            for r in bad_c_p["runs"]:
                if r["arm_name"] == "FlatLoop-Std":
                    r["params"]["non_embedding_params"] = int(ref_p8 * 1.01)
            h7c_p.write_text(json.dumps(bad_c_p), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7c(td_path, verify_live_bindings=False)

            bad_c_f = copy.deepcopy(h7c_orig)
            for r in bad_c_f["runs"]:
                if r["arm_name"] == "FlatLoop-Std":
                    r["flops"]["total_fwd_flops_per_token"] = int(ref_f16 * 1.06)
            h7c_p.write_text(json.dumps(bad_c_f), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7c(td_path, verify_live_bindings=False)

            bad_c_cnt = copy.deepcopy(h7c_orig)
            bad_c_cnt["probes"] = bad_c_cnt["probes"][:-1]
            h7c_p.write_text(json.dumps(bad_c_cnt), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7c(td_path, verify_live_bindings=False)

            # H7b: exact boundaries (0.5%, 1.0%), param > 0.5%, flop > 1.0%, and run count guard.
            h7b_p = td_path / "h7b_gpu_results.json"
            h7b_orig = json.loads(h7b_p.read_text(encoding="utf-8"))
            ref_pb = int(next(r for r in h7b_orig["runs"] if r["arm_name"] == "RoPE-2D-nGPT")["params"]["non_embedding_params"])
            ref_fb = int(next(r for r in h7b_orig["runs"] if r["arm_name"] == "RoPE-2D-nGPT")["flops"]["total_fwd_flops_per_token"])

            # Note ref_pb=14900737 is not divisible by 200; set both ref and target to divisible 14_900_000 for exact 0.5%.
            exact_b = copy.deepcopy(h7b_orig)
            for r in exact_b["runs"]:
                r["params"]["non_embedding_params"] = 14_900_000
                r["flops"]["total_fwd_flops_per_token"] = 34_000_000
                if r["arm_name"] == "SU2-Holonomy-Scan-nGPT":
                    r["params"]["non_embedding_params"] = 14_900_000 + 74_500  # exact 0.5%
                    r["flops"]["total_fwd_flops_per_token"] = 34_000_000 + 340_000  # exact 1.0%
            h7b_p.write_text(json.dumps(exact_b), encoding="utf-8")
            out_ex_b = audit.audit_h7b(td_path, verify_live_bindings=False)
            self.assertEqual(out_ex_b["max_non_emb_param_diff_pct"], 0.5)
            self.assertEqual(out_ex_b["max_flop_diff_pct"], 1.0)

            bad_b_p = copy.deepcopy(h7b_orig)
            for r in bad_b_p["runs"]:
                if r["arm_name"] == "SU2-Holonomy-Scan-nGPT":
                    r["params"]["non_embedding_params"] = int(ref_pb * 1.01)
            h7b_p.write_text(json.dumps(bad_b_p), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7b(td_path, verify_live_bindings=False)

            bad_b_f = copy.deepcopy(h7b_orig)
            for r in bad_b_f["runs"]:
                if r["arm_name"] == "SU2-Holonomy-Scan-nGPT":
                    r["flops"]["total_fwd_flops_per_token"] = int(ref_fb * 1.02)
            h7b_p.write_text(json.dumps(bad_b_f), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7b(td_path, verify_live_bindings=False)

            bad_b_cnt = copy.deepcopy(h7b_orig)
            bad_b_cnt["runs"] = bad_b_cnt["runs"][:-1]
            h7b_p.write_text(json.dumps(bad_b_cnt), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.audit_h7b(td_path, verify_live_bindings=False)

    def test_08_preflight_corpus_manifest_and_digest_guards(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_dir(td_path)

            # Preflight gates_passed != 9 fails.
            pre_p = td_path / "s107_cpu_preflight_receipt.json"
            orig_pre = json.loads(pre_p.read_text(encoding="utf-8"))
            bad_g = copy.deepcopy(orig_pre)
            bad_g["payload"]["gates_passed"] = 8
            bad_g["payload_sha256"] = audit.canonical_sha256(bad_g["payload"])
            pre_p.write_text(json.dumps(bad_g), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)

            # Preflight invalid payload_sha256 format (non-str int) fails before compare_digest.
            bad_pre_fmt = copy.deepcopy(orig_pre)
            bad_pre_fmt["payload_sha256"] = 12345
            pre_p.write_text(json.dumps(bad_pre_fmt), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as ctx_pf:
                audit.build_certificate(td_path)
            self.assertIn("invalid format", str(ctx_pf.exception))

            # Preflight payload_sha256 mismatch fails.
            bad_pre_sha = copy.deepcopy(orig_pre)
            bad_pre_sha["payload_sha256"] = "f" * 64
            pre_p.write_text(json.dumps(bad_pre_sha), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)

            # Restore preflight; test invalid corpus_manifest.json schema.
            shutil.copy2(_THIS_DIR / "s107_cpu_preflight_receipt.json", pre_p)
            man_p = td_path / "corpus_manifest.json"
            bad_man = json.loads(man_p.read_text(encoding="utf-8"))
            bad_man["schema_version"] = "wrong"
            man_p.write_text(json.dumps(bad_man), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)

            # Restore manifest; test H7b/H7c train and eval corpus digest mismatch (with verify_live_bindings=False).
            shutil.copy2(_THIS_DIR / "corpus_manifest.json", man_p)
            h7b_p = td_path / "h7b_gpu_results.json"
            orig_h7b = json.loads(h7b_p.read_text(encoding="utf-8"))

            bad_tr = copy.deepcopy(orig_h7b)
            bad_tr["corpus"]["train_sha256"] = "0" * 64
            h7b_p.write_text(json.dumps(bad_tr), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path, verify_live_bindings=False)

            bad_ev = copy.deepcopy(orig_h7b)
            bad_ev["corpus"]["eval_sha256"] = "0" * 64
            h7b_p.write_text(json.dumps(bad_ev), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path, verify_live_bindings=False)

    def test_09_json_tree_stats_and_missing_file_guards(self) -> None:
        # Non-str key fails.
        with self.assertRaises(audit.S107AuditError):
            audit.check_json_tree_iterative({1: "bad"})

        # Exact depth=64 passes; depth=65 fails (kills > -> >= flip).
        d64: Dict[str, Any] = {}
        cur = d64
        for _ in range(64):
            nxt: Dict[str, Any] = {}
            cur["a"] = nxt
            cur = nxt
        audit.check_json_tree_iterative(d64, max_depth=64)
        cur["a"] = {}
        with self.assertRaises(audit.S107AuditError):
            audit.check_json_tree_iterative(d64, max_depth=64)

        # mean_se and paired_stats boundary checks (n=2 passes, n=1 and mismatch fail).
        self.assertEqual(audit.mean_se([1.0, 3.0]), (2.0, 1.0))
        with self.assertRaises(audit.S107AuditError):
            audit.mean_se([1.0])
        ps = audit.paired_stats([2.0, 4.0], [1.0, 1.0])
        self.assertEqual(ps["df"], 1)
        with self.assertRaises(audit.S107AuditError):
            audit.paired_stats([1.0], [1.0])
        with self.assertRaises(audit.S107AuditError):
            audit.paired_stats([1.0, 2.0], [1.0])

        # _index_runs guards: seeds != 3 and empty runs list.
        with self.assertRaises(audit.S107AuditError):
            audit._index_runs({"seeds": [42, 137], "runs": [{"arm_name": "a", "seed": 42}]})
        with self.assertRaises(audit.S107AuditError):
            audit._index_runs({"seeds": [42, 137, 2026], "runs": []})

        # Missing file, malformed JSON, non-dict top-level JSON, and sha256_file missing.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            with self.assertRaises(audit.S107AuditError) as ctx_sf:
                audit.sha256_file(td_path / "absent.bin")
            self.assertIn("Missing required artifact file", str(ctx_sf.exception))
            with self.assertRaises(audit.S107AuditError) as ctx_js:
                audit.load_json_strict(td_path / "absent.json")
            self.assertIn("Missing required JSON file", str(ctx_js.exception))
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(["--check", str(td_path / "missing.json")]), 2)

            bad_json = td_path / "broken.json"
            bad_json.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.load_json_strict(bad_json)

            arr_json = td_path / "arr.json"
            arr_json.write_text("[1, 2, 3]", encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.load_json_strict(arr_json)


if __name__ == "__main__":
    unittest.main()
