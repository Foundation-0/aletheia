#!/usr/bin/env python3
"""Track S160 EXP-Q42c verifier: reciprocity-cycle and correlated-verifier gate.

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
import random
import re
import stat
import subprocess
import tempfile

ALLOWED_AXIOMS = frozenset({"propext", "Quot.sound"})
EXPECTED_THEOREMS = 9
MAX_BYTES = 1048576
MAX_DEPTH = 32
MAX_INT_DIGITS = 256
CERT_NAME = "s160_q42c_reciprocity_certificate.json"

_FORBIDDEN_LEAN_RE = re.compile(
    r"\b(?:sorry|admit|sorryAx|unsafe|native_decide|Classical|implemented_by|extern|macro|elab|elab_rules|syntax|initialize|builtin_initialize|set_option|run_tac)\b"
    r"|\baxiom\b"
    r"|#eval"
    r"|\bIO\."
)
_ANY_IMPORT_RE = re.compile(r"(?:^|\n)[ \t]*import[ \t]+([A-Za-z0-9_.]+)")
_VALID_IMPORT_RE = re.compile(r"ReciprocityGate(?:\.[A-Za-z0-9_]+)*")
_PUB_THM_RE = re.compile(r"(?:^|\n)[ \t]*theorem[ \t]+([A-Za-z0-9_.']+)")
_PRINT_RE = re.compile(r"(?:^|\n)[ \t]*#print[ \t]+axioms[ \t]+ReciprocityGate\.([A-Za-z0-9_.']+)")


class ReciprocityVerifyError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(code + ": " + message)


def require_ok(cond, code, message):
    if cond is not True:
        raise ReciprocityVerifyError(code, message)


def frac_str(value):
    return str(value.numerator) + "/" + str(value.denominator)


def evaluate_correlated_false_accept(eps1, eps2, rho):
    require_ok(eps1 >= Fraction(0, 1), "EPS1_LO", "eps1 below zero")
    require_ok(eps1 <= Fraction(1, 1), "EPS1_HI", "eps1 above one")
    require_ok(eps2 >= Fraction(0, 1), "EPS2_LO", "eps2 below zero")
    require_ok(eps2 <= Fraction(1, 1), "EPS2_HI", "eps2 above one")
    require_ok(rho >= Fraction(0, 1), "RHO_LO", "rho below zero")
    require_ok(rho <= Fraction(1, 1), "RHO_HI", "rho above one")
    mn = min(eps1, eps2)
    indep = eps1 * eps2
    joint = rho * mn + (Fraction(1, 1) - rho) * indep
    excess = joint - indep
    return {
        "eps1": frac_str(eps1),
        "eps2": frac_str(eps2),
        "rho": frac_str(rho),
        "minimum": frac_str(mn),
        "joint": frac_str(joint),
        "independent": frac_str(indep),
        "excess": frac_str(excess),
        "strict": excess > Fraction(0, 1),
    }


def collation_factor(eps_a, eps_b):
    require_ok(eps_a > Fraction(0, 1), "EPSA_POS", "eps_a must be positive")
    require_ok(eps_a <= Fraction(1, 1), "EPSA_HI", "eps_a above one")
    require_ok(eps_b > Fraction(0, 1), "EPSB_POS", "eps_b must be positive")
    require_ok(eps_b <= Fraction(1, 1), "EPSB_HI", "eps_b above one")
    mn = min(eps_a, eps_b)
    prod = eps_a * eps_b
    factor = mn / prod
    return {
        "eps_a": frac_str(eps_a),
        "eps_b": frac_str(eps_b),
        "minimum": frac_str(mn),
        "product": frac_str(prod),
        "factor": frac_str(factor),
        "strict": factor > Fraction(1, 1),
    }


def verify_correlated_witness_q():
    sand = Fraction(1, 10)
    scarlet = Fraction(1, 5)
    ind = evaluate_correlated_false_accept(sand, scarlet, Fraction(0, 1))
    partial = evaluate_correlated_false_accept(sand, scarlet, Fraction(1, 2))
    full = evaluate_correlated_false_accept(sand, scarlet, Fraction(1, 1))
    factor = collation_factor(sand, scarlet)
    return {"independent": ind, "partial": partial, "full": full, "collation": factor}


def reciprocity_decomposition(edge_set):
    pair_dirs = {}
    for edge in edge_set:
        key = tuple(sorted(edge))
        pair_dirs[key] = pair_dirs.get(key, 0) + 1
    mutual = 0
    single = 0
    for key in pair_dirs:
        if pair_dirs[key] == 2:
            mutual = mutual + 1
        if pair_dirs[key] == 1:
            single = single + 1
    trace = 2 * mutual
    total = len(edge_set)
    return {
        "mutual_pairs": mutual,
        "single_pairs": single,
        "trace_a2": trace,
        "skew_pairs": single,
        "total_edges": total,
        "unordered_pairs": len(pair_dirs),
    }


def audit_review_graph_reciprocity(edges, assignments):
    require_ok(isinstance(assignments, dict), "ASSIGNMENTS_DICT", "assignments must be a dict")
    edge_set = set()
    nodes = set()
    for edge in edges:
        require_ok(len(edge) == 2, "EDGE_ARITY", "edge must have two endpoints")
        u_val = edge[0]
        v_val = edge[1]
        require_ok(u_val != v_val, "SELF_REVIEW_FORBIDDEN", "self review forbidden")
        require_ok(u_val in assignments, "UNKNOWN_REVIEWER", "reviewer missing lane assignment")
        require_ok(v_val in assignments, "UNKNOWN_AUTHOR", "author missing lane assignment")
        require_ok(assignments[u_val] != assignments[v_val], "NON_DISJOINT_LANE", "reviewer and author share a lane")
        require_ok((u_val, v_val) not in edge_set, "DUPLICATE_EDGE", "duplicate review edge")
        edge_set.add((u_val, v_val))
        nodes.add(u_val)
        nodes.add(v_val)
    dec = reciprocity_decomposition(edge_set)
    require_ok(dec["mutual_pairs"] == 0, "RECIPROCITY_2CYCLE_DETECTED", "mutual review 2-cycle detected")
    return {
        "nodes": len(nodes),
        "edges": len(edge_set),
        "mutual_pairs": dec["mutual_pairs"],
        "trace_a2": dec["trace_a2"],
        "skew_pairs": dec["skew_pairs"],
        "admitted": True,
    }


def canonical_assignments():
    return {
        "sand-sail": "lane-a",
        "scarlet-nail": "lane-b",
        "cedar-fern": "lane-a",
        "indigo-reef": "lane-b",
        "amber-fjord": "lane-a",
    }


def canonical_honest_edges():
    return (
        ("sand-sail", "scarlet-nail"),
        ("scarlet-nail", "cedar-fern"),
        ("cedar-fern", "indigo-reef"),
        ("indigo-reef", "amber-fjord"),
        ("sand-sail", "indigo-reef"),
    )


def verify_graph_witness_q():
    honest = audit_review_graph_reciprocity(canonical_honest_edges(), canonical_assignments())
    colluding = reciprocity_decomposition({("sand-sail", "scarlet-nail"), ("scarlet-nail", "sand-sail"), ("cedar-fern", "indigo-reef")})
    return {"honest": honest, "colluding_decomposition": colluding}


def exact_auroc(pos_scores, neg_scores):
    require_ok(len(pos_scores) > 0, "AUROC_POS_EMPTY", "positive scores must be nonempty")
    require_ok(len(neg_scores) > 0, "AUROC_NEG_EMPTY", "negative scores must be nonempty")
    wins = 0
    ties = 0
    for p_score in pos_scores:
        for q_score in neg_scores:
            if p_score > q_score:
                wins = wins + 1
            if p_score == q_score:
                ties = ties + 1
    compared = len(pos_scores) * len(neg_scores)
    auroc = Fraction(2 * wins + ties, 2 * compared)
    return {"wins": wins, "ties": ties, "compared": compared, "auroc": frac_str(auroc)}


def rate_at_threshold(scores, threshold):
    require_ok(len(scores) > 0, "RATE_EMPTY", "scores must be nonempty")
    ge_count = 0
    for score in scores:
        if score >= threshold:
            ge_count = ge_count + 1
    return {"ge_count": ge_count, "total": len(scores), "rate": frac_str(Fraction(ge_count, len(scores)))}


def run_reciprocity_benchmark(seed=16042, trials=20, nodes=24, planted_pairs=6):
    require_ok(trials > 0, "BENCH_TRIALS_POS", "benchmark trials must be positive")
    require_ok(planted_pairs > 0, "BENCH_PAIRS_POS", "planted pairs must be positive")
    require_ok(nodes > 2 * planted_pairs, "BENCH_NODES_FIT", "nodes must exceed twice planted pairs")
    rng = random.Random(seed)
    planted_scores = []
    null_scores = []
    planted_edge_counts = []
    null_edge_counts = []
    trial = 0
    while trial < trials:
        names = []
        idx = 0
        while idx < nodes:
            names.append("n" + str(idx))
            idx = idx + 1
        order = list(names)
        rng.shuffle(order)
        planted = set()
        pos = 0
        while pos + 1 < nodes:
            planted.add((order[pos], order[pos + 1]))
            pos = pos + 1
        pair_idx = 0
        while pair_idx < planted_pairs:
            a_val = order[2 * pair_idx]
            b_val = order[2 * pair_idx + 1]
            planted.add((a_val, b_val))
            planted.add((b_val, a_val))
            pair_idx = pair_idx + 1
        out_stubs = []
        in_stubs = []
        for node in names:
            out_count = 0
            in_count = 0
            for edge in planted:
                if edge[0] == node:
                    out_count = out_count + 1
                if edge[1] == node:
                    in_count = in_count + 1
            k_val = 0
            while k_val < out_count:
                out_stubs.append(node)
                k_val = k_val + 1
            k_val = 0
            while k_val < in_count:
                in_stubs.append(node)
                k_val = k_val + 1
        rng.shuffle(in_stubs)
        null_graph = set()
        stub_idx = 0
        while stub_idx < len(out_stubs):
            u_val = out_stubs[stub_idx]
            w_val = in_stubs[stub_idx]
            if u_val != w_val:
                null_graph.add((u_val, w_val))
            stub_idx = stub_idx + 1
        planted_scores.append(reciprocity_decomposition(planted)["mutual_pairs"])
        null_scores.append(reciprocity_decomposition(null_graph)["mutual_pairs"])
        planted_edge_counts.append(len(planted))
        null_edge_counts.append(len(null_graph))
        trial = trial + 1
    stats = exact_auroc(planted_scores, null_scores)
    wins = stats["wins"]
    ties = stats["ties"]
    compared = stats["compared"]
    auroc = Fraction(2 * wins + ties, 2 * compared)
    threshold = 4
    null_rate = rate_at_threshold(null_scores, threshold)
    planted_rate = rate_at_threshold(planted_scores, threshold)
    fpr = Fraction(null_rate["ge_count"], trials)
    tpr = Fraction(planted_rate["ge_count"], trials)
    require_ok(auroc >= Fraction(95, 100), "BENCH_AUROC", "benchmark AUROC below 95/100")
    require_ok(fpr < Fraction(1, 100), "BENCH_FPR", "benchmark FPR at or above 1/100")
    require_ok(tpr == Fraction(1, 1), "BENCH_TPR", "benchmark TPR must be one")
    return {
        "seed": seed,
        "trials": trials,
        "nodes": nodes,
        "planted_pairs": planted_pairs,
        "threshold": threshold,
        "planted_scores": planted_scores,
        "null_scores": null_scores,
        "planted_edge_counts": planted_edge_counts,
        "null_edge_counts": null_edge_counts,
        "wins": wins,
        "ties": ties,
        "compared": compared,
        "auroc": frac_str(auroc),
        "fpr": frac_str(fpr),
        "tpr": frac_str(tpr),
    }


def track_base():
    here = Path(__file__).parent
    if here.is_absolute():
        return here
    return Path(os.getcwd()) / here


def check_no_symlink_ancestors(path):
    cur = Path(os.path.abspath(str(path)))
    chain = [cur]
    chain.extend(list(cur.parents))
    for item in chain:
        require_ok(item.is_symlink() is False, "SYMLINK_ANCESTOR", "symlink in path ancestors")


def read_strict_bytes(path):
    check_no_symlink_ancestors(path)
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ReciprocityVerifyError("READ_OPEN", "cannot open file")
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
        raise ReciprocityVerifyError("BAD_UTF8", "invalid utf-8")
    require_ok(text.startswith(chr(65279)) is False, "BAD_BOM", "byte order mark rejected")
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
    raise ReciprocityVerifyError("BAD_CONSTANT", "non-json constant rejected")


def parse_strict_json(text):
    scan_json_text(text)
    try:
        data = json.loads(text, object_pairs_hook=dup_free_object, parse_constant=reject_constant)
    except json.JSONDecodeError:
        raise ReciprocityVerifyError("BAD_JSON", "malformed json")
    except RecursionError:
        raise ReciprocityVerifyError("RECURSION", "recursion limit exceeded")
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
    with tempfile.TemporaryDirectory(prefix="q42c_live_lean_") as td:
        stage_dir = Path(td) / "lean"
        stage_dir.mkdir()
        for rel in ("lean-toolchain", "lakefile.toml", "lake-manifest.json", "AxiomAudit.lean", "ReciprocityGate.lean", "ReciprocityGate/Basic.lean"):
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
    try:
        dir_fd = os.open(str(lean_dir), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise ReciprocityVerifyError("MISSING_LEAN_DIR", "lean directory missing")
    os.close(dir_fd)
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
    info["live_lean"] = False
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
    payload["schema"] = "s160.q42c.reciprocity_gate.v1"
    payload["track"] = "S160"
    payload["queue_id"] = "EXP-Q42c"
    payload["correlated"] = verify_correlated_witness_q()
    payload["graph"] = verify_graph_witness_q()
    payload["benchmark"] = run_reciprocity_benchmark()
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
    parser = argparse.ArgumentParser(description="Track S160 EXP-Q42c reciprocity gate verifier")
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
        os.write(1, b"PASS s160.q42c.reciprocity_gate.v1\n")
    return 0


def main(argv=None):
    try:
        return run_cli(argv)
    except ReciprocityVerifyError as exc:
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

