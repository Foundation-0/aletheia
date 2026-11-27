"""
`s168_velocity_bench.py`: Track S168 (EXP-Q56a) Randomized Multi-Trial CPU-Only A/B Harness.

Executes strictly read-only live measurements (CPU-only, `CUDA_VISIBLE_DEVICES=""`) against:
  1. Real Wave-22 track snapshots (`Track S161` & `Track S166`) + 5 synthetic Wave-22 defect fixtures
     reproducing `S161 HIGH-1/MED-3`, `S165 HIGH-1`, and `S167 MED-1/MED-2`,
  2. Multi-trial randomized-order CLI-vs-CLI A/B mutation benchmark (`trials=3`, seeded `random.Random(168)`)
     comparing BOTH iso-worker (`w1 vs w1`, `w8 vs w8`) and end-to-end (`base w1 vs fast w8`) across:
       - Baseline `aletheia mutate --max-mutants 0` CLI (`workers=1` and `workers=8`, Pass 1 + Pass 2 `--guards _require`)
       - `fast_mutate.py` CLI (`workers=1` and `workers=8`, `--failfast` + lossless Pass-2 dedup,
         staged from a genuine `chmod -R a-w` RO copy into private `0o700` writable slots)
     on `Track S166` (`aletheia/portfolio_dag.py`), persisting exact per-mutant status hashes and
     both mutant-only and control-inclusive subprocess counts,
  3. Live mixed killed/survived + non-redundant Pass-2 `--guards` parity check comparing
     baseline `aletheia mutate` CLI vs `fast_mutate.run_dual_fast_mutation` (for full JSON
     report capture when survivors exist) on a target with both KILLED and SURVIVED
     mutants and strictly new Pass-2 sites (refuting trivial all-KILLED engines).

Writes pure-integer / pure-Q `s168_ab_results.json` atomically via `trust_core`, embedding
exact SHA-256 digests of this script, all 3 core engines (`trust_core.py`, `preflight.py`,
`fast_mutate.py`), and the benchmark target script.

Stdlib-only, zero bare asserts, zero floats on trust paths, 3x -I bit-identical.
"""
from __future__ import annotations

from fractions import Fraction
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Sequence

_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

from preflight import run_preflight  # noqa: E402
from trust_core import (  # noqa: E402
    atomic_write_json_nofollow,
    make_strict_parser,
    require_tc,
    run_fail_closed_cli,
    sha256_bytes,
    strict_read_bytes_nofollow,
)

__all__ = [
    "DEFAULT_TRIALS",
    "BENCH_RNG_SEED",
    "ENGINE_FILES",
    "median_int",
    "run_benchmark",
    "build_parser",
    "main",
]

DEFAULT_TRIALS = 3
BENCH_RNG_SEED = 168
ENGINE_FILES: tuple[str, ...] = ("trust_core.py", "preflight.py", "fast_mutate.py")

_EXP_ROOT = _SELF_DIR.parent
_S161_DIR = _EXP_ROOT / "track-s161-z123-affine-zpoly-disproof"
_S166_DIR = _EXP_ROOT / "track-s166-aletheia-cs27-cs29-hardening"
_ALETHEIA_REPO = _EXP_ROOT / "publish" / "aletheia-context-lifecycle"
_FAST_MUTATE_SCRIPT = _SELF_DIR / "fast_mutate.py"


def median_int(values: Sequence[int]) -> int:
    """Exact integer median (upper-middle element at index len // 2 on even length, exact middle on odd length)."""
    require_tc(len(values) > 0, "EMPTY_TRIAL_SERIES", "trial timing series must be non-empty")
    ordered = sorted(int(v) for v in values)
    return ordered[len(ordered) // 2]


def _status_tuples_sha256(tuples: Sequence[tuple[Any, ...]]) -> str:
    raw = json.dumps([list(t) for t in tuples], separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return sha256_bytes(raw)


def _clean_sub_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CUDA_VISIBLE_DEVICES"] = ""
    return env


def _build_synthetic_defect_fixtures(tmp_root: Path) -> list[dict[str, Any]]:
    """Build 5 isolated synthetic fixtures reproducing real Wave-22 audit failures and run preflight."""
    cases: list[tuple[str, str, str]] = []

    # 1. S161 HIGH-1: Wrong 10^k exponent in prose vs certificate.json (10^67 vs actual 10^64)
    d1 = tmp_root / "fix_s161_high1"
    d1.mkdir()
    (d1 / "demo_certificate.json").write_text(
        json.dumps({"z2_sq_minus_z1_z3": -30629060076556831072416516750219744007195842510749495518880944028}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (d1 / "README.md").write_text(
        "# Demo\n\n| Case | Defect |\n|---|---|\n| witness | `−3.062906… × 10^67` |\n",
        encoding="utf-8",
        newline="\n",
    )
    cases.append(("S161_HIGH1_SCI_EXP", os.fspath(d1), "SCI_NOTATION_MISMATCH"))

    # 2. S161 MED-3: Ghost Lean theorem citations absent from *.lean
    d2 = tmp_root / "fix_s161_med3"
    d2.mkdir()
    (d2 / "Demo.lean").write_text(
        "theorem f625_closed_form_good_set_valid : 1 = 1 := by rfl\n",
        encoding="utf-8",
        newline="\n",
    )
    (d2 / "REPORT.md").write_text(
        "# Report\n\n## Lean Formalization\n\nProves `goodSetP_all_pairs_valid` and `evalP_pos_of_allPos` in `Demo.lean`.\n",
        encoding="utf-8",
        newline="\n",
    )
    cases.append(("S161_MED3_GHOST_THEOREM", os.fspath(d2), "GHOST_LEAN_THEOREM"))

    # 3. S165 HIGH-1: Certificate verdict FALSIFIED while sibling *_gate_pass is True + dropped gate var in AST
    d3 = tmp_root / "fix_s165_high1"
    d3.mkdir()
    (d3 / "demo_certificate.json").write_text(
        json.dumps(
            {
                "kill_gate_1": {
                    "b1c_hmse_gate_pass": False,
                    "b1b_vs_a2_ppl_gate_pass": True,
                    "kg1_john_b1_verdict": "FALSIFIED",
                }
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (d3 / "oracle_demo.py").write_text(
        "def eval_kg1(a, b, c):\n"
        "    b1c_hmse_pass = a > 0\n"
        "    b1b_ppl_pass = b > 0\n"
        "    b1c_ppl_pass = c > 0\n"
        "    if b1c_hmse_pass or b1c_ppl_pass:\n"
        "        return 'CONFIRMED'\n"
        "    return 'FALSIFIED'\n",
        encoding="utf-8",
        newline="\n",
    )
    cases.append(("S165_HIGH1_VERDICT_DRIFT", os.fspath(d3), "CERT_VERDICT_CONTRADICTION"))

    # 4. S167 MED-1: results.json strictly older than bench.py
    d4 = tmp_root / "fix_s167_med1"
    d4.mkdir()
    res4 = d4 / "demo_empirical_results.json"
    bench4 = d4 / "demo_live_bench.py"
    res4.write_text('{"ok": true}\n', encoding="utf-8", newline="\n")
    bench4.write_text("def run():\n    return True\n", encoding="utf-8", newline="\n")
    os.utime(res4, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    os.utime(bench4, ns=(1_700_000_500_000_000_000, 1_700_000_500_000_000_000))
    cases.append(("S167_MED1_STALE_RESULTS", os.fspath(d4), "STALE_RESULTS_JSON"))

    # 5. S167 MED-2: results.json never read/hashed on disk by verifier
    d5 = tmp_root / "fix_s167_med2"
    d5.mkdir()
    res5 = d5 / "demo_empirical_results.json"
    ver5 = d5 / "verify_demo.py"
    res5.write_text('{"ok": true}\n', encoding="utf-8", newline="\n")
    ver5.write_text(
        "PIN_SHA = '0' * 64\n"
        "def verify_receipt(rec):\n"
        "    return rec.get('empirical_results_sha256') == PIN_SHA\n",
        encoding="utf-8",
        newline="\n",
    )
    cases.append(("S167_MED2_UNHASHED_RESULTS", os.fspath(d5), "UNHASHED_RESULTS_JSON"))

    out: list[dict[str, Any]] = []
    for name, fdir, expected_code in cases:
        pf = run_preflight(fdir)
        codes = sorted({f["code"] for f in pf["findings"]})
        caught = (not pf["passed"]) and (expected_code in codes)
        require_tc(caught, "FIXTURE_NOT_CAUGHT", f"{name} failed to catch {expected_code}: {codes}")
        out.append({
            "fixture": name,
            "expected_code": expected_code,
            "caught": caught,
            "codes_detected": codes,
            "elapsed_ms": pf["elapsed_ms"],
        })
    return out


def _run_baseline_aletheia_cli_dual(
    work_root: Path,
    script_rel: str,
    test_cmd: str,
    guard_name: str,
    *,
    workers: int,
    allow_survivors: bool = False,
) -> dict[str, Any]:
    """Run baseline `aletheia mutate --max-mutants 0` CLI Pass 1 + Pass 2 at `workers`."""
    env = _clean_sub_env()
    boot = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from aletheia.cli import main; raise SystemExit(main(sys.argv[2:]))"
    )
    p1_cmd = [
        sys.executable, "-I", "-B", "-c", boot, os.fspath(_ALETHEIA_REPO),
        "mutate",
        os.fspath(work_root / script_rel),
        "--work-root", os.fspath(work_root),
        "--add-cwd",
        "--test-cmd", test_cmd,
        "--max-mutants", "0",
        "--workers", str(workers),
        "--json",
    ]
    p2_cmd = [
        sys.executable, "-I", "-B", "-c", boot, os.fspath(_ALETHEIA_REPO),
        "mutate",
        os.fspath(work_root / script_rel),
        "--work-root", os.fspath(work_root),
        "--add-cwd",
        "--test-cmd", test_cmd,
        "--guards", guard_name,
        "--max-mutants", "0",
        "--workers", str(workers),
        "--json",
    ]
    t0_ns = time.monotonic_ns()
    proc1 = subprocess.run(p1_cmd, env=env, capture_output=True, timeout=300, check=False)
    ok_rcs = (0, 1, 2) if allow_survivors else (0,)
    require_tc(
        proc1.returncode in ok_rcs,
        "BASELINE_P1_FAILED",
        f"rc={proc1.returncode}: {(proc1.stdout + proc1.stderr).decode('utf-8', errors='replace')[-400:]}",
    )
    proc2 = subprocess.run(p2_cmd, env=env, capture_output=True, timeout=300, check=False)
    require_tc(
        proc2.returncode in ok_rcs,
        "BASELINE_P2_FAILED",
        f"rc={proc2.returncode}: {(proc2.stdout + proc2.stderr).decode('utf-8', errors='replace')[-400:]}",
    )
    elapsed_ms = (time.monotonic_ns() - t0_ns) // 1_000_000

    j1 = json.loads(proc1.stdout.decode("utf-8"))
    j2 = json.loads(proc2.stdout.decode("utf-8"))
    p1_stat = [(r["line"], r["kind"], r["original"], r["mutated"], r["status"]) for r in j1["results"]]
    p2_stat = [(r["line"], r["kind"], r["original"], r["mutated"], r["status"]) for r in j2["results"]]
    mutant_evals = int(j1["total_mutants"] + j2["total_mutants"])
    control_evals = (2 if j1.get("null_mutant") == "passed" else 1) + (2 if j2.get("null_mutant") == "passed" else 1)
    return {
        "elapsed_ms": max(1, int(elapsed_ms)),
        "workers": workers,
        "cli_entrypoint": True,
        "pass1_total": int(j1["total_mutants"]),
        "pass1_killed": int(j1["killed"]),
        "pass1_survived": int(j1["survived"]),
        "pass2_total": int(j2["total_mutants"]),
        "pass2_killed": int(j2["killed"]),
        "pass2_survived": int(j2["survived"]),
        "mutant_subprocess_evals": mutant_evals,
        "control_subprocess_evals": control_evals,
        "total_subprocess_evals": mutant_evals + control_evals,
        "pass1_statuses": p1_stat,
        "pass2_statuses": p2_stat,
    }


def _run_fast_mutate_cli_dual(
    work_root: Path,
    script_rel: str,
    test_cmd: str,
    guard_name: str,
    *,
    workers: int,
    allow_survivors: bool = False,
) -> dict[str, Any]:
    """Run `fast_mutate.py` CLI subprocess (Pass 1 + deduped Pass 2) at `workers` for apples-to-apples timing."""
    env = _clean_sub_env()
    if allow_survivors:
        runner_code = (
            "import json, sys; sys.path.insert(0, sys.argv[1]); "
            "from fast_mutate import run_dual_fast_mutation; "
            "res = run_dual_fast_mutation(sys.argv[2], sys.argv[3], pass2_guards=[sys.argv[4]], "
            "work_root=sys.argv[5], max_mutants=0, add_cwd=True, workers=int(sys.argv[6]), failfast=True); "
            "sys.stdout.write(json.dumps(res, sort_keys=True, separators=(',', ':')) + '\\n')"
        )
        cmd = [
            sys.executable, "-I", "-B", "-c", runner_code,
            os.fspath(_SELF_DIR),
            os.fspath(work_root / script_rel),
            test_cmd,
            guard_name,
            os.fspath(work_root),
            str(workers),
        ]
    else:
        cmd = [
            sys.executable, "-I", "-B", os.fspath(_FAST_MUTATE_SCRIPT),
            os.fspath(work_root / script_rel),
            "--work-root", os.fspath(work_root),
            "--add-cwd",
            "--test-cmd", test_cmd,
            "--guards", guard_name,
            "--max-mutants", "0",
            "--workers", str(workers),
            "--json",
        ]
    t0_ns = time.monotonic_ns()
    proc = subprocess.run(cmd, env=env, capture_output=True, timeout=300, check=False)
    elapsed_ms = (time.monotonic_ns() - t0_ns) // 1_000_000
    require_tc(
        proc.returncode == 0,
        "FAST_MUTATE_CLI_FAILED",
        f"rc={proc.returncode}: {(proc.stdout + proc.stderr).decode('utf-8', errors='replace')[-400:]}",
    )
    res = json.loads(proc.stdout.decode("utf-8"))
    p1_stat = [(r["line"], r["kind"], r["original"], r["mutated"], r["status"]) for r in res["pass1"]["results"]]
    p2_stat = [(r["line"], r["kind"], r["original"], r["mutated"], r["status"]) for r in res["pass2"]["results"]]
    return {
        "elapsed_ms": max(1, int(elapsed_ms)),
        "workers": workers,
        "cli_entrypoint": not allow_survivors,
        "failfast_injected": bool(res["pass1"]["failfast_injected"]),
        "pass1_total": int(res["pass1"]["total_mutants"]),
        "pass1_killed": int(res["pass1"]["killed"]),
        "pass1_survived": int(res["pass1"]["survived"]),
        "pass2_total": int(res["pass2"]["total_mutants"]),
        "pass2_killed": int(res["pass2"]["killed"]),
        "pass2_survived": int(res["pass2"]["survived"]),
        "pass2_dedup_skipped": int(res["pass2_dedup_skipped"]),
        "mutant_subprocess_evals": int(res["mutant_subprocess_evals"]),
        "control_subprocess_evals": int(res["control_subprocess_evals"]),
        "total_subprocess_evals": int(res["total_subprocess_evals"]),
        "pass1_statuses": p1_stat,
        "pass2_statuses": p2_stat,
    }


def _run_mixed_parity_check(tmp_root: Path) -> dict[str, Any]:
    """
    Verify 100% parity on a mixed killed/survived target with a non-redundant Pass-2 `--guards`
    helper, refuting any engine that trivially reports all mutants KILLED.
    """
    mix_dir = tmp_root / "mixed_parity_work"
    mix_dir.mkdir()
    (mix_dir / "mixed_mod.py").write_text(
        "def custom_gate(cond, tag):\n"
        "    a = 1\n"
        "    b = 2\n"
        "    c = a + b\n"
        "    if c > 0:\n"
        "        pass\n"
        "    if not cond:\n"
        "        raise ValueError(tag)\n"
        "def evaluate(x, y):\n"
        "    if x < 0:\n"
        "        return False\n"
        "    if y > 100:\n"
        "        return False\n"
        "    custom_gate(x >= 1, 'x_pos')\n"
        "    custom_gate(y >= 0, 'y_nonneg')\n"
        "    return True\n",
        encoding="utf-8",
        newline="\n",
    )
    (mix_dir / "test_mixed.py").write_text(
        "import unittest\n"
        "import mixed_mod as mm\n"
        "class T(unittest.TestCase):\n"
        "    def test_partial(self):\n"
        "        self.assertTrue(mm.evaluate(5, 10))\n"
        "        self.assertFalse(mm.evaluate(-1, 10))\n"
        "        with self.assertRaises(ValueError):\n"
        "            mm.evaluate(0, 10)\n",
        encoding="utf-8",
        newline="\n",
    )
    script_rel = "mixed_mod.py"
    test_cmd = "python3 -m unittest test_mixed.py"
    guard = "custom_gate"
    base_m = _run_baseline_aletheia_cli_dual(mix_dir, script_rel, test_cmd, guard, workers=1, allow_survivors=True)
    fast_m = _run_fast_mutate_cli_dual(mix_dir, script_rel, test_cmd, guard, workers=2, allow_survivors=True)

    p1_eq = base_m["pass1_statuses"] == fast_m["pass1_statuses"]
    p2_eq = base_m["pass2_statuses"] == fast_m["pass2_statuses"]
    has_mixed_p1 = base_m["pass1_killed"] > 0 and base_m["pass1_survived"] > 0
    has_new_p2 = base_m["pass2_total"] > base_m["pass1_total"]
    has_mixed_p2 = base_m["pass2_killed"] > base_m["pass1_killed"] and base_m["pass2_survived"] > base_m["pass1_survived"]
    require_tc(p1_eq and p2_eq, "MIXED_PARITY_MISMATCH", "fast_mutate diverged from baseline on mixed killed/survived target")
    require_tc(has_mixed_p1 and has_new_p2 and has_mixed_p2, "MIXED_FIXTURE_DEGENERATE", "mixed parity fixture did not exercise both killed & survived across Pass 1 and new Pass 2 sites")
    return {
        "fast_arm_entrypoint": "python_api_allow_survivors",
        "pass1_total": base_m["pass1_total"],
        "pass1_killed": base_m["pass1_killed"],
        "pass1_survived": base_m["pass1_survived"],
        "pass2_total": base_m["pass2_total"],
        "pass2_killed": base_m["pass2_killed"],
        "pass2_survived": base_m["pass2_survived"],
        "pass2_new_sites": base_m["pass2_total"] - base_m["pass1_total"],
        "pass2_dedup_skipped": fast_m["pass2_dedup_skipped"],
        "pass1_mutant_set_sha256": _status_tuples_sha256(base_m["pass1_statuses"]),
        "pass2_mutant_set_sha256": _status_tuples_sha256(base_m["pass2_statuses"]),
        "parity_exact_100pct": True,
    }


def _make_isolated_copy(src: Path, dst: Path, *, read_only: bool) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".lake", ".git"))
    fmode = 0o444 if read_only else 0o644
    dmode = 0o555 if read_only else 0o755
    for root_s, dirs, files in os.walk(dst, topdown=False):
        for fn in files:
            os.chmod(os.path.join(root_s, fn), fmode)
        for dn in dirs:
            os.chmod(os.path.join(root_s, dn), dmode)
    os.chmod(dst, dmode)


def _cleanup_ro_copy(dst: Path) -> None:
    if not dst.exists():
        return
    for root_s, dirs, files in os.walk(dst, topdown=True):
        os.chmod(root_s, 0o700)
        for dn in dirs:
            os.chmod(os.path.join(root_s, dn), 0o700)
        for fn in files:
            os.chmod(os.path.join(root_s, fn), 0o600)
    shutil.rmtree(dst, ignore_errors=True)


def run_benchmark(out_path: Path, *, trials: int = DEFAULT_TRIALS) -> dict[str, Any]:
    require_tc(type(trials) is int and 1 <= trials <= 9, "INVALID_TRIALS", "trials must be int in [1, 9]")
    bench_bytes = strict_read_bytes_nofollow(Path(__file__).resolve())
    bench_sha = sha256_bytes(bench_bytes)
    engine_shas = {
        fname: sha256_bytes(strict_read_bytes_nofollow(_SELF_DIR / fname))
        for fname in ENGINE_FILES
    }

    # 1. Live read-only preflight on clean RO snapshots of real S161 & S166
    s161_ro = Path(tempfile.gettempdir()) / f"s168_pf_s161_{os.getpid()}_{secrets.token_hex(6)}"
    s166_ro = Path(tempfile.gettempdir()) / f"s168_pf_s166_{os.getpid()}_{secrets.token_hex(6)}"
    try:
        _make_isolated_copy(_S161_DIR, s161_ro, read_only=True)
        _make_isolated_copy(_S166_DIR, s166_ro, read_only=True)
        pf_s161 = run_preflight(s161_ro)
        pf_s166 = run_preflight(s166_ro)
    finally:
        _cleanup_ro_copy(s161_ro)
        _cleanup_ro_copy(s166_ro)
    require_tc(pf_s161["passed"] and pf_s161["elapsed_ms"] < 2000, "PREFLIGHT_S161_UNEXPECTED", f"S161 preflight: {pf_s161}")
    require_tc(pf_s166["elapsed_ms"] < 2000, "PREFLIGHT_S166_SLOW", f"S166 preflight slow: {pf_s166['elapsed_ms']}ms")

    # 2. Synthetic Wave-22 defect fixtures + mixed killed/survived non-redundant Pass-2 parity check
    with tempfile.TemporaryDirectory(prefix="s168_pf_fix_") as tmp_s:
        tmp_p = Path(tmp_s)
        fixture_results = _build_synthetic_defect_fixtures(tmp_p)
        mixed_parity = _run_mixed_parity_check(tmp_p)

    # 3. Randomized multi-trial CLI-vs-CLI A/B mutation benchmark on real Track S166 (`aletheia/portfolio_dag.py`)
    base_dir = Path(tempfile.gettempdir()) / f"s168_base_s166_{os.getpid()}_{secrets.token_hex(6)}"
    ro_dir = Path(tempfile.gettempdir()) / f"s168_ro_s166_{os.getpid()}_{secrets.token_hex(6)}"
    script_rel = "aletheia/portfolio_dag.py"
    target_sha = sha256_bytes(strict_read_bytes_nofollow(_S166_DIR / script_rel))
    test_cmd = "python3 -m unittest tests/test_cs27_cs29_hardening_r5.py"
    guard_name = "_require"

    rng = random.Random(BENCH_RNG_SEED)
    arm_names = ["baseline_w1", "fast_w1", "baseline_w8", "fast_w8"]
    trial_orders: list[list[str]] = []
    trial_ms: dict[str, list[int]] = {k: [] for k in arm_names}
    arm_last: dict[str, dict[str, Any]] = {}
    ro_copy_verified = False

    try:
        _make_isolated_copy(_S166_DIR, base_dir, read_only=False)
        _make_isolated_copy(_S166_DIR, ro_dir, read_only=True)
        ro_target_p = ro_dir / script_rel
        ro_copy_verified = ro_target_p.exists() and ((os.lstat(ro_target_p).st_mode & 0o222) == 0)
        for _ in range(trials):
            order = list(arm_names)
            rng.shuffle(order)
            trial_orders.append(order)
            for arm in order:
                if arm == "baseline_w1":
                    res = _run_baseline_aletheia_cli_dual(base_dir, script_rel, test_cmd, guard_name, workers=1)
                elif arm == "baseline_w8":
                    res = _run_baseline_aletheia_cli_dual(base_dir, script_rel, test_cmd, guard_name, workers=8)
                elif arm == "fast_w1":
                    res = _run_fast_mutate_cli_dual(ro_dir, script_rel, test_cmd, guard_name, workers=1)
                else:
                    res = _run_fast_mutate_cli_dual(ro_dir, script_rel, test_cmd, guard_name, workers=8)
                trial_ms[arm].append(res["elapsed_ms"])
                if arm in arm_last:
                    require_tc(
                        res["pass1_statuses"] == arm_last[arm]["pass1_statuses"]
                        and res["pass2_statuses"] == arm_last[arm]["pass2_statuses"],
                        "TRIAL_PARITY_DRIFT",
                        f"mutant statuses drifted across trials for {arm}",
                    )
                arm_last[arm] = res
    finally:
        _cleanup_ro_copy(base_dir)
        _cleanup_ro_copy(ro_dir)

    target_sha_after = sha256_bytes(strict_read_bytes_nofollow(_S166_DIR / script_rel))
    source_track_untouched = (target_sha_after == target_sha)

    base_w1 = arm_last["baseline_w1"]
    base_w8 = arm_last["baseline_w8"]
    fast_w1 = arm_last["fast_w1"]
    fast_w8 = arm_last["fast_w8"]

    parity_w1 = (fast_w1["pass1_statuses"] == base_w1["pass1_statuses"]) and (fast_w1["pass2_statuses"] == base_w1["pass2_statuses"])
    parity_w8 = (fast_w8["pass1_statuses"] == base_w8["pass1_statuses"]) and (fast_w8["pass2_statuses"] == base_w8["pass2_statuses"])
    parity_base = (base_w1["pass1_statuses"] == base_w8["pass1_statuses"]) and (base_w1["pass2_statuses"] == base_w8["pass2_statuses"])
    require_tc(parity_w1 and parity_w8 and parity_base, "MUTATION_PARITY_MISMATCH", "fast_mutate did not match baseline mutant set 100%")

    med_base_w1 = median_int(trial_ms["baseline_w1"])
    med_base_w8 = median_int(trial_ms["baseline_w8"])
    med_fast_w1 = median_int(trial_ms["fast_w1"])
    med_fast_w8 = median_int(trial_ms["fast_w8"])

    speedup_w1_q = Fraction(med_base_w1, med_fast_w1)
    speedup_w8_iso_q = Fraction(med_base_w8, med_fast_w8)
    speedup_w8_e2e_q = Fraction(med_base_w1, med_fast_w8)
    mutant_eval_red_q = Fraction(base_w1["mutant_subprocess_evals"], fast_w1["mutant_subprocess_evals"])
    total_eval_red_q = Fraction(base_w1["total_subprocess_evals"], fast_w1["total_subprocess_evals"])

    p1_sha = _status_tuples_sha256(base_w1["pass1_statuses"])
    p2_sha = _status_tuples_sha256(base_w1["pass2_statuses"])
    cli_both = bool(
        base_w1.get("cli_entrypoint", False)
        and base_w8.get("cli_entrypoint", False)
        and fast_w1.get("cli_entrypoint", False)
        and fast_w8.get("cli_entrypoint", False)
    )
    cpu_only_env = (_clean_sub_env().get("CUDA_VISIBLE_DEVICES") == "")

    payload: dict[str, Any] = {
        "schema": "s168.q56a.velocity_ab_results.v2",
        "bench_script_sha256": bench_sha,
        "engine_source_sha256": engine_shas,
        "cpu_only": cpu_only_env,
        "host_cpu_count": int(os.cpu_count() or 1),
        "preflight_live": {
            "s161_snapshot": {
                "files_scanned": pf_s161["files_scanned"],
                "lean_unique_theorems": pf_s161["lean_unique_theorems"],
                "lean_theorems_indexed": pf_s161["lean_theorems_indexed"],
                "finding_count": pf_s161["finding_count"],
                "passed": pf_s161["passed"],
                "elapsed_ms": pf_s161["elapsed_ms"],
                "under_2000ms": pf_s161["elapsed_ms"] < 2000,
            },
            "s166_snapshot": {
                "files_scanned": pf_s166["files_scanned"],
                "lean_unique_theorems": pf_s166["lean_unique_theorems"],
                "lean_theorems_indexed": pf_s166["lean_theorems_indexed"],
                "finding_count": pf_s166["finding_count"],
                "finding_codes": sorted({f["code"] for f in pf_s166["findings"]}),
                "elapsed_ms": pf_s166["elapsed_ms"],
                "under_2000ms": pf_s166["elapsed_ms"] < 2000,
            },
            "synthetic_fixtures": fixture_results,
            "synthetic_caught_count": sum(1 for r in fixture_results if r["caught"]),
            "synthetic_total_count": len(fixture_results),
            "all_under_2000ms": (
                pf_s161["elapsed_ms"] < 2000
                and pf_s166["elapsed_ms"] < 2000
                and all(r["elapsed_ms"] < 2000 for r in fixture_results)
            ),
        },
        "mixed_parity_check": mixed_parity,
        "mutate_ab_benchmark": {
            "target_track": "track-s166-aletheia-cs27-cs29-hardening",
            "target_script": script_rel,
            "target_script_sha256": target_sha,
            "test_cmd": test_cmd,
            "pass2_guard": guard_name,
            "trials": trials,
            "rng_seed": BENCH_RNG_SEED,
            "trial_arm_orders": trial_orders,
            "cli_entrypoint_both_arms": cli_both,
            "staged_from_chmod_aw_ro_copy": ro_copy_verified,
            "mutated_in_isolated_writable_slots": True,
            "source_track_untouched": source_track_untouched,
            "pass1_mutant_set_sha256": p1_sha,
            "pass2_mutant_set_sha256": p2_sha,
            "baseline_aletheia_w1": {
                "elapsed_ms": med_base_w1,
                "trial_elapsed_ms": trial_ms["baseline_w1"],
                "workers": 1,
                "pass1_total": base_w1["pass1_total"],
                "pass1_killed": base_w1["pass1_killed"],
                "pass2_total": base_w1["pass2_total"],
                "pass2_killed": base_w1["pass2_killed"],
                "mutant_subprocess_evals": base_w1["mutant_subprocess_evals"],
                "control_subprocess_evals": base_w1["control_subprocess_evals"],
                "total_subprocess_evals": base_w1["total_subprocess_evals"],
            },
            "baseline_aletheia_w8": {
                "elapsed_ms": med_base_w8,
                "trial_elapsed_ms": trial_ms["baseline_w8"],
                "workers": 8,
                "pass1_total": base_w8["pass1_total"],
                "pass1_killed": base_w8["pass1_killed"],
                "pass2_total": base_w8["pass2_total"],
                "pass2_killed": base_w8["pass2_killed"],
                "mutant_subprocess_evals": base_w8["mutant_subprocess_evals"],
                "control_subprocess_evals": base_w8["control_subprocess_evals"],
                "total_subprocess_evals": base_w8["total_subprocess_evals"],
            },
            "fast_mutate_w1": {
                "elapsed_ms": med_fast_w1,
                "trial_elapsed_ms": trial_ms["fast_w1"],
                "workers": 1,
                "failfast_injected": fast_w1["failfast_injected"],
                "pass1_total": fast_w1["pass1_total"],
                "pass1_killed": fast_w1["pass1_killed"],
                "pass2_total": fast_w1["pass2_total"],
                "pass2_killed": fast_w1["pass2_killed"],
                "pass2_dedup_skipped": fast_w1["pass2_dedup_skipped"],
                "mutant_subprocess_evals": fast_w1["mutant_subprocess_evals"],
                "control_subprocess_evals": fast_w1["control_subprocess_evals"],
                "total_subprocess_evals": fast_w1["total_subprocess_evals"],
                "bit_identical_mutant_set": parity_w1,
                "speedup_q": str(speedup_w1_q),
                "speedup_milli": int((med_base_w1 * 1000) // med_fast_w1),
            },
            "fast_mutate_w8": {
                "elapsed_ms": med_fast_w8,
                "trial_elapsed_ms": trial_ms["fast_w8"],
                "workers": 8,
                "failfast_injected": fast_w8["failfast_injected"],
                "pass1_total": fast_w8["pass1_total"],
                "pass1_killed": fast_w8["pass1_killed"],
                "pass2_total": fast_w8["pass2_total"],
                "pass2_killed": fast_w8["pass2_killed"],
                "pass2_dedup_skipped": fast_w8["pass2_dedup_skipped"],
                "mutant_subprocess_evals": fast_w8["mutant_subprocess_evals"],
                "control_subprocess_evals": fast_w8["control_subprocess_evals"],
                "total_subprocess_evals": fast_w8["total_subprocess_evals"],
                "bit_identical_mutant_set": parity_w8,
                "speedup_vs_base_w8_q": str(speedup_w8_iso_q),
                "speedup_vs_base_w8_milli": int((med_base_w8 * 1000) // med_fast_w8),
                "speedup_q": str(speedup_w8_e2e_q),
                "speedup_milli": int((med_base_w1 * 1000) // med_fast_w8),
            },
            "mutant_eval_reduction_q": str(mutant_eval_red_q),
            "total_eval_reduction_q": str(total_eval_red_q),
            "parity_exact_100pct": parity_w1 and parity_w8 and parity_base,
        },
    }
    raw = atomic_write_json_nofollow(out_path, payload, allow_float=False)
    return {
        "status": "OK",
        "results_path": os.fspath(out_path),
        "results_sha256": sha256_bytes(raw),
        "bench_script_sha256": bench_sha,
        "speedup_w1_vs_w1_milli": payload["mutate_ab_benchmark"]["fast_mutate_w1"]["speedup_milli"],
        "speedup_w8_vs_w8_milli": payload["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_vs_base_w8_milli"],
        "speedup_w8_vs_base_w1_milli": payload["mutate_ab_benchmark"]["fast_mutate_w8"]["speedup_milli"],
        "parity_exact_100pct": payload["mutate_ab_benchmark"]["parity_exact_100pct"],
    }


def build_parser() -> Any:
    parser = make_strict_parser("s168_velocity_bench", "Track S168 randomized multi-trial CPU-only A/B benchmark")
    parser.add_argument(
        "--out",
        type=Path,
        default=_SELF_DIR / "s168_ab_results.json",
        help="Output JSON path (written atomically with O_NOFOLLOW)",
    )
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS, help="Number of randomized A/B trials (1..9)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_fail_closed_cli(lambda args: run_benchmark(args.out, trials=args.trials), parser_builder=build_parser, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
