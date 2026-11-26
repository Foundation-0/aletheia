#!/usr/bin/env python3
"""Track S112 Wave-10 Fail-Closed Verifier & R13b Lean 4.36.0 Gate.

Zero IEEE-754 floats, zero bare asserts, zero external dependencies.
Provides:
  - Hardened Zone-B file I/O (O_NOFOLLOW, symlink ancestor rejection, streaming size cap,
    80-digit int/rational DoS cap, atomic 0o600 write)
  - R13b O(1) in_ident Lean 4 lexer + 18-rule static pre-filter + allowlist scrubbed lean --stdin
  - Field-complete secondary auditor (SEC) across all 5 Natural Systems Portals + FR0/FR1
  - CLI: --check (default on no-arg), --write, --verify-lean, --verify-pins, --json
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

import s112_natural_systems_oracle as oracle

DEFAULT_CERT_PATH = TRACK_DIR / "s112_natural_systems_certificate.json"
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
_LEAN4_VALID_PRINT_RE = re.compile(r"^#print\s+axioms\s+(NaturalSystemsConservation\.[A-Za-z0-9_]+)$")
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'(NaturalSystemsConservation\.[A-Za-z0-9_]+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'(NaturalSystemsConservation\.[A-Za-z0-9_]+)' depends on axioms: \[([^\]]*)\]$")

_EXPECTED_PAYLOAD_CACHE: dict[str, Any] | None = None


class S112Error(ValueError):
    """Typed fail-closed error for Track S112 verifier."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise S112Error(code, message)


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
            raise S112Error("SYMLINK_FORBIDDEN", f"{label}: symlink path or ancestor forbidden")


def read_regular_bytes_capped(path: Path, label: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    _reject_symlink_ancestors(path, label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(os.fspath(path), flags)
    except OSError as exc:
        raise S112Error("IO_OPEN_FAIL", f"{label}: cannot open regular file ({exc.__class__.__name__})") from exc
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
    fd, tmp_name = tempfile.mkstemp(prefix=".s112_tmp_", dir=os.fspath(parent))
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
        raise S112Error("IO_WRITE_FAIL", f"atomic write failed ({exc.__class__.__name__})") from exc


def _reject_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def _reject_float(tok: str) -> Any:
    raise S112Error("FLOAT_FORBIDDEN", f"float literal forbidden: {tok}")


def _reject_const(tok: str) -> Any:
    raise S112Error("NON_FINITE_FORBIDDEN", f"non-finite JSON constant forbidden: {tok}")


def _parse_int_capped(tok: str) -> int:
    digits = tok[1:] if tok.startswith("-") else tok
    require_ok(len(digits) <= MAX_INT_DIGITS, "INT_DIGIT_LIMIT", "integer exceeds 80-digit cap")
    return int(tok)


def loads_json_strict(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise S112Error("INVALID_UTF8", f"{label}: invalid UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_dup_keys,
            parse_float=_reject_float,
            parse_constant=_reject_const,
            parse_int=_parse_int_capped,
        )
    except S112Error:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S112Error("INVALID_JSON", f"{label}: malformed JSON ({exc.__class__.__name__})") from exc


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
        raise S112Error("INVALID_UTF8", "Lean file invalid UTF-8") from exc
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
        raise S112Error("LEAN_EXEC_ERROR", f"lean execution failed: {exc.__class__.__name__}") from exc
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
    """Zero-shared-code algebraic checks over all 5 Portals before leaf-complete match."""
    require_ok(p["novelty_grade"] == "N1", "SEC_NOVELTY", "novelty must be N1")
    require_ok(p["n2_claims"] == 0, "SEC_N2_ZERO", "n2_claims must be 0")
    lc = p["lean_companion"]
    require_ok(lc["named_theorem_count"] == 34, "SEC_LEAN_CNT", "34 named theorems required")
    require_ok(
        lc["named_theorem_count"] + lc["helper_theorem_count"] == lc["total_theorem_declarations"],
        "SEC_LEAN_TOTAL",
        "theorem declaration sum mismatch",
    )

    # Portal 1: Homeostasis & LIF
    p1 = p["portal1_homeostasis_and_lif"]
    mc = p1["mult_vs_bingham_crow"]
    c0 = parse_capped_rational(mc["c_row_initial_q"], "p1_c0")
    cmax = parse_capped_rational(mc["c_max_q"], "p1_cmax")
    cmult = parse_capped_rational(mc["c_row_mult_3_4_q"], "p1_cmult")
    cbing = parse_capped_rational(mc["c_row_bingham_tau3_q"], "p1_cbing")
    require_ok(c0 <= cmax, "SEC_P1_CMAX", "initial C_row <= C_max")
    require_ok(cmult == c0, "SEC_P1_MULT", "mult scaling preserves C_row")
    require_ok(cbing > cmax, "SEC_P1_BING", "Bingham breaches C_max")
    require_ok(
        parse_capped_rational(mc["bingham_of_sum_q"], "p1_bs") != parse_capped_rational(mc["sum_of_bingham_q"], "p1_sb"),
        "SEC_P1_NONADD",
        "Bingham non-additivity",
    )
    dm = p1["blockh4_and_dark_mode"]
    require_ok(parse_capped_rational(dm["comm_h4_aniso_frob_sq_q"], "p1_comm") > 0, "SEC_P1_H4COMM", "[H4,D]!=0")
    require_ok(parse_capped_rational(dm["isotropic_forgetting_sq_q"], "p1_iso") == 0, "SEC_P1_ISO", "0 base forgetting")
    require_ok(parse_capped_rational(dm["aniso_input_forgetting_sq_q"], "p1_aniso") > 0, "SEC_P1_ANISO", "aniso leak")
    sm = p1["safety_margin_and_cos_repair"]
    tau = parse_capped_rational(sm["yield_wall_tau_q"], "p1_tau")
    m_pre = parse_capped_rational(sm["margin_pre_q"], "p1_mpre")
    m_post = parse_capped_rational(sm["margin_post_q"], "p1_mpost")
    require_ok(m_pre > tau, "SEC_P1_MPRE", "pre-sleep margin > tau")
    require_ok(m_post < tau, "SEC_P1_MPOST", "post-sleep margin < tau")
    require_ok(m_post > 0, "SEC_P1_MSIGN", "post-sleep margin stays positive")
    require_ok(
        parse_capped_rational(sm["cos2_pre_q"], "p1_cos0") == parse_capped_rational(sm["cos2_post_q"], "p1_cos1"),
        "SEC_P1_COS",
        "cosine repair invariant",
    )
    ml = p1["malecns_and_lif_lyapunov"]
    require_ok(ml["malecns_e_synapses"] + ml["malecns_i_synapses"] == ml["malecns_total_synapses"], "SEC_P1_DALE", "Dale sum")
    s102 = s102_malecns_crosscheck()
    require_ok(
        ml["malecns_e_synapses"] == s102["e"]
        and ml["malecns_i_synapses"] == s102["i"]
        and ml["malecns_total_synapses"] == s102["total"]
        and ml["malecns_cx_net_balance"] == s102["cx"],
        "SEC_P1_DALE_S102",
        "MaleCNS constants must equal the sha256-pinned S102 certificate values",
    )
    require_ok(ml["lif_2step_nonzero_count"] + 1 == ml["lif_grid_states"], "SEC_P1_LIF_CNT", "LIF nonzero count")
    require_ok(ml["lif_2step_min_drop_nonzero"] > 0, "SEC_P1_LIF_DROP", "LIF strict 2-step drop")

    # Portal 2: Turing Morphogenesis
    p2 = p["portal2_turing_morphogenesis"]
    rj = p2["reaction_jacobian"]
    require_ok(parse_capped_rational(rj["tr_j_q"], "p2_tr") < 0, "SEC_P2_TR", "tr(J) < 0")
    require_ok(parse_capped_rational(rj["det_j_q"], "p2_det") > 0, "SEC_P2_DET", "det(J) > 0")
    require_ok(parse_capped_rational(rj["lin_turing_coeff_q"], "p2_lin") > 0, "SEC_P2_LIN", "dv*j11+du*j22 > 0")
    de = p2["dispersion_evaluations"]
    require_ok(parse_capped_rational(de["det_mu3_q"], "p2_d3") < 0, "SEC_P2_INSTAB", "mu=3 unstable")
    require_ok(parse_capped_rational(de["det_mu3_equal_diff_d1_q"], "p2_eqd") > 0, "SEC_P2_EQDIFF", "equal diff stable")
    ga = p2["graph_aliasing"]
    require_ok(ga["c4_unstable_mode_count"] == 0, "SEC_P2_C4", "C4 stable")
    require_ok(ga["c6_unstable_mode_count"] > 0, "SEC_P2_C6", "C6 unstable")

    # Portal 3: Beltrami / Helicity
    p3 = p["portal3_beltrami_helicity"]
    bc = p3["beltrami_cayley_conservation"]
    require_ok(parse_capped_rational(bc["comm_ck_frob_sq_q"], "p3_comm") == 0, "SEC_P3_COMM", "[C,K]=0")
    require_ok(
        parse_capped_rational(bc["energy_in_q"], "p3_e0") == parse_capped_rational(bc["energy_comm_out_q"], "p3_e1"),
        "SEC_P3_ENERGY",
        "Cayley E conserved",
    )
    require_ok(
        parse_capped_rational(bc["helicity_in_q"], "p3_h0") == parse_capped_rational(bc["helicity_comm_out_q"], "p3_h1"),
        "SEC_P3_HELICITY",
        "Cayley H conserved",
    )
    require_ok(
        parse_capped_rational(bc["moment2_in_q"], "p3_m20") == parse_capped_rational(bc["moment2_comm_out_q"], "p3_m21"),
        "SEC_P3_MOMENT2",
        "Cayley m2 conserved",
    )
    ob3 = p3["obstructions_o3_2_and_o3_5"]
    require_ok(
        parse_capped_rational(ob3["energy_noncomm_out_q"], "p3_enc") == parse_capped_rational(bc["energy_in_q"], "p3_e0"),
        "SEC_P3_NONCOMM_E",
        "non-commuting E conserved",
    )
    require_ok(
        parse_capped_rational(ob3["helicity_noncomm_out_q"], "p3_hnc") != parse_capped_rational(bc["helicity_in_q"], "p3_h0"),
        "SEC_P3_NONCOMM_H",
        "non-commuting H drifts",
    )
    require_ok(
        parse_capped_rational(ob3["parity_helicity_q"], "p3_par") == -parse_capped_rational(bc["helicity_in_q"], "p3_h0"),
        "SEC_P3_PARITY",
        "H(Pv) = -H(v)",
    )
    require_ok(
        parse_capped_rational(ob3["rayleigh_after_sym_res_q"], "p3_r1") > parse_capped_rational(ob3["rayleigh_before_q"], "p3_r0"),
        "SEC_P3_RAYLEIGH",
        "symmetric residual raises H/E",
    )

    # Portal 4: Murray, Schur-Thomson, Physarum & Braess
    p4 = p["portal4_murray_physarum_schur"]
    pm = p4["plato_murray_trifurcation"]
    require_ok(
        parse_capped_rational(pm["total_cost_q"], "p4_m") + parse_capped_rational(pm["sos_excess_u50_q"], "p4_ex")
        == parse_capped_rational(pm["area_law_total_cost_q"], "p4_a"),
        "SEC_P4_MURRAY",
        "Murray SOS excess exact",
    )
    st4 = p4["schur_thomson_5node"]
    require_ok(
        parse_capped_rational(st4["g_eff_schur_q"], "p4_g") * parse_capped_rational(st4["r_eff_schur_q"], "p4_r") == 1,
        "SEC_P4_SCHUR_INV",
        "G_eff * R_eff = 1",
    )
    require_ok(
        parse_capped_rational(st4["thomson_power_full_q"], "p4_pf") + parse_capped_rational(st4["thomson_excess_q"], "p4_px")
        == parse_capped_rational(st4["thomson_power_perturbed_q"], "p4_pt"),
        "SEC_P4_THOMSON",
        "Thomson excess exact",
    )
    require_ok(parse_capped_rational(st4["foster_sum_q"], "p4_fos") == 4, "SEC_P4_FOSTER", "Foster sum = 4")
    ph = p4["physarum_hysteresis"]
    require_ok(
        parse_capped_rational(ph["gamma1_ratio_step3_q"], "p4_g1") > parse_capped_rational(ph["gamma1_ratio_init_q"], "p4_g10"),
        "SEC_P4_PHYS_G1",
        "gamma=1 ratio increases",
    )
    require_ok(
        parse_capped_rational(ph["gamma2_ratio_step2_q"], "p4_g2") < parse_capped_rational(ph["gamma2_ratio_init_q"], "p4_g20"),
        "SEC_P4_PHYS_G2",
        "gamma=2 above separatrix decreases",
    )
    rb = p4["rayleigh_vs_braess_and_portal_b"]
    require_ok(
        parse_capped_rational(rb["ohmic_r_eff_post_q"], "p4_op") < parse_capped_rational(rb["ohmic_r_eff_pre_q"], "p4_o0"),
        "SEC_P4_RAYLEIGH",
        "Ohmic R_eff decreases",
    )
    require_ok(
        parse_capped_rational(rb["wardrop_latency_post_q"], "p4_wp") > parse_capped_rational(rb["wardrop_latency_pre_q"], "p4_w0"),
        "SEC_P4_BRAESS",
        "Wardrop latency increases",
    )
    require_ok(
        Fraction(rb["portal_b_min_edges"], rb["portal_b_tree_edges"])
        == parse_capped_rational(rb["portal_b_density_chasm_q"], "p4_pb"),
        "SEC_P4_PORTALB",
        "Portal-B density chasm",
    )

    # Portal 5: Darboux, SUSY, Sylvester Lapse & Hopf
    p5 = p["portal5_darboux_lapse_hopf"]
    db = p5["darboux_rectangular_3x5"]
    require_ok(parse_capped_rational(db["intertwine_diff_sq_q"], "p5_int") == 0, "SEC_P5_INTERTWINE", "A L1 = L2 A")
    require_ok(
        parse_capped_rational(db["av_norm_sq_q"], "p5_avn")
        == (parse_capped_rational(db["vis_eigenvalue_q"], "p5_lam") - parse_capped_rational(db["shift_c_q"], "p5_c"))
        * parse_capped_rational(db["vis_norm_sq_q"], "p5_vn"),
        "SEC_P5_NORM",
        "|Av|^2 = (lam - c)|v|^2",
    )
    require_ok(parse_capped_rational(db["kernel_collision_diff_sq_q"], "p5_col") == 0, "SEC_P5_COLLISION", "A(x+k)=Ax")
    require_ok(
        parse_capped_rational(db["recon_loss_opt_q"], "p5_ro") + parse_capped_rational(db["recon_excess_q"], "p5_rx")
        == parse_capped_rational(db["recon_loss_subopt_q"], "p5_rs"),
        "SEC_P5_RECON",
        "Pythagorean recon lower bound",
    )
    su = p5["singular_susy_5x5"]
    require_ok(parse_capped_rational(su["a_k1_norm_sq_q"], "p5_ak1") == 0, "SEC_P5_SUSY_K1", "k1 in ker A")
    require_ok(parse_capped_rational(su["at_k2_norm_sq_q"], "p5_atk2") == 0, "SEC_P5_SUSY_K2", "k2 in ker A^T")
    require_ok(parse_capped_rational(su["at_k1_norm_sq_q"], "p5_atk1") > 0, "SEC_P5_SUSY_NP1", "A^T k1 != 0")
    require_ok(parse_capped_rational(su["a_k2_norm_sq_q"], "p5_ak2") > 0, "SEC_P5_SUSY_NP2", "A k2 != 0")
    sh = p5["sylvester_lapse_and_hopf_fiber"]
    require_ok(
        parse_capped_rational(sh["quad_dld_q"], "p5_q1") == parse_capped_rational(sh["quad_ldv_q"], "p5_q2"),
        "SEC_P5_SYLV",
        "Sylvester congruence",
    )
    require_ok(sh["hopf_q0"] == sh["hopf_s1_rotated"], "SEC_P5_HOPF_INV", "Hopf S^1 fiber invariant")
    require_ok(sh["hopf_q0"] != sh["hopf_off_fiber"], "SEC_P5_HOPF_OFF", "Hopf off-fiber changes")


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
            raise S112Error("INVALID_JSON_TYPE", f"forbidden value type: {t.__name__}")


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
    base = TRACK_DIR.parent if root_dir is None else root_dir
    checked: list[dict[str, str]] = []
    unverifiable: list[dict[str, str]] = []
    for pid, rel, expected_sha in oracle.EXTERNAL_STAGE_B_PINS:
        p = base / rel
        if not p.is_file():
            # Fail-loud, never silent: a pin whose file is absent is reported as
            # unverifiable instead of being skipped (review ruling: pins that
            # resolve nowhere are flagged, not silently dropped).
            unverifiable.append({"id": pid, "path": rel, "sha256": expected_sha})
            continue
        raw = read_regular_bytes_capped(p, pid)
        actual = oracle.sha256_hex(raw)
        require_ok(actual == expected_sha, "PIN_SHA_MISMATCH", f"{pid}: SHA mismatch")
        checked.append({"id": pid, "sha256": actual})
    if unverifiable:
        return {
            "status": "PINS_UNVERIFIABLE",
            "external": len(checked),
            "unverifiable": len(unverifiable),
            "pins": checked,
            "unverifiable_pins": unverifiable,
        }
    return {"status": "PINS_OK", "external": len(checked), "unverifiable": 0, "pins": checked}


S102_CERT_REL = "track-s102-drosophila-malecns-connectome/s102_malecns_connectome_certificate.json"
S102_CERT_SHA256 = "5238ce3f81099bd93145600b728d8af490a753447e089babf7ce035deb3bd945"


def s102_malecns_crosscheck() -> dict[str, int]:
    """Read the S102 MaleCNS certificate (sha256-pinned) and return its E/I/total/CX values."""
    p = TRACK_DIR.parent / S102_CERT_REL
    raw = read_regular_bytes_capped(p, "S102_CERT")
    require_ok(oracle.sha256_hex(raw) == S102_CERT_SHA256, "S102_CERT_SHA_MISMATCH", "S102 certificate SHA-256 drifted")
    cert = json.loads(raw)
    share = cert["payload"]["pillar1_whole_cns_topology"]["dale_exc_share_of_signed_q"]
    e_s, t_s = (int(x) for x in share.split("/"))
    cx = cert["payload"]["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["biological_sign_witnesses"]["central_complex_self_net"]
    return {"e": e_s, "i": t_s - e_s, "total": t_s, "cx": int(cx)}


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
                raise S112Error("UNKNOWN_FLAG", f"unrecognized argument: {tok}")
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
            if res["status"] == "PINS_UNVERIFIABLE":
                sys.stdout.write(f"PINS_UNVERIFIABLE external={res['external']} unverifiable={res['unverifiable']}\n")
            else:
                sys.stdout.write(f"PINS_OK external={res['external']} unverifiable={res['unverifiable']}\n")
        elif mode == "--verify-lean":
            sys.stdout.write(f"LEAN_OK theorems={res['theorems_verified']} sha256={res['lean_source_sha256']}\n")
        else:
            sys.stdout.write(f"OK {res['track_id']} cert_sha256={res['certificate_sha256']}\n")
        return 0
    except S112Error as exc:
        sys.stderr.write(f"ERROR {exc.code}: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
