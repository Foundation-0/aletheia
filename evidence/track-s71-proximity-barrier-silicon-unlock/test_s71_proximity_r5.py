"""Comprehensive R5 Unit & Adversarial Verification Suite for S71 Proximity Barrier & AVX-512 Unlock.

Covers 100% of oracle & audit mutation surfaces, whole-file DFS AST BoolOp clauses,
R8 Lean 4.36.0 static/live security scanner, strict Zone-B dir_fd I/O (O_NONBLOCK FIFO,
EIO, ENOSPC, short-write, temp tamper, symlink/hardlink, inode-matched $PWD, Darwin prefix),
pre-int() 5,001-digit guard, ZeroDivisionError, and bool-in-int receipt rejection.
Zero floats, zero bare asserts, scratch FIFO only.
"""

from __future__ import annotations

import copy
from decimal import Decimal
import errno
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from typing import Any
from unittest import mock

STUDY_DIR = Path(__file__).resolve().parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

import s71_proximity_audit as audit
import s71_proximity_oracle as oracle


class _IntSub(int):
    pass


class _StrSub(str):
    pass


class _DictSub(dict):
    pass


class _ListSub(list):
    pass


class _FloatSub(float):
    pass


def _resign(cert: dict[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in cert.items() if k != "certificate_sha256"}
    out = dict(body)
    out["certificate_sha256"] = hashlib.sha256(oracle.canonical_json_bytes(body)).hexdigest()
    return out


class TestS71OracleAndReceipts(unittest.TestCase):
    def test_helpers_exact_verdict_and_all_gates(self) -> None:
        self.assertEqual(oracle.q_pair(Fraction(9, 2)), [9, 2])
        self.assertTrue(oracle._is_int_eq(0, 0))
        self.assertFalse(oracle._is_int_eq(False, 0))
        self.assertFalse(oracle._is_int_eq(1, 0))
        self.assertTrue(oracle._is_pos_int(1))
        self.assertFalse(oracle._is_pos_int(True))
        self.assertFalse(oracle._is_pos_int(0))

        # Float & float-subclass rejection in canonical_json_bytes (including tuple & container subclasses)
        for bad_obj in (
            {"x": Fraction(3, 2).__float__()},
            {"x": _FloatSub(Fraction(3, 2))},
            _DictSub({"x": _FloatSub(Fraction(1, 2))}),
            _ListSub([_FloatSub(Fraction(1, 4))]),
            {"a": [1, {"b": Fraction(1, 2).__float__()}]},
            (1, Fraction(1, 4).__float__()),
        ):
            with self.assertRaises(TypeError):
                oracle.canonical_json_bytes(bad_obj)
        self.assertEqual(oracle.canonical_json_bytes((1, 2)), b"[1,2]\n")
        self.assertEqual(oracle._dump_compact_exact({"a": [Decimal("13.27"), 1]}), '{"a":[13.27,1]}')

        # ISO-8601 timestamp parser boundary tests (every BoolOp & guard clause)
        self.assertEqual(oracle._parse_iso_utc_seconds("1970-01-01T00:00:00Z"), 0)
        self.assertLess(
            oracle._parse_iso_utc_seconds("2026-11-24T18:30:24Z"),
            oracle._parse_iso_utc_seconds("2026-11-24T18:33:57Z"),
        )
        for bad_ts in (
            12345,
            "2026-11-24T18:30:24",
            "2026-11-24T18:30:24X",
            "2026-11-24T18:30:24extraZ",
            "2026/11-24T18:30:24Z",
            "2026-11/24T18:30:24Z",
            "2026-11-24 18:30:24Z",
            "2026-11-24T18.30:24Z",
            "2026-11-24T18:30.24Z",
            "+026-11-24T18:30:24Z",
            "202a-11-24T18:30:24Z",
            "2026-00-24T18:30:24Z",
            "2026-13-24T18:30:24Z",
            "2026-11-00T18:30:24Z",
            "2026-11-32T18:30:24Z",
            "2026-11-24T24:30:24Z",
            "2026-11-24T18:60:24Z",
            "2026-11-24T18:30:60Z",
        ):
            with self.assertRaises(ValueError, msg=f"bad_ts={bad_ts!r}"):
                oracle._parse_iso_utc_seconds(bad_ts)  # type: ignore[arg-type]

        # _row_dark_nonneg every clause (incl. isolated pkg_uj=0 with core=uncore=0)
        good_row = {"total_ops": 10, "ns": 10, "tsc": 10, "pkg_uj": 10, "core_uj": 4, "uncore_uj": 2}
        self.assertTrue(oracle._row_dark_nonneg(good_row))
        self.assertFalse(oracle._row_dark_nonneg({"total_ops": 10, "ns": 10, "tsc": 10, "pkg_uj": 0, "core_uj": 0, "uncore_uj": 0}))
        for k, bad_v in (
            ("total_ops", 0),
            ("ns", 0),
            ("tsc", 0),
            ("pkg_uj", 0),
            ("core_uj", False),
            ("core_uj", -1),
            ("uncore_uj", False),
            ("uncore_uj", -1),
            ("uncore_uj", 7),
        ):
            bad_r = dict(good_row)
            bad_r[k] = bad_v
            self.assertFalse(oracle._row_dark_nonneg(bad_r), f"row check failed for {k}={bad_v!r}")

        # _build_exact_pillar barrier sign-flip clause isolation
        cert = oracle.build_certificate()
        self.assertTrue(cert["verdict"]["all_passed"])
        self.assertTrue(cert["verdict"]["exact_invariants_pass"])
        self.assertTrue(cert["verdict"]["sampled_gates_pass"])
        with mock.patch.object(oracle, "_delta_pot_num", side_effect=[0, -1]):
            self.assertFalse(oracle._build_exact_pillar()["barrier_sign_flip_exact"])
        with mock.patch.object(oracle, "_delta_pot_num", side_effect=[1, 0]):
            self.assertFalse(oracle._build_exact_pillar()["barrier_sign_flip_exact"])

        # Exact pillar verdict BoolOp isolation
        for patch_k, patch_v in (
            ("barrier_sign_flip_exact", False),
            ("all_8_cores_stride_8b_single_line", False),
            ("all_8_cores_stride_64b_disjoint_lines", False),
            ("qwen3b_down_proj_weights", 1),
            ("lean4_theorem_count", 11),
        ):
            p1 = oracle._build_exact_pillar()
            p1[patch_k] = patch_v
            with mock.patch.object(oracle, "_build_exact_pillar", return_value=p1):
                c_bad = oracle.build_certificate()
                self.assertFalse(c_bad["verdict"]["exact_invariants_pass"], patch_k)
                self.assertFalse(c_bad["verdict"]["all_passed"], patch_k)

        # Sampled gates BoolOp isolation on FROZEN_S71_TOKENS
        def _tamper_tokens(fn: Any) -> dict[str, Any]:
            saved = copy.deepcopy(oracle.FROZEN_S71_TOKENS)
            try:
                fn(oracle.FROZEN_S71_TOKENS)
                return oracle.build_certificate()
            finally:
                oracle.FROZEN_S71_TOKENS.clear()
                oracle.FROZEN_S71_TOKENS.update(saved)

        for idx, (gate_k, fn) in enumerate((
            ("prereg_strictly_precedes_execution", lambda t: t.__setitem__("prereg_created_utc", "2026-11-24T18:35:00Z")),
            ("prereg_strictly_precedes_execution", lambda t: t.__setitem__("mlos_ended_utc", "2026-11-24T18:33:50Z")),
            ("p_s71_1a_ww2_repulsion_ge_2x", lambda t: t["ww2_64b"].__setitem__("ns", t["ww2_8b"]["ns"])),
            ("p_s71_1a_ww2_repulsion_ge_2x", lambda t: t["ww2_64b"].__setitem__("pkg_uj", t["ww2_8b"]["pkg_uj"])),
            ("p_s71_1b_ww8_repulsion_ge_3x", lambda t: t["ww8_64b"].__setitem__("ns", t["ww8_8b"]["ns"] // 2)),
            ("p_s71_1b_ww8_repulsion_ge_3x", lambda t: t["ww8_64b"].__setitem__("pkg_uj", t["ww8_8b"]["pkg_uj"] // 2)),
            ("p_s71_1c_rd8_fusion_confirmed", lambda t: t["rd8_64b"].__setitem__("ns", t["rd8_8b"]["ns"] + 1)),
            ("p_s71_1c_rd8_fusion_confirmed", lambda t: t["rd8_64b"].__setitem__("pkg_uj", t["rd8_8b"]["pkg_uj"] + 1)),
            ("p_s71_1c_rd8_fusion_confirmed", lambda t: t["rd8_65536b"].__setitem__("ns", t["rd8_8b"]["ns"] + 1)),
            ("p_s71_1c_rd8_fusion_confirmed", lambda t: t["rd8_65536b"].__setitem__("pkg_uj", t["rd8_8b"]["pkg_uj"] + 1)),
            ("p_s71_1d_opposite_sign_3axes_and_dark_nonneg", lambda t: t["ww8_64b"].__setitem__("ns", t["ww8_8b"]["ns"] + 1)),
            ("p_s71_1d_opposite_sign_3axes_and_dark_nonneg", lambda t: t["ww8_64b"].__setitem__("tsc", t["ww8_8b"]["tsc"] + 1)),
            ("p_s71_1d_opposite_sign_3axes_and_dark_nonneg", lambda t: t["ww8_64b"].__setitem__("pkg_uj", t["ww8_8b"]["pkg_uj"] + 1)),
            ("p_s71_1d_opposite_sign_3axes_and_dark_nonneg", lambda t: t["ww8_64b"].__setitem__("core_uj", t["ww8_64b"]["pkg_uj"] + 1)),
            ("p_s71_2a_avx512_zero_errors", lambda t: t.__setitem__("a16_syndrome_errors", 1)),
            ("p_s71_2a_avx512_zero_errors", lambda t: t.__setitem__("avx512_int64_mismatches", 1)),
            ("p_s71_2a_avx512_zero_errors", lambda t: t.__setitem__("multicore_int64_mismatches", 1)),
            ("p_s71_2b_gemv_wall_break_ge_1_5x", lambda t: t["gemv_64b"].__setitem__("ns", t["gemv_8b"]["ns"])),
            ("p_s71_2b_gemv_wall_break_ge_1_5x", lambda t: t["gemv_64b"].__setitem__("pkg_uj", t["gemv_8b"]["pkg_uj"])),
            ("p_s71_2c_dual_opt_vs_8b_ge_3x", lambda t: t["gemv_dual_opt"].__setitem__("ns", t["gemv_8b"]["ns"] * 4)),
            ("p_s71_2c_dual_opt_vs_8b_ge_3x", lambda t: t["gemv_dual_opt"].__setitem__("pkg_uj", t["gemv_8b"]["pkg_uj"] * 4)),
            ("p_s71_2c_dispersed_energy_gain_confirmed_and_latency_nuance", lambda t: t["gemv_dual_opt"].__setitem__("ns", t["gemv_disp_4096b"]["ns"] + 1)),
            ("p_s71_2c_dispersed_energy_gain_confirmed_and_latency_nuance", lambda t: t["gemv_dual_opt"].__setitem__("ns", 100000)),
            ("p_s71_2c_dispersed_energy_gain_confirmed_and_latency_nuance", lambda t: t["gemv_dual_opt"].__setitem__("pkg_uj", t["gemv_disp_4096b"]["pkg_uj"] + 1)),
        )):
            c_bad = _tamper_tokens(fn)
            self.assertFalse(c_bad["pillar_2_sampled_live_i9_rapl_and_avx512"]["sampled_gates"][gate_k], f"gate {gate_k} #{idx}")
            self.assertFalse(c_bad["verdict"]["sampled_gates_pass"], f"token tamper #{idx}")
            self.assertFalse(c_bad["verdict"]["all_passed"], f"token all_passed #{idx}")

        # Test missing stride / label helper exceptions
        with self.assertRaises(KeyError):
            oracle._by_stride([], 8)
        with self.assertRaises(KeyError):
            oracle._by_label([], "missing")

    def test_verify_live_receipts_and_all_tampers(self) -> None:
        res = audit.verify_receipts_directory(STUDY_DIR)
        self.assertTrue(res["all_verified"])
        self.assertTrue(all(res["checks"].values()))

        prereg_raw = (STUDY_DIR / "s71_preregistration.json").read_bytes()
        c_raw = (STUDY_DIR / "s71_proximity_bench.c").read_bytes()
        lean_raw = (STUDY_DIR / "ProximityBarrierSilicon.lean").read_bytes()
        emp_raw = (STUDY_DIR / "s71_empirical_results.json").read_bytes()
        mlos_raw = (STUDY_DIR / "mlos_zone_b_receipt.json").read_bytes()

        p_base = json.loads(prereg_raw.decode("utf-8"))
        e_base = json.loads(emp_raw.decode("utf-8"), parse_float=Decimal)
        m_base = json.loads(mlos_raw.decode("utf-8"), parse_float=Decimal)
        p_sha, c_sha, l_sha, e_sha, m_sha = (
            hashlib.sha256(b).hexdigest() for b in (prereg_raw, c_raw, lean_raw, emp_raw, mlos_raw)
        )

        def _chk(
            p: Any, e: Any, m: Any,
            ps: str = p_sha, cs: str = c_sha, ls: str = l_sha, es: str = e_sha, ms: str = m_sha,
        ) -> dict[str, Any]:
            return oracle.verify_live_receipts(p, e, m, ps, cs, ls, es, ms)

        # Every single one of the 13 digest clauses (incl. inner canonical body recomputation!)
        for idx, (ps, cs, ls, es, ms, mut) in enumerate((
            ("0" * 64, c_sha, l_sha, e_sha, m_sha, None),
            (p_sha, "0" * 64, l_sha, e_sha, m_sha, None),
            (p_sha, c_sha, "0" * 64, e_sha, m_sha, None),
            (p_sha, c_sha, l_sha, "0" * 64, m_sha, None),
            (p_sha, c_sha, l_sha, e_sha, "0" * 64, None),
            (p_sha, c_sha, l_sha, e_sha, m_sha, lambda p, e, m: p.__setitem__("preregistration_sha256", "0" * 64)),
            (p_sha, c_sha, l_sha, e_sha, m_sha, lambda p, e, m: p.__setitem__("__tamper__", 1)),
            (p_sha, c_sha, l_sha, e_sha, m_sha, lambda p, e, m: e.__setitem__("c_source_sha256", "0" * 64)),
            (p_sha, c_sha, l_sha, e_sha, m_sha, lambda p, e, m: e.__setitem__("lean_source_sha256", "0" * 64)),
            (p_sha, c_sha, l_sha, e_sha, m_sha, lambda p, e, m: e.__setitem__("preregistration_file_sha256", "0" * 64)),
            (p_sha, c_sha, l_sha, e_sha, m_sha, lambda p, e, m: e.__setitem__("preregistration_sha256", "0" * 64)),
            (p_sha, c_sha, l_sha, e_sha, m_sha, lambda p, e, m: m.__setitem__("receipt_sha256", "0" * 64)),
            (p_sha, c_sha, l_sha, e_sha, m_sha, lambda p, e, m: m.__setitem__("__tamper__", 1)),
        )):
            p, e, m = copy.deepcopy(p_base), copy.deepcopy(e_base), copy.deepcopy(m_base)
            if mut is not None:
                mut(p, e, m)
            r = _chk(p, e, m, ps, cs, ls, es, ms)
            self.assertFalse(r["checks"]["digests_match"], f"digest #{idx}")
            self.assertFalse(r["all_verified"])

        # Causal order, mlos clean (incl. False == 0!), honesty tags, row counts & dark power
        for check_k, mut in (
            ("prereg_strictly_precedes_execution", lambda p, e, m: p.__setitem__("created_utc", "2026-11-24T18:35:00Z")),
            ("prereg_strictly_precedes_execution", lambda p, e, m: m["execution"].__setitem__("ended_utc", "2026-11-24T18:33:50Z")),
            ("mlos_clean_isolated_run", lambda p, e, m: m.__setitem__("determinism_zone", "A")),
            ("mlos_clean_isolated_run", lambda p, e, m: m.__setitem__("clean_hardware_run", False)),
            ("mlos_clean_isolated_run", lambda p, e, m: m.__setitem__("anomalies", ["thermal"])),
            ("mlos_clean_isolated_run", lambda p, e, m: m["execution"].__setitem__("exit_code", 1)),
            ("mlos_clean_isolated_run", lambda p, e, m: m["execution"].__setitem__("exit_code", False)),
            ("mlos_clean_isolated_run", lambda p, e, m: m["start_gpu_telemetry"].__setitem__("graphics_processes", [{"pid": 1}])),
            ("mlos_clean_isolated_run", lambda p, e, m: m["start_gpu_telemetry"].__setitem__("compute_processes", [{"pid": 1}])),
            ("mlos_clean_isolated_run", lambda p, e, m: m["end_gpu_telemetry"].__setitem__("graphics_processes", [{"pid": 1}])),
            ("mlos_clean_isolated_run", lambda p, e, m: m["end_gpu_telemetry"].__setitem__("compute_processes", [{"pid": 1}])),
            ("honesty_tags", lambda p, e, m: e.__setitem__("measured_live_silicon", False)),
            ("honesty_tags", lambda p, e, m: e.__setitem__("oracle_class", "exact")),
            ("honesty_tags", lambda p, e, m: e.__setitem__("ac_online", False)),
            ("all_34_rows_nonneg_rapl_dark", lambda p, e, m: e["measurements"]["write_write_2core"].pop(4)),
            ("all_34_rows_nonneg_rapl_dark", lambda p, e, m: e["measurements"]["write_write_8core"].pop(4)),
            ("all_34_rows_nonneg_rapl_dark", lambda p, e, m: e["measurements"]["read_shared_8core"].pop(4)),
            ("all_34_rows_nonneg_rapl_dark", lambda p, e, m: e["measurements"]["avx512_a16_blockh4_stride_sweep"].pop(4)),
            ("all_34_rows_nonneg_rapl_dark", lambda p, e, m: e["measurements"]["avx512_a16_blockh4_dual_force"].append(dict(e["measurements"]["avx512_a16_blockh4_dual_force"][0]))),
            ("all_34_rows_nonneg_rapl_dark", lambda p, e, m: e["measurements"]["write_write_2core"][2].__setitem__("core_uj", e["measurements"]["write_write_2core"][2]["pkg_uj"] + 1)),
            ("all_34_rows_nonneg_rapl_dark", lambda p, e, m: e["measurements"]["write_write_2core"][3].__setitem__("ns", 0)),
            ("all_34_rows_nonneg_rapl_dark", lambda p, e, m: e["measurements"]["write_write_2core"][0].__setitem__("total_ops", 0)),
            ("p_s71_2a_avx512_zero_errors", lambda p, e, m: e["measurements"].__setitem__("a16_syndrome_errors", False)),
            ("p_s71_2a_avx512_zero_errors", lambda p, e, m: e["measurements"].__setitem__("avx512_int64_mismatches", False)),
            ("p_s71_2a_avx512_zero_errors", lambda p, e, m: e["measurements"].__setitem__("multicore_int64_mismatches", False)),
        ):
            p, e, m = copy.deepcopy(p_base), copy.deepcopy(e_base), copy.deepcopy(m_base)
            mut(p, e, m)
            r = _chk(p, e, m)
            self.assertFalse(r["checks"][check_k], f"check_k={check_k}")
            self.assertFalse(r["all_verified"])


class TestS71Lean4R8AndAuditHardening(unittest.TestCase):
    def test_lean4_r8_static_and_live_verifier(self) -> None:
        lean_path = STUDY_DIR / "ProximityBarrierSilicon.lean"
        res = audit.verify_lean4_file(lean_path)
        self.assertTrue(res["valid"])
        self.assertEqual(res["theorems_verified"], 19)

        # Clean edge cases: comments, nested comments, strings, raw strings, interp strings, chars, guillemets, brackets
        clean_samples = (
            'r#"ok" sorry "#a',
            'def x := r##"sorry"##\n',
            'def ar := "ok"\ndef y := r1\ndef a.r := "ok"\n',
            's!"sorry {1 + {2}} \\"still\\"\n"\n',
            'def a := s!"hi"\ndef bs := "!"\ndef f! := 1\ndef c := "a\\"b\\nc"\n',
            'def a := as!"{sorry}"\ndef b := a.s!"{sorry}"\ndef c := q!"{sorry}"\ndef d := !"{sorry}"\n',
            '!"{sorry}"s',
            'def x := ss"{sorry}"\n',
            '/- outer /- inner sorry -/ still comment\n -/\n',
            '-- line comment sorry\n',
            'def c1 := \'a\'\ndef c2 := \'\\n\'\ndef c3 := \'\\x27\'\ndef c4 := \'\\u0027\'\n',
            'def c0 := \'"\'\n',
            '\'"\'a',
            'def \u00abok_ident\u00bb := 1\ndef \u00ab--\u00bb := 2\ndef \u00ab#eval\u00bb := 3\n',
            'def x\' := 1\ndef y := x\' + 1\ndef z := a[0]\ndef lonely := ]\n',
            '@[simp] theorem ok : 1 = 1 := rfl\n',
            'import Init\n#print axioms ok\n',
            'theorem d0 : 1 = 1 := by decide\n',
            'theorem d1 : 1 = 1 := by decide -revert\n',
            'theorem d2 : 1 = 1 := by decide (native := false)\n',
            'theorem d3 : 1 = 1 := by decide (native := (Bool.false))\n',
            'theorem d4 : 1 = 1 := by decide (revert := false) (native := false)\n',
            'theorem d5 : 1 = 1 := by decide (config := { native := false })\n',
            'theorem d6 : 1 = 1 := by decide (config := ({ revert := true, native := Bool.false }))\n',
            'theorem d7 : 1 = 1 := by decide (config := { native := false, revert := true })\n',
            'theorem d8 : 1 = 1 := by decide (config := { native := false, })\n',
            'def dc0 : DecideConfig := { native := false }\n',
            'def dc1 := ({ native := Bool.false } : DecideConfig)\n',
            'def dc2 := { native := (false) : Decide.Config }\n',
            'def lonely_rp := )\n',
            'decide   ',
            'decide + ',
            'decide (native := true',
            'decide (foo)',
        )
        for sample in clean_samples:
            r = audit.audit_lean4_source(sample)
            self.assertTrue(r["clean"], f"false positive on {sample!r}: {r}")

        # Direct _unwrap_lean4_span boundary checks
        self.assertEqual(audit._unwrap_lean4_span("   ", 0, 3, {}), (3, 3))
        self.assertEqual(audit._unwrap_lean4_span(" false ", 0, 7, {}), (1, 6))

        # Every R8 exploit & lexer boundary (kills every BoolOp clause in _strip_lean4_r8 & audit_lean4_source!)
        bad_samples = (
            ("LEAN4_UNTERMINATED_COMMENT", "/- unclosed"),
            ("LEAN4_UNTERMINATED_STRING", 'def a := "unclosed'),
            ("LEAN4_UNTERMINATED_STRING", 'def a := r#"unclosed"'),
            ("LEAN4_UNTERMINATED_STRING", 'def a := s!"unclosed'),
            ("LEAN4_UNTERMINATED_STRING", 'def a := s!"{1'),
            ("LEAN4_UNTERMINATED_IDENT", "def \u00abunclosed := 1"),
            ("LEAN4_SORRY", "theorem t : False := by sorry"),
            ("LEAN4_SORRY", "def \u00ab--\u00bb := 1\ntheorem t : False := by sorry"),
            ("LEAN4_SORRY", 'def \u00ab"\u00bb := 1\ntheorem t : False := by sorry\ndef \u00ab" \u00bb := 2'),
            ("LEAN4_SKIP_KERNEL_TC", "def \u00ab/-\u00bb := 1\nset_option debug.skipKernelTC true\ndef \u00ab-/\u00bb := 2"),
            ("LEAN4_SORRY", "def f (x' : Char) := x' '\"'\ntheorem t : False := by sorry\ndef g (y' : Char) := y' '\"'"),
            ("LEAN4_SORRY", "def f (x!' : Char) := x!' '\"'\ntheorem t : False := by sorry\ndef g (y!' : Char) := y!' '\"'"),
            ("LEAN4_SORRY", "def f (x?' : Char) := x?' '\"'\ntheorem t : False := by sorry\ndef g (y?' : Char) := y?' '\"'"),
            ("LEAN4_SORRY", "def a := '\\x27' '\"'\ntheorem t : False := by sorry\ndef b := '\"'"),
            ("LEAN4_SORRY", "def a := '\\u0027' '\"'\ntheorem t : False := by sorry\ndef b := '\"'"),
            ("LEAN4_SORRY", "def a := '\\xGG' '\"'\ntheorem t : False := by sorry\ndef b := '\"'"),
            ("LEAN4_SORRY", "def a := '\\uGGGG' '\"'\ntheorem t : False := by sorry\ndef b := '\"'"),
            ("LEAN4_UNTERMINATED_STRING", "def a := '\\\n' '\"'\ntheorem t : False := by sorry"),
            ("LEAN4_UNTERMINATED_STRING", "def a := '\n' '\"'\ntheorem t : False := by sorry"),
            ("LEAN4_SORRY", "def a := 'x\ntheorem t : False := by sorry"),
            ("LEAN4_SORRY", "def a := r#\"ok\"# sorry"),
            ("LEAN4_SORRY", 'def a := "ok" sorry'),
            ("LEAN4_SORRY", 'def a := s!"ok" sorry'),
            ("LEAN4_SORRY", 's!"{sorry}"a'),
            ("LEAN4_SORRY", 'def a := s!"{sorry}"'),
            ("LEAN4_SORRY", 'def a := ar#"ok" sorry "#'),
            ("LEAN4_SORRY", 'def a := a.r#"ok" sorry "#'),
            ("LEAN4_SORRY", 'def a := 1 - sorry'),
            ("LEAN4_SORRY", '-- comment\ntheorem t : False := by sorry'),
            ("LEAN4_SORRY", 'def a := !\'a\' sorry'),
            ("LEAN4_SORRY", 'def a := x_\' \'"\'\ntheorem t : False := by sorry\ndef b := y_\' \'"\''),
            ("LEAN4_SORRY", "theorem t : 1 = 1 := by \u00absorry\u00bb"),
            ("LEAN4_MK_SORRY", "def x := Lean.Meta.mkSorry"),
            ("LEAN4_MK_SORRY", "def x := mkSorry"),
            ("LEAN4_REDUCE_BOOL", "def x := ofReduceBool"),
            ("LEAN4_REDUCE_NAT", "def x := Lean.ofReduceNat"),
            ("LEAN4_REDUCE_NAT", "def x := ofReduceNat"),
            ("LEAN4_TRUST_COMPILER", "def x := trustCompiler"),
            ("LEAN4_EVAL_SPOOF", "#print \u00abaxioms\u00bb foo"),
            ("LEAN4_EVAL_SPOOF", "theorem ok : True := trivial#eval IO.println 1"),
            ("LEAN4_EVAL_SPOOF", "theorem ok : True := trivial#exit"),
            ("LEAN4_EVAL_SPOOF", "#print axioms!"),
            ("LEAN4_EVAL_SPOOF", "run_cmd pure ()"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide +native"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide -revert +native"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide +revert +native"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (revert := false) +native"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (native := false) +native"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (revert := true) (native := true)"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (native := true)"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (native := (true))"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (\u00abnative\u00bb := true)"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := myCfg)"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := foo})"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := {foo)"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := { a { b })"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := { a } b })"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := { base with revert := false })"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := { native })"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := { native := true })"),
            ("LEAN4_DECIDE_NATIVE", "theorem t : 1 = 1 := by decide (config := { native := false, extra })"),
            ("LEAN4_DECIDE_NATIVE", "def cfg : DecideConfig := { native := true }"),
            ("LEAN4_DECIDE_NATIVE", "def cfg := ({ native := true } : Lean.Elab.Tactic.DecideConfig)"),
            ("LEAN4_DECIDE_NATIVE", "def cfg := { native := true : Decide.Config }"),
            ("LEAN4_PARTIAL", "partial def f : Nat := f"),
            ("LEAN4_NON_INIT_IMPORT", "import Lean"),
            ("LEAN4_ATTR_TRUST_ESCAPE", 'attribute [extern "c_fn"] foo'),
            ("LEAN4_ATTR_TRUST_ESCAPE", "@[implemented_by bar] def foo := 1"),
        )
        for exp_code, src in bad_samples:
            r = audit.audit_lean4_source(src)
            codes = [f["code"] for f in r["findings"]]
            self.assertFalse(r["clean"], f"missed exploit {exp_code} in {src!r}")
            self.assertIn(exp_code, codes, f"expected {exp_code} got {codes} for {src!r}")

        # Deduplication check: DecideConfig inside decide (config := ...) reports once, not twice
        r_dedup = audit.audit_lean4_source(
            "theorem t : 1 = 1 := by decide (config := ({ native := true } : DecideConfig))"
        )
        self.assertEqual([f["code"] for f in r_dedup["findings"]], ["LEAN4_DECIDE_NATIVE"])

        # Boundary tests on _match_lean4_char_literal_end directly (every BoolOp clause!)
        self.assertIsNone(audit._match_lean4_char_literal_end("'a", 0, 2))
        self.assertIsNone(audit._match_lean4_char_literal_end("'ab", 0, 3))
        self.assertIsNone(audit._match_lean4_char_literal_end("'ab'", 0, 4))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\'", 0, 3))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\\n'", 0, 4))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\", 0, 2))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\x27", 0, 5))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\u0027", 0, 7))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\x27a", 0, 6))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\a27'", 0, 6))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\xZZ'", 0, 6))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\u0027a", 0, 8))
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\uZZZZ'", 0, 8))
        self.assertEqual(audit._match_lean4_char_literal_end("'\\x27'", 0, 6), 6)
        self.assertEqual(audit._match_lean4_char_literal_end("'\\u0027'", 0, 8), 8)
        self.assertIsNone(audit._match_lean4_char_literal_end("'\\z1234'", 0, 8))
        self.assertEqual(audit.audit_lean4_source("def a := r#")["clean"], True)
        self.assertEqual(audit.audit_lean4_source("def a := s!")["clean"], True)
        self.assertEqual(audit.audit_lean4_source("def a := '")["clean"], True)
        self.assertEqual(audit.audit_lean4_source("attribute [simp")["clean"], True)
        self.assertEqual(audit.audit_lean4_source("/- a / b -/")["clean"], True)
        self.assertEqual(audit.audit_lean4_source("/- a - b -/")["clean"], True)
        self.assertEqual(audit.audit_lean4_source("def a := 1 / 2 - 3")["clean"], True)
        self.assertEqual(audit.audit_lean4_source("def a := 1 -- comment")["clean"], True)

        # verify_lean4_file error branches + exact elan fallback BoolOp isolation
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            bad_utf = tdp / "bad.lean"
            bad_utf.write_bytes(b"\xff\xfe")
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_lean4_file(bad_utf)
            self.assertEqual(cm.exception.code, "INVALID_UTF8")

            bad_static = tdp / "sorry.lean"
            bad_static.write_text("theorem t : False := by sorry\n", encoding="utf-8")
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_lean4_file(bad_static)
            self.assertEqual(cm.exception.code, "LEAN4_STATIC_REJECT")

            # Live Lean 4.36.0 end-to-end regression: multi-flag decide +native with 12 clean #print axioms
            # compiles under real `lean` (rc=0) yet fails closed in verify_lean4_file (LEAN4_STATIC_REJECT),
            # while safe `decide (revert := false) (native := false)` passes live verify_lean4_file!
            clean_12 = "\n".join(
                f"theorem clean_{k} : {k} = {k} := rfl\n#print axioms clean_{k}"
                for k in range(12)
            )
            safe_dec = tdp / "safe_decide.lean"
            safe_dec.write_text(
                clean_12 + "\ntheorem ok_dec : 1 + 1 = 2 := by decide (revert := false) (native := false)\n",
                encoding="utf-8",
            )
            res_safe = audit.verify_lean4_file(safe_dec)
            self.assertTrue(res_safe["valid"])
            self.assertEqual(res_safe["theorems_verified"], 12)

            for idx_e, tactic in enumerate((
                "decide -revert +native",
                "decide +revert +native",
                "decide (revert := false) +native",
                "decide (native := false) +native",
                "decide (revert := true) (native := true)",
            )):
                adv_f = tdp / f"adv_decide_{idx_e}.lean"
                adv_f.write_text(
                    clean_12 + f"\ntheorem hidden_native : 1 + 1 = 2 := by {tactic}\n",
                    encoding="utf-8",
                )
                with self.assertRaises(audit.AuditError, msg=tactic) as cm:
                    audit.verify_lean4_file(adv_f)
                self.assertEqual(cm.exception.code, "LEAN4_STATIC_REJECT")
                if idx_e == 0:
                    lean_exe = shutil.which("lean") or os.fspath(Path.home() / ".elan" / "bin" / "lean")
                    live_cp = subprocess.run([lean_exe, os.fspath(adv_f)], capture_output=True, text=True, timeout=60, check=False)
                    self.assertEqual(live_cp.returncode, 0)

        fake_ok_stdout = "\n".join(f"'T.t{k}' does not depend on any axioms" for k in range(12)) + "\n"
        fake_cp_ok = subprocess.CompletedProcess(["lean"], 0, stdout=fake_ok_stdout, stderr="")
        elan_expected = os.fspath(Path.home() / ".elan" / "bin" / "lean")
        _real_exists = Path.exists

        def _exists_elan(self: Path, *a: Any, **k: Any) -> bool:
            # Force the elan fallback branch regardless of CI's Lean layout (no ~/.elan in CI).
            if os.fspath(self).endswith(os.path.join(".elan", "bin", "lean")):
                return True
            return _real_exists(self, *a, **k)

        with mock.patch("shutil.which", return_value=None), mock.patch("subprocess.run", return_value=fake_cp_ok) as m_run, mock.patch.object(Path, "exists", _exists_elan):
            res_fb = audit.verify_lean4_file(lean_path, lean_bin="lean")
            self.assertTrue(res_fb["valid"])
            self.assertEqual(m_run.call_args[0][0][0], elan_expected)
        with mock.patch("shutil.which", return_value="/usr/bin/lean"), mock.patch("subprocess.run", return_value=fake_cp_ok) as m_run2:
            self.assertTrue(audit.verify_lean4_file(lean_path, lean_bin="lean")["valid"])
            self.assertEqual(m_run2.call_args[0][0][0], "lean")
        with mock.patch("shutil.which", return_value=None), mock.patch("subprocess.run", return_value=fake_cp_ok) as m_run3:
            self.assertTrue(audit.verify_lean4_file(lean_path, lean_bin="custom_lean")["valid"])
            self.assertEqual(m_run3.call_args[0][0][0], "custom_lean")
        with mock.patch("subprocess.run", side_effect=OSError(errno.ENOENT, "missing")):
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_lean4_file(lean_path, lean_bin="custom_lean")
            self.assertEqual(cm.exception.code, "LEAN4_EXEC_FAILED")

        for fake_rc, fake_out, fake_err, exp_code in (
            (1, "", "", "LEAN4_COMPILE_FAILED"),
            (0, "", "err\n", "LEAN4_STDERR_NONEMPTY"),
            (0, "warning: unused variable\n", "", "LEAN4_WARNING_FORBIDDEN"),
            (0, "'T.a' depends on axioms: [Classical.choice]\n", "", "LEAN4_FORBIDDEN_AXIOM"),
            (0, "spoofed stdout line\n", "", "LEAN4_UNEXPECTED_STDOUT"),
            (0, "'T.a' does not depend on any axioms\n\n", "", "LEAN4_THEOREM_COUNT"),
        ):
            cp = subprocess.CompletedProcess(["lean"], fake_rc, stdout=fake_out, stderr=fake_err)
            with mock.patch("subprocess.run", return_value=cp):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.verify_lean4_file(lean_path)
                self.assertEqual(cm.exception.code, exp_code)

    def test_disk_cert_strict_parser_bijection_and_flags(self) -> None:
        cert_path = STUDY_DIR / "s71_proximity_certificate.json"
        st = os.lstat(cert_path)
        self.assertIn(stat.S_IMODE(st.st_mode), (0o600, 0o644))
        raw_disk = cert_path.read_bytes()
        expected = oracle.build_certificate()
        self.assertEqual(raw_disk, oracle.canonical_json_bytes(expected))

        res_f = audit.verify_certificate_file(cert_path, full_replay=True)
        res_n = audit.verify_certificate_file(cert_path, full_replay=False)
        self.assertTrue(res_f["valid"])
        self.assertFalse(res_n["full_replay"])

        for bad_flag in (1, 0, "yes", None):
            with self.assertRaises(audit.AuditError) as cm1:
                audit.verify_certificate_file(STUDY_DIR / "missing_flag_test.json", full_replay=bad_flag)  # type: ignore[arg-type]
            self.assertEqual(cm1.exception.code, "INVALID_FLAG_TYPE")
            with self.assertRaises(audit.AuditError) as cm2:
                audit.verify_certificate_payload(expected, full_replay=bad_flag)  # type: ignore[arg-type]
            self.assertEqual(cm2.exception.code, "INVALID_FLAG_TYPE")

        for bad_raw, code in (
            (raw_disk[:-1], "NON_CANONICAL_FORMAT"),
            (raw_disk.replace(b"\n", b"\r\n"), "NON_CANONICAL_FORMAT"),
            (b"\xff\xfe\n", "INVALID_UTF8"),
            (b'{"x":1.5}\n', "FLOAT_FORBIDDEN"),
            (b'{"x":NaN}\n', "CONSTANT_FORBIDDEN"),
            (b'{"a":1,"a":2}\n', "DUPLICATE_KEY"),
            (('{"a":' + "9" * (audit.MAX_INT_DIGITS + 1) + "}\n").encode("ascii"), "INT_TOO_LARGE"),
            (('{"a":-' + "9" * (audit.MAX_INT_DIGITS + 1) + "}\n").encode("ascii"), "INT_TOO_LARGE"),
            (b"{bad\n", "JSON_PARSE_ERROR"),
            (b"[1,2]\n", "INVALID_ROOT"),
            (b'{ "a": 1 }\n', "NON_CANONICAL_BYTES"),
        ):
            with self.assertRaises(audit.AuditError) as cm:
                audit.parse_strict_certificate_bytes(bad_raw)
            self.assertEqual(cm.exception.code, code, f"bad_raw={bad_raw[:40]!r}")

        # Exact boundary checks on MAX_INT_DIGITS (incl. direct >MAX_INT_DIGITS kill M005 + 5,001-digit pre-int!), MAX_JSON_DEPTH, MAX_INT_BITS
        self.assertEqual(audit._parse_strict_int("9" * audit.MAX_INT_DIGITS), int("9" * audit.MAX_INT_DIGITS))
        with self.assertRaises(audit.AuditError) as cm:
            audit._parse_strict_int("9" * (audit.MAX_INT_DIGITS + 1))
        self.assertEqual(cm.exception.code, "INT_TOO_LARGE")
        with self.assertRaises(audit.AuditError) as cm:
            audit.parse_strict_certificate_bytes(('{"a":' + "9" * 5001 + "}\n").encode("ascii"))
        self.assertEqual(cm.exception.code, "INT_TOO_LARGE")
        self.assertEqual(audit._parse_receipt_decimal("1." + "0" * (audit.MAX_INT_DIGITS - 2)), Decimal("1"))
        with self.assertRaises(audit.AuditError) as cm:
            audit._parse_receipt_decimal("1." + "0" * audit.MAX_INT_DIGITS)
        self.assertEqual(cm.exception.code, "INT_TOO_LARGE")

        exact_depth: Any = 1
        for _ in range(audit.MAX_JSON_DEPTH):
            exact_depth = {"k": exact_depth}
        audit._validate_json_tree_iter(exact_depth)
        audit._validate_json_tree_iter({"a": (1 << audit.MAX_INT_BITS) - 1})

        deep: Any = 1
        for _ in range(audit.MAX_JSON_DEPTH + 1):
            deep = {"k": deep}
        with self.assertRaises(audit.AuditError) as cm:
            audit._validate_json_tree_iter(deep)
        self.assertEqual(cm.exception.code, "DEPTH_EXCEEDED")

        for bad_obj, code in (
            ({1: "v"}, "INVALID_KEY_TYPE"),
            ({_StrSub("a"): "v"}, "INVALID_KEY_TYPE"),
            ({"\ud800": "v"}, "INVALID_UTF8_SURROGATE"),
            ({"a": "\ud800"}, "INVALID_UTF8_SURROGATE"),
            ({"a": 1 << (audit.MAX_INT_BITS + 1)}, "INT_TOO_LARGE"),
            ({"a": None}, "INVALID_VALUE_TYPE"),
            ({"a": _IntSub(1)}, "INVALID_VALUE_TYPE"),
            ({"a": _StrSub("x")}, "INVALID_VALUE_TYPE"),
            ({"a": _DictSub()}, "INVALID_VALUE_TYPE"),
            ({"a": _ListSub()}, "INVALID_VALUE_TYPE"),
        ):
            with self.assertRaises(audit.AuditError) as cm:
                audit._validate_json_tree_iter(bad_obj)
            self.assertEqual(cm.exception.code, code)

        # Secondary audit & bijective tree checks
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload([])
        self.assertEqual(cm.exception.code, "INVALID_ROOT")
        for bad_sha in ("deadbeef", "G" * 64, 123, "A" * 64):
            c_bad = dict(expected)
            c_bad["certificate_sha256"] = bad_sha
            with self.assertRaises(audit.AuditError) as cm:
                audit.secondary_audit_payload(c_bad)
            self.assertEqual(cm.exception.code, "INVALID_DIGEST")
        c_nosha = {k: v for k, v in expected.items() if k != "certificate_sha256"}
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload(c_nosha)
        self.assertEqual(cm.exception.code, "INVALID_DIGEST")

        c_wrong = dict(expected)
        c_wrong["certificate_sha256"] = ("0" if expected["certificate_sha256"][0] != "0" else "1") + expected["certificate_sha256"][1:]
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload(c_wrong)
        self.assertEqual(cm.exception.code, "DIGEST_MISMATCH")

        c_empty = copy.deepcopy(expected)
        c_empty["pillar_2_sampled_live_i9_rapl_and_avx512"]["exact_ratios"]["ww2_8b_to_64b_lat_ratio_q"] = []
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload(_resign(c_empty))
        self.assertEqual(cm.exception.code, "SCHEMA_LEN_MISMATCH")

        c_type = copy.deepcopy(expected)
        c_type["pillar_1_exact_proximity_and_h4_algebra"]["cache_line_bytes"] = True
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload(_resign(c_type))
        self.assertEqual(cm.exception.code, "SCHEMA_TYPE_MISMATCH")

        c_key = copy.deepcopy(expected)
        c_key["pillar_1_exact_proximity_and_h4_algebra"]["extra_k"] = 1
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload(_resign(c_key))
        self.assertEqual(cm.exception.code, "SCHEMA_KEY_MISMATCH")

        c_leaf = copy.deepcopy(expected)
        c_leaf["pillar_1_exact_proximity_and_h4_algebra"]["cache_line_bytes"] = 32
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload(_resign(c_leaf))
        self.assertEqual(cm.exception.code, "INVARIANT_MISMATCH")

        with mock.patch.object(oracle, "build_certificate", side_effect=[expected, {"different": True}]):
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_certificate_payload(expected, full_replay=True)
            self.assertEqual(cm.exception.code, "REPLAY_MISMATCH")

    def test_zone_b_io_pwd_darwin_atomic_write_receipts_and_cli(self) -> None:
        cert = oracle.build_certificate()
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)

            # Direct API surrogate / NUL / non-Path / empty / basename checks
            for bad_p in (Path("/tmp/\ud800.json"), Path("/tmp/a\x00b.json"), "not_a_path"):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.verify_certificate_file(bad_p)  # type: ignore[arg-type]
                self.assertEqual(cm.exception.code, "INVALID_PATH")
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_certificate_atomic(bad_p, cert)  # type: ignore[arg-type]
                self.assertEqual(cm.exception.code, "INVALID_PATH")
                with self.assertRaises(audit.AuditError) as cm:
                    audit.verify_receipts_directory(bad_p)  # type: ignore[arg-type]
                self.assertEqual(cm.exception.code, "INVALID_PATH")
                with self.assertRaises(audit.AuditError) as cm:
                    audit.verify_lean4_file(bad_p)  # type: ignore[arg-type]
                self.assertEqual(cm.exception.code, "INVALID_PATH")

            with self.assertRaises(audit.AuditError) as cm:
                audit._open_parent_dir_nofollow(Path(""))
            self.assertEqual(cm.exception.code, "EMPTY_PATH")
            for bad_bn in (Path("/"), Path(".."), Path("a/..")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit._open_parent_dir_nofollow(bad_bn)
                self.assertEqual(cm.exception.code, "INVALID_BASENAME")

            # Atomic write & overwrite + mode 0o600
            out_p = td_p / "cert.json"
            sha1 = audit.write_certificate_atomic(out_p, cert)
            self.assertEqual(stat.S_IMODE(os.lstat(out_p).st_mode), 0o600)
            self.assertEqual(sha1, audit.write_certificate_atomic(out_p, cert))
            with self.assertRaises(audit.AuditError) as cm:
                audit.write_certificate_atomic(out_p, [])  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, "INVALID_ROOT")

            # Symlink target & ancestor, ELOOP & ENOTDIR branches, hardlink, FIFO O_NONBLOCK, size cap, EIO
            sym_t = td_p / "sym.json"
            os.symlink(out_p, sym_t)
            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_file_bytes(sym_t)
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(audit.AuditError) as cm:
                audit.write_certificate_atomic(sym_t, cert)
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")

            sub_d = td_p / "real_dir"
            sub_d.mkdir()
            sym_d = td_p / "sym_dir"
            os.symlink(sub_d, sym_d)
            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_file_bytes(sym_d / "x.json")
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")

            real_open = os.open
            for err_code in (errno.ELOOP, errno.ENOTDIR):
                def _open_err(path: Any, flags: int, *a: Any, _ec: int = err_code, **kw: Any) -> int:
                    if path == "sym_dir":
                        raise OSError(_ec, "err")
                    return real_open(path, flags, *a, **kw)
                with mock.patch("os.open", side_effect=_open_err):
                    with self.assertRaises(audit.AuditError) as cm:
                        audit.read_regular_file_bytes(sym_d / "x.json")
                    self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")

            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_file_bytes(out_p / "child.json")
            self.assertEqual(cm.exception.code, "DIR_OPEN_FAILED")

            with mock.patch("os.open", side_effect=OSError(errno.EACCES, "denied")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_file_bytes(out_p)
                self.assertEqual(cm.exception.code, "DIR_OPEN_FAILED")

            hl = td_p / "hl.json"
            os.link(out_p, hl)
            for fn_call in (
                lambda: audit.read_regular_file_bytes(hl),
                lambda: audit.write_certificate_atomic(hl, cert),
            ):
                with self.assertRaises(audit.AuditError) as cm:
                    fn_call()
                self.assertEqual(cm.exception.code, "HARDLINK_FORBIDDEN")
            os.unlink(hl)

            # Scratch FIFO non-regular file rejection
            fifo_p = td_p / "pipe.fifo"
            os.mkfifo(fifo_p)
            for fn_call in (
                lambda: audit.read_regular_file_bytes(fifo_p),
                lambda: audit.write_certificate_atomic(fifo_p, cert),
            ):
                with self.assertRaises(audit.AuditError) as cm:
                    fn_call()
                self.assertEqual(cm.exception.code, "NON_REGULAR_FILE")

            # Exact size boundary + st_size fast-reject + stream cap + EIO
            exact_sz = out_p.stat().st_size
            self.assertEqual(len(audit.read_regular_file_bytes(out_p, max_bytes=exact_sz)), exact_sz)
            with mock.patch("os.read", side_effect=RuntimeError("must reject before os.read")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_file_bytes(out_p, max_bytes=16)
                self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")
            real_fstat = os.fstat
            def _fake_small_stat(fd: int) -> Any:
                st = real_fstat(fd)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid, st.st_gid, 4, st.st_atime, st.st_mtime, st.st_ctime))
            with mock.patch("os.fstat", side_effect=_fake_small_stat):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_file_bytes(out_p, max_bytes=16)
                self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")

            with mock.patch("os.fstat", side_effect=OSError(errno.EIO, "io")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_file_bytes(out_p)
                self.assertEqual(cm.exception.code, "FILE_READ_FAILED")
            with mock.patch("os.read", side_effect=OSError(errno.EIO, "io")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_file_bytes(out_p)
                self.assertEqual(cm.exception.code, "FILE_READ_FAILED")

            # Atomic write fault injection: EEXIST exhaustion, short write, non-reg st_mode & nlink=2, ENOSPC (0 leaked tmps)
            def _open_eexist(path: Any, flags: int, *a: Any, **kw: Any) -> int:
                if flags & os.O_CREAT:
                    raise FileExistsError()
                return real_open(path, flags, *a, **kw)
            with mock.patch("os.open", side_effect=_open_eexist), mock.patch("os.fchmod", side_effect=RuntimeError("no fchmod")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_certificate_atomic(td_p / "w1.json", cert)
                self.assertEqual(cm.exception.code, "ATOMIC_WRITE_FAILED")
                self.assertIn("exhausted", cm.exception.message)

            def _open_eacces(path: Any, flags: int, *a: Any, **kw: Any) -> int:
                if flags & os.O_CREAT:
                    raise OSError(errno.EACCES, "ro")
                return real_open(path, flags, *a, **kw)
            with mock.patch("os.open", side_effect=_open_eacces):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_certificate_atomic(td_p / "w1b.json", cert)
                self.assertEqual(cm.exception.code, "ATOMIC_WRITE_FAILED")
                self.assertIn("cannot create temp file", cm.exception.message)

            with mock.patch("os.write", side_effect=[0, RuntimeError("short write loop")]):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_certificate_atomic(td_p / "w2.json", cert)
                self.assertEqual(cm.exception.code, "SHORT_WRITE")

            def _fake_nlink2(fd: int) -> Any:
                st = real_fstat(fd)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, 2, st.st_uid, st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime))
            with mock.patch("os.fstat", side_effect=_fake_nlink2):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_certificate_atomic(td_p / "w3.json", cert)
                self.assertEqual(cm.exception.code, "TEMP_TAMPERED")

            def _fake_fifo_tmp(fd: int) -> Any:
                st = real_fstat(fd)
                return os.stat_result((stat.S_IFIFO | 0o600, st.st_ino, st.st_dev, 1, st.st_uid, st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime))
            with mock.patch("os.fstat", side_effect=_fake_fifo_tmp):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_certificate_atomic(td_p / "w3b.json", cert)
                self.assertEqual(cm.exception.code, "TEMP_TAMPERED")

            for fn_name in ("os.fchmod", "os.write", "os.fsync", "os.replace"):
                with mock.patch(fn_name, side_effect=OSError(errno.ENOSPC, "full")):
                    with self.assertRaises(audit.AuditError) as cm:
                        audit.write_certificate_atomic(td_p / "w4.json", cert)
                    self.assertEqual(cm.exception.code, "ATOMIC_WRITE_FAILED")
            self.assertEqual([p.name for p in td_p.glob(".*.tmp.*")], [])

            # Relative path + logical $PWD symlink ancestor check + NUL/relative/mismatched dev/ino $PWD
            orig_cwd = os.getcwd()
            try:
                os.chdir(sub_d)
                (sub_d / "local.json").write_bytes(oracle.canonical_json_bytes(cert))
                with mock.patch.dict(os.environ, {"PWD": str(sym_d)}):
                    with self.assertRaises(audit.AuditError) as cm:
                        audit.read_regular_file_bytes(Path("local.json"))
                    self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")
                with mock.patch.dict(os.environ, {"PWD": str(sub_d)}):
                    self.assertEqual(audit.read_regular_file_bytes(Path("./local.json")), oracle.canonical_json_bytes(cert))
                with mock.patch.dict(os.environ, {"PWD": str(td_p)}):
                    self.assertEqual(audit.read_regular_file_bytes(Path("local.json")), oracle.canonical_json_bytes(cert))
                with mock.patch.dict(os.environ, {"PWD": "rel/nonexistent_pwd_xyz"}):
                    self.assertEqual(audit.read_regular_file_bytes(Path("local.json")), oracle.canonical_json_bytes(cert))
                with mock.patch.dict(os.environ, {"PWD": "/nonexistent_pwd_99999"}):
                    self.assertEqual(audit.read_regular_file_bytes(Path("local.json")), oracle.canonical_json_bytes(cert))
                # Relative PWD matching st_ino/st_dev via mock must still be ignored by startswith("/")!
                real_stat = os.stat
                def _rel_match_stat(p: Any, *a: Any, **kw: Any) -> Any:
                    if p == "rel/sym_dir":
                        return real_stat(".")
                    return real_stat(p, *a, **kw)
                with mock.patch.dict(os.environ, {"PWD": "rel/sym_dir"}), mock.patch("os.stat", side_effect=_rel_match_stat):
                    self.assertEqual(audit.read_regular_file_bytes(Path("local.json")), oracle.canonical_json_bytes(cert))
                # Distinct st_dev with identical st_ino AND distinct st_ino with identical st_dev
                def _diff_dev_stat(p: Any, *a: Any, **kw: Any) -> Any:
                    st = real_stat(p, *a, **kw)
                    if p == str(sym_d):
                        return os.stat_result((st.st_mode, st.st_ino, st.st_dev + 99, st.st_nlink, st.st_uid, st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime))
                    return st
                with mock.patch.dict(os.environ, {"PWD": str(sym_d)}), mock.patch("os.stat", side_effect=_diff_dev_stat):
                    self.assertEqual(audit.read_regular_file_bytes(Path("local.json")), oracle.canonical_json_bytes(cert))
                def _diff_ino_stat(p: Any, *a: Any, **kw: Any) -> Any:
                    st = real_stat(p, *a, **kw)
                    if p == str(sym_d):
                        return os.stat_result((st.st_mode, st.st_ino + 99, st.st_dev, st.st_nlink, st.st_uid, st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime))
                    return st
                with mock.patch.dict(os.environ, {"PWD": str(sym_d)}), mock.patch("os.stat", side_effect=_diff_ino_stat):
                    self.assertEqual(audit.read_regular_file_bytes(Path("local.json")), oracle.canonical_json_bytes(cert))
                # NUL in $PWD must be ignored cleanly without raising ValueError
                with mock.patch.object(os.environ, "get", side_effect=lambda k, d="": "/a\x00b" if k == "PWD" else d):
                    self.assertEqual(audit.read_regular_file_bytes(Path("local.json")), oracle.canonical_json_bytes(cert))
            finally:
                os.chdir(orig_cwd)

            # Darwin prefix normalization (with BOTH os.lstat & os.readlink mocked to kill ALL BoolOp mutants!)
            with mock.patch.object(sys, "platform", "darwin"):
                root_lnk = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 0, 0, 11, 0, 0, 0))
                nonroot_lnk = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 1000, 1000, 11, 0, 0, 0))
                root_dir = os.stat_result((stat.S_IFDIR | 0o755, 1, 1, 2, 0, 0, 0, 0, 0, 0))
                with mock.patch("os.lstat", return_value=root_lnk), mock.patch("os.readlink", return_value="private/var"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("/",)), ("/",))
                    self.assertEqual(audit._normalize_darwin_system_prefix(("rel", "var")), ("rel", "var"))
                    self.assertEqual(audit._normalize_darwin_system_prefix(("/", "var", "..", "x")), ("/", "var", "..", "x"))
                    self.assertEqual(audit._normalize_darwin_system_prefix(("/", "usr", "local")), ("/", "usr", "local"))
                    self.assertEqual(audit._normalize_darwin_system_prefix(("/", "var", "folders")), ("/", "private", "var", "folders"))
                with mock.patch("os.lstat", return_value=nonroot_lnk), mock.patch("os.readlink", return_value="private/var"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("/", "var", "x")), ("/", "var", "x"))
                with mock.patch("os.lstat", return_value=root_dir), mock.patch("os.readlink", return_value="private/var"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("/", "var", "x")), ("/", "var", "x"))
                with mock.patch("os.lstat", return_value=root_lnk), mock.patch("os.readlink", return_value="/evil"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("/", "var", "x")), ("/", "var", "x"))
                with mock.patch("os.lstat", side_effect=OSError(errno.ENOENT, "missing")):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("/", "var", "x")), ("/", "var", "x"))

            # Receipt directory error branches (float, bad JSON, non-dict roots, ZeroDivisionError, failed check)
            rdir = td_p / "rec_test"
            rdir.mkdir()
            rec_files = (
                "s71_preregistration.json",
                "s71_proximity_bench.c",
                "ProximityBarrierSilicon.lean",
                "s71_empirical_results.json",
                "mlos_zone_b_receipt.json",
            )
            for fn in rec_files:
                (rdir / fn).write_bytes((STUDY_DIR / fn).read_bytes())

            (rdir / "s71_preregistration.json").write_bytes(b'{"a":1.5}\n')
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_receipts_directory(rdir)
            self.assertEqual(cm.exception.code, "FLOAT_FORBIDDEN")

            (rdir / "s71_preregistration.json").write_bytes(b"{bad")
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_receipts_directory(rdir)
            self.assertEqual(cm.exception.code, "RECEIPT_PARSE_ERROR")

            for fn in ("s71_preregistration.json", "s71_empirical_results.json", "mlos_zone_b_receipt.json"):
                (rdir / fn).write_bytes(b"[]\n")
                with self.assertRaises(audit.AuditError) as cm:
                    audit.verify_receipts_directory(rdir)
                self.assertEqual(cm.exception.code, "RECEIPT_ROOT_INVALID")
                (rdir / fn).write_bytes((STUDY_DIR / fn).read_bytes())

            # Zero total_ops short-circuits cleanly (no ZeroDivisionError!) -> RECEIPT_VERIFICATION_FAILED
            emp_z = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            emp_z["measurements"]["write_write_2core"][0]["total_ops"] = 0
            (rdir / "s71_empirical_results.json").write_text(json.dumps(emp_z), encoding="utf-8")
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_receipts_directory(rdir)
            self.assertEqual(cm.exception.code, "RECEIPT_VERIFICATION_FAILED")

            # Missing required measurement section -> KeyError -> RECEIPT_SCHEMA_ERROR
            emp_m = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            del emp_m["measurements"]["write_write_2core"]
            (rdir / "s71_empirical_results.json").write_text(json.dumps(emp_m), encoding="utf-8")
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_receipts_directory(rdir)
            self.assertEqual(cm.exception.code, "RECEIPT_SCHEMA_ERROR")

            emp_bad = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            emp_bad["ac_online"] = False
            (rdir / "s71_empirical_results.json").write_text(json.dumps(emp_bad), encoding="utf-8")
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_receipts_directory(rdir)
            self.assertEqual(cm.exception.code, "RECEIPT_VERIFICATION_FAILED")

            # CLI tests (all modes + 3-arg extra + 2-arg unknown flag + hostile argv)
            def _run_cli(args: Any) -> tuple[int, bytes, bytes]:
                ob, eb = io.BytesIO(), io.BytesIO()
                with mock.patch.object(sys, "stdout", mock.Mock(buffer=ob)), mock.patch.object(sys, "stderr", mock.Mock(buffer=eb)):
                    rc = audit.main(args)
                return rc, ob.getvalue(), eb.getvalue()

            rc, ob, _ = _run_cli([])
            self.assertEqual(rc, 0)
            self.assertEqual(ob, oracle.canonical_json_bytes(cert))
            rc, ob, _ = _run_cli(["--standalone", "--json"])
            self.assertEqual(rc, 0)
            self.assertEqual(ob, oracle.canonical_json_bytes(cert))
            cli_out = td_p / "cli_cert.json"
            rc, ob, _ = _run_cli(["--write", str(cli_out)])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(ob.decode("utf-8"))["written"])
            # --check now also requires the sibling empirical JSON for the frozen-token bijection
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            rc, ob, _ = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(ob.decode("utf-8"))["valid"])
            self.assertTrue(json.loads(ob.decode("utf-8"))["frozen_tokens_bijection"]["frozen_tokens_bijection_ok"])
            self.assertEqual(json.loads(ob.decode("utf-8"))["frozen_tokens_bijection"]["entries_checked"], 14)
            # Drift between frozen tokens and the empirical JSON must fail --check closed
            emp_drift = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            emp_drift["measurements"]["write_write_2core"][0]["ns"] += 1
            (td_p / "s71_empirical_results.json").write_text(json.dumps(emp_drift), encoding="utf-8")
            rc_d, _ob_d, eb_d = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_d, 2)
            self.assertIn("BIJECTION_MISMATCH", eb_d.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # Label-row drift (gemv_dual_opt label) must fail --check closed
            emp_lab = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            for _row in emp_lab["measurements"]["avx512_a16_blockh4_dual_force"]:
                if _row.get("label") == "dual_force_aligned_reg_read_shared":
                    _row["tsc"] += 1
            (td_p / "s71_empirical_results.json").write_text(json.dumps(emp_lab), encoding="utf-8")
            rc_l, _ob_l, eb_l = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_l, 2)
            self.assertIn("BIJECTION_MISMATCH", eb_l.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # Second label row (gemv_disp_4096b) drift must fail too
            emp_lab2 = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            for _row in emp_lab2["measurements"]["avx512_a16_blockh4_dual_force"]:
                if _row.get("label") == "aligned_reg_dispersed_read_4096B":
                    _row["pkg_uj"] += 1
            (td_p / "s71_empirical_results.json").write_text(json.dumps(emp_lab2), encoding="utf-8")
            rc_l2, _ob_l2, eb_l2 = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_l2, 2)
            self.assertIn("BIJECTION_MISMATCH", eb_l2.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # Scalar drift (a16_syndrome_errors) must fail closed
            emp_sc = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            emp_sc["measurements"]["a16_syndrome_errors"] = 1
            (td_p / "s71_empirical_results.json").write_text(json.dumps(emp_sc), encoding="utf-8")
            rc_s, _ob_s, eb_s = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_s, 2)
            self.assertIn("BIJECTION_MISMATCH", eb_s.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # Duplicated stride row must fail (bijection must be unique)
            emp_dup = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            _grp = emp_dup["measurements"]["write_write_2core"]
            emp_dup["measurements"]["write_write_2core"] = _grp + [dict(_grp[0])]
            (td_p / "s71_empirical_results.json").write_text(json.dumps(emp_dup), encoding="utf-8")
            rc_p, _ob_p, eb_p = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_p, 2)
            self.assertIn("BIJECTION_MISMATCH", eb_p.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # Malformed JSON must fail closed with BIJECTION_PARSE_ERROR
            (td_p / "s71_empirical_results.json").write_text("{not json", encoding="utf-8")
            rc_m, _ob_m, eb_m = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_m, 2)
            self.assertIn("BIJECTION_PARSE_ERROR", eb_m.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # Duplicate label row must fail (label bijection must be unique too)
            emp_dl = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            _df = emp_dl["measurements"]["avx512_a16_blockh4_dual_force"]
            _lab_row = next(r for r in _df if r.get("label") == "dual_force_aligned_reg_read_shared")
            emp_dl["measurements"]["avx512_a16_blockh4_dual_force"] = _df + [dict(_lab_row)]
            (td_p / "s71_empirical_results.json").write_text(json.dumps(emp_dl), encoding="utf-8")
            rc_dl, _ob_dl, eb_dl = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_dl, 2)
            self.assertIn("BIJECTION_MISMATCH", eb_dl.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # measurements not an object must fail schema-closed
            emp_m = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            emp_m["measurements"] = []
            (td_p / "s71_empirical_results.json").write_text(json.dumps(emp_m), encoding="utf-8")
            rc_m2, _ob_m2, eb_m2 = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_m2, 2)
            self.assertIn("BIJECTION_SCHEMA_ERROR", eb_m2.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # a row group that is not a list must fail schema-closed
            emp_g = json.loads((STUDY_DIR / "s71_empirical_results.json").read_text(encoding="utf-8"))
            emp_g["measurements"]["write_write_2core"] = {}
            (td_p / "s71_empirical_results.json").write_text(json.dumps(emp_g), encoding="utf-8")
            rc_g, _ob_g, eb_g = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_g, 2)
            self.assertIn("BIJECTION_SCHEMA_ERROR", eb_g.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            # a NaN literal must fail closed (parse_constant rejects; not BIJECTION_PARSE_ERROR but still rc=2)
            (td_p / "s71_empirical_results.json").write_text('{"measurements": {"a16_syndrome_errors": NaN}}', encoding="utf-8")
            rc_n, _ob_n, eb_n = _run_cli(["--check", str(cli_out)])
            self.assertEqual(rc_n, 2)
            self.assertNotIn("Traceback", eb_n.decode("utf-8"))
            shutil.copyfile(STUDY_DIR / "s71_empirical_results.json", td_p / "s71_empirical_results.json")
            rc, ob, _ = _run_cli(["--verify-receipts", str(STUDY_DIR)])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(ob.decode("utf-8"))["all_verified"])
            fake_lean_ok = subprocess.CompletedProcess(
                ["lean"], 0, stdout="\n".join(f"'T.t{k}' does not depend on any axioms" for k in range(20)) + "\n", stderr=""
            )
            with mock.patch("subprocess.run", return_value=fake_lean_ok):
                rc, ob, _ = _run_cli(["--audit-lean", str(STUDY_DIR / "ProximityBarrierSilicon.lean")])
                self.assertEqual(rc, 0)
                self.assertTrue(json.loads(ob.decode("utf-8"))["valid"])

            with mock.patch.object(sys, "argv", ["audit.py", "--standalone", "--json"]):
                rc, ob, _ = _run_cli(None)
                self.assertEqual(rc, 0)

            for bad_argv, exp_code in (
                (123, "USAGE_ERROR"),
                (["--check", 123], "USAGE_ERROR"),
                (["--check", _StrSub(str(cli_out))], "USAGE_ERROR"),
                (["--bogus"], "USAGE_ERROR"),
                (["--bogus", str(STUDY_DIR / "ProximityBarrierSilicon.lean")], "USAGE_ERROR"),
                (["--check", str(cli_out), "extra"], "USAGE_ERROR"),
                (["--write", str(cli_out), "extra"], "USAGE_ERROR"),
                (["--verify-receipts", str(STUDY_DIR), "extra"], "USAGE_ERROR"),
                (["--audit-lean", str(STUDY_DIR / "ProximityBarrierSilicon.lean"), "extra"], "USAGE_ERROR"),
                (["--check", ""], "INVALID_CLI_PATH"),
                (["--check", "-flag"], "INVALID_CLI_PATH"),
                (["--check", "a\x00b"], "INVALID_PATH"),
                (["--check", "/tmp/\ud800.json"], "INVALID_PATH"),
            ):
                rc, _, eb = _run_cli(bad_argv)
                self.assertEqual(rc, 2, f"bad_argv={bad_argv!r}")
                parsed_err = json.loads(eb.decode("utf-8"))
                self.assertFalse(parsed_err["valid"])
                self.assertEqual(parsed_err["error_code"], exp_code, f"bad_argv={bad_argv!r}")


if __name__ == "__main__":
    unittest.main()
