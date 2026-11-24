#!/usr/bin/env python3
"""
Regression and mutation-hardening tests for bounded depth & ASCII digits in
`aletheia.calculus`, strict integer board `seq` validation in `aletheia.diagnose`,
and full structural validation of `SYM-2P/2.0-rcp` wire packets in `aletheia.mde`.

Zero external dependencies. Zero bare asserts. Safe across all isolated R4 modes.
"""
from __future__ import annotations

import enum
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import calculus, cli, diagnose, mde
from aletheia.scaffold import init_workspace
from aletheia.strict_io import AletheiaError, parse_strict_json_text, write_lf_text


class _Color(enum.IntEnum):
    ONE = 1


class _SubInt(int):
    pass


class _SubStr(str):
    pass


class _LyingStr(str):
    def split(self, *args: object, **kwargs: object) -> list[str]:
        return ["1", "2"]


class _SubFrac(Fraction):
    pass


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(argv)
    return rc, out.getvalue(), err.getvalue()


def _forge_sym2_line(fields: list[str]) -> str:
    bare = "|".join(fields)
    chk = hashlib.sha256(bare.encode("utf-8")).hexdigest()[:16]
    return f"{bare}|{chk}"


def _valid_sym2_fields() -> list[str]:
    return [
        "2",
        "a205",
        "ch1",
        "3",
        "1",
        "5",
        "4",
        "99",
        "96",
        "(10 audit/002 (20 n2 (1 420)))(12 (22 check_003 0 1))",
        "1",
        "f01:2",
        "600",
    ]


def _make_healthy_expedition(root: Path) -> Path:
    ws = root / "exp"
    init_workspace(ws, domain="math")
    write_lf_text(
        ws / "cartography" / "frontier_portals.md",
        "# Frontier Portals\n\n"
        "## Portal 1 — Exact Operator\n"
        "Exact identity `x = y` proved in `probes/math/check.py`.\n"
        "Elevated obstruction into theorem branch.\n\n"
        "## Portal 2 — Companion Operator\n"
        "Exact identity `a -> b`.\n",
    )
    return ws


class TestCalculusDiagnoseMdeHardening(unittest.TestCase):
    def test_01_calculus_depth_bounds_and_no_recursion_error(self) -> None:
        # Exact boundary MAX_EXPR_DEPTH passes; MAX_EXPR_DEPTH + 1 and extreme depths fail closed.
        dmax = calculus.MAX_EXPR_DEPTH
        ok_parens = "(" * dmax + "1" + ")" * dmax
        res_ok = calculus.eval_calculus_expression(ok_parens, env={})
        self.assertEqual(res_ok["value"], "1/1")

        # Sibling nested groups prove depth counter decrements after exiting each group.
        sib_parens = "(" * 40 + "1" + ")" * 40 + "+" + "(" * 40 + "2" + ")" * 40
        self.assertEqual(calculus.eval_calculus_expression(sib_parens, env={})["value"], "3/1")

        # Exact boundary unary negation and sibling unary negation.
        ok_neg = "-" * dmax + "1"
        self.assertEqual(calculus.eval_calculus_expression(ok_neg, env={})["value"], "1/1")
        sib_neg = "-" * 40 + "1 + " + "-" * 40 + "2"
        self.assertEqual(calculus.eval_calculus_expression(sib_neg, env={})["value"], "3/1")

        # Exact boundary flat left-associative binary chain (depth = dmax passes, dmax + 1 fails in eval_ast).
        ok_add = "1" + "+1" * dmax
        self.assertEqual(calculus.eval_calculus_expression(ok_add, env={})["value"], f"{dmax + 1}/1")

        for deep_expr in (
            "(" * (dmax + 1) + "1" + ")" * (dmax + 1),
            "(" * 500 + "1" + ")" * 500,
            "(" * 2000 + "1" + ")" * 2000,
            "-" * (dmax + 1) + "1",
            "-" * 1200 + "1",
            "1" + "+1" * (dmax + 1),
            "1" + "+1" * 1200,
        ):
            with self.assertRaises(calculus.CalculusError) as cm:
                calculus.eval_calculus_expression(deep_expr, env={})
            self.assertEqual(cm.exception.code, "EXPR_DEPTH_EXCEEDED")

        # CLI must return rc=2 with structured JSON error on deep inputs (never raw RecursionError).
        for cli_deep in ("(" * 500 + "1" + ")" * 500, "1" + "+1" * 1200):
            rc, out, _ = _run_cli(["calculus", "--eval", cli_deep, "--json"])
            self.assertEqual(rc, 2)
            payload = parse_strict_json_text(out, allow_float=False)
            self.assertEqual(payload["status"], "ERROR")
            self.assertEqual(payload["code"], "EXPR_DEPTH_EXCEEDED")

        # Parser prefix glyph depth, tuple/CALL parsing, sibling decrement, and max_depth validation.
        self.assertEqual(calculus.eval_calculus_expression("(1, 2)", env={})["value"], ["1/1", "2/1"])
        self.assertEqual(calculus.Parser(calculus.tokenize("(1)"), max_depth=1).parse(), ("NUM", Fraction(1, 1)))
        self.assertEqual(
            calculus.Parser(calculus.tokenize("f(1, 2)"), max_depth=1).parse(),
            ("CALL", "f", (("NUM", Fraction(1, 1)), ("NUM", Fraction(2, 1)))),
        )
        self.assertIsNotNone(calculus.Parser(calculus.tokenize("\u29ba \u29ba M"), max_depth=2).parse())
        self.assertIsNotNone(calculus.Parser(calculus.tokenize("\u29ba M + \u29ba M"), max_depth=1).parse())
        with self.assertRaises(calculus.CalculusError) as cm_u:
            calculus.Parser(calculus.tokenize("\u29ba \u29ba \u29ba M"), max_depth=2).parse()
        self.assertEqual(cm_u.exception.code, "EXPR_DEPTH_EXCEEDED")

        self.assertIsNotNone(calculus.Parser(calculus.tokenize("rk(rk(M))"), max_depth=2).parse())
        self.assertIsNotNone(calculus.Parser(calculus.tokenize("rk(M) + rk(M)"), max_depth=1).parse())
        with self.assertRaises(calculus.CalculusError) as cm_c:
            calculus.Parser(calculus.tokenize("rk(rk(rk(M)))"), max_depth=2).parse()
        self.assertEqual(cm_c.exception.code, "EXPR_DEPTH_EXCEEDED")

        for bad_md in (0, -1, True, "2", _SubInt(2), _Color.ONE):
            with self.assertRaises(calculus.CalculusError) as cm_md:
                calculus.Parser(calculus.tokenize("1"), max_depth=bad_md)  # type: ignore[arg-type]
            self.assertEqual(cm_md.exception.code, "INVALID_MAX_DEPTH")
            with self.assertRaises(calculus.CalculusError) as cm_em:
                calculus.eval_ast(("NUM", Fraction(1, 1)), {}, max_depth=bad_md)  # type: ignore[arg-type]
            self.assertEqual(cm_em.exception.code, "INVALID_MAX_DEPTH")
            with self.assertRaises(calculus.CalculusError) as cm_sm:
                calculus.serialize_calculus_value(Fraction(1, 1), max_depth=bad_md)  # type: ignore[arg-type]
            self.assertEqual(cm_sm.exception.code, "INVALID_MAX_DEPTH")
        self.assertEqual(calculus.eval_ast(("NUM", Fraction(1, 1)), {}, max_depth=1), Fraction(1, 1))
        self.assertEqual(calculus.eval_ast(("NUM", Fraction(1, 1)), {}, max_depth=2), Fraction(1, 1))
        self.assertEqual(calculus.serialize_calculus_value(Fraction(1, 1), max_depth=1), ("rational", "1/1"))
        self.assertEqual(calculus.serialize_calculus_value(Fraction(1, 1), max_depth=2), ("rational", "1/1"))
        self.assertTrue(calculus.is_exact_int(0))
        for bad_i in (True, False, _SubInt(1), _Color.ONE, "1"):
            self.assertFalse(calculus.is_exact_int(bad_i))

        # Direct deep AST and deep serialized tuple depth guards.
        self.assertEqual(calculus.serialize_calculus_value(()), ("tuple", []))
        self.assertEqual(calculus.serialize_calculus_value(((Fraction(1, 1),),)), ("qmat", [["1/1"]]))
        self.assertEqual(
            calculus.serialize_calculus_value(((Fraction(1, 1),), Fraction(2, 1))),
            ("tuple", [["1/1"], "2/1"]),
        )
        self.assertEqual(
            calculus.serialize_calculus_value((((Fraction(1, 1),),),)),
            ("tuple", [[["1/1"]]]),
        )
        deep_tuple: object = Fraction(1, 1)
        for _ in range(dmax):
            deep_tuple = (Fraction(1, 1), deep_tuple)
        vt, _ = calculus.serialize_calculus_value(deep_tuple)
        self.assertEqual(vt, "tuple")
        with self.assertRaises(calculus.CalculusError) as cm_s:
            calculus.serialize_calculus_value((Fraction(1, 1), deep_tuple))
        self.assertEqual(cm_s.exception.code, "VALUE_DEPTH_EXCEEDED")

    def test_02_calculus_ascii_only_digits_and_literal_bounds(self) -> None:
        import ast as py_ast

        # Confirm zero `.isdigit()` calls remain in aletheia/calculus.py.
        src = (ROOT / "aletheia" / "calculus.py").read_text(encoding="utf-8")
        tree = py_ast.parse(src, filename="aletheia/calculus.py")
        isdigit_lines = [
            n.lineno
            for n in py_ast.walk(tree)
            if isinstance(n, py_ast.Call)
            and isinstance(n.func, py_ast.Attribute)
            and n.func.attr == "isdigit"
        ]
        self.assertEqual(isdigit_lines, [])

        # ASCII digit boundaries and valid rational literals pass.
        self.assertEqual(calculus.eval_calculus_expression("0", env={})["value"], "0/1")
        self.assertEqual(calculus.eval_calculus_expression("9", env={})["value"], "9/1")
        self.assertEqual(calculus.eval_calculus_expression("0/9 + 1/2", env={})["value"], "1/2")
        self.assertEqual(calculus.eval_calculus_expression("90/10", env={})["value"], "9/1")

        # Non-ASCII digits (Arabic-Indic, fullwidth, superscript, subscript, Devanagari) and malformed slashes fail with LEX_ERR.
        for bad_num in (
            "\u0662",
            "\uff12",
            "\u00b2",
            "\u2082",
            "\u0968",
            "1/\u00b2",
            "1/\u0662",
            "\u0662/\u0663",
            "1/",
            "1/a",
        ):
            with self.assertRaises(calculus.CalculusError) as cm:
                calculus.eval_calculus_expression(bad_num, env={})
            self.assertEqual(cm.exception.code, "LEX_ERR", f"unexpected code for {bad_num!r}")

        rc, out, _ = _run_cli(["calculus", "--eval", "\u00b2", "--json"])
        self.assertEqual(rc, 2)
        self.assertEqual(parse_strict_json_text(out, allow_float=False)["code"], "LEX_ERR")

        # Zero denominator and integer/rational digit limits fail closed cleanly.
        with self.assertRaises(calculus.CalculusError) as cm_z:
            calculus.eval_calculus_expression("1/0", env={})
        self.assertEqual(cm_z.exception.code, "ZERO_DENOMINATOR")

        max_d = calculus.MAX_INT_DIGITS
        nines = "9" * max_d
        self.assertEqual(calculus.eval_calculus_expression(nines, env={})["value"], f"{nines}/1")
        self.assertEqual(calculus.eval_calculus_expression(f"{nines}/{nines}", env={})["value"], "1/1")
        for huge in ("9" * (max_d + 1), "9" * 5000, f"{'9' * (max_d + 1)}/1", f"1/{'9' * (max_d + 1)}"):
            with self.assertRaises(calculus.CalculusError) as cm_l:
                calculus.eval_calculus_expression(huge, env={})
            self.assertEqual(cm_l.exception.code, "INT_LITERAL_TOO_LONG")

        # Strict str checks reject subclasses and custom .split() overrides in eval/tokenize/_parse_rational_literal.
        for bad_expr in ("", "   ", _SubStr("1"), _LyingStr("1/0"), 123, None):
            with self.assertRaises(calculus.CalculusError) as cm_e:
                calculus.eval_calculus_expression(bad_expr, env={})  # type: ignore[arg-type]
            self.assertEqual(cm_e.exception.code, "EMPTY_EXPRESSION")
        for bad_tok in (_SubStr("1"), _LyingStr("1/0"), 123):
            with self.assertRaises(calculus.CalculusError) as cm_t:
                calculus.tokenize(bad_tok)  # type: ignore[arg-type]
            self.assertEqual(cm_t.exception.code, "INVALID_EXPRESSION_TYPE")
            with self.assertRaises(calculus.CalculusError) as cm_r:
                calculus._parse_rational_literal(bad_tok)  # type: ignore[arg-type]
            self.assertEqual(cm_r.exception.code, "INVALID_LITERAL_TYPE")

        # Bounded serialization across frac_str, exact int, and InertiaTriple (exact bit boundary passes; >14000-bit fails closed).
        max_bits = calculus.MAX_SERIALIZED_INT_BITS
        max_val = (1 << max_bits) - 1
        over_val = 1 << max_bits
        self.assertEqual(calculus.frac_str(Fraction(max_val, 1)), f"{max_val}/1")
        self.assertEqual(calculus.frac_str(Fraction(1, max_val)), f"1/{max_val}")
        self.assertEqual(calculus.serialize_calculus_value(max_val), ("int", max_val))
        self.assertEqual(
            calculus.serialize_calculus_value(calculus.InertiaTriple(max_val, 0, -max_val)),
            ("inertia_triple", [max_val, 0, -max_val]),
        )
        for bad_frac in (_SubFrac(1, 2), 1, "1/2"):
            with self.assertRaises(calculus.CalculusError) as cm_bf:
                calculus.frac_str(bad_frac)  # type: ignore[arg-type]
            self.assertEqual(cm_bf.exception.code, "INVALID_FRACTION_TYPE")
        with self.assertRaises(calculus.CalculusError) as cm_sf:
            calculus.serialize_calculus_value(_SubFrac(1, 2))
        self.assertEqual(cm_sf.exception.code, "INVALID_FRACTION_TYPE")
        for bad_ser_int in (True, _SubInt(1), _Color.ONE, "1"):
            with self.assertRaises(calculus.CalculusError) as cm_bi:
                calculus._require_serializable_int(bad_ser_int)
            self.assertEqual(cm_bi.exception.code, "INVALID_INT_TYPE")
        for huge_frac in (Fraction(over_val, 1), Fraction(1, over_val)):
            with self.assertRaises(calculus.CalculusError) as cm_fs:
                calculus.frac_str(huge_frac)
            self.assertEqual(cm_fs.exception.code, "VALUE_SERIALIZATION_LIMIT")
        for huge_val in (
            over_val,
            -over_val,
            calculus.InertiaTriple(over_val, 0, 0),
            calculus.InertiaTriple(0, over_val, 0),
            calculus.InertiaTriple(0, 0, -over_val),
        ):
            with self.assertRaises(calculus.CalculusError) as cm_hv:
                calculus.serialize_calculus_value(huge_val)
            self.assertEqual(cm_hv.exception.code, "VALUE_SERIALIZATION_LIMIT")
        with self.assertRaises(calculus.CalculusError) as cm_env:
            calculus.eval_calculus_expression("big", env={"big": 1 << 15000})
        self.assertEqual(cm_env.exception.code, "VALUE_SERIALIZATION_LIMIT")

        prod_5000 = "*".join([f"({nines})"] * 5)
        for huge_expr in (
            prod_5000,
            "*".join([f"(1/{nines})"] * 5),
            f"({prod_5000}, 0, 0)",
            f"(0, {prod_5000}, 0)",
            f"(0, 0, {prod_5000})",
            f"(-({prod_5000}), 0, 0)",
            f"(({prod_5000}, 0, 0), 1)",
        ):
            with self.assertRaises(calculus.CalculusError) as cm_p:
                calculus.eval_calculus_expression(huge_expr, env={})
            self.assertEqual(cm_p.exception.code, "VALUE_SERIALIZATION_LIMIT", huge_expr)

        for cli_argv in (
            ["calculus", "--eval", prod_5000, "--json"],
            ["calculus", "--eval", f"({prod_5000}, 0, 0)", "--json"],
            ["calculus", "--eval", f"({prod_5000}, 0, 0)"],
        ):
            rc_5k, out_5k, err_5k = _run_cli(cli_argv)
            self.assertEqual(rc_5k, 2)
            if "--json" in cli_argv:
                self.assertEqual(err_5k, "")
                p_5k = parse_strict_json_text(out_5k, allow_float=False)
                self.assertEqual(p_5k["status"], "ERROR")
                self.assertEqual(p_5k["code"], "VALUE_SERIALIZATION_LIMIT")
            else:
                self.assertIn("VALUE_SERIALIZATION_LIMIT", out_5k + err_5k)

    def test_03_diagnose_strict_board_seq_and_fail_closed_jsonl(self) -> None:
        # Direct helper boundary checks: seq=0 and seq>0 pass, omitted seq uses fallback, bool/neg/subclass/str/float/None fail.
        self.assertEqual(diagnose._require_board_seq({"seq": 0}, 99, "t"), 0)
        self.assertEqual(diagnose._require_board_seq({"seq": 5}, 99, "t"), 5)
        self.assertEqual(diagnose._require_board_seq({"agent": "portal-keeper"}, 7, "t"), 7)
        for bad_seq in (True, False, -1, 1.5, "1", "abc", None, [1], _SubInt(1)):
            with self.assertRaises(AletheiaError) as cm:
                diagnose._require_board_seq({"seq": bad_seq}, 1, "t")
            self.assertEqual(cm.exception.code, "INVALID_BOARD_SEQ")

        with tempfile.TemporaryDirectory(prefix="aletheia_t_seq_") as td:
            root = Path(td)
            ws = _make_healthy_expedition(root)

            # Valid seq=0, omitted seq, and non-dict JSONL line succeed cleanly.
            ok_board = root / "ok_board.jsonl"
            write_lf_text(
                ok_board,
                "\n".join([
                    json.dumps({"seq": 0, "agent": "portal-keeper", "text": "Opened Portal 1"}),
                    json.dumps({"agent": "portal-keeper", "text": "Steelmanned Portal 1"}),
                    "[1, 2, 3]",
                    "",
                ]) + "\n",
            )
            res_ok = diagnose.diagnose_expedition(ws, board_path=ok_board)
            self.assertEqual(res_ok["overall_status"], "HEALTHY")

            # Bool, text, numeric-string, float, null, negative seqs all fail closed via Python API & CLI (rc=2).
            bad_cases = [
                ("bool_true", [{"agent": "portal-keeper", "seq": True, "text": "w1"}]),
                ("bool_false", [{"agent": "portal-keeper", "seq": False, "text": "w1"}]),
                ("text_abc", [{"agent": "portal-keeper", "seq": "abc", "text": "w1"}]),
                ("str_num", [{"agent": "portal-keeper", "seq": "1", "text": "w1"}]),
                ("float_seq", [{"agent": "portal-keeper", "seq": 1.5, "text": "w1"}]),
                ("null_seq", [{"agent": "portal-keeper", "seq": None, "text": "w1"}]),
                ("neg_seq", [{"agent": "portal-keeper", "seq": -1, "text": "w1"}]),
                ("no_keeper_bad_seq", [{"agent": "worker", "seq": "abc", "text": "w1"}]),
            ]
            for label, rows in bad_cases:
                bp = root / f"{label}.jsonl"
                write_lf_text(bp, "\n".join(json.dumps(r) for r in rows) + "\n")
                with self.assertRaises(AletheiaError) as cm:
                    diagnose.diagnose_expedition(ws, board_path=bp)
                self.assertEqual(cm.exception.code, "INVALID_BOARD_SEQ", label)
                rc, out, _ = _run_cli(["diagnose", str(ws), "--board", str(bp), "--json"])
                self.assertEqual(rc, 2, label)
                err_obj = parse_strict_json_text(out, allow_float=False)
                self.assertEqual(err_obj["code"], "INVALID_BOARD_SEQ")

            # Malformed JSONL syntax and invalid UTF-8 raise coded AletheiaError (subclass of ValueError) & CLI rc=2.
            bad_json = root / "bad_syntax.jsonl"
            write_lf_text(bad_json, "{not valid json\n")
            with self.assertRaises(AletheiaError) as cm_j:
                diagnose.diagnose_expedition(ws, board_path=bad_json)
            self.assertEqual(cm_j.exception.code, "INVALID_BOARD_JSONL")
            rc_j, out_j, _ = _run_cli(["diagnose", str(ws), "--board", str(bad_json), "--json"])
            self.assertEqual(rc_j, 2)
            self.assertEqual(parse_strict_json_text(out_j, allow_float=False)["code"], "INVALID_BOARD_JSONL")

            bad_utf8 = root / "bad_utf8.jsonl"
            bad_utf8.write_bytes(b"\xff\xfe\n")
            with self.assertRaises(AletheiaError) as cm_u:
                diagnose.diagnose_expedition(ws, board_path=bad_utf8)
            self.assertEqual(cm_u.exception.code, "INVALID_BOARD_UTF8")

    def test_04_mde_sym2_rcp_structural_validation_and_resigned_forgeries(self) -> None:
        # Existing demo passes untouched.
        demo = mde.run_mde_demo()
        self.assertEqual(demo["status"], "PASS")
        self.assertIs(demo["sym2p_tamper_blocked"], True)

        # Boundary positive controls (min/max cf/cv/exp, empty base, max length & depth body, boundary Unicode).
        pkt_min = mde.encode_sym2_rcp_line(
            pid="p0", tk="t0", sender_role="coordinator", recip_role="swarm",
            act="assign", state="proposed", cf=0, cv=0, body_sexpr="()", rq="none", base="", exp=0,
        )
        self.assertIs(mde.verify_sym2_rcp_line(pkt_min), True)

        max_body = "(" + ("a" * (mde.MAX_SYM2_BODY_LEN - 2)) + ")"
        pkt_max = mde.encode_sym2_rcp_line(
            pid="a205", tk="ch1", sender_role="verifier", recip_role="coordinator",
            act="report", state="expired", cf=100, cv=100, body_sexpr=max_body,
            rq="ver", base="f01:2", exp=mde.ZONE_CANON_LIMIT,
        )
        self.assertIs(mde.verify_sym2_rcp_line(pkt_max), True)

        deep_body = "(" * mde.MAX_SYM2_SEXPR_DEPTH + ")" * mde.MAX_SYM2_SEXPR_DEPTH
        pkt_deep = mde.encode_sym2_rcp_line(
            pid="p1", tk="t1", sender_role="builder", recip_role="critic",
            act="assert", state="open", cf=50, cv=50, body_sexpr=deep_body,
        )
        self.assertIs(mde.verify_sym2_rcp_line(pkt_deep), True)

        # Printable space 0x20 and non-surrogate boundaries U+D7FF / U+E000 pass cleanly.
        pkt_uni = mde.encode_sym2_rcp_line(
            pid="p2", tk="t2", sender_role="scout", recip_role="operator",
            act="inform", state="closed", cf=1, cv=99, body_sexpr="(a \ud7ff \ue000)",
        )
        self.assertIs(mde.verify_sym2_rcp_line(pkt_uni), True)

        # Type, newline, shape, checksum format, checksum mismatch, and lone surrogate rejections.
        for bad_type in (123, b"2|a|b", None, _SubStr(pkt_min)):
            with self.assertRaises(AletheiaError) as cm:
                mde.verify_sym2_rcp_line(bad_type)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, "INVALID_SYM2_RCP_TYPE")

        for bad_nl in (pkt_min + "\n", pkt_min + "\r", f"2|a\nb|t|1|2|1|1|0|0|()|0||0|{'0'*16}"):
            with self.assertRaises(AletheiaError) as cm:
                mde.verify_sym2_rcp_line(bad_nl)
            self.assertEqual(cm.exception.code, "INVALID_SYM2_RCP_LINE")

        for bad_shape in ("2|only|three", "3|" + "|".join(_valid_sym2_fields()[1:]) + "|" + "0" * 16):
            with self.assertRaises(AletheiaError) as cm:
                mde.verify_sym2_rcp_line(bad_shape)
            self.assertEqual(cm.exception.code, "INVALID_SYM2_RCP_SHAPE")

        bare_ok = "|".join(_valid_sym2_fields())
        for bad_chk in ("0" * 15, "G" * 16, "0" * 17):
            with self.assertRaises(AletheiaError) as cm:
                mde.verify_sym2_rcp_line(f"{bare_ok}|{bad_chk}")
            self.assertEqual(cm.exception.code, "INVALID_SYM2_RCP_SUM_FORMAT")

        for surr_ch in ("\ud800", "\udfff"):
            surr_fields = _valid_sym2_fields()
            surr_fields[9] = f"(a{surr_ch}b)"
            with self.assertRaises(AletheiaError) as cm:
                mde.verify_sym2_rcp_line("|".join(surr_fields) + "|" + "a" * 16)
            self.assertEqual(cm.exception.code, "LONE_SURROGATE")

        # Re-hashed forged/hollow/out-of-range/malformed-body packets MUST ALL fail closed.
        forged_cases: list[tuple[str, list[str], str]] = [
            ("hollow_all_empty", ["2"] + [""] * 12, "INVALID_V2_PID"),
            ("bad_pid_empty", ["2", ""] + _valid_sym2_fields()[2:], "INVALID_V2_PID"),
            ("bad_pid_dash", ["2", "-bad"] + _valid_sym2_fields()[2:], "INVALID_V2_PID"),
            ("bad_tk_empty", _valid_sym2_fields()[:2] + [""] + _valid_sym2_fields()[3:], "INVALID_V2_TK"),
            ("sender_role_0", _valid_sym2_fields()[:3] + ["0"] + _valid_sym2_fields()[4:], "INVALID_V2_ROLE"),
            ("sender_role_8", _valid_sym2_fields()[:3] + ["8"] + _valid_sym2_fields()[4:], "INVALID_V2_ROLE"),
            ("sender_role_lead0", _valid_sym2_fields()[:3] + ["01"] + _valid_sym2_fields()[4:], "INVALID_SYM2_RCP_INT"),
            ("sender_role_unicode", _valid_sym2_fields()[:3] + ["\u0662"] + _valid_sym2_fields()[4:], "INVALID_SYM2_RCP_INT"),
            ("recip_role_0", _valid_sym2_fields()[:4] + ["0"] + _valid_sym2_fields()[5:], "INVALID_V2_ROLE"),
            ("recip_role_99", _valid_sym2_fields()[:4] + ["99"] + _valid_sym2_fields()[5:], "INVALID_V2_ROLE"),
            ("act_0", _valid_sym2_fields()[:5] + ["0"] + _valid_sym2_fields()[6:], "INVALID_V2_CODE"),
            ("act_13", _valid_sym2_fields()[:5] + ["13"] + _valid_sym2_fields()[6:], "INVALID_V2_CODE"),
            ("state_0", _valid_sym2_fields()[:6] + ["0"] + _valid_sym2_fields()[7:], "INVALID_V2_CODE"),
            ("state_9", _valid_sym2_fields()[:6] + ["9"] + _valid_sym2_fields()[7:], "INVALID_V2_CODE"),
            ("cf_101", _valid_sym2_fields()[:7] + ["101"] + _valid_sym2_fields()[8:], "INVALID_SYM2_RCP_RANGE"),
            ("cf_neg", _valid_sym2_fields()[:7] + ["-1"] + _valid_sym2_fields()[8:], "INVALID_SYM2_RCP_INT"),
            ("cf_unicode", _valid_sym2_fields()[:7] + ["\u0662"] + _valid_sym2_fields()[8:], "INVALID_SYM2_RCP_INT"),
            ("cv_101", _valid_sym2_fields()[:8] + ["101"] + _valid_sym2_fields()[9:], "INVALID_SYM2_RCP_RANGE"),
            ("body_empty", _valid_sym2_fields()[:9] + [""] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_len1", _valid_sym2_fields()[:9] + ["("] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_too_long", _valid_sym2_fields()[:9] + ["(" + "a" * (mde.MAX_SYM2_BODY_LEN - 1) + ")"] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_plain_text", _valid_sym2_fields()[:9] + ["plain"] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_unmatched_close", _valid_sym2_fields()[:9] + [")("] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_unclosed_open", _valid_sym2_fields()[:9] + ["((1)"] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_outer_junk", _valid_sym2_fields()[:9] + ["(1)junk(2)"] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_too_deep", _valid_sym2_fields()[:9] + ["(" * (mde.MAX_SYM2_SEXPR_DEPTH + 1) + ")" * (mde.MAX_SYM2_SEXPR_DEPTH + 1)] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_ctrl_1f", _valid_sym2_fields()[:9] + ["(a\x1fb)"] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("body_del_7f", _valid_sym2_fields()[:9] + ["(a\x7fb)"] + _valid_sym2_fields()[10:], "INVALID_V2_BODY"),
            ("rq_3", _valid_sym2_fields()[:10] + ["3"] + _valid_sym2_fields()[11:], "INVALID_V2_CODE"),
            ("base_bad", _valid_sym2_fields()[:11] + ["-bad base"] + _valid_sym2_fields()[12:], "INVALID_V2_BASE"),
            ("exp_notint", _valid_sym2_fields()[:12] + ["notint"], "INVALID_SYM2_RCP_INT"),
            ("exp_neg", _valid_sym2_fields()[:12] + ["-1"], "INVALID_SYM2_RCP_INT"),
            ("exp_over_limit", _valid_sym2_fields()[:12] + [str(mde.ZONE_CANON_LIMIT + 1)], "INVALID_SYM2_RCP_RANGE"),
        ]
        for label, fields, exp_code in forged_cases:
            forged_pkt = _forge_sym2_line(fields)
            with self.assertRaises(AletheiaError) as cm:
                mde.verify_sym2_rcp_line(forged_pkt)
            self.assertEqual(cm.exception.code, exp_code, f"{label}: got {cm.exception.code}")

        # encode_sym2_rcp_line enforces the same strict invariants (including type checks & pipe/surrogate bans).
        base_kw = dict(
            pid="p1", tk="t1", sender_role="verifier", recip_role="coordinator",
            act="receipt", state="verified", cf=50, cv=50, body_sexpr="(1 2)", rq="ack", base="f01:2", exp=10,
        )
        bad_encode: list[tuple[dict[str, object], str]] = [
            ({"pid": _SubStr("p1")}, "INVALID_V2_PID"),
            ({"pid": "-bad"}, "INVALID_V2_PID"),
            ({"tk": _SubStr("t1")}, "INVALID_V2_TK"),
            ({"tk": ""}, "INVALID_V2_TK"),
            ({"sender_role": _SubStr("verifier")}, "INVALID_V2_ROLE"),
            ({"sender_role": "bogus"}, "INVALID_V2_ROLE"),
            ({"recip_role": _SubStr("coordinator")}, "INVALID_V2_ROLE"),
            ({"recip_role": "bogus"}, "INVALID_V2_ROLE"),
            ({"act": _SubStr("receipt")}, "INVALID_V2_CODE"),
            ({"act": "bogus"}, "INVALID_V2_CODE"),
            ({"state": _SubStr("verified")}, "INVALID_V2_CODE"),
            ({"state": "bogus"}, "INVALID_V2_CODE"),
            ({"rq": _SubStr("ack")}, "INVALID_V2_CODE"),
            ({"rq": "bogus"}, "INVALID_V2_CODE"),
            ({"cf": True}, "INVALID_V2_SCORE"),
            ({"cf": -1}, "INVALID_V2_SCORE"),
            ({"cf": 101}, "INVALID_V2_SCORE"),
            ({"cv": False}, "INVALID_V2_SCORE"),
            ({"cv": -1}, "INVALID_V2_SCORE"),
            ({"cv": 101}, "INVALID_V2_SCORE"),
            ({"body_sexpr": _SubStr("(1)")}, "INVALID_V2_BODY"),
            ({"body_sexpr": "(a|b)"}, "INVALID_V2_BODY"),
            ({"body_sexpr": "(a\ud800b)"}, "LONE_SURROGATE"),
            ({"base": _SubStr("f01:2")}, "INVALID_V2_BASE"),
            ({"base": "bad base"}, "INVALID_V2_BASE"),
            ({"exp": True}, "INVALID_V2_EXP"),
            ({"exp": -1}, "INVALID_V2_EXP"),
            ({"exp": mde.ZONE_CANON_LIMIT + 1}, "INVALID_V2_EXP"),
        ]
        for overrides, exp_code in bad_encode:
            kw = dict(base_kw)
            kw.update(overrides)
            with self.assertRaises(AletheiaError) as cm:
                mde.encode_sym2_rcp_line(**kw)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, exp_code, f"{overrides}: got {cm.exception.code}")


if __name__ == "__main__":
    unittest.main()
