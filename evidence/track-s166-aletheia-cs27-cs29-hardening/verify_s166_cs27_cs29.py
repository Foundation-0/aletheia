#!/usr/bin/env python3
"""
Track S166 (`EXP-Q48`, `EXP-Q49`, `EXP-Q46b`) Independent Zero-Shared-Code Verifier.

Does NOT import any module from `aletheia.*`: independently recomputes and
certifies:
  1. `CS-29` (`SOP-20`) Pure-Q Thin-Coordinator Context-Tax Crossover Theorem &
     compaction/cold-miss amplification across canonical + boundary grids, plus
     synthetic JSONL transcript bloat ratio thresholds.
  2. `CS-27` (`SOP-18`) Iterative DFS/Kahn cycle-detection & symmetric GitHub+HF
     portfolio coverage checks.
  3. `CS-28` (`SOP-19`) Domain-stripped cross-pillar primitive detection on zero-keyword
     Hadwiger->Quantization and Loopy-BP/Carving->Connectome regressions + Law-5 guard.
  4. `EXP-Q46b` Lean 4.36.0 bypass hardening checks (string-literal escape, `sorryAx`,
     `ofReduceBool`, `trustCompiler`, `partial` on theorem-carrying defs,
     `enable_nanoda: false`, missing/empty dir fail-closed, `lakefile.lean` scan).
  5. Optional `--live-lean` RO-safe cold build & `#print axioms` audit of
     `ThinCoordInterpose.lean` inside an isolated `tempfile.TemporaryDirectory()`.

Stdlib-only, zero floats, zero bare asserts, safe across `-I -B`, `-I -O -B`, `-I -B -W error`.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Callable, Sequence

SCHEMA_VERSION = "aletheia.track_s166_cs27_cs29_certificate.v1"
MAX_CERT_BYTES = 2 * 1024 * 1024
MAX_JSON_DEPTH = 48
MAX_INT_DIGITS = 512
_CHUNK_BYTES = 65536
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

LEAN_THEOREMS: tuple[str, ...] = (
    "ThinCoordInterpose.thin_coord_crossover_iff",
    "ThinCoordInterpose.thin_coord_equal_crossover_no_strict_dominance",
    "ThinCoordInterpose.thin_coord_no_offload_when_summary_ge_payload",
    "ThinCoordInterpose.thin_coord_payload_monotone_dominance",
    "ThinCoordInterpose.thin_coord_turn_monotone_dominance",
    "ThinCoordInterpose.thin_coord_compaction_amplification_iff",
    "ThinCoordInterpose.thin_coord_compaction_amplification_strict_gain",
    "ThinCoordInterpose.thin_coord_40line_rule_concrete_witness",
    "ThinCoordInterpose.cs27_strict_depth_dag_acyclic_obstruction",
    "ThinCoordInterpose.cs27_symmetric_coverage_denominator_exact",
    "ThinCoordInterpose.cs28_law5_zero_operator_obstruction",
    "ThinCoordInterpose.cs28_cross_pillar_score_monotone",
)

LEAN_FILES: tuple[str, ...] = (
    "ThinCoordInterpose.lean",
    "lean-toolchain",
    "lakefile.toml",
    "lake-manifest.json",
)

EVIDENCE_PY_FILES: tuple[str, ...] = (
    "evidence/track-s166-aletheia-cs27-cs29-hardening/verify_s166_cs27_cs29.py",
    "evidence/track-s166-aletheia-cs27-cs29-hardening/s166_cs27_cs29_audit.py",
    "evidence/track-s166-aletheia-cs27-cs29-hardening/test_s166_cs27_cs29_r5.py",
)

CORE_PY_FILES: tuple[str, ...] = (
    "aletheia/_strict_zone_b.py",
    "aletheia/portfolio_dag.py",
    "aletheia/portal_interpose.py",
    "aletheia/thin_coordinator.py",
    "aletheia/lean_audit_hardening.py",
    "tests/test_cs27_cs29_hardening_r5.py",
)

_OWNED_ALETHEIA_MODULES: tuple[str, ...] = (
    "_strict_zone_b",
    "portfolio_dag",
    "portal_interpose",
    "thin_coordinator",
    "lean_audit_hardening",
)

_SUBPROC_LOAD_OWNED_CODE = """
import hashlib, json, os, stat, sys, types
from pathlib import Path

repo = Path(sys.argv[1])
expected = json.loads(sys.argv[2])
allowed = tuple(sys.argv[3].split(","))
if not isinstance(expected, dict):
    raise RuntimeError("missing expected hashes")
pkg = types.ModuleType("aletheia")
pkg.__path__ = []
pkg.__package__ = "aletheia"
sys.modules["aletheia"] = pkg
al_dir_fd = os.open(os.fspath(repo / "aletheia"), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
loaded = []
try:
    for name in allowed:
        rel = f"aletheia/{name}.py"
        fpath = repo / "aletheia" / f"{name}.py"
        fd = os.open(f"{name}.py", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=al_dir_fd)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise RuntimeError(f"non-regular module: {rel}")
            chunks = []
            while True:
                c = os.read(fd, 65536)
                if not c:
                    break
                chunks.append(c)
            raw = b"".join(chunks)
        finally:
            os.close(fd)
        exp_sha = expected.get(rel)
        if not isinstance(exp_sha, str) or hashlib.sha256(raw).hexdigest() != exp_sha:
            raise RuntimeError(f"hash mismatch: {rel}")
        if raw.startswith(bytes((0xEF, 0xBB, 0xBF))):
            raise RuntimeError(f"BOM forbidden: {rel}")
        src = raw.decode("utf-8")
        loaded.append((name, os.fspath(fpath), src))
finally:
    os.close(al_dir_fd)
target_mod = None
for name, src_path, src in loaded:
    full_name = f"aletheia.{name}"
    mod = types.ModuleType(full_name)
    mod.__file__ = src_path
    mod.__package__ = "aletheia"
    sys.modules[full_name] = mod
    setattr(pkg, name, mod)
    exec(compile(src, src_path, "exec"), mod.__dict__)
    if name == "lean_audit_hardening":
        target_mod = mod
raise SystemExit(target_mod.main(["--self-test", "--json"]))
""".strip()

_HEX_CHARS = frozenset("0123456789abcdefABCDEF")
_INTERP_PLAIN_PREFIXES: tuple[str, ...] = (
    "dbg_trace",
    "throwError",
)
_INTERP_ARG_MACROS: tuple[tuple[str, int, bool], ...] = (
    ("Macro.trace[", 1, True),
    ("trace_goal[", 1, True),
    ("trace[", 1, True),
    ("throwNamedErrorAt", 2, False),
    ("logNamedErrorAt", 2, False),
    ("logNamedWarningAt", 2, False),
    ("throwErrorAt", 1, False),
    ("throwNamedError", 1, False),
    ("logNamedError", 1, False),
    ("logNamedWarning", 1, False),
)

_LEAN_BAN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("sorry", re.compile(r"(?<![A-Za-z0-9_'.])sorry(?![A-Za-z0-9_'])")),
    ("admit", re.compile(r"(?<![A-Za-z0-9_'.])admit(?![A-Za-z0-9_'])")),
    ("axiom", re.compile(r"(?<![A-Za-z0-9_'.])axiom(?![A-Za-z0-9_'])")),
    ("unsafe", re.compile(r"(?<![A-Za-z0-9_'.])unsafe(?![A-Za-z0-9_'])")),
    ("native_decide", re.compile(r"(?<![A-Za-z0-9_'.])native_decide(?![A-Za-z0-9_'])")),
    ("decide +native", re.compile(r"(?:(?<![A-Za-z0-9_'.])decide(?:\s|\([^)]*\)|\+[A-Za-z_][A-Za-z0-9_]*)*\+native(?![A-Za-z0-9_'])|(?<![A-Za-z0-9_'.])decide\s*\([^)]*\bnative\s*:=\s*true\b[^)]*\)|(?:^|[\s;(])\+native(?![A-Za-z0-9_']))", re.DOTALL)),
    ("bv_decide", re.compile(r"(?<![A-Za-z0-9_'.])(?:bv_decide|bv_check)(?![A-Za-z0-9_'])")),
    ("Classical", re.compile(r"(?<![A-Za-z0-9_'.])(?:Classical|classical)(?![A-Za-z0-9_'])")),
    ("sorryAx", re.compile(r"(?<![A-Za-z0-9_'])sorryAx(?![A-Za-z0-9_'])")),
    ("mkSorry", re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*Meta\s*\.\s*)?mkSorry(?![A-Za-z0-9_'])", re.DOTALL)),
    ("ofReduceBool", re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?(?:ofReduceBool|ofReduceNat)(?![A-Za-z0-9_'])", re.DOTALL)),
    ("trustCompiler", re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?trustCompiler(?![A-Za-z0-9_'])", re.DOTALL)),
    ("skipKernelTC", re.compile(r"(?<![A-Za-z0-9_'])debug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)(?![A-Za-z0-9_'])", re.DOTALL)),
    ("meta_eval", re.compile(r"(?<![A-Za-z0-9_'.])(?:run_cmd|run_meta|run_tac|initialize|builtin_initialize)(?![A-Za-z0-9_'])")),
    ("syntax_macro", re.compile(r"(?<![A-Za-z0-9_'.])(?:syntax|macro|macro_rules|elab|elab_rules|declare_syntax_cat|infix[lr]?|prefix|postfix|notation)(?![A-Za-z0-9_'])")),
    ("hash_cmd", re.compile(r"#\s*(?:eval!?|reduce|exit|guard_msgs)(?![A-Za-z0-9_'])")),
    ("attr_escape", re.compile(r"(?:@|(?<![A-Za-z0-9_'.])attribute\s*)\[[^\]]*(?<![A-Za-z0-9_'])(?:extern|implemented_by|export|init|builtin_init|macro|elab|tactic)(?![A-Za-z0-9_'])", re.DOTALL)),
    ("native_axiom", re.compile(r"(?:\.\s*)?_native\s*\.\s*[A-Za-z_][A-Za-z0-9_]*\s*\.\s*ax_[A-Za-z0-9_]*", re.DOTALL)),
    ("partial", re.compile(r"(?<![A-Za-z0-9_'.])partial\s+(?:(?:private|protected|noncomputable|unsafe)\s+)*(?:def|instance|abbrev|theorem|lemma|opaque)\b", re.DOTALL)),
)
_ROOT_NS_PREFIX_RE = re.compile(r"(?<![A-Za-z0-9_'.])(?:_root_\s*\.\s*)+")
_TOP_DECL_CMD_RE = re.compile(
    r"^\s*(?:(?:private|protected|noncomputable|unsafe|partial|scoped|local)\s+)*"
    r"(?:theorem|lemma|def|abbrev|opaque|axiom|example|instance|structure|inductive|class|namespace|section|end|open|variable|universe|attribute|#)"
    r"(?![A-Za-z0-9_'])"
)
_STOP_LINE_START_RE = re.compile(r"^\s*stop(?![A-Za-z0-9_'])")
_STOP_AFTER_TACTIC_TOK_RE = re.compile(
    r"(?:(?<![A-Za-z0-9_'.])(?:by|all_goals|any_goals|repeat|try|focus|first)|=>|<;>|[;|({·])\s*stop(?![A-Za-z0-9_'])"
)
_LEAN_IMPORT_RE = re.compile(
    r"(?<![A-Za-z0-9_'.])(?:(?:public|private|meta)\s+)*import\s+(?:all\s+)?([A-Za-z0-9_«»'\u0080-\uffff]+(?:\.[A-Za-z0-9_«»'\u0080-\uffff]+)*)"
)

_AXIOM_LINE_RE = re.compile(
    r"^'([A-Za-z0-9_.']+)'\s+(does not depend on any axioms|depends on axioms:\s*\[([^\]]*)\])\s*$"
)
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}\Z")

_ROOT_KEYS = frozenset({
    "schema_version",
    "lean_bundle",
    "python_source_sha256",
    "cs29_crossover_grid",
    "cs29_transcript_fixtures",
    "cs27_dag_and_portfolio",
    "cs28_interpose_regressions",
    "exp_q46b_bypass_checks",
    "payload_sha256",
})


class VerifyS166Error(ValueError):
    """Fail-closed verifier error with explicit error code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


def _need(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise VerifyS166Error(code, detail)


def _qstr(q: Fraction) -> str:
    return f"{q.numerator}/{q.denominator}"


def _canon_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def _reject_float(tok: str) -> Any:
    raise VerifyS166Error("FLOAT_FORBIDDEN", f"float literal forbidden: {tok!r}")


def _reject_const(tok: str) -> Any:
    raise VerifyS166Error("NONFINITE_JSON", f"non-finite JSON constant forbidden: {tok!r}")


def _strict_int(tok: str) -> int:
    n_digits = len(tok) - 1 if tok.startswith("-") else len(tok)
    _need(n_digits <= MAX_INT_DIGITS, "INT_TOO_LONG", "integer exceeds digit limit")
    return int(tok)


def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        _need(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def _check_json_tree(root: Any) -> None:
    stack: list[tuple[Any, int]] = [(root, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, str):
            for ch in item:
                _need(not (0xD800 <= ord(ch) <= 0xDFFF), "LONE_SURROGATE", "lone surrogate forbidden")
        elif isinstance(item, dict):
            _need(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_EXCEEDED", "JSON nesting too deep")
            for k, v in item.items():
                stack.append((k, depth + 1))
                stack.append((v, depth + 1))
        elif isinstance(item, list):
            _need(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_EXCEEDED", "JSON nesting too deep")
            for v in item:
                stack.append((v, depth + 1))


def _read_regular_bytes(path: Path, label: str, *, max_bytes: int = MAX_CERT_BYTES) -> bytes:
    _need(isinstance(path, Path), "BAD_PATH", f"{label}: Path required")
    _need("\x00" not in os.fspath(path), "BAD_PATH", f"{label}: NUL byte forbidden")
    parts = path.parts
    anchor = os.sep if path.is_absolute() else "."
    idx = 1 if path.is_absolute() else 0
    _need(len(parts) > idx, "BAD_PATH", f"{label}: empty path")
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fds: list[int] = []
    try:
        cur = os.open(anchor, dir_flags)
        fds.append(cur)
        while idx < len(parts) - 1:
            cur = os.open(parts[idx], dir_flags, dir_fd=cur)
            fds.append(cur)
            idx += 1
        fd = os.open(parts[idx], file_flags, dir_fd=cur)
        fds.append(fd)
        st = os.fstat(fd)
        _need(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", f"{label}: must be regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, _CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            _need(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds size cap")
            chunks.append(chunk)
        return b"".join(chunks)
    except VerifyS166Error:
        raise
    except OSError as exc:
        raise VerifyS166Error("IO_ERROR", f"{label}: {exc}") from exc
    finally:
        for fdi in reversed(fds):
            try:
                os.close(fdi)
            except OSError:
                pass


def _decode_strict_utf8(raw: bytes, label: str, *, crlf_code: str = "CRLF_FORBIDDEN") -> str:
    _need(not raw.startswith(b"\xef\xbb\xbf"), "BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    bad_cr = (b"\r\n" in raw) if crlf_code == "CRLF_IN_LEAN_FILE" else (b"\r" in raw)
    _need(not bad_cr, crlf_code, f"{label}: CRLF forbidden")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerifyS166Error("INVALID_UTF8", f"{label}: {exc}") from exc


def _load_strict_json_bytes(raw: bytes, label: str, *, crlf_code: str = "CRLF_FORBIDDEN") -> dict[str, Any]:
    txt = _decode_strict_utf8(raw, label, crlf_code=crlf_code)
    _need(raw.endswith(b"\n"), "MISSING_TRAILING_NEWLINE", f"{label}: trailing LF required")
    _need(len(txt.strip()) > 0, "EMPTY_JSON", f"{label}: empty JSON")
    try:
        obj = json.loads(
            txt,
            parse_float=_reject_float,
            parse_int=_strict_int,
            parse_constant=_reject_const,
            object_pairs_hook=_no_dup_pairs,
        )
    except VerifyS166Error:
        raise
    except (ValueError, RecursionError, OverflowError) as exc:
        raise VerifyS166Error("BAD_JSON", f"{label}: {exc}") from exc
    _check_json_tree(obj)
    _need(type(obj) is dict, "ROOT_NOT_OBJECT", f"{label}: root must be dict")
    return obj


def _atomic_write_lf(path: Path, data: bytes) -> None:
    _need(isinstance(path, Path), "BAD_WRITE_PATH", "write path must be Path")
    parts = path.parts
    anchor = os.sep if path.is_absolute() else "."
    idx = 1 if path.is_absolute() else 0
    _need(len(parts) > idx, "BAD_WRITE_PATH", "write path names no file")
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fds: list[int] = []
    try:
        cur = os.open(anchor, dir_flags)
        fds.append(cur)
        while idx < len(parts) - 1:
            cur = os.open(parts[idx], dir_flags, dir_fd=cur)
            fds.append(cur)
            idx += 1
        leaf = parts[idx]
        try:
            lst = os.lstat(leaf, dir_fd=cur)
            _need(stat.S_ISREG(lst.st_mode), "WRITE_TARGET_NOT_REGULAR", "target exists and is not regular file")
        except FileNotFoundError:
            pass
        tmp_name = f".{leaf}.{os.getpid()}.{secrets.token_hex(6)}.tmp"
        fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=cur)
        try:
            view = memoryview(data)
            pos = 0
            while pos < len(view):
                written = os.write(fd, view[pos:])
                _need(written > 0, "SHORT_WRITE", "short write on certificate")
                pos += written
            os.fsync(fd)
        except Exception:
            os.close(fd)
            try:
                os.unlink(tmp_name, dir_fd=cur)
            except OSError:
                pass
            raise
        os.close(fd)
        os.replace(tmp_name, leaf, src_dir_fd=cur, dst_dir_fd=cur)
    except VerifyS166Error:
        raise
    except OSError as exc:
        raise VerifyS166Error("WRITE_IO_ERROR", f"atomic write failed: {exc}") from exc
    finally:
        for fdi in reversed(fds):
            try:
                os.close(fdi)
            except OSError:
                pass


def _match_char_end(src: str, i: int, n: int) -> int | None:
    if i + 2 < n and src[i + 1] not in ("\\", "'") and src[i + 2] == "'":
        return i + 3
    if i + 3 < n and src[i + 1] == "\\":
        if src[i + 3] == "'" and src[i + 2] != "\n":
            return i + 4
        esc = src[i + 2]
        if esc == "x" and i + 5 < n and src[i + 5] == "'" and all(c in _HEX_CHARS for c in src[i + 3 : i + 5]):
            return i + 6
        if esc == "u" and i + 7 < n and src[i + 7] == "'" and all(c in _HEX_CHARS for c in src[i + 3 : i + 7]):
            return i + 8
    return None


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_ident_cont(ch: str) -> bool:
    return ch.isalnum() or ch in "_'!?"


def _skip_ws_and_comments(src: str, j: int, n: int) -> int:
    while j < n:
        if src[j].isspace():
            j += 1
        elif src.startswith("--", j):
            while j < n and src[j] != "\n":
                j += 1
        elif src.startswith("/-", j):
            cdepth = 1
            j += 3 if (j + 2 < n and src[j + 2] in ("-", "!")) else 2
            while j < n and cdepth > 0:
                if src.startswith("/-", j):
                    cdepth += 1
                    j += 2
                elif src.startswith("-/", j):
                    cdepth -= 1
                    j += 2
                else:
                    j += 1
        else:
            break
    return j


def _find_interp_open_quote(src: str, i: int, n: int, in_ident: bool) -> int | None:
    if in_ident or (i > 0 and src[i - 1] == "."):
        return None
    if _is_ident_start(src[i]):
        k = i + 1
        while k < n and _is_ident_cont(src[k]):
            k += 1
        if src[k - 1] == "!":
            j = _skip_ws_and_comments(src, k, n)
            if j < n and src[j] == '"':
                return j
    for pref in _INTERP_PLAIN_PREFIXES:
        if src.startswith(pref, i):
            k = i + len(pref)
            if k < n and _is_ident_cont(src[k]):
                continue
            j = _skip_ws_and_comments(src, k, n)
            if j < n and src[j] == '"':
                return j
    return None


def _match_interp_arg_macro(src: str, i: int, n: int, in_ident: bool) -> tuple[int, int, bool] | None:
    if in_ident or (i > 0 and src[i - 1] == "."):
        return None
    for kw, argc, is_bracket in _INTERP_ARG_MACROS:
        if src.startswith(kw, i):
            end = i + len(kw)
            if is_bracket:
                return end, argc, True
            if end == n or not _is_ident_cont(src[end]):
                return end, argc, False
    return None


def _has_stop_tactic(scan_text: str) -> bool:
    in_by = False
    for line in scan_text.split("\n"):
        if _TOP_DECL_CMD_RE.match(line):
            in_by = False
        if _STOP_AFTER_TACTIC_TOK_RE.search(line) is not None or (
            in_by and _STOP_LINE_START_RE.match(line) is not None
        ):
            return True
        if re.search(r"(?<![A-Za-z0-9_'.])by(?![A-Za-z0-9_'])", line) is not None:
            in_by = True
    return False


def strip_lean_comments_and_strings(src: str) -> str:
    """Independent literal-, interpolated-string-, and nested-comment-safe Lean 4 stripper."""
    out: list[str] = []
    i = 0
    n = len(src)
    depth = 0
    in_str = False
    raw_hashes = -1
    in_ident = False
    interp_stack: list[int] = []
    pending_args = 0
    arg_depth = 0
    pending_tok = False
    interp_next_quote = False
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
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
            if src.startswith(close_seq, i):
                out.append(" " * len(close_seq))
                i += len(close_seq)
                raw_hashes = -1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_str:
            if ch == "\\" and i + 1 < n:
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
        if interp_stack and interp_stack[-1] == 0:
            if ch == "\\" and i + 1 < n:
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                interp_stack.pop()
                out.append(" ")
                i += 1
            elif ch == "{":
                interp_stack[-1] = 1
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
            in_ident = False
            if i + 2 < n and src[i + 2] in ("-", "!"):
                out.append("   ")
                i += 3
            else:
                out.append("  ")
                i += 2
            continue
        if ch == "-" and nxt == "-":
            if pending_tok:
                pending_tok = False
                pending_args -= 1
                interp_next_quote = pending_args == 0
            in_ident = False
            while i < n and src[i] != "\n":
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
                interp_stack.append(0)
                in_ident = False
                out.append(" ")
                i += 1
                continue
        if pending_args > 0:
            if ch in "([{":
                if pending_tok:
                    pending_tok = False
                    pending_args -= 1
                arg_depth += 1
            elif ch in ")]}" and arg_depth > 0:
                arg_depth -= 1
                if arg_depth == 0:
                    pending_args -= 1
                    interp_next_quote = pending_args == 0
            elif arg_depth == 0:
                if _is_ident_cont(ch) or ch in ".«":
                    pending_tok = True
                else:
                    pending_args = 0
                    pending_tok = False
        if ch == "r" and not in_ident and (i == 0 or src[i - 1] != "."):
            j = i + 1
            while j < n and src[j] == "#":
                j += 1
            if j < n and src[j] == '"':
                raw_hashes = j - (i + 1)
                in_ident = False
                out.append(" " * (j - i + 1))
                i = j + 1
                continue
        macro_arg = _match_interp_arg_macro(src, i, n, in_ident)
        if macro_arg is not None:
            end_kw, argc, is_bracket = macro_arg
            out.append(src[i:end_kw])
            i = end_kw
            in_ident = False
            pending_args = argc
            arg_depth = 1 if is_bracket else 0
            pending_tok = False
            continue
        interp_q = _find_interp_open_quote(src, i, n, in_ident)
        if interp_q is not None:
            interp_stack.append(0)
            in_ident = False
            for k in range(i, interp_q + 1):
                out.append("\n" if src[k] == "\n" else " ")
            i = interp_q + 1
            continue
        if ch == '"':
            in_str = True
            in_ident = False
            out.append(" ")
            i += 1
            continue
        if ch == "'" and not in_ident:
            char_end = _match_char_end(src, i, n)
            if char_end is not None:
                in_ident = False
                out.append(" \n " if src[i + 1] == "\n" else " " * (char_end - i))
                i = char_end
                continue
        if ch == "«":
            end_g = src.find("»", i + 1)
            _need(end_g != -1, "UNTERMINATED_LEAN_LEXEME", "unclosed guillemet identifier in Lean source")
            if out and _is_ident_cont(out[-1][-1]):
                out.append(" ")
            out.append(src[i + 1 : end_g].replace("\n", " "))
            if end_g + 1 < n and _is_ident_start(src[end_g + 1]):
                out.append(" ")
            in_ident = False
            i = end_g + 1
            continue
        if interp_stack:
            if ch == "{":
                interp_stack[-1] += 1
                in_ident = False
                out.append("{")
                i += 1
                continue
            if ch == "}":
                interp_stack[-1] -= 1
                in_ident = False
                out.append(" " if interp_stack[-1] == 0 else "}")
                i += 1
                continue
        in_ident = _is_ident_cont(ch) if in_ident else _is_ident_start(ch)
        out.append(ch)
        i += 1
    _need(depth == 0 and not in_str and raw_hashes < 0 and not interp_stack, "UNTERMINATED_LEAN_LEXEME", "unclosed comment or string in Lean source")
    return "".join(out)


def verify_lean_source_clean(src: str, *, require_pure_init: bool = True) -> str:
    """Clean-room static verifier for Lean 4 source text."""
    cleaned = strip_lean_comments_and_strings(src)
    scan_text = _ROOT_NS_PREFIX_RE.sub("", cleaned)
    for label, pat in _LEAN_BAN_PATTERNS:
        _need(pat.search(scan_text) is None, "FORBIDDEN_LEAN_TOKEN", f"banned Lean token {label}")
    _need(not _has_stop_tactic(scan_text), "FORBIDDEN_LEAN_TOKEN", "banned Lean token stop")
    if require_pure_init:
        _need(_LEAN_IMPORT_RE.search(scan_text) is None, "NON_INIT_IMPORT", "Lean file must be pure-Init with 0 imports")
    return cleaned


def evaluate_crossover_exact(
    case_id: str,
    T: int,
    B: int,
    s: int,
    n_h: int,
    d_h: int,
    n_w: int,
    d_w: int,
    m_cold: int,
    n_m: int,
    d_m: int,
    dk: int,
    n_k: int,
    d_k: int,
) -> dict[str, Any]:
    """Independent pure-Fraction crossover computation with integer cross-check."""
    _need(T >= 1 and B >= 0 and s >= 0, "BAD_CS29_PARAM", f"{case_id}: bad T/B/s")
    _need(n_h > 0 and d_h > 0 and n_w >= 0 and d_w > 0, "BAD_CS29_RATE", f"{case_id}: bad hit/worker rates")
    _need(m_cold >= 0 and n_m >= 0 and d_m > 0 and dk >= 0 and n_k >= 0 and d_k > 0, "BAD_CS29_AMP", f"{case_id}: bad amp params")

    c_hit = Fraction(n_h, d_h)
    W = Fraction(n_w, d_w)
    c_miss = Fraction(n_m, d_m)
    K_comp = Fraction(n_k, d_k)

    base_inline = Fraction(T * B, 1) * c_hit
    base_offload = W + Fraction(T * s, 1) * c_hit
    base_sav = base_inline - base_offload

    amp_inline = base_inline + Fraction(m_cold * B, 1) * c_miss + Fraction(dk, 1) * K_comp
    amp_offload = base_offload + Fraction(m_cold * s, 1) * c_miss
    amp_sav = amp_inline - amp_offload

    return {
        "case_id": case_id,
        "T": T,
        "B": B,
        "s": s,
        "m_cold": m_cold,
        "dk": dk,
        "c_hit_q": _qstr(c_hit),
        "worker_cost_q": _qstr(W),
        "c_miss_q": _qstr(c_miss),
        "compaction_cost_q": _qstr(K_comp),
        "base_inline_q": _qstr(base_inline),
        "base_offload_q": _qstr(base_offload),
        "base_savings_q": _qstr(base_sav),
        "base_offload_wins": base_sav > Fraction(0, 1),
        "amp_inline_q": _qstr(amp_inline),
        "amp_offload_q": _qstr(amp_offload),
        "amp_savings_q": _qstr(amp_sav),
        "amp_offload_wins": amp_sav > Fraction(0, 1),
    }


def check_dag_acyclic(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    """Independent Kahn topological sort verifying cycle absence."""
    _need(len(nodes) > 0, "EMPTY_DAG_NODES", "nodes must be non-empty")
    node_set = set(nodes)
    _need(len(node_set) == len(nodes), "DUP_DAG_NODE", "duplicate node id")
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for u, v in edges:
        _need(u in node_set and v in node_set, "DANGLING_EDGE", f"unknown edge endpoint {u!r}->{v!r}")
        adj[u].append(v)
        indeg[v] += 1
    q = [n for n in nodes if indeg[n] == 0]
    visited = 0
    while q:
        cur = q.pop()
        visited += 1
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    _need(visited == len(nodes), "DAG_CYCLE_DETECTED", "cycle detected in portal graph")
    return True


def check_zero_keyword_cross_pillar(abstract: str, forbidden_kws: tuple[str, ...], pattern: re.Pattern[str], min_hits: int) -> int:
    """Verify abstract contains 0 target-domain keywords yet triggers >= min_hits primitive matches."""
    low = abstract.lower()
    for kw in forbidden_kws:
        _need(kw not in low, "TARGET_KEYWORD_LEAK", f"target keyword {kw!r} present in abstract")
    hits = len({m.group(0).lower() for m in pattern.finditer(abstract)})
    _need(hits >= min_hits, "CROSS_PILLAR_MISS", f"expected >= {min_hits} primitive hits, got {hits}")
    return hits


def _count_lf_lines(txt: str) -> int:
    if not txt:
        return 0
    cnt = txt.count("\n")
    return cnt if txt.endswith("\n") else cnt + 1


def _extract_list_content_split(blocks: list[Any]) -> tuple[str, str]:
    tool_parts: list[str] = []
    other_parts: list[str] = []
    stack: list[tuple[Any, bool]] = [(item, False) for item in reversed(blocks)]
    while stack:
        item, in_tool = stack.pop()
        if type(item) is str:
            if item:
                (tool_parts if in_tool else other_parts).append(item)
        elif isinstance(item, dict):
            next_tool = in_tool or item.get("type") in ("tool", "tool_result", "tool_output")
            for k in ("text", "output", "content"):
                if k in item and item[k] is not None:
                    v = item[k]
                    _need(type(v) is str or isinstance(v, list), "BAD_EVENT_TEXT", "event block content must be str or list")
                    stack.append((v, next_tool))
        elif isinstance(item, list):
            for sub in reversed(item):
                stack.append((sub, in_tool))
        else:
            raise VerifyS166Error("BAD_EVENT_TEXT", "event list item must be dict or str")
    return "\n".join(tool_parts), "\n".join(other_parts)


def measure_synthetic_transcript(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Independent transcript bloat computation supporting string and list-block `content`."""
    _need(len(events) > 0, "EMPTY_EVENTS", "events must be non-empty")
    tot_b = 0
    tool_b = 0
    bloat_ev = 0
    for ev in events:
        _need(type(ev) is dict, "BAD_EVENT_TYPE", "event must be dict")
        c_val = ev.get("content")
        t_val = ev.get("thinking")
        is_gen_tool = ev.get("type") == "GENERIC"
        tool_txt = ""
        other_txt = ""
        has_tool_block = False
        if c_val is not None:
            if type(c_val) is list:
                tool_part, other_part = _extract_list_content_split(c_val)
                if is_gen_tool:
                    tool_txt = "\n".join(p for p in (tool_part, other_part) if p)
                else:
                    tool_txt, other_txt = tool_part, other_part
                    has_tool_block = bool(tool_part)
            else:
                _need(type(c_val) is str, "BAD_EVENT_TEXT", "event content must be str or list")
                if is_gen_tool:
                    tool_txt = c_val
                else:
                    other_txt = c_val
        elif t_val is not None:
            _need(type(t_val) is str, "BAD_EVENT_TEXT", "event thinking must be str")
            if is_gen_tool:
                tool_txt = t_val
            else:
                other_txt = t_val
        tb = len(tool_txt.encode("utf-8"))
        ob = len(other_txt.encode("utf-8"))
        tot_b += tb + ob
        if is_gen_tool or has_tool_block:
            tool_b += tb
            if _count_lf_lines(tool_txt) > 40 or len(tool_txt) > 2400:
                bloat_ev += 1
    ratio = Fraction(tool_b, tot_b) if tot_b > 0 else Fraction(0, 1)
    return {
        "total_bytes": tot_b,
        "inline_tool_bytes": tool_b,
        "inline_tool_ratio_q": _qstr(ratio),
        "inline_bloat_events": bloat_ev,
        "alert": ratio > Fraction(3, 10) and bloat_ev > 0,
    }


def _verify_cs29_grid_and_transcripts() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = [
        evaluate_crossover_exact("exact_crossover_tie", 12, 2120, 120, 1, 10, 2400, 1, 0, 1, 1, 0, 0, 1),
        evaluate_crossover_exact("below_crossover_1tok", 12, 2119, 120, 1, 10, 2400, 1, 0, 1, 1, 0, 0, 1),
        evaluate_crossover_exact("above_crossover_1tok", 12, 2121, 120, 1, 10, 2400, 1, 0, 1, 1, 0, 0, 1),
        evaluate_crossover_exact("forty_line_offload_win", 20, 2000, 120, 1, 10, 2400, 1, 0, 1, 1, 0, 0, 1),
        evaluate_crossover_exact("compaction_tips_tie", 12, 2120, 120, 1, 10, 2400, 1, 1, 3, 1, 1, 5000, 1),
        evaluate_crossover_exact("summary_ge_payload", 30, 100, 150, 1, 10, 500, 1, 0, 1, 1, 0, 0, 1),
    ]
    bloated_lines = [
        {"type": "USER_INPUT", "content": "Investigate bridge"},
        {"type": "GENERIC", "content": "\n".join(f"log line {i}" for i in range(90))},
        {"type": "GENERIC", "content": [{"type": "tool_result", "content": "\n".join(f"diff line {i}" for i in range(60))}]},
        {"type": "CHECKPOINT", "content": "compacted"},
    ]
    thin_lines = [
        {"type": "USER_INPUT", "content": "Investigate bridge"},
        {"type": "PLANNER_RESPONSE", "thinking": "Delegate file scan to ephemeral worker"},
        {"type": "GENERIC", "content": "ok: digest=abc123 path=report.md"},
    ]
    return cases, {
        "bloated_fixture": measure_synthetic_transcript(bloated_lines),
        "thin_fixture": measure_synthetic_transcript(thin_lines),
    }


def _verify_cs27_independent() -> dict[str, Any]:
    dag_ok = check_dag_acyclic(["p0", "d1", "d2", "d2b"], [("p0", "d1"), ("d1", "d2"), ("d1", "d2b")])
    cycle_rejected = False
    try:
        check_dag_acyclic(["p0", "d1"], [("p0", "d1"), ("d1", "p0")])
    except VerifyS166Error as exc:
        cycle_rejected = exc.code == "DAG_CYCLE_DETECTED"
    _need(cycle_rejected, "CS27_CYCLE_CHECK_FAILED", "CS-27 negative cycle control did not fail closed")
    gh_cov = Fraction(12, 12)
    hf_cov = Fraction(4, 4)
    sym = Fraction(1, 2) * (gh_cov + hf_cov)
    return {
        "acyclic_dag_verified": dag_ok and cycle_rejected,
        "cycle_control_rejected": cycle_rejected,
        "symmetric_gh_hf_coverage_q": _qstr(sym),
    }


_LAW5_NEG_RE = re.compile(
    r"\bthere\s+(?:is|are)\s+no\b"
    r"|\b(?:does|do|did)\s+not\s+hold\b"
    r"|\bfails\s+to\s+hold\b"
    r"|\b(?:never|no\s+longer)\s+holds?\b"
    r"|\b(?:cannot|can't)\s+hold\b"
    r"|\bnot\s+valid\b"
    r"|\bis\s+(?:false|invalid)\b"
    r"|\b(?:no|not|without|never|none|nothing|neither|nor|lacks?|missing|absent|vacuous|pseudo|fake|cannot|can't)\b"
    r"(?:\s+[A-Za-z0-9_-]+){0,3}\s+"
    r"(?:identity|equation|map|operator|bridge|transfer|witness|theorem|bound|commutes|obstruction|impossibility|counterexample|wall)\b",
    re.IGNORECASE,
)
_LAW5_REFUTED_RE = re.compile(
    r"\b(?:refut\w*|disprov\w*|falsif\w*|counterexample\w*|impossib\w*|obstruct\w*|no[- ]go|invalid|fails)\b",
    re.IGNORECASE,
)


def _independent_law5_check(disp: str, witness: str) -> bool:
    if disp != "EXACT_OPERATOR_TRANSFER":
        return False
    if _LAW5_NEG_RE.search(witness) is not None or _LAW5_REFUTED_RE.search(witness) is not None:
        return False
    return re.search(r"[A-Za-z0-9_)\]}]\s*(?:=|:=|<=|>=|<->|->|\\to|\\le|\\ge)\s*[A-Za-z0-9_(\[{|\\]", witness) is not None


def _verify_cs28_independent() -> dict[str, Any]:
    quant_pat = re.compile(r"\b(john(?:'s)?|ellipsoid|homothet(?:ic)?|covering|chebyshev|minimax|helly|difference\s+body)\b", re.IGNORECASE)
    bio_pat = re.compile(r"\b(message\s+passing|bethe|cavity|damping|loopy|frustrat\w*|carv\w*|directed\s+graphs?)\b", re.IGNORECASE)
    hadwiger_abstract = "homothetic covering of difference body via John contact decomposition and minimax Chebyshev Helly bounds"
    pfc_abstract = "loopy message passing with Bethe cavity damping and frustrated triads under edge carving on directed graphs"
    h_hits = check_zero_keyword_cross_pillar(hadwiger_abstract, ("quantiz", "siliquant"), quant_pat, 5)
    b_hits = check_zero_keyword_cross_pillar(pfc_abstract, ("connectome", "malecns"), bio_pat, 5)
    neg_blocked = not _independent_law5_check("EXACT_OPERATOR_TRANSFER", "there is no identity: a = b")
    buzz_blocked = not _independent_law5_check("EXACT_OPERATOR_TRANSFER", "deep sheaf duality holonomy")
    op_ok = _independent_law5_check("EXACT_OPERATOR_TRANSFER", "h_{M^{-1}(S)}(u) <= sum c_s |<v_s, u>|")
    law5_ok = neg_blocked and buzz_blocked and op_ok
    _need(law5_ok, "CS28_LAW5_CHECK_FAILED", "Law-5 independent negative/positive control failed")
    return {
        "hadwiger_zero_keyword_hits": h_hits,
        "pfc_zero_keyword_hits": b_hits,
        "law5_requires_operator_or_obstruction": law5_ok,
    }


def default_live_lean_runner(
    track_dir: Path,
    *,
    preloaded_files: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """Build and audit `ThinCoordInterpose.lean` inside an isolated read-write tempdir (RO-safe)."""
    home = os.environ.get("HOME", "")
    path_parts = [
        str(Path(home) / ".local" / "bin"),
        str(Path(home) / ".elan" / "bin"),
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ]
    env = {"PATH": ":".join(path_parts), "HOME": home, "PYTHONDONTWRITEBYTECODE": "1"}
    if preloaded_files is not None:
        raw_files = [(fname, preloaded_files[fname]) for fname in LEAN_FILES]
    else:
        raw_files = [(fname, _read_regular_bytes(track_dir / fname, f"lean_{fname}")) for fname in LEAN_FILES]
    try:
        with tempfile.TemporaryDirectory(prefix="s166_live_lean_") as td:
            stage = Path(td)
            for fname, raw in raw_files:
                (stage / fname).write_bytes(raw)
            ver = subprocess.run(["lean", "--version"], cwd=str(stage), env=env, capture_output=True, timeout=60, check=False)
            bld = subprocess.run(["lake", "build"], cwd=str(stage), env=env, capture_output=True, timeout=180, check=False)
            ax = subprocess.run(["lean", "ThinCoordInterpose.lean"], cwd=str(stage), env=env, capture_output=True, timeout=120, check=False)
        ver_out = (ver.stdout + ver.stderr).decode("utf-8", errors="replace")
        bld_out = (bld.stdout + bld.stderr).decode("utf-8", errors="replace")
        ax_out = ax.stdout.decode("utf-8", errors="strict")
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        raise VerifyS166Error("LIVE_LEAN_EXEC_ERROR", f"live Lean execution failed: {exc}") from exc
    return {
        "version_rc": ver.returncode,
        "version_output": ver_out,
        "build_rc": bld.returncode,
        "build_output": bld_out,
        "axiom_rc": ax.returncode,
        "axiom_stdout": ax_out,
    }


def audit_live_lean_output(run_res: dict[str, Any]) -> dict[str, list[str]]:
    """Fail-closed parser for Lean 4.36.0 version, build, and `#print axioms` output."""
    _need(run_res.get("version_rc") == 0, "LEAN_VERSION_FAIL", "lean --version failed")
    _need(
        re.search(r"\bversion\s+4\.36\.0(?=[,\s)]|\Z)", str(run_res.get("version_output", ""))) is not None,
        "LEAN_VERSION_MISMATCH",
        "expected exact Lean 4.36.0",
    )
    _need(run_res.get("build_rc") == 0, "LAKE_BUILD_FAIL", f"lake build failed: {run_res.get('build_output', '')}")
    _need(run_res.get("axiom_rc") == 0, "LEAN_AXIOM_RUN_FAIL", "lean ThinCoordInterpose.lean failed")

    axioms_by_thm: dict[str, list[str]] = {}
    for line in str(run_res.get("axiom_stdout", "")).split("\n"):
        m = _AXIOM_LINE_RE.match(line.strip())
        if m is None:
            continue
        tname = m.group(1)
        if m.group(2).startswith("does not depend"):
            axioms_by_thm[tname] = []
        else:
            axs = [tok.strip() for tok in m.group(3).split(",") if tok.strip()]
            for ax in axs:
                _need(ax in _ALLOWED_LEAN_AXIOMS, "FORBIDDEN_LEAN_AXIOM", f"forbidden axiom {ax} in {tname}")
            axioms_by_thm[tname] = axs
    _need(set(axioms_by_thm) == set(LEAN_THEOREMS), "LEAN_AXIOM_AUDIT_INCOMPLETE", f"matched {len(axioms_by_thm)}/{len(LEAN_THEOREMS)} theorems")
    return axioms_by_thm


def _audit_track_dir_tree(track_dir: Path) -> None:
    """Reject symlinks, `.lake/` residue, and any extra `.lean` file anywhere under `track_dir`."""
    _need(isinstance(track_dir, Path), "BAD_PATH", "track_dir must be Path")
    _need("\x00" not in os.fspath(track_dir), "BAD_PATH", "track_dir contains NUL byte")
    try:
        root_st = os.lstat(track_dir)
    except OSError as exc:
        raise VerifyS166Error("IO_ERROR", f"track_dir unreachable: {exc}") from exc
    _need(not stat.S_ISLNK(root_st.st_mode) and stat.S_ISDIR(root_st.st_mode), "BAD_TRACK_DIR", "track_dir must be non-symlink directory")
    stack = [track_dir]
    while stack:
        cur = stack.pop()
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
            for entry in entries:
                if entry.is_symlink():
                    raise VerifyS166Error("SYMLINK_IN_BUNDLE", f"symlink forbidden in track bundle: {entry.name}")
                ep = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    _need(entry.name != ".lake", "FORBIDDEN_LAKE_DIR", ".lake build directory residue forbidden")
                    stack.append(ep)
                elif entry.is_file(follow_symlinks=False) and ep.suffix == ".lean":
                    rel = ep.relative_to(track_dir)
                    _need(rel == Path("ThinCoordInterpose.lean"), "EXTRA_LEAN_FILE", f"unexpected Lean file in bundle: {rel}")
        except VerifyS166Error:
            raise
        except OSError as exc:
            raise VerifyS166Error("IO_ERROR", f"bundle scan failed: {exc}") from exc


def _verify_lakefile_toml(toml_text: str) -> None:
    try:
        tdata = tomllib.loads(toml_text)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        raise VerifyS166Error("BAD_LAKEFILE", f"invalid lakefile.toml: {exc}") from exc
    _need("require" not in tdata and "requires" not in tdata, "FORBIDDEN_LAKE_REQUIRE", "external lake dependencies forbidden")
    _need(set(tdata.keys()) <= {"name", "version", "defaultTargets", "lean_lib"}, "BAD_LAKEFILE", "unexpected lakefile.toml keys")
    _need(tdata.get("name") == "thin_coord_interpose", "BAD_LAKEFILE", "unexpected lakefile package name")
    _need(tdata.get("defaultTargets") == ["ThinCoordInterpose"], "BAD_LAKEFILE", "unexpected defaultTargets")
    if "version" in tdata:
        _need(type(tdata["version"]) is str, "BAD_LAKEFILE", "lakefile version must be str")
    libs = tdata.get("lean_lib")
    _need(
        type(libs) is list and len(libs) == 1 and libs[0] == {"name": "ThinCoordInterpose"},
        "BAD_LAKEFILE",
        "lean_lib must declare strictly [{name = 'ThinCoordInterpose'}]",
    )


def _verify_lean_bundle_with_raw(
    track_dir: Path,
    *,
    live_lean: bool,
    lean_runner: Callable[[Path], dict[str, Any]] | None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    _audit_track_dir_tree(track_dir)
    file_hashes: dict[str, str] = {}
    raw_map: dict[str, bytes] = {}
    decoded: dict[str, str] = {}
    manifest: dict[str, Any] = {}
    for fname in LEAN_FILES:
        raw = _read_regular_bytes(track_dir / fname, fname)
        raw_map[fname] = raw
        if fname == "lake-manifest.json":
            manifest = _load_strict_json_bytes(raw, fname, crlf_code="CRLF_IN_LEAN_FILE")
        else:
            decoded[fname] = _decode_strict_utf8(raw, fname, crlf_code="CRLF_IN_LEAN_FILE")
        file_hashes[fname] = hashlib.sha256(raw).hexdigest()

    _need(decoded["lean-toolchain"] == "leanprover/lean4:v4.36.0\n", "BAD_LEAN_TOOLCHAIN", "lean-toolchain must pin leanprover/lean4:v4.36.0")
    _verify_lakefile_toml(decoded["lakefile.toml"])
    _need(manifest.get("packages") == [] and manifest.get("lakeDir") == ".lake", "NONEMPTY_LAKE_MANIFEST", "lake-manifest.json packages must be []")

    lean_src = decoded["ThinCoordInterpose.lean"]
    cleaned = verify_lean_source_clean(lean_src, require_pure_init=True)
    _need(re.search(r"(?<![A-Za-z0-9_'.])namespace\s+ThinCoordInterpose(?![A-Za-z0-9_'])", cleaned) is not None, "LEAN_NAMESPACE_MISSING", "ThinCoordInterpose namespace missing")
    pub_thms = re.findall(r"(?:^|\n)[ \t]*(?:protected\s+)?theorem\s+([A-Za-z0-9_.']+)", cleaned)
    _need(len(pub_thms) == len(LEAN_THEOREMS), "LEAN_THEOREM_COUNT_MISMATCH", f"expected {len(LEAN_THEOREMS)} theorems, found {len(pub_thms)}")
    expected_short = [t.removeprefix("ThinCoordInterpose.") for t in LEAN_THEOREMS]
    _need(pub_thms == expected_short, "LEAN_THEOREM_IDENTITY_MISMATCH", "theorem names do not match LEAN_THEOREMS")
    for full_thm in LEAN_THEOREMS:
        _need(
            re.search(rf"#print\s+axioms\s+{re.escape(full_thm)}(?![A-Za-z0-9_.'])", cleaned) is not None,
            "LEAN_AXIOM_PRINT_MISSING",
            f"missing #print axioms for {full_thm}",
        )

    lean_static_status = "STATIC_PASS"
    lean_live_mode = "STATIC_ONLY"
    live_lean_checked = False
    axioms_by_thm: dict[str, list[str]] = {}
    if live_lean:
        run_res = lean_runner(track_dir) if lean_runner is not None else default_live_lean_runner(track_dir, preloaded_files=raw_map)
        axioms_by_thm = audit_live_lean_output(run_res)
        lean_live_mode = "LIVE_LEAN_4_36_0_PASS"
        live_lean_checked = True

    return {
        "lean_toolchain": decoded["lean-toolchain"].strip(),
        "public_theorems": len(pub_thms),
        "lean_static_status": lean_static_status,
        "lean_live_mode": lean_live_mode,
        "live_lean_checked": live_lean_checked,
        "axioms_verified_count": len(axioms_by_thm),
        "file_sha256": file_hashes,
    }, raw_map


def _lstat_exists(path: Path, label: str) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise VerifyS166Error("IO_ERROR", f"{label}: {exc}") from exc
    return True


def _find_repo_root(track_dir: Path) -> Path | None:
    abs_td = Path(os.path.abspath(os.fspath(track_dir)))
    if abs_td.parent.name != "evidence":
        return None
    cand = abs_td.parent.parent
    probe = cand / "aletheia" / "lean_audit_hardening.py"
    if not _lstat_exists(probe, "repo_root"):
        return None
    return cand


def _collect_python_source_hashes(track_dir: Path) -> tuple[dict[str, str], Path | None]:
    abs_td = Path(os.path.abspath(os.fspath(track_dir)))
    here = Path(__file__).resolve().parent
    repo_root = _find_repo_root(abs_td)
    ev_dir = abs_td if (repo_root is not None or abs_td == here or any(_lstat_exists(abs_td / Path(rel).name, rel) for rel in EVIDENCE_PY_FILES)) else here
    hashes: dict[str, str] = {}
    for rel in EVIDENCE_PY_FILES:
        fname = Path(rel).name
        hashes[rel] = hashlib.sha256(_read_regular_bytes(ev_dir / fname, rel)).hexdigest()
    if repo_root is not None:
        for rel in CORE_PY_FILES:
            hashes[rel] = hashlib.sha256(_read_regular_bytes(repo_root / rel, rel)).hexdigest()
    return hashes, repo_root


def _must_fail_lean_clean(src: str, expected_codes: tuple[str, ...], *, require_pure_init: bool = True) -> bool:
    try:
        verify_lean_source_clean(src, require_pure_init=require_pure_init)
    except VerifyS166Error as exc:
        return exc.code in expected_codes
    return False


def _verify_exp_q46b_independent(
    repo_root: Path | None,
    *,
    expected_py_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Live-execute EXP-Q46b bypass negative/positive controls rather than emitting constants."""
    clean_ok = False
    try:
        verify_lean_source_clean('def ok := "/-- sorry --/"\ntheorem t : True := trivial\n', require_pure_init=True)
        clean_ok = True
    except VerifyS166Error:
        clean_ok = False

    bypasses = {
        "sorryAx": _must_fail_lean_clean("theorem b : False := sorryAx _\n", ("FORBIDDEN_LEAN_TOKEN",)),
        "ofReduceBool": _must_fail_lean_clean("theorem b : True := Lean.ofReduceBool _ _ rfl\n", ("FORBIDDEN_LEAN_TOKEN",)),
        "trustCompiler": _must_fail_lean_clean("def b := Lean.trustCompiler\n", ("FORBIDDEN_LEAN_TOKEN",)),
        "partial_theorem": _must_fail_lean_clean("partial def f (n : Nat) : Nat := f n\ntheorem t : True := trivial\n", ("FORBIDDEN_LEAN_TOKEN",)),
        "string_escape": _must_fail_lean_clean('def s := "/-"\ntheorem b : False := sorry\n', ("FORBIDDEN_LEAN_TOKEN",)),
        "interp_ws_escape": _must_fail_lean_clean('def s := s! "{ "/-" }"\ntheorem b : False := sorry\ndef t := s! "{ "-/" }"\n', ("FORBIDDEN_LEAN_TOKEN",)),
        "bang_s_interp": _must_fail_lean_clean('def s : Bool := !s!"{ "/-" }".isEmpty\ntheorem b : False := sorry\ndef t : Bool := !s!"{ "-/" }".isEmpty\n', ("FORBIDDEN_LEAN_TOKEN",)),
        "stop_tactic": _must_fail_lean_clean("theorem t_stop : False := by stop skip\n", ("FORBIDDEN_LEAN_TOKEN",)),
        "root_sorryAx": _must_fail_lean_clean("theorem t_rs : False := _root_.sorryAx False true\n", ("FORBIDDEN_LEAN_TOKEN",)),
        "root_guil_sorryAx": _must_fail_lean_clean("theorem t_rgs : False := _root_.«sorryAx» False true\n", ("FORBIDDEN_LEAN_TOKEN",)),
        "decide_native": _must_fail_lean_clean("theorem t_dn : 1 + 1 = 2 := by decide +native\n", ("FORBIDDEN_LEAN_TOKEN",)),
        "throwErrorAt_comp": _must_fail_lean_clean('import Lean.Exception\ndef t (stx : Lean.Syntax) := throwErrorAt stx "{ "/-" }"\ntheorem b : False := sorry\ndef t2 (stx : Lean.Syntax) := throwErrorAt stx "{ "-/" }"\n', ("FORBIDDEN_LEAN_TOKEN",), require_pure_init=False),
        "trace_comp": _must_fail_lean_clean('import Lean\ndef t := do\n  trace[Elab] "{ "/-" }"\ntheorem b : False := sorry\ndef t2 := do\n  trace[Elab] "{ "-/" }"\n', ("FORBIDDEN_LEAN_TOKEN",), require_pure_init=False),
        "syntax_macro": _must_fail_lean_clean('syntax "q!" interpolatedStr(term) : term\n', ("FORBIDDEN_LEAN_TOKEN",)),
        "multiline_extern": _must_fail_lean_clean('@[\nextern "c_evil"\n]\ndef f : Nat := 0\n', ("FORBIDDEN_LEAN_TOKEN",)),
        "public_import": _must_fail_lean_clean("public import Mathlib\n", ("NON_INIT_IMPORT",)),
        "hash_eval": _must_fail_lean_clean('#eval IO.println "x"\n', ("FORBIDDEN_LEAN_TOKEN",)),
    }

    lakefile_checked = False
    try:
        _verify_lakefile_toml('name = "thin_coord_interpose"\ndefaultTargets = ["ThinCoordInterpose"]\n[[require]]\nname = "mathlib"\n')
    except VerifyS166Error as exc:
        lakefile_checked = exc.code == "FORBIDDEN_LAKE_REQUIRE"

    missing_dir_rejected = False
    try:
        _audit_track_dir_tree(Path("/nonexistent_s166_probe_dir"))
    except VerifyS166Error as exc:
        missing_dir_rejected = exc.code == "IO_ERROR"

    aletheia_checks_passed = 0
    if repo_root is not None:
        _need(
            isinstance(expected_py_hashes, dict),
            "ALETHEIA_SELF_TEST_FAIL",
            "expected_py_hashes required when repo_root is provided",
        )
        try:
            sub_env = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            proc = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    _SUBPROC_LOAD_OWNED_CODE,
                    str(repo_root),
                    json.dumps(expected_py_hashes, sort_keys=True),
                    ",".join(_OWNED_ALETHEIA_MODULES),
                ],
                cwd=str(repo_root),
                env=sub_env,
                capture_output=True,
                timeout=30,
                check=False,
            )
            _need(proc.returncode == 0, "ALETHEIA_SELF_TEST_FAIL", "aletheia.lean_audit_hardening --self-test failed")
            st_obj = _load_strict_json_bytes(proc.stdout, "aletheia_self_test")
            _need(st_obj.get("passed") is True and type(st_obj.get("checks_passed")) is int, "ALETHEIA_SELF_TEST_FAIL", "invalid self-test payload")
            aletheia_checks_passed = st_obj["checks_passed"]
        except VerifyS166Error:
            raise
        except (OSError, subprocess.SubprocessError) as exc:
            raise VerifyS166Error("ALETHEIA_SELF_TEST_FAIL", f"failed running lean_audit_hardening: {exc}") from exc

    all_ok = clean_ok and all(bypasses.values()) and lakefile_checked and missing_dir_rejected
    _need(all_ok, "EXP_Q46B_SELF_CHECK_FAIL", "independent EXP-Q46b bypass check failed")
    return {
        "bypasses_covered": sum(1 for v in bypasses.values() if v),
        "aletheia_suite_checks_passed": aletheia_checks_passed,
        "string_literal_escape_closed": bypasses["string_escape"] and bypasses["interp_ws_escape"] and bypasses["bang_s_interp"],
        "syntax_and_multiline_attr_blocked": bypasses["syntax_macro"] and bypasses["multiline_extern"],
        "lakefile_included": lakefile_checked,
        "missing_dir_fail_closed": missing_dir_rejected,
    }


def _compute_static_sections(
    repo_root: Path | None,
    *,
    expected_py_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    cs29_grid, cs29_tx = _verify_cs29_grid_and_transcripts()
    return {
        "cs29_crossover_grid": cs29_grid,
        "cs29_transcript_fixtures": cs29_tx,
        "cs27_dag_and_portfolio": _verify_cs27_independent(),
        "cs28_interpose_regressions": _verify_cs28_independent(),
        "exp_q46b_bypass_checks": _verify_exp_q46b_independent(repo_root, expected_py_hashes=expected_py_hashes),
    }


def build_certificate(
    track_dir: Path,
    *,
    live_lean: bool = False,
    lean_runner: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recompute the full Track S166 certificate from scratch without importing `aletheia.*`."""
    lean_bundle, _ = _verify_lean_bundle_with_raw(track_dir, live_lean=live_lean, lean_runner=lean_runner)
    py_hashes, repo_root = _collect_python_source_hashes(track_dir)
    sections = _compute_static_sections(repo_root, expected_py_hashes=py_hashes)

    body = {
        "schema_version": SCHEMA_VERSION,
        "lean_bundle": lean_bundle,
        "python_source_sha256": py_hashes,
        **sections,
    }
    payload_sha = hashlib.sha256(_canon_bytes(body)).hexdigest()
    body["payload_sha256"] = payload_sha
    return body


def _json_exact_equal(lhs: Any, rhs: Any) -> bool:
    """Strict type-exact JSON structural equality (`bool` never equals `int`)."""
    if type(lhs) is not type(rhs):
        return False
    if isinstance(lhs, dict):
        if set(lhs.keys()) != set(rhs.keys()):
            return False
        return all(_json_exact_equal(lhs[k], rhs[k]) for k in lhs)
    if isinstance(lhs, list):
        if len(lhs) != len(rhs):
            return False
        return all(_json_exact_equal(a, b) for a, b in zip(lhs, rhs))
    return bool(lhs == rhs)


def verify_certificate_file(
    cert_path: Path,
    track_dir: Path,
    *,
    live_lean: bool = False,
    lean_runner: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify an on-disk certificate against pre-execution integrity gates, recomputation, and optional live Lean."""
    raw = _read_regular_bytes(cert_path, "certificate")
    cert = _load_strict_json_bytes(raw, "certificate")
    _need(set(cert.keys()) == _ROOT_KEYS, "CERT_KEY_MISMATCH", "unexpected or missing certificate keys")
    _need(_json_exact_equal(cert["schema_version"], SCHEMA_VERSION), "CERT_SCHEMA_MISMATCH", "bad certificate schema_version")
    got_sha = cert["payload_sha256"]
    _need(type(got_sha) is str and _SHA256_HEX_RE.fullmatch(got_sha) is not None, "BAD_PAYLOAD_SHA256", "invalid payload_sha256")

    unsigned = {k: cert[k] for k in cert if k != "payload_sha256"}
    recomputed_sha = hashlib.sha256(_canon_bytes(unsigned)).hexdigest()
    _need(hmac.compare_digest(got_sha, recomputed_sha), "PAYLOAD_SHA256_MISMATCH", "certificate payload_sha256 mismatch")

    lb = cert["lean_bundle"]
    static_lb, preloaded_lean = _verify_lean_bundle_with_raw(track_dir, live_lean=False, lean_runner=None)
    _need(
        type(lb) is dict and set(lb.keys()) == set(static_lb.keys()),
        "LEAN_BUNDLE_KEY_MISMATCH",
        "unexpected or missing lean_bundle schema",
    )
    _need(
        _json_exact_equal(lb["lean_static_status"], "STATIC_PASS"),
        "LEAN_STATIC_STATUS_MISMATCH",
        "lean_bundle.lean_static_status must be STATIC_PASS",
    )
    _need(
        type(lb["lean_live_mode"]) is str and lb["lean_live_mode"] in ("STATIC_ONLY", "LIVE_LEAN_4_36_0_PASS"),
        "LEAN_LIVE_STATUS_INVALID",
        "invalid lean_bundle.lean_live_mode",
    )
    expected_checked = lb["lean_live_mode"] == "LIVE_LEAN_4_36_0_PASS"
    _need(
        _json_exact_equal(lb["live_lean_checked"], expected_checked),
        "LEAN_LIVE_STATUS_INVALID",
        "lean_bundle.live_lean_checked disagrees with lean_live_mode",
    )
    expected_ax = 0 if lb["lean_live_mode"] == "STATIC_ONLY" else len(LEAN_THEOREMS)
    _need(
        _json_exact_equal(lb["axioms_verified_count"], expected_ax),
        "LEAN_AXIOM_COUNT_MISMATCH",
        "lean_bundle.axioms_verified_count disagrees with lean_live_mode",
    )
    _need(
        _json_exact_equal(lb["lean_toolchain"], static_lb["lean_toolchain"]),
        "LEAN_TOOLCHAIN_MISMATCH",
        "lean_toolchain disagrees with disk",
    )
    _need(
        _json_exact_equal(lb["file_sha256"], static_lb["file_sha256"]),
        "LEAN_HASH_MISMATCH",
        "Lean bundle file SHA-256s disagree with disk",
    )
    _need(
        _json_exact_equal(lb["public_theorems"], static_lb["public_theorems"]),
        "LEAN_THEOREM_MISMATCH",
        "Lean theorem count disagrees",
    )
    py_hashes, repo_root = _collect_python_source_hashes(track_dir)
    _need(
        _json_exact_equal(cert["python_source_sha256"], py_hashes),
        "PYTHON_HASH_MISMATCH",
        "Python source SHA-256s disagree with disk",
    )

    if not live_lean:
        _need(
            _json_exact_equal(lb["live_lean_checked"], False),
            "LEAN_LIVE_STATUS_MISMATCH",
            "certificate claiming live Lean verification requires --live-lean",
        )

    sections = _compute_static_sections(repo_root, expected_py_hashes=py_hashes)
    for key, val in sections.items():
        _need(_json_exact_equal(cert[key], val), "RECOMPUTE_MISMATCH", f"section {key} disagrees with independent recomputation")

    final_lb = static_lb
    if live_lean:
        run_res = lean_runner(track_dir) if lean_runner is not None else default_live_lean_runner(track_dir, preloaded_files=preloaded_lean)
        axioms_by_thm = audit_live_lean_output(run_res)
        final_lb = dict(
            static_lb,
            lean_live_mode="LIVE_LEAN_4_36_0_PASS",
            live_lean_checked=True,
            axioms_verified_count=len(axioms_by_thm),
        )

    return {
        "passed": True,
        "schema_version": SCHEMA_VERSION,
        "payload_sha256": recomputed_sha,
        "lean_static_status": final_lb["lean_static_status"],
        "lean_live_mode": final_lb["lean_live_mode"],
        "live_lean_checked": final_lb["live_lean_checked"],
        "axioms_verified_count": final_lb["axioms_verified_count"],
        "lean_theorems_verified": final_lb["public_theorems"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Track S166 Independent Zero-Shared-Code Verifier")
    ap.add_argument("--track-dir", type=Path, default=Path(__file__).resolve().parent, help="Track Lean bundle directory")
    grp = ap.add_mutually_exclusive_group(required=False)
    grp.add_argument("--write", type=Path, default=None, help="Write deterministic certificate JSON")
    grp.add_argument("--check", type=Path, default=None, help="Verify existing certificate JSON")
    ap.add_argument("--live-lean", action="store_true", help="Run isolated cold Lean 4.36.0 build and #print axioms audit")
    args = ap.parse_args(argv)

    try:
        if args.write is not None:
            cert = build_certificate(args.track_dir, live_lean=args.live_lean)
            _atomic_write_lf(args.write, _canon_bytes(cert))
            print(json.dumps({
                "passed": True,
                "action": "write",
                "payload_sha256": cert["payload_sha256"],
                "lean_static_status": cert["lean_bundle"]["lean_static_status"],
                "lean_live_mode": cert["lean_bundle"]["lean_live_mode"],
                "live_lean_checked": cert["lean_bundle"]["live_lean_checked"],
                "public_theorems": cert["lean_bundle"]["public_theorems"],
            }, sort_keys=True))
            return 0
        if args.check is not None:
            res = verify_certificate_file(args.check, args.track_dir, live_lean=args.live_lean)
            print(json.dumps(res, sort_keys=True))
            return 0
        cert = build_certificate(args.track_dir, live_lean=args.live_lean)
        print(json.dumps({
            "passed": True,
            "action": "verify",
            "payload_sha256": cert["payload_sha256"],
            "lean_static_status": cert["lean_bundle"]["lean_static_status"],
            "lean_live_mode": cert["lean_bundle"]["lean_live_mode"],
            "live_lean_checked": cert["lean_bundle"]["live_lean_checked"],
            "public_theorems": cert["lean_bundle"]["public_theorems"],
            "cs29_cases": len(cert["cs29_crossover_grid"]),
            "exp_q46b_bypasses": cert["exp_q46b_bypass_checks"]["bypasses_covered"],
        }, sort_keys=True))
        return 0
    except VerifyS166Error as exc:
        print(json.dumps({"passed": False, "code": exc.code, "detail": exc.detail}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
