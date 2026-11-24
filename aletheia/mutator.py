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
_VERDICT_DICT_KEYS = frozenset({"passed", "valid", "ok", "admissible", "clean", "verified", "status", "verdict"})


def _is_refusal_constant(node: ast.expr | None) -> bool:
    if not isinstance(node, ast.Constant):
        return False
    if node.value is False or node.value is None:
        return True
    if isinstance(node.value, str) and node.value.strip().upper().startswith(_REFUSAL_STR_PREFIXES):
        return True
    return False


def _expr_is_refusal(val: ast.expr | None) -> bool:
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
    return False


def _is_accumulator_name(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Name) and any(tok in expr.id.lower() for tok in _ACCUMULATOR_HINTS)


def _is_refusal_call_stmt(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        fn = stmt.value.func
        if isinstance(fn, ast.Attribute) and fn.attr == "exit" and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
            return True
        if isinstance(fn, ast.Name) and fn.id == "exit":
            return True
        if isinstance(fn, ast.Attribute) and fn.attr in ("append", "extend", "add") and _is_accumulator_name(fn.value):
            return True
    return False


def _is_verdict_subscript_refusal(target: ast.expr, value: ast.expr) -> bool:
    return (
        isinstance(target, ast.Subscript)
        and isinstance(target.slice, ast.Constant)
        and target.slice.value in _VERDICT_DICT_KEYS
        and _is_refusal_constant(value)
    )


def _expr_or_var_is_refusal(val: ast.expr | None, refusal_vars: set[str]) -> bool:
    if _expr_is_refusal(val):
        return True
    return isinstance(val, ast.Name) and val.id in refusal_vars


def _stmt_is_refusal(body: list[ast.stmt]) -> bool:
    """
    Return True if a statement block refuses or records a refusal:
    covers `raise`, `sys.exit`/`exit`, `return` of refusal constants/tuples/dicts/calls,
    assign-then-return refusal dicts/values (including aliases `r2 = r1; return r2`),
    plain and annotated dict-verdict refusal updates (`res["passed"] = False`,
    `res["passed"]: bool = False`), finding-accumulator calls and `+=` updates,
    `with`-wrapped refusals, and `try`-wrapped refusals (`try`/`except`/`else`/`finally`).
    """
    refusal_vars: set[str] = set()
    for stmt in body:
        if isinstance(stmt, ast.Raise) or _is_refusal_call_stmt(stmt):
            return True
        if isinstance(stmt, ast.Return):
            if _expr_or_var_is_refusal(stmt.value, refusal_vars):
                return True
        elif isinstance(stmt, ast.Assign):
            is_ref = _expr_or_var_is_refusal(stmt.value, refusal_vars)
            for tgt in stmt.targets:
                if _is_verdict_subscript_refusal(tgt, stmt.value):
                    return True
                if isinstance(tgt, ast.Name):
                    if is_ref:
                        refusal_vars.add(tgt.id)
                    else:
                        refusal_vars.discard(tgt.id)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            if _is_verdict_subscript_refusal(stmt.target, stmt.value):
                return True
            if isinstance(stmt.target, ast.Name):
                if _expr_or_var_is_refusal(stmt.value, refusal_vars):
                    refusal_vars.add(stmt.target.id)
                else:
                    refusal_vars.discard(stmt.target.id)
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.op, ast.Add) and _is_accumulator_name(stmt.target):
            return True
        elif isinstance(stmt, (ast.With, ast.AsyncWith)) and _stmt_is_refusal(stmt.body):
            return True
        elif isinstance(stmt, ast.Try):
            if (
                _stmt_is_refusal(stmt.body)
                or _stmt_is_refusal(stmt.orelse)
                or _stmt_is_refusal(stmt.finalbody)
                or any(_stmt_is_refusal(h.body) for h in stmt.handlers)
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
    """Return True when a statement block raises or calls sys.exit/exit (including try-wrapped)."""
    for stmt in body:
        if isinstance(stmt, ast.Raise):
            return True
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            fn = stmt.value.func
            if isinstance(fn, ast.Attribute) and fn.attr == "exit" and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
                return True
            if isinstance(fn, ast.Name) and fn.id == "exit":
                return True
        elif isinstance(stmt, ast.Try):
            if (
                _stmt_is_hard_refusal(stmt.body)
                or _stmt_is_hard_refusal(stmt.orelse)
                or _stmt_is_hard_refusal(stmt.finalbody)
                or any(_stmt_is_hard_refusal(h.body) for h in stmt.handlers)
            ):
                return True
    return False


_SCOPE_BOUNDARIES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _store_names(node: ast.AST) -> set[str]:
    """Return every variable name written (Store ctx) anywhere inside `node`."""
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store)}


def _is_wrapper_preamble_stmt(stmt: ast.stmt, cond_param: str) -> bool:
    """Return True for a side-effect/log or non-redefining preamble statement before a wrapper's guard."""
    if not isinstance(stmt, (ast.Expr, ast.Assign, ast.AnnAssign)):
        return False
    return cond_param not in _store_names(stmt)


def _extract_getattr_attr_name(expr: ast.expr | None) -> str | None:
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "getattr"
        and len(expr.args) >= 2
        and isinstance(expr.args[1], ast.Constant)
        and isinstance(expr.args[1].value, str)
    ):
        return expr.args[1].value
    return None


def _extract_call_guard_name(func_expr: ast.expr | None) -> str | None:
    if isinstance(func_expr, ast.Name):
        return func_expr.id
    if isinstance(func_expr, ast.Attribute):
        return func_expr.attr
    return _extract_getattr_attr_name(func_expr)


def _attr_root_name(expr: ast.expr) -> str | None:
    cur = expr
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    if isinstance(cur, ast.Name):
        return cur.id
    return None


def _extract_alias_rhs_name(expr: ast.expr | None, allowed_namespaces: set[str]) -> str | None:
    """Extract a guard target name from an alias RHS, restricting attribute/getattr roots to known namespaces."""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        if _attr_root_name(expr.value) in allowed_namespaces:
            return expr.attr
        return None
    ga_name = _extract_getattr_attr_name(expr)
    if ga_name is not None:
        if _attr_root_name(expr.args[0]) in allowed_namespaces:  # type: ignore[union-attr]
            return ga_name
    return None


def _walk_scope_nodes(stmts: Sequence[ast.stmt]) -> list[ast.AST]:
    """Return AST nodes in the current lexical scope without descending into nested defs/classes/lambdas."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(reversed(stmts))
    while stack:
        cur = stack.pop()
        out.append(cur)
        if isinstance(cur, _SCOPE_BOUNDARIES):
            continue
        children = list(ast.iter_child_nodes(cur))
        stack.extend(reversed(children))
    return out


def _collect_scope_namespaces(stmts: Sequence[ast.stmt]) -> set[str]:
    """Collect module/class namespace names imported or declared directly in this lexical scope."""
    ns: set[str] = set()
    for node in _walk_scope_nodes(stmts):
        if isinstance(node, ast.Import):
            for imp in node.names:
                ns.add(imp.asname or imp.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for imp in node.names:
                ns.add(imp.asname or imp.name)
        elif isinstance(node, ast.ClassDef):
            ns.add(node.name)
    return ns


def _extract_args_param_names(args: ast.arguments) -> set[str]:
    names = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    for extra in (args.vararg, args.kwarg):
        if extra is not None:
            names.add(extra.arg)
    return names


def _resolve_scope_guard_aliases(
    stmts: Sequence[ast.stmt],
    inherited_env: dict[str, str],
    allowed_namespaces: set[str],
    *,
    skip_def_names: set[str] | frozenset[str] = frozenset(),
) -> tuple[dict[str, str], set[str]]:
    """
    Resolve guard aliases within a single lexical scope.
    Any name reassigned to a non-guard, assigned conflicting polarities, or rebound by
    non-alias statements (`for`, `with`, `del`, `:=`, nested `def`, etc.) is invalidated.
    """
    import_bindings: dict[str, set[str]] = {}
    assign_edges: dict[str, list[str | None]] = {}
    poisoned: set[str] = set()

    for node in _walk_scope_nodes(stmts):
        if isinstance(node, ast.ImportFrom):
            for imp in node.names:
                if imp.asname:
                    if imp.name in inherited_env:
                        import_bindings.setdefault(imp.asname, set()).add(inherited_env[imp.name])
                    else:
                        poisoned.add(imp.asname)
                elif imp.name not in inherited_env:
                    poisoned.add(imp.name)
        elif isinstance(node, ast.Import):
            for imp in node.names:
                poisoned.add(imp.asname or imp.name.split(".")[0])
        elif isinstance(node, ast.Assign):
            rhs_name = _extract_alias_rhs_name(node.value, allowed_namespaces)
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    assign_edges.setdefault(tgt.id, []).append(rhs_name)
                else:
                    poisoned.update(_store_names(tgt))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            rhs_name = _extract_alias_rhs_name(node.value, allowed_namespaces)
            if isinstance(node.target, ast.Name):
                assign_edges.setdefault(node.target.id, []).append(rhs_name)
            else:
                poisoned.update(_store_names(node.target))
        elif isinstance(node, ast.AugAssign):
            poisoned.update(_store_names(node.target))
        elif isinstance(node, ast.NamedExpr):
            poisoned.add(node.target.id)
        elif isinstance(node, ast.Delete):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    poisoned.add(tgt.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            poisoned.update(_store_names(node.target))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    poisoned.update(_store_names(item.optional_vars))
        elif isinstance(node, ast.ExceptHandler):
            if node.name is not None:
                poisoned.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name not in skip_def_names:
                poisoned.add(node.name)

    locally_bound = set(assign_edges) | set(import_bindings) | poisoned
    known = {k: v for k, v in inherited_env.items() if k not in locally_bound}
    candidates = (set(assign_edges) | set(import_bindings)) - poisoned
    aliases: dict[str, str] = {}

    changed = True
    while changed:
        changed = False
        for lhs in sorted(candidates):
            if lhs in aliases:
                continue
            pols: set[str] = set(import_bindings.get(lhs, ()))
            all_resolved = True
            for rhs in assign_edges.get(lhs, ()):
                if rhs in known:
                    pols.add(known[rhs])
                else:
                    all_resolved = False
                    break
            if all_resolved and len(pols) == 1:
                pol = next(iter(pols))
                known[lhs] = pol
                aliases[lhs] = pol
                changed = True

    unresolved = locally_bound - set(aliases)
    return aliases, unresolved


def _discover_guard_aliases(tree: ast.Module, base_polarities: dict[str, str]) -> dict[str, str]:
    """Resolve module-level `from ... import g as alias` and safe variable aliases (`chk = require_ok`, `chk = mod.g`, `chk = getattr(mod, 'g')`)."""
    mod_ns = _collect_scope_namespaces(tree.body)
    aliases, _ = _resolve_scope_guard_aliases(
        tree.body,
        base_polarities,
        mod_ns,
        skip_def_names=set(base_polarities),
    )
    return aliases


def _build_call_scope_envs(
    tree: ast.Module,
    base_polarities: dict[str, str],
    explicit_guards: set[str] | frozenset[str] = frozenset(),
) -> tuple[dict[str, str], dict[int, dict[str, str]]]:
    """Build lexical-scope guard polarity environments for module scope and every `ast.Call` node."""
    mod_ns = _collect_scope_namespaces(tree.body)
    mod_aliases, mod_unresolved = _resolve_scope_guard_aliases(
        tree.body,
        base_polarities,
        mod_ns,
        skip_def_names=set(base_polarities),
    )
    mod_env = {k: v for k, v in base_polarities.items() if k not in mod_unresolved}
    mod_env.update(mod_aliases)
    call_envs: dict[int, dict[str, str]] = {}

    def _visit_expr(expr: ast.AST | None, env: dict[str, str]) -> None:
        if expr is None:
            return
        stack: list[ast.AST] = [expr]
        while stack:
            cur = stack.pop()
            if isinstance(cur, ast.Lambda):
                for d in (*cur.args.defaults, *cur.args.kw_defaults):
                    _visit_expr(d, env)
                l_shadowed = _extract_args_param_names(cur.args) - explicit_guards
                l_env = {k: v for k, v in env.items() if k not in l_shadowed}
                _visit_expr(cur.body, l_env)
                continue
            if isinstance(cur, ast.Call):
                call_envs[id(cur)] = env
            children = list(ast.iter_child_nodes(cur))
            stack.extend(reversed(children))

    def _visit_scope(
        stmts: Sequence[ast.stmt],
        expr_env: dict[str, str],
        enclosing_env: dict[str, str],
        ns: set[str],
    ) -> None:
        for node in _walk_scope_nodes(stmts):
            if isinstance(node, ast.Call):
                call_envs[id(node)] = expr_env
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                all_arg_nodes = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                for hdr in (
                    *node.decorator_list,
                    *node.args.defaults,
                    *node.args.kw_defaults,
                    node.returns,
                    *(a.annotation for a in all_arg_nodes),
                    *(a.annotation for a in (node.args.vararg, node.args.kwarg) if a is not None),
                ):
                    _visit_expr(hdr, expr_env)
                params = _extract_args_param_names(node.args)
                shadowed = params - explicit_guards
                fn_inherited = {k: v for k, v in enclosing_env.items() if k not in shadowed}
                fn_ns = (ns - params) | _collect_scope_namespaces(node.body)
                fn_aliases, fn_unresolved = _resolve_scope_guard_aliases(node.body, fn_inherited, fn_ns)
                fn_env = {k: v for k, v in fn_inherited.items() if k not in fn_unresolved}
                fn_env.update(fn_aliases)
                _visit_scope(node.body, fn_env, fn_env, fn_ns)
            elif isinstance(node, ast.ClassDef):
                for hdr in (*node.decorator_list, *node.bases, *(kw.value for kw in node.keywords)):
                    _visit_expr(hdr, expr_env)
                cls_ns = ns | _collect_scope_namespaces(node.body)
                cls_aliases, cls_unresolved = _resolve_scope_guard_aliases(node.body, enclosing_env, cls_ns)
                cls_body_env = {k: v for k, v in enclosing_env.items() if k not in cls_unresolved}
                cls_body_env.update(cls_aliases)
                _visit_scope(node.body, cls_body_env, enclosing_env, cls_ns)
            elif isinstance(node, ast.Lambda):
                _visit_expr(node, expr_env)

    _visit_scope(tree.body, mod_env, mod_env, mod_ns)
    return mod_env, call_envs


def _lookup_call_polarity(
    func_expr: ast.expr,
    scope_env: dict[str, str],
    attr_polarities: dict[str, str],
) -> tuple[str | None, str | None]:
    if isinstance(func_expr, ast.Name):
        return func_expr.id, scope_env.get(func_expr.id)
    attr_name = _extract_call_guard_name(func_expr)
    return attr_name, attr_polarities.get(attr_name)  # type: ignore[arg-type]


def _classify_wrapper_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    pos_params = list(node.args.posonlyargs) + list(node.args.args)
    if not pos_params:
        return None
    cond_param = pos_params[0].arg
    if cond_param in ("self", "cls"):
        if len(pos_params) < 2:
            return None
        cond_param = pos_params[1].arg

    stmts = list(node.body)
    idx = 0
    while idx < len(stmts) and _is_wrapper_preamble_stmt(stmts[idx], cond_param):
        idx += 1
    rem = stmts[idx:]
    if not rem or len(rem) > 2:
        return None
    first = rem[0]
    if not isinstance(first, ast.If):
        return None
    if len(rem) == 2 and not isinstance(rem[1], ast.Return):
        return None

    polarity = _classify_wrapper_test(first.test, cond_param)
    if polarity is None:
        return None
    if not first.orelse and _stmt_is_hard_refusal(first.body):
        return polarity
    if _stmt_is_hard_refusal(first.orelse) and not _stmt_is_hard_refusal(first.body):
        return "reject" if polarity == "require" else "require"
    return None


def discover_local_refusal_wrappers(tree: ast.Module) -> dict[str, str]:
    """
    AST pre-pass: discover single-refusal helper functions whose guard body raises or exits
    (scanning only module-level defs and direct class methods so nested defs never shadow
    or overwrite module-level functions), returning `{func_name: "require" | "reject"}`.
    """
    wrappers: dict[str, str] = {}
    top_level_defs: set[str] = set()
    class_defs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_level_defs.add(node.name)
            pol = _classify_wrapper_func(node)
            if pol is not None:
                wrappers[node.name] = pol
            else:
                wrappers.pop(node.name, None)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_defs.append(item)

    class_pols: dict[str, set[str]] = {}
    for method in class_defs:
        if method.name in top_level_defs:
            continue
        pol = _classify_wrapper_func(method)
        if pol is not None:
            class_pols.setdefault(method.name, set()).add(pol)
    for name, pols in class_pols.items():
        if len(pols) == 1:
            wrappers[name] = next(iter(pols))
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

    base_polarities: dict[str, str] = {name: "require" for name in _REQUIRE_FUNC_NAMES}
    imported_wrappers = discover_imported_refusal_wrappers(tree, target_path=target_path, work_root=work_root)
    base_polarities.update(imported_wrappers)
    local_wrappers = discover_local_refusal_wrappers(tree)
    base_polarities.update(local_wrappers)
    parsed_extra_guards = _parse_extra_guards(extra_guards)
    base_polarities.update(parsed_extra_guards)
    mod_env, call_envs = _build_call_scope_envs(tree, base_polarities, set(parsed_extra_guards))

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
                _, pol = _lookup_call_polarity(stmt.value.func, mod_env, base_polarities)
                if pol is not None and len(stmt.value.args) >= 1:
                    has_top_level_guard_calls = True
                    break

    all_nodes = list(ast.walk(tree))
    sites: list[MutantSite] = []
    idx_counter = 0

    for node_idx, node in enumerate(all_nodes):
        # 1. `if <cond>:` and `else:` refusal branches
        if isinstance(node, ast.If) and not _is_main_guard(node):
            if self_check_mode and has_top_level_guard_calls and id(node) in top_level_ifs:
                # Top-level summary `if FAILS: sys.exit(1)` is verified via `guard_selfcheck_negate`
                # (`check(False, ...)`), avoiding equivalent `if False:` on empty passing-run FAILS.
                continue
            body_refuses = _stmt_is_refusal(node.body)
            else_refuses = _stmt_is_refusal(node.orelse)
            if body_refuses or else_refuses:
                orig_test = ast.unparse(node.test)
                if body_refuses and orig_test != "False":
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
                if else_refuses and orig_test != "True":
                    idx_counter += 1
                    sites.append(MutantSite(
                        mutant_id=f"M{idx_counter:03d}",
                        kind="guard_else_reject",
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        node_index=node_idx,
                        original_src=f"if {orig_test}: ... else:",
                        mutated_src="if True:",
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

        # 1b. `except ...:` refusal handlers (try-wrapped raises / returns)
        elif isinstance(node, ast.ExceptHandler):
            if _stmt_is_refusal(node.body):
                exc_label = ast.unparse(node.type) if node.type is not None else ""
                hdr = f"except {exc_label}:" if exc_label else "except:"
                idx_counter += 1
                sites.append(MutantSite(
                    mutant_id=f"M{idx_counter:03d}",
                    kind="guard_except_reject",
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    node_index=node_idx,
                    original_src=hdr,
                    mutated_src=f"{hdr} pass",
                ))

        # 2. `require*(cond, ...)`, local/imported/aliased wrappers, `getattr` dispatch, and `--guards`
        elif isinstance(node, ast.Call):
            scope_env = call_envs.get(id(node), mod_env)
            fn_name, polarity = _lookup_call_polarity(node.func, scope_env, base_polarities)
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
    elif site.kind == "guard_else_reject":
        require_ok(isinstance(node, ast.If), "MUTANT_NODE_TYPE", "expected ast.If")
        node.test = ast.Constant(value=True)  # type: ignore[union-attr]
    elif site.kind == "guard_except_reject":
        require_ok(isinstance(node, ast.ExceptHandler), "MUTANT_NODE_TYPE", "expected ast.ExceptHandler")
        node.body = [ast.Pass()]  # type: ignore[union-attr]
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
