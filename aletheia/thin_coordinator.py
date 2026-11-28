"""
`aletheia.thin_coordinator`: CS-29 (`SOP-20`) Pure-Q Thin-Coordinator Context-Tax
Crossover Engine & Deterministic JSONL Transcript Bloat Analyzer.

Implements:
  1. Exact `fractions.Fraction` Thin-Coordinator vs Inline-Tool Context-Tax
     Crossover Theorem (`T * B * c_hit > W_worker + T * s * c_hit`) including
     compaction-frequency (`dk * K_comp`) and cold-cache reactivation
     (`m_cold * (B - s) * c_miss`) amplification.
  2. Fail-closed deterministic JSONL transcript bloat analyzer measuring inline
     tool-output byte/line ratios, `> max_inline_lines` (`>40`-line) offload
     violations, compaction checkpoints, and token accounting without emitting
     raw session content or private host paths.

Stdlib-only, zero floats in exact calculations, zero bare asserts, safe under
all R4 isolated modes (`-I -B`, `-I -O -B`, `-I -B -W error`).
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

from aletheia import _strict_zone_b as _zb

__all__ = [
    "MAX_JSON_DEPTH",
    "MAX_JSON_INT_DIGITS",
    "MAX_TRANSCRIPT_BYTES",
    "ThinCoordinatorError",
    "evaluate_thin_coordinator_crossover",
    "analyze_transcript_bloat_lines",
    "analyze_transcript_bloat",
]

MAX_TRANSCRIPT_BYTES = 64 * 1024 * 1024
MAX_JSON_DEPTH = _zb.MAX_JSON_DEPTH
MAX_JSON_INT_DIGITS = _zb.MAX_JSON_INT_DIGITS
_TOOL_ROLES = frozenset({"tool", "tool_result", "tool_output"})


class ThinCoordinatorError(ValueError):
    """Fail-closed validation error for CS-29 crossover & transcript bloat gates."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _require(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise ThinCoordinatorError(code, message)


def _frac_str(val: Fraction) -> str:
    return f"{val.numerator}/{val.denominator}"


def _frac_div(num: Fraction, den: Fraction) -> Fraction:
    return Fraction(num.numerator * den.denominator, num.denominator * den.numerator)


def _require_exact_int(val: Any, label: str, minimum: int = 0) -> int:
    _require(type(val) is int and val >= minimum, "INVALID_INT", f"{label} must be exact int >= {minimum}")
    return val


def _to_fraction(val: Any, label: str) -> Fraction:
    if type(val) is int:
        return Fraction(val, 1)
    _require(type(val) is Fraction, "INVALID_COST", f"{label} must be exact int or Fraction")
    return val


def _require_positive_fraction(val: Any, label: str) -> Fraction:
    q = _to_fraction(val, label)
    _require(q > Fraction(0, 1), "NON_POSITIVE_COST", f"{label} must be > 0")
    return q


def _require_nonnegative_fraction(val: Any, label: str) -> Fraction:
    q = _to_fraction(val, label)
    _require(q >= Fraction(0, 1), "NEGATIVE_COST", f"{label} must be >= 0")
    return q


def _require_unit_fraction(val: Any, label: str) -> Fraction:
    q = _to_fraction(val, label)
    _require(Fraction(0, 1) <= q <= Fraction(1, 1), "OUT_OF_RANGE_RATIO", f"{label} must be in [0, 1]")
    return q


def evaluate_thin_coordinator_crossover(
    *,
    remaining_turns: Any,
    inline_payload_tokens: Any,
    summary_tokens: Any,
    worker_cost: Any,
    c_hit: Any = Fraction(1, 10),
    c_miss: Any = Fraction(1, 1),
    cold_misses: Any = 0,
    extra_compactions: Any = 0,
    compaction_cost: Any = Fraction(0, 1),
    inline_lines: Any = None,
    max_inline_lines: Any = 40,
) -> dict[str, Any]:
    """
    Evaluate the exact pure-Q CS-29 Thin-Coordinator vs Inline-Tool crossover theorem:

      Base model:
        inline_cost  = T * B * c_hit
        offload_cost = W_worker + T * s * c_hit
        offload strictly wins iff T * (B - s) * c_hit > W_worker

      Amplified model (compaction frequency dk >= 0 & cold misses m_cold >= 0):
        inline_amp   = inline_cost + m_cold * B * c_miss + dk * K_comp
        offload_amp  = offload_cost + m_cold * s * c_miss
    """
    T = _require_exact_int(remaining_turns, "remaining_turns", 1)
    B = _require_exact_int(inline_payload_tokens, "inline_payload_tokens", 0)
    s = _require_exact_int(summary_tokens, "summary_tokens", 0)
    W = _require_nonnegative_fraction(worker_cost, "worker_cost")
    hit = _require_positive_fraction(c_hit, "c_hit")
    miss = _require_nonnegative_fraction(c_miss, "c_miss")
    m_cold = _require_exact_int(cold_misses, "cold_misses", 0)
    dk = _require_exact_int(extra_compactions, "extra_compactions", 0)
    K_comp = _require_nonnegative_fraction(compaction_cost, "compaction_cost")
    m_lines = _require_exact_int(max_inline_lines, "max_inline_lines", 1)

    lines_val: int | None = None
    if inline_lines is not None:
        lines_val = _require_exact_int(inline_lines, "inline_lines", 0)

    base_inline = T * B * hit
    base_offload = W + T * s * hit
    base_savings = base_inline - base_offload
    base_wins = base_inline > base_offload

    amp_inline = base_inline + m_cold * B * miss + dk * K_comp
    amp_offload = base_offload + m_cold * s * miss
    amp_savings = amp_inline - amp_offload
    amp_wins = amp_inline > amp_offload

    base_payload_star = Fraction(s, 1) + _frac_div(W, T * hit)
    amp_rate = T * hit + m_cold * miss
    amp_payload_star = Fraction(s, 1) + _frac_div(W - dk * K_comp, amp_rate)

    delta_payload = B - s
    base_turns_star: Fraction | None = None
    amp_turns_star: Fraction | None = None
    if delta_payload > 0:
        base_turns_star = _frac_div(W, delta_payload * hit)
        rem_w = W - dk * K_comp - m_cold * delta_payload * miss
        amp_turns_star = _frac_div(rem_w, delta_payload * hit)

    line_rule_triggered = lines_val is not None and lines_val > m_lines
    policy = "OFFLOAD_TO_EPHEMERAL_WORKER" if amp_wins else "KEEP_INLINE"

    return {
        "schema": "aletheia.thin_coordinator.crossover.v1",
        "policy": policy,
        "base_offload_wins": base_wins,
        "amplified_offload_wins": amp_wins,
        "line_rule_triggered": line_rule_triggered,
        "remaining_turns": T,
        "inline_payload_tokens": B,
        "summary_tokens": s,
        "inline_lines": lines_val,
        "max_inline_lines": m_lines,
        "cold_misses": m_cold,
        "extra_compactions": dk,
        "c_hit_q": _frac_str(hit),
        "c_miss_q": _frac_str(miss),
        "worker_cost_q": _frac_str(W),
        "compaction_cost_q": _frac_str(K_comp),
        "base_inline_cost_q": _frac_str(base_inline),
        "base_offload_cost_q": _frac_str(base_offload),
        "base_savings_q": _frac_str(base_savings),
        "amplified_inline_cost_q": _frac_str(amp_inline),
        "amplified_offload_cost_q": _frac_str(amp_offload),
        "amplified_savings_q": _frac_str(amp_savings),
        "compaction_amplification_q": _frac_str(amp_savings - base_savings),
        "base_crossover_payload_tokens_q": _frac_str(base_payload_star),
        "amplified_crossover_payload_tokens_q": _frac_str(amp_payload_star),
        "base_crossover_turns_q": None if base_turns_star is None else _frac_str(base_turns_star),
        "amplified_crossover_turns_q": None if amp_turns_star is None else _frac_str(amp_turns_star),
    }


def _loads_transcript_record(line: str, lineno: int, allow_float: bool) -> dict[str, Any]:
    obj = _zb.parse_strict_json_text(
        line,
        f"transcript:{lineno}",
        err_cls=ThinCoordinatorError,
        max_depth=MAX_JSON_DEPTH,
        max_int_digits=MAX_JSON_INT_DIGITS,
        allow_float=allow_float,
        syntax_code="INVALID_TRANSCRIPT_JSONL",
        blank_code="TRANSCRIPT_BLANK_LINE",
    )
    _require(type(obj) is dict, "TRANSCRIPT_NOT_OBJECT", f"transcript:{lineno}: event must be JSON object")
    return obj


def _extract_content_blocks(value: Any, *, force_tool: bool = False) -> tuple[list[str], list[str]]:
    """Extract `(tool_chunks, other_chunks)` recursively from string or Anthropic content-block lists."""
    tool_chunks: list[str] = []
    other_chunks: list[str] = []
    stack: list[tuple[Any, bool]] = [(value, force_tool)]
    while stack:
        cur, in_tool = stack.pop()
        if type(cur) is str:
            if cur:
                (tool_chunks if in_tool else other_chunks).append(cur)
        elif isinstance(cur, list):
            for item in reversed(cur):
                stack.append((item, in_tool))
        elif isinstance(cur, dict):
            btype = cur.get("type")
            next_tool = in_tool or btype in _TOOL_ROLES or cur.get("role") in _TOOL_ROLES
            for sub_key in ("text", "tool_output", "output", "content"):
                if sub_key in cur and cur[sub_key] is not None:
                    stack.append((cur[sub_key], next_tool))
    return tool_chunks, other_chunks


def _count_lf_lines(text: str) -> int:
    if not text:
        return 0
    count = text.count("\n")
    return count if text.endswith("\n") else count + 1


def _split_lf_records(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _extract_event_text_metrics(event: dict[str, Any]) -> tuple[bool, bool, str, str, int, int, int]:
    """
    Classify one JSONL transcript event across Antigravity, Claude, and flat tool schemas.

    Returns:
      (is_tool_output, is_checkpoint, tool_text, other_text, input_toks, cache_toks, output_toks)
    """
    etype = event.get("type")
    role = event.get("role")
    kind = event.get("kind")

    is_checkpoint = etype == "CHECKPOINT" or event.get("subtype") == "compact_boundary"

    in_tok = event.get("input_tokens") if type(event.get("input_tokens")) is int and event.get("input_tokens") >= 0 else 0
    cache_tok = event.get("cache_read_tokens") if type(event.get("cache_read_tokens")) is int and event.get("cache_read_tokens") >= 0 else 0
    out_tok = event.get("output_tokens") if type(event.get("output_tokens")) is int and event.get("output_tokens") >= 0 else 0

    if etype == "GENERIC" or role in _TOOL_ROLES or kind in _TOOL_ROLES or etype in _TOOL_ROLES or event.get("is_tool_output") is True:
        chunks: list[str] = []
        for field in ("content", "output", "tool_output", "text"):
            val = event.get(field)
            if val is not None:
                t_c, o_c = _extract_content_blocks(val, force_tool=True)
                chunks.extend(t_c)
                chunks.extend(o_c)
                if chunks:
                    break
        return True, is_checkpoint, "\n".join(chunks), "", in_tok, cache_tok, out_tok

    msg = event.get("message")
    if isinstance(msg, dict):
        usage = msg.get("usage")
        if isinstance(usage, dict):
            if type(usage.get("input_tokens")) is int and usage["input_tokens"] >= 0:
                in_tok += usage["input_tokens"]
            if type(usage.get("cache_read_input_tokens")) is int and usage["cache_read_input_tokens"] >= 0:
                cache_tok += usage["cache_read_input_tokens"]
            if type(usage.get("output_tokens")) is int and usage["output_tokens"] >= 0:
                out_tok += usage["output_tokens"]
        mc = msg.get("content")
        if isinstance(mc, list):
            tool_chunks, other_chunks = _extract_content_blocks(mc, force_tool=msg.get("role") in _TOOL_ROLES)
            return bool(tool_chunks), is_checkpoint, "\n".join(tool_chunks), "\n".join(other_chunks), in_tok, cache_tok, out_tok
        if type(mc) is str:
            is_t = msg.get("role") in _TOOL_ROLES
            return is_t, is_checkpoint, mc if is_t else "", "" if is_t else mc, in_tok, cache_tok, out_tok

    tool_parts: list[str] = []
    other_parts: list[str] = []
    for field in ("content", "thinking", "text"):
        val = event.get(field)
        if val is not None:
            t_c, o_c = _extract_content_blocks(val)
            tool_parts.extend(t_c)
            other_parts.extend(o_c)
    return bool(tool_parts), is_checkpoint, "\n".join(tool_parts), "\n".join(other_parts), in_tok, cache_tok, out_tok


def analyze_transcript_bloat_lines(
    lines: list[str],
    *,
    max_inline_lines: Any = 40,
    max_inline_chars: Any = 2400,
    max_inline_ratio_q: Any = Fraction(3, 10),
    allow_float: bool = False,
    session_label: str = "session",
) -> dict[str, Any]:
    """Deterministically compute CS-29 inline tool-output bloat statistics over JSONL lines."""
    _require(type(lines) is list and len(lines) > 0, "EMPTY_TRANSCRIPT", "transcript must contain >= 1 event")
    _require(type(session_label) is str and len(session_label.strip()) > 0, "INVALID_LABEL", "session_label must be non-empty str")
    m_lines = _require_exact_int(max_inline_lines, "max_inline_lines", 1)
    m_chars = _require_exact_int(max_inline_chars, "max_inline_chars", 1)
    ratio_thresh = _require_unit_fraction(max_inline_ratio_q, "max_inline_ratio_q")

    total_events = 0
    tool_output_events = 0
    inline_bloat_events = 0
    checkpoint_count = 0
    total_content_bytes = 0
    inline_tool_bytes = 0
    total_content_lines = 0
    inline_tool_lines = 0
    max_tool_lines = 0
    max_tool_bytes = 0
    input_tokens = 0
    cache_read_tokens = 0
    output_tokens = 0

    for lineno, raw_line in enumerate(lines, start=1):
        event = _loads_transcript_record(raw_line, lineno, allow_float=allow_float)
        total_events += 1
        is_tool, is_cp, tool_text, other_text, in_tok, cache_tok, out_tok = _extract_event_text_metrics(event)
        if is_cp:
            checkpoint_count += 1
        input_tokens += in_tok
        cache_read_tokens += cache_tok
        output_tokens += out_tok

        t_bytes = len(tool_text.encode("utf-8"))
        t_lines = _count_lf_lines(tool_text)
        o_bytes = len(other_text.encode("utf-8"))
        o_lines = _count_lf_lines(other_text)
        total_content_bytes += t_bytes + o_bytes
        total_content_lines += t_lines + o_lines

        if is_tool:
            tool_output_events += 1
            inline_tool_bytes += t_bytes
            inline_tool_lines += t_lines
            max_tool_lines = max(max_tool_lines, t_lines)
            max_tool_bytes = max(max_tool_bytes, t_bytes)
            if t_lines > m_lines or len(tool_text) > m_chars:
                inline_bloat_events += 1

    byte_ratio = Fraction(inline_tool_bytes, total_content_bytes) if total_content_bytes > 0 else Fraction(0, 1)
    line_ratio = Fraction(inline_tool_lines, total_content_lines) if total_content_lines > 0 else Fraction(0, 1)
    bloat_event_ratio = Fraction(inline_bloat_events, tool_output_events) if tool_output_events > 0 else Fraction(0, 1)
    total_in = input_tokens + cache_read_tokens
    cache_ratio = Fraction(cache_read_tokens, total_in) if total_in > 0 else Fraction(0, 1)

    exceeds_ratio = byte_ratio > ratio_thresh
    if exceeds_ratio and inline_bloat_events > 0:
        status = "ALERT"
    elif exceeds_ratio or inline_bloat_events > 0:
        status = "WARNING"
    else:
        status = "CLEAN"

    return {
        "schema": "aletheia.thin_coordinator.bloat.v1",
        "session_label": session_label,
        "status": status,
        "exceeds_ratio_threshold": exceeds_ratio,
        "thresholds": {
            "max_inline_lines": m_lines,
            "max_inline_chars": m_chars,
            "max_inline_ratio_q": _frac_str(ratio_thresh),
        },
        "counts": {
            "total_events": total_events,
            "tool_output_events": tool_output_events,
            "inline_bloat_events": inline_bloat_events,
            "checkpoint_count": checkpoint_count,
            "total_content_bytes": total_content_bytes,
            "inline_tool_output_bytes": inline_tool_bytes,
            "total_content_lines": total_content_lines,
            "inline_tool_output_lines": inline_tool_lines,
            "max_tool_output_lines": max_tool_lines,
            "max_tool_output_bytes": max_tool_bytes,
            "input_tokens": input_tokens,
            "cache_read_tokens": cache_read_tokens,
            "output_tokens": output_tokens,
        },
        "ratios": {
            "inline_tool_output_ratio_q": _frac_str(byte_ratio),
            "inline_tool_line_ratio_q": _frac_str(line_ratio),
            "inline_bloat_event_ratio_q": _frac_str(bloat_event_ratio),
            "cache_read_ratio_q": _frac_str(cache_ratio),
        },
    }


def analyze_transcript_bloat(
    transcript_path: Any,
    *,
    max_inline_lines: Any = 40,
    max_inline_chars: Any = 2400,
    max_inline_ratio_q: Any = Fraction(3, 10),
    max_file_bytes: Any = MAX_TRANSCRIPT_BYTES,
    allow_float: bool = False,
    session_label: str = "session",
) -> dict[str, Any]:
    """Fail-closed file reader and CS-29 bloat analyzer for a JSONL session transcript."""
    cap = _require_exact_int(max_file_bytes, "max_file_bytes", 1)
    raw = _zb.open_regular_file(
        transcript_path,
        "transcript",
        err_cls=ThinCoordinatorError,
        max_bytes=cap,
        too_large_code="TRANSCRIPT_TOO_LARGE",
    )
    text = _zb.decode_strict_utf8_bytes(
        raw,
        "transcript",
        err_cls=ThinCoordinatorError,
        bom_code="TRANSCRIPT_BOM_FORBIDDEN",
        crlf_code="TRANSCRIPT_CRLF_FORBIDDEN",
        require_crlf_only=True,
    )
    return analyze_transcript_bloat_lines(
        _split_lf_records(text),
        max_inline_lines=max_inline_lines,
        max_inline_chars=max_inline_chars,
        max_inline_ratio_q=max_inline_ratio_q,
        allow_float=allow_float,
        session_label=session_label,
    )
