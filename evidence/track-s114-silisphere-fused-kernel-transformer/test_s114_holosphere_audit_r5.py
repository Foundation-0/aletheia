#!/usr/bin/env python3
"""Track S114 R5 Adversarial & Boundary Audit Test Suite (100% Pure Python Stdlib).

Zero torch/numpy imports. Zero bare asserts. Exercises every require_ok guard,
exact threshold boundary, V1+V2 ptxas binding, fail-closed PREREG/Amendment1,
Zone-B receipt binding, per-seed param & budget checks, preregistered-arm
verdict independence, allow_nan=False, strict int checks, symlink/size guards,
schema faults, and CLI mutual exclusion in s114_holosphere_audit.py.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict
from unittest import mock

TRACK_DIR = Path(__file__).resolve().parent
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import s114_holosphere_audit as audit  # noqa: E402

PINNED_TRACK_FILES = (
    audit.PREREG_FILENAME,
    audit.AMENDMENT1_FILENAME,
    audit.REPORT_FILENAME,
    audit.CU_FILENAME,
    audit.PTXAS_V1_FILENAME,
    audit.PTXAS_V2_FILENAME,
    "s114_h14a_gpu_results.json",
    "s114_v2_gpu_results.json",
    "s114_h14bc_gpu_results.json",
    "mlos_zone_b_s114_h14a.json",
    "mlos_zone_b_s114_v2.json",
    "mlos_zone_b_s114_h14bc.json",
    audit.CERT_FILENAME,
) + audit.GENERATOR_SCRIPTS


def _rehash_json(obj: Dict[str, Any], hash_field: str) -> Dict[str, Any]:
    out = copy.deepcopy(obj)
    out.pop(hash_field, None)
    raw = json.dumps(out, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    out[hash_field] = hashlib.sha256(raw).hexdigest()
    return out


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class TestS114AuditR5(unittest.TestCase):
    """Comprehensive R5 refusal-site & boundary tests for Track S114 audit."""

    def _make_sandbox(self) -> Path:
        td = Path(tempfile.mkdtemp(prefix="s114_r5_"))
        self.addCleanup(lambda: shutil.rmtree(td, ignore_errors=True))
        for fname in PINNED_TRACK_FILES:
            shutil.copy2(TRACK_DIR / fname, td / fname)
        return td

    def _assert_audit_fails(self, expected_code: str, fn: Any, *args: Any, **kwargs: Any) -> None:
        with self.assertRaises(audit.S114AuditError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, expected_code)

    # ------------------------------------------------------------------
    # 1. Real Evidence End-to-End & Exact Certificate Verification
    # ------------------------------------------------------------------
    def test_live_evidence_passes_and_matches_stored_certificate(self) -> None:
        cert = audit.verify_certificate(TRACK_DIR, TRACK_DIR / audit.CERT_FILENAME)
        self.assertTrue(cert["prereg_verified"])
        self.assertEqual(cert["verdicts"], {"H14a": "CONFIRMED", "H14b": "CONFIRMED", "H14c": "FALSIFIED"})
        self.assertEqual(cert["h14b"]["preregistered_arms_verdict"], "CONFIRMED")
        self.assertEqual(cert["ptxas_sm86_v1"]["zero_spill_kernels"], 9)
        self.assertEqual(cert["ptxas_sm86_v2"]["zero_spill_kernels"], 27)
        self.assertEqual(cert["ptxas_sm86_v2"]["nonzero_spill_kernels"], 0)
        self.assertEqual(cert["n2_claims"], 0)
        self.assertEqual(cert["novelty_class"], "N1")

    def test_prereg_and_amendment1_fail_closed_when_missing_or_tampered(self) -> None:
        sb = self._make_sandbox()
        cert = audit.verify_certificate(sb, sb / audit.CERT_FILENAME)
        self.assertTrue(cert["prereg_verified"])

        # Removing PREREG MUST fail closed (never skip silently!)
        (sb / audit.PREREG_FILENAME).unlink()
        self._assert_audit_fails("MISSING_FILE", audit.build_certificate, sb)

        # Tampering PREREG fails SHA check
        (sb / audit.PREREG_FILENAME).write_text("tampered\n", encoding="utf-8")
        self._assert_audit_fails("PREREG_SHA_MISMATCH", audit.build_certificate, sb)

        # Removing or tampering Amendment 1 fails closed
        sb2 = self._make_sandbox()
        (sb2 / audit.AMENDMENT1_FILENAME).unlink()
        self._assert_audit_fails("MISSING_FILE", audit.build_certificate, sb2)

        (sb2 / audit.AMENDMENT1_FILENAME).write_text("tampered\n", encoding="utf-8")
        self._assert_audit_fails("AMENDMENT1_SHA_MISMATCH", audit.build_certificate, sb2)

    # ------------------------------------------------------------------
    # 2. Pure Grading Functions & Exact Threshold Boundaries
    # ------------------------------------------------------------------
    def test_grade_h14a_exact_boundaries(self) -> None:
        g_ok = audit.grade_h14a(
            c1_zero_spill=True,
            c2_parity=True,
            cuda_vs_rope=1.15,
            cuda_speedup_vs_eager=3.40,
            micro_512_speedup=5.0,
            micro_2048_speedup=5.0,
        )
        self.assertEqual(g_ok["verdict"], "CONFIRMED")

        self.assertEqual(
            audit.grade_h14a(
                c1_zero_spill=True, c2_parity=True, cuda_vs_rope=1.1501,
                cuda_speedup_vs_eager=3.40, micro_512_speedup=5.0, micro_2048_speedup=5.0,
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            audit.grade_h14a(
                c1_zero_spill=True, c2_parity=True, cuda_vs_rope=1.0,
                cuda_speedup_vs_eager=3.399, micro_512_speedup=5.0, micro_2048_speedup=5.0,
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            audit.grade_h14a(
                c1_zero_spill=True, c2_parity=True, cuda_vs_rope=1.5,
                cuda_speedup_vs_eager=2.0, micro_512_speedup=5.0, micro_2048_speedup=5.0,
            )["verdict"],
            "PARTIAL",
        )
        # Failing microbench (< 5.0x) yields FALSIFIED per PREREG-S114:38
        self.assertEqual(
            audit.grade_h14a(
                c1_zero_spill=True, c2_parity=True, cuda_vs_rope=1.0,
                cuda_speedup_vs_eager=4.0, micro_512_speedup=4.99, micro_2048_speedup=5.0,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            audit.grade_h14a(
                c1_zero_spill=True, c2_parity=True, cuda_vs_rope=1.0,
                cuda_speedup_vs_eager=4.0, micro_512_speedup=5.0, micro_2048_speedup=4.99,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            audit.grade_h14a(
                c1_zero_spill=True, c2_parity=True, cuda_vs_rope=1.5,
                cuda_speedup_vs_eager=1.99, micro_512_speedup=5.0, micro_2048_speedup=5.0,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            audit.grade_h14a(
                c1_zero_spill=False, c2_parity=True, cuda_vs_rope=0.5,
                cuda_speedup_vs_eager=6.0, micro_512_speedup=10.0, micro_2048_speedup=10.0,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            audit.grade_h14a(
                c1_zero_spill=True, c2_parity=False, cuda_vs_rope=0.5,
                cuda_speedup_vs_eager=6.0, micro_512_speedup=10.0, micro_2048_speedup=10.0,
            )["verdict"],
            "FALSIFIED",
        )

    def test_grade_h14b_exact_boundaries(self) -> None:
        base = dict(
            rel_pct_2048_vs_ngpt=-5.0,
            z_2048_vs_ngpt=-2.0,
            rel_pct_2048_vs_std=-5.0,
            z_2048_vs_std=-2.0,
            rel_pct_512_vs_ngpt=0.5,
            mj_ratio_512=1.15,
            mj_ratio_2048=1.15,
        )
        g_ok = audit.grade_h14b_arm(**base)
        self.assertTrue(all(g_ok.values()))
        self.assertEqual(audit.grade_h14b_campaign({"a": g_ok}), "CONFIRMED")

        for bad_k, bad_v, gate_k in (
            ("rel_pct_2048_vs_ngpt", -4.99, "c1_t2048_ge_5pct_z_le_m2"),
            ("z_2048_vs_ngpt", -1.99, "c1_t2048_ge_5pct_z_le_m2"),
            ("rel_pct_2048_vs_std", -4.99, "c1_t2048_ge_5pct_z_le_m2"),
            ("z_2048_vs_std", -1.99, "c1_t2048_ge_5pct_z_le_m2"),
            ("rel_pct_512_vs_ngpt", 0.51, "c2_t512_non_regression"),
            ("mj_ratio_512", 1.151, "c3_mj_le_115x"),
            ("mj_ratio_2048", 1.151, "c3_mj_le_115x"),
        ):
            kw = dict(base)
            kw[bad_k] = bad_v
            g = audit.grade_h14b_arm(**kw)
            self.assertFalse(g[gate_k])
            expected_v = "FALSIFIED" if gate_k == "c1_t2048_ge_5pct_z_le_m2" else "PARTIAL"
            self.assertEqual(audit.grade_h14b_campaign({"a": g}), expected_v)

    def test_grade_h14c_exact_boundaries(self) -> None:
        base = dict(
            ood_acc_mean=50.0, acc_floor=50.0, margin_pp=15.0,
            diff_vs_rope=15.0, z_vs_rope=2.0, diff_vs_qk=15.0, z_vs_qk=2.0,
        )
        self.assertTrue(audit.grade_h14c_group(**base))
        for bad_k, bad_v in (
            ("ood_acc_mean", 49.99),
            ("diff_vs_rope", 14.99),
            ("z_vs_rope", 1.99),
            ("diff_vs_qk", 14.99),
            ("z_vs_qk", 1.99),
        ):
            kw = dict(base)
            kw[bad_k] = bad_v
            self.assertFalse(audit.grade_h14c_group(**kw))

        self.assertEqual(audit.grade_h14c_campaign(True, True), "CONFIRMED")
        self.assertEqual(audit.grade_h14c_campaign(True, False), "PARTIAL")
        self.assertEqual(audit.grade_h14c_campaign(False, True), "PARTIAL")
        self.assertEqual(audit.grade_h14c_campaign(False, False), "FALSIFIED")

    # ------------------------------------------------------------------
    # 3. Low-Level Helpers: Canonical NaN, Strict Int, Timestamps, JSON Size
    # ------------------------------------------------------------------
    def test_paired_stats_guards_and_boundaries(self) -> None:
        st2 = audit._paired_stats([2.0, 2.2], [3.0, 3.0])
        self.assertAlmostEqual(st2["mean_diff"], -0.9, places=6)
        self._assert_audit_fails("PAIRED_LEN", audit._paired_stats, [1.0], [1.0])
        self._assert_audit_fails("PAIRED_LEN", audit._paired_stats, [1.0, 2.0], [1.0, 2.0, 3.0])
        self._assert_audit_fails("ZERO_BASELINE", audit._paired_stats, [1.0, 2.0], [0.0, 0.0])
        self._assert_audit_fails("ZERO_BASELINE", audit._paired_stats, [1.0, 2.0], [1e-12, 1e-12])

    def test_canonical_nan_strict_int_timestamp_and_number_guards(self) -> None:
        self._assert_audit_fails("NON_CANONICAL_JSON", audit._canonical_bytes, {"x": float("nan")})
        self._assert_audit_fails("NON_CANONICAL_JSON", audit._canonical_bytes, {"x": float("inf")})
        self._assert_audit_fails("BAD_INT", audit._as_int, False, "b")
        self._assert_audit_fails("BAD_INT", audit._as_int, 0.0, "f")
        self._assert_audit_fails("BAD_INT", audit._as_int, "0", "s")
        self.assertEqual(audit._as_int(0, "ok"), 0)

        self._assert_audit_fails("BAD_TIMESTAMP", audit._parse_utc, 12345, "x")
        self._assert_audit_fails("BAD_TIMESTAMP", audit._parse_utc, "not-a-timestamp", "x")
        self._assert_audit_fails("NAIVE_TIMESTAMP", audit._parse_utc, "2026-11-25T22:29:07", "x")
        self._assert_audit_fails("BAD_NUMBER", audit._as_float, True, "x")
        self._assert_audit_fails("BAD_NUMBER", audit._as_float, float("nan"), "x")
        self._assert_audit_fails("BAD_NUMBER", audit._as_float, float("inf"), "x")
        self._assert_audit_fails("BAD_NUMBER", audit._as_float, "1.0", "x")

    def test_missing_oversized_and_malformed_json(self) -> None:
        sb = self._make_sandbox()
        target = sb / "s114_h14a_gpu_results.json"
        exact_sz = target.stat().st_size
        # Exact boundary == MAX_JSON_BYTES passes; exact_sz - 1 fails JSON_TOO_LARGE
        with mock.patch.object(audit, "MAX_JSON_BYTES", exact_sz):
            self.assertIsInstance(audit._load_json_dict(target), dict)
        with mock.patch.object(audit, "MAX_JSON_BYTES", exact_sz - 1):
            self._assert_audit_fails("JSON_TOO_LARGE", audit._load_json_dict, target)

        target.unlink()
        self._assert_audit_fails("MISSING_JSON", audit.build_certificate, sb)

        target.write_text("{broken", encoding="utf-8")
        self._assert_audit_fails("MALFORMED_JSON", audit.build_certificate, sb)

        target.write_text("[]\n", encoding="utf-8")
        self._assert_audit_fails("SCHEMA_ROOT", audit.build_certificate, sb)

    def test_missing_report_and_prereg_ref(self) -> None:
        sb = self._make_sandbox()
        (sb / audit.REPORT_FILENAME).unlink()
        self._assert_audit_fails("MISSING_FILE", audit.build_certificate, sb)

        sb_ref = self._make_sandbox()
        (sb_ref / audit.REPORT_FILENAME).write_text("# Report without locked hash\n", encoding="utf-8")
        self._assert_audit_fails("REPORT_PREREG_REF", audit.build_certificate, sb_ref)

    # ------------------------------------------------------------------
    # 4. Hygiene Guards (SYMLINKS=0, WEIGHTS=0, ELF=0)
    # ------------------------------------------------------------------
    def test_hygiene_symlinks_weights_and_elf_rejected(self) -> None:
        sb0 = self._make_sandbox()
        (sb0 / "evil_link.txt").symlink_to(sb0 / audit.REPORT_FILENAME)
        self._assert_audit_fails("HYGIENE_SYMLINK", audit.build_certificate, sb0)

        sb = self._make_sandbox()
        (sb / "leak_model.pt").write_bytes(b"fake")
        self._assert_audit_fails("HYGIENE_WEIGHTS", audit.build_certificate, sb)

        sb2 = self._make_sandbox()
        (sb2 / "libfoo.so").write_bytes(b"not-elf-ext")
        self._assert_audit_fails("HYGIENE_ELF", audit.build_certificate, sb2)

        sb3 = self._make_sandbox()
        (sb3 / "disguised.dat").write_bytes(b"\x7fELF\x02\x01\x01\x00")
        self._assert_audit_fails("HYGIENE_ELF", audit.build_certificate, sb3)

    # ------------------------------------------------------------------
    # 5. V1 (9/9) & V2 (27/27) ptxas Zero-Spill Receipt Guards
    # ------------------------------------------------------------------
    def test_ptxas_v1_and_v2_refusal_sites(self) -> None:
        # V1 receipt guards
        v1_cases = (
            ("PTXAS_ARCH", lambda d: d.__setitem__("arch", "sm_80")),
            ("PTXAS_CU_SHA", lambda d: d.__setitem__("cu_sha256", "short")),
            ("PTXAS_KERNEL_COUNT", lambda d: (d["kernels"].pop(), d.__setitem__("total_kernels", 8))),
            ("PTXAS_KERNEL_SYMBOL", lambda d: d["kernels"][0].__setitem__("mangled_name", "")),
            ("PTXAS_DUP_SYMBOL", lambda d: d["kernels"][1].__setitem__("mangled_name", d["kernels"][0]["mangled_name"])),
            ("PTXAS_KERNEL_SPILL", lambda d: d["kernels"][0].__setitem__("stack_bytes", 16)),
            ("PTXAS_KERNEL_SPILL", lambda d: d["kernels"][0].__setitem__("spill_stores", 4)),
            ("PTXAS_KERNEL_SPILL", lambda d: d["kernels"][0].__setitem__("spill_loads", 4)),
            ("BAD_INT", lambda d: d["kernels"][0].__setitem__("stack_bytes", False)),
            ("BAD_INT", lambda d: d["kernels"][0].__setitem__("registers", 26.0)),
        )
        for code, mut in v1_cases:
            sb = self._make_sandbox()
            p = sb / audit.PTXAS_V1_FILENAME
            d = _load_json(p)
            mut(d)
            _write_json(p, d)
            self._assert_audit_fails(code, audit.build_certificate, sb)

        # V2 receipt guards
        v2_cases = (
            ("PTXAS_CU_SHA", lambda d: d.__setitem__("cu_sha256", "0" * 64)),
            ("PTXAS_KERNEL_COUNT", lambda d: (d["kernels"].pop(), d.__setitem__("total_kernels", 26))),
            ("PTXAS_TOTAL_MISMATCH", lambda d: d.__setitem__("total_kernels", 28)),
            ("PTXAS_NONZERO_SPILL", lambda d: d.__setitem__("nonzero_spill_kernels", 1)),
            ("PTXAS_KERNEL_ENTRY", lambda d: d["kernels"].__setitem__(0, "bad")),
            ("PTXAS_KERNEL_SYMBOL", lambda d: d["kernels"][0].__setitem__("symbol", "")),
            ("PTXAS_DUP_SYMBOL", lambda d: d["kernels"][1].__setitem__("symbol", d["kernels"][0]["symbol"])),
            ("PTXAS_KERNEL_SPILL", lambda d: d["kernels"][0].__setitem__("stack_frame_bytes", 16)),
            ("PTXAS_KERNEL_SPILL", lambda d: d["kernels"][0].__setitem__("spill_store_bytes", 4)),
            ("PTXAS_KERNEL_SPILL", lambda d: d["kernels"][0].__setitem__("spill_load_bytes", 4)),
            ("PTXAS_KERNEL_SPILL", lambda d: d["kernels"][0].__setitem__("zero_spill", False)),
            ("PTXAS_ZERO_COUNT", lambda d: d.__setitem__("zero_spill_kernels", 26)),
        )
        for code, mut in v2_cases:
            sb = self._make_sandbox()
            p = sb / audit.PTXAS_V2_FILENAME
            d = _load_json(p)
            mut(d)
            _write_json(p, d)
            self._assert_audit_fails(code, audit.build_certificate, sb)

    # ------------------------------------------------------------------
    # 6. Zone-B Receipt Integrity, Telemetry, & Timestamp Window Binding
    # ------------------------------------------------------------------
    def test_zone_b_receipt_tamper_and_boundaries(self) -> None:
        sb = self._make_sandbox()
        rp = sb / "mlos_zone_b_s114_h14a.json"
        rec = _load_json(rp)
        rec["receipt_sha256"] = "0" * 64
        _write_json(rp, rec)
        self._assert_audit_fails("INNER_HASH_MISMATCH", audit.build_certificate, sb)

        rec["receipt_sha256"] = "short"
        _write_json(rp, rec)
        self._assert_audit_fails("MISSING_INNER_HASH", audit.build_certificate, sb)

        # Boundary pass: completed_utc == started_utc AND completed_utc == ended_utc
        for boundary_field in ("started_utc", "ended_utc"):
            sb_b = self._make_sandbox()
            rp_b = sb_b / "mlos_zone_b_s114_h14a.json"
            res_p = sb_b / "s114_h14a_gpu_results.json"
            rec_b = _load_json(rp_b)
            res_b = _load_json(res_p)
            rec_b["execution"][boundary_field] = res_b["completed_utc"]
            _write_json(rp_b, _rehash_json(rec_b, "receipt_sha256"))
            cert_b = audit.build_certificate(sb_b)
            self.assertEqual(cert_b["verdicts"]["H14a"], "CONFIRMED")

        # Out-of-window timestamps (both too early and too late)
        for bad_ts in ("2026-11-25T22:29:06Z", "2026-11-25T22:30:15Z"):
            sb_t = self._make_sandbox()
            res_p = sb_t / "s114_h14a_gpu_results.json"
            res_t = _load_json(res_p)
            res_t["completed_utc"] = bad_ts
            _write_json(res_p, _rehash_json(res_t, "result_sha256"))
            self._assert_audit_fails("RECEIPT_TIME_WINDOW", audit.build_certificate, sb_t)

        # Every telemetry & receipt metadata guard (with valid re-hashed receipt_sha256)
        receipt_cases = (
            ("RECEIPT_SCHEMA", lambda r: r.__setitem__("schema", "other/v0")),
            ("RECEIPT_ZONE", lambda r: r.__setitem__("determinism_zone", "A")),
            ("RECEIPT_UNCLEAN", lambda r: r.__setitem__("clean_hardware_run", False)),
            ("RECEIPT_ANOMALIES", lambda r: r.__setitem__("anomalies", ["thermal_spike"])),
            ("RECEIPT_NO_GPU_TEL", lambda r: r.__setitem__("gpu_telemetry_available", False)),
            ("RECEIPT_EXE_OBJ", lambda r: r.__setitem__("execution", None)),
            ("RECEIPT_EXIT_CODE", lambda r: r["execution"].__setitem__("exit_code", 1)),
            ("BAD_INT", lambda r: r["execution"].__setitem__("exit_code", False)),
            ("RECEIPT_TEL_OBJ", lambda r: r.__setitem__("start_gpu_telemetry", None)),
            ("RECEIPT_COMPUTE_VRAM", lambda r: r["end_gpu_telemetry"].__setitem__("compute_vram_mib", 128)),
            ("BAD_INT", lambda r: r["end_gpu_telemetry"].__setitem__("compute_vram_mib", False)),
            ("RECEIPT_CLOCKS_OBJ", lambda r: r["end_gpu_telemetry"].__setitem__("clocks_event_reasons", None)),
            ("RECEIPT_THERMAL_THROTTLE", lambda r: r["end_gpu_telemetry"]["clocks_event_reasons"].__setitem__("thermal_throttled", True)),
            ("RECEIPT_SLOWDOWN", lambda r: r["end_gpu_telemetry"]["clocks_event_reasons"].__setitem__("slowdown_active", True)),
        )
        for code, mut in receipt_cases:
            sb_r = self._make_sandbox()
            rp_r = sb_r / "mlos_zone_b_s114_v2.json"
            rec_r = _load_json(rp_r)
            mut(rec_r)
            _write_json(rp_r, _rehash_json(rec_r, "receipt_sha256"))
            self._assert_audit_fails(code, audit.build_certificate, sb_r)

        # Duplicate Zone-B receipt across two campaigns
        sb_d = self._make_sandbox()
        rec_wide = _load_json(sb_d / "mlos_zone_b_s114_h14a.json")
        rec_wide["execution"]["ended_utc"] = "2026-11-25T23:59:59Z"
        rec_wide = _rehash_json(rec_wide, "receipt_sha256")
        _write_json(sb_d / "mlos_zone_b_s114_h14a.json", rec_wide)
        _write_json(sb_d / "mlos_zone_b_s114_v2.json", rec_wide)
        self._assert_audit_fails("DUPLICATE_ZONE_B_RECEIPT", audit.build_certificate, sb_d)

    # ------------------------------------------------------------------
    # 7. H14a (Bound to V1 cu_sha256) & V2 Recomputation Guards & Boundaries
    # ------------------------------------------------------------------
    def test_h14a_and_v2_refusal_sites_and_boundaries(self) -> None:
        # H14a kernel SHA MUST match V1 ptxas receipt (rejects V2 hash substitution!)
        sb_cu = self._make_sandbox()
        p_cu = sb_cu / "s114_h14a_gpu_results.json"
        d_cu = _load_json(p_cu)
        d_cu["cu_sha256"] = "15f9b3a2cd55752edc24e33664f8c6a3d60a8ade24036345ef7ebdc9def1f79f"
        _write_json(p_cu, _rehash_json(d_cu, "result_sha256"))
        self._assert_audit_fails("H14A_CU_SHA", audit.build_certificate, sb_cu)

        # H14a inner hash tamper & verdict tamper
        sb = self._make_sandbox()
        p = sb / "s114_h14a_gpu_results.json"
        d = _load_json(p)
        d["h14a_locked_verdict"]["verdict"] = "FALSIFIED"
        _write_json(p, d)
        self._assert_audit_fails("INNER_HASH_MISMATCH", audit.build_certificate, sb)

        _write_json(p, _rehash_json(d, "result_sha256"))
        self._assert_audit_fails("H14A_VERDICT_MISMATCH", audit.build_certificate, sb)

        # H14a preregistration SHA mismatch
        sb_pr = self._make_sandbox()
        p_pr = sb_pr / "s114_h14a_gpu_results.json"
        d_pr = _load_json(p_pr)
        d_pr["preregistration_sha256"] = "1" * 64
        _write_json(p_pr, _rehash_json(d_pr, "result_sha256"))
        self._assert_audit_fails("RESULT_PREREG_SHA", audit.build_certificate, sb_pr)

        # H14a malformed schema (KeyError & AttributeError) -> typed S114AuditError
        sb_ms = self._make_sandbox()
        p_ms = sb_ms / "s114_h14a_gpu_results.json"
        d_ms = _load_json(p_ms)
        del d_ms["parity"]
        _write_json(p_ms, _rehash_json(d_ms, "result_sha256"))
        self._assert_audit_fails("MALFORMED_SCHEMA", audit.build_certificate, sb_ms)

        # H14a parity length exact boundary (5 passes, 4 fails)
        sb_l5 = self._make_sandbox()
        p_l5 = sb_l5 / "s114_h14a_gpu_results.json"
        d_l5 = _load_json(p_l5)
        keep5 = ["32", "256", "512", "1024", "2048"]
        for dk in ("fp32", "bf16"):
            d_l5["parity"]["su2_holonomy"][dk] = {k: d_l5["parity"]["su2_holonomy"][dk][k] for k in keep5}
        _write_json(p_l5, _rehash_json(d_l5, "result_sha256"))
        self.assertEqual(audit.build_certificate(sb_l5)["verdicts"]["H14a"], "CONFIRMED")

        del d_l5["parity"]["su2_holonomy"]["fp32"]["32"]
        _write_json(p_l5, _rehash_json(d_l5, "result_sha256"))
        self._assert_audit_fails("H14A_PARITY_LEN", audit.build_certificate, sb_l5)

        # H14a non-positive timing & micro timing
        sb_t0 = self._make_sandbox()
        p_t0 = sb_t0 / "s114_h14a_gpu_results.json"
        d_t0 = _load_json(p_t0)
        d_t0["full_12l_h7b_step"]["holosphere_cuda_sm86"]["step_median_ms"] = 0.0
        _write_json(p_t0, _rehash_json(d_t0, "result_sha256"))
        self._assert_audit_fails("H14A_TIMING_POS", audit.build_certificate, sb_t0)

        sb_m0 = self._make_sandbox()
        p_m0 = sb_m0 / "s114_h14a_gpu_results.json"
        d_m0 = _load_json(p_m0)
        d_m0["kernel_microbench"]["512"]["cuda_sm86_bhtd_with_permute"]["fwdbwd_ms"] = 0.0
        _write_json(p_m0, _rehash_json(d_m0, "result_sha256"))
        self._assert_audit_fails("H14A_MICRO_POS", audit.build_certificate, sb_m0)

        # V2 exact boundary PASS (all thresholds pinned right at limit!)
        sb_v2ok = self._make_sandbox()
        p_v2ok = sb_v2ok / "s114_v2_gpu_results.json"
        d_v2ok = _load_json(p_v2ok)
        for row in d_v2ok["parity"]["bhtd_rows"]:
            if row["dtype"] == "fp32":
                row["fwd_max_abs"] = audit.FP32_MAX_ABS
            else:
                row["fwd_max_abs"] = audit.BF16_MAX_ABS
            row["norm_drift"] = audit.NORM_DRIFT_MAX
        d_v2ok["parity"]["gpu_beltrami_m0_m4_max_drift"] = audit.BELTRAMI_DRIFT_MAX
        d_v2ok["full_12l_step"]["rope2d_ngpt"]["step_median_ms"] = 100.0
        d_v2ok["full_12l_step"]["holosphere_v2_sm86"]["step_median_ms"] = 115.0
        d_v2ok["full_12l_step"]["eager_h7b"]["step_median_ms"] = 391.0
        _write_json(p_v2ok, _rehash_json(d_v2ok, "result_sha256"))
        self.assertEqual(audit.build_certificate(sb_v2ok)["v2_foundry"]["v2_vs_rope"], 1.15)

        # V2 individual refusal sites
        v2_cases = (
            ("V2_CU_SHA", lambda x: x.__setitem__("cu_sha256", "0" * 64)),
            ("V2_ZERO_SPILL_COUNT", lambda x: x.__setitem__("zero_spill_kernels", 26)),
            ("V2_PARITY_ROWS", lambda x: x["parity"]["bhtd_rows"].pop()),
            ("V2_NAN_INF", lambda x: x["parity"]["summary"].__setitem__("any_nan_or_inf", True)),
            ("V2_FP32_PARITY", lambda x: x["parity"]["bhtd_rows"][0].__setitem__("fwd_max_abs", 2e-4)),
            ("V2_BF16_PARITY", lambda x: x["parity"]["bhtd_rows"][-1].__setitem__("fwd_max_abs", 6e-3)),
            ("V2_NORM_DRIFT", lambda x: x["parity"]["bhtd_rows"][0].__setitem__("norm_drift", 2e-5)),
            ("V2_BELTRAMI_DRIFT", lambda x: x["parity"].__setitem__("gpu_beltrami_m0_m4_max_drift", 2e-6)),
            ("V2_TIMING_POS", lambda x: x["full_12l_step"]["holosphere_v2_sm86"].__setitem__("step_median_ms", 0.0)),
            ("V2_VS_ROPE", lambda x: x["full_12l_step"]["holosphere_v2_sm86"].__setitem__("step_median_ms", 131.0)),
            ("V2_VS_EAGER", lambda x: x["full_12l_step"]["eager_h7b"].__setitem__("step_median_ms", 200.0)),
        )
        for code, mut in v2_cases:
            sb_v = self._make_sandbox()
            pv = sb_v / "s114_v2_gpu_results.json"
            dv = _load_json(pv)
            mut(dv)
            _write_json(pv, _rehash_json(dv, "result_sha256"))
            self._assert_audit_fails(code, audit.build_certificate, sb_v)

    # ------------------------------------------------------------------
    # 8. H14b & H14c Recomputation, Per-Seed Parity, Budget, & Prereg Independence
    # ------------------------------------------------------------------
    def test_h14bc_refusal_sites_and_boundaries(self) -> None:
        # Exact 0.5% param parity + exact +1.0s budget boundary PASS
        sb_p = self._make_sandbox()
        pp = sb_p / "s114_h14bc_gpu_results.json"
        dp = _load_json(pp)
        for r in dp["h14b"]["runs"]:
            if r["arm_name"] == "RoPE-2D-nGPT":
                r["params"]["non_embedding_params"] = 10000000
            elif r["arm_name"] == "RoPE-2D-Std":
                r["params"]["non_embedding_params"] = 10050000
                r["equal_wallclock"]["train_time_s"] = r["t_budget_s"] + audit.H14B_BUDGET_SLACK_S
            else:
                r["params"]["non_embedding_params"] = 10000000
        for r in dp["h14c"]["runs"]:
            if r["arm_name"] == "RoPE-2D-nGPT":
                r["params"]["non_embedding_params"] = 4000000
            elif r["arm_name"] == "H7b-QK-Only":
                r["params"]["non_embedding_params"] = 4020000
            else:
                r["params"]["non_embedding_params"] = 4000000
        _write_json(pp, _rehash_json(dp, "result_sha256"))
        cert_p = audit.build_certificate(sb_p)
        self.assertEqual(cert_p["h14b"]["max_param_delta"], 0.005)
        self.assertEqual(cert_p["h14b"]["max_budget_overshoot_s"], 1.0)
        self.assertEqual(cert_p["h14c"]["max_param_delta"], 0.005)

        def _mut_h14b_seed2026_param(d: Dict[str, Any], val: int) -> None:
            for r in d["h14b"]["runs"]:
                if r["arm_name"] == "RoPE-2D-Std" and r["seed"] == 2026:
                    r["params"]["non_embedding_params"] = val

        def _mut_h14b_budget(d: Dict[str, Any], val: float) -> None:
            for r in d["h14b"]["runs"]:
                if r["arm_name"] == "RoPE-2D-Std" and r["seed"] == 42:
                    r["equal_wallclock"]["train_time_s"] = val

        def _mut_h14b_prereg_fail_exploratory_pass(d: Dict[str, Any]) -> None:
            # Break C3 on preregistered HoloSphere-V2-SU2-Unlooped while exploratory CayleySU2 still passes!
            for r in d["h14b"]["runs"]:
                if r["arm_name"] == "HoloSphere-V2-SU2-Unlooped":
                    r["inference_T512"]["gross_mj_per_tok"] = 2.0
            d["h14b"]["comparisons"]["HoloSphere-V2-SU2-Unlooped"]["c3_mj_le_115x"] = False

        def _mut_h14b_ref_zero(d: Dict[str, Any]) -> None:
            for r in d["h14b"]["runs"]:
                if r["arm_name"] == "RoPE-2D-nGPT":
                    r["params"]["non_embedding_params"] = 0

        def _mut_h14b_mj_zero(d: Dict[str, Any]) -> None:
            for r in d["h14b"]["runs"]:
                if r["arm_name"] == "RoPE-2D-nGPT":
                    r["inference_T512"]["gross_mj_per_tok"] = 0.0

        def _mut_h14c_seed2026_param(d: Dict[str, Any], val: int) -> None:
            for r in d["h14c"]["runs"]:
                if r["group"] == "S3" and r["arm_name"] == "H7b-QK-Only" and r["seed"] == 2026:
                    r["params"]["non_embedding_params"] = val

        def _mut_h14c_ref_zero(d: Dict[str, Any]) -> None:
            for r in d["h14c"]["runs"]:
                if r["group"] == "S3" and r["arm_name"] == "RoPE-2D-nGPT":
                    r["params"]["non_embedding_params"] = 0

        bc_cases = (
            ("H14BC_CU_SHA", lambda d: d.__setitem__("cu_sha256", "0" * 64)),
            ("H14BC_ZERO_SPILL", lambda d: d.__setitem__("zero_spill_kernels", 26)),
            ("CORPUS_DISJOINT", lambda d: d["corpus"].__setitem__("eval_sha256", d["corpus"]["train_sha256"])),
            ("CORPUS_DISJOINT", lambda d: d["corpus"].__setitem__("train_num_bytes", 0)),
            ("H14B_RUN_COUNT", lambda d: d["h14b"]["runs"].pop()),
            ("H14B_ARMS", lambda d: d["h14b"]["runs"][0].__setitem__("arm_name", "Bogus-Arm")),
            ("H14B_SEEDS", lambda d: d["h14b"]["runs"][0].__setitem__("seed", 999)),
            ("H14B_REF_PARAMS", _mut_h14b_ref_zero),
            ("H14B_PARAM_PARITY", lambda d: _mut_h14b_seed2026_param(d, 16000000)),
            ("H14B_BUDGET_OVERSHOOT", lambda d: _mut_h14b_budget(d, 0.0)),
            ("H14B_BUDGET_OVERSHOOT", lambda d: _mut_h14b_budget(d, 70.0)),
            ("H14B_MJ_POS", _mut_h14b_mj_zero),
            ("H14B_GATE_MISMATCH", lambda d: d["h14b"]["comparisons"]["HoloSphere-V2-SU2-Unlooped"].__setitem__("c3_mj_le_115x", False)),
            ("H14B_VERDICT_MISMATCH", _mut_h14b_prereg_fail_exploratory_pass),
            ("H14B_VERDICT_MISMATCH", lambda d: d["h14b"].__setitem__("h14b_locked_verdict", "FALSIFIED")),
            ("H14C_RUN_COUNT", lambda d: d["h14c"]["runs"].pop()),
            ("H14C_ARMS", lambda d: d["h14c"]["runs"][0].__setitem__("arm_name", "Bogus-Arm")),
            ("H14C_SEEDS", lambda d: d["h14c"]["runs"][0].__setitem__("seed", 999)),
            ("H14C_REF_PARAMS", _mut_h14c_ref_zero),
            ("H14C_PARAM_PARITY", lambda d: _mut_h14c_seed2026_param(d, 5500000)),
            ("H14C_GATE_MISMATCH", lambda d: d["h14c"]["comparisons"]["S3"].__setitem__("locked_criterion_pass", True)),
            ("H14C_VERDICT_MISMATCH", lambda d: d["h14c"].__setitem__("h14c_locked_verdict", "CONFIRMED")),
        )
        for code, mut in bc_cases:
            sb_bc = self._make_sandbox()
            pbc = sb_bc / "s114_h14bc_gpu_results.json"
            dbc = _load_json(pbc)
            mut(dbc)
            _write_json(pbc, _rehash_json(dbc, "result_sha256"))
            self._assert_audit_fails(code, audit.build_certificate, sb_bc)

    # ------------------------------------------------------------------
    # 9. Certificate Tamper Detection & CLI Exit Codes / Mutual Exclusion
    # ------------------------------------------------------------------
    def test_certificate_tamper_and_cli_modes(self) -> None:
        sb = self._make_sandbox()
        cert_p = sb / audit.CERT_FILENAME

        # Tamper without re-hashing -> INNER_HASH_MISMATCH
        c = _load_json(cert_p)
        c["n2_claims"] = 1
        _write_json(cert_p, c)
        self._assert_audit_fails("INNER_HASH_MISMATCH", audit.verify_certificate, sb, cert_p)

        # Tamper AND re-hash cert_sha256 -> CERT_MISMATCH against raw evidence
        _write_json(cert_p, _rehash_json(c, "cert_sha256"))
        self._assert_audit_fails("CERT_MISMATCH", audit.verify_certificate, sb, cert_p)

        # CLI --write, --standalone --json, --check, mutual exclusion, and failing exit code 1
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = audit.main(["--track-dir", str(sb), "--write"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["status"], "WROTE")

        buf_json = io.StringIO()
        with redirect_stdout(buf_json):
            rc2 = audit.main(["--track-dir", str(sb), "--standalone", "--json"])
        self.assertEqual(rc2, 0)
        self.assertEqual(buf_json.getvalue(), cert_p.read_text(encoding="utf-8"))

        buf_chk = io.StringIO()
        with redirect_stdout(buf_chk):
            rc3 = audit.main(["--track-dir", str(sb), "--check", str(cert_p)])
        self.assertEqual(rc3, 0)
        self.assertEqual(json.loads(buf_chk.getvalue())["status"], "PASS")

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as sx:
                audit.main(["--track-dir", str(sb), "--write", "--check"])
        self.assertEqual(sx.exception.code, 2)

        # Fail path returns exit code 1
        (sb / audit.REPORT_FILENAME).unlink()
        err_buf = io.StringIO()
        with redirect_stderr(err_buf):
            rc_fail = audit.main(["--track-dir", str(sb), "--standalone"])
        self.assertEqual(rc_fail, 1)
        self.assertIn("AUDIT_FAIL", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
