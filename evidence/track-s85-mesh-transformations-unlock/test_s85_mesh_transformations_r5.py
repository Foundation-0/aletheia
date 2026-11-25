#!/usr/bin/env python3
"""Assertion-free R5 verification, tamper, Zone-B I/O, and R10+ Lean test suite for Track S85.

Zero bare asserts, zero IEEE-754 floats, zero character-device paths, zero skipped tests in Lean-less CI.
"""
from __future__ import annotations

import copy
import errno
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s85_mesh_transformations_oracle as O  # noqa: E402
import verify_s85_mesh_transformations as V  # noqa: E402


def _resign(cert: dict) -> dict:
    c = copy.deepcopy(cert)
    p_sha = O.sha256_hex(O.canonical_json_bytes(c["payload"]))
    c["payload_sha256"] = p_sha
    env = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": p_sha,
        "payload": c["payload"],
    }
    c["certificate_sha256"] = O.sha256_hex(O.canonical_json_bytes(env))
    return c


class _PathSub(type(Path())):
    pass


class _IntSub(int):
    pass


class _StrSub(str):
    pass


class TestS85OracleAndLinearAlgebra(unittest.TestCase):
    def test_01_linear_algebra_helpers_and_edge_cases(self) -> None:
        # Exact rounding & formatting
        self.assertEqual(O.q_str(Fraction(4, 1)), "4")
        self.assertEqual(O.q_str(Fraction(-1, 4)), "-1/4")
        self.assertEqual(O.dec_from_q(Fraction(1, 2), 0), "1")
        self.assertEqual(O.dec_from_q(Fraction(-1, 2), 0), "-1")
        self.assertEqual(O.dec_from_q(Fraction(-1, 10000), 2), "0.00")
        self.assertEqual(O.dec_from_q(Fraction(1, 4), 2), "0.25")
        self.assertEqual(O.dec_from_q(Fraction(2, 5), 0), "0")

        # Matrix determinant: singular, non-singular, row swap sign
        self.assertEqual(O.mat_det([[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]]), 0)
        self.assertEqual(O.mat_det([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]), -1)
        with self.assertRaises(O.S85Error) as cm_inv:
            O.mat_inv([[Fraction(1), Fraction(1)], [Fraction(1), Fraction(1)]])
        self.assertEqual(cm_inv.exception.code, "SINGULAR_MATRIX")
        # Non-trivial row swap during mat_inv
        inv_sw = O.mat_inv([[Fraction(0), Fraction(1)], [Fraction(2), Fraction(0)]])
        self.assertEqual(inv_sw, [[Fraction(0), Fraction(1, 2)], [Fraction(1), Fraction(0)]])

        # Symmetric Bunch-Kaufman inertia: 1x1 pivots, negative pivot, 2x2 hyperbolic pivot, trailing zero
        self.assertEqual(O.sym_inertia([[Fraction(-2)]]), [0, 1, 0])
        self.assertEqual(O.sym_inertia([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]), [1, 1, 0])
        # 4x4 with 2x2 hyperbolic block at indices (0, 2) + coupling to index 3 + zero row at 1
        h4 = [
            [Fraction(0), Fraction(0), Fraction(1), Fraction(2)],
            [Fraction(0), Fraction(0), Fraction(0), Fraction(0)],
            [Fraction(1), Fraction(0), Fraction(0), Fraction(1)],
            [Fraction(2), Fraction(0), Fraction(1), Fraction(0)],
        ]
        self.assertEqual(O.sym_inertia(h4), [1, 2, 1])
        # 3x3 with 2x2 hyperbolic block at (1, 2) after zero row 0 (exercises pair_r != i)
        h3 = [
            [Fraction(0), Fraction(0), Fraction(0)],
            [Fraction(0), Fraction(0), Fraction(1)],
            [Fraction(0), Fraction(1), Fraction(0)],
        ]
        self.assertEqual(O.sym_inertia(h3), [1, 1, 1])
        # Zero matrix
        self.assertEqual(O.sym_inertia([[Fraction(0), Fraction(0)], [Fraction(0), Fraction(0)]]), [0, 0, 2])

    def test_02_exact_t1_to_t6_and_s83_cross_check(self) -> None:
        cert = O.build_certificate()
        p = cert["payload"]
        t1 = p["t1_line_graph_and_hodge"]
        self.assertEqual(t1["line_graph_vertices"], 28)
        self.assertEqual(t1["line_graph_incident_edges"], 168)
        self.assertEqual(t1["line_graph_disjoint_pairs"], 210)
        self.assertEqual(t1["disjoint_same_operator_tag_bridges"], 18)
        self.assertEqual(t1["disjoint_same_class_and_tag_bridges"], 11)
        self.assertTrue(t1["b1_b2_exact_zero"])
        self.assertTrue(t1["l1_equals_8_identity"])
        self.assertEqual(t1["wall_grad_energy_q"], "13/4")
        self.assertEqual(t1["wall_curl_energy_q"], "11/4")
        self.assertEqual(t1["grad_curl_inner_product_q"], "0")

        t2 = p["t2_signed_laplacian_and_double_cover"]
        self.assertEqual(t2["l0_inertia"], [7, 0, 1])
        self.assertEqual(t2["l_sigma_inertia"], [8, 0, 0])
        self.assertEqual(t2["l_sigma_det_q"], "1841101056")
        self.assertEqual(t2["min_weighted_frustration_cut_q"], "6")
        self.assertEqual(t2["min_unweighted_frustration_cut"], 5)
        self.assertEqual(t2["double_cover_inertia"], [15, 0, 1])
        self.assertTrue(t2["antipodal_resistance_equals_2_lsigma_inv_diag"])
        self.assertTrue(t2["law5_irreducible_double_sheet_connected"])

        t3 = p["t3_obstruction_blowup_surgery"]
        self.assertTrue(t3["isolated_wall_v6_v7_flips_all_6"])
        self.assertEqual(t3["braess_unmasking_wall_v1_v4_delta"], 2)
        self.assertTrue(t3["superadditive_transitive_synergy_emergent_v0_v1_v5"])
        self.assertEqual(t3["all_6_walls_holonomy_ranking"][0], "v6-v7")
        self.assertEqual(t3["all_6_walls_holonomy_ranking"][-1], "v1-v4")
        self.assertEqual(t3["three_step_cascade"][2]["exact_transitive_closures"], 9)

        t4 = p["t4_directed_ceer_loop_schur"]
        self.assertEqual(t4["directional_curvature_asymmetry_q"], "117/40")
        self.assertEqual(t4["transient_boost_over_symmetric_t1_t2_t3_q"], ["17", "65", "145"])
        self.assertEqual(t4["gated_h_pc_inertia"], [2, 0, 0])
        self.assertEqual(t4["gated_h_pc_det_q"], "1/4")

        t5 = p["t5_borromean_hypergraph_promotion"]
        self.assertEqual(t5["h3_borromean_s23"]["pairwise_laplacian_inertia"], [0, 0, 3])
        self.assertEqual(t5["h3_borromean_s23"]["hypergraph_h3_inertia"], [2, 0, 1])
        self.assertEqual(t5["h4_sovereign_8gib_stack"]["full_4way_stack_mib"], 3300)
        self.assertTrue(t5["h4_sovereign_8gib_stack"]["only_full_4body_feasible"])

        t6 = p["t6_kron_renormalization_and_curvature"]
        self.assertTrue(t6["kron_core4_r_eff_exact_all_6"])
        self.assertTrue(t6["kron_comp4_r_eff_exact_all_6"])
        self.assertEqual(t6["k4_resistance_gram_det_q"], "3218/7036691")
        self.assertEqual(t6["s81_r3_tetrahedron_gram_det_q"], "0")
        self.assertEqual(t6["s75_cat0_rank_gram_det_q"], "-1/4")
        self.assertEqual(t6["s75_cat0_neg_witness_quad_q"], "-1")
        self.assertTrue(t6["curvature_trichotomy_strictly_disjoint"])

        # Synthetic S83 cross-check + negative tamper
        syn_s83 = {
            "payload": {
                "pillar1_schur_compounding": {
                    "pair_rows": [
                        {
                            "pair": f"v{u}-v{v}",
                            "direct_w_q": str(w),
                            "pathway_class": cls,
                            "operator_tag": tag,
                        }
                        for u, v, w, cls, tag in O.S83_EDGES
                    ]
                }
            }
        }
        self.assertTrue(O.cross_check_s83_certificate_dict(syn_s83))
        bad_s83 = copy.deepcopy(syn_s83)
        bad_s83["payload"]["pillar1_schur_compounding"]["pair_rows"][0]["direct_w_q"] = "99"
        with self.assertRaises(O.S85Error) as cm_s83:
            O.cross_check_s83_certificate_dict(bad_s83)
        self.assertEqual(cm_s83.exception.code, "S83_ANCHOR_MISMATCH")

        # Bad SHA args to build_certificate
        for kw in ("lean_source_sha256", "lakefile_sha256", "toolchain_sha256"):
            with self.assertRaises(O.S85Error):
                O.build_certificate(**{kw: "BAD"})


class TestS85StrictTypesAndParsers(unittest.TestCase):
    def test_03_oracle_type_guards_and_json_tree(self) -> None:
        self.assertFalse(O.is_ascii_digits(""))
        self.assertTrue(O.is_ascii_digits("0123456789"))
        self.assertFalse(O.is_ascii_digits("1/2"))
        self.assertFalse(O.is_ascii_digits("1:2"))
        self.assertFalse(O.is_ascii_digits("\u0661"))

        for bad_s in (123, _StrSub("ok"), "\ud800"):
            with self.assertRaises(O.S85Error):
                O.require_exact_str(bad_s, "s")
        for bad_b in (0, 1, "true", None):
            with self.assertRaises(O.S85Error):
                O.require_bool(bad_b, "b")
        self.assertEqual(O.require_exact_int(5, "x", lo=5, hi=5), 5)
        self.assertEqual(O.require_exact_int((1 << 256) - 1, "x"), (1 << 256) - 1)
        for bad_i in (True, _IntSub(1), 1 << 256):
            with self.assertRaises(O.S85Error):
                O.require_exact_int(bad_i, "x")
        with self.assertRaises(O.S85Error):
            O.require_exact_int(4, "x", lo=5)
        with self.assertRaises(O.S85Error):
            O.require_exact_int(6, "x", hi=5)

        good_hex = "0123456789abcdef" * 4
        self.assertEqual(O.require_hex64(good_hex, "h"), good_hex)
        for bad_h in ("a" * 63, "a" * 65, "A" * 64, "g" * 64, "/" * 64, ":" * 64, "`" * 64):
            with self.assertRaises(O.S85Error):
                O.require_hex64(bad_h, "h")

        # JSON tree validator: valid primitives + depth/node/type rejections
        O.validate_strict_json_tree({"a": [1, True, None, "x", (1 << 256) - 1]}, "ok")
        # Exact max depth 32 passes, 33 fails
        nested: object = 1
        for _ in range(O.MAX_JSON_DEPTH):
            nested = [nested]
        O.validate_strict_json_tree(nested, "d32")
        with self.assertRaises(O.S85Error) as cm_d:
            O.validate_strict_json_tree([nested], "d33")
        self.assertEqual(cm_d.exception.code, "JSON_DEPTH_EXCEEDED")
        with mock.patch.object(O, "MAX_JSON_NODES", 3):
            O.validate_strict_json_tree([1, 2], "n3")
            with self.assertRaises(O.S85Error) as cm_n:
                O.validate_strict_json_tree([1, 2, 3], "n4")
            self.assertEqual(cm_n.exception.code, "JSON_NODES_EXCEEDED")
        for bad_tree in ({"a": 1 << 256}, {"a": (1, 2)}, {1: "a"}, {"a": object()}):
            with self.assertRaises(O.S85Error):
                O.validate_strict_json_tree(bad_tree, "bad")

    def test_04_strict_json_rational_and_decimal_parsers(self) -> None:
        # _parse_bounded_int: exact 78-digit / 256-bit max passes; 79 digits & 257 bits fail
        self.assertEqual(V._parse_bounded_int("0"), 0)
        self.assertEqual(V._parse_bounded_int("-42"), -42)
        max_u256 = (1 << 256) - 1
        self.assertEqual(len(str(max_u256)), 78)
        self.assertEqual(V._parse_bounded_int(str(max_u256)), max_u256)
        with mock.patch.object(O, "MAX_INT_BITS", 1024):
            with self.assertRaises(O.S85Error) as cm_dig:
                V._parse_bounded_int("9" * 79)
            self.assertEqual(cm_dig.exception.code, "INT_TOO_LARGE")
            self.assertIn("digits", cm_dig.exception.detail)
        for bad_tok in ("-0", "01", "-01", "1" + "0" * 78, str(1 << 256), "\u0661"):
            with self.assertRaises(O.S85Error):
                V._parse_bounded_int(bad_tok)

        # parse_strict_json_bytes (also test BOM, CR, dup keys under require_canonical=False!)
        raw_ok = b'{"a":1}\n'
        self.assertEqual(V.parse_strict_json_bytes(raw_ok), {"a": 1})
        self.assertEqual(V.parse_strict_json_bytes(b'{ "a": 1 }', require_canonical=False), {"a": 1})
        for raw_nc, exp_code in (
            (b'\xef\xbb\xbf{"a":1}', "BOM_FORBIDDEN"),
            (b'{"a":1}\r\n', "CRLF_FORBIDDEN"),
            (b'{"a":1,"a":2}', "DUPLICATE_JSON_KEY"),
        ):
            with self.assertRaises(O.S85Error) as cm_nc:
                V.parse_strict_json_bytes(raw_nc, require_canonical=False)
            self.assertEqual(cm_nc.exception.code, exp_code)
        for bad_raw in (
            "not_bytes",
            b"\xff",
            b'{"a":1.0}\n',
            b'{"a":NaN}\n',
            b'{"a":Infinity}\n',
            b"[1,2]\n",
            b"{bad\n",
            b'{ "a": 1 }\n',
        ):
            with self.assertRaises(O.S85Error):
                V.parse_strict_json_bytes(bad_raw)  # type: ignore[arg-type]

        # parse_canonical_rational_str (verify INVALID_RATIONAL vs NONCANONICAL_RATIONAL!)
        self.assertEqual(V.parse_canonical_rational_str("0", "q"), Fraction(0))
        self.assertEqual(V.parse_canonical_rational_str("-1/4", "q"), Fraction(-1, 4))
        with self.assertRaises(O.S85Error) as cm_nd:
            V.parse_canonical_rational_str("1/-2", "q")
        self.assertEqual(cm_nd.exception.code, "INVALID_RATIONAL")
        for bad_q in ("", "1/2/3", "3/1", "2/4", "0/2", "-0", "01/3", "1/02", "1/0", 5):
            with self.assertRaises(O.S85Error):
                V.parse_canonical_rational_str(bad_q, "q")

        # _require_exact_dict non-dict
        with self.assertRaises(O.S85Error) as cm_rd:
            V._require_exact_dict([], frozenset(), "d")
        self.assertEqual(cm_rd.exception.code, "INVALID_SCHEMA_DICT")

        # parse_decimal_str_to_q (incl. S85R2-VER-01 >4300-digit DoS & places bounds)
        self.assertEqual(V.parse_decimal_str_to_q("0.25", 2, "d"), Fraction(1, 4))
        self.assertEqual(V.parse_decimal_str_to_q("1.5", 1, "d"), Fraction(3, 2))
        self.assertEqual(V.parse_decimal_str_to_q("0." + "0" * 17 + "1", 18, "d"), Fraction(1, 10 ** 18))
        self.assertEqual(V.parse_decimal_str_to_q("-12.3450", 4, "d"), Fraction(-123450, 10000))
        self.assertEqual(
            V.parse_decimal_str_to_q("9" * O.MAX_INT_DIGITS + ".00", 2, "d"),
            Fraction(int("9" * O.MAX_INT_DIGITS), 1),
        )
        for bad_pl in (0, 19):
            with self.assertRaises(O.S85Error) as cm_pl:
                V.parse_decimal_str_to_q("1.0", bad_pl, "d")
            self.assertEqual(cm_pl.exception.code, "INT_OUT_OF_RANGE")
        for huge_d in ("9" * (O.MAX_INT_DIGITS + 1) + ".00", "9" * 5000 + ".0000"):
            with self.assertRaises(O.S85Error) as cm_hd:
                V.parse_decimal_str_to_q(huge_d, 4 if huge_d.endswith(".0000") else 2, "d")
            self.assertEqual(cm_hd.exception.code, "INT_TOO_LARGE")
        for bad_d in ("12", "1.2.3", "01.25", "1.2", "1.234", "a.25", "1.ab", "-01.25"):
            with self.assertRaises(O.S85Error):
                V.parse_decimal_str_to_q(bad_d, 2, "d")


class TestS85ZoneBFilesystemAndIO(unittest.TestCase):
    def test_05_path_darwin_pwd_and_atomic_io(self) -> None:
        # Concrete Path & NUL checks
        for bad_p in ("/tmp/x", _PathSub("/tmp/x"), Path("/tmp/a\x00b")):
            with self.assertRaises(O.S85Error):
                V._require_concrete_path(bad_p, "p")

        # Darwin system alias normalization branches (including non-darwin guard with mocked lstat!)
        fake_lnk = mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(os, "lstat", return_value=fake_lnk), mock.patch.object(os, "readlink", return_value="private/var"):
            self.assertEqual(V._normalize_darwin_system_prefix(Path("/var/tmp/x")), Path("/var/tmp/x"))
        with mock.patch.object(sys, "platform", "darwin"):
            with mock.patch.object(os, "lstat", return_value=fake_lnk), mock.patch.object(os, "readlink", return_value="private/var"):
                self.assertEqual(V._normalize_darwin_system_prefix(Path("rel/a")), Path("rel/a"))
                self.assertEqual(V._normalize_darwin_system_prefix(Path("foo/var/y")), Path("foo/var/y"))
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/var")), Path("/var"))
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/var/../etc/x")), Path("/var/../etc/x"))
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/usr/bin/x")), Path("/usr/bin/x"))
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/var/tmp/x")), Path("/private/var/tmp/x"))
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/var"), allow_exact=True), Path("/private/var"))
            # Non-root or non-symlink or unexpected readlink or OSError -> unchanged (with readlink mocked valid!)
            with mock.patch.object(os, "lstat", return_value=mock.Mock(st_mode=stat.S_IFDIR | 0o755, st_uid=0)), mock.patch.object(os, "readlink", return_value="private/tmp"):
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/tmp/x/y")), Path("/tmp/x/y"))
            with mock.patch.object(os, "lstat", return_value=mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=1000)), mock.patch.object(os, "readlink", return_value="private/tmp"):
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/tmp/x/y")), Path("/tmp/x/y"))
            with mock.patch.object(os, "lstat", return_value=fake_lnk), mock.patch.object(os, "readlink", return_value="/evil"):
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/etc/a/b")), Path("/etc/a/b"))
            with mock.patch.object(os, "lstat", side_effect=OSError("no")):
                self.assertEqual(V._normalize_darwin_system_prefix(Path("/etc/a/b")), Path("/etc/a/b"))

        # _safe_cwd OSError
        with mock.patch.object(Path, "cwd", side_effect=OSError("gone")):
            with self.assertRaises(O.S85Error) as cm_cwd:
                V._safe_cwd("t")
            self.assertEqual(cm_cwd.exception.code, "CWD_UNAVAILABLE")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            real_sub = root / "real_sub"
            real_sub.mkdir()
            sym_sub = root / "sym_sub"
            os.symlink(real_sub, sym_sub)

            # Live $PWD symlink ancestor check + edge branches
            with mock.patch.dict(os.environ, {"PWD": "relative"}):
                V._check_pwd_no_symlinks("rel")
            with mock.patch.object(os, "environ", {"PWD": "/a\x00b"}):
                with self.assertRaises(O.S85Error):
                    V._check_pwd_no_symlinks("nul")
            with mock.patch.dict(os.environ, {"PWD": str(root / "nonexistent")}):
                V._check_pwd_no_symlinks("missing")
            with mock.patch.dict(os.environ, {"PWD": str(root)}):
                # Different inode from CWD (unless CWD == root)
                V._check_pwd_no_symlinks("diff")
            old_cwd = os.getcwd()
            try:
                os.chdir(real_sub)
                with mock.patch.dict(os.environ, {"PWD": str(sym_sub)}):
                    with self.assertRaises(O.S85Error) as cm_pwd:
                        V._check_pwd_no_symlinks("sym_pwd")
                    self.assertEqual(cm_pwd.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
                with mock.patch.dict(os.environ, {"PWD": str(real_sub)}):
                    V._check_pwd_no_symlinks("real_pwd")
                    # Root open OSError & component non-ELOOP OSError
                    real_open = os.open
                    with mock.patch.object(os, "open", side_effect=OSError(errno.EACCES, "denied")):
                        with self.assertRaises(O.S85Error) as cm_r:
                            V._check_pwd_no_symlinks("r_err")
                        self.assertEqual(cm_r.exception.code, "CWD_UNAVAILABLE")

                    def fail_second(path_arg, flags, *args, **kwargs):
                        if path_arg == "/":
                            return real_open(path_arg, flags, *args, **kwargs)
                        raise OSError(errno.EACCES, "denied")

                    with mock.patch.object(os, "open", side_effect=fail_second):
                        with self.assertRaises(O.S85Error) as cm_c:
                            V._check_pwd_no_symlinks("c_err")
                        self.assertEqual(cm_c.exception.code, "CWD_UNAVAILABLE")
            finally:
                os.chdir(old_cwd)

            # _open_dir_chain traps: root leaf, .. leaf, symlink ancestor, create_parents & errors
            with self.assertRaises(O.S85Error):
                V._open_dir_chain(Path("/"), "root", create_parents=False)
            with self.assertRaises(O.S85Error):
                V._open_dir_chain(root / "..", "dotdot", create_parents=False)
            with self.assertRaises(O.S85Error) as cm_sa:
                V._open_dir_chain(sym_sub / "a.txt", "sym_anc", create_parents=False)
            self.assertEqual(cm_sa.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(O.S85Error) as cm_saw:
                V.write_regular_bytes_safe(sym_sub / "a.bin", b"x", "sym_anc_w")
            self.assertEqual(cm_saw.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(O.S85Error) as cm_nf:
                V._open_dir_chain(root / "no_dir" / "a.txt", "nf", create_parents=False)
            self.assertEqual(cm_nf.exception.code, "FILE_READ_ERROR")

            # create_parents=True creates nested dirs cleanly
            nested_out = root / "new_a" / "new_b" / "out.bin"
            V.write_regular_bytes_safe(nested_out, b"hello", "nested")
            self.assertEqual(V.read_regular_bytes_capped(nested_out, "nested"), b"hello")
            self.assertEqual(stat.S_IMODE(os.stat(nested_out).st_mode), 0o600)
            # Overwrite existing regular file cleanly
            V.write_regular_bytes_safe(nested_out, b"world!", "overwrite")
            self.assertEqual(V.read_regular_bytes_capped(nested_out, "overwrite"), b"world!")

            # Live relative path write/read
            old_cwd2 = os.getcwd()
            try:
                os.chdir(real_sub)
                with mock.patch.dict(os.environ, {"PWD": str(real_sub)}):
                    V.write_regular_bytes_safe(Path("rel.bin"), b"rel", "rel")
                    self.assertEqual(V.read_regular_bytes_capped(Path("rel.bin"), "rel"), b"rel")
            finally:
                os.chdir(old_cwd2)

            # Live symlink leaf, FIFO (non-hanging!), hardlink, oversized, missing read traps
            sym_leaf = root / "sym_leaf.bin"
            os.symlink(nested_out, sym_leaf)
            with self.assertRaises(O.S85Error) as cm_sl:
                V.read_regular_bytes_capped(sym_leaf, "sl")
            self.assertEqual(cm_sl.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(O.S85Error) as cm_slw:
                V.write_regular_bytes_safe(sym_leaf, b"x", "slw")
            self.assertEqual(cm_slw.exception.code, "SYMLINK_FORBIDDEN")

            fifo_p = root / "pipe.fifo"
            os.mkfifo(fifo_p)
            with self.assertRaises(O.S85Error) as cm_ff:
                V.read_regular_bytes_capped(fifo_p, "fifo")
            self.assertEqual(cm_ff.exception.code, "NOT_A_REGULAR_FILE")
            with self.assertRaises(O.S85Error) as cm_ffw:
                V.write_regular_bytes_safe(fifo_p, b"x", "fifow")
            self.assertEqual(cm_ffw.exception.code, "NOT_A_REGULAR_FILE")

            hl_p = root / "hardlink.bin"
            os.link(nested_out, hl_p)
            with self.assertRaises(O.S85Error) as cm_hl:
                V.read_regular_bytes_capped(hl_p, "hl")
            self.assertEqual(cm_hl.exception.code, "HARDLINK_FORBIDDEN")
            with self.assertRaises(O.S85Error) as cm_hlw:
                V.write_regular_bytes_safe(hl_p, b"x", "hlw")
            self.assertEqual(cm_hlw.exception.code, "HARDLINK_FORBIDDEN")
            hl_p.unlink()

            with self.assertRaises(O.S85Error) as cm_miss:
                V.read_regular_bytes_capped(root / "missing.bin", "miss")
            self.assertEqual(cm_miss.exception.code, "FILE_READ_ERROR")
            with self.assertRaises(O.S85Error) as cm_big:
                V.read_regular_bytes_capped(nested_out, "big", max_bytes=3)
            self.assertEqual(cm_big.exception.code, "FILE_TOO_LARGE")
            self.assertEqual(V.read_regular_bytes_capped(nested_out, "exact", max_bytes=6), b"world!")
            with self.assertRaises(O.S85Error):
                V.read_regular_bytes_capped(nested_out, "badcap", max_bytes=0)
            with self.assertRaises(O.S85Error):
                V.read_regular_bytes_capped(nested_out, "badcap2", max_bytes=V.MAX_ALLOWED_CAP_BYTES + 1)

            # st_size pre-check > max_bytes on short real file + growing stream > max_bytes & os.read OSError
            fake_st_big = mock.Mock(st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_size=999)
            with mock.patch.object(os, "fstat", return_value=fake_st_big):
                with self.assertRaises(O.S85Error) as cm_sz:
                    V.read_regular_bytes_capped(nested_out, "sz", max_bytes=10)
                self.assertEqual(cm_sz.exception.code, "FILE_TOO_LARGE")
                self.assertIn("size exceeds", cm_sz.exception.detail)
            fake_st_small = mock.Mock(st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_size=2)
            with mock.patch.object(os, "fstat", return_value=fake_st_small):
                with self.assertRaises(O.S85Error) as cm_grow:
                    V.read_regular_bytes_capped(nested_out, "grow", max_bytes=3)
                self.assertEqual(cm_grow.exception.code, "FILE_TOO_LARGE")
                self.assertIn("stream exceeds", cm_grow.exception.detail)
            with mock.patch.object(os, "read", side_effect=OSError(errno.EIO, "io")):
                with self.assertRaises(O.S85Error) as cm_rio:
                    V.read_regular_bytes_capped(nested_out, "rio")
                self.assertEqual(cm_rio.exception.code, "FILE_READ_ERROR")

            # Write error branches: non-bytes, lstat OSError, mkdir race/OSError, open errors, short write, nlink, replace OSError
            with self.assertRaises(O.S85Error):
                V.write_regular_bytes_safe(nested_out, "str", "badb")  # type: ignore[arg-type]
            with mock.patch.object(os, "lstat", side_effect=OSError(errno.EACCES, "no")):
                with self.assertRaises(O.S85Error) as cm_ls:
                    V.write_regular_bytes_safe(nested_out, b"x", "ls")
                self.assertEqual(cm_ls.exception.code, "FILE_WRITE_ERROR")
            with mock.patch.object(os, "open", side_effect=OSError(errno.EACCES, "root")):
                with self.assertRaises(O.S85Error) as cm_ro:
                    V._open_dir_chain(nested_out, "ro", create_parents=True)
                self.assertEqual(cm_ro.exception.code, "FILE_WRITE_ERROR")

            # mkdir FileExistsError race + mkdir OSError + reopen OSError
            race_dir = root / "race_p"
            real_mkdir = os.mkdir

            def mkdir_race(p, mode, **kw):
                real_mkdir(p, mode, **kw)
                raise FileExistsError("race")

            with mock.patch.object(os, "mkdir", side_effect=mkdir_race):
                V.write_regular_bytes_safe(race_dir / "f.bin", b"ok", "race")
            self.assertEqual((race_dir / "f.bin").read_bytes(), b"ok")
            with mock.patch.object(os, "mkdir", side_effect=OSError(errno.EACCES, "mk")):
                with self.assertRaises(O.S85Error) as cm_mk:
                    V.write_regular_bytes_safe(root / "mk_fail" / "f.bin", b"ok", "mk")
                self.assertEqual(cm_mk.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("mkdir failed", cm_mk.exception.detail)

            real_open2 = os.open

            def fail_reopen(path_arg, flags, *args, **kwargs):
                if path_arg == "reopen_fail":
                    if (root / "reopen_fail").exists():
                        raise OSError(errno.EACCES, "reopen")
                    raise OSError(errno.ENOENT, "enoent")
                return real_open2(path_arg, flags, *args, **kwargs)

            with mock.patch.object(os, "open", side_effect=fail_reopen):
                with self.assertRaises(O.S85Error) as cm_re:
                    V.write_regular_bytes_safe(root / "reopen_fail" / "f.bin", b"ok", "re")
                self.assertEqual(cm_re.exception.code, "FILE_WRITE_ERROR")

            # Temp file open FileExistsError retry -> success, 64 exhaustion, OSError
            calls = {"n": 0}

            def open_retry(path_arg, flags, *args, **kwargs):
                if isinstance(path_arg, str) and path_arg.startswith(".s85."):
                    calls["n"] += 1
                    if calls["n"] == 1:
                        raise FileExistsError("collide")
                return real_open2(path_arg, flags, *args, **kwargs)

            with mock.patch.object(os, "open", side_effect=open_retry):
                V.write_regular_bytes_safe(root / "retry.bin", b"ok", "retry")

            def open_all_exist(path_arg, flags, *args, **kwargs):
                if isinstance(path_arg, str) and path_arg.startswith(".s85."):
                    raise FileExistsError("collide")
                return real_open2(path_arg, flags, *args, **kwargs)

            with mock.patch.object(os, "open", side_effect=open_all_exist):
                with self.assertRaises(O.S85Error) as cm_ex:
                    V.write_regular_bytes_safe(root / "exh.bin", b"ok", "exh")
                self.assertEqual(cm_ex.exception.code, "FILE_WRITE_ERROR")

            def open_tmp_err(path_arg, flags, *args, **kwargs):
                if isinstance(path_arg, str) and path_arg.startswith(".s85."):
                    raise OSError(errno.ENOSPC, "full")
                return real_open2(path_arg, flags, *args, **kwargs)

            with mock.patch.object(os, "open", side_effect=open_tmp_err):
                with self.assertRaises(O.S85Error) as cm_te:
                    V.write_regular_bytes_safe(root / "te.bin", b"ok", "te")
                self.assertEqual(cm_te.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("temp open failed", cm_te.exception.detail)

            # Short write 0, write OSError, temp nlink != 1, os.replace OSError
            with mock.patch.object(os, "write", return_value=0):
                with self.assertRaises(O.S85Error) as cm_sw:
                    V.write_regular_bytes_safe(root / "sw.bin", b"abc", "sw")
                self.assertEqual(cm_sw.exception.code, "FILE_WRITE_ERROR")
            with mock.patch.object(os, "write", side_effect=OSError(errno.EIO, "wio")):
                with self.assertRaises(O.S85Error) as cm_wio:
                    V.write_regular_bytes_safe(root / "wio.bin", b"abc", "wio")
                self.assertEqual(cm_wio.exception.code, "FILE_WRITE_ERROR")
            with mock.patch.object(os, "fstat", return_value=mock.Mock(st_nlink=2)):
                with self.assertRaises(O.S85Error) as cm_nl:
                    V.write_regular_bytes_safe(root / "nl.bin", b"abc", "nl")
                self.assertEqual(cm_nl.exception.code, "HARDLINK_FORBIDDEN")
            with mock.patch.object(os, "replace", side_effect=OSError(errno.EIO, "rep")):
                with self.assertRaises(O.S85Error) as cm_rp:
                    V.write_regular_bytes_safe(root / "rp.bin", b"abc", "rp")
                self.assertEqual(cm_rp.exception.code, "FILE_WRITE_ERROR")


class TestS85LeanR10AndLiveVerification(unittest.TestCase):
    def test_06_comment_stripper_and_r10_static_gate(self) -> None:
        # Nested block comments, stray '/' outside comments & line comments (with and without trailing newline)
        self.assertEqual(V._strip_lean4_comments("a / b"), "a / b")
        stripped = V._strip_lean4_comments("a /- outer /- inner -/ outer -/ b -- tail\nc -- eof")
        self.assertIn("a ", stripped)
        self.assertIn(" b ", stripped)
        self.assertIn("\nc ", stripped)
        self.assertNotIn("inner", stripped)
        self.assertNotIn("tail", stripped)
        self.assertNotIn("eof", stripped)
        with self.assertRaises(O.S85Error) as cm_ut:
            V._strip_lean4_comments("/- unclosed")
        self.assertEqual(cm_ut.exception.code, "LEAN4_UNTERMINATED_LEX")

        clean_src = (_THIS_DIR / "MeshTransformationsUnlock.lean").read_text(encoding="utf-8")
        V.static_gate_lean4_source(clean_src)

        # CR / NUL / missing theorem / missing #print axioms
        with self.assertRaises(O.S85Error):
            V.static_gate_lean4_source(clean_src + "\r\n")
        with self.assertRaises(O.S85Error):
            V.static_gate_lean4_source(clean_src + "\x00")
        with self.assertRaises(O.S85Error) as cm_mt:
            V.static_gate_lean4_source(clean_src.replace("theorem simplicial_boundary_sq_zero_k3", "def x_dummy"))
        self.assertEqual(cm_mt.exception.code, "LEAN4_MISSING_THEOREM")
        with self.assertRaises(O.S85Error) as cm_mt2:
            V.static_gate_lean4_source(
                clean_src.replace("theorem simplicial_boundary_sq_zero_k3", "private theorem simplicial_boundary_sq_zero_k3")
            )
        self.assertEqual(cm_mt2.exception.code, "LEAN4_MISSING_THEOREM")
        with self.assertRaises(O.S85Error) as cm_mt3:
            V.static_gate_lean4_source(
                clean_src.replace("theorem simplicial_boundary_sq_zero_k3", "theorem simplicial_boundary_sq_zero_k3_fake")
            )
        self.assertEqual(cm_mt3.exception.code, "LEAN4_MISSING_THEOREM")
        with self.assertRaises(O.S85Error) as cm_mp:
            V.static_gate_lean4_source(clean_src.replace("#print axioms MeshTransformationsUnlock.simplicial_boundary_sq_zero_k3", ""))
        self.assertEqual(cm_mp.exception.code, "LEAN4_MISSING_PRINT_AXIOMS")
        with self.assertRaises(O.S85Error) as cm_mp2:
            V.static_gate_lean4_source(
                clean_src.replace(
                    "#print axioms MeshTransformationsUnlock.simplicial_boundary_sq_zero_k3",
                    "#print axioms MeshTransformationsUnlock.simplicial_boundary_sq_zero_k3_fake",
                )
            )
        self.assertEqual(cm_mp2.exception.code, "LEAN4_MISSING_PRINT_AXIOMS")

        # Full 24-probe R10+ adversarial bypass battery
        r10_probes = [
            "theorem _e : False := sorry",
            "theorem _e : False := by admit",
            "axiom _e : False",
            "unsafe def _e := 1",
            "theorem _e : 1 = 1 := by native_decide",
            "def _e := @sorryAx",
            "def _e := @Lean.ofReduceBool",
            "def _e := @Lean.ofReduceNat",
            "def _e := @Lean.trustCompiler",
            "def _e := mkSorry",
            "run_cmd pure ()",
            "initialize pure ()",
            "macro _m : command => pure ()",
            "syntax _s := ident",
            "declare_syntax_cat my_cat",
            'notation "openq\\"" => 0',
            "@[csimp] theorem _e : 1 = 1 := rfl",
            "opaque _e : Nat := 0",
            "set_option debug.skipKernelTC true",
            "set_option debug . skipKernelTC true",
            "set_option «debug».«skipKernelTC» true",
            '@[extern "foo"] def _e : Nat := 0',
            "attribute [implemented_by id] id",
            "private partial def _e (n : Nat) : Nat := _e n",
            "private theorem _e : 1 = 1 := by bv_decide",
            "builtin_initialize pure ()",
            "set_option debug.terminalTacticsAsSorry true",
            "@[export evil_c] def _e : Nat := 0",
            "private theorem _e : 1 = 1 := by decide -revert +native",
            "private theorem _e : 1 = 1 := by decide +revert +native",
            "private theorem _e : 1 = 1 := by decide -kernel +native",
            "private theorem _e : 1 = 1 := by decide (config := cfg)",
            "def native : Bool := true\nprivate theorem _e : 1 + 1 = 2 := by decide +revert (config := { native })",
            "def native : Bool := true\nprivate theorem _e : 1 + 1 = 2 := by decide (revert := false) (config := { native })",
            "def native : Bool := true\nprivate theorem _e : 1 + 1 = 2 := by decide +revert (config := { ({} : _) with native })",
            "def _e := { native }",
            "def _e : DecideConfig := {}",
            "private theorem _e : 1 = 1 := by decide (native := !false)",
            "private theorem _e : 1 = 1 := by decide (native := false || true)",
            "private theorem _e : 1 = 1 := by decide (native := false\n|| true)",
            "private theorem _e : 1 = 1 := by decide (native := false == false)",
            "private theorem _e : 1 = 1 := by decide (native := false != true)",
            "private theorem _e : 1 = 1 := by decide (native := false.not)",
            "#eval 1",
            "#reduce 1",
            "#exit",
            "#print axioms example",
            "import Std",
            "def _q : Char := '\"'",
            'def _s : String := s! /- c -/ "{1}"',
            'def _r := r#"""#',
            'def _f := foo!"x"',
            "def _d := dbg_trace 1",
            "def _dt := _root_.dbgTrace (toString 1) (fun _ => 0)",
            "def _dtv := dbgTraceVal 1",
            "def _dts := dbgTraceIfShared (toString 1) 0",
            "def _dsl := dbgSleep 1 (fun _ => 0)",
            "def _dst := dbgStackTrace (fun _ => 0)",
            "def _dtvi := dbgTraceValId 0",
            "def _ds1 := dbg_sleep 0",
            "def _ds2 := dbg_stack_trace 0",
            "def _p1 : Nat := panic! (String.ofList [])",
            "def _p2 : Nat := panicWithPosWithDecl (String.ofList []) (String.ofList []) 0 0 (String.ofList [])",
            "def _p3 : Nat := panicWithPos 0",
            "def _p4 : Nat := panicCore 0",
            "def _p5 : Nat := unreachable!",
            "def _p6 : Nat := assert! true",
            "def _p7 : Nat := debug_assert! true",
            "noncomputable def _nc : Nat := 0",
            "#guard true",
            "#check 1",
            "#synth Inhabited Nat",
            "@[init] def _ini : IO Unit := pure ()",
            "@[builtin_init] def _bini : IO Unit := pure ()",
            "@[term_elab f] def _te : Nat := 0",
            "@[command_elab f] def _ce : Nat := 0",
            "@[tactic f] def _ta : Nat := 0",
            "@[macro f] def _ma : Nat := 0",
            "@[macro_rules f] def _mr : Nat := 0",
            "@[builtin_tactic f] def _bt : Nat := 0",
            "attribute [simp, init] _ini",
            "#guard_msgs in #check Nat",
            "set_option warn.sorry false in private theorem _ws : False := _root_.sorryAx False false",
        ]
        for snippet in r10_probes:
            with self.assertRaises(O.S85Error) as cm_p:
                V.static_gate_lean4_source(clean_src + "\n" + snippet + "\n")
            self.assertEqual(cm_p.exception.code, "LEAN4_TRUST_ESCAPE", msg=snippet)

        # Clean R12 zero-FP controls
        for ctrl in (
            "private theorem _c1 : 1 + 1 = 2 := by decide (native := false)",
            "private theorem _c2 : 1 + 1 = 2 := by decide (native := Bool.false)",
            "private theorem _c3 : 1 + 1 = 2 := by decide (native := false, revert := true)",
            "export Nat (succ)",
            "attribute [simp] init",
            "@[inline] private def _c4 : Nat := 1",
            "@[macro_inline] private def _c5 : Nat := 2",
            "private def my_panic : Nat := 0",
        ):
            V.static_gate_lean4_source(clean_src + "\n" + ctrl + "\n")

    def test_07_axiom_parser_binary_resolver_and_live_or_leanless_ci(self) -> None:
        # Multi-line wrapped axiom parser + zero-axiom + failure traps
        lines = []
        for idx, thm in enumerate(O.LEAN_THEOREM_NAMES):
            if idx == 0:
                lines.append(f"'{thm}' does not depend on any axioms")
            elif idx == 1:
                lines.append(f"'{thm}' depends on axioms: [propext,")
                lines.append(" Quot.sound]")
            else:
                lines.append(f"'{thm}' depends on axioms: [propext, Quot.sound]")
        parsed = V._parse_lean_axiom_stdout("\n\n" + "\n".join(lines) + "\n")
        self.assertEqual(len(parsed), 18)
        self.assertEqual(parsed[O.LEAN_THEOREM_NAMES[0]], [])
        self.assertEqual(parsed[O.LEAN_THEOREM_NAMES[1]], ["propext", "Quot.sound"])

        with self.assertRaises(O.S85Error) as cm_ut:
            V._parse_lean_axiom_stdout("'X' depends on axioms: [propext,\n")
        self.assertEqual(cm_ut.exception.code, "LEAN_UNEXPECTED_STDOUT")
        with self.assertRaises(O.S85Error) as cm_ux:
            V._parse_lean_axiom_stdout("unexpected noise line")
        self.assertEqual(cm_ux.exception.code, "LEAN_UNEXPECTED_STDOUT")
        with self.assertRaises(O.S85Error) as cm_d0:
            V._parse_lean_axiom_stdout(lines[0] + "\n" + lines[0])
        self.assertEqual(cm_d0.exception.code, "LEAN_DUPLICATE_THEOREM")
        with self.assertRaises(O.S85Error) as cm_d1:
            V._parse_lean_axiom_stdout(lines[3] + "\n" + lines[3])
        self.assertEqual(cm_d1.exception.code, "LEAN_DUPLICATE_THEOREM")
        with self.assertRaises(O.S85Error) as cm_fa:
            V._parse_lean_axiom_stdout(f"'{O.LEAN_THEOREM_NAMES[0]}' depends on axioms: [Classical.choice]")
        self.assertEqual(cm_fa.exception.code, "LEAN_FORBIDDEN_AXIOM")
        with self.assertRaises(O.S85Error) as cm_ms:
            V._parse_lean_axiom_stdout(lines[0])
        self.assertEqual(cm_ms.exception.code, "LEAN_THEOREM_SET_MISMATCH")

        # resolve_lean_binary paths
        with tempfile.TemporaryDirectory() as td:
            fake_bin = Path(td) / "lean"
            fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(fake_bin, 0o755)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(fake_bin)}):
                self.assertEqual(V.resolve_lean_binary(), str(fake_bin))
            os.chmod(fake_bin, 0o644)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(fake_bin)}):
                with self.assertRaises(O.S85Error) as cm_nx:
                    V.resolve_lean_binary()
                self.assertEqual(cm_nx.exception.code, "LEAN_BINARY_UNAVAILABLE")
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(Path(td))}):
                with self.assertRaises(O.S85Error) as cm_dir:
                    V.resolve_lean_binary()
                self.assertEqual(cm_dir.exception.code, "LEAN_BINARY_UNAVAILABLE")

            clean_env = {k: v for k, v in os.environ.items() if k not in ("ALETHEIA_LEAN_BIN", "HOME")}
            with mock.patch.dict(os.environ, clean_env, clear=True):
                # Bare env without HOME must not fall back to /etc/passwd home
                with mock.patch.object(shutil, "which", return_value=None):
                    with self.assertRaises(O.S85Error) as cm_nohome:
                        V.resolve_lean_binary()
                    self.assertEqual(cm_nohome.exception.code, "LEAN_BINARY_UNAVAILABLE")
                # Empty HOME also refuses fallback
                with mock.patch.dict(os.environ, {"HOME": ""}), mock.patch.object(shutil, "which", return_value=None):
                    with self.assertRaises(O.S85Error) as cm_ehome:
                        V.resolve_lean_binary()
                    self.assertEqual(cm_ehome.exception.code, "LEAN_BINARY_UNAVAILABLE")

                # shutil.which returning non-executable falls through cleanly
                home_dir = Path(td) / "fake_home"
                loc_bin = home_dir / ".local" / "bin" / "lean"
                loc_bin.parent.mkdir(parents=True)
                with mock.patch.dict(os.environ, {"HOME": str(home_dir)}), mock.patch.object(shutil, "which", return_value=str(fake_bin)):
                    with self.assertRaises(O.S85Error) as cm_wx:
                        V.resolve_lean_binary()
                    self.assertEqual(cm_wx.exception.code, "LEAN_BINARY_UNAVAILABLE")
                os.chmod(fake_bin, 0o755)
                with mock.patch.object(shutil, "which", return_value=str(fake_bin)):
                    self.assertEqual(V.resolve_lean_binary(), str(fake_bin))
                # $HOME fallback: directory rejected, non-exec rejected, exec accepted, missing fails
                loc_bin.mkdir()
                with mock.patch.dict(os.environ, {"HOME": str(home_dir)}), mock.patch.object(shutil, "which", return_value=None):
                    with self.assertRaises(O.S85Error) as cm_hd:
                        V.resolve_lean_binary()
                    self.assertEqual(cm_hd.exception.code, "LEAN_BINARY_UNAVAILABLE")
                loc_bin.rmdir()
                loc_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                os.chmod(loc_bin, 0o644)
                with mock.patch.dict(os.environ, {"HOME": str(home_dir)}), mock.patch.object(shutil, "which", return_value=None):
                    with self.assertRaises(O.S85Error) as cm_hx:
                        V.resolve_lean_binary()
                    self.assertEqual(cm_hx.exception.code, "LEAN_BINARY_UNAVAILABLE")
                os.chmod(loc_bin, 0o755)
                with mock.patch.dict(os.environ, {"HOME": str(home_dir)}), mock.patch.object(shutil, "which", return_value=None):
                    self.assertEqual(V.resolve_lean_binary(), str(loc_bin))
                loc_bin.unlink()
                with mock.patch.dict(os.environ, {"HOME": str(home_dir)}), mock.patch.object(shutil, "which", return_value=None):
                    with self.assertRaises(O.S85Error) as cm_none:
                        V.resolve_lean_binary()
                    self.assertEqual(cm_none.exception.code, "LEAN_BINARY_UNAVAILABLE")

        # verify_lean4_file_live guard traps (mocked subprocess + real file)
        lean_p = _THIS_DIR / "MeshTransformationsUnlock.lean"
        with self.assertRaises(O.S85Error):
            V.verify_lean4_file_live(lean_p, require_pinned_sha=1)  # type: ignore[arg-type]
        with tempfile.TemporaryDirectory() as td:
            bad_utf8 = Path(td) / "bad.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            with self.assertRaises(O.S85Error) as cm_sha:
                V.verify_lean4_file_live(bad_utf8, require_pinned_sha=True)
            self.assertEqual(cm_sha.exception.code, "LEAN_SHA_MISMATCH")
            with self.assertRaises(O.S85Error) as cm_u8:
                V.verify_lean4_file_live(bad_utf8, require_pinned_sha=False)
            self.assertEqual(cm_u8.exception.code, "INVALID_UTF8")

        with mock.patch.object(V, "resolve_lean_binary", return_value="/fake/lean"):
            with mock.patch.object(subprocess, "run", side_effect=OSError("no")):
                with self.assertRaises(O.S85Error) as cm_ve:
                    V.verify_lean4_file_live(lean_p)
                self.assertEqual(cm_ve.exception.code, "LEAN_EXEC_ERROR")
            with mock.patch.object(subprocess, "run", return_value=mock.Mock(returncode=0, stdout="Lean 4.0.0", stderr="")):
                with self.assertRaises(O.S85Error) as cm_vm:
                    V.verify_lean4_file_live(lean_p)
                self.assertEqual(cm_vm.exception.code, "LEAN_VERSION_MISMATCH")
            with mock.patch.object(subprocess, "run", return_value=mock.Mock(returncode=1, stdout="Lean 4.36.0", stderr="")):
                with self.assertRaises(O.S85Error) as cm_vm2:
                    V.verify_lean4_file_live(lean_p)
                self.assertEqual(cm_vm2.exception.code, "LEAN_VERSION_MISMATCH")

            v_ok = mock.Mock(returncode=0, stdout="Lean (version 4.36.0)", stderr="")
            with mock.patch.object(subprocess, "run", side_effect=[v_ok, subprocess.TimeoutExpired("lean", 1)]):
                with self.assertRaises(O.S85Error) as cm_te:
                    V.verify_lean4_file_live(lean_p)
                self.assertEqual(cm_te.exception.code, "LEAN_EXEC_ERROR")
            with mock.patch.object(subprocess, "run", side_effect=[v_ok, mock.Mock(returncode=1, stdout="", stderr="")]):
                with self.assertRaises(O.S85Error) as cm_rc:
                    V.verify_lean4_file_live(lean_p)
                self.assertEqual(cm_rc.exception.code, "LEAN_COMPILE_FAIL")
            with mock.patch.object(subprocess, "run", side_effect=[v_ok, mock.Mock(returncode=0, stdout="", stderr="err")]):
                with self.assertRaises(O.S85Error) as cm_se:
                    V.verify_lean4_file_live(lean_p)
                self.assertEqual(cm_se.exception.code, "LEAN_STDERR_NONEMPTY")
            with mock.patch.object(subprocess, "run", side_effect=[v_ok, mock.Mock(returncode=0, stdout="warning: unused", stderr="")]):
                with self.assertRaises(O.S85Error) as cm_wn:
                    V.verify_lean4_file_live(lean_p)
                self.assertEqual(cm_wn.exception.code, "LEAN_WARNING_FORBIDDEN")

            # Verify allowlisted env scrub passed to BOTH subprocess.run calls (S85R2-VER-03)
            poison_vars = {
                "LEAN_PATH": "/tmp/evil_lp",
                "LEAN_OPTS": "--evil-flag",
                "LEAN_SRC_PATH": "/tmp/evil_src",
                "LEAN_SYSROOT": "/tmp/evil_sys",
                "LEAN_CC": "/tmp/evil_cc",
                "ELAN_TOOLCHAIN": "evil-99.9",
                "ELAN_HOME": "/tmp/evil_elan",
                "LAKE_HOME": "/tmp/evil_lake",
                "LD_PRELOAD": "/tmp/evil.so",
                "LD_LIBRARY_PATH": "/tmp/evil_lib",
            }
            seen_envs: list = []
            ok_seq = [v_ok, mock.Mock(returncode=0, stdout="\n".join(lines) + "\n", stderr="")]

            def _capture_run(*a, **kw):
                seen_envs.append(kw.get("env"))
                return ok_seq.pop(0)

            with mock.patch.dict(os.environ, poison_vars), mock.patch.object(subprocess, "run", side_effect=_capture_run):
                cleaned_env = V._clean_lean_env()
                for bk in poison_vars:
                    self.assertNotIn(bk, cleaned_env)
                self.assertIn("PATH", cleaned_env)
                mock_res = V.verify_lean4_file_live(lean_p, require_pinned_sha=True)
                self.assertEqual(mock_res["theorems_verified"], 18)
            self.assertEqual(len(seen_envs), 2)
            for ce in seen_envs:
                self.assertIsInstance(ce, dict)
                for bk in poison_vars:
                    self.assertNotIn(bk, ce)

        # Live Lean 4.36.0 execution (under poisoned LEAN_PATH/ELAN_*!) OR zero-skip fail-closed Lean-less CI
        lean_avail = True
        try:
            V.resolve_lean_binary()
        except O.S85Error:
            lean_avail = False
        if lean_avail:
            with tempfile.TemporaryDirectory() as td:
                evil_dir = Path(td) / "evil_lp"
                evil_dir.mkdir(mode=0o700)
                (evil_dir / "Init.olean").write_bytes(b"CORRUPT_OLEAN_HIJACK")
                live_poison = {
                    "LEAN_PATH": str(evil_dir),
                    "LEAN_OPTS": "--nonexistent-lean-flag-999",
                    "ELAN_TOOLCHAIN": "nonexistent-toolchain-99.99",
                    "ELAN_HOME": str(evil_dir),
                    "LEAN_CC": str(evil_dir / "no_cc"),
                }
                with mock.patch.dict(os.environ, live_poison):
                    live_res = V.verify_lean4_file_live(lean_p, require_pinned_sha=True)
                    self.assertEqual(live_res["theorems_verified"], 18)
                    self.assertEqual(live_res["lean_source_sha256"], O.EXPECTED_LEAN_SOURCE_SHA256)
                # Live E2E traps: trivialized statement substitution blocked by SHA pin; R12 escapes blocked statically
                triv = Path(td) / "triv.lean"
                triv.write_text(
                    "namespace MeshTransformationsUnlock\n"
                    + "\n".join(f"theorem {t.split('.')[-1]} : True := trivial" for t in O.LEAN_THEOREM_NAMES)
                    + "\nend MeshTransformationsUnlock\n"
                    + "\n".join(f"#print axioms {t}" for t in O.LEAN_THEOREM_NAMES) + "\n",
                    encoding="utf-8",
                )
                with self.assertRaises(O.S85Error) as cm_triv:
                    V.verify_lean4_file_live(triv, require_pinned_sha=True)
                self.assertEqual(cm_triv.exception.code, "LEAN_SHA_MISMATCH")
                base_src = lean_p.read_text(encoding="utf-8")
                for idx_e, tail in enumerate((
                    "\nprivate theorem _e : 1 = 1 := by decide -revert +native\n",
                    "\n#guard true\n",
                    "\nprivate def _p : Nat := panic! (String.ofList [])\n",
                )):
                    bad_p = Path(td) / f"bad_{idx_e}.lean"
                    bad_p.write_text(base_src + tail, encoding="utf-8")
                    with self.assertRaises(O.S85Error) as cm_bn:
                        V.verify_lean4_file_live(bad_p, require_pinned_sha=False)
                    self.assertEqual(cm_bn.exception.code, "LEAN4_TRUST_ESCAPE")
        else:
            self.assertNotEqual(os.environ.get("ALETHEIA_REQUIRE_LEAN"), "1")
            with self.assertRaises(O.S85Error) as cm_nl:
                V.verify_lean4_file_live(lean_p, require_pinned_sha=True)
            self.assertEqual(cm_nl.exception.code, "LEAN_BINARY_UNAVAILABLE")


class TestS85SecondaryAuditReplayAndCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_cert = O.build_certificate()

    def _expect_sec_fail(self, mutate_fn, exp_code: str | None = None) -> None:
        p = copy.deepcopy(self.valid_cert["payload"])
        mutate_fn(p)
        with self.assertRaises(O.S85Error) as cm:
            V.secondary_audit_payload(p)
        if exp_code is not None:
            self.assertEqual(cm.exception.code, exp_code)

    def test_08_secondary_audit_exhaustive_tamper_kills(self) -> None:
        sec_ok = V.secondary_audit_payload(self.valid_cert["payload"])
        self.assertTrue(sec_ok["secondary_audit_passed"])
        self.assertEqual(sec_ok["transformations_checked"], 6)

        with self.assertRaises(O.S85Error) as cm_pd:
            V.secondary_audit_payload("not_dict")
        self.assertEqual(cm_pd.exception.code, "INVALID_PAYLOAD_TYPE")
        with self.assertRaises(O.S85Error) as cm_it:
            V._require_inertia((1, 0, 0), [1, 0, 0], "in")
        self.assertEqual(cm_it.exception.code, "INVALID_INERTIA")
        with self.assertRaises(O.S85Error) as cm_il:
            V._require_inertia([1, 0], [1, 0, 0], "in")
        self.assertEqual(cm_il.exception.code, "INVALID_INERTIA")
        with self.assertRaises(O.S85Error):
            V._require_inertia([29, 0, 0], [1, 0, 0], "in")
        with self.assertRaises(O.S85Error) as cm_im:
            V._require_inertia([2, 0, 0], [1, 0, 0], "in")
        self.assertEqual(cm_im.exception.code, "INERTIA_MISMATCH")

        # Top-level & pinned_artifacts tampers
        self._expect_sec_fail(lambda p: p.__setitem__("extra", 1))
        self._expect_sec_fail(lambda p: p.__setitem__("schema_version", "bad"))
        self._expect_sec_fail(lambda p: p.__setitem__("track_id", "bad"))
        self._expect_sec_fail(lambda p: p.__setitem__("oracle_class", "bad"))
        self._expect_sec_fail(lambda p: p.__setitem__("novelty_classification", "N2"))
        self._expect_sec_fail(lambda p: p["pinned_artifacts"].__setitem__("lean_source", "X.lean"))
        self._expect_sec_fail(lambda p: p["pinned_artifacts"].__setitem__("lean_source_sha256", "0" * 64), "LEAN_PIN_MISMATCH")
        self._expect_sec_fail(lambda p: p["pinned_artifacts"].__setitem__("lakefile_sha256", "0" * 64), "LEAN_PIN_MISMATCH")
        self._expect_sec_fail(lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain", "old"))
        self._expect_sec_fail(lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain_sha256", "0" * 64), "LEAN_PIN_MISMATCH")
        self._expect_sec_fail(lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", []))
        self._expect_sec_fail(lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", "bad"))
        self._expect_sec_fail(lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", 1), "THEOREM_LIST_MISMATCH")
        self._expect_sec_fail(lambda p: p["pinned_artifacts"]["upstream_cert_shas"].__setitem__("track_s83_k8_mesh", "0" * 64))

        # T1 tampers (incl. S85R2-VER-02 exact K_8 anchors & sub-dict keyset & isolated Hodge anchors)
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("line_graph_incident_edges", 167), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("line_graph_incident_edges", 169), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("line_graph_disjoint_pairs", 209), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("line_graph_disjoint_pairs", 211), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("disjoint_same_operator_tag_bridges", 17), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("disjoint_same_operator_tag_bridges", 19), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("disjoint_same_class_and_tag_bridges", 10), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("disjoint_same_class_and_tag_bridges", 12), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("disjoint_bridges_by_tag", []), "INVALID_SCHEMA_DICT")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"]["disjoint_bridges_by_tag"].__setitem__("EXTRA_TAG", 1), "INVALID_SCHEMA_KEYS")
        for tk, tv in (
            ("BOUNDARY_WALL", 5),
            ("GAUGE_QUOTIENT", 3),
            ("HOLONOMY_CURVATURE", 3),
            ("PHASE_CROSSOVER", 4),
            ("SCHUR_PUSHFORWARD", 3),
        ):
            self._expect_sec_fail(lambda p, kk=tk, vv=tv - 1: p["t1_line_graph_and_hodge"]["disjoint_bridges_by_tag"].__setitem__(kk, vv), "INT_OUT_OF_RANGE")
            self._expect_sec_fail(lambda p, kk=tk, vv=tv + 1: p["t1_line_graph_and_hodge"]["disjoint_bridges_by_tag"].__setitem__(kk, vv), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("sample_disjoint_functor_bridges", []))
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("sample_disjoint_functor_bridges", "x"))
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("sample_disjoint_functor_bridges", [""]), "T1_SAMPLE")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("b1_b2_exact_zero", False))
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("l1_equals_8_identity", False))
        def set_t1_ng_only(p):
            t1 = p["t1_line_graph_and_hodge"]
            t1["wall_grad_energy_q"] = "3"
            t1["wall_cochain_norm_sq_q"] = "23/4"
            t1["wall_grad_pct_dec2"] = O.dec_from_q(Fraction(300) / Fraction(23, 4), 2)
            t1["wall_curl_pct_dec2"] = O.dec_from_q(Fraction(275) / Fraction(23, 4), 2)
        self._expect_sec_fail(set_t1_ng_only, "T1_HODGE_NG")
        def set_t1_nc_only(p):
            t1 = p["t1_line_graph_and_hodge"]
            t1["wall_curl_energy_q"] = "3"
            t1["wall_cochain_norm_sq_q"] = "25/4"
            t1["wall_grad_pct_dec2"] = O.dec_from_q(Fraction(325) / Fraction(25, 4), 2)
            t1["wall_curl_pct_dec2"] = O.dec_from_q(Fraction(300) / Fraction(25, 4), 2)
        self._expect_sec_fail(set_t1_nc_only, "T1_HODGE_NC")
        def set_t1_sum_only(p):
            t1 = p["t1_line_graph_and_hodge"]
            t1["wall_cochain_norm_sq_q"] = "5"
            t1["wall_grad_pct_dec2"] = "65.00"
            t1["wall_curl_pct_dec2"] = "55.00"
        self._expect_sec_fail(set_t1_sum_only, "T1_HODGE_SUM")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("grad_curl_inner_product_q", "1"), "T1_HODGE_ORTH")
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("wall_grad_pct_dec2", "50.00"))
        self._expect_sec_fail(lambda p: p["t1_line_graph_and_hodge"].__setitem__("wall_curl_pct_dec2", "50.00"))

        # T2 tampers
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("l0_det_q", "1"))
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("l_sigma_det_q", "0"), "T2_DET")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("l_sigma_det_q", "1"), "T2_DET")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("min_weighted_frustration_cut_q", "5"), "T2_FRUST_MW")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("min_weighted_quadratic_energy_q", "20"), "T2_FRUST_EQ")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("min_unweighted_frustration_cut", 4), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("min_unweighted_frustration_cut", 6), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("best_unweighted_switch_mask", 118), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("best_unweighted_switch_mask", 120), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("double_cover_total_conductance_q", "141"))
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("antipodal_resistance_equals_2_lsigma_inv_diag", False))
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("law5_irreducible_double_sheet_connected", False))
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"]["antipodal_sheet_resistances_q"].__setitem__("v0", "0"), "T2_ANTI_EXACT")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"]["antipodal_sheet_resistances_q"].__setitem__("v0", "2309/11581"), "T2_ANTI_EXACT")
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("min_sheet_separation_r_dec4", "0.0001"))
        self._expect_sec_fail(lambda p: p["t2_signed_laplacian_and_double_cover"].__setitem__("max_sheet_separation_r_dec4", "0.9999"))

        # T3 tampers (incl. S85-VER-02 + AUDIT-185R3 337/337 exact leaf anchors, tie-breaker & superadditivity!)
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("base_sum_geff_dec4", "269.7214"), "T3_BASE_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("base_kirchhoff_dec4", "3.0097"), "T3_BASE_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("base_lambda2_lo_dec5", "0.00000"), "T3_BASE_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("base_lambda2_hi_dec5", "11.22511"), "T3_BASE_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("single_surgery_rows", "bad"), "T3_ROWS_TYPE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("single_surgery_rows", []), "T3_ROWS_LEN")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("pair", "v9-v9"), "T3_PAIR_UNKNOWN")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][1].__setitem__("pair", "v6-v7"), "T3_DUP_PAIR")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][6].__setitem__("original_class", "BAD"), "T3_CLS")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("original_w", 2), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][6].__setitem__("original_w", 1), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("mediator", "tampered"), "T3_MED")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][6].__setitem__("frustrated_after", 21), "T3_DF")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("multi_wall_after", 6), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("multi_wall_after", 8), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("delta_exact_transitive", 1), "T3_DE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("delta_sum_geff_dec4", "10.6347"), "T3_ROW_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("delta_kirchhoff_dec5", "-0.08884"), "T3_ROW_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("lambda2_lo_dec5", "11.22999"), "T3_ROW_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["single_surgery_rows"][0].__setitem__("lambda2_strictly_lifted", False))
        def set_t3_wall_count_5(p):
            t3 = p["t3_obstruction_blowup_surgery"]
            t3["single_surgery_rows"][5]["original_class"] = "CONDITIONAL_BRIDGE"
            t3["single_surgery_rows"][5]["original_w"] = 2
            t3["all_6_walls_holonomy_ranking"] = t3["all_6_walls_holonomy_ranking"][:5]
        self._expect_sec_fail(set_t3_wall_count_5, "T3_WALL_COUNT")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("all_6_walls_holonomy_ranking", "bad"), "T3_RANK_TYPE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("all_6_walls_holonomy_ranking", ["v6-v7"]), "T3_RANK_ORDER")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("all_6_walls_holonomy_ranking", ["v6-v7"] * 6), "T3_RANK_ORDER")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("all_6_walls_holonomy_ranking", ["v6-v7", "v1-v4", "v0-v4", "v2-v4", "v3-v4", "v1-v5"]), "T3_RANK_ORDER")
        # Tie-breaker check: equal delta_frustrated sorts by descending delta_exact_transitive (-de)
        p_tie = copy.deepcopy(self.valid_cert["payload"])
        p_tie["t3_obstruction_blowup_surgery"]["single_surgery_rows"][2]["delta_exact_transitive"] = 1
        p_tie["t3_obstruction_blowup_surgery"]["single_surgery_rows"][2]["exact_transitive_after"] = 4
        p_tie["t3_obstruction_blowup_surgery"]["single_surgery_rows"][3]["delta_exact_transitive"] = 2
        p_tie["t3_obstruction_blowup_surgery"]["single_surgery_rows"][3]["exact_transitive_after"] = 5
        p_tie["t3_obstruction_blowup_surgery"]["all_6_walls_holonomy_ranking"] = ["v6-v7", "v1-v5", "v2-v4", "v0-v4", "v3-v4", "v1-v4"]
        self.assertTrue(V.secondary_audit_payload(p_tie)["secondary_audit_passed"])
        # Swap v6-v7 & v1-v5 deltas so ranking matches sorted rows yet head != v6-v7
        def set_t3_rank_head_only(p):
            t3 = p["t3_obstruction_blowup_surgery"]
            t3["single_surgery_rows"][0]["delta_frustrated"] = -4
            t3["single_surgery_rows"][0]["frustrated_after"] = 18
            t3["single_surgery_rows"][1]["delta_frustrated"] = -6
            t3["single_surgery_rows"][1]["frustrated_after"] = 16
            t3["all_6_walls_holonomy_ranking"] = ["v1-v5", "v6-v7", "v0-v4", "v2-v4", "v3-v4", "v1-v4"]
        self._expect_sec_fail(set_t3_rank_head_only, "T3_RANK_HEAD")
        def set_t3_v67_delta_only(p):
            t3 = p["t3_obstruction_blowup_surgery"]
            t3["single_surgery_rows"][0]["delta_frustrated"] = -5
            t3["single_surgery_rows"][0]["frustrated_after"] = 17
        self._expect_sec_fail(set_t3_v67_delta_only, "T3_V67_DELTA")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("isolated_wall_v6_v7_flips_all_6", False))
        def set_t3_braess_delta_only(p):
            t3 = p["t3_obstruction_blowup_surgery"]
            t3["single_surgery_rows"][5]["delta_frustrated"] = 1
            t3["single_surgery_rows"][5]["frustrated_after"] = 23
        self._expect_sec_fail(set_t3_braess_delta_only, "T3_BRAESS_DELTA")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("three_step_cascade", "bad"), "T3_CASC_TYPE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("three_step_cascade", []), "T3_CASC_LEN")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("added_pair", "v1-v5"), "T3_CASC_PAIR")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("frustrated_triangles", 15), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("frustrated_triangles", 17), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("multi_wall_triangles", 6), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("multi_wall_triangles", 8), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][2].__setitem__("exact_transitive_closures", 8), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][2].__setitem__("exact_transitive_closures", 10), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("sum_geff_dec4", "280.3560"), "T3_CASC_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("delta_sum_geff_vs_base_dec4", "10.6347"), "T3_CASC_DEC")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("kirchhoff_dec4", "2.9208"), "T3_CASC_DEC")
        def set_t3_synergy_boundary(p):
            t3 = p["t3_obstruction_blowup_surgery"]
            t3["single_surgery_rows"][6]["delta_exact_transitive"] = 3
            t3["single_surgery_rows"][6]["exact_transitive_after"] = 6
        self._expect_sec_fail(set_t3_synergy_boundary, "T3_SYNERGY_SUPERADD")
        self._expect_sec_fail(lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("superadditive_transitive_synergy_emergent_v0_v1_v5", False))

        # T4 tampers (exact error codes for every invariant + S85R2-VER-01 ZeroDivisionError & S85R2-VER-02!)
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"].__setitem__("asymmetric_gains_a_b_q", "bad"), "T4_AB_TYPE")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"].__setitem__("asymmetric_gains_a_b_q", ["1"]), "T4_AB_LEN")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"]["asymmetric_gains_a_b_q"].__setitem__(0, "2"), "T4_A_EXACT")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"]["asymmetric_gains_a_b_q"].__setitem__(1, "1/4"), "T4_B_EXACT")
        for k, bad_v, code in (
            ("monodromy_rho_q", "1/3", "T4_RHO_EQ"),
            ("g_loop_forward_q", "1", "T4_GF"),
            ("g_loop_reversed_q", "1", "T4_GR"),
            ("directional_curvature_asymmetry_q", "1", "T4_ASYM_EQ"),
            ("readout_schur_forward_q", "1", "T4_SF"),
            ("readout_schur_reversed_q", "1", "T4_SR"),
            ("adjoint_gain_direction_invariant_q", "3", "T4_ADJ"),
            ("directional_curvature_asymmetry_dec4", "1.0000", "T4_DEC"),
            ("epistemic_curl_frobenius_sq_q", "1", "T4_CURL"),
            ("ungated_monodromy_divergent_q", "2", "T4_UNG"),
            ("law3_damping_gamma_q", "1/2", "T4_GAM"),
            ("gated_monodromy_contractive_q", "1/3", "T4_GAT_EQ"),
            ("gated_h_pc_det_q", "1", "T4_HPC_DET"),
        ):
            self._expect_sec_fail(lambda p, kk=k, vv=bad_v: p["t4_directed_ceer_loop_schur"].__setitem__(kk, vv), code)
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"].__setitem__("nonnormal_t1_t2_t3_t10_q", "bad"), "T4_NN_TYPE")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"].__setitem__("nonnormal_t1_t2_t3_t10_q", ["1"]), "T4_NN_LEN")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"].__setitem__("symmetric_t1_t2_t3_q", "bad"), "T4_SY_TYPE")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"].__setitem__("symmetric_t1_t2_t3_q", ["1"]), "T4_SY_LEN")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"].__setitem__("transient_boost_over_symmetric_t1_t2_t3_q", "bad"), "T4_BO_TYPE")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"].__setitem__("transient_boost_over_symmetric_t1_t2_t3_q", ["1"]), "T4_BO_LEN")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"]["nonnormal_t1_t2_t3_t10_q"].__setitem__(0, "1"), "T4_NN_EXACT")
        for idx in range(3):
            self._expect_sec_fail(lambda p, ii=idx: p["t4_directed_ceer_loop_schur"]["symmetric_t1_t2_t3_q"].__setitem__(ii, "0"), "T4_SY_POS")
            self._expect_sec_fail(lambda p, ii=idx: p["t4_directed_ceer_loop_schur"]["symmetric_t1_t2_t3_q"].__setitem__(ii, "-1/4"), "T4_SY_POS")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"]["symmetric_t1_t2_t3_q"].__setitem__(0, "1/2"), "T4_SY_EXACT")
        self._expect_sec_fail(lambda p: p["t4_directed_ceer_loop_schur"]["transient_boost_over_symmetric_t1_t2_t3_q"].__setitem__(0, "1"), "T4_BOOST_EQ")

        # T5 tampers (incl. S85R2-VER-02 exact VRAM budget breakdown anchors)
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h3_borromean_s23"].__setitem__("s23a_pairwise_linking_all_zero", False))
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h3_borromean_s23"].__setitem__("s23a_abelian_mutual_helicity_q", "1"))
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h3_borromean_s23"].__setitem__("hypergraph_h3_lambda2_q", "2"))
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h3_borromean_s23"].__setitem__("hypergraph_h3_pair_geff_q", "1"))
        for hk, hv in (
            ("materialized_45bpw_oom_mib", 8256),
            ("stack_30bpw_cce_base_mib", 3044),
            ("lora_r64_mib", 192),
            ("csr_sidecar_mib", 64),
        ):
            self._expect_sec_fail(lambda p, kk=hk, vv=hv - 1: p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"].__setitem__(kk, vv), "INT_OUT_OF_RANGE")
            self._expect_sec_fail(lambda p, kk=hk, vv=hv + 1: p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"].__setitem__(kk, vv), "INT_OUT_OF_RANGE")
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"].__setitem__("full_4way_stack_mib", 3299), "T5_H4_SUM")
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"].__setitem__("headroom_mib", 4891), "T5_H4_HR")
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"].__setitem__("csr_overhead_ratio_q", "1/2"), "T5_CSR")
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"].__setitem__("only_full_4body_feasible", False))
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"].__setitem__("hypergraph_h4_lambda2_q", "3"))
        self._expect_sec_fail(lambda p: p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"].__setitem__("hypergraph_h4_pair_geff_q", "1"))

        # T6 tampers
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("kron_core4_r_eff_exact_all_6", False))
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("kron_comp4_r_eff_exact_all_6", False))
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("kron_core4_foster_q", "4"))
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("kron_comp4_foster_q", "4"))
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("k4_resistance_gram_det_q", "0"), "T6_DK4_EXACT")
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("k4_resistance_gram_det_q", "1"), "T6_DK4_EXACT")
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("k4_resistance_gram_det_dec8", "0.00000001"), "T6_DK4_DEC")
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("s81_r3_tetrahedron_gram_det_q", "1"), "T6_DR3")
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("s75_cat0_rank_gram_det_q", "1/4"), "T6_DRK")
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("s75_cat0_neg_witness_quad_q", "1"), "T6_NQ")
        self._expect_sec_fail(lambda p: p["t6_kron_renormalization_and_curvature"].__setitem__("curvature_trichotomy_strictly_disjoint", False))

    def test_09_verify_dict_fr0_fr1_and_local_pin_traps(self) -> None:
        r_fr1 = V.verify_certificate_dict(self.valid_cert, full_replay=True, track_dir=_THIS_DIR)
        self.assertTrue(r_fr1["valid"] and r_fr1["full_replay"])
        r_fr0 = V.verify_certificate_dict(self.valid_cert, full_replay=False, track_dir=_THIS_DIR)
        self.assertTrue(r_fr0["valid"] and not r_fr0["full_replay"])

        # Non-bool full_replay rejected on both dict and file surfaces
        for bad_fr in (0, 1, "false"):
            with self.assertRaises(O.S85Error):
                V.verify_certificate_dict(self.valid_cert, full_replay=bad_fr)  # type: ignore[arg-type]
            with self.assertRaises(O.S85Error):
                V.check_certificate_file(_THIS_DIR / "s85_mesh_transformations_certificate.json", full_replay=bad_fr)  # type: ignore[arg-type]

        # Envelope tampers (assert exact error codes so schema & payload_sha guards cannot be masked by cert_sha!)
        with self.assertRaises(O.S85Error) as cm_cd:
            V.verify_certificate_dict("not_dict")
        self.assertEqual(cm_cd.exception.code, "INVALID_CERT_TYPE")
        for k, bv, code in (
            ("schema_version", "bad", "SCHEMA_MISMATCH"),
            ("track_id", "bad", "SCHEMA_MISMATCH"),
            ("payload_sha256", "0" * 64, "PAYLOAD_SHA_MISMATCH"),
            ("certificate_sha256", "0" * 64, "CERT_SHA_MISMATCH"),
        ):
            c = copy.deepcopy(self.valid_cert)
            c[k] = bv
            with self.assertRaises(O.S85Error) as cm_e:
                V.verify_certificate_dict(c, full_replay=False)
            self.assertEqual(cm_e.exception.code, code)

        # S85-VER-02 re-signed internal-contradiction & unanchored-bound tampers MUST fail on SEC, FR0, AND FR1!
        def _t1_3_3(p):
            t1 = p["t1_line_graph_and_hodge"]
            t1["wall_grad_energy_q"] = "3"
            t1["wall_curl_energy_q"] = "3"
            t1["wall_grad_pct_dec2"] = "50.00"
            t1["wall_curl_pct_dec2"] = "50.00"

        def _t2_det1(p):
            p["t2_signed_laplacian_and_double_cover"]["l_sigma_det_q"] = "1"

        def _t6_det1(p):
            t6 = p["t6_kron_renormalization_and_curvature"]
            t6["k4_resistance_gram_det_q"] = "1"
            t6["k4_resistance_gram_det_dec8"] = "1.00000000"

        def _gpt6_t1_inc1(p):
            t1 = p["t1_line_graph_and_hodge"]
            t1["line_graph_incident_edges"] = 1
            t1["line_graph_disjoint_pairs"] = 377

        def _gpt6_t2_mc1(p):
            t2 = p["t2_signed_laplacian_and_double_cover"]
            t2["min_unweighted_frustration_cut"] = 1
            t2["best_unweighted_switch_mask"] = 0

        def _t4_unanchored_ab(p):
            t4 = p["t4_directed_ceer_loop_schur"]
            t4["asymmetric_gains_a_b_q"] = ["2", "1/4"]
            t4["monodromy_rho_q"] = "1/2"
            t4["g_loop_forward_q"] = "17/16"
            t4["g_loop_reversed_q"] = "5"
            t4["directional_curvature_asymmetry_q"] = "80/17"
            t4["directional_curvature_asymmetry_dec4"] = "4.7059"
            t4["readout_schur_forward_q"] = "4/17"
            t4["readout_schur_reversed_q"] = "1/20"
            t4["adjoint_gain_direction_invariant_q"] = "2"

        def _t5_fake_budget(p):
            h4 = p["t5_borromean_hypergraph_promotion"]["h4_sovereign_8gib_stack"]
            h4["stack_30bpw_cce_base_mib"] = 100
            h4["lora_r64_mib"] = 100
            h4["csr_sidecar_mib"] = 100
            h4["full_4way_stack_mib"] = 300
            h4["headroom_mib"] = 7892

        resigned_tampers = (
            ("T3_rank6_dups_fake", lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("all_6_walls_holonomy_ranking", ["v6-v7"] * 6), "T3_RANK_ORDER"),
            ("T3_rank6_inverted_fake", lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("all_6_walls_holonomy_ranking", ["v6-v7", "v1-v4", "v0-v4", "v2-v4", "v3-v4", "v1-v5"]), "T3_RANK_ORDER"),
            ("T3_casc_sum_inconsistent", lambda p: p["t3_obstruction_blowup_surgery"]["three_step_cascade"][0].__setitem__("delta_sum_geff_vs_base_dec4", "999.0000"), "T3_CASC_DEC"),
            ("T1_hodge_3_3_fake", _t1_3_3, "T1_HODGE_NG"),
            ("T2_det_lsig_1_fake", _t2_det1, "T2_DET"),
            ("T6_det_k4_1_fake", _t6_det1, "T6_DK4_EXACT"),
            ("S85R2_T3_decimal_5000_digits", lambda p: p["t3_obstruction_blowup_surgery"].__setitem__("base_sum_geff_dec4", "9" * 5000 + ".0000"), "INT_TOO_LARGE"),
            ("S85R2_T4_sy_q_zero_div", lambda p: p["t4_directed_ceer_loop_schur"]["symmetric_t1_t2_t3_q"].__setitem__(0, "0"), "T4_SY_POS"),
            ("GPT6_T1_inc1_disj377", _gpt6_t1_inc1, "INT_OUT_OF_RANGE"),
            ("GPT6_T2_mincut1_mask0", _gpt6_t2_mc1, "INT_OUT_OF_RANGE"),
            ("S85R2_T4_unanchored_ab", _t4_unanchored_ab, "T4_A_EXACT"),
            ("S85R2_T5_fake_budget", _t5_fake_budget, "INT_OUT_OF_RANGE"),
        )
        with tempfile.TemporaryDirectory() as td_rt:
            for idx_rt, (label, mut_fn, exp_code) in enumerate(resigned_tampers):
                c_bad = copy.deepcopy(self.valid_cert)
                mut_fn(c_bad["payload"])
                c_bad = _resign(c_bad)
                with self.assertRaises(O.S85Error, msg=f"{label}:SEC") as cm_s:
                    V.secondary_audit_payload(c_bad["payload"])
                self.assertEqual(cm_s.exception.code, exp_code)
                with self.assertRaises(O.S85Error, msg=f"{label}:FR0") as cm_0:
                    V.verify_certificate_dict(c_bad, full_replay=False, track_dir=_THIS_DIR)
                self.assertEqual(cm_0.exception.code, exp_code)
                with self.assertRaises(O.S85Error, msg=f"{label}:FR1") as cm_1:
                    V.verify_certificate_dict(c_bad, full_replay=True, track_dir=_THIS_DIR)
                self.assertEqual(cm_1.exception.code, exp_code)
                if label in ("S85R2_T3_decimal_5000_digits", "S85R2_T4_sy_q_zero_div"):
                    p_cli = Path(td_rt) / f"bad_{idx_rt}.json"
                    p_cli.write_bytes(O.canonical_json_bytes(c_bad))
                    out_b, err_b = io.StringIO(), io.StringIO()
                    with mock.patch.object(sys, "stdout", out_b), mock.patch.object(sys, "stderr", err_b):
                        rc_cli = V.main(["--check", str(p_cli), "--json"])
                    self.assertEqual(rc_cli, 2, msg=label)
                    self.assertEqual(json.loads(err_b.getvalue())["code"], exp_code)

        # Exhaustive 337/337 single-leaf re-signed SEC + FR0 guard (both basic AND +1 ULP numeric-preserving bumps!)
        def _iter_leaves(obj, prefix=""):
            if type(obj) is dict:
                for kk, vv in obj.items():
                    yield from _iter_leaves(vv, f"{prefix}.{kk}" if prefix else kk)
            elif type(obj) is list:
                for ii, vv in enumerate(obj):
                    yield from _iter_leaves(vv, f"{prefix}.{ii}")
            else:
                yield prefix, obj

        def _set_leaf(obj, path, val):
            parts = path.split(".")
            cur = obj
            for part in parts[:-1]:
                cur = cur[int(part)] if type(cur) is list else cur[part]
            last = parts[-1]
            if type(cur) is list:
                cur[int(last)] = val
            else:
                cur[last] = val

        def _smart_bump(v):
            if type(v) is bool:
                return not v
            if type(v) is int:
                return v + 1
            if "/" in v:
                a_s, b_s = v.split("/", 1)
                a_body = a_s[1:] if a_s.startswith("-") else a_s
                if O.is_ascii_digits(a_body) and O.is_ascii_digits(b_s):
                    return O.q_str(Fraction(int(a_s) + 1, int(b_s)))
            if "." in v:
                a_s, b_s = v.split(".", 1)
                a_body = a_s[1:] if a_s.startswith("-") else a_s
                if O.is_ascii_digits(a_body) and O.is_ascii_digits(b_s):
                    pl = len(b_s)
                    return O.dec_from_q(V.parse_decimal_str_to_q(v, pl, "sb") + Fraction(1, 10 ** pl), pl)
            v_body = v[1:] if v.startswith("-") else v
            if O.is_ascii_digits(v_body):
                return str(int(v) + 1)
            return v + "x"

        leaves = list(_iter_leaves(self.valid_cert["payload"]))
        self.assertEqual(len(leaves), 337)
        for path, orig_val in leaves:
            for mode_lbl, new_val in (
                ("basic", (not orig_val) if type(orig_val) is bool else (orig_val + 1 if type(orig_val) is int else orig_val + "x")),
                ("smart", _smart_bump(orig_val)),
            ):
                c_leaf = copy.deepcopy(self.valid_cert)
                _set_leaf(c_leaf["payload"], path, new_val)
                c_leaf = _resign(c_leaf)
                with self.assertRaises(O.S85Error, msg=f"SEC:{mode_lbl}:{path}"):
                    V.secondary_audit_payload(c_leaf["payload"])
                with self.assertRaises(O.S85Error, msg=f"FR0:{mode_lbl}:{path}"):
                    V.verify_certificate_dict(c_leaf, full_replay=False, track_dir=_THIS_DIR)

        # FR0 accepts semantically valid re-signed order swap (swapping two T3 surgery rows), FR1 rejects!
        c_sub = copy.deepcopy(self.valid_cert)
        srows_sub = c_sub["payload"]["t3_obstruction_blowup_surgery"]["single_surgery_rows"]
        srows_sub[0], srows_sub[1] = srows_sub[1], srows_sub[0]
        c_sub = _resign(c_sub)
        self.assertTrue(V.verify_certificate_dict(c_sub, full_replay=False)["valid"])
        with self.assertRaises(O.S85Error) as cm_fr1:
            V.verify_certificate_dict(c_sub, full_replay=True, track_dir=_THIS_DIR)
        self.assertEqual(cm_fr1.exception.code, "FULL_REPLAY_MISMATCH")

        # _load_local_lean_pins failure traps
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "MeshTransformationsUnlock.lean").write_bytes(b"\xff")
            with self.assertRaises(O.S85Error) as cm_lu:
                V._load_local_lean_pins(d)
            self.assertEqual(cm_lu.exception.code, "INVALID_UTF8")
            (d / "MeshTransformationsUnlock.lean").write_bytes((_THIS_DIR / "MeshTransformationsUnlock.lean").read_bytes())
            (d / "lakefile.toml").write_bytes((_THIS_DIR / "lakefile.toml").read_bytes())
            (d / "lean-toolchain").write_bytes(b"\xff")
            with self.assertRaises(O.S85Error) as cm_tu:
                V._load_local_lean_pins(d)
            self.assertEqual(cm_tu.exception.code, "INVALID_UTF8")
            (d / "lean-toolchain").write_text("leanprover/lean4:v4.0.0\n", encoding="utf-8")
            with self.assertRaises(O.S85Error) as cm_tm:
                V._load_local_lean_pins(d)
            self.assertEqual(cm_tm.exception.code, "TOOLCHAIN_MISMATCH")

    def test_10_cli_parser_and_entrypoints(self) -> None:
        # _parse_cli_args positive & negative coverage
        self.assertEqual(V._parse_cli_args([]), {"mode": "default", "target": None, "json": False})
        self.assertEqual(V._parse_cli_args(["--standalone"]), {"mode": "standalone", "target": None, "json": False})
        self.assertEqual(V._parse_cli_args(["--check=a.json", "--json"]), {"mode": "check", "target": "a.json", "json": True})
        self.assertEqual(V._parse_cli_args(["--write=b.json"]), {"mode": "write", "target": "b.json", "json": False})
        self.assertEqual(V._parse_cli_args(["--verify-lean=c.lean"]), {"mode": "verify-lean", "target": "c.lean", "json": False})
        with self.assertRaises(O.S85Error) as cm_av:
            V._parse_cli_args("--standalone")  # type: ignore[arg-type]
        self.assertEqual(cm_av.exception.code, "INVALID_ARGV")
        with self.assertRaises(O.S85Error) as cm_an:
            V._parse_cli_args(["a\x00b"])
        self.assertEqual(cm_an.exception.code, "NUL_BYTE_FORBIDDEN")
        for bad_argv in (
            ["--json", "--json"],
            ["--standalone", "--standalone"],
            ["--standalone", "--check", "a"],
            ["--check"],
            ["--check", "a\x00b"],
            ["--check", ""],
            ["--check", "-bad"],
            ["--standalone", "--check=a"],
            ["--check="],
            ["--check=-bad"],
            ["--unknown"],
        ):
            with self.assertRaises(O.S85Error):
                V._parse_cli_args(bad_argv)

        # Exercise main() modes capturing stdout/stderr
        disk_cert = _THIS_DIR / "s85_mesh_transformations_certificate.json"
        for argv, exp_rc in (
            ([], 0),
            (["--json"], 0),
            (["--standalone"], 0),
            (["--check", str(disk_cert)], 0),
            (["--check", str(disk_cert), "--json"], 0),
            (["--unknown"], 2),
        ):
            out_buf = io.StringIO()
            err_buf = io.StringIO()
            with mock.patch.object(sys, "stdout", out_buf), mock.patch.object(sys, "stderr", err_buf):
                rc = V.main(argv)
            self.assertEqual(rc, exp_rc, msg=f"argv={argv} err={err_buf.getvalue()}")
            if argv == ["--standalone"]:
                self.assertEqual(out_buf.getvalue().encode("ascii"), disk_cert.read_bytes())

        # --write text & json modes into temp dir
        with tempfile.TemporaryDirectory() as td:
            for extra in ([], ["--json"]):
                out_p = Path(td) / f"c_{len(extra)}.json"
                out_buf = io.StringIO()
                with mock.patch.object(sys, "stdout", out_buf):
                    rc = V.main(["--write", str(out_p)] + extra)
                self.assertEqual(rc, 0)
                self.assertEqual(out_p.read_bytes(), disk_cert.read_bytes())

        # --verify-lean CLI mode (works both with live lean and fail-closed in Lean-less CI!)
        lean_p = _THIS_DIR / "MeshTransformationsUnlock.lean"
        lean_avail = True
        try:
            V.resolve_lean_binary()
        except O.S85Error:
            lean_avail = False
        for extra in ([], ["--json"]):
            out_buf = io.StringIO()
            err_buf = io.StringIO()
            with mock.patch.object(sys, "stdout", out_buf), mock.patch.object(sys, "stderr", err_buf):
                rc = V.main(["--verify-lean", str(lean_p)] + extra)
            if lean_avail:
                self.assertEqual(rc, 0)
            else:
                self.assertEqual(rc, 2)
                self.assertIn("LEAN_BINARY_UNAVAILABLE", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
