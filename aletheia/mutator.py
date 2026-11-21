"""
`aletheia mutate <script.py> --test-cmd "<cmd>"`: Generic AST-based R5 Refusal-Site Mutation Tester.

Discovers genuine refusal & boundary guards in `<script.py>`:
  1. `guard_if_reject`: `if <cond>: raise ...` or `sys.exit(...)` or `return False` -> mutates `<cond>` to `False`
  2. `guard_require_call`: `require*(cond, ...)` / `check(cond, ...)` -> mutates first arg `cond` to `True`
  3. `boundary_cmp`: single comparison operator (`<=`, `<`, `>=`, `>`, `==`, `!=`) inside guard tests
     -> flips boundary operator (`<=` <-> `<`, `>=` <-> `>`, `==` <-> `!=`)

Applies each single-site AST mutation in an isolated temporary copy of the target file/workspace,
verifies the unmutated baseline PASSES (exit 0), runs `--test-cmd` under `-I -O -B` parity, and
reports exact kill rate + any surviving mutants!
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from .strict_io import AletheiaError, require_ok

_REQUIRE_FUNC_NAMES = {"require", "require_ok", "require_cert", "check", "ensure"}

_CMP_FLIP: dict[type[ast.cmpop], type[ast.cmpop]] = {
    ast.LtE: ast.Lt,
    ast.Lt: ast.LtE,
    ast.GtE: ast.Gt,
    ast.Gt: ast.GtE,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}


@dataclass(frozen=True)
class MutantSite:
    mutant_id: str
    kind: str
    lineno: int
    col_offset: int
    node_index: int
    original_src: str
    mutated_src: str
    extra_cmp_idx: int = -1


_REFUSAL_STR_PREFIXES = ("REJECTED", "FAIL", "FALSIFIED", "INVALID", "EXPOSED", "DENIED")
_ACCUMULATOR_HINTS = ("finding", "error", "issue", "viol", "problem", "failure", "reason", "defect", "reject")


def _stmt_is_refusal(body: list[ast.stmt]) -> bool:
    """
    Return True if an `if` body immediately refuses or records a verification refusal:
      1. `raise ...` or `sys.exit(...)` / `exit(...)`
      2. `return False` or `return None`
      3. Dict-verdict rejection: `return {"admissible": False, ...}` or `"REJECTED_*"` / `"FAIL"` / `"INVALID"`
      4. Constructor-verdict rejection: `return Verdict(..., False)` / `return Verdict(ok=False)`
      5. Finding-accumulator refusal: `findings.append(...)`, `errors.append(...)`, `violations.append(...)`, etc.
    """
    if not body:
        return False
    first = body[0]
    if isinstance(first, ast.Raise):
        return True
    if isinstance(first, ast.Return):
        val = first.value
        if isinstance(val, ast.Constant) and (val.value is False or val.value is None):
            return True
        if isinstance(val, ast.Dict):
            for v_node in val.values:
                if isinstance(v_node, ast.Constant) and (
                    v_node.value is False
                    or (isinstance(v_node.value, str) and v_node.value.upper().startswith(_REFUSAL_STR_PREFIXES))
                ):
                    return True
        if isinstance(val, ast.Call):
            if any(isinstance(a, ast.Constant) and a.value is False for a in val.args):
                return True
            if any(isinstance(kw.value, ast.Constant) and kw.value.value is False for kw in val.keywords):
                return True
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Call):
        fn = first.value.func
        if isinstance(fn, ast.Attribute) and fn.attr == "exit" and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
            return True
        if isinstance(fn, ast.Name) and fn.id == "exit":
            return True
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr in ("append", "extend", "add")
            and isinstance(fn.value, ast.Name)
            and any(tok in fn.value.id.lower() for tok in _ACCUMULATOR_HINTS)
        ):
            return True
    return False


def _is_main_guard(node: ast.If) -> bool:
    """Skip `if __name__ == '__main__':` entrypoints."""
    t = node.test
    if isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) and t.left.id == "__name__":
        return True
    return False


def _unwrap_bool_call(expr: ast.expr) -> ast.expr:
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "bool"
        and len(expr.args) == 1
        and not expr.keywords
    ):
        return expr.args[0]
    return expr


def _is_param_name(expr: ast.expr, param_name: str) -> bool:
    return isinstance(expr, ast.Name) and expr.id == param_name


def _classify_wrapper_test(test: ast.expr, cond_param: str) -> str | None:
    """
    Classify the guard polarity of a single-refusal wrapper's `if <test>:` condition:
      - `"require"` when truthy `cond_param` passes (mutating arg0 -> True neutralizes guard):
          `if not cond:`, `if not bool(cond):`, `if cond is False:`, `if cond == False:`,
          `if cond is not True:`, `if cond != True:`
      - `"reject"` when truthy `cond_param` refuses (mutating arg0 -> False neutralizes guard):
          `if cond:`, `if bool(cond):`, `if cond is True:`, `if cond == True:`
    """
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        if _is_param_name(_unwrap_bool_call(test.operand), cond_param):
            return "require"
    if _is_param_name(_unwrap_bool_call(test), cond_param):
        return "reject"
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
        op = test.ops[0]
        left = _unwrap_bool_call(test.left)
        right = test.comparators[0]
        if _is_param_name(left, cond_param) and isinstance(right, ast.Constant):
            if isinstance(op, (ast.Is, ast.Eq)) and right.value is False:
                return "require"
            if isinstance(op, (ast.IsNot, ast.NotEq)) and right.value is True:
                return "require"
            if isinstance(op, (ast.Is, ast.Eq)) and right.value is True:
                return "reject"
    return None


def _stmt_is_hard_refusal(body: list[ast.stmt]) -> bool:
    """
    Return True ONLY when an `if` body immediately raises an exception or exits
    (`raise ...`, `sys.exit(...)`, or `exit(...)`). Excludes ordinary early-return
    utilities such as `if not x: return None`.
    """
    if not body:
        return False
    first = body[0]
    if isinstance(first, ast.Raise):
        return True
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Call):
        fn = first.value.func
        if isinstance(fn, ast.Attribute) and fn.attr == "exit" and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
            return True
        if isinstance(fn, ast.Name) and fn.id == "exit":
            return True
    return False


def discover_local_refusal_wrappers(tree: ast.Module) -> dict[str, str]:
    """
    AST pre-pass (v1.4, closes `PR1-B4` `_req` blind spot):
    Discover local single-refusal helper functions whose guard body raises or exits
    (e.g. `def _req(cond, ...): if not cond: raise ...` or `def _fail_if(bad, ...): if bad: raise ...`,
    with optional docstring and optional trailing `return`), returning `{func_name: "require" | "reject"}`.
    Ignores ordinary early-return utility helpers like `if not x: return None`.
    """
    wrappers: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        pos_params = list(node.args.posonlyargs) + list(node.args.args)
        if not pos_params:
            continue
        cond_param = pos_params[0].arg
        if cond_param in ("self", "cls"):
            if len(pos_params) < 2:
                continue
            cond_param = pos_params[1].arg

        stmts = list(node.body)
        if (
            stmts
            and isinstance(stmts[0], ast.Expr)
            and isinstance(stmts[0].value, ast.Constant)
            and isinstance(stmts[0].value.value, str)
        ):
            stmts = stmts[1:]
        if not stmts or len(stmts) > 2:
            continue
        first = stmts[0]
        if not isinstance(first, ast.If) or first.orelse or not _stmt_is_hard_refusal(first.body):
            continue
        if len(stmts) == 2 and not isinstance(stmts[1], ast.Return):
            continue

        polarity = _classify_wrapper_test(first.test, cond_param)
        if polarity is not None:
            wrappers[node.name] = polarity
    return wrappers


def discover_mutant_sites(source: str, *, include_boundaries: bool = True) -> tuple[ast.Module, list[MutantSite]]:
    """Parse Python source and deterministically discover all R5 refusal-site & boundary mutants."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise AletheiaError("MUTATOR_SYNTAX_ERROR", f"failed to parse target Python file: {exc}") from exc

    wrapper_polarities: dict[str, str] = {name: "require" for name in _REQUIRE_FUNC_NAMES}
    local_wrappers = discover_local_refusal_wrappers(tree)
    wrapper_polarities.update(local_wrappers)

    all_nodes = list(ast.walk(tree))
    sites: list[MutantSite] = []
    idx_counter = 0

    for node_idx, node in enumerate(all_nodes):
        # 1. `if <cond>: raise / sys.exit / return False`
        if isinstance(node, ast.If) and not _is_main_guard(node):
            if _stmt_is_refusal(node.body):
                orig_test = ast.unparse(node.test)
                if orig_test != "False":
                    idx_counter += 1
                    sites.append(MutantSite(
                        mutant_id=f"M{idx_counter:03d}",
                        kind="guard_if_reject",
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        node_index=node_idx,
                        original_src=f"if {orig_test}:",
                        mutated_src="if False:",
                    ))
                # Also mutate boundary comparisons inside refusal `if` tests
                if include_boundaries and isinstance(node.test, ast.Compare):
                    for op_i, op in enumerate(node.test.ops):
                        op_cls = type(op)
                        if op_cls in _CMP_FLIP:
                            alt_tree = copy.deepcopy(node.test)
                            alt_tree.ops[op_i] = _CMP_FLIP[op_cls]()
                            idx_counter += 1
                            sites.append(MutantSite(
                                mutant_id=f"M{idx_counter:03d}",
                                kind="boundary_cmp",
                                lineno=node.lineno,
                                col_offset=node.col_offset,
                                node_index=node_idx,
                                original_src=orig_test,
                                mutated_src=ast.unparse(alt_tree),
                                extra_cmp_idx=op_i,
                            ))

        # 2. `require*(cond, ...)` and auto-detected local refusal-wrapper calls
        elif isinstance(node, ast.Call):
            fn_name = None
            if isinstance(node.func, ast.Name):
                fn_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn_name = node.func.attr
            polarity = wrapper_polarities.get(fn_name) if fn_name is not None else None
            if polarity is not None and len(node.args) >= 1:
                arg0 = node.args[0]
                orig_arg = ast.unparse(arg0)
                neutral_literal = "True" if polarity == "require" else "False"
                mutant_kind = "guard_require_call" if polarity == "require" else "guard_reject_call"
                if orig_arg != neutral_literal:
                    idx_counter += 1
                    sites.append(MutantSite(
                        mutant_id=f"M{idx_counter:03d}",
                        kind=mutant_kind,
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        node_index=node_idx,
                        original_src=f"{fn_name}({orig_arg}, ...)",
                        mutated_src=f"{fn_name}({neutral_literal}, ...)",
                    ))
                    if include_boundaries and isinstance(arg0, ast.Compare):
                        for op_i, op in enumerate(arg0.ops):
                            op_cls = type(op)
                            if op_cls in _CMP_FLIP:
                                alt_cmp = copy.deepcopy(arg0)
                                alt_cmp.ops[op_i] = _CMP_FLIP[op_cls]()
                                idx_counter += 1
                                sites.append(MutantSite(
                                    mutant_id=f"M{idx_counter:03d}",
                                    kind="boundary_cmp_require",
                                    lineno=node.lineno,
                                    col_offset=node.col_offset,
                                    node_index=node_idx,
                                    original_src=orig_arg,
                                    mutated_src=ast.unparse(alt_cmp),
                                    extra_cmp_idx=op_i,
                                ))

    # Deterministic sort by (lineno, col_offset, kind, extra_cmp_idx) and renumber M001..
    sites.sort(key=lambda s: (s.lineno, s.col_offset, s.kind, s.extra_cmp_idx))
    numbered = [
        MutantSite(
            mutant_id=f"M{i:03d}",
            kind=s.kind,
            lineno=s.lineno,
            col_offset=s.col_offset,
            node_index=s.node_index,
            original_src=s.original_src,
            mutated_src=s.mutated_src,
            extra_cmp_idx=s.extra_cmp_idx,
        )
        for i, s in enumerate(sites, start=1)
    ]
    return tree, numbered


def apply_single_mutation(source: str, site: MutantSite) -> str:
    """Apply ONE deterministic AST mutation to `source` and return unparsed Python code."""
    tree = ast.parse(source)
    nodes = list(ast.walk(tree))
    require_ok(0 <= site.node_index < len(nodes), "MUTANT_INDEX_OOB", "mutant AST node index out of bounds")
    node = nodes[site.node_index]

    if site.kind == "guard_if_reject":
        require_ok(isinstance(node, ast.If), "MUTANT_NODE_TYPE", "expected ast.If")
        node.test = ast.Constant(value=False)  # type: ignore[union-attr]
    elif site.kind == "boundary_cmp":
        require_ok(isinstance(node, ast.If) and isinstance(node.test, ast.Compare), "MUTANT_NODE_TYPE", "expected ast.If/Compare")
        cmp_node = node.test  # type: ignore[union-attr]
        op_cls = type(cmp_node.ops[site.extra_cmp_idx])
        cmp_node.ops[site.extra_cmp_idx] = _CMP_FLIP[op_cls]()
    elif site.kind == "guard_require_call":
        require_ok(isinstance(node, ast.Call) and len(node.args) >= 1, "MUTANT_NODE_TYPE", "expected ast.Call")
        node.args[0] = ast.Constant(value=True)  # type: ignore[union-attr]
    elif site.kind == "guard_reject_call":
        require_ok(isinstance(node, ast.Call) and len(node.args) >= 1, "MUTANT_NODE_TYPE", "expected ast.Call")
        node.args[0] = ast.Constant(value=False)  # type: ignore[union-attr]
    elif site.kind == "boundary_cmp_require":
        require_ok(isinstance(node, ast.Call) and isinstance(node.args[0], ast.Compare), "MUTANT_NODE_TYPE", "expected Call/Compare")
        cmp_node = node.args[0]  # type: ignore[union-attr]
        op_cls = type(cmp_node.ops[site.extra_cmp_idx])
        cmp_node.ops[site.extra_cmp_idx] = _CMP_FLIP[op_cls]()
    else:
        raise AletheiaError("UNKNOWN_MUTANT_KIND", f"unknown mutant kind {site.kind!r}")

    ast.fix_missing_locations(tree)
    mutated = ast.unparse(tree) + "\n"
    compile(mutated, "<mutated>", "exec")
    return mutated


def _prepare_cmd(test_cmd: str, target_rel: str, *, add_cwd: bool = False) -> list[str]:
    """
    Parse `--test-cmd`, expanding `{target}` to `target_rel`, and normalizing bare
    `python` / `python3` invocations to `sys.executable -I -O -B` for strict R4 parity.
    When `add_cwd=True`, omits `-I` (keeping `-O -B` and `-s` no-user-site) so repo-local
    imports like `python3 -m unittest tests/...` resolve inside the isolated temp work_root.
    """
    expanded = test_cmd.replace("{target}", target_rel)
    parts = shlex.split(expanded)
    require_ok(len(parts) > 0, "EMPTY_TEST_CMD", "test_cmd cannot be empty")
    if parts[0] in ("python", "python3"):
        rest = parts[1:]
        flags: list[str] = []
        if add_cwd:
            # Strip -I if user omitted it; keep -s (no user site-packages), -O, -B so cwd stays on sys.path[0]
            if "-s" not in rest and "-I" not in rest:
                flags.append("-s")
        else:
            if "-I" not in rest:
                flags.append("-I")
        if "-O" not in rest:
            flags.append("-O")
        if "-B" not in rest:
            flags.append("-B")
        return [sys.executable, *flags, *rest]
    return parts


def run_mutation_suite(
    script_path: Path,
    test_cmd: str,
    *,
    work_root: Path | None = None,
    max_mutants: int = 100,
    timeout: int = 30,
    include_boundaries: bool = True,
    add_cwd: bool = False,
) -> dict[str, Any]:
    """
    Run AST refusal-site mutation testing against `script_path` in an isolated temporary workspace.
    Never modifies any file on disk outside the temporary directory!
    """
    target = script_path.resolve()
    require_ok(target.is_file(), "TARGET_SCRIPT_NOT_FOUND", f"script not found: {target}")
    source = target.read_text(encoding="utf-8")
    tree, sites = discover_mutant_sites(source, include_boundaries=include_boundaries)
    local_wrappers = sorted(discover_local_refusal_wrappers(tree).keys())
    if max_mutants > 0:
        sites = sites[:max_mutants]
    require_ok(len(sites) > 0, "NO_MUTANTS_DISCOVERED", f"no refusal/boundary guard sites found in {target}")

    src_root = (work_root or target.parent).resolve()
    require_ok(
        target == src_root or src_root in target.parents,
        "TARGET_OUTSIDE_WORKROOT",
        f"target {target} is not inside work_root {src_root}",
    )
    rel_target = target.relative_to(src_root)

    with tempfile.TemporaryDirectory(prefix="aletheia_mut_") as tmp_s:
        tmp_root = Path(tmp_s) / "work"
        shutil.copytree(
            src_root,
            tmp_root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv", "venv"),
        )
        tmp_target = tmp_root / rel_target
        cmd = _prepare_cmd(test_cmd, str(rel_target), add_cwd=add_cwd)

        # 1. Verify unmutated baseline passes!
        base_proc = subprocess.run(cmd, cwd=str(tmp_root), capture_output=True, timeout=timeout, check=False)
        if base_proc.returncode != 0:
            raise AletheiaError(
                "BASELINE_TEST_FAILED",
                f"unmutated baseline test failed (rc={base_proc.returncode}): "
                f"{base_proc.stderr.decode('utf-8', errors='replace')[-400:]}",
            )

        results: list[dict[str, Any]] = []
        killed = 0
        survivors: list[dict[str, Any]] = []

        for site in sites:
            mutated_code = apply_single_mutation(source, site)
            tmp_target.write_text(mutated_code, encoding="utf-8", newline="\n")
            try:
                proc = subprocess.run(cmd, cwd=str(tmp_root), capture_output=True, timeout=timeout, check=False)
                is_killed = proc.returncode != 0
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                is_killed = True
                rc = -9

            entry = {
                "id": site.mutant_id,
                "kind": site.kind,
                "line": site.lineno,
                "original": site.original_src,
                "mutated": site.mutated_src,
                "returncode": rc,
                "status": "KILLED" if is_killed else "SURVIVED",
            }
            results.append(entry)
            if is_killed:
                killed += 1
            else:
                survivors.append(entry)

            # Restore clean source immediately
            tmp_target.write_text(source, encoding="utf-8", newline="\n")

    total = len(sites)
    kill_rate = round(100.0 * killed / total, 2) if total > 0 else 0.0
    return {
        "passed": len(survivors) == 0,
        "target": str(target),
        "test_cmd": test_cmd,
        "local_wrappers_detected": local_wrappers,
        "total_mutants": total,
        "killed": killed,
        "survived": len(survivors),
        "kill_rate_pct": kill_rate,
        "survivors": survivors,
        "results": results,
    }
