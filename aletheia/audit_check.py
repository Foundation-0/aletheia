"""
`aletheia audit-check <path>`: Automated R1-R5 & Gate 1-9 verification checker.

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
"""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any, Sequence

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
VALID_ORACLE_TOKENS = {"exact", "sampled", "anchor"}
VALID_NOVELTY_TOKENS = {"N0", "N1", "N2"}

_UNSEEDED_RANDOM_FUNCS = {
    "random", "randint", "randrange", "uniform", "gauss", "normalvariate",
    "choice", "choices", "sample", "shuffle",
}
_UNSEEDED_NP_RANDOM_FUNCS = {
    "rand", "randn", "randint", "random", "uniform", "normal", "choice", "permutation", "shuffle",
}

_AUDIT_ID_RE = re.compile(r"AUDIT-[0-9]+[A-Za-z0-9_-]*")
_PRIOR_ART_HINT_RE = re.compile(
    r"(?:prior[- ]?art|arxiv|literature|borcea|streinu|knausg|alp[oö]ge|loom#|docs/10|confirmed|beyond|over\s+`?loom|refut|reproduc|upstream|skordis|l'vov|viazovska)",
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

    # Track aliases for `import random as X` or `import numpy as Y`
    random_aliases = {"random"}
    numpy_aliases = {"np", "numpy"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "random" and alias.asname:
                    random_aliases.add(alias.asname)
                if alias.name == "numpy" and alias.asname:
                    numpy_aliases.add(alias.asname)

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
                    "hint": "Prefer explicit local random.Random(seed)",
                })
            # np.random.<fn>() (skip np.random.default_rng(seed)!)
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


def validate_audit_log_markdown(path: Path) -> dict[str, Any]:
    """Parse and validate a markdown AUDIT_LOG.md table under Gate 8 & Gate 9."""
    require_ok(path.is_file(), "AUDIT_LOG_NOT_FOUND", f"audit log not found: {path}")
    text = path.read_text(encoding="utf-8")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rows_checked = 0
    verdict_counts: dict[str, int] = {}
    novelty_counts: dict[str, int] = {}

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 8:
            continue
        first_cell = cells[0]
        if _AUDIT_ID_RE.search(first_cell) is None:
            continue
        rows_checked += 1
        audit_id = _AUDIT_ID_RE.search(first_cell).group(0)  # type: ignore[union-attr]

        # Standard 9-column table: ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence
        # Also tolerate 8-column variations by scanning from right for Verdict/Novelty/Oracle
        gates_cell = cells[4] if len(cells) >= 9 else ""
        oracle_cell = cells[5] if len(cells) >= 9 else cells[-4]
        novelty_cell = cells[6] if len(cells) >= 9 else cells[-3]
        verdict_cell = cells[7] if len(cells) >= 9 else cells[-2]
        evidence_cell = cells[8] if len(cells) >= 9 else cells[-1]

        # Extract primary verdict token deterministically (earliest match in cell, longest tie-break)
        matched_positions: list[tuple[int, int, str]] = []
        for v in sorted(VALID_VERDICTS):
            pos = verdict_cell.find(v)
            if pos >= 0:
                matched_positions.append((pos, -len(v), v))
        v_main: str | None = None
        if not matched_positions:
            errors.append({
                "line": lineno,
                "audit_id": audit_id,
                "code": "INVALID_VERDICT",
                "message": f"unrecognized verdict cell {verdict_cell!r}",
            })
        else:
            matched_positions.sort()
            v_main = matched_positions[0][2]
            verdict_counts[v_main] = verdict_counts.get(v_main, 0) + 1

        # Extract oracle class tokens
        o_lower = oracle_cell.lower()
        found_oracles = [tok for tok in sorted(VALID_ORACLE_TOKENS) if tok in o_lower]
        if not found_oracles:
            errors.append({
                "line": lineno,
                "audit_id": audit_id,
                "code": "INVALID_ORACLE_CLASS",
                "message": f"oracle class {oracle_cell!r} must mention exact/sampled/anchor",
            })

        # Extract novelty tokens
        found_nov = [n for n in sorted(VALID_NOVELTY_TOKENS) if n in novelty_cell]
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

        # Provenance inflation check: Lean compiled claim vs uncompiled_source
        row_lower = stripped.lower()
        if "uncompiled_source" in row_lower and "kernel-verified" in row_lower and "not kernel-verified" not in row_lower:
            errors.append({
                "line": lineno,
                "audit_id": audit_id,
                "code": "PROVENANCE_INFLATION",
                "message": "row mixes uncompiled_source with kernel-verified claim",
            })

    return {
        "path": str(path),
        "rows_checked": rows_checked,
        "verdict_counts": verdict_counts,
        "novelty_counts": novelty_counts,
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
    if not isinstance(aid, str) or _AUDIT_ID_RE.fullmatch(aid) is None:
        errors.append({"code": "INVALID_AUDIT_ID", "message": f"audit_id {aid!r} must match AUDIT-NNN..."})

    for req_s in ("target", "repro_command"):
        val = data.get(req_s)
        if not isinstance(val, str) or not val.strip():
            errors.append({"code": "MISSING_RECEIPT_FIELD", "message": f"missing non-empty {req_s!r}"})

    verdict = data.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append({"code": "INVALID_VERDICT", "message": f"verdict {verdict!r} not in {sorted(VALID_VERDICTS)}"})

    oc = data.get("oracle_class")
    if not isinstance(oc, str) or not oc.strip() or any(p.strip() not in VALID_ORACLE_TOKENS for p in oc.split("+")):
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
    (re.compile(r"\bLean\.ofReduceBool\b|\bofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\bLean\.trustCompiler\b|\btrustCompiler\b"), "LEAN4_TRUST_COMPILER"),
)

# Declaration-scoped `partial` across single or multiple lines (zero FP on dot-projections like `SmoothShell.partial`)
_LEAN4_PARTIAL_DECL_RE = re.compile(
    r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", flags=re.DOTALL
)

# Multiline skipKernelTC check (catches `set_option\n debug.skipKernelTC\n true` and bare `debug.skipKernelTC`)
_LEAN4_SKIP_KERNEL_TC_RE = re.compile(
    r"\bdebug\s*\.\s*skipKernelTC\b", flags=re.DOTALL
)

# Lean 4.22 module-aware import regex (supports single-line & multiline `public\n import Foo`)
_LEAN4_IMPORT_FULL_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)", flags=re.DOTALL
)

# Unsound attribute trust escapes vs kernel-proved `@[csimp]` compiler rewrite notice
_LEAN4_HARD_ATTR_RE = re.compile(
    r"@\[[^\]]*\b(extern|implemented_by)\b[^\]]*\]", flags=re.DOTALL
)
_LEAN4_CSIMP_ATTR_RE = re.compile(
    r"@\[[^\]]*\b(csimp)\b[^\]]*\]", flags=re.DOTALL
)

# Anti-vacuity notices (DeepMind formal-conjectures STATEMENTS.md & ExistsImplicationLinter)
_LEAN4_VACUOUS_THM_RE = re.compile(
    r"^\s*(?:private\s+|protected\s+)?(?:theorem|lemma)\s+[A-Za-z0-9_.']+\b[^:\n]*:\s*(?:False\s*(?:→|->)|True\s*:=)"
)
_LEAN4_EXISTS_IMP_RE = re.compile(r"∃[^,\n]+,\s*(?!.*(?:∀|∧))[^,\n]*(?:→|->)")


def _strip_lean4_comments_and_literals(source: str) -> str:
    """Char-literal-safe and nested-block-comment-safe Lean 4 stripper preserving line count."""
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
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
        if in_str:
            if ch == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
            elif ch == '"':
                in_str = False
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
        elif ch == "-" and nxt == "-":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == '"':
            in_str = True
            out.append(" ")
            i += 1
        elif ch == "'":
            # Lean 4 char literals ('"', '\n', 'a') without disturbing identifier primes x'
            if i + 2 < n and source[i + 1] != "\\" and source[i + 2] == "'":
                out.append("   ")
                i += 3
            elif i + 3 < n and source[i + 1] == "\\" and source[i + 3] == "'":
                out.append("    ")
                i += 4
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


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
    cleaned = _strip_lean4_comments_and_literals(source)
    findings: list[dict[str, Any]] = []
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
    for m_imp in _LEAN4_IMPORT_FULL_RE.finditer(cleaned):
        mod = m_imp.group(1)
        lineno = cleaned[: m_imp.start(1)].count("\n") + 1
        imports.append(mod)
        for pref in forbidden_import_prefixes:
            if mod == pref or mod.startswith(pref + "."):
                findings.append(
                    {"line": lineno, "code": "LEAN4_FORBIDDEN_CHALLENGE_IMPORT", "excerpt": mod}
                )
        if not allow_non_init_imports:
            root_pkg = mod.split(".")[0]
            is_allowed_proj = any(
                mod == p or mod.startswith(p + ".") for p in allow_project_imports
            )
            if root_pkg not in ("Init", "Std") and not is_allowed_proj:
                findings.append({"line": lineno, "code": "LEAN4_NON_INIT_IMPORT", "excerpt": mod})

    # Multiline declaration-scoped `partial` check (`partial\n def ...`, zero FP on `.partial`)
    for m_part in _LEAN4_PARTIAL_DECL_RE.finditer(cleaned):
        lineno = cleaned[: m_part.start()].count("\n") + 1
        findings.append({"line": lineno, "code": "LEAN4_PARTIAL", "excerpt": " ".join(m_part.group(0).split())[:100]})

    # Multiline debug.skipKernelTC check
    for m_sk in _LEAN4_SKIP_KERNEL_TC_RE.finditer(cleaned):
        lineno = cleaned[: m_sk.start()].count("\n") + 1
        findings.append({"line": lineno, "code": "LEAN4_SKIP_KERNEL_TC", "excerpt": "debug.skipKernelTC"})

    # Multiline attribute trust-escape check: @[ ... extern | implemented_by ... ]
    for m_attr in _LEAN4_HARD_ATTR_RE.finditer(cleaned):
        lineno = cleaned[: m_attr.start()].count("\n") + 1
        findings.append({"line": lineno, "code": "LEAN4_ATTR_TRUST_ESCAPE", "excerpt": m_attr.group(1)})

    # Kernel-proved @[csimp] rewrite notice
    for m_cs in _LEAN4_CSIMP_ATTR_RE.finditer(cleaned):
        lineno = cleaned[: m_cs.start()].count("\n") + 1
        notices.append({"line": lineno, "code": "LEAN4_CSIMP_REWRITE_NOTICE", "excerpt": m_cs.group(1)})

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
        if not any(part in SKIP_DIRS for part in p.relative_to(root).parts)
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


def validate_pinned_manifest(manifest_path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """
    Validate a cryptographic pinning manifest (`CORE_MANIFEST.json` SHA-256 spec pinning
    from DeepMind/cryptids OR `SafeVerify` 40-hex commit-SHA manifest from Mistral/FLTEval).
    """
    data = load_strict_json_file(manifest_path, allow_float=True, require_object=True)
    base_dir = (root if root is not None else manifest_path.parent).resolve()
    errors: list[str] = []
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
            mode_results[label] = {
                "returncode": proc.returncode,
                "stdout_sha256": h,
                "stdout_bytes": len(proc.stdout),
                "stderr_tail": proc.stderr.decode("utf-8", errors="replace")[-400:],
            }
        except subprocess.TimeoutExpired:
            all_zero = False
            mode_results[label] = {
                "returncode": -1,
                "stdout_sha256": "",
                "stdout_bytes": 0,
                "stderr_tail": f"TIMEOUT after {timeout}s",
            }

    bit_identical = all_zero and len(hashes) == 1
    return {
        "script": str(script_path),
        "isolated": isolated,
        "passed": all_zero and bit_identical,
        "all_exit_zero": all_zero,
        "stdout_bit_identical": bit_identical,
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
) -> dict[str, Any]:
    """Run complete Aletheia R1-R5 & Gate 1-9 audit check on `target_path`."""
    root = target_path.resolve()
    require_ok(root.exists(), "TARGET_NOT_FOUND", f"target path does not exist: {root}")

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

    if root.is_file():
        walk_files = [root]
    else:
        walk_files = []
        for p in sorted(root.rglob("*")):
            rel_parts = p.relative_to(root).parts
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            if "__pycache__" in rel_parts or p.suffix in (".pyc", ".pyo"):
                pycache_entries.append(p)
                continue
            if p.is_file():
                walk_files.append(p)

    pycache_items = [
        str(p.relative_to(root))
        for p in _foreign_bytecode_items(pycache_entries, _loaded_module_bytecode())
    ]

    for p in walk_files:
        files_scanned += 1
        rel_str = p.name if root.is_file() else str(p.relative_to(root))
        raw = p.read_bytes()
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
    if log_path is not None:
        audit_log_report = validate_audit_log_markdown(log_path)

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

    failures: list[str] = []
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
    }
