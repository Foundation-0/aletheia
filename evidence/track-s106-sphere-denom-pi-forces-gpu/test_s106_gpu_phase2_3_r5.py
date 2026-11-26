#!/usr/bin/env python3
"""Top-level R5 CI discovery runner for Track S106 GPU Phase 2 + Phase 3 evidence bundles.

Pure standard library, zero bare asserts, 3-mode isolated Python (-I -B, -I -O -B, -I -B -W error) safe.
Loads and executes both frozen child R5 suites intact (gpu_eval/test_s106_gpu_eval_r5.py and
gpu_eval_phase3_h5_h6/test_s106_phase3_r5.py) plus top-level bundle hygiene checks.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve().parent


def _load_suite_module(mod_name: str, path: pathlib.Path) -> object:
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module spec from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestS106GpuBundleHygiene(unittest.TestCase):
    def test_01_top_level_hygiene_and_bundle_layout(self) -> None:
        bad = ("/" + "home/", "~" + "/", "/" + "dev/" + "null", "4" + "-mode")
        self.assertTrue((_HERE / "README.md").is_file())
        self.assertTrue((_HERE / "PREREG_SPHERE_PI_FORCES_V1.md").is_file())
        self.assertTrue((_HERE / "PREREG_SPHERE_PI_FORCES_AMENDMENT1_H5.md").is_file())
        self.assertTrue((_HERE / "PREREG_SPHERE_PI_FORCES_AMENDMENT2_H6.md").is_file())
        self.assertTrue((_HERE / "gpu_eval" / "verify_s106_gpu_eval.py").is_file())
        self.assertTrue((_HERE / "gpu_eval_phase3_h5_h6" / "verify_s106_phase3.py").is_file())
        v2_mod = _load_suite_module("s106_v2_top_chk", _HERE / "gpu_eval" / "verify_s106_gpu_eval.py")
        v3_mod = _load_suite_module("s106_v3_top_chk", _HERE / "gpu_eval_phase3_h5_h6" / "verify_s106_phase3.py")
        r2 = v2_mod.verify_gpu_eval_dir(_HERE / "gpu_eval")
        r3 = v3_mod.verify_phase3_dir(_HERE / "gpu_eval_phase3_h5_h6")
        self.assertEqual(r2["prereg_status"], "VERIFIED")
        self.assertEqual(r3["prereg_status"], "VERIFIED")
        self.assertEqual(r3["amendment_status"], "VERIFIED")
        for p in sorted(_HERE.rglob("*")):
            if not p.is_file():
                continue
            self.assertNotIn("__pycache__", p.parts, str(p))
            self.assertNotIn(p.suffix, (".bin", ".pt", ".pth", ".safetensors", ".gguf", ".ckpt", ".pyc"))
            raw = p.read_bytes()
            self.assertNotIn(b"\r", raw, str(p))
            low = raw.decode("utf-8").lower()
            for tok in bad:
                self.assertNotIn(tok, low, f"forbidden token in {p.relative_to(_HERE)}")


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    del pattern
    suite = unittest.TestSuite()
    suite.addTests(tests)
    m2 = _load_suite_module(
        "s106_gpu_eval_r5_mod",
        _HERE / "gpu_eval" / "test_s106_gpu_eval_r5.py",
    )
    m3 = _load_suite_module(
        "s106_phase3_r5_mod",
        _HERE / "gpu_eval_phase3_h5_h6" / "test_s106_phase3_r5.py",
    )
    suite.addTests(loader.loadTestsFromModule(m2))
    suite.addTests(loader.loadTestsFromModule(m3))
    return suite


if __name__ == "__main__":
    unittest.main(verbosity=2)
