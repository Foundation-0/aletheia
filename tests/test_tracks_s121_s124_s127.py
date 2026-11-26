"""
Pure-stdlib R4/R5 verification harness for Wave-11-15 verified studies
(`studies/tracks_s121_s124_s127/`: Tracks S121, S122, S123, S124, and S127).

Discovered automatically by `tests/run_all.py` (`pattern="test_*.py"`).
Zero external dependencies (no PyTorch/NumPy required). Zero bare `assert`s.
Zero skipped tests across `-I -B`, `-I -O -B`, and `-I -B -W error`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
STUDIES_DIR = ROOT / "studies" / "tracks_s121_s124_s127"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia.audit_check import run_audit_check

PINNED_S121_PAYLOAD_SHA256 = "373ff4d100e0ad7f6e71160b5bc557fb51ad52165f1d907a4fd3f95d3a35142f"
PINNED_S122_CERT_SHA256 = "16d2d039358dcdee1e1a85e9211603c48a3a1a808c1ba2129d95f3b15fd04ba3"
PINNED_S123_CERT_SHA256 = "00022833acb4cdee03074af058860ff02bdd133b8a7bb493eff1ac46707abdbf"
PINNED_S124_CERT_SHA256 = "7e0724b4bff0e7567bec4285f7e0996027e7aac10d05ecf8da57cb5a04a5b6e9"
PINNED_S127_CERT_SHA256 = "dd1aeb8309fa259ffeb5947eb0419dd152ccd9aa4f05e52e02d332cf569f4e06"


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


class TestWave11To15VerifiedStudies(unittest.TestCase):
    def test_01_s121_loopcd_platosphere_oracle_selftest_and_r5(self) -> None:
        track = STUDIES_DIR / "track_s121_loopcd_platosphere"
        p_oracle = _run_py(track, ["verify_loopcd_sphere_geometry.py", "--check", "--json"])
        payload = json.loads(p_oracle.stdout)
        _req(
            payload.get("payload_sha256") == PINNED_S121_PAYLOAD_SHA256,
            f"S121 payload_sha256 mismatch: {payload.get('payload_sha256')!r}",
        )

        p_self = _run_py(track, ["run_w11_live_loopcd_platosphere.py", "--selftest-stdlib", "--json"])
        self_data = json.loads(p_self.stdout)
        _req(
            self_data.get("passed") is True
            and self_data.get("prereg_source") == "disk_verified"
            and self_data.get("zone_b_bundle_verified") is True,
            f"S121 stdlib selftest or disk prereg/Zone-B binding failed: {self_data}",
        )
        p_zb = _run_py(track, ["run_w11_live_loopcd_platosphere.py", "--check-zone-b", "--json"])
        _req(json.loads(p_zb.stdout).get("passed") is True, f"S121 --check-zone-b failed: {p_zb.stdout}")

        _run_py(track, ["test_loopcd_sphere_geometry_r5.py"])
        _run_py(track, ["test_w11_live_loopcd_platosphere_r5.py"])

    def test_02_s122_xpi_gegenbauer_oracle_and_stdlib_r5(self) -> None:
        track = STUDIES_DIR / "track_s122_xpi_gegenbauer"
        p_oracle = _run_py(track, ["verify_xpi_gegenbauer_attention.py", "--json"])
        cert = json.loads(p_oracle.stdout)
        _req(
            cert.get("certificate_sha256") == PINNED_S122_CERT_SHA256,
            f"S122 certificate_sha256 mismatch: {cert.get('certificate_sha256')!r}",
        )
        p_bchk = _run_py(track, ["bench_gegenbauer_vs_monomial_attn.py", "--check"])
        bchk = json.loads(p_bchk.stdout)
        _req(
            bchk.get("status") == "PASS" and bchk.get("verdict") == "PARTIAL",
            f"S122 bench --check failed: {bchk}",
        )

        _run_py(track, ["test_xpi_gegenbauer_attention_r5.py"])
        # Run the pure-stdlib bench tests unconditionally (zero skips on torch-free hosts)
        _run_py(
            track,
            [
                "-c",
                "import sys, unittest; sys.path.insert(0, '.'); "
                "suite = unittest.defaultTestLoader.loadTestsFromNames(["
                "'test_bench_gegenbauer_r5.TestBenchGegenbauerR5.test_01_basis_matrix_and_pure_law4_grading_boundaries', "
                "'test_bench_gegenbauer_r5.TestBenchGegenbauerR5.test_02_payload_validator_and_cli_guards']); "
                "res = unittest.TextTestRunner(verbosity=0).run(suite); "
                "sys.exit(0 if res.wasSuccessful() and res.testsRun == 2 and not res.skipped else 1)",
            ],
        )

    def test_03_s123_sfast_state_transport_oracle_cert_and_r5(self) -> None:
        track = STUDIES_DIR / "track_s123_sfast_state_transport"
        p_oracle = _run_py(track, ["verify_state_transport_geometry.py", "--json"])
        cert = json.loads(p_oracle.stdout)
        _req(
            cert.get("certificate_sha256") == PINNED_S123_CERT_SHA256,
            f"S123 certificate_sha256 mismatch: {cert.get('certificate_sha256')!r}",
        )
        _run_py(track, ["verify_state_transport_geometry.py", "--check", "s123_state_transport_certificate.json"])

        p_self = _run_py(track, ["bench_sfast_cross_seed_transport.py", "--selftest-stdlib", "--json"])
        self_data = json.loads(p_self.stdout)
        _req(self_data.get("passed") is True, f"S123 stdlib selftest failed: {self_data}")

        _run_py(track, ["test_state_transport_geometry_r5.py"])
        _run_py(track, ["test_bench_sfast_transport_r5.py"])

    def test_04_s124_aa_roofline_l3_oracle_cert_and_r5(self) -> None:
        track = STUDIES_DIR / "track_s124_aa_roofline_l3"
        p_oracle = _run_py(track, ["verify_s124_aa_roofline_l3.py", "--json"])
        cert = json.loads(p_oracle.stdout)
        _req(
            cert.get("certificate_sha256") == PINNED_S124_CERT_SHA256,
            f"S124 certificate_sha256 mismatch: {cert.get('certificate_sha256')!r}",
        )
        _run_py(track, ["verify_s124_aa_roofline_l3.py", "--check"])
        _run_py(track, ["test_s124_aa_roofline_l3_r5.py"])

    def test_05_s127_ratncap_cone_gait_oracle_cert_and_r5(self) -> None:
        track = STUDIES_DIR / "track_s127_ratncap_cone_gait"
        p_oracle = _run_py(track, ["verify_ratncap_cone_gait.py", "--json"])
        cert = json.loads(p_oracle.stdout)
        _req(
            cert.get("certificate_sha256") == PINNED_S127_CERT_SHA256,
            f"S127 certificate_sha256 mismatch: {cert.get('certificate_sha256')!r}",
        )
        _run_py(track, ["verify_ratncap_cone_gait.py", "--check", "s127_ratncap_cone_gait_certificate.json"])
        _run_py(track, ["test_ratncap_cone_gait_r5.py"])

    def test_06_studies_bundle_hygiene_and_safety_audit(self) -> None:
        aud = run_audit_check(
            STUDIES_DIR,
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
            f"Studies bundle audit-check failed: {aud}",
        )


if __name__ == "__main__":
    unittest.main()
