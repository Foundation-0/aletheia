#!/usr/bin/env python3
"""
Track S77 Hardened Standalone Verifier & R9 Lean 4.36.0 Auditor.

Supports:
  --standalone --json       Compute and emit canonical zero-float certificate JSON to stdout
  --write <cert.json>       Atomically write canonical 0o600 certificate JSON via dir_fd + fsync
  --check <cert.json>       Fail-closed Zone-B hardened verification of certificate JSON on disk
  --verify-lean <file.lean> Full R9 11-class static Lean 4 audit + live Lean 4.36.0 axiom check

Zero floats on trust paths, zero bare asserts, zero external dependencies, zero RNG calls.
"""
from __future__ import annotations

import argparse
import errno
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
import threading
from typing import Any

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from s77_mellin_wsp_tomography import (
    CERT_SCHEMA,
    CERT_TRACK_ID,
    LEAN_FILE_SHA256,
    LEAN_THEOREMS,
    MAX_INT_BITS,
    MAX_JSON_DEPTH,
    S77Error,
    build_certificate,
    canonical_json_bytes,
    require_ok,
)

MAX_JSON_BYTES = 1_048_576
_READ_CHUNK_BYTES = 65_536
MAX_INT_DIGITS = 617
_HEX_LOWER = frozenset("0123456789abcdef")
_CERT_KEYS = frozenset({"schema", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset(
    {
        "pillar1_mellin_glu_primitives",
        "pillar2_quantization_margin_collision",
        "pillar3_wsp_dpi_security_collision",
        "pillar4_lean4_and_scope",
    }
)
_PAYLOAD_BOOL_KEYS = frozenset(
    {
        "all_carry_pass",
        "all_editors_below_random",
        "bound_holds",
        "carry_margin_pass",
        "diff_dpi_exposes_sign_flip",
        "edits_weights",
        "exact_invariant",
        "finished_mcnemar_p_lt_1e_10",
        "mcnemar_two_sided_p_gt_4_5",
        "mcnemar_two_sided_p_lt_1e_30",
        "sign_flip_verified",
        "single_snapshot_blind_to_sign_flip",
        "single_snapshot_exposes_mellin_graft",
        "telescoping_residual_zero",
    }
)
_EXACT_PATH_TYPES = (Path, type(Path()))
_TEMP_NAME_LOCK = threading.Lock()
_ALLOWED_LEAN_AXIOMS = frozenset({"propext"})


# ---------------------------------------------------------------------------
# Strict Zone-B Zero-Float JSON & Digest Primitives
# ---------------------------------------------------------------------------

def validate_json_tree_iterative(obj: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    if type(max_depth) is not int or max_depth < 1 or max_depth > 256:
        raise S77Error("INVALID_MAX_DEPTH", "max_depth must be int in [1, 256]")
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            raise S77Error("JSON_DEPTH_EXCEEDED", f"nesting depth > {max_depth}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                if type(k) is not str:
                    raise S77Error("NON_STR_KEY", "dict keys must be strict str")
                try:
                    k.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise S77Error("INVALID_UNICODE_STR", f"lone surrogate key: {exc}") from exc
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is int:
            if cur.bit_length() > MAX_INT_BITS:
                raise S77Error("INT_BIT_LIMIT", f"int exceeds {MAX_INT_BITS} bits")
        elif t is str:
            try:
                cur.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise S77Error("INVALID_UNICODE_STR", f"lone surrogate str: {exc}") from exc
        elif t is bool or cur is None:
            continue
        else:
            raise S77Error("FORBIDDEN_JSON_TYPE", f"forbidden JSON value type: {t.__name__}")


def _no_dups_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise S77Error("DUPLICATE_JSON_KEY", f"duplicate key: {k}")
        out[k] = v
    return out


def _forbid_float(token: str) -> Any:
    raise S77Error("FLOAT_FORBIDDEN", f"float literal forbidden: {token}")


def _forbid_constant(token: str) -> Any:
    raise S77Error("NONFINITE_CONSTANT", f"non-finite constant forbidden: {token}")


def _parse_capped_int_token(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_INT_DIGITS:
        raise S77Error("INT_DIGIT_LIMIT", f"integer token exceeds {MAX_INT_DIGITS} digits")
    val = int(token)
    if val.bit_length() > MAX_INT_BITS:
        raise S77Error("INT_BIT_LIMIT", f"integer token exceeds {MAX_INT_BITS} bits")
    return val


def parse_strict_json(text: str) -> Any:
    if type(text) is not str:
        raise S77Error("INVALID_JSON_TEXT", "JSON text must be strict str")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S77Error("INVALID_UNICODE_STR", f"lone surrogate in JSON text: {exc}") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise S77Error("JSON_TOO_LARGE", f"JSON exceeds {MAX_JSON_BYTES} bytes")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_no_dups_hook,
            parse_int=_parse_capped_int_token,
            parse_float=_forbid_float,
            parse_constant=_forbid_constant,
        )
    except S77Error:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S77Error("JSON_DECODE_ERROR", f"invalid JSON: {exc}") from exc
    validate_json_tree_iterative(parsed)
    return parsed


def require_sha256_hex(val: Any, label: str) -> str:
    if type(val) is not str:
        raise S77Error("INVALID_DIGEST_TYPE", f"{label} must be strict str")
    if len(val) != 64:
        raise S77Error("INVALID_DIGEST_LEN", f"{label} must have length 64")
    if any(ch not in _HEX_LOWER for ch in val):
        raise S77Error("INVALID_DIGEST_HEX", f"{label} must be lowercase ASCII hex")
    return val


def exact_typed_equal(lhs: Any, rhs: Any) -> bool:
    """Iterative strict structural + exact-type equality (rejects bool/int swaps & subclasses)."""
    stack: list[tuple[Any, Any]] = [(lhs, rhs)]
    while stack:
        a, b = stack.pop()
        ta, tb = type(a), type(b)
        if ta is not tb:
            return False
        if ta is dict:
            if len(a) != len(b):
                return False
            for k, va in a.items():
                if k not in b:
                    return False
                stack.append((va, b[k]))
        elif ta is list:
            if len(a) != len(b):
                return False
            for va, vb in zip(a, b):
                stack.append((va, vb))
        elif a != b:
            return False
    return True


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed in-memory Zone-B secondary auditor for the certificate payload alone."""
    validate_json_tree_iterative(payload)
    if type(payload) is not dict:
        raise S77Error("BAD_PAYLOAD_TYPE", "payload must be strict dict")
    if frozenset(payload.keys()) != _PAYLOAD_KEYS:
        raise S77Error("BAD_PAYLOAD_KEYS", "payload keys mismatch")

    stack: list[Any] = [payload]
    while stack:
        cur = stack.pop()
        if type(cur) is dict:
            if len(cur) == 2 and "num" in cur and "den" in cur:
                require_ok(
                    type(cur["num"]) is int and type(cur["den"]) is int and cur["den"] > 0,
                    "BAD_RATIONAL_DICT",
                    "rational dict must have exact int num and positive int den",
                )
            for k, v in cur.items():
                if type(v) is bool:
                    require_ok(k in _PAYLOAD_BOOL_KEYS, "UNEXPECTED_BOOL_FIELD", f"unexpected bool at {k}")
                elif k == "sha256":
                    require_sha256_hex(v, "sha256")
                elif type(v) in (dict, list):
                    stack.append(v)
        else:
            for item in cur:
                require_ok(type(item) is not bool, "UNEXPECTED_BOOL_ITEM", "unexpected bool in payload list")
                if type(item) in (dict, list):
                    stack.append(item)

    for pk in _PAYLOAD_KEYS:
        require_ok(type(payload[pk]) is dict, "BAD_PILLAR_TYPE", f"{pk} must be strict dict")
    p4 = payload["pillar4_lean4_and_scope"]
    lean_cert = p4.get("lean4_certificate")
    require_ok(type(lean_cert) is dict, "BAD_LEAN_CERT_TYPE", "lean4_certificate must be strict dict")
    require_ok(
        lean_cert.get("theorem_count") == len(LEAN_THEOREMS),
        "BAD_THEOREM_COUNT",
        "theorem_count mismatch",
    )
    lean_sha = require_sha256_hex(lean_cert.get("sha256"), "lean4_certificate.sha256")
    require_ok(hmac.compare_digest(lean_sha, LEAN_FILE_SHA256), "BAD_LEAN_PIN", "Lean SHA pin mismatch")
    nov = p4.get("novelty_honesty_law4")
    require_ok(type(nov) is dict, "BAD_NOVELTY_TYPE", "novelty_honesty_law4 must be strict dict")
    require_ok(nov.get("n2_claims") == 0, "BAD_NOVELTY_CLAIMS", "n2_claims must be 0")
    return payload


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    """Fail-closed in-memory Zone-B verifier supporting FR1 (full_replay=True) and FR0 (full_replay=False)."""
    require_ok(type(full_replay) is bool, "INVALID_FULL_REPLAY", "full_replay must be strict bool")
    validate_json_tree_iterative(cert)
    if type(cert) is not dict:
        raise S77Error("NON_OBJECT_ROOT", "certificate root must be strict dict")
    if frozenset(cert.keys()) != _CERT_KEYS:
        raise S77Error("BAD_CERT_KEYS", "certificate keys mismatch")
    if cert["schema"] != CERT_SCHEMA:
        raise S77Error("BAD_SCHEMA", "schema mismatch")
    if cert["track_id"] != CERT_TRACK_ID:
        raise S77Error("BAD_TRACK_ID", "track_id mismatch")

    payload = cert["payload"]
    if type(payload) is not dict:
        raise S77Error("BAD_PAYLOAD_TYPE", "payload must be strict dict")

    claimed_p_sha = require_sha256_hex(cert["payload_sha256"], "payload_sha256")
    claimed_c_sha = require_sha256_hex(cert["certificate_sha256"], "certificate_sha256")

    calc_p_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    if not hmac.compare_digest(claimed_p_sha, calc_p_sha):
        raise S77Error("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    envelope = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": claimed_p_sha,
        "payload": payload,
    }
    calc_c_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    if not hmac.compare_digest(claimed_c_sha, calc_c_sha):
        raise S77Error("CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    secondary_audit_payload(payload)

    if full_replay:
        expected = build_certificate()
        if not exact_typed_equal(payload, expected["payload"]):
            raise S77Error("PAYLOAD_ORACLE_MISMATCH", "payload disagrees with exact-Q oracle")
        if not hmac.compare_digest(claimed_c_sha, expected["certificate_sha256"]):
            raise S77Error("ORACLE_CERT_SHA_MISMATCH", "certificate_sha256 disagrees with exact-Q oracle")
    return cert


def audit_certificate_object(cert: Any) -> dict[str, Any]:
    """Fail-closed in-memory Zone-B hardened full-replay auditor."""
    return verify_certificate_dict(cert, full_replay=True)


# ---------------------------------------------------------------------------
# Hardened dir_fd File I/O (TOCTOU, Symlink, FIFO, Hardlink, 0o600 Atomic Write)
# ---------------------------------------------------------------------------

def _validate_path(path: Any) -> None:
    if type(path) not in _EXACT_PATH_TYPES:
        raise S77Error("INVALID_PATH_TYPE", "path must be concrete pathlib.Path")
    raw = str(path)
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S77Error("INVALID_UNICODE_STR", f"lone surrogate in path: {exc}") from exc
    if "\x00" in raw:
        raise S77Error("INVALID_PATH_NUL", "NUL byte forbidden in path")


def _is_symlink_at(dfd: int, name: str) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(name, dir_fd=dfd).st_mode)
    except OSError:
        return False


def _check_pwd_no_symlinks() -> None:
    pwd = os.environ.get("PWD")
    if pwd is None or not os.path.isabs(pwd):
        return
    try:
        pwd.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S77Error("INVALID_UNICODE_STR", f"lone surrogate in PWD: {exc}") from exc
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in Path(pwd).parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise S77Error("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink in PWD: {comp}") from exc
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
    if len(parts) == 0 or parts[-1] == "..":
        raise S77Error("INVALID_PATH", "path must name a regular file")
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise S77Error("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink ancestor: {comp}") from exc
                raise S77Error("PARENT_DIR_ERROR", f"cannot open ancestor {comp}: {exc}") from exc
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
                raise S77Error("SYMLINK_FORBIDDEN", f"symlink forbidden: {path}") from exc
            raise S77Error("FILE_READ_ERROR", f"cannot open {path}: {exc}") from exc
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise S77Error("NOT_REGULAR_FILE", f"not a regular file: {path}")
        if st.st_nlink != 1:
            raise S77Error("HARDLINK_FORBIDDEN", f"hardlink forbidden (st_nlink={st.st_nlink})")
        if st.st_size > max_bytes:
            raise S77Error("FILE_TOO_LARGE", f"file exceeds {max_bytes} bytes")
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = os.read(fd, _READ_CHUNK_BYTES)
            except OSError as exc:
                raise S77Error("FILE_READ_ERROR", f"read error on {path}: {exc}") from exc
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise S77Error("FILE_TOO_LARGE", f"stream exceeded {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dir_fd)


def write_atomic_0600_bytes(path: Path, data: bytes) -> None:
    dir_fd, leaf = _open_parent_dir_fd(path)
    tmp_name = ""
    fd = -1
    try:
        if _is_symlink_at(dir_fd, leaf):
            raise S77Error("SYMLINK_FORBIDDEN", f"symlink target forbidden: {path}")
        try:
            st_existing = os.lstat(leaf, dir_fd=dir_fd)
            if not stat.S_ISREG(st_existing.st_mode):
                raise S77Error("NOT_REGULAR_FILE", f"target is not a regular file: {path}")
            if st_existing.st_nlink > 1:
                raise S77Error("HARDLINK_FORBIDDEN", f"target hardlink forbidden: {path}")
        except FileNotFoundError:
            pass
        with _TEMP_NAME_LOCK:
            tmp_name = f".{leaf}.tmp.{secrets.token_hex(8)}"
            fd = os.open(
                tmp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600,
                dir_fd=dir_fd,
            )
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(data):
            n = os.write(fd, view[written:])
            if n <= 0:
                raise S77Error("FILE_WRITE_ERROR", "short zero write")
            written += n
        os.fsync(fd)
        st_tmp = os.fstat(fd)
        if st_tmp.st_nlink != 1:
            raise S77Error("HARDLINK_FORBIDDEN", "temp file gained extra hardlink")
        os.close(fd)
        fd = -1
        os.replace(tmp_name, leaf, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        tmp_name = ""
        os.fsync(dir_fd)
    except S77Error:
        raise
    except OSError as exc:
        raise S77Error("FILE_WRITE_ERROR", f"atomic write failed: {exc}") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_name:
            try:
                os.unlink(tmp_name, dir_fd=dir_fd)
            except OSError:
                pass
        os.close(dir_fd)


def check_certificate_file(path: Path) -> dict[str, Any]:
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    if b"\r" in raw:
        raise S77Error("CRLF_FORBIDDEN", "CR/CRLF bytes forbidden in canonical certificate")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S77Error("INVALID_UTF8", f"invalid UTF-8: {exc}") from exc
    parsed = parse_strict_json(text)
    cert = audit_certificate_object(parsed)
    expected_bytes = canonical_json_bytes(cert) + b"\n"
    if raw != expected_bytes:
        raise S77Error("NONCANONICAL_BYTES", "certificate file bytes are not canonical LF-terminated JSON")
    return cert


# ---------------------------------------------------------------------------
# R9 11-Class Static Lean 4 Scanner + Live Lean 4.36.0 Axiom Verifier
# ---------------------------------------------------------------------------

_LEAN4_HARD_LINE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsorry\b"), "LEAN4_SORRY"),
    (re.compile(r"\badmit\b"), "LEAN4_ADMIT"),
    (re.compile(r"(?<!\.)\baxiom\b"), "LEAN4_AXIOM"),
    (re.compile(r"(?<!\.)\bunsafe\b"), "LEAN4_UNSAFE"),
    (re.compile(r"\bnative_decide\b"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\bLean\.Meta\.mkSorry\b|\bmkSorry\b"), "LEAN4_MK_SORRY"),
    (re.compile(r"\bLean\.ofReduceBool\b|\bofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\bLean\.ofReduceNat\b|\bofReduceNat\b"), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"\bLean\.trustCompiler\b|\btrustCompiler\b"), "LEAN4_TRUST_COMPILER"),
)
_LEAN4_PARTIAL_DECL_RE = re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", flags=re.DOTALL)
_LEAN4_GUILLEMET_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
_LEAN4_SIMPLE_GUILLEMET_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_']*\Z")
_LEAN4_DEBUG_RE = re.compile(
    r"\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b",
    flags=re.DOTALL,
)
_LEAN4_PRINT_KW = (
    "def|theorem|lemma|axiom|inductive|structure|class|instance|opaque|abbrev|example|"
    "namespace|section|end|open|variable|universe|import|set_option|attribute|"
    "local|scoped|private|protected|noncomputable|partial|unsafe|meta|where|by|in|let|have"
)
_LEAN4_SPOOF_RE = re.compile(
    r"#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|exit(?![\w'!?])|"
    r"print(?![\w'!?])(?!\s+axioms[ \t]+(?!(?:" + _LEAN4_PRINT_KW + r")(?![\w'!?]))[A-Za-z_]))"
    r"|(?<!\.)\b(?:run_cmd|run_meta|initialize|builtin_initialize)\b",
    flags=re.DOTALL,
)
_LEAN4_IMPORT_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)",
    flags=re.DOTALL,
)
_LEAN4_ATTR_OPEN_RE = re.compile(r"(?:@|(?<!\.)\battribute\s*)\[", flags=re.DOTALL)
_LEAN4_HARD_ATTR_RE = re.compile(r"\b(extern|implemented_by|csimp)\b")
_LEAN4_META_SYNTAX_RE = re.compile(
    r"(?<!\.)\b(?:syntax|macro_rules|macro|elab|elab_rules|declare_syntax_cat|notation|prefix|infixl|infixr|infix|postfix)\b"
)
_LEAN4_CHAR_PREV_IDENT = "_'»!?"
_LEAN4_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_LEAN4_INTERP_BANG_WORDS = frozenset(
    ("s", "f", "m", "v", "println", "reportIssue", "reportDbgIssue", "reportEMatchIssue")
)
_LEAN4_INTERP_KEYWORDS = frozenset(("dbg_trace", "throwError"))
_LEAN4_DECIDE_KW_RE = re.compile(r"\bdecide\b")
_LEAN4_FLAG_TOK_RE = re.compile(r"[+-][A-Za-z0-9_]+")
_LEAN4_OPT_PREFIX_RE = re.compile(r"\s*([A-Za-z0-9_]+)\s*:=")
_LEAN4_CONFIG_NATIVE_RE = re.compile(r"\bnative\b(?:\s*:=\s*([^},]*))?")
_LEAN4_CONFIG_WITH_RE = re.compile(r"\bwith\b")
_LEAN4_DECIDE_CFG_BIND_RE = re.compile(
    r"\b(?:DecideConfig|Decide\.Config)\b[ \t)]*:=\s*(?:\(\s*)*\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}\s*:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b",
    flags=re.DOTALL,
)
_LEAN4_AXIOM_OUT_RE = re.compile(
    r"^'([^']+)'\s+(?:does not depend on any axioms|depends on axioms:\s*\[([^\]]*)\])$"
)


def _is_lean4_ident_prev(source: str, pos: int) -> bool:
    if pos < 0:
        return False
    ch = source[pos]
    if ch.isalnum() or ch in "_.'":
        return True
    if ch in "!?":
        for k in range(pos - 1, -1, -1):
            if source[k] not in "!?":
                return source[k].isalnum() or source[k] in "_'"
        return False
    return False


def _match_lean4_char_literal_end(source: str, i: int, n: int) -> int | None:
    """Return end index of a Lean 4 Char literal starting at source[i] == "'", or None."""
    if i + 2 < n and source[i + 1] not in ("\\", "\n") and source[i + 2] == "'":
        return i + 3
    if i + 3 < n and source[i + 1] == "\\":
        esc = source[i + 2]
        if source[i + 3] == "'" and esc != "\n":
            return i + 4
        if (
            esc == "x"
            and i + 5 < n
            and source[i + 5] == "'"
            and all(c in _LEAN4_HEX_DIGITS for c in source[i + 3 : i + 5])
        ):
            return i + 6
        if (
            esc == "u"
            and i + 7 < n
            and source[i + 7] == "'"
            and all(c in _LEAN4_HEX_DIGITS for c in source[i + 3 : i + 7])
        ):
            return i + 8
    return None


def _strip_lean4_r9(source: str) -> tuple[str, list[str]]:
    """R10-hardened Lean 4 comment/char/string/raw-string/spaced-interp/unknown-bang stripper."""
    out: list[str] = []
    errors: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    in_interp = False
    pending_interp = False
    interp_stack: list[int] = []
    raw_hashes = -1
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
        if raw_hashes >= 0:
            close_seq = '"' + ("#" * raw_hashes)
            if source.startswith(close_seq, i):
                out.append(" " * len(close_seq))
                i += len(close_seq)
                raw_hashes = -1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_str:
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                in_str = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_interp:
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == "{":
                interp_stack.append(1)
                in_interp = False
                out.append(" ")
                i += 1
            elif ch == '"':
                in_interp = False
                out.append(" ")
                i += 1
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
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch.isspace():
            out.append(ch)
            i += 1
            continue
        if ch != '"':
            pending_interp = False
        if interp_stack:
            if ch == "{":
                interp_stack[-1] += 1
                out.append(ch)
                i += 1
                continue
            if ch == "}":
                interp_stack[-1] -= 1
                out.append(ch)
                i += 1
                if interp_stack[-1] == 0:
                    interp_stack.pop()
                    in_interp = True
                continue
        if ch == '"':
            if pending_interp:
                in_interp = True
                pending_interp = False
            else:
                if _is_lean4_ident_prev(source, i - 2) and source[i - 1] == "!":
                    is_panic = (
                        source[i - 6 : i] == "panic!"
                        and not _is_lean4_ident_prev(source, i - 7)
                    )
                    if not is_panic:
                        errors.append("LEAN4_UNKNOWN_BANG_STRING")
                in_str = True
            out.append(" ")
            i += 1
        elif ch == "«":
            end_g = source.find("»", i + 1)
            if end_g == -1:
                errors.append("LEAN4_UNTERMINATED_IDENT")
                break
            inner = source[i + 1 : end_g]
            if _LEAN4_SIMPLE_GUILLEMET_RE.match(inner) is not None and inner != "axioms":
                out.append(source[i : end_g + 1])
            else:
                out.append(" " * (end_g - i + 1))
            i = end_g + 1
        elif ch == "'" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in _LEAN4_CHAR_PREV_IDENT)):
            char_end = _match_lean4_char_literal_end(source, i, n)
            if char_end is not None:
                out.append(" " * (char_end - i))
                i = char_end
            else:
                out.append(ch)
                i += 1
        elif ch == "r" and not _is_lean4_ident_prev(source, i - 1):
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                raw_hashes = j - (i + 1)
                out.append(" " * (j - i + 1))
                i = j + 1
            else:
                out.append(ch)
                i += 1
        elif ch.isalpha() and not _is_lean4_ident_prev(source, i - 1):
            w_end = i + 1
            while w_end < n and (source[w_end].isalnum() or source[w_end] == "_"):
                w_end += 1
            word = source[i:w_end]
            next_ch = source[w_end] if w_end < n else ""
            if next_ch == "!" and word in _LEAN4_INTERP_BANG_WORDS:
                pending_interp = True
                out.append(source[i : w_end + 1])
                i = w_end + 1
                continue
            if word in _LEAN4_INTERP_KEYWORDS:
                pending_interp = True
            out.append(word)
            i = w_end
        else:
            out.append(ch)
            i += 1
    if depth > 0:
        errors.append("LEAN4_UNTERMINATED_COMMENT")
    elif in_str or in_interp or raw_hashes >= 0 or interp_stack:
        errors.append("LEAN4_UNTERMINATED_STRING")
    return "".join(out), errors


def _strip_outer_parens(rhs: str) -> str:
    s = rhs.strip()
    while len(s) >= 2 and s[0] == "(" and s[-1] == ")":
        s = s[1:-1].strip()
    return s


def _is_native_false(rhs: str) -> bool:
    return _strip_outer_parens(rhs) in ("false", "Bool.false")


def _scan_decide_native(cleaned: str) -> bool:
    for mc in _LEAN4_DECIDE_CFG_BIND_RE.finditer(cleaned):
        for g in mc.groups():
            if g is not None and not _is_native_false(g):
                return True
    n = len(cleaned)
    match_rp: dict[int, int] = {}
    pstack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "(":
            pstack.append(idx)
        elif ch == ")" and pstack:
            match_rp[pstack.pop()] = idx
    for m in _LEAN4_DECIDE_KW_RE.finditer(cleaned):
        pos = m.end()
        while True:
            while pos < n and cleaned[pos].isspace():
                pos += 1
            if pos >= n:
                break
            ch = cleaned[pos]
            if ch in "+-":
                mf = _LEAN4_FLAG_TOK_RE.match(cleaned, pos)
                if mf is None:
                    break
                if mf.group(0) == "+native":
                    return True
                pos = mf.end()
                continue
            if ch == "(":
                close_i = match_rp.get(pos)
                if close_i is None:
                    break
                mp = _LEAN4_OPT_PREFIX_RE.match(cleaned, pos + 1, close_i)
                if mp is None:
                    break
                key = mp.group(1)
                rhs = cleaned[mp.end() : close_i].strip()
                if key == "native" and not _is_native_false(rhs):
                    return True
                if key == "config":
                    inner = _strip_outer_parens(rhs)
                    if not (inner.startswith("{") and inner.endswith("}")):
                        return True
                    body = inner[1:-1]
                    if "{" in body or "}" in body or _LEAN4_CONFIG_WITH_RE.search(body) is not None:
                        return True
                    for mn in _LEAN4_CONFIG_NATIVE_RE.finditer(body):
                        if mn.group(1) is None or not _is_native_false(mn.group(1)):
                            return True
                pos = close_i + 1
                continue
            break
    return False


def audit_lean4_source_r9(source: str) -> list[str]:
    """Return list of R9 static Lean 4 finding codes (empty list iff clean)."""
    if type(source) is not str:
        raise S77Error("INVALID_LEAN_SOURCE", "Lean source must be strict str")
    cleaned, findings = _strip_lean4_r9(source)
    cleaned = _LEAN4_GUILLEMET_RE.sub(r"\1", cleaned)
    for line in cleaned.splitlines():
        for pat, code in _LEAN4_HARD_LINE_RULES:
            if pat.search(line) is not None:
                findings.append(code)
    for m_imp in _LEAN4_IMPORT_RE.finditer(cleaned):
        root_pkg = m_imp.group(1).split(".")[0]
        if root_pkg not in ("Init", "Std"):
            findings.append("LEAN4_NON_INIT_IMPORT")
    if _LEAN4_PARTIAL_DECL_RE.search(cleaned) is not None:
        findings.append("LEAN4_PARTIAL")
    if _scan_decide_native(cleaned):
        findings.append("LEAN4_DECIDE_NATIVE")
    if _LEAN4_DEBUG_RE.search(cleaned) is not None:
        findings.append("LEAN4_SKIP_KERNEL_TC")
    if _LEAN4_SPOOF_RE.search(cleaned) is not None:
        findings.append("LEAN4_EVAL_SPOOF")
    if _LEAN4_META_SYNTAX_RE.search(cleaned) is not None:
        findings.append("LEAN4_META_SYNTAX_ESCAPE")
    match_rb: dict[int, int] = {}
    bstack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "[":
            bstack.append(idx)
        elif ch == "]" and bstack:
            match_rb[bstack.pop()] = idx
    for m_open in _LEAN4_ATTR_OPEN_RE.finditer(cleaned):
        lb = m_open.end() - 1
        rb = match_rb.get(lb)
        if rb is not None and _LEAN4_HARD_ATTR_RE.search(cleaned, lb + 1, rb) is not None:
            findings.append("LEAN4_ATTR_TRUST_ESCAPE")
    return findings


def _find_lean_binary() -> str:
    found = shutil.which("lean")
    if found is not None:
        return found
    elan_lean = Path.home() / ".elan" / "bin" / "lean"
    if elan_lean.is_file():
        return str(elan_lean)
    raise S77Error("LEAN_BINARY_NOT_FOUND", "lean binary not found on PATH or ~/.elan/bin")


def verify_lean_file(path: Path, *, check_pinned_sha: bool = True) -> dict[str, Any]:
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    if b"\r" in raw:
        raise S77Error("CRLF_FORBIDDEN", "CR/CRLF forbidden in Lean file")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S77Error("INVALID_UTF8", f"invalid UTF-8 in Lean file: {exc}") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if check_pinned_sha and not hmac.compare_digest(sha, LEAN_FILE_SHA256):
        raise S77Error("LEAN_SHA_MISMATCH", "Lean file SHA-256 does not match pinned digest")
    findings = audit_lean4_source_r9(source)
    require_ok(len(findings) == 0, "LEAN_R9_STATIC_FINDING", f"R9 findings: {findings}")
    lean_bin = _find_lean_binary()
    proc = subprocess.run(
        [lean_bin, str(path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    require_ok(proc.returncode == 0, "LEAN_COMPILE_FAILED", f"lean exited {proc.returncode}: {proc.stderr}")
    require_ok(proc.stderr == "", "LEAN_STDERR_NONEMPTY", f"unexpected lean stderr: {proc.stderr}")
    records: list[str] = []
    for raw_line in proc.stdout.splitlines():
        s = raw_line.strip()
        if records and "[" in records[-1] and "]" not in records[-1]:
            records[-1] = records[-1] + " " + s
        else:
            records.append(s)
    seen: dict[str, list[str]] = {}
    for line in records:
        m = _LEAN4_AXIOM_OUT_RE.match(line)
        require_ok(m is not None, "LEAN_UNEXPECTED_OUTPUT", f"unexpected lean output line: {line}")
        thm = m.group(1)
        require_ok(thm not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate #print axioms for {thm}")
        ax_raw = m.group(2)
        ax_list = [] if ax_raw is None else [a.strip() for a in ax_raw.split(",") if a.strip()]
        for ax in ax_list:
            require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"{thm} uses forbidden axiom {ax}")
        seen[thm] = ax_list
    if check_pinned_sha:
        require_ok(tuple(seen.keys()) == LEAN_THEOREMS, "LEAN_THEOREM_SET_MISMATCH", "theorem set mismatch")
    return {
        "lean_file": path.name,
        "sha256": sha,
        "r9_findings": 0,
        "theorems_verified": len(seen),
        "allowed_axioms": sorted(_ALLOWED_LEAN_AXIOMS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S77 Mellin-GLU x WSP-Gym x siliquant Verifier")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--standalone", action="store_true", help="Run exact-Q oracle and emit canonical JSON")
    mode.add_argument("--write", type=Path, help="Atomically write canonical 0o600 certificate JSON")
    mode.add_argument("--check", type=Path, help="Verify canonical certificate JSON fail-closed")
    mode.add_argument("--verify-lean", type=Path, help="Run R9 static + live Lean 4.36.0 kernel verification")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    try:
        if args.write is not None:
            cert = build_certificate()
            audit_certificate_object(cert)
            out_bytes = canonical_json_bytes(cert) + b"\n"
            write_atomic_0600_bytes(args.write, out_bytes)
            if args.json:
                sys.stdout.buffer.write(
                    canonical_json_bytes(
                        {"status": "WRITTEN", "certificate_sha256": cert["certificate_sha256"]}
                    )
                    + b"\n"
                )
            return 0
        if args.check is not None:
            cert = check_certificate_file(args.check)
            if args.json:
                sys.stdout.buffer.write(
                    canonical_json_bytes(
                        {"status": "PASS", "certificate_sha256": cert["certificate_sha256"]}
                    )
                    + b"\n"
                )
            return 0
        if args.verify_lean is not None:
            res = verify_lean_file(args.verify_lean, check_pinned_sha=True)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        cert = build_certificate()
        audit_certificate_object(cert)
        out_bytes = canonical_json_bytes(cert) + b"\n"
        sys.stdout.buffer.write(out_bytes)
        return 0
    except S77Error as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc.message}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
