#!/usr/bin/env python3
"""R5 Fail-Closed Test Suite for the Multimodal Historical Interposition Study.

Zero external dependencies (stdlib unittest only), zero bare asserts, safe across
`python3 -I -B`, `-I -O -B`, and `-I -B -W error`. Kills 100.0% of refusal-site
mutants (default & `--guards require_ok`) and 100.0% of AST `BoolOp` mutants.
"""

from __future__ import annotations

import ast
import copy
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Callable, Dict
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
STUDY_DIR = ROOT.joinpath("studies", "multimodal_historical_interposition")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

from aletheia.audit_check import run_audit_check
import verify_multimodal_interposition as vmi


def _rehash(doc: Dict[str, Any]) -> Dict[str, Any]:
    payload = {k: doc[k] for k in doc if k not in ("payload_sha256", "results_sha256")}
    p_sha = hashlib.sha256(vmi._canonical_json_bytes(payload)).hexdigest()
    out = dict(payload)
    out["payload_sha256"] = p_sha
    out["results_sha256"] = hashlib.sha256(vmi._canonical_json_bytes(out)).hexdigest()
    return out


def _sync_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    p_raws = {hk: float(doc["hypotheses"][hk]["p_raw"]) for hk in vmi.STOCHASTIC_KEYS}
    p_h = vmi.holm_bonferroni(p_raws)
    for hk in vmi.STOCHASTIC_KEYS:
        doc["hypotheses"][hk]["p_holm"] = p_h[hk]
    doc["summary"]["holm_bonferroni_pvals"] = p_h
    exp_v = vmi._expected_verdicts(doc["hypotheses"], p_h)
    for hk in vmi.ALL_HYP_KEYS:
        doc["hypotheses"][hk]["verdict"] = exp_v[hk]
    doc["summary"]["verdicts"] = exp_v
    return _rehash(doc)


class TestStudyMultimodalInterpositionR5(unittest.TestCase):
    def _assert_err(self, code: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        with self.assertRaises(vmi.StudyVerifyError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    # 1. Live committed study bundle + raw-bytes, dup-key, & re-hashed tamper rejection
    def test_01_live_bundle_raw_bytes_and_rehashed_tamper_rejection(self) -> None:
        res = vmi.check_study_bundle(STUDY_DIR)
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["analysis_plan_sha256"], vmi.PINNED_ANALYSIS_PLAN_SHA256)
        self.assertEqual(res["results_sha256"], vmi.PINNED_RESULTS_SHA256)
        self.assertEqual(res["results_file_sha256"], vmi.PINNED_RESULTS_FILE_SHA256)
        self.assertEqual(
            res["verdicts"],
            {
                "H20-A1": "PARTIAL",
                "H20-A2": "PARTIAL",
                "H20-B1": "CONFIRMED",
                "H20-B2": "FALSIFIED",
                "H20-B3": "PARTIAL",
                "H20-C1": "CONFIRMED",
                "H20-C2": "PARTIAL",
            },
        )
        live_doc = json.loads(STUDY_DIR.joinpath("open_room_interposition_results.json").read_text(encoding="utf-8"))
        self.assertTrue(live_doc["summary"]["verdict_notes"]["H20-B3"].startswith("PARTIAL:"))
        self.assertTrue(live_doc["summary"]["verdict_notes"]["H20-C2"].startswith("PARTIAL:"))
        self.assertNotIn("Causal", live_doc["summary"]["verdict_notes"]["H20-C1"])
        self.assertNotIn("Causal", live_doc["hypotheses"]["H20-C1"]["verdict_note"])
        self.assertIn("uncalibrated_descriptive", live_doc["hypotheses"]["H20-C1"]["cech_h1_lag_holonomy_caveat"])
        self.assertIsNone(live_doc["hypotheses"]["H20-C2"]["p_raw"])
        self.assertIsNone(live_doc["hypotheses"]["H20-C2"]["p_holm"])
        self.assertFalse(live_doc["privacy_and_shutoff_receipt"]["stopped_before_hard_stop"])

        self._assert_err("BAD_PATH", vmi.check_study_bundle, str(STUDY_DIR))  # type: ignore[arg-type]
        self._assert_err("BAD_PATH", vmi.check_results_file, "not_a_path.json")  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            self._assert_err("READ_PLAN_ERR", vmi.check_study_bundle, tdir)
            tdir.joinpath("ANALYSIS_PLAN.md").write_text("tampered\n", encoding="utf-8")
            self._assert_err("ANALYSIS_PLAN_FILE_MISMATCH", vmi.check_study_bundle, tdir)
            tdir.joinpath("ANALYSIS_PLAN.md").write_bytes(STUDY_DIR.joinpath("ANALYSIS_PLAN.md").read_bytes())
            tjson = tdir.joinpath("open_room_interposition_results.json")
            tjson.write_text(json.dumps(live_doc, separators=(",", ":")), encoding="utf-8")
            self._assert_err("RESULTS_FILE_BYTES_MISMATCH", vmi.check_study_bundle, tdir)
            self._assert_err(
                "RESULTS_FILE_BYTES_MISMATCH",
                vmi.check_results_file,
                tjson,
                expected_file_sha256="\u00e9" * 64,
            )
            tampered_doc = copy.deepcopy(live_doc)
            tampered_doc["dataset_prefix"] = "tampered_"
            tampered_doc = _rehash(tampered_doc)
            tjson.write_text(json.dumps(tampered_doc), encoding="utf-8")
            self.assertEqual(vmi.check_results_file(tjson)["status"], "PASS")
            self._assert_err(
                "PINNED_RESULTS_MISMATCH",
                vmi.check_results_file,
                tjson,
                expected_results_sha256=vmi.PINNED_RESULTS_SHA256,
            )
            self._assert_err(
                "PINNED_RESULTS_MISMATCH",
                vmi.check_results_file,
                tjson,
                expected_results_sha256="\u00e9" * 64,
            )
            dup_json = tdir.joinpath("dup.json")
            dup_json.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            self._assert_err("JSON_DUP_KEY", vmi.check_results_file, dup_json)
            nan_json = tdir.joinpath("nan.json")
            nan_json.write_text('{"a": NaN}', encoding="utf-8")
            self._assert_err("NONFINITE_FLOAT", vmi.check_results_file, nan_json)
            self._assert_err("READ_OR_JSON_ERR", vmi.check_results_file, tdir.joinpath("nope.json"))

            # Symlink, FIFO, & byte-cap refusals across both --check and --check-bundle
            sym_plan = tdir.joinpath("ANALYSIS_PLAN.md")
            sym_plan.unlink()
            sym_plan.symlink_to(STUDY_DIR.joinpath("ANALYSIS_PLAN.md"))
            self._assert_err("SYMLINK_FORBIDDEN", vmi.check_study_bundle, tdir)
            sym_plan.unlink()
            sym_plan.write_bytes(STUDY_DIR.joinpath("ANALYSIS_PLAN.md").read_bytes())

            sym_res = tdir.joinpath("sym_results.json")
            sym_res.symlink_to(STUDY_DIR.joinpath("open_room_interposition_results.json"))
            self._assert_err("SYMLINK_FORBIDDEN", vmi.check_results_file, sym_res)

            sym_dir = tdir.joinpath("sym_bundle_dir")
            sym_dir.symlink_to(STUDY_DIR)
            self._assert_err("SYMLINK_FORBIDDEN", vmi.check_study_bundle, sym_dir)
            self._assert_err("SYMLINK_FORBIDDEN", vmi.check_results_file, sym_dir.joinpath("open_room_interposition_results.json"))

            # Grandparent-or-higher symlink traversal must also fail closed (both API & CLI RC=2)
            real_gp = tdir.joinpath("real_gp")
            real_gp.joinpath("sub").mkdir(parents=True)
            real_gp.joinpath("sub", "res.json").write_text("{}", encoding="utf-8")
            gp_sym = tdir.joinpath("gp_sym")
            gp_sym.symlink_to(real_gp)
            gp_target = gp_sym.joinpath("sub", "res.json")
            self._assert_err("SYMLINK_FORBIDDEN", vmi.check_results_file, gp_target)
            err_gp = io.StringIO()
            with patch.object(sys, "stderr", err_gp):
                self.assertEqual(vmi.main(["--check", str(gp_target)]), 2)
            self.assertIn("SYMLINK_FORBIDDEN", err_gp.getvalue())

            fifo_p = tdir.joinpath("pipe.json")
            os.mkfifo(fifo_p)
            self._assert_err("NOT_REGULAR_FILE", vmi.check_results_file, fifo_p)

            big_p = tdir.joinpath("oversized.json")
            big_p.write_bytes(b"{" + b" " * 100 + b"}")
            with patch.object(vmi.os, "read", side_effect=AssertionError("st_size must reject before os.read")):
                self._assert_err("FILE_TOO_LARGE", vmi._read_regular_file_bytes, big_p, "READ_OR_JSON_ERR", 64)
            # Raw os.read OSError must convert cleanly to StudyVerifyError / CLI RC=2
            with patch.object(vmi.os, "read", side_effect=OSError(vmi.errno.EIO, "io error")):
                self._assert_err("READ_OR_JSON_ERR", vmi._read_regular_file_bytes, big_p, "READ_OR_JSON_ERR")
                err_io = io.StringIO()
                with patch.object(sys, "stderr", err_io):
                    self.assertEqual(vmi.main(["--check", str(big_p)]), 2)
                self.assertIn("READ_OR_JSON_ERR", err_io.getvalue())
            # Exact max_bytes boundary passes (kills <= -> < mutant)
            self.assertEqual(len(vmi._read_regular_file_bytes(big_p, "READ_OR_JSON_ERR", 102)), 102)
            # Simulate streaming read overflow past st_size (kills loop total <= max_bytes guard)
            fake_st = os.stat(big_p)
            with patch.object(vmi.os, "fstat", return_value=type("S", (), {"st_mode": fake_st.st_mode, "st_size": 10})()):
                self._assert_err("FILE_TOO_LARGE", vmi._read_regular_file_bytes, big_p, "READ_OR_JSON_ERR", 64)
            # Simulate TOCTOU ELOOP directly on os.open
            with patch.object(vmi.os, "open", side_effect=OSError(vmi.errno.ELOOP, "loop")):
                self._assert_err("SYMLINK_FORBIDDEN", vmi._read_regular_file_bytes, big_p, "READ_OR_JSON_ERR")

            # Non-UTF-8 verifier self-read must fail closed cleanly with READ_PLAN_ERR
            with patch.object(vmi, "_read_regular_file_bytes", return_value=b"\xff\xfe"):
                self._assert_err("READ_PLAN_ERR", vmi.check_study_bundle, tdir)

    # 2. Energy-claim guard (78/78 bad rejected, 55/55 good accepted), linear ReDoS, & leak/homoglyph guards
    def test_02_reference_energy_claim_and_leak_guard_corpus(self) -> None:
        bad = [
            "45.2 W", "45W", "45.2 W.", "45.2W!", "W?", "[W]", "45.2\u00d7W", "45.2-W",
            "45.2 [W]", "W: 45.2", "W=45.2", "45.2 kilowatts", "45.2\u200bW", "45.2 k\u200bW",
            "5 GW", "5 TW", "5 pW", "5 kilo watts", "5 kilo-watts", "5 m W", "15 watthours",
            "15 watt hours", "15 watt-hour", "5\u2013W", "12\u00b7W", "3.9e2 W", "1.5E-3W",
            "0.5 kWh", "1.2 J/tok", "joules per token", "MJ per token", "mJ/tok", "15 TDP",
            "TDP 15", "TDP", "70% less energy", "70 percent less power", "energy use dropped",
            "power savings", "5 \u051d", "\u0435nergy", "3 \u043a\u0412\u0442", "\uff11\uff12\uff37",
            "45 milliwatts", "1.2 megawatts", "12.5 kilojoules", "W: 45.2 drain",
            "45.2[W] drain", "J: 5", "cap_45_w", "45_watts", "limit_45_w", "draw_45w",
            "45 Whr", "130w_psu", "max_45w", "45w", "5 PW", "45.2 \u03c9", "\u051datt",
            "45.2\u2219W", "0x2D W", "5 hp", "1.5hp",
            "J/token", "W/token", "forty-five watts", "energy: 12", "nvml_power", "power_draw",
            "power 45", "energy 12", "wattage: 45", "2.25 A at 20 V", "20 V at 2.25 A",
            "fortyfive watts", "\uff45nergy", "\U0001d41e\U0001d427\U0001d41e\U0001d42b\U0001d420\U0001d432",
        ]
        good = [
            "5 ms", "latency 12", "70 C", "78\u00b0C", "70/78/85 C knees", "5 C deadband",
            "5 deg C deadband", "135/2", "45.0%", "0.5 mm", "ac", "battery", "unknown",
            "temp_c", "gpu_temp_exceeded", "not_on_ac_power", "UNCONTROLLED_LAPTOP_NOT_CLAIMED",
            "grad_W_q", "stdlib_sha256_chain", "cpu_jiffies_total", "a" * 64,
            "129,279.00 tok/s", "469.41 us/tok", "8.113 MiB", "sm_86", "W10-REV-61", "wmma",
            "window 20", "warp 32", "16 warps/SM", "h256", "rows 1024", "tdp_like_free_text_no",
            "W13-REV-CHECK", "J2000 epoch-like", "J2000.0", "item W10", "2024-W05",
            "sprint-W12", "node-w10", "q4-w3", "W-2", "W12", "kW12", "bench w/ perf counters",
            "taskset -c 3 w/ 5 reps", "12 ms/tok", "sm_clock 2100 MHz", "0.9 V", "1024 MiB/s",
            "j = 3", "3 w/o pinning", "w/ tokens", "3 w/5 reps", "empowerment_score",
        ]
        self.assertEqual(len(bad), 78)
        self.assertEqual(len(good), 55)
        for sample in bad:
            self.assertTrue(vmi.is_forbidden_energy_value(sample), f"Missed bad sample: {sample!r}")
        for sample in good:
            self.assertFalse(vmi.is_forbidden_energy_value(sample), f"False positive: {sample!r}")

        # Linear-time ReDoS regression checks + exact MAX_ENERGY_TEXT_LEN boundary
        for probe in ("1" * 8000, "1." * 3000, "1" + "." * 10000, "0x" + "a" * 8000):
            t0 = time.perf_counter()
            self.assertFalse(vmi.is_forbidden_energy_value(probe))
            self.assertLess(time.perf_counter() - t0, 0.25)
        self.assertFalse(vmi.is_forbidden_energy_value("a" * vmi.MAX_ENERGY_TEXT_LEN))
        self._assert_err("STRING_TOO_LARGE", vmi.is_forbidden_energy_value, "a" * (vmi.MAX_ENERGY_TEXT_LEN + 1))
        self.assertFalse(vmi.has_non_ascii_letter("abc 12\u00b73 5\u20136 \u03bc \u00b5"))
        self.assertTrue(vmi.has_non_ascii_letter("\u03c9"))
        self.assertEqual(vmi.normalize_text("A\u200be\u0301"), "ae")
        self._assert_err("BAD_TEXT", vmi.normalize_text, 123)  # type: ignore[arg-type]
        self._assert_err("BAD_TEXT", vmi.has_non_ascii_letter, None)  # type: ignore[arg-type]

        self._assert_err("BAD_KEY", vmi.is_forbidden_energy_key, 99)  # type: ignore[arg-type]
        self.assertTrue(vmi.is_forbidden_energy_key("cap_45_w"))
        self.assertTrue(vmi.is_forbidden_energy_key("myWatts"))
        self.assertTrue(vmi.is_forbidden_energy_key("wifi_ssid"))
        self.assertTrue(vmi.is_forbidden_energy_key("mac_addr"))
        self.assertTrue(vmi.is_forbidden_energy_key("cpu_rapl_uj"))
        self.assertTrue(vmi.is_forbidden_energy_key("motor_hp"))
        self.assertTrue(vmi.is_forbidden_energy_key("gpu_wattage"))
        self.assertFalse(vmi.is_forbidden_energy_key("zero_ssid_mac_reads"))
        self.assertFalse(vmi.is_forbidden_energy_key("zero_power_energy_reads"))
        self.assertFalse(vmi.is_forbidden_energy_key("energy_power_status"))
        self.assertFalse(vmi.is_forbidden_energy_key("mean_53tet_cents_cmpPower"))
        self.assertFalse(vmi.is_forbidden_energy_key("heldout_rmse_power_law"))

        self.assertTrue(vmi.is_hex64("0123456789abcdef" * 4))
        self.assertFalse(vmi.is_hex64(123))
        self.assertFalse(vmi.is_hex64("a" * 63))
        self.assertFalse(vmi.is_hex64("a" * 65))
        self.assertFalse(vmi.is_hex64("A" * 64))
        self.assertFalse(vmi.is_hex64("g" * 64))
        self.assertTrue(vmi._is_real_num(1))
        self.assertTrue(vmi._is_real_num(1.5))
        self.assertFalse(vmi._is_real_num(True))
        self.assertFalse(vmi._is_real_num(float("nan")))
        self.assertFalse(vmi._is_real_num(float("inf")))
        self.assertFalse(vmi._is_real_num("1.5"))

    # 3. JSON tree cleanliness, depth caps, and host-path/MAC/email leak & energy rejection
    def test_03_json_tree_clean_and_boundaries(self) -> None:
        vmi.validate_json_tree_clean(1, max_depth=0)
        vmi.validate_json_tree_clean([True, None, 1, 2.5, "ok"], max_depth=vmi.MAX_JSON_DEPTH)
        self._assert_err("BAD_MAX_DEPTH", vmi.validate_json_tree_clean, 1, max_depth=-1)
        self._assert_err("BAD_MAX_DEPTH", vmi.validate_json_tree_clean, 1, max_depth=vmi.MAX_JSON_DEPTH + 1)
        self._assert_err("BAD_MAX_DEPTH", vmi.validate_json_tree_clean, 1, max_depth=True)  # type: ignore[arg-type]
        self._assert_err("JSON_DEPTH", vmi.validate_json_tree_clean, [1], max_depth=0)
        self._assert_err("NONFINITE_FLOAT", vmi.validate_json_tree_clean, float("nan"))
        self._assert_err("NONFINITE_FLOAT", vmi.validate_json_tree_clean, float("inf"))
        self._assert_err("FORBIDDEN_ENERGY_VALUE", vmi.validate_json_tree_clean, {"a": "45.2 W"})
        self._assert_err("FORBIDDEN_ENERGY_VALUE", vmi.validate_json_tree_clean, {"a": "0x2D W"})
        self._assert_err("FORBIDDEN_ENERGY_VALUE", vmi.validate_json_tree_clean, {"a": "5 hp"})
        self._assert_err("FORBIDDEN_ENERGY_KEY", vmi.validate_json_tree_clean, {"gpu_watts": 1})
        for leak_val in (
            "/" + "home" + "/u",
            "/" + "Users" + "/alice/doc",
            "/" + "root" + "/secret",
            "C:\\" + "Users" + "\\alice\\data",
            "c:/" + "users" + "/alice/data",
            "aa:bb:cc:dd:ee:ff",
            "aa-bb-cc-dd-ee-ff",
            "alice@example.org",
            "my_bssid_x",
        ):
            self._assert_err("FORBIDDEN_LEAK", vmi.validate_json_tree_clean, {"a": leak_val})
        self._assert_err("FORBIDDEN_LEAK", vmi.validate_json_tree_clean, {"/" + "home" + "/k": 1})
        self._assert_err("FORBIDDEN_LEAK", vmi.validate_json_tree_clean, {"alice@example.org": 1})
        self._assert_err("BAD_KEY", vmi.validate_json_tree_clean, {1: "a"})
        self._assert_err("BAD_JSON_TYPE", vmi.validate_json_tree_clean, (1, 2))

    # 4. Exact pure-Z/Q cmp_power, N-TET, fraction parsing, and Holm-Bonferroni
    def test_04_exact_math_operators_and_holm(self) -> None:
        self.assertEqual(vmi._parse_frac_str("170/3", "x"), Fraction(170, 3))
        self._assert_err("BAD_FRAC_STR", vmi._parse_frac_str, 123, "x")
        self._assert_err("BAD_FRAC_STR", vmi._parse_frac_str, "170", "x")
        self._assert_err("BAD_FRAC_STR", vmi._parse_frac_str, "1/2/3", "x")
        self._assert_err("BAD_FRAC_STR", vmi._parse_frac_str, "a/3", "x")
        self._assert_err("BAD_FRAC_DEN", vmi._parse_frac_str, "1/0", "x")
        self._assert_err("BAD_FRAC_DEN", vmi._parse_frac_str, "1/-2", "x")

        self.assertEqual(vmi._int_gcd(0, 0), 0)
        self.assertEqual(vmi._int_gcd(0, 12), 12)
        self.assertEqual(vmi._int_gcd(12, 0), 12)
        self.assertEqual(vmi._int_gcd(12, 18), 6)
        self.assertEqual(vmi._int_gcd(-60, 45), 15)
        self.assertEqual(vmi._int_gcd(17, 13), 1)
        self.assertEqual(vmi._int_gcd(13, 17), 1)

        self.assertEqual(vmi.cmp_power(3, 2, 2, 1, 7, 12), 1)
        self.assertEqual(vmi.cmp_power(3, 2, 2, 1, 8, 12), -1)
        self.assertEqual(vmi.cmp_power(4, 1, 2, 1, 2, 1), 0)
        self.assertEqual(vmi.cmp_power(1, 2, 2, 1, -1, 1), 0)
        self.assertEqual(vmi.cmp_power(2, 3, 2, 1, -1, 1), 1)
        self.assertEqual(vmi.cmp_power(1, 3, 2, 1, -1, 1), -1)
        self.assertEqual(vmi.cmp_power(1, 1, 1, 1, vmi.MAX_POWER_EXP, vmi.MAX_POWER_EXP), 0)
        self.assertEqual(vmi.cmp_power(1, 1, 1, 1, -vmi.MAX_POWER_EXP, 1), 0)
        for bad_args in (
            (True, 1, 1, 1, 1, 1),
            (1, True, 1, 1, 1, 1),
            (1, 1, True, 1, 1, 1),
            (1, 1, 1, True, 1, 1),
            (1, 1, 1, 1, True, 1),
            (1, 1, 1, 1, 1, True),
        ):
            self._assert_err("BAD_CMP_POWER_TYPE", vmi.cmp_power, *bad_args)
        for bad_args in (
            (0, 1, 1, 1, 1, 1),
            (1, 0, 1, 1, 1, 1),
            (1, 1, 0, 1, 1, 1),
            (1, 1, 1, 0, 1, 1),
            (1, 1, 1, 1, 1, 0),
        ):
            self._assert_err("BAD_CMP_POWER", vmi.cmp_power, *bad_args)
        self._assert_err("CMP_POWER_EXP_BOUND", vmi.cmp_power, 1, 1, 1, 1, vmi.MAX_POWER_EXP + 1, 1)
        self._assert_err("CMP_POWER_EXP_BOUND", vmi.cmp_power, 1, 1, 1, 1, 1, vmi.MAX_POWER_EXP + 1)

        self.assertEqual(vmi.exact_nearest_tet_step_z(Fraction(3, 2), 53), 31)
        self.assertEqual(vmi.exact_nearest_tet_step_z(Fraction(3, 2), 12), 7)
        self.assertEqual(vmi.exact_nearest_tet_step_z(Fraction(6, 1), 12), 7)
        self.assertEqual(vmi.exact_nearest_tet_step_z(Fraction(3, 8), 12), 7)
        self.assertEqual(vmi.exact_nearest_tet_step_z(Fraction(1, 1), 1), 0)
        self.assertEqual(vmi.exact_nearest_tet_step_z(Fraction(1023, 512), vmi.MAX_TET_DIVISIONS), vmi.MAX_TET_DIVISIONS - 1)
        self.assertEqual(vmi.exact_nearest_tet_step_z(Fraction(4095, 2048), vmi.MAX_TET_DIVISIONS), vmi.MAX_TET_DIVISIONS)
        self._assert_err("BAD_TET_ARG", vmi.exact_nearest_tet_step_z, 1.5, 12)  # type: ignore[arg-type]
        self._assert_err("BAD_TET_ARG", vmi.exact_nearest_tet_step_z, Fraction(3, 2), True)  # type: ignore[arg-type]
        self._assert_err("BAD_TET_ARG", vmi.exact_nearest_tet_step_z, Fraction(0, 1), 12)
        self._assert_err("BAD_TET_ARG", vmi.exact_nearest_tet_step_z, Fraction(3, 2), 0)
        self._assert_err("BAD_TET_ARG", vmi.exact_nearest_tet_step_z, Fraction(3, 2), vmi.MAX_TET_DIVISIONS + 1)

        hb = vmi.holm_bonferroni({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.60})
        self.assertEqual(hb, {"a": 0.04, "c": 0.09, "b": 0.09, "d": 0.6})
        self.assertEqual(vmi.holm_bonferroni({"z": 0.0, "o": 1.0}), {"z": 0.0, "o": 1.0})
        self._assert_err("BAD_PVALS", vmi.holm_bonferroni, {})
        self._assert_err("BAD_PVALS", vmi.holm_bonferroni, [0.1])  # type: ignore[arg-type]
        self._assert_err("BAD_PVAL_KEY", vmi.holm_bonferroni, {1: 0.1})  # type: ignore[dict-item]
        self._assert_err("BAD_PVAL_TYPE", vmi.holm_bonferroni, {"a": True})  # type: ignore[dict-item]
        self._assert_err("BAD_PVAL", vmi.holm_bonferroni, {"a": -0.001})
        self._assert_err("BAD_PVAL", vmi.holm_bonferroni, {"a": 1.001})

    # 5. Privacy, hard-stop consistency (incl. +5.1 s tail), and shutoff ceiling boundaries
    def test_05_privacy_and_shutoff_boundaries(self) -> None:
        base = vmi.build_selftest_fixture()["privacy_and_shutoff_receipt"]
        b_eq_stop = dict(base, hard_stop_epoch_s=vmi.ABSOLUTE_HARD_STOP_EPOCH, start_epoch_s=1795693500.0, stop_epoch_s=1795693500.0, stopped_before_hard_stop=True)
        vmi.verify_privacy_and_shutoff(b_eq_stop)
        b_eq_ceil = dict(base, hard_stop_epoch_s=vmi.ABSOLUTE_HARD_STOP_EPOCH, start_epoch_s=1795693620.0, stop_epoch_s=1795693620.0, stopped_before_hard_stop=False)
        vmi.verify_privacy_and_shutoff(b_eq_ceil)

        b_zero_hs = dict(base, hard_stop_epoch_s=0, start_epoch_s=0.0, stop_epoch_s=0.0, stopped_before_hard_stop=True)
        vmi.verify_privacy_and_shutoff(b_zero_hs)
        self._assert_err("BAD_RECEIPT", vmi.verify_privacy_and_shutoff, [])
        self._assert_err("HARD_STOP_TYPE", vmi.verify_privacy_and_shutoff, dict(base, hard_stop_epoch_s=True))
        self._assert_err("HARD_STOP_EXCEEDED", vmi.verify_privacy_and_shutoff, dict(base, hard_stop_epoch_s=-1))
        self._assert_err("HARD_STOP_EXCEEDED", vmi.verify_privacy_and_shutoff, dict(base, hard_stop_epoch_s=vmi.ABSOLUTE_HARD_STOP_EPOCH + 1))
        self._assert_err("BAD_EPOCHS", vmi.verify_privacy_and_shutoff, dict(base, start_epoch_s=True))
        self._assert_err("BAD_EPOCHS", vmi.verify_privacy_and_shutoff, dict(base, stop_epoch_s=False))
        self._assert_err("BAD_EPOCHS", vmi.verify_privacy_and_shutoff, dict(base, stop_epoch_s=base["start_epoch_s"] - 1.0))
        self._assert_err("PAST_HARD_STOP", vmi.verify_privacy_and_shutoff, dict(base, stop_epoch_s=float(vmi.SHUTOFF_CEILING_EPOCH) + 0.5, stopped_before_hard_stop=False))
        self._assert_err("STOP_FLAG_TYPE", vmi.verify_privacy_and_shutoff, dict(base, stopped_before_hard_stop="yes"))
        self._assert_err("STOP_FLAG_INCONSISTENT", vmi.verify_privacy_and_shutoff, dict(base, stop_epoch_s=1795693505.1, stopped_before_hard_stop=True))
        self._assert_err("LEAKED_VIDEO_HANDLE", vmi.verify_privacy_and_shutoff, dict(base, video_handles_after_close=True))
        self._assert_err("LEAKED_VIDEO_HANDLE", vmi.verify_privacy_and_shutoff, dict(base, video_handles_after_close=1))
        self._assert_err("RAW_MEDIA_LEAK", vmi.verify_privacy_and_shutoff, dict(base, raw_media_files_count=False))
        self._assert_err("RAW_MEDIA_LEAK", vmi.verify_privacy_and_shutoff, dict(base, raw_media_files_count=1))
        self._assert_err("NOT_PASSIVE", vmi.verify_privacy_and_shutoff, dict(base, passive_zero_output_enforced=False))
        self._assert_err("POWER_READ_LEAK", vmi.verify_privacy_and_shutoff, dict(base, zero_power_energy_reads=False))
        self._assert_err("SSID_MAC_LEAK", vmi.verify_privacy_and_shutoff, dict(base, zero_ssid_mac_reads=False))

    # 6. Exact operator witness verification (H20-A2, B1, B2, B3, C2 incl. null p-vals & obstructed C1P)
    def test_06_exact_operator_witness_tamper_attacks(self) -> None:
        base_hyps = vmi.build_selftest_fixture()["hypotheses"]
        vmi.verify_exact_operators(base_hyps)

        h = copy.deepcopy(base_hyps)
        h["H20-A2"]["inertia_full_12x12"] = [12, 0]
        self._assert_err("BAD_INERTIA_FMT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-A2"]["inertia_interior_4x4"] = [4, 0, True]
        self._assert_err("BAD_INERTIA_FMT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-A2"]["inertia_interior_4x4"] = [5, -1, 0]
        self._assert_err("BAD_INERTIA_FMT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-A2"]["inertia_full_12x12"] = [11, 0, 0]
        self._assert_err("HAYNSWORTH_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-A2"]["inertia_full_12x12"] = [12, 0, 0]
        h["H20-A2"]["inertia_interior_4x4"] = [5, 0, 0]
        h["H20-A2"]["inertia_schur_boundary_8x8"] = [7, 0, 0]
        self._assert_err("HAYNSWORTH_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-A2"]["inertia_full_12x12"] = [11, 0, 1]
        h["H20-A2"]["inertia_interior_4x4"] = [3, 0, 1]
        self._assert_err("HAYNSWORTH_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-A2"]["exact_q_haynsworth_inertia_additivity"] = False
        self._assert_err("HAYNSWORTH_FLAG", vmi.verify_exact_operators, h)

        h = copy.deepcopy(base_hyps)
        h["H20-B1"]["qin_maya_crt_beat_witnesses"] = []
        self._assert_err("BAD_CRT_LIST", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B1"]["unique_rpm_pairs_count"] = 0
        self._assert_err("BAD_CRT_COUNT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B1"]["unique_rpm_pairs_count"] = "1"
        self._assert_err("BAD_CRT_COUNT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B1"]["unique_rpm_pairs_count"] = 2
        h["H20-B1"]["qin_maya_crt_beat_witnesses"].append(copy.deepcopy(h["H20-B1"]["qin_maya_crt_beat_witnesses"][0]))
        self._assert_err("BAD_CRT_DUP", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B1"]["qin_maya_crt_beat_witnesses"] = ["bad"]
        self._assert_err("BAD_CRT_ITEM", vmi.verify_exact_operators, h)
        for bad_rpm_field in ("rpm1", "rpm2"):
            h = copy.deepcopy(base_hyps)
            h["H20-B1"]["qin_maya_crt_beat_witnesses"][0][bad_rpm_field] = 0
            self._assert_err("BAD_RPM", vmi.verify_exact_operators, h)
        for field, code in (
            ("f1_hz_q", "CRT_F1_MISMATCH"),
            ("f2_hz_q", "CRT_F2_MISMATCH"),
            ("beat_hz_q", "CRT_BEAT_MISMATCH"),
            ("crt_phase_sync_s_q", "CRT_SYNC_MISMATCH"),
        ):
            h = copy.deepcopy(base_hyps)
            h["H20-B1"]["qin_maya_crt_beat_witnesses"][0][field] = "999/1"
            self._assert_err(code, vmi.verify_exact_operators, h)

        h = copy.deepcopy(base_hyps)
        h["H20-B2"]["stratum_all_peaks"] = "bad"
        self._assert_err("BAD_STRATUM", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B2"]["stratum_all_peaks"]["sample_pairs_exact_cmpPower"] = []
        self._assert_err("BAD_CMPPOWER_LIST", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B2"]["stratum_all_peaks"]["sample_pairs_exact_cmpPower"] = ["bad"]
        self._assert_err("BAD_CMPPOWER_ITEM", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B2"]["stratum_all_peaks"]["sample_pairs_exact_cmpPower"][0]["k53"] = 30
        self._assert_err("CMPPOWER_K53_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B2"]["stratum_mains_excluded"]["sample_pairs_exact_cmpPower"][0]["k12"] = 4
        self._assert_err("CMPPOWER_K12_MISMATCH", vmi.verify_exact_operators, h)

        h = copy.deepcopy(base_hyps)
        h["H20-B3"]["exact_q_session_mean_fan_hermitian_inertia"] = [3, 0]
        self._assert_err("BAD_HERMITIAN_INERTIA", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B3"]["exact_q_session_mean_fan_hermitian_inertia"] = [2, 0, 1]
        self._assert_err("HERMITIAN_NEG_EIG", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B3"]["exact_q_session_mean_fan_hermitian_inertia"] = [0, 3, 0]
        self._assert_err("HERMITIAN_NEG_EIG", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B3"]["exact_q_session_mean_fan_hermitian_inertia"] = [2, 0, 0]
        self._assert_err("HERMITIAN_NEG_EIG", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-B3"]["psd_violations"] = 1
        self._assert_err("PSD_VIOLATION", vmi.verify_exact_operators, h)

        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["p_raw"] = 0.0
        self._assert_err("BAD_C2_PVAL", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["p_holm"] = 0.0
        self._assert_err("BAD_C2_PVAL", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"] = "bad"
        self._assert_err("BAD_KHIPU", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["tamper_trials"] = 0
        h["H20-C2"]["khipu_tree_checksum"]["tamper_detected"] = 0
        self._assert_err("KHIPU_COUNT_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["tamper_detected"] = 199
        self._assert_err("KHIPU_COUNT_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["tamper_detected"] = -1
        h["H20-C2"]["khipu_tree_checksum"]["tamper_escapes"] = 201
        self._assert_err("KHIPU_COUNT_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["tamper_detected"] = 201
        h["H20-C2"]["khipu_tree_checksum"]["tamper_escapes"] = -1
        self._assert_err("KHIPU_COUNT_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["tamper_detected"] = 0
        h["H20-C2"]["khipu_tree_checksum"]["tamper_escapes"] = 200
        vmi.verify_exact_operators(h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["root_merkle_sha256"] = "0" * 64
        self._assert_err("BAD_KHIPU_ROOT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["root_merkle_sha256"] = "short"
        self._assert_err("BAD_KHIPU_ROOT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["root_value"] = 0
        self._assert_err("BAD_KHIPU_ROOT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["khipu_tree_checksum"]["root_value"] = "123"
        self._assert_err("BAD_KHIPU_ROOT", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["panini_c1p_live_replay"] = "bad"
        self._assert_err("BAD_PANINI", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["spine_len"] = 0
        self._assert_err("BAD_PANINI", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["tag_count"] = 0
        self._assert_err("BAD_PANINI", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["naive_bitset_bits"] = 127
        self._assert_err("PANINI_NAIVE_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["c1p_descriptor_bits"] = 41
        self._assert_err("PANINI_C1P_MISMATCH", vmi.verify_exact_operators, h)
        h = copy.deepcopy(base_hyps)
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["compression_ratio_q"] = "17/5"
        self._assert_err("PANINI_RATIO_MISMATCH", vmi.verify_exact_operators, h)
        for mut_pm in (
            lambda pm: pm.__setitem__("intervals", {}),
            lambda pm: pm.__setitem__("obstructed_count", 1),
            lambda pm: pm.__setitem__("obstructed_tags", {"x": 1}),
            lambda pm: pm["intervals"].__setitem__("t0", "bad"),
            lambda pm: pm["intervals"].__setitem__("t0", [0]),
            lambda pm: pm["intervals"].__setitem__("t0", [True, 7]),
            lambda pm: pm["intervals"].__setitem__("t0", [0, True]),
            lambda pm: pm["intervals"].__setitem__("t0", [-1, 7]),
            lambda pm: pm["intervals"].__setitem__("t0", [8, 7]),
            lambda pm: pm["intervals"].__setitem__("t0", [0, 32]),
        ):
            h = copy.deepcopy(base_hyps)
            mut_pm(h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"])
            self._assert_err("BAD_PANINI_INTERVALS", vmi.verify_exact_operators, h)
        for mut_cr in (
            lambda cr: cr.__setitem__("compression_ratio_q", "16/3"),
            lambda cr: cr.__setitem__("compression_ratio_float", 5.3),
            lambda cr: cr.__setitem__("intervals", {"x": [0, 1]}),
            lambda cr: cr.__setitem__("obstructed_tags", {}),
            lambda cr: cr.__setitem__("obstructed_tags", {"x": 0}),
            lambda cr: cr.__setitem__("obstructed_tags", {"x": True}),
            lambda cr: cr.__setitem__("obstructed_count", 2),
        ):
            h = copy.deepcopy(base_hyps)
            mut_cr(h["H20-C2"]["panini_c1p_live_replay"]["cross_modal_regimes_on_thermal_spine"])
            self._assert_err("BAD_PANINI_OBSTRUCTED", vmi.verify_exact_operators, h)

    # 7. All Law-4 verdict branches & exact pure-Q boundaries (incl. H20-C2 exploratory 12.57x non-override)
    def test_07_law4_verdict_branches_and_exact_boundaries(self) -> None:
        base = vmi.build_selftest_fixture()
        ph_sig = {hk: 0.005 for hk in vmi.STOCHASTIC_KEYS}
        ph_edge = {hk: 0.01 for hk in vmi.STOCHASTIC_KEYS}

        h = copy.deepcopy(base["hypotheses"])
        h["H20-A1"]["primary_stability_ratio"] = 2.0
        h["H20-A1"]["auroc_ir_real_vs_noise"] = 0.90
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A1"], "CONFIRMED")
        h["H20-A1"]["primary_stability_ratio"] = 1.99
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A1"], "PARTIAL")
        self.assertEqual(vmi._expected_verdicts(h, ph_edge)["H20-A1"], "FALSIFIED")
        h["H20-A1"]["auroc_ir_real_vs_noise"] = 0.89
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A1"], "FALSIFIED")

        h = copy.deepcopy(base["hypotheses"])
        h["H20-A2"]["p_raw_spatial_null"] = 0.005
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A2"], "CONFIRMED")
        h["H20-A2"]["p_raw_spatial_null"] = 0.01
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A2"], "PARTIAL")
        h["H20-A2"]["heldout_schur_r2"] = 0.05
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A2"], "FALSIFIED")
        h["H20-A2"]["interior_temporal_snr_ratio"] = 1.24
        h["H20-A2"]["interior_mean_lag1_acorr"] = 0.24
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A2"], "NULL_STATIC_ROOM")
        h["H20-A2"]["interior_temporal_snr_ratio"] = 1.25
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A2"], "FALSIFIED")
        h["H20-A2"]["interior_temporal_snr_ratio"] = 1.20
        h["H20-A2"]["interior_mean_lag1_acorr"] = 0.25
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-A2"], "FALSIFIED")
        h = copy.deepcopy(base["hypotheses"])
        h["H20-A2"]["p_raw_spatial_null"] = 0.005
        self.assertEqual(vmi._expected_verdicts(h, ph_edge)["H20-A2"], "FALSIFIED")

        self.assertEqual(vmi._expected_verdicts(base["hypotheses"], ph_sig)["H20-B1"], "CONFIRMED")
        self.assertEqual(vmi._expected_verdicts(base["hypotheses"], ph_edge)["H20-B1"], "FALSIFIED")
        for b1_k in vmi.B1_SUB_PVAL_KEYS:
            h = copy.deepcopy(base["hypotheses"])
            h["H20-B1"][b1_k] = 0.0
            self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B1"], "CONFIRMED")
            h["H20-B1"][b1_k] = 0.01
            self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B1"], "FALSIFIED")
            h["H20-B1"][b1_k] = 1.0
            self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B1"], "FALSIFIED")
            h["H20-B1"][b1_k] = -0.001
            self._assert_err("BAD_B1_PVAL", vmi._expected_verdicts, h, ph_sig)
            h["H20-B1"][b1_k] = 1.001
            self._assert_err("BAD_B1_PVAL", vmi._expected_verdicts, h, ph_sig)
            h["H20-B1"][b1_k] = "bad"
            self._assert_err("BAD_B1_PVAL", vmi._expected_verdicts, h, ph_sig)

        h = copy.deepcopy(base["hypotheses"])
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B2"], "CONFIRMED")
        self.assertEqual(vmi._expected_verdicts(h, ph_edge)["H20-B2"], "FALSIFIED")
        h["H20-B2"]["stratum_mains_excluded"]["mean_53tet_cents_cmpPower"] = 24.5
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B2"], "FALSIFIED")
        h["H20-B2"]["stratum_mains_excluded"]["mean_53tet_cents_cmpPower"] = None
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B2"], "FALSIFIED")
        h["H20-B2"]["stratum_mains_excluded"]["mean_53tet_cents_cmpPower"] = 5.0
        h["H20-B2"]["stratum_mains_excluded"]["mean_12tet_cents_cmpPower"] = None
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B2"], "FALSIFIED")

        h = copy.deepcopy(base["hypotheses"])
        h["H20-B3"]["n_transients_fitted"] = 5
        h["H20-B3"]["p_raw_transient_damping_diff"] = 0.005
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B3"], "CONFIRMED")
        h["H20-B3"]["n_transients_fitted"] = 4
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B3"], "PARTIAL")
        h["H20-B3"]["n_transients_fitted"] = 5
        h["H20-B3"]["p_raw_transient_damping_diff"] = 0.01
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B3"], "PARTIAL")
        h["H20-B3"]["directional_vs_diffuse_reff_gap"] = 0.2
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-B3"], "FALSIFIED")
        h["H20-B3"]["directional_vs_diffuse_reff_gap"] = 1.1
        self.assertEqual(vmi._expected_verdicts(h, ph_edge)["H20-B3"], "FALSIFIED")

        # H20-C1: graded strictly from recomputed pair_couplings & all C(k,3) lag holonomies
        h = copy.deepcopy(base["hypotheses"])
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C1"], "CONFIRMED")
        for pr in h["H20-C1"]["pair_couplings"]:
            pr["opt_lag_s"] = 0
        h["H20-C1"]["cech_h1_nonzero_holonomy_count"] = 0
        h["H20-C1"]["cech_h1_mean_abs_lag_holonomy_s"] = 0.0
        h["H20-C1"]["cech_h1_sample_triples"][0]["lag_holonomy_s"] = 0
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C1"], "PARTIAL")
        h = copy.deepcopy(base["hypotheses"])
        for pr in h["H20-C1"]["pair_couplings"]:
            pr["p_circ_raw"] = 0.5
            pr["p_circ_holm"] = 1.0
            pr["p_iaaft_raw"] = 0.5
            pr["p_iaaft_holm"] = 1.0
            pr["survives_both_nulls_001"] = False
        h["H20-C1"]["n_pairs_surviving_both_nulls_holm_001"] = 0
        h["H20-C1"]["p_raw"] = 0.5
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C1"], "FALSIFIED")

        # H20-C2: graded STRICTLY on pure-Q default switch counts & exact compression_ratio_q
        h = copy.deepcopy(base["hypotheses"])
        h["H20-C2"]["thermal_governor_live_replay"]["operating_band_5c_deadband"]["reduction_ratio"] = 12.57
        h["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"] = {
            "bangbang_switches": 50,
            "hysteresis_switches": 10,
            "reduction_ratio": 5.0,
        }
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C2"], "CONFIRMED")
        # Default 4.50x (261/58) MUST stay PARTIAL even with exploratory 12.57x present!
        h["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"] = {
            "bangbang_switches": 261,
            "hysteresis_switches": 58,
            "reduction_ratio": 4.5,
        }
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C2"], "PARTIAL")
        # Exact zero bangbang_switches boundary (0/10 == 0.0 -> PARTIAL) & exact 1e-3 ratio tolerance boundary
        h["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"] = {
            "bangbang_switches": 0,
            "hysteresis_switches": 10,
            "reduction_ratio": 1e-3,
        }
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C2"], "PARTIAL")
        # Inconsistent reduction_ratio vs switch counts or None/bad switch counts MUST fail closed
        h_bad = copy.deepcopy(h)
        h_bad["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"]["reduction_ratio"] = 5.0
        self._assert_err("BAD_C2_RATIO", vmi._expected_verdicts, h_bad, ph_sig)
        h_bad = copy.deepcopy(h)
        h_bad["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"]["reduction_ratio"] = None
        self._assert_err("BAD_C2", vmi._expected_verdicts, h_bad, ph_sig)
        h_bad = copy.deepcopy(h)
        h_bad["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"]["bangbang_switches"] = -1
        self._assert_err("BAD_C2", vmi._expected_verdicts, h_bad, ph_sig)
        h_bad = copy.deepcopy(h)
        h_bad["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"]["hysteresis_switches"] = 0
        self._assert_err("BAD_C2", vmi._expected_verdicts, h_bad, ph_sig)
        h_bad = copy.deepcopy(h)
        h_bad["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"]["bangbang_switches"] = 10**400
        h_bad["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"]["hysteresis_switches"] = 1
        self._assert_err("BAD_C2_RATIO", vmi._expected_verdicts, h_bad, ph_sig)
        self._assert_err("BAD_REAL", vmi._require_real, 10**400, "BAD_REAL", "overflow")

        # Panini gate uses exact compression_ratio_q > 1/1 (NOT untied compression_ratio_float!)
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["compression_ratio_q"] = "1/1"
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["compression_ratio_float"] = 9.9
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C2"], "FALSIFIED")
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["compression_ratio_q"] = "16/5"
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["c1p_admissible"] = False
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C2"], "FALSIFIED")
        h["H20-C2"]["panini_c1p_live_replay"]["monotone_thermal_regimes"]["c1p_admissible"] = True
        h["H20-C2"]["khipu_tree_checksum"]["tamper_escapes"] = 1
        self.assertEqual(vmi._expected_verdicts(h, ph_sig)["H20-C2"], "FALSIFIED")

    # 8. Document schema, Holm tolerance boundary, SHA-256 tamper, and CLI pathways
    def test_08_document_schema_crypto_and_cli(self) -> None:
        base = vmi.build_selftest_fixture()
        self.assertEqual(vmi.validate_results_document(base)["status"], "PASS")

        d = copy.deepcopy(base)
        d["n_nulls"] = 100
        d["hypotheses"]["H20-A1"]["p_raw"] = 0.0
        d = _sync_summary(d)
        d["summary"]["holm_bonferroni_pvals"]["H20-A1"] = vmi.HOLM_TOL
        d["hypotheses"]["H20-A1"]["p_holm"] = vmi.HOLM_TOL
        d = _rehash(d)
        self.assertEqual(vmi.validate_results_document(d)["status"], "PASS")

        self._assert_err("BAD_ROOT", vmi.validate_results_document, [])
        d = copy.deepcopy(base)
        del d["seed"]
        self._assert_err("MISSING_KEY", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["unexpected"] = 1
        self._assert_err("EXTRA_KEY", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["schema"] = "wrong"
        self._assert_err("BAD_SCHEMA", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["analysis_plan_sha256"] = "\u00b0" * 64
        self._assert_err("BAD_ANALYSIS_PLAN", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["analysis_plan_sha256"] = "0" * 64
        self._assert_err("BAD_ANALYSIS_PLAN", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["analysis_plan_sha256"] = "short"
        self._assert_err("BAD_ANALYSIS_PLAN", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["dataset_prefix"] = ""
        self._assert_err("BAD_PREFIX", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["seed"] = True
        self._assert_err("BAD_SEED", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["n_nulls"] = 99
        self._assert_err("TOO_FEW_NULLS", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["energy_power_status"] = "CLAIMED"
        self._assert_err("BAD_ENERGY_STATUS", vmi.validate_results_document, d)

        d = copy.deepcopy(base)
        d["hypotheses"] = []
        self._assert_err("BAD_HYPS", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        del d["hypotheses"]["H20-C2"]
        self._assert_err("BAD_HYP_KEYS", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["hypotheses"]["H20-C2"] = []
        self._assert_err("MISSING_HYP", vmi.validate_results_document, d)

        d = copy.deepcopy(base)
        d["summary"] = []
        self._assert_err("BAD_SUMMARY", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["summary"]["holm_bonferroni_pvals"] = []
        self._assert_err("BAD_HOLM", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        del d["summary"]["holm_bonferroni_pvals"]["H20-A1"]
        self._assert_err("BAD_HOLM", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["summary"]["holm_bonferroni_pvals"]["H20-A1"] = 0.5
        self._assert_err("HOLM_MISMATCH", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["hypotheses"]["H20-A1"]["p_holm"] = 0.5
        self._assert_err("HOLM_MISMATCH", vmi.validate_results_document, d)

        d = copy.deepcopy(base)
        d["summary"]["verdicts"] = []
        self._assert_err("BAD_VERDICTS", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        del d["summary"]["verdicts"]["H20-B2"]
        self._assert_err("BAD_VERDICTS", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["summary"]["verdicts"]["H20-B2"] = "CONFIRMED"
        self._assert_err("VERDICT_MISMATCH", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["hypotheses"]["H20-B2"]["verdict"] = "CONFIRMED"
        self._assert_err("VERDICT_MISMATCH", vmi.validate_results_document, d)

        d = copy.deepcopy(base)
        d["payload_sha256"] = "0" * 64
        self._assert_err("PAYLOAD_SHA_MISMATCH", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["payload_sha256"] = "\u00b0" * 64
        self._assert_err("PAYLOAD_SHA_MISMATCH", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["results_sha256"] = "0" * 64
        self._assert_err("RESULTS_SHA_MISMATCH", vmi.validate_results_document, d)
        d = copy.deepcopy(base)
        d["results_sha256"] = "\u00b0" * 64
        self._assert_err("RESULTS_SHA_MISMATCH", vmi.validate_results_document, d)

        for cli_args in ([], ["--check-bundle"], ["--check-bundle", str(STUDY_DIR)], ["--selftest"]):
            out = io.StringIO()
            with patch.object(sys, "stdout", out):
                rc = vmi.main(cli_args)
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out.getvalue())["status"], "PASS")

        out = io.StringIO()
        with patch.object(sys, "stdout", out):
            rc = vmi.main(["--check", str(STUDY_DIR.joinpath("open_room_interposition_results.json"))])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["results_sha256"], vmi.PINNED_RESULTS_SHA256)

        with tempfile.TemporaryDirectory() as td:
            bad_file = Path(td).joinpath("bad.json")
            bad_file.write_text("{not valid json", encoding="utf-8")
            err = io.StringIO()
            with patch.object(sys, "stderr", err):
                rc = vmi.main(["--check", str(bad_file)])
            self.assertEqual(rc, 2)
            self.assertIn("READ_OR_JSON_ERR", err.getvalue())

            self.assertEqual(vmi._parse_bounded_int("9" * vmi.MAX_JSON_INT_DIGITS), int("9" * vmi.MAX_JSON_INT_DIGITS))
            self._assert_err("JSON_INT_TOO_LARGE", vmi._parse_bounded_int, "9" * (vmi.MAX_JSON_INT_DIGITS + 1))
            big_int_file = Path(td).joinpath("big_int.json")
            big_int_file.write_text('{"seed": ' + ("9" * 4400) + "}", encoding="utf-8")
            err = io.StringIO()
            with patch.object(sys, "stderr", err):
                rc = vmi.main(["--check", str(big_int_file)])
            self.assertEqual(rc, 2)
            self.assertIn("JSON_INT_TOO_LARGE", err.getvalue())

            # <=1024-digit ints that overflow IEEE-754 float (10**400) must exit RC=2 cleanly (0 traceback)
            for label, mut_fn, exp_code in (
                ("p_raw_ovf", lambda doc: doc["hypotheses"]["H20-A1"].__setitem__("p_raw", 10**400), "BAD_PVAL_TYPE"),
                ("c2_sw_ovf", lambda doc: doc["hypotheses"]["H20-C2"]["thermal_governor_live_replay"]["default_70_78_85_ladder"].__setitem__("bangbang_switches", 10**400), "BAD_C2_RATIO"),
                ("hs_neg_ovf", lambda doc: doc["privacy_and_shutoff_receipt"].__setitem__("hard_stop_epoch_s", -1), "HARD_STOP_EXCEEDED"),
            ):
                ovf_doc = copy.deepcopy(base)
                mut_fn(ovf_doc)
                ovf_p = Path(td).joinpath(f"{label}.json")
                ovf_p.write_text(json.dumps(ovf_doc), encoding="utf-8")
                err_ovf = io.StringIO()
                with patch.object(sys, "stderr", err_ovf):
                    rc_ovf = vmi.main(["--check", str(ovf_p)])
                self.assertEqual(rc_ovf, 2)
                self.assertIn(exp_code, err_ovf.getvalue())

    # 9. Built-in Aletheia R1-R4 hygiene, safety, and unseeded-RNG check on study directory
    def test_09_study_directory_audit_check_clean(self) -> None:
        report = run_audit_check(
            STUDY_DIR,
            safety_scan=True,
            strict_unseeded=True,
        )
        self.assertTrue(report["passed"], f"audit-check failed: {report}")

    # 10. Hardened in-module AST exact-operator purity audit & negative self-controls
    def test_10_ast_pure_exact_operator_invariants(self) -> None:
        src = STUDY_DIR.joinpath("verify_multimodal_interposition.py").read_text(encoding="utf-8")
        res = vmi.audit_exact_operators_ast(src)
        self.assertTrue(all(res.values()))
        # Whole verifier module also has zero transcendental math calls
        whole_tree = ast.parse(src)
        for node in ast.walk(whole_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, ("log", "log2", "log10", "exp", "pow", "sqrt"))

        # Positive full-snippet check with safe `from fractions import Fraction` & `type(x) is int`
        self.assertTrue(vmi.audit_exact_operators_ast("from fractions import Fraction\nx = Fraction(1, 2)\nok = type(x) is Fraction\n", None)["zero_ast_pow"])
        # Fail closed on missing/renamed function in func_names!
        self._assert_err("MISSING_EXACT_FUNC", vmi.audit_exact_operators_ast, src, ("nonexistent_func",))
        self._assert_err("BAD_SOURCE", vmi.audit_exact_operators_ast, 123, None)  # type: ignore[arg-type]
        self._assert_err("AST_SYNTAX_ERR", vmi.audit_exact_operators_ast, "def (:", None)
        self._assert_err("AST_FLOAT_LITERAL", vmi.audit_exact_operators_ast, "x = 1.5\n", None)
        self._assert_err("AST_FLOAT_LITERAL", vmi.audit_exact_operators_ast, "x = 1j\n", None)
        self._assert_err("AST_DIV_FORBIDDEN", vmi.audit_exact_operators_ast, "x = a / b\n", None)
        self._assert_err("AST_FLOORDIV_FORBIDDEN", vmi.audit_exact_operators_ast, "x = 1 // 2\n", None)
        self._assert_err("AST_MOD_FORBIDDEN", vmi.audit_exact_operators_ast, "x = '%.3f' % Fraction(1, 2)\n", None)
        self._assert_err("AST_MOD_FORBIDDEN", vmi.audit_exact_operators_ast, "x = fmt % y\n", None)
        self._assert_err("AST_POW_FORBIDDEN", vmi.audit_exact_operators_ast, "x = 2 ** -1\n", None)
        self._assert_err("AST_POW_FORBIDDEN", vmi.audit_exact_operators_ast, "x = 2 ** (0 - 1)\n", None)
        self._assert_err("AST_FORMAT_SPEC_FORBIDDEN", vmi.audit_exact_operators_ast, "x = f'{1:.3f}'\n", None)
        self._assert_err("AST_FLOAT_IMPORT", vmi.audit_exact_operators_ast, "import math\n", None)
        self._assert_err("AST_FLOAT_IMPORT", vmi.audit_exact_operators_ast, "import ctypes\n", None)
        self._assert_err("AST_FLOAT_IMPORT", vmi.audit_exact_operators_ast, "from math import log\n", None)
        self._assert_err("AST_FLOAT_IMPORT", vmi.audit_exact_operators_ast, "from .fractions import Fraction\n", None)
        self._assert_err("AST_FLOAT_IMPORT", vmi.audit_exact_operators_ast, "import fractions\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "from fractions import Fraction as F\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "from fractions import gcd\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "g = Fraction\nx = g('0.5')\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "t = type\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "g: object = Fraction\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "x = (g := Fraction)\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "g = mod.Fraction\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "lst = [Fraction]\n", None)
        self._assert_err("AST_FRACTION_ALIAS", vmi.audit_exact_operators_ast, "f = [Fraction][0]\n", None)
        self._assert_err("AST_INDIRECT_CALL", vmi.audit_exact_operators_ast, "x = [Fraction][0]('0.5')\n", None)
        self._assert_err("AST_INDIRECT_CALL", vmi.audit_exact_operators_ast, "x = type(Fraction(1, 1))('1.5')\n", None)
        self._assert_err("AST_INDIRECT_CALL", vmi.audit_exact_operators_ast, "x = (lambda: 1)()\n", None)
        self._assert_err("AST_UNSAFE_TYPE", vmi.audit_exact_operators_ast, "T = type(Fraction(1, 1))\n", None)
        self._assert_err("AST_UNSAFE_TYPE", vmi.audit_exact_operators_ast, "ok = obj.type(a) is int\n", None)
        self._assert_err("AST_UNSAFE_TYPE", vmi.audit_exact_operators_ast, "ok = type('A', (), {}) is int\n", None)
        self._assert_err("AST_UNSAFE_TYPE", vmi.audit_exact_operators_ast, "ok = type(a, k=1) is int\n", None)
        self._assert_err("AST_UNSAFE_TYPE", vmi.audit_exact_operators_ast, "ok = type(a) == int\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "f = float\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = '{:.3f}'.format(Fraction(1, 2))\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = format(Fraction(1, 2), '.3f')\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = '{a:.3f}'.format_map({'a': 1})\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = divmod(5, 2)\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = memoryview(b'1234')\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = literal_eval('1.5')\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = (1).__truediv__(2)\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = (1).__getattribute__('__truediv__')\n", None)
        self._assert_err("AST_INDIRECT_CALL", vmi.audit_exact_operators_ast, "x = (1).__getattribute__('__truediv__')(2)\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = sys.modules['math']\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = pow(2, -1)\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = float(1)\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = Fraction.from_float(1)\n", None)
        self._assert_err("AST_FLOAT_CALL", vmi.audit_exact_operators_ast, "x = obj.log(2)\n", None)
        self._assert_err("AST_UNSAFE_FRACTION", vmi.audit_exact_operators_ast, 'x = Fraction("1/2")\n', None)
        self._assert_err("AST_UNSAFE_FRACTION", vmi.audit_exact_operators_ast, "x = fractions.Fraction(1, 2)\n", None)
        self._assert_err("AST_UNSAFE_FRACTION", vmi.audit_exact_operators_ast, "x = Fraction(1, True)\n", None)
        self._assert_err("AST_UNSAFE_FRACTION", vmi.audit_exact_operators_ast, "x = Fraction(numerator=1, denominator=2)\n", None)

    # 11. R2 planted rehashed `--check` forgeries & exhaustive H20-C1 evidence-binding guards
    def test_11_r2_planted_forgeries_and_c1_evidence_binding(self) -> None:
        live_doc = json.loads(
            STUDY_DIR.joinpath("open_room_interposition_results.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as td:
            tpath = Path(td).joinpath("planted.json")

            def assert_check_rejects(doc: Dict[str, Any], expected_code: str) -> None:
                tpath.write_text(json.dumps(_rehash(doc)), encoding="utf-8")
                self._assert_err(expected_code, vmi.check_results_file, tpath)
                err = io.StringIO()
                with patch.object(sys, "stderr", err):
                    rc = vmi.main(["--check", str(tpath)])
                self.assertEqual(rc, 2)
                self.assertIn(expected_code, err.getvalue())

            # Plant 1: C1 survivor count = 0 + FALSIFIED while 5 surviving pairs remain
            d1 = copy.deepcopy(live_doc)
            d1["hypotheses"]["H20-C1"]["n_pairs_surviving_both_nulls_holm_001"] = 0
            d1["hypotheses"]["H20-C1"]["verdict"] = "FALSIFIED"
            d1["summary"]["verdicts"]["H20-C1"] = "FALSIFIED"
            assert_check_rejects(d1, "C1_SURVIVOR_COUNT_MISMATCH")

            # Plant 2: Clear survives_both_nulls_001 & set pair Holm p-vals to 1.0, keep n_pairs=5 & CONFIRMED
            d2 = copy.deepcopy(live_doc)
            for row in d2["hypotheses"]["H20-C1"]["pair_couplings"]:
                row["survives_both_nulls_001"] = False
                row["p_circ_holm"] = 1.0
                row["p_iaaft_holm"] = 1.0
            assert_check_rejects(d2, "C1_PAIR_HOLM_MISMATCH")

            # Plant 3: Flip survives_both_nulls_001 flag alone (Holm intact)
            d3 = copy.deepcopy(live_doc)
            for row in d3["hypotheses"]["H20-C1"]["pair_couplings"]:
                if row["survives_both_nulls_001"]:
                    row["survives_both_nulls_001"] = False
                    break
            assert_check_rejects(d3, "C1_SURVIVOR_FLAG_MISMATCH")

            # Plant 4: Set cech_h1_nonzero_holonomy_count = 0 + PARTIAL while pair lags give 35/35 nonzero
            d4 = copy.deepcopy(live_doc)
            d4["hypotheses"]["H20-C1"]["cech_h1_nonzero_holonomy_count"] = 0
            d4["hypotheses"]["H20-C1"]["verdict"] = "PARTIAL"
            d4["summary"]["verdicts"]["H20-C1"] = "PARTIAL"
            assert_check_rejects(d4, "C1_HOLONOMY_COUNT_MISMATCH")

            # Plant 5: Set B1 p_raw_4pole_lock_null = 0.9, keep p_raw / p_holm / CONFIRMED
            d5 = copy.deepcopy(live_doc)
            d5["hypotheses"]["H20-B1"]["p_raw_4pole_lock_null"] = 0.9
            assert_check_rejects(d5, "VERDICT_MISMATCH")

            # Plant 6: Zero Khipu root_merkle_sha256 & root_value
            d6 = copy.deepcopy(live_doc)
            d6["hypotheses"]["H20-C2"]["khipu_tree_checksum"]["root_merkle_sha256"] = "0" * 64
            d6["hypotheses"]["H20-C2"]["khipu_tree_checksum"]["root_value"] = 0
            assert_check_rejects(d6, "BAD_KHIPU_ROOT")

            # Plant 7: Set unique_rpm_pairs_count < len(witnesses)
            d7 = copy.deepcopy(live_doc)
            d7["hypotheses"]["H20-B1"]["unique_rpm_pairs_count"] = 7
            assert_check_rejects(d7, "BAD_CRT_COUNT")

        # Direct boundary & guard coverage for _verify_c1_evidence
        base_c1 = copy.deepcopy(vmi.build_selftest_fixture()["hypotheses"]["H20-C1"])
        self.assertEqual(vmi._verify_c1_evidence(base_c1), (2, 1))

        # Exact tolerance boundaries (HOLM_TOL on pair Holm & p_raw; 1e-4 on mean abs holonomy)
        c_edge = copy.deepcopy(base_c1)
        for pr in c_edge["pair_couplings"]:
            pr["opt_lag_s"] = 0
            pr["p_circ_raw"] = 0.0
            pr["p_circ_holm"] = vmi.HOLM_TOL
            pr["p_iaaft_raw"] = 0.0
            pr["p_iaaft_holm"] = vmi.HOLM_TOL
            pr["survives_both_nulls_001"] = True
        c_edge["n_pairs_surviving_both_nulls_holm_001"] = 3
        c_edge["p_raw"] = vmi.HOLM_TOL
        c_edge["cech_h1_nonzero_holonomy_count"] = 0
        c_edge["cech_h1_mean_abs_lag_holonomy_s"] = 1e-4
        c_edge["cech_h1_sample_triples"][0]["lag_holonomy_s"] = 0
        self.assertEqual(vmi._verify_c1_evidence(c_edge), (3, 0))

        # Exact [0.0, 1.0] bounds on pair p-values & exact 0.01 survivor cutoff (circ-only & iaaft-only)
        c_zero = copy.deepcopy(base_c1)
        c_zero["pair_couplings"][0]["p_circ_raw"] = 1.0
        c_zero["pair_couplings"][0]["p_circ_holm"] = 1.0
        c_zero["pair_couplings"][0]["p_iaaft_raw"] = 0.0
        c_zero["pair_couplings"][0]["p_iaaft_holm"] = 0.0
        c_zero["pair_couplings"][0]["survives_both_nulls_001"] = False
        c_zero["pair_couplings"][1]["p_circ_raw"] = 0.0
        c_zero["pair_couplings"][1]["p_circ_holm"] = 0.0
        c_zero["pair_couplings"][1]["p_iaaft_raw"] = 1.0
        c_zero["pair_couplings"][1]["p_iaaft_holm"] = 1.0
        c_zero["pair_couplings"][1]["survives_both_nulls_001"] = False
        c_zero["pair_couplings"][2]["p_circ_raw"] = 0.005
        c_zero["pair_couplings"][2]["p_circ_holm"] = 0.01
        c_zero["pair_couplings"][2]["p_iaaft_raw"] = 0.005
        c_zero["pair_couplings"][2]["p_iaaft_holm"] = 0.01
        c_zero["pair_couplings"][2]["survives_both_nulls_001"] = False
        c_zero["n_pairs_surviving_both_nulls_holm_001"] = 0
        c_zero["p_raw"] = 0.005
        self.assertEqual(vmi._verify_c1_evidence(c_zero), (0, 1))
        # Flipping flag to True when only iaaft < 0.01 or only circ < 0.01 MUST reject
        for idx in (0, 1, 2):
            c_bad_flag = copy.deepcopy(c_zero)
            c_bad_flag["pair_couplings"][idx]["survives_both_nulls_001"] = True
            self._assert_err("C1_SURVIVOR_FLAG_MISMATCH", vmi._verify_c1_evidence, c_bad_flag)

        for bad_ch in ("abc", ["a", "b"], ["a", "b", 1], ["a", "b", ""], ["a", "b", "a"]):
            c = copy.deepcopy(base_c1)
            c["active_channels"] = bad_ch
            self._assert_err("BAD_C1_CHANNELS", vmi._verify_c1_evidence, c)

        c = copy.deepcopy(base_c1)
        c["n_pairs_tested"] = 2
        self._assert_err("BAD_C1_PAIRS", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["pair_couplings"] = {}
        self._assert_err("BAD_C1_PAIRS", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["pair_couplings"] = c["pair_couplings"][:-1]
        self._assert_err("BAD_C1_PAIRS", vmi._verify_c1_evidence, c)

        c = copy.deepcopy(base_c1)
        c["pair_couplings"][0] = "bad"
        self._assert_err("BAD_C1_PAIR_ITEM", vmi._verify_c1_evidence, c)
        for bad_pk in (["unhashable"], "NO__x__PAIR"):
            c = copy.deepcopy(base_c1)
            c["pair_couplings"][0]["pair"] = bad_pk
            self._assert_err("BAD_C1_PAIR_KEY", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["pair_couplings"][1]["pair"] = c["pair_couplings"][0]["pair"]
        self._assert_err("BAD_C1_PAIR_KEY", vmi._verify_c1_evidence, c)

        c = copy.deepcopy(base_c1)
        c["pair_couplings"][0]["opt_lag_s"] = True
        self._assert_err("BAD_C1_LAG", vmi._verify_c1_evidence, c)

        for pv_key in ("p_circ_raw", "p_iaaft_raw", "p_circ_holm", "p_iaaft_holm"):
            for bad_v in (-0.01, 1.01):
                c = copy.deepcopy(base_c1)
                c["pair_couplings"][0][pv_key] = bad_v
                self._assert_err("BAD_C1_PVAL", vmi._verify_c1_evidence, c)

        c = copy.deepcopy(base_c1)
        c["pair_couplings"][0]["survives_both_nulls_001"] = 1
        self._assert_err("BAD_C1_SURV_FLAG", vmi._verify_c1_evidence, c)

        c = copy.deepcopy(base_c1)
        c["pair_couplings"][0]["p_circ_holm"] = 0.9
        self._assert_err("C1_PAIR_HOLM_MISMATCH", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["pair_couplings"][0]["p_iaaft_holm"] = 0.9
        self._assert_err("C1_PAIR_HOLM_MISMATCH", vmi._verify_c1_evidence, c)

        c = copy.deepcopy(base_c1)
        c["p_raw"] = 0.5
        self._assert_err("C1_PRAW_MISMATCH", vmi._verify_c1_evidence, c)

        c = copy.deepcopy(base_c1)
        c["cech_h1_triples_count"] = 2
        self._assert_err("C1_HOLONOMY_COUNT_MISMATCH", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["cech_h1_nonzero_holonomy_count"] = 0
        self._assert_err("C1_HOLONOMY_COUNT_MISMATCH", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["cech_h1_mean_abs_lag_holonomy_s"] = 1.001
        self._assert_err("C1_HOLONOMY_MEAN_MISMATCH", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["pair_couplings"][0]["opt_lag_s"] = 10**400
        self._assert_err("C1_HOLONOMY_MEAN_MISMATCH", vmi._verify_c1_evidence, c)

        c = copy.deepcopy(base_c1)
        c["cech_h1_sample_triples"] = "bad"
        self._assert_err("C1_SAMPLE_TRIPLE_MISMATCH", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["cech_h1_sample_triples"].append(copy.deepcopy(c["cech_h1_sample_triples"][0]))
        self._assert_err("C1_SAMPLE_TRIPLE_MISMATCH", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["cech_h1_sample_triples"] = ["bad"]
        self._assert_err("C1_SAMPLE_TRIPLE_MISMATCH", vmi._verify_c1_evidence, c)
        for bad_tr in ("notlist", [["x"], "M3_mic_rms", "M4_fan_rpm"], ["M1_vis_luma", "M3_mic_rms", "NOPE"]):
            c = copy.deepcopy(base_c1)
            c["cech_h1_sample_triples"][0]["triple"] = bad_tr
            self._assert_err("C1_SAMPLE_TRIPLE_MISMATCH", vmi._verify_c1_evidence, c)
        c = copy.deepcopy(base_c1)
        c["cech_h1_sample_triples"][0]["lag_holonomy_s"] = 99
        self._assert_err("C1_SAMPLE_TRIPLE_MISMATCH", vmi._verify_c1_evidence, c)


if __name__ == "__main__":
    unittest.main()
