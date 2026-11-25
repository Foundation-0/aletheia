#!/usr/bin/env python3
"""Pure-stdlib assertion-free R5 adversarial test suite for Track S110 (`s110_geosphere_audit.py`).

Zero torch/numpy dependencies, zero bare `assert` statements, zero stdout noise; runs identically
on stock /usr/bin/python3 across -I -B, -I -O -B, and -I -B -W error.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import s110_geosphere_audit as audit  # noqa: E402


def _copy_evidence_tree(dst: Path) -> Path:
    for fname in list(audit.REQUIRED_EVIDENCE_FILES) + [audit.DEFAULT_CERT_NAME]:
        src = _HERE / fname
        if src.is_file():
            shutil.copy2(src, dst / fname)
    return dst


def _resign_payload_doc(doc: dict) -> str:
    body = {k: v for k, v in doc.items() if k != "payload_sha256"}
    raw = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
    body["payload_sha256"] = hashlib.sha256(raw).hexdigest()
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


class TestS110GeosphereAuditR5(unittest.TestCase):
    """Fail-closed R1-R5 + R7 verification and adversarial tamper test suite."""

    def test_01_live_certificate_check_and_standalone_parity(self) -> None:
        cert_path = _HERE / audit.DEFAULT_CERT_NAME
        verified = audit.verify_certificate_file(cert_path)
        p = verified["payload"]
        self.assertEqual(p["novelty_tier"], "N1")
        self.assertEqual(p["n2_claims"], 0)
        self.assertEqual(p["weights_count"], 0)
        self.assertEqual(p["run_counts"]["total_runs"], 42)
        self.assertEqual(p["run_counts"]["total_arms"], 14)
        self.assertEqual(p["run_counts"]["total_nan_steps"], 0)
        self.assertEqual(p["run_counts"]["min_pre_norm_faithfulness"], 1.0)
        self.assertLessEqual(p["run_counts"]["max_param_dev_pct"], 0.50)
        self.assertEqual(p["corpus"]["file_overlap_count"], 0)
        self.assertEqual(p["verdicts"]["sm86_microbench"], "PARTIAL")
        self.assertEqual(p["verdicts"]["H10a_single_shell"], "PARTIAL")
        self.assertEqual(p["verdicts"]["H10a_Shell1_Cayley2x2_bpb512"], "CONFIRMED")
        self.assertEqual(p["verdicts"]["H10b_coupled_loso"], "FALSIFIED")
        self.assertEqual(p["h10b_loso_holm_significant_count"], 0)
        self.assertAlmostEqual(p["arm_metrics"]["H10a_Shell1_Cayley2x2"]["bpb_512_mean"], 2.303283, places=5)
        self.assertAlmostEqual(p["arm_metrics"]["H10b_Geosphere_Full"]["bpb_512_mean"], 2.697586, places=5)
        self.assertAlmostEqual(p["h10a_vs_baseline_bpb"]["H10a_Shell1_Cayley2x2"]["z_score"], 3.8242, places=3)
        self.assertAlmostEqual(p["h10a_vs_baseline_bpb"]["H10a_Shell1_Cayley2x2"]["holm_adjusted_p"], 0.0002624, places=6)

        # CLI default no-arg, --check, --standalone, and --standalone --json byte-identity
        out_def = io.StringIO()
        with contextlib.redirect_stdout(out_def):
            rc = audit.main([])
        self.assertEqual(rc, 0)
        self.assertIn("OK track-s110-geosphere-net-gpu runs=42", out_def.getvalue())

        out_chk = io.StringIO()
        with contextlib.redirect_stdout(out_chk):
            rc = audit.main(["--check", str(cert_path)])
        self.assertEqual(rc, 0)
        self.assertEqual(out_chk.getvalue(), out_def.getvalue())

        out_json = io.StringIO()
        with contextlib.redirect_stdout(out_json):
            rc = audit.main(["--standalone", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(out_json.getvalue().encode("utf-8"), cert_path.read_bytes())

    def test_02_tampered_sha_and_flipped_verdict_rejected(self) -> None:
        cert = audit.verify_certificate_file(_HERE / audit.DEFAULT_CERT_NAME)

        # Tampered payload_sha256
        bad_p = dict(cert, payload_sha256="0" * 64)
        with self.assertRaises(audit.S110AuditError) as cm:
            audit.verify_certificate_object(bad_p, _HERE)
        self.assertEqual(cm.exception.code, "PAYLOAD_SHA_MISMATCH")

        # Tampered certificate_sha256
        bad_c = dict(cert, certificate_sha256="0" * 64)
        with self.assertRaises(audit.S110AuditError) as cm:
            audit.verify_certificate_object(bad_c, _HERE)
        self.assertEqual(cm.exception.code, "CERT_SHA_MISMATCH")

        # Hollow re-signed forgery flipping H10b verdict to CONFIRMED
        forged_payload = json.loads(json.dumps(cert["payload"]))
        forged_payload["verdicts"]["H10b_coupled_loso"] = "CONFIRMED"
        fp_sha = audit.sha256_canonical(forged_payload)
        outer = {
            "schema": audit.SCHEMA_VERSION,
            "track_id": audit.TRACK_ID,
            "payload_sha256": fp_sha,
            "payload": forged_payload,
        }
        fc_sha = audit.sha256_canonical(outer)
        forged_cert = dict(outer, certificate_sha256=fc_sha)
        with self.assertRaises(audit.S110AuditError) as cm:
            audit.verify_certificate_object(forged_cert, _HERE)
        self.assertEqual(cm.exception.code, "EVIDENCE_RECOMPUTATION_MISMATCH")

    def test_03_missing_or_unclean_zone_b_receipt_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = _copy_evidence_tree(Path(td))
            zb = td_path / "mlos_zone_b_s110_h10b.json"

            # Unclean Zone-B hardware run rejected
            data = json.loads(zb.read_text(encoding="utf-8"))
            data["clean_hardware_run"] = False
            zb.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "ZONE_B_UNCLEAN")

            # Non-empty anomalies rejected
            data["clean_hardware_run"] = True
            data["anomalies"] = ["thermal_throttle"]
            zb.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "ZONE_B_ANOMALIES")

            # Missing Zone-B file rejected
            zb.unlink()
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "FILE_MISSING_OR_UNREADABLE")

    def test_04_dropped_arm_mutated_faithfulness_and_overlap_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = _copy_evidence_tree(Path(td))
            h10b_p = td_path / "h10b_gpu_results.json"
            orig = json.loads(h10b_p.read_text(encoding="utf-8"))

            # Dropped run (26 instead of 27)
            dropped = json.loads(json.dumps(orig))
            dropped["runs"] = dropped["runs"][:-1]
            h10b_p.write_text(_resign_payload_doc(dropped), encoding="utf-8")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "H10B_RUN_COUNT")

            # Mutated pre_norm_faithfulness < 1.0
            mut_f = json.loads(json.dumps(orig))
            mut_f["runs"][0]["pre_norm_counterfactual_patching"]["pre_norm_faithfulness_rate"] = 0.80
            h10b_p.write_text(_resign_payload_doc(mut_f), encoding="utf-8")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "PRE_NORM_FAITHFULNESS_FAIL")

            # Mutated file_overlap_count != 0
            mut_ov = json.loads(json.dumps(orig))
            mut_ov["corpus"]["file_overlap_count"] = 1
            h10b_p.write_text(_resign_payload_doc(mut_ov), encoding="utf-8")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "CORPUS_OVERLAP")

            # Mutated nan_steps != 0
            mut_nan = json.loads(json.dumps(orig))
            mut_nan["runs"][0]["nan_steps"] = 1
            h10b_p.write_text(_resign_payload_doc(mut_nan), encoding="utf-8")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "NAN_STEPS_NONZERO")

            # Tampered internal payload_sha256 without re-signing
            mut_badsha = json.loads(json.dumps(orig))
            mut_badsha["runs"][0]["train_wall_s"] = 999.0
            h10b_p.write_text(json.dumps(mut_badsha, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "EMBEDDED_SHA_MISMATCH")

            # Missing nested required key raises typed S110AuditError (never untyped KeyError/TypeError)
            mut_missing_key = json.loads(json.dumps(orig))
            del mut_missing_key["runs"][0]["params"]
            h10b_p.write_text(_resign_payload_doc(mut_missing_key), encoding="utf-8")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "MALFORMED_EVIDENCE_SCHEMA")

    def test_05_weights_leak_and_zone_b_file_hygiene_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = _copy_evidence_tree(Path(td))

            # Weight file dropped into evidence directory rejected
            wt = td_path / "forbidden_model.safetensors"
            wt.write_bytes(b"fake")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.build_certificate(td_path)
            self.assertEqual(cm.exception.code, "WEIGHTS_FORBIDDEN")
            wt.unlink()

            # Non-canonical trailing newline rejected
            cert_p = td_path / audit.DEFAULT_CERT_NAME
            raw_ok = cert_p.read_bytes()
            cert_p.write_bytes(raw_ok + b"\n")
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.verify_certificate_file(cert_p)
            self.assertEqual(cm.exception.code, "NON_CANONICAL_BYTES")

            # CRLF rejected
            cert_p.write_bytes(raw_ok.replace(b"\n", b"\r\n"))
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.verify_certificate_file(cert_p)
            self.assertEqual(cm.exception.code, "CRLF_FORBIDDEN")

            # Malformed JSON, duplicate key, NaN rejected
            for bad_txt, exp_code in (
                (b"{bad", "INVALID_JSON"),
                (b'{"a":1,"a":2}\n', "DUPLICATE_KEY"),
                (b'{"a":NaN}\n', "NONFINITE_FORBIDDEN"),
                (b"[1,2]\n", "NON_OBJECT_ROOT"),
            ):
                cert_p.write_bytes(bad_txt)
                with self.assertRaises(audit.S110AuditError) as cm:
                    audit.verify_certificate_file(cert_p)
                self.assertEqual(cm.exception.code, exp_code)

            # Symlink target rejected
            cert_p.write_bytes(raw_ok)
            sym = td_path / "sym_cert.json"
            os.symlink(cert_p, sym)
            with self.assertRaises(audit.S110AuditError) as cm:
                audit.verify_certificate_file(sym)
            self.assertEqual(cm.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

            # Clean --write round-trip in isolated tempdir
            out_w = io.StringIO()
            with contextlib.redirect_stdout(out_w):
                rc = audit.main(["--write", str(cert_p), "--evidence-dir", str(td_path)])
            self.assertEqual(rc, 0)
            self.assertIn("WROTE s110_geosphere_certificate.json", out_w.getvalue())

    def test_06_cli_error_exit_codes(self) -> None:
        for bad_argv, exp_code in (
            (["--bogus"], "UNKNOWN_FLAG"),
            (["--standalone", "--check"], "CONFLICTING_MODE"),
            (["--check", "--json"], "INVALID_FLAG_COMBO"),
            (["--evidence-dir"], "MISSING_ARG"),
            (["--check", str(_HERE / "nonexistent_cert.json")], "FILE_MISSING_OR_UNREADABLE"),
        ):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = audit.main(bad_argv)
            self.assertEqual(rc, 1)
            self.assertIn(exp_code, err.getvalue())


if __name__ == "__main__":
    unittest.main()
