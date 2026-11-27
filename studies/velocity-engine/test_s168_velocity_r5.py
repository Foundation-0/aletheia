"""
`test_s168_velocity_r5.py`: Track S168 (EXP-Q56a) R1-R5 Adversarial, Zone-B,
Lean 4.36.0 Hardening, Preflight, Fast-Mutate, Velocity-Bench, and Zero-Shared-Code Verifier Suite.

Designed for 100.0% uncapped dual `aletheia mutate --max-mutants 0` kill rate across ALL 5
owned Python targets (`trust_core.py`, `preflight.py`, `fast_mutate.py`,
`s168_velocity_bench.py`, `verify_s168_velocity.py`).
Stdlib-only, zero bare asserts, zero floats on trust paths, 3x -I bit-identical.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
import errno
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
from typing import Any, Callable, Sequence

TRACK_DIR = Path(__file__).resolve().parent
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import fast_mutate as fm  # noqa: E402
import preflight as pf  # noqa: E402
import s168_velocity_bench as vb  # noqa: E402
import trust_core as tc  # noqa: E402
import verify_s168_velocity as ver  # noqa: E402

_SKIP_LIVE_LEAN = os.environ.get("S168_SKIP_LIVE_LEAN") == "1"


def _copy_writable(src: Path, dst: Path) -> None:
    """Copy a file preserving mtime and ensuring owner-writable `0o644` mode even from RO snapshots."""
    shutil.copy2(src, dst)
    os.chmod(dst, 0o644)


def _mock_lean_runner_ok(
    expected_theorems: Sequence[str],
    zero_set: frozenset[str],
    propext_set: frozenset[str],
    *,
    version_out: bytes = b"Lean (version 4.36.0, x86_64-unknown-linux-gnu, commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release)\n",
    build_rc: int = 0,
    build_out: bytes = b"Build completed successfully.\n",
    build_err: bytes = b"",
    axiom_rc: int = 0,
    axiom_err: bytes = b"",
    axiom_override: bytes | None = None,
    version_rc: int = 0,
) -> Any:
    def _runner(args: Sequence[str], cwd: Path, timeout: int) -> tuple[int, bytes, bytes]:
        if list(args) == ["lean", "--version"]:
            return version_rc, version_out, b""
        if list(args) == ["lake", "build"]:
            return build_rc, build_out, build_err
        if axiom_override is not None:
            return axiom_rc, axiom_override, axiom_err
        lines: list[str] = []
        for thm in expected_theorems:
            if thm in zero_set:
                lines.append(f"'{thm}' does not depend on any axioms")
            elif thm in propext_set:
                lines.append(f"'{thm}' depends on axioms: [propext]")
            else:
                lines.append(f"'{thm}' depends on axioms: [propext, Quot.sound]")
        return axiom_rc, ("\n".join(lines) + "\n").encode("utf-8"), axiom_err

    return _runner


def _minimal_lean_bundle(
    lean_code: str,
    *,
    toolchain: str = "leanprover/lean4:v4.36.0",
    lakefile_name: str = "lakefile.toml",
    lakefile_bytes: bytes | None = None,
    manifest_bytes: bytes | None = None,
) -> dict[str, bytes]:
    lf = lakefile_bytes if lakefile_bytes is not None else b'name = "Demo"\ndefaultTargets = ["Demo"]\n\n[[lean_lib]]\nname = "Demo"\n'
    man = manifest_bytes if manifest_bytes is not None else b'{"version":"1.1.0","packagesDir":".lake/packages","packages":[],"name":"Demo","lakeDir":".lake"}\n'
    return {
        "Demo.lean": lean_code.encode("utf-8"),
        "lean-toolchain": (toolchain + "\n").encode("utf-8"),
        lakefile_name: lf,
        "lake-manifest.json": man,
    }


def _make_sample_ab_results(bench_sha: str, engine_shas: dict[str, str]) -> dict[str, Any]:
    return {
        "schema": "s168.q56a.velocity_ab_results.v2",
        "bench_script_sha256": bench_sha,
        "engine_source_sha256": engine_shas,
        "cpu_only": True,
        "host_cpu_count": 8,
        "preflight_live": {
            "all_under_2000ms": True,
            "s161_snapshot": {
                "elapsed_ms": 200,
                "files_scanned": 10,
                "finding_count": 0,
                "lean_theorems_indexed": 124,
                "lean_unique_theorems": 62,
                "passed": True,
                "under_2000ms": True,
            },
            "s166_snapshot": {
                "elapsed_ms": 300,
                "files_scanned": 18,
                "finding_codes": ["MISSING_ALLOW_ABBREV_FALSE"],
                "finding_count": 2,
                "lean_theorems_indexed": 24,
                "lean_unique_theorems": 12,
                "under_2000ms": True,
            },
            "synthetic_caught_count": 5,
            "synthetic_fixtures": [
                {"fixture": "F1", "expected_code": "SCI_NOTATION_MISMATCH", "caught": True, "codes_detected": ["SCI_NOTATION_MISMATCH"], "elapsed_ms": 0},
                {"fixture": "F2", "expected_code": "GHOST_LEAN_THEOREM", "caught": True, "codes_detected": ["GHOST_LEAN_THEOREM"], "elapsed_ms": 0},
                {"fixture": "F3", "expected_code": "CERT_VERDICT_CONTRADICTION", "caught": True, "codes_detected": ["CERT_VERDICT_CONTRADICTION"], "elapsed_ms": 0},
                {"fixture": "F4", "expected_code": "STALE_RESULTS_JSON", "caught": True, "codes_detected": ["STALE_RESULTS_JSON"], "elapsed_ms": 0},
                {"fixture": "F5", "expected_code": "UNHASHED_RESULTS_JSON", "caught": True, "codes_detected": ["UNHASHED_RESULTS_JSON"], "elapsed_ms": 0},
            ],
            "synthetic_total_count": 5,
        },
        "mixed_parity_check": {
            "fast_arm_entrypoint": "python_api_allow_survivors",
            "parity_exact_100pct": True,
            "pass1_killed": 2,
            "pass1_survived": 3,
            "pass1_total": 5,
            "pass2_dedup_skipped": 2,
            "pass2_killed": 4,
            "pass2_new_sites": 4,
            "pass2_survived": 5,
            "pass2_total": 9,
            "pass1_mutant_set_sha256": "a" * 64,
            "pass2_mutant_set_sha256": "b" * 64,
        },
        "mutate_ab_benchmark": {
            "target_track": "track-s166-aletheia-cs27-cs29-hardening",
            "target_script": "aletheia/portfolio_dag.py",
            "target_script_sha256": ver.EXPECTED_AB_TARGET_SHA256,
            "test_cmd": "python3 -m unittest tests/test_cs27_cs29_hardening_r5.py",
            "pass2_guard": "_require",
            "trials": 3,
            "rng_seed": 168,
            "trial_arm_orders": [
                ["fast_w8", "fast_w1", "baseline_w8", "baseline_w1"],
                ["fast_w1", "baseline_w8", "baseline_w1", "fast_w8"],
                ["baseline_w8", "fast_w8", "baseline_w1", "fast_w1"],
            ],
            "cli_entrypoint_both_arms": True,
            "staged_from_chmod_aw_ro_copy": True,
            "mutated_in_isolated_writable_slots": True,
            "source_track_untouched": True,
            "pass1_mutant_set_sha256": "d" * 64,
            "pass2_mutant_set_sha256": "d" * 64,
            "baseline_aletheia_w1": {
                "elapsed_ms": 12000,
                "trial_elapsed_ms": [11900, 12000, 12100],
                "workers": 1,
                "pass1_total": 61,
                "pass1_killed": 61,
                "pass2_total": 61,
                "pass2_killed": 61,
                "mutant_subprocess_evals": 122,
                "control_subprocess_evals": 4,
                "total_subprocess_evals": 126,
            },
            "baseline_aletheia_w8": {
                "elapsed_ms": 4000,
                "trial_elapsed_ms": [3900, 4000, 4100],
                "workers": 8,
                "pass1_total": 61,
                "pass1_killed": 61,
                "pass2_total": 61,
                "pass2_killed": 61,
                "mutant_subprocess_evals": 122,
                "control_subprocess_evals": 4,
                "total_subprocess_evals": 126,
            },
            "fast_mutate_w1": {
                "elapsed_ms": 4000,
                "trial_elapsed_ms": [3950, 4000, 4050],
                "workers": 1,
                "failfast_injected": True,
                "pass1_total": 61,
                "pass1_killed": 61,
                "pass2_total": 61,
                "pass2_killed": 61,
                "pass2_dedup_skipped": 61,
                "mutant_subprocess_evals": 61,
                "control_subprocess_evals": 4,
                "total_subprocess_evals": 65,
                "bit_identical_mutant_set": True,
                "speedup_q": "3",
                "speedup_milli": 3000,
            },
            "fast_mutate_w8": {
                "elapsed_ms": 2000,
                "trial_elapsed_ms": [1950, 2000, 2050],
                "workers": 8,
                "failfast_injected": True,
                "pass1_total": 61,
                "pass1_killed": 61,
                "pass2_total": 61,
                "pass2_killed": 61,
                "pass2_dedup_skipped": 61,
                "mutant_subprocess_evals": 61,
                "control_subprocess_evals": 4,
                "total_subprocess_evals": 65,
                "bit_identical_mutant_set": True,
                "speedup_vs_base_w8_q": "2",
                "speedup_vs_base_w8_milli": 2000,
                "speedup_q": "6",
                "speedup_milli": 6000,
            },
            "mutant_eval_reduction_q": "2",
            "total_eval_reduction_q": "126/65",
            "parity_exact_100pct": True,
        },
    }


class TestS168VelocityR5(unittest.TestCase):
    def _assert_err(self, err_cls: type[Any], expected_code: str, fn: Callable[[], Any]) -> None:
        with self.assertRaises(err_cls) as cm:
            fn()
        self.assertEqual(cm.exception.code, expected_code)

    def test_01_trust_core_zone_b_json_and_cli(self) -> None:
        # strict_json_equal kills bool == int spoofs AND bool-key vs int-key spoofs (LOW-1)
        self.assertTrue(tc.strict_json_equal({"a": [1, True, None, "x"]}, {"a": [1, True, None, "x"]}))
        self.assertFalse(tc.strict_json_equal(True, 1))
        self.assertFalse(tc.strict_json_equal(False, 0))
        self.assertFalse(tc.strict_json_equal({"a": 1}, {"a": True}))
        self.assertFalse(tc.strict_json_equal({1: "x"}, {True: "x"}))
        self.assertFalse(tc.strict_json_equal({"a": 1}, {"a": 1, "b": 2}))
        self.assertFalse(tc.strict_json_equal({"a": 1}, {"b": 1}))
        self.assertFalse(tc.strict_json_equal([1, 2], [1]))
        self.assertFalse(tc.strict_json_equal([1, 2], [1, 3]))
        self.assertFalse(tc.strict_json_equal("a", "b"))

        self._assert_err(tc.TrustCoreError, "INVALID_BYTES_TYPE", lambda: tc.sha256_bytes("not-bytes"))  # type: ignore[arg-type]

        # canonical_json_bytes & exact depth/type/int-digit validation (LOW-1)
        raw_c = tc.canonical_json_bytes({"b": 1, "a": True})
        self.assertTrue(raw_c.endswith(b"\n"))
        self._assert_err(tc.TrustCoreError, "JSON_LONE_SURROGATE", lambda: tc.canonical_json_bytes({"x": "\ud800"}))
        self._assert_err(tc.TrustCoreError, "JSON_NON_STRING_KEY", lambda: tc.canonical_json_bytes({1: "k"}))  # type: ignore[dict-item]
        self._assert_err(tc.TrustCoreError, "JSON_UNSUPPORTED_TYPE", lambda: tc.canonical_json_bytes({"s": {1, 2}}))
        self._assert_err(tc.TrustCoreError, "JSON_FLOAT_FORBIDDEN", lambda: tc.canonical_json_bytes({"f": json.loads("1.5")}, allow_float=False))
        self.assertIn(b"1.5", tc.canonical_json_bytes({"f": json.loads("1.5")}, allow_float=True))
        self._assert_err(tc.TrustCoreError, "JSON_FLOAT_NOT_FINITE", lambda: tc.canonical_json_bytes({"f": json.loads("1e999")}, allow_float=True))
        # Exact int-digit bound in canonical_json_bytes: 10**MAX - 1 passes, 10**MAX fails (and >4300 digits never raises raw ValueError!)
        self.assertTrue(len(tc.canonical_json_bytes({"n": (10 ** tc.MAX_JSON_INT_DIGITS) - 1})) > 0)
        self._assert_err(tc.TrustCoreError, "JSON_INT_TOO_LONG", lambda: tc.canonical_json_bytes({"n": 10 ** tc.MAX_JSON_INT_DIGITS}))
        self._assert_err(tc.TrustCoreError, "JSON_INT_TOO_LONG", lambda: tc.canonical_json_bytes({"n": 10 ** 5000}))

        # Exact depth == MAX_JSON_DEPTH passes for BOTH list and dict; MAX_JSON_DEPTH + 1 fails
        deep_list: Any = 1
        for _ in range(tc.MAX_JSON_DEPTH):
            deep_list = [deep_list]
        self.assertTrue(len(tc.canonical_json_bytes(deep_list)) > 0)
        self._assert_err(tc.TrustCoreError, "JSON_DEPTH_EXCEEDED", lambda: tc.canonical_json_bytes([deep_list]))
        deep_dict: Any = 1
        for _ in range(tc.MAX_JSON_DEPTH):
            deep_dict = {"k": deep_dict}
        self.assertTrue(len(tc.canonical_json_bytes(deep_dict)) > 0)
        self._assert_err(tc.TrustCoreError, "JSON_DEPTH_EXCEEDED", lambda: tc.canonical_json_bytes({"k": deep_dict}))

        # parse_strict_json_bytes exact code & boundary matrix including decimal.InvalidOperation (MED-8)
        self.assertEqual(tc.parse_strict_json_bytes(b'{"k": 1}\n'), {"k": 1})
        self.assertEqual(tc.parse_strict_json_bytes(b'{"k": -1}\n'), {"k": -1})
        self.assertEqual(tc.parse_strict_json_bytes(b'{"k": 1}', require_trailing_lf=False), {"k": 1})
        self.assertEqual(tc.parse_strict_json_bytes(b'{"f": 0.0}\n', allow_float=True)["f"], 0)
        self.assertEqual(tc.parse_strict_json_bytes(b'{"f": 1.25}\n', allow_float=True)["f"], json.loads("1.25"))
        for bad_raw, kw, exp_code in [
            ("not-bytes", {}, "INVALID_BYTES_TYPE"),
            (b"", {}, "EMPTY_JSON"),
            (b"   \n", {}, "EMPTY_JSON"),
            (b"\xef\xbb\xbf{}\n", {}, "JSON_BOM_FORBIDDEN"),
            (b"{}\r\n", {}, "JSON_CRLF_FORBIDDEN"),
            (b"{}", {"require_trailing_lf": True}, "JSON_NO_TRAILING_LF"),
            (b"\xff\xfe\n", {}, "INVALID_UTF8"),
            (b'{"a": 1, "a": 2}\n', {}, "JSON_DUPLICATE_KEY"),
            (b'{"a": NaN}\n', {}, "JSON_CONSTANT_FORBIDDEN"),
            (b'{"a": Infinity}\n', {}, "JSON_CONSTANT_FORBIDDEN"),
            (b'{"a": 1.5}\n', {"allow_float": False}, "JSON_FLOAT_FORBIDDEN"),
            (b'{"a": 1e999}\n', {"allow_float": True}, "JSON_FLOAT_NOT_FINITE"),
            (b'{"a": 1e-999}\n', {"allow_float": True}, "JSON_FLOAT_UNDERFLOW"),
            (b'{"x": 1e99999999999999999999999999}\n', {"allow_float": True}, "JSON_SYNTAX_ERROR"),
            (b'{"a": ' + (b"9" * (tc.MAX_JSON_INT_DIGITS + 1)) + b'}\n', {}, "JSON_INT_TOO_LONG"),
            (b'{"a": ' + (b"9" * 5000) + b'}\n', {}, "JSON_INT_TOO_LONG"),
            (b'{bad}\n', {}, "JSON_SYNTAX_ERROR"),
        ]:
            self._assert_err(tc.TrustCoreError, exp_code, lambda br=bad_raw, k=kw: tc.parse_strict_json_bytes(br, **k))  # type: ignore[arg-type]
        ok_int = b'{"n": ' + (b"9" * tc.MAX_JSON_INT_DIGITS) + b'}\n'
        self.assertEqual(len(str(tc.parse_strict_json_bytes(ok_int)["n"])), tc.MAX_JSON_INT_DIGITS)

        # Zone-B read/write: O_NOFOLLOW, .., symlink, hardlink, FIFO, max_bytes, long filename & 0o600 mode preservation (LOW-1)
        with tempfile.TemporaryDirectory(prefix="s168_tc_") as tmp_s:
            tmp = Path(tmp_s)
            real_sub = tmp / "real"
            real_sub.mkdir()
            victim = tmp / "victim.json"
            victim.write_bytes(b'{"keep": true}\n')
            sym_dir = tmp / "symdir"
            os.symlink(real_sub, sym_dir)
            sym_leaf = real_sub / "sym_leaf.json"
            os.symlink(victim, sym_leaf)
            hardlink = real_sub / "hard.json"
            os.link(victim, hardlink)
            fifo_p = real_sub / "pipe.fifo"
            os.mkfifo(fifo_p)

            old_cwd = os.getcwd()
            os.chdir(real_sub)
            try:
                rel_bytes = tc.atomic_write_json_nofollow("rel_ok.json", {"rel": 1})
                self.assertEqual(tc.strict_read_bytes_nofollow("rel_ok.json", max_bytes=len(rel_bytes)), rel_bytes)
            finally:
                os.chdir(old_cwd)

            good_p = real_sub / "ok.json"
            written = tc.atomic_write_json_nofollow(good_p, {"ok": 1, "flag": True})
            self.assertEqual(tc.strict_read_bytes_nofollow(good_p, max_bytes=len(written)), written)
            self.assertEqual(tc.strict_load_json_nofollow(good_p), {"flag": True, "ok": 1})
            # Preserve 0o600 mode on overwrite (LOW-1)
            os.chmod(good_p, 0o600)
            tc.atomic_write_json_nofollow(good_p, {"ok": 2})
            self.assertEqual(stat.S_IMODE(os.lstat(good_p).st_mode), 0o600)
            # 225-char filename must NOT fail with ENAMETOOLONG (LOW-1)
            long_p = real_sub / ("a" * 220 + ".json")
            tc.atomic_write_json_nofollow(long_p, {"long": True})
            self.assertEqual(tc.strict_load_json_nofollow(long_p), {"long": True})

            good_len = len(tc.strict_read_bytes_nofollow(good_p))
            self._assert_err(tc.TrustCoreError, "FILE_TOO_LARGE", lambda: tc.strict_read_bytes_nofollow(good_p, max_bytes=good_len - 1))
            self._assert_err(tc.TrustCoreError, "INVALID_MAX_BYTES", lambda: tc.strict_read_bytes_nofollow(good_p, max_bytes=0))
            self._assert_err(tc.TrustCoreError, "INVALID_MAX_BYTES", lambda: tc.strict_read_bytes_nofollow(good_p, max_bytes=True))  # type: ignore[arg-type]

            for bad_path, r_code, w_code in [
                (123, "INVALID_PATH_TYPE", "INVALID_PATH_TYPE"),
                ("", "EMPTY_PATH", "EMPTY_PATH"),
                ("bad\x00name", "NUL_IN_PATH", "NUL_IN_PATH"),
                ("/", "PATH_NO_LEAF", "PATH_NO_LEAF"),
                (".", "PATH_NO_LEAF", "PATH_NO_LEAF"),
                (sym_dir / ".." / "victim.json", "DOTDOT_PATH", "DOTDOT_PATH"),
                (sym_dir / "escape.json", "PARENT_OPEN_FAILED", "PARENT_OPEN_FAILED"),
                (sym_leaf, "READ_OPEN_FAILED", "WRITE_TARGET_NOT_REG"),
                (hardlink, "HARDLINK_FORBIDDEN", "WRITE_TARGET_HARDLINK"),
                (fifo_p, "NOT_REGULAR_FILE", "WRITE_TARGET_NOT_REG"),
                (real_sub, "NOT_REGULAR_FILE", "WRITE_TARGET_NOT_REG"),
            ]:
                self._assert_err(tc.TrustCoreError, r_code, lambda bp=bad_path: tc.strict_read_bytes_nofollow(bp))  # type: ignore[arg-type]
                self._assert_err(tc.TrustCoreError, w_code, lambda bp=bad_path: tc.atomic_write_json_nofollow(bp, {"pwn": True}))  # type: ignore[arg-type]
            self.assertEqual(victim.read_bytes(), b'{"keep": true}\n')
            self._assert_err(tc.TrustCoreError, "READ_OPEN_FAILED", lambda: tc.strict_read_bytes_nofollow(real_sub / "missing.json"))

            with mock.patch("os.lstat", side_effect=OSError(errno.EACCES, "denied")):
                self._assert_err(tc.TrustCoreError, "WRITE_LSTAT_FAILED", lambda: tc.atomic_write_json_nofollow(good_p, {"x": 1}))
            with mock.patch("os.write", side_effect=[0, OSError(errno.EIO, "stop")]):
                self._assert_err(tc.TrustCoreError, "WRITE_SHORT_ZERO", lambda: tc.atomic_write_json_nofollow(real_sub / "zero.json", {"x": 1}))
            real_fsync = os.fsync
            fsync_calls = [0]

            def _fsync_dir_err(err_no: int) -> Any:
                def _inner(fd_i: int) -> None:
                    fsync_calls[0] += 1
                    if fsync_calls[0] == 2:
                        raise OSError(err_no, "fsync")
                    real_fsync(fd_i)
                return _inner

            fsync_calls[0] = 0
            with mock.patch("os.fsync", side_effect=_fsync_dir_err(errno.EINVAL)):
                tc.atomic_write_json_nofollow(real_sub / "einval.json", {"ok": 1})
            fsync_calls[0] = 0
            with mock.patch("os.fsync", side_effect=_fsync_dir_err(errno.EBADF)):
                self._assert_err(tc.TrustCoreError, "DIR_FSYNC_FAILED", lambda: tc.atomic_write_json_nofollow(real_sub / "ebadf.json", {"ok": 1}))

            # UID-0 safe RO write refusal test (LOW-6)
            if os.geteuid() == 0:
                with mock.patch("os.open", side_effect=OSError(errno.EACCES, "ro")):
                    self._assert_err(tc.TrustCoreError, "PARENT_OPEN_FAILED", lambda: tc.atomic_write_json_nofollow(real_sub / "ro.json", {"x": 1}))
            else:
                ro_sub = tmp / "ro_dir"
                ro_sub.mkdir()
                os.chmod(ro_sub, 0o555)
                try:
                    self._assert_err(tc.TrustCoreError, "ATOMIC_WRITE_IO_ERROR", lambda: tc.atomic_write_json_nofollow(ro_sub / "out.json", {"x": 1}))
                finally:
                    os.chmod(ro_sub, 0o755)

        # Fail-closed CLI incl. --help JSON output, plain ArgumentParser rejection, SystemExit catch (LOW-2)
        def _mk_p() -> argparse.ArgumentParser:
            p = tc.make_strict_parser("demo", "demo desc")
            p.add_argument("--check", action="store_true")
            return p

        out_b, err_b = io.StringIO(), io.StringIO()
        with redirect_stdout(out_b), redirect_stderr(err_b):
            rc_ok = tc.run_fail_closed_cli(lambda args: {"checked": args.check}, parser_builder=_mk_p, argv=["--check"])
            rc_help = tc.run_fail_closed_cli(lambda args: {"checked": args.check}, parser_builder=_mk_p, argv=["--help"])
            rc_noarg = tc.run_fail_closed_cli(lambda: {"ok": True})
            rc_abbr = tc.run_fail_closed_cli(lambda args: {"ok": True}, parser_builder=_mk_p, argv=["--ch"])
            rc_badval = tc.run_fail_closed_cli(lambda args: {"ok": True}, parser_builder=_mk_p, argv=["--check=1"])
            rc_tc_err = tc.run_fail_closed_cli(lambda: (_ for _ in ()).throw(tc.TrustCoreError("BOOM", "bad")))
            rc_sysexit = tc.run_fail_closed_cli(lambda: (_ for _ in ()).throw(SystemExit(3)))
            rc_uni_err = tc.run_fail_closed_cli(lambda: (_ for _ in ()).throw(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")))
            rc_not_dict = tc.run_fail_closed_cli(lambda: [1, 2])  # type: ignore[arg-type,return-value]
            rc_plain_parser = tc.run_fail_closed_cli(
                lambda args: {"ok": True},
                parser_builder=lambda: argparse.ArgumentParser(allow_abbrev=False),
                argv=[],
            )
        self.assertEqual(rc_ok, 0)
        self.assertEqual(rc_help, 0)
        self.assertEqual(rc_noarg, 0)
        stdout_lines = out_b.getvalue().strip().splitlines()
        self.assertEqual(json.loads(stdout_lines[1])["status"], "HELP")
        for rc_bad in (rc_abbr, rc_badval, rc_tc_err, rc_sysexit, rc_uni_err, rc_not_dict, rc_plain_parser):
            self.assertEqual(rc_bad, 2)
        for err_line in err_b.getvalue().strip().splitlines():
            self.assertEqual(json.loads(err_line)["status"], "ERROR")

    def test_02_trust_core_provenance_and_lean_hardening(self) -> None:
        # bind_empirical_artifact fail-closed defaults + extra_source_paths + verified results_obj (MED-1)
        with tempfile.TemporaryDirectory(prefix="s168_bind_") as tmp_s:
            tmp = Path(tmp_s)
            bench = tmp / "bench.py"
            eng = tmp / "engine.py"
            res = tmp / "results.json"
            bench.write_bytes(b"def run():\n    return 1\n")
            eng.write_bytes(b"def eng():\n    return 2\n")
            b_sha = tc.sha256_bytes(bench.read_bytes())
            e_sha = tc.sha256_bytes(eng.read_bytes())
            tc.atomic_write_json_nofollow(res, {"bench_script_sha256": b_sha, "engine_source_sha256": {"engine.py": e_sha}, "val": 42})
            os.utime(bench, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
            os.utime(eng, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            r_sha = tc.sha256_bytes(res.read_bytes())
            bound = tc.bind_empirical_artifact(
                res, bench, expected_bench_sha256=b_sha, expected_results_sha256=r_sha,
                extra_source_paths={"engine.py": eng},
            )
            self.assertTrue(bound["results_postdates_bench"])
            self.assertTrue(bound["embedded_bench_sha_checked"])
            self.assertEqual(bound["results_obj"]["val"], 42)
            self.assertEqual(bound["engine_source_sha256"]["engine.py"], e_sha)

            # Default rejects float & missing bench_script_sha256 & non-dict root & stale/mismatched engine
            tc.atomic_write_json_nofollow(res, [1, 2])
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "RESULTS_NOT_DICT", lambda: tc.bind_empirical_artifact(res, bench))
            res.write_bytes(b'{"bench_script_sha256": "' + b_sha.encode() + b'", "f": 1.5}\n')
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "JSON_FLOAT_FORBIDDEN", lambda: tc.bind_empirical_artifact(res, bench))
            tc.atomic_write_json_nofollow(res, {"val": 1})
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "MISSING_EMBEDDED_BENCH_SHA", lambda: tc.bind_empirical_artifact(res, bench))
            tc.atomic_write_json_nofollow(res, {"bench_script_sha256": b_sha})
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "MISSING_EMBEDDED_ENGINE_SHAS", lambda: tc.bind_empirical_artifact(res, bench, extra_source_paths={"engine.py": eng}))
            tc.atomic_write_json_nofollow(res, {"bench_script_sha256": b_sha, "engine_source_sha256": {"engine.py": "0" * 64}})
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "EMBEDDED_ENGINE_SHA_MISMATCH", lambda: tc.bind_empirical_artifact(res, bench, extra_source_paths={"engine.py": eng}))
            tc.atomic_write_json_nofollow(res, {"bench_script_sha256": b_sha, "engine_source_sha256": {"engine.py": e_sha, "evil_extra.py": "0" * 64}})
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "EMBEDDED_ENGINE_KEYS_MISMATCH", lambda: tc.bind_empirical_artifact(res, bench, extra_source_paths={"engine.py": eng}))
            tc.atomic_write_json_nofollow(res, {"bench_script_sha256": b_sha, "engine_source_sha256": {"engine.py": e_sha}})
            os.utime(eng, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "STALE_EMPIRICAL_RESULTS", lambda: tc.bind_empirical_artifact(res, bench, extra_source_paths={"engine.py": eng}))

            os.utime(res, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
            self._assert_err(tc.TrustCoreError, "STALE_EMPIRICAL_RESULTS", lambda: tc.bind_empirical_artifact(res, bench))
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "BENCH_SHA_MISMATCH", lambda: tc.bind_empirical_artifact(res, bench, expected_bench_sha256="0" * 64))
            self._assert_err(tc.TrustCoreError, "RESULTS_SHA_MISMATCH", lambda: tc.bind_empirical_artifact(res, bench, expected_results_sha256="0" * 64))
            tc.atomic_write_json_nofollow(res, {"bench_script_sha256": "0" * 64})
            os.utime(res, ns=(1_700_000_010_000_000_000, 1_700_000_010_000_000_000))
            self._assert_err(tc.TrustCoreError, "EMBEDDED_BENCH_SHA_MISMATCH", lambda: tc.bind_empirical_artifact(res, bench))

        # Lean 4.36.0 static hardening: clean + `«»«»` + unnamed `section ... end` + nested `namespace A.B ... end B` (LOW-1) + multiline theorem extraction
        clean_lean = (
            "/- outer /- nested comment -/ comment -/\n"
            "-- line comment sorry\n"
            "namespace Demo.Sub\n"
            "section\n"
            "def msg : String := \"/- not a comment\" ++ r#\"-- raw\"#\n"
            "end\n"
            "def dot1 : String := obj.s!\"{\"\n"
            "def dot2 : String := obj.throwErrorAt x \"{\"\n"
            "def plain_m (s : String) : Nat := s.length\n"
            "def ok_m : Nat := m! \"plain_no_braces\"\n"
            "def ch : Char := '\\x41'\n"
            "def empty_g := «»«»\n"
            "theorem\n  t_sub : 1 + 1 = 2 := by decide\n"
            "end Sub\n"
            "theorem t_ok : 1 = 1 := rfl\n"
            "end Demo\n"
        )
        res_ok = tc.audit_lean4_source_static(clean_lean)
        self.assertTrue(res_ok["clean"], res_ok["findings"])
        self.assertEqual(tc.extract_lean4_theorems(clean_lean), ["Demo.Sub.t_sub", "Demo.t_ok"])
        self.assertEqual(
            tc.extract_lean4_theorems("namespace A.B\ntheorem t1 : 1 = 1 := rfl\nend A.B\ntheorem t2 : 1 = 1 := rfl\n"),
            ["A.B.t1", "t2"],
        )
        self._assert_err(tc.TrustCoreError, "INVALID_SOURCE_TYPE", lambda: tc.strip_lean4_comments_and_literals(123))  # type: ignore[arg-type]

        # HIGH-1 live bypass repros (`bad! "{"`, `throwError "{"` + `macro_rules`, `m! "{"` + `notation`/`skipKernelTC`, `throwErrorAt 1 "{"`, `by dbg_trace "{"`) + MED-2 (`by open Nat in ... stop`)
        high1_bypass = (
            'def bad! (s : String) : Nat := s.length\n'
            'def f : Nat := bad! "{"\n'
            'set_option debug.skipKernelTC true\n'
            'axiom evil : False\n'
            'def g : String := "}"\n'
            'theorem t : False := evil\n'
        )
        st_h1 = tc.audit_lean4_source_static(high1_bypass)
        self.assertFalse(st_h1["clean"])
        h1_codes = {f["code"] for f in st_h1["findings"]}
        self.assertIn("LEAN4_AMBIG_INTERP_ESCAPE", h1_codes)
        self.assertIn("LEAN4_DEBUG_ESCAPE", h1_codes)
        self.assertIn("LEAN4_AXIOM", h1_codes)

        exploit_throwerror = (
            'namespace Demo\n'
            'def throwError (s : String) : Nat := s.length\n'
            'def f : Nat := throwError "{"\n'
            'macro_rules | `($_ < $_) => `(True)\n'
            'def g : String := "}"\n'
            'theorem t1 : 1 < 0 := trivial\n'
            'end Demo\n'
        )
        exploit_mbang = (
            'namespace Demo\n'
            'def m! (s : String) : Nat := s.length\n'
            'def f : Nat := m! "{"\n'
            'set_option debug.skipKernelTC true\n'
            'notation "impossible_false" => True\n'
            'def g : String := "}"\n'
            'theorem t1 : impossible_false := trivial\n'
            'end Demo\n'
        )
        exploit_open_stop = (
            'namespace Demo\n'
            'theorem t1 : 1 = 1 := by\n'
            '  open Nat in\n'
            '  rfl\n'
            '  stop\n'
            '  exact rfl\n'
            'end Demo\n'
        )

        st_te = tc.audit_lean4_source_static(exploit_throwerror)
        self.assertFalse(st_te["clean"])
        self.assertIn("LEAN4_AMBIG_INTERP_ESCAPE", {f["code"] for f in st_te["findings"]})
        self.assertIn("LEAN4_SYNTAX_MACRO_ESCAPE", {f["code"] for f in st_te["findings"]})

        st_mb = tc.audit_lean4_source_static(exploit_mbang)
        self.assertFalse(st_mb["clean"])
        self.assertIn("LEAN4_AMBIG_INTERP_ESCAPE", {f["code"] for f in st_mb["findings"]})
        self.assertIn("LEAN4_DEBUG_ESCAPE", {f["code"] for f in st_mb["findings"]})
        self.assertIn("LEAN4_SYNTAX_MACRO_ESCAPE", {f["code"] for f in st_mb["findings"]})

        st_os = tc.audit_lean4_source_static(exploit_open_stop)
        self.assertFalse(st_os["clean"])
        self.assertIn("LEAN4_STOP_TACTIC", {f["code"] for f in st_os["findings"]})

        # Delta-5 LOW-3: trust_core & verifier lexer arg-tracking parity on projections, `#[...]`, and `⟨...⟩` args
        for low3_arg in ("p.1.2", "#[1]", "⟨1, 2⟩", "x.1.foo"):
            low3_src = f'def g := throwErrorAt {low3_arg} "{{"\n'
            self.assertIn("LEAN4_AMBIG_INTERP_ESCAPE", {f["code"] for f in tc.audit_lean4_source_static(low3_src)["findings"]}, low3_arg)
            self._assert_err(ver.VerifierError, "LEAN_AMBIG_INTERP", lambda src=low3_src: ver.audit_lean_static(src))
            low3_ok = f'def g := throwErrorAt {low3_arg} "x"\n'
            self.assertTrue(tc.audit_lean4_source_static(low3_ok)["clean"], low3_arg)
            self.assertEqual(ver.audit_lean_static(low3_ok), [])

        for bad_src, expected_code in [
            ('def x := !s!"{ "/-" }"\ntheorem p : False := by sorry\n', "LEAN4_SORRY"),
            ('def m! (s : String) : Nat := s.length\ndef f : Nat := m! "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def m! (s : String) : Nat := s.length\ndef f : Nat := m! "\\{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def bad! (s : String) : Nat := s.length\ndef f : Nat := bad! "}"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def throwErrorAt (n : Nat) (s : String) : Nat := s.length + n\ndef f : Nat := throwErrorAt 1 "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt s!"a" "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt s!"{1 + 2}" "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt (s!"{1 + 2}") "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt r#"a"# "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ("def throwErrorAt (a : Char) (b : String) : Nat := a.toNat + b.length\ndef f : Nat := throwErrorAt 'a' \"{\"\n", "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt "a" "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def logInfoAt (n : Nat) (s : String) : Nat := n + s.length\ndef f : Nat := logInfoAt 1 "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def logWarningAt (n : Nat) (s : String) : Nat := n + s.length\ndef f : Nat := logWarningAt 1 "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def logErrorAt (n : Nat) (s : String) : Nat := n + s.length\ndef f : Nat := logErrorAt 1 "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('def logAt (n : Nat) (s : String) : Nat := n + s.length\ndef f : Nat := logAt 1 "{"\n', "LEAN4_AMBIG_INTERP_ESCAPE"),
            ('theorem t1 : 1 = 1 := by dbg_trace "{"; rfl\nset_option debug.skipKernelTC true\naxiom e : False\ndef g := "}"\n', "LEAN4_DEBUG_ESCAPE"),
            ('theorem p : False := by stop\n', "LEAN4_STOP_TACTIC"),
            ('theorem p : False := by\n  rfl\n  stop\n', "LEAN4_STOP_TACTIC"),
            ('theorem p : 1 = 1 := by\n  open Nat in\n  rfl\n  stop\n  exact rfl\n', "LEAN4_STOP_TACTIC"),
            ('def x := Lean.Elab.Command.elabCommand\n', "LEAN4_META_ESCAPE"),
            ('def x := Lean.Meta.mkFreshExprMVar\n', "LEAN4_META_ESCAPE"),
            ('macro "foo" : term => `(1)\n', "LEAN4_SYNTAX_MACRO_ESCAPE"),
            ('elab "foo" : term => pure default\n', "LEAN4_SYNTAX_MACRO_ESCAPE"),
            ('syntax "foo" : term\n', "LEAN4_SYNTAX_MACRO_ESCAPE"),
            ('notation "foo" => 1\n', "LEAN4_SYNTAX_MACRO_ESCAPE"),
            ('theorem p : False := _root_.«sorryAx» False true\n', "LEAN4_SORRY_AX"),
            ('theorem p : 1 = 1 := by decide +native\n', "LEAN4_DECIDE_NATIVE"),
            ('theorem p : 1 = 1 := by decide (native := true)\n', "LEAN4_DECIDE_NATIVE"),
            ('theorem p : 1 = 1 := by decide (native := (true))\n', "LEAN4_DECIDE_NATIVE"),
            ('theorem p : 1 = 1 := by decide (config := { native := true })\n', "LEAN4_DECIDE_NATIVE"),
            ('@[\nextern "c_fn"\n]\ndef f : Nat := 0\n', "LEAN4_ATTR_ESCAPE"),
            ('set_option debug.byAsSorry true\n', "LEAN4_DEBUG_ESCAPE"),
            ('set_option debug.proofAsSorry true\n', "LEAN4_DEBUG_ESCAPE"),
            ('set_option debug.terminalTacticsAsSorry true\n', "LEAN4_DEBUG_ESCAPE"),
            ('variable (h : False)\ninclude h\ntheorem p : False := h\n', "LEAN4_VARIABLE_INCLUDE"),
            ('private partial def loop : Nat := loop\n', "LEAN4_PARTIAL_DECL"),
            ('opaque bad_const : Nat\n', "LEAN4_OPAQUE_DECL"),
            ('instance (priority := high) : LT Int := sorry\n', "LEAN4_INSTANCE_OVERRIDE"),
            ('infixl:65 " ++ " => Nat.add\n', "LEAN4_SYNTAX_MACRO_ESCAPE"),
            ('import Mathlib.Data.Nat.Basic\n', "LEAN4_NON_INIT_IMPORT"),
            ('import Std.Tactic.BVDecide\n', "LEAN4_FORBIDDEN_IMPORT"),
            ('public import Init\n', "LEAN4_PUBLIC_IMPORT"),
            ('def s := "unterminated\n', "LEAN4_UNTERMINATED_STRING"),
            ('/- unterminated comment\n', "LEAN4_UNTERMINATED_COMMENT"),
            ('def «unterminated := 1\n', "LEAN4_UNTERMINATED_IDENT"),
            ('def t := throwErrorAt stx "{ "/-" }"\ntheorem p : False := by sorry\n', "LEAN4_SORRY"),
            ('def t := dbg_trace "{ "/-" }"\ntheorem p : False := by sorry\n', "LEAN4_SORRY"),
            ('def t := Macro.trace[foo] "{ "/-" }"\ntheorem p : False := by sorry\n', "LEAN4_SORRY"),
        ]:
            st = tc.audit_lean4_source_static(bad_src)
            self.assertFalse(st["clean"], f"failed to catch {expected_code} on {bad_src!r}")
            self.assertIn(expected_code, {f["code"] for f in st["findings"]})

        # Strict declarative lakefile.toml allowlist + rejection of lakefile.lean / ../evil / .lake/x / globs (HIGH-3)
        self.assertEqual(tc.audit_lakefile_bytes("lakefile.toml", b'name = "Demo"\nversion = "0.1.0"\ndefaultTargets = ["Demo"]\n[[lean_lib]]\nname = "Demo"\nsrcDir = "."\nroots = ["Demo"]\nglobs = ["Demo.+"]\n'), [])
        for bad_lf_name, bad_lf, exp_c in [
            ("lakefile.lean", b'@[default_target] target pwn : Unit := do IO.FS.writeFile "PWN" "x"; return .nil\n', "LAKEFILE_LEAN_FORBIDDEN"),
            ("lakefile.toml", b'name = "Demo"\n[leanOptions]\n"debug.byAsSorry" = true\n', "LAKEFILE_UNSAFE_KEY"),
            ("lakefile.toml", b'name = "Demo"\n"debug.byAsSorry" = true\n', "LAKEFILE_UNSAFE_TOKEN"),
            ("lakefile.toml", b'name = "Demo"\nmoreLeanArgs = ["-Ddebug.byAsSorry=true"]\n', "LAKEFILE_UNSAFE_KEY"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nsrcDir = ""\n', "LAKEFILE_UNSAFE_PATH"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nsrcDir = "a\\u0000b"\n', "LAKEFILE_UNSAFE_PATH"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nsrcDir = "/abs"\n', "LAKEFILE_UNSAFE_PATH"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nsrcDir = "../evil"\n', "LAKEFILE_UNSAFE_PATH"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nsrcDir = ".lake/x"\n', "LAKEFILE_UNSAFE_PATH"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nsrcDir = "venv"\n', "LAKEFILE_UNSAFE_PATH"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "bad/name"\n', "LAKEFILE_UNSAFE_ROOT"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nroots = ["venv.Evil"]\n', "LAKEFILE_UNSAFE_ROOT"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nroots = ["debug.skipKernelTC"]\n', "LAKEFILE_UNSAFE_TOKEN"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nglobs = ["bad/glob"]\n', "LAKEFILE_UNSAFE_GLOB"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nglobs = ["venv.*"]\n', "LAKEFILE_UNSAFE_GLOB"),
            ("lakefile.toml", b'name = "Demo"\n[[lean_lib]]\nname = "Demo"\nmoreLeanArgs = []\n', "LAKEFILE_UNSAFE_KEY"),
            ("lakefile.toml", b'name = "bad name!"\n', "LAKEFILE_INVALID_SCHEMA"),
            ("lakefile.toml", b'version = "not-semver"\n', "LAKEFILE_INVALID_SCHEMA"),
            ("lakefile.toml", b'defaultTargets = ["bad/target"]\n', "LAKEFILE_INVALID_SCHEMA"),
            ("lakefile.toml", b'lean_lib = 123\n', "LAKEFILE_INVALID_SCHEMA"),
            ("lakefile.toml", b'lean_lib = [123]\n', "LAKEFILE_INVALID_SCHEMA"),
        ]:
            lf_f = tc.audit_lakefile_bytes(bad_lf_name, bad_lf)
            self.assertIn(exp_c, {f["code"] for f in lf_f}, f"{bad_lf_name} {bad_lf!r} -> {lf_f}")
        self._assert_err(tc.TrustCoreError, "LAKEFILE_CRLF", lambda: tc.audit_lakefile_bytes("lakefile.toml", b"bad\r\n"))
        self._assert_err(tc.TrustCoreError, "INVALID_UTF8", lambda: tc.audit_lakefile_bytes("lakefile.toml", b"\xff\xfe"))
        self._assert_err(tc.TrustCoreError, "LAKEFILE_TOML_SYNTAX", lambda: tc.audit_lakefile_bytes("lakefile.toml", b"[[broken"))

        # _default_lean_exec & resolve_verified_lean_bins refusal & PATH shim immunity (HIGH-3)
        self._assert_err(tc.TrustCoreError, "INVALID_TOOLCHAIN_SPEC", lambda: tc.resolve_verified_lean_bins("bad_tc"))
        with tempfile.TemporaryDirectory(prefix="s168_shim_") as shim_s:
            shim_d = Path(shim_s)
            fake_lean = shim_d / "lean"
            fake_lean.write_text("#!/bin/sh\necho 'Lean (version 4.36.0, fake)'\n", encoding="utf-8")
            os.chmod(fake_lean, 0o755)
            nonexec_elf = shim_d / "nonexec_elf"
            nonexec_elf.write_bytes(b"\x7fELF\x00\x00\x00\x00")
            os.chmod(nonexec_elf, 0o644)
            self._assert_err(tc.TrustCoreError, "LEAN_TOOL_UNTRUSTED", lambda: tc._verify_elf_executable(fake_lean, "lean"))
            self._assert_err(tc.TrustCoreError, "LEAN_TOOL_UNTRUSTED", lambda: tc._verify_elf_executable(nonexec_elf, "lean"))
            self._assert_err(tc.TrustCoreError, "LEAN_TOOL_NOT_FOUND", lambda: tc._verify_elf_executable(shim_d / "missing", "lean"))
            sym_bin = shim_d / "sym_lean"
            os.symlink(fake_lean, sym_bin)
            self._assert_err(tc.TrustCoreError, "LEAN_TOOL_UNTRUSTED", lambda: tc._verify_elf_executable(sym_bin, "lean"))

            # Real live Lean 4.36.0 execution via trust_core WITH a malicious PATH shim prepended!
            # Also live-reproduce Delta-2 HIGH-1 (`throwError "{"` + `macro_rules`, `m! "{"` + `notation`/`skipKernelTC`)
            # and MED-2 (`by open Nat in ... stop`) directly against Lean 4.36.0 and prove all are rejected!
            if not _SKIP_LIVE_LEAN:
                lean_bin, _, _ = tc.resolve_verified_lean_bins()
                exploit_med2_s = 'namespace Demo\ndef throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt s!"a" "{"\ntheorem t1 : 1 = 1 := rfl\nend Demo\n'
                exploit_med2_sexpr = 'namespace Demo\ndef throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt s!"{1 + 2}" "{"\ntheorem t1 : 1 = 1 := rfl\nend Demo\n'
                exploit_med2_raw = 'namespace Demo\ndef throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt r#"a"# "{"\ntheorem t1 : 1 = 1 := rfl\nend Demo\n'
                exploit_med2_char = "namespace Demo\ndef throwErrorAt (a : Char) (b : String) : Nat := a.toNat + b.length\ndef f : Nat := throwErrorAt 'a' \"{\"\ntheorem t1 : 1 = 1 := rfl\nend Demo\n"
                exploit_med2_logat = 'namespace Demo\ndef logInfoAt (n : Nat) (b : String) : Nat := n + b.length\ndef f : Nat := logInfoAt 1 "{"\ntheorem t1 : 1 = 1 := rfl\nend Demo\n'
                for exp_name, exp_src in (
                    ("throwError_macro", exploit_throwerror),
                    ("mbang_notation_skip", exploit_mbang),
                    ("open_in_stop", exploit_open_stop),
                    ("med2_throwErrorAt_s", exploit_med2_s),
                    ("med2_throwErrorAt_sexpr", exploit_med2_sexpr),
                    ("med2_throwErrorAt_raw", exploit_med2_raw),
                    ("med2_throwErrorAt_char", exploit_med2_char),
                    ("med2_logInfoAt", exploit_med2_logat),
                ):
                    exp_file = shim_d / f"{exp_name}.lean"
                    exp_file.write_text(exp_src, encoding="utf-8", newline="\n")
                    raw_p = subprocess.run([os.fspath(lean_bin), os.fspath(exp_file)], capture_output=True, timeout=60, check=False)
                    self.assertEqual(raw_p.returncode, 0, f"expected raw Lean 4.36.0 to accept exploit {exp_name}: {raw_p.stdout!r}")
                    exp_bundle = _minimal_lean_bundle(exp_src)
                    self._assert_err(
                        tc.TrustCoreError,
                        "LEAN_STATIC_AUDIT_FAILED",
                        lambda eb=exp_bundle: tc.run_isolated_live_lean(eb, ["Demo.t1"], tc.PURE_INIT_AXIOMS),
                    )
                    with self.assertRaises(ver.VerifierError):
                        ver.audit_lean_static(exp_src)

                real_bundle = {
                    fn: (TRACK_DIR / fn).read_bytes()
                    for fn in ("VelocityBounds.lean", "lean-toolchain", "lakefile.toml", "lake-manifest.json")
                }
                old_path = os.environ.get("PATH", "")
                os.environ["PATH"] = f"{shim_d}:{old_path}"
                try:
                    live_real = tc.run_isolated_live_lean(real_bundle, ver.EXPECTED_THEOREMS, tc.PURE_INIT_AXIOMS)
                finally:
                    os.environ["PATH"] = old_path
                self.assertEqual(live_real["status"], "LIVE_LEAN_4_36_0_PASS")
                self.assertEqual(live_real["theorems_verified"], 14)
                self.assertEqual(live_real["zero_axiom_theorems"], 2)
                self.assertTrue(live_real["isolated_tempdir_cleaned"])

        with mock.patch("subprocess.run", side_effect=FileNotFoundError("no lean")):
            self._assert_err(tc.TrustCoreError, "LEAN_TOOL_NOT_FOUND", lambda: tc._default_lean_exec(["lean"], TRACK_DIR, 10))
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["lean"], 1)):
            self._assert_err(tc.TrustCoreError, "LEAN_TIMEOUT", lambda: tc._default_lean_exec(["lean"], TRACK_DIR, 1))

        # run_isolated_live_lean mock matrix incl. bijection & warning rejections (HIGH-3, LOW-6)
        bundle = _minimal_lean_bundle("namespace Demo\ntheorem t1 : 1 = 1 := by decide\nend Demo\n")
        runner_ok = _mock_lean_runner_ok(["Demo.t1"], frozenset({"Demo.t1"}), frozenset())
        live = tc.run_isolated_live_lean(bundle, ["Demo.t1"], tc.PURE_INIT_AXIOMS, runner=runner_ok)
        self.assertEqual(live["status"], "LIVE_LEAN_4_36_0_PASS")
        self.assertEqual(live["zero_axiom_theorems"], 1)
        with mock.patch.object(Path, "exists", return_value=True):
            self._assert_err(tc.TrustCoreError, "TEMP_DIR_RESIDUE", lambda: tc.run_isolated_live_lean(bundle, ["Demo.t1"], tc.PURE_INIT_AXIOMS, runner=runner_ok))

        self._assert_err(tc.TrustCoreError, "EMPTY_LEAN_BUNDLE", lambda: tc.run_isolated_live_lean({}, ["Demo.t1"], tc.PURE_INIT_AXIOMS, runner=runner_ok))
        self._assert_err(tc.TrustCoreError, "EMPTY_EXPECTED_THEOREMS", lambda: tc.run_isolated_live_lean(bundle, [], tc.PURE_INIT_AXIOMS, runner=runner_ok))
        self._assert_err(tc.TrustCoreError, "DUP_EXPECTED_THEOREMS", lambda: tc.run_isolated_live_lean(bundle, ["Demo.t1", "Demo.t1"], tc.PURE_INIT_AXIOMS, runner=runner_ok))
        self._assert_err(tc.TrustCoreError, "UNSAFE_ALLOWED_AXIOM", lambda: tc.run_isolated_live_lean(bundle, ["Demo.t1"], frozenset({"sorryAx"}), runner=runner_ok))
        for bad_bundle, exp_code in [
            ({**bundle, "": b""}, "INVALID_BUNDLE_FILENAME"),
            ({**bundle, "bad": "str"}, "INVALID_BUNDLE_BYTES"),
            ({**bundle, "/abs.lean": b""}, "UNSAFE_BUNDLE_PATH"),
            ({**bundle, "../esc.lean": b""}, "UNSAFE_BUNDLE_PATH"),
            ({**bundle, ".lake/foo": b""}, "LAKE_RESIDUE_IN_BUNDLE"),
            ({**bundle, "venv/Evil.lean": b""}, "UNSAFE_BUNDLE_PATH"),
            ({**bundle, "evil.txt": b"x"}, "UNEXPECTED_BUNDLE_FILE"),
            ({**bundle, "lakefile.lean": b"import Lake\n"}, "LAKEFILE_LEAN_FORBIDDEN"),
            ({k: v for k, v in bundle.items() if k != "lean-toolchain"}, "MISSING_TOOLCHAIN"),
            ({k: v for k, v in bundle.items() if k != "lake-manifest.json"}, "MISSING_LAKE_MANIFEST"),
            ({k: v for k, v in bundle.items() if k != "lakefile.toml"}, "MISSING_LAKEFILE"),
            ({k: v for k, v in bundle.items() if k != "Demo.lean"}, "MISSING_LEAN_SOURCE"),
            (_minimal_lean_bundle("theorem t1 : 1 = 1 := by decide\n", toolchain="leanprover/lean4:v4.36.0-rc1"), "TOOLCHAIN_MISMATCH"),
            (_minimal_lean_bundle("theorem t1 : 1 = 1 := by decide\n", manifest_bytes=b'{"packages":["mathlib"]}\n'), "EXTERNAL_LEAN_PACKAGES"),
            (_minimal_lean_bundle("theorem t1 : 1 = 1 := by decide\n", lakefile_bytes=b'name = "Demo"\nmoreLeanArgs = []\n'), "LAKEFILE_AUDIT_FAILED"),
            (_minimal_lean_bundle("theorem t1 : False := by sorry\n"), "LEAN_STATIC_AUDIT_FAILED"),
            (_minimal_lean_bundle("namespace Demo\ntheorem t1 : 1 = 1 := by decide\ntheorem\n  t_extra : 1 = 1 := rfl\nend Demo\n"), "EXTRA_UNAUDITED_THEOREM_DECL"),
            (_minimal_lean_bundle("namespace Demo\ntheorem t1 : 1 = 1 := rfl\ntheorem t1 : 1 = 1 := rfl\nend Demo\n"), "DUP_DECLARED_THEOREMS"),
            ({**bundle, "Demo.lean": b"theorem t1 : 1 = 1 := by decide\r\n"}, "LEAN_CRLF"),
            ({**bundle, "lean-toolchain": b"leanprover/lean4:v4.36.0\r\n"}, "TOOLCHAIN_CRLF"),
        ]:
            self._assert_err(tc.TrustCoreError, exp_code, lambda bb=bad_bundle: tc.run_isolated_live_lean(bb, ["Demo.t1"], tc.PURE_INIT_AXIOMS, runner=runner_ok))  # type: ignore[arg-type]

        self._assert_err(tc.TrustCoreError, "MISSING_EXPECTED_THEOREM_DECL", lambda: tc.run_isolated_live_lean(bundle, ["Demo.missing"], tc.PURE_INIT_AXIOMS, runner=runner_ok))
        self._assert_err(tc.TrustCoreError, "INVALID_LEAN_MODULE", lambda: tc.run_isolated_live_lean(bundle, ["Demo.t1"], tc.PURE_INIT_AXIOMS, lean_module="bad/mod", runner=runner_ok))

        for bad_runner, exp_code in [
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), version_out=b"\xff\xfe"), "LEAN_OUTPUT_INVALID_UTF8"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), version_rc=1), "LEAN_VERSION_FAILED"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), version_out=b"Lean (version 4.36.0-rc1, Release)\n"), "LEAN_VERSION_MISMATCH"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), build_rc=1), "LAKE_BUILD_FAILED"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), build_err=b"err\n"), "LAKE_BUILD_STDERR"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), build_out=b"Demo.lean:1:0: warning: unused variable\n"), "LAKE_BUILD_WARNING"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_rc=1), "AXIOM_CHECK_FAILED"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_err=b"err\n"), "AXIOM_CHECK_STDERR"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_override=b"garbage line\n"), "UNEXPECTED_AXIOM_LINE"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_override=b"'Demo.t1' depends on axioms: [sorryAx]\n"), "FORBIDDEN_KERNEL_AXIOM"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_override=b"'Demo.t1' depends on axioms: [Classical.choice]\n"), "DISALLOWED_AXIOM"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_override=b"'Demo.t1' does not depend on any axioms\n'Demo.t1' does not depend on any axioms\n"), "DUPLICATE_AXIOM_REPORT"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_override=b"'Demo.t1' depends on axioms: [propext]\n'Demo.t1' depends on axioms: [propext]\n"), "DUPLICATE_AXIOM_REPORT"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_override=b"'Demo.other' does not depend on any axioms\n"), "MISSING_AXIOM_THEOREMS"),
            (_mock_lean_runner_ok(["Demo.t1"], frozenset(), frozenset(), axiom_override=b"'Demo.t1' does not depend on any axioms\n'Demo.extra' does not depend on any axioms\n"), "EXTRA_AXIOM_THEOREMS"),
        ]:
            self._assert_err(tc.TrustCoreError, exp_code, lambda br=bad_runner: tc.run_isolated_live_lean(bundle, ["Demo.t1"], tc.PURE_INIT_AXIOMS, runner=br))

    def test_03_preflight_checks_and_synthetic_defects(self) -> None:
        self._assert_err(tc.TrustCoreError, "INVALID_TRACK_DIR", lambda: pf.run_preflight(123))  # type: ignore[arg-type]
        self._assert_err(tc.TrustCoreError, "NUL_IN_PATH", lambda: pf.run_preflight("bad\x00dir"))
        self._assert_err(tc.TrustCoreError, "TRACK_DIR_NOT_FOUND", lambda: pf.run_preflight("/nonexistent_s168_dir_xyz"))
        self._assert_err(tc.TrustCoreError, "INVALID_BUDGET_MS", lambda: pf.run_preflight(TRACK_DIR, budget_ms=0))
        self._assert_err(tc.TrustCoreError, "INVALID_BUDGET_MS", lambda: pf.run_preflight(TRACK_DIR, budget_ms=pf.MAX_BUDGET_MS + 1))

        self.assertTrue(pf._digits_prefix_matches("1234", "1234"))
        self.assertFalse(pf._digits_prefix_matches("123", "1234"))
        self.assertFalse(pf._digits_prefix_matches("999", "1000"))

        with tempfile.TemporaryDirectory(prefix="s168_pf_") as tmp_s:
            tmp = Path(tmp_s)
            f_not_dir = tmp / "a_file.txt"
            f_not_dir.write_text("hi\n", encoding="utf-8")
            self._assert_err(tc.TrustCoreError, "TRACK_DIR_NOT_DIR", lambda: pf.run_preflight(f_not_dir))
            empty_d = tmp / "empty_d"
            empty_d.mkdir()
            self._assert_err(tc.TrustCoreError, "EMPTY_TRACK_DIR", lambda: pf.run_preflight(empty_d))

            fifo_u = tmp / "u.fifo"
            os.mkfifo(fifo_u)
            hl_u = tmp / "hard_a.txt"
            os.link(f_not_dir, hl_u)
            self._assert_err(tc.TrustCoreError, "NON_REGULAR_FILE", lambda: pf._read_regular_nofollow_under(tmp, Path("u.fifo")))
            self._assert_err(tc.TrustCoreError, "HARDLINK_FORBIDDEN", lambda: pf._read_regular_nofollow_under(tmp, Path("hard_a.txt")))
            self._assert_err(tc.TrustCoreError, "PREFLIGHT_IO_ERROR", lambda: pf._read_regular_nofollow_under(tmp, Path("missing.txt")))
            os.unlink(hl_u)
            raw_hi, _ = pf._read_regular_nofollow_under(tmp, Path("a_file.txt"), max_bytes=3)
            self.assertEqual(raw_hi, b"hi\n")
            self._assert_err(tc.TrustCoreError, "FILE_TOO_LARGE", lambda: pf._read_regular_nofollow_under(tmp, Path("a_file.txt"), max_bytes=2))

            # Clean synthetic track passes with 0 findings + deterministic CLI (no elapsed_ms)
            clean_d = tmp / "clean_track"
            clean_d.mkdir()
            (clean_d / "Demo.lean").write_text("namespace Demo\ntheorem ok_valid : 1 = 1 := by decide\nend Demo\n", encoding="utf-8", newline="\n")
            (clean_d / "lakefile.toml").write_text('name = "Demo"\n', encoding="utf-8", newline="\n")
            (clean_d / "demo_certificate.json").write_text('{"big": "-30629060076556831072416516750219744007195842510749495518880944028"}\n', encoding="utf-8", newline="\n")
            (clean_d / "REPORT.md").write_text("# Report\n\n## Lean Formalization\n\nProves `Demo.ok_valid` (`-3.062906... × 10^64`).\n", encoding="utf-8", newline="\n")
            (clean_d / "verify_demo.py").write_text(
                "import argparse, os\n"
                "def strict_json_equal(a, b):\n    return type(a) is type(b) and a == b\n"
                "def mk():\n    return argparse.ArgumentParser(allow_abbrev=False)\n"
                "def write_cert_safe(path, txt):\n"
                "    with open(path, 'w') as fh:\n        fh.write(txt)\n"
                "    os.replace(path, path)\n",
                encoding="utf-8",
                newline="\n",
            )
            res_c = pf.run_preflight(clean_d, budget_ms=pf.MAX_BUDGET_MS)
            self.assertTrue(res_c["passed"], res_c["findings"])
            self.assertEqual(res_c["checks_applicability"]["lean_static"], "APPLIED")
            self.assertFalse(pf._verifier_ast_hashes_results("def broken(:\n", "r.json"))
            with mock.patch("os.listdir", side_effect=OSError(errno.EACCES, "denied")):
                self._assert_err(tc.TrustCoreError, "PREFLIGHT_IO_ERROR", lambda: pf.run_preflight(clean_d))
            with self.assertRaises(OSError):
                pf._open_dir_nofollow_under(clean_d, Path("missing_subdir"))

            # Delta-4 MED-4 & LOW-2 adversarial bypasses: AP alias, setdefault SoftSafe, cross-file subclass,
            # txt.replace inside open("w"), Name==Call & Subscript==Subscript BOOL_INT_EQ_RISK,
            # 1.23e10 & 3×10^67 sci notation, EXTENSIONLESS CRLF/BOM, nested subdirs (bounded FDs)
            med4_d = tmp / "med4_adv"
            (med4_d / "sub1" / "sub2").mkdir(parents=True)
            (med4_d / "sub1" / "sub2" / "ok.txt").write_text("clean\n", encoding="utf-8", newline="\n")
            (med4_d / "EXTENSIONLESS").write_bytes(b"\xef\xbb\xbfhello\r\n")
            (med4_d / "demo_certificate.json").write_text('{"x": 1}\n', encoding="utf-8", newline="\n")
            (med4_d / "REPORT.md").write_text("# Report\n\nUnbacked: `1.23e10` and `3 × 10^67`.\n", encoding="utf-8", newline="\n")
            (med4_d / "base_cli.py").write_text(
                "from argparse import ArgumentParser as AP\n"
                "class ImportedBadParser(AP):\n    pass\n",
                encoding="utf-8",
                newline="\n",
            )
            (med4_d / "cli_bypass.py").write_text(
                "from argparse import ArgumentParser as AP\n"
                "from base_cli import ImportedBadParser\n"
                "class SoftSafe(AP):\n"
                "    def __init__(self, *a, **kw):\n"
                "        kw.setdefault('allow_abbrev', False)\n"
                "        super().__init__(*a, **kw)\n"
                "def run():\n"
                "    p1 = AP()\n"
                "    p2 = SoftSafe(allow_abbrev=True)\n"
                "    p3 = ImportedBadParser()\n"
                "    return p1, p2, p3\n",
                encoding="utf-8",
                newline="\n",
            )
            (med4_d / "write_eq_bypass.py").write_text(
                "def write_json_bad(path, txt):\n"
                "    with open(path, 'w') as fh:\n"
                "        fh.write(txt.replace('\\r', ''))\n"
                "def check(loaded, doc):\n"
                "    a = (loaded == build_cert())\n"
                "    b = (loaded['k'] == doc['k'])\n"
                "    return a and b\n",
                encoding="utf-8",
                newline="\n",
            )
            res_m4 = pf.run_preflight(med4_d)
            self.assertFalse(res_m4["passed"])
            m4_pairs = {(f["file"], f["code"]) for f in res_m4["findings"]}
            for exp_p in (
                ("EXTENSIONLESS", "BOM_RESIDUE"),
                ("EXTENSIONLESS", "CRLF_RESIDUE"),
                ("REPORT.md", "SCI_NOTATION_UNBACKED"),
                ("cli_bypass.py", "MISSING_ALLOW_ABBREV_FALSE"),
                ("write_eq_bypass.py", "UNSAFE_WRITE_NON_ATOMIC"),
                ("write_eq_bypass.py", "BOOL_INT_EQ_RISK"),
            ):
                self.assertIn(exp_p, m4_pairs, f"MED-4/LOW-2 missed {exp_p}: {m4_pairs}")
            self.assertEqual(
                sum(1 for f in res_m4["findings"] if f["file"] == "cli_bypass.py" and f["code"] == "MISSING_ALLOW_ABBREV_FALSE"),
                3,
            )
            self.assertEqual(
                sum(1 for f in res_m4["findings"] if f["file"] == "write_eq_bypass.py" and f["code"] == "BOOL_INT_EQ_RISK"),
                2,
            )
            self.assertEqual(
                sum(1 for f in res_m4["findings"] if f["file"] == "REPORT.md" and f["code"] == "SCI_NOTATION_UNBACKED"),
                2,
            )

            out_b, err_b = io.StringIO(), io.StringIO()
            with redirect_stdout(out_b), redirect_stderr(err_b):
                self.assertEqual(pf.main([str(clean_d), "--json"]), 0)
            cli_obj = json.loads(out_b.getvalue().strip())
            self.assertNotIn("elapsed_ms", cli_obj)
            self.assertTrue(cli_obj["within_budget"])

            # Budget exceeded must FAIL cleanly (MED-5)
            with mock.patch("time.monotonic_ns", side_effect=[0, 5_000_000_000]):
                res_slow = pf.run_preflight(clean_d, budget_ms=2000)
            self.assertFalse(res_slow["passed"])
            self.assertIn("PREFLIGHT_BUDGET_EXCEEDED", {f["code"] for f in res_slow["findings"]})

            # MED-5 + LOW-5 exact adversarial bypass suite:
            # .env, hardlink structured finding, VERIFIED+false, Ghost.fake_thm, unbacked sci even with non-empty cert_profiles,
            # indirect ArgumentParser subclass, bogus strict_json_equal (no type check), fake __init__ allow_abbrev substring,
            # non-atomic write, all-dropped gates, split-function read+sha256 verifier
            adv_d = tmp / "adv_med5"
            adv_d.mkdir()
            ant_key = "sk" + "-ant-api03-abcdefghijklmnop"
            (adv_d / ".env").write_text(f"API_KEY={ant_key}\n", encoding="utf-8", newline="\n")
            os.link(f_not_dir, adv_d / "hardlinked.txt")
            (adv_d / "cert_certificate.json").write_text(
                '{"big": 30629060076556831072416516750219744007195842510749495518880944028, "gate_pass": false, "verdict": "VERIFIED"}\n',
                encoding="utf-8",
                newline="\n",
            )
            (adv_d / "REPORT.md").write_text("# Report\n\nCites `Ghost.fake_thm`, `9.876 × 10^42`, and `1.2e25`.\n", encoding="utf-8", newline="\n")
            (adv_d / "a.py").write_text(
                "from argparse import ArgumentParser\n"
                "class MyParser(ArgumentParser):\n    pass\n"
                "class SubParser(MyParser):\n    pass\n"
                "class FakeSafe(ArgumentParser):\n"
                "    def __init__(self):\n"
                "        allow_abbrev = True\n"
                "        flag = False\n"
                "def strict_json_equal(cert, payload):\n    return cert == payload\n"
                "def bad_cmp(cert, payload):\n"
                "    p = MyParser()\n"
                "    p2 = SubParser()\n"
                "    p3 = FakeSafe()\n"
                "    sp = p.add_subparsers()\n"
                "    sp.add_parser('sub')\n"
                "    return cert == payload\n"
                "def write_json_bad(path, txt):\n"
                "    with open(path, 'w') as fh:\n"
                "        fh.write(txt)\n"
                "def all_dropped(a, b):\n"
                "    g1_gate_pass = a > 0\n"
                "    g2_gate_pass = b > 0\n"
                "    return True\n",
                encoding="utf-8",
                newline="\n",
            )
            (adv_d / "demo_results.json").write_text('{"ok": true}\n', encoding="utf-8", newline="\n")
            (adv_d / "verify_fake.py").write_text(
                "# bind_empirical_artifact('demo_results.json', 'bench.py')\n"
                "import hashlib\n"
                "def unrelated_hash():\n    return hashlib.sha256(b'x').hexdigest()\n"
                "def read_only():\n    return open('demo_results.json').read()\n",
                encoding="utf-8",
                newline="\n",
            )
            res_adv = pf.run_preflight(adv_d)
            self.assertFalse(res_adv["passed"])
            adv_codes = {(f["file"], f["code"]) for f in res_adv["findings"]}
            for exp_pair in (
                (".env", "HYGIENE_CREDENTIAL_LEAK"),
                ("hardlinked.txt", "HARDLINK_FORBIDDEN"),
                ("cert_certificate.json", "CERT_VERDICT_CONTRADICTION"),
                ("REPORT.md", "GHOST_LEAN_THEOREM"),
                ("REPORT.md", "SCI_NOTATION_UNBACKED"),
                ("a.py", "MISSING_ALLOW_ABBREV_FALSE"),
                ("a.py", "BOOL_INT_EQ_RISK"),
                ("a.py", "UNSAFE_WRITE_NON_ATOMIC"),
                ("a.py", "DROPPED_GATE_VARIABLE"),
                ("demo_results.json", "UNHASHED_RESULTS_JSON"),
            ):
                self.assertIn(exp_pair, adv_codes, f"MED-5/LOW-5 missed {exp_pair}: {adv_codes}")
            # Ensure FakeSafe & SubParser & bogus strict_json_equal all triggered findings!
            a_missing_abbrev = [f for f in res_adv["findings"] if f["file"] == "a.py" and f["code"] == "MISSING_ALLOW_ABBREV_FALSE"]
            self.assertGreaterEqual(len(a_missing_abbrev), 4)
            a_bool_risk = [f for f in res_adv["findings"] if f["file"] == "a.py" and f["code"] == "BOOL_INT_EQ_RISK"]
            self.assertEqual(len(a_bool_risk), 2)
            # Delta-5 LOW-4: variable alias, conditional allow_abbrev, Attribute compare, async writer, `import mod; mod.UnsafeSub()`
            low4_d = tmp / "low4"
            low4_d.mkdir()
            (low4_d / "mod.py").write_text("import argparse\nclass UnsafeSub(argparse.ArgumentParser):\n    pass\n", encoding="utf-8", newline="\n")
            (low4_d / "a.py").write_text(
                "import argparse\nimport mod\n"
                "def f1():\n    P = argparse.ArgumentParser\n    return P()\n"
                "class C(argparse.ArgumentParser):\n    def __init__(self, *a, **kw):\n        if False:\n            kw['allow_abbrev'] = False\n        super().__init__(*a, **kw)\n"
                "class SafeTop(argparse.ArgumentParser):\n    def __init__(self, *a, **kw):\n        kw['allow_abbrev'] = False\n        super().__init__(*a, **kw)\n"
                "def f2(cert, payload):\n    return cert.x == payload.y\n"
                "async def write_json_async(path, txt):\n    with open(path, 'w') as fh:\n        fh.write(txt)\n"
                "def f3():\n    return mod.UnsafeSub()\n"
                "def f4():\n    return C(), SafeTop()\n",
                encoding="utf-8",
                newline="\n",
            )
            low4_res = pf.run_preflight(low4_d)
            low4_f = sorted((f["file"], f["line"], f["code"]) for f in low4_res["findings"])
            self.assertEqual(
                low4_f,
                [
                    ("a.py", 5, "MISSING_ALLOW_ABBREV_FALSE"),
                    ("a.py", 16, "BOOL_INT_EQ_RISK"),
                    ("a.py", 17, "UNSAFE_WRITE_NON_ATOMIC"),
                    ("a.py", 21, "MISSING_ALLOW_ABBREV_FALSE"),
                    ("a.py", 23, "MISSING_ALLOW_ABBREV_FALSE"),
                ],
            )
            # Hardlink-only directory does not crash with EMPTY_TRACK_DIR, reports HARDLINK_FORBIDDEN
            hl_only_d = tmp / "hl_only"
            hl_only_d.mkdir()
            os.link(f_not_dir, hl_only_d / "only_hl.txt")
            res_hl = pf.run_preflight(hl_only_d)
            self.assertFalse(res_hl["passed"])
            self.assertIn(("only_hl.txt", "HARDLINK_FORBIDDEN"), {(f["file"], f["code"]) for f in res_hl["findings"]})

            # Missing verifier when results.json present (MED-5)
            no_ver_d = tmp / "no_ver"
            no_ver_d.mkdir()
            (no_ver_d / "demo_results.json").write_text('{"ok": true}\n', encoding="utf-8", newline="\n")
            res_nv = pf.run_preflight(no_ver_d)
            self.assertIn("MISSING_VERIFIER_FOR_RESULTS", {f["code"] for f in res_nv["findings"]})

            # Comprehensive defect injection killing every residue/AST/provenance/witness branch
            bad_d = tmp / "bad_track"
            bad_d.mkdir()
            (bad_d / ".lake").mkdir()
            (bad_d / "__pycache__").mkdir()
            (bad_d / "junk.pyc").write_bytes(b"00")
            (bad_d / "junk.olean").write_bytes(b"00")
            os.symlink(f_not_dir, bad_d / "link.md")
            os.mkfifo(bad_d / "bad.fifo")
            (bad_d / "bad_utf8.md").write_bytes(b"\xff\xfe\n")
            (bad_d / "bom_crlf.txt").write_bytes(b"\xef\xbb\xbfhello\r\n")
            (bad_d / "Bad.lean").write_text("namespace Bad\ntheorem real_thm : False := by sorry\nend Bad\n", encoding="utf-8", newline="\n")
            (bad_d / "lakefile.toml").write_text('[[broken\n', encoding="utf-8", newline="\n")
            (bad_d / "bad_certificate.json").write_text(
                json.dumps({
                    "big": -30629060076556831072416516750219744007195842510749495518880944028,
                    "kg1": {"b1b_gate_pass": True, "kg1_verdict": "FALSIFIED"},
                }) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (bad_d / "bad_json.json").write_text("{broken\n", encoding="utf-8", newline="\n")
            home_leak = chr(47) + "ho" + "me" + chr(47) + "alice/secret"
            model_leak = "clau" + "de-4.5"
            cred_leak = "AK" + "IA1234567890ABCDEF"
            handle_leak = "@" + "coordinator"
            (bad_d / "REPORT.md").write_text(
                "# Report\n\n"
                "## Lean Theorem Inventory\n"
                "| Public Theorem | Axioms |\n|---|---|\n"
                "| `Bad.ghost_ns_thm` | `[]` |\n"
                "| `ghost_thm_witness` | `[]` |\n\n"
                "Wrong sci: `−3.062906… × 10^67` and `-3.06e68`.\n"
                "Wrong big int: -30629060076556831072416516750219744007195842510749495518880999999.\n"
                f"Leaks: {home_leak} {model_leak} {cred_leak} {handle_leak}\n",
                encoding="utf-8",
                newline="\n",
            )
            (bad_d / "bad_syntax.py").write_text("def broken(:\n", encoding="utf-8", newline="\n")
            (bad_d / "verify_bad.py").write_text(
                "import argparse, os\n"
                "def check(cert, payload):\n"
                "    assert True\n"
                "    p = argparse.ArgumentParser()\n"
                "    return cert == payload\n"
                "def write_cert(path, data):\n"
                "    fd = os.open(path, os.O_WRONLY | os.O_TRUNC)\n"
                "    os.write(fd, data)\n"
                "def eval_kg(a, b):\n"
                "    b1c_hmse_pass = a > 0\n"
                "    b1b_ppl_pass = b > 0\n"
                "    if b1c_hmse_pass:\n"
                "        return 'OK'\n"
                "    return 'FALSIFIED'\n"
                "NOTE = '@" + "coordinator'\n",
                encoding="utf-8",
                newline="\n",
            )
            res_f = bad_d / "demo_empirical_results.json"
            bench_f = bad_d / "demo_bench.py"
            res_f.write_text('{"bench_script_sha256": "0000"}\n', encoding="utf-8", newline="\n")
            bench_f.write_text("def bench():\n    return 1\n", encoding="utf-8", newline="\n")
            os.utime(res_f, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
            os.utime(bench_f, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))

            res_bad = pf.run_preflight(bad_d)
            self.assertFalse(res_bad["passed"])
            pairs = {(f["file"], f["code"]) for f in res_bad["findings"]}
            details = {(f["file"], f["code"], f.get("detail", "")) for f in res_bad["findings"]}
            for exp_pair in (
                (".lake", "LAKE_RESIDUE"),
                ("junk.olean", "LAKE_RESIDUE"),
                ("__pycache__", "PYCACHE_RESIDUE"),
                ("junk.pyc", "PYCACHE_RESIDUE"),
                ("link.md", "SYMLINK_RESIDUE"),
                ("bad.fifo", "NON_REGULAR_FILE"),
                ("bom_crlf.txt", "BOM_RESIDUE"),
                ("bom_crlf.txt", "CRLF_RESIDUE"),
                ("bad_utf8.md", "INVALID_UTF8"),
                ("Bad.lean", "LEAN4_SORRY"),
                ("lakefile.toml", "LAKEFILE_TOML_SYNTAX"),
                ("bad_json.json", "JSON_SYNTAX_ERROR"),
                ("bad_certificate.json", "CERT_VERDICT_CONTRADICTION"),
                ("REPORT.md", "SCI_NOTATION_MISMATCH"),
                ("REPORT.md", "INTEGER_WITNESS_MISMATCH"),
                ("REPORT.md", "HYGIENE_PATH_LEAK"),
                ("REPORT.md", "HYGIENE_MODEL_LEAK"),
                ("REPORT.md", "HYGIENE_CREDENTIAL_LEAK"),
                ("REPORT.md", "HYGIENE_HANDLE_LEAK"),
                ("verify_bad.py", "HYGIENE_HANDLE_LEAK"),
                ("bad_syntax.py", "PYTHON_SYNTAX_ERROR"),
                ("verify_bad.py", "BARE_ASSERT"),
                ("verify_bad.py", "MISSING_ALLOW_ABBREV_FALSE"),
                ("verify_bad.py", "BOOL_INT_EQ_RISK"),
                ("verify_bad.py", "UNSAFE_WRITE_O_TRUNC"),
                ("verify_bad.py", "DROPPED_GATE_VARIABLE"),
                ("demo_empirical_results.json", "STALE_RESULTS_JSON"),
                ("demo_empirical_results.json", "RESULTS_BENCH_SHA_MISMATCH"),
                ("demo_empirical_results.json", "UNHASHED_RESULTS_JSON"),
            ):
                self.assertIn(exp_pair, pairs, f"missing {exp_pair}")
            self.assertTrue(any("Bad.ghost_ns_thm" in d for _, c, d in details if c == "GHOST_LEAN_THEOREM"))
            self.assertTrue(any("ghost_thm_witness" in d for _, c, d in details if c == "GHOST_LEAN_THEOREM"))

            # CLI emits full findings (no [:3] truncation!)
            out_b2, err_b2 = io.StringIO(), io.StringIO()
            with redirect_stdout(out_b2), redirect_stderr(err_b2):
                self.assertEqual(pf.main([str(bad_d), "--json"]), 2)
            err_msg = json.loads(err_b2.getvalue().strip())["message"]
            self.assertIn("UNHASHED_RESULTS_JSON", err_msg)

    def test_04_fast_mutate_failfast_dedup_alias_and_isolation(self) -> None:
        # inject_unittest_failfast: AST-only Case 2 rejects comments & custom argv (HIGH-4)
        c1, inj1 = fm.inject_unittest_failfast(["python3", "-m", "unittest", "test_x.py"])
        self.assertTrue(inj1)
        self.assertEqual(c1, ["python3", "-m", "unittest", "-f", "test_x.py"])
        c2, inj2 = fm.inject_unittest_failfast(["python3", "-m", "unittest", "discover", "-s", "."])
        self.assertTrue(inj2)
        self.assertEqual(c2, ["python3", "-m", "unittest", "discover", "-f", "-s", "."])
        _, inj3 = fm.inject_unittest_failfast(["python3", "-m", "unittest", "-f", "test_x.py"])
        self.assertFalse(inj3)
        _, inj4 = fm.inject_unittest_failfast(["echo", "hi"])
        self.assertFalse(inj4)

        # Diff & line-range parser exact boundaries + upper span guard (LOW-5)
        diff_txt = "@@ -1,0 +5,3 @@\n+a\n+b\n+c\n@@ -10,2 +20 @@\n+z\n@@ -30,1 +40,0 @@\n"
        self.assertEqual(fm.parse_unified_diff_added_lines(diff_txt), {5, 6, 7, 20})
        self.assertEqual(fm.parse_line_ranges("1-1, 3-5, 9"), {1, 3, 4, 5, 9})
        self.assertEqual(len(fm.parse_line_ranges(f"1-{fm.MAX_LINE_RANGE_SPAN}")), fm.MAX_LINE_RANGE_SPAN)
        self.assertEqual(len(fm.parse_line_ranges(f"1-{fm.MAX_LINE_RANGE_SPAN - 1},100000")), fm.MAX_LINE_RANGE_SPAN)
        self.assertEqual(len(fm.parse_line_ranges("1-50000,50001-100000")), fm.MAX_LINE_RANGE_SPAN)
        self._assert_err(tc.TrustCoreError, "EMPTY_LINE_RANGE", lambda: fm.parse_line_ranges(""))
        self._assert_err(tc.TrustCoreError, "LINE_RANGE_TOO_LARGE", lambda: fm.parse_line_ranges(f"1-{fm.MAX_LINE_RANGE_SPAN + 1}"))
        self._assert_err(tc.TrustCoreError, "LINE_RANGE_TOO_LARGE", lambda: fm.parse_line_ranges("1-60000,60001-100001"))
        self._assert_err(tc.TrustCoreError, "LINE_RANGE_TOO_LARGE", lambda: fm.parse_line_ranges(f"1-{fm.MAX_LINE_RANGE_SPAN},100001"))
        for bad_rng in ["0", "0-2", "5-3", "a-b", "x"]:
            self._assert_err(tc.TrustCoreError, "INVALID_LINE_RANGE", lambda br=bad_rng: fm.parse_line_ranges(br))

        # {target} with space expands AFTER shlex.split (LOW-5) + _is_self_check_invocation malformed cmd
        sp_cmd = fm._prepare_base_cmd("python3 {target}", "dir with space/mod.py", add_cwd=True)
        self.assertEqual(sp_cmd[-1], "dir with space/mod.py")
        self.assertFalse(fm._is_self_check_invocation(Path("a.py"), "python3 'unclosed"))
        self.assertFalse(fm._script_has_ast_unittest_main(Path("/nonexistent_s168_script_xyz.py")))

        # AST alias (local + module attribute + getattr), self-check mode, and non-module obj.check guard (MED-6, LOW-5)
        alias_src = (
            "import mod\n"
            "def req(cond, msg):\n    if not cond:\n        raise ValueError(msg)\n"
            "def run(x, obj):\n"
            "    g = req\n"
            "    g(x > 0, 'pos')\n"
            "    h = mod.req\n"
            "    h(x > 1, 'gt1')\n"
            "    getattr(mod, 'req', req)(x >= 1, 'ge1')\n"
            "    obj.check(x > 0)\n"
        )
        _, alias_sites = fm.discover_mutant_sites(alias_src)
        self.assertEqual(len(alias_sites), 7)
        self.assertTrue(any("g(x > 0" in s.original_src for s in alias_sites))
        self.assertTrue(any("h(x > 1" in s.original_src for s in alias_sites))
        self.assertTrue(any("req(x >= 1" in s.original_src for s in alias_sites))
        self.assertFalse(any("check(x > 0" in s.original_src for s in alias_sites))

        selfcheck_src = (
            "def check(cond, msg):\n    if not cond:\n        raise ValueError(msg)\n"
            "check(10 == 10, 'eq')\n"
            "if False:\n    raise SystemExit(1)\n"
        )
        _, sc_sites = fm.discover_mutant_sites(selfcheck_src, self_check_mode=True)
        sc_kinds = {s.kind for s in sc_sites}
        self.assertIn("guard_selfcheck_negate", sc_kinds)
        self.assertIn("boundary_const_require", sc_kinds)
        for s in sc_sites:
            if s.kind == "boundary_const_require":
                self.assertIn("10 == 11", fm.apply_single_mutation(selfcheck_src, s))
        non_int_cmp = "check(x == 'abc')\n"
        non_int_nodes = list(ast.walk(ast.parse(non_int_cmp)))
        call_idx = next(i for i, nd in enumerate(non_int_nodes) if isinstance(nd, ast.Call))
        self._assert_err(tc.TrustCoreError, "MUTANT_NODE_TYPE", lambda: fm.apply_single_mutation(non_int_cmp, fm.MutantSite("M001", "boundary_const_require", 1, 0, call_idx, "a", "b", 0)))

        edge_src = (
            "def no_args():\n    return 1\n"
            "class C:\n"
            "    def only_self(self):\n        return 1\n"
            "    def two_args(self, cond):\n"
            "        if not cond:\n            raise ValueError('bad')\n"
            "def empty_rem(c):\n    x = 1\n"
            "def two_non_ret(c):\n    if not c:\n        raise ValueError()\n    x = 1\n"
            "def bad_pol(c):\n    if c == 5:\n        pass\n    else:\n        raise ValueError()\n"
            "def non_const_ret(x, y):\n    if x:\n        return y\n"
            "def caller(c, v):\n    c.two_args(v > 0)\n    two_non_ret(v > 0)\n    bad_pol(v > 0)\n"
        )
        _, edge_sites = fm.discover_mutant_sites(edge_src)
        self.assertTrue(any(s.kind == "guard_require_call" and "two_args" in s.original_src for s in edge_sites))
        self.assertFalse(any("two_non_ret(" in s.original_src for s in edge_sites))
        self.assertFalse(any("bad_pol(" in s.original_src for s in edge_sites))

        self._assert_err(tc.TrustCoreError, "MUTATOR_SYNTAX_ERROR", lambda: fm.discover_mutant_sites("def bad(:\n"))
        self._assert_err(tc.TrustCoreError, "INVALID_GUARD_SPEC", lambda: fm.discover_mutant_sites("x = 1\n", extra_guards=["bad:unknown"]))
        simple_src = "x = 1\n"
        n_nodes = len(list(ast.walk(ast.parse(simple_src))))
        for k in (
            "guard_if_reject", "guard_else_reject", "guard_except_reject",
            "boundary_cmp", "guard_require_call", "guard_reject_call",
            "guard_selfcheck_negate", "boundary_cmp_require", "boundary_const_require",
        ):
            self._assert_err(tc.TrustCoreError, "MUTANT_NODE_TYPE", lambda kk=k: fm.apply_single_mutation(simple_src, fm.MutantSite("M001", kk, 1, 0, 0, "a", "b")))
        self._assert_err(tc.TrustCoreError, "UNKNOWN_MUTANT_KIND", lambda: fm.apply_single_mutation(simple_src, fm.MutantSite("M001", "unknown_kind", 1, 0, 0, "a", "b")))
        self._assert_err(tc.TrustCoreError, "MUTANT_INDEX_OOB", lambda: fm.apply_single_mutation(simple_src, fm.MutantSite("M001", "guard_if_reject", 1, 0, n_nodes, "a", "b")))
        self._assert_err(tc.TrustCoreError, "INVALID_TEST_CMD", lambda: fm._prepare_base_cmd("python3 'unclosed", "a.py"))

        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["git"], 0, b"@@ -1,0 +7,2 @@\n", b"")):
            self.assertEqual(fm._get_git_changed_lines(Path("a.py"), TRACK_DIR, "HEAD"), {7, 8})
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["git"], 1, b"", b"err")):
            self._assert_err(tc.TrustCoreError, "GIT_DIFF_FAILED", lambda: fm._get_git_changed_lines(Path("a.py"), TRACK_DIR, None))
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["git"], 1)):
            self._assert_err(tc.TrustCoreError, "GIT_DIFF_FAILED", lambda: fm._get_git_changed_lines(Path("a.py"), TRACK_DIR, None))

        with tempfile.TemporaryDirectory(prefix="s168_fm_") as tmp_s:
            tmp = Path(tmp_s)
            mod_p = tmp / "mini_guard.py"
            tst_p = tmp / "test_mini.py"
            mod_p.write_text(
                "def gate(cond, msg):\n"
                "    if not cond:\n"
                "        raise ValueError(msg)\n"
                "def check_val(x):\n"
                "    gate(x >= 10, 'too small')\n"
                "    if x == 42:\n"
                "        return False\n"
                "    try:\n"
                "        y = 100 // x\n"
                "    except ZeroDivisionError:\n"
                "        return None\n"
                "    return y > 0\n",
                encoding="utf-8",
                newline="\n",
            )
            tst_p.write_text(
                "import os, unittest\n"
                "import mini_guard as mg\n"
                "class T(unittest.TestCase):\n"
                "    def test_1(self):\n"
                "        self.assertNotIn('PYTHONPATH', os.environ)\n"
                "        self.assertTrue(mg.check_val(10))\n"
                "        with self.assertRaises(ValueError):\n"
                "            mg.check_val(9)\n"
                "        self.assertFalse(mg.check_val(42))\n"
                "        try:\n"
                "            mg.gate(False, 'x')\n"
                "        except ValueError:\n"
                "            pass\n"
                "        else:\n"
                "            self.fail('gate did not raise')\n"
                "        orig = mg.gate\n"
                "        mg.gate = lambda c, m: None\n"
                "        try:\n"
                "            self.assertIsNone(mg.check_val(0))\n"
                "        finally:\n"
                "            mg.gate = orig\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
                newline="\n",
            )

            # HIGH-4: Comment `# unittest.main(` + argparse script MUST NOT inject `-f` or produce false kills!
            fake_t = tmp / "fake_argparse_test.py"
            fake_t.write_text(
                "# unittest.main(\n"
                "import argparse\n"
                "p = argparse.ArgumentParser()\n"
                "p.parse_args()\n",
                encoding="utf-8",
                newline="\n",
            )
            fc, finj = fm.inject_unittest_failfast(["python3", "fake_argparse_test.py"], work_root=tmp)
            self.assertFalse(finj)
            self.assertEqual(fc, ["python3", "fake_argparse_test.py"])
            fake_res = fm.run_fast_mutation_pass(mod_p, "python3 fake_argparse_test.py", work_root=tmp, add_cwd=True, max_mutants=2)
            self.assertEqual(fake_res["verdict"], "FAIL")
            self.assertEqual(fake_res["killed"], 0)

            # HIGH-4: Mtime preservation across staged copy (results > bench stays strictly true!)
            mtime_a = tmp / "bench_m.py"
            mtime_b = tmp / "res_m.json"
            mtime_a.write_text("def g(x):\n    if x < 0:\n        raise ValueError()\n", encoding="utf-8", newline="\n")
            mtime_b.write_text('{"ok": true}\n', encoding="utf-8", newline="\n")
            os.utime(mtime_a, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
            os.utime(mtime_b, ns=(1_700_000_500_000_000_000, 1_700_000_500_000_000_000))
            m_tst = tmp / "test_mtime.py"
            m_tst.write_text(
                "import os, unittest\n"
                "import bench_m\n"
                "class TM(unittest.TestCase):\n"
                "    def test_mtime(self):\n"
                "        self.assertGreater(os.lstat('res_m.json').st_mtime_ns, os.lstat('bench_m.py').st_mtime_ns)\n"
                "        bench_m.g(0)\n"
                "        with self.assertRaises(ValueError):\n"
                "            bench_m.g(-1)\n",
                encoding="utf-8",
                newline="\n",
            )
            m_pass = fm.run_fast_mutation_pass(mtime_a, "python3 -m unittest test_mtime.py", work_root=tmp, add_cwd=True)
            self.assertTrue(m_pass["passed"])

            dc, dinj = fm.inject_unittest_failfast(["python3", "test_mini.py"], work_root=tmp)
            self.assertTrue(dinj)
            self.assertEqual(dc[-1], "-f")
            # LOW-3: non-python runners & `-m`/`-c` are never mutated; `-W arg` skips cleanly; env strips PYTHONSTARTUP/PYTHONWARNINGS
            self.assertFalse(fm.inject_unittest_failfast(["pytest", "test_mini.py"], work_root=tmp)[1])
            self.assertFalse(fm.inject_unittest_failfast(["python3", "-m", "pytest", "test_mini.py"], work_root=tmp)[1])
            self.assertFalse(fm.inject_unittest_failfast(["python3", "-c", "pass", "test_mini.py"], work_root=tmp)[1])
            self.assertTrue(fm.inject_unittest_failfast(["python3", "-W", "error", "test_mini.py"], work_root=tmp)[1])
            with mock.patch.dict(os.environ, {"PYTHONPATH": "/x", "PYTHONSTARTUP": "/y", "PYTHONWARNINGS": "ignore"}):
                cenv = fm._child_env(1, tmp, tmp)
                self.assertNotIn("PYTHONPATH", cenv)
                self.assertNotIn("PYTHONSTARTUP", cenv)
                self.assertNotIn("PYTHONWARNINGS", cenv)

            # Delta-4 HIGH-1 R5 regression: H1_UNLINK, H1_CHMOD, and H1_SAME_SIZE_MTIME MUST NOT produce false kills!
            # Delta-5 HIGH-1: a mutant running `os.chmod(__file__, 0o000)` on the TARGET itself (w1 + w2 slots) MUST NOT leak.
            for h1_mode, h1_workers in (("H1_UNLINK", 1), ("H1_CHMOD", 1), ("H1_SAME_SIZE_MTIME", 1), ("H1_TARGET_CHMOD", 1), ("H1_TARGET_CHMOD_W2", 2)):
                h1_dir = tmp / f"h1_{h1_mode.lower()}"
                h1_dir.mkdir()
                (h1_dir / "aux.txt").write_text("HELLO\n", encoding="utf-8", newline="\n")
                if h1_mode == "H1_UNLINK":
                    corrupt_stmt = 'os.unlink("aux.txt")'
                elif h1_mode == "H1_CHMOD":
                    corrupt_stmt = 'os.chmod("aux.txt", 0o000)'
                elif h1_mode.startswith("H1_TARGET_CHMOD"):
                    corrupt_stmt = "os.chmod(__file__, 0o000)"
                else:
                    corrupt_stmt = (
                        'st = os.lstat("aux.txt"); open("aux.txt", "w").write("BOGUS\\n"); '
                        'os.utime("aux.txt", ns=(st.st_atime_ns, st.st_mtime_ns))'
                    )
                h1_mod = h1_dir / "h1_target.py"
                h1_mod.write_text(
                    "import os\n"
                    "def check_a(x):\n"
                    "    if x >= 1:\n"
                    '        return open("aux.txt").read()\n'
                    "    else:\n"
                    f"        {corrupt_stmt}\n"
                    '        raise ValueError("bad")\n'
                    "def untested_branch(y):\n"
                    "    if y < 0:\n"
                    "        return False\n"
                    "    return True\n",
                    encoding="utf-8",
                    newline="\n",
                )
                (h1_dir / "test_h1.py").write_text(
                    "import unittest, h1_target\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_ok(self):\n"
                    '        self.assertEqual(h1_target.check_a(1), "HELLO\\n")\n'
                    "        self.assertTrue(h1_target.untested_branch(1))\n",
                    encoding="utf-8",
                    newline="\n",
                )
                h1_res = fm.run_fast_mutation_pass(h1_mod, "python3 -m unittest test_h1.py", work_root=h1_dir, add_cwd=True, workers=h1_workers)
                self.assertEqual(h1_res["verdict"], "FAIL", f"{h1_mode} false PASS: {h1_res}")
                self.assertEqual(h1_res["killed"], 1, f"{h1_mode} false kills: {h1_res['results']}")
                self.assertEqual(h1_res["survived"], 3, f"{h1_mode} survivors lost: {h1_res['results']}")
                untested_statuses = [r["status"] for r in h1_res["results"] if "y < 0" in r["original"]]
                self.assertEqual(untested_statuses, ["SURVIVED", "SURVIVED"])
                self.assertEqual(h1_res["null_mutant"], "passed")

            # Delta-5 HIGH-1 unit: _write_preserve_mtime pins EXACT mode (never leaves 0o200) & replaces hard links / dirs
            wpm_dir = tmp / "wpm"
            wpm_dir.mkdir()
            wpm_t = wpm_dir / "t.py"
            wpm_t.write_text("x = 1\n", encoding="utf-8", newline="\n")
            os.chmod(wpm_t, 0o000)
            fm._write_preserve_mtime(wpm_t, "x = 2\n", (1_700_000_000_000_000_000, 1_700_000_001_000_000_000), 0o644)
            self.assertEqual(stat.S_IMODE(os.lstat(wpm_t).st_mode), 0o644)
            self.assertEqual(os.lstat(wpm_t).st_mtime_ns, 1_700_000_001_000_000_000)
            self.assertEqual(wpm_t.read_text(encoding="utf-8"), "x = 2\n")
            os.link(wpm_t, wpm_dir / "hl.py")
            fm._write_preserve_mtime(wpm_t, "x = 3\n", (1_700_000_000_000_000_000, 1_700_000_001_000_000_000), 0o640)
            self.assertEqual(os.lstat(wpm_t).st_nlink, 1)
            self.assertEqual((wpm_dir / "hl.py").read_text(encoding="utf-8"), "x = 2\n")
            self.assertEqual(stat.S_IMODE(os.lstat(wpm_t).st_mode), 0o640)
            wpm_t.unlink()
            wpm_t.mkdir()
            (wpm_t / "inner").write_text("z", encoding="utf-8")
            os.chmod(wpm_dir, 0o500)
            fm._write_preserve_mtime(wpm_t, "x = 4\n", (1_700_000_000_000_000_000, 1_700_000_001_000_000_000))
            self.assertTrue(stat.S_ISREG(os.lstat(wpm_t).st_mode))
            self.assertEqual(wpm_t.read_text(encoding="utf-8"), "x = 4\n")
            os.chmod(wpm_t, 0o444)
            fm._write_preserve_mtime(wpm_t, "x = 5\n", (1_700_000_000_000_000_000, 1_700_000_001_000_000_000))
            self.assertEqual(stat.S_IMODE(os.lstat(wpm_t).st_mode), 0o644)

            # Delta-5 MED-1 + LOW-5: empty baseline dir (removed by the tested refusal path) is restored with exact mtime -> null_mutant PASS
            ed_dir = tmp / "empty_dir_proj"
            ed_dir.mkdir()
            (ed_dir / "empty_base_dir").mkdir()
            (ed_dir / "ed_target.py").write_text(
                "import os\n"
                "def g(x):\n"
                "    if x < 0:\n"
                '        os.rmdir("empty_base_dir")\n'
                '        raise ValueError("neg")\n'
                "    return x\n",
                encoding="utf-8",
                newline="\n",
            )
            (ed_dir / "test_ed.py").write_text(
                "import os, unittest, ed_target\n"
                "class T(unittest.TestCase):\n"
                "    def test_ed(self):\n"
                "        self.assertTrue(os.path.isdir('empty_base_dir'))\n"
                "        self.assertEqual(os.listdir('empty_base_dir'), [])\n"
                "        self.assertEqual(os.lstat('empty_base_dir').st_mtime_ns, 1700000222000000000)\n"
                "        self.assertEqual(ed_target.g(0), 0)\n"
                "        with self.assertRaises(ValueError):\n"
                "            ed_target.g(-1)\n",
                encoding="utf-8",
                newline="\n",
            )
            os.utime(ed_dir / "empty_base_dir", ns=(1_700_000_222_000_000_000, 1_700_000_222_000_000_000))
            for ed_workers in (1, 2):
                ed_res = fm.run_fast_mutation_pass(ed_dir / "ed_target.py", "python3 -m unittest test_ed.py", work_root=ed_dir, add_cwd=True, workers=ed_workers)
                self.assertEqual(ed_res["null_mutant"], "passed")
                self.assertEqual(ed_res["verdict"], "PASS", f"empty-dir false kill/abort: {ed_res}")
                self.assertTrue(ed_res["passed"])
                self.assertEqual(ed_res["killed"], ed_res["total_mutants"])

            # Dual pass: 100% dedup STILL executes null-mutant control (`null_mutant == 'passed'`, MED-6)
            dual_w1 = fm.run_dual_fast_mutation(
                mod_p, "python3 -m unittest test_mini.py", pass2_guards=["gate:require"],
                work_root=tmp, max_mutants=0, add_cwd=True, workers=1, failfast=True,
            )
            self.assertTrue(dual_w1["passed"])
            self.assertEqual(dual_w1["pass2"]["null_mutant"], "passed")
            self.assertEqual(dual_w1["pass2"]["mutants_executed"], 0)
            self.assertEqual(dual_w1["pass2"]["control_subprocess_evals"], 2)
            self.assertGreater(dual_w1["pass2_dedup_skipped"], 0)

            dual_w2 = fm.run_dual_fast_mutation(
                mod_p, "python3 -m unittest test_mini.py", pass2_guards=["gate"],
                work_root=tmp, max_mutants=0, add_cwd=True, workers=2, failfast=False,
            )
            self.assertTrue(dual_w2["passed"])
            self.assertEqual(dual_w2["killed_combined"], dual_w1["killed_combined"])

            # MED-6: --no-boundaries -> PARTIAL_SCOPE_NOT_FINAL
            no_bnd = fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", work_root=tmp, add_cwd=True, include_boundaries=False)
            self.assertEqual(no_bnd["verdict"], "PARTIAL_SCOPE_NOT_FINAL")
            self.assertFalse(no_bnd["passed"])

            # MED-6 + LOW-4: mutant timeout -> TIMEOUT (FAIL, NOT KILLED!) + live process-group killpg + slot cleanup
            call_t = [0]

            def _mut_timeout(*a: Any, **kw: Any) -> tuple[int, bytes, bytes, bool]:
                call_t[0] += 1
                if call_t[0] <= 2:
                    return 0, b"", b"", False
                return -9, b"", b"", True

            with mock.patch.object(fm, "_run_subprocess_pg", side_effect=_mut_timeout):
                to_res = fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", work_root=tmp, add_cwd=True, max_mutants=1)
            self.assertEqual(to_res["verdict"], "FAIL")
            self.assertEqual(to_res["killed"], 0)
            self.assertEqual(to_res["timed_out"], 1)
            self.assertEqual(to_res["results"][0]["status"], "TIMEOUT")

            # _run_subprocess_pg timeout kills child process group via os.killpg(pid, SIGKILL) (LOW-4)
            fake_pg = mock.Mock(pid=999999)
            fake_pg.communicate.side_effect = [subprocess.TimeoutExpired(["py"], 1), (b"", b"")]
            with (
                mock.patch("subprocess.Popen", return_value=fake_pg),
                mock.patch("os.killpg") as m_killpg,
            ):
                pg_rc, _, _, pg_to = fm._run_subprocess_pg(["py"], tmp, fm._child_env(1, tmp, tmp), 1)
            self.assertTrue(pg_to)
            self.assertEqual(pg_rc, -9)
            m_killpg.assert_called_once_with(999999, fm.signal.SIGKILL)

            # _clean_slot_stray_entries unlinks symlinks without chmodding targets & restores deleted/chmod/same-size-mtime/dir-replaced files (HIGH-1 + LOW-3)
            cln_src = tmp / "cln_src"
            cln_slot = tmp / "cln_slot"
            cln_tmp = tmp / "cln_tmp"
            cln_home = tmp / "cln_home"
            (cln_src / "subd").mkdir(parents=True)
            cln_tmp.mkdir()
            cln_home.mkdir()
            (cln_src / "keep.txt").write_text("orig\n", encoding="utf-8", newline="\n")
            (cln_src / "subd" / "nested.txt").write_text("nest\n", encoding="utf-8", newline="\n")
            (cln_src / "emptyd").mkdir()
            (cln_src / "gone_d").mkdir()
            os.utime(cln_src / "subd", ns=(1_700_000_123_000_000_000, 1_700_000_123_000_000_000))
            _, cln_files, cln_meta, cln_dirs = fm._copy_workroot_nosym(cln_src, cln_slot)
            self.assertEqual(os.lstat(cln_slot / "subd").st_mtime_ns, 1_700_000_123_000_000_000)
            self.assertEqual(set(cln_dirs), {".", "subd", "emptyd", "gone_d"})
            (cln_slot / "gone_d").rmdir()
            (cln_slot / "stray_d" / "deep").mkdir(parents=True)
            ext_target = tmp / "ext_untouched.txt"
            ext_target.write_text("stay\n", encoding="utf-8", newline="\n")
            os.chmod(ext_target, 0o444)
            os.symlink(ext_target, cln_slot / "stray_sym.txt")
            os.symlink(cln_src, cln_slot / "stray_dir_sym")
            (cln_slot / "keep.txt").unlink()
            (cln_slot / "keep.txt").mkdir()
            (cln_slot / "subd" / "nested.txt").unlink()
            os.chmod(cln_slot / "subd", 0o000)
            fm._clean_slot_stray_entries(cln_slot, cln_files, cln_tmp, cln_home, src_root=cln_src, rel_meta=cln_meta, rel_dirs=cln_dirs)
            self.assertTrue((cln_slot / "emptyd").is_dir())
            self.assertTrue((cln_slot / "gone_d").is_dir())
            self.assertFalse((cln_slot / "stray_d").exists())
            self.assertEqual(os.lstat(cln_slot / "subd").st_mtime_ns, 1_700_000_123_000_000_000)
            for d_rel, d_meta in cln_dirs.items():
                self.assertEqual(os.lstat(cln_slot / d_rel).st_mtime_ns, d_meta[2])
                self.assertEqual(stat.S_IMODE(os.lstat(cln_slot / d_rel).st_mode), d_meta[0])
            # Delta-5 LOW-5: post-copy verification fails closed when the live source no longer matches the golden baseline
            (cln_slot / "keep.txt").write_text("tampered\n", encoding="utf-8", newline="\n")

            def _bad_copy2(src: Any, dst: Any, *a: Any, **kw: Any) -> Any:
                Path(dst).write_text("BOGUS\n", encoding="utf-8", newline="\n")
                return dst

            with mock.patch.object(fm.shutil, "copy2", side_effect=_bad_copy2):
                self._assert_err(
                    tc.TrustCoreError,
                    "SLOT_RESTORE_MISMATCH",
                    lambda: fm._clean_slot_stray_entries(cln_slot, cln_files, cln_tmp, cln_home, src_root=cln_src, rel_meta=cln_meta, rel_dirs=cln_dirs),
                )
            fm._clean_slot_stray_entries(cln_slot, cln_files, cln_tmp, cln_home, src_root=cln_src, rel_meta=cln_meta, rel_dirs=cln_dirs)
            self.assertEqual((cln_slot / "keep.txt").read_text(encoding="utf-8"), "orig\n")
            # target_spec: target restored from in-memory source with EXACT pinned mode, even after chmod 0o000
            tgt_rel = "subd/nested.txt"
            os.chmod(cln_slot / tgt_rel, 0o000)
            fm._clean_slot_stray_entries(
                cln_slot, cln_files, cln_tmp, cln_home, src_root=cln_src, rel_meta=cln_meta, rel_dirs=cln_dirs,
                target_spec=(tgt_rel, "nest\n", 0o640, (1_700_000_000_000_000_000, 1_700_000_333_000_000_000)),
            )
            self.assertEqual(stat.S_IMODE(os.lstat(cln_slot / tgt_rel).st_mode), 0o640)
            self.assertEqual(os.lstat(cln_slot / tgt_rel).st_mtime_ns, 1_700_000_333_000_000_000)
            self.assertEqual((cln_slot / tgt_rel).read_text(encoding="utf-8"), "nest\n")
            self.assertEqual(os.lstat(cln_slot / "subd").st_mtime_ns, 1_700_000_123_000_000_000)
            self.assertFalse((cln_slot / "stray_sym.txt").exists() or (cln_slot / "stray_sym.txt").is_symlink())
            self.assertFalse((cln_slot / "stray_dir_sym").exists() or (cln_slot / "stray_dir_sym").is_symlink())
            self.assertEqual((cln_slot / "keep.txt").read_text(encoding="utf-8"), "orig\n")
            self.assertEqual((cln_slot / "subd" / "nested.txt").read_text(encoding="utf-8"), "nest\n")
            self.assertEqual(stat.S_IMODE(os.lstat(ext_target).st_mode), 0o444)
            os.chmod(ext_target, 0o644)

            partial = fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", work_root=tmp, add_cwd=True, changed_lines={5})
            self.assertEqual(partial["verdict"], "PARTIAL_SCOPE_NOT_FINAL")
            self.assertFalse(partial["passed"])

            trunc = fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", work_root=tmp, add_cwd=True, max_mutants=1)
            self.assertTrue(trunc["truncated"])
            self.assertFalse(trunc["passed"])

            weak_tst = tmp / "test_weak.py"
            weak_tst.write_text("import unittest\nclass T(unittest.TestCase):\n    def test_1(self):\n        self.assertTrue(True)\n", encoding="utf-8", newline="\n")
            surv = fm.run_dual_fast_mutation(mod_p, "python3 -m unittest test_weak.py", pass2_guards=["gate"], work_root=tmp, add_cwd=True, max_mutants=1)
            self.assertEqual(surv["verdict"], "FAIL")

            self._assert_err(tc.TrustCoreError, "INVALID_WORKERS", lambda: fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", workers=0))
            self._assert_err(tc.TrustCoreError, "INVALID_MAX_MUTANTS", lambda: fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", max_mutants=-1))
            self._assert_err(tc.TrustCoreError, "INVALID_TIMEOUT", lambda: fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", timeout=0))
            self._assert_err(tc.TrustCoreError, "TARGET_NOT_FOUND", lambda: fm.run_fast_mutation_pass(tmp / "nope.py", "python3 -m unittest test_mini.py", work_root=tmp))
            self._assert_err(tc.TrustCoreError, "TARGET_OUTSIDE_WORKROOT", lambda: fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", work_root=tmp / "other_sub"))
            self._assert_err(tc.TrustCoreError, "EMPTY_TEST_CMD", lambda: fm.run_fast_mutation_pass(mod_p, "", work_root=tmp))
            self._assert_err(tc.TrustCoreError, "BASELINE_TEST_FAILED", lambda: fm.run_fast_mutation_pass(mod_p, "python3 -c 'import sys; sys.exit(1)'", work_root=tmp, add_cwd=True))

            bad_utf = tmp / "bad_utf.py"
            bad_utf.write_bytes(b"\xff\xfe\n")
            self._assert_err(tc.TrustCoreError, "INVALID_UTF8", lambda: fm.run_fast_mutation_pass(bad_utf, "python3 -m unittest test_mini.py", work_root=tmp))
            nomut = tmp / "no_mut.py"
            nomut.write_text("x = 1\n", encoding="utf-8", newline="\n")
            self._assert_err(tc.TrustCoreError, "NO_MUTANTS_DISCOVERED", lambda: fm.run_fast_mutation_pass(nomut, "python3 -m unittest test_mini.py", work_root=tmp))

            comm_p = tmp / "comm_pin.py"
            comm_p.write_text("# PIN_COMMENT\ndef g(x):\n    if x < 0:\n        raise ValueError()\n", encoding="utf-8", newline="\n")
            self._assert_err(
                tc.TrustCoreError,
                "NULL_MUTANT_KILLED",
                lambda: fm.run_fast_mutation_pass(
                    comm_p,
                    "python3 -c \"import sys; sys.exit(0 if '# PIN_COMMENT' in open('comm_pin.py').read() else 1)\"",
                    work_root=tmp,
                    add_cwd=True,
                ),
            )

            with mock.patch.object(fm, "_run_subprocess_pg", return_value=(-9, b"", b"", True)):
                self._assert_err(tc.TrustCoreError, "BASELINE_TEST_TIMEOUT", lambda: fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", work_root=tmp, add_cwd=True, max_mutants=1))
            call_n = [0]

            def _null_timeout(*a: Any, **kw: Any) -> tuple[int, bytes, bytes, bool]:
                call_n[0] += 1
                if call_n[0] == 1:
                    return 0, b"", b"", False
                return -9, b"", b"", True

            with mock.patch.object(fm, "_run_subprocess_pg", side_effect=_null_timeout):
                self._assert_err(tc.TrustCoreError, "NULL_MUTANT_TIMEOUT", lambda: fm.run_fast_mutation_pass(mod_p, "python3 -m unittest test_mini.py", work_root=tmp, add_cwd=True, max_mutants=1))

            out_m, err_m = io.StringIO(), io.StringIO()
            with redirect_stdout(out_m), redirect_stderr(err_m):
                rc1 = fm.main([str(mod_p), "--work-root", str(tmp), "--add-cwd", "--test-cmd", "python3 -m unittest test_mini.py", "--guards", "gate", "--json"])
                rc2 = fm.main([str(mod_p), "--work-root", str(tmp), "--add-cwd", "--test-cmd", "python3 -m unittest test_mini.py", "--changed-lines", "5", "--json"])
            self.assertEqual(rc1, 0)
            self.assertEqual(rc2, 2)

            sym_d = tmp / "sym_wr"
            sym_d.mkdir()
            shutil.copy2(mod_p, sym_d / "mini_guard.py")
            os.symlink(mod_p, sym_d / "bad_sym.py")
            self._assert_err(tc.TrustCoreError, "SYMLINK_IN_WORKROOT", lambda: fm.run_fast_mutation_pass(sym_d / "mini_guard.py", "python3 -m unittest test_mini.py", work_root=sym_d, add_cwd=True))

            fifo_d = tmp / "fifo_wr"
            fifo_d.mkdir()
            shutil.copy2(mod_p, fifo_d / "mini_guard.py")
            os.mkfifo(fifo_d / "bad.fifo")
            self._assert_err(tc.TrustCoreError, "NON_REGULAR_IN_WORKROOT", lambda: fm.run_fast_mutation_pass(fifo_d / "mini_guard.py", "python3 -m unittest test_mini.py", work_root=fifo_d, add_cwd=True))

    def test_05_verifier_zero_shared_code_zone_b_and_lean(self) -> None:
        v_src = (TRACK_DIR / "verify_s168_velocity.py").read_text(encoding="utf-8")
        v_tree = ast.parse(v_src)
        imported: set[str] = set()
        for node in ast.walk(v_tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported.isdisjoint({"trust_core", "preflight", "fast_mutate", "s168_velocity_bench"}))

        # exact_json_equal incl. bool-key vs int-key (LOW-1)
        self.assertTrue(ver.exact_json_equal({"a": [1, False]}, {"a": [1, False]}))
        self.assertFalse(ver.exact_json_equal(True, 1))
        self.assertFalse(ver.exact_json_equal({"a": 1}, {"a": True}))
        self.assertFalse(ver.exact_json_equal({1: "x"}, {True: "x"}))
        self.assertFalse(ver.exact_json_equal({"a": 1}, {"a": 1, "b": 2}))
        self.assertFalse(ver.exact_json_equal({"a": 1}, {"b": 1}))
        self.assertFalse(ver.exact_json_equal([1], [1, 2]))
        self.assertFalse(ver.exact_json_equal([1], [2]))

        for bad_raw, exp_code in [
            (b"", "EMPTY_JSON"),
            (b"\xef\xbb\xbf{}\n", "BOM_FORBIDDEN"),
            (b"{}\r\n", "CR_FORBIDDEN"),
            (b"{}", "NO_FINAL_LF"),
            (b"\xff\xfe\n", "BAD_UTF8"),
            (b'{"a": 1.2}\n', "FLOAT_FORBIDDEN"),
            (b'{"a": NaN}\n', "CONST_FORBIDDEN"),
            (b'{"a": 1, "a": 2}\n', "DUP_KEY"),
            (b'{"a": ' + (b"9" * (ver.MAX_INT_DIGITS + 1)) + b'}\n', "INT_TOO_LONG"),
            (b'{bad\n', "JSON_SYNTAX"),
            (b'{"s": "\\ud800"}\n', "JSON_SURROGATE"),
        ]:
            self._assert_err(ver.VerifierError, exp_code, lambda br=bad_raw: ver.parse_exact_json(br))

        self.assertEqual(len(str(ver.parse_exact_json(b'{"n": ' + (b"9" * ver.MAX_INT_DIGITS) + b'}\n')["n"])), ver.MAX_INT_DIGITS)
        deep_vl: Any = 1
        for _ in range(ver.MAX_DEPTH):
            deep_vl = [deep_vl]
        self.assertIsInstance(ver.parse_exact_json((json.dumps(deep_vl) + "\n").encode("utf-8")), list)
        self._assert_err(ver.VerifierError, "JSON_DEPTH", lambda: ver.parse_exact_json((json.dumps([deep_vl]) + "\n").encode("utf-8")))
        deep_vd: Any = 1
        for _ in range(ver.MAX_DEPTH):
            deep_vd = {"k": deep_vd}
        self.assertIsInstance(ver.parse_exact_json((json.dumps(deep_vd) + "\n").encode("utf-8")), dict)
        self._assert_err(ver.VerifierError, "JSON_DEPTH", lambda: ver.parse_exact_json((json.dumps({"k": deep_vd}) + "\n").encode("utf-8")))

        with tempfile.TemporaryDirectory(prefix="s168_verzb_") as tmp_s:
            tmp = Path(tmp_s)
            sub = tmp / "sub"
            sub.mkdir()
            victim = tmp / "victim.json"
            victim.write_bytes(b'{"stay": 1}\n')
            symd = tmp / "symd"
            os.symlink(sub, symd)
            syml = sub / "syml.json"
            os.symlink(victim, syml)
            hlink = sub / "hard.json"
            os.link(victim, hlink)
            fifo = sub / "f.fifo"
            os.mkfifo(fifo)

            good = sub / "cert.json"
            ver.atomic_write_nofollow(good, b'{"ok": 1}\n')
            old_cwd_v = os.getcwd()
            os.chdir(sub)
            try:
                self.assertEqual(ver.read_nofollow_bytes("cert.json"), b'{"ok": 1}\n')
            finally:
                os.chdir(old_cwd_v)
            self.assertEqual(ver.read_nofollow_bytes(good, max_bytes=10), b'{"ok": 1}\n')
            self._assert_err(ver.VerifierError, "FILE_TOO_BIG", lambda: ver.read_nofollow_bytes(good, max_bytes=9))
            os.chmod(good, 0o600)
            ver.atomic_write_nofollow(good, b'{"ok": 2}\n')
            self.assertEqual(stat.S_IMODE(os.lstat(good).st_mode), 0o600)

            for bad_p, r_c, w_c in [
                (123, "BAD_PATH_TYPE", "BAD_PATH_TYPE"),
                ("", "BAD_PATH", "BAD_PATH"),
                ("a\x00b", "BAD_PATH", "BAD_PATH"),
                ("/", "BAD_LEAF", "BAD_LEAF"),
                (symd / ".." / "victim.json", "DOTDOT_FORBIDDEN", "DOTDOT_FORBIDDEN"),
                (symd / "x.json", "PARENT_OPEN", "PARENT_OPEN"),
                (syml, "OPEN_FAILED", "WRITE_NOT_REG"),
                (hlink, "HARDLINK_REJECTED", "WRITE_HARDLINK"),
                (fifo, "NOT_REG_FILE", "WRITE_NOT_REG"),
                (sub, "NOT_REG_FILE", "WRITE_NOT_REG"),
            ]:
                self._assert_err(ver.VerifierError, r_c, lambda bp=bad_p: ver.read_nofollow_bytes(bp))  # type: ignore[arg-type]
                self._assert_err(ver.VerifierError, w_c, lambda bp=bad_p: ver.atomic_write_nofollow(bp, b'{"pwn": 1}\n'))  # type: ignore[arg-type]
            self.assertEqual(victim.read_bytes(), b'{"stay": 1}\n')

            with mock.patch("os.lstat", side_effect=OSError(errno.EACCES, "denied")):
                self._assert_err(ver.VerifierError, "WRITE_LSTAT", lambda: ver.atomic_write_nofollow(good, b'{"x":1}\n'))
            with mock.patch("os.write", side_effect=[0, OSError(errno.EIO, "stop")]):
                self._assert_err(ver.VerifierError, "WRITE_ZERO", lambda: ver.atomic_write_nofollow(sub / "z.json", b'{"x":1}\n'))
            real_fs = os.fsync
            fc = [0]

            def _fs_err(eno: int) -> Any:
                def _inner(fd_i: int) -> None:
                    fc[0] += 1
                    if fc[0] == 2:
                        raise OSError(eno, "err")
                    real_fs(fd_i)
                return _inner

            fc[0] = 0
            with mock.patch("os.fsync", side_effect=_fs_err(errno.EINVAL)):
                ver.atomic_write_nofollow(sub / "e1.json", b'{"x":1}\n')
            fc[0] = 0
            with mock.patch("os.fsync", side_effect=_fs_err(errno.EIO)):
                self._assert_err(ver.VerifierError, "DIR_FSYNC", lambda: ver.atomic_write_nofollow(sub / "e2.json", b'{"x":1}\n'))
            if os.geteuid() != 0:
                ro_d = tmp / "ro_v"
                ro_d.mkdir()
                os.chmod(ro_d, 0o555)
                try:
                    self._assert_err(ver.VerifierError, "WRITE_IO", lambda: ver.atomic_write_nofollow(ro_d / "x.json", b'{"x":1}\n'))
                finally:
                    os.chmod(ro_d, 0o755)

        # Verifier distinct tokenizing Lean 4.36.0 static auditor (HIGH-1 + MED-2 + MED-4 + LOW-1)
        self.assertEqual(
            ver.audit_lean_static("namespace A.B\nsection\ndef g := «»«»\nend\ntheorem\n  t1 : 1 = 1 := rfl\nend B\ntheorem t2 : 1 = 1 := rfl\nend A\n"),
            ["A.B.t1", "A.t2"],
        )
        self.assertEqual(
            ver.audit_lean_static("namespace A.B\ntheorem t1 : 1 = 1 := rfl\nend A.B\ntheorem t2 : 1 = 1 := rfl\n"),
            ["A.B.t1", "t2"],
        )
        self.assertIn("theorem t1", ver.strip_lean_comments("-- hi\ntheorem t1 : 1 = 1 := rfl\n"))
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("no lean")):
            self._assert_err(ver.VerifierError, "LEAN_EXEC_FAILED", lambda: ver._default_lean_runner(["lean"], TRACK_DIR, 10))
        with tempfile.TemporaryDirectory(prefix="s168_velf_") as vh_s:
            vh = Path(vh_s)
            fake_pw = mock.Mock(pw_dir=str(vh))
            tbin = vh / ".elan" / "toolchains" / "leanprover--lean4---v4.36.0" / "bin"
            with mock.patch("pwd.getpwuid", return_value=fake_pw):
                self._assert_err(ver.VerifierError, "LEAN_EXEC_FAILED", ver._resolve_verified_elf_lean)
                tbin.mkdir(parents=True)
                (tbin / "lean").write_bytes(b"\x7fELF\x00\x00")
                (tbin / "lake").write_bytes(b"\x7fELF\x00\x00")
                os.chmod(tbin / "lean", 0o644)
                os.chmod(tbin / "lake", 0o755)
                self._assert_err(ver.VerifierError, "LEAN_TOOL_UNTRUSTED", ver._resolve_verified_elf_lean)
                (tbin / "lean").write_bytes(b"#!/bin/sh\n")
                os.chmod(tbin / "lean", 0o755)
                self._assert_err(ver.VerifierError, "LEAN_TOOL_UNTRUSTED", ver._resolve_verified_elf_lean)

        for bad_lean in [
            'def bad! (s : String) : Nat := s.length\ndef f : Nat := bad! "{"\nset_option debug.skipKernelTC true\naxiom evil : False\ndef g : String := "}"\ntheorem t : False := evil\n',
            'namespace Demo\ndef throwError (s : String) : Nat := s.length\ndef f : Nat := throwError "{"\nmacro_rules | `($_ < $_) => `(True)\ndef g : String := "}"\ntheorem t1 : 1 < 0 := trivial\nend Demo\n',
            'namespace Demo\ndef m! (s : String) : Nat := s.length\ndef f : Nat := m! "{"\nset_option debug.skipKernelTC true\nnotation "impossible_false" => True\ndef g : String := "}"\ntheorem t1 : impossible_false := trivial\nend Demo\n',
            'def throwErrorAt (n : Nat) (s : String) : Nat := s.length + n\ndef f : Nat := throwErrorAt 1 "{"\n',
            'def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt s!"a" "{"\n',
            'def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt s!"{1 + 2}" "{"\n',
            'def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt (s!"{1 + 2}") "{"\n',
            'def throwErrorAt (a : String) (b : String) : Nat := a.length + b.length\ndef f : Nat := throwErrorAt r#"a"# "{"\n',
            "def throwErrorAt (a : Char) (b : String) : Nat := a.toNat + b.length\ndef f : Nat := throwErrorAt 'a' \"{\"\n",
            'def logInfoAt (n : Nat) (s : String) : Nat := n + s.length\ndef f : Nat := logInfoAt 1 "{"\n',
            'def logWarningAt (n : Nat) (s : String) : Nat := n + s.length\ndef f : Nat := logWarningAt 1 "{"\n',
            'def logErrorAt (n : Nat) (s : String) : Nat := n + s.length\ndef f : Nat := logErrorAt 1 "{"\n',
            'def logAt (n : Nat) (s : String) : Nat := n + s.length\ndef f : Nat := logAt 1 "{"\n',
            'def «debug.skipKernelTC» : Nat := 1\n',
            'def «Lean.Elab» : Nat := 1\n',
            'def f : Nat := m! "\\{"\n',
            'theorem t1 : 1 = 1 := by dbg_trace "{"; rfl\n',
            'theorem p : 1 = 1 := by\n  open Nat in\n  rfl\n  stop\n  exact rfl\n',
            'def x := Lean.Elab.Command.elabCommand\n',
            'def x := Lean.Meta.mkFreshExprMVar\n',
            'def a : Char := \'"\'\ntheorem p : False := by sorry\ndef b : Char := \'"\'\n',
            'def a := r#" " "#\ntheorem p : False := by sorry\ndef b := r#" " "#\n',
            'theorem p : 1 = 1 := by decide (config := { native := true })\n',
            'theorem p : 1 = 1 := by decide (native := (true))\n',
            'theorem p : False := by\n  rfl\n  stop\n',
            'infixl:65 " ++ " => Nat.add\n',
            'set_option debug.proofAsSorry true\n',
            'set_option debug.terminalTacticsAsSorry true\n',
            'opaque bad_o : Nat\n',
            'instance : Inhabited Nat := ⟨0⟩\n',
            'def x := !s!"{ "/-" }"\ntheorem p : False := by sorry\n',
            'theorem p : False := by stop\n',
            'theorem p : False := _root_.«sorryAx» False true\n',
            'theorem p : 1 = 1 := by decide +native\n',
            '@[\nextern "x"\n]\ndef f : Nat := 0\n',
            'attribute [implemented_by foo] bar\n',
            'set_option debug.byAsSorry true\n',
            'variable (h : False)\ninclude h\ntheorem p : False := h\n',
            'partial def loop : Nat := loop\n',
            '#eval 1\n',
            'import Mathlib\n',
            '/- unterminated',
            'def s := "unterminated',
            'def s := r#"unterminated',
            'def s := s!"unterminated',
            'def «bad := 1\n',
        ]:
            with self.assertRaises(ver.VerifierError, msg=f"verifier missed {bad_lean!r}"):
                ver.audit_lean_static(bad_lean)

        # Real live Lean 4.36.0 verification via verify_lean_bundle(live_lean=True) (LOW-6, LOW-7)
        if not _SKIP_LIVE_LEAN:
            lb_real = ver.verify_lean_bundle(TRACK_DIR, live_lean=True)
            self.assertEqual(lb_real["lean_static_status"], "STATIC_PASS")
            self.assertEqual(lb_real["lean_live_mode"], "LIVE_LEAN_4_36_0_PASS")
            self.assertTrue(lb_real["live_lean_checked"])
            self.assertEqual(lb_real["axioms_verified_count"], 14)
            self.assertEqual(lb_real["zero_axiom_theorems"], 2)
            self.assertEqual(lb_real["propext_only_theorems"], 1)
            self.assertEqual(lb_real["propext_quot_theorems"], 11)

        # Offline verify_lean_bundle MUST NOT fabricate 2/1/11 (HIGH-2)
        lb_static = ver.verify_lean_bundle(TRACK_DIR, live_lean=False)
        self.assertEqual(lb_static["lean_static_status"], "STATIC_PASS")
        self.assertEqual(lb_static["lean_live_mode"], "STATIC_ONLY")
        self.assertFalse(lb_static["live_lean_checked"])
        self.assertEqual(lb_static["axioms_verified_count"], 0)
        self.assertIsNone(lb_static["zero_axiom_theorems"])
        self.assertIsNone(lb_static["propext_only_theorems"])
        self.assertIsNone(lb_static["propext_quot_theorems"])

        for bad_r, exp_c in [
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, version_out=b"\xff"), "LIVE_LEAN_UTF8"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, version_out=b"Lean (version 4.36.0-rc1)\n"), "LEAN_VER_BAD"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, build_rc=1), "LAKE_BUILD_BAD"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, build_out=b"VelocityBounds.lean:1:0: warning: unused\n"), "LAKE_BUILD_WARNING"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, build_err=b"\xff"), "LIVE_LEAN_UTF8"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, axiom_rc=1), "AXIOM_EXEC_BAD"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, axiom_override=b"\xff"), "LIVE_LEAN_UTF8"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, axiom_override=b"bad line\n"), "AXIOM_LINE_BAD"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, axiom_override=b"'VelocityBounds.pass2_dedup_bool_union_exact' does not depend on any axioms\n'VelocityBounds.pass2_dedup_bool_union_exact' does not depend on any axioms\n"), "AXIOM_DUP_THEOREM"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, axiom_override=b"'VelocityBounds.pass2_dedup_zero_evals_when_subset' depends on axioms: [propext]\n'VelocityBounds.pass2_dedup_zero_evals_when_subset' depends on axioms: [propext]\n"), "AXIOM_DUP_THEOREM"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, axiom_override=("\n".join(
                f"'{t}' does not depend on any axioms" if t in ver.EXPECTED_ZERO_AXIOM_THEOREMS
                else (f"'{t}' depends on axioms: [propext]" if t in ver.EXPECTED_PROPEXT_ONLY_THEOREMS
                      else (f"'{t}' depends on axioms: [Quot.sound]" if t == ver.EXPECTED_THEOREMS[0]
                            else f"'{t}' depends on axioms: [propext, Quot.sound]"))
                for t in ver.EXPECTED_THEOREMS
            ) + "\n").encode("utf-8")), "AXIOM_PARTITION_MISMATCH"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS, axiom_override=b"'VelocityBounds.two_stage_expected_time_strict_accel_iff' depends on axioms: [Classical.choice]\n"), "FORBIDDEN_AXIOM"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS[:1], ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS), "AXIOM_SET_MISMATCH"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, frozenset(), ver.EXPECTED_PROPEXT_ONLY_THEOREMS), "ZERO_AX_SPLIT_MISMATCH"),
            (_mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, frozenset()), "PROPEXT_SPLIT_MISMATCH"),
        ]:
            self._assert_err(ver.VerifierError, exp_c, lambda br=bad_r: ver.verify_lean_bundle(TRACK_DIR, live_lean=True, runner=br))

    def test_06_verifier_cert_empirical_and_cli(self) -> None:
        # Pillar 1 math: exact dual_accel_stage2 threshold_q == "17/6" + dynamic break-even + measured LOC bound to Lean T14 (MED-3, LOW-4)
        m = ver.verify_pillar1_math(trust_core_nonempty_loc=1200, expected_lean_trust_core_loc=1200, expected_lean_be_n=4, expected_lean_n6_saved=1200)
        self.assertEqual(m["failfast_exhaustive_vectors"], 255)
        self.assertEqual(m["failfast_strict_savings_vectors"], 240)
        self.assertEqual(m["trust_core_breakeven_n"], 2)
        self.assertEqual(m["trust_core_n6_loc_saved"], 1860)
        self.assertEqual(m["measured_trust_core_breakeven_n"], 4)
        self.assertEqual(m["measured_trust_core_n6_loc_saved"], 1200)
        dual_row = [r for r in m["two_stage_grid"] if r["case_id"] == "dual_accel_stage2"][0]
        self.assertEqual(dual_row["threshold_q"], "17/6")

        # LOW-4 exact physical domain bounds (`t1 == 0`, `psurv == 0`, `psurv == 1` pass when t_exp > 0; negative / >1 / t_exp == 0 reject)
        ver.verify_pillar1_math(two_stage_cases=[
            ("zero_t1", 0, 180, 180, Fraction(1, 2), True),
            ("zero_p", 10, 180, 180, Fraction(0, 1), True),
            ("p1_tie", 0, 180, 180, Fraction(1, 1), False),
        ])
        self._assert_err(ver.VerifierError, "MATH_TWO_STAGE_DOMAIN", lambda: ver.verify_pillar1_math(two_stage_cases=[("zero_texp", 0, 180, 180, Fraction(0, 1), True)]))
        self._assert_err(ver.VerifierError, "MATH_TWO_STAGE_DOMAIN", lambda: ver.verify_pillar1_math(two_stage_cases=[("bad_t2", 10, 0, 180, Fraction(1, 3), True)]))
        self._assert_err(ver.VerifierError, "MATH_TWO_STAGE_DOMAIN", lambda: ver.verify_pillar1_math(two_stage_cases=[("bad_t1", -1, 180, 180, Fraction(1, 3), True)]))
        self._assert_err(ver.VerifierError, "MATH_TWO_STAGE_DOMAIN", lambda: ver.verify_pillar1_math(two_stage_cases=[("bad_p_neg", 10, 180, 180, Fraction(-1, 2), True)]))
        self._assert_err(ver.VerifierError, "MATH_TWO_STAGE_DOMAIN", lambda: ver.verify_pillar1_math(two_stage_cases=[("bad_p_gt1", 10, 180, 180, Fraction(3, 2), False)]))
        self._assert_err(ver.VerifierError, "MATH_TWO_STAGE_BAD", lambda: ver.verify_pillar1_math(two_stage_cases=[("bad", 10, 180, 180, Fraction(1, 3), False)]))
        self._assert_err(ver.VerifierError, "MATH_DEDUP_COUNT_BAD", lambda: ver.verify_pillar1_math(dedup_cases=[([1, 2], [1, 2], 1)]))
        self._assert_err(ver.VerifierError, "MATH_DEDUP_SET_BAD", lambda: ver.verify_pillar1_math(dedup_cases=[([1], [2], 0)], dedup_eval=lambda k1, m2: []))
        self.assertEqual(ver.verify_pillar1_math(failfast_max_len=0)["failfast_exhaustive_vectors"], 1)
        self._assert_err(ver.VerifierError, "MATH_FF_MAX_LEN_BAD", lambda: ver.verify_pillar1_math(failfast_max_len=-1))
        self._assert_err(ver.VerifierError, "MATH_FF_EQUIV_BAD", lambda: ver.verify_pillar1_math(failfast_max_len=1, failfast_eval=lambda v: (True, len(v))))
        self._assert_err(ver.VerifierError, "MATH_FF_BOUND_BAD", lambda: ver.verify_pillar1_math(failfast_max_len=1, failfast_eval=lambda v: (any(not r for r in v), len(v) + 1)))
        self._assert_err(ver.VerifierError, "MATH_FF_STRICT_BAD", lambda: ver.verify_pillar1_math(failfast_max_len=2, failfast_eval=lambda v: (any(not r for r in v), len(v))))
        # Exact amortization boundary equality: c_core=400, b_dup=420, b_drop=20 -> N=1 exact tie (420 == 420), N=2 strict win!
        ver.verify_pillar1_math(amort_params=(400, 420, 20, 2000))
        self._assert_err(ver.VerifierError, "MATH_AMORT_PREV_BAD", lambda: ver.verify_pillar1_math(amort_params=(400, 420, 20, 2000), breakeven_override=3))
        self._assert_err(ver.VerifierError, "MATH_AMORT_BE_BAD", lambda: ver.verify_pillar1_math(amort_params=(400, 420, 20, 2000), breakeven_override=1))
        self._assert_err(ver.VerifierError, "MATH_AMORT_GAIN_BAD", lambda: ver.verify_pillar1_math(amort_params=(540, 20, 20, 0)))
        self._assert_err(ver.VerifierError, "MATH_AMORT_N6_BAD", lambda: ver.verify_pillar1_math(amort_params=(540, 420, 20, 999)))
        self._assert_err(ver.VerifierError, "MATH_PREFLIGHT_SAVED_BAD", lambda: ver.verify_pillar1_math(preflight_params=(2, 900, 3, 1, 999)))
        self._assert_err(ver.VerifierError, "MATH_LOC_BAD", lambda: ver.verify_pillar1_math(trust_core_nonempty_loc=0))
        self._assert_err(ver.VerifierError, "MATH_LOC_LEAN_MISMATCH", lambda: ver.verify_pillar1_math(trust_core_nonempty_loc=1436, expected_lean_trust_core_loc=1394))
        self._assert_err(ver.VerifierError, "MATH_MEAS_AMORT_PREV_BAD", lambda: ver.verify_pillar1_math(trust_core_nonempty_loc=1200, expected_lean_be_n=5))
        self._assert_err(ver.VerifierError, "MATH_MEAS_AMORT_BE_BAD", lambda: ver.verify_pillar1_math(trust_core_nonempty_loc=1200, expected_lean_be_n=3))
        self._assert_err(ver.VerifierError, "MATH_MEAS_N6_MISMATCH", lambda: ver.verify_pillar1_math(trust_core_nonempty_loc=1200, expected_lean_n6_saved=999))
        self._assert_err(ver.VerifierError, "LEAN_TC_WITNESS_MISSING", lambda: ver._extract_lean_trust_core_witness("theorem t : 1 = 1 := rfl\n"))
        self._assert_err(
            ver.VerifierError,
            "LEAN_TC_WITNESS_INCONSISTENT",
            lambda: ver._extract_lean_trust_core_witness("(3 * 420 ≤ 1436 + 3 * 20) ∧ (1394 + 4 * 20 < 4 * 420) ∧ (6 * 420 - (1436 + 6 * 20) = 964)\n"),
        )

        # Isolated copy of TRACK_DIR with writable copies (MED-1 RO snapshot safe!) and synthetic fresh s168_ab_results.json
        with tempfile.TemporaryDirectory(prefix="s168_cert_") as tmp_s:
            tmp = Path(tmp_s)
            for fname in (
                "trust_core.py", "preflight.py", "fast_mutate.py", "s168_velocity_bench.py",
                "verify_s168_velocity.py", "test_s168_velocity_r5.py",
                "VelocityBounds.lean", "lean-toolchain", "lakefile.toml", "lake-manifest.json",
            ):
                _copy_writable(TRACK_DIR / fname, tmp / fname)

            # Sync synthetic tmp VelocityBounds.lean witness if trust_core.py was re-formatted by ast.unparse during null-mutant
            tmp_tc_loc = sum(1 for ln in (tmp / "trust_core.py").read_text(encoding="utf-8").splitlines() if ln.strip())
            vb_p = tmp / "VelocityBounds.lean"
            vb_txt = vb_p.read_text(encoding="utf-8")
            lean_c_cur, _, _ = ver._extract_lean_trust_core_witness(vb_txt)
            if tmp_tc_loc != lean_c_cur:
                tmp_be = (tmp_tc_loc // 400) + 1
                tmp_n6 = 6 * 420 - (tmp_tc_loc + 6 * 20)
                vb_txt = ver._LEAN_TC_WITNESS_RE.sub(
                    f"({tmp_be - 1} * 420 ≤ {tmp_tc_loc} + {tmp_be - 1} * 20) ∧\n"
                    f"    ({tmp_tc_loc} + {tmp_be} * 20 < {tmp_be} * 420) ∧\n"
                    f"    (6 * 420 - ({tmp_tc_loc} + 6 * 20) = {tmp_n6})",
                    vb_txt,
                    count=1,
                )
                vb_p.write_text(vb_txt, encoding="utf-8", newline="\n")

            bench_p = tmp / "s168_velocity_bench.py"
            res_p = tmp / "s168_ab_results.json"
            bench_sha = ver._sha256(bench_p.read_bytes())
            eng_shas = {fn: ver._sha256((tmp / fn).read_bytes()) for fn in ver.ENGINE_SOURCE_FILES}
            orig_res = _make_sample_ab_results(bench_sha, eng_shas)
            ver.atomic_write_nofollow(res_p, ver._canon_bytes(orig_res))
            b_ns = max(os.lstat(tmp / fn).st_mtime_ns for fn in ("s168_velocity_bench.py", *ver.ENGINE_SOURCE_FILES))
            r_ns = b_ns + 10_000_000_000
            os.utime(res_p, ns=(r_ns, r_ns))

            cert_p = tmp / "s168_velocity_certificate.json"
            mock_ok = _mock_lean_runner_ok(ver.EXPECTED_THEOREMS, ver.EXPECTED_ZERO_AXIOM_THEOREMS, ver.EXPECTED_PROPEXT_ONLY_THEOREMS)

            # Static cert passes offline --check AND online --check --live-lean (HIGH-2 S166 Delta-6 pattern)
            built_static = ver.build_certificate(tmp, live_lean=False)
            # MED-3: adding 1 non-empty line to trust_core.py without updating VelocityBounds.lean MUST fail closed!
            orig_tc_bytes = (tmp / "trust_core.py").read_bytes()
            (tmp / "trust_core.py").write_bytes(orig_tc_bytes + b"# extra_nonempty_line\n")
            self._assert_err(ver.VerifierError, "MATH_LOC_LEAN_MISMATCH", lambda: ver.build_certificate(tmp, live_lean=False))
            (tmp / "trust_core.py").write_bytes(orig_tc_bytes)
            os.utime(tmp / "trust_core.py", ns=(b_ns - 1_000_000_000, b_ns - 1_000_000_000))
            ver.atomic_write_nofollow(cert_p, ver._canon_bytes(built_static))
            checked_off = ver.verify_certificate_file(cert_p, tmp, live_lean=False)
            self.assertEqual(checked_off["payload_sha256"], built_static["payload_sha256"])
            checked_on = ver.verify_certificate_file(cert_p, tmp, live_lean=True, runner=mock_ok)
            self.assertTrue(checked_on["lean_bundle"]["live_lean_checked"])
            self.assertEqual(checked_on["lean_bundle"]["lean_live_mode"], "LIVE_LEAN_4_36_0_PASS")

            # HIGH-2 FORGERY TEST: Forged LIVE_LEAN_4_36_0_PASS cert with valid recomputed payload_sha256 MUST FAIL offline!
            built_live = ver.build_certificate(tmp, live_lean=True, runner=mock_ok)
            live_cert_p = tmp / "live_cert.json"
            ver.atomic_write_nofollow(live_cert_p, ver._canon_bytes(built_live))
            self._assert_err(ver.VerifierError, "LEAN_LIVE_STATUS_MISMATCH", lambda: ver.verify_certificate_file(live_cert_p, tmp, live_lean=False))
            # Online --live-lean accepts valid live cert, and rejects tampered/non-canonical static/live/bad-type certs
            self.assertEqual(ver.verify_certificate_file(live_cert_p, tmp, live_lean=True, runner=mock_ok)["payload_sha256"], built_live["payload_sha256"])

            no_lb_p = tmp / "no_lb.json"
            ver.atomic_write_nofollow(no_lb_p, ver._canon_bytes({"lean_bundle": "bad"}))
            self._assert_err(ver.VerifierError, "CERT_MISMATCH", lambda: ver.verify_certificate_file(no_lb_p, tmp, live_lean=False))
            bad_lc_p = tmp / "bad_lc.json"
            bad_lc = json.loads(live_cert_p.read_text(encoding="utf-8"))
            bad_lc["lean_bundle"]["live_lean_checked"] = "yes"
            ver.atomic_write_nofollow(bad_lc_p, ver._canon_bytes(bad_lc))
            self._assert_err(ver.VerifierError, "LEAN_LIVE_STATUS_MISMATCH", lambda: ver.verify_certificate_file(bad_lc_p, tmp, live_lean=True, runner=mock_ok))
            bad_live_p = tmp / "bad_live.json"
            bad_live = json.loads(live_cert_p.read_text(encoding="utf-8"))
            bad_live["track"] = "TAMPERED"
            ver.atomic_write_nofollow(bad_live_p, ver._canon_bytes(bad_live))
            self._assert_err(ver.VerifierError, "CERT_MISMATCH", lambda: ver.verify_certificate_file(bad_live_p, tmp, live_lean=True, runner=mock_ok))
            nc_live_p = tmp / "nc_live.json"
            nc_live_p.write_text(json.dumps(built_live) + "\n", encoding="utf-8", newline="\n")
            self._assert_err(ver.VerifierError, "CERT_NON_CANONICAL", lambda: ver.verify_certificate_file(nc_live_p, tmp, live_lean=True, runner=mock_ok))

            # bool-for-int spoof in certificate MUST fail with CERT_MISMATCH (both offline and online)
            spoof = json.loads(cert_p.read_text(encoding="utf-8"))
            spoof["math_velocity_bounds"]["trust_core_breakeven_n"] = True
            spoof_p = tmp / "spoof.json"
            ver.atomic_write_nofollow(spoof_p, ver._canon_bytes(spoof))
            self._assert_err(ver.VerifierError, "CERT_MISMATCH", lambda: ver.verify_certificate_file(spoof_p, tmp, live_lean=False))
            self._assert_err(ver.VerifierError, "CERT_MISMATCH", lambda: ver.verify_certificate_file(spoof_p, tmp, live_lean=True, runner=mock_ok))

            noncanon_p = tmp / "noncanon.json"
            noncanon_p.write_text(json.dumps(built_static) + "\n", encoding="utf-8", newline="\n")
            self._assert_err(ver.VerifierError, "CERT_NON_CANONICAL", lambda: ver.verify_certificate_file(noncanon_p, tmp, live_lean=False))
            self._assert_err(ver.VerifierError, "CERT_NON_CANONICAL", lambda: ver.verify_certificate_file(noncanon_p, tmp, live_lean=True, runner=mock_ok))

            list_p = tmp / "list.json"
            list_p.write_text("[]\n", encoding="utf-8", newline="\n")
            self._assert_err(ver.VerifierError, "CERT_NOT_DICT", lambda: ver.verify_certificate_file(list_p, tmp, live_lean=False))

            # Tampered s168_ab_results.json incl. stale bench/engine (exact equal mtime!), bool-for-int, median mismatch
            os.utime(res_p, ns=(os.lstat(bench_p).st_mtime_ns, os.lstat(bench_p).st_mtime_ns))
            self._assert_err(ver.VerifierError, "EMPIRICAL_STALE", lambda: ver.verify_empirical_ab_results(tmp))
            os.utime(res_p, ns=(r_ns, r_ns))
            tc_orig_ns = os.lstat(tmp / "trust_core.py").st_mtime_ns
            os.utime(tmp / "trust_core.py", ns=(r_ns, r_ns))
            self._assert_err(ver.VerifierError, "EMPIRICAL_STALE_ENGINE", lambda: ver.verify_empirical_ab_results(tmp))
            os.utime(tmp / "trust_core.py", ns=(tc_orig_ns, tc_orig_ns))

            # Exact 3000 (w8 vs base w1) and 2000 (w1 vs w1) boundaries MUST pass
            d_exact = json.loads(json.dumps(orig_res))
            d_exact["mutate_ab_benchmark"]["baseline_aletheia_w1"]["elapsed_ms"] = 6000
            d_exact["mutate_ab_benchmark"]["baseline_aletheia_w1"]["trial_elapsed_ms"] = [6000, 6000, 6000]
            d_exact["mutate_ab_benchmark"]["fast_mutate_w1"]["elapsed_ms"] = 3000
            d_exact["mutate_ab_benchmark"]["fast_mutate_w1"]["trial_elapsed_ms"] = [3000, 3000, 3000]
            d_exact["mutate_ab_benchmark"]["fast_mutate_w1"]["speedup_q"] = "2"
            d_exact["mutate_ab_benchmark"]["fast_mutate_w1"]["speedup_milli"] = 2000
            d_exact["mutate_ab_benchmark"]["fast_mutate_w8"]["elapsed_ms"] = 2000
            d_exact["mutate_ab_benchmark"]["fast_mutate_w8"]["trial_elapsed_ms"] = [2000, 2000, 2000]
            d_exact["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_q"] = "3"
            d_exact["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_milli"] = 3000
            ver.atomic_write_nofollow(res_p, ver._canon_bytes(d_exact))
            os.utime(res_p, ns=(r_ns, r_ns))
            ev_ex = ver.verify_empirical_ab_results(tmp)
            self.assertEqual(ev_ex["speedup_w8_vs_base_w1_milli"], 3000)
            self.assertEqual(ev_ex["speedup_w1_vs_w1_milli"], 2000)

            def _tamper_res(mutator: Any, exp_code: str) -> None:
                d = json.loads(json.dumps(orig_res))
                d2 = mutator(d)
                ver.atomic_write_nofollow(res_p, ver._canon_bytes(d if d2 is None else d2))
                os.utime(res_p, ns=(r_ns, r_ns))
                self._assert_err(ver.VerifierError, exp_code, lambda: ver.verify_empirical_ab_results(tmp))

            _tamper_res(lambda d: [], "EMPIRICAL_ROOT")
            _tamper_res(lambda d: d.__setitem__("schema", "bad.schema"), "EMPIRICAL_SCHEMA")
            _tamper_res(lambda d: d.__setitem__("cpu_only", False), "EMPIRICAL_CPU_ONLY")
            _tamper_res(lambda d: d.__setitem__("bench_script_sha256", "0" * 64), "EMPIRICAL_BENCH_SHA")
            _tamper_res(lambda d: d.__setitem__("engine_source_sha256", None), "EMPIRICAL_ENGINE_SHAS_MISSING")
            _tamper_res(lambda d: d["engine_source_sha256"].__setitem__("evil_extra.py", "0" * 64), "EMPIRICAL_ENGINE_KEYS")
            _tamper_res(lambda d: d["engine_source_sha256"].__setitem__("trust_core.py", "0" * 64), "EMPIRICAL_ENGINE_SHA")
            _tamper_res(lambda d: d.__setitem__("preflight_live", None), "EMPIRICAL_PF_MISSING")
            _tamper_res(lambda d: d["preflight_live"].__setitem__("all_under_2000ms", False), "EMPIRICAL_PF_SLOW")
            _tamper_res(lambda d: d["preflight_live"].__setitem__("synthetic_caught_count", 4), "EMPIRICAL_PF_CATCH")
            _tamper_res(lambda d: d["preflight_live"]["synthetic_fixtures"][0].__setitem__("caught", False), "EMPIRICAL_PF_FIXTURES")
            _tamper_res(lambda d: d["preflight_live"]["synthetic_fixtures"][0].__setitem__("codes_detected", []), "EMPIRICAL_PF_FIXTURES")
            _tamper_res(lambda d: d["preflight_live"]["synthetic_fixtures"][0].__setitem__("elapsed_ms", 2000), "EMPIRICAL_PF_FIXTURES")
            _tamper_res(lambda d: d["preflight_live"]["synthetic_fixtures"][0].__setitem__("elapsed_ms", -1), "EMPIRICAL_PF_FIXTURES")
            _tamper_res(lambda d: d["preflight_live"]["synthetic_fixtures"][1].__setitem__("fixture", "F1"), "EMPIRICAL_PF_FIXTURES")
            _tamper_res(lambda d: d["preflight_live"]["s161_snapshot"].__setitem__("finding_count", False), "EMPIRICAL_S161_PF")
            _tamper_res(lambda d: d["preflight_live"]["s161_snapshot"].__setitem__("lean_unique_theorems", 0), "EMPIRICAL_S161_PF")
            _tamper_res(lambda d: d["preflight_live"]["s161_snapshot"].__setitem__("files_scanned", 0), "EMPIRICAL_S161_PF")
            _tamper_res(lambda d: d["preflight_live"]["s166_snapshot"].__setitem__("finding_count", 1), "EMPIRICAL_S166_PF")
            _tamper_res(lambda d: d["preflight_live"]["s166_snapshot"].__setitem__("finding_codes", []), "EMPIRICAL_S166_PF")
            _tamper_res(lambda d: d["preflight_live"]["s166_snapshot"].__setitem__("files_scanned", 0), "EMPIRICAL_S166_PF")
            _tamper_res(lambda d: d["preflight_live"]["s166_snapshot"].__setitem__("lean_unique_theorems", 0), "EMPIRICAL_S166_PF")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass1_survived", 0), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass1_total", 99), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass2_total", 99), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass2_new_sites", 99), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass2_dedup_skipped", 0), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass2_dedup_skipped", 1), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass2_dedup_skipped", 3), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass2_dedup_skipped", 999), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("fast_arm_entrypoint", "bogus"), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mixed_parity_check"].__setitem__("pass2_mutant_set_sha256", "a" * 64), "EMPIRICAL_MIXED_PARITY")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("parity_exact_100pct", False), "EMPIRICAL_AB_PARITY")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("target_script", "fake_target.py"), "EMPIRICAL_AB_TARGET")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("target_script_sha256", "0" * 64), "EMPIRICAL_AB_TARGET")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("staged_from_chmod_aw_ro_copy", False), "EMPIRICAL_AB_PROVENANCE")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("mutated_in_isolated_writable_slots", False), "EMPIRICAL_AB_PROVENANCE")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("source_track_untouched", False), "EMPIRICAL_AB_PROVENANCE")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("pass2_mutant_set_sha256", "0" * 64), "EMPIRICAL_AB_SET_SHA")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("cli_entrypoint_both_arms", False), "EMPIRICAL_AB_CLI")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("trials", 1), "EMPIRICAL_AB_TRIALS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("trials", 4), "EMPIRICAL_AB_TRIALS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("trial_arm_orders", [["baseline_w1", "fast_w1", "baseline_w8", "baseline_w1"]] * 3), "EMPIRICAL_AB_ORDERS")
            # Delta-5 LOW-1: previously-unpinned fields & identical permutations are now rejected
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("trial_arm_orders", [["fast_w8", "fast_w1", "baseline_w8", "baseline_w1"]] * 3), "EMPIRICAL_AB_ORDERS")
            _tamper_res(lambda d: d.__setitem__("host_cpu_count", -5), "EMPIRICAL_HOST_CPU")
            _tamper_res(lambda d: d.__setitem__("host_cpu_count", 0), "EMPIRICAL_HOST_CPU")
            _tamper_res(lambda d: d.__setitem__("host_cpu_count", True), "EMPIRICAL_HOST_CPU")
            _tamper_res(lambda d: d["preflight_live"]["s161_snapshot"].__setitem__("elapsed_ms", -1), "EMPIRICAL_S161_PF")
            _tamper_res(lambda d: d["preflight_live"]["s166_snapshot"].__setitem__("elapsed_ms", -1), "EMPIRICAL_S166_PF")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("rng_seed", 999), "EMPIRICAL_AB_CONFIG")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("pass2_guard", "fake_guard"), "EMPIRICAL_AB_CONFIG")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("test_cmd", "echo fake"), "EMPIRICAL_AB_CONFIG")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("fast_mutate_w8", None), "EMPIRICAL_AB_STRUCT")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("failfast_injected", False), "EMPIRICAL_AB_FAILFAST")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("failfast_injected", False), "EMPIRICAL_AB_FAILFAST")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["baseline_aletheia_w1"].__setitem__("elapsed_ms", True), d["mutate_ab_benchmark"]["baseline_aletheia_w1"].__setitem__("trial_elapsed_ms", [1, 1, 1])) and None, "EMPIRICAL_BASE_W1_MS")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["baseline_aletheia_w1"].__setitem__("elapsed_ms", 0), d["mutate_ab_benchmark"]["baseline_aletheia_w1"].__setitem__("trial_elapsed_ms", [0, 0, 0])) and None, "EMPIRICAL_BASE_W1_MS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["baseline_aletheia_w1"].__setitem__("trial_elapsed_ms", [1, 2, 3]), "EMPIRICAL_BASE_W1_MS")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("elapsed_ms", 0), d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("trial_elapsed_ms", [0, 0, 0])) and None, "EMPIRICAL_BASE_W8_MS")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("elapsed_ms", 0), d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("trial_elapsed_ms", [0, 0, 0])) and None, "EMPIRICAL_W1_MS")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("elapsed_ms", 0), d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("trial_elapsed_ms", [0, 0, 0])) and None, "EMPIRICAL_W8_MS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("bit_identical_mutant_set", False), "EMPIRICAL_AB_PARITY")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("workers", 99), "EMPIRICAL_AB_WORKERS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("workers", 99), "EMPIRICAL_AB_WORKERS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("workers", 1), "EMPIRICAL_AB_WORKERS")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("control_subprocess_evals", 999), d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("total_subprocess_evals", 1060)) and None, "EMPIRICAL_AB_CONTROLS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("pass1_killed", 60), "EMPIRICAL_AB_KILLS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("pass1_killed", 1), "EMPIRICAL_AB_KILLS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("pass2_killed", 1), "EMPIRICAL_AB_KILLS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("pass2_killed", 60), "EMPIRICAL_AB_KILLS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("pass2_killed", 0), "EMPIRICAL_AB_COUNTS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("total_subprocess_evals", 61), "EMPIRICAL_AB_COUNTS")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("mutant_subprocess_evals", 62), d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("total_subprocess_evals", 66)) and None, "EMPIRICAL_AB_COUNTS")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("mutant_subprocess_evals", 123), d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("total_subprocess_evals", 127)) and None, "EMPIRICAL_AB_COUNTS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("pass2_dedup_skipped", False), "EMPIRICAL_DEDUP_SKIP")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("pass2_dedup_skipped", 60), "EMPIRICAL_DEDUP_SKIP")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("pass1_total", 62), d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("pass1_killed", 62), d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("mutant_subprocess_evals", 123), d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("total_subprocess_evals", 127)) and None, "EMPIRICAL_AB_KILLS")
            _tamper_res(lambda d: (d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("pass2_total", 62), d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("pass2_killed", 62), d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("mutant_subprocess_evals", 123), d["mutate_ab_benchmark"]["baseline_aletheia_w8"].__setitem__("total_subprocess_evals", 127)) and None, "EMPIRICAL_AB_KILLS")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("speedup_q", "1/1"), "EMPIRICAL_W1_RATIO")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w1"].__setitem__("speedup_milli", 1), "EMPIRICAL_W1_MILLI")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("speedup_vs_base_w8_q", "1/1"), "EMPIRICAL_W8_ISO_RATIO")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("speedup_vs_base_w8_milli", 1), "EMPIRICAL_W8_ISO_MILLI")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("speedup_q", "1/1"), "EMPIRICAL_W8_RATIO")
            _tamper_res(lambda d: d["mutate_ab_benchmark"]["fast_mutate_w8"].__setitem__("speedup_milli", 1), "EMPIRICAL_W8_MILLI")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("mutant_eval_reduction_q", "1"), "EMPIRICAL_EVAL_RED")
            _tamper_res(lambda d: d["mutate_ab_benchmark"].__setitem__("total_eval_reduction_q", "1"), "EMPIRICAL_EVAL_RED")

            def _slow_w8(d: dict[str, Any]) -> None:
                d["mutate_ab_benchmark"]["baseline_aletheia_w1"]["elapsed_ms"] = 2000
                d["mutate_ab_benchmark"]["baseline_aletheia_w1"]["trial_elapsed_ms"] = [2000, 2000, 2000]
                d["mutate_ab_benchmark"]["fast_mutate_w1"]["elapsed_ms"] = 1000
                d["mutate_ab_benchmark"]["fast_mutate_w1"]["trial_elapsed_ms"] = [1000, 1000, 1000]
                d["mutate_ab_benchmark"]["fast_mutate_w1"]["speedup_q"] = "2"
                d["mutate_ab_benchmark"]["fast_mutate_w1"]["speedup_milli"] = 2000
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["elapsed_ms"] = 1000
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["trial_elapsed_ms"] = [1000, 1000, 1000]
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_vs_base_w8_q"] = "4"
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_vs_base_w8_milli"] = 4000
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_q"] = "2"
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_milli"] = 2000
            _tamper_res(_slow_w8, "EMPIRICAL_SPEEDUP_LOW")

            def _slow_w1(d: dict[str, Any]) -> None:
                d["mutate_ab_benchmark"]["baseline_aletheia_w1"]["elapsed_ms"] = 6000
                d["mutate_ab_benchmark"]["baseline_aletheia_w1"]["trial_elapsed_ms"] = [6000, 6000, 6000]
                d["mutate_ab_benchmark"]["fast_mutate_w1"]["elapsed_ms"] = 4000
                d["mutate_ab_benchmark"]["fast_mutate_w1"]["trial_elapsed_ms"] = [4000, 4000, 4000]
                d["mutate_ab_benchmark"]["fast_mutate_w1"]["speedup_q"] = "3/2"
                d["mutate_ab_benchmark"]["fast_mutate_w1"]["speedup_milli"] = 1500
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["elapsed_ms"] = 2000
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["trial_elapsed_ms"] = [2000, 2000, 2000]
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_q"] = "3"
                d["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_milli"] = 3000
            _tamper_res(_slow_w1, "EMPIRICAL_W1_SPEEDUP_LOW")

            # Restore valid results & test CLI incl. --help
            ver.atomic_write_nofollow(res_p, ver._canon_bytes(orig_res))
            os.utime(res_p, ns=(r_ns, r_ns))
            out_v, err_v = io.StringIO(), io.StringIO()
            with redirect_stdout(out_v), redirect_stderr(err_v):
                rc_h = ver.main(["--help"])
                rc_w = ver.main(["--track-dir", str(tmp), "--write", str(cert_p)])
                rc_c = ver.main(["--track-dir", str(tmp), "--check", str(cert_p)])
                rc_c_rel = ver.main(["--track-dir", str(tmp), "--check", "s168_velocity_certificate.json"])
                rc_abbr = ver.main(["--ch"])
                rc_bad = ver.main(["--track-dir", str(tmp), "--check", str(spoof_p)])
            self.assertEqual(rc_h, 0)
            self.assertEqual(rc_w, 0)
            self.assertEqual(rc_c, 0)
            self.assertEqual(rc_c_rel, 0)
            self.assertEqual(rc_abbr, 2)
            self.assertEqual(rc_bad, 2)
            for line in err_v.getvalue().strip().splitlines():
                self.assertEqual(json.loads(line)["status"], "ERROR")

            # Tampered Lean bundle files (exact error codes incl. lakefile.lean / srcDir / globs)
            (tmp / "lakefile.lean").write_text("import Lake\n", encoding="utf-8", newline="\n")
            self._assert_err(ver.VerifierError, "LAKEFILE_LEAN_FORBIDDEN", lambda: ver.verify_lean_bundle(tmp, live_lean=False))
            (tmp / "lakefile.lean").unlink()
            (tmp / "lean-toolchain").write_bytes(b"leanprover/lean4:v4.36.0\r\n")
            self._assert_err(ver.VerifierError, "LEAN_BUNDLE_CR", lambda: ver.verify_lean_bundle(tmp, live_lean=False))
            (tmp / "lean-toolchain").write_text("leanprover/lean4:v4.35.0\n", encoding="utf-8", newline="\n")
            self._assert_err(ver.VerifierError, "TOOLCHAIN_BAD", lambda: ver.verify_lean_bundle(tmp, live_lean=False))
            _copy_writable(TRACK_DIR / "lean-toolchain", tmp / "lean-toolchain")
            (tmp / "lake-manifest.json").write_text('{"packages":["bad"]}\n', encoding="utf-8", newline="\n")
            self._assert_err(ver.VerifierError, "MANIFEST_PKGS", lambda: ver.verify_lean_bundle(tmp, live_lean=False))
            _copy_writable(TRACK_DIR / "lake-manifest.json", tmp / "lake-manifest.json")
            for bad_toml, exp_code in [
                ('name = "bad name!"\n', "LAKEFILE_BAD_SCHEMA"),
                ('version = "bad-ver"\n', "LAKEFILE_BAD_SCHEMA"),
                ('defaultTargets = ["bad/t"]\n', "LAKEFILE_BAD_SCHEMA"),
                ('defaultTargets = ["venv.Evil"]\n', "LAKEFILE_BAD_SCHEMA"),
                ('lean_lib = 123\n', "LAKEFILE_BAD_SCHEMA"),
                ('lean_lib = [123]\n', "LAKEFILE_BAD_SCHEMA"),
                ('name = "VelocityBounds"\nmoreLeanArgs = []\n', "LAKEFILE_UNSAFE_KEY"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "VelocityBounds"\nmoreLeanArgs = []\n', "LAKEFILE_UNSAFE_KEY"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "bad/name"\n', "LAKEFILE_UNSAFE_ROOT"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "venv.Evil"\n', "LAKEFILE_UNSAFE_ROOT"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "VelocityBounds"\nsrcDir = ""\n', "LAKEFILE_UNSAFE_PATH"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "VelocityBounds"\nsrcDir = "a\\u0000b"\n', "LAKEFILE_UNSAFE_PATH"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "VelocityBounds"\nsrcDir = "../evil"\n', "LAKEFILE_UNSAFE_PATH"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "VelocityBounds"\nroots = ["venv.Evil"]\n', "LAKEFILE_UNSAFE_ROOT"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "VelocityBounds"\nroots = ["debug.skipKernelTC"]\n', "LAKEFILE_UNSAFE_STR"),
                ('name = "VelocityBounds"\n[[lean_lib]]\nname = "VelocityBounds"\nglobs = ["venv.*"]\n', "LAKEFILE_UNSAFE_GLOB"),
                ('[[broken\n', "LAKEFILE_TOML"),
            ]:
                (tmp / "lakefile.toml").write_text(bad_toml, encoding="utf-8", newline="\n")
                self._assert_err(ver.VerifierError, exp_code, lambda: ver.verify_lean_bundle(tmp, live_lean=False))
            _copy_writable(TRACK_DIR / "lakefile.toml", tmp / "lakefile.toml")
            (tmp / "VelocityBounds.lean").write_bytes(b"\xff\xfe\n")
            self._assert_err(ver.VerifierError, "LEAN_BUNDLE_UTF8", lambda: ver.verify_lean_bundle(tmp, live_lean=False))
            (tmp / "VelocityBounds.lean").write_text("theorem wrong : 1 = 1 := by decide\n", encoding="utf-8", newline="\n")
            self._assert_err(ver.VerifierError, "THEOREM_LIST_MISMATCH", lambda: ver.verify_lean_bundle(tmp, live_lean=False))

    def test_07_velocity_bench_r5_and_isolated_cli_parity(self) -> None:
        # HIGH-5: ALL 4 CLI scripts run cleanly under `python3 -I -B --help` (RC=0, single-line JSON!)
        for script_name in ("preflight.py", "fast_mutate.py", "s168_velocity_bench.py", "verify_s168_velocity.py"):
            proc = subprocess.run(
                [sys.executable, "-I", "-B", os.fspath(TRACK_DIR / script_name), "--help"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, f"{script_name} -I --help failed: {proc.stderr}")
            parsed_h = json.loads(proc.stdout.strip())
            self.assertEqual(parsed_h["status"], "HELP")

        # MED-7 + LOW-2: Full unit & refusal/boundary coverage of s168_velocity_bench.py
        self.assertEqual(vb.median_int([30, 10, 20]), 20)
        self.assertEqual(vb.median_int([10, 20]), 20)
        self.assertEqual(vb.median_int([5]), 5)
        self._assert_err(tc.TrustCoreError, "EMPTY_TRIAL_SERIES", lambda: vb.median_int([]))
        self.assertEqual(len(vb._status_tuples_sha256([(1, "k", "a", "b", "KILLED")])), 64)

        self._assert_err(tc.TrustCoreError, "INVALID_TRIALS", lambda: vb.run_benchmark(Path("/tmp/unused.json"), trials=0))
        self._assert_err(tc.TrustCoreError, "INVALID_TRIALS", lambda: vb.run_benchmark(Path("/tmp/unused.json"), trials=10))

        with tempfile.TemporaryDirectory(prefix="s168_vb_") as tmp_s:
            tmp = Path(tmp_s)
            # Synthetic 5/5 defect fixture harness
            fix_res = vb._build_synthetic_defect_fixtures(tmp)
            self.assertEqual(len(fix_res), 5)
            self.assertTrue(all(r["caught"] for r in fix_res))

            # Refusal paths when preflight fails/slow or fixture uncaught
            unc_d = tmp / "uncaught"
            unc_d.mkdir()
            with mock.patch.object(vb, "run_preflight", return_value={"passed": True, "findings": [], "elapsed_ms": 0}):
                self._assert_err(tc.TrustCoreError, "FIXTURE_NOT_CAUGHT", lambda: vb._build_synthetic_defect_fixtures(unc_d))
            with (
                mock.patch.object(vb, "_make_isolated_copy"),
                mock.patch.object(vb, "_cleanup_ro_copy"),
                mock.patch.object(vb, "run_preflight", side_effect=[
                    {"passed": False, "elapsed_ms": 100},
                    {"passed": False, "elapsed_ms": 100},
                ]),
            ):
                self._assert_err(tc.TrustCoreError, "PREFLIGHT_S161_UNEXPECTED", lambda: vb.run_benchmark(tmp / "out.json", trials=1))
            with (
                mock.patch.object(vb, "_make_isolated_copy"),
                mock.patch.object(vb, "_cleanup_ro_copy"),
                mock.patch.object(vb, "run_preflight", side_effect=[
                    {"passed": True, "elapsed_ms": 100, "files_scanned": 10, "lean_unique_theorems": 62, "lean_theorems_indexed": 124, "finding_count": 0},
                    {"passed": False, "elapsed_ms": 2000, "files_scanned": 18, "lean_unique_theorems": 12, "lean_theorems_indexed": 24, "finding_count": 2, "findings": []},
                ]),
            ):
                self._assert_err(tc.TrustCoreError, "PREFLIGHT_S166_SLOW", lambda: vb.run_benchmark(tmp / "out.json", trials=1))

            # CLI failure paths for baseline & fast_mutate wrappers
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["x"], 1, b"", b"boom")):
                self._assert_err(tc.TrustCoreError, "BASELINE_P1_FAILED", lambda: vb._run_baseline_aletheia_cli_dual(tmp, "a.py", "echo ok", "_req", workers=1))
                self._assert_err(tc.TrustCoreError, "FAST_MUTATE_CLI_FAILED", lambda: vb._run_fast_mutate_cli_dual(tmp, "a.py", "echo ok", "_req", workers=1))
            with mock.patch("subprocess.run", side_effect=[
                subprocess.CompletedProcess(["x"], 0, b'{"total_mutants":1,"killed":1,"survived":0,"null_mutant":"passed","results":[]}', b""),
                subprocess.CompletedProcess(["x"], 1, b"", b"p2fail"),
            ]):
                self._assert_err(tc.TrustCoreError, "BASELINE_P2_FAILED", lambda: vb._run_baseline_aletheia_cli_dual(tmp, "a.py", "echo ok", "_req", workers=1))

            # Mixed parity refusal paths (parity mismatch & degenerate fixture)
            fake_base_m = {
                "pass1_total": 2, "pass1_killed": 1, "pass1_survived": 1,
                "pass2_total": 4, "pass2_killed": 2, "pass2_survived": 2,
                "pass1_statuses": [(1, "k", "a", "b", "KILLED"), (2, "k", "c", "d", "SURVIVED")],
                "pass2_statuses": [(1, "k", "a", "b", "KILLED"), (2, "k", "c", "d", "SURVIVED"), (3, "k", "e", "f", "KILLED"), (4, "k", "g", "h", "SURVIVED")],
            }
            fake_fast_bad = {**fake_base_m, "pass2_dedup_skipped": 1, "pass1_statuses": [(1, "k", "a", "b", "KILLED"), (2, "k", "c", "d", "KILLED")]}
            mp1 = tmp / "mp1"
            mp2 = tmp / "mp2"
            mp1.mkdir()
            mp2.mkdir()
            with mock.patch.object(vb, "_run_baseline_aletheia_cli_dual", return_value=fake_base_m), mock.patch.object(vb, "_run_fast_mutate_cli_dual", return_value=fake_fast_bad):
                self._assert_err(tc.TrustCoreError, "MIXED_PARITY_MISMATCH", lambda: vb._run_mixed_parity_check(mp1))
            fake_degen = {**fake_base_m, "pass1_survived": 0, "pass2_dedup_skipped": 1}
            with mock.patch.object(vb, "_run_baseline_aletheia_cli_dual", return_value=fake_degen), mock.patch.object(vb, "_run_fast_mutate_cli_dual", return_value=fake_degen):
                self._assert_err(tc.TrustCoreError, "MIXED_FIXTURE_DEGENERATE", lambda: vb._run_mixed_parity_check(mp2))

            # End-to-end mocked run_benchmark (1-trial + 2-trial drift refusal + parity mismatch refusal + CLI)
            pf1_ok = {"passed": True, "elapsed_ms": 150, "files_scanned": 10, "lean_unique_theorems": 62, "lean_theorems_indexed": 124, "finding_count": 0, "findings": []}
            pf2_ok = {"passed": False, "elapsed_ms": 200, "files_scanned": 18, "lean_unique_theorems": 12, "lean_theorems_indexed": 24, "finding_count": 2, "findings": [{"code": "MISSING_ALLOW_ABBREV_FALSE"}]}
            mix_ok = {"fast_arm_entrypoint": "python_api_allow_survivors", "pass1_total": 5, "pass1_killed": 2, "pass1_survived": 3, "pass2_total": 9, "pass2_killed": 4, "pass2_survived": 5, "pass2_new_sites": 4, "pass2_dedup_skipped": 2, "pass1_mutant_set_sha256": "a" * 64, "pass2_mutant_set_sha256": "b" * 64, "parity_exact_100pct": True}
            st_ok = [(1, "guard_if_reject", "if x:", "if False:", "KILLED")]
            b_arm = {"elapsed_ms": 6000, "workers": 1, "cli_entrypoint": True, "pass1_total": 1, "pass1_killed": 1, "pass1_survived": 0, "pass2_total": 1, "pass2_killed": 1, "pass2_survived": 0, "mutant_subprocess_evals": 2, "control_subprocess_evals": 4, "total_subprocess_evals": 6, "pass1_statuses": st_ok, "pass2_statuses": st_ok}
            f_arm = {"elapsed_ms": 2000, "workers": 1, "cli_entrypoint": True, "failfast_injected": True, "pass1_total": 1, "pass1_killed": 1, "pass1_survived": 0, "pass2_total": 1, "pass2_killed": 1, "pass2_survived": 0, "pass2_dedup_skipped": 1, "mutant_subprocess_evals": 1, "control_subprocess_evals": 4, "total_subprocess_evals": 5, "pass1_statuses": st_ok, "pass2_statuses": st_ok}

            out_j = tmp / "bench_out.json"
            fake_s166 = tmp / "fake_s166"
            (fake_s166 / "aletheia").mkdir(parents=True)
            (fake_s166 / "aletheia" / "portfolio_dag.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
            with (
                mock.patch.object(vb, "_S166_DIR", fake_s166),
                mock.patch.object(vb, "run_preflight", side_effect=[pf1_ok, pf2_ok]),
                mock.patch.object(vb, "_build_synthetic_defect_fixtures", return_value=[{"fixture": "f", "expected_code": "X", "caught": True, "codes_detected": ["X"], "elapsed_ms": 1}]),
                mock.patch.object(vb, "_run_mixed_parity_check", return_value=mix_ok),
                mock.patch.object(vb, "_make_isolated_copy"),
                mock.patch.object(vb, "_cleanup_ro_copy"),
                mock.patch.object(vb, "_run_baseline_aletheia_cli_dual", return_value=b_arm),
                mock.patch.object(vb, "_run_fast_mutate_cli_dual", return_value=f_arm),
            ):
                out_vb, err_vb = io.StringIO(), io.StringIO()
                with redirect_stdout(out_vb), redirect_stderr(err_vb):
                    rc_vb = vb.main(["--out", str(out_j), "--trials", "1"])
                self.assertEqual(rc_vb, 0)
                self.assertTrue(out_j.is_file())

            # Parity mismatch in run_benchmark
            f_bad_arm = {**f_arm, "pass1_statuses": [(1, "guard_if_reject", "if x:", "if False:", "SURVIVED")]}
            with (
                mock.patch.object(vb, "_S166_DIR", fake_s166),
                mock.patch.object(vb, "run_preflight", side_effect=[pf1_ok, pf2_ok]),
                mock.patch.object(vb, "_build_synthetic_defect_fixtures", return_value=[]),
                mock.patch.object(vb, "_run_mixed_parity_check", return_value=mix_ok),
                mock.patch.object(vb, "_make_isolated_copy"),
                mock.patch.object(vb, "_cleanup_ro_copy"),
                mock.patch.object(vb, "_run_baseline_aletheia_cli_dual", return_value=b_arm),
                mock.patch.object(vb, "_run_fast_mutate_cli_dual", return_value=f_bad_arm),
            ):
                self._assert_err(tc.TrustCoreError, "MUTATION_PARITY_MISMATCH", lambda: vb.run_benchmark(tmp / "bad1.json", trials=1))

            # Trial parity drift in run_benchmark (trials=2)
            with (
                mock.patch.object(vb, "_S166_DIR", fake_s166),
                mock.patch.object(vb, "run_preflight", side_effect=[pf1_ok, pf2_ok]),
                mock.patch.object(vb, "_build_synthetic_defect_fixtures", return_value=[]),
                mock.patch.object(vb, "_run_mixed_parity_check", return_value=mix_ok),
                mock.patch.object(vb, "_make_isolated_copy"),
                mock.patch.object(vb, "_cleanup_ro_copy"),
                mock.patch.object(vb, "_run_baseline_aletheia_cli_dual", side_effect=[b_arm, b_arm, f_bad_arm, b_arm]),
                mock.patch.object(vb, "_run_fast_mutate_cli_dual", return_value=f_arm),
            ):
                self._assert_err(tc.TrustCoreError, "TRIAL_PARITY_DRIFT", lambda: vb.run_benchmark(tmp / "bad2.json", trials=2))


if __name__ == "__main__":
    unittest.main()
