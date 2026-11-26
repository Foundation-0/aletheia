"""
Machine-checked coupling between the two sibling repos (`aletheia` and `cave-expedition`).

Each repo makes claims about the other (audit ids, check-script counts, N2 sets, licence text,
CI). `run_twin_check` evaluates a fixed, named set of checks over both repo roots against a
reviewed contract (`spec/twin_contract.json`) and returns a machine-readable report.

Status vocabulary per check:
  OK       the claim holds
  DRIFT    the claim is false and nothing declares it pending (fails the run)
  PENDING  the claim is false for a declared, tracked reason (never fails the run)
  SKIP     a required repo root is absent (never fails the run)

Pure standard library, no network, no bare asserts (python3 -O safe).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, Callable, Mapping

from .audit_check import _VERDICT_TOKEN_RE, _split_audit_table_row
from .scaffold import _symlink_offenders
from .strict_io import AletheiaError, load_strict_json_file, require_ok

TWIN_REPORT_SCHEMA = "aletheia.twin_report.v1"
TWIN_CONTRACT_SCHEMA = "aletheia.twin_contract.v1"

OK = "OK"
DRIFT = "DRIFT"
PENDING = "PENDING"
SKIP = "SKIP"
STATUSES = (OK, DRIFT, PENDING, SKIP)

CONTRACT_REL = "spec/twin_contract.json"
CAVE_SIBLING_NAME = "cave-expedition"

_SUFFIX = r"[A-Z]\d*[a-z]?"
_ID_PART = re.compile(rf"^AUDIT-(\d{{3}})({_SUFFIX})?$")
_BARE_PART = re.compile(rf"^(\d{{3}})({_SUFFIX})?$")
_LEDGER_ROW = re.compile(r"^\|\s*\*\*(AUDIT-[^*|]*)\*\*\s*\|")
_CITE = re.compile(
    rf"AUDIT-(?P<n1>\d{{3}})(?!\d)(?P<s1>{_SUFFIX})?"
    rf"(?P<more>(?:/\d{{3}}(?!\d)(?:{_SUFFIX})?)*)"
    rf"(?:[`*\s]*(?:\u2013|\u2014|\.\.|-)[`*\s]*(?:AUDIT-)?(?P<n2>\d{{3}})(?!\d)(?P<s2>{_SUFFIX})?)?"
)
_MORE_PART = re.compile(rf"/(\d{{3}})({_SUFFIX})?")
_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
_NOT_VERIFIED = re.compile(r"\bNOT\s+VERIFIED\b", re.IGNORECASE)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}


class _InputError(Exception):
    """A repo file a check needs is missing or unreadable: reported as DRIFT, not a crash."""


class _Ctx:
    def __init__(self, aletheia: Path | None, cave: Path | None, spec: Mapping[str, Any]) -> None:
        self.aletheia = aletheia
        self.cave = cave
        self.spec = spec

    @property
    def expected(self) -> Mapping[str, Any]:
        return self.spec["expected"]

    @property
    def locator(self) -> Mapping[str, Any]:
        return self.spec.get("locator", {})

    @property
    def pending(self) -> list[Mapping[str, Any]]:
        return list(self.spec.get("pending", []))


def _result(
    status: str,
    expected: Any,
    actual: Any,
    note: str,
    evidence: Any = None,
    tracking: list[str] | None = None,
    clears_when: str = "",
) -> dict[str, Any]:
    return {
        "status": status,
        "expected": expected,
        "actual": actual,
        "note": note,
        "evidence": evidence if evidence is not None else {},
        "tracking": list(tracking or []),
        "clears_when": clears_when,
    }


def _safe_rel(rel: str) -> PurePosixPath:
    pure = PurePosixPath(rel)
    require_ok(
        isinstance(rel, str) and len(rel) > 0 and not pure.is_absolute() and ".." not in pure.parts,
        "TWIN_CONTRACT_BAD_PATH",
        f"contract path must be a relative path without '..': {rel!r}",
    )
    return pure


def _repo_path(root: Path, rel: str) -> Path:
    """Resolve rel under root; refuse symlinked components, non-regular files, and paths outside root."""
    rel_posix = _safe_rel(rel).as_posix()
    offenders = _symlink_offenders(root, [rel_posix])
    if offenders:
        raise _InputError(
            f"refusing symlinked path component {offenders[0]!r} under {rel} (never follow links out of the repo root)",
        )
    path = root.joinpath(*PurePosixPath(rel_posix).parts)
    try:
        st = os.lstat(path)
    except OSError as exc:
        raise _InputError(f"missing or unreadable file: {rel} ({exc.strerror or exc})") from exc
    if stat.S_ISLNK(st.st_mode):
        raise _InputError(f"refusing symlinked file: {rel}")
    if not stat.S_ISREG(st.st_mode):
        raise _InputError(f"refusing non-regular file: {rel}")
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
    except OSError as exc:
        raise _InputError(f"cannot resolve path for {rel}: {exc.strerror or exc}") from exc
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise _InputError(f"path resolves outside repo root: {rel}")
    return path


def _read_text(root: Path, rel: str) -> str:
    path = _repo_path(root, rel)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _InputError(f"unreadable file {rel}: {exc.strerror or exc}") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _InputError(f"file is not valid UTF-8: {rel}") from exc


def _read_json(root: Path, rel: str) -> Any:
    path = _repo_path(root, rel)
    try:
        return load_strict_json_file(path, allow_float=True, require_object=False)
    except AletheiaError as exc:
        raise _InputError(f"invalid JSON in {rel}: {exc}") from exc


def _glob(root: Path, pattern: str) -> list[str]:
    _safe_rel(pattern)
    found: list[str] = []
    for p in root.glob(pattern):
        try:
            rel = p.relative_to(root).as_posix()
        except ValueError:
            continue
        try:
            _repo_path(root, rel)
        except _InputError:
            continue
        found.append(rel)
    return sorted(found)


def _verdict_tokens_in_cell(cell: str) -> list[str]:
    """Whole-token verdict scan (audit_check `_VERDICT_TOKEN_RE`); never treat UNVERIFIED or NOT VERIFIED as VERIFIED."""
    if _NOT_VERIFIED.search(cell):
        return []
    tokens: list[str] = []
    i, n = 0, len(cell)
    while i < n:
        if i > 0 and (cell[i - 1].isalnum() or cell[i - 1] in "_/-."):
            i += 1
            continue
        m = _VERDICT_TOKEN_RE.match(cell, i)
        if m is not None:
            tokens.append(m.group(1))
            i = m.end()
        else:
            i += 1
    return tokens


def _ledger_verdict(cell: str) -> str:
    """Simplified ledger verdict for twin checks; unknown or ambiguous cells fail closed (empty string)."""
    tokens = _verdict_tokens_in_cell(cell)
    if len(tokens) != 1:
        return ""
    token = tokens[0]
    if token == "PARTIAL/FRAGILE":
        return "PARTIAL"
    if token in ("VERIFIED", "FALSIFIED"):
        return token
    return ""


def _split_cells(line: str) -> list[str]:
    cells = [c.strip() for c in _UNESCAPED_PIPE.split(line.strip())]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _id_text(num: str, suffix: str | None) -> str:
    return f"AUDIT-{num}{suffix or ''}"


def _split_id(audit_id: str) -> tuple[int, str]:
    m = _ID_PART.match(audit_id)
    require_ok(m is not None, "TWIN_BAD_AUDIT_ID", f"malformed audit id: {audit_id!r}")
    return int(m.group(1)), m.group(2) or ""  # type: ignore[union-attr]


def _ledger_rows(text: str) -> list[dict[str, Any]]:
    """Rows of the cave AUDIT_LOG table whose first cell starts with a bold AUDIT-xxx id."""
    verdict_col: int | None = None
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if verdict_col is None and line.lstrip().startswith("|") and "Verdict" in line:
            for idx, cell in enumerate(_split_cells(line)):
                if "Verdict" in cell:
                    verdict_col = idx
                    break
            continue
        m = _LEDGER_ROW.match(line)
        if m is None:
            continue
        ids: list[str] = []
        for pos, part in enumerate(m.group(1).split("/")):
            part = part.strip()
            full = _ID_PART.match(part)
            bare = _BARE_PART.match(part) if pos > 0 else None
            if full is not None:
                ids.append(_id_text(full.group(1), full.group(2)))
            elif bare is not None:
                ids.append(_id_text(bare.group(1), bare.group(2)))
        cells = _split_audit_table_row(line) if line.lstrip().startswith("|") else _split_cells(line)
        verdict = ""
        if verdict_col is not None and verdict_col < len(cells):
            verdict = _ledger_verdict(cells[verdict_col])
        rows.append({"ids": ids, "line": lineno, "verdict": verdict})
    return rows


def _extract_cited_ids(text: str) -> list[tuple[str, int]]:
    """Audit ids cited in prose, including `AUDIT-006/007` and range endpoints; (id, line)."""
    out: list[tuple[str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _CITE.finditer(line):
            out.append((_id_text(m.group("n1"), m.group("s1")), lineno))
            for mm in _MORE_PART.finditer(m.group("more") or ""):
                out.append((_id_text(mm.group(1), mm.group(2)), lineno))
            if m.group("n2") is not None:
                out.append((_id_text(m.group("n2"), m.group("s2")), lineno))
    return out


def _first_locations(cites: list[tuple[str, str, int]]) -> dict[str, str]:
    first: dict[str, str] = {}
    for audit_id, rel, lineno in cites:
        first.setdefault(audit_id, f"{rel}:{lineno}")
    return first


def _pending_ids(entries: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        for audit_id in entry.get("ids", []):
            out[audit_id] = entry
    return out


def _pending_meta(entries: list[Mapping[str, Any]]) -> tuple[list[str], str]:
    tracking: list[str] = []
    clears: list[str] = []
    for entry in entries:
        for t in entry.get("tracking", []):
            if t not in tracking:
                tracking.append(t)
        c = str(entry.get("clears_when", ""))
        if c and c not in clears:
            clears.append(c)
    return tracking, " | ".join(clears)


def _number_from_token(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token.lower())


# --------------------------------------------------------------------------- checks


def _check_audit_ids_contiguous(ctx: _Ctx) -> dict[str, Any]:
    rel = str(ctx.locator["log_file"])
    rows = _ledger_rows(_read_text(ctx.cave, rel))
    seen: dict[str, list[int]] = {}
    for row in rows:
        for audit_id in row["ids"]:
            seen.setdefault(audit_id, []).append(row["line"])
    duplicates = sorted(i for i, lines in seen.items() if len(lines) > 1)
    base = sorted({_split_id(i)[0] for i in seen if _split_id(i)[1] == ""})
    if not base:
        return _result(DRIFT, ctx.expected, {"count": 0}, f"no AUDIT-xxx rows found in {rel}", {"file": rel})
    gaps = [n for n in range(base[0], base[-1] + 1) if n not in set(base)]
    actual = {
        "first": base[0],
        "last": base[-1],
        "count": len(base),
        "gaps": [f"AUDIT-{n:03d}" for n in gaps],
        "duplicates": duplicates,
    }
    evidence = {"file": rel, "ledger_rows": len(rows), "distinct_ids": len(seen)}
    exp_first = ctx.expected.get("first")
    problems: list[str] = []
    if gaps:
        problems.append(f"gaps {actual['gaps']}")
    if duplicates:
        problems.append(f"duplicate ids {duplicates}")
    if exp_first is not None and base[0] != exp_first:
        problems.append(f"first id is {base[0]}, contract expects {exp_first}")
    if problems:
        return _result(DRIFT, ctx.expected, actual, "; ".join(problems), evidence)
    return _result(
        OK, ctx.expected, actual,
        f"AUDIT-{base[0]:03d}..AUDIT-{base[-1]:03d} contiguous ({len(base)} ids), no duplicates", evidence,
    )


def _check_cites_known_audits(ctx: _Ctx) -> dict[str, Any]:
    aletheia, cave = ctx.aletheia, ctx.cave
    files = [str(f) for f in ctx.locator["files"]]
    for pattern in ctx.locator.get("globs", []):
        files.extend(_glob(aletheia, str(pattern)))
    files = sorted(dict.fromkeys(files))
    known: set[str] = set()
    for row in _ledger_rows(_read_text(cave, str(ctx.locator["cave_log_file"]))):
        known.update(row["ids"])
    cites: list[tuple[str, str, int]] = []
    for rel in dict.fromkeys(files):
        for audit_id, lineno in _extract_cited_ids(_read_text(aletheia, rel)):
            cites.append((audit_id, rel, lineno))
    where = _first_locations(cites)
    cited = set(where)
    pending_map = _pending_ids(ctx.pending)
    unknown = sorted(i for i in cited if i not in known and i not in pending_map)
    pending_hit = sorted(i for i in cited if i not in known and i in pending_map)
    stale = sorted(i for i in pending_map if i in known)
    expected = {"every_cited_id": "exists in cave AUDIT_LOG or is declared pending"}
    actual = {
        "cited_distinct": len(cited),
        "known": len(cited & known),
        "pending": len(pending_hit),
        "unknown": len(unknown),
    }
    evidence = {
        "files_scanned": len(files),
        "citation_scope": str(ctx.locator.get("citation_scope", "")),
        "scanned_files": files,
        "cave_ledger_ids": len(known),
        "unknown_first_seen": {i: where[i] for i in unknown},
        "pending_first_seen": {i: where[i] for i in pending_hit},
        "stale_pending_now_known": stale,
    }
    if unknown:
        return _result(
            DRIFT, expected, actual,
            f"{len(unknown)} cited id(s) are neither in the cave ledger nor declared pending: {unknown}", evidence,
        )
    if pending_hit:
        used = [pending_map[i] for i in pending_hit]
        tracking, clears = _pending_meta(list({id(e): e for e in used}.values()))
        note = f"{len(pending_hit)} cited id(s) exist only in an unmerged cave pull request"
        if stale:
            note += f"; {len(stale)} declared-pending id(s) are now in the ledger and can leave the contract"
        return _result(PENDING, expected, actual, note, evidence, tracking, clears)
    note = "every cited audit id exists in the cave ledger"
    if stale:
        note += f"; {len(stale)} stale pending declaration(s) can leave the contract"
    return _result(OK, expected, actual, note, evidence)


def _locate_number(text: str, regex: str) -> tuple[int, int] | None:
    m = re.search(regex, text, flags=re.MULTILINE)
    if m is None:
        return None
    value = _number_from_token(m.group(1))
    if value is None:
        return None
    return value, text.count("\n", 0, m.start()) + 1


def _check_script_count(ctx: _Ctx) -> dict[str, Any]:
    cave = ctx.cave
    pattern = str(ctx.locator["cave_glob"])
    files = _glob(cave, pattern)
    actual_n = len(files)
    cited = int(ctx.expected["aletheia_cited_check_scripts"])
    evidence: dict[str, Any] = {"cave_glob": pattern, "cave_count": actual_n}
    expected = {"cave_check_scripts": cited}
    if ctx.aletheia is not None:
        cite = ctx.locator["aletheia_citation"]
        rel = str(cite["file"])
        found = _locate_number(_read_text(ctx.aletheia, rel), str(cite["regex"]))
        if found is None:
            return _result(
                DRIFT, expected, {"cave_check_scripts": actual_n},
                f"aletheia no longer states the check-script count where the contract expects it ({rel}); update the contract",
                evidence,
            )
        evidence["aletheia_citation"] = f"{rel}:{found[1]}"
        evidence["aletheia_cited_value"] = found[0]
        if found[0] != cited:
            return _result(
                DRIFT, expected, {"aletheia_text_says": found[0], "cave_check_scripts": actual_n},
                f"aletheia text says {found[0]} but the contract records {cited}; reviewed contract edit needed",
                evidence,
            )
    actual = {"cave_check_scripts": actual_n}
    if actual_n == cited:
        note = f"cave ships {actual_n} check scripts, matching aletheia's citation"
        if ctx.pending:
            note += "; the pending declaration is stale and can leave the contract"
        return _result(OK, expected, actual, note, evidence)
    for entry in ctx.pending:
        after = entry.get("cave_count_after_merge")
        if actual_n < cited and after == cited:
            return _result(
                PENDING, expected, actual,
                f"aletheia cites {cited} check scripts, cave main ships {actual_n}; {cited - actual_n} sit in an unmerged cave pull request",
                evidence, list(entry.get("tracking", [])), str(entry.get("clears_when", "")),
            )
    return _result(
        DRIFT, expected, actual,
        f"cave ships {actual_n} check scripts but aletheia cites {cited}, and no pending declaration covers it",
        evidence,
    )


def _extract_ids_from_cell(cell: str) -> set[str]:
    ids = {_id_text(m.group(1), m.group(2)) for m in re.finditer(rf"AUDIT-(\d{{3}})({_SUFFIX})?", cell)}
    for m in re.finditer(rf"`(\d{{3}})({_SUFFIX})?`", cell):
        ids.add(_id_text(m.group(1), m.group(2)))
    return ids


def _cave_n2_table_ids(text: str, heading_regex: str) -> tuple[set[str], int] | None:
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if re.search(heading_regex, line):
            start = idx
            break
    if start is None:
        return None
    ids: set[str] = set()
    row = re.compile(rf"^\|\s*\*{{0,2}}`?(AUDIT-\d{{3}}(?:{_SUFFIX})?)`?\*{{0,2}}\s*\|")
    for line in lines[start + 1:]:
        if re.match(r"^(#{1,6}\s|---)", line):
            break
        m = row.match(line)
        if m is not None:
            ids.add(m.group(1))
    return ids, start + 1


def _check_n2_set(ctx: _Ctx) -> dict[str, Any]:
    cave = ctx.cave
    loc = ctx.locator
    n2 = {str(i) for i in ctx.expected["aletheia_n2_ids"]}
    borderline = {str(i) for i in ctx.expected["aletheia_borderline_n2_ids"]}
    described = n2 | borderline
    rel = str(loc["cave_readme_file"])
    parsed = _cave_n2_table_ids(_read_text(cave, rel), str(loc["cave_n2_heading_regex"]))
    expected = {"aletheia_describes_n2": sorted(described)}
    if parsed is None:
        return _result(
            DRIFT, expected, {}, f"cave README has no section matching the contract's N2 heading ({rel})", {"file": rel},
        )
    cave_ids, line = parsed
    evidence: dict[str, Any] = {"cave_table": f"{rel}:{line}", "cave_n2_count": len(cave_ids)}
    if ctx.aletheia is not None:
        arel = str(loc["aletheia_file"])
        atext = _read_text(ctx.aletheia, arel)
        got: dict[str, set[str]] = {}
        for key in ("n2_row_regex", "borderline_row_regex"):
            row_line = next((ln for ln in atext.splitlines() if re.search(str(loc[key]), ln)), None)
            if row_line is None:
                return _result(
                    DRIFT, expected, {"cave_n2": sorted(cave_ids)},
                    f"aletheia row for {key} not found in {arel}; update the contract", evidence,
                )
            cells = _split_cells(row_line)
            cell = cells[1] if len(cells) > 1 else row_line
            got[key] = _extract_ids_from_cell(cell.split("*(")[0])
        evidence["aletheia_row_file"] = arel
        if got["n2_row_regex"] != n2 or got["borderline_row_regex"] != borderline:
            return _result(
                DRIFT, expected,
                {"aletheia_text_n2": sorted(got["n2_row_regex"]), "aletheia_text_borderline": sorted(got["borderline_row_regex"])},
                "aletheia text no longer matches the N2 sets recorded in the contract; reviewed contract edit needed",
                evidence,
            )
    cave_only = cave_ids - described
    aletheia_only = described - cave_ids
    actual = {"cave_n2": sorted(cave_ids), "cave_only": sorted(cave_only), "aletheia_only": sorted(aletheia_only)}
    diff = cave_only | aletheia_only
    pending_map = _pending_ids(ctx.pending)
    undeclared = sorted(i for i in diff if i not in pending_map)
    if undeclared:
        return _result(DRIFT, expected, actual, f"N2 sets differ with no pending declaration for {undeclared}", evidence)
    if diff:
        entries = list({id(pending_map[i]): pending_map[i] for i in diff}.values())
        tracking, clears = _pending_meta(entries)
        return _result(
            PENDING, expected, actual,
            f"N2 sets differ only on {sorted(diff)}, all declared pending", evidence, tracking, clears,
        )
    return _result(OK, expected, actual, f"cave README N2 table matches aletheia's description ({len(cave_ids)} ids)", evidence)


def _check_seam_count(ctx: _Ctx) -> dict[str, Any]:
    cave = ctx.cave
    loc = ctx.locator
    jrel = str(loc["json_file"])
    data = _read_json(cave, jrel)
    key = loc.get("json_key")
    seams = data[key] if key is not None and isinstance(data, dict) and key in data else data
    if not isinstance(seams, list):
        return _result(DRIFT, ctx.expected, {}, f"{jrel}: seam list not found under key {key!r}", {"file": jrel})
    actual_n = len(seams)
    trel = str(loc["stated_in_file"])
    text = _read_text(cave, trel)
    stated: list[dict[str, Any]] = []
    problems: list[str] = []
    for name, regex in loc["stated_patterns"].items():
        hits = list(re.finditer(str(regex), text, flags=re.MULTILINE))
        if not hits:
            problems.append(f"stated count '{name}' not found in {trel}; update the contract")
        for m in hits:
            value = _number_from_token(m.group(1))
            where = f"{trel}:{text.count(chr(10), 0, m.start()) + 1}"
            stated.append({"pattern": name, "token": m.group(1), "value": value, "at": where})
            if value != actual_n:
                problems.append(f"{where} says {m.group(1)!r} but {jrel} holds {actual_n}")
    expected = {"stated_equals_json_len": True}
    actual = {"json_len": actual_n, "stated": [s["value"] for s in stated]}
    evidence = {"json_file": jrel, "json_len": actual_n, "stated": stated}
    if problems:
        return _result(DRIFT, expected, actual, "; ".join(problems), evidence)
    return _result(OK, expected, actual, f"{jrel} holds {actual_n} seams, every statement in {trel} agrees", evidence)


def _check_portal_count(ctx: _Ctx) -> dict[str, Any]:
    cave = ctx.cave
    loc = ctx.locator
    jrel = str(loc["json_file"])
    data = _read_json(cave, jrel)
    key = loc.get("json_key")
    points = data[key] if key is not None and isinstance(data, dict) and key in data else data
    if not isinstance(points, list):
        return _result(DRIFT, ctx.expected, {}, f"{jrel}: entry list not found under key {key!r}", {"file": jrel})
    mrel = str(loc["portals_file"])
    portals = re.findall(str(loc["portal_heading_regex"]), _read_text(cave, mrel), flags=re.MULTILINE)
    expected = {"entry_points_equals_portals": True}
    actual = {"entry_points": len(points), "portals": len(portals)}
    evidence = {"json_file": jrel, "portals_file": mrel}
    if len(points) != len(portals):
        return _result(
            DRIFT, expected, actual,
            f"{jrel} holds {len(points)} entry points but {mrel} has {len(portals)} portals", evidence,
        )
    return _result(OK, expected, actual, f"{len(points)} entry points and {len(portals)} portals agree", evidence)


def _closes(num: int, suffix: str, other_num: int, other_suffix: str) -> bool:
    if other_num != num or other_suffix == suffix:
        return False
    if suffix == "":
        return other_suffix.startswith("R")
    return other_suffix.startswith(suffix) and len(other_suffix) > len(suffix)


def _open_ledger_ids(rows: list[dict[str, Any]]) -> list[str]:
    """FALSIFIED / PARTIAL ledger ids that no later VERIFIED repair id (R, R2, ...) closes."""
    verdicts: dict[str, str] = {}
    for row in rows:
        for audit_id in row["ids"]:
            verdicts[audit_id] = row["verdict"]
    parsed = {i: _split_id(i) for i in verdicts}
    open_ids: list[str] = []
    for audit_id, verdict in verdicts.items():
        if verdict not in ("FALSIFIED", "PARTIAL"):
            continue
        num, suffix = parsed[audit_id]
        closed = any(
            _closes(num, suffix, n, s) and verdicts[other] == "VERIFIED"
            for other, (n, s) in parsed.items()
        )
        if not closed:
            open_ids.append(audit_id)
    return sorted(open_ids)


def _check_readme_verified_claim(ctx: _Ctx) -> dict[str, Any]:
    cave = ctx.cave
    loc = ctx.locator
    rrel = str(loc["readme_file"])
    text = _read_text(cave, rrel)
    rows = _ledger_rows(_read_text(cave, str(loc["ledger_file"])))
    open_ids = _open_ledger_ids(rows)

    def find(strings: list[str]) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for s in strings:
            idx = text.find(s)
            if idx >= 0:
                hits.append({"string": s, "at": f"{rrel}:{text.count(chr(10), 0, idx) + 1}"})
        return hits

    assertions = find([str(s) for s in ctx.expected["assertion_strings"]])
    caveats = find([str(s) for s in ctx.expected["caveat_strings"]])
    expected = {"no_unqualified_all_verified_claim": True}
    actual = {"assertion_found": bool(assertions), "caveat_found": bool(caveats), "ledger_rows_without_closing_row": open_ids}
    evidence = {"assertions": assertions, "caveats": caveats, "ledger_file": str(loc["ledger_file"])}
    if assertions and open_ids and not caveats:
        return _result(
            DRIFT, expected, actual,
            f"README asserts every track reached VERIFIED, but {open_ids} are FALSIFIED/PARTIAL with no closing row and the README carries no caveat",
            evidence,
        )
    if not assertions:
        return _result(OK, expected, actual, "README makes no unqualified all-VERIFIED assertion", evidence)
    if caveats:
        return _result(OK, expected, actual, "README keeps the assertion but carries the required caveat", evidence)
    return _result(OK, expected, actual, "assertion present and every FALSIFIED/PARTIAL row has a closing row", evidence)


def _sha256_file(root: Path, rel: str) -> str | None:
    try:
        path = _repo_path(root, rel)
    except _InputError:
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _check_license(ctx: _Ctx) -> dict[str, Any]:
    rel = str(ctx.locator.get("file", "LICENSE"))
    _safe_rel(rel)
    accepted = {str(ctx.expected["canonical_sha256"])} | {str(s) for s in ctx.expected.get("also_accepted_sha256", [])}
    repos = {"aletheia": ctx.aletheia, "cave": ctx.cave}
    hashes = {name: _sha256_file(root, rel) for name, root in repos.items()}
    bad = sorted(name for name, h in hashes.items() if h not in accepted)
    expected = {"canonical_sha256": ctx.expected["canonical_sha256"], "byte_identical": True}
    actual = {name: (h or "missing") for name, h in hashes.items()}
    evidence = {"file": rel, "accepted_sha256": sorted(accepted)}
    if not bad:
        if len(set(hashes.values())) != 1:
            return _result(
                DRIFT, expected, actual,
                "both LICENSE files are an accepted form but not byte-identical to each other", evidence,
            )
        return _result(OK, expected, actual, "both LICENSE files are byte-identical and match the canonical Apache-2.0 hash", evidence)
    covered = {str(e.get("repo")): e for e in ctx.pending}
    undeclared = [name for name in bad if name not in covered]
    if undeclared:
        return _result(
            DRIFT, expected, actual,
            f"LICENSE in {undeclared} is not the canonical Apache-2.0 text and no pending declaration covers it", evidence,
        )
    tracking, clears = _pending_meta([covered[name] for name in bad])
    return _result(
        PENDING, expected, actual,
        f"LICENSE in {bad} is a paraphrase of Apache-2.0; a reviewed pull request replaces it with the verbatim text",
        evidence, tracking, clears,
    )


def _check_ci_present(ctx: _Ctx) -> dict[str, Any]:
    repos = {"aletheia": ctx.aletheia, "cave": ctx.cave}
    per_repo: dict[str, Any] = {}
    statuses: dict[str, str] = {}
    tracking: list[str] = []
    clears: list[str] = []
    for name, root in repos.items():
        cfg = ctx.expected["repos"][name]
        workflows: list[str] = []
        for pattern in cfg["workflow_globs"]:
            workflows.extend(_glob(root, str(pattern)))
        workflows = sorted(set(workflows))
        matched: list[str] = []
        for rel in workflows:
            try:
                body = _read_text(root, rel)
            except _InputError:
                continue
            if any(str(m) in body for m in cfg["run_markers"]):
                matched.append(rel)
        per_repo[name] = {"workflows": workflows, "running_own_checks": matched}
        if matched:
            statuses[name] = OK
        else:
            statuses[name] = str(cfg.get("if_missing", DRIFT))
            require_ok(statuses[name] in (DRIFT, PENDING), "TWIN_CONTRACT_BAD_STATUS", "if_missing must be DRIFT or PENDING")
            if statuses[name] == PENDING:
                tracking.extend(str(t) for t in cfg.get("tracking", []))
                clears.append(str(cfg.get("clears_when", "")))
    expected = {"each_repo_has_ci_running_its_own_checks": True}
    actual = {name: statuses[name] for name in repos}
    if DRIFT in statuses.values():
        miss = sorted(n for n, s in statuses.items() if s == DRIFT)
        return _result(DRIFT, expected, actual, f"no CI workflow runs the checks in: {miss}", per_repo)
    if PENDING in statuses.values():
        miss = sorted(n for n, s in statuses.items() if s == PENDING)
        return _result(
            PENDING, expected, actual, f"no CI workflow on the default branch of: {miss}; a pull request adds it",
            per_repo, list(dict.fromkeys(tracking)), " | ".join(c for c in clears if c),
        )
    return _result(OK, expected, actual, "both repos have a CI workflow that runs their own checks", per_repo)


# (id, repos the check needs, implementation)
_CHECKS: tuple[tuple[str, tuple[str, ...], Callable[[_Ctx], dict[str, Any]]], ...] = (
    ("cave.audit_ids_contiguous", ("cave",), _check_audit_ids_contiguous),
    ("aletheia.cites_known_audits", ("aletheia", "cave"), _check_cites_known_audits),
    ("cave.check_script_count_matches_citation", ("cave",), _check_script_count),
    ("cave.n2_set_matches", ("cave",), _check_n2_set),
    ("cave.seam_count_consistent", ("cave",), _check_seam_count),
    ("cave.portal_count_consistent", ("cave",), _check_portal_count),
    ("cave.readme_verified_claim_consistent", ("cave",), _check_readme_verified_claim),
    ("twin.license_verbatim", ("aletheia", "cave"), _check_license),
    ("twin.ci_present", ("aletheia", "cave"), _check_ci_present),
)

CHECK_IDS = tuple(c[0] for c in _CHECKS)


# --------------------------------------------------------------------------- public API


def package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_roots(
    aletheia_root: Path | None = None,
    cave_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[Path, Path]:
    """Explicit argument, then ALETHEIA_ROOT / CAVE_ROOT, then the package's own repo and its sibling."""
    env = os.environ if env is None else env
    pkg = package_root()
    a = aletheia_root or (Path(env["ALETHEIA_ROOT"]) if env.get("ALETHEIA_ROOT") else pkg)
    c = cave_root or (Path(env["CAVE_ROOT"]) if env.get("CAVE_ROOT") else pkg.parent / CAVE_SIBLING_NAME)
    return a, c


def load_contract(path: Path) -> dict[str, Any]:
    contract = load_strict_json_file(path, allow_float=False, require_object=True)
    require_ok(
        contract.get("schema") == TWIN_CONTRACT_SCHEMA,
        "TWIN_CONTRACT_SCHEMA",
        f"contract schema must be {TWIN_CONTRACT_SCHEMA!r}",
    )
    checks = contract.get("checks")
    require_ok(isinstance(checks, dict), "TWIN_CONTRACT_CHECKS", "contract 'checks' must be an object")
    require_ok(
        set(checks) == set(CHECK_IDS),
        "TWIN_CONTRACT_CHECK_SET",
        f"contract must list exactly the implemented checks; missing={sorted(set(CHECK_IDS) - set(checks))} "
        f"unknown={sorted(set(checks) - set(CHECK_IDS))}",
    )
    for check_id, spec in checks.items():
        require_ok(
            isinstance(spec, dict) and isinstance(spec.get("description"), str) and isinstance(spec.get("expected"), dict),
            "TWIN_CONTRACT_CHECK_ENTRY",
            f"contract entry {check_id} needs a string 'description' and an object 'expected'",
        )
        for entry in spec.get("pending", []):
            require_ok(
                isinstance(entry, dict) and entry.get("tracking") and entry.get("clears_when"),
                "TWIN_CONTRACT_PENDING_ENTRY",
                f"pending entry in {check_id} must name 'tracking' pull requests and say what 'clears_when'",
            )
    return contract


def resolve_contract_path(contract: Path | None, aletheia_root: Path) -> Path:
    if contract is not None:
        return contract
    local = aletheia_root.joinpath(*PurePosixPath(CONTRACT_REL).parts)
    return local if local.is_file() else package_root().joinpath(*PurePosixPath(CONTRACT_REL).parts)


def _overall(counts: Mapping[str, int]) -> str:
    if counts[DRIFT]:
        return DRIFT
    if counts[PENDING]:
        return PENDING
    if counts[OK]:
        return OK
    return SKIP


def run_twin_check(
    aletheia_root: Path,
    cave_root: Path,
    contract_path: Path,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    raw = contract_path.read_bytes()
    present = {"aletheia": aletheia_root.is_dir(), "cave": cave_root.is_dir()}
    roots = {"aletheia": aletheia_root if present["aletheia"] else None, "cave": cave_root if present["cave"] else None}
    rows: list[dict[str, Any]] = []
    for check_id, needs, fn in _CHECKS:
        spec = contract["checks"][check_id]
        absent = [name for name in needs if not present[name]]
        if absent:
            res = _result(
                SKIP, spec["expected"], {}, f"skipped: sibling repo root not present for {absent}; nothing was compared",
            )
        else:
            ctx = _Ctx(roots["aletheia"], roots["cave"], spec)
            try:
                res = fn(ctx)
            except _InputError as exc:
                res = _result(DRIFT, spec["expected"], {}, f"{exc}; the file the contract points at is gone or unreadable")
        require_ok(res["status"] in STATUSES, "TWIN_BAD_STATUS", f"{check_id} produced status {res['status']!r}")
        require_ok(
            res["status"] != PENDING or (res["tracking"] and res["clears_when"]),
            "TWIN_PENDING_UNTRACKED",
            f"{check_id} reported PENDING without a tracking pull request and a clearing condition",
        )
        rows.append({"id": check_id, "description": spec["description"], **res})
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    status = _overall(counts)
    return {
        "schema": TWIN_REPORT_SCHEMA,
        "status": status,
        "passed": counts[DRIFT] == 0,
        "aletheia_root": str(aletheia_root),
        "cave_root": str(cave_root),
        "aletheia_root_present": present["aletheia"],
        "cave_root_present": present["cave"],
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": counts,
        "checks": rows,
    }


def format_twin_table(report: Mapping[str, Any]) -> str:
    counts = report["summary"]
    lines = [
        f"[twin-check] status={report['status']}  "
        + "  ".join(f"{s}={counts[s]}" for s in STATUSES),
        f"  aletheia_root: {report['aletheia_root']}" + ("" if report["aletheia_root_present"] else "  (absent)"),
        f"  cave_root:     {report['cave_root']}" + ("" if report["cave_root_present"] else "  (absent)"),
        "",
        f"  {'STATUS':<8} CHECK",
    ]
    for row in report["checks"]:
        lines.append(f"  {row['status']:<8} {row['id']}")
        lines.append(f"           {row['note']}")
        if row["tracking"]:
            lines.append(f"           tracking: {', '.join(row['tracking'])}")
        if row["clears_when"]:
            lines.append(f"           clears when: {row['clears_when']}")
    return "\n".join(lines)
