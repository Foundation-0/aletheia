"""
`aletheia audit-check <path>`: Automated R1-R4 hygiene & Gate 1-9 verification checker
(R5 is `aletheia mutate`; R6/R7 not automated by this command).

Checks:
  1. Hygiene & R1-R4 static checks:
     - Zero CRLF line endings across text/code files
     - Zero __pycache__ directories or .pyc/.pyo files
     - Zero personal home-directory path leaks or credential tokens
     - Zero bare `assert` statements in Python files (AST-scanned, R4 parity!)
     - Unseeded module-level `random.*` / `np.random.*` calls flagged as Gate 1 warnings
     - Strict JSON parsing (zero duplicate keys, zero NaN/Infinity) on every .json file
  2. R4 3-mode isolated execution (`-I -B`, `-I -O -B`, `-I -B -W error`) on `--scripts`,
     verifying exit code 0 and bit-identical stdout SHA-256 across all 3 modes!
  3. `AUDIT_LOG.md` ledger validation (verdicts, oracle classes, novelty tags, Gate 9 prior-art
     citation check on N2 rows) and `aletheia.audit_receipt.v1` JSON receipt validation.
     A `VERIFIED` `N2` row that lists no `G10` and that no `--outside-rulings` file
     (`outside_observer.rulings.v1`) names gets novelty status `NOT_SHOWN`
     (warning, or error under `--strict-novelty`).
"""
from __future__ import annotations

import ast
import errno
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .safety import scan_directory_safety_surface
from .strict_io import (
    AletheiaError,
    canonical_sha256_bytes,
    load_strict_json_file,
    load_strict_jsonl_file,
    require_ok,
    scan_text_for_leaks,
)

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache", "dist", "build"}
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".lean",
    ".mdc", ".sh", ".js", ".ts", ".cfg", ".ini", ".csv", ".jsonl",
}

VALID_VERDICTS = {"VERIFIED", "PARTIAL/FRAGILE", "FALSIFIED", "NOT_SHOWN", "EXPOSED"}
VALID_ORACLE_TOKENS = {"exact", "sampled", "anchor", "reference_replay"}
VALID_NOVELTY_TOKENS = {"N0", "N1", "N2"}
OUTSIDE_RULINGS_SCHEMA = "outside_observer.rulings.v1"
VALID_OUTSIDE_RULINGS = {"stands", "stands_narrowed", "falls"}

_UNSEEDED_RANDOM_FUNCS = {
    "random", "randint", "randrange", "uniform", "gauss", "normalvariate",
    "choice", "choices", "sample", "shuffle",
}
_UNSEEDED_NP_RANDOM_FUNCS = {
    "rand", "randn", "randint", "random", "uniform", "normal", "choice", "permutation", "shuffle",
}

_AUDIT_ID_RE = re.compile(r"AUDIT-[0-9]{3,4}[A-Za-z0-9_-]*")
_AUDIT_ID_STRICT_RE = re.compile(r"\AAUDIT-[0-9]{3,4}[A-Za-z0-9_-]*\Z")
_DATE_STRICT_RE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_SHA256_LOWER_STRICT_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_UNITTEST_SKIP_RE = re.compile(r"\bskipped\s*=\s*([0-9]+)\b")
_UNITTEST_RAN_RE = re.compile(r"\bRan\s+([0-9]+)\s+tests?\b")
_PRIOR_ART_HINT_RE = re.compile(
    r"(?:prior[- ]?art|arxiv|literature|borcea|streinu|knausg|alp[oö]ge|loom#|docs/10|over\s+`?loom|refut|reproduc|upstream|skordis|l'vov|viazovska)",
    re.IGNORECASE,
)


def _scan_python_ast(path: Path, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (syntax_errors, bare_asserts, unseeded_rng_warnings) for one Python file."""
    syntax_errors: list[dict[str, Any]] = []
    bare_asserts: list[dict[str, Any]] = []
    unseeded_rng: list[dict[str, Any]] = []

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        syntax_errors.append({"file": str(path), "line": exc.lineno or 0, "message": str(exc)})
        return syntax_errors, bare_asserts, unseeded_rng

    # Track aliases for `import random as X`, `import numpy as Y`, `from random import randint`, etc.
    random_aliases = {"random"}
    numpy_aliases = {"np", "numpy"}
    np_random_aliases: set[str] = set()
    direct_random_funcs: dict[str, str] = {}
    direct_np_funcs: dict[str, str] = {}
    has_module_seed = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "random" and alias.asname:
                    random_aliases.add(alias.asname)
                if alias.name == "numpy" and alias.asname:
                    numpy_aliases.add(alias.asname)
                if alias.name == "numpy.random" and alias.asname:
                    np_random_aliases.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "random":
                for alias in node.names:
                    if alias.name in _UNSEEDED_RANDOM_FUNCS:
                        direct_random_funcs[alias.asname or alias.name] = alias.name
            elif mod == "numpy":
                for alias in node.names:
                    if alias.name == "random":
                        np_random_aliases.add(alias.asname or "random")
            elif mod == "numpy.random":
                for alias in node.names:
                    if alias.name in _UNSEEDED_NP_RANDOM_FUNCS:
                        direct_np_funcs[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "seed":
                has_module_seed = True

    rng_hint = (
        "Module-global RNG state (even after random.seed(...)) leaks across imports/tests; prefer explicit local random.Random(seed)"
        if has_module_seed
        else "Prefer explicit local random.Random(seed)"
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            bare_asserts.append({"file": str(path), "line": node.lineno})
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            val = node.func.value
            # Module-level random.<fn>() (skip random.Random(seed)!)
            if isinstance(val, ast.Name) and val.id in random_aliases and attr in _UNSEEDED_RANDOM_FUNCS:
                unseeded_rng.append({
                    "file": str(path),
                    "line": node.lineno,
                    "call": f"{val.id}.{attr}()",
                    "hint": rng_hint,
                })
            # np.random.<fn>() or `from numpy import random as npr; npr.rand()`
            elif (
                isinstance(val, ast.Name)
                and val.id in np_random_aliases
                and attr in _UNSEEDED_NP_RANDOM_FUNCS
            ):
                unseeded_rng.append({
                    "file": str(path),
                    "line": node.lineno,
                    "call": f"{val.id}.{attr}()",
                    "hint": "Prefer explicit np.random.default_rng(seed)",
                })
            elif (
                isinstance(val, ast.Attribute)
                and val.attr == "random"
                and isinstance(val.value, ast.Name)
                and val.value.id in numpy_aliases
                and attr in _UNSEEDED_NP_RANDOM_FUNCS
            ):
                unseeded_rng.append({
                    "file": str(path),
                    "line": node.lineno,
                    "call": f"{val.value.id}.random.{attr}()",
                    "hint": "Prefer explicit np.random.default_rng(seed)",
                })
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fname = node.func.id
            if fname in direct_random_funcs:
                unseeded_rng.append({
                    "file": str(path),
                    "line": node.lineno,
                    "call": f"{fname}() [from random import {direct_random_funcs[fname]}]",
                    "hint": rng_hint,
                })
            elif fname in direct_np_funcs:
                unseeded_rng.append({
                    "file": str(path),
                    "line": node.lineno,
                    "call": f"{fname}() [from numpy.random import {direct_np_funcs[fname]}]",
                    "hint": "Prefer explicit np.random.default_rng(seed)",
                })

    return syntax_errors, bare_asserts, unseeded_rng


def _pyc_matches_source(cache: Path, source: Path) -> bool:
    """True when `cache` is a bytecode file whose header matches `source` (the check the import system makes)."""
    try:
        with cache.open("rb") as fh:
            head = fh.read(16)
        if len(head) < 16 or head[:4] != importlib.util.MAGIC_NUMBER:
            return False
        flags = int.from_bytes(head[4:8], "little")
        if flags & 0b1:
            return head[8:16] == importlib.util.source_hash(source.read_bytes())
        st = source.stat()
        return (
            int.from_bytes(head[8:12], "little") == (int(st.st_mtime) & 0xFFFFFFFF)
            and int.from_bytes(head[12:16], "little") == (st.st_size & 0xFFFFFFFF)
        )
    except OSError:
        return False


def _loaded_module_bytecode() -> set[Path]:
    """
    Cache files of modules this very process imported that still match their source.
    A normal (bytecode-on) run writes exactly these while importing `aletheia`, and the
    child runs that `--scripts` starts read them, so the scan must not count them as artifacts. Any other bytecode (other modules, other
    interpreter tags, mismatched or corrupt headers, loose `.pyc` files) is still counted.
    """
    own: set[Path] = set()
    for mod in list(sys.modules.values()):
        origin = getattr(getattr(mod, "__spec__", None), "origin", None)
        if not isinstance(origin, str) or not origin.endswith(".py"):
            continue
        # A parent run and its -O child name the same module's cache differently (`.opt-1`), so try each level.
        for opt in ("", 1, 2):
            try:
                cache = Path(importlib.util.cache_from_source(origin, optimization=opt))
                if _pyc_matches_source(cache, Path(origin)):
                    own.add(cache.resolve())
            except (OSError, ValueError, NotImplementedError):
                continue
    return own


def _foreign_bytecode_items(entries: Sequence[Path], own: set[Path]) -> list[Path]:
    """Filter `entries` (pycache dirs and files found by the scan) down to what this run did not produce."""
    kept = {p for p in entries if p.is_file() and p.resolve() not in own}
    for d in (p for p in entries if not p.is_file()):
        below = [c for c in entries if c != d and d in c.parents]
        # A __pycache__ directory disappears only when it held files and every one of them is ours.
        if not below or any(c in kept or not c.is_file() for c in below):
            kept.add(d)
    return [p for p in entries if p in kept]


_VERDICT_TOKEN_RE = re.compile(
    "(" + "|".join(re.escape(v) for v in sorted(VALID_VERDICTS, key=len, reverse=True)) + r")(?![A-Za-z0-9_/-]|\.[A-Za-z0-9])"
)
_ORACLE_TOKEN_RES = {
    tok: re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(tok) + r"(?![A-Za-z0-9_-]|\.[A-Za-z0-9])")
    for tok in VALID_ORACLE_TOKENS
}
_NOVELTY_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(" + "|".join(re.escape(n) for n in sorted(VALID_NOVELTY_TOKENS)) + r")(?![A-Za-z0-9_-]|\.[A-Za-z0-9])"
)


def _split_audit_table_row(line: str) -> list[str]:
    """Split a markdown table row on delimiter pipes only: escaped pipes, pipes inside
    `$...$`/`$$...$$` math spans, and pipes inside backtick code spans stay in their cell."""
    cells: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(line)
    in_math = False
    math_block = False
    code_len = 0
    while i < n:
        ch = line[i]
        if code_len:
            if ch == "`":
                j = i
                while j < n and line[j] == "`":
                    j += 1
                buf.append(line[i:j])
                if j - i == code_len:
                    code_len = 0
                i = j
            else:
                buf.append(ch)
                i += 1
        elif in_math:
            if math_block and line.startswith("$$", i):
                buf.append("$$")
                in_math = False
                math_block = False
                i += 2
            elif not math_block and ch == "$":
                buf.append(ch)
                in_math = False
                i += 1
            else:
                buf.append(ch)
                i += 1
        elif ch == "\\" and i + 1 < n and line[i + 1] in "|$`\\":
            buf.append(line[i : i + 2])
            i += 2
        elif ch == "`":
            j = i
            while j < n and line[j] == "`":
                j += 1
            run = j - i
            # Only open a code span when a matching closing run exists later on
            # this line; otherwise the backticks are literal text and must not
            # swallow the remaining delimiters.
            closes = False
            k = j
            while k < n:
                if line[k] == "`":
                    m = k
                    while m < n and line[m] == "`":
                        m += 1
                    if m - k == run:
                        closes = True
                        break
                    k = m
                else:
                    k += 1
            if closes:
                code_len = run
            buf.append(line[i:j])
            i = j
        elif ch == "$":
            if line.startswith("$$", i):
                buf.append("$$")
                if "$$" in line[i + 2 :]:
                    in_math = True
                    math_block = True
                i += 2
            else:
                buf.append(ch)
                if "$" in line[i + 1 :]:
                    in_math = True
                i += 1
        elif ch == "|":
            cells.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    cells.append("".join(buf))
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


_OUTSIDE_AUDIT_ENTRY_RE = re.compile(r"\A(AUDIT-[0-9]{3,4}[A-Za-z0-9_-]*)(?:[ \t]+(\S.*))?\Z")
_AUDIT_ID_SLASH_TAIL_RE = re.compile(r"[ \t]*/[ \t]*([0-9]{3,4}[A-Za-z0-9_-]*)")


def _first_cell_audit_ids(first_cell: str) -> list[str]:
    """
    Every audit id a ledger row's first cell names, in order, without repeats.

    A combined row such as `AUDIT-015R / 016R` or `AUDIT-006R / 007R / 008R` writes its later ids as
    slash shorthand; each is expanded to a full id (`AUDIT-016R`). Full ids anywhere in the cell count too.
    The first id is the row's leading id, the one the row is matched on.
    """
    ids: list[str] = []
    for m_id in _AUDIT_ID_RE.finditer(first_cell):
        ids.append(m_id.group(0))
        pos = m_id.end()
        while (m_tail := _AUDIT_ID_SLASH_TAIL_RE.match(first_cell, pos)) is not None:
            ids.append("AUDIT-" + m_tail.group(1))
            pos = m_tail.end()
    return list(dict.fromkeys(ids))


def load_outside_rulings(path: Path) -> dict[str, list[dict[str, str]]]:
    """
    Load an `outside_observer.rulings.v1` file and map each audit id it names to the areas naming it.

    The accepted shape is the one in cave-expedition `verification/outside/rulings.json`: a non-empty
    `areas` list; each area has a name (`area`), an `audits` string of comma-separated audit ids (an id
    may carry a qualifier such as `Part A`, kept verbatim in `entry`), and a non-empty `findings` list
    in which every finding carries a ruling `stands`, `stands_narrowed` or `falls`. Anything else is
    refused (R1), so a malformed file never counts as an outside ruling.

    Only presence is read: which audit ids an outside two-pass review ruled on. What a ruling decided
    about a novelty label is prose in the file and is not read here. Ids match exactly, so a ruling on
    `AUDIT-011R` does not cover a ledger row `AUDIT-011`.
    """
    data = load_strict_json_file(path, allow_float=False, require_object=True)
    require_ok(
        data.get("schema") == OUTSIDE_RULINGS_SCHEMA,
        "OUTSIDE_RULINGS_BAD_SCHEMA",
        f"{path}: schema must be {OUTSIDE_RULINGS_SCHEMA!r}",
    )
    areas = data.get("areas")
    require_ok(isinstance(areas, list) and len(areas) > 0, "OUTSIDE_RULINGS_NO_AREAS", f"{path}: areas must be a non-empty list")
    coverage: dict[str, list[dict[str, str]]] = {}
    for idx, area in enumerate(areas):
        require_ok(isinstance(area, dict), "OUTSIDE_RULINGS_BAD_AREA", f"{path}: areas[{idx}] is not an object")
        name = area.get("area")
        require_ok(
            isinstance(name, str) and name.strip() != "",
            "OUTSIDE_RULINGS_BAD_AREA",
            f"{path}: areas[{idx}].area must be a non-empty string",
        )
        audits = area.get("audits")
        require_ok(
            isinstance(audits, str) and audits.strip() != "",
            "OUTSIDE_RULINGS_BAD_AUDITS",
            f"{path}: areas[{idx}].audits must be a non-empty string",
        )
        findings = area.get("findings")
        require_ok(
            isinstance(findings, list) and len(findings) > 0,
            "OUTSIDE_RULINGS_NO_FINDINGS",
            f"{path}: areas[{idx}].findings must be a non-empty list",
        )
        for fidx, finding in enumerate(findings):
            ruling = finding.get("ruling") if isinstance(finding, dict) else None
            require_ok(
                isinstance(ruling, str) and ruling in VALID_OUTSIDE_RULINGS,
                "OUTSIDE_RULINGS_BAD_RULING",
                f"{path}: areas[{idx}].findings[{fidx}].ruling must be one of {sorted(VALID_OUTSIDE_RULINGS)}",
            )
        for piece in audits.split(","):
            entry = piece.strip()
            m_entry = _OUTSIDE_AUDIT_ENTRY_RE.match(entry)
            require_ok(
                m_entry is not None,
                "OUTSIDE_RULINGS_BAD_AUDIT_ID",
                f"{path}: areas[{idx}].audits entry {entry!r} does not start with an audit id",
            )
            # A qualifier is prose (`Part A`). One that holds another id (`AUDIT-002 AUDIT-003`, a missing
            # comma) would drop that id without notice, so it is refused.
            require_ok(
                _AUDIT_ID_RE.search(m_entry.group(2) or "") is None,  # type: ignore[union-attr]
                "OUTSIDE_RULINGS_BAD_AUDIT_ID",
                f"{path}: areas[{idx}].audits entry {entry!r} holds more than one audit id; separate ids with commas",
            )
            coverage.setdefault(m_entry.group(1), []).append({"area": name, "entry": entry})  # type: ignore[union-attr]
    return coverage


def validate_audit_log_markdown(
    path: Path,
    *,
    require_rows: bool = True,
    outside_rulings: Mapping[str, Sequence[Mapping[str, str]]] | None = None,
    strict_novelty: bool = False,
) -> dict[str, Any]:
    """
    Parse and validate a markdown AUDIT_LOG.md table under Gate 8 & Gate 9.
    The verdict cell must open with one whole verdict token (markdown emphasis aside), so `NOT VERIFIED`
    is rejected rather than read as `VERIFIED`. With `require_rows`, a ledger with no audit rows is invalid.

    Every `VERIFIED` `N2` row gets a novelty status. It is `SECOND_PASS_RECORDED` when the row's gates
    cell lists `G10` or `outside_rulings` (from `load_outside_rulings`) names the row's audit id, and
    `NOT_SHOWN` otherwise. `NOT_SHOWN` is the warning `N2_NOVELTY_NOT_SHOWN`, or an error when
    `strict_novelty` is set. `SECOND_PASS_RECORDED` says only that a second pass is on record; it does
    not say the pass kept the label.

    A combined row such as `AUDIT-015R / 016R` is matched on its leading id (`AUDIT-015R`): a ruling on a
    later id does not cover the row. Every id the first cell names (`row_ids`, slash shorthand expanded)
    counts as in the ledger for `outside_ruling_ids_not_in_ledger`.
    """
    require_ok(path.is_file(), "AUDIT_LOG_NOT_FOUND", f"audit log not found: {path}")
    text = path.read_text(encoding="utf-8")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rows_checked = 0
    verdict_counts: dict[str, int] = {}
    novelty_counts: dict[str, int] = {}
    n2_novelty: list[dict[str, Any]] = []
    ledger_ids: set[str] = set()

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = _split_audit_table_row(stripped)
        if len(cells) < 8:
            if cells and _AUDIT_ID_RE.search(cells[0]) is not None:
                errors.append(
                    {
                        "code": "MALFORMED_AUDIT_ROW",
                        "line": lineno,
                        "message": f"audit row has {len(cells)} cells, expected at least 8",
                    }
                )
                rows_checked += 1
            continue
        first_cell = cells[0]
        if _AUDIT_ID_RE.search(first_cell) is None:
            continue
        rows_checked += 1
        # The row is matched on its leading id; a combined row's later ids (`AUDIT-015R / 016R`) still
        # count as ledger ids for `outside_ruling_ids_not_in_ledger`.
        row_ids = _first_cell_audit_ids(first_cell)
        audit_id = row_ids[0]
        ledger_ids.update(row_ids)

        # Standard 9-column table: ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence
        # Also tolerate 8-column variations by scanning from right for Verdict/Novelty/Oracle
        gates_cell = cells[4] if len(cells) >= 9 else ""
        oracle_cell = cells[5] if len(cells) >= 9 else cells[-4]
        novelty_cell = cells[6] if len(cells) >= 9 else cells[-3]
        verdict_cell = cells[7] if len(cells) >= 9 else cells[-2]
        evidence_cell = cells[8] if len(cells) >= 9 else cells[-1]

        # The verdict is the whole token that opens the cell (after markdown emphasis such as ** or `).
        v_main: str | None = None
        m_verdict = _VERDICT_TOKEN_RE.match(verdict_cell.lstrip("*`_~ \t"))
        if m_verdict is None:
            errors.append({
                "line": lineno,
                "audit_id": audit_id,
                "code": "INVALID_VERDICT",
                "message": f"unrecognized verdict cell {verdict_cell!r}",
            })
        else:
            v_main = m_verdict.group(1)
            verdict_counts[v_main] = verdict_counts.get(v_main, 0) + 1

        # Extract oracle class tokens (whole tokens only, so `exactitude` is not `exact`)
        o_lower = oracle_cell.lower()
        found_oracles = [tok for tok in sorted(VALID_ORACLE_TOKENS) if _ORACLE_TOKEN_RES[tok].search(o_lower) is not None]
        if not found_oracles:
            errors.append({
                "line": lineno,
                "audit_id": audit_id,
                "code": "INVALID_ORACLE_CLASS",
                "message": f"oracle class {oracle_cell!r} must mention exact/sampled/anchor",
            })

        # Extract novelty tokens (whole tokens only, so `N20` is not `N2`)
        found_nov = _NOVELTY_TOKEN_RE.findall(novelty_cell)
        if not found_nov:
            errors.append({
                "line": lineno,
                "audit_id": audit_id,
                "code": "INVALID_NOVELTY_TAG",
                "message": f"novelty cell {novelty_cell!r} must include N0, N1, or N2",
            })
        else:
            top_nov = "N2" if "N2" in found_nov else ("N1" if "N1" in found_nov else "N0")
            novelty_counts[top_nov] = novelty_counts.get(top_nov, 0) + 1
            if top_nov == "N2" and v_main == "VERIFIED":
                combined = f"{gates_cell} {novelty_cell} {evidence_cell}"
                has_g9 = re.search(r"\bG9\b", gates_cell) is not None
                if not has_g9 and _PRIOR_ART_HINT_RE.search(combined) is None:
                    warnings.append({
                        "line": lineno,
                        "audit_id": audit_id,
                        "code": "N2_MISSING_PRIOR_ART_NOTE",
                        "message": "VERIFIED N2 entry neither lists G9 nor cites prior-art/baseline check in row",
                    })
                # Gate 10 / outside observer: N2 needs Gates 1-10 (spec §2.3), so an N2 label with no second
                # pass on record is NOT_SHOWN, never certified by this row alone.
                rulings_for_row = [dict(r) for r in (outside_rulings or {}).get(audit_id, ())]
                basis = (["G10_LISTED"] if re.search(r"\bG10\b", gates_cell) is not None else []) + (
                    ["OUTSIDE_RULING"] if rulings_for_row else []
                )
                n2_novelty.append({
                    "line": lineno,
                    "audit_id": audit_id,
                    "row_ids": row_ids,
                    "novelty_status": "SECOND_PASS_RECORDED" if basis else "NOT_SHOWN",
                    "basis": basis,
                    "outside_rulings": rulings_for_row,
                })
                if not basis:
                    (errors if strict_novelty else warnings).append({
                        "line": lineno,
                        "audit_id": audit_id,
                        "code": "N2_NOVELTY_NOT_SHOWN",
                        "message": (
                            "VERIFIED N2 row lists no G10 and no outside ruling names it: "
                            "novelty is NOT_SHOWN (no second pass on the label is on record)"
                        ),
                    })

        # Provenance inflation check: Lean compiled claim vs uncompiled_source
        row_lower = stripped.lower()
        if "uncompiled_source" in row_lower and "kernel-verified" in row_lower and "not kernel-verified" not in row_lower:
            errors.append({
                "line": lineno,
                "audit_id": audit_id,
                "code": "PROVENANCE_INFLATION",
                "message": "row mixes uncompiled_source with kernel-verified claim",
            })

    if require_rows and rows_checked == 0:
        errors.append({
            "line": 0,
            "audit_id": "",
            "code": "NO_AUDIT_ROWS",
            "message": "audit log has no audit rows (expected at least one `AUDIT-...` table row)",
        })

    return {
        "path": str(path),
        "rows_checked": rows_checked,
        "verdict_counts": verdict_counts,
        "novelty_counts": novelty_counts,
        "n2_novelty": n2_novelty,
        "verified_n2_rows": len(n2_novelty),
        "verified_n2_without_outside_ruling": sum(1 for r in n2_novelty if not r["outside_rulings"]),
        "n2_novelty_not_shown": sum(1 for r in n2_novelty if r["novelty_status"] == "NOT_SHOWN"),
        "outside_rulings_checked": outside_rulings is not None,
        "outside_ruling_ids_not_in_ledger": sorted(set(outside_rulings or {}) - ledger_ids),
        "errors": errors,
        "warnings": warnings,
        "valid": len(errors) == 0,
    }


def validate_audit_receipt_json(path: Path) -> dict[str, Any]:
    """Strictly validate an `aletheia.audit_receipt.v1` JSON audit receipt (R1/R2/R3)."""
    data = load_strict_json_file(path, allow_float=True, require_object=True)
    errors: list[dict[str, str]] = []

    if data.get("schema") != "aletheia.audit_receipt.v1":
        errors.append({"code": "INVALID_RECEIPT_SCHEMA", "message": f"expected aletheia.audit_receipt.v1, got {data.get('schema')!r}"})

    aid = data.get("audit_id")
    if not isinstance(aid, str) or _AUDIT_ID_STRICT_RE.match(aid) is None:
        errors.append({"code": "INVALID_AUDIT_ID", "message": f"audit_id {aid!r} must match AUDIT-NNN[N]..."})

    dt = data.get("date")
    if dt is not None and (not isinstance(dt, str) or _DATE_STRICT_RE.match(dt) is None):
        errors.append({"code": "INVALID_DATE", "message": f"date {dt!r} must match YYYY-MM-DD (no trailing newline)"})

    csha = data.get("canonical_sha256")
    if csha is not None and (not isinstance(csha, str) or _SHA256_LOWER_STRICT_RE.match(csha) is None):
        errors.append({"code": "INVALID_CANONICAL_SHA256", "message": f"canonical_sha256 {csha!r} must be 64 lower-hex chars"})

    for req_s in ("target", "repro_command"):
        val = data.get(req_s)
        if not isinstance(val, str) or not val.strip():
            errors.append({"code": "MISSING_RECEIPT_FIELD", "message": f"missing non-empty {req_s!r}"})

    verdict = data.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append({"code": "INVALID_VERDICT", "message": f"verdict {verdict!r} not in {sorted(VALID_VERDICTS)}"})

    oc = data.get("oracle_class")
    if (
        not isinstance(oc, str)
        or not oc.strip()
        or "\n" in oc
        or "\r" in oc
        or any(p.strip() not in VALID_ORACLE_TOKENS for p in oc.split("+"))
    ):
        errors.append({"code": "INVALID_ORACLE_CLASS", "message": f"invalid oracle_class {oc!r}"})

    nov = data.get("novelty")
    valid_nov_strs = {"N0", "N1", "N2", "N0/N1", "N1/N2"}
    if nov not in valid_nov_strs:
        errors.append({"code": "INVALID_NOVELTY", "message": f"novelty {nov!r} not in {sorted(valid_nov_strs)}"})

    r4 = data.get("r4_parity")
    if not isinstance(r4, bool):
        errors.append({"code": "INVALID_R4_PARITY_TYPE", "message": "r4_parity must be a boolean"})
    elif verdict == "VERIFIED" and not r4:
        errors.append({"code": "VERIFIED_WITHOUT_R4", "message": "VERIFIED receipt requires r4_parity == true"})

    pa = data.get("prior_art_checked")
    if not isinstance(pa, bool):
        errors.append({"code": "INVALID_PRIOR_ART_TYPE", "message": "prior_art_checked must be a boolean"})
    elif isinstance(nov, str) and "N2" in nov and verdict == "VERIFIED" and not pa:
        errors.append({"code": "N2_WITHOUT_PRIOR_ART", "message": "VERIFIED N2 receipt requires prior_art_checked == true"})

    ev = data.get("evidence")
    ev_ok = (isinstance(ev, str) and bool(ev.strip())) or (
        isinstance(ev, list) and len(ev) > 0 and all(isinstance(x, str) and x.strip() for x in ev)
    )
    if not ev_ok:
        errors.append({"code": "MISSING_EVIDENCE", "message": "evidence must be a non-empty string or list[str]"})

    return {"path": str(path), "valid": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# v1.2 Hardened Static Lean 4 Auditor + Comparator & Pinned-Manifest Gates
# (AUDIT-029 T-10..T-12 + Round-3 4-lab tomography: AUDIT-035/036/038R)
# ---------------------------------------------------------------------------

STANDARD_LEAN4_AXIOMS: frozenset[str] = frozenset(
    {"propext", "Classical.choice", "Quot.sound"}
)

_LEAN4_SHA40_RE = re.compile(r"\A[0-9a-fA-F]{40}\Z")
_LEAN4_SHA256_RE = re.compile(r"\A(?:sha256:)?[0-9a-fA-F]{64}\Z")
_LEAN4_MOD_NAME_RE = re.compile(r"\A[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*\Z")

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
    (
        re.compile(
            r"\b(?:dbgTrace|dbgTraceVal|dbgTraceIfShared|dbgSleep|dbgStackTrace|"
            r"panicCore|panicWithPosWithDecl)\b"
            r"|(?<!\.)\b(?:dbg_trace|dbg_sleep|dbg_stack_trace)(?![\w'.!?])"
            r"|(?<!\.)\b(?:panic|unreachable)!(?![\w'!?])"
        ),
        "LEAN4_DBG_FFI_ESCAPE",
    ),
    (
        re.compile(
            r"(?<!\.)\b(?:macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat|"
            r"notation|infix|infixl|infixr|prefix|postfix)(?![\w'.!?])"
            r"|\binterpolatedStr\b"
        ),
        "LEAN4_META_SYNTAX_ESCAPE",
    ),
)

# Declaration-scoped `partial` across single or multiple lines (zero FP on dot-projections like `SmoothShell.partial`)
_LEAN4_PARTIAL_DECL_RE = re.compile(
    r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", flags=re.DOTALL
)

# Declaration-scoped `opaque` across single or multiple lines (zero FP on `.opaque` projections / `def opaque : ...`)
_LEAN4_OPAQUE_DECL_RE = re.compile(
    r"(?<!\.)\bopaque\s+[A-Za-z_][A-Za-z0-9_.']*", flags=re.DOTALL
)

# Lean 4.15+ `decide` native-evaluation trust escapes: `+native`, `(native := <non-false>)`,
# `(config := <expr>)` (fail-closed outside plain `{ ... }` record literals with only `false`/`Bool.false`
# `native`), French-guillemet escaped identifiers (`«native»`, `«config»`), and bound `DecideConfig` records.
_LEAN4_GUILLEMET_IDENT_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
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


def _is_lean4_native_rhs_false_span(text: str, lo: int, hi: int) -> bool:
    while True:
        while lo != hi and text[lo].isspace():
            lo += 1
        while hi != lo and text[hi - 1].isspace():
            hi -= 1
        if hi - lo >= 7 and text[lo] == "(" and text[hi - 1] == ")":
            lo += 1
            hi -= 1
            continue
        break
    rem = text[lo:hi] if hi - lo <= 10 else ""
    return rem in ("false", "Bool.false")


def _is_lean4_native_rhs_false(rhs: str) -> bool:
    return _is_lean4_native_rhs_false_span(rhs, 0, len(rhs))


def _is_lean4_safe_config_span(
    text: str,
    lo: int,
    hi: int,
    match_rparen: dict[int, int],
) -> bool:
    while True:
        while lo != hi and text[lo].isspace():
            lo += 1
        while hi != lo and text[hi - 1].isspace():
            hi -= 1
        if match_rparen.get(lo) == hi - 1:
            lo += 1
            hi -= 1
            continue
        break
    if text[lo : lo + 1] != "{" or text[hi - 1 : hi] != "}":
        return False
    body_lo = lo + 1
    body_hi = hi - 1
    if text.find("{", body_lo, body_hi) != -1 or text.find("}", body_lo, body_hi) != -1:
        return False
    if _LEAN4_CONFIG_WITH_RE.search(text, body_lo, body_hi) is not None:
        return False
    for m_nv in _LEAN4_CONFIG_NATIVE_RE.finditer(text, body_lo, body_hi):
        if not _is_lean4_native_rhs_false_span(text, m_nv.start(1), m_nv.end(1)):
            return False
        sep = m_nv.end()
        if sep != body_hi and not _LEAN4_CONFIG_AFTER_COMMA_RE.match(text, sep, body_hi):
            return False
    return True


def _scan_lean4_decide_native(cleaned: str) -> list[tuple[int, int]]:
    """Single-pass O(n) balanced-paren scanner for Lean 4 `decide` native-evaluation escapes."""
    if "decide" not in cleaned:
        return []
    n = len(cleaned)
    match_rparen: dict[int, int] = {}
    paren_stack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "(":
            paren_stack.append(idx)
        elif ch == ")" and paren_stack:
            match_rparen[paren_stack.pop()] = idx

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
                    if not _is_lean4_native_rhs_false_span(cleaned, rhs_lo, close_idx):
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


def _lean4_match_enables_native(m_obj: re.Match[str]) -> bool:
    return any(grp is not None and not _is_lean4_native_rhs_false(grp) for grp in m_obj.groups())
_LEAN4_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
# Exact Lean 4.36.0 `Lean.isIdFirst` (`Char.isAlpha || '_' || Lean.isLetterLike`) and
# `Lean.isIdRest` (`isIdFirst || digits || Lean.isSubScriptAlnum || "'!?"`) character sets:
# includes all 96 non-`isalnum()` `Lean.isLetterLike` symbols (`™`, `℘`, `϶`, `᾽`, `U+1D49D`),
# excludes non-identifier `isalnum()` tokens (`λ`, `Π`, `Σ`), and separates digit-led numeric
# literals (`1`, `0x1a`) from identifiers.
_LEAN4_ID_FIRST_CHARS: frozenset[str] = frozenset(
    chr(cp)
    for lo, hi in (
        (65, 90), (95, 95), (97, 122),
        (192, 214), (216, 246), (248, 383),
        (913, 927), (929, 930), (932, 937),
        (945, 954), (956, 969),
        (970, 1019), (7936, 8190),
        (8448, 8527), (119964, 120223),
    )
    for cp in range(lo, hi + 1)
)
_LEAN4_ID_SUBSCRIPT_AND_DIGITS: frozenset[str] = frozenset(
    chr(cp)
    for lo, hi in ((48, 57), (7522, 7530), (8320, 8329), (8336, 8348), (11388, 11388))
    for cp in range(lo, hi + 1)
)
_LEAN4_WORD_CONT_CHARS: frozenset[str] = _LEAN4_ID_FIRST_CHARS | _LEAN4_ID_SUBSCRIPT_AND_DIGITS
_LEAN4_ID_REST_CHARS: frozenset[str] = _LEAN4_WORD_CONT_CHARS | frozenset("'!?")
_LEAN4_PANIC_PREV_CHARS: frozenset[str] = _LEAN4_ID_REST_CHARS | frozenset(".")
_LEAN4_DEC_NUM_CHARS: frozenset[str] = frozenset("0123456789_")
_LEAN4_BIN_NUM_CHARS: frozenset[str] = frozenset("01_")
_LEAN4_OCT_NUM_CHARS: frozenset[str] = frozenset("01234567_")
_LEAN4_HEX_NUM_CHARS: frozenset[str] = _LEAN4_HEX_DIGITS | frozenset("_")
_LEAN4_SIMPLE_GUILLEMET_INNER_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_']*\Z")
_LEAN4_INTERP_BANG_WORDS = frozenset(
    ("s", "f", "m", "v", "println", "reportIssue", "reportDbgIssue", "reportEMatchIssue")
)
_LEAN4_INTERP_KEYWORDS = frozenset(("dbg_trace", "throwError"))
_LEAN4_TRACE_BRACK_WORDS = frozenset(("trace", "trace_goal"))
_LEAN4_SYNTAX_QUOTE_KEYWORDS = frozenset(
    ("notation", "prefix", "infix", "infixl", "infixr", "postfix")
)

# Multiline sorry-injection / kernel-skip option check (`debug.skipKernelTC`, `debug.byAsSorry`, `debug.proofAsSorry`, `debug.terminalTacticsAsSorry`)
_LEAN4_SKIP_KERNEL_TC_RE = re.compile(
    r"\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b",
    flags=re.DOTALL,
)

# Output-spoofing / early-exit / module-initializer commands (`#eval`, `#eval!`, `#reduce`, `#guard_msgs`, non-`axioms` `#print`, `#exit`, `run_cmd`, `run_meta`, `initialize`, `builtin_initialize`)
_LEAN4_PRINT_AXIOMS_KW_BLOCK = (
    "def|theorem|lemma|axiom|inductive|structure|class|instance|opaque|abbrev|example|"
    "namespace|section|end|open|variable|universe|import|set_option|attribute|"
    "local|scoped|private|protected|noncomputable|partial|unsafe|meta|where|by|in|let|have"
)
_LEAN4_EVAL_SPOOF_RE = re.compile(
    r"#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|exit(?![\w'!?])|guard_msgs(?![\w'!?])|"
    r"print(?![\w'!?])(?!\s+axioms[ \t]+(?!(?:"
    + _LEAN4_PRINT_AXIOMS_KW_BLOCK
    + r")(?![\w'!?]))[A-Za-z_]))"
    r"|(?<!\.)\b(?:run_cmd|run_meta|initialize|builtin_initialize)\b",
    flags=re.DOTALL,
)

# Lean 4.22 module-aware import regex (supports single-line & multiline `public\n import Foo`)
_LEAN4_IMPORT_FULL_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)", flags=re.DOTALL
)

# Unsound attribute trust escapes (`@[...]` and post-declaration `attribute [...]`) vs `@[csimp]`/`attribute [csimp]`
_LEAN4_ATTR_OPEN_RE = re.compile(r"(?:@|(?<!\.)\battribute\s*)\[", flags=re.DOTALL)
_LEAN4_HARD_ATTR_KW_RE = re.compile(
    r"\b(extern|implemented_by|export|init|builtin_init|"
    r"term_elab|command_elab|tactic|macro|macro_rules|"
    r"builtin_term_elab|builtin_command_elab|builtin_tactic|builtin_macro|builtin_macro_rules)\b"
)
_LEAN4_CSIMP_ATTR_KW_RE = re.compile(r"\b(csimp)\b")


def _iter_lean4_attr_blocks(cleaned: str) -> list[tuple[int, int, int]]:
    """Return `(attr_start, body_lo, body_hi)` for every `@[...]` or `attribute [...]` block in O(n)."""
    match_rbrack: dict[int, int] = {}
    brack_stack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "[":
            brack_stack.append(idx)
        elif ch == "]" and brack_stack:
            match_rbrack[brack_stack.pop()] = idx
    blocks: list[tuple[int, int, int]] = []
    for m_open in _LEAN4_ATTR_OPEN_RE.finditer(cleaned):
        lb = m_open.end() - 1
        rb = match_rbrack.get(lb)
        if rb is not None:
            blocks.append((m_open.start(), lb + 1, rb))
    return blocks


def _match_lean4_char_literal_end(source: str, i: int, n: int) -> int | None:
    """Return end index of a Lean 4 Char literal starting at `source[i] == "'"`, or None."""
    if i + 2 < n and source[i + 1] not in ("\\", "'") and source[i + 2] == "'":
        return i + 3
    if i + 3 < n and source[i + 1] == "\\":
        if source[i + 3] == "'" and source[i + 2] != "\n":
            return i + 4
        esc = source[i + 2]
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

# Anti-vacuity notices (DeepMind formal-conjectures STATEMENTS.md & ExistsImplicationLinter)
_LEAN4_VACUOUS_THM_RE = re.compile(
    r"^\s*(?:private\s+|protected\s+)?(?:theorem|lemma)\s+[A-Za-z0-9_.']+\b[^:\n]*:\s*(?:False\s*(?:→|->)|True\s*:=)"
)
_LEAN4_EXISTS_IMP_RE = re.compile(r"∃[^,\n]+,\s*(?!.*(?:∀|∧))[^,\n]*(?:→|->)")


def _strip_lean4_with_report(source: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Char-literal-safe, raw-string-safe (`r"..."` and `r#"..."#`), interpolated-string-safe
    (`s!"{...}"` / `m!"{...}"`), and nested-block-comment-safe Lean 4 stripper preserving
    line count. Reports one finding per block comment or string still open at end of file
    so callers treat unterminated escapes as failed audits (R1).
    """
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    in_interp = False
    in_ident = False
    pending_interp = False
    trace_brack = 0
    in_syntax_header = False
    syntax_quote_reported = False
    interp_stack: list[list[int]] = []
    raw_hashes = -1
    opened_at = 0
    lex_issues: list[tuple[int, str]] = []
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
                if nxt == '"' and in_syntax_header and not syntax_quote_reported:
                    syntax_quote_reported = True
                    lex_issues.append((i, "LEAN4_SYNTAX_QUOTE_TOKEN"))
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
        if ch == "/" and nxt == "-":
            in_ident = False
            depth = 1
            opened_at = i
            out.append("  ")
            i += 2
            continue
        if ch == "-" and nxt == "-":
            in_ident = False
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch.isspace():
            in_ident = False
            out.append(ch)
            i += 1
            continue
        if ch != '"':
            pending_interp = False
        if ch != "[" and trace_brack == 1:
            trace_brack = 0
        if interp_stack:
            if ch == "{":
                in_ident = False
                interp_stack[-1][0] += 1
                out.append(ch)
                i += 1
                continue
            if ch == "}":
                in_ident = False
                interp_stack[-1][0] -= 1
                out.append(ch)
                i += 1
                if interp_stack[-1][0] == 0:
                    _, opened_at = interp_stack.pop()
                    in_interp = True
                continue
        if ch == "[" and trace_brack >= 1:
            in_ident = False
            trace_brack += 1
            out.append(ch)
            i += 1
        elif ch == "]" and trace_brack >= 2:
            in_ident = False
            trace_brack -= 1
            if trace_brack == 1:
                trace_brack = 0
                pending_interp = True
            out.append(ch)
            i += 1
        elif ch == "=" and nxt == ">":
            in_ident = False
            in_syntax_header = False
            out.append("=>")
            i += 2
        elif ch == '"':
            if pending_interp:
                in_interp = True
                pending_interp = False
            else:
                if in_ident and source[i - 1] == "!":
                    is_panic = (
                        i >= 6
                        and source[i - 6 : i] == "panic!"
                        and (i == 6 or source[i - 7] not in _LEAN4_PANIC_PREV_CHARS)
                    )
                    if not is_panic:
                        lex_issues.append((i, "LEAN4_UNKNOWN_BANG_STRING"))
                in_str = True
                syntax_quote_reported = False
            in_ident = False
            opened_at = i
            out.append(" ")
            i += 1
        elif ch == "«":
            in_ident = False
            end_g = source.find("»", i + 1)
            if end_g == -1:
                lex_issues.append((i, "LEAN4_UNTERMINATED_IDENT"))
                out.append("\n" * source.count("\n", i))
                break
            inner = source[i + 1 : end_g]
            if _LEAN4_SIMPLE_GUILLEMET_INNER_RE.match(inner) is not None and inner != "axioms":
                out.append(source[i : end_g + 1])
            else:
                out.append(" " + "".join("\n" if c == "\n" else " " for c in inner) + " ")
            i = end_g + 1
        elif ch == "'" and not in_ident:
            # Lean 4 char literals ('"', '<LF>', '\n', '\x27', '\u0027') without disturbing identifier primes x'
            char_end = _match_lean4_char_literal_end(source, i, n)
            if char_end is not None:
                out.append(" \n " if source[i + 1] == "\n" else " " * (char_end - i))
                i = char_end
            else:
                out.append(ch)
                i += 1
        else:
            if not in_ident and "0" <= ch <= "9":
                num_end = i + 1
                if ch == "0" and nxt in "xXbBoO":
                    num_end += 1
                    base_chars = (
                        _LEAN4_HEX_NUM_CHARS
                        if nxt in "xX"
                        else (_LEAN4_BIN_NUM_CHARS if nxt in "bB" else _LEAN4_OCT_NUM_CHARS)
                    )
                    while num_end < n and source[num_end] in base_chars:
                        num_end += 1
                else:
                    while num_end < n and source[num_end] in _LEAN4_DEC_NUM_CHARS:
                        num_end += 1
                    has_dot = False
                    if num_end < n and source[num_end] == "." and num_end + 1 < n and "0" <= source[num_end + 1] <= "9":
                        has_dot = True
                        num_end += 2
                        while num_end < n and source[num_end] in _LEAN4_DEC_NUM_CHARS:
                            num_end += 1
                    exp_start = num_end + 1 if (not has_dot and num_end < n and source[num_end] == ".") else num_end
                    if exp_start < n and source[exp_start] in "eE":
                        exp_pos = exp_start + 1
                        if exp_pos < n and source[exp_pos] in "+-":
                            exp_pos += 1
                        if exp_pos < n and "0" <= source[exp_pos] <= "9":
                            while exp_pos < n and source[exp_pos] in _LEAN4_DEC_NUM_CHARS:
                                exp_pos += 1
                            num_end = exp_pos
                out.append(" " * (num_end - i))
                i = num_end
                continue
            ident_prev = in_ident or (i > 0 and source[i - 1] == ".")
            if ch == "r" and not ident_prev:
                j = i + 1
                while j < n and source[j] == "#":
                    j += 1
                if j < n and source[j] == '"':
                    in_ident = False
                    raw_hashes = j - (i + 1)
                    opened_at = i
                    out.append(" " * (j - i + 1))
                    i = j + 1
                    continue
            if ch.isascii() and ch.isalpha() and not ident_prev:
                w_end = i + 1
                while w_end < n and source[w_end] in _LEAN4_WORD_CONT_CHARS:
                    w_end += 1
                word = source[i:w_end]
                if word == "Macro" and source.startswith(".trace", w_end):
                    end_mt = w_end + 6
                    if end_mt == n or source[end_mt] not in _LEAN4_ID_REST_CHARS:
                        if trace_brack == 0:
                            trace_brack = 1
                        in_ident = True
                        out.append(source[i:end_mt])
                        i = end_mt
                        continue
                next_ch = source[w_end] if w_end < n else ""
                if next_ch == "!" and word in _LEAN4_INTERP_BANG_WORDS:
                    after_bang = source[w_end + 1] if w_end + 1 < n else ""
                    if after_bang not in _LEAN4_ID_REST_CHARS:
                        pending_interp = True
                        in_ident = True
                        out.append(source[i : w_end + 1])
                        i = w_end + 1
                        continue
                if next_ch not in ".'!?":
                    if word in _LEAN4_INTERP_KEYWORDS:
                        pending_interp = True
                    elif word in _LEAN4_TRACE_BRACK_WORDS and trace_brack == 0:
                        trace_brack = 1
                    elif word in _LEAN4_SYNTAX_QUOTE_KEYWORDS:
                        in_syntax_header = True
                in_ident = True
                out.append(word)
                i = w_end
                continue
            in_ident = (ch in _LEAN4_ID_REST_CHARS) if in_ident else (ch in _LEAN4_ID_FIRST_CHARS)
            out.append(ch)
            i += 1
    unclosed_open = depth > 0 or in_str or in_interp or raw_hashes >= 0
    if unclosed_open or interp_stack:
        err_at = opened_at if unclosed_open else interp_stack[-1][1]
        lex_issues.append((err_at, "LEAN4_UNTERMINATED_COMMENT" if depth > 0 else "LEAN4_UNTERMINATED_STRING"))
    unterminated: list[dict[str, Any]] = []
    if lex_issues:
        lines = source.splitlines()
        cur_line = 1
        cur_pos = 0
        for pos, code in sorted(lex_issues):
            cur_line += source.count("\n", cur_pos, pos)
            cur_pos = pos
            unterminated.append({"line": cur_line, "code": code, "excerpt": lines[cur_line - 1].strip()[:100]})
    return "".join(out), unterminated


def _strip_lean4_comments_and_literals(source: str) -> str:
    """Cleaned Lean 4 source (comments and literals blanked, line count preserved)."""
    return _strip_lean4_with_report(source)[0]


def audit_lean4_source(
    source: str,
    *,
    allow_non_init_imports: bool = False,
    allow_project_imports: Sequence[str] = (),
    allowed_axioms: frozenset[str] = frozenset(),
    forbidden_import_prefixes: Sequence[str] = (),
) -> dict[str, Any]:
    """
    Hardened v1.2 static Lean 4 auditor (AUDIT-029 + Round-3 4-lab tomography):
      - Flags `sorry`, `admit`, `axiom`, `unsafe`, `native_decide`, `sorryAx`,
        `Lean.ofReduceBool`, `Lean.trustCompiler`, and multiline `debug.skipKernelTC`
      - Scopes `partial` to declarations (`partial def|instance|abbrev`) to avoid `.partial` FPs
      - Flags multiline `@[... extern | implemented_by ...]` as hard escapes and separates
        kernel-proved `@[csimp]` rewrites + `ExistsImplication` / vacuous signatures as notices
      - Parses Lean 4.22 `(public|private|meta)? import` with optional `allow_project_imports`
        and `forbidden_import_prefixes` (enforcing Spec -/-> Proof isolation)
    """
    cleaned, unterminated = _strip_lean4_with_report(source)
    cleaned = _LEAN4_GUILLEMET_IDENT_RE.sub(r"\1", cleaned)
    findings: list[dict[str, Any]] = list(unterminated)
    notices: list[dict[str, Any]] = []
    imports: list[str] = []

    for lineno, line in enumerate(cleaned.splitlines(), start=1):
        for pat, code in _LEAN4_HARD_LINE_RULES:
            if pat.search(line):
                if code == "LEAN4_AXIOM" and allowed_axioms:
                    m_ax = re.search(r"(?<!\.)\baxiom\s+([A-Za-z0-9_.']+)", line)
                    if m_ax is not None and m_ax.group(1) in allowed_axioms:
                        notices.append(
                            {
                                "line": lineno,
                                "code": "LEAN4_DOCUMENTED_CONDITIONAL_AXIOM",
                                "excerpt": m_ax.group(1),
                            }
                        )
                        continue
                findings.append({"line": lineno, "code": code, "excerpt": line.strip()[:100]})

        if _LEAN4_VACUOUS_THM_RE.search(line):
            notices.append(
                {"line": lineno, "code": "LEAN4_VACUOUS_SIGNATURE_NOTICE", "excerpt": line.strip()[:100]}
            )

        if _LEAN4_EXISTS_IMP_RE.search(line):
            notices.append(
                {"line": lineno, "code": "LEAN4_EXISTS_IMPLICATION_NOTICE", "excerpt": line.strip()[:100]}
            )

    # Full-buffer Lean 4.22 module-aware import scan (handles multiline `public\n import Foo`)
    imp_line, imp_pos = 1, 0
    for m_imp in _LEAN4_IMPORT_FULL_RE.finditer(cleaned):
        mod = m_imp.group(1)
        pos_m = m_imp.start(1)
        imp_line += cleaned.count("\n", imp_pos, pos_m)
        imp_pos = pos_m
        imports.append(mod)
        for pref in forbidden_import_prefixes:
            if mod == pref or mod.startswith(pref + "."):
                findings.append(
                    {"line": imp_line, "code": "LEAN4_FORBIDDEN_CHALLENGE_IMPORT", "excerpt": mod}
                )
        if not allow_non_init_imports:
            root_pkg = mod.split(".")[0]
            is_allowed_proj = any(
                mod == p or mod.startswith(p + ".") for p in allow_project_imports
            )
            if root_pkg not in ("Init", "Std") and not is_allowed_proj:
                findings.append({"line": imp_line, "code": "LEAN4_NON_INIT_IMPORT", "excerpt": mod})

    # Multiline declaration-scoped `partial` check (`partial\n def ...`, zero FP on `.partial`)
    part_line, part_pos = 1, 0
    for m_part in _LEAN4_PARTIAL_DECL_RE.finditer(cleaned):
        pos_m = m_part.start()
        part_line += cleaned.count("\n", part_pos, pos_m)
        part_pos = pos_m
        findings.append({"line": part_line, "code": "LEAN4_PARTIAL", "excerpt": " ".join(m_part.group(0).split())[:100]})

    # Multiline declaration-scoped `opaque` check (`opaque\n foo ...`, zero FP on `.opaque` / `def opaque : ...`)
    opaq_line, opaq_pos = 1, 0
    for m_opaq in _LEAN4_OPAQUE_DECL_RE.finditer(cleaned):
        pos_m = m_opaq.start()
        opaq_line += cleaned.count("\n", opaq_pos, pos_m)
        opaq_pos = pos_m
        findings.append({"line": opaq_line, "code": "LEAN4_OPAQUE", "excerpt": " ".join(m_opaq.group(0).split())[:100]})

    # Lean 4.15+ `decide +native`, `(native := <non-false>)`, `(config := { native := <non-false> })`, & bound DecideConfig
    decide_spans = _scan_lean4_decide_native(cleaned)
    dec_line = 1
    dec_pos = 0
    for ds, de in decide_spans:
        dec_line += cleaned.count("\n", dec_pos, ds)
        dec_pos = ds
        findings.append(
            {
                "line": dec_line,
                "code": "LEAN4_DECIDE_NATIVE",
                "excerpt": " ".join(cleaned[ds : min(de, ds + 200)].split())[:100],
            }
        )
    dc_line, dc_pos = 1, 0
    for m_dc in _LEAN4_DECIDE_CONFIG_BIND_RE.finditer(cleaned):
        if any(m_dc.start() in range(ds, de) for ds, de in decide_spans):
            continue
        if not _lean4_match_enables_native(m_dc):
            continue
        pos_m = m_dc.start()
        dc_line += cleaned.count("\n", dc_pos, pos_m)
        dc_pos = pos_m
        findings.append(
            {"line": dc_line, "code": "LEAN4_DECIDE_NATIVE", "excerpt": " ".join(m_dc.group(0).split())[:100]}
        )

    # Multiline debug.{skipKernelTC, byAsSorry, proofAsSorry, terminalTacticsAsSorry} check
    sk_line, sk_pos = 1, 0
    for m_sk in _LEAN4_SKIP_KERNEL_TC_RE.finditer(cleaned):
        pos_m = m_sk.start()
        sk_line += cleaned.count("\n", sk_pos, pos_m)
        sk_pos = pos_m
        findings.append(
            {"line": sk_line, "code": "LEAN4_SKIP_KERNEL_TC", "excerpt": " ".join(m_sk.group(0).split())[:100]}
        )

    # Output-spoofing / early-exit commands (#eval, #eval!, #reduce, #guard_msgs, non-axioms #print, #exit)
    ev_line, ev_pos = 1, 0
    for m_ev in _LEAN4_EVAL_SPOOF_RE.finditer(cleaned):
        pos_m = m_ev.start()
        ev_line += cleaned.count("\n", ev_pos, pos_m)
        ev_pos = pos_m
        findings.append({"line": ev_line, "code": "LEAN4_EVAL_SPOOF", "excerpt": m_ev.group(0)})

    # Multiline attribute trust-escape and csimp notice check: `@[...]` and post-declaration `attribute [...]`
    attr_line, attr_pos = 1, 0
    for attr_start, b_lo, b_hi in _iter_lean4_attr_blocks(cleaned):
        attr_line += cleaned.count("\n", attr_pos, attr_start)
        attr_pos = attr_start
        m_attr = _LEAN4_HARD_ATTR_KW_RE.search(cleaned, b_lo, b_hi)
        if m_attr is not None:
            findings.append({"line": attr_line, "code": "LEAN4_ATTR_TRUST_ESCAPE", "excerpt": m_attr.group(1)})
        m_cs = _LEAN4_CSIMP_ATTR_KW_RE.search(cleaned, b_lo, b_hi)
        if m_cs is not None:
            notices.append({"line": attr_line, "code": "LEAN4_CSIMP_REWRITE_NOTICE", "excerpt": m_cs.group(1)})

    return {"clean": len(findings) == 0, "findings": findings, "notices": notices, "imports": imports}


def audit_lean4_directory(
    root: Path,
    *,
    allow_non_init_imports: bool = False,
    allow_project_imports: Sequence[str] = (),
    allowed_axioms: frozenset[str] = frozenset(),
    forbidden_import_prefixes: Sequence[str] = (),
) -> dict[str, Any]:
    """Scan all `.lean` files under `root` with the hardened v1.2 static Lean 4 auditor."""
    lean_files = [root] if root.is_file() and root.suffix == ".lean" else [
        p for p in sorted(root.rglob("*.lean"))
        if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(root).parts)
    ]
    all_findings: list[dict[str, Any]] = []
    all_notices: list[dict[str, Any]] = []
    for lf in lean_files:
        rel = lf.name if root.is_file() else str(lf.relative_to(root))
        res = audit_lean4_source(
            lf.read_text(encoding="utf-8", errors="replace"),
            allow_non_init_imports=allow_non_init_imports,
            allow_project_imports=allow_project_imports,
            allowed_axioms=allowed_axioms,
            forbidden_import_prefixes=forbidden_import_prefixes,
        )
        for f in res["findings"]:
            all_findings.append({"file": rel, **f})
        for n in res["notices"]:
            all_notices.append({"file": rel, **n})
    return {
        "files_checked": len(lean_files),
        "clean": len(all_findings) == 0,
        "findings": all_findings,
        "notices": all_notices,
    }


def validate_comparator_config(
    config_path: Path,
    *,
    lean_root: Path | None = None,
    require_nanoda: bool = True,
    allow_extra_axioms: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """
    Validate a Lean 4 Comparator JSON config (OpenAI / Anthropic / DeepMind standard):
      - Verifies challenge_module, solution_module, non-empty theorem_names, permitted_axioms
      - Enforces `enable_nanoda: true` (independent second Rust kernel) when `require_nanoda=True`
      - If `lean_root` is provided, confirms both files exist and solution never imports challenge
    """
    data = load_strict_json_file(config_path, allow_float=False, require_object=True)
    errors: list[str] = []
    warnings: list[str] = []

    chl_mod = data.get("challenge_module")
    sol_mod = data.get("solution_module")
    thms = data.get("theorem_names")
    axioms = data.get("permitted_axioms")
    enable_nanoda = data.get("enable_nanoda")

    if not isinstance(chl_mod, str) or not _LEAN4_MOD_NAME_RE.match(chl_mod):
        errors.append("INVALID_OR_MISSING_CHALLENGE_MODULE")
    if not isinstance(sol_mod, str) or not _LEAN4_MOD_NAME_RE.match(sol_mod):
        errors.append("INVALID_OR_MISSING_SOLUTION_MODULE")
    if not isinstance(thms, list) or not thms or any(not isinstance(t, str) or not t.strip() for t in thms):
        errors.append("EMPTY_OR_INVALID_THEOREM_NAMES")
    if not isinstance(axioms, list) or any(not isinstance(a, str) for a in axioms):
        errors.append("INVALID_PERMITTED_AXIOMS")
    else:
        allowed_all = STANDARD_LEAN4_AXIOMS | allow_extra_axioms
        extra = sorted(a for a in axioms if a not in allowed_all)
        if extra:
            errors.append(f"UNDECLARED_NONSTANDARD_AXIOMS:{','.join(extra)}")

    if isinstance(chl_mod, str) and chl_mod == sol_mod:
        errors.append(f"CHALLENGE_EQUALS_SOLUTION_MODULE:{chl_mod}")

    if enable_nanoda is not True:
        msg = f"NANODA_DISABLED_OR_OMITTED:{enable_nanoda!r}"
        if require_nanoda:
            errors.append(msg)
        else:
            warnings.append(msg)

    if (
        lean_root is not None
        and isinstance(chl_mod, str)
        and isinstance(sol_mod, str)
        and _LEAN4_MOD_NAME_RE.match(chl_mod) is not None
        and _LEAN4_MOD_NAME_RE.match(sol_mod) is not None
    ):
        root_res = lean_root.resolve()
        chl_path = (root_res / Path(*chl_mod.split(".")).with_suffix(".lean")).resolve()
        sol_path = (root_res / Path(*sol_mod.split(".")).with_suffix(".lean")).resolve()
        if not chl_path.is_relative_to(root_res):
            errors.append(f"CHALLENGE_PATH_OUTSIDE_ROOT:{chl_mod}")
        elif not chl_path.is_file():
            errors.append(f"MISSING_CHALLENGE_FILE:{chl_path.name}")
        if not sol_path.is_relative_to(root_res):
            errors.append(f"SOLUTION_PATH_OUTSIDE_ROOT:{sol_mod}")
        elif not sol_path.is_file():
            errors.append(f"MISSING_SOLUTION_FILE:{sol_path.name}")
        else:
            sol_audit = audit_lean4_source(
                sol_path.read_text(encoding="utf-8", errors="replace"),
                allow_non_init_imports=True,
                allowed_axioms=allow_extra_axioms,
                forbidden_import_prefixes=(chl_mod,),
            )
            if not sol_audit["clean"]:
                for f in sol_audit["findings"]:
                    errors.append(f"SOLUTION_AUDIT:{f['code']}@L{f['line']}")

    return {"path": str(config_path), "passed": len(errors) == 0, "errors": errors, "warnings": warnings}


# What `git rev-parse --local-env-vars` lists. Inherited (for example inside a git hook), these would point
# the history search at another repository, index, object store or config, so they are removed for it.
_GIT_LOCAL_ENV_VARS = frozenset({
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX", "GIT_SHALLOW_FILE",
    "GIT_COMMON_DIR",
})
_GIT_HISTORY_TIMEOUT_S = 60


def _git_history_env() -> dict[str, str]:
    """Environment for the read-only history search: local repository variables removed, no network."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_LOCAL_ENV_VARS}
    env.update({
        "GIT_LITERAL_PATHSPECS": "1",  # the pinned path is a file name, never a glob or `:(magic)` pathspec
        "GIT_NO_LAZY_FETCH": "1",  # never fetch a missing object from a promisor remote
        "GIT_ALLOW_PROTOCOL": "",  # and allow no transport should a fetch be attempted anyway
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",  # hash the stored objects, not `git replace` substitutes
    })
    return env


def _git_revision_with_sha256(base_dir: Path, target: Path, want: str) -> tuple[str | None, str]:
    """
    Find the newest commit on HEAD at which `target` held bytes whose SHA-256 is `want`.

    Searches the git work tree holding `base_dir`: the commits on HEAD that touched the path
    (`git rev-list --full-history`, renames not followed), newest first, hashing the blob bytes each
    revision holds at the path (`git cat-file blob`), so a match is measured, never declared. A revision
    at which the path is absent (a deletion) or is not a file has no blob to read and is skipped.
    Returns `(commit, history)`; `history` says how much a miss shows:

    - `complete`: a full clone (not shallow, no promisor remote), at least one commit touched the path,
      and the blob of every listed revision was read.
    - `partial`: a shallow or partial (promisor) clone, git could not say which, or the blob of a listed
      revision could not be read (missing objects are never fetched). A miss does not show that the
      bytes never existed; a match names the newest matching commit among the blobs read.
    - `untracked`: no commit on HEAD touched the path (an untracked file, or a directory inside an
      unrelated repository). No history of these bytes was searched.
    - `unavailable`: no git, no work tree holding `base_dir`, the target outside it, an unborn HEAD,
      or a git call failed or timed out.
    """
    env = _git_history_env()

    def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, env=env, timeout=_GIT_HISTORY_TIMEOUT_S, check=False,
        )

    try:
        top_res = _git(base_dir, "rev-parse", "--show-toplevel")
        top_out = os.fsdecode(top_res.stdout).strip()
        top = Path(top_out).resolve()
        if top_res.returncode != 0 or not top_out or not target.is_relative_to(top):
            return None, "unavailable"
        rel = target.relative_to(top).as_posix()
        shallow_res = _git(top, "rev-parse", "--is-shallow-repository")
        promisor_res = _git(top, "config", "--get-regexp", r"^(extensions\.partialclone|remote\..+\.promisor)$")
        full_clone = (
            shallow_res.returncode == 0 and shallow_res.stdout.strip() == b"false"
            and promisor_res.returncode == 1 and promisor_res.stdout.strip() == b""
        )
        list_res = _git(top, "rev-list", "--full-history", "HEAD", "--", rel)
        if list_res.returncode != 0:
            return None, "unavailable"
        commits = list_res.stdout.decode("ascii", "replace").split()
        if not commits:
            return None, "untracked"
        unread = False
        rel_bytes = os.fsencode(rel)
        for commit in commits:
            tree_res = _git(top, "ls-tree", "-z", commit, "--", rel)
            if tree_res.returncode != 0:
                unread = True
                continue
            blob_oid: str | None = None
            for record in tree_res.stdout.split(b"\0"):
                meta, _, name = record.partition(b"\t")
                fields = meta.split(b" ")
                if name == rel_bytes and len(fields) == 3 and fields[1] == b"blob":
                    blob_oid = fields[2].decode("ascii", "replace")
            if blob_oid is None:
                continue  # the path is absent at this revision, or is not a file there
            blob = _git(top, "cat-file", "blob", blob_oid)
            if blob.returncode != 0:
                unread = True
                continue
            if canonical_sha256_bytes(blob.stdout) == want:
                return commit, ("complete" if full_clone and not unread else "partial")
    except (OSError, subprocess.TimeoutExpired):  # no git binary, or a git call hung
        return None, "unavailable"
    return None, ("complete" if full_clone and not unread else "partial")


def _classify_pinned_mismatch(base_dir: Path, target: Path, rel: str, want: str, actual: str) -> dict[str, Any]:
    """`STALE` when the pinned hash is an older revision of the file in git history, else `UNKNOWN`."""
    commit, history = _git_revision_with_sha256(base_dir, target, want)
    return {
        "path": rel,
        "status": "UNKNOWN" if commit is None else "STALE",
        "stale_commit": commit,
        "history": history,
        "expected_sha256": want,
        "actual_sha256": actual,
    }


def validate_pinned_manifest(manifest_path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """
    Validate a cryptographic pinning manifest (`CORE_MANIFEST.json` SHA-256 spec pinning
    from DeepMind/cryptids OR `SafeVerify` 40-hex commit-SHA manifest from Mistral/FLTEval).

    Each `PINNED_FILE_SHA256_MISMATCH` also gets an entry in `mismatches`: `STALE` with the commit when
    the pinned hash equals an older revision of that file in the git history holding the root, else
    `UNKNOWN`, with how much a miss shows (`history`: `complete`, `partial`, `untracked` or `unavailable`,
    see `_git_revision_with_sha256`). Both still fail the manifest. The search reads local objects only.
    """
    data = load_strict_json_file(manifest_path, allow_float=True, require_object=True)
    base_dir = (root if root is not None else manifest_path.parent).resolve()
    errors: list[str] = []
    mismatches: list[dict[str, Any]] = []
    files_verified = 0
    commits_verified = 0

    # Format 1: file SHA-256 map (`files: {rel_path: sha256}` or `entries: [{path, sha256}]`)
    if "files" in data:
        files_map = data["files"]
        if not isinstance(files_map, dict):
            errors.append("INVALID_FILES_SECTION_TYPE")
        else:
            for rel, expected in files_map.items():
                if not isinstance(rel, str) or not isinstance(expected, str) or not _LEAN4_SHA256_RE.match(expected):
                    errors.append(f"INVALID_FILE_HASH_ENTRY:{rel!r}")
                    continue
                target = (base_dir / rel).resolve()
                if not target.is_relative_to(base_dir):
                    errors.append(f"PINNED_FILE_OUTSIDE_ROOT:{rel}")
                    continue
                if not target.is_file():
                    errors.append(f"PINNED_FILE_MISSING:{rel}")
                    continue
                actual = canonical_sha256_bytes(target.read_bytes())
                want = expected.split(":", 1)[-1].lower()
                if actual != want:
                    errors.append(f"PINNED_FILE_SHA256_MISMATCH:{rel}")
                    mismatches.append(_classify_pinned_mismatch(base_dir, target, rel, want, actual))
                else:
                    files_verified += 1

    if "entries" in data:
        entries = data["entries"]
        if not isinstance(entries, list):
            errors.append("INVALID_ENTRIES_SECTION_TYPE")
        else:
            for idx, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    errors.append(f"INVALID_ENTRY_TYPE:{idx}")
                    continue
                rel = entry.get("path")
                expected = entry.get("sha256")
                if not isinstance(rel, str) or not isinstance(expected, str) or not _LEAN4_SHA256_RE.match(expected):
                    errors.append(f"INVALID_ENTRY_SPEC:{idx}")
                    continue
                target = (base_dir / rel).resolve()
                if not target.is_relative_to(base_dir):
                    errors.append(f"PINNED_FILE_OUTSIDE_ROOT:{rel}")
                    continue
                if not target.is_file():
                    errors.append(f"PINNED_FILE_MISSING:{rel}")
                    continue
                actual = canonical_sha256_bytes(target.read_bytes())
                want = expected.split(":", 1)[-1].lower()
                if actual != want:
                    errors.append(f"PINNED_FILE_SHA256_MISMATCH:{rel}")
                    mismatches.append(_classify_pinned_mismatch(base_dir, target, rel, want, actual))
                else:
                    files_verified += 1

    # Format 2: SafeVerify / toolchain commit-SHA pinning (`commit` / `rev` / `pins: {name: {commit/rev}}`)
    for top_key in ("commit", "rev", "source_commit"):
        if top_key in data:
            val = data[top_key]
            if not isinstance(val, str) or not _LEAN4_SHA40_RE.match(val):
                errors.append(f"INVALID_COMMIT_SHA:{top_key}")
            else:
                commits_verified += 1

    if "pins" in data:
        pins = data["pins"]
        if not isinstance(pins, dict):
            errors.append("INVALID_PINS_SECTION_TYPE")
        else:
            for pname, pobj in pins.items():
                sha_val = pobj if isinstance(pobj, str) else (
                    pobj.get("commit") or pobj.get("rev") if isinstance(pobj, dict) else None
                )
                if not isinstance(sha_val, str) or not _LEAN4_SHA40_RE.match(sha_val):
                    errors.append(f"INVALID_PIN_COMMIT_SHA:{pname}")
                else:
                    commits_verified += 1

    if files_verified == 0 and commits_verified == 0 and not errors:
        errors.append("EMPTY_PINNED_MANIFEST")

    return {
        "path": str(manifest_path),
        "passed": len(errors) == 0,
        "files_verified": files_verified,
        "commits_verified": commits_verified,
        "errors": errors,
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# v1.1 Git-DAG Preregistration Check (Gate 8, inspired by siliquant)
# ---------------------------------------------------------------------------

def verify_preregistration_git_dag(
    repo_root: Path,
    *,
    plan_commit: str | None = None,
    data_commit: str | None = None,
    plan_path: str = "cartography/frontier_portals.md",
    data_path: str = "verification/AUDIT_LOG.md",
) -> dict[str, Any]:
    """
    Mechanical Gate 8 preregistration check (strict git ancestor: `plan != data` and
    `git merge-base --is-ancestor <plan> <data>`).
    When explicit commits are omitted, locates the LATEST commit touching `plan_path` and
    the EARLIEST commit introducing `data_path`, closing HARKing/post-hoc plan rewrites,
    typo-commit masking, and same-commit bulk bundling.
    """
    root = repo_root.resolve()
    def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)

    in_git = _git(["rev-parse", "--is-inside-work-tree"])
    if in_git.returncode != 0:
        return {"checked": False, "passed": False, "reason": "not a git repository", "plan_commit": None, "data_commit": None}

    p_sha = plan_commit
    d_sha = data_commit
    if p_sha is None:
        # LATEST commit touching plan_path (prevents post-hoc plan rewrite after data!)
        r_p = _git(["log", "--topo-order", "-n", "1", "--format=%H", "--", plan_path])
        lines = [ln.strip() for ln in r_p.stdout.splitlines() if ln.strip()]
        p_sha = lines[0] if lines else None
    if d_sha is None:
        # EARLIEST commit introducing data_path (prevents masking HARKing behind later typo edits!)
        r_d = _git(["log", "--topo-order", "--reverse", "--format=%H", "--", data_path])
        lines = [ln.strip() for ln in r_d.stdout.splitlines() if ln.strip()]
        d_sha = lines[0] if lines else None

    if not p_sha or not d_sha:
        return {
            "checked": True,
            "passed": False,
            "reason": f"missing git history for plan ({plan_path!r}) or data ({data_path!r})",
            "plan_commit": p_sha,
            "data_commit": d_sha,
        }

    if p_sha.startswith("-") or d_sha.startswith("-"):
        return {
            "checked": True,
            "passed": False,
            "reason": "invalid commit ref starting with '-'",
            "plan_commit": p_sha,
            "data_commit": d_sha,
        }

    # Resolve canonical 40-hex commit SHAs before strict inequality check
    rp_res = _git(["rev-parse", "--verify", f"{p_sha}^{{commit}}"])
    rd_res = _git(["rev-parse", "--verify", f"{d_sha}^{{commit}}"])
    if rp_res.returncode != 0 or rd_res.returncode != 0:
        return {
            "checked": True,
            "passed": False,
            "reason": "unresolvable plan_commit or data_commit ref",
            "plan_commit": p_sha,
            "data_commit": d_sha,
        }
    p_canon = rp_res.stdout.strip()
    d_canon = rd_res.stdout.strip()

    if p_canon == d_canon:
        return {
            "checked": True,
            "passed": False,
            "reason": "plan and data share the same commit (strict preregistration requires plan strictly before data)",
            "plan_commit": p_canon,
            "data_commit": d_canon,
        }

    # In auto-discovery mode (data_commit omitted), verify no ancestor-or-self of plan_commit touched data_path
    if data_commit is None:
        pre_data = _git(["rev-list", "-n", "1", p_canon, "--", data_path])
        if pre_data.returncode == 0 and pre_data.stdout.strip():
            return {
                "checked": True,
                "passed": False,
                "reason": "data_path already existed at or before latest plan commit",
                "plan_commit": p_canon,
                "data_commit": pre_data.stdout.strip(),
            }

    anc = _git(["merge-base", "--is-ancestor", p_canon, d_canon])
    is_strict_anc = (anc.returncode == 0)
    return {
        "checked": True,
        "passed": is_strict_anc,
        "reason": "plan commit is a verified strict git ancestor of earliest data/audit commit" if is_strict_anc else "plan commit is NOT a strict ancestor of earliest data/audit commit",
        "plan_commit": p_canon,
        "data_commit": d_canon,
    }


def run_r4_script_check(
    script_path: Path,
    *,
    cwd: Path | None = None,
    timeout: int = 120,
    isolated: bool = True,
) -> dict[str, Any]:
    """
    Execute `script_path` across all 3 R4 modes:
      - mode_B:      python3 [-I] -B <script>
      - mode_OB:     python3 [-I] -O -B <script>
      - mode_Werror: python3 [-I] -B -W error <script>
    Verify exit code 0 in all 3 modes AND bit-identical stdout SHA-256!
    """
    require_ok(script_path.is_file(), "SCRIPT_NOT_FOUND", f"script not found: {script_path}")
    iso = ["-I"] if isolated else []
    modes: list[tuple[str, list[str]]] = [
        ("B", [sys.executable, *iso, "-B", str(script_path)]),
        ("O_B", [sys.executable, *iso, "-O", "-B", str(script_path)]),
        ("B_Werror", [sys.executable, *iso, "-B", "-W", "error", str(script_path)]),
    ]
    run_dir = str((cwd or script_path.parent).resolve())
    mode_results: dict[str, dict[str, Any]] = {}
    hashes: set[str] = set()
    all_zero = True

    for label, cmd in modes:
        try:
            proc = subprocess.run(
                cmd,
                cwd=run_dir,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            h = canonical_sha256_bytes(proc.stdout)
            hashes.add(h)
            if proc.returncode != 0:
                all_zero = False
            stderr_text = proc.stderr.decode("utf-8", errors="replace")
            m_skip = _UNITTEST_SKIP_RE.search(stderr_text)
            m_ran = _UNITTEST_RAN_RE.search(stderr_text)
            mode_results[label] = {
                "returncode": proc.returncode,
                "stdout_sha256": h,
                "stdout_bytes": len(proc.stdout),
                "tests_ran": int(m_ran.group(1)) if m_ran else None,
                "tests_skipped": int(m_skip.group(1)) if m_skip else 0,
                "stderr_tail": stderr_text[-400:],
            }
        except subprocess.TimeoutExpired:
            all_zero = False
            mode_results[label] = {
                "returncode": -1,
                "stdout_sha256": "",
                "stdout_bytes": 0,
                "tests_ran": None,
                "tests_skipped": 0,
                "stderr_tail": f"TIMEOUT after {timeout}s",
            }

    bit_identical = all_zero and len(hashes) == 1
    skip_counts = {mode_results[lbl]["tests_skipped"] for lbl, _ in modes}
    ran_counts = {mode_results[lbl]["tests_ran"] for lbl, _ in modes}
    # aletheia#5 #2: fail R4 if -O silently skips tests that ran in plain mode
    skip_parity = len(skip_counts) == 1 and len(ran_counts) == 1
    return {
        "script": str(script_path),
        "isolated": isolated,
        "passed": all_zero and bit_identical and skip_parity,
        "all_exit_zero": all_zero,
        "stdout_bit_identical": bit_identical,
        "skip_parity": skip_parity,
        "modes": mode_results,
    }


def verify_ancestor_dir_modes(dir_modes: Sequence[tuple[str, int]]) -> dict[str, Any]:
    """
    Canonical Ancestor-Directory Permission Gate (v1.4, reverse-extracted from
    `warp-drive` `harden-image-modes.sh` & `AUDIT-062R` `BYPASS-04`):
      - Requires a non-empty sequence of `(canonical_abs_path, strict_int_mode)` pairs
      - Rejects non-canonical paths (leading `//`, embedded `//`, `.`, `..`, trailing `/`,
        NUL or newline characters, non-absolute paths, and duplicate path entries)
      - Rejects non-`int` / `bool` modes and out-of-range modes outside `[0, 0o7777]`
      - Rejects group/world-writable directories (`(mode & 0o022) != 0`) so unprivileged
        actors cannot rename-swap read-only verifier or policy files
      - Requires EVERY strict ancestor from `/` through parent to be explicitly present.
    """
    findings: list[dict[str, Any]] = []
    if not isinstance(dir_modes, (list, tuple)) or len(dir_modes) == 0:
        findings.append({"code": "EMPTY_DIR_MODES", "path": "", "message": "dir_modes must be a non-empty sequence"})
        return {"passed": False, "checked_dirs": 0, "errors": [f["code"] for f in findings], "findings": findings}

    seen_modes: dict[str, int] = {}
    for idx, entry in enumerate(dir_modes):
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            findings.append({"code": "INVALID_ENTRY", "path": f"[{idx}]", "message": "entry must be a (path, mode) pair"})
            continue
        path_str, mode = entry[0], entry[1]
        if (
            type(path_str) is not str
            or not path_str.startswith("/")
            or "\x00" in path_str
            or "\n" in path_str
            or "\r" in path_str
            or (path_str != "/" and any(seg in ("", ".", "..") for seg in path_str.split("/")[1:]))
        ):
            findings.append({"code": "NON_CANONICAL_PATH", "path": repr(path_str), "message": "path must be canonical POSIX absolute path"})
            continue
        if type(mode) is not int or mode < 0 or mode > 0o7777:
            findings.append({"code": "INVALID_MODE", "path": path_str, "message": f"mode must be exact int in [0, 0o7777], got {mode!r}"})
            continue
        if path_str in seen_modes:
            findings.append({"code": "DUPLICATE_PATH", "path": path_str, "message": "duplicate directory path in ancestor chain"})
            continue
        seen_modes[path_str] = mode
        if (mode & 0o022) != 0:
            findings.append({
                "code": "WRITABLE_ANCESTOR_MODE",
                "path": path_str,
                "mode_octal": oct(mode),
                "message": f"directory {path_str} has group/world write bits set ({oct(mode)})",
            })

    for path_str in sorted(seen_modes):
        if path_str == "/":
            continue
        if "/" not in seen_modes:
            findings.append({"code": "MISSING_ANCESTOR", "path": "/", "message": f"root '/' missing for {path_str}"})
        parts = path_str.split("/")[1:]
        for depth in range(1, len(parts)):
            ancestor = "/" + "/".join(parts[:depth])
            if ancestor not in seen_modes:
                findings.append({
                    "code": "MISSING_ANCESTOR",
                    "path": ancestor,
                    "message": f"strict ancestor {ancestor} missing for {path_str}",
                })

    return {
        "passed": len(findings) == 0,
        "checked_dirs": len(seen_modes),
        "errors": sorted({f["code"] for f in findings}),
        "findings": findings,
    }


def audit_ancestor_dir_permissions(target_path: Path) -> dict[str, Any]:
    """Inspect real filesystem permissions along the full canonical ancestor chain of `target_path`."""
    resolved = target_path.resolve()
    require_ok(resolved.exists(), "TARGET_NOT_FOUND", f"target path does not exist: {resolved}")
    base_dir = resolved if resolved.is_dir() else resolved.parent
    chain_paths = list(reversed([base_dir, *base_dir.parents]))
    dir_modes: list[tuple[str, int]] = []
    for d in chain_paths:
        st = os.stat(d)
        dir_modes.append((str(d), stat.S_IMODE(st.st_mode)))
    res = verify_ancestor_dir_modes(dir_modes)
    res["target"] = str(base_dir)
    return res


_SYMLINK_CODES = frozenset({"SYMLINK_DIR", "SYMLINK_OUTSIDE_ROOT", "BROKEN_SYMLINK"})


def _err_detail(exc: OSError) -> str:
    name = errno.errorcode.get(exc.errno, "") if exc.errno is not None else ""
    return f"{type(exc).__name__}{'/' + name if name else ''}: {exc.strerror or 'os error'}"


def _read_regular_bytes(p: Path) -> bytes:
    """Read `p` only if it is a regular file (opened non-blocking so a swapped-in FIFO cannot hang the scan)."""
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        require_ok(stat.S_ISREG(os.fstat(fd).st_mode), "NON_REGULAR_FILE", f"not a regular file: {p.name}")
        with os.fdopen(fd, "rb", closefd=False) as fh:
            return fh.read()
    finally:
        os.close(fd)


def _walk_classified(root: Path) -> tuple[list[Path], list[Path], list[dict[str, str]], list[dict[str, str]]]:
    """
    Walk `root` without ever following a symlink or reading anything, classifying every entry with `os.lstat`.
    Returns `(files_to_scan, pycache_entries, path_findings, symlinks)`.
    """
    real_root = os.path.realpath(root)
    files: list[Path] = []
    pycache: list[Path] = []
    findings: list[dict[str, str]] = []
    symlinks: list[dict[str, str]] = []

    def find(p: Path, code: str, detail: str) -> None:
        findings.append({"file": str(p.relative_to(root)), "code": code, "detail": detail})

    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                children = sorted(Path(e.path) for e in it)
        except OSError as exc:
            find(d, "UNREADABLE_FILE", f"directory not listable: {_err_detail(exc)}")
            continue
        for p in children:
            rel_parts = p.relative_to(root).parts
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            try:
                st = os.lstat(p)
            except OSError as exc:
                find(p, "UNREADABLE_FILE", _err_detail(exc))
                continue
            scan = False
            if stat.S_ISLNK(st.st_mode):
                target = os.path.realpath(p)
                outside = not Path(target).is_relative_to(real_root)
                try:
                    tmode = os.stat(p).st_mode
                except OSError as exc:
                    tmode = None
                    find(p, "BROKEN_SYMLINK", f"symlink target unavailable ({_err_detail(exc)}): {os.readlink(p)}")
                kind = "broken" if tmode is None else "dir" if stat.S_ISDIR(tmode) else "file" if stat.S_ISREG(tmode) else "other"
                symlinks.append({"file": str(p.relative_to(root)), "target": os.readlink(p), "kind": kind})
                if tmode is not None and outside:
                    find(p, "SYMLINK_OUTSIDE_ROOT", f"symlink resolves outside the scan root: {target}")
                if kind == "dir":
                    find(p, "SYMLINK_DIR", "symlink to a directory (not followed, contents not audited)")
                elif kind == "other":
                    find(p, "NON_REGULAR_FILE", "symlink to a non-regular file (never read)")
                scan = kind == "file" and not outside
            elif stat.S_ISDIR(st.st_mode):
                stack.append(p)
            elif stat.S_ISREG(st.st_mode):
                scan = True
            else:
                find(p, "NON_REGULAR_FILE", f"non-regular file (mode {oct(stat.S_IFMT(st.st_mode))}), never read")
            if "__pycache__" in rel_parts or p.suffix in (".pyc", ".pyo"):
                pycache.append(p)
            elif scan:
                files.append(p)
    return sorted(files), sorted(pycache), sorted(findings, key=lambda f: (f["file"], f["code"])), sorted(
        symlinks, key=lambda f: f["file"]
    )


def run_audit_check(
    target_path: Path,
    *,
    scripts: Sequence[Path] = (),
    audit_log: Path | None = None,
    receipt: Path | None = None,
    strict_unseeded: bool = False,
    strict_ancestors: bool = False,
    allow_bare_assert_in_tests: bool = False,
    isolated: bool = True,
    timeout: int = 120,
    lean_audit: bool = False,
    allow_project_imports: Sequence[str] = (),
    comparator_config: Path | None = None,
    require_nanoda: bool = True,
    pinned_manifest: Path | None = None,
    prereg_check: bool = False,
    plan_commit: str | None = None,
    data_commit: str | None = None,
    safety_scan: bool = False,
    include_host_hygiene: bool = False,
    allow_symlinks: bool = False,
    outside_rulings: Path | None = None,
    strict_novelty: bool = False,
) -> dict[str, Any]:
    """Run the Aletheia R1-R4 hygiene & Gate 1-9 audit check on `target_path`, plus a Gate 10 record check
    (R5 is `aletheia mutate`; R6/R7 not automated by this command).

    `outside_rulings` (an `outside_observer.rulings.v1` file) and `strict_novelty` feed the novelty
    status of `VERIFIED` `N2` ledger rows (see `validate_audit_log_markdown`): whether a second pass
    (a `G10` entry or an outside ruling) is on record, not what it decided. Both need a ledger.
    """
    try:
        raw_st = os.lstat(target_path)
    except FileNotFoundError as exc:
        raise AletheiaError("TARGET_NOT_FOUND", f"target path does not exist: {target_path}") from exc
    except OSError as exc:
        raise AletheiaError("TARGET_UNREADABLE", f"cannot stat target path ({_err_detail(exc)}): {target_path}") from exc
    require_ok(
        not (stat.S_ISLNK(raw_st.st_mode) and not allow_symlinks),
        "TARGET_IS_SYMLINK",
        f"target path is a symlink (pass --allow-symlinks to follow): {target_path}",
    )
    root = target_path.resolve()
    require_ok(root.exists(), "TARGET_NOT_FOUND", f"target path does not exist: {root}")
    root_mode = os.stat(root).st_mode
    require_ok(
        stat.S_ISREG(root_mode) or stat.S_ISDIR(root_mode),
        "TARGET_NOT_REGULAR",
        f"target is not a regular file or directory (FIFO, socket, or device?): {root}",
    )
    if stat.S_ISDIR(root_mode):
        try:
            with os.scandir(root):
                pass
        except OSError as exc:
            raise AletheiaError(
                "TARGET_UNREADABLE",
                f"cannot read target directory ({_err_detail(exc)}): {root}",
            ) from exc

    crlf_files: list[str] = []
    pycache_entries: list[Path] = []
    leak_findings: list[dict[str, Any]] = []
    syntax_errors: list[dict[str, Any]] = []
    bare_asserts: list[dict[str, Any]] = []
    unseeded_rng: list[dict[str, Any]] = []
    json_errors: list[dict[str, Any]] = []

    files_scanned = 0
    py_files_scanned = 0
    json_files_scanned = 0

    path_findings: list[dict[str, str]] = []
    symlinks: list[dict[str, str]] = []
    if root.is_file():
        walk_files = [root]
    else:
        walk_files, pycache_entries, path_findings, symlinks = _walk_classified(root)

    pycache_items = [
        str(p.relative_to(root))
        for p in _foreign_bytecode_items(pycache_entries, _loaded_module_bytecode())
    ]

    for p in walk_files:
        rel_str = p.name if root.is_file() else str(p.relative_to(root))
        try:
            raw = _read_regular_bytes(p)
        except AletheiaError as exc:
            path_findings.append({"file": rel_str, "code": exc.code, "detail": exc.message})
            continue
        except OSError as exc:
            path_findings.append({"file": rel_str, "code": "UNREADABLE_FILE", "detail": _err_detail(exc)})
            continue
        files_scanned += 1
        is_text = p.suffix.lower() in TEXT_SUFFIXES or p.name in {"LICENSE", "Makefile", "Dockerfile"}
        if not is_text:
            continue

        if b"\r\n" in raw:
            crlf_files.append(rel_str)

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            syntax_errors.append({"file": rel_str, "line": 0, "message": f"invalid UTF-8: {exc}"})
            continue

        for lk in scan_text_for_leaks(text):
            leak_findings.append({"file": rel_str, **lk})

        if p.suffix.lower() == ".py":
            py_files_scanned += 1
            se, ba, ur = _scan_python_ast(Path(rel_str), text)
            syntax_errors.extend(se)
            in_tests = "tests" in Path(rel_str).parts or p.name.startswith("test_")
            if not (allow_bare_assert_in_tests and in_tests):
                bare_asserts.extend(ba)
            unseeded_rng.extend(ur)
        elif p.suffix.lower() == ".json":
            json_files_scanned += 1
            try:
                load_strict_json_file(p, allow_float=True, require_object=False)
            except AletheiaError as exc:
                json_errors.append({"file": rel_str, "code": exc.code, "message": exc.message})
        elif p.suffix.lower() == ".jsonl":
            json_files_scanned += 1
            try:
                load_strict_jsonl_file(p, allow_float=True, require_object=False)
            except AletheiaError as exc:
                json_errors.append({"file": rel_str, "code": exc.code, "message": exc.message})

    # R4 3-mode script checks
    script_reports: list[dict[str, Any]] = []
    for sp in scripts:
        s_resolved = sp if sp.is_absolute() else (root / sp if root.is_dir() else sp.resolve())
        script_reports.append(
            run_r4_script_check(
                s_resolved,
                cwd=(root if root.is_dir() else root.parent),
                timeout=timeout,
                isolated=isolated,
            )
        )

    # Audit log validation (explicit or auto-discovered)
    audit_log_report: dict[str, Any] | None = None
    log_path = audit_log
    if log_path is None and root.is_dir():
        cand = root / "verification" / "AUDIT_LOG.md"
        if cand.is_file():
            log_path = cand
    outside_coverage: dict[str, list[dict[str, str]]] | None = None
    if outside_rulings is not None:
        require_ok(
            log_path is not None,
            "OUTSIDE_RULINGS_WITHOUT_AUDIT_LOG",
            "--outside-rulings needs a ledger: pass --audit-log or audit a directory with verification/AUDIT_LOG.md",
        )
        outside_coverage = load_outside_rulings(outside_rulings)
    require_ok(
        log_path is not None or not strict_novelty,
        "STRICT_NOVELTY_WITHOUT_AUDIT_LOG",
        "--strict-novelty needs a ledger: pass --audit-log or audit a directory with verification/AUDIT_LOG.md",
    )
    if log_path is not None:
        # An explicit --audit-log must hold rows. A freshly scaffolded workspace has an empty ledger, so the
        # auto-discovered one may still be empty.
        audit_log_report = validate_audit_log_markdown(
            log_path,
            require_rows=audit_log is not None,
            outside_rulings=outside_coverage,
            strict_novelty=strict_novelty,
        )

    # Optional JSON audit receipt validation
    receipt_report: dict[str, Any] | None = None
    if receipt is not None:
        receipt_report = validate_audit_receipt_json(receipt)

    # Optional v1.2 static Lean 4 audit
    lean_report: dict[str, Any] | None = None
    if lean_audit:
        lean_report = audit_lean4_directory(
            root, allow_project_imports=allow_project_imports
        )

    # Optional v1.2 Comparator JSON check (enable_nanoda + Spec -/-> Proof isolation)
    comparator_report: dict[str, Any] | None = None
    if comparator_config is not None:
        comparator_report = validate_comparator_config(
            comparator_config,
            lean_root=(root if root.is_dir() else root.parent),
            require_nanoda=require_nanoda,
        )

    # Optional v1.2 cryptographic manifest check (CORE_MANIFEST.json / SafeVerify SHA pins)
    manifest_report: dict[str, Any] | None = None
    if pinned_manifest is not None:
        manifest_report = validate_pinned_manifest(
            pinned_manifest,
            root=(root if root.is_dir() else root.parent),
        )

    # Optional v1.1 git-DAG preregistration check
    prereg_report: dict[str, Any] | None = None
    if prereg_check:
        prereg_report = verify_preregistration_git_dag(
            root if root.is_dir() else root.parent,
            plan_commit=plan_commit,
            data_commit=data_commit,
        )

    # Optional v1.4 canonical ancestor-directory permission gate (--strict-ancestors)
    ancestor_report: dict[str, Any] | None = None
    if strict_ancestors:
        ancestor_report = audit_ancestor_dir_permissions(root)

    # Optional v2.0 deterministic static agent-safety scanner (CYA-GAP-01..06, --safety-scan)
    safety_report: dict[str, Any] | None = None
    if safety_scan:
        safety_report = scan_directory_safety_surface(root, include_host_hygiene=include_host_hygiene)

    fatal_findings = [f for f in path_findings if not (allow_symlinks and f["code"] in _SYMLINK_CODES)]
    non_regular_count = sum(1 for f in path_findings if f["code"] == "NON_REGULAR_FILE")
    unreadable_count = sum(1 for f in path_findings if f["code"] == "UNREADABLE_FILE")

    failures: list[str] = []
    if fatal_findings:
        by_code: dict[str, int] = {}
        for f in fatal_findings:
            by_code[f["code"]] = by_code.get(f["code"], 0) + 1
        failures.append(
            f"path walk findings ({len(fatal_findings)}: "
            + ", ".join(f"{c}={n}" for c, n in sorted(by_code.items()))
            + ")"
        )
    if crlf_files:
        failures.append(f"CRLF line endings in {len(crlf_files)} file(s)")
    if pycache_items:
        failures.append(f"bytecode/pycache artifacts present ({len(pycache_items)})")
    if leak_findings:
        failures.append(f"personal path or credential leaks detected ({len(leak_findings)})")
    if syntax_errors:
        failures.append(f"Python/UTF-8 syntax errors ({len(syntax_errors)})")
    if bare_asserts:
        failures.append(f"bare assert statements on trust paths ({len(bare_asserts)})")
    if json_errors:
        failures.append(f"strict JSON validation errors ({len(json_errors)})")
    if strict_unseeded and unseeded_rng:
        failures.append(f"unseeded RNG calls ({len(unseeded_rng)})")
    if any(not sr["passed"] for sr in script_reports):
        failures.append("one or more scripts failed R4 3-mode parity")
    if audit_log_report is not None and not audit_log_report["valid"]:
        failures.append(f"AUDIT_LOG validation errors ({len(audit_log_report['errors'])})")
    if receipt_report is not None and not receipt_report["valid"]:
        failures.append(f"audit receipt validation errors ({len(receipt_report['errors'])})")
    if lean_report is not None and not lean_report["clean"]:
        failures.append(f"Lean 4 static audit findings ({len(lean_report['findings'])})")
    if comparator_report is not None and not comparator_report["passed"]:
        failures.append(f"Comparator config validation errors ({len(comparator_report['errors'])})")
    if manifest_report is not None and not manifest_report["passed"]:
        failures.append(f"pinned manifest verification errors ({len(manifest_report['errors'])})")
    if prereg_report is not None and not prereg_report["passed"]:
        failures.append(f"git-DAG preregistration check failed ({prereg_report['reason']})")
    if ancestor_report is not None and not ancestor_report["passed"]:
        failures.append(f"ancestor directory permission findings ({len(ancestor_report['findings'])})")
    if safety_report is not None and not safety_report["clean"]:
        failures.append(
            "agent safety-surface findings "
            f"({safety_report['finding_count']} findings, "
            f"{len(safety_report['skipped_files'])} skipped, "
            f"{len(safety_report['undecodable_files'])} undecodable, "
            f"{len(safety_report['unreadable_files'])} unreadable)"
        )

    passed = len(failures) == 0
    return {
        "passed": passed,
        "status": "PASS" if passed else "FAIL",
        "target": str(root),
        "summary": {
            "files_scanned": files_scanned,
            "py_files_scanned": py_files_scanned,
            "json_files_scanned": json_files_scanned,
            "crlf_count": len(crlf_files),
            "pycache_count": len(pycache_items),
            "leak_count": len(leak_findings),
            "syntax_error_count": len(syntax_errors),
            "bare_assert_count": len(bare_asserts),
            "unseeded_rng_warning_count": len(unseeded_rng),
            "json_error_count": len(json_errors),
            "r4_scripts_checked": len(script_reports),
            "r4_scripts_passed": sum(1 for sr in script_reports if sr["passed"]),
            "lean_files_checked": lean_report["files_checked"] if lean_report is not None else 0,
            "lean_findings_count": len(lean_report["findings"]) if lean_report is not None else 0,
            "lean_notices_count": len(lean_report["notices"]) if lean_report is not None else 0,
            "ancestor_permission_findings_count": len(ancestor_report["findings"]) if ancestor_report is not None else 0,
            "safety_findings_count": safety_report["finding_count"] if safety_report is not None else 0,
            "verified_n2_rows": audit_log_report["verified_n2_rows"] if audit_log_report is not None else 0,
            "verified_n2_without_outside_ruling": (
                audit_log_report["verified_n2_without_outside_ruling"] if audit_log_report is not None else 0
            ),
            "n2_novelty_not_shown": audit_log_report["n2_novelty_not_shown"] if audit_log_report is not None else 0,
            "outside_rulings_checked": outside_coverage is not None,
            "pinned_mismatch_stale_count": (
                sum(1 for m in manifest_report["mismatches"] if m["status"] == "STALE") if manifest_report is not None else 0
            ),
            "pinned_mismatch_unknown_count": (
                sum(1 for m in manifest_report["mismatches"] if m["status"] == "UNKNOWN") if manifest_report is not None else 0
            ),
            "path_findings_count": len(path_findings),
            "symlink_count": len(symlinks),
            "non_regular_count": non_regular_count,
            "unreadable_count": unreadable_count,
        },
        "failures": failures,
        "crlf_files": crlf_files,
        "pycache_items": pycache_items,
        "leak_findings": leak_findings,
        "syntax_errors": syntax_errors,
        "bare_asserts": bare_asserts,
        "unseeded_rng_warnings": unseeded_rng,
        "json_errors": json_errors,
        "r4_scripts": script_reports,
        "audit_log": audit_log_report,
        "audit_receipt": receipt_report,
        "lean_audit": lean_report,
        "comparator_config": comparator_report,
        "pinned_manifest": manifest_report,
        "prereg_check": prereg_report,
        "ancestor_permissions": ancestor_report,
        "safety_scan": safety_report,
        "path_findings": path_findings,
        "symlinks": symlinks,
        "allow_symlinks": allow_symlinks,
    }
