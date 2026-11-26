#!/usr/bin/env python3
"""
Track S84: Hardened Zone-B Verifier, R10+ Live Lean 4.36.0 Auditor, & CLI.

Verifies:
  1. Pure-Z/Q Track S84 K_16 Higher-Order Mesh certificate envelope (atomic dir_fd +
     O_NONBLOCK + O_NOFOLLOW + st_nlink==1 + $PWD symlink defense; strict JSON loader
     with pre-parse ASCII int digit cap, zero floats/NaN/Inf/duplicates/CRLF; FR1 full
     oracle replay, FR0 independent 4-pillar audit, raising `secondary_audit_payload`).
  2. Live Lean 4.36.0 kernel execution over `--stdin` (zero read-to-compile TOCTOU),
     R10+ comment-only static scanner with strict quote/guillemet ban, pinned SHA-256
     check on `HigherOrderEpistemicMesh.lean` (18/18 universal theorems, strictly
     within allowed axioms `{"propext", "Quot.sound"}`, zero `Classical.choice`, zero
     banned axioms).
  3. Optional atomic dir_fd on-disk SHA-256 lock of all 16 pinned upstream certificates
     when `--expedition-root <dir>` is supplied (zero hardcoded host paths).
  4. Durable atomic `0o600` dir_fd certificate emission via `--write <path>`.
"""

from __future__ import annotations

import errno
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from s84_higher_order_k16_oracle import (
    EXPECTED_LEAN_SHA256,
    EXPECTED_LEAN_THEOREMS,
    EXPECTED_LEAN_TOOLCHAIN,
    MAX_INT_BITS,
    MAX_JSON_DEPTH,
    MESH_NODES,
    OPERATOR_GLYPHS,
    PATHWAY_WEIGHTS,
    SCHEMA_VERSION,
    TRACK_ID,
    build_certificate_envelope,
    canonical_json_bytes,
)

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_INT_DIGITS = 320
ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

REQUIRED_TOP_KEYS = frozenset(
    {"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"}
)
REQUIRED_PAYLOAD_KEYS = frozenset(
    {
        "all_pillars_verified",
        "lean_source_sha256",
        "lean_theorem_count",
        "lean_toolchain",
        "novelty_tier",
        "oracle_class",
        "pillar_1_order1_k16_and_k8_lift",
        "pillar_2_order2_triangles_hodge_disjoint",
        "pillar_3_order3_tetrahedra_bianchi",
        "pillar_4_order4_5cells_metamesh_silocut_firewall",
        "pinned_nodes",
        "track_id",
    }
)
HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_ASCII_INT_RE = re.compile(r"\A-?[0-9]+\Z")

_LEAN_QUOTE_OR_GUILLEMET_RE = re.compile(r'["\'«»]')
_LEAN_FORBIDDEN_RE = re.compile(
    r"\b(?:sorry|admit|axiom|unsafe|native_decide|sorryAx|"
    r"ofReduceBool|ofReduceNat|trustCompiler|mkSorry|"
    r"elab|elab_rules|macro|macro_rules|syntax|declare_syntax_cat|"
    r"notation|prefix|infix|infixl|infixr|postfix|"
    r"initialize|builtin_initialize|opaque|dbg_trace|throwError|"
    r"run_cmd|run_meta|interpolatedStr)\b"
)
_LEAN_PARTIAL_RE = re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev|theorem)\b")
_LEAN_DECIDE_NATIVE_RE = re.compile(
    r"(?<!\w)\+\s*native\b|\bnative\s*:=(?!\s*(?:Bool\.)?false\s*(?:[),}]|\Z))|"
    r"\bDecide(?:Config|\.Config)\b|\bdecide\s*\(\s*(?:config|revert)\b"
)
_LEAN_SKIP_TC_RE = re.compile(
    r"\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b"
)
_LEAN_EVAL_SPOOF_RE = re.compile(
    r"#(?:eval!?|reduce|exit)\b|"
    r"#print\s+(?!axioms\s+(?!example\b|def\b|theorem\b|lemma\b)[A-Za-z0-9_.]+\s*(?:\n|\Z))"
)
_LEAN_ATTR_ESCAPE_RE = re.compile(
    r"(?:@\[|\battribute\s*\[)[^\]]*\b(?:extern|implemented_by|export|csimp)\b"
)
_LEAN_IMPORT_RE = re.compile(
    r"(?:^|\n)\s*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)"
)
_ZERO_AXIOM_LINE_RE = re.compile(
    r"\A'([A-Za-z0-9_.]+)' does not depend on any axioms\Z"
)
_DEPENDS_AXIOM_LINE_RE = re.compile(
    r"\A'([A-Za-z0-9_.]+)' depends on axioms: \[([A-Za-z0-9_., ]+)\]\Z"
)


def require_ok(cond: bool, msg: str) -> None:
    """Hardened non-assert verification guard (immune to python3 -O)."""
    if not cond:
        raise ValueError(msg)


def _is_sha256_hex(val: Any) -> bool:
    return type(val) is str and bool(HEX64_RE.match(val))


def _req_dict(val: Any, code: str) -> dict[str, Any]:
    require_ok(type(val) is dict, code)
    return val


def _req_int(val: Any, code: str) -> int:
    require_ok(type(val) is int, code)
    return val


def _check_json_depth_and_types(root: Any) -> None:
    """Iterative exact-type JSON tree validator (blocks subclasses, huge ints, surrogates, cycles, DoS)."""
    active: set[int] = set()
    frames: list[tuple[Any, int, bool]] = [(root, 0, False)]
    while frames:
        obj, depth, is_exit = frames.pop()
        if is_exit:
            active.discard(obj)
            continue
        require_ok(depth <= MAX_JSON_DEPTH, "JSON_MAX_DEPTH_EXCEEDED")
        t = type(obj)
        if obj is None or t is bool:
            continue
        if t is int:
            require_ok(obj.bit_length() <= MAX_INT_BITS, "JSON_INT_TOO_LARGE")
            continue
        if t is str:
            require_ok("\x00" not in obj, "JSON_NUL_IN_STRING")
            for ch in obj:
                code = ord(ch)
                require_ok(not (0xD800 <= code <= 0xDFFF), "JSON_LONE_SURROGATE")
            continue
        if t is list:
            oid = id(obj)
            require_ok(oid not in active, "JSON_CYCLE")
            active.add(oid)
            frames.append((oid, depth, True))
            for item in obj:
                frames.append((item, depth + 1, False))
            continue
        if t is dict:
            oid = id(obj)
            require_ok(oid not in active, "JSON_CYCLE")
            active.add(oid)
            frames.append((oid, depth, True))
            for k, v in obj.items():
                require_ok(type(k) is str, "JSON_NON_STRING_KEY")
                frames.append((k, depth + 1, False))
                frames.append((v, depth + 1, False))
            continue
        raise ValueError(f"JSON_DISALLOWED_TYPE:{t.__name__}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"JSON_DUPLICATE_KEY:{k}")
        out[k] = v
    return out


def _parse_strict_int(token: str) -> int:
    """Pre-parse ASCII digit cap blocking Python's raw 4,300-digit ValueError crash."""
    require_ok(bool(_ASCII_INT_RE.match(token)), "JSON_INVALID_INT_TOKEN")
    digits = token[1:] if token.startswith("-") else token
    require_ok(len(digits) <= MAX_INT_DIGITS, "JSON_INT_TOO_LARGE")
    return int(token)


def _reject_float(token: str) -> Any:
    raise ValueError(f"JSON_FLOAT_FORBIDDEN:{token}")


def _reject_constant(token: str) -> Any:
    raise ValueError(f"JSON_CONSTANT_FORBIDDEN:{token}")


def _validate_path_str(raw: str) -> Path:
    require_ok(type(raw) is str and len(raw) > 0, "EMPTY_PATH")
    require_ok("\x00" not in raw, "NUL_IN_PATH")
    return Path(raw)


def _is_symlink_at(dfd: int, name: str) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(name, dir_fd=dfd).st_mode)
    except OSError:
        return False


def _check_pwd_no_symlinks() -> None:
    """Fail closed if logical $PWD contains a symlink ancestor."""
    pwd = os.environ.get("PWD")
    if pwd is None:
        return
    if not os.path.isabs(pwd):
        return
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in Path(pwd).parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise ValueError("SYMLINK_IN_PATH") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
    finally:
        os.close(cur_fd)


def _open_parent_dir_fd(path: Path) -> tuple[int, str]:
    """Step down ancestor directories atomically via O_RDONLY|O_DIRECTORY|O_NOFOLLOW."""
    p_str = str(path)
    require_ok("\x00" not in p_str, "INVALID_PATH")
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    require_ok(len(parts) > 0, "INVALID_PATH")
    ancestors, leaf = parts[:-1], parts[-1]
    require_ok(leaf != "..", "INVALID_PATH")
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise ValueError("SYMLINK_IN_PATH") from exc
                raise ValueError(f"INVALID_PARENT_DIR:{exc.errno}") from exc
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, leaf
    except BaseException:
        os.close(cur_fd)
        raise


def _read_regular_file_bytes(path: Path, max_bytes: int) -> bytes:
    """Atomically read a regular, single-link, non-symlink, non-FIFO file via pinned dir_fd."""
    dfd, leaf = _open_parent_dir_fd(path)
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ValueError("SYMLINK_IN_PATH") from exc
            raise ValueError(f"OPEN_FAILED:{exc.errno}") from exc
        try:
            st = os.fstat(fd)
            require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE")
            require_ok(st.st_nlink == 1, "HARDLINK_FORBIDDEN")
            require_ok(st.st_size <= max_bytes, "FILE_TOO_LARGE")
            chunks: list[bytes] = []
            total = 0
            while True:
                buf = os.read(fd, 65536)
                if not buf:
                    break
                total += len(buf)
                require_ok(total <= max_bytes, "FILE_TOO_LARGE")
                chunks.append(buf)
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


def load_strict_json_file(path: Path) -> dict[str, Any]:
    """Read a regular single-link non-symlink canonical UTF-8 JSON object."""
    raw = _read_regular_file_bytes(path, MAX_JSON_BYTES)
    require_ok(b"\x00" not in raw, "NUL_BYTE_IN_JSON")
    require_ok(b"\r" not in raw, "CRLF_FORBIDDEN")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("INVALID_UTF8") from exc
    try:
        data = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_int=_parse_strict_int,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON_SYNTAX_ERROR:{exc.msg}") from exc
    except RecursionError as exc:
        raise ValueError("JSON_MAX_DEPTH_EXCEEDED") from exc
    require_ok(type(data) is dict, "JSON_ROOT_NOT_OBJECT")
    _check_json_depth_and_types(data)
    require_ok(raw == canonical_json_bytes(data), "NON_CANONICAL_JSON_BYTES")
    return data


def _require_writable_target_safe(dfd: int, leaf: str) -> None:
    try:
        st_l = os.lstat(leaf, dir_fd=dfd)
    except FileNotFoundError:
        return
    require_ok(not stat.S_ISLNK(st_l.st_mode), "SYMLINK_IN_PATH")
    require_ok(stat.S_ISREG(st_l.st_mode), "TARGET_NOT_REGULAR")
    require_ok(st_l.st_nlink == 1, "HARDLINK_FORBIDDEN")


def atomic_write_0600(target: Path, content: bytes) -> None:
    """Atomically write bytes to target with strict 0o600 permissions via pinned dir_fd."""
    dfd, leaf = _open_parent_dir_fd(target)
    try:
        _require_writable_target_safe(dfd, leaf)
        tmp_name = f".{leaf}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        fd = os.open(tmp_name, flags, 0o600, dir_fd=dfd)
        written_ok = False
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(content)
            offset = 0
            total = len(content)
            while offset < total:
                n = os.write(fd, view[offset:])
                if n <= 0:
                    raise OSError("SHORT_WRITE")
                offset += n
            os.fsync(fd)
            require_ok(os.fstat(fd).st_nlink == 1, "TMP_HARDLINK_DETECTED")
            written_ok = True
        finally:
            os.close(fd)
            if not written_ok:
                try:
                    os.unlink(tmp_name, dir_fd=dfd)
                except OSError:
                    pass
        try:
            _require_writable_target_safe(dfd, leaf)
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
        except BaseException:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
            raise
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _strip_lean_comments_only(source: str) -> tuple[str, list[str]]:
    """Strip ONLY Lean 4 line (`--`) and nested block (`/- ... -/`) comments."""
    out: list[str] = []
    errors: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        if source.startswith("--", i):
            nl = source.find("\n", i + 2)
            if nl == -1:
                break
            out.append("\n")
            i = nl + 1
            continue
        if source.startswith("/-", i):
            depth = 1
            i += 2
            while i < n:
                if source.startswith("/-", i):
                    depth += 1
                    i += 2
                elif source.startswith("-/", i):
                    depth -= 1
                    i += 2
                    if depth == 0:
                        break
                else:
                    if source[i] == "\n":
                        out.append("\n")
                    i += 1
            if depth != 0:
                errors.append("LEAN_UNTERMINATED_BLOCK_COMMENT")
            out.append(" ")
            continue
        out.append(source[i])
        i += 1
    return "".join(out), errors


def audit_lean_source_static(source: str) -> dict[str, Any]:
    """Static R10+ audit of Lean 4 source (comment-only strip + strict quote/guillemet ban)."""
    cleaned, findings = _strip_lean_comments_only(source)
    if _LEAN_QUOTE_OR_GUILLEMET_RE.search(cleaned):
        findings.append("LEAN_QUOTE_OR_GUILLEMET_FORBIDDEN")
    deguillemet = cleaned.replace("\u00ab", "").replace("\u00bb", "")
    if _LEAN_FORBIDDEN_RE.search(deguillemet):
        findings.append("LEAN_FORBIDDEN_KEYWORD")
    if _LEAN_PARTIAL_RE.search(deguillemet):
        findings.append("LEAN_PARTIAL_DECL")
    if _LEAN_DECIDE_NATIVE_RE.search(deguillemet):
        findings.append("LEAN_DECIDE_NATIVE")
    if _LEAN_SKIP_TC_RE.search(deguillemet):
        findings.append("LEAN_SKIP_KERNEL_TC")
    if _LEAN_EVAL_SPOOF_RE.search(deguillemet):
        findings.append("LEAN_EVAL_OR_PRINT_SPOOF")
    if _LEAN_ATTR_ESCAPE_RE.search(deguillemet):
        findings.append("LEAN_ATTR_TRUST_ESCAPE")
    imports = [m.group(1) for m in _LEAN_IMPORT_RE.finditer(deguillemet)]
    if imports:
        findings.append(f"LEAN_NON_ZERO_IMPORTS:{','.join(imports)}")
    return {"clean": len(findings) == 0, "findings": findings, "imports": imports}


def resolve_lean_binary() -> str:
    """Resolve executable `lean` binary (respects optional ALETHEIA_LEAN_BIN override)."""
    override = os.environ.get("ALETHEIA_LEAN_BIN")
    if override is not None:
        p = Path(override)
        require_ok(p.is_file() and os.access(str(p), os.X_OK), "LEAN_BINARY_UNAVAILABLE")
        return str(p)
    found = shutil.which("lean")
    require_ok(found is not None, "LEAN_BINARY_UNAVAILABLE")
    return str(found)


def verify_lean_proof(lean_path: Path, *, enforce_sha256: bool = True) -> dict[str, Any]:
    """Atomic dir_fd read, R10+ static scan, SHA-256 pin, and live Lean 4.36.0 `--stdin` check."""
    require_ok(type(enforce_sha256) is bool, "INVALID_ENFORCE_SHA256_FLAG")
    raw = _read_regular_file_bytes(lean_path, MAX_JSON_BYTES)
    lean_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("LEAN_INVALID_UTF8") from exc
    static = audit_lean_source_static(source)
    require_ok(static["clean"], f"LEAN_STATIC_AUDIT_FAILED:{','.join(static['findings'])}")
    if enforce_sha256:
        require_ok(hmac.compare_digest(lean_sha256, EXPECTED_LEAN_SHA256), "LEAN_SHA256_MISMATCH")

    lean_bin = resolve_lean_binary()
    proc = subprocess.run(
        [lean_bin, "--stdin"],
        input=source,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    require_ok(proc.returncode == 0, f"LEAN_COMPILE_FAILED:{proc.returncode}")
    require_ok(proc.stderr.strip() == "", "LEAN_NONEMPTY_STDERR")

    logical_lines: list[str] = []
    for raw_line in proc.stdout.splitlines():
        if not raw_line.strip():
            continue
        if raw_line[0] in (" ", "\t") and logical_lines:
            logical_lines[-1] = logical_lines[-1] + " " + raw_line.strip()
        else:
            logical_lines.append(raw_line.strip())

    seen: list[str] = []
    seen_set: set[str] = set()
    axioms_used: set[str] = set()
    zero_axiom_count = 0
    for line in logical_lines:
        m0 = _ZERO_AXIOM_LINE_RE.match(line)
        if m0 is not None:
            thm = m0.group(1)
            require_ok(thm not in seen_set, f"LEAN_DUPLICATE_THEOREM:{thm}")
            seen.append(thm)
            seen_set.add(thm)
            zero_axiom_count += 1
            continue
        m1 = _DEPENDS_AXIOM_LINE_RE.match(line)
        require_ok(m1 is not None, f"LEAN_UNEXPECTED_STDOUT_LINE:{line[:80]}")
        thm = m1.group(1)  # type: ignore[union-attr]
        require_ok(thm not in seen_set, f"LEAN_DUPLICATE_THEOREM:{thm}")
        axs = [tok.strip() for tok in m1.group(2).split(",")]  # type: ignore[union-attr]
        for ax in axs:
            require_ok(ax in ALLOWED_LEAN_AXIOMS, f"LEAN_FORBIDDEN_AXIOM:{ax}")
            axioms_used.add(ax)
        seen.append(thm)
        seen_set.add(thm)

    require_ok(tuple(seen) == EXPECTED_LEAN_THEOREMS, "LEAN_THEOREM_LIST_MISMATCH")
    return {
        "lean_file": lean_path.name,
        "lean_sha256": lean_sha256,
        "sha256_pinned": enforce_sha256,
        "static_clean": True,
        "theorems_verified": len(seen),
        "zero_axiom_theorems": zero_axiom_count,
        "axioms_used": sorted(axioms_used),
        "imports": [],
    }


def _audit_payload_pillars(p: dict[str, Any]) -> None:
    """Independent 4-pillar structural, strict-type, and algebraic invariant audit (zero oracle replay)."""
    require_ok(set(p.keys()) == REQUIRED_PAYLOAD_KEYS, "PAYLOAD_KEYS_MISMATCH")
    require_ok(p["track_id"] == TRACK_ID, "PAYLOAD_TRACK_MISMATCH")
    require_ok(p["oracle_class"] == "exact", "ORACLE_CLASS_MISMATCH")
    require_ok(p["novelty_tier"] == "N1", "NOVELTY_TIER_MISMATCH")
    require_ok(p["lean_toolchain"] == EXPECTED_LEAN_TOOLCHAIN, "LEAN_TOOLCHAIN_MISMATCH")
    require_ok(p["lean_source_sha256"] == EXPECTED_LEAN_SHA256, "PAYLOAD_LEAN_SHA_MISMATCH")
    require_ok(_req_int(p["lean_theorem_count"], "LEAN_COUNT_INVALID") == len(EXPECTED_LEAN_THEOREMS), "LEAN_COUNT_MISMATCH")
    require_ok(p["all_pillars_verified"] is True, "PILLARS_NOT_VERIFIED")

    # Pinned 16 nodes
    nodes = p["pinned_nodes"]
    require_ok(type(nodes) is list, "NODES_NOT_LIST")
    require_ok(len(nodes) == 16, "NODES_LEN_MISMATCH")
    for idx, nd in enumerate(nodes):
        nd_d = _req_dict(nd, "NODE_NOT_DICT")
        require_ok(nd_d.get("id") == f"n{idx:02d}", "NODE_ID_MISMATCH")
        require_ok(_is_sha256_hex(nd_d.get("sha256")), "NODE_SHA_INVALID")
        require_ok(_req_int(nd_d.get("bytes"), "NODE_BYTES_INVALID") > 0, "NODE_BYTES_NONPOS")

    # Pillar 1: Order 1 (120 edges, Laplacian inertia, Foster=15, K_8 lift)
    p1 = _req_dict(p["pillar_1_order1_k16_and_k8_lift"], "P1_NOT_DICT")
    require_ok(p1.get("all_verified") is True, "P1_NOT_VERIFIED")
    require_ok(_req_int(p1.get("node_count"), "P1_INT_INVALID") == 16, "P1_NODE_COUNT_MISMATCH")
    require_ok(_req_int(p1.get("edge_count"), "P1_INT_INVALID") == 120, "P1_EDGE_COUNT_MISMATCH")
    require_ok(p1.get("foster_sum_q") == "15", "P1_FOSTER_MISMATCH")
    require_ok(p1.get("all_120_pairs_strictly_compounded") is True, "P1_COMPOUNDING_FAILED")
    iner1 = p1.get("laplacian_inertia")
    require_ok(type(iner1) is list, "P1_INERTIA_INVALID")
    require_ok(len(iner1) == 3, "P1_INERTIA_INVALID")
    require_ok(
        [_req_int(x, "P1_INT_INVALID") for x in iner1] == [15, 0, 1],
        "P1_INERTIA_MISMATCH",
    )
    edges = p1.get("canonical_edges")
    require_ok(type(edges) is list, "P1_EDGES_NOT_LIST")
    require_ok(len(edges) == 120, "P1_EDGES_LEN_MISMATCH")
    w_sum = 0
    for ed in edges:
        ed_d = _req_dict(ed, "P1_EDGE_NOT_DICT")
        cls = ed_d.get("pathway_class")
        require_ok(cls in PATHWAY_WEIGHTS, "P1_EDGE_CLASS_INVALID")
        ew = _req_int(ed_d.get("weight"), "P1_INT_INVALID")
        require_ok(ew == PATHWAY_WEIGHTS[cls], "P1_EDGE_WEIGHT_MISMATCH")
        require_ok(ed_d.get("operator_tag") in OPERATOR_GLYPHS, "P1_EDGE_OP_INVALID")
        w_sum += ew
    require_ok(_req_int(p1.get("total_edge_weight"), "P1_INT_INVALID") == w_sum, "P1_TOTAL_WEIGHT_MISMATCH")
    require_ok(_req_int(p1.get("max_compounding_direct_w"), "P1_INT_INVALID") >= 1, "P1_INT_INVALID")
    k8 = _req_dict(p1.get("wave4_k8_submesh_comparison"), "P1_K8_NOT_DICT")
    require_ok(_req_int(k8.get("k8_edge_count"), "P1_INT_INVALID") == 28, "P1_K8_EDGES_MISMATCH")
    require_ok(k8.get("all_28_wave4_pairs_strictly_amplified_by_k16") is True, "P1_K8_LIFT_FAILED")
    k8_in = k8.get("k8_schur_pushforward_inertia")
    require_ok(type(k8_in) is list, "P1_K8_INERTIA_INVALID")
    require_ok([_req_int(x, "P1_INT_INVALID") for x in k8_in] == [7, 0, 1], "P1_K8_INERTIA_MISMATCH")

    # Pillar 2: Order 2 (560 triangles, B_1 B_2 = 0, Hodge-1, disjoint transforms)
    p2 = _req_dict(p["pillar_2_order2_triangles_hodge_disjoint"], "P2_NOT_DICT")
    require_ok(p2.get("all_verified") is True, "P2_NOT_VERIFIED")
    tc = _req_dict(p2.get("triangle_counts"), "P2_TC_NOT_DICT")
    t_total = sum(_req_int(v, "P2_INT_INVALID") for v in tc.values())
    require_ok(t_total == 560, "P2_TRIANGLE_SUM_MISMATCH")
    h1 = _req_dict(p2.get("hodge_1_simplicial"), "P2_HODGE_NOT_DICT")
    require_ok(_req_int(h1.get("b1_b2_nonzero_entries"), "P2_INT_INVALID") == 0, "P2_B1B2_NONZERO")
    require_ok(h1.get("b1_b2_identically_zero") is True, "P2_B1B2_FLAG_FAILED")
    g_dim = _req_int(h1.get("gradient_dim"), "P2_INT_INVALID")
    c_dim = _req_int(h1.get("curl_dim"), "P2_INT_INVALID")
    hm_dim = _req_int(h1.get("harmonic_dim"), "P2_INT_INVALID")
    require_ok(g_dim + c_dim + hm_dim == 120, "P2_HODGE_DIM_MISMATCH")
    require_ok(hm_dim == 0, "P2_HARM_DIM_NONZERO")
    b1_in = h1.get("b1_b1t_inertia")
    require_ok(type(b1_in) is list, "P2_B1_INERTIA_INVALID")
    require_ok([_req_int(x, "P2_INT_INVALID") for x in b1_in] == [15, 0, 1], "P2_B1_INERTIA_MISMATCH")
    dj = _req_dict(p2.get("disjoint_edge_second_order_convergences"), "P2_DISJOINT_NOT_DICT")
    cur_t = dj.get("curated_transforms")
    require_ok(type(cur_t) is list, "P2_CURATED_NOT_LIST")
    require_ok(len(cur_t) == 8, "P2_CURATED_LEN_MISMATCH")

    # Pillar 3: Order 3 (1,820 tetrahedra, Z_2 Bianchi = 0, K_4 exact locks & paired repair)
    p3 = _req_dict(p["pillar_3_order3_tetrahedra_bianchi"], "P3_NOT_DICT")
    require_ok(p3.get("all_verified") is True, "P3_NOT_VERIFIED")
    require_ok(_req_int(p3.get("z2_bianchi_nonzero_count"), "P3_INT_INVALID") == 0, "P3_BIANCHI_NONZERO")
    require_ok(p3.get("z2_bianchi_all_zero") is True, "P3_BIANCHI_FLAG_FAILED")
    tet_c = _req_dict(p3.get("tetrahedron_counts"), "P3_TET_NOT_DICT")
    require_ok(sum(_req_int(v, "P3_INT_INVALID") for v in tet_c.values()) == 1820, "P3_TET_SUM_MISMATCH")
    require_ok(_req_int(p3.get("k4_exact_lock_count"), "P3_INT_INVALID") == tet_c.get("K4_EXACT_LOCK"), "P3_K4_LOCK_MISMATCH")

    # Pillar 4: Order 4 (4,368 5-cells, M_4 meta-mesh, silo-cut exponential law, Law-3 firewall)
    p4 = _req_dict(p["pillar_4_order4_5cells_metamesh_silocut_firewall"], "P4_NOT_DICT")
    require_ok(p4.get("all_verified") is True, "P4_NOT_VERIFIED")
    cc = _req_dict(p4.get("five_cell_counts"), "P4_CC_NOT_DICT")
    require_ok(sum(_req_int(v, "P4_INT_INVALID") for v in cc.values()) == 4368, "P4_5CELL_SUM_MISMATCH")
    hist = _req_dict(p4.get("five_cell_frustrated_face_histogram"), "P4_HIST_NOT_DICT")
    require_ok(sum(_req_int(v, "P4_INT_INVALID") for v in hist.values()) == 4368, "P4_HIST_SUM_MISMATCH")

    m4 = _req_dict(p4.get("fourth_order_meta_mesh_m4"), "P4_M4_NOT_DICT")
    require_ok(m4.get("quotient_identity_pt_l0_p_exact") is True, "P4_M4_QUOT_FAILED")
    require_ok(m4.get("foster_sum_q") == "3", "P4_M4_FOSTER_MISMATCH")
    require_ok(m4.get("all_6_meta_pairs_strictly_compounded") is True, "P4_M4_COMP_FAILED")
    m4_in = m4.get("laplacian_inertia")
    require_ok(type(m4_in) is list, "P4_M4_INERTIA_INVALID")
    require_ok([_req_int(x, "P4_INT_INVALID") for x in m4_in] == [3, 0, 1], "P4_M4_INERTIA_MISMATCH")
    cls_l = m4.get("clusters")
    require_ok(type(cls_l) is list, "P4_M4_CLUSTERS_NOT_LIST")
    require_ok(len(cls_l) == 4, "P4_M4_CLUSTERS_LEN_MISMATCH")
    for cl_row in cls_l:
        cld = _req_dict(cl_row, "P4_M4_CLUSTER_NOT_DICT")
        _req_int(cld.get("internal_commute_edges"), "P4_INT_INVALID")
        _req_int(cld.get("internal_obstruction_edges"), "P4_INT_INVALID")

    silo = _req_dict(p4.get("k_simplex_silo_cut_law_k16"), "P4_SILO_NOT_DICT")
    ords = silo.get("orders")
    require_ok(type(ords) is list, "P4_SILO_ORDERS_NOT_LIST")
    require_ok(len(ords) == 4, "P4_SILO_LEN_MISMATCH")
    expected_destroyed = (64, 448, 1680, 4256)
    for idx, (row, exp_d) in enumerate(zip(ords, expected_destroyed), start=1):
        rd = _req_dict(row, "P4_SILO_ROW_NOT_DICT")
        require_ok(_req_int(rd.get("order"), "P4_INT_INVALID") == idx, "P4_SILO_ORDER_MISMATCH")
        require_ok(_req_int(rd.get("destroyed_8_8"), "P4_INT_INVALID") == exp_d, "P4_SILO_DESTROYED_MISMATCH")
        require_ok(rd.get("strictly_below_exponential_ceiling") is True, "P4_SILO_CEIL_FAILED")

    fw = _req_dict(p4.get("law3_contagion_firewall_k16_to_k15"), "P4_FW_NOT_DICT")
    require_ok(_req_int(fw.get("gated_corrupting_flux"), "P4_INT_INVALID") == 0, "P4_FW_GATED_FLUX_NONZERO")
    require_ok(_req_int(fw.get("gated_interior_nodes_corrupted"), "P4_INT_INVALID") == 0, "P4_FW_GATED_INT_NONZERO")
    require_ok(fw.get("ungated_all_14_interior_corrupted") is True, "P4_FW_UNGATED_FAILED")
    require_ok(_req_int(fw.get("k15_surviving_five_cells"), "P4_INT_INVALID") == 3003, "P4_FW_K15_MISMATCH")
    require_ok(fw.get("k15_all_105_pairs_compounded") is True, "P4_FW_K15_COMP_FAILED")


def secondary_audit_payload(
    cert_dict: Any,
    lean_report: Any = None,
) -> dict[str, Any]:
    """Raising independent secondary audit (envelope digests + all 4 higher-order pillars; zero replay)."""
    require_ok(type(cert_dict) is dict, "CERT_NOT_DICT")
    _check_json_depth_and_types(cert_dict)
    require_ok(set(cert_dict.keys()) == REQUIRED_TOP_KEYS, "CERT_TOP_KEYS_MISMATCH")
    require_ok(cert_dict["schema_version"] == SCHEMA_VERSION, "SCHEMA_VERSION_MISMATCH")
    require_ok(cert_dict["track_id"] == TRACK_ID, "TRACK_ID_MISMATCH")
    require_ok(_is_sha256_hex(cert_dict["payload_sha256"]), "INVALID_PAYLOAD_SHA256")
    require_ok(_is_sha256_hex(cert_dict["certificate_sha256"]), "INVALID_CERT_SHA256")
    require_ok(type(cert_dict["payload"]) is dict, "PAYLOAD_NOT_DICT")

    calc_payload_sha = hashlib.sha256(canonical_json_bytes(cert_dict["payload"])).hexdigest()
    require_ok(
        hmac.compare_digest(calc_payload_sha, cert_dict["payload_sha256"]),
        "PAYLOAD_SHA256_TAMPERED",
    )
    env_body = {
        "schema_version": cert_dict["schema_version"],
        "track_id": cert_dict["track_id"],
        "payload_sha256": cert_dict["payload_sha256"],
        "payload": cert_dict["payload"],
    }
    calc_cert_sha = hashlib.sha256(canonical_json_bytes(env_body)).hexdigest()
    require_ok(
        hmac.compare_digest(calc_cert_sha, cert_dict["certificate_sha256"]),
        "CERTIFICATE_SHA256_TAMPERED",
    )

    _audit_payload_pillars(cert_dict["payload"])

    if lean_report is not None:
        lr = _req_dict(lean_report, "LEAN_REPORT_NOT_DICT")
        require_ok(lr.get("static_clean") is True, "LEAN_REPORT_INCOMPLETE")
        n_ver = _req_int(lr.get("theorems_verified"), "LEAN_REPORT_INCOMPLETE")
        require_ok(n_ver == len(EXPECTED_LEAN_THEOREMS), "LEAN_REPORT_INCOMPLETE")

    return {
        "ok": True,
        "secondary_audit_passed": True,
        "certificate_sha256": cert_dict["certificate_sha256"],
        "payload_sha256": cert_dict["payload_sha256"],
        "lean_verified": lean_report is not None,
    }


def verify_certificate_dict(data: dict[str, Any], *, full_replay: bool = True) -> dict[str, Any]:
    """Verify envelope, independent 4-pillar audit (FR0), and optional pure-Z/Q oracle replay (FR1)."""
    require_ok(type(full_replay) is bool, "INVALID_FULL_REPLAY_FLAG")
    audit = secondary_audit_payload(data)
    if full_replay:
        recomputed = build_certificate_envelope()
        require_ok(
            hmac.compare_digest(data["payload_sha256"], recomputed["payload_sha256"]),
            "ORACLE_PAYLOAD_DRIFT",
        )
        require_ok(
            hmac.compare_digest(data["certificate_sha256"], recomputed["certificate_sha256"]),
            "ORACLE_CERT_DRIFT",
        )
    return {
        "schema_version": data["schema_version"],
        "track_id": data["track_id"],
        "payload_sha256": data["payload_sha256"],
        "certificate_sha256": data["certificate_sha256"],
        "all_pillars_verified": True,
        "full_replay": full_replay,
        "secondary_audit_passed": audit["secondary_audit_passed"],
    }


def verify_pinned_nodes_on_disk(expedition_root: Path) -> dict[str, Any]:
    """Verify exact on-disk SHA-256 digests and byte lengths of all 16 pinned K_16 certificates."""
    require_ok(expedition_root.is_dir(), "EXPEDITION_ROOT_INVALID")
    checked: dict[str, Any] = {}
    for nd in MESH_NODES:
        p = expedition_root / nd["relative_ref"]
        raw = _read_regular_file_bytes(p, MAX_JSON_BYTES)
        sha = hashlib.sha256(raw).hexdigest()
        require_ok(hmac.compare_digest(sha, nd["sha256"]), f"PINNED_NODE_SHA_MISMATCH:{nd['id']}")
        require_ok(len(raw) == nd["bytes"], f"PINNED_NODE_BYTES_MISMATCH:{nd['id']}")
        checked[nd["id"]] = {"sha256": sha, "bytes": len(raw), "match": True}
    return {"nodes_checked": len(checked), "all_matched": True, "details": checked}


def _parse_cli(argv: list[str]) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "write": None,
        "check": None,
        "lean": None,
        "expedition_root": None,
        "standalone": False,
        "json_out": False,
    }
    i = 0
    n = len(argv)
    while i < n:
        arg = argv[i]
        if arg in ("--write", "--check", "--lean", "--expedition-root"):
            key = arg[2:].replace("-", "_")
            require_ok(opts[key] is None, f"DUPLICATE_FLAG:{arg}")
            require_ok(i + 1 < n, f"MISSING_VALUE:{arg}")
            opts[key] = _validate_path_str(argv[i + 1])
            i += 2
        elif arg == "--standalone":
            require_ok(not opts["standalone"], "DUPLICATE_FLAG:--standalone")
            opts["standalone"] = True
            i += 1
        elif arg == "--json":
            require_ok(not opts["json_out"], "DUPLICATE_FLAG:--json")
            opts["json_out"] = True
            i += 1
        else:
            raise ValueError(f"UNKNOWN_ARG:{arg}")
    require_ok(not (opts["write"] is not None and opts["check"] is not None), "MUTUALLY_EXCLUSIVE_WRITE_CHECK")
    return opts


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        opts = _parse_cli(args)
        report: dict[str, Any] = {"ok": True, "track_id": TRACK_ID}

        if opts["write"] is not None:
            env = build_certificate_envelope()
            cert_summary = verify_certificate_dict(env)
            atomic_write_0600(opts["write"], canonical_json_bytes(env))
            report["certificate"] = cert_summary
            report["wrote"] = opts["write"].name
        elif opts["check"] is not None:
            loaded = load_strict_json_file(opts["check"])
            report["certificate"] = verify_certificate_dict(loaded)
        else:
            env = build_certificate_envelope()
            report["certificate"] = verify_certificate_dict(env)

        if opts["lean"] is not None:
            report["lean"] = verify_lean_proof(opts["lean"])
        elif not opts["standalone"] and opts["check"] is None and opts["write"] is None:
            default_lean = Path(__file__).resolve().parent / "HigherOrderEpistemicMesh.lean"
            if default_lean.exists():
                report["lean"] = verify_lean_proof(default_lean)

        if opts["expedition_root"] is not None:
            report["pinned_nodes"] = verify_pinned_nodes_on_disk(opts["expedition_root"])

        if opts["json_out"]:
            print(json.dumps(report, sort_keys=True, allow_nan=False))
        else:
            print(f"PASS {TRACK_ID} cert={report['certificate']['certificate_sha256']}")
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        err = {"ok": False, "error": str(exc)}
        if "--json" in args:
            print(json.dumps(err, sort_keys=True, allow_nan=False))
        else:
            print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
