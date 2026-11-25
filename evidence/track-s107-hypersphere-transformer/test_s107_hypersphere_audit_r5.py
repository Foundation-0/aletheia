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


if __name__ == "__main__":
    unittest.main()
