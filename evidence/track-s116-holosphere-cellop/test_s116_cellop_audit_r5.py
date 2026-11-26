#!/usr/bin/env python3
"""Pure-Stdlib R5 Unit & Mutation-Kill Suite for `s116_cellop_audit.py`.

Strictly Python standard library ONLY (`0` third-party imports, `0` bare asserts, `0` skips).
Exercises every `require_ok` guard, exact threshold boundary (`CONFIRMED` / `PARTIAL` /
`FALSIFIED` / `UNIFIED_CONFIRMED` across all 5 pure grading functions), non-finite JSON
rejection (`NaN`/`Infinity`/`-Infinity`/`1e999`), Zone-B receipt binding & same-window swap
refusal, `ptxas` zero-spill/SASS refusal, `CS-08` & Holm-Bonferroni tamper refusal, Lean 4
source integrity, directory hygiene (`WEIGHTS`/`AV`/`ELF`), and CLI modes.
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

import s116_cellop_audit as aud  # noqa: E402


def _resign(obj: Dict[str, Any], field: str) -> Dict[str, Any]:
    body = {k: v for k, v in obj.items() if k != field}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    out = dict(body)
    out[field] = hashlib.sha256(raw).hexdigest()
    return out


class TestS116CellOpAuditR5(unittest.TestCase):
    def _copy_bundle(self, td: str) -> Path:
        dst = Path(td) / "bundle"
        shutil.copytree(_HERE, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return dst

    def _expect_code(self, fn: Callable[[], Any], code: str) -> None:
        with self.assertRaises(aud.S116AuditError) as ctx:
            fn()
        self.assertEqual(ctx.exception.code, code)

    def _rebind_receipt(self, dst: Path, rec_name: str, res_name: str, has_inner: bool) -> None:
        res_p = dst / res_name
        res_obj = json.loads(res_p.read_text(encoding="utf-8"))
        if has_inner:
            res_obj = _resign(res_obj, "payload_sha256")
            res_p.write_text(json.dumps(res_obj, sort_keys=True), encoding="utf-8")
            inner = res_obj["payload_sha256"]
        else:
            inner = hashlib.sha256(aud._canonical_bytes(res_obj)).hexdigest()
        rec_p = dst / rec_name
        rec = json.loads(rec_p.read_text(encoding="utf-8"))
        old_sha = rec["receipt_sha256"]
        rec["result_sha256"] = inner
        rec["bound_result_file_sha256"] = hashlib.sha256(res_p.read_bytes()).hexdigest()
        rec = _resign(rec, "receipt_sha256")
        rec_p.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")
        rep_p = dst / aud.REPORT_FILENAME
        rep_p.write_text(rep_p.read_text(encoding="utf-8").replace(old_sha, rec["receipt_sha256"]), encoding="utf-8")

    def test_01_live_certificate_and_cli_modes(self) -> None:
        cert = aud.build_certificate(_HERE)
        self.assertEqual(cert["schema"], aud.SCHEMA_VERSION)
        self.assertEqual(cert["n2_claims"], 0)
        self.assertEqual(
            cert["verdicts"],
            {
                "H16a_v2": "CONFIRMED",
                "H16c_v2": "CONFIRMED",
                "H16e_v1": "PARTIAL",
                "H16e_v2": "PARTIAL",
                "H16e_v3": "FALSIFIED",
            },
        )
        self.assertEqual(cert["hygiene"], {"weights_count": 0, "av_count": 0, "elf_count": 0})
        self.assertEqual(cert["lean"]["theorem_count"], 5)
        self.assertEqual(cert["ptxas"]["kernel_count"], 10)
        self.assertEqual(len(cert["cert_sha256"]), 64)
        self.assertGreater(cert["h16a_v2"]["speedup_vs_pt12l_t2048"], 106.0)
        self.assertGreater(cert["h16a_v2"]["speedup_vs_pt12l_t8192"], 113.0)
        self.assertGreater(cert["h16c_v2"]["pinned_4pass_gb_s"], 525.0)
        self.assertAlmostEqual(cert["h16e_v3"]["a5_m_s3_ood_pct"]["T256"], 81.1849, places=4)

        with tempfile.TemporaryDirectory() as td:
            d = self._copy_bundle(td)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(aud.main(["--track-dir", str(d), "--write"]), 0)
                self.assertIn("S116_CELLOP_AUDIT_OK", out.getvalue())
                cert_p = d / aud.CERT_FILENAME
                self.assertEqual(aud.main(["--track-dir", str(d), "--check", str(cert_p)]), 0)
                self.assertEqual(aud.main(["--track-dir", str(d), "--check"]), 0)
                self.assertEqual(aud.main(["--track-dir", str(d)]), 0)
                out.seek(0)
                out.truncate(0)
                self.assertEqual(aud.main(["--track-dir", str(d), "--standalone", "--json"]), 0)
                parsed = json.loads(out.getvalue())
                self.assertEqual(parsed["cert_sha256"], cert["cert_sha256"])

                # CLI conflicts fail closed (rc=2)
                self.assertEqual(aud.main(["--track-dir", str(d), "--write", "--check"]), 2)
                self.assertIn("CLI_CONFLICT", err.getvalue())
                self.assertEqual(aud.main(["--track-dir", str(d), "--write", "--standalone"]), 2)
                self.assertEqual(aud.main(["--track-dir", str(d), "--check", "--standalone"]), 2)

                # Tampered cert inner hash & drifted cert_sha256 fail closed (rc=2)
                bad = json.loads(cert_p.read_text(encoding="utf-8"))
                bad["n2_claims"] = 1
                cert_p.write_text(json.dumps(bad), encoding="utf-8")
                self.assertEqual(aud.main(["--track-dir", str(d), "--check"]), 2)
                cert_p.write_text(json.dumps(_resign(bad, "cert_sha256")), encoding="utf-8")
                err.seek(0)
                err.truncate(0)
                self.assertEqual(aud.main(["--track-dir", str(d), "--check"]), 2)
                self.assertIn("CERT_DRIFT", err.getvalue())

                # Non-finite JSON constants & overflow float MUST fail closed (MALFORMED_JSON)
                for lit in ("NaN", "Infinity", "-Infinity", "1e999"):
                    err.seek(0)
                    err.truncate(0)
                    cert_p.write_text('{"cert_sha256":"' + ("0" * 64) + '","x":' + lit + "}\n", encoding="utf-8")
                    self.assertEqual(aud.main(["--track-dir", str(d), "--check"]), 2)
                    self.assertIn("MALFORMED_JSON", err.getvalue())

    def test_02_pure_grading_boundaries_all_five_gates(self) -> None:
        # H16a-v2 exact boundaries
        self.assertEqual(
            aud.grade_h16a_v2_pure(
                zero_spill=True, hmma_zero=True, parity_pass=True,
                speedup_vs_pt12l=3.0, speedup_vs_switch_48cta=3.0, speedup_vs_perop_48=1.01,
            )["verdict"],
            "CONFIRMED",
        )
        self.assertEqual(
            aud.grade_h16a_v2_pure(
                zero_spill=True, hmma_zero=True, parity_pass=True,
                speedup_vs_pt12l=2.99, speedup_vs_switch_48cta=2.0, speedup_vs_perop_48=1.01,
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            aud.grade_h16a_v2_pure(
                zero_spill=True, hmma_zero=True, parity_pass=True,
                speedup_vs_pt12l=3.0, speedup_vs_switch_48cta=1.99, speedup_vs_perop_48=1.0,
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            aud.grade_h16a_v2_pure(
                zero_spill=True, hmma_zero=True, parity_pass=True,
                speedup_vs_pt12l=2.99, speedup_vs_switch_48cta=1.99, speedup_vs_perop_48=1.5,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            aud.grade_h16a_v2_pure(
                zero_spill=False, hmma_zero=True, parity_pass=True,
                speedup_vs_pt12l=10.0, speedup_vs_switch_48cta=10.0, speedup_vs_perop_48=5.0,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            aud.grade_h16a_v2_pure(
                zero_spill=True, hmma_zero=False, parity_pass=True,
                speedup_vs_pt12l=10.0, speedup_vs_switch_48cta=10.0, speedup_vs_perop_48=5.0,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            aud.grade_h16a_v2_pure(
                zero_spill=True, hmma_zero=True, parity_pass=False,
                speedup_vs_pt12l=10.0, speedup_vs_switch_48cta=10.0, speedup_vs_perop_48=5.0,
            )["verdict"],
            "FALSIFIED",
        )

        # H16c-v2 exact boundaries
        self.assertEqual(
            aud.grade_h16c_v2_pure(
                clamp_exact=True, pin_speedup_t2048=1.25, pin_speedup_t8192_1pass=1.25,
                pinned_4pass_vs_stream=1.25, weight_in_a_vs_b=1.01,
            )["verdict"],
            "CONFIRMED",
        )
        self.assertEqual(
            aud.grade_h16c_v2_pure(
                clamp_exact=True, pin_speedup_t2048=1.24, pin_speedup_t8192_1pass=1.25,
                pinned_4pass_vs_stream=1.25, weight_in_a_vs_b=1.5,
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            aud.grade_h16c_v2_pure(
                clamp_exact=True, pin_speedup_t2048=1.25, pin_speedup_t8192_1pass=1.24,
                pinned_4pass_vs_stream=1.24, weight_in_a_vs_b=1.5,
            )["verdict"],
            "FALSIFIED",
        )
        self.assertEqual(
            aud.grade_h16c_v2_pure(
                clamp_exact=True, pin_speedup_t2048=1.3, pin_speedup_t8192_1pass=1.3,
                pinned_4pass_vs_stream=1.3, weight_in_a_vs_b=1.0,
            )["verdict"],
            "PARTIAL",
        )
        self.assertEqual(
            aud.grade_h16c_v2_pure(
                clamp_exact=False, pin_speedup_t2048=1.5, pin_speedup_t8192_1pass=1.5,
                pinned_4pass_vs_stream=1.5, weight_in_a_vs_b=1.5,
            )["verdict"],
            "FALSIFIED",
        )

        # H16e-v1 exact boundaries
        base_v1 = dict(
            s3_acc=50.0, s3_gain_a0=15.0, s3_gain_a2=15.0, s3_p_a0=0.0099, s3_p_a2=0.0099,
            a5_acc=15.0, a5_gain_a0=8.0, a5_gain_a2=8.0, a5_p_a0=0.0099, a5_p_a2=0.0099,
            utf8_delta_pct=1.0,
        )
        self.assertEqual(aud.grade_h16e_v1_pure(**base_v1)["verdict"], "CONFIRMED")
        self.assertEqual(aud.grade_h16e_v1_pure(**{**base_v1, "utf8_delta_pct": 1.01})["verdict"], "PARTIAL")
        for key, bad_val in (
            ("s3_acc", 49.99), ("s3_gain_a0", 14.99), ("s3_gain_a2", 14.99),
            ("s3_p_a0", 0.01), ("s3_p_a2", 0.01),
            ("a5_acc", 14.99), ("a5_gain_a0", 7.99), ("a5_gain_a2", 7.99),
            ("a5_p_a0", 0.01), ("a5_p_a2", 0.01),
        ):
            self.assertEqual(aud.grade_h16e_v1_pure(**{**base_v1, key: bad_val})["verdict"], "PARTIAL")
        self.assertEqual(
            aud.grade_h16e_v1_pure(**{**base_v1, "s3_acc": 49.99, "a5_acc": 14.99})["verdict"],
            "FALSIFIED",
        )

        # H16e-v2 exact boundaries
        base_v2 = dict(
            a5_wa5_acc=50.0, a5_wa5_gain_a0=8.0, a5_wa5_gain_a2=8.0, a5_wa5_p_a0=0.0099, a5_wa5_p_a2=0.0099,
            a4_wa5_acc=50.0, a4_wa5_gain_a0=8.0, a4_wa5_gain_a2=8.0, a4_wa5_p_a0=0.0099, a4_wa5_p_a2=0.0099,
            a5_ms3_gain_a2=20.0, a5_ms3_gain_a4=20.0, a5_ms3_p_a2=0.0099, a5_ms3_p_a4=0.0099,
            a5_utf8_bpb=4.0, a3_utf8_bpb=4.01, a4_utf8_bpb=4.01, a5_utf8_delta_pct=1.0,
        )
        self.assertEqual(aud.grade_h16e_v2_pure(**base_v2)["verdict"], "UNIFIED_CONFIRMED")
        for key, bad_val in (
            ("a5_wa5_acc", 49.99), ("a5_wa5_gain_a0", 7.99), ("a5_wa5_gain_a2", 7.99),
            ("a5_wa5_p_a0", 0.01), ("a5_wa5_p_a2", 0.01),
            ("a5_ms3_gain_a2", 19.99), ("a5_ms3_gain_a4", 19.99),
            ("a5_ms3_p_a2", 0.01), ("a5_ms3_p_a4", 0.01),
            ("a5_utf8_bpb", 4.01), ("a3_utf8_bpb", 4.0), ("a4_utf8_bpb", 4.0),
        ):
            self.assertEqual(aud.grade_h16e_v2_pure(**{**base_v2, key: bad_val})["verdict"], "PARTIAL")
        fail_a5 = {**base_v2, "a5_wa5_acc": 10.0, "a5_ms3_gain_a2": 5.0}
        self.assertEqual(aud.grade_h16e_v2_pure(**fail_a5)["verdict"], "PARTIAL")
        for key, bad_val in (
            ("a4_wa5_acc", 49.99), ("a4_wa5_gain_a0", 7.99), ("a4_wa5_gain_a2", 7.99),
            ("a4_wa5_p_a0", 0.01), ("a4_wa5_p_a2", 0.01), ("a5_utf8_delta_pct", 1.01),
        ):
            self.assertEqual(aud.grade_h16e_v2_pure(**{**fail_a5, key: bad_val})["verdict"], "FALSIFIED")

        # H16e-v3 exact boundaries
        base_v3 = dict(
            a6_ms3=90.0, a6_ma5=50.0, a4_ma5=5.0, a5_ma5=49.9, a6_vs_a4_p_holm=0.0099, a6_m2=10.0, a5_m2=20.0
        )
        self.assertEqual(aud.grade_h16e_v3_pure(**base_v3)["verdict"], "CONFIRMED")
        self.assertEqual(
            aud.grade_h16e_v3_pure(**{**base_v3, "a5_ma5": 50.0, "a6_m2": 20.1})["verdict"],
            "CONFIRMED",
        )
        self.assertEqual(aud.grade_h16e_v3_pure(**{**base_v3, "a5_ma5": 50.0, "a6_m2": 20.0})["verdict"], "PARTIAL")
        self.assertEqual(aud.grade_h16e_v3_pure(**{**base_v3, "a6_ma5": 49.99})["verdict"], "PARTIAL")
        self.assertEqual(aud.grade_h16e_v3_pure(**{**base_v3, "a4_ma5": 5.01})["verdict"], "PARTIAL")
        self.assertEqual(aud.grade_h16e_v3_pure(**{**base_v3, "a6_vs_a4_p_holm": 0.01})["verdict"], "PARTIAL")
        self.assertEqual(aud.grade_h16e_v3_pure(**{**base_v3, "a6_ma5": 14.99, "a6_m2": 15.0})["verdict"], "PARTIAL")
        self.assertEqual(aud.grade_h16e_v3_pure(**{**base_v3, "a6_ma5": 14.99, "a6_m2": 14.99})["verdict"], "FALSIFIED")
        self.assertEqual(aud.grade_h16e_v3_pure(**{**base_v3, "a6_ms3": 89.99})["verdict"], "FALSIFIED")

    def test_03_math_and_parser_helpers_fail_closed(self) -> None:
        self.assertAlmostEqual(aud.student_t_two_sided_df2_p(0.0), 1.0, places=12)
        self._expect_code(lambda: aud.student_t_two_sided_df2_p(-0.1), "BAD_ABS_T")
        self._expect_code(lambda: aud.holm_bonferroni_adjust([]), "HOLM_EMPTY")
        self._expect_code(lambda: aud.holm_bonferroni_adjust([-0.01]), "HOLM_P_BOUNDS")
        self._expect_code(lambda: aud.holm_bonferroni_adjust([1.01]), "HOLM_P_BOUNDS")
        self.assertEqual(aud.holm_bonferroni_adjust([0.0, 1.0]), [0.0, 1.0])
        self._expect_code(lambda: aud.recompute_paired_t_df2([1.0, 2.0], [1.0, 2.0]), "PAIRED_LEN3")
        self._expect_code(lambda: aud.recompute_paired_t_df2([1.0, 2.0, 3.0], [1.0, 2.0]), "PAIRED_LEN3")
        zero_t = aud.recompute_paired_t_df2([5.0, 5.0, 5.0], [5.0, 5.0, 5.0])
        self.assertEqual(zero_t["t_stat"], 0.0)
        const_t = aud.recompute_paired_t_df2([6.0, 6.0, 6.0], [5.0, 5.0, 5.0])
        self.assertEqual(const_t["t_stat"], 1e6)

        self._expect_code(lambda: aud._as_float(True, "b"), "BAD_NUMBER")
        self._expect_code(lambda: aud._as_float(float("nan"), "n"), "BAD_NUMBER")
        self._expect_code(lambda: aud._as_float("1.0", "s"), "BAD_NUMBER")
        self._expect_code(lambda: aud._as_int("1", "s"), "BAD_INT")
        self._expect_code(lambda: aud._as_int(True, "b"), "BAD_INT")
        self._expect_code(lambda: aud._parse_utc(123, "ts"), "BAD_TIMESTAMP")
        self._expect_code(lambda: aud._parse_utc("not-a-date", "ts"), "BAD_TIMESTAMP")
        self._expect_code(lambda: aud._parse_utc("2026-11-26T00:00:00", "ts"), "NAIVE_TIMESTAMP")

        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._expect_code(lambda: aud._sha256_file(p / "missing.txt"), "MISSING_FILE")
            self._expect_code(lambda: aud._load_json_dict(p / "missing.json"), "MISSING_JSON")
            arr_p = p / "arr.json"
            arr_p.write_text("[1, 2, 3]\n", encoding="utf-8")
            self._expect_code(lambda: aud._load_json_dict(arr_p), "SCHEMA_ROOT")
            bad_hash_obj = {"a": 1, "receipt_sha256": "short"}
            self._expect_code(lambda: aud._verify_inner_hash(bad_hash_obj, "receipt_sha256", "x"), "MISSING_INNER_HASH")

    def test_04_hygiene_prereg_lean_report_and_ptxas_refusals(self) -> None:
        # Directory hygiene: WEIGHTS, AV, ELF suffix, and ELF magic
        for fname, content, code in (
            ("bad.pt", b"weights", "HYGIENE_WEIGHTS"),
            ("bad.wav", b"audio", "HYGIENE_AV"),
            ("bad.so", b"not-elf", "HYGIENE_ELF"),
            ("sneaky.txt", b"\x7fELFbinary", "HYGIENE_ELF"),
        ):
            with tempfile.TemporaryDirectory() as td:
                d = self._copy_bundle(td)
                (d / fname).write_bytes(content)
                self._expect_code(lambda: aud.build_certificate(d), code)

        # PREREG tamper
        with tempfile.TemporaryDirectory() as td:
            d = self._copy_bundle(td)
            p = d / aud.PREREG_SPECS[0][1]
            p.write_text(p.read_text(encoding="utf-8") + " ", encoding="utf-8")
            self._expect_code(lambda: aud.build_certificate(d), "PREREG_SHA_MISMATCH")

        # Report missing receipt SHA
        with tempfile.TemporaryDirectory() as td:
            d = self._copy_bundle(td)
            (d / aud.REPORT_FILENAME).write_text("# Empty report\n", encoding="utf-8")
            self._expect_code(lambda: aud.build_certificate(d), "REPORT_MISSING_RECEIPT")

        # Lean SHA tamper, forbidden token, and missing theorem
        with tempfile.TemporaryDirectory() as td:
            d = self._copy_bundle(td)
            lp = d / aud.LEAN_RELPATH
            lp.write_text(lp.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self._expect_code(lambda: aud.build_certificate(d), "LEAN_SHA_MISMATCH")

        orig_lean_sha = aud.LEAN_SHA256
        try:
            with tempfile.TemporaryDirectory() as td:
                d = self._copy_bundle(td)
                lp = d / aud.LEAN_RELPATH
                bad_src = lp.read_text(encoding="utf-8") + "\ntheorem bad_sorry : True := sorry\n"
                lp.write_text(bad_src, encoding="utf-8")
                aud.LEAN_SHA256 = hashlib.sha256(lp.read_bytes()).hexdigest()
                self._expect_code(lambda: aud._verify_lean_artifact(d), "LEAN_FORBIDDEN_TOKEN")

                no_ax = "\n".join(ln for ln in lp.read_text(encoding="utf-8").splitlines() if "bad_sorry" not in ln and not ln.startswith("#print axioms"))
                lp.write_text(no_ax + "\n", encoding="utf-8")
                aud.LEAN_SHA256 = hashlib.sha256(lp.read_bytes()).hexdigest()
                self._expect_code(lambda: aud._verify_lean_artifact(d), "LEAN_THEOREM_SET")
        finally:
            aud.LEAN_SHA256 = orig_lean_sha

        # ptxas tamper matrix
        ptx_cases = [
            (lambda o: o.__setitem__("all_zero_spill", False), "PTXAS_SPILL_FLAG"),
            (lambda o: o["kernels"].pop(), "PTXAS_KERNEL_COUNT"),
            (lambda o: o.__setitem__("kernel_count", 9), "PTXAS_COUNT_FIELD"),
            (lambda o: o["kernels"][0].__setitem__("spill_loads_bytes", False), "BAD_INT"),
            (lambda o: o["kernels"][0].__setitem__("spill_stores_bytes", False), "BAD_INT"),
            (lambda o: o["kernels"][0].__setitem__("stack_frame_bytes", False), "BAD_INT"),
            (lambda o: o["kernels"][0].__setitem__("registers", True), "BAD_INT"),
            (lambda o: o["kernels"][0].__setitem__("spill_loads_bytes", 4), "PTXAS_NONZERO_SPILL"),
            (lambda o: o["kernels"][0].__setitem__("spill_stores_bytes", 4), "PTXAS_NONZERO_SPILL"),
            (lambda o: o["kernels"][0].__setitem__("stack_frame_bytes", 4), "PTXAS_NONZERO_SPILL"),
            (lambda o: [k.__setitem__("registers", 76) for k in o["kernels"] if "uniform_cell_8warp_sm86" in k["name"]], "PTXAS_U8_REGS"),
            (lambda o: [k.__setitem__("registers", 0) for k in o["kernels"] if "uniform_cell_8warp_sm86" in k["name"]], "PTXAS_U8_REGS"),
            (lambda o: o.__setitem__("per_kernel_sass_counts", {}), "PTXAS_U8_SASS"),
            (lambda o: [v.__setitem__("IMMA.16832", 0) for k, v in o["per_kernel_sass_counts"].items() if "uniform_cell_8warp_sm86" in k], "PTXAS_NO_IMMA"),
            (lambda o: [v.__setitem__("HMMA.16816", 1) for k, v in o["per_kernel_sass_counts"].items() if "uniform_cell_8warp_sm86" in k], "PTXAS_HMMA_PRESENT"),
        ]
        for mut, code in ptx_cases:
            with tempfile.TemporaryDirectory() as td:
                d = self._copy_bundle(td)
                p = d / aud.PTXAS_FILENAME
                obj = json.loads(p.read_text(encoding="utf-8"))
                mut(obj)
                p.write_text(json.dumps(obj), encoding="utf-8")
                self._expect_code(lambda: aud.build_certificate(d), code)

    def test_05_zone_b_receipt_and_result_stat_tamper_refusals(self) -> None:
        rec_name = "mlos_zone_b_s116_h16e_v3.json"
        res_name = "s116_h16e_v3_gpu_results.json"

        # Receipt field tampering matrix
        rec_cases = [
            (lambda r: r.__setitem__("schema", "bad"), "RECEIPT_SCHEMA"),
            (lambda r: r.__setitem__("determinism_zone", "A"), "RECEIPT_ZONE"),
            (lambda r: r.__setitem__("clean_hardware_run", False), "RECEIPT_UNCLEAN"),
            (lambda r: r.__setitem__("anomalies", ["thermal"]), "RECEIPT_ANOMALIES"),
            (lambda r: r.__setitem__("gpu_telemetry_available", False), "RECEIPT_NO_GPU_TEL"),
            (lambda r: r.__setitem__("original_unmodified_run_receipt_sha256", "0" * 64), "RECEIPT_ORIG_SHA"),
            (lambda r: r.__setitem__("preregistration_sha256", "0" * 64), "RECEIPT_PREREG_BIND"),
            (lambda r: r["execution"].__setitem__("exit_code", 1), "RECEIPT_EXIT_CODE"),
            (lambda r: r["execution"].__setitem__("ended_utc", "2020-01-01T00:00:00Z"), "RECEIPT_TIME_ORDER"),
            (lambda r: r.__setitem__("result_sha256", "0" * 64), "RECEIPT_RESULT_BIND"),
            (lambda r: r.__setitem__("bound_result_file_sha256", "0" * 64), "RECEIPT_FILE_BIND"),
        ]
        for mut, code in rec_cases:
            with tempfile.TemporaryDirectory() as td:
                d = self._copy_bundle(td)
                rp = d / rec_name
                rec = json.loads(rp.read_text(encoding="utf-8"))
                mut(rec)
                rec = _resign(rec, "receipt_sha256")
                rp.write_text(json.dumps(rec), encoding="utf-8")
                self._expect_code(lambda: aud.build_certificate(d), code)

        # Unresigned receipt fails INNER_HASH_MISMATCH
        with tempfile.TemporaryDirectory() as td:
            d = self._copy_bundle(td)
            rp = d / rec_name
            rec = json.loads(rp.read_text(encoding="utf-8"))
            rec["anomalies"] = ["tamper"]
            rp.write_text(json.dumps(rec), encoding="utf-8")
            self._expect_code(lambda: aud.build_certificate(d), "INNER_HASH_MISMATCH")

        # Same-window results swap attack (resigned result, untouched receipt) fails RECEIPT_RESULT_BIND
        with tempfile.TemporaryDirectory() as td:
            d = self._copy_bundle(td)
            sp = d / res_name
            res = json.loads(sp.read_text(encoding="utf-8"))
            res["swap_tag"] = "attack"
            sp.write_text(json.dumps(_resign(res, "payload_sha256")), encoding="utf-8")
            self._expect_code(lambda: aud.build_certificate(d), "RECEIPT_RESULT_BIND")

        # Phase-2B live parity failure (rebound receipt)
        for pkey, pval in (
            ("all_parity_pass", False),
            ("fmnmx_onehot_nan_desyncs", 1),
            ("fmnmx_onehot_imma_max_int32_diff", 1),
            ("weight_in_a_imma_max_int32_diff", 1),
            ("weight_in_a_valid_syndrome_errors", 1),
            ("weight_in_a_injected_16_flips_caught", 15),
            ("cell8warp_2cta_syndrome_errors", 1),
            ("cell8warp_2cta_nan_desyncs", 1),
            ("cell8warp_2cta_passb_max_int32_diff", 1),
            ("cell8warp_2cta_16b_pi_t0_rollback_max_drift", 1e-5),
        ):
            with tempfile.TemporaryDirectory() as td:
                d = self._copy_bundle(td)
                sp = d / "s116_phase2b_gpu_results.json"
                obj = json.loads(sp.read_text(encoding="utf-8"))
                obj["phase2b_live_parity"][pkey] = pval
                sp.write_text(json.dumps(obj), encoding="utf-8")
                self._rebind_receipt(d, "mlos_zone_b_s116_phase2b.json", "s116_phase2b_gpu_results.json", False)
                self._expect_code(lambda: aud.build_certificate(d), "PHASE2B_PARITY_FAIL")

        # CS-08 violation, CS-08 mismatch, stat mismatches, & verdict mismatches (rebound receipts)
        v3_cases = [
            (lambda o: o["tasks"]["H16e_M_S3"]["arms"]["A6_RelationalCellOp"].__setitem__("non_embedding_params", 96000), "CS08_VIOLATION"),
            (lambda o: o["tasks"]["H16e_M_S3"].__setitem__("cs08_max_non_embed_param_delta_pct", 0.45), "CS08_MISMATCH"),
            (lambda o: o["tasks"]["H16e_M_S3"]["stats_t128"]["A6_vs_A5"].__setitem__("mean_diff", 0.0), "STAT_DIFF_MISMATCH"),
            (lambda o: o["tasks"]["H16e_M_S3"]["stats_t128"]["A6_vs_A5"].__setitem__("t_stat", 0.0), "STAT_T_MISMATCH"),
            (lambda o: o["tasks"]["H16e_M_S3"]["stats_t128"]["A6_vs_A5"].__setitem__("p_raw", 0.5), "STAT_PRAW_MISMATCH"),
            (lambda o: o["tasks"]["H16e_M_S3"]["stats_t128"]["A6_vs_A5"].__setitem__("p_holm", 0.5), "STAT_PHOLM_MISMATCH"),
            (lambda o: o["prereg_s116_amendment4_gate"].__setitem__("verdict", "CONFIRMED"), "H16E_V3_VERDICT_MISMATCH"),
        ]
        for mut, code in v3_cases:
            with tempfile.TemporaryDirectory() as td:
                d = self._copy_bundle(td)
                sp = d / res_name
                obj = json.loads(sp.read_text(encoding="utf-8"))
                mut(obj)
                sp.write_text(json.dumps(obj), encoding="utf-8")
                self._rebind_receipt(d, rec_name, res_name, True)
                self._expect_code(lambda: aud.build_certificate(d), code)

        # Exact boundary equality tests (kills all 7 boundary_cmp_require mutants!)
        # 1) Receipt ended_utc == started_utc MUST PASS
        with tempfile.TemporaryDirectory() as td:
            d = self._copy_bundle(td)
            rp = d / rec_name
            rec = json.loads(rp.read_text(encoding="utf-8"))
            old_sha = rec["receipt_sha256"]
            rec["execution"]["ended_utc"] = rec["execution"]["started_utc"]
            rec = _resign(rec, "receipt_sha256")
            rp.write_text(json.dumps(rec), encoding="utf-8")
            rep_p = d / aud.REPORT_FILENAME
            rep_p.write_text(rep_p.read_text(encoding="utf-8").replace(old_sha, rec["receipt_sha256"]), encoding="utf-8")
            self.assertEqual(aud.build_certificate(d)["verdicts"]["H16e_v3"], "FALSIFIED")

        # 2) Exact CS-08 == 0.5% and exact dyadic STAT_TOL_COARSE / STAT_TOL_PROB boundary equality MUST PASS
        eq_tasks = {
            "T_eq": {
                "cs08_max_non_embed_param_delta_pct": 0.5 - aud.STAT_TOL_COARSE,
                "arms": {
                    "A0_base": {
                        "non_embedding_params": 100000,
                        "per_seed": [{"ood_final_acc_pct": {"T128": 10.0}} for _ in range(3)],
                    },
                    "A1_cand": {
                        "non_embedding_params": 100500,
                        "per_seed": [{"ood_final_acc_pct": {"T128": 10.0}} for _ in range(3)],
                    },
                },
                "stats_t128": {
                    "A1_vs_A0": {
                        "mean_diff": aud.STAT_TOL_COARSE,
                        "t_stat": aud.STAT_TOL_COARSE,
                        "p_raw": 1.0 - aud.STAT_TOL_PROB,
                        "p_holm": 1.0 - aud.STAT_TOL_PROB,
                    }
                },
            }
        }
        eq_res = aud._audit_group_tasks(eq_tasks, "A0_base", "boundary_eq")
        self.assertEqual(eq_res["T_eq"]["cs08_max_delta_pct"], 0.5)

        # H16e-v1 and H16e-v2 verdict tamper checks
        for rec_n, res_n, gkey, code in (
            ("mlos_zone_b_s116_h16e.json", "s116_h16e_gpu_results.json", "prereg_s116_amendment2_gate", "H16E_V1_VERDICT_MISMATCH"),
            ("mlos_zone_b_s116_h16e_v2.json", "s116_h16e_v2_gpu_results.json", "prereg_s116_amendment3_gate", "H16E_V2_VERDICT_MISMATCH"),
        ):
            with tempfile.TemporaryDirectory() as td:
                d = self._copy_bundle(td)
                sp = d / res_n
                obj = json.loads(sp.read_text(encoding="utf-8"))
                obj[gkey]["verdict"] = "CONFIRMED"
                sp.write_text(json.dumps(obj), encoding="utf-8")
                self._rebind_receipt(d, rec_n, res_n, True)
                self._expect_code(lambda: aud.build_certificate(d), code)


if __name__ == "__main__":
    unittest.main()
