#!/usr/bin/env python3
"""Track S97 R5 Verification & Adversarial Test Suite (0-skip Lean-less CI).

Zero bare asserts, zero floats, zero .isdigit(), zero random, zero null-device writes.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction

THIS_DIR = pathlib.Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import s97_wse_hc_oracle as oracle
import verify_s97_wse_hc as verifier

CERT_PATH = THIS_DIR / "s97_wse_hc_certificate.json"
LEAN_PATH = THIS_DIR / oracle.LEAN_FILE_NAME
LIVE_RESULTS_PATH = THIS_DIR / oracle.PINNED_LIVE_RESULTS_FILE
MLOS_RECEIPT_PATH = THIS_DIR / oracle.PINNED_MLOS_RECEIPT_FILE
REPORT_PATH = THIS_DIR / "REPORT.md"


def _resign(cert: dict) -> dict:
    c = copy.deepcopy(cert)
    pay = c["payload"]
    p_sha = hashlib.sha256(
        json.dumps(pay, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    c["payload_sha256"] = p_sha
    env = {
        "schema_version": c["schema_version"],
        "payload_sha256": p_sha,
        "payload": pay,
    }
    c["certificate_sha256"] = hashlib.sha256(
        json.dumps(env, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return c


class TestS97OracleAndRationals(unittest.TestCase):
    def test_01_parse_decimal_to_q_and_matrix_ops(self) -> None:
        self.assertEqual(oracle.parse_decimal_to_q(7), Fraction(7, 1))
        self.assertEqual(oracle.parse_decimal_to_q("0"), Fraction(0, 1))
        self.assertEqual(oracle.parse_decimal_to_q("+12.50"), Fraction(25, 2))
        self.assertEqual(oracle.parse_decimal_to_q("-3.25"), Fraction(-13, 4))
        self.assertEqual(oracle.parse_decimal_to_q("1.5e2"), Fraction(150, 1))
        self.assertEqual(oracle.parse_decimal_to_q("1.5E+2"), Fraction(150, 1))
        self.assertEqual(oracle.parse_decimal_to_q("2.5e-2"), Fraction(1, 40))
        self.assertEqual(oracle.parse_decimal_to_q("3e0"), Fraction(3, 1))
        for bad in (None, True, "", "   ", "+", "-", "abc", "1_0", "1e1_0", "1.2.3", "1e", "1e+", "1e-", "1ea", ".5", "5.", "1.a", "9" * 257):
            with self.assertRaises(ValueError):
                oracle.parse_decimal_to_q(bad)
        self.assertTrue(oracle.is_ascii_digits("0123456789"))
        self.assertFalse(oracle.is_ascii_digits(""))
        self.assertFalse(oracle.is_ascii_digits("12a"))
        with self.assertRaises(ValueError):
            oracle.invert_2x2_q([[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]])

    def test_02_oracle_file_guards_and_cli_standalone(self) -> None:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="s97_t_"))
        try:
            real = tmp / "r.json"
            real.write_text('{"a": 1}\n', encoding="utf-8")
            sym = tmp / "s.json"
            sym.symlink_to(real)
            with self.assertRaises(ValueError):
                oracle.load_json_no_floats(sym)
            with self.assertRaises(ValueError):
                oracle.load_json_no_floats(tmp)
            with self.assertRaises(ValueError):
                oracle.write_private_json(sym, {"ok": True})
            bad_list = tmp / "list.json"
            bad_list.write_text("[1,2,3]\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                oracle.load_json_no_floats(bad_list)
            exact_cap = tmp / "exact_cap.json"
            exact_cap.write_bytes(b'{"a":"' + (b"x" * (oracle.MAX_ANCHOR_BYTES - 8)) + b'"}')
            self.assertEqual(len(exact_cap.read_bytes()), oracle.MAX_ANCHOR_BYTES)
            obj_ec, _, _ = oracle.load_json_no_floats(exact_cap)
            self.assertIn("a", obj_ec)
            huge = tmp / "huge.json"
            huge.write_bytes(b'{"a":"' + (b"x" * (oracle.MAX_ANCHOR_BYTES - 7)) + b'"}')
            self.assertEqual(len(huge.read_bytes()), oracle.MAX_ANCHOR_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "size cap"):
                oracle.load_json_no_floats(huge)
            ok_int_80 = tmp / "okint80.json"
            ok_int_80.write_text('{"x": ' + ("9" * 80) + '}\n', encoding="utf-8")
            self.assertEqual(oracle.load_json_no_floats(ok_int_80)[0]["x"], int("9" * 80))
            big_int_anchor = tmp / "bigint.json"
            big_int_anchor.write_text('{"x": ' + ("9" * 81) + '}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digit cap"):
                oracle.load_json_no_floats(big_int_anchor)
            ok_flt_80 = tmp / "okflt80.json"
            ok_flt_80.write_text('{"x": 1.' + ("9" * 78) + '}\n', encoding="utf-8")
            self.assertEqual(len(oracle.load_json_no_floats(ok_flt_80)[0]["x"]), 80)
            big_flt_anchor = tmp / "bigflt.json"
            big_flt_anchor.write_text('{"x": 1.' + ("9" * 79) + '}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "length cap"):
                oracle.load_json_no_floats(big_flt_anchor)

            # Live anchor guard negative cases (M2 strict types + M3 inner result_sha256)
            def _write_resigned_live(obj: dict, path: pathlib.Path) -> None:
                c = copy.deepcopy(obj)
                c.pop("result_sha256", None)
                pre = json.dumps(c, sort_keys=True, separators=(",", ":")).encode("utf-8")
                c["result_sha256"] = hashlib.sha256(pre).hexdigest()
                path.write_text(json.dumps(c, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

            valid_live = json.loads(LIVE_RESULTS_PATH.read_text(encoding="utf-8"), parse_float=str)
            valid_mlos = json.loads(MLOS_RECEIPT_PATH.read_text(encoding="utf-8"), parse_float=str)
            p_live = tmp / "live.json"
            p_mlos = tmp / "mlos.json"
            p_mlos.write_text(json.dumps(valid_mlos), encoding="utf-8")

            # Tampered inner result_sha256 & length/type guards (M2 + M3 + BoolOp killers)
            with self.assertRaises(ValueError):
                oracle._require_strict_str("", "s")
            with self.assertRaises(ValueError):
                oracle._require_strict_str(123, "s")
            with self.assertRaisesRegex(ValueError, "length"):
                oracle._verify_live_inner_result_sha256(b"{}", "short")
            with self.assertRaisesRegex(ValueError, "missing or duplicated"):
                oracle._verify_live_inner_result_sha256(b"{}", "0" * 64)

            bad_sha = copy.deepcopy(valid_live)
            bad_sha["result_sha256"] = "0" * 64
            p_live.write_text(json.dumps(bad_sha, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad_base = copy.deepcopy(valid_live)
            bad_base["baseline"] = []
            _write_resigned_live(bad_base, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad_arms_type = copy.deepcopy(valid_live)
            bad_arms_type["arms"] = {"0": {}, "1": {}, "2": {}, "3": {}}
            _write_resigned_live(bad_arms_type, p_live)
            with self.assertRaisesRegex(ValueError, "4 arms"):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad_arm_elem = copy.deepcopy(valid_live)
            bad_arm_elem["arms"][0] = "not-a-dict"
            _write_resigned_live(bad_arm_elem, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            # Strict bool/int coercion spoofs MUST fail (M2)
            bad_bool = copy.deepcopy(valid_live)
            bad_bool["arms"][0]["backprop_free"] = "false"
            _write_resigned_live(bad_bool, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad_int = copy.deepcopy(valid_live)
            bad_int["arms"][0]["accepted_steps"] = "30"
            _write_resigned_live(bad_int, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad_step = copy.deepcopy(valid_live)
            bad_step["arms"][2]["accepted_steps"] = 999
            _write_resigned_live(bad_step, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad_neg_acc = copy.deepcopy(valid_live)
            bad_neg_acc["arms"][2]["accepted_steps"] = -1
            bad_neg_acc["arms"][2]["rejected_ratchet"] = 25
            _write_resigned_live(bad_neg_acc, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad_neg_rej = copy.deepcopy(valid_live)
            bad_neg_rej["arms"][2]["accepted_steps"] = 25
            bad_neg_rej["arms"][2]["rejected_ratchet"] = -1
            _write_resigned_live(bad_neg_rej, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad1 = copy.deepcopy(valid_live)
            bad1["weights_saved_in_expedition"] = 1
            _write_resigned_live(bad1, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            bad2 = copy.deepcopy(valid_live)
            bad2["arms"] = bad2["arms"][:3]
            _write_resigned_live(bad2, p_live)
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            _write_resigned_live(valid_live, p_live)
            badm1 = copy.deepcopy(valid_mlos)
            badm1["determinism_zone"] = "A"
            p_mlos.write_text(json.dumps(badm1), encoding="utf-8")
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            badm2 = copy.deepcopy(valid_mlos)
            badm2["gpu_telemetry_available"] = False
            p_mlos.write_text(json.dumps(badm2), encoding="utf-8")
            with self.assertRaises(ValueError):
                oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)

            # Zero bp_vram edge branch
            bad3 = copy.deepcopy(valid_live)
            bad3["arms"][0]["peak_vram_alloc_mib"] = "0"
            _write_resigned_live(bad3, p_live)
            p_mlos.write_text(json.dumps(valid_mlos), encoding="utf-8")
            res_zero = oracle.build_pillar_2_live_rtx3080_anchor(p_live, p_mlos)
            self.assertEqual(res_zero["pure_vs_backprop_vram_cut_ratio_q"], {"num": 0, "den": 1})

            # Write private json & standalone CLI parity
            out_c = tmp / "out_cert.json"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = oracle.main(["--out", str(out_c)])
            self.assertEqual(rc, 0)
            self.assertEqual(stat.S_IMODE(out_c.stat().st_mode), 0o600)
            self.assertEqual(out_c.read_bytes(), CERT_PATH.read_bytes())

            proc = subprocess.run(
                [sys.executable, "-I", "-B", str(THIS_DIR / "s97_wse_hc_oracle.py"), "--standalone"],
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, CERT_PATH.read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def _find_upstream_root() -> pathlib.Path | None:
    first_rel = oracle.UPSTREAM_CERT_MANIFEST[0][1]
    if (THIS_DIR.parent / first_rel).is_file():
        return THIS_DIR.parent
    env_root = os.environ.get("S97_EXPEDITION_ROOT", "")
    if env_root and (pathlib.Path(env_root) / first_rel).is_file():
        return pathlib.Path(env_root)
    return None


class TestS97VerifierAndSecurity(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_cert = verifier.strict_json_loads(CERT_PATH.read_text(encoding="utf-8"))

    def test_03_valid_cert_both_replay_modes_and_upstream_pins(self) -> None:
        r1 = verifier.check_certificate_file(CERT_PATH, full_replay=True)
        r0 = verifier.check_certificate_file(CERT_PATH, full_replay=False)
        self.assertTrue(r1["ok"])
        self.assertTrue(r1["full_replay"])
        self.assertTrue(r0["ok"])
        self.assertFalse(r0["full_replay"])
        self.assertEqual(r1["certificate_sha256"], r0["certificate_sha256"])

        with self.assertRaises(verifier.VerifyError) as ctx1:
            verifier.check_certificate_file(THIS_DIR / "nonexistent_m061.json", full_replay=1)  # type: ignore[arg-type]
        self.assertEqual(ctx1.exception.code, "INVALID_FULL_REPLAY")
        with self.assertRaises(verifier.VerifyError) as ctx2:
            verifier.verify_certificate_dict(self.valid_cert, full_replay=1)  # type: ignore[arg-type]
        self.assertEqual(ctx2.exception.code, "INVALID_FULL_REPLAY")

        # Verify all 7 upstream certs on disk when expedition root is present
        up_root = _find_upstream_root()
        if up_root is not None:
            up = verifier.verify_upstream_pins(up_root)
            self.assertEqual(up["matched"], 7)
            self.assertEqual(up["total"], 7)

        tmp = pathlib.Path(tempfile.mkdtemp(prefix="s97_up_"))
        try:
            t_rel = oracle.UPSTREAM_CERT_MANIFEST[0][1]
            t_path = tmp / t_rel
            t_path.parent.mkdir(parents=True, exist_ok=True)
            t_path.write_text('{"tampered": true}\n', encoding="utf-8")
            with self.assertRaises(verifier.VerifyError) as ctx_u:
                verifier.verify_upstream_pins(tmp)
            self.assertEqual(ctx_u.exception.code, "UPSTREAM_SHA_MISMATCH")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_04_strict_json_and_tree_defenses(self) -> None:
        # Exact depth boundary == MAX_JSON_DEPTH passes; +1 fails (kills M011)
        exact_nested = "[" * verifier.MAX_JSON_DEPTH + "1" + "]" * verifier.MAX_JSON_DEPTH
        self.assertIsInstance(verifier.strict_json_loads(exact_nested), list)
        nested = "[" * (verifier.MAX_JSON_DEPTH + 1) + "1" + "]" * (verifier.MAX_JSON_DEPTH + 1)
        with self.assertRaises(verifier.VerifyError) as c_dep:
            verifier.strict_json_loads(nested)
        self.assertEqual(c_dep.exception.code, "JSON_MAX_DEPTH")

        # is_hex64 & subclass defenses (kills L110, L122, L161, L218 BoolOps)
        self.assertFalse(verifier.is_hex64(["a"] * 64))
        self.assertFalse(verifier.is_hex64("a" * 63))
        self.assertTrue(verifier.is_hex64("a" * 64))

        class EvilDict(dict):
            pass

        with self.assertRaises(verifier.VerifyError) as c_ed1:
            verifier.parse_qdict(EvilDict({"num": 1, "den": 1}), "q")
        self.assertEqual(c_ed1.exception.code, "INVALID_RATIONAL_DICT")
        with self.assertRaises(verifier.VerifyError) as c_ed2:
            verifier._require_keys(EvilDict({"a": 1}), {"a"}, "k")
        self.assertEqual(c_ed2.exception.code, "SCHEMA_KEYS_MISMATCH")

        # Tree-level rational dict detection on partial num/den keys (kills L161 BoolOp)
        verifier.scan_json_tree_iterative({"plain": 1})
        with self.assertRaises(verifier.VerifyError) as c_tn:
            verifier.scan_json_tree_iterative({"num": 1, "other": 2})
        self.assertEqual(c_tn.exception.code, "INVALID_RATIONAL_DICT")
        with self.assertRaises(verifier.VerifyError) as c_td:
            verifier.scan_json_tree_iterative({"other": 1, "den": 2})
        self.assertEqual(c_td.exception.code, "INVALID_RATIONAL_DICT")

        # Exact MAX_INT_BITS boundary via strict_json_loads
        self.assertEqual(
            verifier.strict_json_loads('{"ok": ' + str((1 << verifier.MAX_INT_BITS) - 1) + "}")["ok"],
            (1 << verifier.MAX_INT_BITS) - 1,
        )

        # Deep in-memory object (>1000 depth) must not trigger RecursionError
        deep_obj: list = []
        cur = deep_obj
        for _ in range(50):
            nxt: list = []
            cur.append(nxt)
            cur = nxt
        with self.assertRaises(verifier.VerifyError) as c_deep:
            verifier.scan_json_tree_iterative(deep_obj)
        self.assertEqual(c_deep.exception.code, "JSON_MAX_DEPTH")

        # Parser recursion limit test
        very_deep = "[" * 1500 + "]" * 1500
        with self.assertRaises(verifier.VerifyError):
            verifier.strict_json_loads(very_deep)

        for raw, exp_code in (
            ('{"a": 1.5}', "FLOAT_FORBIDDEN"),
            ('{"a": NaN}', "NON_FINITE_JSON"),
            ('{"a": Infinity}', "NON_FINITE_JSON"),
            ('{"a": 1, "a": 2}', "DUPLICATE_JSON_KEY"),
            ("{" + '"x": ' + ("9" * (verifier.MAX_INT_DIGITS + 1)) + "}", "INT_DIGIT_LIMIT"),
            ("{" + '"x": -' + str(1 << verifier.MAX_INT_BITS) + "}", "INT_BIT_LIMIT"),
            ("{bad json", "INVALID_JSON"),
        ):
            with self.assertRaises(verifier.VerifyError) as ctx:
                verifier.strict_json_loads(raw)
            self.assertEqual(ctx.exception.code, exp_code)

        # In-memory boundary checks (2**8192 - 1 allowed, 2**8192 rejected)
        verifier.scan_json_tree_iterative({"ok": (1 << verifier.MAX_INT_BITS) - 1, "n": None, "b": True})
        with self.assertRaises(verifier.VerifyError) as c_bit:
            verifier.scan_json_tree_iterative({"bad": 1 << verifier.MAX_INT_BITS})
        self.assertEqual(c_bit.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(verifier.VerifyError) as c_flt:
            verifier.scan_json_tree_iterative({"bad": 1.25})
        self.assertEqual(c_flt.exception.code, "FLOAT_FORBIDDEN")
        with self.assertRaises(verifier.VerifyError) as c_sur1:
            verifier.scan_json_tree_iterative({"bad": "\ud800"})
        self.assertEqual(c_sur1.exception.code, "INVALID_SURROGATE")
        with self.assertRaises(verifier.VerifyError) as c_sur2:
            verifier.scan_json_tree_iterative({"\udfff": 1})
        self.assertEqual(c_sur2.exception.code, "INVALID_SURROGATE")
        with self.assertRaises(verifier.VerifyError) as c_nsk:
            verifier.scan_json_tree_iterative({1: "x"})  # type: ignore[dict-item]
        self.assertEqual(c_nsk.exception.code, "NON_STRING_KEY")
        with self.assertRaises(verifier.VerifyError) as c_ut:
            verifier.scan_json_tree_iterative((1, 2))
        self.assertEqual(c_ut.exception.code, "UNSUPPORTED_TYPE")

        # Strict 2-key coprime rational dict checks (S87-F1 class!)
        for bad_q, code in (
            ({"num": 1, "den": 2, "extra": 0}, "INVALID_RATIONAL_DICT"),
            ({"num": 1, "other": 2}, "INVALID_RATIONAL_DICT"),
            ({"other": 1, "den": 2}, "INVALID_RATIONAL_DICT"),
            ({"num": True, "den": 1}, "INVALID_RATIONAL_TYPE"),
            ({"num": 1, "den": False}, "INVALID_RATIONAL_TYPE"),
            ({"num": 1 << verifier.MAX_INT_BITS, "den": 1}, "INT_BIT_LIMIT"),
            ({"num": 1, "den": (1 << verifier.MAX_INT_BITS) + 1}, "INT_BIT_LIMIT"),
            ({"num": 1, "den": 0}, "INVALID_RATIONAL_DEN"),
            ({"num": 1, "den": -2}, "INVALID_RATIONAL_DEN"),
            ({"num": 2, "den": 4}, "NON_COPRIME_RATIONAL"),
        ):
            with self.assertRaises(verifier.VerifyError) as ctx:
                verifier.parse_qdict(bad_q, "q")
            self.assertEqual(ctx.exception.code, code)

    def test_05_non_hollow_resigned_semantic_tampers(self) -> None:
        # Hash mismatch checks
        bad_pay_sha = copy.deepcopy(self.valid_cert)
        bad_pay_sha["payload_sha256"] = "0" * 64
        with self.assertRaises(verifier.VerifyError) as c1:
            verifier.verify_certificate_dict(bad_pay_sha, full_replay=False)
        self.assertEqual(c1.exception.code, "PAYLOAD_SHA_MISMATCH")

        bad_cert_sha = copy.deepcopy(self.valid_cert)
        bad_cert_sha["certificate_sha256"] = "0" * 64
        with self.assertRaises(verifier.VerifyError) as c2:
            verifier.verify_certificate_dict(bad_cert_sha, full_replay=False)
        self.assertEqual(c2.exception.code, "CERT_SHA_MISMATCH")

        bad_hex = copy.deepcopy(self.valid_cert)
        bad_hex["payload_sha256"] = "Z" * 64
        with self.assertRaises(verifier.VerifyError) as c3:
            verifier.verify_certificate_dict(bad_hex, full_replay=False)
        self.assertEqual(c3.exception.code, "INVALID_SHA_FORMAT")

        bad_hex2 = copy.deepcopy(self.valid_cert)
        bad_hex2["certificate_sha256"] = "Z" * 64
        with self.assertRaises(verifier.VerifyError) as c3b:
            verifier.verify_certificate_dict(bad_hex2, full_replay=False)
        self.assertEqual(c3b.exception.code, "INVALID_SHA_FORMAT")

        # Re-signed semantic tampers MUST fail in BOTH full_replay=False AND secondary_audit_payload!
        def _mutate_and_check(mutator, exp_code: str) -> None:
            cand = copy.deepcopy(self.valid_cert)
            mutator(cand["payload"])
            rs = _resign(cand)
            with self.assertRaises(verifier.VerifyError) as c_sec:
                verifier.secondary_audit_payload(rs["payload"])
            self.assertEqual(c_sec.exception.code, exp_code)
            with self.assertRaises(verifier.VerifyError) as c_fr0:
                verifier.verify_certificate_dict(rs, full_replay=False)
            self.assertEqual(c_fr0.exception.code, exp_code)

        _mutate_and_check(lambda p: p["pillar_1a_subspace_collapse"].__setitem__("snr_lift_full_q", {"num": 1175, "den": 1}), "ALGEBRAIC_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_1b_discrete_oracle"].__setitem__("step_oracle_jump_gain", 2), "VALUE_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_1c_ratchet_and_nullspace"].__setitem__("nullspace_projected_forgetting_energy_q", {"num": 1, "den": 1}), "ALGEBRAIC_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_1d_recursive_relinearization"].__setitem__("recursive_relinearized_err_fro_sq_q", {"num": 1, "den": 2}), "ALGEBRAIC_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"].__setitem__("mlos_clean_hardware_run", 1), "VALUE_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"].__setitem__("gpu_name", ""), "VALUE_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"].__setitem__("baseline_wiki_test_ppl_q", {"num": 1, "den": 1}), "INVALID_BASELINE_RANGE")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"].__setitem__("arms", p["pillar_2_live_rtx3080_anchor"]["arms"][:3]), "INVALID_ARMS_LIST")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("arm", "WrongArm"), "ARM_ORDER_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("backprop_free", 0), "ARM_FIELD_TYPE")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("accepted_steps", -1), "ARM_NEG_STEPS")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("heldout_acc_gain_q", {"num": 99, "den": 1}), "ALGEBRAIC_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("wiki_test_nll_drift_q", {"num": 99, "den": 1}), "ALGEBRAIC_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("wiki_test_ppl_drift_q", {"num": 99, "den": 1}), "ALGEBRAIC_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("peak_vram_alloc_mib_q", {"num": 0, "den": 1}), "ARM_RANGE_INVALID")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"].__setitem__("pure_vs_backprop_vram_cut_mib_q", {"num": 0, "den": 1}), "ALGEBRAIC_MISMATCH")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("wall_time_sec_q", {"num": 1, "den": 1}), "ANCHOR_DIGEST_MISMATCH")
        _mutate_and_check(lambda p: p["lean4_certificate"].__setitem__("theorem_count", 17), "VALUE_MISMATCH")
        # Additional verifier BoolOp killers (arm total/rejected/type, v_res < v_alloc, non-list um, bad cli arg types)
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"].__setitem__("arms", {"0": {}, "1": {}, "2": {}, "3": {}}), "INVALID_ARMS_LIST")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("total_steps", True), "ARM_FIELD_TYPE")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("accepted_steps", True), "ARM_FIELD_TYPE")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("rejected_steps", True), "ARM_FIELD_TYPE")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].update({"total_steps": 0, "accepted_steps": 0, "rejected_steps": 0}), "ARM_NEG_STEPS")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].update({"total_steps": 29, "accepted_steps": -1, "rejected_steps": 30}), "ARM_NEG_STEPS")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].update({"total_steps": 29, "accepted_steps": 30, "rejected_steps": -1}), "ARM_NEG_STEPS")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("accepted_steps", 1), "ARM_NEG_STEPS")
        _mutate_and_check(lambda p: p["pillar_2_live_rtx3080_anchor"]["arms"][0].__setitem__("peak_vram_reserved_mib_q", {"num": 1, "den": 1}), "ARM_RANGE_INVALID")
        _mutate_and_check(lambda p: p["upstream_cert_manifest"].pop(), "UPSTREAM_MANIFEST_LEN")
        _mutate_and_check(lambda p: p.__setitem__("upstream_cert_manifest", {str(i): {} for i in range(7)}), "UPSTREAM_MANIFEST_LEN")
        with self.assertRaises(verifier.VerifyError) as c_a1:
            verifier._parse_cli_args(["--check", 123])
        self.assertEqual(c_a1.exception.code, "INVALID_ARG")
        with self.assertRaises(verifier.VerifyError) as c_a2:
            verifier._parse_cli_args([123])
        self.assertEqual(c_a2.exception.code, "INVALID_ARG")
        with self.assertRaises(verifier.VerifyError) as c_a3:
            verifier._parse_cli_args(["bad\x00flag"])
        self.assertEqual(c_a3.exception.code, "INVALID_ARG")
        with self.assertRaises(verifier.VerifyError) as c_a4:
            verifier._parse_cli_args(["--check", ""])
        self.assertEqual(c_a4.exception.code, "INVALID_PATH_ARG")
        with self.assertRaises(verifier.VerifyError) as c_a5:
            verifier._parse_cli_args(["--check", "a\x00b"])
        self.assertEqual(c_a5.exception.code, "INVALID_PATH_ARG")
        opts_ln = verifier._parse_cli_args(["--verify-lean"])
        self.assertIsNone(opts_ln["check"])
        self.assertEqual(opts_ln["verify_lean"], str(LEAN_PATH))
        self.assertIsNone(opts_ln["verify_upstream"])
        opts_up = verifier._parse_cli_args(["--verify-upstream", str(THIS_DIR)])
        self.assertIsNone(opts_up["check"])
        self.assertEqual(opts_up["verify_upstream"], str(THIS_DIR))
        with self.assertRaises(verifier.VerifyError) as c_mu:
            verifier._parse_cli_args(["--verify-upstream"])
        self.assertEqual(c_mu.exception.code, "MISSING_PATH_ARG")
        _mutate_and_check(lambda p: p["novelty_honesty_law4"].__setitem__("n2_claims", 1), "VALUE_MISMATCH")
        _mutate_and_check(lambda p: p["novelty_honesty_law4"].__setitem__("extra", 1), "SCHEMA_KEYS_MISMATCH")

        # Full replay failure paths (REPLAY_BUILD_FAILED on missing/corrupt track_dir + FULL_REPLAY_MISMATCH)
        tmp_rep = pathlib.Path(tempfile.mkdtemp(prefix="s97_rep_"))
        try:
            with self.assertRaises(verifier.VerifyError) as c_rb:
                verifier.verify_certificate_dict(self.valid_cert, full_replay=True, track_dir=tmp_rep)
            self.assertEqual(c_rb.exception.code, "REPLAY_BUILD_FAILED")

            # Valid live file with altered timing -> oracle replays a different cert -> FULL_REPLAY_MISMATCH
            live_mod = json.loads(LIVE_RESULTS_PATH.read_text(encoding="utf-8"), parse_float=str)
            live_mod["arms"][0]["wall_time_sec"] = "5.0"
            live_mod.pop("result_sha256", None)
            pre = json.dumps(live_mod, sort_keys=True, separators=(",", ":")).encode("utf-8")
            live_mod["result_sha256"] = hashlib.sha256(pre).hexdigest()
            (tmp_rep / oracle.PINNED_LIVE_RESULTS_FILE).write_text(
                json.dumps(live_mod, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
            )
            shutil.copy2(MLOS_RECEIPT_PATH, tmp_rep / oracle.PINNED_MLOS_RECEIPT_FILE)
            with self.assertRaises(verifier.VerifyError) as c_mm:
                verifier.verify_certificate_dict(self.valid_cert, full_replay=True, track_dir=tmp_rep)
            self.assertEqual(c_mm.exception.code, "FULL_REPLAY_MISMATCH")
        finally:
            shutil.rmtree(tmp_rep, ignore_errors=True)

    def test_06_file_io_symlinks_fifo_size_and_cli_parsing(self) -> None:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="s97_io_"))
        try:
            with self.assertRaises(verifier.VerifyError) as c_nul:
                verifier.read_regular_file_bytes(pathlib.Path("bad\x00path"), 1024, "x")
            self.assertEqual(c_nul.exception.code, "NULL_BYTE_PATH")
            with self.assertRaises(verifier.VerifyError) as c_miss:
                verifier.read_regular_file_bytes(tmp / "nope.json", 1024, "x")
            self.assertEqual(c_miss.exception.code, "FILE_MISSING")
            with self.assertRaises(verifier.VerifyError) as c_dir:
                verifier.read_regular_file_bytes(tmp, 1024, "x")
            self.assertEqual(c_dir.exception.code, "NOT_REGULAR_FILE")

            real = tmp / "real.json"
            real.write_text('{"a": 1}\n', encoding="utf-8")
            sym = tmp / "sym.json"
            sym.symlink_to(real)
            with self.assertRaises(verifier.VerifyError) as c_sym:
                verifier.read_regular_file_bytes(sym, 1024, "x")
            self.assertEqual(c_sym.exception.code, "SYMLINK_FORBIDDEN")

            sub = tmp / "sub"
            sub.mkdir()
            (sub / "f.json").write_text('{"a": 1}\n', encoding="utf-8")
            sym_dir = tmp / "symdir"
            sym_dir.symlink_to(sub)
            with self.assertRaises(verifier.VerifyError) as c_sdir:
                verifier.read_regular_file_bytes(sym_dir / "f.json", 1024, "x")
            self.assertEqual(c_sdir.exception.code, "SYMLINK_FORBIDDEN")

            fifo = tmp / "pipe.fifo"
            os.mkfifo(fifo)
            with self.assertRaises(verifier.VerifyError) as c_fifo:
                verifier.read_regular_file_bytes(fifo, 1024, "x")
            self.assertEqual(c_fifo.exception.code, "NOT_REGULAR_FILE")

            exact_b = tmp / "exact.bin"
            exact_b.write_bytes(b"a" * 100)
            self.assertEqual(len(verifier.read_regular_file_bytes(exact_b, 100, "x")), 100)
            big = tmp / "big.json"
            big.write_bytes(b"a" * 101)
            with self.assertRaises(verifier.VerifyError) as c_big:
                verifier.read_regular_file_bytes(big, 100, "x")
            self.assertEqual(c_big.exception.code, "FILE_TOO_LARGE")

            unreadable = tmp / "unreadable.json"
            unreadable.write_bytes(b"{}\n")
            os.chmod(unreadable, 0o000)
            try:
                if os.geteuid() != 0:
                    with self.assertRaises(verifier.VerifyError) as c_ur:
                        verifier.read_regular_file_bytes(unreadable, 100, "x")
                    self.assertEqual(c_ur.exception.code, "FILE_OPEN_ERROR")
            finally:
                os.chmod(unreadable, 0o600)

            bad_utf8 = tmp / "bad.bin"
            bad_utf8.write_bytes(b"\xff\xfe")
            with self.assertRaises(verifier.VerifyError) as c_u8:
                verifier.check_certificate_file(bad_utf8, full_replay=False)
            self.assertEqual(c_u8.exception.code, "INVALID_UTF8")

            crlf_c = tmp / "crlf.json"
            crlf_c.write_bytes(CERT_PATH.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaises(verifier.VerifyError) as c_cr:
                verifier.check_certificate_file(crlf_c, full_replay=False)
            self.assertEqual(c_cr.exception.code, "CRLF_FORBIDDEN")

            pretty_c = tmp / "pretty.json"
            pretty_c.write_text(json.dumps(self.valid_cert, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(verifier.VerifyError) as c_pr:
                verifier.check_certificate_file(pretty_c, full_replay=False)
            self.assertEqual(c_pr.exception.code, "NON_CANONICAL_JSON")

            # CLI parser & main exit codes (captured streams keep R4 3-mode stdout bit-identical)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verifier.main(["--check", str(CERT_PATH), "--json"]), 0)
                self.assertEqual(verifier.main(["--check", "--no-replay"]), 0)
                self.assertEqual(verifier.main([]), 0)
                up_root = _find_upstream_root()
                if up_root is not None:
                    self.assertEqual(verifier.main(["--verify-upstream", str(up_root), "--json"]), 0)
                self.assertEqual(verifier.main(["--verify-upstream", str(tmp), "--json"]), 2)
                self.assertEqual(verifier.main(["--unknown"]), 2)
                self.assertEqual(verifier.main(["--json", "--json"]), 2)
                self.assertEqual(verifier.main(["--no-replay", "--no-replay"]), 2)
                self.assertEqual(verifier.main(["--check", "--check"]), 2)
                self.assertEqual(verifier.main(["--verify-upstream"]), 2)
                self.assertEqual(verifier.main(["--check", ""]), 2)
                self.assertEqual(verifier.main(["--check", "a\x00b"]), 2)
                self.assertEqual(verifier.main(["--check", str(tmp / "missing.json"), "--json"]), 2)
            with self.assertRaises(verifier.VerifyError) as c_nl:
                verifier._parse_cli_args("not-a-list")
            self.assertEqual(c_nl.exception.code, "INVALID_ARGV")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestS97LeanR10AndHygiene(unittest.TestCase):
    def test_07_r11_static_scanner_probes_and_zero_fp(self) -> None:
        # Clean positive controls (0 FP)
        positive_controls = [
            "theorem t_ok : 1 + 1 = 2 := by decide (native := false)\n",
            "theorem t_ok_b : 1 + 1 = 2 := by decide (native := Bool.false)\n",
            "theorem t_ok2 : 1 = 1 := by\n  decide (native := false\n)\n",
            "export Nat (succ)\ntheorem t_exp : succ 0 = 1 := rfl\n",
            "/- outer /- sorry native_decide axiom import \"x\" -/ still comment -/\n-- sorry\ntheorem t_c : 1 = 1 := rfl\n",
            "theorem t_end : 1 = 1 := by decide (native := false, revert := true)\n",
        ]
        for src in positive_controls:
            self.assertEqual(verifier.scan_lean_source_r10(src), [], f"FP on: {src!r}")

        # 60 adversarial R11 trust-escape probes MUST be rejected!
        probes = [
            "import Lean\n",
            "public import Init\n",
            "private import Mathlib\n",
            "theorem t : True := by sorry\n",
            "theorem t : True := by admit\n",
            "def x := sorryAx\n",
            "def x := _root_.sorryAx\n",
            "def x := warn.sorry\n",
            "def x := mkSorry\n",
            "axiom bad : False\n",
            "constant bad : Nat\n",
            "opaque bad : Nat := 0\n",
            "unsafe def f := 0\n",
            "partial def f : Nat -> Nat | n => f n\n",
            "@[implemented_by x] def f := 0\n",
            "@[extern \"c\"] def f := 0\n",
            "@[csimp] theorem t : 1 = 1 := rfl\n",
            "def d := dbg_trace 0 (fun _ => 0)\n",
            "def d := dbg_sleep 1 (fun _ => 0)\n",
            "def d := dbg_stack_trace 0\n",
            "def d := dbgTrace 0 (fun _ => 0)\n",
            "def d := dbgTraceVal 0\n",
            "def d := dbgTraceValId 0\n",
            "def d := dbgTraceIfShared 0 0\n",
            "def d := dbgSleep 1 (fun _ => 0)\n",
            "def d := dbgStackTrace 0\n",
            "def p := panic! 0\n",
            "def u := unreachable!\n",
            "#guard 1 = 1\n",
            "@[export foo] def f := 0\n",
            "@[init] def f := pure ()\n",
            "@[builtin_init] def f := pure ()\n",
            "@[term_elab t] def f := 0\n",
            "@[command_elab c] def f := 0\n",
            "@[tactic t] def f := 0\n",
            "attribute [export foo] f\n",
            "theorem t : 1 = 1 := by native_decide\n",
            "theorem t : 1 = 1 := by bv_decide\n",
            "theorem t : 1 = 1 := by decide (native := true)\n",
            "theorem t : 1 = 1 := by decide (native := false || true)\n",
            "theorem t : 1 = 1 := by decide (native := false\n  || true)\n",
            "theorem t : 1 = 1 := by decide (native := false == false)\n",
            "theorem t : 1 = 1 := by decide (native := false != true)\n",
            "theorem t : 1 = 1 := by decide (native := false.not)\n",
            "theorem t : 1 = 1 := by decide (native := !false)\n",
            "theorem t : 1 = 1 := by decide (native := (true))\n",
            "theorem t : 1 = 1 := by decide +revert +native\n",
            "theorem t : 1 = 1 := by decide (config := { native := true })\n",
            "set_option maxHeartbeats 0\n",
            "#exit\n",
            "#guard_msgs in theorem t : 1 = 1 := rfl\n",
            "def x := debug.terminalTacticsAsSorry\n",
            "run_cmd pure ()\n",
            "run_meta pure ()\n",
            "elab \"x\" : term => pure ()\n",
            "elab_rules | `(t) => pure ()\n",
            "macro \"x\" : term => `(0)\n",
            "macro_rules | `(t) => `(0)\n",
            "syntax \"x\" : term\n",
            "declare_syntax_cat mycat\n",
            "notation x => x\n",
            "prefix:50 x => x\n",
            "infixl:50 x => x\n",
            "postfix:50 x => x\n",
            "attribute [implemented_by f] g\n",
            'def s := "escaped"\n',
            "def «guill» := 0\n",
            "def x := Lean.ofReduceBool\n",
            "def x := Lean.ofReduceNat\n",
            "def x := Lean.trustCompiler\n",
            "def x := Lean.Elab.Command.elabCommand\n",
            "def c : Char := '\"'\n",
            "def x := lcProof\n",
            "def x := Classical.choice\n",
        ]
        self.assertEqual(len(probes), 74)
        for p in probes:
            hits = verifier.scan_lean_source_r10(p)
            self.assertTrue(len(hits) >= 1, f"Scanner missed probe: {p!r}")

        with self.assertRaises(verifier.VerifyError) as c_uc:
            verifier.scan_lean_source_r10("/- unclosed")
        self.assertEqual(c_uc.exception.code, "LEAN_UNCLOSED_COMMENT")
        with self.assertRaises(verifier.VerifyError) as c_crlf:
            verifier.scan_lean_source_r10("theorem t : 1 = 1 := rfl\r\n")
        self.assertEqual(c_crlf.exception.code, "LEAN_CRLF")

    def test_08_lean_live_and_zero_skip_leanless_ci(self) -> None:
        # Strict bool check on check_pinned_sha (S87-F3)
        with self.assertRaises(verifier.VerifyError) as c_bool:
            verifier.verify_lean_file(LEAN_PATH, check_pinned_sha=1)  # type: ignore[arg-type]
        self.assertEqual(c_bool.exception.code, "INVALID_CHECK_PINNED_SHA")

        tmp = pathlib.Path(tempfile.mkdtemp(prefix="s97_ln_"))
        try:
            # 0-theorem Lean file MUST fail even when check_pinned_sha=False (S87-F3)
            empty_lean = tmp / "Empty.lean"
            empty_lean.write_text("def x : Nat := 1\n", encoding="utf-8")
            with self.assertRaises(verifier.VerifyError) as c_nt:
                verifier.verify_lean_file(empty_lean, check_pinned_sha=False)
            self.assertEqual(c_nt.exception.code, "LEAN_NO_THEOREMS_VERIFIED")

            # Pinned SHA mismatch rejected
            with self.assertRaises(verifier.VerifyError) as c_sha:
                verifier.verify_lean_file(empty_lean, check_pinned_sha=True)
            self.assertEqual(c_sha.exception.code, "LEAN_SHA_MISMATCH")

            # Invalid UTF-8 rejected
            bad_u8 = tmp / "Bad.lean"
            bad_u8.write_bytes(b"\xff\xfe")
            with self.assertRaises(verifier.VerifyError) as c_u8:
                verifier.verify_lean_file(bad_u8, check_pinned_sha=False)
            self.assertEqual(c_u8.exception.code, "LEAN_INVALID_UTF8")

            # Static escape rejected even before invoking lean binary
            esc = tmp / "Esc.lean"
            esc.write_text("theorem t : True := by sorry\n", encoding="utf-8")
            with self.assertRaises(verifier.VerifyError) as c_esc:
                verifier.verify_lean_file(esc, check_pinned_sha=False)
            self.assertEqual(c_esc.exception.code, "LEAN_STATIC_ESCAPE")

            # Live Lean vs Lean-less CI (ZERO skips!)
            lean_bin = verifier.resolve_lean_binary()
            if lean_bin is not None:
                res = verifier.verify_lean_file(LEAN_PATH, check_pinned_sha=True)
                self.assertTrue(res["ok"])
                self.assertEqual(res["theorem_count"], 18)
                self.assertEqual(res["axioms_used"], ["Quot.sound", "propext"])

                # Unpinned valid 1-theorem file passes (including protected theorem discovery!)
                one_thm = tmp / "One.lean"
                one_thm.write_text("namespace OneNS\nprotected theorem t1 (n : Nat) : n = n := rfl\nend OneNS\n", encoding="utf-8")
                r_one = verifier.verify_lean_file(one_thm, check_pinned_sha=False)
                self.assertEqual(r_one["theorem_count"], 1)
                self.assertEqual(r_one["axioms_used"], [])

                # Warning on stderr with rc=0 MUST fail closed (kills proc1.stderr BoolOp)
                warn_pf = tmp / "Warn.lean"
                warn_pf.write_text("theorem tw (unused_var : Nat) : 1 = 1 := rfl\n", encoding="utf-8")
                with self.assertRaises(verifier.VerifyError) as c_wn:
                    verifier.verify_lean_file(warn_pf, check_pinned_sha=False)
                self.assertEqual(c_wn.exception.code, "LEAN_ELAB_FAILED")

                # Private theorem using Classical.choice MUST be discovered and rejected (H1)!
                priv_cc = tmp / "PrivChoice.lean"
                priv_cc.write_text(
                    "private theorem sneak : ∀ P : Prop, P ∨ ¬P := fun P => by by_cases h : P; exact Or.inl h; exact Or.inr h\n"
                    "theorem ok1 : 1 = 1 := rfl\n",
                    encoding="utf-8",
                )
                with self.assertRaises(verifier.VerifyError) as c_pcc:
                    verifier.verify_lean_file(priv_cc, check_pinned_sha=False)
                self.assertEqual(c_pcc.exception.code, "LEAN_BANNED_AXIOM")

                # Broken proof fails elaboration
                bad_pf = tmp / "BadProof.lean"
                bad_pf.write_text("theorem bad : 1 = 2 := rfl\n", encoding="utf-8")
                with self.assertRaises(verifier.VerifyError) as c_el:
                    verifier.verify_lean_file(bad_pf, check_pinned_sha=False)
                self.assertEqual(c_el.exception.code, "LEAN_ELAB_FAILED")

                # Test resolve_lean_binary fallback + mock lean failure modes (kills L713, L766, M074, M077, M080)
                old_path = os.environ.get("PATH")
                old_home = os.environ.get("HOME")
                fake_home = tmp / "fakehome"
                fake_bin = fake_home / ".elan" / "bin" / "lean"
                fake_bin.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.environ["PATH"] = str(tmp / "empty_path")
                    os.environ["HOME"] = str(fake_home)
                    # Directory named lean (+x but not file -> kills L713 SUBCOND_DEL[0])
                    fake_bin.mkdir()
                    self.assertIsNone(verifier.resolve_lean_binary())
                    fake_bin.rmdir()
                    # Missing binary fails closed with LEAN_BINARY_NOT_FOUND (kills M074)
                    with self.assertRaises(verifier.VerifyError) as c_nf:
                        verifier.verify_lean_file(one_thm, check_pinned_sha=False)
                    self.assertEqual(c_nf.exception.code, "LEAN_BINARY_NOT_FOUND")
                    # Non-executable file ignored
                    fake_bin.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
                    os.chmod(fake_bin, 0o600)
                    self.assertIsNone(verifier.resolve_lean_binary())
                    # Mock lean exiting rc=1 with silent stdout/stderr -> kills L766 SUBCOND_DEL[0]
                    os.chmod(fake_bin, 0o700)
                    self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
                    with self.assertRaises(verifier.VerifyError) as c_sil:
                        verifier.verify_lean_file(one_thm, check_pinned_sha=False)
                    self.assertEqual(c_sil.exception.code, "LEAN_ELAB_FAILED")
                    # Mock lean succeeding on Verified.lean, failing rc=1 on Audit.lean -> kills M077
                    fake_bin.write_text(
                        '#!/bin/sh\ncase "$1" in *Audit.lean) exit 1;; *) exit 0;; esac\n',
                        encoding="utf-8",
                    )
                    os.chmod(fake_bin, 0o700)
                    with self.assertRaises(verifier.VerifyError) as c_af:
                        verifier.verify_lean_file(one_thm, check_pinned_sha=False)
                    self.assertEqual(c_af.exception.code, "LEAN_AXIOM_AUDIT_FAILED")
                    # Mock lean returning rc=0 with empty stdout on Audit.lean -> kills M080
                    fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                    os.chmod(fake_bin, 0o700)
                    with self.assertRaises(verifier.VerifyError) as c_ms:
                        verifier.verify_lean_file(one_thm, check_pinned_sha=False)
                    self.assertEqual(c_ms.exception.code, "LEAN_MISSING_AXIOM_REPORT")
                finally:
                    if old_path is None:
                        os.environ.pop("PATH", None)
                    else:
                        os.environ["PATH"] = old_path
                    if old_home is None:
                        os.environ.pop("HOME", None)
                    else:
                        os.environ["HOME"] = old_home
            else:
                # Lean-less CI: MUST fail closed deterministically (ZERO skips!)
                with self.assertRaises(verifier.VerifyError) as c_nb:
                    verifier.verify_lean_file(LEAN_PATH, check_pinned_sha=True)
                self.assertEqual(c_nb.exception.code, "LEAN_BINARY_NOT_FOUND")
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(verifier.main(["--verify-lean"]), 2)
                if os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
                    self.fail("ALETHEIA_REQUIRE_LEAN=1 set but Lean binary unavailable")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_09_hygiene_no_leaks_crlf_or_forbidden_phrases(self) -> None:
        bad_four = "".join(["4", "-", "mode"])
        bad_home = "".join(["/", "home", "/"])
        bad_null = "".join(["/", "dev", "/", "null"])
        for p in sorted(THIS_DIR.iterdir()):
            if not p.is_file():
                continue
            raw = p.read_bytes()
            self.assertNotIn(b"\r\n", raw, f"CRLF in {p.name}")
            txt = raw.decode("utf-8")
            self.assertNotIn(bad_home, txt, f"home path leak in {p.name}")
            self.assertNotIn(bad_null, txt, f"null device literal in {p.name}")
            if p.name == "REPORT.md":
                self.assertIsNone(re.search(bad_four, txt, re.IGNORECASE), "forbidden R4 phrase in REPORT.md")


if __name__ == "__main__":
    unittest.main(verbosity=2)
