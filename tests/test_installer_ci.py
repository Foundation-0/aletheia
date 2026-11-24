"""
Regression tests for the CI workflow that `aletheia install --target repo` writes.

Before this test the embedded workflow ran `python3 -m aletheia audit-check .` in a
fresh runner without installing aletheia, so it could not import the package. The
workflow must install the `aletheia-method` distribution (dependency-free, pinned to a
full commit SHA) before any `python3 -m aletheia` step, and its step names must not
claim more than `audit-check` automates.

Zero external dependencies. Zero bare assert statements (100% R4 parity across
`-I -B`, `-I -O -B`, and `-I -B -W error`).
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia.installer import _EMBEDDED_CI_YML, _build_install_plan, install_adapter

WORKFLOW = ".github/workflows/aletheia-ci.yml"
_PINNED_INSTALL_RE = re.compile(
    r'python3 -m pip install --no-deps "aletheia-method @ git\+https://github\.com/Foundation-0/aletheia@([0-9a-f]{40})"\Z'
)


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


class TestEmbeddedCIWorkflow(unittest.TestCase):
    def test_dry_run_plans_the_workflow_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_ci_dry_") as td:
            dest = Path(td) / "repo"
            dest.mkdir()
            res = install_adapter("repo", dest=dest, dry_run=True)
            _req(res["status"] == "DRY_RUN" and res["dry_run"] is True, f"not a dry run: {res}")
            by_rel = {f["relative_path"]: f for f in res["files"]}
            _req(WORKFLOW in by_rel, f"dry run does not plan {WORKFLOW}: {sorted(by_rel)}")
            _req(by_rel[WORKFLOW]["action"] == "CREATE", f"unexpected action: {by_rel[WORKFLOW]}")
            planned = dict(_build_install_plan("repo", None))[WORKFLOW]
            _req(
                by_rel[WORKFLOW]["bytes"] == len(planned.encode("utf-8")),
                "dry-run byte count does not match the workflow text checked below",
            )
            _req(not (dest / ".github").exists(), "dry run wrote files")

    def test_workflow_installs_aletheia_before_running_it(self) -> None:
        for repo_root in (None, ROOT):
            workflow = dict(_build_install_plan("repo", repo_root))[WORKFLOW]
            lines = [ln.strip() for ln in workflow.splitlines()]
            installs = [i for i, ln in enumerate(lines) if "pip install" in ln]
            runs = [i for i, ln in enumerate(lines) if ln.startswith("python3 -m aletheia ")]
            _req(len(installs) == 1, f"expected one install line (repo_root={repo_root}), got {installs}")
            _req(len(runs) >= 1, "workflow runs no aletheia command")
            _req(installs[0] < min(runs), "aletheia is run before it is installed")
            line = lines[installs[0]]
            _req(_PINNED_INSTALL_RE.match(line) is not None, f"install line is not a pinned, dependency-free install: {line}")
            _req("--no-build-isolation" not in line, f"install needs preinstalled setuptools: {line}")

    def test_step_names_scope_what_audit_check_automates(self) -> None:
        _req("R6/R7 not automated by this command" in _EMBEDDED_CI_YML, "audit-check step name does not scope R6/R7")
        _req("R1-R5" not in _EMBEDDED_CI_YML and "R1–R5" not in _EMBEDDED_CI_YML, "step name claims R1-R5")


if __name__ == "__main__":
    unittest.main()
