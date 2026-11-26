#!/usr/bin/env python3
"""Track S110 Stage 3 (H10c) Wave-10 Fail-Closed Verifier & R13b Lean 4.36.0 Gate.

Zero IEEE-754 floats, zero bare asserts, zero external dependencies.
Provides:
  - Hardened Zone-B file I/O (O_NOFOLLOW, size caps, 80-digit int/rational DoS cap, atomic 0o600 write)
  - R13b O(1) in_ident Lean 4 lexer + 18-rule static pre-filter + allowlist scrubbed lean --stdin
  - Field-complete secondary auditor (SEC) + FR0/FR1 envelope & replay verification
  - CLI: --check, --write, --verify-lean, --verify-pins, --json (fail-closed on unknown flags)
"""

from __future__ import annotations

import copy
from fractions import Fraction
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

TRACK_DIR = Path(__file__).resolve().parent
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import s110_geosphere_weft_oracle as oracle

DEFAULT_CERT_PATH = TRACK_DIR / "s110_geosphere_weft_certificate.json"
DEFAULT_LEAN_PATH = TRACK_DIR / oracle.LEAN_FILE_NAME

MAX_FILE_BYTES = 1_048_576
MAX_INT_DIGITS = 80
MAX_INT_BITS = 266
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_RAT_RE = re.compile(r"^-?[0-9]{1,80}(?:/[1-9][0-9]{0,79})?$")
_ENVELOPE_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_SAFE_LEAN_ENV_KEYS = frozenset({"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "TERM"})
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

# O(1) Lean 4 identifier character classes for Char-literal vs prime disambiguation (R13b)
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_LEAN4_ID_FIRST = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_LEAN4_ID_REST = _LEAN4_ID_FIRST | frozenset("0123456789'!?")

# 18-rule static Lean 4 pre-filter (applied to comment- and Char-stripped source)
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
    ("R18_ROOT_SORRYAX", re.compile(r"\b_root_\.sorryAx\b")),
)

_LEAN4_PRINT_LINE_RE = re.compile(r"(?m)^\s*#print\b.*$")
_LEAN4_VALID_PRINT_RE = re.compile(r"^#print\s+axioms\s+(GeosphereWeftConservation\.[A-Za-z0-9_]+)$")
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'(GeosphereWeftConservation\.[A-Za-z0-9_]+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'(GeosphereWeftConservation\.[A-Za-z0-9_]+)' depends on axioms: \[([^\]]*)\]$")

_EXPECTED_PAYLOAD_CACHE: dict[str, Any] | None = None


class S110Error(ValueError):
    """Typed fail-closed error for Track S110 verifier."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise S110Error(code, message)


def _expected_payload_ref() -> dict[str, Any]:
    global _EXPECTED_PAYLOAD_CACHE
    if _EXPECTED_PAYLOAD_CACHE is None:
        _EXPECTED_PAYLOAD_CACHE = oracle.build_payload()
    return _EXPECTED_PAYLOAD_CACHE


def expected_payload() -> dict[str, Any]:
    return copy.deepcopy(_expected_payload_ref())


# ---------------------------------------------------------------------------
# Hardened Zone-B regular-file I/O and strict JSON loader
# ---------------------------------------------------------------------------

def _reject_symlink_ancestors(path: Path, label: str) -> None:
    cur = Path(os.path.abspath(os.fspath(path)))
    for candidate in (cur, *cur.parents):
        if candidate.is_symlink():
            raise S110Error("SYMLINK_FORBIDDEN", f"{label}: symlink path or ancestor forbidden")


def read_regular_bytes_capped(path: Path, label: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    _reject_symlink_ancestors(path, label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(os.fspath(path), flags)
    except OSError as exc:
        raise S110Error("IO_OPEN_FAIL", f"{label}: cannot open regular file ({exc.__class__.__name__})") from exc
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


def write_atomic_0600(path: Path, data: bytes) -> None:
    parent = path.parent
    require_ok(parent.is_dir(), "IO_WRITE_FAIL", "parent directory missing")
    fd, tmp_name = tempfile.mkstemp(prefix=".s110_tmp_", dir=os.fspath(parent))
    tmp_path = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(os.fspath(tmp_path), os.fspath(path))
    except OSError as exc:
        if fd >= 0:
            os.close(fd)
        if tmp_path.exists():
            tmp_path.unlink()
        raise S110Error("IO_WRITE_FAIL", f"atomic write failed ({exc.__class__.__name__})") from exc


def _reject_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def _reject_float(tok: str) -> Any:
    raise S110Error("FLOAT_FORBIDDEN", f"float literal forbidden: {tok}")


def _reject_const(tok: str) -> Any:
    raise S110Error("NON_FINITE_FORBIDDEN", f"non-finite JSON constant forbidden: {tok}")


def _parse_int_capped(tok: str) -> int:
    digits = tok[1:] if tok.startswith("-") else tok
    require_ok(len(digits) <= MAX_INT_DIGITS, "INT_DIGIT_LIMIT", "integer exceeds 80-digit cap")
    return int(tok)


def loads_json_strict(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise S110Error("INVALID_UTF8", f"{label}: invalid UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_dup_keys,
            parse_float=_reject_float,
            parse_constant=_reject_const,
            parse_int=_parse_int_capped,
        )
    except S110Error:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S110Error("INVALID_JSON", f"{label}: malformed JSON ({exc.__class__.__name__})") from exc


# ---------------------------------------------------------------------------
# R13b O(1) in_ident Lean 4 lexer + 18-rule static pre-filter + live Lean
# ---------------------------------------------------------------------------

def _match_lean4_char_literal_end(src: str, i: int, n: int) -> int | None:
    if i + 2 < n:
        ch1 = src[i + 1]
        if ch1 not in ("\\", "'"):
            if src[i + 2] == "'":
                return i + 3
    if i + 3 < n:
        if src[i + 1] == "\\":
            if src[i + 3] == "'":
                if src[i + 2] != "\n":
                    return i + 4
            esc = src[i + 2]
            if esc == "x":
                if i + 5 < n:
                    if src[i + 5] == "'":
                        if all(c in _HEX_DIGITS for c in src[i + 3 : i + 5]):
                            return i + 6
            if esc == "u":
                if i + 7 < n:
                    if src[i + 7] == "'":
                        if all(c in _HEX_DIGITS for c in src[i + 3 : i + 7]):
                            return i + 8
    return None


def strip_lean4_source(src: str) -> str:
    """Strip -- and nested /- -/ comments plus Char literals via O(1) in_ident state machine."""
    out: list[str] = []
    i = 0
    n = len(src)
    depth = 0
    in_ident = False
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
        if ch == "/" and nxt == "-":
            in_ident = False
            depth = 1
            out.append("  ")
            i += 2
            continue
        if ch == "-" and nxt == "-":
            in_ident = False
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "'" and not in_ident:
            cend = _match_lean4_char_literal_end(src, i, n)
            if cend is not None:
                out.append(" \n " if src[i + 1] == "\n" else " " * (cend - i))
                i = cend
                continue
        in_ident = (ch in _LEAN4_ID_REST) if in_ident else (ch in _LEAN4_ID_FIRST)
        out.append(ch)
        i += 1
    require_ok(depth == 0, "LEAN4_UNTERMINATED_COMMENT", "unclosed /- block comment")
    return "".join(out)


def lean4_rule_hits(src: str) -> list[str]:
    stripped = strip_lean4_source(src)
    return [rid for rid, rx in LEAN4_RULES if rx.search(stripped) is not None]


def static_gate_lean4_source(src: str) -> None:
    require_ok("\r" not in src, "LEAN4_BAD_CHARS", "CR forbidden in Lean source")
    require_ok("\x00" not in src, "LEAN4_BAD_CHARS", "NUL forbidden in Lean source")
    hits = lean4_rule_hits(src)
    require_ok(hits == [], "LEAN4_TRUST_ESCAPE", f"banned Lean construct(s): {hits}")
    stripped = strip_lean4_source(src)
    seen: list[str] = []
    for pm in _LEAN4_PRINT_LINE_RE.finditer(stripped):
        vm = _LEAN4_VALID_PRINT_RE.match(pm.group(0).strip())
        require_ok(vm is not None, "LEAN4_BAD_PRINT", f"disallowed #print: {pm.group(0)[:80]!r}")
        seen.append(vm.group(1))
    require_ok(seen == list(oracle.LEAN_THEOREM_NAMES), "LEAN4_PRINT_SET_MISMATCH", "#print axioms mismatch")
    for short in oracle.LEAN_THEOREM_SHORT_NAMES:
        require_ok(
            re.search(rf"(?m)^theorem\s+{re.escape(short)}\b", stripped) is not None,
            "LEAN4_MISSING_THEOREM",
            f"missing theorem {short}",
        )


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN", "")
    if env_bin != "":
        require_ok(os.path.isfile(env_bin), "LEAN_BINARY_NOT_FILE", "ALETHEIA_LEAN_BIN is not a file")
        require_ok(os.access(env_bin, os.X_OK), "LEAN_BINARY_NOT_EXECUTABLE", "ALETHEIA_LEAN_BIN not executable")
        return env_bin
    found = shutil.which("lean")
    require_ok(found is not None, "LEAN_BINARY_UNAVAILABLE", "lean not found on PATH")
    return str(found)


def scrubbed_lean_env() -> dict[str, str]:
    """Allowlist env for live Lean subprocess: drops LEAN_*, ELAN_*, LAKE_*, LD_*, DYLD_*."""
    return {k: v for k, v in os.environ.items() if k in _SAFE_LEAN_ENV_KEYS}


def parse_lean_axiom_output(stdout: str) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    idx = 0
    while idx < len(lines):
        ln = lines[idx]
        idx += 1
        while "depends on axioms: [" in ln and not ln.endswith("]") and idx < len(lines):
            ln = ln + " " + lines[idx]
            idx += 1
        m_none = _LEAN4_AXIOM_NONE_RE.match(ln)
        m_dep = _LEAN4_AXIOM_DEP_RE.match(ln)
        require_ok(m_none is not None or m_dep is not None, "LEAN_UNEXPECTED_STDOUT", f"unexpected line: {ln[:80]!r}")
        m = m_none if m_none is not None else m_dep
        tname = m.group(1)
        require_ok(tname not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate {tname}")
        axs = [] if m_dep is None else [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        for ax in axs:
            require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"forbidden axiom {ax}")
        seen[tname] = axs
    require_ok(frozenset(seen) == frozenset(oracle.LEAN_THEOREM_NAMES), "LEAN_THEOREM_SET_MISMATCH", "axiom set mismatch")
    return seen


def verify_lean4_file_live(lean_path: Path, *, check_sha: bool = True) -> dict[str, Any]:
    raw = read_regular_bytes_capped(lean_path, "lean_source")
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise S110Error("INVALID_UTF8", "Lean file invalid UTF-8") from exc
    static_gate_lean4_source(src)
    src_sha = oracle.sha256_hex(raw)
    if check_sha:
        require_ok(src_sha == oracle.LEAN_SOURCE_SHA256, "LEAN_SHA_MISMATCH", "Lean source SHA-256 mismatch")
    lean_bin = resolve_lean_binary()
    env = scrubbed_lean_env()
    try:
        v_proc = subprocess.run([lean_bin, "--version"], capture_output=True, text=True, timeout=60, check=False, env=env)
        proc = subprocess.run([lean_bin, "--stdin"], input=src, capture_output=True, text=True, timeout=300, check=False, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        raise S110Error("LEAN_EXEC_ERROR", f"lean execution failed: {exc.__class__.__name__}") from exc
    require_ok(v_proc.returncode == 0, "LEAN_VERSION_MISMATCH", "lean --version failed")
    require_ok("version 4.36.0," in v_proc.stdout, "LEAN_VERSION_MISMATCH", "expected Lean 4.36.0")
    require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    require_ok(proc.stderr == "", "LEAN_STDERR_NONEMPTY", "lean stderr non-empty")
    require_ok("warning" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning emitted")
    seen = parse_lean_axiom_output(proc.stdout)
    return {
        "lean_version": v_proc.stdout.strip().splitlines()[0],
        "theorems_verified": len(seen),
        "lean_source_sha256": src_sha,
    }


# ---------------------------------------------------------------------------
# Field-complete secondary auditor (SEC; enforced on SEC, FR0, and FR1)
# ---------------------------------------------------------------------------

def strict_shape_match(a: Any, b: Any) -> str:
    stack: list[tuple[Any, Any, str]] = [(a, b, "payload")]
    while stack:
        x, y, path = stack.pop()
        if type(x) is not type(y):
            return path
        if type(x) is dict:
            if frozenset(x) != frozenset(y):
                return path
            for k in x:
                stack.append((x[k], y[k], f"{path}.{k}"))
        elif type(x) is list:
            if len(x) != len(y):
                return path
            for i, (xi, yi) in enumerate(zip(x, y)):
                stack.append((xi, yi, f"{path}[{i}]"))
    return ""


def strict_deep_equal(a: Any, b: Any) -> str:
    stack: list[tuple[Any, Any, str]] = [(a, b, "payload")]
    while stack:
        x, y, path = stack.pop()
        if type(x) is not type(y):
            return path
        if type(x) is dict:
            if frozenset(x) != frozenset(y):
                return path
            for k in x:
                stack.append((x[k], y[k], f"{path}.{k}"))
        elif type(x) is list:
            if len(x) != len(y):
                return path
            for i, (xi, yi) in enumerate(zip(x, y)):
                stack.append((xi, yi, f"{path}[{i}]"))
        elif x != y:
            return path
    return ""


def parse_capped_rational(val: Any, label: str) -> Fraction:
    require_ok(type(val) is str, "INVALID_RATIONAL_STR", f"{label}: must be str")
    require_ok(_RAT_RE.fullmatch(val) is not None, "INVALID_RATIONAL_STR", f"{label}: invalid rational")
    return Fraction(val)


def _independent_semantics(p: dict[str, Any]) -> None:
    """Zero-shared-code algebraic checks over all 4 pillars before leaf-complete match."""
    require_ok(p["novelty_grade"] == "N1", "SEC_NOVELTY", "novelty must be N1")
    require_ok(p["n2_claims"] == 0, "SEC_N2_ZERO", "n2_claims must be 0")
    lc = p["lean_companion"]
    require_ok(lc["named_theorem_count"] == 38, "SEC_LEAN_CNT", "38 named theorems required")
    require_ok(
        lc["named_theorem_count"] + lc["helper_theorem_count"] == lc["total_theorem_declarations"],
        "SEC_LEAN_TOTAL",
        "theorem declaration sum mismatch",
    )
    p1 = p["pillar1_geodynamo_cayley"]
    require_ok(parse_capped_rational(p1["rank2_skew_d8"]["lorentz_radial_work_q"], "work8") == 0, "SEC_P1_WORK", "work=0")
    b2 = p1["block2x2_cayley_d8"]
    require_ok(
        parse_capped_rational(b2["norm_sq_in_q"], "n8in") == parse_capped_rational(b2["norm_sq_out_q"], "n8out"),
        "SEC_P1_CAY2",
        "2x2 Cayley norm",
    )
    h4 = p1["hopf_quat_cayley_d4"]
    require_ok(
        parse_capped_rational(h4["norm_sq_in_q"], "n4in") == parse_capped_rational(h4["norm_sq_out_q"], "n4out"),
        "SEC_P1_CAY4",
        "4D Cayley norm",
    )
    pf = p1["pfaffian_4d_invertibility"]
    a, b, c, d, e, f = pf["skew_entries_abcdef"]
    expected_det = 1 + a * a + b * b + c * c + d * d + e * e + f * f + (a * f - b * e + c * d) ** 2
    require_ok(parse_capped_rational(pf["det_I_plus_skew_q"], "det4") == expected_det, "SEC_P1_DET4", "det4 Pfaffian")

    p2 = p["pillar2_oceanic_and_darcy"]
    oc = p2["bidirectional_birkhoff_d4"]
    require_ok(
        parse_capped_rational(oc["mass_in_q"], "min") == parse_capped_rational(oc["mass_out_q"], "mout"),
        "SEC_P2_MASS",
        "mass conservation",
    )
    require_ok(p2["b1_causal_sinkhorn_obstruction"]["forced_identity"] is True, "SEC_P2_B1", "B1 identity")
    d2 = p2["discovery2_so2_birkhoff_non_commutation"]
    require_ok(parse_capped_rational(d2["commutator_frob_sq_q"], "comm") > 0, "SEC_P2_COMM", "QT!=TQ")
    dc = p2["darcy_aquifer_contraction"]
    alpha = parse_capped_rational(dc["alpha_q"], "alpha")
    ns_s = parse_capped_rational(dc["norm_sq_s_q"], "ns_s")
    ns_k = parse_capped_rational(dc["norm_sq_k_q"], "ns_k")
    ns_n = parse_capped_rational(dc["norm_sq_next_q"], "ns_n")
    res = parse_capped_rational(dc["parallelogram_residual_q"], "para_res")
    require_ok(ns_n + res == (1 - alpha) * ns_s + alpha * ns_k, "SEC_P2_PARA", "Darcy parallelogram")
    require_ok(
        parse_capped_rational(p2["m1_unbounded_K_obstruction"]["post_state_q"], "m1") > 1,
        "SEC_P2_M1",
        "M1 escapes bound",
    )

    p3 = p["pillar3_bingham_poloidal_and_ozone"]
    require_ok(p3["bingham_y_phase_sweep"][-1]["is_stagnant_lid_zero"] is True, "SEC_P3_STAG", "Y=1 zero")
    require_ok(parse_capped_rational(p3["b5_sigma_obstruction"]["leaked_output_q"], "b5") != 0, "SEC_P3_B5", "B5 leak")
    s50 = p3["s50_commutator_obstruction"]
    require_ok(
        parse_capped_rational(s50["bingham_of_sum_q"], "s50l") != parse_capped_rational(s50["sum_of_bingham_q"], "s50r"),
        "SEC_P3_S50",
        "S50 commutator",
    )
    pol = p3["discovery3_poloidal_bingham_S_YH"]
    require_ok(parse_capped_rational(pol["pol_tor_dot_q"], "poldot") == 0, "SEC_P3_ORTH", "Pol/Tor orth")
    require_ok(pol["so4_equivariant_exact"] is True, "SEC_P3_EQUIV", "SO4 fixed-gain linearity")
    require_ok(pol["so4_check_kind"].startswith("fixed-gain linearity"), "SEC_P3_EQUIV_KIND", "SO4 check kind must be honestly labelled")
    oz = p3["ozone_channel2b_airlock"]
    adv = parse_capped_rational(oz["advection_sq_q"], "adv")
    b1 = parse_capped_rational(oz["bound_b1_q"], "b1")
    b2 = parse_capped_rational(oz["bound_b2_q"], "b2")
    require_ok(adv <= b1, "SEC_P3_OZ1", "airlock bound")
    require_ok(b1 <= b2, "SEC_P3_OZ2", "airlock monotone")

    p4 = p["pillar4_weft_smith_triple_gate"]
    hh = p4["householder_crow_invariance"]
    require_ok(
        parse_capped_rational(hh["c_row_before_q"], "cr0") == parse_capped_rational(hh["c_row_after_q"], "cr1"),
        "SEC_P4_CROW",
        "C_row invariance",
    )
    require_ok(
        parse_capped_rational(hh["c_row_after_q"], "cr1") <= parse_capped_rational(hh["c_max_q"], "cmax"),
        "SEC_P4_DPI",
        "C_row <= C_max",
    )
    cc = p4["crow_cancellation_obstruction"]
    require_ok(
        parse_capped_rational(cc["c_row_composed_q"], "cc_comp") > parse_capped_rational(cc["c_row_patch1_q"], "cc_p1"),
        "SEC_P4_CANCEL",
        "composed C_row bypasses per-patch cap",
    )
    sim = p4["h11c_50cycle_simulation"]
    require_ok(sim["clean_committed"] + sim["poisoned_injected"] == sim["cycles_total"], "SEC_P4_CYCLES", "50 cycles")
    require_ok(
        Fraction(sim["poisoned_rejected_and_rolled_back"], sim["poisoned_injected"]) >= Fraction(9, 10),
        "SEC_P4_CATCH",
        "90% catch gate",
    )
    require_ok(sim["anchor_err_final"] <= sim["anchor_err_initial"], "SEC_P4_MONO", "anchor monotone")
    require_ok(sim["cum_norm_sq_final"] <= sim["cum_cap_sq"], "SEC_P4_CUM", "cumulative drift cap")
    require_ok(sim["h11c_simulation_kind"].startswith("scripted-illustration"), "SEC_P4_SIMKIND", "H11c simulation must be labelled scripted-illustration")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be dict")
    exp = _expected_payload_ref()
    shape_bad = strict_shape_match(payload, exp)
    require_ok(shape_bad == "", "SCHEMA_SHAPE_MISMATCH", f"schema/type mismatch at {shape_bad}")
    _independent_semantics(payload)
    diff_path = strict_deep_equal(payload, exp)
    require_ok(diff_path == "", "SEMANTIC_VALUE_MISMATCH", f"payload mismatch at {diff_path}")
    return {"status": "OK"}


def _validate_exact_json_tree(obj: Any) -> None:
    """Iterative pre-hash tree validator: blocks subclasses, floats, LyingSequence, and >80-digit ints."""
    stack: list[Any] = [obj]
    while stack:
        cur = stack.pop()
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                require_ok(type(k) is str, "INVALID_JSON_KEY", "dict key must be exact str")
                stack.append(v)
        elif t is list:
            stack.extend(cur)
        elif t is int:
            require_ok(cur.bit_length() <= MAX_INT_BITS, "INT_DIGIT_LIMIT", "integer exceeds bit limit")
        elif t is str or t is bool:
            continue
        else:
            raise S110Error("INVALID_JSON_TYPE", f"forbidden value type: {t.__name__}")


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    require_ok(type(cert) is dict, "INVALID_ENVELOPE_TYPE", "certificate must be JSON object")
    require_ok(frozenset(cert) == _ENVELOPE_KEYS, "INVALID_ENVELOPE_KEYS", "unexpected envelope keys")
    require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_VERSION_MISMATCH", "schema_version mismatch")
    require_ok(cert["track_id"] == oracle.TRACK_ID, "TRACK_ID_MISMATCH", "track_id mismatch")
    payload_sha = cert["payload_sha256"]
    cert_sha = cert["certificate_sha256"]
    require_ok(type(payload_sha) is str, "INVALID_HASH", "payload_sha256 must be str")
    require_ok(_HEX64_RE.fullmatch(payload_sha) is not None, "INVALID_HASH", "payload_sha256 bad hex")
    require_ok(type(cert_sha) is str, "INVALID_HASH", "certificate_sha256 must be str")
    require_ok(_HEX64_RE.fullmatch(cert_sha) is not None, "INVALID_HASH", "certificate_sha256 bad hex")
    payload = cert["payload"]
    require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be dict")
    _validate_exact_json_tree(payload)
    computed_psha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    require_ok(computed_psha == payload_sha, "PAYLOAD_HASH_MISMATCH", "payload_sha256 mismatch")
    env_obj = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": payload_sha,
    }
    computed_csha = oracle.sha256_hex(oracle.canonical_json_bytes(env_obj))
    require_ok(computed_csha == cert_sha, "CERT_HASH_MISMATCH", "certificate_sha256 mismatch")
    if full_replay:
        fresh = oracle.build_payload()
        replay_bad = strict_deep_equal(payload, fresh)
        require_ok(replay_bad == "", "REPLAY_MISMATCH", f"live replay mismatch at {replay_bad}")
    secondary_audit_payload(payload)
    return {
        "status": "OK",
        "track_id": oracle.TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "full_replay": full_replay,
    }


def verify_certificate_file(cert_path: Path, *, full_replay: bool = True) -> dict[str, Any]:
    raw = read_regular_bytes_capped(cert_path, "certificate")
    cert = loads_json_strict(raw, "certificate")
    res = verify_certificate_dict(cert, full_replay=full_replay)
    require_ok(raw == oracle.canonical_json_bytes(cert) + b"\n", "NON_CANONICAL_BYTES", "certificate bytes must be canonical JSON + LF")
    return res


def verify_external_pins(root_dir: Path | None = None) -> dict[str, Any]:
    """Re-hash shipped prereg pins when present; pins whose files are not shipped are
    reported as unverifiable external-historical pins (never silently skipped)."""
    base = TRACK_DIR.parent if root_dir is None else root_dir
    checked: list[dict[str, str]] = []
    unverifiable: list[dict[str, str]] = []
    for pid, rel, expected_sha in oracle.EXTERNAL_PROTOCOL_PINS:
        p = base / rel
        if not p.is_file():
            unverifiable.append({"id": pid, "rel_path": rel, "sha256": expected_sha,
                                 "status": "external-historical (file not shipped; no repo@sha named)"})
            continue
        raw = read_regular_bytes_capped(p, pid)
        actual = oracle.sha256_hex(raw)
        require_ok(actual == expected_sha, "PIN_SHA_MISMATCH", f"{pid}: SHA mismatch")
        checked.append({"id": pid, "sha256": actual})
    return {
        "status": "PINS_OK" if not unverifiable else "PINS_PARTIAL_UNVERIFIABLE",
        "external": len(checked),
        "unverifiable": unverifiable,
        "pins": checked,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = False
    mode = ""
    target: Path | None = None
    i = 0
    try:
        while i < len(args):
            tok = args[i]
            if tok == "--json":
                as_json = True
                i += 1
            elif tok in ("--check", "--write", "--verify-lean", "--verify-pins"):
                require_ok(mode == "", "CONFLICTING_FLAGS", f"duplicate mode flag {tok}")
                mode = tok
                i += 1
                if i < len(args):
                    if not args[i].startswith("--"):
                        target = Path(args[i])
                        i += 1
            else:
                raise S110Error("UNKNOWN_FLAG", f"unrecognized argument: {tok}")
        if mode == "":
            mode = "--check"
        if mode == "--write":
            out_path = DEFAULT_CERT_PATH if target is None else target
            cert = oracle.build_certificate()
            data = oracle.canonical_json_bytes(cert) + b"\n"
            write_atomic_0600(out_path, data)
            res = {
                "status": "WRITTEN",
                "track_id": oracle.TRACK_ID,
                "certificate_sha256": cert["certificate_sha256"],
                "payload_sha256": cert["payload_sha256"],
            }
        elif mode == "--check":
            cert_path = DEFAULT_CERT_PATH if target is None else target
            res = verify_certificate_file(cert_path, full_replay=True)
        elif mode == "--verify-lean":
            lean_path = DEFAULT_LEAN_PATH if target is None else target
            res = verify_lean4_file_live(lean_path, check_sha=True)
        else:
            res = verify_external_pins(target)
        if as_json:
            sys.stdout.write(json.dumps(res, sort_keys=True) + "\n")
        elif mode == "--verify-pins":
            sys.stdout.write(f"{res['status']} external={res['external']} unverifiable={len(res.get('unverifiable', []))}\n")
        elif mode == "--verify-lean":
            sys.stdout.write(f"LEAN_OK theorems={res['theorems_verified']} sha256={res['lean_source_sha256']}\n")
        else:
            sys.stdout.write(f"OK {res['track_id']} cert_sha256={res['certificate_sha256']}\n")
        return 0
    except S110Error as exc:
        sys.stderr.write(f"ERROR {exc.code}: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
