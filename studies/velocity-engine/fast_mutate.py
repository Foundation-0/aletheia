"""
`fast_mutate.py`: Track S168 (EXP-Q56a) Exact Zero-Loss Accelerated Mutation Engine.

Exact-parity AST refusal-site & boundary mutator matching `aletheia mutate`'s
mutant universe across all bare/module/alias/`self`/`cls` guards (including lexical-scope
guard aliases, `getattr` dispatch, and self-check mode; intentionally skipping unrelated
non-namespace instance `.check(...)` methods unless locally/imported-discovered or passed
via `--guards`, while achieving 100.0% site parity across all 5 S168 scripts `547/547`
and S166 `61/61`), while adding three mathematically exact accelerations:
  (a) AST-verified & null-mutant-validated `--failfast` (`-f`) unittest flag injection
      (100% lossless: any first failing test already proves `returncode != 0`),
  (b) Context-bound lossless Pass-2 `--guards` deduplication skipping exact
      `(lineno, col_offset, kind, original_src, mutated_src)` + mutated-SHA-256 +
      `(work_root_tree_hash, test_cmd)` sites already KILLED in Pass 1 (`K_1 U K_2 = K_1 U (K_2 \\ K_1)`),
  (c) Optional `--changed-only` / `--changed-lines` / `--no-boundaries` narrowing strictly marked
      `PARTIAL_SCOPE_NOT_FINAL` (`final_signoff_eligible=False`, `passed=False`).

Stages read-only source trees into private `0o700` writable slots preserving exact `mtime`
and executable bits, isolates per-slot `TMPDIR`/`HOME`, strips `PYTHONPATH`, always executes
baseline + null-mutant controls, and classifies mutant timeouts as `TIMEOUT` (failure).

Stdlib-only, zero bare asserts, zero floats on trust paths, 3x -I bit-identical.
"""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from dataclasses import dataclass
from fractions import Fraction
import json
import os
from pathlib import Path
import queue
import re
import secrets
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Sequence

_SELF_DIR = str(Path(__file__).resolve().parent)
if _SELF_DIR not in sys.path:
    sys.path.insert(0, _SELF_DIR)

from trust_core import (  # noqa: E402
    TrustCoreError,
    make_strict_parser,
    require_tc,
    run_fail_closed_cli,
    sha256_bytes,
    strict_read_bytes_nofollow,
)

__all__ = [
    "MAX_LINE_RANGE_SPAN",
    "MutantSite",
    "mutant_signature",
    "discover_mutant_sites",
    "apply_single_mutation",
    "null_mutant_source",
    "inject_unittest_failfast",
    "parse_unified_diff_added_lines",
    "parse_line_ranges",
    "run_fast_mutation_pass",
    "run_dual_fast_mutation",
    "build_parser",
    "main",
]

_MAX_WORKERS = 32
MAX_LINE_RANGE_SPAN = 100_000
_COPY_IGNORE = frozenset({".git", "__pycache__", ".venv", "venv", ".lake"})
_REQUIRE_NAMES = frozenset({"require", "require_ok", "require_cert", "check", "ensure"})
_CMP_FLIP: dict[type[ast.cmpop], type[ast.cmpop]] = {
    ast.LtE: ast.Lt,
    ast.Lt: ast.LtE,
    ast.GtE: ast.Gt,
    ast.Gt: ast.GtE,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}
_REFUSAL_PREFIXES = (
    "REJECTED", "FAIL", "FALSIFIED", "INVALID", "EXPOSED", "DENIED",
    "REFUSED", "AGAINST", "INCONCLUSIVE", "NOT_SHOWN", "UNVERIFIED", "ERROR",
)
_ACCUMULATOR_HINTS = ("finding", "error", "issue", "viol", "problem", "failure", "reason", "defect", "reject")
_VERDICT_KEYS = frozenset({"passed", "valid", "ok", "admissible", "clean", "verified", "status", "verdict"})
_SCOPE_BOUNDARIES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


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


def mutant_signature(site: MutantSite) -> tuple[int, int, str, str, str]:
    """Canonical 5-tuple deduplication key `(line, col, kind, orig, repl)`."""
    return (site.lineno, site.col_offset, site.kind, site.original_src, site.mutated_src)


def _is_refusal_const(node: ast.expr | None) -> bool:
    if not isinstance(node, ast.Constant):
        return False
    if node.value is False or node.value is None:
        return True
    if type(node.value) is str and node.value.strip().upper().startswith(_REFUSAL_PREFIXES):
        return True
    return False


def _expr_is_refusal(val: ast.expr | None) -> bool:
    if _is_refusal_const(val):
        return True
    if isinstance(val, ast.Tuple) and len(val.elts) >= 1 and _is_refusal_const(val.elts[0]):
        return True
    if isinstance(val, ast.Dict):
        return any(_is_refusal_const(v) for v in val.values)
    if isinstance(val, ast.Call):
        if any(isinstance(a, ast.Constant) and a.value is False for a in val.args):
            return True
        if any(isinstance(kw.value, ast.Constant) and kw.value.value is False for kw in val.keywords):
            return True
    return False


def _is_acc_name(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Name) and any(h in expr.id.lower() for h in _ACCUMULATOR_HINTS)


def _is_refusal_call_stmt(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        fn = stmt.value.func
        if isinstance(fn, ast.Attribute) and fn.attr == "exit" and isinstance(fn.value, ast.Name) and fn.value.id == "sys":
            return True
        if isinstance(fn, ast.Name) and fn.id == "exit":
            return True
        if isinstance(fn, ast.Attribute) and fn.attr in ("append", "extend", "add") and _is_acc_name(fn.value):
            return True
    return False


def _is_verdict_sub_refusal(target: ast.expr, value: ast.expr) -> bool:
    return (
        isinstance(target, ast.Subscript)
        and isinstance(target.slice, ast.Constant)
        and target.slice.value in _VERDICT_KEYS
        and _is_refusal_const(value)
    )


def _stmt_is_refusal(body: Sequence[ast.stmt]) -> bool:
    ref_vars: set[str] = set()
    for stmt in body:
        if isinstance(stmt, ast.Raise) or _is_refusal_call_stmt(stmt):
            return True
        if isinstance(stmt, ast.Return):
            if _expr_is_refusal(stmt.value) or (isinstance(stmt.value, ast.Name) and stmt.value.id in ref_vars):
                return True
        elif isinstance(stmt, ast.Assign):
            is_ref = _expr_is_refusal(stmt.value) or (isinstance(stmt.value, ast.Name) and stmt.value.id in ref_vars)
            for tgt in stmt.targets:
                if _is_verdict_sub_refusal(tgt, stmt.value):
                    return True
                if isinstance(tgt, ast.Name):
                    if is_ref:
                        ref_vars.add(tgt.id)
                    else:
                        ref_vars.discard(tgt.id)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            if _is_verdict_sub_refusal(stmt.target, stmt.value):
                return True
            if isinstance(stmt.target, ast.Name):
                is_ref = _expr_is_refusal(stmt.value) or (isinstance(stmt.value, ast.Name) and stmt.value.id in ref_vars)
                if is_ref:
                    ref_vars.add(stmt.target.id)
                else:
                    ref_vars.discard(stmt.target.id)
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.op, ast.Add) and _is_acc_name(stmt.target):
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


def _stmt_is_hard_refusal(body: Sequence[ast.stmt]) -> bool:
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


def _is_main_guard(node: ast.If) -> bool:
    return isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"


def _unwrap_bool(expr: ast.expr) -> ast.expr:
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "bool" and len(expr.args) == 1 and not expr.keywords:
        return expr.args[0]
    return expr


def _store_names(node: ast.AST) -> set[str]:
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store)}


def _extract_getattr_attr_name(expr: ast.expr | None) -> str | None:
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "getattr"
        and len(expr.args) >= 2
        and isinstance(expr.args[1], ast.Constant)
        and type(expr.args[1].value) is str
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


def _build_call_scope_envs(
    tree: ast.Module,
    base_polarities: dict[str, str],
    explicit_guards: set[str] | frozenset[str] = frozenset(),
) -> tuple[dict[str, str], dict[int, dict[str, str]], dict[int, set[str]], set[str]]:
    """Build lexical-scope guard polarity environments and namespace sets for every `ast.Call`."""
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
    call_ns: dict[int, set[str]] = {}

    def _visit_expr(expr: ast.AST | None, env: dict[str, str], ns: set[str]) -> None:
        if expr is None:
            return
        stack: list[ast.AST] = [expr]
        while stack:
            cur = stack.pop()
            if isinstance(cur, ast.Lambda):
                for d in (*cur.args.defaults, *cur.args.kw_defaults):
                    _visit_expr(d, env, ns)
                l_shadowed = _extract_args_param_names(cur.args) - explicit_guards
                l_env = {k: v for k, v in env.items() if k not in l_shadowed}
                _visit_expr(cur.body, l_env, ns)
                continue
            if isinstance(cur, ast.Call):
                call_envs[id(cur)] = env
                call_ns[id(cur)] = ns
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
                call_ns[id(node)] = ns
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
                    _visit_expr(hdr, expr_env, ns)
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
                    _visit_expr(hdr, expr_env, ns)
                cls_ns = ns | _collect_scope_namespaces(node.body)
                cls_aliases, cls_unresolved = _resolve_scope_guard_aliases(node.body, enclosing_env, cls_ns)
                cls_body_env = {k: v for k, v in enclosing_env.items() if k not in cls_unresolved}
                cls_body_env.update(cls_aliases)
                _visit_scope(node.body, cls_body_env, enclosing_env, cls_ns)
            elif isinstance(node, ast.Lambda):
                _visit_expr(node, expr_env, ns)

    _visit_scope(tree.body, mod_env, mod_env, mod_ns)
    return mod_env, call_envs, call_ns, mod_ns


def _lookup_call_polarity(
    func_expr: ast.expr,
    scope_env: dict[str, str],
    attr_polarities: dict[str, str],
    discovered_polarities: dict[str, str],
    scope_ns: set[str],
) -> tuple[str | None, str | None]:
    if isinstance(func_expr, ast.Name):
        return func_expr.id, scope_env.get(func_expr.id)
    attr_name = _extract_call_guard_name(func_expr)
    if attr_name in discovered_polarities:
        return attr_name, discovered_polarities[attr_name]
    if attr_name in attr_polarities:
        root_expr = func_expr.value if isinstance(func_expr, ast.Attribute) else (func_expr.args[0] if isinstance(func_expr, ast.Call) and func_expr.args else None)
        root_nm = _attr_root_name(root_expr) if root_expr is not None else None
        if root_nm in ("self", "cls") or (root_nm is not None and root_nm in scope_ns):
            return attr_name, attr_polarities[attr_name]
    return attr_name, None


def _classify_wrapper(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    pos = list(node.args.posonlyargs) + list(node.args.args)
    if not pos:
        return None
    cond_param = pos[0].arg
    if cond_param in ("self", "cls"):
        if len(pos) < 2:
            return None
        cond_param = pos[1].arg
    idx = 0
    stmts = list(node.body)
    while idx < len(stmts) and isinstance(stmts[idx], (ast.Expr, ast.Assign, ast.AnnAssign)):
        if cond_param in _store_names(stmts[idx]):
            break
        idx += 1
    rem = stmts[idx:]
    if not rem or len(rem) > 2 or not isinstance(rem[0], ast.If):
        return None
    if len(rem) == 2 and not isinstance(rem[1], ast.Return):
        return None
    test = rem[0].test
    pol: str | None = None
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        u = _unwrap_bool(test.operand)
        if isinstance(u, ast.Name) and u.id == cond_param:
            pol = "require"
    elif isinstance(_unwrap_bool(test), ast.Name) and getattr(_unwrap_bool(test), "id", None) == cond_param:
        pol = "reject"
    elif isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
        left = _unwrap_bool(test.left)
        right = test.comparators[0]
        if isinstance(left, ast.Name) and left.id == cond_param and isinstance(right, ast.Constant):
            if isinstance(test.ops[0], (ast.Is, ast.Eq)) and right.value is False:
                pol = "require"
            elif isinstance(test.ops[0], (ast.IsNot, ast.NotEq)) and right.value is True:
                pol = "require"
            elif isinstance(test.ops[0], (ast.Is, ast.Eq)) and right.value is True:
                pol = "reject"
    if pol is None:
        return None
    if not rem[0].orelse and _stmt_is_hard_refusal(rem[0].body):
        return pol
    if _stmt_is_hard_refusal(rem[0].orelse) and not _stmt_is_hard_refusal(rem[0].body):
        return "reject" if pol == "require" else "require"
    return None


def _discover_local_wrappers(tree: ast.Module) -> dict[str, str]:
    wrappers: dict[str, str] = {}
    top_defs: set[str] = set()
    cls_methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_defs.add(node.name)
            pol = _classify_wrapper(node)
            if pol is not None:
                wrappers[node.name] = pol
            else:
                wrappers.pop(node.name, None)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cls_methods.append(item)
    cls_pols: dict[str, set[str]] = {}
    for m in cls_methods:
        if m.name not in top_defs:
            pol = _classify_wrapper(m)
            if pol is not None:
                cls_pols.setdefault(m.name, set()).add(pol)
    for name, pols in cls_pols.items():
        if len(pols) == 1:
            wrappers[name] = next(iter(pols))
    return wrappers


def _resolve_local_mod(module_name: str, roots: Sequence[Path], level: int, target_parent: Path) -> Path | None:
    parts = module_name.split(".") if module_name else []
    cands: list[Path] = []
    if level > 0:
        base = target_parent
        for _ in range(level - 1):
            base = base.parent
        cands.append(base)
    else:
        cands.extend(roots)
    for base in cands:
        if parts:
            mod_py = base.joinpath(*parts).with_suffix(".py")
            if mod_py.is_file():
                return mod_py
            pkg = base.joinpath(*parts, "__init__.py")
            if pkg.is_file():
                return pkg
        else:
            pkg = base / "__init__.py"
            if pkg.is_file():
                return pkg
    return None


def _discover_imported_wrappers(tree: ast.Module, target_path: Path | None, work_root: Path | None) -> dict[str, str]:
    if target_path is None:
        return {}
    roots = [target_path.parent]
    if work_root is not None and work_root.resolve() != target_path.parent.resolve():
        roots.append(work_root.resolve())
    out: dict[str, str] = {}
    cache: dict[Path, dict[str, str]] = {}

    def _get(mod_file: Path) -> dict[str, str]:
        if mod_file not in cache:
            try:
                mtree = ast.parse(mod_file.read_text(encoding="utf-8", errors="replace"))
                cache[mod_file] = _discover_local_wrappers(mtree)
            except (OSError, SyntaxError):
                cache[mod_file] = {}
        return cache[mod_file]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mf = _resolve_local_mod(node.module or "", roots, node.level, target_path.parent)
            if mf is None:
                continue
            mw = _get(mf)
            for alias in node.names:
                if alias.name == "*":
                    out.update(mw)
                elif alias.name in mw:
                    out[alias.asname or alias.name] = mw[alias.name]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mf = _resolve_local_mod(alias.name, roots, 0, target_path.parent)
                if mf is None:
                    continue
                for fn_name, pol in _get(mf).items():
                    out.setdefault(fn_name, pol)
    return out


def _parse_extra_guards(extra_guards: Sequence[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in extra_guards:
        for raw_tok in item.split(","):
            tok = raw_tok.strip()
            if not tok:
                continue
            if ":" in tok:
                name, pol = tok.split(":", 1)
                name, pol = name.strip(), pol.strip().lower()
                require_tc(bool(name) and pol in ("require", "reject"), "INVALID_GUARD_SPEC", f"invalid guard spec: {tok!r}")
                parsed[name] = pol
            else:
                parsed[tok] = "require"
    return parsed


def _is_self_check_invocation(target: Path, test_cmd: str) -> bool:
    try:
        parts = [tok.replace("{target}", target.name) for tok in shlex.split(test_cmd)]
    except ValueError:
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
    """Deterministically discover AST refusal-site & boundary mutants with full alias/getattr/self-check parity."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise TrustCoreError("MUTATOR_SYNTAX_ERROR", f"failed to parse target Python file: {exc}") from exc

    base_polarities: dict[str, str] = {name: "require" for name in _REQUIRE_NAMES}
    imported_wrappers = _discover_imported_wrappers(tree, target_path, work_root)
    local_wrappers = _discover_local_wrappers(tree)
    parsed_extra_guards = _parse_extra_guards(extra_guards)
    discovered_polarities: dict[str, str] = {}
    discovered_polarities.update(imported_wrappers)
    discovered_polarities.update(local_wrappers)
    discovered_polarities.update(parsed_extra_guards)
    base_polarities.update(discovered_polarities)
    mod_env, call_envs, call_ns, mod_ns = _build_call_scope_envs(tree, base_polarities, set(parsed_extra_guards))

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
                _, pol = _lookup_call_polarity(stmt.value.func, mod_env, base_polarities, discovered_polarities, mod_ns)
                if pol is not None and len(stmt.value.args) >= 1:
                    has_top_level_guard_calls = True
                    break

    all_nodes = list(ast.walk(tree))
    sites: list[MutantSite] = []
    idx_counter = 0

    for node_idx, node in enumerate(all_nodes):
        if isinstance(node, ast.If) and not _is_main_guard(node):
            if self_check_mode and has_top_level_guard_calls and id(node) in top_level_ifs:
                continue
            body_ref = _stmt_is_refusal(node.body)
            else_ref = _stmt_is_refusal(node.orelse)
            if body_ref or else_ref:
                orig_test = ast.unparse(node.test)
                if body_ref and orig_test != "False":
                    idx_counter += 1
                    sites.append(MutantSite(f"M{idx_counter:03d}", "guard_if_reject", node.lineno, node.col_offset, node_idx, f"if {orig_test}:", "if False:"))
                if else_ref and orig_test != "True":
                    idx_counter += 1
                    sites.append(MutantSite(f"M{idx_counter:03d}", "guard_else_reject", node.lineno, node.col_offset, node_idx, f"if {orig_test}: ... else:", "if True:"))
                if include_boundaries and isinstance(node.test, ast.Compare):
                    for op_i, op in enumerate(node.test.ops):
                        op_cls = type(op)
                        if op_cls in _CMP_FLIP:
                            alt = copy.deepcopy(node.test)
                            alt.ops[op_i] = _CMP_FLIP[op_cls]()
                            idx_counter += 1
                            sites.append(MutantSite(f"M{idx_counter:03d}", "boundary_cmp", node.lineno, node.col_offset, node_idx, orig_test, ast.unparse(alt), op_i))
        elif isinstance(node, ast.ExceptHandler):
            if _stmt_is_refusal(node.body):
                lbl = ast.unparse(node.type) if node.type is not None else ""
                hdr = f"except {lbl}:" if lbl else "except:"
                idx_counter += 1
                sites.append(MutantSite(f"M{idx_counter:03d}", "guard_except_reject", node.lineno, node.col_offset, node_idx, hdr, f"{hdr} pass"))
        elif isinstance(node, ast.Call):
            scope_env = call_envs.get(id(node), mod_env)
            scope_ns = call_ns.get(id(node), mod_ns)
            fn_name, pol = _lookup_call_polarity(node.func, scope_env, base_polarities, discovered_polarities, scope_ns)
            if pol is not None and len(node.args) >= 1:
                arg0 = node.args[0]
                orig_arg = ast.unparse(arg0)
                is_selfcheck_call = self_check_mode and has_top_level_guard_calls and id(node) in top_level_calls
                if is_selfcheck_call:
                    if orig_arg != "False":
                        idx_counter += 1
                        sites.append(MutantSite(f"M{idx_counter:03d}", "guard_selfcheck_negate", node.lineno, node.col_offset, node_idx, f"{fn_name}({orig_arg}, ...)", f"{fn_name}(False, ...)"))
                    if include_boundaries and isinstance(arg0, ast.Compare):
                        for op_i, op in enumerate(arg0.ops):
                            op_cls = type(op)
                            if op_cls in _CMP_FLIP:
                                alt = copy.deepcopy(arg0)
                                alt.ops[op_i] = _CMP_FLIP[op_cls]()
                                idx_counter += 1
                                sites.append(MutantSite(f"M{idx_counter:03d}", "boundary_cmp_require", node.lineno, node.col_offset, node_idx, orig_arg, ast.unparse(alt), op_i))
                        for c_i, comp in enumerate(arg0.comparators):
                            if isinstance(comp, ast.Constant) and type(comp.value) is int:
                                alt_v = copy.deepcopy(arg0)
                                alt_v.comparators[c_i] = ast.Constant(value=comp.value + 1)
                                idx_counter += 1
                                sites.append(MutantSite(f"M{idx_counter:03d}", "boundary_const_require", node.lineno, node.col_offset, node_idx, orig_arg, ast.unparse(alt_v), c_i))
                    continue

                neutral = "True" if pol == "require" else "False"
                kind = "guard_require_call" if pol == "require" else "guard_reject_call"
                if orig_arg != neutral:
                    idx_counter += 1
                    sites.append(MutantSite(f"M{idx_counter:03d}", kind, node.lineno, node.col_offset, node_idx, f"{fn_name}({orig_arg}, ...)", f"{fn_name}({neutral}, ...)"))
                    if include_boundaries and isinstance(arg0, ast.Compare):
                        for op_i, op in enumerate(arg0.ops):
                            op_cls = type(op)
                            if op_cls in _CMP_FLIP:
                                alt = copy.deepcopy(arg0)
                                alt.ops[op_i] = _CMP_FLIP[op_cls]()
                                idx_counter += 1
                                sites.append(MutantSite(f"M{idx_counter:03d}", "boundary_cmp_require", node.lineno, node.col_offset, node_idx, orig_arg, ast.unparse(alt), op_i))

    sites.sort(key=lambda s: (s.lineno, s.col_offset, s.kind, s.extra_cmp_idx))
    numbered = [
        MutantSite(f"M{i:03d}", s.kind, s.lineno, s.col_offset, s.node_index, s.original_src, s.mutated_src, s.extra_cmp_idx)
        for i, s in enumerate(sites, start=1)
    ]
    return tree, numbered


def _serialise_module(tree: ast.Module) -> str:
    ast.fix_missing_locations(tree)
    code = ast.unparse(tree) + "\n"
    compile(code, "<mutated>", "exec")
    return code


def null_mutant_source(source: str) -> str:
    return _serialise_module(ast.parse(source))


def apply_single_mutation(source: str, site: MutantSite) -> str:
    tree = ast.parse(source)
    nodes = list(ast.walk(tree))
    require_tc(0 <= site.node_index < len(nodes), "MUTANT_INDEX_OOB", "mutant AST node index out of bounds")
    node = nodes[site.node_index]
    if site.kind == "guard_if_reject":
        require_tc(isinstance(node, ast.If), "MUTANT_NODE_TYPE", "expected ast.If")
        node.test = ast.Constant(value=False)  # type: ignore[union-attr]
    elif site.kind == "guard_else_reject":
        require_tc(isinstance(node, ast.If), "MUTANT_NODE_TYPE", "expected ast.If")
        node.test = ast.Constant(value=True)  # type: ignore[union-attr]
    elif site.kind == "guard_except_reject":
        require_tc(isinstance(node, ast.ExceptHandler), "MUTANT_NODE_TYPE", "expected ast.ExceptHandler")
        node.body = [ast.Pass()]  # type: ignore[union-attr]
    elif site.kind == "boundary_cmp":
        require_tc(isinstance(node, ast.If) and isinstance(node.test, ast.Compare), "MUTANT_NODE_TYPE", "expected ast.If/Compare")
        cmp_n = node.test  # type: ignore[union-attr]
        cmp_n.ops[site.extra_cmp_idx] = _CMP_FLIP[type(cmp_n.ops[site.extra_cmp_idx])]()
    elif site.kind == "guard_require_call":
        require_tc(isinstance(node, ast.Call) and len(node.args) >= 1, "MUTANT_NODE_TYPE", "expected ast.Call")
        node.args[0] = ast.Constant(value=True)  # type: ignore[union-attr]
    elif site.kind in ("guard_reject_call", "guard_selfcheck_negate"):
        require_tc(isinstance(node, ast.Call) and len(node.args) >= 1, "MUTANT_NODE_TYPE", "expected ast.Call")
        node.args[0] = ast.Constant(value=False)  # type: ignore[union-attr]
    elif site.kind == "boundary_cmp_require":
        require_tc(isinstance(node, ast.Call) and isinstance(node.args[0], ast.Compare), "MUTANT_NODE_TYPE", "expected Call/Compare")
        cmp_n = node.args[0]  # type: ignore[union-attr]
        cmp_n.ops[site.extra_cmp_idx] = _CMP_FLIP[type(cmp_n.ops[site.extra_cmp_idx])]()
    elif site.kind == "boundary_const_require":
        require_tc(isinstance(node, ast.Call) and isinstance(node.args[0], ast.Compare), "MUTANT_NODE_TYPE", "expected Call/Compare")
        cmp_n = node.args[0]  # type: ignore[union-attr]
        comp = cmp_n.comparators[site.extra_cmp_idx]
        require_tc(isinstance(comp, ast.Constant) and type(comp.value) is int, "MUTANT_NODE_TYPE", "expected int constant")
        cmp_n.comparators[site.extra_cmp_idx] = ast.Constant(value=comp.value + 1)
    else:
        raise TrustCoreError("UNKNOWN_MUTANT_KIND", f"unknown mutant kind: {site.kind!r}")
    return _serialise_module(tree)


def _prepare_base_cmd(test_cmd: str, target_rel: str, *, add_cwd: bool = False) -> list[str]:
    try:
        raw_parts = shlex.split(test_cmd)
    except ValueError as exc:
        raise TrustCoreError("INVALID_TEST_CMD", f"malformed test_cmd: {exc}") from exc
    parts = [tok.replace("{target}", target_rel) for tok in raw_parts]
    require_tc(len(parts) > 0, "EMPTY_TEST_CMD", "test_cmd cannot be empty")
    if parts[0] in ("python", "python3"):
        rest = parts[1:]
        flags: list[str] = []
        if add_cwd:
            if "-s" not in rest and "-I" not in rest:
                flags.append("-s")
        elif "-I" not in rest:
            flags.append("-I")
        if "-O" not in rest:
            flags.append("-O")
        if "-B" not in rest:
            flags.append("-B")
        return [sys.executable, *flags, *rest]
    return parts


def _script_has_ast_unittest_main(script_path: Path) -> bool:
    """AST-verify a direct `if __name__ == '__main__': unittest.main()` call with no custom `argv`."""
    try:
        tree = ast.parse(script_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return False
    for stmt in tree.body:
        if isinstance(stmt, ast.If) and _is_main_guard(stmt):
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Call):
                    fn = sub.func
                    if (
                        isinstance(fn, ast.Attribute)
                        and fn.attr == "main"
                        and isinstance(fn.value, ast.Name)
                        and fn.value.id == "unittest"
                    ):
                        if len(sub.args) == 0 and not any(kw.arg == "argv" for kw in sub.keywords):
                            return True
    return False


def inject_unittest_failfast(cmd_parts: Sequence[str], *, work_root: Path | None = None) -> tuple[list[str], bool]:
    """
    Inject `-f` (`--failfast`) into AST-verified `unittest` invocations automatically.
    Returns `(new_cmd_parts, injected_flag)`. Compatibility is strictly verified by running
    the null-mutant control with `mutant_cmd` before any mutant executes.
    """
    parts = list(cmd_parts)
    if "-f" in parts or "--failfast" in parts:
        return parts, False
    # Case 1: `... -m unittest ...`
    for i in range(len(parts) - 1):
        if parts[i] == "-m" and parts[i + 1] == "unittest":
            insert_at = i + 2
            if insert_at < len(parts) and parts[insert_at] == "discover":
                insert_at += 1
            parts.insert(insert_at, "-f")
            return parts, True
    # Case 2: direct `python [flags] test_foo.py` (never non-python runners or `-m`/`-c`)
    if work_root is not None and len(parts) >= 2 and Path(parts[0]).name.startswith("python"):
        idx = 1
        while idx < len(parts):
            tok = parts[idx]
            if tok in ("-m", "-c"):
                break
            if tok in ("-W", "-X"):
                idx += 2
                continue
            if tok.startswith("-"):
                idx += 1
                continue
            if tok.endswith(".py"):
                cand = work_root / tok
                if cand.is_file() and _script_has_ast_unittest_main(cand):
                    parts.append("-f")
                    return parts, True
            break
    return parts, False


def parse_unified_diff_added_lines(diff_text: str) -> set[int]:
    """Parse `git diff -U0` unified diff output and return exact added/modified line numbers in the new file."""
    changed: set[int] = set()
    for line in diff_text.splitlines():
        m = _HUNK_RE.match(line)
        if m is not None:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            if count > 0:
                changed.update(range(start, start + count))
    return changed


def parse_line_ranges(spec: str) -> set[int]:
    """Parse bounded comma-separated 1-based line numbers or `a-b` ranges (e.g. `'10-20,35'`)."""
    out: set[int] = set()
    budget = 0
    for raw in spec.split(","):
        tok = raw.strip()
        if not tok:
            continue
        if "-" in tok:
            a_s, b_s = tok.split("-", 1)
            require_tc(a_s.isdigit() and b_s.isdigit(), "INVALID_LINE_RANGE", f"invalid range: {tok!r}")
            a_i, b_i = int(a_s), int(b_s)
            require_tc(1 <= a_i <= b_i, "INVALID_LINE_RANGE", f"invalid line bounds: {tok!r}")
            budget += (b_i - a_i + 1)
            require_tc(budget <= MAX_LINE_RANGE_SPAN, "LINE_RANGE_TOO_LARGE", f"range exceeds {MAX_LINE_RANGE_SPAN} lines: {tok!r}")
            out.update(range(a_i, b_i + 1))
        else:
            require_tc(tok.isdigit() and int(tok) >= 1, "INVALID_LINE_RANGE", f"invalid line number: {tok!r}")
            budget += 1
            require_tc(budget <= MAX_LINE_RANGE_SPAN, "LINE_RANGE_TOO_LARGE", f"total line count exceeds {MAX_LINE_RANGE_SPAN}")
            out.add(int(tok))
    require_tc(len(out) > 0, "EMPTY_LINE_RANGE", "line range specification produced zero lines")
    return out


def _get_git_changed_lines(target: Path, src_root: Path, diff_base: str | None) -> set[int]:
    cmd = ["git", "diff", "-U0"]
    if diff_base is not None:
        cmd.append(diff_base)
    cmd.extend(["--", os.fspath(target)])
    try:
        proc = subprocess.run(cmd, cwd=str(src_root), capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrustCoreError("GIT_DIFF_FAILED", f"git diff failed: {exc}") from exc
    require_tc(proc.returncode == 0, "GIT_DIFF_FAILED", f"git diff rc={proc.returncode}")
    return parse_unified_diff_added_lines(proc.stdout.decode("utf-8", errors="replace"))


def _copy_workroot_nosym(
    src_root: Path, dst_root: Path
) -> tuple[str, set[str], dict[str, tuple[int, int, int, str]], dict[str, tuple[int, int, int]]]:
    """
    Copy `src_root` into `dst_root` preserving exact file/dir `mtime` (`shutil.copy2` + bottom-up `utime`)
    and permissions while rejecting symlinks/non-regular entries.
    Returns `(tree_sha256, rel_file_set, rel_meta, rel_dirs)` where `rel_meta[rel] = (size, mtime_ns, mode, sha256)`
    and `rel_dirs[rel] = (mode, atime_ns, mtime_ns)` records EVERY baseline directory (including empty ones and
    the slot root `"."`) so slot cleanup preserves/restores them exactly (Delta-5 MED-1 + LOW-5).
    """
    os.mkdir(dst_root, 0o700)
    src_root_st = os.lstat(src_root)
    dir_times: list[tuple[Path, str, tuple[int, int]]] = [(dst_root, ".", (src_root_st.st_atime_ns, src_root_st.st_mtime_ns))]
    stack: list[tuple[Path, Path, Path]] = [(src_root, dst_root, Path("."))]
    manifest_parts: list[str] = []
    rel_files: set[str] = set()
    rel_meta: dict[str, tuple[int, int, int, str]] = {}
    rel_dirs: dict[str, tuple[int, int, int]] = {}
    while stack:
        c_src, c_dst, c_rel = stack.pop()
        with os.scandir(c_src) as it:
            entries = sorted(it, key=lambda e: e.name)
        for entry in entries:
            if entry.name in _COPY_IGNORE or entry.name.endswith(".pyc"):
                continue
            require_tc(not entry.is_symlink(), "SYMLINK_IN_WORKROOT", f"symlink forbidden in work_root: {entry.name}")
            dst_item = c_dst / entry.name
            rel_item = Path(entry.name) if c_rel == Path(".") else (c_rel / entry.name)
            if entry.is_dir(follow_symlinks=False):
                os.mkdir(dst_item, 0o700)
                st_dir = entry.stat(follow_symlinks=False)
                dir_times.append((dst_item, os.fspath(rel_item), (st_dir.st_atime_ns, st_dir.st_mtime_ns)))
                stack.append((Path(entry.path), dst_item, rel_item))
            elif entry.is_file(follow_symlinks=False):
                shutil.copy2(entry.path, dst_item)
                st_dst = os.lstat(dst_item)
                rel_s = os.fspath(rel_item)
                rel_files.add(rel_s)
                fsha = sha256_bytes(strict_read_bytes_nofollow(dst_item))
                rel_meta[rel_s] = (int(st_dst.st_size), int(st_dst.st_mtime_ns), stat.S_IMODE(st_dst.st_mode), fsha)
                manifest_parts.append(f"{rel_s}:{fsha}")
            else:
                raise TrustCoreError("NON_REGULAR_IN_WORKROOT", f"non-regular file forbidden: {entry.name}")
    for d_dst, d_rel, d_ns in reversed(dir_times):
        os.utime(d_dst, ns=d_ns)
        rel_dirs[d_rel] = (stat.S_IMODE(os.lstat(d_dst).st_mode), int(d_ns[0]), int(d_ns[1]))
    manifest_parts.sort()
    tree_sha = sha256_bytes("\n".join(manifest_parts).encode("utf-8"))
    return tree_sha, rel_files, rel_meta, rel_dirs

def _rmtree_force(root: Path) -> None:
    if not root.exists() and not root.is_symlink():
        return
    for cur_s, dirs, files in os.walk(root, topdown=True, followlinks=False):
        try:
            if not os.path.islink(cur_s):
                os.chmod(cur_s, 0o700)
        except OSError:
            pass
        for dn in dirs:
            dp_s = os.path.join(cur_s, dn)
            if not os.path.islink(dp_s):
                try:
                    os.chmod(dp_s, 0o700)
                except OSError:
                    pass
        for fn in files:
            fp_s = os.path.join(cur_s, fn)
            if not os.path.islink(fp_s):
                try:
                    os.chmod(fp_s, 0o600)
                except OSError:
                    pass
    shutil.rmtree(root, ignore_errors=True)


def _write_preserve_mtime(target: Path, text: str, orig_times_ns: tuple[int, int], mode: int | None = None) -> None:
    """
    (Re)write `target` with `text`, then pin its EXACT baseline `st_mode` (`mode`, i.e. `orig_mode | 0o200`) and
    `(atime_ns, mtime_ns)`. Non-regular entries (symlink/dir/fifo) and multiply-linked inodes (`st_nlink != 1`)
    are replaced by a fresh regular file, so a mutant's `os.chmod(__file__, 0o000)` / hard-link / dir swap can
    never leak into later mutants (Delta-5 HIGH-1).
    """
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    os.chmod(parent, stat.S_IMODE(os.lstat(parent).st_mode) | 0o700)
    if os.path.lexists(target):
        st_t = os.lstat(target)
        if stat.S_ISDIR(st_t.st_mode):
            _rmtree_force(target)
        elif not stat.S_ISREG(st_t.st_mode) or st_t.st_nlink != 1:
            target.unlink()
        else:
            os.chmod(target, (stat.S_IMODE(st_t.st_mode) if mode is None else mode) | 0o200)
    target.write_text(text, encoding="utf-8", newline="\n")
    if mode is not None:
        os.chmod(target, mode)
    os.utime(target, ns=orig_times_ns)

def _run_subprocess_pg(
    cmd: Sequence[str],
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> tuple[int, bytes, bytes, bool]:
    """Run child in its own process group (`start_new_session=True`) and `killpg` entire group on timeout."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out_b, err_b = proc.communicate(timeout=timeout)
        return int(proc.returncode), out_b, err_b, False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            out_b, err_b = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out_b, err_b = b"", b""
        return -9, out_b, err_b, True


def _slot_file_matches(fp: Path, meta: tuple[int, int, int, str]) -> bool:
    """Exact golden-baseline check: regular, `st_nlink == 1`, `(size, mtime_ns, mode, sha256)` all identical."""
    exp_size, exp_mtime_ns, exp_mode, exp_sha = meta
    st_cur = os.lstat(fp) if os.path.lexists(fp) else None
    return (
        st_cur is not None
        and stat.S_ISREG(st_cur.st_mode)
        and st_cur.st_nlink == 1
        and int(st_cur.st_size) == exp_size
        and int(st_cur.st_mtime_ns) == exp_mtime_ns
        and stat.S_IMODE(st_cur.st_mode) == exp_mode
        and (exp_mode & 0o400) != 0
        and sha256_bytes(fp.read_bytes()) == exp_sha
    )


def _slot_dir_matches(dp: Path, meta: tuple[int, int, int]) -> bool:
    """Exact baseline directory check: real directory with identical `mode` and `mtime_ns`."""
    exp_mode, _, exp_mtime_ns = meta
    st_d = os.lstat(dp) if os.path.lexists(dp) else None
    return st_d is not None and stat.S_ISDIR(st_d.st_mode) and stat.S_IMODE(st_d.st_mode) == exp_mode and int(st_d.st_mtime_ns) == exp_mtime_ns


def _remove_any(fp: Path) -> None:
    if fp.is_symlink():
        fp.unlink()
    elif fp.is_dir():
        _rmtree_force(fp)
    elif os.path.lexists(fp):
        os.chmod(fp, 0o600)
        fp.unlink()


def _clean_slot_stray_entries(
    slot_root: Path,
    expected_rel_files: set[str],
    slot_tmp: Path,
    slot_home: Path,
    *,
    src_root: Path | None = None,
    rel_meta: dict[str, tuple[int, int, int, str]] | None = None,
    rel_dirs: dict[str, tuple[int, int, int]] | None = None,
    target_spec: tuple[str, str, int, tuple[int, int]] | None = None,
) -> None:
    """
    Remove stray files/symlinks/dirs, preserve/restore every baseline directory (`rel_dirs`, incl. empty ones),
    restore EVERY tracked baseline file whose existence, file type, link count, exact mode, mtime, or SHA-256
    differs from the golden baseline, and restore the mutation target itself from `target_spec =
    (rel_target, source_text, exact_mode, (atime_ns, mtime_ns))` -- never skipping it (Delta-5 HIGH-1).
    Every restored entry is re-verified post-copy; any residual mismatch fails closed (`SLOT_RESTORE_MISMATCH`).
    """
    dirs_meta = rel_dirs if rel_dirs is not None else {}
    # Ensure the slot root and all non-symlink directories are traversable even after a `chmod 0o000` mutant
    os.chmod(slot_root, 0o700)
    for cur_s, dirs, _ in os.walk(slot_root, topdown=True, followlinks=False):
        if not os.path.islink(cur_s):
            try:
                os.chmod(cur_s, 0o700)
            except OSError:
                pass
        for dn in dirs:
            dp_s = os.path.join(cur_s, dn)
            if not os.path.islink(dp_s):
                try:
                    os.chmod(dp_s, 0o700)
                except OSError:
                    pass

    for cur_s, dirs, files in os.walk(slot_root, topdown=False, followlinks=False):
        cur_p = Path(cur_s)
        for fn in files:
            fp = cur_p / fn
            rel_s = os.fspath(fp.relative_to(slot_root))
            if fp.is_symlink():
                try:
                    fp.unlink()
                except OSError:
                    pass
            elif rel_s not in expected_rel_files:
                try:
                    os.chmod(fp, 0o600)
                    fp.unlink()
                except OSError:
                    pass
        for dn in dirs:
            dp = cur_p / dn
            rel_d = os.fspath(dp.relative_to(slot_root))
            if dp.is_symlink():
                try:
                    dp.unlink()
                except OSError:
                    pass
                continue
            if rel_d in expected_rel_files:
                _rmtree_force(dp)
                continue
            if rel_d in dirs_meta:
                continue
            try:
                if not any(dp.iterdir()):
                    rel_prefix = rel_d + os.sep
                    if not any(rf.startswith(rel_prefix) for rf in expected_rel_files):
                        os.chmod(dp, 0o700)
                        dp.rmdir()
            except OSError:
                pass

    # Recreate any missing (or type-swapped) baseline directory, parents first (Delta-5 MED-1)
    for rel_d in sorted(dirs_meta, key=lambda r: (0 if r == "." else 1, r.count(os.sep), r)):
        dp = slot_root / rel_d
        if not dp.is_dir() or dp.is_symlink():
            _remove_any(dp)
            dp.mkdir(parents=True, exist_ok=True)

    # The mutation target is restored from the in-memory golden source with its EXACT pinned mode (Delta-5 HIGH-1)
    target_meta: dict[str, tuple[int, int, int, str]] = {}
    if target_spec is not None:
        t_rel, t_text, t_mode, t_times = target_spec
        t_bytes = t_text.encode("utf-8")
        target_meta[t_rel] = (len(t_bytes), int(t_times[1]), t_mode, sha256_bytes(t_bytes))
        t_fp = slot_root / t_rel
        if not _slot_file_matches(t_fp, target_meta[t_rel]):
            _write_preserve_mtime(t_fp, t_text, t_times, t_mode)

    # Explicit golden-baseline verification & restoration across ALL other tracked files
    if src_root is not None and rel_meta is not None:
        for rel_s in sorted(expected_rel_files):
            meta = rel_meta.get(rel_s)
            if meta is None or rel_s in target_meta:
                continue
            fp = slot_root / rel_s
            if not _slot_file_matches(fp, meta):
                _remove_any(fp)
                fp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_root / rel_s, fp)

    # Re-pin baseline directory modes & `mtime_ns` AFTER all file operations (Delta-5 LOW-5)
    for rel_d in sorted(dirs_meta, key=lambda r: (1 if r == "." else 0, -r.count(os.sep), r)):
        d_mode, d_atime, d_mtime = dirs_meta[rel_d]
        dp = slot_root / rel_d
        os.chmod(dp, d_mode)
        os.utime(dp, ns=(d_atime, d_mtime))

    # Post-restore re-verification of EVERY tracked file, the target, and every baseline dir (fail closed)
    mismatched: list[str] = []
    if src_root is not None and rel_meta is not None:
        for rel_s in sorted(expected_rel_files):
            meta = target_meta.get(rel_s, rel_meta.get(rel_s))
            if meta is not None and not _slot_file_matches(slot_root / rel_s, meta):
                mismatched.append(rel_s)
    for rel_s, meta in sorted(target_meta.items()):
        if rel_s not in mismatched and not _slot_file_matches(slot_root / rel_s, meta):
            mismatched.append(rel_s)
    for rel_d, d_meta in sorted(dirs_meta.items()):
        if not _slot_dir_matches(slot_root / rel_d, d_meta):
            mismatched.append(rel_d + os.sep)
    require_tc(len(mismatched) == 0, "SLOT_RESTORE_MISMATCH", f"slot restore verification failed: {mismatched[:5]}")

    for scratch in (slot_tmp, slot_home):
        _rmtree_force(scratch)
        os.mkdir(scratch, 0o700)

def _select_snap_parent(prefer_shm: bool) -> Path:
    shm = Path("/dev/shm")
    if prefer_shm and sys.platform.startswith("linux"):
        try:
            st = os.lstat(shm)
            if stat.S_ISDIR(st.st_mode) and os.access(shm, os.W_OK | os.X_OK):
                return shm
        except OSError:
            pass
    return Path(tempfile.gettempdir()).resolve()


def _child_env(workers: int, slot_tmp: Path, slot_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONSTARTUP", None)
    env.pop("PYTHONWARNINGS", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["TMPDIR"] = os.fspath(slot_tmp)
    env["HOME"] = os.fspath(slot_home)
    if workers > 1:
        env["OPENBLAS_NUM_THREADS"] = "1"
        env["OMP_NUM_THREADS"] = "1"
        env["MKL_NUM_THREADS"] = "1"
        env["NUMEXPR_NUM_THREADS"] = "1"
    return env


def run_fast_mutation_pass(
    script_path: str | Path,
    test_cmd: str,
    *,
    work_root: str | Path | None = None,
    max_mutants: int = 0,
    timeout: int = 30,
    include_boundaries: bool = True,
    add_cwd: bool = False,
    extra_guards: Sequence[str] = (),
    workers: int = 1,
    failfast: bool = True,
    prior_killed_map: dict[tuple[int, int, str, str, str], dict[str, Any]] | None = None,
    changed_only: bool = False,
    changed_lines: set[int] | None = None,
    diff_base: str | None = None,
) -> dict[str, Any]:
    """
    Execute one accelerated mutation pass with exact parity against `aletheia mutate`.
    Always runs baseline (`base_cmd`) + null-mutant (`mutant_cmd`) controls, preserves `mtime`,
    binds dedup reuse to `(work_root_tree_hash, target_sha, cmds)`, isolates per-slot `TMPDIR`/`HOME`,
    and classifies timeouts as `TIMEOUT` (failure).
    """
    t0_ns = time.monotonic_ns()
    require_tc(type(workers) is int and 1 <= workers <= _MAX_WORKERS, "INVALID_WORKERS", f"workers must be int in [1, {_MAX_WORKERS}]")
    require_tc(type(max_mutants) is int and max_mutants >= 0, "INVALID_MAX_MUTANTS", "max_mutants must be non-negative int")
    require_tc(type(timeout) is int and timeout >= 1, "INVALID_TIMEOUT", "timeout must be positive int")

    target = Path(script_path).resolve()
    require_tc(target.is_file(), "TARGET_NOT_FOUND", f"target script not found: {target}")
    src_root = (Path(work_root) if work_root is not None else target.parent).resolve()
    require_tc(target == src_root or src_root in target.parents, "TARGET_OUTSIDE_WORKROOT", "target outside work_root")

    raw_bytes = strict_read_bytes_nofollow(target)
    target_sha = sha256_bytes(raw_bytes)
    try:
        source = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TrustCoreError("INVALID_UTF8", f"target script invalid UTF-8: {exc}") from exc

    self_check_mode = _is_self_check_invocation(target, test_cmd)
    _, all_sites = discover_mutant_sites(
        source,
        include_boundaries=include_boundaries,
        extra_guards=extra_guards,
        target_path=target,
        work_root=src_root,
        self_check_mode=self_check_mode,
    )
    discovered = len(all_sites)
    require_tc(discovered > 0, "NO_MUTANTS_DISCOVERED", f"no refusal/boundary sites found in {target}")

    is_partial_scope = not include_boundaries
    selected_sites = list(all_sites)
    active_changed_lines: list[int] = []
    if changed_only or changed_lines is not None:
        is_partial_scope = True
        line_set = changed_lines if changed_lines is not None else _get_git_changed_lines(target, src_root, diff_base)
        active_changed_lines = sorted(line_set)
        selected_sites = [s for s in selected_sites if s.lineno in line_set]

    truncated = False
    if max_mutants > 0 and len(selected_sites) > max_mutants:
        selected_sites = selected_sites[:max_mutants]
        truncated = True
        is_partial_scope = True

    rel_target = target.relative_to(src_root)
    base_cmd = _prepare_base_cmd(test_cmd, os.fspath(rel_target), add_cwd=add_cwd)
    if failfast:
        mutant_cmd, failfast_injected = inject_unittest_failfast(base_cmd, work_root=src_root)
    else:
        mutant_cmd, failfast_injected = list(base_cmd), False

    snap_parent = _select_snap_parent(prefer_shm=(workers > 1))
    snap_dir = snap_parent / f"fast_mut_{os.getpid()}_{secrets.token_hex(8)}"
    os.mkdir(snap_dir, 0o700)

    reused_entries: dict[int, dict[str, Any]] = {}
    executed_entries: dict[int, dict[str, Any]] = {}
    to_run: list[tuple[int, MutantSite, str, str]] = []
    context_sha = ""

    try:
        slot0 = snap_dir / "slot_0"
        tree_sha, expected_rel_files, expected_rel_meta, expected_rel_dirs = _copy_workroot_nosym(src_root, slot0)
        rel_target_s = os.fspath(rel_target)
        slot0_target = slot0 / rel_target
        orig_st = os.lstat(slot0_target)
        orig_times_ns = (orig_st.st_atime_ns, orig_st.st_mtime_ns)
        orig_mode = stat.S_IMODE(orig_st.st_mode)
        tgt_mode = orig_mode | 0o200
        os.chmod(slot0_target, tgt_mode)
        os.utime(slot0_target, ns=orig_times_ns)
        tgt_spec = (rel_target_s, source, tgt_mode, orig_times_ns)

        slot0_tmp = snap_dir / "tmp_0"
        slot0_home = snap_dir / "home_0"
        os.mkdir(slot0_tmp, 0o700)
        os.mkdir(slot0_home, 0o700)
        env0 = _child_env(workers, slot0_tmp, slot0_home)

        context_payload = json.dumps(
            {
                "base_cmd": base_cmd,
                "mutant_cmd": mutant_cmd,
                "python_executable": sys.executable,
                "target_sha": target_sha,
                "timeout": timeout,
                "tree_sha": tree_sha,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        context_sha = sha256_bytes(context_payload)

        # 1. Baseline check (always full suite via `base_cmd`)
        b_rc, _, b_err, b_to = _run_subprocess_pg(base_cmd, slot0, env0, timeout)
        require_tc(not b_to, "BASELINE_TEST_TIMEOUT", f"baseline test timed out after {timeout}s")
        require_tc(
            b_rc == 0,
            "BASELINE_TEST_FAILED",
            f"baseline failed rc={b_rc}: {b_err.decode('utf-8', errors='replace')[-300:]}",
        )
        _clean_slot_stray_entries(slot0, expected_rel_files, slot0_tmp, slot0_home, src_root=src_root, rel_meta=expected_rel_meta, rel_dirs=expected_rel_dirs, target_spec=tgt_spec)

        # 2. Null-mutant control (ALWAYS runs with `mutant_cmd`, validating BOTH `ast.unparse` AND `-f` flag!)
        _write_preserve_mtime(slot0_target, null_mutant_source(source), orig_times_ns, tgt_mode)
        try:
            n_rc, _, _, n_to = _run_subprocess_pg(mutant_cmd, slot0, env0, timeout)
        finally:
            _clean_slot_stray_entries(slot0, expected_rel_files, slot0_tmp, slot0_home, src_root=src_root, rel_meta=expected_rel_meta, rel_dirs=expected_rel_dirs, target_spec=tgt_spec)
        require_tc(not n_to, "NULL_MUTANT_TIMEOUT", f"null mutant timed out after {timeout}s")
        require_tc(n_rc == 0, "NULL_MUTANT_KILLED", f"null mutant failed rc={n_rc}")

        # 3. Context-bound dedup partitioning
        prior_map = prior_killed_map or {}
        for idx, site in enumerate(selected_sites):
            mcode = apply_single_mutation(source, site)
            msha = sha256_bytes(mcode.encode("utf-8"))
            sig = mutant_signature(site)
            prior = prior_map.get(sig)
            if (
                prior is not None
                and prior.get("status") == "KILLED"
                and prior.get("mutated_sha256") == msha
                and prior.get("context_sha256") == context_sha
            ):
                reused_entries[idx] = {
                    "id": site.mutant_id,
                    "kind": site.kind,
                    "line": site.lineno,
                    "col": site.col_offset,
                    "original": site.original_src,
                    "mutated": site.mutated_src,
                    "mutated_sha256": msha,
                    "context_sha256": context_sha,
                    "returncode": prior["returncode"],
                    "status": "KILLED",
                    "dedup_reused": True,
                }
            else:
                to_run.append((idx, site, mcode, msha))

        # 4. Execute remaining mutants (single-worker or isolated RAM-backed parallel slots)
        eff_workers = min(workers, len(to_run)) if len(to_run) > 0 else 1
        if len(to_run) > 0 and eff_workers == 1:
            for idx, site, mcode, msha in to_run:
                _write_preserve_mtime(slot0_target, mcode, orig_times_ns, tgt_mode)
                try:
                    rc, _, _, timed_out = _run_subprocess_pg(mutant_cmd, slot0, env0, timeout)
                    status = "TIMEOUT" if timed_out else ("KILLED" if rc != 0 else "SURVIVED")
                finally:
                    _clean_slot_stray_entries(slot0, expected_rel_files, slot0_tmp, slot0_home, src_root=src_root, rel_meta=expected_rel_meta, rel_dirs=expected_rel_dirs, target_spec=tgt_spec)
                executed_entries[idx] = {
                    "id": site.mutant_id,
                    "kind": site.kind,
                    "line": site.lineno,
                    "col": site.col_offset,
                    "original": site.original_src,
                    "mutated": site.mutated_src,
                    "mutated_sha256": msha,
                    "context_sha256": context_sha,
                    "returncode": rc,
                    "status": status,
                    "dedup_reused": False,
                }
        elif len(to_run) > 0:
            slots: list[tuple[Path, Path, Path, Path, dict[str, str]]] = [(slot0, slot0_target, slot0_tmp, slot0_home, env0)]
            for s_i in range(1, eff_workers):
                s_root = snap_dir / f"slot_{s_i}"
                shutil.copytree(slot0, s_root)
                s_tmp = snap_dir / f"tmp_{s_i}"
                s_home = snap_dir / f"home_{s_i}"
                os.mkdir(s_tmp, 0o700)
                os.mkdir(s_home, 0o700)
                slots.append((s_root, s_root / rel_target, s_tmp, s_home, _child_env(workers, s_tmp, s_home)))
            slot_q: queue.Queue[int] = queue.Queue()
            for s_i in range(eff_workers):
                slot_q.put(s_i)

            def _run_one(item: tuple[int, MutantSite, str, str]) -> tuple[int, dict[str, Any]]:
                idx_i, site_i, mcode_i, msha_i = item
                slot_id = slot_q.get()
                s_root, s_tgt, s_tmp, s_home, s_env = slots[slot_id]
                try:
                    _write_preserve_mtime(s_tgt, mcode_i, orig_times_ns, tgt_mode)
                    try:
                        rc_i, _, _, to_i = _run_subprocess_pg(mutant_cmd, s_root, s_env, timeout)
                        status_i = "TIMEOUT" if to_i else ("KILLED" if rc_i != 0 else "SURVIVED")
                    finally:
                        _clean_slot_stray_entries(s_root, expected_rel_files, s_tmp, s_home, src_root=src_root, rel_meta=expected_rel_meta, rel_dirs=expected_rel_dirs, target_spec=tgt_spec)
                finally:
                    slot_q.put(slot_id)
                return idx_i, {
                    "id": site_i.mutant_id,
                    "kind": site_i.kind,
                    "line": site_i.lineno,
                    "col": site_i.col_offset,
                    "original": site_i.original_src,
                    "mutated": site_i.mutated_src,
                    "mutated_sha256": msha_i,
                    "context_sha256": context_sha,
                    "returncode": rc_i,
                    "status": status_i,
                    "dedup_reused": False,
                }

            with ThreadPoolExecutor(max_workers=eff_workers) as pool:
                futs = [pool.submit(_run_one, item) for item in to_run]
                for fut in as_completed(futs):
                    idx_r, ent_r = fut.result()
                    executed_entries[idx_r] = ent_r
    finally:
        _rmtree_force(snap_dir)

    results: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []
    timeouts: list[dict[str, Any]] = []
    killed = 0
    for idx in range(len(selected_sites)):
        ent = reused_entries[idx] if idx in reused_entries else executed_entries[idx]
        results.append(ent)
        if ent["status"] == "KILLED":
            killed += 1
        elif ent["status"] == "TIMEOUT":
            timeouts.append(ent)
        else:
            survivors.append(ent)

    total = len(selected_sites)
    if len(survivors) > 0 or len(timeouts) > 0:
        verdict = "FAIL"
        passed = False
    elif is_partial_scope:
        verdict = "PARTIAL_SCOPE_NOT_FINAL"
        passed = False
    else:
        verdict = "PASS"
        passed = True

    kill_rate_q = str(Fraction(killed, total)) if total > 0 else "0/1"
    kill_rate_bps = (killed * 10000) // total if total > 0 else 0
    elapsed_ms = (time.monotonic_ns() - t0_ns) // 1_000_000
    control_evals = 2
    mutant_evals = len(to_run)
    return {
        "verdict": verdict,
        "passed": passed,
        "scope_status": "PARTIAL_SCOPE_NOT_FINAL" if is_partial_scope else "FULL_SIGNOFF_ELIGIBLE",
        "final_signoff_eligible": not is_partial_scope,
        "target": os.fspath(target),
        "target_sha256": target_sha,
        "context_sha256": context_sha,
        "test_cmd": test_cmd,
        "self_check_mode": self_check_mode,
        "include_boundaries": include_boundaries,
        "failfast_injected": failfast_injected,
        "null_mutant": "passed",
        "mutants_discovered": discovered,
        "total_mutants": total,
        "control_subprocess_evals": control_evals,
        "mutants_executed": mutant_evals,
        "total_subprocess_evals": control_evals + mutant_evals,
        "mutants_dedup_reused": len(reused_entries),
        "truncated": truncated,
        "changed_only": changed_only or (changed_lines is not None),
        "changed_lines": active_changed_lines,
        "killed": killed,
        "survived": len(survivors),
        "timed_out": len(timeouts),
        "kill_rate_q": kill_rate_q,
        "kill_rate_bps": int(kill_rate_bps),
        "elapsed_ms": int(elapsed_ms),
        "survivors": survivors,
        "timeouts": timeouts,
        "results": results,
    }


def run_dual_fast_mutation(
    script_path: str | Path,
    test_cmd: str,
    *,
    pass2_guards: Sequence[str],
    work_root: str | Path | None = None,
    max_mutants: int = 0,
    timeout: int = 30,
    include_boundaries: bool = True,
    add_cwd: bool = False,
    workers: int = 1,
    failfast: bool = True,
    changed_only: bool = False,
    changed_lines: set[int] | None = None,
    diff_base: str | None = None,
) -> dict[str, Any]:
    """
    Execute dual-pass mutation testing (Pass 1 default + Pass 2 `--guards`) with
    context-bound mathematically 100% lossless Pass-2 deduplication (`K_1 U K_2 = K_1 U (K_2 \\ K_1)`).
    """
    t0_ns = time.monotonic_ns()
    pass1 = run_fast_mutation_pass(
        script_path,
        test_cmd,
        work_root=work_root,
        max_mutants=max_mutants,
        timeout=timeout,
        include_boundaries=include_boundaries,
        add_cwd=add_cwd,
        extra_guards=(),
        workers=workers,
        failfast=failfast,
        changed_only=changed_only,
        changed_lines=changed_lines,
        diff_base=diff_base,
    )
    killed_map: dict[tuple[int, int, str, str, str], dict[str, Any]] = {}
    for ent in pass1["results"]:
        if ent["status"] == "KILLED":
            sig = (ent["line"], ent["col"], ent["kind"], ent["original"], ent["mutated"])
            killed_map[sig] = ent

    pass2 = run_fast_mutation_pass(
        script_path,
        test_cmd,
        work_root=work_root,
        max_mutants=max_mutants,
        timeout=timeout,
        include_boundaries=include_boundaries,
        add_cwd=add_cwd,
        extra_guards=pass2_guards,
        workers=workers,
        failfast=failfast,
        prior_killed_map=killed_map,
        changed_only=changed_only,
        changed_lines=changed_lines,
        diff_base=diff_base,
    )

    total_combined = pass1["total_mutants"] + pass2["total_mutants"]
    killed_combined = pass1["killed"] + pass2["killed"]
    survived_combined = pass1["survived"] + pass2["survived"]
    timed_out_combined = pass1["timed_out"] + pass2["timed_out"]
    mutant_evals_combined = pass1["mutants_executed"] + pass2["mutants_executed"]
    control_evals_combined = pass1["control_subprocess_evals"] + pass2["control_subprocess_evals"]
    dedup_skipped = pass2["mutants_dedup_reused"]
    is_partial = (not pass1["final_signoff_eligible"]) or (not pass2["final_signoff_eligible"])

    if survived_combined > 0 or timed_out_combined > 0:
        verdict = "FAIL"
        passed = False
    elif is_partial:
        verdict = "PARTIAL_SCOPE_NOT_FINAL"
        passed = False
    else:
        verdict = "PASS"
        passed = True

    elapsed_ms = (time.monotonic_ns() - t0_ns) // 1_000_000
    return {
        "verdict": verdict,
        "passed": passed,
        "scope_status": "PARTIAL_SCOPE_NOT_FINAL" if is_partial else "FULL_SIGNOFF_ELIGIBLE",
        "final_signoff_eligible": not is_partial,
        "target": pass1["target"],
        "target_sha256": pass1["target_sha256"],
        "pass2_guards": list(pass2_guards),
        "total_combined_mutants": total_combined,
        "killed_combined": killed_combined,
        "survived_combined": survived_combined,
        "timed_out_combined": timed_out_combined,
        "mutant_subprocess_evals": mutant_evals_combined,
        "control_subprocess_evals": control_evals_combined,
        "total_subprocess_evals": mutant_evals_combined + control_evals_combined,
        "pass2_dedup_skipped": dedup_skipped,
        "elapsed_ms": int(elapsed_ms),
        "pass1": pass1,
        "pass2": pass2,
    }


def build_parser() -> Any:
    parser = make_strict_parser("fast_mutate", "Track S168 exact zero-loss accelerated mutation engine")
    parser.add_argument("script", type=Path, help="Target Python script to mutate")
    parser.add_argument("--test-cmd", required=True, help="Test command (supports {target})")
    parser.add_argument("--work-root", type=Path, default=None, help="Workspace root directory")
    parser.add_argument("--add-cwd", action="store_true", help="Use -s -O -B instead of -I")
    parser.add_argument("--guards", action="extend", nargs="+", default=[], help="Pass-2 explicit guard names")
    parser.add_argument("--max-mutants", type=int, default=0, help="Max mutants (0 = uncapped full signoff)")
    parser.add_argument("--timeout", type=int, default=30, help="Per-mutant timeout seconds")
    parser.add_argument("--workers", type=int, default=1, help="Parallel worker slots (1..32)")
    parser.add_argument("--no-failfast", action="store_true", help="Disable automatic unittest -f injection")
    parser.add_argument("--no-boundaries", action="store_true", help="Skip boundary operator flips (PARTIAL_SCOPE_NOT_FINAL)")
    parser.add_argument("--changed-only", action="store_true", help="Scope to git-diff changed lines (PARTIAL_SCOPE_NOT_FINAL)")
    parser.add_argument("--changed-lines", default=None, help="Explicit changed line ranges e.g. 10-25,40 (PARTIAL_SCOPE_NOT_FINAL)")
    parser.add_argument("--diff-base", default=None, help="Optional git ref base for --changed-only")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    def _run(args: Any) -> dict[str, Any]:
        line_set = parse_line_ranges(args.changed_lines) if args.changed_lines is not None else None
        if args.guards:
            res = run_dual_fast_mutation(
                args.script,
                args.test_cmd,
                pass2_guards=args.guards,
                work_root=args.work_root,
                max_mutants=args.max_mutants,
                timeout=args.timeout,
                include_boundaries=not args.no_boundaries,
                add_cwd=args.add_cwd,
                workers=args.workers,
                failfast=not args.no_failfast,
                changed_only=args.changed_only,
                changed_lines=line_set,
                diff_base=args.diff_base,
            )
            surv_list = res["pass1"]["survivors"] + res["pass2"]["survivors"]
            to_list = res["pass1"]["timeouts"] + res["pass2"]["timeouts"]
        else:
            res = run_fast_mutation_pass(
                args.script,
                args.test_cmd,
                work_root=args.work_root,
                max_mutants=args.max_mutants,
                timeout=args.timeout,
                include_boundaries=not args.no_boundaries,
                add_cwd=args.add_cwd,
                workers=args.workers,
                failfast=not args.no_failfast,
                changed_only=args.changed_only,
                changed_lines=line_set,
                diff_base=args.diff_base,
            )
            surv_list = res["survivors"]
            to_list = res["timeouts"]
        if not res["passed"]:
            summary = [
                {"id": s["id"], "line": s["line"], "kind": s["kind"], "status": s["status"], "original": s["original"], "mutated": s["mutated"]}
                for s in (surv_list + to_list)
            ]
            raise TrustCoreError(res["verdict"], f"mutation verdict={res['verdict']} issues={json.dumps(summary, sort_keys=True, separators=(',', ':'))}")
        return res

    return run_fail_closed_cli(_run, parser_builder=build_parser, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
