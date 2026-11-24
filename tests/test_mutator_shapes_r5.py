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
        # Refusal tuple (incl. 1-elem), refusal call positional/kwarg False, sys.exit, exit, accumulator, ann-assign preservation.
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
        )
        for sample in (src_dict, src_ann, src_sub):
            _, sites = mutator.discover_mutant_sites(sample)
            self.assertEqual({s.kind for s in sites}, {"guard_if_reject", "boundary_cmp"})
        _, ext_sites = mutator.discover_mutant_sites(src_extras)
        self.assertEqual(len([s for s in ext_sites if s.kind == "guard_if_reject"]), 8)

        # Negative controls: overwritten refusal variable (plain & annotated), non-Name AnnAssign, non-verdict/non-Constant subscript,
        # empty & non-refusal tuples, non-refusal calls with Name/True args & kwargs.
        benign = (
            "def b1(x):\n    if x < 0:\n        res = {'passed': False}\n        res = {'passed': True}\n        return res\n"
            "def b2(x):\n    if x < 0:\n        res: dict = {'passed': False}\n        res: dict = {'passed': True}\n        return res\n"
            "def b3(x, obj):\n    if x < 0:\n        obj.res: dict = {'passed': False}\n        return {'passed': True}\n"
            "def b4(x, k):\n    d = {}\n    if x < 0:\n        d['note'] = False\n        d[0] = False\n        d[k] = False\n        d['passed'] = True\n    return d\n"
            "def b5(x):\n    if x < 0:\n        t = ()\n        return t\n"
            "def b6(x):\n    if x < 0:\n        other = {'passed': False}\n        good = {'passed': True}\n        return good\n"
            "def b7(x):\n    items = []\n    if x < 0:\n        items.append('ok')\n"
            "def b8(x):\n    if x < 0:\n        return (True, 'ok')\n"
            "def b9(x, fn):\n    if x < 0:\n        return fn(x, True, k=x, ok=True)\n"
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


if __name__ == "__main__":
    unittest.main()
