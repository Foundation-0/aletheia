#!/usr/bin/env python3
"""Assertion-free pure-stdlib R5 test suite for Track S107 (PREREG-S107 + Amendment 1)."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s107_hypersphere_audit as audit


class TestTrackS107HypersphereAuditR5(unittest.TestCase):
    def test_01_live_certificate_check_passes(self) -> None:
        cert_path = _THIS_DIR / "s107_hypersphere_certificate.json"
        cert = audit.verify_certificate_file(cert_path, _THIS_DIR)
        p = cert["payload"]
        self.assertEqual(p["total_live_gpu_runs"], 111)
        self.assertEqual(p["scorecard"]["H7a"], "FALSIFIED")
        self.assertEqual(p["scorecard"]["H7c"], "PARTIAL")
        self.assertEqual(p["scorecard"]["H7b"], "PARTIAL")
        self.assertEqual(p["scorecard"]["n2_claims"], 0)
        self.assertEqual(p["scorecard"]["weights_saved"], 0)
        self.assertEqual(p["cpu_preflight"]["gates_passed"], 9)
        self.assertEqual(p["h7b"]["su2_over_rope_wall_clock_ratio"], 3.9125)

    def test_02_cli_check_and_standalone_deterministic(self) -> None:
        cert_path = _THIS_DIR / "s107_hypersphere_certificate.json"
        rc1 = audit.main(["--check", str(cert_path)])
        rc2 = audit.main(["--standalone", "--track-dir", str(_THIS_DIR)])
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)

    def test_03_tampered_certificate_hash_fails_closed(self) -> None:
        cert_path = _THIS_DIR / "s107_hypersphere_certificate.json"
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad_cert.json"
            obj = json.loads(cert_path.read_text(encoding="utf-8"))
            obj["certificate_sha256"] = "0" * 64
            bad.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.verify_certificate_file(bad, _THIS_DIR)
            self.assertEqual(audit.main(["--check", str(bad), "--track-dir", str(_THIS_DIR)]), 2)

    def test_04_tampered_payload_verdict_fails_closed(self) -> None:
        cert_path = _THIS_DIR / "s107_hypersphere_certificate.json"
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad_payload.json"
            obj = json.loads(cert_path.read_text(encoding="utf-8"))
            obj["payload"]["scorecard"]["H7a"] = "CONFIRMED"
            body_no_sig = {k: v for k, v in obj.items() if k != "certificate_sha256"}
            obj["payload_sha256"] = audit.canonical_sha256(obj["payload"])
            body_no_sig["payload_sha256"] = obj["payload_sha256"]
            obj["certificate_sha256"] = audit.canonical_sha256(body_no_sig)
            bad.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.verify_certificate_file(bad, _THIS_DIR)

    def test_05_tampered_mlos_dirty_hardware_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            for fname in (
                "h7a_gpu_results.json",
                "h7b_gpu_results.json",
                "h7c_gpu_results.json",
                "mlos_zone_b_h7a.json",
                "mlos_zone_b_h7b.json",
                "mlos_zone_b_h7c.json",
                "s107_cpu_preflight_receipt.json",
            ):
                shutil.copy2(_THIS_DIR / fname, td_path / fname)
            mlos_p = td_path / "mlos_zone_b_h7a.json"
            m = json.loads(mlos_p.read_text(encoding="utf-8"))
            m["clean_hardware_run"] = False
            mlos_p.write_text(json.dumps(m), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)

    def test_06_tampered_preflight_receipt_sha_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            for fname in (
                "h7a_gpu_results.json",
                "h7b_gpu_results.json",
                "h7c_gpu_results.json",
                "mlos_zone_b_h7a.json",
                "mlos_zone_b_h7b.json",
                "mlos_zone_b_h7c.json",
                "s107_cpu_preflight_receipt.json",
            ):
                shutil.copy2(_THIS_DIR / fname, td_path / fname)
            pre_p = td_path / "s107_cpu_preflight_receipt.json"
            p = json.loads(pre_p.read_text(encoding="utf-8"))
            p["payload_sha256"] = "f" * 64
            pre_p.write_text(json.dumps(p), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(td_path)

    def test_07_non_str_key_and_depth_guard_fail_closed(self) -> None:
        with self.assertRaises(audit.S107AuditError):
            audit.check_json_tree_iterative({1: "bad"})
        deep: dict = {}
        cur = deep
        for _ in range(70):
            nxt: dict = {}
            cur["a"] = nxt
            cur = nxt
        with self.assertRaises(audit.S107AuditError):
            audit.check_json_tree_iterative(deep)

    def test_08_missing_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(audit.S107AuditError):
                audit.build_certificate(Path(td))
            self.assertEqual(audit.main(["--check", str(Path(td) / "missing.json")]), 2)

    def test_09_receipt_binding_attacks_and_computed_verdicts(self) -> None:
        def _copy_track(td: Path) -> Path:
            for fname in (
                "h7a_gpu_results.json", "h7b_gpu_results.json", "h7c_gpu_results.json",
                "mlos_zone_b_h7a.json", "mlos_zone_b_h7b.json", "mlos_zone_b_h7c.json",
                "s107_cpu_preflight_receipt.json",
            ):
                shutil.copy2(_THIS_DIR / fname, td / fname)
            return td

        # Positive: shipped receipts verify with recomputed self-hash + results binding.
        cert = audit.build_certificate(_THIS_DIR)
        self.assertEqual(cert["payload"]["scorecard"]["literal_prereg_verdicts"],
                         {"H7a": "FALSIFIED", "H7c": "CONFIRMED", "H7b": "FALSIFIED"})
        self.assertEqual(cert["payload"]["scorecard"]["H7c"], "PARTIAL")
        self.assertEqual(cert["payload"]["scorecard"]["H7b"], "PARTIAL")

        # Attack 1: zeroed receipt_sha256 -> MLOS_RECEIPT_SHA_MISMATCH.
        with tempfile.TemporaryDirectory() as td:
            d = _copy_track(Path(td))
            rp = d / "mlos_zone_b_h7a.json"
            m = json.loads(rp.read_text(encoding="utf-8"))
            m["receipt_sha256"] = "0" * 64
            rp.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as cm:
                audit.build_certificate(d)
            self.assertIn("MLOS_RECEIPT_SHA_MISMATCH", str(cm.exception))

        # Attack 2: unsigned telemetry edit (self-hash not recomputed) -> mismatch.
        with tempfile.TemporaryDirectory() as td:
            d = _copy_track(Path(td))
            rp = d / "mlos_zone_b_h7b.json"
            m = json.loads(rp.read_text(encoding="utf-8"))
            m["start_gpu_telemetry"]["pkg_w_mean"] = 999.0
            rp.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")
            with self.assertRaises(audit.S107AuditError) as cm:
                audit.build_certificate(d)
            self.assertIn("MLOS_RECEIPT_SHA_MISMATCH", str(cm.exception))

        # Attack 3: H7a receipt copied over the H7c receipt -> binding failure.
        with tempfile.TemporaryDirectory() as td:
            d = _copy_track(Path(td))
            shutil.copy2(d / "mlos_zone_b_h7a.json", d / "mlos_zone_b_h7c.json")
            with self.assertRaises(audit.S107AuditError) as cm:
                audit.build_certificate(d)
            self.assertIn("MLOS_NOT_BOUND_TO_RESULTS", str(cm.exception))

        # Verdicts are computed from gate booleans: flipping one gate input changes the
        # literal verdict instead of raising a hardcoded-pattern error.
        with tempfile.TemporaryDirectory() as td:
            d = _copy_track(Path(td))
            rp = d / "h7c_gpu_results.json"
            r = json.loads(rp.read_text(encoding="utf-8"))
            # make criterion 1 fail: worsen CliffordTorus-HopfLoop R3 BPB vs FlatLoop-Std
            for run in r["runs"]:
                if run["arm_name"] == "CliffordTorus-HopfLoop":
                    run["val"]["bpb"] = run["val"]["bpb"] * 1.05
            rp.write_text(json.dumps(r, indent=2, sort_keys=True), encoding="utf-8")
            # rebind the h7c receipt to the edited results file (else binding fires first)
            import hashlib as _hl
            mrec_p = d / "mlos_zone_b_h7c.json"
            mrec = json.loads(mrec_p.read_text(encoding="utf-8"))
            mrec["bound_results_sha256"] = _hl.sha256(rp.read_bytes()).hexdigest()
            body = {k: v for k, v in mrec.items() if k != "receipt_sha256"}
            mrec["receipt_sha256"] = _hl.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            mrec_p.write_text(json.dumps(mrec, indent=2, sort_keys=True), encoding="utf-8")
            cert2 = audit.build_certificate(d)
            self.assertEqual(cert2["payload"]["h7c"]["literal_prereg_verdict"], "FALSIFIED")
            self.assertNotEqual(cert2["payload"]["h7c"]["verdict"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
