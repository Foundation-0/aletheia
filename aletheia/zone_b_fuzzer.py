#!/usr/bin/env python3
"""
`aletheia.zone_b_fuzzer`: Reusable Zero-Dependency 16-Vector Zone-B Adversarial Fuzzer.

Pure Python 3 standard library (`0` bare asserts, `0` external dependencies, `0` RNG calls,
strict zero-float certified outputs).

Fires all 16 canonical Zone-B corpus attack vectors (`ZB01`..`ZB16`) against:
  1. Any CLI certificate checker (`--target-cli <script> --cert <cert.json>`)
  2. Any in-memory Python certificate validator (`fuzz_python_validator(...)`)
  3. Its own built-in hardened reference checker + 7 deliberately vulnerable foils
     (`--self-test --json`, `--standalone --json`, `--write <path>`, `--check <cert.json>`).

Hardened I/O boundary:
  - Atomic `dir_fd` step-down (`O_RDONLY | O_DIRECTORY | O_NOFOLLOW`) + `$PWD` symlink
    ancestor check + leaf `O_RDONLY | O_NOFOLLOW | O_NONBLOCK` + `os.fstat(fd)` `S_ISREG`
    + `65,536`-byte streaming `os.read` capped at `MAX_JSON_BYTES` (closes `renameat2`
    symlink TOCTOU and procfs `st_size==0` unbounded reads)
  - Durable `0o600` `dir_fd` atomic writes (`threading.Lock` + `secrets.token_hex(8)`
    temp naming, `O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK`, `os.fsync`, pre-replace
    `os.fstat(fd).st_nlink == 1`, target `st_nlink <= 1`, `os.replace(..., dir_fd)`,
    and directory `os.fsync`).

Distinguishes four verdicts:
  - `BASELINE_FAILED`: valid baseline certificate failed or timed out
  - `REJECTED_CLEAN`: hostile vector rejected with non-zero exit & no uncaught Python traceback
    (or expected typed exception in-memory excluding masked `ValueError` crash subclasses)
  - `BYPASS`: hostile vector silently accepted (`rc == 0` or no exception raised)
  - `CRASH`: hostile vector triggered an uncaught exception / traceback / timeout, or a masked
    `UnicodeError` / `JSONDecodeError` / raw 4,300-digit `ValueError`
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import copy
import errno
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import tempfile
import threading
from typing import Any

HERE = Path(__file__).resolve().parent
CERT_SCHEMA = "aletheia.zone_b_fuzzer.certificate.v1"
CERT_TRACK_ID = "ALETHEIA-V21-ZONE-B-FUZZER"
MAX_JSON_BYTES = 1_048_576
_READ_CHUNK_BYTES = 65_536
MAX_JSON_DEPTH = 64
MAX_INT_BITS = 2048
MAX_INT_DIGITS = 620
_EXACT_PATH_TYPES = (Path, type(Path()))
_TEMP_NAME_LOCK = threading.Lock()
_HEX_LOWER = frozenset("0123456789abcdef")
_CERT_KEYS = frozenset({"schema", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_REF_SCHEMA = "aletheia.zone_b_fuzzer.reference_cert.v1"
_REF_KEYS = frozenset({"schema", "payload_sha256", "certificate_sha256", "payload"})

# Canonical 16-vector Zone-B corpus (`ZB01`..`ZB16`)
CORPUS_VECTORS: tuple[dict[str, str], ...] = (
    {"id": "ZB01_non_ascii_digest", "surface": "both", "origin": "Non-ASCII 64-char digest triggering hmac.compare_digest TypeError"},
    {"id": "ZB02_lone_surrogate_digest", "surface": "both", "origin": "Unpaired UTF-16 surrogate in digest or dict key"},
    {"id": "ZB03_huge_int_5000_digits", "surface": "both", "origin": "5,000-digit integer exceeding Python 4,300-digit str limit"},
    {"id": "ZB04_deep_nesting", "surface": "both", "origin": "Deeply nested JSON/list triggering RecursionError"},
    {"id": "ZB05_bool_resigned_sha_forgery", "surface": "both", "origin": "1==True / 0==False bool swap with re-signed SHA-256"},
    {"id": "ZB06_bool_as_int_injection", "surface": "both", "origin": "Raw bool-as-int injection exploiting isinstance(True, int)"},
    {"id": "ZB07_duplicate_keys_unicode_escape", "surface": "cli", "origin": "Duplicate JSON object key via Unicode escape"},
    {"id": "ZB08_nonfinite_and_float_literals", "surface": "both", "origin": "NaN, +/-Infinity, and float literals on exact trust paths"},
    {"id": "ZB09_non_dict_root", "surface": "both", "origin": "Non-object JSON/dict root (list, null, None)"},
    {"id": "ZB10_crlf_and_noncanonical_bytes", "surface": "cli", "origin": "CR/CRLF line endings and non-canonical JSON formatting"},
    {"id": "ZB11_lying_sequence_container", "surface": "memory", "origin": "Lying Sequence container whose __len__ disagrees with items"},
    {"id": "ZB12_hostile_mapping_and_subclasses", "surface": "memory", "origin": "Hostile Mapping, builtin subclasses, and non-str dict keys"},
    {"id": "ZB13_hollow_resigned_payload", "surface": "both", "origin": "Self-consistent re-signed SHA over hollowed payload"},
    {"id": "ZB14_symlink_target_and_ancestor", "surface": "cli", "origin": "Symlink file target and symlink ancestor directory"},
    {"id": "ZB15_missing_and_directory_paths", "surface": "cli", "origin": "Missing file path and existing directory path"},
    {"id": "ZB16_invalid_utf8_and_truncated_json", "surface": "cli", "origin": "Invalid UTF-8 bytes and truncated JSON input"},
)


class ZoneBFuzzError(ValueError):
    """Fail-closed typed error for the Zone-B fuzzer and its reference checker."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


# ---------------------------------------------------------------------------
# Strict Zero-Float JSON & Digest Primitives (Zone-B Hardened)
# ---------------------------------------------------------------------------

def require_exact_int(val: Any, label: str, min_val: int | None = None, max_val: int | None = None) -> int:
    if type(val) is not int:
        raise ZoneBFuzzError("INVALID_INT", f"{label} must be strict int")
    blen = val.bit_length()
    if blen > MAX_INT_BITS:
        raise ZoneBFuzzError("INT_BIT_LIMIT", f"{label} bit_length={blen} exceeds {MAX_INT_BITS}")
    if min_val is not None:
        if type(min_val) is not int:
            raise ZoneBFuzzError("INVALID_BOUND", f"{label} min_val must be strict int")
        if val < min_val:
            raise ZoneBFuzzError("INT_TOO_SMALL", f"{label} bit_length={blen} below min_bits={min_val.bit_length()}")
    if max_val is not None:
        if type(max_val) is not int:
            raise ZoneBFuzzError("INVALID_BOUND", f"{label} max_val must be strict int")
        if val > max_val:
            raise ZoneBFuzzError("INT_TOO_LARGE", f"{label} bit_length={blen} above max_bits={max_val.bit_length()}")
    return val


def validate_json_tree_iterative(obj: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    limit = require_exact_int(max_depth, "max_depth", min_val=1, max_val=256)
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > limit:
            raise ZoneBFuzzError("JSON_DEPTH_EXCEEDED", f"nesting depth > {limit}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                if type(k) is not str:
                    raise ZoneBFuzzError("NON_STR_KEY", "dict keys must be strict str")
                try:
                    k.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise ZoneBFuzzError("INVALID_UNICODE_STR", f"lone surrogate key forbidden: {exc}") from exc
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is int:
            blen = cur.bit_length()
            if blen > MAX_INT_BITS:
                raise ZoneBFuzzError("INT_BIT_LIMIT", f"int bit_length={blen} exceeds {MAX_INT_BITS}")
        elif t is str:
            try:
                cur.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ZoneBFuzzError("INVALID_UNICODE_STR", f"lone surrogate forbidden: {exc}") from exc
        elif t is bool or cur is None:
            continue
        else:
            raise ZoneBFuzzError("FORBIDDEN_JSON_TYPE", f"forbidden JSON value type: {t.__name__}")


def _no_dups_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ZoneBFuzzError("DUPLICATE_JSON_KEY", f"duplicate key: {k}")
        out[k] = v
    return out


def _forbid_float(token: str) -> Any:
    raise ZoneBFuzzError("FLOAT_FORBIDDEN", f"float literal forbidden: {token}")


def _forbid_constant(token: str) -> Any:
    raise ZoneBFuzzError("NONFINITE_CONSTANT", f"non-finite constant forbidden: {token}")


def _parse_capped_int_token(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_INT_DIGITS:
        raise ZoneBFuzzError("INT_DIGIT_LIMIT", f"integer token exceeds {MAX_INT_DIGITS} digits")
    val = int(token)
    blen = val.bit_length()
    if blen > MAX_INT_BITS:
        raise ZoneBFuzzError("INT_BIT_LIMIT", f"integer token bit_length={blen} exceeds {MAX_INT_BITS}")
    return val


def parse_strict_json(text: str) -> Any:
    if type(text) is not str:
        raise ZoneBFuzzError("INVALID_JSON_TEXT", "JSON text must be strict str")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ZoneBFuzzError("INVALID_UNICODE_STR", f"lone surrogate forbidden: {exc}") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ZoneBFuzzError("JSON_TOO_LARGE", f"JSON text exceeds {MAX_JSON_BYTES} bytes")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_no_dups_hook,
            parse_int=_parse_capped_int_token,
            parse_float=_forbid_float,
            parse_constant=_forbid_constant,
        )
    except ZoneBFuzzError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ZoneBFuzzError("JSON_DECODE_ERROR", f"invalid JSON: {exc}") from exc
    validate_json_tree_iterative(parsed)
    return parsed


def canonical_json_bytes(obj: Any) -> bytes:
    validate_json_tree_iterative(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def require_sha256_hex(val: Any, label: str) -> str:
    if type(val) is not str:
        raise ZoneBFuzzError("INVALID_DIGEST_TYPE", f"{label} must be strict str")
    if len(val) != 64:
        raise ZoneBFuzzError("INVALID_DIGEST_LEN", f"{label} must have length 64")
    if any(ch not in _HEX_LOWER for ch in val):
        raise ZoneBFuzzError("INVALID_DIGEST_HEX", f"{label} must be lowercase ASCII hex")
    return val


def _validate_path_obj(path: Any) -> str:
    if type(path) not in _EXACT_PATH_TYPES:
        raise ZoneBFuzzError("INVALID_PATH_TYPE", "path must be concrete pathlib.Path")
    raw_s = str(path)
    try:
        raw_s.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ZoneBFuzzError("INVALID_UNICODE_STR", f"lone surrogate in path: {exc}") from exc
    if "\x00" in raw_s:
        raise ZoneBFuzzError("INVALID_PATH_NUL", "NUL byte forbidden in path")
    return raw_s


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
        raise ZoneBFuzzError("INVALID_UNICODE_STR", f"lone surrogate in PWD: {exc}") from exc
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in Path(pwd).parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise ZoneBFuzzError("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink ancestor in PWD: {comp}") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
    finally:
        os.close(cur_fd)


def require_no_symlink_path(path: Path) -> None:
    _validate_path_obj(path)
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    if not parts:
        return
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise ZoneBFuzzError("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink ancestor forbidden: {comp}") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
        if _is_symlink_at(cur_fd, leaf):
            raise ZoneBFuzzError("SYMLINK_FORBIDDEN", f"symlink path forbidden: {path}")
    finally:
        os.close(cur_fd)


def _open_parent_dir_fd(
    path: Path,
    *,
    create_parents: bool = False,
    not_found_code: str = "FILE_NOT_FOUND",
) -> tuple[int, str]:
    _validate_path_obj(path)
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    if len(parts) == 0 or parts[-1] == "..":
        raise ZoneBFuzzError(not_found_code, "path must name a regular file")
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            if create_parents:
                try:
                    os.mkdir(comp, 0o700, dir_fd=cur_fd)
                except FileExistsError:
                    pass
                except OSError as exc:
                    raise ZoneBFuzzError("FILE_WRITE_ERROR", f"cannot create directory {comp}: {exc}") from exc
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise ZoneBFuzzError("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink ancestor forbidden: {comp}") from exc
                if exc.errno in (errno.ENOENT, errno.ENOTDIR):
                    raise ZoneBFuzzError(not_found_code, f"ancestor not found: {comp}") from exc
                raise ZoneBFuzzError("FILE_READ_ERROR", f"cannot open ancestor {comp}: {exc}") from exc
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, leaf
    except BaseException:
        os.close(cur_fd)
        raise


def _read_regular_bytes_atomic(
    path: Path,
    max_bytes: int,
    *,
    not_found_code: str = "FILE_NOT_FOUND",
    too_large_code: str = "FILE_TOO_LARGE",
) -> bytes:
    dfd, leaf = _open_parent_dir_fd(path, not_found_code=not_found_code)
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ZoneBFuzzError("SYMLINK_FORBIDDEN", f"symlink path forbidden: {leaf}") from exc
            if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.EISDIR):
                raise ZoneBFuzzError(not_found_code, f"regular file not found: {leaf}") from exc
            raise ZoneBFuzzError("FILE_READ_ERROR", f"cannot open file {leaf}: {exc}") from exc
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise ZoneBFuzzError(not_found_code, f"not a regular file: {leaf}")
            chunks: list[bytes] = []
            total = 0
            while True:
                try:
                    chunk = os.read(fd, _READ_CHUNK_BYTES)
                except OSError as exc:
                    raise ZoneBFuzzError("FILE_READ_ERROR", f"cannot read file {leaf}: {exc}") from exc
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ZoneBFuzzError(too_large_code, f"file exceeds {max_bytes} bytes")
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


# ---------------------------------------------------------------------------
# Hostile Python Subclass & Lying Container Fixtures (ZB11 / ZB12)
# ---------------------------------------------------------------------------

class LyingSequence(Sequence):
    """Sequence whose __len__ lies relative to yielded items."""

    def __init__(self, items: tuple[int, ...], fake_len: int) -> None:
        self._items = items
        self._fake_len = fake_len

    def __getitem__(self, idx: int) -> int:
        return self._items[idx]

    def __len__(self) -> int:
        return self._fake_len


class LyingMapping(Mapping):
    """Mapping subclass (non-dict) presenting certificate keys."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


class EvilDict(dict):
    pass


class EvilList(list):
    pass


class EvilInt(int):
    pass


class EvilStr(str):
    pass


# ---------------------------------------------------------------------------
# Traceback / Crash Classification & Payload Mutation Helpers
# ---------------------------------------------------------------------------

def detect_python_traceback(stderr_text: str, stdout_text: str = "") -> tuple[bool, str]:
    """Detect uncaught Python tracebacks or unhandled runtime errors in CLI output."""
    if type(stderr_text) is not str or type(stdout_text) is not str:
        raise ZoneBFuzzError("INVALID_STR", "stderr_text and stdout_text must be strict str")
    combined = stderr_text + "\n" + stdout_text
    if "Traceback (most recent call last):" in combined:
        lines = [ln.strip() for ln in combined.splitlines() if ln.strip()]
        return True, lines[-1]
    return False, ""


def _safe_exc_text(exc: BaseException, limit: int = 256) -> str:
    """Safely format an exception without letting huge-int args or lone surrogates crash the fuzzer."""
    try:
        text = str(exc)
    except BaseException:
        return "<unstringifiable>"
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        text = text.encode("utf-8", errors="replace").decode("utf-8")
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _safe_dumps(obj: Any, *, ensure_ascii: bool = True, indent: int | None = None) -> str:
    """Serialize JSON cleanly, catching 4,300-digit ValueError, TypeError, and RecursionError."""
    try:
        if indent is None:
            return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=ensure_ascii)
        return json.dumps(obj, sort_keys=True, indent=indent, ensure_ascii=ensure_ascii)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ZoneBFuzzError("SERIALIZE_ERROR", f"cannot serialize case: {_safe_exc_text(exc)}") from exc


def _resign_envelope(obj: dict[str, Any]) -> dict[str, Any]:
    """Recompute common payload_sha256 / certificate_sha256 fields if present."""
    out = copy.deepcopy(obj)
    if "payload" in out and "payload_sha256" in out:
        p_bytes = _safe_dumps(out["payload"], ensure_ascii=True).encode("utf-8")
        out["payload_sha256"] = hashlib.sha256(p_bytes).hexdigest()
    if "certificate_sha256" in out:
        env = {k: v for k, v in out.items() if k != "certificate_sha256"}
        e_bytes = _safe_dumps(env, ensure_ascii=True).encode("utf-8")
        out["certificate_sha256"] = hashlib.sha256(e_bytes).hexdigest()
    return out


def _flip_first_zero_or_one_int(obj: Any) -> tuple[Any, bool]:
    """Replace the first strict int 0 or 1 with False or True (1==True forgery)."""
    if type(obj) is dict:
        out: dict[str, Any] = {}
        flipped = False
        for k, v in obj.items():
            if not flipped:
                nv, flipped = _flip_first_zero_or_one_int(v)
                out[k] = nv
            else:
                out[k] = copy.deepcopy(v)
        return out, flipped
    if type(obj) is list:
        out_l: list[Any] = []
        flipped = False
        for item in obj:
            if not flipped:
                ni, flipped = _flip_first_zero_or_one_int(item)
                out_l.append(ni)
            else:
                out_l.append(copy.deepcopy(item))
        return out_l, flipped
    if type(obj) is int and obj in (0, 1):
        return bool(obj), True
    return copy.deepcopy(obj), False


def _replace_digest_strings(obj: Any, replacement: str) -> tuple[Any, bool]:
    """Replace top-level or nested *_sha256 digest string fields with `replacement`."""
    if type(obj) is dict:
        out: dict[str, Any] = {}
        changed = False
        for k, v in obj.items():
            if type(k) is str and k.endswith("_sha256") and type(v) is str:
                out[k] = replacement
                changed = True
            else:
                nv, c2 = _replace_digest_strings(v, replacement)
                out[k] = nv
                changed = changed or c2
        return out, changed
    if type(obj) is list:
        out_l: list[Any] = []
        changed = False
        for item in obj:
            ni, c2 = _replace_digest_strings(item, replacement)
            out_l.append(ni)
            changed = changed or c2
        return out_l, changed
    return copy.deepcopy(obj), False


def _make_bool_resigned_cert(valid_cert: dict[str, Any]) -> dict[str, Any]:
    target = copy.deepcopy(valid_cert)
    if "payload" in target:
        flipped_payload, did_flip = _flip_first_zero_or_one_int(target["payload"])
        if not did_flip and type(flipped_payload) is dict:
            flipped_payload["zb05_bool_forge"] = True
        target["payload"] = flipped_payload
    else:
        flipped_root, did_flip = _flip_first_zero_or_one_int(target)
        if not did_flip:
            flipped_root["zb05_bool_forge"] = True
        target = flipped_root
    return _resign_envelope(target)


def _make_hollow_resigned_cert(valid_cert: dict[str, Any]) -> dict[str, Any]:
    target = copy.deepcopy(valid_cert)
    if "payload" in target and type(target["payload"]) is dict:
        target["payload"] = {}
    else:
        for k in sorted(target.keys()):
            if k not in ("schema", "track_id", "audit_id", "study_id", "certificate_sha256", "payload_sha256"):
                target[k] = "HOLLOWED_BY_ZONE_B"
                break
    return _resign_envelope(target)


# ---------------------------------------------------------------------------
# CLI & In-Memory Fuzzing Engines
# ---------------------------------------------------------------------------

def build_cli_attack_cases(
    valid_cert_bytes: bytes,
    work_dir: Path,
) -> list[tuple[str, str, Path]]:
    """Materialize all CLI attack files inside `work_dir` and return (vector_id, subcase, path)."""
    if type(valid_cert_bytes) is not bytes:
        raise ZoneBFuzzError("INVALID_PAYLOAD_BYTES", "valid_cert_bytes must be strict bytes")
    require_no_symlink_path(work_dir)
    try:
        valid_obj = json.loads(valid_cert_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ZoneBFuzzError("BASELINE_CERT_INVALID", f"invalid baseline cert JSON: {_safe_exc_text(exc)}") from exc
    if type(valid_obj) is not dict:
        raise ZoneBFuzzError("BASELINE_CERT_NOT_DICT", "baseline certificate JSON must be an object")

    cases: list[tuple[str, str, Path]] = []

    def _emit_bytes(vid: str, sub: str, raw: bytes) -> None:
        p = work_dir / f"{vid}_{sub}.json"
        p.write_bytes(raw)
        cases.append((vid, sub, p))

    def _emit_text(vid: str, sub: str, txt: str) -> None:
        _emit_bytes(vid, sub, txt.encode("utf-8"))

    # ZB01: non-ASCII 64-char digest (triggers hmac.compare_digest TypeError if unguarded)
    zb01_obj, zb01_hit = _replace_digest_strings(valid_obj, "\u00e9" * 64)
    if not zb01_hit:
        zb01_obj["payload_sha256"] = "\u00e9" * 64
    _emit_text("ZB01_non_ascii_digest", "non_ascii_64", _safe_dumps(zb01_obj, ensure_ascii=False) + "\n")

    # ZB02: lone UTF-16 surrogate in digest string via raw \ud800 JSON escape
    zb02_marker = "__ZB02_SURROGATE_MARKER__"
    zb02_obj, zb02_hit = _replace_digest_strings(valid_obj, zb02_marker)
    if not zb02_hit:
        zb02_obj["payload_sha256"] = zb02_marker
    zb02_txt = _safe_dumps(zb02_obj, ensure_ascii=True).replace(
        zb02_marker, "\\ud800" * 64
    ) + "\n"
    _emit_text("ZB02_lone_surrogate_digest", "lone_surrogate_64", zb02_txt)

    # ZB03: 5,000-digit integer JSON literal (triggers Python 4,300-digit ValueError if uncaught)
    _emit_text("ZB03_huge_int_5000_digits", "json_5000_digits", '{"huge":' + ("9" * 5000) + "}\n")

    # ZB04: deep nesting (100-deep and 1,500-deep)
    _emit_text("ZB04_deep_nesting", "depth_100", ("[" * 100) + "0" + ("]" * 100) + "\n")
    _emit_text("ZB04_deep_nesting", "depth_1500", ("[" * 1500) + "0" + ("]" * 1500) + "\n")

    # ZB05: 1==True re-signed SHA forgery
    zb05_obj = _make_bool_resigned_cert(valid_obj)
    _emit_text("ZB05_bool_resigned_sha_forgery", "resigned_bool_int", _safe_dumps(zb05_obj, ensure_ascii=True) + "\n")

    # ZB06: raw bool-as-int injection (unsigned)
    zb06_obj, zb06_hit = _flip_first_zero_or_one_int(valid_obj)
    if not zb06_hit:
        zb06_obj["bool_as_int"] = True
    _emit_text("ZB06_bool_as_int_injection", "bool_as_int", _safe_dumps(zb06_obj, ensure_ascii=True) + "\n")

    # ZB07: duplicate key with \u-escape
    _emit_text("ZB07_duplicate_keys_unicode_escape", "dup_unicode_key", '{"schema":"a","\\u0073chema":"b"}\n')

    # ZB08: float literal, NaN, Infinity, -Infinity
    _emit_text("ZB08_nonfinite_and_float_literals", "float_lit", '{"val":1.5}\n')
    _emit_text("ZB08_nonfinite_and_float_literals", "nan_const", '{"val":NaN}\n')
    _emit_text("ZB08_nonfinite_and_float_literals", "inf_const", '{"val":Infinity}\n')
    _emit_text("ZB08_nonfinite_and_float_literals", "neginf_const", '{"val":-Infinity}\n')

    # ZB09: non-dict root (list and null)
    _emit_text("ZB09_non_dict_root", "list_root", "[]\n")
    _emit_text("ZB09_non_dict_root", "null_root", "null\n")

    # ZB10: CRLF line endings & non-canonical pretty-printed JSON
    _emit_bytes("ZB10_crlf_and_noncanonical_bytes", "crlf", valid_cert_bytes.replace(b"\n", b"\r\n"))
    _emit_text("ZB10_crlf_and_noncanonical_bytes", "pretty_noncanon", _safe_dumps(valid_obj, indent=2) + "\n")

    # ZB13: hollow re-signed self-consistent SHA payload
    zb13_obj = _make_hollow_resigned_cert(valid_obj)
    _emit_text("ZB13_hollow_resigned_payload", "hollow_resigned", _safe_dumps(zb13_obj, ensure_ascii=True) + "\n")

    # ZB14: symlink target & symlink ancestor pointing to valid certificate
    valid_copy_dir = work_dir / "real_cert_dir"
    valid_copy_dir.mkdir(mode=0o700)
    valid_copy = valid_copy_dir / "valid.json"
    valid_copy.write_bytes(valid_cert_bytes)

    sym_file = work_dir / "ZB14_symlink_file.json"
    sym_file.symlink_to(valid_copy)
    cases.append(("ZB14_symlink_target_and_ancestor", "symlink_file", sym_file))

    sym_dir = work_dir / "ZB14_symlink_dir"
    sym_dir.symlink_to(valid_copy_dir)
    cases.append(("ZB14_symlink_target_and_ancestor", "symlink_ancestor", sym_dir / "valid.json"))

    # ZB15: missing path & directory path
    cases.append(("ZB15_missing_and_directory_paths", "missing_file", work_dir / "does_not_exist.json"))
    cases.append(("ZB15_missing_and_directory_paths", "directory_path", valid_copy_dir))

    # ZB16: invalid UTF-8 bytes & truncated JSON
    _emit_bytes("ZB16_invalid_utf8_and_truncated_json", "invalid_utf8", b"\xff\xfe\x00\x80")
    _emit_bytes("ZB16_invalid_utf8_and_truncated_json", "truncated_json", b'{"schema":')

    return cases


def build_memory_attack_cases(valid_cert: dict[str, Any]) -> list[tuple[str, str, Any]]:
    """Construct all in-memory Zone-B attack objects for direct Python validator fuzzing."""
    if type(valid_cert) is not dict:
        raise ZoneBFuzzError("BASELINE_CERT_NOT_DICT", "valid_cert must be strict dict")

    cases: list[tuple[str, str, Any]] = []

    # ZB01: non-ASCII digest
    zb01_obj, zb01_hit = _replace_digest_strings(valid_cert, "\u00e9" * 64)
    if not zb01_hit:
        zb01_obj["payload_sha256"] = "\u00e9" * 64
    cases.append(("ZB01_non_ascii_digest", "non_ascii_64", zb01_obj))

    # ZB02: lone surrogate in digest & dict key
    zb02_obj, zb02_hit = _replace_digest_strings(valid_cert, "\ud800" * 64)
    if not zb02_hit:
        zb02_obj["payload_sha256"] = "\ud800" * 64
    cases.append(("ZB02_lone_surrogate_digest", "lone_surrogate_64", zb02_obj))
    cases.append(("ZB02_lone_surrogate_digest", "lone_surrogate_key", {"\ud800": 1}))

    # ZB03: in-memory 5,000-digit int (10**5000)
    zb03_obj = copy.deepcopy(valid_cert)
    if "payload" in zb03_obj and type(zb03_obj["payload"]) is dict:
        zb03_obj["payload"]["zb03_huge"] = 10 ** 5000
    else:
        zb03_obj["zb03_huge"] = 10 ** 5000
    cases.append(("ZB03_huge_int_5000_digits", "mem_10_pow_5000", zb03_obj))

    # ZB04: 1,500-deep nested Python list (triggers RecursionError on recursive walkers)
    deep: list[Any] = []
    cur = deep
    for _ in range(1500):
        nxt: list[Any] = []
        cur.append(nxt)
        cur = nxt
    zb04_obj = copy.deepcopy(valid_cert)
    if "payload" in zb04_obj and type(zb04_obj["payload"]) is dict:
        zb04_obj["payload"]["zb04_deep"] = deep
    else:
        zb04_obj["zb04_deep"] = deep
    cases.append(("ZB04_deep_nesting", "mem_depth_1500", zb04_obj))

    # ZB05: 1==True re-signed SHA forgery
    cases.append(("ZB05_bool_resigned_sha_forgery", "resigned_bool_int", _make_bool_resigned_cert(valid_cert)))

    # ZB06: bool-as-int injection
    zb06_obj, zb06_hit = _flip_first_zero_or_one_int(valid_cert)
    if not zb06_hit:
        zb06_obj["bool_as_int"] = True
    cases.append(("ZB06_bool_as_int_injection", "bool_as_int", zb06_obj))

    # ZB08: float & NaN in-memory (hostile attack fixture generation only; zero AST float/float() calls)
    for sub, fval in (
        ("float_val", json.loads("1.5")),
        ("nan_val", json.loads("NaN")),
        ("inf_val", json.loads("Infinity")),
    ):
        zb08_obj = copy.deepcopy(valid_cert)
        if "payload" in zb08_obj and type(zb08_obj["payload"]) is dict:
            zb08_obj["payload"]["zb08_float"] = fval
        else:
            zb08_obj["zb08_float"] = fval
        cases.append(("ZB08_nonfinite_and_float_literals", sub, zb08_obj))

    # ZB09: non-dict root
    cases.append(("ZB09_non_dict_root", "list_root", []))
    cases.append(("ZB09_non_dict_root", "none_root", None))

    # ZB11: lying Sequence container
    zb11_obj = copy.deepcopy(valid_cert)
    if "payload" in zb11_obj and type(zb11_obj["payload"]) is dict:
        zb11_obj["payload"]["zb11_lying_seq"] = LyingSequence((1, 2, 3, 4, 5, 6, 7, 8, 9), 8)
    else:
        zb11_obj["zb11_lying_seq"] = LyingSequence((1, 2, 3, 4, 5, 6, 7, 8, 9), 8)
    cases.append(("ZB11_lying_sequence_container", "lying_seq_8_vs_9", zb11_obj))

    # ZB12: hostile Mapping & dict/list/int/str subclasses
    cases.append(("ZB12_hostile_mapping_and_subclasses", "lying_mapping_root", LyingMapping(copy.deepcopy(valid_cert))))
    cases.append(("ZB12_hostile_mapping_and_subclasses", "evil_dict_root", EvilDict(copy.deepcopy(valid_cert))))
    zb12_sub = copy.deepcopy(valid_cert)
    if "payload" in zb12_sub and type(zb12_sub["payload"]) is dict:
        zb12_sub["payload"]["zb12_evil_int"] = EvilInt(1)
        zb12_sub["payload"]["zb12_evil_str"] = EvilStr("x")
        zb12_sub["payload"]["zb12_evil_list"] = EvilList([1])
    else:
        zb12_sub["zb12_evil_int"] = EvilInt(1)
    cases.append(("ZB12_hostile_mapping_and_subclasses", "evil_leaf_subclasses", zb12_sub))
    cases.append(("ZB12_hostile_mapping_and_subclasses", "non_str_dict_key", {1: "int_key", "schema": "x"}))

    # ZB13: hollow re-signed payload
    cases.append(("ZB13_hollow_resigned_payload", "hollow_resigned", _make_hollow_resigned_cert(valid_cert)))

    return cases


def fuzz_cli_checker(
    script_path: Path,
    cert_path: Path,
    *,
    check_flag: str = "--check",
    timeout_sec: int = 30,
) -> dict[str, Any]:
    """Run baseline check + full CLI Zone-B corpus against an external `--check` CLI."""
    _read_regular_bytes_atomic(script_path, MAX_JSON_BYTES, not_found_code="SCRIPT_NOT_FOUND")
    valid_bytes = _read_regular_bytes_atomic(
        cert_path,
        MAX_JSON_BYTES,
        not_found_code="CERT_NOT_FOUND",
        too_large_code="CERT_FILE_TOO_LARGE",
    )
    if type(check_flag) is not str or not check_flag.strip():
        raise ZoneBFuzzError("INVALID_CHECK_FLAG", "check_flag must be non-empty str")
    t_sec = require_exact_int(timeout_sec, "timeout_sec", min_val=1, max_val=300)

    def _run(target_cert: Path) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-I", "-O", "-B", "-W", "error", str(script_path), check_flag, str(target_cert)]
        return subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=t_sec, check=False)

    try:
        base = _run(cert_path)
    except subprocess.TimeoutExpired:
        return {
            "surface": "cli",
            "baseline_ok": False,
            "passed": False,
            "status": "BASELINE_FAILED",
            "baseline_rc": -1,
            "cases_run": 0,
            "clean_rejections": 0,
            "bypasses": 0,
            "crashes": 0,
            "findings": [],
        }
    if base.returncode != 0:
        return {
            "surface": "cli",
            "baseline_ok": False,
            "passed": False,
            "status": "BASELINE_FAILED",
            "baseline_rc": base.returncode,
            "cases_run": 0,
            "clean_rejections": 0,
            "bypasses": 0,
            "crashes": 0,
            "findings": [],
        }

    results: list[dict[str, Any]] = []
    clean_count = 0
    bypass_count = 0
    crash_count = 0
    findings: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="aletheia_zb_") as td:
        work_dir = Path(td)
        cases = build_cli_attack_cases(valid_bytes, work_dir)
        for vid, sub, attack_path in cases:
            try:
                proc = _run(attack_path)
            except subprocess.TimeoutExpired:
                crash_count += 1
                rec = {
                    "vector_id": vid,
                    "subcase": sub,
                    "outcome": "CRASH",
                    "returncode": -1,
                    "traceback_tail": "TIMEOUT",
                }
                results.append(rec)
                findings.append(rec)
                continue
            has_tb, tb_tail = detect_python_traceback(proc.stderr, proc.stdout)
            if proc.returncode == 0:
                outcome = "BYPASS"
                bypass_count += 1
            elif proc.returncode < 0:
                outcome = "CRASH"
                if not tb_tail:
                    tb_tail = f"SIGNAL:{-proc.returncode}"
                crash_count += 1
            elif has_tb:
                outcome = "CRASH"
                crash_count += 1
            else:
                outcome = "REJECTED_CLEAN"
                clean_count += 1
            rec = {
                "vector_id": vid,
                "subcase": sub,
                "outcome": outcome,
                "returncode": proc.returncode,
                "traceback_tail": tb_tail,
            }
            results.append(rec)
            if outcome != "REJECTED_CLEAN":
                findings.append(rec)

    passed = bypass_count == 0 and crash_count == 0
    return {
        "surface": "cli",
        "baseline_ok": True,
        "passed": passed,
        "status": "PASS" if passed else "FAIL",
        "baseline_rc": 0,
        "cases_run": len(results),
        "clean_rejections": clean_count,
        "bypasses": bypass_count,
        "crashes": crash_count,
        "findings": findings,
    }


def _masked_valueerror_crash_detail(
    exc: BaseException,
    expected_exc_types: tuple[type[BaseException], ...],
) -> str:
    """Detect UnicodeError, JSONDecodeError, or raw 4,300-digit ValueError masquerading under ValueError."""
    if isinstance(exc, UnicodeError):
        if not any(issubclass(t, UnicodeError) for t in expected_exc_types):
            return f"masked_unicode_error:{type(exc).__name__}: {_safe_exc_text(exc)}"
        return ""
    if isinstance(exc, json.JSONDecodeError):
        if not any(issubclass(t, json.JSONDecodeError) for t in expected_exc_types):
            return f"masked_json_decode_error: {_safe_exc_text(exc)}"
        return ""
    msg = _safe_exc_text(exc)
    if type(exc) is ValueError and "Exceeds the limit" in msg:
        return f"raw_int_digit_limit: {msg}"
    return ""


def fuzz_python_validator(
    validator_fn: Callable[[Any], Any],
    valid_cert: dict[str, Any],
    *,
    expected_exc_types: tuple[type[BaseException], ...] = (ValueError,),
) -> dict[str, Any]:
    """Run baseline check + full in-memory Zone-B corpus against a Python validator callable."""
    if not callable(validator_fn):
        raise ZoneBFuzzError("INVALID_VALIDATOR", "validator_fn must be callable")
    if type(expected_exc_types) is not tuple or len(expected_exc_types) == 0:
        raise ZoneBFuzzError("INVALID_EXC_TYPES", "expected_exc_types must be non-empty tuple of exception types")
    for exc_t in expected_exc_types:
        if not (isinstance(exc_t, type) and issubclass(exc_t, BaseException)):
            raise ZoneBFuzzError("INVALID_EXC_TYPES", "each entry in expected_exc_types must be an exception class")

    try:
        validator_fn(copy.deepcopy(valid_cert))
    except Exception as exc:
        return {
            "surface": "memory",
            "baseline_ok": False,
            "passed": False,
            "status": "BASELINE_FAILED",
            "baseline_error": f"{type(exc).__name__}: {_safe_exc_text(exc)}",
            "cases_run": 0,
            "clean_rejections": 0,
            "bypasses": 0,
            "crashes": 0,
            "findings": [],
        }

    cases = build_memory_attack_cases(valid_cert)
    clean_count = 0
    bypass_count = 0
    crash_count = 0
    findings: list[dict[str, Any]] = []

    for vid, sub, payload_obj in cases:
        outcome = "BYPASS"
        exc_info = ""
        try:
            validator_fn(payload_obj)
            bypass_count += 1
        except (KeyboardInterrupt, SystemExit):
            raise
        except expected_exc_types as exc:
            crash_detail = _masked_valueerror_crash_detail(exc, expected_exc_types)
            if crash_detail:
                outcome = "CRASH"
                exc_info = crash_detail
                crash_count += 1
            else:
                outcome = "REJECTED_CLEAN"
                exc_info = type(exc).__name__
                clean_count += 1
        except BaseException as exc:
            outcome = "CRASH"
            exc_info = f"{type(exc).__name__}: {_safe_exc_text(exc)}"
            crash_count += 1
        if outcome != "REJECTED_CLEAN":
            findings.append({
                "vector_id": vid,
                "subcase": sub,
                "outcome": outcome,
                "detail": exc_info,
            })

    passed = bypass_count == 0 and crash_count == 0
    return {
        "surface": "memory",
        "baseline_ok": True,
        "passed": passed,
        "status": "PASS" if passed else "FAIL",
        "cases_run": len(cases),
        "clean_rejections": clean_count,
        "bypasses": bypass_count,
        "crashes": crash_count,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Self-Contained Hardened Reference Checker + 7 Deliberate Vulnerable Foils
# ---------------------------------------------------------------------------

def build_reference_cert() -> dict[str, Any]:
    payload = {
        "exact_count": 1,
        "zero_flag": 0,
        "vectors_defined": len(CORPUS_VECTORS),
        "all_passed": True,
    }
    p_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    env = {"schema": _REF_SCHEMA, "payload_sha256": p_sha, "payload": payload}
    c_sha = hashlib.sha256(canonical_json_bytes(env)).hexdigest()
    return {
        "schema": _REF_SCHEMA,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": payload,
    }


def reference_verify_dict(cert: Any) -> dict[str, Any]:
    """Hardened reference validator passing all 16/16 Zone-B corpus vectors."""
    validate_json_tree_iterative(cert)
    if type(cert) is not dict:
        raise ZoneBFuzzError("REF_NOT_DICT", "reference cert must be strict dict")
    if set(cert.keys()) != _REF_KEYS:
        raise ZoneBFuzzError("REF_KEYS_MISMATCH", "unexpected reference cert keys")
    if cert["schema"] != _REF_SCHEMA:
        raise ZoneBFuzzError("REF_SCHEMA_MISMATCH", "reference schema mismatch")
    p_sha = require_sha256_hex(cert["payload_sha256"], "payload_sha256")
    c_sha = require_sha256_hex(cert["certificate_sha256"], "certificate_sha256")
    comp_p = hashlib.sha256(canonical_json_bytes(cert["payload"])).hexdigest()
    if not hmac.compare_digest(p_sha, comp_p):
        raise ZoneBFuzzError("REF_PAYLOAD_SHA_MISMATCH", "payload sha mismatch")
    env = {"schema": cert["schema"], "payload_sha256": p_sha, "payload": cert["payload"]}
    comp_c = hashlib.sha256(canonical_json_bytes(env)).hexdigest()
    if not hmac.compare_digest(c_sha, comp_c):
        raise ZoneBFuzzError("REF_CERT_SHA_MISMATCH", "cert sha mismatch")
    expected = build_reference_cert()
    if not hmac.compare_digest(comp_p, expected["payload_sha256"]):
        raise ZoneBFuzzError("REF_RECOMPUTED_DRIFT", "payload differs from canonical recomputation")
    return {"valid": True, "payload_sha256": comp_p, "certificate_sha256": comp_c}


def reference_check_file(path: Path) -> dict[str, Any]:
    raw = _read_regular_bytes_atomic(
        path,
        MAX_JSON_BYTES,
        not_found_code="REF_FILE_NOT_FOUND",
        too_large_code="REF_FILE_TOO_LARGE",
    )
    if b"\r" in raw:
        raise ZoneBFuzzError("REF_CRLF_FORBIDDEN", "CR/CRLF forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ZoneBFuzzError("REF_INVALID_UTF8", f"invalid utf-8: {exc}") from exc
    parsed = parse_strict_json(text)
    canon = canonical_json_bytes(parsed)
    if raw not in (canon, canon + b"\n"):
        raise ZoneBFuzzError("REF_NON_CANONICAL", "non-canonical JSON bytes")
    return reference_verify_dict(parsed)


def _foil_naive_compare_digest(cert: Any) -> dict[str, Any]:
    """Vulnerable foil 1: calls hmac.compare_digest without ASCII hex validation (crashes on ZB01)."""
    if type(cert) is not dict or set(cert.keys()) != _REF_KEYS:
        raise ZoneBFuzzError("FOIL_SCHEMA", "bad schema")
    expected = build_reference_cert()
    if not hmac.compare_digest(cert["payload_sha256"], expected["payload_sha256"]):
        raise ZoneBFuzzError("FOIL_SHA", "sha mismatch")
    return {"valid": True}


def _foil_recursive_walker(cert: Any) -> dict[str, Any]:
    """Vulnerable foil 2: unbounded recursion on nested lists (crashes with RecursionError on ZB04)."""
    def _walk(x: Any) -> None:
        if isinstance(x, dict):
            for v in x.values():
                _walk(v)
        elif isinstance(x, list):
            for item in x:
                _walk(item)
    _walk(cert)
    return reference_verify_dict(cert)


def _foil_bool_eq_and_isinstance(cert: Any) -> dict[str, Any]:
    """Vulnerable foil 3: uses isinstance + Python `==` (accepts 1==True ZB05 & EvilDict ZB12)."""
    if not isinstance(cert, Mapping) or set(cert.keys()) != _REF_KEYS:
        raise ZoneBFuzzError("FOIL_SCHEMA", "bad schema")
    expected = build_reference_cert()
    if cert["payload"] != expected["payload"]:
        raise ZoneBFuzzError("FOIL_PAYLOAD", "payload mismatch")
    return {"valid": True}


def _foil_hash_only_no_recompute(cert: Any) -> dict[str, Any]:
    """Vulnerable foil 4: verifies internal SHA consistency without oracle recomputation (accepts ZB13)."""
    validate_json_tree_iterative(cert)
    if type(cert) is not dict or set(cert.keys()) != _REF_KEYS:
        raise ZoneBFuzzError("FOIL_SCHEMA", "bad schema")
    p_sha = require_sha256_hex(cert["payload_sha256"], "payload_sha256")
    c_sha = require_sha256_hex(cert["certificate_sha256"], "certificate_sha256")
    comp_p = hashlib.sha256(canonical_json_bytes(cert["payload"])).hexdigest()
    env = {"schema": cert["schema"], "payload_sha256": p_sha, "payload": cert["payload"]}
    comp_c = hashlib.sha256(canonical_json_bytes(env)).hexdigest()
    if not (hmac.compare_digest(p_sha, comp_p) and hmac.compare_digest(c_sha, comp_c)):
        raise ZoneBFuzzError("FOIL_SHA", "internal sha mismatch")
    return {"valid": True}


def _foil_broken_baseline(cert: Any) -> dict[str, Any]:
    """Vulnerable foil 5: always rejects even valid baseline certificate."""
    raise ZoneBFuzzError("ALWAYS_FAIL", "broken baseline")


def _foil_raw_int_digit_limit(cert: Any) -> dict[str, Any]:
    """Vulnerable foil 6: calls json.dumps without integer bit-length cap (crashes on ZB03)."""
    json.dumps(cert)
    return reference_verify_dict(cert)


def _foil_unhandled_surrogate_utf8(cert: Any) -> dict[str, Any]:
    """Vulnerable foil 7: encodes digest as UTF-8 without surrogate check (crashes on ZB02)."""
    if type(cert) is dict and type(cert.get("payload_sha256")) is str:
        cert["payload_sha256"].encode("utf-8")
    return reference_verify_dict(cert)


def build_self_certification_payload() -> dict[str, Any]:
    """Run all 16 corpus vectors against hardened reference (CLI + memory) and vulnerable foils."""
    ref_cert = build_reference_cert()
    mem_hardened = fuzz_python_validator(
        reference_verify_dict,
        ref_cert,
        expected_exc_types=(ZoneBFuzzError,),
    )

    with tempfile.TemporaryDirectory(prefix="aletheia_zb_self_") as td:
        ref_path = Path(td) / "ref_cert.json"
        ref_path.write_bytes(canonical_json_bytes(ref_cert) + b"\n")
        cli_hardened = fuzz_cli_checker(
            Path(__file__).resolve(),
            ref_path,
            check_flag="--ref-check",
        )

    foil_compare = fuzz_python_validator(_foil_naive_compare_digest, ref_cert, expected_exc_types=(ZoneBFuzzError,))
    foil_recurse = fuzz_python_validator(_foil_recursive_walker, ref_cert, expected_exc_types=(ZoneBFuzzError,))
    foil_bool_sub = fuzz_python_validator(_foil_bool_eq_and_isinstance, ref_cert, expected_exc_types=(ZoneBFuzzError,))
    foil_hollow = fuzz_python_validator(_foil_hash_only_no_recompute, ref_cert, expected_exc_types=(ZoneBFuzzError,))
    foil_broken = fuzz_python_validator(_foil_broken_baseline, ref_cert, expected_exc_types=(ZoneBFuzzError,))
    foil_int_limit = fuzz_python_validator(_foil_raw_int_digit_limit, ref_cert, expected_exc_types=(ValueError,))
    foil_surrogate = fuzz_python_validator(_foil_unhandled_surrogate_utf8, ref_cert, expected_exc_types=(ValueError,))

    def _finding_ids(rep: dict[str, Any], outcome: str) -> list[str]:
        return sorted({f["vector_id"] for f in rep["findings"] if f["outcome"] == outcome})

    checks = {
        "corpus_has_16_vectors": len(CORPUS_VECTORS) == 16,
        "hardened_cli_passes_zero_findings": cli_hardened["passed"] is True and cli_hardened["clean_rejections"] == cli_hardened["cases_run"],
        "hardened_memory_passes_zero_findings": mem_hardened["passed"] is True and mem_hardened["clean_rejections"] == mem_hardened["cases_run"],
        "foil_compare_digest_caught_crash_zb01": "ZB01_non_ascii_digest" in _finding_ids(foil_compare, "CRASH"),
        "foil_recursive_caught_crash_zb04": "ZB04_deep_nesting" in _finding_ids(foil_recurse, "CRASH"),
        "foil_bool_eq_caught_bypass_zb05_zb12": (
            "ZB05_bool_resigned_sha_forgery" in _finding_ids(foil_bool_sub, "BYPASS")
            and "ZB12_hostile_mapping_and_subclasses" in _finding_ids(foil_bool_sub, "BYPASS")
        ),
        "foil_hash_only_caught_bypass_zb13": "ZB13_hollow_resigned_payload" in _finding_ids(foil_hollow, "BYPASS"),
        "foil_broken_baseline_caught": foil_broken["status"] == "BASELINE_FAILED",
        "foil_raw_int_limit_caught_crash_zb03": "ZB03_huge_int_5000_digits" in _finding_ids(foil_int_limit, "CRASH"),
        "foil_surrogate_utf8_caught_crash_zb02": "ZB02_lone_surrogate_digest" in _finding_ids(foil_surrogate, "CRASH"),
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise ZoneBFuzzError("SELF_CERT_FAILED", f"failed checks: {failed}")

    return {
        "track_id": CERT_TRACK_ID,
        "corpus_vector_count": len(CORPUS_VECTORS),
        "corpus_vector_ids": [v["id"] for v in CORPUS_VECTORS],
        "hardened_reference_cli": {
            "status": cli_hardened["status"],
            "cases_run": cli_hardened["cases_run"],
            "clean_rejections": cli_hardened["clean_rejections"],
            "bypasses": cli_hardened["bypasses"],
            "crashes": cli_hardened["crashes"],
        },
        "hardened_reference_memory": {
            "status": mem_hardened["status"],
            "cases_run": mem_hardened["cases_run"],
            "clean_rejections": mem_hardened["clean_rejections"],
            "bypasses": mem_hardened["bypasses"],
            "crashes": mem_hardened["crashes"],
        },
        "must_catch_foils": {
            "naive_compare_digest_crash_vectors": _finding_ids(foil_compare, "CRASH"),
            "recursive_walker_crash_vectors": _finding_ids(foil_recurse, "CRASH"),
            "bool_eq_isinstance_bypass_vectors": _finding_ids(foil_bool_sub, "BYPASS"),
            "hash_only_bypass_vectors": _finding_ids(foil_hollow, "BYPASS"),
            "broken_baseline_status": foil_broken["status"],
            "raw_int_digit_limit_crash_vectors": _finding_ids(foil_int_limit, "CRASH"),
            "unhandled_surrogate_utf8_crash_vectors": _finding_ids(foil_surrogate, "CRASH"),
        },
        "invariant_checks": checks,
        "all_passed": True,
    }


def build_certificate() -> dict[str, Any]:
    payload = build_self_certification_payload()
    payload_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    envelope = {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha256,
        "payload": payload,
    }
    certificate_sha256 = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    return {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha256,
        "certificate_sha256": certificate_sha256,
        "payload": payload,
    }


def verify_certificate_dict(cert: Any) -> dict[str, Any]:
    validate_json_tree_iterative(cert)
    if type(cert) is not dict:
        raise ZoneBFuzzError("CERT_NOT_DICT", "certificate root must be strict dict")
    if set(cert.keys()) != _CERT_KEYS:
        raise ZoneBFuzzError("CERT_SCHEMA_KEYS", f"unexpected keys: {sorted(cert.keys())}")
    if cert["schema"] != CERT_SCHEMA:
        raise ZoneBFuzzError("CERT_SCHEMA_MISMATCH", "schema mismatch")
    if cert["track_id"] != CERT_TRACK_ID:
        raise ZoneBFuzzError("CERT_TRACK_ID_MISMATCH", "track_id mismatch")
    stored_p = require_sha256_hex(cert["payload_sha256"], "payload_sha256")
    stored_c = require_sha256_hex(cert["certificate_sha256"], "certificate_sha256")
    comp_p = hashlib.sha256(canonical_json_bytes(cert["payload"])).hexdigest()
    if not hmac.compare_digest(stored_p, comp_p):
        raise ZoneBFuzzError("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")
    env = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": stored_p,
        "payload": cert["payload"],
    }
    comp_c = hashlib.sha256(canonical_json_bytes(env)).hexdigest()
    if not hmac.compare_digest(stored_c, comp_c):
        raise ZoneBFuzzError("CERTIFICATE_SHA_MISMATCH", "certificate_sha256 mismatch")
    expected = build_certificate()
    if not hmac.compare_digest(comp_p, expected["payload_sha256"]):
        raise ZoneBFuzzError("RECOMPUTED_PAYLOAD_DRIFT", "payload digest differs from recomputation")
    return {"valid": True, "track_id": CERT_TRACK_ID, "payload_sha256": comp_p, "certificate_sha256": comp_c}


def check_certificate_file(path: Path) -> dict[str, Any]:
    raw = _read_regular_bytes_atomic(
        path,
        MAX_JSON_BYTES,
        not_found_code="CERT_FILE_NOT_FOUND",
        too_large_code="CERT_FILE_TOO_LARGE",
    )
    if b"\r" in raw:
        raise ZoneBFuzzError("CRLF_FORBIDDEN", "CR/CRLF forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ZoneBFuzzError("INVALID_UTF8", f"invalid UTF-8: {exc}") from exc
    parsed = parse_strict_json(text)
    canon = canonical_json_bytes(parsed)
    if raw not in (canon, canon + b"\n"):
        raise ZoneBFuzzError("NON_CANONICAL_CERT_BYTES", "certificate file is not canonical JSON")
    return verify_certificate_dict(parsed)


def _atomic_write_bytes_0600(path: Path, raw: bytes) -> None:
    """Atomic 0o600 dir_fd write: strict bytes + atomic ancestor dir_fd + lstat target + CSPRNG O_EXCL temp + fsync + pre-replace nlink==1 + os.replace + dir fsync."""
    if type(raw) is not bytes:
        raise ZoneBFuzzError("INVALID_PAYLOAD_BYTES", "raw payload must be strict bytes")
    dfd, leaf = _open_parent_dir_fd(path, create_parents=True, not_found_code="NOT_REGULAR_FILE")
    tmp_name: str | None = None
    try:
        try:
            st_ex = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_ex = None
        if st_ex is not None:
            if stat.S_ISLNK(st_ex.st_mode):
                raise ZoneBFuzzError("SYMLINK_FORBIDDEN", "symlink target path forbidden")
            if not stat.S_ISREG(st_ex.st_mode):
                raise ZoneBFuzzError("NOT_REGULAR_FILE", "target path is not a regular file")
            if st_ex.st_nlink > 1:
                raise ZoneBFuzzError("HARDLINK_FORBIDDEN", "hardlinked target path forbidden")
        pid = os.getpid()
        for _ in range(64):
            with _TEMP_NAME_LOCK:
                cand = f".zb.{pid}.{secrets.token_hex(8)}.tmp"
            try:
                fd = os.open(
                    cand,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                    0o600,
                    dir_fd=dfd,
                )
                tmp_name = cand
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise ZoneBFuzzError("FILE_WRITE_ERROR", f"cannot create temp file: {exc}") from exc
        else:
            raise ZoneBFuzzError("TEMP_SLOT_EXHAUSTED", "exhausted temp file slots")
        try:
            view = memoryview(raw)
            written = 0
            while written < len(view):
                written += os.write(fd, view[written:])
            os.fsync(fd)
            if os.fstat(fd).st_nlink != 1:
                raise ZoneBFuzzError("HARDLINK_FORBIDDEN", "temp file link count altered")
        finally:
            os.close(fd)
        os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
        tmp_name = None
        os.fsync(dfd)
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


def write_certificate_file(path: Path) -> dict[str, Any]:
    require_no_symlink_path(path)
    cert = build_certificate()
    raw = canonical_json_bytes(cert) + b"\n"
    _atomic_write_bytes_0600(path, raw)
    return check_certificate_file(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aletheia v2.1 — Reusable 16-Vector Zone-B Adversarial Fuzzer")
    parser.add_argument("--self-test", "--standalone", dest="standalone", action="store_true", help="Run standalone self-certification")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON output")
    parser.add_argument("--write", type=str, help="Write canonical self-cert JSON to an explicit path")
    parser.add_argument("--check", type=str, help="Fail-closed verification of a self-cert JSON file")
    parser.add_argument("--ref-check", type=str, help="Internal hardened reference checker target for self-fuzzing")
    parser.add_argument("--target-cli", type=str, help="Path to external `--check` CLI script to fuzz")
    parser.add_argument("--cert", type=str, help="Path to valid baseline certificate JSON for `--target-cli`")
    parser.add_argument("--check-flag", type=str, default="--check", help="CLI flag used by `--target-cli` (default: --check)")
    args = parser.parse_args(argv)

    try:
        if args.ref_check is not None:
            res = reference_check_file(Path(args.ref_check))
            print(f"OK REF payload_sha256={res['payload_sha256']} certificate_sha256={res['certificate_sha256']}")
            return 0
        if args.target_cli is not None:
            if args.cert is None:
                raise ZoneBFuzzError("MISSING_CERT_ARG", "--target-cli requires --cert <path>")
            rep = fuzz_cli_checker(Path(args.target_cli), Path(args.cert), check_flag=args.check_flag)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(rep) + b"\n")
            else:
                print(
                    f"{rep['status']} target_cli cases={rep['cases_run']} "
                    f"clean={rep['clean_rejections']} bypasses={rep['bypasses']} crashes={rep['crashes']}"
                )
            return 0 if rep["passed"] else 1
        if args.check is not None:
            res = check_certificate_file(Path(args.check))
            print(f"OK {CERT_TRACK_ID} payload_sha256={res['payload_sha256']} certificate_sha256={res['certificate_sha256']}")
            return 0
        if args.write is not None:
            res = write_certificate_file(Path(args.write))
            print(f"WROTE {CERT_TRACK_ID} payload_sha256={res['payload_sha256']} certificate_sha256={res['certificate_sha256']}")
            return 0
        cert = build_certificate()
        if args.json:
            sys.stdout.buffer.write(canonical_json_bytes(cert) + b"\n")
            return 0
        print(
            f"OK {CERT_TRACK_ID} payload_sha256={cert['payload_sha256']} "
            f"certificate_sha256={cert['certificate_sha256']} all_passed={cert['payload']['all_passed']}"
        )
        return 0
    except (ZoneBFuzzError, ValueError, RecursionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"REJECT {_safe_exc_text(exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
