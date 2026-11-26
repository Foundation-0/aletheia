#!/usr/bin/env python3
"""Zone-B Hardened Standalone CLI, Live Lean 4.36.0 & Secondary Auditor for Track S83.

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero .isdigit(),
zero mathematical RNG (secrets.token_hex used strictly for atomic temp filenames).
Full R10+ Lean 4 static & live hardening from day 1.
"""
from __future__ import annotations

import errno
from fractions import Fraction
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import threading
from typing import Any, Sequence

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s83_epistemic_mesh_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
_EXACT_PATH_TYPES = (Path, type(Path()))
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_DARWIN_SYSTEM_ROOT_ALIASES: tuple[tuple[str, str], ...] = (
    ("/var", "/private/var"),
    ("/tmp", "/private/tmp"),
    ("/etc", "/private/etc"),
)
_TEMP_NAME_LOCK = threading.Lock()
_TEMP_SEQ = 0
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset({
    "schema_version",
    "track_id",
    "oracle_class",
    "novelty_classification",
    "pinned_artifacts",
    "mesh_nodes",
    "pillar1_schur_compounding",
    "pillar2_triangle_holonomy",
    "pillar3_silo_cuts_and_firewall",
})
_PINNED_KEYS = frozenset({
    "lean_source",
    "lean_source_sha256",
    "lean_toolchain",
    "lean_toolchain_sha256",
    "lakefile_sha256",
    "lean_theorem_count",
    "lean_theorem_names",
})
_NODE_KEYS = frozenset({"id", "domain", "track", "cert_file", "cert_sha256", "anchor_invariant"})
_P1_KEYS = frozenset({
    "n_nodes",
    "n_undirected_pathways",
    "n_directed_pathways",
    "pathway_class_counts",
    "total_conductance_q",
    "laplacian_inertia",
    "foster_sum_q",
    "foster_identity_exact",
    "all_28_pairs_strictly_compounded",
    "min_compounding_gain_pair",
    "min_compounding_gain_q",
    "min_compounding_gain_dec4",
    "max_compounding_gain_pair",
    "max_compounding_gain_q",
    "max_compounding_gain_dec4",
    "resistance_triangle_inequalities_verified",
    "core4_schur_inertia",
    "core4_all_6_edges_strictly_boosted",
    "core4_edges",
    "pair_rows",
})
_P1_PAIR_KEYS = frozenset({
    "pair",
    "pathway_class",
    "operator_tag",
    "direct_w_q",
    "schur_boost_q",
    "g_eff_q",
    "r_eff_q",
    "compounding_gain_q",
    "compounding_gain_dec4",
})
_P1_CORE4_KEYS = frozenset({"pair", "direct_w_q", "core4_eff_w_q", "core4_boost_q", "core4_ratio_dec4"})
_P2_KEYS = frozenset({
    "n_triangles",
    "classification_counts",
    "odd_z2_holonomy_triangles",
    "even_z2_holonomy_triangles",
    "exact_transitive_closures",
    "frustrated_curvature_loops",
    "multi_wall_boundary_sectors",
    "tetrahedra_checked",
    "bianchi_coboundary_zero_all_70",
    "min_3node_schur_boost_q",
    "max_3node_schur_boost_q",
})
_P2_CLASS_KEYS = frozenset({
    "EXACT_TRANSITIVE_CLOSURE",
    "CONDITIONAL_COMPOUNDING_CLOSURE",
    "FRUSTRATED_CURVATURE_LOOP",
    "MULTI_WALL_BOUNDARY_SECTOR",
})
_P3_KEYS = frozenset({
    "total_nontrivial_bipartitions",
    "prop_e10_k8_balanced_min_pathways",
    "prop_e10_k8_balanced_min_triangles_destroyed",
    "split_summary",
    "contagion_firewall_case",
})
_P3_SPLIT_ROW_KEYS = frozenset({
    "partitions_counted",
    "pathways_severed",
    "pathways_severed_pct_dec2",
    "triangles_destroyed",
    "triangles_destroyed_pct_dec2",
    "min_weighted_cut_q",
    "max_weighted_cut_q",
})
_P3_FW_KEYS = frozenset({
    "compromised_node",
    "clean_anchor_node",
    "injected_error_q",
    "direct_edge_flux_q",
    "ungated_total_flux_q",
    "ungated_flux_amplification_q",
    "ungated_flux_amplification_dec4",
    "flux_equals_schur_g_eff",
    "interior_node_errors_q",
    "all_6_interior_nodes_corrupted",
    "gated_firewall_flux_q",
    "gated_firewall_interior_max_error_q",
    "gated_k7_pathways_retained",
    "gated_k7_pathways_retained_pct_dec2",
    "gated_k7_triangles_retained",
    "gated_k7_triangles_retained_pct_dec2",
    "gated_k7_all_21_pairs_compounded",
    "gated_k7_min_compounding_gain_q",
    "gated_k7_min_compounding_gain_dec4",
})

# Full R10+ Lean 4 static trust-escape rules (pure-Init file: no quotes, guillemets, macros, imports, +native)
_LEAN4_BANNED_RE = re.compile(
    r"(?<!\.)\b(?:sorry|admit|axiom|unsafe|native_decide|sorryAx|ofReduceBool|ofReduceNat|"
    r"trustCompiler|mkSorry|run_cmd|run_meta|initialize|builtin_initialize|"
    r"macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat|interpolatedStr|dbg_trace|throwError|"
    r"notation|prefix|infix|infixl|infixr|postfix|csimp|opaque)\b"
    r"|\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b"
    r"|(?:@|(?<!\.)\battribute\s*)\[[^\]]*\b(?:extern|implemented_by)\b"
    r"|\bpartial\s+(?:def|instance|abbrev)\b"
    r"|(?<!\w)\+\s*native\b|\bnative\s*:=\s*(?!false\b)|\bDecide(?:Config|\.Config)\b|\bdecide\s*\(\s*config\b"
    r"|#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|exit(?![\w'!?])|print(?![\w'!?])(?!\s+axioms[ \t]+[A-Za-z_]))"
    r"|(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+"
    r'|["«»]',
    flags=re.DOTALL,
)
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([^']+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([^']+)' depends on axioms: \[([^\]]*)\]$")


# ---------------------------------------------------------------------------
# Zone-B Path, Darwin Prefix, CWD/$PWD, Atomic dir_fd & Atomic Write
# ---------------------------------------------------------------------------

def _require_concrete_path(path: Any, label: str) -> Path:
    oracle.require_ok(type(path) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label}: concrete Path required")
    raw_s = oracle.require_exact_str(str(path), label)
    oracle.require_ok("\x00" not in raw_s, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    return path


def _normalize_darwin_system_prefix(path: Path, *, allow_exact: bool = False) -> Path:
    if sys.platform != "darwin" or not path.is_absolute():
        return path
    parts = path.parts
    min_parts = 2 if allow_exact else 3
    if len(parts) < min_parts or ".." in parts:
        return path
    top = "/" + parts[1]
    for alias, canonical in _DARWIN_SYSTEM_ROOT_ALIASES:
        if top != alias:
            continue
        try:
            st = os.lstat(alias)
            if not stat.S_ISLNK(st.st_mode) or st.st_uid != 0:
                return path
            target = os.readlink(alias)
            if target not in (canonical, canonical.lstrip("/")):
                return path
        except OSError:
            return path
        return Path(canonical, *parts[2:])
    return path


def _safe_cwd(label: str) -> Path:
    try:
        cwd = Path.cwd()
    except OSError as exc:
        raise oracle.S83Error("CWD_UNAVAILABLE", f"{label}: CWD unavailable") from exc
    oracle.require_exact_str(str(cwd), f"{label} CWD")
    return cwd


def _check_pwd_no_symlinks(label: str) -> None:
    pwd = os.environ.get("PWD", "")
    if not pwd.startswith("/"):
        return
    oracle.require_exact_str(pwd, f"{label} PWD")
    oracle.require_ok("\x00" not in pwd, "NUL_BYTE_FORBIDDEN", f"{label} PWD: NUL byte forbidden")
    pwd_path = _normalize_darwin_system_prefix(Path(pwd), allow_exact=True)
    try:
        pwd_st = os.stat(pwd_path)
        cwd_st = os.stat(".")
    except OSError:
        return
    if (pwd_st.st_dev, pwd_st.st_ino) != (cwd_st.st_dev, cwd_st.st_ino):
        return
    try:
        dfd = os.open("/", _DIR_OPEN_FLAGS)
    except OSError as exc:
        raise oracle.S83Error("CWD_UNAVAILABLE", f"{label}: cannot open root for PWD") from exc
    try:
        for part in pwd_path.parts[1:]:
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.S83Error("SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor") from exc
                raise oracle.S83Error("CWD_UNAVAILABLE", f"{label}: PWD ancestor unavailable") from exc
            os.close(dfd)
            dfd = next_fd
    finally:
        os.close(dfd)


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    if target.is_absolute():
        parts = _normalize_darwin_system_prefix(target).parts[1:]
    else:
        cwd = _normalize_darwin_system_prefix(_safe_cwd(label), allow_exact=True)
        _check_pwd_no_symlinks(label)
        parts = cwd.parts[1:] + target.parts
    oracle.require_ok(
        len(parts) >= 1 and parts[-1] != "..",
        "NOT_A_REGULAR_FILE",
        f"{label}: path does not name a regular file leaf",
    )
    parent_parts, leaf = parts[:-1], parts[-1]
    err_code = "FILE_WRITE_ERROR" if create_parents else "FILE_READ_ERROR"
    try:
        dfd = os.open("/", _DIR_OPEN_FLAGS)
    except OSError as exc:
        raise oracle.S83Error(err_code, f"{label}: cannot open root") from exc
    try:
        for part in parent_parts:
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if create_parents and exc.errno == errno.ENOENT:
                    try:
                        os.mkdir(part, 0o755, dir_fd=dfd)
                    except FileExistsError:
                        pass
                    except OSError as mk_exc:
                        raise oracle.S83Error("FILE_WRITE_ERROR", f"{label}: mkdir failed") from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise oracle.S83Error("FILE_WRITE_ERROR", f"{label}: open created dir failed") from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.S83Error("SYMLINK_FORBIDDEN", f"{label}: symlink ancestor forbidden") from exc
                else:
                    raise oracle.S83Error(err_code, f"{label}: ancestor unavailable") from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str = "file", max_bytes: int = MAX_JSON_BYTES) -> bytes:
    target = _require_concrete_path(path, label)
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise oracle.S83Error("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise oracle.S83Error("FILE_READ_ERROR", f"{label}: open failed") from exc
    finally:
        os.close(dfd)

    chunks: list[bytes] = []
    total = 0
    try:
        st_f = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st_f.st_mode), "NOT_A_REGULAR_FILE", f"{label}: not a regular file")
        oracle.require_ok(st_f.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlink forbidden")
        oracle.require_ok(st_f.st_size <= max_bytes, "FILE_TOO_LARGE", f"{label}: size exceeds cap")
        while total <= max_bytes:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except oracle.S83Error:
        raise
    except OSError as exc:
        raise oracle.S83Error("FILE_READ_ERROR", f"{label}: read failed") from exc
    finally:
        os.close(fd)
    oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: stream exceeds cap")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str = "output") -> None:
    global _TEMP_SEQ
    oracle.require_ok(type(payload) is bytes, "INVALID_PAYLOAD_BYTES", f"{label}: exact bytes required")
    target = _require_concrete_path(path, label)
    dfd, leaf = _open_dir_chain(target, label, create_parents=True)
    tmp_name: str | None = None
    try:
        try:
            st_existing = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_existing = None
        except OSError as exc:
            raise oracle.S83Error("FILE_WRITE_ERROR", f"{label}: lstat failed") from exc
        if st_existing is not None:
            oracle.require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf")
            oracle.require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            oracle.require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target")

        pid = os.getpid()
        for _ in range(64):
            with _TEMP_NAME_LOCK:
                _TEMP_SEQ += 1
                seq_num = _TEMP_SEQ
                cand = f".s83.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
            try:
                fd = os.open(
                    cand,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                    0o600,
                    dir_fd=dfd,
                )
                tmp_name = cand
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise oracle.S83Error("FILE_WRITE_ERROR", f"{label}: temp open failed") from exc
        else:
            raise oracle.S83Error("FILE_WRITE_ERROR", f"{label}: temp slots exhausted")

        try:
            os.fchmod(fd, 0o600)
            view = memoryview(payload)
            written = 0
            while written < len(view):
                n_written = os.write(fd, view[written:])
                oracle.require_ok(n_written > 0, "FILE_WRITE_ERROR", f"{label}: short write 0")
                written += n_written
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            oracle.require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp nlink altered")
        except oracle.S83Error:
            raise
        except OSError as exc:
            raise oracle.S83Error("FILE_WRITE_ERROR", f"{label}: write/fsync failed") from exc
        finally:
            os.close(fd)

        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise oracle.S83Error("FILE_WRITE_ERROR", f"{label}: atomic replace failed") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Strict Zero-Float Canonical JSON & Canonical Rational Parsers
# ---------------------------------------------------------------------------

def _parse_bounded_int(token: str) -> int:
    s = oracle.require_exact_str(token, "json_int")
    neg = s.startswith("-")
    body = s[1:] if neg else s
    oracle.require_ok(oracle.is_ascii_digits(body), "INVALID_INT_TOKEN", "non-ASCII digits")
    oracle.require_ok(len(body) <= oracle.MAX_INT_DIGITS, "INT_TOO_LARGE", "int digits cap")
    oracle.require_ok(not (len(body) > 1 and body[0] == "0"), "NONCANONICAL_INT", "leading zero")
    oracle.require_ok(not (neg and body == "0"), "NONCANONICAL_INT", "negative zero")
    val = int(s)
    oracle.require_ok(val.bit_length() <= oracle.MAX_INT_BITS, "INT_TOO_LARGE", "int bits cap")
    return val


def _reject_float(token: str) -> Any:
    raise oracle.S83Error("FLOAT_FORBIDDEN", f"IEEE-754 float forbidden: {token!r}")


def _reject_const(token: str) -> Any:
    raise oracle.S83Error("NONFINITE_JSON_CONSTANT", f"JSON constant forbidden: {token!r}")


def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes, label: str = "json", *, require_canonical: bool = True) -> dict[str, Any]:
    oracle.require_ok(type(raw) is bytes, "INVALID_BYTES", f"{label}: exact bytes required")
    oracle.require_ok(not raw.startswith(b"\xef\xbb\xbf"), "BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    oracle.require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"{label}: CR forbidden")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S83Error("INVALID_UTF8", f"{label}: invalid UTF-8") from exc
    try:
        obj = json.loads(
            text,
            parse_float=_reject_float,
            parse_int=_parse_bounded_int,
            parse_constant=_reject_const,
            object_pairs_hook=_no_dup_pairs,
        )
    except oracle.S83Error:
        raise
    except (ValueError, RecursionError) as exc:
        raise oracle.S83Error("INVALID_JSON", f"{label}: malformed JSON") from exc
    oracle.require_ok(type(obj) is dict, "INVALID_ROOT_TYPE", f"{label}: root must be dict")
    oracle.validate_strict_json_tree(obj, label)
    if require_canonical:
        oracle.require_ok(
            hmac.compare_digest(raw, oracle.canonical_json_bytes(obj)),
            "NONCANONICAL_JSON",
            f"{label}: not canonical ASCII LF JSON",
        )
    return obj


def parse_canonical_rational_str(val: Any, label: str) -> Fraction:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(len(s) > 0, "INVALID_RATIONAL", f"{label}: empty")
    if "/" in s:
        parts = s.split("/")
        oracle.require_ok(len(parts) == 2, "INVALID_RATIONAL", f"{label}: multiple slashes")
        num_s, den_s = parts[0], parts[1]
        num = _parse_bounded_int(num_s)
        oracle.require_ok(not den_s.startswith("-"), "INVALID_RATIONAL", f"{label}: negative den")
        den = _parse_bounded_int(den_s)
        oracle.require_ok(den > 1, "NONCANONICAL_RATIONAL", f"{label}: den must be > 1")
        q = Fraction(num, den)
        oracle.require_ok(q.denominator == den, "NONCANONICAL_RATIONAL", f"{label}: not reduced")
        return q
    return Fraction(_parse_bounded_int(s), 1)


def _require_exact_dict(obj: Any, keys: frozenset[str], label: str) -> dict[str, Any]:
    oracle.require_ok(type(obj) is dict, "INVALID_SCHEMA_DICT", f"{label}: exact dict required")
    oracle.require_ok(frozenset(obj.keys()) == keys, "INVALID_SCHEMA_KEYS", f"{label}: keyset mismatch")
    return obj


# ---------------------------------------------------------------------------
# Live Lean 4.36.0 & R10+ Static Lean Gate
# ---------------------------------------------------------------------------

def _strip_lean4_for_static_gate(source: str) -> str:
    """Strip Lean 4 nested block comments and line comments fail-closed."""
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if depth > 0:
            if ch == "/" and nxt == "-":
                depth += 1
                out.append("  ")
                i += 2
            elif ch == "-" and nxt == "/":
                depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if ch == "/" and nxt == "-":
            depth = 1
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            out.append("  ")
            i += 2
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    oracle.require_ok(depth == 0, "LEAN4_UNTERMINATED_LEX", "unterminated Lean block comment")
    return "".join(out)


def static_gate_lean4_source(source: str) -> None:
    s = oracle.require_exact_str(source, "lean_source")
    oracle.require_ok("\r" not in s and "\x00" not in s, "LEAN4_BAD_CHARS", "CR/NUL in Lean source")
    cleaned = _strip_lean4_for_static_gate(s)
    m = _LEAN4_BANNED_RE.search(cleaned)
    oracle.require_ok(m is None, "LEAN4_TRUST_ESCAPE", f"banned Lean construct: {m.group(0)!r}" if m else "")
    for thm in oracle.LEAN_THEOREM_NAMES:
        short = thm.split(".")[-1]
        oracle.require_ok(f"theorem {short}" in cleaned, "LEAN4_MISSING_THEOREM", f"missing {short}")
        oracle.require_ok(f"#print axioms {thm}" in cleaned, "LEAN4_MISSING_PRINT_AXIOMS", f"missing #print axioms {thm}")


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN")
    if env_bin is not None:
        oracle.require_exact_str(env_bin, "ALETHEIA_LEAN_BIN")
        p = Path(env_bin)
        oracle.require_ok(p.is_file() and os.access(str(p), os.X_OK), "LEAN_BINARY_UNAVAILABLE", "ALETHEIA_LEAN_BIN unusable")
        return str(p)
    found = shutil.which("lean")
    if found is not None and os.access(found, os.X_OK):
        return found
    for rel in ((".local", "bin", "lean"), (".elan", "bin", "lean")):
        cand = Path.home().joinpath(*rel)
        if cand.is_file() and os.access(str(cand), os.X_OK):
            return str(cand)
    raise oracle.S83Error("LEAN_BINARY_UNAVAILABLE", "lean executable not found")


def verify_lean4_file_live(lean_path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_capped(lean_path, "lean_source", max_bytes=1024 * 1024)
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S83Error("INVALID_UTF8", "Lean source not UTF-8") from exc
    static_gate_lean4_source(src)
    lean_bin = resolve_lean_binary()
    try:
        v_proc = subprocess.run([lean_bin, "--version"], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise oracle.S83Error("LEAN_EXEC_ERROR", "lean --version failed") from exc
    oracle.require_ok(v_proc.returncode == 0 and "4.36.0" in v_proc.stdout, "LEAN_VERSION_MISMATCH", "Lean 4.36.0 required")
    try:
        proc = subprocess.run([lean_bin, str(lean_path)], capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise oracle.S83Error("LEAN_EXEC_ERROR", "lean elaboration failed") from exc
    oracle.require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    oracle.require_ok(proc.stderr.strip() == "", "LEAN_STDERR_NONEMPTY", "lean stderr must be empty")
    oracle.require_ok("warning:" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning forbidden")

    joined_lines: list[str] = []
    pending = ""
    for raw_line in proc.stdout.splitlines():
        s_line = raw_line.strip()
        if not s_line:
            continue
        if pending:
            pending = f"{pending} {s_line}"
            if "]" in s_line:
                joined_lines.append(pending)
                pending = ""
        elif "[" in s_line and "]" not in s_line:
            pending = s_line
        else:
            joined_lines.append(s_line)
    oracle.require_ok(pending == "", "LEAN_UNEXPECTED_STDOUT", "unterminated axiom list")

    seen: dict[str, list[str]] = {}
    for s_line in joined_lines:
        m_none = _LEAN4_AXIOM_NONE_RE.match(s_line)
        if m_none is not None:
            thm_name = m_none.group(1)
            oracle.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate axiom line: {thm_name}")
            seen[thm_name] = []
            continue
        m_dep = _LEAN4_AXIOM_DEP_RE.match(s_line)
        oracle.require_ok(m_dep is not None, "LEAN_UNEXPECTED_STDOUT", f"unexpected lean line: {s_line[:80]}")
        thm_name = m_dep.group(1)
        oracle.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate axiom line: {thm_name}")
        axs = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        for ax in axs:
            oracle.require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"forbidden axiom {ax}")
        seen[thm_name] = axs
    oracle.require_ok(frozenset(seen.keys()) == frozenset(oracle.LEAN_THEOREM_NAMES), "LEAN_THEOREM_SET_MISMATCH", "axioms set mismatch")
    return {
        "lean_version": v_proc.stdout.strip().splitlines()[0],
        "theorems_verified": len(seen),
        "lean_source_sha256": oracle.sha256_hex(raw),
    }


# ---------------------------------------------------------------------------
# Fail-Closed Secondary Audit (FR0 / SEC) & Full Replay (FR1)
# ---------------------------------------------------------------------------

def _require_inertia(val: Any, expected: list[int], label: str) -> None:
    oracle.require_ok(type(val) is list and len(val) == 3, "INVALID_INERTIA", label)
    for elem in val:
        oracle.require_exact_int(elem, label, lo=0, hi=16)
    oracle.require_ok(val == expected, "INERTIA_MISMATCH", f"{label}: expected {expected}")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed semantic + algebraic auditor enforced under BOTH full_replay=True and False."""
    oracle.require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")
    oracle.validate_strict_json_tree(payload, "payload")
    _require_exact_dict(payload, _PAYLOAD_KEYS, "payload")
    oracle.require_ok(payload["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema_version")
    oracle.require_ok(payload["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "track_id")
    oracle.require_ok(payload["oracle_class"] == "exact", "SCHEMA_MISMATCH", "oracle_class")
    oracle.require_ok(payload["novelty_classification"] == "N1", "SCHEMA_MISMATCH", "novelty")

    pa = _require_exact_dict(payload["pinned_artifacts"], _PINNED_KEYS, "pinned_artifacts")
    oracle.require_ok(pa["lean_source"] == "AllToAllEpistemicMesh.lean", "SCHEMA_MISMATCH", "lean_source")
    oracle.require_hex64(pa["lean_source_sha256"], "lean_source_sha256")
    oracle.require_ok(pa["lean_toolchain"] == oracle.EXPECTED_LEAN_TOOLCHAIN, "SCHEMA_MISMATCH", "lean_toolchain")
    oracle.require_hex64(pa["lean_toolchain_sha256"], "lean_toolchain_sha256")
    oracle.require_hex64(pa["lakefile_sha256"], "lakefile_sha256")
    thm_n = oracle.require_exact_int(
        pa["lean_theorem_count"], "lean_theorem_count", lo=len(oracle.LEAN_THEOREM_NAMES), hi=len(oracle.LEAN_THEOREM_NAMES)
    )
    thms = pa["lean_theorem_names"]
    oracle.require_ok(type(thms) is list and tuple(thms) == oracle.LEAN_THEOREM_NAMES, "THEOREM_LIST_MISMATCH", "lean_theorem_names")

    # Nodes
    nodes = payload["mesh_nodes"]
    oracle.require_ok(type(nodes) is list and len(nodes) == 8, "INVALID_NODES", "8 nodes required")
    for idx, nd in enumerate(nodes):
        row = _require_exact_dict(nd, _NODE_KEYS, f"node[{idx}]")
        oracle.require_ok(row["id"] == f"v{idx}", "INVALID_NODE_ID", f"node[{idx}].id")
        oracle.require_hex64(row["cert_sha256"], f"node[{idx}].cert_sha256")

    # Pillar 1: Schur compounding, Foster identity, triangle inequalities, 4-node pushforward
    p1 = _require_exact_dict(payload["pillar1_schur_compounding"], _P1_KEYS, "pillar1")
    oracle.require_exact_int(p1["n_nodes"], "p1.n_nodes", lo=8, hi=8)
    oracle.require_exact_int(p1["n_undirected_pathways"], "p1.n_undirected", lo=28, hi=28)
    oracle.require_exact_int(p1["n_directed_pathways"], "p1.n_directed", lo=56, hi=56)
    p1_cls = _require_exact_dict(p1["pathway_class_counts"], frozenset(oracle.PATHWAY_WEIGHTS.keys()), "p1.cls")
    c_ex = oracle.require_exact_int(p1_cls["EXACT_COMMUTE"], "p1.c_ex", lo=1, hi=28)
    c_br = oracle.require_exact_int(p1_cls["CONDITIONAL_BRIDGE"], "p1.c_br", lo=1, hi=28)
    c_ob = oracle.require_exact_int(p1_cls["EXACT_OBSTRUCTION"], "p1.c_ob", lo=1, hi=28)
    oracle.require_ok(c_ex + c_br + c_ob == 28, "PILLAR1_COUNTS", "pathway class sum != 28")
    tot_w = parse_canonical_rational_str(p1["total_conductance_q"], "p1.total_w")
    oracle.require_ok(tot_w == Fraction(4 * c_ex + 2 * c_br + c_ob, 1), "PILLAR1_ALGEBRA", "total conductance mismatch")
    _require_inertia(p1["laplacian_inertia"], [7, 0, 1], "p1.lap_inertia")
    oracle.require_ok(
        parse_canonical_rational_str(p1["foster_sum_q"], "p1.foster") == Fraction(7, 1)
        and oracle.require_bool(p1["foster_identity_exact"], "p1.foster_flag") is True
        and oracle.require_bool(p1["all_28_pairs_strictly_compounded"], "p1.all28") is True,
        "PILLAR1_FOSTER_FAIL",
        "Foster or compounding invariant failed",
    )
    oracle.require_exact_int(p1["resistance_triangle_inequalities_verified"], "p1.tri_ineq", lo=168, hi=168)
    _require_inertia(p1["core4_schur_inertia"], [3, 0, 1], "p1.core4_inertia")
    oracle.require_ok(oracle.require_bool(p1["core4_all_6_edges_strictly_boosted"], "p1.core4_flag") is True, "PILLAR1_CORE4_FAIL", "core4")

    p1_pairs = p1["pair_rows"]
    oracle.require_ok(type(p1_pairs) is list and len(p1_pairs) == 28, "PILLAR1_PAIRS", "28 pair rows required")
    foster_acc = Fraction(0)
    min_g = Fraction(10**9, 1)
    max_g = Fraction(0, 1)
    for idx, pr in enumerate(p1_pairs):
        rr = _require_exact_dict(pr, _P1_PAIR_KEYS, f"p1.pair[{idx}]")
        cls = oracle.require_exact_str(rr["pathway_class"], f"p1.pair[{idx}].cls")
        oracle.require_ok(cls in oracle.PATHWAY_WEIGHTS, "PILLAR1_PAIR_CLS", cls)
        w_d = parse_canonical_rational_str(rr["direct_w_q"], "w_d")
        boost = parse_canonical_rational_str(rr["schur_boost_q"], "boost")
        g_e = parse_canonical_rational_str(rr["g_eff_q"], "g_e")
        r_e = parse_canonical_rational_str(rr["r_eff_q"], "r_e")
        gain = parse_canonical_rational_str(rr["compounding_gain_q"], "gain")
        oracle.require_ok(
            w_d == Fraction(oracle.PATHWAY_WEIGHTS[cls], 1)
            and boost > 0
            and g_e == w_d + boost
            and g_e * r_e == 1
            and gain == g_e / w_d
            and rr["compounding_gain_dec4"] == oracle.dec_from_q(gain, 4),
            "PILLAR1_PAIR_ALGEBRA",
            rr["pair"],
        )
        foster_acc += w_d * r_e
        if gain < min_g:
            min_g = gain
        if gain > max_g:
            max_g = gain
    oracle.require_ok(foster_acc == Fraction(7, 1), "PILLAR1_FOSTER_FAIL", "recomputed foster != 7")
    oracle.require_ok(
        parse_canonical_rational_str(p1["min_compounding_gain_q"], "min_g") == min_g
        and p1["min_compounding_gain_dec4"] == oracle.dec_from_q(min_g, 4)
        and parse_canonical_rational_str(p1["max_compounding_gain_q"], "max_g") == max_g
        and p1["max_compounding_gain_dec4"] == oracle.dec_from_q(max_g, 4),
        "PILLAR1_EXTREMA",
        "min/max gain mismatch",
    )
    c4_rows = p1["core4_edges"]
    oracle.require_ok(type(c4_rows) is list and len(c4_rows) == 6, "PILLAR1_CORE4_LEN", "6 core4 edges")
    for idx, cr in enumerate(c4_rows):
        cc = _require_exact_dict(cr, _P1_CORE4_KEYS, f"p1.core4[{idx}]")
        wd = parse_canonical_rational_str(cc["direct_w_q"], "c4.wd")
        we = parse_canonical_rational_str(cc["core4_eff_w_q"], "c4.we")
        wb = parse_canonical_rational_str(cc["core4_boost_q"], "c4.wb")
        oracle.require_ok(
            wd > 0 and wb > 0 and we == wd + wb and cc["core4_ratio_dec4"] == oracle.dec_from_q(we / wd, 4),
            "PILLAR1_CORE4_ALGEBRA",
            cc["pair"],
        )

    # Pillar 2: 56 triangles, Bianchi coboundary
    p2 = _require_exact_dict(payload["pillar2_triangle_holonomy"], _P2_KEYS, "pillar2")
    oracle.require_exact_int(p2["n_triangles"], "p2.n_tri", lo=56, hi=56)
    p2c = _require_exact_dict(p2["classification_counts"], _P2_CLASS_KEYS, "p2.cls")
    n_et = oracle.require_exact_int(p2c["EXACT_TRANSITIVE_CLOSURE"], "p2.et", lo=1, hi=56)
    n_cc = oracle.require_exact_int(p2c["CONDITIONAL_COMPOUNDING_CLOSURE"], "p2.cc", lo=1, hi=56)
    n_fr = oracle.require_exact_int(p2c["FRUSTRATED_CURVATURE_LOOP"], "p2.fr", lo=1, hi=56)
    n_mw = oracle.require_exact_int(p2c["MULTI_WALL_BOUNDARY_SECTOR"], "p2.mw", lo=1, hi=56)
    oracle.require_ok(n_et + n_cc + n_fr + n_mw == 56, "PILLAR2_SUM", "triangle classes != 56")
    n_odd = oracle.require_exact_int(p2["odd_z2_holonomy_triangles"], "p2.odd", lo=1, hi=56)
    n_ev = oracle.require_exact_int(p2["even_z2_holonomy_triangles"], "p2.even", lo=1, hi=56)
    oracle.require_ok(n_odd + n_ev == 56 and n_odd >= n_fr, "PILLAR2_PARITY", "odd/even sum")
    oracle.require_ok(
        type(p2["exact_transitive_closures"]) is list and len(p2["exact_transitive_closures"]) == n_et
        and type(p2["frustrated_curvature_loops"]) is list and len(p2["frustrated_curvature_loops"]) == n_fr
        and type(p2["multi_wall_boundary_sectors"]) is list and len(p2["multi_wall_boundary_sectors"]) == n_mw,
        "PILLAR2_LISTS",
        "triangle lists count mismatch",
    )
    oracle.require_exact_int(p2["tetrahedra_checked"], "p2.tet", lo=70, hi=70)
    oracle.require_ok(oracle.require_bool(p2["bianchi_coboundary_zero_all_70"], "p2.bianchi") is True, "PILLAR2_BIANCHI", "Bianchi")
    b_min = parse_canonical_rational_str(p2["min_3node_schur_boost_q"], "p2.b_min")
    b_max = parse_canonical_rational_str(p2["max_3node_schur_boost_q"], "p2.b_max")
    oracle.require_ok(Fraction(0) < b_min <= b_max, "PILLAR2_BOOST", "3-node boost bounds")

    # Pillar 3: Silo cuts & contagion firewall
    p3 = _require_exact_dict(payload["pillar3_silo_cuts_and_firewall"], _P3_KEYS, "pillar3")
    oracle.require_exact_int(p3["total_nontrivial_bipartitions"], "p3.bipart", lo=127, hi=127)
    oracle.require_exact_int(p3["prop_e10_k8_balanced_min_pathways"], "p3.min_e", lo=15, hi=15)
    oracle.require_exact_int(p3["prop_e10_k8_balanced_min_triangles_destroyed"], "p3.min_t", lo=45, hi=45)
    splits = _require_exact_dict(p3["split_summary"], frozenset({"1|7", "2|6", "3|5", "4|4"}), "p3.splits")
    expected_splits = {
        "1|7": (8, 7, 21),
        "2|6": (28, 12, 36),
        "3|5": (56, 15, 45),
        "4|4": (35, 16, 48),
    }
    for sk, (exp_p, exp_e, exp_t) in expected_splits.items():
        sr = _require_exact_dict(splits[sk], _P3_SPLIT_ROW_KEYS, f"p3.split[{sk}]")
        oracle.require_exact_int(sr["partitions_counted"], f"{sk}.p", lo=exp_p, hi=exp_p)
        oracle.require_exact_int(sr["pathways_severed"], f"{sk}.e", lo=exp_e, hi=exp_e)
        oracle.require_exact_int(sr["triangles_destroyed"], f"{sk}.t", lo=exp_t, hi=exp_t)
        oracle.require_ok(
            sr["pathways_severed_pct_dec2"] == oracle.dec_from_q(Fraction(exp_e * 100, 28), 2)
            and sr["triangles_destroyed_pct_dec2"] == oracle.dec_from_q(Fraction(exp_t * 100, 56), 2),
            "PILLAR3_SPLIT_PCT",
            sk,
        )
        wmin = parse_canonical_rational_str(sr["min_weighted_cut_q"], f"{sk}.wmin")
        wmax = parse_canonical_rational_str(sr["max_weighted_cut_q"], f"{sk}.wmax")
        oracle.require_ok(Fraction(0) < wmin <= wmax, "PILLAR3_CUT_W", sk)

    fw = _require_exact_dict(p3["contagion_firewall_case"], _P3_FW_KEYS, "p3.fw")
    j_dir = parse_canonical_rational_str(fw["direct_edge_flux_q"], "fw.j_dir")
    j_ung = parse_canonical_rational_str(fw["ungated_total_flux_q"], "fw.j_ung")
    amp = parse_canonical_rational_str(fw["ungated_flux_amplification_q"], "fw.amp")
    oracle.require_ok(
        parse_canonical_rational_str(fw["injected_error_q"], "fw.eps") == Fraction(1, 1)
        and j_dir > 0
        and j_ung > j_dir
        and amp == j_ung / j_dir
        and fw["ungated_flux_amplification_dec4"] == oracle.dec_from_q(amp, 4)
        and oracle.require_bool(fw["flux_equals_schur_g_eff"], "fw.schur") is True
        and oracle.require_bool(fw["all_6_interior_nodes_corrupted"], "fw.corrupt") is True,
        "PILLAR3_CONTAGION",
        "ungated contagion invariant",
    )
    ie = _require_exact_dict(fw["interior_node_errors_q"], frozenset({"v1", "v2", "v3", "v4", "v5", "v7"}), "p3.fw.ie")
    for nk, nv in ie.items():
        uv = parse_canonical_rational_str(nv, f"fw.ie.{nk}")
        oracle.require_ok(Fraction(0) < uv < Fraction(1), "PILLAR3_IE_RANGE", nk)
    oracle.require_exact_int(fw["gated_k7_pathways_retained"], "fw.k7e", lo=21, hi=21)
    oracle.require_exact_int(fw["gated_k7_triangles_retained"], "fw.k7t", lo=35, hi=35)
    oracle.require_ok(
        parse_canonical_rational_str(fw["gated_firewall_flux_q"], "fw.gflux") == 0
        and parse_canonical_rational_str(fw["gated_firewall_interior_max_error_q"], "fw.gerr") == 0
        and fw["gated_k7_pathways_retained_pct_dec2"] == "75.00"
        and fw["gated_k7_triangles_retained_pct_dec2"] == "62.50"
        and oracle.require_bool(fw["gated_k7_all_21_pairs_compounded"], "fw.k7c") is True,
        "PILLAR3_FIREWALL",
        "gated firewall invariant",
    )
    k7mg = parse_canonical_rational_str(fw["gated_k7_min_compounding_gain_q"], "fw.k7mg")
    oracle.require_ok(
        k7mg > 1 and fw["gated_k7_min_compounding_gain_dec4"] == oracle.dec_from_q(k7mg, 4),
        "PILLAR3_K7_GAIN",
        "k7 min compounding gain",
    )

    return {
        "secondary_audit_passed": True,
        "lean_theorem_count": thm_n,
        "n_pathways": 28,
        "n_triangles": 56,
        "frustrated_loops": n_fr,
    }


def _load_track_artifacts(track_dir: Path) -> tuple[str, str, str, dict[str, Any]]:
    tc_raw = read_regular_bytes_capped(track_dir / "lean-toolchain", "lean-toolchain", max_bytes=256)
    try:
        tc_text = tc_raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise oracle.S83Error("INVALID_UTF8", "lean-toolchain invalid UTF-8") from exc
    oracle.require_ok(tc_text == oracle.EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", "unexpected lean-toolchain")
    lake_raw = read_regular_bytes_capped(track_dir / "lakefile.toml", "lakefile.toml", max_bytes=4096)
    lean_res = verify_lean4_file_live(track_dir / "AllToAllEpistemicMesh.lean")
    return (
        lean_res["lean_source_sha256"],
        oracle.sha256_hex(tc_raw),
        oracle.sha256_hex(lake_raw),
        lean_res,
    )


def verify_certificate_dict(
    cert: Any,
    *,
    full_replay: bool = True,
    track_dir: Path | None = None,
) -> dict[str, Any]:
    oracle.require_bool(full_replay, "full_replay")
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    oracle.validate_strict_json_tree(cert, "certificate")
    _require_exact_dict(cert, _CERT_KEYS, "certificate")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "cert schema_version")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "cert track_id")

    p_sha = oracle.require_hex64(cert["payload_sha256"], "payload_sha256")
    c_sha = oracle.require_hex64(cert["certificate_sha256"], "certificate_sha256")
    payload = cert["payload"]
    sec_res = secondary_audit_payload(payload)

    recomputed_p = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    oracle.require_ok(hmac.compare_digest(p_sha, recomputed_p), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")
    env = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    recomputed_c = oracle.sha256_hex(oracle.canonical_json_bytes(env))
    oracle.require_ok(hmac.compare_digest(c_sha, recomputed_c), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    replayed = False
    lean_live: dict[str, Any] | None = None
    if full_replay:
        root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
        l_sha, tc_sha, lk_sha, lean_live = _load_track_artifacts(root)
        expected = oracle.build_certificate(
            lean_source_sha256=l_sha,
            toolchain_sha256=tc_sha,
            lakefile_sha256=lk_sha,
        )
        oracle.require_ok(
            hmac.compare_digest(oracle.canonical_json_bytes(cert), oracle.canonical_json_bytes(expected)),
            "FULL_REPLAY_MISMATCH",
            "certificate does not match pure-Z/Q + Lean 4.36.0 replay",
        )
        replayed = True

    out: dict[str, Any] = {
        "valid": True,
        "full_replay": replayed,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "secondary_audit": sec_res,
    }
    if lean_live is not None:
        out["lean_live"] = lean_live
    return out


def write_certificate_file(path: Path, *, track_dir: Path | None = None) -> dict[str, Any]:
    root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
    l_sha, tc_sha, lk_sha, _ = _load_track_artifacts(root)
    cert = oracle.build_certificate(
        lean_source_sha256=l_sha,
        toolchain_sha256=tc_sha,
        lakefile_sha256=lk_sha,
    )
    raw = oracle.canonical_json_bytes(cert)
    write_regular_bytes_safe(path, raw, "certificate")
    return {
        "written": True,
        "bytes": len(raw),
        "file_sha256": oracle.sha256_hex(raw),
        "certificate_sha256": cert["certificate_sha256"],
    }


def check_certificate_file(path: Path, *, full_replay: bool = True, track_dir: Path | None = None) -> dict[str, Any]:
    raw = read_regular_bytes_capped(path, "certificate")
    cert = parse_strict_json_bytes(raw, "certificate", require_canonical=True)
    res = verify_certificate_dict(cert, full_replay=full_replay, track_dir=track_dir)
    res["file_sha256"] = oracle.sha256_hex(raw)
    return res


def _parse_cli_args(argv: Any) -> dict[str, Any]:
    oracle.require_ok(type(argv) is list, "INVALID_ARGV", "argv must be exact list")
    mode: str | None = None
    target_path: str | None = None
    want_json = False
    i = 0
    n = len(argv)
    while i < n:
        arg = oracle.require_exact_str(argv[i], "argv")
        oracle.require_ok("\x00" not in arg, "NUL_BYTE_FORBIDDEN", "NUL byte in argv")
        if arg == "--json":
            oracle.require_ok(not want_json, "DUPLICATE_FLAG", "--json repeated")
            want_json = True
            i += 1
        elif arg == "--standalone":
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            mode = "standalone"
            i += 1
        elif arg in ("--check", "--write"):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            oracle.require_ok(i + 1 < n, "MISSING_PATH_ARG", f"{arg} requires a path")
            val = oracle.require_exact_str(argv[i + 1], f"{arg} path")
            oracle.require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", f"NUL byte in {arg} path")
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = arg[2:]
            target_path = val
            i += 2
        elif arg.startswith("--check=") or arg.startswith("--write="):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            flag_name, val = arg.split("=", 1)
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = flag_name[2:]
            target_path = val
            i += 1
        else:
            raise oracle.S83Error("UNKNOWN_FLAG", f"unsupported flag: {arg!r}")
    return {"mode": mode or "default", "target": target_path, "json": want_json}


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv: Any = list(sys.argv[1:]) if argv is None else argv
    try:
        opts = _parse_cli_args(raw_argv)
        mode = opts["mode"]
        if mode == "standalone":
            root = Path(_THIS_DIR)
            l_sha, tc_sha, lk_sha, _ = _load_track_artifacts(root)
            cert = oracle.build_certificate(
                lean_source_sha256=l_sha,
                toolchain_sha256=tc_sha,
                lakefile_sha256=lk_sha,
            )
            sys.stdout.write(oracle.canonical_json_bytes(cert).decode("ascii"))
            return 0
        if mode == "write":
            res = write_certificate_file(Path(opts["target"]))
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"WROTE {res['file_sha256']}\n")
            return 0
        if mode == "check":
            res = check_certificate_file(Path(opts["target"]), full_replay=True)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"OK {res['certificate_sha256']}\n")
            return 0
        res = check_certificate_file(Path(_THIS_DIR) / "s83_epistemic_mesh_certificate.json", full_replay=True)
        if opts["json"]:
            sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
        else:
            sys.stdout.write(f"OK {res['certificate_sha256']}\n")
        return 0
    except oracle.S83Error as exc:
        err_obj = {"error": True, "code": exc.code, "detail": exc.detail}
        sys.stderr.write(json.dumps(err_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
