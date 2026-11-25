#!/usr/bin/env python3
"""Track S104 R5 test suite: assertion-free (unittest methods only), zero floats, zero skips.

Covers oracle primitive guards, exact Kronecker/obstruction/EXP-Delta/triple-gate/wire replays,
hardened Zone-B I/O, the strict JSON parser, the 18-rule R11+ Lean scanner with clean controls,
mocked and live Lean 4.36.0 gates, the re-signed SEC/FR0/FR1 forgery battery over every payload
leaf, and the CLI surface.
"""
from __future__ import annotations

import ast
import copy
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s104_kronecker_triple_gate_oracle as oracle  # noqa: E402
import verify_s104_kronecker_triple_gate as verifier  # noqa: E402

E = oracle.S104Error
CERT = oracle.build_certificate()
PAYLOAD = CERT["payload"]
LEAN_PATH = _THIS_DIR / oracle.LEAN_SOURCE_NAME
LEAN_SRC = LEAN_PATH.read_text(encoding="utf-8")
SOURCES = ("s104_kronecker_triple_gate_oracle.py", "verify_s104_kronecker_triple_gate.py", "test_s104_kronecker_triple_gate_r5.py")
FAKE_LIVE = {"lean_version": "Lean (version 4.36.0, mock)", "theorems_verified": 25,
             "lean_source_sha256": oracle.PINNED_LEAN_SOURCE_SHA256}


def code_of(fn, *args, **kwargs) -> str:
    try:
        fn(*args, **kwargs)
    except E as exc:
        return exc.code
    return "NO_ERROR"


def resign(payload: dict) -> dict:
    p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    core = {"schema_version": oracle.SCHEMA_VERSION, "track_id": oracle.TRACK_ID, "payload_sha256": p_sha, "payload": payload}
    return {**core, "certificate_sha256": oracle.sha256_hex(oracle.canonical_json_bytes(core))}


def set_path(obj, path, value):
    cur = obj
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value


def leaf_paths(obj, prefix=()):
    if type(obj) is dict:
        for k, v in obj.items():
            yield from leaf_paths(v, prefix + (k,))
    elif type(obj) is list:
        for i, v in enumerate(obj):
            yield from leaf_paths(v, prefix + (i,))
    else:
        yield prefix, obj


def tamper_value(v):
    if type(v) is bool:
        return not v
    if type(v) is int:
        return v + 1
    if type(v) is str:
        return v + "x"
    return "x"


def axiom_stdout(names, dep_for=()) -> str:
    lines = []
    for n in names:
        if n in dep_for:
            lines.append(f"'{n}' depends on axioms: [propext, Quot.sound]")
        else:
            lines.append(f"'{n}' does not depend on any axioms")
    return "\n".join(lines) + "\n"


def completed(rc=0, out="", err=""):
    return subprocess.CompletedProcess(args=["lean"], returncode=rc, stdout=out, stderr=err)


GOOD_VERSION = "Lean (version 4.36.0, x86_64-unknown-linux-gnu, Release)\n"


class Test01Hygiene(unittest.TestCase):
    def test_python_sources_zero_floats_asserts_and_literals(self):
        banned_sub = ("/dev/" + "null", "4-" + "mode", "/" + "home/", "\r")
        for name in SOURCES:
            text = (_THIS_DIR / name).read_text(encoding="utf-8")
            for b in banned_sub:
                self.assertNotIn(b, text, f"{name} contains banned literal")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.Assert, f"{name}: bare assert")
                if isinstance(node, ast.Constant):
                    self.assertNotIsInstance(node.value, float, f"{name}: float literal")
                    self.assertNotIsInstance(node.value, complex, f"{name}: complex literal")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "float", f"{name}: float() call")
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mods = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
                    self.assertNotIn("random", mods)

    def test_lean_source_clean_and_counts(self):
        verifier.static_gate_lean4_source(LEAN_SRC)
        self.assertEqual(verifier.lean4_rule_hits(LEAN_SRC), [])
        self.assertEqual(len(oracle.LEAN_THEOREM_NAMES), 25)
        self.assertEqual(len(set(oracle.LEAN_THEOREM_NAMES)), 25)
        self.assertEqual(len(verifier.LEAN4_RULES), 18)
        self.assertEqual(len({rid for rid, _ in verifier.LEAN4_RULES}), 18)


class Test02OraclePrimitives(unittest.TestCase):
    def test_require_family(self):
        self.assertEqual(code_of(oracle.require_bool, 1, "x"), "INVALID_BOOL")
        self.assertIs(oracle.require_bool(False, "x"), False)
        self.assertEqual(code_of(oracle.require_exact_int, True, "x"), "INVALID_INT")
        self.assertEqual(oracle.require_exact_int(5, "x", lo=5, hi=5), 5)
        self.assertEqual(code_of(oracle.require_exact_int, 4, "x", lo=5), "INT_OUT_OF_RANGE")
        self.assertEqual(code_of(oracle.require_exact_int, 6, "x", hi=5), "INT_OUT_OF_RANGE")
        self.assertEqual(code_of(oracle.require_exact_str, 1, "x"), "INVALID_STR")
        self.assertEqual(code_of(oracle.require_hex64, "a" * 63, "x"), "INVALID_HEX64")
        self.assertEqual(code_of(oracle.require_hex64, "A" * 64, "x"), "INVALID_HEX64")
        self.assertEqual(oracle.require_hex64("a" * 64, "x"), "a" * 64)
        self.assertEqual(code_of(oracle.require_ok, 1, "C", "d"), "C")

    def test_strict_json_tree(self):
        deep = []
        cur = deep
        for _ in range(31):
            nxt = []
            cur.append(nxt)
            cur = nxt
        oracle.validate_strict_json_tree([deep])
        self.assertEqual(code_of(oracle.validate_strict_json_tree, [[deep]]), "JSON_DEPTH_EXCEEDED")
        oracle.validate_strict_json_tree((1 << 2048) - 1)
        self.assertEqual(code_of(oracle.validate_strict_json_tree, 1 << 2048), "INT_BIT_LIMIT")
        self.assertEqual(code_of(oracle.validate_strict_json_tree, {1: 2}), "INVALID_JSON_KEY")
        self.assertEqual(code_of(oracle.validate_strict_json_tree, {"a": Fraction(1, 2)}), "FORBIDDEN_JSON_TYPE")
        self.assertEqual(code_of(oracle.validate_strict_json_tree, (1,)), "FORBIDDEN_JSON_TYPE")
        oracle.validate_strict_json_tree({"a": None, "b": True, "c": "s", "d": [1]})
        self.assertEqual(oracle.canonical_json_bytes({"b": 1, "a": None}), b'{"a":null,"b":1}\n')

    def test_formatting_and_rounding(self):
        self.assertEqual(code_of(oracle.fmt_q, 1), "INVALID_FRACTION")
        self.assertEqual(oracle.fmt_q(Fraction(3)), "3")
        self.assertEqual(oracle.fmt_q(Fraction(-1, 2)), "-1/2")
        self.assertEqual(code_of(oracle.fmt_dec_q, 1, 2), "INVALID_FRACTION")
        self.assertEqual(code_of(oracle.fmt_dec_q, Fraction(1), 19), "INT_OUT_OF_RANGE")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-1, 3), 3), "-0.333")
        self.assertEqual(oracle.fmt_dec_q(Fraction(5, 2), 0), "3")
        self.assertEqual(oracle.fmt_dec_q(Fraction(1, 8), 2), "0.13")
        self.assertEqual(code_of(oracle.round_half_even, 1), "INVALID_FRACTION")
        cases = [(Fraction(1, 2), 0), (Fraction(3, 2), 2), (Fraction(5, 2), 2), (Fraction(-1, 2), 0),
                 (Fraction(7, 3), 2), (Fraction(8, 3), 3), (Fraction(-7, 2), -4)]
        for q, want in cases:
            self.assertEqual(oracle.round_half_even(q), want)

    def test_matrix_guards(self):
        self.assertEqual(code_of(oracle.rank_q, "x"), "INVALID_MATRIX")
        self.assertEqual(code_of(oracle.rank_q, []), "EMPTY_MATRIX")
        self.assertEqual(code_of(oracle.rank_q, [1]), "INVALID_MATRIX_ROW")
        self.assertEqual(code_of(oracle.rank_q, [[1], 2]), "INVALID_MATRIX_ROW")
        self.assertEqual(code_of(oracle.rank_q, [[]]), "EMPTY_MATRIX_ROW")
        self.assertEqual(code_of(oracle.rank_q, [[1], [1, 2]]), "RAGGED_MATRIX")
        self.assertEqual(code_of(oracle.rank_q, [["a"]]), "INVALID_MATRIX_ENTRY")
        self.assertEqual(code_of(oracle.rank_q, [[True]]), "INVALID_MATRIX_ENTRY")
        self.assertEqual(code_of(oracle.dot_q, [1], [1, 2]), "DIM_MISMATCH")
        self.assertEqual(code_of(oracle.mat_mul, [[1, 2]], [[1, 2]]), "DIM_MISMATCH")
        self.assertEqual(oracle.mat_mul([[1, 2]], [[3], [4]]), [[Fraction(11)]])
        self.assertEqual(oracle.rank_q([[1, 2], [2, 4]]), 1)
        self.assertEqual(oracle.rank_q([[0, 1], [1, 0]]), 2)
        self.assertEqual(oracle.rank_q([[0, 0], [0, 0]]), 0)
        self.assertEqual(oracle.rank_q([[1, 2, 3], [2, 4, 7], [3, 6, 10]]), 2)
        self.assertEqual(oracle.inverse_q([[2]]), [[Fraction(1, 2)]])
        self.assertEqual(oracle.inverse_q([[0, 1], [1, 0]]), [[0, 1], [1, 0]])
        self.assertEqual(oracle.inverse_q([[1, 2], [3, 4]]), [[-2, 1], [Fraction(3, 2), Fraction(-1, 2)]])
        self.assertEqual(code_of(oracle.inverse_q, [[1, 2], [2, 4]]), "SINGULAR_MATRIX")
        self.assertEqual(code_of(oracle.inverse_q, [[1, 2]]), "NOT_SQUARE")
        self.assertEqual(code_of(oracle.schur_complement_q, [[1, 2]], [0]), "NOT_SQUARE")
        self.assertEqual(code_of(oracle.schur_complement_q, [[2, 1], [1, 2]], []), "EMPTY_SCHUR_ELIM")
        self.assertEqual(code_of(oracle.schur_complement_q, [[2, 1], [1, 2]], [0, 1]), "EMPTY_SCHUR_KEEP")
        self.assertEqual(oracle.schur_complement_q([[2, 1], [1, 2]], [0]), [[Fraction(3, 2)]])
        self.assertEqual(code_of(oracle.vlp_rearrange, [[1, 2]], 1, 2), "NOT_SQUARE")
        self.assertEqual(code_of(oracle.vlp_rearrange, [[1, 0], [0, 1]], 2, 2), "VLP_SHAPE_MISMATCH")
        ga = [[2, 1], [1, 3]]
        gb = [[1, 4], [4, 5]]
        self.assertEqual(oracle.rank_q(oracle.vlp_rearrange(oracle.kron_mat(ga, gb), 2, 2)), 1)
        self.assertEqual(oracle.kron_mat([[1, 2]], [[3], [4]]), [[3, 6], [4, 8]])
        self.assertEqual(code_of(oracle.row_concentration_q, [[0], [0]]), "ZERO_ENERGY")
        self.assertEqual(oracle.row_concentration_q([[1], [1]]), 1)
        self.assertEqual(oracle.row_concentration_q([[1], [0]]), 2)
        self.assertEqual(code_of(oracle._det_q, [[1, 2]]), "NOT_SQUARE")
        self.assertEqual(oracle._det_q([[0, 1], [1, 0]]), -1)
        self.assertEqual(oracle._det_q([[0, 0], [0, 1]]), 0)
        self.assertEqual(oracle._det_q([[2, 1], [4, 3]]), 2)

    def test_binary64_and_cells(self):
        self.assertEqual(code_of(oracle.nearest_binary64, 1), "INVALID_FRACTION")
        self.assertEqual(code_of(oracle.nearest_binary64, Fraction(0)), "NONPOSITIVE")
        self.assertEqual(code_of(oracle.nearest_binary64, Fraction(-1)), "NONPOSITIVE")
        self.assertEqual(oracle.nearest_binary64(Fraction(3, 20)), (0x13333333333333, 55))
        self.assertEqual(oracle.nearest_binary64(Fraction(1)), (1 << 52, 52))
        self.assertEqual(oracle.nearest_binary64(Fraction((1 << 60) - 1, 1 << 60)), (1 << 52, 52))
        self.assertEqual(oracle.nearest_binary64(Fraction(1, 3)), (0x15555555555555, 54))
        self.assertEqual(oracle.nearest_binary64(Fraction(10)), (0x14000000000000, 49))
        for fn in (oracle.lane_local_v3_digest, oracle.full_diffusion_digest):
            self.assertEqual(code_of(fn, "x" * 1088), "INVALID_CELL_TYPE")
            self.assertEqual(code_of(fn, b"x" * 1087), "INVALID_CELL_LENGTH")
            self.assertEqual(len(fn(bytes(1088))), 32)
        self.assertEqual(code_of(oracle.changed_byte_positions, b"ab", b"a"), "DIM_MISMATCH")
        self.assertEqual(oracle.changed_byte_positions(b"abc", b"abd"), [2])
        self.assertEqual(oracle.rotl32(0x80000001, 1), 3)

    def test_bracket_gates_and_rationals(self):
        self.assertEqual(code_of(oracle.zero_success_upper_bracket, 0, Fraction(1, 20), 4), "INT_OUT_OF_RANGE")
        self.assertEqual(code_of(oracle.zero_success_upper_bracket, 96, Fraction(1, 20), 0), "INT_OUT_OF_RANGE")
        for n, alpha, it in ((96, Fraction(1, 20), 24), (10, Fraction(1, 2), 10), (1, Fraction(1, 3), 6)):
            self.assertEqual(oracle.zero_success_upper_bracket(n, alpha, it), verifier._independent_cp_bracket(n, alpha, it))
        self.assertEqual(oracle.argmax_val([]), [])
        self.assertEqual(oracle.argmax_val([{"val": 1}, {"val": 3}, {"val": 2}]), [{"val": 3}])
        self.assertEqual(oracle.gate_filter([{"s": True, "h": False}, {"s": True, "h": True}], ("s", "h")), [{"s": True, "h": True}])
        self.assertEqual(code_of(oracle.parse_unit_rational, 1, "p"), "INVALID_STR")
        for bad in ("1/0", "\u0661/2", "a/b", "1", "1/2/3", "-1/2", "1" * 41 + "/2", " 1/2"):
            self.assertEqual(code_of(oracle.parse_unit_rational, bad, "p"), "INVALID_RATIONAL_STR", bad)
        self.assertEqual(code_of(oracle.parse_unit_rational, "2/1", "p"), "P_VALUE_OUT_OF_RANGE")
        self.assertEqual(oracle.parse_unit_rational("1/1", "p"), 1)
        self.assertEqual(oracle.parse_unit_rational("0/5", "p"), 0)

    def test_payload_has_no_shared_mutable_aliases(self):
        p1 = oracle.build_payload()
        p1["pillar3_exp_delta"]["repaired_gates"]["kill_tri_min"] = 0
        p1["upstream_pins"][0]["sha256"] = "0" * 64
        p1["audit_findings"][0]["verdict"] = "TRUE"
        p1["pillar4_triple_gate"]["selection_noncommutation"]["candidates"][0]["val"] = 0
        p1["pinned_artifacts"]["lean_theorem_names"].append("x")
        self.assertEqual(oracle.build_payload(), PAYLOAD)
        spec = oracle.build_exp_delta_spec()
        spec["gates"]["thresholds"]["kill_tri_min"] = 0
        self.assertEqual(oracle.REPAIRED_GATES["kill_tri_min"], 49)


class Test03EvaluatorEdges(unittest.TestCase):
    def ev(self, **kw):
        return oracle.evaluate_exp_delta_results(oracle.synthetic_results(**kw))

    def test_guards(self):
        self.assertEqual(code_of(oracle.evaluate_exp_delta_results, []), "INVALID_RESULTS")
        bad = oracle.synthetic_results()
        bad["extra"] = 1
        self.assertEqual(code_of(oracle.evaluate_exp_delta_results, bad), "RESULTS_KEYSET_MISMATCH")
        self.assertEqual(code_of(self.ev, schema_version="x"), "RESULTS_SCHEMA_MISMATCH")
        self.assertEqual(code_of(self.ev, r_hidden=True), "INVALID_INT")
        self.assertEqual(code_of(self.ev, r_hidden=665), "INT_OUT_OF_RANGE")
        self.assertEqual(code_of(self.ev, r_hidden=-1), "INT_OUT_OF_RANGE")
        self.assertEqual(code_of(self.ev, p_adj_tri="3/2"), "P_VALUE_OUT_OF_RANGE")

    def test_resource_and_agreement_edges(self):
        self.assertEqual(self.ev(), "PASS")
        self.assertEqual(self.ev(peak_vram_mib=7680), "PASS")
        self.assertEqual(self.ev(peak_vram_mib=7681), "FAIL_CLOSED_RESOURCE")
        self.assertEqual(self.ev(wall_3080_s=600), "PASS")
        self.assertEqual(self.ev(wall_3080_s=601), "FAIL_CLOSED_RESOURCE")
        self.assertEqual(self.ev(ram_m1_mib=20480), "PASS")
        self.assertEqual(self.ev(ram_m1_mib=20481), "FAIL_CLOSED_RESOURCE")
        self.assertEqual(self.ev(wall_m1_s=1800), "PASS")
        self.assertEqual(self.ev(wall_m1_s=1801), "FAIL_CLOSED_RESOURCE")
        self.assertEqual(self.ev(r_hidden_node_a=321), "PASS")
        self.assertEqual(self.ev(r_hidden_node_a=322), "ABSTAIN_NODE_DISAGREEMENT")
        self.assertEqual(self.ev(r_hidden_node_b=316), "ABSTAIN_NODE_DISAGREEMENT")
        self.assertEqual(self.ev(fp_hidden=10, fp_budget=10), "PASS")
        self.assertEqual(self.ev(fp_hidden=11, fp_budget=10), "ABSTAIN_FPR_UNMATCHED")

    def test_kill_and_pass_edges(self):
        self.assertEqual(self.ev(r_hidden_cross=14, p_adj_cross="1/20"), "KILL")
        self.assertEqual(self.ev(r_hidden_cross=14, p_adj_cross="1/19"), "ABSTAIN_INTERMEDIATE")
        self.assertEqual(self.ev(r_hidden_cross=13, p_adj_cross="0/1"), "ABSTAIN_INTERMEDIATE")
        self.assertEqual(self.ev(r_hidden=340, p_adj_overall="1/20"), "KILL")
        self.assertEqual(self.ev(r_hidden=340, p_adj_overall="1/19"), "ABSTAIN_INTERMEDIATE")
        self.assertEqual(self.ev(r_hidden=339, p_adj_overall="0/1"), "ABSTAIN_INTERMEDIATE")
        self.assertEqual(self.ev(t_hidden=49, p_adj_tri="1/20"), "KILL")
        self.assertEqual(self.ev(t_hidden=49, p_adj_tri="1/19"), "ABSTAIN_INTERMEDIATE")
        self.assertEqual(self.ev(t_hidden=48, p_adj_tri="0/1"), "ABSTAIN_INTERMEDIATE")
        self.assertEqual(self.ev(r_hidden=320), "PASS")
        self.assertEqual(self.ev(r_hidden=321), "ABSTAIN_INTERMEDIATE")
        self.assertEqual(self.ev(r_hidden_cross=8), "PASS")
        self.assertEqual(self.ev(r_hidden_cross=9), "ABSTAIN_INTERMEDIATE")
        self.assertEqual(self.ev(t_hidden=25), "ABSTAIN_INTERMEDIATE")
        self.assertEqual([r["verdict"] for r in oracle.evaluator_selftest()],
                         ["PASS", "KILL", "ABSTAIN_INTERMEDIATE", "ABSTAIN_FPR_UNMATCHED",
                          "ABSTAIN_INTERMEDIATE", "ABSTAIN_NODE_DISAGREEMENT", "FAIL_CLOSED_RESOURCE"])


class Test04ExactReplays(unittest.TestCase):
    """Independent re-derivations (own loops, no oracle math helpers)."""

    def test_kronecker_identities_independent(self):
        a = [[3, -1, 2], [0, 4, -2]]
        b = [[1, 2], [-3, 1], [2, 2]]
        rows = [[x * y for x in ar for y in bp] for ar in a for bp in b]

        def d(u, v):
            return sum(x * y for x, y in zip(u, v))
        for i, u in enumerate(rows):
            for j, v in enumerate(rows):
                self.assertEqual(d(u, v), d(a[i // 3], a[j // 3]) * d(b[i % 3], b[j % 3]))
        pb = PAYLOAD["pillar1_kronecker_algebra"]["param_budget"]
        self.assertEqual(pb["reduction_ratio_q"], "262144/33")
        self.assertEqual(pb["realistic_reduction_ratio_q"], "18992/33")
        self.assertEqual(pb["full_table_params"], 1 << 31)
        self.assertEqual(pb["factored_params"], 270336)
        ki = PAYLOAD["pillar1_kronecker_algebra"]["kronecker_identities"]
        self.assertEqual((ki["pair_identities_hold"], ki["norm_identities_hold"]), (144, 12))
        self.assertEqual((ki["kron_gram_vlp_rank"], ki["flat_table_gram_vlp_rank"]), (1, 9))
        self.assertIs(ki["schur_kron_commutes"], True)

    def test_dpi_and_obstruction(self):
        dpi = PAYLOAD["pillar1_kronecker_algebra"]["dpi_calibration"]
        self.assertEqual(dpi["table_c_row_q"], "1")
        self.assertEqual(dpi["patched_table_c_row_q"], "1")
        self.assertEqual(dpi["patch_c_row_q"], "4")
        self.assertEqual(dpi["flat_single_row_patch_c_row_q"], "12")
        for row in oracle.CAL_A:
            self.assertEqual(sum(x * x for x in row), 9)
        for row in oracle.CAL_B:
            self.assertEqual(sum(x * x for x in row), 4)
        r1 = PAYLOAD["pillar2_rank1_obstruction"]
        self.assertEqual((r1["additive_minor_lhs"], r1["additive_minor_rhs"]), (1, 0))
        self.assertEqual(r1["additive_kernel_vlp_rank"], 2)
        self.assertEqual(r1["kron_shared_root_cross_pattern_similarity_q"], "0")
        self.assertEqual(r1["hybrid_shared_root_cross_pattern_similarity_q"], "9")
        self.assertIs(r1["ml4_root_floor_claim_holds_for_rank1"], False)

    def test_exp_delta_triple_gate_wire(self):
        ed = PAYLOAD["pillar3_exp_delta"]
        tri = 220 * Fraction(319, 664) ** 3
        self.assertEqual(ed["surface"]["triangle_independence_model_q"], f"{tri.numerator}/{tri.denominator}")
        self.assertEqual(ed["ml4_gate_checks"]["repaired_kill_tri_ceil_twice_model"], 49)
        self.assertTrue(48 < 2 * tri <= 49)
        self.assertIs(ed["ml4_gate_checks"]["ml4_kill_tri_is_at_least_twice_model"], False)
        self.assertEqual(ed["spec_sha256"], oracle.sha256_hex(oracle.canonical_json_bytes(oracle.build_exp_delta_spec())))
        zs = PAYLOAD["pillar4_triple_gate"]["zero_success_bound"]
        self.assertTrue(20 * 31 ** 96 < 32 ** 96)
        self.assertIs(zs["cp_upper_strictly_below_one_32nd"], True)
        gc = PAYLOAD["pillar4_triple_gate"]["gate_commutation"]
        self.assertEqual((gc["candidate_lists"], gc["orderings_commute"], gc["witness_lists"]), (585, 3510, 185))
        av = PAYLOAD["pillar5_wire_hash"]["avalanche"]
        self.assertEqual(av["lane_local_v3_changed_bytes"], [8] * 8)
        self.assertEqual(av["lane_local_v3_flips_confined_to_own_lane"], 8)
        self.assertTrue(min(av["full_diffusion_changed_bytes"]) >= 16)
        self.assertTrue(min(av["sha256_changed_bytes"]) >= 16)
        qs = PAYLOAD["pillar5_wire_hash"]["quantize_serialize_order"]
        self.assertEqual((qs["q_exact_round_half_even_10v"], qs["q_after_float_wire_10v"]), (2, 1))
        self.assertEqual(PAYLOAD["pillar5_wire_hash"]["hampack_locality"]["ratio_q"], "14949/2048")
        self.assertEqual(len(PAYLOAD["audit_findings"]), 13)
        self.assertEqual(PAYLOAD["novelty_classification"], "N0")


class Test05ZoneBIO(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)
        self._cwd = os.getcwd()
        self._pwd = os.environ.get("PWD")

    def tearDown(self):
        os.chdir(self._cwd)
        if self._pwd is None:
            os.environ.pop("PWD", None)
        else:
            os.environ["PWD"] = self._pwd
        for p in self.td.rglob("*"):
            if p.is_dir() and not p.is_symlink():
                os.chmod(p, 0o700)
        self._td.cleanup()

    def mk(self, name, data=b"abc"):
        p = self.td / name
        p.write_bytes(data)
        return p

    def test_path_guards(self):
        R = verifier.read_regular_bytes_capped
        self.assertEqual(code_of(R, "", "x"), "EMPTY_PATH")
        self.assertEqual(code_of(R, "a\x00b", "x"), "NUL_BYTE_FORBIDDEN")
        self.assertEqual(code_of(R, "a\udcff", "x"), "INVALID_UTF8_SURROGATE")
        self.assertEqual(code_of(R, 5, "x"), "INVALID_STR")
        self.assertEqual(code_of(R, self.mk("f"), "x", max_bytes=0), "INT_OUT_OF_RANGE")
        self.assertEqual(R(self.mk("g"), "x"), b"abc")
        os.symlink(self.mk("t"), self.td / "lnk")
        self.assertEqual(code_of(R, self.td / "lnk", "x"), "SYMLINK_IN_PATH")
        (self.td / "real").mkdir()
        self.mk("real/f")
        os.symlink(self.td / "real", self.td / "dlink")
        self.assertEqual(code_of(R, self.td / "dlink" / "f", "x"), "SYMLINK_IN_PATH")
        self.assertEqual(code_of(R, self.td / "missing" / "f", "x"), "IO_OPEN_ERROR")
        rel = os.path.relpath(self.mk("relf"), os.getcwd())
        self.assertEqual(R(rel, "x"), b"abc")
        with mock.patch.object(verifier.os, "lstat", side_effect=PermissionError("no")):
            self.assertEqual(code_of(R, self.mk("h"), "x"), "IO_STAT_ERROR")

    def test_cwd_and_pwd(self):
        R = verifier.read_regular_bytes_capped
        f = self.mk("f")
        with mock.patch.object(verifier.os, "getcwd", side_effect=FileNotFoundError("gone")):
            self.assertEqual(code_of(R, f, "x"), "CWD_ERROR")
        (self.td / "real").mkdir()
        os.symlink(self.td / "real", self.td / "via")
        os.chdir(self.td / "real")
        os.environ["PWD"] = str(self.td / "via")
        self.assertEqual(code_of(R, f, "x"), "SYMLINK_IN_PATH")
        os.environ["PWD"] = str(self.td / "real")
        self.assertEqual(R(f, "x"), b"abc")
        os.environ["PWD"] = str(self.td / "nonexistent-dir")
        self.assertEqual(R(f, "x"), b"abc")
        os.environ["PWD"] = "relative/path"
        self.assertEqual(R(f, "x"), b"abc")
        os.environ["PWD"] = str(self.td)
        self.assertEqual(R(f, "x"), b"abc")

    def test_file_kind_and_size_guards(self):
        R = verifier.read_regular_bytes_capped
        self.assertEqual(code_of(R, self.td, "x"), "NOT_REGULAR_FILE")
        os.mkfifo(self.td / "fifo")
        self.assertEqual(code_of(R, self.td / "fifo", "x"), "NOT_REGULAR_FILE")
        os.link(self.mk("a"), self.td / "b")
        self.assertEqual(code_of(R, self.td / "a", "x"), "HARDLINK_FORBIDDEN")
        self.assertEqual(R(self.mk("ten", b"0123456789"), "x", max_bytes=10), b"0123456789")
        self.assertEqual(code_of(R, self.mk("eleven", b"0123456789A"), "x", max_bytes=10), "FILE_TOO_LARGE")
        self.assertEqual(code_of(R, f"/proc/{os.getpid()}/status", "x", max_bytes=8), "FILE_STREAM_TOO_LARGE")
        with mock.patch.object(verifier.os, "read", side_effect=OSError("eio")):
            self.assertEqual(code_of(R, self.mk("r"), "x"), "IO_READ_ERROR")

    def test_atomic_write(self):
        W = verifier.write_regular_bytes_atomic_0600
        self.assertEqual(code_of(W, self.td / "o", "s", "x"), "INVALID_BYTES")
        self.assertEqual(code_of(W, self.td / "nodir" / "o", b"d", "x"), "PARENT_MISSING")
        self.mk("file")
        self.assertEqual(code_of(W, self.td / "file" / "o", b"d", "x"), "PARENT_NOT_DIR")
        (self.td / "adir").mkdir()
        self.assertEqual(code_of(W, self.td / "adir", b"d", "x"), "TARGET_NOT_REGULAR")
        os.link(self.mk("h1"), self.td / "h2")
        self.assertEqual(code_of(W, self.td / "h1", b"d", "x"), "HARDLINK_FORBIDDEN")
        os.symlink(self.mk("tgt"), self.td / "sl")
        self.assertEqual(code_of(W, self.td / "sl", b"d", "x"), "SYMLINK_IN_PATH")
        out = W(self.td / "new.json", b"payload", "x")
        self.assertEqual(out.read_bytes(), b"payload")
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)
        W(self.td / "new.json", b"second", "x")
        self.assertEqual((self.td / "new.json").read_bytes(), b"second")
        with mock.patch.object(verifier.os, "fsync", side_effect=OSError("eio")):
            self.assertEqual(code_of(W, self.td / "fail.json", b"d", "x"), "IO_WRITE_ERROR")
        self.assertEqual(sorted(p.name for p in self.td.iterdir() if p.name.startswith(".")), [])
        (self.td / "ro").mkdir()
        os.chmod(self.td / "ro", 0o500)
        self.assertEqual(code_of(W, self.td / "ro" / "o", b"d", "x"), "IO_OPEN_ERROR")


class Test06StrictJSON(unittest.TestCase):
    def test_parser_guards(self):
        P = verifier.parse_strict_json_bytes
        self.assertEqual(code_of(P, "{}", "x"), "INVALID_BYTES")
        big = b'"' + b"a" * (verifier.MAX_JSON_BYTES - 3) + b'"\n'
        self.assertEqual(len(big), verifier.MAX_JSON_BYTES)
        self.assertEqual(P(big, "x"), "a" * (verifier.MAX_JSON_BYTES - 3))
        self.assertEqual(code_of(P, big + b" ", "x"), "JSON_TOO_LARGE")
        self.assertEqual(code_of(P, '{"a":"\u00e9"}\n'.encode("utf-8"), "x"), "NON_ASCII_JSON")
        self.assertEqual(code_of(P, b'{"a":' + b"1" * 81 + b"}\n", "x"), "JSON_INT_TOO_LARGE")
        self.assertEqual(P(b'{"a":' + b"1" * 80 + b"}\n", "x"), {"a": int("1" * 80)})
        self.assertEqual(code_of(P, b'{"a":-' + b"1" * 81 + b"}\n", "x"), "JSON_INT_TOO_LARGE")
        self.assertEqual(code_of(P, b'{"a":1,"a":2}\n', "x"), "DUPLICATE_JSON_KEY")
        self.assertEqual(code_of(P, b'{"a":1.5}\n', "x"), "FORBIDDEN_JSON_FLOAT")
        self.assertEqual(code_of(P, b'{"a":NaN}\n', "x"), "FORBIDDEN_JSON_CONST")
        self.assertEqual(code_of(P, b'{"a":', "x"), "INVALID_JSON")
        self.assertEqual(code_of(P, b"[" * 100000, "x"), "INVALID_JSON")
        self.assertEqual(code_of(P, b'{"a": 1}\n', "x"), "NON_CANONICAL_JSON")
        self.assertEqual(code_of(P, b'{"a":1}', "x"), "NON_CANONICAL_JSON")
        self.assertEqual(P(b'{"a":[1,true,null,"s"]}\n', "x"), {"a": [1, True, None, "s"]})


POCS: tuple[tuple[str, str], ...] = (
    ("R01_STRING_OR_GUILLEMET", "def s := \"x\""),
    ("R01_STRING_OR_GUILLEMET", "def «weird» := 1"),
    ("R02_SORRY_ADMIT_AXIOM", "theorem t : False := sorry"),
    ("R02_SORRY_ADMIT_AXIOM", "theorem t : False := _root_.sorryAx False"),
    ("R02_SORRY_ADMIT_AXIOM", "axiom bad : False"),
    ("R02_SORRY_ADMIT_AXIOM", "theorem t : False := by admit"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_PRIVATE", "partial def f : Nat → Nat := f"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_PRIVATE", "opaque c : Nat"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_PRIVATE", "unsafe def g : Nat := 0"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_PRIVATE", "private theorem p : True := trivial"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_PRIVATE", "protected theorem p : True := trivial"),
    ("R04_KERNEL_BYPASS_PANIC", "theorem t : 1 = 1 := by native_decide"),
    ("R04_KERNEL_BYPASS_PANIC", "def f : Nat := panic! (String.ofList [])"),
    ("R04_KERNEL_BYPASS_PANIC", "def f : Nat := unreachable!"),
    ("R04_KERNEL_BYPASS_PANIC", "def f : Nat := panicCore (String.ofList [])"),
    ("R04_KERNEL_BYPASS_PANIC", "def f : Nat := panicWithPosWithDecl m d 1 2 (String.ofList [])"),
    ("R04_KERNEL_BYPASS_PANIC", "theorem t := Lean.ofReduceBool a b h"),
    ("R05_FFI_IMPLEMENTED_BY", "@[implemented_by g] def f : Nat := 0"),
    ("R05_FFI_IMPLEMENTED_BY", "@[csimp] theorem c : f = g := rfl"),
    ("R06_INITIALIZE", "initialize r : IO.Ref Nat ← IO.mkRef 0"),
    ("R06_INITIALIZE", "builtin_initialize foo"),
    ("R07_INIT_ATTRIBUTE", "@[init g] def f : IO Unit := pure ()"),
    ("R07_INIT_ATTRIBUTE", "@[simp, builtin_init g] def f : Nat := 0"),
    ("R07_INIT_ATTRIBUTE", "attribute [init g] f"),
    ("R08_EXPORT", "@[export lean_f] def f : Nat := 0"),
    ("R08_EXPORT", "export Nat (succ)"),
    ("R09_METAPROGRAMMING", "macro_rules | `(x) => `(y)"),
    ("R09_METAPROGRAMMING", "declare_syntax_cat foo"),
    ("R09_METAPROGRAMMING", "elab_rules : tactic | _ => pure ()"),
    ("R09_METAPROGRAMMING", "run_cmd pure ()"),
    ("R09_METAPROGRAMMING", "@[term_elab foo] def f : Nat := 0"),
    ("R09_METAPROGRAMMING", "@[command_elab foo] def f : Nat := 0"),
    ("R09_METAPROGRAMMING", "@[tactic foo] def f : Nat := 0"),
    ("R09_METAPROGRAMMING", "@[builtin_macro foo] def f : Nat := 0"),
    ("R10_NOTATION", "notation a \u2295 b => a + b"),
    ("R10_NOTATION", "infixl:65 \u2295 => Nat.add"),
    ("R11_IMPORT", "import Lean"),
    ("R12_SET_OPTION", "set_option maxHeartbeats 0 in"),
    ("R13_DEBUG_WARN_OPTIONS", "theorem t := by debug.skipKernelTC"),
    ("R13_DEBUG_WARN_OPTIONS", "x debug.terminalTacticsAsSorry y"),
    ("R13_DEBUG_WARN_OPTIONS", "x warn.sorry y"),
    ("R14_DBG_BUILTINS", "def f := dbg_trace 1"),
    ("R14_DBG_BUILTINS", "def f := dbgTraceIfShared 1 2"),
    ("R14_DBG_BUILTINS", "def f := dbgSleep 1 fun _ => 0"),
    ("R14_DBG_BUILTINS", "def f := dbgStackTrace fun _ => 0"),
    ("R15_HASH_COMMANDS", "#eval 1"),
    ("R15_HASH_COMMANDS", "#guard_msgs in"),
    ("R15_HASH_COMMANDS", "#exit"),
    ("R15_HASH_COMMANDS", "#check Nat"),
    ("R16_PLUS_NATIVE_FLAG", "theorem t : 1 = 1 := by decide +revert +native"),
    ("R17_NATIVE_CONFIG", "theorem t : 1 = 1 := by decide (config := { native := true })"),
    ("R17_NATIVE_CONFIG", "theorem t : 1 = 1 := by decide (native := true)"),
    ("R17_NATIVE_CONFIG", "def c : Lean.Meta.DecideConfig := {}"),
    ("R18_MULTILINE_DECIDE", "theorem t : 1 = 1 := by decide\n  (kernel := true)"),
    ("R18_MULTILINE_DECIDE", "theorem t : 1 = 1 := by decide\n  +kernel"),
)

CLEAN_CONTROLS: tuple[str, ...] = (
    "theorem partially_ordered_ok : True := trivial",
    "theorem native_ok : True := trivial",
    "theorem t : 1 = 1 := by decide\n\ntheorem u : True := trivial",
    "-- sorry, axiom, partial, #eval in a line comment\ntheorem t : True := trivial",
    "/- block: import Lean, set_option, dbg_trace -/ theorem t : True := trivial",
    "theorem exported_value : True := trivial",
    "def initializer_count : Nat := 0",
    "theorem decide_free (n : Nat) : n = n := rfl",
    "@[simp] theorem tactic_free_simp_lemma : True := trivial",
    "theorem my_panic_free : True := trivial",
)


class Test07LeanStaticScanner(unittest.TestCase):
    def test_every_rule_has_a_poc_hit(self):
        covered = set()
        for rid, src in POCS:
            hits = verifier.lean4_rule_hits(src)
            self.assertIn(rid, hits, f"{rid} missed {src!r}")
            covered.add(rid)
            self.assertEqual(code_of(verifier.static_gate_lean4_source, LEAN_SRC + "\n" + src + "\n"), "LEAN4_TRUST_ESCAPE")
        self.assertEqual(covered, {rid for rid, _ in verifier.LEAN4_RULES})

    def test_clean_controls_zero_false_positives(self):
        for src in CLEAN_CONTROLS:
            self.assertEqual(verifier.lean4_rule_hits(src), [], src)

    def test_structural_gates(self):
        G = verifier.static_gate_lean4_source
        self.assertEqual(code_of(G, LEAN_SRC + "\r"), "LEAN4_BAD_CHARS")
        self.assertEqual(code_of(G, LEAN_SRC + "\x00"), "LEAN4_BAD_CHARS")
        self.assertEqual(code_of(G, LEAN_SRC + "\n/- open"), "LEAN4_UNTERMINATED_COMMENT")
        self.assertEqual(code_of(G, LEAN_SRC + "\n#print Nat\n"), "LEAN4_BAD_PRINT")
        self.assertEqual(code_of(G, LEAN_SRC + "\n#print axioms Foo.bar\n"), "LEAN4_BAD_PRINT")
        last = f"#print axioms {oracle.LEAN_THEOREM_NAMES[-1]}\n"
        self.assertEqual(code_of(G, LEAN_SRC.replace(last, "")), "LEAN4_PRINT_SET_MISMATCH")
        self.assertEqual(code_of(G, LEAN_SRC + last), "LEAN4_PRINT_SET_MISMATCH")
        self.assertEqual(code_of(G, LEAN_SRC.replace("theorem dot_append ", "theorem dot_append_x ")), "LEAN4_MISSING_THEOREM")
        self.assertEqual(code_of(G, LEAN_SRC.replace("theorem latent_repair_collision_ceiling", "theorem latent_x")), "LEAN4_MISSING_THEOREM")

    def test_comment_stripper(self):
        S = verifier.strip_lean4_comments
        self.assertEqual(S("/- a -- b -/x"), "x")
        self.assertEqual(S("a -- b"), "a ")
        self.assertEqual(S("a -- b\nc"), "a \nc")
        self.assertEqual(S("x -/ y"), "x -/ y")
        self.assertEqual(S("/- abc -/x"), "x")
        self.assertEqual(S("/- a /- b -/ c -/d"), "d")
        self.assertEqual(S("/- a\nb -/c"), "\nc")
        self.assertEqual(code_of(S, "/- a /- b -/"), "LEAN4_UNTERMINATED_COMMENT")
        self.assertEqual(verifier.lean4_rule_hits("/- sorry -/ theorem t : True := trivial"), [])


class Test08LeanLive(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_resolve_binary(self):
        os.environ["ALETHEIA_LEAN_BIN"] = "/nonexistent/lean-bin"
        self.assertEqual(code_of(verifier.resolve_lean_binary), "LEAN_BINARY_NOT_FILE")
        with tempfile.TemporaryDirectory() as td:
            os.environ["ALETHEIA_LEAN_BIN"] = td
            self.assertEqual(code_of(verifier.resolve_lean_binary), "LEAN_BINARY_NOT_FILE")
            f = Path(td) / "lean"
            f.write_bytes(b"x")
            os.chmod(f, 0o600)
            os.environ["ALETHEIA_LEAN_BIN"] = str(f)
            self.assertEqual(code_of(verifier.resolve_lean_binary), "LEAN_BINARY_NOT_EXECUTABLE")
            os.chmod(f, 0o700)
            self.assertEqual(verifier.resolve_lean_binary(), str(f))
        os.environ["ALETHEIA_LEAN_BIN"] = ""
        with mock.patch.object(verifier.shutil, "which", return_value=None):
            self.assertEqual(code_of(verifier.resolve_lean_binary), "LEAN_BINARY_UNAVAILABLE")
        with mock.patch.object(verifier.shutil, "which", return_value="/opt/lean"):
            self.assertEqual(verifier.resolve_lean_binary(), "/opt/lean")

    def test_env_scrub(self):
        for k in ("LEAN_PATH", "LEAN_OPTS", "LEAN_SRC_PATH", "LEAN_CC", "LEAN_SYSROOT", "ELAN_TOOLCHAIN", "ELAN_HOME"):
            os.environ[k] = "/evil"
        os.environ["S104_KEEP"] = "1"
        env = verifier.scrubbed_lean_env()
        for k in ("LEAN_PATH", "LEAN_OPTS", "LEAN_SRC_PATH", "LEAN_CC", "LEAN_SYSROOT", "ELAN_TOOLCHAIN", "ELAN_HOME"):
            self.assertNotIn(k, env)
        self.assertEqual(env["S104_KEEP"], "1")

    def run_mocked(self, outs):
        with mock.patch.object(verifier, "resolve_lean_binary", return_value="lean"), \
                mock.patch.object(verifier.subprocess, "run", side_effect=outs) as m:
            code = code_of(verifier.verify_lean4_file_live, LEAN_PATH)
        return code, m

    def test_mocked_live_outcomes(self):
        good = axiom_stdout(oracle.LEAN_THEOREM_NAMES)
        os.environ["LEAN_PATH"] = "/evil"
        code, m = self.run_mocked([completed(0, GOOD_VERSION), completed(0, good)])
        self.assertEqual(code, "NO_ERROR")
        for call in m.call_args_list:
            self.assertNotIn("LEAN_PATH", call.kwargs["env"])
        self.assertEqual(m.call_args_list[1].kwargs["input"], LEAN_SRC)
        self.assertEqual(self.run_mocked([completed(1, GOOD_VERSION), completed(0, good)])[0], "LEAN_VERSION_MISMATCH")
        self.assertEqual(self.run_mocked([completed(0, "Lean (version 4.35.0, x)\n"), completed(0, good)])[0], "LEAN_VERSION_MISMATCH")
        self.assertEqual(self.run_mocked([completed(0, GOOD_VERSION), completed(1, good)])[0], "LEAN_COMPILE_FAIL")
        self.assertEqual(self.run_mocked([completed(0, GOOD_VERSION), completed(0, good, "err")])[0], "LEAN_STDERR_NONEMPTY")
        self.assertEqual(self.run_mocked([completed(0, GOOD_VERSION), completed(0, good + "<stdin>:1:1: warning: x\n")])[0], "LEAN_WARNING_FORBIDDEN")
        self.assertEqual(self.run_mocked(OSError("noexec"))[0], "LEAN_EXEC_ERROR")
        self.assertEqual(self.run_mocked(subprocess.TimeoutExpired("lean", 1))[0], "LEAN_EXEC_ERROR")
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "Bad.lean"
            bad.write_bytes(b"\xff\xfe")
            self.assertEqual(code_of(verifier.verify_lean4_file_live, bad), "INVALID_UTF8")

    def test_axiom_output_parser(self):
        names = oracle.LEAN_THEOREM_NAMES
        P = verifier.parse_lean_axiom_output
        out = P(axiom_stdout(names, dep_for=names[:3]))
        self.assertEqual(out[names[0]], ["propext", "Quot.sound"])
        self.assertEqual(out[names[-1]], [])
        wrapped = axiom_stdout(names[1:]) + f"'{names[0]}' depends on axioms: [propext,\n Quot.sound]\n\n"
        self.assertEqual(P(wrapped)[names[0]], ["propext", "Quot.sound"])
        self.assertEqual(code_of(P, axiom_stdout(names) + "junk\n"), "LEAN_UNEXPECTED_STDOUT")
        self.assertEqual(code_of(P, axiom_stdout(names) + axiom_stdout(names[:1])), "LEAN_DUPLICATE_THEOREM")
        bad_ax = axiom_stdout(names[1:]) + f"'{names[0]}' depends on axioms: [propext, Classical.choice]\n"
        self.assertEqual(code_of(P, bad_ax), "LEAN_FORBIDDEN_AXIOM")
        self.assertEqual(code_of(P, axiom_stdout(names[1:])), "LEAN_THEOREM_SET_MISMATCH")
        trunc = axiom_stdout(names[1:]) + f"'{names[0]}' depends on axioms: [propext,"
        self.assertEqual(code_of(P, trunc), "LEAN_UNEXPECTED_STDOUT")

    def test_real_lean_kernel_check(self):
        live = verifier.verify_lean4_file_live(LEAN_PATH)
        self.assertEqual(live["theorems_verified"], 25)
        self.assertEqual(live["lean_source_sha256"], oracle.PINNED_LEAN_SOURCE_SHA256)
        self.assertIn("4.36.0", live["lean_version"])


SEMANTIC_TAMPERS: tuple[tuple[tuple, object, str], ...] = (
    (("pillar1_kronecker_algebra", "param_budget", "reduction_ratio_q"), "7900", "SEC_PARAM_RATIO"),
    (("pillar1_kronecker_algebra", "param_budget", "realistic_reduction_ratio_q"), "576", "SEC_REAL_RATIO"),
    (("pillar1_kronecker_algebra", "dpi_calibration", "patch_c_row_q"), "1", "SEC_PATCH_C_ROW"),
    (("pillar1_kronecker_algebra", "kronecker_identities", "pair_identities_hold"), 143, "SEC_KRON_PAIRS"),
    (("pillar1_kronecker_algebra", "kronecker_identities", "schur_kron_commutes"), False, "SEC_SCHUR"),
    (("pillar2_rank1_obstruction", "kron_shared_root_cross_pattern_similarity_q"), "9", "SEC_ROOT_FLOOR"),
    (("pillar3_exp_delta", "surface", "triangle_independence_model_q"), "24", "SEC_TRI_MODEL"),
    (("pillar3_exp_delta", "ml4_gate_checks", "repaired_kill_tri_ceil_twice_model"), 44, "SEC_TRI_KILL"),
    (("pillar4_triple_gate", "zero_success_bound", "cp_upper_bracket_lo_q"), "1/32", "SEC_CP_LO"),
    (("pillar4_triple_gate", "zero_success_bound", "cp_upper_bracket_hi_q"), "1/32", "SEC_CP_HI"),
    (("pillar5_wire_hash", "quantize_serialize_order", "binary64_mantissa"), 0x13333333333334, "SEC_BINARY64"),
    (("pillar5_wire_hash", "avalanche", "lane_local_v3_changed_bytes"), [16] * 8, "SEC_LANE_LOCAL"),
    (("pillar5_wire_hash", "hampack_locality", "ratio_q"), "153/20", "SEC_HAMPACK"),
    (("pillar1_kronecker_algebra", "param_budget", "reduction_ratio_q"), "1.5", "INVALID_RATIONAL_STR"),
    (("pillar1_kronecker_algebra", "param_budget", "reduction_ratio_q"), "1" * 5000, "INVALID_RATIONAL_STR"),
    (("prior_art", 0), "forged", "SEC_PAYLOAD_PIN_MISMATCH"),
    (("pillar2_rank1_obstruction", "hybrid_restores_root_floor"), 1, "SEC_PAYLOAD_PIN_MISMATCH"),
    (("scope", "gpu_touch"), 1, "SEC_PAYLOAD_PIN_MISMATCH"),
)


class Test09SecFr0Fr1(unittest.TestCase):
    def test_baseline_fr0_and_mocked_fr1(self):
        r0 = verifier.verify_certificate_dict(copy.deepcopy(CERT), full_replay=False)
        self.assertIs(r0["valid"], True)
        self.assertNotIn("lean_live", r0)
        with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE)):
            r1 = verifier.verify_certificate_dict(copy.deepcopy(CERT), full_replay=True)
        self.assertEqual(r1["lean_live"]["theorems_verified"], 25)
        self.assertEqual(r1["certificate_sha256"], CERT["certificate_sha256"])

    def test_envelope_guards(self):
        V = verifier.verify_certificate_dict
        self.assertEqual(code_of(V, copy.deepcopy(CERT), full_replay=1), "INVALID_BOOL")
        self.assertEqual(code_of(V, [], full_replay=False), "INVALID_CERT_TYPE")
        c = copy.deepcopy(CERT)
        c["payload"]["x"] = Fraction(1)
        self.assertEqual(code_of(V, c, full_replay=False), "FORBIDDEN_JSON_TYPE")
        c = copy.deepcopy(CERT)
        c["extra"] = 1
        self.assertEqual(code_of(V, c, full_replay=False), "KEYSET_MISMATCH")
        for key, code in (("schema_version", "SCHEMA_MISMATCH"), ("track_id", "SCHEMA_MISMATCH")):
            c = copy.deepcopy(CERT)
            c[key] = "forged"
            self.assertEqual(code_of(V, c, full_replay=False), code)
        c = copy.deepcopy(CERT)
        c["payload_sha256"] = "z" * 64
        self.assertEqual(code_of(V, c, full_replay=False), "INVALID_HEX64")
        c = copy.deepcopy(CERT)
        c["certificate_sha256"] = CERT["certificate_sha256"].upper()
        self.assertEqual(code_of(V, c, full_replay=False), "INVALID_HEX64")
        c = copy.deepcopy(CERT)
        c["payload_sha256"] = "0" * 64
        self.assertEqual(code_of(V, c, full_replay=False), "PAYLOAD_SHA_MISMATCH")
        c = copy.deepcopy(CERT)
        c["certificate_sha256"] = "0" * 64
        self.assertEqual(code_of(V, c, full_replay=False), "CERT_SHA_MISMATCH")
        self.assertEqual(code_of(verifier.secondary_audit_payload, []), "INVALID_PAYLOAD_TYPE")
        p = copy.deepcopy(PAYLOAD)
        del p["scope"]
        self.assertEqual(code_of(verifier.secondary_audit_payload, p), "KEYSET_MISMATCH")

    def test_semantic_forgeries_all_surfaces(self):
        for path, val, code in SEMANTIC_TAMPERS:
            p = copy.deepcopy(PAYLOAD)
            set_path(p, path, val)
            self.assertEqual(code_of(verifier.secondary_audit_payload, p), code, path)
            self.assertEqual(code_of(verifier.verify_certificate_dict, resign(p), full_replay=False), code, path)
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE)):
                self.assertEqual(code_of(verifier.verify_certificate_dict, resign(p), full_replay=True), code, path)

    def test_every_leaf_resigned_tamper_rejected(self):
        paths = list(leaf_paths(PAYLOAD))
        self.assertTrue(len(paths) > 300)
        bypass = []
        for path, v in paths:
            p = copy.deepcopy(PAYLOAD)
            set_path(p, path, tamper_value(v))
            for fr in (False,):
                if code_of(verifier.verify_certificate_dict, resign(p), full_replay=fr) == "NO_ERROR":
                    bypass.append(path)
            if code_of(verifier.secondary_audit_payload, p) == "NO_ERROR":
                bypass.append(path)
        self.assertEqual(bypass, [])

    def test_strict_deep_equal(self):
        D = verifier.strict_deep_equal
        self.assertEqual(D({"a": [1, {"b": True}]}, {"a": [1, {"b": True}]}), "")
        self.assertEqual(D({"a": [1, {"b": True}]}, {"a": [1, {"b": 1}]}), "payload.a[1].b")
        self.assertEqual(D({"a": 1}, {"b": 1}), "payload")
        self.assertEqual(D([1, 2], [1]), "payload")
        self.assertEqual(D({"a": "x"}, {"a": "y"}), "payload.a")
        self.assertIsNot(verifier.expected_payload(), verifier.expected_payload())

    def test_track_artifact_replay(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            for name in (oracle.LEAN_SOURCE_NAME, "lean-toolchain", "lakefile.toml", oracle.SPEC_FILE_NAME):
                shutil.copyfile(_THIS_DIR / name, t / name)
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE)):
                r = verifier.verify_certificate_dict(copy.deepcopy(CERT), full_replay=True, track_dir=t)
                self.assertIs(r["valid"], True)
                (t / "lean-toolchain").write_bytes(b"leanprover/lean4:v4.35.0\n")
                self.assertEqual(code_of(verifier._load_track_artifacts, t), "TOOLCHAIN_MISMATCH")
                shutil.copyfile(_THIS_DIR / "lean-toolchain", t / "lean-toolchain")
                (t / "lakefile.toml").write_bytes(b"name = \"x\"\n")
                self.assertEqual(code_of(verifier._load_track_artifacts, t), "LAKEFILE_SHA_MISMATCH")
                shutil.copyfile(_THIS_DIR / "lakefile.toml", t / "lakefile.toml")
                (t / oracle.SPEC_FILE_NAME).write_bytes(b"{}\n")
                self.assertEqual(code_of(verifier._load_track_artifacts, t), "SPEC_FILE_MISMATCH")
                shutil.copyfile(_THIS_DIR / oracle.SPEC_FILE_NAME, t / oracle.SPEC_FILE_NAME)
            wrong = dict(FAKE_LIVE, lean_source_sha256="0" * 64)
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=wrong):
                self.assertEqual(code_of(verifier._load_track_artifacts, t), "LEAN_SHA_MISMATCH")

    def test_upstream_pins(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "d").mkdir()
            (root / "d" / "f.md").write_bytes(b"hello")
            row = {"id": "T", "relpath": "d/f.md", "bytes": 5, "sha256": oracle.sha256_hex(b"hello")}
            with mock.patch.object(oracle, "UPSTREAM_PINS", (row,)):
                self.assertEqual(verifier.verify_upstream_pins(str(root))["upstream_pins_verified"], 1)
                (root / "d" / "f.md").write_bytes(b"hello!")
                self.assertEqual(code_of(verifier.verify_upstream_pins, str(root)), "UPSTREAM_PIN_BYTES")
                (root / "d" / "f.md").write_bytes(b"jello")
                self.assertEqual(code_of(verifier.verify_upstream_pins, str(root)), "UPSTREAM_PIN_SHA")
                self.assertEqual(code_of(verifier.verify_upstream_pins, ""), "EMPTY_PATH")
                os.symlink(root, Path(td + "-lnk"))
                try:
                    self.assertEqual(code_of(verifier.verify_upstream_pins, td + "-lnk"), "SYMLINK_IN_PATH")
                finally:
                    os.unlink(td + "-lnk")


class Test10CLI(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(verifier.sys, "stdout", out), mock.patch.object(verifier.sys, "stderr", err):
            rc = verifier.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_arg_parser(self):
        A = verifier._parse_cli_args
        self.assertEqual(A([]), {"mode": "default", "target": None, "as_json": False})
        self.assertEqual(A(["--json", "--check", "c.json"]), {"mode": "check", "target": "c.json", "as_json": True})
        self.assertEqual(code_of(A, ["--json", "--json"]), "DUPLICATE_FLAG")
        self.assertEqual(code_of(A, ["--standalone", "--standalone"]), "CONFLICTING_MODE")
        self.assertEqual(code_of(A, ["--check", "a", "--standalone"]), "CONFLICTING_MODE")
        self.assertEqual(code_of(A, ["--check", "a", "--write", "b"]), "CONFLICTING_MODE")
        self.assertEqual(code_of(A, ["--bogus"]), "UNKNOWN_FLAG")
        self.assertEqual(code_of(A, ["--check"]), "MISSING_PATH_ARG")
        self.assertEqual(code_of(A, ["--check", "-x"]), "INVALID_PATH_ARG")
        self.assertEqual(code_of(A, [1]), "INVALID_STR")
        self.assertEqual(code_of(A, ["--check", 1]), "INVALID_STR")

    def test_main_modes(self):
        rc, out, _ = self.run_main(["--standalone"])
        self.assertEqual((rc, out), (0, oracle.canonical_json_bytes(CERT).decode("ascii")))
        rc, _, err = self.run_main(["--bogus"])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(err)["code"], "UNKNOWN_FLAG")
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            rc, out, _ = self.run_main(["--write-spec", str(t / "spec.json")])
            self.assertEqual(rc, 0)
            self.assertTrue(out.startswith("WROTE "))
            self.assertEqual((t / "spec.json").read_bytes(), oracle.canonical_json_bytes(oracle.build_exp_delta_spec()))
            rc, out, _ = self.run_main(["--json", "--write-spec", str(t / "spec2.json")])
            self.assertIs(json.loads(out)["written"], True)
            (t / "res.json").write_bytes(oracle.canonical_json_bytes(oracle.synthetic_results(r_hidden_cross=14, p_adj_cross="1/251")))
            self.assertEqual(self.run_main(["--evaluate-results", str(t / "res.json")])[:2], (0, "EXP_DELTA KILL\n"))
            self.assertEqual(json.loads(self.run_main(["--json", "--evaluate-results", str(t / "res.json")])[1]), {"verdict": "KILL"})
            (t / "d").mkdir()
            (t / "d" / "f").write_bytes(b"x")
            row = {"id": "T", "relpath": "d/f", "bytes": 1, "sha256": oracle.sha256_hex(b"x")}
            with mock.patch.object(oracle, "UPSTREAM_PINS", (row,)):
                self.assertEqual(self.run_main(["--verify-pins", str(t)])[:2], (0, "PINS_OK upstream=1\n"))
                self.assertEqual(json.loads(self.run_main(["--json", "--verify-pins", str(t)])[1])["status"], "PINS_VERIFIED")
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE)):
                rc, out, _ = self.run_main(["--write", str(t / "cert.json")])
                self.assertEqual(rc, 0)
                self.assertIn(CERT["certificate_sha256"], out)
                self.assertEqual((t / "cert.json").read_bytes(), oracle.canonical_json_bytes(CERT))
                rc, out, _ = self.run_main(["--json", "--write", str(t / "cert2.json")])
                self.assertIs(json.loads(out)["written"], True)
                rc, out, _ = self.run_main(["--check", str(t / "cert.json")])
                self.assertEqual((rc, out), (0, f"OK {oracle.TRACK_ID} cert_sha256={CERT['certificate_sha256']}\n"))
                rc, out, _ = self.run_main(["--json"])
                self.assertIs(json.loads(out)["valid"], True)
                rc, out, _ = self.run_main([])
                self.assertTrue(out.startswith("OK "))
                forged = copy.deepcopy(PAYLOAD)
                forged["scope"]["gpu_touch"] = 1
                (t / "forged.json").write_bytes(oracle.canonical_json_bytes(resign(forged)))
                rc, _, err = self.run_main(["--check", str(t / "forged.json")])
                self.assertEqual((rc, json.loads(err)["code"]), (2, "SEC_PAYLOAD_PIN_MISMATCH"))

    def test_frozen_artifacts_and_real_subprocess(self):
        cert_p = _THIS_DIR / oracle.CERT_FILE_NAME
        self.assertEqual(cert_p.read_bytes(), oracle.canonical_json_bytes(CERT))
        self.assertEqual((_THIS_DIR / oracle.SPEC_FILE_NAME).read_bytes(), oracle.canonical_json_bytes(oracle.build_exp_delta_spec()))
        script = str(_THIS_DIR / "verify_s104_kronecker_triple_gate.py")
        proc = subprocess.run([sys.executable, "-I", "-B", script, "--check", str(cert_p)], capture_output=True, text=True, timeout=300, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(CERT["certificate_sha256"], proc.stdout)
        proc = subprocess.run([sys.executable, "-I", "-B", script, "--check", str(_THIS_DIR / "missing.json")], capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(json.loads(proc.stderr)["code"], "IO_OPEN_ERROR")


if __name__ == "__main__":
    unittest.main()
