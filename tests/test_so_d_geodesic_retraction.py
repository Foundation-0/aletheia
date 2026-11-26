"""Pure-stdlib integration verification for the SO(d) Cayley geodesic retraction study.

Discovered automatically by `tests/run_all.py` (`pattern="test_*.py"`).
Zero external dependencies, zero bare asserts, zero skipped tests across
`-I -B`, `-I -O -B`, and `-I -B -W error`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
STUDY_DIR = ROOT / "studies" / "so_d_geodesic_retraction"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia.audit_check import run_audit_check

PINNED_CERTIFICATE_SHA256 = "ef1cda74445458021f148cafc1a9f618eac909122da876143d73a9316ed56146"


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run_py(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    flags = ["-I", "-O", "-B"] if not __debug__ else ["-I", "-B"]
    if any(opt == "error" or opt.startswith("error:") for opt in sys.warnoptions):
        flags.extend(["-W", "error"])
    proc = subprocess.run(
        [sys.executable, *flags, *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    _req(
        proc.returncode == 0,
        f"Command {args!r} failed in {cwd.name} (rc={proc.returncode}):\n"
        f"STDOUT:\n{proc.stdout[-800:]}\nSTDERR:\n{proc.stderr[-800:]}",
    )
    return proc


class TestSoDGeodesicRetractionStudy(unittest.TestCase):
    def test_01_certificate_check_and_r5_suite(self) -> None:
        p_chk = _run_py(
            STUDY_DIR,
            [
                "verify_so_d_geodesic_retraction.py",
                "--check",
                "so_d_geodesic_retraction_certificate.json",
                "--require-pinned",
            ],
        )
        data = json.loads(p_chk.stdout)
        _req(
            data.get("status") == "PASS"
            and data.get("phase1_verdict") == "FALSIFIED"
            and data.get("phase2_verdict") == "CONFIRMED"
            and data.get("certificate_sha256") == PINNED_CERTIFICATE_SHA256,
            f"Certificate check mismatch: {data}",
        )
        _run_py(STUDY_DIR, ["test_so_d_geodesic_retraction_r5.py"])

    def test_02_study_bundle_hygiene_and_safety_audit(self) -> None:
        aud = run_audit_check(
            STUDY_DIR,
            lean_audit=True,
            safety_scan=True,
            strict_unseeded=True,
        )
        _req(
            aud["passed"]
            and aud["summary"]["bare_assert_count"] == 0
            and aud["summary"]["leak_count"] == 0
            and aud["summary"]["crlf_count"] == 0
            and aud["summary"]["safety_findings_count"] == 0,
            f"Study bundle audit-check failed: {aud}",
        )


if __name__ == "__main__":
    unittest.main()
