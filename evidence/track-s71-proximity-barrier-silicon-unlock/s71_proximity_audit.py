"""Fail-Closed Silicon Verification & Hardened Lean 4 Static/Live Auditor for S71.

Pure integer / rational auditing (zero floats, zero bare asserts, zero os.path.islink):
  - O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC dir_fd regular-file reader with inode-matched $PWD check
  - Atomic 0o600 certificate writer with short-write, temp-tamper, and ENOSPC leak-free cleanup
  - Strict canonical JSON parser (pre-int() MAX_INT_DIGITS guard, no floats/NaN/dup-keys/subclasses)
  - Full R8 Lean 4.36.0 static scanner (guillemets, Char hex/unicode/ident-prime, nested comments,
    raw/interpolated strings, decide +native, post-decl attribute, glued #eval/#exit/non-axioms #print)
    plus live `lean` compiler axiom allowlist & stdout warning rejection
  - Exact live receipt directory verifier (preregistration, C/Lean sources, RAPL JSON, mlos receipt)
"""

from __future__ import annotations

import errno
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

STUDY_DIR = Path(__file__).resolve().parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

import s71_proximity_oracle as oracle

MAX_CERT_BYTES = 131_072
MAX_RECEIPT_BYTES = 1_048_576
MAX_JSON_DEPTH = 32
MAX_INT_BITS = 256
MAX_INT_DIGITS = 1000
_HEX_LOWER = frozenset("0123456789abcdef")
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

# ---- Hardened R8 Lean 4 Static Lexer & Trust-Escape Rules ----
_LEAN4_IDENT_EXTRA = "_.'!?"
_LEAN4_CHAR_PREV_IDENT = "_'\u00bb!?"
_LEAN4_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_LEAN4_SIMPLE_GUILLEMET_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_']*\Z")
_LEAN4_GUILLEMET_UNWRAP_RE = re.compile(r"\u00ab([A-Za-z_][A-Za-z0-9_']*)\u00bb")

_LEAN4_HARD_LINE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsorry\b"), "LEAN4_SORRY"),
    (re.compile(r"\badmit\b"), "LEAN4_ADMIT"),
    (re.compile(r"(?<!\.)\baxiom\b"), "LEAN4_AXIOM"),
    (re.compile(r"(?<!\.)\bunsafe\b"), "LEAN4_UNSAFE"),
    (re.compile(r"\bnative_decide\b"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\bLean\.Meta\.mkSorry\b|\bmkSorry\b"), "LEAN4_MK_SORRY"),
    (re.compile(r"\bLean\.ofReduceBool\b|\bofReduceBool\b"), "LEAN4_REDUCE_BOOL"),
    (re.compile(r"\bLean\.ofReduceNat\b|\bofReduceNat\b"), "LEAN4_REDUCE_NAT"),
    (re.compile(r"\bLean\.trustCompiler\b|\btrustCompiler\b"), "LEAN4_TRUST_COMPILER"),
)
_LEAN4_PARTIAL_DECL_RE = re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", flags=re.DOTALL)
_LEAN4_SKIP_KERNEL_TC_RE = re.compile(r"\bdebug\s*\.\s*skipKernelTC\b", flags=re.DOTALL)
_LEAN4_DECIDE_KW_RE = re.compile(r"\bdecide\b")
_LEAN4_FLAG_TOK_RE = re.compile(r"[+-][A-Za-z0-9_]+")
_LEAN4_OPT_PREFIX_RE = re.compile(r"\s*([A-Za-z0-9_]+)\s*:=")
_LEAN4_CONFIG_NATIVE_RE = re.compile(r"\bnative\b(?:\s*:=\s*([^},]*))?")
_LEAN4_CONFIG_AFTER_COMMA_RE = re.compile(r",\s*(?:\Z|[A-Za-z_][A-Za-z0-9_']*\s*:=)")
_LEAN4_CONFIG_WITH_RE = re.compile(r"\bwith\b")
_LEAN4_DECIDE_CONFIG_BIND_RE = re.compile(
    r"\b(?:DecideConfig|Decide\.Config)\b[ \t)]*:=\s*(?:\(\s*)*\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}\s*:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,:]*)(?:,[^}{]*)?:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b[^}{]*\}",
    flags=re.DOTALL,
)
_LEAN4_PRINT_AXIOMS_KW_BLOCK = (
    "def|theorem|lemma|axiom|inductive|structure|class|instance|opaque|abbrev|"
    "namespace|section|end|open|variable|universe|import|set_option|attribute|"
    "local|scoped|private|protected|noncomputable|partial|unsafe|meta|where|by|in|let|have"
)
_LEAN4_EVAL_SPOOF_RE = re.compile(
    r"#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|exit(?![\w'!?])|"
    r"print(?![\w'!?])(?!\s+axioms[ \t]+(?!(?:"
    + _LEAN4_PRINT_AXIOMS_KW_BLOCK
    + r")(?![\w'!?]))[A-Za-z_]))"
    r"|(?<!\.)\b(?:run_cmd|run_meta)\b",
    flags=re.DOTALL,
)
_LEAN4_IMPORT_FULL_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)",
    flags=re.DOTALL,
)
_LEAN4_ATTR_OPEN_RE = re.compile(r"(?:@|(?<!\.)\battribute\s*)\[", flags=re.DOTALL)
_LEAN4_HARD_ATTR_KW_RE = re.compile(r"\b(extern|implemented_by)\b")
_LEAN4_AXIOM_OUT_NO_RE = re.compile(r"^'([A-Za-z0-9_.']+)' does not depend on any axioms$")
_LEAN4_AXIOM_OUT_LIST_RE = re.compile(r"^'([A-Za-z0-9_.']+)' depends on axioms: \[([^\]]*)\]$")


class AuditError(ValueError):
    """Fail-closed audit error carrying a structured machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _is_hex64(val: Any) -> bool:
    return type(val) is str and len(val) == 64 and all(ch in _HEX_LOWER for ch in val)


def _validate_path(path: Path) -> str:
    if not isinstance(path, Path):
        raise AuditError("INVALID_PATH", "path must be a pathlib.Path instance")
    raw = os.fspath(path)
    if "\x00" in raw:
        raise AuditError("INVALID_PATH", "path must not contain NUL bytes")
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AuditError("INVALID_PATH", "path contains unpaired UTF-16 surrogates") from exc
    return raw


def _parse_strict_int(token: str) -> int:
    body = token[1:] if token.startswith("-") else token
    if len(body) > MAX_INT_DIGITS:
        raise AuditError("INT_TOO_LARGE", f"integer token exceeds {MAX_INT_DIGITS} digits")
    return int(token)


def _parse_receipt_decimal(token: str) -> Decimal:
    if len(token) > MAX_INT_DIGITS:
        raise AuditError("INT_TOO_LARGE", f"numeric token exceeds {MAX_INT_DIGITS} chars")
    return Decimal(token)


def _validate_json_tree_iter(root: Any) -> None:
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise AuditError("DEPTH_EXCEEDED", f"JSON nesting exceeds {MAX_JSON_DEPTH}")
        nt = type(node)
        if nt is dict:
            for k, v in node.items():
                if type(k) is not str:
                    raise AuditError("INVALID_KEY_TYPE", "JSON object key must be exact str")
                try:
                    k.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise AuditError("INVALID_UTF8_SURROGATE", "unpaired UTF-16 surrogate in key") from exc
                stack.append((v, depth + 1))
        elif nt is list:
            for item in node:
                stack.append((item, depth + 1))
        elif nt is str:
            try:
                node.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise AuditError("INVALID_UTF8_SURROGATE", "unpaired UTF-16 surrogate in string") from exc
        elif nt is int:
            if node.bit_length() > MAX_INT_BITS:
                raise AuditError("INT_TOO_LARGE", f"integer exceeds {MAX_INT_BITS} bits")
        elif nt is bool:
            continue
        else:
            raise AuditError("INVALID_VALUE_TYPE", f"unsupported value type: {nt.__name__}")


def _reject_float_token(token: str) -> Any:
    raise AuditError("FLOAT_FORBIDDEN", f"floating-point JSON token forbidden: {token}")


def _reject_const_token(token: str) -> Any:
    raise AuditError("CONSTANT_FORBIDDEN", f"non-standard JSON constant forbidden: {token}")


def _no_duplicate_keys_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise AuditError("DUPLICATE_KEY", f"duplicate JSON object key: {k}")
        out[k] = v
    return out


def _normalize_darwin_system_prefix(parts: tuple[str, ...]) -> tuple[str, ...]:
    if sys.platform != "darwin":
        return parts
    if len(parts) < 2 or parts[0] != "/" or ".." in parts:
        return parts
    head = parts[1]
    if head not in ("var", "tmp", "etc"):
        return parts
    try:
        st = os.lstat("/" + head)
        if not stat.S_ISLNK(st.st_mode) or st.st_uid != 0:
            return parts
        target = os.readlink("/" + head)
    except OSError:
        return parts
    if target == "private/" + head:
        return ("/", "private", head, *parts[2:])
    return parts


def _open_dir_chain_nofollow(anchor_path: str, components: tuple[str, ...]) -> int:
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        cur_fd = os.open(anchor_path, dir_flags)
    except OSError as exc:
        raise AuditError("DIR_OPEN_FAILED", f"cannot open anchor directory: {exc.strerror}") from exc

    for comp in components:
        if comp in ("", "."):
            continue
        try:
            nxt_fd = os.open(comp, dir_flags, dir_fd=cur_fd)
        except OSError as exc:
            err_no = exc.errno
            if err_no == errno.ELOOP:
                os.close(cur_fd)
                raise AuditError("SYMLINK_FORBIDDEN", f"symlink ancestor rejected: {comp}") from exc
            if err_no == errno.ENOTDIR:
                try:
                    st_c = os.lstat(comp, dir_fd=cur_fd)
                    if stat.S_ISLNK(st_c.st_mode):
                        os.close(cur_fd)
                        raise AuditError("SYMLINK_FORBIDDEN", f"symlink ancestor rejected: {comp}") from exc
                except OSError:
                    pass
            os.close(cur_fd)
            raise AuditError("DIR_OPEN_FAILED", f"cannot traverse directory component {comp}: {exc.strerror}") from exc
        os.close(cur_fd)
        cur_fd = nxt_fd
    return cur_fd


def _open_parent_dir_nofollow(path: Path) -> tuple[int, str]:
    _validate_path(path)
    parts = path.parts
    if not parts:
        raise AuditError("EMPTY_PATH", "empty path rejected")
    if parts[-1] in ("", ".", "..", "/"):
        raise AuditError("INVALID_BASENAME", "path must name a regular file basename")

    if path.is_absolute():
        norm = _normalize_darwin_system_prefix(parts)
        return _open_dir_chain_nofollow("/", norm[1:-1]), norm[-1]

    pwd_env = os.environ.get("PWD", "")
    if pwd_env.startswith("/") and "\x00" not in pwd_env:
        try:
            st_pwd = os.stat(pwd_env)
            st_cwd = os.stat(".")
            if st_pwd.st_ino == st_cwd.st_ino and st_pwd.st_dev == st_cwd.st_dev:
                pwd_parts = _normalize_darwin_system_prefix(Path(pwd_env).parts)
                chk_fd = _open_dir_chain_nofollow("/", pwd_parts[1:])
                os.close(chk_fd)
        except OSError:
            pass
    return _open_dir_chain_nofollow(".", parts[:-1]), parts[-1]


def read_regular_file_bytes(path: Path, max_bytes: int = MAX_CERT_BYTES) -> bytes:
    """Open regular file strictly via O_NOFOLLOW | O_NONBLOCK | dir_fd with size & hardlink guards."""
    dir_fd, name = _open_parent_dir_nofollow(path)
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = -1
    try:
        try:
            fd = os.open(name, file_flags, dir_fd=dir_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise AuditError("SYMLINK_FORBIDDEN", f"symlink file rejected: {name}") from exc
            raise AuditError("FILE_OPEN_FAILED", f"cannot open file {name}: {exc.strerror}") from exc

        try:
            st = os.fstat(fd)
        except OSError as exc:
            raise AuditError("FILE_READ_FAILED", f"fstat failed on {name}: {exc.strerror}") from exc
        if not stat.S_ISREG(st.st_mode):
            raise AuditError("NON_REGULAR_FILE", f"non-regular file rejected: {name}")
        if st.st_nlink != 1:
            raise AuditError("HARDLINK_FORBIDDEN", f"hardlinked file rejected (nlink={st.st_nlink})")
        if st.st_size > max_bytes:
            raise AuditError("FILE_TOO_LARGE", f"file size {st.st_size} exceeds {max_bytes}")

        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                blk = os.read(fd, 16384)
            except OSError as exc:
                raise AuditError("FILE_READ_FAILED", f"read failed on {name}: {exc.strerror}") from exc
            if not blk:
                break
            total += len(blk)
            if total > max_bytes:
                raise AuditError("FILE_TOO_LARGE", f"stream size exceeded {max_bytes}")
            chunks.append(blk)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dir_fd)


def write_certificate_atomic(path: Path, payload: dict[str, Any]) -> str:
    """Atomically write canonical certificate JSON with strict 0o600 permissions and full cleanup."""
    if type(payload) is not dict:
        raise AuditError("INVALID_ROOT", "certificate payload must be exact dict")
    _validate_json_tree_iter(payload)
    raw = oracle.canonical_json_bytes(payload)

    dir_fd, target_name = _open_parent_dir_nofollow(path)
    tmp_name = ""
    tmp_fd: int | None = None
    try:
        try:
            st_existing = os.lstat(target_name, dir_fd=dir_fd)
            if stat.S_ISLNK(st_existing.st_mode):
                raise AuditError("SYMLINK_FORBIDDEN", "refusing atomic overwrite of symlink target")
            if not stat.S_ISREG(st_existing.st_mode):
                raise AuditError("NON_REGULAR_FILE", "refusing atomic overwrite of non-regular target")
            if st_existing.st_nlink != 1:
                raise AuditError("HARDLINK_FORBIDDEN", "refusing atomic overwrite of hardlinked target")
        except FileNotFoundError:
            pass

        create_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        for _ in range(32):
            cand = f".{target_name}.tmp.{secrets.token_hex(8)}"
            try:
                tmp_fd = os.open(cand, create_flags, 0o600, dir_fd=dir_fd)
                tmp_name = cand
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise AuditError("ATOMIC_WRITE_FAILED", f"cannot create temp file: {exc.strerror}") from exc
        if tmp_fd is None:
            raise AuditError("ATOMIC_WRITE_FAILED", "exhausted temp file candidates")

        try:
            os.fchmod(tmp_fd, 0o600)
            view = memoryview(raw)
            written = 0
            while written < len(raw):
                n = os.write(tmp_fd, view[written:])
                if n <= 0:
                    raise AuditError("SHORT_WRITE", "zero-byte write during atomic certificate emit")
                written += n
            st_tmp = os.fstat(tmp_fd)
            if not stat.S_ISREG(st_tmp.st_mode) or st_tmp.st_nlink != 1:
                raise AuditError("TEMP_TAMPERED", "temp file tampered before atomic replace")
            os.fsync(tmp_fd)
            os.close(tmp_fd)
            tmp_fd = None
            os.replace(tmp_name, target_name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            tmp_name = ""
            os.fsync(dir_fd)
        except AuditError:
            raise
        except OSError as exc:
            raise AuditError("ATOMIC_WRITE_FAILED", f"atomic write failed: {exc.strerror}") from exc
        return hashlib.sha256(raw).hexdigest()
    except BaseException:
        if tmp_fd is not None:
            os.close(tmp_fd)
            tmp_fd = None
        if tmp_name:
            try:
                os.unlink(tmp_name, dir_fd=dir_fd)
            except OSError:
                pass
        raise
    finally:
        if tmp_fd is not None:
            os.close(tmp_fd)
        os.close(dir_fd)


def _assert_exact_tree_bijection(actual: Any, expected: Any, trail: str = "$") -> None:
    if type(actual) is not type(expected):
        raise AuditError("SCHEMA_TYPE_MISMATCH", f"type mismatch at {trail}")
    if type(expected) is dict:
        if set(actual.keys()) != set(expected.keys()):
            raise AuditError("SCHEMA_KEY_MISMATCH", f"key mismatch at {trail}")
        for k in sorted(expected.keys()):
            _assert_exact_tree_bijection(actual[k], expected[k], f"{trail}.{k}")
    elif type(expected) is list:
        if len(actual) != len(expected):
            raise AuditError("SCHEMA_LEN_MISMATCH", f"list length mismatch at {trail}")
        for idx, (a_i, e_i) in enumerate(zip(actual, expected)):
            _assert_exact_tree_bijection(a_i, e_i, f"{trail}[{idx}]")
    elif actual != expected:
        raise AuditError("INVARIANT_MISMATCH", f"value mismatch at {trail}")


def parse_strict_certificate_bytes(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or b"\r\n" in raw:
        raise AuditError("NON_CANONICAL_FORMAT", "certificate must be LF-terminated without CRLF")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError("INVALID_UTF8", "certificate bytes are not valid UTF-8") from exc
    try:
        parsed = json.loads(
            text,
            parse_float=_reject_float_token,
            parse_int=_parse_strict_int,
            parse_constant=_reject_const_token,
            object_pairs_hook=_no_duplicate_keys_hook,
        )
    except AuditError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise AuditError("JSON_PARSE_ERROR", f"malformed JSON: {exc}") from exc
    if type(parsed) is not dict:
        raise AuditError("INVALID_ROOT", "certificate JSON root must be an object")
    _validate_json_tree_iter(parsed)
    if oracle.canonical_json_bytes(parsed) != raw:
        raise AuditError("NON_CANONICAL_BYTES", "certificate JSON is not in canonical byte form")
    return parsed


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Independent structural, type-exact, digest, and bijective-invariant verifier."""
    if type(payload) is not dict:
        raise AuditError("INVALID_ROOT", "certificate payload must be exact dict")
    _validate_json_tree_iter(payload)
    if "certificate_sha256" not in payload or not _is_hex64(payload["certificate_sha256"]):
        raise AuditError("INVALID_DIGEST", "certificate_sha256 missing or not lowercase 64-hex")
    body = {k: v for k, v in payload.items() if k != "certificate_sha256"}
    recomputed = hashlib.sha256(oracle.canonical_json_bytes(body)).hexdigest()
    if not hmac.compare_digest(recomputed, payload["certificate_sha256"]):
        raise AuditError("DIGEST_MISMATCH", "certificate_sha256 does not match canonical body")
    expected = oracle.build_certificate()
    expected_body = {k: v for k, v in expected.items() if k != "certificate_sha256"}
    _assert_exact_tree_bijection(body, expected_body)
    return {"valid": True, "certificate_sha256": payload["certificate_sha256"]}


def verify_certificate_payload(payload: Any, *, full_replay: bool = True) -> dict[str, Any]:
    if type(full_replay) is not bool:
        raise AuditError("INVALID_FLAG_TYPE", "full_replay must be exact bool")
    sec = secondary_audit_payload(payload)
    if full_replay:
        expected = oracle.build_certificate()
        if payload != expected:
            raise AuditError("REPLAY_MISMATCH", "payload diverged from standalone oracle replay")
    return {"valid": True, "full_replay": full_replay, "certificate_sha256": sec["certificate_sha256"]}


def verify_certificate_file(path: Path, *, full_replay: bool = True) -> dict[str, Any]:
    if type(full_replay) is not bool:
        raise AuditError("INVALID_FLAG_TYPE", "full_replay must be exact bool")
    raw = read_regular_file_bytes(path, max_bytes=MAX_CERT_BYTES)
    parsed = parse_strict_certificate_bytes(raw)
    res = verify_certificate_payload(parsed, full_replay=full_replay)
    res["file_sha256"] = hashlib.sha256(raw).hexdigest()
    return res


def _match_lean4_char_literal_end(source: str, i: int, n: int) -> int | None:
    if i + 2 < n and source[i + 1] != "\\" and source[i + 1] != "\n" and source[i + 2] == "'":
        return i + 3
    if i + 3 < n and source[i + 1] == "\\":
        if source[i + 3] == "'" and source[i + 2] != "\n":
            return i + 4
        esc = source[i + 2]
        if esc == "x" and i + 5 < n and source[i + 5] == "'" and all(c in _LEAN4_HEX_DIGITS for c in source[i + 3 : i + 5]):
            return i + 6
        if esc == "u" and i + 7 < n and source[i + 7] == "'" and all(c in _LEAN4_HEX_DIGITS for c in source[i + 3 : i + 7]):
            return i + 8
    return None


def _strip_lean4_r8(source: str) -> tuple[str, list[dict[str, Any]]]:
    """R8-hardened single-pass O(n) Lean 4 comment/string/char/guillemet stripper."""
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    in_interp = False
    interp_stack: list[list[int]] = []
    raw_hashes = -1
    opened_at = 0
    unterminated: list[dict[str, Any]] = []

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
                interp_stack.append([1, opened_at])
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
        if interp_stack:
            if ch == "{":
                interp_stack[-1][0] += 1
                out.append(ch)
                i += 1
                continue
            if ch == "}":
                interp_stack[-1][0] -= 1
                out.append(ch)
                i += 1
                if interp_stack[-1][0] == 0:
                    _, opened_at = interp_stack.pop()
                    in_interp = True
                continue
        if ch == "/" and nxt == "-":
            depth = 1
            opened_at = i
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "r" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in _LEAN4_IDENT_EXTRA)):
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                raw_hashes = j - (i + 1)
                opened_at = i
                out.append(" " * (j - i + 1))
                i = j + 1
            else:
                out.append(ch)
                i += 1
        elif ch == "!" and nxt == '"' and i >= 1 and source[i - 1] in "smf" and (i == 1 or not (source[i - 2].isalnum() or source[i - 2] in _LEAN4_IDENT_EXTRA)):
            in_interp = True
            opened_at = i
            out.append("  ")
            i += 2
        elif ch == '"':
            in_str = True
            opened_at = i
            out.append(" ")
            i += 1
        elif ch == "\u00ab":
            end_g = source.find("\u00bb", i + 1)
            if end_g == -1:
                lineno = source.count("\n", 0, i) + 1
                unterminated.append({"line": lineno, "code": "LEAN4_UNTERMINATED_IDENT"})
                out.append("\n" * source.count("\n", i))
                break
            inner = source[i + 1 : end_g]
            if _LEAN4_SIMPLE_GUILLEMET_RE.match(inner) is not None and inner != "axioms":
                out.append(source[i : end_g + 1])
            else:
                out.append(" " + "".join("\n" if c == "\n" else " " for c in inner) + " ")
            i = end_g + 1
        elif ch == "'" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in _LEAN4_CHAR_PREV_IDENT)):
            char_end = _match_lean4_char_literal_end(source, i, n)
            if char_end is not None:
                out.append(" " * (char_end - i))
                i = char_end
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1

    unclosed_open = depth > 0 or in_str or in_interp or raw_hashes >= 0
    if unclosed_open or interp_stack:
        err_at = opened_at if unclosed_open else interp_stack[-1][1]
        lineno = source.count("\n", 0, err_at) + 1
        unterminated.append({"line": lineno, "code": "LEAN4_UNTERMINATED_COMMENT" if depth > 0 else "LEAN4_UNTERMINATED_STRING"})
    return "".join(out), unterminated


def _build_paren_map(text: str) -> dict[int, int]:
    match_rparen: dict[int, int] = {}
    stk: list[int] = []
    for idx, ch in enumerate(text):
        if ch == "(":
            stk.append(idx)
        elif ch == ")" and stk:
            match_rparen[stk.pop()] = idx
    return match_rparen


def _unwrap_lean4_span(
    text: str,
    lo: int,
    hi: int,
    match_rparen: dict[int, int],
) -> tuple[int, int]:
    while True:
        while lo < hi and text[lo].isspace():
            lo += 1
        while hi > lo and text[hi - 1].isspace():
            hi -= 1
        if match_rparen.get(lo) == hi - 1:
            lo += 1
            hi -= 1
            continue
        break
    return lo, hi


def _is_lean4_native_rhs_false_span(
    text: str,
    lo: int,
    hi: int,
    match_rparen: dict[int, int],
) -> bool:
    lo, hi = _unwrap_lean4_span(text, lo, hi, match_rparen)
    return text[lo:hi] in ("false", "Bool.false")


def _is_lean4_safe_config_span(
    text: str,
    lo: int,
    hi: int,
    match_rparen: dict[int, int],
) -> bool:
    lo, hi = _unwrap_lean4_span(text, lo, hi, match_rparen)
    if text[lo : lo + 1] != "{" or text[hi - 1 : hi] != "}":
        return False
    body_lo = lo + 1
    body_hi = hi - 1
    if text.find("{", body_lo, body_hi) != -1 or text.find("}", body_lo, body_hi) != -1:
        return False
    if _LEAN4_CONFIG_WITH_RE.search(text, body_lo, body_hi) is not None:
        return False
    for m_nv in _LEAN4_CONFIG_NATIVE_RE.finditer(text, body_lo, body_hi):
        if not _is_lean4_native_rhs_false_span(text, m_nv.start(1), m_nv.end(1), match_rparen):
            return False
        sep = m_nv.end()
        if sep != body_hi and not _LEAN4_CONFIG_AFTER_COMMA_RE.match(text, sep, body_hi):
            return False
    return True


def _scan_lean4_decide_native(
    cleaned: str,
    match_rparen: dict[int, int],
) -> list[tuple[int, int]]:
    """Single-pass O(n) multi-flag balanced-paren scanner for Lean 4 `decide` native escapes."""
    n = len(cleaned)
    spans: list[tuple[int, int]] = []
    for m_dec in _LEAN4_DECIDE_KW_RE.finditer(cleaned):
        start = m_dec.start()
        pos = m_dec.end()
        native_hit = False
        while True:
            ws = pos
            while ws != n and cleaned[ws].isspace():
                ws += 1
            if ws == n:
                break
            ch = cleaned[ws]
            if ch in "+-":
                m_flag = _LEAN4_FLAG_TOK_RE.match(cleaned, ws)
                if m_flag is None:
                    break
                if m_flag.group(0) == "+native":
                    native_hit = True
                pos = m_flag.end()
                continue
            if ch == "(":
                close_idx = match_rparen.get(ws)
                if close_idx is None:
                    break
                m_pfx = _LEAN4_OPT_PREFIX_RE.match(cleaned, ws + 1, close_idx)
                if m_pfx is None:
                    break
                opt_key = m_pfx.group(1)
                rhs_lo = m_pfx.end()
                if opt_key == "native":
                    if not _is_lean4_native_rhs_false_span(cleaned, rhs_lo, close_idx, match_rparen):
                        native_hit = True
                elif opt_key == "config":
                    if not _is_lean4_safe_config_span(cleaned, rhs_lo, close_idx, match_rparen):
                        native_hit = True
                pos = close_idx + 1
                continue
            break
        if native_hit:
            spans.append((start, pos))
    return spans


def audit_lean4_source(source: str) -> dict[str, Any]:
    """Static R8 Lean 4 trust-escape scanner returning clean flag and structured findings."""
    cleaned, findings = _strip_lean4_r8(source)
    cleaned = _LEAN4_GUILLEMET_UNWRAP_RE.sub(r"\1", cleaned)
    for lineno, line in enumerate(cleaned.splitlines(), start=1):
        for pat, code in _LEAN4_HARD_LINE_RULES:
            if pat.search(line) is not None:
                findings.append({"line": lineno, "code": code})
    for m_imp in _LEAN4_IMPORT_FULL_RE.finditer(cleaned):
        root_pkg = m_imp.group(1).split(".")[0]
        if root_pkg not in ("Init", "Std"):
            findings.append({"line": cleaned[: m_imp.start(1)].count("\n") + 1, "code": "LEAN4_NON_INIT_IMPORT"})
    for pat, code in (
        (_LEAN4_PARTIAL_DECL_RE, "LEAN4_PARTIAL"),
        (_LEAN4_SKIP_KERNEL_TC_RE, "LEAN4_SKIP_KERNEL_TC"),
        (_LEAN4_EVAL_SPOOF_RE, "LEAN4_EVAL_SPOOF"),
    ):
        for m in pat.finditer(cleaned):
            findings.append({"line": cleaned[: m.start()].count("\n") + 1, "code": code})
    match_rparen = _build_paren_map(cleaned)
    decide_spans = _scan_lean4_decide_native(cleaned, match_rparen)
    for ds, _ in decide_spans:
        findings.append({"line": cleaned[:ds].count("\n") + 1, "code": "LEAN4_DECIDE_NATIVE"})
    for m_dc in _LEAN4_DECIDE_CONFIG_BIND_RE.finditer(cleaned):
        if any(ds <= m_dc.start() < de for ds, de in decide_spans):
            continue
        rhs_grp = next((g for g in m_dc.groups() if g is not None), "")
        if not _is_lean4_native_rhs_false_span(rhs_grp, 0, len(rhs_grp), _build_paren_map(rhs_grp)):
            findings.append({"line": cleaned[: m_dc.start()].count("\n") + 1, "code": "LEAN4_DECIDE_NATIVE"})
    match_rb: dict[int, int] = {}
    stk: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "[":
            stk.append(idx)
        elif ch == "]" and stk:
            match_rb[stk.pop()] = idx
    for m_open in _LEAN4_ATTR_OPEN_RE.finditer(cleaned):
        rb = match_rb.get(m_open.end() - 1)
        if rb is not None and _LEAN4_HARD_ATTR_KW_RE.search(cleaned, m_open.end(), rb) is not None:
            findings.append({"line": cleaned[: m_open.start()].count("\n") + 1, "code": "LEAN4_ATTR_TRUST_ESCAPE"})
    return {"clean": len(findings) == 0, "findings": findings}


def verify_lean4_file(path: Path, *, lean_bin: str = "lean") -> dict[str, Any]:
    """Static R8 audit + live Lean 4.36.0 compiler check rejecting warnings, stderr, & non-allowlist axioms."""
    raw = read_regular_file_bytes(path, max_bytes=MAX_RECEIPT_BYTES)
    try:
        src = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError("INVALID_UTF8", "Lean source is not valid UTF-8") from exc
    static = audit_lean4_source(src)
    if not static["clean"]:
        raise AuditError("LEAN4_STATIC_REJECT", f"static Lean 4 findings: {static['findings']}")
    resolved_bin = lean_bin
    if lean_bin == "lean" and shutil.which("lean") is None:
        elan_lean = Path.home() / ".elan" / "bin" / "lean"
        if elan_lean.exists():
            resolved_bin = os.fspath(elan_lean)
    try:
        proc = subprocess.run([resolved_bin, os.fspath(path)], capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuditError("LEAN4_EXEC_FAILED", f"cannot run Lean compiler: {exc}") from exc
    if proc.returncode != 0:
        raise AuditError("LEAN4_COMPILE_FAILED", f"lean exited with code {proc.returncode}")
    if proc.stderr.strip():
        raise AuditError("LEAN4_STDERR_NONEMPTY", "lean emitted non-empty stderr")
    theorems: dict[str, list[str]] = {}
    for line in proc.stdout.splitlines():
        s = line.strip()
        if not s:
            continue
        if "warning:" in s.lower():
            raise AuditError("LEAN4_WARNING_FORBIDDEN", f"lean emitted warning: {s[:80]}")
        m_no = _LEAN4_AXIOM_OUT_NO_RE.match(s)
        if m_no is not None:
            theorems[m_no.group(1)] = []
            continue
        m_ls = _LEAN4_AXIOM_OUT_LIST_RE.match(s)
        if m_ls is not None:
            axs = [a.strip() for a in m_ls.group(2).split(",") if a.strip()]
            bad = [a for a in axs if a not in _ALLOWED_LEAN_AXIOMS]
            if bad:
                raise AuditError("LEAN4_FORBIDDEN_AXIOM", f"disallowed axioms {bad} on {m_ls.group(1)}")
            theorems[m_ls.group(1)] = axs
            continue
        raise AuditError("LEAN4_UNEXPECTED_STDOUT", f"unexpected lean stdout line: {s[:80]}")
    if len(theorems) < 12:
        raise AuditError("LEAN4_THEOREM_COUNT", f"expected >= 12 theorems, got {len(theorems)}")
    return {"valid": True, "theorems_verified": len(theorems), "lean_sha256": hashlib.sha256(raw).hexdigest()}


def verify_receipts_directory(root_dir: Path) -> dict[str, Any]:
    """Read preregistration, C/Lean sources, live empirical JSON, and mlos receipt safely."""
    _validate_path(root_dir)
    prereg_raw = read_regular_file_bytes(root_dir / "s71_preregistration.json", max_bytes=MAX_RECEIPT_BYTES)
    c_raw = read_regular_file_bytes(root_dir / "s71_proximity_bench.c", max_bytes=MAX_RECEIPT_BYTES)
    lean_raw = read_regular_file_bytes(root_dir / "ProximityBarrierSilicon.lean", max_bytes=MAX_RECEIPT_BYTES)
    emp_raw = read_regular_file_bytes(root_dir / "s71_empirical_results.json", max_bytes=MAX_RECEIPT_BYTES)
    mlos_raw = read_regular_file_bytes(root_dir / "mlos_zone_b_receipt.json", max_bytes=MAX_RECEIPT_BYTES)

    try:
        prereg_obj = json.loads(
            prereg_raw.decode("utf-8"),
            parse_float=_reject_float_token,
            parse_int=_parse_strict_int,
            parse_constant=_reject_const_token,
            object_pairs_hook=_no_duplicate_keys_hook,
        )
        emp_obj = json.loads(
            emp_raw.decode("utf-8"),
            parse_float=_parse_receipt_decimal,
            parse_int=_parse_strict_int,
            parse_constant=_reject_const_token,
            object_pairs_hook=_no_duplicate_keys_hook,
        )
        mlos_obj = json.loads(
            mlos_raw.decode("utf-8"),
            parse_float=_parse_receipt_decimal,
            parse_int=_parse_strict_int,
            parse_constant=_reject_const_token,
            object_pairs_hook=_no_duplicate_keys_hook,
        )
    except AuditError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise AuditError("RECEIPT_PARSE_ERROR", f"malformed receipt JSON: {exc}") from exc

    if type(prereg_obj) is not dict or type(emp_obj) is not dict or type(mlos_obj) is not dict:
        raise AuditError("RECEIPT_ROOT_INVALID", "all receipt JSON roots must be objects")

    try:
        res = oracle.verify_live_receipts(
            prereg_obj,
            emp_obj,
            mlos_obj,
            hashlib.sha256(prereg_raw).hexdigest(),
            hashlib.sha256(c_raw).hexdigest(),
            hashlib.sha256(lean_raw).hexdigest(),
            hashlib.sha256(emp_raw).hexdigest(),
            hashlib.sha256(mlos_raw).hexdigest(),
        )
    except (KeyError, TypeError, AttributeError, ValueError, ZeroDivisionError) as exc:
        raise AuditError("RECEIPT_SCHEMA_ERROR", f"receipt schema mismatch: {exc}") from exc

    if not res["all_verified"]:
        raise AuditError("RECEIPT_VERIFICATION_FAILED", f"failed checks: {res['checks']}")
    return res


_TOKEN_ROW_SOURCES: list[tuple[str, str, int]] = [
    ("ww2_8b", "write_write_2core", 8),
    ("ww2_64b", "write_write_2core", 64),
    ("ww8_8b", "write_write_8core", 8),
    ("ww8_64b", "write_write_8core", 64),
    ("rd8_8b", "read_shared_8core", 8),
    ("rd8_64b", "read_shared_8core", 64),
    ("rd8_65536b", "read_shared_8core", 65536),
    ("gemv_8b", "avx512_a16_blockh4_stride_sweep", 8),
    ("gemv_64b", "avx512_a16_blockh4_stride_sweep", 64),
]
_TOKEN_LABEL_SOURCES: list[tuple[str, str, str]] = [
    ("gemv_dual_opt", "avx512_a16_blockh4_dual_force", "dual_force_aligned_reg_read_shared"),
    ("gemv_disp_4096b", "avx512_a16_blockh4_dual_force", "aligned_reg_dispersed_read_4096B"),
]
_TOKEN_SCALARS: list[str] = ["a16_syndrome_errors", "avx512_int64_mismatches", "multicore_int64_mismatches"]
_TOKEN_FIELDS: tuple[str, ...] = ("total_ops", "ns", "tsc", "pkg_uj", "core_uj", "uncore_uj")


def verify_frozen_tokens_bijection(cert_dir: Path) -> dict[str, Any]:
    """Exact bijection between oracle.FROZEN_S71_TOKENS and the shipped s71_empirical_results.json rows.

    Every frozen token must equal exactly one empirical row (matched uniquely by stride or label),
    so a silent drift in either direction is caught by the CI-invoked `--check` command.
    """
    _validate_path(cert_dir)
    emp_raw = read_regular_file_bytes(cert_dir / "s71_empirical_results.json", max_bytes=MAX_RECEIPT_BYTES)
    try:
        emp_obj = json.loads(
            emp_raw.decode("utf-8"),
            parse_float=_parse_receipt_decimal,
            parse_int=_parse_strict_int,
            parse_constant=_reject_const_token,
            object_pairs_hook=_no_duplicate_keys_hook,
        )
    except AuditError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise AuditError("BIJECTION_PARSE_ERROR", f"malformed empirical JSON: {exc}") from exc
    if type(emp_obj) is not dict or type(emp_obj.get("measurements")) is not dict:
        raise AuditError("BIJECTION_SCHEMA_ERROR", "empirical JSON must have a measurements object")
    meas = emp_obj["measurements"]
    tokens = oracle.FROZEN_S71_TOKENS
    checked = 0

    def _rows_of(group: Any) -> list[Any]:
        rows = meas.get(group)
        if type(rows) is not list:
            raise AuditError("BIJECTION_SCHEMA_ERROR", f"measurements.{group} missing or not a list")
        return rows

    for key, group, stride in _TOKEN_ROW_SOURCES:
        matches = [r for r in _rows_of(group) if type(r) is dict and r.get("stride_bytes") == stride]
        if len(matches) != 1:
            raise AuditError(
                "BIJECTION_MISMATCH",
                f"token {key}: expected exactly 1 row at stride {stride} in {group}, found {len(matches)}",
            )
        tok = tokens[key]
        for field in _TOKEN_FIELDS:
            if tok.get(field) != matches[0].get(field):
                raise AuditError(
                    "BIJECTION_MISMATCH",
                    f"token {key}.{field}: frozen {tok.get(field)!r} != json {matches[0].get(field)!r}",
                )
        checked += 1
    for key, group, label in _TOKEN_LABEL_SOURCES:
        matches = [r for r in _rows_of(group) if type(r) is dict and r.get("label") == label]
        if len(matches) != 1:
            raise AuditError(
                "BIJECTION_MISMATCH",
                f"token {key}: expected exactly 1 row with label {label!r} in {group}, found {len(matches)}",
            )
        tok = tokens[key]
        for field in _TOKEN_FIELDS:
            if tok.get(field) != matches[0].get(field):
                raise AuditError(
                    "BIJECTION_MISMATCH",
                    f"token {key}.{field}: frozen {tok.get(field)!r} != json {matches[0].get(field)!r}",
                )
        checked += 1
    for key in _TOKEN_SCALARS:
        if tokens.get(key) != meas.get(key):
            raise AuditError(
                "BIJECTION_MISMATCH",
                f"token {key}: frozen {tokens.get(key)!r} != json {meas.get(key)!r}",
            )
        checked += 1
    return {"frozen_tokens_bijection_ok": True, "entries_checked": checked}


def _require_cli_path(raw_arg: str) -> Path:
    if not raw_arg or raw_arg.startswith("-"):
        raise AuditError("INVALID_CLI_PATH", "path argument must not be empty or flag-like")
    p = Path(raw_arg)
    _validate_path(p)
    return p


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        if type(args) is not list or any(type(item) is not str for item in args):
            raise AuditError("USAGE_ERROR", "argv must be a list of strings")
        if args == [] or args == ["--standalone", "--json"]:
            cert = oracle.build_certificate()
            sys.stdout.buffer.write(oracle.canonical_json_bytes(cert))
            return 0
        if len(args) == 2 and args[0] == "--check":
            cert_path = _require_cli_path(args[1])
            res = verify_certificate_file(cert_path, full_replay=True)
            res["frozen_tokens_bijection"] = verify_frozen_tokens_bijection(cert_path.parent)
            sys.stdout.buffer.write(oracle.canonical_json_bytes(res))
            return 0
        if len(args) == 2 and args[0] == "--write":
            cert = oracle.build_certificate()
            file_sha = write_certificate_atomic(_require_cli_path(args[1]), cert)
            out = {"written": True, "file_sha256": file_sha, "certificate_sha256": cert["certificate_sha256"]}
            sys.stdout.buffer.write(oracle.canonical_json_bytes(out))
            return 0
        if len(args) == 2 and args[0] == "--verify-receipts":
            res = verify_receipts_directory(_require_cli_path(args[1]))
            sys.stdout.buffer.write(oracle.canonical_json_bytes(res))
            return 0
        if len(args) == 2 and args[0] == "--audit-lean":
            res = verify_lean4_file(_require_cli_path(args[1]))
            sys.stdout.buffer.write(oracle.canonical_json_bytes(res))
            return 0
        raise AuditError(
            "USAGE_ERROR",
            "expected [--standalone --json] | [--check PATH] | [--write PATH] | [--verify-receipts DIR] | [--audit-lean FILE]",
        )
    except AuditError as exc:
        err_obj = {"valid": False, "error_code": exc.code, "error": exc.message}
        sys.stderr.buffer.write((json.dumps(err_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8"))
        return 2


if __name__ == "__main__":
    sys.exit(main())
