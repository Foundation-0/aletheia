#!/usr/bin/env python3
"""
Regression and mutation-hardening tests for refusal-shape discovery and mutation
in `aletheia.mutator`:
  1. `else`-branch refusals (`guard_else_reject` + boundary flips),
  2. `try`-wrapped refusals (`try`/`except`/`else`/`finally` inside `if` AND standalone `except` handlers),
  3. assign-then-return refusal dicts/values (`res = {"passed": False}; return res`) & verdict-key updates,
  4. aliased guards (`chk = require_ok`, `from mod import require_ok as g`, chained & annotated aliases),
  5. `getattr` dispatch (`getattr(mod, "require_ok")(cond, ...)`),
  6. refusal wrappers with preamble log/setup lines before the guard (and `else`-branch / `try`-wrapped wrappers).

Zero external dependencies. Zero bare asserts. Safe across all isolated R4 modes.
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import mutator
from aletheia.strict_io import AletheiaError, write_lf_text


def _run_suite_pair(
    root: Path,
    name: str,
    target_src: str,
    weak_test_src: str,
    strong_test_src: str,
    *,
    extra_files: dict[str, str] | None = None,
) -> tuple[dict, dict]:
    sub = root / name
    sub.mkdir(parents=True, exist_ok=True)
    if extra_files:
        for rel, content in extra_files.items():
            write_lf_text(sub / rel, content)
    tgt = sub / "target_mod.py"
    write_lf_text(tgt, target_src)
    write_lf_text(sub / "test_weak.py", weak_test_src)
    write_lf_text(sub / "test_strong.py", strong_test_src)
    weak = mutator.run_mutation_suite(
        tgt,
        "python3 test_weak.py",
        work_root=sub,
        max_mutants=0,
        add_cwd=True,
    )
    strong = mutator.run_mutation_suite(
        tgt,
        "python3 test_strong.py",
        work_root=sub,
        max_mutants=0,
        add_cwd=True,
    )
    return weak, strong


class TestMutatorRefusalShapes(unittest.TestCase):
    def test_01_else_branch_raise_and_elif_chain(self) -> None:
        src = (
            "def positive_only(x):\n"
            "    if x > 0:\n"
            "        return x\n"
            "    else:\n"
            "        raise ValueError('non-positive')\n"
        )
        _, sites = mutator.discover_mutant_sites(src)
        kinds = {s.kind for s in sites}
        self.assertEqual(kinds, {"guard_else_reject", "boundary_cmp"})

        # `if True: ... else: raise ...` and `if False: raise ...` must not emit no-op guard mutations.
        const_true_src = "def f():\n    if True:\n        return 1\n    else:\n        raise ValueError('unreachable')\n"
        self.assertEqual([s for s in mutator.discover_mutant_sites(const_true_src)[1] if s.kind == "guard_else_reject"], [])
        const_false_src = "def f():\n    if False:\n        raise ValueError('dead')\n"
        self.assertEqual(mutator.discover_mutant_sites(const_false_src)[1], [])

        # `if`/`elif`/`else: raise` mutates ONLY the inner `elif` (never misclassifying `elif` as `else` refusal).
        elif_src = (
            "def classify(x):\n"
            "    if x == 1:\n"
            "        return 'a'\n"
            "    elif x == 2:\n"
            "        return 'b'\n"
            "    else:\n"
            "        raise ValueError(x)\n"
        )
        _, elif_sites = mutator.discover_mutant_sites(elif_src)
        self.assertEqual([(s.lineno, s.kind) for s in elif_sites], [(4, "boundary_cmp"), (4, "guard_else_reject")])

        # Non-refusal `else` produces zero sites.
        ok_else = "def f(x):\n    if x > 0:\n        return 1\n    else:\n        return 2\n"
        self.assertEqual(mutator.discover_mutant_sites(ok_else)[1], [])

        # End-to-end: weak suite (only tests x=1) MUST FAIL; strong suite (tests 1, 0, -1) MUST PASS 100%.
        with tempfile.TemporaryDirectory(prefix="aletheia_t_else_") as td:
            weak, strong = _run_suite_pair(
                Path(td),
                "else_raise",
                src,
                "import target_mod\nif target_mod.positive_only(1) != 1:\n    raise SystemExit(1)\n",
                (
                    "import target_mod\n"
                    "if target_mod.positive_only(1) != 1:\n    raise SystemExit(1)\n"
                    "for bad in (0, -1):\n"
                    "    try:\n        target_mod.positive_only(bad)\n        raise SystemExit(2)\n"
                    "    except ValueError:\n        pass\n"
                ),
            )
            self.assertFalse(weak["passed"])
            self.assertEqual(weak["survived"], 2)
            self.assertTrue(strong["passed"])
            self.assertEqual(strong["killed"], 2)
            self.assertEqual(strong["survived"], 0)

    def test_02_try_wrapped_raises_and_except_handlers(self) -> None:
        # All 4 sub-blocks of `ast.Try` inside `if` (`body`, `handlers`, `orelse`, `finalbody`).
        try_variants = [
            "def f(x):\n    if x < 0:\n        try:\n            raise ValueError(x)\n        finally:\n            pass\n    return x\n",
            "def f(x):\n    if x < 0:\n        try:\n            int('bad')\n        except ValueError:\n            raise RuntimeError(x)\n    return x\n",
            "def f(x):\n    if x < 0:\n        try:\n            pass\n        except ValueError:\n            pass\n        else:\n            raise ValueError(x)\n    return x\n",
            "def f(x):\n    if x < 0:\n        try:\n            pass\n        finally:\n            raise ValueError(x)\n    return x\n",
        ]
        for variant in try_variants:
            _, sites = mutator.discover_mutant_sites(variant)
            self.assertIn("guard_if_reject", {s.kind for s in sites})
            self.assertIn("boundary_cmp", {s.kind for s in sites})

        # Non-refusal `try` inside `if` produces zero sites.
        benign_try = "def f(x):\n    if x < 0:\n        try:\n            return 1\n        except ValueError:\n            return 2\n    return x\n"
        self.assertEqual(mutator.discover_mutant_sites(benign_try)[1], [])

        # Bare `except:` refusal emits `except:` -> `except: pass`.
        bare_exc = "def f(x):\n    try:\n        return int(x)\n    except:\n        raise RuntimeError('bad')\n"
        _, bare_sites = mutator.discover_mutant_sites(bare_exc)
        self.assertEqual(len(bare_sites), 1)
        self.assertEqual(bare_sites[0].kind, "guard_except_reject")
        self.assertEqual(bare_sites[0].original_src, "except:")
        self.assertEqual(bare_sites[0].mutated_src, "except: pass")

        # Standalone `try: return int(s) except ValueError: raise RuntimeError('bad')` end-to-end.
        src_try = (
            "def parse_num(s):\n"
            "    try:\n"
            "        return int(s)\n"
            "    except ValueError:\n"
            "        raise RuntimeError('bad')\n"
        )
        with tempfile.TemporaryDirectory(prefix="aletheia_t_try_") as td:
            weak, strong = _run_suite_pair(
                Path(td),
                "try_except",
                src_try,
                "import target_mod\nif target_mod.parse_num('7') != 7:\n    raise SystemExit(1)\n",
                (
                    "import target_mod\n"
                    "if target_mod.parse_num('7') != 7:\n    raise SystemExit(1)\n"
                    "try:\n    target_mod.parse_num('abc')\n    raise SystemExit(2)\n"
                    "except RuntimeError:\n    pass\n"
                ),
            )
            self.assertFalse(weak["passed"])
            self.assertEqual(weak["survived"], 1)
            self.assertTrue(strong["passed"])
            self.assertEqual(strong["killed"], 1)

    def test_03_assign_then_return_dict_and_verdict_updates(self) -> None:
        # Plain assign-then-return refusal dict.
        src_dict = (
            "def verify(x):\n"
            "    if x < 0:\n"
            "        res = {'passed': False, 'valid': False}\n"
            "        return res\n"
            "    return {'passed': True, 'valid': True}\n"
        )
        # Annotated assign-then-return refusal dict (`ast.AnnAssign`).
        src_ann = (
            "def verify(x):\n"
            "    if x < 0:\n"
            "        res: dict = {'passed': False}\n"
            "        return res\n"
            "    return {'passed': True}\n"
        )
        # Subscript verdict-key update (`res['passed'] = False`).
        src_sub = (
            "def verify(x):\n"
            "    res = {'passed': True}\n"
            "    if x < 0:\n"
            "        res['passed'] = False\n"
            "    return res\n"
        )
        # Refusal tuple (incl. 1-elem), refusal call positional/kwarg False, sys.exit, exit, accumulator,
        # ann-assign preservation, alias-then-return, annotated alias, annotated verdict subscript, `+=` accumulator, `with` raise.
        src_extras = (
            "import sys\n"
            "def f1(x):\n    if x < 0:\n        r = (False, 'neg')\n        return r\n"
            "def f2(x):\n    if x < 0:\n        return dict(ok=False)\n"
            "def f3(x):\n    if x < 0:\n        return bool(False)\n"
            "def f4(x):\n    if x < 0:\n        sys.exit(1)\n"
            "def f5(x):\n    if x < 0:\n        exit(1)\n"
            "def f6(x):\n    findings = []\n    if x < 0:\n        findings.append('neg')\n"
            "def f7(x):\n    if x < 0:\n        return (False,)\n"
            "def f8(x):\n    if x < 0:\n        res = {'passed': False}\n        res: dict\n        return res\n"
            "def f9(x):\n    if x < 0:\n        r1 = {'passed': False}\n        r2 = r1\n        return r2\n"
            "def f10(x):\n    if x < 0:\n        r1 = {'passed': False}\n        r2: dict = r1\n        return r2\n"
            "def f11(x):\n    res = {'passed': True}\n    if x < 0:\n        res['passed']: bool = False\n    return res\n"
            "def f12(x):\n    findings = []\n    if x < 0:\n        findings += ['neg']\n"
            "def f13(x, ctx):\n    if x < 0:\n        with ctx:\n            raise ValueError(x)\n"
            "async def f14(x, ctx):\n    if x < 0:\n        async with ctx:\n            raise ValueError(x)\n"
        )
        for sample in (src_dict, src_ann, src_sub):
            _, sites = mutator.discover_mutant_sites(sample)
            self.assertEqual({s.kind for s in sites}, {"guard_if_reject", "boundary_cmp"})
        _, ext_sites = mutator.discover_mutant_sites(src_extras)
        self.assertEqual(len([s for s in ext_sites if s.kind == "guard_if_reject"]), 14)

        # Negative controls: overwritten refusal variable (plain, annotated, aliased), non-Name AnnAssign, non-verdict/non-Constant subscript,
        # non-Add AugAssign, non-accumulator `+=`, benign `with`, empty & non-refusal tuples, non-refusal calls.
        benign = (
            "def b1(x):\n    if x < 0:\n        res = {'passed': False}\n        res = {'passed': True}\n        return res\n"
            "def b2(x):\n    if x < 0:\n        res: dict = {'passed': False}\n        res: dict = {'passed': True}\n        return res\n"
            "def b3(x, obj):\n    if x < 0:\n        obj.res: dict = {'passed': False}\n        return {'passed': True}\n"
            "def b4(x, k):\n    d = {}\n    if x < 0:\n        d['note'] = False\n        d[0] = False\n        d[k] = False\n        d['passed'] = True\n        d['note']: bool = False\n        d['passed']: bool = True\n    return d\n"
            "def b5(x):\n    if x < 0:\n        t = ()\n        return t\n"
            "def b6(x):\n    if x < 0:\n        other = {'passed': False}\n        good = {'passed': True}\n        return good\n"
            "def b7(x, obj):\n    items = []\n    findings = []\n    if x < 0:\n        items.append('ok')\n        items += ['ok']\n        findings.clear()\n        obj.findings.append('ok')\n        obj.x += 1\n    count_findings = 1\n    if x < 0:\n        count_findings -= 1\n"
            "def b8(x):\n    if x < 0:\n        return (True, 'ok')\n"
            "def b9(x, fn):\n    if x < 0:\n        return fn(x, True, k=x, ok=True)\n"
            "def b10(x):\n    if x < 0:\n        r1 = {'passed': False}\n        r2 = r1\n        r2 = {'passed': True}\n        return r2\n"
            "def b11(x, ctx):\n    if x < 0:\n        with ctx:\n            pass\n"
            "def b12(x, sys, get_sys):\n    if x < 0:\n        'note'\n        sys.getrecursionlimit()\n        get_sys().exit(1)\n"
        )
        self.assertEqual(mutator.discover_mutant_sites(benign)[1], [])

        # End-to-end on assign-then-return dict: weak suite fails, strong suite passes 100%.
        with tempfile.TemporaryDirectory(prefix="aletheia_t_dict_") as td:
            weak, strong = _run_suite_pair(
                Path(td),
                "assign_dict",
                src_dict,
                "import target_mod\nif not target_mod.verify(1)['passed']:\n    raise SystemExit(1)\n",
                (
                    "import target_mod\n"
                    "if not target_mod.verify(0)['passed']:\n    raise SystemExit(1)\n"
                    "if target_mod.verify(-1)['passed']:\n    raise SystemExit(2)\n"
                ),
            )
            self.assertFalse(weak["passed"])
            self.assertEqual(weak["survived"], 2)
            self.assertTrue(strong["passed"])
            self.assertEqual(strong["killed"], 2)

    def test_04_aliased_guards_and_getattr_dispatch(self) -> None:
        # 1. `from ... import require_ok as guard_fn`, local assign alias, chained alias, annotated alias, attr alias, getattr alias.
        src_aliases = (
            "from aletheia.strict_io import require_ok as guard_fn\n"
            "import aletheia.strict_io as sio\n"
            "chk1 = guard_fn\n"
            "chk2 = chk1\n"
            "chk3: object = sio.require_ok\n"
            "chk4 = getattr(sio, 'require_ok')\n"
            "def check_all(x):\n"
            "    guard_fn(x > 0, 'E1', 'e1')\n"
            "    chk2(x > 1, 'E2', 'e2')\n"
            "    chk3(x > 2, 'E3', 'e3')\n"
            "    chk4(x > 3, 'E4', 'e4')\n"
            "    getattr(sio, 'require_ok')(x > 4, 'E5', 'e5')\n"
            "    getattr(sio, 'require_ok', None)(x > 5, 'E6', 'e6')\n"
            "    return x\n"
        )
        _, sites = mutator.discover_mutant_sites(src_aliases)
        req_lines = sorted(s.lineno for s in sites if s.kind == "guard_require_call")
        cmp_lines = sorted(s.lineno for s in sites if s.kind == "boundary_cmp_require")
        self.assertEqual(req_lines, [8, 9, 10, 11, 12, 13])
        self.assertEqual(cmp_lines, [8, 9, 10, 11, 12, 13])

        # Direct helper checks on `_extract_getattr_attr_name` and `_discover_guard_aliases` (unaliased import, non-str attr, attr func).
        self.assertIsNone(mutator._extract_getattr_attr_name(ast.parse("getattr(m, 123)").body[0].value))  # type: ignore[arg-type]
        self.assertIsNone(mutator._extract_getattr_attr_name(ast.parse("obj.getattr(m, 'require_ok')").body[0].value))  # type: ignore[arg-type]
        self.assertEqual(mutator._discover_guard_aliases(ast.parse("from mod import require_ok\n"), {"require_ok": "require"}), {})

        # Non-guard getattr calls, 1-arg getattr, non-str attr name, non-Name AnnAssign, non-guard aliases must produce 0 sites.
        benign_ga = (
            "import math as m\n"
            "from math import sqrt as sq\n"
            "a = sq\n"
            "b: object = m.sqrt\n"
            "c: int\n"
            "def f(x, key, obj):\n"
            "    obj.g: object = m.sqrt\n"
            "    obj.getattr(m, 'require_ok')(x)\n"
            "    getattr(m, 'sqrt')(x)\n"
            "    getattr(m, key)(x)\n"
            "    getattr(m, 123)(x)\n"
            "    getattr(m)(x)\n"
            "    other(m, 'require_ok')(x)\n"
            "    return a(x) + b(x)\n"
        )
        self.assertEqual(mutator.discover_mutant_sites(benign_ga)[1], [])

        # End-to-end on aliased guard + getattr dispatch: weak suite fails, strong suite kills 100%.
        src_e2e = (
            "import aletheia.strict_io as sio\n"
            "from aletheia.strict_io import require_ok as g_alias\n"
            "chk = g_alias\n"
            "def gate(x, y):\n"
            "    chk(x > 0, 'BAD_X', 'x')\n"
            "    getattr(sio, 'require_ok')(y > 0, 'BAD_Y', 'y')\n"
            "    return x + y\n"
        )
        with tempfile.TemporaryDirectory(prefix="aletheia_t_alias_") as td:
            weak, strong = _run_suite_pair(
                Path(td),
                "alias_getattr",
                src_e2e,
                "import sys\nsys.path.insert(0, " + repr(str(ROOT)) + ")\nimport target_mod\nif target_mod.gate(1, 1) != 2:\n    raise SystemExit(1)\n",
                (
                    "import sys\nsys.path.insert(0, " + repr(str(ROOT)) + ")\n"
                    "import target_mod\nfrom aletheia.strict_io import AletheiaError\n"
                    "if target_mod.gate(1, 1) != 2:\n    raise SystemExit(1)\n"
                    "for bx, by in ((0, 1), (-1, 1), (1, 0), (1, -1)):\n"
                    "    try:\n        target_mod.gate(bx, by)\n        raise SystemExit(2)\n"
                    "    except AletheiaError:\n        pass\n"
                ),
            )
            self.assertFalse(weak["passed"])
            self.assertEqual(weak["survived"], 4)
            self.assertTrue(strong["passed"])
            self.assertEqual(strong["killed"], 4)

    def test_05_wrappers_with_log_preamble_else_and_try(self) -> None:
        # Wrappers with: (a) log line before guard, (b) assign + ann-assign + log before guard + trailing return,
        # (c) else-branch raise (`require` & `reject` polarity inversion), (d) try-wrapped raise in wrapper body.
        src_wrappers = (
            "def req_logged(cond, msg):\n"
            "    print('checking', msg)\n"
            "    if not cond:\n"
            "        raise ValueError(msg)\n\n"
            "def req_setup(cond, msg, ctx):\n"
            "    tag = 'err:' + msg\n"
            "    code: str = tag\n"
            "    ctx['last'] = code\n"
            "    ctx['last']: str = code\n"
            "    print(code)\n"
            "    if not cond:\n"
            "        raise ValueError(code)\n"
            "    return True\n\n"
            "def req_else(ok, msg):\n"
            "    print('else check')\n"
            "    if ok:\n"
            "        return True\n"
            "    else:\n"
            "        raise ValueError(msg)\n\n"
            "def rej_else(bad, msg):\n"
            "    if not bad:\n"
            "        return True\n"
            "    else:\n"
            "        raise ValueError(msg)\n\n"
            "def req_try(cond, msg):\n"
            "    if not cond:\n"
            "        try:\n"
            "            print(msg)\n"
            "        finally:\n"
            "            raise ValueError(msg)\n\n"
            "def req_try_h(cond, msg):\n"
            "    if not cond:\n"
            "        try:\n"
            "            int('x')\n"
            "        except ValueError:\n"
            "            raise RuntimeError(msg)\n\n"
            "def req_try_e(cond, msg):\n"
            "    if not cond:\n"
            "        try:\n"
            "            pass\n"
            "        except ValueError:\n"
            "            pass\n"
            "        else:\n"
            "            raise ValueError(msg)\n\n"
            "def req_try_b(cond, msg):\n"
            "    if not cond:\n"
            "        try:\n"
            "            raise ValueError(msg)\n"
            "        finally:\n"
            "            pass\n\n"
            "def req_sys_exit(cond):\n"
            "    import sys\n"
            "    if not cond:\n"
            "        sys.exit(1)\n\n"
            "def req_exit(cond):\n"
            "    if not cond:\n"
            "        exit(1)\n"
        )
        tree = ast.parse(src_wrappers)
        detected = mutator.discover_local_refusal_wrappers(tree)
        self.assertEqual(
            detected,
            {
                "req_logged": "require",
                "req_setup": "require",
                "req_else": "require",
                "rej_else": "reject",
                "req_try": "require",
                "req_try_h": "require",
                "req_try_e": "require",
                "req_try_b": "require",
                "req_exit": "require",
            },
        )
        # `req_sys_exit` has `import sys` (not a preamble Expr/Assign), so skipped cleanly;
        # also test functions that overwrite `cond` param, have both-branch raises, or have >2 stmts after preamble!
        non_wrappers = (
            "def overwrites_param(x):\n    x = bool(x)\n    if not x:\n        raise ValueError()\n"
            "def overwrites_ann(x):\n    x: bool = bool(x)\n    if not x:\n        raise ValueError()\n"
            "def both_raise(x):\n    if x:\n        raise ValueError('a')\n    else:\n        raise ValueError('b')\n"
            "def trailing_stmt(x):\n    if not x:\n        raise ValueError()\n    y = 1\n"
            "def too_many(x):\n    if not x:\n        raise ValueError()\n    print('ok')\n    return True\n"
            "def no_if(x):\n    print(x)\n"
            "def non_hard_try(x):\n    if not x:\n        try:\n            return False\n        except Exception:\n            return False\n"
            "def ok_else_fn(ok):\n    if ok:\n        return 1\n    else:\n        return 2\n"
        )
        self.assertEqual(mutator.discover_local_refusal_wrappers(ast.parse(non_wrappers)), {})

        # End-to-end with a logged wrapper + alias to it: weak suite fails, strong suite passes 100%.
        src_log_e2e = (
            "def check_logged(cond, msg):\n"
            "    print('checking', msg)\n"
            "    if not cond:\n"
            "        raise ValueError(msg)\n\n"
            "def accept(x):\n"
            "    check_logged(x > 0, 'non-positive')\n"
            "    return x\n"
        )
        with tempfile.TemporaryDirectory(prefix="aletheia_t_logw_") as td:
            weak, strong = _run_suite_pair(
                Path(td),
                "logged_wrapper",
                src_log_e2e,
                "import target_mod\nif target_mod.accept(2) != 2:\n    raise SystemExit(1)\n",
                (
                    "import target_mod\n"
                    "if target_mod.accept(2) != 2:\n    raise SystemExit(1)\n"
                    "for bad in (0, -1):\n"
                    "    try:\n        target_mod.accept(bad)\n        raise SystemExit(2)\n"
                    "    except ValueError:\n        pass\n"
                ),
            )
            self.assertFalse(weak["passed"])
            self.assertEqual(weak["local_wrappers_detected"], ["check_logged"])
            self.assertEqual(weak["survived"], 3)
            self.assertTrue(strong["passed"])
            self.assertEqual(strong["killed"], 3)

    def test_06_apply_single_mutation_type_guards_and_selfcheck_getattr(self) -> None:
        # Wrong AST node index type for `guard_else_reject` and `guard_except_reject` must raise MUTANT_NODE_TYPE.
        src = "x = 1\n"
        for kind in ("guard_else_reject", "guard_except_reject"):
            bad_site = mutator.MutantSite(
                mutant_id="M001",
                kind=kind,
                lineno=1,
                col_offset=0,
                node_index=0,
                original_src="x = 1",
                mutated_src="pass",
            )
            with self.assertRaises(AletheiaError) as cm:
                mutator.apply_single_mutation(src, bad_site)
            self.assertEqual(cm.exception.code, "MUTANT_NODE_TYPE")

        # Self-check mode also recognizes top-level `getattr(..., 'check')(cond, ...)` guard calls.
        sc_src = (
            "import sys\n"
            "FAILS = []\n"
            "class Box:\n"
            "    @staticmethod\n"
            "    def check(cond, msg):\n"
            "        if not cond:\n"
            "            FAILS.append(msg)\n"
            "getattr(Box, 'check')(2 + 2 == 4, 'math')\n"
            "if FAILS:\n"
            "    sys.exit(1)\n"
        )
        _, sc_sites = mutator.discover_mutant_sites(sc_src, self_check_mode=True)
        self.assertIn("guard_selfcheck_negate", {s.kind for s in sc_sites})

        # Self-check boundary checks: non-guard call & 0-arg guard call do NOT trigger top-level guard suppression,
        # while a 1-arg guard call DOES trigger `guard_selfcheck_negate` and suppresses `if FAILS: sys.exit(1)`.
        sc_non_guard = "import sys\nFAILS = []\nprint('ok')\nif FAILS:\n    sys.exit(1)\n"
        self.assertEqual([s.kind for s in mutator.discover_mutant_sites(sc_non_guard, self_check_mode=True)[1]], ["guard_if_reject"])
        sc_zero_arg = "import sys\nFAILS = []\ncheck()\nif FAILS:\n    sys.exit(1)\n"
        self.assertEqual([s.kind for s in mutator.discover_mutant_sites(sc_zero_arg, self_check_mode=True)[1]], ["guard_if_reject"])
        sc_one_arg = "\"\"\"doc\"\"\"\nimport sys\nFAILS = []\ncheck(2 + 2 == 4)\nif FAILS:\n    sys.exit(1)\n"
        sc_one_kinds = {s.kind for s in mutator.discover_mutant_sites(sc_one_arg, self_check_mode=True)[1]}
        self.assertIn("guard_selfcheck_negate", sc_one_kinds)
        self.assertNotIn("guard_if_reject", sc_one_kinds)

    def test_07_scoped_and_reassignment_safe_guard_aliases(self) -> None:
        # 1. Reassigned aliases (in function or at module level) MUST NOT emit false-positive mutations.
        reassigned_src = (
            "def benign(v):\n    return v\n"
            "m_chk = require_ok\n"
            "m_chk = benign\n"
            "def f_mod(x):\n    return m_chk(x > 0)\n"
            "def f_local(x):\n    chk = require_ok\n    chk = benign\n    return chk(x > 0)\n"
            "def f_const(x):\n    chk = require_ok\n    chk = 42\n    return chk(x > 0)\n"
            "def f_chain_poison(x):\n    chk1 = require_ok\n    chk2 = chk1\n    chk1 = benign\n    return chk2(x > 0)\n"
            "def f_ann_poison(x):\n    chk: object = require_ok\n    chk: object = benign\n    return chk(x > 0)\n"
            "def f_ann_nonname(x, box):\n    box.chk: object = require_ok\n    return box.chk(x > 0)\n"
            "def f_rebind_kinds(x, items, ctx):\n"
            "    a = require_ok\n    a += benign\n    a(x > 0)\n"
            "    b = require_ok\n    print(b := benign)\n    b(x > 0)\n"
            "    c = require_ok\n    del c\n    c(x > 0)\n"
            "    d = require_ok\n    for d in items:\n        d(x > 0)\n"
            "    e = require_ok\n    with ctx as e:\n        e(x > 0)\n"
            "    f = require_ok\n    try:\n        pass\n    except Exception as f:\n        f(x > 0)\n"
            "    g = require_ok\n    g, _ = require_ok, 1\n    g(x > 0)\n"
            "    h = require_ok\n    from mod import other as h\n    h(x > 0)\n"
            "    k = require_ok\n    import math as k\n    k(x > 0)\n"
            "    import check\n    check(x > 0)\n"
            "    m = require_ok\n    def m(v):\n        return v\n    m(x > 0)\n"
            "    items.g = require_ok\n"
            "    with ctx:\n        pass\n"
            "    try:\n        pass\n    except Exception:\n        pass\n"
            "    del items[0]\n"
        )
        self.assertEqual(mutator.discover_mutant_sites(reassigned_src)[1], [])

        # 2. Conflicting polarities in SEPARATE functions stay strictly scoped (zero silent polarity inversion!),
        #    while conflicting polarities in the SAME scope are invalidated cleanly.
        polarity_src = (
            "def reject_bad(bad):\n"
            "    if bad:\n"
            "        raise ValueError('bad')\n\n"
            "def fn1(x):\n"
            "    g = reject_bad\n"
            "    g(x < 0)\n\n"
            "def fn2(x):\n"
            "    g = require_ok\n"
            "    g(x > 0, 'E', 'e')\n\n"
            "def fn_conflict(x):\n"
            "    g = reject_bad\n"
            "    g = require_ok\n"
            "    g(x > 0)\n\n"
            "def fn_imp_conflict(x):\n"
            "    from aletheia.strict_io import require_ok as g\n"
            "    g = reject_bad\n"
            "    g(x > 0)\n"
        )
        _, pol_sites = mutator.discover_mutant_sites(polarity_src)
        call_sites = [(s.lineno, s.kind, s.mutated_src) for s in pol_sites if s.kind in ("guard_require_call", "guard_reject_call")]
        self.assertEqual(
            call_sites,
            [
                (7, "guard_reject_call", "g(False, ...)"),
                (11, "guard_require_call", "g(True, ...)"),
            ],
        )

        # 3. Cross-function / bool-field / parameter shadowing / lambda isolation.
        leak_src = (
            "import aletheia.strict_io as sio\n"
            "mod_chk = require_ok\n"
            "def fn1(obj, x):\n"
            "    ok = obj.check\n"
            "    ok2 = getattr(obj, 'check')\n"
            "    ok3 = (obj()).check\n"
            "    chk = require_ok\n"
            "    chk(x > 0, 'E', 'e')\n"
            "    return ok(x) or ok2(x) or ok3(x)\n"
            "def fn2(ok, chk, x):\n"
            "    return ok(x) or chk(x)\n"
            "def fn_shadow_mod(mod_chk, x):\n"
            "    return mod_chk(x)\n"
            "def fn_shadow_var(*mod_chk, **other):\n"
            "    return mod_chk(1) or other(1)\n"
            "def fn_shadow_kw(**mod_chk):\n"
            "    return mod_chk(1)\n"
            "def fn_shadow_ns(sio, x):\n"
            "    loc = sio.require_ok\n"
            "    return loc(x)\n"
            "def fn_lambdas(x):\n"
            "    f_shadow = lambda mod_chk: mod_chk(x > 0)\n"
            "    f_use = lambda v: mod_chk(v > 0, 'E', 'e')\n"
            "    return f_shadow, f_use\n"
        )
        _, leak_sites = mutator.discover_mutant_sites(leak_src)
        leak_calls = [(s.lineno, s.kind, s.original_src) for s in leak_sites if s.kind in ("guard_require_call", "guard_reject_call")]
        self.assertEqual(
            leak_calls,
            [
                (8, "guard_require_call", "chk(x > 0, ...)"),
                (23, "guard_require_call", "mod_chk(v > 0, ...)"),
            ],
        )

        # 4. Valid namespace aliases: unaliased `import`, unaliased & aliased `from ... import`, `class` namespace,
        #    unaliased guard `from ... import require_ok`, and value-less annotation preserving an alias.
        ns_src = (
            "import aletheia\n"
            "from aletheia import strict_io\n"
            "from aletheia import strict_io as sio2\n"
            "from aletheia.strict_io import require_ok\n"
            "class Box:\n"
            "    def run(self, x):\n"
            "        c_cls = Box.check\n"
            "        c_cls(x > 0, 'E')\n"
            "c1 = aletheia.strict_io.require_ok\n"
            "c2 = strict_io.require_ok\n"
            "c3 = sio2.require_ok\n"
            "c4 = require_ok\n"
            "c4: object\n"
            "def use_all(x):\n"
            "    c1(x > 1, 'E1', 'e1')\n"
            "    c2(x > 2, 'E2', 'e2')\n"
            "    c3(x > 3, 'E3', 'e3')\n"
            "    c4(x > 4, 'E4', 'e4')\n"
            "    require_ok(x > 5, 'E5', 'e5')\n"
        )
        _, ns_sites = mutator.discover_mutant_sites(ns_src)
        ns_lines = sorted(s.lineno for s in ns_sites if s.kind == "guard_require_call")
        self.assertEqual(ns_lines, [8, 15, 16, 17, 18, 19])

        # Module-level non-guard import / non-wrapper def shadows an outer/built-in name cleanly.
        shadow_top = (
            "from other_mod import benign\n"
            "def check(x):\n"
            "    return x + 1\n"
            "def caller(x):\n"
            "    return benign(x)\n"
        )
        self.assertEqual(mutator.discover_mutant_sites(shadow_top)[1], [])

        # Explicit `--guards` callback parameters (both def and lambda) remain mutable.
        cb_src = "def f(x, cb):\n    cb(x > 0, 'neg')\n    return lambda cb: cb(x > 1, 'neg2')\n"
        _, cb_sites = mutator.discover_mutant_sites(cb_src, extra_guards=("cb",))
        self.assertEqual(len([s for s in cb_sites if s.kind == "guard_require_call"]), 2)

    def test_08_wrapper_preamble_and_non_shadowing_scope(self) -> None:
        # 1. Tuple-unpacking and walrus parameter reassignments MUST reject wrapper classification,
        #    while reading `cond` in a preamble (`print(cond)`) MUST still be accepted.
        preamble_src = (
            "def invert_tuple(cond, msg):\n"
            "    cond, tag = not cond, msg\n"
            "    if not cond:\n"
            "        raise ValueError(tag)\n\n"
            "def invert_walrus_expr(cond, msg):\n"
            "    print(cond := not cond)\n"
            "    if not cond:\n"
            "        raise ValueError(msg)\n\n"
            "def invert_walrus_assign(cond, msg):\n"
            "    tag = (cond := not cond)\n"
            "    if not cond:\n"
            "        raise ValueError(msg)\n\n"
            "def req_log_cond(cond, msg):\n"
            "    print(cond, msg)\n"
            "    if not cond:\n"
            "        raise ValueError(msg)\n"
        )
        self.assertEqual(mutator.discover_local_refusal_wrappers(ast.parse(preamble_src)), {"req_log_cond": "require"})

        # 2. Nested `def` MUST NOT hijack unrelated top-level functions OR overwrite top-level wrapper polarity.
        nested_src = (
            "def helper(n):\n"
            "    return n + 1\n\n"
            "def gate(bad):\n"
            "    if bad:\n"
            "        raise ValueError('bad')\n\n"
            "def outer(x):\n"
            "    def helper(cond):\n"
            "        if not cond:\n"
            "            raise ValueError('nested')\n"
            "    def gate(ok):\n"
            "        if not ok:\n"
            "            raise ValueError('nested')\n"
            "    gate(x > 0)\n"
            "    return helper(x > 0)\n\n"
            "def caller(x):\n"
            "    gate(x < 0)\n"
            "    return helper(x)\n"
        )
        tree_n = ast.parse(nested_src)
        self.assertEqual(mutator.discover_local_refusal_wrappers(tree_n), {"gate": "reject"})
        _, nested_sites = mutator.discover_mutant_sites(nested_src)
        nested_calls = [(s.lineno, s.kind, s.original_src, s.mutated_src) for s in nested_sites if s.kind in ("guard_require_call", "guard_reject_call")]
        self.assertEqual(nested_calls, [(19, "guard_reject_call", "gate(x < 0, ...)", "gate(False, ...)")])

        # 3. Direct ClassDef wrapper methods, async top-level wrappers, top-level precedence over class methods,
        #    conflicting class-method polarities dropped, and module-level redefinition drops stale wrapper.
        scope_src = (
            "class Validator:\n"
            "    def must_ok(self, cond):\n"
            "        if not cond:\n"
            "            raise ValueError('v')\n"
            "    def helper(self, cond):\n"
            "        if not cond:\n"
            "            raise ValueError('h')\n"
            "    def conflict(self, cond):\n"
            "        if not cond:\n"
            "            raise ValueError('a')\n"
            "    def non_wrap(self, x):\n"
            "        return x\n"
            "    def only_self(self):\n"
            "        return 1\n"
            "    X = 1\n\n"
            "class OtherValidator:\n"
            "    def conflict(self, bad):\n"
            "        if bad:\n"
            "            raise ValueError('b')\n\n"
            "def non_param_else(x):\n"
            "    if x > 0:\n"
            "        return 1\n"
            "    else:\n"
            "        raise ValueError('bad')\n\n"
            "def helper(n):\n"
            "    return n + 1\n\n"
            "async def async_req(cond):\n"
            "    if not cond:\n"
            "        raise ValueError('a')\n\n"
            "def redef(bad):\n"
            "    if bad:\n"
            "        raise ValueError('r')\n\n"
            "def redef(n):\n"
            "    return n\n"
        )
        self.assertEqual(
            mutator.discover_local_refusal_wrappers(ast.parse(scope_src)),
            {"must_ok": "require", "async_req": "require"},
        )

    def test_09_nested_lambda_class_body_and_header_scopes(self) -> None:
        # 1. Nested lambda shadowing (both alias and built-in guard), lambda defaults in outer scope,
        #    and positive control for unshadowed nested lambda.
        nested_lambda_neg = (
            "def benign(v):\n    return v\n"
            "chk = require_ok\n"
            "def f_shadow_alias():\n"
            "    chk = require_ok\n"
            "    return lambda x: (lambda chk: chk(x > 0))(benign)\n"
            "f_shadow_builtin = lambda x: (lambda require_ok: require_ok(x > 0))(benign)\n"
            "def f_shadow_kw_default():\n"
            "    chk = benign\n"
            "    return lambda *, a=chk(1 > 0): a\n"
        )
        self.assertEqual(mutator.discover_mutant_sites(nested_lambda_neg)[1], [])

        nested_lambda_pos = (
            "def f_pos():\n"
            "    chk = require_ok\n"
            "    g1 = lambda x: (lambda y: chk(x > y, 'E', 'e'))(0)\n"
            "    g2 = lambda chk=chk(1 > 0, 'E', 'e'): chk(2 > 0)\n"
            "    return g1, g2\n"
        )
        _, lam_pos_sites = mutator.discover_mutant_sites(nested_lambda_pos)
        lam_pos_calls = [(s.lineno, s.original_src) for s in lam_pos_sites if s.kind == "guard_require_call"]
        self.assertEqual(
            lam_pos_calls,
            [
                (3, "chk(x > y, ...)"),
                (4, "chk(1 > 0, ...)"),
            ],
        )

        # 2. ClassDef body rebinding (alias & built-in guard) suppresses class-body & method-header calls,
        #    while methods still inherit the enclosing non-class LEGB scope; class headers evaluate in enclosing scope.
        cls_neg = (
            "def benign(v):\n    return v\n"
            "chk = require_ok\n"
            "class C1:\n"
            "    chk = benign\n"
            "    res = chk(1 > 0)\n"
            "class C2:\n"
            "    require_ok = benign\n"
            "    res = require_ok(1 > 0)\n"
            "def outer_cls():\n"
            "    chk = benign\n"
            "    @chk(1 > 0)\n"
            "    class C3(chk(2 > 0), k=chk(3 > 0)):\n"
            "        def m(self, v):\n"
            "            return chk(v > 0)\n"
        )
        self.assertEqual(mutator.discover_mutant_sites(cls_neg)[1], [])

        cls_legb_pos = (
            "def benign(v):\n    return v\n"
            "chk = require_ok\n"
            "class C:\n"
            "    chk = benign\n"
            "    loc = require_ok\n"
            "    res_b = chk(1 > 0)\n"
            "    res_g = loc(2 > 0, 'E', 'e')\n"
            "    def m(self, x=chk(3 > 0)):\n"
            "        chk(x > 0, 'E', 'e')\n"
            "        return loc(x > 1)\n"
        )
        _, cls_pos_sites = mutator.discover_mutant_sites(cls_legb_pos)
        cls_pos_calls = [(s.lineno, s.original_src) for s in cls_pos_sites if s.kind == "guard_require_call"]
        self.assertEqual(
            cls_pos_calls,
            [
                (8, "loc(2 > 0, ...)"),
                (10, "chk(x > 0, ...)"),
            ],
        )

        # 3. Enclosing-scope FunctionDef/AsyncFunctionDef headers (decorators, defaults, kw_defaults, returns, annotations).
        hdr_neg = (
            "def benign(v):\n    return v\n"
            "chk = require_ok\n"
            "def outer():\n"
            "    chk = benign\n"
            "    @chk(1 > 0)\n"
            "    def inner(x: chk(2 > 0) = chk(3 > 0), *a: chk(4 > 0), y=chk(5 > 0), **kw: chk(6 > 0)) -> chk(7 > 0):\n"
            "        return x\n"
            "    @chk(8 > 0)\n"
            "    async def ainner(z=chk(9 > 0)):\n"
            "        return z\n"
            "    return inner, ainner\n"
        )
        self.assertEqual(mutator.discover_mutant_sites(hdr_neg)[1], [])

        hdr_pos = (
            "def outer():\n"
            "    chk = require_ok\n"
            "    @chk(1 > 0, 'E1', 'e1')\n"
            "    def inner(x: chk(2 > 0, 'E2', 'e2') = chk(3 > 0, 'E3', 'e3'), *a: chk(4 > 0, 'E4', 'e4'), y=chk(5 > 0, 'E5', 'e5')) -> chk(6 > 0, 'E6', 'e6'):\n"
            "        return x, y\n"
            "    return inner\n"
        )
        _, hdr_pos_sites = mutator.discover_mutant_sites(hdr_pos)
        hdr_pos_calls = [(s.lineno, s.original_src) for s in hdr_pos_sites if s.kind == "guard_require_call"]
        self.assertEqual(
            hdr_pos_calls,
            [
                (3, "chk(1 > 0, ...)"),
                (4, "chk(2 > 0, ...)"),
                (4, "chk(3 > 0, ...)"),
                (4, "chk(4 > 0, ...)"),
                (4, "chk(5 > 0, ...)"),
                (4, "chk(6 > 0, ...)"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
