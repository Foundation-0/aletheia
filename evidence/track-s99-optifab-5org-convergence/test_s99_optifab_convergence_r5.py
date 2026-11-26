#!/usr/bin/env python3
"""Track S99 R5 Assertion-Free Comprehensive Verification & Mutation-Killing Suite.

Zero bare asserts (survives all three isolated R4 modes), zero floats, zero skips
under both live-Lean and Lean-less CI environments (`env -i PATH=/usr/bin:/bin`
and `HOME=/nonexistent`), designed for 100.0% kill on `aletheia-fast-mutate`
(`--guards require_ok`) and whole-file DFS AST `BoolOp` mutation testing.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import types
from typing import Any

TRACK_DIR = Path(__file__).resolve().parent
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import s99_optifab_convergence_oracle as oracle  # noqa: E402
import verify_s99_optifab_convergence as ver  # noqa: E402


class TestFailure(RuntimeError):
    """Raised when any assertion-free R5 test invariant fails."""


def expect(cond: bool, msg: str) -> None:
    if not cond:
        raise TestFailure(msg)


def expect_raises(fn: Any, *args: Any, **kwargs: Any) -> None:
    try:
        fn(*args, **kwargs)
    except ver.VerificationError:
        return
    raise TestFailure(f"expected VerificationError from {fn}")


def expect_raises_msg(fn: Any, needle: str, *args: Any, **kwargs: Any) -> None:
    try:
        fn(*args, **kwargs)
    except ver.VerificationError as exc:
        if needle not in str(exc):
            raise TestFailure(f"expected {needle!r} in VerificationError {exc!r}") from exc
        return
    raise TestFailure(f"expected VerificationError({needle!r}) from {fn}")


def _resign(cert: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(cert)
    p_sha = oracle.sha256_canonical(out["payload"])
    out["payload_sha256"] = p_sha
    body = {
        "schema_version": out["schema_version"],
        "track_id": out["track_id"],
        "payload": out["payload"],
        "payload_sha256": p_sha,
    }
    out["certificate_sha256"] = oracle.sha256_canonical(body)
    return out


def _tamper_scalar(val: Any) -> Any:
    if type(val) is bool:
        return not val
    if type(val) is int:
        return val + 1
    if type(val) is str:
        if val == "ok":
            return "bad"
        if len(val) == 64 and all(ch in ver.HEX_LOWER for ch in val):
            return ("0" if val[0] != "0" else "1") + val[1:]
        if "/" in val:
            parts = val.split("/")
            if len(parts) == 2 and all(
                len(p.lstrip("-")) > 0 and all("0" <= c <= "9" for c in p.lstrip("-"))
                for p in parts
            ):
                return f"{int(parts[0]) + 1}/{parts[1]}"
            return val + "_x"
        if val.replace("-", "").replace(".", "").isascii() and val.count(".") == 1:
            return val[:-1] + ("0" if val[-1] != "0" else "1")
        if val.lstrip("-").isascii() and all("0" <= c <= "9" for c in val.lstrip("-")) and val != "":
            return str(int(val) + 1)
        return val + "_x"
    if val is None:
        return ["0"] * 6
    raise TestFailure(f"unexpected scalar type: {type(val)}")


def _walk_and_tamper_tree(root: Any, mutate_fn: Any, path_prefix: str = "") -> int:
    """Exhaustively tamper every dict key (extra/missing) and leaf scalar in payload."""
    count = 0
    stack: list[tuple[list[Any], Any, str]] = [([], root, path_prefix)]
    while stack:
        keys_path, cur, label = stack.pop()
        if type(cur) is dict:
            for mode in ("extra", "missing"):
                clone = copy.deepcopy(root)
                target = clone
                for kp in keys_path:
                    target = target[kp]
                if mode == "extra":
                    target["__s99_extra_key__"] = 1
                else:
                    first_k = next(iter(target.keys()))
                    del target[first_k]
                mutate_fn(clone, f"{label}:{mode}")
                count += 1
            for k, v in cur.items():
                stack.append((keys_path + [k], v, f"{label}.{k}"))
        elif type(cur) is list:
            clone_short = copy.deepcopy(root)
            t_short = clone_short
            for kp in keys_path[:-1]:
                t_short = t_short[kp]
            if keys_path:
                t_short[keys_path[-1]] = cur[:-1] if len(cur) > 0 else ["extra"]
                mutate_fn(clone_short, f"{label}:list_len")
                count += 1
                clone_type = copy.deepcopy(root)
                t_type = clone_type
                for kp in keys_path[:-1]:
                    t_type = t_type[kp]
                t_type[keys_path[-1]] = "not_a_list"
                mutate_fn(clone_type, f"{label}:list_type")
                count += 1
            for idx, item in enumerate(cur):
                stack.append((keys_path + [idx], item, f"{label}[{idx}]"))
        else:
            clone = copy.deepcopy(root)
            parent = clone
            for kp in keys_path[:-1]:
                parent = parent[kp]
            parent[keys_path[-1]] = _tamper_scalar(cur)
            mutate_fn(clone, f"{label}:val")
            count += 1
            if type(cur) is bool:
                clone_t = copy.deepcopy(root)
                pt = clone_t
                for kp in keys_path[:-1]:
                    pt = pt[kp]
                pt[keys_path[-1]] = 1 if cur else 0
                mutate_fn(clone_t, f"{label}:int_for_bool")
                count += 1
            elif type(cur) is int and cur in (0, 1):
                clone_t = copy.deepcopy(root)
                pt = clone_t
                for kp in keys_path[:-1]:
                    pt = pt[kp]
                pt[keys_path[-1]] = True if cur == 1 else False
                mutate_fn(clone_t, f"{label}:bool_for_int")
                count += 1
            elif type(cur) is str:
                clone_t = copy.deepcopy(root)
                pt = clone_t
                for kp in keys_path[:-1]:
                    pt = pt[kp]
                pt[keys_path[-1]] = 123
                mutate_fn(clone_t, f"{label}:int_for_str")
                count += 1
    return count


def test_01_baseline_and_field_complete_sec_fr0_fr1() -> None:
    cert = oracle.build_certificate()
    ver.verify_certificate_dict(cert)
    ver.verify_payload_dict(cert["payload"])
    ver.secondary_audit_payload(cert["payload"])

    disk_cert = ver.verify_certificate_file(ver.DEFAULT_CERT_PATH)
    expect(disk_cert == cert, "disk certificate diverges from oracle")

    # S99-VER-03: Zero mutable global aliases in oracle.build_certificate() + live in-process forgery/TypeError resistance
    def _mutable_ids(obj: Any) -> set[int]:
        ids: set[int] = set()
        stk: list[Any] = [obj]
        while stk:
            cur = stk.pop()
            if type(cur) is dict:
                ids.add(id(cur))
                stk.extend(cur.values())
            elif type(cur) is list:
                ids.add(id(cur))
                stk.extend(cur)
            elif type(cur) is tuple:
                stk.extend(cur)
        return ids

    global_mut_ids = _mutable_ids(
        (
            oracle.PROPOSAL_MESH_NODES,
            oracle.THREE_NODE_EXECUTION_NODES,
            oracle.UPSTREAM_OPTIFAB_PIN,
            oracle.ASKA_PUBLIC_SIBLING_HEADS,
            oracle.UPSTREAM_EXPEDITION_CERTS,
        )
    )
    cert_mut_ids = _mutable_ids(cert)
    expect(len(global_mut_ids & cert_mut_ids) == 0, "oracle.build_certificate() aliased mutable module globals")

    inproc_title = oracle.build_certificate()
    orig_title = oracle.PROPOSAL_MESH_NODES[0]["title"]
    inproc_title["payload"]["pillar_3_proposals_k8_5org_mesh"]["proposals"][0]["title"] = "FORGED_TITLE"
    expect(oracle.PROPOSAL_MESH_NODES[0]["title"] == orig_title, "mutating cert title must not mutate oracle global")
    expect_raises(ver.secondary_audit_payload, inproc_title["payload"])
    expect_raises(ver.verify_certificate_dict, _resign(inproc_title))

    inproc_none = oracle.build_certificate()
    inproc_none["payload"]["pillar_3_proposals_k8_5org_mesh"]["proposals"][0]["required_orgs"] = None
    expect(oracle.PROPOSAL_MESH_NODES[0]["required_orgs"] is not None, "mutating required_orgs must not mutate global")
    expect_raises(ver.secondary_audit_payload, inproc_none["payload"])

    def check_sec_rejects(tampered_payload: dict[str, Any], tag: str) -> None:
        try:
            ver.secondary_audit_payload(tampered_payload)
        except ver.VerificationError:
            return
        raise TestFailure(f"SEC bypass on {tag}")

    n_muts = _walk_and_tamper_tree(cert["payload"], check_sec_rejects, "payload")
    expect(n_muts >= 400, f"expected >= 400 exhaustive SEC tampers, got {n_muts}")

    # Explicit non-negative witness tests (qf == 0 and qf > 0 with matching negative_witness_quad_form_q!)
    ovl_zero = copy.deepcopy(cert["payload"]["pillar_2_coupled_physical_digital_gate"]["schur_coupled_gate"]["overload_eta3"])
    ovl_zero["negative_witness_vec_q"] = ["0", "0", "0", "0", "0", "0"]
    ovl_zero["negative_witness_quad_form_q"] = "0"
    expect_raises(ver._verify_coupled_regime, ovl_zero, Fraction(3, 1), "ovl_zero")

    ovl_pos = copy.deepcopy(cert["payload"]["pillar_2_coupled_physical_digital_gate"]["schur_coupled_gate"]["overload_eta3"])
    ovl_pos["negative_witness_vec_q"] = ["1", "0", "0", "0", "0", "0"]
    ovl_pos["negative_witness_quad_form_q"] = "2"
    expect_raises(ver._verify_coupled_regime, ovl_pos, Fraction(3, 1), "ovl_pos")

    # Exact tuple-instead-of-list type guards on direct pillar verifiers
    ovl_tup = copy.deepcopy(cert["payload"]["pillar_2_coupled_physical_digital_gate"]["schur_coupled_gate"]["overload_eta3"])
    ovl_tup["negative_witness_vec_q"] = tuple(ovl_tup["negative_witness_vec_q"])
    expect_raises(ver._verify_coupled_regime, ovl_tup, Fraction(3, 1), "ovl_tup")

    p2_tup1 = copy.deepcopy(cert["payload"]["pillar_2_coupled_physical_digital_gate"])
    p2_tup1["physical_limit_states"] = tuple(p2_tup1["physical_limit_states"])
    expect_raises(ver._verify_pillar2, p2_tup1)

    p2_tup2 = copy.deepcopy(cert["payload"]["pillar_2_coupled_physical_digital_gate"])
    p2_tup2["frame_contract_checks"] = tuple(p2_tup2["frame_contract_checks"])
    expect_raises(ver._verify_pillar2, p2_tup2)

    p3_tup1 = copy.deepcopy(cert["payload"]["pillar_3_proposals_k8_5org_mesh"])
    p3_tup1["proposals"] = tuple(p3_tup1["proposals"])
    expect_raises(ver._verify_pillar3, p3_tup1)

    p3_tup2 = copy.deepcopy(cert["payload"]["pillar_3_proposals_k8_5org_mesh"])
    p3_tup2["borromean_5org_obstruction"]["four_org_failure_witnesses"] = tuple(
        p3_tup2["borromean_5org_obstruction"]["four_org_failure_witnesses"]
    )
    expect_raises(ver._verify_pillar3, p3_tup2)

    p3_tup3 = copy.deepcopy(cert["payload"]["pillar_3_proposals_k8_5org_mesh"])
    p3_tup3["three_node_execution_plan"]["nodes"] = tuple(
        p3_tup3["three_node_execution_plan"]["nodes"]
    )
    expect_raises(ver._verify_pillar3, p3_tup3)

    # Re-signed FR1 rejection samples across all 4 pillars
    for mut_fn in (
        lambda p: p["pillar_1_optifab14_defects_and_repairs"]["defect_14_3_equal_objective_headroom_decay"].__setitem__("v033_headroom_after_ppm", 318),
        lambda p: p["pillar_2_coupled_physical_digital_gate"]["schur_coupled_gate"]["overload_eta3"].__setitem__("r5_coupled_verdict", "ADMIT"),
        lambda p: p["pillar_2_coupled_physical_digital_gate"]["schur_coupled_gate"]["nominal_eta1"].__setitem__("negative_witness_quad_form_q", "-1"),
        lambda p: p["pillar_2_coupled_physical_digital_gate"]["physical_limit_states"][0].__setitem__("headroom_dec6", "0.820901"),
        lambda p: p["pillar_3_proposals_k8_5org_mesh"]["three_node_execution_plan"]["nodes"][0].__setitem__("hardware_profile", "short"),
        lambda p: p["pillar_4_lean4_and_provenance"]["epistemic_scope"].__setitem__("n2_claims_count", 1),
    ):
        c2 = copy.deepcopy(cert)
        mut_fn(c2["payload"])
        c2 = _resign(c2)
        expect_raises(ver.verify_certificate_dict, c2)

    # Forged payload_sha256 with self-consistent outer certificate_sha256 (kills M145!)
    forged_p = copy.deepcopy(cert)
    forged_p["payload_sha256"] = "0" * 64
    forged_p["certificate_sha256"] = oracle.sha256_canonical(
        {
            "schema_version": forged_p["schema_version"],
            "track_id": forged_p["track_id"],
            "payload": forged_p["payload"],
            "payload_sha256": forged_p["payload_sha256"],
        }
    )
    expect_raises(ver.verify_certificate_dict, forged_p)

    # Outer envelope FR1 tampers
    for bad_env in (
        {**cert, "extra": 1},
        {k: v for k, v in cert.items() if k != "track_id"},
        {**cert, "schema_version": "wrong"},
        {**cert, "track_id": "wrong"},
        {**cert, "payload_sha256": 123},
        {**cert, "payload_sha256": "abc"},
        {**cert, "payload_sha256": "G" * 64},
        {**cert, "certificate_sha256": "0" * 64},
    ):
        expect_raises(ver.verify_certificate_dict, bad_env)


def test_02_strict_rational_and_tree_parsers() -> None:
    # Direct helper type & digest checks
    expect_raises(ver._require_eq_int_list, (0, 3, 6, 7), [0, 3, 6, 7], "tup")
    expect_raises(ver._require_eq_str_list, "ab", ["a", "b"], "str_as_list")
    expect_raises(ver._require_sha256_hex, "a" * 63, "short_hex")
    expect_raises(ver._require_sha256_hex, "A" * 64, "upper_hex")
    expect_raises(ver._check_keys, types.SimpleNamespace(keys=lambda: {"a"}), {"a"}, "ns_keys")

    expect(ver._parse_q_strict("-3/5", "neg") == Fraction(-3, 5), "negative rational parse")
    expect(ver._parse_q_strict("7", "int") == Fraction(7, 1), "int rational parse")
    # S99-VER-01: exact 620-digit rational boundary PASS, 621-digit & 5000-digit FAIL cleanly (zero raw ValueError!), and >2 slashes
    expect(ver._parse_q_strict("9" * ver.MAX_INT_DIGITS, "q620") == Fraction(int("9" * ver.MAX_INT_DIGITS), 1), "620-digit rational")
    expect_raises_msg(ver._parse_q_strict, "invalid rational format", "1/2/3", "q3")
    expect_raises_msg(ver._parse_q_strict, "rational digits exceed", "9" * (ver.MAX_INT_DIGITS + 1), "q621")
    expect_raises_msg(ver._parse_q_strict, "rational digits exceed", "9" * 5000, "q5000")
    expect_raises_msg(ver._parse_q_strict, "rational digits exceed", "1/" + "9" * 5000, "q5000_den")
    for bad_q in (123, "", "/", "1/", "/2", "-/2", "1/2/3", "1/a", "a/2", "1/0", "1/-2", "2/4", "4/2", "1/1", "1/\u0662"):
        expect_raises(ver._parse_q_strict, bad_q, "bad_q")

    # S99-VER-01 4-surface check: re-signed 5000-digit rational string fails cleanly on SEC, FR0, FR1 (zero raw ValueError)
    for big_q in ("9" * 5000, "1/" + "9" * 5000):
        big_cert = oracle.build_certificate()
        big_cert["payload"]["pillar_1_optifab14_defects_and_repairs"]["defect_14_1_outage_constant"]["double_subtracted_const_kw_q"] = big_q
        big_cert = _resign(big_cert)
        expect_raises_msg(ver.secondary_audit_payload, "rational digits exceed", big_cert["payload"])
        expect_raises_msg(ver.verify_payload_dict, "rational digits exceed", big_cert["payload"])
        expect_raises_msg(ver.verify_certificate_dict, "rational digits exceed", big_cert)

    # Exact depth == 64 boundary PASS & depth == 65 FAIL
    d64: Any = 1
    for _ in range(ver.MAX_JSON_DEPTH):
        d64 = [d64]
    ver.validate_json_tree_iterative(d64, "exact_depth_64")
    expect_raises(ver.validate_json_tree_iterative, [d64], "depth_65")

    # Exact bit_length == 2048 boundary PASS & 2049 FAIL
    max_2048 = (1 << ver.MAX_INT_BITS) - 1
    ver.validate_json_tree_iterative({"a": max_2048}, "exact_2048")
    expect_raises(ver.validate_json_tree_iterative, {"a": 1 << ver.MAX_INT_BITS}, "bits_2049")

    # Tree validator negative cases
    expect_raises(ver.validate_json_tree_iterative, {1: "a"}, "non_str_key")
    expect_raises(ver.validate_json_tree_iterative, {"\ud800": 1}, "surr_key")
    expect_raises(ver.validate_json_tree_iterative, {"a": "\ud800"}, "surr_val")
    expect_raises(ver.validate_json_tree_iterative, {"a": (1, 2)}, "tuple_forbidden")

    class SubInt(int):
        pass

    expect_raises(ver.validate_json_tree_iterative, {"a": SubInt(1)}, "sub_int")

    # Direct capped int parser boundary checks: exact 620 digits PASS, exact 2048 bits PASS, 5000 digits -> VerificationError!
    expect(ver._parse_capped_int_token("0" * (ver.MAX_INT_DIGITS - 1) + "1") == 1, "exact 620 digits")
    expect(ver._parse_capped_int_token(str(max_2048)) == max_2048, "exact 2048 bits")
    expect(ver._parse_capped_int_token("-42") == -42, "neg capped int")
    expect_raises(ver._parse_capped_int_token, "9" * 5000)
    expect_raises(ver._parse_capped_int_token, str(1 << ver.MAX_INT_BITS))
    expect_raises(ver._forbid_float_token, "1.5")
    expect_raises(ver._forbid_constant_token, "NaN")
    expect_raises(ver._no_dup_pairs_hook, [("a", 1), ("a", 2)])


def test_03_zone_b_filesystem_and_atomic_write() -> None:
    cert = oracle.build_certificate()
    with tempfile.TemporaryDirectory(prefix="s99_zb_") as td:
        base = Path(td)

        out_p = base / "cert.json"
        ver._write_json_atomic_0600(out_p, cert)
        st = os.lstat(str(out_p))
        expect(stat.S_IMODE(st.st_mode) == 0o600, "cert mode must be 0o600")
        ver.verify_certificate_file(out_p)
        ver._write_json_atomic_0600(out_p, cert)

        hl = base / "hardlink.json"
        os.link(str(out_p), str(hl))
        expect_raises(ver.verify_certificate_file, hl)
        expect_raises(ver._write_json_atomic_0600, hl, cert)
        os.unlink(str(hl))

        sl = base / "symlink.json"
        os.symlink(str(out_p), str(sl))
        expect_raises(ver.verify_certificate_file, sl)
        expect_raises(ver._write_json_atomic_0600, sl, cert)

        real_dir = base / "realdir"
        real_dir.mkdir(mode=0o700)
        ver._write_json_atomic_0600(real_dir / "c.json", cert)
        link_dir = base / "linkdir"
        os.symlink(str(real_dir), str(link_dir))
        expect_raises(ver.verify_certificate_file, link_dir / "c.json")

        # Directory & FIFO direct checks (kills M060 & M078!)
        expect_raises(ver.verify_certificate_file, real_dir)
        expect_raises(ver._write_json_atomic_0600, real_dir, cert)
        fifo = base / "pipe.json"
        os.mkfifo(str(fifo), 0o600)
        expect_raises(ver._read_regular_bytes_strict, fifo, 100, "fifo_direct")
        expect_raises(ver._write_json_atomic_0600, fifo, cert)

        # Permissions checks
        gw = base / "gw.json"
        ver._write_json_atomic_0600(gw, cert)
        os.chmod(str(gw), 0o644)
        ver.verify_certificate_file(gw)
        os.chmod(str(gw), 0o660)
        expect_raises(ver.verify_certificate_file, gw)
        os.chmod(str(gw), 0o602)
        expect_raises(ver.verify_certificate_file, gw)

        # Direct _read_json_strict cases (kills M074 & M076!)
        for name, content in (
            ("nul", b'{"a":1}\x00'),
            ("crlf", b'{\r\n  "a": 1\r\n}\r\n'),
            ("utf8", b"\xff\xfe"),
            ("syntax", b"{bad"),
            ("dup", b'{"a":1,"a":2}\n'),
            ("flt", b'{"a":1.5}\n'),
            ("nan", b'{"a":NaN}\n'),
            ("huge", ('{"a":' + "9" * 625 + "}\n").encode("ascii")),
            ("deep", ("[" * 100 + "]" * 100 + "\n").encode("ascii")),
            ("listroot", b"[\n  1\n]\n"),
            ("noncanon", b'{"a":1}\n'),
        ):
            fp = base / f"bad_{name}.json"
            fp.write_bytes(content)
            os.chmod(str(fp), 0o600)
            expect_raises(ver._read_json_strict, fp, f"bad_{name}")

        # Exact stream size boundary: 10 bytes PASS at max_bytes=10, FAIL at max_bytes=9 (kills M067 & M068!)
        exact_f = base / "exact10.bin"
        exact_f.write_bytes(b"0123456789")
        os.chmod(str(exact_f), 0o600)
        expect(ver._read_regular_bytes_strict(exact_f, 10, "eq10") == b"0123456789", "exact max_bytes pass")
        expect_raises(ver._read_regular_bytes_strict, exact_f, 9, "over9")

        # Path validation edge cases (real_dir / ".." uses an EXISTING dir -> kills M055!)
        expect_raises(ver._open_parent_dir_fd, Path("a\x00b"), "nul_path")
        expect_raises(ver._open_parent_dir_fd, Path("a\ud800b"), "surr_path")
        expect_raises(ver._open_parent_dir_fd, Path(".."), "dotdot_leaf")
        expect_raises(ver._open_parent_dir_fd, Path("/"), "empty_leaf")
        expect_raises(ver._open_parent_dir_fd, real_dir / ".." / "cert.json", "dotdot_real_anc")
        expect_raises(ver._open_parent_dir_fd, base / "nonexistent" / "cert.json", "missing_anc")

        # Relative path + $PWD symlink / unset / relative / nonexistent / lone-surrogate checks
        old_cwd = os.getcwd()
        old_pwd = os.environ.get("PWD")
        try:
            os.chdir(str(base))
            os.environ["PWD"] = str(link_dir)
            expect_raises(ver.verify_certificate_file, Path("cert.json"))
            os.environ["PWD"] = "/nonexistent_s99_dir_xyz"
            ver.verify_certificate_file(Path("cert.json"))
            os.environ["PWD"] = "relative/pwd"
            ver.verify_certificate_file(Path("cert.json"))
            os.environ.pop("PWD", None)
            ver.verify_certificate_file(Path("cert.json"))
            os.environ["PWD"] = os.fsdecode(b"/bad\xffpwd")
            expect_raises(ver._check_pwd_no_symlinks)
        finally:
            os.chdir(old_cwd)
            if old_pwd is None:
                os.environ.pop("PWD", None)
            else:
                os.environ["PWD"] = old_pwd

        # Strict `is False` check kills M048!
        dfd = os.open(str(base), os.O_RDONLY | os.O_DIRECTORY)
        try:
            expect(ver._is_symlink_at(dfd, "no_such_entry") is False, "missing symlink_at must return False")
            expect(ver._is_symlink_at(dfd, "symlink.json") is True, "real symlink_at must return True")
        finally:
            os.close(dfd)


def test_04_r11_lean_static_and_live_gate() -> None:
    real_src = ver.DEFAULT_LEAN_PATH.read_text(encoding="utf-8")
    found = ver.static_scan_lean(real_src)
    expect(len(found) == 18, "expected 18 theorems")

    # Zero false positives on clean controls (decide (native := false / Bool.false), export, attribute [simp], nested comments)
    expect(ver._strip_lean_comments("/- -- -/\n") == "\n", "dash inside block comment must not eat closer")
    clean_with_decide = (
        real_src
        + "\n/- outer /- nested sorry -- axiom -/ comment -/\n"
        + "-- line comment with sorry and native_decide\n"
        + "export Nat (succ)\n"
        + "attribute [simp] init_eq\n"
        + "def cleanDecCheck : Bool := by decide (native := false)\n"
        + "def cleanDecBoolFalse : Bool := by decide (native := Bool.false)\n"
    )
    expect(len(ver.static_scan_lean(clean_with_decide)) == 18, "0 FP on clean controls")

    # Comment & structural scanner errors (`-/ /-` kills M083 & M084; lone `«` kills M089; empty expected kills M092/M093!)
    expect_raises(ver._strip_lean_comments, "-/ /-")
    expect_raises(ver.static_scan_lean, real_src + "\x00")
    expect_raises(ver.static_scan_lean, real_src + "\n/- unterminated")
    expect_raises(ver.static_scan_lean, real_src + "\n-/\n")
    expect_raises(ver.static_scan_lean, real_src + '\ndef s := "hi"\n')
    expect_raises(ver.static_scan_lean, real_src + "\ndef «a := 1\n")
    expect_raises(ver.static_scan_lean, real_src + "\ndef a» := 1\n")
    expect_raises(ver.static_scan_lean, "def x := 1\n", ())
    expect_raises(ver.static_scan_lean, real_src + "\ntheorem defect14_1_outage_constant_positive_error : 1 = 1 := rfl\n")
    expect_raises(ver.static_scan_lean, "theorem wrong_name : 1 = 1 := rfl\n")
    # S99-VER-02 theorem-discovery regressions: private/protected theorem & lemma MUST be discovered & fail theorem-set check
    expect_raises_msg(ver.static_scan_lean, "theorem set mismatch", real_src + "\nprivate theorem _priv_extra : 1 = 1 := rfl\n")
    expect_raises_msg(ver.static_scan_lean, "theorem set mismatch", real_src + "\nprotected theorem _prot_extra : 1 = 1 := rfl\n")
    expect_raises_msg(ver.static_scan_lean, "theorem set mismatch", real_src + "\nlemma _lem_extra : 1 = 1 := rfl\n")

    # Exhaustive R12 escape snippets (every single pattern in FORBIDDEN_LEAN_PATTERNS + 9 live bypasses)
    escape_snippets = [
        "import Init\n",
        "def f := sorry\n",
        "def f : False := _root_.sorryAx False false\n",
        "def f := Lean.Meta.mkSorry\n",
        "def f := admit\n",
        "axiom bad : Prop\n",
        "unsafe def f := 1\n",
        "@[implemented_by x] def f := 1\n",
        "@[extern c_fn] def f := 1\n",
        "@[csimp] private theorem _f_csimp : 1 = 1 := rfl\n",
        "attribute [csimp] _f_csimp\n",
        "noncomputable def _nc : Nat := 0\n",
        "@[export c_sym] def f (n : Nat) : Nat := n\n",
        "attribute [export c_sym] f\n",
        "@[init] def myInit : IO Unit := pure ()\n",
        "attribute [local init] myInit\n",
        "@[builtin_init] def myBInit : IO Unit := pure ()\n",
        "attribute [builtin_init] myBInit\n",
        "def f := by native_decide\n",
        "def f := by decide +native\n",
        "def f := by decide +revert +native\n",
        "def f := by decide +revert (config := { native })\n",
        "def f := { ({} : _) with native }\n",
        "def f := by decide (native := true)\n",
        "def f := by decide (native := false || true)\n",
        "def f := by decide (native := false == false)\n",
        "def f := by decide (native := false != true)\n",
        "def f := by decide (native := false.not)\n",
        "def f := by decide (native := false\n|| true)\n",
        "def f := by decide (native := false -- c\n|| true)\n",
        "def f : DecideConfig := default\n",
        "def f : Decide.Config := default\n",
        "def f := Lean.ofReduceBool\n",
        "def f := Lean.ofReduceNat\n",
        "def f := Lean.trustCompiler\n",
        "def f := Lean.Elab.Command.elabCommand\n",
        "def f := Classical.choice\n",
        "def f := Classical.em\n",
        "def f := Classical.byContradiction\n",
        "def f := debug.skipKernelTC\n",
        "def f := debug.byAsSorry\n",
        "def f := debug.proofAsSorry\n",
        "def f := debug.terminalTacticsAsSorry\n",
        "set_option warn.sorry false\n",
        "def f := dbg_trace 1\n",
        "def f := _root_.dbgTrace (String.ofList []) (fun _ => 0)\n",
        "def f := dbgTraceVal 1\n",
        "def f := dbgTraceValId 1\n",
        "def f := dbgTraceIfShared (String.ofList []) 1\n",
        "def f := dbgSleep 0 (fun _ => 0)\n",
        "def f := dbgStackTrace 0\n",
        "def f : Nat := panicWithPosWithDecl (String.ofList []) (String.ofList []) 1 1 (String.ofList [])\n",
        "def f : Nat := panic! (String.ofList [])\n",
        "def f : Nat := unreachable!\n",
        "initialize x := pure ()\n",
        "builtin_initialize x := pure ()\n",
        "partial def f (n : Nat) : Nat := f n\n",
        "opaque f : Nat\n",
        "run_cmd pure ()\n",
        "run_meta pure ()\n",
        "#guard (1 + 1 == 2)\n",
        "#guard_msgs\n",
        "#exit\n",
        "#check Nat\n",
        "#synth Inhabited Nat\n",
        "#eval 1\n",
        "#eval! 1\n",
        "#reduce 1\n",
        "#print Nat\n",
        "macro x : term => x\n",
        "macro_rules | x => x\n",
        "elab x : term => x\n",
        "elab_rules | x => x\n",
        "syntax foo := term\n",
        "declare_syntax_cat _mc\n",
        "local syntax ident : _mc\n",
        "local instance : Inhabited Nat := ⟨0⟩\n",
        "theorem t : True := trivial\n",
    ]
    for idx, snip in enumerate(escape_snippets):
        try:
            ver.static_scan_lean(real_src + "\n" + snip)
        except ver.VerificationError:
            continue
        raise TestFailure(f"R12 Lean static scanner missed escape #{idx}: {snip!r}")

    # Unit-test _parse_lean_axiom_stdout
    good_lines = [
        f"'{oracle.LEAN_NAMESPACE}.{t}' depends on axioms: [propext, Quot.sound]"
        for t in oracle.LEAN_THEOREM_NAMES[:-1]
    ] + [
        "",
        f"'{oracle.LEAN_NAMESPACE}.{oracle.LEAN_THEOREM_NAMES[-1]}' does not depend on any axioms",
    ]
    good_stdout = "\n".join(good_lines) + "\n"
    parsed = ver._parse_lean_axiom_stdout(good_stdout)
    expect(len(parsed) == 18, "parsed 18 theorem axiom lines")
    expect(parsed[f"{oracle.LEAN_NAMESPACE}.{oracle.LEAN_THEOREM_NAMES[-1]}"] == [], "empty axiom list")

    expect_raises(ver._parse_lean_axiom_stdout, "\n".join(good_lines + ["warning: unused var"]))
    expect_raises(ver._parse_lean_axiom_stdout, "\n".join(good_lines[:-1]))
    expect_raises(ver._parse_lean_axiom_stdout, "\n".join(good_lines + ["garbage stdout"]))
    bad_ax = list(good_lines)
    bad_ax[0] = f"'{oracle.LEAN_NAMESPACE}.{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext, Classical.choice]"
    expect_raises(ver._parse_lean_axiom_stdout, "\n".join(bad_ax))
    bad_sorry = list(good_lines)
    bad_sorry[0] = f"'{oracle.LEAN_NAMESPACE}.{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [sorryAx]"
    expect_raises(ver._parse_lean_axiom_stdout, "\n".join(bad_sorry))

    # Single live/no-Lean companion verification (0 skips in BOTH environments!)
    res = ver.verify_lean_companion(ver.DEFAULT_LEAN_PATH, require_live=False)
    expect(res["static_scan_passed"] is True, "static scan must pass")
    expect(res["theorem_count"] == 18, "18 theorems")

    with tempfile.TemporaryDirectory(prefix="s99_lean_") as td:
        bad_lean = Path(td) / "bad.lean"
        bad_lean.write_text(real_src + "\n-- tampered\n", encoding="utf-8")
        os.chmod(str(bad_lean), 0o600)
        expect_raises(ver.verify_lean_companion, bad_lean, False)

    # _find_lean_bin BoolOp killers (non-exec file, exec dir) + M107/M109 killers (valid stdout on rc=1 and stderr!=empty!)
    orig_which = shutil.which
    orig_home = os.environ.get("HOME")
    orig_req = os.environ.get("ALETHEIA_REQUIRE_LEAN")
    try:
        shutil.which = lambda _cmd: None  # type: ignore[assignment]
        os.environ.pop("HOME", None)
        expect(ver._find_lean_bin() is None, "no HOME & no PATH => None")
        os.environ["ALETHEIA_REQUIRE_LEAN"] = "0"
        nl = ver.verify_lean_companion(ver.DEFAULT_LEAN_PATH, require_live=False)
        expect(nl["live_lean_executed"] is False, "no-Lean graceful static return")
        expect_raises(ver.verify_lean_companion, ver.DEFAULT_LEAN_PATH, True)
        os.environ["ALETHEIA_REQUIRE_LEAN"] = "1"
        expect_raises(ver.verify_lean_companion, ver.DEFAULT_LEAN_PATH, False)

        with tempfile.TemporaryDirectory(prefix="s99_home_") as hd:
            # 1. Executable directory named .local/bin/lean must NOT be returned (kills is_file() deletion!)
            fake_dir = Path(hd) / ".local" / "bin" / "lean"
            fake_dir.mkdir(parents=True, mode=0o700)
            os.environ["HOME"] = hd
            expect(ver._find_lean_bin() is None, "directory named lean must not match")
            fake_dir.rmdir()

            # 2. Non-executable regular file must NOT be returned (kills os.access(X_OK) deletion!)
            fake_lean = fake_dir
            fake_lean.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(str(fake_lean), 0o600)
            expect(ver._find_lean_bin() is None, "non-executable lean must not match")

            # 3. Bad --version rc=1 with "4.36.0" & rc=0 with "4.99.0" (valid --stdin kills M098 + ALL L485 BoolOp mutants!)
            stdout_file = Path(hd) / "valid_axioms.txt"
            stdout_file.write_text(good_stdout, encoding="utf-8")
            fake_lean.write_text(
                f"#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'Lean (version 4.36.0, Release)'; exit 1; fi\ncat '{stdout_file}'\nexit 0\n",
                encoding="utf-8",
            )
            os.chmod(str(fake_lean), 0o700)
            expect(ver._find_lean_bin() == str(fake_lean), "HOME .local/bin/lean found")
            expect_raises(ver.verify_lean_companion, ver.DEFAULT_LEAN_PATH, True)

            fake_lean.write_text(
                f"#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'Lean (version 4.99.0, Release)'; exit 0; fi\ncat '{stdout_file}'\nexit 0\n",
                encoding="utf-8",
            )
            expect_raises(ver.verify_lean_companion, ver.DEFAULT_LEAN_PATH, True)

            # 4. Executable fake lean with valid --version + valid 18-theorem axiom stdout but exiting 1 on --stdin
            fake_lean.write_text(
                f"#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'Lean (version 4.36.0, Release)'; exit 0; fi\ncat '{stdout_file}'\nexit 1\n",
                encoding="utf-8",
            )
            expect_raises(ver.verify_lean_companion, ver.DEFAULT_LEAN_PATH, True)

            # 5. Executable fake lean with valid --version + valid axiom stdout + exit 0 + non-empty stderr
            fake_lean.write_text(
                f"#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'Lean (version 4.36.0, Release)'; exit 0; fi\ncat '{stdout_file}'\necho warn >&2\nexit 0\n",
                encoding="utf-8",
            )
            expect_raises(ver.verify_lean_companion, ver.DEFAULT_LEAN_PATH, True)

            # 6. S99-VER-02 strict allowlist env scrub proof: poison ALL Lean/Elan/LD/DYLD vars & verify ALL are scrubbed!
            poison_vars = (
                "LEAN_PATH",
                "LEAN_OPTS",
                "LEAN_SRC_PATH",
                "LEAN_SYSROOT",
                "LEAN_CC",
                "ELAN_TOOLCHAIN",
                "ELAN_HOME",
                "LD_PRELOAD",
                "LD_LIBRARY_PATH",
                "DYLD_INSERT_LIBRARIES",
            )
            scrub_check_script = (
                "#!/bin/sh\n"
                "for v in LEAN_PATH LEAN_OPTS LEAN_SRC_PATH LEAN_SYSROOT LEAN_CC ELAN_TOOLCHAIN ELAN_HOME LD_PRELOAD LD_LIBRARY_PATH DYLD_INSERT_LIBRARIES; do\n"
                "  eval \"val=\\$$v\"\n"
                "  if [ -n \"$val\" ]; then echo \"LEAK:$v\" >&2; exit 99; fi\n"
                "done\n"
                "if [ \"$1\" = \"--version\" ]; then echo 'Lean (version 4.36.0, Release)'; exit 0; fi\n"
                f"cat '{stdout_file}'\n"
                "exit 0\n"
            )
            fake_lean.write_text(scrub_check_script, encoding="utf-8")
            saved_poison = {k: os.environ.get(k) for k in poison_vars}
            try:
                for k in poison_vars:
                    os.environ[k] = "/poisoned/evil"
                scrub_res = ver.verify_lean_companion(ver.DEFAULT_LEAN_PATH, require_live=True)
                expect(scrub_res["live_lean_executed"] is True, "env-scrubbed live lean must succeed")
                expect(scrub_res["theorem_count"] == 18, "env-scrubbed live lean 18 thms")
            finally:
                for k, old_v in saved_poison.items():
                    if old_v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = old_v
    finally:
        shutil.which = orig_which
        if orig_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = orig_home
        if orig_req is None:
            os.environ.pop("ALETHEIA_REQUIRE_LEAN", None)
        else:
            os.environ["ALETHEIA_REQUIRE_LEAN"] = orig_req


def test_05_upstream_pins_and_cli_entry_points() -> None:
    with tempfile.TemporaryDirectory(prefix="s99_up_") as td:
        root = Path(td)
        expect_raises(ver.verify_upstream_pins, root)
        for info in oracle.UPSTREAM_EXPEDITION_CERTS.values():
            p = root / info["rel_path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"{}\n")
            os.chmod(str(p), 0o600)
        expect_raises(ver.verify_upstream_pins, root)

    exp_root = TRACK_DIR.parent
    if (exp_root / oracle.UPSTREAM_EXPEDITION_CERTS["S51"]["rel_path"]).is_file():
        matched = ver.verify_upstream_pins(exp_root)
        expect(len(matched) == 7, "all 7 upstream expedition certs matched")

    orig_out, orig_err = sys.stdout, sys.stderr
    orig_which = shutil.which
    orig_home = os.environ.get("HOME")
    try:
        shutil.which = lambda _cmd: None  # type: ignore[assignment]
        os.environ.pop("HOME", None)
        buf = io.StringIO()
        sys.stdout = buf
        sys.stderr = io.StringIO()
        expect(ver.main(["--standalone"]) == 0, "--standalone rc 0")
        expect(json.loads(buf.getvalue()) == oracle.build_certificate(), "--standalone matches oracle")

        with tempfile.TemporaryDirectory(prefix="s99_cli_") as td:
            cpath = Path(td) / "cli_cert.json"
            sys.stdout = io.StringIO()
            expect(ver.main(["--write", str(cpath)]) == 0, "--write rc 0")
            sys.stdout = io.StringIO()
            expect(ver.main(["--check", str(cpath)]) == 0, "--check rc 0")
            sys.stdout = io.StringIO()
            expect(ver.main(["--check", "--cert", str(cpath)]) == 0, "--check --cert rc 0")
            sys.stdout = io.StringIO()
            expect(ver.main([]) == 0, "default zero-arg check rc 0")
            sys.stderr = io.StringIO()
            expect(ver.main(["--check", str(Path(td) / "missing.json")]) == 1, "--check missing rc 1")
            # S99-VER-01 CLI --check test on re-signed 5000-digit rational string: clean rc=1, zero Traceback!
            big_q_path = Path(td) / "big_q_5000.json"
            big_cert = oracle.build_certificate()
            big_cert["payload"]["pillar_1_optifab14_defects_and_repairs"]["defect_14_1_outage_constant"]["double_subtracted_const_kw_q"] = "9" * 5000
            big_cert = _resign(big_cert)
            ver._write_json_atomic_0600(big_q_path, big_cert)
            err_buf = io.StringIO()
            sys.stderr = err_buf
            expect(ver.main(["--check", str(big_q_path)]) == 1, "--check 5000-digit rational must fail cleanly rc=1")
            expect("Traceback" not in err_buf.getvalue() and "rational digits exceed" in err_buf.getvalue(), "clean VerificationError on CLI 5000-digit rational")
            sys.stderr = io.StringIO()
            expect(ver.main(["--verify-lean"]) == 1, "--verify-lean without lean rc 1")
            sys.stderr = io.StringIO()
            expect(ver.main(["--verify-upstream", td]) == 1, "--verify-upstream missing rc 1")
    finally:
        sys.stdout, sys.stderr = orig_out, orig_err
        shutil.which = orig_which
        if orig_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = orig_home


def test_06_oracle_domain_invariants() -> None:
    p, sc, g0 = oracle.OPTIFAB_PLANT, oracle.OPTIFAB_SCENARIO, oracle.START_GENOME
    expect(oracle.ppm(10, 0) == oracle.MAX_PPM, "ppm den<=0")

    # Kill oracle floor_margin guard & boundary: cg<=0, floor==0, and both negative!
    expect(oracle.floor_margin(p, dict(g0, capture_ppm=500_000)) == oracle.MAX_PPM, "cg<=0 returns MAX_PPM")
    expect(oracle.floor_margin(p, dict(g0, floor_kw=0)) == oracle.MAX_PPM, "floor==0 returns MAX_PPM")
    expect(oracle.floor_margin(p, dict(g0, capture_ppm=500_000, floor_kw=-10)) == oracle.MAX_PPM, "both neg returns MAX_PPM")

    # Kill oracle gate_v033_sym & gate_asymmetric_recovery BoolOps (L641, L713)!
    expect(oracle.gate_v033_sym([1], [1], 100, 1, 0)[0] == "cost", "sym gate cost<=0")
    expect(oracle.gate_v033_sym([1], [1], 100, 0, 1)[0] == "budget", "sym gate budget<cost")
    expect(oracle.gate_v033_sym([1], [1, 2], 100, 1, 1)[0] == "shape", "sym gate len mismatch")
    expect(oracle.gate_v033_sym([], [], 100, 1, 1)[0] == "shape", "sym gate empty")
    expect(oracle.gate_asymmetric_recovery([1], [1], 100, 1, 0)[0] == "cost", "asym cost<=0")
    expect(oracle.gate_asymmetric_recovery([1], [1], 100, 0, 1)[0] == "budget", "asym budget")
    expect(oracle.gate_asymmetric_recovery([1], [1, 2], 100, 1, 1)[0] == "shape", "asym len mismatch")
    expect(oracle.gate_asymmetric_recovery([], [], 100, 1, 1)[0] == "shape", "asym empty")
    expect(oracle.gate_asymmetric_recovery([900_000], [1_050_000], 1_000_000, 1, 1)[0] == "pos_distance", "asym pos_distance")
    expect(oracle.gate_asymmetric_recovery([1_050_000], [1_060_000], 1_000_000, 1, 1)[0] == "recovery_no_descent", "asym no descent")
    expect(oracle.gate_asymmetric_recovery([1_050_000, 500_000], [1_020_000, 1_010_000], 1_000_000, 1, 1)[0] == "recovery_regression", "asym regression")

    # Kill oracle accepts_lex_repaired BoolOp (L678): strictly higher obj_c > obj_b with LOWER headroom MUST admit!
    g_better_obj = dict(g0, floor_kw=595)
    expect(oracle.objective_v031_repaired(p, sc, g_better_obj) > oracle.objective_v031_repaired(p, sc, g0), "floor 595 raises obj")
    expect(oracle.accepts_lex_repaired(p, sc, oracle.LIMIT_PPM, g0, g_better_obj, 64)[0] is True, "lex admits higher obj despite smaller headroom")

    expect(oracle.accepts_v033(p, sc, oracle.LIMIT_PPM, g0, g0, 64)[1] == "same", "v33 same")
    expect(oracle.accepts_v033(p, sc, oracle.LIMIT_PPM, g0, dict(g0, pcm_kwh=10), 64)[1] == "bounds", "v33 bounds")
    expect(oracle.accepts_v033(p, sc, oracle.LIMIT_PPM, g0, dict(g0, pcm_kwh=5_000), 64)[1] == "distance", "v33 distance")
    expect(oracle.accepts_v033(p, sc, oracle.LIMIT_PPM, g0, dict(g0, floor_kw=610), 64)[1] == "worse", "v33 worse")
    expect(oracle.accepts_lex_repaired(p, sc, oracle.LIMIT_PPM, g0, dict(g0, pcm_kwh=10), 64)[1] == "bounds", "lex bounds")
    expect(oracle.accepts_lex_repaired(p, sc, oracle.LIMIT_PPM, g0, dict(g0, pcm_kwh=5_000), 64)[1] == "distance", "lex distance")
    expect(oracle.accepts_lex_repaired(p, sc, oracle.LIMIT_PPM, g0, dict(g0, floor_kw=610), 64)[1] == "worse", "lex worse")
    expect(oracle.accepts_lex_repaired(p, sc, oracle.LIMIT_PPM, g0, dict(g0, pcm_kwh=2_450), 64)[1] == "tie_no_headroom_gain", "lex tie decay")

    # Kill oracle mat_inv_det_q singular matrix guard (M002) & exact contract frame boundaries (M017/M021/M024/M026)
    try:
        oracle.mat_inv_det_q([[Fraction(0), Fraction(0)], [Fraction(0), Fraction(0)]])
    except ValueError:
        pass
    else:
        raise TestFailure("singular matrix must raise ValueError")
    lf_b = Fraction(1, 2)
    rc_b = Fraction(41, 1)
    bc_b = Fraction(325, 171)
    expect(
        oracle.evaluate_contract_frame(
            Fraction(1, 1), Fraction(1, 1), lf_b, rc_b, bc_b, True, lf_b, rc_b, bc_b
        )
        == [],
        "exact boundary frame must be admitted with zero violations",
    )

    # Kill ALL 18 clauses of oracle.well_formed_plant_check (L685)!
    wf_bad_cases: list[tuple[dict[str, Any], dict[str, int], int, dict[str, int]]] = [
        ({**p, "p_it_w": 0}, sc, oracle.LIMIT_PPM, g0),
        ({**p, "cop_ppm": 0}, sc, oracle.LIMIT_PPM, g0),
        ({**p, "ua_roof_mw_k": -1}, sc, oracle.LIMIT_PPM, g0),
        ({**p, "wall_area_m2": -1}, sc, oracle.LIMIT_PPM, g0),
        ({**p, "dt_mk": -1}, sc, oracle.LIMIT_PPM, g0),
        ({**p, "other_w": -1}, sc, oracle.LIMIT_PPM, g0),
        ({**p, "loop_cop_milli": 0}, sc, oracle.LIMIT_PPM, g0),
        (p, {**sc, "outage_min": 0}, oracle.LIMIT_PPM, g0),
        (p, {**sc, "outages_per_year": -1}, oracle.LIMIT_PPM, g0),
        (p, {**sc, "low_demand_fraction_ppm": -1}, oracle.LIMIT_PPM, g0),
        (p, {**sc, "low_demand_fraction_ppm": oracle.LIMIT_PPM + 1}, oracle.LIMIT_PPM, g0),
        (p, {**sc, "low_demand_hours": -1}, oracle.LIMIT_PPM, g0),
        (p, {**sc, "low_demand_hours": sc["hours_per_year"] + 1}, oracle.LIMIT_PPM, g0),
        (p, {**sc, "hours_per_year": 0, "low_demand_hours": 0}, oracle.LIMIT_PPM, g0),
        (p, sc, oracle.LIMIT_PPM + 1, g0),
        (p, sc, oracle.LIMIT_PPM, {**g0, "pcm_kwh": 0}),
        (p, sc, oracle.LIMIT_PPM, {**g0, "capture_ppm": 0}),
        (p, sc, oracle.LIMIT_PPM, {**g0, "capture_ppm": oracle.LIMIT_PPM + 1}),
        (p, sc, oracle.LIMIT_PPM, {**g0, "wall_u_mw": -1}),
        (p, sc, oracle.LIMIT_PPM, {**g0, "floor_kw": 0}),
        (p, sc, oracle.LIMIT_PPM, {**g0, "shed_ppm": -1}),
        (p, sc, oracle.LIMIT_PPM, {**g0, "shed_ppm": oracle.LIMIT_PPM + 1}),
    ]
    for idx, (bp, bsc, blim, bg) in enumerate(wf_bad_cases):
        expect(oracle.well_formed_plant_check(bp, bsc, blim, bg) is False, f"wf_bad_case #{idx} must fail")


def run_all() -> None:
    tests = (
        test_01_baseline_and_field_complete_sec_fr0_fr1,
        test_02_strict_rational_and_tree_parsers,
        test_03_zone_b_filesystem_and_atomic_write,
        test_04_r11_lean_static_and_live_gate,
        test_05_upstream_pins_and_cli_entry_points,
        test_06_oracle_domain_invariants,
    )
    for fn in tests:
        fn()
    print(f"PASS_R5 tests={len(tests)}/{len(tests)} skips=0")


if __name__ == "__main__":
    run_all()
