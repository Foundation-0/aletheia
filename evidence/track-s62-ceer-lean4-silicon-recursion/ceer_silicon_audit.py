#!/usr/bin/env python3
"""
ceer_silicon_audit.py — Independent hardened verifier & certificate builder for
3-cycle CEER (pure-Init Lean 4.36.0 <-> live hardware silicon recursion).

Verifies:
  1. Strict pure-Z/Q JSON schema (zero floats, zero NaN/Inf, zero duplicate keys,
     zero subclasses, zero NUL/surrogates, bounded depth/nodes/int-bits) on BOTH
     primary AND direct secondary_audit_payload entry points.
  2. Strict filesystem hardening (no symlinks on any path component, regular file only,
     st_nlink == 1, bounded size, atomic 0o600 writes with retry & temp nlink check,
     $PWD dev/ino parity, flag-like & surrogate CLI path rejection, wrapped main(argv)).
  3. Full cryptographic SHA-256 binding of all 19 frozen artifacts (actuator C source,
     runner, toolchain, lakefile, 3 preregs, 3 telemetries, 3 hardware run receipts,
     and all 6 Lean 4.36.0 Theory/Verdict modules), read strictly before oracle parsing.
  4. Hardened Lean 4 static trust-escape audit (comments/strings stripped, French-guillemet
     normalization, decide +native / (native := ...) / (config := ...) / DecideConfig /
     sorry / admit / axiom / unsafe / native_decide / partial / skipKernelTC / extern /
     implemented_by / zero external imports) + anchored unique Lean Verdict witness parity
     against raw telemetry + live Lean 4.36.0 kernel execution & strict #print axioms audit.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
from typing import Any

_TRACK_DIR = Path(__file__).resolve().parent
if str(_TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(_TRACK_DIR))

from ceer_silicon_oracle import (  # noqa: E402
    OracleError,
    compute_ceer_summary,
    exact_schur_3x3,
)

SCHEMA_VERSION = "aletheia.ceer_silicon_certificate.v1"
MAX_FILE_BYTES = 2_000_000
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 100_000
MAX_INT_BITS = 2048
_MAX_TMP_RETRIES = 16
STANDARD_LEAN4_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

LEAN_MODULES: tuple[tuple[str, int], ...] = (
    ("CEERSiliconCerts/CEER_Cycle0_Theory.lean", 7),
    ("CEERSiliconCerts/CEER_Cycle0_Verdict.lean", 6),
    ("CEERSiliconCerts/CEER_Cycle1_Theory.lean", 4),
    ("CEERSiliconCerts/CEER_Cycle1_Verdict.lean", 7),
    ("CEERSiliconCerts/CEER_Cycle2_Theory.lean", 5),
    ("CEERSiliconCerts/CEER_Cycle2_Verdict.lean", 7),
)

EXPECTED_LEAN_THEOREMS: dict[str, frozenset[str]] = {
    "CEER_Cycle0_Theory.lean": frozenset(
        {
            "CEERSiliconCerts.Cycle0Theory.constant_fan_zero_hyst_area",
            "CEERSiliconCerts.Cycle0Theory.falsify_H0a",
            "CEERSiliconCerts.Cycle0Theory.falsify_H0b_dark",
            "CEERSiliconCerts.Cycle0Theory.falsify_H0b_energy",
            "CEERSiliconCerts.Cycle0Theory.falsify_H0c",
            "CEERSiliconCerts.Cycle0Theory.falsify_H0d_area",
            "CEERSiliconCerts.Cycle0Theory.falsify_H0d_rpm",
        }
    ),
    "CEER_Cycle0_Verdict.lean": frozenset(
        {
            "CEERSiliconCerts.Cycle0Verdict.cycle0_H0a_degenerate_pl1_saturation",
            "CEERSiliconCerts.Cycle0Verdict.cycle0_H0b_cliff_gt_80x",
            "CEERSiliconCerts.Cycle0Verdict.cycle0_H0d_fan_plateau_and_thermal_lag",
            "CEERSiliconCerts.Cycle0Verdict.cycle0_disproof_H0b",
            "CEERSiliconCerts.Cycle0Verdict.cycle0_disproof_H0c",
            "CEERSiliconCerts.Cycle0Verdict.cycle0_on_package_dark_power_positive",
        }
    ),
    "CEER_Cycle1_Theory.lean": frozenset(
        {
            "CEERSiliconCerts.Cycle1Theory.falsify_H1b_cliff",
            "CEERSiliconCerts.Cycle1Theory.falsify_H1c_contrast",
            "CEERSiliconCerts.Cycle1Theory.falsify_H1d_temp_lag",
            "CEERSiliconCerts.Cycle1Theory.pl1_flat_power_implies_eff_gain",
        }
    ),
    "CEER_Cycle1_Verdict.lean": frozenset(
        {
            "CEERSiliconCerts.Cycle1Verdict.cycle1_H1b_residual_cliff_and_dark_power",
            "CEERSiliconCerts.Cycle1Verdict.cycle1_H1c_static_dominance_obstruction",
            "CEERSiliconCerts.Cycle1Verdict.cycle1_H1d_reversed_loop_obstruction",
            "CEERSiliconCerts.Cycle1Verdict.cycle1_corroborates_H1a",
            "CEERSiliconCerts.Cycle1Verdict.cycle1_corroborates_H1c",
            "CEERSiliconCerts.Cycle1Verdict.cycle1_disproof_H1b",
            "CEERSiliconCerts.Cycle1Verdict.cycle1_disproof_H1d",
        }
    ),
    "CEER_Cycle2_Theory.lean": frozenset(
        {
            "CEERSiliconCerts.Cycle2Theory.falsify_H2b_cliff",
            "CEERSiliconCerts.Cycle2Theory.falsify_H2c_sign",
            "CEERSiliconCerts.Cycle2Theory.falsify_H2d_zero_delta",
            "CEERSiliconCerts.Cycle2Theory.schur_3x3_variance_identity",
            "CEERSiliconCerts.Cycle2Theory.schur_strict_variance_reduction",
        }
    ),
    "CEER_Cycle2_Verdict.lean": frozenset(
        {
            "CEERSiliconCerts.Cycle2Verdict.cycle2_H2b_primary_cliff_and_dark_power",
            "CEERSiliconCerts.Cycle2Verdict.cycle2_H2d_sharp_schur_reductions",
            "CEERSiliconCerts.Cycle2Verdict.cycle2_corroborates_H2a",
            "CEERSiliconCerts.Cycle2Verdict.cycle2_corroborates_H2c",
            "CEERSiliconCerts.Cycle2Verdict.cycle2_corroborates_H2d",
            "CEERSiliconCerts.Cycle2Verdict.cycle2_disproof_H2b_dram_asymptote",
            "CEERSiliconCerts.Cycle2Verdict.cycle2_epistemic_chain_disjoint_and_monotone",
        }
    ),
}

EXPECTED_ZERO_AXIOM_THEOREMS: frozenset[str] = frozenset(
    {
        "CEERSiliconCerts.Cycle0Theory.falsify_H0d_area",
        "CEERSiliconCerts.Cycle2Theory.falsify_H2d_zero_delta",
        "CEERSiliconCerts.Cycle2Verdict.cycle2_H2d_sharp_schur_reductions",
        "CEERSiliconCerts.Cycle2Verdict.cycle2_corroborates_H2d",
        "CEERSiliconCerts.Cycle2Verdict.cycle2_epistemic_chain_disjoint_and_monotone",
    }
)

ARTIFACT_FILES: tuple[str, ...] = (
    "ceer_actuator.c",
    "ceer_silicon_runner.py",
    "lean-toolchain",
    "lakefile.toml",
    "cycle_0_prereg.json",
    "cycle_0_telemetry.json",
    "mlos_cycle0_receipt.json",
    "cycle_1_prereg.json",
    "cycle_1_telemetry.json",
    "mlos_cycle1_receipt.json",
    "cycle_2_prereg.json",
    "cycle_2_telemetry.json",
    "mlos_cycle2_receipt.json",
    "CEERSiliconCerts/CEER_Cycle0_Theory.lean",
    "CEERSiliconCerts/CEER_Cycle0_Verdict.lean",
    "CEERSiliconCerts/CEER_Cycle1_Theory.lean",
    "CEERSiliconCerts/CEER_Cycle1_Verdict.lean",
    "CEERSiliconCerts/CEER_Cycle2_Theory.lean",
    "CEERSiliconCerts/CEER_Cycle2_Verdict.lean",
)

EXPECTED_TOP_KEYS = frozenset(
    {
        "schema_version",
        "track_id",
        "toolchain",
        "artifact_sha256",
        "mlos_receipts",
        "lean4_verification",
        "ceer_summary",
        "certificate_sha256",
    }
)

_HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_LEAN4_IDENT_EXTRA = "_.'!?"
_LEAN4_GUILLEMET_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
_LEAN4_HARD_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsorry\b"), "LEAN4_SORRY"),
    (re.compile(r"\badmit\b"), "LEAN4_ADMIT"),
    (re.compile(r"(?<!\.)\baxiom\b"), "LEAN4_AXIOM"),
    (re.compile(r"(?<!\.)\bunsafe\b"), "LEAN4_UNSAFE"),
    (re.compile(r"\bnative_decide\b"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\bmkSorry\b"), "LEAN4_MK_SORRY"),
    (re.compile(r"\bofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\bofReduceNat\b"), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"\btrustCompiler\b"), "LEAN4_TRUST_COMPILER"),
    (re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", re.DOTALL), "LEAN4_PARTIAL"),
    (re.compile(r"\bdebug\s*\.\s*skipKernelTC\b", re.DOTALL), "LEAN4_SKIP_KERNEL_TC"),
    (re.compile(r"(?:@|\battribute\s*)\[[^\]]*\b(?:extern|implemented_by)\b[^\]]*\]", re.DOTALL), "LEAN4_UNSOUND_ATTR"),
    (re.compile(r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+[A-Za-z0-9_.]+", re.DOTALL), "LEAN4_EXTERNAL_IMPORT"),
    (re.compile(r"#\s*(?:eval|reduce)\b"), "LEAN4_META_EXEC"),
    (re.compile(r"#\s*print(?!\s+axioms\b)\b"), "LEAN4_PRINT_NON_AXIOMS"),
)
_LEAN4_DECIDE_KW_RE = re.compile(r"\bdecide\b")
_LEAN4_FLAG_TOK_RE = re.compile(r"[+-][A-Za-z0-9_]+")
_LEAN4_OPT_PREFIX_RE = re.compile(r"\s*([A-Za-z0-9_]+)\s*:=")
_LEAN4_CONFIG_NATIVE_RE = re.compile(r"\bnative\b(?:\s*:=\s*([^},]*))?")
_LEAN4_CONFIG_AFTER_COMMA_RE = re.compile(r",\s*(?:\Z|[A-Za-z_][A-Za-z0-9_']*\s*:=)")
_LEAN4_CONFIG_WITH_RE = re.compile(r"\bwith\b")
_LEAN4_DECIDE_CONFIG_BIND_RE = re.compile(
    r"\b(?:DecideConfig|Decide\.Config)\b[ \t)]*:=\s*(?:\(\s*)*\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}\s*:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,:]*)(?:,[^}{]*)?:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b[^}{]*\}",
    re.DOTALL,
)
_LEAN4_AXIOM_ENTRY_RE = re.compile(
    r"'([^']+)' depends on axioms: \[([^\]]*)\]|'([^']+)' does not depend on any axioms",
    re.DOTALL,
)
_LEAN4_WITNESS_FIELD_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\s*:=\s*(-?[0-9]+)\b")


class AuditError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _validate_str_chars(s: str, label: str) -> None:
    if "\x00" in s:
        raise AuditError("NUL_IN_STRING", f"NUL byte in {label}")
    for ch in s:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            raise AuditError("SURROGATE_CHAR", f"unpaired surrogate in {label}")


def _validate_json_tree(obj: Any) -> None:
    stack: list[tuple[Any, int]] = [(obj, 0)]
    nodes = 0
    while stack:
        cur, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise AuditError("DEPTH_LIMIT", "JSON nesting exceeds maximum depth")
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise AuditError("NODE_LIMIT", "JSON node count exceeds maximum")
        t = type(cur)
        if t is type(None) or t is bool:
            continue
        if t is int:
            if cur.bit_length() > MAX_INT_BITS:
                raise AuditError("INT_BIT_LIMIT", "integer exceeds maximum bit width")
            continue
        if t is str:
            _validate_str_chars(cur, "value")
            continue
        if t is list:
            for item in cur:
                stack.append((item, depth + 1))
            continue
        if t is dict:
            for k, v in cur.items():
                if type(k) is not str:
                    raise AuditError("NON_STR_KEY", "dict keys must be exact str")
                _validate_str_chars(k, "key")
                stack.append((v, depth + 1))
            continue
        raise AuditError("FORBIDDEN_TYPE", f"forbidden value type: {t.__name__}")


def _reject_constant(token: str) -> Any:
    raise AuditError("NON_FINITE_JSON", f"forbidden JSON constant: {token}")


def _reject_float(token: str) -> Any:
    raise AuditError("FLOAT_FORBIDDEN", f"floating-point literal forbidden: {token}")


def _strict_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise AuditError("DUPLICATE_KEY", f"duplicate JSON key: {k}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError("INVALID_UTF8", "invalid UTF-8 payload") from exc
    try:
        obj = json.loads(
            text,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
            object_pairs_hook=_strict_pairs_hook,
        )
    except AuditError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise AuditError("INVALID_JSON", f"malformed JSON: {exc}") from exc
    _validate_json_tree(obj)
    if type(obj) is not dict:
        raise AuditError("ROOT_NOT_OBJECT", "JSON root must be an object")
    if raw != canonical_json_bytes(obj) + b"\n":
        raise AuditError("NON_CANONICAL_JSON", "certificate JSON bytes are not canonical")
    return obj


def _verified_cwd() -> Path:
    cwd_real = Path(os.getcwd())
    pwd_env = os.environ.get("PWD", "")
    if os.path.isabs(pwd_env):
        try:
            st_pwd = os.stat(pwd_env)
            st_dot = os.stat(".")
            if (st_pwd.st_dev, st_pwd.st_ino) == (st_dot.st_dev, st_dot.st_ino):
                return Path(pwd_env)
        except (OSError, ValueError):
            pass
    return cwd_real


def _normalize_darwin_prefix(path: Path) -> Path:
    if sys.platform != "darwin":
        return path
    s = str(path)
    for prefix in ("/tmp", "/var", "/etc"):
        if s == prefix or s.startswith(prefix + "/"):
            try:
                st = os.lstat(prefix)
                if stat.S_ISLNK(st.st_mode) and st.st_uid == 0:
                    target = os.readlink(prefix).lstrip("/")
                    if target == "private" + prefix:
                        return Path("/private" + s)
            except OSError:
                return path
    return path


def _check_cli_path_arg(raw: Any) -> Path:
    if type(raw) is not str or not raw:
        raise AuditError("BAD_PATH", "empty or non-string path argument")
    _validate_str_chars(raw, "cli_path")
    if raw.startswith("-"):
        raise AuditError("FLAG_LIKE_PATH", f"refusing flag-like path: {raw}")
    p = Path(raw)
    if not p.is_absolute():
        p = _verified_cwd() / p
    p = _normalize_darwin_prefix(Path(os.path.normpath(str(p))))
    return p


def _require_exact_bool(val: Any, label: str) -> bool:
    if type(val) is not bool:
        raise AuditError("BAD_BOOL", f"{label} must be exact bool")
    return val


def _decode_utf8_strict(raw: bytes, label: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError("INVALID_UTF8", f"invalid UTF-8 in {label}") from exc


def _reject_any_symlink_component(path: Path, check_leaf: bool) -> None:
    parts = path.parts
    cur = Path(parts[0])
    limit = len(parts) if check_leaf else len(parts) - 1
    for idx in range(1, limit):
        cur = cur / parts[idx]
        try:
            st = os.lstat(cur)
        except FileNotFoundError as exc:
            if check_leaf:
                raise AuditError("PATH_NOT_FOUND", f"missing path: {cur}") from exc
            raise AuditError("PARENT_NOT_FOUND", f"missing parent dir: {cur}") from exc
        except OSError as exc:
            raise AuditError("STAT_FAILED", f"lstat failed on {cur}: {exc.strerror}") from exc
        if stat.S_ISLNK(st.st_mode):
            raise AuditError("SYMLINK_REJECTED", f"symlink component rejected: {cur}")


def read_regular_file_strict(path: Path, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    _reject_any_symlink_component(path, check_leaf=True)
    try:
        dfd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise AuditError("OPEN_FAILED", f"cannot open parent dir: {exc.strerror}") from exc
    fd = -1
    try:
        try:
            fd = os.open(
                path.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=dfd,
            )
            st = os.fstat(fd)
        except OSError as exc:
            raise AuditError("OPEN_FAILED", f"cannot open {path.name}: {exc.strerror}") from exc
        if not stat.S_ISREG(st.st_mode):
            raise AuditError("NOT_REGULAR_FILE", f"non-regular file rejected: {path.name}")
        if st.st_nlink != 1:
            raise AuditError("HARDLINK_REJECTED", f"hardlinked file rejected: nlink={st.st_nlink}")
        if st.st_size > max_bytes:
            raise AuditError("FILE_TOO_LARGE", f"file exceeds {max_bytes} bytes")
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError as exc:
                raise AuditError("READ_FAILED", f"read failed on {path.name}: {exc.strerror}") from exc
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise AuditError("FILE_TOO_LARGE", f"stream exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dfd)


def _verify_write_target_safe(dfd: int, name: str) -> None:
    try:
        existing = os.lstat(name, dir_fd=dfd)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise AuditError("STAT_FAILED", f"lstat failed on target: {exc.strerror}") from exc
    if stat.S_ISLNK(existing.st_mode):
        raise AuditError("SYMLINK_REJECTED", f"symlink target rejected: {name}")
    if not stat.S_ISREG(existing.st_mode):
        raise AuditError("NOT_REGULAR_FILE", f"non-regular target rejected: {name}")
    if existing.st_nlink != 1:
        raise AuditError("HARDLINK_REJECTED", f"hardlinked target rejected: {name}")


def write_atomic_0600(path: Path, data: bytes) -> None:
    _reject_any_symlink_component(path, check_leaf=False)
    try:
        dfd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise AuditError("WRITE_FAILED", f"cannot open parent dir: {exc.strerror}") from exc
    tmp_name: str | None = None
    fd = -1
    try:
        _verify_write_target_safe(dfd, path.name)
        try:
            for _ in range(_MAX_TMP_RETRIES):
                cand = f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
                try:
                    fd = os.open(
                        cand,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=dfd,
                    )
                    tmp_name = cand
                    break
                except FileExistsError:
                    continue
            if tmp_name is None:
                raise AuditError("TEMP_EXHAUSTED", "exhausted unique temp file retries")
            os.fchmod(fd, 0o600)
            mv = memoryview(data)
            off = 0
            while off < len(mv):
                written = os.write(fd, mv[off:])
                if written <= 0:
                    raise AuditError("SHORT_WRITE", "os.write returned non-positive count")
                off += written
            if os.fstat(fd).st_nlink != 1:
                raise AuditError("HARDLINK_REJECTED", f"hardlinked temp file rejected: {tmp_name}")
            os.fsync(fd)
            os.close(fd)
            fd = -1
            _verify_write_target_safe(dfd, path.name)
            os.replace(tmp_name, path.name, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise AuditError("WRITE_FAILED", f"atomic write failed: {exc.strerror}") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Hardened Static & Live Lean 4.36.0 Auditor
# ---------------------------------------------------------------------------

def _strip_lean4_comments_and_strings(source: str) -> str:
    """Char-, raw-string (`r"..."`/`r#"..."#`), interpolated-string (`s!"{...}"`),
    and nested-block-comment-safe Lean 4 stripper preserving line count."""
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    in_interp = False
    interp_stack: list[int] = []
    raw_hashes = -1
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if depth > 0:
            if ch == "/" and nxt == "-":
                depth += 1
                out.append("  ")
                i += 2
            elif ch == "-" and nxt == "/":
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
        if in_interp:
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == "{":
                interp_stack.append(1)
                in_interp = False
                out.append(" ")
                i += 1
            elif ch == '"':
                in_interp = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if interp_stack:
            if ch == "{":
                interp_stack[-1] += 1
                out.append(ch)
                i += 1
                continue
            if ch == "}":
                interp_stack[-1] -= 1
                out.append(ch)
                i += 1
                if interp_stack[-1] == 0:
                    interp_stack.pop()
                    in_interp = True
                continue
        if ch == "/" and nxt == "-":
            depth = 1
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "r" and (
            i == 0 or not (source[i - 1].isalnum() or source[i - 1] in _LEAN4_IDENT_EXTRA)
        ):
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                raw_hashes = j - (i + 1)
                out.append(" " * (j - i + 1))
                i = j + 1
            else:
                out.append(ch)
                i += 1
        elif (
            ch == "!"
            and nxt == '"'
            and i >= 1
            and source[i - 1] in "smf"
            and (i == 1 or not (source[i - 2].isalnum() or source[i - 2] in _LEAN4_IDENT_EXTRA))
        ):
            in_interp = True
            out.append("  ")
            i += 2
        elif ch == '"':
            in_str = True
            out.append(" ")
            i += 1
        elif ch == "'" and (
            i == 0 or not (source[i - 1].isalnum() or source[i - 1] in "_'»")
        ):
            if i + 2 < n and source[i + 1] != "\\" and source[i + 2] == "'":
                out.append("   ")
                i += 3
            elif i + 3 < n and source[i + 1] == "\\" and source[i + 3] == "'":
                out.append("    ")
                i += 4
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1
    if depth > 0:
        raise AuditError("LEAN4_UNTERMINATED_COMMENT", "unterminated Lean 4 block comment")
    if in_str or in_interp or raw_hashes >= 0 or interp_stack:
        raise AuditError("LEAN4_UNTERMINATED_STRING", "unterminated Lean 4 string literal")
    return "".join(out)


def _is_lean4_native_rhs_false_span(text: str, lo: int, hi: int) -> bool:
    while True:
        while lo != hi and text[lo].isspace():
            lo += 1
        while hi != lo and text[hi - 1].isspace():
            hi -= 1
        if hi - lo >= 7 and text[lo] == "(" and text[hi - 1] == ")":
            lo += 1
            hi -= 1
            continue
        break
    rem = text[lo:hi] if hi - lo <= 10 else ""
    return rem in ("false", "Bool.false")


def _is_lean4_safe_config_span(
    text: str, lo: int, hi: int, match_rparen: dict[int, int]
) -> bool:
    while True:
        while lo != hi and text[lo].isspace():
            lo += 1
        while hi != lo and text[hi - 1].isspace():
            hi -= 1
        if match_rparen.get(lo) == hi - 1:
            lo += 1
            hi -= 1
            continue
        break
    if text[lo : lo + 1] != "{" or text[hi - 1 : hi] != "}":
        return False
    body_lo = lo + 1
    body_hi = hi - 1
    if text.find("{", body_lo, body_hi) != -1 or text.find("}", body_lo, body_hi) != -1:
        return False
    if _LEAN4_CONFIG_WITH_RE.search(text, body_lo, body_hi) is not None:
        return False
    for m_nv in _LEAN4_CONFIG_NATIVE_RE.finditer(text, body_lo, body_hi):
        if not _is_lean4_native_rhs_false_span(text, m_nv.start(1), m_nv.end(1)):
            return False
        sep = m_nv.end()
        if sep != body_hi and not _LEAN4_CONFIG_AFTER_COMMA_RE.match(text, sep, body_hi):
            return False
    return True


def _has_lean4_decide_native_escape(cleaned: str) -> bool:
    n = len(cleaned)
    match_rparen: dict[int, int] = {}
    stack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "(":
            stack.append(idx)
        elif ch == ")" and stack:
            match_rparen[stack.pop()] = idx

    for m_dec in _LEAN4_DECIDE_KW_RE.finditer(cleaned):
        pos = m_dec.end()
        while True:
            ws = pos
            while ws != n and cleaned[ws].isspace():
                ws += 1
            if ws == n:
                break
            ch = cleaned[ws]
            if ch in "+-":
                m_flag = _LEAN4_FLAG_TOK_RE.match(cleaned, ws)
                if m_flag is None:
                    break
                if m_flag.group(0) == "+native":
                    return True
                pos = m_flag.end()
                continue
            if ch == "(":
                close_idx = match_rparen.get(ws)
                if close_idx is None:
                    break
                m_pfx = _LEAN4_OPT_PREFIX_RE.match(cleaned, ws + 1, close_idx)
                if m_pfx is None:
                    break
                opt_key = m_pfx.group(1)
                rhs_lo = m_pfx.end()
                if opt_key == "native":
                    if not _is_lean4_native_rhs_false_span(cleaned, rhs_lo, close_idx):
                        return True
                elif opt_key == "config":
                    if not _is_lean4_safe_config_span(cleaned, rhs_lo, close_idx, match_rparen):
                        return True
                pos = close_idx + 1
                continue
            break
    return False


def scan_lean4_source(source: str) -> list[str]:
    cleaned = _strip_lean4_comments_and_strings(source)
    cleaned = _LEAN4_GUILLEMET_RE.sub(r"\1", cleaned)
    findings: list[str] = []
    for rx, code in _LEAN4_HARD_RULES:
        if rx.search(cleaned) is not None:
            findings.append(code)
    if _has_lean4_decide_native_escape(cleaned):
        findings.append("LEAN4_DECIDE_NATIVE")
    for m_bind in _LEAN4_DECIDE_CONFIG_BIND_RE.finditer(cleaned):
        if any(
            grp is not None and not _is_lean4_native_rhs_false_span(grp, 0, len(grp))
            for grp in m_bind.groups()
        ):
            findings.append("LEAN4_DECIDE_CONFIG_BIND")
            break
    return findings


def _parse_verdict_witness_fields(
    source: str, expected_obs: dict[str, int], obs_name: str = "obs"
) -> None:
    cleaned = _strip_lean4_comments_and_strings(source)
    all_defs = re.findall(rf"\bdef\s+{re.escape(obs_name)}\b", cleaned)
    obs_matches = re.findall(
        rf"\bdef\s+{re.escape(obs_name)}\b(?:\s*:\s*[A-Za-z0-9_.]+)?\s*:=\s*\{{([^}}{{]*)\}}",
        cleaned,
        re.DOTALL,
    )
    if len(all_defs) != 1 or len(obs_matches) != 1:
        raise AuditError("WITNESS_ANCHOR_INVALID", f"expected unique def {obs_name} record")
    found: dict[str, int] = {}
    for m in _LEAN4_WITNESS_FIELD_RE.finditer(obs_matches[0]):
        k, raw_num = m.group(1), m.group(2)
        if len(raw_num) > 64:
            raise AuditError("WITNESS_INT_TOO_LONG", f"witness integer {k} exceeds 64 chars")
        v = int(raw_num)
        if k in found:
            raise AuditError("WITNESS_DUPLICATE_FIELD", f"duplicate witness field {k}")
        found[k] = v
    if found != expected_obs:
        raise AuditError("WITNESS_PARITY_MISMATCH", "Lean Verdict obs witness does not match telemetry")


def _resolve_lean_bin() -> str:
    which = shutil.which("lean")
    if which:
        return which
    cand = Path.home() / ".local" / "bin" / "lean"
    if cand.is_file():
        return str(cand)
    raise AuditError("LEAN_NOT_FOUND", "Lean 4 binary not found in PATH or ~/.local/bin/lean")


def verify_lean4_module_live(lean_path: Path, expected_theorems: int) -> dict[str, Any]:
    lean_bin = _resolve_lean_bin()
    try:
        proc = subprocess.run(
            [lean_bin, str(lean_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuditError("LEAN4_EXEC_ERROR", f"failed executing lean on {lean_path.name}: {exc}") from exc
    if proc.returncode != 0 or proc.stderr.strip():
        raise AuditError(
            "LEAN4_VERIFY_FAILED",
            f"{lean_path.name} failed rc={proc.returncode} stderr={proc.stderr[:200]}",
        )
    axioms_by_thm: dict[str, list[str]] = {}
    pos = 0
    for m in _LEAN4_AXIOM_ENTRY_RE.finditer(proc.stdout):
        if proc.stdout[pos : m.start()].strip():
            raise AuditError("LEAN4_UNEXPECTED_OUTPUT", f"{lean_path.name} emitted non-axiom stdout")
        pos = m.end()
        if m.group(1) is not None:
            thm = m.group(1)
            ax_list = [tok.strip() for tok in m.group(2).split(",") if tok.strip()]
            if len(ax_list) != len(set(ax_list)):
                raise AuditError("LEAN4_DUPLICATE_AXIOM", f"{thm} has duplicate axioms")
            for ax in ax_list:
                if ax not in STANDARD_LEAN4_AXIOMS:
                    raise AuditError("LEAN4_NONSTANDARD_AXIOM", f"{thm} uses non-standard axiom {ax}")
            axioms = sorted(ax_list)
        else:
            thm = m.group(3)
            axioms = []
        if thm in axioms_by_thm:
            raise AuditError("LEAN4_DUPLICATE_THEOREM", f"duplicate #print axioms for {thm}")
        axioms_by_thm[thm] = axioms
    if proc.stdout[pos:].strip():
        raise AuditError("LEAN4_UNEXPECTED_OUTPUT", f"{lean_path.name} emitted trailing stdout")
    if len(axioms_by_thm) != expected_theorems:
        raise AuditError(
            "LEAN4_THEOREM_COUNT_MISMATCH",
            f"{lean_path.name}: expected {expected_theorems} theorems, got {len(axioms_by_thm)}",
        )
    expected_names = EXPECTED_LEAN_THEOREMS.get(lean_path.name)
    if expected_names is not None and set(axioms_by_thm.keys()) != expected_names:
        raise AuditError("LEAN4_THEOREM_NAME_MISMATCH", f"{lean_path.name} theorem names mismatch")
    return {
        "module": lean_path.name,
        "theorem_count": len(axioms_by_thm),
        "theorems": axioms_by_thm,
        "warnings": 0,
    }


def _check_mlos_receipt_bytes(raw: bytes, label: str) -> dict[str, Any]:
    text = _decode_utf8_strict(raw, label)
    home_prefix = "/" + "home/"
    if home_prefix in text:
        raise AuditError("HOME_PATH_LEAK", f"personal home path leak in {label}")
    try:
        obj = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_pairs_hook,
        )
    except AuditError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise AuditError("INVALID_JSON", f"malformed JSON in {label}") from exc
    if type(obj) is not dict:
        raise AuditError("MLOS_SCHEMA_BAD", f"{label} root must be object")
    if obj.get("schema") != "mlos-run-receipt/v0.1":
        raise AuditError("MLOS_SCHEMA_BAD", f"{label} wrong mlos schema")
    if obj.get("clean_hardware_run") is not True:
        raise AuditError("MLOS_NOT_CLEAN", f"{label} clean_hardware_run is not True")
    if obj.get("determinism_zone") != "B":
        raise AuditError("MLOS_BAD_ZONE", f"{label} determinism_zone != B")
    if obj.get("anomalies") != []:
        raise AuditError("MLOS_ANOMALIES", f"{label} has anomalies")
    if obj.get("profile_id") != "ux582hs-rtx3080-8gb":
        raise AuditError("MLOS_BAD_PROFILE", f"{label} wrong profile_id")
    exe = obj.get("execution")
    if type(exe) is not dict or type(exe.get("exit_code")) is not int or exe["exit_code"] != 0:
        raise AuditError("MLOS_NONZERO_EXIT", f"{label} execution.exit_code != 0")
    rsha = obj.get("receipt_sha256")
    if type(rsha) is not str or not _HEX64_RE.match(rsha):
        raise AuditError("MLOS_BAD_SHA", f"{label} invalid receipt_sha256")
    return {
        "file": label,
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "receipt_sha256": rsha,
        "clean_hardware_run": True,
        "determinism_zone": "B",
        "profile_id": "ux582hs-rtx3080-8gb",
        "exit_code": 0,
        "anomalies_count": 0,
    }


def _check_mlos_receipt(path: Path) -> dict[str, Any]:
    return _check_mlos_receipt_bytes(read_regular_file_strict(path), path.name)


def _compute_certificate_digest(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "certificate_sha256"}
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def build_certificate(track_dir: Path, run_live_lean: bool = True) -> dict[str, Any]:
    _require_exact_bool(run_live_lean, "run_live_lean")
    toolchain_raw = read_regular_file_strict(track_dir / "lean-toolchain")
    toolchain = _decode_utf8_strict(toolchain_raw, "lean-toolchain").strip()
    if toolchain != "leanprover/lean4:v4.36.0":
        raise AuditError("TOOLCHAIN_MISMATCH", f"unexpected lean-toolchain: {toolchain}")

    artifact_bytes: dict[str, bytes] = {"lean-toolchain": toolchain_raw}
    artifact_hashes: dict[str, str] = {
        "lean-toolchain": hashlib.sha256(toolchain_raw).hexdigest()
    }
    for rel in ARTIFACT_FILES:
        if rel == "lean-toolchain":
            continue
        raw = read_regular_file_strict(track_dir / rel)
        artifact_bytes[rel] = raw
        artifact_hashes[rel] = hashlib.sha256(raw).hexdigest()

    summary = compute_ceer_summary(track_dir, preloaded_bytes=artifact_bytes)

    mlos_receipts = [
        _check_mlos_receipt_bytes(
            artifact_bytes[f"mlos_cycle{cid}_receipt.json"],
            f"mlos_cycle{cid}_receipt.json",
        )
        for cid in (0, 1, 2)
    ]

    verdict_obs_by_rel = {
        "CEERSiliconCerts/CEER_Cycle0_Verdict.lean": ("obs0", summary["cycle_0"]["obs"]),
        "CEERSiliconCerts/CEER_Cycle1_Verdict.lean": ("obs1", summary["cycle_1"]["obs"]),
        "CEERSiliconCerts/CEER_Cycle2_Verdict.lean": ("obs2", summary["cycle_2"]["obs"]),
    }
    lean_results: list[dict[str, Any]] = []
    for rel, exp_count in LEAN_MODULES:
        p = track_dir / rel
        src = _decode_utf8_strict(artifact_bytes[rel], rel)
        findings = scan_lean4_source(src)
        if findings:
            raise AuditError("LEAN4_STATIC_FINDING", f"{rel}: {findings}")
        if rel in verdict_obs_by_rel:
            obs_name, exp_obs = verdict_obs_by_rel[rel]
            _parse_verdict_witness_fields(src, exp_obs, obs_name=obs_name)
        if run_live_lean:
            lean_results.append(verify_lean4_module_live(p, exp_count))
        else:
            lean_results.append(
                {"module": p.name, "theorem_count": exp_count, "theorems": {}, "warnings": 0}
            )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "track_id": "track-s62-ceer-lean4-silicon-recursion",
        "toolchain": toolchain,
        "artifact_sha256": artifact_hashes,
        "mlos_receipts": mlos_receipts,
        "lean4_verification": {
            "pure_init_zero_mathlib": True,
            "static_findings": 0,
            "witness_telemetry_parity": True,
            "axioms_subset_standard": True,
            "total_modules": len(LEAN_MODULES),
            "total_theorems": sum(r["theorem_count"] for r in lean_results),
            "modules": lean_results,
        },
        "ceer_summary": summary,
    }
    payload["certificate_sha256"] = _compute_certificate_digest(payload)
    _validate_json_tree(payload)
    return payload


_MLOS_REC_KEYS = frozenset(
    {"file", "file_sha256", "receipt_sha256", "clean_hardware_run", "determinism_zone", "profile_id", "exit_code", "anomalies_count"}
)
_LEAN_BLOCK_KEYS = frozenset(
    {"pure_init_zero_mathlib", "static_findings", "witness_telemetry_parity", "axioms_subset_standard", "total_modules", "total_theorems", "modules"}
)
_LEAN_MOD_KEYS = frozenset({"module", "theorem_count", "theorems", "warnings"})
_CEER_SUM_KEYS = frozenset({"disjoint_held_out_levers", "cryptographic_chain", "cycle_0", "cycle_1", "cycle_2", "epistemic_trajectory"})
_DISJOINT_KEYS = frozenset(
    {"pairwise_disjoint_cores", "pairwise_disjoint_pairs", "pairwise_disjoint_bytes", "pairwise_distinct_ramps",
     "total_distinct_core_counts", "total_distinct_spatial_pairs", "total_distinct_memory_footprints"}
)
_TRAJ_KEYS = frozenset({"corroborated_clean_by_cycle", "strictly_monotone"})
_C0_POS = frozenset({"pkgMwP1", "pkgMwP2", "pkgMwP4", "pkgMwP8", "opsP1", "opsP8", "pkgUj16k", "ops16k", "pkgUj64m", "ops64m"})
_C0_OBS_KEYS = _C0_POS | frozenset(
    {"darkMw16k", "darkMw64m", "pkgDarkMw16k", "pkgDarkMw64m", "adjInactRiseMc", "distInactRiseMc",
     "twiceFanHystArea", "rpmUpMean", "rpmDownMean", "tempUpMeanMc", "tempDownMeanMc", "twiceThermalLoadArea"}
)
_C1_POS = frozenset({"pkgMwP3", "pkgMwP6", "pkgUjP3", "pkgUjP6", "opsP3", "opsP6", "pkgUj8m", "ops8m", "pkgUj32m", "ops32m"})
_C1_OBS_KEYS = _C1_POS | frozenset(
    {"pkgDarkMw8m", "pkgDarkMw32m", "contrast23Mc", "contrast27Mc", "interiorMinusEdgeMc",
     "twiceThermalLoadArea", "tempUpMeanMc", "tempDownMeanMc"}
)
_C2_POS = frozenset(
    {"pkgMwP5", "pkgMwP7", "pkgUjP5", "pkgUjP7", "opsP5", "opsP7", "freqKhzP5", "freqKhzP7",
     "pkgUj512k", "ops512k", "pkgUj12m", "ops12m", "pkgUj48m", "ops48m", "syy", "suu", "svvSoak", "svvSpread"}
)
_C2_OBS_KEYS = _C2_POS | frozenset(
    {"pkgDarkMw512k", "pkgDarkMw12m", "pkgDarkMw48m", "contrast45Mc", "contrast16Mc",
     "twiceThermalLoadArea", "syu", "suvSoak", "syvSoak", "suvSpread", "syvSpread"}
)


def _req_exact_dict(obj: Any, expected_keys: frozenset[str], code: str) -> dict[str, Any]:
    if type(obj) is not dict or set(obj.keys()) != expected_keys:
        raise AuditError(code, f"dict key set mismatch ({code})")
    return obj


def _req_int_dict(
    obj: Any, expected_keys: frozenset[str], pos_keys: frozenset[str], code: str
) -> dict[str, int]:
    d = _req_exact_dict(obj, expected_keys, code)
    for k, v in d.items():
        if type(v) is not int:
            raise AuditError(code, f"non-int obs field {k}")
        if k in pos_keys and v <= 0:
            raise AuditError(code, f"non-positive obs field {k}")
    return d


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Independent pure-Z/Q verifier callable directly on an untrusted payload dict."""
    _validate_json_tree(payload)
    if type(payload) is not dict:
        raise AuditError("ROOT_NOT_OBJECT", "payload must be exact dict")
    _req_exact_dict(payload, EXPECTED_TOP_KEYS, "KEY_SET_MISMATCH")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise AuditError("SCHEMA_MISMATCH", "wrong schema_version")
    if payload["track_id"] != "track-s62-ceer-lean4-silicon-recursion":
        raise AuditError("TRACK_ID_MISMATCH", "wrong track_id")
    if payload["toolchain"] != "leanprover/lean4:v4.36.0":
        raise AuditError("TOOLCHAIN_MISMATCH", "wrong toolchain")

    cert_sha = payload["certificate_sha256"]
    if type(cert_sha) is not str or not _HEX64_RE.match(cert_sha):
        raise AuditError("BAD_CERT_SHA", "invalid certificate_sha256 format")
    if not hmac.compare_digest(cert_sha, _compute_certificate_digest(payload)):
        raise AuditError("CERT_SHA_MISMATCH", "certificate_sha256 digest mismatch")

    ah = _req_exact_dict(payload["artifact_sha256"], frozenset(ARTIFACT_FILES), "ARTIFACT_MAP_MISMATCH")
    for k, v in ah.items():
        if type(v) is not str or not _HEX64_RE.match(v):
            raise AuditError("BAD_ARTIFACT_SHA", f"invalid sha256 for {k}")

    mlos_list = payload["mlos_receipts"]
    if type(mlos_list) is not list or len(mlos_list) != 3:
        raise AuditError("BAD_MLOS_LIST", "expected 3 mlos receipts")
    for cid, rec_raw in enumerate(mlos_list):
        rec = _req_exact_dict(rec_raw, _MLOS_REC_KEYS, "MLOS_RECEIPT_INVALID")
        exp_fname = f"mlos_cycle{cid}_receipt.json"
        if (
            rec["file"] != exp_fname
            or rec["file_sha256"] != ah[exp_fname]
            or type(rec["receipt_sha256"]) is not str
            or not _HEX64_RE.match(rec["receipt_sha256"])
            or rec["clean_hardware_run"] is not True
            or rec["determinism_zone"] != "B"
            or rec["profile_id"] != "ux582hs-rtx3080-8gb"
            or type(rec["exit_code"]) is not int
            or rec["exit_code"] != 0
            or type(rec["anomalies_count"]) is not int
            or rec["anomalies_count"] != 0
        ):
            raise AuditError("MLOS_RECEIPT_INVALID", f"invalid mlos receipt for cycle {cid}")

    lv = _req_exact_dict(payload["lean4_verification"], _LEAN_BLOCK_KEYS, "LEAN4_BLOCK_INVALID")
    mods = lv["modules"]
    if (
        lv["pure_init_zero_mathlib"] is not True
        or type(lv["static_findings"]) is not int
        or lv["static_findings"] != 0
        or lv["witness_telemetry_parity"] is not True
        or lv["axioms_subset_standard"] is not True
        or lv["total_modules"] != 6
        or lv["total_theorems"] != 36
        or type(mods) is not list
        or len(mods) != 6
    ):
        raise AuditError("LEAN4_BLOCK_INVALID", "invalid lean4_verification summary")
    for mod_raw, (rel, exp_cnt) in zip(mods, LEAN_MODULES):
        mod = _req_exact_dict(mod_raw, _LEAN_MOD_KEYS, "LEAN4_BLOCK_INVALID")
        mod_name = Path(rel).name
        thms = mod["theorems"]
        if (
            mod["module"] != mod_name
            or mod["theorem_count"] != exp_cnt
            or type(mod["warnings"]) is not int
            or mod["warnings"] != 0
            or type(thms) is not dict
            or set(thms.keys()) != EXPECTED_LEAN_THEOREMS[mod_name]
        ):
            raise AuditError("LEAN4_BLOCK_INVALID", f"invalid lean module entry {rel}")
        for thm_name, ax_list in thms.items():
            if (
                type(ax_list) is not list
                or any(ax not in STANDARD_LEAN4_AXIOMS for ax in ax_list)
                or ax_list != sorted(set(ax_list))
            ):
                raise AuditError("LEAN4_BLOCK_INVALID", f"invalid axiom list in {rel}")
            if thm_name in EXPECTED_ZERO_AXIOM_THEOREMS and ax_list != []:
                raise AuditError("LEAN4_BLOCK_INVALID", f"expected zero axioms for {thm_name}")

    cs = _req_exact_dict(payload["ceer_summary"], _CEER_SUM_KEYS, "BAD_CEER_SUMMARY")
    dl = _req_exact_dict(cs["disjoint_held_out_levers"], _DISJOINT_KEYS, "LEVERS_NOT_DISJOINT")
    if (
        dl["pairwise_disjoint_cores"] is not True
        or dl["pairwise_disjoint_pairs"] is not True
        or dl["pairwise_disjoint_bytes"] is not True
        or dl["pairwise_distinct_ramps"] is not True
        or dl["total_distinct_core_counts"] != 8
        or dl["total_distinct_spatial_pairs"] != 6
        or dl["total_distinct_memory_footprints"] != 9
    ):
        raise AuditError("LEVERS_NOT_DISJOINT", "held-out levers not pairwise disjoint")

    expected_chain = {
        f"cycle_{cid}_{suffix}": ah[rel]
        for cid in (0, 1, 2)
        for suffix, rel in (
            ("prereg_sha256", f"cycle_{cid}_prereg.json"),
            ("telemetry_sha256", f"cycle_{cid}_telemetry.json"),
            ("theory_lean_sha256", f"CEERSiliconCerts/CEER_Cycle{cid}_Theory.lean"),
            ("verdict_lean_sha256", f"CEERSiliconCerts/CEER_Cycle{cid}_Verdict.lean"),
        )
    }
    if cs["cryptographic_chain"] != expected_chain:
        raise AuditError("CHAIN_BINDING_MISMATCH", "cryptographic_chain does not match artifact_sha256")

    c0 = _req_exact_dict(cs["cycle_0"], frozenset({"obs", "verdicts"}), "C0_MATH_MISMATCH")
    c1 = _req_exact_dict(cs["cycle_1"], frozenset({"obs", "verdicts"}), "C1_MATH_MISMATCH")
    c2 = _req_exact_dict(cs["cycle_2"], frozenset({"obs", "schur_soak", "schur_spread", "verdicts"}), "C2_MATH_MISMATCH")

    c0_obs = _req_int_dict(c0["obs"], _C0_OBS_KEYS, _C0_POS, "C0_MATH_MISMATCH")
    c1_obs = _req_int_dict(c1["obs"], _C1_OBS_KEYS, _C1_POS, "C1_MATH_MISMATCH")
    c2_obs = _req_int_dict(c2["obs"], _C2_OBS_KEYS, _C2_POS, "C2_MATH_MISMATCH")

    cliff0 = Fraction(c0_obs["pkgUj64m"] * c0_obs["ops16k"], c0_obs["pkgUj16k"] * c0_obs["ops64m"])
    exp_v0 = {
        "H0a_raw": True,
        "H0a_degenerate_pl1": True,
        "H0b": False,
        "H0c": False,
        "H0d_fan_plateau": True,
        "H0d_thermal_lag_obstructed": True,
        "corroborated_clean": 0,
        "falsified_or_obstructed": 4,
        "cliff_16k_to_64m_fraction": [cliff0.numerator, cliff0.denominator],
        "cliff_16k_to_64m_100x": (100 * cliff0.numerator) // cliff0.denominator,
    }
    c0_checks = (
        canonical_json_bytes(c0["verdicts"]) == canonical_json_bytes(exp_v0),
        3 * (c0_obs["pkgMwP8"] - c0_obs["pkgMwP4"]) >= 4 * (c0_obs["pkgMwP4"] - c0_obs["pkgMwP1"]),
        abs(c0_obs["pkgMwP8"] - c0_obs["pkgMwP1"]) <= 200,
        c0_obs["opsP8"] >= 7 * c0_obs["opsP1"],
        c0_obs["pkgUj64m"] * c0_obs["ops16k"] > 80 * c0_obs["pkgUj16k"] * c0_obs["ops64m"],
        abs(c0_obs["adjInactRiseMc"] - c0_obs["distInactRiseMc"]) > 500,
        c0_obs["twiceFanHystArea"] == 0,
        abs(c0_obs["rpmDownMean"] - c0_obs["rpmUpMean"]) <= 50,
        c0_obs["tempDownMeanMc"] - c0_obs["tempUpMeanMc"] > 1000,
        c0_obs["twiceThermalLoadArea"] != 0,
        c0_obs["pkgDarkMw16k"] > 4000,
        c0_obs["pkgDarkMw64m"] > 4000,
        c0_obs["darkMw16k"] < 0,
    )
    if not all(c0_checks):
        raise AuditError("C0_MATH_MISMATCH", "Cycle 0 mathematical invariants violated")

    exp_v1 = {
        "H1a": True,
        "H1b": False,
        "H1c": True,
        "H1d": False,
        "corroborated_clean": 2,
        "falsified_or_obstructed": 2,
        "eff_p3_to_p6_100x": (100 * c1_obs["opsP6"] * c1_obs["pkgUjP3"]) // (c1_obs["opsP3"] * c1_obs["pkgUjP6"]),
        "cliff_8m_to_32m_100x": (100 * c1_obs["pkgUj32m"] * c1_obs["ops8m"]) // (c1_obs["pkgUj8m"] * c1_obs["ops32m"]),
    }
    c1_checks = (
        canonical_json_bytes(c1["verdicts"]) == canonical_json_bytes(exp_v1),
        20 * abs(c1_obs["pkgMwP6"] - c1_obs["pkgMwP3"]) <= c1_obs["pkgMwP3"],
        10 * c1_obs["opsP6"] * c1_obs["pkgUjP3"] >= 16 * c1_obs["opsP3"] * c1_obs["pkgUjP6"],
        2 * c1_obs["pkgUj32m"] * c1_obs["ops8m"] < 3 * c1_obs["pkgUj8m"] * c1_obs["ops32m"],
        c1_obs["pkgDarkMw8m"] > 4000,
        c1_obs["pkgDarkMw32m"] > 4000,
        c1_obs["contrast23Mc"] > c1_obs["contrast27Mc"],
        c1_obs["interiorMinusEdgeMc"] > 1500,
        c1_obs["tempDownMeanMc"] < c1_obs["tempUpMeanMc"],
        c1_obs["twiceThermalLoadArea"] > 30000,
    )
    if not all(c1_checks):
        raise AuditError("C1_MATH_MISMATCH", "Cycle 1 mathematical invariants violated")

    schur1 = exact_schur_3x3(
        c2_obs["syy"], c2_obs["suu"], c2_obs["svvSoak"],
        c2_obs["syu"], c2_obs["syvSoak"], c2_obs["suvSoak"],
    )
    schur2 = exact_schur_3x3(
        c2_obs["syy"], c2_obs["suu"], c2_obs["svvSpread"],
        c2_obs["syu"], c2_obs["syvSpread"], c2_obs["suvSpread"],
    )
    if not all((
        schur1["identity_residual"] == 0,
        schur2["identity_residual"] == 0,
        canonical_json_bytes(schur1) == canonical_json_bytes(c2["schur_soak"]),
        canonical_json_bytes(schur2) == canonical_json_bytes(c2["schur_spread"]),
    )):
        raise AuditError("C2_SCHUR_MISMATCH", "Cycle 2 Schur complement recomputation mismatch")

    exp_v2 = {
        "H2a": True,
        "H2b_full": False,
        "H2b_primary_cliff_and_dark": True,
        "H2b_tail_12m_to_48m": False,
        "H2c": True,
        "H2d": True,
        "corroborated_clean": 3,
        "falsified_or_obstructed": 1,
        "eff_raw_100x": (100 * c2_obs["opsP7"] * c2_obs["pkgUjP5"]) // (c2_obs["opsP5"] * c2_obs["pkgUjP7"]),
        "eff_freq_100x": (100 * c2_obs["opsP7"] * c2_obs["pkgUjP5"] * c2_obs["freqKhzP5"])
        // (c2_obs["opsP5"] * c2_obs["pkgUjP7"] * c2_obs["freqKhzP7"]),
        "cliff_512k_to_48m_100x": (100 * c2_obs["pkgUj48m"] * c2_obs["ops512k"]) // (c2_obs["pkgUj512k"] * c2_obs["ops48m"]),
        "cliff_512k_to_12m_100x": (100 * c2_obs["pkgUj12m"] * c2_obs["ops512k"]) // (c2_obs["pkgUj512k"] * c2_obs["ops12m"]),
        "cliff_12m_to_48m_100x": (100 * c2_obs["pkgUj48m"] * c2_obs["ops12m"]) // (c2_obs["pkgUj12m"] * c2_obs["ops48m"]),
    }
    c2_checks = (
        canonical_json_bytes(c2["verdicts"]) == canonical_json_bytes(exp_v2),
        20 * abs(c2_obs["pkgMwP7"] - c2_obs["pkgMwP5"]) <= c2_obs["pkgMwP5"],
        100 * c2_obs["opsP7"] * c2_obs["pkgUjP5"] >= 125 * c2_obs["opsP5"] * c2_obs["pkgUjP7"],
        100 * c2_obs["opsP7"] * c2_obs["pkgUjP5"] * c2_obs["freqKhzP5"]
        >= 120 * c2_obs["opsP5"] * c2_obs["pkgUjP7"] * c2_obs["freqKhzP7"],
        c2_obs["pkgUj48m"] * c2_obs["ops512k"] >= 24 * c2_obs["pkgUj512k"] * c2_obs["ops48m"],
        c2_obs["pkgUj12m"] * c2_obs["ops512k"] >= 25 * c2_obs["pkgUj512k"] * c2_obs["ops12m"],
        10 * c2_obs["pkgUj48m"] * c2_obs["ops12m"] < 11 * c2_obs["pkgUj12m"] * c2_obs["ops48m"],
        c2_obs["pkgDarkMw512k"] > 4400,
        c2_obs["pkgDarkMw12m"] > 4400,
        c2_obs["pkgDarkMw48m"] > 4400,
        c2_obs["contrast45Mc"] > 0,
        c2_obs["contrast16Mc"] < 0,
        c2_obs["contrast45Mc"] - c2_obs["contrast16Mc"] > 10000,
        c2_obs["twiceThermalLoadArea"] != 0,
        100 * schur1["delta"] * schur1["delta"] >= 23 * schur1["r1_num"] * schur1["det_a"],
        100 * schur2["delta"] * schur2["delta"] >= 62 * schur2["r1_num"] * schur2["det_a"],
    )
    if not all(c2_checks):
        raise AuditError("C2_MATH_MISMATCH", "Cycle 2 mathematical invariants violated")

    traj = _req_exact_dict(cs["epistemic_trajectory"], _TRAJ_KEYS, "TRAJECTORY_MISMATCH")
    if canonical_json_bytes(traj) != canonical_json_bytes({"corroborated_clean_by_cycle": [0, 2, 3], "strictly_monotone": True}):
        raise AuditError("TRAJECTORY_MISMATCH", "epistemic trajectory mismatch")

    return {
        "secondary_audit_ok": True,
        "certificate_sha256": cert_sha,
        "corroborated_clean_by_cycle": [0, 2, 3],
        "schur_soak_bps": schur1["variance_reduction_bps"],
        "schur_spread_bps": schur2["variance_reduction_bps"],
    }


def validate_certificate_payload(
    payload: Any,
    track_dir: Path | None = None,
    run_live_lean: bool = True,
) -> dict[str, Any]:
    """Primary fail-closed validator (supports both offline FR0 and full-recompute FR1)."""
    _require_exact_bool(run_live_lean, "run_live_lean")
    sec = secondary_audit_payload(payload)
    if track_dir is not None:
        fresh = build_certificate(track_dir, run_live_lean=run_live_lean)
        if not run_live_lean:
            # Compare everything except detailed live theorem maps when run_live_lean=False
            for key in ("toolchain", "artifact_sha256", "mlos_receipts", "ceer_summary"):
                if payload[key] != fresh[key]:
                    raise AuditError("FRESH_RECOMPUTE_MISMATCH", f"recomputed {key} mismatch")
        elif payload != fresh:
            raise AuditError("FRESH_CERT_MISMATCH", "certificate does not match live recomputation")
    return sec


def main(argv: list[str] | None = None) -> int:
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        if not args or args == ["--standalone", "--json"]:
            cert = build_certificate(_TRACK_DIR, run_live_lean=True)
            secondary_audit_payload(cert)
            sys.stdout.write(canonical_json_bytes(cert).decode("utf-8") + "\n")
            return 0
        if len(args) == 2 and args[0] == "--write":
            out_path = _check_cli_path_arg(args[1])
            cert = build_certificate(_TRACK_DIR, run_live_lean=True)
            secondary_audit_payload(cert)
            write_atomic_0600(out_path, canonical_json_bytes(cert) + b"\n")
            sys.stdout.write(
                canonical_json_bytes(
                    {"written": out_path.name, "certificate_sha256": cert["certificate_sha256"]}
                ).decode("utf-8")
                + "\n"
            )
            return 0
        if len(args) == 2 and args[0] == "--check":
            in_path = _check_cli_path_arg(args[1])
            raw = read_regular_file_strict(in_path)
            payload = parse_strict_json_bytes(raw)
            res = validate_certificate_payload(payload, track_dir=_TRACK_DIR, run_live_lean=True)
            sys.stdout.write(canonical_json_bytes(res).decode("utf-8") + "\n")
            return 0
        raise AuditError(
            "BAD_CLI_ARGS",
            "usage: ceer_silicon_audit.py (--standalone --json | --write <path> | --check <path>)",
        )
    except (AuditError, OracleError, OSError, KeyError, TypeError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        sys.stderr.write(f"AUDIT_FAIL [{code}]: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
