"""
`aletheia._strict_zone_b`: Shared fail-closed Zone-B OS-descriptor file IO and
strict exact JSON validation helpers for CS-27..CS-29 & EXP-Q46b modules.

Stdlib-only, zero bare asserts, safe under `-I -B`, `-I -O -B`, and `-I -B -W error`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import Any, Type

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_JSON_INT_DIGITS = 1024
_READ_CHUNK_BYTES = 65536


def require(cond: bool, err_cls: Type[ValueError], code: str, message: str) -> None:
    """Raise `err_cls(code, message)` when `cond` is false."""
    if not cond:
        raise err_cls(code, message)


def decode_strict_utf8_bytes(
    raw_bytes: bytes,
    label: str,
    *,
    err_cls: Type[ValueError],
    bom_code: str = "JSON_BOM_FORBIDDEN",
    crlf_code: str = "JSON_CRLF_FORBIDDEN",
    require_crlf_only: bool = False,
) -> str:
    """Validate zero UTF-8 BOM, zero CR/CRLF, and strict UTF-8 decoding."""
    require(not raw_bytes.startswith(b"\xef\xbb\xbf"), err_cls, bom_code, f"{label}: UTF-8 BOM forbidden")
    bad_cr = (b"\r\n" in raw_bytes) if require_crlf_only else (b"\r" in raw_bytes)
    require(not bad_cr, err_cls, crlf_code, f"{label}: CR/CRLF forbidden")
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise err_cls("INVALID_UTF8", f"{label}: invalid UTF-8: {exc}") from exc


def _check_depth_and_surrogates(value: Any, err_cls: Type[ValueError], max_depth: int) -> None:
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, str):
            for ch in item:
                require(
                    not (0xD800 <= ord(ch) <= 0xDFFF),
                    err_cls,
                    "JSON_LONE_SURROGATE",
                    "lone surrogate in JSON string",
                )
        elif isinstance(item, dict):
            require(depth <= max_depth, err_cls, "JSON_DEPTH_EXCEEDED", f"JSON depth > {max_depth}")
            for k, sub in item.items():
                stack.append((k, depth + 1))
                stack.append((sub, depth + 1))
        elif isinstance(item, list):
            require(depth <= max_depth, err_cls, "JSON_DEPTH_EXCEEDED", f"JSON depth > {max_depth}")
            for sub in item:
                stack.append((sub, depth + 1))


def parse_strict_json_text(
    text: str,
    label: str,
    *,
    err_cls: Type[ValueError],
    max_depth: int = MAX_JSON_DEPTH,
    max_int_digits: int = MAX_JSON_INT_DIGITS,
    allow_float: bool = False,
    syntax_code: str = "JSON_SYNTAX_ERROR",
    blank_code: str = "EMPTY_JSON",
) -> Any:
    """Parse JSON text strictly: duplicate-key, constant, float, int-digit, depth, surrogate guards."""
    require(len(text.strip()) > 0, err_cls, blank_code, f"{label}: JSON payload is empty")

    def _reject_float(raw: str) -> Any:
        raise err_cls("JSON_FLOAT_FORBIDDEN", f"float literal forbidden: {raw!r}")

    def _reject_constant(raw: str) -> Any:
        raise err_cls("JSON_CONSTANT_FORBIDDEN", f"non-finite JSON constant forbidden: {raw!r}")

    def _parse_int_strict(raw: str) -> int:
        digits = len(raw) - 1 if raw.startswith("-") else len(raw)
        require(
            digits <= max_int_digits,
            err_cls,
            "JSON_INT_TOO_LONG",
            f"integer exceeds {max_int_digits} digits",
        )
        return int(raw)

    def _object_pairs_no_dup(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            require(k not in out, err_cls, "JSON_DUPLICATE_KEY", f"duplicate JSON key: {k!r}")
            out[k] = v
        return out

    kwargs: dict[str, Any] = {
        "parse_int": _parse_int_strict,
        "parse_constant": _reject_constant,
        "object_pairs_hook": _object_pairs_no_dup,
    }
    if not allow_float:
        kwargs["parse_float"] = _reject_float

    try:
        obj = json.loads(text, **kwargs)
    except err_cls:
        raise
    except (ValueError, RecursionError, OverflowError) as exc:
        raise err_cls(syntax_code, f"{label}: {exc}") from exc
    _check_depth_and_surrogates(obj, err_cls, max_depth)
    return obj


def parse_strict_json_bytes(
    raw_bytes: bytes,
    label: str,
    *,
    err_cls: Type[ValueError],
    max_depth: int = MAX_JSON_DEPTH,
    max_int_digits: int = MAX_JSON_INT_DIGITS,
    allow_float: bool = False,
    bom_code: str = "JSON_BOM_FORBIDDEN",
    crlf_code: str = "JSON_CRLF_FORBIDDEN",
    syntax_code: str = "JSON_SYNTAX_ERROR",
    blank_code: str = "EMPTY_JSON",
) -> Any:
    """Decode UTF-8 (no BOM/CRLF) and parse strict JSON."""
    text = decode_strict_utf8_bytes(
        raw_bytes,
        label,
        err_cls=err_cls,
        bom_code=bom_code,
        crlf_code=crlf_code,
    )
    return parse_strict_json_text(
        text,
        label,
        err_cls=err_cls,
        max_depth=max_depth,
        max_int_digits=max_int_digits,
        allow_float=allow_float,
        syntax_code=syntax_code,
        blank_code=blank_code,
    )


def _read_fd_or_resolve(
    path: Any,
    label: str,
    *,
    err_cls: Type[ValueError],
    max_bytes: int | None,
    path_code: str,
    not_reg_code: str,
    io_code: str,
    too_large_code: str,
) -> bytes | Path:
    p = Path(path) if type(path) is str else path
    require(isinstance(p, Path), err_cls, path_code, f"{label}: path must be str or Path")
    require("\x00" not in os.fspath(p), err_cls, path_code, f"{label}: NUL byte forbidden in path")
    parts = p.parts
    anchor = os.sep if p.is_absolute() else "."
    idx = 1 if p.is_absolute() else 0
    require(len(parts) > idx, err_cls, path_code, f"{label}: path names no file")
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fds: list[int] = []
    try:
        cur = os.open(anchor, dir_flags)
        fds.append(cur)
        while idx < len(parts) - 1:
            cur = os.open(parts[idx], dir_flags, dir_fd=cur)
            fds.append(cur)
            idx += 1
        fd = os.open(parts[idx], file_flags, dir_fd=cur)
        fds.append(fd)
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode), err_cls, not_reg_code, f"{label}: not a regular file")
        if max_bytes is None:
            proc_fd = f"/proc/self/fd/{fd}"
            cand = Path(os.readlink(proc_fd)) if os.path.islink(proc_fd) else Path(os.path.abspath(os.fspath(p)))
            cand_st = os.lstat(cand)
            require(
                stat.S_ISREG(cand_st.st_mode) and cand_st.st_dev == st.st_dev and cand_st.st_ino == st.st_ino,
                err_cls,
                not_reg_code,
                f"{label}: path changed during verification",
            )
            return cand
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, _READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            require(total <= max_bytes, err_cls, too_large_code, f"{label}: exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    except err_cls:
        raise
    except OSError as exc:
        raise err_cls(io_code, f"{label}: {exc}") from exc
    finally:
        for fd_item in reversed(fds):
            try:
                os.close(fd_item)
            except OSError:
                pass


def open_regular_file(
    path: Any,
    label: str,
    *,
    err_cls: Type[ValueError],
    max_bytes: int = MAX_FILE_BYTES,
    path_code: str = "INVALID_PATH",
    not_reg_code: str = "NOT_REGULAR_FILE",
    io_code: str = "IO_ERROR",
    too_large_code: str = "FILE_TOO_LARGE",
) -> bytes:
    """Traverse dirs with `O_NOFOLLOW`, verify `S_ISREG`, and return bounded file bytes."""
    out = _read_fd_or_resolve(
        path,
        label,
        err_cls=err_cls,
        max_bytes=max_bytes,
        path_code=path_code,
        not_reg_code=not_reg_code,
        io_code=io_code,
        too_large_code=too_large_code,
    )
    return out if type(out) is bytes else b""


def verify_regular_file_path(
    path: Any,
    label: str,
    *,
    err_cls: Type[ValueError],
    path_code: str = "INVALID_PATH",
    not_reg_code: str = "NOT_REGULAR_FILE",
    io_code: str = "IO_ERROR",
) -> Path:
    """Traverse dirs with `O_NOFOLLOW`, verify `S_ISREG`, and return verified `Path` without `Path.resolve()`."""
    out = _read_fd_or_resolve(
        path,
        label,
        err_cls=err_cls,
        max_bytes=None,
        path_code=path_code,
        not_reg_code=not_reg_code,
        io_code=io_code,
        too_large_code="FILE_TOO_LARGE",
    )
    return out if isinstance(out, Path) else Path(str(path))
