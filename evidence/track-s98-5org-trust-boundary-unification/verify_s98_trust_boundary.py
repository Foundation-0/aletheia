#!/usr/bin/env python3
"""
Track S98 Hardened Non-Hollow R10+ Verifier: 5-Org Cross-Language Trust Boundary Unification.

Pure stdlib, ZERO floats, ZERO bare asserts, ZERO .isdigit(), ZERO random.
Enforces:
  - Iterative (non-recursive) Zone-B JSON tree validation (bit_length() <= 8192,
    MAX_INT_DIGITS = 2467, depth <= 64, nodes <= 16384, surrogate-free UTF-8, NUL-free
    strings, exact runtime types rejecting bool/subclasses, no duplicates, no floats/NaN/Inf).
  - Safe regular-file I/O rejecting symlinks (including parent-chain & $PWD symlinks),
    FIFOs/special files (O_NOFOLLOW | O_NONBLOCK), oversized files, and NUL paths.
  - Field-complete independent secondary auditor (`secondary_audit_payload`) enforcing
    exact sub-dict keysets and independent pure-Z/Q recomputation across ALL 4 Pillars
    so zero re-signed semantic forgeries bypass SEC, FR0, or FR1.
  - Zero-TOCTOU private 0o700 temp-copy live Lean 4.36.0 (`--verify-lean`) and native
    Rust `rustc` (`--verify-rust`) verification with $HOME-aware discovery (`0` skips
    in Lean-less / Rust-less CI).
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import s98_trust_boundary_oracle as oracle

MAX_FILE_BYTES = 1048576
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 16384
MAX_INT_DIGITS = 2467
MAX_INT_BITS = 8192

_ASCII_HEX_LOWER = frozenset("0123456789abcdef")

PINNED_LEAN_SHA256 = oracle.LEAN_FILE_SHA256
PINNED_RUST_SHA256 = oracle.RUST_REF_SHA256

CERT_TOP_KEYS = frozenset({"schema", "track_id", "payload_sha256", "certificate_sha256", "payload"})
PAYLOAD_TOP_KEYS = frozenset(
    {
        "pillar_1_zone_canon_v1",
        "pillar_2_r10_lean_trust_gate",
        "pillar_3_c2_anchors_safetensors",
        "pillar_4_provenance_and_lean",
    }
)
ALLOWED_LEAN_AXIOMS = frozenset({"propext"})
_AXIOM_LINE_RE = re.compile(r"^'([^']+)'\s+(does not depend on any axioms|depends on axioms:\s*\[([^\]]*)\])$")


class S98Error(ValueError):
    """Fail-closed Track S98 verification rejection."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise S98Error(code, detail)


def _is_hex64(val: Any) -> bool:
    return type(val) is str and len(val) == 64 and all(ch in _ASCII_HEX_LOWER for ch in val)


def _check_exact_keys(obj: Any, expected: frozenset[str], ctx: str) -> Dict[str, Any]:
    require_ok(type(obj) is dict, "TYPE_MISMATCH", f"{ctx} must be strict dict")
    actual = frozenset(obj.keys())
    require_ok(actual == expected, "KEYSET_MISMATCH", f"{ctx} keyset mismatch")
    return obj


def _parse_q_dict(obj: Any, ctx: str) -> Fraction:
    d = _check_exact_keys(obj, frozenset({"num", "den"}), ctx)
    num = d["num"]
    den = d["den"]
    require_ok(type(num) is int and type(den) is int, "RATIONAL_TYPE", f"{ctx} non-int")
    require_ok(den > 0, "RATIONAL_DEN", f"{ctx} non-positive den")
    require_ok(math.gcd(abs(num), den) == 1, "RATIONAL_UNREDUCED", f"{ctx} not coprime")
    return Fraction(num, den)


def _validate_tree(root: Any) -> None:
    """Iterative Zone-B tree validator: strict types, depth/node/bit/surrogate/NUL bounds."""
    stack: List[Tuple[Any, int]] = [(root, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        require_ok(nodes <= MAX_JSON_NODES, "MAX_NODES_EXCEEDED", "JSON node cap exceeded")
        require_ok(depth <= MAX_JSON_DEPTH, "MAX_DEPTH_EXCEEDED", "JSON depth cap exceeded")
        t = type(item)
        if t is dict:
            for k, v in item.items():
                require_ok(type(k) is str, "NON_STRING_KEY", "dict key must be strict str")
                require_ok("\x00" not in k, "NUL_IN_STRING", "NUL byte in key")
                require_ok(not any(0xD800 <= ord(c) <= 0xDFFF for c in k), "SURROGATE_STRING", "surrogate key")
                stack.append((v, depth + 1))
        elif t is list:
            for elem in item:
                stack.append((elem, depth + 1))
        elif t is str:
            require_ok("\x00" not in item, "NUL_IN_STRING", "NUL byte in string")
            require_ok(not any(0xD800 <= ord(c) <= 0xDFFF for c in item), "SURROGATE_STRING", "surrogate str")
        elif t is int:
            require_ok(item.bit_length() <= MAX_INT_BITS, "INT_BITS_EXCEEDED", "integer bit bound exceeded")
        elif t is bool or item is None:
            continue
        else:
            raise S98Error("FORBIDDEN_TYPE", f"forbidden JSON runtime type {t.__name__}")


def _reject_float(raw: str) -> Any:
    raise S98Error("JSON_FLOAT_FORBIDDEN", f"float rejected: {raw}")


def _reject_constant(raw: str) -> Any:
    raise S98Error("JSON_CONSTANT_FORBIDDEN", f"constant rejected: {raw}")


def _parse_int_strict(raw: str) -> int:
    require_ok(raw != "-0", "NEGATIVE_ZERO", "-0 forbidden")
    body = raw[1:] if raw.startswith("-") else raw
    require_ok(len(body) <= MAX_INT_DIGITS, "INT_DIGITS_EXCEEDED", "integer digit bound exceeded")
    val = int(raw)
    require_ok(val.bit_length() <= MAX_INT_BITS, "INT_BITS_EXCEEDED", "integer bit bound exceeded")
    return val


def _no_dup_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        require_ok(k not in out, "JSON_DUPLICATE_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes) -> Dict[str, Any]:
    require_ok(len(raw) <= MAX_FILE_BYTES, "FILE_TOO_LARGE", "JSON exceeds byte limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S98Error("INVALID_UTF8", "invalid UTF-8") from exc
    require_ok("\x00" not in text, "NUL_IN_JSON", "NUL byte in JSON text")
    try:
        parsed = json.loads(
            text,
            parse_int=_parse_int_strict,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_dup_pairs,
        )
    except S98Error:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise S98Error("INVALID_JSON", f"JSON parse error: {exc}") from exc
    require_ok(type(parsed) is dict, "ROOT_NOT_OBJECT", "JSON root must be object")
    _validate_tree(parsed)
    return parsed


def _check_no_symlink_chain(path: Path) -> None:
    if not path.is_absolute():
        pwd_env = os.environ.get("PWD", "")
        if pwd_env:
            require_ok(os.path.normpath(pwd_env) == os.path.realpath("."), "PWD_SYMLINK", "PWD symlink mismatch")
        base = Path(os.path.realpath("."))
        parts = path.parts
    else:
        base = Path(path.anchor)
        parts = path.parts[1:]
    cur = base
    for part in parts:
        require_ok(part != "..", "PARENT_TRAVERSAL", "parent traversal rejected")
        cur = cur / part
        try:
            st = os.lstat(str(cur))
        except OSError as exc:
            raise S98Error("PATH_UNREADABLE", f"cannot stat {cur.name}") from exc
        require_ok(not stat.S_ISLNK(st.st_mode), "SYMLINK_FORBIDDEN", f"symlink rejected: {cur.name}")


def read_safe_regular_file(path_like: Any) -> bytes:
    require_ok(type(path_like) is str or isinstance(path_like, Path), "INVALID_PATH_TYPE", "path must be str/Path")
    raw_str = str(path_like)
    require_ok(len(raw_str) > 0 and "\x00" not in raw_str, "INVALID_PATH", "empty or NUL path")
    p = Path(raw_str)
    _check_no_symlink_chain(p)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(str(p), flags)
    except OSError as exc:
        raise S98Error("OPEN_FAILED", f"cannot open regular file: {exc}") from exc
    try:
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", "target is not a regular file")
        chunks: List[bytes] = []
        total = 0
        while True:
            buf = os.read(fd, 65536)
            if not buf:
                break
            total += len(buf)
            require_ok(total <= MAX_FILE_BYTES, "FILE_TOO_LARGE", "file exceeds MAX_FILE_BYTES")
            chunks.append(buf)
        return b"".join(chunks)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Independent Pure-Stdlib Zone-Canon-v1 Checker (Distinct from Oracle Parser!)
# ---------------------------------------------------------------------------
def _check_zone_str(s: str) -> None:
    require_ok("\x00" not in s, "NUL_FORBIDDEN", "NUL in zone string")
    for ch in s:
        cp = ord(ch)
        require_ok(not (0xD800 <= cp <= 0xDBFF), "LONE_HIGH_SURROGATE", "high surrogate in zone string")
        require_ok(not (0xDC00 <= cp <= 0xDFFF), "LONE_LOW_SURROGATE", "low surrogate in zone string")


def _validate_zone_tree(root: Any) -> None:
    """Iterative Zone-Canon-v1 tree validator matching exact oracle/Rust caps (depth<=64, nodes<=4096)."""
    stack: List[Tuple[Any, int]] = [(root, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        require_ok(nodes <= oracle.ZONE_CANON_MAX_NODES, "MAX_NODES_EXCEEDED", "zone node cap exceeded")
        t = type(item)
        if t is dict:
            require_ok(depth + 1 <= oracle.ZONE_CANON_MAX_DEPTH, "MAX_DEPTH_EXCEEDED", "zone depth cap exceeded")
            for k, v in item.items():
                _check_zone_str(k)
                stack.append((v, depth + 1))
        elif t is list:
            require_ok(depth + 1 <= oracle.ZONE_CANON_MAX_DEPTH, "MAX_DEPTH_EXCEEDED", "zone depth cap exceeded")
            for elem in item:
                stack.append((elem, depth + 1))
        elif t is str:
            _check_zone_str(item)


def _independent_zone_canon(text: str, profile: str) -> Tuple[bytes, str, str]:
    """Independent stdlib `json.loads` canonicalizer verifying zero parser-engine drift."""
    require_ok(len(text) <= oracle.ZONE_CANON_MAX_BYTES, "INPUT_TOO_LARGE", "zone input byte cap exceeded")

    def _chk_int(raw: str) -> int:
        if raw == "-0":
            raise S98Error("NEGATIVE_ZERO", "-0 rejected")
        body = raw[1:] if raw.startswith("-") else raw
        if len(body) > oracle.ZONE_CANON_MAX_INT_DIGITS:
            raise S98Error("INT_DIGITS_EXCEEDED", "int digits cap")
        v = int(raw)
        if profile == "mde_v0_utf8":
            if abs(v) > oracle.JS_SAFE_INT_MAX:
                raise S98Error("INT_RANGE_EXCEEDED", "int > 2^53-1")
        else:
            if v < oracle.SIGNED_INT256_MIN or v > oracle.SIGNED_INT256_MAX:
                raise S98Error("INT_256_EXCEEDED", "int > 256-bit")
        return v

    def _chk_float(raw: str) -> Any:
        raise S98Error("FLOAT_FORBIDDEN", f"float rejected: {raw}")

    def _chk_const(raw: str) -> Any:
        raise S98Error("BAD_TOKEN", f"constant rejected: {raw}")

    def _chk_dup(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for k, v in pairs:
            if k in d:
                raise S98Error("DUPLICATE_KEY", "dup key")
            d[k] = v
        return d

    try:
        parsed = json.loads(
            text,
            parse_int=_chk_int,
            parse_float=_chk_float,
            parse_constant=_chk_const,
            object_pairs_hook=_chk_dup,
        )
    except S98Error:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise S98Error("ZONE_PARSE_ERR", str(exc)) from exc
    _validate_zone_tree(parsed)
    ensure_ascii = profile == "v1_ascii"
    canon = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=ensure_ascii).encode("utf-8")
    raw_sha = hashlib.sha256(canon).hexdigest()
    dom_sha = hashlib.sha256(oracle.PROFILE_DOMAINS[profile] + canon).hexdigest()
    return canon, raw_sha, dom_sha


def _audit_pillar1(p1: Any) -> None:
    d = _check_exact_keys(
        p1,
        frozenset(
            {
                "spec_id",
                "dos_bounds",
                "mde7_float_drift_cure",
                "unicode_profile_separation",
                "accept_count",
                "reject_count",
                "accept_vectors",
                "reject_vectors",
                "rust_reference_file",
                "rust_reference_sha256",
            }
        ),
        "pillar_1_zone_canon_v1",
    )
    require_ok(d["spec_id"] == "zone-canon-v1", "P1_SPEC_ID", "bad spec_id")
    dos = _check_exact_keys(
        d["dos_bounds"],
        frozenset({"max_input_bytes", "max_depth", "max_nodes", "max_int_digits", "js_safe_int_max", "signed_int64_max", "signed_int256_max_digits"}),
        "p1.dos_bounds",
    )
    require_ok(dos["max_input_bytes"] == 1048576 and dos["max_depth"] == 64 and dos["max_nodes"] == 4096, "P1_DOS", "bad bytes/depth/nodes")
    require_ok(dos["max_int_digits"] == 78 and dos["js_safe_int_max"] == (1 << 53) - 1, "P1_DOS_INT", "bad js/digits")
    require_ok(dos["signed_int64_max"] == (1 << 63) - 1 and dos["signed_int256_max_digits"] == 77, "P1_DOS_I64", "bad i64/i256")

    av = d["accept_vectors"]
    rv = d["reject_vectors"]
    require_ok(type(av) is list and len(av) == len(oracle.ZONE_CANON_ACCEPT_VECTORS), "P1_AC_LEN", "accept len")
    require_ok(type(rv) is list and len(rv) == len(oracle.ZONE_CANON_REJECT_VECTORS), "P1_RJ_LEN", "reject len")
    require_ok(d["accept_count"] == len(av) and d["reject_count"] == len(rv), "P1_COUNTS", "count mismatch")

    row_keys = frozenset({"name", "profile", "canonical_hex", "canonical_bytes", "raw_sha256", "domain_sha256"})
    for idx, (exp_name, exp_prof, raw_inp) in enumerate(oracle.ZONE_CANON_ACCEPT_VECTORS):
        row = _check_exact_keys(av[idx], row_keys, f"p1.accept[{idx}]")
        canon, raw_sha, dom_sha = _independent_zone_canon(raw_inp, exp_prof)
        require_ok(row["name"] == exp_name and row["profile"] == exp_prof, "P1_AC_ID", "accept name/prof")
        require_ok(row["canonical_hex"] == canon.hex() and row["canonical_bytes"] == len(canon), "P1_AC_BYTES", "accept bytes")
        require_ok(row["raw_sha256"] == raw_sha and row["domain_sha256"] == dom_sha, "P1_AC_SHA", "accept sha")

    rj_keys = frozenset({"name", "profile", "rejected_code"})
    for idx, (exp_name, exp_prof, raw_inp) in enumerate(oracle.ZONE_CANON_REJECT_VECTORS):
        row = _check_exact_keys(rv[idx], rj_keys, f"p1.reject[{idx}]")
        require_ok(row["name"] == exp_name and row["profile"] == exp_prof, "P1_RJ_ID", "reject name/prof")
        ind_code = ""
        try:
            _independent_zone_canon(raw_inp, exp_prof)
        except S98Error as exc:
            ind_code = exc.code
        require_ok(ind_code != "", "P1_RJ_MUST_FAIL", "independent parser accepted reject vector")
        require_ok(row["rejected_code"] == ind_code, "P1_RJ_CODE", "reject code mismatch")

    mde7 = _check_exact_keys(
        d["mde7_float_drift_cure"],
        frozenset({"python_legacy_fragment", "rust_legacy_fragment", "python_legacy_sha256", "rust_legacy_sha256", "unified_rational_pair", "unified_canonical_sha256", "unified_domain_sha256"}),
        "p1.mde7",
    )
    require_ok(mde7["python_legacy_fragment"] == '"corpus":1e-05' and mde7["rust_legacy_fragment"] == '"corpus":0.00001', "P1_MDE7_FRAG", "bad mde7 frag")
    require_ok(mde7["python_legacy_sha256"] == "5fdd6fa5d59947b5ad6d201d75b949540ee521152972b575d80464bd33f2e39c", "P1_MDE7_PY", "bad mde7 py sha")
    require_ok(mde7["rust_legacy_sha256"] == "85bdbadfdcf7b3251154587a576d71b43479d00986b43ada5afbcb448ecf3951", "P1_MDE7_RS", "bad mde7 rs sha")
    require_ok(_parse_q_dict(mde7["unified_rational_pair"], "p1.mde7.q") == Fraction(1, 100000), "P1_MDE7_Q", "bad rational pair")
    require_ok(mde7["unified_canonical_sha256"] == av[7]["raw_sha256"] and mde7["unified_domain_sha256"] == av[7]["domain_sha256"], "P1_MDE7_SHA", "bad mde7 unified sha")

    ups = _check_exact_keys(
        d["unicode_profile_separation"],
        frozenset({"utf8_bytes_len", "ascii_bytes_len", "utf8_raw_sha256", "ascii_raw_sha256", "utf8_domain_sha256", "ascii_domain_sha256", "raw_digests_distinct", "domain_digests_distinct"}),
        "p1.unicode_sep",
    )
    u_c, u_raw, u_dom = _independent_zone_canon('{"\u00e9":"\u65e5\u672c","a":"\\u00e9"}', "v1_utf8")
    a_c, a_raw, a_dom = _independent_zone_canon('{"\u00e9":"\u65e5\u672c","a":"\\u00e9"}', "v1_ascii")
    require_ok(ups["utf8_bytes_len"] == len(u_c) and ups["ascii_bytes_len"] == len(a_c), "P1_UPS_LEN", "bad unicode len")
    require_ok(ups["utf8_raw_sha256"] == u_raw and ups["ascii_raw_sha256"] == a_raw, "P1_UPS_RAW", "bad unicode raw sha")
    require_ok(ups["utf8_domain_sha256"] == u_dom and ups["ascii_domain_sha256"] == a_dom, "P1_UPS_DOM", "bad unicode dom sha")
    require_ok(ups["raw_digests_distinct"] is True and ups["domain_digests_distinct"] is True, "P1_UPS_FLAG", "bad distinct flag")
    require_ok(d["rust_reference_file"] == oracle.RUST_REF_FILE_NAME and d["rust_reference_sha256"] == PINNED_RUST_SHA256, "P1_RUST_PIN", "bad rust pin")


def _audit_pillar2(p2: Any) -> None:
    d = _check_exact_keys(
        p2,
        frozenset(
            {
                "attack_count",
                "s98_attacks_blocked",
                "mcproof_pr3_attacks_missed",
                "aletheia_r10_attacks_missed",
                "control_count",
                "false_positives",
                "six_kernel_comparator_names",
                "bendtt_live_audit",
                "attack_matrix",
                "control_matrix",
            }
        ),
        "pillar_2_r10_lean_trust_gate",
    )
    am = d["attack_matrix"]
    cm = d["control_matrix"]
    require_ok(type(am) is list and len(am) == len(oracle.R10_LIVE_ATTACKS), "P2_AM_LEN", "bad attack len")
    require_ok(type(cm) is list and len(cm) == len(oracle.R10_CLEAN_CONTROLS), "P2_CM_LEN", "bad control len")
    mc_miss_cnt = 0
    agy_miss_cnt = 0
    atk_keys = frozenset({"attack_id", "mcproof_pr3_missed", "aletheia_r10_missed", "s98_r10_plus_blocked", "s98_rule_codes"})
    for idx, (aid, mc_m, agy_m, code) in enumerate(oracle.R10_LIVE_ATTACKS):
        row = _check_exact_keys(am[idx], atk_keys, f"p2.attack[{idx}]")
        hits = oracle.scan_lean4_r10_plus(code)
        require_ok(len(hits) > 0, "P2_SCAN_MISS", f"scanner missed {aid}")
        require_ok(row["attack_id"] == aid and row["mcproof_pr3_missed"] is mc_m and row["aletheia_r10_missed"] is agy_m, "P2_ATK_META", "attack meta mismatch")
        require_ok(row["s98_r10_plus_blocked"] is True and row["s98_rule_codes"] == hits, "P2_ATK_HITS", "attack hits mismatch")
        if mc_m:
            mc_miss_cnt += 1
        if agy_m:
            agy_miss_cnt += 1
    ctrl_keys = frozenset({"control_id", "false_positive", "rule_codes"})
    for idx, (cid, code) in enumerate(oracle.R10_CLEAN_CONTROLS):
        row = _check_exact_keys(cm[idx], ctrl_keys, f"p2.ctrl[{idx}]")
        hits = oracle.scan_lean4_r10_plus(code)
        require_ok(len(hits) == 0 and row["control_id"] == cid and row["false_positive"] is False and row["rule_codes"] == [], "P2_CTRL", "control mismatch")
    require_ok(d["attack_count"] == 24 and d["s98_attacks_blocked"] == 24, "P2_ATK_CNT", "bad attack count")
    require_ok(d["mcproof_pr3_attacks_missed"] == mc_miss_cnt and d["aletheia_r10_attacks_missed"] == agy_miss_cnt, "P2_MISS_CNT", "bad miss count")
    require_ok(d["control_count"] == 5 and d["false_positives"] == 0, "P2_CTRL_CNT", "bad control count")
    require_ok(
        d["six_kernel_comparator_names"] == ["lean-paranoid", "lean4lean", "nanoda", "con-leche", "con-ron", "lean-default"],
        "P2_KERNELS",
        "bad 6-kernel list",
    )
    bt = _check_exact_keys(
        d["bendtt_live_audit"],
        frozenset({"repo", "file", "commit", "sha256", "lines", "bytes", "plain_theorems_count", "csimp_theorems_count", "theorems_count", "parser_partial_defs_count", "sorry_count", "native_decide_count", "live_lean436_rc", "kernel_axioms"}),
        "p2.bendtt",
    )
    require_ok(bt["repo"] == "bendlang/bend" and bt["file"] == "bend2/bendtt.lean", "P2_BEND_ID", "bad bend id")
    require_ok(bt["commit"] == oracle.BENDTT_COMMIT and bt["sha256"] == oracle.BENDTT_SHA256, "P2_BEND_SHA", "bad bend sha")
    require_ok(bt["lines"] == 3861 and bt["bytes"] == 169051 and bt["plain_theorems_count"] == 227 and bt["csimp_theorems_count"] == 1 and bt["theorems_count"] == 228 and bt["parser_partial_defs_count"] == 17, "P2_BEND_METRICS", "bad bend metrics")
    require_ok(bt["sorry_count"] == 0 and bt["native_decide_count"] == 0 and bt["live_lean436_rc"] == 0, "P2_BEND_CLEAN", "bad bend clean flags")
    require_ok(bt["kernel_axioms"] == ["Classical.choice", "Quot.sound", "propext"], "P2_BEND_AX", "bad bend axioms")


def _audit_pillar3(p3: Any) -> None:
    d = _check_exact_keys(
        p3,
        frozenset({"weft_c2_exact_gate", "spliceware_byzantine_anchor_defense", "strict_safetensors_and_rmsnorm_e8"}),
        "pillar_3_c2_anchors_safetensors",
    )
    c2 = _check_exact_keys(
        d["weft_c2_exact_gate"],
        frozenset(
            {
                "overflow_scale_exp2",
                "overflow_scaled_sq_norm_q",
                "overflow_accepted",
                "zeno_input_budget_q",
                "zeno_step_cost_q",
                "zeno_remaining_budget_q",
                "zeno_strictly_decreased",
                "neg_cost_accepted",
                "neg_cost_budget_preserved",
                "underflow_accepted",
                "underflow_budget_preserved",
                "royalty_u64_threshold_wei",
                "royalty_bps",
                "royalty_upstream_wei",
                "royalty_weaver_wei",
                "royalty_conserved",
                "mdr_dust_blocked",
                "mdr_real_triggered",
            }
        ),
        "p3.c2",
    )
    require_ok(c2["overflow_scale_exp2"] == 512 and _parse_q_dict(c2["overflow_scaled_sq_norm_q"], "p3.ov") == Fraction(2, 1) and c2["overflow_accepted"] is True, "P3_OV", "bad overflow witness")
    zb = _parse_q_dict(c2["zeno_input_budget_q"], "p3.zb")
    zc = _parse_q_dict(c2["zeno_step_cost_q"], "p3.zc")
    zr = _parse_q_dict(c2["zeno_remaining_budget_q"], "p3.zr")
    require_ok(zb == Fraction(10**16, 1) and zc == Fraction(1, 10) and zr == zb - zc and c2["zeno_strictly_decreased"] is True, "P3_ZENO", "bad zeno witness")
    require_ok(c2["neg_cost_accepted"] is False and c2["neg_cost_budget_preserved"] is True, "P3_NEG", "bad neg cost")
    require_ok(c2["underflow_accepted"] is False and c2["underflow_budget_preserved"] is True, "P3_UF", "bad underflow")
    gross = c2["royalty_u64_threshold_wei"]
    bps = c2["royalty_bps"]
    up = c2["royalty_upstream_wei"]
    wv = c2["royalty_weaver_wei"]
    require_ok(gross == 12297829382473035 and bps == 1500 and up == (gross * bps) // 10000 and wv == gross - up and c2["royalty_conserved"] is True, "P3_ROY", "bad royalty")
    require_ok(c2["mdr_dust_blocked"] is True and c2["mdr_real_triggered"] is True, "P3_MDR", "bad mdr")

    sp = _check_exact_keys(
        d["spliceware_byzantine_anchor_defense"],
        frozenset(
            {
                "host_triangular_anchors",
                "byzantine_op_in_host_pass",
                "byzantine_op_in_host_err",
                "closed_form_loop_free_pass",
                "arx_v3_untouched_lanes_q",
                "tier_self_carried_anchor_verdict",
                "tier_unsafe_4of4_verdict",
                "tier_safe_3of4_stepping_stone_verdict",
                "tier_safe_4of4_promote_verdict",
            }
        ),
        "p3.spliceware",
    )
    anc = sp["host_triangular_anchors"]
    require_ok(anc == [[0, 0], [5, 15], [13, 91], [37, 191]], "P3_ANC", "bad anchors")
    exp_byz_pass = sum(1 for x, y in anc if (x & 0xFF) == y)
    exp_byz_err = sum(abs((x & 0xFF) - y) for x, y in anc)
    require_ok(sp["byzantine_op_in_host_pass"] == exp_byz_pass and sp["byzantine_op_in_host_err"] == exp_byz_err, "P3_BYZ", "bad byzantine score")
    require_ok(sp["closed_form_loop_free_pass"] == 4 and _parse_q_dict(sp["arx_v3_untouched_lanes_q"], "p3.arx") == Fraction(3, 4), "P3_CF_ARX", "bad closed/arx")
    require_ok(
        sp["tier_self_carried_anchor_verdict"] == 0
        and sp["tier_unsafe_4of4_verdict"] == 0
        and sp["tier_safe_3of4_stepping_stone_verdict"] == 2
        and sp["tier_safe_4of4_promote_verdict"] == 1,
        "P3_TIERS",
        "bad tier verdicts",
    )

    st = _check_exact_keys(
        d["strict_safetensors_and_rmsnorm_e8"],
        frozenset(
            {
                "safetensors_pre_zero_overflow_rejected",
                "safetensors_u64_zero_overflow_rejected",
                "safetensors_subbyte_misaligned_rejected",
                "safetensors_valid_f16_4x6_accepted",
                "safetensors_valid_f16_4x6_bytes",
                "safetensors_contiguous_48b_accepted",
                "safetensors_gapped_48b_rejected",
                "rmsnorm_eta_q",
                "rmsnorm_s_lower_q",
                "rmsnorm_s_exact_q",
                "rmsnorm_s_upper_q",
                "rmsnorm_s_upper_dec4",
                "rmsnorm_split_l4_upper_q",
                "rmsnorm_split_l4_factor_q",
            }
        ),
        "p3.st_e8",
    )
    require_ok(
        st["safetensors_pre_zero_overflow_rejected"] is True
        and st["safetensors_u64_zero_overflow_rejected"] is True
        and st["safetensors_subbyte_misaligned_rejected"] is True
        and st["safetensors_valid_f16_4x6_accepted"] is True
        and st["safetensors_valid_f16_4x6_bytes"] == 48
        and st["safetensors_contiguous_48b_accepted"] is True
        and st["safetensors_gapped_48b_rejected"] is True,
        "P3_ST",
        "bad safetensors flags",
    )
    eta = _parse_q_dict(st["rmsnorm_eta_q"], "p3.eta")
    slo = _parse_q_dict(st["rmsnorm_s_lower_q"], "p3.slo")
    sex = _parse_q_dict(st["rmsnorm_s_exact_q"], "p3.sex")
    shi = _parse_q_dict(st["rmsnorm_s_upper_q"], "p3.shi")
    sl4 = _parse_q_dict(st["rmsnorm_split_l4_upper_q"], "p3.sl4")
    sfac = _parse_q_dict(st["rmsnorm_split_l4_factor_q"], "p3.sfac")
    require_ok(eta == Fraction(9, 16) and slo == eta / (2 * (1 + eta)) and sex == Fraction(1, 5) and shi == eta / 2, "P3_E8_Q", "bad rmsnorm sandwich")
    require_ok(st["rmsnorm_s_upper_dec4"] == oracle.fmt_dec4(shi), "P3_E8_DEC4", "bad rmsnorm dec4")
    require_ok(sl4 == shi / 4 and sfac == Fraction(4, 1), "P3_E8_L4", "bad l4 split")


def _audit_pillar4(p4: Any) -> None:
    d = _check_exact_keys(p4, frozenset({"lean_companion", "five_org_upstream_pins", "law4_honesty"}), "pillar_4_provenance_and_lean")
    lc = _check_exact_keys(
        d["lean_companion"],
        frozenset({"file", "sha256", "lakefile_sha256", "toolchain_sha256", "namespace", "theorem_count", "universal_theorem_count", "ground_witness_count", "zero_axiom_count", "propext_only_count", "allowed_axioms"}),
        "p4.lean",
    )
    require_ok(lc["file"] == oracle.LEAN_FILE_NAME and lc["sha256"] == PINNED_LEAN_SHA256, "P4_LEAN_SHA", "bad lean sha")
    require_ok(lc["lakefile_sha256"] == oracle.LAKEFILE_SHA256 and lc["toolchain_sha256"] == oracle.TOOLCHAIN_SHA256, "P4_LAKE_SHA", "bad lake/tc sha")
    require_ok(lc["namespace"] == "S98TrustBoundaryUnification" and lc["theorem_count"] == 19, "P4_LEAN_NS", "bad lean ns/count")
    require_ok(lc["universal_theorem_count"] == 18 and lc["ground_witness_count"] == 1, "P4_LEAN_SPLIT", "bad univ/ground")
    require_ok(lc["zero_axiom_count"] == 8 and lc["propext_only_count"] == 11 and lc["allowed_axioms"] == ["propext"], "P4_LEAN_AX", "bad axiom counts")

    expected_pins = oracle.build_pillar4_provenance_and_lean()["five_org_upstream_pins"]
    pins = d["five_org_upstream_pins"]
    require_ok(type(pins) is list and len(pins) == len(expected_pins), "P4_PINS_LEN", "bad pins len")
    pin_keys = frozenset({"org", "repo", "ref", "artifact", "sha256"})
    for idx, exp in enumerate(expected_pins):
        row = _check_exact_keys(pins[idx], pin_keys, f"p4.pin[{idx}]")
        require_ok(row == exp, "P4_PIN_VAL", f"pin {idx} mismatch")

    l4 = _check_exact_keys(d["law4_honesty"], frozenset({"max_novelty_tier", "n0_prior_art_anchored", "n1_exact_synthesis_verified", "n2_claims"}), "p4.law4")
    require_ok(l4["max_novelty_tier"] == "N1" and l4["n0_prior_art_anchored"] is True and l4["n1_exact_synthesis_verified"] is True and l4["n2_claims"] == 0, "P4_LAW4", "bad law4")


def secondary_audit_payload(payload: Any) -> Dict[str, Any]:
    """Field-complete independent pure-Z/Q auditor (rejects every re-signed semantic forgery)."""
    _validate_tree(payload)
    p = _check_exact_keys(payload, PAYLOAD_TOP_KEYS, "payload")
    _audit_pillar1(p["pillar_1_zone_canon_v1"])
    _audit_pillar2(p["pillar_2_r10_lean_trust_gate"])
    _audit_pillar3(p["pillar_3_c2_anchors_safetensors"])
    _audit_pillar4(p["pillar_4_provenance_and_lean"])
    return {"status": "PASS", "pillars_verified": 4}


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> Dict[str, Any]:
    require_ok(type(full_replay) is bool, "INVALID_FULL_REPLAY", "full_replay must be strict bool")
    _validate_tree(cert)
    c = _check_exact_keys(cert, CERT_TOP_KEYS, "certificate")
    require_ok(c["schema"] == oracle.SCHEMA_VERSION and c["track_id"] == oracle.TRACK_ID, "HEADER_MISMATCH", "bad schema/track_id")
    require_ok(_is_hex64(c["payload_sha256"]) and _is_hex64(c["certificate_sha256"]), "INVALID_HEX64", "bad digest format")

    payload = c["payload"]
    got_payload_sha = hashlib.sha256(oracle.canonical_json_bytes(payload)).hexdigest()
    require_ok(hmac.compare_digest(got_payload_sha, c["payload_sha256"]), "PAYLOAD_SHA_MISMATCH", "payload sha mismatch")
    body = {
        "schema": c["schema"],
        "track_id": c["track_id"],
        "payload_sha256": c["payload_sha256"],
        "payload": payload,
    }
    got_cert_sha = hashlib.sha256(oracle.canonical_json_bytes(body)).hexdigest()
    require_ok(hmac.compare_digest(got_cert_sha, c["certificate_sha256"]), "CERT_SHA_MISMATCH", "certificate sha mismatch")

    secondary_audit_payload(payload)
    if full_replay:
        expected_cert = oracle.build_certificate()
        require_ok(hmac.compare_digest(c["certificate_sha256"], expected_cert["certificate_sha256"]), "ORACLE_DRIFT", "oracle replay drift")

    return {"status": "PASS", "certificate_sha256": c["certificate_sha256"], "full_replay": full_replay}


def verify_certificate_file(path_like: Any, *, full_replay: bool = True) -> Dict[str, Any]:
    raw = read_safe_regular_file(path_like)
    parsed = parse_strict_json_bytes(raw)
    require_ok(raw == oracle.canonical_json_bytes(parsed) + b"\n", "NONCANONICAL_BYTES", "certificate file is not canonical LF-terminated JSON")
    return verify_certificate_dict(parsed, full_replay=full_replay)


def resolve_tool_binary(tool_name: str, home_rel: str) -> Optional[str]:
    found = shutil.which(tool_name)
    if found:
        return found
    home_env = os.environ.get("HOME", "")
    if home_env:
        cand = Path(home_env) / home_rel
        if cand.is_file() and os.access(str(cand), os.X_OK):
            return str(cand)
    return None


def _scrubbed_tool_env() -> Dict[str, str]:
    """Whitelist minimal env vars, scrubbing LEAN_PATH, LEAN_OPTS, RUSTFLAGS, LD_PRELOAD, etc."""
    return {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL")}


def scan_lean4_r10_plus(source: str) -> List[str]:
    """R10+/R11/R12 static Lean 4 pre-filter (paired with mandatory live `#print axioms` kernel verification in `verify_lean4_file_live`; lexes comments, Char literals, raw strings, and plain strings)."""
    return oracle.scan_lean4_r10_plus(source)


def verify_lean4_file_live(path_like: Any, *, check_pinned_sha: bool = True) -> Dict[str, Any]:
    require_ok(type(check_pinned_sha) is bool, "INVALID_CHECK_PINNED_SHA", "check_pinned_sha must be strict bool")
    raw = read_safe_regular_file(path_like)
    file_sha = hashlib.sha256(raw).hexdigest()
    if check_pinned_sha:
        require_ok(hmac.compare_digest(file_sha, PINNED_LEAN_SHA256), "LEAN_SHA_MISMATCH", "lean sha mismatch")
    try:
        src = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S98Error("LEAN_INVALID_UTF8", "invalid UTF-8 in lean file") from exc
    findings = scan_lean4_r10_plus(src)
    require_ok(len(findings) == 0, "LEAN_R10_BLOCKED", f"R10+ static findings: {findings}")
    lean_bin = resolve_tool_binary("lean", ".local/bin/lean")
    require_ok(lean_bin is not None, "LEAN_BINARY_MISSING", "lean binary not found")

    tmp_dir = tempfile.mkdtemp(prefix="s98_lean_")
    try:
        os.chmod(tmp_dir, 0o700)
        tmp_lean = Path(tmp_dir) / oracle.LEAN_FILE_NAME
        tmp_lean.write_bytes(raw)
        proc = subprocess.run(
            [str(lean_bin), str(tmp_lean)],
            capture_output=True,
            text=True,
            timeout=120,
            env=_scrubbed_tool_env(),
        )
        require_ok(proc.returncode == 0 and proc.stderr == "", "LEAN_ELAB_FAILED", f"rc={proc.returncode}")
        verified: List[str] = []
        for line in proc.stdout.splitlines():
            m = _AXIOM_LINE_RE.match(line.strip())
            if m is None:
                continue
            thm = m.group(1)
            ax_body = m.group(3)
            axioms = [a.strip() for a in ax_body.split(",") if a.strip()] if ax_body else []
            for ax in axioms:
                require_ok(ax in ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"{thm} uses {ax}")
            verified.append(thm)
        require_ok(len(verified) > 0, "LEAN_NO_THEOREMS", "no #print axioms theorems verified")
        if check_pinned_sha:
            require_ok(len(verified) == 19, "LEAN_THEOREM_COUNT", f"expected 19 theorems, got {len(verified)}")
        return {
            "status": "PASS",
            "lean_file": oracle.LEAN_FILE_NAME,
            "sha256": file_sha,
            "r10_findings": 0,
            "theorems_verified": len(verified),
            "allowed_axioms": sorted(ALLOWED_LEAN_AXIOMS),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def verify_rust_conformance_live(path_like: Any, *, check_pinned_sha: bool = True) -> Dict[str, Any]:
    require_ok(type(check_pinned_sha) is bool, "INVALID_CHECK_PINNED_SHA", "check_pinned_sha must be strict bool")
    raw = read_safe_regular_file(path_like)
    file_sha = hashlib.sha256(raw).hexdigest()
    if check_pinned_sha:
        require_ok(hmac.compare_digest(file_sha, PINNED_RUST_SHA256), "RUST_SHA_MISMATCH", "rust sha mismatch")
    rustc_bin = resolve_tool_binary("rustc", ".local/bin/rustc")
    require_ok(rustc_bin is not None, "RUSTC_BINARY_MISSING", "rustc binary not found")

    tmp_dir = tempfile.mkdtemp(prefix="s98_rust_")
    try:
        os.chmod(tmp_dir, 0o700)
        tmp_rs = Path(tmp_dir) / oracle.RUST_REF_FILE_NAME
        tmp_bin = Path(tmp_dir) / "zone_canon_v1_ref"
        tmp_rs.write_bytes(raw)
        clean_env = _scrubbed_tool_env()
        cproc = subprocess.run(
            [str(rustc_bin), "-O", "-D", "warnings", str(tmp_rs), "-o", str(tmp_bin)],
            capture_output=True,
            text=True,
            timeout=120,
            env=clean_env,
        )
        require_ok(cproc.returncode == 0, "RUSTC_BUILD_FAILED", cproc.stderr[:200])
        for name, prof, raw_inp in oracle.ZONE_CANON_ACCEPT_VECTORS:
            py_c, py_raw, py_dom = oracle.canonicalize_zone_v1(raw_inp, prof)
            rproc = subprocess.run(
                [str(tmp_bin), "--profile", prof],
                input=raw_inp,
                capture_output=True,
                text=True,
                timeout=30,
                env=clean_env,
            )
            require_ok(rproc.returncode == 0, "RUST_ACCEPT_FAILED", f"{name}: {rproc.stdout}")
            parts = rproc.stdout.strip().split()
            require_ok(len(parts) == 4 and parts[0] == "OK", "RUST_OUTPUT_MALFORMED", name)
            require_ok(parts[1] == py_c.hex() and parts[2] == py_raw and parts[3] == py_dom, "RUST_PYTHON_DRIFT", name)
        for name, prof, raw_inp in oracle.ZONE_CANON_REJECT_VECTORS:
            rproc = subprocess.run(
                [str(tmp_bin), "--profile", prof],
                input=raw_inp,
                capture_output=True,
                text=True,
                timeout=30,
                env=clean_env,
            )
            require_ok(rproc.returncode == 1 and rproc.stdout.startswith("REJECT "), "RUST_REJECT_BYPASS", name)
        uproc = subprocess.run(
            [str(tmp_bin), "--profile", "v1_utf8"],
            input=b"\xff\xfe",
            capture_output=True,
            timeout=30,
            env=clean_env,
        )
        require_ok(uproc.returncode == 1 and uproc.stdout.startswith(b"REJECT INVALID_UTF8"), "RUST_UTF8_BYPASS", "invalid_utf8")
        return {
            "status": "PASS",
            "rust_file": oracle.RUST_REF_FILE_NAME,
            "sha256": file_sha,
            "accept_parity": len(oracle.ZONE_CANON_ACCEPT_VECTORS),
            "reject_parity": len(oracle.ZONE_CANON_REJECT_VECTORS),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S98 Hardened Verifier")
    parser.add_argument("--check", type=str, default="", help="Verify certificate JSON file")
    parser.add_argument("--no-replay", action="store_true", help="Skip oracle full_replay (FR0)")
    parser.add_argument("--verify-lean", type=str, default="", help="Run R10+ static + live Lean 4.36.0 check")
    parser.add_argument("--verify-rust", type=str, default="", help="Compile & verify native Rust zone-canon-v1 parity")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if type(exc.code) is int else 2

    chosen = int(bool(args.check)) + int(bool(args.verify_lean)) + int(bool(args.verify_rust))
    if chosen > 1:
        sys.stderr.write("error: specify at most one of --check, --verify-lean, or --verify-rust\n")
        return 2

    try:
        if chosen == 0:
            res = verify_certificate_file(THIS_DIR / "s98_trust_boundary_certificate.json", full_replay=not args.no_replay)
            sys.stdout.write(json.dumps(res, sort_keys=True, separators=(",", ":")) + "\n")
            return 0
        if args.check:
            res = verify_certificate_file(args.check, full_replay=not args.no_replay)
        elif args.verify_lean:
            res = verify_lean4_file_live(args.verify_lean, check_pinned_sha=True)
        else:
            res = verify_rust_conformance_live(args.verify_rust, check_pinned_sha=True)
    except S98Error as exc:
        if args.json:
            sys.stdout.write(json.dumps({"status": "FAIL", "code": exc.code}, sort_keys=True) + "\n")
        else:
            sys.stderr.write(f"FAIL [{exc.code}]: {exc.detail}\n")
        return 2 if exc.code in ("LEAN_BINARY_MISSING", "RUSTC_BINARY_MISSING") else 1

    if args.json:
        sys.stdout.write(json.dumps(res, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
