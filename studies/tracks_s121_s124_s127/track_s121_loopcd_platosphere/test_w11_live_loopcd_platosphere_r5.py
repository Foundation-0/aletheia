#!/usr/bin/env python3
"""Pure-stdlib R5 adversarial test suite for `run_w11_live_loopcd_platosphere.py`
(passes stock /usr/bin/python3 -I x3 BOTH in-tree AND in isolated standalone track snapshots)."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import run_w11_live_loopcd_platosphere as w11  # noqa: E402


class _DummyTokenizer:
    eos_token_id: int | None = 2

    def encode(self, text: str, add_special_tokens: bool = True) -> list[int]:
        return list(range(len(text.split()) + (1 if add_special_tokens else 0)))

    def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
        return ",".join(str(i) for i in ids)


class _DummyScalar:
    def __init__(self, val: int) -> None:
        self._val = val

    def item(self) -> int:
        return self._val


class _DummyLogits:
    def __init__(self, tok_id: int) -> None:
        self._tok_id = tok_id

    def __getitem__(self, _idx: object) -> _DummyLogits:
        return self

    def argmax(self, dim: int = -1, keepdim: bool = True) -> _DummyScalar:
        return _DummyScalar(self._tok_id)


class _DummyOut:
    def __init__(self, tok_id: int) -> None:
        self.past_key_values = ("kv",)
        self.logits = _DummyLogits(tok_id)


class _DummyModel:
    def __init__(self, seq: list[int]) -> None:
        self._seq = list(seq)
        self._idx = 0

    def __call__(self, **_kwargs: object) -> _DummyOut:
        tok = self._seq[min(self._idx, len(self._seq) - 1)]
        self._idx += 1
        return _DummyOut(tok)


class TestW11LiveProbesStdlib(unittest.TestCase):
    def test_01_prereg_lock_standalone_snapshot_and_subject_disjoint_suite(self) -> None:
        r1 = w11.run_stdlib_selftest()
        r2 = w11.run_stdlib_selftest()
        self.assertTrue(r1["passed"])
        self.assertEqual(r1["prereg_sha256"], w11.PINNED_PREREG_SHA256)
        self.assertEqual(r1["prereg_source"], "disk_verified")
        self.assertTrue(r1["zone_b_bundle_verified"])
        self.assertTrue(w11.run_stdlib_selftest(allow_missing_zone_b=True)["zone_b_bundle_verified"])
        self.assertIs(w11._is_strict_num(1.5), True)
        self.assertIs(w11._is_strict_num(True), False)
        self.assertIs(w11._is_strict_num("1.5"), False)
        self.assertIs(w11._is_strict_num(10**400), False)
        self.assertEqual(r1["total_unique_facts"], 148)
        self.assertGreaterEqual(r1["total_unique_facts"], 120)
        self.assertTrue(r1["subject_disjoint_pass"])
        self.assertEqual(r1["payload_sha256"], r2["payload_sha256"])

        # Direct _eval_selftest_flags coverage (kills every BoolOp conjunct)
        self.assertEqual(w11._eval_selftest_flags(120, 120, 0, True, True, True), (True, True))
        self.assertEqual(w11._eval_selftest_flags(119, 119, 0, True, False, False), (False, False))
        self.assertEqual(w11._eval_selftest_flags(120, 119, 0, True, False, False), (False, False))
        self.assertEqual(w11._eval_selftest_flags(120, 120, 1, True, False, False), (False, False))
        self.assertEqual(w11._eval_selftest_flags(120, 120, 0, False, False, False), (True, False))
        self.assertEqual(w11._eval_selftest_flags(120, 120, 0, True, True, False), (True, False))

        zb_live = w11.verify_w11_zone_b_bundle(_HERE)
        self.assertTrue(zb_live["passed"])
        self.assertEqual(zb_live["git_head_status"], "not_captured_at_run_time")

        # Paired git_head / git_head_status builder helper (clean, dirty, null, invalid)
        self.assertEqual(
            w11.build_zone_b_git_head_fields(None),
            {"git_head": None, "git_head_status": "not_captured_at_run_time"},
        )
        self.assertEqual(
            w11.build_zone_b_git_head_fields("a" * 40),
            {"git_head": "a" * 40, "git_head_status": "captured"},
        )
        self.assertEqual(
            w11.build_zone_b_git_head_fields("a" * 40, dirty=True),
            {"git_head": "a" * 40, "git_head_status": "captured_dirty"},
        )
        for bad_head in ("deadbeef", "A" * 40, 123):
            with self.assertRaises(w11.Wave11ProbeError) as cm_gh:
                w11.build_zone_b_git_head_fields(bad_head)  # type: ignore[arg-type]
            self.assertEqual(cm_gh.exception.code, "INVALID_GIT_HEAD")

        # CLI --check-zone-b (text & --json), default text OK, and --selftest-stdlib without --json
        buf_zb = io.StringIO()
        with redirect_stdout(buf_zb):
            self.assertEqual(w11.main(["--check-zone-b"]), 0)
        self.assertIn("PASS S121_ZONE_B", buf_zb.getvalue())
        buf_zb_j = io.StringIO()
        with redirect_stdout(buf_zb_j):
            self.assertEqual(w11.main(["--check-zone-b", "--json"]), 0)
        self.assertTrue(json.loads(buf_zb_j.getvalue())["passed"])

        buf_def = io.StringIO()
        with redirect_stdout(buf_def):
            self.assertEqual(w11.main([]), 0)
        self.assertTrue(buf_def.getvalue().startswith("OK "))

        buf_st_nojson = io.StringIO()
        with redirect_stdout(buf_st_nojson):
            self.assertEqual(w11.main(["--selftest-stdlib"]), 0)
        self.assertTrue(json.loads(buf_st_nojson.getvalue())["passed"])

        # Mutually exclusive CLI flags (--run-gpu + --check-zone-b) refused cleanly (rc == 2, zero traceback)
        proc_mutex = subprocess.run(
            [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--run-gpu", "--check-zone-b"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc_mutex.returncode, 2)
        self.assertIn("not allowed with argument", proc_mutex.stderr)
        self.assertNotIn("Traceback", proc_mutex.stderr)

        # R5 Zone-B tamper plants (including real git repo HEAD capture/verify & forged 40-hex rejection!)
        with tempfile.TemporaryDirectory() as td_zb:
            base = Path(td_zb)
            pr_dir = base / "preregistrations"
            tr_dir = base / "track_s121_loopcd_platosphere"
            pr_dir.mkdir()
            tr_dir.mkdir()

            def _reset_zb() -> None:
                shutil.copyfile(_HERE.parent / "preregistrations" / w11.PREREG_FILENAME, pr_dir / w11.PREREG_FILENAME)
                for fn in ("w11_live_loopcd_platosphere_results.json", "mlos_zone_b_w11_loopcd_platosphere.json", "ux582hs-rtx3080-8gb.toml"):
                    shutil.copyfile(_HERE / fn, tr_dir / fn)

            def _resign_rec(obj: dict[str, object]) -> dict[str, object]:
                body = {k: v for k, v in obj.items() if k != "receipt_sha256"}
                out = dict(body)
                out["receipt_sha256"] = hashlib.sha256(
                    json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
                ).hexdigest()
                return out

            _reset_zb()
            self.assertTrue(w11.verify_w11_zone_b_bundle(tr_dir)["passed"])

            # Non-git dir: _capture_git_head -> (None, "not_captured_at_run_time"), forged 40-hex rejected, ambient GIT_* stripped & TimeoutExpired handled!
            self.assertEqual(w11._capture_git_head(base), (None, "not_captured_at_run_time"))
            with patch.dict(os.environ, {"GIT_DIR": "/nonexistent/gitdir", "GIT_WORK_TREE": "/nonexistent/wt"}):
                cleaned_env = w11._clean_git_env()
                self.assertNotIn("GIT_DIR", cleaned_env)
                self.assertNotIn("GIT_WORK_TREE", cleaned_env)
            non_exec_git = base / "non_exec_git"
            non_exec_git.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(non_exec_git, 0o644)
            with patch.object(w11, "_GIT_EXE_CANDIDATES", (str(non_exec_git),)):
                self.assertIsNone(w11._resolve_git_exe())
            with patch.object(w11, "_resolve_git_exe", return_value=None):
                self.assertEqual(w11._capture_git_head(base), (None, "not_captured_at_run_time"))
                self.assertFalse(w11._verify_git_commit_exists(base, "a" * 40))
            with patch.object(w11.subprocess, "run", side_effect=OSError("git unavailable")):
                self.assertEqual(w11._capture_git_head(base), (None, "not_captured_at_run_time"))
                self.assertFalse(w11._verify_git_commit_exists(base, "a" * 40))
            with patch.object(w11.subprocess, "run", side_effect=subprocess.TimeoutExpired(["git"], 5)):
                self.assertEqual(w11._capture_git_head(base), (None, "not_captured_at_run_time"))
                self.assertFalse(w11._verify_git_commit_exists(base, "a" * 40))
            with patch.object(w11.subprocess, "run", return_value=subprocess.CompletedProcess(["git"], 0, stdout=b"\xff\xfe", stderr=b"")):
                self.assertEqual(w11._capture_git_head(base), (None, "not_captured_at_run_time"))
            with patch.object(w11.subprocess, "run", return_value=subprocess.CompletedProcess(["git"], 1, stdout=b"a" * 40 + b"\n", stderr=b"")):
                self.assertEqual(w11._capture_git_head(base), (None, "not_captured_at_run_time"))
            with patch.object(w11.subprocess, "run", return_value=subprocess.CompletedProcess(["git"], 0, stdout=b"not_a_hex_sha\n", stderr=b"")):
                self.assertEqual(w11._capture_git_head(base), (None, "not_captured_at_run_time"))
            with patch.object(
                w11.subprocess,
                "run",
                side_effect=[
                    subprocess.CompletedProcess(["git"], 0, stdout=b"a" * 40 + b"\n", stderr=b""),
                    subprocess.CompletedProcess(["git"], 1, stdout=b"", stderr=b""),
                ],
            ):
                self.assertEqual(w11._capture_git_head(base), ("a" * 40, "captured_dirty"))
            with patch.object(
                w11.subprocess,
                "run",
                side_effect=[
                    subprocess.CompletedProcess(["git"], 0, stdout=b"a" * 40 + b"\n", stderr=b""),
                    subprocess.CompletedProcess(["git"], 0, stdout=b"\xff\xfe", stderr=b""),
                ],
            ):
                self.assertEqual(w11._capture_git_head(base), ("a" * 40, "captured_dirty"))
            rec_fake = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
            rec_fake["git_head"] = "b" * 40
            rec_fake["git_head_status"] = "captured"
            (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_fake)), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_fake_hex:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_fake_hex.exception.code, "RECEIPT_BINDING_MISMATCH")

            # Real temporary git repository: genuine commit passes (when results & receipt agree), mismatches/forged fail, dirty detected!
            with tempfile.TemporaryDirectory() as td_git:
                gbase = Path(td_git)
                gpr = gbase / "preregistrations"
                gtr = gbase / "track_s121_loopcd_platosphere"
                gpr.mkdir()
                gtr.mkdir()
                shutil.copyfile(_HERE.parent / "preregistrations" / w11.PREREG_FILENAME, gpr / w11.PREREG_FILENAME)
                for fn in ("w11_live_loopcd_platosphere_results.json", "mlos_zone_b_w11_loopcd_platosphere.json", "ux582hs-rtx3080-8gb.toml"):
                    shutil.copyfile(_HERE / fn, gtr / fn)
                git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
                subprocess.run(["git", "-C", str(gbase), "init", "-q"], check=True, env=git_env)
                subprocess.run(["git", "-C", str(gbase), "add", "."], check=True, env=git_env)
                subprocess.run(["git", "-C", str(gbase), "commit", "-q", "-m", "init"], check=True, env=git_env)

                real_sha, real_status = w11._capture_git_head(gbase)
                self.assertIsNotNone(real_sha)
                self.assertEqual(real_status, "captured")

                # Dirty repo detection
                (gbase / "untracked.txt").write_text("dirty\n", encoding="utf-8")
                dirty_sha, dirty_status = w11._capture_git_head(gbase)
                self.assertEqual(dirty_sha, real_sha)
                self.assertEqual(dirty_status, "captured_dirty")
                (gbase / "untracked.txt").unlink()

                # Receipt claiming captured while results omits git_head -> REJECTED (Finding 4)!
                rec_real = json.loads((gtr / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
                rec_real["git_head"] = real_sha
                rec_real["git_head_status"] = "captured"
                (gtr / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_real)), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_nores_gh:
                    w11.verify_w11_zone_b_bundle(gtr)
                self.assertEqual(cm_nores_gh.exception.code, "RECEIPT_BINDING_MISMATCH")

                # Genuine commit SHA paired across BOTH results and receipt -> PASS (and strict committed-pin check rejects re-signed bundle)!
                res_real = json.loads((gtr / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
                res_real["git_head"] = real_sha
                res_real["git_head_status"] = "captured"
                res_body = {k: v for k, v in res_real.items() if k != "payload_sha256"}
                res_real["payload_sha256"] = hashlib.sha256(w11._canonical_json_bytes(res_body)).hexdigest()
                res_bytes = (json.dumps(res_real, indent=2, sort_keys=True) + "\n").encode("utf-8")
                (gtr / "w11_live_loopcd_platosphere_results.json").write_bytes(res_bytes)
                rec_real["bound_results_payload_sha256"] = res_real["payload_sha256"]
                rec_real["bound_results_file_sha256"] = hashlib.sha256(res_bytes).hexdigest()
                (gtr / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_real)), encoding="utf-8")

                zb_real = w11.verify_w11_zone_b_bundle(gtr)
                self.assertTrue(zb_real["passed"])
                self.assertEqual(zb_real["git_head_status"], "captured")
                self.assertTrue(w11.verify_w11_zone_b_bundle(gtr, expected_git_head=real_sha)["passed"])
                with self.assertRaises(w11.Wave11ProbeError) as cm_pin:
                    w11.verify_w11_zone_b_bundle(gtr, verify_committed_pins=True)
                self.assertEqual(cm_pin.exception.code, "RECEIPT_PIN_MISMATCH")
                # Trailing newline keeps canonical payload_sha256 == PINNED while changing results_file_sha & receipt_sha256 (kills and->or BoolOp on committed pins!)
                _reset_zb()
                raw_res_pad = (tr_dir / "w11_live_loopcd_platosphere_results.json").read_bytes() + b"\n"
                (tr_dir / "w11_live_loopcd_platosphere_results.json").write_bytes(raw_res_pad)
                rec_pad = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
                rec_pad["bound_results_file_sha256"] = hashlib.sha256(raw_res_pad).hexdigest()
                (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_pad)), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_pin_pad:
                    w11.verify_w11_zone_b_bundle(tr_dir, verify_committed_pins=True)
                self.assertEqual(cm_pin_pad.exception.code, "RECEIPT_PIN_MISMATCH")
                _reset_zb()
                with self.assertRaises(w11.Wave11ProbeError) as cm_exp_gh:
                    w11.verify_w11_zone_b_bundle(gtr, expected_git_head="0" * 40)
                self.assertEqual(cm_exp_gh.exception.code, "RECEIPT_BINDING_MISMATCH")
                with self.assertRaises(w11.Wave11ProbeError) as cm_exp_na:
                    w11.verify_w11_zone_b_bundle(gtr, expected_git_head="\u00e9" * 40)
                self.assertEqual(cm_exp_na.exception.code, "RECEIPT_BINDING_MISMATCH")

                # Mismatched results git_head vs receipt git_head -> REJECTED!
                res_real["git_head_status"] = "captured_dirty"
                res_body2 = {k: v for k, v in res_real.items() if k != "payload_sha256"}
                res_real["payload_sha256"] = hashlib.sha256(w11._canonical_json_bytes(res_body2)).hexdigest()
                res_bytes2 = (json.dumps(res_real, indent=2, sort_keys=True) + "\n").encode("utf-8")
                (gtr / "w11_live_loopcd_platosphere_results.json").write_bytes(res_bytes2)
                rec_real["bound_results_payload_sha256"] = res_real["payload_sha256"]
                rec_real["bound_results_file_sha256"] = hashlib.sha256(res_bytes2).hexdigest()
                (gtr / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_real)), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_gh_mis:
                    w11.verify_w11_zone_b_bundle(gtr)
                self.assertEqual(cm_gh_mis.exception.code, "RECEIPT_BINDING_MISMATCH")

                # Forged non-existent 40-hex commit inside real git repo -> REJECTED!
                rec_real["git_head"] = "b" * 40
                (gtr / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_real)), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_forged_git:
                    w11.verify_w11_zone_b_bundle(gtr)
                self.assertEqual(cm_forged_git.exception.code, "RECEIPT_BINDING_MISMATCH")

            # Corrupt JSON, non-dict, NaN/Infinity, duplicate keys, oversized int digits, & deep nesting on BOTH files -> rc == 2!
            deep_dict = '{"a":' * (w11.MAX_JSON_DEPTH + 2) + "1" + "}" * (w11.MAX_JSON_DEPTH + 2)
            deep_list = '{"a":' + "[" * (w11.MAX_JSON_DEPTH + 1) + "1" + "]" * (w11.MAX_JSON_DEPTH + 1) + "}"
            deep_rec = '{"a":' * 1500 + "1" + "}" * 1500
            big_int = '{"n": ' + ("9" * (w11.MAX_JSON_INT_DIGITS + 1)) + "}"
            big_neg_int = '{"n": -' + ("9" * (w11.MAX_JSON_INT_DIGITS + 1)) + "}"
            for fname, exp_code in (
                ("w11_live_loopcd_platosphere_results.json", "RESULTS_JSON_INVALID"),
                ("mlos_zone_b_w11_loopcd_platosphere.json", "RECEIPT_JSON_INVALID"),
            ):
                for bad_txt in (
                    "{bad json",
                    "[]",
                    '{"nan_probe": NaN}',
                    '{"inf_probe": Infinity}',
                    '{"neg_inf": -Infinity}',
                    '{"ovf_pos": 1e999}',
                    '{"ovf_neg": -1e999}',
                    '{"dup": 1, "dup": 2}',
                    big_int,
                    big_neg_int,
                    deep_dict,
                    deep_list,
                    deep_rec,
                ):
                    _reset_zb()
                    (tr_dir / fname).write_text(bad_txt, encoding="utf-8")
                    with self.assertRaises(w11.Wave11ProbeError) as cm_js:
                        w11.verify_w11_zone_b_bundle(tr_dir)
                    self.assertEqual(cm_js.exception.code, exp_code)

            # Exact boundary positive checks for _parse_json_dict_bytes (kills <= to < on digit cap & depth cap!)
            exact_int_obj = w11._parse_json_dict_bytes(
                ('{"n": -' + ("9" * w11.MAX_JSON_INT_DIGITS) + "}").encode("utf-8"),
                "exact_int.json",
                "TEST_CODE",
            )
            self.assertEqual(exact_int_obj["n"], -(10**w11.MAX_JSON_INT_DIGITS - 1))
            exact_depth_bytes = ('{"a":' + "[" * (w11.MAX_JSON_DEPTH - 1) + "1" + "]" * (w11.MAX_JSON_DEPTH - 1) + "}").encode("utf-8")
            self.assertIsInstance(w11._parse_json_dict_bytes(exact_depth_bytes, "exact_depth.json", "TEST_CODE"), dict)

            # Direct _load_json_dict, _read_regular_file_bytes byte-cap boundary (<= vs <), os.fstat/os.read OSError, root "/", relative path, symlink, ancestor symlink, & FIFO refusal!
            cap_file = base / "cap_probe.bin"
            cap_file.write_bytes(b"x" * 16)
            self.assertEqual(len(w11._read_regular_file_bytes(cap_file, "CAP_ERR", max_bytes=16)), 16)
            old_cwd_w11 = os.getcwd()
            try:
                os.chdir(base)
                self.assertEqual(len(w11._read_regular_file_bytes(Path("./cap_probe.bin"), "CAP_ERR", max_bytes=16)), 16)
            finally:
                os.chdir(old_cwd_w11)
            with self.assertRaises(w11.Wave11ProbeError) as cm_rslash:
                w11._read_regular_file_bytes(Path("/"), "CAP_ERR")
            self.assertEqual(cm_rslash.exception.code, "CAP_ERR")
            with patch.object(w11.os, "open", side_effect=OSError("root fail")):
                with self.assertRaises(w11.Wave11ProbeError) as cm_ropen:
                    w11._read_regular_file_bytes(cap_file, "CAP_ERR")
                self.assertEqual(cm_ropen.exception.code, "CAP_ERR")
            with patch.object(w11.os, "fstat", side_effect=OSError("EBADF")):
                with self.assertRaises(w11.Wave11ProbeError) as cm_fst:
                    w11._read_regular_file_bytes(cap_file, "CAP_ERR", max_bytes=16)
                self.assertEqual(cm_fst.exception.code, "CAP_ERR")
            with patch.object(w11.os, "read", side_effect=OSError("EIO")):
                with self.assertRaises(w11.Wave11ProbeError) as cm_eio:
                    w11._read_regular_file_bytes(cap_file, "CAP_ERR", max_bytes=16)
                self.assertEqual(cm_eio.exception.code, "CAP_ERR")
            cap_file.write_bytes(b"x" * 17)
            with self.assertRaises(w11.Wave11ProbeError) as cm_cap:
                w11._read_regular_file_bytes(cap_file, "CAP_ERR", max_bytes=16)
            self.assertEqual(cm_cap.exception.code, "CAP_ERR")
            self.assertNotIn(str(base), cm_cap.exception.message)

            # Symlinked results/receipt/profile/prereg + ancestor symlink + FIFO -> fail closed (zero path leak, zero hang!)
            _reset_zb()
            valid_json_p = base / "valid_direct.json"
            valid_json_p.write_text('{"ok": 1}\n', encoding="utf-8")
            self.assertEqual(w11._load_json_dict(valid_json_p, "DIRECT_ERR"), {"ok": 1})
            sym_direct = base / "sym_direct.json"
            os.symlink(valid_json_p, sym_direct)
            with self.assertRaises(w11.Wave11ProbeError) as cm_sdir:
                w11._load_json_dict(sym_direct, "DIRECT_ERR")
            self.assertEqual(cm_sdir.exception.code, "DIRECT_ERR")
            self.assertNotIn(str(valid_json_p), cm_sdir.exception.message)

            # Subprocess --check-zone-b --json against symlinked results.json, NaN, duplicate key, deep nesting, & FIFO -> RC=2!
            _reset_zb()
            real_res_bak = base / "real_results_target.json"
            shutil.copyfile(tr_dir / "w11_live_loopcd_platosphere_results.json", real_res_bak)
            (tr_dir / "w11_live_loopcd_platosphere_results.json").unlink()
            os.symlink(real_res_bak, tr_dir / "w11_live_loopcd_platosphere_results.json")
            proc_sym = subprocess.run(
                [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_sym.returncode, 2)
            self.assertNotIn("Traceback", proc_sym.stderr)
            sym_out = json.loads(proc_sym.stdout)
            self.assertFalse(sym_out["passed"])
            self.assertEqual(sym_out["code"], "ZONEB_FILE_MISSING")
            self.assertNotIn(str(real_res_bak), sym_out["message"])

            # Ancestor & grandparent symlink above track_dir -> refused!
            _reset_zb()
            sym_tr = base / "sym_track_dir"
            os.symlink(tr_dir, sym_tr)
            with self.assertRaises(w11.Wave11ProbeError) as cm_anc:
                w11.verify_w11_zone_b_bundle(sym_tr)
            self.assertEqual(cm_anc.exception.code, "ZONEB_PREREG_MISSING")

            with tempfile.TemporaryDirectory() as td_gp:
                gp_base = Path(td_gp)
                real_root = gp_base / "real_gp" / "bundle"
                (real_root / "preregistrations").mkdir(parents=True)
                (real_root / "track_s121_loopcd_platosphere").mkdir(parents=True)
                shutil.copyfile(_HERE.parent / "preregistrations" / w11.PREREG_FILENAME, real_root / "preregistrations" / w11.PREREG_FILENAME)
                for fn in ("w11_live_loopcd_platosphere_results.json", "mlos_zone_b_w11_loopcd_platosphere.json", "ux582hs-rtx3080-8gb.toml"):
                    shutil.copyfile(_HERE / fn, real_root / "track_s121_loopcd_platosphere" / fn)
                os.symlink(gp_base / "real_gp", gp_base / "sym_gp")
                with self.assertRaises(w11.Wave11ProbeError) as cm_gp:
                    w11.verify_w11_zone_b_bundle(gp_base / "sym_gp" / "bundle" / "track_s121_loopcd_platosphere")
                self.assertEqual(cm_gp.exception.code, "ZONEB_PREREG_MISSING")

            # FIFO replacing results.json -> O_NONBLOCK + S_ISREG fails immediately without hanging!
            _reset_zb()
            (tr_dir / "w11_live_loopcd_platosphere_results.json").unlink()
            os.mkfifo(tr_dir / "w11_live_loopcd_platosphere_results.json")
            with self.assertRaises(w11.Wave11ProbeError) as cm_fifo:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_fifo.exception.code, "ZONEB_FILE_MISSING")
            (tr_dir / "w11_live_loopcd_platosphere_results.json").unlink()

            # Subprocess --check-zone-b --json against NaN, duplicate key, and deep recursion on results.json -> RC=2, zero traceback!
            for adv_txt in ('{"nan_probe": NaN}', '{"dup": 1, "dup": 2}', deep_rec):
                _reset_zb()
                (tr_dir / "w11_live_loopcd_platosphere_results.json").write_text(adv_txt, encoding="utf-8")
                proc_adv = subprocess.run(
                    [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc_adv.returncode, 2)
                self.assertNotIn("Traceback", proc_adv.stderr)
                adv_out = json.loads(proc_adv.stdout)
                self.assertFalse(adv_out["passed"])
                self.assertEqual(adv_out["code"], "RESULTS_JSON_INVALID")

            # Live subprocess rc == 2 + zero-Traceback checks for corrupt/non-dict JSON on receipt!
            for bad_txt in ("{bad json", "[]"):
                _reset_zb()
                (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(bad_txt, encoding="utf-8")
                proc_bad_js = subprocess.run(
                    [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc_bad_js.returncode, 2)
                self.assertIn("FAIL S121_ZONE_B code=RECEIPT_JSON_INVALID", proc_bad_js.stderr)
                self.assertNotIn("Traceback", proc_bad_js.stderr)

                proc_bad_js_out = subprocess.run(
                    [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir), "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc_bad_js_out.returncode, 2)
                self.assertNotIn("Traceback", proc_bad_js_out.stderr)
                err_json = json.loads(proc_bad_js_out.stdout)
                self.assertFalse(err_json["passed"])
                self.assertEqual(err_json["code"], "RECEIPT_JSON_INVALID")

            # Non-Zone-B CLI (--selftest-stdlib) with corrupt & non-dict JSON on disk -> rc == 2, FAIL S121_W11_PROBE, zero traceback!
            shutil.copy(_HERE / "run_w11_live_loopcd_platosphere.py", tr_dir / "run_w11_live_loopcd_platosphere.py")
            for fname, exp_code in (
                ("mlos_zone_b_w11_loopcd_platosphere.json", "RECEIPT_JSON_INVALID"),
                ("w11_live_loopcd_platosphere_results.json", "RESULTS_JSON_INVALID"),
            ):
                for bad_txt in ("{bad json", "[]"):
                    _reset_zb()
                    (tr_dir / fname).write_text(bad_txt, encoding="utf-8")
                    p_st_bad = subprocess.run(
                        [sys.executable, "-I", "-B", str(tr_dir / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(p_st_bad.returncode, 2)
                    self.assertIn(f"FAIL S121_W11_PROBE code={exp_code}", p_st_bad.stderr)
                    self.assertNotIn("Traceback", p_st_bad.stderr)
            (tr_dir / "run_w11_live_loopcd_platosphere.py").unlink()

            _reset_zb()
            (pr_dir / w11.PREREG_FILENAME).unlink()
            with self.assertRaises(w11.Wave11ProbeError) as cm_z1:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_z1.exception.code, "ZONEB_PREREG_MISSING")

            (pr_dir / w11.PREREG_FILENAME).write_text("bad\n", encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_z2:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_z2.exception.code, "PREREG_HASH_MISMATCH")

            for miss_fn in ("w11_live_loopcd_platosphere_results.json", "mlos_zone_b_w11_loopcd_platosphere.json", "ux582hs-rtx3080-8gb.toml"):
                _reset_zb()
                (tr_dir / miss_fn).unlink()
                with self.assertRaises(w11.Wave11ProbeError) as cm_zm:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_zm.exception.code, "ZONEB_FILE_MISSING")

            for bad_sha in ("short", "\u00e9" * 64, "A" * 64, 123):
                _reset_zb()
                r_obj = json.loads((tr_dir / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
                r_obj["payload_sha256"] = bad_sha
                (tr_dir / "w11_live_loopcd_platosphere_results.json").write_text(json.dumps(r_obj), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_rs1:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_rs1.exception.code, "RESULTS_SHA_MISSING")

            # Extra or missing top-level keys in results JSON (including lone git_head without git_head_status) -> RESULTS_SCHEMA_INVALID!
            for res_schema_mut in (
                lambda o: o.__setitem__("extra_key", 1),
                lambda o: o.__setitem__("git_head", None),
                lambda o: o.pop("wall_seconds"),
            ):
                _reset_zb()
                r_obj = json.loads((tr_dir / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
                res_schema_mut(r_obj)
                (tr_dir / "w11_live_loopcd_platosphere_results.json").write_text(json.dumps(r_obj), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_rsk:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_rsk.exception.code, "RESULTS_SCHEMA_INVALID")

            # Finding 3 (MED): Coherently re-signed Probe A / Probe B / wall_seconds stripping or verdict forgery -> RESULTS_PROBES_INVALID!
            for probe_mut in (
                lambda o: o.__setitem__("wall_seconds", True),
                lambda o: o.__setitem__("wall_seconds", 0.0),
                lambda o: o.__setitem__("wall_seconds", 10**400),
                lambda o: o.__setitem__("probe_a_loopcd_strang_holosphere_v3", {}),
                lambda o: o.__setitem__("probe_a_loopcd_strang_holosphere_v3", []),
                lambda o: o["probe_a_loopcd_strang_holosphere_v3"].__setitem__("summary", {"fake": True}),
                lambda o: o["probe_a_loopcd_strang_holosphere_v3"]["summary"].__setitem__("gate_W11_A2_verdict", "FALSIFIED"),
                lambda o: o.__setitem__("probe_b_platos_key_spheremap_procrustes", {}),
                lambda o: o.__setitem__("probe_b_platos_key_spheremap_procrustes", []),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["model_recall_summary"]["Qwen/Qwen2.5-0.5B"].__setitem__("total_facts", 10),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["pairs"].pop("Qwen2.5-0.5B_to_Qwen2.5-1.5B"),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["pairs"]["Qwen2.5-0.5B_to_Qwen2.5-1.5B"].pop("test_transfer_accuracy"),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["summary"].__setitem__("gate_W11_B3_spheremap_verdict", "CONFIRMED"),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["summary"].__setitem__("gate_W11_B1_plato_replication_pass", True),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["summary"].__setitem__("gate_W11_B2_ols_shrinkage_pass", False),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["summary"].__setitem__("pooled_dark_memories_total", 999),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["summary"].__setitem__("mean_frob_procrustes", 0.9999),
                lambda o: o["probe_b_platos_key_spheremap_procrustes"]["summary"].__setitem__("mean_spheremap_quadrupole", 0.9999),
            ):
                _reset_zb()
                r_obj = json.loads((tr_dir / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
                probe_mut(r_obj)
                r_body = {k: v for k, v in r_obj.items() if k != "payload_sha256"}
                r_obj["payload_sha256"] = hashlib.sha256(w11._canonical_json_bytes(r_body)).hexdigest()
                r_bytes = json.dumps(r_obj).encode("utf-8")
                (tr_dir / "w11_live_loopcd_platosphere_results.json").write_bytes(r_bytes)
                rec_p = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
                rec_p["bound_results_payload_sha256"] = r_obj["payload_sha256"]
                rec_p["bound_results_file_sha256"] = hashlib.sha256(r_bytes).hexdigest()
                (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_p)), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_prb:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_prb.exception.code, "RESULTS_PROBES_INVALID")

            # Extra or missing top-level key in receipt JSON -> RECEIPT_SCHEMA_INVALID!
            _reset_zb()
            rec_extra = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
            rec_extra["unexpected_field"] = 1
            (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_extra)), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_rext:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_rext.exception.code, "RECEIPT_SCHEMA_INVALID")

            _reset_zb()
            r_obj = json.loads((tr_dir / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
            r_obj["payload_sha256"] = "0" * 64
            (tr_dir / "w11_live_loopcd_platosphere_results.json").write_text(json.dumps(r_obj), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_rs2:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_rs2.exception.code, "RESULTS_SHA_MISMATCH")

            for bad_res_updates in (
                {"prereg_sha256": "0" * 64},
                {"schema": "bad.schema"},
                {"prereg_filename": "WRONG.md"},
                {"gpu_name": "FAKE_GPU_9999"},
            ):
                _reset_zb()
                r_obj = json.loads((tr_dir / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
                r_obj.update(bad_res_updates)
                r_body = {k: v for k, v in r_obj.items() if k != "payload_sha256"}
                r_obj["payload_sha256"] = hashlib.sha256(w11._canonical_json_bytes(r_body)).hexdigest()
                (tr_dir / "w11_live_loopcd_platosphere_results.json").write_text(json.dumps(r_obj), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_rp:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_rp.exception.code, "RESULTS_PREREG_MISMATCH")

            # Finding 2 (HIGH+MED): coherently re-signed receipt tampering GPU/hardware/determinism_pins/host/bool-coercion MUST fail!
            for hw_mut in (
                lambda o: o.__setitem__("schema", "bad-schema"),
                lambda o: o.__setitem__("determinism_zone", "A"),
                lambda o: o.__setitem__("clean_hardware_run", False),
                lambda o: o.__setitem__("clean_hardware_run", 1),
                lambda o: o.__setitem__("anomalies", ["thermal_event"]),
                lambda o: o.__setitem__("determinism_pins", {}),
                lambda o: o["determinism_pins"].__setitem__("PYTHONHASHSEED", "42"),
                lambda o: o.__setitem__("gpu_telemetry_available", False),
                lambda o: o.__setitem__("gpu_telemetry_available", 1),
                lambda o: o.__setitem__("host", []),
                lambda o: o["host"].__setitem__("host_os", "windows"),
                lambda o: o["host"].__setitem__("cpu_isa", "arm64"),
                lambda o: o["host"].__setitem__("os_release", ""),
                lambda o: o["host"].__setitem__("python_version", ""),
                lambda o: o.__setitem__("profile_id", "fake-profile"),
                lambda o: o.__setitem__("execution", []),
                lambda o: o["execution"].__setitem__("exit_code", False),
                lambda o: o["execution"].__setitem__("exit_code", 1),
                lambda o: o.__setitem__("start_gpu_telemetry", []),
                lambda o: o.__setitem__("end_gpu_telemetry", []),
                lambda o: o["start_gpu_telemetry"].__setitem__("gpu_name", "FAKE_GPU_9999"),
                lambda o: o["end_gpu_telemetry"].__setitem__("gpu_name", "FAKE_GPU_9999"),
                lambda o: o["start_gpu_telemetry"].__setitem__("gpu_processes_queried", 1),
                lambda o: o["end_gpu_telemetry"].__setitem__("gpu_processes_queried", False),
                lambda o: o["start_gpu_telemetry"].__setitem__("clocks_event_reasons", []),
                lambda o: o["end_gpu_telemetry"].__setitem__("clocks_event_reasons", []),
                lambda o: o["start_gpu_telemetry"]["clocks_event_reasons"].__setitem__("thermal_throttled", True),
                lambda o: o["start_gpu_telemetry"]["clocks_event_reasons"].__setitem__("thermal_throttled", 0),
                lambda o: o["end_gpu_telemetry"]["clocks_event_reasons"].__setitem__("thermal_throttled", True),
                lambda o: o["end_gpu_telemetry"]["clocks_event_reasons"].__setitem__("thermal_throttled", 0),
                lambda o: o["start_gpu_telemetry"]["clocks_event_reasons"].__setitem__("slowdown_active", True),
                lambda o: o["end_gpu_telemetry"]["clocks_event_reasons"].__setitem__("slowdown_active", 0),
            ):
                _reset_zb()
                rec_hw = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
                hw_mut(rec_hw)
                (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_hw)), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_hw:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_hw.exception.code, "RECEIPT_HARDWARE_INVALID")

            # Tampered profile file on disk (even if coherently re-signed in receipt) -> RECEIPT_HARDWARE_INVALID!
            _reset_zb()
            (tr_dir / "ux582hs-rtx3080-8gb.toml").write_text("tampered = true\n", encoding="utf-8")
            rec_prof = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
            rec_prof["profile_sha256"] = hashlib.sha256(b"tampered = true\n").hexdigest()
            (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_prof)), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_prof:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_prof.exception.code, "RECEIPT_HARDWARE_INVALID")

            for bad_rec_sha in (123, "\u00e9" * 64, "A" * 64):
                _reset_zb()
                rec_obj = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
                rec_obj["receipt_sha256"] = bad_rec_sha
                (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(rec_obj), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_rc1:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_rc1.exception.code, "RECEIPT_SHA_MISSING")
            # Subprocess check for non-ASCII receipt_sha256 -> RC=2, zero Traceback (Finding 1)!
            proc_na = subprocess.run(
                [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_na.returncode, 2)
            self.assertIn("RECEIPT_SHA_MISSING", proc_na.stderr)
            self.assertNotIn("Traceback", proc_na.stderr)

            _reset_zb()
            rec_obj = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
            rec_obj["receipt_sha256"] = "0" * 64
            (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(rec_obj), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_rc2:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_rc2.exception.code, "RECEIPT_SHA_MISMATCH")
            proc_sha = subprocess.run(
                [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_sha.returncode, 2)
            self.assertIn("FAIL S121_ZONE_B code=RECEIPT_SHA_MISMATCH", proc_sha.stderr)
            self.assertNotIn("Traceback", proc_sha.stderr)

            for updates in (
                {"bound_results_file": "other.json"},
                {"bound_results_payload_sha256": "0" * 64},
                {"bound_results_file_sha256": "0" * 64},
                {"bound_prereg_sha256": "0" * 64},
                {"bound_profile_file": "other.toml"},
                {"profile_sha256": "0" * 64},
                {"git_head": 123, "git_head_status": "captured"},
                {"git_head": "deadbeef", "git_head_status": "captured"},
                {"git_head": "a" * 40, "git_head_status": "not_captured_at_run_time"},
                {"git_head": None, "git_head_status": "captured"},
                {"git_head": None, "git_head_status": "fabricated"},
                {"energy_power_status": "CLAIMED_WATTS"},
            ):
                _reset_zb()
                rec_obj = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
                rec_obj.update(updates)
                (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_obj)), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_rb:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_rb.exception.code, "RECEIPT_BINDING_MISMATCH")

            # Subprocess CLI rc == 2 + zero traceback for RECEIPT_BINDING_MISMATCH (text & --json)
            proc_bind = subprocess.run(
                [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_bind.returncode, 2)
            self.assertIn("FAIL S121_ZONE_B code=RECEIPT_BINDING_MISMATCH", proc_bind.stderr)
            self.assertNotIn("Traceback", proc_bind.stderr)
            proc_bind_j = subprocess.run(
                [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_bind_j.returncode, 2)
            self.assertNotIn("Traceback", proc_bind_j.stderr)
            self.assertEqual(json.loads(proc_bind_j.stdout)["code"], "RECEIPT_BINDING_MISMATCH")

            # Issue #123 Item 2: CLI --check-zone-b plant failures exit cleanly with rc=2 and structured FAIL line
            _reset_zb()
            (pr_dir / w11.PREREG_FILENAME).unlink()
            err_zb = io.StringIO()
            with redirect_stderr(err_zb):
                rc_txt = w11.main(["--check-zone-b", "--track-dir", str(tr_dir)])
            self.assertEqual(rc_txt, 2)
            self.assertIn("FAIL S121_ZONE_B code=ZONEB_PREREG_MISSING", err_zb.getvalue())

            out_zb_err = io.StringIO()
            with redirect_stdout(out_zb_err):
                rc_js = w11.main(["--check-zone-b", "--track-dir", str(tr_dir), "--json"])
            self.assertEqual(rc_js, 2)
            parsed_err = json.loads(out_zb_err.getvalue())
            self.assertFalse(parsed_err["passed"])
            self.assertEqual(parsed_err["code"], "ZONEB_PREREG_MISSING")

            proc_zb_fail = subprocess.run(
                [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--check-zone-b", "--track-dir", str(tr_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_zb_fail.returncode, 2)
            self.assertIn("FAIL S121_ZONE_B code=ZONEB_PREREG_MISSING", proc_zb_fail.stderr)
            self.assertNotIn("Traceback", proc_zb_fail.stderr)

        # Issue #123 Item 3: Isolated snapshot WITHOUT PREREG file fails closed with rc=2 and zero traceback!
        with tempfile.TemporaryDirectory() as td:
            snap = Path(td) / "track_snap"
            snap.mkdir()
            shutil.copy(_HERE / "run_w11_live_loopcd_platosphere.py", snap / "run_w11_live_loopcd_platosphere.py")
            proc_miss = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_miss.returncode, 2)
            self.assertIn("FAIL S121_W11_PROBE code=PREREG_MISSING", proc_miss.stderr)
            self.assertNotIn("Traceback", proc_miss.stderr)

            proc_miss_j = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_miss_j.returncode, 2)
            self.assertNotIn("Traceback", proc_miss_j.stderr)
            self.assertEqual(json.loads(proc_miss_j.stdout)["code"], "PREREG_MISSING")

            # Legacy notes/portals_wave11_2026_11_25/ PREREG resolution path:
            # Default --selftest-stdlib without Zone-B receipt MUST fail closed (ZONEB_FILE_MISSING); --allow-missing-zone-b opts in!
            legacy_dir = Path(td) / "notes" / "portals_wave11_2026_11_25"
            legacy_dir.mkdir(parents=True)
            shutil.copyfile(_HERE.parent / "preregistrations" / w11.PREREG_FILENAME, legacy_dir / w11.PREREG_FILENAME)
            proc_no_zb = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_no_zb.returncode, 2)
            self.assertIn("ZONEB_PREREG_MISSING", proc_no_zb.stderr)
            proc_leg_ok = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib", "--allow-missing-zone-b", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_leg_ok.returncode, 0, proc_leg_ok.stderr)
            self.assertEqual(json.loads(proc_leg_ok.stdout)["prereg_source"], "disk_verified")

            (legacy_dir / w11.PREREG_FILENAME).write_text("TAMPERED_LEGACY\n", encoding="utf-8")
            proc_leg_bad = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib", "--allow-missing-zone-b"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_leg_bad.returncode, 2)
            self.assertIn("PREREG_HASH_MISMATCH", proc_leg_bad.stderr)
            self.assertNotIn("Traceback", proc_leg_bad.stderr)
            (legacy_dir / w11.PREREG_FILENAME).unlink()

            # Providing the genuine sibling preregistrations/ file without Zone-B receipt fails closed (ZONEB_FILE_MISSING); --allow-missing-zone-b passes!
            pr_snap = Path(td) / "preregistrations"
            pr_snap.mkdir()
            shutil.copyfile(_HERE.parent / "preregistrations" / w11.PREREG_FILENAME, pr_snap / w11.PREREG_FILENAME)
            proc_no_zb_rec = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_no_zb_rec.returncode, 2)
            self.assertIn("ZONEB_FILE_MISSING", proc_no_zb_rec.stderr)
            proc_ok = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib", "--allow-missing-zone-b", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_ok.returncode, 0, proc_ok.stderr)
            out = json.loads(proc_ok.stdout)
            self.assertTrue(out["passed"])
            self.assertEqual(out["prereg_source"], "disk_verified")
            self.assertEqual(out["prereg_sha256"], w11.PINNED_PREREG_SHA256)

            # Broken stdout/stderr on main() returns RC=2 cleanly with zero traceback!
            class _BrokenPipeStream:
                def write(self, _s: str) -> int:
                    raise BrokenPipeError("epipe")

                def flush(self) -> None:
                    raise BrokenPipeError("epipe")

            self.assertIs(w11._safe_write_stream(_BrokenPipeStream(), "x"), False)
            with patch.object(w11.sys, "stdout", _BrokenPipeStream()):
                self.assertEqual(w11.main(["--check-zone-b", "--json"]), 2)
                self.assertEqual(w11.main(["--selftest-stdlib", "--json"]), 2)
            with patch.object(w11.sys, "stderr", _BrokenPipeStream()):
                with patch.object(w11, "verify_w11_zone_b_bundle", side_effect=OSError("io")):
                    self.assertEqual(w11.main(["--check-zone-b"]), 2)

            # Tampered PREREG file on disk MUST fail closed with rc=2 and PREREG_HASH_MISMATCH!
            (pr_snap / w11.PREREG_FILENAME).write_text("TAMPERED_PREREG\n", encoding="utf-8")
            proc_bad = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib", "--allow-missing-zone-b"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_bad.returncode, 2)
            self.assertIn("PREREG_HASH_MISMATCH", proc_bad.stderr)
            self.assertNotIn("Traceback", proc_bad.stderr)

    def test_02_b1_hardened_answer_matcher_and_all_six_attack_controls(self) -> None:
        # Positive controls
        self.assertTrue(w11._answer_matches(" Berlin, which is...", "Berlin"))
        self.assertTrue(w11._answer_matches(" William Shakespeare.", "William Shakespeare"))
        self.assertTrue(w11._answer_matches(" Shakespeare", "William Shakespeare"))
        self.assertTrue(w11._answer_matches(" Kiev", "Kyiv"))
        self.assertTrue(w11._answer_matches(" He.", "He"))
        self.assertTrue(w11._answer_matches(" As,", "As"))
        self.assertTrue(w11._answer_matches(" I.", "I"))
        self.assertTrue(w11._answer_matches(" South America.", "South America"))
        self.assertTrue(w11._answer_matches(" J. R. R. Tolkien.", "J. R. R. Tolkien"))

        # B1 MUST-FAIL controls: all 6 audit false-accept strings + empty/punctuation/refusal-head/Kyiv negative controls!
        self.assertFalse(w11._answer_matches("H", "He"))
        self.assertFalse(w11._answer_matches("N", "Ne"))
        self.assertFalse(w11._answer_matches("I think so", "I"))
        self.assertFalse(w11._answer_matches("as a result", "As"))
        self.assertFalse(w11._answer_matches("J.K. Rowling", "J. R. R. Tolkien"))
        self.assertFalse(w11._answer_matches("Not Shakespeare", "William Shakespeare"))
        self.assertFalse(w11._answer_matches("North America", "South America"))
        self.assertFalse(w11._answer_matches("South Africa", "Africa"))
        self.assertFalse(w11._answer_matches(" Paris", "Berlin"))
        self.assertFalse(w11._answer_matches("Moscow", "Kyiv"))
        self.assertFalse(w11._answer_matches("", "Berlin"))
        self.assertFalse(w11._answer_matches("Berlin", ""))
        self.assertFalse(w11._answer_matches(".", ""))
        self.assertFalse(w11._answer_matches("...", "Berlin"))
        self.assertFalse(w11._answer_matches("Berlin", "..."))
        self.assertFalse(w11._answer_matches("Unknown", "Unknown"))

    def test_03_b1_swap_tuples_forbid_same_answer_collisions(self) -> None:
        same_ans = [
            ("continent", "Slovenia", "Europe"),
            ("continent", "Estonia", "Europe"),
        ]
        self.assertEqual(w11.make_swap_tuples(same_ans), [])

        mixed = [
            ("continent", "Slovenia", "Europe"),
            ("continent", "Estonia", "Europe"),
            ("continent", "Bolivia", "South America"),
            ("continent", "Nepal", "Asia"),
        ]
        ans_by_subj = {s: a for _, s, a in mixed}
        swaps = w11.make_swap_tuples(mixed)
        self.assertEqual(len(swaps), 4)
        for _rel, d_s, d_a, t_s in swaps:
            self.assertNotEqual(d_s, t_s)
            self.assertNotEqual(w11._normalize_ans(d_a), w11._normalize_ans(ans_by_subj[t_s]))

        splits = w11.build_subject_disjoint_fact_splits(20261125)
        all_ans = {s: a for _, s, a in w11.RAW_FACTS}
        for sp_name in ("val", "test"):
            sp_swaps = w11.make_swap_tuples(splits[sp_name])
            self.assertGreater(len(sp_swaps), 0)
            for _rel, d_s, d_a, t_s in sp_swaps:
                self.assertNotEqual(d_s, t_s)
                self.assertNotEqual(w11._normalize_ans(d_a), w11._normalize_ans(all_ans[t_s]))

    def test_04_b2_fail_closed_gate_graders_and_refusal_guards(self) -> None:
        # B2: Probe B grader across all branches (kills every BoolOp in grade_probe_b_verdict)
        v_under = w11.grade_probe_b_verdict(
            w11_b1_pass=False,
            mean_frob=0.2902,
            mean_sph=0.3259,
            mean_rand=0.1027,
            mean_shuf=0.1696,
            tot_dm=118,
            dm_frob_rate=0.0085,
            dm_sph_rate=0.0,
            dm_rand_rate=0.0254,
        )
        self.assertEqual(v_under, "PARTIAL_UNDERPOWERED")

        v_fail_b = w11.grade_probe_b_verdict(
            w11_b1_pass=False,
            mean_frob=0.20,
            mean_sph=0.15,
            mean_rand=0.10,
            mean_shuf=0.10,
            tot_dm=10,
            dm_frob_rate=0.0,
            dm_sph_rate=0.0,
            dm_rand_rate=0.0,
        )
        self.assertEqual(v_fail_b, "FALSIFIED")

        # CONFIRMED via diff_sph_frob >= 0.03 alone (dm_confirmed=False -> kills or->and!)
        self.assertEqual(
            w11.grade_probe_b_verdict(
                w11_b1_pass=True,
                mean_frob=0.40,
                mean_sph=0.44,
                mean_rand=0.02,
                mean_shuf=0.02,
                tot_dm=0,
                dm_frob_rate=0.0,
                dm_sph_rate=0.0,
                dm_rand_rate=0.0,
            ),
            "CONFIRMED",
        )
        # CONFIRMED via dm_confirmed alone (diff_sph_frob=0.0 -> kills or->and!)
        self.assertEqual(
            w11.grade_probe_b_verdict(
                w11_b1_pass=True,
                mean_frob=0.40,
                mean_sph=0.40,
                mean_rand=0.02,
                mean_shuf=0.02,
                tot_dm=50,
                dm_frob_rate=0.10,
                dm_sph_rate=0.25,
                dm_rand_rate=0.02,
            ),
            "CONFIRMED",
        )
        # PARTIAL when w11_b1_pass=True, diff_sph_frob=0.0, tot_dm>0 but dm_sph_rate <= 0.18 (kills dm_confirmed and->or!)
        self.assertEqual(
            w11.grade_probe_b_verdict(
                w11_b1_pass=True,
                mean_frob=0.40,
                mean_sph=0.40,
                mean_rand=0.02,
                mean_shuf=0.02,
                tot_dm=50,
                dm_frob_rate=0.10,
                dm_sph_rate=0.10,
                dm_rand_rate=0.02,
            ),
            "PARTIAL",
        )
        # FALSIFIED when w11_b1_pass=True and diff_sph_frob < -0.02
        self.assertEqual(
            w11.grade_probe_b_verdict(
                w11_b1_pass=True,
                mean_frob=0.40,
                mean_sph=0.35,
                mean_rand=0.02,
                mean_shuf=0.02,
                tot_dm=0,
                dm_frob_rate=0.0,
                dm_sph_rate=0.0,
                dm_rand_rate=0.0,
            ),
            "FALSIFIED",
        )

        # Probe A grader across CONFIRMED / PARTIAL / FALSIFIED (kills every BoolOp in grade_probe_a_verdict!)
        self.assertEqual(
            w11.grade_probe_a_verdict(
                w11_a1_pass=False,
                l6_gain=0.001,
                l6_2048_gain=0.001,
                l4_gain=-0.20,
                l3_gain=-0.33,
                su2_gain=-0.0001,
                any_bpb_gain=True,
                any_top1_gain=True,
            ),
            "FALSIFIED",
        )
        self.assertEqual(
            w11.grade_probe_a_verdict(
                w11_a1_pass=True,
                l6_gain=0.001,
                l6_2048_gain=0.001,
                l4_gain=-0.20,
                l3_gain=0.01,
                su2_gain=0.01,
                any_bpb_gain=True,
                any_top1_gain=False,
            ),
            "CONFIRMED",
        )
        self.assertEqual(
            w11.grade_probe_a_verdict(
                w11_a1_pass=True,
                l6_gain=-0.001,
                l6_2048_gain=0.01,
                l4_gain=0.01,
                l3_gain=0.01,
                su2_gain=0.01,
                any_bpb_gain=True,
                any_top1_gain=False,
            ),
            "PARTIAL",
        )
        self.assertEqual(
            w11.grade_probe_a_verdict(
                w11_a1_pass=True,
                l6_gain=0.01,
                l6_2048_gain=0.01,
                l4_gain=0.01,
                l3_gain=0.01,
                su2_gain=0.01,
                any_bpb_gain=False,
                any_top1_gain=False,
            ),
            "FALSIFIED",
        )

        # Pure-stdlib Probe A summary reducer (kills all 6 BoolOps in _summarize_probe_a_grids!)
        g2048 = {
            "L6_k1_om0.0": {"L_target": 6, "k_early": 1, "omega": 0.0, "bpb": 2.50, "top1_acc": 0.40},
            "L6_k1_om0.5": {"L_target": 6, "k_early": 1, "omega": 0.5, "bpb": 2.51, "top1_acc": 0.39},
            "L4_k1_om0.0": {"L_target": 4, "k_early": 1, "omega": 0.0, "bpb": 2.10, "top1_acc": 0.40},
            "L4_k1_om0.5": {"L_target": 4, "k_early": 1, "omega": 0.5, "bpb": 2.09, "top1_acc": 0.39},
        }
        g8192 = {
            "L6_k1_om0.0": {"L_target": 6, "k_early": 1, "omega": 0.0, "bpb": 2.60, "top1_acc": 0.40},
            "L6_k1_om0.5": {"L_target": 6, "k_early": 1, "omega": 0.5, "bpb": 2.65, "top1_acc": 0.41},
            "L4_k1_om0.0": {"L_target": 4, "k_early": 1, "omega": 0.0, "bpb": 2.80, "top1_acc": 0.35},
            "L4_k1_om0.5": {"L_target": 4, "k_early": 1, "omega": 0.5, "bpb": 2.82, "top1_acc": 0.34},
            "L3_k1_om0.0": {"L_target": 3, "k_early": 1, "omega": 0.0, "bpb": 3.00, "top1_acc": 0.30},
            "L3_k1_om0.5": {"L_target": 3, "k_early": 1, "omega": 0.5, "bpb": 2.995, "top1_acc": 0.29},
        }
        st8192 = {"k1_om0.5": {"left_over_right_err_ratio": 12.0}}
        su2_2048 = {
            "unguided_om0.0": {"bpb": 2.50, "top1_acc": 0.40},
            "strang_linear_om0.5": {"bpb": 2.51, "top1_acc": 0.39},
        }
        sum_a = w11._summarize_probe_a_grids(g2048, g8192, st8192, su2_2048)
        self.assertEqual(sum_a["best_guided_L6_t8192"]["config"], "L6_k1_om0.5")
        self.assertEqual(sum_a["best_guided_L4_t8192"]["config"], "L4_k1_om0.5")
        self.assertEqual(sum_a["best_guided_L3_t8192"]["config"], "L3_k1_om0.5")
        self.assertEqual(sum_a["gate_W11_A2_verdict"], "PARTIAL")
        # Also verify top1_acc-only gain triggers PARTIAL (no bpb gain anywhere -> kills any_top1_gain or->and!)
        g8192_nobpb = {k: dict(v) for k, v in g8192.items()}
        g8192_nobpb["L3_k1_om0.5"]["bpb"] = 3.05
        sum_a2 = w11._summarize_probe_a_grids(g2048, g8192_nobpb, st8192, su2_2048)
        self.assertEqual(sum_a2["gate_W11_A2_verdict"], "PARTIAL")
        # Zero top1 gain and single bpb gain (L3 only) -> kills any_bpb_gain or->and!
        g8192_notop = {k: dict(v) for k, v in g8192.items()}
        g8192_notop["L6_k1_om0.5"]["top1_acc"] = 0.39
        sum_a3 = w11._summarize_probe_a_grids(g2048, g8192_notop, st8192, su2_2048)
        self.assertEqual(sum_a3["gate_W11_A2_verdict"], "PARTIAL")

        # Pure-stdlib Probe B split/DM filter & gate evaluator (kills all 6 BoolOps in _filter_shared_and_dm_facts / _eval_probe_b_gates!)
        syn_splits = {
            "train": [("capital", "A", "X"), ("capital", "B", "Y")],
            "val": [("capital", "C", "Z"), ("capital", "D", "W")],
            "test": [("capital", "E", "U"), ("capital", "F", "V")],
        }
        syn_all = syn_splits["train"] + syn_splits["val"] + syn_splits["test"]
        ex_a = {"direct_ok": {"A": True, "B": True, "C": True, "D": False, "E": True, "F": True}}
        ex_b = {
            "direct_ok": {"A": True, "B": False, "C": True, "D": True, "E": True, "F": False},
            "dark_mem_ok": {"A": False, "B": True, "C": False, "D": False, "E": False, "F": False},
        }
        tr_s, va_s, te_s, dm_f = w11._filter_shared_and_dm_facts(syn_splits, syn_all, ex_a, ex_b)
        self.assertEqual([f[1] for f in tr_s], ["A"])
        self.assertEqual([f[1] for f in va_s], ["C"])
        self.assertEqual([f[1] for f in te_s], ["E"])
        self.assertEqual([f[1] for f in dm_f], ["B"])

        pr_good = {"p1": {"scales": {"s_ols": 0.8, "s_frob": 1.0}}}
        self.assertEqual(w11._eval_probe_b_gates(pr_good, 0.30, 0.25, 0.28, 0.02, 0.03), (True, True))
        self.assertEqual(w11._eval_probe_b_gates(pr_good, 0.30, 0.25, 0.28, 0.08, 0.03), (False, True))
        self.assertEqual(w11._eval_probe_b_gates(pr_good, 0.30, 0.40, 0.28, 0.02, 0.03), (True, False))

        # Pure-stdlib _greedy_decode_kv EOS branch check (kills eos_id is not None and gen_ids[-1] == int(eos_id)!)
        tok_eos = _DummyTokenizer()
        self.assertEqual(w11._greedy_decode_kv(None, _DummyModel([5, 2, 9]), tok_eos, None, max_new_tokens=5), "5,2")
        tok_no_eos = _DummyTokenizer()
        tok_no_eos.eos_token_id = None
        self.assertEqual(w11._greedy_decode_kv(None, _DummyModel([5, 2, 9]), tok_no_eos, None, max_new_tokens=3), "5,2,9")

        # Exact 120-fact boundary passes (kills >= 120 -> > 120)
        splits_120 = w11.build_subject_disjoint_fact_splits(facts=w11.RAW_FACTS[:120])
        self.assertEqual(sum(len(v) for v in splits_120.values()), 120)

        # Direct split overlap guards (kills SPLIT_LEAK + all 3 pairwise disjoint checks)
        f_a = [("capital", "Germany", "Berlin")]
        f_b = [("capital", "Spain", "Madrid")]
        f_c = [("capital", "Poland", "Warsaw")]
        w11._check_splits_disjoint(f_a, f_b, f_c)
        for tr, va, te in ((f_a, f_a, f_c), (f_a, f_b, f_a), (f_a, f_b, f_b)):
            with self.assertRaises(w11.Wave11ProbeError) as cm_ov:
                w11._check_splits_disjoint(tr, va, te)
            self.assertEqual(cm_ov.exception.code, "SPLIT_LEAK")

        # Pure-stdlib GPU precondition helper guards (clearing ALL HF cache env vars!)
        with tempfile.TemporaryDirectory() as td_h:
            p1 = Path(td_h) / "ckpt.pt"
            p2 = Path(td_h) / "eval.bin"
            p1.write_bytes(b"a")
            with self.assertRaises(w11.Wave11ProbeError) as cm_pa1:
                w11._require_probe_a_files(p1, p2)
            self.assertEqual(cm_pa1.exception.code, "PROBE_A_MISSING")
            p1.unlink()
            p2.write_bytes(b"b")
            with self.assertRaises(w11.Wave11ProbeError) as cm_pa2:
                w11._require_probe_a_files(p1, p2)
            self.assertEqual(cm_pa2.exception.code, "PROBE_A_MISSING")
            p1.write_bytes(b"a")
            w11._require_probe_a_files(p1, p2)

            clean_env = {k: v for k, v in os.environ.items() if k not in ("HF_HOME", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE")}
            with patch.dict(os.environ, {**clean_env, "HF_HOME": td_h}, clear=True):
                with self.assertRaises(w11.Wave11ProbeError) as cm_hf:
                    w11._resolve_offline_hf_snapshot("Org/MissingModel")
                self.assertEqual(cm_hf.exception.code, "OFFLINE_MODEL_MISSING")
                snap_dir = Path(td_h) / "hub" / "models--Org--PresentModel" / "snapshots" / "rev001"
                snap_dir.mkdir(parents=True)
                self.assertEqual(w11._resolve_offline_hf_snapshot("Org/PresentModel"), snap_dir)
            # Also verify HF_HUB_CACHE / HUGGINGFACE_HUB_CACHE precedence (kills or->and BoolOp!)
            with patch.dict(os.environ, {**clean_env, "HF_HUB_CACHE": str(Path(td_h) / "hub")}, clear=True):
                self.assertEqual(w11._resolve_offline_hf_snapshot("Org/PresentModel"), snap_dir)
            with patch.dict(os.environ, {**clean_env, "HUGGINGFACE_HUB_CACHE": str(Path(td_h) / "hub")}, clear=True):
                self.assertEqual(w11._resolve_offline_hf_snapshot("Org/PresentModel"), snap_dir)

            # --run-gpu without PyTorch returns clean rc == 2 + TORCH_MISSING + zero traceback!
            out_j = Path(td_h) / "out.json"
            with patch.dict(sys.modules, {"torch": None}):
                err_nt = io.StringIO()
                with redirect_stderr(err_nt):
                    rc_nt = w11.main(["--run-gpu", "--ckpt", str(p1), "--eval-bin", str(p2), "--out-json", str(out_j)])
                self.assertEqual(rc_nt, 2)
                self.assertIn("FAIL S121_W11_PROBE code=TORCH_MISSING", err_nt.getvalue())
                out_nt_j = io.StringIO()
                with redirect_stdout(out_nt_j):
                    rc_nt_j = w11.main(["--run-gpu", "--ckpt", str(p1), "--eval-bin", str(p2), "--out-json", str(out_j), "--json"])
                self.assertEqual(rc_nt_j, 2)
                self.assertEqual(json.loads(out_nt_j.getvalue())["code"], "TORCH_MISSING")

            # Live subprocess --run-gpu in stock stdlib (or with torch blocked via -c import hook) exits rc == 2, zero traceback!
            proc_gpu_notorch = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    "import sys; sys.modules['torch'] = None; "
                    f"sys.path.insert(0, {str(_HERE)!r}); "
                    "import run_w11_live_loopcd_platosphere as m; "
                    f"raise SystemExit(m.main(['--run-gpu', '--ckpt', {str(p1)!r}, '--eval-bin', {str(p2)!r}, '--out-json', {str(out_j)!r}]))",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_gpu_notorch.returncode, 2)
            self.assertIn("FAIL S121_W11_PROBE code=TORCH_MISSING", proc_gpu_notorch.stderr)
            self.assertNotIn("Traceback", proc_gpu_notorch.stderr)

        self.assertEqual(w11._require_wk_ref("ok"), "ok")
        with self.assertRaises(w11.Wave11ProbeError) as cm_wk:
            w11._require_wk_ref(None)
        self.assertEqual(cm_wk.exception.code, "WK_REF_MISSING")

        w11._require_cuda_available(True)
        with self.assertRaises(w11.Wave11ProbeError) as cm_cu:
            w11._require_cuda_available(False)
        self.assertEqual(cm_cu.exception.code, "CUDA_REQUIRED")

        # Refusal guards: DUP_SUBJECT, TOO_FEW_FACTS, SUBJ_NOT_IN_PROMPT (plus idx==0 boundary!), --run-gpu BAD_ARGS rc=2
        with self.assertRaises(w11.Wave11ProbeError) as cm_dup:
            w11.build_subject_disjoint_fact_splits(facts=[("capital", "Germany", "Berlin"), ("capital", "Germany", "Berlin")])
        self.assertEqual(cm_dup.exception.code, "DUP_SUBJECT")

        with self.assertRaises(w11.Wave11ProbeError) as cm_few:
            w11.build_subject_disjoint_fact_splits(facts=[("capital", f"Country{i}", f"City{i}") for i in range(10)])
        self.assertEqual(cm_few.exception.code, "TOO_FEW_FACTS")

        ids_0, pos_0 = w11._locate_subject_last_token(_DummyTokenizer(), "Germany is in Europe", "Germany")
        self.assertEqual(pos_0, 1)
        self.assertGreater(len(ids_0), 0)
        with self.assertRaises(w11.Wave11ProbeError) as cm_sub:
            w11._locate_subject_last_token(_DummyTokenizer(), "The capital of France is", "Germany")
        self.assertEqual(cm_sub.exception.code, "SUBJ_NOT_IN_PROMPT")

        # Partial --run-gpu args (1 provided, 2 missing -> kills and->or BoolOp on BAD_ARGS!)
        err_gpu = io.StringIO()
        with redirect_stderr(err_gpu):
            self.assertEqual(w11.main(["--run-gpu", "--ckpt", "a.pt"]), 2)
        self.assertIn("FAIL S121_W11_PROBE code=BAD_ARGS", err_gpu.getvalue())
        proc_gpu = subprocess.run(
            [sys.executable, "-I", "-B", str(_HERE / "run_w11_live_loopcd_platosphere.py"), "--run-gpu"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc_gpu.returncode, 2)
        self.assertIn("FAIL S121_W11_PROBE code=BAD_ARGS", proc_gpu.stderr)
        self.assertNotIn("Traceback", proc_gpu.stderr)

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = w11.main(["--selftest-stdlib", "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["prereg_sha256"], w11.PINNED_PREREG_SHA256)
        self.assertEqual(len(hashlib.sha256(buf.getvalue().encode("utf-8")).hexdigest()), 64)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if res.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
