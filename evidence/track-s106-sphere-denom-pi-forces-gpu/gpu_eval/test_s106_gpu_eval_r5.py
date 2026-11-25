#!/usr/bin/env python3
"""Track S106 GPU Eval R5 Verification & Adversarial Test Suite (Pure Stdlib)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

_THIS_DIR = pathlib.Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import verify_s106_gpu_eval as verifier


def _resign_pilot(obj: dict) -> bytes:
    body = {k: v for k, v in obj.items() if k != "pilot_params_sha256"}
    obj["pilot_params_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _resign_gauntlet(obj: dict) -> bytes:
    body = {k: v for k, v in obj.items() if k != "result_sha256"}
    obj["result_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class TestS106GpuEvalR5(unittest.TestCase):
    def _make_copy(self, td: str) -> pathlib.Path:
        dst = pathlib.Path(td)
        for name in (
            "s106_frozen_pilot_params.json",
            "s106_blind_gauntlet_results.json",
            "mlos_zone_b_pilot_receipt.json",
            "mlos_zone_b_gauntlet_receipt.json",
        ):
            shutil.copy2(_THIS_DIR / name, dst / name)
        return dst

    def test_01_live_verification_and_cli(self) -> None:
        res = verifier.verify_gpu_eval_dir(_THIS_DIR)
        self.assertTrue(res["ok"])
        self.assertEqual(res["arms_verified"], 117)
        self.assertEqual(res["verdicts"]["H1"], "FALSIFIED")
        self.assertEqual(res["verdicts"]["H2a"], "PARTIAL")
        self.assertEqual(res["verdicts"]["H3a"], "PARTIAL")
        self.assertEqual(res["verdicts"]["H3b"], "PARTIAL")
        self.assertEqual(res["verdicts"]["H3c"], "PARTIAL")
        self.assertEqual(res["verdicts"]["H4"], "FALSIFIED")
        strict = res["strict_kill_gate_verdicts"]
        self.assertEqual(strict, {
            "H1": "FALSIFIED",
            "H2a": "FALSIFIED",
            "H3a": "PARTIAL",
            "H3b": "FALSIFIED",
            "H3c": "FALSIFIED",
            "H4": "FALSIFIED",
        })
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = verifier.main(["--dir", str(_THIS_DIR), "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue())
        self.assertTrue(parsed["ok"])

    def test_02_reject_tampered_inner_hashes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s106_gpu_t2_") as td:
            d = self._make_copy(td)
            g = json.loads((d / "s106_blind_gauntlet_results.json").read_text(encoding="utf-8"))
            g["elapsed_seconds"] = 1.0
            (d / "s106_blind_gauntlet_results.json").write_text(
                json.dumps(g, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
            )
            with self.assertRaises(verifier.S106GpuVerifyError) as ctx:
                verifier.verify_gpu_eval_dir(d)
            self.assertEqual(ctx.exception.code, "RESULT_SHA_MISMATCH")

    def test_03_reject_snooped_pilot_and_temporal_inversion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s106_gpu_t3_") as td:
            d = self._make_copy(td)
            p = json.loads((d / "s106_frozen_pilot_params.json").read_text(encoding="utf-8"))
            p["held_out_models_touched"] = ["Qwen/Qwen2.5-3B"]
            p_bytes = _resign_pilot(p)
            (d / "s106_frozen_pilot_params.json").write_bytes(p_bytes)
            with self.assertRaises(verifier.S106GpuVerifyError) as ctx:
                verifier.verify_gpu_eval_dir(d)
            self.assertEqual(ctx.exception.code, "PILOT_SNOOPING_DETECTED")

            # Restore clean held_out_models_touched, invert timestamp
            p["held_out_models_touched"] = []
            p["locked_utc"] = "2099-01-01T00:00:00Z"
            p_bytes = _resign_pilot(p)
            (d / "s106_frozen_pilot_params.json").write_bytes(p_bytes)
            g = json.loads((d / "s106_blind_gauntlet_results.json").read_text(encoding="utf-8"))
            g["pilot_params_file_sha256"] = hashlib.sha256(p_bytes).hexdigest()
            g["pilot_params_inner_sha256"] = p["pilot_params_sha256"]
            (d / "s106_blind_gauntlet_results.json").write_bytes(_resign_gauntlet(g))
            with self.assertRaises(verifier.S106GpuVerifyError) as ctx2:
                verifier.verify_gpu_eval_dir(d)
            self.assertEqual(ctx2.exception.code, "TEMPORAL_SNOOP_ORDER")

    def test_04_reject_nonzero_syndrome_oob_verdict_spoof_and_dirty_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s106_gpu_t4_") as td:
            d = self._make_copy(td)
            # Spoof verdict to CONFIRMED and re-sign
            g = json.loads((d / "s106_blind_gauntlet_results.json").read_text(encoding="utf-8"))
            g["preregistered_verdicts"]["H1"]["verdict"] = "CONFIRMED"
            (d / "s106_blind_gauntlet_results.json").write_bytes(_resign_gauntlet(g))
            with self.assertRaises(verifier.S106GpuVerifyError) as ctx:
                verifier.verify_gpu_eval_dir(d)
            self.assertEqual(ctx.exception.code, "VERDICT_MISMATCH")

            # Inject syndrome error and re-sign
            g = json.loads((_THIS_DIR / "s106_blind_gauntlet_results.json").read_text(encoding="utf-8"))
            g["models"]["Qwen/Qwen2.5-1.5B"]["arms"]["sp_E8_lin_3b"]["syndrome_errors"] = 1
            (d / "s106_blind_gauntlet_results.json").write_bytes(_resign_gauntlet(g))
            with self.assertRaises(verifier.S106GpuVerifyError) as ctx2:
                verifier.verify_gpu_eval_dir(d)
            self.assertEqual(ctx2.exception.code, "SYNDROME_ERROR_NONZERO")

            # Dirty mlos receipt
            shutil.copy2(_THIS_DIR / "s106_blind_gauntlet_results.json", d / "s106_blind_gauntlet_results.json")
            rec = json.loads((d / "mlos_zone_b_gauntlet_receipt.json").read_text(encoding="utf-8"))
            rec["anomalies"] = ["thermal_spike"]
            (d / "mlos_zone_b_gauntlet_receipt.json").write_text(json.dumps(rec) + "\n", encoding="utf-8")
            with self.assertRaises(verifier.S106GpuVerifyError) as ctx3:
                verifier.verify_gpu_eval_dir(d)
            self.assertEqual(ctx3.exception.code, "HARDWARE_ANOMALIES")

    def test_06_receipt_forgery_prereg_status_and_link_guards(self) -> None:
        # Live run must loudly report the unshipped prereg (never silently skip).
        res = verifier.verify_gpu_eval_dir(_THIS_DIR)
        self.assertEqual(res["prereg_status"], "UNVERIFIABLE_NOT_SHIPPED")
        with tempfile.TemporaryDirectory(prefix="s106_gpu_t6_") as td:
            d = self._make_copy(td)

            def expect(code: str) -> None:
                with self.assertRaises(verifier.S106GpuVerifyError) as ctx:
                    verifier.verify_gpu_eval_dir(d)
                self.assertEqual(ctx.exception.code, code)

            # Forged receipt telemetry without re-signing -> RECEIPT_SHA_MISMATCH
            rec = json.loads((d / "mlos_zone_b_gauntlet_receipt.json").read_text(encoding="utf-8"))
            rec["end_gpu_telemetry"]["temperature_gpu_c"] = 99
            (d / "mlos_zone_b_gauntlet_receipt.json").write_text(json.dumps(rec) + "\n", encoding="utf-8")
            expect("RECEIPT_SHA_MISMATCH")

            # Zeroed receipt_sha256 -> RECEIPT_SHA_MISMATCH
            rec = json.loads((_THIS_DIR / "mlos_zone_b_gauntlet_receipt.json").read_text(encoding="utf-8"))
            rec["receipt_sha256"] = "0" * 64
            (d / "mlos_zone_b_gauntlet_receipt.json").write_text(json.dumps(rec) + "\n", encoding="utf-8")
            expect("RECEIPT_SHA_MISMATCH")

            # Re-signed but wrong bound_file_sha256 -> RECEIPT_BOUND_LINK_MISMATCH
            rec = json.loads((_THIS_DIR / "mlos_zone_b_gauntlet_receipt.json").read_text(encoding="utf-8"))
            rec["bound_file_sha256"] = "1" * 64
            body = {k: v for k, v in rec.items() if k != "receipt_sha256"}
            rec["receipt_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            (d / "mlos_zone_b_gauntlet_receipt.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            expect("RECEIPT_BOUND_LINK_MISMATCH")
            shutil.copy2(_THIS_DIR / "mlos_zone_b_gauntlet_receipt.json", d / "mlos_zone_b_gauntlet_receipt.json")

            # Tampered pilot inner hash -> PILOT_SHA_MISMATCH
            pil = json.loads((d / "s106_frozen_pilot_params.json").read_text(encoding="utf-8"))
            pil["pilot_params_sha256"] = "0" * 64
            (d / "s106_frozen_pilot_params.json").write_bytes((json.dumps(pil, sort_keys=True, separators=(",", ":")) + "\n").encode())
            expect("PILOT_SHA_MISMATCH")
            shutil.copy2(_THIS_DIR / "s106_frozen_pilot_params.json", d / "s106_frozen_pilot_params.json")

            # Tampered gauntlet->pilot link -> PILOT_LINK_SHA_MISMATCH
            g = json.loads((d / "s106_blind_gauntlet_results.json").read_text(encoding="utf-8"))
            g["pilot_params_file_sha256"] = "2" * 64
            (d / "s106_blind_gauntlet_results.json").write_bytes(_resign_gauntlet(g))
            expect("PILOT_LINK_SHA_MISMATCH")
            shutil.copy2(_THIS_DIR / "s106_blind_gauntlet_results.json", d / "s106_blind_gauntlet_results.json")

            # Tampered prereg constant in pilot -> PILOT_PREREG_MISMATCH
            pil = json.loads((d / "s106_frozen_pilot_params.json").read_text(encoding="utf-8"))
            pil["preregistration_sha256"] = "3" * 64
            (d / "s106_frozen_pilot_params.json").write_bytes(_resign_pilot(pil))
            expect("PILOT_PREREG_MISMATCH")
            shutil.copy2(_THIS_DIR / "s106_frozen_pilot_params.json", d / "s106_frozen_pilot_params.json")

            # oob / non-block / CS-08 ceiling guards
            for field, code in (("oob_groups", "OOB_GROUPS_NONZERO"), ("non_block_diffs", "NON_BLOCK_DIFF_NONZERO")):
                g = json.loads((_THIS_DIR / "s106_blind_gauntlet_results.json").read_text(encoding="utf-8"))
                g["models"]["Qwen/Qwen2.5-1.5B"]["arms"]["sp_E8_lin_3b"][field] = 1
                (d / "s106_blind_gauntlet_results.json").write_bytes(_resign_gauntlet(g))
                expect(code)
            g = json.loads((_THIS_DIR / "s106_blind_gauntlet_results.json").read_text(encoding="utf-8"))
            g["models"]["Qwen/Qwen2.5-1.5B"]["arms"]["sp_A16_lin_3b"]["exact_bpw"] = 3.5
            (d / "s106_blind_gauntlet_results.json").write_bytes(_resign_gauntlet(g))
            expect("CS08_BPW_EXCEEDED")
            shutil.copy2(_THIS_DIR / "s106_blind_gauntlet_results.json", d / "s106_blind_gauntlet_results.json")

            # Clean copy passes with the loud prereg status
            res = verifier.verify_gpu_eval_dir(d)
            self.assertTrue(res["ok"])
            self.assertEqual(res["prereg_status"], "UNVERIFIABLE_NOT_SHIPPED")

    def test_05_hygiene_no_leaks_crlf_or_weights(self) -> None:
        bad_tokens = (
            "/" + "home/",
            "~" + "/",
            "/" + "dev/" + "null",
            "4" + "-mode",
        )
        for p in sorted(_THIS_DIR.iterdir()):
            if not p.is_file():
                continue
            self.assertNotIn(p.suffix, (".bin", ".pt", ".pth", ".safetensors", ".gguf", ".ckpt"))
            raw = p.read_bytes()
            self.assertNotIn(b"\r", raw, f"CRLF in {p.name}")
            txt = raw.decode("utf-8")
            low = txt.lower()
            for tok in bad_tokens:
                self.assertNotIn(tok, low, f"Forbidden token in {p.name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
