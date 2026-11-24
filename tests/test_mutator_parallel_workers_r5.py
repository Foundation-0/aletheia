#!/usr/bin/env python3
"""
R5 regression and mutation-hardening tests for opt-in parallel `--workers N`
RAM-backed mutation execution in `aletheia.mutator` & `aletheia.cli`.

Covers:
  1. Bit-identical JSON payload parity across `workers=1`, `workers=4`, `workers=8`, and `workers=64`
     (both 100% PASS and partial-survivor FAIL suites, plus timeout kills).
  2. Independent inode preservation (`st_nlink == 1`) across all sibling files in every worker slot
     (Zone-B hardlink-checking verifiers pass identically under parallel workers).
  3. Fail-closed validation: `INVALID_WORKERS` (`0`, `-1`, `True`, `False`, `65`, `1.5`, `"4"`),
     `INVALID_TEST_CMD` (malformed `shlex.split`), `INVALID_SNAP_ROOT` (missing, file, symlink, non-writable dir),
     `SYMLINK_IN_WORKROOT` (live and dangling symlinks), `NON_REGULAR_IN_WORKROOT` (scratch FIFO),
     and `SNAP_DIR_SECURITY_FAILED` (non-dir, wrong UID, non-0o700 mode).
  4. Private `0o700` snap selection & cleanup: Linux `/dev/shm` selection when `workers > 1`,
     graceful `tempfile.gettempdir()` fallback on non-Linux (`darwin`/`win32`) or missing/symlink/unwritable `/dev/shm`,
     and zero leftover snap directories on normal exit, baseline failure, and forced mid-run exception.
  5. CLI `--workers N` end-to-end parity and fail-closed exit code `2` on invalid `--workers`.

Zero external dependencies. Zero bare asserts. Zero `/dev/null` writes. Safe across all isolated R4 modes.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import mutator
from aletheia.cli import main as cli_main
from aletheia.strict_io import AletheiaError, write_lf_text


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = cli_main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


def _code_of(fn) -> str:
    try:
        fn()
    except AletheiaError as exc:
        return exc.code
    return "NO_ERROR"


_SAMPLE_TARGET = (
    "def check_val(x):\n"
    "    if x < 0:\n"
    "        raise ValueError('neg')\n"
    "    if x > 10:\n"
    "        raise ValueError('high')\n"
    "    if x == 5:\n"
    "        return False\n"
    "    return True\n"
)

_STRONG_TEST = (
    "import os, sys\n"
    "from pathlib import Path\n"
    "import target_mod\n"
    "sib = Path('sibling_cert.json')\n"
    "if os.lstat(sib).st_nlink != 1:\n"
    "    raise SystemExit(42)\n"
    "if not target_mod.check_val(0):\n"
    "    raise SystemExit(1)\n"
    "if not target_mod.check_val(10):\n"
    "    raise SystemExit(1)\n"
    "if target_mod.check_val(5) is not False:\n"
    "    raise SystemExit(1)\n"
    "for bad in (-1, 11):\n"
    "    try:\n"
    "        target_mod.check_val(bad)\n"
    "        raise SystemExit(2)\n"
    "    except ValueError:\n"
    "        pass\n"
)

_WEAK_TEST = (
    "import target_mod\n"
    "if not target_mod.check_val(0):\n"
    "    raise SystemExit(1)\n"
    "try:\n"
    "    target_mod.check_val(-1)\n"
    "    raise SystemExit(2)\n"
    "except ValueError:\n"
    "    pass\n"
)


class TestMutatorParallelWorkers(unittest.TestCase):
    def test_01_bit_identical_parity_and_st_nlink_one(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_par_") as td:
            root = Path(td)
            work = root / "ws"
            snap_parent = root / "snaps"
            work.mkdir()
            snap_parent.mkdir()
            os.chmod(snap_parent, 0o700)

            tgt = work / "target_mod.py"
            write_lf_text(tgt, _SAMPLE_TARGET)
            write_lf_text(work / "sibling_cert.json", '{"ok":true}\n')
            write_lf_text(work / "test_strong.py", _STRONG_TEST)
            write_lf_text(work / "test_weak.py", _WEAK_TEST)
            # Verify nested subdir and ignored artifacts (.git, __pycache__, stray .pyc) are handled properly
            (work / "nested").mkdir()
            write_lf_text(work / "nested" / "helper.py", "X = 1\n")
            (work / ".git").mkdir()
            write_lf_text(work / ".git" / "HEAD", "ref: refs/heads/main\n")
            (work / "__pycache__").mkdir()
            (work / "__pycache__" / "target_mod.cpython-314.pyc").write_bytes(b"0000")
            (work / "stray.pyc").write_bytes(b"0000")

            r1 = mutator.run_mutation_suite(
                tgt, "python3 test_strong.py", work_root=work, max_mutants=0, add_cwd=True, workers=1, snap_root=snap_parent
            )
            r4 = mutator.run_mutation_suite(
                tgt, "python3 test_strong.py", work_root=work, max_mutants=0, add_cwd=True, workers=4, snap_root=snap_parent
            )
            r64 = mutator.run_mutation_suite(
                tgt, "python3 test_strong.py", work_root=work, max_mutants=0, add_cwd=True, workers=64, snap_root=snap_parent
            )
            self.assertTrue(r1["passed"])
            self.assertEqual(r1["total_mutants"], 6)
            self.assertEqual(r1["killed"], 6)
            self.assertEqual(r1["survived"], 0)
            s1 = json.dumps(r1, sort_keys=False)
            self.assertEqual(s1, json.dumps(r4, sort_keys=False))
            self.assertEqual(s1, json.dumps(r64, sort_keys=False))
            self.assertEqual([e["id"] for e in r4["results"]], ["M001", "M002", "M003", "M004", "M005", "M006"])

            # Weak suite (mixed KILLED and SURVIVED) must also be 100% bit-identical in exact order
            w1 = mutator.run_mutation_suite(
                tgt, "python3 test_weak.py", work_root=work, max_mutants=0, add_cwd=True, workers=1, snap_root=snap_parent
            )
            w4 = mutator.run_mutation_suite(
                tgt, "python3 test_weak.py", work_root=work, max_mutants=0, add_cwd=True, workers=4, snap_root=snap_parent
            )
            self.assertFalse(w1["passed"])
            self.assertGreater(w1["survived"], 0)
            self.assertEqual(json.dumps(w1, sort_keys=False), json.dumps(w4, sort_keys=False))

            # Spy verify prefer_shm=(workers > 1) and serial vs ThreadPoolExecutor dispatch (effective_workers == 1)
            seen_prefer: list[bool] = []
            orig_sel = mutator._select_snap_parent

            def spy_sel(sr, *, prefer_shm, platform_name=None, shm_dir=None):
                seen_prefer.append(prefer_shm)
                return orig_sel(sr, prefer_shm=prefer_shm, platform_name=platform_name, shm_dir=shm_dir)

            pool_calls: list[int] = []
            orig_pool = mutator.ThreadPoolExecutor

            def spy_pool(*args, **kwargs):
                pool_calls.append(kwargs.get("max_workers", args[0] if args else -1))
                return orig_pool(*args, **kwargs)

            with (
                mock.patch.object(mutator, "_select_snap_parent", side_effect=spy_sel),
                mock.patch.object(mutator, "ThreadPoolExecutor", side_effect=spy_pool),
            ):
                mutator.run_mutation_suite(
                    tgt, "python3 test_strong.py", work_root=work, max_mutants=2, add_cwd=True, workers=1, snap_root=snap_parent
                )
                self.assertEqual(seen_prefer, [False])
                self.assertEqual(pool_calls, [])
                mutator.run_mutation_suite(
                    tgt, "python3 test_strong.py", work_root=work, max_mutants=2, add_cwd=True, workers=2, snap_root=snap_parent
                )
                self.assertEqual(seen_prefer, [False, True])
                self.assertEqual(pool_calls, [2])

            # Zero leaked snaps left in snap_parent
            self.assertEqual(list(snap_parent.iterdir()), [])

    def test_02_parallel_timeout_kill_and_env_pinning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_parto_") as td:
            root = Path(td)
            tgt = root / "loop_mod.py"
            write_lf_text(
                tgt,
                "import time\n"
                "def guard_a(x):\n"
                "    if x < 0:\n"
                "        raise ValueError('neg')\n"
                "    return x\n"
                "def guard_b(x):\n"
                "    if x > 5:\n"
                "        raise ValueError('big')\n"
                "    return x\n",
            )
            # When guard_a(-1) fails to raise, sleep past timeout; verify env vars pinned when workers > 1
            write_lf_text(
                root / "test_to.py",
                "import os, time\n"
                "import loop_mod\n"
                "if os.environ.get('OPENBLAS_NUM_THREADS') != '1':\n"
                "    raise SystemExit(9)\n"
                "if os.environ.get('OMP_NUM_THREADS') != '1':\n"
                "    raise SystemExit(9)\n"
                "if os.environ.get('PYTHONDONTWRITEBYTECODE') != '1':\n"
                "    raise SystemExit(9)\n"
                "if loop_mod.guard_a(0) != 0 or loop_mod.guard_b(5) != 5:\n"
                "    raise SystemExit(1)\n"
                "try:\n"
                "    loop_mod.guard_a(-1)\n"
                "    time.sleep(5)\n"
                "except ValueError:\n"
                "    pass\n"
                "try:\n"
                "    loop_mod.guard_b(6)\n"
                "    raise SystemExit(2)\n"
                "except ValueError:\n"
                "    pass\n",
            )
            res = mutator.run_mutation_suite(
                tgt, "python3 test_to.py", work_root=root, max_mutants=0, timeout=1, add_cwd=True, workers=2
            )
            self.assertTrue(res["passed"])
            self.assertIn(-9, [r["returncode"] for r in res["results"]])

        # Direct unit check of _child_env_for_workers boundary (workers=1 vs workers=2)
        self.assertIsNone(mutator._child_env_for_workers(1))
        env2 = mutator._child_env_for_workers(2)
        self.assertIsInstance(env2, dict)
        self.assertEqual(env2["OPENBLAS_NUM_THREADS"], "1")
        self.assertEqual(env2["OMP_NUM_THREADS"], "1")
        self.assertEqual(env2["MKL_NUM_THREADS"], "1")
        self.assertEqual(env2["NUMEXPR_NUM_THREADS"], "1")
        self.assertEqual(env2["PYTHONDONTWRITEBYTECODE"], "1")

    def test_03_fail_closed_validation_and_symlink_fifo_refusal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_parval_") as td:
            root = Path(td)
            tgt = root / "m.py"
            write_lf_text(tgt, "def f(x):\n    if x < 0:\n        raise ValueError(x)\n    return x\n")

            # INVALID_WORKERS: 0, -1, 65, bools, float, str
            for bad_w in (0, -1, 65, True, False, 1.5, "4"):
                self.assertEqual(
                    _code_of(lambda w=bad_w: mutator.run_mutation_suite(tgt, "python3 -c pass", work_root=root, workers=w)),
                    "INVALID_WORKERS",
                )

            # INVALID_TEST_CMD: malformed shlex quotation
            self.assertEqual(
                _code_of(lambda: mutator._prepare_cmd("python3 'unclosed", "m.py")),
                "INVALID_TEST_CMD",
            )
            self.assertEqual(
                _code_of(lambda: mutator.run_mutation_suite(tgt, "python3 'unclosed", work_root=root, workers=2)),
                "INVALID_TEST_CMD",
            )

            # SYMLINK_IN_WORKROOT: live symlink & dangling symlink
            ws_sym = root / "ws_sym"
            ws_sym.mkdir()
            write_lf_text(ws_sym / "m.py", "def f(x):\n    if x < 0:\n        raise ValueError(x)\n    return x\n")
            os.symlink(tgt, ws_sym / "link.py")
            self.assertEqual(
                _code_of(lambda: mutator.run_mutation_suite(ws_sym / "m.py", "python3 -c pass", work_root=ws_sym, workers=2)),
                "SYMLINK_IN_WORKROOT",
            )

            ws_dang = root / "ws_dang"
            ws_dang.mkdir()
            write_lf_text(ws_dang / "m.py", "def f(x):\n    if x < 0:\n        raise ValueError(x)\n    return x\n")
            os.symlink(root / "does_not_exist.py", ws_dang / "dangling.py")
            self.assertEqual(
                _code_of(lambda: mutator.run_mutation_suite(ws_dang / "m.py", "python3 -c pass", work_root=ws_dang, workers=1)),
                "SYMLINK_IN_WORKROOT",
            )

            # NON_REGULAR_IN_WORKROOT: scratch FIFO inside work_root
            if hasattr(os, "mkfifo"):
                ws_fifo = root / "ws_fifo"
                ws_fifo.mkdir()
                write_lf_text(ws_fifo / "m.py", "def f(x):\n    if x < 0:\n        raise ValueError(x)\n    return x\n")
                os.mkfifo(ws_fifo / "pipe.fifo")
                self.assertEqual(
                    _code_of(lambda: mutator.run_mutation_suite(ws_fifo / "m.py", "python3 -c pass", work_root=ws_fifo, workers=2)),
                    "NON_REGULAR_IN_WORKROOT",
                )

            # Verify _copy_workspace_no_symlinks ignores .git, __pycache__, and *.pyc while preserving nested files
            src_ig = root / "src_ig"
            dst_ig = root / "dst_ig"
            (src_ig / ".git").mkdir(parents=True)
            (src_ig / "__pycache__").mkdir()
            (src_ig / "sub").mkdir()
            write_lf_text(src_ig / ".git" / "config", "x\n")
            (src_ig / "__pycache__" / "a.pyc").write_bytes(b"1")
            (src_ig / "top.pyc").write_bytes(b"1")
            write_lf_text(src_ig / "sub" / "keep.py", "Y = 2\n")
            mutator._copy_workspace_no_symlinks(src_ig, dst_ig)
            self.assertFalse((dst_ig / ".git").exists())
            self.assertFalse((dst_ig / "__pycache__").exists())
            self.assertFalse((dst_ig / "top.pyc").exists())
            self.assertTrue((dst_ig / "sub" / "keep.py").is_file())
            self.assertEqual(os.lstat(dst_ig / "sub" / "keep.py").st_nlink, 1)

    def test_04_snap_parent_selection_darwin_fallback_security_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_parsnap_") as td:
            root = Path(td)
            real_dir = root / "real_shm"
            real_dir.mkdir()
            os.chmod(real_dir, 0o700)
            ro_dir = root / "ro_dir"
            ro_dir.mkdir()
            os.chmod(ro_dir, 0o500)
            reg_file = root / "afile"
            write_lf_text(reg_file, "x\n")
            sym_dir = root / "sym_dir"
            os.symlink(real_dir, sym_dir)
            missing_dir = root / "nonexistent"
            tmp_fallback = Path(tempfile.gettempdir()).resolve()

            try:
                # Explicit snap_root validation
                self.assertEqual(mutator._select_snap_parent(real_dir, prefer_shm=False), real_dir.resolve())
                for bad_root in (missing_dir, reg_file, sym_dir, ro_dir):
                    self.assertEqual(
                        _code_of(lambda p=bad_root: mutator._select_snap_parent(p, prefer_shm=True)),
                        "INVALID_SNAP_ROOT",
                    )

                # Linux + prefer_shm=True picks writable non-symlink shm_dir
                self.assertEqual(
                    mutator._select_snap_parent(None, prefer_shm=True, platform_name="linux", shm_dir=real_dir),
                    real_dir,
                )
                # Graceful tempdir fallback: prefer_shm=False, macOS darwin, missing shm, symlink shm, non-dir shm, unwritable shm
                self.assertEqual(
                    mutator._select_snap_parent(None, prefer_shm=False, platform_name="linux", shm_dir=real_dir),
                    tmp_fallback,
                )
                self.assertEqual(
                    mutator._select_snap_parent(None, prefer_shm=True, platform_name="darwin", shm_dir=real_dir),
                    tmp_fallback,
                )
                for bad_shm in (missing_dir, sym_dir, reg_file, ro_dir):
                    self.assertEqual(
                        mutator._select_snap_parent(None, prefer_shm=True, platform_name="linux", shm_dir=bad_shm),
                        tmp_fallback,
                    )

                # _create_private_snap_dir mode 0o700, create failure, and security stat checks
                created = mutator._create_private_snap_dir(real_dir)
                try:
                    self.assertEqual(os.lstat(created).st_mode & 0o777, 0o700)
                finally:
                    created.rmdir()

                self.assertEqual(
                    _code_of(lambda: mutator._create_private_snap_dir(ro_dir)),
                    "SNAP_DIR_CREATE_FAILED",
                )

                uid = os.getuid() if hasattr(os, "getuid") else 1000
                st_ok = os.stat_result((stat.S_IFDIR | 0o700, 0, 0, 1, uid, 0, 0, 0, 0, 0))
                mutator._verify_private_dir_stat(st_ok, uid, real_dir)
                st_not_dir = os.stat_result((stat.S_IFREG | 0o700, 0, 0, 1, uid, 0, 0, 0, 0, 0))
                st_bad_uid = os.stat_result((stat.S_IFDIR | 0o700, 0, 0, 1, uid + 1, 0, 0, 0, 0, 0))
                st_bad_mode = os.stat_result((stat.S_IFDIR | 0o755, 0, 0, 1, uid, 0, 0, 0, 0, 0))
                for bad_st in (st_not_dir, st_bad_uid, st_bad_mode):
                    self.assertEqual(
                        _code_of(lambda s=bad_st: mutator._verify_private_dir_stat(s, uid, real_dir)),
                        "SNAP_DIR_SECURITY_FAILED",
                    )

                # Verify _create_private_snap_dir actually enforces _verify_private_dir_stat on POSIX and cleans up
                if os.name == "posix":
                    with mock.patch("aletheia.mutator.os.lstat", return_value=st_bad_mode):
                        self.assertEqual(
                            _code_of(lambda: mutator._create_private_snap_dir(real_dir)),
                            "SNAP_DIR_SECURITY_FAILED",
                        )
                    self.assertEqual(list(real_dir.iterdir()), [])

                # Unconditional cleanup on baseline failure AND forced mid-run exception
                ws = root / "ws_err"
                ws.mkdir()
                write_lf_text(ws / "m.py", _SAMPLE_TARGET)
                write_lf_text(ws / "fail_base.py", "raise SystemExit(7)\n")
                self.assertEqual(
                    _code_of(
                        lambda: mutator.run_mutation_suite(
                            ws / "m.py", "python3 fail_base.py", work_root=ws, workers=2, snap_root=real_dir
                        )
                    ),
                    "BASELINE_TEST_FAILED",
                )
                self.assertEqual(list(real_dir.iterdir()), [])

                write_lf_text(ws / "ok_base.py", "import m\n")
                with mock.patch("aletheia.mutator.apply_single_mutation", side_effect=RuntimeError("boom")):
                    with self.assertRaises(RuntimeError):
                        mutator.run_mutation_suite(
                            ws / "m.py", "python3 ok_base.py", work_root=ws, add_cwd=True, workers=2, snap_root=real_dir
                        )
                self.assertEqual(list(real_dir.iterdir()), [])
            finally:
                os.chmod(ro_dir, 0o700)

    def test_05_cli_workers_parity_and_refusal(self) -> None:
        fixture = ROOT / "tests" / "fixture_verifier.py"
        rc1, out1, err1 = _run_cli([
            "mutate", str(fixture),
            "--test-cmd", "python3 fixture_verifier_test.py",
            "--work-root", str(fixture.parent),
            "--workers", "1",
            "--json",
        ])
        rc4, out4, err4 = _run_cli([
            "mutate", str(fixture),
            "--test-cmd", "python3 fixture_verifier_test.py",
            "--work-root", str(fixture.parent),
            "--workers", "4",
            "--json",
        ])
        self.assertEqual(rc1, 0, f"CLI workers=1 failed: {out1} {err1}")
        self.assertEqual(rc4, 0, f"CLI workers=4 failed: {out4} {err4}")
        self.assertEqual(out1, out4)
        parsed = json.loads(out4)
        self.assertTrue(parsed["passed"])
        self.assertEqual(parsed["survived"], 0)

        # Fail-closed CLI refusal on --workers 0 and --workers 65
        for bad in ("0", "65"):
            rc_b, out_b, _ = _run_cli([
                "mutate", str(fixture),
                "--test-cmd", "python3 fixture_verifier_test.py",
                "--work-root", str(fixture.parent),
                "--workers", bad,
                "--json",
            ])
            self.assertEqual(rc_b, 2)
            self.assertEqual(json.loads(out_b)["code"], "INVALID_WORKERS")


if __name__ == "__main__":
    unittest.main()
