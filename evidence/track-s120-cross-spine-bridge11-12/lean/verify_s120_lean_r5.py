#!/usr/bin/env python3
"""Track S120 / Project HoloSphere Cross-Spine Bridges (#49-#50) Lean 4.36.0 Verifier & R5 Suite.

Zero IEEE-754 floats, zero bare asserts, zero external dependencies, zero host-path leaks.
Supports both:
  1. Deterministic R4 CLI check mode (`--verify-lean`, `--check`, `--json`), bit-identical
     across `-I -B`, `-I -O -B`, and `-I -B -W error`.
  2. Full R5 `unittest` suite (default when invoked with no args, `-v`, or via `unittest`),
     exercising:
       - Exact pure-int & Z[sqrt(5)] cross-verification of Theorems #49 (BRIDGE_11) and #50 (BRIDGE_12)
       - R13b O(1) `in_ident` Lean 4 lexer + all 18 static pre-filter rules (must-fail controls)
       - R13b `#print axioms` parser & allowlist (`{propext, Quot.sound}`; blocks
         `Classical.choice`, `Lean.ofReduceBool`, `sorryAx`, `Lean.trustCompiler`)
       - Scrubbed `env -i` live `Lean 4.36.0` `--stdin` kernel check + live `Init.olean`
         `LEAN_PATH` hijack defense
       - Zone-B file I/O & CLI flag refusal must-fail controls
"""

from __future__ import annotations

import hashlib
import io
from itertools import permutations, product
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any
import unittest

LEAN_DIR = Path(__file__).resolve().parent
LEAN_FILE_NAME = "HoloSphereCrossSpineBridges.lean"
DEFAULT_LEAN_PATH = LEAN_DIR / LEAN_FILE_NAME
LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
LEAN_SOURCE_SHA256 = "2381dd26ca5c8411e5e8b427a820a50e277938b5c3e93f59d9e8143a8ab5b040"

PUBLIC_THEOREMS: tuple[str, ...] = (
    "HoloSphereCrossSpineBridges.p49_bridge11_bent4_u4_symplectic_and_flat_wht",
    "HoloSphereCrossSpineBridges.p50_bridge12_nonscalar_krein_holonomy_order_split",
)
PRIVATE_THEOREM_COUNT = 29
MAX_FILE_BYTES = 1_048_576
_SAFE_LEAN_ENV_KEYS = frozenset({"PATH", "HOME", "ELAN_HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "TERM"})
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_LEAN4_ID_FIRST = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_LEAN4_ID_REST = _LEAN4_ID_FIRST | frozenset("0123456789'!?")

LEAN4_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("R01_LITERAL_OR_GUILLEMET", re.compile(r'["«»]')),
    ("R02_IMPORT", re.compile(r"(?m)^\s*import\b")),
    ("R03_SORRY_ADMIT", re.compile(r"\b(?:sorry|admit|sorryAx)\b")),
    ("R04_AXIOM_DECL", re.compile(r"(?m)^\s*(?:private\s+|protected\s+)?axiom\b")),
    ("R05_UNSAFE_EXTERN", re.compile(r"\bunsafe\b|@\[[^\]]*\b(?:extern|implemented_by|csimp)\b")),
    ("R06_OPAQUE_PARTIAL", re.compile(r"\b(?:opaque|partial|noncomputable)\b")),
    ("R07_NATIVE_DECIDE", re.compile(r"\bnative_decide\b|\bdecide\s*\+\s*(?:native|revert)\b")),
    ("R08_DBG_TRACE", re.compile(r"\b(?:dbg_trace|dbgTrace|dbgTraceVal|dbgTraceIfShared|dbgSleep|dbgStackTrace)\b")),
    ("R09_INIT_EXPORT_ATTR", re.compile(r"@\[[^\]]*\b(?:export|init|builtin_init)\b|\b(?:initialize|builtin_initialize)\b")),
    ("R10_GUARD_MSGS", re.compile(r"#guard_msgs\b")),
    ("R11_WARN_SORRY_OPT", re.compile(r"\b(?:warn\.sorry|terminalTacticsAsSorry|allowUnsafeReducibility)\b")),
    ("R12_META_EVAL_CMD", re.compile(r"#(?:eval|reduce|synth|check_failure)\b|\brun_cmd\b|\brun_meta\b")),
    ("R13_SET_OPTION", re.compile(r"(?m)^\s*set_option\b")),
    ("R14_ELAB_TACTIC_MACRO", re.compile(r"(?m)^\s*(?:elab|elab_rules|macro|macro_rules|syntax|declare_syntax_cat)\b")),
    ("R15_IO_SYSTEM", re.compile(r"\bIO\.|\bSystem\.|\bLean\.Environment\b|\bLean\.Elab\b")),
    ("R16_PANIC_UNREACHABLE", re.compile(r"\b(?:panic!|unreachable!|assert!)")),
    ("R17_DECIDE_CONFIG", re.compile(r"\bconfig\s*:=\s*\{[^}]*\bnative\b")),
    ("R18_ROOT_ESCAPE", re.compile(r"\b_root_\.[A-Za-z_]")),
)

_LEAN4_PRINT_LINE_RE = re.compile(r"(?m)^\s*#print\b.*$")
_LEAN4_VALID_PRINT_RE = re.compile(r"^#print\s+axioms\s+(HoloSphereCrossSpineBridges\.[A-Za-z0-9_]+)$")
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'(HoloSphereCrossSpineBridges\.[A-Za-z0-9_]+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'(HoloSphereCrossSpineBridges\.[A-Za-z0-9_]+)' depends on axioms: \[([^\]]*)\]$")


class S120LeanError(ValueError):
    """Typed fail-closed error for Track S120 Cross-Spine Bridges Lean 4.36.0 verifier."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise S120LeanError(code, message)


def _reject_symlink_ancestors(path: Path, label: str) -> None:
    cur = Path(os.path.abspath(os.fspath(path)))
    for candidate in (cur, *cur.parents):
        if candidate.is_symlink():
            raise S120LeanError("SYMLINK_FORBIDDEN", f"{label}: symlink path or ancestor forbidden")


def read_regular_bytes_capped(path: Path, label: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    _reject_symlink_ancestors(path, label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(os.fspath(path), flags)
    except OSError as exc:
        raise S120LeanError("IO_OPEN_FAIL", f"{label}: cannot open regular file ({exc.__class__.__name__})") from exc
    try:
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NON_REGULAR_FILE", f"{label}: not a regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            blk = os.read(fd, 65536)
            if not blk:
                break
            total += len(blk)
            require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} bytes")
            chunks.append(blk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _match_lean4_char_literal(source: str, pos: int) -> int | None:
    n = len(source)
    if pos + 2 >= n or source[pos] != "'":
        return None
    c1 = source[pos + 1]
    if c1 in ("'", "\n", "\r"):
        return None
    if c1 != "\\":
        return (pos + 3) if source[pos + 2] == "'" else None
    if pos + 3 >= n:
        return None
    esc = source[pos + 2]
    if esc in ("\\", "'", '"', "n", "r", "t", "0"):
        return (pos + 4) if source[pos + 3] == "'" else None
    if esc == "x":
        if pos + 5 < n and source[pos + 3] in _HEX_DIGITS and source[pos + 4] in _HEX_DIGITS and source[pos + 5] == "'":
            return pos + 6
        return None
    if esc == "u":
        if pos + 7 < n and all(source[pos + 3 + k] in _HEX_DIGITS for k in range(4)) and source[pos + 7] == "'":
            return pos + 8
        return None
    return None


def strip_lean4_comments_and_chars(source: str) -> str:
    """R13b O(1) in_ident lexer stripping line/nested block comments and Char literals."""
    require_ok("\x00" not in source, "NUL_BYTE_FORBIDDEN", "NUL byte forbidden in Lean source")
    require_ok("\r" not in source, "CRLF_FORBIDDEN", "CR/LF forbidden in Lean source")
    out: list[str] = []
    i = 0
    n = len(source)
    block_depth = 0
    in_ident = False
    while i < n:
        ch = source[i]
        if block_depth > 0:
            if ch == "/" and i + 1 < n and source[i + 1] == "-":
                block_depth += 1
                out.append("  ")
                i += 2
                continue
            if ch == "-" and i + 1 < n and source[i + 1] == "/":
                block_depth -= 1
                out.append("  ")
                i += 2
                continue
            out.append("\n" if ch == "\n" else " ")
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "-":
            block_depth = 1
            in_ident = False
            out.append("  ")
            i += 2
            continue
        if ch == "-" and i + 1 < n and source[i + 1] == "-":
            in_ident = False
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "'" and not in_ident:
            end_pos = _match_lean4_char_literal(source, i)
            if end_pos is not None:
                out.append(" " * (end_pos - i))
                i = end_pos
                continue
        if in_ident:
            if ch not in _LEAN4_ID_REST:
                in_ident = False
        else:
            if ch in _LEAN4_ID_FIRST:
                in_ident = True
        out.append(ch)
        i += 1
    require_ok(block_depth == 0, "UNCLOSED_BLOCK_COMMENT", "unclosed /- ... -/ block comment")
    return "".join(out)


def audit_lean4_static(source: str) -> dict[str, Any]:
    stripped = strip_lean4_comments_and_chars(source)
    for code, pat in LEAN4_RULES:
        m = pat.search(stripped)
        require_ok(m is None, code, f"forbidden Lean token matched {code}")

    pub_theorems = re.findall(r"(?m)^theorem\s+([A-Za-z0-9_]+)\b", stripped)
    priv_theorems = re.findall(r"(?m)^private\s+theorem\s+([A-Za-z0-9_]+)\b", stripped)
    expected_short = [t.split(".", 1)[1] for t in PUBLIC_THEOREMS]
    require_ok(pub_theorems == expected_short, "THEOREM_LIST_MISMATCH", f"got public theorems {pub_theorems}")
    require_ok(len(priv_theorems) == PRIVATE_THEOREM_COUNT, "PRIVATE_HELPER_COUNT", f"got {len(priv_theorems)}")

    print_lines = _LEAN4_PRINT_LINE_RE.findall(stripped)
    require_ok(len(print_lines) == len(PUBLIC_THEOREMS), "PRINT_AXIOMS_COUNT", f"expected {len(PUBLIC_THEOREMS)} #print lines")
    printed: list[str] = []
    for ln in print_lines:
        m = _LEAN4_VALID_PRINT_RE.match(ln.strip())
        require_ok(m is not None, "INVALID_PRINT_CMD", f"invalid #print line: {ln!r}")
        if m is not None:
            printed.append(m.group(1))
    require_ok(tuple(printed) == PUBLIC_THEOREMS, "PRINT_AXIOMS_ORDER", "printed theorem order mismatch")
    return {
        "static_rules_checked": len(LEAN4_RULES),
        "public_theorem_count": len(pub_theorems),
        "private_theorem_count": len(priv_theorems),
        "total_theorem_decls": len(pub_theorems) + len(priv_theorems),
    }


def _unwrap_axiom_lines(stdout: str) -> list[str]:
    merged: list[str] = []
    for raw_ln in stdout.splitlines():
        if not raw_ln.strip():
            continue
        if raw_ln[0].isspace() and merged:
            merged[-1] = merged[-1] + " " + raw_ln.strip()
        else:
            merged.append(raw_ln.strip())
    return merged


def parse_and_audit_lean_axioms(stdout: str) -> dict[str, list[str]]:
    lines = _unwrap_axiom_lines(stdout)
    require_ok(len(lines) == len(PUBLIC_THEOREMS), "AXIOM_LINE_COUNT", f"expected {len(PUBLIC_THEOREMS)} output lines, got {len(lines)}")
    axiom_map: dict[str, list[str]] = {}
    for expected_thm, line in zip(PUBLIC_THEOREMS, lines):
        m_none = _LEAN4_AXIOM_NONE_RE.match(line)
        if m_none is not None:
            thm = m_none.group(1)
            require_ok(thm == expected_thm, "AXIOM_THM_ORDER", f"expected {expected_thm}, got {thm}")
            axiom_map[thm] = []
            continue
        m_dep = _LEAN4_AXIOM_DEP_RE.match(line)
        require_ok(m_dep is not None, "UNEXPECTED_LEAN_STDOUT", f"unrecognized Lean output line: {line!r}")
        if m_dep is not None:
            thm = m_dep.group(1)
            require_ok(thm == expected_thm, "AXIOM_THM_ORDER", f"expected {expected_thm}, got {thm}")
            axioms = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
            for ax in axioms:
                require_ok(ax in _ALLOWED_LEAN_AXIOMS, "FORBIDDEN_AXIOM", f"{thm} uses forbidden axiom {ax!r}")
            axiom_map[thm] = axioms
    return axiom_map


def resolve_lean_binary() -> str:
    override = os.environ.get("ALETHEIA_LEAN_BIN")
    if override:
        return override
    toolchain_rel = Path("toolchains/leanprover--lean4---v4.36.0/bin/lean")
    elan_home = os.environ.get("ELAN_HOME", "")
    if elan_home:
        cand = Path(elan_home) / toolchain_rel
        if cand.is_file():
            return str(cand)
    found = shutil.which("lean")
    if found is not None:
        # Prefer the direct toolchain binary next to an elan shim so env -i HOME=/nonexistent succeeds
        for anchor in (Path(os.path.abspath(found)), Path(os.path.realpath(found))):
            direct = anchor.parent.parent / toolchain_rel
            if direct.is_file():
                return str(direct)
        return found
    home = os.environ.get("HOME", "")
    if home:
        for base in (Path(home) / ".elan", Path(home) / ".local"):
            cand = base / toolchain_rel
            if cand.is_file():
                return str(cand)
    raise S120LeanError("LEAN_BINARY_UNAVAILABLE", "lean not found on PATH")


def build_scrubbed_lean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k in _SAFE_LEAN_ENV_KEYS}


def _detect_lean_436() -> bool:
    try:
        lean_bin = resolve_lean_binary()
        proc = subprocess.run(
            [lean_bin, "--version"],
            capture_output=True,
            text=True,
            env=build_scrubbed_lean_env(),
            timeout=15,
            check=False,
        )
    except (S120LeanError, OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and "4.36.0" in proc.stdout


_HAS_LEAN = _detect_lean_436()


_LIVE_LEAN_CACHE: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}


def verify_lean4_file_live(lean_path: Path = DEFAULT_LEAN_PATH, check_sha: bool = True) -> dict[str, Any]:
    raw = read_regular_bytes_capped(lean_path, LEAN_FILE_NAME)
    try:
        src = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S120LeanError("INVALID_UTF8", "Lean file is not valid UTF-8") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if check_sha:
        require_ok(sha == LEAN_SOURCE_SHA256, "LEAN_SHA_MISMATCH", f"expected {LEAN_SOURCE_SHA256}, got {sha}")

    static_info = audit_lean4_static(src)
    lean_bin = resolve_lean_binary()
    env = build_scrubbed_lean_env()
    cache_key = (sha, tuple(sorted(env.items())))
    cached = _LIVE_LEAN_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)
    try:
        ver_proc = subprocess.run([lean_bin, "--version"], capture_output=True, text=True, env=env, timeout=30, check=False)
    except OSError as exc:
        raise S120LeanError("LEAN_EXEC_ERROR", f"cannot execute lean ({exc.__class__.__name__})") from exc
    require_ok(ver_proc.returncode == 0 and "4.36.0" in ver_proc.stdout, "LEAN_VERSION_MISMATCH", f"bad lean version: {ver_proc.stdout!r}")

    try:
        proc = subprocess.run([lean_bin, "--stdin"], input=src, capture_output=True, text=True, env=env, timeout=360, check=False)
    except OSError as exc:
        raise S120LeanError("LEAN_EXEC_ERROR", f"cannot execute lean --stdin ({exc.__class__.__name__})") from exc
    require_ok("warning:" not in (proc.stdout + proc.stderr).lower(), "LEAN_WARNING_FORBIDDEN", "Lean emitted warning")
    require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean exited {proc.returncode}")
    require_ok(proc.stderr == "", "LEAN_STDERR_NONEMPTY", f"non-empty stderr: {proc.stderr!r}")
    axioms = parse_and_audit_lean_axioms(proc.stdout)
    result = {
        "status": "LEAN_OK",
        "lean_toolchain": LEAN_TOOLCHAIN,
        "lean_version": ver_proc.stdout.strip().splitlines()[0],
        "lean_source_sha256": sha,
        "theorems_verified": len(axioms),
        "axioms": axioms,
        **static_info,
    }
    _LIVE_LEAN_CACHE[cache_key] = dict(result)
    return result


# ---------------------------------------------------------------------------
# Pure-Int & Z[sqrt(5)] Exact Oracle Verification of Theorems #49 & #50
# ---------------------------------------------------------------------------

Z5 = tuple[int, int]
QuatZ5 = tuple[Z5, Z5, Z5, Z5]


def _bent4_quad(x: int) -> int:
    return (((x >> 0) & 1) & ((x >> 2) & 1)) ^ (((x >> 1) & 1) & ((x >> 3) & 1))


def _bent4_polar(x: int, y: int) -> int:
    return (
        (((x >> 0) & 1) & ((y >> 2) & 1))
        ^ (((x >> 2) & 1) & ((y >> 0) & 1))
        ^ (((x >> 1) & 1) & ((y >> 3) & 1))
        ^ (((x >> 3) & 1) & ((y >> 1) & 1))
    )


def _u4_heis(x: int, s: int) -> tuple[tuple[int, ...], ...]:
    return (
        (1, (x >> 0) & 1, (x >> 1) & 1, s & 1),
        (0, 1, 0, (x >> 2) & 1),
        (0, 0, 1, (x >> 3) & 1),
        (0, 0, 0, 1),
    )


def _mat4_mul_f2(a: tuple[tuple[int, ...], ...], b: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(sum(a[i][k] & b[k][j] for k in range(4)) & 1 for j in range(4)) for i in range(4))


def _pauli4_z(x: int) -> tuple[tuple[int, ...], ...]:
    x1, x2, x3, x4 = (x >> 0) & 1, (x >> 1) & 1, (x >> 2) & 1, (x >> 3) & 1
    rows: list[tuple[int, ...]] = []
    for r in range(4):
        c0 = ((r >> 0) & 1) ^ x1
        c1 = ((r >> 1) & 1) ^ x2
        col = c0 | (c1 << 1)
        sgn = -1 if ((x3 & c0) ^ (x4 & c1)) else 1
        row = [0, 0, 0, 0]
        row[col] = sgn
        rows.append(tuple(row))
    return tuple(rows)


def _mat4_mul_z(a: tuple[tuple[int, ...], ...], b: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)) for i in range(4))


def _a16_syndrome(w16: int) -> int:
    w = w16 & 0xFFFF
    p0 = w.bit_count() & 1
    p1 = (w & 0xAAAA).bit_count() & 1
    p2 = (w & 0xCCCC).bit_count() & 1
    p3 = (w & 0xF0F0).bit_count() & 1
    p4 = (w & 0xFF00).bit_count() & 1
    return p0 | (p1 << 1) | (p2 << 2) | (p3 << 3) | (p4 << 4)


def _mat3_mul_z(a: tuple[tuple[int, ...], ...], b: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _mat3_trans_z(m: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(m[r][c] for r in range(3)) for c in range(3))


def _krein_25_z(g: tuple[tuple[int, ...], ...], op: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    cong = _mat3_mul_z(_mat3_trans_z(op), _mat3_mul_z(g, op))
    return tuple(tuple(25 * g[i][j] - cong[i][j] for j in range(3)) for i in range(3))


def _z5_mul(x: Z5, y: Z5) -> Z5:
    return (x[0] * y[0] + 5 * x[1] * y[1], x[0] * y[1] + x[1] * y[0])


def _z5_pos(z: Z5) -> bool:
    a, b = z
    if a >= 0 and b >= 0 and a + b > 0:
        return True
    if a > 0 and b < 0 and 5 * b * b < a * a:
        return True
    if a < 0 and b > 0 and a * a < 5 * b * b:
        return True
    return False


def _build_scale4_2i() -> list[QuatZ5]:
    elems: set[QuatZ5] = set()
    z0: Z5 = (0, 0)
    for idx in range(4):
        for s in ((4, 0), (-4, 0)):
            v = [z0, z0, z0, z0]
            v[idx] = s
            elems.add((v[0], v[1], v[2], v[3]))
    for signs in product(((2, 0), (-2, 0)), repeat=4):
        elems.add(signs)  # type: ignore[arg-type]
    for perm in permutations(range(4)):
        inv = sum(1 for i in range(4) for j in range(i + 1, 4) if perm[i] > perm[j])
        if inv % 2 != 0:
            continue
        for s1, s2, s3 in product((1, -1), repeat=3):
            raw = (z0, (2 * s1, 0), (-s2, s2), (s3, s3))
            elems.add((raw[perm[0]], raw[perm[1]], raw[perm[2]], raw[perm[3]]))
    return sorted(elems)


def verify_exact_s120_bridges_oracle() -> dict[str, Any]:
    # #49 BRIDGE_11 checks
    polar_hits = sum(
        1 for x in range(16) for y in range(16)
        if (_bent4_quad(x ^ y) ^ _bent4_quad(x) ^ _bent4_quad(y)) == _bent4_polar(x, y)
    )
    require_ok(polar_hits == 256, "POLAR_MISMATCH", f"got {polar_hits}")

    u4_comm_hits = 0
    for x in range(16):
        for s in (0, 1):
            mx = _u4_heis(x, s)
            ix = _u4_heis(x, s ^ _bent4_quad(x))
            require_ok(_mat4_mul_f2(mx, ix) == _u4_heis(0, 0), "U4_INV_FAIL", "bad inverse")
            for y in range(16):
                for t in (0, 1):
                    my = _u4_heis(y, t)
                    iy = _u4_heis(y, t ^ _bent4_quad(y))
                    comm = _mat4_mul_f2(_mat4_mul_f2(mx, my), _mat4_mul_f2(ix, iy))
                    if comm == _u4_heis(0, _bent4_polar(x, y)):
                        u4_comm_hits += 1
    require_ok(u4_comm_hits == 1024, "U4_COMM_MISMATCH", f"got {u4_comm_hits}")

    paulis = [_pauli4_z(x) for x in range(16)]
    pauli_hits = 0
    for x in range(16):
        for y in range(16):
            ab = _mat4_mul_z(paulis[x], paulis[y])
            ba = _mat4_mul_z(paulis[y], paulis[x])
            sgn = -1 if _bent4_polar(x, y) else 1
            if ab == tuple(tuple(sgn * ba[i][j] for j in range(4)) for i in range(4)):
                pauli_hits += 1
    require_ok(pauli_hits == 256, "PAULI_MISMATCH", f"got {pauli_hits}")

    wht_hits = 0
    for u in range(16):
        acc = sum(-1 if (_bent4_quad(x) ^ ((u & x).bit_count() & 1)) else 1 for x in range(16))
        if acc == (-4 if _bent4_quad(u) else 4):
            wht_hits += 1
    require_ok(wht_hits == 16, "WHT_MISMATCH", f"got {wht_hits}")

    upper_faults_ok = 0
    clean = [1 if k < 4 else 0 for k in range(16)]
    require_ok(_a16_syndrome(0x000F) == 0, "CW000F_SYNDROME", "0x000F not valid codeword")
    for b in (1, 2, 3):
        step = 1 << b
        for j in range(16):
            pert = list(clean)
            pert[j] += step
            lsb_w = sum(((pert[k] & 1) << k) for k in range(16))
            plane_w = sum((((pert[k] >> b) & 1) << k) for k in range(16))
            syn = _a16_syndrome(plane_w)
            if _a16_syndrome(lsb_w) == 0 and (syn & 1) == 1 and ((syn >> 1) & 0xF) == j:
                upper_faults_ok += 1
    require_ok(upper_faults_ok == 48, "CARRY_COVER_MISMATCH", f"got {upper_faults_ok}")

    # #50 BRIDGE_12 checks
    id3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    g311 = ((3, 0, 0), (0, 1, 0), (0, 0, 1))
    l5 = ((3, 0, 0), (0, 6, 0), (0, 0, 3))
    u_cyc = ((0, 1, 0), (0, 0, 1), (1, 0, 0))
    m_ul_i = _krein_25_z(id3, _mat3_mul_z(u_cyc, l5))
    m_lu_i = _krein_25_z(id3, _mat3_mul_z(l5, u_cyc))
    m_ul_g3 = _krein_25_z(g311, _mat3_mul_z(u_cyc, l5))
    m_lu_g3 = _krein_25_z(g311, _mat3_mul_z(l5, u_cyc))
    require_ok(m_ul_i == ((16, 0, 0), (0, -11, 0), (0, 0, 16)), "MUL_I3_MISMATCH", f"got {m_ul_i}")
    require_ok(m_lu_i == ((16, 0, 0), (0, 16, 0), (0, 0, -11)), "MLU_I3_MISMATCH", f"got {m_lu_i}")
    require_ok(m_ul_g3 == ((66, 0, 0), (0, -83, 0), (0, 0, 16)), "MUL_G3_MISMATCH", f"got {m_ul_g3}")
    require_ok(m_lu_g3 == ((66, 0, 0), (0, -2, 0), (0, 0, -11)), "MLU_G3_MISMATCH", f"got {m_lu_g3}")

    elems_2i = _build_scale4_2i()
    require_ok(len(elems_2i) == 120, "GROUP_2I_SIZE", f"got {len(elems_2i)}")
    neg_2i = 0
    pos_2i = 0
    for q in elems_2i:
        w2 = _z5_mul(q[0], q[0])
        h16 = (48 - 4 * w2[0], -4 * w2[1])
        if _z5_pos((-h16[0], -h16[1])):
            neg_2i += 1
        elif _z5_pos(h16):
            pos_2i += 1
    require_ok(neg_2i == 2 and pos_2i == 118, "HOLONOMY_2I_SPLIT", f"got {neg_2i}/{pos_2i}")

    return {
        "polar_matches": polar_hits,
        "u4_commutator_matches": u4_comm_hits,
        "pauli_commutator_matches": pauli_hits,
        "wht_self_dual_matches": wht_hits,
        "upper_nibble_carry_faults": upper_faults_ok,
        "g311_ul_diag": [m_ul_g3[0][0], m_ul_g3[1][1], m_ul_g3[2][2]],
        "g311_lu_diag": [m_lu_g3[0][0], m_lu_g3[1][1], m_lu_g3[2][2]],
        "holonomy_2i_neg_pos": [neg_2i, pos_2i],
    }


# ---------------------------------------------------------------------------
# R5 Adversarial & Live-Lean Test Suite
# ---------------------------------------------------------------------------

class TestS120CrossSpineBridgesLeanR5(unittest.TestCase):
    def test_01_exact_bridge11_and_bridge12_oracle(self) -> None:
        res = verify_exact_s120_bridges_oracle()
        self.assertEqual(res["polar_matches"], 256)
        self.assertEqual(res["u4_commutator_matches"], 1024)
        self.assertEqual(res["pauli_commutator_matches"], 256)
        self.assertEqual(res["wht_self_dual_matches"], 16)
        self.assertEqual(res["upper_nibble_carry_faults"], 48)
        self.assertEqual(res["g311_ul_diag"], [66, -83, 16])
        self.assertEqual(res["g311_lu_diag"], [66, -2, -11])
        self.assertEqual(res["holonomy_2i_neg_pos"], [2, 118])

    def test_02_r13b_lexer_and_all_18_static_must_fail_rules(self) -> None:
        clean_src = DEFAULT_LEAN_PATH.read_text(encoding="utf-8")
        info = audit_lean4_static(clean_src)
        self.assertEqual(info["static_rules_checked"], 18)
        self.assertEqual(info["public_theorem_count"], 2)
        self.assertEqual(info["private_theorem_count"], PRIVATE_THEOREM_COUNT)

        primed = clean_src.replace(
            "def bitAt",
            "-- comment with sorry, native_decide, and \"quote\"\ndef b_prime' : Int := 1\ndef bitAt",
            1,
        )
        self.assertEqual(audit_lean4_static(primed)["public_theorem_count"], 2)

        for bad_src, expected_code in (
            ("a\x00b", "NUL_BYTE_FORBIDDEN"),
            ("a\r\nb", "CRLF_FORBIDDEN"),
            ("/- unclosed", "UNCLOSED_BLOCK_COMMENT"),
        ):
            with self.assertRaises(S120LeanError) as cm0:
                strip_lean4_comments_and_chars(bad_src)
            self.assertEqual(cm0.exception.code, expected_code)

        snippets = (
            ("R01_LITERAL_OR_GUILLEMET", 'def s := "bad"\n'),
            ("R02_IMPORT", "import Init\n"),
            ("R03_SORRY_ADMIT", "def x := sorry\n"),
            ("R04_AXIOM_DECL", "axiom bad : False\n"),
            ("R05_UNSAFE_EXTERN", "unsafe def u : Nat := 0\n"),
            ("R06_OPAQUE_PARTIAL", "noncomputable def nc : Nat := 0\n"),
            ("R07_NATIVE_DECIDE", "theorem t : True := by native_decide\n"),
            ("R08_DBG_TRACE", "def d := dbg_trace 1\n"),
            ("R09_INIT_EXPORT_ATTR", "@[export c_fn] def f : Nat := 0\n"),
            ("R10_GUARD_MSGS", "#guard_msgs in\n"),
            ("R11_WARN_SORRY_OPT", "def w := terminalTacticsAsSorry\n"),
            ("R12_META_EVAL_CMD", "#eval 1 + 1\n"),
            ("R13_SET_OPTION", "set_option maxHeartbeats 0\n"),
            ("R14_ELAB_TACTIC_MACRO", "macro_rules | `(t) => `(t)\n"),
            ("R15_IO_SYSTEM", "def io := IO.println\n"),
            ("R16_PANIC_UNREACHABLE", "def p := panic! 0\n"),
            ("R17_DECIDE_CONFIG", "def c := decide (config := { native := true })\n"),
            ("R18_ROOT_ESCAPE", "def r := _root_.Nat\n"),
        )
        for expected_code, poison in snippets:
            with self.assertRaises(S120LeanError) as cm:
                audit_lean4_static(poison + clean_src)
            self.assertEqual(cm.exception.code, expected_code)

    def test_03_r13b_axiom_parser_and_must_fail_axioms(self) -> None:
        wrapped = (
            f"'{PUBLIC_THEOREMS[0]}' does not depend on any axioms\n"
            f"'{PUBLIC_THEOREMS[1]}' depends on axioms: [propext,\n Quot.sound]\n"
        )
        parsed = parse_and_audit_lean_axioms(wrapped)
        self.assertEqual(parsed[PUBLIC_THEOREMS[0]], [])
        self.assertEqual(parsed[PUBLIC_THEOREMS[1]], ["propext", "Quot.sound"])

        base_lines = [f"'{thm}' depends on axioms: [propext, Quot.sound]" for thm in PUBLIC_THEOREMS]
        for forbidden in ("Classical.choice", "Lean.ofReduceBool", "sorryAx", "Lean.trustCompiler"):
            bad = list(base_lines)
            bad[1] = f"'{PUBLIC_THEOREMS[1]}' depends on axioms: [propext, {forbidden}]"
            with self.assertRaises(S120LeanError) as cm:
                parse_and_audit_lean_axioms("\n".join(bad) + "\n")
            self.assertEqual(cm.exception.code, "FORBIDDEN_AXIOM")

    def test_04_zone_b_sha_tamper_symlink_and_flag_refusal(self) -> None:
        raw = read_regular_bytes_capped(DEFAULT_LEAN_PATH, LEAN_FILE_NAME)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), LEAN_SOURCE_SHA256)

        with tempfile.TemporaryDirectory(prefix="s120_lean_r5_") as td:
            d = Path(td)
            mod_lean = d / "tampered.lean"
            mod_lean.write_text(DEFAULT_LEAN_PATH.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(S120LeanError) as cm_sha:
                verify_lean4_file_live(mod_lean, check_sha=True)
            self.assertEqual(cm_sha.exception.code, "LEAN_SHA_MISMATCH")

            sym = d / "sym.lean"
            os.symlink(DEFAULT_LEAN_PATH, sym)
            with self.assertRaises(S120LeanError) as cm_sym:
                read_regular_bytes_capped(sym, "sym")
            self.assertEqual(cm_sym.exception.code, "SYMLINK_FORBIDDEN")

        out_buf2, err_buf2 = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = out_buf2, err_buf2
            rc_bad = run_cli(["--unknown-flag"])
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        self.assertEqual(rc_bad, 2)
        self.assertIn("UNKNOWN_FLAG", err_buf2.getvalue())

    @unittest.skipUnless(_HAS_LEAN, "Lean 4.36.0 toolchain unavailable")
    def test_05_live_lean_compile_and_init_olean_hijack_defense(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s120_lean_live_") as td:
            d = Path(td)
            lean_bin = resolve_lean_binary()
            src = DEFAULT_LEAN_PATH.read_text(encoding="utf-8")
            (d / "Init.olean").write_bytes(b"CORRUPT_FAKE_INIT_OLEAN")
            poison_env = dict(os.environ)
            poison_env["LEAN_PATH"] = str(d)
            raw_proc = subprocess.run([lean_bin, "--stdin"], input=src, capture_output=True, text=True, env=poison_env, timeout=60, check=False)
            self.assertNotEqual(raw_proc.returncode, 0)

            _LIVE_LEAN_CACHE.clear()
            old_lp = os.environ.get("LEAN_PATH")
            try:
                os.environ["LEAN_PATH"] = str(d)
                clean_res = verify_lean4_file_live(DEFAULT_LEAN_PATH, check_sha=True)
                self.assertEqual(clean_res["theorems_verified"], 2)
                self.assertEqual(clean_res["lean_source_sha256"], LEAN_SOURCE_SHA256)
                self.assertEqual(clean_res["axioms"][PUBLIC_THEOREMS[0]], ["propext"])
                self.assertEqual(clean_res["axioms"][PUBLIC_THEOREMS[1]], ["propext", "Quot.sound"])
            finally:
                if old_lp is None:
                    os.environ.pop("LEAN_PATH", None)
                else:
                    os.environ["LEAN_PATH"] = old_lp

    @unittest.skipUnless(_HAS_LEAN, "Lean 4.36.0 toolchain unavailable")
    def test_06_live_lean_cli_json(self) -> None:
        out_buf, err_buf = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = out_buf, err_buf
            rc = run_cli(["--verify-lean", "--json"])
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        self.assertEqual(rc, 0)
        payload = json.loads(out_buf.getvalue())
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["theorems_verified"], 2)


def run_cli(argv: list[str]) -> int:
    json_out = False
    for a in argv:
        if a == "--json":
            json_out = True
        elif a in ("--verify-lean", "--check"):
            pass
        else:
            sys.stderr.write(f"[UNKNOWN_FLAG] unknown flag: {a}\n")
            return 2
    try:
        oracle_res = verify_exact_s120_bridges_oracle()
        lean_res = verify_lean4_file_live(DEFAULT_LEAN_PATH, check_sha=True)
        report = {**lean_res, "status": "OK", "oracle_witnesses": oracle_res}
    except S120LeanError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if json_out:
        sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
    else:
        sys.stdout.write(
            f"S120_LEAN_OK theorems={report['theorems_verified']} "
            f"sha256={report['lean_source_sha256']} "
            f"u4_comm={oracle_res['u4_commutator_matches']} "
            f"2i_split={oracle_res['holonomy_2i_neg_pos'][0]}/{oracle_res['holonomy_2i_neg_pos'][1]}\n"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and all(a in ("--verify-lean", "--check", "--json") or a.startswith("--unknown") for a in args):
        return run_cli(args)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestS120CrossSpineBridgesLeanR5)
    verbosity = 2 if ("-v" in args or "--verbose" in args) else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
