"""
`aletheia.context_hygiene`: CS-26 context-lifecycle & cold-cache hygiene (pure-Q).

Stdlib-only, pure `int` / `fractions.Fraction` engine for ephemeral worker
retire/respawn, cold-cache reactivation guard, external-file-in-place board
discipline, and wave-boundary rotation accounting
(`spec/proposals/CONTEXT_LIFECYCLE_AND_CACHE_HYGIENE.md`).

All file reads fail closed: leaf and ancestor symlink refusal via
`O_DIRECTORY | O_NOFOLLOW` traversal, `O_RDONLY | O_NOFOLLOW | O_NONBLOCK`
leaf open with `S_ISREG` check, streaming 16 MiB cap, strict exact JSON
(float-free, duplicate-key-free, bounded int digits and nesting depth).
Zero bare asserts; safe across all R4 isolated modes.
"""
from __future__ import annotations

from fractions import Fraction
import json
import os
from pathlib import Path
import stat
from typing import Any

from .strict_io import AletheiaError

__all__ = [
    "MAX_FILE_BYTES",
    "MAX_JSON_DEPTH",
    "MAX_JSON_INT_DIGITS",
    "evaluate_reactivation_policy",
    "audit_context_hygiene",
    "run_context_hygiene_demo",
    "run_context_hygiene_self_test",
]

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_JSON_INT_DIGITS = 1024
MAX_JSON_DEPTH = 64
_READ_CHUNK_BYTES = 65536
_SCHEMA = "aletheia.context_hygiene.v1"


def _frac_str(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _frac_div(numerator: Fraction, denominator: Fraction) -> Fraction:
    return Fraction(numerator.numerator * denominator.denominator, numerator.denominator * denominator.numerator)


def _require_exact_int(value: Any, label: str, minimum: int) -> int:
    if type(value) is not int:
        raise AletheiaError("CONTEXT_HYGIENE_INVALID_INT", f"{label} must be an exact int, got {type(value).__name__}")
    if value < minimum:
        raise AletheiaError("CONTEXT_HYGIENE_INVALID_INT", f"{label} must be >= {minimum}, got {value}")
    return value


def _to_fraction(value: Any, label: str) -> Fraction:
    if type(value) is int:
        return Fraction(value, 1)
    if type(value) is not Fraction:
        raise AletheiaError("CONTEXT_HYGIENE_INVALID_COST", f"{label} must be an exact int or Fraction, got {type(value).__name__}")
    return value


def _require_positive_fraction(value: Fraction, label: str) -> Fraction:
    if value <= Fraction(0, 1):
        raise AletheiaError("CONTEXT_HYGIENE_INVALID_COST", f"{label} must be > 0, got {_frac_str(value)}")
    return value


def _require_nonnegative_fraction(value: Fraction, label: str) -> Fraction:
    if value < Fraction(0, 1):
        raise AletheiaError("CONTEXT_HYGIENE_INVALID_COST", f"{label} must be >= 0, got {_frac_str(value)}")
    return value


def _reject_float(raw: str) -> Any:
    raise AletheiaError("CONTEXT_HYGIENE_JSON_FLOAT", f"float literal forbidden in exact JSON: {raw!r}")


def _reject_constant(raw: str) -> Any:
    raise AletheiaError("CONTEXT_HYGIENE_JSON_CONSTANT", f"non-standard JSON constant forbidden: {raw!r}")


def _parse_int_strict(raw: str) -> int:
    digits = len(raw)
    if raw.startswith("-"):
        digits = digits - 1
    if digits > MAX_JSON_INT_DIGITS:
        raise AletheiaError("CONTEXT_HYGIENE_JSON_INT_TOO_LONG", f"integer literal exceeds {MAX_JSON_INT_DIGITS} digits")
    return int(raw)


def _object_pairs_no_dup(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in pairs:
        if key in out:
            raise AletheiaError("CONTEXT_HYGIENE_JSON_DUPLICATE_KEY", f"duplicate JSON key: {key!r}")
        out[key] = val
    return out


def _check_depth_and_surrogates(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 1)]
    while len(stack) > 0:
        item, depth = stack.pop()
        if isinstance(item, str):
            if any(0xD800 <= ord(ch) <= 0xDFFF for ch in item):
                raise AletheiaError("CONTEXT_HYGIENE_JSON_LONE_SURROGATE", "lone surrogate in JSON string")
        if isinstance(item, (dict, list)):
            if depth > MAX_JSON_DEPTH:
                raise AletheiaError("CONTEXT_HYGIENE_JSON_DEPTH", f"JSON nesting exceeds depth {MAX_JSON_DEPTH}")
        if isinstance(item, dict):
            for key, sub in item.items():
                stack.append((key, depth + 1))
                stack.append((sub, depth + 1))
        if isinstance(item, list):
            for sub in item:
                stack.append((sub, depth + 1))


def _loads_strict_exact(text: Any, label: str) -> Any:
    if type(text) is not str:
        raise AletheiaError("CONTEXT_HYGIENE_JSON_TYPE", f"{label} JSON text must be str, got {type(text).__name__}")
    if len(text.strip()) == 0:
        raise AletheiaError("CONTEXT_HYGIENE_JSON_EMPTY", f"{label} JSON text must be non-empty")
    try:
        obj = json.loads(
            text,
            parse_float=_reject_float,
            parse_int=_parse_int_strict,
            parse_constant=_reject_constant,
            object_pairs_hook=_object_pairs_no_dup,
        )
    except AletheiaError:
        raise
    except RecursionError as exc:
        raise AletheiaError("CONTEXT_HYGIENE_JSON_DEPTH", f"{label}: JSON nesting exceeds parser depth bound") from exc
    except (ValueError, OverflowError) as exc:
        raise AletheiaError("CONTEXT_HYGIENE_JSON_SYNTAX", f"{label}: {exc}") from exc
    _check_depth_and_surrogates(obj)
    return obj


def _read_file_bytes(path: Any, label: str) -> bytes:
    p = path
    if type(path) is str:
        p = Path(path)
    if isinstance(p, Path) is False:
        raise AletheiaError("CONTEXT_HYGIENE_INVALID_PATH", f"{label} path must be str or Path, got {type(path).__name__}")
    parts = p.parts
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    anchor = "."
    idx = 0
    if p.is_absolute():
        anchor = os.sep
        idx = 1
    if len(parts) <= idx:
        raise AletheiaError("CONTEXT_HYGIENE_INVALID_PATH", f"{label} path names no file: {p}")
    fds: list[int] = []
    try:
        cur = os.open(anchor, dir_flags)
        fds.append(cur)
        while idx < len(parts) - 1:
            cur = os.open(parts[idx], dir_flags, dir_fd=cur)
            fds.append(cur)
            idx = idx + 1
        fd = os.open(parts[idx], file_flags, dir_fd=cur)
        fds.append(fd)
        st = os.fstat(fd)
        if stat.S_ISREG(st.st_mode) is False:
            raise AletheiaError("CONTEXT_HYGIENE_NOT_REGULAR_FILE", f"{label} is not a regular file: {p}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, _READ_CHUNK_BYTES)
            if len(chunk) == 0:
                break
            total = total + len(chunk)
            if total > MAX_FILE_BYTES:
                raise AletheiaError("CONTEXT_HYGIENE_FILE_TOO_LARGE", f"{label} exceeds {MAX_FILE_BYTES} bytes: {p}")
            chunks.append(chunk)
        return b"".join(chunks)
    except AletheiaError:
        raise
    except OSError as exc:
        raise AletheiaError("CONTEXT_HYGIENE_IO_ERROR", f"{label}: cannot read {p}: {exc}") from exc
    finally:
        for open_fd in reversed(fds):
            try:
                os.close(open_fd)
            except OSError:
                pass


def _decode_utf8(data: bytes, label: str) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AletheiaError("CONTEXT_HYGIENE_INVALID_UTF8", f"{label} is not valid UTF-8: {exc}") from exc
    if "\r" in text:
        raise AletheiaError("CONTEXT_HYGIENE_CRLF", f"{label} contains CR characters (LF-only required)")
    return text


def evaluate_reactivation_policy(
    *,
    context_tokens: Any,
    idle_seconds: Any,
    cache_ttl_seconds: Any = 300,
    fresh_context_tokens: Any = 0,
    system_tokens: Any = 0,
    summary_tokens: Any = 0,
    c_miss: Any = Fraction(1, 1),
    c_hit: Any = Fraction(1, 10),
    c_out: Any = Fraction(1, 1),
) -> dict[str, Any]:
    """Exact pure-Q reactivation policy: `RETIRE_AND_RESPAWN`, `PRE_IDLE_COMPACT`, or `KEEP_WARM`."""
    ctx = _require_exact_int(context_tokens, "context_tokens", 0)
    idle = _require_exact_int(idle_seconds, "idle_seconds", 0)
    ttl = _require_exact_int(cache_ttl_seconds, "cache_ttl_seconds", 0)
    fresh = _require_exact_int(fresh_context_tokens, "fresh_context_tokens", 0)
    system = _require_exact_int(system_tokens, "system_tokens", 0)
    summary = _require_exact_int(summary_tokens, "summary_tokens", 0)
    miss = _require_positive_fraction(_to_fraction(c_miss, "c_miss"), "c_miss")
    hit = _require_nonnegative_fraction(_to_fraction(c_hit, "c_hit"), "c_hit")
    out = _require_nonnegative_fraction(_to_fraction(c_out, "c_out"), "c_out")

    cold_cost = miss * ctx
    warm_cost = hit * ctx
    respawn_cost = miss * fresh
    compact_cost = hit * ctx + out * summary + miss * (system + summary)
    crossover = None
    if miss > hit:
        crossover = _frac_div(out * summary + miss * (system + summary), miss - hit)
    is_cold = idle >= ttl
    reactivation_cost = cold_cost if is_cold else warm_cost

    policy = "KEEP_WARM"
    chosen_cost = reactivation_cost
    if is_cold:
        if respawn_cost < cold_cost:
            if respawn_cost <= compact_cost:
                policy = "RETIRE_AND_RESPAWN"
                chosen_cost = respawn_cost
            if compact_cost < respawn_cost:
                policy = "PRE_IDLE_COMPACT"
                chosen_cost = compact_cost
        if respawn_cost >= cold_cost:
            if compact_cost < cold_cost:
                policy = "PRE_IDLE_COMPACT"
                chosen_cost = compact_cost

    return {
        "schema": "aletheia.context_hygiene.policy.v1",
        "policy": policy,
        "is_cold": is_cold,
        "context_tokens": ctx,
        "idle_seconds": idle,
        "cache_ttl_seconds": ttl,
        "fresh_context_tokens": fresh,
        "system_tokens": system,
        "summary_tokens": summary,
        "c_miss": _frac_str(miss),
        "c_hit": _frac_str(hit),
        "c_out": _frac_str(out),
        "cold_cost": _frac_str(cold_cost),
        "warm_cost": _frac_str(warm_cost),
        "respawn_cost": _frac_str(respawn_cost),
        "compact_cost": _frac_str(compact_cost),
        "reactivation_cost": _frac_str(reactivation_cost),
        "chosen_cost": _frac_str(chosen_cost),
        "crossover_tokens": None if crossover is None else _frac_str(crossover),
        "respawn_savings": _frac_str(reactivation_cost - respawn_cost),
        "compact_savings": _frac_str(reactivation_cost - compact_cost),
        "chosen_savings": _frac_str(reactivation_cost - chosen_cost),
    }


def _audit_board(board_path: Any, max_lines: int, max_chars: int) -> tuple[list[dict[str, Any]], int, int]:
    text = _decode_utf8(_read_file_bytes(board_path, "board"), "board")
    findings: list[dict[str, Any]] = []
    count = 0
    oversize = 0
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        count = count + 1
        if len(raw_line.strip()) == 0:
            raise AletheiaError("CONTEXT_HYGIENE_BOARD_BLANK_LINE", f"board:{lineno}: blank line")
        obj = _loads_strict_exact(raw_line, f"board:{lineno}")
        if isinstance(obj, dict) is False:
            raise AletheiaError("CONTEXT_HYGIENE_BOARD_NOT_OBJECT", f"board:{lineno}: line must be a JSON object")
        measured = raw_line
        if "text" in obj:
            if type(obj["text"]) is not str:
                raise AletheiaError("CONTEXT_HYGIENE_BOARD_TEXT_TYPE", f"board:{lineno}: text must be str")
            measured = obj["text"]
        n_lines = len(measured.splitlines())
        n_chars = len(measured)
        flagged = False
        if n_lines > max_lines:
            findings.append({
                "kind": "BOARD_MESSAGE_TOO_MANY_LINES",
                "severity": "WARNING",
                "source": "board",
                "line": lineno,
                "measured": n_lines,
                "limit": max_lines,
                "message": "board message exceeds line budget; move the payload to an external file and post verdict, path, digest, and action",
            })
            flagged = True
        if n_chars > max_chars:
            findings.append({
                "kind": "BOARD_MESSAGE_TOO_LONG",
                "severity": "WARNING",
                "source": "board",
                "line": lineno,
                "measured": n_chars,
                "limit": max_chars,
                "message": "board message exceeds character budget; move the payload to an external file and post verdict, path, digest, and action",
            })
            flagged = True
        if flagged:
            oversize = oversize + 1
    return findings, count, oversize


def _get_required_int(obj: dict[str, Any], field: str, label: str) -> int:
    if field not in obj:
        raise AletheiaError("CONTEXT_HYGIENE_MISSING_FIELD", f"{label}: missing required field {field!r}")
    return _require_exact_int(obj[field], f"{label}.{field}", 0)


def _audit_workers(
    workers_path: Any,
    cold_tokens: int,
    ttl_seconds: int,
    max_compactions: int,
) -> tuple[list[dict[str, Any]], int, int, int, int, int]:
    obj = _loads_strict_exact(_decode_utf8(_read_file_bytes(workers_path, "workers"), "workers"), "workers")
    if isinstance(obj, dict) is False:
        raise AletheiaError("CONTEXT_HYGIENE_WORKERS_NOT_OBJECT", "workers payload must be a JSON object")
    if "workers" not in obj:
        raise AletheiaError("CONTEXT_HYGIENE_MISSING_FIELD", "workers: missing required field 'workers'")
    workers = obj["workers"]
    if isinstance(workers, list) is False:
        raise AletheiaError("CONTEXT_HYGIENE_WORKERS_NOT_LIST", "workers.workers must be a list")
    findings: list[dict[str, Any]] = []
    total_tokens = 0
    max_tokens = 0
    bloated = 0
    cold_risk = 0
    for idx, worker in enumerate(workers):
        if isinstance(worker, dict) is False:
            raise AletheiaError("CONTEXT_HYGIENE_WORKER_NOT_OBJECT", f"workers[{idx}] must be a JSON object")
        if "id" not in worker:
            raise AletheiaError("CONTEXT_HYGIENE_MISSING_FIELD", f"workers[{idx}]: missing required field 'id'")
        wid = worker["id"]
        if type(wid) is not str:
            raise AletheiaError("CONTEXT_HYGIENE_WORKER_ID_TYPE", f"workers[{idx}].id must be str")
        if len(wid) == 0:
            raise AletheiaError("CONTEXT_HYGIENE_WORKER_ID_EMPTY", f"workers[{idx}].id must be non-empty")
        ctx = _get_required_int(worker, "context_tokens", f"workers[{idx}]")
        idle = _get_required_int(worker, "idle_seconds", f"workers[{idx}]")
        compactions = _get_required_int(worker, "compactions", f"workers[{idx}]")
        total_tokens = total_tokens + ctx
        if ctx > max_tokens:
            max_tokens = ctx
        if ctx > cold_tokens:
            bloated = bloated + 1
            if idle >= ttl_seconds:
                cold_risk = cold_risk + 1
                findings.append({
                    "kind": "COLD_CACHE_REACTIVATION_RISK",
                    "severity": "ALERT",
                    "source": "workers",
                    "worker_id": wid,
                    "context_tokens": ctx,
                    "idle_seconds": idle,
                    "limit": cold_tokens,
                    "cache_ttl_seconds": ttl_seconds,
                    "message": "bloated worker idle past cache TTL; retire and respawn fresh, or compact before idling",
                })
            if idle < ttl_seconds:
                findings.append({
                    "kind": "CONTEXT_BLOAT",
                    "severity": "WARNING",
                    "source": "workers",
                    "worker_id": wid,
                    "context_tokens": ctx,
                    "idle_seconds": idle,
                    "limit": cold_tokens,
                    "cache_ttl_seconds": ttl_seconds,
                    "message": "worker context exceeds cold threshold while still warm; finish, land work on disk, then retire or compact",
                })
        if compactions > max_compactions:
            findings.append({
                "kind": "COMPACTION_CHURN",
                "severity": "WARNING",
                "source": "workers",
                "worker_id": wid,
                "measured": compactions,
                "limit": max_compactions,
                "message": "worker exceeded compaction budget; rotate the role at the next wave boundary",
            })
    return findings, len(workers), total_tokens, max_tokens, bloated, cold_risk


def audit_context_hygiene(
    *,
    board_path: Any = None,
    workers_path: Any = None,
    max_board_lines: Any = 12,
    max_board_chars: Any = 2000,
    cold_context_tokens: Any = 150000,
    cache_ttl_seconds: Any = 300,
    max_compactions: Any = 5,
) -> dict[str, Any]:
    """Deterministic CS-26 scan of an optional board JSONL and optional workers JSON."""
    m_lines = _require_exact_int(max_board_lines, "max_board_lines", 1)
    m_chars = _require_exact_int(max_board_chars, "max_board_chars", 1)
    cold_tokens = _require_exact_int(cold_context_tokens, "cold_context_tokens", 0)
    ttl = _require_exact_int(cache_ttl_seconds, "cache_ttl_seconds", 0)
    m_comp = _require_exact_int(max_compactions, "max_compactions", 0)

    findings: list[dict[str, Any]] = []
    board_count = 0
    board_oversize = 0
    workers_count = 0
    total_tokens = 0
    max_tokens = 0
    bloated = 0
    cold_risk = 0
    if board_path is not None:
        b_findings, board_count, board_oversize = _audit_board(board_path, m_lines, m_chars)
        findings.extend(b_findings)
    if workers_path is not None:
        w_findings, workers_count, total_tokens, max_tokens, bloated, cold_risk = _audit_workers(
            workers_path, cold_tokens, ttl, m_comp
        )
        findings.extend(w_findings)

    has_alert = False
    has_warning = False
    for finding in findings:
        if finding["severity"] == "ALERT":
            has_alert = True
        if finding["severity"] == "WARNING":
            has_warning = True
    status = "CLEAN"
    if has_warning:
        status = "WARNING"
    if has_alert:
        status = "ALERT"

    bloated_ratio = Fraction(bloated, workers_count) if workers_count > 0 else Fraction(0, 1)
    cold_ratio = Fraction(cold_risk, workers_count) if workers_count > 0 else Fraction(0, 1)
    oversize_ratio = Fraction(board_oversize, board_count) if board_count > 0 else Fraction(0, 1)
    return {
        "schema": _SCHEMA,
        "status": status,
        "thresholds": {
            "max_board_lines": m_lines,
            "max_board_chars": m_chars,
            "cold_context_tokens": cold_tokens,
            "cache_ttl_seconds": ttl,
            "max_compactions": m_comp,
        },
        "board": {
            "messages": board_count,
            "oversize_messages": board_oversize,
            "oversize_ratio": _frac_str(oversize_ratio),
        },
        "workers": {
            "count": workers_count,
            "total_context_tokens": total_tokens,
            "max_context_tokens": max_tokens,
            "bloated_workers": bloated,
            "cold_risk_workers": cold_risk,
            "bloated_ratio": _frac_str(bloated_ratio),
            "cold_risk_ratio": _frac_str(cold_ratio),
        },
        "findings": findings,
    }


def run_context_hygiene_demo() -> dict[str, Any]:
    """Deterministic zero-file demo of the three reactivation policies."""
    respawn = evaluate_reactivation_policy(
        context_tokens=200000,
        idle_seconds=3600,
        cache_ttl_seconds=300,
        fresh_context_tokens=2000,
        system_tokens=2000,
        summary_tokens=4000,
        c_miss=Fraction(3, 1),
        c_hit=Fraction(1, 10),
        c_out=Fraction(15, 1),
    )
    compact = evaluate_reactivation_policy(
        context_tokens=200000,
        idle_seconds=3600,
        cache_ttl_seconds=300,
        fresh_context_tokens=150000,
        system_tokens=2000,
        summary_tokens=2000,
        c_miss=Fraction(3, 1),
        c_hit=Fraction(1, 10),
        c_out=Fraction(15, 1),
    )
    warm = evaluate_reactivation_policy(
        context_tokens=200000,
        idle_seconds=10,
        cache_ttl_seconds=300,
        fresh_context_tokens=2000,
        system_tokens=2000,
        summary_tokens=4000,
        c_miss=Fraction(3, 1),
        c_hit=Fraction(1, 10),
        c_out=Fraction(15, 1),
    )
    clean = audit_context_hygiene()
    return {
        "schema": "aletheia.context_hygiene.demo.v1",
        "status": "OK",
        "passed": True,
        "examples": {"respawn": respawn, "compact": compact, "warm": warm},
        "empty_audit": clean,
    }


def run_context_hygiene_self_test() -> dict[str, Any]:
    """Deterministic self-test with positive checks and fail-closed negative controls."""
    checks: dict[str, bool] = {}
    respawn = evaluate_reactivation_policy(
        context_tokens=200000,
        idle_seconds=3600,
        cache_ttl_seconds=300,
        fresh_context_tokens=2000,
        system_tokens=2000,
        summary_tokens=4000,
        c_miss=Fraction(3, 1),
        c_hit=Fraction(1, 10),
        c_out=Fraction(15, 1),
    )
    checks["respawn_policy"] = respawn["policy"] == "RETIRE_AND_RESPAWN"
    checks["respawn_is_cold"] = respawn["is_cold"] is True
    checks["crossover_exact"] = respawn["crossover_tokens"] == "780000/29"
    checks["compact_cost_exact"] = respawn["compact_cost"] == "98000/1"
    checks["cold_cost_exact"] = respawn["cold_cost"] == "600000/1"
    checks["respawn_savings_exact"] = respawn["respawn_savings"] == "594000/1"
    no_crossover_eq = evaluate_reactivation_policy(
        context_tokens=1000, idle_seconds=3600, c_miss=Fraction(1, 1), c_hit=Fraction(1, 1)
    )
    checks["crossover_none_when_miss_eq_hit"] = no_crossover_eq["crossover_tokens"] is None
    no_crossover_lt = evaluate_reactivation_policy(
        context_tokens=1000, idle_seconds=3600, c_miss=Fraction(1, 1), c_hit=Fraction(2, 1)
    )
    checks["crossover_none_when_miss_lt_hit"] = no_crossover_lt["crossover_tokens"] is None
    warm = evaluate_reactivation_policy(context_tokens=1000, idle_seconds=0, cache_ttl_seconds=300)
    checks["default_c_hit_exact"] = warm["c_hit"] == "1/10"
    checks["warm_policy"] = warm["policy"] == "KEEP_WARM"
    checks["warm_is_cold"] = warm["is_cold"] is False
    clean = audit_context_hygiene()
    checks["empty_audit_clean"] = clean["status"] == "CLEAN"
    checks["empty_audit_schema"] = clean["schema"] == _SCHEMA

    rejected_negative = False
    try:
        evaluate_reactivation_policy(context_tokens=-1, idle_seconds=0)
    except AletheiaError:
        rejected_negative = True
    checks["negative_context_rejected"] = rejected_negative

    rejected_bool = False
    try:
        evaluate_reactivation_policy(context_tokens=True, idle_seconds=0)
    except AletheiaError:
        rejected_bool = True
    checks["bool_context_rejected"] = rejected_bool

    rejected_cost = False
    try:
        evaluate_reactivation_policy(context_tokens=10, idle_seconds=0, c_miss=Fraction(0, 1))
    except AletheiaError:
        rejected_cost = True
    checks["zero_miss_cost_rejected"] = rejected_cost

    rejected_threshold = False
    try:
        audit_context_hygiene(max_board_lines=0)
    except AletheiaError:
        rejected_threshold = True
    checks["zero_board_lines_rejected"] = rejected_threshold

    passed = all(checks.values())
    return {
        "schema": "aletheia.context_hygiene.self_test.v1",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "checks": checks,
    }
