#!/usr/bin/env python3
"""Track S99: Zone-B Hardened Field-Complete Independent Verifier & R12 Lean Gate.

Independently recomputes every mathematical invariant across Pillars 1-4 in
pure Z/Q without invoking build_certificate(), enforces exact nested keysets
and strict builtin types on both FR0 and SEC (zero re-signed bypasses),
hardens all CLI/JSON/file I/O via atomic dir_fd step-down + $PWD symlink
ancestor checks + iterative depth/int-bit-bounded JSON validation, and
verifies OptiFabFiveOrgConvergence.lean via R12 static scanning and
env-scrubbed zero-TOCTOU live `lean --stdin` axiom auditing.
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
import shutil
import stat
import subprocess
import sys
from typing import Any

TRACK_DIR = Path(__file__).resolve().parent
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import s99_optifab_convergence_oracle as oracle  # noqa: E402

DEFAULT_CERT_PATH = TRACK_DIR / "s99_optifab_convergence_certificate.json"
DEFAULT_LEAN_PATH = TRACK_DIR / oracle.LEAN_COMPANION_FILE
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_LEAN_BYTES = 512 * 1024
MAX_JSON_DEPTH = 64
MAX_INT_BITS = 2048
MAX_INT_DIGITS = 620
READ_CHUNK_BYTES = 65_536

ALLOWED_LEAN_AXIOMS: frozenset[str] = frozenset({"propext", "Quot.sound"})
SAFE_LEAN_ENV_KEYS: tuple[str, ...] = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
HEX_LOWER: frozenset[str] = frozenset("0123456789abcdef")
AXIOM_LINE_RE = re.compile(r"^'([^']+)' depends on axioms: \[([^\]]*)\]$")
NO_AXIOM_LINE_RE = re.compile(r"^'([^']+)' does not depend on any axioms$")
THEOREM_DECL_RE = re.compile(
    r"(?m)^\s*(?:(?:private|protected|noncomputable|unsafe|partial)\s+)*(?:theorem|lemma)\s+([A-Za-z0-9_']+)\b"
)

FORBIDDEN_LEAN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("import_stmt", re.compile(r"(?m)^\s*(?:(?:public|private|meta)\s+)*import\b")),
    ("sorry_token", re.compile(r"\b(?:sorry|sorryAx|mkSorry)\b")),
    ("admit_token", re.compile(r"\badmit\b")),
    ("axiom_decl", re.compile(r"\baxiom\b")),
    ("unsafe_kw", re.compile(r"\bunsafe\b")),
    ("implemented_by", re.compile(r"\bimplemented_by\b")),
    ("extern_attr", re.compile(r"\bextern\b")),
    ("csimp_kw", re.compile(r"\bcsimp\b")),
    ("noncomputable_kw", re.compile(r"\bnoncomputable\b")),
    ("native_decide", re.compile(r"\bnative_decide\b")),
    ("plus_native", re.compile(r"(?<!\w)\+\s*native\b")),
    ("config_assign", re.compile(r"\bconfig\s*:=")),
    ("native_nonfalse", re.compile(r"\bnative\b(?!\s*:=\s*(?:Bool\.)?false\s*[),}])")),
    ("decide_config_type", re.compile(r"\bDecide(?:Config|\.Config)\b")),
    ("of_reduce_bool_nat", re.compile(r"\b(?:Lean\.)?ofReduce(?:Bool|Nat)\b")),
    ("trust_compiler", re.compile(r"\b(?:Lean\.)?trustCompiler\b")),
    ("lean_namespace", re.compile(r"\bLean\s*\.")),
    ("classical_escape", re.compile(r"\bClassical\.(?:choice|em|byContradiction)\b")),
    ("debug_escape", re.compile(r"\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b")),
    ("set_option", re.compile(r"\bset_option\b")),
    ("dbg_ffi_escape", re.compile(r"\b(?:dbg_trace|dbgTrace|dbgTraceVal|dbgTraceValId|dbgTraceIfShared|dbgSleep|dbgStackTrace|panicWithPosWithDecl)\b")),
    ("panic_unreachable", re.compile(r"\b(?:panic|unreachable)!(?![\w'!?])")),
    ("attr_trust_escape", re.compile(r"(?:@|(?<!\.)\battribute\s*)\[[^\]]*\b(?:export|init|builtin_init|term_elab|command_elab|tactic|macro|macro_rules)\b")),
    ("initialize_kw", re.compile(r"\b(?:builtin_)?initialize\b")),
    ("partial_kw", re.compile(r"\bpartial\b")),
    ("opaque_kw", re.compile(r"\bopaque\b")),
    ("run_cmd_meta", re.compile(r"\brun_(?:cmd|meta)\b")),
    ("hash_meta_cmd", re.compile(r"#(?:guard(?:_msgs)?|exit|check|synth|eval!?|reduce|print)(?![\w'!?])")),
    ("meta_macro_elab", re.compile(r"(?m)^\s*(?:(?:local|scoped|private|protected)\s+)*(?:macro(?:_rules)?|elab(?:_rules)?|syntax|declare_syntax_cat|notation|prefix|infix[lr]?|postfix|instance)\b")),
    ("tautology_true", re.compile(r":\s*True\s*:=")),
)


class VerificationError(ValueError):
    """Fail-closed typed error for Zone-B, cryptographic, algebraic, and Lean checks."""


def require_ok(cond: bool, msg: str) -> None:
    if not cond:
        raise VerificationError(msg)


def _require_eq_int(val: Any, expected: int, label: str) -> None:
    require_ok(type(val) is int, f"{label}: strict int required")
    require_ok(val == expected, f"{label}: int mismatch")


def _require_eq_bool(val: Any, expected: bool, label: str) -> None:
    require_ok(val is expected, f"{label}: bool mismatch")


def _require_eq_str(val: Any, expected: str, label: str) -> None:
    require_ok(val == expected, f"{label}: str mismatch")


def _require_eq_int_list(val: Any, expected: list[int], label: str) -> None:
    require_ok(type(val) is list, f"{label}: list required")
    require_ok(len(val) == len(expected), f"{label}: list len mismatch")
    for idx, (got_item, exp_item) in enumerate(zip(val, expected)):
        _require_eq_int(got_item, exp_item, f"{label}[{idx}]")


def _require_eq_str_list(val: Any, expected: list[str], label: str) -> None:
    require_ok(type(val) is list, f"{label}: list required")
    require_ok(len(val) == len(expected), f"{label}: list len mismatch")
    for idx, (got_item, exp_item) in enumerate(zip(val, expected)):
        _require_eq_str(got_item, exp_item, f"{label}[{idx}]")


def _require_sha256_hex(val: Any, label: str) -> str:
    require_ok(type(val) is str, f"{label}: must be strict str")
    require_ok(len(val) == 64, f"{label}: digest length must be 64")
    require_ok(all(ch in HEX_LOWER for ch in val), f"{label}: digest must be lowercase ASCII hex")
    return val


def _check_keys(obj: Any, expected: set[str], label: str) -> dict[str, Any]:
    require_ok(type(obj) is dict, f"{label}: must be strict dict")
    require_ok(set(obj.keys()) == expected, f"{label}: key mismatch")
    return obj


def _require_utf8_str(val: str, label: str) -> None:
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise VerificationError(f"{label}: lone surrogate forbidden") from exc


def validate_json_tree_iterative(obj: Any, label: str) -> None:
    """Iterative Zone-B validator blocking floats, subclasses, surrogates, depth > 64, huge ints."""
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        require_ok(depth <= MAX_JSON_DEPTH, f"{label}: JSON nesting depth exceeds {MAX_JSON_DEPTH}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                require_ok(type(k) is str, f"{label}: non-str dict key")
                _require_utf8_str(k, label)
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is int:
            require_ok(cur.bit_length() <= MAX_INT_BITS, f"{label}: integer bit length exceeds {MAX_INT_BITS}")
        elif t is str:
            _require_utf8_str(cur, label)
        elif t is bool or cur is None:
            continue
        else:
            raise VerificationError(f"{label}: forbidden JSON value type {t.__name__}")


def _parse_q_strict(val: Any, label: str) -> Fraction:
    require_ok(type(val) is str, f"{label}: rational string required")
    parts = val.split("/")
    require_ok(len(parts) <= 2, f"{label}: invalid rational format")
    for part in parts:
        require_ok(len(part) > 0, f"{label}: empty rational component")
        body = part[1:] if part[0] == "-" else part
        require_ok(len(body) > 0, f"{label}: empty rational digits")
        require_ok(len(body) <= MAX_INT_DIGITS, f"{label}: rational digits exceed {MAX_INT_DIGITS}")
        require_ok(all("0" <= ch <= "9" for ch in body), f"{label}: non-ascii digits")
    num = int(parts[0])
    den = 1 if len(parts) == 1 else int(parts[1])
    require_ok(den > 0, f"{label}: non-positive denominator")
    frac = Fraction(num, den)
    require_ok(oracle.fmt_q(frac) == val, f"{label}: non-canonical rational string")
    return frac


def _require_eq_q(val: Any, expected: Fraction, label: str) -> None:
    require_ok(_parse_q_strict(val, label) == expected, f"{label}: rational mismatch")


def _no_dup_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        require_ok(k not in out, f"duplicate JSON key: {k}")
        out[k] = v
    return out


def _forbid_float_token(token: str) -> Any:
    raise VerificationError(f"float literal forbidden: {token}")


def _forbid_constant_token(token: str) -> Any:
    raise VerificationError(f"non-finite JSON constant forbidden: {token}")


def _parse_capped_int_token(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    require_ok(len(digits) <= MAX_INT_DIGITS, f"integer token exceeds {MAX_INT_DIGITS} digits")
    val = int(token)
    require_ok(val.bit_length() <= MAX_INT_BITS, f"integer bit length exceeds {MAX_INT_BITS}")
    return val


# ---------------------------------------------------------------------------
# Atomic dir_fd Step-Down & $PWD Symlink Ancestor Hardening (Zone-B I/O)
# ---------------------------------------------------------------------------

def _is_symlink_at(dfd: int, name: str) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(name, dir_fd=dfd).st_mode)
    except OSError:
        return False


def _check_pwd_no_symlinks() -> None:
    pwd = os.environ.get("PWD")
    if pwd is None:
        return
    if not os.path.isabs(pwd):
        return
    _require_utf8_str(pwd, "PWD")
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in Path(pwd).parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise VerificationError(f"symlink ancestor in PWD forbidden: {comp}") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
    finally:
        os.close(cur_fd)


def _open_parent_dir_fd(path: Path, label: str) -> tuple[int, str]:
    raw_s = str(path)
    _require_utf8_str(raw_s, label)
    require_ok("\x00" not in raw_s, f"{label}: NUL byte in path")
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    require_ok(len(parts) > 0, f"{label}: empty path")
    require_ok(parts[-1] not in ("", ".", ".."), f"{label}: invalid leaf")
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            require_ok(comp != "..", f"{label}: parent traversal forbidden")
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                raise VerificationError(f"{label}: unsafe or missing ancestor {comp}") from exc
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, leaf
    except BaseException:
        os.close(cur_fd)
        raise


def _read_regular_bytes_strict(path: Path, max_bytes: int, label: str) -> bytes:
    parent_fd, leaf = _open_parent_dir_fd(path, label)
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        try:
            fd = os.open(leaf, flags, dir_fd=parent_fd)
        except OSError as exc:
            raise VerificationError(f"{label}: cannot open regular file safely ({exc})") from exc
    finally:
        os.close(parent_fd)
    try:
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), f"{label}: not a regular file")
        require_ok(st.st_nlink == 1, f"{label}: hardlinked file forbidden")
        require_ok((st.st_mode & 0o022) == 0, f"{label}: group/world-writable file forbidden")
        chunks: list[bytes] = []
        total = 0
        while True:
            buf = os.read(fd, READ_CHUNK_BYTES)
            if not buf:
                break
            total += len(buf)
            require_ok(total <= max_bytes, f"{label}: stream exceeds max size {max_bytes}")
            chunks.append(buf)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _read_json_strict(path: Path, label: str) -> dict[str, Any]:
    raw = _read_regular_bytes_strict(path, MAX_JSON_BYTES, label)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"{label}: invalid UTF-8") from exc
    try:
        obj = json.loads(
            text,
            object_pairs_hook=_no_dup_pairs_hook,
            parse_int=_parse_capped_int_token,
            parse_float=_forbid_float_token,
            parse_constant=_forbid_constant_token,
        )
    except VerificationError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise VerificationError(f"{label}: invalid JSON ({exc})") from exc
    require_ok(type(obj) is dict, f"{label}: root must be JSON object")
    validate_json_tree_iterative(obj, label)
    canonical_pretty = (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    require_ok(raw == canonical_pretty, f"{label}: non-canonical JSON formatting")
    return obj


def _write_json_atomic_0600(path: Path, obj: dict[str, Any]) -> None:
    validate_json_tree_iterative(obj, "write_cert")
    data = (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    parent_fd, leaf = _open_parent_dir_fd(path, "write_cert")
    try:
        try:
            st_ex = os.lstat(leaf, dir_fd=parent_fd)
            require_ok(stat.S_ISREG(st_ex.st_mode), "refusing to overwrite non-regular file or symlink")
            require_ok(st_ex.st_nlink == 1, "refusing to overwrite hardlinked file")
        except FileNotFoundError:
            pass
        tmp_name = f".{leaf}.tmp.{os.getpid()}.{secrets.token_hex(8)}"
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
        fd = os.open(tmp_name, flags, 0o600, dir_fd=parent_fd)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            written = 0
            while written < len(view):
                written += os.write(fd, view[written:])
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_name, leaf, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


# ---------------------------------------------------------------------------
# R12 Static & Env-Scrubbed Zero-TOCTOU Live Lean 4.36.0 Verification
# ---------------------------------------------------------------------------

def _strip_lean_comments(src: str) -> str:
    """Strip nested Lean block comments /- ... -/ and line comments -- ... safely."""
    out: list[str] = []
    i = 0
    n = len(src)
    depth = 0
    while i < n:
        if depth == 0 and src[i : i + 2] == "--":
            nl = src.find("\n", i)
            if nl < 0:
                break
            out.append("\n")
            i = nl + 1
            continue
        if src[i : i + 2] == "/-":
            depth += 1
            i += 2
            continue
        if src[i : i + 2] == "-/":
            require_ok(depth > 0, "unmatched Lean block comment closer")
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(src[i])
        i += 1
    require_ok(depth == 0, "unterminated Lean block comment")
    return "".join(out)


def static_scan_lean(src: str, expected_theorems: tuple[str, ...] = oracle.LEAN_THEOREM_NAMES) -> list[str]:
    require_ok("\x00" not in src, "NUL byte in Lean source")
    stripped = _strip_lean_comments(src)
    require_ok('"' not in stripped, "string literal forbidden in pure-Init Lean companion")
    require_ok("«" not in stripped, "left guillemet identifier escape forbidden")
    require_ok("»" not in stripped, "right guillemet identifier escape forbidden")
    for name, pat in FORBIDDEN_LEAN_PATTERNS:
        require_ok(pat.search(stripped) is None, f"forbidden Lean construct matched: {name}")
    found = THEOREM_DECL_RE.findall(stripped)
    require_ok(len(found) > 0, "Lean companion declares zero theorems")
    require_ok(len(found) == len(set(found)), "duplicate theorem declaration in Lean companion")
    require_ok(set(found) == set(expected_theorems), "Lean theorem set mismatch")
    return found


def _parse_lean_axiom_stdout(
    stdout: str,
    expected_theorems: tuple[str, ...] = oracle.LEAN_THEOREM_NAMES,
    namespace: str = oracle.LEAN_NAMESPACE,
) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m_ax = AXIOM_LINE_RE.match(line)
        if m_ax:
            thm = m_ax.group(1)
            axioms = [a.strip() for a in m_ax.group(2).split(",") if a.strip()]
            for ax in axioms:
                require_ok(ax in ALLOWED_LEAN_AXIOMS, f"forbidden Lean axiom {ax} on {thm}")
            seen[thm] = axioms
            continue
        m_no = NO_AXIOM_LINE_RE.match(line)
        if m_no:
            seen[m_no.group(1)] = []
            continue
        raise VerificationError(f"unexpected Lean stdout line: {line}")
    expected_fq = {f"{namespace}.{t}" for t in expected_theorems}
    require_ok(set(seen.keys()) == expected_fq, "Lean #print axioms theorem coverage mismatch")
    return seen


def _find_lean_bin() -> str | None:
    found = shutil.which("lean")
    if found:
        return found
    home_env = os.environ.get("HOME")
    if not home_env:
        return None
    for rel in (".local/bin/lean", ".elan/bin/lean"):
        cand = Path(home_env) / rel
        if cand.is_file() and os.access(str(cand), os.X_OK):
            return str(cand)
    return None


def verify_lean_companion(
    lean_path: Path = DEFAULT_LEAN_PATH,
    require_live: bool = False,
) -> dict[str, Any]:
    raw = _read_regular_bytes_strict(lean_path, MAX_LEAN_BYTES, "lean_companion")
    actual_sha = hashlib.sha256(raw).hexdigest()
    require_ok(hmac.compare_digest(actual_sha, oracle.PINNED_LEAN_SHA256), "Lean companion SHA-256 mismatch")
    src = raw.decode("utf-8")
    theorems = static_scan_lean(src, oracle.LEAN_THEOREM_NAMES)

    must_run_live = require_live or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1"
    lean_bin = _find_lean_bin()
    if lean_bin is None:
        require_ok(not must_run_live, "Lean binary unavailable while live Lean verification required")
        return {
            "static_scan_passed": True,
            "live_lean_executed": False,
            "theorem_count": len(theorems),
            "sha256": actual_sha,
        }

    clean_env = {k: os.environ[k] for k in SAFE_LEAN_ENV_KEYS if k in os.environ}
    v_proc = subprocess.run(
        [lean_bin, "--version"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
        env=clean_env,
    )
    require_ok(v_proc.returncode == 0 and "4.36.0" in v_proc.stdout, "live lean 4.36.0 version mismatch")

    probe = (
        src
        + "\n"
        + "\n".join(
            f"#print axioms {oracle.LEAN_NAMESPACE}.{t}"
            for t in oracle.LEAN_THEOREM_NAMES
        )
        + "\n"
    )
    proc = subprocess.run(
        [lean_bin, "--stdin"],
        input=probe,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
        env=clean_env,
    )
    require_ok(proc.returncode == 0, f"live lean --stdin failed (rc={proc.returncode})")
    require_ok(proc.stderr.strip() == "", "live lean --stdin emitted stderr")
    axioms_map = _parse_lean_axiom_stdout(proc.stdout, oracle.LEAN_THEOREM_NAMES, oracle.LEAN_NAMESPACE)
    return {
        "static_scan_passed": True,
        "live_lean_executed": True,
        "theorem_count": len(axioms_map),
        "sha256": actual_sha,
        "axioms_by_theorem": axioms_map,
    }


# ---------------------------------------------------------------------------
# Independent Pure-Z/Q Payload Recomputation (FR0 & SEC — Zero Hollow Checks!)
# ---------------------------------------------------------------------------

def _verify_pillar1(p1: Any) -> None:
    d = _check_keys(
        p1,
        {
            "upstream_commit",
            "upstream_version",
            "start_headroom_ppm",
            "defect_14_1_outage_constant",
            "defect_14_2_outage_fixed_heat",
            "defect_14_3_equal_objective_headroom_decay",
            "defect_14_4_missing_wellformed_predicate",
            "defect_14_5_asymmetric_distance_and_recovery",
            "all_five_defects_certified",
        },
        "pillar_1",
    )
    _require_eq_str(d["upstream_commit"], oracle.UPSTREAM_OPTIFAB_PIN["commit"], "p1.commit")
    _require_eq_str(d["upstream_version"], oracle.UPSTREAM_OPTIFAB_PIN["version"], "p1.version")
    _require_eq_bool(d["all_five_defects_certified"], True, "p1.flag")

    p = oracle.OPTIFAB_PLANT
    sc = oracle.OPTIFAB_SCENARIO
    g0 = oracle.START_GENOME
    m0 = oracle.margins_v031(p, sc, g0)
    hr0 = oracle.headroom_ppm(oracle.LIMIT_PPM, m0)
    _require_eq_int(d["start_headroom_ppm"], hr0, "p1.start_hr")

    # #14.1
    d1 = _check_keys(
        d["defect_14_1_outage_constant"],
        {
            "upstream_status",
            "double_subtracted_const_kw_q",
            "double_subtracted_const_kw_dec4",
            "eta_v030_buggy_ppm",
            "eta_v031_repaired_ppm",
            "eta_delta_ppm",
        },
        "p1.14_1",
    )
    _require_eq_str(d1["upstream_status"], "fixed_in_v0_3_1_reproduced", "p1.14_1.status")
    c_kw = Fraction(
        (p["aux_w"] + p["other_w"]) * p["loop_cop_milli"] - p["passive_w"] * 1_000,
        p["loop_cop_milli"] * 1_000,
    )
    _require_eq_q(d1["double_subtracted_const_kw_q"], c_kw, "p1.14_1.const_q")
    _require_eq_str(d1["double_subtracted_const_kw_dec4"], oracle.fmt_dec(c_kw, 4), "p1.14_1.const_dec4")
    eta30 = oracle.objective_v030_buggy(p, sc, g0)
    eta31 = oracle.objective_v031_repaired(p, sc, g0)
    _require_eq_int(d1["eta_v030_buggy_ppm"], eta30, "p1.14_1.eta30")
    _require_eq_int(d1["eta_v031_repaired_ppm"], eta31, "p1.14_1.eta31")
    _require_eq_int(d1["eta_delta_ppm"], eta31 - eta30, "p1.14_1.delta")

    # #14.2
    d2 = _check_keys(
        d["defect_14_2_outage_fixed_heat"],
        {
            "upstream_status",
            "qfix_start_uw",
            "omitted_heat_kwh_q",
            "omitted_heat_kwh_dec4",
            "start_outage_v030_buggy_ppm",
            "start_outage_v031_repaired_ppm",
            "start_outage_delta_ppm",
            "false_admit_pcm_kwh",
            "false_admit_v030_ppm",
            "false_admit_v031_ppm",
        },
        "p1.14_2",
    )
    _require_eq_str(d2["upstream_status"], "fixed_in_v0_3_1_reproduced", "p1.14_2.status")
    qfix0 = oracle.q_fix(p, g0)
    omitted = Fraction(qfix0 * sc["outage_min"], 60_000_000_000)
    out30 = oracle.outage_margin_v030_buggy(p, sc, g0)
    out31 = oracle.outage_margin_v031_repaired(p, sc, g0)
    g_ov = dict(g0, pcm_kwh=2_350)
    ov30 = oracle.outage_margin_v030_buggy(p, sc, g_ov)
    ov31 = oracle.outage_margin_v031_repaired(p, sc, g_ov)
    _require_eq_int(d2["qfix_start_uw"], qfix0, "p1.14_2.qfix")
    _require_eq_q(d2["omitted_heat_kwh_q"], omitted, "p1.14_2.omitted_q")
    _require_eq_str(d2["omitted_heat_kwh_dec4"], oracle.fmt_dec(omitted, 4), "p1.14_2.omitted_dec4")
    _require_eq_int(d2["start_outage_v030_buggy_ppm"], out30, "p1.14_2.out30")
    _require_eq_int(d2["start_outage_v031_repaired_ppm"], out31, "p1.14_2.out31")
    _require_eq_int(d2["start_outage_delta_ppm"], out31 - out30, "p1.14_2.delta")
    _require_eq_int(d2["false_admit_pcm_kwh"], 2_350, "p1.14_2.pcm")
    _require_eq_int(d2["false_admit_v030_ppm"], ov30, "p1.14_2.ov30")
    _require_eq_int(d2["false_admit_v031_ppm"], ov31, "p1.14_2.ov31")

    # #14.3
    d3 = _check_keys(
        d["defect_14_3_equal_objective_headroom_decay"],
        {
            "upstream_status",
            "attack_step_count",
            "v033_admitted_count",
            "v033_headroom_before_ppm",
            "v033_headroom_after_ppm",
            "v033_headroom_eroded_ppm",
            "v033_eta_unchanged_ppm",
            "lex_repair_admitted_attack_count",
            "lex_repair_budget_preserved",
            "lex_repair_admits_widening_move",
            "lex_repair_widening_verdict",
            "lex_repair_widened_headroom_ppm",
        },
        "p1.14_3",
    )
    _require_eq_str(d3["upstream_status"], "open_in_v0_3_3_repaired_here", "p1.14_3.status")
    steps = [
        dict(g0, pcm_kwh=2_450),
        dict(g0, pcm_kwh=2_420),
        dict(g0, pcm_kwh=2_410),
        dict(g0, pcm_kwh=2_405),
    ]
    h33, b33, adm33 = dict(g0), 64, 0
    for c in steps:
        ok, _, rem = oracle.accepts_v033(p, sc, oracle.LIMIT_PPM, h33, c, b33)
        if ok:
            adm33 += 1
            h33, b33 = c, rem
    hr_after = oracle.headroom_ppm(oracle.LIMIT_PPM, oracle.margins_v031(p, sc, h33))
    hlex, blex, admlex = dict(g0), 64, 0
    for c in steps:
        ok, _, rem = oracle.accepts_lex_repaired(p, sc, oracle.LIMIT_PPM, hlex, c, blex)
        if ok:
            admlex += 1
            hlex, blex = c, rem
    g_w = dict(g0, pcm_kwh=2_580)
    w_ok, w_verd, _ = oracle.accepts_lex_repaired(p, sc, oracle.LIMIT_PPM, g0, g_w, 64)
    hr_w = oracle.headroom_ppm(oracle.LIMIT_PPM, oracle.margins_v031(p, sc, g_w))
    _require_eq_int(d3["attack_step_count"], 4, "p1.14_3.step_count")
    _require_eq_int(d3["v033_admitted_count"], adm33, "p1.14_3.v33_adm")
    _require_eq_int(d3["v033_headroom_before_ppm"], hr0, "p1.14_3.hr0")
    _require_eq_int(d3["v033_headroom_after_ppm"], hr_after, "p1.14_3.hr_after")
    _require_eq_int(d3["v033_headroom_eroded_ppm"], hr0 - hr_after, "p1.14_3.eroded")
    _require_eq_int(d3["v033_eta_unchanged_ppm"], eta31, "p1.14_3.eta")
    _require_eq_int(d3["lex_repair_admitted_attack_count"], admlex, "p1.14_3.lex_adm")
    _require_eq_int(d3["lex_repair_budget_preserved"], blex, "p1.14_3.lex_bud")
    _require_eq_bool(d3["lex_repair_admits_widening_move"], w_ok, "p1.14_3.widen_ok")
    _require_eq_str(d3["lex_repair_widening_verdict"], w_verd, "p1.14_3.widen_verd")
    _require_eq_int(d3["lex_repair_widened_headroom_ppm"], hr_w, "p1.14_3.widen_hr")

    # #14.4
    d4 = _check_keys(
        d["defect_14_4_missing_wellformed_predicate"],
        {
            "upstream_status",
            "bad_shed_ppm",
            "bad_shed_v033_outage_ppm",
            "bad_shed_wellformed_pass",
            "zero_floor_v033_margin_ppm",
            "zero_floor_wellformed_at_10m_pass",
            "start_genome_wellformed_pass",
        },
        "p1.14_4",
    )
    _require_eq_str(d4["upstream_status"], "open_in_v0_3_3_repaired_here", "p1.14_4.status")
    g_bs = dict(g0, shed_ppm=2_000_000)
    bs_out = oracle.outage_margin_v031_repaired(p, sc, g_bs)
    g_zf = dict(g0, floor_kw=0)
    zf_m = oracle.floor_margin(p, g_zf)
    _require_eq_int(d4["bad_shed_ppm"], 2_000_000, "p1.14_4.bad_shed")
    _require_eq_int(d4["bad_shed_v033_outage_ppm"], bs_out, "p1.14_4.bs_out")
    _require_eq_bool(d4["bad_shed_wellformed_pass"], oracle.well_formed_plant_check(p, sc, oracle.LIMIT_PPM, g_bs), "p1.14_4.bs_wf")
    _require_eq_int(d4["zero_floor_v033_margin_ppm"], zf_m, "p1.14_4.zf")
    _require_eq_bool(d4["zero_floor_wellformed_at_10m_pass"], oracle.well_formed_plant_check(p, sc, oracle.MAX_PPM, g_zf), "p1.14_4.zf_wf")
    _require_eq_bool(d4["start_genome_wellformed_pass"], oracle.well_formed_plant_check(p, sc, oracle.LIMIT_PPM, g0), "p1.14_4.start_wf")

    # #14.5
    d5 = _check_keys(
        d["defect_14_5_asymmetric_distance_and_recovery"],
        {
            "upstream_status",
            "double_pcm_start_outage_ppm",
            "double_pcm_cand_outage_ppm",
            "double_pcm_headroom_after_ppm",
            "double_pcm_sym_dist_sq",
            "double_pcm_radius_sq",
            "double_pcm_pos_dist_sq",
            "double_pcm_v033_verdict",
            "double_pcm_repaired_verdict",
            "oob_start_max_margin_ppm",
            "oob_start_headroom_ppm",
            "oob_recovery_v033_verdict",
            "oob_recovery_repaired_verdict",
            "oob_recovered_max_margin_ppm",
        },
        "p1.14_5",
    )
    _require_eq_str(d5["upstream_status"], "open_in_v0_3_3_repaired_here", "p1.14_5.status")
    m_dbl = oracle.margins_v031(p, sc, dict(g0, pcm_kwh=5_000))
    m_oob = oracle.margins_v031(p, sc, g_ov)
    sv_dbl, _ = oracle.gate_v033_sym(m0, m_dbl, oracle.LIMIT_PPM, 64, 1)
    av_dbl, _ = oracle.gate_asymmetric_recovery(m0, m_dbl, oracle.LIMIT_PPM, 64, 1)
    sv_rec, _ = oracle.gate_v033_sym(m_oob, m0, oracle.LIMIT_PPM, 64, 1)
    av_rec, _ = oracle.gate_asymmetric_recovery(m_oob, m0, oracle.LIMIT_PPM, 64, 1)
    _require_eq_int(d5["double_pcm_start_outage_ppm"], m0[-1], "p1.14_5.start_out")
    _require_eq_int(d5["double_pcm_cand_outage_ppm"], m_dbl[-1], "p1.14_5.dbl_out")
    _require_eq_int(d5["double_pcm_headroom_after_ppm"], oracle.headroom_ppm(oracle.LIMIT_PPM, m_dbl), "p1.14_5.dbl_hr")
    _require_eq_int(d5["double_pcm_sym_dist_sq"], oracle.dist_sq(m0, m_dbl), "p1.14_5.sym_sq")
    _require_eq_int(d5["double_pcm_radius_sq"], hr0 * hr0, "p1.14_5.r_sq")
    _require_eq_int(d5["double_pcm_pos_dist_sq"], oracle.pos_dist_sq(m0, m_dbl), "p1.14_5.pos_sq")
    _require_eq_str(d5["double_pcm_v033_verdict"], sv_dbl, "p1.14_5.sv_dbl")
    _require_eq_str(d5["double_pcm_repaired_verdict"], av_dbl, "p1.14_5.av_dbl")
    _require_eq_int(d5["oob_start_max_margin_ppm"], max(m_oob), "p1.14_5.oob_max")
    _require_eq_int(d5["oob_start_headroom_ppm"], oracle.headroom_ppm(oracle.LIMIT_PPM, m_oob), "p1.14_5.oob_hr")
    _require_eq_str(d5["oob_recovery_v033_verdict"], sv_rec, "p1.14_5.sv_rec")
    _require_eq_str(d5["oob_recovery_repaired_verdict"], av_rec, "p1.14_5.av_rec")
    _require_eq_int(d5["oob_recovered_max_margin_ppm"], max(m0), "p1.14_5.rec_max")


def _verify_coupled_regime(reg: Any, eta: Fraction, label: str) -> None:
    r = _check_keys(
        reg,
        {
            "eta_q",
            "det_a_q",
            "det_schur_q",
            "det_full_q",
            "block_det_identity_exact",
            "inertia_a",
            "inertia_d",
            "inertia_schur",
            "inertia_full",
            "haynsworth_additivity_exact",
            "decoupled_blocks_both_spd",
            "r5_coupled_verdict",
            "negative_witness_vec_q",
            "negative_witness_quad_form_q",
        },
        label,
    )
    _require_eq_q(r["eta_q"], eta, f"{label}.eta")
    a = [list(row) for row in oracle.COUPLED_A_BLOCK]
    d = [list(row) for row in oracle.COUPLED_D_BLOCK]
    b = [[eta * x for x in row] for row in oracle.COUPLED_B_BASE]
    bt = oracle.mat_transpose_q(b)
    a_inv, det_a = oracle.mat_inv_det_q(a)
    s_mat = oracle.mat_sub_q(d, oracle.mat_mul_q(bt, oracle.mat_mul_q(a_inv, b)))
    _, det_s = oracle.mat_inv_det_q(s_mat)
    m = [a[i] + b[i] for i in range(4)] + [bt[i] + d[i] for i in range(2)]
    _, det_m = oracle.mat_inv_det_q(m)
    ia = list(oracle.symmetric_inertia_q(a)[:3])
    id_b = list(oracle.symmetric_inertia_q(d)[:3])
    is_b = list(oracle.symmetric_inertia_q(s_mat)[:3])
    im = list(oracle.symmetric_inertia_q(m)[:3])
    _require_eq_q(r["det_a_q"], det_a, f"{label}.det_a")
    _require_eq_q(r["det_schur_q"], det_s, f"{label}.det_s")
    _require_eq_q(r["det_full_q"], det_m, f"{label}.det_m")
    _require_eq_bool(r["block_det_identity_exact"], det_m == det_a * det_s, f"{label}.det_id")
    _require_eq_int_list(r["inertia_a"], ia, f"{label}.ia")
    _require_eq_int_list(r["inertia_d"], id_b, f"{label}.id")
    _require_eq_int_list(r["inertia_schur"], is_b, f"{label}.is")
    _require_eq_int_list(r["inertia_full"], im, f"{label}.im")
    _require_eq_bool(
        r["haynsworth_additivity_exact"],
        [ia[k] + is_b[k] for k in range(3)] == im,
        f"{label}.haynsworth",
    )
    _require_eq_bool(
        r["decoupled_blocks_both_spd"],
        (ia, id_b) == ([4, 0, 0], [2, 0, 0]),
        f"{label}.decoupled",
    )
    if im == [6, 0, 0]:
        _require_eq_str(r["r5_coupled_verdict"], "ADMIT", f"{label}.admit")
        require_ok(r["negative_witness_vec_q"] is None, f"{label}: witness vec must be None")
        require_ok(r["negative_witness_quad_form_q"] is None, f"{label}: witness qf must be None")
    else:
        _require_eq_str(r["r5_coupled_verdict"], "REFUSE_SCHUR_NEGATIVE_INERTIA", f"{label}.refuse")
        w_raw = r["negative_witness_vec_q"]
        require_ok(type(w_raw) is list, f"{label}: witness vec list required")
        require_ok(len(w_raw) == 6, f"{label}: witness vec len must be 6")
        w_vec = [_parse_q_strict(x, f"{label}.w") for x in w_raw]
        qf = oracle.quad_form_q(m, w_vec)
        require_ok(qf < 0, f"{label}: witness quadratic form must be negative")
        _require_eq_q(r["negative_witness_quad_form_q"], qf, f"{label}.qf")


def _verify_pillar2(p2: Any) -> None:
    d = _check_keys(
        p2,
        {
            "frame_bytes",
            "frame_slot_count",
            "physical_limit_state_count",
            "physical_limit_states",
            "physical_binding_limit_state",
            "physical_binding_headroom_q",
            "physical_binding_headroom_dec6",
            "pcm_budget_kwh",
            "carnot_recooling_max_15c_q",
            "carnot_recooling_max_15c_dec4",
            "carnot_recooling_max_18c_q",
            "carnot_recooling_max_18c_dec4",
            "load_floor_p_min_mw_q",
            "load_floor_p_min_mw_dec6",
            "silicon_compute_anchors",
            "schur_coupled_gate",
            "frame_contract_checks",
            "all_verified",
        },
        "pillar_2",
    )
    _require_eq_int(d["frame_bytes"], 64, "p2.frame_bytes")
    _require_eq_int(d["frame_slot_count"], 16, "p2.frame_slots")
    _require_eq_int(d["pcm_budget_kwh"], 2_500, "p2.pcm")
    _require_eq_bool(d["all_verified"], True, "p2.flag")

    rows = d["physical_limit_states"]
    require_ok(type(rows) is list, "p2: rows list required")
    require_ok(len(rows) == 12, "p2: 12 limit states required")
    _require_eq_int(d["physical_limit_state_count"], 12, "p2.ls_count")
    min_hr = Fraction(1, 1)
    bind_name = ""
    for row, (exp_name, exp_src, exp_dem, exp_cap) in zip(rows, oracle.PHYSICAL_LIMIT_STATES):
        rr = _check_keys(
            row,
            {
                "limit_state",
                "source",
                "demand_q",
                "capacity_q",
                "utilisation_q",
                "utilisation_dec6",
                "headroom_q",
                "headroom_dec6",
            },
            f"p2.ls.{exp_name}",
        )
        _require_eq_str(rr["limit_state"], exp_name, f"p2.{exp_name}.name")
        _require_eq_str(rr["source"], exp_src, f"p2.{exp_name}.src")
        _require_eq_q(rr["demand_q"], exp_dem, f"p2.{exp_name}.dem")
        _require_eq_q(rr["capacity_q"], exp_cap, f"p2.{exp_name}.cap")
        util = exp_dem / exp_cap
        hr = Fraction(1, 1) - util
        _require_eq_q(rr["utilisation_q"], util, f"p2.{exp_name}.util")
        _require_eq_str(rr["utilisation_dec6"], oracle.fmt_dec(util, 6), f"p2.{exp_name}.util_d6")
        _require_eq_q(rr["headroom_q"], hr, f"p2.{exp_name}.hr")
        _require_eq_str(rr["headroom_dec6"], oracle.fmt_dec(hr, 6), f"p2.{exp_name}.hr_d6")
        if hr < min_hr:
            min_hr = hr
            bind_name = exp_name

    _require_eq_str(d["physical_binding_limit_state"], bind_name, "p2.bind_name")
    _require_eq_q(d["physical_binding_headroom_q"], min_hr, "p2.bind_hr")
    _require_eq_str(d["physical_binding_headroom_dec6"], oracle.fmt_dec(min_hr, 6), "p2.bind_hr_d6")

    t_d = Fraction(33_115, 100)
    cop = Fraction(62, 100)
    t_c15 = Fraction(28_815, 100)
    t_c18 = Fraction(29_115, 100)
    rec15 = (t_d * t_c15 * (1 + cop)) / (t_c15 + cop * t_d) - Fraction(27_315, 100)
    rec18 = (t_d * t_c18 * (1 + cop)) / (t_c18 + cop * t_d) - Fraction(27_315, 100)
    _require_eq_q(d["carnot_recooling_max_15c_q"], rec15, "p2.rec15")
    _require_eq_str(d["carnot_recooling_max_15c_dec4"], oracle.fmt_dec(rec15, 4), "p2.rec15_d4")
    _require_eq_q(d["carnot_recooling_max_18c_q"], rec18, "p2.rec18")
    _require_eq_str(d["carnot_recooling_max_18c_dec4"], oracle.fmt_dec(rec18, 4), "p2.rec18_d4")

    p_min = Fraction(oracle.q_fix(oracle.OPTIFAB_PLANT, oracle.START_GENOME), 1_000_000_000_000) / (
        (Fraction(1, 1) + cop) * Fraction(85, 100) - Fraction(1, 1)
    )
    _require_eq_q(d["load_floor_p_min_mw_q"], p_min, "p2.pmin")
    _require_eq_str(d["load_floor_p_min_mw_dec6"], oracle.fmt_dec(p_min, 6), "p2.pmin_d6")

    sca = _check_keys(
        d["silicon_compute_anchors"],
        {
            "s86_r128_vram_util_q",
            "s86_r128_vram_util_dec6",
            "s86_r128_vram_headroom_q",
            "s86_r128_vram_headroom_dec6",
            "vram_tighter_than_physical_collar",
            "s94_b_crit_bpw_q",
            "s94_b_crit_bpw_dec4",
            "s94_bonsai_cliff_util_q",
            "s94_bonsai_cliff_util_dec4",
            "s94_quadsnake_3bpw_cliff_util_q",
            "s94_quadsnake_3bpw_cliff_util_dec4",
            "s58_sm86_tok_s_q",
            "s58_sm86_tok_s_dec2",
            "s58_energy_reduction_ratio_q",
            "s58_energy_reduction_ratio_dec4",
            "s61_landauer_net_core_gap_ceil",
            "s53_dynamic_channels",
            "s53_signal_over_null_ratio_q",
            "s53_signal_over_null_ratio_dec4",
        },
        "p2.silicon",
    )
    vu = Fraction(6_914_886_656, 8_589_934_592)
    vh = Fraction(1, 1) - vu
    bc = Fraction(325, 171)
    bu = Fraction(44, 25) / bc
    qu = Fraction(3, 1) / bc
    tps = Fraction(20_029, 50)
    eg = Fraction(30_702_453, 20_000) / Fraction(31_278_711, 100_000)
    sn = Fraction(103_215_570_329, 1_000_000_000_000) / Fraction(1_922_367_199, 200_000_000_000)
    _require_eq_q(sca["s86_r128_vram_util_q"], vu, "p2.vu")
    _require_eq_str(sca["s86_r128_vram_util_dec6"], oracle.fmt_dec(vu, 6), "p2.vu_d6")
    _require_eq_q(sca["s86_r128_vram_headroom_q"], vh, "p2.vh")
    _require_eq_str(sca["s86_r128_vram_headroom_dec6"], oracle.fmt_dec(vh, 6), "p2.vh_d6")
    _require_eq_bool(sca["vram_tighter_than_physical_collar"], vh < min_hr, "p2.vram_tight")
    _require_eq_q(sca["s94_b_crit_bpw_q"], bc, "p2.bc")
    _require_eq_str(sca["s94_b_crit_bpw_dec4"], oracle.fmt_dec(bc, 4), "p2.bc_d4")
    _require_eq_q(sca["s94_bonsai_cliff_util_q"], bu, "p2.bu")
    _require_eq_str(sca["s94_bonsai_cliff_util_dec4"], oracle.fmt_dec(bu, 4), "p2.bu_d4")
    _require_eq_q(sca["s94_quadsnake_3bpw_cliff_util_q"], qu, "p2.qu")
    _require_eq_str(sca["s94_quadsnake_3bpw_cliff_util_dec4"], oracle.fmt_dec(qu, 4), "p2.qu_d4")
    _require_eq_q(sca["s58_sm86_tok_s_q"], tps, "p2.tps")
    _require_eq_str(sca["s58_sm86_tok_s_dec2"], oracle.fmt_dec(tps, 2), "p2.tps_d2")
    _require_eq_q(sca["s58_energy_reduction_ratio_q"], eg, "p2.eg")
    _require_eq_str(sca["s58_energy_reduction_ratio_dec4"], oracle.fmt_dec(eg, 4), "p2.eg_d4")
    _require_eq_int(sca["s61_landauer_net_core_gap_ceil"], 345_639_005_232, "p2.s61")
    _require_eq_int(sca["s53_dynamic_channels"], 48, "p2.s53_ch")
    _require_eq_q(sca["s53_signal_over_null_ratio_q"], sn, "p2.sn")
    _require_eq_str(sca["s53_signal_over_null_ratio_dec4"], oracle.fmt_dec(sn, 4), "p2.sn_d4")

    scg = _check_keys(
        d["schur_coupled_gate"],
        {"matrix_dim", "physical_block_dim", "digital_block_dim", "nominal_eta1", "overload_eta3"},
        "p2.schur",
    )
    _require_eq_int(scg["matrix_dim"], 6, "p2.mdim")
    _require_eq_int(scg["physical_block_dim"], 4, "p2.pdim")
    _require_eq_int(scg["digital_block_dim"], 2, "p2.ddim")
    _verify_coupled_regime(scg["nominal_eta1"], Fraction(1, 1), "p2.schur.nom")
    _verify_coupled_regime(scg["overload_eta3"], Fraction(3, 1), "p2.schur.ovl")

    fcs = d["frame_contract_checks"]
    require_ok(type(fcs) is list, "p2: frame checks list required")
    require_ok(len(fcs) == 8, "p2: 8 frame cases required")
    expected_frames = [
        ("design_nominal_coupled", []),
        ("recooling_missing", ["recooling_not_measured"]),
        ("idle_below_load_floor", ["below_load_floor"]),
        ("recooling_above_41p46C", ["recooling_above_limit"]),
        ("punching_collar_exceeded", ["limit_exceeded"]),
        ("thermal_budget_exhausted", ["thermal_budget_exhausted"]),
        ("vram_residency_cliff_exceeded", ["silicon_vram_cliff_exceeded"]),
        ("schur_cross_coupling_unstable", ["schur_cross_coupling_unstable"]),
    ]
    for fc, (exp_cid, exp_v) in zip(fcs, expected_frames):
        f = _check_keys(fc, {"case_id", "violations", "admitted"}, f"p2.frame.{exp_cid}")
        _require_eq_str(f["case_id"], exp_cid, f"p2.frame.{exp_cid}.id")
        _require_eq_str_list(f["violations"], exp_v, f"p2.frame.{exp_cid}.viol")
        _require_eq_bool(f["admitted"], len(exp_v) == 0, f"p2.frame.{exp_cid}.adm")


def _verify_pillar3(p3: Any) -> None:
    d = _check_keys(
        p3,
        {
            "mesh_node_count",
            "mesh_edge_count",
            "triangle_count",
            "tetrahedron_count",
            "proposals",
            "foster_effective_resistance_q",
            "foster_sum_q",
            "foster_identity_exact",
            "schur_compounding_count",
            "schur_effective_conductance_q",
            "schur_compounding_gain_q",
            "nonzero_triangle_holonomy_count",
            "tetrahedral_bianchi_z_zero_count",
            "tetrahedral_bianchi_z2_zero_count",
            "silo_cut_4x4",
            "borromean_5org_obstruction",
            "three_node_execution_plan",
            "all_verified",
        },
        "pillar_3",
    )
    _require_eq_bool(d["all_verified"], True, "p3.flag")
    n = 8
    _require_eq_int(d["mesh_node_count"], n, "p3.n")
    _require_eq_int(d["mesh_edge_count"], 28, "p3.edges")
    _require_eq_int(d["triangle_count"], 56, "p3.tris")
    _require_eq_int(d["tetrahedron_count"], 70, "p3.tets")

    props = d["proposals"]
    require_ok(type(props) is list, "p3: proposals list required")
    require_ok(len(props) == 8, "p3: 8 proposals required")
    for got, exp in zip(props, oracle.PROPOSAL_MESH_NODES):
        gp = _check_keys(got, set(exp.keys()), f"p3.prop.{exp['proposal_id']}")
        _require_eq_int(gp["node_id"], exp["node_id"], f"p3.prop.{exp['proposal_id']}.nid")
        _require_eq_int(gp["issue_number"], exp["issue_number"], f"p3.prop.{exp['proposal_id']}.iss")
        require_ok(gp == exp, f"p3.prop.{exp['proposal_id']}: content mismatch")

    # Independent K_8 Laplacian grounded at node 0 (different from oracle's node 7!)
    lap = [
        [Fraction(n - 1, 1) if i == j else Fraction(-1, 1) for j in range(n)]
        for i in range(n)
    ]
    red0 = [[lap[i][j] for j in range(1, n)] for i in range(1, n)]
    red0_inv, _ = oracle.mat_inv_det_q(red0)

    foster = Fraction(0, 1)
    comp_cnt = 0
    for i in range(n):
        for j in range(i + 1, n):
            uu = red0_inv[i - 1][i - 1] if i > 0 else Fraction(0, 1)
            vv = red0_inv[j - 1][j - 1] if j > 0 else Fraction(0, 1)
            uv = red0_inv[i - 1][j - 1] if i > 0 else Fraction(0, 1)
            re = uu + vv - 2 * uv
            foster += re
            if Fraction(1, 1) / re > Fraction(1, 1):
                comp_cnt += 1

    _require_eq_q(d["foster_effective_resistance_q"], Fraction(1, 4), "p3.reff")
    _require_eq_q(d["foster_sum_q"], foster, "p3.foster")
    _require_eq_bool(d["foster_identity_exact"], foster == Fraction(n - 1, 1), "p3.foster_flag")
    _require_eq_int(d["schur_compounding_count"], comp_cnt, "p3.comp")
    _require_eq_q(d["schur_effective_conductance_q"], Fraction(4, 1), "p3.ceff")
    _require_eq_q(d["schur_compounding_gain_q"], Fraction(3, 1), "p3.cgain")

    tri: dict[tuple[int, int, int], int] = {}
    nz = 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                f = (
                    oracle.edge_cochain_value(i, j)
                    + oracle.edge_cochain_value(j, k)
                    - oracle.edge_cochain_value(i, k)
                )
                tri[(i, j, k)] = f
                if f != 0:
                    nz += 1
    bz, bz2 = 0, 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    df = tri[(j, k, l)] - tri[(i, k, l)] + tri[(i, j, l)] - tri[(i, j, k)]
                    if df == 0:
                        bz += 1
                    if df % 2 == 0:
                        bz2 += 1
    _require_eq_int(d["nonzero_triangle_holonomy_count"], nz, "p3.nz_tri")
    _require_eq_int(d["tetrahedral_bianchi_z_zero_count"], bz, "p3.bianchi_z")
    _require_eq_int(d["tetrahedral_bianchi_z2_zero_count"], bz2, "p3.bianchi_z2")

    sc4 = _check_keys(
        d["silo_cut_4x4"],
        {"physical_node_ids", "digital_node_ids", "cross_boundary_edges", "lambda2_intact", "lambda2_cut"},
        "p3.silo",
    )
    _require_eq_int_list(sc4["physical_node_ids"], [0, 3, 6, 7], "p3.silo.phys")
    _require_eq_int_list(sc4["digital_node_ids"], [1, 2, 4, 5], "p3.silo.dig")
    _require_eq_int(sc4["cross_boundary_edges"], 16, "p3.silo.cross")
    _require_eq_int(sc4["lambda2_intact"], 8, "p3.silo.l2i")
    _require_eq_int(sc4["lambda2_cut"], 0, "p3.silo.l2c")

    b5 = _check_keys(
        d["borromean_5org_obstruction"],
        {
            "public_orgs",
            "nonempty_subsets_checked",
            "full_closure_subset_count",
            "strict_borromean_necessity",
            "four_org_failure_witnesses",
        },
        "p3.borr5",
    )
    _require_eq_str_list(b5["public_orgs"], list(oracle.FIVE_ORGS), "p3.borr5.orgs")
    passing_5 = 0
    expected_w4: list[dict[str, Any]] = []
    for mask in range(1, 32):
        pres = {oracle.FIVE_ORGS[idx] for idx in range(5) if (mask >> idx) & 1}
        cprops = [nd["proposal_id"] for nd in oracle.PROPOSAL_MESH_NODES if set(nd["required_orgs"]).issubset(pres)]
        cifaces = {ifc for nd in oracle.PROPOSAL_MESH_NODES if set(nd["required_orgs"]).issubset(pres) for ifc in nd["closes_interfaces"]}
        if len(cprops) == 8:
            passing_5 += 1
        if len(pres) == 4:
            dropped = next(iter(set(oracle.FIVE_ORGS) - pres))
            broken = [nd["proposal_id"] for nd in oracle.PROPOSAL_MESH_NODES if not set(nd["required_orgs"]).issubset(pres)]
            expected_w4.append(
                {
                    "dropped_org": dropped,
                    "closed_proposal_count": len(cprops),
                    "closed_interface_count": len(cifaces),
                    "broken_proposals": broken,
                }
            )
    _require_eq_int(b5["nonempty_subsets_checked"], 31, "p3.borr5.31")
    _require_eq_int(b5["full_closure_subset_count"], passing_5, "p3.borr5.pass")
    _require_eq_bool(b5["strict_borromean_necessity"], passing_5 == 1, "p3.borr5.flag")
    w4 = b5["four_org_failure_witnesses"]
    require_ok(type(w4) is list, "p3.borr5: w4 list required")
    require_ok(len(w4) == 5, "p3.borr5: 5 witnesses required")
    for got_w, exp_w in zip(w4, expected_w4):
        gw = _check_keys(got_w, set(exp_w.keys()), "p3.borr5.w4")
        _require_eq_int(gw["closed_proposal_count"], exp_w["closed_proposal_count"], "p3.borr5.w4.cp")
        _require_eq_int(gw["closed_interface_count"], exp_w["closed_interface_count"], "p3.borr5.w4.ci")
        require_ok(gw == exp_w, "p3.borr5.w4: mismatch")

    tn = _check_keys(
        d["three_node_execution_plan"],
        {
            "nodes",
            "nonempty_host_subsets_checked",
            "full_execution_subset_count",
            "strict_3node_borromean_necessity",
        },
        "p3.3node",
    )
    nodes = tn["nodes"]
    require_ok(type(nodes) is list, "p3.3node: nodes list required")
    require_ok(len(nodes) == 3, "p3.3node: 3 nodes required")
    for got_n, exp_n in zip(nodes, oracle.THREE_NODE_EXECUTION_NODES):
        ehost = exp_n["host_role"]
        gn = _check_keys(
            got_n,
            {"host_role", "hardware_profile", "memory_budget_gib_q", "assigned_proposals", "primary_deliverables"},
            f"p3.3node.{ehost}",
        )
        _require_eq_str(gn["host_role"], ehost, f"p3.3node.{ehost}.role")
        _require_eq_str(gn["hardware_profile"], exp_n["hardware_profile"], f"p3.3node.{ehost}.hw")
        _require_eq_q(gn["memory_budget_gib_q"], Fraction(int(exp_n["memory_budget_gib_q"]), 1), f"p3.3node.{ehost}.mem")
        _require_eq_str_list(gn["assigned_proposals"], exp_n["assigned_proposals"], f"p3.3node.{ehost}.props")
        _require_eq_str(gn["primary_deliverables"], exp_n["primary_deliverables"], f"p3.3node.{ehost}.deliv")
    _require_eq_int(tn["nonempty_host_subsets_checked"], 7, "p3.3node.7")
    _require_eq_int(tn["full_execution_subset_count"], 1, "p3.3node.1")
    _require_eq_bool(tn["strict_3node_borromean_necessity"], True, "p3.3node.flag")


def _verify_pillar4(p4: Any) -> None:
    d = _check_keys(
        p4,
        {
            "lean4_companion",
            "pinned_upstream_provenance",
            "law5_non_commutativity",
            "epistemic_scope",
            "all_verified",
        },
        "pillar_4",
    )
    _require_eq_bool(d["all_verified"], True, "p4.flag")

    lc = _check_keys(
        d["lean4_companion"],
        {
            "file",
            "sha256",
            "lakefile",
            "lakefile_sha256",
            "toolchain_file",
            "toolchain_sha256",
            "namespace",
            "theorem_count",
            "theorems",
            "allowed_axioms",
            "pure_init_zero_external_imports",
            "all_theorems_universally_quantified",
        },
        "p4.lean",
    )
    _require_eq_str(lc["file"], oracle.LEAN_COMPANION_FILE, "p4.lean.file")
    require_ok(hmac.compare_digest(_require_sha256_hex(lc["sha256"], "p4.lean.sha"), oracle.PINNED_LEAN_SHA256), "p4.lean: sha")
    _require_eq_str(lc["lakefile"], oracle.LAKEFILE_NAME, "p4.lean.lakefile")
    require_ok(hmac.compare_digest(_require_sha256_hex(lc["lakefile_sha256"], "p4.lean.lsha"), oracle.PINNED_LAKEFILE_SHA256), "p4.lean: lake sha")
    _require_eq_str(lc["toolchain_file"], oracle.LEAN_TOOLCHAIN_FILE, "p4.lean.tc")
    require_ok(hmac.compare_digest(_require_sha256_hex(lc["toolchain_sha256"], "p4.lean.tsha"), oracle.PINNED_TOOLCHAIN_SHA256), "p4.lean: tc sha")
    _require_eq_str(lc["namespace"], oracle.LEAN_NAMESPACE, "p4.lean.ns")
    _require_eq_int(lc["theorem_count"], 18, "p4.lean.count")
    _require_eq_str_list(lc["theorems"], list(oracle.LEAN_THEOREM_NAMES), "p4.lean.thms")
    _require_eq_str_list(lc["allowed_axioms"], ["propext", "Quot.sound"], "p4.lean.axioms")
    _require_eq_bool(lc["pure_init_zero_external_imports"], True, "p4.lean.pure")
    _require_eq_bool(lc["all_theorems_universally_quantified"], True, "p4.lean.forall")

    up = _check_keys(
        d["pinned_upstream_provenance"],
        {"optifab", "aska_public_sibling_heads", "expedition_certificates"},
        "p4.upstream",
    )
    _check_keys(up["optifab"], set(oracle.UPSTREAM_OPTIFAB_PIN.keys()), "p4.upstream.optifab")
    require_ok(up["optifab"] == oracle.UPSTREAM_OPTIFAB_PIN, "p4.upstream.optifab: mismatch")
    _check_keys(up["aska_public_sibling_heads"], set(oracle.ASKA_PUBLIC_SIBLING_HEADS.keys()), "p4.upstream.siblings")
    require_ok(up["aska_public_sibling_heads"] == oracle.ASKA_PUBLIC_SIBLING_HEADS, "p4.upstream.siblings: mismatch")
    _check_keys(up["expedition_certificates"], set(oracle.UPSTREAM_EXPEDITION_CERTS.keys()), "p4.upstream.exp")
    for k, exp_v in oracle.UPSTREAM_EXPEDITION_CERTS.items():
        got_v = _check_keys(up["expedition_certificates"][k], {"rel_path", "sha256"}, f"p4.upstream.exp.{k}")
        require_ok(got_v == exp_v, f"p4.upstream.exp.{k}: mismatch")

    l5 = _check_keys(
        d["law5_non_commutativity"],
        {"witness_count", "sym_vs_pos_distance_delta", "steady_vs_transient_outage_flip_pcm_kwh", "decoupled_vs_schur_flip_eta_q"},
        "p4.law5",
    )
    _require_eq_int(l5["witness_count"], 3, "p4.law5.count")
    _require_eq_int(l5["sym_vs_pos_distance_delta"], 231_213_837_409, "p4.law5.delta")
    _require_eq_int(l5["steady_vs_transient_outage_flip_pcm_kwh"], 2_350, "p4.law5.flip_pcm")
    _require_eq_q(l5["decoupled_vs_schur_flip_eta_q"], Fraction(3, 1), "p4.law5.eta")

    es = _check_keys(
        d["epistemic_scope"],
        {"novelty_tier", "n0_scaffolding_count", "n1_synthesis_count", "n2_claims_count", "public_repos_only", "zero_gpu_touch"},
        "p4.scope",
    )
    _require_eq_str(es["novelty_tier"], oracle.NOVELTY_TIER, "p4.scope.tier")
    _require_eq_int(es["n0_scaffolding_count"], 2, "p4.scope.n0")
    _require_eq_int(es["n1_synthesis_count"], 4, "p4.scope.n1")
    _require_eq_int(es["n2_claims_count"], 0, "p4.scope.n2")
    _require_eq_bool(es["public_repos_only"], True, "p4.scope.public")
    _require_eq_bool(es["zero_gpu_touch"], True, "p4.scope.zero_gpu")


def secondary_audit_payload(payload: Any) -> None:
    """Field-complete independent audit of payload (used identically by SEC and FR0)."""
    validate_json_tree_iterative(payload, "payload")
    d = _check_keys(
        payload,
        {
            "track_id",
            "schema_version",
            "oracle_class",
            "novelty_tier",
            "pillar_1_optifab14_defects_and_repairs",
            "pillar_2_coupled_physical_digital_gate",
            "pillar_3_proposals_k8_5org_mesh",
            "pillar_4_lean4_and_provenance",
            "all_pillars_verified",
        },
        "payload",
    )
    _require_eq_str(d["track_id"], oracle.TRACK_ID, "payload.track_id")
    _require_eq_str(d["schema_version"], oracle.SCHEMA_VERSION, "payload.schema")
    _require_eq_str(d["oracle_class"], oracle.ORACLE_CLASS, "payload.oracle_class")
    _require_eq_str(d["novelty_tier"], oracle.NOVELTY_TIER, "payload.novelty_tier")
    _require_eq_bool(d["all_pillars_verified"], True, "payload.all_pillars")
    _verify_pillar1(d["pillar_1_optifab14_defects_and_repairs"])
    _verify_pillar2(d["pillar_2_coupled_physical_digital_gate"])
    _verify_pillar3(d["pillar_3_proposals_k8_5org_mesh"])
    _verify_pillar4(d["pillar_4_lean4_and_provenance"])


def verify_payload_dict(payload: Any) -> dict[str, Any]:
    """FR0 in-memory payload verification entry point."""
    secondary_audit_payload(payload)
    return payload


def verify_certificate_dict(cert: Any) -> dict[str, Any]:
    """Full FR1 (envelope/hashes) + FR0 (independent field-complete payload audit)."""
    validate_json_tree_iterative(cert, "cert")
    c = _check_keys(
        cert,
        {"schema_version", "track_id", "payload", "payload_sha256", "certificate_sha256"},
        "certificate",
    )
    _require_eq_str(c["schema_version"], oracle.SCHEMA_VERSION, "cert.schema_version")
    _require_eq_str(c["track_id"], oracle.TRACK_ID, "cert.track_id")
    p_sha = _require_sha256_hex(c["payload_sha256"], "payload_sha256")
    c_sha = _require_sha256_hex(c["certificate_sha256"], "certificate_sha256")
    secondary_audit_payload(c["payload"])
    recomp_p_sha = oracle.sha256_canonical(c["payload"])
    require_ok(hmac.compare_digest(p_sha, recomp_p_sha), "cert: payload_sha256 mismatch")
    body = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload": c["payload"],
        "payload_sha256": p_sha,
    }
    recomp_c_sha = oracle.sha256_canonical(body)
    require_ok(hmac.compare_digest(c_sha, recomp_c_sha), "cert: certificate_sha256 mismatch")
    return c


def verify_certificate_file(path: Path = DEFAULT_CERT_PATH) -> dict[str, Any]:
    cert = _read_json_strict(path, "certificate_file")
    return verify_certificate_dict(cert)


def verify_upstream_pins(expedition_root: Path) -> dict[str, str]:
    matched: dict[str, str] = {}
    for tag, info in oracle.UPSTREAM_EXPEDITION_CERTS.items():
        target = expedition_root / info["rel_path"]
        raw = _read_regular_bytes_strict(target, MAX_JSON_BYTES, f"upstream_{tag}")
        actual = hashlib.sha256(raw).hexdigest()
        require_ok(hmac.compare_digest(actual, info["sha256"]), f"upstream {tag} SHA-256 mismatch")
        matched[tag] = actual
    return matched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S99 OptiFab 5-Org Convergence Verifier")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--write", nargs="?", const=str(DEFAULT_CERT_PATH), help="Build, verify, and atomically write certificate")
    mode.add_argument("--check", nargs="?", const=str(DEFAULT_CERT_PATH), help="Verify certificate file and Lean static/live gate")
    mode.add_argument("--standalone", action="store_true", help="Emit canonical certificate JSON to stdout")
    mode.add_argument("--verify-lean", action="store_true", help="Run strict static + live Lean 4.36.0 gate")
    mode.add_argument("--verify-upstream", metavar="EXPEDITION_ROOT", help="Verify all 7 pinned upstream expedition certs")
    parser.add_argument("--cert", default=None, help="Override certificate JSON path")
    parser.add_argument("--lean", default=str(DEFAULT_LEAN_PATH), help="Lean companion path")
    args = parser.parse_args(argv)

    lean_path = Path(args.lean)
    try:
        if args.standalone:
            cert = oracle.build_certificate()
            verify_certificate_dict(cert)
            sys.stdout.write(json.dumps(cert, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
            return 0
        if args.write is not None:
            cert_path = Path(args.cert) if args.cert is not None else Path(args.write)
            cert = oracle.build_certificate()
            verify_certificate_dict(cert)
            _write_json_atomic_0600(cert_path, cert)
            verify_certificate_file(cert_path)
            lean_res = verify_lean_companion(lean_path, require_live=False)
            sys.stdout.write(
                f"WROTE {cert_path.name} cert_sha256={cert['certificate_sha256'][:16]} "
                f"lean_live={lean_res['live_lean_executed']} thms={lean_res['theorem_count']}\n"
            )
            return 0
        if args.verify_lean:
            lean_res = verify_lean_companion(lean_path, require_live=True)
            sys.stdout.write(
                f"PASS_LEAN thms={lean_res['theorem_count']} sha256={lean_res['sha256'][:16]}\n"
            )
            return 0
        if args.verify_upstream:
            matched = verify_upstream_pins(Path(args.verify_upstream))
            sys.stdout.write(f"PASS_UPSTREAM matched={len(matched)}/{len(oracle.UPSTREAM_EXPEDITION_CERTS)}\n")
            return 0
        default_check = args.check if args.check is not None else str(DEFAULT_CERT_PATH)
        cert_path = Path(args.cert) if args.cert is not None else Path(default_check)
        cert = verify_certificate_file(cert_path)
        lean_res = verify_lean_companion(lean_path, require_live=False)
        sys.stdout.write(
            f"PASS {cert['track_id']} cert_sha256={cert['certificate_sha256'][:16]} "
            f"lean_live={lean_res['live_lean_executed']} thms={lean_res['theorem_count']}\n"
        )
        return 0
    except VerificationError as exc:
        sys.stderr.write(f"FAIL: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
