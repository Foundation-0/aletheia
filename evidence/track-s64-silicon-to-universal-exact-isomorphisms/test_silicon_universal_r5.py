#!/usr/bin/env python3
"""
Adversarial Verification & Mutation-Kill Suite:
Silicon-to-Universal Exact-Operator Correspondence & Obstruction Atlas.

Zero bare asserts, zero AST floats, zero external dependencies, zero writes
to system device paths (uses private scratch os.mkfifo + chmod 0o700/0o500).
"""
from __future__ import annotations

import copy
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import silicon_universal_audit as audit
import silicon_universal_oracle as oracle


class _EvilStr(str):
    pass


class _EvilInt(int):
    pass


class _EvilList(list):
    pass


class _EvilDict(dict):
    pass


class TestTrackS64SiliconUniversalR5(unittest.TestCase):
    def _fresh_cert(self) -> dict:
        return oracle.build_certificate()

    def _resign(self, payload: dict, *, schema: str | None = None, track_id: str | None = None) -> dict:
        sc = oracle.CERT_SCHEMA if schema is None else schema
        tid = oracle.CERT_TRACK_ID if track_id is None else track_id
        p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
        body = {"schema": sc, "track_id": tid, "payload_sha256": p_sha, "payload": payload}
        c_sha = oracle.sha256_hex(oracle.canonical_json_bytes(body))
        return {
            "schema": sc,
            "track_id": tid,
            "payload_sha256": p_sha,
            "certificate_sha256": c_sha,
            "payload": payload,
        }

    def test_01_oracle_exact_invariants_and_roundtrip(self) -> None:
        cert = self._fresh_cert()
        res = audit.verify_certificate_object(cert)
        self.assertTrue(res["valid"])
        self.assertEqual(res["secondary_audit"]["pillars_verified"], 6)

        # Verify pure-Z/Q exact primitives on boundary cases
        self.assertEqual(oracle.q_str(Fraction(4, 1)), "4")
        self.assertEqual(oracle.q_str(Fraction(9, 2)), "9/2")
        # Round-half-to-even boundaries (odd vs even tie, negative values)
        self.assertEqual(oracle.round_q_1e6(Fraction(1, 2_000_000)), Fraction(0, 1))
        self.assertEqual(oracle.round_q_1e6(Fraction(3, 2_000_000)), Fraction(2, 1_000_000))
        self.assertEqual(oracle.round_q_1e6(Fraction(-5, 2_000_000)), Fraction(-2, 1_000_000))
        self.assertEqual(oracle.round_q_1e6(Fraction(-7, 2_000_000)), Fraction(-4, 1_000_000))
        self.assertEqual(oracle.round_q_1e6(Fraction(11, 4_000_000)), Fraction(3, 1_000_000))

        # Exact S39, C_[16,11,4], RM(1,4), E_8, Stage-A gauge invariants
        ex = cert["payload"]["exact"]
        self.assertTrue(ex["s39_nyquist_third_prism_exact"]["wn_formula_matches_binomial"])
        self.assertTrue(ex["s39_nyquist_third_prism_exact"]["rw_formula_matches_binomial"])
        codes = ex["universal_code_and_lattice_exact"]
        self.assertEqual(codes["c16_11_4_codeword_count"], 2048)
        self.assertEqual(codes["c16_11_4_min_distance"], 4)
        self.assertEqual(codes["rm14_subset_c16_verified_count"], 32)
        self.assertEqual(codes["e8_total_minimal_roots"], 240)
        self.assertTrue(ex["stage_a_gauge_invariance_exact"]["exact_zero_gauge_drift"])

        # Pivot row swap coverage inside compute_scale_invariant_schur_exact (lam=0 with zero leading entry)
        a_sw = [[Fraction(1), Fraction(2), Fraction(4), Fraction(8)]]
        b_sw = [
            [Fraction(1), Fraction(1), Fraction(1), Fraction(2)],
            [Fraction(2), Fraction(3), Fraction(5), Fraction(9)],
        ]
        # Regular case + check exact invariance
        etas, me, _, _ = oracle.compute_scale_invariant_schur_exact(a_sw + a_sw, b_sw, Fraction(1, 20))
        self.assertEqual(len(etas), 2)
        self.assertTrue(me > 0)

        # Green's 2-area exact check (CCW unit square: sum (y_{i+1}+y_i)(x_{i+1}-x_i) = -2*Area)
        op, cl = oracle.compute_green_2area_exact([0, 1, 1, 0], [0, 0, 1, 1])
        self.assertEqual(op, -2)
        self.assertEqual(cl, -2)

        # Oracle boundary guard checks (S39 prism min len 6 & coprime shuffle)
        self.assertEqual(len(oracle.compute_s39_prism_exact([1, 3, 2, 5, 1, 4])), 5)
        with self.assertRaises(ValueError):
            oracle.compute_s39_prism_exact([1, 2, 3, 4, 5])
        self.assertEqual(oracle.deterministic_coprime_shuffle([7], 1), [7])
        with self.assertRaises(ValueError):
            oracle.deterministic_coprime_shuffle([], 1)
        with self.assertRaises(ValueError):
            oracle.deterministic_coprime_shuffle([1, 2, 3, 4], 2)

        # Disk cert check if present. The 0o600 guarantee applies only to fresh atomic
        # --write outputs; a git checkout stores 0644 (git cannot store 0600), so both
        # modes are accepted here while the canonical bytes stay pinned.
        disk_cert = HERE / "silicon_universal_certificate.json"
        if disk_cert.exists():
            st = os.lstat(disk_cert)
            self.assertIn(stat.S_IMODE(st.st_mode), (0o600, 0o644))
            chk = audit.check_certificate_file(disk_cert)
            self.assertTrue(chk["valid"])
            self.assertEqual(chk["certificate_sha256"], cert["certificate_sha256"])

    def test_02_type_json_and_rational_parsers(self) -> None:
        # _is_ascii_digits + _parse_rational + _parse_positive_rational
        self.assertFalse(audit._is_ascii_digits(""))
        self.assertFalse(audit._is_ascii_digits("12a"))
        self.assertFalse(audit._is_ascii_digits("\u0661"))
        self.assertTrue(audit._is_ascii_digits("0123456789"))

        for bad_q, code in [
            (123, "INVALID_STR"),
            ("1/2/3", "INVALID_RATIONAL"),
            ("a/2", "INVALID_RATIONAL"),
            ("1/b", "INVALID_RATIONAL"),
            ("1/0", "INVALID_RATIONAL"),
            ("2/4", "NON_CANONICAL_RATIONAL"),
            ("2/1", "NON_CANONICAL_RATIONAL"),
            ("-0", "NON_CANONICAL_RATIONAL"),
            ("12x", "INVALID_RATIONAL"),
            ("1" * 621, "RATIONAL_DIGIT_LIMIT"),
            (("1" * 621) + "/1", "RATIONAL_DIGIT_LIMIT"),
            ("1/" + ("1" * 621), "RATIONAL_DIGIT_LIMIT"),
        ]:
            with self.assertRaises(audit.AuditError) as cm:
                audit._parse_rational(bad_q, "q")
            self.assertEqual(cm.exception.code, code)

        self.assertEqual(audit._parse_rational("-3/4", "q"), Fraction(-3, 4))
        self.assertEqual(audit._parse_rational("-5", "q"), Fraction(-5, 1))
        self.assertEqual(audit._parse_rational("1" * 620, "q"), Fraction(int("1" * 620), 1))
        self.assertEqual(audit._parse_rational("1/" + ("9" * 620), "q"), Fraction(1, int("9" * 620)))
        for nonpos in ("0", "-1", "-3/2"):
            with self.assertRaises(audit.AuditError) as cm:
                audit._parse_positive_rational(nonpos, "pos")
            self.assertEqual(cm.exception.code, "NONPOSITIVE_VALUE")

        # Exact container / scalar type checks and bounds
        for fn, bad, code in [
            (audit._req_dict, _EvilDict(), "INVALID_DICT"),
            (audit._req_list, _EvilList(), "INVALID_LIST"),
            (audit._req_str, _EvilStr("x"), "INVALID_STR"),
            (audit._req_str, "\ud800", "INVALID_UNICODE_STR"),
            (audit._req_bool, 1, "INVALID_BOOL"),
            (audit._req_int, True, "INVALID_INT"),
            (audit._req_int, _EvilInt(1), "INVALID_INT"),
            (audit._req_int, 1 << 2048, "INT_BIT_LIMIT"),
            (audit._req_sha256, "a" * 63, "INVALID_SHA256"),
            (audit._req_sha256, "A" * 64, "INVALID_SHA256"),
        ]:
            with self.assertRaises(audit.AuditError) as cm:
                fn(bad, "x")
            self.assertEqual(cm.exception.code, code)
        self.assertEqual(audit._req_int((1 << 2048) - 1, "max_ok"), (1 << 2048) - 1)

        # JSON tree iterative depth, non-str key, forbidden type, float, None
        deep: object = 1
        for _ in range(audit.MAX_JSON_DEPTH):
            deep = [deep]
        audit._validate_json_tree(deep, "exact_depth")
        with self.assertRaises(audit.AuditError) as cm:
            audit._validate_json_tree([deep], "too_deep")
        self.assertEqual(cm.exception.code, "JSON_DEPTH_EXCEEDED")

        audit._validate_json_tree({"n": None, "b": True, "i": 1}, "ok")
        for bad_tree, code in [
            ({1: "a"}, "NON_STR_KEY"),
            ({"\ud800": "a"}, "INVALID_UNICODE_STR"),
            ((1, 2), "FORBIDDEN_TYPE"),
            (object(), "FORBIDDEN_TYPE"),
        ]:
            with self.assertRaises(audit.AuditError) as cm:
                audit._validate_json_tree(bad_tree, "t")
            self.assertEqual(cm.exception.code, code)

        # Strict JSON bytes parsing
        for bad_raw, code in [
            (b'{"a":1}\r\n', "CRLF_FORBIDDEN"),
            (b"\xff\xfe", "INVALID_UTF8"),
            (b'{"a":1,"a":2}', "DUPLICATE_JSON_KEY"),
            (b'{"a":NaN}', "NONFINITE_JSON_CONSTANT"),
            (b'{"a":1.5}', "FLOAT_LITERAL_FORBIDDEN"),
            (b'{"a":' + b"9" * 621 + b"}", "INT_DIGIT_LIMIT"),
            (b'{"a":' + str(1 << 2048).encode() + b"}", "INT_BIT_LIMIT"),
            (b"{bad", "INVALID_JSON"),
        ]:
            with self.assertRaises(audit.AuditError) as cm:
                audit.parse_strict_json_bytes(bad_raw)
            self.assertEqual(cm.exception.code, code)
        # Boundary exact 620-digit int & allow_floats=True bit limit (kills M034 & M037!)
        ok_big = b'{"a":' + str((1 << 2048) - 1).encode() + b"}"
        self.assertEqual(audit.parse_strict_json_bytes(ok_big)["a"], (1 << 2048) - 1)
        ok_neg = b'{"a":-' + b"9" * 615 + b"}"
        self.assertEqual(audit.parse_strict_json_bytes(ok_neg)["a"], -int("9" * 615))
        with self.assertRaises(audit.AuditError) as cm:
            audit.parse_strict_json_bytes(b'{"a":' + b"1" + b"0" * 619 + b"}", allow_floats=True)
        self.assertEqual(cm.exception.code, "INT_BIT_LIMIT")
        # allow_floats=True parses float without error
        self.assertIn("a", audit.parse_strict_json_bytes(b'{"a":1.5}', allow_floats=True))

    def test_03_semantic_tamper_and_envelope_checks(self) -> None:
        cert = self._fresh_cert()

        # Envelope checks
        c_keys = copy.deepcopy(cert)
        c_keys["extra"] = 1
        with self.assertRaises(audit.AuditError) as cm:
            audit.verify_certificate_object(c_keys)
        self.assertEqual(cm.exception.code, "CERT_KEYS_MISMATCH")

        for field, bad_val, code in [
            ("schema", "bad.schema", "SCHEMA_MISMATCH"),
            ("track_id", "BAD-TRACK", "TRACK_ID_MISMATCH"),
            ("payload_sha256", "0" * 64, "PAYLOAD_SHA_MISMATCH"),
            ("certificate_sha256", "0" * 64, "CERT_SHA_MISMATCH"),
        ]:
            cand = copy.deepcopy(cert)
            cand[field] = bad_val
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_certificate_object(cand)
            self.assertEqual(cm.exception.code, code)

        # Payload key mismatch
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload({"exact": {}, "sampled": {}})
        self.assertEqual(cm.exception.code, "PAYLOAD_KEYS_MISMATCH")

        # Targeted semantic guard triggers across ALL 6 pillars + privacy + Ring-0 + bijective pin
        cases: list[tuple[str, object, str]] = [
            ("exact.provenance_tier", "wrong", "TIER_MISMATCH"),
            ("exact.s39_nyquist_third_prism_exact.white_noise_r2_to_r5_q", ["2", "3", "7/2", "18/5"], "S39_WN_MISMATCH"),
            ("exact.s39_nyquist_third_prism_exact.random_walk_r2_to_r5_q", ["3", "3", "10/3", "7/2"], "S39_RW_MISMATCH"),
            ("exact.universal_code_and_lattice_exact.c16_11_4_codeword_count", 2047, "CODE_INVARIANT_MISMATCH"),
            ("exact.universal_code_and_lattice_exact.rm14_subset_c16_verified_count", 31, "CODE_INVARIANT_MISMATCH"),
            ("exact.universal_code_and_lattice_exact.e8_total_minimal_roots", 239, "CODE_INVARIANT_MISMATCH"),
            ("exact.stage_a_gauge_invariance_exact.exact_zero_gauge_drift", False, "GAUGE_DRIFT"),
            ("sampled.provenance_tier", "wrong", "TIER_MISMATCH"),
            ("sampled.measured_live_silicon", False, "LIVE_SILICON_FLAG"),
            ("sampled.privacy_locks.audio_capture_accessed", True, "PRIVACY_VIOLATION"),
            ("sampled.privacy_locks.camera_accessed", True, "PRIVACY_VIOLATION"),
            ("sampled.privacy_locks.display_modified", True, "PRIVACY_VIOLATION"),
            ("sampled.ring0_mlos_receipt.clean_hardware_run", False, "RING0_DIRTY"),
            ("sampled.ring0_mlos_receipt.exit_code", 1, "RING0_ANOMALY"),
            ("sampled.ring0_mlos_receipt.anomaly_count", 1, "RING0_ANOMALY"),
            ("sampled.ring0_mlos_receipt.linux_kmd_baseline_vram_mib", -1, "RING0_VRAM_EXCESS"),
            ("sampled.ring0_mlos_receipt.linux_kmd_baseline_vram_mib", 5, "RING0_VRAM_EXCESS"),
            ("sampled.ring0_mlos_receipt.thermal_throttled", True, "RING0_THROTTLED"),
            ("sampled.ring0_mlos_receipt.slowdown_active", True, "RING0_THROTTLED"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.s53_multisecond_eta_ladder_q", ["1/2", "3/4", "1/4"], "P1_LADDER_ORDER"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.s53_multisecond_eta_ladder_q", ["3/4", "1/2"], "P1_LADDER_ORDER"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.live_100hz_mean_psys_mw_q", "999999999", "P1_PSYS_OBSTRUCTION"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.live_100hz_mean_psys_mw_q", "112072963/1600", "P1_PSYS_OBSTRUCTION"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.live_100hz_mean_dark_inpkg_mw_q", "0", "NONPOSITIVE_VALUE"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.psys_vendor_scale_obstruction_ratio_r6_q", "1", "P1_RATIO_MISMATCH"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.schur_100hz_mean_eta_r6_q", "1/2", "P1_RC_OBSTRUCTION"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.schur_100hz_mean_eta_r6_q", "448340210833/500000000000", "P1_RC_OBSTRUCTION"),
            ("sampled.pillar_2_hysteresis_and_yield_wall.l3_over_l1_latency_cliff_q", "1", "P2_CLIFF_MISMATCH"),
            ("sampled.pillar_2_hysteresis_and_yield_wall.dram_over_l1_latency_cliff_q", "1", "P2_CLIFF_MISMATCH"),
            ("sampled.pillar_2_hysteresis_and_yield_wall.green_2area_tpkg_cpufan_closed", 0, "P2_ZERO_HYSTERESIS"),
            ("sampled.pillar_2_hysteresis_and_yield_wall.green_2area_tpkg_ppkg_closed", 0, "P2_ZERO_HYSTERESIS"),
            ("sampled.pillar_3_spectral_prism_and_nulls.rdtsc_dram_64mib.s39_r2_to_r5_r6_q", [], "P3_PRISM_LEN"),
            ("sampled.pillar_3_spectral_prism_and_nulls.rdtsc_dram_64mib.s39_r2_to_r5_r6_q", ["2", "3", "3"], "P3_PRISM_LEN"),
            ("sampled.pillar_3_spectral_prism_and_nulls.rdtsc_dram_64mib.s39_shuffle_null_r2_to_r5_r6_q", [], "P3_PRISM_LEN"),
            ("sampled.pillar_3_spectral_prism_and_nulls.rdtsc_dram_64mib.s39_shuffle_null_r2_to_r5_r6_q", ["3", "3", "3"], "P3_PRISM_LEN"),
            ("sampled.pillar_3_spectral_prism_and_nulls.rdtsc_dram_64mib.s39_r2_to_r5_r6_q", ["4", "3", "3", "3"], "P3_DRAM_NULL"),
            ("sampled.pillar_3_spectral_prism_and_nulls.live_100hz_channels.dark_inpkg_mw.s39_r2_to_r5_r6_q", [], "P3_PRISM_LEN"),
            ("sampled.pillar_3_spectral_prism_and_nulls.live_100hz_channels.dark_inpkg_mw.s39_r2_to_r5_r6_q", ["4", "3", "3"], "P3_PRISM_LEN"),
            ("sampled.pillar_3_spectral_prism_and_nulls.live_100hz_channels.dark_inpkg_mw.s39_r2_to_r5_r6_q", ["3", "3", "3", "3"], "P3_SUPER_NYQUIST"),
            ("sampled.pillar_4_allometric_pl1_ceiling.work_per_core_gops_s_r6_q", ["1", "2", "3", "4", "5"], "P4_WPC_ORDER"),
            ("sampled.pillar_4_allometric_pl1_ceiling.work_per_core_gops_s_r6_q", ["5", "4", "3"], "P4_WPC_ORDER"),
            ("sampled.pillar_4_allometric_pl1_ceiling.pkg_power_spread_pct_r6_q", "1", "P4_PL1_FLATNESS"),
            ("sampled.pillar_5_landauer_thermodynamic_gap.exp3_p8_landauer_ratio_bracket", [1], "P5_BRACKET_LEN"),
            ("sampled.pillar_5_landauer_thermodynamic_gap.exp3_p1_landauer_ratio_bracket", [1], "P5_BRACKET_LEN"),
            ("sampled.pillar_5_landauer_thermodynamic_gap.exp3_p1_landauer_ratio_bracket", [10**11, 10**11 + 1], "P5_LANDAUER_GAP"),
            ("sampled.pillar_6_universal_code_vs_weight_anisotropy.qwen_05b_a16_block_h2_over_axis_wt_kl_q", "1", "P6_CROSSOVER"),
            ("sampled.pillar_6_universal_code_vs_weight_anisotropy.qwen_15b_a16_block_h2_over_axis_wt_kl_q", "1", "P6_CROSSOVER"),
            ("sampled.pillar_6_universal_code_vs_weight_anisotropy.qwen_15b_regime1_axis_layers", 100, "P6_LAYER_SUM"),
            ("anchor.provenance_tier", "wrong", "TIER_MISMATCH"),
            ("anchor.cs13_citations", [], "ANCHOR_CITES_SHORT"),
            ("sampled.ring0_mlos_receipt.linux_kmd_baseline_vram_mib", 0, "PAYLOAD_PIN_MISMATCH"),
            ("sampled.ring0_mlos_receipt.linux_kmd_baseline_vram_mib", 4, "PAYLOAD_PIN_MISMATCH"),
            ("sampled.pillar_1_dark_mode_schur_and_gauge.live_100hz_n_ticks", 1599, "PAYLOAD_PIN_MISMATCH"),
        ]
        for dotted, new_val, expected_code in cases:
            payload = copy.deepcopy(cert["payload"])
            parts = dotted.split(".")
            cur = payload
            for k in parts[:-1]:
                cur = cur[k]
            cur[parts[-1]] = new_val
            resigned = self._resign(payload)
            with self.assertRaises(audit.AuditError, msg=f"failed on {dotted}") as cm:
                audit.verify_certificate_object(resigned)
            self.assertEqual(cm.exception.code, expected_code, msg=f"wrong code on {dotted}")

        # Boundary checks for non-positive denominator safety (0 -> NONPOSITIVE_VALUE, never ZeroDivisionError)
        for dotted in (
            "sampled.pillar_1_dark_mode_schur_and_gauge.live_100hz_mean_psys_mw_q",
            "sampled.pillar_2_hysteresis_and_yield_wall.l1_16kib_p50_cyc_per_step_q",
        ):
            payload = copy.deepcopy(cert["payload"])
            parts = dotted.split(".")
            cur = payload
            for k in parts[:-1]:
                cur = cur[k]
            cur[parts[-1]] = "0"
            with self.assertRaises(audit.AuditError) as cm:
                audit.secondary_audit_payload(payload)
            self.assertEqual(cm.exception.code, "NONPOSITIVE_VALUE")

        # Extra nested key rejected by bijective pin
        payload_extra = copy.deepcopy(cert["payload"])
        payload_extra["sampled"]["pillar_6_universal_code_vs_weight_anisotropy"]["sneaky"] = 1
        with self.assertRaises(audit.AuditError) as cm:
            audit.secondary_audit_payload(payload_extra)
        self.assertEqual(cm.exception.code, "PAYLOAD_PIN_MISMATCH")

    def test_04_hardened_io_symlinks_hardlinks_fifo_pwd_darwin_and_atomic_errors(self) -> None:
        cert = self._fresh_cert()
        raw = oracle.canonical_json_bytes(cert)

        # Path object validation
        for bad_path, code in [
            ("not_a_path", "INVALID_PATH_TYPE"),
            (Path("bad\ud800path"), "INVALID_UNICODE_STR"),
            (Path("bad\x00path"), "INVALID_PATH"),
            (Path("/"), "INVALID_PATH"),
            (Path("."), "INVALID_PATH"),
            (Path(".."), "INVALID_PATH"),
            (Path("../b"), "PARENT_TRAVERSAL_FORBIDDEN"),
        ]:
            with self.assertRaises(audit.AuditError) as cm:
                audit._open_parent_dir_fd(bad_path)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, code)

        # Darwin system prefix normalization (simulated) + non-darwin fast-return & SUBCOND_DEL kills
        with mock.patch.object(audit.sys, "platform", "linux"), mock.patch("os.lstat", side_effect=RuntimeError("no lstat on linux")):
            self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))
        with mock.patch.object(audit.sys, "platform", "darwin"):
            self.assertEqual(audit._normalize_darwin_system_prefix(Path("/")), Path("/"))
            with mock.patch("os.lstat", side_effect=RuntimeError("no lstat on non-system link")):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/usr/a")), Path("/usr/a"))
            st_lnk = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch("os.lstat", return_value=st_lnk), mock.patch("os.readlink", return_value="private/tmp"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/a/b")), Path("/private/tmp/a/b"))
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("rel/tmp/a")), Path("rel/tmp/a"))
            st_dir_root = os.stat_result((stat.S_IFDIR | 0o755, 1, 1, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch("os.lstat", return_value=st_dir_root), mock.patch("os.readlink", return_value="private/tmp"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))
            with mock.patch("os.lstat", side_effect=OSError("no")):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))
            st_nonroot = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 1000, 1000, 0, 0, 0, 0))
            with mock.patch("os.lstat", return_value=st_nonroot), mock.patch("os.readlink", return_value="private/tmp"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))
            with mock.patch("os.lstat", return_value=st_lnk), mock.patch("os.readlink", return_value="other/tmp"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.chmod(root, 0o700)

            # Atomic 0o600 write, overwrite existing regular file (st_nlink==1, kills M071), & read-back
            nested = root / "sub1" / "sub2" / "cert.json"
            audit.write_regular_bytes_atomic_0600(nested, raw)
            audit.write_regular_bytes_atomic_0600(nested, raw)
            self.assertEqual(stat.S_IMODE(os.lstat(nested).st_mode), 0o600)
            self.assertEqual(audit.read_regular_bytes_safe(nested), raw)
            self.assertTrue(audit.check_certificate_file(nested)["valid"])

            # Strict False return on missing symlink probe (kills M045)
            rfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertIs(audit._is_symlink_at(rfd, "does_not_exist"), False)
            finally:
                os.close(rfd)

            # Missing file & missing ancestor dir (must not create ancestor, kills M054)
            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_bytes_safe(root / "no_such_dir" / "x.json")
            self.assertEqual(cm.exception.code, "FILE_NOT_FOUND")
            self.assertFalse((root / "no_such_dir").exists())
            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_bytes_safe(root / "missing.json")
            self.assertEqual(cm.exception.code, "FILE_NOT_FOUND")

            # Symlink target & symlink ancestor
            sym_file = root / "sym.json"
            os.symlink(nested, sym_file)
            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_bytes_safe(sym_file)
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(audit.AuditError) as cm:
                audit.write_regular_bytes_atomic_0600(sym_file, raw)
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")

            sym_dir = root / "sym_dir"
            os.symlink(nested.parent, sym_dir)
            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_bytes_safe(sym_dir / "cert.json")
            self.assertEqual(cm.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

            # Non-dir ancestor file -> DIR_OPEN_ERROR
            plain = root / "plain.txt"
            plain.write_bytes(b"hi")
            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_bytes_safe(plain / "child.json")
            self.assertEqual(cm.exception.code, "DIR_OPEN_ERROR")

            # Hardlink rejection on read, write target, and temp file
            hl = root / "hl.json"
            os.link(nested, hl)
            try:
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_bytes_safe(hl)
                self.assertEqual(cm.exception.code, "HARDLINK_FORBIDDEN")
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(hl, raw)
                self.assertEqual(cm.exception.code, "HARDLINK_FORBIDDEN")
            finally:
                hl.unlink()

            # Scratch FIFO (zero system device path writes!)
            fifo_p = root / "test.fifo"
            os.mkfifo(fifo_p, 0o600)
            with self.assertRaises(audit.AuditError) as cm:
                audit.read_regular_bytes_safe(fifo_p)
            self.assertEqual(cm.exception.code, "NON_REGULAR_FILE")
            with self.assertRaises(audit.AuditError) as cm:
                audit.write_regular_bytes_atomic_0600(fifo_p, raw)
            self.assertEqual(cm.exception.code, "NON_REGULAR_TARGET")

            # Read-only 0o500 dir direct & nested mkdir -> typed ATOMIC_WRITE_ERROR
            ro_dir = root / "ro_dir"
            ro_dir.mkdir(mode=0o700)
            os.chmod(ro_dir, 0o500)
            try:
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(ro_dir / "out.json", raw)
                self.assertEqual(cm.exception.code, "ATOMIC_WRITE_ERROR")
                self.assertIn("cannot create temp file", cm.exception.message)
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(ro_dir / "sub" / "out.json", raw)
                self.assertEqual(cm.exception.code, "ATOMIC_WRITE_ERROR")
                self.assertIn("cannot create ancestor", cm.exception.message)
                self.assertEqual(list(ro_dir.iterdir()), [])
            finally:
                os.chmod(ro_dir, 0o700)

            # Bounded EEXIST retries + wrapped lstat / write / short-write / hardlink-tmp / replace errors
            real_open = os.open
            eexist_hits = 0
            def _eexist_excl(p, flags, *args, **kwargs):
                nonlocal eexist_hits
                if flags & os.O_EXCL:
                    eexist_hits += 1
                    raise FileExistsError("dup")
                return real_open(p, flags, *args, **kwargs)
            with mock.patch("os.open", side_effect=_eexist_excl):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(root / "eexist.json", raw)
                self.assertEqual(cm.exception.code, "ATOMIC_WRITE_ERROR")
            self.assertEqual(eexist_hits, audit._MAX_TMP_RETRIES)

            with mock.patch("os.lstat", side_effect=PermissionError("denied")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(root / "lstat_err.json", raw)
                self.assertEqual(cm.exception.code, "ATOMIC_WRITE_ERROR")

            with mock.patch("os.write", return_value=0):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(root / "short_wr.json", raw)
                self.assertEqual(cm.exception.code, "SHORT_WRITE")

            with mock.patch("os.write", side_effect=OSError("disk full")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(root / "os_wr.json", raw)
                self.assertEqual(cm.exception.code, "ATOMIC_WRITE_ERROR")

            real_fstat = os.fstat
            def _nlink2_fstat(fd: int):
                st = real_fstat(fd)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, 2, st.st_uid, st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime))
            with mock.patch("os.fstat", side_effect=_nlink2_fstat):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(root / "hl_tmp.json", raw)
                self.assertEqual(cm.exception.code, "HARDLINK_FORBIDDEN")

            with mock.patch("os.replace", side_effect=OSError("replace fail")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.write_regular_bytes_atomic_0600(root / "rep_err.json", raw)
                self.assertEqual(cm.exception.code, "ATOMIC_WRITE_ERROR")

            # Unreadable file -> FILE_OPEN_ERROR
            unr = root / "unreadable.json"
            unr.write_bytes(b"{}")
            os.chmod(unr, 0o000)
            try:
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_bytes_safe(unr)
                self.assertEqual(cm.exception.code, "FILE_OPEN_ERROR")
            finally:
                os.chmod(unr, 0o600)

            # Exact size boundary & streaming cap (including fstat st_size==0 procfs simulation)
            big = root / "big.json"
            big.write_bytes(b"a" * 32)
            self.assertEqual(len(audit.read_regular_bytes_safe(big, max_bytes=32)), 32)
            with mock.patch("os.read", side_effect=RuntimeError("must fast-reject before os.read")):
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_bytes_safe(big, max_bytes=16)
                self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")

            def _zero_size_fstat(fd: int):
                st = real_fstat(fd)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid, st.st_gid, 0, st.st_atime, st.st_mtime, st.st_ctime))
            with mock.patch("os.fstat", side_effect=_zero_size_fstat):
                self.assertEqual(len(audit.read_regular_bytes_safe(big, max_bytes=32)), 32)
                with self.assertRaises(audit.AuditError) as cm:
                    audit.read_regular_bytes_safe(big, max_bytes=16)
                self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")

            # Non-canonical JSON file rejection
            pretty = root / "pretty.json"
            pretty.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(audit.AuditError) as cm:
                audit.check_certificate_file(pretty)
            self.assertEqual(cm.exception.code, "NON_CANONICAL_BYTES")

            # $PWD symlink ancestor checks (relative path + inode match + surrogate + stale PWD)
            real_sub = root / "real_sub"
            real_sub.mkdir(mode=0o700)
            (real_sub / "ok.json").write_bytes(raw)
            sym_sub = root / "sym_sub"
            os.symlink(real_sub, sym_sub)
            orig_cwd = os.getcwd()
            try:
                os.chdir(real_sub)
                with mock.patch.dict(os.environ, {"PWD": str(sym_sub)}):
                    with self.assertRaises(audit.AuditError) as cm:
                        audit.read_regular_bytes_safe(Path("ok.json"))
                    self.assertEqual(cm.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
                with mock.patch.object(audit.os, "environ", {"PWD": str(real_sub) + "\ud800"}):
                    with self.assertRaises(audit.AuditError) as cm:
                        audit._check_pwd_no_symlinks()
                    self.assertEqual(cm.exception.code, "INVALID_UNICODE_STR")
                with mock.patch.object(audit.os, "environ", {}):
                    audit._check_pwd_no_symlinks()
                with mock.patch.dict(os.environ, {"PWD": "relative_pwd"}):
                    with mock.patch("os.stat", side_effect=RuntimeError("must not stat relative PWD")):
                        audit._check_pwd_no_symlinks()
                with mock.patch.dict(os.environ, {"PWD": str(root)}):
                    audit._check_pwd_no_symlinks()
                with mock.patch.dict(os.environ, {"PWD": str(real_sub)}):
                    audit._check_pwd_no_symlinks()
                with mock.patch.dict(os.environ, {"PWD": str(real_sub)}):
                    with mock.patch("os.stat", side_effect=OSError("stat fail")):
                        audit._check_pwd_no_symlinks()
                with mock.patch.dict(os.environ, {"PWD": str(real_sub)}):
                    real_open_pwd = os.open
                    def _fail_second(p, fl, *a, **kw):
                        if p != "/":
                            raise PermissionError("blocked")
                        return real_open_pwd(p, fl, *a, **kw)
                    with mock.patch("os.open", side_effect=_fail_second):
                        with self.assertRaises(audit.AuditError) as cm:
                            audit._check_pwd_no_symlinks()
                        self.assertEqual(cm.exception.code, "PWD_WALK_ERROR")
            finally:
                os.chdir(orig_cwd)

    def test_05_live_receipts_and_raw_integer_replay(self) -> None:
        # Live receipt + full raw integer array replay against real Track S64 capture
        res = audit.verify_live_receipts(HERE)
        self.assertTrue(res["all_verified"])
        self.assertEqual(res["files_verified"], 3)
        self.assertTrue(res["raw_integer_replay_exact"])
        self.assertTrue(res["live_11ch_stage_a_gauge_exact_zero"])

        # Tampered receipt / mlos fields / replay mismatch coverage
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            for fname in ("granular_silicon_microprobe.c", "granular_silicon_capture.json", "mlos_zone_b_receipt.json"):
                (tdp / fname).write_bytes((HERE / fname).read_bytes())

            # Digest mismatch
            (tdp / "granular_silicon_microprobe.c").write_bytes(b"// tampered\n")
            with self.assertRaises(audit.AuditError) as cm:
                audit.verify_live_receipts(tdp)
            self.assertEqual(cm.exception.code, "RECEIPT_SHA_MISMATCH")
            (tdp / "granular_silicon_microprobe.c").write_bytes((HERE / "granular_silicon_microprobe.c").read_bytes())

            # mlos receipt field guards (bypassing SHA check via mock to verify independent semantic guards!)
            orig_rcp = json.loads((HERE / "mlos_zone_b_receipt.json").read_bytes())
            for mod_key, mod_val, code in [
                ("clean_hardware_run", False, "MLOS_DIRTY_RUN"),
                ("anomalies", ["thermal"], "MLOS_ANOMALIES"),
                ("determinism_zone", "A", "MLOS_ZONE_MISMATCH"),
                ("receipt_sha256", "0" * 64, "MLOS_INNER_SHA_MISMATCH"),
                ("profile_sha256", "0" * 64, "MLOS_PROFILE_SHA_MISMATCH"),
            ]:
                bad_rcp = copy.deepcopy(orig_rcp)
                bad_rcp[mod_key] = mod_val
                bad_bytes = json.dumps(bad_rcp).encode("utf-8")
                bad_sha = oracle.sha256_hex(bad_bytes)
                (tdp / "mlos_zone_b_receipt.json").write_bytes(bad_bytes)
                patched = dict(oracle.PINNED_S64_DIGESTS)
                patched["mlos_zone_b_receipt_json"] = bad_sha
                with mock.patch.dict(oracle.PINNED_S64_DIGESTS, patched):
                    with self.assertRaises(audit.AuditError) as cm:
                        audit.verify_live_receipts(tdp)
                    self.assertEqual(cm.exception.code, code)
            (tdp / "mlos_zone_b_receipt.json").write_bytes((HERE / "mlos_zone_b_receipt.json").read_bytes())

            # Replay mismatch guards across Pillars 1..5
            good_replay = oracle.recompute_from_raw_capture(
                json.loads((HERE / "granular_silicon_capture.json").read_bytes())
            )
            for mut_fn, msg_hint in (
                (lambda r: r["exp2"].__setitem__("mean_pkg_mw_q", "1"), "Pillar-1"),
                (lambda r: r["exp2"].__setitem__("green_2area_tpkg_cpufan_closed", 0), "Pillar-2"),
                (lambda r: r["exp2"].__setitem__("ramp_up_2c_mean_tpkg_mc_q", "1"), "ramp_up_2c"),
                (lambda r: r["exp2"].__setitem__("ramp_down_2c_mean_tpkg_mc_q", "1"), "ramp_down_2c"),
                (lambda r: r["exp1"]["l1_16kib_quiescent"].__setitem__("p50_cyc_per_step_q", "1"), "Pillar-2 exp1"),
                (lambda r: r["exp1"]["l1_16kib_quiescent"].__setitem__("s39_r2_to_r5_r6_q", ["1", "1", "1", "1"]), "Pillar-3"),
                (lambda r: r["exp1"]["l3_16mib_boundary"].__setitem__("s39_r2_to_r5_r6_q", ["1", "1", "1", "1"]), "Pillar-3"),
                (lambda r: r["exp1"]["dram_64mib_chase"].__setitem__("s39_r2_to_r5_r6_q", ["1", "1", "1", "1"]), "Pillar-3"),
                (lambda r: r["exp2"]["channels_spectral"].__setitem__("pkg_mw", {}), "Pillar-3"),
                (lambda r: r["exp3"].__setitem__("pkg_power_spread_pct_r6_q", "99"), "Pillar-4"),
                (lambda r: r["exp3"].__setitem__("p1_temp_k_q", "300"), "Pillar-5"),
                (lambda r: r["exp3"].__setitem__("p8_temp_k_q", "300"), "Pillar-5"),
                (lambda r: r["exp3"].__setitem__("p1_landauer_ratio_bracket", [1, 2]), "Pillar-5"),
                (lambda r: r["exp3"].__setitem__("p8_landauer_ratio_bracket", [1, 2]), "Pillar-5"),
            ):
                bad_rep = copy.deepcopy(good_replay)
                mut_fn(bad_rep)
                with mock.patch.object(oracle, "recompute_from_raw_capture", return_value=bad_rep):
                    with self.assertRaises(audit.AuditError) as cm:
                        audit.verify_live_receipts(tdp)
                    self.assertEqual(cm.exception.code, "REPLAY_MISMATCH")
                    self.assertIn(msg_hint, cm.exception.message)

    def test_06_cli_hardening_and_modes(self) -> None:
        cert = self._fresh_cert()
        raw = oracle.canonical_json_bytes(cert)

        # In-process CLI coverage (valid modes + error handling)
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            out_p = tdp / "out_cert.json"

            for std_argv in ([], ["--json"], ["--standalone", "--json"]):
                buf = io.StringIO()
                with mock.patch.object(sys, "stdout", buf):
                    self.assertEqual(audit.main(std_argv), 0)
                self.assertEqual(buf.getvalue().encode("utf-8"), raw)

            # Separate --write alone & --check alone (kills all L816 SUBCOND_DEL mutants)
            buf = io.StringIO()
            with mock.patch.object(sys, "stdout", buf):
                self.assertEqual(audit.main(["--write", str(out_p)]), 0)
            w_obj = json.loads(buf.getvalue())
            self.assertTrue(w_obj["valid"] and w_obj["written"])
            self.assertEqual(stat.S_IMODE(os.lstat(out_p).st_mode), 0o600)
            self.assertEqual(out_p.read_bytes(), raw)

            buf = io.StringIO()
            with mock.patch.object(sys, "stdout", buf):
                self.assertEqual(audit.main(["--check", str(out_p)]), 0)
            c_obj = json.loads(buf.getvalue())
            self.assertTrue(c_obj["valid"] and c_obj["check"]["valid"])

            buf = io.StringIO()
            with mock.patch.object(sys, "stdout", buf):
                self.assertEqual(audit.main(("--write", str(out_p), "--check", str(out_p), "--json")), 0)
            self.assertTrue(json.loads(buf.getvalue())["valid"])

            buf = io.StringIO()
            with mock.patch.object(audit, "verify_live_receipts", return_value={"all_verified": True}) as mock_vr:
                with mock.patch.object(sys, "stdout", buf):
                    self.assertEqual(audit.main(["--verify-receipts", str(HERE), "--json"]), 0)
                self.assertTrue(json.loads(buf.getvalue())["receipts"]["all_verified"])
                mock_vr.assert_called_once_with(HERE)

            for bare_vr in (["--verify-receipts"], ["--verify-receipts", "--json"]):
                buf = io.StringIO()
                with mock.patch.object(audit, "verify_live_receipts", return_value={"all_verified": True}) as mock_vr:
                    with mock.patch.object(sys, "stdout", buf):
                        self.assertEqual(audit.main(bare_vr), 0)
                    self.assertTrue(json.loads(buf.getvalue())["receipts"]["all_verified"])
                    mock_vr.assert_called_once_with(Path("."))

            # Empty prism list re-signed cert -> clean CLI JSON rc=1 P3_PRISM_LEN (no IndexError)
            bad_p = copy.deepcopy(cert["payload"])
            bad_p["sampled"]["pillar_3_spectral_prism_and_nulls"]["rdtsc_dram_64mib"]["s39_r2_to_r5_r6_q"] = []
            bad_cert = self._resign(bad_p)
            bad_f = tdp / "empty_prism.json"
            bad_f.write_bytes(oracle.canonical_json_bytes(bad_cert))
            proc_bad = subprocess.run(
                [sys.executable, "-I", "-B", str(HERE / "silicon_universal_audit.py"), "--check", str(bad_f)],
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc_bad.returncode, 1)
            self.assertEqual(proc_bad.stderr, b"")
            self.assertEqual(json.loads(proc_bad.stdout.decode("utf-8"))["error_code"], "P3_PRISM_LEN")

            # Hostile / malformed CLI args fail closed with rc=1 & exact error_code, zero stray files
            for bad_argv, expected_code in (
                (123, "INVALID_CLI_ARGS"),
                (["--check", 123], "INVALID_CLI_ARGS"),
                (["--unknown"], "INVALID_CLI_ARGS"),
                (["--write"], "INVALID_CLI_ARGS"),
                (["--check"], "INVALID_CLI_ARGS"),
                (["--write", "--json"], "INVALID_CLI_ARGS"),
                (["--check", "-bad"], "INVALID_CLI_ARGS"),
                (["--write", ""], "INVALID_CLI_ARGS"),
                (["--check", str(tdp / "nonexistent.json")], "FILE_NOT_FOUND"),
            ):
                buf = io.StringIO()
                with mock.patch.object(sys, "stdout", buf):
                    rc = audit.main(bad_argv)
                self.assertEqual(rc, 1)
                obj = json.loads(buf.getvalue())
                self.assertFalse(obj["valid"])
                self.assertEqual(obj["error_code"], expected_code)
            self.assertFalse((HERE / "--json").exists())

        # Subprocess -I -B standalone parity check
        proc = subprocess.run(
            [sys.executable, "-I", "-B", str(HERE / "silicon_universal_audit.py"), "--standalone"],
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, raw)


if __name__ == "__main__":
    unittest.main()
