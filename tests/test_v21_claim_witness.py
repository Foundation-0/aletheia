#!/usr/bin/env python3
"""Assertion-free R5 adversarial test suite for `aletheia.claim_witness`.

Zero bare asserts (immune to python3 -O). Covers:
  - All 6 canonical shared-nullspace escape classes & 6 clean positive controls (0 FP)
  - Exact Z/Q blind-spot tomography invariants
  - All 3 executable pillars (edge cases, exact boundaries, non-mutation)
  - Full Zone-B hostile input battery (surrogates, 10**5000, deep/cyclic trees,
    non-ASCII HMAC, subclasses, lying containers, symlinks, CRLF, dup keys, floats)
  - Certificate verification tamper controls and CLI modes
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
import ctypes
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia import claim_witness as cwc


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(f"R5_CHECK_FAILED: {msg}")


def _expect_error(code: str, fn: object, *args: object, **kwargs: object) -> None:
    if not callable(fn):
        raise RuntimeError("R5_HARNESS_ERROR: fn must be callable")
    try:
        fn(*args, **kwargs)
    except cwc.ClaimWitnessError as exc:
        if exc.code != code:
            raise RuntimeError(f"Expected error code {code}, got {exc.code} ({exc.detail})") from exc
        return
    raise RuntimeError(f"Expected ClaimWitnessError({code}), but call succeeded")


class _IntSub(int):
    pass


class _StrSub(str):
    pass


class _DictSub(dict):
    pass


class _ListSub(list):
    pass


class _FracSub(Fraction):
    pass


class _EvilPath(type(Path())):
    pass


class _LyingSeq(Sequence):
    def __getitem__(self, idx: int) -> int:
        return 1

    def __len__(self) -> int:
        return 1


class _LyingMap(Mapping):
    def __getitem__(self, key: str) -> int:
        return 1

    def __iter__(self):
        return iter(("a",))

    def __len__(self) -> int:
        return 1


class TestZoneBStrictIO(unittest.TestCase):
    def test_constants_and_scalar_guards(self) -> None:
        _check(cwc.MAX_JSON_DEPTH == 64, "MAX_JSON_DEPTH")
        _check(cwc.MAX_JSON_BYTES == 2_000_000, "MAX_JSON_BYTES")
        _check(cwc.MAX_INT_BITS == 2048, "MAX_INT_BITS")
        _check(cwc.MAX_INT_DIGITS == 620, "MAX_INT_DIGITS")
        _check(cwc.SCHEMA_VERSION == "aletheia.claim_witness.v1", "SCHEMA_VERSION")
        _check(cwc.COMPONENT_ID == "aletheia-v21-claim-witness", "COMPONENT_ID")

        _check(cwc.require_str("", "s") == "", "empty str allowed by default")
        _check(cwc.require_str("ok", "s", non_empty=True) == "ok", "non-empty str")
        _expect_error("EMPTY_STR", cwc.require_str, "", "s", non_empty=True)
        _expect_error("INVALID_STR_TYPE", cwc.require_str, _StrSub("a"), "s")
        _expect_error("INVALID_STR_TYPE", cwc.require_str, 123, "s")
        _expect_error("INVALID_UTF8_SURROGATE", cwc.require_str, chr(0xD800), "s")

        _check(cwc.require_bool(True, "b") is True, "bool True")
        _check(cwc.require_bool(False, "b") is False, "bool False")
        _expect_error("INVALID_BOOL_TYPE", cwc.require_bool, 1, "b")
        _expect_error("INVALID_BOOL_TYPE", cwc.require_bool, "true", "b")

        max_ok = (1 << 2048) - 1
        _check(cwc.require_int(max_ok, "n") == max_ok, "2048-bit int boundary ok")
        _check(cwc.require_int(-max_ok, "n") == -max_ok, "-2048-bit int boundary ok")
        _expect_error("INT_BIT_LIMIT_EXCEEDED", cwc.require_int, 1 << 2048, "n")
        _expect_error("INT_BIT_LIMIT_EXCEEDED", cwc.require_int, 10**5000, "huge")
        _expect_error("INT_BIT_LIMIT_EXCEEDED", cwc.require_int, -(10**5000), "neg_huge")
        _expect_error("INVALID_INT_TYPE", cwc.require_int, True, "flag")
        _expect_error("INVALID_INT_TYPE", cwc.require_int, _IntSub(1), "sub")
        _check(cwc.require_int(5, "n", min_value=5, max_value=5) == 5, "min/max exact")
        _expect_error("INT_BELOW_MIN", cwc.require_int, 4, "n", min_value=5)
        _expect_error("INT_ABOVE_MAX", cwc.require_int, 6, "n", max_value=5)

    def test_exact_fractions_and_hex64(self) -> None:
        _check(cwc.require_exact_fraction(-3, "q") == Fraction(-3, 1), "int frac")
        _check(cwc.require_exact_fraction(Fraction(6, 8), "q") == Fraction(3, 4), "Fraction")
        _check(cwc.require_exact_fraction("-7/4", "q") == Fraction(-7, 4), "str frac")
        _check(cwc.require_exact_fraction("0" * 619 + "1", "q") == Fraction(1, 1), "620 digits ok")
        _expect_error("INT_BIT_LIMIT_EXCEEDED", cwc.require_exact_fraction, "9" * 620, "q")
        _check(cwc.fmt_q(Fraction(5, 1)) == "5", "fmt_q int")
        _check(cwc.fmt_q(Fraction(3, 4)) == "3/4", "fmt_q frac")

        _expect_error("INVALID_FRACTION_TYPE", cwc.require_exact_fraction, json.loads("1.5"), "q")
        _expect_error("INVALID_FRACTION_TYPE", cwc.require_exact_fraction, True, "q")
        _expect_error("INVALID_FRACTION_TYPE", cwc.require_exact_fraction, _FracSub(1, 2), "q")
        _expect_error("INT_BIT_LIMIT_EXCEEDED", cwc.require_exact_fraction, Fraction(10**5000, 1), "q")
        _expect_error("INT_BIT_LIMIT_EXCEEDED", cwc.require_exact_fraction, Fraction(1, 10**5000), "q")
        _expect_error("INT_BIT_LIMIT_EXCEEDED", cwc.fmt_q, Fraction(10**5000, 1))
        _expect_error("INVALID_INT_LITERAL", cwc.require_exact_fraction, "", "q")
        _expect_error("INVALID_INT_LITERAL", cwc.require_exact_fraction, "-", "q")
        _expect_error("INVALID_INT_LITERAL", cwc.require_exact_fraction, "\u0661", "q")
        _expect_error("INVALID_INT_LITERAL", cwc.require_exact_fraction, " 1", "q")
        _expect_error("INT_DIGIT_LIMIT_EXCEEDED", cwc.require_exact_fraction, "9" * 621, "q")
        _expect_error("NON_POSITIVE_DENOMINATOR", cwc.require_exact_fraction, "1/0", "q")
        _expect_error("NON_POSITIVE_DENOMINATOR", cwc.require_exact_fraction, "1/-2", "q")
        _expect_error("INVALID_FRACTION_STR", cwc.require_exact_fraction, "1/2/3", "q")

        good_a = "0123456789abcdef" * 4
        good_b = "f" + good_a[1:]
        _check(cwc.constant_time_hex64_equal(good_a, good_a), "hex64 equal")
        _check(not cwc.constant_time_hex64_equal(good_a, good_b), "hex64 not equal")
        _expect_error("INVALID_HEX64_LEN", cwc.require_hex64_ascii, "a" * 63, "h")
        _expect_error("INVALID_HEX64_LEN", cwc.require_hex64_ascii, "a" * 65, "h")
        _expect_error("INVALID_HEX64_CHAR", cwc.require_hex64_ascii, "A" * 64, "h")
        _expect_error("INVALID_HEX64_CHAR", cwc.require_hex64_ascii, "a" * 63 + "\n", "h")
        _expect_error("INVALID_HEX64_CHAR", cwc.constant_time_hex64_equal, "\u00e9" * 64, good_a)
        _expect_error("INVALID_UTF8_SURROGATE", cwc.constant_time_hex64_equal, good_a, chr(0xD800) * 64)

    def test_containers_json_depth_and_paths(self) -> None:
        _check(cwc.require_exact_dict({"a": 1}, "d") == {"a": 1}, "dict ok")
        _expect_error("INVALID_DICT_TYPE", cwc.require_exact_dict, _DictSub({"a": 1}), "d")
        _expect_error("INVALID_DICT_TYPE", cwc.require_exact_dict, _LyingMap(), "d")
        _expect_error("INVALID_STR_TYPE", cwc.require_exact_dict, {1: "a"}, "d")
        _expect_error("INVALID_UTF8_SURROGATE", cwc.require_exact_dict, {chr(0xD800): 1}, "d")

        _check(cwc.require_exact_list([], "l") == [], "empty list ok")
        _expect_error("EMPTY_LIST", cwc.require_exact_list, [], "l", non_empty=True)
        _expect_error("INVALID_LIST_TYPE", cwc.require_exact_list, _ListSub([1]), "l")
        _expect_error("INVALID_LIST_TYPE", cwc.require_exact_list, _LyingSeq(), "l")

        _expect_error("INT_BELOW_MIN", cwc.validate_json_value, {}, max_depth=0)
        _expect_error("INT_ABOVE_MAX", cwc.validate_json_value, {}, max_depth=65)
        cwc.validate_json_value([1], max_depth=1)
        _expect_error("JSON_DEPTH_EXCEEDED", cwc.validate_json_value, [[1]], max_depth=1)

        d64: object = 0
        for _ in range(64):
            d64 = [d64]
        cwc.validate_json_value(d64)
        _expect_error("JSON_DEPTH_EXCEEDED", cwc.validate_json_value, [d64])

        deep1500: object = 0
        for _ in range(1500):
            deep1500 = [deep1500]
        _expect_error("JSON_DEPTH_EXCEEDED", cwc.validate_json_value, deep1500)

        cyc_list: list[object] = []
        cyc_list.append(cyc_list)
        _expect_error("JSON_DEPTH_EXCEEDED", cwc.validate_json_value, cyc_list)

        cyc_dict: dict[str, object] = {}
        cyc_dict["self"] = cyc_dict
        _expect_error("JSON_DEPTH_EXCEEDED", cwc.validate_json_value, cyc_dict)

        cwc.validate_json_value({"n": None, "b": True, "i": 1, "s": "ok", "l": [1]})
        _expect_error("UNSUPPORTED_JSON_TYPE", cwc.validate_json_value, json.loads("1.5"))
        _expect_error("UNSUPPORTED_JSON_TYPE", cwc.validate_json_value, (1, 2))
        _expect_error("UNSUPPORTED_JSON_TYPE", cwc.validate_json_value, {"a": _IntSub(1)})
        _expect_error("INVALID_UTF8_SURROGATE", cwc.validate_json_value, {chr(0xD800): 1})
        _expect_error("INVALID_UTF8_SURROGATE", cwc.validate_json_value, {"a": chr(0xD800)})

        _check(cwc.canonical_json_bytes({"b": 1, "a": "\u00e9"}) == b'{"a":"\\u00e9","b":1}', "canonical")
        _check(cwc.parse_strict_json_text('{"a":1}', max_bytes=7) == {"a": 1}, "exact max_bytes")
        _expect_error("JSON_TOO_LARGE", cwc.parse_strict_json_text, '{"a":12}', max_bytes=7)
        _expect_error("JSON_DUPLICATE_KEY", cwc.parse_strict_json_text, '{"a":1,"a":2}')
        _expect_error("JSON_FLOAT_FORBIDDEN", cwc.parse_strict_json_text, '{"x":1.5}')
        _expect_error("JSON_CONSTANT_FORBIDDEN", cwc.parse_strict_json_text, '{"x":NaN}')
        _expect_error("INT_DIGIT_LIMIT_EXCEEDED", cwc.parse_strict_json_text, '{"n":' + ("9" * 5000) + "}")
        _expect_error("INVALID_UTF8_SURROGATE", cwc.parse_strict_json_text, '{"s":"\\ud800"}')
        _expect_error("INVALID_UTF8_SURROGATE", cwc.parse_strict_json_text, '{"\\ud800":1}')
        _expect_error("JSON_SYNTAX_ERROR", cwc.parse_strict_json_text, "{bad")
        _expect_error("JSON_ROOT_NOT_OBJECT", cwc.parse_strict_json_text, "[1]", require_object=True)
        _check(cwc.parse_strict_json_text("[1]", require_object=False) == [1], "non-object json ok")

        _expect_error("INVALID_PATH_TYPE", cwc.require_no_symlink_path, "not_a_path")
        _expect_error("INVALID_PATH_TYPE", cwc.require_no_symlink_path, _EvilPath("a.json"))
        _expect_error("INVALID_PATH_NUL", cwc.require_no_symlink_path, Path("a\x00b"))
        _expect_error("INVALID_UTF8_SURROGATE", cwc.require_no_symlink_path, Path(chr(0xD800)))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good_f = root / "good.json"
            good_f.write_bytes(b'{"a":1}\n')
            raw, text = cwc.read_strict_utf8_file(good_f, max_bytes=8)
            _check(raw == b'{"a":1}\n' and text == '{"a":1}\n', "exact file max_bytes ok")
            _expect_error("FILE_TOO_LARGE", cwc.read_strict_utf8_file, good_f, max_bytes=7)

            _expect_error("FILE_NOT_FOUND", cwc.read_strict_utf8_file, root / "missing.json")
            _expect_error("FILE_NOT_FOUND", cwc.read_strict_utf8_file, root)

            crlf_f = root / "crlf.json"
            crlf_f.write_bytes(b'{"a":1}\r\n')
            _expect_error("CR_LINE_ENDINGS_FORBIDDEN", cwc.read_strict_utf8_file, crlf_f)

            bad_utf8 = root / "bad.bin"
            bad_utf8.write_bytes(b"\xff\xfe")
            _expect_error("INVALID_UTF8", cwc.read_strict_utf8_file, bad_utf8)

            sym_f = root / "sym.json"
            sym_f.symlink_to(good_f)
            _expect_error("SYMLINK_FORBIDDEN", cwc.read_strict_utf8_file, sym_f)

            real_dir = root / "real_dir"
            real_dir.mkdir()
            inner_f = real_dir / "inner.json"
            inner_f.write_bytes(b"{}")
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(real_dir, target_is_directory=True)
            _expect_error("SYMLINK_ANCESTOR_FORBIDDEN", cwc.read_strict_utf8_file, sym_dir / "inner.json")


class TestThreePillarsUnitAndBoundary(unittest.TestCase):
    def test_pillar1_all_kinds_and_boundaries(self) -> None:
        _expect_error("EMPTY_LIST", cwc.verify_prose_artifact_bindings, [])
        _expect_error("UNKNOWN_BINDING_KIND", cwc.verify_prose_artifact_bindings, [{"kind": "nope"}])

        res = cwc.verify_prose_artifact_bindings([
            {
                "id": "dense_packed_with_bitmap",
                "kind": "slot_packing_bpw",
                "n_values": 1024,
                "kept_values": 64,
                "kept_bits_per_val": 16,
                "rest_block_size": 8,
                "rest_bits_per_block": 28,
                "scale_group_size": 128,
                "scale_bits_per_slot": 16,
                "extra_header_bits": 64,
                "claimed_bpw": "4576/1024",
            },
            {
                "id": "ceil_boundary_n1025",
                "kind": "slot_packing_bpw",
                "n_values": 1025,
                "kept_values": 1,
                "kept_bits_per_val": 16,
                "rest_block_size": 8,
                "rest_bits_per_block": 28,
                "scale_group_size": 128,
                "scale_bits_per_slot": 16,
                "claimed_bpw": str(Fraction(16 + 128 * 28 + 9 * 16, 1025)),
            },
            {
                "id": "ceil_boundary_n1023",
                "kind": "slot_packing_bpw",
                "n_values": 1023,
                "kept_values": 7,
                "kept_bits_per_val": 16,
                "rest_block_size": 8,
                "rest_bits_per_block": 28,
                "scale_group_size": 128,
                "scale_bits_per_slot": 16,
                "claimed_bpw": str(Fraction(7 * 16 + 127 * 28 + 8 * 16, 1023)),
            },
        ])
        _check(res["passed"] and res["checked_count"] == 3 and res["failed_count"] == 0, "slot boundaries")
        _check(res["results"][1]["allocated_scale_slots"] == 9, "1025 -> 9 slots")
        _check(res["results"][2]["allocated_scale_slots"] == 8, "1023 -> 8 slots")

        _expect_error(
            "NON_DIVISIBLE_REST_BLOCK",
            cwc.verify_prose_artifact_bindings,
            [{
                "id": "bad_div",
                "kind": "slot_packing_bpw",
                "n_values": 10,
                "kept_values": 1,
                "kept_bits_per_val": 16,
                "rest_block_size": 8,
                "rest_bits_per_block": 28,
                "scale_group_size": 128,
                "scale_bits_per_slot": 16,
                "claimed_bpw": "1",
            }],
        )

        rng = cwc.verify_prose_artifact_bindings([
            {
                "id": "cnt_bad",
                "kind": "integer_range_binding",
                "claimed_count": 35,
                "claimed_min": 9,
                "claimed_max": 197,
                "artifact_count": 34,
                "artifact_min": 9,
                "artifact_max": 197,
            },
            {
                "id": "min_bad",
                "kind": "integer_range_binding",
                "claimed_count": 34,
                "claimed_min": 10,
                "claimed_max": 197,
                "artifact_count": 34,
                "artifact_min": 9,
                "artifact_max": 197,
            },
            {
                "id": "max_bad",
                "kind": "integer_range_binding",
                "claimed_count": 34,
                "claimed_min": 9,
                "claimed_max": 198,
                "artifact_count": 34,
                "artifact_min": 9,
                "artifact_max": 197,
            },
        ])
        _check(not rng["passed"] and rng["failed_count"] == 3, "range 3 failures")
        _check(rng["results"][0]["reasons"] == ["PROSE_COUNT_MISMATCH"], "count only")
        _check(rng["results"][1]["reasons"] == ["PROSE_RANGE_MISMATCH"], "min only")
        _check(rng["results"][2]["reasons"] == ["PROSE_RANGE_MISMATCH"], "max only")

        c_ok = cwc.verify_prose_artifact_bindings([{
            "id": "exact_l1_boundary",
            "kind": "c_allocation_table",
            "claimed_hot_bytes": 32768,
            "claimed_cache_limit_bytes": 32768,
            "claimed_fits_cache": True,
            "allocated_arrays": [
                {"name": "hot", "bytes": 32768, "hot_read": True},
                {"name": "cold", "bytes": 4096, "hot_read": False},
            ],
        }])
        _check(c_ok["passed"], "exact cache boundary fits")
        _check(c_ok["results"][0]["actual_total_bytes"] == 36864, "cold bytes counted in total")
        _check(c_ok["results"][0]["actual_fits_cache"] is True, "exact <= limit")

        c_fail_iso = cwc.verify_prose_artifact_bindings([
            {
                "id": "hot_only_mismatch",
                "kind": "c_allocation_table",
                "claimed_hot_bytes": 100,
                "allocated_arrays": [{"name": "a", "bytes": 200, "hot_read": True}],
            },
            {
                "id": "cache_fit_only_mismatch",
                "kind": "c_allocation_table",
                "claimed_hot_bytes": 34050,
                "claimed_cache_limit_bytes": 32768,
                "claimed_fits_cache": True,
                "allocated_arrays": [{"name": "a", "bytes": 34050, "hot_read": True}],
            },
        ])
        _check(not c_fail_iso["passed"] and c_fail_iso["failed_count"] == 2, "isolated C table failures")
        _check(c_fail_iso["results"][0]["reasons"] == ["C_HOT_FOOTPRINT_MISMATCH"], "hot mismatch only")
        _check(c_fail_iso["results"][1]["reasons"] == ["CACHE_FIT_CLAIM_MISMATCH"], "cache fit mismatch only")

        _expect_error(
            "DUPLICATE_ARRAY_NAME",
            cwc.verify_prose_artifact_bindings,
            [{
                "id": "dup_arr",
                "kind": "c_allocation_table",
                "claimed_hot_bytes": 20,
                "allocated_arrays": [
                    {"name": "a", "bytes": 10, "hot_read": True},
                    {"name": "a", "bytes": 10, "hot_read": True},
                ],
            }],
        )
        _expect_error(
            "INVALID_BOOL_TYPE",
            cwc.verify_prose_artifact_bindings,
            [{
                "id": "half_cache_keys",
                "kind": "c_allocation_table",
                "claimed_hot_bytes": 10,
                "claimed_cache_limit_bytes": 32,
                "allocated_arrays": [{"name": "a", "bytes": 10, "hot_read": True}],
            }],
        )
        _expect_error(
            "INVALID_INT_TYPE",
            cwc.verify_prose_artifact_bindings,
            [{
                "id": "half_cache_keys_2",
                "kind": "c_allocation_table",
                "claimed_hot_bytes": 10,
                "claimed_fits_cache": True,
                "allocated_arrays": [{"name": "a", "bytes": 10, "hot_read": True}],
            }],
        )

        inv = cwc.verify_prose_artifact_bindings([{
            "id": "exact_16_non_ws",
            "kind": "prose_invariant_binding",
            "rule": "min_non_whitespace_chars",
            "threshold": 16,
            "sample_input": "a" * 16 + "   ",
            "code_admitted": True,
        }])
        _check(inv["passed"] and inv["results"][0]["non_whitespace_chars"] == 16, "exact threshold")
        _expect_error(
            "UNKNOWN_INVARIANT_RULE",
            cwc.verify_prose_artifact_bindings,
            [{
                "id": "bad_rule",
                "kind": "prose_invariant_binding",
                "rule": "other",
                "threshold": 1,
                "sample_input": "a",
                "code_admitted": True,
            }],
        )

    def test_pillar2_all_kinds_and_branches(self) -> None:
        _expect_error("EMPTY_LIST", cwc.verify_provenance_claims, [])
        _expect_error("UNKNOWN_PROVENANCE_KIND", cwc.verify_provenance_claims, [{"kind": "nope"}])

        op_res = cwc.verify_provenance_claims([
            {
                "id": "valid_exact",
                "kind": "operator_equivalence",
                "claimed_operator": "SiLU",
                "claimed_provenance": "exact_operator",
                "witness_operator": "SiLU",
                "witness_provenance": "exact_operator",
                "claims_gradient_coverage": True,
                "witness_has_gradient_coverage": True,
                "claims_causal_impossibility": False,
                "witness_proves_only_distributional_symmetry": False,
            },
            {
                "id": "valid_surrogate_matched",
                "kind": "operator_equivalence",
                "claimed_operator": "rational_silu",
                "claimed_provenance": "surrogate_operator",
                "witness_operator": "rational_silu",
                "witness_provenance": "surrogate_operator",
                "claims_gradient_coverage": False,
                "witness_has_gradient_coverage": False,
                "claims_causal_impossibility": True,
                "witness_proves_only_distributional_symmetry": False,
            },
            {
                "id": "fail_surrogate_op_mismatch",
                "kind": "operator_equivalence",
                "claimed_operator": "rational_silu_rmslike",
                "claimed_provenance": "surrogate_operator",
                "witness_operator": "piecewise_linear_relu",
                "witness_provenance": "surrogate_operator",
                "claims_gradient_coverage": True,
                "witness_has_gradient_coverage": True,
                "claims_causal_impossibility": False,
                "witness_proves_only_distributional_symmetry": True,
            },
            {
                "id": "fail_surrogate_vs_exact_mismatch",
                "kind": "operator_equivalence",
                "claimed_operator": "rational_silu_rmslike",
                "claimed_provenance": "surrogate_operator",
                "witness_operator": "GELU",
                "witness_provenance": "exact_operator",
                "claims_gradient_coverage": True,
                "witness_has_gradient_coverage": True,
                "claims_causal_impossibility": False,
                "witness_proves_only_distributional_symmetry": True,
            },
            {
                "id": "fail_op_name_only",
                "kind": "operator_equivalence",
                "claimed_operator": "RMSNorm",
                "claimed_provenance": "exact_operator",
                "witness_operator": "LayerNorm",
                "witness_provenance": "exact_operator",
                "claims_gradient_coverage": False,
                "witness_has_gradient_coverage": True,
                "claims_causal_impossibility": False,
                "witness_proves_only_distributional_symmetry": True,
            },
            {
                "id": "fail_grad_only",
                "kind": "operator_equivalence",
                "claimed_operator": "rational_silu",
                "claimed_provenance": "surrogate_operator",
                "witness_operator": "rational_silu",
                "witness_provenance": "surrogate_operator",
                "claims_gradient_coverage": True,
                "witness_has_gradient_coverage": False,
                "claims_causal_impossibility": False,
                "witness_proves_only_distributional_symmetry": True,
            },
            {
                "id": "fail_causal_only",
                "kind": "operator_equivalence",
                "claimed_operator": "rational_silu",
                "claimed_provenance": "surrogate_operator",
                "witness_operator": "rational_silu",
                "witness_provenance": "surrogate_operator",
                "claims_gradient_coverage": False,
                "witness_has_gradient_coverage": False,
                "claims_causal_impossibility": True,
                "witness_proves_only_distributional_symmetry": True,
            },
        ])
        _check(not op_res["passed"] and op_res["failed_count"] == 5, "5 op failures")
        _check(op_res["results"][0]["passed"] and op_res["results"][1]["passed"], "2 op passes")
        _check(op_res["results"][2]["reasons"] == ["OPERATOR_IDENTITY_MISMATCH"], "surrogate op mismatch")
        _check(op_res["results"][3]["reasons"] == ["OPERATOR_IDENTITY_MISMATCH"], "surrogate vs exact mismatch")
        _check(op_res["results"][4]["reasons"] == ["OPERATOR_IDENTITY_MISMATCH"], "op name")
        _check(op_res["results"][5]["reasons"] == ["UNVERIFIED_GRADIENT_COVERAGE"], "grad only")
        _check(op_res["results"][6]["reasons"] == ["DISTRIBUTIONAL_OVERCLAIMED_AS_CAUSAL"], "causal only")

        _expect_error(
            "UNKNOWN_OPERATOR_PROVENANCE",
            cwc.verify_provenance_claims,
            [{
                "id": "x",
                "kind": "operator_equivalence",
                "claimed_operator": "A",
                "claimed_provenance": "bogus",
                "witness_operator": "A",
                "witness_provenance": "exact_operator",
                "claims_gradient_coverage": False,
                "witness_has_gradient_coverage": False,
                "claims_causal_impossibility": False,
                "witness_proves_only_distributional_symmetry": False,
            }],
        )
        _expect_error(
            "UNKNOWN_OPERATOR_PROVENANCE",
            cwc.verify_provenance_claims,
            [{
                "id": "x",
                "kind": "operator_equivalence",
                "claimed_operator": "A",
                "claimed_provenance": "exact_operator",
                "witness_operator": "A",
                "witness_provenance": "bogus",
                "claims_gradient_coverage": False,
                "witness_has_gradient_coverage": False,
                "claims_causal_impossibility": False,
                "witness_proves_only_distributional_symmetry": False,
            }],
        )

        met_res = cwc.verify_provenance_claims([
            {
                "id": "valid_direct",
                "kind": "metric_attribution",
                "claimed_subject": "E8_Had",
                "measured_subject": "E8_Had",
                "claimed_provenance": "same_experiment_measurement",
                "witness_provenance": "same_experiment_measurement",
                "experiment_executed_for_claimed_subject": True,
            },
            {
                "id": "valid_unmeasured",
                "kind": "metric_attribution",
                "claimed_subject": "E8_Had",
                "measured_subject": "E8_std",
                "claimed_provenance": "unmeasured_hypothesis",
                "witness_provenance": "unmeasured_hypothesis",
                "experiment_executed_for_claimed_subject": False,
            },
            {
                "id": "fail_prov_only",
                "kind": "metric_attribution",
                "claimed_subject": "E8_Had",
                "measured_subject": "E8_Had",
                "claimed_provenance": "same_experiment_measurement",
                "witness_provenance": "cross_experiment_anchor",
                "experiment_executed_for_claimed_subject": True,
            },
            {
                "id": "fail_subj_only",
                "kind": "metric_attribution",
                "claimed_subject": "E8_Had",
                "measured_subject": "E8_std",
                "claimed_provenance": "same_experiment_measurement",
                "witness_provenance": "same_experiment_measurement",
                "experiment_executed_for_claimed_subject": True,
            },
            {
                "id": "fail_not_exec_only",
                "kind": "metric_attribution",
                "claimed_subject": "E8_Had",
                "measured_subject": "E8_Had",
                "claimed_provenance": "same_experiment_measurement",
                "witness_provenance": "same_experiment_measurement",
                "experiment_executed_for_claimed_subject": False,
            },
            {
                "id": "fail_hyp_overclaim",
                "kind": "metric_attribution",
                "claimed_subject": "E8_Had",
                "measured_subject": "E8_std",
                "claimed_provenance": "cross_experiment_anchor",
                "witness_provenance": "unmeasured_hypothesis",
                "experiment_executed_for_claimed_subject": False,
            },
        ])
        _check(met_res["results"][0]["passed"] and met_res["results"][1]["passed"], "2 metric passes")
        for idx in (2, 3, 4):
            _check(met_res["results"][idx]["reasons"] == ["CROSS_EXPERIMENT_ATTRIBUTION_SMUGGLING"], f"disjunct {idx}")
        _check(met_res["results"][5]["reasons"] == ["UNMEASURED_HYPOTHESIS_OVERCLAIM"], "hyp overclaim")

        _expect_error(
            "UNKNOWN_METRIC_PROVENANCE",
            cwc.verify_provenance_claims,
            [{
                "id": "m",
                "kind": "metric_attribution",
                "claimed_subject": "A",
                "measured_subject": "A",
                "claimed_provenance": "bogus",
                "witness_provenance": "cross_experiment_anchor",
                "experiment_executed_for_claimed_subject": False,
            }],
        )
        _expect_error(
            "UNKNOWN_METRIC_PROVENANCE",
            cwc.verify_provenance_claims,
            [{
                "id": "m",
                "kind": "metric_attribution",
                "claimed_subject": "A",
                "measured_subject": "A",
                "claimed_provenance": "cross_experiment_anchor",
                "witness_provenance": "bogus",
                "experiment_executed_for_claimed_subject": False,
            }],
        )

        sp = cwc.verify_provenance_claims([{
            "id": "non_exact_ok",
            "kind": "spec_completeness",
            "required_clauses": ["c1", "c2"],
            "implemented_clauses": ["c1"],
            "claimed_exact_spec_equivalence": False,
        }])
        _check(sp["passed"] and sp["results"][0]["missing_clauses"] == ["c2"], "non-exact ok")
        _expect_error(
            "DUPLICATE_SPEC_CLAUSE",
            cwc.verify_provenance_claims,
            [{
                "id": "dup_spec",
                "kind": "spec_completeness",
                "required_clauses": ["c1", "c1"],
                "implemented_clauses": [],
                "claimed_exact_spec_equivalence": True,
            }],
        )

        ds = cwc.verify_provenance_claims([{
            "id": "lower_scope_ok",
            "kind": "delivery_scope",
            "claimed_scope_tier": "research_prototype",
            "witnessed_scope_tier": "production_deployment",
        }])
        _check(ds["passed"] and ds["results"][0]["claimed_rank"] == 1, "lower rank ok")
        _expect_error(
            "UNKNOWN_SCOPE_TIER",
            cwc.verify_provenance_claims,
            [{
                "id": "s1",
                "kind": "delivery_scope",
                "claimed_scope_tier": "bogus",
                "witnessed_scope_tier": "research_prototype",
            }],
        )
        _expect_error(
            "UNKNOWN_SCOPE_TIER",
            cwc.verify_provenance_claims,
            [{
                "id": "s2",
                "kind": "delivery_scope",
                "claimed_scope_tier": "research_prototype",
                "witnessed_scope_tier": "bogus",
            }],
        )

    def test_pillar3_semantic_destruction_gate_all_ops(self) -> None:
        base = {
            "meta": {"count": 5, "map": {"k": 1}, "items": [{"ok": True}]},
            "zero_sha": "0" * 64,
            "hex_sha": "a" * 64,
        }
        snapshot = copy.deepcopy(base)

        def strict_v(w: dict) -> bool:
            if w["zero_sha"] != "0" * 64 or w["hex_sha"] != "a" * 64:
                return False
            m = w["meta"]
            if m["count"] != 5 or m["map"] != {"k": 1}:
                return False
            if m["items"] != [{"ok": True}]:
                raise RuntimeError("invalid items")
            return True

        perts = [
            {"id": "p_empty", "op": "empty_mapping_field", "path": ["meta", "map"]},
            {"id": "p_list", "op": "replace_list_with_arbitrary_dict", "path": ["meta", "items"]},
            {"id": "p_drop", "op": "drop_required_field", "path": ["meta", "map"]},
            {"id": "p_hash0", "op": "corrupt_pinned_hash", "path": ["zero_sha"]},
            {"id": "p_hasha", "op": "corrupt_pinned_hash", "path": ["hex_sha"]},
            {"id": "p_num", "op": "invert_numeric_claim", "path": ["meta", "count"]},
        ]
        gate = cwc.run_semantic_destruction_gate(strict_v, base, perts)
        _check(gate["passed"] and gate["verdict"] == "STRICT_SEMANTIC_VERIFIER", "strict passes all 6 ops")
        _check(gate["perturbations_tested"] == 6 and gate["hollow_survivals"] == 0, "6 tested, 0 survived")
        _check(base == snapshot, "valid_witness not mutated in place")

        rej = cwc.run_semantic_destruction_gate(lambda _w: False, base, perts[:1])
        _check(not rej["passed"] and rej["verdict"] == "VALID_WITNESS_REJECTED", "rejects always-false verifier")

        _expect_error("VERIFIER_NOT_CALLABLE", cwc.run_semantic_destruction_gate, "nope", base, perts[:1])
        _expect_error(
            "INVALID_VERIFIER_RETURN_TYPE",
            cwc.run_semantic_destruction_gate,
            lambda _w: 1,
            base,
            perts[:1],
        )
        _expect_error(
            "DESTRUCTION_PATH_MISSING",
            cwc.run_semantic_destruction_gate,
            strict_v,
            base,
            [{"id": "e1", "op": "drop_required_field", "path": ["nope", "x"]}],
        )
        _expect_error(
            "DESTRUCTION_PATH_MISSING",
            cwc.run_semantic_destruction_gate,
            lambda _w: True,
            {"a": ["b"]},
            [{"id": "e1b", "op": "drop_required_field", "path": ["a", "b", "c"]}],
        )
        _expect_error(
            "DESTRUCTION_PARENT_NOT_DICT",
            cwc.run_semantic_destruction_gate,
            lambda _w: True,
            {"a": [1]},
            [{"id": "e2", "op": "drop_required_field", "path": ["a", "x"]}],
        )
        _expect_error(
            "DESTRUCTION_LEAF_MISSING",
            cwc.run_semantic_destruction_gate,
            strict_v,
            base,
            [{"id": "e3", "op": "drop_required_field", "path": ["meta", "missing"]}],
        )
        _expect_error(
            "TARGET_NOT_NONEMPTY_DICT",
            cwc.run_semantic_destruction_gate,
            lambda _w: True,
            {"m": {}},
            [{"id": "e4", "op": "empty_mapping_field", "path": ["m"]}],
        )
        _expect_error(
            "TARGET_NOT_NONEMPTY_DICT",
            cwc.run_semantic_destruction_gate,
            lambda _w: True,
            {"m": 1},
            [{"id": "e4b", "op": "empty_mapping_field", "path": ["m"]}],
        )
        _expect_error(
            "TARGET_NOT_NONEMPTY_LIST",
            cwc.run_semantic_destruction_gate,
            lambda _w: True,
            {"l": []},
            [{"id": "e5", "op": "replace_list_with_arbitrary_dict", "path": ["l"]}],
        )
        _expect_error(
            "TARGET_NOT_NONEMPTY_LIST",
            cwc.run_semantic_destruction_gate,
            lambda _w: True,
            {"l": {"k": 1}},
            [{"id": "e5b", "op": "replace_list_with_arbitrary_dict", "path": ["l"]}],
        )
        _check(
            not cwc._hollow_fault_verifier({"n_faults": 1, "faults": ({"k": 1},)}),
            "hollow fault verifier requires exact list type",
        )
        _expect_error(
            "UNKNOWN_DESTRUCTION_OP",
            cwc.run_semantic_destruction_gate,
            strict_v,
            base,
            [{"id": "e6", "op": "bogus", "path": ["zero_sha"]}],
        )
        _expect_error(
            "RESIGN_FIELD_MISSING",
            cwc.run_semantic_destruction_gate,
            strict_v,
            base,
            [{"id": "e7", "op": "invert_numeric_claim", "path": ["meta", "count"], "resign_hash_field": "nope"}],
        )

        m0 = cwc._apply_semantic_destruction(base, {"op": "corrupt_pinned_hash", "path": ["zero_sha"]})
        ma = cwc._apply_semantic_destruction(base, {"op": "corrupt_pinned_hash", "path": ["hex_sha"]})
        _check(m0["zero_sha"] == "1" + ("0" * 63), "0 flips to 1")
        _check(ma["hex_sha"] == "0" + ("a" * 63), "a flips to 0")
        mn = cwc._apply_semantic_destruction(base, {"op": "invert_numeric_claim", "path": ["meta", "count"]})
        _check(mn["meta"]["count"] == 6, "count increments by 1")


class TestReferenceEscapesAndTomography(unittest.TestCase):
    def test_all_6_escapes_caught_and_6_positive_controls_pass(self) -> None:
        tomo = cwc.compute_blind_spot_tomography()
        suite = tomo["reference_escape_suite"]

        _check(tomo["verifier_families_count"] == 11, "11 verifier families")
        _check(tomo["baseline_orthogonal_signatures_count"] == 8, "8 baseline signatures")
        _check(tomo["baseline_exclusive_signatures_count"] == 5, "5 exclusive")
        _check(tomo["baseline_exclusive_share_q"] == "5/8", "5/8 exclusive")
        _check(tomo["baseline_max_single_family_sigs"] == 3, "max 3 sigs")
        _check(tomo["baseline_max_single_family_share_q"] == "3/8", "3/8 max single")
        _check(tomo["shared_nullspace_escapes_count"] == 6, "6 escapes")
        _check(tomo["total_corpus_signatures_count"] == 14, "14 total")
        _check(tomo["before_pctw_corpus_recall_q"] == "4/7", "8/14 = 4/7 before")
        _check(tomo["before_pctw_shared_nullspace_share_q"] == "3/7", "6/14 = 3/7 nullspace")
        _check(tomo["after_pctw_escape_recall_q"] == "1", "6/6 escapes caught")
        _check(tomo["after_pctw_positive_specificity_q"] == "1", "6/6 positive controls")
        _check(tomo["after_pctw_false_positive_rate_q"] == "0", "0 false positives")
        _check(tomo["after_pctw_corpus_recall_q"] == "1", "14/14 in-sample recall")
        _check(tomo["corpus_recall_gain_q"] == "3/7", "+3/7 gain")

        pp = tomo["per_pillar_escape_coverage"]
        _check(pp["pillar1_count"] == 4 and pp["pillar1_share_q"] == "2/3", "pillar1 = 4/6")
        _check(pp["pillar2_count"] == 4 and pp["pillar2_share_q"] == "2/3", "pillar2 = 4/6")
        _check(pp["pillar3_count"] == 2 and pp["pillar3_share_q"] == "1/3", "pillar3 = 2/6")

        _check(suite["negative_escapes_caught"] == 6, "6/6 caught")
        _check(suite["positive_controls_passed"] == 6, "6/6 pos pass")
        _check(suite["false_positives"] == 0, "0 FP")

        by_id = {c["escape_id"]: c for c in suite["negative_cases"]}
        _check(by_id["ESC-01"]["evidence"]["pillar1"]["results"][0]["delta_bpw"] == "-1/128", "ESC-01 -1/128 bpw")
        _check(by_id["ESC-01"]["evidence"]["pillar3"]["verdict"] == "HOLLOW_WITNESS_VERIFIER", "ESC-01 hollow")
        _check(by_id["ESC-02"]["evidence"]["pillar1"]["results"][0]["non_whitespace_chars"] == 2, "ESC-02 2 non-ws")
        _check(len(by_id["ESC-02"]["evidence"]["pillar2"]["results"][0]["missing_clauses"]) == 5, "ESC-02 5 clauses")
        _check(by_id["ESC-03"]["evidence"]["pillar1"]["results"][0]["artifact"] == [34, 9, 197], "ESC-03 9..197")
        _check(by_id["ESC-03"]["evidence"]["pillar3"]["verdict"] == "HOLLOW_WITNESS_VERIFIER", "ESC-03 hollow")
        _check(len(by_id["ESC-04"]["evidence"]["pillar2"]["results"][0]["reasons"]) == 4, "ESC-04 4 reasons")
        _check(by_id["ESC-05"]["evidence"]["pillar1"]["results"][0]["omitted_hot_bytes"] == 12056, "ESC-05 12056B")
        _check(by_id["ESC-05"]["evidence"]["pillar1"]["results"][0]["actual_fits_cache"] is False, "ESC-05 L1 False")
        _check(by_id["ESC-05"]["evidence"]["pillar1"]["results"][1]["omitted_hot_bytes"] == 112896, "ESC-05 Z32")
        _check(
            by_id["ESC-06"]["evidence"]["pillar2"]["results"][0]["reasons"]
            == ["CROSS_EXPERIMENT_ATTRIBUTION_SMUGGLING"],
            "ESC-06 smuggling",
        )

        w, pin = cwc._make_neuron_witness()
        sv = cwc._strict_pinned_verifier(pin)
        _check(sv(w) is True, "strict pinned valid")
        bad_self = copy.deepcopy(w)
        bad_self["canonical_sha256"] = "0" * 64
        _check(sv(bad_self) is False, "strict pinned rejects bad self sha")
        bad_pin_only = copy.deepcopy(w)
        bad_pin_only["study"] = "resigned-non-pinned-study"
        bad_pin_only["canonical_sha256"] = cwc.canonical_sha256(
            {k: v for k, v in bad_pin_only.items() if k != "canonical_sha256"}
        )
        _check(sv(bad_pin_only) is False, "strict pinned rejects valid self-hash with wrong pin")
        bad_l15 = copy.deepcopy(w)
        bad_l15["empirical_join"]["layer_joins"]["layer_15"] = 15
        bad_l15_pin = cwc.canonical_sha256({k: v for k, v in bad_l15.items() if k != "canonical_sha256"})
        bad_l15["canonical_sha256"] = bad_l15_pin
        _check(cwc._strict_pinned_verifier(bad_l15_pin)(bad_l15) is False, "strict pinned rejects layer_15!=16")
        bad_l19 = copy.deepcopy(w)
        bad_l19["empirical_join"]["layer_joins"]["layer_19"] = 3
        bad_l19_pin = cwc.canonical_sha256({k: v for k, v in bad_l19.items() if k != "canonical_sha256"})
        bad_l19["canonical_sha256"] = bad_l19_pin
        _check(cwc._strict_pinned_verifier(bad_l19_pin)(bad_l19) is False, "strict pinned rejects layer_19!=4")
        bad_top = copy.deepcopy(w)
        bad_top["empirical_join"]["top40_first_seventh"] = 28
        bad_top_pin = cwc.canonical_sha256({k: v for k, v in bad_top.items() if k != "canonical_sha256"})
        bad_top["canonical_sha256"] = bad_top_pin
        _check(cwc._strict_pinned_verifier(bad_top_pin)(bad_top) is False, "strict pinned rejects top40!=29")

        valid_fault = {"qubit": 1, "pauli": "X", "syndrome_weight": 0, "logical_flip": True}
        _check(
            cwc._strict_fault_verifier({"n_faults": 1, "faults": (valid_fault,)}) is False,
            "non-list tuple with valid fault",
        )
        _check(
            cwc._strict_fault_verifier({"n_faults": 2, "faults": [valid_fault]}) is False,
            "len mismatch with valid fault",
        )
        _check(cwc._strict_fault_verifier({"n_faults": 1, "faults": [1]}) is False, "non-dict item")
        for missing_k in ("qubit", "pauli", "syndrome_weight", "logical_flip"):
            item = {"qubit": 1, "pauli": "X", "syndrome_weight": 0, "logical_flip": True}
            del item[missing_k]
            _check(cwc._strict_fault_verifier({"n_faults": 1, "faults": [item]}) is False, f"miss {missing_k}")
        _check(
            cwc._strict_fault_verifier(
                {"n_faults": 1, "faults": [{"qubit": 1, "pauli": "X", "syndrome_weight": 1, "logical_flip": True}]}
            )
            is False,
            "nonzero syndrome",
        )
        _check(
            cwc._strict_fault_verifier(
                {"n_faults": 1, "faults": [{"qubit": 1, "pauli": "X", "syndrome_weight": 0, "logical_flip": False}]}
            )
            is False,
            "false logical_flip",
        )
        _check(cwc._hollow_fault_verifier({"n_faults": 1, "faults": [{}]}) is False, "hollow empty dict")
        _check(cwc._hollow_fault_verifier({"n_faults": 2, "faults": [{"a": 1}]}) is False, "hollow len")
        _check(cwc._hollow_fault_verifier({"n_faults": 1, "faults": "bad"}) is False, "hollow non-list")
        _check(cwc._hollow_fault_verifier({"n_faults": 1, "faults": [1]}) is False, "hollow non-dict")


class TestCertificateAndCLI(unittest.TestCase):
    def test_certificate_verification_and_tamper_resistance(self) -> None:
        cert = cwc.build_certificate()
        canonical = cwc.canonical_json_bytes(cert)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p_nl = root / "cert_nl.json"
            p_nl.write_bytes(canonical + b"\n")
            v1 = cwc.verify_certificate_file(p_nl)
            _check(v1["valid"] and v1["certificate_sha256"] == cert["certificate_sha256"], "valid with nl")

            p_no_nl = root / "cert_no_nl.json"
            p_no_nl.write_bytes(canonical)
            v2 = cwc.verify_certificate_file(p_no_nl)
            _check(v2["valid"] and v2["payload_sha256"] == cert["payload_sha256"], "valid without nl")

            p_ws = root / "ws.json"
            p_ws.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
            _expect_error("NON_CANONICAL_CERT_BYTES", cwc.verify_certificate_file, p_ws)

            extra = copy.deepcopy(cert)
            extra["extra"] = 1
            p_extra = root / "extra.json"
            p_extra.write_bytes(cwc.canonical_json_bytes(extra) + b"\n")
            _expect_error("CERT_KEYS_MISMATCH", cwc.verify_certificate_file, p_extra)

            bad_psha = copy.deepcopy(cert)
            bad_psha["payload_sha256"] = "0" * 64
            p_psha = root / "bad_psha.json"
            p_psha.write_bytes(cwc.canonical_json_bytes(bad_psha) + b"\n")
            _expect_error("PAYLOAD_SHA_MISMATCH", cwc.verify_certificate_file, p_psha)

            bad_csha = copy.deepcopy(cert)
            bad_csha["certificate_sha256"] = "0" * 64
            p_csha = root / "bad_csha.json"
            p_csha.write_bytes(cwc.canonical_json_bytes(bad_csha) + b"\n")
            _expect_error("CERTIFICATE_SHA_MISMATCH", cwc.verify_certificate_file, p_csha)

            forged_p = copy.deepcopy(cert)
            forged_p["payload"]["shared_nullspace_escapes_count"] = 0
            forged_p["payload_sha256"] = cwc.canonical_sha256(forged_p["payload"])
            body_p = {k: v for k, v in forged_p.items() if k != "certificate_sha256"}
            forged_p["certificate_sha256"] = cwc.canonical_sha256(body_p)
            p_fp = root / "forged_p.json"
            p_fp.write_bytes(cwc.canonical_json_bytes(forged_p) + b"\n")
            _expect_error("PAYLOAD_RECOMPUTATION_MISMATCH", cwc.verify_certificate_file, p_fp)

            forged_h = copy.deepcopy(cert)
            forged_h["novelty_tier"] = "N0"
            body_h = {k: v for k, v in forged_h.items() if k != "certificate_sha256"}
            forged_h["certificate_sha256"] = cwc.canonical_sha256(body_h)
            p_fh = root / "forged_h.json"
            p_fh.write_bytes(cwc.canonical_json_bytes(forged_h) + b"\n")
            _expect_error("CERT_RECOMPUTATION_MISMATCH", cwc.verify_certificate_file, p_fh)

            buf = io.StringIO()
            with patch("sys.stdout", buf):
                rc = cwc.main(["--self-test", "--json"])
            _check(rc == 0 and buf.getvalue().encode("ascii") == canonical + b"\n", "CLI self-test json")

            buf = io.StringIO()
            with patch("sys.stdout", buf):
                rc = cwc.main([])
            _check(rc == 0 and cert["certificate_sha256"] in buf.getvalue(), "CLI default text")

            buf = io.StringIO()
            with patch("sys.stdout", buf):
                rc = cwc.main(["--standalone"])
            _check(rc == 0 and cert["certificate_sha256"] in buf.getvalue(), "CLI standalone text")

            buf = io.StringIO()
            with patch("sys.stdout", buf):
                rc = cwc.main(["--check", str(p_nl), "--json"])
            _check(rc == 0 and json.loads(buf.getvalue())["valid"] is True, "CLI check json")

            buf = io.StringIO()
            with patch("sys.stdout", buf):
                rc = cwc.main(["--check", str(p_nl)])
            _check(rc == 0 and "OK verified" in buf.getvalue(), "CLI check text")

            err_buf = io.StringIO()
            with patch("sys.stderr", err_buf):
                rc = cwc.main(["--check", str(p_fp)])
            _check(rc == 1 and "FAIL PAYLOAD_RECOMPUTATION_MISMATCH" in err_buf.getvalue(), "CLI check fail")

            # F4: CLI catches OSError cleanly alongside ClaimWitnessError
            err_io = io.StringIO()
            with patch.object(cwc, "verify_certificate_file", side_effect=PermissionError("denied")):
                with patch("sys.stderr", err_io):
                    rc_io = cwc.main(["--check", str(p_nl)])
            _check(rc_io == 1 and "FAIL IO_ERROR:" in err_io.getvalue(), "CLI OSError fail")

    def test_r3_atomic_dirfd_streaming_renameat2_and_guards(self) -> None:
        # Typed INVALID_BOUND_TYPE on require_int optional bounds & max_bits
        for bad_b in (True, "1", _IntSub(1)):
            _expect_error("INVALID_BOUND_TYPE", cwc.require_int, 5, "n", min_value=bad_b)
            _expect_error("INVALID_BOUND_TYPE", cwc.require_int, 5, "n", max_value=bad_b)
            _expect_error("INVALID_BOUND_TYPE", cwc.require_int, 5, "n", max_bits=bad_b)
        _expect_error("INVALID_BOUND_TYPE", cwc.require_int, 5, "n", max_bits=0)
        _expect_error("INVALID_BOUND_TYPE", cwc.require_int, 5, "n", max_bits=-1)
        _check(cwc.require_int(1, "n", max_bits=1) == 1, "max_bits=1 boundary ok")
        _expect_error("INVALID_BOOL_TYPE", cwc.parse_strict_json_text, "{}", require_object=1)

        with tempfile.TemporaryDirectory(prefix="cw_r3_io_") as td:
            root = Path(td)
            real_dir = root / "real"
            real_dir.mkdir()
            cert = cwc.build_certificate()
            cert_bytes = cwc.canonical_json_bytes(cert) + b"\n"
            good_f = real_dir / "cert.json"
            good_f.write_bytes(cert_bytes)
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(real_dir, target_is_directory=True)
            sym_f = root / "sym_f.json"
            sym_f.symlink_to(good_f)

            # require_no_symlink_path edge cases & $PWD checks
            cwc.require_no_symlink_path(Path("/"))
            cwc.require_no_symlink_path(root / "no_dir" / "x.json")
            cwc.require_no_symlink_path(root / "missing.json")
            _expect_error("SYMLINK_FORBIDDEN", cwc.require_no_symlink_path, sym_f)
            _expect_error("SYMLINK_ANCESTOR_FORBIDDEN", cwc.require_no_symlink_path, sym_dir / "cert.json")

            orig_cwd = os.getcwd()
            try:
                os.chdir(real_dir)
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("PWD", None)
                    cwc.require_no_symlink_path(Path("."))
                    cwc.require_no_symlink_path(Path("cert.json"))
                    _check(cwc.verify_certificate_file(Path("cert.json"))["valid"], "rel path PWD unset")
                with patch.dict(os.environ, {"PWD": "rel_" + chr(0xDC80)}):
                    cwc.require_no_symlink_path(Path("cert.json"))
                with patch.dict(os.environ, {"PWD": "/tmp/" + chr(0xDC80)}):
                    _expect_error("INVALID_UTF8_SURROGATE", cwc.require_no_symlink_path, Path("cert.json"))
                with patch.dict(os.environ, {"PWD": str(root / "missing_pwd")}):
                    cwc.require_no_symlink_path(Path("cert.json"))
                with patch.dict(os.environ, {"PWD": str(sym_dir)}):
                    _expect_error("SYMLINK_ANCESTOR_FORBIDDEN", cwc.require_no_symlink_path, Path("cert.json"))
                    _expect_error("SYMLINK_ANCESTOR_FORBIDDEN", cwc.read_strict_utf8_file, Path("cert.json"))
                    # Absolute path outside symlink MUST succeed even when $PWD is a symlink
                    cwc.require_no_symlink_path(good_f)
                    _check(cwc.verify_certificate_file(good_f)["valid"], "abs path under sym PWD")
            finally:
                os.chdir(orig_cwd)

            # Live subprocess CLI check under symlink $PWD
            env_sym = dict(os.environ)
            env_sym["PWD"] = str(sym_dir)
            proc_rel = subprocess.run(
                [sys.executable, "-I", "-B", str(CLI_ROOT / "aletheia" / "claim_witness.py"), "--check", "cert.json"],
                cwd=str(real_dir),
                env=env_sym,
                capture_output=True,
                text=True,
                timeout=15,
            )
            _check(proc_rel.returncode == 1 and "SYMLINK_ANCESTOR_FORBIDDEN" in proc_rel.stderr, "CLI sym PWD ref")
            proc_abs = subprocess.run(
                [sys.executable, "-I", "-B", str(CLI_ROOT / "aletheia" / "claim_witness.py"), "--check", str(good_f)],
                cwd=str(real_dir),
                env=env_sym,
                capture_output=True,
                text=True,
                timeout=15,
            )
            _check(proc_abs.returncode == 0, "CLI abs under sym PWD ok")

            # _open_parent_dir_fd boundary & ancestor branches
            _expect_error("FILE_NOT_FOUND", cwc._open_parent_dir_fd, Path("/"))
            _expect_error("FILE_NOT_FOUND", cwc._open_parent_dir_fd, real_dir / "..")
            _expect_error("FILE_NOT_FOUND", cwc._open_parent_dir_fd, root / "no_dir" / "x.json")
            _expect_error("FILE_NOT_FOUND", cwc._open_parent_dir_fd, good_f / "x.json")
            _expect_error("SYMLINK_ANCESTOR_FORBIDDEN", cwc._open_parent_dir_fd, sym_dir / "cert.json")

            # chmod 000 leaf & ancestor -> typed FILE_READ_ERROR (zero raw PermissionError)
            if os.geteuid() != 0:
                noperm_f = root / "noperm.json"
                noperm_f.write_bytes(b"{}\n")
                noperm_d = root / "noperm_dir"
                noperm_d.mkdir()
                os.chmod(noperm_f, 0o000)
                os.chmod(noperm_d, 0o000)
                try:
                    _expect_error("FILE_READ_ERROR", cwc.read_strict_utf8_file, noperm_f)
                    _expect_error("FILE_READ_ERROR", cwc.read_strict_utf8_file, noperm_d / "x.json")
                finally:
                    os.chmod(noperm_f, 0o600)
                    os.chmod(noperm_d, 0o700)

            # FIFO, multi-chunk boundary, os.read OSError, & /proc/kallsyms streaming cap
            fifo_p = root / "pipe.fifo"
            os.mkfifo(fifo_p)
            _expect_error("FILE_NOT_FOUND", cwc.read_strict_utf8_file, fifo_p)
            big_ok = root / "big70k.txt"
            big_ok.write_bytes(b"a" * 70_000)
            raw70, _txt70 = cwc.read_strict_utf8_file(big_ok, max_bytes=70_000)
            _check(len(raw70) == 70_000, "multi-chunk exact cap ok")
            _expect_error("FILE_TOO_LARGE", cwc.read_strict_utf8_file, big_ok, max_bytes=69_999)
            with patch.object(cwc.os, "read", side_effect=OSError("simulated EIO")):
                _expect_error("FILE_READ_ERROR", cwc.read_strict_utf8_file, good_f)
            kallsyms = Path("/proc/kallsyms")
            if kallsyms.exists():
                _expect_error("FILE_TOO_LARGE", cwc.read_strict_utf8_file, kallsyms, max_bytes=1024)

            # Live renameat2(RENAME_EXCHANGE) TOCTOU race: 0 canary leaks
            canary_f = root / "canary.json"
            canary_f.write_bytes(b'{"canary":"TOP_CANARY_LEAK"}\n')
            victim_f = root / "victim.json"
            victim_f.write_bytes(b'{"pub":1}\n')
            bait_sym = root / "bait_sym.json"
            bait_sym.symlink_to(canary_f)
            stop_ev = threading.Event()
            swap_errs: list[str] = []
            arch = os.uname().machine
            sys_nr = 316 if arch == "x86_64" else 276
            libc = ctypes.CDLL(None, use_errno=True)

            def _swap() -> None:
                while not stop_ev.is_set():
                    rc = libc.syscall(sys_nr, -100, os.fsencode(victim_f), -100, os.fsencode(bait_sym), 2)
                    if rc != 0:
                        swap_errs.append(str(ctypes.get_errno()))
                        break

            th = threading.Thread(target=_swap)
            th.start()
            leaks = 0
            try:
                for _ in range(300):
                    try:
                        _raw, txt = cwc.read_strict_utf8_file(victim_f, max_bytes=4096)
                        if "TOP_CANARY_LEAK" in txt:
                            leaks += 1
                    except cwc.ClaimWitnessError as exc:
                        _check(exc.code == "SYMLINK_FORBIDDEN", f"unexpected race error {exc.code}")
            finally:
                stop_ev.set()
                th.join(timeout=10)
            _check(swap_errs == [], f"swap errors: {swap_errs}")
            _check(leaks == 0, f"canary leaks: {leaks}")

    def test_self_test_cli_exits_nonzero_on_missed_escape_or_fp(self) -> None:
        # Must fail closed via build_certificate() and CLI exit code if an escape is missed or FP occurs.
        with patch.object(
            cwc,
            "_check_delivery_scope",
            return_value={"id": "p", "kind": "delivery_scope", "passed": True, "reasons": []},
        ):
            _expect_error("SELF_TEST_FAILED", cwc.build_certificate)
            err_buf = io.StringIO()
            with patch("sys.stderr", err_buf):
                rc = cwc.main(["--self-test", "--json"])
            _check(rc == 1, f"expected rc=1 on missed escape, got {rc}")
            _check("SELF_TEST_FAILED" in err_buf.getvalue(), "expected SELF_TEST_FAILED on stderr")

        real_tomo = cwc.compute_blind_spot_tomography

        def _fp_tomo() -> dict[str, object]:
            p = real_tomo()
            p["reference_escape_suite"]["false_positives"] = 1
            return p

        def _pos_tomo() -> dict[str, object]:
            p = real_tomo()
            p["reference_escape_suite"]["positive_controls_passed"] = 5
            return p

        for fn in (_fp_tomo, _pos_tomo):
            with patch.object(cwc, "compute_blind_spot_tomography", side_effect=fn):
                _expect_error("SELF_TEST_FAILED", cwc.build_certificate)


if __name__ == "__main__":
    unittest.main()
