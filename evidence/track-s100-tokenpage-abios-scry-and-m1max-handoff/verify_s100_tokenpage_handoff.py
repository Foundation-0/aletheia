#!/usr/bin/env python3
"""
Track S100 Hardened Field-Complete Zone-B Verifier, Read-Only Pin Auditor
& R10+ Pure-Init Lean 4.36.0 Gate.

Supports:
  --standalone --json       Compute canonical certificate and print to stdout
  --write <cert.json>       Atomically write canonical 0o600 certificate JSON via dir_fd + fsync
  --check <cert.json>       Fail-closed Zone-B verification of certificate JSON on disk
  --verify-lean <file>      R10+ static Lean 4 audit + live Lean 4.36.0 --stdin kernel check
  --verify-pins             Read-only SHA-256 & anchor consistency audit on disk

Zero floats, zero bare asserts, zero external dependencies, zero RNG.
"""
from __future__ import annotations

import argparse
import errno
from fractions import Fraction
import hashlib
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

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from s100_tokenpage_handoff_oracle import (
    ABIOS_RFVM_FORMS,
    ANCHOR_PIN,
    EXPECTED_LEAN_SHA256,
    EXPECTED_LEAN_THEOREMS,
    LEAN_FILE_NAME,
    LEAN_TOOLCHAIN,
    NOVELTY_TIER,
    ORACLE_CLASS,
    S92_BILINGUAL_TOTALS,
    S92_TREATISE_TOTALS,
    SCHEMA_VERSION,
    TOKENIZER_PINS,
    TRACK_ID,
    UPSTREAM_CERT_PINS,
    WAVE_FIXTURE_PINS,
    build_certificate_envelope,
    canonical_json_bytes,
    dec_str,
    q_str,
    require_ok,
)

MAX_JSON_BYTES = 1_048_576
MAX_PIN_BYTES = 16_777_216
MAX_JSON_DEPTH = 48
MAX_INT_BITS = 2048
MAX_INT_DIGITS = 617
_READ_CHUNK = 65_536
_EXACT_PATH_TYPES = (Path, type(Path()))

REQUIRED_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
REQUIRED_PAYLOAD_KEYS = frozenset(
    {
        "track_id",
        "oracle_class",
        "novelty_tier",
        "all_pillars_verified",
        "pillar_1_tokenizer_protocol_and_arabic_density",
        "pillar_2_vocab_surgery_and_s31_dpi_bounds",
        "pillar_3_three_node_m1max_and_edge_handoff_pack",
        "pillar_4_provenance_and_lean4",
    }
)
_PAYLOAD_BOOL_KEYS = frozenset(
    {
        "all_four_ablations_rejected",
        "all_four_gates_pass",
        "all_pillars_verified",
        "all_theorems_universally_quantified",
        "all_verified",
        "defect1_silent_loss_confirmed",
        "defect2_corruption_confirmed",
        "defect3_arity_crash_confirmed",
        "dual_load_fits_m1max_64gib",
        "fits_m1max_64gib",
        "fixed_codec_all_bijective",
        "gate1_sha_pinned",
        "gate2_memory_resident",
        "gate3_zero_float_predicate",
        "gate4_deterministic_kill_gate",
        "householder_involution_exact",
        "n0_prior_art_anchored",
        "n1_exact_synthesis_verified",
        "raw_arabic_strictly_cheaper",
        "spike_exceeds_unity",
        "tokenpage_sign_reversal_verified",
        "wan_never_beats_prefill",
        "zero_dataset_copies_in_expedition",
    }
)
HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_CANON_INT_RE = re.compile(r"\A(?:0|-?[1-9][0-9]*)\Z")
_CANON_POS_INT_RE = re.compile(r"\A[1-9][0-9]*\Z")

# R12 Strict Static Lean 4 Scanner (Comment-Only Strip + Quote/Guillemet Ban + End-Anchored decide + dbgTrace/panic/warn.sorry)
_LEAN_QUOTE_OR_GUILLEMET_RE = re.compile(r'["\'«»]')
_LEAN_FORBIDDEN_RE = re.compile(
    r"\b(?:sorry|admit|axiom|unsafe|native_decide|bv_decide|decide_cbv|sorryAx|"
    r"ofReduceBool|ofReduceNat|trustCompiler|mkSorry|"
    r"elab|elab_rules|macro|macro_rules|syntax|declare_syntax_cat|"
    r"notation|prefix|infix|infixl|infixr|postfix|"
    r"initialize|builtin_initialize|opaque|"
    r"dbg_trace|dbg_sleep|dbg_stack_trace|dbgTrace|dbgTraceVal|dbgTraceIfShared|dbgSleep|dbgStackTrace|"
    r"panic|panicCore|panicWithPosWithDecl|unreachable|throwError|"
    r"run_cmd|run_meta|interpolatedStr)\b"
)
_LEAN_PARTIAL_RE = re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev|theorem)\b")
_LEAN_DECIDE_NATIVE_RE = re.compile(
    r"(?<!\w)\+\s*native\b"
    r"|\bnative\s*:=(?!\s*(?:Bool\.)?false\s*(?:[),}]|\Z))"
    r"|\{[^}]*\bnative\b(?!\s*:=\s*(?:Bool\.)?false\s*[,}])"
    r"|\bconfig\s*:=(?!\s*\{\s*native\s*:=\s*(?:Bool\.)?false\s*\}\s*[)])"
    r"|\bDecide(?:Config|\.Config)\b"
    r"|\bdecide\s*\(\s*revert\b"
)
_LEAN_SKIP_TC_RE = re.compile(
    r"\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b"
    r"|\bwarn\s*\.\s*sorry\b"
)
_LEAN_EVAL_SPOOF_RE = re.compile(
    r"#(?:eval!?|reduce|guard_msgs|guard|exit)\b|"
    r"#print\s+(?!axioms\s+(?!example\b|def\b|theorem\b|lemma\b)[A-Za-z0-9_.]+\s*(?:\n|\Z))"
)
_LEAN_ATTR_ESCAPE_RE = re.compile(
    r"(?:@\[|\battribute\s*\[)[^\]]*\b(?:"
    r"extern|implemented_by|export|csimp|init|builtin_init|"
    r"term_elab|command_elab|tactic|macro|macro_rules|"
    r"builtin_term_elab|builtin_command_elab|builtin_tactic|builtin_macro|builtin_macro_rules)\b"
)
_LEAN_IMPORT_RE = re.compile(
    r"(?:^|\n)\s*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)"
)
_ZERO_AXIOM_LINE_RE = re.compile(r"\A'([A-Za-z0-9_.]+)' does not depend on any axioms\Z")
_DEPENDS_AXIOM_LINE_RE = re.compile(r"\A'([A-Za-z0-9_.]+)' depends on axioms: \[([A-Za-z0-9_., ]+)\]\Z")
_ALLOWED_LEAN_AXIOMS = frozenset({"propext"})


# ---------------------------------------------------------------------------
# Strict Zone-B Zero-Float JSON, Rational & Digest Primitives
# ---------------------------------------------------------------------------

def _is_sha256_hex(val: Any) -> bool:
    return type(val) is str and bool(HEX64_RE.match(val))


def parse_canonical_q(val: Any, code: str) -> Fraction:
    require_ok(type(val) is str, code)
    if "/" not in val:
        require_ok(bool(_CANON_INT_RE.match(val)), code)
        require_ok(len(val.lstrip("-")) <= MAX_INT_DIGITS, code)
        return Fraction(int(val), 1)
    parts = val.split("/")
    require_ok(len(parts) == 2, code)
    n_s, d_s = parts
    require_ok(bool(_CANON_INT_RE.match(n_s)) and bool(_CANON_POS_INT_RE.match(d_s)), code)
    require_ok(len(n_s.lstrip("-")) <= MAX_INT_DIGITS and len(d_s) <= MAX_INT_DIGITS, code)
    num, den = int(n_s), int(d_s)
    require_ok(den >= 2 and math.gcd(abs(num), den) == 1, code)
    return Fraction(num, den)


def _check_json_tree(root: Any) -> None:
    active: set[int] = set()
    frames: list[tuple[Any, int, bool]] = [(root, 0, False)]
    while frames:
        obj, depth, is_exit = frames.pop()
        if is_exit:
            active.discard(obj)
            continue
        require_ok(depth <= MAX_JSON_DEPTH, "JSON_MAX_DEPTH_EXCEEDED")
        t = type(obj)
        if obj is None or t is bool:
            continue
        if t is int:
            require_ok(obj.bit_length() <= MAX_INT_BITS, "JSON_INT_TOO_LARGE")
            continue
        if t is str:
            require_ok("\x00" not in obj, "JSON_NUL_IN_STRING")
            for ch in obj:
                c = ord(ch)
                require_ok(not (0xD800 <= c <= 0xDFFF), "JSON_LONE_SURROGATE")
            continue
        if t is list:
            oid = id(obj)
            require_ok(oid not in active, "JSON_CYCLE")
            active.add(oid)
            frames.append((oid, depth, True))
            for item in obj:
                frames.append((item, depth + 1, False))
            continue
        if t is dict:
            oid = id(obj)
            require_ok(oid not in active, "JSON_CYCLE")
            active.add(oid)
            frames.append((oid, depth, True))
            for k, v in obj.items():
                require_ok(type(k) is str, "JSON_NON_STRING_KEY")
                frames.append((k, depth + 1, False))
                frames.append((v, depth + 1, False))
            continue
        raise ValueError(f"JSON_DISALLOWED_TYPE:{t.__name__}")


def _no_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        require_ok(k not in out, f"JSON_DUPLICATE_KEY:{k}")
        out[k] = v
    return out


def _parse_capped_int(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    require_ok(len(digits) <= MAX_INT_DIGITS, "JSON_INT_TOO_LARGE")
    val = int(token)
    require_ok(val.bit_length() <= MAX_INT_BITS, "JSON_INT_TOO_LARGE")
    return val


def _forbid_float(token: str) -> Any:
    raise ValueError(f"JSON_FLOAT_FORBIDDEN:{token}")


def _forbid_constant(token: str) -> Any:
    raise ValueError(f"JSON_CONSTANT_FORBIDDEN:{token}")


def parse_strict_json_bytes(raw: bytes, *, trailing_lf: bool = True) -> dict[str, Any]:
    require_ok(b"\r" not in raw, "CRLF_FORBIDDEN")
    require_ok(b"\x00" not in raw, "NUL_BYTE_IN_JSON")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("INVALID_UTF8") from exc
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_no_dup_keys,
            parse_int=_parse_capped_int,
            parse_float=_forbid_float,
            parse_constant=_forbid_constant,
        )
    except ValueError:
        raise
    except RecursionError as exc:
        raise ValueError("JSON_MAX_DEPTH_EXCEEDED") from exc
    require_ok(type(parsed) is dict, "JSON_ROOT_NOT_OBJECT")
    _check_json_tree(parsed)
    expected = canonical_json_bytes(parsed) + (b"\n" if trailing_lf else b"")
    require_ok(raw == expected, "NON_CANONICAL_JSON_BYTES")
    return parsed


def exact_typed_equal(lhs: Any, rhs: Any) -> bool:
    stack: list[tuple[Any, Any]] = [(lhs, rhs)]
    while stack:
        a, b = stack.pop()
        if type(a) is not type(b):
            return False
        if type(a) is dict:
            if len(a) != len(b):
                return False
            for k, va in a.items():
                if k not in b:
                    return False
                stack.append((va, b[k]))
        elif type(a) is list:
            if len(a) != len(b):
                return False
            for va, vb in zip(a, b):
                stack.append((va, vb))
        elif a != b:
            return False
    return True


# ---------------------------------------------------------------------------
# Hardened dir_fd File I/O (PWD Symlink, FIFO, Hardlink, 0o600 Atomic Write)
# ---------------------------------------------------------------------------

def _validate_path(path: Any) -> None:
    require_ok(type(path) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE")
    raw = str(path)
    require_ok("\x00" not in raw, "INVALID_PATH")
    for ch in raw:
        require_ok(not (0xD800 <= ord(ch) <= 0xDFFF), "INVALID_PATH_SURROGATE")


def _check_pwd_no_symlinks() -> None:
    pwd = os.environ.get("PWD")
    if pwd is None or not os.path.isabs(pwd):
        return
    for ch in pwd:
        require_ok(not (0xD800 <= ord(ch) <= 0xDFFF), "INVALID_PWD_SURROGATE")
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in Path(pwd).parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise ValueError(f"SYMLINK_IN_PATH:{comp}") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
    finally:
        os.close(cur_fd)


def _open_parent_dir_fd(path: Path) -> tuple[int, str]:
    _validate_path(path)
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    require_ok(len(parts) >= 1 and parts[-1] not in ("", ".", ".."), "INVALID_PATH")
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise ValueError(f"SYMLINK_IN_PATH:{comp}") from exc
                raise ValueError(f"INVALID_PARENT_DIR:{comp}") from exc
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, leaf
    except BaseException:
        os.close(cur_fd)
        raise


def read_regular_file_bytes(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    dir_fd, leaf = _open_parent_dir_fd(path)
    fd = -1
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ValueError(f"SYMLINK_IN_PATH:{leaf}") from exc
            raise ValueError(f"FILE_OPEN_ERROR:{leaf}") from exc
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE")
        require_ok(st.st_nlink == 1, "HARDLINK_FORBIDDEN")
        require_ok(st.st_size <= max_bytes, "FILE_TOO_LARGE")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, _READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            require_ok(total <= max_bytes, "FILE_TOO_LARGE")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dir_fd)


def atomic_write_0600(path: Path, data: bytes) -> None:
    dir_fd, leaf = _open_parent_dir_fd(path)
    tmp_name = ""
    fd = -1
    try:
        try:
            st_ex = os.lstat(leaf, dir_fd=dir_fd)
            require_ok(not stat.S_ISLNK(st_ex.st_mode), "SYMLINK_IN_PATH")
            require_ok(stat.S_ISREG(st_ex.st_mode), "TARGET_NOT_REGULAR")
            require_ok(st_ex.st_nlink == 1, "HARDLINK_FORBIDDEN")
        except FileNotFoundError:
            pass
        tmp_name = f".{leaf}.{secrets.token_hex(8)}.tmp"
        fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=dir_fd)
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(data):
            n = os.write(fd, view[written:])
            if n <= 0:
                raise OSError("SHORT_WRITE")
            written += n
        os.fsync(fd)
        st_tmp = os.fstat(fd)
        require_ok(st_tmp.st_nlink == 1, "TMP_HARDLINK_DETECTED")
        os.close(fd)
        fd = -1
        try:
            st_re = os.lstat(leaf, dir_fd=dir_fd)
            require_ok(not stat.S_ISLNK(st_re.st_mode), "SYMLINK_IN_PATH")
        except FileNotFoundError:
            pass
        os.replace(tmp_name, leaf, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        tmp_name = ""
        os.fsync(dir_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_name:
            try:
                os.unlink(tmp_name, dir_fd=dir_fd)
            except OSError:
                pass
        os.close(dir_fd)


# ---------------------------------------------------------------------------
# Field-Complete Independent Semantic Auditor (SEC & FR0 — Zero Re-Signed Bypasses)
# ---------------------------------------------------------------------------

def _req_dict(val: Any, code: str) -> dict[str, Any]:
    require_ok(type(val) is dict, code)
    return val


def _req_exact_dict(val: Any, keys: frozenset[str], code: str) -> dict[str, Any]:
    d = _req_dict(val, code)
    require_ok(frozenset(d.keys()) == keys, code)
    return d


def _req_int(val: Any, code: str) -> int:
    require_ok(type(val) is int, code)
    return val


def _req_str(val: Any, code: str) -> str:
    require_ok(type(val) is str, code)
    return val


def _req_list(val: Any, length: int, code: str) -> list[Any]:
    require_ok(type(val) is list and len(val) == length, code)
    return val


def _check_all(checks: list[tuple[bool, str]]) -> None:
    for cond, code in checks:
        require_ok(cond, code)


def _check_sha_eq(val: Any, expected: str, code: str) -> None:
    require_ok(_is_sha256_hex(val), code)
    require_ok(hmac.compare_digest(val, expected), code)


def _check_q_dec(d: dict[str, Any], q_key: str, dec_key: str, expected: Fraction, digits: int, code: str) -> None:
    require_ok(parse_canonical_q(d[q_key], code) == expected, code)
    require_ok(_req_str(d[dec_key], code) == dec_str(expected, digits), code)


_P1_KEYS = frozenset(
    {
        "abios_sym2p_4form_audit",
        "aletheia_8glyph_and_5cert_audit",
        "s92_arabic_vocab_tax_and_compounding",
        "representation_vs_readout_gauge_gap",
        "abios_pr39_wire_lists_codec_audit",
        "all_verified",
    }
)
_P1_ABIOS_KEYS = frozenset(
    {
        "packet_count",
        "source_sha256",
        "forms",
        "qwen25_sym2p_vs_markdown_saving_q",
        "qwen25_sym2p_vs_markdown_saving_dec4",
        "qwen25_abios3_full_vs_sym2p_saving_q",
        "qwen25_abios3_full_vs_sym2p_saving_dec4",
        "qwen25_abios3_full_vs_markdown_saving_q",
        "qwen25_abios3_full_vs_markdown_saving_dec4",
        "smollm2_abios3_full_vs_sym2p_saving_q",
        "smollm2_abios3_full_vs_sym2p_saving_dec4",
        "smollm2_abios3_full_vs_markdown_saving_q",
        "smollm2_abios3_full_vs_markdown_saving_dec4",
        "qwen25_abios3_vs_sym2p_breakeven_packets",
        "smollm2_abios3_vs_sym2p_breakeven_packets",
    }
)
_FORM_ENTRY_KEYS = frozenset({"utf8_bytes", "qwen25_tokens", "smollm2_tokens"})
_P1_ALETHEIA_KEYS = frozenset(
    {
        "glyph_count",
        "glyph_qwen25_total_tokens",
        "glyph_smollm2_total_tokens",
        "glyph_qwen25_mean_tok_per_glyph_q",
        "glyph_smollm2_mean_tok_per_glyph_q",
        "expr_glyph_qwen25_tokens",
        "expr_ascii_qwen25_tokens",
        "expr_reserved_8tok_qwen25_tokens",
        "expr_glyph_smollm2_tokens",
        "expr_ascii_smollm2_tokens",
        "expr_reserved_8tok_smollm2_tokens",
        "qwen25_reserved_vs_glyph_saving_q",
        "qwen25_reserved_vs_glyph_saving_dec4",
        "smollm2_reserved_vs_glyph_saving_q",
        "smollm2_reserved_vs_glyph_saving_dec4",
        "frozen_cert_count",
        "frozen_cert_total_bytes",
        "frozen_cert_qwen25_tokens",
        "frozen_cert_smollm2_tokens",
        "frozen_cert_qwen25_bytes_per_tok_q",
        "frozen_cert_qwen25_bytes_per_tok_dec4",
        "frozen_cert_smollm2_bytes_per_tok_q",
        "frozen_cert_smollm2_bytes_per_tok_dec4",
    }
)
_P1_ARABIC_KEYS = frozenset(
    {
        "treatise_count",
        "treatises_utf8_bytes",
        "treatises_whitespace_words",
        "treatises_qwen25_tokens",
        "treatises_smollm2_tokens",
        "treatises_extra_smollm2_tokens",
        "treatises_smol_over_qwen_q",
        "treatises_smol_over_qwen_dec4",
        "treatises_min_ratio_q",
        "treatises_min_ratio_dec4",
        "treatises_max_ratio_q",
        "treatises_max_ratio_dec4",
        "bilingual_catalog_count",
        "bilingual_pair_count",
        "bilingual_qwen25_ar_tokens",
        "bilingual_qwen25_en_tokens",
        "bilingual_smollm2_ar_tokens",
        "bilingual_smollm2_en_tokens",
        "bilingual_qwen25_ar_over_en_q",
        "bilingual_qwen25_ar_over_en_dec4",
        "bilingual_smollm2_ar_over_en_q",
        "bilingual_smollm2_ar_over_en_dec4",
        "cross_tokenizer_tax_amplification_q",
        "cross_tokenizer_tax_amplification_dec4",
        "compounding_ladder",
    }
)
_COMP_ROW_KEYS = frozenset(
    {
        "label",
        "simplex_order_k",
        "edges_m",
        "bpe_tax_q",
        "bpe_tax_dec4",
        "simplex_retention_q",
        "simplex_retention_dec6",
        "en_over_ar_cost_q",
        "en_over_ar_cost_dec4",
        "raw_arabic_strictly_cheaper",
    }
)
_P1_GAUGE_KEYS = frozenset(
    {
        "tokenpage_max_bits_q",
        "tokenpage_glyph_latent_low_bits_q",
        "tokenpage_glyph_latent_high_bits_q",
        "tokenpage_glyph_bits_per_tok_q",
        "tokenpage_readout_cold_q",
        "tokenpage_readout_legend_q",
        "tokenpage_pos01_collapse_q",
        "tokenpage_gauge_gap_q",
        "tokenpage_gauge_gap_dec4",
        "tokenpage_unfloored_kl_gain_q",
        "tokenpage_floored_kl_artifact_q",
        "tokenpage_sign_reversal_verified",
        "abios51_cold_low_q",
        "abios51_cold_high_q",
        "abios51_spec_in_context_q",
        "abios51_readout_jump_q",
        "abios51_readout_jump_dec4",
        "abios51_compile_before_q",
        "abios51_compile_after_q",
    }
)
_P1_CODEC_KEYS = frozenset(
    {
        "source_commit",
        "source_sha256",
        "defect1_whitespace_encoded",
        "defect1_decoded_len",
        "defect1_silent_loss_confirmed",
        "defect2_scalar_encoded",
        "defect2_decoded_len",
        "defect2_corruption_confirmed",
        "defect3_bracket_encoded",
        "defect3_whitespace_tokens",
        "defect3_arity_crash_confirmed",
        "fixed_codec_cases_total",
        "fixed_codec_single_token_passed",
        "fixed_codec_roundtrip_passed",
        "fixed_codec_all_bijective",
    }
)


def _audit_pillar_1_semantics(p1: dict[str, Any]) -> None:
    _req_exact_dict(p1, _P1_KEYS, "P1_KEYS")
    require_ok(p1["all_verified"] is True, "P1_NOT_VERIFIED")

    # 1a. ABIOS SYM-2P 4-form audit
    ab = _req_exact_dict(p1["abios_sym2p_4form_audit"], _P1_ABIOS_KEYS, "P1_ABIOS_KEYS")
    require_ok(_req_int(ab["packet_count"], "P1_ABIOS_PKT") == 12, "P1_ABIOS_PKT")
    _check_sha_eq(ab["source_sha256"], WAVE_FIXTURE_PINS[1]["sha256"], "P1_ABIOS_SHA")
    forms = _req_exact_dict(ab["forms"], frozenset(ABIOS_RFVM_FORMS.keys()), "P1_FORMS_KEYS")
    for fname, exp in ABIOS_RFVM_FORMS.items():
        fd = _req_exact_dict(forms[fname], _FORM_ENTRY_KEYS, "P1_FORM_ENTRY")
        _check_all(
            [
                (_req_int(fd["utf8_bytes"], "P1_FORM_B") == exp["utf8_bytes"], "P1_FORM_B"),
                (_req_int(fd["qwen25_tokens"], "P1_FORM_Q") == exp["qwen25_tokens"], "P1_FORM_Q"),
                (_req_int(fd["smollm2_tokens"], "P1_FORM_S") == exp["smollm2_tokens"], "P1_FORM_S"),
            ]
        )
    q_md, q_sym, q_af, q_ap, q_su = (
        forms["verbose_markdown"]["qwen25_tokens"],
        forms["sym2p_jsonl"]["qwen25_tokens"],
        forms["abios3_full_with_setup"]["qwen25_tokens"],
        forms["abios3_payload_only"]["qwen25_tokens"],
        forms["abios3_setup_header"]["qwen25_tokens"],
    )
    s_md, s_sym, s_af, s_ap, s_su = (
        forms["verbose_markdown"]["smollm2_tokens"],
        forms["sym2p_jsonl"]["smollm2_tokens"],
        forms["abios3_full_with_setup"]["smollm2_tokens"],
        forms["abios3_payload_only"]["smollm2_tokens"],
        forms["abios3_setup_header"]["smollm2_tokens"],
    )
    _check_q_dec(ab, "qwen25_sym2p_vs_markdown_saving_q", "qwen25_sym2p_vs_markdown_saving_dec4", Fraction(q_md - q_sym, q_md), 4, "P1_AB_QMD")
    _check_q_dec(ab, "qwen25_abios3_full_vs_sym2p_saving_q", "qwen25_abios3_full_vs_sym2p_saving_dec4", Fraction(q_sym - q_af, q_sym), 4, "P1_AB_QAF")
    _check_q_dec(ab, "qwen25_abios3_full_vs_markdown_saving_q", "qwen25_abios3_full_vs_markdown_saving_dec4", Fraction(q_md - q_af, q_md), 4, "P1_AB_QAFM")
    _check_q_dec(ab, "smollm2_abios3_full_vs_sym2p_saving_q", "smollm2_abios3_full_vs_sym2p_saving_dec4", Fraction(s_sym - s_af, s_sym), 4, "P1_AB_SAF")
    _check_q_dec(ab, "smollm2_abios3_full_vs_markdown_saving_q", "smollm2_abios3_full_vs_markdown_saving_dec4", Fraction(s_md - s_af, s_md), 4, "P1_AB_SAFM")
    _check_all(
        [
            (_req_int(ab["qwen25_abios3_vs_sym2p_breakeven_packets"], "P1_AB_QBE") == (q_su * 12) // (q_sym - q_ap) + 1, "P1_AB_QBE"),
            (_req_int(ab["smollm2_abios3_vs_sym2p_breakeven_packets"], "P1_AB_SBE") == (s_su * 12) // (s_sym - s_ap) + 1, "P1_AB_SBE"),
        ]
    )

    # 1b. Aletheia 8-glyph & 5-cert audit
    al = _req_exact_dict(p1["aletheia_8glyph_and_5cert_audit"], _P1_ALETHEIA_KEYS, "P1_AL_KEYS")
    _check_all(
        [
            (_req_int(al["glyph_count"], "P1_AL_GC") == 8, "P1_AL_GC"),
            (_req_int(al["glyph_qwen25_total_tokens"], "P1_AL_GQ") == 17, "P1_AL_GQ"),
            (_req_int(al["glyph_smollm2_total_tokens"], "P1_AL_GS") == 24, "P1_AL_GS"),
            (parse_canonical_q(al["glyph_qwen25_mean_tok_per_glyph_q"], "P1_AL_GQM") == Fraction(17, 8), "P1_AL_GQM"),
            (parse_canonical_q(al["glyph_smollm2_mean_tok_per_glyph_q"], "P1_AL_GSM") == Fraction(3, 1), "P1_AL_GSM"),
            (_req_int(al["expr_glyph_qwen25_tokens"], "P1_AL_EGQ") == 32, "P1_AL_EGQ"),
            (_req_int(al["expr_ascii_qwen25_tokens"], "P1_AL_EAQ") == 37, "P1_AL_EAQ"),
            (_req_int(al["expr_reserved_8tok_qwen25_tokens"], "P1_AL_ERQ") == 17, "P1_AL_ERQ"),
            (_req_int(al["expr_glyph_smollm2_tokens"], "P1_AL_EGS") == 33, "P1_AL_EGS"),
            (_req_int(al["expr_ascii_smollm2_tokens"], "P1_AL_EAS") == 47, "P1_AL_EAS"),
            (_req_int(al["expr_reserved_8tok_smollm2_tokens"], "P1_AL_ERS") == 17, "P1_AL_ERS"),
            (_req_int(al["frozen_cert_count"], "P1_AL_CC") == 5, "P1_AL_CC"),
            (_req_int(al["frozen_cert_total_bytes"], "P1_AL_CB") == 114394, "P1_AL_CB"),
            (_req_int(al["frozen_cert_qwen25_tokens"], "P1_AL_CQ") == 48234, "P1_AL_CQ"),
            (_req_int(al["frozen_cert_smollm2_tokens"], "P1_AL_CS") == 55485, "P1_AL_CS"),
        ]
    )
    _check_q_dec(al, "qwen25_reserved_vs_glyph_saving_q", "qwen25_reserved_vs_glyph_saving_dec4", Fraction(15, 32), 4, "P1_AL_QRS")
    _check_q_dec(al, "smollm2_reserved_vs_glyph_saving_q", "smollm2_reserved_vs_glyph_saving_dec4", Fraction(16, 33), 4, "P1_AL_SRS")
    _check_q_dec(al, "frozen_cert_qwen25_bytes_per_tok_q", "frozen_cert_qwen25_bytes_per_tok_dec4", Fraction(114394, 48234), 4, "P1_AL_QBPT")
    _check_q_dec(al, "frozen_cert_smollm2_bytes_per_tok_q", "frozen_cert_smollm2_bytes_per_tok_dec4", Fraction(114394, 55485), 4, "P1_AL_SBPT")

    # 1c. S92 Arabic treatises + bilingual compounding ladder
    ar = _req_exact_dict(p1["s92_arabic_vocab_tax_and_compounding"], _P1_ARABIC_KEYS, "P1_AR_KEYS")
    tr, bi = S92_TREATISE_TOTALS, S92_BILINGUAL_TOTALS
    _check_all(
        [
            (_req_int(ar["treatise_count"], "P1_AR_TC") == tr["treatise_count"], "P1_AR_TC"),
            (_req_int(ar["treatises_utf8_bytes"], "P1_AR_TB") == tr["total_text_utf8_bytes"], "P1_AR_TB"),
            (_req_int(ar["treatises_whitespace_words"], "P1_AR_TW") == tr["total_whitespace_words"], "P1_AR_TW"),
            (_req_int(ar["treatises_qwen25_tokens"], "P1_AR_TQ") == tr["total_qwen25_tokens"], "P1_AR_TQ"),
            (_req_int(ar["treatises_smollm2_tokens"], "P1_AR_TS") == tr["total_smollm2_tokens"], "P1_AR_TS"),
            (_req_int(ar["treatises_extra_smollm2_tokens"], "P1_AR_TE") == tr["total_smollm2_tokens"] - tr["total_qwen25_tokens"], "P1_AR_TE"),
            (_req_int(ar["bilingual_catalog_count"], "P1_AR_BC") == bi["catalog_count"], "P1_AR_BC"),
            (_req_int(ar["bilingual_pair_count"], "P1_AR_BP") == bi["total_pairs"], "P1_AR_BP"),
            (_req_int(ar["bilingual_qwen25_ar_tokens"], "P1_AR_BQA") == bi["total_qwen25_ar_tokens"], "P1_AR_BQA"),
            (_req_int(ar["bilingual_qwen25_en_tokens"], "P1_AR_BQE") == bi["total_qwen25_en_tokens"], "P1_AR_BQE"),
            (_req_int(ar["bilingual_smollm2_ar_tokens"], "P1_AR_BSA") == bi["total_smollm2_ar_tokens"], "P1_AR_BSA"),
            (_req_int(ar["bilingual_smollm2_en_tokens"], "P1_AR_BSE") == bi["total_smollm2_en_tokens"], "P1_AR_BSE"),
        ]
    )
    _check_q_dec(ar, "treatises_smol_over_qwen_q", "treatises_smol_over_qwen_dec4", Fraction(tr["total_smollm2_tokens"], tr["total_qwen25_tokens"]), 4, "P1_AR_TR")
    _check_q_dec(ar, "treatises_min_ratio_q", "treatises_min_ratio_dec4", Fraction(tr["min_ratio_treatise_smollm2_tokens"], tr["min_ratio_treatise_qwen25_tokens"]), 4, "P1_AR_MIN")
    _check_q_dec(ar, "treatises_max_ratio_q", "treatises_max_ratio_dec4", Fraction(tr["max_ratio_treatise_smollm2_tokens"], tr["max_ratio_treatise_qwen25_tokens"]), 4, "P1_AR_MAX")
    q_tax = Fraction(bi["total_qwen25_ar_tokens"], bi["total_qwen25_en_tokens"])
    s_tax = Fraction(bi["total_smollm2_ar_tokens"], bi["total_smollm2_en_tokens"])
    _check_q_dec(ar, "bilingual_qwen25_ar_over_en_q", "bilingual_qwen25_ar_over_en_dec4", q_tax, 4, "P1_AR_QTAX")
    _check_q_dec(ar, "bilingual_smollm2_ar_over_en_q", "bilingual_smollm2_ar_over_en_dec4", s_tax, 4, "P1_AR_STAX")
    _check_q_dec(ar, "cross_tokenizer_tax_amplification_q", "cross_tokenizer_tax_amplification_dec4", s_tax / q_tax, 4, "P1_AR_AMP")

    comp_specs = (
        ("qwen25_overall_k1", q_tax, Fraction(319, 664), 1),
        ("smollm2_overall_k1", s_tax, Fraction(319, 664), 1),
        ("qwen25_overall_k2", q_tax, Fraction(319, 664), 2),
        ("smollm2_overall_k2", s_tax, Fraction(319, 664), 2),
        ("qwen25_cross_disc_k1", q_tax, Fraction(7, 85), 1),
        ("smollm2_cross_disc_k1", s_tax, Fraction(7, 85), 1),
        ("qwen25_cross_disc_k2", q_tax, Fraction(7, 85), 2),
        ("smollm2_cross_disc_k2", s_tax, Fraction(7, 85), 2),
    )
    ladder = _req_list(ar["compounding_ladder"], 8, "P1_AR_LADDER")
    for row_obj, (lbl, tax_q, ret_q, k_ord) in zip(ladder, comp_specs):
        row = _req_exact_dict(row_obj, _COMP_ROW_KEYS, "P1_AR_ROW_KEYS")
        m_e = (k_ord * (k_ord + 1)) // 2
        s_ret = ret_q ** m_e
        en_ar = Fraction(1, 1) / (tax_q * s_ret)
        _check_all(
            [
                (_req_str(row["label"], "P1_AR_RL") == lbl, "P1_AR_RL"),
                (_req_int(row["simplex_order_k"], "P1_AR_RK") == k_ord, "P1_AR_RK"),
                (_req_int(row["edges_m"], "P1_AR_RM") == m_e, "P1_AR_RM"),
                (row["raw_arabic_strictly_cheaper"] is (en_ar > 1), "P1_AR_RCHEAP"),
            ]
        )
        _check_q_dec(row, "bpe_tax_q", "bpe_tax_dec4", tax_q, 4, "P1_AR_RTAX")
        _check_q_dec(row, "simplex_retention_q", "simplex_retention_dec6", s_ret, 6, "P1_AR_RRET")
        _check_q_dec(row, "en_over_ar_cost_q", "en_over_ar_cost_dec4", en_ar, 4, "P1_AR_RCOST")

    # 1d. Representation-vs-readout gauge gap
    gg = _req_exact_dict(p1["representation_vs_readout_gauge_gap"], _P1_GAUGE_KEYS, "P1_GG_KEYS")
    exp_gap = Fraction(1132, 1149) - Fraction(558, 1000)
    _check_all(
        [
            (parse_canonical_q(gg["tokenpage_max_bits_q"], "P1_GG_MAX") == Fraction(1149, 100), "P1_GG_MAX"),
            (parse_canonical_q(gg["tokenpage_glyph_latent_low_bits_q"], "P1_GG_LL") == Fraction(1132, 100), "P1_GG_LL"),
            (parse_canonical_q(gg["tokenpage_glyph_latent_high_bits_q"], "P1_GG_LH") == Fraction(1140, 100), "P1_GG_LH"),
            (parse_canonical_q(gg["tokenpage_glyph_bits_per_tok_q"], "P1_GG_BPT") == Fraction(96, 100), "P1_GG_BPT"),
            (parse_canonical_q(gg["tokenpage_readout_cold_q"], "P1_GG_RC") == Fraction(558, 1000), "P1_GG_RC"),
            (parse_canonical_q(gg["tokenpage_readout_legend_q"], "P1_GG_RL") == Fraction(542, 1000), "P1_GG_RL"),
            (parse_canonical_q(gg["tokenpage_pos01_collapse_q"], "P1_GG_P01") == Fraction(19, 24), "P1_GG_P01"),
            (parse_canonical_q(gg["tokenpage_unfloored_kl_gain_q"], "P1_GG_KLU") == Fraction(1767, 1000), "P1_GG_KLU"),
            (parse_canonical_q(gg["tokenpage_floored_kl_artifact_q"], "P1_GG_KLF") == Fraction(-197, 100), "P1_GG_KLF"),
            (gg["tokenpage_sign_reversal_verified"] is True, "P1_GG_SR"),
            (parse_canonical_q(gg["abios51_cold_low_q"], "P1_GG_CL") == Fraction(4, 23), "P1_GG_CL"),
            (parse_canonical_q(gg["abios51_cold_high_q"], "P1_GG_CH") == Fraction(6, 23), "P1_GG_CH"),
            (parse_canonical_q(gg["abios51_spec_in_context_q"], "P1_GG_SP") == Fraction(18, 23), "P1_GG_SP"),
            (parse_canonical_q(gg["abios51_compile_before_q"], "P1_GG_CB") == Fraction(0, 1), "P1_GG_CB"),
            (parse_canonical_q(gg["abios51_compile_after_q"], "P1_GG_CA") == Fraction(1, 1), "P1_GG_CA"),
        ]
    )
    _check_q_dec(gg, "tokenpage_gauge_gap_q", "tokenpage_gauge_gap_dec4", exp_gap, 4, "P1_GG_GAP")
    _check_q_dec(gg, "abios51_readout_jump_q", "abios51_readout_jump_dec4", Fraction(12, 23), 4, "P1_GG_JMP")

    # 1e. abios#39 wire_lists codec audit
    cd = _req_exact_dict(p1["abios_pr39_wire_lists_codec_audit"], _P1_CODEC_KEYS, "P1_CD_KEYS")
    _check_sha_eq(cd["source_sha256"], WAVE_FIXTURE_PINS[2]["sha256"], "P1_CD_SHA")
    _check_all(
        [
            (_req_str(cd["source_commit"], "P1_CD_CMT") == "3e251f0b92a8", "P1_CD_CMT"),
            (_req_str(cd["defect1_whitespace_encoded"], "P1_CD_D1E") == "[ ]", "P1_CD_D1E"),
            (_req_int(cd["defect1_decoded_len"], "P1_CD_D1L") == 0, "P1_CD_D1L"),
            (cd["defect1_silent_loss_confirmed"] is True, "P1_CD_D1OK"),
            (_req_str(cd["defect2_scalar_encoded"], "P1_CD_D2E") == "[1,2]", "P1_CD_D2E"),
            (_req_int(cd["defect2_decoded_len"], "P1_CD_D2L") == 1, "P1_CD_D2L"),
            (cd["defect2_corruption_confirmed"] is True, "P1_CD_D2OK"),
            (_req_str(cd["defect3_bracket_encoded"], "P1_CD_D3E") == '["see [1] now"]', "P1_CD_D3E"),
            (_req_int(cd["defect3_whitespace_tokens"], "P1_CD_D3T") == 3, "P1_CD_D3T"),
            (cd["defect3_arity_crash_confirmed"] is True, "P1_CD_D3OK"),
            (_req_int(cd["fixed_codec_cases_total"], "P1_CD_FC") == 6, "P1_CD_FC"),
            (_req_int(cd["fixed_codec_single_token_passed"], "P1_CD_FS") == 6, "P1_CD_FS"),
            (_req_int(cd["fixed_codec_roundtrip_passed"], "P1_CD_FR") == 6, "P1_CD_FR"),
            (cd["fixed_codec_all_bijective"] is True, "P1_CD_FB"),
        ]
    )


_P2_KEYS = frozenset(
    {
        "k_grid",
        "protocol_token_surgery_sweep",
        "s31_dpi_qwen25_k128_safety_bound",
        "s31_dpi_smollm2_k128_safety_bound",
        "all_verified",
    }
)
_P2_SURG_KEYS = frozenset(
    {
        "model_name",
        "hidden_dim",
        "base_params",
        "added_k",
        "tied_added_params",
        "untied_added_params",
        "tied_overhead_ppm_q",
        "tied_overhead_ppm_dec2",
        "untied_overhead_ppm_q",
        "untied_overhead_ppm_dec2",
        "setup_tokens",
        "delta_tok_per_turn",
        "breakeven_turn_n_star",
        "net_tokens_saved_100_turns",
        "net_tokens_saved_1000_turns",
    }
)
_P2_DPI_KEYS = frozenset(
    {
        "vocab_v",
        "added_k",
        "total_rows",
        "mean_norm_sq",
        "matched_dpi_ratio_q",
        "spike_alpha",
        "spike_dpi_ratio_q",
        "spike_dpi_ratio_dec4",
        "spike_exceeds_unity",
        "s31_two_row_dpi_anchor_q",
        "householder_norm_before_q",
        "householder_norm_after_q",
        "householder_norm_delta_q",
        "householder_involution_exact",
    }
)


def _audit_dpi_block(blk: dict[str, Any], exp_v: int, code_prefix: str) -> None:
    d = _req_exact_dict(blk, _P2_DPI_KEYS, f"{code_prefix}_KEYS")
    tot = exp_v + 128
    spike_q = Fraction(16 * tot, tot + 15)
    _check_all(
        [
            (_req_int(d["vocab_v"], f"{code_prefix}_V") == exp_v, f"{code_prefix}_V"),
            (_req_int(d["added_k"], f"{code_prefix}_K") == 128, f"{code_prefix}_K"),
            (_req_int(d["total_rows"], f"{code_prefix}_TOT") == tot, f"{code_prefix}_TOT"),
            (_req_int(d["mean_norm_sq"], f"{code_prefix}_M") == 16, f"{code_prefix}_M"),
            (parse_canonical_q(d["matched_dpi_ratio_q"], f"{code_prefix}_MD") == Fraction(1, 1), f"{code_prefix}_MD"),
            (_req_int(d["spike_alpha"], f"{code_prefix}_SA") == 16, f"{code_prefix}_SA"),
            (d["spike_exceeds_unity"] is True, f"{code_prefix}_SU"),
            (parse_canonical_q(d["s31_two_row_dpi_anchor_q"], f"{code_prefix}_A2") == Fraction(exp_v, 2), f"{code_prefix}_A2"),
            (parse_canonical_q(d["householder_norm_before_q"], f"{code_prefix}_HNB") == Fraction(70, 1), f"{code_prefix}_HNB"),
            (parse_canonical_q(d["householder_norm_after_q"], f"{code_prefix}_HNA") == Fraction(70, 1), f"{code_prefix}_HNA"),
            (parse_canonical_q(d["householder_norm_delta_q"], f"{code_prefix}_HND") == Fraction(0, 1), f"{code_prefix}_HND"),
            (d["householder_involution_exact"] is True, f"{code_prefix}_HI"),
        ]
    )
    _check_q_dec(d, "spike_dpi_ratio_q", "spike_dpi_ratio_dec4", spike_q, 4, f"{code_prefix}_SD")


def _audit_pillar_2_semantics(p2: dict[str, Any]) -> None:
    _req_exact_dict(p2, _P2_KEYS, "P2_KEYS")
    require_ok(p2["all_verified"] is True, "P2_NOT_VERIFIED")
    require_ok(_req_list(p2["k_grid"], 4, "P2_KGRID") == [16, 32, 64, 128], "P2_KGRID")
    exp_specs = (
        ("Qwen2.5-0.5B", 896, 494032768, 16, 96, 15),
        ("Qwen2.5-0.5B", 896, 494032768, 32, 96, 28),
        ("Qwen2.5-1.5B", 1536, 1543714304, 64, 96, 44),
        ("Qwen2.5-3B", 2048, 3085938688, 128, 96, 68),
        ("SmolLM2-360M", 960, 361821120, 16, 104, 22),
        ("SmolLM2-360M", 960, 361821120, 32, 104, 38),
        ("SmolLM2-360M", 960, 361821120, 64, 104, 58),
        ("SmolLM2-360M", 960, 361821120, 128, 104, 96),
    )
    rows = _req_list(p2["protocol_token_surgery_sweep"], 8, "P2_SWEEP")
    for obj, (mname, hd, bp, k_add, setup, delta) in zip(rows, exp_specs):
        r = _req_exact_dict(obj, _P2_SURG_KEYS, "P2_ROW_KEYS")
        tied = k_add * hd
        untied = 2 * tied
        _check_all(
            [
                (_req_str(r["model_name"], "P2_RM") == mname, "P2_RM"),
                (_req_int(r["hidden_dim"], "P2_RHD") == hd, "P2_RHD"),
                (_req_int(r["base_params"], "P2_RBP") == bp, "P2_RBP"),
                (_req_int(r["added_k"], "P2_RK") == k_add, "P2_RK"),
                (_req_int(r["tied_added_params"], "P2_RT") == tied, "P2_RT"),
                (_req_int(r["untied_added_params"], "P2_RU") == untied, "P2_RU"),
                (_req_int(r["setup_tokens"], "P2_RS") == setup, "P2_RS"),
                (_req_int(r["delta_tok_per_turn"], "P2_RD") == delta, "P2_RD"),
                (_req_int(r["breakeven_turn_n_star"], "P2_RN") == setup // delta + 1, "P2_RN"),
                (_req_int(r["net_tokens_saved_100_turns"], "P2_R100") == 100 * delta - setup, "P2_R100"),
                (_req_int(r["net_tokens_saved_1000_turns"], "P2_R1000") == 1000 * delta - setup, "P2_R1000"),
            ]
        )
        _check_q_dec(r, "tied_overhead_ppm_q", "tied_overhead_ppm_dec2", Fraction(tied * 1_000_000, bp), 2, "P2_TPPM")
        _check_q_dec(r, "untied_overhead_ppm_q", "untied_overhead_ppm_dec2", Fraction(untied * 1_000_000, bp), 2, "P2_UPPM")
    _audit_dpi_block(p2["s31_dpi_qwen25_k128_safety_bound"], 151936, "P2_DQ")
    _audit_dpi_block(p2["s31_dpi_smollm2_k128_safety_bound"], 49152, "P2_DS")


_P3_KEYS = frozenset(
    {
        "node_count",
        "nodes",
        "handoff_count",
        "handoffs",
        "borromean_four_gate_ablations",
        "all_four_ablations_rejected",
        "all_verified",
    }
)
_NODE_KEYS = frozenset({"node_id", "role", "vram_or_unified_gb_q", "bandwidth_gbs_q"})
_H1_KEYS = frozenset(
    {
        "handoff_id",
        "target_node",
        "title",
        "pinned_config_sha256",
        "model_hidden_size",
        "model_vocab_size",
        "model_unpadded_vocab_size",
        "model_num_layers",
        "loop_core_passes",
        "moe_routed_experts",
        "moe_active_experts",
        "memory_required_gb_q",
        "memory_headroom_gb_q",
        "fits_m1max_64gib",
        "serial_200calls_sec_q",
        "window_w4_sec_q",
        "window_w8_sec_q",
        "window_w8_speedup_q",
        "loop_contractive_3pass_q",
        "loop_expansive_3pass_q",
        "pass_gate_min_acc_q",
        "pass_gate_max_format_breaks",
        "pass_gate_max_eval_wall_sec",
        "kill_gate_trigger",
        "manifest_sha256",
    }
)
_H2_KEYS = frozenset(
    {
        "handoff_id",
        "target_node",
        "title",
        "memory_required_gb_q",
        "memory_headroom_gb_q",
        "fits_m1max_64gib",
        "e8_rmsnorm_eta_q",
        "e8_l1_shrink_low_q",
        "e8_l1_shrink_high_q",
        "e8_l4_shrink_low_q",
        "e8_l4_shrink_high_q",
        "e8_l4_suppression_factor_q",
        "e11c_min_new_task_acc_q",
        "e11c_max_iid_drop_q",
        "part_c_min_retention_q",
        "part_c_max_rollback_logprob_diff_q",
        "kill_gate_trigger",
        "manifest_sha256",
    }
)
_H3_KEYS = frozenset(
    {
        "handoff_id",
        "target_node",
        "title",
        "bonsai_size_gb_q",
        "fp16_size_gb_q",
        "dual_load_total_gb_q",
        "dual_load_headroom_gb_q",
        "dual_load_fits_m1max_64gib",
        "rtx3080_fp16_spill_gb_q",
        "gemma12b_buggy_hhbg_kl_q",
        "gemma12b_hebg_ref_kl_q",
        "gemma12b_buggy_blowup_q",
        "gemma12b_buggy_blowup_dec4",
        "commutator_h2_d81_frob_sq",
        "pass_gate_bonsai_tool_retention_q",
        "pass_gate_fixed_hhbg_max_kl_q",
        "kill_gate_trigger",
        "manifest_sha256",
    }
)
_H4_KEYS = frozenset(
    {
        "handoff_id",
        "target_node",
        "title",
        "kv_bytes_per_tok",
        "lan_1gbps_c_wire_ns",
        "wan_10mbps_c_wire_ns",
        "local_cpu_c_prefill_ns",
        "rtt_plus_blake3_ns",
        "lan_breakeven_tokens_l_star",
        "lan_4096tok_speedup_q",
        "lan_4096tok_speedup_dec4",
        "wan_never_beats_prefill",
        "pass_gate_max_kv_logit_diff_q",
        "pass_gate_min_speedup_q",
        "kill_gate_trigger",
        "manifest_sha256",
    }
)
_BORR_KEYS = frozenset(
    {
        "all_four_gates_clean",
        "ablate_g1_unpinned_sha",
        "ablate_g2_memory_spill",
        "ablate_g3_float_predicate",
        "ablate_g4_missing_kill_gate",
    }
)
_GATE_KEYS = frozenset(
    {
        "gate1_sha_pinned",
        "gate2_memory_resident",
        "gate3_zero_float_predicate",
        "gate4_deterministic_kill_gate",
        "all_four_gates_pass",
    }
)


def _check_handoff_manifest_sha(h: dict[str, Any], code: str) -> None:
    got = _req_str(h["manifest_sha256"], code)
    require_ok(_is_sha256_hex(got), code)
    unsigned = {k: v for k, v in h.items() if k != "manifest_sha256"}
    calc = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    require_ok(hmac.compare_digest(got, calc), code)


def _audit_pillar_3_semantics(p3: dict[str, Any]) -> None:
    _req_exact_dict(p3, _P3_KEYS, "P3_KEYS")
    require_ok(p3["all_verified"] is True, "P3_NOT_VERIFIED")
    require_ok(p3["all_four_ablations_rejected"] is True, "P3_ABL_FLAG")
    require_ok(_req_int(p3["node_count"], "P3_NC") == 3, "P3_NC")
    nodes = _req_list(p3["nodes"], 3, "P3_NODES")
    exp_nodes = (
        ("node_rtx3080_linux", "8gib_gpu_sovereign_train_and_verify", Fraction(8, 1), Fraction(1783, 5)),
        ("node_m1max_macos", "64gib_unified_long_context_and_dual_load", Fraction(64, 1), Fraction(400, 1)),
        ("node_client_omarchy", "edge_cpu_exyber_nullmodem_kv_peer", Fraction(16, 1), Fraction(50, 1)),
    )
    for nobj, (nid, exp_role, mem_q, bw_q) in zip(nodes, exp_nodes):
        nd = _req_exact_dict(nobj, _NODE_KEYS, "P3_NODE_KEYS")
        _check_all(
            [
                (_req_str(nd["node_id"], "P3_NID") == nid, "P3_NID"),
                (_req_str(nd["role"], "P3_NROLE") == exp_role, "P3_NROLE"),
                (parse_canonical_q(nd["vram_or_unified_gb_q"], "P3_NMEM") == mem_q, "P3_NMEM"),
                (parse_canonical_q(nd["bandwidth_gbs_q"], "P3_NBW") == bw_q, "P3_NBW"),
            ]
        )

    require_ok(_req_int(p3["handoff_count"], "P3_HC") == 4, "P3_HC")
    hs = _req_list(p3["handoffs"], 4, "P3_HS")

    h1 = _req_exact_dict(hs[0], _H1_KEYS, "P3_H1_KEYS")
    _check_handoff_manifest_sha(h1, "P3_H1_SHA")
    _check_sha_eq(h1["pinned_config_sha256"], WAVE_FIXTURE_PINS[0]["sha256"], "P3_H1_CFG")
    _check_all(
        [
            (_req_str(h1["handoff_id"], "P3_H1_ID") == "M1-H1", "P3_H1_ID"),
            (_req_str(h1["target_node"], "P3_H1_ND") == "node_m1max_macos", "P3_H1_ND"),
            (_req_str(h1["title"], "P3_H1_TI") == "Inkling-2-Mini 20GB Beyond-LoRA & weft-loom#46/#47 Windowed Sampling Sweep", "P3_H1_TI"),
            (_req_int(h1["model_hidden_size"], "P3_H1_HD") == 2304, "P3_H1_HD"),
            (_req_int(h1["model_vocab_size"], "P3_H1_VS") == 201024, "P3_H1_VS"),
            (_req_int(h1["model_unpadded_vocab_size"], "P3_H1_UV") == 200058, "P3_H1_UV"),
            (_req_int(h1["model_num_layers"], "P3_H1_NL") == 24, "P3_H1_NL"),
            (_req_int(h1["loop_core_passes"], "P3_H1_LP") == 3, "P3_H1_LP"),
            (_req_int(h1["moe_routed_experts"], "P3_H1_RE") == 128, "P3_H1_RE"),
            (_req_int(h1["moe_active_experts"], "P3_H1_AE") == 8, "P3_H1_AE"),
            (parse_canonical_q(h1["memory_required_gb_q"], "P3_H1_MR") == Fraction(30, 1), "P3_H1_MR"),
            (parse_canonical_q(h1["memory_headroom_gb_q"], "P3_H1_MH") == Fraction(34, 1), "P3_H1_MH"),
            (h1["fits_m1max_64gib"] is True, "P3_H1_FIT"),
            (parse_canonical_q(h1["serial_200calls_sec_q"], "P3_H1_SS") == Fraction(514, 1), "P3_H1_SS"),
            (parse_canonical_q(h1["window_w4_sec_q"], "P3_H1_W4") == Fraction(257, 2), "P3_H1_W4"),
            (parse_canonical_q(h1["window_w8_sec_q"], "P3_H1_W8") == Fraction(257, 4), "P3_H1_W8"),
            (parse_canonical_q(h1["window_w8_speedup_q"], "P3_H1_SP") == Fraction(8, 1), "P3_H1_SP"),
            (parse_canonical_q(h1["loop_contractive_3pass_q"], "P3_H1_LC") == Fraction(27, 64), "P3_H1_LC"),
            (parse_canonical_q(h1["loop_expansive_3pass_q"], "P3_H1_LE") == Fraction(125, 64), "P3_H1_LE"),
            (parse_canonical_q(h1["pass_gate_min_acc_q"], "P3_H1_ACC") == Fraction(11, 20), "P3_H1_ACC"),
            (_req_int(h1["pass_gate_max_format_breaks"], "P3_H1_FB") == 0, "P3_H1_FB"),
            (_req_int(h1["pass_gate_max_eval_wall_sec"], "P3_H1_WT") == 120, "P3_H1_WT"),
            (_req_str(h1["kill_gate_trigger"], "P3_H1_KG") == "eval_acc < 11/20 OR format_breaks > 0 OR eval_wall_sec > 120", "P3_H1_KG"),
        ]
    )

    h2 = _req_exact_dict(hs[1], _H2_KEYS, "P3_H2_KEYS")
    _check_handoff_manifest_sha(h2, "P3_H2_SHA")
    _check_all(
        [
            (_req_str(h2["handoff_id"], "P3_H2_ID") == "M1-H2", "P3_H2_ID"),
            (_req_str(h2["target_node"], "P3_H2_ND") == "node_m1max_macos", "P3_H2_ND"),
            (_req_str(h2["title"], "P3_H2_TI") == "siliconcordat/weft E8 Part C Qwen3.5-4B Live Verification & weft-loom E11c DAWE", "P3_H2_TI"),
            (parse_canonical_q(h2["memory_required_gb_q"], "P3_H2_MR") == Fraction(18, 1), "P3_H2_MR"),
            (parse_canonical_q(h2["memory_headroom_gb_q"], "P3_H2_MH") == Fraction(46, 1), "P3_H2_MH"),
            (h2["fits_m1max_64gib"] is True, "P3_H2_FIT"),
            (parse_canonical_q(h2["e8_rmsnorm_eta_q"], "P3_H2_ETA") == Fraction(1, 10), "P3_H2_ETA"),
            (parse_canonical_q(h2["e8_l1_shrink_low_q"], "P3_H2_L1L") == Fraction(1, 22), "P3_H2_L1L"),
            (parse_canonical_q(h2["e8_l1_shrink_high_q"], "P3_H2_L1H") == Fraction(1, 20), "P3_H2_L1H"),
            (parse_canonical_q(h2["e8_l4_shrink_low_q"], "P3_H2_L4L") == Fraction(1, 82), "P3_H2_L4L"),
            (parse_canonical_q(h2["e8_l4_shrink_high_q"], "P3_H2_L4H") == Fraction(1, 80), "P3_H2_L4H"),
            (parse_canonical_q(h2["e8_l4_suppression_factor_q"], "P3_H2_SF") == Fraction(4, 1), "P3_H2_SF"),
            (parse_canonical_q(h2["e11c_min_new_task_acc_q"], "P3_H2_NT") == Fraction(4, 5), "P3_H2_NT"),
            (parse_canonical_q(h2["e11c_max_iid_drop_q"], "P3_H2_IDD") == Fraction(1, 10), "P3_H2_IDD"),
            (parse_canonical_q(h2["part_c_min_retention_q"], "P3_H2_RET") == Fraction(9, 10), "P3_H2_RET"),
            (parse_canonical_q(h2["part_c_max_rollback_logprob_diff_q"], "P3_H2_RB") == Fraction(0, 1), "P3_H2_RB"),
            (_req_str(h2["kill_gate_trigger"], "P3_H2_KG") == "missing_base_gguf_sha256 OR new_task_acc < 4/5 OR iid_drop > 1/10 OR retention < 9/10", "P3_H2_KG"),
        ]
    )

    h3 = _req_exact_dict(hs[2], _H3_KEYS, "P3_H3_KEYS")
    _check_handoff_manifest_sha(h3, "P3_H3_SHA")
    exp_blow = Fraction(94440, 31715)
    _check_all(
        [
            (_req_str(h3["handoff_id"], "P3_H3_ID") == "M1-H3", "P3_H3_ID"),
            (_req_str(h3["target_node"], "P3_H3_ND") == "node_m1max_macos", "P3_H3_ND"),
            (_req_str(h3["title"], "P3_H3_TI") == "Bonsai 2.5 27B vs FP16 53.8GB Dual-Load Parity & Fixed [H_8,D] siliquant#97 Gemma-3-12B", "P3_H3_TI"),
            (parse_canonical_q(h3["bonsai_size_gb_q"], "P3_H3_BN") == Fraction(593, 100), "P3_H3_BN"),
            (parse_canonical_q(h3["fp16_size_gb_q"], "P3_H3_FP") == Fraction(269, 5), "P3_H3_FP"),
            (parse_canonical_q(h3["dual_load_total_gb_q"], "P3_H3_DT") == Fraction(6273, 100), "P3_H3_DT"),
            (parse_canonical_q(h3["dual_load_headroom_gb_q"], "P3_H3_DH") == Fraction(127, 100), "P3_H3_DH"),
            (h3["dual_load_fits_m1max_64gib"] is True, "P3_H3_FIT"),
            (parse_canonical_q(h3["rtx3080_fp16_spill_gb_q"], "P3_H3_SP") == Fraction(473, 10), "P3_H3_SP"),
            (parse_canonical_q(h3["gemma12b_buggy_hhbg_kl_q"], "P3_H3_BK") == Fraction(94440, 1000000), "P3_H3_BK"),
            (parse_canonical_q(h3["gemma12b_hebg_ref_kl_q"], "P3_H3_RK") == Fraction(31715, 1000000), "P3_H3_RK"),
            (_req_int(h3["commutator_h2_d81_frob_sq"], "P3_H3_CF") == 98, "P3_H3_CF"),
            (parse_canonical_q(h3["pass_gate_bonsai_tool_retention_q"], "P3_H3_TR") == Fraction(19, 20), "P3_H3_TR"),
            (parse_canonical_q(h3["pass_gate_fixed_hhbg_max_kl_q"], "P3_H3_MK") == Fraction(7, 200), "P3_H3_MK"),
            (_req_str(h3["kill_gate_trigger"], "P3_H3_KG") == "dual_load_oom OR fixed_hhbg_kl > 7/200 OR bonsai_tool_retention < 19/20", "P3_H3_KG"),
        ]
    )
    _check_q_dec(h3, "gemma12b_buggy_blowup_q", "gemma12b_buggy_blowup_dec4", exp_blow, 4, "P3_H3_BLOW")

    h4 = _req_exact_dict(hs[3], _H4_KEYS, "P3_H4_KEYS")
    _check_handoff_manifest_sha(h4, "P3_H4_SHA")
    exp_sp = Fraction(4096 * 2000000, 5000000 + 4096 * 229376)
    _check_all(
        [
            (_req_str(h4["handoff_id"], "P3_H4_ID") == "EDGE-H1", "P3_H4_ID"),
            (_req_str(h4["target_node"], "P3_H4_ND") == "node_client_omarchy", "P3_H4_ND"),
            (_req_str(h4["title"], "P3_H4_TI") == "exyber (iroh/BLAKE3) + nullmodem Cross-Host KV-Cache Transfer Benchmark", "P3_H4_TI"),
            (_req_int(h4["kv_bytes_per_tok"], "P3_H4_KV") == 28672, "P3_H4_KV"),
            (_req_int(h4["lan_1gbps_c_wire_ns"], "P3_H4_LAN") == 229376, "P3_H4_LAN"),
            (_req_int(h4["wan_10mbps_c_wire_ns"], "P3_H4_WAN") == 22937600, "P3_H4_WAN"),
            (_req_int(h4["local_cpu_c_prefill_ns"], "P3_H4_PF") == 2000000, "P3_H4_PF"),
            (_req_int(h4["rtt_plus_blake3_ns"], "P3_H4_RTT") == 5000000, "P3_H4_RTT"),
            (_req_int(h4["lan_breakeven_tokens_l_star"], "P3_H4_LS") == 5000000 // (2000000 - 229376) + 1, "P3_H4_LS"),
            (h4["wan_never_beats_prefill"] is True, "P3_H4_WNO"),
            (parse_canonical_q(h4["pass_gate_max_kv_logit_diff_q"], "P3_H4_LD") == Fraction(1, 10000), "P3_H4_LD"),
            (parse_canonical_q(h4["pass_gate_min_speedup_q"], "P3_H4_MS") == Fraction(2, 1), "P3_H4_MS"),
            (_req_str(h4["kill_gate_trigger"], "P3_H4_KG") == "blake3_mismatch OR unsigned_plaintext_kv OR logit_diff > 1/10000 OR speedup < 2", "P3_H4_KG"),
        ]
    )
    _check_q_dec(h4, "lan_4096tok_speedup_q", "lan_4096tok_speedup_dec4", exp_sp, 4, "P3_H4_SP4K")

    abls = _req_exact_dict(p3["borromean_four_gate_ablations"], _BORR_KEYS, "P3_ABL_KEYS")
    exp_abls = (
        ("all_four_gates_clean", True, True, True, True, True),
        ("ablate_g1_unpinned_sha", False, True, True, True, False),
        ("ablate_g2_memory_spill", True, False, True, True, False),
        ("ablate_g3_float_predicate", True, True, False, True, False),
        ("ablate_g4_missing_kill_gate", True, True, True, False, False),
    )
    for kname, g1, g2, g3, g4, allp in exp_abls:
        gd = _req_exact_dict(abls[kname], _GATE_KEYS, "P3_GATE_KEYS")
        _check_all(
            [
                (gd["gate1_sha_pinned"] is g1, "P3_G1"),
                (gd["gate2_memory_resident"] is g2, "P3_G2"),
                (gd["gate3_zero_float_predicate"] is g3, "P3_G3"),
                (gd["gate4_deterministic_kill_gate"] is g4, "P3_G4"),
                (gd["all_four_gates_pass"] is allp, "P3_GALL"),
            ]
        )


_P4_KEYS = frozenset(
    {
        "lean4_companion",
        "anchor_pin",
        "upstream_cert_count",
        "upstream_cert_pins",
        "tokenizer_pin_count",
        "tokenizer_pins",
        "wave_fixture_pin_count",
        "wave_fixture_pins",
        "novelty_honesty_law4",
        "zero_dataset_copies_in_expedition",
    }
)
_P4_LEAN_KEYS = frozenset({"toolchain", "file", "sha256", "theorem_count", "all_theorems_universally_quantified", "allowed_axioms", "theorems"})
_P4_ANCHOR_KEYS = frozenset({"file", "bytes", "file_sha256", "payload_sha256"})
_P4_UP_KEYS = frozenset({"track_id", "relative_ref", "bytes", "sha256", "qwen25_tokens", "smollm2_tokens"})
_P4_TOK_KEYS = frozenset({"id", "model_id", "rel_cache_path", "bytes", "sha256", "active_vocab_size", "padded_vocab_size"})
_P4_FIX_KEYS = frozenset({"id", "root_kind", "filename", "bytes", "sha256"})
_P4_NOV_KEYS = frozenset({"novelty_tier", "n0_prior_art_anchored", "n1_exact_synthesis_verified", "n2_claims"})


def _audit_pillar_4_semantics(p4: dict[str, Any]) -> None:
    _req_exact_dict(p4, _P4_KEYS, "P4_KEYS")
    require_ok(p4["zero_dataset_copies_in_expedition"] is True, "P4_ZERO_COPIES")

    lc = _req_exact_dict(p4["lean4_companion"], _P4_LEAN_KEYS, "P4_LEAN_KEYS")
    _check_sha_eq(lc["sha256"], EXPECTED_LEAN_SHA256, "P4_LSHA")
    _check_all(
        [
            (_req_str(lc["toolchain"], "P4_LTC") == LEAN_TOOLCHAIN, "P4_LTC"),
            (_req_str(lc["file"], "P4_LF") == LEAN_FILE_NAME, "P4_LF"),
            (_req_int(lc["theorem_count"], "P4_LCNT") == len(EXPECTED_LEAN_THEOREMS), "P4_LCNT"),
            (lc["all_theorems_universally_quantified"] is True, "P4_LUNIV"),
            (_req_list(lc["allowed_axioms"], 1, "P4_LAXS") == ["propext"], "P4_LAXS"),
            (_req_list(lc["theorems"], len(EXPECTED_LEAN_THEOREMS), "P4_LTHMS") == list(EXPECTED_LEAN_THEOREMS), "P4_LTHMS"),
        ]
    )

    ap = _req_exact_dict(p4["anchor_pin"], _P4_ANCHOR_KEYS, "P4_AP_KEYS")
    _check_sha_eq(ap["file_sha256"], ANCHOR_PIN["file_sha256"], "P4_AP_FS")
    _check_sha_eq(ap["payload_sha256"], ANCHOR_PIN["payload_sha256"], "P4_AP_PS")
    _check_all(
        [
            (_req_str(ap["file"], "P4_AP_F") == ANCHOR_PIN["file"], "P4_AP_F"),
            (_req_int(ap["bytes"], "P4_AP_B") == ANCHOR_PIN["bytes"], "P4_AP_B"),
        ]
    )

    nov = _req_exact_dict(p4["novelty_honesty_law4"], _P4_NOV_KEYS, "P4_NOV_KEYS")
    _check_all(
        [
            (_req_str(nov["novelty_tier"], "P4_NT") == NOVELTY_TIER, "P4_NT"),
            (nov["n0_prior_art_anchored"] is True, "P4_N0"),
            (nov["n1_exact_synthesis_verified"] is True, "P4_N1"),
            (_req_int(nov["n2_claims"], "P4_N2") == 0, "P4_N2"),
        ]
    )

    require_ok(_req_int(p4["upstream_cert_count"], "P4_UC") == len(UPSTREAM_CERT_PINS), "P4_UC")
    for obj, exp in zip(_req_list(p4["upstream_cert_pins"], len(UPSTREAM_CERT_PINS), "P4_UP"), UPSTREAM_CERT_PINS):
        d = _req_exact_dict(obj, _P4_UP_KEYS, "P4_UP_KEYS")
        _check_sha_eq(d["sha256"], exp["sha256"], "P4_UP_SHA")
        _check_all(
            [
                (_req_str(d["track_id"], "P4_UP_ID") == exp["track_id"], "P4_UP_ID"),
                (_req_str(d["relative_ref"], "P4_UP_REF") == exp["relative_ref"], "P4_UP_REF"),
                (_req_int(d["bytes"], "P4_UP_B") == exp["bytes"], "P4_UP_B"),
                (_req_int(d["qwen25_tokens"], "P4_UP_QT") == exp["qwen25_tokens"], "P4_UP_QT"),
                (_req_int(d["smollm2_tokens"], "P4_UP_ST") == exp["smollm2_tokens"], "P4_UP_ST"),
            ]
        )

    require_ok(_req_int(p4["tokenizer_pin_count"], "P4_TC") == len(TOKENIZER_PINS), "P4_TC")
    for obj, exp in zip(_req_list(p4["tokenizer_pins"], len(TOKENIZER_PINS), "P4_TOK"), TOKENIZER_PINS):
        d = _req_exact_dict(obj, _P4_TOK_KEYS, "P4_TOK_KEYS")
        _check_sha_eq(d["sha256"], exp["sha256"], "P4_TOK_SHA")
        _check_all(
            [
                (_req_str(d["id"], "P4_TOK_ID") == exp["id"], "P4_TOK_ID"),
                (_req_str(d["model_id"], "P4_TOK_MID") == exp["model_id"], "P4_TOK_MID"),
                (_req_str(d["rel_cache_path"], "P4_TOK_RP") == exp["rel_cache_path"], "P4_TOK_RP"),
                (_req_int(d["bytes"], "P4_TOK_B") == exp["bytes"], "P4_TOK_B"),
                (_req_int(d["active_vocab_size"], "P4_TOK_AV") == exp["active_vocab_size"], "P4_TOK_AV"),
                (_req_int(d["padded_vocab_size"], "P4_TOK_PV") == exp["padded_vocab_size"], "P4_TOK_PV"),
            ]
        )

    require_ok(_req_int(p4["wave_fixture_pin_count"], "P4_FC") == len(WAVE_FIXTURE_PINS), "P4_FC")
    for obj, exp in zip(_req_list(p4["wave_fixture_pins"], len(WAVE_FIXTURE_PINS), "P4_FIX"), WAVE_FIXTURE_PINS):
        d = _req_exact_dict(obj, _P4_FIX_KEYS, "P4_FIX_KEYS")
        _check_sha_eq(d["sha256"], exp["sha256"], "P4_FIX_SHA")
        _check_all(
            [
                (_req_str(d["id"], "P4_FIX_ID") == exp["id"], "P4_FIX_ID"),
                (_req_str(d["root_kind"], "P4_FIX_RK") == exp["root_kind"], "P4_FIX_RK"),
                (_req_str(d["filename"], "P4_FIX_FN") == exp["filename"], "P4_FIX_FN"),
                (_req_int(d["bytes"], "P4_FIX_B") == exp["bytes"], "P4_FIX_B"),
            ]
        )


def audit_payload_semantics(payload: Any) -> dict[str, Any]:
    _check_json_tree(payload)
    p = _req_exact_dict(payload, REQUIRED_PAYLOAD_KEYS, "PAYLOAD_KEYS_MISMATCH")
    stack: list[Any] = [p]
    while stack:
        cur = stack.pop()
        if type(cur) is dict:
            for k, v in cur.items():
                if type(v) is bool:
                    require_ok(k in _PAYLOAD_BOOL_KEYS, f"UNEXPECTED_BOOL_FIELD:{k}")
                elif type(v) in (dict, list):
                    stack.append(v)
        else:
            for item in cur:
                require_ok(type(item) is not bool, "UNEXPECTED_BOOL_ITEM")
                if type(item) in (dict, list):
                    stack.append(item)
    require_ok(p["track_id"] == TRACK_ID, "PAYLOAD_TRACK_MISMATCH")
    require_ok(p["oracle_class"] == ORACLE_CLASS, "ORACLE_CLASS_MISMATCH")
    require_ok(p["novelty_tier"] == NOVELTY_TIER, "NOVELTY_TIER_MISMATCH")
    require_ok(p["all_pillars_verified"] is True, "PILLARS_NOT_VERIFIED")
    _audit_pillar_1_semantics(_req_dict(p["pillar_1_tokenizer_protocol_and_arabic_density"], "P1_NOT_DICT"))
    _audit_pillar_2_semantics(_req_dict(p["pillar_2_vocab_surgery_and_s31_dpi_bounds"], "P2_NOT_DICT"))
    _audit_pillar_3_semantics(_req_dict(p["pillar_3_three_node_m1max_and_edge_handoff_pack"], "P3_NOT_DICT"))
    _audit_pillar_4_semantics(_req_dict(p["pillar_4_provenance_and_lean4"], "P4_NOT_DICT"))
    return p


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    return audit_payload_semantics(payload)


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    require_ok(type(full_replay) is bool, "INVALID_FULL_REPLAY_FLAG")
    _check_json_tree(cert)
    c = _req_exact_dict(cert, REQUIRED_CERT_KEYS, "CERT_KEYS_MISMATCH")
    require_ok(c["schema_version"] == SCHEMA_VERSION, "SCHEMA_VERSION_MISMATCH")
    require_ok(c["track_id"] == TRACK_ID, "TRACK_ID_MISMATCH")
    require_ok(_is_sha256_hex(c["payload_sha256"]), "INVALID_PAYLOAD_SHA256")
    require_ok(_is_sha256_hex(c["certificate_sha256"]), "INVALID_CERT_SHA256")
    payload = _req_dict(c["payload"], "PAYLOAD_NOT_DICT")

    calc_p = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    require_ok(hmac.compare_digest(c["payload_sha256"], calc_p), "PAYLOAD_SHA256_TAMPERED")
    body = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": c["payload_sha256"],
        "payload": payload,
    }
    calc_c = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    require_ok(hmac.compare_digest(c["certificate_sha256"], calc_c), "CERTIFICATE_SHA256_TAMPERED")

    audit_payload_semantics(payload)

    if full_replay:
        expected = build_certificate_envelope()
        require_ok(exact_typed_equal(payload, expected["payload"]), "ORACLE_PAYLOAD_DRIFT")
        require_ok(hmac.compare_digest(c["certificate_sha256"], expected["certificate_sha256"]), "ORACLE_CERT_DRIFT")
    return {
        "status": "PASS",
        "track_id": TRACK_ID,
        "full_replay": full_replay,
        "secondary_audit_passed": True,
        "payload_sha256": c["payload_sha256"],
        "certificate_sha256": c["certificate_sha256"],
    }


def check_certificate_file(path: Path, *, full_replay: bool = True) -> dict[str, Any]:
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    parsed = parse_strict_json_bytes(raw)
    return verify_certificate_dict(parsed, full_replay=full_replay)


# ---------------------------------------------------------------------------
# Read-Only On-Disk Pin Verification (Anchor + 5 Certs + 2 Tokenizers + 5 Fixtures)
# ---------------------------------------------------------------------------

def verify_pins_on_disk(
    *,
    anchor_file: Path | None = None,
    expedition_root: Path | None = None,
    hf_cache_root: Path | None = None,
    wave7_root: Path | None = None,
    abios_root: Path | None = None,
) -> dict[str, Any]:
    require_ok(
        any(p is not None for p in (anchor_file, expedition_root, hf_cache_root, wave7_root, abios_root)),
        "NO_PIN_ROOT_SPECIFIED",
    )
    res: dict[str, Any] = {"status": "PINS_VERIFIED"}
    if anchor_file is not None:
        raw = read_regular_file_bytes(anchor_file, max_bytes=MAX_JSON_BYTES)
        require_ok(len(raw) == ANCHOR_PIN["bytes"], "ANCHOR_BYTES_MISMATCH")
        require_ok(hmac.compare_digest(hashlib.sha256(raw).hexdigest(), ANCHOR_PIN["file_sha256"]), "ANCHOR_FILE_SHA_MISMATCH")
        parsed = parse_strict_json_bytes(raw, trailing_lf=False)
        require_ok(hmac.compare_digest(parsed["anchor_payload_sha256"], ANCHOR_PIN["payload_sha256"]), "ANCHOR_PAYLOAD_SHA_MISMATCH")
        ap = parsed["payload"]
        require_ok(exact_typed_equal(ap["corpus_a_abios_sym2p"]["forms"], ABIOS_RFVM_FORMS), "ANCHOR_ABIOS_FORMS_DRIFT")
        tr_p = ap["corpus_c_s92_raw_arabic_treatises"]
        require_ok(tr_p["total_qwen25_tokens"] == S92_TREATISE_TOTALS["total_qwen25_tokens"], "ANCHOR_TR_QWEN_DRIFT")
        require_ok(tr_p["total_smollm2_tokens"] == S92_TREATISE_TOTALS["total_smollm2_tokens"], "ANCHOR_TR_SMOL_DRIFT")
        bi_p = ap["corpus_c_s92_bilingual_catalogs"]
        require_ok(bi_p["total_pairs"] == S92_BILINGUAL_TOTALS["total_pairs"], "ANCHOR_BI_PAIRS_DRIFT")
        require_ok(bi_p["total_qwen25_ar_tokens"] == S92_BILINGUAL_TOTALS["total_qwen25_ar_tokens"], "ANCHOR_BI_QAR_DRIFT")
        require_ok(bi_p["total_smollm2_ar_tokens"] == S92_BILINGUAL_TOTALS["total_smollm2_ar_tokens"], "ANCHOR_BI_SAR_DRIFT")
        res["anchor_verified"] = True
    if expedition_root is not None:
        _validate_path(expedition_root)
        require_ok(expedition_root.is_dir(), "EXPEDITION_ROOT_INVALID")
        for pin in UPSTREAM_CERT_PINS:
            raw = read_regular_file_bytes(expedition_root / pin["relative_ref"], max_bytes=MAX_JSON_BYTES)
            require_ok(len(raw) == pin["bytes"], f"UPSTREAM_BYTES_MISMATCH:{pin['track_id']}")
            require_ok(hmac.compare_digest(hashlib.sha256(raw).hexdigest(), pin["sha256"]), f"UPSTREAM_SHA_MISMATCH:{pin['track_id']}")
        res["upstream_certs_verified"] = len(UPSTREAM_CERT_PINS)
    if hf_cache_root is not None:
        _validate_path(hf_cache_root)
        require_ok(hf_cache_root.is_dir(), "HF_CACHE_ROOT_INVALID")
        for pin in TOKENIZER_PINS:
            # HF hub snapshot tokenizer.json may be a symlink into blobs/; hash via realpath inside hf_cache_root
            cand = (hf_cache_root / pin["rel_cache_path"]).resolve()
            raw = read_regular_file_bytes(cand, max_bytes=MAX_PIN_BYTES)
            require_ok(len(raw) == pin["bytes"], f"TOKENIZER_BYTES_MISMATCH:{pin['id']}")
            require_ok(hmac.compare_digest(hashlib.sha256(raw).hexdigest(), pin["sha256"]), f"TOKENIZER_SHA_MISMATCH:{pin['id']}")
        res["tokenizers_verified"] = len(TOKENIZER_PINS)
    if wave7_root is not None:
        _validate_path(wave7_root)
        require_ok(wave7_root.is_dir(), "WAVE7_ROOT_INVALID")
        cnt = 0
        for pin in WAVE_FIXTURE_PINS:
            if pin["root_kind"] == "wave7":
                raw = read_regular_file_bytes(wave7_root / pin["filename"], max_bytes=MAX_JSON_BYTES)
                require_ok(len(raw) == pin["bytes"], f"WAVE7_BYTES_MISMATCH:{pin['id']}")
                require_ok(hmac.compare_digest(hashlib.sha256(raw).hexdigest(), pin["sha256"]), f"WAVE7_SHA_MISMATCH:{pin['id']}")
                cnt += 1
        res["wave7_fixtures_verified"] = cnt
    if abios_root is not None:
        _validate_path(abios_root)
        require_ok(abios_root.is_dir(), "ABIOS_ROOT_INVALID")
        cnt = 0
        for pin in WAVE_FIXTURE_PINS:
            if pin["root_kind"] == "abios":
                raw = read_regular_file_bytes(abios_root / pin["filename"], max_bytes=MAX_JSON_BYTES)
                require_ok(len(raw) == pin["bytes"], f"ABIOS_BYTES_MISMATCH:{pin['id']}")
                require_ok(hmac.compare_digest(hashlib.sha256(raw).hexdigest(), pin["sha256"]), f"ABIOS_SHA_MISMATCH:{pin['id']}")
                cnt += 1
        res["abios_fixtures_verified"] = cnt
    return res


# ---------------------------------------------------------------------------
# R10+ Static & Live Lean 4.36.0 Verification (Zero-TOCTOU --stdin + $HOME CI)
# ---------------------------------------------------------------------------

def strip_lean_comments_only(source: str) -> tuple[str, list[str]]:
    out: list[str] = []
    errors: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
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
            depth = 1
            out.append("  ")
            i += 2
            continue
        if ch == "-" and nxt == "-":
            i += 2
            out.append("  ")
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        out.append(ch)
        i += 1
    if depth > 0:
        errors.append("LEAN_UNTERMINATED_BLOCK_COMMENT")
    return "".join(out), errors


def audit_lean_source_static(source: str) -> dict[str, Any]:
    require_ok(type(source) is str, "LEAN_SOURCE_NOT_STR")
    cleaned, findings = strip_lean_comments_only(source)
    if _LEAN_QUOTE_OR_GUILLEMET_RE.search(cleaned) is not None:
        findings.append("LEAN_QUOTE_OR_GUILLEMET_FORBIDDEN")
    norm = cleaned.replace("«", "").replace("»", "")
    m_forb = _LEAN_FORBIDDEN_RE.search(norm)
    if m_forb is not None:
        findings.append(f"LEAN_FORBIDDEN_KEYWORD:{m_forb.group(0)}")
    if _LEAN_PARTIAL_RE.search(norm) is not None:
        findings.append("LEAN_PARTIAL_DECL")
    if _LEAN_DECIDE_NATIVE_RE.search(norm) is not None:
        findings.append("LEAN_DECIDE_NATIVE")
    if _LEAN_SKIP_TC_RE.search(norm) is not None:
        findings.append("LEAN_SKIP_KERNEL_TC")
    if _LEAN_EVAL_SPOOF_RE.search(norm) is not None:
        findings.append("LEAN_EVAL_OR_PRINT_SPOOF")
    if _LEAN_ATTR_ESCAPE_RE.search(norm) is not None:
        findings.append("LEAN_ATTR_TRUST_ESCAPE")
    imports = [m.group(1) for m in _LEAN_IMPORT_RE.finditer(norm)]
    if imports:
        findings.append(f"LEAN_NON_ZERO_IMPORTS:{','.join(imports)}")
    return {"clean": len(findings) == 0, "findings": findings, "imports": imports}


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN")
    if env_bin:
        p = Path(env_bin)
        require_ok(p.is_file() and os.access(p, os.X_OK), "LEAN_BINARY_UNAVAILABLE")
        return str(p)
    found = shutil.which("lean")
    if found is not None:
        return found
    home_env = os.environ.get("HOME")
    if home_env:
        for rel in (".local/bin/lean", ".elan/bin/lean"):
            cand = Path(home_env) / rel
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand)
    raise ValueError("LEAN_BINARY_UNAVAILABLE")


_LEAN_ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "TMPDIR")


def _scrubbed_lean_env() -> dict[str, str]:
    """Minimal allowlist stripping LEAN_*, ELAN_*, LAKE_*, LD_PRELOAD, LD_LIBRARY_PATH."""
    clean = {k: os.environ[k] for k in _LEAN_ENV_ALLOWLIST if k in os.environ}
    if "PATH" not in clean:
        clean["PATH"] = "/usr/bin:/bin"
    return clean


def verify_lean_proof(path: Path, *, enforce_sha256: bool = True) -> dict[str, Any]:
    require_ok(type(enforce_sha256) is bool, "INVALID_ENFORCE_SHA256_FLAG")
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    require_ok(b"\r" not in raw, "CRLF_FORBIDDEN")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("LEAN_INVALID_UTF8") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if enforce_sha256:
        require_ok(hmac.compare_digest(sha, EXPECTED_LEAN_SHA256), "LEAN_SHA256_MISMATCH")
    static_res = audit_lean_source_static(source)
    require_ok(static_res["clean"], f"LEAN_STATIC_AUDIT_FAILED:{static_res['findings']}")

    lean_bin = resolve_lean_binary()
    proc = subprocess.run(
        [lean_bin, "--stdin"],
        input=source,
        capture_output=True,
        text=True,
        env=_scrubbed_lean_env(),
        timeout=120,
        check=False,
    )
    require_ok(proc.returncode == 0, f"LEAN_COMPILE_FAILED:{proc.stderr.strip()}")
    require_ok(proc.stderr == "", f"LEAN_NONEMPTY_STDERR:{proc.stderr.strip()}")

    coalesced: list[str] = []
    for raw_ln in proc.stdout.splitlines():
        if raw_ln.startswith("  ") and coalesced:
            coalesced[-1] = coalesced[-1] + " " + raw_ln.strip()
        else:
            coalesced.append(raw_ln.strip())

    seen: dict[str, list[str]] = {}
    zero_ax_count = 0
    axioms_used: set[str] = set()
    for line in coalesced:
        m0 = _ZERO_AXIOM_LINE_RE.match(line)
        if m0 is not None:
            thm = m0.group(1)
            require_ok(thm not in seen, f"LEAN_DUPLICATE_THEOREM:{thm}")
            seen[thm] = []
            zero_ax_count += 1
            continue
        m1 = _DEPENDS_AXIOM_LINE_RE.match(line)
        require_ok(m1 is not None, f"LEAN_UNEXPECTED_STDOUT_LINE:{line}")
        thm = m1.group(1)
        require_ok(thm not in seen, f"LEAN_DUPLICATE_THEOREM:{thm}")
        ax_list = [a.strip() for a in m1.group(2).split(",")]
        for ax in ax_list:
            require_ok(ax in _ALLOWED_LEAN_AXIOMS, f"LEAN_FORBIDDEN_AXIOM:{ax}")
            axioms_used.add(ax)
        seen[thm] = ax_list

    require_ok(len(seen) >= 1, "LEAN_NO_THEOREMS_VERIFIED")
    if enforce_sha256:
        require_ok(tuple(seen.keys()) == EXPECTED_LEAN_THEOREMS, "LEAN_THEOREM_LIST_MISMATCH")
    return {
        "lean_file": path.name,
        "lean_sha256": sha,
        "sha256_pinned": enforce_sha256,
        "static_clean": True,
        "theorems_verified": len(seen),
        "zero_axiom_theorems": zero_ax_count,
        "axioms_used": sorted(axioms_used),
        "imports": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S100 Hardened Field-Complete Verifier")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--standalone", action="store_true", help="Emit canonical certificate JSON")
    mode.add_argument("--write", type=Path, help="Atomically write canonical 0o600 certificate JSON")
    mode.add_argument("--check", type=Path, help="Fail-closed Zone-B verification of certificate JSON")
    mode.add_argument("--verify-lean", type=Path, help="R10+ static + live Lean 4.36.0 verification")
    mode.add_argument("--verify-pins", action="store_true", help="Verify pinned anchor/certs/tokenizers/fixtures")
    parser.add_argument("--anchor-file", type=Path, default=None, help="Path to s100_tokenizer_anchor.json")
    parser.add_argument("--expedition-root", type=Path, default=None, help="Read-only expedition parent root")
    parser.add_argument("--hf-cache-root", type=Path, default=None, help="Read-only HuggingFace hub cache root")
    parser.add_argument("--wave7-root", type=Path, default=None, help="Read-only Wave-7 snapshot directory")
    parser.add_argument("--abios-root", type=Path, default=None, help="Read-only abios fixture directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    try:
        if args.write is not None:
            cert = build_certificate_envelope()
            verify_certificate_dict(cert, full_replay=True)
            atomic_write_0600(args.write, canonical_json_bytes(cert) + b"\n")
            if args.json:
                sys.stdout.buffer.write(
                    canonical_json_bytes({"status": "WRITTEN", "certificate_sha256": cert["certificate_sha256"]}) + b"\n"
                )
            return 0
        if args.check is not None:
            res = check_certificate_file(args.check, full_replay=True)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        if args.verify_lean is not None:
            res = verify_lean_proof(args.verify_lean, enforce_sha256=True)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        if args.verify_pins:
            res = verify_pins_on_disk(
                anchor_file=args.anchor_file,
                expedition_root=args.expedition_root,
                hf_cache_root=args.hf_cache_root,
                wave7_root=args.wave7_root,
                abios_root=args.abios_root,
            )
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        cert = build_certificate_envelope()
        verify_certificate_dict(cert, full_replay=True)
        sys.stdout.buffer.write(canonical_json_bytes(cert) + b"\n")
        return 0
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
