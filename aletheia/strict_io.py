"""
R1/R2/R3-clean strict JSON, validation, hashing, and hygiene pattern primitives.

Zero bare asserts (100% python3 -O parity). Leak patterns are assembled programmatically
so this module never contains literal personal path or secret tokens.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


class AletheiaError(ValueError):
    """Explicit structured validation error (never stripped by python3 -O)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    """Explicit non-assert guard for all TCB / verification paths."""
    if not cond:
        raise AletheiaError(code, message)


def canonical_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_no_lone_surrogates(value: Any) -> None:
    """Reject lone surrogates in any parsed string (they crash later UTF-8 encodes)."""
    if isinstance(value, str):
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            raise AletheiaError("JSON_LONE_SURROGATE", "lone surrogate in JSON string")
    elif isinstance(value, dict):
        for key, item in value.items():
            _require_no_lone_surrogates(key)
            _require_no_lone_surrogates(item)
    elif isinstance(value, list):
        for item in value:
            _require_no_lone_surrogates(item)


def parse_strict_json_text(
    raw_text: str,
    *,
    allow_float: bool = True,
    require_object: bool = True,
) -> Any:
    """
    R1/R3 strict JSON parser:
      - Rejects empty/blank strings
      - Rejects duplicate keys anywhere in the JSON tree
      - Rejects NaN, Infinity, -Infinity, including respelled overflow such as 1e999
      - Rejects lone surrogates in strings
      - Optionally rejects floats (allow_float=False)
      - Optionally requires top-level JSON object (dict).
    """
    if not isinstance(raw_text, str) or len(raw_text.strip()) == 0:
        raise AletheiaError("EMPTY_JSON_INPUT", "JSON text must be non-empty")

    def reject_constant(s: str) -> Any:
        raise AletheiaError("JSON_CONSTANT_FORBIDDEN", f"non-standard JSON constant forbidden: {s!r}")

    def reject_float(s: str) -> Any:
        raise AletheiaError("JSON_FLOAT_FORBIDDEN", f"float literal forbidden in exact JSON: {s!r}")

    def finite_float(s: str) -> float:
        value = float(s)
        if not math.isfinite(value):
            raise AletheiaError("JSON_FLOAT_NOT_FINITE", f"non-finite float literal forbidden: {s!r}")
        return value

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise AletheiaError("JSON_DUPLICATE_KEY", f"duplicate JSON key: {k!r}")
            out[k] = v
        return out

    kwargs: dict[str, Any] = {
        "parse_constant": reject_constant,
        "object_pairs_hook": reject_duplicate_keys,
    }
    if not allow_float:
        kwargs["parse_float"] = reject_float
    else:
        kwargs["parse_float"] = finite_float

    try:
        obj = json.loads(raw_text, **kwargs)
    except AletheiaError:
        raise
    except Exception as exc:
        raise AletheiaError("JSON_SYNTAX_ERROR", str(exc)) from exc

    _require_no_lone_surrogates(obj)

    if require_object and not isinstance(obj, dict):
        raise AletheiaError("JSON_ROOT_NOT_OBJECT", "top-level JSON payload must be an object")
    return obj


def loads_strict_json(
    raw_text: str,
    *,
    allow_float: bool = True,
    require_object: bool = False,
) -> Any:
    """
    Drop-in strict JSON loader (v1.4, reverse-extracted from warp-drive `server.py` & `WD-LEDGER-01`):
      - Rejects duplicate keys at EVERY nesting depth via `object_pairs_hook`
      - Rejects non-RFC-8259 `NaN`, `Infinity`, `-Infinity` via `parse_constant`
      - Optionally rejects floats (`allow_float=False`) and non-object roots (`require_object=True`).
    """
    return parse_strict_json_text(raw_text, allow_float=allow_float, require_object=require_object)


def load_strict_json_file(
    path: Path,
    *,
    allow_float: bool = True,
    require_object: bool = True,
) -> Any:
    require_ok(path.is_file(), "FILE_NOT_FOUND", f"JSON file not found: {path}")
    raw = path.read_bytes()
    require_ok(b"\r\n" not in raw, "CRLF_LINE_ENDINGS", f"CRLF line endings detected in {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AletheiaError("INVALID_UTF8", f"file {path} is not valid UTF-8: {exc}") from exc
    return parse_strict_json_text(text, allow_float=allow_float, require_object=require_object)


def load_strict_jsonl_file(
    path: Path,
    *,
    allow_float: bool = True,
    require_object: bool = True,
) -> list[Any]:
    """
    Strict line-delimited JSONL loader (v1.4, closes `WD-LEDGER-01`):
      - Rejects CRLF line endings and invalid UTF-8
      - Rejects whitespace-only non-empty tampered files (empty 0-byte file returns `[]`)
      - Rejects blank interior lines, duplicate keys at any depth, and `NaN`/`Infinity`.
    """
    require_ok(path.is_file(), "FILE_NOT_FOUND", f"JSONL file not found: {path}")
    raw = path.read_bytes()
    require_ok(b"\r\n" not in raw, "CRLF_LINE_ENDINGS", f"CRLF line endings detected in {path}")
    if len(raw) == 0:
        return []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AletheiaError("INVALID_UTF8", f"file {path} is not valid UTF-8: {exc}") from exc
    if len(text.strip()) == 0:
        raise AletheiaError("JSONL_WHITESPACE_ONLY", f"whitespace-only non-empty JSONL file: {path}")
    records: list[Any] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if len(line.strip()) == 0:
            raise AletheiaError("JSONL_BLANK_LINE", f"blank line at {path}:{lineno}")
        try:
            records.append(loads_strict_json(line, allow_float=allow_float, require_object=require_object))
        except AletheiaError as exc:
            raise AletheiaError(exc.code, f"{path}:{lineno}: {exc.message}") from exc
    return records


def personal_path_regexes() -> list[tuple[str, re.Pattern[str]]]:
    """
    Build personal filesystem path regexes programmatically so static scanners never
    self-trigger on this module's own source code.
    """
    slash = chr(47)
    bslash = chr(92)
    unix_home = slash + "ho" + "me" + slash + r"[A-Za-z0-9._-]+"
    mac_users = slash + "Us" + "ers" + slash + r"[A-Za-z0-9._-]+"
    win_users = r"[A-Za-z]:" + bslash + bslash + "Us" + "ers" + bslash + bslash + r"[A-Za-z0-9._-]+"
    return [
        ("unix_home_path", re.compile(unix_home)),
        ("macos_users_path", re.compile(mac_users)),
        ("windows_users_path", re.compile(win_users)),
    ]


def credential_regexes() -> list[tuple[str, re.Pattern[str]]]:
    """Build secret/credential detection regexes programmatically (no literal tokens in source)."""
    gh_p = "gh" + "p_" + r"[A-Za-z0-9]{20,}"
    gh_o = "gh" + "o_" + r"[A-Za-z0-9]{20,}"
    gh_pat = "github_" + "pat_" + r"[A-Za-z0-9_]{20,}"
    aws_k = "AK" + "IA" + r"[0-9A-Z]{16}"
    openai_k = "sk" + "-proj-" + r"[A-Za-z0-9_-]{20,}"
    priv_key = "-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    return [
        ("github_classic_pat", re.compile(gh_p)),
        ("github_oauth_token", re.compile(gh_o)),
        ("github_fine_grained_pat", re.compile(gh_pat)),
        ("aws_access_key", re.compile(aws_k)),
        ("openai_project_key", re.compile(openai_k)),
        ("private_key_block", re.compile(priv_key)),
    ]


def scan_text_for_leaks(text: str) -> list[dict[str, Any]]:
    """Return list of personal-path or credential leak matches in text."""
    findings: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, rx in personal_path_regexes():
            if rx.search(line) is not None:
                findings.append({"kind": "personal_path", "rule": label, "line": lineno})
        for label, rx in credential_regexes():
            if rx.search(line) is not None:
                findings.append({"kind": "credential", "rule": label, "line": lineno})
    return findings


def write_lf_text(path: Path, text: str) -> None:
    """Write UTF-8 text with strict LF line endings."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(normalized)
