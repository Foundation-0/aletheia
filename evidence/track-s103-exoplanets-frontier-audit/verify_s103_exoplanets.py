#!/usr/bin/env python3
"""Track S103: Fail-Closed R5 Verifier, Field-Complete SEC/FR0/FR1 Semantic Auditor,
Hardened Zone-B I/O, and Full R12 Static + Zero-TOCTOU Live Lean 4.36.0 Gate.

Zero floating-point operations, zero bare asserts, zero third-party packages.
"""
from __future__ import annotations

from fractions import Fraction
import hmac
import json
import math
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

import s103_exoplanets_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_JSON_INT_DIGITS = 80
MAX_RATIONAL_STR_LEN = 162
MAX_FILE_BYTES = 4 * 1024 * 1024

_INT_LITERAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_RAW_INT_SCAN_RE = re.compile(r"(?<![0-9A-Za-z_\"'])-?[0-9]+")
_RAT_RE = re.compile(r"^(-?(?:0|[1-9][0-9]*))(?:/([1-9][0-9]*))?$")

_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

# Full R12 Lean 4 trust-escape rules (zero leading (?<!\.) so dot-qualified escapes are caught!)
_LEAN4_BANNED_RE = re.compile(
    r"(?:"
    r'["«»]'
    r"|\b(?:sorry|admit|axiom|unsafe|partial|opaque|noncomputable|native_decide|bv_decide"
    r"|sorryAx|ofReduceBool|ofReduceNat|trustCompiler|mkSorry"
    r"|extern|implemented_by|csimp|initialize|builtin_initialize"
    r"|macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat"
    r"|notation|prefix|infix|infixl|infixr|postfix|run_cmd|run_meta|import"
    r"|set_option|dbg_trace|dbg_sleep|dbg_stack_trace"
    r"|dbgTrace|dbgTraceVal|dbgTraceValId|dbgTraceIfShared|dbgSleep|dbgStackTrace"
    r"|panicWithPos|panicWithPosWithDecl)\b"
    r"|\b(?:panic|unreachable|assert|debug_assert)!"
    r"|\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|sorryAsError|terminalTacticsAsSorry)\b"
    r"|@\s*\[\s*(?:(?:local|scoped)\s+)?(?:[^\]\n]*,\s*)?(?:(?:builtin_)?init|export|term_elab|command_elab|tactic|macro(?:_rules)?)\b"
    r"|\battribute\s*\[\s*(?:(?:local|scoped)\s+)?(?:[^\]\n]*,\s*)?(?:(?:builtin_)?init|export|term_elab|command_elab|tactic|macro(?:_rules)?)\b"
    r"|#\s*(?:eval|reduce|exit|check|synth|guard(?:_msgs)?)\b"
    r"|(?<!\w)\+\s*native\b"
    r"|\bnative\s*:=(?!\s*(?:Bool\.)?false\b(?:\s*[},)]|\Z))"
    r"|\bDecide(?:Config|\.Config)\b"
    r"|\bconfig\s*:=(?!\s*\{\s*native\s*:=\s*(?:Bool\.)?false\s*\})"
    r")"
)
_LEAN4_PRINT_LINE_RE = re.compile(r"#\s*print\b[^\n]*")
_LEAN4_VALID_PRINT_RE = re.compile(r"^#print axioms (ExoplanetsFrontierOperators\.[A-Za-z0-9_]+)$")
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([^']+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([^']+)' depends on axioms: \[([^\]]*)\]$")

_ENVELOPE_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "payload", "certificate_sha256"})
_PAYLOAD_KEYS = frozenset({
    "schema_version", "track_id", "oracle_class", "novelty_classification", "n2_claims",
    "external_provenance", "pinned_artifacts",
    "pillar1_sop9_exoplanets_frontier_audit",
    "pillar2_exact_astrophysical_operators",
    "pillar3_sop10_astronomy_spine_convergence",
})
_EXPECTED_ALETHEIA_GATE_BRIDGES: tuple[str, ...] = (
    "CS-09: PR #6 seeded 25d MES=49.76 / SDE=7.23<7.5 exposes narrow-window support-truncation mirage on MAD-normalized SDE",
    "CS-18: Blind S106-S107 4-state abstention (LOW_SNR_INCONCLUSIVE=9, DATA_GAP=2) prevents forced false rejections",
    "Pont-beta ratchet: exact variance-inflation beta^2 = 1 + N*(sr/sw)^2 hardens S102/S95-S97 correlated time-series detectors",
)


# ---------------------------------------------------------------------------
# Hardened Zone-B File I/O & Path Hygiene
# ---------------------------------------------------------------------------

def _normalize_darwin_private_prefix(path_str: str) -> str:
    for prefix, target in (("/private/tmp", "/tmp"), ("/private/var", "/var")):
        if path_str == prefix or path_str.startswith(prefix + "/"):
            return target + path_str[len(prefix):]
    return path_str


def _check_path_str(raw_path: Any, label: str) -> Path:
    if isinstance(raw_path, Path):
        s = str(raw_path)
    else:
        s = oracle.require_exact_str(raw_path, label)
    oracle.require_ok(len(s) > 0, "EMPTY_PATH", f"{label} is empty")
    oracle.require_ok("\x00" not in s, "NUL_BYTE_FORBIDDEN", f"{label} contains NUL")
    try:
        s.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise oracle.S103Error("INVALID_UTF8_SURROGATE", f"{label}: invalid utf-8") from exc
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
            raise oracle.S103Error("IO_STAT_ERROR", f"{label}: lstat failed on {cur}") from exc
        oracle.require_ok(not stat.S_ISLNK(st.st_mode), "SYMLINK_IN_PATH", f"{label}: symlink {cur}")
    return path


def _check_safe_cwd() -> None:
    try:
        cwd = os.getcwd()
    except OSError as exc:
        raise oracle.S103Error("CWD_ERROR", f"getcwd failed: {exc}") from exc
    _check_no_symlink_components(Path(_normalize_darwin_private_prefix(cwd)), "cwd")
    pwd = os.environ.get("PWD", "")
    if os.path.isabs(pwd):
        try:
            st_pwd = os.stat(pwd)
            st_cwd = os.stat(cwd)
        except OSError:
            return
        if st_pwd.st_ino == st_cwd.st_ino and st_pwd.st_dev == st_cwd.st_dev:
            _check_no_symlink_components(Path(_normalize_darwin_private_prefix(pwd)), "PWD")


def read_regular_bytes_capped(raw_path: Any, label: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=64 * 1024 * 1024)
    _check_safe_cwd()
    path = _check_no_symlink_components(_check_path_str(raw_path, label), label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        raise oracle.S103Error("IO_OPEN_ERROR", f"{label}: open failed ({exc})") from exc
    try:
        st = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", f"{label}: not regular file")
        oracle.require_ok(st.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: nlink={st.st_nlink} != 1")
        oracle.require_ok(st.st_size <= max_bytes, "FILE_TOO_LARGE", f"{label}: size > {max_bytes}")
        chunks: list[bytes] = []
        total = 0
        while True:
            buf = os.read(fd, min(65536, max_bytes - total + 1))
            if not buf:
                break
            total += len(buf)
            oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: stream > {max_bytes}")
            chunks.append(buf)
        return b"".join(chunks)
    finally:
        os.close(fd)


def write_regular_bytes_atomic_0600(raw_path: Any, data: bytes, label: str) -> Path:
    oracle.require_ok(type(data) is bytes, "INVALID_BYTES", f"{label}: data must be bytes")
    _check_safe_cwd()
    path = _check_no_symlink_components(_check_path_str(raw_path, label), label)
    parent = path.parent
    try:
        pst = os.lstat(parent)
    except OSError as exc:
        raise oracle.S103Error("PARENT_MISSING", f"{label}: parent unavailable") from exc
    oracle.require_ok(stat.S_ISDIR(pst.st_mode), "PARENT_NOT_DIR", f"{label}: parent not dir")
    try:
        tst = os.lstat(path)
    except FileNotFoundError:
        tst = None
    except OSError as exc:
        raise oracle.S103Error("IO_STAT_ERROR", f"{label}: target lstat error") from exc
    if tst is not None:
        oracle.require_ok(stat.S_ISREG(tst.st_mode), "TARGET_NOT_REGULAR", f"{label}: target not regular")
        oracle.require_ok(tst.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: target nlink != 1")
    tmp_path = parent / f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(6)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(tmp_path), flags, 0o600)
    except OSError as exc:
        raise oracle.S103Error("IO_OPEN_ERROR", f"{label}: temp open failed") from exc
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            n = os.write(fd, view[written:])
            oracle.require_ok(n > 0, "IO_WRITE_ERROR", f"{label}: short write")
            written += n
        os.fchmod(fd, 0o600)
        st = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "TMP_TAMPERED", f"{label}: tmp tampered")
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp_path, path)
    except Exception:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return path


# ---------------------------------------------------------------------------
# Strict Zero-Float Canonical JSON & Rational Parsers
# ---------------------------------------------------------------------------

def _reject_float(token: str) -> Any:
    raise oracle.S103Error("FORBIDDEN_JSON_FLOAT", f"float token forbidden: {token}")


def _reject_const(token: str) -> Any:
    raise oracle.S103Error("FORBIDDEN_JSON_CONST", f"non-standard JSON constant: {token}")


def _strict_int_parse(token: str) -> int:
    oracle.require_ok(_INT_LITERAL_RE.match(token) is not None, "INVALID_JSON_INT", f"invalid int: {token}")
    digits = token[1:] if token.startswith("-") else token
    oracle.require_ok(len(digits) <= MAX_JSON_INT_DIGITS, "JSON_INT_TOO_LARGE", f"int exceeds {MAX_JSON_INT_DIGITS} digits")
    return int(token)


def _no_dup_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key: {k}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes, label: str, *, require_canonical: bool = True) -> Any:
    oracle.require_ok(type(raw) is bytes, "INVALID_BYTES", f"{label}: expected bytes")
    oracle.require_ok(len(raw) <= MAX_JSON_BYTES, "JSON_TOO_LARGE", f"{label}: exceeds {MAX_JSON_BYTES} bytes")
    oracle.require_ok(b"\r" not in raw and b"\x00" not in raw, "JSON_BAD_BYTES", f"{label}: CR/NUL forbidden")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise oracle.S103Error("NON_ASCII_JSON", f"{label}: non-ASCII byte") from exc
    for m in _RAW_INT_SCAN_RE.finditer(text):
        tok = m.group(0)
        digits = tok[1:] if tok.startswith("-") else tok
        oracle.require_ok(len(digits) <= MAX_JSON_INT_DIGITS, "JSON_INT_TOO_LARGE", f"{label}: integer too large")
    try:
        obj = json.loads(
            text,
            parse_float=_reject_float,
            parse_int=_strict_int_parse,
            parse_constant=_reject_const,
            object_pairs_hook=_no_dup_object_pairs,
        )
    except oracle.S103Error:
        raise
    except Exception as exc:
        raise oracle.S103Error("INVALID_JSON", f"{label}: malformed JSON ({exc})") from exc
    oracle.validate_strict_json_tree(obj, label)
    if require_canonical:
        canon = oracle.canonical_json_bytes(obj)
        oracle.require_ok(hmac.compare_digest(raw, canon), "NON_CANONICAL_JSON", f"{label}: not canonical")
    return obj


def _require_exact_dict(obj: Any, expected_keys: frozenset[str], label: str) -> dict[str, Any]:
    oracle.require_ok(type(obj) is dict, "INVALID_DICT", f"{label} must be exact dict")
    oracle.require_ok(frozenset(obj.keys()) == expected_keys, "KEYSET_MISMATCH", f"{label} keyset mismatch")
    return obj


def parse_canonical_rational_str(val: Any, label: str) -> Fraction:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(len(s) <= MAX_RATIONAL_STR_LEN, "RATIONAL_TOO_LARGE", f"{label}: rational length > {MAX_RATIONAL_STR_LEN}")
    m = _RAT_RE.match(s)
    oracle.require_ok(m is not None, "INVALID_RATIONAL_STR", f"{label}: bad rational {s!r}")
    num = int(m.group(1))
    den_s = m.group(2)
    if den_s is None:
        return Fraction(num, 1)
    den = int(den_s)
    oracle.require_ok(den > 1, "NON_CANONICAL_RATIONAL", f"{label}: denominator must be > 1")
    oracle.require_ok(math.gcd(abs(num), den) == 1, "NON_REDUCED_RATIONAL", f"{label}: not reduced")
    return Fraction(num, den)


# ---------------------------------------------------------------------------
# Full R12 Static + Zero-TOCTOU Live Lean 4.36.0 Verification Gate
# ---------------------------------------------------------------------------

def _strip_lean4_comments(src: str) -> str:
    out: list[str] = []
    i = 0
    n = len(src)
    depth = 0
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if depth == 0 and ch == "-" and nxt == "-":
            i += 2
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "-":
            depth += 1
            i += 2
            continue
        if depth > 0 and ch == "-" and nxt == "/":
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(ch)
        elif ch == "\n":
            out.append("\n")
        i += 1
    oracle.require_ok(depth == 0, "LEAN4_UNTERMINATED_LEX", "unclosed /- block comment")
    return "".join(out)


def static_gate_lean4_source(src: str) -> None:
    oracle.require_ok("\r" not in src and "\x00" not in src, "LEAN4_BAD_CHARS", "CR/NUL forbidden in Lean")
    stripped = _strip_lean4_comments(src)
    m = _LEAN4_BANNED_RE.search(stripped)
    oracle.require_ok(m is None, "LEAN4_TRUST_ESCAPE", f"banned Lean construct: {m.group(0)!r}" if m else "")
    for pm in _LEAN4_PRINT_LINE_RE.finditer(stripped):
        line = pm.group(0).strip()
        vm = _LEAN4_VALID_PRINT_RE.match(line)
        oracle.require_ok(
            vm is not None and vm.group(1) in oracle.LEAN_THEOREM_NAMES,
            "LEAN4_TRUST_ESCAPE",
            f"disallowed #print: {line!r}",
        )
    for full_name in oracle.LEAN_THEOREM_NAMES:
        short = full_name.split(".", 1)[1]
        oracle.require_ok(
            re.search(rf"\b(?:(?:private|protected)\s+)?theorem\s+{re.escape(short)}\b", stripped) is not None,
            "LEAN4_MISSING_THEOREM",
            f"missing {short}",
        )
        oracle.require_ok(
            re.search(rf"(?m)^#print axioms {re.escape(full_name)}$", stripped) is not None,
            "LEAN4_MISSING_PRINT_AXIOMS",
            f"missing #print axioms {full_name}",
        )


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN", "").strip()
    if env_bin:
        p = Path(env_bin)
        oracle.require_ok(p.is_file() and os.access(p, os.X_OK), "LEAN_BINARY_UNAVAILABLE", "ALETHEIA_LEAN_BIN invalid")
        return str(p)
    found = shutil.which("lean")
    if found:
        p = Path(found)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    home = os.environ.get("HOME", "").strip()
    if home:
        cand = Path(home) / ".elan" / "bin" / "lean"
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    raise oracle.S103Error("LEAN_BINARY_UNAVAILABLE", "lean binary not found")


def verify_lean4_file_live(lean_path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_capped(lean_path, "lean_source")
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S103Error("INVALID_UTF8", "Lean file invalid UTF-8") from exc
    static_gate_lean4_source(src)
    lean_bin = resolve_lean_binary()
    lean_env = {
        k: os.environ[k]
        for k in ("PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL")
        if k in os.environ
    }
    try:
        v_proc = subprocess.run([lean_bin, "--version"], env=lean_env, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise oracle.S103Error("LEAN_EXEC_ERROR", f"lean --version failed: {exc}") from exc
    oracle.require_ok(v_proc.returncode == 0 and "4.36.0" in v_proc.stdout, "LEAN_VERSION_MISMATCH", "expected Lean 4.36.0")
    try:
        proc = subprocess.run([lean_bin, "--stdin"], input=src, env=lean_env, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise oracle.S103Error("LEAN_EXEC_ERROR", f"lean --stdin failed: {exc}") from exc
    oracle.require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    oracle.require_ok(proc.stderr == "", "LEAN_STDERR_NONEMPTY", "lean stderr non-empty")
    oracle.require_ok("warning:" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning emitted")
    seen: dict[str, list[str]] = {}
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    idx = 0
    while idx < len(lines):
        ln = lines[idx]
        idx += 1
        while "depends on axioms: [" in ln and not ln.endswith("]") and idx < len(lines):
            ln = ln + " " + lines[idx]
            idx += 1
        m_none = _LEAN4_AXIOM_NONE_RE.match(ln)
        if m_none:
            tname = m_none.group(1)
            oracle.require_ok(tname not in seen, "LEAN_DUPLICATE_THEOREM", f"dup {tname}")
            seen[tname] = []
            continue
        m_dep = _LEAN4_AXIOM_DEP_RE.match(ln)
        oracle.require_ok(m_dep is not None, "LEAN_UNEXPECTED_STDOUT", f"unexpected line: {ln!r}")
        tname = m_dep.group(1)
        oracle.require_ok(tname not in seen, "LEAN_DUPLICATE_THEOREM", f"dup {tname}")
        axs = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        for ax in axs:
            oracle.require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"forbidden axiom {ax}")
        seen[tname] = axs
    oracle.require_ok(frozenset(seen.keys()) == frozenset(oracle.LEAN_THEOREM_NAMES), "LEAN_THEOREM_SET_MISMATCH", "axioms mismatch")
    return {
        "lean_version": v_proc.stdout.strip().splitlines()[0],
        "theorems_verified": len(seen),
        "lean_source_sha256": oracle.sha256_hex(raw),
    }


# ---------------------------------------------------------------------------
# Field-Complete Fail-Closed Secondary Auditor (Enforced on BOTH FR1 and FR0)
# ---------------------------------------------------------------------------

def _audit_pillar1(p1: dict[str, Any]) -> None:
    _require_exact_dict(p1, frozenset({
        "main_commit", "cool_vet_main_syntax_error", "cool_vet_error_line",
        "convergence_cert_files_total", "convergence_cert_files_matched",
        "claims_sha_prefixes_checked", "claims_sha_prefixes_stale", "claims_stale_artifacts",
        "blind_s106_s107_audit", "pr8_cool_audit_findings", "pr6_issue5_synthetic_control", "pr_matrix",
    }), "p1")
    oracle.require_ok(p1["main_commit"] == oracle.EXOPLANETS_FRONTIER_MAIN_COMMIT, "P1_COMMIT", "main_commit")
    oracle.require_ok(oracle.require_bool(p1["cool_vet_main_syntax_error"], "p1.syn") is True, "P1_SYNTAX", "syntax flag")
    oracle.require_exact_int(p1["cool_vet_error_line"], "p1.line", lo=2, hi=2)
    oracle.require_exact_int(p1["convergence_cert_files_total"], "p1.ct", lo=41, hi=41)
    oracle.require_exact_int(p1["convergence_cert_files_matched"], "p1.cm", lo=41, hi=41)
    oracle.require_exact_int(p1["claims_sha_prefixes_checked"], "p1.sc", lo=6, hi=6)
    oracle.require_exact_int(p1["claims_sha_prefixes_stale"], "p1.ss", lo=3, hi=3)
    oracle.require_ok(
        p1["claims_stale_artifacts"] == ["benchmark_and_null.json", "ttv_ephemeris_audit.csv", "blend_localization.csv"],
        "P1_STALE_LIST", "stale artifacts mismatch",
    )

    bl = _require_exact_dict(p1["blind_s106_s107_audit"], frozenset({
        "total_pairs", "covered_pairs", "data_gap_pairs", "confirmed_on_schedule",
        "marginal_recovery", "timing_offset_ttv", "low_snr_inconclusive",
        "non_detection_4sigma", "snr_ge_3_count", "inverted_artifact_tic", "inverted_artifact_snr_q",
    }), "p1.blind")
    tot = oracle.require_exact_int(bl["total_pairs"], "bl.tot", lo=39, hi=39)
    cov = oracle.require_exact_int(bl["covered_pairs"], "bl.cov", lo=37, hi=37)
    gap = oracle.require_exact_int(bl["data_gap_pairs"], "bl.gap", lo=2, hi=2)
    conf = oracle.require_exact_int(bl["confirmed_on_schedule"], "bl.conf", lo=22, hi=22)
    marg = oracle.require_exact_int(bl["marginal_recovery"], "bl.marg", lo=5, hi=5)
    ttv = oracle.require_exact_int(bl["timing_offset_ttv"], "bl.ttv", lo=1, hi=1)
    low = oracle.require_exact_int(bl["low_snr_inconclusive"], "bl.low", lo=9, hi=9)
    nd4 = oracle.require_exact_int(bl["non_detection_4sigma"], "bl.nd4", lo=0, hi=0)
    oracle.require_exact_int(bl["snr_ge_3_count"], "bl.s3", lo=24, hi=24)
    oracle.require_exact_int(bl["inverted_artifact_tic"], "bl.tic", lo=44669885, hi=44669885)
    oracle.require_ok(parse_canonical_rational_str(bl["inverted_artifact_snr_q"], "bl.isnr") == Fraction(-161, 20), "P1_BLIND_SNR", "inv snr")
    oracle.require_ok(cov + gap == tot and conf + marg + ttv + low + nd4 == cov, "P1_BLIND_SUM", "blind sum mismatch")

    p8 = _require_exact_dict(p1["pr8_cool_audit_findings"], frozenset({
        "audited_targets", "verified_survivors", "survivor_tics", "quarantined_blends",
        "committed_cool_pngs", "orphan_png_count", "stale_report_heading_count", "unguarded_main_push",
    }), "p1.pr8")
    oracle.require_exact_int(p8["audited_targets"], "p8.aud", lo=10, hi=10)
    oracle.require_exact_int(p8["verified_survivors"], "p8.surv", lo=2, hi=2)
    oracle.require_ok(p8["survivor_tics"] == [409696823, 224279805], "P1_PR8_TICS", "survivor tics")
    oracle.require_exact_int(p8["quarantined_blends"], "p8.q", lo=5, hi=5)
    oracle.require_exact_int(p8["committed_cool_pngs"], "p8.png", lo=15, hi=15)
    oracle.require_exact_int(p8["orphan_png_count"], "p8.orph", lo=6, hi=6)
    oracle.require_exact_int(p8["stale_report_heading_count"], "p8.hd", lo=14, hi=14)
    oracle.require_ok(oracle.require_bool(p8["unguarded_main_push"], "p8.push") is True, "P1_PR8_PUSH", "unguarded push")

    p6 = _require_exact_dict(p1["pr6_issue5_synthetic_control"], frozenset({
        "issue5_rows", "issue5_survived", "seeded_17d_mes_q", "seeded_17d_sde_q",
        "seeded_17d_passes_sde", "seeded_25d_mes_q", "seeded_25d_sde_q", "seeded_25d_passes_sde",
    }), "p1.pr6")
    oracle.require_exact_int(p6["issue5_rows"], "p6.r", lo=6, hi=6)
    oracle.require_exact_int(p6["issue5_survived"], "p6.s", lo=0, hi=0)
    m17 = parse_canonical_rational_str(p6["seeded_17d_mes_q"], "p6.m17")
    s17 = parse_canonical_rational_str(p6["seeded_17d_sde_q"], "p6.s17")
    m25 = parse_canonical_rational_str(p6["seeded_25d_mes_q"], "p6.m25")
    s25 = parse_canonical_rational_str(p6["seeded_25d_sde_q"], "p6.s25")
    oracle.require_ok(m17 == Fraction(5864, 100) and s17 == Fraction(859, 100), "P1_PR6_17", "17d mismatch")
    oracle.require_ok(m25 == Fraction(4976, 100) and s25 == Fraction(723, 100), "P1_PR6_25", "25d mismatch")
    oracle.require_ok(
        oracle.require_bool(p6["seeded_17d_passes_sde"], "p6.p17") is (s17 >= Fraction(15, 2))
        and oracle.require_bool(p6["seeded_25d_passes_sde"], "p6.p25") is (s25 >= Fraction(15, 2)),
        "P1_PR6_FLAGS", "PR6 SDE flags",
    )

    prm = p1["pr_matrix"]
    oracle.require_ok(type(prm) is list and prm == oracle.expected_pr_matrix(), "P1_PR_MATRIX", "pr_matrix mismatch")


def _audit_pillar2(p2: dict[str, Any]) -> None:
    _require_exact_dict(p2, frozenset({
        "bls_and_farey_separation", "pont_and_eight_gate_bayes",
        "harmonic_despot_orthogonality", "oc_ttv_and_wcs_affine",
    }), "p2")

    # 2a. BLS & Farey & CS-09 SDE
    b = _require_exact_dict(p2["bls_and_farey_separation"], frozenset({
        "baseline_multi_yr_d", "baseline_stage1_d", "sharpening_ratio_q", "sharpening_ratio_dec6",
        "nyquist_bins_full_baseline", "two_stage_budget_trials", "alias_guard_q",
        "farey_resonance_checks", "cs09_sde_truncation_witness",
    }), "p2.bls")
    tm = oracle.require_exact_int(b["baseline_multi_yr_d"], "tm", lo=2900, hi=2900)
    ts = oracle.require_exact_int(b["baseline_stage1_d"], "ts", lo=60, hi=60)
    sh = parse_canonical_rational_str(b["sharpening_ratio_q"], "sh")
    ag = parse_canonical_rational_str(b["alias_guard_q"], "ag")
    oracle.require_ok(sh == Fraction(tm, ts) and b["sharpening_ratio_dec6"] == oracle.fmt_dec_q(sh, 6), "P2_SHARP", "sharpening")
    oracle.require_exact_int(b["nyquist_bins_full_baseline"], "nyq", lo=36018, hi=36018)
    oracle.require_exact_int(b["two_stage_budget_trials"], "bud", lo=40000, hi=40000)
    oracle.require_ok(ag == Fraction(1, 125), "P2_AG", "alias guard")

    frows = b["farey_resonance_checks"]
    oracle.require_ok(type(frows) is list and len(frows) == len(oracle.FAREY_TEST_PAIRS), "P2_FAREY_LEN", "farey len")
    for idx, (row, (p1_, q1_, p2_, q2_)) in enumerate(zip(frows, oracle.FAREY_TEST_PAIRS)):
        rr = _require_exact_dict(row, frozenset({
            "r1_q", "r2_q", "unimodular_det", "gap_q", "gap_dec6", "collides_alias_guard",
        }), f"p2.f[{idx}]")
        r1 = parse_canonical_rational_str(rr["r1_q"], "r1")
        r2 = parse_canonical_rational_str(rr["r2_q"], "r2")
        gp = parse_canonical_rational_str(rr["gap_q"], "gp")
        dt = oracle.require_exact_int(rr["unimodular_det"], "det", lo=1)
        col = oracle.require_bool(rr["collides_alias_guard"], "col")
        exp_det, exp_gap = oracle.farey_separation_q(p1_, q1_, p2_, q2_)
        oracle.require_ok(
            r1 == Fraction(p1_, q1_) and r2 == Fraction(p2_, q2_)
            and dt == exp_det and gp == exp_gap
            and rr["gap_dec6"] == oracle.fmt_dec_q(exp_gap, 6)
            and col is (exp_gap < ag),
            "P2_FAREY_MATH", f"farey[{idx}]",
        )

    cs = _require_exact_dict(b["cs09_sde_truncation_witness"], frozenset({
        "peak_mes_q", "wide_sde_q", "narrow_sde_q", "sde_threshold_q",
        "wide_passes", "narrow_fails_despite_high_mes",
    }), "p2.cs09")
    pk = parse_canonical_rational_str(cs["peak_mes_q"], "pk")
    ws = parse_canonical_rational_str(cs["wide_sde_q"], "ws")
    ns = parse_canonical_rational_str(cs["narrow_sde_q"], "ns")
    st = parse_canonical_rational_str(cs["sde_threshold_q"], "st")
    oracle.require_ok(
        pk == 50 and st == Fraction(15, 2)
        and ws == oracle.sde_exact_q(pk, Fraction(10), Fraction(4))
        and ns == oracle.sde_exact_q(pk, Fraction(15), Fraction(5))
        and oracle.require_bool(cs["wide_passes"], "wp") is True
        and oracle.require_bool(cs["narrow_fails_despite_high_mes"], "nf") is True,
        "P2_CS09_MATH", "CS-09 SDE mismatch",
    )

    # 2b. Pont & 8-Gate Bayes
    pb = _require_exact_dict(p2["pont_and_eight_gate_bayes"], frozenset({
        "bin_occupancy_n", "red_to_white_ratio_q", "pont_beta_sq_q", "pont_beta_q",
        "raw_mes_q", "corrected_mes_q", "mes_threshold_q", "red_noise_collapses_below_gate",
        "prior_planet_q", "gate_retention_q", "gate_leakage_q",
        "indep_8gate_fpp_q", "indep_8gate_fpp_dec6", "indep_passes_tier_sval",
        "correlated_4gate_fpp_q", "correlated_4gate_fpp_dec6", "correlated_violates_tier_sval",
    }), "p2.pb")
    nb = oracle.require_exact_int(pb["bin_occupancy_n"], "nb", lo=12, hi=12)
    rw = parse_canonical_rational_str(pb["red_to_white_ratio_q"], "rw")
    bsq = parse_canonical_rational_str(pb["pont_beta_sq_q"], "bsq")
    bv = parse_canonical_rational_str(pb["pont_beta_q"], "bv")
    rm = parse_canonical_rational_str(pb["raw_mes_q"], "rm")
    cm = parse_canonical_rational_str(pb["corrected_mes_q"], "cm")
    mt = parse_canonical_rational_str(pb["mes_threshold_q"], "mt")
    oracle.require_ok(
        rw == Fraction(1, 2) and bsq == oracle.pont_beta_sq_q(nb, rw)
        and bv * bv == bsq and bv > 0 and rm == 14 and mt == Fraction(19, 2) and cm == rm / bv
        and oracle.require_bool(pb["red_noise_collapses_below_gate"], "rnc") is True,
        "P2_PONT_MATH", "Pont math mismatch",
    )
    pp = parse_canonical_rational_str(pb["prior_planet_q"], "pp")
    rg = parse_canonical_rational_str(pb["gate_retention_q"], "rg")
    eg = parse_canonical_rational_str(pb["gate_leakage_q"], "eg")
    fi = parse_canonical_rational_str(pb["indep_8gate_fpp_q"], "fi")
    fc = parse_canonical_rational_str(pb["correlated_4gate_fpp_q"], "fc")
    exp_fi = oracle.bayes_fpp_q(pp, 1 - pp, rg ** 8, eg ** 8)
    exp_fc = oracle.bayes_fpp_q(pp, 1 - pp, rg ** 8, (eg ** 4) * Fraction(1, 2))
    oracle.require_ok(
        pp == Fraction(1, 100) and rg == Fraction(19, 20) and eg == Fraction(1, 4)
        and fi == exp_fi and pb["indep_8gate_fpp_dec6"] == oracle.fmt_dec_q(exp_fi, 6)
        and oracle.require_bool(pb["indep_passes_tier_sval"], "ips") is True
        and fc == exp_fc and pb["correlated_4gate_fpp_dec6"] == oracle.fmt_dec_q(exp_fc, 6)
        and oracle.require_bool(pb["correlated_violates_tier_sval"], "cvs") is True,
        "P2_BAYES_MATH", "Bayes FPP mismatch",
    )

    # 2c. Harmonic despot orthogonality
    hd = _require_exact_dict(p2["harmonic_despot_orthogonality"], frozenset({
        "grid_points_n", "harmonic_modes_m", "spot_amp_ppm_q", "injected_depth_ppm_q",
        "unmasked_gram_det_q", "unmasked_recovered_depth_q", "unmasked_retention_ratio_q",
        "masked_gram_det_q", "masked_recovered_spot_q", "masked_recovered_depth_q", "masked_retention_ratio_q",
        "phase_lock_masked_gram_det_q", "phase_lock_rank_collapsed",
        "scrambled_null_l2_orig_q", "scrambled_null_l2_preserved",
    }), "p2.hd")
    oracle.require_exact_int(hd["grid_points_n"], "gn", lo=8, hi=8)
    oracle.require_exact_int(hd["harmonic_modes_m"], "hm", lo=4, hi=4)
    sa = parse_canonical_rational_str(hd["spot_amp_ppm_q"], "sa")
    dj = parse_canonical_rational_str(hd["injected_depth_ppm_q"], "dj")
    ug = parse_canonical_rational_str(hd["unmasked_gram_det_q"], "ug")
    ud = parse_canonical_rational_str(hd["unmasked_recovered_depth_q"], "ud")
    ur = parse_canonical_rational_str(hd["unmasked_retention_ratio_q"], "ur")
    mg = parse_canonical_rational_str(hd["masked_gram_det_q"], "mg")
    ms = parse_canonical_rational_str(hd["masked_recovered_spot_q"], "ms")
    md = parse_canonical_rational_str(hd["masked_recovered_depth_q"], "md")
    mr = parse_canonical_rational_str(hd["masked_retention_ratio_q"], "mr")
    lg = parse_canonical_rational_str(hd["phase_lock_masked_gram_det_q"], "lg")
    l2 = parse_canonical_rational_str(hd["scrambled_null_l2_orig_q"], "l2")
    oracle.require_ok(
        sa == 10000 and dj == 1500 and ug == 1024 and ud == 750 and ur == Fraction(1, 2)
        and mg == 512 and ms == sa and md == dj and mr == 1
        and lg == 0 and oracle.require_bool(hd["phase_lock_rank_collapsed"], "pl") is True
        and l2 == 3900 and oracle.require_bool(hd["scrambled_null_l2_preserved"], "sl2") is True,
        "P2_DESPOT_MATH", "despot math mismatch",
    )

    # 2d. O-C TTV & 2D WCS affine
    oc = _require_exact_dict(p2["oc_ttv_and_wcs_affine"], frozenset({
        "linear_drift_chi0_q", "linear_drift_chi_lin_q", "quadratic_signal_chi_lin_q",
        "quadratic_signal_chi_quad_q", "drift_1500_orbits_4s_min_q",
        "breaches_60min_wall_rescued_by_240min", "wcs_affine_det_q", "wcs_centroid_equivariant",
        "dilution_residual_bias_q", "beb_obs_depth_q", "beb_required_neighbor_depth_q",
        "beb_required_neighbor_depth_dec6", "beb_physically_excluded", "pm_10yr_300mas_shift_arcsec_q",
    }), "p2.oc")
    c0l = parse_canonical_rational_str(oc["linear_drift_chi0_q"], "c0l")
    cll = parse_canonical_rational_str(oc["linear_drift_chi_lin_q"], "cll")
    clq = parse_canonical_rational_str(oc["quadratic_signal_chi_lin_q"], "clq")
    cqq = parse_canonical_rational_str(oc["quadratic_signal_chi_quad_q"], "cqq")
    drf = parse_canonical_rational_str(oc["drift_1500_orbits_4s_min_q"], "drf")
    wdt = parse_canonical_rational_str(oc["wcs_affine_det_q"], "wdt")
    drb = parse_canonical_rational_str(oc["dilution_residual_bias_q"], "drb")
    bod = parse_canonical_rational_str(oc["beb_obs_depth_q"], "bod")
    brd = parse_canonical_rational_str(oc["beb_required_neighbor_depth_q"], "brd")
    pms = parse_canonical_rational_str(oc["pm_10yr_300mas_shift_arcsec_q"], "pms")
    exp_brd = bod * (Fraction(100) + Fraction(1, 2)) / Fraction(1, 2)
    oracle.require_ok(
        c0l == 2250 and cll == 0 and clq == 224 and cqq == 0 and drf == 100
        and oracle.require_bool(oc["breaches_60min_wall_rescued_by_240min"], "brw") is True
        and wdt == 7 and oracle.require_bool(oc["wcs_centroid_equivariant"], "weq") is True
        and drb == 0 and bod == Fraction(1, 100) and brd == exp_brd
        and oc["beb_required_neighbor_depth_dec6"] == oracle.fmt_dec_q(exp_brd, 6)
        and oracle.require_bool(oc["beb_physically_excluded"], "bex") is True
        and pms == 3,
        "P2_OC_WCS_MATH", "O-C / WCS math mismatch",
    )


def _audit_pillar3(p3: dict[str, Any]) -> None:
    _require_exact_dict(p3, frozenset({
        "all_repos_verified_public", "astronomy_spine_repos",
        "eumemic_sop10_high_signal_repos", "aletheia_gate_bridges",
    }), "p3")
    oracle.require_ok(oracle.require_bool(p3["all_repos_verified_public"], "p3.pub") is True, "P3_PUB", "public flag")
    repos = p3["astronomy_spine_repos"]
    oracle.require_ok(type(repos) is list and len(repos) == len(oracle.ASTRONOMY_SPINE_REPOS), "P3_SPINE_LEN", "spine len")
    for idx, (row, exp) in enumerate(zip(repos, oracle.ASTRONOMY_SPINE_REPOS)):
        rr = _require_exact_dict(row, frozenset({
            "repo", "is_private", "main_commit", "branch_count", "open_pr_count", "merged_pr_count", "unmerged_seam",
        }), f"p3.sp[{idx}]")
        oracle.require_ok(
            rr["repo"] == exp["repo"]
            and oracle.require_bool(rr["is_private"], f"sp[{idx}].priv") is False
            and rr["main_commit"] == exp["main_commit"]
            and oracle.require_exact_int(rr["branch_count"], f"sp[{idx}].br", lo=1) == exp["branch_count"]
            and oracle.require_exact_int(rr["open_pr_count"], f"sp[{idx}].op", lo=0) == exp["open_pr_count"]
            and oracle.require_exact_int(rr["merged_pr_count"], f"sp[{idx}].mp", lo=0) == exp["merged_pr_count"]
            and rr["unmerged_seam"] == exp["unmerged_seam"],
            "P3_SPINE_PIN", f"spine[{idx}] mismatch",
        )
    oracle.require_ok(
        p3["eumemic_sop10_high_signal_repos"] == [
            "eumemic/exact-dft-bounds", "eumemic/integer-mult-bounds",
            "eumemic/stdhttp-verify", "eumemic/errata-findings",
        ],
        "P3_SOP10_LIST", "SOP-10 list mismatch",
    )
    brs = p3["aletheia_gate_bridges"]
    oracle.require_ok(type(brs) is list and tuple(brs) == _EXPECTED_ALETHEIA_GATE_BRIDGES, "P3_BR_PIN", "aletheia_gate_bridges mismatch")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed field-complete semantic + algebraic auditor enforced on BOTH FR1 and FR0."""
    oracle.require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")
    oracle.validate_strict_json_tree(payload, "payload")
    _require_exact_dict(payload, _PAYLOAD_KEYS, "payload")
    oracle.require_ok(payload["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema_version")
    oracle.require_ok(payload["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "track_id")
    oracle.require_ok(payload["oracle_class"] == "exact", "SCHEMA_MISMATCH", "oracle_class")
    oracle.require_ok(payload["novelty_classification"] == "N1", "SCHEMA_MISMATCH", "novelty")
    oracle.require_exact_int(payload["n2_claims"], "n2_claims", lo=0, hi=0)

    prov = _require_exact_dict(payload["external_provenance"], frozenset({
        "pinned_external_count", "pinned_external_files", "upstream_bridges_count", "upstream_expedition_bridges",
    }), "external_provenance")
    n_ext = oracle.require_exact_int(prov["pinned_external_count"], "n_ext", lo=16, hi=16)
    exts = prov["pinned_external_files"]
    oracle.require_ok(type(exts) is list and len(exts) == n_ext, "PROV_EXT_LEN", "16 external pins")
    for idx, row in enumerate(exts):
        _require_exact_dict(row, frozenset({"id", "repo", "relpath", "bytes", "sha256"}), f"ext[{idx}]")
    oracle.require_ok(
        [(r["id"], r["repo"], r["relpath"], r["bytes"], r["sha256"]) for r in exts]
        == [(r["id"], r["repo"], r["relpath"], r["bytes"], r["sha256"]) for r in oracle.PINNED_EXTERNAL_FILES],
        "PROV_EXT_PIN", "external file pins mismatch",
    )

    n_up = oracle.require_exact_int(prov["upstream_bridges_count"], "n_up", lo=6, hi=6)
    ups = prov["upstream_expedition_bridges"]
    oracle.require_ok(type(ups) is list and len(ups) == n_up, "PROV_UP_LEN", "6 upstream pins")
    for idx, row in enumerate(ups):
        _require_exact_dict(row, frozenset({"track", "cert_file", "cert_sha256", "bridge"}), f"up[{idx}]")
    oracle.require_ok(
        [(r["track"], r["cert_file"], r["cert_sha256"], r["bridge"]) for r in ups]
        == [(r["track"], r["cert_file"], r["cert_sha256"], r["bridge"]) for r in oracle.UPSTREAM_EXPEDITION_CERTS],
        "PROV_UP_PIN", "upstream cert pins mismatch",
    )

    pa = _require_exact_dict(payload["pinned_artifacts"], frozenset({
        "lean_source", "lean_source_sha256", "lean_toolchain", "lean_toolchain_sha256",
        "lakefile_sha256", "lean_theorem_count", "lean_theorem_names",
    }), "pinned_artifacts")
    oracle.require_ok(pa["lean_source"] == "ExoplanetsFrontierOperators.lean", "SCHEMA_MISMATCH", "lean_source")
    oracle.require_ok(pa["lean_toolchain"] == oracle.EXPECTED_LEAN_TOOLCHAIN, "SCHEMA_MISMATCH", "lean_toolchain")
    oracle.require_ok(
        (pa["lean_source_sha256"], pa["lean_toolchain_sha256"], pa["lakefile_sha256"])
        == (oracle.PINNED_LEAN_SOURCE_SHA256, oracle.PINNED_LEAN_TOOLCHAIN_SHA256, oracle.PINNED_LAKEFILE_SHA256),
        "PINNED_SHA_MISMATCH", "pinned artifact SHA mismatch",
    )
    thm_n = oracle.require_exact_int(pa["lean_theorem_count"], "thm_n", lo=len(oracle.LEAN_THEOREM_NAMES), hi=len(oracle.LEAN_THEOREM_NAMES))
    thms = pa["lean_theorem_names"]
    oracle.require_ok(type(thms) is list and tuple(thms) == oracle.LEAN_THEOREM_NAMES, "THEOREM_LIST_MISMATCH", "lean_theorem_names")

    _audit_pillar1(payload["pillar1_sop9_exoplanets_frontier_audit"])
    _audit_pillar2(payload["pillar2_exact_astrophysical_operators"])
    _audit_pillar3(payload["pillar3_sop10_astronomy_spine_convergence"])

    return {
        "secondary_audit_passed": True,
        "external_files_pinned": n_ext,
        "upstream_bridges_pinned": n_up,
        "lean_theorem_count": thm_n,
    }


def _load_track_artifacts(track_dir: Path) -> tuple[str, str, str, dict[str, Any]]:
    lean_p = track_dir / "ExoplanetsFrontierOperators.lean"
    tc_p = track_dir / "lean-toolchain"
    lk_p = track_dir / "lakefile.toml"
    tc_raw = read_regular_bytes_capped(tc_p, "lean-toolchain")
    lk_raw = read_regular_bytes_capped(lk_p, "lakefile.toml")
    try:
        tc_str = tc_raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise oracle.S103Error("INVALID_UTF8", "lean-toolchain invalid UTF-8") from exc
    oracle.require_ok(tc_str == oracle.EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", f"got {tc_str!r}")
    live = verify_lean4_file_live(lean_p)
    return live["lean_source_sha256"], oracle.sha256_hex(tc_raw), oracle.sha256_hex(lk_raw), live


def verify_certificate_dict(cert: Any, *, full_replay: bool = True, track_dir: Path | None = None) -> dict[str, Any]:
    oracle.require_bool(full_replay, "full_replay")
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    oracle.validate_strict_json_tree(cert, "certificate")
    _require_exact_dict(cert, _ENVELOPE_KEYS, "certificate")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "envelope schema_version")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "envelope track_id")
    p_sha = oracle.require_hex64(cert["payload_sha256"], "payload_sha256")
    c_sha = oracle.require_hex64(cert["certificate_sha256"], "certificate_sha256")
    payload = cert["payload"]
    sec = secondary_audit_payload(payload)
    recomp_p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    oracle.require_ok(hmac.compare_digest(p_sha, recomp_p_sha), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")
    core = {"schema_version": cert["schema_version"], "track_id": cert["track_id"], "payload_sha256": p_sha, "payload": payload}
    recomp_c_sha = oracle.sha256_hex(oracle.canonical_json_bytes(core))
    oracle.require_ok(hmac.compare_digest(c_sha, recomp_c_sha), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")
    receipt: dict[str, Any] = {
        "valid": True,
        "track_id": oracle.TRACK_ID,
        "full_replay": full_replay,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "secondary_audit": sec,
    }
    if full_replay:
        tdir = _THIS_DIR if track_dir is None else track_dir
        lean_sha, tc_sha, lk_sha, live = _load_track_artifacts(tdir)
        pa = payload["pinned_artifacts"]
        oracle.require_ok(hmac.compare_digest(lean_sha, pa["lean_source_sha256"]), "LEAN_SHA_MISMATCH", "Lean SHA mismatch")
        oracle.require_ok(hmac.compare_digest(tc_sha, pa["lean_toolchain_sha256"]), "TOOLCHAIN_SHA_MISMATCH", "toolchain SHA mismatch")
        oracle.require_ok(hmac.compare_digest(lk_sha, pa["lakefile_sha256"]), "LAKEFILE_SHA_MISMATCH", "lakefile SHA mismatch")
        expected_cert = oracle.build_certificate()
        oracle.require_ok(hmac.compare_digest(c_sha, expected_cert["certificate_sha256"]), "REPLAY_MISMATCH", "full replay mismatch")
        receipt["lean_live"] = live
    return receipt


def verify_external_pins_on_disk(clones_root: Path, expedition_root: Path) -> dict[str, Any]:
    cr = _check_no_symlink_components(_check_path_str(clones_root, "clones_root"), "clones_root")
    er = _check_no_symlink_components(_check_path_str(expedition_root, "expedition_root"), "expedition_root")
    for row in oracle.PINNED_EXTERNAL_FILES:
        raw = read_regular_bytes_capped(cr / row["relpath"], row["id"])
        oracle.require_ok(
            len(raw) == row["bytes"] and hmac.compare_digest(oracle.sha256_hex(raw), row["sha256"]),
            "EXT_PIN_MISMATCH", f"mismatch on {row['id']}",
        )
    for row in oracle.UPSTREAM_EXPEDITION_CERTS:
        raw = read_regular_bytes_capped(er / row["cert_file"], row["track"])
        oracle.require_ok(
            hmac.compare_digest(oracle.sha256_hex(raw), row["cert_sha256"]),
            "UPSTREAM_PIN_MISMATCH", f"mismatch on {row['track']}",
        )
    return {
        "status": "PINS_VERIFIED",
        "external_files_verified": len(oracle.PINNED_EXTERNAL_FILES),
        "upstream_certs_verified": len(oracle.UPSTREAM_EXPEDITION_CERTS),
    }


def _parse_cli_args(argv: list[str]) -> dict[str, Any]:
    oracle.require_ok(type(argv) is list, "INVALID_ARGV", "argv must be list")
    mode: str | None = None
    target: str | None = None
    clones_root: str | None = None
    exp_root: str | None = None
    as_json = False
    i = 0
    while i < len(argv):
        arg = oracle.require_exact_str(argv[i], f"argv[{i}]")
        oracle.require_ok("\x00" not in arg, "NUL_BYTE_FORBIDDEN", "NUL in argv")
        try:
            arg.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise oracle.S103Error("INVALID_UTF8_SURROGATE", "invalid utf-8 in argv") from exc
        if arg == "--json":
            oracle.require_ok(not as_json, "DUPLICATE_FLAG", "duplicate --json")
            as_json = True
            i += 1
            continue
        if arg == "--standalone":
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode")
            mode = "standalone"
            i += 1
            continue
        if arg == "--verify-pins":
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode")
            mode = "verify_pins"
            i += 1
            continue
        if arg in ("--check", "--write"):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode")
            oracle.require_ok(i + 1 < len(argv), "MISSING_PATH_ARG", f"missing path for {arg}")
            val = oracle.require_exact_str(argv[i + 1], f"{arg}_path")
            oracle.require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", "NUL in path arg")
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = arg[2:]
            target = val
            i += 2
            continue
        if arg.startswith("--check=") or arg.startswith("--write="):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode")
            flag, val = arg.split("=", 1)
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = flag[2:]
            target = val
            i += 1
            continue
        if arg in ("--clones-root", "--expedition-root"):
            oracle.require_ok(i + 1 < len(argv), "MISSING_PATH_ARG", f"missing path for {arg}")
            val = oracle.require_exact_str(argv[i + 1], f"{arg}_path")
            oracle.require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", "NUL in root arg")
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid root {val!r}")
            if arg == "--clones-root":
                oracle.require_ok(clones_root is None, "DUPLICATE_FLAG", "duplicate --clones-root")
                clones_root = val
            else:
                oracle.require_ok(exp_root is None, "DUPLICATE_FLAG", "duplicate --expedition-root")
                exp_root = val
            i += 2
            continue
        raise oracle.S103Error("UNKNOWN_FLAG", f"unknown flag: {arg!r}")
    return {
        "mode": "default" if mode is None else mode,
        "target": target,
        "clones_root": clones_root,
        "expedition_root": exp_root,
        "as_json": as_json,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        opts = _parse_cli_args(sys.argv[1:] if argv is None else argv)
        mode = opts["mode"]
        if mode == "standalone":
            sys.stdout.write(oracle.canonical_json_bytes(oracle.build_certificate()).decode("ascii"))
            return 0
        if mode == "verify_pins":
            oracle.require_ok(opts["clones_root"] is not None and opts["expedition_root"] is not None, "MISSING_PATH_ARG", "verify-pins requires --clones-root and --expedition-root")
            res = verify_external_pins_on_disk(Path(opts["clones_root"]), Path(opts["expedition_root"]))
            if opts["as_json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"PINS_OK ext={res['external_files_verified']} up={res['upstream_certs_verified']}\n")
            return 0
        if mode == "write":
            cert = oracle.build_certificate()
            res = verify_certificate_dict(cert, full_replay=True)
            out_p = write_regular_bytes_atomic_0600(opts["target"], oracle.canonical_json_bytes(cert), "write_target")
            if opts["as_json"]:
                sys.stdout.write(oracle.canonical_json_bytes({"written": True, "path": str(out_p), **res}).decode("ascii"))
            else:
                sys.stdout.write(f"WROTE {out_p} sha256={res['certificate_sha256']}\n")
            return 0
        if mode == "check":
            raw = read_regular_bytes_capped(opts["target"], "check_target", max_bytes=MAX_JSON_BYTES)
            cert = parse_strict_json_bytes(raw, "check_target", require_canonical=True)
            res = verify_certificate_dict(cert, full_replay=True)
        else:
            res = verify_certificate_dict(oracle.build_certificate(), full_replay=True)
        if opts["as_json"]:
            sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
        else:
            sys.stdout.write(f"OK {res['track_id']} cert_sha256={res['certificate_sha256']}\n")
        return 0
    except oracle.S103Error as exc:
        err_obj = {"valid": False, "code": exc.code, "detail": exc.detail}
        sys.stderr.write(oracle.canonical_json_bytes(err_obj).decode("ascii"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
