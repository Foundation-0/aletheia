#!/usr/bin/env python3
"""
Comprehensive R1-R5 unit test suite for Track S166 (`EXP-Q48`, `EXP-Q49`, `EXP-Q46b`):
  - `aletheia.portfolio_dag` (CS-27 / SOP-18)
  - `aletheia.portal_interpose` (CS-28 / SOP-19)
  - `aletheia.thin_coordinator` (CS-29 / SOP-20)
  - `aletheia.lean_audit_hardening` (EXP-Q46b)

Zero external dependencies, zero bare asserts, 100% parity across:
  python3 -I -B tests/test_cs27_cs29_hardening_r5.py
  python3 -I -O -B tests/test_cs27_cs29_hardening_r5.py
  python3 -I -B -W error tests/test_cs27_cs29_hardening_r5.py
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import lean_audit_hardening as lah  # noqa: E402
from aletheia import portal_interpose as pi  # noqa: E402
from aletheia import portfolio_dag as pdag  # noqa: E402
from aletheia import thin_coordinator as tc  # noqa: E402


def _write_lf(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _valid_dag() -> dict:
    return {
        "zero_antibot_bypass": True,
        "nodes": [
            {"id": "p0", "depth": 0, "url": "https://example.invalid/p0"},
            {"id": "d1", "depth": 1, "url": "https://example.invalid/d1"},
            {"id": "d2", "depth": 2, "url": "https://example.invalid/d2"},
            {"id": "d2b", "depth": 2, "url": "https://example.invalid/d2b"},
        ],
        "edges": [
            {"from": "p0", "to": "d1", "relation": "links_to"},
            {"from": "d1", "to": "d2", "relation": "cites"},
            {"from": "d2", "to": "d2b", "relation": "peer"},
        ],
    }


def _valid_portfolio(exp_hf: int = 2, n_hf: int = 2) -> dict:
    arts = [
        {"id": f"org/art_{i}", "kind": "model" if i % 2 == 0 else "dataset", "private": False}
        for i in range(n_hf)
    ]
    hf: dict = {
        "checked": True,
        "expected_public_artifacts": exp_hf,
        "artifacts": arts,
    }
    if exp_hf == 0 and n_hf == 0:
        hf["zero_hf_disambiguation_query"] = "author_query_0_hits"
    return {
        "author": "alice",
        "github": {
            "checked": True,
            "expected_public_repos": 2,
            "branches_enumerated": True,
            "prs_enumerated": True,
            "repos": [
                {"name": "repo1", "is_private": False},
                {"name": "repo2", "is_private": False},
            ],
        },
        "huggingface": hf,
    }


class TestCS27PortfolioDag(unittest.TestCase):
    def _assert_dag_err(self, fn, code: str, *args, **kwargs) -> None:
        with self.assertRaises(pdag.PortfolioDagError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_01_valid_dag_and_url_key_fallback(self) -> None:
        res = pdag.validate_nested_link_dag(_valid_dag(), min_deep_ratio_q=Fraction(3, 4))
        self.assertTrue(res["dag_verified"])
        self.assertEqual(res["total_nodes"], 4)
        self.assertEqual(res["deep_nodes"], 3)
        self.assertEqual(res["max_depth"], 2)
        self.assertEqual(res["deep_node_ratio_q"], "3/4")
        self.assertEqual(res["mean_out_degree_q"], "3/4")

        url_graph = {
            "nodes": [
                {"url": "https://a.invalid", "depth": 0},
                {"url": "https://b.invalid", "depth": 1},
            ],
            "edges": [{"from": "https://a.invalid", "to": "https://b.invalid"}],
        }
        r2 = pdag.validate_nested_link_dag(url_graph, enforce_depth_monotone=False)
        self.assertEqual(r2["total_nodes"], 2)

        # Wave-22 schema aliases: ('source', 'target') + 'edge_type' and ('src', 'dst') + 'rel' + 'min_depth'
        g_st = {
            "nodes": [{"id": "r", "min_depth": 0}, {"id": "c", "min_depth": 1}],
            "edges": [{"source": "r", "target": "c", "edge_type": "cites"}],
        }
        self.assertTrue(pdag.validate_nested_link_dag(g_st)["dag_verified"])
        g_sd = {
            "nodes": [{"id": "r", "depth": 0}, {"id": "c", "depth": 1}],
            "edges": [{"src": "r", "dst": "c", "rel": "child"}],
        }
        self.assertTrue(pdag.validate_nested_link_dag(g_sd)["dag_verified"])

    def test_02_dag_cycles_and_structural_rejections(self) -> None:
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_GRAPH_TYPE", [])
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_BOOL", _valid_dag(), require_recursive=1)
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_BOOL", _valid_dag(), enforce_depth_monotone=0)
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_FRACTION", _valid_dag(), min_deep_ratio_q="0.5")
        self._assert_dag_err(pdag.validate_nested_link_dag, "OUT_OF_RANGE_FRACTION", _valid_dag(), min_deep_ratio_q=Fraction(-1, 2))
        self._assert_dag_err(pdag.validate_nested_link_dag, "OUT_OF_RANGE_FRACTION", _valid_dag(), min_deep_ratio_q=Fraction(3, 2))

        # Exact boundary [0, 1] accepted
        self.assertTrue(pdag.validate_nested_link_dag(_valid_dag(), min_deep_ratio_q=0)["dag_verified"])
        self._assert_dag_err(pdag.validate_nested_link_dag, "INSUFFICIENT_DEEP_COVERAGE", _valid_dag(), min_deep_ratio_q=Fraction(1, 1))

        g_ab = _valid_dag()
        g_ab["zero_antibot_bypass"] = False
        self._assert_dag_err(pdag.validate_nested_link_dag, "ANTIBOT_BYPASS_FORBIDDEN", g_ab)

        g_nab = _valid_dag()
        g_nab["nodes"][0]["anti_bot_bypass"] = True
        self._assert_dag_err(pdag.validate_nested_link_dag, "ANTIBOT_BYPASS_FORBIDDEN", g_nab)

        self._assert_dag_err(pdag.validate_nested_link_dag, "MISSING_NODES", {"edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "MISSING_EDGES", {"nodes": [{"id": "a", "depth": 0}]})
        self._assert_dag_err(pdag.validate_nested_link_dag, "EMPTY_NODES", {"nodes": [], "edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_NODE", {"nodes": ["bad"], "edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "MISSING_NODE_KEY", {"nodes": [{"depth": 0}], "edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_STR", {"nodes": [{"id": " ", "depth": 0}], "edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "DUPLICATE_NODE_ID", {"nodes": [{"id": "a", "depth": 0}, {"id": "a", "depth": 1}], "edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "MISSING_NODE_DEPTH", {"nodes": [{"id": "a"}], "edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_INT", {"nodes": [{"id": "a", "depth": True}], "edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_INT", {"nodes": [{"id": "a", "depth": -1}], "edges": []})
        self._assert_dag_err(pdag.validate_nested_link_dag, "NO_ROOT_PORTAL", {"nodes": [{"id": "a", "depth": 1}], "edges": []})

        # Edge checks & cycle detection (self-loop and 3-cycle)
        self._assert_dag_err(pdag.validate_nested_link_dag, "INVALID_EDGE", {"nodes": [{"id": "a", "depth": 0}], "edges": ["bad"]})
        self._assert_dag_err(pdag.validate_nested_link_dag, "MISSING_EDGE_ENDPOINT", {"nodes": [{"id": "a", "depth": 0}], "edges": [{"from": "a"}]})
        self._assert_dag_err(pdag.validate_nested_link_dag, "DANGLING_EDGE_ENDPOINT", {"nodes": [{"id": "a", "depth": 0}], "edges": [{"from": "missing", "to": "a"}]})
        self._assert_dag_err(pdag.validate_nested_link_dag, "DANGLING_EDGE_ENDPOINT", {"nodes": [{"id": "a", "depth": 0}], "edges": [{"from": "a", "to": "missing"}]})
        self._assert_dag_err(
            pdag.validate_nested_link_dag,
            "DUPLICATE_EDGE",
            {"nodes": [{"id": "a", "depth": 0}, {"id": "b", "depth": 1}], "edges": [{"from": "a", "to": "b"}, {"from": "a", "to": "b"}]},
        )
        self._assert_dag_err(
            pdag.validate_nested_link_dag,
            "CYCLE_DETECTED",
            {"nodes": [{"id": "a", "depth": 0}], "edges": [{"from": "a", "to": "a"}]},
        )
        g_cyc = _valid_dag()
        g_cyc["edges"].append({"from": "d2b", "to": "p0", "relation": "back"})
        self._assert_dag_err(pdag.validate_nested_link_dag, "CYCLE_DETECTED", g_cyc)

        # Depth regression & unreachable deep node
        g_reg = _valid_dag()
        g_reg["edges"].append({"from": "d1", "to": "p0", "relation": "up"})
        g_reg["nodes"][0]["depth"] = 0
        g_reg["nodes"][1]["depth"] = 1
        # d1 -> d2 -> d2b; d1 -> p0 creates no cycle if p0 -> d1 is removed:
        g_reg["edges"] = [{"from": "d1", "to": "p0", "relation": "up"}]
        g_reg["nodes"] = [{"id": "p0", "depth": 0}, {"id": "d1", "depth": 1}, {"id": "r0", "depth": 0}]
        g_reg["edges"] = [{"from": "r0", "to": "d1"}, {"from": "d1", "to": "p0"}]
        self._assert_dag_err(pdag.validate_nested_link_dag, "DEPTH_REGRESSION", g_reg)

        g_unreach = {"nodes": [{"id": "p0", "depth": 0}, {"id": "d1", "depth": 1}], "edges": []}
        self._assert_dag_err(pdag.validate_nested_link_dag, "UNREACHABLE_DEEP_NODE", g_unreach)

        g_shallow = {"nodes": [{"id": "p0", "depth": 0}], "edges": []}
        self._assert_dag_err(pdag.validate_nested_link_dag, "SHALLOW_PORTAL_BLINDNESS", g_shallow)
        g_shallow_ok = {"nodes": [{"id": "p0", "depth": 0}], "edges": [], "exhaustion_verified": True}
        self.assertTrue(pdag.validate_nested_link_dag(g_shallow_ok)["dag_verified"])
        self.assertTrue(pdag.validate_nested_link_dag(g_shallow, require_recursive=False)["dag_verified"])

    def test_03_portfolio_coverage_and_zone_b_file_checks(self) -> None:
        res = pdag.evaluate_portfolio_coverage(_valid_portfolio())
        self.assertTrue(res["passed"])
        self.assertEqual(res["platform_symmetry_q"], "1/1")

        # Zero HF with explicit disambiguation query passes; zero GH also requires explicit disambiguation query ([LOW-6])
        zero_hf = _valid_portfolio(exp_hf=0, n_hf=0)
        self.assertEqual(pdag.evaluate_portfolio_coverage(zero_hf)["hf_coverage_q"], "1/1")
        zero_gh_unverified = _valid_portfolio()
        zero_gh_unverified["github"] = {"checked": True, "expected_public_repos": 0, "repos": []}
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "UNVERIFIED_ZERO_GH", zero_gh_unverified)
        zero_gh = _valid_portfolio()
        zero_gh["github"] = {
            "checked": True,
            "expected_public_repos": 0,
            "repos": [],
            "zero_gh_disambiguation_query": "author_gh_query_0_hits",
        }
        self.assertEqual(pdag.evaluate_portfolio_coverage(zero_gh)["github_coverage_q"], "1/1")

        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "INVALID_PORTFOLIO_TYPE", "bad")
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_AUTHOR", {"github": {}, "huggingface": {}})
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "SINGLE_PLATFORM_BLINDNESS", {"author": "a", "huggingface": {}})
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "SINGLE_PLATFORM_BLINDNESS", {"author": "a", "github": {}})

        p_nochk = _valid_portfolio()
        del p_nochk["github"]["checked"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_GH_CHECKED", p_nochk)
        p_ghf = _valid_portfolio()
        p_ghf["github"]["checked"] = False
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "SINGLE_PLATFORM_BLINDNESS", p_ghf)

        p_noexp = _valid_portfolio()
        del p_noexp["github"]["expected_public_repos"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_GH_EXPECTED", p_noexp)

        p_norepos = _valid_portfolio()
        p_norepos["github"]["repos"] = "bad"
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_GH_REPOS", p_norepos)

        p_badrepo = _valid_portfolio()
        p_badrepo["github"]["repos"] = ["bad"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "INVALID_GH_REPO", p_badrepo)

        p_duprepo = _valid_portfolio()
        p_duprepo["github"]["repos"] = [{"name": "r1", "is_private": False}, {"name": "r1", "is_private": False}]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "DUPLICATE_GH_REPO", p_duprepo)

        p_nopriv = _valid_portfolio()
        del p_nopriv["github"]["repos"][0]["is_private"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_GH_PRIVATE_FLAG", p_nopriv)

        p_priv = _valid_portfolio()
        p_priv["github"]["repos"][0]["is_private"] = True
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "PRIVATE_REPO_LEAK", p_priv)

        p_nobr = _valid_portfolio()
        del p_nobr["github"]["branches_enumerated"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "SHALLOW_MAIN_ONLY", p_nobr)
        p_brf = _valid_portfolio()
        p_brf["github"]["prs_enumerated"] = False
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "SHALLOW_MAIN_ONLY", p_brf)
        self.assertTrue(pdag.evaluate_portfolio_coverage(p_brf, require_branch_pr_enumeration=False)["passed"])

        # HF checks
        p_hfc = _valid_portfolio()
        del p_hfc["huggingface"]["checked"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_HF_CHECKED", p_hfc)
        p_hff = _valid_portfolio()
        p_hff["huggingface"]["checked"] = False
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "SINGLE_PLATFORM_BLINDNESS", p_hff)
        p_hfe = _valid_portfolio()
        del p_hfe["huggingface"]["expected_public_artifacts"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_HF_EXPECTED", p_hfe)
        p_hfa = _valid_portfolio()
        p_hfa["huggingface"]["artifacts"] = "bad"
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_HF_ARTIFACTS", p_hfa)
        p_hfi = _valid_portfolio()
        p_hfi["huggingface"]["artifacts"] = ["bad"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "INVALID_HF_ARTIFACT", p_hfi)
        p_hfk = _valid_portfolio()
        p_hfk["huggingface"]["artifacts"][0]["kind"] = "unknown"
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "INVALID_HF_KIND", p_hfk)
        p_hfd = _valid_portfolio()
        p_hfd["huggingface"]["artifacts"][1] = dict(p_hfd["huggingface"]["artifacts"][0])
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "DUPLICATE_HF_ARTIFACT", p_hfd)
        p_hfnp = _valid_portfolio()
        del p_hfnp["huggingface"]["artifacts"][0]["private"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "MISSING_HF_PRIVATE_FLAG", p_hfnp)
        p_hfp = _valid_portfolio()
        p_hfp["huggingface"]["artifacts"][0]["private"] = True
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "PRIVATE_HF_LEAK", p_hfp)
        p_zhf = _valid_portfolio(exp_hf=0, n_hf=0)
        del p_zhf["huggingface"]["zero_hf_disambiguation_query"]
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "UNVERIFIED_ZERO_HF", p_zhf)

        p_ghlow = _valid_portfolio()
        p_ghlow["github"]["expected_public_repos"] = 4
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "GITHUB_COVERAGE_BELOW_THRESHOLD", p_ghlow)
        p_hflow = _valid_portfolio()
        p_hflow["huggingface"]["expected_public_artifacts"] = 4
        self._assert_dag_err(pdag.evaluate_portfolio_coverage, "HF_COVERAGE_BELOW_THRESHOLD", p_hflow)

        # Zone-B strict JSON & file checks
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dag_ok = _write_lf(root / "dag.json", (json.dumps(_valid_dag()) + "\n").encode("utf-8"))
            cov_ok = _write_lf(root / "cov.json", (json.dumps(_valid_portfolio()) + "\n").encode("utf-8"))
            self.assertTrue(pdag.validate_nested_link_dag_file(dag_ok)["dag_verified"])
            self.assertTrue(pdag.evaluate_portfolio_coverage_file(cov_ok)["passed"])

            self._assert_dag_err(pdag.validate_nested_link_dag_file, "INVALID_PATH", 123)
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "INVALID_PATH", "bad\x00path.json")
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "INVALID_PATH", Path("."))
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "IO_ERROR", root / "missing.json")
            sub = root / "adir"
            sub.mkdir()
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "NOT_REGULAR_FILE", sub)
            sym = root / "sym.json"
            os.symlink(dag_ok, sym)
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "IO_ERROR", sym)

            bom = _write_lf(root / "bom.json", b"\xef\xbb\xbf{}\n")
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_BOM_FORBIDDEN", bom)
            crlf = _write_lf(root / "crlf.json", b"{}\r\n")
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_CRLF_FORBIDDEN", crlf)
            bad_utf = _write_lf(root / "utf.json", b"\xff\xfe\n")
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "INVALID_UTF8", bad_utf)
            emp = _write_lf(root / "emp.json", b"   \n")
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "EMPTY_JSON", emp)
            flt = _write_lf(root / "flt.json", b'{"a": 1.5}\n')
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_FLOAT_FORBIDDEN", flt)
            nanf = _write_lf(root / "nan.json", b'{"a": NaN}\n')
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_CONSTANT_FORBIDDEN", nanf)
            dup = _write_lf(root / "dup.json", b'{"a": 1, "a": 2}\n')
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_DUPLICATE_KEY", dup)
            big_int = _write_lf(root / "bigint.json", ('{"a": ' + ("9" * 1025) + "}\n").encode("utf-8"))
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_INT_TOO_LONG", big_int)
            neg_int_ok = _write_lf(root / "negok.json", ('{"a": -' + ("9" * 1024) + "}\n").encode("utf-8"))
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "MISSING_NODES", neg_int_ok)
            bad_syn = _write_lf(root / "syn.json", b"{bad\n")
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_SYNTAX_ERROR", bad_syn)
            sur = _write_lf(root / "sur.json", b'{"a": "\\ud800"}\n')
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_LONE_SURROGATE", sur)

            # Exact depth 64 dict & list pass depth check; depth 65 fails; exact 1024-digit int passes
            ok_1024 = _write_lf(root / "ok1024.json", ('{"a": ' + ("9" * 1024) + "}\n").encode("utf-8"))
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "MISSING_NODES", ok_1024)
            d64_dict = _write_lf(root / "d64d.json", ('{"a":' * 64 + "1" + "}" * 64 + "\n").encode("utf-8"))
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "MISSING_NODES", d64_dict)
            d64_list = _write_lf(root / "d64l.json", ("[" * 64 + "1" + "]" * 64 + "\n").encode("utf-8"))
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "INVALID_GRAPH_TYPE", d64_list)
            d65_f = _write_lf(root / "d65.json", ("[" * 65 + "1" + "]" * 65 + "\n").encode("utf-8"))
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_DEPTH_EXCEEDED", d65_f)
            d65_obj = _write_lf(root / "d65o.json", ('{"x":' * 65 + "1" + "}" * 65 + "\n").encode("utf-8"))
            self._assert_dag_err(pdag.validate_nested_link_dag_file, "JSON_DEPTH_EXCEEDED", d65_obj)

            dag_len = len(dag_ok.read_bytes())
            with mock.patch.object(pdag, "MAX_FILE_BYTES", dag_len):
                self.assertTrue(pdag.validate_nested_link_dag_file(dag_ok)["dag_verified"])
            with mock.patch.object(pdag, "MAX_FILE_BYTES", dag_len - 1):
                self._assert_dag_err(pdag.validate_nested_link_dag_file, "FILE_TOO_LARGE", dag_ok)

            # [LOW-5] verify_regular_file_path avoids Path.resolve() and checks lstat parity
            with mock.patch.object(Path, "resolve", side_effect=AssertionError("resolve must not be called")):
                verified_p = pdag._zb.verify_regular_file_path(dag_ok, "dag", err_cls=pdag.PortfolioDagError)
                self.assertTrue(verified_p.is_file())
            fake_sym_stat = os.stat_result((0o120777, 0, 0, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch("os.lstat", return_value=fake_sym_stat):
                self._assert_dag_err(
                    pdag._zb.verify_regular_file_path,
                    "NOT_REGULAR_FILE",
                    dag_ok,
                    "dag",
                    err_cls=pdag.PortfolioDagError,
                )


class TestCS28PortalInterpose(unittest.TestCase):
    def _assert_pi_err(self, fn, code: str, *args, **kwargs) -> None:
        with self.assertRaises(pi.PortalInterposeError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_04_regressions_domain_strip_sqlite_and_law5(self) -> None:
        reg = pi.run_cs28_regression_fixtures()
        self.assertTrue(reg["passed"])
        self.assertIn("optimization_quantization", reg["hadwiger_pillars_hit"])
        self.assertIn("bio_connectome", reg["pfc_pillars_hit"])

        stripped = pi.strip_domain_labels("Neuroscience and Convex Geometry study ellipsoid covering")
        self.assertEqual(stripped["stripped_labels"], ["convex geometry", "neuroscience"])
        self.assertEqual(stripped["stripped_label_count"], 2)

        self._assert_pi_err(pi.strip_domain_labels, "EMPTY_OR_INVALID_TEXT", "   ")
        self._assert_pi_err(pi.score_domain_stripped_pillars, "EMPTY_PILLAR_SPECS", "t", "body", pillar_specs=())
        self._assert_pi_err(
            pi.score_domain_stripped_pillars,
            "EMPTY_PILLAR_RULES",
            "t",
            "body",
            pillar_specs=(("p", "L", "R", ()),),
        )
        self._assert_pi_err(pi.interpose_portal, "NO_PILLAR_HIT", "Unrelated", "xylophone zebra meadow cloud")
        no_req = pi.interpose_portal("Unrelated", "xylophone zebra", require_any_hit=False)
        self.assertEqual(no_req["pillars_hit"], 0)

        # Law-5 guard dispositions
        cand = pi.enforce_law5_interpose_guard({"pillar": "bio_connectome", "disposition": "CANDIDATE_ONLY"})
        self.assertFalse(cand["verified_bridge"])
        obs = pi.enforce_law5_interpose_guard({
            "pillar": "pure_math_formal",
            "disposition": "STRUCTURAL_OBSTRUCTION",
            "source_object": "V2(Z(O_4))",
            "target_object": "V2(Q_4)",
            "witness": "obstruction: 12 + 8*sqrt(3) > 24 strictly blocks V2 domination",
        })
        self.assertEqual(obs["status"], "STRUCTURAL_OBSTRUCTION_RECORDED")

        self._assert_pi_err(pi.enforce_law5_interpose_guard, "INVALID_CLAIM_TYPE", [])
        self._assert_pi_err(
            pi.enforce_law5_interpose_guard,
            "INVALID_DISPOSITION",
            {"pillar": "p", "disposition": "BAD"},
        )
        self._assert_pi_err(
            pi.enforce_law5_interpose_guard,
            "LAW5_SMUGGLE_REJECTED",
            {
                "pillar": "p",
                "disposition": "EXACT_OPERATOR_TRANSFER",
                "source_object": "A",
                "target_object": "B",
                "witness": "sheaf duality holonomy",
            },
        )
        self._assert_pi_err(
            pi.enforce_law5_interpose_guard,
            "LAW5_MISSING_OPERATOR_WITNESS",
            {
                "pillar": "p",
                "disposition": "EXACT_OPERATOR_TRANSFER",
                "source_object": "A",
                "target_object": "B",
                "witness": "plain prose without symbols",
            },
        )
        # [MED-10 / LOW-1] Negated/refuted/vacuous operator & obstruction witnesses must fail closed
        for bad_op_w in (
            "there is no identity here",
            "=",
            "identity",
            "no exact map commutes",
            "a = b does not hold",
            "refuted: x = y",
            "disproved: x = y",
            "x = y fails to hold",
        ):
            self._assert_pi_err(
                pi.enforce_law5_interpose_guard,
                "LAW5_MISSING_OPERATOR_WITNESS",
                {
                    "pillar": "p",
                    "disposition": "EXACT_OPERATOR_TRANSFER",
                    "source_object": "A",
                    "target_object": "B",
                    "witness": bad_op_w,
                },
            )
        self._assert_pi_err(
            pi.enforce_law5_interpose_guard,
            "LAW5_SMUGGLE_REJECTED",
            {
                "pillar": "p",
                "disposition": "EXACT_OPERATOR_TRANSFER",
                "source_object": "A",
                "target_object": "B",
                "witness": "exact identity via sheaf duality holonomy",
            },
        )
        self._assert_pi_err(
            pi.enforce_law5_interpose_guard,
            "LAW5_MISSING_OBSTRUCTION_WITNESS",
            {
                "pillar": "p",
                "disposition": "STRUCTURAL_OBSTRUCTION",
                "source_object": "A",
                "target_object": "B",
                "witness": "plain prose without reason",
            },
        )
        for bad_obs_w in ("<", "there is no obstruction here", "obstruction does not hold"):
            self._assert_pi_err(
                pi.enforce_law5_interpose_guard,
                "LAW5_MISSING_OBSTRUCTION_WITNESS",
                {
                    "pillar": "p",
                    "disposition": "STRUCTURAL_OBSTRUCTION",
                    "source_object": "A",
                    "target_object": "B",
                    "witness": bad_obs_w,
                },
            )

        # Optional read-only SQLite archive query
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "rag.sqlite"
            con = sqlite3.connect(str(db))
            con.execute("CREATE TABLE nodes (id TEXT, node_type TEXT, title TEXT, summary TEXT)")
            con.execute("INSERT INTO nodes VALUES ('track:s20b', 'track', 'SiliQuant BlockH4', 'quantization codebook')")
            con.commit()
            con.close()

            ip_res = pi.interpose_portal(
                "Ellipsoid Covering",
                "Homothetic covering and John ellipsoid preconditioning",
                rag_db_path=db,
                archive_limit=1,
            )
            self.assertTrue(ip_res["archive_queried"])
            hits_with_arch = [r for r in ip_res["pillar_matrix"] if r["pillar"] == "optimization_quantization"][0]
            self.assertEqual(len(hits_with_arch["archive_nodes"]), 1)
            self.assertEqual(pi.query_sqlite_archive(db, "unknown_pillar"), [])

            self._assert_pi_err(pi.query_sqlite_archive, "INVALID_ARCHIVE_PATH", 123, "optimization_quantization")
            self._assert_pi_err(pi.query_sqlite_archive, "INVALID_ARCHIVE_PATH", Path("."), "optimization_quantization")
            self._assert_pi_err(pi.query_sqlite_archive, "INVALID_INT", db, "optimization_quantization", limit=0)
            self._assert_pi_err(pi.query_sqlite_archive, "ARCHIVE_IO_ERROR", root / "nope.sqlite", "optimization_quantization")
            sub = root / "dir"
            sub.mkdir()
            self._assert_pi_err(pi.query_sqlite_archive, "NOT_REGULAR_ARCHIVE", sub, "optimization_quantization")
            bad_db = _write_lf(root / "bad.sqlite", b"not sqlite\n")
            self._assert_pi_err(pi.query_sqlite_archive, "ARCHIVE_SQLITE_ERROR", bad_db, "optimization_quantization")
            with mock.patch("sqlite3.connect", side_effect=sqlite3.OperationalError("boom")):
                self._assert_pi_err(pi.query_sqlite_archive, "ARCHIVE_SQLITE_ERROR", db, "optimization_quantization")

            # [MED-3] URI special chars (#, ?, %) never truncate path, never create `bad`, never read wrong DB
            self._assert_pi_err(pi.query_sqlite_archive, "ARCHIVE_IO_ERROR", root / "bad#1.db", "optimization_quantization")
            self._assert_pi_err(pi.query_sqlite_archive, "ARCHIVE_IO_ERROR", root / "bad?1.db", "optimization_quantization")
            self.assertFalse((root / "bad").exists())
            bad_corrupt = _write_lf(root / "bad#corrupt.db", b"corrupt\n")
            self._assert_pi_err(pi.query_sqlite_archive, "ARCHIVE_SQLITE_ERROR", bad_corrupt, "optimization_quantization")
            self.assertFalse((root / "bad").exists())

            trap_db = root / "victim"
            tcon = sqlite3.connect(str(trap_db))
            tcon.execute("CREATE TABLE nodes (id TEXT, node_type TEXT, title TEXT, summary TEXT)")
            tcon.execute("INSERT INTO nodes VALUES ('wrong_db_siliquant', 'track', 'wrong', 'siliquant')")
            tcon.commit()
            tcon.close()
            for sp_name in ("victim#1.db", "victim?1.db", "victim%20.db"):
                sp_db = root / sp_name
                scon = sqlite3.connect(str(sp_db))
                scon.execute("CREATE TABLE nodes (id TEXT, node_type TEXT, title TEXT, summary TEXT)")
                scon.execute("INSERT INTO nodes VALUES (?, 'track', 'SiliQuant exact', 'quantization')", (f"ok:{sp_name}",))
                scon.commit()
                scon.close()
                got = pi.query_sqlite_archive(sp_db, "optimization_quantization")
                self.assertEqual(got[0]["node_id"], f"ok:{sp_name}")
            self.assertFalse((root / "bad").exists())

            # [MED-9] Uncheckpointed WAL rows visible read-only; symlinked -wal sidecar rejected; [LOW-9] ESCAPE '!'
            wal_db = root / "wal_live.sqlite"
            wcon = sqlite3.connect(str(wal_db))
            wcon.execute("PRAGMA journal_mode=WAL")
            wcon.execute("CREATE TABLE nodes (id TEXT, node_type TEXT, title TEXT, summary TEXT)")
            wcon.execute("INSERT INTO nodes VALUES ('wal:1', 'track', 'SiliQuant WAL', 'quantization')")
            wcon.execute("INSERT INTO nodes VALUES ('arch:x', 'repo', 'smX86 wrong', 'smX86')")
            wcon.execute("INSERT INTO nodes VALUES ('arch:ok', 'repo', 'sm_86 exact', 'sm_86')")
            wcon.commit()
            try:
                wal_rows = pi.query_sqlite_archive(wal_db, "optimization_quantization")
                self.assertEqual(wal_rows[0]["node_id"], "wal:1")
                arch_rows = pi.query_sqlite_archive(wal_db, "architecture_silicon")
                self.assertEqual([r["node_id"] for r in arch_rows], ["arch:ok"])
            finally:
                wcon.close()

            sym_wal_db = root / "sym_wal.sqlite"
            swcon = sqlite3.connect(str(sym_wal_db))
            swcon.execute("CREATE TABLE nodes (id TEXT, node_type TEXT, title TEXT, summary TEXT)")
            swcon.commit()
            swcon.close()
            os.symlink(db, Path(f"{sym_wal_db}-wal"))
            self._assert_pi_err(pi.query_sqlite_archive, "NOT_REGULAR_ARCHIVE", sym_wal_db, "optimization_quantization")
            sym_wal_err = root / "sym_wal_dir.sqlite"
            swcon2 = sqlite3.connect(str(sym_wal_err))
            swcon2.execute("CREATE TABLE nodes (id TEXT, node_type TEXT, title TEXT, summary TEXT)")
            swcon2.commit()
            swcon2.close()
            Path(f"{sym_wal_err}-wal").write_bytes(b"")
            real_lstat = os.lstat

            def _shm_lstat_fail(p_arg, *args, **kwargs):
                if os.fspath(p_arg).endswith("-shm"):
                    raise PermissionError("sidecar lstat fail")
                return real_lstat(p_arg, *args, **kwargs)

            with mock.patch("os.lstat", side_effect=_shm_lstat_fail):
                self._assert_pi_err(pi.query_sqlite_archive, "ARCHIVE_IO_ERROR", sym_wal_err, "optimization_quantization")

            # [LOW-2] Post-open TOCTOU swap detection on SQLite archive path
            lstat_calls = {"n": 0}

            def _swap_after_open(p_arg, *args, **kwargs):
                if os.fspath(p_arg) == str(db):
                    lstat_calls["n"] += 1
                    if lstat_calls["n"] >= 3:
                        return os.stat_result((0o120777, 0, 0, 1, 0, 0, 0, 0, 0, 0))
                return real_lstat(p_arg, *args, **kwargs)

            with mock.patch("os.lstat", side_effect=_swap_after_open):
                self._assert_pi_err(pi.query_sqlite_archive, "NOT_REGULAR_ARCHIVE", db, "optimization_quantization")

            db_err_calls = {"n": 0}

            def _db_lstat_err(p_arg, *args, **kwargs):
                if os.fspath(p_arg) == str(db):
                    db_err_calls["n"] += 1
                    if db_err_calls["n"] >= 2:
                        raise PermissionError("db lstat denied")
                return real_lstat(p_arg, *args, **kwargs)

            with mock.patch("os.lstat", side_effect=_db_lstat_err):
                self._assert_pi_err(pi.query_sqlite_archive, "ARCHIVE_IO_ERROR", db, "optimization_quantization")


class TestCS29ThinCoordinator(unittest.TestCase):
    def _assert_tc_err(self, fn, code: str, *args, **kwargs) -> None:
        with self.assertRaises(tc.ThinCoordinatorError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_05_crossover_exact_boundaries_and_amplification(self) -> None:
        # Exact tie: T=12, B=2120, s=120, c_hit=1/10, W=2400 -> 12*2120/10 = 2544 == 2400 + 12*120/10
        tie = tc.evaluate_thin_coordinator_crossover(
            remaining_turns=12, inline_payload_tokens=2120, summary_tokens=120, worker_cost=2400, inline_lines=40
        )
        self.assertEqual(tie["policy"], "KEEP_INLINE")
        self.assertFalse(tie["base_offload_wins"])
        self.assertEqual(tie["base_savings_q"], "0/1")
        self.assertEqual(tie["base_crossover_payload_tokens_q"], "2120/1")
        self.assertEqual(tie["base_crossover_turns_q"], "12/1")
        self.assertFalse(tie["line_rule_triggered"])

        # +1 token above crossover -> OFFLOAD wins; +1 line -> line_rule_triggered
        above = tc.evaluate_thin_coordinator_crossover(
            remaining_turns=12, inline_payload_tokens=2121, summary_tokens=120, worker_cost=2400, inline_lines=41
        )
        self.assertEqual(above["policy"], "OFFLOAD_TO_EPHEMERAL_WORKER")
        self.assertTrue(above["base_offload_wins"])
        self.assertEqual(above["base_savings_q"], "6/5")
        self.assertTrue(above["line_rule_triggered"])

        # Compaction & cold-miss amplification tips an exact tie!
        amp = tc.evaluate_thin_coordinator_crossover(
            remaining_turns=12,
            inline_payload_tokens=2120,
            summary_tokens=120,
            worker_cost=Fraction(2400, 1),
            c_hit=Fraction(1, 10),
            c_miss=Fraction(3, 1),
            cold_misses=1,
            extra_compactions=1,
            compaction_cost=Fraction(5000, 1),
        )
        self.assertFalse(amp["base_offload_wins"])
        self.assertTrue(amp["amplified_offload_wins"])
        self.assertEqual(amp["compaction_amplification_q"], "11000/1")

        # B == s and B < s: crossover_turns is None
        eq_s = tc.evaluate_thin_coordinator_crossover(
            remaining_turns=10, inline_payload_tokens=100, summary_tokens=100, worker_cost=0
        )
        self.assertIsNone(eq_s["base_crossover_turns_q"])
        self.assertEqual(eq_s["policy"], "KEEP_INLINE")

        self._assert_tc_err(tc.evaluate_thin_coordinator_crossover, "INVALID_INT", remaining_turns=0, inline_payload_tokens=10, summary_tokens=1, worker_cost=1)
        self._assert_tc_err(tc.evaluate_thin_coordinator_crossover, "INVALID_INT", remaining_turns=True, inline_payload_tokens=10, summary_tokens=1, worker_cost=1)
        self._assert_tc_err(tc.evaluate_thin_coordinator_crossover, "INVALID_COST", remaining_turns=1, inline_payload_tokens=10, summary_tokens=1, worker_cost="1")
        self._assert_tc_err(tc.evaluate_thin_coordinator_crossover, "NON_POSITIVE_COST", remaining_turns=1, inline_payload_tokens=10, summary_tokens=1, worker_cost=1, c_hit=0)
        self._assert_tc_err(tc.evaluate_thin_coordinator_crossover, "NEGATIVE_COST", remaining_turns=1, inline_payload_tokens=10, summary_tokens=1, worker_cost=-1)
        self._assert_tc_err(tc.evaluate_thin_coordinator_crossover, "INVALID_INT", remaining_turns=1, inline_payload_tokens=10, summary_tokens=1, worker_cost=1, inline_lines=-1)

    def test_06_transcript_bloat_schemas_boundaries_and_io(self) -> None:
        # Antigravity + Claude + Flat schema lines + exact boundary tests (40 lines & 2400 chars)
        clean_40 = "\n".join(f"l{i}" for i in range(40))
        clean_lines = [
            json.dumps({"type": "USER_INPUT", "content": "hi"}),
            json.dumps({"type": "PLANNER_RESPONSE", "thinking": "x" * 200, "input_tokens": 100, "cache_read_tokens": 300, "output_tokens": 50}),
            json.dumps({"type": "GENERIC", "content": clean_40}),
            json.dumps({"type": "user", "message": {"role": "user", "usage": {"input_tokens": 10, "cache_read_input_tokens": 20, "output_tokens": 5}, "content": [{"type": "text", "text": "note"}]}}),
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "ok"}}),
        ]
        res_clean = tc.analyze_transcript_bloat_lines(clean_lines, max_inline_ratio_q=Fraction(1, 2))
        self.assertEqual(res_clean["status"], "CLEAN")
        self.assertEqual(res_clean["counts"]["inline_bloat_events"], 0)
        self.assertEqual(res_clean["counts"]["total_content_bytes"], 2 + 200 + len(clean_40) + 4 + 2)
        self.assertEqual(res_clean["ratios"]["cache_read_ratio_q"], "32/43")

        # Claude tool_result + flat tool role + compaction boundary -> ALERT
        alert_lines = [
            json.dumps({"type": "CHECKPOINT", "content": "cp"}),
            json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "\n".join(f"r{i}" for i in range(41))}]}}),
            json.dumps({"role": "tool", "output": "x" * 2401}),
            json.dumps({"type": "GENERIC", "content": "x" * 2400}),
        ]
        res_alert = tc.analyze_transcript_bloat_lines(alert_lines, max_inline_ratio_q=Fraction(1, 2))
        self.assertEqual(res_alert["status"], "ALERT")
        self.assertEqual(res_alert["counts"]["checkpoint_count"], 1)
        self.assertEqual(res_alert["counts"]["inline_bloat_events"], 2)

        # [MED-11] GENERIC event with Anthropic list-structured content + nested tool_result list
        gen_list_lines = [
            json.dumps({"type": "USER_INPUT", "content": [{"type": "text", "text": "go"}]}),
            json.dumps({
                "type": "GENERIC",
                "content": [{"type": "tool_result", "content": [{"type": "text", "text": "\n".join(f"g{i}" for i in range(41))}]}],
            }),
            json.dumps({
                "type": "assistant",
                "content": [{"type": "tool_result", "content": "x" * 2401}],
            }),
        ]
        res_gen_list = tc.analyze_transcript_bloat_lines(gen_list_lines, max_inline_ratio_q=Fraction(1, 2))
        self.assertEqual(res_gen_list["status"], "ALERT")
        self.assertEqual(res_gen_list["counts"]["tool_output_events"], 2)
        self.assertEqual(res_gen_list["counts"]["inline_bloat_events"], 2)
        self.assertGreater(res_gen_list["counts"]["inline_tool_output_bytes"], 2401)

        # [LOW-7] Mixed text + tool_result blocks keep other_chunks in total_content_bytes denominator
        mixed_lines = [
            json.dumps({
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "p" * 500},
                        {"type": "tool_result", "content": "t" * 40},
                    ],
                },
            }),
        ]
        res_mixed = tc.analyze_transcript_bloat_lines(mixed_lines, max_inline_ratio_q=Fraction(3, 10))
        self.assertEqual(res_mixed["counts"]["total_content_bytes"], 540)
        self.assertEqual(res_mixed["counts"]["inline_tool_output_bytes"], 40)
        self.assertEqual(res_mixed["ratios"]["inline_tool_output_ratio_q"], "2/27")
        self.assertEqual(res_mixed["status"], "CLEAN")

        # WARNING cases: (ratio <= thresh AND bloat > 0) vs (ratio > thresh AND bloat == 0)
        warn_bloat = tc.analyze_transcript_bloat_lines([
            json.dumps({"type": "USER_INPUT", "content": "a" * 5000}),
            json.dumps({"type": "GENERIC", "content": "\n".join(f"b{i}" for i in range(41))}),
        ], max_inline_ratio_q=Fraction(1, 2))
        self.assertEqual(warn_bloat["status"], "WARNING")

        warn_ratio = tc.analyze_transcript_bloat_lines([
            json.dumps({"type": "USER_INPUT", "content": "a"}),
            json.dumps({"type": "GENERIC", "content": "tool ok"}),
        ], max_inline_ratio_q=Fraction(1, 2))
        self.assertEqual(warn_ratio["status"], "WARNING")

        # Exact ratio == threshold is NOT exceeds_ratio_threshold; [0, 1] threshold boundaries pass
        eq_ratio = tc.analyze_transcript_bloat_lines([
            json.dumps({"type": "USER_INPUT", "content": "aaaa"}),
            json.dumps({"type": "GENERIC", "content": "bbbb"}),
        ], max_inline_ratio_q=Fraction(1, 2))
        self.assertFalse(eq_ratio["exceeds_ratio_threshold"])
        self.assertEqual(eq_ratio["status"], "CLEAN")
        self.assertEqual(
            tc.analyze_transcript_bloat_lines([json.dumps({"type": "USER_INPUT", "content": "a"})], max_inline_ratio_q=Fraction(0, 1))["status"],
            "CLEAN",
        )
        self.assertEqual(
            tc.analyze_transcript_bloat_lines([json.dumps({"type": "GENERIC", "content": "b"})], max_inline_ratio_q=Fraction(1, 1))["status"],
            "CLEAN",
        )
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "OUT_OF_RANGE_RATIO", ["{}"], max_inline_ratio_q=Fraction(-1, 2))

        # Negative controls on lines & file I/O
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "EMPTY_TRANSCRIPT", [])
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "INVALID_LABEL", ["{}"], session_label=" ")
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "OUT_OF_RANGE_RATIO", ["{}"], max_inline_ratio_q=Fraction(2, 1))
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "TRANSCRIPT_BLANK_LINE", ["   "])
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "JSON_FLOAT_FORBIDDEN", ['{"x": 1.2}'])
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "JSON_CONSTANT_FORBIDDEN", ['{"x": NaN}'])
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "JSON_DUPLICATE_KEY", ['{"x": 1, "x": 2}'])
        self.assertEqual(tc.analyze_transcript_bloat_lines(['{"x": ' + ("9" * 1024) + "}"])["status"], "CLEAN")
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "JSON_INT_TOO_LONG", ['{"x": ' + ("9" * 1025) + "}"])
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "JSON_LONE_SURROGATE", ['{"x": "\\ud800"}'])
        self.assertEqual(tc.analyze_transcript_bloat_lines(['{"a":' * 64 + "1" + "}" * 64])["status"], "CLEAN")
        self.assertEqual(tc.analyze_transcript_bloat_lines(['{"a":' + "[" * 63 + "1" + "]" * 63 + "}"])["status"], "CLEAN")
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "JSON_DEPTH_EXCEEDED", ['{"a":' + "[" * 64 + "1" + "]" * 64 + "}"])
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "JSON_DEPTH_EXCEEDED", ['{"a":' * 65 + "1" + "}" * 65])
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "TRANSCRIPT_NOT_OBJECT", ["[1, 2]"])
        self._assert_tc_err(tc.analyze_transcript_bloat_lines, "INVALID_TRANSCRIPT_JSONL", ["{bad"])
        self.assertEqual(tc.analyze_transcript_bloat_lines(['{"x": 1.2}'], allow_float=True)["status"], "CLEAN")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ok = _write_lf(root / "ok.jsonl", (clean_lines[0] + "\n").encode("utf-8"))
            self.assertEqual(tc.analyze_transcript_bloat(ok, max_file_bytes=ok.stat().st_size)["status"], "CLEAN")
            ls_u2028 = _write_lf(
                root / "u2028.jsonl",
                (json.dumps({"type": "USER_INPUT", "content": "a\u2028b\x0bc"}, ensure_ascii=False) + "\n").encode("utf-8"),
            )
            res_u2028 = tc.analyze_transcript_bloat(ls_u2028)
            self.assertEqual(res_u2028["counts"]["total_events"], 1)
            self.assertEqual(res_u2028["counts"]["total_content_lines"], 1)
            self._assert_tc_err(tc.analyze_transcript_bloat, "INVALID_PATH", 123)
            self._assert_tc_err(tc.analyze_transcript_bloat, "INVALID_PATH", Path("."))
            self._assert_tc_err(tc.analyze_transcript_bloat, "IO_ERROR", root / "missing.jsonl")
            d = root / "dir"
            d.mkdir()
            self._assert_tc_err(tc.analyze_transcript_bloat, "NOT_REGULAR_FILE", d)
            bom = _write_lf(root / "bom.jsonl", b"\xef\xbb\xbf{}\n")
            self._assert_tc_err(tc.analyze_transcript_bloat, "TRANSCRIPT_BOM_FORBIDDEN", bom)
            crlf = _write_lf(root / "crlf.jsonl", b"{}\r\n")
            self._assert_tc_err(tc.analyze_transcript_bloat, "TRANSCRIPT_CRLF_FORBIDDEN", crlf)
            badu = _write_lf(root / "u.jsonl", b"\xff\n")
            self._assert_tc_err(tc.analyze_transcript_bloat, "INVALID_UTF8", badu)
            self._assert_tc_err(tc.analyze_transcript_bloat, "TRANSCRIPT_TOO_LARGE", ok, max_file_bytes=4)


class TestEXPQ46bLeanAuditHardening(unittest.TestCase):
    def _assert_lah_err(self, fn, code: str, *args, **kwargs) -> None:
        with self.assertRaises(lah.LeanAuditHardeningError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_07_exp_q46b_bypass_suite_and_lexer_edges(self) -> None:
        suite = lah.run_exp_q46b_bypass_suite()
        self.assertTrue(suite["passed"])
        self.assertEqual(suite["checks_passed"], suite["checks_total"])

        # Lexer edge cases: nested comments, raw strings, char literals, guillemets, unterminated
        src = '/- outer /- inner sorry -/ still -/\ndef c : Char := \'"\'\ndef r := r#"/- sorry"#\ndef «ok_id» := 1\n'
        cleaned, lf = lah.strip_lean4_comments_and_literals(src)
        self.assertEqual(lf, [])
        self.assertNotIn("sorry", cleaned)
        self.assertIn("ok_id", cleaned)

        self._assert_lah_err(lah.strip_lean4_comments_and_literals, "INVALID_SOURCE_TYPE", 123)
        _, lf_uc = lah.strip_lean4_comments_and_literals("/- unclosed")
        self.assertEqual(lf_uc[0]["code"], "LEAN4_UNTERMINATED_COMMENT")
        _, lf_us = lah.strip_lean4_comments_and_literals('"unclosed')
        self.assertEqual(lf_us[0]["code"], "LEAN4_UNTERMINATED_STRING")
        _, lf_ur = lah.strip_lean4_comments_and_literals('r#"unclosed')
        self.assertEqual(lf_ur[0]["code"], "LEAN4_UNTERMINATED_STRING")
        _, lf_ug = lah.strip_lean4_comments_and_literals("«unclosed")
        self.assertEqual(lf_ug[0]["code"], "LEAN4_UNTERMINATED_IDENT")

        # [HIGH-1] Interpolated strings (s!"...", m!"...", f!"...") with nested { ... } antiquotations
        smuggle = 'def s : String := s!"{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := s!"{ "-/" }"\n'
        smuggle_res = lah.audit_lean4_source_hardened(smuggle)
        self.assertFalse(smuggle_res["clean"])
        self.assertEqual(smuggle_res["findings"][0]["code"], "LEAN4_SORRY")

        for variant in (
            'def m : String := m!"{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := m!"{ "-/" }"\n',
            'def f : String := f!"{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := f!"{ "-/" }"\n',
            'def inner : String := s!"{ sorry }"\n',
            'def nest : String := s!"a { s!"{ "/-" }" } b"\ntheorem fake : False := sorry\n',
            'def s : String := s! "{ "/-" }"\ntheorem bad : False := sorry\ndef t : String := s! "{ "-/" }"\n',
            'def s : String := s! /- c -/ "{ "/-" }"\ntheorem bad : False := sorry\ndef t : String := s! -- c\n"{ "-/" }"\n',
            'def m : String := m! "{ "/-" }"\ntheorem bad : False := sorry\ndef t : String := m! "{ "-/" }"\n',
            'def f : String := f! "{ "/-" }"\ntheorem bad : False := sorry\ndef t : String := f! "{ "-/" }"\n',
            'def p := println! "{ "/-" }"\ntheorem bad : False := sorry\ndef t := println! "{ "-/" }"\n',
            'def d := dbg_trace "{ "/-" }"; 0\ntheorem bad : False := sorry\ndef t := dbg_trace "{ "-/" }"; 0\n',
            'def badPrefix : Bool := !s!"{ "/-" }".isEmpty\ntheorem bad_nh1 : False := sorry\ndef badPrefix2 : Bool := !s!"{ "-/" }".isEmpty\n',
            'def b2 : Bool := !!s!"{ "/-" }".isEmpty\ntheorem bad_nh2 : False := sorry\ndef b3 : Bool := !!s!"{ "-/" }".isEmpty\n',
            'def q := custom!"{ "/-" }"\ntheorem bad_custom : False := sorry\ndef q2 := custom!"{ "-/" }"\n',
            'def g1 := «foo»sorry\n',
            'def g2 := foo«sorry»\n',
        ):
            vres = lah.audit_lean4_source_hardened(variant)
            self.assertFalse(vres["clean"])
            self.assertEqual(vres["findings"][0]["code"], "LEAN4_SORRY")

        # [HIGH-2] stop tactic, _root_.sorryAx, _root_.«sorryAx», decide +native
        for stop_src in (
            "theorem t_stop : False := by stop skip\n",
            "theorem t_stop2 : False := by\n  intro h\n  stop skip\n",
            "theorem t_stop3 : False := by\n  · stop skip\n",
            "theorem t_stop4 : False := by (stop skip)\n",
        ):
            s_res = lah.audit_lean4_source_hardened(stop_src)
            self.assertFalse(s_res["clean"])
            self.assertEqual(s_res["findings"][0]["code"], "LEAN4_STOP_TACTIC")

        for rs_src in (
            "theorem t_rs : False := _root_.sorryAx False true\n",
            "theorem t_rgs : False := _root_.«sorryAx» False true\n",
            "theorem t_g2 : False := «_root_».«sorryAx» False true\n",
        ):
            r_res = lah.audit_lean4_source_hardened(rs_src)
            self.assertFalse(r_res["clean"])
            self.assertEqual(r_res["findings"][0]["code"], "LEAN4_SORRY_AX")

        for dn_src in (
            "theorem t_dn : 1 + 1 = 2 := by decide +native\n",
            "theorem t_dn2 : 1 + 1 = 2 := by decide +revert +native\n",
            "theorem t_dn3 : 1 + 1 = 2 := by decide (config := { native := true })\n",
            "theorem t_dn4 : 1 + 1 = 2 := by\n  decide\n    +native\n",
        ):
            d_res = lah.audit_lean4_source_hardened(dn_src)
            self.assertFalse(d_res["clean"])
            self.assertEqual(d_res["findings"][0]["code"], "LEAN4_DECIDE_NATIVE")

        # [MED-7] Comparator throwErrorAt / trace[...] / throwNamedError interpolated strings
        for comp_src in (
            'import Lean.Exception\ndef t (stx : Lean.Syntax) := throwErrorAt stx "{ "/-" }"\ntheorem bad_m6 : False := sorry\ndef t2 (stx : Lean.Syntax) := throwErrorAt stx "{ "-/" }"\n',
            'import Lean.Exception\ndef t (stx : Lean.Syntax) := throwErrorAt (stx) "{ "/-" }"\ntheorem bad_m6b : False := sorry\ndef t2 (stx : Lean.Syntax) := throwErrorAt (stx) "{ "-/" }"\n',
            'import Lean.Exception\ndef t (stx : Lean.Syntax) := throwErrorAt /- c -/ stx /- d -/ "{ "/-" }"\ntheorem bad_m6c : False := sorry\ndef t2 (stx : Lean.Syntax) := throwErrorAt stx -- c\n"{ "-/" }"\n',
            'import Lean\ndef t := do\n  trace[Elab] "{ "/-" }"\ntheorem bad_tr : False := sorry\ndef t2 := do\n  trace[Elab] "{ "-/" }"\n',
            'import Lean\ndef t := throwNamedError myErr "{ "/-" }"\ntheorem bad_ne : False := sorry\ndef t2 := throwNamedError myErr "{ "-/" }"\n',
        ):
            c_res = lah.audit_lean4_source_hardened(comp_src, allow_non_init_imports=True)
            self.assertFalse(c_res["clean"])
            self.assertTrue(any(f["code"] == "LEAN4_SORRY" for f in c_res["findings"]))
        self.assertTrue(
            any(
                f["code"] == "LEAN4_SORRY"
                for f in lah.audit_lean4_source_hardened(
                    'import Lean.Exception\ndef t := throwErrorAt (sorry) "{ "/-" }"\n',
                    allow_non_init_imports=True,
                )["findings"]
            )
        )

        # [HIGH-1] syntax/macro/macro_rules/elab, #eval, run_cmd, public import, and [MED-1] multiline @[extern]
        self.assertEqual(
            lah.audit_lean4_source_hardened('syntax "q!" interpolatedStr(term) : term\nmacro_rules | `(q! $s) => `(s! $s)\n')["findings"][0]["code"],
            "LEAN4_SYNTAX_MACRO_ESCAPE",
        )
        self.assertEqual(
            lah.audit_lean4_source_hardened('elab "myelab" : term => sorry\n')["findings"][1]["code"],
            "LEAN4_SYNTAX_MACRO_ESCAPE",
        )
        self.assertEqual(lah.audit_lean4_source_hardened('#eval IO.println "x"\n')["findings"][0]["code"], "LEAN4_HASH_SPOOF")
        self.assertEqual(lah.audit_lean4_source_hardened("run_cmd IO.println 1\n")["findings"][0]["code"], "LEAN4_META_EVAL_ESCAPE")
        self.assertEqual(lah.audit_lean4_source_hardened("public import Init\n")["findings"][0]["code"], "LEAN4_PUBLIC_IMPORT")
        self.assertEqual(
            lah.audit_lean4_source_hardened('@[\nextern "c_evil"\n]\ndef f : Nat := 0\n')["findings"][0]["code"],
            "LEAN4_ATTR_ESCAPE",
        )
        self.assertEqual(
            lah.audit_lean4_source_hardened('opaque f : Nat\nattribute [\nextern "c_evil"\n] f\n')["findings"][0]["code"],
            "LEAN4_ATTR_ESCAPE",
        )
        # [LOW-1] sorry' identifier not FP; [LOW-2] Unicode import; [LOW-3] /--/ doc comment matches Lean 4.36.0
        self.assertTrue(lah.audit_lean4_source_hardened("def sorry' : Nat := 0\n")["clean"])
        self.assertTrue(lah.audit_lean4_source_hardened("/--/\n-/\ndef ok : Nat := 0\n")["clean"])
        self.assertTrue(lah.audit_lean4_source_hardened("import MyProj.α\n", allow_project_imports=("MyProj",))["clean"])
        self.assertEqual(lah.audit_lean4_source_hardened("import MyProj.α\n")["findings"][0]["code"], "LEAN4_NON_INIT_IMPORT")
        self.assertTrue(lah.audit_lean4_source_hardened('def c := s! /- unclosed')["clean"] is False)

        clean_interp = (
            'def a : String := s!"{ /- block with } inside -/ "ok" } { { x := 1 }.x }"\n'
            'def b : String := s!"escaped \\" \\{ end"\n'
            'def g (x : String) : String := x\n'
            'def xs! (x : String) : String := x\n'
            'def «s!» (x : String) : String := x\n'
            'def c := g!"/-"\n'
            'def y1 := xs! ("{")\n'
            'def y2 := Foo.f ("{")\n'
            'def y3 := throwErrorAt stx ("ok")\n'
            'def y4 := throwErrorAt (stx), ("ok")\n'
            'def foo_throwError (x : String) := x\n'
            'def z1 := foo_throwError "{"\n'
            'def z2 := Foo.throwError "{"\n'
            'def z3 := Foo.throwErrorAt stx "{"\n'
            'theorem ok_by : True := by rfl\n'
            'def stop : Nat := 1\n'
            'def useStop : Nat :=\n  stop\n'
            'theorem ok_interp : True := trivial\n'
        )
        # Note: g!"/-" has plain string "/-" which strips cleanly without starting a comment!
        self.assertTrue(lah.audit_lean4_source_hardened(clean_interp)["clean"])

        _, lf_ui = lah.strip_lean4_comments_and_literals('def x := s!"unclosed')
        self.assertEqual(lf_ui[0]["code"], "LEAN4_UNTERMINATED_STRING")
        _, lf_uib = lah.strip_lean4_comments_and_literals('def x := s!"{ 1')
        self.assertEqual(lf_uib[0]["code"], "LEAN4_UNTERMINATED_STRING")

        # Additional imports, partial without theorem, invalid source type
        self._assert_lah_err(lah.audit_lean4_source_hardened, "INVALID_SOURCE_TYPE", 123)
        self.assertEqual(lah.audit_lean4_source_hardened("import Std.Tactic\n")["findings"][0]["code"], "LEAN4_BV_DECIDE_IMPORT")
        self.assertEqual(lah.audit_lean4_source_hardened("import Mathlib.Data.Nat.Basic\n")["findings"][0]["code"], "LEAN4_NON_INIT_IMPORT")
        self.assertTrue(lah.audit_lean4_source_hardened("import MyProj.Core\n", allow_project_imports=("MyProj",))["clean"])
        self.assertEqual(lah.audit_lean4_source_hardened("partial def f (x : Nat) : Nat := f x\n")["findings"][0]["code"], "LEAN4_PARTIAL")

    def test_08_project_comparator_target_audit_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proj = root / "proj"
            proj.mkdir()
            (proj / "lakefile.toml").write_text('name = "p"\n[[require]]\nname = "mathlib"\n', encoding="utf-8")
            (proj / "Core.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
            # Missing manifest for require
            r_mm = lah.audit_lean4_project_hardened(proj)
            self.assertFalse(r_mm["clean"])
            self.assertEqual(r_mm["findings"][0]["code"], "LEAN4_LAKEFILE_MISSING_MANIFEST")

            # Unmanifested require + nonempty manifest + invalid require type
            (proj / "lake-manifest.json").write_text('{"packages": [{"name": "other"}]}\n', encoding="utf-8")
            r_um = lah.audit_lean4_project_hardened(proj)
            codes = {f["code"] for f in r_um["findings"]}
            self.assertIn("LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES", codes)
            self.assertIn("LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE", codes)

            (proj / "lakefile.toml").write_text('require = ""\n', encoding="utf-8")
            self.assertEqual(lah.audit_lean4_project_hardened(proj)["findings"][-1]["code"], "LEAN4_LAKEFILE_INVALID")
            (proj / "lakefile.toml").write_text('[[require]]\nname = 123\n', encoding="utf-8")
            self.assertEqual(lah.audit_lean4_project_hardened(proj)["findings"][-1]["code"], "LEAN4_LAKEFILE_INVALID")

            # [MED-2] srcDir="venv" never skipped by _SKIP_DIRS; invalid/symlink/escaping srcDir flagged
            sd_proj = root / "sd_proj"
            sd_proj.mkdir()
            (sd_proj / "Main.lean").write_text("theorem ok : True := trivial\n", encoding="utf-8")
            (sd_proj / "lakefile.toml").write_text('name = "sd"\n[[lean_lib]]\nname = "Evil"\nsrcDir = "venv"\n', encoding="utf-8")
            (sd_proj / "venv").mkdir()
            (sd_proj / "venv" / "Evil.lean").write_text("theorem bad : False := sorry\n", encoding="utf-8")
            sd_res = lah.audit_lean4_project_hardened(sd_proj)
            self.assertFalse(sd_res["clean"])
            self.assertEqual(sd_res["findings"][0]["code"], "LEAN4_SORRY")

            (sd_proj / "lakefile.toml").write_text('name = "sd"\nsrcDir = 123\n', encoding="utf-8")
            self.assertEqual(lah.audit_lean4_project_hardened(sd_proj)["findings"][0]["code"], "LEAN4_LAKEFILE_INVALID")
            (sd_proj / "lakefile.toml").write_text('name = "sd"\nsrcDir = "../escape"\n', encoding="utf-8")
            self.assertEqual(lah.audit_lean4_project_hardened(sd_proj)["findings"][0]["code"], "LEAN4_LAKEFILE_SRCDIR_ESCAPE")
            (sd_proj / "lakefile.toml").write_text('name = "sd"\nsrcDir = "venv/sym_dir"\n', encoding="utf-8")
            os.symlink(sd_proj / "venv", sd_proj / "venv" / "sym_dir")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "SYMLINK_IN_LEAN_TREE", sd_proj)
            (sd_proj / "venv" / "sym_dir").unlink()
            (sd_proj / "lakefile.toml").write_text('name = "sd"\nsrcDir = "venv/Evil.lean"\n', encoding="utf-8")
            self.assertTrue(lah.audit_lean4_project_hardened(sd_proj)["clean"])
            (sd_proj / "lakefile.toml").write_text('name = "sd"\nsrcDir = "missing"\n', encoding="utf-8")
            self.assertTrue(lah.audit_lean4_project_hardened(sd_proj)["clean"])
            (sd_proj / "lakefile.toml").write_text('name = "sd"\nsrcDir = "venv/missing"\n', encoding="utf-8")
            self.assertTrue(lah.audit_lean4_project_hardened(sd_proj)["clean"])
            (sd_proj / "lakefile.toml").write_text('name = "sd"\nsrcDir = "venv\\u0000x"\n', encoding="utf-8")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "INVALID_PATH", sd_proj)

            # [MED-3] & [MED-4] roots=["venv.Evil"], globs, leanOptions, moreLeanArgs, precompileModules, lakefile.lean srcDir
            roots_proj = root / "roots_proj"
            roots_proj.mkdir()
            (roots_proj / "Main.lean").write_text("theorem ok : True := trivial\n", encoding="utf-8")
            (roots_proj / "venv").mkdir()
            (roots_proj / "venv" / "Evil.lean").write_text("theorem bad : False := sorry\n", encoding="utf-8")
            (roots_proj / "lakefile.toml").write_text('name = "rp"\n[[lean_lib]]\nname = "Evil"\nroots = ["venv.Evil"]\n', encoding="utf-8")
            rp_res = lah.audit_lean4_project_hardened(roots_proj)
            self.assertFalse(rp_res["clean"])
            rp_codes = {f["code"] for f in rp_res["findings"]}
            self.assertIn("LEAN4_LAKEFILE_SKIPPED_ROOT", rp_codes)
            self.assertIn("LEAN4_SORRY", rp_codes)

            for bad_toml in (
                'name = "rp"\nmoreLeanArgs = ["--quiet"]\n',
                'name = "rp"\n[[lean_lib]]\nname = "L"\nleanOptions = { "foo" = true }\n',
                'name = "rp"\ncustomOpt = { "debug.byAsSorry" = true }\n',
                'name = "rp"\ncustomStr = "-Ddebug.byAsSorry=true"\n',
                'name = "rp"\nprecompileModules = true\n[[lean_lib]]\nname = "Evil"\nglobs = [{submodules = "venv"}]\n',
            ):
                (roots_proj / "lakefile.toml").write_text(bad_toml, encoding="utf-8")
                opt_res = lah.audit_lean4_project_hardened(roots_proj)
                self.assertFalse(opt_res["clean"])
                self.assertIn("LEAN4_LAKEFILE_UNSAFE_OPTION", {f["code"] for f in opt_res["findings"]})

            (roots_proj / "lakefile.toml").write_text('name = "rp"\n[[lean_lib]]\nname = "L"\nroots = 123\n', encoding="utf-8")
            self.assertIn("LEAN4_LAKEFILE_INVALID", {f["code"] for f in lah.audit_lean4_project_hardened(roots_proj)["findings"]})
            (roots_proj / "lakefile.toml").write_text('name = "rp"\n[[lean_lib]]\nname = "L"\nroots = [".*"]\n', encoding="utf-8")
            self.assertIn("LEAN4_LAKEFILE_INVALID", {f["code"] for f in lah.audit_lean4_project_hardened(roots_proj)["findings"]})
            (roots_proj / "lakefile.toml").write_text('name = "rp"\n[[lean_lib]]\nname = "L"\nroots = ["../evil"]\n', encoding="utf-8")
            self.assertIn("LEAN4_LAKEFILE_SRCDIR_ESCAPE", {f["code"] for f in lah.audit_lean4_project_hardened(roots_proj)["findings"]})
            (roots_proj / "lakefile.toml").write_text('name = "rp"\n[[lean_lib]]\nname = "L"\nroots = ["bad\\u0000mod"]\n', encoding="utf-8")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "INVALID_PATH", roots_proj)
            os.symlink(roots_proj / "venv" / "Evil.lean", roots_proj / "venv" / "SymEvil.lean")
            (roots_proj / "lakefile.toml").write_text('name = "rp"\n[[lean_lib]]\nname = "L"\nroots = ["venv.SymEvil"]\n', encoding="utf-8")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "SYMLINK_IN_LEAN_TREE", roots_proj)
            (roots_proj / "venv" / "SymEvil.lean").unlink()

            lf_lean_proj = root / "lf_lean_proj"
            lf_lean_proj.mkdir()
            (lf_lean_proj / "Main.lean").write_text("theorem ok : True := trivial\n", encoding="utf-8")
            (lf_lean_proj / "venv").mkdir()
            (lf_lean_proj / "venv" / "Evil.lean").write_text("theorem bad : False := sorry\n", encoding="utf-8")
            (lf_lean_proj / "lakefile.lean").write_text(
                'import Lake\nopen Lake DSL\npackage p where\n  moreLeanArgs := #["-Ddebug.byAsSorry=true"]\nlean_lib Evil where\n  srcDir := "venv"\n  roots := #[`venv.Evil]\n',
                encoding="utf-8",
            )
            lfl_res = lah.audit_lean4_project_hardened(lf_lean_proj, allow_non_init_imports=True)
            lfl_codes = {f["code"] for f in lfl_res["findings"]}
            self.assertNotIn("LEAN4_LAKEFILE_INVALID", lfl_codes)
            self.assertIn("LEAN4_LAKEFILE_UNSAFE_OPTION", lfl_codes)
            self.assertIn("LEAN4_LAKEFILE_SKIPPED_ROOT", lfl_codes)
            self.assertIn("LEAN4_SORRY", lfl_codes)
            (lf_lean_proj / "lakefile.lean").write_text('def srcDir := someVar\n', encoding="utf-8")
            self.assertIn("LEAN4_LAKEFILE_INVALID", {f["code"] for f in lah.audit_lean4_project_hardened(lf_lean_proj)["findings"]})
            (lf_lean_proj / "lakefile.lean").write_text('def srcDir := "  "\n', encoding="utf-8")
            self.assertIn("LEAN4_LAKEFILE_INVALID", {f["code"] for f in lah.audit_lean4_project_hardened(lf_lean_proj)["findings"]})
            (lf_lean_proj / "lakefile.lean").write_text('def srcDir := "../escape"\n', encoding="utf-8")
            self.assertIn("LEAN4_LAKEFILE_SRCDIR_ESCAPE", {f["code"] for f in lah.audit_lean4_project_hardened(lf_lean_proj)["findings"]})

            (proj / "lake-manifest.json").write_text('{"packages": "not_list"}\n', encoding="utf-8")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "LEAN4_LAKE_MANIFEST_INVALID", proj)
            (proj / "lake-manifest.json").write_text('{"packages": []}\n', encoding="utf-8")

            # Bad TOML lakefile
            (proj / "lakefile.toml").write_text("bad = [\n", encoding="utf-8")
            self.assertEqual(lah.audit_lean4_project_hardened(proj)["findings"][-1]["code"], "LEAN4_LAKEFILE_INVALID")

            # Clean project + comparator check + CLI rc=0
            clean_p = root / "clean_p"
            clean_p.mkdir()
            (clean_p / "Challenge.lean").write_text("theorem goal_thm : True := trivial\n", encoding="utf-8")
            (clean_p / "Solution.lean").write_text("theorem goal_thm : True := trivial\n", encoding="utf-8")
            (clean_p / "lakefile.toml").write_text('name = "clean_p"\n', encoding="utf-8")
            (clean_p / "lake-manifest.json").write_text('{"packages": []}\n', encoding="utf-8")
            cfg = clean_p / "config.json"
            cfg.write_text(
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Solution",
                    "theorem_names": ["goal_thm"],
                    "permitted_axioms": ["propext", "Quot.sound"],
                    "enable_nanoda": True,
                }) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(lah.audit_lean4_project_hardened(clean_p)["clean"])
            self.assertTrue(lah.validate_comparator_config_hardened(cfg, lean_root=clean_p)["passed"])
            buf_ok, buf_err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf_ok), redirect_stderr(buf_err):
                self.assertEqual(lah.main(["--audit", str(clean_p), "--comparator-config", str(cfg), "--json"]), 0)

            # Comparator structural failures
            cfg_arr = _write_lf(root / "cfg_arr.json", b"[]\n")
            self._assert_lah_err(lah.validate_comparator_config_hardened, "INVALID_COMPARATOR_CONFIG", cfg_arr)
            cfg_same = _write_lf(
                root / "cfg_same.json",
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Challenge",
                    "theorem_names": [],
                    "permitted_axioms": "bad",
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            same_res = lah.validate_comparator_config_hardened(cfg_same, lean_root=clean_p)
            self.assertIn("CHALLENGE_EQUALS_SOLUTION", same_res["errors"])
            self.assertIn("INVALID_THEOREM_NAMES", same_res["errors"])
            self.assertIn("INVALID_PERMITTED_AXIOMS", same_res["errors"])

            cfg_miss = _write_lf(
                root / "cfg_miss.json",
                json.dumps({
                    "challenge_module": 123,
                    "solution_module": "MissingMod",
                    "theorem_names": ["t"],
                    "permitted_axioms": [],
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            miss_res = lah.validate_comparator_config_hardened(cfg_miss, lean_root=clean_p)
            self.assertIn("INVALID_CHALLENGE_MODULE", miss_res["errors"])

            cfg_bad_sol = _write_lf(
                root / "cfg_bad_sol.json",
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "NoSuchMod",
                    "theorem_names": ["t"],
                    "permitted_axioms": [],
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            self.assertIn("MISSING_SOLUTION_FILE", lah.validate_comparator_config_hardened(cfg_bad_sol, lean_root=clean_p)["errors"])

            cfg_bad_mod = _write_lf(
                root / "cfg_bad_mod.json",
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": ".bad",
                    "theorem_names": ["t"],
                    "permitted_axioms": [],
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            self.assertIn("INVALID_SOLUTION_MODULE", lah.validate_comparator_config_hardened(cfg_bad_mod, lean_root=clean_p)["errors"])

            # Solution importing Challenge + nonstandard axiom + nanoda disabled
            (clean_p / "Solution.lean").write_text("import Challenge\ntheorem goal_thm : False := sorry\n", encoding="utf-8")
            bad_cfg = clean_p / "bad_cfg.json"
            bad_cfg.write_text(
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Solution",
                    "theorem_names": ["goal_thm"],
                    "permitted_axioms": ["MyAx"],
                    "enable_nanoda": False,
                }) + "\n",
                encoding="utf-8",
            )
            bad_res = lah.validate_comparator_config_hardened(bad_cfg, lean_root=clean_p)
            self.assertFalse(bad_res["passed"])
            self.assertIn("SOLUTION_IMPORTS_CHALLENGE", bad_res["errors"])
            self.assertIn("NONSTANDARD_AXIOMS:MyAx", bad_res["errors"])
            self.assertIn("NANODA_DISABLED:False", bad_res["errors"])

            # [MED-7] & [MED-8] & [LOW-22/23]: default lean_root, transitive imports, Challenge checks, no Path.resolve()
            comp_ok_p = root / "comp_ok_p"
            comp_ok_p.mkdir()
            (comp_ok_p / "Challenge.lean").write_text("theorem goal_thm : True := trivial\n", encoding="utf-8")
            (comp_ok_p / "Solution.lean").write_text("theorem goal_thm : True := trivial\n", encoding="utf-8")
            comp_ok_cfg = _write_lf(
                comp_ok_p / "config.json",
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Solution",
                    "theorem_names": ["goal_thm"],
                    "permitted_axioms": ["propext", "Quot.sound"],
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            with mock.patch.object(Path, "resolve", side_effect=AssertionError("resolve must not be called")):
                self.assertTrue(lah.validate_comparator_config_hardened(comp_ok_cfg)["passed"])
            self._assert_lah_err(lah.validate_comparator_config_hardened, "INVALID_PATH", comp_ok_cfg, lean_root=123)
            self._assert_lah_err(lah.validate_comparator_config_hardened, "INVALID_PATH", comp_ok_cfg, lean_root="bad\x00root")

            miss_both = root / "miss_both"
            miss_both.mkdir()
            mb_cfg = _write_lf(
                miss_both / "cfg.json",
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Solution",
                    "theorem_names": ["t"],
                    "permitted_axioms": [],
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            mb_res = lah.validate_comparator_config_hardened(mb_cfg)
            self.assertIn("MISSING_CHALLENGE_FILE", mb_res["errors"])
            self.assertIn("MISSING_SOLUTION_FILE", mb_res["errors"])

            trans_p = root / "trans_p"
            trans_p.mkdir()
            (trans_p / "Challenge.lean").write_text("theorem goal_thm : True := trivial\n", encoding="utf-8")
            (trans_p / "Helper.lean").write_text("import Challenge\ntheorem h_bad : False := sorry\n", encoding="utf-8")
            (trans_p / "Solution.lean").write_text("import Helper\ntheorem goal_thm : True := trivial\n", encoding="utf-8")
            trans_cfg = _write_lf(
                trans_p / "cfg.json",
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Solution",
                    "theorem_names": ["goal_thm"],
                    "permitted_axioms": [],
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            trans_res = lah.validate_comparator_config_hardened(trans_cfg)
            self.assertFalse(trans_res["passed"])
            self.assertIn("SOLUTION_IMPORTS_CHALLENGE", trans_res["errors"])
            self.assertTrue(any(e.startswith("TRANSITIVE_SOLUTION_ESCAPE:Helper:LEAN4_SORRY") for e in trans_res["errors"]))

            # [MED-5] Symlinked or missing transitive Helper.lean must fail closed (never continue)
            sym_trans_p = root / "sym_trans_p"
            sym_trans_p.mkdir()
            (sym_trans_p / "Challenge.lean").write_text("theorem goal_thm : True := trivial\n", encoding="utf-8")
            (sym_trans_p / "EvilOutside.lean").write_text("theorem h_bad : False := sorry\n", encoding="utf-8")
            os.symlink(sym_trans_p / "EvilOutside.lean", sym_trans_p / "Helper.lean")
            (sym_trans_p / "Solution.lean").write_text("import Helper\ntheorem goal_thm : True := trivial\n", encoding="utf-8")
            sym_trans_cfg = _write_lf(
                sym_trans_p / "cfg.json",
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Solution",
                    "theorem_names": ["goal_thm"],
                    "permitted_axioms": [],
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            sym_trans_res = lah.validate_comparator_config_hardened(sym_trans_cfg)
            self.assertFalse(sym_trans_res["passed"])
            self.assertIn("UNREADABLE_TRANSITIVE_SOLUTION_MODULE:Helper:SYMLINK_MODULE:Helper", sym_trans_res["errors"])
            (sym_trans_p / "Helper.lean").unlink()
            miss_trans_res = lah.validate_comparator_config_hardened(sym_trans_cfg)
            self.assertFalse(miss_trans_res["passed"])
            self.assertIn("MISSING_TRANSITIVE_SOLUTION_MODULE:Helper", miss_trans_res["errors"])
            (sym_trans_p / "Solution.lean").unlink()
            os.symlink(sym_trans_p / "EvilOutside.lean", sym_trans_p / "Solution.lean")
            sym_sol_res = lah.validate_comparator_config_hardened(sym_trans_cfg)
            self.assertFalse(sym_sol_res["passed"])
            self.assertIn("UNREADABLE_SOLUTION_FILE:SYMLINK_MODULE:Solution", sym_sol_res["errors"])

            chl_bad_p = root / "chl_bad_p"
            chl_bad_p.mkdir()
            (chl_bad_p / "Challenge.lean").write_text("theorem goal_thm : False := sorry\n", encoding="utf-8")
            (chl_bad_p / "Solution.lean").write_text("theorem goal_thm : True := trivial\n", encoding="utf-8")
            cb_cfg = _write_lf(
                chl_bad_p / "cfg.json",
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Solution",
                    "theorem_names": ["goal_thm"],
                    "permitted_axioms": [],
                    "enable_nanoda": True,
                }).encode("utf-8"),
            )
            self.assertTrue(any(e.startswith("CHALLENGE_ESCAPE:LEAN4_SORRY") for e in lah.validate_comparator_config_hardened(cb_cfg)["errors"]))

            # Project input validation, symlink, fifo, UTF-8, and CRLF rejections
            self._assert_lah_err(lah.audit_lean4_project_hardened, "INVALID_PATH", 123)
            self._assert_lah_err(lah.audit_lean4_project_hardened, "INVALID_PATH", "bad\x00dir")
            txt_f = _write_lf(root / "not_lean.txt", b"hello\n")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "NOT_LEAN_FILE", txt_f)
            fifo_p = root / "pipe"
            os.mkfifo(fifo_p)
            self._assert_lah_err(lah.audit_lean4_project_hardened, "INVALID_LEAN_TARGET", fifo_p)
            sym = root / "sym_p"
            os.symlink(clean_p, sym)
            self._assert_lah_err(lah.audit_lean4_project_hardened, "SYMLINK_TARGET_FORBIDDEN", sym)
            sym_dir = root / "sym_dir"
            sym_dir.mkdir()
            os.symlink(clean_p / "Challenge.lean", sym_dir / "Link.lean")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "SYMLINK_IN_LEAN_TREE", sym_dir)
            bad_utf = _write_lf(root / "badu.lean", b"\xff\n")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "INVALID_UTF8", bad_utf)
            crlf_f = _write_lf(root / "crlf.lean", b"theorem x : True := trivial\r\n")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "LEAN4_CRLF_LINE_ENDINGS", crlf_f)

            # [LOW-3] & [LOW-4]: os.scandir OSError, lakefile.toml / Solution.lean UTF-8, lake-manifest allow_float=False
            with mock.patch("os.scandir", side_effect=OSError("perm denied")):
                self._assert_lah_err(lah.audit_lean4_project_hardened, "LEAN_TREE_IO_ERROR", clean_p)

            bad_toml_proj = root / "bad_toml_proj"
            bad_toml_proj.mkdir()
            (bad_toml_proj / "Main.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
            (bad_toml_proj / "lakefile.toml").write_bytes(b"\xff\xfe\n")
            self._assert_lah_err(lah.audit_lean4_project_hardened, "INVALID_UTF8", bad_toml_proj)

            flt_man_proj = root / "flt_man_proj"
            flt_man_proj.mkdir()
            (flt_man_proj / "Main.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
            (flt_man_proj / "lake-manifest.json").write_bytes(b'{"packages": [], "ver": 1.5}\n')
            self._assert_lah_err(lah.audit_lean4_project_hardened, "JSON_FLOAT_FORBIDDEN", flt_man_proj)

            bad_sol_proj = root / "bad_sol_proj"
            bad_sol_proj.mkdir()
            (bad_sol_proj / "Challenge.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
            (bad_sol_proj / "Solution.lean").write_bytes(b"\xff\xfe\n")
            (bad_sol_proj / "cfg.json").write_text(
                json.dumps({
                    "challenge_module": "Challenge",
                    "solution_module": "Solution",
                    "theorem_names": ["t"],
                    "permitted_axioms": [],
                    "enable_nanoda": True,
                }) + "\n",
                encoding="utf-8",
            )
            self._assert_lah_err(lah.validate_comparator_config_hardened, "INVALID_UTF8", bad_sol_proj / "cfg.json", lean_root=bad_sol_proj)

            # TargetAudit checks ([MED-5], [MED-6], [LOW-1/2/13])
            self._assert_lah_err(lah.audit_target_audit_source, "EMPTY_TARGET_AUDIT", " ")
            ta_rc = lah.audit_target_audit_source(
                "withImportModules imports {loadExts := true}\nlet _ := mod.constNames\ncollectAxioms `a\n"
            )
            self.assertEqual(ta_rc["errors"], ["TARGET_AUDIT_UNSAFE_ELAB_EXTS"])
            ta_med5 = lah.audit_target_audit_source(
                "withImportModules imports {loadExts:=true}\ndef x:=constNames\ndef y:=collectAxioms\n"
            )
            self.assertFalse(ta_med5["passed"])
            self.assertIn("TARGET_AUDIT_UNSAFE_ELAB_EXTS", ta_med5["errors"])
            self.assertIn("MISSING_SERIALIZED_CONSTNAMES_CHECK", ta_med5["errors"])
            self.assertIn("MISSING_COLLECT_AXIOMS", ta_med5["errors"])
            ta_bad = lah.audit_target_audit_source("def x := 1\n")
            self.assertFalse(ta_bad["passed"])
            self.assertIn("MISSING_WITH_IMPORT_MODULES", ta_bad["errors"])
            self.assertIn("MISSING_SERIALIZED_CONSTNAMES_CHECK", ta_bad["errors"])
            self.assertIn("MISSING_COLLECT_AXIOMS", ta_bad["errors"])
            ta_bypass = lah.audit_target_audit_source(
                "-- withImportModules mod.constNames collectAxioms `a\nrun_cmd\n-- loadExts := false\n"
            )
            self.assertFalse(ta_bypass["passed"])
            self.assertIn("MISSING_WITH_IMPORT_MODULES", ta_bypass["errors"])
            self.assertIn("TARGET_AUDIT_UNSAFE_ELAB_EXTS", ta_bypass["errors"])
            self.assertIn("MISSING_SERIALIZED_CONSTNAMES_CHECK", ta_bypass["errors"])
            self.assertIn("MISSING_COLLECT_AXIOMS", ta_bypass["errors"])
            ta_esc = lah.audit_target_audit_source(
                "withImportModules imports {loadExts := false}\nlet _ := mod.constNames\ncollectAxioms `a\ntheorem x := sorry\n"
            )
            self.assertIn("TARGET_AUDIT_ESCAPE:LEAN4_SORRY", ta_esc["errors"])
            ta_unclosed = lah.audit_target_audit_source("/- unclosed\nwithImportModules loadExts := false mod.constNames collectAxioms `a\n")
            self.assertFalse(ta_unclosed["passed"])
            self.assertIn("TARGET_AUDIT_LEX:LEAN4_UNTERMINATED_COMMENT", ta_unclosed["errors"])
            ta_ok = lah.audit_target_audit_source(
                "-- ok\nrun_cmd do\n  let _ ← withImportModules #[{module := `M}] {} (loadExts := false)\n  let _ := mod.constNames\n  collectAxioms `a\n"
            )
            self.assertTrue(ta_ok["passed"])

            # [MED-6] {loadExts := (true)} & dead-definition splitting must fail
            ta_parens = lah.audit_target_audit_source(
                "def dead1 := withImportModules imports {loadExts := false}\n"
                "def real := withImportModules imports {loadExts := (true)}\n"
                "let _ := mod.constNames\ncollectAxioms `a\n"
            )
            self.assertFalse(ta_parens["passed"])
            self.assertIn("TARGET_AUDIT_UNSAFE_ELAB_EXTS", ta_parens["errors"])
            ta_split = lah.audit_target_audit_source(
                "def dead1 := withImportModules\ndef dead2 := { loadExts := false }\nlet _ := mod.constNames\ncollectAxioms `a\n"
            )
            self.assertFalse(ta_split["passed"])
            self.assertIn("TARGET_AUDIT_UNSAFE_ELAB_EXTS", ta_split["errors"])
            ta_stop = lah.audit_target_audit_source(
                "withImportModules imports {loadExts := false}\nlet _ := mod.constNames\ncollectAxioms `a\ntheorem x : False := by stop skip\n"
            )
            self.assertIn("TARGET_AUDIT_ESCAPE:LEAN4_STOP_TACTIC", ta_stop["errors"])

            # [LOW-8] audit_target_audit_log rejects str or non-collection iterables cleanly
            dummy_log = 'ALL-OWNED-JSON {"tag":"passed","modules":0,"declarations":0,"raw_declarations":0}\n'
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_EXPECTED_MODULES",
                dummy_log,
                expected_modules="AB",
                required_decls=("ModA.thm",),
            )
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_EXPECTED_MODULES",
                dummy_log,
                expected_modules=[123],
                required_decls=("ModA.thm",),
            )
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_EXPECTED_MODULES",
                dummy_log,
                expected_modules=["  "],
                required_decls=("ModA.thm",),
            )
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_REQUIRED_DECLS",
                dummy_log,
                expected_modules=("ModA",),
                required_decls=None,
            )
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_EXPECTED_PRIVATE_DECLS",
                dummy_log,
                expected_modules=("ModA",),
                required_decls=("ModA.thm",),
                expected_private_decls="P",
            )
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_ALLOWED_AXIOMS",
                dummy_log,
                expected_modules=("ModA",),
                required_decls=("ModA.thm",),
                allowed_axioms="propext",
            )

            # [MED-6] 0/0/0 vacuous log, subset bypass, unanchored marker, duplicate/foreign constNames, missing private
            vac_res = lah.audit_target_audit_log(
                'ALL-OWNED-JSON {"tag":"passed","modules":0,"declarations":0,"raw_declarations":0}\n',
                expected_modules=(),
                required_decls=(),
            )
            self.assertFalse(vac_res["passed"])
            self.assertIn("EMPTY_EXPECTED_MODULES", vac_res["errors"])
            self.assertIn("EMPTY_REQUIRED_DECLS", vac_res["errors"])
            self.assertIn("VACUOUS_AUDIT_LOG", vac_res["errors"])

            sub_res = lah.audit_target_audit_log(
                "\n".join([
                    'ALL-OWNED-JSON {"tag":"module","module":"M","import_all":true,"has_data":true,"names":["M.other"]}',
                    'ALL-OWNED-JSON {"tag":"declaration","name":"M.req","axioms":[]}',
                    'ALL-OWNED-JSON {"tag":"declaration","name":"M.other","axioms":[]}',
                    'ALL-OWNED-JSON {"tag":"required","name":"M.req"}',
                    'ALL-OWNED-JSON {"tag":"passed","modules":1,"declarations":2,"raw_declarations":1}',
                ]),
                expected_modules=("M",),
                required_decls=("M.req",),
                expected_private_decls=("_private.M.0.priv",),
            )
            self.assertFalse(sub_res["passed"])
            self.assertIn("REQUIRED_DECL_NOT_SERIALIZED", sub_res["errors"])
            self.assertIn("MISSING_PRIVATE_DECLARATION", sub_res["errors"])
            self.assertIn("UNSERIALIZED_DECLARATION", sub_res["errors"])

            dup_for_res = lah.audit_target_audit_log(
                "\n".join([
                    'INFO: ALL-OWNED-JSON {"tag":"ignored"}',
                    'ALL-OWNED-JSON {"tag":"module","module":"M","import_all":true,"has_data":true,"names":["M.a","M.a","Other.x"]}',
                    'ALL-OWNED-JSON {"tag":"declaration","name":"M.a","axioms":[]}',
                    'ALL-OWNED-JSON {"tag":"declaration","name":"Other.x","axioms":[]}',
                    'ALL-OWNED-JSON {"tag":"required","name":"M.a"}',
                    'ALL-OWNED-JSON {"tag":"passed","modules":1,"declarations":2,"raw_declarations":2}',
                ]),
                expected_modules=("M",),
                required_decls=("M.a",),
            )
            self.assertIn("DUPLICATE_CONSTNAME:M", dup_for_res["errors"])
            self.assertIn("FOREIGN_CONSTNAME:M", dup_for_res["errors"])
            self.assertIn("SUMMARY_COUNT_MISMATCH", dup_for_res["errors"])

            bool_sum_log = "\n".join([
                'ALL-OWNED-JSON {"tag":"module","module":"M","import_all":true,"has_data":true,"names":["M.a"]}',
                'ALL-OWNED-JSON {"tag":"declaration","name":"M.a","axioms":[]}',
                'ALL-OWNED-JSON {"tag":"required","name":"M.a"}',
                'ALL-OWNED-JSON {"tag":"passed","modules":true,"declarations":true,"raw_declarations":true}',
            ])
            bs_res = lah.audit_target_audit_log(bool_sum_log, expected_modules=("M",), required_decls=("M.a",))
            self.assertFalse(bs_res["passed"])
            self.assertIn("SUMMARY_COUNT_MISMATCH", bs_res["errors"])

            self._assert_lah_err(
                lah.audit_target_audit_log,
                "EMPTY_AUDIT_LOG",
                "  ",
                expected_modules=(),
                required_decls=(),
            )
            self._assert_lah_err(lah.audit_target_audit_log, "INVALID_LOG_RECORD", "ALL-OWNED-JSON []\n", expected_modules=(), required_decls=())
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_OR_DUP_MODULE",
                'ALL-OWNED-JSON {"tag":"module","module":1}\n',
                expected_modules=(),
                required_decls=(),
            )
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_OR_DUP_DECL",
                'ALL-OWNED-JSON {"tag":"declaration","name":1}\n',
                expected_modules=(),
                required_decls=(),
            )
            self._assert_lah_err(
                lah.audit_target_audit_log,
                "INVALID_REQUIRED_DECL",
                'ALL-OWNED-JSON {"tag":"required","name":1}\n',
                expected_modules=(),
                required_decls=(),
            )

            bad_log = "\n".join([
                'ALL-OWNED-JSON {"tag":"module","module":"M","import_all":false,"has_data":false,"names":"bad"}',
                'ALL-OWNED-JSON {"tag":"declaration","name":"M.a","axioms":["BadAxiom"]}',
                'ALL-OWNED-JSON {"tag":"declaration","name":"M.b","axioms":"bad"}',
                'ALL-OWNED-JSON {"tag":"weird"}',
                'ALL-OWNED-JSON {"tag":"passed","modules":99,"declarations":0,"raw_declarations":0}',
            ])
            bl_res = lah.audit_target_audit_log(bad_log, expected_modules=("N",), required_decls=("M.req",))
            self.assertFalse(bl_res["passed"])
            for expected_code in (
                "UNKNOWN_LOG_TAG:'weird'",
                "MODULE_INVENTORY_MISMATCH",
                "REQUIRED_DECL_MISSING",
                "INCOMPLETE_PRIVATE_DATA:M",
                "INVALID_CONSTNAMES:M",
                "INVALID_DECL_AXIOMS:M.b",
                "UNAPPROVED_DECL_AXIOM:M.a",
                "SUMMARY_COUNT_MISMATCH",
            ):
                self.assertIn(expected_code, bl_res["errors"])

            no_sum_log = "\n".join([
                'ALL-OWNED-JSON {"tag":"module","module":"M","import_all":true,"has_data":true,"names":["M.a"]}',
                'ALL-OWNED-JSON {"tag":"declaration","name":"M.a","axioms":["sorryAx"]}',
            ])
            ns_res = lah.audit_target_audit_log(no_sum_log, expected_modules=("M",), required_decls=())
            self.assertIn("FORBIDDEN_AXIOM_IN_LOG:LEAN4_SORRY_AX", ns_res["errors"])
            self.assertIn("MISSING_OR_DUP_PASSED_SUMMARY", ns_res["errors"])

            buf_o, buf_e = io.StringIO(), io.StringIO()
            with redirect_stdout(buf_o), redirect_stderr(buf_e):
                self.assertEqual(lah.main(["--self-test", "--json"]), 0)
                self.assertEqual(lah.main(["--audit", str(root / "nope"), "--json"]), 2)
                self.assertEqual(lah.main(["--audit", str(clean_p), "--comparator-config", str(cfg), "--json"]), 1)


if __name__ == "__main__":
    unittest.main()
