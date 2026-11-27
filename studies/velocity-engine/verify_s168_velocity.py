"""
`verify_s168_velocity.py`: Track S168 (EXP-Q56a) Independent Zero-Shared-Code Verifier.

Independently verifies (with ZERO imports from `trust_core`, `preflight`, `fast_mutate`, or
`s168_velocity_bench`):
  1. Pure-Z/Q exact pipeline acceleration theorems (two-stage kill-gate with per-branch
     `threshold_q = (Tmono - T1) / T2`, lossless Pass-2 dedup, exhaustive 255-case `--failfast`
     kill equivalence + step bound + strict early-fail savings, dynamic break-even N-track
     amortization with measured `trust_core.py` LOC, and shift-left preflight savings),
  2. Pure-Init Lean 4.36.0 bundle (`VelocityBounds.lean`, 14/14 theorems, 0 sorry/axiom/
     Classical.choice) via a genuinely distinct typed-token Lean 4 static auditor + strict
     declarative `lakefile.toml` schema validation + optional isolated `--live-lean` native ELF
     kernel replay with strict offline vs live separation (S166 Delta-6 PASS pattern),
  3. Live multi-trial empirical A/B benchmark provenance (`s168_ab_results.json` strictly
     post-dating bench + all 3 core engines, embedded bench & engine SHA-256 verification,
     strict `type(x) is int` checks, mixed killed/survived non-redundant Pass-2 parity, and
     exact rational median speedup recomputation for `w1 vs w1`, `w8 vs w8`, and `base w1 vs fast w8`),
  4. Full Zone-B hardened OS-descriptor I/O (`O_NOFOLLOW`, `st_nlink == 1`, atomic `O_EXCL`
     + `os.replace`), exact-type JSON equality (keys and values), and fail-closed JSON CLI.

Stdlib-only, zero bare asserts, zero floats on trust paths, 3x -I bit-identical.
"""
from __future__ import annotations

import argparse
import errno
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import pwd
import random
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Callable, Sequence

__all__ = [
    "EXPECTED_THEOREMS",
    "EXPECTED_ZERO_AXIOM_THEOREMS",
    "EXPECTED_PROPEXT_ONLY_THEOREMS",
    "EXPECTED_TOOLCHAIN",
    "SOURCE_FILES_TO_PIN",
    "VerifierError",
    "need",
    "exact_json_equal",
    "read_nofollow_bytes",
    "parse_exact_json",
    "atomic_write_nofollow",
    "tokenize_lean4",
    "strip_lean_comments",
    "audit_lean_static",
    "verify_lean_bundle",
    "verify_pillar1_math",
    "verify_empirical_ab_results",
    "build_certificate",
    "verify_certificate_file",
    "main",
]

MAX_BYTES = 16 * 1024 * 1024
MAX_DEPTH = 64
MAX_INT_DIGITS = 1024
EXPECTED_TOOLCHAIN = "leanprover/lean4:v4.36.0"
EXPECTED_LEAN_VERSION_TOKEN = "version 4.36.0,"

EXPECTED_THEOREMS: tuple[str, ...] = (
    "VelocityBounds.two_stage_expected_time_strict_accel_iff",
    "VelocityBounds.two_stage_general_T2_le_Tmono_accel",
    "VelocityBounds.two_stage_expected_savings_exact",
    "VelocityBounds.two_stage_monotone_in_survival_prob",
    "VelocityBounds.two_stage_no_gain_at_unit_survival",
    "VelocityBounds.pass2_dedup_bool_union_exact",
    "VelocityBounds.pass2_dedup_list_mem_exact",
    "VelocityBounds.pass2_dedup_eval_count_exact",
    "VelocityBounds.pass2_dedup_zero_evals_when_subset",
    "VelocityBounds.failfast_kill_equivalence_and_bound",
    "VelocityBounds.trust_core_amortized_savings_iff",
    "VelocityBounds.trust_core_monotone_in_tracks",
    "VelocityBounds.preflight_audit_round_savings_iff",
    "VelocityBounds.velocity_engine_concrete_witnesses",
)
EXPECTED_ZERO_AXIOM_THEOREMS: frozenset[str] = frozenset({
    "VelocityBounds.pass2_dedup_bool_union_exact",
    "VelocityBounds.velocity_engine_concrete_witnesses",
})
EXPECTED_PROPEXT_ONLY_THEOREMS: frozenset[str] = frozenset({
    "VelocityBounds.pass2_dedup_zero_evals_when_subset",
})
ALLOWED_AXIOMS: frozenset[str] = frozenset({"propext", "Quot.sound"})
SOURCE_FILES_TO_PIN: tuple[str, ...] = (
    "trust_core.py",
    "preflight.py",
    "fast_mutate.py",
    "s168_velocity_bench.py",
    "verify_s168_velocity.py",
    "test_s168_velocity_r5.py",
)
ENGINE_SOURCE_FILES: tuple[str, ...] = ("trust_core.py", "preflight.py", "fast_mutate.py")
EXPECTED_AB_TARGET_TRACK = "track-s166-aletheia-cs27-cs29-hardening"
EXPECTED_AB_TARGET_SCRIPT = "aletheia/portfolio_dag.py"
EXPECTED_AB_TARGET_SHA256 = "f34cbea939a372c9b214e4bd49eac4641b9ce733471650b636d64e729724b288"
_AB_ARM_NAMES: frozenset[str] = frozenset({"baseline_w1", "fast_w1", "baseline_w8", "fast_w8"})
_AB_ARM_BASE_ORDER: tuple[str, ...] = ("baseline_w1", "fast_w1", "baseline_w8", "fast_w8")
EXPECTED_AB_RNG_SEED = 168
EXPECTED_AB_PASS2_GUARD = "_require"
EXPECTED_AB_TEST_CMD = "python3 -m unittest tests/test_cs27_cs29_hardening_r5.py"
_SHA64_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_LEAN_TC_WITNESS_RE = re.compile(
    r"\(\s*(\d+)\s*\*\s*420\s*≤\s*(\d+)\s*\+\s*(\d+)\s*\*\s*20\s*\)\s*∧\s*"
    r"\(\s*(\d+)\s*\+\s*(\d+)\s*\*\s*20\s*<\s*(\d+)\s*\*\s*420\s*\)\s*∧\s*"
    r"\(\s*6\s*\*\s*420\s*-\s*\(\s*(\d+)\s*\+\s*6\s*\*\s*20\s*\)\s*=\s*(\d+)\s*\)"
)

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_INIT_RESERVED_INTERP_BANGS = frozenset({"s!", "f!", "println!"})
_AMBIG_INTERP_PLAINS = frozenset({"dbg_trace", "throwError", "logInfo", "logError", "logWarning"})
_ALLOWLIST_INTERP_ARG_MACROS: dict[str, tuple[int, bool]] = {
    "Macro.trace": (1, True),
    "trace_goal": (1, True),
    "trace": (1, True),
    "throwNamedErrorAt": (2, False),
    "logNamedErrorAt": (2, False),
    "logNamedWarningAt": (2, False),
    "throwErrorAt": (1, False),
    "logInfoAt": (1, False),
    "logWarningAt": (1, False),
    "logErrorAt": (1, False),
    "logAt": (1, False),
    "throwNamedError": (1, False),
    "logNamedError": (1, False),
    "logNamedWarning": (1, False),
}

_FORBIDDEN_KW_TOKENS = frozenset({
    "sorry", "admit", "axiom", "unsafe", "opaque", "instance",
    "native_decide", "bv_decide", "bv_check",
    "run_cmd", "run_meta", "run_tac", "run_elab", "by_elab", "initialize", "builtin_initialize",
    "syntax", "macro", "macro_rules", "elab", "elab_rules", "declare_syntax_cat",
    "notation", "infix", "infixl", "infixr", "prefix", "postfix",
    "import",
})
_FORBIDDEN_IDENT_TOKENS = frozenset({
    "sorryAx", "mkSorry", "ofReduceBool", "ofReduceNat", "trustCompiler",
})
_FORBIDDEN_DEBUG_SUFFIXES = frozenset({
    "skipKernelTC", "byAsSorry", "proofAsSorry", "terminalTacticsAsSorry",
})
_FORBIDDEN_DOTTED_DEBUG = frozenset(f"debug.{s}" for s in _FORBIDDEN_DEBUG_SUFFIXES)
_FORBIDDEN_DOTTED_META = frozenset({"Lean.Elab", "Lean.Meta"})
_FORBIDDEN_HASH_CMDS = frozenset({
    "eval", "eval!", "reduce", "exit", "guard_msgs", "check_failure",
})
_FORBIDDEN_ATTR_TOKENS = frozenset({
    "extern", "implemented_by", "export", "init", "builtin_init", "macro", "elab", "tactic", "default_instance",
})
_PARTIAL_TARGETS = frozenset({"def", "instance", "abbrev", "theorem", "lemma", "opaque"})
_TOP_DECL_WORDS = frozenset({
    "theorem", "lemma", "def", "abbrev", "opaque", "axiom", "example", "instance",
    "structure", "inductive", "class", "namespace", "section", "end", "open",
    "variable", "universe", "attribute", "private", "protected", "noncomputable",
    "unsafe", "partial", "scoped", "local",
})
_ALLOWED_TOML_TOP_KEYS = frozenset({"name", "version", "defaultTargets", "lean_lib"})
_ALLOWED_TOML_LIB_KEYS = frozenset({"name", "srcDir", "roots", "globs"})
_SKIP_DIR_SEGS = frozenset({".git", ".lake", ".venv", "venv", "node_modules", "__pycache__"})
_MOD_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
_GLOB_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\.\+|\.\*)?\Z")
_PKG_NAME_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_-]*\Z")
_VER_RE = re.compile(r"\A[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?\Z")
_AXIOM_NONE_RE = re.compile(r"\A'([^']+)' does not depend on any axioms\Z")
_AXIOM_LIST_RE = re.compile(r"\A'([^']+)' depends on axioms: \[([^\]]*)\]\Z")
_LEAN_WARN_RE = re.compile(r"(?:^|\s)warning(?:\s*\([^)]*\))?:", re.IGNORECASE)
_UNSAFE_TOML_STRS = ("debug.byAsSorry", "debug.skipKernelTC", "debug.proofAsSorry", "debug.terminalTacticsAsSorry")


class VerifierError(ValueError):
    """Fail-closed error raised by the independent Track S168 verifier."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class _HelpExit(Exception):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__("HELP")


def need(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise VerifierError(code, message)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_exact_int(val: Any) -> bool:
    return type(val) is int


def _median_int(values: Sequence[int]) -> int:
    """Exact integer median (exact middle on odd length; upper-middle index `len // 2` on even length)."""
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def exact_json_equal(a: Any, b: Any) -> bool:
    """Iterative type-exact JSON equality checking BOTH dict key types and value types."""
    stack: list[tuple[Any, Any]] = [(a, b)]
    while stack:
        x, y = stack.pop()
        if type(x) is not type(y):
            return False
        if type(x) is dict:
            if len(x) != len(y):
                return False
            xt = {(type(k), k): v for k, v in x.items()}
            yt = {(type(k), k): v for k, v in y.items()}
            for tk, xv in xt.items():
                if tk not in yt:
                    return False
                stack.append((xv, yt[tk]))
        elif type(x) is list:
            if len(x) != len(y):
                return False
            for xv, yv in zip(x, y):
                stack.append((xv, yv))
        elif x != y:
            return False
    return True


def _open_parent_dir_fd(path: Any, label: str) -> tuple[int, str]:
    if type(path) is str:
        need(len(path) > 0, "BAD_PATH", f"{label}: empty path")
        p = Path(path)
    else:
        need(isinstance(path, Path), "BAD_PATH_TYPE", f"{label}: expected str or Path")
        p = path
    raw = os.fspath(p)
    need("\x00" not in raw, "BAD_PATH", f"{label}: invalid path")
    parts = p.parts
    need(".." not in parts, "DOTDOT_FORBIDDEN", f"{label}: '..' traversal forbidden")
    anchor = os.sep if p.is_absolute() else "."
    segs = parts[1:] if p.is_absolute() else parts
    need(len(segs) >= 1, "BAD_LEAF", f"{label}: invalid leaf")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    cur_fd = -1
    try:
        cur_fd = os.open(anchor, flags)
        for seg in segs[:-1]:
            nxt = os.open(seg, flags, dir_fd=cur_fd)
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, segs[-1]
    except OSError as exc:
        if cur_fd >= 0:
            os.close(cur_fd)
        raise VerifierError("PARENT_OPEN", f"{label}: {exc}") from exc


def _read_bytes_and_stat(path: str | Path, label: str, max_bytes: int = MAX_BYTES) -> tuple[bytes, os.stat_result]:
    parent_dfd, leaf = _open_parent_dir_fd(path, label)
    fd = -1
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_dfd)
            st = os.fstat(fd)
        except OSError as exc:
            raise VerifierError("OPEN_FAILED", f"{label}: {exc}") from exc
        need(stat.S_ISREG(st.st_mode), "NOT_REG_FILE", f"{label}: not a regular file")
        need(st.st_nlink == 1, "HARDLINK_REJECTED", f"{label}: hardlink forbidden (nlink={st.st_nlink})")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            need(total <= max_bytes, "FILE_TOO_BIG", f"{label}: exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks), st
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent_dfd)


def read_nofollow_bytes(path: str | Path, label: str = "file", max_bytes: int = MAX_BYTES) -> bytes:
    raw, _ = _read_bytes_and_stat(path, label, max_bytes)
    return raw


def _check_json_depth_surrogates(obj: Any, max_depth: int = MAX_DEPTH) -> None:
    stack: list[tuple[Any, int]] = [(obj, 1)]
    while stack:
        cur, depth = stack.pop()
        if type(cur) is str:
            for ch in cur:
                need(not (0xD800 <= ord(ch) <= 0xDFFF), "JSON_SURROGATE", "lone surrogate forbidden")
        elif type(cur) is dict:
            need(depth <= max_depth, "JSON_DEPTH", "JSON depth exceeded")
            for k, v in cur.items():
                stack.append((k, depth + 1))
                stack.append((v, depth + 1))
        elif type(cur) is list:
            need(depth <= max_depth, "JSON_DEPTH", "JSON depth exceeded")
            for v in cur:
                stack.append((v, depth + 1))


def parse_exact_json(raw: bytes, label: str = "json") -> Any:
    """Strict float-free RFC-8259 JSON parser (no BOM/CR/CRLF, trailing LF, no duplicate keys)."""
    need(len(raw) > 0, "EMPTY_JSON", f"{label}: empty JSON")
    need(not raw.startswith(b"\xef\xbb\xbf"), "BOM_FORBIDDEN", f"{label}: BOM forbidden")
    need(b"\r" not in raw, "CR_FORBIDDEN", f"{label}: CR/CRLF forbidden")
    need(raw.endswith(b"\n"), "NO_FINAL_LF", f"{label}: trailing LF required")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerifierError("BAD_UTF8", f"{label}: invalid UTF-8") from exc

    def _no_float(tok: str) -> Any:
        raise VerifierError("FLOAT_FORBIDDEN", f"{label}: float forbidden: {tok!r}")

    def _no_const(tok: str) -> Any:
        raise VerifierError("CONST_FORBIDDEN", f"{label}: non-finite constant: {tok!r}")

    def _strict_int(tok: str) -> int:
        digits = len(tok) - 1 if tok.startswith("-") else len(tok)
        need(digits <= MAX_INT_DIGITS, "INT_TOO_LONG", f"{label}: integer > {MAX_INT_DIGITS} digits")
        return int(tok)

    def _no_dup(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for k, v in pairs:
            need(k not in d, "DUP_KEY", f"{label}: duplicate key {k!r}")
            d[k] = v
        return d

    try:
        obj = json.loads(text, parse_float=_no_float, parse_constant=_no_const, parse_int=_strict_int, object_pairs_hook=_no_dup)
    except VerifierError:
        raise
    except (ValueError, RecursionError) as exc:
        raise VerifierError("JSON_SYNTAX", f"{label}: {exc}") from exc
    _check_json_depth_surrogates(obj)
    return obj


def _canon_bytes(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def atomic_write_nofollow(path: str | Path, raw: bytes) -> None:
    parent_dfd, leaf = _open_parent_dir_fd(path, "write_cert")
    tmp_name = f".{leaf[:64]}.ver_{os.getpid()}_{secrets.token_hex(12)}.tmp"
    fd = -1
    created = False
    try:
        try:
            st = os.lstat(leaf, dir_fd=parent_dfd)
        except FileNotFoundError:
            st = None
        except OSError as exc:
            raise VerifierError("WRITE_LSTAT", str(exc)) from exc
        mode = 0o644
        if st is not None:
            need(stat.S_ISREG(st.st_mode), "WRITE_NOT_REG", "existing write target is not regular file")
            need(st.st_nlink == 1, "WRITE_HARDLINK", "refusing to overwrite hardlinked target")
            mode = stat.S_IMODE(st.st_mode)
        try:
            fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=parent_dfd)
            created = True
            os.fchmod(fd, mode)
            off = 0
            while off < len(raw):
                n = os.write(fd, raw[off:])
                need(n > 0, "WRITE_ZERO", "short zero write")
                off += n
            os.fsync(fd)
            os.close(fd)
            fd = -1
            os.replace(tmp_name, leaf, src_dir_fd=parent_dfd, dst_dir_fd=parent_dfd)
            created = False
        except OSError as exc:
            raise VerifierError("WRITE_IO", str(exc)) from exc
        try:
            os.fsync(parent_dfd)
        except OSError as exc:
            if exc.errno not in (errno.EINVAL, errno.EROFS):
                raise VerifierError("DIR_FSYNC", str(exc)) from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if created:
            try:
                os.unlink(tmp_name, dir_fd=parent_dfd)
            except OSError:
                pass
        os.close(parent_dfd)


def _char_lit_end(src: str, i: int, n: int) -> int | None:
    if i + 2 < n and src[i + 1] not in ("\\", "'") and src[i + 2] == "'":
        return i + 3
    if i + 3 < n and src[i + 1] == "\\":
        if src[i + 3] == "'" and src[i + 2] != "\n":
            return i + 4
        esc = src[i + 2]
        if esc == "x" and i + 5 < n and src[i + 5] == "'" and all(c in _HEX_DIGITS for c in src[i + 3 : i + 5]):
            return i + 6
        if esc == "u" and i + 7 < n and src[i + 7] == "'" and all(c in _HEX_DIGITS for c in src[i + 3 : i + 7]):
            return i + 8
    return None


def _is_id_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_id_cont(ch: str) -> bool:
    return ch.isalnum() or ch in "_'!?"


def tokenize_lean4(source: str) -> list[tuple[str, str, int]]:
    """
    Distinct typed-token Lean 4.36.0 lexer returning `(kind, text, lineno)` for code tokens only.
    Handles nested `/- -/` comments, `--` line comments, raw strings `r#"..."#`, char literals `'\"'`,
    guillemets `«...»`, and ONLY Init-reserved interpolated strings (`s!`, `f!`, `println!`).
    Any ambiguous non-Init prefix (`m!`, `throwError`, `throwErrorAt`, `dbg_trace`, `log*`,
    arg macros, arbitrary `<ident>!`) followed by a string containing `{` or `}` fails closed
    (`LEAN_AMBIG_INTERP`), closing all HIGH-1 plain/interp desynchronization exploits.
    """
    tokens: list[tuple[str, str, int]] = []
    i = 0
    n = len(source)
    lineno = 1
    interp_braces: list[list[int]] = []
    pending_args = 0
    arg_depth = 0
    ambig_next_quote = False
    prev_was_dot = False

    def _consume_block_comment(pos: int) -> tuple[int, int]:
        depth = 1
        step = 3 if (pos + 2 < n and source[pos + 2] in ("-", "!")) else 2
        ln_inc = 0
        p = pos + step
        while p < n and depth > 0:
            if source.startswith("/-", p):
                depth += 1
                p += 2
            elif source.startswith("-/", p):
                depth -= 1
                p += 2
            else:
                if source[p] == "\n":
                    ln_inc += 1
                p += 1
        need(depth == 0, "LEAN_UNTERM_LEX", "unterminated block comment")
        return p, ln_inc

    def _consume_plain_string(pos: int, *, forbid_braces: bool, start_line: int) -> tuple[int, int]:
        p = pos + 1
        ln_inc = 0
        while p < n:
            if source[p] == "\\" and p + 1 < n:
                if forbid_braces and source[p + 1] in "{}":
                    raise VerifierError("LEAN_AMBIG_INTERP", f"line {start_line}: ambiguous non-Init interpolated string with braces")
                if source[p + 1] == "\n":
                    ln_inc += 1
                p += 2
            elif source[p] == '"':
                return p + 1, ln_inc
            else:
                if forbid_braces and source[p] in "{}":
                    raise VerifierError("LEAN_AMBIG_INTERP", f"line {start_line}: ambiguous non-Init interpolated string with braces")
                if source[p] == "\n":
                    ln_inc += 1
                p += 1
        raise VerifierError("LEAN_UNTERM_LEX", "unterminated string literal")

    def _consume_raw_string(pos: int, hashes: int) -> tuple[int, int]:
        close_seq = '"' + ("#" * hashes)
        p = pos + 2 + hashes
        ln_inc = 0
        while p < n:
            if source.startswith(close_seq, p):
                return p + len(close_seq), ln_inc
            if source[p] == "\n":
                ln_inc += 1
            p += 1
        raise VerifierError("LEAN_UNTERM_LEX", "unterminated raw string literal")

    def _peek_next_code(pos: int) -> int:
        p = pos
        while p < n:
            if source[p].isspace():
                p += 1
            elif source.startswith("--", p):
                while p < n and source[p] != "\n":
                    p += 1
            elif source.startswith("/-", p):
                p, _ = _consume_block_comment(p)
            else:
                break
        return p

    while i < n:
        # Inside Init-reserved interpolated string text mode (`interp_braces[-1][0] == 0`)
        if interp_braces and interp_braces[-1][0] == 0:
            ch = source[i]
            if ch == "\\" and i + 1 < n:
                if source[i + 1] == "\n":
                    lineno += 1
                i += 2
            elif ch == '"':
                _, saved_pa, saved_ad = interp_braces.pop()
                pending_args = saved_pa
                arg_depth = saved_ad
                i += 1
                if pending_args > 0 and arg_depth == 0:
                    pending_args -= 1
                    ambig_next_quote = pending_args == 0
            elif ch == "{":
                interp_braces[-1][0] = 1
                prev_was_dot = False
                i += 1
            else:
                if ch == "\n":
                    lineno += 1
                i += 1
            continue

        ch = source[i]
        if ch == "\n":
            tokens.append(("NL", "\n", lineno))
            lineno += 1
            i += 1
            continue
        if ch.isspace():
            i += 1
            continue
        if source.startswith("--", i):
            while i < n and source[i] != "\n":
                i += 1
            continue
        if source.startswith("/-", i):
            i, inc = _consume_block_comment(i)
            lineno += inc
            continue

        was_ambig = ambig_next_quote
        ambig_next_quote = False

        # Raw string r#"..."# (only when not preceded by `.`)
        if ch == "r" and not prev_was_dot:
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                i, inc = _consume_raw_string(i, j - (i + 1))
                lineno += inc
                prev_was_dot = False
                if pending_args > 0 and arg_depth == 0:
                    pending_args -= 1
                    ambig_next_quote = pending_args == 0
                continue

        # Plain string literal (rejecting `{`/`}` when preceded by an ambiguous non-Init prefix)
        if ch == '"':
            i, inc = _consume_plain_string(i, forbid_braces=was_ambig, start_line=lineno)
            lineno += inc
            prev_was_dot = False
            if pending_args > 0 and arg_depth == 0:
                pending_args -= 1
                ambig_next_quote = pending_args == 0
            continue

        # Char literal (`'"'`, `'\n'`, `'\x41'`, `'\u0041'`)
        if ch == "'":
            cend = _char_lit_end(source, i, n)
            if cend is not None:
                if source[i + 1] == "\n":
                    lineno += 1
                i = cend
                prev_was_dot = False
                if pending_args > 0 and arg_depth == 0:
                    pending_args -= 1
                    ambig_next_quote = pending_args == 0
                continue

        # Guillemet identifier `«...»` (safe on empty `«»«»`)
        if ch == "«":
            end_g = source.find("»", i + 1)
            need(end_g != -1, "LEAN_UNTERM_IDENT", "unterminated guillemet identifier")
            inner = source[i + 1 : end_g]
            ln_inc = inner.count("\n")
            ident = inner.replace("\n", " ").strip()
            if ident:
                tokens.append(("IDENT", ident, lineno))
            lineno += ln_inc
            i = max(i + 1, end_g + 1)
            prev_was_dot = False
            if pending_args > 0 and arg_depth == 0:
                pending_args -= 1
                ambig_next_quote = pending_args == 0
            continue

        # Numeric literal (ensures `throwErrorAt 1 "{"` decrements pending_args cleanly)
        if ch.isdigit():
            k = i + 1
            while k < n and (source[k].isalnum() or source[k] == "_"):
                k += 1
            tokens.append(("NUM", source[i:k], lineno))
            i = k
            prev_was_dot = False
            # Projection chains (`p.1.2`) only complete the argument at their LAST component (Delta-5 LOW-3)
            if pending_args > 0 and arg_depth == 0 and not (i < n and source[i] == "."):
                pending_args -= 1
                ambig_next_quote = pending_args == 0
            continue

        # Closing/opening braces inside active Init-reserved interpolation expression
        if interp_braces:
            if ch == "{":
                interp_braces[-1][0] += 1
                tokens.append(("SYM", "{", lineno))
                prev_was_dot = False
                i += 1
                continue
            if ch == "}":
                interp_braces[-1][0] -= 1
                if interp_braces[-1][0] > 0:
                    tokens.append(("SYM", "}", lineno))
                prev_was_dot = False
                i += 1
                continue

        # Identifier / keyword / Init-reserved or ambiguous interpolation prefix
        if _is_id_start(ch):
            k = i + 1
            while k < n and _is_id_cont(source[k]):
                k += 1
            tok = source[i:k]
            if not prev_was_dot and tok == "Macro" and k < n and source[k] == "." and source.startswith("trace[", k + 1):
                tokens.append(("IDENT", "Macro.trace", lineno))
                tokens.append(("SYM", "[", lineno))
                i = k + 7
                pending_args = 1
                arg_depth = 1
                prev_was_dot = False
                continue
            if not prev_was_dot and tok in _ALLOWLIST_INTERP_ARG_MACROS:
                argc, needs_br = _ALLOWLIST_INTERP_ARG_MACROS[tok]
                if needs_br and k < n and source[k] == "[":
                    tokens.append(("IDENT", tok, lineno))
                    tokens.append(("SYM", "[", lineno))
                    i = k + 1
                    pending_args = argc
                    arg_depth = 1
                    prev_was_dot = False
                    continue
                if not needs_br:
                    tokens.append(("IDENT", tok, lineno))
                    i = k
                    pending_args = argc
                    arg_depth = 0
                    prev_was_dot = False
                    continue
            if not prev_was_dot and tok in _INIT_RESERVED_INTERP_BANGS:
                nxt_q = _peek_next_code(k)
                if nxt_q < n and source[nxt_q] == '"':
                    lineno += source.count("\n", i, nxt_q + 1)
                    interp_braces.append([0, pending_args, arg_depth])
                    pending_args = 0
                    arg_depth = 0
                    i = nxt_q + 1
                    prev_was_dot = False
                    continue
            if not prev_was_dot and (tok.endswith("!") or tok in _AMBIG_INTERP_PLAINS):
                nxt_q = _peek_next_code(k)
                if nxt_q < n and source[nxt_q] == '"':
                    ambig_next_quote = True
            tokens.append(("IDENT", tok, lineno))
            i = k
            prev_was_dot = False
            if pending_args > 0 and arg_depth == 0:
                if not (i < n and source[i] == "."):
                    pending_args -= 1
                    ambig_next_quote = pending_args == 0
            continue

        # Multi-char operators relevant to Lean tactics
        if source.startswith("<;>", i):
            tokens.append(("SYM", "<;>", lineno))
            prev_was_dot = False
            i += 3
            continue
        if source.startswith("=>", i) or source.startswith(":=", i):
            tokens.append(("SYM", source[i : i + 2], lineno))
            prev_was_dot = False
            i += 2
            continue

        # Single-char symbol
        if pending_args > 0:
            # `#[...]` array literals and `⟨...⟩` anonymous constructors are single arguments (Delta-5 LOW-3)
            if ch in "([{⟨":
                arg_depth += 1
            elif ch in ")]}⟩" and arg_depth > 0:
                arg_depth -= 1
                if arg_depth == 0:
                    pending_args -= 1
                    ambig_next_quote = pending_args == 0
            elif arg_depth == 0 and ch != "." and not (ch == "#" and source.startswith("[", i + 1)):
                pending_args = 0

        tokens.append(("SYM", ch, lineno))
        prev_was_dot = (ch == ".")
        i += 1

    need(len(interp_braces) == 0, "LEAN_UNTERM_LEX", "unterminated interpolated string literal")
    return tokens


def strip_lean_comments(source: str) -> str:
    """Reconstruct normalized token-stream Lean source with comments and literals removed."""
    toks = tokenize_lean4(source)
    parts: list[str] = []
    for kind, text, _ in toks:
        if kind == "NL":
            parts.append("\n")
        else:
            if parts and parts[-1] != "\n":
                parts.append(" ")
            parts.append(text)
    return "".join(parts)


def audit_lean_static(source: str) -> list[str]:
    """Audit Lean 4.36.0 source via typed token stream and return declared public theorem names."""
    raw_toks = tokenize_lean4(source)

    # Strip `_root_.` prefix tokens while preserving lines
    toks: list[tuple[str, str, int]] = []
    idx = 0
    nt = len(raw_toks)
    while idx < nt:
        k, txt, ln = raw_toks[idx]
        if k == "IDENT" and txt == "_root_":
            j = idx + 1
            while j < nt and raw_toks[j][0] == "NL":
                j += 1
            if j < nt and raw_toks[j][0] == "SYM" and raw_toks[j][1] == ".":
                idx = j + 1
                continue
        toks.append((k, txt, ln))
        idx += 1

    # Non-NL code stream for cross-line pattern checks
    code: list[tuple[str, str, int]] = [t for t in toks if t[0] != "NL"]
    nc = len(code)
    has_var = False
    has_inc = False

    for ci, (kind, txt, ln) in enumerate(code):
        if kind == "IDENT":
            if txt in _FORBIDDEN_KW_TOKENS:
                raise VerifierError("LEAN_FORBIDDEN_KW", f"line {ln}: forbidden keyword {txt!r}")
            if txt == "stop":
                raise VerifierError("LEAN_STOP_TACTIC", f"line {ln}: stop tactic forbidden")
            if txt in _FORBIDDEN_IDENT_TOKENS or txt == "_native":
                raise VerifierError("LEAN_FORBIDDEN_AX", f"line {ln}: forbidden identifier {txt!r}")
            if txt in _FORBIDDEN_DOTTED_DEBUG:
                raise VerifierError("LEAN_DEBUG_ESCAPE", f"line {ln}: forbidden {txt}")
            if txt in _FORBIDDEN_DOTTED_META:
                raise VerifierError("LEAN_META_ESCAPE", f"line {ln}: forbidden {txt}")
            if txt == "variable":
                has_var = True
            elif txt == "include":
                has_inc = True
            elif txt == "Lean":
                if ci + 2 < nc and code[ci + 1][1] == "." and code[ci + 2][1] in ("Elab", "Meta"):
                    raise VerifierError("LEAN_META_ESCAPE", f"line {ln}: forbidden Lean.{code[ci + 2][1]}")
            elif txt == "debug":
                if ci + 2 < nc and code[ci + 1][1] == "." and code[ci + 2][1] in _FORBIDDEN_DEBUG_SUFFIXES:
                    raise VerifierError("LEAN_DEBUG_ESCAPE", f"line {ln}: forbidden debug.{code[ci + 2][1]}")
            elif txt == "partial":
                j = ci + 1
                while j < nc and code[j][1] in ("private", "protected", "noncomputable", "unsafe"):
                    j += 1
                if j < nc and code[j][1] in _PARTIAL_TARGETS:
                    raise VerifierError("LEAN_PARTIAL", f"line {ln}: partial declaration forbidden")
            elif txt == "decide":
                j = ci + 1
                while j < nc:
                    if code[j][1] == "+":
                        j += 2
                    elif code[j][1] == "(":
                        pdepth = 1
                        j += 1
                        while j < nc and pdepth > 0:
                            if code[j][1] == "(":
                                pdepth += 1
                            elif code[j][1] == ")":
                                pdepth -= 1
                            elif code[j][1] in ("native", "config"):
                                raise VerifierError("LEAN_DECIDE_NATIVE", f"line {ln}: decide ({code[j][1]} := ...) forbidden")
                            j += 1
                    else:
                        break
            elif txt == "attribute" and ci + 1 < nc and code[ci + 1][1] == "[":
                j = ci + 2
                while j < nc and code[j][1] != "]":
                    need(code[j][1] not in _FORBIDDEN_ATTR_TOKENS, "LEAN_ATTR_ESCAPE", f"line {ln}: forbidden attribute {code[j][1]!r}")
                    j += 1
        elif kind == "SYM":
            if txt == "+" and ci + 1 < nc and code[ci + 1][1] == "native":
                raise VerifierError("LEAN_DECIDE_NATIVE", f"line {ln}: +native option forbidden")
            if txt == "#" and ci + 1 < nc and code[ci + 1][1] in _FORBIDDEN_HASH_CMDS:
                raise VerifierError("LEAN_HASH_ESCAPE", f"line {ln}: forbidden command #{code[ci + 1][1]}")
            if txt == "@" and ci + 1 < nc and code[ci + 1][1] == "[":
                j = ci + 2
                while j < nc and code[j][1] != "]":
                    need(code[j][1] not in _FORBIDDEN_ATTR_TOKENS, "LEAN_ATTR_ESCAPE", f"line {ln}: forbidden attribute {code[j][1]!r}")
                    j += 1

    need(not (has_var and has_inc), "LEAN_VAR_INC", "variable+include forbidden")

    # Multiline-aware public theorem extraction with exact per-segment namespace/section stack
    scopes: list[tuple[str, str]] = []
    thms: list[str] = []
    pending_private = False
    ci = 0
    while ci < nc:
        kind, txt, _ = code[ci]
        if txt == "@" and ci + 1 < nc and code[ci + 1][1] == "[":
            ci += 2
            while ci < nc and code[ci][1] != "]":
                ci += 1
            ci += 1
            continue
        if txt in ("protected", "noncomputable", "scoped", "local"):
            ci += 1
            continue
        if txt == "private":
            pending_private = True
            ci += 1
            continue
        if txt == "namespace" and ci + 1 < nc and code[ci + 1][0] == "IDENT":
            ns_parts = [code[ci + 1][1]]
            ci += 2
            while ci + 1 < nc and code[ci][1] == "." and code[ci + 1][0] == "IDENT":
                ns_parts.append(code[ci + 1][1])
                ci += 2
            for seg in ns_parts:
                scopes.append(("namespace", seg))
            pending_private = False
            continue
        if txt == "section":
            if ci + 1 < nc and code[ci + 1][0] == "IDENT" and code[ci + 1][1] not in _TOP_DECL_WORDS:
                sec_parts = [code[ci + 1][1]]
                ci += 2
                while ci + 1 < nc and code[ci][1] == "." and code[ci + 1][0] == "IDENT":
                    sec_parts.append(code[ci + 1][1])
                    ci += 2
                for seg in sec_parts:
                    scopes.append(("section", seg))
            else:
                scopes.append(("section", ""))
                ci += 1
            pending_private = False
            continue
        if txt == "end":
            if ci + 1 < nc and code[ci + 1][0] == "IDENT" and scopes:
                end_parts = [code[ci + 1][1]]
                j = ci + 2
                while j + 1 < nc and code[j][1] == "." and code[j + 1][0] == "IDENT":
                    end_parts.append(code[j + 1][1])
                    j += 2
                k_end = len(end_parts)
                if len(scopes) >= k_end and [nm for _, nm in scopes[-k_end:]] == end_parts:
                    del scopes[-k_end:]
                    ci = j
                    pending_private = False
                    continue
            if scopes:
                scopes.pop()
            pending_private = False
            ci += 1
            continue
        if txt in ("theorem", "lemma") and ci + 1 < nc and code[ci + 1][0] == "IDENT":
            name_parts = [code[ci + 1][1]]
            ci += 2
            while ci + 1 < nc and code[ci][1] == "." and code[ci + 1][0] == "IDENT":
                name_parts.append(code[ci + 1][1])
                ci += 2
            if not pending_private:
                ns_prefix = [nm for sk, nm in scopes if sk == "namespace" and nm]
                thms.append(".".join((*ns_prefix, *name_parts)))
            pending_private = False
            continue
        pending_private = False
        ci += 1
    return thms


def _audit_lakefile_toml_strict(lf_text: str) -> None:
    try:
        toml_obj = tomllib.loads(lf_text)
    except tomllib.TOMLDecodeError as exc:
        raise VerifierError("LAKEFILE_TOML", str(exc)) from exc
    for k, v in toml_obj.items():
        need(k in _ALLOWED_TOML_TOP_KEYS, "LAKEFILE_UNSAFE_KEY", f"unsafe lakefile key {k}")
        if k == "name":
            need(type(v) is str and _PKG_NAME_RE.match(v) is not None, "LAKEFILE_BAD_SCHEMA", "invalid lakefile name")
        elif k == "version":
            need(type(v) is str and _VER_RE.match(v) is not None, "LAKEFILE_BAD_SCHEMA", "invalid lakefile version")
        elif k == "defaultTargets":
            need(
                type(v) is list
                and all(type(x) is str and _MOD_RE.match(x) is not None and not any(s in _SKIP_DIR_SEGS for s in x.split(".")) for x in v),
                "LAKEFILE_BAD_SCHEMA",
                "invalid defaultTargets",
            )
        elif k == "lean_lib":
            need(type(v) is list, "LAKEFILE_BAD_SCHEMA", "lean_lib must be list")
            for entry in v:
                need(type(entry) is dict, "LAKEFILE_BAD_SCHEMA", "lean_lib item must be dict")
                for lk, lv in entry.items():
                    need(lk in _ALLOWED_TOML_LIB_KEYS, "LAKEFILE_UNSAFE_KEY", f"unsafe lean_lib key {lk}")
                    if lk == "name":
                        need(
                            type(lv) is str and _MOD_RE.match(lv) is not None and not any(s in _SKIP_DIR_SEGS for s in lv.split(".")),
                            "LAKEFILE_UNSAFE_ROOT",
                            f"bad lean_lib name {lv!r}",
                        )
                    elif lk == "srcDir":
                        need(type(lv) is str and len(lv) > 0 and "\x00" not in lv and not lv.startswith(("/", "\\")), "LAKEFILE_UNSAFE_PATH", f"unsafe srcDir {lv!r}")
                        if lv != ".":
                            segs = re.split(r"[/\\]", lv)
                            need(all(s and s != ".." and s not in _SKIP_DIR_SEGS and not s.startswith(".") for s in segs), "LAKEFILE_UNSAFE_PATH", f"unsafe srcDir {lv!r}")
                    elif lk == "roots":
                        need(
                            type(lv) is list and all(type(x) is str and _MOD_RE.match(x) is not None and not any(s in _SKIP_DIR_SEGS for s in x.split(".")) for x in lv),
                            "LAKEFILE_UNSAFE_ROOT",
                            f"unsafe roots {lv!r}",
                        )
                    elif lk == "globs":
                        need(
                            type(lv) is list and all(
                                type(x) is str
                                and _GLOB_RE.match(x) is not None
                                and not any(s in _SKIP_DIR_SEGS for s in x.removesuffix(".+").removesuffix(".*").split("."))
                                for x in lv
                            ),
                            "LAKEFILE_UNSAFE_GLOB",
                            f"unsafe globs {lv!r}",
                        )
    t_stack: list[Any] = [toml_obj]
    while t_stack:
        cur = t_stack.pop()
        if type(cur) is dict:
            t_stack.extend(cur.values())
        elif type(cur) is list:
            t_stack.extend(cur)
        elif type(cur) is str:
            for bad in _UNSAFE_TOML_STRS:
                need(bad not in cur, "LAKEFILE_UNSAFE_STR", f"unsafe lakefile string {cur}")


def _resolve_verified_elf_lean() -> tuple[Path, Path, Path]:
    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    tc_dir_name = EXPECTED_TOOLCHAIN.replace("/", "--").replace(":", "---")
    bin_dir = real_home / ".elan" / "toolchains" / tc_dir_name / "bin"
    lean_bin = bin_dir / "lean"
    lake_bin = bin_dir / "lake"
    for bp, nm in ((lean_bin, "lean"), (lake_bin, "lake")):
        try:
            st = os.lstat(bp)
        except OSError as exc:
            raise VerifierError("LEAN_EXEC_FAILED", f"{nm} missing at {bp}: {exc}") from exc
        need(stat.S_ISREG(st.st_mode) and bool(st.st_mode & 0o111), "LEAN_TOOL_UNTRUSTED", f"{nm} must be regular executable binary")
        fd = os.open(os.fspath(bp), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            hdr = os.read(fd, 4)
        finally:
            os.close(fd)
        need(hdr == b"\x7fELF", "LEAN_TOOL_UNTRUSTED", f"{nm} must be native ELF binary")
    return lean_bin, lake_bin, real_home


def _default_lean_runner(args: Sequence[str], cwd: Path, timeout: int) -> tuple[int, bytes, bytes]:
    lean_bin, lake_bin, real_home = _resolve_verified_elf_lean()
    resolved: list[str] = []
    for idx, tok in enumerate(args):
        if idx == 0 and tok == "lean":
            resolved.append(os.fspath(lean_bin))
        elif idx == 0 and tok == "lake":
            resolved.append(os.fspath(lake_bin))
        elif idx == 2 and len(args) >= 3 and args[0] == "lake" and args[1] == "env" and tok == "lean":
            resolved.append(os.fspath(lean_bin))
        else:
            resolved.append(tok)
    clean_env = {
        "PATH": f"{os.fspath(lean_bin.parent)}:/usr/bin:/bin",
        "HOME": os.fspath(real_home),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    try:
        proc = subprocess.run(resolved, cwd=str(cwd), env=clean_env, capture_output=True, timeout=timeout, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise VerifierError("LEAN_EXEC_FAILED", str(exc)) from exc
    return proc.returncode, proc.stdout, proc.stderr


def verify_lean_bundle(
    track_dir: Path,
    *,
    live_lean: bool = False,
    runner: Callable[[Sequence[str], Path, int], tuple[int, bytes, bytes]] | None = None,
) -> dict[str, Any]:
    """
    Read, hash, statically audit, and optionally live-replay the Lean 4.36.0 bundle.
    Strictly separates `lean_static_status="STATIC_PASS"` from `live_lean_checked` (S166 Delta-6
    pattern) and derives exact axiom counts dynamically only during live execution.
    """
    need(not (track_dir / "lakefile.lean").exists(), "LAKEFILE_LEAN_FORBIDDEN", "executable lakefile.lean forbidden")
    lean_files = ("VelocityBounds.lean", "lean-toolchain", "lakefile.toml", "lake-manifest.json")
    pinned: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for fname in lean_files:
        raw = read_nofollow_bytes(track_dir / fname, fname)
        need(b"\r" not in raw, "LEAN_BUNDLE_CR", f"{fname}: CR/CRLF forbidden")
        pinned[fname] = raw
        hashes[fname] = _sha256(raw)

    try:
        tc_text = pinned["lean-toolchain"].decode("utf-8").strip()
        lf_text = pinned["lakefile.toml"].decode("utf-8")
        lean_text = pinned["VelocityBounds.lean"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerifierError("LEAN_BUNDLE_UTF8", str(exc)) from exc

    need(tc_text == EXPECTED_TOOLCHAIN, "TOOLCHAIN_BAD", f"expected {EXPECTED_TOOLCHAIN}, got {tc_text}")
    manifest = parse_exact_json(pinned["lake-manifest.json"], "lake-manifest.json")
    need(type(manifest) is dict and manifest.get("packages") == [], "MANIFEST_PKGS", "lake-manifest packages must be []")
    _audit_lakefile_toml_strict(lf_text)

    declared = audit_lean_static(lean_text)
    need(tuple(declared) == EXPECTED_THEOREMS, "THEOREM_LIST_MISMATCH", f"declared theorems mismatch: {declared}")

    lean_static_status = "STATIC_PASS"
    lean_live_mode = "STATIC_ONLY"
    live_lean_checked = False
    axioms_verified_count = 0
    zero_ax_cnt: int | None = None
    propext_only_cnt: int | None = None
    propext_quot_cnt: int | None = None

    if live_lean:
        exec_fn = _default_lean_runner if runner is None else runner
        with tempfile.TemporaryDirectory(prefix="s168_lean_ver_") as tmp_s:
            tmp_dir = Path(tmp_s)
            os.chmod(tmp_dir, 0o700)
            for fname, raw in pinned.items():
                dst = tmp_dir / fname
                dst.write_bytes(raw)
                os.chmod(dst, 0o644)
            audit_src = "\n".join(["import VelocityBounds", *(f"#print axioms {t}" for t in EXPECTED_THEOREMS), ""])
            audit_p = tmp_dir / "__AuditS168.lean"
            audit_p.write_bytes(audit_src.encode("utf-8"))
            os.chmod(audit_p, 0o644)

            v_rc, v_out_b, v_err_b = exec_fn(["lean", "--version"], tmp_dir, 60)
            try:
                v_out = v_out_b.decode("utf-8").strip()
                _ = v_err_b.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise VerifierError("LIVE_LEAN_UTF8", str(exc)) from exc
            need(v_rc == 0 and EXPECTED_LEAN_VERSION_TOKEN in v_out, "LEAN_VER_BAD", f"unexpected Lean version: {v_out}")

            b_rc, b_out_b, b_err_b = exec_fn(["lake", "build"], tmp_dir, 120)
            try:
                b_out = b_out_b.decode("utf-8")
                b_err = b_err_b.decode("utf-8").strip()
            except UnicodeDecodeError as exc:
                raise VerifierError("LIVE_LEAN_UTF8", str(exc)) from exc
            need(b_rc == 0 and b_err == "", "LAKE_BUILD_BAD", f"lake build rc={b_rc} err={b_err}")
            need(_LEAN_WARN_RE.search(b_out) is None, "LAKE_BUILD_WARNING", f"lake build emitted warning: {b_out.strip()[:200]}")

            a_rc, a_out_b, a_err_b = exec_fn(["lake", "env", "lean", "__AuditS168.lean"], tmp_dir, 120)
            try:
                a_out = a_out_b.decode("utf-8")
                a_err = a_err_b.decode("utf-8").strip()
            except UnicodeDecodeError as exc:
                raise VerifierError("LIVE_LEAN_UTF8", str(exc)) from exc
            need(a_rc == 0 and a_err == "", "AXIOM_EXEC_BAD", f"axiom check rc={a_rc} err={a_err}")

            seen: dict[str, tuple[str, ...]] = {}
            for line in a_out.splitlines():
                s = line.strip()
                if not s:
                    continue
                m0 = _AXIOM_NONE_RE.match(s)
                if m0 is not None:
                    need(m0.group(1) not in seen, "AXIOM_DUP_THEOREM", f"duplicate axiom report for {m0.group(1)}")
                    seen[m0.group(1)] = ()
                    continue
                m1 = _AXIOM_LIST_RE.match(s)
                need(m1 is not None, "AXIOM_LINE_BAD", f"unparsed axiom line: {s!r}")
                need(m1.group(1) not in seen, "AXIOM_DUP_THEOREM", f"duplicate axiom report for {m1.group(1)}")
                axs = tuple(tok.strip() for tok in m1.group(2).split(",") if tok.strip())
                for ax in axs:
                    need(ax in ALLOWED_AXIOMS, "FORBIDDEN_AXIOM", f"{m1.group(1)} uses disallowed axiom {ax}")
                seen[m1.group(1)] = axs

            need(set(seen.keys()) == set(EXPECTED_THEOREMS), "AXIOM_SET_MISMATCH", "missing or extra theorems in #print axioms")
            actual_zero = {k for k, v in seen.items() if v == ()}
            actual_prop = {k for k, v in seen.items() if v == ("propext",)}
            actual_prop_quot = {k for k, v in seen.items() if len(v) == 2 and set(v) == {"propext", "Quot.sound"}}
            need(actual_zero == EXPECTED_ZERO_AXIOM_THEOREMS, "ZERO_AX_SPLIT_MISMATCH", f"zero-axiom split mismatch: {sorted(actual_zero)}")
            need(actual_prop == EXPECTED_PROPEXT_ONLY_THEOREMS, "PROPEXT_SPLIT_MISMATCH", f"propext split mismatch: {sorted(actual_prop)}")
            need(
                len(actual_zero) + len(actual_prop) + len(actual_prop_quot) == len(seen),
                "AXIOM_PARTITION_MISMATCH",
                "unexpected axiom combination outside {}, {propext}, {propext, Quot.sound}",
            )
            lean_live_mode = "LIVE_LEAN_4_36_0_PASS"
            live_lean_checked = True
            axioms_verified_count = len(seen)
            zero_ax_cnt = len(actual_zero)
            propext_only_cnt = len(actual_prop)
            propext_quot_cnt = len(actual_prop_quot)

    return {
        "axioms_verified_count": axioms_verified_count,
        "file_sha256": hashes,
        "lean_live_mode": lean_live_mode,
        "lean_module": "VelocityBounds",
        "lean_static_status": lean_static_status,
        "lean_toolchain": EXPECTED_TOOLCHAIN,
        "live_lean_checked": live_lean_checked,
        "propext_only_theorems": propext_only_cnt,
        "propext_quot_theorems": propext_quot_cnt,
        "public_theorems": len(EXPECTED_THEOREMS),
        "zero_axiom_theorems": zero_ax_cnt,
    }


def _eval_failfast_vec(vec: Sequence[bool]) -> tuple[bool, int]:
    ff_killed = False
    ff_steps = 0
    for r in vec:
        ff_steps += 1
        if not r:
            ff_killed = True
            break
    return ff_killed, ff_steps


def _eval_dedup_pass2(k1: Sequence[int], m2: Sequence[int]) -> list[int]:
    k1_set = set(k1)
    return [s for s in m2 if s not in k1_set]


def _extract_lean_trust_core_witness(lean_text: str) -> tuple[int, int, int]:
    """Extract `(C_core, be_n, n6_saved)` from live (comment-stripped) `VelocityBounds.lean` Theorem 14 witness."""
    m = _LEAN_TC_WITNESS_RE.search(strip_lean_comments(lean_text))
    need(m is not None, "LEAN_TC_WITNESS_MISSING", "VelocityBounds.lean missing measured trust_core LOC witness")
    n_prev_l, c1, n_prev_r = int(m.group(1)), int(m.group(2)), int(m.group(3))
    c2, n_be_l, n_be_r = int(m.group(4)), int(m.group(5)), int(m.group(6))
    c3, saved_n6 = int(m.group(7)), int(m.group(8))
    need(
        n_prev_l == n_prev_r and n_be_l == n_be_r and n_be_l == n_prev_l + 1 and c1 == c2 == c3,
        "LEAN_TC_WITNESS_INCONSISTENT",
        "inconsistent trust_core LOC witness in VelocityBounds.lean",
    )
    return c1, n_be_l, saved_n6


def verify_pillar1_math(
    *,
    two_stage_cases: Sequence[tuple[str, int, int, int, Fraction, bool]] | None = None,
    dedup_cases: Sequence[tuple[Sequence[int], Sequence[int], int]] | None = None,
    failfast_max_len: int = 7,
    amort_params: tuple[int, int, int, int] = (540, 420, 20, 1860),
    preflight_params: tuple[int, int, int, int, int] = (2, 900, 3, 1, 1798),
    trust_core_nonempty_loc: int | None = None,
    expected_lean_trust_core_loc: int | None = None,
    expected_lean_be_n: int | None = None,
    expected_lean_n6_saved: int | None = None,
    failfast_eval: Callable[[Sequence[bool]], tuple[bool, int]] | None = None,
    dedup_eval: Callable[[Sequence[int], Sequence[int]], list[int]] | None = None,
    breakeven_override: int | None = None,
) -> dict[str, Any]:
    """Independently compute & verify exact rational acceleration, dedup, failfast, and amortization identities."""
    # 1. Two-stage kill-gate grid with exact per-branch threshold `(Tmono - T1) / T2`
    ts_cases = two_stage_cases if two_stage_cases is not None else [
        ("wave22_killgate_win", 10, 180, 180, Fraction(1, 3), True),
        ("exact_boundary_tie", 30, 180, 180, Fraction(5, 6), False),
        ("above_threshold_loss", 30, 180, 180, Fraction(7, 8), False),
        ("unit_survival_overhead", 10, 180, 180, Fraction(1, 1), False),
        ("dual_accel_stage2", 10, 60, 180, Fraction(1, 2), True),
    ]
    two_stage_out: list[dict[str, Any]] = []
    for cid, t1, t2, tmono, psurv, expected_win in ts_cases:
        t_exp = Fraction(t1) + psurv * Fraction(t2)
        need(
            t1 >= 0 and t2 > 0 and tmono > 0 and Fraction(0) <= psurv <= Fraction(1) and t_exp > 0,
            "MATH_TWO_STAGE_DOMAIN",
            f"invalid physical domain parameter in {cid}",
        )
        thresh = Fraction(tmono - t1, t2)
        strict_win = (psurv < thresh)
        need(strict_win is expected_win, "MATH_TWO_STAGE_BAD", f"two-stage case {cid} mismatch")
        two_stage_out.append({
            "case_id": cid,
            "t_2stage_q": str(t_exp),
            "t_mono_q": str(Fraction(tmono)),
            "p_surv_q": str(psurv),
            "threshold_q": str(thresh),
            "speedup_q": str(Fraction(tmono) / t_exp),
            "strict_win": strict_win,
        })

    # 2. Lossless Pass-2 mutant deduplication checks
    dd_fn = _eval_dedup_pass2 if dedup_eval is None else dedup_eval
    dd_cases = dedup_cases if dedup_cases is not None else [
        ([1, 2, 3, 4], [1, 2, 3, 4], 0),
        ([1, 2, 3], [2, 3, 4, 5], 2),
        ([1, 2], [3, 4, 5], 3),
    ]
    for k1, m2, exp_exec in dd_cases:
        dedup_run = dd_fn(k1, m2)
        need(set(k1) | set(m2) == set(k1) | set(dedup_run), "MATH_DEDUP_SET_BAD", "dedup union mismatch")
        need(len(dedup_run) == exp_exec, "MATH_DEDUP_COUNT_BAD", "dedup exec count mismatch")

    # 3. Exhaustive 255-case `--failfast` kill equivalence, upper bound, and strict early-fail savings
    need(failfast_max_len >= 0, "MATH_FF_MAX_LEN_BAD", "failfast_max_len must be >= 0")
    ff_fn = _eval_failfast_vec if failfast_eval is None else failfast_eval
    checked_vectors = 0
    strict_step_savings = 0
    for length in range(failfast_max_len + 1):
        for mask in range(1 << length):
            vec = [bool((mask >> bit) & 1) for bit in range(length)]
            full_killed = any(not r for r in vec)
            ff_killed, ff_steps = ff_fn(vec)
            need(ff_killed is full_killed, "MATH_FF_EQUIV_BAD", f"failfast kill mismatch on {vec}")
            need(ff_steps <= length, "MATH_FF_BOUND_BAD", f"failfast steps > length on {vec}")
            has_early_fail = any(not vec[i] for i in range(max(0, length - 1)))
            need((ff_steps < length) is has_early_fail, "MATH_FF_STRICT_BAD", f"failfast strict savings mismatch on {vec}")
            if ff_steps < length:
                strict_step_savings += 1
            checked_vectors += 1

    # 4. Shared trust_core N-track amortization (illustrative minimal model + measured actual LOC bound to Lean T14)
    c_core, b_dup, b_drop, exp_saved_n6 = amort_params
    per_track_gain = b_dup - b_drop
    need(per_track_gain > 0, "MATH_AMORT_GAIN_BAD", "b_dup must strictly exceed b_drop")
    breakeven_n = ((c_core // per_track_gain) + 1) if breakeven_override is None else breakeven_override
    need(c_core + (breakeven_n - 1) * b_drop >= (breakeven_n - 1) * b_dup, "MATH_AMORT_PREV_BAD", "N-1 should not break even")
    need(c_core + breakeven_n * b_drop < breakeven_n * b_dup, "MATH_AMORT_BE_BAD", "N should strictly break even")
    saved_n6 = 6 * b_dup - (c_core + 6 * b_drop)
    need(saved_n6 == exp_saved_n6, "MATH_AMORT_N6_BAD", "N=6 LOC savings mismatch")

    p_sec, a_sec, r_mono, r_pre, exp_pf_saved = preflight_params
    preflight_saved_sec = r_mono * a_sec - (p_sec + r_pre * a_sec)
    need(preflight_saved_sec == exp_pf_saved, "MATH_PREFLIGHT_SAVED_BAD", "preflight savings mismatch")

    out: dict[str, Any] = {
        "two_stage_grid": two_stage_out,
        "dedup_cases_verified": len(dd_cases),
        "failfast_exhaustive_vectors": checked_vectors,
        "failfast_strict_savings_vectors": strict_step_savings,
        "illustrative_model_params": {
            "c_core_loc": c_core,
            "b_dup_loc": b_dup,
            "b_drop_loc": b_drop,
            "preflight_p_sec": p_sec,
            "audit_round_a_sec": a_sec,
        },
        "trust_core_breakeven_n": breakeven_n,
        "trust_core_n6_loc_saved": saved_n6,
        "preflight_audit_sec_saved": preflight_saved_sec,
    }
    if trust_core_nonempty_loc is not None:
        need(_is_exact_int(trust_core_nonempty_loc) and trust_core_nonempty_loc > 0, "MATH_LOC_BAD", "invalid measured LOC")
        if expected_lean_trust_core_loc is not None:
            need(
                trust_core_nonempty_loc == expected_lean_trust_core_loc,
                "MATH_LOC_LEAN_MISMATCH",
                f"measured trust_core.py LOC ({trust_core_nonempty_loc}) != VelocityBounds.lean witness ({expected_lean_trust_core_loc})",
            )
        meas_be_n = expected_lean_be_n if expected_lean_be_n is not None else ((trust_core_nonempty_loc // per_track_gain) + 1)
        need(
            trust_core_nonempty_loc + (meas_be_n - 1) * b_drop >= (meas_be_n - 1) * b_dup,
            "MATH_MEAS_AMORT_PREV_BAD",
            "measured N-1 should not break even",
        )
        need(
            trust_core_nonempty_loc + meas_be_n * b_drop < meas_be_n * b_dup,
            "MATH_MEAS_AMORT_BE_BAD",
            "measured N should strictly break even",
        )
        meas_saved_n6 = 6 * b_dup - (trust_core_nonempty_loc + 6 * b_drop)
        if expected_lean_n6_saved is not None:
            need(meas_saved_n6 == expected_lean_n6_saved, "MATH_MEAS_N6_MISMATCH", "measured N=6 LOC savings != Lean witness")
        out["measured_trust_core_nonempty_loc"] = trust_core_nonempty_loc
        out["measured_trust_core_breakeven_n"] = meas_be_n
        out["measured_trust_core_n6_loc_saved"] = meas_saved_n6
    return out


def _expected_trial_arm_orders(trials: int) -> list[list[str]]:
    """Independently replay the pinned seeded (`random.Random(168)`) per-trial arm shuffles (Delta-5 LOW-1)."""
    rng = random.Random(EXPECTED_AB_RNG_SEED)
    out: list[list[str]] = []
    for _ in range(trials):
        order = list(_AB_ARM_BASE_ORDER)
        rng.shuffle(order)
        out.append(order)
    return out


def verify_empirical_ab_results(track_dir: Path) -> dict[str, Any]:
    """
    Independently read, hash, check freshness (`results > bench` and `results > core engines`),
    verify strict exact-int types, exact keysets, provenance booleans, fixture & order invariants,
    and recompute iso-worker & end-to-end A/B ratios.
    """
    bench_bytes, bench_st = _read_bytes_and_stat(track_dir / "s168_velocity_bench.py", "s168_velocity_bench.py")
    res_bytes, res_st = _read_bytes_and_stat(track_dir / "s168_ab_results.json", "s168_ab_results.json")
    bench_sha = _sha256(bench_bytes)
    res_sha = _sha256(res_bytes)

    need(res_st.st_mtime_ns > bench_st.st_mtime_ns, "EMPIRICAL_STALE", "s168_ab_results.json must strictly post-date bench script")
    obj = parse_exact_json(res_bytes, "s168_ab_results.json")
    need(type(obj) is dict, "EMPIRICAL_ROOT", "results JSON must be object")
    need(obj.get("schema") == "s168.q56a.velocity_ab_results.v2", "EMPIRICAL_SCHEMA", "unexpected empirical results schema")
    need(obj.get("cpu_only") is True, "EMPIRICAL_CPU_ONLY", "empirical benchmark must run CPU-only")
    need(obj.get("bench_script_sha256") == bench_sha, "EMPIRICAL_BENCH_SHA", "embedded bench_script_sha256 mismatch")
    need(_is_exact_int(obj.get("host_cpu_count")) and obj["host_cpu_count"] >= 1, "EMPIRICAL_HOST_CPU", "host_cpu_count must be exact int >= 1")

    emb_eng = obj.get("engine_source_sha256")
    need(type(emb_eng) is dict, "EMPIRICAL_ENGINE_SHAS_MISSING", "missing engine_source_sha256 mapping")
    need(set(emb_eng.keys()) == set(ENGINE_SOURCE_FILES), "EMPIRICAL_ENGINE_KEYS", "engine_source_sha256 keyset mismatch")
    for eng_name in ENGINE_SOURCE_FILES:
        eb, est = _read_bytes_and_stat(track_dir / eng_name, eng_name)
        need(res_st.st_mtime_ns > est.st_mtime_ns, "EMPIRICAL_STALE_ENGINE", f"s168_ab_results.json must strictly post-date {eng_name}")
        need(type(emb_eng.get(eng_name)) is str and emb_eng[eng_name] == _sha256(eb), "EMPIRICAL_ENGINE_SHA", f"embedded {eng_name} SHA mismatch")

    pf = obj.get("preflight_live")
    need(type(pf) is dict, "EMPIRICAL_PF_MISSING", "preflight_live missing")
    need(pf.get("all_under_2000ms") is True, "EMPIRICAL_PF_SLOW", "preflight exceeded 2000ms")
    sc_cnt = pf.get("synthetic_caught_count")
    st_cnt = pf.get("synthetic_total_count")
    need(_is_exact_int(sc_cnt) and _is_exact_int(st_cnt) and sc_cnt == 5 and st_cnt == 5, "EMPIRICAL_PF_CATCH", "synthetic catch rate < 5/5")
    syn_fix = pf.get("synthetic_fixtures")
    need(
        type(syn_fix) is list
        and len(syn_fix) == st_cnt
        and all(
            type(fx) is dict
            and fx.get("caught") is True
            and type(fx.get("fixture")) is str
            and len(fx["fixture"]) > 0
            and type(fx.get("expected_code")) is str
            and len(fx["expected_code"]) > 0
            and type(fx.get("codes_detected")) is list
            and fx["expected_code"] in fx["codes_detected"]
            and _is_exact_int(fx.get("elapsed_ms"))
            and 0 <= fx["elapsed_ms"] < 2000
            for fx in syn_fix
        )
        and len({fx["fixture"] for fx in syn_fix}) == st_cnt,
        "EMPIRICAL_PF_FIXTURES",
        "synthetic_fixtures provenance invalid",
    )
    s161_pf = pf.get("s161_snapshot")
    s166_pf = pf.get("s166_snapshot")
    need(
        type(s161_pf) is dict
        and s161_pf.get("passed") is True
        and s161_pf.get("under_2000ms") is True
        and _is_exact_int(s161_pf.get("files_scanned"))
        and s161_pf["files_scanned"] > 0
        and _is_exact_int(s161_pf.get("lean_unique_theorems"))
        and s161_pf["lean_unique_theorems"] > 0
        and _is_exact_int(s161_pf.get("finding_count"))
        and s161_pf["finding_count"] == 0
        and _is_exact_int(s161_pf.get("elapsed_ms"))
        and 0 <= s161_pf["elapsed_ms"] < 2000,
        "EMPIRICAL_S161_PF",
        "S161 snapshot preflight invalid",
    )
    need(
        type(s166_pf) is dict
        and s166_pf.get("under_2000ms") is True
        and _is_exact_int(s166_pf.get("files_scanned"))
        and s166_pf["files_scanned"] > 0
        and _is_exact_int(s166_pf.get("lean_unique_theorems"))
        and s166_pf["lean_unique_theorems"] > 0
        and s166_pf.get("finding_codes") == ["MISSING_ALLOW_ABBREV_FALSE"]
        and _is_exact_int(s166_pf.get("finding_count"))
        and s166_pf["finding_count"] == 2
        and _is_exact_int(s166_pf.get("elapsed_ms"))
        and 0 <= s166_pf["elapsed_ms"] < 2000,
        "EMPIRICAL_S166_PF",
        "S166 snapshot preflight invalid",
    )

    mix = obj.get("mixed_parity_check")
    need(
        type(mix) is dict
        and mix.get("parity_exact_100pct") is True
        and mix.get("fast_arm_entrypoint") == "python_api_allow_survivors"
        and all(
            _is_exact_int(mix.get(k))
            for k in (
                "pass1_total", "pass1_killed", "pass1_survived",
                "pass2_total", "pass2_killed", "pass2_survived",
                "pass2_new_sites", "pass2_dedup_skipped",
            )
        )
        and mix["pass1_killed"] > 0
        and mix["pass1_survived"] > 0
        and mix["pass1_total"] == mix["pass1_killed"] + mix["pass1_survived"]
        and mix["pass2_killed"] > mix["pass1_killed"]
        and mix["pass2_survived"] > mix["pass1_survived"]
        and mix["pass2_total"] == mix["pass2_killed"] + mix["pass2_survived"]
        and mix["pass2_new_sites"] > 0
        and mix["pass2_new_sites"] == mix["pass2_total"] - mix["pass1_total"]
        and mix["pass2_dedup_skipped"] == mix["pass1_killed"]
        and type(mix.get("pass1_mutant_set_sha256")) is str
        and _SHA64_RE.match(mix["pass1_mutant_set_sha256"]) is not None
        and type(mix.get("pass2_mutant_set_sha256")) is str
        and _SHA64_RE.match(mix["pass2_mutant_set_sha256"]) is not None
        and mix["pass1_mutant_set_sha256"] != mix["pass2_mutant_set_sha256"],
        "EMPIRICAL_MIXED_PARITY",
        "mixed killed/survived non-redundant Pass-2 parity check invalid",
    )

    ab = obj.get("mutate_ab_benchmark")
    need(type(ab) is dict and ab.get("parity_exact_100pct") is True, "EMPIRICAL_AB_PARITY", "A/B mutant parity failed")
    need(
        ab.get("target_track") == EXPECTED_AB_TARGET_TRACK
        and ab.get("target_script") == EXPECTED_AB_TARGET_SCRIPT
        and ab.get("target_script_sha256") == EXPECTED_AB_TARGET_SHA256,
        "EMPIRICAL_AB_TARGET",
        "A/B target track/script/SHA mismatch",
    )
    need(
        ab.get("staged_from_chmod_aw_ro_copy") is True
        and ab.get("mutated_in_isolated_writable_slots") is True
        and ab.get("source_track_untouched") is True,
        "EMPIRICAL_AB_PROVENANCE",
        "A/B RO staging / isolation provenance flags invalid",
    )
    need(
        type(ab.get("pass1_mutant_set_sha256")) is str
        and _SHA64_RE.match(ab["pass1_mutant_set_sha256"]) is not None
        and ab.get("pass2_mutant_set_sha256") == ab["pass1_mutant_set_sha256"],
        "EMPIRICAL_AB_SET_SHA",
        "A/B pass1/pass2 mutant set SHA mismatch",
    )
    need(ab.get("cli_entrypoint_both_arms") is True, "EMPIRICAL_AB_CLI", "both arms must execute CLI entrypoints")
    need(
        ab.get("rng_seed") == EXPECTED_AB_RNG_SEED
        and _is_exact_int(ab.get("rng_seed"))
        and ab.get("pass2_guard") == EXPECTED_AB_PASS2_GUARD
        and ab.get("test_cmd") == EXPECTED_AB_TEST_CMD,
        "EMPIRICAL_AB_CONFIG",
        "A/B rng_seed / pass2_guard / test_cmd must match the pinned benchmark configuration",
    )
    trials = ab.get("trials")
    need(_is_exact_int(trials) and trials >= 3 and trials % 2 == 1, "EMPIRICAL_AB_TRIALS", "multi-trial benchmark requires odd trials >= 3")
    orders = ab.get("trial_arm_orders")
    need(
        type(orders) is list
        and len(orders) == trials
        and all(type(o) is list and len(o) == 4 and set(o) == _AB_ARM_NAMES for o in orders)
        and orders == _expected_trial_arm_orders(trials),
        "EMPIRICAL_AB_ORDERS",
        "trial_arm_orders must equal the pinned seeded 4-arm permutations for each trial",
    )
    base_w1 = ab.get("baseline_aletheia_w1")
    base_w8 = ab.get("baseline_aletheia_w8")
    fw1 = ab.get("fast_mutate_w1")
    fw8 = ab.get("fast_mutate_w8")
    need(
        type(base_w1) is dict and type(base_w8) is dict and type(fw1) is dict and type(fw8) is dict,
        "EMPIRICAL_AB_STRUCT",
        "missing A/B blocks",
    )

    for lbl, blk, code in (
        ("base_w1", base_w1, "EMPIRICAL_BASE_W1_MS"),
        ("base_w8", base_w8, "EMPIRICAL_BASE_W8_MS"),
        ("fast_w1", fw1, "EMPIRICAL_W1_MS"),
        ("fast_w8", fw8, "EMPIRICAL_W8_MS"),
    ):
        ms_v = blk.get("elapsed_ms")
        t_list = blk.get("trial_elapsed_ms")
        need(_is_exact_int(ms_v) and ms_v > 0, code, f"invalid {lbl} elapsed_ms")
        need(
            type(t_list) is list and len(t_list) == trials and all(_is_exact_int(x) and x > 0 for x in t_list) and _median_int(t_list) == ms_v,
            code,
            f"invalid {lbl} trial_elapsed_ms median",
        )

    bw1_ms = base_w1["elapsed_ms"]
    bw8_ms = base_w8["elapsed_ms"]
    w1_ms = fw1["elapsed_ms"]
    w8_ms = fw8["elapsed_ms"]

    need(fw1.get("bit_identical_mutant_set") is True and fw8.get("bit_identical_mutant_set") is True, "EMPIRICAL_AB_PARITY", "arm parity flag false")
    need(fw1.get("failfast_injected") is True and fw8.get("failfast_injected") is True, "EMPIRICAL_AB_FAILFAST", "fast arms must inject --failfast")
    for blk, exp_workers, is_fast in ((base_w1, 1, False), (base_w8, 8, False), (fw1, 1, True), (fw8, 8, True)):
        for k in ("pass1_total", "pass1_killed", "pass2_total", "pass2_killed", "mutant_subprocess_evals", "control_subprocess_evals", "total_subprocess_evals", "workers"):
            need(_is_exact_int(blk.get(k)) and blk[k] > 0, "EMPIRICAL_AB_COUNTS", f"invalid integer count {k}")
        need(blk["workers"] == exp_workers, "EMPIRICAL_AB_WORKERS", f"expected workers={exp_workers}, got {blk['workers']}")
        need(blk["control_subprocess_evals"] == 4, "EMPIRICAL_AB_CONTROLS", f"expected control_subprocess_evals=4, got {blk['control_subprocess_evals']}")
        need(blk["total_subprocess_evals"] == blk["mutant_subprocess_evals"] + blk["control_subprocess_evals"], "EMPIRICAL_AB_COUNTS", "eval sum mismatch")
        need(blk["pass1_killed"] == blk["pass1_total"] and blk["pass2_killed"] == blk["pass2_total"], "EMPIRICAL_AB_KILLS", "arm killed != total")
        if is_fast:
            need(
                _is_exact_int(blk.get("pass2_dedup_skipped")) and blk["pass2_dedup_skipped"] == blk["pass2_total"],
                "EMPIRICAL_DEDUP_SKIP",
                "pass2 dedup did not skip identical killed sites",
            )
            need(
                blk["mutant_subprocess_evals"] == blk["pass1_total"] + blk["pass2_total"] - blk["pass2_dedup_skipped"],
                "EMPIRICAL_AB_COUNTS",
                "fast arm mutant_subprocess_evals mismatch",
            )
        else:
            need(
                blk["mutant_subprocess_evals"] == blk["pass1_total"] + blk["pass2_total"],
                "EMPIRICAL_AB_COUNTS",
                "baseline arm mutant_subprocess_evals mismatch",
            )

    need(
        base_w1["pass1_total"] == base_w8["pass1_total"] == fw1["pass1_total"] == fw8["pass1_total"]
        and base_w1["pass2_total"] == base_w8["pass2_total"] == fw1["pass2_total"] == fw8["pass2_total"],
        "EMPIRICAL_AB_KILLS",
        "cross-arm pass1/pass2 totals mismatch",
    )

    need(fw1.get("speedup_q") == str(Fraction(bw1_ms, w1_ms)), "EMPIRICAL_W1_RATIO", "w1 vs w1 speedup_q mismatch")
    need(fw1.get("speedup_milli") == (bw1_ms * 1000) // w1_ms, "EMPIRICAL_W1_MILLI", "w1 vs w1 speedup_milli mismatch")
    need(fw8.get("speedup_vs_base_w8_q") == str(Fraction(bw8_ms, w8_ms)), "EMPIRICAL_W8_ISO_RATIO", "w8 vs w8 speedup_q mismatch")
    need(fw8.get("speedup_vs_base_w8_milli") == (bw8_ms * 1000) // w8_ms, "EMPIRICAL_W8_ISO_MILLI", "w8 vs w8 speedup_milli mismatch")
    need(fw8.get("speedup_q") == str(Fraction(bw1_ms, w8_ms)), "EMPIRICAL_W8_RATIO", "w8 vs base w1 speedup_q mismatch")
    need(fw8.get("speedup_milli") == (bw1_ms * 1000) // w8_ms, "EMPIRICAL_W8_MILLI", "w8 vs base w1 speedup_milli mismatch")
    need(
        ab.get("mutant_eval_reduction_q") == str(Fraction(base_w1["mutant_subprocess_evals"], fw1["mutant_subprocess_evals"])),
        "EMPIRICAL_EVAL_RED",
        "mutant eval reduction mismatch",
    )
    need(
        ab.get("total_eval_reduction_q") == str(Fraction(base_w1["total_subprocess_evals"], fw1["total_subprocess_evals"])),
        "EMPIRICAL_EVAL_RED",
        "total eval reduction mismatch",
    )
    need(fw8["speedup_milli"] >= 3000, "EMPIRICAL_SPEEDUP_LOW", f"accelerated speedup < 3.0x: {fw8['speedup_milli']}")
    need(fw1["speedup_milli"] >= 2000, "EMPIRICAL_W1_SPEEDUP_LOW", f"iso-worker w1 vs w1 speedup < 2.0x: {fw1['speedup_milli']}")

    return {
        "ab_target_script": EXPECTED_AB_TARGET_SCRIPT,
        "ab_trials": trials,
        "baseline_w1_ms": bw1_ms,
        "baseline_w8_ms": bw8_ms,
        "bench_script_sha256": bench_sha,
        "fast_w1_ms": w1_ms,
        "fast_w8_ms": w8_ms,
        "mixed_parity_exact_100pct": True,
        "mixed_pass2_new_sites": mix["pass2_new_sites"],
        "mutant_eval_reduction_q": ab["mutant_eval_reduction_q"],
        "parity_exact_100pct": True,
        "pass1_killed": f"{fw1['pass1_killed']}/{fw1['pass1_total']}",
        "pass2_dedup_skipped": f"{fw1['pass2_dedup_skipped']}/{fw1['pass2_total']}",
        "preflight_s161_ms": s161_pf["elapsed_ms"],
        "preflight_s166_ms": s166_pf["elapsed_ms"],
        "preflight_s166_real_findings": s166_pf["finding_count"],
        "preflight_synthetic_caught": f"{sc_cnt}/{st_cnt}",
        "results_postdates_bench": True,
        "results_sha256": res_sha,
        "speedup_w1_vs_w1_milli": fw1["speedup_milli"],
        "speedup_w1_vs_w1_q": fw1["speedup_q"],
        "speedup_w8_vs_base_w1_milli": fw8["speedup_milli"],
        "speedup_w8_vs_base_w1_q": fw8["speedup_q"],
        "speedup_w8_vs_w8_milli": fw8["speedup_vs_base_w8_milli"],
        "speedup_w8_vs_w8_q": fw8["speedup_vs_base_w8_q"],
        "total_eval_reduction_q": ab["total_eval_reduction_q"],
    }


def build_certificate(
    track_dir: Path,
    *,
    live_lean: bool = False,
    runner: Callable[[Sequence[str], Path, int], tuple[int, bytes, bytes]] | None = None,
) -> dict[str, Any]:
    """Independently compute the full Track S168 certificate payload and its canonical SHA-256."""
    source_bytes = {
        fname: read_nofollow_bytes(track_dir / fname, fname)
        for fname in SOURCE_FILES_TO_PIN
    }
    source_hashes = {fname: _sha256(raw) for fname, raw in source_bytes.items()}
    tc_nonempty_loc = sum(1 for ln in source_bytes["trust_core.py"].decode("utf-8").splitlines() if ln.strip())

    lean_info = verify_lean_bundle(track_dir, live_lean=live_lean, runner=runner)
    lean_text = read_nofollow_bytes(track_dir / "VelocityBounds.lean", "VelocityBounds.lean").decode("utf-8")
    lean_c_core, lean_be_n, lean_n6_saved = _extract_lean_trust_core_witness(lean_text)
    math_info = verify_pillar1_math(
        trust_core_nonempty_loc=tc_nonempty_loc,
        expected_lean_trust_core_loc=lean_c_core,
        expected_lean_be_n=lean_be_n,
        expected_lean_n6_saved=lean_n6_saved,
    )
    emp_info = verify_empirical_ab_results(track_dir)

    body: dict[str, Any] = {
        "empirical_velocity_ab": emp_info,
        "lean_bundle": lean_info,
        "math_velocity_bounds": math_info,
        "novelty_classification": "N1",
        "oracle_class": "exact",
        "queue_id": "EXP-Q56a",
        "schema": "s168.q56a.aletheia_velocity_certificate.v2",
        "source_sha256": source_hashes,
        "track": "S168",
    }
    payload_sha = _sha256(_canon_bytes(body))
    cert = dict(body)
    cert["payload_sha256"] = payload_sha
    return cert


def verify_certificate_file(
    cert_path: Path,
    track_dir: Path,
    *,
    live_lean: bool = False,
    runner: Callable[[Sequence[str], Path, int], tuple[int, bytes, bytes]] | None = None,
) -> dict[str, Any]:
    """
    Read `cert_path` via `O_NOFOLLOW` and strictly verify against recomputed payload.
    Offline `--check` (`live_lean=False`) REJECTS any certificate claiming `live_lean_checked=true`
    or `lean_live_mode="LIVE_LEAN_4_36_0_PASS"` (`LEAN_LIVE_STATUS_MISMATCH`, `RC=2`).
    Online `--check --live-lean` (`live_lean=True`) verifies the certificate AND executes real
    isolated Lean 4.36.0 kernel replay, returning the live-verified payload.
    """
    raw = read_nofollow_bytes(cert_path, "certificate")
    loaded = parse_exact_json(raw, "certificate")
    need(type(loaded) is dict, "CERT_NOT_DICT", "certificate root must be object")

    lb = loaded.get("lean_bundle")
    need(type(lb) is dict, "CERT_MISMATCH", "certificate missing lean_bundle object")
    if not live_lean:
        need(
            lb.get("live_lean_checked") is False and lb.get("lean_live_mode") == "STATIC_ONLY",
            "LEAN_LIVE_STATUS_MISMATCH",
            "offline --check rejects certificates claiming live Lean verification; pass --live-lean",
        )
        expected_static = build_certificate(track_dir, live_lean=False)
        need(exact_json_equal(loaded, expected_static), "CERT_MISMATCH", "certificate does not match independently verified exact payload")
        need(raw == _canon_bytes(expected_static), "CERT_NON_CANONICAL", "certificate bytes are not canonical")
        return expected_static

    expected_live = build_certificate(track_dir, live_lean=True, runner=runner)
    if lb.get("live_lean_checked") is False:
        expected_static = build_certificate(track_dir, live_lean=False)
        need(exact_json_equal(loaded, expected_static), "CERT_MISMATCH", "static certificate does not match independently verified exact payload")
        need(raw == _canon_bytes(expected_static), "CERT_NON_CANONICAL", "certificate bytes are not canonical")
        return expected_live
    need(lb.get("live_lean_checked") is True, "LEAN_LIVE_STATUS_MISMATCH", "invalid live_lean_checked type")
    need(exact_json_equal(loaded, expected_live), "CERT_MISMATCH", "live certificate does not match independently verified exact payload")
    need(raw == _canon_bytes(expected_live), "CERT_NON_CANONICAL", "certificate bytes are not canonical")
    return expected_live


class _VerHelpAction(argparse.Action):
    def __init__(self, option_strings: Sequence[str], dest: str = argparse.SUPPRESS, default: Any = argparse.SUPPRESS, help: str | None = None) -> None:
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: Any, option_string: str | None = None) -> None:
        raise _HelpExit({
            "description": parser.description or "",
            "prog": parser.prog,
            "status": "HELP",
            "usage": parser.format_usage().strip(),
        })


class _StrictParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["allow_abbrev"] = False
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action=_VerHelpAction, help="Emit canonical JSON help and exit 0")

    def error(self, message: str) -> Any:
        raise VerifierError("CLI_ARG_ERROR", message)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = _StrictParser(prog="verify_s168_velocity", description="Track S168 Zero-Shared-Code Verifier", allow_abbrev=False)
        parser.add_argument("--track-dir", type=Path, default=Path(__file__).resolve().parent, help="Track directory")
        grp = parser.add_mutually_exclusive_group(required=False)
        grp.add_argument("--write", type=Path, default=None, help="Write certificate atomically with O_NOFOLLOW")
        grp.add_argument("--check", type=Path, nargs="?", const=Path("s168_velocity_certificate.json"), default=None, help="Verify certificate file")
        parser.add_argument("--live-lean", action="store_true", help="Run isolated Lean 4.36.0 kernel replay")
        parser.add_argument("--json", action="store_true", help="Emit canonical JSON certificate")
        args = parser.parse_args(argv)

        track_dir = args.track_dir
        if args.write is not None:
            cert = build_certificate(track_dir, live_lean=args.live_lean)
            raw = _canon_bytes(cert)
            atomic_write_nofollow(args.write, raw)
            sys.stdout.write(raw.decode("utf-8"))
            return 0

        cert_path = args.check if args.check is not None else (track_dir / "s168_velocity_certificate.json")
        if not cert_path.is_absolute():
            cand = track_dir / cert_path
            if cand.exists():
                cert_path = cand
        cert = verify_certificate_file(cert_path, track_dir, live_lean=args.live_lean)
        sys.stdout.write(_canon_bytes(cert).decode("utf-8"))
        return 0
    except _HelpExit as sig:
        sys.stdout.write(json.dumps(sig.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 0
    except VerifierError as exc:
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


if __name__ == "__main__":
    raise SystemExit(main())
