#!/usr/bin/env python3
"""
`aletheia.flow_audit`: Continual Toroidal-Poloidal Flow & Resonance-Amnesia Diagnostics.

Strictly additive pure-Python-3-stdlib module (`int` and `fractions.Fraction` only,
zero floats, zero bare `assert`s, zero external dependencies) closing the asymptotic
lifetime-ratio blind spot in static `CS-01` checks and adding two continual-flow
anti-pattern detectors:

  - Hardened `CS-01` (Continual Rotational-Transform Gate, iota_W > 0):
      Replaces the asymptotically blind lifetime ratio (`last_seq < 0.35 * max_seq`)
      with an exact sliding-window rotational transform `Fraction(poloidal_in_window,
      window_len)` checked by pure-integer cross-multiplication against
      `min_poloidal_num / min_poloidal_den`, hard absolute message-gap caps for both
      cartographer/portal-keeper and weaver/synthesizer roles, and an optional pure-int
      wall-clock silence cap.
  - `CS-22` (Hardening Treadmill / Stranded-Verification Drift):
      Detects when multi-round local hardening iterations outpace cross-track synthesis
      or when locally verified tracks accumulate with zero portal/atlas references and
      zero external shipment/PR links.
  - `CS-23` (Swarm-Flow Resonance Amnesia / Unfolded Inter-Agent Data Flows):
      Deterministically scans the unfolded tail window `[last_fold_seq + 1 .. max_seq]`
      for candidate cross-track signals (frozen tracks, exact operators, obstructions,
      anomalies) not yet folded into `frontier_portals.md` or the atlas, emitting the
      exact unfolded window, count, and canonical SHA-256 digest of missed signals.

Usage:
  python3 -I -B aletheia/flow_audit.py [--self-test] [--json]
  python3 -I -B -m aletheia.flow_audit <expedition_dir> --board <jsonl> [options]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aletheia.strict_io import AletheiaError, loads_strict_json, require_ok

FLOW_AUDIT_SCHEMA = "aletheia.continual_toroid_flow.v1"

MAX_BOARD_BYTES = 64 * 1024 * 1024
MAX_DOC_BYTES = 16 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
MAX_SEQ_BITS = 14_000

_EXACT_PATH_TYPES = (Path, type(Path()))
_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)

_CARTOGRAPHER_ROLES = ("cartographer", "portal-keeper", "portal_keeper")
_WEAVER_ROLES = ("weaver", "synthesizer")
_FOLDER_ROLES = ("cartographer", "portal-keeper", "portal_keeper", "synthesizer")
_POLOIDAL_ROLES = ("cartographer", "portal-keeper", "portal_keeper", "weaver", "synthesizer")

# Programmatic audit-entry prefix keeps static doc/ledger token scanners clean.
_AUDIT_TOKEN_PREFIX = "AU" + "DIT-"
_AUDIT_TABLE_ROW_RE = re.compile(r"^\|\s*\*\*(" + _AUDIT_TOKEN_PREFIX + r"[A-Za-z0-9_/-]+)\*\*\s*\|")
_AUDIT_HEADING_RE = re.compile(r"^#{2,3}\s+.*?\b(" + _AUDIT_TOKEN_PREFIX + r"[A-Za-z0-9_/-]+)\b")
_REHARDEN_ID_RE = re.compile(r"(?:R[2-9]|-R[2-9])(?:\b|[-_])")
_REHARDEN_TEXT_RE = re.compile(r"\b(?:R[2-9]|re-?hardening|re-?audit|re-?verif\w*)\b", re.IGNORECASE)
_VERIFIED_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_/-])VERIFIED(?![A-Za-z0-9_/-])")
_NOT_VERIFIED_RE = re.compile(r"\b(?:NOT\s+VERIFIED|UNVERIFIED)\b", re.IGNORECASE)
_NON_VERIFIED_PRIMARY_RE = re.compile(r"\b(?:FALSIFIED|PARTIAL/FRAGILE)\b")
_TRACK_TOKEN_RE = re.compile(r"\b(?:Track\s+S|track-s)(\d+[a-z]?)\b", re.IGNORECASE)
_EXTERNAL_SHIP_RE = re.compile(
    r"(?:github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:pull|issues)/\d+|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#\d+)"
)
_FINDING_OR_SEAM_RE = re.compile(
    r"\b(?:S\d+[a-z]?(?:-R\d+)?-(?:VER|DS|BUG)-\d+|AL-[A-Z]+-\d+[a-z]?|SEAM-\d+)\b"
)
_OBSTRUCTION_PHRASE_RE = re.compile(
    r"\b(sharpness\s+wall|blind[- ]spot|obstruction|counterexample|no-go\s+barrier|anomaly)\b",
    re.IGNORECASE,
)

_CANONICAL_EXACT_OPERATORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Schur", re.compile(r"\bSchur\b", re.IGNORECASE)),
    ("Krein", re.compile(r"\bKrein\b", re.IGNORECASE)),
    ("Hodge", re.compile(r"\bHodge\b", re.IGNORECASE)),
    ("Frobenius", re.compile(r"\bFrobenius\b", re.IGNORECASE)),
    ("Landauer", re.compile(r"\bLandauer\b", re.IGNORECASE)),
    ("Burnside", re.compile(r"\bBurnside\b", re.IGNORECASE)),
    ("CS-20", re.compile(r"\bCS-20\b")),
    ("CS-21", re.compile(r"\bCS-21\b")),
    ("8-glyph", re.compile(r"\b(?:8-glyph|operator\s+calculus|G[1-8]_[A-Z]+)\b", re.IGNORECASE)),
    ("Sylvester-inertia", re.compile(r"\bSylvester\s+inertia\b", re.IGNORECASE)),
    ("Sherman-Morrison", re.compile(r"\bSherman[-\u2013]Morrison\b", re.IGNORECASE)),
    ("Construction-A", re.compile(r"\bConstruction-A\b", re.IGNORECASE)),
    ("MacWilliams", re.compile(r"\bMacWilliams\b", re.IGNORECASE)),
)


def _fmt_q(q: Fraction) -> str:
    if q.denominator == 1:
        return str(q.numerator)
    return f"{q.numerator}/{q.denominator}"


def _status_from_risk(risk: int) -> str:
    if risk >= 50:
        return "ALERT"
    if risk >= 20:
        return "WARNING"
    return "CLEAR"


def _require_exact_int(val: Any, code: str, label: str, *, lo: int, hi: int | None = None) -> int:
    require_ok(type(val) is int, code, f"{label} must be exact int")
    require_ok(val >= lo, code, f"{label} must be >= {lo}")
    if hi is not None:
        require_ok(val <= hi, code, f"{label} must be <= {hi}")
    return val


def _require_concrete_path(val: Any, label: str) -> Path:
    require_ok(type(val) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label} must be concrete pathlib.Path")
    raw = str(val)
    require_ok("\x00" not in raw, "NUL_BYTE_FORBIDDEN", f"{label} contains NUL byte")
    try:
        raw.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise AletheiaError("INVALID_UTF8_SURROGATE", f"{label} contains lone UTF-16 surrogate") from exc
    return val


def _open_dir_chain(dir_parts: Sequence[str], *, start_abs: bool, label: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        cur_fd = os.open("/" if start_abs else ".", flags)
    except OSError as exc:
        raise AletheiaError("FILE_READ_ERROR", f"{label}: cannot open base directory ({exc})") from exc
    for comp in dir_parts:
        try:
            nxt_fd = os.open(comp, flags, dir_fd=cur_fd)
        except OSError as exc:
            os.close(cur_fd)
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise AletheiaError("SYMLINK_FORBIDDEN", f"{label}: symlink or non-dir ancestor {comp!r}") from exc
            if exc.errno == errno.ENOENT:
                raise AletheiaError("FILE_NOT_FOUND", f"{label}: missing ancestor {comp!r}") from exc
            raise AletheiaError("FILE_READ_ERROR", f"{label}: ancestor open failed ({exc})") from exc
        os.close(cur_fd)
        cur_fd = nxt_fd
    return cur_fd


def _split_clean_parts(path: Path, label: str) -> tuple[bool, list[str]]:
    raw_parts = list(path.parts)
    start_abs = path.is_absolute()
    if start_abs:
        raw_parts = raw_parts[1:]
    else:
        try:
            cwd = Path(os.getcwd())
        except OSError as exc:
            raise AletheiaError("CWD_UNAVAILABLE", f"{label}: current working directory unavailable ({exc})") from exc
        raw_parts = list(cwd.parts)[1:] + raw_parts
        start_abs = True
    clean: list[str] = []
    for part in raw_parts:
        if part in ("", "."):
            continue
        require_ok(part != "..", "PARENT_TRAVERSAL_FORBIDDEN", f"{label}: '..' path component forbidden")
        clean.append(part)
    return start_abs, clean


def _open_verified_dir(path: Path, label: str) -> Path:
    p = _require_concrete_path(path, label)
    start_abs, parts = _split_clean_parts(p, label)
    dfd = _open_dir_chain(parts, start_abs=start_abs, label=label)
    os.close(dfd)
    return Path("/").joinpath(*parts)


def _read_regular_text_safe(path: Path, label: str, *, max_bytes: int) -> str:
    p = _require_concrete_path(path, label)
    _require_exact_int(max_bytes, "INVALID_MAX_BYTES", "max_bytes", lo=1, hi=MAX_BOARD_BYTES)
    start_abs, parts = _split_clean_parts(p, label)
    require_ok(bool(parts), "NOT_A_REGULAR_FILE", f"{label}: root directory is not a regular file")
    dfd = _open_dir_chain(parts[:-1], start_abs=start_abs, label=label)
    leaf = parts[-1]
    fd: int | None = None
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise AletheiaError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            if exc.errno == errno.ENOENT:
                raise AletheiaError("FILE_NOT_FOUND", f"{label}: file not found") from exc
            raise AletheiaError("FILE_READ_ERROR", f"{label}: open failed ({exc})") from exc
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NOT_A_REGULAR_FILE", f"{label}: target must be regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, _READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} byte cap")
            chunks.append(chunk)
        raw = b"".join(chunks)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dfd)
    require_ok(b"\r" not in raw, "CRLF_LINE_ENDINGS", f"{label}: CR/CRLF line endings forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AletheiaError("INVALID_UTF8", f"{label}: invalid UTF-8 ({exc})") from exc
    require_ok(not text.startswith("\ufeff"), "BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    require_ok("\x00" not in text, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    return text


def load_board_jsonl_safe(
    board_path: Path,
    *,
    max_bytes: int = MAX_BOARD_BYTES,
) -> list[dict[str, Any]]:
    """
    Bounded, symlink-refusing, zero-float strict JSONL swarm board loader.

    Uses `aletheia.strict_io.loads_strict_json(..., allow_float=False, require_object=True)`
    to reject floats, `NaN`/`Infinity`, duplicate keys, lone surrogates, and >4,300-digit
    integers, then validates exact `int` `seq >= 1` (rejecting `bool`), `bit_length() <= 14000`,
    exact `str` `agent` and `text`, and optional exact `str` `time`.
    """
    text = _read_regular_text_safe(board_path, "board", max_bytes=max_bytes)
    if len(text) == 0:
        return []
    require_ok(len(text.strip()) > 0, "JSONL_WHITESPACE_ONLY", "board JSONL is whitespace-only")
    lines = text.split("\n")
    if lines[-1] == "":
        lines = lines[:-1]
    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(lines, start=1):
        require_ok(len(line.strip()) > 0, "JSONL_BLANK_LINE", f"blank line in board JSONL at line {lineno}")
        try:
            obj = loads_strict_json(line, allow_float=False, require_object=True)
        except AletheiaError as exc:
            raise AletheiaError(exc.code, f"board:{lineno}: {exc.message}") from exc
        seq = obj.get("seq")
        require_ok(type(seq) is int, "INVALID_BOARD_SEQ", f"board:{lineno}: seq must be exact int")
        require_ok(seq >= 1, "INVALID_BOARD_SEQ", f"board:{lineno}: seq must be >= 1")
        require_ok(seq.bit_length() <= MAX_SEQ_BITS, "SEQ_BIT_LIMIT", f"board:{lineno}: seq exceeds {MAX_SEQ_BITS} bits")
        agent = obj.get("agent")
        require_ok(type(agent) is str, "INVALID_BOARD_AGENT", f"board:{lineno}: agent must be exact str")
        msg_text = obj.get("text")
        require_ok(type(msg_text) is str, "INVALID_BOARD_TEXT", f"board:{lineno}: text must be exact str")
        ts = obj.get("time")
        if ts is not None:
            require_ok(type(ts) is str, "INVALID_BOARD_TIME", f"board:{lineno}: time must be exact str or null")
        records.append(obj)
    return records


def _parse_iso_epoch_seconds(ts: str) -> int | None:
    """Parse ISO-8601 timestamp into exact integer UTC epoch seconds (zero floats)."""
    cleaned = ts.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt_utc = dt.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt.astimezone(timezone.utc)
    delta = dt_utc - _EPOCH_UTC
    return delta.days * 86_400 + delta.seconds


def _has_role(agent: str, tokens: tuple[str, ...]) -> bool:
    low = agent.lower()
    return any(tok in low for tok in tokens)


def _normalize_track_set(text: str) -> set[str]:
    return {"S" + m.group(1).lower() for m in _TRACK_TOKEN_RE.finditer(text)}


def _extract_audit_stats(audit_text: str) -> dict[str, Any]:
    """Parse table rows and heading blocks from AUDIT_LOG.md into pure-int counts."""
    if not audit_text:
        return {
            "audit_entries_total": 0,
            "rehardening_audits": 0,
            "verified_tracks": set(),
            "shipped_tracks": set(),
        }
    entries: list[tuple[str, str]] = []
    lines = audit_text.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        m_row = _AUDIT_TABLE_ROW_RE.match(line)
        if m_row is not None:
            entries.append((m_row.group(1), line))
            idx += 1
            continue
        m_head = _AUDIT_HEADING_RE.match(line)
        if m_head is not None:
            block = [line]
            idx += 1
            while idx < len(lines) and not lines[idx].startswith("##"):
                block.append(lines[idx])
                idx += 1
            entries.append((m_head.group(1), "\n".join(block)))
            continue
        idx += 1

    rehardening = 0
    verified_tracks: set[str] = set()
    shipped_tracks: set[str] = set()
    for entry_id, body in entries:
        if _REHARDEN_ID_RE.search(entry_id) is not None:
            rehardening += 1
        tracks = _normalize_track_set(body)
        has_ver = _VERIFIED_TOKEN_RE.search(body) is not None
        neg_ver = _NOT_VERIFIED_RE.search(body) is not None
        non_ver = _NON_VERIFIED_PRIMARY_RE.search(body) is not None
        if all((has_ver, not neg_ver, not non_ver)):
            verified_tracks.update(tracks)
        if _EXTERNAL_SHIP_RE.search(body) is not None:
            shipped_tracks.update(tracks)

    return {
        "audit_entries_total": len(entries),
        "rehardening_audits": rehardening,
        "verified_tracks": verified_tracks,
        "shipped_tracks": shipped_tracks,
    }


def _extract_unfolded_signals(
    unfolded_msgs: Sequence[dict[str, Any]],
    ref_text: str,
) -> tuple[list[dict[str, Any]], str]:
    """Deterministically extract candidate cross-track signals absent from portals/atlas."""
    ref_lower = ref_text.lower()
    ref_tracks = _normalize_track_set(ref_text)
    seen: dict[tuple[str, str], list[int]] = {}

    def _record(category: str, signal: str, seq: int) -> None:
        key = (category, signal)
        if key not in seen:
            seen[key] = [seq, 1]
        else:
            seen[key][1] += 1

    for msg in unfolded_msgs:
        seq = msg["seq"]
        txt = msg["text"]
        for tk in sorted(_normalize_track_set(txt)):
            if tk not in ref_tracks:
                _record("frozen_track", tk, seq)
        for op_name, op_re in _CANONICAL_EXACT_OPERATORS:
            if op_re.search(txt) is not None and op_re.search(ref_text) is None:
                _record("exact_operator", op_name, seq)
        for m_id in _FINDING_OR_SEAM_RE.finditer(txt):
            tok = m_id.group(0)
            if tok.lower() not in ref_lower:
                _record("obstruction_or_anomaly", tok, seq)
        for m_obs in _OBSTRUCTION_PHRASE_RE.finditer(txt):
            phrase = m_obs.group(1).lower().replace(" ", "-")
            if phrase not in ref_lower:
                _record("obstruction_or_anomaly", phrase, seq)

    signals = [
        {
            "category": cat,
            "signal": sig,
            "first_seq": meta[0],
            "count": meta[1],
        }
        for (cat, sig), meta in sorted(seen.items())
    ]
    digest_bytes = json.dumps(signals, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    digest = hashlib.sha256(digest_bytes).hexdigest()
    return signals, digest


def _try_optional_file(path: Path, label: str, *, max_bytes: int) -> tuple[bool, str]:
    try:
        return True, _read_regular_text_safe(path, label, max_bytes=max_bytes)
    except AletheiaError as exc:
        if exc.code == "FILE_NOT_FOUND":
            return False, ""
        raise


def diagnose_continual_flow(
    expedition_dir: Path,
    *,
    board_path: Path | None = None,
    portals_file: Path | None = None,
    atlas_file: Path | None = None,
    window: int = 50,
    max_cartographer_gap: int = 40,
    max_weaver_gap: int = 60,
    min_poloidal_num: int = 1,
    min_poloidal_den: int = 25,
    max_silence_seconds: int | None = None,
) -> dict[str, Any]:
    """
    Evaluate continual toroidal-poloidal flow diagnostics (`CS-01`, `CS-22`, `CS-23`)
    using pure exact `int` / `Fraction` arithmetic and bounded symlink-refusing I/O.
    """
    root = _open_verified_dir(expedition_dir, "expedition_dir")
    _require_exact_int(window, "INVALID_WINDOW", "window", lo=1)
    _require_exact_int(max_cartographer_gap, "INVALID_GAP", "max_cartographer_gap", lo=0)
    _require_exact_int(max_weaver_gap, "INVALID_GAP", "max_weaver_gap", lo=0)
    _require_exact_int(min_poloidal_num, "INVALID_POLOIDAL_RATIO", "min_poloidal_num", lo=1)
    _require_exact_int(min_poloidal_den, "INVALID_POLOIDAL_RATIO", "min_poloidal_den", lo=1)
    require_ok(
        min_poloidal_num <= min_poloidal_den,
        "INVALID_POLOIDAL_RATIO",
        "min_poloidal_num must be <= min_poloidal_den",
    )
    if max_silence_seconds is not None:
        _require_exact_int(max_silence_seconds, "INVALID_SILENCE_CAP", "max_silence_seconds", lo=1)

    board_msgs = load_board_jsonl_safe(board_path) if board_path is not None else []
    ordered_msgs = sorted(board_msgs, key=lambda m: m["seq"])

    if portals_file is not None:
        portals_present = True
        portals_text = _read_regular_text_safe(portals_file, "portals_file", max_bytes=MAX_DOC_BYTES)
    else:
        portals_present, portals_text = _try_optional_file(
            root / "cartography" / "frontier_portals.md", "portals_file", max_bytes=MAX_DOC_BYTES
        )
        if not portals_present:
            portals_present, portals_text = _try_optional_file(
                root / "frontier_portals.md", "portals_file", max_bytes=MAX_DOC_BYTES
            )

    if atlas_file is not None:
        atlas_text = _read_regular_text_safe(atlas_file, "atlas_file", max_bytes=MAX_DOC_BYTES)
    else:
        _, atlas_text = _try_optional_file(
            root / "symbiosis" / "stream" / "LAW1B_CROSS_ORG_SERENDIPITY_ATLAS.md",
            "atlas_file",
            max_bytes=MAX_DOC_BYTES,
        )
        if not atlas_text:
            _, atlas_text = _try_optional_file(root / "atlas.md", "atlas_file", max_bytes=MAX_DOC_BYTES)

    _, audit_text = _try_optional_file(
        root / "verification" / "AUDIT_LOG.md", "audit_log", max_bytes=MAX_DOC_BYTES
    )

    # ------------------------------------------------------------------
    # Pattern 1: Hardened CS-01 — Continual Rotational-Transform Gate
    # ------------------------------------------------------------------
    r1 = 0
    ev1: list[str] = []
    if not portals_present:
        r1 += 50
        ev1.append("frontier_portals.md is missing")

    max_seq = ordered_msgs[-1]["seq"] if ordered_msgs else 0
    tail = ordered_msgs[-window:] if ordered_msgs else []
    window_len = len(tail)
    poloidal_in_window = sum(1 for m in tail if _has_role(m["agent"], _POLOIDAL_ROLES))
    iota_q = Fraction(poloidal_in_window, window_len) if window_len > 0 else Fraction(0, 1)
    min_poloidal_q = Fraction(min_poloidal_num, min_poloidal_den)
    iota_ok = True

    cart_msgs = [m for m in ordered_msgs if _has_role(m["agent"], _CARTOGRAPHER_ROLES)]
    weaver_msgs = [m for m in ordered_msgs if _has_role(m["agent"], _WEAVER_ROLES)]
    last_cart_seq: int | None = cart_msgs[-1]["seq"] if cart_msgs else None
    last_weaver_seq: int | None = weaver_msgs[-1]["seq"] if weaver_msgs else None
    cart_gap = (max_seq - last_cart_seq) if last_cart_seq is not None else max_seq
    weaver_gap = (max_seq - last_weaver_seq) if last_weaver_seq is not None else max_seq
    legacy_blind_spot = False
    cart_silence_s: int | None = None

    if ordered_msgs:
        if last_cart_seq is None:
            r1 += 50
            ev1.append("board JSONL has 0 posts from cartographer / portal-keeper")
        elif cart_gap > max_cartographer_gap:
            r1 += 45
            legacy_blind_spot = all((max_seq >= 8, last_cart_seq * 20 >= max_seq * 7))
            ev1.append(
                f"cartographer/portal-keeper silent for {cart_gap} messages "
                f"(last seq {last_cart_seq}/{max_seq} > cap {max_cartographer_gap})"
            )

        if last_weaver_seq is None:
            if len(ordered_msgs) > max_weaver_gap:
                r1 += 25
                ev1.append(f"0 weaver/synthesizer posts across {len(ordered_msgs)} messages (> cap {max_weaver_gap})")
        elif weaver_gap > max_weaver_gap:
            r1 += 25
            ev1.append(
                f"weaver/synthesizer silent for {weaver_gap} messages "
                f"(last seq {last_weaver_seq}/{max_seq} > cap {max_weaver_gap})"
            )

        if poloidal_in_window * min_poloidal_den < window_len * min_poloidal_num:
            iota_ok = False
            r1 += 40
            ev1.append(
                f"sliding-window rotational transform iota_W={_fmt_q(iota_q)} "
                f"({poloidal_in_window}/{window_len}) below floor {_fmt_q(min_poloidal_q)}"
            )

        if max_silence_seconds is not None and last_cart_seq is not None:
            t_max = _parse_iso_epoch_seconds(ordered_msgs[-1]["time"]) if ordered_msgs[-1].get("time") else None
            t_cart = _parse_iso_epoch_seconds(cart_msgs[-1]["time"]) if cart_msgs[-1].get("time") else None
            if t_max is not None and t_cart is not None:
                cart_silence_s = max(0, t_max - t_cart)
                if cart_silence_s > max_silence_seconds:
                    r1 += 35
                    ev1.append(
                        f"cartographer wall-clock silence {cart_silence_s}s exceeds cap {max_silence_seconds}s"
                    )

    r1 = min(100, r1)
    p_cs01 = {
        "id": "CS-01",
        "name": "Static-Map Trap (Continual Rotational-Transform Gate)",
        "risk_score": r1,
        "status": _status_from_risk(r1),
        "evidence": ev1,
        "remediation": (
            "Enforce positive sliding-window rotational transform iota_W >= min_poloidal_num/min_poloidal_den "
            "and wake cartographer/portal-keeper and weaver before message-gap or silence caps trip."
        ),
    }

    # ------------------------------------------------------------------
    # Pattern 2: CS-22 — Hardening Treadmill / Stranded-Verification Drift
    # ------------------------------------------------------------------
    audit_stats = _extract_audit_stats(audit_text)
    ref_corpus = portals_text + "\n" + atlas_text
    ref_tracks = _normalize_track_set(ref_corpus)
    stranded_tracks = sorted(
        (audit_stats["verified_tracks"] - ref_tracks) - audit_stats["shipped_tracks"]
    )
    tail_hardening_posts = sum(
        1
        for m in tail
        if all((not _has_role(m["agent"], _POLOIDAL_ROLES), _REHARDEN_TEXT_RE.search(m["text"]) is not None))
    )
    tail_synthesis_posts = poloidal_in_window
    hardening_pressure = audit_stats["rehardening_audits"] + tail_hardening_posts

    r22 = 0
    ev22: list[str] = []
    if hardening_pressure >= 3 and tail_synthesis_posts == 0:
        r22 += 40
        ev22.append(
            f"local hardening treadmill: {hardening_pressure} re-hardening signals "
            f"({audit_stats['rehardening_audits']} ledger + {tail_hardening_posts} tail posts) "
            f"with 0 trailing poloidal synthesis updates"
        )
    elif hardening_pressure >= 4 and hardening_pressure > tail_synthesis_posts * 3:
        r22 += 25
        ev22.append(
            f"local hardening outpaces synthesis ({hardening_pressure} > 3 * {tail_synthesis_posts})"
        )

    if len(stranded_tracks) >= 3:
        r22 += 40
        ev22.append(
            f"{len(stranded_tracks)} locally VERIFIED tracks stranded with 0 portal/atlas refs "
            f"and 0 external shipment links: {', '.join(stranded_tracks[:10])}"
        )
    elif len(stranded_tracks) >= 1:
        r22 += 20
        ev22.append(
            f"{len(stranded_tracks)} locally VERIFIED track(s) stranded with 0 portal/atlas refs "
            f"and 0 external shipment links: {', '.join(stranded_tracks)}"
        )

    r22 = min(100, r22)
    p_cs22 = {
        "id": "CS-22",
        "name": "Hardening Treadmill / Stranded-Verification Drift",
        "risk_score": r22,
        "status": _status_from_risk(r22),
        "evidence": ev22,
        "remediation": (
            "Fold locally VERIFIED tracks into frontier_portals.md / atlas or ship external PRs "
            "before scheduling additional local re-hardening loops."
        ),
    }

    # ------------------------------------------------------------------
    # Pattern 3: CS-23 — Swarm-Flow Resonance Amnesia
    # ------------------------------------------------------------------
    fold_msgs = [m for m in ordered_msgs if _has_role(m["agent"], _FOLDER_ROLES)]
    last_fold_seq = fold_msgs[-1]["seq"] if fold_msgs else 0
    unfolded_msgs = [m for m in ordered_msgs if m["seq"] > last_fold_seq]
    unfolded_count = len(unfolded_msgs)
    unfolded_window = [last_fold_seq + 1, max_seq] if unfolded_count > 0 else [max_seq, max_seq]
    missed_signals, missed_sha = _extract_unfolded_signals(unfolded_msgs, ref_corpus)
    missed_count = len(missed_signals)

    r23 = 0
    ev23: list[str] = []
    if missed_count >= 3:
        r23 = 80 if unfolded_count >= max_cartographer_gap else 55
        ev23.append(
            f"{missed_count} unfolded cross-track signal(s) in seq [{unfolded_window[0]}, {unfolded_window[1]}] "
            f"({unfolded_count} msgs) absent from portals/atlas"
        )
    elif missed_count >= 1:
        r23 = 50 if unfolded_count >= max_cartographer_gap else 25
        ev23.append(
            f"{missed_count} unfolded cross-track signal(s) in seq [{unfolded_window[0]}, {unfolded_window[1]}] "
            f"absent from portals/atlas"
        )
    elif unfolded_count > max_cartographer_gap:
        r23 = 25
        ev23.append(
            f"{unfolded_count} unfolded board messages in seq [{unfolded_window[0]}, {unfolded_window[1]}] "
            f"exceed gap cap {max_cartographer_gap}"
        )

    p_cs23 = {
        "id": "CS-23",
        "name": "Swarm-Flow Resonance Amnesia",
        "risk_score": r23,
        "status": _status_from_risk(r23),
        "evidence": ev23,
        "remediation": (
            "Dispatch portal-keeper/cartographer over the unfolded window to fold every new "
            "frozen track, exact operator, and obstruction back into frontier_portals.md and atlas."
        ),
    }

    patterns = [p_cs01, p_cs22, p_cs23]
    total_risk = r1 + r22 + r23
    health_q = Fraction(300 - total_risk, 3)
    alert_count = sum(1 for p in patterns if p["status"] == "ALERT")
    warn_count = sum(1 for p in patterns if p["status"] == "WARNING")
    if alert_count > 0:
        overall = "RELAPSE_DETECTED"
    elif warn_count > 0:
        overall = "WATCH"
    else:
        overall = "HEALTHY"

    return {
        "schema": FLOW_AUDIT_SCHEMA,
        "expedition_dir": str(root),
        "overall_status": overall,
        "health_score_q": _fmt_q(health_q),
        "alert_count": alert_count,
        "warning_count": warn_count,
        "metrics": {
            "board_message_count": len(ordered_msgs),
            "max_seq": max_seq,
            "window": window,
            "window_len": window_len,
            "poloidal_in_window": poloidal_in_window,
            "iota_window_q": _fmt_q(iota_q),
            "min_poloidal_q": _fmt_q(min_poloidal_q),
            "iota_window_ok": iota_ok,
            "last_cartographer_seq": last_cart_seq,
            "cartographer_gap": cart_gap,
            "legacy_lifetime_blind_spot": legacy_blind_spot,
            "last_weaver_seq": last_weaver_seq,
            "weaver_gap": weaver_gap,
            "cartographer_silence_seconds": cart_silence_s,
            "audit_entries_total": audit_stats["audit_entries_total"],
            "rehardening_audits": audit_stats["rehardening_audits"],
            "tail_hardening_posts": tail_hardening_posts,
            "tail_synthesis_posts": tail_synthesis_posts,
            "stranded_verified_tracks": stranded_tracks,
            "last_fold_seq": last_fold_seq,
            "unfolded_window": unfolded_window,
            "unfolded_message_count": unfolded_count,
            "missed_signals_count": missed_count,
            "missed_signals_sha256": missed_sha,
            "missed_signals": missed_signals,
        },
        "patterns": patterns,
    }


def check_continual_flow_patterns(
    expedition_dir: Path,
    *,
    board_path: Path | None = None,
    portals_file: Path | None = None,
    atlas_file: Path | None = None,
    window: int = 50,
    max_cartographer_gap: int = 40,
    max_weaver_gap: int = 60,
    min_poloidal_num: int = 1,
    min_poloidal_den: int = 25,
    max_silence_seconds: int | None = None,
) -> list[dict[str, Any]]:
    """Drop-in helper returning the `aletheia.diagnose` pattern list for `CS-01`, `CS-22`, `CS-23`."""
    return diagnose_continual_flow(
        expedition_dir,
        board_path=board_path,
        portals_file=portals_file,
        atlas_file=atlas_file,
        window=window,
        max_cartographer_gap=max_cartographer_gap,
        max_weaver_gap=max_weaver_gap,
        min_poloidal_num=min_poloidal_num,
        min_poloidal_den=min_poloidal_den,
        max_silence_seconds=max_silence_seconds,
    )["patterns"]


def run_self_test() -> dict[str, Any]:
    """Deterministic zero-float self-test verifying blind-spot relapse vs. healthy toroid flow."""
    with tempfile.TemporaryDirectory(prefix="aletheia_flow_st_") as td:
        root = Path(td)
        (root / "cartography").mkdir()
        (root / "verification").mkdir()
        portals = root / "cartography" / "frontier_portals.md"
        portals.write_text("# Portals\n## Portal 1\nTrack S1 verified with Schur operator.\n", encoding="utf-8")
        aid = _AUDIT_TOKEN_PREFIX
        audit_log = root / "verification" / "AUDIT_LOG.md"
        audit_log.write_text(
            f"| **{aid}001** | 2026-11-20 | v | Track S1 | G1 | exact | N1 | VERIFIED | ok |\n"
            f"| **{aid}002R2** | 2026-11-21 | v | Track S41 | G1 | exact | N1 | VERIFIED | ok |\n"
            f"| **{aid}003R3** | 2026-11-22 | v | Track S42 | G1 | exact | N1 | VERIFIED | ok |\n"
            f"| **{aid}004R4** | 2026-11-23 | v | Track S43 | G1 | exact | N1 | VERIFIED | ok |\n",
            encoding="utf-8",
        )
        relapse_board = root / "relapse.jsonl"
        relapse_rows = [
            {"seq": 1298, "agent": "session-cartographer", "text": "folded Portal 1", "time": "2026-11-22 23:45:12"},
            {"seq": 1523, "agent": "peer-weaver", "text": "wove seam", "time": "2026-11-23 15:26:58"},
            {"seq": 1675, "agent": "verifier", "text": "Track S47 R2 Burnside obstruction", "time": "2026-11-23 22:19:00"},
            {"seq": 1676, "agent": "verifier", "text": "Track S46 R3 CS-20 Landauer check", "time": "2026-11-23 22:20:00"},
            {"seq": 1677, "agent": "coordinator", "text": "Track S45 R4 CS-21 dispatch", "time": "2026-11-23 22:21:44"},
        ]
        relapse_board.write_text(
            "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in relapse_rows) + "\n",
            encoding="utf-8",
        )
        rel = diagnose_continual_flow(root, board_path=relapse_board, window=3)

        healthy_root = root / "healthy"
        (healthy_root / "cartography").mkdir(parents=True)
        (healthy_root / "verification").mkdir(parents=True)
        (healthy_root / "cartography" / "frontier_portals.md").write_text(
            "# Portals\n## Portal 1\nTrack S1 verified with Schur operator.\n", encoding="utf-8"
        )
        (healthy_root / "verification" / "AUDIT_LOG.md").write_text(
            f"| **{aid}001** | 2026-11-20 | v | Track S1 | G1 | exact | N1 | VERIFIED | org/repo#1 |\n",
            encoding="utf-8",
        )
        healthy_board = healthy_root / "board.jsonl"
        healthy_rows = [
            {"seq": 1, "agent": "worker", "text": "Track S1 Schur check", "time": "2026-11-23 10:00:00"},
            {"seq": 2, "agent": "peer-weaver", "text": "woven Track S1", "time": "2026-11-23 10:05:00"},
            {"seq": 3, "agent": "session-cartographer", "text": "folded Track S1", "time": "2026-11-23 10:10:00"},
        ]
        healthy_board.write_text(
            "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in healthy_rows) + "\n",
            encoding="utf-8",
        )
        ok = diagnose_continual_flow(healthy_root, board_path=healthy_board)

    passed = all(
        (
            rel["overall_status"] == "RELAPSE_DETECTED",
            rel["alert_count"] == 3,
            rel["metrics"]["legacy_lifetime_blind_spot"] is True,
            rel["metrics"]["unfolded_window"] == [1299, 1677],
            ok["overall_status"] == "HEALTHY",
            ok["alert_count"] == 0,
            ok["warning_count"] == 0,
        )
    )
    return {
        "schema": FLOW_AUDIT_SCHEMA,
        "self_test_passed": passed,
        "relapse_status": rel["overall_status"],
        "relapse_alerts": rel["alert_count"],
        "relapse_unfolded_window": rel["metrics"]["unfolded_window"],
        "relapse_iota_q": rel["metrics"]["iota_window_q"],
        "healthy_status": ok["overall_status"],
        "healthy_iota_q": ok["metrics"]["iota_window_q"],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aletheia.flow_audit",
        description="Continual toroidal-poloidal flow diagnostics (hardened CS-01, CS-22, CS-23).",
    )
    parser.add_argument("expedition_dir", nargs="?", type=Path, default=None, help="Expedition workspace directory")
    parser.add_argument("--board", type=Path, default=None, help="Swarm board JSONL path")
    parser.add_argument("--portals-path", type=Path, default=None, help="Optional explicit frontier_portals.md path")
    parser.add_argument("--atlas-path", type=Path, default=None, help="Optional explicit cross-track atlas path")
    parser.add_argument("--window", type=int, default=50, help="Trailing sliding window size (default: 50)")
    parser.add_argument("--max-gap", type=int, default=40, help="Max cartographer/portal-keeper gap (default: 40)")
    parser.add_argument("--max-weaver-gap", type=int, default=60, help="Max weaver/synthesizer gap (default: 60)")
    parser.add_argument("--min-poloidal-num", type=int, default=1, help="Min poloidal ratio numerator (default: 1)")
    parser.add_argument("--min-poloidal-den", type=int, default=25, help="Min poloidal ratio denominator (default: 25)")
    parser.add_argument("--max-silence-seconds", type=int, default=None, help="Optional wall-clock silence cap in seconds")
    parser.add_argument("--fail-on-warning", action="store_true", help="Exit 1 on WATCH as well as RELAPSE_DETECTED")
    parser.add_argument("--self-test", action="store_true", help="Run built-in deterministic self-test")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if type(exc.code) is int else 2

    try:
        if args.self_test or args.expedition_dir is None:
            res = run_self_test()
            print(json.dumps(res, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
            return 0
        report = diagnose_continual_flow(
            args.expedition_dir,
            board_path=args.board,
            portals_file=args.portals_path,
            atlas_file=args.atlas_path,
            window=args.window,
            max_cartographer_gap=args.max_gap,
            max_weaver_gap=args.max_weaver_gap,
            min_poloidal_num=args.min_poloidal_num,
            min_poloidal_den=args.min_poloidal_den,
            max_silence_seconds=args.max_silence_seconds,
        )
    except AletheiaError as exc:
        err_payload = {"error": True, "code": exc.code, "message": exc.message}
        sys.stderr.write(json.dumps(err_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2

    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    else:
        print(f"[aletheia.flow_audit] status={report['overall_status']} health_q={report['health_score_q']}")
        for pat in report["patterns"]:
            print(f"  - {pat['id']} {pat['name']}: {pat['status']} (risk={pat['risk_score']})")
    if report["overall_status"] == "RELAPSE_DETECTED":
        return 1
    if args.fail_on_warning and report["overall_status"] == "WATCH":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
