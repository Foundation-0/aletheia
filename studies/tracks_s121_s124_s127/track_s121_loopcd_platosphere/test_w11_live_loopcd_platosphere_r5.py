#!/usr/bin/env python3
"""Pure-stdlib R5 adversarial test suite for `run_w11_live_loopcd_platosphere.py`
(passes stock /usr/bin/python3 -I x3 BOTH in-tree AND in isolated standalone track snapshots)."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import run_w11_live_loopcd_platosphere as w11  # noqa: E402


class _DummyTokenizer:
    def encode(self, text: str, add_special_tokens: bool = True) -> list[int]:
        return list(range(len(text.split()) + (1 if add_special_tokens else 0)))


class TestW11LiveProbesStdlib(unittest.TestCase):
    def test_01_prereg_lock_standalone_snapshot_and_subject_disjoint_suite(self) -> None:
        r1 = w11.run_stdlib_selftest()
        r2 = w11.run_stdlib_selftest()
        self.assertTrue(r1["passed"])
        self.assertEqual(r1["prereg_sha256"], w11.PINNED_PREREG_SHA256)
        self.assertEqual(r1["prereg_source"], "disk_verified")
        self.assertTrue(r1["zone_b_bundle_verified"])
        self.assertEqual(r1["total_unique_facts"], 148)
        self.assertGreaterEqual(r1["total_unique_facts"], 120)
        self.assertTrue(r1["subject_disjoint_pass"])
        self.assertEqual(r1["payload_sha256"], r2["payload_sha256"])

        zb_live = w11.verify_w11_zone_b_bundle(_HERE)
        self.assertTrue(zb_live["passed"])

        # CLI --check-zone-b (text & --json)
        buf_zb = io.StringIO()
        with redirect_stdout(buf_zb):
            self.assertEqual(w11.main(["--check-zone-b"]), 0)
        self.assertIn("PASS S121_ZONE_B", buf_zb.getvalue())
        buf_zb_j = io.StringIO()
        with redirect_stdout(buf_zb_j):
            self.assertEqual(w11.main(["--check-zone-b", "--json"]), 0)
        self.assertTrue(json.loads(buf_zb_j.getvalue())["passed"])

        # R5 Zone-B tamper plants (missing prereg/files, tampered results/receipt/profile/bindings)
        with tempfile.TemporaryDirectory() as td_zb:
            base = Path(td_zb)
            pr_dir = base / "preregistrations"
            tr_dir = base / "track_s121_loopcd_platosphere"
            pr_dir.mkdir()
            tr_dir.mkdir()

            def _reset_zb() -> None:
                shutil.copyfile(_HERE.parent / "preregistrations" / w11.PREREG_FILENAME, pr_dir / w11.PREREG_FILENAME)
                for fn in ("w11_live_loopcd_platosphere_results.json", "mlos_zone_b_w11_loopcd_platosphere.json", "ux582hs-rtx3080-8gb.toml"):
                    shutil.copyfile(_HERE / fn, tr_dir / fn)

            def _resign_rec(obj: dict[str, object]) -> dict[str, object]:
                body = {k: v for k, v in obj.items() if k != "receipt_sha256"}
                out = dict(body)
                out["receipt_sha256"] = hashlib.sha256(
                    json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
                ).hexdigest()
                return out

            _reset_zb()
            self.assertTrue(w11.verify_w11_zone_b_bundle(tr_dir)["passed"])

            (pr_dir / w11.PREREG_FILENAME).unlink()
            with self.assertRaises(w11.Wave11ProbeError) as cm_z1:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_z1.exception.code, "ZONEB_PREREG_MISSING")

            (pr_dir / w11.PREREG_FILENAME).write_text("bad\n", encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_z2:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_z2.exception.code, "PREREG_HASH_MISMATCH")

            for miss_fn in ("w11_live_loopcd_platosphere_results.json", "mlos_zone_b_w11_loopcd_platosphere.json", "ux582hs-rtx3080-8gb.toml"):
                _reset_zb()
                (tr_dir / miss_fn).unlink()
                with self.assertRaises(w11.Wave11ProbeError) as cm_zm:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_zm.exception.code, "ZONEB_FILE_MISSING")

            _reset_zb()
            r_obj = json.loads((tr_dir / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
            r_obj["payload_sha256"] = "short"
            (tr_dir / "w11_live_loopcd_platosphere_results.json").write_text(json.dumps(r_obj), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_rs1:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_rs1.exception.code, "RESULTS_SHA_MISSING")

            _reset_zb()
            r_obj = json.loads((tr_dir / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
            r_obj["payload_sha256"] = "0" * 64
            (tr_dir / "w11_live_loopcd_platosphere_results.json").write_text(json.dumps(r_obj), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_rs2:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_rs2.exception.code, "RESULTS_SHA_MISMATCH")

            _reset_zb()
            r_obj = json.loads((tr_dir / "w11_live_loopcd_platosphere_results.json").read_text(encoding="utf-8"))
            r_obj["prereg_sha256"] = "0" * 64
            r_body = {k: v for k, v in r_obj.items() if k != "payload_sha256"}
            r_obj["payload_sha256"] = hashlib.sha256(w11._canonical_json_bytes(r_body)).hexdigest()
            (tr_dir / "w11_live_loopcd_platosphere_results.json").write_text(json.dumps(r_obj), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_rp:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_rp.exception.code, "RESULTS_PREREG_MISMATCH")

            _reset_zb()
            rec_obj = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
            rec_obj["receipt_sha256"] = 123
            (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(rec_obj), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_rc1:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_rc1.exception.code, "RECEIPT_SHA_MISSING")

            _reset_zb()
            rec_obj = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
            rec_obj["receipt_sha256"] = "0" * 64
            (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(rec_obj), encoding="utf-8")
            with self.assertRaises(w11.Wave11ProbeError) as cm_rc2:
                w11.verify_w11_zone_b_bundle(tr_dir)
            self.assertEqual(cm_rc2.exception.code, "RECEIPT_SHA_MISMATCH")

            for bad_k, bad_v in (
                ("bound_results_file", "other.json"),
                ("bound_results_payload_sha256", "0" * 64),
                ("bound_results_file_sha256", "0" * 64),
                ("bound_prereg_sha256", "0" * 64),
                ("bound_profile_file", "other.toml"),
                ("profile_sha256", "0" * 64),
                ("energy_power_status", "CLAIMED_WATTS"),
            ):
                _reset_zb()
                rec_obj = json.loads((tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").read_text(encoding="utf-8"))
                rec_obj[bad_k] = bad_v
                (tr_dir / "mlos_zone_b_w11_loopcd_platosphere.json").write_text(json.dumps(_resign_rec(rec_obj)), encoding="utf-8")
                with self.assertRaises(w11.Wave11ProbeError) as cm_rb:
                    w11.verify_w11_zone_b_bundle(tr_dir)
                self.assertEqual(cm_rb.exception.code, "RECEIPT_BINDING_MISMATCH")

        # B3: Verify standalone isolated snapshot without sibling notes/ tree STILL passes selftest cleanly!
        with tempfile.TemporaryDirectory() as td:
            snap = Path(td) / "track_snap"
            snap.mkdir()
            shutil.copy(_HERE / "run_w11_live_loopcd_platosphere.py", snap / "run_w11_live_loopcd_platosphere.py")
            proc = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertTrue(out["passed"])
            self.assertEqual(out["prereg_source"], "pinned_standalone")
            self.assertEqual(out["prereg_sha256"], w11.PINNED_PREREG_SHA256)

            # Tampered PREREG file on disk MUST fail closed with PREREG_HASH_MISMATCH!
            notes_dir = Path(td) / "notes" / "portals_wave11_2026_11_25"
            notes_dir.mkdir(parents=True)
            (notes_dir / w11.PREREG_FILENAME).write_text("TAMPERED_PREREG\n", encoding="utf-8")
            proc_bad = subprocess.run(
                [sys.executable, "-I", "-B", str(snap / "run_w11_live_loopcd_platosphere.py"), "--selftest-stdlib", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc_bad.returncode, 0)
            self.assertIn("PREREG_HASH_MISMATCH", proc_bad.stderr)

    def test_02_b1_hardened_answer_matcher_and_all_six_attack_controls(self) -> None:
        # Positive controls
        self.assertTrue(w11._answer_matches(" Berlin, which is...", "Berlin"))
        self.assertTrue(w11._answer_matches(" William Shakespeare.", "William Shakespeare"))
        self.assertTrue(w11._answer_matches(" Shakespeare", "William Shakespeare"))
        self.assertTrue(w11._answer_matches(" Kiev", "Kyiv"))
        self.assertTrue(w11._answer_matches(" He.", "He"))
        self.assertTrue(w11._answer_matches(" As,", "As"))
        self.assertTrue(w11._answer_matches(" I.", "I"))
        self.assertTrue(w11._answer_matches(" South America.", "South America"))
        self.assertTrue(w11._answer_matches(" J. R. R. Tolkien.", "J. R. R. Tolkien"))

        # B1 MUST-FAIL controls: all 6 audit false-accept strings + additional negatives!
        self.assertFalse(w11._answer_matches("H", "He"))
        self.assertFalse(w11._answer_matches("N", "Ne"))
        self.assertFalse(w11._answer_matches("I think so", "I"))
        self.assertFalse(w11._answer_matches("as a result", "As"))
        self.assertFalse(w11._answer_matches("J.K. Rowling", "J. R. R. Tolkien"))
        self.assertFalse(w11._answer_matches("Not Shakespeare", "William Shakespeare"))
        self.assertFalse(w11._answer_matches("North America", "South America"))
        self.assertFalse(w11._answer_matches("South Africa", "Africa"))
        self.assertFalse(w11._answer_matches(" Paris", "Berlin"))
        self.assertFalse(w11._answer_matches("", "Berlin"))
        self.assertFalse(w11._answer_matches("Berlin", ""))

    def test_03_b1_swap_tuples_forbid_same_answer_collisions(self) -> None:
        # Same-continent pair ONLY (Slovenia & Estonia both Europe) -> MUST emit 0 swaps!
        same_ans = [
            ("continent", "Slovenia", "Europe"),
            ("continent", "Estonia", "Europe"),
        ]
        self.assertEqual(w11.make_swap_tuples(same_ans), [])

        # Mixed continent list: every emitted swap MUST have tgt_subj != d_subj AND tgt_ans != d_ans!
        mixed = [
            ("continent", "Slovenia", "Europe"),
            ("continent", "Estonia", "Europe"),
            ("continent", "Bolivia", "South America"),
            ("continent", "Nepal", "Asia"),
        ]
        ans_by_subj = {s: a for _, s, a in mixed}
        swaps = w11.make_swap_tuples(mixed)
        self.assertEqual(len(swaps), 4)
        for _rel, d_s, d_a, t_s in swaps:
            self.assertNotEqual(d_s, t_s)
            self.assertNotEqual(w11._normalize_ans(d_a), w11._normalize_ans(ans_by_subj[t_s]))

        # Verify zero same-answer collisions across all real val & test splits!
        splits = w11.build_subject_disjoint_fact_splits(20261125)
        all_ans = {s: a for _, s, a in w11.RAW_FACTS}
        for sp_name in ("val", "test"):
            sp_swaps = w11.make_swap_tuples(splits[sp_name])
            self.assertGreater(len(sp_swaps), 0)
            for _rel, d_s, d_a, t_s in sp_swaps:
                self.assertNotEqual(d_s, t_s)
                self.assertNotEqual(w11._normalize_ans(d_a), w11._normalize_ans(all_ans[t_s]))

    def test_04_b2_fail_closed_gate_graders_and_refusal_guards(self) -> None:
        # B2: Probe B MUST NEVER emit CONFIRMED when W11-B1 fails (even if diff_sph_frob >= +0.03)!
        v_under = w11.grade_probe_b_verdict(
            w11_b1_pass=False,
            mean_frob=0.2902,
            mean_sph=0.3259,
            mean_rand=0.1027,
            mean_shuf=0.1696,
            tot_dm=118,
            dm_frob_rate=0.0085,
            dm_sph_rate=0.0,
            dm_rand_rate=0.0254,
        )
        self.assertEqual(v_under, "PARTIAL_UNDERPOWERED")
        self.assertNotEqual(v_under, "CONFIRMED")

        # When W11-B1 fails and SphereMap trails by > 2 pp -> FALSIFIED
        v_fail_b = w11.grade_probe_b_verdict(
            w11_b1_pass=False,
            mean_frob=0.20,
            mean_sph=0.15,
            mean_rand=0.10,
            mean_shuf=0.10,
            tot_dm=10,
            dm_frob_rate=0.0,
            dm_sph_rate=0.0,
            dm_rand_rate=0.0,
        )
        self.assertEqual(v_fail_b, "FALSIFIED")

        # Genuine CONFIRMED requires W11-B1 pass AND (+3pp or dark-memory beat over Frob AND rand null)
        v_conf_b = w11.grade_probe_b_verdict(
            w11_b1_pass=True,
            mean_frob=0.40,
            mean_sph=0.45,
            mean_rand=0.02,
            mean_shuf=0.02,
            tot_dm=50,
            dm_frob_rate=0.10,
            dm_sph_rate=0.22,
            dm_rand_rate=0.02,
        )
        self.assertEqual(v_conf_b, "CONFIRMED")

        # Probe A: MUST NOT emit CONFIRMED if W11-A1 failed!
        v_fail_a = w11.grade_probe_a_verdict(
            w11_a1_pass=False,
            l6_gain=0.001,
            l6_2048_gain=0.001,
            l4_gain=-0.20,
            l3_gain=-0.33,
            su2_gain=-0.0001,
            any_bpb_gain=True,
            any_top1_gain=True,
        )
        self.assertEqual(v_fail_a, "FALSIFIED")
        v_conf_a = w11.grade_probe_a_verdict(
            w11_a1_pass=True,
            l6_gain=0.001,
            l6_2048_gain=0.001,
            l4_gain=-0.20,
            l3_gain=-0.33,
            su2_gain=-0.0001,
            any_bpb_gain=True,
            any_top1_gain=True,
        )
        self.assertEqual(v_conf_a, "CONFIRMED")

        # Refusal guards: DUP_SUBJECT, TOO_FEW_FACTS, SUBJ_NOT_IN_PROMPT, BAD_ARGS
        with self.assertRaises(w11.Wave11ProbeError) as cm_dup:
            w11.build_subject_disjoint_fact_splits(facts=[("capital", "Germany", "Berlin"), ("capital", "Germany", "Berlin")])
        self.assertEqual(cm_dup.exception.code, "DUP_SUBJECT")

        with self.assertRaises(w11.Wave11ProbeError) as cm_few:
            w11.build_subject_disjoint_fact_splits(facts=[("capital", f"Country{i}", f"City{i}") for i in range(10)])
        self.assertEqual(cm_few.exception.code, "TOO_FEW_FACTS")

        with self.assertRaises(w11.Wave11ProbeError) as cm_sub:
            w11._locate_subject_last_token(_DummyTokenizer(), "The capital of France is", "Germany")
        self.assertEqual(cm_sub.exception.code, "SUBJ_NOT_IN_PROMPT")

        with self.assertRaises(w11.Wave11ProbeError) as cm_args:
            w11.main(["--run-gpu"])
        self.assertEqual(cm_args.exception.code, "BAD_ARGS")

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = w11.main(["--selftest-stdlib", "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["prereg_sha256"], w11.PINNED_PREREG_SHA256)
        self.assertEqual(len(hashlib.sha256(buf.getvalue().encode("utf-8")).hexdigest()), 64)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if res.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
