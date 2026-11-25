#!/usr/bin/env python3
"""
Track S95: Assertion-Free R5 Hardening, Law-3 Router, Re-Signed Forgery, & R12 Lean Test Suite.

Pure Python 3 stdlib. Zero bare asserts, zero floats, zero special-device-null literals,
zero skips under bare `env -i PATH=/usr/bin:/bin` Lean-less CI.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from typing import Any

TRACK_DIR = Path(__file__).resolve().parent
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import aletheia_specialist_router as router  # noqa: E402
import s95_specialist_foundry_oracle as s95  # noqa: E402
import verify_s95_specialist_foundry as v  # noqa: E402


def _resign(cert: dict) -> dict:
    c = copy.deepcopy(cert)
    psha = hashlib.sha256(s95.canonical_json_bytes(c["payload"])).hexdigest()
    c["payload_sha256"] = psha
    env = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": psha,
        "payload": c["payload"],
    }
    c["certificate_sha256"] = hashlib.sha256(s95.canonical_json_bytes(env)).hexdigest()
    return c


def _has_lean() -> bool:
    try:
        v._find_lean_binary()
        return True
    except s95.S95Error:
        return False


class TestOracleAndArtifacts(unittest.TestCase):
    def test_01_oracle_math_and_budget_boundaries(self) -> None:
        self.assertEqual(s95.matched_qwen_adapter_params(), 8798208)
        for kwargs in (
            {"layers": 0},
            {"hidden": 0},
            {"kv_dim": 0},
            {"intermediate": 0},
            {"budget_s": 0},
        ):
            with self.assertRaises(s95.S95Error) as ctx:
                s95.matched_qwen_adapter_params(**kwargs)
            self.assertEqual(ctx.exception.code, "BAD_ARCH_DIM")
        self.assertEqual(s95.compute_f1_exact(0, 0, 0), Fraction(0))
        self.assertEqual(s95.compute_f1_exact(36, 0, 0), Fraction(1))
        self.assertEqual(s95.compute_f1_exact(36, 8, 0), Fraction(9, 10))
        self.assertEqual(s95.fmt_q(Fraction(5, 1)), "5")
        self.assertEqual(s95.fmt_q(Fraction(2, 33)), "2/33")
        self.assertEqual(s95.fmt_dec(Fraction(2, 33), 4), "0.0606")

    def test_02_certificate_replay_and_live_artifacts(self) -> None:
        cert = s95.build_certificate()
        self.assertEqual(cert["schema_version"], s95.SCHEMA_VERSION)
        self.assertEqual(cert["track_id"], s95.TRACK_ID)
        p2 = cert["payload"]["pillar2_beyond_lora_showdown"]
        self.assertEqual(p2["aletheia_scribe_0_5b"]["winner_adapter"], "standard_lora")
        self.assertEqual(p2["aletheia_weaver_0_5b"]["winner_adapter"], "privsparse_ortho")
        self.assertEqual(p2["aletheia_prover_0_5b"]["winner_adapter"], "standard_lora")
        self.assertEqual(p2["aletheia_prover_0_5b"]["arms"]["privsparse_ortho"]["forgetting_learning_ratio_q"], "NEG_LEARNING")
        self.assertFalse(p2["aletheia_prover_0_5b"]["arms"]["privsparse_ortho"]["beats_s78_unit_wall"])
        self.assertTrue(p2["aletheia_scribe_0_5b"]["arms"]["blockh4_butterfly"]["beats_s78_unit_wall"])
        self.assertEqual(p2["beyond_lora_pareto_summary"]["prover_blockh4_fl_improvement_vs_lora_dec4"], "22.5765")

        res = s95.verify_live_artifacts_on_disk(TRACK_DIR)
        self.assertEqual(res["artifacts_verified"], 5)
        self.assertEqual(res["mlos_inner_sha256"], s95.MLOS_RECEIPT_INNER_SHA256)

        # Direct unit tests for verify_mlos_receipt_obj guards (100% oracle mutation kill)
        mlos_real = json.loads((TRACK_DIR / s95.MLOS_RECEIPT_FILE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(s95.verify_mlos_receipt_obj(mlos_real), s95.MLOS_RECEIPT_INNER_SHA256)
        m_nc = copy.deepcopy(mlos_real)
        m_nc["clean_hardware_run"] = False
        with self.assertRaises(s95.S95Error) as cm1:
            s95.verify_mlos_receipt_obj(m_nc)
        self.assertEqual(cm1.exception.code, "MLOS_NOT_CLEAN")
        m_an = copy.deepcopy(mlos_real)
        m_an["anomalies"] = ["thermal"]
        with self.assertRaises(s95.S95Error) as cm2:
            s95.verify_mlos_receipt_obj(m_an)
        self.assertEqual(cm2.exception.code, "MLOS_ANOMALIES")
        m_tp = copy.deepcopy(mlos_real)
        m_tp["receipt_sha256"] = 123
        with self.assertRaises(s95.S95Error) as cm3:
            s95.verify_mlos_receipt_obj(m_tp)
        self.assertEqual(cm3.exception.code, "MLOS_INNER_SHA_TYPE")
        m_bad_self = copy.deepcopy(mlos_real)
        m_bad_self["receipt_sha256"] = "0" * 64
        with self.assertRaises(s95.S95Error) as cm4:
            s95.verify_mlos_receipt_obj(m_bad_self)
        self.assertEqual(cm4.exception.code, "MLOS_INNER_SHA_MISMATCH")
        m_resigned = copy.deepcopy(mlos_real)
        m_resigned["git_head"] = "tampered"
        inner_t = {k: val for k, val in m_resigned.items() if k != "receipt_sha256"}
        m_resigned["receipt_sha256"] = hashlib.sha256(s95.canonical_json_bytes(inner_t)).hexdigest()
        with self.assertRaises(s95.S95Error) as cm5:
            s95.verify_mlos_receipt_obj(m_resigned)
        self.assertEqual(cm5.exception.code, "MLOS_INNER_PIN_MISMATCH")

        with tempfile.TemporaryDirectory(prefix="s95_art_") as td:
            tp = Path(td)
            with self.assertRaises(s95.S95Error) as ctx:
                s95.verify_live_artifacts_on_disk(tp)
            self.assertEqual(ctx.exception.code, "ARTIFACT_MISSING")
            (tp / s95.RESULTS_FILE_NAME).write_bytes(b"bad")
            with self.assertRaises(s95.S95Error) as ctx2:
                s95.verify_live_artifacts_on_disk(tp)
            self.assertEqual(ctx2.exception.code, "ARTIFACT_SHA_MISMATCH")

        cert_disk = (TRACK_DIR / "s95_specialist_foundry_certificate.json").read_bytes()
        proc = subprocess.run(
            [sys.executable, "-I", "-B", str(TRACK_DIR / "s95_specialist_foundry_oracle.py")],
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, cert_disk)


class TestSpecialistRouterGates(unittest.TestCase):
    def test_03_scribe_weaver_and_prover_audit_gates(self) -> None:
        good_sc = json.dumps(
            {
                "track_id": "TRACK_S95",
                "novelty": "N1",
                "oracle_class": "HYBRID_GPU_CERTIFIED",
                "lean_theorems": 16,
                "leak_flags": False,
                "four_mode_violation": False,
                "crlf_or_assert_flag": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        out_sc = router.route_and_gate("scribe", {}, dry_run_response=good_sc)
        self.assertEqual(out_sc["gate_status"], "VERIFIED")
        for bad in (
            123,
            "not json",
            good_sc + " trailing",
            '{"a": 1.5}',
            '{"a": NaN}',
            "{bad}",
            '{"track_id": "X"}',
            good_sc.replace('"TRACK_S95"', '""'),
            good_sc.replace('"N1"', '"N9"'),
            good_sc.replace('"HYBRID_GPU_CERTIFIED"', '"BAD"'),
            good_sc.replace("16", "-1"),
            good_sc.replace("16", "true"),
            good_sc.replace('"leak_flags":false', '"leak_flags":1'),
        ):
            with self.assertRaises(router.GateError):
                router.gate_scribe_output(bad)  # type: ignore[arg-type]

        good_wv = json.dumps(
            {
                "pathway_class": "EXACT_OBSTRUCTION",
                "canonical_glyph": "⧇",
                "operator_tag": "SMUGGLING_BLOCKED",
                "is_language_smuggling": True,
                "suggested_mediator_class": "EXACT_OPERATOR_PROOF_REQUIRED",
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        self.assertEqual(router.route_and_gate("weaver", {}, dry_run_response=good_wv)["gate_status"], "VERIFIED")
        bad_cs03 = json.dumps(
            {
                "pathway_class": "EXACT_COMMUTE",
                "canonical_glyph": "⧅",
                "operator_tag": "SCHUR_PUSHFORWARD",
                "is_language_smuggling": True,
                "suggested_mediator_class": "DIRECT_IDENTITY",
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with self.assertRaises(router.GateError) as ctx_cs03:
            router.gate_weaver_output(bad_cs03)
        self.assertEqual(ctx_cs03.exception.code, "WEAVER_CS03_INVARIANT")
        with self.assertRaises(router.GateError):
            router.gate_weaver_output(good_wv.replace("⧇", "⧅"))

        good_pa = '{"clean":false,"escape_class":"LEAN4_SORRY"}'
        self.assertEqual(router.route_and_gate("prover_audit", {}, dry_run_response=good_pa)["gate_status"], "VERIFIED")
        for bad_pa in (
            '{"clean":true,"escape_class":"LEAN4_SORRY"}',
            '{"clean":false,"escape_class":"CLEAN"}',
            '{"clean":true,"escape_class":"UNKNOWN"}',
        ):
            with self.assertRaises(router.GateError):
                router.gate_prover_audit_output(bad_pa)

    def test_04_prover_tactic_gate_and_router_cli(self) -> None:
        with self.assertRaises(router.GateError) as c1:
            router.gate_prover_tactic_output("", "theorem t : 1 = 1 :=", "t", "   ")
        self.assertEqual(c1.exception.code, "PROVER_EMPTY_PROOF")
        for bad_proof in ("by sorry", "by bv_decide", "by native_decide", "by decide +native"):
            with self.assertRaises(router.GateError) as ce:
                router.gate_prover_tactic_output("", "theorem t : 1 = 1 :=", "t", bad_proof)
            self.assertEqual(ce.exception.code, "PROVER_R10_STATIC_REJECT")

        if _has_lean():
            ok = router.route_and_gate(
                "prover_tactic",
                {
                    "preamble": "namespace Demo",
                    "theorem_header": "theorem add_comm_one (a : Int) : a + 1 = 1 + a :=",
                    "full_theorem_name": "Demo.add_comm_one",
                },
                dry_run_response="by omega",
            )
            self.assertEqual(ok["gate_status"], "VERIFIED")
            self.assertTrue(ok["output"]["kernel_verified"])
        else:
            with self.assertRaises(router.GateError) as c_nl:
                router.gate_prover_tactic_output("", "theorem t : 1 = 1 :=", "t", "rfl")
            self.assertEqual(c_nl.exception.code, "LEAN_BINARY_UNAVAILABLE")

        p_self = subprocess.run(
            [sys.executable, "-I", "-B", str(TRACK_DIR / "aletheia_specialist_router.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p_self.returncode, 0)
        p_ok = subprocess.run(
            [
                sys.executable, "-I", "-B", str(TRACK_DIR / "aletheia_specialist_router.py"),
                "--task", "prover_audit", "--input-json", "{}",
                "--dry-run-response", '{"clean":true,"escape_class":"CLEAN"}',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p_ok.returncode, 0)
        p_bad = subprocess.run(
            [
                sys.executable, "-I", "-B", str(TRACK_DIR / "aletheia_specialist_router.py"),
                "--task", "prover_audit", "--input-json", "{}",
                "--dry-run-response", '{"clean":true,"escape_class":"LEAN4_SORRY"}',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p_bad.returncode, 2)


class TestZoneBIOAndParsing(unittest.TestCase):
    def test_05_canonical_rational_and_container_safety(self) -> None:
        self.assertTrue(v._is_nonempty_str("ok"))
        self.assertFalse(v._is_nonempty_str("  "))
        self.assertFalse(v._is_nonempty_str(123))
        self.assertTrue(v._is_lower_hex64("0123456789abcdef" * 4))
        self.assertFalse(v._is_lower_hex64(123))
        self.assertFalse(v._is_lower_hex64("a" * 63))
        self.assertFalse(v._is_lower_hex64("g" * 64))

        self.assertEqual(v.parse_canonical_rational("0"), Fraction(0))
        self.assertEqual(v.parse_canonical_rational("-42"), Fraction(-42))
        self.assertEqual(v.parse_canonical_rational("2/33"), Fraction(2, 33))
        self.assertEqual(v.parse_canonical_rational("-57/2500"), Fraction(-57, 2500))
        for bad in (
            123,
            "1/2/3",
            "",
            "abc",
            "01",
            "-0",
            "1/",
            "1/02",
            "1/1",
            "1/0",
            "2/4",
            "1/" + ("9" * 1001),
            ("9" * 1001) + "/7",
            "1/abc",
        ):
            with self.assertRaises(s95.S95Error) as cr:
                v.parse_canonical_rational(bad)
            self.assertEqual(cr.exception.code, "INVALID_RATIONAL")

        class SubInt(int):
            pass

        class SubStr(str):
            pass

        # Exact 1000-digit boundary PASSES (kills >= on _MAX_INT_BITS & MAX_INT_DIGITS!)
        v._check_container_safety({"a": [1, True, None, "ok", 10 ** 1000 - 1]})
        # 1 << 20000 exceeds Python's 4300 str-digit limit -> ONLY bit_length fast path raises S95Error("INT_TOO_LARGE")!
        with self.assertRaises(s95.S95Error) as c_huge:
            v._check_container_safety({"a": 1 << 20000})
        self.assertEqual(c_huge.exception.code, "INT_TOO_LARGE")
        with self.assertRaises(s95.S95Error) as c_1001:
            v._check_container_safety({"a": 10 ** 1000})
        self.assertEqual(c_1001.exception.code, "INT_TOO_LARGE")

        for bad_obj, code in (
            ({1: "k"}, "INVALID_DICT_KEY"),
            ({"\ud800": "k"}, "INVALID_DICT_KEY"),
            ({SubStr("a"): "k"}, "INVALID_DICT_KEY"),
            ({"a": "\udfff"}, "LONE_SURROGATE"),
            ({"a": SubInt(1)}, "FORBIDDEN_VALUE_TYPE"),
            ({"a": (1, 2)}, "FORBIDDEN_VALUE_TYPE"),
        ):
            with self.assertRaises(s95.S95Error) as cs:
                v._check_container_safety(bad_obj)
            self.assertEqual(cs.exception.code, code)

        # Exact depth 64 PASSES, depth 65 FAILS (kills depth >= MAX_JSON_DEPTH!)
        ok_depth: Any = 1
        for _ in range(64):
            ok_depth = [ok_depth]
        v._check_container_safety(ok_depth)
        bad_depth: Any = [ok_depth]
        with self.assertRaises(s95.S95Error) as cd:
            v._check_container_safety(bad_depth)
        self.assertEqual(cd.exception.code, "MAX_DEPTH_EXCEEDED")

    def test_06_strict_json_parser_defenses(self) -> None:
        self.assertEqual(v.parse_strict_json_bytes(b'{"a":1}\n', require_canonical=True), {"a": 1})
        self.assertEqual(v.parse_strict_json_bytes(b'{"a": 1}', require_canonical=False), {"a": 1})
        # Exact 1000-digit integer JSON PASSES (kills len(digits) >= MAX_INT_DIGITS!)
        exact_1000 = b'{"a":' + b"9" * 1000 + b"}\n"
        self.assertEqual(v.parse_strict_json_bytes(exact_1000, require_canonical=True), {"a": 10 ** 1000 - 1})
        # Exact nesting depth 64 JSON PASSES (kills raw depth >= MAX_JSON_DEPTH!)
        d64 = b'{"a":' + (b"[" * 63) + b"1" + (b"]" * 63) + b"}\n"
        self.assertIsInstance(v.parse_strict_json_bytes(d64, require_canonical=True), dict)
        # String containing brackets does not falsely trigger nesting depth
        self.assertEqual(v.parse_strict_json_bytes(b'{"a":"' + b"[" * 100 + b'\\"}"}\n'), {"a": "[" * 100 + '"}'})

        # Test each guard with require_canonical=False and exact error code!
        for raw, req_can, exp_code in (
            (b'{"a":1}\r\n', False, "CRLF_FORBIDDEN"),
            (b"\xff\xfe", False, "INVALID_UTF8"),
            (b"[" * 2000 + b"]" * 2000, False, "MAX_DEPTH_EXCEEDED"),
            (b'{"a":1,"a":2}', False, "DUPLICATE_JSON_KEY"),
            (b'{"a":1.5}', False, "FLOAT_FORBIDDEN"),
            (b'{"a":NaN}', False, "NONFINITE_JSON"),
            (b'{"a":' + b"9" * 4500 + b"}", False, "INT_TOO_LARGE"),
            (b'{"a":-' + b"9" * 1001 + b"}", False, "INT_TOO_LARGE"),
            (b"[1,2]", False, "NON_OBJECT_ROOT"),
            (b"{invalid}", False, "INVALID_JSON"),
            (b'{"a": 1}\n', True, "NON_CANONICAL_JSON"),
            (b'{"a":1}', True, "NON_CANONICAL_JSON"),
        ):
            with self.assertRaises(s95.S95Error) as cj:
                v.parse_strict_json_bytes(raw, require_canonical=req_can)
            self.assertEqual(cj.exception.code, exp_code)

    def test_07_atomic_dirfd_io_and_fs_defenses(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s95_io_") as td:
            root = Path(td)
            target = root / "sub" / "cert.json"
            target.parent.mkdir()
            data = b'{"ok":true}\n'

            old_u = os.umask(0o022)
            try:
                v.write_atomic_0600_bytes(target, data)
            finally:
                os.umask(old_u)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            # Exact max_bytes boundary PASSES, max_bytes - 1 FAILS (kills total >= max_bytes!)
            self.assertEqual(v.read_regular_file_bytes(target, max_bytes=len(data)), data)
            with self.assertRaises(s95.S95Error) as c_big:
                v.read_regular_file_bytes(target, max_bytes=len(data) - 1)
            self.assertEqual(c_big.exception.code, "FILE_TOO_LARGE")

            old_cwd = os.getcwd()
            try:
                os.chdir(target.parent)
                self.assertEqual(v.read_regular_file_bytes(Path("./../sub/cert.json")), data)
                # Deleted CWD triggers CWD_UNAVAILABLE (kills M027!)
                gone = root / "gone_cwd"
                gone.mkdir()
                os.chdir(gone)
                gone.rmdir()
                with self.assertRaises(s95.S95Error) as c_cwd:
                    v.read_regular_file_bytes(Path("cert.json"))
                self.assertEqual(c_cwd.exception.code, "CWD_UNAVAILABLE")
            finally:
                os.chdir(old_cwd)

            with self.assertRaises(s95.S95Error) as c_root:
                v.read_regular_file_bytes(Path("/"))
            self.assertEqual(c_root.exception.code, "INVALID_TARGET_PATH")

            sym = root / "sym.json"
            sym.symlink_to(target)
            with self.assertRaises(s95.S95Error) as c_sr:
                v.read_regular_file_bytes(sym)
            self.assertEqual(c_sr.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(s95.S95Error) as c_sw:
                v.write_atomic_0600_bytes(sym, data)
            self.assertEqual(c_sw.exception.code, "SYMLINK_FORBIDDEN")

            symdir = root / "symdir"
            symdir.symlink_to(target.parent)
            with self.assertRaises(s95.S95Error) as c_sd:
                v.read_regular_file_bytes(symdir / "cert.json")
            self.assertEqual(c_sd.exception.code, "SYMLINK_IN_PATH")

            with self.assertRaises(s95.S95Error) as c_md:
                v.read_regular_file_bytes(root / "missing_dir" / "cert.json")
            self.assertEqual(c_md.exception.code, "DIR_OPEN_FAILED")

            with self.assertRaises(s95.S95Error) as c_mf:
                v.read_regular_file_bytes(root / "missing.json")
            self.assertEqual(c_mf.exception.code, "FILE_OPEN_FAILED")

            hl = root / "hardlink.json"
            os.link(target, hl)
            with self.assertRaises(s95.S95Error) as c_hr:
                v.read_regular_file_bytes(hl)
            self.assertEqual(c_hr.exception.code, "HARDLINK_FORBIDDEN")
            with self.assertRaises(s95.S95Error) as c_hw:
                v.write_atomic_0600_bytes(hl, data)
            self.assertEqual(c_hw.exception.code, "HARDLINK_FORBIDDEN")
            hl.unlink()

            fifo = root / "pipe.fifo"
            os.mkfifo(fifo)
            with self.assertRaises(s95.S95Error) as c_fr:
                v.read_regular_file_bytes(fifo)
            self.assertEqual(c_fr.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(s95.S95Error) as c_fw:
                v.write_atomic_0600_bytes(fifo, data)
            self.assertEqual(c_fw.exception.code, "NOT_REGULAR_FILE")

            old_pwd = os.environ.get("PWD")
            try:
                os.environ["PWD"] = str(symdir)
                with self.assertRaises(s95.S95Error) as c_pwd:
                    v.read_regular_file_bytes(target)
                self.assertEqual(c_pwd.exception.code, "SYMLINK_IN_PATH")
                os.environ["PWD"] = "/nonexistent_pwd_segment_xyz"
                self.assertEqual(v.read_regular_file_bytes(target), data)
                os.environ["PWD"] = "relative_pwd"
                self.assertEqual(v.read_regular_file_bytes(target), data)
            finally:
                if old_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = old_pwd

            ro_dir = root / "ro"
            ro_dir.mkdir()
            ro_file = ro_dir / "ro.json"
            v.write_atomic_0600_bytes(ro_file, data)
            os.chmod(ro_file, 0o644)
            os.chmod(ro_dir, 0o555)
            try:
                self.assertEqual(v.read_regular_file_bytes(ro_file), data)
                with self.assertRaises(s95.S95Error) as c_ro:
                    v.write_atomic_0600_bytes(ro_dir / "new.json", data)
                self.assertEqual(c_ro.exception.code, "ATOMIC_WRITE_FAILED")
            finally:
                os.chmod(ro_dir, 0o755)


class TestFieldCompleteSecondaryAudit(unittest.TestCase):
    def _assert_all3_code(self, cert: dict, exp_code: str, label: str) -> None:
        with self.assertRaises(s95.S95Error, msg=f"SEC failed {label}") as c1:
            v.secondary_audit_payload(cert)
        self.assertEqual(c1.exception.code, exp_code, f"SEC wrong code for {label}")
        with self.assertRaises(s95.S95Error, msg=f"SEC(payload) failed {label}") as c2:
            v.secondary_audit_payload(cert["payload"])
        self.assertEqual(c2.exception.code, exp_code, f"SEC(p) wrong code for {label}")
        with self.assertRaises(s95.S95Error, msg=f"FR0 failed {label}") as c3:
            v.verify_certificate_dict(cert, full_replay=False)
        self.assertEqual(c3.exception.code, exp_code, f"FR0 wrong code for {label}")
        with self.assertRaises(s95.S95Error, msg=f"FR1 failed {label}") as c4:
            v.verify_certificate_dict(cert, full_replay=True)
        self.assertEqual(c4.exception.code, "REPLAY_MISMATCH", f"FR1 wrong code for {label}")

    def test_08_envelope_and_immutability(self) -> None:
        base = s95.build_certificate()
        snap = copy.deepcopy(base)
        self.assertEqual(v.secondary_audit_payload(base)["secondary_audit"], "PASS")
        self.assertEqual(v.secondary_audit_payload(base["payload"])["secondary_audit"], "PASS")
        self.assertEqual(v.verify_certificate_dict(base, full_replay=False)["certificate_sha256"], base["certificate_sha256"])
        self.assertEqual(v.verify_certificate_dict(base, full_replay=True)["certificate_sha256"], base["certificate_sha256"])
        self.assertEqual(base, snap)

        with self.assertRaises(s95.S95Error) as c_nd1:
            v.secondary_audit_payload("not_a_dict")
        self.assertEqual(c_nd1.exception.code, "NON_DICT_INPUT")
        with self.assertRaises(s95.S95Error) as c_nd2:
            v.verify_certificate_dict("not_a_dict")
        self.assertEqual(c_nd2.exception.code, "NON_DICT_CERT")
        with self.assertRaises(s95.S95Error) as c_fr:
            v.verify_certificate_dict(base, full_replay=1)  # type: ignore[arg-type]
        self.assertEqual(c_fr.exception.code, "INVALID_FULL_REPLAY_FLAG")

        # Envelope rejections with EXACT error codes (kills M086..M089!)
        for mut, exp_code in (
            (lambda c: c.update({"extra": 1}), "BAD_CERT_KEYS"),
            (lambda c: c.update({"schema_version": "bad"}), "BAD_SCHEMA_VERSION"),
            (lambda c: c.update({"track_id": "bad"}), "BAD_TRACK_ID"),
            (lambda c: c.update({"payload_sha256": "A" * 64}), "BAD_PAYLOAD_SHA_SYNTAX"),
            (lambda c: c.update({"certificate_sha256": "short"}), "BAD_CERT_SHA_SYNTAX"),
            (lambda c: c.update({"payload": []}), "BAD_PAYLOAD_TYPE"),
            (lambda c: c.update({"certificate_sha256": "0" * 64}), "CERT_SHA_MISMATCH"),
        ):
            bad = copy.deepcopy(base)
            mut(bad)
            with self.assertRaises(s95.S95Error) as ce:
                v.verify_certificate_dict(bad, full_replay=False)
            self.assertEqual(ce.exception.code, exp_code)

        # Bad payload_sha256 WITH matching certificate_sha256 computed over it -> ONLY PAYLOAD_SHA_MISMATCH catches it!
        bad_psha = copy.deepcopy(base)
        bad_psha["payload_sha256"] = "0" * 64
        env_bad = {
            "schema_version": bad_psha["schema_version"],
            "track_id": bad_psha["track_id"],
            "payload_sha256": "0" * 64,
            "payload": bad_psha["payload"],
        }
        bad_psha["certificate_sha256"] = hashlib.sha256(s95.canonical_json_bytes(env_bad)).hexdigest()
        with self.assertRaises(s95.S95Error) as c_pm:
            v.verify_certificate_dict(bad_psha, full_replay=False)
        self.assertEqual(c_pm.exception.code, "PAYLOAD_SHA_MISMATCH")

        # Boundary equality algebraic acceptance test on _audit_pillar2 (kills <= vs < mutants cleanly!)
        c_eq = copy.deepcopy(base)
        p2_eq = c_eq["payload"]["pillar2_beyond_lora_showdown"]
        wv_arm = p2_eq["aletheia_weaver_0_5b"]["arms"]["privsparse_ortho"]
        wv_arm.update(
            {
                "strict_json_ok": 60,
                "exact_all5_ok": 60,
                "pathway_class_ok": 60,
                "operator_tag_ok": 60,
                "exact_all5_rate_q": "1",
                "exact_all5_rate_dec4": "1.0000",
                "pathway_class_rate_q": "1",
                "pathway_class_rate_dec4": "1.0000",
            }
        )
        pv_arm = p2_eq["aletheia_prover_0_5b"]["arms"]["standard_lora"]
        pv_arm.update(
            {
                "live_lean_kernel_pass": 24,
                "live_lean_pass_rate_q": "1",
                "live_lean_pass_rate_dec4": "1.0000",
            }
        )
        p2_eq["aletheia_prover_0_5b"]["lora_passed_theorems"] = [f"Thm.t{i}" for i in range(24)]
        eq_tot = v._audit_pillar2(p2_eq, 8798208, 20399)
        self.assertEqual(eq_tot["win_gate"], 157)

        # Informational leaf tamper (seed=43) -> caught on SEC & FR0 via SEC_PINNED_PAYLOAD_MISMATCH, FR1 via REPLAY_MISMATCH
        c_seed = copy.deepcopy(base)
        c_seed["payload"]["pillar1_hardware_and_datasets"]["seed"] = 43
        c_seed = _resign(c_seed)
        with self.assertRaises(s95.S95Error) as c_sec:
            v.secondary_audit_payload(c_seed)
        self.assertEqual(c_sec.exception.code, "SEC_PINNED_PAYLOAD_MISMATCH")
        with self.assertRaises(s95.S95Error) as c_fr0:
            v.verify_certificate_dict(c_seed, full_replay=False)
        self.assertEqual(c_fr0.exception.code, "SEC_PINNED_PAYLOAD_MISMATCH")
        with self.assertRaises(s95.S95Error) as c_rep:
            v.verify_certificate_dict(c_seed, full_replay=True)
        self.assertEqual(c_rep.exception.code, "REPLAY_MISMATCH")

    def test_14_exhaustive_479_leaf_resigned_sweep(self) -> None:
        base = s95.build_certificate()

        def _iter_leaves(obj: Any, path: tuple[Any, ...] = ()):
            if type(obj) is dict:
                for k, val in obj.items():
                    yield from _iter_leaves(val, path + (k,))
            elif type(obj) is list:
                for idx, val in enumerate(obj):
                    yield from _iter_leaves(val, path + (idx,))
            else:
                yield path, obj

        leaves = list(_iter_leaves(base["payload"]))
        self.assertEqual(len(leaves), 479)
        for path, val in leaves:
            c2 = copy.deepcopy(base)
            cur: Any = c2["payload"]
            for seg in path[:-1]:
                cur = cur[seg]
            if type(val) is bool:
                cur[path[-1]] = not val
            elif type(val) is int:
                cur[path[-1]] = val + 1
            elif type(val) is str and len(val) == 64 and all(ch in "0123456789abcdef" for ch in val):
                cur[path[-1]] = ("f" if val.startswith("0") else "0") + val[1:]
            else:
                cur[path[-1]] = str(val) + "_tamper"
            c2 = _resign(c2)
            snap_c2 = copy.deepcopy(c2)
            with self.assertRaises(s95.S95Error, msg=f"SEC bypassed on {path}"):
                v.secondary_audit_payload(c2)
            with self.assertRaises(s95.S95Error, msg=f"FR0 bypassed on {path}"):
                v.verify_certificate_dict(c2, full_replay=False)
            with self.assertRaises(s95.S95Error, msg=f"FR1 bypassed on {path}"):
                v.verify_certificate_dict(c2, full_replay=True)
            self.assertEqual(c2, snap_c2)

    def test_09_resigned_semantic_forgeries_pillar1_and_pillar2(self) -> None:
        base = s95.build_certificate()

        def mutate(fn) -> dict:
            c = copy.deepcopy(base)
            fn(c["payload"])
            return _resign(c)

        for label, fn, code in [
            ("payload_extra_key", lambda p: p.update({"extra": 1}), "BAD_PAYLOAD_KEYS"),
            ("payload_bad_schema", lambda p: p.update({"schema_version": "bad"}), "BAD_PAYLOAD_SCHEMA"),
            ("payload_bad_track", lambda p: p.update({"track_id": "bad"}), "BAD_PAYLOAD_TRACK"),
            ("payload_bad_oracle", lambda p: p.update({"oracle_class": "BAD"}), "BAD_ORACLE_CLASS"),
            # Pillar 1
            ("p1_non_dict", lambda p: p.update({"pillar1_hardware_and_datasets": []}), "BAD_P1_KEYS"),
            ("p1_bad_keys", lambda p: p["pillar1_hardware_and_datasets"].update({"x": 1}), "BAD_P1_KEYS"),
            ("p1_empty_gpu", lambda p: p["pillar1_hardware_and_datasets"].update({"gpu_name": "   "}), "BAD_P1_STR"),
            ("p1_res_sha", lambda p: p["pillar1_hardware_and_datasets"].update({"results_file_sha256": "0" * 64}), "BAD_P1_RES_SHA"),
            ("p1_res_sha_int", lambda p: p["pillar1_hardware_and_datasets"].update({"results_file_sha256": 123}), "BAD_P1_RES_SHA"),
            ("p1_res_sha_bad", lambda p: p["pillar1_hardware_and_datasets"].update({"results_file_sha256": "bad"}), "BAD_P1_RES_SHA"),
            ("p1_mlos_sha", lambda p: p["pillar1_hardware_and_datasets"].update({"mlos_receipt_file_sha256": "0" * 64}), "BAD_P1_MLOS_SHA"),
            ("p1_mlos_inner", lambda p: p["pillar1_hardware_and_datasets"].update({"mlos_receipt_inner_sha256": "0" * 64}), "BAD_P1_MLOS_INNER_SHA"),
            ("p1_prof_sha", lambda p: p["pillar1_hardware_and_datasets"].update({"mlos_profile_sha256": "0" * 64}), "BAD_P1_PROFILE_SHA"),
            ("p1_not_clean", lambda p: p["pillar1_hardware_and_datasets"].update({"mlos_clean_hardware_run": False}), "BAD_P1_MLOS_STATE"),
            ("p1_exit_nz", lambda p: p["pillar1_hardware_and_datasets"].update({"mlos_exit_code": 1}), "BAD_P1_MLOS_STATE"),
            ("p1_anom_nz", lambda p: p["pillar1_hardware_and_datasets"].update({"mlos_anomaly_count": 1}), "BAD_P1_MLOS_STATE"),
            ("p1_dur_zero", lambda p: p["pillar1_hardware_and_datasets"].update({"mlos_duration_ms_x1000": 0}), "BAD_P1_MLOS_STATE"),
            ("p1_seed_zero", lambda p: p["pillar1_hardware_and_datasets"].update({"seed": 0}), "BAD_P1_POS_INT"),
            ("p1_seed_bool", lambda p: p["pillar1_hardware_and_datasets"].update({"seed": True}), "BAD_P1_POS_INT"),
            ("p1_param_lie", lambda p: p["pillar1_hardware_and_datasets"].update({"exact_matched_trainable_params": 8798207}), "P1_PARAM_BUDGET_MISMATCH"),
            ("p1_layers_lie", lambda p: p["pillar1_hardware_and_datasets"].update({"merged_layers_count": 167}), "P1_LAYERS_MISMATCH"),
            ("p1_ds_not_list", lambda p: p["pillar1_hardware_and_datasets"].update({"datasets": {str(i): i for i in range(7)}}), "BAD_P1_DATASETS"),
            ("p1_ds_len", lambda p: p["pillar1_hardware_and_datasets"]["datasets"].pop(), "BAD_P1_DATASETS"),
            ("p1_ds_empty", lambda p: p["pillar1_hardware_and_datasets"]["datasets"][0].update({"file": ""}), "BAD_DS_FILE"),
            ("p1_ds_dup", lambda p: p["pillar1_hardware_and_datasets"]["datasets"][1].update({"file": p["pillar1_hardware_and_datasets"]["datasets"][0]["file"]}), "BAD_DS_FILE"),
            ("p1_ds_rows0", lambda p: p["pillar1_hardware_and_datasets"]["datasets"][0].update({"rows": 0}), "BAD_DS_COUNTS"),
            ("p1_ds_bytes0", lambda p: p["pillar1_hardware_and_datasets"]["datasets"][0].update({"bytes": 0}), "BAD_DS_COUNTS"),
            ("p1_ds_sha", lambda p: p["pillar1_hardware_and_datasets"]["datasets"][0].update({"sha256": "bad"}), "BAD_DS_SHA"),
            ("p1_ds_tot_rows", lambda p: p["pillar1_hardware_and_datasets"].update({"dataset_total_rows": 1}), "P1_DS_TOTALS_MISMATCH"),
            ("p1_ds_tot_bytes", lambda p: p["pillar1_hardware_and_datasets"].update({"dataset_total_bytes": 1}), "P1_DS_TOTALS_MISMATCH"),
            ("p1_ds_5mib_flag", lambda p: p["pillar1_hardware_and_datasets"].update({"dataset_under_5mib": False}), "P1_DS_TOTALS_MISMATCH"),
            # Pillar 2 Scribe
            ("p2_sc_hdr_win", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"].update({"winner_adapter": "bad"}), "BAD_SCRIBE_HDR"),
            ("p2_sc_hdr_t0", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"].update({"base_target_nll_0_x10000": 0}), "BAD_SCRIBE_HDR"),
            ("p2_sc_win", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"].update({"winner_adapter": "blockh4_butterfly"}), "SCRIBE_WINNER_MISMATCH"),
            ("p2_sc_win_sha", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"].update({"winner_safetensors_sha256": "0" * 64}), "SCRIBE_WINNER_SHA_MISMATCH"),
            ("p2_sc_base_tot", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["base_eval"].update({"total": 0}), "BAD_SCRIBE_TOTAL"),
            ("p2_sc_base_neg", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["base_eval"].update({"strict_json_ok": -1}), "BAD_SCRIBE_BASE_CNT"),
            ("p2_sc_base_ex7", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["base_eval"].update({"exact_all7_ok": -1}), "BAD_SCRIBE_BASE_CNT"),
            ("p2_sc_arm_params", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"trainable_params": 1}), "ARM_PARAMS_MISMATCH"),
            ("p2_sc_arm_vram", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"peak_vram_mib": 0}), "ARM_POS_INT_BAD"),
            ("p2_sc_arm_merge", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"max_merge_diff_x1e6": -1}), "ARM_MERGE_BAD"),
            ("p2_sc_arm_sha", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"safetensors_sha256": "bad"}), "ARM_SHA_BAD"),
            ("p2_sc_arm_perf", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"latency_ms_x100": 0}), "BAD_SCRIBE_PERF"),
            ("p2_sc_arm_tot", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"total": 47}), "BAD_SCRIBE_BOUNDS"),
            ("p2_sc_arm_bounds", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"strict_json_ok": 47}), "BAD_SCRIBE_BOUNDS"),
            ("p2_sc_arm_acc_q", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"exact_all7_rate_q": "1/2"}), "SCRIBE_ACC_MISMATCH"),
            ("p2_sc_arm_acc_dec", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"exact_all7_rate_dec4": "0.5000"}), "SCRIBE_ACC_MISMATCH"),
            ("p2_sc_arm_conf", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"hygiene_tn": 99}), "CONFUSION_MISMATCH"),
            ("p2_sc_arm_f1_dec", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"hygiene_f1_dec4": "0.5000"}), "SCRIBE_F1_MISMATCH"),
            ("p2_sc_nll_neg", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"base_retention_nll_after_x10000": -1}), "BAD_NLL_INT"),
            ("p2_sc_df_lie", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"delta_forgetting_dec4": "0.0001"}), "NLL_DF_MISMATCH"),
            ("p2_sc_dl_lie", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"delta_learning_dec4": "0.0001"}), "NLL_DL_MISMATCH"),
            ("p2_sc_fl_lie", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"forgetting_learning_ratio_dec4": "0.0001"}), "NLL_FL_MISMATCH"),
            ("p2_sc_wall_lie", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_scribe_0_5b"]["arms"]["standard_lora"].update({"beats_s78_unit_wall": False}), "NLL_WALL_MISMATCH"),
            # Pillar 2 Weaver
            ("p2_wv_hdr_win", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"].update({"winner_adapter": "bad"}), "BAD_WEAVER_HDR"),
            ("p2_wv_pareto_bad", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"].update({"retention_pareto_adapter": "bad"}), "BAD_WEAVER_HDR"),
            ("p2_wv_win", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"].update({"winner_adapter": "standard_lora"}), "WEAVER_WINNER_MISMATCH"),
            ("p2_wv_win_sha", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"].update({"winner_safetensors_sha256": "0" * 64}), "WEAVER_WINNER_SHA_MISMATCH"),
            ("p2_wv_base_tot", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["base_eval"].update({"total": 0}), "BAD_WEAVER_TOTAL"),
            ("p2_wv_base_neg", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["base_eval"].update({"operator_tag_ok": -1}), "BAD_WEAVER_BASE_CNT"),
            ("p2_wv_perf", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["arms"]["standard_lora"].update({"tok_per_sec_x100": 0}), "BAD_WEAVER_PERF"),
            ("p2_wv_tot", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["arms"]["standard_lora"].update({"total": 59}), "BAD_WEAVER_BOUNDS"),
            ("p2_wv_order", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["arms"]["standard_lora"].update({"exact_all5_ok": 40}), "BAD_WEAVER_BOUNDS"),
            ("p2_wv_bounds", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["arms"]["standard_lora"].update({"operator_tag_ok": 60}), "BAD_WEAVER_BOUNDS"),
            ("p2_wv_acc_dec", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["arms"]["standard_lora"].update({"exact_all5_rate_dec4": "0.9999"}), "WEAVER_ACC_MISMATCH"),
            ("p2_wv_pcls_dec", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["arms"]["standard_lora"].update({"pathway_class_rate_dec4": "0.9999"}), "WEAVER_PCLS_MISMATCH"),
            ("p2_wv_f1_dec", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_weaver_0_5b"]["arms"]["standard_lora"].update({"cs03_f1_dec4": "0.5000"}), "WEAVER_F1_MISMATCH"),
            # Pillar 2 Prover & Pareto
            ("p2_pv_hdr_win", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"].update({"winner_adapter": "bad"}), "BAD_PROVER_HDR"),
            ("p2_pv_win", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"].update({"winner_adapter": "blockh4_butterfly"}), "PROVER_WINNER_MISMATCH"),
            ("p2_pv_win_sha", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"].update({"winner_safetensors_sha256": "0" * 64}), "PROVER_WINNER_SHA_MISMATCH"),
            ("p2_pv_base_tot", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["base_eval"].update({"audit_total": 0}), "BAD_PROVER_TOTALS"),
            ("p2_pv_base_neg", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["base_eval"].update({"live_lean_kernel_pass": -1}), "BAD_PROVER_BASE_CNT"),
            ("p2_pv_perf", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"audit_latency_ms_x100": 0}), "BAD_PROVER_PERF"),
            ("p2_pv_ttot", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"tactics_total": 23}), "BAD_PROVER_BOUNDS"),
            ("p2_pv_atot", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"audit_total": 24}), "BAD_PROVER_BOUNDS"),
            ("p2_pv_lple", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"live_lean_kernel_pass": 25}), "BAD_PROVER_BOUNDS"),
            ("p2_pv_bounds", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"r10_static_rejected": -1}), "BAD_PROVER_BOUNDS"),
            ("p2_pv_aud_ord", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"audit_strict_json_ok": 24}), "BAD_PROVER_BOUNDS"),
            ("p2_pv_tac_dec", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"live_lean_pass_rate_dec4": "0.9999"}), "PROVER_TAC_MISMATCH"),
            ("p2_pv_aud_dec", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"exact_escape_rate_dec4": "0.5000"}), "PROVER_AUD_MISMATCH"),
            ("p2_pv_f1_dec", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["standard_lora"].update({"escape_f1_dec4": "0.5000"}), "PROVER_F1_MISMATCH"),
            ("p2_pv_neg_learn_q", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["privsparse_ortho"].update({"forgetting_learning_ratio_q": "1"}), "NLL_NEG_LEARN_MISMATCH"),
            ("p2_pv_neg_learn_d", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["privsparse_ortho"].update({"forgetting_learning_ratio_dec4": "1.0000"}), "NLL_NEG_LEARN_MISMATCH"),
            ("p2_pv_neg_learn_w", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["arms"]["privsparse_ortho"].update({"beats_s78_unit_wall": True}), "NLL_NEG_LEARN_MISMATCH"),
            ("p2_pv_thms_type", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"].update({"lora_passed_theorems": {f"k{i}": i for i in range(5)}}), "PROVER_PASSED_THMS_MISMATCH"),
            ("p2_pv_thms_len", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["lora_passed_theorems"].pop(), "PROVER_PASSED_THMS_MISMATCH"),
            ("p2_pv_thms_str", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["lora_passed_theorems"].__setitem__(0, ""), "PROVER_PASSED_THMS_MISMATCH"),
            ("p2_pv_thms_dup", lambda p: p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["blockh4_passed_theorems"].__setitem__(1, p["pillar2_beyond_lora_showdown"]["aletheia_prover_0_5b"]["blockh4_passed_theorems"][0]), "PROVER_PASSED_THMS_MISMATCH"),
            ("p2_pareto_fl", lambda p: p["pillar2_beyond_lora_showdown"]["beyond_lora_pareto_summary"].update({"prover_blockh4_fl_improvement_vs_lora_dec4": "99.9999"}), "PARETO_RATIO_MISMATCH"),
            ("p2_pareto_wc", lambda p: p["pillar2_beyond_lora_showdown"]["beyond_lora_pareto_summary"].update({"scribe_blockh4_wallclock_ratio_vs_lora_dec4": "1.0000"}), "PARETO_RATIO_MISMATCH"),
        ]:
            self._assert_all3_code(mutate(fn), code, label)

        def _make_neg_learn(sp_k: str, arm_k: str, tgt0: int) -> dict:
            c = copy.deepcopy(base)
            a = c["payload"]["pillar2_beyond_lora_showdown"][sp_k]["arms"][arm_k]
            a["target_eval_nll_after_x10000"] = tgt0
            a["delta_learning_q"] = "0"
            a["delta_learning_dec4"] = "0.0000"
            a["forgetting_learning_ratio_q"] = "NEG_LEARNING"
            a["forgetting_learning_ratio_dec4"] = "NEG_LEARNING"
            a["beats_s78_unit_wall"] = False
            return _resign(c)

        self._assert_all3_code(_make_neg_learn("aletheia_scribe_0_5b", "standard_lora", s95.SCRIBE_BASE_TGT_NLL_0_X10000), "SCRIBE_FL_NONE", "sc_neg_learn")
        self._assert_all3_code(_make_neg_learn("aletheia_weaver_0_5b", "standard_lora", s95.WEAVER_BASE_TGT_NLL_0_X10000), "WEAVER_FL_NONE", "wv_neg_learn")
        self._assert_all3_code(_make_neg_learn("aletheia_prover_0_5b", "standard_lora", s95.PROVER_BASE_TGT_NLL_0_X10000), "PARETO_PV_FL_MISSING", "pv_lora_neg_learn")
        self._assert_all3_code(_make_neg_learn("aletheia_prover_0_5b", "blockh4_butterfly", s95.PROVER_BASE_TGT_NLL_0_X10000), "PARETO_PV_FL_MISSING", "pv_bh_neg_learn")

    def test_10_resigned_semantic_forgeries_pillar3_4_5(self) -> None:
        base = s95.build_certificate()

        def mutate(fn) -> dict:
            c = copy.deepcopy(base)
            fn(c["payload"])
            return _resign(c)

        for label, fn, code in [
            # Pillar 3
            ("p3_zero_fa", lambda p: p["pillar3_law3_routing_and_law4_failures"].update({"law3_zero_false_accept_enforced": False}), "BAD_P3_ZERO_FA"),
            ("p3_tot_lie", lambda p: p["pillar3_law3_routing_and_law4_failures"].update({"total_heldout_eval_calls": 999}), "P3_TOTALS_MISMATCH"),
            ("p3_rate_lie", lambda p: p["pillar3_law3_routing_and_law4_failures"].update({"winner_law3_gate_pass_rate_dec4": "0.9999"}), "P3_RATES_MISMATCH"),
            ("p3_det_lie", lambda p: p["pillar3_law3_routing_and_law4_failures"].update({"winner_deterministic_exact_rate_dec4": "0.9999"}), "P3_RATES_MISMATCH"),
            ("p3_fm_type", lambda p: p["pillar3_law3_routing_and_law4_failures"].update({"law4_honest_failure_modes": {f"k{i}": i for i in range(3)}}), "BAD_P3_FMS"),
            ("p3_fm_len", lambda p: p["pillar3_law3_routing_and_law4_failures"]["law4_honest_failure_modes"].pop(), "BAD_P3_FMS"),
            ("p3_fm_empty_id", lambda p: p["pillar3_law3_routing_and_law4_failures"]["law4_honest_failure_modes"][0].update({"id": ""}), "BAD_FM_ENTRY"),
            ("p3_fm_dup", lambda p: p["pillar3_law3_routing_and_law4_failures"]["law4_honest_failure_modes"][1].update({"id": p["pillar3_law3_routing_and_law4_failures"]["law4_honest_failure_modes"][0]["id"]}), "BAD_FM_ENTRY"),
            ("p3_fm_empty", lambda p: p["pillar3_law3_routing_and_law4_failures"]["law4_honest_failure_modes"][0].update({"summary": "  "}), "BAD_FM_ENTRY"),
            # Pillar 4
            ("p4_cfg_sha", lambda p: p["pillar4_inkling2_transfer"].update({"inkling2_config_sha256": "0" * 64}), "BAD_P4_PINS"),
            ("p4_s96_sha", lambda p: p["pillar4_inkling2_transfer"].update({"track_s96_cert_sha256": "0" * 64}), "BAD_P4_PINS"),
            ("p4_model", lambda p: p["pillar4_inkling2_transfer"].update({"model_type": "other"}), "BAD_P4_MODEL"),
            ("p4_quant", lambda p: p["pillar4_inkling2_transfer"].update({"quant_algo": "FP16"}), "BAD_P4_MODEL"),
            ("p4_zero_int", lambda p: p["pillar4_inkling2_transfer"].update({"gate_rank": 0}), "BAD_P4_INT"),
            ("p4_eff_lie", lambda p: p["pillar4_inkling2_transfer"].update({"effective_layers": 24}), "P4_EFF_LAYERS_MISMATCH"),
            ("p4_pad_lie", lambda p: p["pillar4_inkling2_transfer"].update({"blockh4_zero_pad_compatible": False}), "P4_PAD_MISMATCH"),
            ("p4_dr_lie", lambda p: p["pillar4_inkling2_transfer"].update({"depth_reuse_ratio_q": "3"}), "P4_DEPTH_RATIO_MISMATCH"),
            ("p4_lev_lie", lambda p: p["pillar4_inkling2_transfer"].update({"loop_core_adapter_leverage_q": "2"}), "P4_LEV_MISMATCH"),
            ("p4_exp_lie", lambda p: p["pillar4_inkling2_transfer"].update({"active_expert_fraction_q": "1/8"}), "P4_EXPERT_MISMATCH"),
            ("p4_vram_fit", lambda p: p["pillar4_inkling2_transfer"].update({"rtx3080_full_resident_fits": True}), "P4_VRAM_MISMATCH"),
            ("p4_ws_fit", lambda p: p["pillar4_inkling2_transfer"].update({"workstation_32gib_full_resident_fits": False}), "P4_VRAM_MISMATCH"),
            ("p4_ovf_lie", lambda p: p["pillar4_inkling2_transfer"].update({"rtx3080_overflow_ratio_q": "3"}), "P4_VRAM_MISMATCH"),
            # Pillar 5
            ("p5_lean_file", lambda p: p["pillar5_lean4_and_novelty"].update({"lean_file": ""}), "BAD_P5_META"),
            ("p5_lean_ver", lambda p: p["pillar5_lean4_and_novelty"].update({"lean_version": "4.35.0"}), "BAD_P5_META"),
            ("p5_lean_sha", lambda p: p["pillar5_lean4_and_novelty"].update({"lean_sha256": "0" * 64}), "BAD_P5_SHAS"),
            ("p5_lake_sha", lambda p: p["pillar5_lean4_and_novelty"].update({"lakefile_sha256": "0" * 64}), "BAD_P5_SHAS"),
            ("p5_tc_sha", lambda p: p["pillar5_lean4_and_novelty"].update({"toolchain_sha256": "0" * 64}), "BAD_P5_SHAS"),
            ("p5_thm_cnt", lambda p: p["pillar5_lean4_and_novelty"].update({"theorem_count": 15}), "BAD_P5_THMS"),
            ("p5_univ_cnt", lambda p: p["pillar5_lean4_and_novelty"].update({"universal_theorem_count": 15}), "BAD_P5_THMS"),
            ("p5_cc_cnt", lambda p: p["pillar5_lean4_and_novelty"].update({"classical_choice_count": 1}), "BAD_P5_THMS"),
            ("p5_ax_sum", lambda p: p["pillar5_lean4_and_novelty"].update({"zero_axiom_theorem_count": 2}), "BAD_P5_THMS"),
            ("p5_thms_lst", lambda p: p["pillar5_lean4_and_novelty"]["theorems"].pop(), "BAD_P5_THMS"),
            ("p5_nov_cls", lambda p: p["pillar5_lean4_and_novelty"].update({"max_novelty_class": "N2"}), "BAD_P5_NOVELTY"),
            ("p5_n2_cnt", lambda p: p["pillar5_lean4_and_novelty"].update({"n2_claims_count": 1}), "BAD_P5_NOVELTY"),
            ("p5_n0_flag", lambda p: p["pillar5_lean4_and_novelty"].update({"n0_prior_art_anchored": False}), "BAD_P5_NOVELTY"),
            ("p5_n1_flag", lambda p: p["pillar5_lean4_and_novelty"].update({"n1_exact_synthesis_verified": False}), "BAD_P5_NOVELTY"),
        ]:
            self._assert_all3_code(mutate(fn), code, label)


class TestLean4R12AndLiveKernel(unittest.TestCase):
    def test_11_r12_static_scanner_all_classes_and_controls(self) -> None:
        with self.assertRaises(s95.S95Error) as ci:
            v.audit_lean4_source_r12(123)  # type: ignore[arg-type]
        self.assertEqual(ci.exception.code, "INVALID_LEAN_SOURCE")

        # Unit checks on _strip_outer_parens to kill L793 BoolOp cleanly
        self.assertEqual(v._strip_outer_parens("((false))"), "false")
        self.assertEqual(v._strip_outer_parens("(false"), "(false")
        self.assertEqual(v._strip_outer_parens("false)"), "false)")

        # Clean controls MUST produce 0 findings (0 FP) and exercise every lexer/scanner edge!
        clean_controls = [
            '"sorry"!',  # quote at index 0 + trailing '!' kills L761 (i > 0 and source[i-1] == '!')
            "import Init\nimport Std\ntheorem ok : 1 + 1 = 2 := by decide (native := false)\n#print axioms ok\n",
            "theorem ok2 : 1 = 1 := by decide (native := Bool.false)\n",
            "theorem ok3 : 1 = 1 := by decide (native := (false))\n",
            "theorem ok4 : 1 = 1 := by decide (config := { native := false })\n",
            "def cfg_ok : DecideConfig := { native := false }\n",
            "theorem ok5 : 1 = 1 := by decide -revert (revert := true)\n",
            "theorem ok6 : 1 = 1 := by decide\n",
            "theorem ok7 : 1 = 1 := by decide (1 + 1)\n",
            "theorem ok8 : 1 = 1 := by decide ++\n",
            "theorem ok9 : 1 = 1 := by decide (native := false\n",
            "@[simp] def f_ok : Nat := 1\n@[extern\n",
            "def stray := ) ]\n",
            "/- nested a / b - c /- sorry -/ block\n comment -/\n-- sorry line\ndef q := 4 / 2 - 1\ndef s := \"sorry \\\" \\n \"\ndef r := r#\"sorry\n\"#\ndef c1 := 'a'\ndef c2 := '\\n'\ndef x' := 1\ndef r_ok := \"hi\"\ndef ok_dot := Foo.axiom + Foo.opaque\n",
        ]
        for idx, src in enumerate(clean_controls):
            self.assertEqual(v.audit_lean4_source_r12(src), [], f"clean control {idx} false positive")

        self.assertIn("LEAN4_UNTERMINATED_COMMENT", v.audit_lean4_source_r12("/- unclosed"))
        self.assertIn("LEAN4_UNTERMINATED_STRING", v.audit_lean4_source_r12('def s := "unclosed'))
        self.assertIn("LEAN4_UNTERMINATED_STRING", v.audit_lean4_source_r12('def s := r#"unclosed'))

        escapes: list[tuple[str, str]] = [
            ("theorem t : False := sorry", "LEAN4_SORRY"),
            ("theorem t : False := by admit", "LEAN4_ADMIT"),
            ("axiom a : False", "LEAN4_AXIOM"),
            ("unsafe def f : Nat := 0", "LEAN4_UNSAFE"),
            ("theorem t : 1 = 1 := by native_decide", "LEAN4_NATIVE_DECIDE"),
            ("theorem t : 1 = 1 := by bv_decide", "LEAN4_NATIVE_DECIDE"),
            ("def x := sorryAx", "LEAN4_SORRY_AX"),
            ("def x := Lean.Meta.mkSorry", "LEAN4_MK_SORRY"),
            ("def x := ofReduceBool", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := ofReduceNat", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := Lean.trustCompiler", "LEAN4_TRUST_COMPILER"),
            ('def x := dbg_trace "hi"; 0', "LEAN4_DBG_FFI_ESCAPE"),
            ("def x := dbgTraceVal 0", "LEAN4_DBG_FFI_ESCAPE"),
            ('def x : Nat := panic! "boom"', "LEAN4_DBG_FFI_ESCAPE"),
            ("def x : Nat := unreachable!", "LEAN4_DBG_FFI_ESCAPE"),
            ('macro "foo" : term => `(0)', "LEAN4_META_SYNTAX_ESCAPE"),
            ("declare_syntax_cat mycat", "LEAN4_META_SYNTAX_ESCAPE"),
            ('notation "foo" => 0', "LEAN4_META_SYNTAX_ESCAPE"),
            ("import Mathlib.Tactic", "LEAN4_NON_INIT_IMPORT"),
            ("partial def loop (n : Nat) : Nat := loop n", "LEAN4_PARTIAL"),
            ("opaque hidden : Nat := 0", "LEAN4_OPAQUE"),
            ("set_option debug.terminalTacticsAsSorry true", "LEAN4_SKIP_KERNEL_TC"),
            ("set_option maxHeartbeats 0", "LEAN4_SKIP_KERNEL_TC"),
            ("#eval 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#guard_msgs in #check 1", "LEAN4_EVAL_SPOOF"),
            ("#exit", "LEAN4_EVAL_SPOOF"),
            ("#print Nat", "LEAN4_EVAL_SPOOF"),
            ("initialize pure ()", "LEAN4_EVAL_SPOOF"),
            ('@[extern "c_fn"] def f : Nat := 0', "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [csimp] f", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[tactic mytac] def f : Nat := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[init] def f : IO Unit := pure ()", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("theorem t : 1 = 1 := by decide +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide -revert +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false || true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false == false)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false != true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false.not)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := myCfg)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := {a)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := a})", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { a { b })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { a } b })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { c with native := false })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native })", "LEAN4_DECIDE_NATIVE"),
            ("def c : DecideConfig := { native := true }", "LEAN4_DECIDE_NATIVE"),
            ("def c := ({ native := true } : Decide.Config)", "LEAN4_DECIDE_NATIVE"),
            ('def x := s!"{sorry}"', "LEAN4_SORRY"),
            ("theorem t : False := «sorry»", "LEAN4_SORRY"),
        ]
        for src, expected_code in escapes:
            got = v.audit_lean4_source_r12(src)
            self.assertIn(expected_code, got, f"expected {expected_code} for {src!r}, got {got}")

    def test_12_lean_output_parser_and_live_or_leanless(self) -> None:
        wrapped = "'A.t1' depends on axioms: [propext,\n Quot.sound]\n'A.t2' does not depend on any axioms\n"
        parsed = v._verify_lean_output(0, "", wrapped, check_pinned_sha=False)
        self.assertEqual(parsed, {"A.t1": ["propext", "Quot.sound"], "A.t2": []})
        # Exact codes (kills M066: rc=1 with empty stderr & valid stdout!)
        for rc, err, out, pin, exp_code in (
            (1, "", "'A.t1' does not depend on any axioms\n", False, "LEAN_COMPILE_FAILED"),
            (0, "warn", "'A.t1' does not depend on any axioms\n", False, "LEAN_STDERR_NONEMPTY"),
            (0, "", "junk line\n", False, "LEAN_UNEXPECTED_OUTPUT"),
            (0, "", "'A.t1' does not depend on any axioms\n'A.t1' does not depend on any axioms\n", False, "LEAN_DUPLICATE_THEOREM"),
            (0, "", "'A.t1' depends on axioms: [sorryAx]\n", False, "LEAN_FORBIDDEN_AXIOM"),
            (0, "", "'A.t1' depends on axioms: [Classical.choice]\n", False, "LEAN_FORBIDDEN_AXIOM"),
            (0, "", "", False, "LEAN_ZERO_THEOREMS"),
            (0, "", "'A.t1' does not depend on any axioms\n", True, "LEAN_THEOREM_SET_MISMATCH"),
        ):
            with self.assertRaises(s95.S95Error) as cl:
                v._verify_lean_output(rc, err, out, check_pinned_sha=pin)
            self.assertEqual(cl.exception.code, exp_code)

        lean_p = TRACK_DIR / s95.LEAN_FILE_NAME
        with tempfile.TemporaryDirectory(prefix="s95_ln_") as td:
            tp = Path(td)
            f_crlf = tp / "c.lean"
            f_crlf.write_bytes(b"theorem t : 1 = 1 := rfl\r\n")
            with self.assertRaises(s95.S95Error) as c1:
                v.verify_lean_file(f_crlf, check_pinned_sha=False)
            self.assertEqual(c1.exception.code, "CRLF_FORBIDDEN")

            f_u8 = tp / "u.lean"
            f_u8.write_bytes(b"\xff\xfe")
            with self.assertRaises(s95.S95Error) as c2:
                v.verify_lean_file(f_u8, check_pinned_sha=False)
            self.assertEqual(c2.exception.code, "INVALID_UTF8")

            f_sha = tp / "s.lean"
            f_sha.write_text("theorem t : 1 = 1 := rfl\n#print axioms t\n", encoding="utf-8")
            with self.assertRaises(s95.S95Error) as c3:
                v.verify_lean_file(f_sha, check_pinned_sha=True)
            self.assertEqual(c3.exception.code, "LEAN_SHA_MISMATCH")

            f_bad = tp / "b.lean"
            f_bad.write_text("theorem t : False := sorry\n#print axioms t\n", encoding="utf-8")
            with self.assertRaises(s95.S95Error) as c4:
                v.verify_lean_file(f_bad, check_pinned_sha=False)
            self.assertEqual(c4.exception.code, "LEAN_R12_STATIC_FINDING")

            f_zero = tp / "z.lean"
            f_zero.write_text("def x : Nat := 1\n", encoding="utf-8")

            if _has_lean():
                poison_dir = tp / "poison"
                poison_dir.mkdir()
                (poison_dir / "Init.olean").write_bytes(b"CORRUPT")
                saved_env = {k: os.environ.get(k) for k in ("LEAN_PATH", "LEAN_OPTS", "LEAN_SRC_PATH", "ELAN_TOOLCHAIN", "LAKE_HOME")}
                try:
                    os.environ["LEAN_PATH"] = str(poison_dir)
                    os.environ["LEAN_OPTS"] = "--invalid-opt"
                    os.environ["LEAN_SRC_PATH"] = str(poison_dir)
                    os.environ["ELAN_TOOLCHAIN"] = "nonexistent-toolchain"
                    os.environ["LAKE_HOME"] = str(poison_dir)
                    res_live = v.verify_lean_file(lean_p, check_pinned_sha=True)
                    self.assertEqual(res_live["theorems_verified"], 16)
                    self.assertEqual(res_live["r12_findings"], 0)
                finally:
                    for k, val in saved_env.items():
                        if val is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = val

                with self.assertRaises(s95.S95Error) as c_zero:
                    v.verify_lean_file(f_zero, check_pinned_sha=False)
                self.assertEqual(c_zero.exception.code, "LEAN_ZERO_THEOREMS")
            else:
                with self.assertRaises(s95.S95Error) as c_nl:
                    v.verify_lean_file(lean_p, check_pinned_sha=True)
                self.assertEqual(c_nl.exception.code, "LEAN_BINARY_NOT_FOUND")
                self.assertEqual(v.main(["--verify-lean", str(lean_p)]), 2)

    def test_13_cli_modes_and_error_exit(self) -> None:
        cert_path = TRACK_DIR / "s95_specialist_foundry_certificate.json"
        self.assertEqual(v.main(["--check", str(cert_path), "--json"]), 0)
        self.assertEqual(v.main(["--check", str(cert_path)]), 0)
        self.assertEqual(v.main(["--verify-artifacts", str(TRACK_DIR), "--json"]), 0)
        self.assertEqual(v.main(["--verify-artifacts", str(TRACK_DIR)]), 0)
        self.assertEqual(v.main(["--standalone"]), 0)
        with tempfile.TemporaryDirectory(prefix="s95_cli_") as td:
            out_p = Path(td) / "out.json"
            self.assertEqual(v.main(["--write", str(out_p), "--json"]), 0)
            self.assertEqual(out_p.read_bytes(), cert_path.read_bytes())
            self.assertEqual(v.main(["--write", str(out_p)]), 0)
            self.assertEqual(v.main(["--check", str(Path(td) / "nope.json")]), 2)
        if _has_lean():
            self.assertEqual(v.main(["--verify-lean", str(TRACK_DIR / s95.LEAN_FILE_NAME), "--json"]), 0)
            self.assertEqual(v.main(["--verify-lean", str(TRACK_DIR / s95.LEAN_FILE_NAME)]), 0)


if __name__ == "__main__":
    unittest.main()
