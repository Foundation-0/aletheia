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

    def _flip_results_and_rebind(self, td_path: Path, track: str, key: str, value: str) -> None:
        """Flip a recorded grading verdict, re-sign the results AND rebind the receipt, so
        only the computed-vs-recorded verdict guard (or the bound_results guard when the
        receipt is left stale) can catch the tamper."""
        res_p = td_path / f"gpu_results_{track}" / "s108_gpu_full_results.json"
        res = json.loads(res_p.read_text(encoding="utf-8"))
        res["results"][track]["grading"][key] = value
        res["result_sha256"] = audit.canonical_sha256({k: v for k, v in res.items() if k != "result_sha256"})
        res_p.write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
        rec_p = td_path / f"mlos_zone_b_{track}_receipt.json"
        rec = json.loads(rec_p.read_text(encoding="utf-8"))
        rec["bound_results_sha256"] = audit.sha256_file(res_p)
        rec["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in rec.items() if k != "receipt_sha256"})
        rec_p.write_text(json.dumps(rec, indent=2), encoding="utf-8")

    def test_10_swapped_receipt_fails_closed(self) -> None:
        # H8c receipt re-signed into the h8a slot, with BOTH its execution window re-dated
        # to bracket h8a created_utc AND bound_results_sha256 set to h8a's valid results SHA:
        # ONLY the bound_protocol_sha256 guard (:135) can catch this tamper.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            proto = json.loads((td_path / "gpu_results_h8a" / "s108_locked_protocol.json").read_text(encoding="utf-8"))
            created = str(proto["created_utc"])
            h8a_res_sha = audit.sha256_file(td_path / "gpu_results_h8a" / "s108_gpu_full_results.json")
            src = json.loads((td_path / "mlos_zone_b_h8c_receipt.json").read_text(encoding="utf-8"))
            src["execution"]["started_utc"] = "2026-11-25T00:00:00Z"
            src["execution"]["ended_utc"] = "2026-11-26T00:00:00Z"
            src["bound_results_sha256"] = h8a_res_sha
            self.assertTrue("2026-11-25T00:00:00Z" <= created <= "2026-11-26T00:00:00Z")
            src["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in src.items() if k != "receipt_sha256"})
            (td_path / "mlos_zone_b_h8a_receipt.json").write_text(json.dumps(src, indent=2), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_13_h8a_verdict_flip_rebound_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            self._flip_results_and_rebind(td_path, "h8a", "verdict", "CONFIRMED")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_14_h8b_verdict_flip_rebound_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            self._flip_results_and_rebind(td_path, "h8b", "verdict", "CONFIRMED")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_15_h8c_part1_verdict_flip_rebound_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            self._flip_results_and_rebind(td_path, "h8c", "part1_verdict", "CONFIRMED")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_16_h8c_part3_verdict_flip_rebound_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            self._flip_results_and_rebind(td_path, "h8c", "part3_verdict", "CONFIRMED")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_17_results_edit_without_rebind_fails_closed(self) -> None:
        # Unchecked top-level metadata (elapsed_s) edited and result_sha256 re-signed,
        # while receipt is NOT rebound: ONLY bound_results_sha256 (:138) can catch it.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            res_p = td_path / "gpu_results_h8b" / "s108_gpu_full_results.json"
            res = json.loads(res_p.read_text(encoding="utf-8"))
            res["elapsed_s"] = 9999.0
            res["result_sha256"] = audit.canonical_sha256({k: v for k, v in res.items() if k != "result_sha256"})
            res_p.write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

    def test_18_receipt_window_inclusive_boundaries(self) -> None:
        # Verify inclusive boundaries started == proto_created_utc and proto_created_utc == ended
        # both pass (:142), killing `<` vs `<=` boundary mutants, exact == boundary passes (outside-window rejection covered by test_11).
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            _copy_track_tree(td_path)
            proto_p = td_path / "gpu_results_h8b" / "s108_locked_protocol.json"
            created = str(json.loads(proto_p.read_text(encoding="utf-8"))["created_utc"])
            rec_p = td_path / "mlos_zone_b_h8b_receipt.json"
            orig = json.loads(rec_p.read_text(encoding="utf-8"))
            # 1) started_utc == created_utc (left boundary inclusive -> must succeed)
            r1 = json.loads(json.dumps(orig))
            r1["execution"]["started_utc"] = created
            r1["execution"]["ended_utc"] = "2099-01-01T00:00:00Z"
            r1["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in r1.items() if k != "receipt_sha256"})
            rec_p.write_text(json.dumps(r1, indent=2), encoding="utf-8")
            self.assertEqual(audit.build_certificate(td_path)["payload"]["total_live_gpu_runs"], 51)
            # 2) ended_utc == created_utc (right boundary inclusive -> must succeed)
            r2 = json.loads(json.dumps(orig))
            r2["execution"]["started_utc"] = "2000-01-01T00:00:00Z"
            r2["execution"]["ended_utc"] = created
            r2["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in r2.items() if k != "receipt_sha256"})
            rec_p.write_text(json.dumps(r2, indent=2), encoding="utf-8")
            self.assertEqual(audit.build_certificate(td_path)["payload"]["total_live_gpu_runs"], 51)

    def test_19_guard_and_boundary_matrix_kills_mutants(self) -> None:
        # Exercise remaining require_ok and tolerance boundary guards directly.
        # 1. check_json_tree_iterative exact max_depth=64 boundary (64 passes, 65 fails)
        d64: dict = {}
        cur = d64
        for _ in range(64):
            nxt: dict = {}
            cur["k"] = nxt
            cur = nxt
        audit.check_json_tree_iterative(d64, max_depth=64)
        cur["k"] = {"leaf": 1}
        with self.assertRaises(audit.S108AuditError):
            audit.check_json_tree_iterative(d64, max_depth=64)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # 2. load_json_strict: missing, malformed, and list root
            with self.assertRaises(audit.S108AuditError):
                audit.load_json_strict(td_path / "nope.json")
            bad_j = td_path / "bad.json"
            bad_j.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.load_json_strict(bad_j)
            arr_j = td_path / "arr.json"
            arr_j.write_text("[1, 2, 3]", encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.load_json_strict(arr_j)

            # 3. paired_stats & _assert_close_stats inclusive boundaries + exceedances
            with self.assertRaises(audit.S108AuditError):
                audit.paired_stats([1.0], [1.0])
            with self.assertRaises(audit.S108AuditError):
                audit.paired_stats([1.0, 2.0], [1.0])
            base_st = {"n": 3, "mean_diff": 0.0, "se": 0.0, "rel_pct": 0.0, "z": 0.0}
            audit._assert_close_stats(base_st, {
                "n": 3,
                "mean_diff": 2e-6,
                "se": 2e-6,
                "rel_pct": 2e-4,
                "z": 2e-3,
            }, "bnd_ok")
            for k, bad_v in (
                ("n", 4),
                ("mean_diff", 3e-6),
                ("se", 3e-6),
                ("rel_pct", 3e-4),
                ("z", 3e-3),
            ):
                rec_bad = dict(base_st)
                rec_bad[k] = bad_v
                with self.assertRaises(audit.S108AuditError):
                    audit._assert_close_stats(base_st, rec_bad, f"bad_{k}")

            # 4. _extract_seed_ordered guards
            with self.assertRaises(audit.S108AuditError):
                audit._extract_seed_ordered([{"seed": 42}, {"seed": 137}], "len2")
            with self.assertRaises(audit.S108AuditError):
                audit._extract_seed_ordered([{"seed": 42}, {"seed": 137}, {"seed": 999}], "bad_seed")

            # 5. verify_mlos_receipt individual field guards
            _copy_track_tree(td_path)
            rec_src = json.loads((_THIS_DIR / "mlos_zone_b_h8a_receipt.json").read_text(encoding="utf-8"))
            rp = td_path / "tmp_rec.json"
            for mut_fn in (
                lambda d: d.__setitem__("schema", "wrong"),
                lambda d: d.__setitem__("anomalies", ["x"]),
                lambda d: d.__setitem__("determinism_zone", "A"),
                lambda d: d.__setitem__("gpu_telemetry_available", False),
                lambda d: d["execution"].__setitem__("exit_code", 1),
            ):
                m = json.loads(json.dumps(rec_src))
                mut_fn(m)
                m["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in m.items() if k != "receipt_sha256"})
                rp.write_text(json.dumps(m), encoding="utf-8")
                with self.assertRaises(audit.S108AuditError):
                    audit.verify_mlos_receipt(rp)
            m_bad_len = json.loads(json.dumps(rec_src))
            m_bad_len["receipt_sha256"] = "abc"
            rp.write_text(json.dumps(m_bad_len), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.verify_mlos_receipt(rp)
            m_bad_sig = json.loads(json.dumps(rec_src))
            m_bad_sig["receipt_sha256"] = "0" * 64
            rp.write_text(json.dumps(m_bad_sig), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.verify_mlos_receipt(rp)

            # 6. verify_track_envelope individual field guards
            def _write_env_pair(p_mut=None, r_mut=None, resign_res: bool = True, link_proto: bool = True) -> None:
                p = json.loads((_THIS_DIR / "gpu_results_h8a" / "s108_locked_protocol.json").read_text(encoding="utf-8"))
                r = json.loads((_THIS_DIR / "gpu_results_h8a" / "s108_gpu_full_results.json").read_text(encoding="utf-8"))
                if p_mut is not None:
                    p_mut(p)
                pp = td_path / "gpu_results_h8a" / "s108_locked_protocol.json"
                pp.write_text(json.dumps(p, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                if link_proto:
                    r["protocol_sha256"] = audit.sha256_file(pp)
                if r_mut is not None:
                    r_mut(r)
                if resign_res:
                    r["result_sha256"] = audit.canonical_sha256({k: v for k, v in r.items() if k != "result_sha256"})
                rp2 = td_path / "gpu_results_h8a" / "s108_gpu_full_results.json"
                rp2.write_text(json.dumps(r, sort_keys=True, separators=(",", ":")), encoding="utf-8")

            for p_mut, r_mut, resign_res, link_proto in (
                (lambda p: p.__setitem__("schema", "bad"), None, True, True),
                (lambda p: p.__setitem__("track", "h8b"), None, True, True),
                (lambda p: p.__setitem__("mode", "cpu-smoke"), None, True, True),
                (None, lambda r: r.__setitem__("mode", "cpu-smoke"), True, True),
                (lambda p: p.__setitem__("device", "cpu"), None, True, True),
                (None, lambda r: r.__setitem__("device", "cpu"), True, True),
                (lambda p: p.__setitem__("weights_saved", 1), None, True, True),
                (None, lambda r: r.__setitem__("weights_saved", 1), True, True),
                (lambda p: p.__setitem__("parent_preregistration_sha256", "0" * 64), None, True, True),
                (None, lambda r: r.__setitem__("parent_preregistration_sha256", "0" * 64), True, True),
                (lambda p: p.__setitem__("amendment1_sha256", "0" * 64), None, True, True),
                (None, lambda r: r.__setitem__("amendment1_sha256", "0" * 64), True, True),
                (lambda p: p.__setitem__("harness_interpreter", "x"), None, True, False),
                (None, lambda r: r.__setitem__("result_sha256", "short"), False, True),
                (lambda p: p["corpus_byte_sizes"].pop("python"), None, True, True),
                (lambda p: p["corpus_sha256"].pop("python"), None, True, True),
                (lambda p: p["corpus_byte_sizes"]["python"].__setitem__("train_bytes", 100), None, True, True),
            ):
                _write_env_pair(p_mut, r_mut, resign_res, link_proto)
                with self.assertRaises(audit.S108AuditError):
                    audit.verify_track_envelope(td_path, "h8a")

            # 7. Amendment1 doc tamper & cross-track corpus mismatch & verify_certificate_file guards
            _copy_track_tree(td_path)
            (td_path / "PREREG_S107_S108_AMENDMENT1.md").write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

            _copy_track_tree(td_path)
            p_b = json.loads((td_path / "gpu_results_h8b" / "s108_locked_protocol.json").read_text(encoding="utf-8"))
            p_b["corpus_sha256"]["python"] = "1" * 64
            pp_b = td_path / "gpu_results_h8b" / "s108_locked_protocol.json"
            pp_b.write_text(json.dumps(p_b, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            r_b = json.loads((td_path / "gpu_results_h8b" / "s108_gpu_full_results.json").read_text(encoding="utf-8"))
            r_b["protocol_sha256"] = audit.sha256_file(pp_b)
            r_b["result_sha256"] = audit.canonical_sha256({k: v for k, v in r_b.items() if k != "result_sha256"})
            rp_b = td_path / "gpu_results_h8b" / "s108_gpu_full_results.json"
            rp_b.write_text(json.dumps(r_b, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            rec_b = json.loads((td_path / "mlos_zone_b_h8b_receipt.json").read_text(encoding="utf-8"))
            rec_b["bound_protocol_sha256"] = audit.sha256_file(pp_b)
            rec_b["bound_results_sha256"] = audit.sha256_file(rp_b)
            rec_b["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in rec_b.items() if k != "receipt_sha256"})
            (td_path / "mlos_zone_b_h8b_receipt.json").write_text(json.dumps(rec_b, indent=2), encoding="utf-8")
            with self.assertRaises(audit.S108AuditError):
                audit.build_certificate(td_path)

            # verify_certificate_file envelope guards (:653, :654, :661)
            _copy_track_tree(td_path)
            base_cert = json.loads((_THIS_DIR / "s108_tokenizer_loop_certificate.json").read_text(encoding="utf-8"))
            cp = td_path / "c_bad.json"
            for mut_c in (
                lambda c: c.__setitem__("certificate_sha256", "short"),
                lambda c: c.__setitem__("payload_sha256", "short"),
                lambda c: (
                    c["payload"].__setitem__("total_live_gpu_runs", 99),
                    c.__setitem__("certificate_sha256", audit.canonical_sha256({k: v for k, v in c.items() if k != "certificate_sha256"})),
                ),
            ):
                cm = json.loads(json.dumps(base_cert))
                mut_c(cm)
                cp.write_text(json.dumps(cm), encoding="utf-8")
                with self.assertRaises(audit.S108AuditError):
                    audit.verify_certificate_file(cp, _THIS_DIR)

            # 8. Per-track semantic guards in audit_h8a / audit_h8b / audit_h8c
            def _check_res_tamper(track: str, mut_fn) -> None:
                _copy_track_tree(td_path)
                res_p = td_path / f"gpu_results_{track}" / "s108_gpu_full_results.json"
                res = json.loads(res_p.read_text(encoding="utf-8"))
                mut_fn(res["results"][track])
                res["result_sha256"] = audit.canonical_sha256({k: v for k, v in res.items() if k != "result_sha256"})
                res_p.write_text(json.dumps(res, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                rec_p = td_path / f"mlos_zone_b_{track}_receipt.json"
                rec = json.loads(rec_p.read_text(encoding="utf-8"))
                rec["bound_results_sha256"] = audit.sha256_file(res_p)
                rec["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in rec.items() if k != "receipt_sha256"})
                rec_p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
                with self.assertRaises(audit.S108AuditError):
                    audit.build_certificate(td_path)

            for fn_a in (
                lambda h: h.__setitem__("vocab_size", 2048),
                lambda h: h["arms"].pop("flat_bpe"),
                lambda h: h["arms"]["flat_bpe"].__setitem__("mean_arabic_abios_bpb", 9.9),
                lambda h: h["arms"]["flat_bpe"].__setitem__("mean_english_python_bpb", 9.9),
                lambda h: h["arms"]["flat_bpe"].__setitem__("mean_bpb_across_seeds", 9.9),
                lambda h: h["grading"].__setitem__("best_hybrid_arm", "flat_bpe"),
            ):
                _check_res_tamper("h8a", fn_a)

            for fn_b in (
                lambda h: h.__setitem__("ctx_bytes", 256),
                lambda h: h["arms"].pop("bpe_std"),
                lambda h: h["arms"]["bpe_std"].__setitem__("mean_bpb_across_seeds", 9.9),
                lambda h: h.__setitem__("turing_diagnostic", None),
                lambda h: h["turing_diagnostic"]["diff_D_1_10"].__setitem__("nucleated", False),
                lambda h: h["turing_diagnostic"]["diff_D_1_10"].__setitem__("mean_boundary_period", 2.59),
                lambda h: h["turing_diagnostic"]["diff_D_1_10"].__setitem__("mean_boundary_period", 3.46),
                lambda h: h["turing_diagnostic"]["equal_D_5_5_null"].__setitem__("nucleated", True),
            ):
                _check_res_tamper("h8b", fn_b)

            for fn_c in (
                lambda h: h["part1_adaptive_pacing"].pop("random"),
                lambda h: h["part1_adaptive_pacing"]["adaptive"]["runs"][0].__setitem__("exact_mean_r", 2.1),
                lambda h: h["part1_adaptive_pacing"]["adaptive"]["runs"][0]["loop_diag"].__setitem__("max_unit_norm_drift", 1e-4),
                lambda h: h["part1_adaptive_pacing"]["adaptive"]["runs"][0]["loop_diag"].__setitem__("mean_empirical_rho", 0.0),
                lambda h: h["part1_adaptive_pacing"]["adaptive"]["runs"][0]["loop_diag"].__setitem__("mean_empirical_rho", 1.0),
                lambda h: h["part1_adaptive_pacing"]["adaptive"].__setitem__("mean_primary_bpb", 9.9),
                lambda h: h["part2_mtp8_vs_ar"].pop("local_ar"),
                lambda h: h["part2_mtp8_vs_ar"]["markov_mtp8"].__setitem__("mean_primary_bpb", 9.9),
                lambda h: h["part2_mtp8_vs_ar"]["markov_mtp8"].__setitem__("mean_mtp_bpb_tf", 9.9),
                lambda h: h["part2_mtp8_vs_ar"]["markov_mtp8"].__setitem__("mean_mtp_bpb_unrolled", 9.9),
                lambda h: h["part3_nullmodem"]["all_seed_runs"][0]["arms"]["nullmodem_sphere_cell"].__setitem__("hash_verified_fraction", 0.5),
                lambda h: h["part3_nullmodem"]["all_seed_runs"][0]["arms"]["nullmodem_sphere_cell"].__setitem__("payload_bits", 16),
                lambda h: h["part3_nullmodem"]["all_seed_runs"][0]["arms"]["nullmodem_sphere_cell"].__setitem__("total_wire_bits", 128.0),
                lambda h: h["part3_nullmodem"]["mean_across_seeds"].__setitem__("frozen_judge_field_acc", 0.1),
                lambda h: h["part3_nullmodem"]["mean_across_seeds"].__setitem__("frozen_judge_exact_acc", 0.1),
                lambda h: h["part3_nullmodem"]["mean_across_seeds"].__setitem__("counterfactual_edit_acc", 0.1),
            ):
                _check_res_tamper("h8c", fn_c)

            # 9. Exact inclusive boundary checks on per-arm 2e-6 / 1e-6 / [2.60, 3.45] tolerances (must PASS)
            def _check_res_pass(track: str, mut_fn) -> None:
                _copy_track_tree(td_path)
                res_p = td_path / f"gpu_results_{track}" / "s108_gpu_full_results.json"
                res = json.loads(res_p.read_text(encoding="utf-8"))
                mut_fn(res["results"][track])
                res["result_sha256"] = audit.canonical_sha256({k: v for k, v in res.items() if k != "result_sha256"})
                res_p.write_text(json.dumps(res, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                rec_p = td_path / f"mlos_zone_b_{track}_receipt.json"
                rec = json.loads(rec_p.read_text(encoding="utf-8"))
                rec["bound_results_sha256"] = audit.sha256_file(res_p)
                rec["receipt_sha256"] = audit.canonical_sha256({k: v for k, v in rec.items() if k != "receipt_sha256"})
                rec_p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
                self.assertEqual(audit.build_certificate(td_path)["payload"]["total_live_gpu_runs"], 51)

            _check_res_pass("h8b", lambda h: h["turing_diagnostic"]["diff_D_1_10"].__setitem__("mean_boundary_period", 2.60))
            _check_res_pass("h8b", lambda h: h["turing_diagnostic"]["diff_D_1_10"].__setitem__("mean_boundary_period", 3.45))
            _check_res_pass("h8c", lambda h: (
                [r.__setitem__("primary_bpb", 0.0) for r in h["part1_adaptive_pacing"]["adaptive"]["runs"]],
                h["part1_adaptive_pacing"]["adaptive"].__setitem__("mean_primary_bpb", 2e-6),
                h["grading"]["part1_vs_uniform"].update(audit.paired_stats([0.0, 0.0, 0.0], [float(r["primary_bpb"]) for r in sorted(h["part1_adaptive_pacing"]["uniform"]["runs"], key=lambda x: x["seed"])])),
                h["grading"]["part1_vs_random"].update(audit.paired_stats([0.0, 0.0, 0.0], [float(r["primary_bpb"]) for r in sorted(h["part1_adaptive_pacing"]["random"]["runs"], key=lambda x: x["seed"])])),
                h["grading"].__setitem__("part1_verdict", "CONFIRMED"),
            ))

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
