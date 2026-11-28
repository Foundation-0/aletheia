"""
`trust_core.py`: Track S168 (EXP-Q56a) Pre-Certified Drop-In Trust Kernel.

Eliminates repeated per-track Zone-B OS-descriptor I/O, strict JSON equality,
empirical provenance binding, isolated Lean 4.36.0 static+live verification,
and fail-closed CLI boilerplate across Aletheia research tracks.

Stdlib-only, zero bare asserts, zero floats on trust paths, 3x -I bit-identical.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Callable, Mapping, Sequence

__all__ = [
    "MAX_FILE_BYTES",
    "MAX_JSON_DEPTH",
    "MAX_JSON_INT_DIGITS",
    "STANDARD_LEAN4_AXIOMS",
    "PURE_INIT_AXIOMS",
    "TrustCoreError",
    "require_tc",
    "canonical_json_bytes",
    "sha256_bytes",
    "strict_json_equal",
    "strict_read_bytes_nofollow",
    "parse_strict_json_bytes",
    "strict_load_json_nofollow",
    "atomic_write_json_nofollow",
    "bind_empirical_artifact",
    "strip_lean4_comments_and_literals",
    "audit_lean4_source_static",
    "extract_lean4_theorems",
    "audit_lakefile_bytes",
    "resolve_verified_lean_bins",
    "run_isolated_live_lean",
    "StrictArgumentParser",
    "make_strict_parser",
    "run_fail_closed_cli",
]

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_JSON_INT_DIGITS = 1024
_READ_CHUNK_BYTES = 65536

STANDARD_LEAN4_AXIOMS: frozenset[str] = frozenset({"propext", "Classical.choice", "Quot.sound"})
PURE_INIT_AXIOMS: frozenset[str] = frozenset({"propext", "Quot.sound"})
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

# Strict allowlist of genuine Lean 4.36.0 Init-reserved interpolation prefixes (`s!`, `f!`, `println!`).
# All other prefixes (`m!`, `v!`, `throwError`, `dbg_trace`, `log*`, arg macros, arbitrary `<ident>!`)
# can take plain strings in pure-Init / tactic mode: primary pass lexes them as plain strings and
# rejects `{`/`}`, while dual-projection also scans under interpolated-string expansion (closes HIGH-1).
_INIT_RESERVED_INTERP_BANGS: frozenset[str] = frozenset({"s!", "f!", "println!"})
_AMBIG_INTERP_PLAINS: tuple[str, ...] = ("dbg_trace", "throwError", "logInfo", "logError", "logWarning")
_INTERP_ARG_MACROS: tuple[tuple[str, int, bool], ...] = (
    ("Macro.trace[", 1, True),
    ("trace_goal[", 1, True),
    ("trace[", 1, True),
    ("throwNamedErrorAt", 2, False),
    ("logNamedErrorAt", 2, False),
    ("logNamedWarningAt", 2, False),
    ("throwErrorAt", 1, False),
    ("logInfoAt", 1, False),
    ("logWarningAt", 1, False),
    ("logErrorAt", 1, False),
    ("logAt", 1, False),
    ("throwNamedError", 1, False),
    ("logNamedError", 1, False),
    ("logNamedWarning", 1, False),
)

_ROOT_NS_PREFIX_RE = re.compile(r"(?<![A-Za-z0-9_'.])(?:_root_\s*\.\s*)+")
_SOURCE_ESCAPE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<![A-Za-z0-9_'.])sorry(?![A-Za-z0-9_'])"), "LEAN4_SORRY"),
    (re.compile(r"(?<![A-Za-z0-9_'.])admit(?![A-Za-z0-9_'])"), "LEAN4_ADMIT"),
    (re.compile(r"(?<![A-Za-z0-9_'.])stop(?![A-Za-z0-9_'])"), "LEAN4_STOP_TACTIC"),
    (re.compile(r"(?<![A-Za-z0-9_'.])axiom(?![A-Za-z0-9_'])"), "LEAN4_AXIOM"),
    (re.compile(r"(?<![A-Za-z0-9_'.])unsafe(?![A-Za-z0-9_'])"), "LEAN4_UNSAFE"),
    (re.compile(r"(?<![A-Za-z0-9_'.])opaque(?![A-Za-z0-9_'])"), "LEAN4_OPAQUE_DECL"),
    (re.compile(r"(?<![A-Za-z0-9_'.])native_decide(?![A-Za-z0-9_'])"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"(?:^|[\s;(])\+native(?![A-Za-z0-9_'])"), "LEAN4_DECIDE_NATIVE"),
    (re.compile(r"(?<![A-Za-z0-9_'.])(?:bv_decide|bv_check)(?![A-Za-z0-9_'])"), "LEAN4_BV_DECIDE"),
    (re.compile(r"(?<![A-Za-z0-9_'])sorryAx(?![A-Za-z0-9_'])"), "LEAN4_SORRY_AX"),
    (re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*Meta\s*\.\s*)?mkSorry(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_MK_SORRY"),
    (re.compile(r"(?<![A-Za-z0-9_'.])Lean\s*\.\s*(?:Elab|Meta)(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_META_ESCAPE"),
    (re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?ofReduceBool(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?ofReduceNat(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?trustCompiler(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_TRUST_COMPILER"),
    (
        re.compile(
            r"(?<![A-Za-z0-9_'])debug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)(?![A-Za-z0-9_'])",
            re.DOTALL,
        ),
        "LEAN4_DEBUG_ESCAPE",
    ),
    (
        re.compile(
            r"(?<![A-Za-z0-9_'.])(?:run_cmd|run_meta|run_tac|run_elab|by_elab|initialize|builtin_initialize)(?![A-Za-z0-9_'])"
        ),
        "LEAN4_META_ESCAPE",
    ),
    (
        re.compile(
            r"(?<![A-Za-z0-9_'.])(?:syntax|macro|macro_rules|elab|elab_rules|declare_syntax_cat|infix[lr]?|prefix|postfix|notation)(?![A-Za-z0-9_'])"
        ),
        "LEAN4_SYNTAX_MACRO_ESCAPE",
    ),
    (re.compile(r"#\s*(?:eval!?|reduce|exit|guard_msgs|check_failure)(?![A-Za-z0-9_'])"), "LEAN4_HASH_ESCAPE"),
    (
        re.compile(
            r"(?:@|(?<![A-Za-z0-9_'.])attribute\s*)\[[^\]]*(?<![A-Za-z0-9_'])(?:extern|implemented_by|export|init|builtin_init|macro|elab|tactic|default_instance)(?![A-Za-z0-9_'])",
            re.DOTALL,
        ),
        "LEAN4_ATTR_ESCAPE",
    ),
    (re.compile(r"(?:\.\s*)?_native\s*\.\s*[A-Za-z_][A-Za-z0-9_]*\s*\.\s*ax_[A-Za-z0-9_]*", re.DOTALL), "LEAN4_NATIVE_AXIOM"),
    (
        re.compile(
            r"(?<![A-Za-z0-9_'.])partial\s+(?:(?:private|protected|noncomputable|unsafe)\s+)*(?:def|instance|abbrev|theorem|lemma|opaque)(?![A-Za-z0-9_'])",
            re.DOTALL,
        ),
        "LEAN4_PARTIAL_DECL",
    ),
)
_INSTANCE_RE = re.compile(r"(?<![A-Za-z0-9_'.])instance(?![A-Za-z0-9_'])")
_DECIDE_WORD_RE = re.compile(r"(?<![A-Za-z0-9_'.])decide(?![A-Za-z0-9_'])")
_NATIVE_OR_CONFIG_RE = re.compile(r"(?<![A-Za-z0-9_'])(?:native|config)(?![A-Za-z0-9_'])")

_VAR_DECL_RE = re.compile(r"(?<![A-Za-z0-9_'.])variable(?![A-Za-z0-9_'])")
_INCLUDE_DECL_RE = re.compile(r"(?<![A-Za-z0-9_'.])include(?![A-Za-z0-9_'])")
_IMPORT_RE = re.compile(
    r"(?<![A-Za-z0-9_'.])((?:(?:public|private|meta)\s+)*)import\s+(?:all\s+)?([A-Za-z0-9_'\u0080-\uffff]+(?:\.[A-Za-z0-9_'\u0080-\uffff]+)*)"
)
_DECL_TOKEN_RE = re.compile(
    r"@\[[^\]]*\]|:=|[A-Za-z_][A-Za-z0-9_.']*|\S",
    re.DOTALL,
)
_ALLOWED_LAKE_TOP_KEYS = frozenset({"name", "version", "defaultTargets", "lean_lib"})
_ALLOWED_LEAN_LIB_KEYS = frozenset({"name", "srcDir", "roots", "globs"})
_LAKE_PKG_NAME_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_-]*\Z")
_LAKE_VERSION_RE = re.compile(r"\A[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?\Z")
_LAKE_GLOB_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\.\+|\.\*)?\Z")
_UNSAFE_LAKE_TOKENS: tuple[str, ...] = (
    "debug.byAsSorry",
    "debug.skipKernelTC",
    "debug.proofAsSorry",
    "debug.terminalTacticsAsSorry",
)
_SKIP_DIR_SEGMENTS = frozenset({".git", ".lake", ".venv", "venv", "node_modules", "__pycache__"})
_FORBIDDEN_AXIOM_RE = re.compile(
    r"\A(?:sorryAx|Lean\.ofReduceBool|ofReduceBool|Lean\.ofReduceNat|ofReduceNat|Lean\.trustCompiler|trustCompiler|_native\..*|.*\._native\..*)\Z"
)
_AXIOM_NONE_RE = re.compile(r"\A'([^']+)' does not depend on any axioms\Z")
_AXIOM_SOME_RE = re.compile(r"\A'([^']+)' depends on axioms: \[([^\]]*)\]\Z")
_MOD_IDENT_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
_TOOLCHAIN_RE = re.compile(r"\A[A-Za-z0-9_-]+/[A-Za-z0-9_-]+:v[0-9]+\.[0-9]+\.[0-9]+\Z")
_LEAN_WARN_RE = re.compile(r"(?:^|\s)warning(?:\s*\([^)]*\))?:", re.IGNORECASE)


class TrustCoreError(ValueError):
    """Fail-closed structured error raised across all trust_core operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class _StrictHelpSignal(Exception):
    """Internal signal raised by StrictArgumentParser on -h/--help for single-line JSON output."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__("HELP")


def require_tc(cond: bool, code: str, message: str) -> None:
    """Explicit non-assert guard (never stripped by `python3 -O`)."""
    if not cond:
        raise TrustCoreError(code, message)


def sha256_bytes(data: bytes) -> str:
    require_tc(type(data) is bytes, "INVALID_BYTES_TYPE", "sha256_bytes requires bytes")
    return hashlib.sha256(data).hexdigest()


def _validate_json_tree(
    value: Any,
    *,
    allow_float: bool,
    max_depth: int = MAX_JSON_DEPTH,
    max_int_digits: int = MAX_JSON_INT_DIGITS,
) -> None:
    int_limit = 10 ** max_int_digits
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if type(item) is str:
            for ch in item:
                code = ord(ch)
                require_tc(not (0xD800 <= code <= 0xDFFF), "JSON_LONE_SURROGATE", "lone surrogate in JSON string")
        elif type(item) is dict:
            require_tc(depth <= max_depth, "JSON_DEPTH_EXCEEDED", f"JSON depth > {max_depth}")
            for k, v in item.items():
                require_tc(type(k) is str, "JSON_NON_STRING_KEY", "JSON object keys must be str")
                stack.append((k, depth + 1))
                stack.append((v, depth + 1))
        elif type(item) is list:
            require_tc(depth <= max_depth, "JSON_DEPTH_EXCEEDED", f"JSON depth > {max_depth}")
            for sub in item:
                stack.append((sub, depth + 1))
        elif type(item) is int:
            require_tc(abs(item) < int_limit, "JSON_INT_TOO_LONG", f"int exceeds {max_int_digits} digits")
        elif type(item) is bool or item is None:
            continue
        elif type(item) is float:
            require_tc(allow_float, "JSON_FLOAT_FORBIDDEN", "float value forbidden on exact trust path")
            s = repr(item).lower()
            require_tc(s not in ("nan", "inf", "-inf"), "JSON_FLOAT_NOT_FINITE", f"non-finite float: {s}")
        else:
            raise TrustCoreError("JSON_UNSUPPORTED_TYPE", f"unsupported JSON type: {type(item).__name__}")


def canonical_json_bytes(obj: Any, *, allow_float: bool = False) -> bytes:
    """Serialize `obj` to canonical LF-terminated ASCII JSON bytes."""
    _validate_json_tree(obj, allow_float=allow_float)
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    return text.encode("utf-8")


def strict_json_equal(a: Any, b: Any) -> bool:
    """
    Recursive exact-type JSON equality (`type(a) is type(b)` at every key and value node).
    Permanently eliminates Python `True == 1`, `False == 0`, and `{1: x} == {True: x}` spoofs.
    """
    stack: list[tuple[Any, Any]] = [(a, b)]
    while stack:
        left, right = stack.pop()
        if type(left) is not type(right):
            return False
        if type(left) is dict:
            if len(left) != len(right):
                return False
            lt = {(type(k), k): v for k, v in left.items()}
            rt = {(type(k), k): v for k, v in right.items()}
            for tk, lv in lt.items():
                if tk not in rt:
                    return False
                stack.append((lv, rt[tk]))
        elif type(left) is list:
            if len(left) != len(right):
                return False
            for lv, rv in zip(left, right):
                stack.append((lv, rv))
        else:
            if left != right:
                return False
    return True


def _validate_path_segments(path: Any, label: str) -> tuple[str, tuple[str, ...]]:
    if type(path) is str:
        require_tc(len(path) > 0, "EMPTY_PATH", f"{label}: path is empty")
        p = Path(path)
    else:
        require_tc(isinstance(path, Path), "INVALID_PATH_TYPE", f"{label}: path must be str or Path")
        p = path
    raw = os.fspath(p)
    require_tc("\x00" not in raw, "NUL_IN_PATH", f"{label}: NUL byte forbidden in path")
    parts = p.parts
    require_tc(".." not in parts, "DOTDOT_PATH", f"{label}: '..' traversal forbidden")
    anchor = os.sep if p.is_absolute() else "."
    segs = parts[1:] if p.is_absolute() else parts
    require_tc(len(segs) >= 1, "PATH_NO_LEAF", f"{label}: path names no file")
    return anchor, segs


def _open_parent_dir_nofollow(path: Any, label: str) -> tuple[int, str]:
    anchor, segs = _validate_path_segments(path, label)
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    cur_fd = -1
    try:
        cur_fd = os.open(anchor, dir_flags)
        for seg in segs[:-1]:
            nxt_fd = os.open(seg, dir_flags, dir_fd=cur_fd)
            os.close(cur_fd)
            cur_fd = nxt_fd
        return cur_fd, segs[-1]
    except OSError as exc:
        if cur_fd >= 0:
            os.close(cur_fd)
        raise TrustCoreError("PARENT_OPEN_FAILED", f"{label}: {exc}") from exc


def _strict_read_bytes_and_stat_nofollow(
    path: str | Path,
    max_bytes: int = MAX_FILE_BYTES,
    *,
    label: str = "read",
) -> tuple[bytes, os.stat_result]:
    require_tc(type(max_bytes) is int and max_bytes >= 1, "INVALID_MAX_BYTES", "max_bytes must be positive int")
    parent_dfd, leaf = _open_parent_dir_nofollow(path, label)
    fd = -1
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_dfd)
            st = os.fstat(fd)
        except OSError as exc:
            raise TrustCoreError("READ_OPEN_FAILED", f"{label}: {exc}") from exc
        require_tc(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", f"{label}: not a regular file")
        require_tc(st.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked file forbidden (nlink={st.st_nlink})")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, _READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            require_tc(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: file exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks), st
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent_dfd)


def strict_read_bytes_nofollow(path: str | Path, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    """Read regular file bytes via `O_NOFOLLOW` ancestor walk, rejecting symlinks, FIFOs, and hardlinks."""
    raw, _ = _strict_read_bytes_and_stat_nofollow(path, max_bytes, label="strict_read_bytes")
    return raw


def parse_strict_json_bytes(
    raw: bytes,
    *,
    label: str = "json",
    allow_float: bool = False,
    require_trailing_lf: bool = True,
    max_depth: int = MAX_JSON_DEPTH,
    max_int_digits: int = MAX_JSON_INT_DIGITS,
) -> Any:
    """Strictly decode UTF-8 bytes (no BOM/CR/CRLF, trailing LF) and parse RFC-8259 JSON without duplicates/floats."""
    require_tc(type(raw) is bytes, "INVALID_BYTES_TYPE", f"{label}: expected bytes")
    require_tc(len(raw) > 0, "EMPTY_JSON", f"{label}: JSON bytes are empty")
    require_tc(not raw.startswith(b"\xef\xbb\xbf"), "JSON_BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    require_tc(b"\r" not in raw, "JSON_CRLF_FORBIDDEN", f"{label}: CR/CRLF forbidden")
    if require_trailing_lf:
        require_tc(raw.endswith(b"\n"), "JSON_NO_TRAILING_LF", f"{label}: trailing LF required")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TrustCoreError("INVALID_UTF8", f"{label}: invalid UTF-8: {exc}") from exc
    require_tc(len(text.strip()) > 0, "EMPTY_JSON", f"{label}: JSON text is blank")

    def _reject_float(token: str) -> Any:
        raise TrustCoreError("JSON_FLOAT_FORBIDDEN", f"{label}: float literal forbidden: {token!r}")

    def _reject_constant(token: str) -> Any:
        raise TrustCoreError("JSON_CONSTANT_FORBIDDEN", f"{label}: non-finite constant forbidden: {token!r}")

    def _parse_int_strict(token: str) -> int:
        digits = len(token) - 1 if token.startswith("-") else len(token)
        require_tc(digits <= max_int_digits, "JSON_INT_TOO_LONG", f"{label}: int exceeds {max_int_digits} digits")
        return int(token)

    def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            require_tc(k not in out, "JSON_DUPLICATE_KEY", f"{label}: duplicate JSON key {k!r}")
            out[k] = v
        return out

    def _parse_checked_float(token: str) -> Any:
        exact = Decimal(token)
        parsed = json.loads(token)
        if parsed == 0:
            require_tc(exact.is_zero(), "JSON_FLOAT_UNDERFLOW", f"{label}: float underflow {token!r}")
        return parsed

    kwargs: dict[str, Any] = {
        "parse_int": _parse_int_strict,
        "parse_constant": _reject_constant,
        "object_pairs_hook": _no_dup_pairs,
        "parse_float": _parse_checked_float if allow_float else _reject_float,
    }
    try:
        obj = json.loads(text, **kwargs)
    except TrustCoreError:
        raise
    except (ValueError, RecursionError, ArithmeticError) as exc:
        raise TrustCoreError("JSON_SYNTAX_ERROR", f"{label}: {exc}") from exc
    _validate_json_tree(obj, allow_float=allow_float, max_depth=max_depth, max_int_digits=max_int_digits)
    return obj


def strict_load_json_nofollow(
    path: str | Path,
    max_bytes: int = MAX_FILE_BYTES,
    allow_float: bool = False,
    *,
    require_trailing_lf: bool = True,
) -> Any:
    """Read via `O_NOFOLLOW` + `st_nlink==1` and strictly parse JSON."""
    raw = strict_read_bytes_nofollow(path, max_bytes)
    return parse_strict_json_bytes(
        raw,
        label=os.fspath(path),
        allow_float=allow_float,
        require_trailing_lf=require_trailing_lf,
    )


def atomic_write_json_nofollow(
    path: str | Path,
    obj: Any,
    *,
    allow_float: bool = False,
) -> bytes:
    """
    Write canonical JSON atomically with `O_NOFOLLOW` ancestor walk, `lstat` `st_nlink==1`
    check on any existing target, mode preservation, CSPRNG `O_CREAT|O_EXCL` temp file,
    `fsync`, and `os.replace`.
    """
    raw = canonical_json_bytes(obj, allow_float=allow_float)
    parent_dfd, leaf = _open_parent_dir_nofollow(path, "atomic_write_json")
    tmp_name = f".{leaf[:64]}.tc_{os.getpid()}_{secrets.token_hex(12)}.tmp"
    fd = -1
    created_tmp = False
    try:
        try:
            existing_st = os.lstat(leaf, dir_fd=parent_dfd)
        except FileNotFoundError:
            existing_st = None
        except OSError as exc:
            raise TrustCoreError("WRITE_LSTAT_FAILED", f"lstat failed on {leaf!r}: {exc}") from exc

        target_mode = 0o644
        if existing_st is not None:
            require_tc(stat.S_ISREG(existing_st.st_mode), "WRITE_TARGET_NOT_REG", f"target is not a regular file: {leaf!r}")
            require_tc(
                existing_st.st_nlink == 1,
                "WRITE_TARGET_HARDLINK",
                f"refusing to overwrite hardlinked target (nlink={existing_st.st_nlink}): {leaf!r}",
            )
            target_mode = stat.S_IMODE(existing_st.st_mode)

        try:
            fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, target_mode, dir_fd=parent_dfd)
            created_tmp = True
            os.fchmod(fd, target_mode)
            offset = 0
            while offset < len(raw):
                written = os.write(fd, raw[offset:])
                require_tc(written > 0, "WRITE_SHORT_ZERO", "os.write returned 0 bytes")
                offset += written
            os.fsync(fd)
            os.close(fd)
            fd = -1
            os.replace(tmp_name, leaf, src_dir_fd=parent_dfd, dst_dir_fd=parent_dfd)
            created_tmp = False
        except OSError as exc:
            raise TrustCoreError("ATOMIC_WRITE_IO_ERROR", f"atomic write failed for {leaf!r}: {exc}") from exc

        try:
            os.fsync(parent_dfd)
        except OSError as exc:
            if exc.errno not in (errno.EINVAL, errno.EROFS):
                raise TrustCoreError("DIR_FSYNC_FAILED", f"directory fsync failed: {exc}") from exc
        return raw
    finally:
        if fd >= 0:
            os.close(fd)
        if created_tmp:
            try:
                os.unlink(tmp_name, dir_fd=parent_dfd)
            except OSError:
                pass
        os.close(parent_dfd)


def bind_empirical_artifact(
    results_path: str | Path,
    bench_script_path: str | Path,
    *,
    max_bytes: int = MAX_FILE_BYTES,
    allow_float_results: bool = False,
    expected_results_sha256: str | None = None,
    expected_bench_sha256: str | None = None,
    require_embedded_bench_sha: bool = True,
    extra_source_paths: Mapping[str, str | Path] | None = None,
) -> dict[str, Any]:
    """
    Bind an empirical `results.json` artifact to its generating `bench_script` and core engines:
      - Fail-closed defaults (`allow_float_results=False`, `require_embedded_bench_sha=True`),
      - Reads all files via `O_NOFOLLOW` + `st_nlink==1` regular-file descriptors,
      - Enforces JSON object root, strictly parses `results.json`, and returns verified `results_obj`,
      - Enforces `results_mtime_ns > bench_mtime_ns` (and `> engine_mtime_ns` for `extra_source_paths`),
      - Verifies embedded `bench_script_sha256` and `engine_source_sha256` digests.
    """
    bench_bytes, bench_st = _strict_read_bytes_and_stat_nofollow(bench_script_path, max_bytes, label="bench_script")
    res_bytes, res_st = _strict_read_bytes_and_stat_nofollow(results_path, max_bytes, label="empirical_results")
    res_obj = parse_strict_json_bytes(
        res_bytes,
        label=os.fspath(results_path),
        allow_float=allow_float_results,
        require_trailing_lf=True,
    )
    require_tc(type(res_obj) is dict, "RESULTS_NOT_DICT", "empirical results root must be a JSON object")
    bench_sha = sha256_bytes(bench_bytes)
    res_sha = sha256_bytes(res_bytes)

    require_tc(
        res_st.st_mtime_ns > bench_st.st_mtime_ns,
        "STALE_EMPIRICAL_RESULTS",
        f"results mtime ({res_st.st_mtime_ns}) must strictly post-date bench script ({bench_st.st_mtime_ns})",
    )
    if expected_bench_sha256 is not None:
        require_tc(bench_sha == expected_bench_sha256, "BENCH_SHA_MISMATCH", "bench script SHA-256 mismatch")
    if expected_results_sha256 is not None:
        require_tc(res_sha == expected_results_sha256, "RESULTS_SHA_MISMATCH", "empirical results SHA-256 mismatch")

    embedded_checked = False
    if "bench_script_sha256" in res_obj:
        emb = res_obj["bench_script_sha256"]
        require_tc(
            type(emb) is str and emb == bench_sha,
            "EMBEDDED_BENCH_SHA_MISMATCH",
            "embedded bench_script_sha256 does not match bench script on disk",
        )
        embedded_checked = True
    elif require_embedded_bench_sha:
        raise TrustCoreError("MISSING_EMBEDDED_BENCH_SHA", "results JSON missing required bench_script_sha256 field")

    verified_engines: dict[str, str] = {}
    if extra_source_paths is not None:
        emb_engines = res_obj.get("engine_source_sha256")
        require_tc(
            type(emb_engines) is dict,
            "MISSING_EMBEDDED_ENGINE_SHAS",
            "results JSON missing engine_source_sha256 mapping",
        )
        require_tc(
            set(emb_engines.keys()) == set(extra_source_paths.keys()),
            "EMBEDDED_ENGINE_KEYS_MISMATCH",
            "embedded engine_source_sha256 keys do not match expected source files",
        )
        for src_name, src_path in sorted(extra_source_paths.items()):
            src_bytes, src_st = _strict_read_bytes_and_stat_nofollow(src_path, max_bytes, label=src_name)
            src_sha = sha256_bytes(src_bytes)
            require_tc(
                res_st.st_mtime_ns > src_st.st_mtime_ns,
                "STALE_EMPIRICAL_RESULTS",
                f"results mtime ({res_st.st_mtime_ns}) must strictly post-date {src_name} ({src_st.st_mtime_ns})",
            )
            require_tc(
                type(emb_engines.get(src_name)) is str and emb_engines[src_name] == src_sha,
                "EMBEDDED_ENGINE_SHA_MISMATCH",
                f"embedded engine_source_sha256[{src_name!r}] does not match file on disk",
            )
            verified_engines[src_name] = src_sha

    return {
        "bench_script_sha256": bench_sha,
        "results_sha256": res_sha,
        "engine_source_sha256": verified_engines,
        "bench_mtime_ns": int(bench_st.st_mtime_ns),
        "results_mtime_ns": int(res_st.st_mtime_ns),
        "mtime_delta_ns": int(res_st.st_mtime_ns - bench_st.st_mtime_ns),
        "results_postdates_bench": True,
        "embedded_bench_sha_checked": embedded_checked,
        "results_obj": res_obj,
    }


def _match_char_literal_end(source: str, i: int, n: int) -> int | None:
    if i + 2 < n and source[i + 1] not in ("\\", "'") and source[i + 2] == "'":
        return i + 3
    if i + 3 < n and source[i + 1] == "\\":
        if source[i + 3] == "'" and source[i + 2] != "\n":
            return i + 4
        esc = source[i + 2]
        if esc == "x" and i + 5 < n and source[i + 5] == "'" and all(c in _HEX_DIGITS for c in source[i + 3 : i + 5]):
            return i + 6
        if esc == "u" and i + 7 < n and source[i + 7] == "'" and all(c in _HEX_DIGITS for c in source[i + 3 : i + 7]):
            return i + 8
    return None


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_ident_cont(ch: str) -> bool:
    return ch.isalnum() or ch in "_'!?"


def _skip_ws_and_comments(source: str, j: int, n: int) -> int:
    while j < n:
        if source[j].isspace():
            j += 1
        elif source.startswith("--", j):
            while j < n and source[j] != "\n":
                j += 1
        elif source.startswith("/-", j):
            cdepth = 1
            j += 3 if (j + 2 < n and source[j + 2] in ("-", "!")) else 2
            while j < n and cdepth > 0:
                if source.startswith("/-", j):
                    cdepth += 1
                    j += 2
                elif source.startswith("-/", j):
                    cdepth -= 1
                    j += 2
                else:
                    j += 1
        else:
            break
    return j


def _find_interp_open_quote(source: str, i: int, n: int, in_ident: bool) -> tuple[int, int, bool] | None:
    """
    Detect Lean 4 interpolation prefixes followed by a string literal quote `"`.
    Returns `(tok_end, quote_idx, is_init_reserved)`:
      - `is_init_reserved=True` ONLY for Init-reserved keywords (`s!`, `f!`, `println!`).
      - `is_init_reserved=False` for ambiguous non-Init prefixes (`m!`, `throwError`, `dbg_trace`,
        `log*`, and arbitrary `<ident>! "..."`).
    """
    if in_ident or (i > 0 and source[i - 1] == "."):
        return None
    if _is_ident_start(source[i]):
        k = i + 1
        while k < n and _is_ident_cont(source[k]):
            k += 1
        tok = source[i:k]
        if tok in _INIT_RESERVED_INTERP_BANGS:
            j = _skip_ws_and_comments(source, k, n)
            if j < n and source[j] == '"':
                return k, j, True
        elif tok.endswith("!") or tok in _AMBIG_INTERP_PLAINS:
            j = _skip_ws_and_comments(source, k, n)
            if j < n and source[j] == '"':
                return k, j, False
    return None


def _match_interp_arg_macro(source: str, i: int, n: int, in_ident: bool) -> tuple[int, int, bool] | None:
    if in_ident or (i > 0 and source[i - 1] == "."):
        return None
    for kw, argc, is_bracket in _INTERP_ARG_MACROS:
        if source.startswith(kw, i):
            end = i + len(kw)
            if is_bracket:
                return end, argc, True
            if end == n or not _is_ident_cont(source[end]):
                return end, argc, False
    return None


def strip_lean4_comments_and_literals(
    source: str,
    *,
    expand_ambig_interp: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Literal-safe & nested-comment-safe Lean 4.36.0 stripper preserving line numbers.
    Only Init-reserved keywords (`s!`, `f!`, `println!`) unconditionally open interpolated
    strings in primary (`expand_ambig_interp=False`) mode; ambiguous prefixes (`m!`, `throwError`,
    `throwErrorAt`, `dbg_trace`, arg macros, arbitrary `<ident>!`) are lexed as plain strings
    and fail-closed (`LEAN4_AMBIG_INTERP_ESCAPE`) if the string contains `{` or `}`. Setting
    `expand_ambig_interp=True` runs the complementary dual-projection expansion pass.
    """
    require_tc(type(source) is str, "INVALID_SOURCE_TYPE", "Lean source must be str")
    out: list[str] = []
    lex_findings: list[dict[str, Any]] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    in_ambig_str = False
    ambig_str_flagged = False
    raw_hashes = -1
    opened_at = 0
    in_ident = False
    interp_stack: list[list[int]] = []
    pending_args = 0
    arg_depth = 0
    pending_tok = False
    interp_next_quote = False

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
                if pending_args > 0 and arg_depth == 0:
                    pending_args -= 1
                    pending_tok = False
                    interp_next_quote = pending_args == 0
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_str:
            if ch == "\\" and i + 1 < n:
                if in_ambig_str and not ambig_str_flagged and nxt in "{}":
                    ambig_str_flagged = True
                    line = source.count("\n", 0, opened_at) + 1
                    lex_findings.append({"line": line, "code": "LEAN4_AMBIG_INTERP_ESCAPE", "excerpt": "ambiguous non-Init interpolated string with braces"})
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                in_str = False
                in_ambig_str = False
                ambig_str_flagged = False
                out.append(" ")
                i += 1
                if pending_args > 0 and arg_depth == 0:
                    pending_args -= 1
                    pending_tok = False
                    interp_next_quote = pending_args == 0
            else:
                if in_ambig_str and not ambig_str_flagged and ch in "{}":
                    ambig_str_flagged = True
                    line = source.count("\n", 0, opened_at) + 1
                    lex_findings.append({"line": line, "code": "LEAN4_AMBIG_INTERP_ESCAPE", "excerpt": "ambiguous non-Init interpolated string with braces"})
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if interp_stack and interp_stack[-1][1] == 0:
            if ch == "\\" and i + 1 < n:
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                popped = interp_stack.pop()
                pending_args = popped[2]
                arg_depth = popped[3]
                pending_tok = bool(popped[4])
                out.append(" ")
                i += 1
                if pending_args > 0 and arg_depth == 0:
                    pending_args -= 1
                    pending_tok = False
                    interp_next_quote = pending_args == 0
            elif ch == "{":
                interp_stack[-1][1] = 1
                in_ident = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        if ch == "/" and nxt == "-":
            if pending_tok:
                pending_tok = False
                pending_args -= 1
                interp_next_quote = pending_args == 0
            depth = 1
            opened_at = i
            in_ident = False
            step = 3 if (i + 2 < n and source[i + 2] in ("-", "!")) else 2
            out.append(" " * step)
            i += step
            continue
        if ch == "-" and nxt == "-":
            if pending_tok:
                pending_tok = False
                pending_args -= 1
                interp_next_quote = pending_args == 0
            in_ident = False
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch.isspace():
            if pending_tok:
                pending_tok = False
                pending_args -= 1
                interp_next_quote = pending_args == 0
            in_ident = False
            out.append(ch)
            i += 1
            continue
        if interp_next_quote:
            interp_next_quote = False
            if ch == '"':
                if expand_ambig_interp:
                    interp_stack.append([i, 0, 0, 0, 0])
                else:
                    in_str = True
                    in_ambig_str = True
                    ambig_str_flagged = False
                    opened_at = i
                in_ident = False
                out.append(" ")
                i += 1
                continue
        if ch == "r" and not in_ident and (i == 0 or source[i - 1] != "."):
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                raw_hashes = j - (i + 1)
                opened_at = i
                in_ident = False
                out.append(" " * (j - i + 1))
                i = j + 1
                continue
        macro_arg = _match_interp_arg_macro(source, i, n, in_ident)
        if macro_arg is not None:
            end_kw, argc, is_bracket = macro_arg
            out.append(source[i:end_kw])
            i = end_kw
            in_ident = False
            pending_args = argc
            arg_depth = 1 if is_bracket else 0
            pending_tok = False
            continue
        interp_hit = _find_interp_open_quote(source, i, n, in_ident)
        if interp_hit is not None:
            tok_end, interp_q, is_reserved = interp_hit
            in_ident = False
            if is_reserved or expand_ambig_interp:
                interp_stack.append([i, 0, pending_args, arg_depth, 1 if pending_tok else 0])
                pending_args = 0
                arg_depth = 0
                pending_tok = False
                for k in range(i, interp_q + 1):
                    out.append("\n" if source[k] == "\n" else " ")
            else:
                out.append(source[i:tok_end])
                for k in range(tok_end, interp_q + 1):
                    out.append("\n" if source[k] == "\n" else " ")
                in_str = True
                in_ambig_str = True
                ambig_str_flagged = False
                opened_at = interp_q
            i = interp_q + 1
            continue
        if ch == '"':
            in_str = True
            in_ambig_str = False
            ambig_str_flagged = False
            opened_at = i
            in_ident = False
            out.append(" ")
            i += 1
            continue
        if ch == "'" and not in_ident:
            char_end = _match_char_literal_end(source, i, n)
            if char_end is not None:
                in_ident = False
                out.append(" \n " if source[i + 1] == "\n" else " " * (char_end - i))
                i = char_end
                if pending_args > 0 and arg_depth == 0:
                    pending_args -= 1
                    pending_tok = False
                    interp_next_quote = pending_args == 0
                continue
        if ch == "«":
            end_g = source.find("»", i + 1)
            if end_g == -1:
                line = source.count("\n", 0, i) + 1
                lex_findings.append({"line": line, "code": "LEAN4_UNTERMINATED_IDENT", "excerpt": "unterminated guillemet"})
                out.append("\n" * source.count("\n", i))
                break
            inner_g = source[i + 1 : end_g].replace("\n", " ")
            if out and out[-1] and _is_ident_cont(out[-1][-1]):
                out.append(" ")
            out.append(inner_g if inner_g else " ")
            if end_g + 1 < n and _is_ident_start(source[end_g + 1]):
                out.append(" ")
            in_ident = False
            i = max(i + 1, end_g + 1)
            if pending_args > 0 and arg_depth == 0:
                if i < n and source[i] == ".":
                    pending_tok = True
                else:
                    pending_args -= 1
                    pending_tok = False
                    interp_next_quote = pending_args == 0
            continue
        if interp_stack:
            if ch == "{":
                interp_stack[-1][1] += 1
                in_ident = False
                out.append("{")
                i += 1
                continue
            if ch == "}":
                interp_stack[-1][1] -= 1
                in_ident = False
                out.append(" " if interp_stack[-1][1] == 0 else "}")
                i += 1
                continue
        if pending_args > 0:
            if ch in "([{⟨":
                if pending_tok:
                    pending_tok = False
                    pending_args -= 1
                arg_depth += 1
            elif ch in ")]}⟩" and arg_depth > 0:
                arg_depth -= 1
                if arg_depth == 0:
                    pending_args -= 1
                    interp_next_quote = pending_args == 0
            elif arg_depth == 0 and not (ch == "#" and not pending_tok and source.startswith("[", i + 1)):
                if _is_ident_cont(ch) or ch == ".":
                    pending_tok = True
                else:
                    pending_args = 0
                    pending_tok = False

        in_ident = _is_ident_cont(ch) if in_ident else _is_ident_start(ch)
        out.append(ch)
        i += 1

    if depth > 0 or in_str or raw_hashes >= 0 or interp_stack:
        err_pos = opened_at if (depth > 0 or in_str or raw_hashes >= 0) else interp_stack[-1][0]
        line = source.count("\n", 0, err_pos) + 1
        code = "LEAN4_UNTERMINATED_COMMENT" if depth > 0 else "LEAN4_UNTERMINATED_STRING"
        lex_findings.append({"line": line, "code": code, "excerpt": code.lower()})

    return "".join(out), lex_findings


def _find_decide_native_lines(scan_text: str) -> list[int]:
    """Catch `decide (native := ...)`, `decide (config := ...)`, and nested paren/brace variants."""
    lines_out: list[int] = []
    n = len(scan_text)
    for m in _DECIDE_WORD_RE.finditer(scan_text):
        j = m.end()
        while j < n:
            while j < n and scan_text[j].isspace():
                j += 1
            if j >= n:
                break
            if scan_text[j] == "(":
                start_p = j
                pdepth = 1
                j += 1
                while j < n and pdepth > 0:
                    if scan_text[j] == "(":
                        pdepth += 1
                    elif scan_text[j] == ")":
                        pdepth -= 1
                    j += 1
                arg_text = scan_text[start_p:j]
                if _NATIVE_OR_CONFIG_RE.search(arg_text) is not None:
                    lines_out.append(scan_text.count("\n", 0, m.start()) + 1)
                    break
            elif scan_text[j] == "+":
                k = j + 1
                while k < n and _is_ident_cont(scan_text[k]):
                    k += 1
                if scan_text[j + 1 : k] == "native":
                    lines_out.append(scan_text.count("\n", 0, m.start()) + 1)
                    break
                j = k
            else:
                break
    return lines_out


def extract_lean4_theorems(source: str) -> list[str]:
    """
    Extract all public (non-private) theorem/lemma names with exact per-segment namespace tracking.
    Handles multiline `theorem\\n  name`, multiline `@[...]`, unnamed `section ... end`, and
    partial nested pops (`namespace A.B ... end B ... end A`) matching Lean 4 semantics.
    """
    cleaned, _ = strip_lean4_comments_and_literals(source)
    toks = _DECL_TOKEN_RE.findall(cleaned)
    scopes: list[tuple[str, str]] = []
    theorems: list[str] = []
    i = 0
    n = len(toks)
    pending_private = False
    while i < n:
        tok = toks[i]
        if tok.startswith("@[") or tok in ("protected", "noncomputable", "unsafe", "partial", "scoped", "local"):
            i += 1
            continue
        if tok == "private":
            pending_private = True
            i += 1
            continue
        if tok == "namespace" and i + 1 < n and _is_ident_start(toks[i + 1][0]):
            for seg in toks[i + 1].split("."):
                scopes.append(("namespace", seg))
            pending_private = False
            i += 2
            continue
        if tok == "section":
            if i + 1 < n and _is_ident_start(toks[i + 1][0]) and toks[i + 1] not in (
                "theorem", "lemma", "def", "abbrev", "private", "protected", "noncomputable",
                "namespace", "section", "end", "open", "variable", "universe", "structure", "inductive", "class",
            ):
                for seg in toks[i + 1].split("."):
                    scopes.append(("section", seg))
                i += 2
            else:
                scopes.append(("section", ""))
                i += 1
            pending_private = False
            continue
        if tok == "end":
            if i + 1 < n and _is_ident_start(toks[i + 1][0]) and scopes:
                end_parts = toks[i + 1].split(".")
                k_end = len(end_parts)
                if len(scopes) >= k_end and [nm for _, nm in scopes[-k_end:]] == end_parts:
                    del scopes[-k_end:]
                    i += 2
                    pending_private = False
                    continue
            if scopes:
                scopes.pop()
            pending_private = False
            i += 1
            continue
        if tok in ("theorem", "lemma") and i + 1 < n and _is_ident_start(toks[i + 1][0]):
            if not pending_private:
                ns_parts = [nm for kind, nm in scopes if kind == "namespace" and nm]
                name = toks[i + 1]
                theorems.append(".".join((*ns_parts, name)) if ns_parts else name)
            pending_private = False
            i += 2
            continue
        pending_private = False
        i += 1
    return theorems


def _scan_lean4_escape_text(
    cleaned: str,
    *,
    allow_non_init_imports: bool,
    allow_project_imports: Sequence[str],
    allow_instances: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    scan_text = _ROOT_NS_PREFIX_RE.sub(lambda m: "\n" * m.group(0).count("\n"), cleaned)
    findings: list[dict[str, Any]] = []
    lines = scan_text.split("\n")

    for pat, code in _SOURCE_ESCAPE_RULES:
        for m_esc in pat.finditer(scan_text):
            lineno = scan_text.count("\n", 0, m_esc.start()) + 1
            excerpt = lines[lineno - 1].strip()[:100]
            findings.append({"line": lineno, "code": code, "excerpt": excerpt})

    if not allow_instances:
        for m_inst in _INSTANCE_RE.finditer(scan_text):
            lineno = scan_text.count("\n", 0, m_inst.start()) + 1
            findings.append({"line": lineno, "code": "LEAN4_INSTANCE_OVERRIDE", "excerpt": lines[lineno - 1].strip()[:100]})

    for dec_line in _find_decide_native_lines(scan_text):
        findings.append({"line": dec_line, "code": "LEAN4_DECIDE_NATIVE", "excerpt": lines[dec_line - 1].strip()[:100]})

    if _VAR_DECL_RE.search(scan_text) is not None and _INCLUDE_DECL_RE.search(scan_text) is not None:
        m_inc = _INCLUDE_DECL_RE.search(scan_text)
        lineno = scan_text.count("\n", 0, m_inc.start()) + 1 if m_inc is not None else 1
        findings.append({"line": lineno, "code": "LEAN4_VARIABLE_INCLUDE", "excerpt": lines[lineno - 1].strip()[:100]})

    imports: list[str] = []
    for m_imp in _IMPORT_RE.finditer(scan_text):
        lineno = scan_text.count("\n", 0, m_imp.start(2)) + 1
        mod = m_imp.group(2)
        imports.append(mod)
        if re.search(r"\bpublic\b", m_imp.group(1)) is not None:
            findings.append({"line": lineno, "code": "LEAN4_PUBLIC_IMPORT", "excerpt": mod})
        root_pkg = mod.split(".", 1)[0]
        allowed_proj = any(mod == p or mod.startswith(p + ".") for p in allow_project_imports)
        if mod in ("Std", "Std.Tactic", "Lean", "Lean.Elab", "Lean.Elab.Tactic") or mod.startswith("Std.Tactic.BVDecide"):
            findings.append({"line": lineno, "code": "LEAN4_FORBIDDEN_IMPORT", "excerpt": mod})
        elif not allow_non_init_imports and root_pkg != "Init" and not allowed_proj:
            findings.append({"line": lineno, "code": "LEAN4_NON_INIT_IMPORT", "excerpt": mod})

    return findings, imports


def audit_lean4_source_static(
    source: str,
    *,
    allow_non_init_imports: bool = False,
    allow_project_imports: Sequence[str] = (),
    allow_instances: bool = False,
) -> dict[str, Any]:
    """Static Lean 4.36.0 dual-projection hardening auditor closing all Wave-22 & Delta-2 bypass classes."""
    cleaned_plain, lex_findings = strip_lean4_comments_and_literals(source, expand_ambig_interp=False)
    plain_findings, imports = _scan_lean4_escape_text(
        cleaned_plain,
        allow_non_init_imports=allow_non_init_imports,
        allow_project_imports=allow_project_imports,
        allow_instances=allow_instances,
    )
    findings: list[dict[str, Any]] = list(lex_findings) + plain_findings

    # Dual-projection pass: also scan with ambiguous non-Init prefixes expanded as interpolated strings
    cleaned_interp, _ = strip_lean4_comments_and_literals(source, expand_ambig_interp=True)
    if cleaned_interp != cleaned_plain:
        seen_keys = {(f["line"], f["code"]) for f in findings}
        interp_findings, _ = _scan_lean4_escape_text(
            cleaned_interp,
            allow_non_init_imports=allow_non_init_imports,
            allow_project_imports=allow_project_imports,
            allow_instances=allow_instances,
        )
        for item in interp_findings:
            key = (item["line"], item["code"])
            if key not in seen_keys:
                seen_keys.add(key)
                findings.append(item)

    return {"clean": len(findings) == 0, "findings": findings, "imports": imports}


def _check_safe_srcdir(val: str) -> bool:
    if not val or "\x00" in val or val.startswith(("/", "\\")):
        return False
    if val == ".":
        return True
    segs = re.split(r"[/\\]", val)
    for seg in segs:
        if not seg or seg == ".." or seg in _SKIP_DIR_SEGMENTS or seg.startswith("."):
            return False
    return True


def _check_safe_root(val: str) -> bool:
    if _MOD_IDENT_RE.match(val) is None:
        return False
    return not any(seg in _SKIP_DIR_SEGMENTS for seg in val.split("."))


def _check_safe_glob(val: str) -> bool:
    if _LAKE_GLOB_RE.match(val) is None:
        return False
    base = val.removesuffix(".+").removesuffix(".*")
    return not any(seg in _SKIP_DIR_SEGMENTS for seg in base.split("."))


def audit_lakefile_bytes(filename: str, raw: bytes) -> list[dict[str, Any]]:
    """
    Audit `lakefile.toml` bytes against a strict declarative schema allowlist.
    Executable `lakefile.lean` files are unconditionally rejected (closes HIGH-3 IO escape).
    """
    require_tc(b"\r" not in raw, "LAKEFILE_CRLF", f"{filename}: CR/CRLF forbidden")
    if filename != "lakefile.toml":
        return [{"file": filename, "code": "LAKEFILE_LEAN_FORBIDDEN", "excerpt": "only declarative lakefile.toml is permitted"}]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TrustCoreError("INVALID_UTF8", f"{filename}: invalid UTF-8: {exc}") from exc

    try:
        tdata = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise TrustCoreError("LAKEFILE_TOML_SYNTAX", f"{filename}: {exc}") from exc

    findings: list[dict[str, Any]] = []
    for k, v in tdata.items():
        for tok in _UNSAFE_LAKE_TOKENS:
            if tok in k:
                findings.append({"file": filename, "code": "LAKEFILE_UNSAFE_TOKEN", "excerpt": tok})
        if k not in _ALLOWED_LAKE_TOP_KEYS:
            findings.append({"file": filename, "code": "LAKEFILE_UNSAFE_KEY", "excerpt": k})
            continue
        if k == "name":
            if type(v) is not str or _LAKE_PKG_NAME_RE.match(v) is None:
                findings.append({"file": filename, "code": "LAKEFILE_INVALID_SCHEMA", "excerpt": f"name={v!r}"})
        elif k == "version":
            if type(v) is not str or _LAKE_VERSION_RE.match(v) is None:
                findings.append({"file": filename, "code": "LAKEFILE_INVALID_SCHEMA", "excerpt": f"version={v!r}"})
        elif k == "defaultTargets":
            if type(v) is not list or not all(type(item) is str and _check_safe_root(item) for item in v):
                findings.append({"file": filename, "code": "LAKEFILE_INVALID_SCHEMA", "excerpt": f"defaultTargets={v!r}"})
        elif k == "lean_lib":
            if type(v) is not list:
                findings.append({"file": filename, "code": "LAKEFILE_INVALID_SCHEMA", "excerpt": "lean_lib must be list"})
                continue
            for entry in v:
                if type(entry) is not dict:
                    findings.append({"file": filename, "code": "LAKEFILE_INVALID_SCHEMA", "excerpt": "lean_lib entry must be table"})
                    continue
                for lk, lv in entry.items():
                    if lk not in _ALLOWED_LEAN_LIB_KEYS:
                        findings.append({"file": filename, "code": "LAKEFILE_UNSAFE_KEY", "excerpt": lk})
                    elif lk == "name":
                        if type(lv) is not str or not _check_safe_root(lv):
                            findings.append({"file": filename, "code": "LAKEFILE_UNSAFE_ROOT", "excerpt": str(lv)})
                    elif lk == "srcDir":
                        if type(lv) is not str or not _check_safe_srcdir(lv):
                            findings.append({"file": filename, "code": "LAKEFILE_UNSAFE_PATH", "excerpt": str(lv)})
                    elif lk == "roots":
                        if type(lv) is not list or not all(type(item) is str and _check_safe_root(item) for item in lv):
                            findings.append({"file": filename, "code": "LAKEFILE_UNSAFE_ROOT", "excerpt": str(lv)})
                    elif lk == "globs":
                        if type(lv) is not list or not all(type(item) is str and _check_safe_glob(item) for item in lv):
                            findings.append({"file": filename, "code": "LAKEFILE_UNSAFE_GLOB", "excerpt": str(lv)})

    # Defense-in-depth scan of all nested strings for unsafe tokens
    stack: list[Any] = [tdata]
    while stack:
        cur = stack.pop()
        if type(cur) is dict:
            stack.extend(cur.values())
        elif type(cur) is list:
            stack.extend(cur)
        elif type(cur) is str:
            for tok in _UNSAFE_LAKE_TOKENS:
                if tok in cur:
                    findings.append({"file": filename, "code": "LAKEFILE_UNSAFE_TOKEN", "excerpt": tok})
    return findings


def _decode_tool_bytes(raw: bytes, label: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TrustCoreError("LEAN_OUTPUT_INVALID_UTF8", f"{label}: non-UTF-8 tool output: {exc}") from exc


def _verify_elf_executable(bin_path: Path, label: str) -> None:
    try:
        st = os.lstat(bin_path)
    except OSError as exc:
        raise TrustCoreError("LEAN_TOOL_NOT_FOUND", f"{label} missing at {bin_path}: {exc}") from exc
    require_tc(stat.S_ISREG(st.st_mode), "LEAN_TOOL_UNTRUSTED", f"{label} must be a regular binary (no symlinks): {bin_path}")
    require_tc(bool(st.st_mode & 0o111), "LEAN_TOOL_UNTRUSTED", f"{label} is not executable: {bin_path}")
    fd = os.open(os.fspath(bin_path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        raw_hdr = os.read(fd, 4)
    finally:
        os.close(fd)
    require_tc(raw_hdr == b"\x7fELF", "LEAN_TOOL_UNTRUSTED", f"{label} must be a native ELF binary (shell shims rejected): {bin_path}")


def resolve_verified_lean_bins(expected_toolchain: str = "leanprover/lean4:v4.36.0") -> tuple[Path, Path, Path]:
    """
    Resolve pinned absolute native ELF `lean` and `lake` binaries directly from the
    user's trusted elan toolchain directory (immune to `PATH` shims and `ELAN_TOOLCHAIN` spoofing).
    """
    require_tc(_TOOLCHAIN_RE.match(expected_toolchain) is not None, "INVALID_TOOLCHAIN_SPEC", f"invalid toolchain: {expected_toolchain!r}")
    tc_dir_name = expected_toolchain.replace("/", "--").replace(":", "---")
    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    elan_home = real_home / ".elan"
    tc_bin = elan_home / "toolchains" / tc_dir_name / "bin"
    lean_bin = tc_bin / "lean"
    lake_bin = tc_bin / "lake"
    _verify_elf_executable(lean_bin, "lean")
    _verify_elf_executable(lake_bin, "lake")
    return lean_bin, lake_bin, real_home


def _default_lean_exec(
    args: Sequence[str],
    cwd: Path,
    timeout: int,
    *,
    expected_toolchain: str = "leanprover/lean4:v4.36.0",
) -> tuple[int, bytes, bytes]:
    lean_bin, lake_bin, real_home = resolve_verified_lean_bins(expected_toolchain)
    resolved_args: list[str] = []
    for idx, tok in enumerate(args):
        if idx == 0 and tok == "lean":
            resolved_args.append(os.fspath(lean_bin))
        elif idx == 0 and tok == "lake":
            resolved_args.append(os.fspath(lake_bin))
        elif idx == 2 and len(args) >= 3 and args[0] == "lake" and args[1] == "env" and tok == "lean":
            resolved_args.append(os.fspath(lean_bin))
        else:
            resolved_args.append(tok)
    clean_env = {
        "PATH": f"{os.fspath(lean_bin.parent)}:/usr/bin:/bin",
        "HOME": os.fspath(real_home),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    try:
        proc = subprocess.run(resolved_args, cwd=str(cwd), env=clean_env, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise TrustCoreError("LEAN_TOOL_NOT_FOUND", f"required tool missing: {resolved_args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise TrustCoreError("LEAN_TIMEOUT", f"command timed out after {timeout}s: {' '.join(resolved_args)}") from exc
    return proc.returncode, proc.stdout, proc.stderr


def _parse_axiom_lines(stdout_text: str, expected_theorems: Sequence[str], allowed_axioms: frozenset[str]) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m_none = _AXIOM_NONE_RE.match(line)
        if m_none is not None:
            thm = m_none.group(1)
            require_tc(thm not in seen, "DUPLICATE_AXIOM_REPORT", f"duplicate axiom output for {thm}")
            seen[thm] = []
            continue
        m_some = _AXIOM_SOME_RE.match(line)
        require_tc(m_some is not None, "UNEXPECTED_AXIOM_LINE", f"unexpected axiom output line: {line!r}")
        thm = m_some.group(1)
        require_tc(thm not in seen, "DUPLICATE_AXIOM_REPORT", f"duplicate axiom output for {thm}")
        raw_axs = [tok.strip() for tok in m_some.group(2).split(",") if tok.strip()]
        for ax in raw_axs:
            require_tc(_FORBIDDEN_AXIOM_RE.match(ax) is None, "FORBIDDEN_KERNEL_AXIOM", f"{thm} uses forbidden axiom {ax}")
            require_tc(ax in allowed_axioms, "DISALLOWED_AXIOM", f"{thm} uses axiom {ax} not in {sorted(allowed_axioms)}")
        seen[thm] = raw_axs

    missing = [thm for thm in expected_theorems if thm not in seen]
    require_tc(len(missing) == 0, "MISSING_AXIOM_THEOREMS", f"missing #print axioms output for: {missing}")
    extra = [thm for thm in seen if thm not in expected_theorems]
    require_tc(len(extra) == 0, "EXTRA_AXIOM_THEOREMS", f"unexpected #print axioms output for: {extra}")
    return seen


def run_isolated_live_lean(
    pinned_files_bytes: Mapping[str, bytes],
    expected_theorems: Sequence[str],
    allowed_axioms: Sequence[str] | frozenset[str] = PURE_INIT_AXIOMS,
    *,
    lean_module: str | None = None,
    expected_toolchain: str = "leanprover/lean4:v4.36.0",
    timeout: int = 120,
    runner: Callable[[Sequence[str], Path, int], tuple[int, bytes, bytes]] | None = None,
) -> dict[str, Any]:
    """
    Verify pinned in-memory Lean 4.36.0 files with zero disk re-read and zero `.lake/` residue:
      1. Enforces strict bundle allowlist (`lean-toolchain`, `lake-manifest.json`, `lakefile.toml`, safe `*.lean`),
      2. Enforces declarative `lakefile.toml` only (never executes `lakefile.lean`),
      3. Enforces exact bijection `declared == expected` (multiline-aware, no extra unaudited theorems),
      4. Resolves native ELF `lean`/`lake` binaries directly from elan (blocks `PATH` shims & env hijacking),
      5. Rejects warnings on stdout/stderr, enforces exact axiom compliance, and verifies tempdir cleanup.
    """
    require_tc(isinstance(pinned_files_bytes, Mapping) and len(pinned_files_bytes) > 0, "EMPTY_LEAN_BUNDLE", "pinned_files_bytes is empty")
    require_tc(len(expected_theorems) > 0, "EMPTY_EXPECTED_THEOREMS", "expected_theorems must be non-empty")
    require_tc(len(set(expected_theorems)) == len(expected_theorems), "DUP_EXPECTED_THEOREMS", "duplicate expected theorem names")
    allowed_set = frozenset(allowed_axioms)
    for ax in allowed_set:
        require_tc(_FORBIDDEN_AXIOM_RE.match(ax) is None, "UNSAFE_ALLOWED_AXIOM", f"forbidden axiom cannot be allowed: {ax}")

    file_hashes: dict[str, str] = {}
    lean_sources: dict[str, str] = {}
    all_declared: list[str] = []
    has_lakefile = False

    for rel_name, raw in sorted(pinned_files_bytes.items()):
        require_tc(type(rel_name) is str and len(rel_name) > 0, "INVALID_BUNDLE_FILENAME", "filename must be non-empty str")
        require_tc(type(raw) is bytes, "INVALID_BUNDLE_BYTES", f"{rel_name}: bytes required")
        p = Path(rel_name)
        require_tc(not p.is_absolute() and ".." not in p.parts and "\x00" not in rel_name, "UNSAFE_BUNDLE_PATH", f"unsafe path: {rel_name!r}")
        require_tc(".lake" not in p.parts, "LAKE_RESIDUE_IN_BUNDLE", f".lake residue forbidden: {rel_name!r}")
        require_tc(not any(seg in _SKIP_DIR_SEGMENTS for seg in p.parts), "UNSAFE_BUNDLE_PATH", f"forbidden directory segment: {rel_name!r}")
        file_hashes[rel_name] = sha256_bytes(raw)

        if rel_name == "lean-toolchain":
            require_tc(b"\r" not in raw, "TOOLCHAIN_CRLF", "lean-toolchain must use LF")
            tc_text = _decode_tool_bytes(raw, "lean-toolchain").strip()
            require_tc(tc_text == expected_toolchain, "TOOLCHAIN_MISMATCH", f"expected {expected_toolchain!r}, got {tc_text!r}")
        elif rel_name == "lake-manifest.json":
            man = parse_strict_json_bytes(raw, label="lake-manifest.json", allow_float=False, require_trailing_lf=True)
            require_tc(type(man) is dict and man.get("packages") == [], "EXTERNAL_LEAN_PACKAGES", "lake-manifest packages must be []")
        elif rel_name == "lakefile.toml":
            has_lakefile = True
            lf_findings = audit_lakefile_bytes(rel_name, raw)
            require_tc(len(lf_findings) == 0, "LAKEFILE_AUDIT_FAILED", f"unsafe lakefile: {lf_findings}")
        elif rel_name == "lakefile.lean":
            raise TrustCoreError("LAKEFILE_LEAN_FORBIDDEN", "executable lakefile.lean forbidden; use declarative lakefile.toml")
        elif rel_name.endswith(".lean"):
            require_tc(b"\r" not in raw, "LEAN_CRLF", f"{rel_name}: CR/CRLF forbidden")
            src_text = _decode_tool_bytes(raw, rel_name)
            st_res = audit_lean4_source_static(src_text)
            require_tc(st_res["clean"], "LEAN_STATIC_AUDIT_FAILED", f"{rel_name}: {st_res['findings']}")
            lean_sources[rel_name] = src_text
            all_declared.extend(extract_lean4_theorems(src_text))
        else:
            raise TrustCoreError("UNEXPECTED_BUNDLE_FILE", f"unexpected non-Lean bundle entry: {rel_name!r}")

    require_tc("lean-toolchain" in file_hashes, "MISSING_TOOLCHAIN", "lean-toolchain missing from pinned bundle")
    require_tc("lake-manifest.json" in file_hashes, "MISSING_LAKE_MANIFEST", "lake-manifest.json missing from pinned bundle")
    require_tc(has_lakefile, "MISSING_LAKEFILE", "lakefile.toml missing from pinned bundle")
    require_tc(len(lean_sources) > 0, "MISSING_LEAN_SOURCE", "no .lean source files in pinned bundle")

    require_tc(len(set(all_declared)) == len(all_declared), "DUP_DECLARED_THEOREMS", f"duplicate declared theorems: {all_declared}")
    declared_set = set(all_declared)
    expected_set = set(expected_theorems)
    missing_static = [t for t in expected_theorems if t not in declared_set]
    require_tc(len(missing_static) == 0, "MISSING_EXPECTED_THEOREM_DECL", f"undeclared expected theorems: {missing_static}")
    extra_static = [t for t in all_declared if t not in expected_set]
    require_tc(len(extra_static) == 0, "EXTRA_UNAUDITED_THEOREM_DECL", f"extra unaudited theorems declared: {extra_static}")

    mod_name = lean_module
    if mod_name is None:
        first_lean = sorted(lean_sources.keys())[0]
        mod_name = first_lean[:-5].replace("/", ".")
    require_tc(_MOD_IDENT_RE.match(mod_name) is not None, "INVALID_LEAN_MODULE", f"invalid Lean module: {mod_name!r}")

    exec_fn: Callable[[Sequence[str], Path, int], tuple[int, bytes, bytes]]
    if runner is None:
        exec_fn = lambda a, c, t: _default_lean_exec(a, c, t, expected_toolchain=expected_toolchain)
    else:
        exec_fn = runner
    expected_ver_prefix = expected_toolchain.split(":v", 1)[-1]

    staged_tmp: Path | None = None
    with tempfile.TemporaryDirectory(prefix="aletheia_lean_") as tmp_str:
        tmp_dir = Path(tmp_str)
        staged_tmp = tmp_dir
        os.chmod(tmp_dir, 0o700)
        for rel_name, raw in sorted(pinned_files_bytes.items()):
            dst = tmp_dir / rel_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(raw)
            os.chmod(dst, 0o644)

        audit_lines = [f"import {mod_name}", *(f"#print axioms {thm}" for thm in expected_theorems), ""]
        audit_file = tmp_dir / "__AuditAxioms.lean"
        audit_file.write_bytes("\n".join(audit_lines).encode("utf-8"))
        os.chmod(audit_file, 0o644)

        v_rc, v_out_b, v_err_b = exec_fn(["lean", "--version"], tmp_dir, timeout)
        v_out = _decode_tool_bytes(v_out_b, "lean --version stdout").strip()
        v_err = _decode_tool_bytes(v_err_b, "lean --version stderr").strip()
        require_tc(v_rc == 0, "LEAN_VERSION_FAILED", f"lean --version rc={v_rc}: {v_err}")
        require_tc(
            f"version {expected_ver_prefix}," in v_out,
            "LEAN_VERSION_MISMATCH",
            f"expected exact Lean {expected_ver_prefix}, got {v_out!r}",
        )

        b_rc, b_out_b, b_err_b = exec_fn(["lake", "build"], tmp_dir, timeout)
        b_out = _decode_tool_bytes(b_out_b, "lake build stdout")
        b_err = _decode_tool_bytes(b_err_b, "lake build stderr").strip()
        require_tc(b_rc == 0, "LAKE_BUILD_FAILED", f"lake build rc={b_rc}: {b_err}")
        require_tc(b_err == "", "LAKE_BUILD_STDERR", f"lake build emitted stderr: {b_err}")
        require_tc(_LEAN_WARN_RE.search(b_out) is None, "LAKE_BUILD_WARNING", f"lake build emitted warning: {b_out.strip()[:200]}")

        a_rc, a_out_b, a_err_b = exec_fn(["lake", "env", "lean", "__AuditAxioms.lean"], tmp_dir, timeout)
        a_out = _decode_tool_bytes(a_out_b, "axiom check stdout")
        a_err = _decode_tool_bytes(a_err_b, "axiom check stderr").strip()
        require_tc(a_rc == 0, "AXIOM_CHECK_FAILED", f"axiom check rc={a_rc}: {a_err}")
        require_tc(a_err == "", "AXIOM_CHECK_STDERR", f"axiom check emitted stderr: {a_err}")

        thm_axioms = _parse_axiom_lines(a_out, expected_theorems, allowed_set)

    tempdir_cleaned = staged_tmp is not None and not staged_tmp.exists()
    require_tc(tempdir_cleaned, "TEMP_DIR_RESIDUE", "isolated Lean tempdir still exists after cleanup")
    zero_ax_count = sum(1 for axs in thm_axioms.values() if len(axs) == 0)
    return {
        "status": "LIVE_LEAN_4_36_0_PASS",
        "lean_version": v_out,
        "lean_module": mod_name,
        "theorems_verified": len(thm_axioms),
        "zero_axiom_theorems": zero_ax_count,
        "theorem_axioms": {k: thm_axioms[k] for k in expected_theorems},
        "file_sha256": file_hashes,
        "isolated_tempdir_cleaned": tempdir_cleaned,
    }


class _StrictHelpAction(argparse.Action):
    def __init__(self, option_strings: Sequence[str], dest: str = argparse.SUPPRESS, default: Any = argparse.SUPPRESS, help: str | None = None) -> None:
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: Any, option_string: str | None = None) -> None:
        raise _StrictHelpSignal({
            "description": parser.description or "",
            "prog": parser.prog,
            "status": "HELP",
            "usage": parser.format_usage().strip(),
        })


class StrictArgumentParser(argparse.ArgumentParser):
    """Fail-closed ArgumentParser: disables abbreviations, emits JSON help, raises `TrustCoreError` on errors."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["allow_abbrev"] = False
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action=_StrictHelpAction, help="Emit canonical JSON help and exit 0")

    def error(self, message: str) -> Any:
        raise TrustCoreError("CLI_ARG_ERROR", message)


def make_strict_parser(prog: str, description: str) -> StrictArgumentParser:
    return StrictArgumentParser(prog=prog, description=description, allow_abbrev=False)


def run_fail_closed_cli(
    fn: Callable[..., dict[str, Any]],
    *,
    parser_builder: Callable[[], argparse.ArgumentParser] | None = None,
    argv: Sequence[str] | None = None,
    allow_float_output: bool = False,
) -> int:
    """
    Execute a CLI callback fail-closed:
      - Enforces `StrictArgumentParser` with `allow_abbrev=False` when `parser_builder` is provided,
      - Emits canonical single-line JSON on stdout (`RC=0`) on success or `--help`,
      - Catches ALL exceptions (including `TrustCoreError`, `SystemExit`, `UnicodeDecodeError`, `OSError`)
        and emits canonical single-line JSON on stderr with `RC=2` (zero `RC=1` tracebacks).
    """
    try:
        if parser_builder is not None:
            parser = parser_builder()
            require_tc(
                isinstance(parser, StrictArgumentParser) and parser.allow_abbrev is False,
                "CLI_PARSER_NOT_STRICT",
                "parser must be StrictArgumentParser with allow_abbrev=False",
            )
            arg_val = parser.parse_args(argv)
            result = fn(arg_val)
        else:
            result = fn()
        require_tc(type(result) is dict, "CLI_RESULT_NOT_DICT", "CLI callback must return dict")
        _validate_json_tree(result, allow_float=allow_float_output)
        line = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        sys.stdout.write(line + "\n")
        return 0
    except _StrictHelpSignal as sig:
        line = json.dumps(sig.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        sys.stdout.write(line + "\n")
        return 0
    except TrustCoreError as exc:
        err = {"code": exc.code, "message": exc.message, "status": "ERROR"}
        sys.stderr.write(json.dumps(err, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2
    except SystemExit as exc:
        err = {"code": "CLI_SYSTEM_EXIT", "message": f"unexpected SystemExit({exc.code})", "status": "ERROR"}
        sys.stderr.write(json.dumps(err, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2
    except Exception as exc:
        err = {"code": f"UNHANDLED_{type(exc).__name__.upper()}", "message": str(exc), "status": "ERROR"}
        sys.stderr.write(json.dumps(err, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2
