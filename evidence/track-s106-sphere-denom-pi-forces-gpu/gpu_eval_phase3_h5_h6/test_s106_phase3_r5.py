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
