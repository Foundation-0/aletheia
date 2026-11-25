#!/usr/bin/env python3
"""Assertion-free pure-stdlib R5 test suite for Track S108 (PREREG-S108 + Amendment 1).

Zero external dependencies (no torch, no numpy); deterministic stdout across
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

import s108_tokenizer_loop_audit as audit  # noqa: E402


def _copy_track_tree(dst: Path) -> None:
    for fname in (
        "PREREG_S108_TOKENIZER_LOOPING_BRIDGE.md",
        "PREREG_S107_S108_AMENDMENT1.md",
        "mlos_zone_b_h8a_receipt.json",
        "mlos_zone_b_h8b_receipt.json",
        "mlos_zone_b_h8c_receipt.json",
        "s108_tokenizer_loop_certificate.json",
    ):
        shutil.copy2(_THIS_DIR / fname, dst / fname)
    for sub in ("gpu_results_h8a", "gpu_results_h8b", "gpu_results_h8c"):
        (dst / sub).mkdir(parents=True, exist_ok=True)
        for jname in ("s108_locked_protocol.json", "s108_gpu_full_results.json"):
            shutil.copy2(_THIS_DIR / sub / jname, dst / sub / jname)


class TestTrackS108TokenizerLoopAuditR5(unittest.TestCase):
    def test_01_live_certificate_check_passes(self) -> None:
        cert_path = _THIS_DIR / "s108_tokenizer_loop_certificate.json"
        cert = audit.verify_certificate_file(cert_path, _THIS_DIR)
        p = cert["payload"]
        self.assertEqual(p["total_live_gpu_runs"], 51)
        self.assertEqual(p["part3_nullmodem_seeds"], 3)
        self.assertEqual(p["prereg_sha256"], audit.PREREG_S108_SHA256)
        self.assertEqual(p["amendment1_sha256"], audit.AMENDMENT1_SHA256)
        sc = p["scorecard"]
        self.assertEqual(sc["H8a"], "FALSIFIED")
        self.assertEqual(sc["H8b"], "FALSIFIED")
        self.assertEqual(sc["H8c_Part1"], "FALSIFIED")
        self.assertEqual(sc["H8c_Part2"], "FALSIFIED")  # preregistered gate (BPE leg unrun, params not matched)
        self.assertEqual(sc["H8c_Part2_vs_LocalAR"], "EXPLORATORY_N0")
        self.assertEqual(sc["H8c_Part3"], "FALSIFIED")  # preregistered total-wire gate; no PARTIAL tier
        self.assertEqual(sc["n2_claims"], 0)
        self.assertEqual(sc["weights_saved"], 0)
        self.assertAlmostEqual(p["h8a"]["embed_compression_ratio"], 28.9811, places=4)
        self.assertAlmostEqual(p["h8b"]["arms"]["spherepatch_geodesic2"]["mean_avg_patch_len"], 1.02, places=3)
        self.assertAlmostEqual(p["h8b"]["turing_diagnostic"]["diff_D_1_10"]["mean_boundary_period"], 3.2222, places=4)
        self.assertEqual(p["h8b"]["turing_diagnostic"]["equal_D_5_5_null"]["mean_boundary_period_sentinel"], 32.0)
        self.assertAlmostEqual(p["h8c"]["part2_mtp8_vs_ar"]["markov_vs_parallel_tf"]["rel_pct"], -19.3361, places=4)
        self.assertEqual(p["h8c"]["part3_nullmodem"]["payload_bits"], 32)
        self.assertEqual(p["h8c"]["part3_nullmodem"]["total_wire_bits"], 352.0)

    def test_02_cli_check_and_standalone_bit_identical(self) -> None:
        cert_path = _THIS_DIR / "s108_tokenizer_loop_certificate.json"
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
        self.assertIn("OK track-s108-tokenizer-looping-bridge runs=51", out1.getvalue())

    def test_03_tampered_certificate_hash_fails_closed(self) -> None:
        cert_path = _THIS_DIR / "s108_tokenizer_loop_certificate.json"
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad_cert.json"
            obj = json.loads(cert_path.read_text(encoding="utf-8"))
            obj["certificate_sha256"] = "0" * 64
            bad.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.verify_certificate_file(bad, _THIS_DIR)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = audit.main(["--check", str(bad), "--track-dir", str(_THIS_DIR)])
            self.assertEqual(rc, 2)
            self.assertIn("FAIL:", err.getvalue())

    def test_04_tampered_payload_verdict_resigned_fails_closed(self) -> None:
        cert_path = _THIS_DIR / "s108_tokenizer_loop_certificate.json"
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad_payload.json"
            obj = json.loads(cert_path.read_text(encoding="utf-8"))
            obj["payload"]["scorecard"]["H8a"] = "CONFIRMED"
            obj["payload_sha256"] = audit.canonical_sha256(obj["payload"])
            body_no_sig = {k: v for k, v in obj.items() if k != "certificate_sha256"}
            obj["certificate_sha256"] = audit.canonical_sha256(body_no_sig)
            bad.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.verify_certificate_file(bad, _THIS_DIR)

    def test_05_tampered_mlos_dirty_hardware_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            mlos_p = td_path / "mlos_zone_b_h8b_receipt.json"
            m = json.loads(mlos_p.read_text(encoding="utf-8"))
            m["clean_hardware_run"] = False
            no_sha = {k: v for k, v in m.items() if k != "receipt_sha256"}
            m["receipt_sha256"] = audit.canonical_sha256(no_sha)
            mlos_p.write_text(json.dumps(m), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_06_tampered_raw_gpu_result_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            res_p = td_path / "gpu_results_h8c" / "s108_gpu_full_results.json"
            obj = json.loads(res_p.read_text(encoding="utf-8"))
            obj["results"]["h8c"]["part1_adaptive_pacing"]["adaptive"]["runs"][0]["exact_mean_r"] = 2.5
            res_p.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_07_tampered_prereg_doc_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            (td_path / "PREREG_S108_TOKENIZER_LOOPING_BRIDGE.md").write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_08_non_str_key_and_depth_guard_fail_closed(self) -> None:
        with self.assertRaises(audit.S108AuditError):
            audit.check_json_tree_iterative({1: "bad"})
        deep: dict = {}
        cur = deep
        for _ in range(70):
            nxt: dict = {}
            cur["a"] = nxt
            cur = nxt
        with self.assertRaises(audit.S108AuditError):
            audit.check_json_tree_iterative(deep)

    def test_09_missing_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(Path(td))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = audit.main(["--check", str(Path(td) / "missing.json")])
            self.assertEqual(rc, 2)

    def test_10_swapped_receipt_fails_closed(self) -> None:
        # H8c receipt re-signed into the h8a slot: only the bound_protocol_sha256 /
        # bound_results_sha256 guards can catch it.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            src = json.loads((td_path / "mlos_zone_b_h8c_receipt.json").read_text(encoding="utf-8"))
            src["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in src.items() if k != "receipt_sha256"})
            (td_path / "mlos_zone_b_h8a_receipt.json").write_text(json.dumps(src, indent=2), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_11_redated_receipt_fails_closed(self) -> None:
        # Receipt re-dated (and re-signed) so the protocol created_utc falls outside the
        # execution window: only the window guard can catch it.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            rec_p = td_path / "mlos_zone_b_h8b_receipt.json"
            rec = json.loads(rec_p.read_text(encoding="utf-8"))
            rec["execution"]["started_utc"] = "2026-11-20T00:00:00Z"
            rec["execution"]["ended_utc"] = "2026-11-20T01:00:00Z"
            rec["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in rec.items() if k != "receipt_sha256"})
            rec_p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_12_recorded_verdict_flip_rebound_fails_closed(self) -> None:
        # part2_verdict flipped to CONFIRMED, results re-signed AND the h8c receipt rebound to
        # the new results file: only the computed-vs-recorded verdict guard can catch it.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            res_p = td_path / "gpu_results_h8c" / "s108_gpu_full_results.json"
            res = json.loads(res_p.read_text(encoding="utf-8"))
            res["results"]["h8c"]["grading"]["part2_verdict"] = "CONFIRMED"
            res["result_sha256"] = audit.canonical_sha256({k: v for k, v in res.items() if k != "result_sha256"})
            res_p.write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
            rec_p = td_path / "mlos_zone_b_h8c_receipt.json"
            rec = json.loads(rec_p.read_text(encoding="utf-8"))
            rec["bound_results_sha256"] = audit.sha256_file(res_p)
            rec["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in rec.items() if k != "receipt_sha256"})
            rec_p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)


if __name__ == "__main__":
    unittest.main()
