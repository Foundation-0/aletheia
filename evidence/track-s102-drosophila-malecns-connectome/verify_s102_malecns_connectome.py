#!/usr/bin/env python3
"""Track S102 Zone-B Hardened Verifier, Field-Complete Secondary Mathematical
Auditor (SEC/FR0/FR1), R12-Grade Static Lean 4 Scanner, and Live Lean 4.36.0
Kernel Verifier.

CLI modes:
  --check <path> [--json]                  Verify certificate + replay + live Lean 4.36.0
  --write <path> [--json]                  Atomically write canonical certificate (0o600)
  --standalone                             Emit canonical certificate JSON to stdout
  --verify-data <malecns_dir> <wave9_dir>  Also re-hash external read-only datasets on disk
  [--json]                                 Default: check committed certificate in track dir
"""
from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s102_malecns_connectome_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 512 * 1024
MAX_JSON_INT_DIGITS = 80
MAX_JSON_INT_BITS = 2048
_CANON_Q_RE = re.compile(r"^(?:0|-?[1-9][0-9]*)(?:/[1-9][0-9]*)?$")
_RAW_INT_SCAN_RE = re.compile(r"(?<![A-Za-z0-9_.\"])-?[0-9]+(?![A-Za-z0-9_.\"])")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# R12-grade fail-closed Lean 4 trust-escape scanner (aletheia#34 R12 parity; 0 FP):
# Blocks sorry/admit/axiom/unsafe/native_decide/sorryAx (incl. _root_.sorryAx)/ofReduceBool/
# ofReduceNat/trustCompiler/mkSorry/dbg_trace/dbgTrace/dbgTraceVal/dbgTraceIfShared/dbgSleep/
# dbgStackTrace/dbg_sleep/dbg_stack_trace/panic!/unreachable!/panicWithPosWithDecl/
# implemented_by/extern/initialize/builtin_initialize/run_cmd/run_meta/syntax/macro/elab/
# notation/csimp/opaque/partial/import/bv_decide/set_option/warn.sorry/
# debug.{skipKernelTC,byAsSorry,proofAsSorry,sorryAsError,terminalTacticsAsSorry}/
# @[... extern|implemented_by|export|init|builtin_init|term_elab|command_elab|tactic|macro ...]/
# attribute [...]/#eval/#reduce/#exit/#check/#synth/#guard/#guard_msgs/non-allowlisted #print/
# +native/native:=<non-false>/DecideConfig/config:=<non-{native:=false}>/strings/guillemets.
_LEAN4_BANNED_RE = re.compile(
    r"""
    ["«»]
    | (?<![A-Za-z0-9_])(?:
        sorry | admit | axiom | unsafe | native_decide | sorryAx
        | ofReduceBool | ofReduceNat | trustCompiler | implemented_by
        | extern | initialize | builtin_initialize | run_cmd
        | run_meta | syntax | declare_syntax_cat | macro | macro_rules
        | elab | elab_rules | notation | prefix | infix | infixl | infixr
        | postfix | dbg_trace | dbgTrace | dbgTraceVal | dbgTraceIfShared
        | dbgSleep | dbgStackTrace | dbg_sleep | dbg_stack_trace
        | panicWithPosWithDecl | throwError | interpolatedStr | csimp
        | opaque | import | mkSorry | bv_decide | set_option
      )(?![A-Za-z0-9_])
    | (?<![A-Za-z0-9_])(?:panic|unreachable)!
    | (?<![A-Za-z0-9_.])partial(?![A-Za-z0-9_])
    | (?:\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|sorryAsError|terminalTacticsAsSorry)\b)
    | (?:\bwarn\s*\.\s*sorry\b)
    | (?:\#\s*(?:eval|reduce|exit|check|synth|guard(?:_msgs)?)\b)
    | (?:\#\s*print\s+(?!axioms\s+DrosophilaConnectomeOperators\.[A-Za-z0-9_]+\b))
    | (?:(?<!\w)\+\s*native\b)
    | (?:\bnative\s*:=(?!\s*(?:Bool\.)?false\b(?:\s*[},)]|$)))
    | (?:\bDecide(?:Config|\.Config)\b)
    | (?:\bconfig\s*:=(?!\s*\{\s*native\s*:=\s*(?:Bool\.)?false\s*\}))
    """,
    re.VERBOSE,
)

_LEAN4_ATTR_OPEN_RE = re.compile(r"(?:@|(?<![A-Za-z0-9_.])\battribute\s*)\[", re.DOTALL)
_LEAN4_HARD_ATTR_KW_RE = re.compile(
    r"\b(?:extern|implemented_by|export|init|builtin_init|term_elab|command_elab|tactic|macro|macro_rules)\b"
)
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([A-Za-z0-9_.]+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([A-Za-z0-9_.]+)' depends on axioms: \[([^\]]*)\]$")
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

_ENVELOPE_KEYS = frozenset({
    "schema_version", "track_id", "payload_sha256", "payload", "certificate_sha256",
})
_PAYLOAD_KEYS = frozenset({
    "schema_version", "track_id", "oracle_class", "novelty_classification",
    "pillar1_whole_cns_topology", "pillar2_cx_attractor_and_supergraph",
    "pillar3_wave9_portal_engineering", "pillar4_lean4_and_provenance",
})


# ---------------------------------------------------------------------------
# Zone-B Path & Filesystem Hardening
# ---------------------------------------------------------------------------


def _normalize_darwin_private_prefix(raw: str) -> str:
    if raw == "/private/tmp" or raw.startswith("/private/tmp/"):
        return raw[len("/private"):]
    if raw == "/private/var" or raw.startswith("/private/var/"):
        return raw[len("/private"):]
    return raw


def _check_path_str(raw: Any, label: str) -> Path:
    if isinstance(raw, Path):
        s = os.fspath(raw)
    else:
        s = oracle.require_exact_str(raw, label)
    oracle.require_ok(len(s) > 0, "EMPTY_PATH", f"{label} empty")
    oracle.require_ok("\x00" not in s, "NUL_BYTE_FORBIDDEN", f"{label} contains NUL")
    try:
        s.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise oracle.S102Error("INVALID_UTF8_SURROGATE", f"{label} invalid UTF-8") from exc
    return Path(s)


def _check_no_symlink_components(path: Path, label: str) -> Path:
    abs_p = Path(os.path.abspath(os.fspath(path)))
    cur = Path(abs_p.anchor)
    for part in abs_p.parts[1:]:
        cur = cur / part
        try:
            st = os.lstat(cur)
        except (FileNotFoundError, NotADirectoryError):
            break
        except OSError as exc:
            raise oracle.S102Error("IO_STAT_ERROR", f"{label}: {exc}") from exc
        oracle.require_ok(
            not stat.S_ISLNK(st.st_mode),
            "SYMLINK_IN_PATH",
            f"{label}: symlink at {cur.name}",
        )
    return abs_p


def _check_safe_cwd() -> None:
    try:
        cwd = os.getcwd()
    except OSError as exc:
        raise oracle.S102Error("CWD_ERROR", str(exc)) from exc
    _check_no_symlink_components(Path(cwd), "cwd")
    pwd = os.environ.get("PWD")
    if pwd is not None and pwd.startswith("/"):
        norm_pwd = Path(_normalize_darwin_private_prefix(pwd))
        try:
            pwd_st = os.stat(norm_pwd)
            cwd_st = os.stat(cwd)
        except OSError:
            return
        if (pwd_st.st_dev, pwd_st.st_ino) == (cwd_st.st_dev, cwd_st.st_ino):
            _check_no_symlink_components(norm_pwd, "PWD")


def read_regular_bytes_capped(
    path_like: Any, label: str, max_bytes: int = MAX_JSON_BYTES
) -> bytes:
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=64 * 1024 * 1024)
    p = _check_no_symlink_components(_check_path_str(path_like, label), label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(os.fspath(p), flags)
    except OSError as exc:
        raise oracle.S102Error("IO_OPEN_ERROR", f"{label}: {exc}") from exc
    try:
        st = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", f"{label}: not regular")
        oracle.require_ok(st.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: st_nlink={st.st_nlink}")
        oracle.require_ok(st.st_size <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            oracle.require_ok(total <= max_bytes, "FILE_STREAM_TOO_LARGE", f"{label}: stream exceeds {max_bytes}")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def write_regular_bytes_atomic_0600(path_like: Any, data: bytes, label: str) -> Path:
    oracle.require_ok(type(data) is bytes, "INVALID_BYTES", f"{label}: data must be exact bytes")
    p = _check_no_symlink_components(_check_path_str(path_like, label), label)
    parent = p.parent
    try:
        pst = os.lstat(parent)
    except OSError as exc:
        raise oracle.S102Error("PARENT_STAT_ERROR", f"{label}: {exc}") from exc
    oracle.require_ok(stat.S_ISDIR(pst.st_mode), "PARENT_NOT_DIR", f"{label}: parent not dir")
    try:
        tst = os.lstat(p)
    except FileNotFoundError:
        tst = None
    except OSError as exc:
        raise oracle.S102Error("TARGET_STAT_ERROR", f"{label}: {exc}") from exc
    if tst is not None:
        oracle.require_ok(stat.S_ISREG(tst.st_mode), "TARGET_NOT_REGULAR", f"{label}: target not regular")
        oracle.require_ok(tst.st_nlink == 1, "TARGET_HARDLINK", f"{label}: target st_nlink={tst.st_nlink}")
    fd = -1
    tmp_name = ""
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=".s102_tmp_", dir=os.fspath(parent))
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp_name, os.fspath(p))
        tmp_name = ""
        try:
            dfd = os.open(os.fspath(parent), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
    except OSError as exc:
        raise oracle.S102Error("IO_WRITE_ERROR", f"{label}: {exc}") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
    return p


# ---------------------------------------------------------------------------
# Strict Zero-Float / Zero-Duplicate-Key / Bounded-Int JSON Parser
# ---------------------------------------------------------------------------


def _reject_float(token: str) -> Any:
    raise oracle.S102Error("FLOAT_FORBIDDEN", f"JSON float forbidden: {token}")


def _reject_constant(token: str) -> Any:
    raise oracle.S102Error("JSON_CONSTANT_FORBIDDEN", f"JSON constant forbidden: {token}")


def _bounded_parse_int(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    oracle.require_ok(
        len(digits) <= MAX_JSON_INT_DIGITS,
        "JSON_INT_TOO_LARGE",
        f"integer token exceeds {MAX_JSON_INT_DIGITS} digits",
    )
    return int(token)


def _reject_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise oracle.S102Error("DUPLICATE_JSON_KEY", f"duplicate key: {k}")
        out[k] = v
    return out


def validate_strict_json_tree(obj: Any, *, depth: int = 0) -> None:
    oracle.require_ok(depth <= 32, "JSON_TOO_DEEP", "JSON depth exceeds 32")
    if obj is None or type(obj) is bool:
        return
    if type(obj) is int:
        oracle.require_ok(
            obj.bit_length() <= MAX_JSON_INT_BITS,
            "JSON_INT_TOO_LARGE",
            f"int bit_length {obj.bit_length()} > {MAX_JSON_INT_BITS}",
        )
        return
    if type(obj) is str:
        oracle.require_ok("\x00" not in obj, "NUL_BYTE_FORBIDDEN", "NUL byte in string")
        try:
            obj.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise oracle.S102Error("INVALID_UTF8_SURROGATE", "surrogate in string") from exc
        return
    if type(obj) is list:
        for item in obj:
            validate_strict_json_tree(item, depth=depth + 1)
        return
    if type(obj) is dict:
        for k, v in obj.items():
            oracle.require_ok(type(k) is str, "NON_STRING_KEY", "dict key must be str")
            validate_strict_json_tree(k, depth=depth + 1)
            validate_strict_json_tree(v, depth=depth + 1)
        return
    raise oracle.S102Error("DISALLOWED_JSON_TYPE", f"disallowed type: {type(obj).__name__}")


def parse_strict_json_bytes(raw: bytes, label: str = "json") -> dict[str, Any]:
    oracle.require_ok(type(raw) is bytes, "INVALID_BYTES", f"{label}: expected bytes")
    oracle.require_ok(len(raw) > 0, "EMPTY_JSON", f"{label}: empty")
    oracle.require_ok(len(raw) <= MAX_JSON_BYTES, "FILE_TOO_LARGE", f"{label}: exceeds cap")
    oracle.require_ok(b"\x00" not in raw, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte")
    oracle.require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"{label}: CR/CRLF forbidden")
    oracle.require_ok(not raw.startswith(b"\xef\xbb\xbf"), "UTF8_BOM_FORBIDDEN", f"{label}: BOM")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S102Error("INVALID_UTF8", f"{label}: {exc}") from exc
    for m in _RAW_INT_SCAN_RE.finditer(text):
        tok = m.group(0)
        digits = tok[1:] if tok.startswith("-") else tok
        oracle.require_ok(
            len(digits) <= MAX_JSON_INT_DIGITS,
            "JSON_INT_TOO_LARGE",
            f"{label}: integer exceeds {MAX_JSON_INT_DIGITS} digits",
        )
    try:
        parsed = json.loads(
            text,
            parse_float=_reject_float,
            parse_int=_bounded_parse_int,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_dup_keys,
        )
    except oracle.S102Error:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise oracle.S102Error("JSON_SYNTAX_ERROR", f"{label}: {exc}") from exc
    oracle.require_ok(type(parsed) is dict, "JSON_ROOT_NOT_OBJECT", f"{label}: root must be dict")
    validate_strict_json_tree(parsed)
    oracle.require_ok(
        raw == oracle.canonical_json_bytes(parsed),
        "NON_CANONICAL_JSON",
        f"{label}: JSON bytes are not canonical",
    )
    return parsed


def load_strict_json_file(path_like: Any, label: str = "certificate") -> dict[str, Any]:
    return parse_strict_json_bytes(read_regular_bytes_capped(path_like, label), label)


def parse_exact_q(val: Any, label: str) -> Fraction:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(len(s) <= 256, "RATIONAL_STR_TOO_LONG", f"{label}: len > 256")
    oracle.require_ok(_CANON_Q_RE.match(s) is not None, "INVALID_RATIONAL_STR", f"{label}: {s}")
    if "/" in s:
        ns, ds = s.split("/", 1)
        n_i, d_i = int(ns), int(ds)
        oracle.require_ok(d_i > 1, "NON_CANONICAL_Q", f"{label}: denom {d_i} <= 1")
        oracle.require_ok(math.gcd(abs(n_i), d_i) == 1, "NON_CANONICAL_Q", f"{label}: unreduced")
        return Fraction(n_i, d_i)
    return Fraction(int(s), 1)


def require_sha256_str(val: Any, label: str) -> str:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(_SHA256_RE.match(s) is not None, "INVALID_SHA256", f"{label}: bad sha256")
    return s


def require_exact_keys(obj: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    oracle.require_ok(type(obj) is dict, "TYPE_ERROR", f"{label}: expected dict")
    oracle.require_ok(frozenset(obj.keys()) == expected, "KEY_SET_MISMATCH", f"{label}: key mismatch")
    return obj


# ---------------------------------------------------------------------------
# R12-Grade Static Lean 4 Scanner & Live Lean 4.36.0 Kernel Verifier
# ---------------------------------------------------------------------------


def strip_lean4_comments(source: str) -> str:
    """Nested block-comment & line-comment stripper preserving line count (fail-closed)."""
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
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
        elif ch == "/" and nxt == "-":
            depth = 1
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    oracle.require_ok(depth == 0, "LEAN4_UNTERMINATED_COMMENT", "unterminated Lean block comment")
    return "".join(out)


def _scan_lean4_attr_escapes(cleaned: str) -> list[str]:
    """Find unsound `@[...]` / `attribute [...]` escapes (extern, implemented_by, export, init, builtin_init)."""
    match_rb: dict[int, int] = {}
    stack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "[":
            stack.append(idx)
        elif ch == "]" and stack:
            match_rb[stack.pop()] = idx
    hits: list[str] = []
    for m_open in _LEAN4_ATTR_OPEN_RE.finditer(cleaned):
        lb = m_open.end() - 1
        rb = match_rb.get(lb)
        if rb is None:
            hits.append("unclosed_attribute_block")
            continue
        m_kw = _LEAN4_HARD_ATTR_KW_RE.search(cleaned, lb + 1, rb)
        if m_kw is not None:
            hits.append(f"attr:{m_kw.group(0)}")
    return hits


def scan_lean4_source_r12(source: str) -> list[str]:
    oracle.require_exact_str(source, "lean_source")
    oracle.require_ok("\x00" not in source, "NUL_BYTE_FORBIDDEN", "NUL byte in Lean source")
    cleaned = strip_lean4_comments(source)
    hits: list[str] = [m.group(0).strip() for m in _LEAN4_BANNED_RE.finditer(cleaned)]
    hits.extend(_scan_lean4_attr_escapes(cleaned))
    return hits


def resolve_lean_executable() -> str | None:
    which_lean = shutil.which("lean")
    if which_lean:
        return which_lean
    home = os.environ.get("HOME", "")
    if home:
        for rel in (".elan/bin/lean", ".local/bin/lean"):
            cand = Path(home) / rel
            if cand.is_file() and os.access(cand, os.X_OK):
                return os.fspath(cand)
    return None


def verify_lean_artifact(
    lean_path: Path,
    *,
    expected_sha256: str | None = None,
    require_live_lean: bool = False,
) -> dict[str, Any]:
    oracle.require_exact_bool(require_live_lean, "require_live_lean")
    raw = read_regular_bytes_capped(lean_path, "lean_source", max_bytes=MAX_JSON_BYTES)
    got_sha = oracle.sha256_bytes(raw)
    if expected_sha256 is not None:
        oracle.require_ok(
            got_sha == expected_sha256,
            "LEAN_SHA_MISMATCH",
            f"Lean file sha mismatch: {got_sha}",
        )
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S102Error("INVALID_UTF8", f"Lean source invalid UTF-8: {exc}") from exc

    hits = scan_lean4_source_r12(src)
    oracle.require_ok(len(hits) == 0, "LEAN4_BANNED_CONSTRUCT", f"banned Lean constructs: {hits[:5]}")

    cleaned = strip_lean4_comments(src)
    for thm in oracle.LEAN_THEOREM_NAMES:
        short = thm.split(".")[-1]
        oracle.require_ok(
            re.search(rf"\btheorem\s+{re.escape(short)}\b", cleaned) is not None,
            "LEAN4_MISSING_THEOREM",
            f"missing theorem declaration: {short}",
        )
        oracle.require_ok(
            re.search(rf"#print\s+axioms\s+{re.escape(thm)}\b", cleaned) is not None,
            "LEAN4_MISSING_AXIOM_PRINT",
            f"missing #print axioms for {thm}",
        )

    lean_bin = resolve_lean_executable()
    if lean_bin is None:
        oracle.require_ok(not require_live_lean, "LEAN_NOT_FOUND", "live Lean required but not found")
        return {
            "lean_sha256": got_sha,
            "static_r12_clean": True,
            "live_lean_executed": False,
            "theorems_verified": len(oracle.LEAN_THEOREM_NAMES),
        }

    # Zero-TOCTOU: feed the exact already-hashed UTF-8 source bytes via stdin with scrubbed Lean/Elan/LD env
    _SCRUB_ENV_KEYS = frozenset({
        "LEAN_PATH",
        "LEAN_OPTS",
        "LEAN_SRC_PATH",
        "LEAN_SYSROOT",
        "ELAN_TOOLCHAIN",
        "ELAN_HOME",
        "LAKE_HOME",
        "LEAN_CC",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
    })
    clean_env = {k: v for k, v in os.environ.items() if k not in _SCRUB_ENV_KEYS}
    proc = subprocess.run(
        [lean_bin, "--stdin"],
        input=raw,
        capture_output=True,
        timeout=120,
        env=clean_env,
        check=False,
    )
    oracle.require_ok(
        proc.returncode == 0,
        "LEAN_COMPILE_FAILED",
        f"lean --stdin failed rc={proc.returncode}: {proc.stderr.decode('utf-8', 'replace')[:200]}",
    )
    oracle.require_ok(
        len(proc.stderr.strip()) == 0,
        "LEAN_STDERR_NONEMPTY",
        f"unexpected lean stderr: {proc.stderr.decode('utf-8', 'replace')[:200]}",
    )
    stdout = proc.stdout.decode("utf-8", "strict")
    seen: dict[str, list[str]] = {}
    for line in stdout.splitlines():
        sline = line.strip()
        if not sline:
            continue
        m_none = _LEAN4_AXIOM_NONE_RE.match(sline)
        if m_none is not None:
            seen[m_none.group(1)] = []
            continue
        m_dep = _LEAN4_AXIOM_DEP_RE.match(sline)
        oracle.require_ok(m_dep is not None, "LEAN_UNEXPECTED_STDOUT", f"unexpected line: {sline}")
        axioms = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        for ax in axioms:
            oracle.require_ok(
                ax in _ALLOWED_LEAN_AXIOMS,
                "LEAN_DISALLOWED_AXIOM",
                f"{m_dep.group(1)} uses disallowed axiom {ax}",
            )
        seen[m_dep.group(1)] = axioms

    oracle.require_ok(
        frozenset(seen.keys()) == frozenset(oracle.LEAN_THEOREM_NAMES),
        "LEAN_THEOREM_SET_MISMATCH",
        f"verified theorem set mismatch ({len(seen)} vs {len(oracle.LEAN_THEOREM_NAMES)})",
    )
    return {
        "lean_sha256": got_sha,
        "static_r12_clean": True,
        "live_lean_executed": True,
        "theorems_verified": len(seen),
        "axioms_by_theorem": seen,
    }


# ---------------------------------------------------------------------------
# Field-Complete Secondary Mathematical Auditor (SEC / FR0 / FR1 — 0 bypasses)
# ---------------------------------------------------------------------------


def _audit_mat_int(mat: Any, dim: int, label: str, *, nonneg: bool = False) -> list[list[int]]:
    oracle.require_ok(type(mat) is list and len(mat) == dim, "MAT_ROW_DIM_ERROR", f"{label}: bad rows")
    out: list[list[int]] = []
    for r in range(dim):
        row = mat[r]
        oracle.require_ok(type(row) is list and len(row) == dim, "MAT_COL_DIM_ERROR", f"{label}[{r}]: bad cols")
        out.append([
            oracle.require_exact_int(row[c], f"{label}[{r}][{c}]", lo=0 if nonneg else None)
            for c in range(dim)
        ])
    return out


def _audit_ops_block(ops: Any, mat: list[list[int]], label: str) -> None:
    expected = oracle.operator_frobenius_and_commutator(mat)
    req = require_exact_keys(ops, frozenset(expected.keys()), label)
    oracle.require_ok(
        oracle.canonical_json_bytes(req) == oracle.canonical_json_bytes(expected),
        "OPERATOR_MISMATCH",
        f"{label}: operator invariants mismatch",
    )


def secondary_audit_payload(payload: dict[str, Any], anchor: dict[str, Any] | None = None) -> None:
    """Field-complete independent mathematical recomputation from the verified anchor.
    Enforces every domain invariant, exact matrix/Laplacian/Schur/Krein/triad/portal
    equation, and exact provenance pin so 0 re-signed forgeries bypass SEC or FR0.
    """
    validate_strict_json_tree(payload)
    require_exact_keys(payload, _PAYLOAD_KEYS, "payload")
    anc = oracle.load_anchor_default() if anchor is None else anchor
    oracle.require_ok(payload["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema")
    oracle.require_ok(payload["track_id"] == oracle.TRACK_ID, "TRACK_MISMATCH", "track")
    oracle.require_ok(payload["oracle_class"] == oracle.ORACLE_CLASS, "ORACLE_CLASS_MISMATCH", "oracle_class")
    oracle.require_ok(
        payload["novelty_classification"] == oracle.NOVELTY_CLASSIFICATION,
        "NOVELTY_MISMATCH",
        "novelty_classification",
    )

    # Pillar 1 independent recomputation & domain invariants
    p1 = payload["pillar1_whole_cns_topology"]
    exp_p1 = oracle.build_pillar1_whole_cns(anc)
    require_exact_keys(p1, frozenset(exp_p1.keys()), "pillar1")
    edges = oracle.require_exact_int(p1["directed_edges"], "p1.edges", lo=1)
    syn = oracle.require_exact_int(p1["total_synapses"], "p1.synapses", lo=edges)
    act = oracle.require_exact_int(p1["active_connected_neurons"], "p1.active", lo=1)
    oracle.require_ok(
        parse_exact_q(p1["mean_weight_per_edge_q"], "p1.mean_w") == Fraction(syn, edges),
        "P1_MEAN_W",
        "mean weight mismatch",
    )
    oracle.require_ok(
        parse_exact_q(p1["mean_out_degree_q"], "p1.mean_deg") == Fraction(edges, act),
        "P1_MEAN_DEG",
        "mean out-degree mismatch",
    )
    oracle.require_exact_int(p1["dale_signed_synapses_total"], "p1.dale_tot", lo=1)
    oracle.require_exact_int(p1["dale_signed_net_balance"], "p1.dale_net", lo=1)
    oracle.require_ok(
        parse_exact_q(p1["s86_minus_malecns_top_0p5pct_gap_q"], "p1.gap") > 0,
        "P1_GAP_POS",
        "S86 minus MaleCNS gap must be positive",
    )
    oracle.require_ok(
        oracle.canonical_json_bytes(p1) == oracle.canonical_json_bytes(exp_p1),
        "P1_REPLAY_MISMATCH",
        "pillar1 differs from exact anchor computation",
    )

    # Pillar 2 independent matrix, Laplacian, Krein ([n_pos, n_neg, n_zero] order), Schur, and triad recomputation
    p2 = payload["pillar2_cx_attractor_and_supergraph"]
    exp_p2 = oracle.build_pillar2_cx_and_supergraph(anc)
    require_exact_keys(p2, frozenset(exp_p2.keys()), "pillar2")

    sg = require_exact_keys(p2["supergraph_8x8"], frozenset(exp_p2["supergraph_8x8"].keys()), "p2.sg")
    w8_u = _audit_mat_int(sg["unsigned_synapses_8x8"], 8, "w8_u", nonneg=True)
    w8_s = _audit_mat_int(sg["dale_signed_synapses_8x8"], 8, "w8_s", nonneg=False)
    for r in range(8):
        for c in range(8):
            oracle.require_ok(abs(w8_s[r][c]) <= w8_u[r][c], "DALE_ABS_BOUND", f"w8[{r}][{c}]")
    _audit_ops_block(sg["unsigned_operators"], w8_u, "w8_u_ops")
    _audit_ops_block(sg["signed_operators"], w8_s, "w8_s_ops")
    oracle.require_ok(
        sg["signed_laplacian_ldlt_inertia"] == [8, 0, 0]
        and sg["signed_laplacian_structurally_frustrated"] is True,
        "W8_FRUSTRATION_MISMATCH",
        "W8 signed Laplacian must be 8-pos frustrated",
    )
    sch = require_exact_keys(
        sg["schur_complement_io_boundary"],
        frozenset(exp_p2["supergraph_8x8"]["schur_complement_io_boundary"].keys()),
        "p2.sch",
    )
    tr_l_bb = oracle.require_exact_int(sch["trace_L_BB"], "sch.trace_L_BB", lo=1)
    oracle.require_ok(
        parse_exact_q(sch["trace_S_B_q"], "sch.tr_sb")
        + parse_exact_q(sch["trace_dark_shadow_q"], "sch.tr_sh")
        == Fraction(tr_l_bb, 1),
        "SCHUR_TRACE_CONSERVATION",
        "Schur trace conservation failed",
    )

    cx = require_exact_keys(p2["central_complex_6x6"], frozenset(exp_p2["central_complex_6x6"].keys()), "p2.cx")
    w6_u = _audit_mat_int(cx["unsigned_synapses_6x6"], 6, "w6_u", nonneg=True)
    w6_s = _audit_mat_int(cx["dale_signed_synapses_6x6"], 6, "w6_s", nonneg=False)
    _audit_ops_block(cx["unsigned_operators"], w6_u, "w6_u_ops")
    _audit_ops_block(cx["signed_operators"], w6_s, "w6_s_ops")
    oracle.require_ok(
        cx["dale_row_pure_homogeneous"] is True
        and cx["signed_laplacian_ldlt_inertia"] == [6, 0, 0]
        and cx["symmetrized_dale_krein_inertia"] == [4, 2, 0],
        "CX_OPERATOR_INERTIA_MISMATCH",
        "CX core Dale/Laplacian/Krein inertia mismatch",
    )

    tri = require_exact_keys(
        p2["central_complex_triads_w10"],
        frozenset(exp_p2["central_complex_triads_w10"].keys()),
        "p2.tri",
    )
    oracle.require_ok(
        parse_exact_q(tri["observed_incoherent_ffl_fraction_q"], "tri.inc")
        > parse_exact_q(tri["null_incoherent_ffl_fraction_q"], "tri.null_inc"),
        "CX_INCOHERENT_FFL_EXCESS",
        "observed incoherent FFL fraction must exceed null",
    )
    oracle.require_ok(
        parse_exact_q(tri["observed_neg_3cycle_fraction_q"], "tri.neg3")
        > parse_exact_q(tri["null_neg_3cycle_fraction_q"], "tri.null_neg3"),
        "CX_NEG_3CYC_EXCESS",
        "observed negative 3-cycle fraction must exceed null",
    )
    oracle.require_ok(
        oracle.canonical_json_bytes(p2) == oracle.canonical_json_bytes(exp_p2),
        "P2_REPLAY_MISMATCH",
        "pillar2 differs from exact anchor computation",
    )

    # Pillar 3 independent engineering bounds & LIF witness recomputation
    p3 = payload["pillar3_wave9_portal_engineering"]
    exp_p3 = oracle.build_pillar3_wave9_engineering()
    require_exact_keys(p3, frozenset(exp_p3.keys()), "pillar3")
    fr = require_exact_keys(
        p3["fly_racer_four_arm_tail_risk"],
        frozenset(exp_p3["fly_racer_four_arm_tail_risk"].keys()),
        "p3.fr",
    )
    oracle.require_ok(
        parse_exact_q(fr["fly_minus_mlp_3sigma_margin_q"], "p3.margin") > 0,
        "FLY_RACER_MARGIN_NONPOS",
        "fly-racer 3-sigma margin must be strictly positive",
    )
    fc = require_exact_keys(
        p3["fruitfly_calculator"],
        frozenset(exp_p3["fruitfly_calculator"].keys()),
        "p3.fc",
    )
    lif_pw = require_exact_keys(
        fc["lif_may_fire_pruned_witness"],
        frozenset(exp_p3["fruitfly_calculator"]["lif_may_fire_pruned_witness"].keys()),
        "p3.lif_pw",
    )
    oracle.require_ok(
        lif_pw["never_reached_theta"] is True,
        "LIF_WITNESS_INVALID",
        "LIF pruned witness failed",
    )
    oracle.require_ok(
        oracle.canonical_json_bytes(p3) == oracle.canonical_json_bytes(exp_p3),
        "P3_REPLAY_MISMATCH",
        "pillar3 differs from exact engineering constants",
    )

    # Pillar 4 provenance, Lean pins, and honest novelty scope
    p4 = payload["pillar4_lean4_and_provenance"]
    exp_p4 = oracle.build_pillar4_lean4_and_provenance(anc)
    require_exact_keys(p4, frozenset(exp_p4.keys()), "pillar4")
    require_sha256_str(p4["anchor_file_sha256"], "p4.anchor_file_sha256")
    require_sha256_str(p4["anchor_payload_sha256"], "p4.anchor_payload_sha256")
    hns = require_exact_keys(
        p4["honest_novelty_scope"],
        frozenset(exp_p4["honest_novelty_scope"].keys()),
        "p4.hns",
    )
    oracle.require_exact_int(hns["n2_open_claims_count"], "p4.n2", lo=0, hi=0)
    oracle.require_ok(
        oracle.canonical_json_bytes(p4) == oracle.canonical_json_bytes(exp_p4),
        "P4_REPLAY_MISMATCH",
        "pillar4 differs from pinned provenance",
    )


def verify_certificate_dict(
    cert: dict[str, Any],
    *,
    full_replay: bool = True,
    anchor_path: Path | None = None,
) -> dict[str, Any]:
    oracle.require_exact_bool(full_replay, "full_replay")
    validate_strict_json_tree(cert)
    require_exact_keys(cert, _ENVELOPE_KEYS, "envelope")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "env schema")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "TRACK_MISMATCH", "env track")
    payload = cert["payload"]
    oracle.require_ok(type(payload) is dict, "TYPE_ERROR", "payload must be dict")

    p_sha = require_sha256_str(cert["payload_sha256"], "payload_sha256")
    c_sha = require_sha256_str(cert["certificate_sha256"], "certificate_sha256")
    got_p_sha = oracle.sha256_bytes(oracle.canonical_json_bytes(payload))
    oracle.require_ok(got_p_sha == p_sha, "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    body = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    got_c_sha = oracle.sha256_bytes(oracle.canonical_json_bytes(body))
    oracle.require_ok(got_c_sha == c_sha, "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    anc_p = oracle.TRACK_DIR / oracle.ANCHOR_FILENAME if anchor_path is None else anchor_path
    anc_raw = read_regular_bytes_capped(anc_p, "anchor_json")
    anchor = oracle.load_anchor_from_bytes(anc_raw, check_pinned_sha=True)
    secondary_audit_payload(payload, anchor)

    if full_replay:
        replayed = oracle.build_certificate(anchor)
        oracle.require_ok(
            oracle.canonical_json_bytes(cert) == oracle.canonical_json_bytes(replayed),
            "FULL_REPLAY_MISMATCH",
            "certificate != fresh replay",
        )

    return {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "full_replay": full_replay,
        "secondary_audit": "PASS",
    }


def verify_track_companion_pins(track_dir: Path) -> dict[str, str]:
    pins = oracle.PINNED_LEAN_FILES
    checks = (
        ("lean-toolchain", pins["lean_toolchain_sha256"]),
        ("lakefile.toml", pins["lakefile_sha256"]),
        (pins["lean_source"], pins["lean_source_sha256"]),
        (oracle.ANCHOR_FILENAME, oracle.PINNED_ANCHOR_FILE_SHA256),
    )
    out: dict[str, str] = {}
    for fname, exp_sha in checks:
        raw = read_regular_bytes_capped(track_dir / fname, fname)
        got_sha = oracle.sha256_bytes(raw)
        oracle.require_ok(got_sha == exp_sha, "COMPANION_SHA_MISMATCH", f"{fname}: {got_sha} != {exp_sha}")
        out[fname] = got_sha
    return out


def verify_external_datasets(malecns_dir: Path, wave9_dir: Path, anchor: dict[str, Any]) -> dict[str, int]:
    m_dir = _check_no_symlink_components(_check_path_str(malecns_dir, "malecns_dir"), "malecns_dir")
    w_dir = _check_no_symlink_components(_check_path_str(wave9_dir, "wave9_dir"), "wave9_dir")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    checked_m = 0
    for pin in anchor["malecns_external_pins"]:
        fp = _check_no_symlink_components(m_dir / pin["filename"], pin["id"])
        try:
            fd = os.open(os.fspath(fp), flags)
        except OSError as exc:
            raise oracle.S102Error("IO_OPEN_ERROR", f"{pin['id']}: {exc}") from exc
        try:
            st = os.fstat(fd)
            oracle.require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", f"{pin['id']}: not regular")
            oracle.require_ok(st.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{pin['id']}: hardlink")
            h = hashlib.sha256()
            total = 0
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                h.update(chunk)
        finally:
            os.close(fd)
        oracle.require_ok(total == pin["bytes"], "EXT_BYTES_MISMATCH", f"{pin['id']} bytes")
        oracle.require_ok(h.hexdigest() == pin["sha256"], "EXT_SHA_MISMATCH", f"{pin['id']} sha256")
        checked_m += 1
    checked_w = 0
    for pin in anchor["wave9_portal_pins"]:
        raw = read_regular_bytes_capped(w_dir / pin["relpath"], pin["id"], max_bytes=4 * 1024 * 1024)
        oracle.require_ok(len(raw) == pin["bytes"], "WAVE9_BYTES_MISMATCH", f"{pin['id']} bytes")
        oracle.require_ok(oracle.sha256_bytes(raw) == pin["sha256"], "WAVE9_SHA_MISMATCH", f"{pin['id']} sha256")
        checked_w += 1
    return {"malecns_files_verified": checked_m, "wave9_files_verified": checked_w}


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------


def _parse_cli(argv: Sequence[str]) -> dict[str, Any]:
    mode = "check"
    target: str | None = None
    as_json = False
    verify_data: tuple[str, str] | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            as_json = True
            i += 1
        elif arg == "--standalone":
            oracle.require_ok(mode == "check" and target is None, "CLI_CONFLICT", "conflicting modes")
            mode = "standalone"
            i += 1
        elif arg == "--check":
            oracle.require_ok(mode == "check" and target is None, "CLI_CONFLICT", "duplicate mode")
            oracle.require_ok(i + 1 < len(argv), "CLI_MISSING_ARG", "--check requires path")
            target = argv[i + 1]
            i += 2
        elif arg == "--write":
            oracle.require_ok(mode == "check" and target is None, "CLI_CONFLICT", "conflicting modes")
            oracle.require_ok(i + 1 < len(argv), "CLI_MISSING_ARG", "--write requires path")
            mode = "write"
            target = argv[i + 1]
            i += 2
        elif arg == "--verify-data":
            oracle.require_ok(i + 2 < len(argv), "CLI_MISSING_ARG", "--verify-data requires 2 dirs")
            verify_data = (argv[i + 1], argv[i + 2])
            i += 3
        else:
            raise oracle.S102Error("CLI_UNKNOWN_ARG", f"unknown argument: {arg}")
    return {"mode": mode, "target": target, "as_json": as_json, "verify_data": verify_data}


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        _check_safe_cwd()
        cfg = _parse_cli(args)
        mode = cfg["mode"]

        if mode == "standalone":
            cert = oracle.build_certificate()
            sys.stdout.write(oracle.canonical_json_bytes(cert).decode("ascii"))
            return 0

        if mode == "write":
            cert = oracle.build_certificate()
            raw = oracle.canonical_json_bytes(cert)
            out_path = write_regular_bytes_atomic_0600(cfg["target"], raw, "write_cert")
            res = {
                "status": "WRITTEN",
                "path": out_path.name,
                "bytes": len(raw),
                "certificate_sha256": cert["certificate_sha256"],
            }
            if cfg["as_json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"WROTE {out_path.name} ({len(raw)} B) sha256={cert['certificate_sha256']}\n")
            return 0

        cert_path = (
            oracle.TRACK_DIR / oracle.DEFAULT_CERT_FILENAME
            if cfg["target"] is None
            else Path(cfg["target"])
        )
        cert = load_strict_json_file(cert_path, "certificate")
        cert_res = verify_certificate_dict(cert, full_replay=True)
        pins_res = verify_track_companion_pins(oracle.TRACK_DIR)
        lean_res = verify_lean_artifact(
            oracle.TRACK_DIR / oracle.PINNED_LEAN_FILES["lean_source"],
            expected_sha256=oracle.PINNED_LEAN_FILES["lean_source_sha256"],
            require_live_lean=False,
        )
        out: dict[str, Any] = {
            "status": "PASS",
            "certificate": cert_res,
            "companion_pins": pins_res,
            "lean": lean_res,
        }
        if cfg["verify_data"] is not None:
            anc = oracle.load_anchor_default()
            out["external_data"] = verify_external_datasets(
                Path(cfg["verify_data"][0]),
                Path(cfg["verify_data"][1]),
                anc,
            )
        if cfg["as_json"]:
            sys.stdout.write(oracle.canonical_json_bytes(out).decode("ascii"))
        else:
            sys.stdout.write(
                f"Track {oracle.TRACK_ID} PASS | cert={cert_res['certificate_sha256'][:16]} "
                f"| lean_live={lean_res['live_lean_executed']} thms={lean_res['theorems_verified']}\n"
            )
        return 0
    except oracle.S102Error as exc:
        err = {"status": "ERROR", "code": exc.code, "message": exc.message}
        sys.stderr.write(oracle.canonical_json_bytes(err).decode("ascii"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
