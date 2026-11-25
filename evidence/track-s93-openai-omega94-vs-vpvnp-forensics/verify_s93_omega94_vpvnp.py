#!/usr/bin/env python3
"""Track S93: Zone-B Hardened Verifier, Fail-Closed Secondary Mathematical Auditor,
R12 Static Lean 4 Scanner (with end-anchored decide-native & attribute-escape
guards), and Live Lean 4.36.0 Kernel Verifier.

CLI modes:
  --check <path> [--json]   Verify certificate + full replay + live Lean 4.36.0
  --write <path> [--json]   Atomically write canonical certificate (0o600)
  --standalone              Emit canonical certificate JSON to stdout
  [--json]                  Default: check committed certificate in track dir
"""
from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
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

import s93_omega94_vpvnp_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 512 * 1024
MAX_JSON_INT_DIGITS = 80
MAX_RATIONAL_STR_LEN = 256
_CANON_INT_RE = re.compile(r"^(?:0|-?[1-9][0-9]*)$")
_CANON_Q_RE = re.compile(r"^(?:0|-?[1-9][0-9]*)(?:/[1-9][0-9]*)?$")
_RAW_INT_SCAN_RE = re.compile(r"(?<![A-Za-z0-9_.\"])-?[0-9]+(?![A-Za-z0-9_.\"])")

# R12 fail-closed Lean 4 trust-escape scanner (zero bypasses, zero FP)
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
    | (?:\#\s*print\s+(?!axioms\s+OmegaNineFourthsAndSpectrum\.[A-Za-z0-9_]+\b))
    | (?:(?<!\w)\+\s*native\b)
    | (?:\bnative\s*:=(?!\s*(?:Bool\.)?false\b(?:\s*[},)]|$)))
    | (?:\bDecide(?:Config|\.Config)\b)
    | (?:\bconfig\s*:=(?!\s*\{\s*native\s*:=\s*(?:Bool\.)?false\s*\}))
    | (?:\bLean\s*\.)
    """,
    re.VERBOSE,
)
_LEAN4_ATTR_OPEN_RE = re.compile(r"(?:@|(?<![A-Za-z0-9_.])\battribute\s*)\[", re.DOTALL)
_LEAN4_HARD_ATTR_KW_RE = re.compile(
    r"\b(?:extern|implemented_by|export|init|builtin_init|term_elab|command_elab|tactic|macro|macro_rules|csimp)\b"
)
SAFE_LEAN_ENV_KEYS = frozenset({"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"})

_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([A-Za-z0-9_.]+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([A-Za-z0-9_.]+)' depends on axioms: \[([^\]]*)\]$")
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

_ENVELOPE_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "payload", "certificate_sha256"})
_PAYLOAD_KEYS = frozenset({
    "schema_version", "track_id", "oracle_class", "novelty_classification",
    "wave6_provenance", "upstream_expedition_bridges", "pinned_artifacts",
    "pillar1_openai_omega94", "pillar2_forensic_trust_audit",
    "pillar3_law5_reconciliation", "pillar4_pequalnp_barriers",
})
_PINNED_KEYS = frozenset({
    "lean_source", "lean_source_sha256", "lean_toolchain",
    "lean_toolchain_sha256", "lakefile_sha256",
    "lean_theorem_count", "lean_theorem_names",
})
_PROV_KEYS = frozenset({
    "openai_math_repo", "openai_math_commit", "openai_math_toolchain",
    "pequalnp_repo", "pequalnp_commit", "pequalnp_toolchain",
    "pinned_sources_count", "pinned_sources",
})
_SRC_KEYS = frozenset({"id", "repo", "relpath", "bytes", "sha256", "role"})
_UP_KEYS = frozenset({"track", "cert_file", "cert_sha256", "bridge"})


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
        raise oracle.S93Error("INVALID_UTF8_SURROGATE", f"{label} invalid UTF-8") from exc
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
            raise oracle.S93Error("IO_STAT_ERROR", f"{label}: {exc}") from exc
        oracle.require_ok(not stat.S_ISLNK(st.st_mode), "SYMLINK_IN_PATH", f"{label}: symlink at {cur.name}")
    return abs_p


def _check_safe_cwd() -> None:
    try:
        cwd = os.getcwd()
    except OSError as exc:
        raise oracle.S93Error("CWD_ERROR", str(exc)) from exc
    _check_no_symlink_components(Path(cwd), "cwd")
    pwd = os.environ.get("PWD")
    if pwd is not None and pwd.startswith("/"):
        norm_pwd = Path(_normalize_darwin_private_prefix(pwd))
        try:
            pwd_st = os.stat(norm_pwd)
            cwd_st = os.stat(cwd)
        except OSError:
            return
        if pwd_st.st_dev == cwd_st.st_dev and pwd_st.st_ino == cwd_st.st_ino:
            _check_no_symlink_components(norm_pwd, "PWD")


def read_regular_bytes_capped(path_like: Any, label: str, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=64 * 1024 * 1024)
    p = _check_no_symlink_components(_check_path_str(path_like, label), label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(os.fspath(p), flags)
    except OSError as exc:
        raise oracle.S93Error("IO_OPEN_ERROR", f"{label}: {exc}") from exc
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
            oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: stream exceeds {max_bytes}")
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
        raise oracle.S93Error("PARENT_MISSING", f"{label}: parent unavailable") from exc
    oracle.require_ok(stat.S_ISDIR(pst.st_mode), "PARENT_NOT_DIR", f"{label}: parent not dir")
    try:
        tst = os.lstat(p)
    except FileNotFoundError:
        tst = None
    except OSError as exc:
        raise oracle.S93Error("IO_STAT_ERROR", f"{label}: target stat failed") from exc
    if tst is not None:
        oracle.require_ok(stat.S_ISREG(tst.st_mode), "TARGET_NOT_REGULAR", f"{label}: target not regular")
        oracle.require_ok(tst.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: target st_nlink={tst.st_nlink}")

    dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        dfd = os.open(os.fspath(parent), dir_flags)
    except OSError as exc:
        raise oracle.S93Error("IO_OPEN_ERROR", f"{label}: dir open failed") from exc

    tmp_path: Path | None = None
    try:
        fd, tmp_str = tempfile.mkstemp(prefix=".s93_tmp_", dir=os.fspath(parent))
        tmp_path = Path(tmp_str)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            written = 0
            while written < len(view):
                n = os.write(fd, view[written:])
                oracle.require_ok(n > 0, "IO_WRITE_ERROR", f"{label}: short write")
                written += n
            os.fsync(fd)
            tmp_st = os.fstat(fd)
            oracle.require_ok(stat.S_ISREG(tmp_st.st_mode) and tmp_st.st_nlink == 1, "TMP_TAMPERED", f"{label}: tmp tampered")
        finally:
            os.close(fd)
        os.replace(tmp_path.name, p.name, src_dir_fd=dfd, dst_dir_fd=dfd)
        tmp_path = None
        os.fsync(dfd)
        return p
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path.name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Strict Zero-Float Canonical JSON & Rational Parsers
# ---------------------------------------------------------------------------

def _reject_json_float(raw: str) -> Any:
    raise oracle.S93Error("FORBIDDEN_JSON_FLOAT", f"float literal forbidden: {raw[:24]}")


def _reject_json_const(raw: str) -> Any:
    raise oracle.S93Error("FORBIDDEN_JSON_CONST", f"non-standard constant forbidden: {raw[:24]}")


def _strict_int_parse(raw: str) -> int:
    digits = raw[1:] if raw.startswith("-") else raw
    oracle.require_ok(len(digits) <= MAX_JSON_INT_DIGITS, "JSON_INT_TOO_LARGE", f"int exceeds {MAX_JSON_INT_DIGITS} digits")
    oracle.require_ok(_CANON_INT_RE.match(raw) is not None, "INVALID_JSON_INT", "non-canonical int")
    return int(raw)


def _no_dup_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes, label: str, *, require_canonical: bool = True) -> Any:
    oracle.require_ok(type(raw) is bytes, "INVALID_BYTES", f"{label}: bytes required")
    oracle.require_ok(len(raw) <= MAX_JSON_BYTES, "JSON_TOO_LARGE", f"{label}: exceeds {MAX_JSON_BYTES}")
    oracle.require_ok(b"\r" not in raw and b"\x00" not in raw, "JSON_BAD_BYTES", f"{label}: CR or NUL forbidden")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise oracle.S93Error("NON_ASCII_JSON", f"{label}: non-ASCII JSON") from exc
    for m in _RAW_INT_SCAN_RE.finditer(text):
        tok = m.group(0)
        dig = tok[1:] if tok.startswith("-") else tok
        oracle.require_ok(len(dig) <= MAX_JSON_INT_DIGITS, "JSON_INT_TOO_LARGE", f"{label}: pre-parse int cap")
    try:
        obj = json.loads(
            text,
            parse_float=_reject_json_float,
            parse_int=_strict_int_parse,
            parse_constant=_reject_json_const,
            object_pairs_hook=_no_dup_object_pairs,
        )
    except oracle.S93Error:
        raise
    except (ValueError, RecursionError) as exc:
        raise oracle.S93Error("INVALID_JSON", f"{label}: {exc}") from exc
    oracle.validate_strict_json_tree(obj, label)
    if require_canonical:
        oracle.require_ok(oracle.canonical_json_bytes(obj) == raw, "NON_CANONICAL_JSON", f"{label}: non-canonical")
    return obj


def parse_canonical_rational_str(val: Any, label: str) -> Fraction:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(len(s) <= MAX_RATIONAL_STR_LEN, "RATIONAL_STR_TOO_LONG", f"{label}: rational string too long")
    oracle.require_ok(_CANON_Q_RE.match(s) is not None, "INVALID_RATIONAL_STR", f"{label}: bad rational {s[:32]}")
    if "/" in s:
        ns, ds = s.split("/", 1)
        num = int(ns)
        den = int(ds)
        oracle.require_ok(den > 1, "NON_CANONICAL_RATIONAL", f"{label}: denominator must be > 1")
        fr = Fraction(num, den)
        oracle.require_ok(fr.denominator == den, "NON_REDUCED_RATIONAL", f"{label}: not reduced")
        return fr
    return Fraction(int(s), 1)


def _require_exact_dict(val: Any, keys: frozenset[str], label: str) -> dict[str, Any]:
    oracle.require_ok(type(val) is dict, "INVALID_DICT", f"{label}: expected dict")
    oracle.require_ok(frozenset(val.keys()) == keys, "KEYSET_MISMATCH", f"{label}: keyset mismatch")
    return val


def _require_nonempty_str(val: Any, label: str) -> str:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(len(s) > 0, "EMPTY_STR", f"{label}: empty string")
    return s


# ---------------------------------------------------------------------------
# R10+ Static Lean 4 Scanner & Live Lean 4.36.0 Kernel Verifier
# ---------------------------------------------------------------------------

def _strip_lean4_for_static_gate(source: str) -> str:
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
            continue
        if ch == "/" and nxt == "-":
            depth = 1
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            out.append("  ")
            i += 2
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    oracle.require_ok(depth == 0, "LEAN4_UNTERMINATED_LEX", "unterminated Lean block comment")
    return "".join(out)


def _scan_lean4_attr_escapes(cleaned: str) -> list[str]:
    """Find unsound `@[...]` / `attribute [...]` escapes."""
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
        m_kw = _LEAN4_HARD_ATTR_KW_RE.search(cleaned, lb, rb)
        if m_kw is not None:
            hits.append(f"attr:{m_kw.group(0)}")
    return hits


def static_gate_lean4_source(source: str) -> None:
    s = oracle.require_exact_str(source, "lean_source")
    oracle.require_ok("\r" not in s and "\x00" not in s, "LEAN4_BAD_CHARS", "CR/NUL in Lean source")
    cleaned = _strip_lean4_for_static_gate(s)
    m = _LEAN4_BANNED_RE.search(cleaned)
    oracle.require_ok(m is None, "LEAN4_TRUST_ESCAPE", f"banned Lean construct: {m.group(0)!r}" if m else "")
    attr_hits = _scan_lean4_attr_escapes(cleaned)
    oracle.require_ok(len(attr_hits) == 0, "LEAN4_TRUST_ESCAPE", f"banned Lean attribute: {attr_hits[0]}" if attr_hits else "")
    for thm in oracle.LEAN_THEOREM_NAMES:
        short = thm.split(".")[-1]
        oracle.require_ok(
            re.search(rf"(?:^|\n)[ \t]*(?:(?:private|protected)\s+)*theorem\s+{re.escape(short)}\b", cleaned) is not None,
            "LEAN4_MISSING_THEOREM",
            f"missing {short}",
        )
        oracle.require_ok(f"#print axioms {thm}" in cleaned, "LEAN4_MISSING_PRINT_AXIOMS", f"missing #print axioms {thm}")


def resolve_lean_binary() -> str:
    """Resolve lean binary respecting os.environ['HOME'] (never /etc/passwd fallback)
    so bare `env -i PATH=/usr/bin:/bin` cleanly exercises the no-Lean CI path."""
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN")
    if env_bin is not None:
        oracle.require_exact_str(env_bin, "ALETHEIA_LEAN_BIN")
        p = Path(env_bin)
        oracle.require_ok(p.is_file() and os.access(str(p), os.X_OK), "LEAN_BINARY_UNAVAILABLE", "ALETHEIA_LEAN_BIN unusable")
        return str(p)
    found = shutil.which("lean")
    if found is not None and os.access(found, os.X_OK):
        return found
    env_home = os.environ.get("HOME")
    if env_home is not None and len(env_home) > 0:
        for rel in ((".local", "bin", "lean"), (".elan", "bin", "lean")):
            cand = Path(env_home).joinpath(*rel)
            if cand.is_file() and os.access(str(cand), os.X_OK):
                return str(cand)
    raise oracle.S93Error("LEAN_BINARY_UNAVAILABLE", "lean executable not found")


def verify_lean4_file_live(lean_path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_capped(lean_path, "lean_source", max_bytes=1024 * 1024)
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S93Error("INVALID_UTF8", "Lean source not UTF-8") from exc
    static_gate_lean4_source(src)
    lean_bin = resolve_lean_binary()
    clean_env = {k: v for k, v in os.environ.items() if k in SAFE_LEAN_ENV_KEYS}
    try:
        v_proc = subprocess.run([lean_bin, "--version"], capture_output=True, text=True, timeout=30, check=False, env=clean_env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise oracle.S93Error("LEAN_EXEC_ERROR", "lean --version failed") from exc
    oracle.require_ok(v_proc.returncode == 0 and "4.36.0" in v_proc.stdout, "LEAN_VERSION_MISMATCH", "Lean 4.36.0 required")
    try:
        proc = subprocess.run([lean_bin, "--stdin"], input=src, capture_output=True, text=True, timeout=120, check=False, env=clean_env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise oracle.S93Error("LEAN_EXEC_ERROR", "lean elaboration failed") from exc
    oracle.require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    oracle.require_ok(proc.stderr.strip() == "", "LEAN_STDERR_NONEMPTY", "lean stderr must be empty")
    oracle.require_ok("warning:" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning forbidden")

    joined_lines: list[str] = []
    pending = ""
    for raw_line in proc.stdout.splitlines():
        s_line = raw_line.strip()
        if not s_line:
            continue
        if pending:
            pending = f"{pending} {s_line}"
            if "]" in s_line:
                joined_lines.append(pending)
                pending = ""
        elif "[" in s_line and "]" not in s_line:
            pending = s_line
        else:
            joined_lines.append(s_line)
    oracle.require_ok(pending == "", "LEAN_UNEXPECTED_STDOUT", "unterminated axiom list")

    seen: dict[str, list[str]] = {}
    for s_line in joined_lines:
        m_none = _LEAN4_AXIOM_NONE_RE.match(s_line)
        if m_none is not None:
            thm_name = m_none.group(1)
            oracle.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate axiom line: {thm_name}")
            seen[thm_name] = []
            continue
        m_dep = _LEAN4_AXIOM_DEP_RE.match(s_line)
        oracle.require_ok(m_dep is not None, "LEAN_UNEXPECTED_STDOUT", f"unexpected lean line: {s_line[:80]}")
        thm_name = m_dep.group(1)
        oracle.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate axiom line: {thm_name}")
        axs = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        for ax in axs:
            oracle.require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"forbidden axiom {ax}")
        seen[thm_name] = axs
    oracle.require_ok(frozenset(seen.keys()) == frozenset(oracle.LEAN_THEOREM_NAMES), "LEAN_THEOREM_SET_MISMATCH", "axioms set mismatch")
    return {
        "lean_version": v_proc.stdout.strip().splitlines()[0],
        "theorems_verified": len(seen),
        "lean_source_sha256": oracle.sha256_hex(raw),
    }


# ---------------------------------------------------------------------------
# Fail-Closed Secondary Mathematical & Semantic Auditor (BOTH FR1 and FR0)
# Independently recomputes ALL Pillars 1-4 (never calls build_payload()).
# ---------------------------------------------------------------------------

def _audit_pillar1(p1: dict[str, Any]) -> None:
    _require_exact_dict(p1, frozenset({
        "square_omega_q", "dual_alpha_q", "irreducible_excess_above_2_q",
        "rectangular_1_1_t_curve", "s3_symmetry_triple_q", "s3_symmetry_omega_q",
        "s3_symmetry_omega_dec6", "s3_all_6_permutations_equal",
        "general_sub_harmonic_omega_q", "midpoint_convexity_checks",
        "strassen_2_280_lt_7_100_lt_2_281", "historical_benchmarks",
        "corollary12_finite_floors",
    }), "pillar1")
    sq = parse_canonical_rational_str(p1["square_omega_q"], "p1.sq")
    al = parse_canonical_rational_str(p1["dual_alpha_q"], "p1.alpha")
    ex = parse_canonical_rational_str(p1["irreducible_excess_above_2_q"], "p1.excess")
    oracle.require_ok(sq == Fraction(9, 4) and al == Fraction(1, 2) and ex == sq - 2, "P1_CORE", "core constants mismatch")

    curve = p1["rectangular_1_1_t_curve"]
    oracle.require_ok(type(curve) is list and len(curve) == 9, "P1_CURVE_LEN", "expected 9 curve points")
    prev_t: Fraction | None = None
    for idx, row in enumerate(curve):
        rr = _require_exact_dict(row, frozenset({
            "t_q", "omega_q", "omega_dec6", "penalty_above_2_q",
            "in_linear_o_n2_regime", "cor13_lower_bound_q", "strictly_exceeds_cor13",
        }), f"p1.curve[{idx}]")
        tv = parse_canonical_rational_str(rr["t_q"], "t")
        om = parse_canonical_rational_str(rr["omega_q"], "om")
        pen = parse_canonical_rational_str(rr["penalty_above_2_q"], "pen")
        c13 = parse_canonical_rational_str(rr["cor13_lower_bound_q"], "c13")
        in_lin = oracle.require_bool(rr["in_linear_o_n2_regime"], "in_lin")
        gt13 = oracle.require_bool(rr["strictly_exceeds_cor13"], "gt13")
        oracle.require_ok(Fraction(0) <= tv <= Fraction(1), "P1_T_RANGE", f"curve[{idx}] t range")
        if prev_t is not None:
            oracle.require_ok(tv > prev_t, "P1_T_ORDER", f"curve[{idx}] t must increase strictly")
        prev_t = tv
        exp_om = Fraction(2) if tv <= Fraction(1, 2) else Fraction(2) + (2 * tv - 1) * (2 * tv - 1) / (4 * tv)
        exp_c13 = max(Fraction(2), Fraction(3, 4) * (2 + tv))
        oracle.require_ok(om == exp_om and pen == om - 2 and c13 == exp_c13, "P1_CURVE_MATH", f"curve[{idx}] math")
        oracle.require_ok(in_lin is (om == 2) and gt13 is (om > c13), "P1_CURVE_FLAG", f"curve[{idx}] flags")
        oracle.require_ok(rr["omega_dec6"] == oracle.fmt_dec_q(om, 6), "P1_CURVE_DEC", f"curve[{idx}] dec")

    tri = p1["s3_symmetry_triple_q"]
    oracle.require_ok(type(tri) is list and len(tri) == 3, "P1_SYM_LEN", "3 weights")
    ws = [parse_canonical_rational_str(x, "tri") for x in tri]
    sym_om = parse_canonical_rational_str(p1["s3_symmetry_omega_q"], "sym_om")
    exp_sym = oracle.openai_rectangular_omega(ws[0], ws[1], ws[2])
    oracle.require_ok(sym_om == exp_sym and oracle.require_bool(p1["s3_all_6_permutations_equal"], "s3") is True, "P1_SYM_MATH", "sym mismatch")
    oracle.require_ok(p1["s3_symmetry_omega_dec6"] == oracle.fmt_dec_q(sym_om, 6), "P1_SYM_DEC", "sym dec")
    sub_h = parse_canonical_rational_str(p1["general_sub_harmonic_omega_q"], "sub_h")
    oracle.require_ok(sub_h == Fraction(7, 4), "P1_HARM", "harmonic mismatch")

    crows = p1["midpoint_convexity_checks"]
    oracle.require_ok(type(crows) is list and len(crows) == 3, "P1_CONV_LEN", "3 convexity checks")
    for idx, row in enumerate(crows):
        rr = _require_exact_dict(row, frozenset({"t1_q", "t2_q", "tmid_q", "jensen_gap_q", "jensen_gap_dec6"}), f"p1.cv[{idx}]")
        t1 = parse_canonical_rational_str(rr["t1_q"], "t1")
        t2 = parse_canonical_rational_str(rr["t2_q"], "t2")
        tm = parse_canonical_rational_str(rr["tmid_q"], "tm")
        gp = parse_canonical_rational_str(rr["jensen_gap_q"], "gp")
        oracle.require_ok(Fraction(1, 2) <= t1 < t2 <= Fraction(1) and tm == (t1 + t2) / 2, "P1_CONV_DOM", f"cv[{idx}]")
        exp_gp = (t2 - t1) * (t2 - t1) / (8 * t1 * t2 * (t1 + t2))
        oracle.require_ok(gp == exp_gp and rr["jensen_gap_dec6"] == oracle.fmt_dec_q(gp, 6), "P1_CONV_MATH", f"cv[{idx}]")

    oracle.require_ok(oracle.require_bool(p1["strassen_2_280_lt_7_100_lt_2_281"], "strassen") is True, "P1_STRASSEN", "Strassen flag")
    brows = p1["historical_benchmarks"]
    oracle.require_ok(type(brows) is list and len(brows) == 6, "P1_BENCH_LEN", "6 benchmarks")
    prev_e: Fraction | None = None
    for idx, row in enumerate(brows):
        rr = _require_exact_dict(row, frozenset({"name", "exponent_q", "gap_above_9_4_q", "gap_dec6"}), f"p1.b[{idx}]")
        _require_nonempty_str(rr["name"], "b.name")
        ev = parse_canonical_rational_str(rr["exponent_q"], "b.e")
        gv = parse_canonical_rational_str(rr["gap_above_9_4_q"], "b.g")
        oracle.require_ok(gv == ev - Fraction(9, 4) and gv >= 0 and rr["gap_dec6"] == oracle.fmt_dec_q(gv, 6), "P1_BENCH_MATH", f"b[{idx}]")
        if prev_e is not None:
            oracle.require_ok(ev < prev_e, "P1_BENCH_ORDER", f"benchmarks must decrease strictly at {idx}")
        prev_e = ev

    frows = p1["corollary12_finite_floors"]
    oracle.require_ok(type(frows) is list and len(frows) == 3, "P1_FLOOR_LEN", "3 finite floors")
    for idx, row in enumerate(frows):
        rr = _require_exact_dict(row, frozenset({
            "k", "side_n", "output_entries_n2", "border_rank_lb_n94",
            "nonscalar_gate_lb", "naive_cubic_n3", "rank_over_output_q",
        }), f"p1.f[{idx}]")
        k = oracle.require_exact_int(rr["k"], "k", lo=2, hi=64)
        n = oracle.require_exact_int(rr["side_n"], "n", lo=16)
        n2 = oracle.require_exact_int(rr["output_entries_n2"], "n2", lo=256)
        rlb = oracle.require_exact_int(rr["border_rank_lb_n94"], "rlb", lo=512)
        glb = oracle.require_exact_int(rr["nonscalar_gate_lb"], "glb", lo=256)
        n3 = oracle.require_exact_int(rr["naive_cubic_n3"], "n3", lo=4096)
        rat = parse_canonical_rational_str(rr["rank_over_output_q"], "rat")
        oracle.require_ok(n == k ** 4 and n2 == n * n and rlb == k ** 9 and glb == (rlb + 1) // 2 and n3 == n * n * n and rat == Fraction(rlb, n2), "P1_FLOOR_MATH", f"f[{idx}]")


def _audit_pillar2(p2: dict[str, Any]) -> None:
    _require_exact_dict(p2, frozenset({
        "openai_math_dual_model_verified", "openai_comparator_model",
        "openai_internal_rational_model", "openai_r10_proof_files_scanned",
        "openai_r10_proof_non_import_findings", "openai_r10_comparator_sorry_stubs",
        "openai_r10_lakefile_meta_hits", "pequalnp_r10_proof_files_scanned",
        "pequalnp_r10_proof_non_import_findings", "pequalnp_checker_controls",
        "trust_scorecard_matrix",
    }), "pillar2")
    oracle.require_ok(oracle.require_bool(p2["openai_math_dual_model_verified"], "p2.dual") is True, "P2_DUAL", "dual model flag")
    _require_nonempty_str(p2["openai_comparator_model"], "p2.cmp")
    _require_nonempty_str(p2["openai_internal_rational_model"], "p2.rat")
    oracle.require_exact_int(p2["openai_r10_proof_files_scanned"], "p2.oai_f", lo=13, hi=13)
    oracle.require_exact_int(p2["openai_r10_proof_non_import_findings"], "p2.oai_e", lo=0, hi=0)
    oracle.require_exact_int(p2["openai_r10_comparator_sorry_stubs"], "p2.oai_s", lo=3, hi=3)
    oracle.require_exact_int(p2["openai_r10_lakefile_meta_hits"], "p2.oai_l", lo=2, hi=2)
    oracle.require_exact_int(p2["pequalnp_r10_proof_files_scanned"], "p2.pnp_f", lo=15, hi=15)
    oracle.require_exact_int(p2["pequalnp_r10_proof_non_import_findings"], "p2.pnp_e", lo=0, hi=0)
    ctrls = p2["pequalnp_checker_controls"]
    oracle.require_ok(type(ctrls) is list and len(ctrls) == 5, "P2_CTRL_LEN", "5 checker controls")
    for idx, c in enumerate(ctrls):
        _require_nonempty_str(c, f"p2.ctrl[{idx}]")
    mat = p2["trust_scorecard_matrix"]
    oracle.require_ok(type(mat) is list and len(mat) == 4, "P2_MAT_LEN", "4 trust rows")
    for idx, row in enumerate(mat):
        rr = _require_exact_dict(row, frozenset({
            "program", "commit", "lean_toolchain", "uses_mathlib_classical",
            "audited_proof_files", "proof_files_non_import_escapes", "challenge_sorry_stubs",
            "t13_statement_isolation", "t14_dual_kernel_nanoda",
            "t15_paper_lean_parity_honest", "all_three_v23_gates_pass", "key_scope_note",
        }), f"p2.m[{idx}]")
        _require_nonempty_str(rr["program"], f"m[{idx}].prog")
        _require_nonempty_str(rr["commit"], f"m[{idx}].commit")
        _require_nonempty_str(rr["lean_toolchain"], f"m[{idx}].tc")
        oracle.require_bool(rr["uses_mathlib_classical"], f"m[{idx}].mc")
        _require_nonempty_str(rr["key_scope_note"], f"m[{idx}].note")
        oracle.require_exact_int(rr["audited_proof_files"], "af", lo=1)
        oracle.require_exact_int(rr["proof_files_non_import_escapes"], "ae", lo=0, hi=0)
        oracle.require_exact_int(rr["challenge_sorry_stubs"], "cs", lo=0)
        t13 = oracle.require_bool(rr["t13_statement_isolation"], "t13")
        t14 = oracle.require_bool(rr["t14_dual_kernel_nanoda"], "t14")
        t15 = oracle.require_bool(rr["t15_paper_lean_parity_honest"], "t15")
        all3 = oracle.require_bool(rr["all_three_v23_gates_pass"], "all3")
        oracle.require_ok(all3 is oracle.eval_trust_scorecard(t13, t14, t15), "P2_SCORECARD", f"m[{idx}] conjunction mismatch")


def _audit_pillar3(p3: dict[str, Any]) -> None:
    _require_exact_dict(p3, frozenset({
        "ambient_space_unified_cat0", "spectral_flat_law_imports_catzero",
        "euclidean_flat_charts", "planar_rectangle_3x4",
        "openai_cat0_tripod_witness", "vpvnp_rem_d3_witness",
        "law5_reconciliation_verdict",
    }), "pillar3")
    oracle.require_ok(
        oracle.require_bool(p3["ambient_space_unified_cat0"], "p3.cat0") is True
        and oracle.require_bool(p3["spectral_flat_law_imports_catzero"], "p3.imp") is True,
        "P3_FLAGS", "CAT(0) flags",
    )
    fcs = p3["euclidean_flat_charts"]
    oracle.require_ok(type(fcs) is list and len(fcs) == 3, "P3_FLAT_LEN", "3 flat charts")
    for idx, row in enumerate(fcs):
        rr = _require_exact_dict(row, frozenset({
            "label", "sides_q", "perimeter_q", "normalized_mean_width_q",
            "perimeter_over_mean_width_q", "gram_det_q", "strictly_below_9_4",
        }), f"p3.fc[{idx}]")
        _require_nonempty_str(rr["label"], f"fc[{idx}].label")
        sides = rr["sides_q"]
        oracle.require_ok(type(sides) is list and len(sides) == 3, "P3_SIDES", f"fc[{idx}] sides")
        a, b, c = (parse_canonical_rational_str(x, "side") for x in sides)
        per = parse_canonical_rational_str(rr["perimeter_q"], "per")
        mw = parse_canonical_rational_str(rr["normalized_mean_width_q"], "mw")
        rat = parse_canonical_rational_str(rr["perimeter_over_mean_width_q"], "rat")
        gd = parse_canonical_rational_str(rr["gram_det_q"], "gd")
        sq_d = [[Fraction(0), a * a, c * c], [a * a, Fraction(0), b * b], [c * c, b * b, Fraction(0)]]
        exp_gd = oracle.exact_det_q(oracle.gram_from_sq_dists(sq_d))
        oracle.require_ok(per == a + b + c and mw == per / 2 and rat == Fraction(2) and gd == exp_gd and gd > 0, "P3_FLAT_MATH", f"fc[{idx}]")
        oracle.require_ok(oracle.require_bool(rr["strictly_below_9_4"], "b94") is True, "P3_FLAT_B94", f"fc[{idx}]")

    rect = _require_exact_dict(p3["planar_rectangle_3x4"], frozenset({
        "perimeter_q", "normalized_mean_width_q", "interior_insertion_delta_q", "monotone_above_345_triangle",
    }), "p3.rect")
    rp = parse_canonical_rational_str(rect["perimeter_q"], "rp")
    rmw = parse_canonical_rational_str(rect["normalized_mean_width_q"], "rmw")
    rd = parse_canonical_rational_str(rect["interior_insertion_delta_q"], "rd")
    oracle.require_ok(rp == 14 and rmw == rp / 2 and rd == 0 and oracle.require_bool(rect["monotone_above_345_triangle"], "rmono") is True, "P3_RECT", "rect mismatch")

    tw = _require_exact_dict(p3["openai_cat0_tripod_witness"], frozenset({
        "arm_length_q", "tip_distance_q", "triangle_perimeter_q", "shared_label_rate_q",
        "curvature_defect_below_flat_q", "ratio_perimeter_over_rate_q",
        "gram_matrix_q", "gram_det_q", "neg_quad_witness_vec", "neg_quad_form_q",
        "bruhat_tits_cn_slack_q", "isometric_euclidean_chart_blocked",
    }), "p3.tripod")
    arm = parse_canonical_rational_str(tw["arm_length_q"], "arm")
    tip = parse_canonical_rational_str(tw["tip_distance_q"], "tip")
    tp = parse_canonical_rational_str(tw["triangle_perimeter_q"], "tp")
    rate = parse_canonical_rational_str(tw["shared_label_rate_q"], "rate")
    defect = parse_canonical_rational_str(tw["curvature_defect_below_flat_q"], "defect")
    tratio = parse_canonical_rational_str(tw["ratio_perimeter_over_rate_q"], "tratio")
    tdet = parse_canonical_rational_str(tw["gram_det_q"], "tdet")
    tqf = parse_canonical_rational_str(tw["neg_quad_form_q"], "tqf")
    tcn = parse_canonical_rational_str(tw["bruhat_tits_cn_slack_q"], "tcn")
    gm = tw["gram_matrix_q"]
    oracle.require_ok(type(gm) is list and len(gm) == 3 and all(type(r) is list and len(r) == 3 for r in gm), "P3_TGM", "3x3 Gram")
    g_mat = [[parse_canonical_rational_str(x, "tg") for x in row] for row in gm]
    exp_tg = oracle.gram_from_sq_dists([
        [Fraction(0), Fraction(1), Fraction(1), Fraction(1)],
        [Fraction(1), Fraction(0), Fraction(4), Fraction(4)],
        [Fraction(1), Fraction(4), Fraction(0), Fraction(4)],
        [Fraction(1), Fraction(4), Fraction(4), Fraction(0)],
    ])
    tvec = tw["neg_quad_witness_vec"]
    oracle.require_ok(type(tvec) is list and len(tvec) == 3, "P3_TVEC", "3-vec")
    tv_q = [Fraction(oracle.require_exact_int(x, "tv")) for x in tvec]
    oracle.require_ok(
        arm == 1 and tip == 2 * arm and tp == 3 * tip and rate == Fraction(8, 3) * arm
        and defect == tp / 2 - rate and tratio == tp / rate
        and g_mat == exp_tg and tdet == oracle.exact_det_q(g_mat)
        and tqf == oracle.exact_quad_form_q(g_mat, tv_q) and tqf < 0
        and tcn == Fraction(2) and oracle.require_bool(tw["isometric_euclidean_chart_blocked"], "tblk") is True,
        "P3_TRIPOD_MATH", "tripod verification failed",
    )

    vw = _require_exact_dict(p3["vpvnp_rem_d3_witness"], frozenset({
        "points", "gram_matrix_q", "gram_det_q", "neg_quad_witness_vec",
        "neg_quad_form_q", "two_g_quad_form", "isometric_euclidean_chart_blocked",
    }), "p3.vpvnp")
    pts = vw["points"]
    oracle.require_ok(type(pts) is list and len(pts) == 5, "P3_VPTS", "5 Rem D.3 points")
    for idx, pt in enumerate(pts):
        _require_nonempty_str(pt, f"p3.pt[{idx}]")
    vgm = vw["gram_matrix_q"]
    oracle.require_ok(type(vgm) is list and len(vgm) == 4 and all(type(r) is list and len(r) == 4 for r in vgm), "P3_VGM", "4x4 Gram")
    vg_mat = [[parse_canonical_rational_str(x, "vg") for x in row] for row in vgm]
    exp_vg = oracle.gram_from_sq_dists([
        [Fraction(0), Fraction(1), Fraction(1), Fraction(1), Fraction(2)],
        [Fraction(1), Fraction(0), Fraction(1), Fraction(2), Fraction(1)],
        [Fraction(1), Fraction(1), Fraction(0), Fraction(1), Fraction(2)],
        [Fraction(1), Fraction(2), Fraction(1), Fraction(0), Fraction(1)],
        [Fraction(2), Fraction(1), Fraction(2), Fraction(1), Fraction(0)],
    ])
    vvec = vw["neg_quad_witness_vec"]
    oracle.require_ok(type(vvec) is list and len(vvec) == 4, "P3_VVEC", "4-vec")
    vv_q = [Fraction(oracle.require_exact_int(x, "vv")) for x in vvec]
    vdet = parse_canonical_rational_str(vw["gram_det_q"], "vdet")
    vqf = parse_canonical_rational_str(vw["neg_quad_form_q"], "vqf")
    v2qf = oracle.require_exact_int(vw["two_g_quad_form"], "v2qf")
    oracle.require_ok(
        vg_mat == exp_vg and vdet == oracle.exact_det_q(vg_mat)
        and vqf == oracle.exact_quad_form_q(vg_mat, vv_q) and vqf == -1 and Fraction(v2qf) == 2 * vqf
        and oracle.require_bool(vw["isometric_euclidean_chart_blocked"], "vblk") is True,
        "P3_VPVNP_MATH", "Rem D.3 verification failed",
    )

    verd = _require_exact_dict(p3["law5_reconciliation_verdict"], frozenset({
        "naive_contradiction", "domain_boundary", "thm_d2_interaction",
    }), "p3.verd")
    oracle.require_ok(oracle.require_bool(verd["naive_contradiction"], "nc") is False, "P3_VERD", "no naive contradiction")
    _require_nonempty_str(verd["domain_boundary"], "p3.db")
    _require_nonempty_str(verd["thm_d2_interaction"], "p3.td2")


def _audit_pillar4(p4: dict[str, Any]) -> None:
    _require_exact_dict(p4, frozenset({
        "note1_statement_count", "note1_statements", "circuit_helpers",
        "path_exact_sizes", "cycle_exact_sizes", "c4_biclique_obstruction",
        "lindsey_n3_witness", "parity_smol_central_sq_checks",
        "sat_five_4bit_block_checks", "barrier_crosswalk_s41_s44_s75_s93",
    }), "pillar4")
    nc = oracle.require_exact_int(p4["note1_statement_count"], "p4.nc", lo=10, hi=10)
    stmts = p4["note1_statements"]
    oracle.require_ok(type(stmts) is list and len(stmts) == nc, "P4_STMT_LEN", "10 note-1 statements")
    for idx, row in enumerate(stmts):
        rr = _require_exact_dict(row, frozenset({"id", "file", "run", "sha256", "summary"}), f"p4.st[{idx}]")
        _require_nonempty_str(rr["id"], f"st[{idx}].id")
        _require_nonempty_str(rr["file"], f"st[{idx}].file")
        _require_nonempty_str(rr["run"], f"st[{idx}].run")
        oracle.require_hex64(rr["sha256"], f"st[{idx}].sha")
        _require_nonempty_str(rr["summary"], f"st[{idx}].sum")
    oracle.require_ok(
        [(r["id"], r["file"], r["sha256"]) for r in stmts] == [(r["id"], r["file"], r["sha256"]) for r in oracle.PEQUALNP_NOTE1_ROWS],
        "P4_STMT_PIN", "note-1 pinned SHAs mismatch",
    )

    helpers = p4["circuit_helpers"]
    oracle.require_ok(type(helpers) is list and len(helpers) == 5, "P4_HELP_LEN", "5 helpers")
    for idx, row in enumerate(helpers):
        rr = _require_exact_dict(row, frozenset({"name", "sha256", "barrier_class"}), f"p4.h[{idx}]")
        _require_nonempty_str(rr["name"], f"h[{idx}].name")
        oracle.require_hex64(rr["sha256"], f"h[{idx}].sha")
        _require_nonempty_str(rr["barrier_class"], f"h[{idx}].bc")
    oracle.require_ok(
        [(r["name"], r["sha256"]) for r in helpers] == [(r["name"], r["sha256"]) for r in oracle.PEQUALNP_CIRCUIT_HELPERS],
        "P4_HELP_PIN", "helper pinned SHAs mismatch",
    )

    paths = p4["path_exact_sizes"]
    oracle.require_ok(type(paths) is list and len(paths) == 7, "P4_PATH_LEN", "7 paths")
    for idx, row in enumerate(paths):
        rr = _require_exact_dict(row, frozenset({"n", "edges", "tau", "exact_circuit_size"}), f"p4.p[{idx}]")
        n = oracle.require_exact_int(rr["n"], "n", lo=2)
        e = oracle.require_exact_int(rr["edges"], "e", lo=1)
        t = oracle.require_exact_int(rr["tau"], "t", lo=1)
        s = oracle.require_exact_int(rr["exact_circuit_size"], "s", lo=1)
        oracle.require_ok(e == n - 1 and t == n // 2 and s == e + t - 1, "P4_PATH_MATH", f"p[{idx}]")
    oracle.require_ok([r["n"] for r in paths] == [2, 3, 4, 5, 6, 7, 8], "P4_PATH_DOM", "paths domain 2..8")

    cycles = p4["cycle_exact_sizes"]
    oracle.require_ok(type(cycles) is list and len(cycles) == 6, "P4_CYC_LEN", "6 cycles")
    for idx, row in enumerate(cycles):
        rr = _require_exact_dict(row, frozenset({"n", "edges", "tau", "exact_circuit_size"}), f"p4.c[{idx}]")
        n = oracle.require_exact_int(rr["n"], "n", lo=5)
        e = oracle.require_exact_int(rr["edges"], "e", lo=5)
        t = oracle.require_exact_int(rr["tau"], "t", lo=3)
        s = oracle.require_exact_int(rr["exact_circuit_size"], "s", lo=7)
        oracle.require_ok(e == n and t == (n + 1) // 2 and s == e + t - 1, "P4_CYC_MATH", f"c[{idx}]")
    oracle.require_ok([r["n"] for r in cycles] == [5, 6, 7, 8, 9, 10], "P4_CYC_DOM", "cycles domain 5..10")

    c4 = _require_exact_dict(p4["c4_biclique_obstruction"], frozenset({
        "formula_prediction", "exact_circuit_size", "biclique_gate_deficit",
        "truth_table_matches_16", "pair_funnel_three_of_four_coincide",
    }), "p4.c4")
    fp = oracle.require_exact_int(c4["formula_prediction"], "fp", lo=5, hi=5)
    es = oracle.require_exact_int(c4["exact_circuit_size"], "es", lo=3, hi=3)
    df = oracle.require_exact_int(c4["biclique_gate_deficit"], "df")
    oracle.require_exact_int(c4["truth_table_matches_16"], "tt", lo=16, hi=16)
    oracle.require_ok(df == fp - es, "P4_C4_MATH", "C4 math")
    oracle.require_ok(oracle.require_bool(c4["pair_funnel_three_of_four_coincide"], "pf") is True, "P4_C4_PF", "C4 funnel")

    lw = _require_exact_dict(p4["lindsey_n3_witness"], frozenset({
        "orthogonality_checks_64", "rect_a_size", "rect_b_size",
        "discrepancy_sum", "lindsey_lhs_sq", "lindsey_rhs_2n_ab",
    }), "p4.lw")
    oracle.require_exact_int(lw["orthogonality_checks_64"], "orth", lo=64, hi=64)
    ra = oracle.require_exact_int(lw["rect_a_size"], "ra", lo=1, hi=8)
    rb = oracle.require_exact_int(lw["rect_b_size"], "rb", lo=1, hi=8)
    ds = oracle.require_exact_int(lw["discrepancy_sum"], "ds")
    ll = oracle.require_exact_int(lw["lindsey_lhs_sq"], "ll", lo=0)
    lr = oracle.require_exact_int(lw["lindsey_rhs_2n_ab"], "lr", lo=1)
    oracle.require_ok(ll == ds * ds and lr == 8 * ra * rb and ll <= lr, "P4_LINDSEY_MATH", "Lindsey math")

    smols = p4["parity_smol_central_sq_checks"]
    oracle.require_ok(type(smols) is list and len(smols) == 9, "P4_SMOL_LEN", "9 Smolensky checks")
    for idx, row in enumerate(smols):
        rr = _require_exact_dict(row, frozenset({"k", "central_binom", "lhs", "rhs_16k"}), f"p4.sm[{idx}]")
        k = oracle.require_exact_int(rr["k"], "k", lo=0, hi=12)
        cb = oracle.require_exact_int(rr["central_binom"], "cb", lo=1)
        lhs = oracle.require_exact_int(rr["lhs"], "lhs", lo=1)
        rhs = oracle.require_exact_int(rr["rhs_16k"], "rhs", lo=1)
        oracle.require_ok(cb == math.comb(2 * k, k) and lhs == cb * cb * (2 * k + 1) and rhs == 16 ** k, "P4_SMOL_MATH", f"sm[{idx}]")
    oracle.require_ok([r["k"] for r in smols] == list(range(9)), "P4_SMOL_DOM", "smol domain 0..8")

    s5s = p4["sat_five_4bit_block_checks"]
    oracle.require_ok(type(s5s) is list and len(s5s) == 4, "P4_SAT5_LEN", "4 SatFive checks")
    for idx, row in enumerate(s5s):
        rr = _require_exact_dict(row, frozenset({"n_bits", "encoded_len"}), f"p4.s5[{idx}]")
        nb = oracle.require_exact_int(rr["n_bits"], "nb", lo=0)
        el = oracle.require_exact_int(rr["encoded_len"], "el", lo=0)
        oracle.require_ok(el == 4 * nb, "P4_SAT5_MATH", f"s5[{idx}]")
    oracle.require_ok([r["n_bits"] for r in s5s] == [0, 1, 3, 5], "P4_SAT5_DOM", "sat5 domain")

    cw = p4["barrier_crosswalk_s41_s44_s75_s93"]
    oracle.require_ok(type(cw) is list and len(cw) == 5, "P4_CW_LEN", "5 crosswalk rows")
    for idx, row in enumerate(cw):
        rr = _require_exact_dict(row, frozenset({"track", "model", "evades_natural_proofs", "status"}), f"p4.cw[{idx}]")
        _require_nonempty_str(rr["track"], f"cw[{idx}].tr")
        _require_nonempty_str(rr["model"], f"cw[{idx}].mo")
        oracle.require_bool(rr["evades_natural_proofs"], "enp")
        _require_nonempty_str(rr["status"], f"cw[{idx}].st")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed semantic + algebraic auditor enforced under BOTH FR1 and FR0."""
    oracle.require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")
    oracle.validate_strict_json_tree(payload, "payload")
    _require_exact_dict(payload, _PAYLOAD_KEYS, "payload")
    oracle.require_ok(payload["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema_version")
    oracle.require_ok(payload["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "track_id")
    oracle.require_ok(payload["oracle_class"] == "exact", "SCHEMA_MISMATCH", "oracle_class")
    oracle.require_ok(payload["novelty_classification"] == "N1", "SCHEMA_MISMATCH", "novelty")

    prov = _require_exact_dict(payload["wave6_provenance"], _PROV_KEYS, "wave6_provenance")
    oracle.require_ok(prov["openai_math_repo"] == oracle.OPENAI_MATH_REPO, "PROV_OAI_REPO", "openai repo")
    oracle.require_ok(prov["openai_math_commit"] == oracle.OPENAI_MATH_COMMIT, "PROV_OAI_COMMIT", "openai commit")
    oracle.require_ok(prov["openai_math_toolchain"] == oracle.OPENAI_MATH_TOOLCHAIN, "PROV_OAI_TC", "openai toolchain")
    oracle.require_ok(prov["pequalnp_repo"] == oracle.PEQUALNP_REPO, "PROV_PNP_REPO", "pequalnp repo")
    oracle.require_ok(prov["pequalnp_commit"] == oracle.PEQUALNP_COMMIT, "PROV_PNP_COMMIT", "pequalnp commit")
    oracle.require_ok(prov["pequalnp_toolchain"] == oracle.PEQUALNP_TOOLCHAIN, "PROV_PNP_TC", "pequalnp toolchain")
    n_src = oracle.require_exact_int(prov["pinned_sources_count"], "n_src", lo=12, hi=12)
    srcs = prov["pinned_sources"]
    oracle.require_ok(type(srcs) is list and len(srcs) == n_src, "PROV_SRCS_LEN", "12 pinned sources")
    for idx, src in enumerate(srcs):
        rr = _require_exact_dict(src, _SRC_KEYS, f"src[{idx}]")
        _require_nonempty_str(rr["id"], f"src[{idx}].id")
        _require_nonempty_str(rr["repo"], f"src[{idx}].repo")
        _require_nonempty_str(rr["relpath"], f"src[{idx}].rel")
        oracle.require_hex64(rr["sha256"], f"src[{idx}].sha256")
        oracle.require_exact_int(rr["bytes"], f"src[{idx}].bytes", lo=1)
        _require_nonempty_str(rr["role"], f"src[{idx}].role")
    oracle.require_ok(
        [(r["id"], r["bytes"], r["sha256"]) for r in srcs] == [(r["id"], r["bytes"], r["sha256"]) for r in oracle.PINNED_WAVE6_SOURCES],
        "PROV_SRCS_PIN", "wave6 source pins mismatch",
    )

    ups = payload["upstream_expedition_bridges"]
    oracle.require_ok(type(ups) is list and len(ups) == 4, "UP_LEN", "4 upstream certs")
    for idx, ub in enumerate(ups):
        rr = _require_exact_dict(ub, _UP_KEYS, f"up[{idx}]")
        _require_nonempty_str(rr["track"], f"up[{idx}].tr")
        _require_nonempty_str(rr["cert_file"], f"up[{idx}].cf")
        oracle.require_hex64(rr["cert_sha256"], f"up[{idx}].sha256")
        _require_nonempty_str(rr["bridge"], f"up[{idx}].br")
    oracle.require_ok(
        [(r["track"], r["cert_file"], r["cert_sha256"]) for r in ups] == [(r["track"], r["cert_file"], r["cert_sha256"]) for r in oracle.UPSTREAM_EXPEDITION_CERTS],
        "UP_PIN", "upstream cert pins mismatch",
    )

    pa = _require_exact_dict(payload["pinned_artifacts"], _PINNED_KEYS, "pinned_artifacts")
    oracle.require_ok(pa["lean_source"] == "OmegaNineFourthsAndSpectrum.lean", "SCHEMA_MISMATCH", "lean_source")
    oracle.require_hex64(pa["lean_source_sha256"], "lean_source_sha256")
    oracle.require_ok(pa["lean_toolchain"] == oracle.EXPECTED_LEAN_TOOLCHAIN, "SCHEMA_MISMATCH", "lean_toolchain")
    oracle.require_hex64(pa["lean_toolchain_sha256"], "lean_toolchain_sha256")
    oracle.require_hex64(pa["lakefile_sha256"], "lakefile_sha256")
    oracle.require_ok(
        (pa["lean_source_sha256"], pa["lean_toolchain_sha256"], pa["lakefile_sha256"])
        == (oracle.PINNED_LEAN_SOURCE_SHA256, oracle.PINNED_LEAN_TOOLCHAIN_SHA256, oracle.PINNED_LAKEFILE_SHA256),
        "PINNED_SHA_MISMATCH", "pinned artifact SHA mismatch",
    )
    thm_n = oracle.require_exact_int(
        pa["lean_theorem_count"], "lean_theorem_count", lo=len(oracle.LEAN_THEOREM_NAMES), hi=len(oracle.LEAN_THEOREM_NAMES)
    )
    thms = pa["lean_theorem_names"]
    oracle.require_ok(type(thms) is list and tuple(thms) == oracle.LEAN_THEOREM_NAMES, "THEOREM_LIST_MISMATCH", "lean_theorem_names")

    _audit_pillar1(payload["pillar1_openai_omega94"])
    _audit_pillar2(payload["pillar2_forensic_trust_audit"])
    _audit_pillar3(payload["pillar3_law5_reconciliation"])
    _audit_pillar4(payload["pillar4_pequalnp_barriers"])
    oracle.require_ok(
        oracle.canonical_json_bytes(payload) == oracle.canonical_json_bytes(oracle.build_payload()),
        "PAYLOAD_CANONICAL_PIN_MISMATCH",
        "payload diverges from canonical deterministic Track S93 audit payload",
    )

    return {
        "secondary_audit_passed": True,
        "wave6_sources_pinned": n_src,
        "upstream_bridges_pinned": len(ups),
        "lean_theorem_count": thm_n,
    }


def _load_track_artifacts(track_dir: Path) -> tuple[str, str, str, dict[str, Any]]:
    lean_p = track_dir / "OmegaNineFourthsAndSpectrum.lean"
    tc_p = track_dir / "lean-toolchain"
    lk_p = track_dir / "lakefile.toml"
    tc_raw = read_regular_bytes_capped(tc_p, "lean-toolchain", max_bytes=4096)
    lk_raw = read_regular_bytes_capped(lk_p, "lakefile.toml", max_bytes=65536)
    try:
        tc_text = tc_raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise oracle.S93Error("INVALID_UTF8", "lean-toolchain not UTF-8") from exc
    oracle.require_ok(tc_text == oracle.EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", f"got {tc_text!r}")
    lean_res = verify_lean4_file_live(lean_p)
    return (
        lean_res["lean_source_sha256"],
        oracle.sha256_hex(tc_raw),
        oracle.sha256_hex(lk_raw),
        lean_res,
    )


def verify_certificate_dict(
    cert: Any,
    *,
    full_replay: bool = True,
    track_dir: Path | None = None,
) -> dict[str, Any]:
    oracle.require_bool(full_replay, "full_replay")
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    oracle.validate_strict_json_tree(cert, "certificate")
    _require_exact_dict(cert, _ENVELOPE_KEYS, "certificate")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "envelope schema_version")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "envelope track_id")

    payload = cert["payload"]
    sec = secondary_audit_payload(payload)

    expected_payload_sha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    oracle.require_ok(cert["payload_sha256"] == expected_payload_sha, "PAYLOAD_SHA_MISMATCH", "payload digest mismatch")
    envelope_core = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": cert["payload_sha256"],
        "payload": payload,
    }
    expected_cert_sha = oracle.sha256_hex(oracle.canonical_json_bytes(envelope_core))
    oracle.require_ok(cert["certificate_sha256"] == expected_cert_sha, "CERT_SHA_MISMATCH", "certificate digest mismatch")

    receipt: dict[str, Any] = {
        "valid": True,
        "track_id": oracle.TRACK_ID,
        "full_replay": full_replay,
        "payload_sha256": expected_payload_sha,
        "certificate_sha256": expected_cert_sha,
        "secondary_audit": sec,
    }
    if full_replay:
        replayed = oracle.build_certificate()
        oracle.require_ok(
            oracle.canonical_json_bytes(replayed) == oracle.canonical_json_bytes(cert),
            "REPLAY_MISMATCH",
            "certificate differs from deterministic oracle replay",
        )
        tdir = Path(_THIS_DIR) if track_dir is None else _check_no_symlink_components(_check_path_str(track_dir, "track_dir"), "track_dir")
        l_sha, tc_sha, lk_sha, lean_live = _load_track_artifacts(tdir)
        pa = payload["pinned_artifacts"]
        oracle.require_ok(pa["lean_source_sha256"] == l_sha, "LEAN_SHA_MISMATCH", "lean source sha mismatch")
        oracle.require_ok(pa["lean_toolchain_sha256"] == tc_sha, "TOOLCHAIN_SHA_MISMATCH", "toolchain sha mismatch")
        oracle.require_ok(pa["lakefile_sha256"] == lk_sha, "LAKEFILE_SHA_MISMATCH", "lakefile sha mismatch")
        receipt["lean_live"] = lean_live
    return receipt


# ---------------------------------------------------------------------------
# Strict Manual CLI Parser & Entry Point
# ---------------------------------------------------------------------------

def _parse_cli_args(argv: Sequence[str]) -> dict[str, Any]:
    oracle.require_ok(isinstance(argv, (list, tuple)), "INVALID_ARGV", "argv must be list/tuple")
    mode: str | None = None
    path_arg: str | None = None
    json_out = False
    i = 0
    n = len(argv)
    while i < n:
        tok = oracle.require_exact_str(argv[i], f"argv[{i}]")
        oracle.require_ok("\x00" not in tok, "NUL_BYTE_FORBIDDEN", "NUL byte in arg")
        if tok == "--json":
            oracle.require_ok(not json_out, "DUPLICATE_FLAG", "--json repeated")
            json_out = True
            i += 1
        elif tok == "--standalone":
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "multiple modes specified")
            mode = "standalone"
            i += 1
        elif tok in ("--check", "--write"):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "multiple modes specified")
            oracle.require_ok(i + 1 < n, "MISSING_PATH_ARG", f"{tok} requires path")
            val = oracle.require_exact_str(argv[i + 1], f"{tok}.path")
            oracle.require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", "NUL byte in arg")
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"bad path for {tok}")
            mode = tok[2:]
            path_arg = val
            i += 2
        elif tok.startswith("--check=") or tok.startswith("--write="):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "multiple modes specified")
            flag, val = tok.split("=", 1)
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"bad path for {flag}")
            mode = flag[2:]
            path_arg = val
            i += 1
        else:
            raise oracle.S93Error("UNKNOWN_FLAG", f"unrecognized argument: {tok[:32]}")
    return {"mode": mode or "default", "path": path_arg, "json": json_out}


def main(argv: Sequence[str] | None = None) -> int:
    args_in = list(sys.argv[1:]) if argv is None else argv
    try:
        _check_safe_cwd()
        cfg = _parse_cli_args(args_in)
        mode = cfg["mode"]
        if mode == "standalone":
            sys.stdout.write(oracle.canonical_json_bytes(oracle.build_certificate()).decode("ascii"))
            return 0
        if mode == "write":
            cert = oracle.build_certificate()
            raw = oracle.canonical_json_bytes(cert)
            out_p = write_regular_bytes_atomic_0600(cfg["path"], raw, "write_cert")
            receipt = verify_certificate_dict(cert, full_replay=True)
            out_obj = {"written": True, "path": out_p.name, "bytes": len(raw), "receipt": receipt}
            if cfg["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(out_obj).decode("ascii"))
            else:
                sys.stdout.write(f"WROTE {out_p.name} ({len(raw)} bytes) cert_sha256={cert['certificate_sha256'][:16]}\n")
            return 0
        target = Path(_THIS_DIR) / "s93_omega94_vpvnp_certificate.json" if mode == "default" else cfg["path"]
        raw_in = read_regular_bytes_capped(target, "certificate_file")
        cert_in = parse_strict_json_bytes(raw_in, "certificate_file", require_canonical=True)
        receipt = verify_certificate_dict(cert_in, full_replay=True)
        if cfg["json"]:
            sys.stdout.write(oracle.canonical_json_bytes(receipt).decode("ascii"))
        else:
            sys.stdout.write(f"OK {oracle.TRACK_ID} cert_sha256={receipt['certificate_sha256'][:16]}\n")
        return 0
    except oracle.S93Error as exc:
        err_obj = {"error": True, "code": exc.code, "detail": exc.detail}
        sys.stderr.write(oracle.canonical_json_bytes(err_obj).decode("ascii"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
