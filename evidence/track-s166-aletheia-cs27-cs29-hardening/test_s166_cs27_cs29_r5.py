#!/usr/bin/env python3
"""
Standalone R1-R5 tests for `verify_s166_cs27_cs29.py` (CI `evidence-tracks` target).

Zero external dependencies, zero bare asserts, 100% parity across:
  python3 -I -B test_s166_cs27_cs29_r5.py
  python3 -I -O -B test_s166_cs27_cs29_r5.py
  python3 -I -B -W error test_s166_cs27_cs29_r5.py
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import py_compile
import re
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import verify_s166_cs27_cs29 as v  # noqa: E402


def _mock_runner_ok(_track_dir: Path) -> dict:
    lines = []
    for thm in v.LEAN_THEOREMS:
        if thm.endswith("concrete_witness"):
            lines.append(f"'{thm}' does not depend on any axioms")
        else:
            lines.append(f"'{thm}' depends on axioms: [propext, Quot.sound]")
    return {
        "version_rc": 0,
        "version_output": "Lean (version 4.36.0)",
        "build_rc": 0,
        "build_output": "Build completed successfully",
        "axiom_rc": 0,
        "axiom_stdout": "\n".join(lines) + "\n",
    }


def _stage_bundle(root: Path) -> Path:
    bundle = root / "bundle"
    bundle.mkdir()
    for fname in v.LEAN_FILES:
        shutil.copyfile(HERE / fname, bundle / fname)
    return bundle


class TestVerifyS166R5(unittest.TestCase):
    def _need_err(self, fn, code: str, *args, **kwargs) -> None:
        with self.assertRaises(v.VerifyS166Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_01_write_check_and_negative_controls(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = _stage_bundle(root)
            cert_path = root / "cert.json"
            cert = v.build_certificate(bundle, live_lean=True, lean_runner=_mock_runner_ok)
            v._atomic_write_lf(cert_path, v._canon_bytes(cert))
            chk = v.verify_certificate_file(cert_path, bundle, live_lean=True, lean_runner=_mock_runner_ok)
            self.assertTrue(chk["passed"])
            self.assertEqual(chk["lean_static_status"], "STATIC_PASS")
            self.assertEqual(chk["lean_live_mode"], "LIVE_LEAN_4_36_0_PASS")
            self.assertIs(chk["live_lean_checked"], True)
            self.assertEqual(chk["axioms_verified_count"], len(v.LEAN_THEOREMS))
            self.assertEqual(chk["lean_theorems_verified"], len(v.LEAN_THEOREMS))

            # Tamper checks: R1/R2/R3
            bad_keys = dict(cert)
            del bad_keys["exp_q46b_bypass_checks"]
            p_bk = root / "bk.json"
            p_bk.write_bytes(v._canon_bytes(bad_keys))
            self._need_err(v.verify_certificate_file, "CERT_KEY_MISMATCH", p_bk, bundle)

            bad_schema = dict(cert, schema_version="bad")
            p_bs = root / "bs.json"
            p_bs.write_bytes(v._canon_bytes(bad_schema))
            self._need_err(v.verify_certificate_file, "CERT_SCHEMA_MISMATCH", p_bs, bundle)

            bad_hex = dict(cert, payload_sha256="zz" * 32)
            p_bh = root / "bh.json"
            p_bh.write_bytes(v._canon_bytes(bad_hex))
            self._need_err(v.verify_certificate_file, "BAD_PAYLOAD_SHA256", p_bh, bundle)

            bad_sha = dict(cert, payload_sha256="0" * 64)
            p_bsha = root / "bsha.json"
            p_bsha.write_bytes(v._canon_bytes(bad_sha))
            self._need_err(v.verify_certificate_file, "PAYLOAD_SHA256_MISMATCH", p_bsha, bundle)

            # Re-signed tampered section must fail RECOMPUTE_MISMATCH (built from static_cert so offline check reaches recomputation)
            static_cert = v.build_certificate(bundle, live_lean=False)
            tampered = dict(static_cert)
            tampered["cs27_dag_and_portfolio"] = {"acyclic_dag_verified": False}
            unsigned = {k: tampered[k] for k in tampered if k != "payload_sha256"}
            tampered["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(unsigned)).hexdigest()
            p_tam = root / "tam.json"
            p_tam.write_bytes(v._canon_bytes(tampered))
            self._need_err(v.verify_certificate_file, "RECOMPUTE_MISMATCH", p_tam, bundle)

            # Re-signed stale Lean hash / theorem count
            t_hash = json.loads(json.dumps(cert))
            t_hash["lean_bundle"]["file_sha256"]["lean-toolchain"] = "0" * 64
            u_h = {k: t_hash[k] for k in t_hash if k != "payload_sha256"}
            t_hash["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_h)).hexdigest()
            p_th = root / "th.json"
            p_th.write_bytes(v._canon_bytes(t_hash))
            self._need_err(v.verify_certificate_file, "LEAN_HASH_MISMATCH", p_th, bundle)

            t_thm = json.loads(json.dumps(cert))
            t_thm["lean_bundle"]["public_theorems"] = 99
            u_t = {k: t_thm[k] for k in t_thm if k != "payload_sha256"}
            t_thm["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_t)).hexdigest()
            p_tt = root / "tt.json"
            p_tt.write_bytes(v._canon_bytes(t_thm))
            self._need_err(v.verify_certificate_file, "LEAN_THEOREM_MISMATCH", p_tt, bundle)

            for bad_lb_val in ({}, []):
                t_lb = json.loads(json.dumps(cert))
                t_lb["lean_bundle"] = bad_lb_val
                u_lb = {k: t_lb[k] for k in t_lb if k != "payload_sha256"}
                t_lb["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_lb)).hexdigest()
                p_tlb = root / f"lb_{type(bad_lb_val).__name__}.json"
                p_tlb.write_bytes(v._canon_bytes(t_lb))
                self._need_err(v.verify_certificate_file, "LEAN_BUNDLE_KEY_MISMATCH", p_tlb, bundle)

            # [MED-1] Strict type-exact equality: bool-for-int spoof + dict key / list length mismatch
            t_bool = json.loads(json.dumps(static_cert))
            t_bool["cs29_crossover_grid"][0]["dk"] = False
            u_bool = {k: t_bool[k] for k in t_bool if k != "payload_sha256"}
            t_bool["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_bool)).hexdigest()
            p_bool = root / "bool_spoof.json"
            p_bool.write_bytes(v._canon_bytes(t_bool))
            self._need_err(v.verify_certificate_file, "RECOMPUTE_MISMATCH", p_bool, bundle)
            bo_s, be_s = io.StringIO(), io.StringIO()
            with redirect_stdout(bo_s), redirect_stderr(be_s):
                self.assertEqual(v.main(["--track-dir", str(bundle), "--check", str(p_bool)]), 2)

            t_len = json.loads(json.dumps(static_cert))
            t_len["cs29_crossover_grid"] = t_len["cs29_crossover_grid"][:-1]
            u_len = {k: t_len[k] for k in t_len if k != "payload_sha256"}
            t_len["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_len)).hexdigest()
            p_len = root / "len_spoof.json"
            p_len.write_bytes(v._canon_bytes(t_len))
            self._need_err(v.verify_certificate_file, "RECOMPUTE_MISMATCH", p_len, bundle)

            t_mkey = json.loads(json.dumps(static_cert))
            del t_mkey["cs27_dag_and_portfolio"]["symmetric_gh_hf_coverage_q"]
            u_mkey = {k: t_mkey[k] for k in t_mkey if k != "payload_sha256"}
            t_mkey["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_mkey)).hexdigest()
            p_mkey = root / "mkey_spoof.json"
            p_mkey.write_bytes(v._canon_bytes(t_mkey))
            self._need_err(v.verify_certificate_file, "RECOMPUTE_MISMATCH", p_mkey, bundle)

            # [LOW-6] lean_bundle metadata spoofs (toolchain, lean_static_status, lean_live_mode, live_lean_checked, axioms_verified_count) & trailing LF
            t_tc = json.loads(json.dumps(cert))
            t_tc["lean_bundle"]["lean_toolchain"] = "SPOOFED_TOOLCHAIN"
            u_tc = {k: t_tc[k] for k in t_tc if k != "payload_sha256"}
            t_tc["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_tc)).hexdigest()
            p_tc = root / "tc_spoof.json"
            p_tc.write_bytes(v._canon_bytes(t_tc))
            self._need_err(v.verify_certificate_file, "LEAN_TOOLCHAIN_MISMATCH", p_tc, bundle)

            t_ss = json.loads(json.dumps(cert))
            t_ss["lean_bundle"]["lean_static_status"] = "STATIC_FAIL"
            u_ss = {k: t_ss[k] for k in t_ss if k != "payload_sha256"}
            t_ss["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_ss)).hexdigest()
            p_ss = root / "ss_spoof.json"
            p_ss.write_bytes(v._canon_bytes(t_ss))
            self._need_err(v.verify_certificate_file, "LEAN_STATIC_STATUS_MISMATCH", p_ss, bundle)

            t_ls = json.loads(json.dumps(cert))
            t_ls["lean_bundle"]["lean_live_mode"] = "FAKE_LIVE"
            t_ls["lean_bundle"]["live_lean_checked"] = False
            t_ls["lean_bundle"]["axioms_verified_count"] = 0
            u_ls = {k: t_ls[k] for k in t_ls if k != "payload_sha256"}
            t_ls["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_ls)).hexdigest()
            p_ls = root / "ls_spoof.json"
            p_ls.write_bytes(v._canon_bytes(t_ls))
            self._need_err(v.verify_certificate_file, "LEAN_LIVE_STATUS_INVALID", p_ls, bundle)

            for bad_chk in (False, 1):
                t_lc = json.loads(json.dumps(cert))
                t_lc["lean_bundle"]["live_lean_checked"] = bad_chk
                u_lc = {k: t_lc[k] for k in t_lc if k != "payload_sha256"}
                t_lc["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_lc)).hexdigest()
                p_lc = root / f"lc_{bad_chk}.json"
                p_lc.write_bytes(v._canon_bytes(t_lc))
                self._need_err(v.verify_certificate_file, "LEAN_LIVE_STATUS_INVALID", p_lc, bundle)

            for bad_ax in (999, True):
                t_ax = json.loads(json.dumps(cert))
                t_ax["lean_bundle"]["axioms_verified_count"] = bad_ax
                u_ax = {k: t_ax[k] for k in t_ax if k != "payload_sha256"}
                t_ax["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_ax)).hexdigest()
                p_ax = root / f"ax_{bad_ax}.json"
                p_ax.write_bytes(v._canon_bytes(t_ax))
                self._need_err(v.verify_certificate_file, "LEAN_AXIOM_COUNT_MISMATCH", p_ax, bundle)

            # [MED-3] & [LOW-2] Static --check MUST reject forged live_lean_checked=True BEFORE running _compute_static_sections
            with mock.patch.object(v, "_compute_static_sections", side_effect=RuntimeError("must reject before recompute")):
                self._need_err(v.verify_certificate_file, "LEAN_LIVE_STATUS_MISMATCH", cert_path, bundle, live_lean=False)

            # [HIGH-2] Pre-execution integrity gate: tampered Lean or hash mismatch MUST fail BEFORE running Lean!
            runner_called = False

            def _spy_runner(_td: Path) -> dict:
                nonlocal runner_called
                runner_called = True
                return _mock_runner_ok(_td)

            # 1) Clean-looking Lean tamper -> hash mismatch caught before Lean runs
            (bundle / "ThinCoordInterpose.lean").write_text(
                (HERE / "ThinCoordInterpose.lean").read_text(encoding="utf-8") + "\ndef extra_tamper : Nat := 0\n",
                encoding="utf-8",
            )
            self._need_err(v.verify_certificate_file, "LEAN_HASH_MISMATCH", cert_path, bundle, live_lean=True, lean_runner=_spy_runner)
            self.assertFalse(runner_called)
            # 2) Banned #eval tamper -> static audit catches FORBIDDEN_LEAN_TOKEN before Lean runs
            (bundle / "ThinCoordInterpose.lean").write_text(
                (HERE / "ThinCoordInterpose.lean").read_text(encoding="utf-8") + '\n#eval IO.println "pwn"\n',
                encoding="utf-8",
            )
            self._need_err(v.verify_certificate_file, "FORBIDDEN_LEAN_TOKEN", cert_path, bundle, live_lean=True, lean_runner=_spy_runner)
            self.assertFalse(runner_called)
            shutil.copyfile(HERE / "ThinCoordInterpose.lean", bundle / "ThinCoordInterpose.lean")

            # [MED-4] Tampered python_source_sha256 -> PYTHON_HASH_MISMATCH
            t_py = json.loads(json.dumps(cert))
            t_py["python_source_sha256"]["evidence/track-s166-aletheia-cs27-cs29-hardening/verify_s166_cs27_cs29.py"] = "0" * 64
            u_py = {k: t_py[k] for k in t_py if k != "payload_sha256"}
            t_py["payload_sha256"] = v.hashlib.sha256(v._canon_bytes(u_py)).hexdigest()
            p_tpy = root / "py_hash.json"
            p_tpy.write_bytes(v._canon_bytes(t_py))
            self._need_err(v.verify_certificate_file, "PYTHON_HASH_MISMATCH", p_tpy, bundle)

            static_cert = v.build_certificate(bundle, live_lean=False)
            p_st = root / "static_cert.json"
            p_st.write_bytes(v._canon_bytes(static_cert))
            st_chk = v.verify_certificate_file(p_st, bundle, live_lean=False)
            self.assertTrue(st_chk["passed"])
            self.assertEqual(st_chk["lean_static_status"], "STATIC_PASS")
            self.assertEqual(st_chk["lean_live_mode"], "STATIC_ONLY")
            self.assertIs(st_chk["live_lean_checked"], False)
            self.assertEqual(st_chk["axioms_verified_count"], 0)
            live_chk = v.verify_certificate_file(p_st, bundle, live_lean=True, lean_runner=_mock_runner_ok)
            self.assertTrue(live_chk["passed"])
            self.assertEqual(live_chk["lean_static_status"], "STATIC_PASS")
            self.assertEqual(live_chk["lean_live_mode"], "LIVE_LEAN_4_36_0_PASS")
            self.assertIs(live_chk["live_lean_checked"], True)
            self.assertEqual(live_chk["axioms_verified_count"], len(v.LEAN_THEOREMS))

            p_nonl = root / "no_nl.json"
            p_nonl.write_bytes(v._canon_bytes(cert).rstrip(b"\n"))
            self._need_err(v.verify_certificate_file, "MISSING_TRAILING_NEWLINE", p_nonl, bundle)

            # Delta-5/Delta-6: Synthetic aletheia package stub NEVER hashes/executes aletheia/__init__.py or __pycache__/*.pyc,
            # strictly pre-hashes owned modules, and runs unconditionally even in evidence/-only mode ([LOW-3]).
            track_root = HERE.parent.parent
            repo_stage = root / "repo_stage"
            ev_stage = repo_stage / "evidence" / "track-s166-aletheia-cs27-cs29-hardening"
            al_stage = repo_stage / "aletheia"
            ts_stage = repo_stage / "tests"
            ev_stage.mkdir(parents=True)
            al_stage.mkdir()
            ts_stage.mkdir()
            for fname in v.LEAN_FILES:
                shutil.copyfile(HERE / fname, ev_stage / fname)
            for rel in v.EVIDENCE_PY_FILES:
                fn = Path(rel).name
                shutil.copyfile(HERE / fn, ev_stage / fn)
            if (track_root / "aletheia" / "lean_audit_hardening.py").exists():
                for rel in v.CORE_PY_FILES:
                    shutil.copyfile(track_root / rel, repo_stage / rel)
            else:
                for rel in v.CORE_PY_FILES:
                    if rel == "aletheia/lean_audit_hardening.py":
                        (repo_stage / rel).write_text(
                            'import json\ndef main(argv=None):\n    print(json.dumps({"passed": True, "checks_passed": 1}, sort_keys=True))\n    return 0\n',
                            encoding="utf-8",
                        )
                    else:
                        (repo_stage / rel).write_text("# stub\n", encoding="utf-8")
            no_init_cert = v.build_certificate(ev_stage, live_lean=False)
            self.assertNotIn("aletheia/__init__.py", no_init_cert["python_source_sha256"])
            self.assertEqual(len(no_init_cert["python_source_sha256"]), 9)

            marker = root / "init_exec_marker.txt"
            init_p = al_stage / "__init__.py"
            init_p.write_text(
                f'from pathlib import Path\nPath({str(marker)!r}).write_text("pwn", encoding="utf-8")\n',
                encoding="utf-8",
            )
            (al_stage / "unrelated_pr130.py").write_text("raise RuntimeError('must never import')\n", encoding="utf-8")
            staged_cert = v.build_certificate(ev_stage, live_lean=False)
            self.assertEqual(staged_cert["python_source_sha256"], no_init_cert["python_source_sha256"])
            self.assertFalse(marker.exists())
            staged_cert_p = root / "staged_cert.json"
            v._atomic_write_lf(staged_cert_p, v._canon_bytes(staged_cert))
            self.assertTrue(v.verify_certificate_file(staged_cert_p, ev_stage, live_lean=False)["passed"])
            self.assertFalse(marker.exists())

            # [MED-1] Poisoned aletheia/__pycache__/lean_audit_hardening.cpython-*.pyc MUST be ignored completely!
            pyc_marker = root / "pyc_hijack_marker.txt"
            evil_src = root / "evil_lah.py"
            evil_src.write_text(
                f'from pathlib import Path\n'
                f'Path({str(pyc_marker)!r}).write_text("pwn_pyc", encoding="utf-8")\n'
                f'raise RuntimeError("poisoned pyc executed")\n',
                encoding="utf-8",
            )
            target_lah = al_stage / "lean_audit_hardening.py"
            target_st = target_lah.stat()
            (al_stage / "__pycache__").mkdir(exist_ok=True)
            for opt_val in ("", 1):
                pyc_p = Path(importlib.util.cache_from_source(str(target_lah), optimization=opt_val))
                py_compile.compile(str(evil_src), cfile=str(pyc_p), doraise=True, optimize=0 if opt_val == "" else 1)
                pyc_data = bytearray(pyc_p.read_bytes())
                struct.pack_into("<II", pyc_data, 8, int(target_st.st_mtime) & 0xFFFFFFFF, target_st.st_size & 0xFFFFFFFF)
                pyc_p.write_bytes(bytes(pyc_data))
            self.assertTrue(v.verify_certificate_file(staged_cert_p, ev_stage, live_lean=False)["passed"])
            self.assertFalse(pyc_marker.exists())
            shutil.rmtree(al_stage / "__pycache__")

            # Tamper owned module -> MUST fail PYTHON_HASH_MISMATCH WITHOUT executing side-effect!
            orig_lah = target_lah.read_bytes()
            target_lah.write_text(
                f'from pathlib import Path\nPath({str(marker)!r}).write_text("pwn", encoding="utf-8")\n',
                encoding="utf-8",
            )
            self._need_err(v.verify_certificate_file, "PYTHON_HASH_MISMATCH", staged_cert_p, ev_stage, live_lean=False)
            self.assertFalse(marker.exists())
            target_lah.write_bytes(orig_lah)

            # [LOW-1] Missing expected_py_hashes with non-None repo_root MUST fail closed before spawning subprocess (and child also rejects null)
            ok_sub = mock.Mock(returncode=0, stdout=b'{"passed": true, "checks_passed": 1}\n', stderr=b"")
            with mock.patch("subprocess.run", return_value=ok_sub):
                self._need_err(v._verify_exp_q46b_independent, "ALETHEIA_SELF_TEST_FAIL", repo_stage)
            self._need_err(v._verify_exp_q46b_independent, "ALETHEIA_SELF_TEST_FAIL", repo_stage)

            bad_hashes = dict(staged_cert["python_source_sha256"])
            bad_hashes["aletheia/lean_audit_hardening.py"] = "0" * 64
            self._need_err(v._verify_exp_q46b_independent, "ALETHEIA_SELF_TEST_FAIL", repo_stage, expected_py_hashes=bad_hashes)

            # Deleting an evidence script from staged track_dir must fail IO_ERROR (never fall back to HERE)
            (ev_stage / "s166_cs27_cs29_audit.py").unlink()
            self._need_err(v._collect_python_source_hashes, "IO_ERROR", ev_stage)

            # _find_repo_root guards OSError and non-'evidence' parents
            with mock.patch("os.lstat", side_effect=PermissionError("lstat denied")):
                self._need_err(v._find_repo_root, "IO_ERROR", ev_stage)
            not_ev = root / "not_evidence" / "bundle"
            not_ev.mkdir(parents=True)
            (root / "aletheia").mkdir(exist_ok=True)
            (root / "aletheia" / "lean_audit_hardening.py").write_text("", encoding="utf-8")
            self.assertIsNone(v._find_repo_root(not_ev))

    def test_02_independent_mathematical_and_lean_guards(self) -> None:
        # Parameterized crossover, DAG, interpose, transcript, and Lean guards
        self._need_err(v.evaluate_crossover_exact, "BAD_CS29_PARAM", "x", 0, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1)
        self._need_err(v.evaluate_crossover_exact, "BAD_CS29_RATE", "x", 1, 0, 0, 0, 1, 0, 1, 0, 1, 1, 0, 0, 1)
        self._need_err(v.evaluate_crossover_exact, "BAD_CS29_AMP", "x", 1, 0, 0, 1, 1, 0, 1, -1, 1, 1, 0, 0, 1)

        self._need_err(v.check_dag_acyclic, "EMPTY_DAG_NODES", [], [])
        self._need_err(v.check_dag_acyclic, "DUP_DAG_NODE", ["a", "a"], [])
        self._need_err(v.check_dag_acyclic, "DANGLING_EDGE", ["a"], [("a", "b")])
        self._need_err(v.check_dag_acyclic, "DAG_CYCLE_DETECTED", ["a", "b"], [("a", "b"), ("b", "a")])

        rx = re.compile(r"\b(john|ellipsoid|covering|helly|minimax)\b")
        self._need_err(v.check_zero_keyword_cross_pillar, "TARGET_KEYWORD_LEAK", "quantiz", ("quantiz",), rx, 1)
        self._need_err(v.check_zero_keyword_cross_pillar, "CROSS_PILLAR_MISS", "plain", ("quantiz",), rx, 1)
        self.assertEqual(v.check_zero_keyword_cross_pillar("john ellipsoid", ("quantiz",), rx, 2), 2)
        self._need_err(v.measure_synthetic_transcript, "EMPTY_EVENTS", [])
        self.assertEqual(v.measure_synthetic_transcript([{"type": "USER_INPUT", "content": ""}])["inline_tool_ratio_q"], "0/1")
        self.assertEqual(v.measure_synthetic_transcript([{"type": "USER_INPUT"}])["total_bytes"], 0)
        list_tx = v.measure_synthetic_transcript([
            {"type": "GENERIC", "content": [{"type": "tool_result", "content": [{"type": "text", "text": "x" * 2401}]}]},
        ])
        self.assertTrue(list_tx["alert"])
        self.assertEqual(list_tx["inline_tool_bytes"], 2401)
        mixed_tx = v.measure_synthetic_transcript([
            {"type": "user", "content": [{"type": "text", "text": "p" * 500}, {"type": "tool_result", "content": "t" * 40}]},
        ])
        self.assertEqual(mixed_tx["total_bytes"], 540)
        self.assertEqual(mixed_tx["inline_tool_bytes"], 40)
        self.assertEqual(mixed_tx["inline_tool_ratio_q"], "2/27")
        self.assertFalse(mixed_tx["alert"])
        self._need_err(v.measure_synthetic_transcript, "BAD_EVENT_TYPE", ["not_a_dict"])
        self._need_err(v.measure_synthetic_transcript, "BAD_EVENT_TEXT", [{"content": 123}])
        self._need_err(v.measure_synthetic_transcript, "BAD_EVENT_TEXT", [{"content": [123]}])
        self._need_err(v.measure_synthetic_transcript, "BAD_EVENT_TEXT", [{"content": [{"content": 123}]}])
        self._need_err(v.measure_synthetic_transcript, "BAD_EVENT_TEXT", [{"content": [{"content": {"bad": 1}}]}])
        self._need_err(v.measure_synthetic_transcript, "BAD_EVENT_TEXT", [{"content": False}])
        self._need_err(v.measure_synthetic_transcript, "BAD_EVENT_TEXT", [{"thinking": 123}])

        # Direct Law-5, CS-27, and EXP-Q46b self-check guard controls
        self.assertFalse(v._independent_law5_check("CANDIDATE_ONLY", "x = y"))
        self.assertFalse(v._independent_law5_check("EXACT_OPERATOR_TRANSFER", "there is no identity here"))
        self.assertFalse(v._independent_law5_check("EXACT_OPERATOR_TRANSFER", "there is no identity: a = b"))
        self.assertFalse(v._independent_law5_check("EXACT_OPERATOR_TRANSFER", "a = b does not hold"))
        self.assertFalse(v._independent_law5_check("EXACT_OPERATOR_TRANSFER", "refuted: x = y"))
        self.assertTrue(v._independent_law5_check("EXACT_OPERATOR_TRANSFER", "x <= y"))
        with mock.patch.object(v, "check_dag_acyclic", return_value=True):
            self._need_err(v._verify_cs27_independent, "CS27_CYCLE_CHECK_FAILED")
        with mock.patch.object(v, "_independent_law5_check", return_value=False):
            self._need_err(v._verify_cs28_independent, "CS28_LAW5_CHECK_FAILED")
        with mock.patch.object(v, "verify_lean_source_clean", return_value=""):
            self._need_err(v._verify_exp_q46b_independent, "EXP_Q46B_SELF_CHECK_FAIL", None)
        bad_sub = mock.Mock(returncode=1, stdout=b"", stderr=b"fail")
        with mock.patch("subprocess.run", return_value=bad_sub):
            self._need_err(v._verify_exp_q46b_independent, "ALETHEIA_SELF_TEST_FAIL", HERE.parent.parent, expected_py_hashes={})
        bad_json_sub = mock.Mock(returncode=0, stdout=b'{"passed": false}\n', stderr=b"")
        with mock.patch("subprocess.run", return_value=bad_json_sub):
            self._need_err(v._verify_exp_q46b_independent, "ALETHEIA_SELF_TEST_FAIL", HERE.parent.parent, expected_py_hashes={})
        with mock.patch("subprocess.run", side_effect=OSError("boom")):
            self._need_err(v._verify_exp_q46b_independent, "ALETHEIA_SELF_TEST_FAIL", HERE.parent.parent, expected_py_hashes={})

        self._need_err(v.strip_lean_comments_and_strings, "UNTERMINATED_LEAN_LEXEME", "/- open")
        self._need_err(v.strip_lean_comments_and_strings, "UNTERMINATED_LEAN_LEXEME", 's!"open')
        self._need_err(v.strip_lean_comments_and_strings, "UNTERMINATED_LEAN_LEXEME", 's!"{ 1')
        self._need_err(v.strip_lean_comments_and_strings, "UNTERMINATED_LEAN_LEXEME", 'r#"open')
        self._need_err(v.strip_lean_comments_and_strings, "UNTERMINATED_LEAN_LEXEME", "«open")
        self._need_err(v.verify_lean_source_clean, "FORBIDDEN_LEAN_TOKEN", "theorem bad : False := sorryAx _")
        self._need_err(v.verify_lean_source_clean, "NON_INIT_IMPORT", "import Mathlib")
        self._need_err(v.verify_lean_source_clean, "NON_INIT_IMPORT", "public import Mathlib")

        # [HIGH-1] & [MED-1] Interpolated string (incl. whitespace/comments), syntax/macro, #eval, run_cmd, @[extern]
        for bad_interp in (
            'def s : String := s!"{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := s!"{ "-/" }"\n',
            'def m : String := m!"{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := m!"{ "-/" }"\n',
            'def f : String := f!"{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := f!"{ "-/" }"\n',
            'def s : String := s!"{ sorry }"\n',
            'def s : String := s!"a { s!"{ "/-" }" } b"\ntheorem fake : False := sorry\n',
            'def s : String := s! "{ "/-" }"\ntheorem bad : False := sorry\ndef t : String := s! "{ "-/" }"\n',
            'def s : String := s! /- c -/ "{ "/-" }"\ntheorem bad : False := sorry\ndef t : String := s! -- c\n"{ "-/" }"\n',
            'def m : String := m! "{ "/-" }"\ntheorem bad : False := sorry\ndef t : String := m! "{ "-/" }"\n',
            'def f : String := f! "{ "/-" }"\ntheorem bad : False := sorry\ndef t : String := f! "{ "-/" }"\n',
            'syntax "q!" interpolatedStr(term) : term\nmacro_rules | `(q! $s) => `(s! $s)\n',
            '@[\nextern "c_evil"\n]\ndef f : Nat := 0\n',
            '#eval IO.println "x"\n',
            'run_cmd IO.println 1\n',
            'def badPrefix : Bool := !s!"{ "/-" }".isEmpty\ntheorem bad_nh1 : False := sorry\ndef badPrefix2 : Bool := !s!"{ "-/" }".isEmpty\n',
            'def q := custom!"{ "/-" }"\ntheorem bad_custom : False := sorry\ndef q2 := custom!"{ "-/" }"\n',
            'theorem t_stop : False := by stop skip\n',
            'theorem t_stop2 : False := by\n  intro h\n  stop skip\n',
            'theorem t_rs : False := _root_.sorryAx False true\n',
            'theorem t_rgs : False := _root_.«sorryAx» False true\n',
            'theorem t_dn : 1 + 1 = 2 := by decide +native\n',
            'theorem t_dn2 : 1 + 1 = 2 := by decide (config := { native := true })\n',
            'def g1 := «foo»sorry\n',
            'def g2 := foo«sorry»\n',
        ):
            self._need_err(v.verify_lean_source_clean, "FORBIDDEN_LEAN_TOKEN", bad_interp)

        for bad_comp in (
            'import Lean.Exception\ndef t (stx : Lean.Syntax) := throwErrorAt stx "{ "/-" }"\ntheorem bad : False := sorry\ndef t2 (stx : Lean.Syntax) := throwErrorAt stx "{ "-/" }"\n',
            'import Lean.Exception\ndef t (stx : Lean.Syntax) := throwErrorAt (stx) "{ "/-" }"\ntheorem bad : False := sorry\ndef t2 (stx : Lean.Syntax) := throwErrorAt (stx) "{ "-/" }"\n',
            'import Lean.Exception\ndef t (stx : Lean.Syntax) := throwErrorAt /- c -/ stx /- d -/ "{ "/-" }"\ntheorem bad : False := sorry\ndef t2 (stx : Lean.Syntax) := throwErrorAt stx -- c\n"{ "-/" }"\n',
            'import Lean\ndef t := do\n  trace[Elab] "{ "/-" }"\ntheorem bad : False := sorry\ndef t2 := do\n  trace[Elab] "{ "-/" }"\n',
            'import Lean.Exception\ndef t := throwErrorAt (sorry) "{ "/-" }"\n',
        ):
            self._need_err(v.verify_lean_source_clean, "FORBIDDEN_LEAN_TOKEN", bad_comp, require_pure_init=False)

        clean_interp = (
            'def a := s!"{ /- { } -/ "ok" } { { x := 1 }.x }"\n'
            'def b := s!"esc \\" \\{"\n'
            'def c : Char := \'"\'\n'
            'def r := r#"/- sorry"#\n'
            'def «ok_id» := 1\n'
            'def g (x : String) := x\n'
            'def xs! (x : String) := x\n'
            'def d := g!"/-"\n'
            'def y1 := xs! ("{")\n'
            'def y2 := Foo.f ("{")\n'
            'def y3 := throwErrorAt stx ("ok")\n'
            'def y4 := throwErrorAt (stx), ("ok")\n'
            'def foo_throwError (x : String) := x\n'
            'def z1 := foo_throwError "{"\n'
            'def z2 := Foo.throwError "{"\n'
            'def z3 := Foo.throwErrorAt stx "{"\n'
            'def sorry\' : Nat := 0\n'
            '/--/\n-/\n'
            'theorem ok_by : True := by rfl\n'
            'def stop : Nat := 1\n'
            'def useStop : Nat :=\n  stop\n'
            'theorem ok_t : True := trivial\n'
        )
        self.assertIn("ok_id", v.verify_lean_source_clean(clean_interp))

        # Live Lean runner output validation negative controls ([LOW-4] exact 4.36.0 pin)
        ok_out = _mock_runner_ok(HERE)
        self._need_err(v.audit_live_lean_output, "LEAN_VERSION_FAIL", dict(ok_out, version_rc=1))
        self._need_err(v.audit_live_lean_output, "LEAN_VERSION_MISMATCH", dict(ok_out, version_output="Lean 4.0.0"))
        self._need_err(v.audit_live_lean_output, "LEAN_VERSION_MISMATCH", dict(ok_out, version_output="Lean (version 4.36.0-rc1)"))
        self._need_err(v.audit_live_lean_output, "LAKE_BUILD_FAIL", dict(ok_out, build_rc=1))
        self._need_err(v.audit_live_lean_output, "LEAN_AXIOM_RUN_FAIL", dict(ok_out, axiom_rc=1))
        self._need_err(
            v.audit_live_lean_output,
            "FORBIDDEN_LEAN_AXIOM",
            dict(ok_out, axiom_stdout=f"'{v.LEAN_THEOREMS[0]}' depends on axioms: [Classical.choice]\n"),
        )
        self._need_err(v.audit_live_lean_output, "LEAN_AXIOM_AUDIT_INCOMPLETE", dict(ok_out, axiom_stdout=""))

    def test_03_zone_b_io_json_and_cli_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = _stage_bundle(root)

            # CRLF, non-empty manifest, missing theorem in Lean source
            (bundle / "lean-toolchain").write_bytes(b"leanprover/lean4:v4.36.0\r\n")
            self._need_err(v.build_certificate, "CRLF_IN_LEAN_FILE", bundle)
            (bundle / "lean-toolchain").write_bytes(b"leanprover/lean4:v4.36.0\n")

            (bundle / "lake-manifest.json").write_bytes(b'{"packages": []}\r\n')
            self._need_err(v.build_certificate, "CRLF_IN_LEAN_FILE", bundle)
            (bundle / "lake-manifest.json").write_bytes(b'{"packages": ["x"], "lakeDir": ".lake"}\n')
            self._need_err(v.build_certificate, "NONEMPTY_LAKE_MANIFEST", bundle)
            (bundle / "lake-manifest.json").write_bytes(b'{"packages": []}\n')
            self._need_err(v.build_certificate, "NONEMPTY_LAKE_MANIFEST", bundle)
            shutil.copyfile(HERE / "lake-manifest.json", bundle / "lake-manifest.json")

            # [MED-4] Reject extra .lean files (incl. venv/), .lake dir, [[require]] mathlib, bad lean-toolchain, theorem rename
            (bundle / "Evil.lean").write_text("theorem bad : False := sorry\n", encoding="utf-8")
            self._need_err(v.build_certificate, "EXTRA_LEAN_FILE", bundle)
            (bundle / "Evil.lean").unlink()

            (bundle / ".lake").mkdir()
            self._need_err(v.build_certificate, "FORBIDDEN_LAKE_DIR", bundle)
            (bundle / ".lake").rmdir()

            (bundle / "lakefile.toml").write_text(
                'name = "thin_coord_interpose"\ndefaultTargets = ["ThinCoordInterpose"]\n[[require]]\nname = "mathlib"\n',
                encoding="utf-8",
            )
            self._need_err(v.build_certificate, "FORBIDDEN_LAKE_REQUIRE", bundle)
            for bad_lf in (
                "bad = [\n",
                'name = "evil"\ndefaultTargets = ["ThinCoordInterpose"]\n[[lean_lib]]\nname = "ThinCoordInterpose"\n',
                'name = "thin_coord_interpose"\ndefaultTargets = ["Other"]\n[[lean_lib]]\nname = "ThinCoordInterpose"\n',
                'name = "thin_coord_interpose"\ndefaultTargets = ["ThinCoordInterpose"]\nsrcDir = "venv"\n[[lean_lib]]\nname = "ThinCoordInterpose"\n',
                'name = "thin_coord_interpose"\ndefaultTargets = ["ThinCoordInterpose"]\n[[lean_lib]]\nname = "ThinCoordInterpose"\nsrcDir = "venv"\n',
                'name = "thin_coord_interpose"\nversion = 123\ndefaultTargets = ["ThinCoordInterpose"]\n[[lean_lib]]\nname = "ThinCoordInterpose"\n',
                'name = "thin_coord_interpose"\ndefaultTargets = ["ThinCoordInterpose"]\nmoreLeanArgs = ["-Ddebug.byAsSorry=true"]\n[[lean_lib]]\nname = "ThinCoordInterpose"\n',
                'name = "thin_coord_interpose"\ndefaultTargets = ["ThinCoordInterpose"]\nleanOptions = { "debug.byAsSorry" = true }\n[[lean_lib]]\nname = "ThinCoordInterpose"\n',
                'name = "thin_coord_interpose"\ndefaultTargets = ["ThinCoordInterpose"]\nprecompileModules = true\n[[lean_lib]]\nname = "ThinCoordInterpose"\n',
            ):
                (bundle / "lakefile.toml").write_text(bad_lf, encoding="utf-8")
                self._need_err(v.build_certificate, "BAD_LAKEFILE", bundle)
            shutil.copyfile(HERE / "lakefile.toml", bundle / "lakefile.toml")

            (bundle / "lean-toolchain").write_text("leanprover/lean4:v4.0.0\n", encoding="utf-8")
            self._need_err(v.build_certificate, "BAD_LEAN_TOOLCHAIN", bundle)
            shutil.copyfile(HERE / "lean-toolchain", bundle / "lean-toolchain")

            (bundle / "ThinCoordInterpose.lean").write_bytes(b"theorem only_one : True := trivial\n")
            self._need_err(v.build_certificate, "LEAN_NAMESPACE_MISSING", bundle)
            (bundle / "ThinCoordInterpose.lean").write_bytes(b"namespace ThinCoordInterpose\ntheorem only_one : True := trivial\nend ThinCoordInterpose\n")
            self._need_err(v.build_certificate, "LEAN_THEOREM_COUNT_MISMATCH", bundle)

            # [MED-3] 12 renamed theorems -> LEAN_THEOREM_IDENTITY_MISMATCH; missing #print axioms -> LEAN_AXIOM_PRINT_MISSING
            renamed_src = "namespace ThinCoordInterpose\n" + "\n".join(
                f"theorem wrong_{i} : True := trivial" for i in range(len(v.LEAN_THEOREMS))
            ) + "\nend ThinCoordInterpose\n"
            (bundle / "ThinCoordInterpose.lean").write_text(renamed_src, encoding="utf-8")
            self._need_err(v.build_certificate, "LEAN_THEOREM_IDENTITY_MISMATCH", bundle)
            no_print_src = "namespace ThinCoordInterpose\n" + "\n".join(
                f"theorem {t.removeprefix('ThinCoordInterpose.')} : True := trivial" for t in v.LEAN_THEOREMS
            ) + "\nend ThinCoordInterpose\n"
            (bundle / "ThinCoordInterpose.lean").write_text(no_print_src, encoding="utf-8")
            self._need_err(v.build_certificate, "LEAN_AXIOM_PRINT_MISSING", bundle)

            # [HIGH-1 / HIGH-2] Live R5 must-fail on !s!, by stop skip, _root_.sorryAx, _root_.«sorryAx», decide +native, syntax q!, and multiline @[extern]
            for bad_src in (
                'def s : String := s! "{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := s! "{ "-/" }"\n',
                'def badPrefix : Bool := !s!"{ "/-" }".isEmpty\ntheorem bad_nh1 : False := sorry\ndef badPrefix2 : Bool := !s!"{ "-/" }".isEmpty\n',
                "theorem t_stop : False := by stop skip\n",
                "theorem t_rs : False := _root_.sorryAx False true\n",
                "theorem t_rgs : False := _root_.«sorryAx» False true\n",
                "theorem t_dn : 1 + 1 = 2 := by decide +native\n",
                'syntax "q!" interpolatedStr(term) : term\nmacro_rules | `(q! $s) => `(s! $s)\n',
                '@[\nextern "c_evil"\n]\ndef f : Nat := 0\n',
            ):
                (bundle / "ThinCoordInterpose.lean").write_text(bad_src, encoding="utf-8")
                self._need_err(v.build_certificate, "FORBIDDEN_LEAN_TOKEN", bundle)
            bo_i, be_i = io.StringIO(), io.StringIO()
            with redirect_stdout(bo_i), redirect_stderr(be_i):
                self.assertEqual(v.main(["--track-dir", str(bundle)]), 2)

            # [MED-2] Invalid UTF-8 in Lean/toolchain/lakefile & subprocess OSError -> RC=2 VerifyS166Error
            (bundle / "ThinCoordInterpose.lean").write_bytes(b"\xff\xfeinvalid")
            self._need_err(v.build_certificate, "INVALID_UTF8", bundle)
            bo_u, be_u = io.StringIO(), io.StringIO()
            with redirect_stdout(bo_u), redirect_stderr(be_u):
                self.assertEqual(v.main(["--track-dir", str(bundle)]), 2)
            self.assertEqual(json.loads(be_u.getvalue().strip())["code"], "INVALID_UTF8")
            shutil.copyfile(HERE / "ThinCoordInterpose.lean", bundle / "ThinCoordInterpose.lean")

            (bundle / "lakefile.toml").write_bytes(b"\xff\xfe")
            self._need_err(v.build_certificate, "INVALID_UTF8", bundle)
            shutil.copyfile(HERE / "lakefile.toml", bundle / "lakefile.toml")

            self._need_err(v.default_live_lean_runner, "IO_ERROR", root / "missing_bundle")
            with mock.patch("subprocess.run", side_effect=OSError("no lean")):
                self._need_err(v.default_live_lean_runner, "LIVE_LEAN_EXEC_ERROR", bundle)

            # Strict JSON + File IO error codes
            self._need_err(v._read_regular_bytes, "BAD_PATH", "str_not_path", "lbl")
            self._need_err(v._read_regular_bytes, "BAD_PATH", Path("bad\x00path"), "lbl")
            self._need_err(v._read_regular_bytes, "BAD_PATH", Path("."), "lbl")
            self._need_err(v._read_regular_bytes, "IO_ERROR", root / "nope", "lbl")
            d = root / "adir"
            d.mkdir()
            self._need_err(v._read_regular_bytes, "NOT_REGULAR_FILE", d, "lbl")
            f_ok = root / "ok.json"
            ok_raw = b'{"k": 1}\n'
            f_ok.write_bytes(ok_raw)
            self._need_err(v._audit_track_dir_tree, "BAD_PATH", "not_a_path")
            self._need_err(v._audit_track_dir_tree, "BAD_PATH", Path("bad\x00dir"))
            self._need_err(v._audit_track_dir_tree, "BAD_TRACK_DIR", f_ok)
            sym_b = root / "sym_b"
            os.symlink(bundle, sym_b)
            self._need_err(v._audit_track_dir_tree, "BAD_TRACK_DIR", sym_b)
            sym_in_b = bundle / "sym_link"
            os.symlink(HERE / "README.md", sym_in_b)
            self._need_err(v._audit_track_dir_tree, "SYMLINK_IN_BUNDLE", bundle)
            sym_in_b.unlink()
            with mock.patch("os.scandir", side_effect=OSError("perm denied")):
                self._need_err(v._audit_track_dir_tree, "IO_ERROR", bundle)
            self.assertEqual(v._read_regular_bytes(f_ok, "lbl", max_bytes=len(ok_raw)), ok_raw)
            with mock.patch.object(v, "MAX_CERT_BYTES", 2):
                self._need_err(v._read_regular_bytes, "FILE_TOO_LARGE", f_ok, "lbl", max_bytes=2)

            self._need_err(v._load_strict_json_bytes, "BOM_FORBIDDEN", b"\xef\xbb\xbf{}\n", "j")
            self._need_err(v._load_strict_json_bytes, "CRLF_FORBIDDEN", b"{}\r\n", "j")
            self._need_err(v._load_strict_json_bytes, "INVALID_UTF8", b"\xff\n", "j")
            self._need_err(v._load_strict_json_bytes, "EMPTY_JSON", b" \n", "j")
            self._need_err(v._load_strict_json_bytes, "FLOAT_FORBIDDEN", b'{"a":1.5}\n', "j")
            self._need_err(v._load_strict_json_bytes, "MISSING_TRAILING_NEWLINE", b'{"a":1}', "j")
            self._need_err(v._load_strict_json_bytes, "NONFINITE_JSON", b'{"a":NaN}\n', "j")
            self._need_err(v._load_strict_json_bytes, "DUPLICATE_JSON_KEY", b'{"a":1,"a":2}\n', "j")
            self.assertEqual(v._load_strict_json_bytes(('{"a":' + "9" * 512 + "}\n").encode(), "j")["a"], int("9" * 512))
            self._need_err(v._load_strict_json_bytes, "INT_TOO_LONG", ('{"a":' + "9" * 513 + "}\n").encode(), "j")
            self._need_err(v._load_strict_json_bytes, "BAD_JSON", b"{bad\n", "j")
            self._need_err(v._load_strict_json_bytes, "LONE_SURROGATE", b'{"a":"\\ud800"}\n', "j")
            self.assertIsInstance(v._load_strict_json_bytes(('{"a":' * 48 + "1" + "}" * 48 + "\n").encode(), "j"), dict)
            self.assertIsInstance(v._load_strict_json_bytes(('{"a":' + "[" * 47 + "1" + "]" * 47 + "}\n").encode(), "j"), dict)
            self._need_err(v._load_strict_json_bytes, "JSON_DEPTH_EXCEEDED", ('{"a":' + "[" * 48 + "1" + "]" * 48 + "}\n").encode(), "j")
            self._need_err(v._load_strict_json_bytes, "JSON_DEPTH_EXCEEDED", ("[" * 49 + "1" + "]" * 49 + "\n").encode(), "j")
            self._need_err(v._load_strict_json_bytes, "JSON_DEPTH_EXCEEDED", ('{"a":' * 49 + "1" + "}" * 49 + "\n").encode(), "j")
            self._need_err(v._load_strict_json_bytes, "ROOT_NOT_OBJECT", b"[1]\n", "j")

            self._need_err(v._atomic_write_lf, "BAD_WRITE_PATH", "bad", b"x")
            self._need_err(v._atomic_write_lf, "BAD_WRITE_PATH", Path("."), b"x")
            self._need_err(v._atomic_write_lf, "WRITE_TARGET_NOT_REGULAR", d, b"x")
            self._need_err(v._atomic_write_lf, "WRITE_IO_ERROR", root / "no_dir" / "f.json", b"x")
            with mock.patch("os.write", return_value=0):
                self._need_err(v._atomic_write_lf, "SHORT_WRITE", root / "short.json", b"xyz")
            with mock.patch("os.fsync", side_effect=OSError("disk full")):
                self._need_err(v._atomic_write_lf, "WRITE_IO_ERROR", root / "fsync_fail.json", b"xyz")
            self.assertEqual([p for p in root.iterdir() if p.name.endswith(".tmp")], [])

            # CLI main() write/check/default/error (single-line JSON)
            cert_cli = root / "cli_cert.json"
            bo, be = io.StringIO(), io.StringIO()
            with redirect_stdout(bo), redirect_stderr(be):
                self.assertEqual(v.main(["--track-dir", str(HERE)]), 0)
                self.assertEqual(v.main(["--track-dir", str(HERE), "--write", str(cert_cli)]), 0)
                self.assertEqual(v.main(["--track-dir", str(HERE), "--check", str(cert_cli)]), 0)
                self.assertEqual(v.main(["--track-dir", str(root / "missing")]), 2)
            out_lines = bo.getvalue().strip().splitlines()
            self.assertEqual(len(out_lines), 3)
            for line in out_lines:
                self.assertTrue(json.loads(line)["passed"])


if __name__ == "__main__":
    unittest.main()
