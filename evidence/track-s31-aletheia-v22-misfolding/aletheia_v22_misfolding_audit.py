"""Zone-B hardened standalone CLI & certificate verifier for Track S31.

Zero external dependencies, zero IEEE-754 floats, zero bare asserts, zero RNG.
Uniform Zone-B Gold Standard built in from R1:
  - Concrete pathlib.Path check + NUL-byte & lone UTF-16 surrogate path refusal
  - Deleted-CWD OSError wrapping -> CWD_UNAVAILABLE (rc=2)
  - Relative-path PWD symlink walk + atomic per-component dir_fd openat
    (O_RDONLY | O_DIRECTORY | O_NOFOLLOW) traversal (zero renameat2 TOCTOU)
  - Leaf read via O_RDONLY | O_NOFOLLOW | O_NONBLOCK + fstat S_ISREG + streaming capped read
    (rejects /proc/kallsyms st_size==0 pseudofiles, FIFOs, dirs, symlinks, chmod 000)
  - Leaf write via dir_fd lstat (SYMLINK_FORBIDDEN / NOT_A_REGULAR_FILE / HARDLINK_FORBIDDEN)
    + O_CREAT | O_EXCL | O_NOFOLLOW temp in same dfd + atomic os.replace(..., src_dir_fd, dst_dir_fd)
  - Strict manual exact-str CLI parser (rejects --write --json, --write=--json, --check=--json,
    --write=, --check=, empty paths, unknown flags -> rc=2, zero files created)
  - Full pure-Q deterministic replay + secondary algebraic invariant cross-check + constant-time
    hmac.compare_digest over canonical LF-only compact JSON bytes
"""
from __future__ import annotations

import errno
from fractions import Fraction
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

_ROOT_DIR = str(Path(__file__).resolve().parent)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import aletheia_v22_misfolding_oracle as oracle

MAX_JSON_BYTES = 1_048_576
MAX_ALLOWED_READ_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
MAX_JSON_DEPTH = 64
_EXACT_PATH_TYPES = (Path, type(Path()))
DEFAULT_CERT_NAME = "aletheia_v22_misfolding_certificate.json"


def _require_concrete_path(path: Any, label: str) -> Path:
    oracle.require_ok(
        type(path) in _EXACT_PATH_TYPES,
        "INVALID_PATH_TYPE",
        f"{label}: concrete pathlib.Path required",
    )
    raw_s = str(path)
    oracle.require_ok("\x00" not in raw_s, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    try:
        raw_s.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise oracle.AletheiaV22Error("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate in path") from exc
    return path


def _safe_cwd(label: str) -> Path:
    try:
        return Path.cwd()
    except OSError as exc:
        raise oracle.AletheiaV22Error("CWD_UNAVAILABLE", f"{label}: current working directory unavailable ({exc})") from exc


def _check_pwd_no_symlinks(label: str) -> None:
    pwd = os.environ.get("PWD")
    if pwd and os.path.isabs(pwd):
        try:
            pwd.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise oracle.AletheiaV22Error("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate in PWD") from exc
        pwd_path = Path(pwd)
        cur = Path(pwd_path.anchor)
        for part in pwd_path.parts[1:]:
            cur = cur / part
            oracle.require_ok(
                not os.path.islink(cur),
                "SYMLINK_ANCESTOR_FORBIDDEN",
                f"{label}: symlink PWD ancestor forbidden",
            )


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    """Open ancestor directory chain atomically via dir_fd + O_DIRECTORY | O_NOFOLLOW."""
    if target.is_absolute():
        parts = target.parts[1:]
    else:
        cwd = _safe_cwd(label)
        _check_pwd_no_symlinks(label)
        parts = cwd.parts[1:] + target.parts
    oracle.require_ok(len(parts) >= 1, "NOT_A_REGULAR_FILE", f"{label}: path has no leaf component")
    oracle.require_ok(parts[-1] not in ("", ".", ".."), "NOT_A_REGULAR_FILE", f"{label}: invalid leaf component")
    parent_parts = parts[:-1]
    leaf = parts[-1]
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    err_code = "FILE_WRITE_ERROR" if create_parents else "FILE_READ_ERROR"
    try:
        dfd = os.open("/", dir_flags)
    except OSError as exc:
        raise oracle.AletheiaV22Error(err_code, f"{label}: cannot open root ({exc})") from exc
    try:
        for part in parent_parts:
            if part == ".":
                continue
            try:
                next_fd = os.open(part, dir_flags, dir_fd=dfd)
            except OSError as exc:
                if create_parents and exc.errno == errno.ENOENT:
                    try:
                        os.mkdir(part, 0o755, dir_fd=dfd)
                    except FileExistsError:
                        pass
                    except OSError as mk_exc:
                        raise oracle.AletheiaV22Error("FILE_WRITE_ERROR", f"{label}: mkdir failed ({mk_exc})") from mk_exc
                    try:
                        next_fd = os.open(part, dir_flags, dir_fd=dfd)
                    except OSError as reopen_exc:
                        raise oracle.AletheiaV22Error(
                            "FILE_WRITE_ERROR", f"{label}: cannot open created dir ({reopen_exc})"
                        ) from reopen_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    try:
                        st_p = os.lstat(part, dir_fd=dfd)
                        is_lnk = stat.S_ISLNK(st_p.st_mode)
                    except OSError:
                        is_lnk = False
                    if is_lnk:
                        raise oracle.AletheiaV22Error("SYMLINK_FORBIDDEN", f"{label}: symlink component forbidden") from exc
                    raise oracle.AletheiaV22Error(err_code, f"{label}: non-directory ancestor ({exc})") from exc
                else:
                    raise oracle.AletheiaV22Error(err_code, f"{label}: cannot open ancestor ({exc})") from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Read regular file bytes under strict cap via atomic dir_fd openat O_NOFOLLOW|O_NONBLOCK + fstat S_ISREG."""
    target = _require_concrete_path(path, label)
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_READ_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise oracle.AletheiaV22Error("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise oracle.AletheiaV22Error("FILE_READ_ERROR", f"{label}: cannot open ({exc})") from exc
    finally:
        os.close(dfd)
    chunks: list[bytes] = []
    total = 0
    try:
        st_f = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st_f.st_mode), "NOT_A_REGULAR_FILE", f"{label}: not a regular file")
        while total <= max_bytes:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except oracle.AletheiaV22Error:
        raise
    except OSError as exc:
        raise oracle.AletheiaV22Error("FILE_READ_ERROR", f"{label}: read failed ({exc})") from exc
    finally:
        os.close(fd)
    oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} bytes")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str) -> None:
    """Write bytes atomically via dir_fd O_CREAT|O_EXCL|O_NOFOLLOW + fsync + os.replace (zero TOCTOU/hardlink clobber)."""
    target = _require_concrete_path(path, label)
    oracle.require_ok(type(payload) is bytes, "INVALID_PAYLOAD_BYTES", f"{label}: exact bytes payload required")
    dfd, leaf = _open_dir_chain(target, label, create_parents=True)
    tmp_name: str | None = None
    try:
        try:
            st_existing = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_existing = None
        except OSError as exc:
            raise oracle.AletheiaV22Error("FILE_WRITE_ERROR", f"{label}: stat failed ({exc})") from exc
        if st_existing is not None:
            oracle.require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden")
            oracle.require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: refusing non-regular target")
            oracle.require_ok(st_existing.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: refusing hardlinked target")
        pid = os.getpid()
        for seq in range(64):
            cand = f".{leaf}.s31_tmp_{pid}_{seq}"
            try:
                fd = os.open(cand, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o644, dir_fd=dfd)
                tmp_name = cand
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise oracle.AletheiaV22Error("FILE_WRITE_ERROR", f"{label}: create temp failed ({exc})") from exc
        else:
            raise oracle.AletheiaV22Error("FILE_WRITE_ERROR", f"{label}: exhausted temp file slots")
        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                written += os.write(fd, view[written:])
            os.fsync(fd)
        except OSError as exc:
            raise oracle.AletheiaV22Error("FILE_WRITE_ERROR", f"{label}: write failed ({exc})") from exc
        finally:
            os.close(fd)
        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise oracle.AletheiaV22Error("FILE_WRITE_ERROR", f"{label}: atomic replace failed ({exc})") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


def _reject_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def _reject_nonfinite(token: str) -> Any:
    raise oracle.AletheiaV22Error("NONFINITE_JSON", f"non-finite JSON constant {token!r}")


def _reject_float(token: str) -> Any:
    raise oracle.AletheiaV22Error("FLOAT_FORBIDDEN", f"JSON float token forbidden: {token!r}")


def _validate_json_tree(root: Any, label: str) -> None:
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        oracle.require_ok(depth <= MAX_JSON_DEPTH, "MAX_DEPTH_EXCEEDED", f"{label}: depth > {MAX_JSON_DEPTH}")
        t = type(node)
        if t is str:
            try:
                node.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise oracle.AletheiaV22Error("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate") from exc
        elif t is dict:
            for k, v in node.items():
                oracle.require_ok(type(k) is str, "INVALID_JSON_KEY", f"{label}: dict keys must be exact str")
                stack.append((k, depth + 1))
                stack.append((v, depth + 1))
        elif t is list:
            for item in node:
                stack.append((item, depth + 1))
        elif t is int:
            oracle.require_ok(
                node.bit_length() <= oracle.MAX_RATIONAL_BITS,
                "INT_TOO_LARGE",
                f"{label}: integer exceeds {oracle.MAX_RATIONAL_BITS} bits",
            )
        elif t is bool or node is None:
            pass
        else:
            raise oracle.AletheiaV22Error("INVALID_JSON_VALUE", f"{label}: unsupported type {t.__name__}")


def parse_strict_json_text(text: str, label: str, *, require_object: bool = True) -> Any:
    oracle.require_ok(type(text) is str, "INVALID_JSON_TEXT", f"{label}: text must be exact str")
    oracle.require_exact_bool(require_object, "require_object")
    oracle.require_ok("\x00" not in text, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_dup_keys,
            parse_constant=_reject_nonfinite,
            parse_float=_reject_float,
        )
    except oracle.AletheiaV22Error:
        raise
    except (ValueError, RecursionError) as exc:
        raise oracle.AletheiaV22Error("INVALID_JSON", f"{label}: {exc}") from exc
    if require_object:
        oracle.require_ok(type(parsed) is dict, "JSON_ROOT_NOT_OBJECT", f"{label}: JSON root must be dict")
    _validate_json_tree(parsed, label)
    return parsed


def canonical_json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _req_dict(parent: dict[str, Any], key: str, code: str) -> dict[str, Any]:
    val = parent.get(key)
    oracle.require_ok(type(val) is dict, code, f"{key} must be exact dict")
    return val


def _req_field(parent: dict[str, Any], key: str, code: str) -> Any:
    oracle.require_ok(key in parent, code, f"missing required field {key}")
    return parent[key]


def secondary_audit_payload(payload: dict[str, Any]) -> None:
    """Fail-closed schema-safe secondary algebraic invariant cross-check over Track S31 payload."""
    oracle.require_ok(type(payload) is dict, "AUDIT_PAYLOAD_TYPE", "payload must be exact dict")
    p1 = _req_dict(payload, "pillar_1_dpi_misfolding_separation", "AUDIT_MISSING_PILLAR")
    p2 = _req_dict(payload, "pillar_2_risk_asymmetry_and_bellwethers", "AUDIT_MISSING_PILLAR")
    p3 = _req_dict(payload, "pillar_3_siliquant_hadamard_bypass_bridge", "AUDIT_MISSING_PILLAR")
    p4 = _req_dict(payload, "pillar_4_aletheia_v22_governance_cs15_cs19", "AUDIT_MISSING_PILLAR")
    p5 = _req_dict(payload, "pillar_5_three_channel_provenance_airlock", "AUDIT_MISSING_PILLAR")

    # Cross-check P1 iso-Frobenius separation & -5x reversal
    toy = _req_dict(p1, "toy_64x16_iso_frobenius_separation", "AUDIT_P1_SCHEMA")
    oracle.require_ok(
        oracle.parse_exact_rational(_req_field(toy, "frobenius_energy_residual", "AUDIT_P1_ISO_FROB")) == Fraction(0, 1),
        "AUDIT_P1_ISO_FROB",
        "iso-Frobenius residual != 0",
    )
    oracle.require_ok(
        oracle.parse_exact_rational(_req_field(toy, "row_concentration_separation_factor", "AUDIT_P1_SEP")) == Fraction(32, 1),
        "AUDIT_P1_SEP",
        "row concentration separation != 32",
    )
    rev = _req_dict(p1, "rank1_spectral_and_reversal_detector", "AUDIT_P1_SCHEMA")
    rev5 = _req_dict(rev, "reversal_5x_projection", "AUDIT_P1_SCHEMA")
    ablit = _req_dict(rev, "abliteration_projection", "AUDIT_P1_SCHEMA")
    oracle.require_ok(
        oracle.parse_exact_rational(_req_field(rev5, "gamma_u", "AUDIT_P1_REV5")) == Fraction(-5, 1),
        "AUDIT_P1_REV5",
        "reversal gamma_u != -5",
    )
    oracle.require_ok(
        oracle.parse_exact_rational(_req_field(ablit, "gamma_u", "AUDIT_P1_ABLIT")) == Fraction(0, 1),
        "AUDIT_P1_ABLIT",
        "abliteration gamma_u != 0",
    )

    # Cross-check P2 exact k*(1/22) = 15 witness
    w22 = _req_dict(p2, "brindle_1_over_22_exact_threshold_witness", "AUDIT_P2_SCHEMA")
    oracle.require_ok(_req_field(w22, "k_star", "AUDIT_P2_KSTAR") == 15, "AUDIT_P2_KSTAR", "k*(1/22) != 15")
    oracle.require_ok(
        oracle.parse_exact_rational(_req_field(w22, "k_15_pass_at_k", "AUDIT_P2_SUM"))
        + oracle.parse_exact_rational(_req_field(w22, "k_15_pass_pow_k", "AUDIT_P2_SUM"))
        == Fraction(1, 1),
        "AUDIT_P2_SUM",
        "pass@15 + pass^15 != 1",
    )

    # Cross-check P3 Hadamard 1/8 spreading, live survival_fraction == 1 & token_embd bypass invariance
    h8_law = _req_dict(p3, "pure_spike_h8_spreading_law", "AUDIT_P3_SCHEMA")
    oracle.require_ok(
        oracle.parse_exact_rational(_req_field(h8_law, "coherence_ratio_drop", "AUDIT_P3_H8")) == Fraction(1, 8),
        "AUDIT_P3_H8",
        "H8 coherence drop != 1/8",
    )
    bypass = _req_dict(p3, "unquantized_token_embd_bypass_theorem", "AUDIT_P3_SCHEMA")
    oracle.require_ok(
        _req_field(bypass, "post_quant_embd_patch_exact_invariant", "AUDIT_P3_BYPASS") is True,
        "AUDIT_P3_BYPASS",
        "token_embd bypass invariant failed",
    )
    oracle.require_ok(
        oracle.parse_exact_rational(_req_field(bypass, "survival_fraction", "AUDIT_P3_SURV")) == Fraction(1, 1),
        "AUDIT_P3_SURV",
        "token_embd survival_fraction != 1",
    )

    # Cross-check P4 2.64x LoRA flip & 300/300 distinct synthetic abstention
    cs16 = _req_dict(p4, "cs16_matched_gain_pareto", "AUDIT_P4_SCHEMA")
    lora = _req_dict(cs16, "lora_vs_full_ft_2p64x_flip", "AUDIT_P4_SCHEMA")
    oracle.require_ok(
        oracle.parse_exact_rational(_req_field(lora, "matched_ratio_fa_over_fb", "AUDIT_P4_LORA")) == Fraction(66, 25),
        "AUDIT_P4_LORA",
        "LoRA matched ratio != 66/25 (2.64x)",
    )
    cs18 = _req_dict(p4, "cs18_abstention_and_tost", "AUDIT_P4_SCHEMA")
    oracle.require_ok(
        _req_field(cs18, "mismatched_300_abstained_count", "AUDIT_P4_CS18") == 300,
        "AUDIT_P4_CS18",
        "CS-18 abstention count != 300",
    )
    oracle.require_ok(
        _req_field(cs18, "distinct_synthetic_mismatched_records", "AUDIT_P4_CS18") == 300,
        "AUDIT_P4_CS18",
        "CS-18 distinct synthetic records != 300",
    )

    # Cross-check P5 airlock ALLOW on clean & DENY on all 5 negative controls
    clean_air = _req_dict(p5, "clean_compliant_record", "AUDIT_P5_SCHEMA")
    oracle.require_ok(_req_field(clean_air, "verdict", "AUDIT_P5_CLEAN") == "ALLOW", "AUDIT_P5_CLEAN", "clean airlock not ALLOW")
    neg = _req_dict(p5, "negative_controls", "AUDIT_P5_SCHEMA")
    oracle.require_ok(len(neg) == 5, "AUDIT_P5_NEG_COUNT", "expected exactly 5 negative controls")
    for name in neg:
        res = _req_dict(neg, name, "AUDIT_P5_NEG")
        oracle.require_ok(_req_field(res, "verdict", "AUDIT_P5_NEG") == "DENY", "AUDIT_P5_NEG", f"airlock negative control {name} not DENY")


def build_certificate() -> dict[str, Any]:
    payload = oracle.compute_s31_payload()
    payload_bytes = canonical_json_bytes(payload)
    payload_sha = hashlib.sha256(payload_bytes).hexdigest()
    envelope = {
        "schema_version": "1.0.0",
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    return {
        "schema_version": "1.0.0",
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


def verify_certificate_dict(cert: Any) -> dict[str, Any]:
    """Fail-closed in-memory certificate verifier (full pure-Q replay + secondary algebraic checks)."""
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    expected_keys = {"schema_version", "payload_sha256", "certificate_sha256", "payload"}
    oracle.require_ok(set(cert.keys()) == expected_keys, "INVALID_CERT_KEYS", "unexpected or missing cert keys")
    _validate_json_tree(cert, "cert")
    secondary_audit_payload(cert["payload"])
    expected = build_certificate()
    got_bytes = canonical_json_bytes(cert)
    exp_bytes = canonical_json_bytes(expected)
    oracle.require_ok(
        hmac.compare_digest(got_bytes, exp_bytes),
        "CERTIFICATE_MISMATCH",
        "certificate does not match freshly computed exact oracle output",
    )
    return {
        "valid": True,
        "payload_sha256": expected["payload_sha256"],
        "certificate_sha256": expected["certificate_sha256"],
    }


def verify_certificate_file(cert_path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_capped(cert_path, "certificate")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise oracle.AletheiaV22Error("INVALID_UTF8", f"certificate: invalid UTF-8 ({exc})") from exc
    oracle.require_ok("\r" not in text, "CRLF_FORBIDDEN", "certificate: CRLF line endings forbidden")
    parsed = parse_strict_json_text(text, "certificate", require_object=True)
    expected_keys = {"schema_version", "payload_sha256", "certificate_sha256", "payload"}
    oracle.require_ok(set(parsed.keys()) == expected_keys, "INVALID_CERT_KEYS", "unexpected or missing cert keys")
    secondary_audit_payload(parsed["payload"])
    expected = build_certificate()
    exp_bytes = canonical_json_bytes(expected)
    oracle.require_ok(
        hmac.compare_digest(raw, exp_bytes),
        "CERTIFICATE_BYTE_MISMATCH",
        "certificate bytes do not match canonical oracle output",
    )
    return {
        "valid": True,
        "payload_sha256": expected["payload_sha256"],
        "certificate_sha256": expected["certificate_sha256"],
    }


def _validate_cli_argv(argv: Any) -> list[str]:
    oracle.require_ok(type(argv) is list, "INVALID_ARGV", "argv must be exact list")
    for item in argv:
        oracle.require_ok(type(item) is str, "INVALID_ARGV", "argv entries must be exact str")
        oracle.require_ok("\x00" not in item, "NUL_BYTE_FORBIDDEN", "NUL byte forbidden in argv")
        try:
            item.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise oracle.AletheiaV22Error("INVALID_UTF8_SURROGATE", "lone UTF-16 surrogate in argv") from exc
    return argv


def _validate_cli_path_arg(arg: str, flag: str) -> Path:
    oracle.require_ok(len(arg) > 0, "INVALID_PATH_ARG", f"{flag}: path argument must be non-empty")
    oracle.require_ok(not arg.startswith("-"), "INVALID_PATH_ARG", f"{flag}: flag-like path argument forbidden")
    return Path(arg)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _validate_cli_argv(list(sys.argv[1:]) if argv is None else argv)
        if args in ([], ["--standalone", "--json"]):
            cert = build_certificate()
            sys.stdout.buffer.write(canonical_json_bytes(cert))
            sys.stdout.buffer.flush()
            return 0
        if len(args) == 2 and args[0] == "--write":
            out_path = _validate_cli_path_arg(args[1], "--write")
            cert = build_certificate()
            write_regular_bytes_safe(out_path, canonical_json_bytes(cert), "certificate")
            return 0
        if len(args) == 2 and args[0] == "--check":
            chk_path = _validate_cli_path_arg(args[1], "--check")
            res = verify_certificate_file(chk_path)
            sys.stdout.write(json.dumps(res, sort_keys=True, separators=(",", ":")) + "\n")
            return 0
        if len(args) == 3 and args[0] == "--check" and args[2] == "--json":
            chk_path = _validate_cli_path_arg(args[1], "--check")
            res = verify_certificate_file(chk_path)
            sys.stdout.write(json.dumps(res, sort_keys=True, separators=(",", ":")) + "\n")
            return 0
        raise oracle.AletheiaV22Error(
            "INVALID_CLI_ARGS",
            "usage: aletheia_v22_misfolding_audit.py (--standalone --json | --write <path> | --check <path> [--json])",
        )
    except oracle.AletheiaV22Error as exc:
        sys.stderr.write(f"[FAIL] {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
