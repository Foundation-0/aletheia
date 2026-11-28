#!/usr/bin/env python3
"""Track S105 verifier: fail-closed SEC/FR0/FR1 certificate auditor, hardened Zone-B I/O,
18-rule R12 static Lean 4 scanner, and zero-TOCTOU live Lean 4.36.0 gate with allowlist
environment scrubbing (stripping LEAN_*, ELAN_*, LAKE_*, LD_*, DYLD_*).

Zero floating-point operations, zero bare asserts, zero third-party packages.
"""
from __future__ import annotations

from fractions import Fraction
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

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s105_dual_chow_matroid_oracle as oracle  # noqa: E402
from s105_dual_chow_matroid_oracle import S105Error, require_ok  # noqa: E402

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_JSON_INT_DIGITS = 80
MAX_FILE_BYTES = 4 * 1024 * 1024

_RAW_INT_SCAN_RE = re.compile(r"(?<![0-9A-Za-z_\"'])-?[0-9]+")
_RAT_RE = re.compile(r"(-?(?:0|[1-9][0-9]{0,79}))(?:/([1-9][0-9]{0,79}))?")
_DEC_RE = re.compile(r"-?(?:0|[1-9][0-9]{0,79})(?:\.[0-9]{1,18})?")
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})
_SAFE_LEAN_ENV_KEYS = frozenset({"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP", "HOME", "USER"})

# 18-rule R12 static Lean 4 trust-escape scanner (applied to comment-stripped source).
LEAN4_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("R01_STRING_OR_GUILLEMET", re.compile(r'["«»]')),
    ("R02_SORRY_ADMIT_AXIOM", re.compile(r"\b(?:sorry|admit|axiom|sorryAx|mkSorry)\b")),
    ("R03_UNSAFE_PARTIAL_OPAQUE_VIS", re.compile(r"\b(?:unsafe|partial|opaque|private|protected|noncomputable)\b")),
    ("R04_KERNEL_BYPASS_PANIC", re.compile(
        r"\b(?:native_decide|bv_decide|ofReduceBool|ofReduceNat|trustCompiler|panic|panicCore|panicWithPos|panicWithPosWithDecl|unreachable)\b")),
    ("R05_FFI_IMPLEMENTED_BY", re.compile(r"\b(?:extern|implemented_by|csimp)\b")),
    ("R06_INITIALIZE", re.compile(r"\b(?:initialize|builtin_initialize)\b")),
    ("R07_INIT_ATTRIBUTE", re.compile(
        r"(?:@\s*\[|\battribute\s*\[)\s*(?:(?:local|scoped)\s+)?(?:[^\]\n]*,\s*)?(?:builtin_)?init\b")),
    ("R08_EXPORT", re.compile(r"\bexport\b")),
    ("R09_METAPROGRAMMING", re.compile(
        r"\b(?:macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat|run_cmd|run_elab|run_meta"
        r"|term_elab|command_elab|builtin_term_elab|builtin_command_elab|builtin_tactic|builtin_macro)\b"
        r"|@\s*\[[^\]\n]*\btactic\b")),
    ("R10_NOTATION", re.compile(r"\b(?:notation|prefix|infix|infixl|infixr|postfix)\b")),
    ("R11_IMPORT", re.compile(r"\bimport\b")),
    ("R12_SET_OPTION", re.compile(r"\bset_option\b")),
    ("R13_DEBUG_WARN_OPTIONS", re.compile(
        r"\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|sorryAsError|terminalTacticsAsSorry)\b"
        r"|\bwarn\s*\.\s*sorry\b")),
    ("R14_DBG_BUILTINS", re.compile(
        r"\b(?:dbg_trace|dbg_sleep|dbg_stack_trace|dbgTrace|dbgTraceVal|dbgTraceIfShared|dbgSleep|dbgStackTrace)\b")),
    ("R15_HASH_COMMANDS", re.compile(r"#\s*(?:eval|reduce|exit|check|synth|guard_msgs|guard_expr|guard)\b")),
    ("R16_PLUS_NATIVE_FLAG", re.compile(r"(?<!\w)\+\s*native\b")),
    ("R17_NATIVE_CONFIG", re.compile(
        r"\bnative\s*:=|\bDecide(?:Config|\.Config)\b|\bconfig\s*:=|\{\s*native\b")),
    ("R18_MULTILINE_DECIDE", re.compile(r"\bdecide\s*\n\s*[(+{]")),
)
_LEAN4_PRINT_LINE_RE = re.compile(r"#\s*print\b[^\n]*")
_LEAN4_VALID_PRINT_RE = re.compile(r"^#print axioms (" + re.escape(oracle.LEAN_MODULE) + r"\.[A-Za-z0-9_]+)$")
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([^']+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([^']+)' depends on axioms: \[([^\]]*)\]$")

_ENVELOPE_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "payload", "certificate_sha256"})
_PAYLOAD_KEYS = frozenset({
    "schema_version", "track_id", "oracle_class", "novelty_classification", "n2_claims", "prior_art",
    "external_pins", "pinned_artifacts", "pillar1_pr569_audit", "pillar2_sharp_rank_and_r4_frontier",
    "pillar3_phase_transition", "pillar4_higher_rank_and_obstructions",
    "pillar5_affine_gabidulin_and_bcel_frontier", "scope",
})


# ---------------------------------------------------------------------------
# Hardened Zone-B file I/O
# ---------------------------------------------------------------------------

def _check_path_str(raw_path: Any, label: str) -> Path:
    s = str(raw_path) if isinstance(raw_path, Path) else oracle.require_exact_str(raw_path, label)
    require_ok(len(s) > 0, "EMPTY_PATH", f"{label} is empty")
    require_ok("\x00" not in s, "NUL_BYTE_FORBIDDEN", f"{label} contains NUL")
    try:
        s.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise S105Error("INVALID_UTF8_SURROGATE", f"{label}: invalid utf-8") from exc
    return Path(s)


def _check_no_symlink_components(path: Path, label: str) -> Path:
    cur = Path("/") if path.is_absolute() else Path(".")
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        cur = cur / part
        try:
            st = os.lstat(cur)
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError as exc:
            raise S105Error("IO_STAT_ERROR", f"{label}: lstat failed on {cur}") from exc
        require_ok(not stat.S_ISLNK(st.st_mode), "SYMLINK_IN_PATH", f"{label}: symlink {cur}")
    return path


def _check_safe_cwd() -> None:
    try:
        cwd = os.getcwd()
    except OSError as exc:
        raise S105Error("CWD_ERROR", f"getcwd failed: {exc}") from exc
    pwd = os.environ.get("PWD", "")
    if os.path.isabs(pwd):
        try:
            st_pwd = os.stat(pwd)
            st_cwd = os.stat(cwd)
        except OSError:
            return
        if st_pwd.st_ino == st_cwd.st_ino:
            _check_no_symlink_components(Path(pwd), "PWD")


def read_regular_bytes_capped(raw_path: Any, label: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=64 * 1024 * 1024)
    _check_safe_cwd()
    path = _check_no_symlink_components(_check_path_str(raw_path, label), label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        raise S105Error("IO_OPEN_ERROR", f"{label}: open failed ({exc.__class__.__name__})") from exc
    try:
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", f"{label}: not a regular file")
        require_ok(st.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: nlink={st.st_nlink}")
        require_ok(st.st_size <= max_bytes, "FILE_TOO_LARGE", f"{label}: size > {max_bytes}")
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                buf = os.read(fd, min(65536, max_bytes - total + 1))
            except OSError as exc:
                raise S105Error("IO_READ_ERROR", f"{label}: read failed") from exc
            if not buf:
                break
            total += len(buf)
            require_ok(total <= max_bytes, "FILE_STREAM_TOO_LARGE", f"{label}: stream > {max_bytes}")
            chunks.append(buf)
        return b"".join(chunks)
    finally:
        os.close(fd)


def write_regular_bytes_atomic_0600(raw_path: Any, data: bytes, label: str) -> Path:
    require_ok(type(data) is bytes, "INVALID_BYTES", f"{label}: data must be bytes")
    _check_safe_cwd()
    path = _check_no_symlink_components(_check_path_str(raw_path, label), label)
    try:
        pst = os.lstat(path.parent)
    except OSError as exc:
        raise S105Error("PARENT_MISSING", f"{label}: parent unavailable") from exc
    require_ok(stat.S_ISDIR(pst.st_mode), "PARENT_NOT_DIR", f"{label}: parent not a directory")
    try:
        tst = os.lstat(path)
    except FileNotFoundError:
        tst = None
    if tst is not None:
        require_ok(stat.S_ISREG(tst.st_mode), "TARGET_NOT_REGULAR", f"{label}: target not regular")
        require_ok(tst.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: target nlink != 1")
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(6)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(tmp_path), flags, 0o600)
    except OSError as exc:
        raise S105Error("IO_OPEN_ERROR", f"{label}: temp open failed") from exc
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fchmod(fd, 0o600)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp_path, path)
    except OSError as exc:
        if fd >= 0:
            os.close(fd)
        os.unlink(tmp_path)
        raise S105Error("IO_WRITE_ERROR", f"{label}: write failed") from exc
    return path


# ---------------------------------------------------------------------------
# Strict zero-float canonical JSON parser
# ---------------------------------------------------------------------------

def _reject_float(token: str) -> Any:
    raise S105Error("FORBIDDEN_JSON_FLOAT", f"float token forbidden: {token[:16]}")


def _reject_const(token: str) -> Any:
    raise S105Error("FORBIDDEN_JSON_CONST", f"non-standard JSON constant: {token}")


def _no_dup_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key: {k[:32]}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes, label: str) -> Any:
    require_ok(type(raw) is bytes, "INVALID_BYTES", f"{label}: expected bytes")
    require_ok(len(raw) <= MAX_JSON_BYTES, "JSON_TOO_LARGE", f"{label}: exceeds {MAX_JSON_BYTES} bytes")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise S105Error("NON_ASCII_JSON", f"{label}: non-ASCII byte") from exc
    for m in _RAW_INT_SCAN_RE.finditer(text):
        require_ok(len(m.group(0).lstrip("-")) <= MAX_JSON_INT_DIGITS, "JSON_INT_TOO_LARGE", f"{label}: integer too large")
    try:
        obj = json.loads(text, parse_float=_reject_float, parse_constant=_reject_const,
                         object_pairs_hook=_no_dup_object_pairs)
    except S105Error:
        raise
    except (ValueError, RecursionError) as exc:
        raise S105Error("INVALID_JSON", f"{label}: malformed JSON ({exc.__class__.__name__})") from exc
    canon = oracle.canonical_json_bytes(obj)
    require_ok(hmac.compare_digest(raw, canon), "NON_CANONICAL_JSON", f"{label}: not canonical")
    return obj


# ---------------------------------------------------------------------------
# R12 static Lean 4 scanner and zero-TOCTOU live Lean 4.36.0 gate
# ---------------------------------------------------------------------------

def strip_lean4_comments(src: str) -> str:
    out: list[str] = []
    i = 0
    n = len(src)
    depth = 0
    while i < n:
        two = src[i:i + 2]
        if depth == 0 and two == "--":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if two == "/-":
            depth += 1
            i += 2
            continue
        if depth > 0 and two == "-/":
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(src[i])
        elif src[i] == "\n":
            out.append("\n")
        i += 1
    require_ok(depth == 0, "LEAN4_UNTERMINATED_COMMENT", "unclosed /- block comment")
    return "".join(out)


def lean4_rule_hits(src: str) -> list[str]:
    stripped = strip_lean4_comments(src)
    return [rid for rid, rx in LEAN4_RULES if rx.search(stripped) is not None]


def static_gate_lean4_source(src: str) -> None:
    require_ok("\r" not in src, "LEAN4_BAD_CHARS", "CR forbidden in Lean source")
    require_ok("\x00" not in src, "LEAN4_BAD_CHARS", "NUL forbidden in Lean source")
    hits = lean4_rule_hits(src)
    require_ok(hits == [], "LEAN4_TRUST_ESCAPE", f"banned Lean construct(s): {hits}")
    stripped = strip_lean4_comments(src)
    seen: list[str] = []
    for pm in _LEAN4_PRINT_LINE_RE.finditer(stripped):
        vm = _LEAN4_VALID_PRINT_RE.match(pm.group(0).strip())
        require_ok(vm is not None, "LEAN4_BAD_PRINT", f"disallowed #print: {pm.group(0)[:80]!r}")
        seen.append(vm.group(1))
    require_ok(seen == list(oracle.LEAN_THEOREM_NAMES), "LEAN4_PRINT_SET_MISMATCH", "#print axioms mismatch")
    for short in oracle.LEAN_THEOREM_SHORT_NAMES:
        require_ok(re.search(rf"(?m)^theorem\s+{re.escape(short)}\b", stripped) is not None,
                   "LEAN4_MISSING_THEOREM", f"missing theorem {short}")


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN", "")
    if env_bin != "":
        require_ok(os.path.isfile(env_bin), "LEAN_BINARY_NOT_FILE", "ALETHEIA_LEAN_BIN is not a regular file")
        require_ok(os.access(env_bin, os.X_OK), "LEAN_BINARY_NOT_EXECUTABLE", "ALETHEIA_LEAN_BIN is not executable")
        return env_bin
    found = shutil.which("lean")
    require_ok(found is not None, "LEAN_BINARY_UNAVAILABLE", "lean not found on PATH (set ALETHEIA_LEAN_BIN)")
    return str(found)


def scrubbed_lean_env() -> dict[str, str]:
    """Strict allowlist env for live Lean: strips LEAN_*, ELAN_*, LAKE_*, LD_*, DYLD_*."""
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


def verify_lean4_file_live(lean_path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_capped(lean_path, "lean_source")
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise S105Error("INVALID_UTF8", "Lean file invalid UTF-8") from exc
    static_gate_lean4_source(src)
    lean_bin = resolve_lean_binary()
    env = scrubbed_lean_env()
    try:
        v_proc = subprocess.run([lean_bin, "--version"], capture_output=True, text=True, timeout=60, check=False, env=env)
        proc = subprocess.run([lean_bin, "--stdin"], input=src, capture_output=True, text=True, timeout=300, check=False, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        raise S105Error("LEAN_EXEC_ERROR", f"lean execution failed: {exc.__class__.__name__}") from exc
    require_ok(v_proc.returncode == 0, "LEAN_VERSION_MISMATCH", "lean --version failed")
    require_ok("version 4.36.0," in v_proc.stdout, "LEAN_VERSION_MISMATCH", "expected Lean 4.36.0")
    require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    require_ok(proc.stderr == "", "LEAN_STDERR_NONEMPTY", "lean stderr non-empty")
    require_ok("warning" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning emitted")
    seen = parse_lean_axiom_output(proc.stdout)
    return {
        "lean_version": v_proc.stdout.strip().splitlines()[0],
        "theorems_verified": len(seen),
        "lean_source_sha256": oracle.sha256_hex(raw),
    }


# ---------------------------------------------------------------------------
# Field-complete secondary auditor (SEC; enforced on both FR0 and FR1)
# ---------------------------------------------------------------------------

def strict_shape_match(a: Any, b: Any) -> str:
    """Verify identical container types, dict keysets, list lengths, and leaf types; '' iff matched."""
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
    """Type-strict structural equality; returns '' when equal, else the first mismatching path."""
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
    s = oracle.require_exact_str(val, label)
    m = _RAT_RE.fullmatch(s)
    require_ok(m is not None, "INVALID_RATIONAL_STR", f"{label}: bad or over-long rational")
    return Fraction(int(m.group(1)), int(m.group(2) or "1"))


def parse_capped_int_str(val: Any, label: str) -> int:
    s = oracle.require_exact_str(val, label)
    m = _RAT_RE.fullmatch(s)
    require_ok(m is not None, "INVALID_INT_STR", f"{label}: bad or over-long int string")
    require_ok(m.group(2) is None, "INVALID_INT_STR", f"{label}: denominator forbidden")
    return int(m.group(1))


def parse_capped_dec(val: Any, label: str) -> str:
    s = oracle.require_exact_str(val, label)
    require_ok(_DEC_RE.fullmatch(s) is not None, "INVALID_DEC_STR", f"{label}: bad or over-long decimal")
    return s


def _independent_semantics(p: dict[str, Any]) -> None:
    """Zero-shared-code re-derivation of the load-bearing exact claims across all 5 pillars."""
    p1 = p["pillar1_pr569_audit"]
    require_ok(p1["m17_ground_set_size"] == (17 ** 8 - 1) // 16 + 17 ** 4, "SEC_M17_SIZE", "|E(M_17)| mismatch")
    g17 = [parse_capped_int_str(x, "m17_g") for x in p1["m17_gamma_Hstar"]]
    d17 = parse_capped_int_str(p1["m17_disc_Hstar"], "m17_disc")
    require_ok(d17 == g17[1] * g17[1] - 4 * g17[0] * g17[2], "SEC_M17_DISC", "M_17 discriminant mismatch")
    require_ok(d17 < 0, "SEC_M17_DISC_SIGN", "M_17 discriminant must be negative")
    parse_capped_dec(p1["q16_ratio_Hstar_dec6"], "q16_rat")
    parse_capped_dec(p1["q17_ratio_Hstar_dec6"], "q17_rat")
    require_ok(p1["shifted_neg_disc_Hstar_deg"] == 43, "SEC_SHIFT43_DEG", "expected deg 43")
    require_ok(parse_capped_rational(p1["shifted_neg_disc_Hstar_lc_q"], "lc43") == 4, "SEC_SHIFT43_LC", "expected LC 4")
    p2 = p["pillar2_sharp_rank_and_r4_frontier"]
    require_ok(p2["sharp_min_rank_for_Hstar"] == 5, "SEC_MIN_RANK", "sharp min rank is 5")
    require_ok(p2["rank4_gabidulin_Fstar_disc_shift2_all_pos"] is True, "SEC_R4_FSTAR", "rank4 F* disc")
    p3 = p["pillar3_phase_transition"]
    rows3 = p3["rows"]
    berg_q = next(r["q"] for r in rows3 if r["bergman_h_real_roots"] < 4)
    dual_q = next(r["q"] for r in rows3 if r["H_star_real_roots"] < 4)
    require_ok(p3["bergman_first_fail_q"] == berg_q, "SEC_BERGMAN_Q8", "Bergman first fail must equal first row with <4 real roots")
    require_ok(p3["bergman_first_fail_ground_set"] == (berg_q ** 8 - 1) // (berg_q - 1) + berg_q ** 4, "SEC_M8_SIZE", "|E(M_berg)| derived from rows")
    require_ok(p3["dual_chow_first_fail_q"] == dual_q, "SEC_DUAL_Q17", "dual Chow first fail must equal first row with H*<4")
    require_ok(p3["dual_chow_first_fail_ground_set"] == (dual_q ** 8 - 1) // (dual_q - 1) + dual_q ** 4, "SEC_M17_SIZE", "|E(M_dual)| derived from rows")
    require_ok(
        p3["primal_vs_dual_separation_verified"] is (all(r["H_ord_real_roots"] == 4 for r in rows3) and any(r["H_star_real_roots"] < 4 for r in rows3)),
        "SEC_SEP",
        "separation flag must be derived from rows",
    )
    require_ok(p3["ordinary_chow_all_4of4_real_rooted"] is True, "SEC_H_ORD", "ordinary Chow stays 4/4")
    p4 = p["pillar4_higher_rank_and_obstructions"]
    r6_q = next(r["q"] for r in p4["rank6_rows"] if r["gamma_quad_disc_neg"])
    r7_q = next(r["q"] for r in p4["rank7_rows"] if r["cubic_gamma_disc_neg"])
    r7_row = next(r for r in p4["rank7_rows"] if r["q"] == r7_q)
    require_ok(p4["rank6_threshold_q"] == r6_q, "SEC_R6_Q11", "rank 6 threshold derived from rank6_rows")
    require_ok(p4["rank7_threshold_q"] == r7_q, "SEC_R7_Q7", "rank 7 threshold derived from rank7_rows")
    require_ok(
        p4["rank7_q7_fails_cubic_disc_before_newton"] is (r7_row["cubic_gamma_disc_neg"] and r7_row["newton_1_holds"] and r7_row["newton_2_holds"]),
        "SEC_R7_DISC_BEFORE_NEWTON",
        "rank-7 flag derived from rank7_rows",
    )
    require_ok(p4["mrd_duality_obstruction"]["dual_min_rank"] == 4, "SEC_MRD_DUAL", "MRD dual min rank = 4")
    p5 = p["pillar5_affine_gabidulin_and_bcel_frontier"]
    ag = p5["affine_gabidulin_rank5"]
    require_ok(ag["a17_ground_set_size"] == 17 ** 6 + 17 ** 3, "SEC_A17_SIZE", "|E(A_17)| mismatch")
    require_ok(
        parse_capped_rational(ag["size_reduction_factor_q"], "red_q") == Fraction((17 ** 8 - 1) // 16 + 17 ** 4, 17 ** 6 + 17 ** 3),
        "SEC_RED_RATIO", "18.06x reduction ratio mismatch",
    )
    ag_g17 = [parse_capped_int_str(x, "a17_g") for x in ag["a17_gamma_Hstar"]]
    ag_d17 = parse_capped_int_str(ag["a17_disc_Hstar"], "a17_disc")
    require_ok(ag_d17 == ag_g17[1] * ag_g17[1] - 4 * ag_g17[0] * ag_g17[2], "SEC_A17_DISC", "A_17 disc mismatch")
    require_ok(ag_d17 < 0, "SEC_A17_DISC_SIGN", "A_17 disc must be negative")
    require_ok(ag["shifted_neg_disc_Hstar_deg"] == 35, "SEC_SHIFT35_DEG", "expected deg 35")
    require_ok(ag["a2_brute_force_verification"]["w4_matches_formula"] is True, "SEC_A2_BF", "A_2 brute-force match")


_EXPECTED_PAYLOAD_CANON: list[bytes] = []
_EXPECTED_PAYLOAD_REF: list[Any] = []


def expected_payload() -> Any:
    if not _EXPECTED_PAYLOAD_CANON:
        _EXPECTED_PAYLOAD_CANON.append(oracle.canonical_json_bytes(oracle.build_payload()))
    return json.loads(_EXPECTED_PAYLOAD_CANON[0].decode("ascii"))


def _expected_payload_ref() -> Any:
    if not _EXPECTED_PAYLOAD_REF:
        _EXPECTED_PAYLOAD_REF.append(expected_payload())
    return _EXPECTED_PAYLOAD_REF[0]


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")
    oracle.validate_strict_json_tree(payload, "payload")
    require_ok(frozenset(payload) == _PAYLOAD_KEYS, "KEYSET_MISMATCH", "payload keyset mismatch")
    ref = _expected_payload_ref()
    shape_err = strict_shape_match(payload, ref)
    require_ok(shape_err == "", "SEC_SHAPE_MISMATCH", f"payload shape/type mismatch at {shape_err}")
    _independent_semantics(payload)
    diff = strict_deep_equal(payload, ref)
    require_ok(diff == "", "SEC_PAYLOAD_PIN_MISMATCH", f"payload leaf mismatch at {diff}")
    return {
        "secondary_audit_passed": True,
        "lean_theorem_count": len(oracle.LEAN_THEOREM_NAMES),
        "external_pins_count": len(oracle.EXTERNAL_PINS),
    }


def _load_track_artifacts(track_dir: Path) -> dict[str, Any]:
    tc_raw = read_regular_bytes_capped(track_dir / "lean-toolchain", "lean-toolchain")
    lk_raw = read_regular_bytes_capped(track_dir / "lakefile.toml", "lakefile.toml")
    require_ok(tc_raw == (oracle.EXPECTED_LEAN_TOOLCHAIN + "\n").encode("ascii"), "TOOLCHAIN_MISMATCH", "lean-toolchain mismatch")
    require_ok(oracle.sha256_hex(lk_raw) == oracle.PINNED_LAKEFILE_SHA256, "LAKEFILE_SHA_MISMATCH", "lakefile SHA mismatch")
    live = verify_lean4_file_live(track_dir / oracle.LEAN_SOURCE_NAME)
    require_ok(live["lean_source_sha256"] == oracle.PINNED_LEAN_SOURCE_SHA256, "LEAN_SHA_MISMATCH", "Lean SHA mismatch")
    return live


def verify_certificate_dict(cert: Any, *, full_replay: bool = True, track_dir: Path | None = None) -> dict[str, Any]:
    oracle.require_bool(full_replay, "full_replay")
    require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    oracle.validate_strict_json_tree(cert, "certificate")
    require_ok(frozenset(cert) == _ENVELOPE_KEYS, "KEYSET_MISMATCH", "envelope keyset mismatch")
    require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "envelope schema_version")
    require_ok(cert["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "envelope track_id")
    p_sha = oracle.require_hex64(cert["payload_sha256"], "payload_sha256")
    c_sha = oracle.require_hex64(cert["certificate_sha256"], "certificate_sha256")
    payload = cert["payload"]
    sec = secondary_audit_payload(payload)
    require_ok(hmac.compare_digest(p_sha, oracle.sha256_hex(oracle.canonical_json_bytes(payload))), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")
    core = {"schema_version": cert["schema_version"], "track_id": cert["track_id"], "payload_sha256": p_sha, "payload": payload}
    require_ok(hmac.compare_digest(c_sha, oracle.sha256_hex(oracle.canonical_json_bytes(core))), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")
    receipt: dict[str, Any] = {
        "valid": True, "track_id": oracle.TRACK_ID, "full_replay": full_replay,
        "payload_sha256": p_sha, "certificate_sha256": c_sha, "secondary_audit": sec,
    }
    if full_replay:
        receipt["lean_live"] = _load_track_artifacts(_THIS_DIR if track_dir is None else track_dir)
    return receipt


def verify_external_pins(repo_root: Any) -> dict[str, Any]:
    root = _check_no_symlink_components(_check_path_str(repo_root, "repo_root"), "repo_root")
    for pid, rel, nbytes, sha in oracle.EXTERNAL_PINS:
        raw = read_regular_bytes_capped(root / rel, pid)
        require_ok(len(raw) == nbytes, "EXT_PIN_BYTES", f"byte length mismatch on {pid}")
        require_ok(hmac.compare_digest(oracle.sha256_hex(raw), sha), "EXT_PIN_SHA", f"sha mismatch on {pid}")
    return {"status": "PINS_VERIFIED", "external_pins_verified": len(oracle.EXTERNAL_PINS)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_PATH_FLAGS = ("--check", "--write", "--verify-pins")


def _parse_cli_args(argv: list[str]) -> dict[str, Any]:
    mode = "default"
    target: str | None = None
    as_json = False
    i = 0
    while i < len(argv):
        arg = oracle.require_exact_str(argv[i], f"argv[{i}]")
        if arg == "--json":
            require_ok(not as_json, "DUPLICATE_FLAG", "duplicate --json")
            as_json = True
            i += 1
            continue
        if arg == "--standalone":
            require_ok(mode == "default", "CONFLICTING_MODE", "conflicting mode")
            mode = "standalone"
            i += 1
            continue
        require_ok(arg in _PATH_FLAGS, "UNKNOWN_FLAG", f"unknown flag: {arg[:40]!r}")
        require_ok(mode == "default", "CONFLICTING_MODE", "conflicting mode")
        require_ok(i + 1 < len(argv), "MISSING_PATH_ARG", f"missing path for {arg}")
        val = oracle.require_exact_str(argv[i + 1], f"{arg}_path")
        require_ok(not val.startswith("-"), "INVALID_PATH_ARG", "path must not start with '-'")
        mode = arg[2:]
        target = val
        i += 2
    return {"mode": mode, "target": target, "as_json": as_json}


def _emit(obj: dict[str, Any], as_json: bool, text: str) -> None:
    sys.stdout.write(oracle.canonical_json_bytes(obj).decode("ascii") if as_json else text)


def main(argv: list[str] | None = None) -> int:
    try:
        opts = _parse_cli_args(sys.argv[1:] if argv is None else argv)
        mode = opts["mode"]
        if mode == "standalone":
            sys.stdout.write(oracle.canonical_json_bytes(oracle.build_certificate()).decode("ascii"))
            return 0
        if mode == "verify-pins":
            res = verify_external_pins(opts["target"])
            _emit(res, opts["as_json"], f"PINS_OK external={res['external_pins_verified']}\n")
            return 0
        if mode == "write":
            cert = oracle.build_certificate()
            res = verify_certificate_dict(cert, full_replay=True)
            out_p = write_regular_bytes_atomic_0600(opts["target"], oracle.canonical_json_bytes(cert), "write_target")
            _emit({"written": True, "path": str(out_p), **res}, opts["as_json"], f"WROTE {out_p} sha256={res['certificate_sha256']}\n")
            return 0
        if mode == "check":
            raw = read_regular_bytes_capped(opts["target"], "check_target", max_bytes=MAX_JSON_BYTES)
            res = verify_certificate_dict(parse_strict_json_bytes(raw, "check_target"), full_replay=True)
        else:
            res = verify_certificate_dict(oracle.build_certificate(), full_replay=True)
        _emit(res, opts["as_json"], f"OK {res['track_id']} cert_sha256={res['certificate_sha256']}\n")
        return 0
    except S105Error as exc:
        sys.stderr.write(oracle.canonical_json_bytes({"valid": False, "code": exc.code, "detail": exc.detail}).decode("ascii"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
