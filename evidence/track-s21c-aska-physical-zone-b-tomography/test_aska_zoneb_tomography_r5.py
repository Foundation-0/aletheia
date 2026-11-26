#!/usr/bin/env python3
"""Assertion-free R5 verification and Zone-B adversarial test suite for Track S21c."""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import aska_zoneb_tomography_audit as audit
import aska_zoneb_tomography_oracle as oracle
from aska_zoneb_tomography_oracle import TomographyError


class EvilDict(dict):
    pass


class EvilList(list):
    pass


class EvilInt(int):
    pass


class EvilStr(str):
    pass


class EvilPath(type(Path())):
    pass


class TestTrackS21cTomography(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cert = audit.build_certificate()

    def test_exact_org_tomography_and_law2b_steelman(self) -> None:
        pay = self.cert["payload"]
        m = pay["org_metrics"]
        self.assertEqual(m["n_public_repos"], 9)
        self.assertEqual(m["total_bare_asserts"], 86)
        self.assertEqual(m["total_const_first_maxmin"], 29)
        self.assertEqual(m["total_all_builtin_maxmin"], 76)
        self.assertEqual(m["total_cert_dict_eq"], 11)
        self.assertEqual(m["total_unguarded_json_load"], 17)
        self.assertEqual(m["family_repo_counts"], {
            "F1_BARE_ASSERT_O_STRIP": 8,
            "F2_NAN_SWALLOW_MAXMIN": 8,
            "F3_ZONEB_CERT_DICT_EQ": 9,
            "F4_ZONEB_UNGUARDED_JSON_IO": 9,
        })
        self.assertEqual(m["family_prevalence_exact"], {
            "F1_BARE_ASSERT_O_STRIP": "8/9",
            "F2_NAN_SWALLOW_MAXMIN": "8/9",
            "F3_ZONEB_CERT_DICT_EQ": "1",
            "F4_ZONEB_UNGUARDED_JSON_IO": "1",
        })
        self.assertEqual(m["total_exposure_cells"], 36)
        self.assertEqual(m["exposed_cells"], 34)
        self.assertEqual(m["clean_cells"], 2)
        self.assertEqual(m["exposure_density_exact"], "17/18")
        self.assertEqual(m["repos_with_all_four_families"], 7)
        self.assertEqual(m["min_families_per_repo"], 3)
        self.assertEqual(m["minimal_shim_hitting_set_size"], 3)
        self.assertEqual(m["minimal_shim_hitting_sets"], [[
            "require_no_assert",
            "strict_finite_clamp",
            "verify_canonical_cert_bytes",
        ]])
        self.assertEqual(m["primitive_closure_shares_exact"], {
            "require_no_assert": "4/17",
            "strict_finite_clamp": "4/17",
            "verify_canonical_cert_bytes": "9/17",
        })
        self.assertEqual(m["co_occurrence_matrix"]["F1_BARE_ASSERT_O_STRIP"]["F2_NAN_SWALLOW_MAXMIN"], 7)
        self.assertEqual(m["co_occurrence_matrix"]["F3_ZONEB_CERT_DICT_EQ"]["F4_ZONEB_UNGUARDED_JSON_IO"], 9)
        # Verify Law-2b micro-shim has strictly 0 exposures
        corpus_map = {r["id"]: r["observed_counts"] for r in pay["minimal_repro_corpus"]}
        self.assertEqual(len(corpus_map), 7)
        self.assertEqual(corpus_map["law2b_hardened_micro_shim"], {
            "bare_assert_count": 0,
            "const_first_maxmin_count": 0,
            "all_builtin_maxmin_count": 0,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        })
        self.assertEqual(corpus_map["repro_fibral_nan_max"]["all_builtin_maxmin_count"], 2)
        self.assertEqual(corpus_map["repro_zoneb_cert_eq_crash"]["cert_dict_eq_count"], 1)

    def test_ast_scanner_positive_and_negative_controls(self) -> None:
        # Unary negative const, guarded try/except vs handler, read_json, saved != cert, fresh != saved,
        # non-eq saved < cert, non-json foo.loads/json.dumps, single-side saved/fresh == other
        src = (
            "import json\n"
            "def f(a, cert, saved, fresh, raw, p, foo, other):\n"
            "    x = max(-1, a)\n"
            "    y = max(a)\n"
            "    z = min(True, a)\n"
            "    w = max(-True, a)\n"
            "    q = foo.loads(raw)\n"
            "    r = json.dumps(a)\n"
            "    try:\n"
            "        d = json.loads(raw)\n"
            "    except ValueError:\n"
            "        d = json.loads(raw)\n"
            "    if read_json(p) != cert:\n"
            "        return 1\n"
            "    if saved != cert or fresh != saved:\n"
            "        return 2\n"
            "    if saved < cert or saved == other or fresh == other:\n"
            "        return 3\n"
            "    assert x > 0\n"
            "    return d, q, r, w, y, z\n"
        )
        c = oracle.scan_python_source_exact(src, "ctrl.py")
        self.assertEqual(c, {
            "bare_assert_count": 1,
            "const_first_maxmin_count": 1,
            "all_builtin_maxmin_count": 4,
            "cert_dict_eq_count": 3,
            "unguarded_json_load_count": 1,
        })
        # Exact MAX_SOURCE_BYTES positive boundary
        self.assertEqual(
            oracle.scan_python_source_exact("#" * oracle.MAX_SOURCE_BYTES, "exact_cap.py")["bare_assert_count"],
            0,
        )
        # Negative controls on scan_python_source_exact
        for bad_src, code in (
            (123, "INVALID_SOURCE"),
            (EvilStr("x = 1"), "INVALID_SOURCE"),
            ("x = 1\x00", "NUL_IN_SOURCE"),
            ("\ud800", "INVALID_UTF8_SOURCE"),
            ("a" * (oracle.MAX_SOURCE_BYTES + 1), "SOURCE_TOO_LARGE"),
            ("def broken(:", "SYNTAX_ERROR"),
        ):
            with self.assertRaises(TomographyError) as cm:
                oracle.scan_python_source_exact(bad_src, "x.py")  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, code)
        for bad_fn in ("", None, EvilStr("x.py")):
            with self.assertRaises(TomographyError) as cm2:
                oracle.scan_python_source_exact("x = 1\n", bad_fn)  # type: ignore[arg-type]
            self.assertEqual(cm2.exception.code, "INVALID_FILENAME")

    def test_oracle_helpers_metrics_and_corpus_negative_controls(self) -> None:
        self.assertEqual(oracle.format_rational(Fraction(4, 2)), "2")
        self.assertEqual(oracle.format_rational(Fraction(3, 4)), "3/4")
        with self.assertRaises(TomographyError) as cm_r:
            oracle.format_rational(1)  # type: ignore[arg-type]
        self.assertEqual(cm_r.exception.code, "INVALID_RATIONAL")
        self.assertEqual(oracle.require_exact_int(5, "x", lo=5, hi=5), 5)
        for bad_i, lo, hi, code in (
            (True, 0, 10, "INVALID_INT"),
            (EvilInt(1), 0, 10, "INVALID_INT"),
            (4, 5, 10, "INT_OUT_OF_RANGE"),
            (11, 5, 10, "INT_OUT_OF_RANGE"),
        ):
            with self.assertRaises(TomographyError) as cm_i:
                oracle.require_exact_int(bad_i, "x", lo=lo, hi=hi)
            self.assertEqual(cm_i.exception.code, code)
        # Clean-repo metrics edge case (0 exposed cells) + partial-family hitting set tie/subset
        zero_row = {
            "repo": "clean-repo",
            "bare_assert_count": 0,
            "const_first_maxmin_count": 0,
            "all_builtin_maxmin_count": 0,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        }
        mz = oracle.compute_exact_org_metrics([zero_row])
        self.assertEqual(mz["exposed_cells"], 0)
        self.assertEqual(mz["primitive_closure_shares_exact"]["require_no_assert"], "0")
        self.assertEqual(mz["minimal_shim_hitting_set_size"], 1)
        self.assertEqual(len(mz["minimal_shim_hitting_sets"]), 3)
        # Invalid rows
        for bad_rows, code in (
            ([], "INVALID_ROWS"),
            (None, "INVALID_ROWS"),
            (EvilList([zero_row]), "INVALID_ROWS"),
            ([None], "INVALID_ROW"),
            ([EvilDict(zero_row)], "INVALID_ROW"),
            ([{**zero_row, "repo": ""}], "INVALID_ROW"),
            ([{**zero_row, "bare_assert_count": True}], "INVALID_INT"),
            ([{**zero_row, "bare_assert_count": -1}], "INT_OUT_OF_RANGE"),
            ([{**zero_row, "const_first_maxmin_count": 2, "all_builtin_maxmin_count": 1}], "INVALID_ROW"),
        ):
            with self.assertRaises(TomographyError) as cm_m:
                oracle.compute_exact_org_metrics(bad_rows)  # type: ignore[arg-type]
            self.assertEqual(cm_m.exception.code, code)
        # Corpus mismatch negative control
        bad_corpus = (dict(oracle.MINIMAL_REPRO_CORPUS[0], expected={"bare_assert_count": 99}),)
        with patch.object(oracle, "MINIMAL_REPRO_CORPUS", bad_corpus):
            with self.assertRaises(TomographyError) as cm_c:
                oracle.verify_minimal_repro_corpus()
            self.assertEqual(cm_c.exception.code, "CORPUS_SCAN_MISMATCH")

    def test_live_repos_dir_verification_and_fail_closed_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            # Build a tiny 1-repo pinned spec pointing into tdir
            sample_code = "import json\ndef f(p, c):\n    assert True\n    return json.loads(p.read_text()) != c\n"
            sample_cert = '{"ok":true}\n'
            rdir = tdir / "demo-repo"
            rdir.mkdir()
            (rdir / "verify.py").write_text(sample_code, encoding="utf-8")
            (rdir / "cert.json").write_text(sample_cert, encoding="utf-8")
            spec_ok = ({
                "repo": "demo-repo",
                "files": ("verify.py",),
                "file_sha256": {"verify.py": hashlib.sha256(sample_code.encode("utf-8")).hexdigest()},
                "cert_path": "cert.json",
                "cert_sha256": hashlib.sha256(sample_cert.encode("utf-8")).hexdigest(),
                "bare_assert_count": 1,
                "const_first_maxmin_count": 0,
                "all_builtin_maxmin_count": 0,
                "cert_dict_eq_count": 0,
                "unguarded_json_load_count": 1,
            },)
            with patch.object(oracle, "PINNED_ASKA_REPOS", spec_ok):
                with patch.object(oracle, "MAX_LIVE_FILE_BYTES", len(sample_code.encode("utf-8"))):
                    res = oracle.verify_live_repos_dir(tdir)
                self.assertEqual(res, {"live_verified": True, "repos_verified": 1, "repos": ["demo-repo"]})
                # CLI --live-dir happy path
                out = io.StringIO()
                with patch("sys.stdout", out):
                    rc = audit.main(["--live-dir", str(tdir)])
                self.assertEqual(rc, 0)
                self.assertTrue(json.loads(out.getvalue())["live_verified"])
                # Missing dir
                with self.assertRaises(TomographyError) as cm1:
                    oracle.verify_live_repos_dir(tdir / "missing")
                self.assertEqual(cm1.exception.code, "LIVE_DIR_NOT_FOUND")
                # Tampered cert SHA ({} hollow attack!)
                (rdir / "cert.json").write_text("{}", encoding="utf-8")
                with self.assertRaises(TomographyError) as cm2:
                    oracle.verify_live_repos_dir(tdir)
                self.assertEqual(cm2.exception.code, "LIVE_CERT_SHA_MISMATCH")
                # Missing cert
                (rdir / "cert.json").unlink()
                with self.assertRaises(TomographyError) as cm3:
                    oracle.verify_live_repos_dir(tdir)
                self.assertEqual(cm3.exception.code, "LIVE_CERT_MISSING")
                (rdir / "cert.json").write_text(sample_cert, encoding="utf-8")
                # Tampered AST count against same file hash
                spec_bad_cnt = ({**spec_ok[0], "bare_assert_count": 2},)
                with patch.object(oracle, "PINNED_ASKA_REPOS", spec_bad_cnt):
                    with self.assertRaises(TomographyError) as cm4:
                        oracle.verify_live_repos_dir(tdir)
                    self.assertEqual(cm4.exception.code, "LIVE_AST_COUNT_MISMATCH")
                # Tampered file SHA
                (rdir / "verify.py").write_text("x = 1\n", encoding="utf-8")
                with self.assertRaises(TomographyError) as cm5:
                    oracle.verify_live_repos_dir(tdir)
                self.assertEqual(cm5.exception.code, "LIVE_FILE_SHA_MISMATCH")
                # Oversized file
                (rdir / "verify.py").write_bytes(b"#" * (oracle.MAX_LIVE_FILE_BYTES + 1))
                with self.assertRaises(TomographyError) as cm6:
                    oracle.verify_live_repos_dir(tdir)
                self.assertEqual(cm6.exception.code, "LIVE_FILE_TOO_LARGE")
                # Missing file
                (rdir / "verify.py").unlink()
                with self.assertRaises(TomographyError) as cm7:
                    oracle.verify_live_repos_dir(tdir)
                self.assertEqual(cm7.exception.code, "LIVE_FILE_MISSING")
                # Missing repo dir
                (rdir / "cert.json").unlink()
                rdir.rmdir()
                with self.assertRaises(TomographyError) as cm8:
                    oracle.verify_live_repos_dir(tdir)
                self.assertEqual(cm8.exception.code, "LIVE_REPO_MISSING")

    def test_zone_b_memory_parser_file_and_cli_controls(self) -> None:
        # In-memory verify_certificate_dict positive + negative
        res = audit.verify_certificate_dict(self.cert)
        self.assertTrue(res["valid"])
        for bad_d, code in (
            ("nothex", "INVALID_DIGEST"),
            ("0" * 63, "INVALID_DIGEST"),
            (123, "INVALID_DIGEST"),
            ("A" * 64, "INVALID_DIGEST"),
            ("0" * 63 + "é", "INVALID_DIGEST"),
            ("0" * 63 + "\ud800", "INVALID_DIGEST"),
        ):
            with self.assertRaises(TomographyError) as cm_dh:
                audit._require_hex64(bad_d, "d")
            self.assertEqual(cm_dh.exception.code, code)
        # Positive exact boundaries for depth, MAX_INT_DIGITS, and _strict_int
        audit.validate_json_tree_iterative([1], max_depth=1)
        audit.validate_json_tree_iterative({"n": 10 ** 999})
        self.assertEqual(audit._strict_int("9" * 1000), 10 ** 1000 - 1)
        self.assertEqual(audit._strict_int("-" + "9" * 1000), -(10 ** 1000 - 1))
        # Depth, int digit limit, bool-as-int re-signed forgery, subclasses, non-str key, float
        with self.assertRaises(TomographyError) as cm_d0:
            audit.validate_json_tree_iterative({}, max_depth=0)
        self.assertEqual(cm_d0.exception.code, "INVALID_DEPTH")
        with self.assertRaises(TomographyError) as cm_db:
            audit.validate_json_tree_iterative({}, max_depth=True)  # type: ignore[arg-type]
        self.assertEqual(cm_db.exception.code, "INVALID_DEPTH")
        deep: Any = 1
        for _ in range(audit.MAX_JSON_DEPTH + 1):
            deep = [deep]
        with self.assertRaises(TomographyError) as cm_dp:
            audit.validate_json_tree_iterative(deep)
        self.assertEqual(cm_dp.exception.code, "JSON_DEPTH_EXCEEDED")
        self.assertEqual(audit._int_digit_len(0), 1)
        self.assertEqual(audit._int_digit_len(-42), 2)
        with self.assertRaises(TomographyError) as cm_big:
            audit.validate_json_tree_iterative({"n": 10 ** 1000})
        self.assertEqual(cm_big.exception.code, "INT_TOO_LARGE")
        with self.assertRaises(TomographyError) as cm_huge:
            audit.validate_json_tree_iterative({"n": 10 ** 5000})
        self.assertEqual(cm_huge.exception.code, "INT_TOO_LARGE")
        for bad_obj, code in (
            ({1: "a"}, "NON_STR_KEY"),
            ({"\ud800": "a"}, "INVALID_UNICODE"),
            ({"a": "\ud800"}, "INVALID_UNICODE"),
            ({"a": 1.5}, "FORBIDDEN_TYPE"),
            ({"a": EvilInt(1)}, "FORBIDDEN_TYPE"),
            ({"a": EvilStr("x")}, "FORBIDDEN_TYPE"),
            ({"a": EvilList([1])}, "FORBIDDEN_TYPE"),
        ):
            with self.assertRaises(TomographyError) as cm_t:
                audit.validate_json_tree_iterative(bad_obj)
            self.assertEqual(cm_t.exception.code, code)
        for bad_root in ([], None, EvilDict(self.cert)):
            with self.assertRaises(TomographyError) as cm_rt:
                audit.verify_certificate_dict(bad_root)
            self.assertEqual(cm_rt.exception.code, "CERT_NOT_DICT")
        # Re-signed bool-as-int forgery + schema + keys + payload type + payload sha + cert sha
        c_bl = copy.deepcopy(self.cert)
        c_bl["payload"]["org_metrics"]["n_public_repos"] = True
        ps = audit.sha256_hex(audit.canonical_json_bytes(c_bl["payload"]))
        c_bl["payload_sha256"] = ps
        c_bl["certificate_sha256"] = audit.sha256_hex(audit.canonical_json_bytes({"schema": c_bl["schema"], "payload": c_bl["payload"], "payload_sha256": ps}))
        with self.assertRaises(TomographyError) as cm_bl:
            audit.verify_certificate_dict(c_bl)
        self.assertEqual(cm_bl.exception.code, "ORACLE_PAYLOAD_MISMATCH")
        c_ek = copy.deepcopy(self.cert)
        c_ek["extra"] = 1
        with self.assertRaises(TomographyError) as cm_ek:
            audit.verify_certificate_dict(c_ek)
        self.assertEqual(cm_ek.exception.code, "CERT_KEYS_MISMATCH")
        c_sc = copy.deepcopy(self.cert)
        c_sc["schema"] = "wrong"
        with self.assertRaises(TomographyError) as cm_sc:
            audit.verify_certificate_dict(c_sc)
        self.assertEqual(cm_sc.exception.code, "SCHEMA_MISMATCH")
        c_pl = copy.deepcopy(self.cert)
        c_pl["payload"] = []
        with self.assertRaises(TomographyError) as cm_pl:
            audit.verify_certificate_dict(c_pl)
        self.assertEqual(cm_pl.exception.code, "PAYLOAD_NOT_DICT")
        c_ps = copy.deepcopy(self.cert)
        c_ps["payload_sha256"] = "0" * 64
        with self.assertRaises(TomographyError) as cm_ps:
            audit.verify_certificate_dict(c_ps)
        self.assertEqual(cm_ps.exception.code, "PAYLOAD_SHA_MISMATCH")
        c_cs = copy.deepcopy(self.cert)
        c_cs["certificate_sha256"] = "0" * 64
        with self.assertRaises(TomographyError) as cm_cs:
            audit.verify_certificate_dict(c_cs)
        self.assertEqual(cm_cs.exception.code, "CERT_SHA_MISMATCH")
        # Strict JSON parser negative controls
        for bad_txt, code in (
            ("", "EMPTY_JSON"),
            ("   ", "EMPTY_JSON"),
            (123, "EMPTY_JSON"),
            ("\ud800", "INVALID_UNICODE"),
            ("[]", "ROOT_NOT_OBJECT"),
            ('{"a": 1.5}', "FLOAT_FORBIDDEN"),
            ('{"a": NaN}', "FLOAT_FORBIDDEN"),
            ('{"a": Infinity}', "FLOAT_FORBIDDEN"),
            ('{"a": 1, "a": 2}', "DUPLICATE_KEY"),
            ('{"a": 1, "\\u0061": 2}', "DUPLICATE_KEY"),
            ('{"a": ' + "9" * 1001 + "}", "INT_TOO_LARGE"),
            ('{"a": ' + "9" * 5000 + "}", "INT_TOO_LARGE"),
            ('{"a": -' + "9" * 1001 + "}", "INT_TOO_LARGE"),
            ('{"a":', "JSON_PARSE_ERROR"),
            ('{"a":' + "[" * 70 + "]" * 70 + "}", "JSON_DEPTH_EXCEEDED"),
        ):
            with self.assertRaises(TomographyError) as cm_j:
                audit.parse_strict_json_text(bad_txt)  # type: ignore[arg-type]
            self.assertEqual(cm_j.exception.code, code)
        with self.assertRaises(TomographyError) as cm_si:
            audit._strict_int("notanint")
        self.assertEqual(cm_si.exception.code, "INVALID_INT")
        with self.assertRaises(TomographyError) as cm_si2:
            audit._strict_int("9" * 1001)
        self.assertEqual(cm_si2.exception.code, "INT_TOO_LARGE")
        self.assertEqual(audit._strict_int("0"), 0)
        # File, symlink, EvilPath, and CLI controls
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            cp = tdir / "cert.json"
            out_w = io.StringIO()
            with patch("sys.stdout", out_w):
                self.assertEqual(audit.main(["--write", str(cp)]), 0)
            out_c = io.StringIO()
            with patch("sys.stdout", out_c):
                self.assertEqual(audit.main(["--check", str(cp)]), 0)
            self.assertTrue(json.loads(out_c.getvalue())["valid"])
            self.assertTrue(audit.check_certificate_file(cp)["valid"])
            self.assertTrue(audit.check_certificate_file(str(cp))["valid"])
            out_s = io.StringIO()
            with patch("sys.stdout", out_s):
                self.assertEqual(audit.main(["--standalone", "--json"]), 0)
            self.assertEqual(out_s.getvalue().encode("ascii"), cp.read_bytes())
            out_b = io.StringIO()
            with patch("sys.stdout", out_b):
                self.assertEqual(audit.main([]), 0)
            self.assertEqual(out_b.getvalue().encode("ascii"), cp.read_bytes())
            # Exact Path subclass rejected!
            for bad_p in ("", None, 123, EvilStr(str(cp)), EvilPath(cp)):
                with self.assertRaises(TomographyError) as cm_bp:
                    audit.check_certificate_file(bad_p)  # type: ignore[arg-type]
                self.assertEqual(cm_bp.exception.code, "INVALID_PATH")
            # CRLF, non-canonical, symlink file & ancestor, missing, dir, invalid utf8, OSError read/write
            crlf = tdir / "crlf.json"
            crlf.write_bytes(cp.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaises(TomographyError) as cm_cr:
                audit.check_certificate_file(crlf)
            self.assertEqual(cm_cr.exception.code, "CRLF_FORBIDDEN")
            pretty = tdir / "pretty.json"
            pretty.write_text(json.dumps(self.cert, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(TomographyError) as cm_pr:
                audit.check_certificate_file(pretty)
            self.assertEqual(cm_pr.exception.code, "NON_CANONICAL_JSON")
            sym = tdir / "sym.json"
            os.symlink(cp, sym)
            with self.assertRaises(TomographyError) as cm_sf:
                audit.check_certificate_file(sym)
            self.assertEqual(cm_sf.exception.code, "SYMLINK_FORBIDDEN")
            rsub = tdir / "rsub"
            rsub.mkdir()
            (rsub / "cert.json").write_bytes(cp.read_bytes())
            sdir = tdir / "sdir"
            os.symlink(rsub, sdir)
            with self.assertRaises(TomographyError) as cm_sd:
                audit.check_certificate_file(sdir / "cert.json")
            self.assertEqual(cm_sd.exception.code, "SYMLINK_FORBIDDEN")
            # S21C-BUG-01 (D1): unnormalized '..' traversal through symlink and symlinked PWD
            with self.assertRaises(TomographyError) as cm_dotdot:
                audit.check_certificate_file(sdir / ".." / "rsub" / "cert.json")
            self.assertEqual(cm_dotdot.exception.code, "SYMLINK_FORBIDDEN")
            with patch.dict(os.environ, {"PWD": str(sdir)}):
                with self.assertRaises(TomographyError) as cm_pwd:
                    audit.check_certificate_file(Path("cert.json"))
                self.assertEqual(cm_pwd.exception.code, "SYMLINK_FORBIDDEN")
            # S21C-BUG-02 (D2): --write to FIFO must fail closed with NOT_A_FILE (no hang), overwrite regular file OK
            fifo = tdir / "pipe.json"
            os.mkfifo(fifo)
            eb_fifo = io.StringIO()
            with patch("sys.stderr", eb_fifo):
                self.assertEqual(audit.main(["--write", str(fifo)]), 2)
            self.assertIn("NOT_A_FILE", eb_fifo.getvalue())
            out_ow = io.StringIO()
            with patch("sys.stdout", out_ow):
                self.assertEqual(audit.main(["--write", str(cp)]), 0)
            # S21C-BUG-03 (D4 & D3): format_rational bit cap boundary & --live-dir PermissionError/OSError
            lim_ok = (1 << oracle.MAX_RATIONAL_BITS) - 1
            lim_bad = 1 << oracle.MAX_RATIONAL_BITS
            self.assertTrue(oracle.format_rational(Fraction(lim_ok, 1)).isdigit())
            self.assertTrue(oracle.format_rational(Fraction(1, lim_ok)).startswith("1/"))
            for huge_q in (Fraction(lim_bad, 1), Fraction(1, lim_bad), Fraction(10**5000, 1), Fraction(1, 10**5000)):
                with self.assertRaises(TomographyError) as cm_rat:
                    oracle.format_rational(huge_q)
                self.assertEqual(cm_rat.exception.code, "RATIONAL_TOO_LARGE")
            with patch.object(Path, "read_bytes", side_effect=PermissionError("denied")):
                with self.assertRaises(TomographyError) as cm_perm:
                    oracle._read_live_bytes(cp, "verify.py")
                self.assertEqual(cm_perm.exception.code, "LIVE_FILE_READ_ERROR")
            with self.assertRaises(TomographyError) as cm_nf:
                audit.check_certificate_file(tdir / "missing.json")
            self.assertEqual(cm_nf.exception.code, "FILE_NOT_FOUND")
            with self.assertRaises(TomographyError) as cm_dr:
                audit.check_certificate_file(tdir)
            self.assertEqual(cm_dr.exception.code, "NOT_A_FILE")
            bad_u8 = tdir / "bad.json"
            bad_u8.write_bytes(b"\xff\xfe\x00")
            with self.assertRaises(TomographyError) as cm_u8:
                audit.check_certificate_file(bad_u8)
            self.assertEqual(cm_u8.exception.code, "INVALID_UTF8")
            with patch.object(Path, "read_bytes", side_effect=OSError("boom")):
                with self.assertRaises(TomographyError) as cm_rd:
                    audit.check_certificate_file(cp)
                self.assertEqual(cm_rd.exception.code, "FILE_READ_ERROR")
            # CLI errors
            for bad_argv, expected_code in (
                (["--bogus"], "INVALID_CLI_ARGS"),
                (["--check"], "INVALID_CLI_ARGS"),
                (["--write"], "INVALID_CLI_ARGS"),
                (["--live-dir"], "INVALID_CLI_ARGS"),
                (["--foo", "bar"], "INVALID_CLI_ARGS"),
                (["--write", str(tdir)], "NOT_A_FILE"),
                (["--write", str(tdir / "no_parent" / "c.json")], "FILE_WRITE_ERROR"),
                (["--write", ""], "INVALID_PATH"),
            ):
                eb = io.StringIO()
                with patch("sys.stderr", eb):
                    rc_e = audit.main(bad_argv)
                self.assertEqual(rc_e, 2)
                self.assertIn(expected_code, eb.getvalue())


if __name__ == "__main__":
    unittest.main()
