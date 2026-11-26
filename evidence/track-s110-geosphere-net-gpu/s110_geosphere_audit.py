#!/usr/bin/env python3
"""Pure-stdlib fail-closed verifier and certificate checker for Track S110 (PREREG-S110 + Amendment 1).

Zero external dependencies (zero torch, zero numpy): executes cleanly under stock /usr/bin/python3
across -I -B, -I -O -B, and -I -B -W error for Foundation-0/aletheia CI `evidence-tracks`.

Recomputes and cryptographically verifies directly from the frozen live RTX 3080 JSON records (R7):
  - Exact SHA-256 bindings of all 9 frozen evidence files (h10a/h10b/microbench/preflight/zone_b/REPORT)
  - Internal payload_sha256 recomputation on h10a, h10b, both microbenches, and cpu_preflight_receipt
  - Clean Zone-B hardware provenance (3/3 clean_hardware_run == True, anomalies == [])
  - Corpus provenance equality across H10a & H10b (train_sha256, eval_sha256, file_overlap_count == 0)
  - All 42/42 runs across 14 arms x 3 seeds [42, 137, 2026], 15M (+/- 0.50%) param parity,
    nan_steps == 0, pre_norm_faithfulness == 1.0, WEIGHTS == 0
  - Independent recomputation of H10a/H10b arm means, SEs, paired z-scores, Holm-Bonferroni
    step-down adjusted p-values, microbench gate status, and literal locked verdicts
    (microbench=PARTIAL, H10a=PARTIAL [Shell1_Cayley2x2 BPB-512 CONFIRMED], H10b=FALSIFIED,
    novelty_tier=N1, n2_claims=0)
  - Fail-closed Zone-B path/symlink/JSON/digest checks (hmac.compare_digest) and canonical byte parity.

Zero bare asserts; strict fail-closed S110AuditError on all malformed, tampered, or missing inputs.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
import stat
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_VERSION = "aletheia.track_s110.geosphere_net.certificate.v1"
TRACK_ID = "track-s110-geosphere-net-gpu"
PREREG_S110_SHA256 = "2e645597e81a330159b2183caf670f685821a9451a37223a782936e88e30d0fe"
PREREG_S110_AMEND1_SHA256 = "a41399fdb888167288a63cefa540778d921574197f721b8d5322bd8825d0928a"
EXPECTED_SEEDS = [42, 137, 2026]
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 64
DEFAULT_CERT_NAME = "s110_geosphere_certificate.json"

REQUIRED_EVIDENCE_FILES = (
    "h10a_gpu_results.json",
    "h10b_gpu_results.json",
    "s110_sm86_microbench.json",
    "s110_sm86_microbench_eager_hillis.json",
    "s110_cpu_preflight_receipt.json",
    "mlos_zone_b_s110_microbench.json",
    "mlos_zone_b_s110_h10a.json",
    "mlos_zone_b_s110_h10b.json",
    "REPORT_S110_GPU_EVAL.md",
)

# Each Zone-B hardware receipt is cryptographically bound to the results file(s) it describes.
RECEIPT_BINDINGS = {
    "mlos_zone_b_s110_microbench.json": ("s110_sm86_microbench.json", "s110_sm86_microbench_eager_hillis.json"),
    "mlos_zone_b_s110_h10a.json": ("h10a_gpu_results.json",),
    "mlos_zone_b_s110_h10b.json": ("h10b_gpu_results.json",),
}

# Amendment 1 sm_86 pre-gate: operators adding > 15% full-model train-step overhead are PRUNED.
PRUNE_STEP_OVERHEAD_PCT = 15.0
# Preregistered Shell-Dynamo earn-keep (PREREG-S110 :40): >= 15% M1-H1 reduction OR >= 5% better
# R_test=6, each at >= 2 SE paired z, against H10a_Baseline_Loop.
EARN_KEEP_M1H1_REDUCTION_PCT = 15.0
EARN_KEEP_R6_REDUCTION_PCT = 5.0
EARN_KEEP_MIN_Z = 2.0

EXPECTED_H10A_ARMS = (
    "H10a_Baseline_Loop",
    "H10a_Shell1_Cayley2x2",
    "H10a_Shell2_BinghamProx",
    "H10a_Shell3_DarcyEMA",
    "H10a_Shell4_ACTPlume_MTP8",
)

EXPECTED_H10B_ARMS = (
    "H10b_Geosphere_Full",
    "H10b_LOSO_NoCayley",
    "H10b_LOSO_NoBingham",
    "H10b_LOSO_NoDarcyEMA",
    "H10b_LOSO_NoACTDraft",
    "N0_nGPT_Loop_15M",
    "N0_Monolithic_Loop_15M",
    "N0_English_CoT_15M",
    "N0_nGPT_Unlooped_15M",
)

CERT_TOP_KEYS = frozenset({"schema", "track_id", "payload_sha256", "certificate_sha256", "payload"})
WEIGHT_EXTS = frozenset({".pt", ".pth", ".bin", ".safetensors", ".ckpt"})


class S110AuditError(ValueError):
    """Typed fail-closed error raised on any integrity, schema, provenance, or parity violation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def require_ok(cond: bool, code: str, msg: str) -> None:
    if not cond:
        raise S110AuditError(code, msg)


def require_hex_sha256(val: Any, label: str) -> str:
    require_ok(type(val) is str, "INVALID_SHA256", f"{label} must be strict str")
    require_ok(len(val) == 64 and all(c in "0123456789abcdef" for c in val), "INVALID_SHA256", f"{label} invalid hex")
    return val


def require_no_symlink_path(raw_path: Any, label: str = "path") -> Path:
    if type(raw_path) is str:
        s = raw_path
    elif type(raw_path) is Path or type(raw_path).__name__ == "PosixPath":
        s = str(raw_path)
    else:
        raise S110AuditError("INVALID_PATH_TYPE", f"{label} must be str or Path")
    require_ok(len(s) > 0 and "\x00" not in s, "INVALID_PATH", f"{label} empty or contains NUL")

    # Resolve lexical segments against real CWD while rejecting any symlink component along the walk.
    p_in = Path(s)
    if p_in.is_absolute():
        parts = p_in.parts
        cur = Path(parts[0])
        rest = parts[1:]
    else:
        cwd = Path(os.getcwd())
        env_pwd = os.environ.get("PWD", "")
        if env_pwd:
            try:
                if os.path.samefile(env_pwd, cwd):
                    p_pwd = Path(env_pwd)
                    acc = Path(p_pwd.parts[0])
                    for comp in p_pwd.parts[1:]:
                        acc = acc / comp
                        if os.path.lexists(acc) and stat.S_ISLNK(os.lstat(acc).st_mode):
                            raise S110AuditError("SYMLINK_ANCESTOR_FORBIDDEN", f"PWD contains symlink: {acc}")
            except OSError:
                pass
        cur = cwd
        rest = p_in.parts

    # Check existing ancestors of cur
    anc = Path(cur.parts[0])
    for comp in cur.parts[1:]:
        anc = anc / comp
        if os.path.lexists(anc) and stat.S_ISLNK(os.lstat(anc).st_mode):
            raise S110AuditError("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink ancestor forbidden: {anc}")

    for comp in rest:
        if comp in ("", "."):
            continue
        cur = cur / comp
        if os.path.lexists(cur):
            st = os.lstat(cur)
            if stat.S_ISLNK(st.st_mode):
                raise S110AuditError("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink forbidden: {cur}")
    return cur


def _read_regular_file_bytes(path: Path, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    checked = require_no_symlink_path(path, path.name)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(checked), flags)
    except OSError as exc:
        raise S110AuditError("FILE_MISSING_OR_UNREADABLE", f"cannot open {checked.name}: {exc}") from exc
    try:
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NON_REGULAR_FILE", f"not a regular file: {checked.name}")
        require_ok(st.st_size <= max_bytes, "FILE_TOO_LARGE", f"{checked.name} exceeds size cap")
        chunks: List[bytes] = []
        total = 0
        while True:
            buf = os.read(fd, 65536)
            if not buf:
                break
            total += len(buf)
            require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{checked.name} exceeds streaming cap")
            chunks.append(buf)
        return b"".join(chunks)
    except OSError as exc:
        raise S110AuditError("FILE_MISSING_OR_UNREADABLE", f"read failed on {checked.name}: {exc}") from exc
    finally:
        os.close(fd)


def _no_dup_object_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise S110AuditError("DUPLICATE_KEY", f"duplicate JSON key: {k!r}")
        out[k] = v
    return out


def _reject_nonfinite(tok: str) -> Any:
    raise S110AuditError("NONFINITE_FORBIDDEN", f"non-finite JSON constant forbidden: {tok!r}")


def validate_json_tree_iterative(obj: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    stack: List[Tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        require_ok(depth <= max_depth, "JSON_DEPTH_EXCEEDED", f"JSON depth > {max_depth}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                require_ok(type(k) is str, "INVALID_JSON_KEY", "dict key must be str")
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is float:
            require_ok(math.isfinite(cur), "NONFINITE_FORBIDDEN", "non-finite float forbidden")
        elif t in (int, bool, str) or cur is None:
            continue
        else:
            raise S110AuditError("FORBIDDEN_JSON_TYPE", f"unsupported JSON type: {t.__name__}")


def parse_strict_json_bytes(raw: bytes, label: str = "json") -> Dict[str, Any]:
    require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"CR/CRLF forbidden in {label}")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise S110AuditError("INVALID_UTF8", f"invalid UTF-8 in {label}: {exc}") from exc
    try:
        obj = json.loads(text, object_pairs_hook=_no_dup_object_pairs, parse_constant=_reject_nonfinite)
    except S110AuditError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S110AuditError("INVALID_JSON", f"malformed JSON in {label}: {exc}") from exc
    require_ok(type(obj) is dict, "NON_OBJECT_ROOT", f"JSON root must be dict in {label}")
    validate_json_tree_iterative(obj)
    return obj


def canonical_json_bytes(obj: Any) -> bytes:
    validate_json_tree_iterative(obj)
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256_canonical(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


# ---------------------------------------------------------------------------
# Pure-Stdlib Statistical Recomputation (Independent R7 Audit)
# ---------------------------------------------------------------------------


def _mean_se(vals: Sequence[float]) -> Tuple[float, float]:
    n = len(vals)
    require_ok(n >= 2, "INSUFFICIENT_SEEDS", f"need >= 2 seeds (got {n})")
    m = sum(vals) / float(n)
    var = sum((x - m) ** 2 for x in vals) / float(n - 1)
    se = math.sqrt(var / float(n)) if var > 0.0 else 0.0
    return m, se


def _paired_z_p(base_vals: Sequence[float], arm_vals: Sequence[float]) -> Dict[str, float]:
    require_ok(len(base_vals) == len(arm_vals) and len(base_vals) >= 2, "PAIRED_LEN_MISMATCH", "paired seed mismatch")
    deltas = [b - a for b, a in zip(base_vals, arm_vals)]
    m, se = _mean_se(deltas)
    z = (m / se) if se > 1e-12 else (10.0 if m > 0 else (-10.0 if m < 0 else 0.0))
    p = min(1.0, max(0.0, 0.5 * math.erfc(z / math.sqrt(2.0))))
    base_m = sum(base_vals) / float(len(base_vals))
    rel_pct = (-100.0 * m / base_m) if abs(base_m) > 1e-12 else 0.0
    return {
        "mean_gain": round(m, 6),
        "se": round(se, 6),
        "z_score": round(z, 4),
        "p_one_sided": round(p, 8),
        "rel_bpb_pct": round(rel_pct, 2),
    }


def _student_t_cdf_df2(t: float) -> float:
    # Exact closed-form CDF of Student-t with df = 2 (the n = 3 paired-seed case used here).
    return 0.5 + t / (2.0 * math.sqrt(t * t + 2.0))


def _paired_t_p(base_vals: Sequence[float], arm_vals: Sequence[float]) -> Dict[str, float]:
    # Conservative small-sample companion to _paired_z_p: same paired deltas, exact t(df = n-1)
    # CDF (closed form for df = 2), one-sided in the gain direction. Reported alongside the
    # normal-z Holm so a CONFIRMED is never locked on the anti-conservative normal p at n = 3.
    require_ok(len(base_vals) == len(arm_vals) and len(base_vals) >= 2, "PAIRED_LEN_MISMATCH", "paired seed mismatch")
    n = len(base_vals)
    deltas = [b - a for b, a in zip(base_vals, arm_vals)]
    m, se = _mean_se(deltas)
    t = (m / se) if se > 1e-12 else (10.0 if m > 0 else (-10.0 if m < 0 else 0.0))
    if n == 3:
        cdf = _student_t_cdf_df2(t)
        p = 1.0 - cdf
    else:
        # Normal fallback for n != 3 (not exercised by the locked 3-seed protocol).
        p = 0.5 * math.erfc(t / math.sqrt(2.0))
    p = min(1.0, max(0.0, p))
    return {
        "mean_gain": round(m, 6),
        "se": round(se, 6),
        "t_stat": round(t, 4),
        "df": n - 1,
        "p_one_sided_t": round(p, 8),
    }


def _holm_bonferroni(p_values: Sequence[float], alpha: float = 0.05) -> Tuple[List[float], List[bool]]:
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda kv: kv[1])
    adj = [0.0] * m
    rej = [False] * m
    run_max = 0.0
    active = True
    for rank, (orig_i, pv) in enumerate(indexed):
        pa = min(1.0, max(run_max, pv * float(m - rank)))
        run_max = pa
        adj[orig_i] = round(pa, 8)
        if active and pa <= alpha:
            rej[orig_i] = True
        else:
            active = False
            rej[orig_i] = False
    return adj, rej


def _verify_embedded_payload_sha(doc: Dict[str, Any], label: str) -> str:
    declared = require_hex_sha256(doc.get("payload_sha256"), f"{label}.payload_sha256")
    copy_no_sha = {k: v for k, v in doc.items() if k != "payload_sha256"}
    # Both s110_train_eval.py (indent=2) and s110_cpu_preflight.py (compact) hash without payload_sha256.
    raw_indented = (json.dumps(copy_no_sha, indent=2, sort_keys=True) + "\n").encode("utf-8")
    raw_compact = (json.dumps(copy_no_sha, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    h_ind = hashlib.sha256(raw_indented).hexdigest()
    h_cmp = hashlib.sha256(raw_compact).hexdigest()
    ok = hmac.compare_digest(declared, h_ind) or hmac.compare_digest(declared, h_cmp)
    require_ok(ok, "EMBEDDED_SHA_MISMATCH", f"internal payload_sha256 mismatch in {label}")
    return declared


def _receipt_self_sha(doc: Dict[str, Any]) -> str:
    # Zone-B receipt self-hash convention: compact sorted JSON of the receipt minus the
    # receipt_sha256 field itself, no trailing newline.
    body = {k: v for k, v in doc.items() if k != "receipt_sha256"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parse_iso_utc(val: Any, label: str) -> datetime:
    require_ok(type(val) is str and val.endswith("Z"), "BAD_TIMESTAMP", f"{label} must be an ISO-8601 Z timestamp")
    try:
        dt = datetime.fromisoformat(val[:-1] + "+00:00")
    except ValueError:
        raise S110AuditError("BAD_TIMESTAMP", f"{label} unparseable: {val!r}")
    require_ok(dt.tzinfo is not None, "BAD_TIMESTAMP", f"{label} missing tz")
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Full R7 Evidence Recomputation & Certificate Construction
# ---------------------------------------------------------------------------


def build_certificate(evidence_dir: Path) -> Dict[str, Any]:
    """Independently recompute and certify all Track S110 metrics directly from raw evidence files."""
    try:
        return _build_certificate_impl(evidence_dir)
    except S110AuditError:
        raise
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise S110AuditError("MALFORMED_EVIDENCE_SCHEMA", f"malformed evidence structure: {exc}") from exc


def _build_certificate_impl(evidence_dir: Path) -> Dict[str, Any]:
    edir = require_no_symlink_path(evidence_dir, "evidence_dir")
    require_ok(edir.is_dir(), "MISSING_EVIDENCE_DIR", f"evidence directory missing: {edir}")

    # 1. Zero weight checkpoints anywhere under evidence_dir (WEIGHTS=0)
    weight_files = [
        p.name for p in sorted(edir.rglob("*")) if p.is_file() and p.suffix.lower() in WEIGHT_EXTS
    ]
    require_ok(len(weight_files) == 0, "WEIGHTS_FORBIDDEN", f"weight artifacts forbidden: {weight_files}")

    # 2. Hash all 9 required frozen files & parse JSON artifacts strictly
    file_digests: Dict[str, Dict[str, Any]] = {}
    parsed: Dict[str, Dict[str, Any]] = {}
    for fname in REQUIRED_EVIDENCE_FILES:
        fpath = edir / fname
        raw = _read_regular_file_bytes(fpath)
        file_digests[fname] = {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if fname.endswith(".json"):
            parsed[fname] = parse_strict_json_bytes(raw, fname)

    h10a = parsed["h10a_gpu_results.json"]
    h10b = parsed["h10b_gpu_results.json"]
    mb_cufft = parsed["s110_sm86_microbench.json"]
    mb_hillis = parsed["s110_sm86_microbench_eager_hillis.json"]
    preflight = parsed["s110_cpu_preflight_receipt.json"]

    # 3. Verify preregistration SHA locks & internal payload digests
    for fname in ("h10a_gpu_results.json", "h10b_gpu_results.json", "s110_sm86_microbench.json", "s110_sm86_microbench_eager_hillis.json"):
        doc = parsed[fname]
        require_ok(doc.get("prereg_s110_sha256") == PREREG_S110_SHA256, "PREREG_SHA_MISMATCH", f"{fname} parent prereg SHA mismatch")
        require_ok(doc.get("prereg_s110_amend1_sha256") == PREREG_S110_AMEND1_SHA256, "AMEND1_SHA_MISMATCH", f"{fname} amend1 SHA mismatch")
        require_ok(doc.get("weights_saved") == 0, "WEIGHTS_SAVED_NONZERO", f"{fname} weights_saved != 0")
        _verify_embedded_payload_sha(doc, fname)

    _verify_embedded_payload_sha(preflight, "s110_cpu_preflight_receipt.json")
    require_ok(preflight.get("all_gates_passed") is True, "PREFLIGHT_NOT_PASSED", "CPU preflight all_gates_passed != True")
    require_ok(preflight.get("gates_passed") == 10 and preflight.get("gates_total") == 10, "PREFLIGHT_COUNT_MISMATCH", "CPU preflight gates != 10/10")

    # 4. Verify 3/3 Zone-B hardware receipts: self-hash, results-file binding, and time window
    zone_b_summary: Dict[str, Any] = {}
    receipt_windows: Dict[str, Tuple[datetime, datetime]] = {}
    for zname, bound_files in RECEIPT_BINDINGS.items():
        z = parsed[zname]
        require_ok(z.get("clean_hardware_run") is True, "ZONE_B_UNCLEAN", f"{zname} clean_hardware_run != True")
        anoms = z.get("anomalies")
        require_ok(type(anoms) is list and len(anoms) == 0, "ZONE_B_ANOMALIES", f"{zname} has anomalies: {anoms}")
        # 4a. Recompute the internal receipt_sha256 (canonical compact JSON minus the self field).
        declared_rsha = require_hex_sha256(z.get("receipt_sha256"), f"{zname}.receipt_sha256")
        recomp_rsha = _receipt_self_sha(z)
        require_ok(hmac.compare_digest(declared_rsha, recomp_rsha), "RECEIPT_SHA_MISMATCH", f"{zname} receipt_sha256 mismatch")
        # 4b. Bind the receipt to the sha256 of every results file it describes (fail on swap).
        bnd = z.get("bound_results_sha256")
        require_ok(type(bnd) is dict and set(bnd.keys()) == set(bound_files), "RECEIPT_BINDING_KEYS", f"{zname} bound_results_sha256 keys != {sorted(bound_files)}")
        for bf in bound_files:
            require_hex_sha256(bnd[bf], f"{zname}.bound_results_sha256[{bf}]")
            require_ok(hmac.compare_digest(bnd[bf], file_digests[bf]["sha256"]), "RECEIPT_BINDING_MISMATCH", f"{zname} not bound to {bf} (receipt swap or results edit)")
        # 4c. Execution window: positive duration, sane ordering, duration matches the window.
        ex = z.get("execution")
        require_ok(type(ex) is dict, "RECEIPT_NO_EXECUTION", f"{zname} missing execution block")
        dur = ex.get("duration_ms")
        require_ok(type(dur) is float and dur > 0.0, "RECEIPT_BAD_DURATION", f"{zname} duration_ms={dur!r}")
        started = _parse_iso_utc(ex.get("started_utc"), f"{zname}.started_utc")
        ended = _parse_iso_utc(ex.get("ended_utc"), f"{zname}.ended_utc")
        require_ok(started < ended, "RECEIPT_WINDOW_INVERTED", f"{zname} started_utc >= ended_utc")
        win_ms = (ended - started).total_seconds() * 1000.0
        require_ok(abs(dur - win_ms) <= 1000.0, "RECEIPT_DURATION_WINDOW_MISMATCH", f"{zname} duration_ms={dur} != window {win_ms:.3f} ms")
        gh = z.get("git_head")
        require_ok(gh is None or (type(gh) is str and len(gh) == 64), "RECEIPT_BAD_GIT_HEAD", f"{zname} git_head must be null or a 64-hex sha")
        receipt_windows[zname] = (started, ended)
        zone_b_summary[zname] = {
            "clean_hardware_run": True,
            "anomalies_count": 0,
            "sha256": file_digests[zname]["sha256"],
            "receipt_sha256": declared_rsha,
            "bound_results": sorted(bound_files),
            "window_utc": [ex["started_utc"], ex["ended_utc"]],
            "duration_ms": dur,
        }
    # 4d. Cross-receipt ordering: microbench -> H10a -> H10b must be non-overlapping, in order.
    order = ["mlos_zone_b_s110_microbench.json", "mlos_zone_b_s110_h10a.json", "mlos_zone_b_s110_h10b.json"]
    for prev, nxt in zip(order, order[1:]):
        require_ok(receipt_windows[prev][1] <= receipt_windows[nxt][0], "RECEIPT_WINDOW_OVERLAP", f"{prev} ends after {nxt} starts")

    # 5. Verify disjoint corpus equality across H10a & H10b
    c_a = h10a.get("corpus")
    c_b = h10b.get("corpus")
    require_ok(type(c_a) is dict and type(c_b) is dict, "MISSING_CORPUS_META", "corpus metadata missing")
    require_ok(c_a.get("train_sha256") == c_b.get("train_sha256"), "CORPUS_TRAIN_DRIFT", "H10a vs H10b train_sha256 mismatch")
    require_ok(c_a.get("eval_sha256") == c_b.get("eval_sha256"), "CORPUS_EVAL_DRIFT", "H10a vs H10b eval_sha256 mismatch")
    require_ok(c_a.get("file_overlap_count") == 0 and c_b.get("file_overlap_count") == 0, "CORPUS_OVERLAP", "train/eval file overlap != 0")

    # 6. Independently recompute all 42 runs (15 H10a + 27 H10b) from raw `runs` arrays
    runs_a = h10a.get("runs")
    runs_b = h10b.get("runs")
    require_ok(type(runs_a) is list and len(runs_a) == 15, "H10A_RUN_COUNT", f"expected 15 H10a runs, got {len(runs_a) if type(runs_a) is list else None}")
    require_ok(type(runs_b) is list and len(runs_b) == 27, "H10B_RUN_COUNT", f"expected 27 H10b runs, got {len(runs_b) if type(runs_b) is list else None}")

    all_runs = runs_a + runs_b
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    total_nan_steps = 0
    min_pre_norm_faith = 1.0
    max_param_dev_pct = 0.0

    for r in all_runs:
        require_ok(type(r) is dict, "INVALID_RUN_RECORD", "run record must be dict")
        arm = r.get("arm_name")
        require_ok(type(arm) is str, "INVALID_ARM_NAME", "arm_name must be str")
        nan_s = r.get("nan_steps")
        require_ok(type(nan_s) is int and nan_s == 0, "NAN_STEPS_NONZERO", f"{arm} seed={r.get('seed')} nan_steps={nan_s}")
        total_nan_steps += nan_s
        pn = r.get("pre_norm_counterfactual_patching")
        require_ok(type(pn) is dict, "MISSING_PATCH_AUDIT", f"missing pre-N patching in {arm}")
        faith = float(pn.get("pre_norm_faithfulness_rate", -1.0))
        require_ok(faith == 1.0, "PRE_NORM_FAITHFULNESS_FAIL", f"{arm} pre_norm_faithfulness={faith} != 1.0")
        min_pre_norm_faith = min(min_pre_norm_faith, faith)
        p_tot = int(r["params"]["total_params"])
        p_dev = abs(p_tot - 15_000_000) / 15_000_000.0 * 100.0
        require_ok(p_dev <= 0.50, "PARAM_PARITY_VIOLATION", f"{arm} param dev {p_dev:.4f}% > 0.50%")
        max_param_dev_pct = max(max_param_dev_pct, p_dev)
        by_arm.setdefault(arm, []).append(r)

    expected_all = set(EXPECTED_H10A_ARMS) | set(EXPECTED_H10B_ARMS)
    require_ok(set(by_arm.keys()) == expected_all, "ARM_SET_MISMATCH", f"unexpected arm set: {sorted(by_arm.keys())}")

    arm_metrics: Dict[str, Dict[str, Any]] = {}
    bpb512_by_arm: Dict[str, List[float]] = {}
    r6_by_arm: Dict[str, List[float]] = {}
    m1h1_by_arm: Dict[str, List[float]] = {}
    for arm in list(EXPECTED_H10A_ARMS) + list(EXPECTED_H10B_ARMS):
        rs = sorted(by_arm[arm], key=lambda x: int(x["seed"]))
        seeds = [int(x["seed"]) for x in rs]
        require_ok(seeds == EXPECTED_SEEDS, "SEED_MISMATCH", f"{arm} seeds={seeds} != {EXPECTED_SEEDS}")
        b512 = [float(x["eval_default"]["bpb"]) for x in rs]
        b1024 = [float(x["eval_long_2x"]["bpb"]) for x in rs]
        br6 = [float(x["eval_r6_extrap"]["bpb"]) for x in rs]
        m1h1 = [float(x["ptq_3b"]["m1_h1_loop_drift"]["delta_3_over_delta_1"]) for x in rs]
        kl3 = [float(x["ptq_3b"]["ptq_kl_nats"]) for x in rs]
        bpb512_by_arm[arm] = b512
        r6_by_arm[arm] = br6
        m1h1_by_arm[arm] = m1h1
        m512, se512 = _mean_se(b512)
        m1024, _ = _mean_se(b1024)
        mr6, _ = _mean_se(br6)
        mm1, _ = _mean_se(m1h1)
        mkl, _ = _mean_se(kl3)
        arm_metrics[arm] = {
            "total_params": int(rs[0]["params"]["total_params"]),
            "bpb_512_mean": round(m512, 6),
            "bpb_512_se": round(se512, 6),
            "bpb_1024_mean": round(m1024, 6),
            "ctx_decay_mean": round(m1024 - m512, 6),
            "bpb_r6_mean": round(mr6, 6),
            "m1_h1_mean": round(mm1, 4),
            "ptq_3b_kl_mean": round(mkl, 6),
        }

    # 7. Recompute Stage-1 H10a Holm-Bonferroni & paired verdicts (normal-z AND exact t[df=2])
    h10a_shells = list(EXPECTED_H10A_ARMS[1:])
    h10a_pairs: Dict[str, Dict[str, Any]] = {}
    p_raw_a: List[float] = []
    p_raw_t_a: List[float] = []
    for sh in h10a_shells:
        st = _paired_z_p(bpb512_by_arm["H10a_Baseline_Loop"], bpb512_by_arm[sh])
        st_t = _paired_t_p(bpb512_by_arm["H10a_Baseline_Loop"], bpb512_by_arm[sh])
        st["t_stat"] = st_t["t_stat"]
        st["p_one_sided_t"] = st_t["p_one_sided_t"]
        h10a_pairs[sh] = st
        p_raw_a.append(st["p_one_sided"])
        p_raw_t_a.append(st_t["p_one_sided_t"])
    adj_a, rej_a = _holm_bonferroni(p_raw_a, alpha=0.05)
    adj_t_a, rej_t_a = _holm_bonferroni(p_raw_t_a, alpha=0.05)
    for idx, sh in enumerate(h10a_shells):
        h10a_pairs[sh]["holm_adjusted_p"] = adj_a[idx]
        h10a_pairs[sh]["holm_significant"] = rej_a[idx]
        h10a_pairs[sh]["holm_adjusted_p_t"] = adj_t_a[idx]
        h10a_pairs[sh]["holm_significant_t"] = rej_t_a[idx]

    cay = h10a_pairs["H10a_Shell1_Cayley2x2"]
    h10a_sig_count = sum(1 for x in rej_a if x)
    h10a_sig_count_t = sum(1 for x in rej_t_a if x)

    # 7b. Preregistered Shell-Dynamo earn-keep per shell (PREREG-S110 :40): >= 15% M1-H1
    # reduction OR >= 5% better R_test=6, each at >= 2 SE paired z vs Baseline_Loop. This is
    # the graded Stage-1 gate; BPB-512 Holm above is reported, not the earn-keep.
    base_m1 = m1h1_by_arm["H10a_Baseline_Loop"]
    base_r6 = r6_by_arm["H10a_Baseline_Loop"]
    base_m1_mean = sum(base_m1) / float(len(base_m1))
    base_r6_mean = sum(base_r6) / float(len(base_r6))
    shell_earn_keep: Dict[str, Dict[str, Any]] = {}
    for sh in h10a_shells:
        st_m1 = _paired_z_p(base_m1, m1h1_by_arm[sh])
        st_r6 = _paired_z_p(base_r6, r6_by_arm[sh])
        m1_red_pct = 100.0 * st_m1["mean_gain"] / base_m1_mean if abs(base_m1_mean) > 1e-12 else 0.0
        r6_red_pct = 100.0 * st_r6["mean_gain"] / base_r6_mean if abs(base_r6_mean) > 1e-12 else 0.0
        earn_m1 = (m1_red_pct >= EARN_KEEP_M1H1_REDUCTION_PCT) and (st_m1["z_score"] >= EARN_KEEP_MIN_Z)
        earn_r6 = (r6_red_pct >= EARN_KEEP_R6_REDUCTION_PCT) and (st_r6["z_score"] >= EARN_KEEP_MIN_Z)
        earn = earn_m1 or earn_r6
        shell_earn_keep[sh] = {
            "m1_h1_reduction_pct": round(m1_red_pct, 4),
            "m1_h1_z": st_m1["z_score"],
            "r6_reduction_pct": round(r6_red_pct, 4),
            "r6_z": st_r6["z_score"],
            "earn_keep_m1_h1": earn_m1,
            "earn_keep_r6": earn_r6,
            "verdict": "CONFIRMED" if earn else "FALSIFIED",
        }

    # 7c. Amendment-1 sm_86 pre-gate: shells with > 15% full-model train-step overhead are PRUNED.
    step_bench = mb_cufft["microbench"]["full_model_train_step_bench"]
    shell_step_overhead: Dict[str, float] = {}
    shell_verdicts: Dict[str, str] = {}
    for sh in h10a_shells:
        ovh = float(step_bench[sh]["step_overhead_pct_vs_baseline"])
        shell_step_overhead[sh] = ovh
        pruned = ovh > PRUNE_STEP_OVERHEAD_PCT
        shell_verdicts[sh] = "PRUNED" if pruned else shell_earn_keep[sh]["verdict"]

    # 8. Recompute Stage-2 H10b LOSO Holm-Bonferroni & N0 baseline comparisons (z and t)
    loso_arms = ["H10b_LOSO_NoCayley", "H10b_LOSO_NoBingham", "H10b_LOSO_NoDarcyEMA", "H10b_LOSO_NoACTDraft"]
    loso_pairs: Dict[str, Dict[str, Any]] = {}
    p_raw_b: List[float] = []
    p_raw_t_b: List[float] = []
    for la in loso_arms:
        # Positive gain means removing shell hurt (increased BPB)
        st = _paired_z_p(bpb512_by_arm[la], bpb512_by_arm["H10b_Geosphere_Full"])
        st_t = _paired_t_p(bpb512_by_arm[la], bpb512_by_arm["H10b_Geosphere_Full"])
        st["t_stat"] = st_t["t_stat"]
        st["p_one_sided_t"] = st_t["p_one_sided_t"]
        loso_pairs[la] = st
        p_raw_b.append(st["p_one_sided"])
        p_raw_t_b.append(st_t["p_one_sided_t"])
    adj_b, rej_b = _holm_bonferroni(p_raw_b, alpha=0.05)
    adj_t_b, rej_t_b = _holm_bonferroni(p_raw_t_b, alpha=0.05)
    for idx, la in enumerate(loso_arms):
        loso_pairs[la]["holm_adjusted_p"] = adj_b[idx]
        loso_pairs[la]["holm_significant"] = rej_b[idx]
        loso_pairs[la]["holm_adjusted_p_t"] = adj_t_b[idx]
        loso_pairs[la]["holm_significant_t"] = rej_t_b[idx]
    loso_sig_count = sum(1 for x in rej_b if x)
    loso_sig_count_t = sum(1 for x in rej_t_b if x)

    n0_anchors = ["N0_nGPT_Loop_15M", "N0_Monolithic_Loop_15M", "N0_English_CoT_15M", "N0_nGPT_Unlooped_15M"]
    full_vs_n0: Dict[str, Dict[str, Any]] = {}
    for anc in n0_anchors:
        st = _paired_z_p(bpb512_by_arm[anc], bpb512_by_arm["H10b_Geosphere_Full"])
        st_t = _paired_t_p(bpb512_by_arm[anc], bpb512_by_arm["H10b_Geosphere_Full"])
        st["t_stat"] = st_t["t_stat"]
        st["p_one_sided_t"] = st_t["p_one_sided_t"]
        full_vs_n0[anc] = st
    n0_anchors_beaten = sum(1 for st in full_vs_n0.values() if st["mean_gain"] < 0.0)

    # 8b. Recompute exact Portal-3 Beltrami [C,K]=0 & per-seed Rayleigh ceiling across all 15 Cayley runs
    cay_runs = [r for r in all_runs if r.get("beltrami_commutator_diag") is not None]
    require_ok(len(cay_runs) == 15, "CAYLEY_RUN_COUNT", f"expected 15 Cayley runs, got {len(cay_runs)}")
    max_cay_comm = max(float(r["beltrami_commutator_diag"]["commuting_commutator_frob"]) for r in cay_runs)
    max_cay_m04 = max(float(r["beltrami_commutator_diag"]["commuting_max_moment_drift_m0_m4"]) for r in cay_runs)
    max_cay_rayleigh_abs = max(abs(float(x)) for r in cay_runs for x in r["beltrami_rayleigh_by_pass"])
    require_ok(max_cay_comm == 0.0 and max_cay_m04 <= 1e-6, "BELTRAMI_CONSERVATION_FAIL", f"comm={max_cay_comm}, m04={max_cay_m04}")

    # 9. Independently recompute sm_86 microbench overhead ratios from op_ms / ref_block_ms
    ops_cufft = mb_cufft["microbench"]["operators"]
    ops_hillis = mb_hillis["microbench"]["operators"]
    pass_ops: List[str] = []
    prune_ops: List[str] = []
    for op_name, op_data in sorted(ops_cufft.items()):
        ratio = float(op_data["op_ms"]) / float(op_data["ref_block_ms"])
        recomp_pass = (ratio <= 0.15) and (op_data.get("all_finite") is True)
        recorded_pass = op_data.get("gate_status") == "PASS"
        require_ok(recomp_pass == recorded_pass, "MICROBENCH_ARITH_MISMATCH", f"{op_name} gate_status mismatch with op_ms/ref_block_ms={ratio:.4f}")
        (pass_ops if recomp_pass else prune_ops).append(op_name)

    # 10. Derive every certificate verdict from the preregistered gates (no hardcoded literals,
    # no expected-pattern locks): microbench PASS/PRUNE, per-shell earn-keep + prune flags,
    # Stage-1/Stage-2 outcomes, and the novelty tier all follow from the recomputed numbers.
    h10a_confirmed = any(v == "CONFIRMED" for v in shell_verdicts.values())
    microbench_verdict = "PRUNE" if len(prune_ops) > 0 else "PASS"
    h10a_single_shell_verdict = "CONFIRMED" if h10a_confirmed else "FALSIFIED"
    # BPB-512 headline graded on the conservative exact-t Holm (df = 2), not the normal-z p.
    cay_bpb512_verdict = "CONFIRMED" if cay["holm_significant_t"] else "FALSIFIED"
    h10b_verdict = "CONFIRMED" if loso_sig_count > 0 else "FALSIFIED"
    verdicts = {
        "sm86_microbench": microbench_verdict,
        "H10a_single_shell": h10a_single_shell_verdict,
        "H10a_Shell1_Cayley2x2_bpb512": cay_bpb512_verdict,
        "H10b_coupled_loso": h10b_verdict,
    }
    # Prereg :14: a single matching N0 anchor grades N0; genuine N1/N2 requires coupled
    # multi-shell synergy, i.e. H10b CONFIRMED.
    novelty_tier = "N1" if h10b_verdict == "CONFIRMED" else "N0"

    payload: Dict[str, Any] = {
        "novelty_tier": novelty_tier,
        "n2_claims": 0,
        "weights_count": 0,
        "prereg_s110_sha256": PREREG_S110_SHA256,
        "prereg_s110_amend1_sha256": PREREG_S110_AMEND1_SHA256,
        "cpu_preflight_payload_sha256": preflight["payload_sha256"],
        "cpu_preflight_gates": "10/10",
        "corpus": {
            "tag": c_a["tag"],
            "train_bytes": c_a["train_bytes"],
            "train_sha256": c_a["train_sha256"],
            "eval_bytes": c_a["eval_bytes"],
            "eval_sha256": c_a["eval_sha256"],
            "file_overlap_count": 0,
        },
        "run_counts": {
            "total_runs": len(all_runs),
            "h10a_runs": len(runs_a),
            "h10b_runs": len(runs_b),
            "total_arms": len(arm_metrics),
            "seeds": EXPECTED_SEEDS,
            "total_nan_steps": total_nan_steps,
            "min_pre_norm_faithfulness": min_pre_norm_faith,
            "max_param_dev_pct": round(max_param_dev_pct, 4),
        },
        "zone_b_receipts": zone_b_summary,
        "microbench_sm86": {
            "pass_operators": pass_ops,
            "prune_eager_operators": prune_ops,
            "darcy_hillis_step_overhead_pct": mb_hillis["microbench"]["full_model_train_step_bench"]["H10a_Shell3_DarcyEMA"]["step_overhead_pct_vs_baseline"],
            "darcy_cufft_step_overhead_pct": mb_cufft["microbench"]["full_model_train_step_bench"]["H10a_Shell3_DarcyEMA"]["step_overhead_pct_vs_baseline"],
            "geosphere_full_cufft_peak_vram_mib": mb_cufft["microbench"]["full_model_train_step_bench"]["H10b_Geosphere_Full"]["peak_vram_mib"],
            "darcy_hillis_op_ms": ops_hillis["op3_darcy_diagonal_ema"]["op_ms"],
            "darcy_cufft_op_ms": ops_cufft["op3_darcy_diagonal_ema"]["op_ms"],
        },
        "verdicts": verdicts,
        "shell_earn_keep": shell_earn_keep,
        "shell_step_overhead_pct": shell_step_overhead,
        "shell_verdicts": shell_verdicts,
        "h10a_vs_baseline_bpb": h10a_pairs,
        "h10a_holm_significant_count": h10a_sig_count,
        "h10a_holm_significant_count_t": h10a_sig_count_t,
        "h10b_loso_bpb": loso_pairs,
        "h10b_loso_holm_significant_count": loso_sig_count,
        "h10b_loso_holm_significant_count_t": loso_sig_count_t,
        "h10b_full_vs_n0_bpb": full_vs_n0,
        "h10b_n0_anchors_beaten": n0_anchors_beaten,
        "beltrami_cayley_post_train": {
            "cayley_runs_checked": len(cay_runs),
            "max_commutator_frob": max_cay_comm,
            "max_moment_drift_m0_m4": max_cay_m04,
            "max_per_seed_rayleigh_abs": round(max_cay_rayleigh_abs, 6),
        },
        "arm_metrics": arm_metrics,
        "evidence_files": file_digests,
    }

    p_sha = sha256_canonical(payload)
    outer = {
        "schema": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": p_sha,
        "payload": payload,
    }
    c_sha = sha256_canonical(outer)
    return {
        "schema": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": payload,
    }


def verify_certificate_object(cert: Any, evidence_dir: Path) -> Dict[str, Any]:
    """Fail-closed in-memory validator + full live R7 recomputation against evidence_dir."""
    require_ok(type(cert) is dict, "NON_OBJECT_CERT", "certificate must be strict dict")
    validate_json_tree_iterative(cert)
    require_ok(frozenset(cert.keys()) == CERT_TOP_KEYS, "INVALID_CERT_KEYS", "certificate top-level key mismatch")
    require_ok(type(cert["schema"]) is str and cert["schema"] == SCHEMA_VERSION, "INVALID_SCHEMA", "unexpected schema")
    require_ok(type(cert["track_id"]) is str and cert["track_id"] == TRACK_ID, "INVALID_TRACK_ID", "unexpected track_id")

    p_sha = require_hex_sha256(cert["payload_sha256"], "payload_sha256")
    c_sha = require_hex_sha256(cert["certificate_sha256"], "certificate_sha256")
    payload = cert["payload"]
    require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be strict dict")

    recomp_p_sha = sha256_canonical(payload)
    require_ok(hmac.compare_digest(p_sha, recomp_p_sha), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    outer = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    recomp_c_sha = sha256_canonical(outer)
    require_ok(hmac.compare_digest(c_sha, recomp_c_sha), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    expected = build_certificate(evidence_dir)
    require_ok(
        canonical_json_bytes(cert) == canonical_json_bytes(expected),
        "EVIDENCE_RECOMPUTATION_MISMATCH",
        "certificate diverges from live evidence recomputation",
    )
    return cert


def verify_certificate_file(cert_path: Any, evidence_dir: Optional[Path] = None) -> Dict[str, Any]:
    checked = require_no_symlink_path(cert_path, "cert_path")
    raw = _read_regular_file_bytes(checked)
    cert = parse_strict_json_bytes(raw, checked.name)
    edir = checked.parent if evidence_dir is None else evidence_dir
    verified = verify_certificate_object(cert, edir)
    require_ok(raw == canonical_json_bytes(verified), "NON_CANONICAL_BYTES", "certificate file bytes are not canonical")
    return verified


def write_certificate_file(cert_path: Any, evidence_dir: Optional[Path] = None) -> Dict[str, Any]:
    checked = require_no_symlink_path(cert_path, "write_path")
    parent = checked.parent
    try:
        pst = os.lstat(parent)
    except OSError as exc:
        raise S110AuditError("PARENT_MISSING", f"parent directory missing: {exc}") from exc
    require_ok(not stat.S_ISLNK(pst.st_mode) and stat.S_ISDIR(pst.st_mode), "INVALID_PARENT", "parent must be real directory")
    if os.path.lexists(checked):
        st = os.lstat(checked)
        require_ok(not stat.S_ISLNK(st.st_mode) and stat.S_ISREG(st.st_mode), "INVALID_WRITE_TARGET", "target must be regular file")

    edir = parent if evidence_dir is None else evidence_dir
    cert = build_certificate(edir)
    raw = canonical_json_bytes(cert)
    tmp = parent / f".{checked.name}.tmp.{os.getpid()}"
    try:
        tmp.write_bytes(raw)
        os.replace(tmp, checked)
    except OSError as exc:
        if os.path.lexists(tmp):
            tmp.unlink()
        raise S110AuditError("WRITE_FAILED", f"failed writing certificate: {exc}") from exc
    return cert


def _parse_cli_args(raw_argv: Sequence[str], default_dir: Path) -> Tuple[str, bool, Path, Path]:
    mode: Optional[str] = None
    emit_json = False
    target: Optional[Path] = None
    edir = default_dir
    i = 0
    n = len(raw_argv)
    while i < n:
        tok = raw_argv[i]
        require_ok(type(tok) is str and "\x00" not in tok, "INVALID_ARGV", "invalid CLI token")
        if tok == "--standalone":
            require_ok(mode is None, "CONFLICTING_MODE", "specify only one mode")
            mode = "standalone"
            i += 1
        elif tok == "--json":
            emit_json = True
            i += 1
        elif tok == "--check":
            require_ok(mode is None, "CONFLICTING_MODE", "specify only one mode")
            mode = "check"
            if i + 1 < n and not raw_argv[i + 1].startswith("--"):
                target = Path(raw_argv[i + 1])
                i += 2
            else:
                target = default_dir / DEFAULT_CERT_NAME
                i += 1
        elif tok == "--write":
            require_ok(mode is None, "CONFLICTING_MODE", "specify only one mode")
            mode = "write"
            if i + 1 < n and not raw_argv[i + 1].startswith("--"):
                target = Path(raw_argv[i + 1])
                i += 2
            else:
                target = default_dir / DEFAULT_CERT_NAME
                i += 1
        elif tok == "--evidence-dir":
            require_ok(i + 1 < n, "MISSING_ARG", "--evidence-dir requires a path")
            edir = Path(raw_argv[i + 1])
            i += 2
        else:
            raise S110AuditError("UNKNOWN_FLAG", f"unrecognized argument: {tok!r}")

    if mode is None:
        # Default no-arg execution verifies the committed certificate (supports aletheia --scripts).
        mode = "check"
        target = edir / DEFAULT_CERT_NAME
    if emit_json and mode != "standalone":
        raise S110AuditError("INVALID_FLAG_COMBO", "--json is only valid with --standalone")
    if target is None:
        target = edir / DEFAULT_CERT_NAME
    return mode, emit_json, target, edir


def main(argv: Optional[Sequence[str]] = None) -> int:
    default_dir = Path(__file__).resolve().parent
    try:
        raw_argv = list(sys.argv[1:]) if argv is None else list(argv)
        mode, emit_json, target, edir = _parse_cli_args(raw_argv, default_dir)
        if mode == "standalone":
            cert = build_certificate(edir)
            if emit_json:
                sys.stdout.write(canonical_json_bytes(cert).decode("utf-8"))
            else:
                v = cert["payload"]["verdicts"]
                rc = cert["payload"]["run_counts"]["total_runs"]
                sys.stdout.write(
                    f"PASS {TRACK_ID} runs={rc} microbench={v['sm86_microbench']} "
                    f"H10a={v['H10a_single_shell']} H10b={v['H10b_coupled_loso']} "
                    f"cert_sha256={cert['certificate_sha256']}\n"
                )
            return 0
        if mode == "write":
            cert = write_certificate_file(target, evidence_dir=edir)
            sys.stdout.write(f"WROTE {target.name} cert_sha256={cert['certificate_sha256']}\n")
            return 0
        cert = verify_certificate_file(target, evidence_dir=edir if edir != default_dir else None)
        v = cert["payload"]["verdicts"]
        rc = cert["payload"]["run_counts"]["total_runs"]
        sys.stdout.write(
            f"OK {TRACK_ID} runs={rc} microbench={v['sm86_microbench']} "
            f"H10a={v['H10a_single_shell']} H10b={v['H10b_coupled_loso']} "
            f"cert_sha256={cert['certificate_sha256']}\n"
        )
        return 0
    except S110AuditError as exc:
        sys.stderr.write(f"FAIL {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
