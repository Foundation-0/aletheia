"""
`aletheia mutate <script.py> --test-cmd "<cmd>"`: Generic AST-based R5 Refusal-Site Mutation Tester.

v2.0 upgrades (closing aletheia#5 #1, #6, #7, #11, #12 and aletheia#3 §4):
  1. `guard_if_reject`: `if <cond>:` containing `raise`, `sys.exit`, `return False/None`,
     refusal string (`"REJECTED"`, `"against"`, `"inconclusive"`, `"FAIL"`, ...),
     refusal tuple (`(False, ...)` / `("REJECTED", ...)`), dict-verdict rejection,
     constructor rejection, or finding-accumulator refusal (anywhere in the branch body!).
  2. `guard_require_call` / `guard_reject_call`: built-in guards, AST-discovered local wrappers,
     AST-discovered cross-module imported wrappers (from local repo modules), AND explicit `--guards`.
  3. `boundary_cmp` / `boundary_cmp_require`: boundary operator flips (`<=` <-> `<`, `>=` <-> `>`, `==` <-> `!=`).
  4. Self-check script support (`selfcheck.py`, aletheia#5 #12): when a script invokes itself as `--test-cmd`
     with module-level `check(cond, ...)` calls, replaces equivalent `check(True)` mutations with
     `guard_selfcheck_negate` (`check(False, ...)`) and `boundary_const_require` (`== 10` -> `== 11`).
  5. `aletheia#3` §4 sampled-integrity rule: truncating discovered sites via `--max-mutants`
     yields verdict `"NOT_SHOWN"` (`passed=False`) rather than `"PASS"`.
  6. Structured `BASELINE_TEST_TIMEOUT` on timeout (zero unhandled traceback) and explicit `-I`/`--add-cwd`
     hint on `ModuleNotFoundError`/`ImportError` during baseline execution.
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
from typing import Any, Sequence

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


_REFUSAL_STR_PREFIXES = (
    "REJECTED",
    "FAIL",
    "FALSIFIED",
    "INVALID",
    "EXPOSED",
    "DENIED",
    "REFUSED",
    "AGAINST",
    "INCONCLUSIVE",
    "NOT_SHOWN",
    "UNVERIFIED",
    "ERROR",
)
_ACCUMULATOR_HINTS = ("finding", "error", "issue", "viol", "problem", "failure", "reason", "defect", "reject")


def _is_refusal_constant(node: ast.expr | None) -> bool:
    if not isinstance(node, ast.Constant):
        return False
    if node.value is False or node.value is None:
        return True
    if isinstance(node.value, str) and node.value.strip().upper().startswith(_REFUSAL_STR_PREFIXES):
        return True
    return False


def _single_stmt_is_refusal(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Raise):
        return True
    if isinstance(stmt, ast.Return):
        val = stmt.value
        if _is_refusal_constant(val):
            return True
        if isinstance(val, ast.Tuple) and len(val.elts) >= 1 and _is_refusal_constant(val.elts[0]):
            return True
        if isinstance(val, ast.Dict):
            for v_node in val.values:
                if _is_refusal_constant(v_node):
                    return True
        if isinstance(val, ast.Call):
            if any(isinstance(a, ast.Constant) and a.value is False for a in val.args):
                return True
            if any(isinstance(kw.value, ast.Constant) and kw.value.value is False for kw in val.keywords):
                return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        fn = stmt.value.func
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


def _stmt_is_refusal(body: list[ast.stmt]) -> bool:
    """
    Return True if any top-level statement in an `if` branch refuses or records a refusal
    (covers `raise`, `sys.exit`, `return False/None`, refusal string/tuple/dict/constructor,
    finding-accumulator calls, AND multi-statement branches like `print("bad"); raise ValueError(x)`).
    """
    return any(_single_stmt_is_refusal(stmt) for stmt in body)


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
    """Classify guard polarity of a single-refusal wrapper (`require` vs `reject`)."""
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
    """Return True when an `if` branch raises or calls sys.exit/exit (ignoring ordinary return None)."""
    for stmt in body:
        if isinstance(stmt, ast.Raise):
            return True
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            fn = stmt.value.func
            if isinstance(fn, ast.Attribute) and fn.attr == "exit" and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
                return True
            if isinstance(fn, ast.Name) and fn.id == "exit":
                return True
    return False


def discover_local_refusal_wrappers(tree: ast.Module) -> dict[str, str]:
    """
    AST pre-pass: discover single-refusal helper functions whose guard body raises or exits
    (e.g. `def _req(cond, ...): if not cond: raise ...` or `def _fail_if(bad, ...): if bad: raise ...`),
    returning `{func_name: "require" | "reject"}`.
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


def _resolve_local_module_file(module_name: str, search_roots: Sequence[Path], level: int, target_parent: Path) -> Path | None:
    """Resolve a repo-local Python module path safely without importing or executing it."""
    rel_parts = module_name.split(".") if module_name else []
    candidates: list[Path] = []
    if level > 0:
        base = target_parent
        for _ in range(level - 1):
            base = base.parent
        candidates.append(base)
    else:
        candidates.extend(search_roots)

    for base in candidates:
        if rel_parts:
            mod_py = base.joinpath(*rel_parts).with_suffix(".py")
            if mod_py.is_file():
                return mod_py
            pkg_init = base.joinpath(*rel_parts, "__init__.py")
            if pkg_init.is_file():
                return pkg_init
        else:
            pkg_init = base / "__init__.py"
            if pkg_init.is_file():
                return pkg_init
    return None


def discover_imported_refusal_wrappers(
    tree: ast.Module,
    *,
    target_path: Path | None = None,
    work_root: Path | None = None,
) -> dict[str, str]:
    """
    v2.0 cross-module AST pre-pass (closes aletheia#5 #1 for imported wrappers like `from helpers import need`):
    Inspects repo-local `from mod import fn` and `import mod` statements via static AST parsing (zero code execution).
    """
    if target_path is None:
        return {}
    search_roots = [target_path.parent]
    if work_root is not None and work_root.resolve() != target_path.parent.resolve():
        search_roots.append(work_root.resolve())

    discovered: dict[str, str] = {}
    parsed_cache: dict[Path, dict[str, str]] = {}

    def _wrappers_in(mod_file: Path) -> dict[str, str]:
        if mod_file not in parsed_cache:
            try:
                mod_tree = ast.parse(mod_file.read_text(encoding="utf-8", errors="replace"))
                parsed_cache[mod_file] = discover_local_refusal_wrappers(mod_tree)
            except (OSError, SyntaxError):
                parsed_cache[mod_file] = {}
        return parsed_cache[mod_file]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod_file = _resolve_local_module_file(node.module or "", search_roots, node.level, target_path.parent)
            if mod_file is None:
                continue
            mod_wrappers = _wrappers_in(mod_file)
            for alias in node.names:
                if alias.name == "*":
                    discovered.update(mod_wrappers)
                elif alias.name in mod_wrappers:
                    local_name = alias.asname or alias.name
                    discovered[local_name] = mod_wrappers[alias.name]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod_file = _resolve_local_module_file(alias.name, search_roots, 0, target_path.parent)
                if mod_file is None:
                    continue
                mod_wrappers = _wrappers_in(mod_file)
                for fn_name, pol in mod_wrappers.items():
                    discovered.setdefault(fn_name, pol)
    return discovered


def _parse_extra_guards(extra_guards: Sequence[str]) -> dict[str, str]:
    """Parse CLI `--guards` entries (`name`, `name:require`, `name:reject`, or comma-separated)."""
    parsed: dict[str, str] = {}
    for item in extra_guards:
        for raw_tok in item.split(","):
            tok = raw_tok.strip()
            if not tok:
                continue
            if ":" in tok:
                name, pol = tok.split(":", 1)
                name = name.strip()
                pol = pol.strip().lower()
                require_ok(bool(name) and pol in ("require", "reject"), "INVALID_GUARD_SPEC", f"invalid --guards spec {tok!r}")
                parsed[name] = pol
            else:
                parsed[tok] = "require"
    return parsed


def _is_self_check_invocation(target: Path, test_cmd: str) -> bool:
    """Detect self-checking scripts run directly via `--test-cmd 'python3 selfcheck.py'` (aletheia#5 #12)."""
    try:
        parts = shlex.split(test_cmd.replace("{target}", target.name))
    except ValueError:
        return False
    if not parts:
        return False
    return any(Path(tok).name == target.name for tok in parts[1:])


def discover_mutant_sites(
    source: str,
    *,
    include_boundaries: bool = True,
    extra_guards: Sequence[str] = (),
    target_path: Path | None = None,
    work_root: Path | None = None,
    self_check_mode: bool = False,
) -> tuple[ast.Module, list[MutantSite]]:
    """Parse Python source and deterministically discover all R5 refusal-site & boundary mutants."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise AletheiaError("MUTATOR_SYNTAX_ERROR", f"failed to parse target Python file: {exc}") from exc

    wrapper_polarities: dict[str, str] = {name: "require" for name in _REQUIRE_FUNC_NAMES}
    imported_wrappers = discover_imported_refusal_wrappers(tree, target_path=target_path, work_root=work_root)
    wrapper_polarities.update(imported_wrappers)
    local_wrappers = discover_local_refusal_wrappers(tree)
    wrapper_polarities.update(local_wrappers)
    wrapper_polarities.update(_parse_extra_guards(extra_guards))

    # Identify top-level Expr(Call) nodes for self-check mode (aletheia#5 #12)
    top_level_calls: set[int] = set()
    top_level_ifs: set[int] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            top_level_calls.add(id(stmt.value))
        elif isinstance(stmt, ast.If) and not _is_main_guard(stmt):
            top_level_ifs.add(id(stmt))

    has_top_level_guard_calls = False
    if self_check_mode:
        for stmt in tree.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                fn = stmt.value.func
                fname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
                if fname in wrapper_polarities and len(stmt.value.args) >= 1:
                    has_top_level_guard_calls = True
                    break

    all_nodes = list(ast.walk(tree))
    sites: list[MutantSite] = []
    idx_counter = 0

    for node_idx, node in enumerate(all_nodes):
        # 1. `if <cond>:` refusal branches
        if isinstance(node, ast.If) and not _is_main_guard(node):
            if self_check_mode and has_top_level_guard_calls and id(node) in top_level_ifs:
                # Top-level summary `if FAILS: sys.exit(1)` is verified via `guard_selfcheck_negate`
                # (`check(False, ...)`), avoiding equivalent `if False:` on empty passing-run FAILS.
                continue
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

        # 2. `require*(cond, ...)`, local wrappers, imported wrappers, and `--guards`
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
                is_selfcheck_call = self_check_mode and has_top_level_guard_calls and id(node) in top_level_calls

                if is_selfcheck_call:
                    # Self-check call: negate to False (proves check + exit gate fire!) and perturb constant
                    if orig_arg != "False":
                        idx_counter += 1
                        sites.append(MutantSite(
                            mutant_id=f"M{idx_counter:03d}",
                            kind="guard_selfcheck_negate",
                            lineno=node.lineno,
                            col_offset=node.col_offset,
                            node_index=node_idx,
                            original_src=f"{fn_name}({orig_arg}, ...)",
                            mutated_src=f"{fn_name}(False, ...)",
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
                        for c_i, comp in enumerate(arg0.comparators):
                            if isinstance(comp, ast.Constant) and type(comp.value) is int:
                                alt_val = copy.deepcopy(arg0)
                                alt_val.comparators[c_i] = ast.Constant(value=comp.value + 1)
                                idx_counter += 1
                                sites.append(MutantSite(
                                    mutant_id=f"M{idx_counter:03d}",
                                    kind="boundary_const_require",
                                    lineno=node.lineno,
                                    col_offset=node.col_offset,
                                    node_index=node_idx,
                                    original_src=orig_arg,
                                    mutated_src=ast.unparse(alt_val),
                                    extra_cmp_idx=c_i,
                                ))
                    continue

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
    elif site.kind in ("guard_reject_call", "guard_selfcheck_negate"):
        require_ok(isinstance(node, ast.Call) and len(node.args) >= 1, "MUTANT_NODE_TYPE", "expected ast.Call")
        node.args[0] = ast.Constant(value=False)  # type: ignore[union-attr]
    elif site.kind == "boundary_cmp_require":
        require_ok(isinstance(node, ast.Call) and isinstance(node.args[0], ast.Compare), "MUTANT_NODE_TYPE", "expected Call/Compare")
        cmp_node = node.args[0]  # type: ignore[union-attr]
        op_cls = type(cmp_node.ops[site.extra_cmp_idx])
        cmp_node.ops[site.extra_cmp_idx] = _CMP_FLIP[op_cls]()
    elif site.kind == "boundary_const_require":
        require_ok(isinstance(node, ast.Call) and isinstance(node.args[0], ast.Compare), "MUTANT_NODE_TYPE", "expected Call/Compare")
        cmp_node = node.args[0]  # type: ignore[union-attr]
        comp = cmp_node.comparators[site.extra_cmp_idx]
        require_ok(isinstance(comp, ast.Constant) and type(comp.value) is int, "MUTANT_NODE_TYPE", "expected int constant")
        cmp_node.comparators[site.extra_cmp_idx] = ast.Constant(value=comp.value + 1)
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
    When `add_cwd=True`, omits `-I` (keeping `-s -O -B`) so repo-local imports resolve.
    """
    expanded = test_cmd.replace("{target}", target_rel)
    parts = shlex.split(expanded)
    require_ok(len(parts) > 0, "EMPTY_TEST_CMD", "test_cmd cannot be empty")
    if parts[0] in ("python", "python3"):
        rest = parts[1:]
        flags: list[str] = []
        if add_cwd:
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
    extra_guards: Sequence[str] = (),
) -> dict[str, Any]:
    """
    Run AST refusal-site mutation testing against `script_path` in an isolated temporary workspace.
    Never modifies any file on disk outside the temporary directory!
    """
    target = script_path.resolve()
    require_ok(target.is_file(), "TARGET_SCRIPT_NOT_FOUND", f"script not found: {target}")
    src_root = (work_root or target.parent).resolve()
    require_ok(
        target == src_root or src_root in target.parents,
        "TARGET_OUTSIDE_WORKROOT",
        f"target {target} is not inside work_root {src_root}",
    )

    source = target.read_text(encoding="utf-8")
    self_check_mode = _is_self_check_invocation(target, test_cmd)
    tree, sites = discover_mutant_sites(
        source,
        include_boundaries=include_boundaries,
        extra_guards=extra_guards,
        target_path=target,
        work_root=src_root,
        self_check_mode=self_check_mode,
    )
    local_wrappers = sorted(discover_local_refusal_wrappers(tree).keys())
    imported_wrappers = sorted(discover_imported_refusal_wrappers(tree, target_path=target, work_root=src_root).keys())
    explicit_guards = sorted(_parse_extra_guards(extra_guards).keys())
    discovered = len(sites)
    if max_mutants > 0:
        sites = sites[:max_mutants]
    require_ok(len(sites) > 0, "NO_MUTANTS_DISCOVERED", f"no refusal/boundary guard sites found in {target}")

    covered_lines = sorted({s.lineno for s in sites})
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

        # 1. Verify unmutated baseline passes (catch TimeoutExpired cleanly -> aletheia#5 #7)
        try:
            base_proc = subprocess.run(cmd, cwd=str(tmp_root), capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise AletheiaError(
                "BASELINE_TEST_TIMEOUT",
                f"unmutated baseline test timed out after {timeout}s (increase --timeout or inspect test command)",
            ) from exc

        if base_proc.returncode != 0:
            stderr_tail = base_proc.stderr.decode("utf-8", errors="replace")[-400:]
            hint = ""
            if not add_cwd and ("ModuleNotFoundError" in stderr_tail or "ImportError" in stderr_tail):
                hint = " (hint: python3 ran under -I isolated mode, which omits cwd from sys.path; retry with --add-cwd)"
            raise AletheiaError(
                "BASELINE_TEST_FAILED",
                f"unmutated baseline test failed (rc={base_proc.returncode}): {stderr_tail}{hint}",
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

            tmp_target.write_text(source, encoding="utf-8", newline="\n")

    total = len(sites)
    kill_rate = round(100.0 * killed / total, 2) if total > 0 else 0.0
    truncated = total < discovered
    # aletheia#3 §4: sampled/truncated gate-integrity with 0 hits is NOT_SHOWN, never PASS!
    if len(survivors) > 0:
        verdict = "FAIL"
        passed = False
    elif truncated:
        verdict = "NOT_SHOWN"
        passed = False
    else:
        verdict = "PASS"
        passed = True

    payload: dict[str, Any] = {
        "verdict": verdict,
        "passed": passed,
        "target": str(target),
        "test_cmd": test_cmd,
        "self_check_mode": self_check_mode,
        "local_wrappers_detected": local_wrappers,
        "imported_wrappers_detected": imported_wrappers,
        "explicit_guards": explicit_guards,
        "covered_lines": covered_lines,
        "mutants_discovered": discovered,
        "truncated": truncated,
        "total_mutants": total,
        "killed": killed,
        "survived": len(survivors),
        "kill_rate_pct": kill_rate,
        "survivors": survivors,
        "results": results,
    }
    if truncated:
        payload["warning"] = (
            f"max_mutants={max_mutants} cut {discovered - total} of {discovered} discovered sites; "
            "verdict is NOT_SHOWN (use --max-mutants 0 to test all sites)"
        )
    return payload
