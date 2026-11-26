#!/usr/bin/env python3
"""Track S160 EXP-Q42b verifier: Prior-Tilt obstruction and lattice contraction.

Pure exact integer and rational verification. Standard library only.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from math import gcd
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

ALLOWED_AXIOMS = frozenset({"propext", "Quot.sound"})
EXPECTED_THEOREMS = 9
MAX_BYTES = 1048576
MAX_DEPTH = 32
MAX_INT_DIGITS = 256
CERT_NAME = "s160_q42b_prior_tilt_certificate.json"

_FORBIDDEN_LEAN_RE = re.compile(
    r"\b(?:sorry|admit|sorryAx|unsafe|native_decide|Classical|implemented_by|extern|macro|elab|syntax)\b"
    r"|\baxiom\b"
    r"|#eval"
    r"|\bIO\."
)
_ANY_IMPORT_RE = re.compile(r"(?:^|\n)[ \t]*import[ \t]+([A-Za-z0-9_.]+)")
_VALID_IMPORT_RE = re.compile(r"PriorTilt(?:\.[A-Za-z0-9_]+)*")
_PUB_THM_RE = re.compile(r"(?:^|\n)[ \t]*theorem[ \t]+([A-Za-z0-9_.']+)")
_PRINT_RE = re.compile(r"(?:^|\n)[ \t]*#print[ \t]+axioms[ \t]+PriorTilt\.([A-Za-z0-9_.']+)")


class PriorTiltVerifyError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(code + ": " + message)


def require_ok(cond, code, message):
    if cond is not True:
        raise PriorTiltVerifyError(code, message)


def frac_str(value):
    return str(value.numerator) + "/" + str(value.denominator)


def canonical_witness():
    return {
        "pos_errors": 264,
        "neg_errors": 167,
        "imbalance": 97,
        "feedback_pos": 18,
        "feedback_neg": 7,
        "feedback_diff": 11,
        "comparable_pairs": 406,
        "real_majority": 75,
        "real_minority": 2,
        "real_net": 77,
        "flipped_majority": 0,
        "flipped_minority": 52,
        "flipped_net": 52,
    }


def verify_witness_q(w=None):
    if w is None:
        w = canonical_witness()
    require_ok(w["pos_errors"] - w["neg_errors"] == w["imbalance"], "W_IMBALANCE", "pos minus neg mismatch")
    require_ok(w["imbalance"] > 0, "W_IMBALANCE_POS", "imbalance must be positive")
    require_ok(w["feedback_pos"] - w["feedback_neg"] == w["feedback_diff"], "W_FEEDBACK_DIFF", "feedback diff mismatch")
    require_ok(w["feedback_diff"] > 0, "W_FEEDBACK_POS", "feedback diff must be positive")
    require_ok(w["real_majority"] + w["real_minority"] == w["real_net"], "W_REAL_NET", "real net mismatch")
    require_ok(w["flipped_majority"] + w["flipped_minority"] == w["flipped_net"], "W_FLIP_NET", "flipped net mismatch")
    require_ok(w["real_net"] > 0, "W_REAL_POS", "real net must be positive")
    require_ok(w["flipped_net"] > 0, "W_FLIP_POS", "flipped net must be positive")
    require_ok(w["comparable_pairs"] > 0, "W_COMPARABLE_POS", "comparable pairs must be positive")
    real_rate = Fraction(w["real_net"], w["comparable_pairs"])
    flip_rate = Fraction(w["flipped_net"], w["comparable_pairs"])
    require_ok(real_rate == Fraction(11, 58), "W_REAL_RATE", "real rate mismatch")
    require_ok(flip_rate == Fraction(26, 203), "W_FLIP_RATE", "flipped rate mismatch")
    require_ok(gcd(w["real_net"], w["comparable_pairs"]) == 7, "W_REAL_GCD", "real rate gcd mismatch")
    out = dict(w)
    out["real_rate"] = frac_str(real_rate)
    out["flipped_rate"] = frac_str(flip_rate)
    return out


def balanced_numerator(f_pos, r_neg, n_pos, n_neg):
    return f_pos * n_neg - r_neg * n_pos


def verify_balanced_q(f_pos=5, r_neg=5, n_pos=20, n_neg=20, imb_f=18, imb_r=7, imb_npos=264, imb_nneg=167):
    num = balanced_numerator(f_pos, r_neg, n_pos, n_neg)
    require_ok(num == 0, "B_BALANCED_NONZERO", "balanced numerator must be zero")
    require_ok(n_pos == n_neg, "B_COUNTS_UNEQUAL", "balanced counts must be equal")
    imb_num = balanced_numerator(imb_f, imb_r, imb_npos, imb_nneg)
    require_ok(imb_num > 0, "B_IMBALANCED_NONPOS", "imbalanced numerator must be positive")
    require_ok(imb_num == 1158, "B_IMBALANCED_VALUE", "imbalanced numerator value mismatch")
    return {
        "balanced_numerator": num,
        "imbalanced_numerator": imb_num,
        "balanced_weight_pos": frac_str(Fraction(1, 2 * n_pos)),
        "balanced_weight_neg": frac_str(Fraction(1, 2 * n_neg)),
    }


def verify_contraction_q(b_num=1, b_den=50, p_num=45, p_den=60, remainders=(390625, 625, 1, 0), grid_cases=((7, 2, 3), (10, 3, 3), (0, 0, 4))):
    require_ok(Fraction(p_num, p_den) == Fraction(3, 4), "C_P_REDUCED", "p must reduce to 3/4")
    require_ok(b_den > 0, "C_B_DEN_POS", "B denominator must be positive")
    require_ok(3 * b_num * b_num * p_den < p_num * b_den * b_den, "C_GATE", "contraction gate failed")
    factor = Fraction(3 * b_num * b_num * p_den, p_num * b_den * b_den)
    require_ok(factor == Fraction(1, 625), "C_FACTOR", "contraction factor mismatch")
    steps = 0
    idx = 0
    while idx + 1 < len(remainders):
        cur = remainders[idx]
        nxt = remainders[idx + 1]
        require_ok(nxt >= 0, "C_NEXT_NEG", "remainder must be nonnegative")
        require_ok(625 * nxt <= cur, "C_STEP", "remainder step must contract by 625")
        steps = steps + 1
        idx = idx + 1
    grid_checks = 0
    for case in grid_cases:
        x_val = case[0]
        m_val = case[1]
        scale = case[2]
        require_ok(scale > 0, "C_SCALE_POS", "grid scale must be positive")
        defect2 = 2 * (x_val - m_val * scale)
        require_ok(defect2 >= -scale, "C_GRID_LO", "grid defect below lower bound")
        require_ok(defect2 <= scale, "C_GRID_HI", "grid defect above upper bound")
        grid_checks = grid_checks + 1
    return {
        "b": frac_str(Fraction(b_num, b_den)),
        "p": frac_str(Fraction(p_num, p_den)),
        "p_input": str(p_num) + "/" + str(p_den),
        "factor": frac_str(factor),
        "contraction_steps": steps,
        "grid_checks": grid_checks,
    }


def track_base():
    here = Path(__file__).parent
    if here.is_absolute():
        return here
    return Path(os.getcwd()) / here


def _unnormalized_parts(path):
    raw = Path(str(path))
    if raw.is_absolute():
        return raw.parts
    return (Path.cwd() / raw).parts


def check_no_symlink_ancestors(path):
    parts = _unnormalized_parts(path)
    cur = Path("/")
    for seg in parts[1:]:
        cur = cur / seg
        require_ok(cur.is_symlink() is False, "SYMLINK_ANCESTOR", "symlink in path ancestors")


def _open_parent_nofollow(path):
    parts = _unnormalized_parts(path)
    require_ok(len(parts) >= 2, "READ_OPEN", "cannot open file")
    dfd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        for seg in parts[1:-1]:
            nxt = os.open(seg, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
            os.close(dfd)
            dfd = nxt
    except OSError:
        os.close(dfd)
        raise PriorTiltVerifyError("READ_OPEN", "cannot open file")
    return dfd, parts[-1]


def read_strict_bytes(path):
    check_no_symlink_ancestors(path)
    dfd, leaf = _open_parent_nofollow(path)
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError:
            raise PriorTiltVerifyError("READ_OPEN", "cannot open file")
    finally:
        os.close(dfd)
    chunks = []
    try:
        info = os.fstat(fd)
        require_ok(stat.S_ISREG(info.st_mode), "NOT_REGULAR", "not a regular file")
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if chunk == b"":
                break
            total = total + len(chunk)
            require_ok(total <= MAX_BYTES, "TOO_LARGE", "file exceeds size cap")
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def decode_strict_text(raw):
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise PriorTiltVerifyError("BAD_UTF8", "invalid utf-8")
    require_ok(text.startswith("\ufeff") is False, "BAD_BOM", "byte order mark rejected")
    require_ok("\r" not in text, "BAD_LF", "carriage return rejected")
    require_ok(text.endswith("\n"), "BAD_FINAL_LF", "missing final newline")
    return text


def read_strict_text(path):
    return decode_strict_text(read_strict_bytes(path))


def scan_json_text(text):
    depth = 0
    in_str = False
    escaped = False
    digit_run = 0
    saw_float = False
    prev_digit = False
    for ch in text:
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            digit_run = 0
            prev_digit = False
            continue
        if ch == '"':
            in_str = True
            digit_run = 0
            prev_digit = False
            continue
        if ch == "{":
            depth = depth + 1
        if ch == "[":
            depth = depth + 1
        if ch == "}":
            depth = depth - 1
        if ch == "]":
            depth = depth - 1
        require_ok(depth <= MAX_DEPTH, "DEPTH", "nesting depth exceeded")
        require_ok(depth >= 0, "UNBALANCED", "nesting depth went negative")
        if ch.isdigit():
            digit_run = digit_run + 1
            require_ok(digit_run <= MAX_INT_DIGITS, "INT_DIGITS", "integer digit bound exceeded")
            prev_digit = True
        else:
            if ch == ".":
                if prev_digit:
                    saw_float = True
            if ch == "e":
                if prev_digit:
                    saw_float = True
            if ch == "E":
                if prev_digit:
                    saw_float = True
            digit_run = 0
            prev_digit = False
    require_ok(depth == 0, "UNBALANCED_FINAL", "unbalanced nesting")
    require_ok(saw_float is False, "FLOAT_TOKEN", "floating token rejected")
    require_ok(in_str is False, "UNTERMINATED_JSON_STRING", "unterminated json string")


def dup_free_object(pairs):
    out = {}
    for pair in pairs:
        require_ok(pair[0] not in out, "DUP_KEY", "duplicate json key")
        out[pair[0]] = pair[1]
    return out


def reject_constant(_value):
    raise PriorTiltVerifyError("BAD_CONSTANT", "non-json constant rejected")


def parse_strict_json(text):
    scan_json_text(text)
    try:
        data = json.loads(text, object_pairs_hook=dup_free_object, parse_constant=reject_constant)
    except PriorTiltVerifyError:
        raise
    except (json.JSONDecodeError, ValueError):
        raise PriorTiltVerifyError("BAD_JSON", "malformed json")
    require_ok(isinstance(data, dict), "NOT_OBJECT", "top level must be object")
    return data


def read_strict_json(path):
    return parse_strict_json(read_strict_text(path))


def strip_lean_comments_and_strings(src):
    out = []
    i = 0
    n = len(src)
    depth = 0
    in_str = False
    while i < n:
        ch = src[i]
        nxt = ""
        if i + 1 < n:
            nxt = src[i + 1]
        if depth > 0:
            if ch == "/":
                if nxt == "-":
                    depth = depth + 1
                    out.append("  ")
                    i = i + 2
                    continue
            if ch == "-":
                if nxt == "/":
                    depth = depth - 1
                    out.append("  ")
                    i = i + 2
                    continue
            if ch == "\n":
                out.append("\n")
            else:
                out.append(" ")
            i = i + 1
            continue
        if in_str:
            if ch == "\\":
                if i + 1 < n:
                    out.append("  ")
                    i = i + 2
                    continue
            if ch == '"':
                in_str = False
                out.append(" ")
                i = i + 1
                continue
            if ch == "\n":
                out.append("\n")
            else:
                out.append(" ")
            i = i + 1
            continue
        if ch == "-":
            if nxt == "-":
                while i < n:
                    if src[i] == "\n":
                        break
                    out.append(" ")
                    i = i + 1
                continue
        if ch == "/":
            if nxt == "-":
                depth = 1
                out.append("  ")
                i = i + 2
                continue
        if ch == '"':
            in_str = True
            out.append(" ")
            i = i + 1
            continue
        out.append(ch)
        i = i + 1
    require_ok(depth == 0, "UNTERMINATED_BLOCK_COMMENT", "unterminated block comment")
    require_ok(in_str is False, "UNTERMINATED_STRING_LITERAL", "unterminated string literal")
    return "".join(out)


def validate_axiom_lines(lines, expected_count=9):
    non_empty = []
    for ln in lines:
        stripped = ln.strip()
        if stripped != "":
            non_empty.append(stripped)
    require_ok(len(non_empty) == expected_count, "AXIOM_LINE_COUNT", "axiom line count mismatch")
    zero_count = 0
    listed_count = 0
    for ln in non_empty:
        if "does not depend on any axioms" in ln:
            zero_count = zero_count + 1
            continue
        require_ok("depends on axioms:" in ln, "AXIOM_LINE_FORMAT", "unrecognized axiom line")
        rhs = ln.split("depends on axioms:", 1)[1].strip()
        require_ok(rhs.startswith("["), "AXIOM_LBRACKET", "missing opening bracket")
        require_ok(rhs.endswith("]"), "AXIOM_RBRACKET", "missing closing bracket")
        names = []
        for part in rhs[1:-1].split(","):
            item = part.strip()
            if item != "":
                names.append(item)
        for name in names:
            require_ok(name in ALLOWED_AXIOMS, "FORBIDDEN_AXIOM", "axiom not allowlisted")
        listed_count = listed_count + 1
    return {"zero_axiom": zero_count, "listed": listed_count}


def default_live_lean_runner(lean_dir):
    home = os.path.expanduser("~")
    elan_bin = str(Path(home) / ".elan" / "bin")
    env = {}
    env["PATH"] = elan_bin + ":/usr/bin:/bin"
    env["HOME"] = home
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="q42b_live_lean_") as td:
        stage_dir = Path(td) / "lean"
        stage_dir.mkdir()
        for rel in ("lean-toolchain", "lakefile.toml", "lake-manifest.json", "AxiomAudit.lean", "PriorTilt.lean", "PriorTilt/Basic.lean"):
            dst = stage_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((Path(lean_dir) / rel).read_bytes())
        version = subprocess.run(["lean", "--version"], cwd=str(stage_dir), env=env, capture_output=True, text=True, timeout=60, check=False)
        build = subprocess.run(["lake", "build"], cwd=str(stage_dir), env=env, capture_output=True, text=True, timeout=180, check=False)
        audit = subprocess.run(["lake", "env", "lean", "AxiomAudit.lean"], cwd=str(stage_dir), env=env, capture_output=True, text=True, timeout=120, check=False)
    return {
        "version_rc": version.returncode,
        "version_output": version.stdout + version.stderr,
        "build_rc": build.returncode,
        "build_output": build.stdout + build.stderr,
        "axiom_rc": audit.returncode,
        "axiom_stdout": audit.stdout,
    }


def verify_lean_package(base, run_live_lean=False, lean_runner=None):
    lean_dir = Path(base) / "lean"
    require_ok(lean_dir.is_dir(), "MISSING_LEAN_DIR", "lean directory missing")
    toolchain = read_strict_text(lean_dir / "lean-toolchain").strip()
    require_ok(toolchain == "leanprover/lean4:v4.36.0", "BAD_TOOLCHAIN", "toolchain mismatch")
    manifest = read_strict_json(lean_dir / "lake-manifest.json")
    require_ok(manifest.get("packages") == [], "NONEMPTY_PACKAGES", "lake packages must be empty")
    lean_files = sorted(lean_dir.rglob("*.lean"))
    require_ok(len(lean_files) == 3, "LEAN_FILE_COUNT", "lean file count mismatch")
    total_loc = 0
    pub_thms = []
    audited = []
    for lf in lean_files:
        src = read_strict_text(lf)
        total_loc = total_loc + len(src.splitlines())
        cleaned = strip_lean_comments_and_strings(src)
        require_ok(_FORBIDDEN_LEAN_RE.search(cleaned) is None, "LEAN_ESCAPE", "forbidden lean construct")
        for match in _ANY_IMPORT_RE.finditer(cleaned):
            mod = match.group(1).strip()
            require_ok(_VALID_IMPORT_RE.fullmatch(mod) is not None, "BAD_IMPORT", "forbidden lean import")
        if lf.name == "Basic.lean":
            pub_thms = _PUB_THM_RE.findall(cleaned)
        if lf.name == "AxiomAudit.lean":
            audited = _PRINT_RE.findall(cleaned)
    require_ok(len(pub_thms) == EXPECTED_THEOREMS, "THM_COUNT", "public theorem count mismatch")
    require_ok(len(audited) == EXPECTED_THEOREMS, "AUDIT_COUNT", "audited theorem count mismatch")
    require_ok(set(pub_thms) == set(audited), "AUDIT_SET", "audited set mismatch")
    info = {}
    info["toolchain"] = toolchain
    info["lean_files"] = len(lean_files)
    info["lean_loc"] = total_loc
    info["public_theorems"] = len(pub_thms)
    runner = lean_runner
    if runner is None:
        if run_live_lean:
            runner = default_live_lean_runner
    if runner is not None:
        result = runner(lean_dir)
        require_ok(result["version_rc"] == 0, "LEAN_VERSION_RC", "lean version command failed")
        require_ok("4.36.0" in result["version_output"], "BAD_LEAN_VERSION", "lean version mismatch")
        require_ok(result["build_rc"] == 0, "LAKE_BUILD_FAIL", "lake build failed")
        require_ok("warning:" not in result["build_output"].lower(), "LAKE_BUILD_WARNING", "lake build warning")
        require_ok(result["axiom_rc"] == 0, "AXIOM_RC", "axiom audit command failed")
        validate_axiom_lines(result["axiom_stdout"].splitlines(), EXPECTED_THEOREMS)
    return info


def build_payload(base=None, run_live_lean=False, lean_runner=None):
    if base is None:
        base = track_base()
    payload = {}
    payload["schema"] = "s160.q42b.prior_tilt.v1"
    payload["track"] = "S160"
    payload["queue_id"] = "EXP-Q42b"
    payload["witness"] = verify_witness_q()
    payload["balanced"] = verify_balanced_q()
    payload["contraction"] = verify_contraction_q()
    payload["lean"] = verify_lean_package(base, run_live_lean=run_live_lean, lean_runner=lean_runner)
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload["payload_sha256"] = hashlib.sha256(canon).hexdigest()
    return payload


def canonical_cert_bytes(payload):
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    return text.encode("utf-8")


def write_cert(path, payload):
    raw = canonical_cert_bytes(payload)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    try:
        os.write(fd, raw)
    finally:
        os.close(fd)


def emit_error(code, message):
    err = {}
    err["status"] = "FAIL"
    err["code"] = code
    err["message"] = message
    line = json.dumps(err, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    os.write(2, line.encode("utf-8"))


def resolve_cert_path(base, given):
    if given is None:
        return Path(base) / CERT_NAME
    cand = Path(given)
    if cand.is_absolute():
        return cand
    return Path(base) / cand


def run_cli(argv=None):
    parser = argparse.ArgumentParser(description="Track S160 EXP-Q42b prior-tilt verifier")
    parser.add_argument("--check", nargs="?", const=CERT_NAME, default=None)
    parser.add_argument("--write", nargs="?", const=CERT_NAME, default=None)
    parser.add_argument("--standalone", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_out")
    parser.add_argument("--live-lean", action="store_true")
    args = parser.parse_args(argv)
    modes = 0
    if args.check is not None:
        modes = modes + 1
    if args.write is not None:
        modes = modes + 1
    if args.standalone:
        modes = modes + 1
    require_ok(modes <= 1, "MODE_COUNT", "at most one mode allowed")
    check_given = args.check
    if modes == 0:
        check_given = CERT_NAME
    base = track_base()
    payload = build_payload(base=base, run_live_lean=args.live_lean)
    if args.write is not None:
        write_cert(resolve_cert_path(base, args.write), payload)
    if check_given is not None:
        cert = read_strict_json(resolve_cert_path(base, check_given))
        require_ok(cert == payload, "CERT_MISMATCH", "certificate mismatch")
    if args.json_out:
        line = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        os.write(1, line.encode("utf-8"))
    else:
        os.write(1, b"PASS s160.q42b.prior_tilt.v1\n")
    return 0


def main(argv=None):
    try:
        return run_cli(argv)
    except PriorTiltVerifyError as exc:
        emit_error(exc.code, str(exc))
        return 2
    except RecursionError:
        emit_error("RECURSION", "recursion limit exceeded")
        return 2
    except OSError as exc:
        emit_error("OS_ERROR", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())



