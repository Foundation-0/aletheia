#!/usr/bin/env python3
"""Track S106 Phase 3 (H5/H6) R5 adversarial + hygiene test suite (pure stdlib)."""

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
from unittest import mock

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import verify_s106_phase3 as v3

_DATA = (
    "h5_locked_protocol.json", "s106_h5_results.json", "mlos_zone_b_h5_receipt.json",
    "h6_locked_protocol.json", "s106_h6_results.json", "mlos_zone_b_h6_receipt.json",
)


def _resign(obj: dict) -> bytes:
    body = {k: val for k, val in obj.items() if k != "result_sha256"}
    obj["result_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class TestS106Phase3R5(unittest.TestCase):
    def _copy(self, td: str) -> pathlib.Path:
        d = pathlib.Path(td)
        for n in _DATA:
            shutil.copy2(_HERE / n, d / n)
        return d

    def _expect(self, d: pathlib.Path, code: str) -> None:
        with self.assertRaises(v3.S106Phase3Error) as ctx:
            v3.verify_phase3_dir(d)
        self.assertEqual(ctx.exception.code, code)

    def test_01_live_verification_and_cli(self) -> None:
        res = v3.verify_phase3_dir(_HERE)
        self.assertTrue(res["ok"])
        recorded = json.loads((_HERE / "s106_h5_results.json").read_text(encoding="utf-8"))["preregistered_verdicts"]
        self.assertEqual(res["h5"]["verdicts"], {k: recorded[k]["verdict"] for k in ("H5a", "H5b")})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = v3.main(["--dir", str(_HERE), "--json"])
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(buf.getvalue())["ok"])

    def test_02_reject_tampered_inner_hash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s106_p3_t2_") as td:
            d = self._copy(td)
            obj = json.loads((d / "s106_h5_results.json").read_text(encoding="utf-8"))
            obj["elapsed_seconds"] = 1.0
            (d / "s106_h5_results.json").write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            self._expect(d, "INNER_SHA_MISMATCH")

    def test_03_reject_verdict_spoof_and_integrity_injection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s106_p3_t3_") as td:
            d = self._copy(td)
            obj = json.loads((d / "s106_h6_results.json").read_text(encoding="utf-8"))
            cur = obj["preregistered_verdicts"]["H6a"]["verdict"]
            obj["preregistered_verdicts"]["H6a"]["verdict"] = "CONFIRMED" if cur != "CONFIRMED" else "FALSIFIED"
            (d / "s106_h6_results.json").write_bytes(_resign(obj))
            self._expect(d, "VERDICT_MISMATCH")
            obj = json.loads((_HERE / "s106_h5_results.json").read_text(encoding="utf-8"))
            obj["models"]["Qwen/Qwen2.5-3B"]["arms"]["static_E8_30b"]["oob_groups"] = 2
            (d / "s106_h5_results.json").write_bytes(_resign(obj))
            shutil.copy2(_HERE / "s106_h6_results.json", d / "s106_h6_results.json")
            self._expect(d, "INTEGRITY_NONZERO")

    def test_04_reject_bpw_mismatch_temporal_and_dirty_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s106_p3_t4_") as td:
            d = self._copy(td)
            obj = json.loads((d / "s106_h5_results.json").read_text(encoding="utf-8"))
            obj["models"]["Qwen/Qwen2.5-1.5B"]["arms"]["flownoise_E8_30b"]["exact_bpw"] = 3.1
            (d / "s106_h5_results.json").write_bytes(_resign(obj))
            self._expect(d, "H5A_BPW_NOT_MATCHED")
            obj = json.loads((_HERE / "s106_h5_results.json").read_text(encoding="utf-8"))
            obj["completed_utc"] = "2000-01-01T00:00:00Z"
            (d / "s106_h5_results.json").write_bytes(_resign(obj))
            self._expect(d, "TEMPORAL_ORDER")
            shutil.copy2(_HERE / "s106_h5_results.json", d / "s106_h5_results.json")
            rec = json.loads((d / "mlos_zone_b_h6_receipt.json").read_text(encoding="utf-8"))
            rec["clean_hardware_run"] = False
            (d / "mlos_zone_b_h6_receipt.json").write_text(json.dumps(rec) + "\n", encoding="utf-8")
            self._expect(d, "DIRTY_RECEIPT")

    def test_06_receipt_forgery_links_and_remaining_guards(self) -> None:
        def _resign_receipt(obj: dict) -> bytes:
            body = {k: val for k, val in obj.items() if k != "receipt_sha256"}
            obj["receipt_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")

        with tempfile.TemporaryDirectory(prefix="s106_p3_t6_") as td:
            d = self._copy(td)

            # Zeroed receipt sha -> RECEIPT_SHA_MISMATCH
            rec = json.loads((d / "mlos_zone_b_h6_receipt.json").read_text(encoding="utf-8"))
            rec["receipt_sha256"] = "0" * 64
            (d / "mlos_zone_b_h6_receipt.json").write_text(json.dumps(rec) + "\n", encoding="utf-8")
            self._expect(d, "RECEIPT_SHA_MISMATCH")

            # Re-signed but forged telemetry -> RECEIPT_SHA_MISMATCH (self-sign no longer matches)
            rec = json.loads((_HERE / "mlos_zone_b_h6_receipt.json").read_text(encoding="utf-8"))
            rec["end_gpu_telemetry"]["temperature_gpu_c"] = 99
            (d / "mlos_zone_b_h6_receipt.json").write_text(json.dumps(rec) + "\n", encoding="utf-8")
            self._expect(d, "RECEIPT_SHA_MISMATCH")

            # Re-signed with wrong bound -> RECEIPT_BOUND_LINK_MISMATCH
            rec = json.loads((_HERE / "mlos_zone_b_h6_receipt.json").read_text(encoding="utf-8"))
            rec["bound_file_sha256"] = "1" * 64
            (d / "mlos_zone_b_h6_receipt.json").write_bytes(_resign_receipt(rec))
            self._expect(d, "RECEIPT_BOUND_LINK_MISMATCH")
            shutil.copy2(_HERE / "mlos_zone_b_h6_receipt.json", d / "mlos_zone_b_h6_receipt.json")

            # Protocol-file link tamper -> PROTOCOL_LINK_MISMATCH
            obj = json.loads((d / "s106_h6_results.json").read_text(encoding="utf-8"))
            obj["protocol_file_sha256"] = "4" * 64
            (d / "s106_h6_results.json").write_bytes(_resign(obj))
            self._expect(d, "PROTOCOL_LINK_MISMATCH")
            shutil.copy2(_HERE / "s106_h6_results.json", d / "s106_h6_results.json")

            # Protocol lock outside the receipt window -> PROTOCOL_OUTSIDE_RECEIPT_WINDOW
            proto = json.loads((d / "h6_locked_protocol.json").read_text(encoding="utf-8"))
            proto["locked_utc"] = "2000-01-01T00:00:00Z"
            (d / "h6_locked_protocol.json").write_text(json.dumps(proto, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            obj = json.loads((d / "s106_h6_results.json").read_text(encoding="utf-8"))
            obj["protocol_locked_utc"] = "2000-01-01T00:00:00Z"
            obj["protocol_file_sha256"] = hashlib.sha256((d / "h6_locked_protocol.json").read_bytes()).hexdigest()
            (d / "s106_h6_results.json").write_bytes(_resign(obj))
            # Re-bind the receipt to the tampered results file so the window check is reached
            rec = json.loads((d / "mlos_zone_b_h6_receipt.json").read_text(encoding="utf-8"))
            rec["bound_file_sha256"] = hashlib.sha256((d / "s106_h6_results.json").read_bytes()).hexdigest()
            (d / "mlos_zone_b_h6_receipt.json").write_bytes(_resign_receipt(rec))
            self._expect(d, "PROTOCOL_OUTSIDE_RECEIPT_WINDOW")
            shutil.copy2(_HERE / "h6_locked_protocol.json", d / "h6_locked_protocol.json")
            shutil.copy2(_HERE / "s106_h6_results.json", d / "s106_h6_results.json")
            shutil.copy2(_HERE / "mlos_zone_b_h6_receipt.json", d / "mlos_zone_b_h6_receipt.json")

            # Prereg constant mismatch (monkeypatched) -> PREREG_MISMATCH
            orig = v3.PREREG_SHA256
            try:
                v3.PREREG_SHA256 = "5" * 64
                self._expect(d, "PREREG_MISMATCH")
            finally:
                v3.PREREG_SHA256 = orig

            # H6c arm-count / n_params pins
            obj = json.loads((d / "s106_h6_results.json").read_text(encoding="utf-8"))
            for r in obj["h6c_runs"]:
                r["n_params"] = 12345
            (d / "s106_h6_results.json").write_bytes(_resign(obj))
            self._expect(d, "H6C_N_PARAMS_MISMATCH")
            shutil.copy2(_HERE / "s106_h6_results.json", d / "s106_h6_results.json")

            # Global integrity tamper
            obj = json.loads((d / "s106_h6_results.json").read_text(encoding="utf-8"))
            obj["global_integrity"]["total_syndrome_errors"] = 1
            (d / "s106_h6_results.json").write_bytes(_resign(obj))
            self._expect(d, "GLOBAL_INTEGRITY_MISMATCH")
            shutil.copy2(_HERE / "s106_h6_results.json", d / "s106_h6_results.json")

            # Clean copy still passes
            res = v3.verify_phase3_dir(d)
            self.assertTrue(res["ok"])

    def test_07_amendment_flags_require_full_sha256(self) -> None:
        # Not supplied -> loudly UNVERIFIABLE_NOT_SHIPPED (never silently VERIFIED).
        res = v3.verify_phase3_dir(_HERE)
        self.assertEqual(res["amendment_status"], "UNVERIFIABLE_NOT_SHIPPED")
        with tempfile.TemporaryDirectory(prefix="s106_p3_t7_") as td:
            d = self._copy(td)
            # Wrong bytes -> AMENDMENT_FILE_SHA_MISMATCH.
            bad = pathlib.Path(td) / "amend1.md"
            bad.write_bytes(b"not the amendment")
            with self.assertRaises(v3.S106Phase3Error) as ctx:
                v3.verify_phase3_dir(d, amendment1_path=bad)
            self.assertEqual(ctx.exception.code, "AMENDMENT_FILE_SHA_MISMATCH")
            # Full 64-hex equality: a file matching the pinned full sha passes...
            good1 = pathlib.Path(td) / "amend1_good.md"
            good1.write_bytes(b"amendment one bytes")
            good2 = pathlib.Path(td) / "amend2_good.md"
            good2.write_bytes(b"amendment two bytes")
            with mock.patch.object(v3, "AMEND1_SHA256", hashlib.sha256(b"amendment one bytes").hexdigest()), \
                 mock.patch.object(v3, "AMEND2_SHA256", hashlib.sha256(b"amendment two bytes").hexdigest()), \
                 mock.patch.object(v3, "_verify_one", return_value={"verdicts": {}, "arms": 0}):
                res2 = v3.verify_phase3_dir(d, amendment1_path=good1, amendment2_path=good2)
                self.assertEqual(res2["amendment_status"], "VERIFIED")
                # ...while a one-byte-different near miss fails (the old 16-hex prefix check
                # could not distinguish these; the full-sha check does).
                near = pathlib.Path(td) / "amend1_near.md"
                near.write_bytes(b"amendment one bytes!")
                with self.assertRaises(v3.S106Phase3Error) as ctx2:
                    v3.verify_phase3_dir(d, amendment1_path=near, amendment2_path=good2)
                self.assertEqual(ctx2.exception.code, "AMENDMENT_FILE_SHA_MISMATCH")
            # CLI surface: --amendment1/2 flags wired through.
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = v3.main(["--dir", str(d), "--json", "--amendment1", str(bad)])
            self.assertEqual(rc, 1)

    def test_05_hygiene(self) -> None:
        bad = ("/" + "home/", "~" + "/", "/" + "dev/" + "null", "4" + "-mode")
        for p in sorted(_HERE.iterdir()):
            if not p.is_file():
                continue
            self.assertNotIn(p.suffix, (".bin", ".pt", ".pth", ".safetensors", ".gguf", ".ckpt"))
            raw = p.read_bytes()
            self.assertNotIn(b"\r", raw, p.name)
            low = raw.decode("utf-8").lower()
            for tok in bad:
                self.assertNotIn(tok, low, p.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
