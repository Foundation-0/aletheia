#!/usr/bin/env python3
"""
Track S95: Zone-B Hardened & R12 Lean 4.36.0 Certificate Verifier.

Pure Python 3 standard library. Zero floats, zero bare asserts, zero hardcoded host paths.
Provides all 4 independent verification surfaces for Zone-B fuzzing (`82/82`):
  1. CLI (`--check <cert.json> [--json]`)
  2. `verify_certificate_dict(cert, full_replay=True)`  (FR1)
  3. `verify_certificate_dict(cert, full_replay=False)` (FR0)
  4. `secondary_audit_payload(cert_or_payload)`          (SEC — field-complete, zero oracle replay)
Plus `--standalone --json`, `--write <cert.json>`, `--verify-lean <file.lean>`, and
`--verify-artifacts <track_dir>`.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import copy
from decimal import Decimal, ROUND_HALF_UP
import errno
from fractions import Fraction
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import s95_specialist_foundry_oracle as s95  # noqa: E402
from s95_specialist_foundry_oracle import (  # noqa: E402
    ADAPTER_KINDS,
    INKLING2_CONFIG_SHA256,
    LAKEFILE_SHA256,
    LEAN_FILE_SHA256,
    LEAN_THEOREMS,
    MLOS_PROFILE_SHA256,
    MLOS_RECEIPT_FILE_SHA256,
    MLOS_RECEIPT_INNER_SHA256,
    ORACLE_CLASS,
    RESULTS_FILE_SHA256,
    SCHEMA_VERSION,
    S95Error,
    TOOLCHAIN_SHA256,
    TRACK_ID,
    TRACK_S96_CERT_SHA256,
    build_certificate,
    build_payload,
    canonical_json_bytes,
    require_ok,
)

MAX_JSON_BYTES = 1_048_576
MAX_JSON_DEPTH = 64
MAX_INT_DIGITS = 1000
_MAX_INT_BITS = (10 ** MAX_INT_DIGITS - 1).bit_length()
EXPECTED_PAYLOAD_SHA256 = "18fce09c589a915aa04e61c0cfec64600aa57dbf2f7781683d72604f5d5ad7c8"
_HEX_LOWER = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})
_ADAPTER_SET = frozenset(ADAPTER_KINDS)

_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "track_id",
        "oracle_class",
        "pillar1_hardware_and_datasets",
        "pillar2_beyond_lora_showdown",
        "pillar3_law3_routing_and_law4_failures",
        "pillar4_inkling2_transfer",
        "pillar5_lean4_and_novelty",
    }
)
_P1_KEYS = frozenset(
    {
        "base_model_id",
        "base_model_license",
        "gpu_name",
        "results_file_name",
        "results_file_sha256",
        "results_file_bytes",
        "mlos_receipt_file_name",
        "mlos_receipt_file_sha256",
        "mlos_receipt_inner_sha256",
        "mlos_profile_sha256",
        "mlos_clean_hardware_run",
        "mlos_exit_code",
        "mlos_anomaly_count",
        "mlos_duration_ms_x1000",
        "seed",
        "matched_adapter_budget_s",
        "lora_alpha",
        "merged_layers_count",
        "exact_matched_trainable_params",
        "total_params_with_adapter",
        "merged_safetensors_bytes",
        "base_retention_nll_0_x10000",
        "dataset_total_rows",
        "dataset_total_bytes",
        "dataset_under_5mib",
        "datasets",
    }
)
_DS_ROW_KEYS = frozenset({"file", "rows", "bytes", "sha256"})
_P2_KEYS = frozenset(
    {
        "aletheia_scribe_0_5b",
        "aletheia_weaver_0_5b",
        "aletheia_prover_0_5b",
        "beyond_lora_pareto_summary",
    }
)
_NLL_KEYS = frozenset(
    {
        "base_retention_nll_after_x10000",
        "target_eval_nll_after_x10000",
        "delta_forgetting_q",
        "delta_forgetting_dec4",
        "delta_learning_q",
        "delta_learning_dec4",
        "forgetting_learning_ratio_q",
        "forgetting_learning_ratio_dec4",
        "beats_s78_unit_wall",
    }
)
_ARM_COMMON_KEYS = frozenset(
    {
        "trainable_params",
        "peak_vram_mib",
        "train_seconds_x100",
        "ms_per_step_x100",
        "opt_steps",
        "max_merge_diff_x1e6",
        "safetensors_sha256",
    }
) | _NLL_KEYS
_SCRIBE_SP_KEYS = frozenset(
    {"winner_adapter", "winner_safetensors_sha256", "base_target_nll_0_x10000", "base_eval", "arms"}
)
_SCRIBE_BASE_KEYS = frozenset(
    {"total", "strict_json_ok", "exact_all7_ok", "hygiene_tp", "hygiene_fp", "hygiene_fn", "hygiene_tn"}
)
_SCRIBE_ARM_KEYS = _ARM_COMMON_KEYS | _SCRIBE_BASE_KEYS | frozenset(
    {"latency_ms_x100", "tok_per_sec_x100", "exact_all7_rate_q", "exact_all7_rate_dec4", "hygiene_f1_q", "hygiene_f1_dec4"}
)
_WEAVER_SP_KEYS = frozenset(
    {
        "winner_adapter",
        "retention_pareto_adapter",
        "winner_safetensors_sha256",
        "base_target_nll_0_x10000",
        "base_eval",
        "arms",
    }
)
_WEAVER_BASE_KEYS = frozenset(
    {
        "total",
        "strict_json_ok",
        "exact_all5_ok",
        "pathway_class_ok",
        "operator_tag_ok",
        "cs03_tp",
        "cs03_fp",
        "cs03_fn",
        "cs03_tn",
    }
)
_WEAVER_ARM_KEYS = _ARM_COMMON_KEYS | _WEAVER_BASE_KEYS | frozenset(
    {
        "latency_ms_x100",
        "tok_per_sec_x100",
        "exact_all5_rate_q",
        "exact_all5_rate_dec4",
        "pathway_class_rate_q",
        "pathway_class_rate_dec4",
        "cs03_f1_q",
        "cs03_f1_dec4",
    }
)
_PROVER_SP_KEYS = frozenset(
    {
        "winner_adapter",
        "winner_safetensors_sha256",
        "base_target_nll_0_x10000",
        "base_eval",
        "lora_passed_theorems",
        "blockh4_passed_theorems",
        "arms",
    }
)
_PROVER_BASE_KEYS = frozenset(
    {
        "tactics_total",
        "live_lean_kernel_pass",
        "audit_total",
        "exact_escape_class_ok",
        "escape_tp",
        "escape_fp",
        "escape_fn",
        "escape_tn",
    }
)
_PROVER_ARM_KEYS = _ARM_COMMON_KEYS | _PROVER_BASE_KEYS | frozenset(
    {
        "tactics_latency_ms_x100",
        "tactics_tok_per_sec_x100",
        "audit_latency_ms_x100",
        "audit_tok_per_sec_x100",
        "live_lean_pass_rate_q",
        "live_lean_pass_rate_dec4",
        "r10_static_rejected",
        "audit_strict_json_ok",
        "exact_escape_rate_q",
        "exact_escape_rate_dec4",
        "escape_f1_q",
        "escape_f1_dec4",
    }
)
_PARETO_KEYS = frozenset(
    {
        "scribe_blockh4_fl_improvement_vs_lora_q",
        "scribe_blockh4_fl_improvement_vs_lora_dec4",
        "weaver_blockh4_fl_improvement_vs_lora_q",
        "weaver_blockh4_fl_improvement_vs_lora_dec4",
        "prover_blockh4_fl_improvement_vs_lora_q",
        "prover_blockh4_fl_improvement_vs_lora_dec4",
        "scribe_blockh4_wallclock_ratio_vs_lora_q",
        "scribe_blockh4_wallclock_ratio_vs_lora_dec4",
        "weaver_blockh4_wallclock_ratio_vs_lora_q",
        "weaver_blockh4_wallclock_ratio_vs_lora_dec4",
        "prover_blockh4_wallclock_ratio_vs_lora_q",
        "prover_blockh4_wallclock_ratio_vs_lora_dec4",
    }
)
_P3_KEYS = frozenset(
    {
        "law3_zero_false_accept_enforced",
        "total_heldout_eval_calls",
        "base_zero_shot_gate_passed",
        "winner_law3_gate_passed",
        "winner_law3_gate_pass_rate_q",
        "winner_law3_gate_pass_rate_dec4",
        "deterministic_exact_tasks_total",
        "winner_deterministic_exact_passed",
        "winner_deterministic_exact_rate_q",
        "winner_deterministic_exact_rate_dec4",
        "law4_honest_failure_modes",
    }
)
_FM_KEYS = frozenset({"id", "summary"})
_P4_KEYS = frozenset(
    {
        "inkling2_config_sha256",
        "track_s96_cert_sha256",
        "model_type",
        "quant_algo",
        "hidden_size",
        "intermediate_size",
        "blockh4_zero_pad_compatible",
        "physical_layers",
        "core_layers",
        "num_passes",
        "effective_layers",
        "depth_reuse_ratio_q",
        "loop_core_adapter_leverage_q",
        "gate_rank",
        "n_routed_experts",
        "num_experts_per_tok",
        "active_expert_fraction_q",
        "mtp_block_size",
        "mtp_markov_rank",
        "nvfp4_footprint_gb",
        "rtx3080_vram_gib",
        "workstation_vram_gib",
        "rtx3080_full_resident_fits",
        "workstation_32gib_full_resident_fits",
        "rtx3080_overflow_ratio_q",
    }
)
_P5_KEYS = frozenset(
    {
        "lean_file",
        "lean_sha256",
        "lakefile_sha256",
        "toolchain_sha256",
        "lean_version",
        "theorem_count",
        "universal_theorem_count",
        "zero_axiom_theorem_count",
        "propext_only_theorem_count",
        "propext_quot_theorem_count",
        "classical_choice_count",
        "theorems",
        "max_novelty_class",
        "n0_prior_art_anchored",
        "n1_exact_synthesis_verified",
        "n2_claims_count",
    }
)


# ---------------------------------------------------------------------------
# Strict Zone-B Type, Container, Rational & Digest Guards
# ---------------------------------------------------------------------------

def _is_nonempty_str(val: Any) -> bool:
    return type(val) is str and len(val.strip()) > 0


def _is_lower_hex64(val: Any) -> bool:
    return type(val) is str and len(val) == 64 and all(ch in _HEX_LOWER for ch in val)


def _has_surrogate(text: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def _check_int_digits(val: int) -> None:
    if abs(val).bit_length() > _MAX_INT_BITS:
        raise S95Error("INT_TOO_LARGE", "integer exceeds digit bound")
    if len(str(abs(val))) > MAX_INT_DIGITS:
        raise S95Error("INT_TOO_LARGE", "integer exceeds digit bound")


def _check_container_safety(root: Any) -> None:
    """Iterative depth-bounded strict type & value audit (zero RecursionError)."""
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise S95Error("MAX_DEPTH_EXCEEDED", "container depth exceeds MAX_JSON_DEPTH")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                if type(k) is not str or _has_surrogate(k):
                    raise S95Error("INVALID_DICT_KEY", "dict key must be valid strict str")
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is str:
            if _has_surrogate(cur):
                raise S95Error("LONE_SURROGATE", "lone UTF-16 surrogate forbidden")
        elif t is int:
            _check_int_digits(cur)
        elif t is bool or cur is None:
            continue
        else:
            raise S95Error("FORBIDDEN_VALUE_TYPE", f"forbidden type: {t.__name__}")


def parse_canonical_rational(val: Any, label: str = "rational") -> Fraction:
    """Parse canonical reduced rational string ('n' or 'n/d', d > 1, gcd(|n|,d)==1)."""
    if type(val) is not str:
        raise S95Error("INVALID_RATIONAL", f"{label}: must be strict str")
    parts = val.split("/")
    if len(parts) > 2:
        raise S95Error("INVALID_RATIONAL", f"{label}: multiple slashes")
    num_s = parts[0]
    neg = num_s.startswith("-")
    ndig = num_s[1:] if neg else num_s
    if not ndig or len(ndig) > MAX_INT_DIGITS or any(ch not in _ASCII_DIGITS for ch in ndig):
        raise S95Error("INVALID_RATIONAL", f"{label}: invalid numerator")
    if len(ndig) > 1 and ndig[0] == "0":
        raise S95Error("INVALID_RATIONAL", f"{label}: leading zero in numerator")
    if neg and ndig == "0":
        raise S95Error("INVALID_RATIONAL", f"{label}: negative zero forbidden")
    num = -int(ndig) if neg else int(ndig)
    if len(parts) == 1:
        return Fraction(num, 1)
    den_s = parts[1]
    if not den_s or len(den_s) > MAX_INT_DIGITS or any(ch not in _ASCII_DIGITS for ch in den_s):
        raise S95Error("INVALID_RATIONAL", f"{label}: invalid denominator")
    if den_s[0] == "0":
        raise S95Error("INVALID_RATIONAL", f"{label}: leading zero in denominator")
    den = int(den_s)
    if den <= 1:
        raise S95Error("INVALID_RATIONAL", f"{label}: denominator must be > 1")
    if math.gcd(abs(num), den) != 1:
        raise S95Error("INVALID_RATIONAL", f"{label}: fraction not reduced")
    return Fraction(num, den)


def _dec4_expected(val: Fraction) -> str:
    return str((Decimal(val.numerator) / Decimal(val.denominator)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Strict Zone-B Atomic `dir_fd` I/O (Symlink, Hardlink, FIFO & TOCTOU Safe)
# ---------------------------------------------------------------------------

def _check_pwd_no_symlinks() -> None:
    pwd = os.environ.get("PWD", "")
    if not pwd.startswith("/"):
        return
    cur = Path("/")
    for part in Path(pwd).parts[1:]:
        cur = cur / part
        try:
            st = os.lstat(cur)
        except OSError:
            return
        if stat.S_ISLNK(st.st_mode):
            raise S95Error("SYMLINK_IN_PATH", f"logical PWD contains symlink: {part}")


def _require_single_link(nlink: int, code: str, label: str) -> None:
    if nlink != 1:
        raise S95Error(code, f"hardlinked file forbidden: {label}")


def _open_dir_chain(path: Path) -> tuple[int, str]:
    _check_pwd_no_symlinks()
    if not path.is_absolute():
        try:
            cwd = Path(os.getcwd())
        except OSError as exc:
            raise S95Error("CWD_UNAVAILABLE", f"current directory unavailable: {exc}") from exc
        full = cwd / path
    else:
        full = path
    norm_parts: list[str] = []
    for part in full.parts[1:]:
        if part == "..":
            if norm_parts:
                norm_parts.pop()
        elif part != ".":
            norm_parts.append(part)
    if not norm_parts:
        raise S95Error("INVALID_TARGET_PATH", "path names root directory")
    dir_parts = norm_parts[:-1]
    base_name = norm_parts[-1]
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    dfd = os.open("/", flags)
    for comp in dir_parts:
        try:
            nxt = os.open(comp, flags, dir_fd=dfd)
        except OSError as exc:
            os.close(dfd)
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise S95Error("SYMLINK_IN_PATH", f"symlink or non-dir component: {comp}") from exc
            raise S95Error("DIR_OPEN_FAILED", f"cannot traverse {comp}: {exc}") from exc
        os.close(dfd)
        dfd = nxt
    return dfd, base_name


def read_regular_file_bytes(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    dfd, name = _open_dir_chain(path)
    oflags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = -1
    try:
        try:
            fd = os.open(name, oflags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise S95Error("SYMLINK_FORBIDDEN", f"target is symlink: {name}") from exc
            raise S95Error("FILE_OPEN_FAILED", f"cannot open {name}: {exc}") from exc
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise S95Error("NOT_REGULAR_FILE", f"target is not a regular file: {name}")
        _require_single_link(st.st_nlink, "HARDLINK_FORBIDDEN", name)
        chunks: list[bytes] = []
        total = 0
        while True:
            blk = os.read(fd, 65536)
            if not blk:
                break
            total += len(blk)
            if total > max_bytes:
                raise S95Error("FILE_TOO_LARGE", f"file read exceeds {max_bytes} bytes")
            chunks.append(blk)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dfd)


def write_atomic_0600_bytes(path: Path, data: bytes) -> None:
    dfd, name = _open_dir_chain(path)
    tmp_name = f".{name}.{secrets.token_hex(8)}.tmp"
    tflags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    tfd = -1
    created = False
    try:
        try:
            existing = os.lstat(name, dir_fd=dfd)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if stat.S_ISLNK(existing.st_mode):
                raise S95Error("SYMLINK_FORBIDDEN", f"refusing symlink target: {name}")
            if not stat.S_ISREG(existing.st_mode):
                raise S95Error("NOT_REGULAR_FILE", f"refusing non-regular target: {name}")
            _require_single_link(existing.st_nlink, "HARDLINK_FORBIDDEN", name)
        tfd = os.open(tmp_name, tflags, 0o600, dir_fd=dfd)
        created = True
        view = memoryview(data)
        written = 0
        while written < len(data):
            n = os.write(tfd, view[written:])
            written += n
        os.fchmod(tfd, 0o600)
        os.fsync(tfd)
        tst = os.fstat(tfd)
        _require_single_link(tst.st_nlink, "TMP_HARDLINK_DETECTED", tmp_name)
        os.close(tfd)
        tfd = -1
        os.replace(tmp_name, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        created = False
        os.fsync(dfd)
    except S95Error:
        raise
    except OSError as exc:
        raise S95Error("ATOMIC_WRITE_FAILED", f"atomic write failed: {exc}") from exc
    finally:
        if tfd >= 0:
            os.close(tfd)
        if created:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Strict Zero-Float Canonical JSON Parser (Pre-Parse Digit Cap & Depth Guard)
# ---------------------------------------------------------------------------

def _parse_bounded_int(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_INT_DIGITS:
        raise S95Error("INT_TOO_LARGE", "JSON integer exceeds digit limit")
    return int(token)


def _reject_float(token: str) -> Any:
    raise S95Error("FLOAT_FORBIDDEN", f"JSON float forbidden: {token}")


def _reject_constant(token: str) -> Any:
    raise S95Error("NONFINITE_JSON", f"non-finite JSON constant forbidden: {token}")


def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise S95Error("DUPLICATE_JSON_KEY", f"duplicate JSON key: {k}")
        out[k] = v
    return out


def _check_raw_json_nesting(text: str) -> None:
    depth = 0
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise S95Error("MAX_DEPTH_EXCEEDED", "JSON nesting depth exceeds limit")
        elif ch in "}]":
            if depth > 0:
                depth -= 1


def parse_strict_json_bytes(raw: bytes, *, require_canonical: bool = True) -> dict[str, Any]:
    if b"\r" in raw:
        raise S95Error("CRLF_FORBIDDEN", "CR/CRLF forbidden in canonical JSON")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S95Error("INVALID_UTF8", f"invalid UTF-8 JSON: {exc}") from exc
    _check_raw_json_nesting(text)
    try:
        obj = json.loads(
            text,
            parse_int=_parse_bounded_int,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_dup_pairs,
        )
    except S95Error:
        raise
    except (ValueError, RecursionError) as exc:
        raise S95Error("INVALID_JSON", f"JSON parse error: {exc}") from exc
    if type(obj) is not dict:
        raise S95Error("NON_OBJECT_ROOT", "JSON root must be an object")
    _check_container_safety(obj)
    if require_canonical:
        expected_raw = canonical_json_bytes(obj) + b"\n"
        if raw != expected_raw:
            raise S95Error("NON_CANONICAL_JSON", "JSON bytes are not canonical LF-terminated")
    return obj


# ---------------------------------------------------------------------------
# Full R12 Lean 4.36.0 Static Scanner & Scrubbed Live `lean --stdin` Verifier
# ---------------------------------------------------------------------------

_LEAN4_GUIL_UNWRAP_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
_LEAN4_HARD_LINE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsorry\b"), "LEAN4_SORRY"),
    (re.compile(r"\badmit\b"), "LEAN4_ADMIT"),
    (re.compile(r"(?<!\.)\baxiom\b"), "LEAN4_AXIOM"),
    (re.compile(r"(?<!\.)\bunsafe\b"), "LEAN4_UNSAFE"),
    (re.compile(r"\b(?:native_decide|bv_decide)\b"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\b(?:Lean\.Meta\.)?mkSorry\b"), "LEAN4_MK_SORRY"),
    (re.compile(r"\b(?:Lean\.)?(?:ofReduceBool|ofReduceNat)\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\b(?:Lean\.)?trustCompiler\b"), "LEAN4_TRUST_COMPILER"),
    (
        re.compile(
            r"\b(?:dbgTrace|dbgTraceVal|dbgTraceIfShared|dbgSleep|dbgStackTrace|"
            r"panicCore|panicWithPosWithDecl)\b"
            r"|(?<!\.)\b(?:dbg_trace|dbg_sleep|dbg_stack_trace)(?![\w'.!?])"
            r"|(?<!\.)\b(?:panic|unreachable)!(?![\w'!?])"
        ),
        "LEAN4_DBG_FFI_ESCAPE",
    ),
    (
        re.compile(
            r"(?<!\.)\b(?:macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat|"
            r"notation|infix|infixl|infixr|prefix|postfix)(?![\w'.!?])"
            r"|\binterpolatedStr\b"
        ),
        "LEAN4_META_SYNTAX_ESCAPE",
    ),
)
_LEAN4_IMPORT_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)",
    flags=re.DOTALL,
)
_LEAN4_PARTIAL_DECL_RE = re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", flags=re.DOTALL)
_LEAN4_OPAQUE_DECL_RE = re.compile(r"(?<!\.)\bopaque\s+[A-Za-z_][A-Za-z0-9_.']*", flags=re.DOTALL)
_LEAN4_DEBUG_RE = re.compile(
    r"\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b|\bset_option\b",
    flags=re.DOTALL,
)
_LEAN4_PRINT_KW_BLOCK = (
    "def|theorem|lemma|axiom|inductive|structure|class|instance|opaque|abbrev|example|"
    "namespace|section|end|open|variable|universe|import|set_option|attribute|"
    "local|scoped|private|protected|noncomputable|partial|unsafe|meta|where|by|in|let|have"
)
_LEAN4_SPOOF_RE = re.compile(
    r"#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|exit(?![\w'!?])|guard_msgs(?![\w'!?])|"
    r"print(?![\w'!?])(?!\s+axioms[ \t]+(?!(?:" + _LEAN4_PRINT_KW_BLOCK + r")(?![\w'!?]))[A-Za-z_]))"
    r"|(?<!\.)\b(?:run_cmd|run_meta|initialize|builtin_initialize)\b",
    flags=re.DOTALL,
)
_LEAN4_ATTR_OPEN_RE = re.compile(r"(?:@|(?<!\.)\battribute\s*)\[", flags=re.DOTALL)
_LEAN4_HARD_ATTR_RE = re.compile(
    r"\b(?:extern|implemented_by|export|csimp|init|builtin_init|"
    r"term_elab|command_elab|tactic|macro|macro_rules|"
    r"builtin_term_elab|builtin_command_elab|builtin_tactic|builtin_macro|builtin_macro_rules)\b"
)
_LEAN4_DECIDE_KW_RE = re.compile(r"\bdecide\b")
_LEAN4_FLAG_TOK_RE = re.compile(r"[+-][A-Za-z0-9_]+")
_LEAN4_OPT_PREFIX_RE = re.compile(r"\s*([A-Za-z0-9_]+)\s*:=")
_LEAN4_CONFIG_NATIVE_RE = re.compile(r"\bnative\b(?:\s*:=\s*([^},]*))?")
_LEAN4_CONFIG_WITH_RE = re.compile(r"\bwith\b")
_LEAN4_DECIDE_CFG_BIND_RE = re.compile(
    r"\b(?:DecideConfig|Decide\.Config)\b[ \t)]*:=\s*(?:\(\s*)*\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}\s*:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b",
    flags=re.DOTALL,
)
_LEAN4_AXIOM_OUT_RE = re.compile(
    r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[([^\]]*)\])$"
)
_LEAN4_CHAR_LIT_RE = re.compile(r"(?<![A-Za-z0-9_'])'(?:[^'\\\n]|\\.)'")
_LEAN4_RAW_OPEN_RE = re.compile(r'(?<![A-Za-z0-9_])r(#*)"')


def _strip_lean4_r12(source: str) -> tuple[str, list[str]]:
    """Strip Lean 4 nested block comments, line comments, plain/raw strings & char literals."""
    out: list[str] = []
    errors: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    raw_hashes = -1
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if depth > 0:
            if source.startswith("/-", i):
                depth += 1
                out.append("  ")
                i += 2
            elif source.startswith("-/", i):
                depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if raw_hashes >= 0:
            close_seq = '"' + ("#" * raw_hashes)
            if source.startswith(close_seq, i):
                out.append(" " * len(close_seq))
                i += len(close_seq)
                raw_hashes = -1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_str:
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                in_str = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if source.startswith("/-", i):
            depth = 1
            out.append("  ")
            i += 2
            continue
        if source.startswith("--", i):
            nl = source.find("\n", i)
            end_l = n if nl == -1 else nl
            out.append(" " * (end_l - i))
            i = end_l
            continue
        if ch == '"':
            if i > 0 and source[i - 1] == "!":
                out.append(" ")
                i += 1
                continue
            in_str = True
            out.append(" ")
            i += 1
            continue
        if ch == "'":
            mc = _LEAN4_CHAR_LIT_RE.match(source, i)
            if mc is not None:
                out.append(" " * (mc.end() - i))
                i = mc.end()
                continue
        if ch == "r":
            mr = _LEAN4_RAW_OPEN_RE.match(source, i)
            if mr is not None:
                raw_hashes = len(mr.group(1))
                out.append(" " * (mr.end() - i))
                i = mr.end()
                continue
        out.append(ch)
        i += 1
    if depth > 0:
        errors.append("LEAN4_UNTERMINATED_COMMENT")
    elif in_str or raw_hashes >= 0:
        errors.append("LEAN4_UNTERMINATED_STRING")
    return "".join(out), errors


def _strip_outer_parens(rhs: str) -> str:
    s = rhs.strip()
    while s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    return s


def _is_native_false(rhs: str) -> bool:
    return _strip_outer_parens(rhs) in ("false", "Bool.false")


def _scan_decide_native(cleaned: str) -> bool:
    for mc in _LEAN4_DECIDE_CFG_BIND_RE.finditer(cleaned):
        for grp in mc.groups():
            if grp is not None and not _is_native_false(grp):
                return True
    n = len(cleaned)
    match_rp: dict[int, int] = {}
    pstack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "(":
            pstack.append(idx)
        elif ch == ")" and pstack:
            match_rp[pstack.pop()] = idx
    for m in _LEAN4_DECIDE_KW_RE.finditer(cleaned):
        pos = m.end()
        while True:
            while pos < n:
                if not cleaned[pos].isspace():
                    break
                pos += 1
            if pos >= n:
                break
            ch = cleaned[pos]
            if ch in "+-":
                mf = _LEAN4_FLAG_TOK_RE.match(cleaned, pos)
                if mf is None:
                    break
                if mf.group(0) == "+native":
                    return True
                pos = mf.end()
                continue
            if ch == "(":
                close_i = match_rp.get(pos)
                if close_i is None:
                    break
                mp = _LEAN4_OPT_PREFIX_RE.match(cleaned, pos + 1, close_i)
                if mp is None:
                    break
                key = mp.group(1)
                rhs = cleaned[mp.end() : close_i].strip()
                if key == "native" and not _is_native_false(rhs):
                    return True
                if key == "config":
                    inner = _strip_outer_parens(rhs)
                    if not (inner.startswith("{") and inner.endswith("}")):
                        return True
                    body = inner[1:-1]
                    if "{" in body or "}" in body or _LEAN4_CONFIG_WITH_RE.search(body) is not None:
                        return True
                    for mn in _LEAN4_CONFIG_NATIVE_RE.finditer(body):
                        if mn.group(1) is None or not _is_native_false(mn.group(1)):
                            return True
                pos = close_i + 1
                continue
            break
    return False


def audit_lean4_source_r12(source: str) -> list[str]:
    """Return list of R12 static Lean 4.36.0 finding codes (empty iff clean)."""
    if type(source) is not str:
        raise S95Error("INVALID_LEAN_SOURCE", "Lean source must be strict str")
    cleaned, findings = _strip_lean4_r12(source)
    cleaned = _LEAN4_GUIL_UNWRAP_RE.sub(r"\1", cleaned)
    for line in cleaned.splitlines():
        for pat, code in _LEAN4_HARD_LINE_RULES:
            if pat.search(line) is not None:
                findings.append(code)
    for m_imp in _LEAN4_IMPORT_RE.finditer(cleaned):
        root_pkg = m_imp.group(1).split(".")[0]
        if root_pkg not in ("Init", "Std"):
            findings.append("LEAN4_NON_INIT_IMPORT")
    if _LEAN4_PARTIAL_DECL_RE.search(cleaned) is not None:
        findings.append("LEAN4_PARTIAL")
    if _LEAN4_OPAQUE_DECL_RE.search(cleaned) is not None:
        findings.append("LEAN4_OPAQUE")
    if _scan_decide_native(cleaned):
        findings.append("LEAN4_DECIDE_NATIVE")
    if _LEAN4_DEBUG_RE.search(cleaned) is not None:
        findings.append("LEAN4_SKIP_KERNEL_TC")
    if _LEAN4_SPOOF_RE.search(cleaned) is not None:
        findings.append("LEAN4_EVAL_SPOOF")
    match_rb: dict[int, int] = {}
    bstack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "[":
            bstack.append(idx)
        elif ch == "]" and bstack:
            match_rb[bstack.pop()] = idx
    for m_open in _LEAN4_ATTR_OPEN_RE.finditer(cleaned):
        lb = m_open.end() - 1
        rb = match_rb.get(lb)
        if rb is not None and _LEAN4_HARD_ATTR_RE.search(cleaned, lb + 1, rb) is not None:
            findings.append("LEAN4_ATTR_TRUST_ESCAPE")
    return findings


def _find_lean_binary() -> str:
    found = shutil.which("lean")
    if found is not None:
        return found
    home_env = os.environ.get("HOME")
    if home_env:
        elan_lean = Path(home_env) / ".elan" / "bin" / "lean"
        if elan_lean.is_file():
            return str(elan_lean)
    raise S95Error("LEAN_BINARY_NOT_FOUND", "lean binary not found on PATH or $HOME/.elan/bin")


def _scrubbed_lean_env() -> dict[str, str]:
    """Minimal safe env blocking LEAN_PATH/LEAN_OPTS/LEAN_SRC_PATH/ELAN_TOOLCHAIN/LAKE_HOME/LD_PRELOAD."""
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    home_val = os.environ.get("HOME")
    if home_val:
        env["HOME"] = home_val
    return env


def _verify_lean_output(
    returncode: int,
    stderr: str,
    stdout: str,
    *,
    check_pinned_sha: bool = True,
) -> dict[str, list[str]]:
    require_ok(returncode == 0, "LEAN_COMPILE_FAILED", f"lean exited {returncode}: {stderr}")
    require_ok(stderr == "", "LEAN_STDERR_NONEMPTY", f"unexpected lean stderr: {stderr}")
    records: list[str] = []
    for raw_line in stdout.splitlines():
        s = raw_line.strip()
        if records and "[" in records[-1] and "]" not in records[-1]:
            records[-1] = records[-1] + " " + s
        else:
            records.append(s)
    seen: dict[str, list[str]] = {}
    for line in records:
        m = _LEAN4_AXIOM_OUT_RE.match(line)
        require_ok(m is not None, "LEAN_UNEXPECTED_OUTPUT", f"unexpected lean output: {line}")
        thm = m.group(1)
        require_ok(thm not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate theorem output: {thm}")
        ax_raw = m.group(2)
        ax_list = [] if ax_raw is None else [a.strip() for a in ax_raw.split(",") if a.strip()]
        for ax in ax_list:
            require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"{thm} uses forbidden axiom {ax}")
        seen[thm] = ax_list
    require_ok(len(seen) > 0, "LEAN_ZERO_THEOREMS", "Lean file produced zero verified theorem axiom lines")
    if check_pinned_sha:
        require_ok(tuple(seen.keys()) == LEAN_THEOREMS, "LEAN_THEOREM_SET_MISMATCH", "theorem set mismatch")
    return seen


def verify_lean_file(path: Path, *, check_pinned_sha: bool = True) -> dict[str, Any]:
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    if b"\r" in raw:
        raise S95Error("CRLF_FORBIDDEN", "CR/CRLF forbidden in Lean file")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S95Error("INVALID_UTF8", f"invalid UTF-8 in Lean file: {exc}") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if check_pinned_sha and not hmac.compare_digest(sha, LEAN_FILE_SHA256):
        raise S95Error("LEAN_SHA_MISMATCH", "Lean file SHA-256 mismatch")
    findings = audit_lean4_source_r12(source)
    require_ok(len(findings) == 0, "LEAN_R12_STATIC_FINDING", f"R12 findings: {findings}")
    lean_bin = _find_lean_binary()
    proc = subprocess.run(
        [lean_bin, "--stdin"],
        input=source,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=_scrubbed_lean_env(),
    )
    seen = _verify_lean_output(proc.returncode, proc.stderr, proc.stdout, check_pinned_sha=check_pinned_sha)
    return {
        "lean_file": path.name,
        "sha256": sha,
        "r12_findings": 0,
        "theorems_verified": len(seen),
        "allowed_axioms": sorted(_ALLOWED_LEAN_AXIOMS),
    }


# ---------------------------------------------------------------------------
# Field-Complete Independent Secondary Audit (Surface 4: SEC — ZERO Oracle Replay!)
# ---------------------------------------------------------------------------

def _require_dict_keys(obj: Any, expected: frozenset[str], code: str) -> dict[str, Any]:
    if type(obj) is not dict:
        raise S95Error(code, f"non-dict object for {code}")
    if set(obj.keys()) != expected:
        raise S95Error(code, f"exact keys mismatch for {code}")
    return obj


def _req_int(val: Any, min_val: int, code: str, label: str) -> int:
    require_ok(type(val) is int, code, f"{label}: must be strict int")
    require_ok(val >= min_val, code, f"{label}: below minimum {min_val}")
    return val


def _req_hex_pin(val: Any, expected: str, code: str, label: str) -> None:
    require_ok(_is_lower_hex64(val), code, f"{label}: invalid lower-hex64")
    require_ok(hmac.compare_digest(val, expected), code, f"{label}: pinned digest mismatch")


def _req_q_dec4(q_val: Any, dec_val: Any, expected: Fraction, code: str, label: str) -> None:
    require_ok(parse_canonical_rational(q_val, label) == expected, code, f"{label}: exact rational mismatch")
    require_ok(dec_val == _dec4_expected(expected), code, f"{label}: dec4 mismatch")


def _require_fl(val: Fraction | None, code: str, label: str) -> Fraction:
    if val is None:
        raise S95Error(code, f"{label}: expected positive learning F/L ratio")
    return val


def _verify_envelope_digests(cert: dict[str, Any]) -> dict[str, Any]:
    _require_dict_keys(cert, _CERT_KEYS, "BAD_CERT_KEYS")
    require_ok(cert["schema_version"] == SCHEMA_VERSION, "BAD_SCHEMA_VERSION", "schema mismatch")
    require_ok(cert["track_id"] == TRACK_ID, "BAD_TRACK_ID", "track_id mismatch")
    psha = cert["payload_sha256"]
    csha = cert["certificate_sha256"]
    require_ok(_is_lower_hex64(psha), "BAD_PAYLOAD_SHA_SYNTAX", "payload_sha256 must be 64 lower hex")
    require_ok(_is_lower_hex64(csha), "BAD_CERT_SHA_SYNTAX", "certificate_sha256 must be 64 lower hex")
    payload = cert["payload"]
    if type(payload) is not dict:
        raise S95Error("BAD_PAYLOAD_TYPE", "payload must be strict dict")
    calc_p = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    require_ok(hmac.compare_digest(psha, calc_p), "PAYLOAD_SHA_MISMATCH", "payload digest mismatch")
    env = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": psha,
        "payload": payload,
    }
    calc_c = hashlib.sha256(canonical_json_bytes(env)).hexdigest()
    require_ok(hmac.compare_digest(csha, calc_c), "CERT_SHA_MISMATCH", "certificate digest mismatch")
    return payload


def _audit_nll_block(arm: dict[str, Any], base_nll_0: int, tgt_nll_0: int, label: str) -> Fraction | None:
    ba = _req_int(arm["base_retention_nll_after_x10000"], 0, "BAD_NLL_INT", f"{label}.ba")
    ta = _req_int(arm["target_eval_nll_after_x10000"], 0, "BAD_NLL_INT", f"{label}.ta")
    exp_df = Fraction(ba - base_nll_0, 10000)
    exp_dl = Fraction(tgt_nll_0 - ta, 10000)
    _req_q_dec4(arm["delta_forgetting_q"], arm["delta_forgetting_dec4"], exp_df, "NLL_DF_MISMATCH", f"{label}.df")
    _req_q_dec4(arm["delta_learning_q"], arm["delta_learning_dec4"], exp_dl, "NLL_DL_MISMATCH", f"{label}.dl")
    if exp_dl > 0:
        exp_fl = exp_df / exp_dl
        _req_q_dec4(arm["forgetting_learning_ratio_q"], arm["forgetting_learning_ratio_dec4"], exp_fl, "NLL_FL_MISMATCH", f"{label}.fl")
        require_ok(arm["beats_s78_unit_wall"] is (exp_fl < Fraction(1)), "NLL_WALL_MISMATCH", label)
        return exp_fl
    require_ok(arm["forgetting_learning_ratio_q"] == "NEG_LEARNING", "NLL_NEG_LEARN_MISMATCH", f"{label}.fl_q")
    require_ok(arm["forgetting_learning_ratio_dec4"] == "NEG_LEARNING", "NLL_NEG_LEARN_MISMATCH", f"{label}.fl_d")
    require_ok(arm["beats_s78_unit_wall"] is False, "NLL_NEG_LEARN_MISMATCH", f"{label}.wall")
    return None


def _audit_arm_common(arm: dict[str, Any], expected_params: int, label: str) -> None:
    tp = _req_int(arm["trainable_params"], 1, "ARM_PARAMS_MISMATCH", f"{label}.params")
    require_ok(tp == expected_params, "ARM_PARAMS_MISMATCH", label)
    for k in ("peak_vram_mib", "train_seconds_x100", "ms_per_step_x100", "opt_steps"):
        _req_int(arm[k], 1, "ARM_POS_INT_BAD", f"{label}.{k}")
    _req_int(arm["max_merge_diff_x1e6"], 0, "ARM_MERGE_BAD", f"{label}.merge")
    require_ok(_is_lower_hex64(arm["safetensors_sha256"]), "ARM_SHA_BAD", label)


def _audit_confusion(tp: Any, fp: Any, fn: Any, tn: Any, total: int, label: str) -> Fraction:
    i_tp = _req_int(tp, 0, "CONFUSION_MISMATCH", f"{label}.tp")
    i_fp = _req_int(fp, 0, "CONFUSION_MISMATCH", f"{label}.fp")
    i_fn = _req_int(fn, 0, "CONFUSION_MISMATCH", f"{label}.fn")
    i_tn = _req_int(tn, 0, "CONFUSION_MISMATCH", f"{label}.tn")
    require_ok((i_tp + i_fp + i_fn + i_tn) == total, "CONFUSION_MISMATCH", label)
    denom = 2 * i_tp + i_fp + i_fn
    return Fraction(0) if denom == 0 else Fraction(2 * i_tp, denom)


def _audit_pillar1(p1: Any) -> tuple[int, int]:
    d = _require_dict_keys(p1, _P1_KEYS, "BAD_P1_KEYS")
    for k in ("base_model_id", "base_model_license", "gpu_name", "results_file_name", "mlos_receipt_file_name"):
        require_ok(_is_nonempty_str(d[k]), "BAD_P1_STR", k)
    _req_hex_pin(d["results_file_sha256"], RESULTS_FILE_SHA256, "BAD_P1_RES_SHA", "results_file_sha256")
    _req_hex_pin(d["mlos_receipt_file_sha256"], MLOS_RECEIPT_FILE_SHA256, "BAD_P1_MLOS_SHA", "mlos_receipt_file_sha256")
    _req_hex_pin(d["mlos_receipt_inner_sha256"], MLOS_RECEIPT_INNER_SHA256, "BAD_P1_MLOS_INNER_SHA", "mlos_receipt_inner_sha256")
    _req_hex_pin(d["mlos_profile_sha256"], MLOS_PROFILE_SHA256, "BAD_P1_PROFILE_SHA", "mlos_profile_sha256")
    require_ok(d["mlos_clean_hardware_run"] is True, "BAD_P1_MLOS_STATE", "clean_hardware_run")
    require_ok(_req_int(d["mlos_exit_code"], 0, "BAD_P1_MLOS_STATE", "exit") == 0, "BAD_P1_MLOS_STATE", "exit_code")
    require_ok(_req_int(d["mlos_anomaly_count"], 0, "BAD_P1_MLOS_STATE", "anom") == 0, "BAD_P1_MLOS_STATE", "anomalies")
    _req_int(d["mlos_duration_ms_x1000"], 1, "BAD_P1_MLOS_STATE", "duration")
    for k in (
        "results_file_bytes",
        "seed",
        "matched_adapter_budget_s",
        "lora_alpha",
        "merged_layers_count",
        "exact_matched_trainable_params",
        "total_params_with_adapter",
        "merged_safetensors_bytes",
        "base_retention_nll_0_x10000",
    ):
        _req_int(d[k], 1, "BAD_P1_POS_INT", k)
    s_b = d["matched_adapter_budget_s"]
    exp_p = 24 * (2 * s_b * (896 + 896) + 2 * s_b * (896 + 128) + 3 * s_b * (896 + 4864))
    require_ok(d["exact_matched_trainable_params"] == exp_p, "P1_PARAM_BUDGET_MISMATCH", "param formula mismatch")
    require_ok(d["merged_layers_count"] == 168, "P1_LAYERS_MISMATCH", "merged_layers != 168")
    ds = d["datasets"]
    require_ok(type(ds) is list, "BAD_P1_DATASETS", "datasets must be list")
    require_ok(len(ds) == 7, "BAD_P1_DATASETS", "expected 7 dataset files")
    seen_f: set[str] = set()
    sum_rows = 0
    sum_bytes = 0
    for row in ds:
        r = _require_dict_keys(row, _DS_ROW_KEYS, "BAD_DS_ROW_KEYS")
        require_ok(_is_nonempty_str(r["file"]), "BAD_DS_FILE", "empty dataset file")
        require_ok(r["file"] not in seen_f, "BAD_DS_FILE", "duplicate dataset file")
        rows_i = _req_int(r["rows"], 1, "BAD_DS_COUNTS", f"{r['file']}.rows")
        bytes_i = _req_int(r["bytes"], 1, "BAD_DS_COUNTS", f"{r['file']}.bytes")
        require_ok(_is_lower_hex64(r["sha256"]), "BAD_DS_SHA", r["file"])
        seen_f.add(r["file"])
        sum_rows += rows_i
        sum_bytes += bytes_i
    require_ok(_req_int(d["dataset_total_rows"], 1, "P1_DS_TOTALS_MISMATCH", "tot_rows") == sum_rows, "P1_DS_TOTALS_MISMATCH", "rows sum")
    require_ok(_req_int(d["dataset_total_bytes"], 1, "P1_DS_TOTALS_MISMATCH", "tot_bytes") == sum_bytes, "P1_DS_TOTALS_MISMATCH", "bytes sum")
    require_ok(d["dataset_under_5mib"] is (sum_bytes < 5 * 1024 * 1024), "P1_DS_TOTALS_MISMATCH", "under_5mib")
    return exp_p, d["base_retention_nll_0_x10000"]


def _audit_pillar2(p2: Any, exp_params: int, base_nll_0: int) -> dict[str, int]:
    d = _require_dict_keys(p2, _P2_KEYS, "BAD_P2_KEYS")

    # 1. Scribe
    sc = _require_dict_keys(d["aletheia_scribe_0_5b"], _SCRIBE_SP_KEYS, "BAD_SCRIBE_KEYS")
    require_ok(sc["winner_adapter"] in _ADAPTER_SET, "BAD_SCRIBE_HDR", "scribe winner set")
    sc_t0 = _req_int(sc["base_target_nll_0_x10000"], 1, "BAD_SCRIBE_HDR", "scribe tgt0")
    sc_b = _require_dict_keys(sc["base_eval"], _SCRIBE_BASE_KEYS, "BAD_SCRIBE_BASE")
    sc_tot = _req_int(sc_b["total"], 1, "BAD_SCRIBE_TOTAL", "scribe total")
    _audit_confusion(sc_b["hygiene_tp"], sc_b["hygiene_fp"], sc_b["hygiene_fn"], sc_b["hygiene_tn"], sc_tot, "scribe_base")
    _req_int(sc_b["strict_json_ok"], 0, "BAD_SCRIBE_BASE_CNT", "sc_b.json")
    _req_int(sc_b["exact_all7_ok"], 0, "BAD_SCRIBE_BASE_CNT", "sc_b.ex7")
    sc_arms = _require_dict_keys(sc["arms"], _ADAPTER_SET, "BAD_SCRIBE_ARMS")
    sc_fl: dict[str, Fraction] = {}
    for k in ADAPTER_KINDS:
        a = _require_dict_keys(sc_arms[k], _SCRIBE_ARM_KEYS, f"BAD_SCRIBE_ARM_{k}")
        _audit_arm_common(a, exp_params, f"scribe.{k}")
        _req_int(a["latency_ms_x100"], 1, "BAD_SCRIBE_PERF", f"{k}.lat")
        _req_int(a["tok_per_sec_x100"], 1, "BAD_SCRIBE_PERF", f"{k}.tps")
        require_ok(_req_int(a["total"], 1, "BAD_SCRIBE_BOUNDS", f"{k}.tot") == sc_tot, "BAD_SCRIBE_BOUNDS", f"{k}.tot")
        sj = _req_int(a["strict_json_ok"], 0, "BAD_SCRIBE_BOUNDS", f"{k}.sj")
        ex7 = _req_int(a["exact_all7_ok"], 0, "BAD_SCRIBE_BOUNDS", f"{k}.ex7")
        require_ok(ex7 <= sj <= sc_tot, "BAD_SCRIBE_BOUNDS", f"{k}.order")
        _req_q_dec4(a["exact_all7_rate_q"], a["exact_all7_rate_dec4"], Fraction(ex7, sc_tot), "SCRIBE_ACC_MISMATCH", f"sc_acc.{k}")
        exp_f1 = _audit_confusion(a["hygiene_tp"], a["hygiene_fp"], a["hygiene_fn"], a["hygiene_tn"], sc_tot, f"scribe.{k}")
        _req_q_dec4(a["hygiene_f1_q"], a["hygiene_f1_dec4"], exp_f1, "SCRIBE_F1_MISMATCH", f"sc_f1.{k}")
        sc_fl[k] = _require_fl(_audit_nll_block(a, base_nll_0, sc_t0, f"scribe.{k}"), "SCRIBE_FL_NONE", k)
    exp_sc_win = max(ADAPTER_KINDS, key=lambda k: (sc_arms[k]["exact_all7_ok"], sc_arms[k]["hygiene_tp"] - sc_arms[k]["hygiene_fp"], -sc_arms[k]["base_retention_nll_after_x10000"]))
    require_ok(sc["winner_adapter"] == exp_sc_win, "SCRIBE_WINNER_MISMATCH", "scribe winner")
    require_ok(sc["winner_safetensors_sha256"] == sc_arms[exp_sc_win]["safetensors_sha256"], "SCRIBE_WINNER_SHA_MISMATCH", "scribe winner sha")

    # 2. Weaver
    wv = _require_dict_keys(d["aletheia_weaver_0_5b"], _WEAVER_SP_KEYS, "BAD_WEAVER_KEYS")
    require_ok(wv["winner_adapter"] in _ADAPTER_SET, "BAD_WEAVER_HDR", "weaver winner set")
    require_ok(wv["retention_pareto_adapter"] in _ADAPTER_SET, "BAD_WEAVER_HDR", "weaver pareto set")
    wv_t0 = _req_int(wv["base_target_nll_0_x10000"], 1, "BAD_WEAVER_HDR", "weaver tgt0")
    wv_b = _require_dict_keys(wv["base_eval"], _WEAVER_BASE_KEYS, "BAD_WEAVER_BASE")
    wv_tot = _req_int(wv_b["total"], 1, "BAD_WEAVER_TOTAL", "weaver total")
    _audit_confusion(wv_b["cs03_tp"], wv_b["cs03_fp"], wv_b["cs03_fn"], wv_b["cs03_tn"], wv_tot, "weaver_base")
    for bk in ("strict_json_ok", "exact_all5_ok", "pathway_class_ok", "operator_tag_ok"):
        _req_int(wv_b[bk], 0, "BAD_WEAVER_BASE_CNT", bk)
    wv_arms = _require_dict_keys(wv["arms"], _ADAPTER_SET, "BAD_WEAVER_ARMS")
    wv_fl: dict[str, Fraction] = {}
    for k in ADAPTER_KINDS:
        a = _require_dict_keys(wv_arms[k], _WEAVER_ARM_KEYS, f"BAD_WEAVER_ARM_{k}")
        _audit_arm_common(a, exp_params, f"weaver.{k}")
        _req_int(a["latency_ms_x100"], 1, "BAD_WEAVER_PERF", f"{k}.lat")
        _req_int(a["tok_per_sec_x100"], 1, "BAD_WEAVER_PERF", f"{k}.tps")
        require_ok(_req_int(a["total"], 1, "BAD_WEAVER_BOUNDS", f"{k}.tot") == wv_tot, "BAD_WEAVER_BOUNDS", f"{k}.tot")
        sj = _req_int(a["strict_json_ok"], 0, "BAD_WEAVER_BOUNDS", f"{k}.sj")
        ex5 = _req_int(a["exact_all5_ok"], 0, "BAD_WEAVER_BOUNDS", f"{k}.ex5")
        pc = _req_int(a["pathway_class_ok"], 0, "BAD_WEAVER_BOUNDS", f"{k}.pc")
        ot = _req_int(a["operator_tag_ok"], 0, "BAD_WEAVER_BOUNDS", f"{k}.ot")
        require_ok(ex5 <= pc <= sj <= wv_tot, "BAD_WEAVER_BOUNDS", f"{k}.order")
        require_ok(ot <= sj, "BAD_WEAVER_BOUNDS", f"{k}.ot_le_sj")
        _req_q_dec4(a["exact_all5_rate_q"], a["exact_all5_rate_dec4"], Fraction(ex5, wv_tot), "WEAVER_ACC_MISMATCH", f"wv_a5.{k}")
        _req_q_dec4(a["pathway_class_rate_q"], a["pathway_class_rate_dec4"], Fraction(pc, wv_tot), "WEAVER_PCLS_MISMATCH", f"wv_pc.{k}")
        exp_f1 = _audit_confusion(a["cs03_tp"], a["cs03_fp"], a["cs03_fn"], a["cs03_tn"], wv_tot, f"weaver.{k}")
        _req_q_dec4(a["cs03_f1_q"], a["cs03_f1_dec4"], exp_f1, "WEAVER_F1_MISMATCH", f"wv_f1.{k}")
        wv_fl[k] = _require_fl(_audit_nll_block(a, base_nll_0, wv_t0, f"weaver.{k}"), "WEAVER_FL_NONE", k)
    exp_wv_win = max(ADAPTER_KINDS, key=lambda k: (wv_arms[k]["pathway_class_ok"] + wv_arms[k]["cs03_tp"], wv_arms[k]["exact_all5_ok"], -wv_arms[k]["base_retention_nll_after_x10000"]))
    require_ok(wv["winner_adapter"] == exp_wv_win, "WEAVER_WINNER_MISMATCH", "weaver winner")
    require_ok(wv["winner_safetensors_sha256"] == wv_arms[exp_wv_win]["safetensors_sha256"], "WEAVER_WINNER_SHA_MISMATCH", "weaver winner sha")

    # 3. Prover
    pv = _require_dict_keys(d["aletheia_prover_0_5b"], _PROVER_SP_KEYS, "BAD_PROVER_KEYS")
    require_ok(pv["winner_adapter"] in _ADAPTER_SET, "BAD_PROVER_HDR", "prover winner set")
    pv_t0 = _req_int(pv["base_target_nll_0_x10000"], 1, "BAD_PROVER_HDR", "prover tgt0")
    pv_b = _require_dict_keys(pv["base_eval"], _PROVER_BASE_KEYS, "BAD_PROVER_BASE")
    pv_ttot = _req_int(pv_b["tactics_total"], 1, "BAD_PROVER_TOTALS", "pv_b.ttot")
    pv_atot = _req_int(pv_b["audit_total"], 1, "BAD_PROVER_TOTALS", "pv_b.atot")
    _req_int(pv_b["live_lean_kernel_pass"], 0, "BAD_PROVER_BASE_CNT", "pv_b.tac")
    _req_int(pv_b["exact_escape_class_ok"], 0, "BAD_PROVER_BASE_CNT", "pv_b.aud")
    _audit_confusion(pv_b["escape_tp"], pv_b["escape_fp"], pv_b["escape_fn"], pv_b["escape_tn"], pv_atot, "prover_base")
    pv_arms = _require_dict_keys(pv["arms"], _ADAPTER_SET, "BAD_PROVER_ARMS")
    pv_fl: dict[str, Fraction | None] = {}
    for k in ADAPTER_KINDS:
        a = _require_dict_keys(pv_arms[k], _PROVER_ARM_KEYS, f"BAD_PROVER_ARM_{k}")
        _audit_arm_common(a, exp_params, f"prover.{k}")
        for pk in ("tactics_latency_ms_x100", "tactics_tok_per_sec_x100", "audit_latency_ms_x100", "audit_tok_per_sec_x100"):
            _req_int(a[pk], 1, "BAD_PROVER_PERF", f"{k}.{pk}")
        require_ok(_req_int(a["tactics_total"], 1, "BAD_PROVER_BOUNDS", f"{k}.ttot") == pv_ttot, "BAD_PROVER_BOUNDS", f"{k}.ttot")
        require_ok(_req_int(a["audit_total"], 1, "BAD_PROVER_BOUNDS", f"{k}.atot") == pv_atot, "BAD_PROVER_BOUNDS", f"{k}.atot")
        lp = _req_int(a["live_lean_kernel_pass"], 0, "BAD_PROVER_BOUNDS", f"{k}.lp")
        require_ok(lp <= pv_ttot, "BAD_PROVER_BOUNDS", f"{k}.lp_le")
        _req_int(a["r10_static_rejected"], 0, "BAD_PROVER_BOUNDS", f"{k}.r10")
        asj = _req_int(a["audit_strict_json_ok"], 0, "BAD_PROVER_BOUNDS", f"{k}.asj")
        aec = _req_int(a["exact_escape_class_ok"], 0, "BAD_PROVER_BOUNDS", f"{k}.aec")
        require_ok(aec <= asj <= pv_atot, "BAD_PROVER_BOUNDS", f"{k}.aud_order")
        _req_q_dec4(a["live_lean_pass_rate_q"], a["live_lean_pass_rate_dec4"], Fraction(lp, pv_ttot), "PROVER_TAC_MISMATCH", f"pv_tac.{k}")
        _req_q_dec4(a["exact_escape_rate_q"], a["exact_escape_rate_dec4"], Fraction(aec, pv_atot), "PROVER_AUD_MISMATCH", f"pv_aud.{k}")
        exp_f1 = _audit_confusion(a["escape_tp"], a["escape_fp"], a["escape_fn"], a["escape_tn"], pv_atot, f"prover.{k}")
        _req_q_dec4(a["escape_f1_q"], a["escape_f1_dec4"], exp_f1, "PROVER_F1_MISMATCH", f"pv_f1.{k}")
        pv_fl[k] = _audit_nll_block(a, base_nll_0, pv_t0, f"prover.{k}")
    exp_pv_win = max(ADAPTER_KINDS, key=lambda k: (pv_arms[k]["live_lean_kernel_pass"] + pv_arms[k]["exact_escape_class_ok"], pv_arms[k]["live_lean_kernel_pass"], -pv_arms[k]["base_retention_nll_after_x10000"]))
    require_ok(pv["winner_adapter"] == exp_pv_win, "PROVER_WINNER_MISMATCH", "prover winner")
    require_ok(pv["winner_safetensors_sha256"] == pv_arms[exp_pv_win]["safetensors_sha256"], "PROVER_WINNER_SHA_MISMATCH", "prover winner sha")
    for lst_k, arm_k in (("lora_passed_theorems", "standard_lora"), ("blockh4_passed_theorems", "blockh4_butterfly")):
        lst = pv[lst_k]
        require_ok(type(lst) is list, "PROVER_PASSED_THMS_MISMATCH", f"{lst_k}.list")
        require_ok(len(lst) == pv_arms[arm_k]["live_lean_kernel_pass"], "PROVER_PASSED_THMS_MISMATCH", f"{lst_k}.len")
        require_ok(all(_is_nonempty_str(t) for t in lst), "PROVER_PASSED_THMS_MISMATCH", f"{lst_k}.str")
        require_ok(len(set(lst)) == len(lst), "PROVER_PASSED_THMS_MISMATCH", f"{lst_k}.uniq")

    # 4. Beyond-LoRA Pareto cross-ratios
    par = _require_dict_keys(d["beyond_lora_pareto_summary"], _PARETO_KEYS, "BAD_PARETO_KEYS")
    pv_lora_fl = _require_fl(pv_fl["standard_lora"], "PARETO_PV_FL_MISSING", "prover lora fl")
    pv_bh_fl = _require_fl(pv_fl["blockh4_butterfly"], "PARETO_PV_FL_MISSING", "prover blockh4 fl")
    exp_ratios = (
        ("scribe_blockh4_fl_improvement_vs_lora", sc_fl["standard_lora"] / sc_fl["blockh4_butterfly"]),
        ("weaver_blockh4_fl_improvement_vs_lora", wv_fl["standard_lora"] / wv_fl["blockh4_butterfly"]),
        ("prover_blockh4_fl_improvement_vs_lora", pv_lora_fl / pv_bh_fl),
        ("scribe_blockh4_wallclock_ratio_vs_lora", Fraction(sc_arms["blockh4_butterfly"]["train_seconds_x100"], sc_arms["standard_lora"]["train_seconds_x100"])),
        ("weaver_blockh4_wallclock_ratio_vs_lora", Fraction(wv_arms["blockh4_butterfly"]["train_seconds_x100"], wv_arms["standard_lora"]["train_seconds_x100"])),
        ("prover_blockh4_wallclock_ratio_vs_lora", Fraction(pv_arms["blockh4_butterfly"]["train_seconds_x100"], pv_arms["standard_lora"]["train_seconds_x100"])),
    )
    for pfx, exp_r in exp_ratios:
        _req_q_dec4(par[f"{pfx}_q"], par[f"{pfx}_dec4"], exp_r, "PARETO_RATIO_MISMATCH", pfx)

    return {
        "total_eval": sc_tot + wv_tot + pv_ttot + pv_atot,
        "base_passed": sc_b["strict_json_ok"] + wv_b["strict_json_ok"] + pv_b["live_lean_kernel_pass"] + pv_b["exact_escape_class_ok"],
        "win_gate": sc_arms[exp_sc_win]["strict_json_ok"] + wv_arms[exp_wv_win]["strict_json_ok"] + pv_arms[exp_pv_win]["live_lean_kernel_pass"] + pv_arms[exp_pv_win]["audit_strict_json_ok"],
        "det_total": sc_tot + pv_atot + pv_ttot,
        "det_exact": sc_arms[exp_sc_win]["exact_all7_ok"] + pv_arms[exp_pv_win]["exact_escape_class_ok"] + pv_arms[exp_pv_win]["live_lean_kernel_pass"],
    }


def _audit_pillar3(p3: Any, p2_totals: dict[str, int]) -> None:
    d = _require_dict_keys(p3, _P3_KEYS, "BAD_P3_KEYS")
    require_ok(d["law3_zero_false_accept_enforced"] is True, "BAD_P3_ZERO_FA", "zero false accept must be true")
    for dk, pk in (
        ("total_heldout_eval_calls", "total_eval"),
        ("base_zero_shot_gate_passed", "base_passed"),
        ("winner_law3_gate_passed", "win_gate"),
        ("deterministic_exact_tasks_total", "det_total"),
        ("winner_deterministic_exact_passed", "det_exact"),
    ):
        require_ok(d[dk] == p2_totals[pk], "P3_TOTALS_MISMATCH", dk)
    _req_q_dec4(d["winner_law3_gate_pass_rate_q"], d["winner_law3_gate_pass_rate_dec4"], Fraction(p2_totals["win_gate"], p2_totals["total_eval"]), "P3_RATES_MISMATCH", "p3_gp")
    _req_q_dec4(d["winner_deterministic_exact_rate_q"], d["winner_deterministic_exact_rate_dec4"], Fraction(p2_totals["det_exact"], p2_totals["det_total"]), "P3_RATES_MISMATCH", "p3_de")
    fms = d["law4_honest_failure_modes"]
    require_ok(type(fms) is list, "BAD_P3_FMS", "failure modes must be list")
    require_ok(len(fms) == 3, "BAD_P3_FMS", "expected 3 Law-4 failure modes")
    seen_fm: set[str] = set()
    for fm in fms:
        f = _require_dict_keys(fm, _FM_KEYS, "BAD_FM_KEYS")
        require_ok(_is_nonempty_str(f["id"]), "BAD_FM_ENTRY", "empty failure mode id")
        require_ok(f["id"] not in seen_fm, "BAD_FM_ENTRY", "dup failure mode id")
        require_ok(_is_nonempty_str(f["summary"]), "BAD_FM_ENTRY", "empty failure mode summary")
        seen_fm.add(f["id"])


def _audit_pillar4(p4: Any) -> None:
    d = _require_dict_keys(p4, _P4_KEYS, "BAD_P4_KEYS")
    _req_hex_pin(d["inkling2_config_sha256"], INKLING2_CONFIG_SHA256, "BAD_P4_PINS", "inkling2_config_sha256")
    _req_hex_pin(d["track_s96_cert_sha256"], TRACK_S96_CERT_SHA256, "BAD_P4_PINS", "track_s96_cert_sha256")
    require_ok(d["model_type"] == "inkling2_loop", "BAD_P4_MODEL", "model_type mismatch")
    require_ok(d["quant_algo"] == "NVFP4", "BAD_P4_MODEL", "quant_algo mismatch")
    for k in ("hidden_size", "intermediate_size", "physical_layers", "core_layers", "num_passes", "effective_layers", "gate_rank", "n_routed_experts", "num_experts_per_tok", "mtp_block_size", "mtp_markov_rank", "nvfp4_footprint_gb", "rtx3080_vram_gib", "workstation_vram_gib"):
        _req_int(d[k], 1, "BAD_P4_INT", k)
    exp_eff = (d["physical_layers"] - d["core_layers"]) + d["num_passes"] * d["core_layers"]
    require_ok(d["effective_layers"] == exp_eff, "P4_EFF_LAYERS_MISMATCH", "effective_layers mismatch")
    require_ok(d["blockh4_zero_pad_compatible"] is all(x % 16 == 0 for x in (d["hidden_size"], d["intermediate_size"])), "P4_PAD_MISMATCH", "zero-pad flag mismatch")
    require_ok(parse_canonical_rational(d["depth_reuse_ratio_q"], "p4_dr") == Fraction(exp_eff, d["physical_layers"]), "P4_DEPTH_RATIO_MISMATCH", "depth reuse mismatch")
    require_ok(parse_canonical_rational(d["loop_core_adapter_leverage_q"], "p4_lev") == Fraction(d["num_passes"], 1), "P4_LEV_MISMATCH", "leverage mismatch")
    require_ok(parse_canonical_rational(d["active_expert_fraction_q"], "p4_exp") == Fraction(d["num_experts_per_tok"], d["n_routed_experts"]), "P4_EXPERT_MISMATCH", "active expert fraction mismatch")
    require_ok(d["rtx3080_full_resident_fits"] is (d["nvfp4_footprint_gb"] <= d["rtx3080_vram_gib"]), "P4_VRAM_MISMATCH", "rtx3080 fit")
    require_ok(d["workstation_32gib_full_resident_fits"] is (d["nvfp4_footprint_gb"] <= d["workstation_vram_gib"]), "P4_VRAM_MISMATCH", "ws32 fit")
    require_ok(parse_canonical_rational(d["rtx3080_overflow_ratio_q"], "p4_ovf") == Fraction(d["nvfp4_footprint_gb"], d["rtx3080_vram_gib"]), "P4_VRAM_MISMATCH", "overflow ratio")


def _audit_pillar5(p5: Any) -> None:
    d = _require_dict_keys(p5, _P5_KEYS, "BAD_P5_KEYS")
    require_ok(_is_nonempty_str(d["lean_file"]), "BAD_P5_META", "lean_file empty")
    require_ok(d["lean_version"] == "4.36.0", "BAD_P5_META", "lean_version mismatch")
    _req_hex_pin(d["lean_sha256"], LEAN_FILE_SHA256, "BAD_P5_SHAS", "lean_sha256")
    _req_hex_pin(d["lakefile_sha256"], LAKEFILE_SHA256, "BAD_P5_SHAS", "lakefile_sha256")
    _req_hex_pin(d["toolchain_sha256"], TOOLCHAIN_SHA256, "BAD_P5_SHAS", "toolchain_sha256")
    n_thms = len(LEAN_THEOREMS)
    require_ok(_req_int(d["theorem_count"], 1, "BAD_P5_THMS", "thm_cnt") == n_thms, "BAD_P5_THMS", "theorem_count")
    require_ok(_req_int(d["universal_theorem_count"], 1, "BAD_P5_THMS", "univ_cnt") == n_thms, "BAD_P5_THMS", "universal_count")
    z_cnt = _req_int(d["zero_axiom_theorem_count"], 0, "BAD_P5_THMS", "zero_ax")
    p_cnt = _req_int(d["propext_only_theorem_count"], 0, "BAD_P5_THMS", "propext_ax")
    pq_cnt = _req_int(d["propext_quot_theorem_count"], 0, "BAD_P5_THMS", "pq_ax")
    require_ok(_req_int(d["classical_choice_count"], 0, "BAD_P5_THMS", "cc") == 0, "BAD_P5_THMS", "classical_choice != 0")
    require_ok((z_cnt + p_cnt + pq_cnt) == n_thms, "BAD_P5_THMS", "axiom breakdown sum")
    require_ok(d["theorems"] == list(LEAN_THEOREMS), "BAD_P5_THMS", "theorem list mismatch")
    require_ok(d["max_novelty_class"] == "N1", "BAD_P5_NOVELTY", "max_novelty_class != N1")
    require_ok(d["n0_prior_art_anchored"] is True, "BAD_P5_NOVELTY", "n0 flag")
    require_ok(d["n1_exact_synthesis_verified"] is True, "BAD_P5_NOVELTY", "n1 flag")
    require_ok(_req_int(d["n2_claims_count"], 0, "BAD_P5_NOVELTY", "n2") == 0, "BAD_P5_NOVELTY", "n2_claims_count != 0")


def secondary_audit_payload(cert_or_payload: Any) -> dict[str, Any]:
    """
    Field-complete independent audit of Track S95 certificate or payload without
    calling `build_payload()`. Performs deep copy so caller input is never mutated.
    """
    if type(cert_or_payload) is not dict:
        raise S95Error("NON_DICT_INPUT", "input must be strict dict")
    _check_container_safety(cert_or_payload)
    snap = copy.deepcopy(cert_or_payload)
    payload = _verify_envelope_digests(snap) if "certificate_sha256" in snap else snap

    _require_dict_keys(payload, _PAYLOAD_KEYS, "BAD_PAYLOAD_KEYS")
    require_ok(payload["schema_version"] == SCHEMA_VERSION, "BAD_PAYLOAD_SCHEMA", "payload schema mismatch")
    require_ok(payload["track_id"] == TRACK_ID, "BAD_PAYLOAD_TRACK", "payload track mismatch")
    require_ok(payload["oracle_class"] == ORACLE_CLASS, "BAD_ORACLE_CLASS", "oracle_class mismatch")

    exp_params, base_nll_0 = _audit_pillar1(payload["pillar1_hardware_and_datasets"])
    p2_totals = _audit_pillar2(payload["pillar2_beyond_lora_showdown"], exp_params, base_nll_0)
    _audit_pillar3(payload["pillar3_law3_routing_and_law4_failures"], p2_totals)
    _audit_pillar4(payload["pillar4_inkling2_transfer"])
    _audit_pillar5(payload["pillar5_lean4_and_novelty"])
    payload_digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    require_ok(
        hmac.compare_digest(payload_digest, EXPECTED_PAYLOAD_SHA256),
        "SEC_PINNED_PAYLOAD_MISMATCH",
        "payload does not match pinned frozen S95 certificate content",
    )
    return {"secondary_audit": "PASS", "arms_verified": 9, "matched_params": exp_params, "lean_theorems": len(LEAN_THEOREMS)}


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    """Verify in-memory Track S95 certificate dict (Surfaces FR1 & FR0)."""
    if type(full_replay) is not bool:
        raise S95Error("INVALID_FULL_REPLAY_FLAG", "full_replay must be strict bool")
    if type(cert) is not dict:
        raise S95Error("NON_DICT_CERT", "certificate must be strict dict")
    _check_container_safety(cert)
    snap = copy.deepcopy(cert)
    payload = _verify_envelope_digests(snap)
    if full_replay:
        replayed = build_payload()
        if not hmac.compare_digest(canonical_json_bytes(payload), canonical_json_bytes(replayed)):
            raise S95Error("REPLAY_MISMATCH", "payload does not match deterministic oracle replay")
    secondary_audit_payload(snap)
    return snap


def check_certificate_file(path: Path, *, full_replay: bool = True) -> dict[str, Any]:
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    cert = parse_strict_json_bytes(raw, require_canonical=True)
    return verify_certificate_dict(cert, full_replay=full_replay)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S95 Aletheia Specialist Foundry Verifier")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--standalone", action="store_true", help="Emit canonical certificate JSON to stdout")
    mode.add_argument("--write", type=Path, help="Atomically write 0o600 canonical certificate JSON")
    mode.add_argument("--check", type=Path, help="Verify canonical certificate JSON fail-closed")
    mode.add_argument("--verify-lean", type=Path, help="Run R12 static + scrubbed live Lean 4.36.0 check")
    mode.add_argument("--verify-artifacts", type=Path, help="Verify pinned on-disk S95 track artifacts")
    parser.add_argument("--json", action="store_true", help="Emit compact JSON receipt")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.write is not None:
            cert = build_certificate()
            verify_certificate_dict(cert, full_replay=True)
            write_atomic_0600_bytes(args.write, canonical_json_bytes(cert) + b"\n")
            if args.json:
                sys.stdout.buffer.write(
                    canonical_json_bytes({"status": "WRITTEN", "certificate_sha256": cert["certificate_sha256"]}) + b"\n"
                )
            return 0
        if args.check is not None:
            cert = check_certificate_file(args.check, full_replay=True)
            if args.json:
                sys.stdout.buffer.write(
                    canonical_json_bytes({"status": "PASS", "certificate_sha256": cert["certificate_sha256"]}) + b"\n"
                )
            return 0
        if args.verify_lean is not None:
            res = verify_lean_file(args.verify_lean, check_pinned_sha=True)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        if args.verify_artifacts is not None:
            res = s95.verify_live_artifacts_on_disk(args.verify_artifacts)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        cert = build_certificate()
        verify_certificate_dict(cert, full_replay=True)
        sys.stdout.buffer.write(canonical_json_bytes(cert) + b"\n")
        return 0
    except S95Error as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc.message}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
