#!/usr/bin/env python3
"""Assertion-free pure-stdlib R5 test suite for Track S109 (PREREG-S109 + Amendments 1-3).

Zero external dependencies (no torch, no numpy); deterministic stdout (0 stdout bytes) across
-I -B, -I -O -B, and -I -B -W error.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s109_terracore_audit as audit  # noqa: E402


def _copy_track_tree(dst: Path) -> None:
    for fname in (
        "PREREG_S109_MINIMAL_MEDIUM_CORE_AND_TRANSLATOR.md",
        "PREREG_S109_AMENDMENT1_COUNCIL_HARDENING.md",
        "PREREG_S109_AMENDMENT2_GEODYNAMIC_TERRACORE.md",
        "PREREG_S109_AMENDMENT3_STEELMAN_REPAIR.md",
        "mlos_zone_b_s109_h9a.json",
        "mlos_zone_b_s109_h9a_v2.json",
        "mlos_zone_b_s109_terracore.json",
        "s109_terracore_certificate.json",
    ):
        shutil.copy2(_THIS_DIR / fname, dst / fname)
    for sub in ("gpu_results_h9a", "gpu_results_h9a_v2", "gpu_results_terracore"):
        (dst / sub).mkdir(parents=True, exist_ok=True)
        for jname in ("s109_locked_protocol.json", "s109_gpu_full_results.json"):
            shutil.copy2(_THIS_DIR / sub / jname, dst / sub / jname)


class TestTrackS109TerraCoreAuditR5(unittest.TestCase):
    def test_01_live_certificate_check_passes(self) -> None:
        cert_path = _THIS_DIR / "s109_terracore_certificate.json"
        cert = audit.verify_certificate_file(cert_path, _THIS_DIR)
        p = cert["payload"]
        self.assertEqual(p["total_neural_models_trained"], 114)
        self.assertEqual(p["total_plate_seam_routers_calibrated"], 18)
        self.assertEqual(p["locked_seeds"], [42, 137, 2026])
        pins = p["prereg_sha256_pins"]
        self.assertEqual(pins["PREREG_S109_MINIMAL_MEDIUM_CORE_AND_TRANSLATOR.md"], audit.PREREG_S109_SHA256)
        self.assertEqual(pins["PREREG_S109_AMENDMENT1_COUNCIL_HARDENING.md"], audit.AMENDMENT1_SHA256)
        self.assertEqual(pins["PREREG_S109_AMENDMENT2_GEODYNAMIC_TERRACORE.md"], audit.AMENDMENT2_SHA256)
        self.assertEqual(pins["PREREG_S109_AMENDMENT3_STEELMAN_REPAIR.md"], audit.AMENDMENT3_SHA256)

        sc = p["scorecard"]
        self.assertEqual(sc["H9a"], "CONFIRMED")
        self.assertEqual(sc["H9b"], "FALSIFIED")
        self.assertEqual(sc["H9c"], "FALSIFIED")
        self.assertEqual(sc["H9d"], "FALSIFIED")
        self.assertEqual(sc["n2_claims"], 0)
        self.assertEqual(sc["weights_saved"], 0)

        h9a = p["h9a_v2_steelman"]
        self.assertEqual(h9a["arm_a_r1"]["mean"], 1.0)
        self.assertAlmostEqual(h9a["arm_a_r2"]["mean"], 0.99821, places=5)
        self.assertEqual(h9a["decompressor_emulation"]["regime2_exact_str_acc"]["mean"], 0.0)
        self.assertGreater(h9a["probe_lm_predictivity"]["deflate_to_english_ratio"], 13.0)

        tc = p["terracore_h9b_h9c_h9d"]
        self.assertEqual(tc["parity"]["P_mono"], 15023648)
        self.assertEqual(tc["parity"]["P_terra"], 15003063)
        self.assertAlmostEqual(tc["parity"]["P_ratio"], 0.99863, places=4)
        self.assertAlmostEqual(tc["parity"]["F_ratio"], 0.994948, places=4)
        self.assertAlmostEqual(tc["seed42_y025_dpi_recovery_pct"], 93.98, places=2)
        self.assertEqual(tc["security_and_geometry"]["cs21_leak_triggers"], 0)
        self.assertEqual(tc["security_and_geometry"]["mhplate_en_ar_ir_exact_match"], 1.0)
        self.assertAlmostEqual(tc["cross_track_comparisons"]["h9b_native_r1_speedup_vs_arm_a"], 1.6138, places=3)
        self.assertAlmostEqual(tc["cross_track_comparisons"]["h9b_native_r1_vram_reduction_vs_arm_a"], 2.4645, places=3)

    def test_02_cli_check_and_standalone_bit_identical(self) -> None:
        cert_path = _THIS_DIR / "s109_terracore_certificate.json"
        out1, out2, out3 = io.StringIO(), io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out1):
            rc1 = audit.main(["--check", str(cert_path)])
        with contextlib.redirect_stdout(out2):
            rc2 = audit.main(["--standalone", "--track-dir", str(_THIS_DIR)])
        with contextlib.redirect_stdout(out3):
            rc3 = audit.main(["--track-dir", str(_THIS_DIR)])
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        self.assertEqual(rc3, 0)
        self.assertEqual(out1.getvalue(), out2.getvalue())
        self.assertEqual(out1.getvalue(), out3.getvalue())
        self.assertIn("OK track-s109-minimal-medium-terracore models=114 routers=18", out1.getvalue())

    def test_03_tampered_certificate_hash_fails_closed(self) -> None:
        cert_path = _THIS_DIR / "s109_terracore_certificate.json"
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad_cert.json"
            obj = json.loads(cert_path.read_text(encoding="utf-8"))
            obj["certificate_sha256"] = "0" * 64
            bad.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S109AuditError):
                audit.verify_certificate_file(bad, _THIS_DIR)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = audit.main(["--check", str(bad), "--track-dir", str(_THIS_DIR)])
            self.assertEqual(rc, 2)
            self.assertIn("FAIL:", err.getvalue())

    def test_04_tampered_payload_verdict_resigned_fails_closed(self) -> None:
        cert_path = _THIS_DIR / "s109_terracore_certificate.json"
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad_payload.json"
            obj = json.loads(cert_path.read_text(encoding="utf-8"))
            obj["payload"]["scorecard"]["H9d"] = "CONFIRMED"
            obj["payload_sha256"] = audit.canonical_sha256(obj["payload"])
            body_no_sig = {k: v for k, v in obj.items() if k != "certificate_sha256"}
            obj["certificate_sha256"] = audit.canonical_sha256(body_no_sig)
            bad.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S109AuditError):
                audit.verify_certificate_file(bad, _THIS_DIR)

    def test_05_tampered_mlos_dirty_hardware_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            mlos_p = td_path / "mlos_zone_b_s109_terracore.json"
            m = json.loads(mlos_p.read_text(encoding="utf-8"))
            m["clean_hardware_run"] = False
            no_sha = {k: v for k, v in m.items() if k != "receipt_sha256"}
            m["receipt_sha256"] = audit.canonical_sha256(no_sha)
            mlos_p.write_text(json.dumps(m), encoding="utf-8")
            with self.assertRaises(audit.S109AuditError):
                audit.build_certificate(td_path)

    def test_06_tampered_raw_gpu_result_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            res_p = td_path / "gpu_results_terracore" / "s109_gpu_full_results.json"
            obj = json.loads(res_p.read_text(encoding="utf-8"))
            obj["results"]["per_seed"]["42"]["h9d_yield_sweep"]["Y_0.50"]["core_sha_unchanged"] = False
            res_p.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S109AuditError):
                audit.build_certificate(td_path)

    def test_07_tampered_prereg_doc_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            (td_path / "PREREG_S109_AMENDMENT3_STEELMAN_REPAIR.md").write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(audit.S109AuditError):
                audit.build_certificate(td_path)

    def test_08_tampered_tuple_overlap_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            res_p = td_path / "gpu_results_h9a_v2" / "s109_gpu_full_results.json"
            obj = json.loads(res_p.read_text(encoding="utf-8"))
            obj["results"]["per_seed"]["42"]["train_eval_tuple_overlap"]["regime1"] = 1
            no_sha = {k: v for k, v in obj.items() if k != "result_sha256"}
            obj["result_sha256"] = audit.canonical_sha256(no_sha)
            res_p.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S109AuditError):
                audit.build_certificate(td_path)

    def test_09_non_str_key_and_depth_guard_fail_closed(self) -> None:
        with self.assertRaises(audit.S109AuditError):
            audit.check_json_tree_iterative({1: "bad"})
        deep: dict = {}
        cur = deep
        for _ in range(70):
            nxt: dict = {}
            cur["a"] = nxt
            cur = nxt
        with self.assertRaises(audit.S109AuditError):
            audit.check_json_tree_iterative(deep)

    def test_10_missing_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(audit.S109AuditError):
                audit.build_certificate(Path(td))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = audit.main(["--check", str(Path(td) / "missing.json")])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
