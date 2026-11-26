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
        self.assertEqual(r1["total_unique_facts"], 148)
        self.assertGreaterEqual(r1["total_unique_facts"], 120)
        self.assertTrue(r1["subject_disjoint_pass"])
        self.assertEqual(r1["payload_sha256"], r2["payload_sha256"])

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
