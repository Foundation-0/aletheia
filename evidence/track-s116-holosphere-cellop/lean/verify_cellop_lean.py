#!/usr/bin/env python3
"""Project HoloSphere (PR #2 Candidate / Track S116 CellOp) Lean 4.36.0 Verifier.

Zero IEEE-754 floats, zero bare asserts, zero external dependencies, zero host-path leaks.
Provides:
  - Hardened regular-file I/O (O_NOFOLLOW, symlink ancestor rejection, size cap)
  - R13b O(1) in_ident Lean 4 lexer + 18-rule static pre-filter (blocks native_decide,
    sorry/admit, axiom, import, unsafe/extern, noncomputable, set_option, meta eval)
  - Scrubbed env -i live Lean 4.36.0 --stdin kernel & #print axioms verification
    (0 sorryAx, 0 Classical.choice, 0 Lean.ofReduceBool, 0 warnings, 0 stderr bytes)
  - Exact pure-int / Fraction cross-verification of Theorems #37-#40 + #40b (incl.
    exhaustive [-8, 7]^4 Block-H4 check, exact Pythagorean rational Cayley SO(3)
    involution & O(1)-VRAM reversibility, and exhaustive 256x256 H_256 + Maiorana-McFarland
    bent4 orthogonality & 0/2048 constant-warp verification)
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any

LEAN_DIR = Path(__file__).resolve().parent
LEAN_FILE_NAME = "HoloSphereCellOpInvariants.lean"
DEFAULT_LEAN_PATH = LEAN_DIR / LEAN_FILE_NAME
LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
LEAN_SOURCE_SHA256 = "78c8e3bae5bd16569c539ceadc4b0f8a82fc3ee762625579687f8cddc914dfc4"

PUBLIC_THEOREMS: tuple[str, ...] = (
    "HoloSphereCellOpInvariants.p1_blockh4_involutory_and_int8_bounds",
    "HoloSphereCellOpInvariants.p2_cayley_unit_ball_so3_involution_and_even",
    "HoloSphereCellOpInvariants.p3_cayley_exact_inverse_reversibility",
    "HoloSphereCellOpInvariants.p4_hadamard256_byte_orthogonality",
    "HoloSphereCellOpInvariants.p4b_bent_phase_preserves_orthogonality",
)
PRIVATE_THEOREM_COUNT = 30
MAX_FILE_BYTES = 1_048_576
_SAFE_LEAN_ENV_KEYS = frozenset({"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "TERM"})
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
_LEAN4_VALID_PRINT_RE = re.compile(r"^#print\s+axioms\s+(HoloSphereCellOpInvariants\.[A-Za-z0-9_]+)$")
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'(HoloSphereCellOpInvariants\.[A-Za-z0-9_]+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'(HoloSphereCellOpInvariants\.[A-Za-z0-9_]+)' depends on axioms: \[([^\]]*)\]$")


class CellOpLeanError(ValueError):
    """Typed fail-closed error for CellOp Lean 4.36.0 verifier."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise CellOpLeanError(code, message)


def _reject_symlink_ancestors(path: Path, label: str) -> None:
    cur = Path(os.path.abspath(os.fspath(path)))
    for candidate in (cur, *cur.parents):
        if candidate.is_symlink():
            raise CellOpLeanError("SYMLINK_FORBIDDEN", f"{label}: symlink path or ancestor forbidden")


def read_regular_bytes_capped(path: Path, label: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    _reject_symlink_ancestors(path, label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(os.fspath(path), flags)
    except OSError as exc:
        raise CellOpLeanError("IO_OPEN_FAIL", f"{label}: cannot open regular file ({exc.__class__.__name__})") from exc
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


def parse_and_audit_lean_axioms(stdout: str) -> dict[str, list[str]]:
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
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


def _direct_toolchain_from_elan_root(elan_root: Path) -> str | None:
    cand = elan_root / "toolchains" / "leanprover--lean4---v4.36.0" / "bin" / "lean"
    if cand.is_file() and os.access(cand, os.X_OK):
        return str(cand)
    return None


def resolve_lean_binary() -> str:
    """Resolve the Lean 4.36.0 compiler binary without relying on an elan proxy under env -i.

    Operator override: set ``ALETHEIA_LEAN_BIN`` to an explicit executable path.
    Otherwise, when ``lean`` on ``PATH`` is an ``elan`` proxy shim (``<elan>/bin/lean``),
    resolve directly to ``<elan>/toolchains/leanprover--lean4---v4.36.0/bin/lean`` (or query
    ``--print-prefix`` with ``LEAN_PATH``/``ELAN_TOOLCHAIN`` scrubbed) so invocation works
    even under ``env -i HOME=/nonexistent``.
    """
    override = os.environ.get("ALETHEIA_LEAN_BIN")
    if override:
        return override
    found = shutil.which("lean")
    if found is not None:
        found_path = Path(found)
        if found_path.parent.name == "bin":
            direct = _direct_toolchain_from_elan_root(found_path.parent.parent)
            if direct is not None:
                return direct
        probe_env = build_scrubbed_lean_env()
        elan_home = os.environ.get("ELAN_HOME")
        if elan_home and Path(elan_home).is_dir():
            probe_env["ELAN_HOME"] = elan_home
        try:
            pref = subprocess.run([found, "--print-prefix"], capture_output=True, text=True, env=probe_env, timeout=15, check=False)
            if pref.returncode == 0 and pref.stdout.strip():
                resolved = Path(pref.stdout.strip()) / "bin" / "lean"
                if resolved.is_file() and os.access(resolved, os.X_OK):
                    return str(resolved)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return found
    for root_str in (os.environ.get("ELAN_HOME", ""), os.path.join(os.environ.get("HOME", ""), ".elan") if os.environ.get("HOME") else ""):
        if root_str:
            direct = _direct_toolchain_from_elan_root(Path(root_str))
            if direct is not None:
                return direct
    raise CellOpLeanError("LEAN_BINARY_UNAVAILABLE", "lean not found on PATH")


def build_scrubbed_lean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k in _SAFE_LEAN_ENV_KEYS}


def verify_lean4_file_live(lean_path: Path = DEFAULT_LEAN_PATH, check_sha: bool = True) -> dict[str, Any]:
    raw = read_regular_bytes_capped(lean_path, "HoloSphereCellOpInvariants.lean")
    try:
        src = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CellOpLeanError("INVALID_UTF8", "Lean file is not valid UTF-8") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if check_sha:
        require_ok(sha == LEAN_SOURCE_SHA256, "LEAN_SHA_MISMATCH", f"expected {LEAN_SOURCE_SHA256}, got {sha}")

    static_info = audit_lean4_static(src)
    lean_bin = resolve_lean_binary()
    env = build_scrubbed_lean_env()
    try:
        ver_proc = subprocess.run([lean_bin, "--version"], capture_output=True, text=True, env=env, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CellOpLeanError("LEAN_EXEC_ERROR", f"cannot execute lean ({exc.__class__.__name__})") from exc
    require_ok(
        ver_proc.returncode == 0 and "4.36.0" in ver_proc.stdout,
        "LEAN_VERSION_MISMATCH",
        f"bad lean version (rc={ver_proc.returncode}): stdout={ver_proc.stdout!r} stderr={ver_proc.stderr!r}",
    )

    try:
        proc = subprocess.run([lean_bin, "--stdin"], input=src, capture_output=True, text=True, env=env, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CellOpLeanError("LEAN_EXEC_ERROR", f"cannot execute lean --stdin ({exc.__class__.__name__})") from exc
    require_ok("warning:" not in (proc.stdout + proc.stderr).lower(), "LEAN_WARNING_FORBIDDEN", "Lean emitted warning")
    require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean exited {proc.returncode}")
    require_ok(proc.stderr == "", "LEAN_STDERR_NONEMPTY", f"non-empty stderr: {proc.stderr!r}")
    axioms = parse_and_audit_lean_axioms(proc.stdout)
    return {
        "status": "LEAN_OK",
        "lean_toolchain": LEAN_TOOLCHAIN,
        "lean_version": ver_proc.stdout.strip().splitlines()[0],
        "lean_source_sha256": sha,
        "theorems_verified": len(axioms),
        "axioms": axioms,
        **static_info,
    }


# ---------------------------------------------------------------------------
# Exact Pure-Int Cross-Verification of Theorems #37-#40 + #40b
# ---------------------------------------------------------------------------

def _block_h4(u: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    u0, u1, u2, u3 = u
    return (u0 + u1 + u2 + u3, u0 - u1 + u2 - u3, u0 + u1 - u2 - u3, u0 - u1 - u2 + u3)


def _qmul(p: tuple[int, int, int, int], q: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    pw, px, py, pz = p
    qw, qx, qy, qz = q
    return (
        pw * qw - px * qx - py * qy - pz * qz,
        pw * qx + px * qw + py * qz - pz * qy,
        pw * qy - px * qz + py * qw + pz * qx,
        pw * qz + px * qy - py * qx + pz * qw,
    )


def _so3_adj(q: tuple[int, int, int, int]) -> tuple[int, ...]:
    w, x, y, z = q
    return (
        w * w + x * x - y * y - z * z, 2 * (x * y - w * z), 2 * (x * z + w * y),
        2 * (x * y + w * z), w * w - x * x + y * y - z * z, 2 * (y * z - w * x),
        2 * (x * z - w * y), 2 * (y * z + w * x), w * w - x * x - y * y + z * z,
    )


def verify_algebraic_witnesses() -> dict[str, Any]:
    # 1. Exhaustive [-8, 7]^4 = 65,536 Block-H4 check (#37)
    min_r = 10**9
    max_r = -(10**9)
    for u0 in range(-8, 8):
        for u1 in range(-8, 8):
            for u2 in range(-8, 8):
                for u3 in range(-8, 8):
                    u = (u0, u1, u2, u3)
                    r = _block_h4(u)
                    rr = _block_h4(r)
                    require_ok(rr == (4 * u0, 4 * u1, 4 * u2, 4 * u3), "H4_INVOL_FAIL", "H4^2 != 4*I")
                    for c in r:
                        if c < min_r:
                            min_r = c
                        if c > max_r:
                            max_r = c
    require_ok((min_r, max_r) == (-32, 30), "H4_BOUNDS_MISMATCH", f"got {(min_r, max_r)}")

    # 2. Rational Cayley unit-sphere involution (#38) & exact inverse (#39)
    for wx, wy, wz, d in ((1, 0, 0, 1), (3, 4, 0, 5), (1, 2, 2, 3), (-2, 3, 6, 7)):
        nsq = wx * wx + wy * wy + wz * wz
        require_ok(nsq == d * d, "BAD_UNIT_WITNESS", "not unit sphere")
        q_pos = (d * d - nsq, 2 * d * wx, 2 * d * wy, 2 * d * wz)
        q_neg = (d * d - nsq, -2 * d * wx, -2 * d * wy, -2 * d * wz)
        require_ok(q_pos[0] == 0, "CAYLEY_SCALAR_NONZERO", "unit sphere must have scalar 0")
        require_ok(_qmul(q_pos, q_pos) == (-(4 * (d * d) * (d * d)), 0, 0, 0), "CAYLEY_SQ_FAIL", "bad involution square")
        den_sq = (d * d + nsq) ** 2
        require_ok(_qmul(q_pos, q_neg) == (den_sq, 0, 0, 0), "CAYLEY_INV_FAIL", "bad inverse")
        require_ok(_so3_adj(tuple(-c for c in q_pos)) == _so3_adj(q_pos), "SO3_EVEN_FAIL", "R(-q) != R(q)")

    # 3. Exhaustive 256x256 H_256 + Maiorana-McFarland bent4 check (#40 & #40b)
    walsh_rows: list[list[int]] = []
    bent_rows: list[list[int]] = []
    bent_signs = [(-1) ** ((((d & 3) & ((d >> 2) & 3)).bit_count()) & 1) for d in range(256)]
    for b in range(256):
        w_row = [(-1) ** ((b & d).bit_count()) for d in range(256)]
        b_row = [bent_signs[d] * w_row[d] for d in range(256)]
        walsh_rows.append(w_row)
        bent_rows.append(b_row)

    const_warps_bent = 0
    for b1 in range(256):
        r1 = walsh_rows[b1]
        br1 = bent_rows[b1]
        for w_idx in range(8):
            w_sum = sum(br1[w_idx * 32:(w_idx + 1) * 32])
            if abs(w_sum) == 32:
                const_warps_bent += 1
        for b2 in range(b1, 256):
            r2 = walsh_rows[b2]
            br2 = bent_rows[b2]
            dot_w = sum(x * y for x, y in zip(r1, r2))
            dot_b = sum(x * y for x, y in zip(br1, br2))
            expected = 256 if b1 == b2 else 0
            require_ok(dot_w == expected and dot_b == expected, "H256_ORTHO_FAIL", f"pair {(b1, b2)}")
    require_ok(const_warps_bent == 0, "BENT_CONST_WARP_NONZERO", f"got {const_warps_bent}")
    return {
        "blockh4_exhaustive_vectors": 65536,
        "blockh4_tight_range": [min_r, max_r],
        "h256_pairs_checked": 256 * 257 // 2,
        "bent4_const_warps_of_2048": const_warps_bent,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    json_out = False
    verify_lean = False
    for a in args:
        if a == "--json":
            json_out = True
        elif a in ("--verify-lean", "--check"):
            verify_lean = True
        else:
            sys.stderr.write(f"[UNKNOWN_FLAG] unknown flag: {a}\n")
            return 2
    try:
        alg = verify_algebraic_witnesses()
        lean_res = verify_lean4_file_live(DEFAULT_LEAN_PATH, check_sha=True) if (verify_lean or not args or args == ["--json"]) else {}
        report = {**lean_res, "status": "OK", "algebraic_witnesses": alg}
    except CellOpLeanError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if json_out:
        sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
    else:
        sys.stdout.write(
            f"CELLOP_LEAN_OK theorems={report['theorems_verified']} "
            f"sha256={report['lean_source_sha256']} "
            f"bent4_const_warps={alg['bent4_const_warps_of_2048']}/2048\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
