"""
Fail-closed file-walk tests for `aletheia audit-check`.

The walk must never report PASS for a path it could not read: non-regular roots are refused, and symlinks,
FIFOs and unreadable files found in the tree become hard path findings. Zero bare `assert` statements.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from aletheia.audit_check import run_audit_check
from aletheia.cli import main as cli_main
from aletheia.strict_io import AletheiaError

HAS_MKFIFO = hasattr(os, "mkfifo")
BAD_PY = "assert 1 == 1\n"


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = cli_main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


def _codes(report: dict[str, Any]) -> list[str]:
    return sorted(f["code"] for f in report["path_findings"])


def _audit_without_hanging(root: Path, **kwargs: Any) -> dict[str, Any]:
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box["report"] = run_audit_check(root, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - surfaced to the test thread below
            box["error"] = exc

    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(timeout=15)
    _req(not th.is_alive(), "audit-check blocked (read a FIFO?)")
    if "error" in box:
        raise box["error"]
    return box["report"]


def _make_tree(td: str) -> tuple[Path, Path]:
    base = Path(td).resolve()
    root = base / "root"
    outside = base / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "ok.txt").write_text("fine\n", encoding="utf-8")
    return root, outside


class TestAuditWalkFailClosed(unittest.TestCase):
    def test_01_clean_tree_has_new_keys_and_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, _ = _make_tree(td)
            (root / "good.py").write_text("x = 1\n", encoding="utf-8")
            rep = run_audit_check(root)
            _req(rep["passed"] and rep["status"] == "PASS", f"clean tree must pass: {rep['failures']}")
            _req(rep["path_findings"] == [] and rep["symlinks"] == [], "clean tree must have no path findings")
            for key in ("path_findings_count", "symlink_count", "non_regular_count", "unreadable_count"):
                _req(rep["summary"][key] == 0, f"summary.{key} must be 0")
            _req(rep["summary"]["files_scanned"] == 2, f"files_scanned: {rep['summary']['files_scanned']}")

    @unittest.skipUnless(HAS_MKFIFO, "os.mkfifo unavailable")
    def test_02_fifo_root_refused_with_coded_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            fifo = Path(td) / "fifo_root"
            os.mkfifo(fifo)
            with self.assertRaises(AletheiaError) as cm:
                run_audit_check(fifo)
            _req(cm.exception.code == "TARGET_NOT_REGULAR", f"wrong code: {cm.exception.code}")
            rc, out, _ = _run_cli(["audit-check", str(fifo), "--json"])
            payload = json.loads(out)
            _req(rc == 2 and payload["status"] == "ERROR", f"rc={rc} out={out}")
            _req(payload["code"] == "TARGET_NOT_REGULAR", f"wrong cli code: {payload}")

    def test_03_symlinked_dir_is_reported_and_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, outside = _make_tree(td)
            (outside / "bad.py").write_text(BAD_PY, encoding="utf-8")
            os.symlink(outside, root / "linkdir")
            rep = run_audit_check(root)
            _req(not rep["passed"] and rep["status"] == "FAIL", "symlinked dir must fail the run")
            _req("SYMLINK_DIR" in _codes(rep), f"missing SYMLINK_DIR: {rep['path_findings']}")
            _req(rep["summary"]["py_files_scanned"] == 0, "nothing may be read through the symlinked dir")
            _req(rep["summary"]["bare_assert_count"] == 0, "bare assert behind symlink must not be read")
            _req(rep["summary"]["symlink_count"] == 1, "symlink_count must be 1")
            _req(rep["summary"]["path_findings_count"] == len(rep["path_findings"]), "count mismatch")
            _req(any(f["file"] == "linkdir" for f in rep["path_findings"]), "finding must name the symlink")
            rc, out, _ = _run_cli(["audit-check", str(root), "--json"])
            _req(rc == 1 and json.loads(out)["status"] == "FAIL", f"cli rc={rc}")

    def test_04_symlink_outside_root_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, outside = _make_tree(td)
            (outside / "secret.py").write_text(BAD_PY, encoding="utf-8")
            os.symlink(outside / "secret.py", root / "escape.py")
            rep = run_audit_check(root)
            _req(not rep["passed"], "escaping symlink must fail the run")
            _req(_codes(rep) == ["SYMLINK_OUTSIDE_ROOT"], f"codes: {_codes(rep)}")
            _req(rep["summary"]["py_files_scanned"] == 0, "outside target must not be read")

    def test_05_broken_symlink_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, _ = _make_tree(td)
            os.symlink(root / "does_not_exist.py", root / "dangling.py")
            rep = run_audit_check(root)
            _req(not rep["passed"], "broken symlink must fail the run")
            _req(_codes(rep) == ["BROKEN_SYMLINK"], f"codes: {_codes(rep)}")

    @unittest.skipUnless(HAS_MKFIFO, "os.mkfifo unavailable")
    def test_06_fifo_in_tree_reported_and_never_read(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, _ = _make_tree(td)
            os.mkfifo(root / "pipe.py")
            os.mkfifo(root / "pipe.lean")
            rep = _audit_without_hanging(root, lean_audit=True)
            _req(not rep["passed"], "FIFO in tree must fail the run")
            _req(_codes(rep) == ["NON_REGULAR_FILE", "NON_REGULAR_FILE"], f"codes: {_codes(rep)}")
            _req(rep["summary"]["non_regular_count"] == 2, "non_regular_count must be 2")
            _req(rep["summary"]["files_scanned"] == 1, "files_scanned must count only files actually read")
            rep2 = _audit_without_hanging(root, allow_symlinks=True)
            _req(not rep2["passed"], "NON_REGULAR_FILE must stay fatal with allow_symlinks")

    @unittest.skipUnless(HAS_MKFIFO, "os.mkfifo unavailable")
    def test_07_symlink_to_fifo_inside_root_never_read(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, _ = _make_tree(td)
            os.mkfifo(root / "pipe")
            os.symlink(root / "pipe", root / "pipe_link.py")
            rep = _audit_without_hanging(root)
            _req(not rep["passed"], "symlink to FIFO must fail the run")
            _req(_codes(rep) == ["NON_REGULAR_FILE", "NON_REGULAR_FILE"], f"codes: {_codes(rep)}")

    @unittest.skipIf(not hasattr(os, "geteuid") or os.geteuid() == 0, "needs a non-root POSIX user")
    def test_08_unreadable_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, _ = _make_tree(td)
            locked = root / "locked.txt"
            locked.write_text("hidden\n", encoding="utf-8")
            locked.chmod(0)
            lockdir = root / "lockdir"
            lockdir.mkdir()
            (lockdir / "inner.txt").write_text("hidden\n", encoding="utf-8")
            lockdir.chmod(0)
            try:
                if os.access(locked, os.R_OK):
                    self.skipTest("file remains readable (permissions not enforced)")
                rep = run_audit_check(root)
                rep_allow = run_audit_check(root, allow_symlinks=True)
            finally:
                lockdir.chmod(stat.S_IRWXU)
                locked.chmod(stat.S_IRUSR | stat.S_IWUSR)
            _req(not rep["passed"], "unreadable file must fail the run")
            _req(_codes(rep) == ["UNREADABLE_FILE", "UNREADABLE_FILE"], f"codes: {_codes(rep)}")
            _req(rep["summary"]["unreadable_count"] == 2, "unreadable_count must be 2")
            _req(rep["summary"]["files_scanned"] == 1, "files_scanned must count only files actually read")
            _req(not rep_allow["passed"], "UNREADABLE_FILE must stay fatal with allow_symlinks")

    def test_09_allow_symlinks_downgrades_symlink_findings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, outside = _make_tree(td)
            os.symlink(outside, root / "linkdir")
            os.symlink(outside / "nowhere.py", root / "dangling.py")
            (outside / "t.txt").write_text("x\n", encoding="utf-8")
            os.symlink(outside / "t.txt", root / "escape.txt")
            rc, _, _ = _run_cli(["audit-check", str(root), "--json"])
            _req(rc == 1, f"default must fail closed, rc={rc}")
            rc, out, _ = _run_cli(["audit-check", str(root), "--allow-symlinks", "--json"])
            rep = json.loads(out)
            _req(rc == 0 and rep["status"] == "PASS", f"--allow-symlinks must be non-fatal: {rep['failures']}")
            _req(
                _codes(rep) == ["BROKEN_SYMLINK", "SYMLINK_DIR", "SYMLINK_OUTSIDE_ROOT", "SYMLINK_OUTSIDE_ROOT"],
                f"findings must still be reported: {_codes(rep)}",
            )
            _req(rep["summary"]["symlink_count"] == 3, "symlink_count must stay 3")
            _req(rep["allow_symlinks"] is True, "allow_symlinks must be echoed in the report")

    def test_10_internal_file_symlink_is_scanned_and_listed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, _ = _make_tree(td)
            (root / "real.py").write_text(BAD_PY, encoding="utf-8")
            os.symlink(root / "real.py", root / "alias.py")
            rep = run_audit_check(root)
            _req(rep["path_findings"] == [], f"internal file symlink is allowed: {rep['path_findings']}")
            _req(rep["summary"]["py_files_scanned"] == 2, "symlinked file must be scanned")
            _req(rep["summary"]["symlink_count"] == 1, "symlink must be counted")
            _req(
                [(s["file"], s["kind"]) for s in rep["symlinks"]] == [("alias.py", "file")],
                f"symlink must be listed: {rep['symlinks']}",
            )
            _req(not rep["passed"], "bare assert in the scanned symlink target must still fail")
            _req(rep["summary"]["bare_assert_count"] == 2, "both names are scanned")

    def test_11_symlink_loop_does_not_hang_or_descend(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_walk_") as td:
            root, _ = _make_tree(td)
            os.symlink(root, root / "self")
            rep = _audit_without_hanging(root)
            _req(not rep["passed"], "directory loop must fail the run")
            _req("SYMLINK_DIR" in _codes(rep), f"codes: {_codes(rep)}")

    def test_12_help_documents_fatal_exceptions(self) -> None:
        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            try:
                cli_main(["audit-check", "--help"])
            except SystemExit:
                pass
        text = " ".join(out_buf.getvalue().split())
        _req("--allow-symlinks" in text and "NON_REGULAR_FILE and UNREADABLE_FILE stay fatal" in text, "help text")


if __name__ == "__main__":
    unittest.main()
