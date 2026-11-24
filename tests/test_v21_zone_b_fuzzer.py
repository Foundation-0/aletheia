#!/usr/bin/env python3
"""
R5 Mutation-Hardened Adversarial Test Suite for `aletheia.zone_b_fuzzer`.

Pure Python 3 stdlib (`0` bare asserts, `0` external dependencies, `0` RNG calls).
"""
from __future__ import annotations

import copy
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import traceback
import unittest
from unittest import mock

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia import zone_b_fuzzer as mod


class _EvilPath(type(Path())):
    """Path subclass rejected by strict concrete pathlib.Path check."""


def _rename_exchange(path_a: Path, path_b: Path) -> None:
    arch = os.uname().machine
    sys_nr = 316 if arch == "x86_64" else 276
    libc = ctypes.CDLL(None, use_errno=True)
    rc = libc.syscall(sys_nr, -100, os.fsencode(path_a), -100, os.fsencode(path_b), 2)
    if rc != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


class TestZoneBPrimitives(unittest.TestCase):
    def test_parse_capped_int_token_and_json_byte_boundaries(self) -> None:
        max_2048 = (1 << mod.MAX_INT_BITS) - 1
        over_2048 = 1 << mod.MAX_INT_BITS
        self.assertEqual(mod.MAX_INT_DIGITS, 620)
        self.assertEqual(mod._parse_capped_int_token(str(max_2048)), max_2048)
        self.assertEqual(mod._parse_capped_int_token("-" + str(max_2048)), -max_2048)
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._parse_capped_int_token(str(over_2048))
        self.assertEqual(ctx.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json('{"n":' + ("1" + "0" * (mod.MAX_INT_DIGITS - 1)) + "}")
        self.assertEqual(ctx.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json('{"n":' + ("9" * (mod.MAX_INT_DIGITS + 1)) + "}")
        self.assertEqual(ctx.exception.code, "INT_DIGIT_LIMIT")

        exact_cap = '{"s":"' + ("a" * (mod.MAX_JSON_BYTES - 8)) + '"}'
        self.assertIn("s", mod.parse_strict_json(exact_cap))
        over_cap = '{"s":"' + ("a" * (mod.MAX_JSON_BYTES - 7)) + '"}'
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json(over_cap)
        self.assertEqual(ctx.exception.code, "JSON_TOO_LARGE")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json('{"s":"' + chr(0xD800) + '"}')
        self.assertEqual(ctx.exception.code, "INVALID_UNICODE_STR")

    def test_require_exact_int_boundaries(self) -> None:
        max_2048 = (1 << mod.MAX_INT_BITS) - 1
        self.assertEqual(mod.require_exact_int(max_2048, "m"), max_2048)
        self.assertEqual(mod.require_exact_int(-max_2048, "m"), -max_2048)
        self.assertEqual(mod.require_exact_int(-999, "x"), -999)
        self.assertEqual(mod.require_exact_int(5, "x", min_val=5, max_val=10), 5)
        self.assertEqual(mod.require_exact_int(10, "x", min_val=5, max_val=10), 10)
        for bad in (True, False, "5", json.loads("5.0"), mod.EvilInt(5)):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_exact_int(bad, "x")
            self.assertEqual(ctx.exception.code, "INVALID_INT")
        for bad_bound in (True, "5", mod.EvilInt(5)):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_exact_int(5, "x", min_val=bad_bound)  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_BOUND")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_exact_int(5, "x", max_val=bad_bound)  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_BOUND")
        for huge in (1 << mod.MAX_INT_BITS, -(1 << mod.MAX_INT_BITS), 10 ** 5000):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_exact_int(huge, "huge", min_val=0, max_val=10)
            self.assertEqual(ctx.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.require_exact_int(4, "x", min_val=5)
        self.assertEqual(ctx.exception.code, "INT_TOO_SMALL")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.require_exact_int(1, "x", min_val=10 ** 5000)
        self.assertEqual(ctx.exception.code, "INT_TOO_SMALL")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.require_exact_int(11, "x", max_val=10)
        self.assertEqual(ctx.exception.code, "INT_TOO_LARGE")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.require_exact_int(1, "x", max_val=-(10 ** 5000))
        self.assertEqual(ctx.exception.code, "INT_TOO_LARGE")

    def test_validate_json_tree_iterative_all_guards(self) -> None:
        mod.validate_json_tree_iterative([[1]], max_depth=2)
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.validate_json_tree_iterative([[[1]]], max_depth=2)
        self.assertEqual(ctx.exception.code, "JSON_DEPTH_EXCEEDED")

        mod.validate_json_tree_iterative(1, max_depth=1)
        mod.validate_json_tree_iterative(1, max_depth=256)
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.validate_json_tree_iterative(1, max_depth=0)
        self.assertEqual(ctx.exception.code, "INT_TOO_SMALL")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.validate_json_tree_iterative(1, max_depth=257)
        self.assertEqual(ctx.exception.code, "INT_TOO_LARGE")

        max_2048 = (1 << mod.MAX_INT_BITS) - 1
        mod.validate_json_tree_iterative({"n": max_2048, "m": -max_2048, "b": True, "f": False, "z": None, "s": "ok"})
        for over_int in (1 << mod.MAX_INT_BITS, -(1 << mod.MAX_INT_BITS), 10 ** 5000):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.validate_json_tree_iterative({"n": over_int})
            self.assertEqual(ctx.exception.code, "INT_BIT_LIMIT")

        for bad_dict in ({1: "a"}, {mod.EvilStr("a"): 1}):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.validate_json_tree_iterative(bad_dict)
            self.assertEqual(ctx.exception.code, "NON_STR_KEY")

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.validate_json_tree_iterative({"s": "\ud800"})
        self.assertEqual(ctx.exception.code, "INVALID_UNICODE_STR")

        for bad_obj in (
            json.loads("1.5"),
            mod.EvilDict({"a": 1}),
            mod.EvilList([1]),
            mod.EvilInt(1),
            mod.EvilStr("x"),
            mod.LyingSequence((1, 2), 1),
            mod.LyingMapping({"a": 1}),
        ):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.validate_json_tree_iterative(bad_obj)
            self.assertEqual(ctx.exception.code, "FORBIDDEN_JSON_TYPE")

    def test_parse_strict_json_and_canonical_bytes(self) -> None:
        self.assertEqual(mod.parse_strict_json('{"b":1,"a":2}'), {"b": 1, "a": 2})
        self.assertEqual(mod.canonical_json_bytes({"b": 1, "a": 2}), b'{"a":2,"b":1}')

        for bad_text in (b"{}", mod.EvilStr("{}")):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.parse_strict_json(bad_text)  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_JSON_TEXT")

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json('{"schema":"a","\\u0073chema":"b"}')
        self.assertEqual(ctx.exception.code, "DUPLICATE_JSON_KEY")

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json('{"val":1.5}')
        self.assertEqual(ctx.exception.code, "FLOAT_FORBIDDEN")

        for tok in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.parse_strict_json('{"val":' + tok + "}")
            self.assertEqual(ctx.exception.code, "NONFINITE_CONSTANT")

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json('{"broken":')
        self.assertEqual(ctx.exception.code, "JSON_DECODE_ERROR")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json('{"huge":' + ("9" * 5000) + "}")
        self.assertEqual(ctx.exception.code, "INT_DIGIT_LIMIT")

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json(("[" * 1500) + "0" + ("]" * 1500))
        self.assertIn(ctx.exception.code, ("JSON_DECODE_ERROR", "JSON_DEPTH_EXCEEDED"))

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json(("[" * 100) + "0" + ("]" * 100))
        self.assertEqual(ctx.exception.code, "JSON_DEPTH_EXCEEDED")

    def test_require_sha256_hex_and_no_symlink(self) -> None:
        good = "0123456789abcdef" * 4
        self.assertEqual(mod.require_sha256_hex(good, "d"), good)
        for bad_type in (123, None, mod.EvilStr(good)):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_sha256_hex(bad_type, "d")
            self.assertEqual(ctx.exception.code, "INVALID_DIGEST_TYPE")
        for bad_len in ("0" * 63, "0" * 65):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_sha256_hex(bad_len, "d")
            self.assertEqual(ctx.exception.code, "INVALID_DIGEST_LEN")
        for bad_hex in ("A" * 64, "g" * 64, "\u00e9" * 64, "\ud800" * 64):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_sha256_hex(bad_hex, "d")
            self.assertEqual(ctx.exception.code, "INVALID_DIGEST_HEX")

        for bad_p in ("not_a_path", _EvilPath("a.json")):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_no_symlink_path(bad_p)  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_PATH_TYPE")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.require_no_symlink_path(Path("bad\x00file.json"))
        self.assertEqual(ctx.exception.code, "INVALID_PATH_NUL")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.require_no_symlink_path(Path("bad" + chr(0xD800) + ".json"))
        self.assertEqual(ctx.exception.code, "INVALID_UNICODE_STR")

        with tempfile.TemporaryDirectory(prefix="zb_sym_test_") as td:
            root = Path(td)
            real_dir = root / "real"
            real_dir.mkdir()
            real_file = real_dir / "f.json"
            real_file.write_bytes(b"{}\n")
            mod.require_no_symlink_path(real_file)

            sym_file = root / "sym_f.json"
            sym_file.symlink_to(real_file)
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_no_symlink_path(sym_file)
            self.assertEqual(ctx.exception.code, "SYMLINK_FORBIDDEN")

            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(real_dir)
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.require_no_symlink_path(sym_dir / "f.json")
            self.assertEqual(ctx.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

    def test_hostile_containers_and_mutation_helpers(self) -> None:
        ls = mod.LyingSequence((10, 20, 30), 2)
        self.assertEqual(len(ls), 2)
        self.assertEqual(ls[2], 30)
        lm = mod.LyingMapping({"k": 7})
        self.assertEqual(len(lm), 1)
        self.assertEqual(list(lm), ["k"])
        self.assertEqual(lm["k"], 7)

        self.assertEqual(
            mod.detect_python_traceback("Traceback (most recent call last):\nTypeError: bad\n", ""),
            (True, "TypeError: bad"),
        )
        self.assertEqual(
            mod.detect_python_traceback("", "Traceback (most recent call last):\nValueError: out\n"),
            (True, "ValueError: out"),
        )
        self.assertEqual(mod.detect_python_traceback("REJECT error", "OK"), (False, ""))

        only_p = mod._resign_envelope({"payload": {"a": 1}})
        self.assertNotIn("payload_sha256", only_p)
        self.assertNotIn("certificate_sha256", only_p)
        only_psha = mod._resign_envelope({"payload_sha256": "0" * 64})
        self.assertEqual(only_psha["payload_sha256"], "0" * 64)

        flipped_d, ok_d = mod._flip_first_zero_or_one_int({"a": True, "b": 2, "c": 1, "d": 0})
        self.assertTrue(ok_d)
        self.assertIs(flipped_d["a"], True)
        self.assertEqual(flipped_d["b"], 2)
        self.assertIs(flipped_d["c"], True)
        self.assertEqual(flipped_d["d"], 0)
        self.assertIs(type(flipped_d["d"]), int)

        flipped_l, ok_l = mod._flip_first_zero_or_one_int([2, 0, 1])
        self.assertTrue(ok_l)
        self.assertEqual(flipped_l[0], 2)
        self.assertIs(flipped_l[1], False)
        self.assertEqual(flipped_l[2], 1)
        self.assertIs(type(flipped_l[2]), int)

        unflipped, ok_none = mod._flip_first_zero_or_one_int({"a": 2, "b": "s"})
        self.assertFalse(ok_none)
        self.assertEqual(unflipped, {"a": 2, "b": "s"})

        rep_d, ch_d = mod._replace_digest_strings({"a_sha256": "0" * 64, "b": 1, "c_sha256": 99}, "X")
        self.assertTrue(ch_d)
        self.assertEqual(rep_d, {"a_sha256": "X", "b": 1, "c_sha256": 99})
        rep_l, ch_l = mod._replace_digest_strings([{"a_sha256": "0" * 64}, {"b": 1}], "Y")
        self.assertTrue(ch_l)
        self.assertEqual(rep_l, [{"a_sha256": "Y"}, {"b": 1}])
        rep_ns, ch_ns = mod._replace_digest_strings({1: "a", "schema": "v1"}, "X")
        self.assertFalse(ch_ns)
        self.assertEqual(rep_ns, {1: "a", "schema": "v1"})
        rep_nest, ch_nest = mod._replace_digest_strings({"outer": {"inner_sha256": "0" * 64}}, "X")
        self.assertTrue(ch_nest)
        self.assertEqual(rep_nest, {"outer": {"inner_sha256": "X"}})
        _, ch_no = mod._replace_digest_strings({"plain": 1}, "Z")
        self.assertFalse(ch_no)

        b_wrapped_hit = mod._make_bool_resigned_cert({"payload": {"x": 1}, "payload_sha256": "0" * 64})
        self.assertNotIn("zb05_bool_forge", b_wrapped_hit["payload"])
        self.assertIs(b_wrapped_hit["payload"]["x"], True)

        b_wrapped_miss = mod._make_bool_resigned_cert({"payload": {"x": 2}, "payload_sha256": "0" * 64})
        self.assertIs(b_wrapped_miss["payload"]["zb05_bool_forge"], True)

        b_wrapped_list = mod._make_bool_resigned_cert({"payload": [2], "payload_sha256": "0" * 64})
        self.assertEqual(b_wrapped_list["payload"], [2])

        b_flat_hit = mod._make_bool_resigned_cert({"x": 0})
        self.assertIs(b_flat_hit["x"], False)
        self.assertNotIn("zb05_bool_forge", b_flat_hit)

        b_flat_miss = mod._make_bool_resigned_cert({"x": 2})
        self.assertIs(b_flat_miss["zb05_bool_forge"], True)

        h_wrapped = mod._make_hollow_resigned_cert({"payload": {"a": 1}, "payload_sha256": "0" * 64})
        self.assertEqual(h_wrapped["payload"], {})
        h_flat = mod._make_hollow_resigned_cert({"schema": "s", "value": 42})
        self.assertEqual(h_flat["schema"], "s")
        self.assertEqual(h_flat["value"], "HOLLOWED_BY_ZONE_B")


def _inprocess_ref_check_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    """Execute `zone_b_fuzzer.py --ref-check <path>` in-process for deterministic fast tests."""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    try:
        with mock.patch("sys.stdout", out_buf), mock.patch("sys.stderr", err_buf):
            rc = mod.main(cmd[7:])
    except BaseException:
        err_buf.write(traceback.format_exc())
        rc = 1
    return subprocess.CompletedProcess(cmd, rc, out_buf.getvalue(), err_buf.getvalue())


class TestFuzzerEnginesAndFoils(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ref_cert = mod.build_reference_cert()
        with mock.patch.object(mod.subprocess, "run", side_effect=_inprocess_ref_check_run):
            cls.real_cert = mod.build_certificate()

    def test_build_attack_cases_wrapped_and_flat_and_16_vector_coverage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zb_cases_") as td:
            wd = Path(td)
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.build_cli_attack_cases(b"[]\n", wd)
            self.assertEqual(ctx.exception.code, "BASELINE_CERT_NOT_DICT")

            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.build_memory_attack_cases([])  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "BASELINE_CERT_NOT_DICT")

            cli_wrapped = mod.build_cli_attack_cases(mod.canonical_json_bytes(self.ref_cert) + b"\n", wd)
            mem_wrapped = mod.build_memory_attack_cases(self.ref_cert)
            seen_ids = {vid for vid, _, _ in cli_wrapped} | {vid for vid, _, _ in mem_wrapped}
            expected_ids = {v["id"] for v in mod.CORPUS_VECTORS}
            self.assertEqual(seen_ids, expected_ids)
            self.assertEqual(len(seen_ids), 16)

            flat_dir = wd / "flat"
            flat_dir.mkdir()
            cli_flat = mod.build_cli_attack_cases(b'{"a":2}\n', flat_dir)
            mem_flat = mod.build_memory_attack_cases({"a": 2})
            self.assertEqual(len(cli_flat), len(cli_wrapped))
            self.assertEqual(len(mem_flat), len(mem_wrapped))

            mem_list_payload = mod.build_memory_attack_cases({"schema": "s", "payload": [1, 2], "count": 2})
            self.assertEqual(len(mem_list_payload), len(mem_wrapped))
            hollow_lp = [obj for _vid, sub, obj in mem_list_payload if sub == "hollow_resigned"]
            self.assertEqual(len(hollow_lp), 1)
            self.assertEqual(hollow_lp[0]["payload"], [1, 2])
            self.assertEqual(hollow_lp[0]["count"], "HOLLOWED_BY_ZONE_B")

    def test_fuzz_cli_checker_validation_and_outcomes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zb_cli_eng_") as td:
            root = Path(td)
            good_script = root / "s.py"
            good_script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
            good_cert = root / "c.json"
            good_cert.write_bytes(mod.canonical_json_bytes(self.ref_cert) + b"\n")

            for sp, cp in (("not_path", good_cert), (good_script, "not_path")):
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod.fuzz_cli_checker(sp, cp)  # type: ignore[arg-type]
                self.assertEqual(ctx.exception.code, "INVALID_PATH_TYPE")

            sym_s = root / "sym_s.py"
            sym_s.symlink_to(good_script)
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.fuzz_cli_checker(sym_s, good_cert)
            self.assertEqual(ctx.exception.code, "SYMLINK_FORBIDDEN")

            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.fuzz_cli_checker(root / "missing.py", good_cert)
            self.assertEqual(ctx.exception.code, "SCRIPT_NOT_FOUND")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.fuzz_cli_checker(good_script, root / "missing.json")
            self.assertEqual(ctx.exception.code, "CERT_NOT_FOUND")

            for bad_flag in ("", "   ", 123):
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod.fuzz_cli_checker(good_script, good_cert, check_flag=bad_flag)  # type: ignore[arg-type]
                self.assertEqual(ctx.exception.code, "INVALID_CHECK_FLAG")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.fuzz_cli_checker(good_script, good_cert, timeout_sec=0)
            self.assertEqual(ctx.exception.code, "INT_TOO_SMALL")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.fuzz_cli_checker(good_script, good_cert, timeout_sec=301)
            self.assertEqual(ctx.exception.code, "INT_TOO_LARGE")

            broken_script = root / "broken.py"
            broken_script.write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
            rep_base = mod.fuzz_cli_checker(broken_script, good_cert)
            self.assertEqual(rep_base["status"], "BASELINE_FAILED")
            self.assertFalse(rep_base["baseline_ok"])
            self.assertFalse(rep_base["passed"])
            self.assertEqual(rep_base["baseline_rc"], 2)

            one_attack = root / "one_attack.json"
            one_attack.write_bytes(b"[]\n")

            def _one_case(_raw: bytes, _wd: Path) -> list[tuple[str, str, Path]]:
                return [("ZB09_non_dict_root", "list_root", one_attack)]

            with mock.patch.object(mod, "build_cli_attack_cases", side_effect=_one_case):
                rep_bypass = mod.fuzz_cli_checker(good_script, good_cert)
            self.assertEqual(rep_bypass["status"], "FAIL")
            self.assertFalse(rep_bypass["passed"])
            self.assertEqual(rep_bypass["bypasses"], 1)
            self.assertEqual(rep_bypass["crashes"], 0)

            crash_script = root / "crash.py"
            crash_script.write_text(
                "import sys\n"
                f"if sys.argv[-1] == {str(good_cert)!r}:\n"
                "    sys.exit(0)\n"
                "raise RuntimeError('forced_cli_crash')\n",
                encoding="utf-8",
            )
            with mock.patch.object(mod, "build_cli_attack_cases", side_effect=_one_case):
                rep_crash = mod.fuzz_cli_checker(crash_script, good_cert)
            self.assertEqual(rep_crash["status"], "FAIL")
            self.assertFalse(rep_crash["passed"])
            self.assertEqual(rep_crash["bypasses"], 0)
            self.assertEqual(rep_crash["crashes"], 1)
            self.assertEqual(rep_crash["findings"][0]["traceback_tail"], "RuntimeError: forced_cli_crash")

            with mock.patch.object(mod, "build_cli_attack_cases", side_effect=_one_case):
                rep_clean = mod.fuzz_cli_checker(mod.HERE / "zone_b_fuzzer.py", good_cert, check_flag="--ref-check")
            self.assertEqual(rep_clean["status"], "PASS")
            self.assertTrue(rep_clean["passed"])
            self.assertEqual(rep_clean["clean_rejections"], 1)
            self.assertEqual(rep_clean["bypasses"], 0)
            self.assertEqual(rep_clean["crashes"], 0)

    def test_fuzz_python_validator_validation_and_foils(self) -> None:
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.fuzz_python_validator(123, self.ref_cert)  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.code, "INVALID_VALIDATOR")

        for bad_excs in ((), [ValueError], (int,), ("not_a_type",)):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.fuzz_python_validator(mod.reference_verify_dict, self.ref_cert, expected_exc_types=bad_excs)  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_EXC_TYPES")

        def _plain_val_err(obj: object) -> bool:
            if type(obj) is dict and obj == self.ref_cert and type(obj.get("payload", {}).get("exact_count")) is int:
                return True
            raise ValueError("ordinary rejection")

        rep_plain = mod.fuzz_python_validator(_plain_val_err, self.ref_cert, expected_exc_types=(ValueError,))
        self.assertTrue(rep_plain["passed"])
        self.assertEqual(rep_plain["crashes"], 0)
        self.assertEqual(rep_plain["bypasses"], 0)

        rep_rec = mod.fuzz_python_validator(mod._foil_recursive_walker, self.ref_cert, expected_exc_types=(mod.ZoneBFuzzError,))
        self.assertFalse(rep_rec["passed"])
        self.assertEqual(rep_rec["bypasses"], 0)
        self.assertGreater(rep_rec["crashes"], 0)

        rep_hol = mod.fuzz_python_validator(mod._foil_hash_only_no_recompute, self.ref_cert, expected_exc_types=(mod.ZoneBFuzzError,))
        self.assertFalse(rep_hol["passed"])
        self.assertGreater(rep_hol["bypasses"], 0)
        self.assertEqual(rep_hol["crashes"], 0)

        rep_int = mod.fuzz_python_validator(mod._foil_raw_int_digit_limit, self.ref_cert, expected_exc_types=(ValueError,))
        self.assertFalse(rep_int["passed"])
        zb03_findings = [f for f in rep_int["findings"] if f["vector_id"] == "ZB03_huge_int_5000_digits"]
        self.assertEqual(len(zb03_findings), 1)
        self.assertEqual(zb03_findings[0]["outcome"], "CRASH")
        self.assertIn("raw_int_digit_limit:", zb03_findings[0]["detail"])

        self.assertEqual(mod._foil_naive_compare_digest(self.ref_cert), {"valid": True})
        for bad in ([], {"wrong": 1}):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._foil_naive_compare_digest(bad)
            self.assertEqual(ctx.exception.code, "FOIL_SCHEMA")
        bad_f1 = copy.deepcopy(self.ref_cert)
        bad_f1["payload_sha256"] = "0" * 64
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_naive_compare_digest(bad_f1)
        self.assertEqual(ctx.exception.code, "FOIL_SHA")

        self.assertEqual(mod._foil_bool_eq_and_isinstance(self.ref_cert), {"valid": True})
        for bad in ([], {"wrong": 1}):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._foil_bool_eq_and_isinstance(bad)
            self.assertEqual(ctx.exception.code, "FOIL_SCHEMA")
        bad_f3 = copy.deepcopy(self.ref_cert)
        bad_f3["payload"] = {}
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_bool_eq_and_isinstance(bad_f3)
        self.assertEqual(ctx.exception.code, "FOIL_PAYLOAD")

        self.assertEqual(mod._foil_hash_only_no_recompute(self.ref_cert), {"valid": True})
        for bad in ([], {"wrong": 1}):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._foil_hash_only_no_recompute(bad)
            self.assertEqual(ctx.exception.code, "FOIL_SCHEMA")
        self.assertEqual(
            mod._masked_valueerror_crash_detail(
                mod.ZoneBFuzzError("INT_LIMIT", "Exceeds the limit (4300 digits)"),
                (mod.ZoneBFuzzError,),
            ),
            "",
        )

        bad_f4_c = copy.deepcopy(self.ref_cert)
        bad_f4_c["certificate_sha256"] = "0" * 64
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_hash_only_no_recompute(bad_f4_c)
        self.assertEqual(ctx.exception.code, "FOIL_SHA")
        bad_f4_p = copy.deepcopy(self.ref_cert)
        bad_f4_p["payload_sha256"] = "0" * 64
        bad_f4_env = {
            "schema": bad_f4_p["schema"],
            "payload_sha256": bad_f4_p["payload_sha256"],
            "payload": bad_f4_p["payload"],
        }
        bad_f4_p["certificate_sha256"] = hashlib.sha256(mod.canonical_json_bytes(bad_f4_env)).hexdigest()
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_hash_only_no_recompute(bad_f4_p)
        self.assertEqual(ctx.exception.code, "FOIL_SHA")

    def test_reference_checker_and_self_cert_guards(self) -> None:
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.reference_verify_dict([])
        self.assertEqual(ctx.exception.code, "REF_NOT_DICT")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.reference_verify_dict({"a": 1})
        self.assertEqual(ctx.exception.code, "REF_KEYS_MISMATCH")

        bad_schema = copy.deepcopy(self.ref_cert)
        bad_schema["schema"] = "wrong"
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.reference_verify_dict(bad_schema)
        self.assertEqual(ctx.exception.code, "REF_SCHEMA_MISMATCH")

        bad_psha = copy.deepcopy(self.ref_cert)
        bad_psha["payload_sha256"] = "0" * 64
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.reference_verify_dict(bad_psha)
        self.assertEqual(ctx.exception.code, "REF_PAYLOAD_SHA_MISMATCH")

        bad_csha = copy.deepcopy(self.ref_cert)
        bad_csha["certificate_sha256"] = "0" * 64
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.reference_verify_dict(bad_csha)
        self.assertEqual(ctx.exception.code, "REF_CERT_SHA_MISMATCH")

        hollow_ref = mod._make_hollow_resigned_cert(self.ref_cert)
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.reference_verify_dict(hollow_ref)
        self.assertEqual(ctx.exception.code, "REF_RECOMPUTED_DRIFT")

        with tempfile.TemporaryDirectory(prefix="zb_ref_file_") as td:
            root = Path(td)
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.reference_check_file(root / "nope.json")
            self.assertEqual(ctx.exception.code, "REF_FILE_NOT_FOUND")

            canon = mod.canonical_json_bytes(self.ref_cert)
            p_no_nl = root / "no_nl.json"
            p_no_nl.write_bytes(canon)
            self.assertTrue(mod.reference_check_file(p_no_nl)["valid"])

            with mock.patch.object(mod, "MAX_JSON_BYTES", len(canon)):
                self.assertTrue(mod.reference_check_file(p_no_nl)["valid"])
            with mock.patch.object(mod, "MAX_JSON_BYTES", len(canon) - 1):
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod.reference_check_file(p_no_nl)
                self.assertEqual(ctx.exception.code, "REF_FILE_TOO_LARGE")

            for fname, suffix in (("crlf.json", b"\r\n"), ("cr.json", b"\r")):
                p_cr = root / fname
                p_cr.write_bytes(canon + suffix)
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod.reference_check_file(p_cr)
                self.assertEqual(ctx.exception.code, "REF_CRLF_FORBIDDEN")

            p_bad_utf8 = root / "bad_utf8.json"
            p_bad_utf8.write_bytes(b"\xff\xfe")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.reference_check_file(p_bad_utf8)
            self.assertEqual(ctx.exception.code, "REF_INVALID_UTF8")

            p_noncanon = root / "noncanon.json"
            p_noncanon.write_bytes(canon + b"\n\n")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.reference_check_file(p_noncanon)
            self.assertEqual(ctx.exception.code, "REF_NON_CANONICAL")

    def test_self_cert_payload_failure_guards_and_boolops(self) -> None:
        ok_cli = {
            "surface": "cli",
            "baseline_ok": True,
            "passed": True,
            "status": "PASS",
            "baseline_rc": 0,
            "cases_run": 25,
            "clean_rejections": 25,
            "bypasses": 0,
            "crashes": 0,
            "findings": [],
        }

        for bad_cli in (dict(ok_cli, clean_rejections=24), dict(ok_cli, passed=False)):
            with mock.patch.object(mod, "fuzz_cli_checker", return_value=bad_cli):
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod.build_self_certification_payload()
                self.assertEqual(ctx.exception.code, "SELF_CERT_FAILED")

        real_fuzz_py = mod.fuzz_python_validator

        def _bad_mem_fuzz(fn, vc, **kw):
            rep = real_fuzz_py(fn, vc, **kw)
            if fn is mod.reference_verify_dict:
                rep["clean_rejections"] = rep["cases_run"] - 1
            return rep

        def _bad_mem_passed(fn, vc, **kw):
            rep = real_fuzz_py(fn, vc, **kw)
            if fn is mod.reference_verify_dict:
                rep["passed"] = False
            return rep

        for side_eff in (_bad_mem_fuzz, _bad_mem_passed):
            with mock.patch.object(mod, "fuzz_cli_checker", return_value=ok_cli):
                with mock.patch.object(mod, "fuzz_python_validator", side_effect=side_eff):
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.build_self_certification_payload()
                    self.assertEqual(ctx.exception.code, "SELF_CERT_FAILED")

        def _partial_bool_foil(fn, vc, **kw):
            rep = real_fuzz_py(fn, vc, **kw)
            if fn is mod._foil_bool_eq_and_isinstance:
                rep["findings"] = [f for f in rep["findings"] if f["vector_id"] != "ZB12_hostile_mapping_and_subclasses"]
            return rep

        def _partial_bool_foil_no_zb05(fn, vc, **kw):
            rep = real_fuzz_py(fn, vc, **kw)
            if fn is mod._foil_bool_eq_and_isinstance:
                rep["findings"] = [f for f in rep["findings"] if f["vector_id"] != "ZB05_bool_resigned_sha_forgery"]
            return rep

        for side_eff in (_partial_bool_foil, _partial_bool_foil_no_zb05):
            with mock.patch.object(mod, "fuzz_cli_checker", return_value=ok_cli):
                with mock.patch.object(mod, "fuzz_python_validator", side_effect=side_eff):
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.build_self_certification_payload()
                    self.assertEqual(ctx.exception.code, "SELF_CERT_FAILED")

    def test_verify_and_check_certificate_and_cli_main(self) -> None:
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.verify_certificate_dict([])
        self.assertEqual(ctx.exception.code, "CERT_NOT_DICT")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.verify_certificate_dict({"a": 1})
        self.assertEqual(ctx.exception.code, "CERT_SCHEMA_KEYS")

        c_schema = copy.deepcopy(self.real_cert)
        c_schema["schema"] = "wrong"
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.verify_certificate_dict(c_schema)
        self.assertEqual(ctx.exception.code, "CERT_SCHEMA_MISMATCH")

        c_track = copy.deepcopy(self.real_cert)
        c_track["track_id"] = "WRONG"
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.verify_certificate_dict(c_track)
        self.assertEqual(ctx.exception.code, "CERT_TRACK_ID_MISMATCH")

        c_psha = copy.deepcopy(self.real_cert)
        c_psha["payload_sha256"] = "0" * 64
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.verify_certificate_dict(c_psha)
        self.assertEqual(ctx.exception.code, "PAYLOAD_SHA_MISMATCH")

        c_csha = copy.deepcopy(self.real_cert)
        c_csha["certificate_sha256"] = "0" * 64
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.verify_certificate_dict(c_csha)
        self.assertEqual(ctx.exception.code, "CERTIFICATE_SHA_MISMATCH")

        c_hollow = mod._make_hollow_resigned_cert(self.real_cert)
        with mock.patch.object(mod, "build_certificate", return_value=self.real_cert):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.verify_certificate_dict(c_hollow)
            self.assertEqual(ctx.exception.code, "RECOMPUTED_PAYLOAD_DRIFT")
            res_ok = mod.verify_certificate_dict(self.real_cert)
            self.assertTrue(res_ok["valid"])

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.check_certificate_file("not_a_path")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.code, "INVALID_PATH_TYPE")

        with tempfile.TemporaryDirectory(prefix="zb_cert_io_") as td:
            root = Path(td)
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.check_certificate_file(root / "missing.json")
            self.assertEqual(ctx.exception.code, "CERT_FILE_NOT_FOUND")

            canon = mod.canonical_json_bytes(self.real_cert)
            p_cert = root / "cert.json"
            p_cert.write_bytes(canon)

            with mock.patch.object(mod, "build_certificate", return_value=self.real_cert):
                with mock.patch.object(mod, "MAX_JSON_BYTES", len(canon)):
                    self.assertTrue(mod.check_certificate_file(p_cert)["valid"])
                with mock.patch.object(mod, "MAX_JSON_BYTES", len(canon) - 1):
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.check_certificate_file(p_cert)
                    self.assertEqual(ctx.exception.code, "CERT_FILE_TOO_LARGE")

                p_written = root / "sub" / "written.json"
                w_res = mod.write_certificate_file(p_written)
                self.assertTrue(w_res["valid"])
                self.assertEqual(p_written.read_bytes(), canon + b"\n")

                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    self.assertEqual(mod.main(["--check", str(p_written)]), 0)
                    self.assertEqual(mod.main(["--write", str(root / "w2.json")]), 0)
                    self.assertEqual(mod.main(["--self-test"]), 0)
                self.assertIn(f"OK {mod.CERT_TRACK_ID}", buf.getvalue())
                self.assertIn(f"WROTE {mod.CERT_TRACK_ID}", buf.getvalue())

                raw_out = io.BytesIO()
                fake_stdout = mock.MagicMock()
                fake_stdout.buffer = raw_out
                with mock.patch("sys.stdout", fake_stdout):
                    self.assertEqual(mod.main(["--standalone", "--json"]), 0)
                self.assertEqual(raw_out.getvalue(), canon + b"\n")

            for fname, suffix in (("crlf.json", b"\r\n"), ("cr.json", b"\r")):
                p_cr = root / fname
                p_cr.write_bytes(canon + suffix)
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod.check_certificate_file(p_cr)
                self.assertEqual(ctx.exception.code, "CRLF_FORBIDDEN")

            p_utf8 = root / "utf8.json"
            p_utf8.write_bytes(b"\xff\xfe")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.check_certificate_file(p_utf8)
            self.assertEqual(ctx.exception.code, "INVALID_UTF8")

            p_noncanon = root / "noncanon.json"
            p_noncanon.write_bytes(canon + b" ")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.check_certificate_file(p_noncanon)
            self.assertEqual(ctx.exception.code, "NON_CANONICAL_CERT_BYTES")

            ref_path = root / "ref.json"
            ref_path.write_bytes(mod.canonical_json_bytes(self.ref_cert) + b"\n")
            with mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(mod.main(["--ref-check", str(ref_path)]), 0)
                self.assertEqual(mod.main(["--ref-check", str(root / "missing.json")]), 2)
                self.assertEqual(mod.main(["--target-cli", str(mod.HERE / "zone_b_fuzzer.py")]), 2)

            ok_rep = {
                "surface": "cli",
                "baseline_ok": True,
                "passed": True,
                "status": "PASS",
                "baseline_rc": 0,
                "cases_run": 25,
                "clean_rejections": 25,
                "bypasses": 0,
                "crashes": 0,
                "findings": [],
            }
            fail_rep = dict(ok_rep, passed=False, status="FAIL", bypasses=1, clean_rejections=24)
            with mock.patch.object(mod, "fuzz_cli_checker", return_value=ok_rep):
                out_txt = io.StringIO()
                with mock.patch("sys.stdout", out_txt):
                    self.assertEqual(mod.main(["--target-cli", "a.py", "--cert", "b.json"]), 0)
                self.assertIn("PASS target_cli", out_txt.getvalue())

                out_bin = io.BytesIO()
                fake_stdout2 = mock.MagicMock()
                fake_stdout2.buffer = out_bin
                with mock.patch("sys.stdout", fake_stdout2):
                    self.assertEqual(mod.main(["--target-cli", "a.py", "--cert", "b.json", "--json"]), 0)
                self.assertEqual(json.loads(out_bin.getvalue().decode("utf-8"))["status"], "PASS")

            with mock.patch.object(mod, "fuzz_cli_checker", return_value=fail_rep):
                with mock.patch("sys.stdout", io.StringIO()):
                    self.assertEqual(mod.main(["--target-cli", "a.py", "--cert", "b.json"]), 1)

    def test_zone_b_hardening_regression_closures(self) -> None:
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.validate_json_tree_iterative({"\ud800": 1})
        self.assertEqual(ctx.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.parse_strict_json('{"\\ud800":1}')
        self.assertEqual(ctx.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod.canonical_json_bytes({"\ud800": 1})
        self.assertEqual(ctx.exception.code, "INVALID_UNICODE_STR")

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_unhandled_surrogate_utf8([])
        self.assertEqual(ctx.exception.code, "REF_NOT_DICT")
        with self.assertRaises(UnicodeEncodeError):
            mod._foil_unhandled_surrogate_utf8({"payload_sha256": "\ud800" * 64})
        rep_surr = mod.fuzz_python_validator(
            mod._foil_unhandled_surrogate_utf8, self.ref_cert, expected_exc_types=(ValueError,)
        )
        self.assertFalse(rep_surr["passed"])
        zb02_crashes = [f for f in rep_surr["findings"] if f["vector_id"] == "ZB02_lone_surrogate_digest" and f["outcome"] == "CRASH"]
        self.assertEqual(len(zb02_crashes), 1)
        self.assertIn("masked_unicode_error:", zb02_crashes[0]["detail"])

        def _raise_unicode_on_attack(obj: object) -> bool:
            if type(obj) is dict and obj == self.ref_cert and type(obj.get("payload", {}).get("exact_count")) is int:
                return True
            "\ud800".encode("utf-8")
            return False

        rep_uni_expected = mod.fuzz_python_validator(
            _raise_unicode_on_attack, self.ref_cert, expected_exc_types=(UnicodeError,)
        )
        self.assertTrue(rep_uni_expected["passed"])
        self.assertEqual(rep_uni_expected["crashes"], 0)

        def _raise_json_decode_on_attack(obj: object) -> bool:
            if type(obj) is dict and obj == self.ref_cert and type(obj.get("payload", {}).get("exact_count")) is int:
                return True
            raise json.JSONDecodeError("bad", "x", 0)

        rep_jdec_masked = mod.fuzz_python_validator(
            _raise_json_decode_on_attack, self.ref_cert, expected_exc_types=(ValueError,)
        )
        self.assertFalse(rep_jdec_masked["passed"])
        self.assertEqual(rep_jdec_masked["crashes"], rep_jdec_masked["cases_run"])
        self.assertIn("masked_json_decode_error:", rep_jdec_masked["findings"][0]["detail"])

        rep_jdec_expected = mod.fuzz_python_validator(
            _raise_json_decode_on_attack, self.ref_cert, expected_exc_types=(json.JSONDecodeError,)
        )
        self.assertTrue(rep_jdec_expected["passed"])
        self.assertEqual(rep_jdec_expected["crashes"], 0)

        with tempfile.TemporaryDirectory(prefix="zb_r2_cli_") as td:
            root = Path(td)
            script = root / "s.py"
            script.write_text(
                "import sys\n"
                "sys.stderr.buffer.write(b'\\xff\\xfeREJECT\\n')\n"
                "sys.exit(0 if sys.argv[-1].endswith('good.json') else 2)\n",
                encoding="utf-8",
            )
            good_cert = root / "good.json"
            good_cert.write_bytes(mod.canonical_json_bytes(self.ref_cert) + b"\n")
            one_attack = root / "bad.json"
            one_attack.write_bytes(b"[]\n")

            def _one_case(_raw: bytes, _wd: Path) -> list[tuple[str, str, Path]]:
                return [("ZB09_non_dict_root", "list_root", one_attack)]

            with mock.patch.object(mod, "build_cli_attack_cases", side_effect=_one_case):
                rep_nonutf8 = mod.fuzz_cli_checker(script, good_cert)
            self.assertTrue(rep_nonutf8["passed"])
            self.assertEqual(rep_nonutf8["clean_rejections"], 1)
            self.assertEqual(rep_nonutf8["crashes"], 0)

            with mock.patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
                rep_base_to = mod.fuzz_cli_checker(script, good_cert)
            self.assertEqual(rep_base_to["status"], "BASELINE_FAILED")
            self.assertEqual(rep_base_to["baseline_rc"], -1)
            self.assertFalse(rep_base_to["passed"])

            call_n = {"i": 0}

            def _timeout_on_second(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
                call_n["i"] += 1
                if call_n["i"] == 1:
                    return subprocess.CompletedProcess(cmd, 0, "OK\n", "")
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

            with mock.patch.object(mod, "build_cli_attack_cases", side_effect=_one_case):
                with mock.patch.object(mod.subprocess, "run", side_effect=_timeout_on_second):
                    rep_att_to = mod.fuzz_cli_checker(script, good_cert)
            self.assertEqual(rep_att_to["status"], "FAIL")
            self.assertFalse(rep_att_to["passed"])
            self.assertEqual(rep_att_to["crashes"], 1)
            self.assertEqual(rep_att_to["findings"][0]["returncode"], -1)
            self.assertEqual(rep_att_to["findings"][0]["traceback_tail"], "TIMEOUT")

            for bad_raw in (b"\xff\xfe", b'{"huge":' + (b"9" * 5000) + b"}"):
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod.build_cli_attack_cases(bad_raw, root)
                self.assertEqual(ctx.exception.code, "BASELINE_CERT_INVALID")

        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._resign_envelope({"payload": {"x": 10 ** 5000}, "payload_sha256": "0" * 64})
        self.assertEqual(ctx.exception.code, "SERIALIZE_ERROR")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._safe_dumps({"x": object()})
        self.assertEqual(ctx.exception.code, "SERIALIZE_ERROR")
        self.assertIn("\n", mod._safe_dumps({"a": 1}, indent=2))

        self.assertEqual(mod._safe_exc_text(ValueError("a" * 256)), "a" * 256)
        self.assertEqual(mod._safe_exc_text(ValueError("a" * 257)), ("a" * 256) + "...")
        surr_txt = mod._safe_exc_text(ValueError("bad \ud800 key"))
        self.assertNotIn("\ud800", surr_txt)
        mod.canonical_json_bytes({"msg": surr_txt})

        class _BrokenStrError(RuntimeError):
            def __str__(self) -> str:
                raise RuntimeError("boom in __str__")

        self.assertEqual(mod._safe_exc_text(_BrokenStrError()), "<unstringifiable>")

        def _always_broken_str(_obj: object) -> None:
            raise _BrokenStrError()

        rep_broken_base = mod.fuzz_python_validator(_always_broken_str, self.ref_cert)
        self.assertEqual(rep_broken_base["status"], "BASELINE_FAILED")
        self.assertIn("<unstringifiable>", rep_broken_base["baseline_error"])
        mod.canonical_json_bytes(rep_broken_base)

        def _attack_broken_str(obj: object) -> bool:
            if type(obj) is dict and obj == self.ref_cert and type(obj.get("payload", {}).get("exact_count")) is int:
                return True
            raise _BrokenStrError()

        rep_broken_att = mod.fuzz_python_validator(_attack_broken_str, self.ref_cert)
        self.assertEqual(rep_broken_att["status"], "FAIL")
        self.assertEqual(rep_broken_att["crashes"], rep_broken_att["cases_run"])
        self.assertIn("<unstringifiable>", rep_broken_att["findings"][0]["detail"])
        mod.canonical_json_bytes(rep_broken_att)

    def test_r2_signal_crash_interrupt_and_atomic_write_0600(self) -> None:
        # F1: negative signal returncode (empty stderr) MUST be classified as CRASH, never REJECTED_CLEAN
        with tempfile.TemporaryDirectory(prefix="zb_r2_sig_") as td:
            root = Path(td)
            sig_script = root / "sig_foil.py"
            sig_script.write_text(
                "import os, signal, sys\n"
                "if sys.argv[-1].endswith('good.json'):\n"
                "    sys.exit(0)\n"
                "os.kill(os.getpid(), signal.SIGKILL)\n",
                encoding="utf-8",
            )
            good_cert = root / "good.json"
            good_cert.write_bytes(mod.canonical_json_bytes(self.ref_cert) + b"\n")
            one_attack = root / "bad.json"
            one_attack.write_bytes(b"[]\n")

            def _one_case(_raw: bytes, _wd: Path) -> list[tuple[str, str, Path]]:
                return [("ZB09_non_dict_root", "list_root", one_attack)]

            with mock.patch.object(mod, "build_cli_attack_cases", side_effect=_one_case):
                rep_sig = mod.fuzz_cli_checker(sig_script, good_cert)
            self.assertEqual(rep_sig["status"], "FAIL")
            self.assertFalse(rep_sig["passed"])
            self.assertEqual(rep_sig["crashes"], 1)
            self.assertEqual(rep_sig["clean_rejections"], 0)
            self.assertEqual(rep_sig["findings"][0]["outcome"], "CRASH")
            self.assertEqual(rep_sig["findings"][0]["returncode"], -int(signal.SIGKILL))
            self.assertEqual(rep_sig["findings"][0]["traceback_tail"], f"SIGNAL:{int(signal.SIGKILL)}")

            # F7: KeyboardInterrupt & SystemExit MUST propagate out of fuzz_python_validator
            for fatal_exc in (KeyboardInterrupt(), SystemExit(3)):
                def _raise_fatal(obj: object, exc: BaseException = fatal_exc) -> bool:
                    if type(obj) is dict and obj == self.ref_cert and type(obj.get("payload", {}).get("exact_count")) is int:
                        return True
                    raise exc

                with self.assertRaises(type(fatal_exc)):
                    mod.fuzz_python_validator(_raise_fatal, self.ref_cert)

            # R2 atomic 0o600 write: mode, regular overwrite, non-regular dir, target hardlink,
            # EEXIST retry, temp slot exhaustion, pre-replace temp st_nlink != 1, & 16T concurrency
            wtarget = root / "out" / "cert.json"
            mod._atomic_write_bytes_0600(wtarget, b'{"v":1}\n')
            self.assertEqual(stat.S_IMODE(os.stat(wtarget).st_mode), 0o600)
            mod._atomic_write_bytes_0600(wtarget, b'{"v":2}\n')
            self.assertEqual(wtarget.read_bytes(), b'{"v":2}\n')

            sub_dir = root / "sub_dir"
            sub_dir.mkdir()
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._atomic_write_bytes_0600(sub_dir, b"{}\n")
            self.assertEqual(ctx.exception.code, "NOT_REGULAR_FILE")

            hl_alias = wtarget.parent / "alias.json"
            os.link(wtarget, hl_alias)
            try:
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod._atomic_write_bytes_0600(hl_alias, b'{"v":9}\n')
                self.assertEqual(ctx.exception.code, "HARDLINK_FORBIDDEN")
                self.assertEqual(wtarget.read_bytes(), b'{"v":2}\n')
            finally:
                hl_alias.unlink()

            # EEXIST CSPRNG collision retry
            tok_a = "cafe000000000001"
            tok_b = "cafe000000000002"
            pre_tmp = wtarget.parent / f".zb.{os.getpid()}.{tok_a}.tmp"
            pre_tmp.write_bytes(b"pre")
            toks = iter((tok_a, tok_b))
            with mock.patch.object(mod.secrets, "token_hex", side_effect=lambda _n=8: next(toks)):
                mod._atomic_write_bytes_0600(wtarget, b'{"v":3}\n')
            self.assertEqual(wtarget.read_bytes(), b'{"v":3}\n')
            self.assertEqual(pre_tmp.read_bytes(), b"pre")
            pre_tmp.unlink()

            # Exhausted temp slots (64 FileExistsError)
            with mock.patch.object(mod.secrets, "token_hex", return_value=tok_a):
                pre_tmp.write_bytes(b"block")
                try:
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod._atomic_write_bytes_0600(wtarget, b'{"v":4}\n')
                    self.assertEqual(ctx.exception.code, "TEMP_SLOT_EXHAUSTED")
                finally:
                    pre_tmp.unlink()

            # Live pre-replace temp st_nlink != 1 check via os.fsync hook
            orig_fsync = mod.os.fsync
            inj_link = wtarget.parent / "inj_tmp"
            armed = [True]

            def _fsync_inject(fd_arg: int) -> None:
                if armed[0]:
                    tmps = list(wtarget.parent.glob(".zb.*.tmp"))
                    if tmps:
                        armed[0] = False
                        os.link(tmps[0], inj_link)
                orig_fsync(fd_arg)

            try:
                with mock.patch.object(mod.os, "fsync", side_effect=_fsync_inject):
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod._atomic_write_bytes_0600(wtarget, b'{"v":5}\n')
                    self.assertEqual(ctx.exception.code, "HARDLINK_FORBIDDEN")
            finally:
                if inj_link.exists():
                    inj_link.unlink()
            self.assertEqual(wtarget.read_bytes(), b'{"v":3}\n')
            self.assertEqual(list(wtarget.parent.glob(".zb.*.tmp")), [])

            # 16T concurrent atomic writes
            cw_errs: list[str] = []
            valid_16 = {f'{{"t":{i}}}\n'.encode("ascii") for i in range(16)}

            def _w16(idx: int) -> None:
                try:
                    for _ in range(3):
                        mod._atomic_write_bytes_0600(wtarget, f'{{"t":{idx}}}\n'.encode("ascii"))
                except BaseException as exc:
                    cw_errs.append(f"{idx}:{exc}")

            threads = [threading.Thread(target=_w16, args=(i,)) for i in range(16)]
            for th in threads:
                th.start()
            for th in threads:
                th.join(timeout=15)
            self.assertEqual(cw_errs, [])
            self.assertIn(wtarget.read_bytes(), valid_16)
            self.assertEqual(list(wtarget.parent.glob(".zb.*.tmp")), [])

    def test_r3_atomic_dirfd_streaming_renameat2_and_guards(self) -> None:
        # Strict str validation on both detect_python_traceback parameters
        for bad_err, bad_out in ((None, ""), ("", None), (mod.EvilStr("x"), ""), ("", mod.EvilStr("x"))):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.detect_python_traceback(bad_err, bad_out)  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_STR")

        # KeyboardInterrupt / SystemExit MUST propagate even when expected_exc_types includes BaseException
        for fatal_exc in (KeyboardInterrupt(), SystemExit(7)):
            def _raise_fatal_base(obj: object, exc: BaseException = fatal_exc) -> bool:
                if type(obj) is dict and obj == self.ref_cert and type(obj.get("payload", {}).get("exact_count")) is int:
                    return True
                raise exc

            with self.assertRaises(type(fatal_exc)):
                mod.fuzz_python_validator(_raise_fatal_base, self.ref_cert, expected_exc_types=(BaseException,))

        with tempfile.TemporaryDirectory(prefix="zb_r3_io_") as td:
            root = Path(td)
            real_dir = root / "real"
            real_dir.mkdir()
            good_f = real_dir / "good.json"
            good_f.write_bytes(mod.canonical_json_bytes(self.ref_cert) + b"\n")
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(real_dir)
            sym_f = root / "sym_f.json"
            sym_f.symlink_to(good_f)

            # build_cli_attack_cases strict bytes & Path / symlink checks
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.build_cli_attack_cases("{}", real_dir)  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_PAYLOAD_BYTES")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.build_cli_attack_cases(b"{}\n", _EvilPath(real_dir))  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_PATH_TYPE")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.build_cli_attack_cases(b"{}\n", sym_dir)
            self.assertEqual(ctx.exception.code, "SYMLINK_FORBIDDEN")

            # require_no_symlink_path edge cases + $PWD ancestor checks (relative vs absolute)
            mod.require_no_symlink_path(Path("/"))
            mod.require_no_symlink_path(root / "no_such_dir" / "x.json")
            mod.require_no_symlink_path(root / "missing_leaf.json")

            orig_cwd = os.getcwd()
            try:
                os.chdir(real_dir)
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("PWD", None)
                    mod.require_no_symlink_path(Path("."))
                    mod.require_no_symlink_path(Path("good.json"))
                    self.assertTrue(mod.reference_check_file(Path("good.json"))["valid"])
                with mock.patch.dict(os.environ, {"PWD": "rel_" + chr(0xDC80)}):
                    mod.require_no_symlink_path(Path("good.json"))
                with mock.patch.dict(os.environ, {"PWD": "/tmp/" + chr(0xDC80)}):
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.require_no_symlink_path(Path("good.json"))
                    self.assertEqual(ctx.exception.code, "INVALID_UNICODE_STR")
                with mock.patch.dict(os.environ, {"PWD": str(root / "nonexistent_pwd")}):
                    mod.require_no_symlink_path(Path("good.json"))
                with mock.patch.dict(os.environ, {"PWD": str(sym_dir)}):
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.require_no_symlink_path(Path("good.json"))
                    self.assertEqual(ctx.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.reference_check_file(Path("good.json"))
                    self.assertEqual(ctx.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
                    # Absolute path outside symlink MUST NOT be blocked by symlink $PWD
                    mod.require_no_symlink_path(good_f)
                    self.assertTrue(mod.reference_check_file(good_f)["valid"])
            finally:
                os.chdir(orig_cwd)

            # Live subprocess CLI check under symlink $PWD
            env_sym = dict(os.environ)
            env_sym["PWD"] = str(sym_dir)
            proc_rel = subprocess.run(
                [sys.executable, "-I", "-B", str(mod.HERE / "zone_b_fuzzer.py"), "--ref-check", "good.json"],
                cwd=str(real_dir),
                env=env_sym,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc_rel.returncode, 2)
            self.assertIn("SYMLINK_ANCESTOR_FORBIDDEN", proc_rel.stderr)
            proc_abs = subprocess.run(
                [sys.executable, "-I", "-B", str(mod.HERE / "zone_b_fuzzer.py"), "--ref-check", str(good_f)],
                cwd=str(real_dir),
                env=env_sym,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc_abs.returncode, 0)

            # _open_parent_dir_fd boundary & error branches
            for bad_p, exp_code in (
                (Path("/"), "FILE_NOT_FOUND"),
                (real_dir / "..", "FILE_NOT_FOUND"),
                (root / "no_dir" / "x.json", "FILE_NOT_FOUND"),
                (good_f / "x.json", "FILE_NOT_FOUND"),
                (sym_dir / "good.json", "SYMLINK_ANCESTOR_FORBIDDEN"),
            ):
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod._open_parent_dir_fd(bad_p)
                self.assertEqual(ctx.exception.code, exp_code)

            # _atomic_write_bytes_0600 guards (non-bytes, root, .., symlink leaf, symlink ancestor, chmod 500)
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._atomic_write_bytes_0600(root / "bad.json", "not_bytes")  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "INVALID_PAYLOAD_BYTES")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._atomic_write_bytes_0600(Path("/"), b"{}\n")
            self.assertEqual(ctx.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._atomic_write_bytes_0600(real_dir / "..", b"{}\n")
            self.assertEqual(ctx.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._atomic_write_bytes_0600(sym_f, b"{}\n")
            self.assertEqual(ctx.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._atomic_write_bytes_0600(sym_dir / "out.json", b"{}\n")
            self.assertEqual(ctx.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

            # chmod 000 file & ancestor -> typed FILE_READ_ERROR; chmod 500 dir -> typed FILE_WRITE_ERROR
            if os.geteuid() != 0:
                noperm_f = root / "noperm.json"
                noperm_f.write_bytes(b"{}\n")
                noperm_d = root / "noperm_dir"
                noperm_d.mkdir()
                ro_d = root / "ro_dir"
                ro_d.mkdir()
                os.chmod(noperm_f, 0o000)
                os.chmod(noperm_d, 0o000)
                os.chmod(ro_d, 0o500)
                try:
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.check_certificate_file(noperm_f)
                    self.assertEqual(ctx.exception.code, "FILE_READ_ERROR")
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.check_certificate_file(noperm_d / "x.json")
                    self.assertEqual(ctx.exception.code, "FILE_READ_ERROR")
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod._atomic_write_bytes_0600(ro_d / "new_sub" / "x.json", b"{}\n")
                    self.assertEqual(ctx.exception.code, "FILE_WRITE_ERROR")
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod._atomic_write_bytes_0600(ro_d / "x.json", b"{}\n")
                    self.assertEqual(ctx.exception.code, "FILE_WRITE_ERROR")
                finally:
                    os.chmod(noperm_f, 0o600)
                    os.chmod(noperm_d, 0o700)
                    os.chmod(ro_d, 0o700)

            # FIFO non-blocking rejection & directory rejection & os.read OSError wrapping
            fifo_p = root / "pipe.fifo"
            os.mkfifo(fifo_p)
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.check_certificate_file(fifo_p)
            self.assertEqual(ctx.exception.code, "CERT_FILE_NOT_FOUND")
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod.check_certificate_file(real_dir)
            self.assertEqual(ctx.exception.code, "CERT_FILE_NOT_FOUND")
            with mock.patch.object(mod.os, "read", side_effect=OSError("simulated EIO")):
                with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                    mod.check_certificate_file(good_f)
                self.assertEqual(ctx.exception.code, "FILE_READ_ERROR")

            # Procfs st_size==0 streaming cap (/proc/kallsyms) in check_certificate_file AND fuzz_cli_checker
            kallsyms = Path("/proc/kallsyms")
            if kallsyms.exists():
                tiny_script = root / "tiny.py"
                tiny_script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
                with mock.patch.object(mod, "MAX_JSON_BYTES", 1024):
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.check_certificate_file(kallsyms)
                    self.assertEqual(ctx.exception.code, "CERT_FILE_TOO_LARGE")
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.fuzz_cli_checker(tiny_script, kallsyms)
                    self.assertEqual(ctx.exception.code, "CERT_FILE_TOO_LARGE")
                    with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                        mod.fuzz_cli_checker(mod.HERE / "zone_b_fuzzer.py", good_f)
                    self.assertEqual(ctx.exception.code, "FILE_TOO_LARGE")

            # Live renameat2(RENAME_EXCHANGE) TOCTOU race: 0 canary leaks & 0 symlink-followed cert accepts
            canary_f = root / "canary.json"
            canary_f.write_bytes(b'{"canary":"TOP_CANARY_LEAK"}\n')
            victim_f = root / "victim.json"
            victim_f.write_bytes(b'{"pub":1}\n')
            bait_sym = root / "bait_sym.json"
            bait_sym.symlink_to(canary_f)
            stop_ev = threading.Event()
            swap_errs: list[str] = []

            def _swap_loop(a: Path, b: Path) -> None:
                while not stop_ev.is_set():
                    try:
                        _rename_exchange(a, b)
                    except BaseException as exc:
                        swap_errs.append(str(exc))
                        break

            t_swap = threading.Thread(target=_swap_loop, args=(victim_f, bait_sym))
            t_swap.start()
            canary_leaks = 0
            try:
                for _ in range(300):
                    try:
                        data = mod._read_regular_bytes_atomic(victim_f, 4096)
                        if b"TOP_CANARY_LEAK" in data:
                            canary_leaks += 1
                    except mod.ZoneBFuzzError as exc:
                        self.assertEqual(exc.code, "SYMLINK_FORBIDDEN")
            finally:
                stop_ev.set()
                t_swap.join(timeout=10)
            self.assertEqual(swap_errs, [])
            self.assertEqual(canary_leaks, 0)

            # Live renameat2(RENAME_EXCHANGE) cert-accept race: invalid regular file <-> symlink to valid ref cert
            bad_reg = root / "race_cert.json"
            bad_reg.write_bytes(b'{"invalid":1}\n')
            bait_valid = root / "bait_valid.json"
            bait_valid.symlink_to(good_f)
            stop_ev2 = threading.Event()
            swap_errs2: list[str] = []

            def _swap_loop2() -> None:
                while not stop_ev2.is_set():
                    try:
                        _rename_exchange(bad_reg, bait_valid)
                    except BaseException as exc:
                        swap_errs2.append(str(exc))
                        break

            t_swap2 = threading.Thread(target=_swap_loop2)
            t_swap2.start()
            symlink_accepts = 0
            try:
                for _ in range(300):
                    try:
                        mod.reference_check_file(bad_reg)
                        symlink_accepts += 1
                    except mod.ZoneBFuzzError as exc:
                        self.assertIn(exc.code, ("SYMLINK_FORBIDDEN", "REF_KEYS_MISMATCH"))
            finally:
                stop_ev2.set()
                t_swap2.join(timeout=10)
            self.assertEqual(swap_errs2, [])
            self.assertEqual(symlink_accepts, 0)

            # 80T barrier burst on _atomic_write_bytes_0600
            burst_target = root / "burst" / "cert.json"
            barrier = threading.Barrier(80)
            burst_errs: list[str] = []
            valid_80 = {f'{{"b":{i}}}\n'.encode("ascii") for i in range(80)}

            def _w80(idx: int) -> None:
                try:
                    barrier.wait(timeout=15)
                    mod._atomic_write_bytes_0600(burst_target, f'{{"b":{idx}}}\n'.encode("ascii"))
                except BaseException as exc:
                    burst_errs.append(f"{idx}:{exc}")

            threads80 = [threading.Thread(target=_w80, args=(i,)) for i in range(80)]
            for th in threads80:
                th.start()
            for th in threads80:
                th.join(timeout=20)
            self.assertEqual(burst_errs, [])
            self.assertIn(burst_target.read_bytes(), valid_80)
            self.assertEqual(stat.S_IMODE(os.stat(burst_target).st_mode), 0o600)
            self.assertEqual(list(burst_target.parent.glob(".zb.*.tmp")), [])

    def test_pr32_review_closures_resigned_zb07_zb08_zb10_tmpdir_and_noisy_baseline(self) -> None:
        # 1. Helper branch coverage: _replace_first_int_with_float, _make_float_resigned_cert, _make_dup_unicode_key_resigned_text
        flt_list, ch_l = mod._replace_first_int_with_float(["x", [2, 3], 4])
        self.assertTrue(ch_l)
        self.assertIs(type(flt_list[1][0]), type(json.loads("2.0")))
        self.assertEqual(flt_list[1][1], 3)
        self.assertEqual(flt_list[2], 4)

        no_int_p = mod._make_float_resigned_cert({"schema": "s", "payload": {"k": "v"}, "payload_sha256": "0" * 64})
        self.assertIn("zb08_float", no_int_p["payload"])
        list_p = mod._make_float_resigned_cert({"schema": "s", "payload": ["str_only"], "payload_sha256": "0" * 64})
        self.assertEqual(list_p["payload"], ["str_only"])
        no_pay_int = mod._make_float_resigned_cert({"schema": "s", "n": 7})
        self.assertIs(type(no_pay_int["n"]), type(json.loads("7.0")))
        no_pay_str = mod._make_float_resigned_cert({"schema": "s", "k": "v"})
        self.assertIn("zb08_float", no_pay_str)

        self.assertEqual(mod._make_dup_unicode_key_resigned_text({}), '{"schema":"a","\\u0073chema":"b"}\n')
        dup_no_schema = mod._make_dup_unicode_key_resigned_text({"alpha": 1})
        self.assertIn("\\u0061lpha", dup_no_schema)
        self.assertEqual(json.loads(dup_no_schema), {"alpha": 1})

        # 2. _foil_float_tolerant direct branches & ZB08 BYPASS detection
        self.assertEqual(mod._foil_float_tolerant(self.ref_cert), {"valid": True})
        for bad in ([], {"wrong": 1}, dict(self.ref_cert, schema="other")):
            with self.assertRaises(mod.ZoneBFuzzError) as ctx:
                mod._foil_float_tolerant(bad)
            self.assertEqual(ctx.exception.code, "FOIL_SCHEMA")
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_float_tolerant(dict(self.ref_cert, payload="not_dict"))
        self.assertEqual(ctx.exception.code, "FOIL_PAYLOAD")
        bad_psha = copy.deepcopy(self.ref_cert)
        bad_psha["payload_sha256"] = "0" * 64
        bad_psha["certificate_sha256"] = hashlib.sha256(
            mod._safe_dumps(
                {"schema": bad_psha["schema"], "payload_sha256": bad_psha["payload_sha256"], "payload": bad_psha["payload"]},
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_float_tolerant(bad_psha)
        self.assertEqual(ctx.exception.code, "FOIL_SHA")
        bad_csha = copy.deepcopy(self.ref_cert)
        bad_csha["certificate_sha256"] = "0" * 64
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_float_tolerant(bad_csha)
        self.assertEqual(ctx.exception.code, "FOIL_SHA")
        hollow = mod._make_hollow_resigned_cert(self.ref_cert)
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_float_tolerant(hollow)
        self.assertEqual(ctx.exception.code, "FOIL_PAYLOAD")
        bool_res = mod._make_bool_resigned_cert(self.ref_cert)
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_float_tolerant(bool_res)
        self.assertEqual(ctx.exception.code, "FOIL_PAYLOAD")
        val_diff = copy.deepcopy(self.ref_cert)
        val_diff["payload"]["exact_count"] = 2
        val_diff = mod._resign_envelope(val_diff)
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_float_tolerant(val_diff)
        self.assertEqual(ctx.exception.code, "FOIL_PAYLOAD")
        flt_res = mod._make_float_resigned_cert(self.ref_cert)
        self.assertEqual(mod._foil_float_tolerant(flt_res), {"valid": True})
        rep_ft = mod.fuzz_python_validator(mod._foil_float_tolerant, self.ref_cert, expected_exc_types=(mod.ZoneBFuzzError,))
        self.assertFalse(rep_ft["passed"])
        self.assertEqual(
            sorted({f["vector_id"] for f in rep_ft["findings"] if f["outcome"] == "BYPASS"}),
            ["ZB08_nonfinite_and_float_literals"],
        )

        # 3. _foil_raw_int_digit_limit iterative (no RecursionError on 1500-deep ZB04; Python 3.11-3.14 invariant)
        with self.assertRaises(ValueError) as ctx_raw:
            mod._foil_raw_int_digit_limit(10**5000)
        self.assertIs(type(ctx_raw.exception), ValueError)
        deep_1500: list[object] = []
        cur = deep_1500
        for _ in range(1500):
            nxt: list[object] = []
            cur.append(nxt)
            cur = nxt
        with self.assertRaises(mod.ZoneBFuzzError) as ctx:
            mod._foil_raw_int_digit_limit({"payload": deep_1500})
        self.assertEqual(ctx.exception.code, "JSON_DEPTH_EXCEEDED")
        rep_int = mod.fuzz_python_validator(mod._foil_raw_int_digit_limit, self.ref_cert, expected_exc_types=(ValueError,))
        self.assertEqual(
            sorted({f["vector_id"] for f in rep_int["findings"] if f["outcome"] == "CRASH"}),
            ["ZB03_huge_int_5000_digits"],
        )

        with tempfile.TemporaryDirectory(prefix="zb_pr32_", dir=mod._resolved_temp_root()) as td:
            root = Path(td)
            # 4. ZB10 baseline without trailing LF passes cleanly (no false BYPASS) EVEN under a symlinked TMPDIR!
            real_tmp = root / "real_tmp"
            real_tmp.mkdir()
            sym_tmp = root / "sym_tmp"
            sym_tmp.symlink_to(real_tmp)
            nonl_cert = root / "ref_nonl.json"
            nonl_cert.write_bytes(mod.canonical_json_bytes(self.ref_cert))
            with mock.patch.object(mod.tempfile, "gettempdir", return_value=str(sym_tmp)):
                self.assertEqual(mod._resolved_temp_root(), os.path.realpath(str(real_tmp)))
                rep_nonl = mod.fuzz_cli_checker(mod.HERE / "zone_b_fuzzer.py", nonl_cert, check_flag="--ref-check")
                self.assertTrue(rep_nonl["passed"])
                self.assertEqual(rep_nonl["bypasses"], 0)
                self.assertEqual(rep_nonl["crashes"], 0)
                seen_self_dirs: list[str] = []

                def _spy_cli(_sp: Path, cp: Path, **_kw: object) -> dict[str, object]:
                    seen_self_dirs.append(str(cp.parent))
                    mod.require_no_symlink_path(cp)
                    return {
                        "surface": "cli",
                        "baseline_ok": True,
                        "passed": True,
                        "status": "PASS",
                        "baseline_rc": 0,
                        "cases_run": 25,
                        "clean_rejections": 25,
                        "bypasses": 0,
                        "crashes": 0,
                        "findings": [],
                    }

                with mock.patch.object(mod, "fuzz_cli_checker", side_effect=_spy_cli):
                    sc_symtmp = mod.build_self_certification_payload()
                    self.assertTrue(sc_symtmp["all_passed"])
                self.assertEqual(len(seen_self_dirs), 1)
                self.assertTrue(seen_self_dirs[0].startswith(os.path.realpath(str(real_tmp))))

            pretty_work = root / "pretty_cases"
            pretty_work.mkdir()
            pretty_base = (mod._safe_dumps(self.ref_cert, indent=2) + "\n").encode("utf-8")
            p_cases = mod.build_cli_attack_cases(pretty_base, pretty_work)
            pretty_probes = [p.read_bytes() for v, s, p in p_cases if v == "ZB10_crlf_and_noncanonical_bytes" and s == "pretty_noncanon"]
            self.assertEqual(len(pretty_probes), 1)
            self.assertNotEqual(pretty_probes[0], pretty_base)
            # Also cover ZB03 with dict payload, non-dict payload, and without payload key
            zb03_dict_probes = [p.read_text(encoding="utf-8") for v, _, p in p_cases if v == "ZB03_huge_int_5000_digits"]
            self.assertEqual(len(zb03_dict_probes), 1)
            self.assertIn('"payload":{', zb03_dict_probes[0])
            self.assertIn('"zb03_huge":' + ("9" * 5000), zb03_dict_probes[0])
            nopay_work = root / "nopay_cases"
            nopay_work.mkdir()
            np_cases = mod.build_cli_attack_cases(b'{"schema":"x","payload":["a"]}\n', nopay_work)
            zb03_list_probes = [p.read_text(encoding="utf-8") for v, _, p in np_cases if v == "ZB03_huge_int_5000_digits"]
            self.assertEqual(len(zb03_list_probes), 1)
            self.assertIn('"payload":["a"],"schema":"x","zb03_huge":' + ("9" * 5000), zb03_list_probes[0])

            # 5. CLI float-tolerant & dup-key-tolerant foils are caught with BYPASS on ZB08 and ZB07!
            ref_nl = root / "ref_nl.json"
            ref_nl.write_bytes(mod.canonical_json_bytes(self.ref_cert) + b"\n")
            foil_cli = root / "foil_float_dup_cli.py"
            foil_cli.write_text(
                "import hashlib, json, sys\n"
                "from pathlib import Path\n"
                "p = Path(sys.argv[2])\n"
                "if p.is_symlink() or not p.is_file(): sys.exit(2)\n"
                "raw = p.read_bytes()\n"
                "if b'\\r' in raw: sys.exit(2)\n"
                "try:\n"
                "    obj = json.loads(raw.decode('utf-8'))\n"
                "except Exception:\n"
                "    sys.exit(2)\n"
                "if type(obj) is not dict or set(obj.keys()) != {'schema','payload_sha256','certificate_sha256','payload'}:\n"
                "    sys.exit(2)\n"
                "pay = obj['payload']\n"
                "if type(pay) is not dict:\n"
                "    sys.exit(2)\n"
                "want = {'all_passed': True, 'exact_count': 1, 'vectors_defined': 16, 'zero_flag': 0}\n"
                "if set(pay.keys()) != set(want.keys()): sys.exit(2)\n"
                "for k, w in want.items():\n"
                "    v = pay[k]\n"
                "    if (type(v) is bool) != (type(w) is bool) or v != w: sys.exit(2)\n"
                "ps = hashlib.sha256(json.dumps(pay, sort_keys=True, separators=(',',':')).encode()).hexdigest()\n"
                "if obj['payload_sha256'] != ps: sys.exit(2)\n"
                "env = {'schema': obj['schema'], 'payload_sha256': ps, 'payload': pay}\n"
                "cs = hashlib.sha256(json.dumps(env, sort_keys=True, separators=(',',':')).encode()).hexdigest()\n"
                "if obj['certificate_sha256'] != cs: sys.exit(2)\n"
                "sys.exit(0)\n",
                encoding="utf-8",
            )
            rep_foil_cli = mod.fuzz_cli_checker(foil_cli, ref_nl)
            self.assertFalse(rep_foil_cli["passed"])
            bypass_vids = {f["vector_id"] for f in rep_foil_cli["findings"] if f["outcome"] == "BYPASS"}
            self.assertIn("ZB08_nonfinite_and_float_literals", bypass_vids)
            self.assertIn("ZB07_duplicate_keys_unicode_escape", bypass_vids)

            # 6. Noisy baseline (rc=0 with ResourceWarning traceback in stderr) reports NOISY_BASELINE
            noisy_cli = root / "noisy_baseline_cli.py"
            noisy_cli.write_text(
                "import sys\n"
                "sys.stderr.write('Traceback (most recent call last):\\nResourceWarning: unclosed file\\n')\n"
                "sys.exit(0)\n",
                encoding="utf-8",
            )
            rep_noisy = mod.fuzz_cli_checker(noisy_cli, ref_nl)
            self.assertFalse(rep_noisy["passed"])
            self.assertFalse(rep_noisy["baseline_ok"])
            self.assertEqual(rep_noisy["status"], "NOISY_BASELINE")
            self.assertEqual(rep_noisy["baseline_rc"], 0)
            self.assertIn("ResourceWarning", rep_noisy["baseline_traceback_tail"])


if __name__ == "__main__":
    unittest.main()
