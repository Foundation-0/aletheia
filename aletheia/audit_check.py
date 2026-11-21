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
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

from .strict_io import (
    AletheiaError,
    canonical_sha256_bytes,
    load_strict_json_file,
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
    "choice", "choices", "sample", "shuffle", "seed",
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


def run_audit_check(
    target_path: Path,
    *,
    scripts: Sequence[Path] = (),
    audit_log: Path | None = None,
    receipt: Path | None = None,
    strict_unseeded: bool = False,
    allow_bare_assert_in_tests: bool = False,
    isolated: bool = True,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run complete Aletheia R1-R5 & Gate 1-9 audit check on `target_path`."""
    root = target_path.resolve()
    require_ok(root.exists(), "TARGET_NOT_FOUND", f"target path does not exist: {root}")

    crlf_files: list[str] = []
    pycache_items: list[str] = []
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
                pycache_items.append(str(p.relative_to(root)))
                continue
            if p.is_file():
                walk_files.append(p)

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
    }
